"""Wave-0 RED contract for the unprotected multi-candidate controller."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from skillscout.application.ports import ErrorCode, SafeFailure


ROOT = Path(__file__).resolve().parents[1]
APPLICATION_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-discovery-application-missing",
)

BUSINESS_OUTCOMES = (
    "filter_rejected",
    "no_workflow",
    "qualification_rejected",
    "validation_rejected",
    "review_rejected",
    "completed_reuse",
    "eligible_local_candidate",
)
CONTINUABLE_OUTCOMES = BUSINESS_OUTCOMES + ("semantic_outcome_unknown",)
FATAL_OUTCOMES = (
    "state_integrity_conflict",
    "permanent_failure",
)


def _module():
    return importlib.import_module("skillscout.application.discovery")


def test_outcome_matrix_keeps_business_quarantine_and_fatal_classes_distinct() -> None:
    assert len(set(BUSINESS_OUTCOMES)) == len(BUSINESS_OUTCOMES)
    assert set(CONTINUABLE_OUTCOMES).isdisjoint(FATAL_OUTCOMES)
    assert "confirmed_retryable" not in CONTINUABLE_OUTCOMES
    assert "semantic_outcome_unknown" in CONTINUABLE_OUTCOMES


def test_crash_matrix_names_every_non_refundable_durability_seam() -> None:
    seams = (
        "before_page_dedup",
        "after_page_dedup",
        "before_discovery_reservation",
        "after_discovery_reservation",
        "before_semantic_attempt_start",
        "after_semantic_attempt_start",
        "before_semantic_result",
        "after_semantic_result",
        "before_candidate_terminal",
        "after_candidate_terminal",
        "before_final_handoff_sync",
        "after_final_handoff_sync",
    )
    assert len(seams) == len(set(seams))
    assert all(
        seam.startswith(("before_", "after_"))
        for seam in seams
    )


def test_discovery_dependency_surface_has_no_publication_authority() -> None:
    module = _module()
    dependencies = getattr(module, "DiscoveryDependencies")
    fields = set(getattr(dependencies, "__annotations__", {}))
    assert {
        "search_factory",
        "operations_store_factory",
        "state_restore",
        "durability_barrier",
        "phase2_factory",
        "phase3_factory",
    } <= fields
    forbidden = {
        "publication",
        "publisher",
        "catalog",
        "catalog_token",
        "publication_factory",
        "remote_publisher",
    }
    assert fields.isdisjoint(forbidden)


def test_discovery_source_imports_phase2_phase3_but_never_phase4() -> None:
    module = _module()
    source_path = Path(inspect.getsourcefile(module) or "")
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "skillscout.application.pipeline" in imported
    assert "skillscout.application.phase3" in imported
    assert "skillscout.application.publication" not in imported
    literals = {
        node.value.casefold()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any(
        marker in literal
        for marker in ("github_publish", "catalog token", "publicationapplication")
        for literal in literals
    )


def test_application_contract_exposes_bounded_result_and_run_only() -> None:
    module = _module()
    application = getattr(module, "DiscoveryApplication")
    result = getattr(module, "DiscoveryApplicationResult")
    assert tuple(inspect.signature(application.run).parameters) in (
        ("self",),
        ("self", "authority"),
    )
    fields = set(getattr(result, "model_fields", {})) | set(
        getattr(result, "__annotations__", {})
    )
    assert {
        "run_id",
        "state_root_digest",
        "state_commit_sha",
        "eligible_candidates",
    } <= fields
    assert fields.isdisjoint(
        {
            "publication_admission",
            "publication_intent",
            "catalog_token",
            "repository_text",
            "provider_response",
        }
    )


def test_three_workflow_repository_uses_one_semantic_reservation() -> None:
    module = _module()
    scenario = module.DiscoveryScenario(
        repository_id=910001,
        workflows=(
            module.WorkflowScenario("eligible"),
            module.WorkflowScenario("qualification_rejected"),
            module.WorkflowScenario("review_rejected"),
        ),
    )
    result = module.evaluate_discovery_scenario(scenario)
    assert result.semantic_reservation_count == 1
    assert result.workflow_outcomes == (
        "eligible_local_candidate",
        "qualification_rejected",
        "review_rejected",
    )
    assert len(set(result.workflow_authority_digests)) == 3


@pytest.mark.parametrize(
    "outcome",
    CONTINUABLE_OUTCOMES,
)
def test_business_and_quarantine_outcomes_continue_later_candidates(
    outcome: str,
) -> None:
    module = _module()
    result = module.evaluate_discovery_scenario(
        module.DiscoveryScenario(
            repository_id=910001,
            terminal=outcome,
            later_repository_id=910002,
        )
    )
    assert result.processed_repository_ids == (910001, 910002)
    if outcome == "semantic_outcome_unknown":
        assert result.provider_request_count == 1
        assert result.automatic_replay_count == 0


@pytest.mark.parametrize("outcome", FATAL_OUTCOMES)
def test_integrity_and_permanent_failures_stop_the_run(outcome: str) -> None:
    module = _module()
    result = module.evaluate_discovery_scenario(
        module.DiscoveryScenario(
            repository_id=910001,
            terminal=outcome,
            later_repository_id=910002,
        )
    )
    assert result.processed_repository_ids == (910001,)
    assert result.run_status in {"integrity_conflict", "permanent_failure"}


def test_unknown_outcome_consumes_once_without_automatic_replay() -> None:
    module = _module()
    result = module.evaluate_discovery_scenario(
        module.DiscoveryScenario(
            repository_id=910001,
            workflows=(module.WorkflowScenario("semantic_outcome_unknown"),),
            later_repository_id=910002,
        )
    )
    assert result.semantic_reservation_count == 1
    assert result.provider_request_count == 1
    assert result.automatic_replay_count == 0
    assert result.processed_repository_ids == (910001, 910002)
    assert result.run_status == "completed_degraded"


def test_eligible_handoff_locator_is_bounded_and_non_authorizing() -> None:
    module = _module()
    authority = "sha256:" + ("a" * 64)
    identity = "sha256:" + ("b" * 64)
    locator = module.eligible_candidate_locator(
        authority_digest=authority,
        workflow_identity_digest=identity,
    )
    assert locator.locator == (
        "state/objects/sha256/aa/" + ("a" * 64) + ".json"
    )
    assert set(locator.__annotations__) == {
        "locator",
        "authority_digest",
        "workflow_identity_digest",
    }


def test_forbidden_publication_factory_cannot_be_offered_to_dependencies() -> None:
    module = _module()
    calls: list[str] = []

    def forbidden() -> object:
        calls.append("publication_construct")
        return object()

    with pytest.raises(TypeError):
        module.DiscoveryDependencies(  # type: ignore[call-arg]
            search_factory=lambda: object(),
            operations_store_factory=lambda: object(),
            state_restore=lambda: object(),
            durability_barrier=object(),
            phase2_factory=lambda: object(),
            phase3_factory=lambda: object(),
            publication_factory=forbidden,
        )
    assert calls == []


def test_unexpected_health_failure_collapses_without_raw_exception() -> None:
    module = _module()

    class Operations:
        def run_discovery(self, **_kwargs: object) -> object:
            raise RuntimeError("SECRET_EXCEPTION_CANARY")

    dependencies = module.DiscoveryDependencies(
        search_factory=lambda: object(),
        operations_store_factory=Operations,
        state_restore=lambda: object(),
        durability_barrier=object(),
        phase2_factory=lambda: object(),
        phase3_factory=lambda: object(),
    )
    with pytest.raises(SafeFailure) as failure:
        module.DiscoveryApplication(dependencies).run()
    assert failure.value.code is ErrorCode.PIPELINE_INTERRUPTED
    assert "SECRET_EXCEPTION_CANARY" not in str(failure.value)
