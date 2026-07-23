"""Strict immutable contracts crossing SkillScout pipeline boundaries."""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from skillscout.domain.enums import AttemptStatus, ExecutionMode, PipelineStage, RunStatus

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PersistedIdentifier = Annotated[str, Field(min_length=1, max_length=512)]
PersistedSubject = Annotated[str, Field(min_length=1, max_length=128)]
PersistedVersion = Annotated[str, Field(min_length=1, max_length=128)]
PersistedDiagnosticCode = Annotated[str, Field(min_length=1, max_length=64)]
PersistedDiagnosticSummary = Annotated[str, Field(min_length=1, max_length=160)]
PersistedTelemetryText = Annotated[str, Field(min_length=1, max_length=512)]
PersistedTimestamp = Annotated[
    str,
    Field(pattern=(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")),
]
PersistedSQLiteInt = Annotated[int, Field(ge=0, le=9_223_372_036_854_775_807)]

MAX_MANIFEST_BYTES = 262_144
MAX_STAGE_PAYLOAD_DEPTH = 16
MAX_STAGE_PAYLOAD_NODES = 4_096
MAX_STAGE_COLLECTION_ITEMS = 1_024
MAX_STAGE_KEY_BYTES = 256
MAX_STAGE_STRING_BYTES = 65_536
MAX_STAGE_INTEGER_ABS = 9_007_199_254_740_991

SUPPORTED_PRODUCER_SCHEMAS: frozenset[tuple[str, str]] = frozenset(
    {("1", "fixture-v1"), ("2", "fixture-v1"), ("2", "phase2-v1")}
)

PHASE_THREE_SCHEMA_VERSION = "phase3-ledger-v1"
PHASE_THREE_PROFILE_VERSION = "phase3-profile-v1"
CANDIDATE_CHECKPOINT_SCHEMA_VERSION = "candidate-stage-checkpoint-v1"
CANDIDATE_CHECKPOINT_PROFILE_VERSION = "phase3-checkpoint-v1"


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


class PhaseThreeStageV1(str, Enum):
    """Closed stage order for the isolated candidate ledger."""

    QUALIFIER = "qualifier"
    GENERATOR = "generator"
    VALIDATOR = "validator"
    REVIEWER = "reviewer"


PHASE_THREE_STAGE_SEQUENCE = tuple(PhaseThreeStageV1)


def _canonical_self_hash(model: BaseModel, field: str) -> str:
    """Digest every canonical field except the digest being verified."""

    from skillscout.domain.canonical import sha256_digest

    return sha256_digest(
        model.model_dump(
            mode="json",
            exclude_none=False,
            exclude={field},
        )
    )


PHASE_THREE_GENESIS_CHECKPOINT_HASH = "sha256:" + ("0" * 64)


class CandidateRunIdentityV1(StrictFrozenModel):
    """Complete prelookup execution authority rooting one Phase 3 run."""

    schema_version: Literal["phase3-ledger-v1"]
    run_id: PersistedIdentifier
    candidate_execution_authority: Any
    candidate_execution_authority_digest: Digest
    identity_digest: Digest

    @model_validator(mode="after")
    def validate_candidate_identity(self) -> CandidateRunIdentityV1:
        from skillscout.domain.candidate_authority import CandidateExecutionAuthorityV1

        authority = self.candidate_execution_authority
        if (
            type(authority) is not CandidateExecutionAuthorityV1
            or self.candidate_execution_authority_digest != authority.authority_digest
            or self.identity_digest != _canonical_self_hash(self, "identity_digest")
        ):
            raise ValueError("candidate run identity authority disagrees")
        return self


class CandidateStageAttemptV1(StrictFrozenModel):
    """One Phase 3 stage attempt citing the exact verified predecessor."""

    schema_version: Literal["phase3-ledger-v1"]
    run_id: PersistedIdentifier
    candidate_execution_authority_digest: Digest
    stage: PhaseThreeStageV1
    stage_index: Annotated[int, Field(ge=0, lt=4)]
    attempt_no: Annotated[int, Field(ge=1, le=1_000_000)]
    previous_checkpoint_hash: Digest
    previous_output_hash: Digest | None
    producer_version: PersistedVersion
    profile_version: Literal["phase3-profile-v1"]
    retry_policy_version: PersistedVersion
    status: Literal["running", "succeeded", "failed", "abandoned"]
    outcome_code: Annotated[
        str,
        Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
    ]
    payload_digest: Digest
    attempt_hash: Digest

    @model_validator(mode="after")
    def validate_candidate_attempt(self) -> CandidateStageAttemptV1:
        if (
            self.stage_index != PHASE_THREE_STAGE_SEQUENCE.index(self.stage)
            or self.attempt_hash != _canonical_self_hash(self, "attempt_hash")
        ):
            raise ValueError("candidate attempt identity disagrees")
        return self


class CandidateStageResultV1(StrictFrozenModel):
    """Canonical successful output from one exact Phase 3 attempt."""

    schema_version: Literal["phase3-ledger-v1"]
    run_id: PersistedIdentifier
    candidate_execution_authority_digest: Digest
    stage: PhaseThreeStageV1
    stage_index: Annotated[int, Field(ge=0, lt=4)]
    attempt_no: Annotated[int, Field(ge=1, le=1_000_000)]
    attempt_hash: Digest
    previous_result_hash: Digest | None
    producer_version: PersistedVersion
    profile_version: Literal["phase3-profile-v1"]
    retry_policy_version: PersistedVersion
    outcome_code: Annotated[
        str,
        Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
    ]
    payload_digest: Digest
    output_hash: Digest
    result_hash: Digest

    @model_validator(mode="after")
    def validate_candidate_result(self) -> CandidateStageResultV1:
        from skillscout.domain.canonical import sha256_digest

        expected_output = sha256_digest(
            {
                "schema_version": self.schema_version,
                "run_id": self.run_id,
                "stage": self.stage.value,
                "attempt_hash": self.attempt_hash,
                "payload_digest": self.payload_digest,
                "outcome_code": self.outcome_code,
            }
        )
        if (
            self.stage_index != PHASE_THREE_STAGE_SEQUENCE.index(self.stage)
            or self.output_hash != expected_output
            or self.result_hash != _canonical_self_hash(self, "result_hash")
        ):
            raise ValueError("candidate result identity disagrees")
        return self


class CandidateStageCheckpointV1(StrictFrozenModel):
    """Successful result boundary binding the exact next legal stage."""

    schema_version: Literal["candidate-stage-checkpoint-v1"]
    profile_version: Literal["phase3-checkpoint-v1"]
    run_id: PersistedIdentifier
    candidate_execution_authority_digest: Digest
    stage: PhaseThreeStageV1
    stage_index: Annotated[int, Field(ge=0, lt=4)]
    attempt_no: Annotated[int, Field(ge=1, le=1_000_000)]
    result_hash: Digest
    output_hash: Digest
    previous_checkpoint_hash: Digest
    next_stage: PhaseThreeStageV1 | None
    terminal: bool
    checkpoint_hash: Digest

    @model_validator(mode="after")
    def validate_candidate_checkpoint(self) -> CandidateStageCheckpointV1:
        expected_index = PHASE_THREE_STAGE_SEQUENCE.index(self.stage)
        expected_next = (
            PHASE_THREE_STAGE_SEQUENCE[expected_index + 1]
            if expected_index + 1 < len(PHASE_THREE_STAGE_SEQUENCE)
            else None
        )
        if (
            self.stage_index != expected_index
            or self.next_stage is not expected_next
            or self.terminal is (expected_next is not None)
            or self.checkpoint_hash != _canonical_self_hash(self, "checkpoint_hash")
        ):
            raise ValueError("candidate checkpoint transition disagrees")
        return self


class CandidateResumeEventV1(StrictFrozenModel):
    """Immutable Phase 3 invocation/checkpoint projection."""

    schema_version: Literal["phase3-ledger-v1"]
    run_id: PersistedIdentifier
    candidate_execution_authority_digest: Digest
    event_index: PersistedSQLiteInt
    prior_event_hash: Digest | None
    checkpoint_hash: Digest | None
    checkpoint_output_hash: Digest | None
    next_stage: PhaseThreeStageV1 | None
    terminal: bool
    event_hash: Digest

    @model_validator(mode="after")
    def validate_candidate_resume_event(self) -> CandidateResumeEventV1:
        checkpoint_fields = (self.checkpoint_hash, self.checkpoint_output_hash)
        if self.event_index == 0:
            valid_shape = (
                self.prior_event_hash is None
                and all(value is None for value in checkpoint_fields)
                and self.next_stage is PhaseThreeStageV1.QUALIFIER
                and not self.terminal
            )
        else:
            valid_shape = (
                self.prior_event_hash is not None
                and all(value is not None for value in checkpoint_fields)
                and (self.next_stage is None) is self.terminal
            )
        if (
            not valid_shape
            or self.event_hash != _canonical_self_hash(self, "event_hash")
        ):
            raise ValueError("candidate resume event shape disagrees")
        return self


class VerifiedCandidateRunChain(StrictFrozenModel):
    """Fully verified, isolated Phase 3 authority and successful prefix."""

    identity: CandidateRunIdentityV1
    attempts: tuple[CandidateStageAttemptV1, ...]
    results: tuple[CandidateStageResultV1, ...]
    checkpoints: tuple[CandidateStageCheckpointV1, ...]
    resume_events: tuple[CandidateResumeEventV1, ...]

    @model_validator(mode="after")
    def validate_candidate_chain(self) -> VerifiedCandidateRunChain:
        count = len(self.results)
        if (
            count > len(PHASE_THREE_STAGE_SEQUENCE)
            or len(self.checkpoints) != count
            or len(self.resume_events) != count + 1
        ):
            raise ValueError("candidate chain cardinality disagrees")

        run_id = self.identity.run_id
        authority_digest = self.identity.candidate_execution_authority_digest
        genesis = self.resume_events[0]
        if (
            genesis.run_id != run_id
            or genesis.candidate_execution_authority_digest != authority_digest
            or genesis.event_index != 0
        ):
            raise ValueError("candidate genesis authority disagrees")

        previous_checkpoint_hash = PHASE_THREE_GENESIS_CHECKPOINT_HASH
        previous_output_hash: str | None = None
        previous_result_hash: str | None = None
        previous_event_hash = genesis.event_hash
        attempts_by_stage: dict[PhaseThreeStageV1, list[CandidateStageAttemptV1]] = {}
        prior_attempt_key: tuple[int, int] | None = None
        for attempt in self.attempts:
            attempt_key = (attempt.stage_index, attempt.attempt_no)
            if (
                attempt.run_id != run_id
                or attempt.candidate_execution_authority_digest != authority_digest
                or (prior_attempt_key is not None and attempt_key <= prior_attempt_key)
            ):
                raise ValueError("candidate attempt authority disagrees")
            prior_attempt_key = attempt_key
            attempts_by_stage.setdefault(attempt.stage, []).append(attempt)

        for index, (result, checkpoint, event) in enumerate(
            zip(self.results, self.checkpoints, self.resume_events[1:], strict=True)
        ):
            stage = PHASE_THREE_STAGE_SEQUENCE[index]
            stage_attempts = attempts_by_stage.get(stage, [])
            successful = [
                attempt for attempt in stage_attempts if attempt.status == "succeeded"
            ]
            if len(successful) != 1:
                raise ValueError("candidate successful attempt cardinality disagrees")
            attempt = successful[0]
            if (
                stage
                not in {PhaseThreeStageV1.GENERATOR, PhaseThreeStageV1.REVIEWER}
                and stage_attempts != [attempt]
            ):
                raise ValueError("candidate deterministic attempt history disagrees")
            common_records = (result, checkpoint, event)
            if any(
                record.run_id != run_id
                or record.candidate_execution_authority_digest != authority_digest
                for record in common_records
            ):
                raise ValueError("candidate record authority disagrees")
            if (
                attempt.stage is not stage
                or result.stage is not stage
                or checkpoint.stage is not stage
                or attempt.stage_index != index
                or result.stage_index != index
                or checkpoint.stage_index != index
                or attempt.status != "succeeded"
                or attempt.previous_checkpoint_hash != previous_checkpoint_hash
                or attempt.previous_output_hash != previous_output_hash
                or result.attempt_no != attempt.attempt_no
                or result.attempt_hash != attempt.attempt_hash
                or result.previous_result_hash != previous_result_hash
                or result.producer_version != attempt.producer_version
                or result.profile_version != attempt.profile_version
                or result.retry_policy_version != attempt.retry_policy_version
                or result.outcome_code != attempt.outcome_code
                or result.payload_digest != attempt.payload_digest
                or checkpoint.attempt_no != result.attempt_no
                or checkpoint.result_hash != result.result_hash
                or checkpoint.output_hash != result.output_hash
                or checkpoint.previous_checkpoint_hash != previous_checkpoint_hash
                or event.event_index != index + 1
                or event.prior_event_hash != previous_event_hash
                or event.checkpoint_hash != checkpoint.checkpoint_hash
                or event.checkpoint_output_hash != checkpoint.output_hash
                or event.next_stage is not checkpoint.next_stage
                or event.terminal is not checkpoint.terminal
            ):
                raise ValueError("candidate chain continuity disagrees")
            previous_checkpoint_hash = checkpoint.checkpoint_hash
            previous_output_hash = result.output_hash
            previous_result_hash = result.result_hash
            previous_event_hash = event.event_hash

        semantic_attempt_limits = {
            PhaseThreeStageV1.GENERATOR: (
                self.identity.candidate_execution_authority.max_generator_attempts
            ),
            PhaseThreeStageV1.REVIEWER: (
                self.identity.candidate_execution_authority.max_reviewer_attempts
            ),
        }
        for semantic_stage, attempt_limit in semantic_attempt_limits.items():
            semantic_attempts = attempts_by_stage.get(semantic_stage, [])
            if not semantic_attempts:
                continue
            stage_index = PHASE_THREE_STAGE_SEQUENCE.index(semantic_stage)
            if stage_index == 0 or len(self.checkpoints) < stage_index:
                raise ValueError("candidate semantic attempt precedes its stage")
            semantic_previous_checkpoint_hash = self.checkpoints[
                stage_index - 1
            ].checkpoint_hash
            semantic_previous_output_hash = self.results[
                stage_index - 1
            ].output_hash
            expected_numbers = tuple(range(1, len(semantic_attempts) + 1))
            if (
                len(semantic_attempts) > attempt_limit
                or tuple(attempt.attempt_no for attempt in semantic_attempts)
                != expected_numbers
                or any(
                    attempt.previous_checkpoint_hash
                    != semantic_previous_checkpoint_hash
                    or attempt.previous_output_hash != semantic_previous_output_hash
                    for attempt in semantic_attempts
                )
            ):
                raise ValueError("candidate semantic attempt continuity disagrees")
            result_exists = count > stage_index
            terminal_attempt = semantic_attempts[-1]
            if result_exists:
                if (
                    terminal_attempt.status != "succeeded"
                    or any(
                        (attempt.status, attempt.outcome_code)
                        not in {
                            ("failed", "stage_transient_failure"),
                            ("abandoned", "attempt_interrupted"),
                        }
                        for attempt in semantic_attempts[:-1]
                    )
                ):
                    raise ValueError("candidate semantic result history disagrees")
            elif count == stage_index:
                if (
                    any(
                        (attempt.status, attempt.outcome_code)
                        not in {
                            ("failed", "stage_transient_failure"),
                            ("abandoned", "attempt_interrupted"),
                        }
                        for attempt in semantic_attempts[:-1]
                    )
                    or terminal_attempt.status
                    not in {"failed", "abandoned", "running"}
                    or (
                        terminal_attempt.status == "running"
                        and terminal_attempt.outcome_code
                        != f"{semantic_stage.value}_call_started"
                    )
                    or (
                        terminal_attempt.status == "abandoned"
                        and terminal_attempt.outcome_code != "attempt_interrupted"
                    )
                ):
                    raise ValueError("candidate pending semantic history disagrees")
            else:
                raise ValueError("candidate semantic attempt precedes its stage")
        for stage in attempts_by_stage:
            stage_index = PHASE_THREE_STAGE_SEQUENCE.index(stage)
            if stage_index > count or (
                stage_index == count
                and stage
                not in {PhaseThreeStageV1.GENERATOR, PhaseThreeStageV1.REVIEWER}
            ):
                raise ValueError("candidate attempt stage is not reachable")
        return self


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


class PersistedRunRecord(RunRecord):
    """Exact sanitized projection of one persisted run row."""

    run_id: PersistedIdentifier
    schema_version: Literal["1", "2"]
    subject_id: PersistedSubject
    producer_version: PersistedVersion
    retry_policy_version: PersistedVersion
    created_at: PersistedTimestamp
    updated_at: PersistedTimestamp
    error_code: PersistedDiagnosticCode | None
    error_summary: PersistedDiagnosticSummary | None
    reused_stage_count: Annotated[int, Field(ge=0, le=len(tuple(PipelineStage)))]

    @model_validator(mode="after")
    def validate_persisted_run(self) -> PersistedRunRecord:
        has_code = self.error_code is not None
        has_summary = self.error_summary is not None
        if has_code != has_summary:
            raise ValueError("persisted run diagnostic is incomplete")
        needs_error = self.status in {RunStatus.INTERRUPTED, RunStatus.FAILED}
        if needs_error != has_code:
            raise ValueError("persisted run status and diagnostic disagree")
        if self.updated_at < self.created_at:
            raise ValueError("persisted run timestamps are not monotonic")
        return self


class PersistedAttemptRecord(StrictFrozenModel):
    """Flattened sanitized projection of one persisted attempt row."""

    attempt_id: PersistedIdentifier
    run_id: PersistedIdentifier
    subject_id: PersistedSubject
    stage: PipelineStage
    stage_index: Annotated[int, Field(ge=0, lt=len(tuple(PipelineStage)))]
    attempt_no: Annotated[int, Field(ge=1, le=1_000_000)]
    status: AttemptStatus
    input_hash: Digest
    producer_version: PersistedVersion
    retry_policy_version: PersistedVersion
    reusable_key_digest: Digest
    started_at: PersistedTimestamp
    finished_at: PersistedTimestamp | None
    prompt_version: PersistedTelemetryText | None
    policy_version: PersistedTelemetryText | None
    model_id: PersistedTelemetryText | None
    request_id: PersistedTelemetryText | None
    latency_ms: PersistedSQLiteInt | None
    prompt_tokens: PersistedSQLiteInt | None
    completion_tokens: PersistedSQLiteInt | None
    total_tokens: PersistedSQLiteInt | None
    error_code: PersistedDiagnosticCode | None
    error_summary: PersistedDiagnosticSummary | None
    retryable: bool

    @model_validator(mode="after")
    def validate_persisted_attempt(self) -> PersistedAttemptRecord:
        if self.stage_index != tuple(PipelineStage).index(self.stage):
            raise ValueError("persisted attempt stage index disagrees")
        if self.attempt_id != f"{self.run_id}:{self.stage.value}:{self.attempt_no}":
            raise ValueError("persisted attempt identity disagrees")

        has_code = self.error_code is not None
        has_summary = self.error_summary is not None
        if has_code != has_summary:
            raise ValueError("persisted attempt diagnostic is incomplete")
        if self.status is AttemptStatus.RUNNING:
            valid_lifecycle = self.finished_at is None and not has_code and not self.retryable
        elif self.status is AttemptStatus.SUCCEEDED:
            valid_lifecycle = self.finished_at is not None and not has_code and not self.retryable
        elif self.status is AttemptStatus.FAILED:
            valid_lifecycle = self.finished_at is not None and has_code
        else:
            valid_lifecycle = self.finished_at is not None and has_code and self.retryable
        if not valid_lifecycle:
            raise ValueError("persisted attempt lifecycle is incoherent")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("persisted attempt timestamps are not monotonic")

        token_values = (
            self.prompt_tokens,
            self.completion_tokens,
            self.total_tokens,
        )
        if any(value is None for value in token_values):
            if any(value is not None for value in token_values):
                raise ValueError("persisted attempt token usage is incomplete")
        elif self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("persisted attempt token usage is inconsistent")
        return self


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


class ResumeEvent(StrictFrozenModel):
    """Immutable invocation decision bound to one exact verified prefix."""

    event_hash: Digest
    run_id: PersistedIdentifier
    event_index: PersistedSQLiteInt
    prior_event_hash: Digest | None
    reused_stage_count: Annotated[int, Field(ge=0, le=len(tuple(PipelineStage)))]
    checkpoint_stage: PipelineStage | None
    checkpoint_result_row_id: Digest | None
    checkpoint_manifest_hash: Digest | None
    recorded_at: PersistedTimestamp

    @model_validator(mode="after")
    def validate_resume_event(self) -> ResumeEvent:
        checkpoint_tuple = (
            self.checkpoint_stage,
            self.checkpoint_result_row_id,
            self.checkpoint_manifest_hash,
        )
        all_null = all(value is None for value in checkpoint_tuple)
        all_present = all(value is not None for value in checkpoint_tuple)

        if self.event_index == 0:
            valid_shape = (
                self.prior_event_hash is None
                and self.reused_stage_count == 0
                and all_null
            )
        elif self.prior_event_hash is None:
            valid_shape = False
        elif self.reused_stage_count == 0:
            valid_shape = all_null
        else:
            valid_shape = all_present and self.reused_stage_count == (
                self.checkpoint_stage_index + 1
            )
        if not valid_shape:
            raise ValueError("resume event shape is inconsistent")

        from skillscout.domain.canonical import resume_event_hash

        expected_hash = resume_event_hash(
            **self.model_dump(mode="json", exclude={"event_hash"})
        )
        if self.event_hash != expected_hash:
            raise ValueError("resume event hash is inconsistent")
        return self

    @property
    def checkpoint_stage_index(self) -> int:
        if self.checkpoint_stage is None:
            raise ValueError("resume event has no checkpoint stage")
        return tuple(PipelineStage).index(self.checkpoint_stage)


class PersistedCheckpointRecord(Checkpoint):
    """Exact sanitized projection of one persisted checkpoint row."""

    run_id: PersistedIdentifier
    subject_id: PersistedSubject
    stage_index: Annotated[int, Field(ge=0, lt=len(tuple(PipelineStage)))]
    manifest_path: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            pattern=r"^[a-z_]+/[0-9a-f]{64}\.json$",
        ),
    ]
    updated_at: PersistedTimestamp

    @model_validator(mode="after")
    def validate_persisted_checkpoint(self) -> PersistedCheckpointRecord:
        if self.stage_index != tuple(PipelineStage).index(self.stage):
            raise ValueError("persisted checkpoint stage index disagrees")
        return self


class VerifiedRunChain(StrictFrozenModel):
    """Fully verified persisted authority for one bound run."""

    run: PersistedRunRecord
    identity: RunIdentity
    attempts: tuple[PersistedAttemptRecord, ...]
    results: tuple[StageEnvelope, ...]
    checkpoints: tuple[PersistedCheckpointRecord, ...]
    resume_events: tuple[ResumeEvent, ...]

    @model_validator(mode="after")
    def validate_verified_chain_shape(self) -> VerifiedRunChain:
        if self.run.identity_state != "bound" or self.run.identity != self.identity:
            raise ValueError("verified run identity disagrees")
        if len(self.results) != len(self.checkpoints):
            raise ValueError("verified result/checkpoint cardinality disagrees")
        if not self.resume_events:
            raise ValueError("verified resume-event chain is empty")
        prior_hash: str | None = None
        for expected_index, event in enumerate(self.resume_events):
            if (
                event.run_id != self.run.run_id
                or event.event_index != expected_index
                or event.prior_event_hash != prior_hash
            ):
                raise ValueError("verified resume-event linkage disagrees")
            prior_hash = event.event_hash
        if self.run.reused_stage_count != self.resume_events[-1].reused_stage_count:
            raise ValueError("verified reused-stage count disagrees")
        return self

    @property
    def latest_checkpoint(self) -> PersistedCheckpointRecord | None:
        return self.checkpoints[-1] if self.checkpoints else None

    @property
    def reused_stage_count(self) -> int:
        """Return reuse authority derived only from the verified event head."""

        return self.resume_events[-1].reused_stage_count


class PublicationPlan(StrictFrozenModel):
    run_id: NonEmpty
    status: str = "planned_not_published"
    last_stage: PipelineStage = PipelineStage.PUBLICATION_PLANNER
    remote_writes_attempted: NonNegativeInt = 0

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=False)


class StageOutcomeEntry(StrictFrozenModel):
    """One stage's closed outcome inside the extraction summary."""

    stage: PipelineStage
    outcome: str


class ExtractionSummary(StrictFrozenModel):
    """Bounded terminal artifact for one completed phase-two extraction run."""

    run_id: NonEmpty
    subject_id: NonEmpty
    repository: NonEmpty
    pinned_commit_sha: str | None
    stage_outcomes: tuple[StageOutcomeEntry, ...]
    extractor_outcome: str
    workflow_count: NonNegativeInt
    workflow_fingerprints: Annotated[tuple[str, ...], Field(max_length=3)]
    remote_writes_attempted: NonNegativeInt = 0

    @model_validator(mode="after")
    def validate_workflow_count(self) -> ExtractionSummary:
        if self.workflow_count != len(self.workflow_fingerprints):
            raise ValueError("workflow count disagrees with fingerprints")
        return self

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
