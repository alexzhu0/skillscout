"""Canonical, non-circular identity functions for immutable stage facts."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel

from skillscout.domain.enums import PipelineStage
from skillscout.domain.models import StageEnvelope, StageInput


def _json_compatible(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=False)
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_json_bytes(value: object) -> bytes:
    """Encode the sole canonical JSON form, retaining explicit null fields."""

    return json.dumps(
        _json_compatible(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_digest(value: object) -> str:
    """Return a tagged lowercase SHA-256 over canonical bytes or supplied bytes."""

    payload = value if isinstance(value, bytes) else canonical_json_bytes(value)
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def stage_input_hash(stage_input: StageInput) -> str:
    """Hash exactly the complete stage input, which contains no hash of itself."""

    return sha256_digest(stage_input)


def stage_output_hash(
    *,
    schema_version: str,
    subject_id: str,
    stage: PipelineStage,
    producer_version: str,
    prompt_version: str | None,
    policy_version: str | None,
    model_id: str | None,
    payload: dict[str, Any],
) -> str:
    """Hash semantic output identity, excluding run-local and telemetry fields."""

    if schema_version == "1":
        return sha256_digest(
            {
                "schema_version": schema_version,
                "stage": stage.value,
                "subject_id": subject_id,
                "producer_version": producer_version,
                "payload": payload,
            }
        )
    return sha256_digest(
        {
            "schema_version": schema_version,
            "subject_id": subject_id,
            "stage": stage.value,
            "producer_version": producer_version,
            "prompt_version": prompt_version,
            "policy_version": policy_version,
            "model_id": model_id,
            "payload": payload,
        }
    )


def stage_manifest_hash(envelope: StageEnvelope) -> str:
    """Address the whole immutable envelope except its own manifest hash."""

    preimage = envelope.model_dump(mode="json", exclude_none=False, exclude={"manifest_hash"})
    return sha256_digest(preimage)


def reusable_key_digest(
    *,
    subject_id: str,
    stage: PipelineStage,
    input_hash: str,
    producer_version: str,
    retry_policy_version: str,
) -> str:
    """Hash exactly the five fields that own reuse and retry budgets."""

    return sha256_digest(
        {
            "subject_id": subject_id,
            "stage": stage.value,
            "input_hash": input_hash,
            "producer_version": producer_version,
            "retry_policy_version": retry_policy_version,
        }
    )


def make_result_id(
    *,
    subject_id: str,
    stage: PipelineStage,
    input_hash: str,
    producer_version: str,
    output_hash: str,
    retry_policy_version: str | None = None,
) -> str:
    """Derive a deterministic result identity from semantic producer facts."""

    preimage = {
        "subject_id": subject_id,
        "stage": stage.value,
        "input_hash": input_hash,
        "producer_version": producer_version,
        "output_hash": output_hash,
    }
    if retry_policy_version is not None:
        preimage["retry_policy_version"] = retry_policy_version
    return sha256_digest(preimage)


def make_result_row_id(*, run_id: str, stage: PipelineStage) -> str:
    """Hash the canonical run/stage association, separate from semantic identity."""

    return sha256_digest({"run_id": run_id, "stage": stage.value})
