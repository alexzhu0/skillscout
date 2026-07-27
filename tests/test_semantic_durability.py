"""Remote-confirmed semantic durability contract and state-branch barrier tests."""

from __future__ import annotations

from dataclasses import fields
import hashlib
import importlib
import inspect

import pytest


DIGEST_A = "sha256:" + ("a" * 64)
DIGEST_B = "sha256:" + ("b" * 64)
DIGEST_C = "sha256:" + ("c" * 64)
PRIOR_HEAD = "d" * 40
STATE_SHA = "e" * 40
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


def _transition(
    *,
    provider: str = "openai",
    stage: str = "extractor",
    attempt_no: int = 1,
    transition: str = "attempt_started",
):
    return _ports().SemanticDurabilityTransition.create(
        run_id="discovery-run-1",
        repository_id=101,
        workflow_authority_digest=DIGEST_A,
        provider=provider,
        stage=stage,
        attempt_no=attempt_no,
        transition=transition,
        expected_prior_state_head=PRIOR_HEAD,
        expected_prior_root_digest=DIGEST_B,
        pipeline_export_digest=DIGEST_A,
        operations_export_digest=DIGEST_B,
        publication_export_digest=DIGEST_C,
    )


def _receipt(request=None):
    module = _ports()
    transition = request or _transition()
    return module.DurabilityReceipt.from_remote_verification(
        transition=transition,
        verified_state_head=STATE_SHA,
        state_root_digest="sha256:" + ("f" * 64),
        pipeline_database_digest="sha256:" + ("1" * 64),
        operations_database_digest="sha256:" + ("2" * 64),
        publication_database_digest="sha256:" + ("3" * 64),
        pipeline_projection_digest="sha256:" + ("4" * 64),
        operations_projection_digest="sha256:" + ("5" * 64),
        publication_projection_digest="sha256:" + ("6" * 64),
    )


def test_contract_matrix_covers_two_providers_three_stages_and_four_transitions() -> None:
    matrix = {
        (provider, stage, transition)
        for provider in PROVIDERS
        for stage in STAGES
        for transition in TRANSITIONS
    }
    assert len(matrix) == 24
    for provider, stage, transition in matrix:
        request = _transition(
            provider=provider,
            stage=stage,
            transition=transition,
        )
        assert (request.provider, request.stage, request.transition) == (
            provider,
            stage,
            transition,
        )


def test_transition_authority_is_self_hashed_and_has_no_untrusted_payload_surface() -> None:
    module = _ports()
    request = _transition()
    assert request.transition_authority_digest.startswith("sha256:")
    assert module.SemanticDurabilityTransition.from_dict(
        request.as_dict()
    ) == request
    exposed = {field.name for field in fields(request)}
    assert not exposed.intersection(
        {
            "provider_payload",
            "provider_response",
            "repository_text",
            "exception",
            "error_message",
            "token",
            "secret",
        }
    )

    tampered = request.as_dict()
    tampered["attempt_no"] = 2
    with pytest.raises(ValueError, match="transition authority"):
        module.SemanticDurabilityTransition.from_dict(tampered)


@pytest.mark.parametrize("provider", ("", "OPENAI", "other", None))
def test_transition_rejects_invalid_provider(provider: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _ports().SemanticDurabilityTransition.create(
            run_id="discovery-run-1",
            repository_id=101,
            workflow_authority_digest=DIGEST_A,
            provider=provider,
            stage="extractor",
            attempt_no=1,
            transition="attempt_started",
            expected_prior_state_head=PRIOR_HEAD,
            expected_prior_root_digest=DIGEST_B,
            pipeline_export_digest=DIGEST_A,
            operations_export_digest=DIGEST_B,
            publication_export_digest=DIGEST_C,
        )


@pytest.mark.parametrize(
    ("stage", "attempt_no", "transition"),
    (
        ("scout", 1, "attempt_started"),
        ("extractor", 0, "attempt_started"),
        ("extractor", 17, "attempt_started"),
        ("extractor", 1, "started"),
        ("reviewer", 1, "result_retryable"),
    ),
)
def test_transition_rejects_invalid_stage_attempt_and_transition_combinations(
    stage: str,
    attempt_no: int,
    transition: str,
) -> None:
    with pytest.raises(ValueError):
        _transition(
            stage=stage,
            attempt_no=attempt_no,
            transition=transition,
        )


def test_receipt_binds_parent_root_transition_and_all_three_stores() -> None:
    request = _transition()
    receipt = _receipt(request)
    assert receipt.authorizes(request)
    assert receipt.verified_state_head == STATE_SHA
    assert receipt.expected_prior_state_head == PRIOR_HEAD
    assert receipt.transition_authority_digest == (
        request.transition_authority_digest
    )
    assert receipt.database_digests == (
        "sha256:" + ("1" * 64),
        "sha256:" + ("2" * 64),
        "sha256:" + ("3" * 64),
    )


@pytest.mark.parametrize(
    "field",
    (
        "transition_authority_digest",
        "expected_prior_state_head",
        "expected_prior_root_digest",
        "pipeline_export_digest",
        "operations_export_digest",
        "publication_export_digest",
    ),
)
def test_incomplete_or_mismatched_receipt_never_grants_authority(
    field: str,
) -> None:
    module = _ports()
    request = _transition()
    receipt = _receipt(request)
    changed = request.as_dict()
    changed[field] = (
        "a" * 40
        if field == "expected_prior_state_head"
        else "sha256:" + ("9" * 64)
    )
    if field != "transition_authority_digest":
        changed.pop("transition_authority_digest")
        other = module.SemanticDurabilityTransition.create(**changed)
    else:
        with pytest.raises(ValueError):
            module.SemanticDurabilityTransition.from_dict(changed)
        return
    assert receipt.authorizes(other) is False
    assert module.receipt_authorizes(other, receipt) is False
    with pytest.raises(module.SafeFailure) as failure:
        module.require_durability_receipt(other, receipt)
    assert failure.value.code is module.ErrorCode.STATE_OPERATION_FAILED


def test_missing_receipt_and_malformed_receipt_fail_with_closed_sanitized_error() -> None:
    module = _ports()
    request = _transition()
    for receipt in (None, object()):
        assert module.receipt_authorizes(request, receipt) is False
        with pytest.raises(module.SafeFailure) as failure:
            module.require_durability_receipt(request, receipt)
        assert failure.value.as_dict() == {
            "code": "state_operation_failed",
            "summary": "Local state operation failed.",
        }


def test_barrier_port_is_narrow_and_runtime_checkable() -> None:
    module = _ports()

    class Barrier:
        def confirm(self, *, transition, pipeline_store, operations_store, publication_store):
            del pipeline_store, operations_store, publication_store
            return _receipt(transition)

    assert isinstance(Barrier(), module.ThreeStoreDurabilityBarrier)
    parameters = inspect.signature(
        module.ThreeStoreDurabilityBarrier.confirm
    ).parameters
    assert tuple(parameters) == (
        "self",
        "transition",
        "pipeline_store",
        "operations_store",
        "publication_store",
    )


def test_receipt_digest_detects_forged_remote_confirmation() -> None:
    module = _ports()
    receipt = _receipt()
    raw = receipt.as_dict()
    raw["verified_state_head"] = "9" * 40
    with pytest.raises(ValueError, match="receipt digest"):
        module.DurabilityReceipt.from_dict(raw)
    assert hashlib.sha256(receipt.receipt_digest.encode("ascii")).digest()
