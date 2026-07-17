"""Ordered local-only schema-v1 pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from skillscout.adapters.fixtures import FixtureSubject
from skillscout.application.ports import ErrorCode, LocalStateStore, SafeFailure, StageProcessor

STAGE_SEQUENCE = (
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
RETRY_POLICY_VERSION = "retry-v1"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_canonical_bytes(value)).hexdigest()}"


def canonical_v1_digest(
    *,
    subject_id: str,
    stage: str,
    input_hash: str,
    producer_version: str,
    retry_policy_version: str,
) -> str:
    """Hash exactly the five schema-v1 reusable identity fields."""

    return _digest(
        {
            "subject_id": subject_id,
            "stage": stage,
            "input_hash": input_hash,
            "producer_version": producer_version,
            "retry_policy_version": retry_policy_version,
        }
    )


@dataclass(frozen=True)
class StageResult:
    stage: str
    output_hash: str


@dataclass(frozen=True)
class PublicationPlan:
    run_id: str
    status: str = "planned_not_published"
    last_stage: str = "publication_planner"
    remote_writes_attempted: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "last_stage": self.last_stage,
            "remote_writes_attempted": self.remote_writes_attempted,
        }


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    status: str
    last_stage: str
    publication_plan_path: Path
    reused_stage_count: int = 0
    remote_writes_attempted: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "last_stage": self.last_stage,
            "reused_stage_count": self.reused_stage_count,
            "publication_plan_path": str(self.publication_plan_path),
            "remote_writes_attempted": self.remote_writes_attempted,
        }


class PipelineRunner:
    """Persist identity before work and results/checkpoints after work."""

    def __init__(self, state: LocalStateStore, processor: StageProcessor) -> None:
        self.state = state
        self.processor = processor

    def run(
        self,
        subject: FixtureSubject,
        output_directory: Path,
        fail_after: str | None = None,
    ) -> RunSummary:
        if fail_after is not None and fail_after not in STAGE_SEQUENCE:
            raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)

        run_id = uuid.uuid4().hex
        now = _now()
        self.state.create_run(run_id, subject.subject_id, now)
        previous_output_hash: str | None = None

        for stage_index, stage in enumerate(STAGE_SEQUENCE):
            input_value = {
                "schema_version": "1",
                "execution_mode": "dry_run",
                "subject_id": subject.subject_id,
                "stage": stage,
                "previous_output_hash": previous_output_hash,
                "fixture_hash": _digest(subject.model_dump(mode="json")) if stage_index == 0 else None,
            }
            input_hash = _digest(input_value)
            reusable_digest = canonical_v1_digest(
                subject_id=subject.subject_id,
                stage=stage,
                input_hash=input_hash,
                producer_version=self.processor.producer_version,
                retry_policy_version=RETRY_POLICY_VERSION,
            )
            attempt_id = f"{run_id}:{stage}:1"
            started_at = _now()
            self.state.start_attempt(
                attempt_id=attempt_id,
                run_id=run_id,
                subject_id=subject.subject_id,
                stage=stage,
                stage_index=stage_index,
                input_hash=input_hash,
                producer_version=self.processor.producer_version,
                retry_policy_version=RETRY_POLICY_VERSION,
                reusable_key_digest=reusable_digest,
                started_at=started_at,
            )

            try:
                output: Mapping[str, Any] = self.processor.process(
                    stage, subject.subject_id, previous_output_hash
                )
            except Exception:
                failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                self.state.fail_attempt(attempt_id, run_id, failure, _now())
                raise failure from None

            output_json = _canonical_bytes(output).decode("utf-8")
            output_hash = _digest(
                {
                    "schema_version": "1",
                    "stage": stage,
                    "subject_id": subject.subject_id,
                    "producer_version": self.processor.producer_version,
                    "payload": output,
                }
            )
            result_id = _digest(
                {
                    "stage": stage,
                    "subject_id": subject.subject_id,
                    "input_hash": input_hash,
                    "producer_version": self.processor.producer_version,
                    "output_hash": output_hash,
                }
            )
            finished_at = _now()
            self.state.complete_stage(
                result_id=result_id,
                attempt_id=attempt_id,
                run_id=run_id,
                subject_id=subject.subject_id,
                stage=stage,
                stage_index=stage_index,
                output_json=output_json,
                output_hash=output_hash,
                producer_version=self.processor.producer_version,
                finished_at=finished_at,
            )
            previous_output_hash = output_hash

            if fail_after == stage:
                failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                self.state.set_run_status(run_id, "interrupted", _now(), failure)
                raise failure

        plan_path = self._write_publication_plan(output_directory, PublicationPlan(run_id))
        self.state.set_run_status(run_id, "planned_not_published", _now())
        persisted = self.state.read_run(run_id)
        return RunSummary(
            run_id=str(persisted["run_id"]),
            status=str(persisted["status"]),
            last_stage=str(persisted["last_stage"]),
            publication_plan_path=plan_path,
        )

    @staticmethod
    def _write_publication_plan(output_directory: Path, plan: PublicationPlan) -> Path:
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
            target = output_directory / "publication-plan.json"
            temporary = output_directory / ".publication-plan.json.tmp"
            payload = _canonical_bytes(plan.as_dict()) + b"\n"
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


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
