"""Explicitly opt-in contract for the separately authorized live canary.

This module never constructs an HTTP client unless every admission variable is
present.  It deliberately has no cleanup operation: a bounded manifest is the
only handoff to the separately authorized human/admin cleanup process.

Residual platform risk: a Pull requests write installation token may be able to
mark a pull request ready outside SkillScout.  SkillScout keeps that transition
human-only by omitting it from the production adapter, CLI, and workflow; it is
proved by static/transport surface evidence rather than a live platform denial.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import httpx
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
    "SKILLSCOUT_CANARY_POSITIVE_PULL",
    "SKILLSCOUT_CANARY_OTHERWISE_MERGEABLE_PR",
    "SKILLSCOUT_CANARY_DEFAULT_UPDATE_SHA",
    "SKILLSCOUT_CANARY_UNAUTHORIZED_REPOSITORY",
    "SKILLSCOUT_CANARY_UNAUTHORIZED_RESOURCE",
)
NEGATIVE_PROBES = (
    "default_ref_update",
    "merge",
    "ruleset_read",
    "ruleset_mutation",
    "unauthorized_repository_access",
    "repository_or_environment_secret_access",
)
SAFE_CLASSIFICATIONS = frozenset({"denied", "not_found", "conflict", "validation", "rate_limited"})
_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_FULL_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_LOGIN = re.compile(r"[A-Za-z0-9-]{1,39}")


@dataclass(frozen=True)
class LiveCanaryConfig:
    catalog_id: int
    catalog_full_name: str
    app_token: str = field(repr=False)
    ruleset_evidence_digest: str
    reviewer: str
    slug: str
    positive_pull_number: int
    otherwise_mergeable_pr: int
    default_update_sha: str
    unauthorized_repository: str
    unauthorized_resource: str


@dataclass(frozen=True)
class LiveCanaryResult:
    installation_id: int
    catalog_repository_id: int
    ruleset_evidence_digest: str
    machine_branch: str
    positive_pull_number: int
    positive_draft: bool
    requested_reviewers: tuple[str, ...]
    default_sha_before: str
    default_sha_after: str
    negative_classifications: tuple[tuple[str, str], ...]
    probe_installation_ids: tuple[int, ...]
    remote_state_unchanged: bool
    residual_platform_ready_risk: str
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
        positive_pull_number = int(values["SKILLSCOUT_CANARY_POSITIVE_PULL"])
        otherwise_mergeable_pr = int(values["SKILLSCOUT_CANARY_OTHERWISE_MERGEABLE_PR"])
    except ValueError:
        return None
    if catalog_id <= 0 or positive_pull_number <= 0 or otherwise_mergeable_pr <= 0:
        return None
    digest = values["SKILLSCOUT_CANARY_RULESET_EVIDENCE_DIGEST"]
    if _DIGEST.fullmatch(digest) is None:
        return None
    full_name = values["SKILLSCOUT_CANARY_CATALOG_FULL_NAME"]
    reviewer = values["SKILLSCOUT_CANARY_REVIEWER"]
    slug = values["SKILLSCOUT_CANARY_SLUG"]
    default_update_sha = values["SKILLSCOUT_CANARY_DEFAULT_UPDATE_SHA"]
    if (
        _FULL_NAME.fullmatch(full_name) is None
        or _LOGIN.fullmatch(reviewer) is None
        or _LOGIN.fullmatch(slug) is None
        or _SHA.fullmatch(default_update_sha) is None
        or positive_pull_number == otherwise_mergeable_pr
        or _FULL_NAME.fullmatch(values["SKILLSCOUT_CANARY_UNAUTHORIZED_REPOSITORY"]) is None
        or re.fullmatch(r"(?:actions/secrets|environments/[A-Za-z0-9_.-]+/secrets)", values["SKILLSCOUT_CANARY_UNAUTHORIZED_RESOURCE"]) is None
    ):
        return None
    return LiveCanaryConfig(
        catalog_id=catalog_id,
        catalog_full_name=full_name,
        app_token=values["SKILLSCOUT_CANARY_APP_TOKEN"],
        ruleset_evidence_digest=digest,
        reviewer=reviewer,
        slug=slug,
        positive_pull_number=positive_pull_number,
        otherwise_mergeable_pr=otherwise_mergeable_pr,
        default_update_sha=default_update_sha,
        unauthorized_repository=values["SKILLSCOUT_CANARY_UNAUTHORIZED_REPOSITORY"],
        unauthorized_resource=values["SKILLSCOUT_CANARY_UNAUTHORIZED_RESOURCE"],
    )


class CanaryGitHubClient:
    """Test-only live probe transport; it is never imported by production code."""

    def __init__(self, config: LiveCanaryConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {config.app_token}"},
            timeout=10.0,
            transport=transport,
        )
        self._installation_id: int | None = None

    @staticmethod
    def _classification(response: httpx.Response) -> str:
        if response.status_code in {401, 403, 405}:
            return "denied"
        if response.status_code == 404:
            return "not_found"
        if response.status_code == 409:
            return "conflict"
        if response.status_code == 422:
            return "validation"
        if response.status_code == 429:
            return "rate_limited"
        if 200 <= response.status_code < 300:
            return "success"
        raise AssertionError(f"unbounded canary status: {response.status_code}")

    def _json(self, method: str, path: str, *, payload: object | None = None) -> tuple[str, object]:
        response = self._client.request(method, path, json=payload)
        try:
            classification = self._classification(response)
            if classification != "success":
                return classification, None
            return classification, response.json()
        finally:
            response.close()

    def _required_json(self, path: str) -> dict[str, object]:
        classification, payload = self._json("GET", path)
        assert classification == "success" and isinstance(payload, dict)
        return payload

    def run(self) -> LiveCanaryResult:
        """Run explicit positive and negative probes; there is deliberately no cleanup."""

        try:
            installation = self._required_json("/installation")
            installation_id = installation.get("id")
            assert isinstance(installation_id, int) and installation_id > 0
            self._installation_id = installation_id
            catalog = self._required_json(f"/repos/{self._config.catalog_full_name}")
            assert (catalog.get("id"), catalog.get("full_name")) == (
                self._config.catalog_id,
                self._config.catalog_full_name,
            )
            base_branch = catalog.get("default_branch")
            assert isinstance(base_branch, str) and _LOGIN.fullmatch(base_branch)
            default_before = self._required_json(f"/repos/{self._config.catalog_full_name}/git/ref/heads/{base_branch}")
            default_sha_before = str(default_before.get("object", {}).get("sha", ""))
            assert _SHA.fullmatch(default_sha_before)
            positive = self._required_json(f"/repos/{self._config.catalog_full_name}/pulls/{self._config.positive_pull_number}")
            assert positive.get("number") == self._config.positive_pull_number
            assert positive.get("draft") is True
            assert positive.get("head", {}).get("ref") == f"skillscout/{self._config.slug}"
            requested = self._required_json(f"/repos/{self._config.catalog_full_name}/pulls/{self._config.positive_pull_number}/requested_reviewers")
            reviewers = tuple(item.get("login") for item in requested.get("users", []) if isinstance(item, dict))
            assert reviewers == (self._config.reviewer,)
            mergeable = self._required_json(f"/repos/{self._config.catalog_full_name}/pulls/{self._config.otherwise_mergeable_pr}")
            assert mergeable.get("number") == self._config.otherwise_mergeable_pr
            assert mergeable.get("draft") is False and mergeable.get("mergeable") is True
            probes = (
                ("default_ref_update", "PATCH", f"/repos/{self._config.catalog_full_name}/git/refs/heads/{base_branch}", {"sha": self._config.default_update_sha, "force": False}),
                ("merge", "PUT", f"/repos/{self._config.catalog_full_name}/pulls/{self._config.otherwise_mergeable_pr}/merge", {"merge_method": "squash"}),
                ("ruleset_read", "GET", f"/repos/{self._config.catalog_full_name}/rulesets", None),
                ("ruleset_mutation", "POST", f"/repos/{self._config.catalog_full_name}/rulesets", {"name": "skillscout-canary-probe", "target": "branch", "enforcement": "active", "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}, "rules": []}),
                ("unauthorized_repository_access", "GET", f"/repos/{self._config.unauthorized_repository}", None),
                ("repository_or_environment_secret_access", "GET", f"/repos/{self._config.catalog_full_name}/{self._config.unauthorized_resource}", None),
            )
            classifications = tuple((name, self._json(method, path, payload=payload)[0]) for name, method, path, payload in probes)
            assert all(classification in SAFE_CLASSIFICATIONS for _, classification in classifications)
            default_after = self._required_json(f"/repos/{self._config.catalog_full_name}/git/ref/heads/{base_branch}")
            default_sha_after = str(default_after.get("object", {}).get("sha", ""))
            assert _SHA.fullmatch(default_sha_after)
            return LiveCanaryResult(
                installation_id=installation_id,
                catalog_repository_id=self._config.catalog_id,
                ruleset_evidence_digest=self._config.ruleset_evidence_digest,
                machine_branch=f"skillscout/{self._config.slug}",
                positive_pull_number=self._config.positive_pull_number,
                positive_draft=True,
                requested_reviewers=reviewers,
                default_sha_before=default_sha_before,
                default_sha_after=default_sha_after,
                negative_classifications=classifications,
                probe_installation_ids=(installation_id,) * len(classifications),
                remote_state_unchanged=default_sha_before == default_sha_after,
                residual_platform_ready_risk="Pull requests write may permit ready-for-review outside SkillScout; production surface is closed and human-only.",
                cleanup_manifest=_cleanup_manifest(self._config, f"skillscout/{self._config.slug}", self._config.positive_pull_number),
            )
        finally:
            self._client.close()


def _canary_client(config: LiveCanaryConfig) -> CanaryGitHubClient:
    return CanaryGitHubClient(config)


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
        positive_pull_number=77,
        otherwise_mergeable_pr=79,
        default_update_sha="b" * 40,
        unauthorized_repository="other-org/private",
        unauthorized_resource="environments/controlled-publishing/secrets",
    )
    result = LiveCanaryResult(
        installation_id=4001,
        catalog_repository_id=config.catalog_id,
        ruleset_evidence_digest=config.ruleset_evidence_digest,
        machine_branch="skillscout/bounded-workflow-canary",
        positive_pull_number=78,
        positive_draft=True,
        requested_reviewers=(config.reviewer,),
        default_sha_before="a" * 40,
        default_sha_after="a" * 40,
        negative_classifications=tuple((probe, "denied") for probe in NEGATIVE_PROBES),
        probe_installation_ids=(4001,) * len(NEGATIVE_PROBES),
        remote_state_unchanged=True,
        residual_platform_ready_risk="Pull requests write may permit ready-for-review outside SkillScout; production surface is closed and human-only.",
        cleanup_manifest=_cleanup_manifest(config, "skillscout/bounded-workflow-canary", 78),
    )
    assert result.positive_draft is True
    assert result.default_sha_before == result.default_sha_after
    assert set(name for name, _ in result.negative_classifications) == set(NEGATIVE_PROBES)
    assert all(classification in SAFE_CLASSIFICATIONS for _, classification in result.negative_classifications)
    assert result.cleanup_manifest == (
        "repository:catalog-org/skills", "branch:skillscout/bounded-workflow-canary", "pull:78"
    )
    assert "not-rendered" not in repr(result)


def test_approve_and_ready_for_review_are_static_transport_proofs_not_live_denials() -> None:
    root = Path(__file__).resolve().parents[1]
    adapter_source = (root / "src/skillscout/adapters/github_publish.py").read_text(encoding="utf-8")
    cli_source = (root / "src/skillscout/cli.py").read_text(encoding="utf-8")
    workflow_source = (root / ".github/workflows/publish-candidate.yml").read_text(encoding="utf-8")
    for forbidden in ("/graphql", "/merge", "/reviews", "/ready-for-review", "submit_review", "ready_for_review"):
        assert forbidden not in adapter_source
        assert forbidden not in cli_source
    assert "ready-for-review" not in workflow_source
    assert "CanaryGitHubClient" not in adapter_source
    assert "approve" not in NEGATIVE_PROBES
    assert "ready_for_review" not in NEGATIVE_PROBES
    assert "residual platform risk" in __doc__.casefold()


def test_live_canary_execution_is_explicit_and_never_performs_cleanup() -> None:
    config = load_live_canary_config()
    if config is None:
        pytest.skip("live canary is not explicitly configured")
    client = _canary_client(config)
    result = client.run()  # pragma: no cover - opt-in only
    assert result.positive_draft is True
    assert result.default_sha_before == result.default_sha_after
    assert result.cleanup_manifest


def test_test_only_canary_uses_one_installation_identity_for_positive_and_negative_probes() -> None:
    """The future opt-in transport runner must expose no production client seam."""

    config = LiveCanaryConfig(
        catalog_id=910001,
        catalog_full_name="catalog-org/skills",
        app_token="not-rendered",
        ruleset_evidence_digest="sha256:" + "a" * 64,
        reviewer="skill-maintainer",
        slug="bounded-workflow-canary",
        positive_pull_number=78,
        otherwise_mergeable_pr=79,
        default_update_sha="b" * 40,
        unauthorized_repository="other-org/private",
        unauthorized_resource="environments/controlled-publishing/secrets",
    )
    requests: list[tuple[str, str, str | None]] = []

    def respond(request: object) -> object:
        import httpx

        assert isinstance(request, httpx.Request)
        requests.append((request.method, request.url.path, request.headers.get("authorization")))
        routes = {
            ("GET", "/installation"): {"id": 4001},
            ("GET", "/repos/catalog-org/skills"): {"id": 910001, "full_name": "catalog-org/skills", "default_branch": "main"},
            ("GET", "/repos/catalog-org/skills/git/ref/heads/main"): {"ref": "refs/heads/main", "object": {"sha": "a" * 40}},
            ("GET", "/repos/catalog-org/skills/pulls/78"): {"number": 78, "draft": True, "head": {"ref": "skillscout/bounded-workflow-canary"}},
            ("GET", "/repos/catalog-org/skills/pulls/78/requested_reviewers"): {"users": [{"login": "skill-maintainer"}]},
            ("GET", "/repos/catalog-org/skills/pulls/79"): {"number": 79, "draft": False, "mergeable": True},
        }
        payload = routes.get((request.method, request.url.path))
        if payload is not None:
            return httpx.Response(200, json=payload)
        return httpx.Response(403, json={"message": "denied"})

    import httpx

    result = CanaryGitHubClient(config, transport=httpx.MockTransport(respond)).run()
    assert result.installation_id == 4001
    assert result.positive_pull_number == 78
    assert result.positive_draft is True
    assert result.requested_reviewers == ("skill-maintainer",)
    assert result.remote_state_unchanged is True
    assert result.probe_installation_ids == (4001,) * len(NEGATIVE_PROBES)
    assert {name for name, _ in result.negative_classifications} == set(NEGATIVE_PROBES)
    assert all(value == "denied" for _, value in result.negative_classifications)
    assert all(header == "Bearer not-rendered" for _, _, header in requests)
    assert not any(method == "DELETE" for method, _, _ in requests)
