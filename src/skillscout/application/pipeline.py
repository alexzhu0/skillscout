"""Ordered, resumable local-only pipeline over strict schema-v2 contracts."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from skillscout.adapters.fixtures import FixtureSubject
from skillscout.application.ports import (
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
from skillscout.domain.enums import AttemptStatus, ExecutionMode, PipelineStage, RunStatus
from skillscout.domain.models import (
    PublicationPlan,
    RunSummary,
    StageAttempt,
    StageEnvelope,
    StageInput,
)

STAGE_SEQUENCE = tuple(stage.value for stage in PipelineStage)
RETRY_POLICY_VERSION = "retry-v1"


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
    def now(self) -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class UUIDIdProvider:
    def new_run_id(self) -> str:
        return uuid.uuid4().hex


class PipelineRunner:
    """Persist running identity before work and atomic evidence after work."""

    def __init__(
        self,
        state: StateStore,
        processor: StageProcessor,
        *,
        clock: Clock | None = None,
        ids: IdProvider | None = None,
    ) -> None:
        self.state = state
        self.processor = processor
        self.clock = clock or SystemClock()
        self.ids = ids or UUIDIdProvider()

    def run(
        self,
        subject: FixtureSubject,
        output_directory: Path,
        fail_after: str | None = None,
    ) -> RunSummary:
        if fail_after is not None and fail_after not in STAGE_SEQUENCE:
            raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)

        resumable = self.state.find_resumable_run(subject.subject_id)
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
            self.state.verify_completed_results(run_id, start_index)
            self.state.set_run_status(run_id, RunStatus.RUNNING.value, self.clock.now())

        fixture_hash = sha256_digest(subject.model_dump(mode="json", exclude_none=False))
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
                producer_version=self.processor.producer_version,
                retry_policy_version=RETRY_POLICY_VERSION,
            )
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
                producer_version=self.processor.producer_version,
                retry_policy_version=RETRY_POLICY_VERSION,
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
                self.state.fail_attempt(attempt_id, run_id, failure, self.clock.now())
                raise
            except Exception:
                failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                self.state.fail_attempt(attempt_id, run_id, failure, self.clock.now())
                raise failure from None

            payload = dict(output)
            output_hash = stage_output_hash(
                schema_version=schema_version,
                subject_id=subject.subject_id,
                stage=stage,
                producer_version=self.processor.producer_version,
                prompt_version=None,
                policy_version=None,
                model_id=None,
                payload=payload,
            )
            result_id = make_result_id(
                subject_id=subject.subject_id,
                stage=stage,
                input_hash=input_hash,
                producer_version=self.processor.producer_version,
                output_hash=output_hash,
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
                producer_version=self.processor.producer_version,
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
            self.state.complete_stage(envelope)
            previous_output_hash = output_hash

            if fail_after == stage.value:
                failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                self.state.set_run_status(
                    run_id, RunStatus.INTERRUPTED.value, self.clock.now(), failure
                )
                raise failure

        plan_path = self._write_publication_plan(output_directory, PublicationPlan(run_id=run_id))
        self.state.set_run_status(run_id, RunStatus.PLANNED_NOT_PUBLISHED.value, self.clock.now())
        persisted = self.state.read_run(run_id)
        return RunSummary(
            run_id=str(persisted["run_id"]),
            status=RunStatus(str(persisted["status"])),
            last_stage=PipelineStage(str(persisted["last_stage"])),
            reused_stage_count=reused_count,
            publication_plan_path=str(plan_path),
            remote_writes_attempted=0,
        )

    @staticmethod
    def _write_publication_plan(output_directory: Path, plan: PublicationPlan) -> Path:
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
            target = output_directory / "publication-plan.json"
            temporary = output_directory / ".publication-plan.json.tmp"
            payload = canonical_json_bytes(plan) + b"\n"
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_CLOEXEC", 0),
                0o600,
            )
            try:
                view = memoryview(payload)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(temporary, target)
            return target
        except OSError:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
