"""Strict identity and transition contracts for the schema-v2 ledger."""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from skillscout.domain.canonical import (
    canonical_json_bytes,
    make_result_id,
    reusable_key_digest,
    stage_input_hash,
    stage_manifest_hash,
    stage_output_hash,
)
from skillscout.domain.enums import (
    AttemptStatus,
    ExecutionMode,
    PipelineStage,
    RunStatus,
    validate_attempt_transition,
    validate_run_transition,
    validate_stage_successor,
)
from skillscout.domain.models import StageAttempt, StageEnvelope, StageInput, TokenUsage


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _stage_input(**changes: object) -> StageInput:
    values: dict[str, object] = {
        "schema_version": "2",
        "execution_mode": ExecutionMode.DRY_RUN,
        "subject_id": "fixture:approved-workflow",
        "stage": PipelineStage.VALIDATORS,
        "previous_output_hash": "sha256:" + "1" * 64,
        "fixture_hash": None,
    }
    values.update(changes)
    return StageInput.model_validate(values)


def _attempt(**changes: object) -> StageAttempt:
    input_hash = stage_input_hash(_stage_input())
    values: dict[str, object] = {
        "attempt_id": "run-1:validators:1",
        "run_id": "run-1",
        "subject_id": "fixture:approved-workflow",
        "stage": PipelineStage.VALIDATORS,
        "stage_index": 6,
        "attempt_no": 1,
        "status": AttemptStatus.RUNNING,
        "input_hash": input_hash,
        "producer_version": "fixture-v1",
        "retry_policy_version": "retry-v1",
        "reusable_key_digest": reusable_key_digest(
            subject_id="fixture:approved-workflow",
            stage=PipelineStage.VALIDATORS,
            input_hash=input_hash,
            producer_version="fixture-v1",
            retry_policy_version="retry-v1",
        ),
        "started_at": "2026-07-17T00:00:00.000000Z",
        "finished_at": None,
        "prompt_version": None,
        "policy_version": None,
        "model_id": None,
        "request_id": None,
        "latency_ms": None,
        "token_usage": None,
        "error_code": None,
        "error_summary": None,
        "retryable": False,
    }
    values.update(changes)
    return StageAttempt.model_validate(values)


def _envelope(**changes: object) -> StageEnvelope:
    payload = {"outcome": "accepted", "说明": "稳定"}
    input_hash = stage_input_hash(_stage_input())
    output_hash = stage_output_hash(
        schema_version="2",
        subject_id="fixture:approved-workflow",
        stage=PipelineStage.VALIDATORS,
        producer_version="fixture-v1",
        prompt_version=None,
        policy_version=None,
        model_id=None,
        payload=payload,
    )
    values: dict[str, object] = {
        "schema_version": "2",
        "result_id": make_result_id(
            subject_id="fixture:approved-workflow",
            stage=PipelineStage.VALIDATORS,
            input_hash=input_hash,
            producer_version="fixture-v1",
            output_hash=output_hash,
        ),
        "run_id": "run-1",
        "attempt_id": "run-1:validators:1",
        "attempt_no": 1,
        "subject_id": "fixture:approved-workflow",
        "stage": PipelineStage.VALIDATORS,
        "stage_index": 6,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "producer_version": "fixture-v1",
        "prompt_version": None,
        "policy_version": None,
        "model_id": None,
        "request_id": None,
        "created_at": "2026-07-17T00:00:01.000000Z",
        "payload": payload,
        "manifest_hash": None,
    }
    values.update(changes)
    provisional = StageEnvelope.model_validate(values)
    return provisional.model_copy(
        update={"manifest_hash": stage_manifest_hash(provisional)},
    )


def test_models_are_strict_frozen_and_reject_extras() -> None:
    with pytest.raises(ValidationError):
        TokenUsage(prompt_tokens="1", completion_tokens=2, total_tokens=3)
    with pytest.raises(ValidationError):
        StageInput.model_validate({**_stage_input().model_dump(), "unexpected": True})

    attempt = _attempt()
    with pytest.raises(ValidationError):
        attempt.status = AttemptStatus.SUCCEEDED


def test_canonical_json_preserves_explicit_nulls_unicode_and_key_order() -> None:
    encoded = canonical_json_bytes(_attempt())
    decoded = json.loads(encoded)
    assert decoded["request_id"] is None
    assert decoded["token_usage"] is None
    assert encoded == json.dumps(
        decoded,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert "稳定".encode() in canonical_json_bytes(_envelope())

    with pytest.raises(ValueError):
        canonical_json_bytes({"not_finite": float("nan")})


def test_stage_input_hash_has_one_exact_non_self_referential_preimage() -> None:
    stage_input = _stage_input()
    expected = _digest(
        {
            "execution_mode": "dry_run",
            "fixture_hash": None,
            "previous_output_hash": "sha256:" + "1" * 64,
            "schema_version": "2",
            "stage": "validators",
            "subject_id": "fixture:approved-workflow",
        }
    )
    assert stage_input_hash(stage_input) == expected


def test_output_identity_ignores_run_attempt_time_and_request_only() -> None:
    baseline = _envelope()
    local_change = _envelope(
        run_id="run-2",
        attempt_id="run-2:validators:7",
        attempt_no=7,
        request_id="request-9",
        created_at="2026-07-18T00:00:00.000000Z",
    )
    assert local_change.output_hash == baseline.output_hash

    for change in (
        {"payload": {"outcome": "rejected"}},
        {"producer_version": "fixture-v2"},
        {"prompt_version": "prompt-v2"},
        {"policy_version": "policy-v2"},
        {"model_id": "model-v2"},
    ):
        changed = stage_output_hash(
            schema_version="2",
            subject_id="fixture:approved-workflow",
            stage=PipelineStage.VALIDATORS,
            producer_version=change.get("producer_version", "fixture-v1"),
            prompt_version=change.get("prompt_version"),
            policy_version=change.get("policy_version"),
            model_id=change.get("model_id"),
            payload=change.get("payload", {"outcome": "accepted", "说明": "稳定"}),
        )
        assert changed != baseline.output_hash


def test_manifest_hash_covers_envelope_except_itself() -> None:
    envelope = _envelope()
    assert stage_manifest_hash(envelope) == envelope.manifest_hash
    assert stage_manifest_hash(
        envelope.model_copy(update={"manifest_hash": "sha256:" + "f" * 64})
    ) == envelope.manifest_hash
    assert stage_manifest_hash(envelope.model_copy(update={"request_id": "request-2"})) != (
        envelope.manifest_hash
    )


def test_reusable_key_has_exact_five_field_preimage() -> None:
    base = {
        "subject_id": "fixture:approved-workflow",
        "stage": PipelineStage.VALIDATORS,
        "input_hash": "sha256:" + "2" * 64,
        "producer_version": "fixture-v1",
        "retry_policy_version": "retry-v1",
    }
    digest = reusable_key_digest(**base)
    assert digest == _digest(
        {
            "input_hash": base["input_hash"],
            "producer_version": "fixture-v1",
            "retry_policy_version": "retry-v1",
            "stage": "validators",
            "subject_id": "fixture:approved-workflow",
        }
    )
    assert len(digest) == len("sha256:") + 64

    changes = (
        {"subject_id": "fixture:other"},
        {"stage": PipelineStage.REVIEWER},
        {"input_hash": "sha256:" + "3" * 64},
        {"producer_version": "fixture-v2"},
        {"retry_policy_version": "retry-v2"},
    )
    assert all(reusable_key_digest(**(base | change)) != digest for change in changes)

    first = _attempt()
    second = _attempt(
        attempt_id="run-1:validators:2",
        attempt_no=2,
        status=AttemptStatus.FAILED,
        finished_at="2026-07-17T00:00:02.000000Z",
        latency_ms=50,
        token_usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        error_code="transient_failure",
        error_summary="Stage processing failed.",
        retryable=True,
    )
    assert first.reusable_key_digest == second.reusable_key_digest


@pytest.mark.parametrize(
    "missing",
    ("input_hash", "producer_version", "retry_policy_version", "reusable_key_digest"),
)
def test_running_attempt_requires_precomputed_identity(missing: str) -> None:
    values = _attempt().model_dump()
    values.pop(missing)
    with pytest.raises(ValidationError):
        StageAttempt.model_validate(values)


def test_closed_stages_and_transitions() -> None:
    expected = (
        "scout",
        "filter",
        "reader",
        "extractor",
        "qualifier",
        "generator",
        "validators",
        "reviewer",
        "publication_planner",
    )
    assert tuple(stage.value for stage in PipelineStage) == expected
    for current, successor in zip(PipelineStage, tuple(PipelineStage)[1:], strict=True):
        assert validate_stage_successor(current, successor) is successor
    with pytest.raises(ValueError):
        validate_stage_successor(PipelineStage.SCOUT, PipelineStage.READER)

    assert validate_run_transition(RunStatus.RUNNING, RunStatus.INTERRUPTED) is RunStatus.INTERRUPTED
    assert validate_run_transition(RunStatus.INTERRUPTED, RunStatus.RUNNING) is RunStatus.RUNNING
    with pytest.raises(ValueError):
        validate_run_transition(RunStatus.PLANNED_NOT_PUBLISHED, RunStatus.RUNNING)

    assert (
        validate_attempt_transition(AttemptStatus.RUNNING, AttemptStatus.SUCCEEDED)
        is AttemptStatus.SUCCEEDED
    )
    with pytest.raises(ValueError):
        validate_attempt_transition(AttemptStatus.SUCCEEDED, AttemptStatus.RUNNING)


def test_digest_fields_reject_noncanonical_values() -> None:
    with pytest.raises(ValidationError):
        _attempt(input_hash="ABC")
    with pytest.raises(ValidationError):
        _envelope(output_hash="sha256:" + "A" * 64)
