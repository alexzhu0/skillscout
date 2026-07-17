"""Local-only contracts shared by the Phase 1 application and adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping, Protocol

from skillscout.domain.models import StageAttempt, StageEnvelope, StageInput


class ErrorCode(StrEnum):
    """The complete schema-v1 diagnostic vocabulary."""

    INVALID_FIXTURE = "invalid_fixture"
    FIXTURE_CHANGED = "fixture_changed"
    STATE_OPERATION_FAILED = "state_operation_failed"
    PIPELINE_INTERRUPTED = "pipeline_interrupted"
    STATE_SCHEMA_INCOMPATIBLE = "state_schema_incompatible"
    STATE_SCHEMA_MIGRATION_ERROR = "state_schema_migration_error"
    STATE_INTEGRITY_ERROR = "state_integrity_error"
    RETRY_EXHAUSTED = "retry_exhausted"
    STAGE_TRANSIENT_FAILURE = "stage_transient_failure"
    STAGE_PERMANENT_FAILURE = "stage_permanent_failure"


ERROR_SUMMARIES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_FIXTURE: "Fixture input was rejected.",
    ErrorCode.FIXTURE_CHANGED: "Fixture input changed while it was being read.",
    ErrorCode.STATE_OPERATION_FAILED: "Local state operation failed.",
    ErrorCode.PIPELINE_INTERRUPTED: "Dry-run pipeline was interrupted.",
    ErrorCode.STATE_SCHEMA_INCOMPATIBLE: "Local state schema is incompatible.",
    ErrorCode.STATE_SCHEMA_MIGRATION_ERROR: "Local state schema migration failed.",
    ErrorCode.STATE_INTEGRITY_ERROR: "Local state integrity verification failed.",
    ErrorCode.RETRY_EXHAUSTED: "Stage retry budget was exhausted.",
    ErrorCode.STAGE_TRANSIENT_FAILURE: "Stage processing failed temporarily.",
    ErrorCode.STAGE_PERMANENT_FAILURE: "Stage processing failed permanently.",
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


class StageProcessor(Protocol):
    """Provider-independent deterministic stage processor."""

    producer_version: str

    def process(
        self,
        stage_input: StageInput,
    ) -> Mapping[str, Any]: ...


class Clock(Protocol):
    """Injectable UTC clock used only for audit timestamps."""

    def now(self) -> str: ...


class IdProvider(Protocol):
    """Injectable run identifier source."""

    def new_run_id(self) -> str: ...


class StateStore(Protocol):
    """Provider-independent persistence operations used by the runner."""

    def create_run(
        self, run_id: str, subject_id: str, created_at: str, schema_version: str
    ) -> None: ...

    def start_attempt(
        self,
        attempt: StageAttempt,
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

    def read_run(self, run_id: str) -> Mapping[str, Any]: ...

    def close(self) -> None: ...


LocalStateStore = StateStore
