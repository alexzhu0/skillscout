"""Strict immutable contracts crossing SkillScout pipeline boundaries."""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from skillscout.domain.enums import AttemptStatus, ExecutionMode, PipelineStage, RunStatus

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]

MAX_MANIFEST_BYTES = 262_144
MAX_STAGE_PAYLOAD_DEPTH = 16
MAX_STAGE_PAYLOAD_NODES = 4_096
MAX_STAGE_COLLECTION_ITEMS = 1_024
MAX_STAGE_KEY_BYTES = 256
MAX_STAGE_STRING_BYTES = 65_536
MAX_STAGE_INTEGER_ABS = 9_007_199_254_740_991

SUPPORTED_PRODUCER_SCHEMAS: frozenset[tuple[str, str]] = frozenset(
    {("1", "fixture-v1"), ("2", "fixture-v1")}
)


def validate_manifest_bytes(manifest_bytes: bytes) -> bytes:
    """Reject a canonical manifest above the one shared storage boundary."""

    if type(manifest_bytes) is not bytes or len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest bytes exceed the closed stage output contract")
    return manifest_bytes


def _bounded_utf8(value: str, maximum: int) -> bool:
    """Check a UTF-8 byte bound without first encoding an obviously huge value."""

    return len(value) <= maximum and len(value.encode("utf-8")) <= maximum


def _validate_json_tree(value: object) -> None:
    """Validate JSON types and resource bounds before Pydantic traverses the tree."""

    node_count = 0

    def visit(node: object, *, container_depth: int) -> None:
        nonlocal node_count
        node_count += 1
        if node_count > MAX_STAGE_PAYLOAD_NODES:
            raise ValueError("stage payload node limit exceeded")

        if node is None or type(node) is bool:
            return
        if type(node) is int:
            if abs(node) > MAX_STAGE_INTEGER_ABS:
                raise ValueError("stage payload integer limit exceeded")
            return
        if type(node) is float:
            if not math.isfinite(node):
                raise ValueError("stage payload number must be finite")
            return
        if type(node) is str:
            if not _bounded_utf8(node, MAX_STAGE_STRING_BYTES):
                raise ValueError("stage payload string limit exceeded")
            return

        if type(node) is list:
            if container_depth > MAX_STAGE_PAYLOAD_DEPTH:
                raise ValueError("stage payload depth limit exceeded")
            if len(node) > MAX_STAGE_COLLECTION_ITEMS:
                raise ValueError("stage payload collection limit exceeded")
            for item in node:
                visit(item, container_depth=container_depth + 1)
            return

        if type(node) is dict:
            if container_depth > MAX_STAGE_PAYLOAD_DEPTH:
                raise ValueError("stage payload depth limit exceeded")
            if len(node) > MAX_STAGE_COLLECTION_ITEMS:
                raise ValueError("stage payload collection limit exceeded")
            for key, item in node.items():
                if type(key) is not str:
                    raise ValueError("stage payload keys must be strings")
                if not _bounded_utf8(key, MAX_STAGE_KEY_BYTES):
                    raise ValueError("stage payload key limit exceeded")
                visit(item, container_depth=container_depth + 1)
            return

        raise ValueError("stage payload contains a non-JSON value")

    if type(value) is not dict:
        raise ValueError("stage payload must be a JSON object")
    visit(value, container_depth=1)


class StagePayload(RootModel[dict[str, Any]]):
    """Strict frozen JSON object accepted from a stage processor."""

    model_config = ConfigDict(frozen=True, strict=True)

    @model_validator(mode="before")
    @classmethod
    def validate_json_tree(cls, value: object) -> object:
        if isinstance(value, cls):
            return value
        _validate_json_tree(value)
        return value


class StrictFrozenModel(BaseModel):
    """One fail-closed configuration for every persisted domain object."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TokenUsage(StrictFrozenModel):
    prompt_tokens: NonNegativeInt
    completion_tokens: NonNegativeInt
    total_tokens: NonNegativeInt


class StageInput(StrictFrozenModel):
    schema_version: NonEmpty
    execution_mode: ExecutionMode
    subject_id: NonEmpty
    stage: PipelineStage
    previous_output_hash: Digest | None
    fixture_hash: Digest | None


class StageEnvelope(StrictFrozenModel):
    schema_version: NonEmpty
    result_row_id: Digest
    result_id: Digest
    run_id: NonEmpty
    attempt_id: NonEmpty
    attempt_no: Annotated[int, Field(ge=1)]
    subject_id: NonEmpty
    stage: PipelineStage
    stage_index: NonNegativeInt
    input_hash: Digest
    output_hash: Digest
    producer_version: NonEmpty
    retry_policy_version: NonEmpty
    prompt_version: str | None
    policy_version: str | None
    model_id: str | None
    request_id: str | None
    created_at: NonEmpty
    payload: dict[str, Any]
    manifest_hash: Digest | None

    @field_validator("payload", mode="before")
    @classmethod
    def validate_payload(cls, value: object) -> dict[str, Any]:
        return StagePayload.model_validate(value).root


class StageAttempt(StrictFrozenModel):
    attempt_id: NonEmpty
    run_id: NonEmpty
    subject_id: NonEmpty
    stage: PipelineStage
    stage_index: NonNegativeInt
    attempt_no: Annotated[int, Field(ge=1)]
    status: AttemptStatus
    input_hash: Digest
    producer_version: NonEmpty
    retry_policy_version: NonEmpty
    reusable_key_digest: Digest
    started_at: NonEmpty
    finished_at: str | None
    prompt_version: str | None
    policy_version: str | None
    model_id: str | None
    request_id: str | None
    latency_ms: NonNegativeInt | None
    token_usage: TokenUsage | None
    error_code: str | None
    error_summary: str | None
    retryable: bool


class RunIdentity(StrictFrozenModel):
    """Complete immutable authority for creating or resuming one run."""

    schema_version: NonEmpty
    subject_id: NonEmpty
    fixture_hash: Digest
    producer_version: NonEmpty
    retry_policy_version: NonEmpty


class RunRecord(StrictFrozenModel):
    run_id: NonEmpty
    schema_version: NonEmpty
    subject_id: NonEmpty
    fixture_hash: Digest | None
    producer_version: NonEmpty
    retry_policy_version: NonEmpty
    identity_state: Literal["bound", "legacy_unbound"]
    execution_mode: ExecutionMode
    status: RunStatus
    created_at: NonEmpty
    updated_at: NonEmpty
    error_code: str | None
    error_summary: str | None
    reused_stage_count: NonNegativeInt

    @model_validator(mode="after")
    def validate_identity_state(self) -> RunRecord:
        if self.identity_state == "bound" and self.fixture_hash is None:
            raise ValueError("bound run identity is incomplete")
        if self.identity_state == "legacy_unbound" and self.fixture_hash is not None:
            raise ValueError("legacy unbound run carries fixture authority")
        return self

    @property
    def identity(self) -> RunIdentity:
        if self.identity_state != "bound" or self.fixture_hash is None:
            raise ValueError("run identity is not bound")
        return RunIdentity(
            schema_version=self.schema_version,
            subject_id=self.subject_id,
            fixture_hash=self.fixture_hash,
            producer_version=self.producer_version,
            retry_policy_version=self.retry_policy_version,
        )


class Checkpoint(StrictFrozenModel):
    run_id: NonEmpty
    subject_id: NonEmpty
    stage: PipelineStage
    stage_index: NonNegativeInt
    result_row_id: Digest
    result_id: Digest
    output_hash: Digest
    manifest_hash: Digest
    updated_at: NonEmpty


class PublicationPlan(StrictFrozenModel):
    run_id: NonEmpty
    status: str = "planned_not_published"
    last_stage: PipelineStage = PipelineStage.PUBLICATION_PLANNER
    remote_writes_attempted: NonNegativeInt = 0

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=False)


class RunSummary(StrictFrozenModel):
    run_id: NonEmpty
    status: RunStatus
    last_stage: PipelineStage
    reused_stage_count: NonNegativeInt
    publication_plan_path: str
    remote_writes_attempted: NonNegativeInt

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=False)
