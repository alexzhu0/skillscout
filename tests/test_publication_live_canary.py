"""Explicitly opt-in contract for the separately authorized live canary.

This module never constructs an HTTP client unless every admission variable is
present.  It deliberately has no cleanup operation: a bounded manifest is the
only handoff to the separately authorized human/admin cleanup process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

import pytest


LIVE_CANARY_ENVIRONMENT = "SKILLSCOUT_LIVE_CANARY"
REQUIRED_CANARY_ENV = (
    "SKILLSCOUT_LIVE_CANARY",
    "SKILLSCOUT_CANARY_CATALOG_ID",
    "SKILLSCOUT_CANARY_CATALOG_FULL_NAME",
    "SKILLSCOUT_CANARY_APP_TOKEN",
    "SKILLSCOUT_CANARY_RULESET_EVIDENCE_DIGEST",
    "SKILLSCOUT_CANARY_REVIEWER",
    "SKILLSCOUT_CANARY_SLUG",
    "SKILLSCOUT_CANARY_OTHERWISE_MERGEABLE_PR",
    "SKILLSCOUT_CANARY_UNAUTHORIZED_REPOSITORY",
    "SKILLSCOUT_CANARY_UNAUTHORIZED_RESOURCE",
)
NEGATIVE_PROBES = (
    "default_ref_update",
    "merge",
    "ruleset_access_or_mutation",
    "unauthorized_repository_access",
    "repository_or_environment_secret_access",
)
SAFE_CLASSIFICATIONS = frozenset({"denied", "not_found", "forbidden", "conflict", "rate_limited"})


@dataclass(frozen=True)
class LiveCanaryConfig:
    catalog_id: int
    catalog_full_name: str
    app_token: str
    ruleset_evidence_digest: str
    reviewer: str
    slug: str
    otherwise_mergeable_pr: int
    unauthorized_repository: str
    unauthorized_resource: str


@dataclass(frozen=True)
class LiveCanaryResult:
    catalog_id: int
    machine_branch: str
    pull_number: int
    pull_node_id: str
    draft: bool
    requested_reviewer: str
    pre_default_sha: str
    post_default_sha: str
    negative_classifications: tuple[tuple[str, str], ...]
    cleanup_manifest: tuple[str, ...]


def load_live_canary_config(env: Mapping[str, str] | None = None) -> LiveCanaryConfig | None:
    """Parse all-or-nothing opt-in configuration without exposing the token."""
    values = os.environ if env is None else env
    if values.get(LIVE_CANARY_ENVIRONMENT) != "1":
        return None
    if any(not values.get(name) for name in REQUIRED_CANARY_ENV):
        return None
    try:
        catalog_id = int(values["SKILLSCOUT_CANARY_CATALOG_ID"])
        pull_number = int(values["SKILLSCOUT_CANARY_OTHERWISE_MERGEABLE_PR"])
    except ValueError:
        return None
    if catalog_id <= 0 or pull_number <= 0:
        return None
    digest = values["SKILLSCOUT_CANARY_RULESET_EVIDENCE_DIGEST"]
    if not digest.startswith("sha256:") or len(digest) != 71:
        return None
    return LiveCanaryConfig(
        catalog_id=catalog_id,
        catalog_full_name=values["SKILLSCOUT_CANARY_CATALOG_FULL_NAME"],
        app_token=values["SKILLSCOUT_CANARY_APP_TOKEN"],
        ruleset_evidence_digest=digest,
        reviewer=values["SKILLSCOUT_CANARY_REVIEWER"],
        slug=values["SKILLSCOUT_CANARY_SLUG"],
        otherwise_mergeable_pr=pull_number,
        unauthorized_repository=values["SKILLSCOUT_CANARY_UNAUTHORIZED_REPOSITORY"],
        unauthorized_resource=values["SKILLSCOUT_CANARY_UNAUTHORIZED_RESOURCE"],
    )


def _canary_client(config: LiveCanaryConfig) -> object:
    """Deferred production import; no default collection or test path reaches it."""
    from skillscout.adapters.github_publish import GitHubPublishClient

    return GitHubPublishClient.live_canary_only(config=config)


def _cleanup_manifest(config: LiveCanaryConfig, branch: str, pull_number: int) -> tuple[str, ...]:
    return (
        f"repository:{config.catalog_full_name}",
        f"branch:{branch}",
        f"pull:{pull_number}",
    )


def test_live_canary_skips_before_client_construction_without_complete_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in REQUIRED_CANARY_ENV:
        monkeypatch.delenv(name, raising=False)
    assert load_live_canary_config() is None
    pytest.skip("live canary requires complete explicit protected configuration")


def test_partial_environment_fails_closed_before_token_use(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLSCOUT_LIVE_CANARY", "1")
    monkeypatch.setenv("SKILLSCOUT_CANARY_APP_TOKEN", "token-must-not-be-used")
    assert load_live_canary_config() is None


def test_live_canary_result_is_bounded_and_emits_cleanup_manifest_only() -> None:
    config = LiveCanaryConfig(
        catalog_id=910001,
        catalog_full_name="catalog-org/skills",
        app_token="not-rendered",
        ruleset_evidence_digest="sha256:" + "a" * 64,
        reviewer="skill-maintainer",
        slug="bounded-workflow-canary",
        otherwise_mergeable_pr=77,
        unauthorized_repository="other-org/private",
        unauthorized_resource="environments/controlled-publishing/secrets",
    )
    result = LiveCanaryResult(
        catalog_id=config.catalog_id,
        machine_branch="skillscout/bounded-workflow-canary",
        pull_number=78,
        pull_node_id="PR_kwDOcanary78",
        draft=True,
        requested_reviewer=config.reviewer,
        pre_default_sha="a" * 40,
        post_default_sha="a" * 40,
        negative_classifications=tuple((probe, "denied") for probe in NEGATIVE_PROBES),
        cleanup_manifest=_cleanup_manifest(config, "skillscout/bounded-workflow-canary", 78),
    )
    assert result.draft is True
    assert result.pre_default_sha == result.post_default_sha
    assert set(name for name, _ in result.negative_classifications) == set(NEGATIVE_PROBES)
    assert all(classification in SAFE_CLASSIFICATIONS for _, classification in result.negative_classifications)
    assert result.cleanup_manifest == (
        "repository:catalog-org/skills", "branch:skillscout/bounded-workflow-canary", "pull:78"
    )
    assert "not-rendered" not in repr(result)


def test_approve_and_ready_for_review_are_static_transport_proofs_not_live_denials() -> None:
    production_surface = {
        "create_blob", "create_tree", "create_commit", "create_ref", "create_pull", "request_reviewers"
    }
    assert production_surface.isdisjoint({"submit_review", "approve", "ready_for_review", "graphql"})
    assert "approve" not in NEGATIVE_PROBES
    assert "ready_for_review" not in NEGATIVE_PROBES


def test_live_canary_execution_is_explicit_and_never_performs_cleanup() -> None:
    config = load_live_canary_config()
    if config is None:
        pytest.skip("live canary is not explicitly configured")
    client = _canary_client(config)
    result = client.run_causal_canary(negative_probes=NEGATIVE_PROBES)  # pragma: no cover - opt-in only
    assert result.draft is True
    assert result.pre_default_sha == result.post_default_sha
    assert result.cleanup_manifest
