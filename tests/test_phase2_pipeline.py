"""Profile slice, runtime-only context, telemetry and COMPLETED terminal evidence."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

from skillscout.adapters.fixtures import FixtureProcessor, FixtureSubject, load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.adapters.subjects import load_subject
from skillscout.application import pipeline
from skillscout.application.pipeline import (
    PHASE_TWO_STAGE_SEQUENCE,
    PipelineRunner,
)
from skillscout.application.ports import (
    ErrorCode,
    SafeFailure,
    StageContext,
    StageOutcome,
    StageTelemetry,
    StateStore,
)
from skillscout.domain.enums import PipelineStage, RunStatus
from skillscout.domain.models import ExtractionSummary, StageInput, TokenUsage
from skillscout.domain.subjects import RepositorySubject

APPROVED_FIXTURE = Path(__file__).parent / "fixtures" / "pipeline" / "approved.json"
APPROVED_SUBJECT = Path(__file__).parent / "fixtures" / "subject" / "approved.json"
PINNED_SHA = "0123456789abcdef0123456789abcdef01234567"
FINGERPRINTS = ("sha256:" + "a" * 64, "sha256:" + "b" * 64)


def _telemetry(prompt_version: str = "extract-prompt-v1") -> StageTelemetry:
    return StageTelemetry(
        prompt_version=prompt_version,
        policy_version=None,
        model_id="test-model",
        request_id="req-double",
        latency_ms=7,
        token_usage=TokenUsage(prompt_tokens=3, completion_tokens=5, total_tokens=8),
    )


class DoublePhaseTwoProcessor:
    """Canned phase-two processor recording every dispatched invocation."""

    producer_version = "phase2-v1"

    def __init__(self, prompt_version: str = "extract-prompt-v1") -> None:
        self.calls: list[tuple[PipelineStage, StageContext]] = []
        self._prompt_version = prompt_version

    def process(self, stage_input: StageInput, context: StageContext) -> StageOutcome:
        self.calls.append((stage_input.stage, context))
        payload: dict[str, object] = {
            "schema_version": stage_input.schema_version,
            "stage": stage_input.stage.value,
            "subject_id": stage_input.subject_id,
            "outcome": (
                "extracted" if stage_input.stage is PipelineStage.EXTRACTOR else "accepted"
            ),
        }
        if stage_input.stage is PipelineStage.SCOUT:
            payload["pinned_commit_sha"] = PINNED_SHA
        if stage_input.stage is PipelineStage.EXTRACTOR:
            payload["workflows"] = [{"fingerprint": value} for value in FINGERPRINTS]
        return StageOutcome(
            payload=payload,
            telemetry=_telemetry(self._prompt_version),
        )


def _run_phase_two(
    tmp_path: Path,
    processor: DoublePhaseTwoProcessor,
    *,
    store: SQLiteStateStore | None = None,
    fail_after: str | None = None,
    output: str = "output",
) -> tuple[object, SQLiteStateStore, bool]:
    resolved = store or SQLiteStateStore(tmp_path / "state.db")
    summary = PipelineRunner(resolved, processor).run(
        load_subject(APPROVED_SUBJECT), tmp_path / output, fail_after=fail_after
    )
    return summary, resolved, store is not None


def test_profiles_are_closed_prefix_slices_with_declared_terminals() -> None:
    spine = tuple(PipelineStage)
    assert set(pipeline.PIPELINE_PROFILES) == {"fixture-v1", "phase2-v1"}
    for profile in pipeline.PIPELINE_PROFILES.values():
        assert profile.stages == spine[: len(profile.stages)]
    fixture = pipeline.PIPELINE_PROFILES["fixture-v1"]
    assert fixture.uses_context is False
    assert fixture.terminal_status is RunStatus.PLANNED_NOT_PUBLISHED
    phase_two = pipeline.PIPELINE_PROFILES["phase2-v1"]
    assert phase_two.uses_context is True
    assert phase_two.terminal_status is RunStatus.COMPLETED
    assert PHASE_TWO_STAGE_SEQUENCE == ("scout", "filter", "reader", "extractor")
    assert pipeline.PHASE_TWO_MAX_SCOPES == frozenset(
        {
            pipeline.EffectScope.NONE,
            pipeline.EffectScope.LOCAL_STATE,
            pipeline.EffectScope.REMOTE_READ,
        }
    )
    assert pipeline.SideEffectPolicy.phase_two().allowed_scopes == (
        pipeline.PHASE_TWO_MAX_SCOPES
    )


def test_run_signature_covers_repository_subjects() -> None:
    hints = get_type_hints(PipelineRunner.run)
    assert hints["subject"] == FixtureSubject | RepositorySubject


def test_phase_two_slice_completes_with_context_telemetry_and_summary(tmp_path: Path) -> None:
    subject = load_subject(APPROVED_SUBJECT)
    processor = DoublePhaseTwoProcessor()
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        summary = PipelineRunner(store, processor).run(subject, tmp_path / "output")
        chain = store.verify_run_chain(summary.run_id)
        telemetry_rows = store.connection.execute(
            """SELECT prompt_version, model_id, request_id, latency_ms,
                      prompt_tokens, completion_tokens, total_tokens
               FROM stage_attempts ORDER BY stage_index"""
        ).fetchall()
    finally:
        store.close()

    assert summary.status is RunStatus.COMPLETED
    assert summary.last_stage is PipelineStage.EXTRACTOR
    assert summary.reused_stage_count == 0
    assert summary.publication_plan_path == "extraction-summary.json"
    assert summary.remote_writes_attempted == 0

    stages = [stage for stage, _context in processor.calls]
    assert stages == [
        PipelineStage.SCOUT,
        PipelineStage.FILTER,
        PipelineStage.READER,
        PipelineStage.EXTRACTOR,
    ]
    assert [attempt.stage_index for attempt in chain.attempts] == [0, 1, 2, 3]
    assert [envelope.stage_index for envelope in chain.results] == [0, 1, 2, 3]

    scout_context = processor.calls[0][1]
    assert scout_context.subject is subject
    assert scout_context.prior_payloads == {}
    assert isinstance(scout_context.scratch, dict)
    assert processor.calls[1][1].prior_payloads.keys() == {"scout"}
    assert processor.calls[1][1].prior_payloads["scout"]["pinned_commit_sha"] == PINNED_SHA
    assert processor.calls[2][1].prior_payloads.keys() == {"scout", "filter"}
    assert processor.calls[3][1].prior_payloads.keys() == {"scout", "filter", "reader"}

    expected_telemetry = ("extract-prompt-v1", "test-model", "req-double", 7, 3, 5, 8)
    assert [tuple(row) for row in telemetry_rows] == [expected_telemetry] * 4
    for envelope in chain.results:
        assert envelope.prompt_version == "extract-prompt-v1"
        assert envelope.policy_version is None
        assert envelope.model_id == "test-model"
        assert envelope.request_id == "req-double"

    artifact = tmp_path / "output" / "extraction-summary.json"
    extraction = ExtractionSummary.model_validate_json(artifact.read_bytes())
    assert extraction.run_id == summary.run_id
    assert extraction.subject_id == subject.subject_id
    assert extraction.repository == subject.repository
    assert extraction.pinned_commit_sha == PINNED_SHA
    assert [(entry.stage, entry.outcome) for entry in extraction.stage_outcomes] == [
        (PipelineStage.SCOUT, "accepted"),
        (PipelineStage.FILTER, "accepted"),
        (PipelineStage.READER, "accepted"),
        (PipelineStage.EXTRACTOR, "extracted"),
    ]
    assert extraction.extractor_outcome == "extracted"
    assert extraction.workflow_count == 2
    assert extraction.workflow_fingerprints == FINGERPRINTS
    assert extraction.remote_writes_attempted == 0
    assert sorted(path.name for path in (tmp_path / "output").iterdir()) == [
        ".extraction-summary.json.lock",
        "extraction-summary.json",
    ]


def test_resume_hydrates_prior_payloads_without_replaying_succeeded_stages(
    tmp_path: Path,
) -> None:
    first = DoublePhaseTwoProcessor()
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, first).run(
                load_subject(APPROVED_SUBJECT),
                tmp_path / "output-a",
                fail_after="reader",
            )
        assert failure.value.code is ErrorCode.PIPELINE_INTERRUPTED
        assert [stage for stage, _context in first.calls] == [
            PipelineStage.SCOUT,
            PipelineStage.FILTER,
            PipelineStage.READER,
        ]

        resumed = DoublePhaseTwoProcessor()
        summary = PipelineRunner(store, resumed).run(
            load_subject(APPROVED_SUBJECT), tmp_path / "output-b"
        )
        chain = store.verify_run_chain(summary.run_id)
    finally:
        store.close()

    assert summary.status is RunStatus.COMPLETED
    assert summary.reused_stage_count == 3
    assert [stage for stage, _context in resumed.calls] == [PipelineStage.EXTRACTOR]
    hydrated = resumed.calls[0][1].prior_payloads
    assert hydrated.keys() == {"scout", "filter", "reader"}
    for envelope in chain.results[:3]:
        assert hydrated[envelope.stage.value] == envelope.payload


def test_telemetry_variation_changes_the_stage_output_hash(tmp_path: Path) -> None:
    def scout_output_hash(prompt_version: str, name: str) -> str:
        store = SQLiteStateStore(tmp_path / f"{name}.db")
        try:
            processor = DoublePhaseTwoProcessor(prompt_version=prompt_version)
            summary = PipelineRunner(store, processor).run(
                load_subject(APPROVED_SUBJECT), tmp_path / name
            )
            return store.verify_run_chain(summary.run_id).results[0].output_hash
        finally:
            store.close()

    assert scout_output_hash("extract-prompt-v1", "run-a") != scout_output_hash(
        "extract-prompt-v2", "run-b"
    )


def test_context_profile_rejects_non_outcome_and_non_mapping_returns(tmp_path: Path) -> None:
    class RawMappingProcessor(DoublePhaseTwoProcessor):
        def process(self, stage_input: StageInput, context: StageContext) -> object:
            return {"stage": stage_input.stage.value}

    class NonMappingPayloadProcessor(DoublePhaseTwoProcessor):
        def process(self, stage_input: StageInput, context: StageContext) -> StageOutcome:
            return StageOutcome(payload=[("stage", stage_input.stage.value)], telemetry=None)

    for index, processor in enumerate(
        (RawMappingProcessor(), NonMappingPayloadProcessor())
    ):
        store = SQLiteStateStore(tmp_path / f"state-{index}.db")
        try:
            with pytest.raises(SafeFailure) as failure:
                PipelineRunner(store, processor).run(
                    load_subject(APPROVED_SUBJECT), tmp_path / f"output-{index}"
                )
            assert failure.value.code is ErrorCode.STAGE_OUTPUT_INVALID
        finally:
            store.close()


def test_fixture_profile_stays_one_argument_telemetry_free_and_publication_bound(
    tmp_path: Path,
) -> None:
    class OneArgProbe(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            return super().process(stage_input)

    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        summary = PipelineRunner(store, OneArgProbe()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "output"
        )
        telemetry_rows = store.connection.execute(
            """SELECT COUNT(*) FROM stage_attempts
               WHERE prompt_version IS NOT NULL OR policy_version IS NOT NULL
                  OR model_id IS NOT NULL OR request_id IS NOT NULL
                  OR latency_ms IS NOT NULL OR prompt_tokens IS NOT NULL"""
        ).fetchone()[0]
    finally:
        store.close()

    assert summary.status is RunStatus.PLANNED_NOT_PUBLISHED
    assert summary.publication_plan_path == "publication-plan.json"
    assert telemetry_rows == 0
    assert (tmp_path / "output" / "publication-plan.json").is_file()
    assert not (tmp_path / "output" / "extraction-summary.json").exists()


def test_record_attempt_telemetry_requires_a_running_attempt(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        with pytest.raises(SafeFailure) as failure:
            store.record_attempt_telemetry("missing-run:scout:1", _telemetry())
        assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    finally:
        store.close()


def test_state_store_protocol_exposes_record_attempt_telemetry() -> None:
    protocol_signature = inspect.signature(StateStore.record_attempt_telemetry)
    adapter_signature = inspect.signature(SQLiteStateStore.record_attempt_telemetry)
    assert tuple(protocol_signature.parameters) == tuple(adapter_signature.parameters)
