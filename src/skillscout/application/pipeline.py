"""Ordered, resumable local-only pipeline over strict schema-v2 contracts."""

from __future__ import annotations

import os
import stat
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Iterable, Mapping, Protocol

from skillscout.adapters.fixtures import FixtureProcessor, FixtureSubject
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.ports import (
    AdapterRegistration,
    Clock,
    ErrorCode,
    IdProvider,
    SafeFailure,
    StageProcessor,
    StateStore,
)
from skillscout.domain.canonical import (
    canonical_json_bytes,
    make_result_id,
    reusable_key_digest,
    sha256_digest,
    stage_input_hash,
    stage_manifest_hash,
    stage_output_hash,
)
from skillscout.domain.enums import (
    AttemptStatus,
    EffectScope,
    ExecutionMode,
    PipelineStage,
    RunStatus,
)
from skillscout.domain.models import (
    PublicationPlan,
    RunSummary,
    SUPPORTED_PRODUCER_SCHEMAS,
    StageAttempt,
    StageEnvelope,
    StageInput,
    StagePayload,
)

STAGE_SEQUENCE = tuple(stage.value for stage in PipelineStage)
RETRY_POLICY_VERSION = "retry-v1"
PHASE_ONE_MAX_SCOPES: Final[frozenset[EffectScope]] = frozenset(
    {EffectScope.NONE, EffectScope.LOCAL_STATE}
)


@dataclass(frozen=True)
class RetryPolicy:
    """Finite retry authority scoped only to a canonical reusable digest."""

    version: str = RETRY_POLICY_VERSION
    max_attempts: int = 3
    transient_error_codes: frozenset[ErrorCode] = frozenset(
        {ErrorCode.STAGE_TRANSIENT_FAILURE}
    )

    def __post_init__(self) -> None:
        if not self.version or self.max_attempts < 1:
            raise ValueError("invalid retry policy")


def canonical_v1_digest(
    *,
    subject_id: str,
    stage: str,
    input_hash: str,
    producer_version: str,
    retry_policy_version: str,
) -> str:
    """Compatibility seam for frozen schema-v1 provenance tests."""

    return reusable_key_digest(
        subject_id=subject_id,
        stage=PipelineStage(stage),
        input_hash=input_hash,
        producer_version=producer_version,
        retry_policy_version=retry_policy_version,
    )


class SystemClock:
    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.NONE

    def now(self) -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class UUIDIdProvider:
    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.NONE

    def new_run_id(self) -> str:
        return uuid.uuid4().hex


@dataclass(frozen=True)
class SideEffectPolicy:
    """Fail-closed authority policy applied before runtime construction."""

    allowed_scopes: frozenset[EffectScope]

    @classmethod
    def phase_one(cls) -> SideEffectPolicy:
        return cls(PHASE_ONE_MAX_SCOPES)

    def validate(
        self, registrations: Iterable[AdapterRegistration]
    ) -> tuple[AdapterRegistration, ...]:
        registry = tuple(registrations)
        if any(registration.scope not in self.allowed_scopes for registration in registry):
            raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE)
        return registry


@dataclass(frozen=True)
class DryRunRuntime:
    """Validated local-only runtime returned by the sole composition root."""

    runner: PipelineRunner
    registrations: tuple[AdapterRegistration, ...]
    policy: SideEffectPolicy


class _PublicationWriter(Protocol):
    def write(self, output_directory: Path, plan: PublicationPlan) -> Path: ...


class _LocalPublicationPlanner:
    """The only publication capability present in the Phase 1 runtime."""

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.LOCAL_STATE

    def write(self, output_directory: Path, plan: PublicationPlan) -> Path:
        return PipelineRunner._write_publication_plan(output_directory, plan)


class PipelineRunner:
    """Persist running identity before work and atomic evidence after work."""

    def __init__(
        self,
        state: StateStore,
        processor: StageProcessor,
        *,
        clock: Clock | None = None,
        ids: IdProvider | None = None,
        retry_policy: RetryPolicy | None = None,
        publication_writer: _PublicationWriter | None = None,
    ) -> None:
        self.state = state
        self.processor = processor
        self.clock = clock or SystemClock()
        self.ids = ids or UUIDIdProvider()
        self.retry_policy = retry_policy or RetryPolicy()
        self.publication_writer = publication_writer or _LocalPublicationPlanner()

    def run(
        self,
        subject: FixtureSubject,
        output_directory: Path,
        fail_after: str | None = None,
    ) -> RunSummary:
        if fail_after is not None and fail_after not in STAGE_SEQUENCE:
            raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)

        try:
            producer_version = self.processor.producer_version
            producer_supported = (
                type(producer_version) is str
                and ("2", producer_version) in SUPPORTED_PRODUCER_SCHEMAS
            )
        except Exception:
            producer_supported = False
        if not producer_supported:
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)

        fixture_hash = sha256_digest(subject.model_dump(mode="json", exclude_none=False))
        resumable = self.state.find_resumable_run(subject.subject_id)
        if resumable is not None and not self.state.resume_identity_matches(
            str(resumable["run_id"]),
            schema_version=str(resumable["schema_version"]),
            subject_id=subject.subject_id,
            fixture_hash=fixture_hash,
            producer_version=producer_version,
            retry_policy_version=self.retry_policy.version,
        ):
            resumable = None
        if resumable is None:
            run_id = self.ids.new_run_id()
            schema_version = "2"
            self.state.create_run(run_id, subject.subject_id, self.clock.now(), schema_version)
            start_index = 0
            previous_output_hash: str | None = None
            reused_count = 0
        else:
            run_id = str(resumable["run_id"])
            schema_version = str(resumable["schema_version"])
            checkpoint = self.state.latest_checkpoint(run_id)
            start_index = int(checkpoint["stage_index"]) + 1 if checkpoint else 0
            previous_output_hash = str(checkpoint["output_hash"]) if checkpoint else None
            reused_count = start_index
            resumable_status = RunStatus(str(resumable["status"]))
            if resumable_status is RunStatus.INTERRUPTED:
                self.state.set_run_status(run_id, RunStatus.RUNNING.value, self.clock.now())
            elif resumable_status is not RunStatus.RUNNING:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        self.state.set_reused_stage_count(run_id, reused_count)

        for stage_index, stage in enumerate(PipelineStage):
            if stage_index < start_index:
                continue
            stage_input = StageInput(
                schema_version=schema_version,
                execution_mode=ExecutionMode.DRY_RUN,
                subject_id=subject.subject_id,
                stage=stage,
                previous_output_hash=previous_output_hash,
                fixture_hash=fixture_hash if stage_index == 0 else None,
            )
            input_hash = stage_input_hash(stage_input)
            reusable_digest = reusable_key_digest(
                subject_id=subject.subject_id,
                stage=stage,
                input_hash=input_hash,
                producer_version=producer_version,
                retry_policy_version=self.retry_policy.version,
            )
            self.state.abandon_stale_running(run_id, stage, self.clock.now())
            if self.state.has_permanent_failure(reusable_digest):
                failure = SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
                self.state.set_run_status(
                    run_id, RunStatus.INTERRUPTED.value, self.clock.now(), failure
                )
                raise failure
            if self.state.retry_attempt_count(reusable_digest) >= self.retry_policy.max_attempts:
                failure = SafeFailure(ErrorCode.RETRY_EXHAUSTED)
                self.state.set_run_status(
                    run_id, RunStatus.INTERRUPTED.value, self.clock.now(), failure
                )
                raise failure
            attempt_no = self.state.next_attempt_no(run_id, stage, reusable_digest)
            attempt_id = f"{run_id}:{stage.value}:{attempt_no}"
            attempt = StageAttempt(
                attempt_id=attempt_id,
                run_id=run_id,
                subject_id=subject.subject_id,
                stage=stage,
                stage_index=stage_index,
                attempt_no=attempt_no,
                status=AttemptStatus.RUNNING,
                input_hash=input_hash,
                producer_version=producer_version,
                retry_policy_version=self.retry_policy.version,
                reusable_key_digest=reusable_digest,
                started_at=self.clock.now(),
                finished_at=None,
                prompt_version=None,
                policy_version=None,
                model_id=None,
                request_id=None,
                latency_ms=None,
                token_usage=None,
                error_code=None,
                error_summary=None,
                retryable=False,
            )
            self.state.start_attempt(attempt)

            try:
                output: Mapping[str, object] = self.processor.process(stage_input)
            except SafeFailure as failure:
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise
            except Exception:
                failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise failure from None

            try:
                payload = StagePayload.model_validate(output).root
                output_hash = stage_output_hash(
                    schema_version=schema_version,
                    subject_id=subject.subject_id,
                    stage=stage,
                    producer_version=producer_version,
                    prompt_version=None,
                    policy_version=None,
                    model_id=None,
                    payload=payload,
                )
                result_id = make_result_id(
                    subject_id=subject.subject_id,
                    stage=stage,
                    input_hash=input_hash,
                    producer_version=producer_version,
                    output_hash=output_hash,
                    retry_policy_version=self.retry_policy.version,
                )
                provisional = StageEnvelope(
                    schema_version=schema_version,
                    result_id=result_id,
                    run_id=run_id,
                    attempt_id=attempt_id,
                    attempt_no=attempt_no,
                    subject_id=subject.subject_id,
                    stage=stage,
                    stage_index=stage_index,
                    input_hash=input_hash,
                    output_hash=output_hash,
                    producer_version=producer_version,
                    retry_policy_version=self.retry_policy.version,
                    prompt_version=None,
                    policy_version=None,
                    model_id=None,
                    request_id=None,
                    created_at=self.clock.now(),
                    payload=payload,
                    manifest_hash=None,
                )
                envelope = provisional.model_copy(
                    update={"manifest_hash": stage_manifest_hash(provisional)}
                )
            except Exception:
                failure = SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise failure from None

            try:
                self.state.complete_stage(envelope)
            except SafeFailure as failure:
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise
            except Exception:
                failure = SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise failure from None
            previous_output_hash = output_hash

            if fail_after == stage.value:
                failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                self.state.set_run_status(
                    run_id, RunStatus.INTERRUPTED.value, self.clock.now(), failure
                )
                raise failure

        self.publication_writer.write(output_directory, PublicationPlan(run_id=run_id))
        self.state.set_run_status(run_id, RunStatus.PLANNED_NOT_PUBLISHED.value, self.clock.now())
        persisted = self.state.read_run(run_id)
        return RunSummary(
            run_id=str(persisted["run_id"]),
            status=RunStatus(str(persisted["status"])),
            last_stage=PipelineStage(str(persisted["last_stage"])),
            reused_stage_count=reused_count,
            publication_plan_path="publication-plan.json",
            remote_writes_attempted=0,
        )

    def _close_started_attempt(
        self,
        *,
        attempt_id: str,
        run_id: str,
        failure: SafeFailure,
    ) -> None:
        """Close a known running lifecycle or expose only a closed state failure."""

        try:
            self.state.fail_attempt(
                attempt_id,
                run_id,
                failure,
                self.clock.now(),
                retryable=failure.code in self.retry_policy.transient_error_codes,
            )
        except SafeFailure:
            raise
        except Exception:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    @staticmethod
    def _write_publication_plan(output_directory: Path, plan: PublicationPlan) -> Path:
        temporary: Path | None = None
        descriptor = -1
        try:
            if PipelineRunner._path_contains_symlink(output_directory):
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            output_directory.mkdir(parents=True, exist_ok=True)
            directory_metadata = os.lstat(output_directory)
            if stat.S_ISLNK(directory_metadata.st_mode) or not stat.S_ISDIR(
                directory_metadata.st_mode
            ):
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            target = output_directory / "publication-plan.json"
            temporary = output_directory / ".publication-plan.json.tmp"
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            if temporary.exists() or temporary.is_symlink():
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            payload = canonical_json_bytes(plan) + b"\n"
            descriptor = os.open(
                temporary,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
                0o600,
            )
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary, target)
            return target
        except SafeFailure:
            raise
        except OSError:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        finally:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _path_contains_symlink(path: Path) -> bool:
        absolute = path.absolute()
        for candidate in reversed((absolute, *absolute.parents)):
            try:
                if stat.S_ISLNK(os.lstat(candidate).st_mode):
                    return True
            except FileNotFoundError:
                continue
            except OSError:
                return True
        return False


def build_dry_run_runtime(
    state: SQLiteStateStore,
    processor: FixtureProcessor,
    *,
    retry_policy: RetryPolicy | None = None,
) -> DryRunRuntime:
    """Construct the closed Phase 1 runtime under its immutable authority ceiling."""

    resolved_clock = SystemClock()
    resolved_ids = UUIDIdProvider()
    publication_writer = _LocalPublicationPlanner()
    try:
        complete_registry = (
            AdapterRegistration("fixture_processor", processor),
            AdapterRegistration("sqlite_and_manifests", state),
            AdapterRegistration("clock", resolved_clock),
            AdapterRegistration("run_ids", resolved_ids),
            AdapterRegistration("local_publication_planner", publication_writer),
        )
    except ValueError:
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE) from None

    resolved_policy = SideEffectPolicy.phase_one()
    validated = resolved_policy.validate(complete_registry)
    expected_types = (
        FixtureProcessor,
        SQLiteStateStore,
        SystemClock,
        UUIDIdProvider,
        _LocalPublicationPlanner,
    )
    if any(
        type(registration.adapter) is not expected
        for registration, expected in zip(validated, expected_types, strict=True)
    ):
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE)

    runner = PipelineRunner(
        state,
        processor,
        clock=resolved_clock,
        ids=resolved_ids,
        retry_policy=retry_policy,
        publication_writer=publication_writer,
    )
    return DryRunRuntime(runner=runner, registrations=validated, policy=resolved_policy)
