"""Wave-0 RED contracts for capability-separated acceptance orchestration."""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
from typing import Any

import pytest


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
