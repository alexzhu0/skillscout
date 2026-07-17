"""Local-only contracts shared by the Phase 1 application and adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping, Protocol


class ErrorCode(StrEnum):
    """The complete schema-v1 diagnostic vocabulary."""

    INVALID_FIXTURE = "invalid_fixture"
    FIXTURE_CHANGED = "fixture_changed"
    STATE_OPERATION_FAILED = "state_operation_failed"
    PIPELINE_INTERRUPTED = "pipeline_interrupted"


ERROR_SUMMARIES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_FIXTURE: "Fixture input was rejected.",
    ErrorCode.FIXTURE_CHANGED: "Fixture input changed while it was being read.",
    ErrorCode.STATE_OPERATION_FAILED: "Local state operation failed.",
    ErrorCode.PIPELINE_INTERRUPTED: "Dry-run pipeline was interrupted.",
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
        stage: str,
        subject_id: str,
        previous_output_hash: str | None,
    ) -> Mapping[str, Any]: ...


class LocalStateStore(Protocol):
    """Persistence operations required by the schema-v1 runner."""

    def create_run(self, run_id: str, subject_id: str, created_at: str) -> None: ...

    def start_attempt(
        self,
        *,
        attempt_id: str,
        run_id: str,
        subject_id: str,
        stage: str,
        stage_index: int,
        input_hash: str,
        producer_version: str,
        retry_policy_version: str,
        reusable_key_digest: str,
        started_at: str,
    ) -> None: ...

    def complete_stage(
        self,
        *,
        result_id: str,
        attempt_id: str,
        run_id: str,
        subject_id: str,
        stage: str,
        stage_index: int,
        output_json: str,
        output_hash: str,
        producer_version: str,
        finished_at: str,
    ) -> None: ...

    def fail_attempt(
        self, attempt_id: str, run_id: str, failure: SafeFailure, finished_at: str
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
