"""Local-only contracts shared by the Phase 1 application and adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Protocol, runtime_checkable

from skillscout.domain.candidate_authority import CandidateSubjectDescriptorV1
from skillscout.domain.enums import EffectScope, PipelineStage
from skillscout.domain.models import (
    Checkpoint,
    ResumeEvent,
    RunIdentity,
    RunRecord,
    StageAttempt,
    StageEnvelope,
    StageInput,
    TokenUsage,
    VerifiedRunChain,
)

if TYPE_CHECKING:
    from skillscout.adapters.openai_generate import GenerationRequestV1, GenerationResult
    from skillscout.adapters.state import CompletedCandidateProjectionV1
    from skillscout.domain.candidate_authority import CandidateExecutionAuthorityV1
    from skillscout.domain.review import ReviewResult
    from skillscout.domain.skill_artifacts import FrozenSkillPackageV1
    from skillscout.domain.validation import ValidationReportV1


class ErrorCode(StrEnum):
    """The complete schema-v1 diagnostic vocabulary."""

    INVALID_CLI_ARGUMENTS = "invalid_cli_arguments"
    INVALID_FIXTURE = "invalid_fixture"
    FIXTURE_CHANGED = "fixture_changed"
    STATE_OPERATION_FAILED = "state_operation_failed"
    PIPELINE_INTERRUPTED = "pipeline_interrupted"
    STATE_SCHEMA_INCOMPATIBLE = "state_schema_incompatible"
    STATE_SCHEMA_MIGRATION_ERROR = "state_schema_migration_error"
    STATE_INTEGRITY_ERROR = "state_integrity_error"
    STATE_IDENTITY_UNBOUND = "state_identity_unbound"
    RETRY_EXHAUSTED = "retry_exhausted"
    STAGE_TRANSIENT_FAILURE = "stage_transient_failure"
    STAGE_PERMANENT_FAILURE = "stage_permanent_failure"
    STAGE_OUTPUT_INVALID = "stage_output_invalid"
    FORBIDDEN_EFFECT_SCOPE = "forbidden_effect_scope"
    INVALID_SUBJECT = "invalid_subject"
    CANDIDATE_SOURCE_UNAVAILABLE = "candidate_source_unavailable"


ERROR_SUMMARIES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_CLI_ARGUMENTS: "Command-line arguments were rejected.",
    ErrorCode.INVALID_FIXTURE: "Fixture input was rejected.",
    ErrorCode.FIXTURE_CHANGED: "Fixture input changed while it was being read.",
    ErrorCode.STATE_OPERATION_FAILED: "Local state operation failed.",
    ErrorCode.PIPELINE_INTERRUPTED: "Dry-run pipeline was interrupted.",
    ErrorCode.STATE_SCHEMA_INCOMPATIBLE: "Local state schema is incompatible.",
    ErrorCode.STATE_SCHEMA_MIGRATION_ERROR: "Local state schema migration failed.",
    ErrorCode.STATE_INTEGRITY_ERROR: "Local state integrity verification failed.",
    ErrorCode.STATE_IDENTITY_UNBOUND: "Run identity is not bound.",
    ErrorCode.RETRY_EXHAUSTED: "Stage retry budget was exhausted.",
    ErrorCode.STAGE_TRANSIENT_FAILURE: "Stage processing failed temporarily.",
    ErrorCode.STAGE_PERMANENT_FAILURE: "Stage processing failed permanently.",
    ErrorCode.STAGE_OUTPUT_INVALID: "Stage output violated its closed contract.",
    ErrorCode.FORBIDDEN_EFFECT_SCOPE: "Dry-run adapter authority was rejected.",
    ErrorCode.INVALID_SUBJECT: "Subject input was rejected.",
    ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE: "Candidate source is unavailable.",
}

if not all(summary.isascii() and len(summary) <= 160 for summary in ERROR_SUMMARIES.values()):
    raise RuntimeError("unsafe diagnostic summary configuration")


class SafeFailure(Exception):
    """A failure whose public representation is selected only from an allowlist."""

    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(ERROR_SUMMARIES[code])

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "summary": ERROR_SUMMARIES[self.code]}


class CandidateSourceUnavailable(SafeFailure):
    """One fixed no-echo boundary for every unavailable Phase 2 source."""

    def __init__(self) -> None:
        super().__init__(ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE)


@dataclass(frozen=True)
class PhaseTwoCandidateProjection:
    """Minimal verified Phase 2 facts permitted to cross into Phase 3."""

    phase2_run_id: str
    workflow_spec_bytes: bytes
    extractor_output_hash: str
    verified_chain_anchor: str
    repository_id: int
    repository_url: str
    pinned_commit_sha: str
    license_spdx: str


@runtime_checkable
class PhaseTwoCandidateSource(Protocol):
    """Read-only resolution of one strict completed-Phase-2 descriptor."""

    def resolve(
        self,
        descriptor: CandidateSubjectDescriptorV1,
    ) -> PhaseTwoCandidateProjection: ...

    def resolve_all(
        self,
        *,
        phase2_run_id: str,
        phase2_profile_version: str,
        phase2_producer_version: str,
    ) -> tuple[PhaseTwoCandidateProjection, ...]: ...


@runtime_checkable
class ScopedAdapter(Protocol):
    """An adapter registration with an explicit, closed effect scope."""

    @property
    def effect_scope(self) -> EffectScope: ...


@dataclass(frozen=True)
class AdapterRegistration:
    """Immutable declaration of one runtime adapter and its authority."""

    name: str
    adapter: object
    scope: EffectScope = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("invalid adapter registration")
        if not isinstance(self.adapter, ScopedAdapter):
            raise ValueError("invalid adapter registration")
        declared_scope = self.adapter.effect_scope
        if not isinstance(declared_scope, EffectScope):
            raise ValueError("invalid adapter registration")
        object.__setattr__(self, "scope", declared_scope)

    @property
    def effect_scope(self) -> EffectScope:
        return self.scope


class StageProcessor(Protocol):
    """Provider-independent deterministic stage processor."""

    producer_version: str

    def process(
        self,
        stage_input: StageInput,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class StageTelemetry:
    """Optional per-invocation telemetry copied onto attempts and envelopes."""

    prompt_version: str | None = None
    policy_version: str | None = None
    model_id: str | None = None
    request_id: str | None = None
    latency_ms: int | None = None
    token_usage: TokenUsage | None = None


@dataclass(frozen=True)
class StageOutcome:
    """One processor result: a bounded JSON payload plus optional telemetry."""

    payload: Mapping[str, Any]
    telemetry: StageTelemetry | None = None


@dataclass(frozen=True)
class StageContext:
    """Runtime-only per-invocation context; never persisted or canonicalized."""

    subject: object
    prior_payloads: dict[str, Mapping[str, Any]]
    scratch: dict[str, Any]


class ContextStageProcessor(Protocol):
    """Context-aware phase-two stage processor contract."""

    producer_version: str

    def process(
        self,
        stage_input: StageInput,
        context: StageContext,
    ) -> StageOutcome: ...


class Clock(Protocol):
    """Injectable UTC clock used only for audit timestamps."""

    def now(self) -> str: ...


class IdProvider(Protocol):
    """Injectable run identifier source."""

    def new_run_id(self) -> str: ...


class StateStore(Protocol):
    """Provider-independent persistence operations used by the runner."""

    def create_run(
        self, run_id: str, identity: RunIdentity, created_at: str
    ) -> ResumeEvent: ...

    def find_resumable_run(self, identity: RunIdentity) -> RunRecord | None: ...

    def find_completed_run(self, identity: RunIdentity) -> RunRecord | None: ...

    def bind_legacy_run(self, expected: RunIdentity) -> RunRecord | None: ...

    def verify_run_chain(
        self,
        run_id: str,
        expected_identity: RunIdentity | None = None,
    ) -> VerifiedRunChain: ...

    def latest_checkpoint(self, run_id: str) -> Checkpoint | None: ...

    def reconcile_orphan_running_attempts(self) -> None: ...

    def record_resume_decision(
        self,
        run_id: str,
        checkpoint: Checkpoint | None,
        recorded_at: str,
    ) -> ResumeEvent: ...

    def abandon_stale_running(
        self, run_id: str, stage: PipelineStage, finished_at: str
    ) -> None: ...

    def retry_attempt_count(self, reusable_digest: str) -> int: ...

    def has_permanent_failure(self, reusable_digest: str) -> bool: ...

    def next_attempt_no(
        self, run_id: str, stage: PipelineStage, reusable_digest: str
    ) -> int: ...

    def start_attempt(
        self,
        attempt: StageAttempt,
    ) -> None: ...

    def record_attempt_telemetry(
        self,
        attempt_id: str,
        telemetry: StageTelemetry,
    ) -> None: ...

    def complete_stage(
        self,
        envelope: StageEnvelope,
    ) -> None: ...

    def fail_attempt(
        self,
        attempt_id: str,
        run_id: str,
        failure: SafeFailure,
        finished_at: str,
        *,
        retryable: bool,
    ) -> None: ...

    def set_run_status(
        self,
        run_id: str,
        status: str,
        updated_at: str,
        failure: SafeFailure | None = None,
    ) -> None: ...

    def read_run(self, run_id: str) -> RunRecord: ...

    def close(self) -> None: ...


LocalStateStore = StateStore


@runtime_checkable
class CandidateGenerator(Protocol):
    """One bounded semantic generation request per runner-owned attempt."""

    def generate(self, *, request: GenerationRequestV1) -> GenerationResult: ...


@runtime_checkable
class CandidateValidator(Protocol):
    """Official plus local validation over one already-frozen package."""

    def validate(
        self,
        *,
        package: FrozenSkillPackageV1,
        authority: CandidateExecutionAuthorityV1,
    ) -> ValidationReportV1: ...


@runtime_checkable
class CandidateReviewer(Protocol):
    """One independent judgment request per runner-owned attempt."""

    def review(
        self,
        *,
        workflow_spec: object,
        package: FrozenSkillPackageV1,
        validation_report: ValidationReportV1,
    ) -> ReviewResult: ...


@runtime_checkable
class CompletedCandidateProjector(Protocol):
    """Read-only exact completed lookup with clean-miss semantics."""

    def find_completed_candidate(
        self,
        authority: CandidateExecutionAuthorityV1,
    ) -> CompletedCandidateProjectionV1 | None: ...


@runtime_checkable
class MutableCandidateState(Protocol):
    """Write-capable Phase 3 state, constructed only after a verified miss."""

    def find_resumable_candidate(
        self,
        authority: CandidateExecutionAuthorityV1,
    ) -> object | None: ...

    def find_pending_candidate_projection(
        self,
        authority: CandidateExecutionAuthorityV1,
    ) -> object | None: ...

    def persist_candidate_chain(self, chain: object, *, status: str) -> None: ...

    def persist_candidate_stage(
        self,
        chain: object,
        *,
        stage_payload: bytes,
        recovery_artifacts: Mapping[str, bytes],
        status: str,
    ) -> None: ...

    def read_candidate_checkpoint_payloads(
        self,
        run_id: str,
    ) -> Mapping[str, bytes]: ...

    def project_prior_lineage_binding(self, binding_digest: str) -> object | None: ...

    def project_verified_prior_lineage_evidence(
        self, binding_digest: str
    ) -> object | None: ...

    def project_lineage_slug_owners(self, stable_slug: str) -> tuple[str, ...]: ...

    def persist_candidate_terminal(
        self,
        run_id: str,
        *,
        terminal_summary: object,
        artifacts: Mapping[str, bytes],
        projection_required: bool = False,
    ) -> None: ...

    def complete_candidate_projection(
        self,
        run_id: str,
        *,
        authority: CandidateExecutionAuthorityV1,
    ) -> None: ...

    def close(self) -> None: ...


class MutableCandidateStateFactory(Protocol):
    """Separate factory for the mutation-capable state boundary."""

    def __call__(self) -> MutableCandidateState: ...


@runtime_checkable
class CandidateArtifactProjector(Protocol):
    """Local-only optional projection of newly produced immutable artifacts."""

    def project(
        self,
        *,
        output_directory: Path,
        terminal_summary: object,
        artifacts: Mapping[str, bytes],
    ) -> object: ...
