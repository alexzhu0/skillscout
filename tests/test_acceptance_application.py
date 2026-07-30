"""Wave-0 RED contracts for capability-separated acceptance orchestration."""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from skillscout.adapters.github import LicenseResponse, RateLimitFacts, RepoMetadata
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.acceptance import NominationEntryV1, NominationSetV1
from skillscout.domain.discovery import (
    DiscoveryQuerySetV1,
    SearchPageObservationV1,
    SearchRateLimitFactsV1,
    SearchRepositoryObservationV1,
)


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-07-30T00:00:00.000000Z"
DIGEST = "sha256:" + ("a" * 64)


REQUIRED_APPLICATION_CONTRACTS = (
    "NominationDependencies",
    "LockedCampaignDependencies",
    "ReplayUpdateDependencies",
    "HumanAttestationDependencies",
    "CleanupAttestationDependencies",
    "AcceptanceRebuildDependencies",
)

EVALUATOR_ONLY_FIELDS = {
    "expected_role",
    "expected_outcome",
    "evaluator_notes",
    "human_label",
}
LIVE_CAPABILITY_FIELDS = {
    "semantic_client_factory",
    "extractor_factory",
    "generator_factory",
    "reviewer_factory",
    "publication_factory",
    "publisher_factory",
    "catalog_token_factory",
    "credential_factory",
}


def _application_module(*, skip_if_missing: bool) -> Any:
    if importlib.util.find_spec("skillscout.application.acceptance") is None:
        if skip_if_missing:
            pytest.skip("phase6-application-contracts-not-yet-implemented")
        return None
    return importlib.import_module("skillscout.application.acceptance")


def _symbol(name: str, *, skip_if_missing: bool = True) -> type[Any]:
    module = _application_module(skip_if_missing=skip_if_missing)
    if module is None:
        pytest.fail(f"phase6-missing-application-contract:{name}", pytrace=False)
    value = getattr(module, name, None)
    if value is None:
        if skip_if_missing:
            pytest.skip("phase6-application-contracts-not-yet-implemented")
        pytest.fail(f"phase6-missing-application-contract:{name}", pytrace=False)
    return value


@pytest.mark.parametrize(
    "contract",
    REQUIRED_APPLICATION_CONTRACTS,
    ids=REQUIRED_APPLICATION_CONTRACTS,
)
def test_required_phase6_application_contract_is_missing(contract: str) -> None:
    _symbol(contract, skip_if_missing=False)


def _field_names(contract: str) -> set[str]:
    model = _symbol(contract)
    assert dataclasses.is_dataclass(model)
    return {field.name for field in dataclasses.fields(model)}


def test_nomination_signature_has_search_state_only_and_no_hypothesis_channel() -> None:
    fields = _field_names("NominationDependencies")
    assert {"search_factory", "operations_store_factory"} <= fields
    assert fields.isdisjoint(LIVE_CAPABILITY_FIELDS)
    assert fields.isdisjoint(EVALUATOR_ONLY_FIELDS)
    assert fields.isdisjoint(
        {
            "phase2_factory",
            "phase3_factory",
            "model",
            "endpoint",
            "catalog",
            "reviewer_targets",
        }
    )


def test_nomination_search_filters_and_pins_role_neutral_entries() -> None:
    module = _application_module(skip_if_missing=False)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )
    repositories = []
    for index in range(1, 7):
        values = {
            "schema_version": "search-repository-observation-v1",
            "repository_id": 910000 + index,
            "owner": "octo-org",
            "name": f"workflow-{index}",
            "full_name": f"octo-org/workflow-{index}",
            "private": False,
            "visibility": "public",
            "fork": False,
            "archived": False,
            "disabled": False,
            "default_branch": "main",
        }
        repositories.append(
            SearchRepositoryObservationV1(
                **values,
                observation_digest=sha256_digest(values),
            )
        )

    class Search:
        def search_repositories(
            self,
            *,
            query_set: DiscoveryQuerySetV1,
            discovery_run_authority_digest: str,
            query_ordinal: int,
            page: int,
        ) -> tuple[SearchPageObservationV1, tuple[SearchRepositoryObservationV1, ...]]:
            query = query_set.queries[query_ordinal - 1]
            values = {
                "schema_version": "search-page-observation-v1",
                "discovery_run_authority_digest": discovery_run_authority_digest,
                "query_set_version": query_set.query_set_version,
                "query_set_digest": query_set.query_set_digest,
                "query_id": query.query_id,
                "query_ordinal": query_ordinal,
                "query_text": query.query_text,
                "sort": query_set.sort,
                "order": query_set.order,
                "page": page,
                "per_page": query_set.per_page,
                "next_page": None,
                "total_count": len(repositories),
                "incomplete_results": False,
                "item_count": len(repositories),
                "request_id": f"request-{query_ordinal}-{page}",
                "rate_limit": SearchRateLimitFactsV1(
                    limit=30,
                    remaining=29,
                    used=1,
                    reset_epoch=1,
                    resource="search",
                ),
            }
            return (
                SearchPageObservationV1(
                    **values,
                    observation_digest=sha256_digest(
                        {
                            **values,
                            "rate_limit": values["rate_limit"].model_dump(
                                mode="json", exclude_none=False
                            ),
                        }
                    ),
                ),
                tuple(repositories),
            )

        def get_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
            index = int(repo.rpartition("-")[2])
            return RepoMetadata(
                id=910000 + index,
                owner=owner,
                name=repo,
                default_branch="main",
                private=False,
                fork=False,
                archived=False,
                disabled=False,
                visibility="public",
                license_spdx="GPL-3.0" if index == 6 else "MIT",
                rate_limit=RateLimitFacts(limit=5000, remaining=4999, reset=1),
            )

        def resolve_commit(self, owner: str, repo: str, ref: str) -> str:
            return f"{int(repo.rpartition('-')[2]):040x}"

        def get_license(self, owner: str, repo: str, sha: str) -> LicenseResponse:
            index = int(repo.rpartition("-")[2])
            return LicenseResponse(
                status="confirmed",
                spdx_id="GPL-3.0" if index == 6 else "MIT",
                license_blob_sha=f"{index + 100:040x}",
            )

        def close(self) -> None:
            pass

    nomination = module.nominate_search_candidates(
        search=Search(),
        query_set=query_set,
        search_run_authority_digest=DIGEST,
        nomination_set_id="nomination-search",
        created_at=TIMESTAMP,
    )

    assert len(nomination.search_derived_entries) == 5
    assert {entry.repository_id for entry in nomination.search_derived_entries} == {
        910001,
        910002,
        910003,
        910004,
        910005,
    }
    assert all(
        "coverage_role" not in entry.model_dump(mode="json")
        for entry in nomination.search_derived_entries
    )


def test_nomination_application_persists_fact_before_exact_state_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _application_module(skip_if_missing=False)
    entries = tuple(
        NominationEntryV1(
            schema_version="nomination-entry-v1",
            repository_full_name=f"octo-org/workflow-{index}",
            repository_id=910000 + index,
            exact_commit_sha=f"{index:040x}",
            license_spdx="MIT",
            selection_source="search_derived",
            selection_evidence_digests=(sha256_digest({"index": index}),),
        )
        for index in range(1, 6)
    )
    nomination = NominationSetV1.model_validate(
        {
            "schema_version": "nomination-set-v1",
            "nomination_set_id": "nomination-cas",
            "query_set_digest": DIGEST,
            "search_run_authority_digest": DIGEST,
            "search_derived_entries": tuple(
                entry.model_dump(mode="python", exclude_none=False)
                for entry in sorted(entries, key=lambda entry: entry.entry_digest or "")
            ),
            "user_nominated_entries": (),
            "created_at": TIMESTAMP,
        },
        strict=True,
    )
    monkeypatch.setattr(
        module,
        "nominate_search_candidates",
        lambda **_arguments: nomination,
    )
    recorded = []

    class Store:
        def record_acceptance_fact(
            self, acceptance_run_id: str, kind: str, fact: object
        ) -> object:
            from skillscout.adapters.operations_state import AcceptanceFactRecord

            recorded.append((acceptance_run_id, kind, fact))
            return AcceptanceFactRecord(
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact_digest=nomination.nomination_set_digest,
                fact=nomination,
            )

        def close(self) -> None:
            pass

    class Barrier:
        def sync_nomination(self, **arguments: object) -> object:
            assert recorded
            assert arguments["prior_root_digest"] == DIGEST
            return SimpleNamespace(
                status="verified",
                previous_head="a" * 40,
                commit_sha="b" * 40,
                root_digest="sha256:" + ("b" * 64),
            )

    dependencies = module.NominationDependencies(
        search_factory=lambda: SimpleNamespace(close=lambda: None),
        operations_store_factory=Store,
        state_restore=lambda: SimpleNamespace(
            status="verified",
            observed_head="a" * 40,
            bundle=SimpleNamespace(root=SimpleNamespace(root_digest=DIGEST)),
        ),
        durability_barrier=Barrier(),
    )
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )

    result = module.NominationApplication(
        dependencies,
        query_set=query_set,
        initial_state_root_digest=DIGEST,
    ).run(
        search_run_authority_digest=DIGEST,
        nomination_set_id="nomination-cas",
        created_at=TIMESTAMP,
    )

    assert result.nomination == nomination
    assert result.state_commit_sha == "b" * 40
    assert result.state_root_digest == "sha256:" + ("b" * 64)
    assert recorded == [("nomination-cas", "acceptance_nomination", nomination)]


def test_locked_campaign_signature_cannot_receive_evaluator_answers() -> None:
    fields = _field_names("LockedCampaignDependencies")
    assert {
        "discovery_factory",
        "operations_store_factory",
    } <= fields
    assert fields.isdisjoint(EVALUATOR_ONLY_FIELDS)
    assert fields.isdisjoint(
        {
            "benchmark_role",
            "selection_notes",
            "expected_terminal",
            "human_verdict",
        }
    )


def test_rebuild_and_attestation_signatures_have_no_live_semantic_or_edit_authority() -> None:
    for contract in (
        "HumanAttestationDependencies",
        "CleanupAttestationDependencies",
        "AcceptanceRebuildDependencies",
    ):
        fields = _field_names(contract)
        assert fields.isdisjoint(LIVE_CAPABILITY_FIELDS)
        assert fields.isdisjoint(EVALUATOR_ONLY_FIELDS)
        assert fields.isdisjoint(
            {
                "edit_candidate",
                "rewrite_skill",
                "approve_pull_request",
                "merge_pull_request",
                "mark_ready",
            }
        )


def test_offline_and_rebuild_application_surfaces_cannot_construct_live_adapters() -> None:
    module = _application_module(skip_if_missing=True)
    offline = getattr(module, "OfflineEvaluationDependencies", None)
    if offline is not None:
        assert {
            field.name for field in dataclasses.fields(offline)
        }.isdisjoint(LIVE_CAPABILITY_FIELDS | EVALUATOR_ONLY_FIELDS)
    rebuild = _field_names("AcceptanceRebuildDependencies")
    assert rebuild.isdisjoint(
        {
            "github_factory",
            "http_client_factory",
            "semantic_client_factory",
            "publication_factory",
        }
    )


def test_terminal_mapper_keeps_business_rejections_distinct_from_system_failures() -> None:
    module = _application_module(skip_if_missing=True)
    mapper = getattr(module, "classify_acceptance_terminal")
    for business in (
        "filter_rejected",
        "no_workflow",
        "qualification_rejected",
        "validation_rejected",
        "review_rejected",
    ):
        assert mapper(business) == "business_terminal"
    for failure in (
        "provider_exhausted",
        "schema_exhausted",
        "evidence_missing",
        "duplicate_effect",
        "unauthorized_effect",
        "harness_failed",
    ):
        assert mapper(failure) == "system_failure"


def test_semantic_request_projection_excludes_all_evaluator_only_metadata() -> None:
    module = _application_module(skip_if_missing=True)
    builder = getattr(module, "build_acceptance_semantic_payload")
    payload = builder(
        workflow_spec={"schema_version": "workflow-spec-v1"},
        provenance={"repository_id": 101, "source_commit_sha": "a" * 40},
    )
    assert type(payload) is dict
    assert set(payload).isdisjoint(EVALUATOR_ONLY_FIELDS)
    serialized = repr(payload)
    for canary in (
        "expected_role",
        "expected_outcome",
        "evaluator_notes",
        "human_label",
    ):
        assert canary not in serialized
