"""Wave-0 RED contract for remote-confirmed semantic durability barriers."""

from __future__ import annotations

import importlib

import pytest


DURABILITY_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-semantic-durability-missing",
)
DIGEST_A = "sha256:" + ("a" * 64)
DIGEST_B = "sha256:" + ("b" * 64)
STATE_SHA = "c" * 40
STAGES = ("extractor", "generator", "reviewer")
PROVIDERS = ("openai", "deepseek")
TRANSITIONS = (
    "attempt_started",
    "result_decided",
    "result_confirmed_retryable",
    "result_outcome_unknown",
)


def _ports():
    return importlib.import_module("skillscout.application.ports")


def test_barrier_matrix_covers_two_providers_three_stages_and_four_transitions() -> None:
    matrix = {
        (provider, stage, transition)
        for provider in PROVIDERS
        for stage in STAGES
        for transition in TRANSITIONS
    }
    assert len(matrix) == 24
    assert ("deepseek", "reviewer", "result_outcome_unknown") in matrix
    assert ("openai", "extractor", "attempt_started") in matrix


@DURABILITY_XFAIL
def test_receipt_binds_parent_root_transition_and_three_store_digests() -> None:
    module = _ports()
    receipt = module.DurabilityReceipt(
        schema_version="durability-receipt-v1",
        transition_authority_digest=DIGEST_A,
        expected_prior_state_head="d" * 40,
        verified_state_head=STATE_SHA,
        state_root_digest=DIGEST_B,
        pipeline_projection_digest=DIGEST_A,
        operations_projection_digest=DIGEST_B,
        publication_projection_digest="sha256:" + ("c" * 64),
    )
    assert receipt.authorizes(
        transition_authority_digest=DIGEST_A,
        expected_prior_state_head="d" * 40,
    )
    assert receipt.verified_state_head == STATE_SHA


@pytest.mark.parametrize("transition", TRANSITIONS)
@DURABILITY_XFAIL
def test_incomplete_or_mismatched_receipt_never_grants_authority(
    transition: str,
) -> None:
    module = _ports()
    request = module.SemanticDurabilityTransition(
        schema_version="semantic-durability-transition-v1",
        provider="openai",
        stage="extractor",
        attempt_no=1,
        transition=transition,
        transition_authority_digest=DIGEST_A,
        expected_prior_state_head="d" * 40,
    )
    assert request.transition == transition
    for mutation in (
        "missing_receipt",
        "wrong_transition",
        "wrong_parent",
        "wrong_root",
        "wrong_pipeline_projection",
        "wrong_operations_projection",
        "wrong_publication_projection",
    ):
        assert module.receipt_authorizes(request, mutation=mutation) is False


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize(
    "seam",
    (
        "before_attempt_started_sync",
        "after_attempt_started_sync",
        "before_result_sync",
        "after_result_sync",
        "export_pipeline_failed",
        "export_operations_failed",
        "export_publication_failed",
        "cas_failed",
        "reread_failed",
        "projection_mismatch",
    ),
)
@DURABILITY_XFAIL
def test_sync_failure_and_crash_matrix_has_zero_ambiguous_replay(
    provider: str,
    stage: str,
    seam: str,
) -> None:
    module = _ports()
    result = module.evaluate_semantic_barrier_scenario(
        provider=provider,
        stage=stage,
        seam=seam,
    )
    if seam in {
        "before_attempt_started_sync",
        "export_pipeline_failed",
        "export_operations_failed",
        "export_publication_failed",
        "cas_failed",
        "reread_failed",
        "projection_mismatch",
    }:
        assert result.provider_requests == 0
    else:
        assert result.provider_requests <= 1
    assert result.automatic_ambiguous_replays == 0
    assert result.terminal_without_receipt == 0
