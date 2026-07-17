"""Strict immutable contracts crossing SkillScout pipeline boundaries."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from skillscout.domain.enums import AttemptStatus, ExecutionMode, PipelineStage, RunStatus

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]


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
    prompt_version: str | None
    policy_version: str | None
    model_id: str | None
    request_id: str | None
    created_at: NonEmpty
    payload: dict[str, Any]
    manifest_hash: Digest | None


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


class RunRecord(StrictFrozenModel):
    run_id: NonEmpty
    schema_version: NonEmpty
    subject_id: NonEmpty
    execution_mode: ExecutionMode
    status: RunStatus
    created_at: NonEmpty
    updated_at: NonEmpty
    error_code: str | None
    error_summary: str | None


class Checkpoint(StrictFrozenModel):
    run_id: NonEmpty
    subject_id: NonEmpty
    stage: PipelineStage
    stage_index: NonNegativeInt
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
