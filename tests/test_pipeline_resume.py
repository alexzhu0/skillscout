"""Migration, durable-manifest and no-replay evidence for schema v2."""

from __future__ import annotations

import fcntl
import hashlib
import inspect
import json
import multiprocessing
import os
import shutil
import sqlite3
from pathlib import Path
from typing import get_type_hints

import pytest

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.localfs import AnchoredDirectory
from skillscout.adapters.semantic_provider import (
    SemanticProviderFailure,
    SemanticTransportDisposition,
)
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import (
    PipelineRunner,
    RetryPolicy,
    SemanticDurabilityGuard,
    SemanticReservationReceipt,
)
from skillscout.application.ports import (
    ERROR_SUMMARIES,
    DurabilityReceipt,
    ErrorCode,
    SafeFailure,
    StageOutcome,
    StateStore,
)
from skillscout.domain.canonical import (
    reusable_key_digest,
    sha256_digest,
    stage_input_hash,
)
from skillscout.domain.enums import AttemptStatus, ExecutionMode, PipelineStage
from skillscout.domain.models import (
    MAX_STAGE_STRING_BYTES,
    ResumeEvent,
    RunIdentity,
    RunRecord,
    StageAttempt,
    StageInput,
    VerifiedRunChain,
)
from skillscout.domain.subjects import RepositorySubject

FROZEN_DATABASE = Path(__file__).parent / "fixtures" / "state" / "v1-cli.db"
FROZEN_PROVENANCE = Path(__file__).parent / "fixtures" / "state" / "v1-cli-provenance.json"
APPROVED_FIXTURE = Path(__file__).parent / "fixtures" / "pipeline" / "approved.json"


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _copy_frozen(tmp_path: Path) -> Path:
    copied = tmp_path / "migrating.db"
    shutil.copy2(FROZEN_DATABASE, copied)
    copied.chmod(0o600)
    return copied


def _schema_fingerprint(path: Path) -> tuple[tuple[object, ...], ...]:
    with _connect(path) as connection:
        return tuple(
            tuple(row)
            for row in connection.execute(
                """SELECT type, name, tbl_name, sql FROM sqlite_master
                   WHERE type IN ('table', 'index') ORDER BY type, name"""
            )
        )


def _resume_events(store: SQLiteStateStore, run_id: str) -> tuple[ResumeEvent, ...]:
    rows = store.connection.execute(
        """SELECT * FROM resume_events WHERE run_id = ?
           ORDER BY event_index""",
        (run_id,),
    ).fetchall()
    events: list[ResumeEvent] = []
    for row in rows:
        payload = dict(row)
        if payload["checkpoint_stage"] is not None:
            payload["checkpoint_stage"] = PipelineStage(payload["checkpoint_stage"])
        events.append(ResumeEvent.model_validate(payload))
    return tuple(events)


def test_frozen_fixture_provenance_is_real_interrupted_schema_v1() -> None:
    provenance = json.loads(FROZEN_PROVENANCE.read_text())
    assert (
        hashlib.sha256(FROZEN_DATABASE.read_bytes()).hexdigest() == (provenance["database_sha256"])
    )
    assert "skillscout dry-run" in provenance["command"]
    assert "--fail-after generator" in provenance["command"]
    with _connect(FROZEN_DATABASE) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert dict(connection.execute("SELECT run_id, status FROM runs").fetchone()) == {
            "run_id": provenance["run_id"],
            "status": "interrupted",
        }
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM stage_attempts WHERE stage = 'validators'"
            ).fetchone()[0]
            == 0
        )


def test_migrated_frozen_run_resumes_at_validators_without_replay(tmp_path: Path) -> None:
    copied = _copy_frozen(tmp_path)
    provenance = json.loads(FROZEN_PROVENANCE.read_text())
    with _connect(copied) as connection:
        original_hashes = [
            row[0]
            for row in connection.execute(
                "SELECT output_hash FROM stage_results ORDER BY stage_index"
            )
        ]

    calls: list[PipelineStage] = []

    class CanaryProcessor(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            if stage_input.stage.value in {
                "scout",
                "filter",
                "reader",
                "extractor",
                "qualifier",
                "generator",
            }:
                raise AssertionError("a durable schema-v1 stage was replayed")
            calls.append(stage_input.stage)
            return super().process(stage_input)

    store = SQLiteStateStore(copied)
    try:
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 3
        event_rows = store.connection.execute(
            "SELECT * FROM resume_events ORDER BY event_index"
        ).fetchall()
        assert len(event_rows) == 1
        assert tuple(event_rows[0])[2:5] == (0, None, 0)
        migrated_run = store.connection.execute(
            "SELECT latest_resume_event_hash, reused_stage_count FROM runs"
        ).fetchone()
        assert tuple(migrated_run) == (event_rows[0]["event_hash"], 0)
        with pytest.raises(SafeFailure) as unbound:
            store.inspect_run(str(provenance["run_id"]))
        assert unbound.value.code is ErrorCode.STATE_IDENTITY_UNBOUND
        assert unbound.value.as_dict() == {
            "code": "state_identity_unbound",
            "summary": "Run identity is not bound.",
        }

        subject = load_fixture(APPROVED_FIXTURE)
        fixture_hash = sha256_digest(subject.model_dump(mode="json", exclude_none=False))
        wrong = RunIdentity(
            schema_version="1",
            subject_id=subject.subject_id,
            fixture_hash="sha256:" + "f" * 64,
            producer_version="fixture-v1",
            retry_policy_version="retry-v1",
        )
        before_wrong_bind = copied.read_bytes()
        assert store.bind_legacy_run(wrong) is None
        assert copied.read_bytes() == before_wrong_bind
        assert (
            store.connection.execute("SELECT identity_state FROM runs").fetchone()[0]
            == "legacy_unbound"
        )

        expected = wrong.model_copy(update={"fixture_hash": fixture_hash})
        bound = store.bind_legacy_run(expected)
        assert isinstance(bound, RunRecord)
        assert bound.identity_state == "bound"
        assert bound.identity == expected
        assert isinstance(store.verify_run_chain(bound.run_id, expected), VerifiedRunChain)
        assert store.inspect_run(bound.run_id)["run"]["identity_state"] == "bound"

        summary = PipelineRunner(store, CanaryProcessor()).run(subject, tmp_path / "output")
        assert summary.run_id == provenance["run_id"]
        assert summary.reused_stage_count == 6
        assert calls == [
            PipelineStage.VALIDATORS,
            PipelineStage.REVIEWER,
            PipelineStage.PUBLICATION_PLANNER,
        ]
        migrated_hashes = [
            row[0]
            for row in store.connection.execute(
                "SELECT output_hash FROM stage_results ORDER BY stage_index LIMIT 6"
            )
        ]
        assert migrated_hashes == original_hashes
        checkpoint = store.connection.execute(
            "SELECT stage, stage_index FROM checkpoints ORDER BY stage_index DESC LIMIT 1"
        ).fetchone()
        assert tuple(checkpoint) == ("publication_planner", 8)
    finally:
        store.close()

    assert (
        hashlib.sha256(FROZEN_DATABASE.read_bytes()).hexdigest() == (provenance["database_sha256"])
    )


def test_legacy_binding_verifies_a_private_candidate_before_durable_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copied = _copy_frozen(tmp_path)
    subject = load_fixture(APPROVED_FIXTURE)
    fixture_hash = sha256_digest(subject.model_dump(mode="json", exclude_none=False))
    expected = RunIdentity(
        schema_version="1",
        subject_id=subject.subject_id,
        fixture_hash=fixture_hash,
        producer_version="fixture-v1",
        retry_policy_version="retry-v1",
    )
    store = SQLiteStateStore(copied)
    original = store._verify_run_chain
    observed: list[tuple[bool, str, str]] = []

    def observe_candidate(database, run_id: str, identity: RunIdentity | None):
        row = database.execute(
            "SELECT identity_state, fixture_hash FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        observed.append(
            (
                database is not store.connection,
                str(row["identity_state"]),
                str(row["fixture_hash"]),
            )
        )
        return original(database, run_id, identity)

    monkeypatch.setattr(store, "_verify_run_chain", observe_candidate)
    try:
        wrong = expected.model_copy(update={"fixture_hash": "sha256:" + "f" * 64})
        before = copied.read_bytes()
        assert store.bind_legacy_run(wrong) is None
        assert copied.read_bytes() == before
        assert tuple(
            store.connection.execute(
                "SELECT identity_state, fixture_hash FROM runs"
            ).fetchone()
        ) == ("legacy_unbound", None)

        bound = store.bind_legacy_run(expected)
        assert bound is not None and bound.identity == expected
        assert observed == [
            (True, "bound", wrong.fixture_hash),
            (True, "bound", expected.fixture_hash),
        ]
    finally:
        store.close()


def test_state_store_protocol_matches_domain_typed_verified_chain_contract() -> None:
    protocol_signature = inspect.signature(StateStore.verify_run_chain)
    adapter_signature = inspect.signature(SQLiteStateStore.verify_run_chain)
    assert tuple(protocol_signature.parameters) == tuple(adapter_signature.parameters)
    assert get_type_hints(StateStore.verify_run_chain)["return"] is VerifiedRunChain
    assert get_type_hints(SQLiteStateStore.verify_run_chain)["return"] is VerifiedRunChain


def test_state_store_protocol_exposes_only_atomic_resume_decisions() -> None:
    protocol_signature = inspect.signature(StateStore.record_resume_decision)
    adapter_signature = inspect.signature(SQLiteStateStore.record_resume_decision)
    assert tuple(protocol_signature.parameters) == tuple(adapter_signature.parameters)
    assert get_type_hints(StateStore.record_resume_decision)["return"] is ResumeEvent
    assert get_type_hints(SQLiteStateStore.record_resume_decision)["return"] is ResumeEvent
    assert not hasattr(StateStore, "set_reused_stage_count")
    assert not hasattr(SQLiteStateStore, "set_reused_stage_count")


def test_fresh_run_uses_genesis_as_its_persisted_zero_reuse_authority(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "fresh-genesis-authority.db")
    try:
        summary = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "fresh-genesis-output"
        )
        events = _resume_events(store, summary.run_id)
        run = store.connection.execute(
            "SELECT latest_resume_event_hash, reused_stage_count FROM runs WHERE run_id = ?",
            (summary.run_id,),
        ).fetchone()
    finally:
        store.close()

    assert len(events) == 1
    assert events[0].event_index == 0
    assert events[0].reused_stage_count == summary.reused_stage_count == 0
    assert tuple(run) == (events[0].event_hash, 0)


def test_crash_before_first_attempt_appends_zero_prefix_and_starts_at_scout(
    tmp_path: Path,
) -> None:
    subject = load_fixture(APPROVED_FIXTURE)
    identity = RunIdentity(
        schema_version="2",
        subject_id=subject.subject_id,
        fixture_hash=sha256_digest(subject.model_dump(mode="json", exclude_none=False)),
        producer_version="fixture-v1",
        retry_policy_version="retry-v1",
    )
    calls: list[PipelineStage] = []

    class Probe(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            calls.append(stage_input.stage)
            return super().process(stage_input)

    store = SQLiteStateStore(tmp_path / "crash-before-first.db")
    try:
        store.create_run(
            "crash-before-first",
            identity,
            "2026-07-19T00:00:00.000000Z",
        )
        summary = PipelineRunner(store, Probe()).run(
            subject, tmp_path / "crash-before-first-output"
        )
        events = _resume_events(store, summary.run_id)
    finally:
        store.close()

    assert calls[0] is PipelineStage.SCOUT
    assert [event.event_index for event in events] == [0, 1]
    assert [event.reused_stage_count for event in events] == [0, 0]
    assert events[1].prior_event_hash == events[0].event_hash
    assert events[1].checkpoint_stage is None
    assert summary.reused_stage_count == 0


def test_crash_after_zero_prefix_decision_appends_another_zero_before_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = load_fixture(APPROVED_FIXTURE)
    identity = RunIdentity(
        schema_version="2",
        subject_id=subject.subject_id,
        fixture_hash=sha256_digest(subject.model_dump(mode="json", exclude_none=False)),
        producer_version="fixture-v1",
        retry_policy_version="retry-v1",
    )
    calls: list[PipelineStage] = []

    class Probe(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            calls.append(stage_input.stage)
            return super().process(stage_input)

    store = SQLiteStateStore(tmp_path / "crash-after-zero.db")
    store.create_run(
        "crash-after-zero",
        identity,
        "2026-07-19T00:00:00.000000Z",
    )
    original_start_attempt = store.start_attempt

    def crash_before_start(_attempt: StageAttempt) -> None:
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)

    monkeypatch.setattr(store, "start_attempt", crash_before_start)
    with pytest.raises(SafeFailure) as failure:
        PipelineRunner(store, Probe()).run(subject, tmp_path / "crashed-output")
    assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    after_crash = _resume_events(store, "crash-after-zero")
    assert [event.reused_stage_count for event in after_crash] == [0, 0]
    assert calls == []
    assert store.connection.execute("SELECT COUNT(*) FROM stage_attempts").fetchone()[0] == 0

    monkeypatch.setattr(store, "start_attempt", original_start_attempt)
    try:
        summary = PipelineRunner(store, Probe()).run(
            subject, tmp_path / "recovered-output"
        )
        events = _resume_events(store, summary.run_id)
    finally:
        store.close()

    assert calls.count(PipelineStage.SCOUT) == 1
    assert [event.event_index for event in events] == [0, 1, 2]
    assert [event.reused_stage_count for event in events] == [0, 0, 0]
    assert events[1].prior_event_hash == events[0].event_hash
    assert events[2].prior_event_hash == events[1].event_hash
    assert summary.reused_stage_count == 0


def test_positive_resume_event_is_durable_before_first_new_processor_call(
    tmp_path: Path,
) -> None:
    subject = load_fixture(APPROVED_FIXTURE)
    store = SQLiteStateStore(tmp_path / "event-before-work.db")
    with pytest.raises(SafeFailure):
        PipelineRunner(store, FixtureProcessor()).run(
            subject, tmp_path / "event-before-first", fail_after="generator"
        )
    run_id = str(store.connection.execute("SELECT run_id FROM runs").fetchone()[0])
    generator_checkpoint = store.latest_checkpoint(run_id)
    assert generator_checkpoint is not None
    observations: list[ResumeEvent] = []

    class EventProbe(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            observations.append(_resume_events(store, run_id)[-1])
            return super().process(stage_input)

    try:
        summary = PipelineRunner(store, EventProbe()).run(
            subject, tmp_path / "event-before-resume"
        )
        events = _resume_events(store, run_id)
    finally:
        store.close()

    assert observations[0] == events[1]
    assert events[1].prior_event_hash == events[0].event_hash
    assert events[1].reused_stage_count == 6
    assert events[1].checkpoint_stage is PipelineStage.GENERATOR
    assert events[1].checkpoint_result_row_id == generator_checkpoint.result_row_id
    assert events[1].checkpoint_manifest_hash == generator_checkpoint.manifest_hash
    assert summary.reused_stage_count == events[1].reused_stage_count


def test_repeated_positive_resumes_form_contiguous_checkpoint_bound_chain(
    tmp_path: Path,
) -> None:
    subject = load_fixture(APPROVED_FIXTURE)
    store = SQLiteStateStore(tmp_path / "repeated-positive.db")
    try:
        with pytest.raises(SafeFailure):
            PipelineRunner(store, FixtureProcessor()).run(
                subject, tmp_path / "positive-one", fail_after="generator"
            )
        with pytest.raises(SafeFailure):
            PipelineRunner(store, FixtureProcessor()).run(
                subject, tmp_path / "positive-two", fail_after="validators"
            )
        summary = PipelineRunner(store, FixtureProcessor()).run(
            subject, tmp_path / "positive-three"
        )
        events = _resume_events(store, summary.run_id)
    finally:
        store.close()

    assert [event.event_index for event in events] == [0, 1, 2]
    assert [event.reused_stage_count for event in events] == [0, 6, 7]
    assert [event.checkpoint_stage for event in events] == [
        None,
        PipelineStage.GENERATOR,
        PipelineStage.VALIDATORS,
    ]
    assert events[1].prior_event_hash == events[0].event_hash
    assert events[2].prior_event_hash == events[1].event_hash
    assert summary.reused_stage_count == 7


def test_run_row_count_cannot_authorize_or_override_persisted_resume_fact(
    tmp_path: Path,
) -> None:
    subject = load_fixture(APPROVED_FIXTURE)
    store = SQLiteStateStore(tmp_path / "count-is-not-authority.db")
    try:
        with pytest.raises(SafeFailure):
            PipelineRunner(store, FixtureProcessor()).run(
                subject, tmp_path / "count-first", fail_after="generator"
            )
        run_id = str(store.connection.execute("SELECT run_id FROM runs").fetchone()[0])
        before = tuple(
            store.connection.execute(
                """SELECT r.status, r.updated_at, COUNT(DISTINCT a.attempt_id),
                          COUNT(DISTINCT e.event_hash)
                   FROM runs r
                   LEFT JOIN stage_attempts a USING (run_id)
                   LEFT JOIN resume_events e USING (run_id)
                   WHERE r.run_id = ? GROUP BY r.run_id""",
                (run_id,),
            ).fetchone()
        )
        store.connection.execute(
            "UPDATE runs SET reused_stage_count = 1 WHERE run_id = ?", (run_id,)
        )
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor()).run(
                subject, tmp_path / "count-resume"
            )
        after = tuple(
            store.connection.execute(
                """SELECT r.status, r.updated_at, COUNT(DISTINCT a.attempt_id),
                          COUNT(DISTINCT e.event_hash)
                   FROM runs r
                   LEFT JOIN stage_attempts a USING (run_id)
                   LEFT JOIN resume_events e USING (run_id)
                   WHERE r.run_id = ? GROUP BY r.run_id""",
                (run_id,),
            ).fetchone()
        )
    finally:
        store.close()

    assert failure.value.as_dict() == {
        "code": ErrorCode.STATE_INTEGRITY_ERROR.value,
        "summary": ERROR_SUMMARIES[ErrorCode.STATE_INTEGRITY_ERROR],
    }
    assert after == before


def test_complete_run_identity_is_persisted_before_first_attempt(tmp_path: Path) -> None:
    subject = load_fixture(APPROVED_FIXTURE)
    store = SQLiteStateStore(tmp_path / "identity-before-attempt.db")

    class IdentityProbe(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            row = store.connection.execute(
                """SELECT schema_version, subject_id, fixture_hash, producer_version,
                          retry_policy_version, identity_state
                   FROM runs"""
            ).fetchone()
            assert dict(row) == {
                "schema_version": "2",
                "subject_id": subject.subject_id,
                "fixture_hash": sha256_digest(subject.model_dump(mode="json", exclude_none=False)),
                "producer_version": "fixture-v1",
                "retry_policy_version": "retry-v1",
                "identity_state": "bound",
            }
            return super().process(stage_input)

    try:
        PipelineRunner(store, IdentityProbe()).run(subject, tmp_path / "identity-out")
    finally:
        store.close()


def test_exact_identity_lookup_uses_index_and_skips_newer_subject_mismatch(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "identity-index.db")
    first = RunIdentity(
        schema_version="2",
        subject_id="fixture:same-subject",
        fixture_hash="sha256:" + "1" * 64,
        producer_version="fixture-v1",
        retry_policy_version="retry-v1",
    )
    newer = first.model_copy(
        update={
            "fixture_hash": "sha256:" + "2" * 64,
            "producer_version": "fixture-v2",
            "retry_policy_version": "retry-v2",
        }
    )
    try:
        store.create_run("run-a", first, "2026-07-19T00:00:00.000000Z")
        store.create_run("run-b", newer, "2026-07-19T00:00:01.000000Z")
        selected = store.find_resumable_run(first)
        assert isinstance(selected, RunRecord)
        assert selected.run_id == "run-a"
        assert selected.identity == first
        query_plan = " ".join(
            str(value)
            for value in store.connection.execute(
                """EXPLAIN QUERY PLAN SELECT run_id FROM runs
                   INDEXED BY idx_runs_resumable_identity
                   WHERE schema_version = ? AND subject_id = ? AND fixture_hash = ?
                     AND producer_version = ? AND retry_policy_version = ?
                     AND identity_state = 'bound'
                     AND status IN ('running', 'interrupted')
                   ORDER BY updated_at DESC, run_id DESC LIMIT 1""",
                (
                    first.schema_version,
                    first.subject_id,
                    first.fixture_hash,
                    first.producer_version,
                    first.retry_policy_version,
                ),
            ).fetchone()
        )
        assert "idx_runs_resumable_identity" in query_plan
    finally:
        store.close()


def test_changed_a_prime_completes_without_reuse_and_both_runs_inspect(
    tmp_path: Path,
) -> None:
    original = load_fixture(APPROVED_FIXTURE)
    changed = original.model_copy(
        update={
            "workflow": original.workflow.model_copy(
                update={"goal": "A-prime canonical workflow goal"}
            )
        }
    )
    store = SQLiteStateStore(tmp_path / "changed-a-prime.db")
    try:
        with pytest.raises(SafeFailure):
            PipelineRunner(store, FixtureProcessor()).run(
                original, tmp_path / "a-interrupted", fail_after="generator"
            )
        original_run = str(
            store.connection.execute(
                "SELECT run_id FROM runs WHERE fixture_hash = ?",
                (sha256_digest(original.model_dump(mode="json", exclude_none=False)),),
            ).fetchone()[0]
        )

        changed_summary = PipelineRunner(store, FixtureProcessor()).run(
            changed, tmp_path / "a-prime"
        )
        assert changed_summary.run_id != original_run
        assert changed_summary.reused_stage_count == 0
        assert store.inspect_run(original_run)["run"]["status"] == "interrupted"
        assert store.inspect_run(changed_summary.run_id)["run"]["status"] == (
            "planned_not_published"
        )
        duplicates = store.connection.execute(
            """SELECT result_id, COUNT(*) AS count FROM stage_results
               GROUP BY result_id HAVING COUNT(*) > 1"""
        ).fetchall()
        assert duplicates
    finally:
        store.close()


def test_a_interrupt_b_interrupt_a_rerun_resumes_exact_a_without_touching_b(
    tmp_path: Path,
) -> None:
    original = load_fixture(APPROVED_FIXTURE)
    changed = original.model_copy(
        update={
            "workflow": original.workflow.model_copy(update={"goal": "B canonical workflow goal"})
        }
    )
    store = SQLiteStateStore(tmp_path / "a-b-a.db")
    try:
        with pytest.raises(SafeFailure):
            PipelineRunner(store, FixtureProcessor()).run(
                original, tmp_path / "a-first", fail_after="generator"
            )
        a_run = str(
            store.connection.execute(
                "SELECT run_id FROM runs ORDER BY created_at LIMIT 1"
            ).fetchone()[0]
        )
        a_hashes = [
            tuple(row)
            for row in store.connection.execute(
                """SELECT result_row_id, result_id, output_hash, manifest_hash
                   FROM stage_results WHERE run_id = ? ORDER BY stage_index""",
                (a_run,),
            )
        ]

        with pytest.raises(SafeFailure):
            PipelineRunner(store, FixtureProcessor()).run(
                changed, tmp_path / "b-first", fail_after="reader"
            )
        b_run = str(
            store.connection.execute(
                "SELECT run_id FROM runs WHERE run_id != ?", (a_run,)
            ).fetchone()[0]
        )
        b_before = tuple(
            store.connection.execute(
                """SELECT r.status, r.updated_at, c.stage, c.stage_index,
                          c.result_row_id, c.result_id, c.output_hash, c.manifest_hash
                   FROM runs r JOIN checkpoints c USING (run_id)
                   WHERE r.run_id = ? ORDER BY c.stage_index DESC LIMIT 1""",
                (b_run,),
            ).fetchone()
        )

        calls: list[PipelineStage] = []

        class ResumeCanary(FixtureProcessor):
            def process(self, stage_input: StageInput) -> dict[str, object]:
                calls.append(stage_input.stage)
                return super().process(stage_input)

        resumed = PipelineRunner(store, ResumeCanary()).run(original, tmp_path / "a-resumed")
        assert resumed.run_id == a_run
        assert resumed.reused_stage_count == 6
        assert calls == [
            PipelineStage.VALIDATORS,
            PipelineStage.REVIEWER,
            PipelineStage.PUBLICATION_PLANNER,
        ]
        assert [
            tuple(row)
            for row in store.connection.execute(
                """SELECT result_row_id, result_id, output_hash, manifest_hash
                   FROM stage_results WHERE run_id = ?
                   ORDER BY stage_index LIMIT 6""",
                (a_run,),
            )
        ] == a_hashes
        resumed_event = _resume_events(store, a_run)[-1]
        a_checkpoint = store.connection.execute(
            """SELECT result_row_id, manifest_hash FROM checkpoints
               WHERE run_id = ? AND stage = 'generator'""",
            (a_run,),
        ).fetchone()
        b_checkpoint = store.connection.execute(
            """SELECT result_row_id, manifest_hash FROM checkpoints
               WHERE run_id = ? ORDER BY stage_index DESC LIMIT 1""",
            (b_run,),
        ).fetchone()
        assert resumed_event.checkpoint_stage is PipelineStage.GENERATOR
        assert (
            resumed_event.checkpoint_result_row_id,
            resumed_event.checkpoint_manifest_hash,
        ) == tuple(a_checkpoint)
        assert (
            resumed_event.checkpoint_result_row_id,
            resumed_event.checkpoint_manifest_hash,
        ) != tuple(b_checkpoint)
        b_after = tuple(
            store.connection.execute(
                """SELECT r.status, r.updated_at, c.stage, c.stage_index,
                          c.result_row_id, c.result_id, c.output_hash, c.manifest_hash
                   FROM runs r JOIN checkpoints c USING (run_id)
                   WHERE r.run_id = ? ORDER BY c.stage_index DESC LIMIT 1""",
                (b_run,),
            ).fetchone()
        )
        assert b_after == b_before
    finally:
        store.close()


@pytest.mark.parametrize("seam", ["after_schema", "after_copy", "after_validation"])
def test_forced_migration_failure_rolls_back_to_intact_v1(tmp_path: Path, seam: str) -> None:
    copied = _copy_frozen(tmp_path)
    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(copied, migration_fail_at=seam)
    assert failure.value.code is ErrorCode.STATE_SCHEMA_MIGRATION_ERROR

    with _connect(copied) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert tables == {"runs", "stage_attempts", "stage_results", "checkpoints"}
        assert connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 6
    assert not copied.with_suffix(".manifests").exists()


def test_missing_database_creates_v3_and_existing_v3_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "new.db"
    first = SQLiteStateStore(database)
    first.close()
    with _connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {
            "runs",
            "stage_attempts",
            "stage_results",
            "checkpoints",
            "resume_events",
        } <= tables
    second = SQLiteStateStore(database)
    second.close()


def test_fresh_and_migrated_v3_use_identical_schema_fingerprint(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh.db"
    SQLiteStateStore(fresh).close()
    migrated = _copy_frozen(tmp_path)
    SQLiteStateStore(migrated).close()

    assert _schema_fingerprint(migrated) == _schema_fingerprint(fresh)


@pytest.mark.parametrize("kind", ["version_zero", "future", "malformed"])
def test_unknown_or_malformed_state_fails_closed_without_recreation(
    tmp_path: Path, kind: str
) -> None:
    database = tmp_path / f"{kind}.db"
    if kind == "malformed":
        database.write_bytes(b"not a sqlite database\x00hostile")
    else:
        with _connect(database) as connection:
            if kind == "future":
                connection.execute("PRAGMA user_version = 99")
            connection.commit()
    before = database.read_bytes()
    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(database)
    assert failure.value.code is ErrorCode.STATE_SCHEMA_INCOMPATIBLE
    assert database.read_bytes() == before


def test_processor_runs_outside_transactions_and_manifest_precedes_db_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "state.db"
    store = SQLiteStateStore(database)
    processor_observations: list[bool] = []
    manifest_observations: list[Path] = []

    class TransactionProbe(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            processor_observations.append(store.connection.in_transaction)
            return super().process(stage_input)

    original_commit = store._commit_success

    def observe_manifest(envelope, manifest_path):
        assert manifest_path.is_file()
        manifest_observations.append(manifest_path)
        return original_commit(envelope, manifest_path)

    monkeypatch.setattr(store, "_commit_success", observe_manifest)
    try:
        PipelineRunner(store, TransactionProbe()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "output"
        )
    finally:
        store.close()
    assert processor_observations == [False] * 9
    assert len(manifest_observations) == 9
    assert all(path.is_file() for path in manifest_observations)


def test_database_failure_after_manifest_never_advances_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "state.db"
    store = SQLiteStateStore(database)
    written: list[Path] = []

    def fail_after_manifest(_envelope, manifest_path):
        assert manifest_path.is_file()
        written.append(manifest_path)
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)

    monkeypatch.setattr(store, "_commit_success", fail_after_manifest)
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), tmp_path / "output"
            )
        assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
        assert written
        assert store.connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0
        attempt = store.connection.execute(
            "SELECT status, error_code, error_summary FROM stage_attempts"
        ).fetchone()
        run = store.connection.execute(
            "SELECT status, error_code, error_summary FROM runs"
        ).fetchone()
        assert tuple(attempt) == (
            "failed",
            ErrorCode.STATE_OPERATION_FAILED.value,
            ERROR_SUMMARIES[ErrorCode.STATE_OPERATION_FAILED],
        )
        assert tuple(run) == (
            "interrupted",
            ErrorCode.STATE_OPERATION_FAILED.value,
            ERROR_SUMMARIES[ErrorCode.STATE_OPERATION_FAILED],
        )
    finally:
        store.close()


def test_stale_running_attempt_is_abandoned_before_monotonic_replacement(
    tmp_path: Path,
) -> None:
    subject = load_fixture(APPROVED_FIXTURE)
    store = SQLiteStateStore(tmp_path / "state.db")
    run_id = "stale-run"
    store.create_run(
        run_id,
        RunIdentity(
            schema_version="2",
            subject_id=subject.subject_id,
            fixture_hash=sha256_digest(subject.model_dump(mode="json", exclude_none=False)),
            producer_version="fixture-v1",
            retry_policy_version="retry-v1",
        ),
        "2026-07-17T00:00:00.000000Z",
    )
    stage_input = StageInput(
        schema_version="2",
        execution_mode=ExecutionMode.DRY_RUN,
        subject_id=subject.subject_id,
        stage=PipelineStage.SCOUT,
        previous_output_hash=None,
        fixture_hash=sha256_digest(subject.model_dump(mode="json", exclude_none=False)),
    )
    input_hash = stage_input_hash(stage_input)
    digest = reusable_key_digest(
        subject_id=subject.subject_id,
        stage=PipelineStage.SCOUT,
        input_hash=input_hash,
        producer_version="fixture-v1",
        retry_policy_version="retry-v1",
    )
    store.start_attempt(
        StageAttempt(
            attempt_id=f"{run_id}:scout:1",
            run_id=run_id,
            subject_id=subject.subject_id,
            stage=PipelineStage.SCOUT,
            stage_index=0,
            attempt_no=1,
            status=AttemptStatus.RUNNING,
            input_hash=input_hash,
            producer_version="fixture-v1",
            retry_policy_version="retry-v1",
            reusable_key_digest=digest,
            started_at="2026-07-17T00:00:00.000000Z",
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
    )
    try:
        PipelineRunner(store, FixtureProcessor()).run(subject, tmp_path / "output")
        rows = store.connection.execute(
            """SELECT attempt_no, status FROM stage_attempts
               WHERE stage = 'scout' ORDER BY attempt_no"""
        ).fetchall()
        assert [tuple(row) for row in rows] == [(1, "abandoned"), (2, "succeeded")]
    finally:
        store.close()


def test_three_transient_attempts_exhaust_one_digest_before_fourth_invocation(
    tmp_path: Path,
) -> None:
    calls = 0

    class AlwaysTransient(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            nonlocal calls
            calls += 1
            raise SafeFailure(ErrorCode.STAGE_TRANSIENT_FAILURE)

    store = SQLiteStateStore(tmp_path / "state.db")
    subject = load_fixture(APPROVED_FIXTURE)
    processor = AlwaysTransient()
    try:
        for _ in range(3):
            with pytest.raises(SafeFailure) as failure:
                PipelineRunner(store, processor).run(subject, tmp_path / "output")
            assert failure.value.code is ErrorCode.STAGE_TRANSIENT_FAILURE
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, processor).run(subject, tmp_path / "output")
        assert failure.value.code is ErrorCode.RETRY_EXHAUSTED
        assert calls == 3
        rows = store.connection.execute(
            """SELECT reusable_key_digest, status, retryable FROM stage_attempts
               WHERE stage = 'scout' ORDER BY attempt_no"""
        ).fetchall()
        assert len({row["reusable_key_digest"] for row in rows}) == 1
        assert [tuple(row)[1:] for row in rows] == [("failed", 1)] * 3
        query_plan = " ".join(
            str(value)
            for value in store.connection.execute(
                "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM stage_attempts WHERE reusable_key_digest = ?",
                (rows[0]["reusable_key_digest"],),
            ).fetchone()
        )
        assert "idx_attempts_reusable" in query_plan
    finally:
        store.close()


def test_fail_once_unexpected_exception_resumes_failed_stage_without_prefix_replay(
    tmp_path: Path,
) -> None:
    credential = "OPENAI_API_KEY_UNEXPECTED_DO_NOT_DISCLOSE_123456"
    attacker_path = "/attacker/unexpected/private/path"
    calls: list[PipelineStage] = []
    failed_once = False

    class FailOnceAtValidators(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            nonlocal failed_once
            calls.append(stage_input.stage)
            if stage_input.stage is PipelineStage.VALIDATORS and not failed_once:
                failed_once = True
                raise RuntimeError(credential, attacker_path)
            return super().process(stage_input)

    database = tmp_path / "fail-once-unexpected.db"
    store = SQLiteStateStore(database)
    subject = load_fixture(APPROVED_FIXTURE)
    processor = FailOnceAtValidators()
    try:
        with pytest.raises(SafeFailure) as interrupted:
            PipelineRunner(store, processor).run(subject, tmp_path / "first-output")
        assert interrupted.value.as_dict() == {
            "code": ErrorCode.PIPELINE_INTERRUPTED.value,
            "summary": ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
        }
        assert credential not in str(interrupted.value)
        assert attacker_path not in str(interrupted.value)

        run_id = str(store.connection.execute("SELECT run_id FROM runs").fetchone()[0])
        failed_attempt = store.connection.execute(
            """SELECT status, error_code, error_summary, retryable
               FROM stage_attempts WHERE stage = 'validators'"""
        ).fetchone()
        assert tuple(failed_attempt) == (
            "failed",
            ErrorCode.PIPELINE_INTERRUPTED.value,
            ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
            1,
        )
        failed_run = store.connection.execute(
            "SELECT status, error_code, error_summary FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        assert tuple(failed_run) == (
            "interrupted",
            ErrorCode.PIPELINE_INTERRUPTED.value,
            ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
        )

        prefix_attempts = tuple(
            tuple(row)
            for row in store.connection.execute(
                "SELECT * FROM stage_attempts WHERE stage_index < 6 ORDER BY stage_index"
            )
        )
        prefix_results = tuple(
            tuple(row)
            for row in store.connection.execute(
                "SELECT * FROM stage_results WHERE stage_index < 6 ORDER BY stage_index"
            )
        )
        prefix_checkpoints = tuple(
            tuple(row)
            for row in store.connection.execute(
                "SELECT * FROM checkpoints WHERE stage_index < 6 ORDER BY stage_index"
            )
        )
        prefix_manifests = {
            path.relative_to(store.manifest_root).as_posix(): path.read_bytes()
            for path in store.manifest_root.rglob("*.json")
        }
        first_surfaces = database.read_bytes() + b"".join(prefix_manifests.values())
        assert credential.encode() not in first_surfaces
        assert attacker_path.encode() not in first_surfaces

        summary = PipelineRunner(store, processor).run(subject, tmp_path / "second-output")
        assert summary.status.value == "planned_not_published"
        assert summary.run_id == run_id
        assert summary.reused_stage_count == 6
        assert calls.count(PipelineStage.VALIDATORS) == 2
        assert all(calls.count(stage) == 1 for stage in tuple(PipelineStage)[:6])
        assert all(calls.count(stage) == 1 for stage in tuple(PipelineStage)[7:])
        assert prefix_attempts == tuple(
            tuple(row)
            for row in store.connection.execute(
                "SELECT * FROM stage_attempts WHERE stage_index < 6 ORDER BY stage_index"
            )
        )
        assert prefix_results == tuple(
            tuple(row)
            for row in store.connection.execute(
                "SELECT * FROM stage_results WHERE stage_index < 6 ORDER BY stage_index"
            )
        )
        assert prefix_checkpoints == tuple(
            tuple(row)
            for row in store.connection.execute(
                "SELECT * FROM checkpoints WHERE stage_index < 6 ORDER BY stage_index"
            )
        )
        assert all(
            (store.manifest_root / locator).read_bytes() == payload
            for locator, payload in prefix_manifests.items()
        )
        resume_event = _resume_events(store, run_id)[-1]
        assert resume_event.reused_stage_count == 6
        assert resume_event.checkpoint_stage is PipelineStage.GENERATOR
        attempts = store.connection.execute(
            """SELECT status, error_code, error_summary, retryable
               FROM stage_attempts WHERE stage = 'validators' ORDER BY attempt_no"""
        ).fetchall()
        assert [tuple(row) for row in attempts] == [
            (
                "failed",
                ErrorCode.PIPELINE_INTERRUPTED.value,
                ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
                1,
            ),
            ("succeeded", None, None, 0),
        ]
        final_surfaces = database.read_bytes() + b"".join(
            path.read_bytes()
            for root in (store.manifest_root, tmp_path / "second-output")
            for path in root.rglob("*")
            if path.is_file()
        )
        assert credential.encode() not in final_surfaces
        assert attacker_path.encode() not in final_surfaces
    finally:
        store.close()


def test_unexpected_exception_exhaustion_is_finite_and_identity_scoped(
    tmp_path: Path,
) -> None:
    credential = "github_pat_UNEXPECTED_RETRY_DO_NOT_DISCLOSE"
    attacker_path = "/attacker/unexpected/retry/path"
    calls = 0

    class AlwaysUnexpected(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            nonlocal calls
            calls += 1
            raise RuntimeError(credential, attacker_path, stage_input.stage.value)

    original = load_fixture(APPROVED_FIXTURE)
    changed = original.model_copy(
        update={
            "workflow": original.workflow.model_copy(
                update={"goal": "A separate unexpected-exception retry identity"}
            )
        }
    )
    database = tmp_path / "unexpected-exhaustion.db"
    store = SQLiteStateStore(database)
    processor = AlwaysUnexpected()
    try:
        for _ in range(3):
            with pytest.raises(SafeFailure) as interrupted:
                PipelineRunner(store, processor).run(original, tmp_path / "original-output")
            assert interrupted.value.code is ErrorCode.PIPELINE_INTERRUPTED

        with pytest.raises(SafeFailure) as exhausted:
            PipelineRunner(store, processor).run(original, tmp_path / "original-output")
        assert exhausted.value.code is ErrorCode.RETRY_EXHAUSTED
        assert calls == 3

        with pytest.raises(SafeFailure) as changed_interrupted:
            PipelineRunner(store, processor).run(changed, tmp_path / "changed-output")
        assert changed_interrupted.value.code is ErrorCode.PIPELINE_INTERRUPTED
        assert calls == 4

        attempts = store.connection.execute(
            """SELECT reusable_key_digest, status, error_code, error_summary, retryable
               FROM stage_attempts WHERE stage = 'scout'
               ORDER BY reusable_key_digest, attempt_no"""
        ).fetchall()
        counts: dict[str, int] = {}
        for row in attempts:
            digest = str(row["reusable_key_digest"])
            counts[digest] = counts.get(digest, 0) + 1
            assert tuple(row)[1:] == (
                "failed",
                ErrorCode.PIPELINE_INTERRUPTED.value,
                ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
                1,
            )
        assert sorted(counts.values()) == [1, 3]
        surfaces = database.read_bytes() + b"".join(
            path.read_bytes()
            for path in tmp_path.rglob("*")
            if path.is_file() and path != database
        )
        assert credential.encode() not in surfaces
        assert attacker_path.encode() not in surfaces
    finally:
        store.close()


def test_permanent_error_is_not_invoked_twice_for_same_digest(tmp_path: Path) -> None:
    calls = 0

    class PermanentFailure(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            nonlocal calls
            calls += 1
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)

    store = SQLiteStateStore(tmp_path / "state.db")
    subject = load_fixture(APPROVED_FIXTURE)
    processor = PermanentFailure()
    try:
        for _ in range(2):
            with pytest.raises(SafeFailure) as failure:
                PipelineRunner(store, processor).run(subject, tmp_path / "output")
            assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE
        assert calls == 1
        assert store.connection.execute("SELECT COUNT(*) FROM stage_attempts").fetchone()[0] == 1
    finally:
        store.close()


@pytest.mark.parametrize("changed_field", ["input", "retry_policy"])
def test_changed_identity_gets_fresh_budget_and_never_reuses_old_checkpoint(
    tmp_path: Path, changed_field: str
) -> None:
    original = load_fixture(APPROVED_FIXTURE)
    changed_subject = original
    old_processor_version = "fixture-v1"
    new_processor_version = old_processor_version
    old_policy = RetryPolicy(version="retry-v1")
    new_policy = old_policy
    if changed_field == "input":
        changed_subject = original.model_copy(
            update={
                "workflow": original.workflow.model_copy(
                    update={"goal": "A distinct canonical workflow goal"}
                )
            }
        )
    else:
        new_policy = RetryPolicy(version="retry-v2")

    class VersionedTransient(FixtureProcessor):
        def __init__(self, version: str) -> None:
            self.producer_version = version

        def process(self, stage_input: StageInput) -> dict[str, object]:
            raise SafeFailure(ErrorCode.STAGE_TRANSIENT_FAILURE)

    class VersionedSuccess(FixtureProcessor):
        def __init__(self, version: str) -> None:
            self.producer_version = version
            self.calls: list[PipelineStage] = []

        def process(self, stage_input: StageInput) -> dict[str, object]:
            self.calls.append(stage_input.stage)
            return super().process(stage_input)

    budget_store = SQLiteStateStore(tmp_path / f"budget-{changed_field}.db")
    try:
        failing = VersionedTransient(old_processor_version)
        for _ in range(3):
            with pytest.raises(SafeFailure):
                PipelineRunner(budget_store, failing, retry_policy=old_policy).run(
                    original, tmp_path / "old-output"
                )
        success = VersionedSuccess(new_processor_version)
        summary = PipelineRunner(budget_store, success, retry_policy=new_policy).run(
            changed_subject, tmp_path / "new-output"
        )
        assert summary.status.value == "planned_not_published"
        assert success.calls[0] is PipelineStage.SCOUT
        digest_counts = budget_store.connection.execute(
            """SELECT reusable_key_digest, COUNT(*) AS count
               FROM stage_attempts WHERE stage = 'scout'
               GROUP BY reusable_key_digest ORDER BY count DESC"""
        ).fetchall()
        assert [row["count"] for row in digest_counts] == [3, 1]
        assert digest_counts[0]["reusable_key_digest"] != digest_counts[1]["reusable_key_digest"]
    finally:
        budget_store.close()

    checkpoint_store = SQLiteStateStore(tmp_path / f"checkpoint-{changed_field}.db")
    first_processor = VersionedSuccess(old_processor_version)
    try:
        with pytest.raises(SafeFailure):
            PipelineRunner(checkpoint_store, first_processor, retry_policy=old_policy).run(
                original, tmp_path / "checkpoint-old", fail_after="scout"
            )
        old_run_id = checkpoint_store.connection.execute("SELECT run_id FROM runs").fetchone()[0]
        second_processor = VersionedSuccess(new_processor_version)
        summary = PipelineRunner(checkpoint_store, second_processor, retry_policy=new_policy).run(
            changed_subject, tmp_path / "checkpoint-new"
        )
        assert summary.run_id != old_run_id
        assert summary.reused_stage_count == 0
        assert second_processor.calls[0] is PipelineStage.SCOUT
    finally:
        checkpoint_store.close()


def test_unsupported_producer_is_rejected_before_run_creation(tmp_path: Path) -> None:
    calls = 0

    class UnsupportedProcessor(FixtureProcessor):
        producer_version = "fixture-v2"

        def process(self, stage_input: StageInput) -> dict[str, object]:
            nonlocal calls
            calls += 1
            return super().process(stage_input)

    database = tmp_path / "unsupported.db"
    store = SQLiteStateStore(database)
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, UnsupportedProcessor()).run(
                load_fixture(APPROVED_FIXTURE), tmp_path / "output"
            )
        assert failure.value.code is ErrorCode.STAGE_OUTPUT_INVALID
        assert calls == 0
        assert store.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM stage_attempts").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0
        assert not database.with_suffix(".manifests").exists()
        assert not (tmp_path / "output").exists()
    finally:
        store.close()


@pytest.mark.parametrize(
    "output",
    (
        {"value": object()},
        {str(index): "x" * MAX_STAGE_STRING_BYTES for index in range(4)},
    ),
    ids=("non-json", "manifest-cap-plus-one"),
)
def test_invalid_or_oversized_output_closes_lifecycle_before_manifest_io(
    tmp_path: Path,
    output: dict[str, object],
) -> None:
    subject = load_fixture(APPROVED_FIXTURE)

    class InvalidOutputProcessor(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            return output

    filesystem_events: list[str] = []
    database = tmp_path / "invalid-output.db"
    store = SQLiteStateStore(database, filesystem_seam=filesystem_events.append)
    filesystem_events.clear()
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, InvalidOutputProcessor()).run(subject, tmp_path / "output")
        assert failure.value.code is ErrorCode.STAGE_OUTPUT_INVALID
        attempt = store.connection.execute(
            "SELECT status, error_code, error_summary FROM stage_attempts"
        ).fetchone()
        run = store.connection.execute(
            "SELECT status, error_code, error_summary FROM runs"
        ).fetchone()
        assert tuple(attempt) == (
            "failed",
            ErrorCode.STAGE_OUTPUT_INVALID.value,
            ERROR_SUMMARIES[ErrorCode.STAGE_OUTPUT_INVALID],
        )
        assert tuple(run) == (
            "interrupted",
            ErrorCode.STAGE_OUTPUT_INVALID.value,
            ERROR_SUMMARIES[ErrorCode.STAGE_OUTPUT_INVALID],
        )
        assert store.connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0
        assert all("manifest" not in event for event in filesystem_events)
        assert not database.with_suffix(".manifests").exists()
    finally:
        store.close()


def test_indeterminate_failure_closure_is_reconciled_on_next_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class InvalidOutputProcessor(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            return {"value": object()}

    database = tmp_path / "orphan.db"
    store = SQLiteStateStore(database)

    def fail_to_close(*_args: object, **_kwargs: object) -> None:
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)

    monkeypatch.setattr(store, "fail_attempt", fail_to_close)
    with pytest.raises(SafeFailure) as failure:
        PipelineRunner(store, InvalidOutputProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "output"
        )
    assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    assert store.connection.execute("SELECT status FROM stage_attempts").fetchone()[0] == "running"
    assert store.connection.execute("SELECT status FROM runs").fetchone()[0] == "running"
    store.close()

    reopened = SQLiteStateStore(database)
    try:
        attempt = reopened.connection.execute(
            "SELECT status, error_code, error_summary, retryable FROM stage_attempts"
        ).fetchone()
        run = reopened.connection.execute(
            "SELECT status, error_code, error_summary FROM runs"
        ).fetchone()
        assert tuple(attempt) == (
            "abandoned",
            ErrorCode.PIPELINE_INTERRUPTED.value,
            ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
            1,
        )
        assert tuple(run) == (
            "interrupted",
            ErrorCode.PIPELINE_INTERRUPTED.value,
            ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
        )
        assert reopened.connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 0
        assert reopened.connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0
    finally:
        reopened.close()


def test_supported_writer_state_is_immediately_verifiable_and_inspectable(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "supported.db")
    try:
        summary = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "output"
        )
        store.verify_completed_results(summary.run_id, len(PipelineStage))
        inspection = store.inspect_run(summary.run_id)
        assert inspection["run"]["status"] == "planned_not_published"
        assert len(inspection["results"]) == len(PipelineStage)
        assert set(inspection["checkpoint"]) == {
            "run_id",
            "subject_id",
            "stage",
            "stage_index",
            "result_row_id",
            "result_id",
            "output_hash",
            "manifest_hash",
            "manifest_path",
            "updated_at",
        }
        assert inspection["checkpoint"]["manifest_path"].startswith("publication_planner/")
    finally:
        store.close()


def test_running_failed_and_abandoned_records_project_explicit_nulls(
    tmp_path: Path,
) -> None:
    database = tmp_path / "status-projections.db"
    store = SQLiteStateStore(database)
    running_identity = RunIdentity(
        schema_version="2",
        subject_id="fixture:running-projection",
        fixture_hash="sha256:" + "1" * 64,
        producer_version="fixture-v1",
        retry_policy_version="retry-v1",
    )
    abandoned_identity = running_identity.model_copy(
        update={
            "subject_id": "fixture:abandoned-projection",
            "fixture_hash": "sha256:" + "2" * 64,
        }
    )
    try:
        store.create_run("failed-run", running_identity, "2026-07-19T00:00:00.000000Z")
        store.set_run_status(
            "failed-run",
            "failed",
            "2026-07-19T00:00:01.000000Z",
            SafeFailure(ErrorCode.STATE_OPERATION_FAILED),
        )
        failed = store.inspect_run("failed-run")
        assert failed["run"]["status"] == "failed"
        assert failed["run"]["error_code"] == ErrorCode.STATE_OPERATION_FAILED.value

        store.create_run("abandoned-run", abandoned_identity, "2026-07-19T00:00:02.000000Z")
        abandoned_input_hash = stage_input_hash(
            StageInput(
                schema_version=abandoned_identity.schema_version,
                execution_mode=ExecutionMode.DRY_RUN,
                subject_id=abandoned_identity.subject_id,
                stage=PipelineStage.SCOUT,
                previous_output_hash=None,
                fixture_hash=abandoned_identity.fixture_hash,
            )
        )
        abandoned_reusable = reusable_key_digest(
            subject_id=abandoned_identity.subject_id,
            stage=PipelineStage.SCOUT,
            input_hash=abandoned_input_hash,
            producer_version=abandoned_identity.producer_version,
            retry_policy_version=abandoned_identity.retry_policy_version,
        )
        store.start_attempt(
            StageAttempt(
                attempt_id="abandoned-run:scout:1",
                run_id="abandoned-run",
                subject_id=abandoned_identity.subject_id,
                stage=PipelineStage.SCOUT,
                stage_index=0,
                attempt_no=1,
                status=AttemptStatus.RUNNING,
                input_hash=abandoned_input_hash,
                producer_version="fixture-v1",
                retry_policy_version="retry-v1",
                reusable_key_digest=abandoned_reusable,
                started_at="2026-07-19T00:00:02.000000Z",
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
        )
        running = store.inspect_run("abandoned-run")
        assert running["run"]["status"] == "running"
        nullable_attempt_fields = {
            "finished_at",
            "prompt_version",
            "policy_version",
            "model_id",
            "request_id",
            "latency_ms",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "error_code",
            "error_summary",
        }
        assert nullable_attempt_fields <= set(running["attempts"][0])
        assert all(running["attempts"][0][field] is None for field in nullable_attempt_fields)
    finally:
        store.close()

    reopened = SQLiteStateStore(database)
    try:
        abandoned = reopened.inspect_run("abandoned-run")
        assert abandoned["run"]["status"] == "interrupted"
        assert abandoned["attempts"][0]["status"] == "abandoned"
        assert abandoned["attempts"][0]["retryable"] is True
        assert abandoned["attempts"][0]["error_code"] == (ErrorCode.PIPELINE_INTERRUPTED.value)
    finally:
        reopened.close()


def test_migration_rejects_oversized_output_before_manifest_creation(
    tmp_path: Path,
) -> None:
    copied = _copy_frozen(tmp_path)
    oversized = {str(index): "x" * MAX_STAGE_STRING_BYTES for index in range(4)}
    with _connect(copied) as connection:
        connection.execute(
            "UPDATE stage_results SET output_json = ? WHERE stage = 'scout'",
            (json.dumps(oversized, separators=(",", ":")),),
        )
        connection.commit()

    filesystem_events: list[str] = []
    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(copied, filesystem_seam=filesystem_events.append)
    assert failure.value.code is ErrorCode.STATE_SCHEMA_MIGRATION_ERROR
    assert all("manifest" not in event for event in filesystem_events)
    assert not copied.with_suffix(".manifests").exists()
    with _connect(copied) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


@pytest.mark.parametrize(
    "seam",
    ["before_state_file_fsync", "before_state_directory_fsync"],
)
def test_state_snapshot_sync_failure_restores_prior_bytes_and_requires_reopen(
    tmp_path: Path,
    seam: str,
) -> None:
    active = False

    def fail_selected(operation: str) -> None:
        if active and operation == seam:
            raise OSError("forced durability failure")

    database = tmp_path / f"snapshot-{seam}.db"
    store = SQLiteStateStore(database, filesystem_seam=fail_selected)
    before = database.read_bytes()
    active = True
    with pytest.raises(SafeFailure) as failure:
        store.create_run(
            "not-durable",
            RunIdentity(
                schema_version="2",
                subject_id="subject",
                fixture_hash="sha256:" + "1" * 64,
                producer_version="fixture-v1",
                retry_policy_version="retry-v1",
            ),
            "2026-07-19T00:00:00.000000Z",
        )
    assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    assert store.connection is None
    assert database.read_bytes() == before
    store.close()

    reopened = SQLiteStateStore(database)
    try:
        assert reopened.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        assert reopened.connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "seam",
    ["before_manifest_file_fsync", "before_manifest_directory_fsync"],
)
def test_manifest_sync_failure_never_advances_checkpoint(
    tmp_path: Path,
    seam: str,
) -> None:
    active = False

    def fail_selected(operation: str) -> None:
        if active and operation == seam:
            raise OSError("forced manifest durability failure")

    database = tmp_path / f"manifest-{seam}.db"
    store = SQLiteStateStore(database, filesystem_seam=fail_selected)
    active = True
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), tmp_path / "output"
            )
        assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
        assert store.connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0
        assert store.connection.execute("SELECT status FROM runs").fetchone()[0] == "interrupted"
    finally:
        store.close()


@pytest.mark.parametrize(
    "seam",
    [
        "before_publication_file_fsync",
        "before_publication_directory_fsync",
        "before_ancestor_directory_fsync",
    ],
)
def test_publication_sync_failure_prevents_terminal_transition(
    tmp_path: Path,
    seam: str,
) -> None:
    active = False

    def fail_selected(operation: str) -> None:
        if active and operation == seam:
            raise OSError("forced publication durability failure")

    store = SQLiteStateStore(tmp_path / f"publication-{seam}.db")
    active = True
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor(), filesystem_seam=fail_selected).run(
                load_fixture(APPROVED_FIXTURE), tmp_path / seam / "nested-output"
            )
        assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
        assert store.connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 9
        assert store.connection.execute("SELECT status FROM runs").fetchone()[0] == "running"
    finally:
        store.close()


def test_publication_is_directory_durable_before_terminal_state_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def observe(operation: str) -> None:
        events.append(operation)

    output = tmp_path / "publication-output"
    store = SQLiteStateStore(tmp_path / "publication-order.db")
    original_set_status = store.set_run_status

    def assert_durable_order(*args: object, **kwargs: object) -> None:
        if len(args) >= 2 and args[1] == "planned_not_published":
            assert events[-1] == "after_publication_durable"
            assert (output / "publication-plan.json").is_file()
        original_set_status(*args, **kwargs)

    monkeypatch.setattr(store, "set_run_status", assert_durable_order)
    try:
        summary = PipelineRunner(
            store,
            FixtureProcessor(),
            filesystem_seam=observe,
        ).run(load_fixture(APPROVED_FIXTURE), output)
        assert summary.status.value == "planned_not_published"
    finally:
        store.close()


def _killed_state_writer(database: str, output: str, control) -> None:
    """Reopen the store and block with a durable state temp before its rename."""

    tripped = False

    def block_at_first_rename(seam: str) -> None:
        nonlocal tripped
        if seam == "before_state_rename" and not tripped:
            tripped = True
            control.send("temp-created")
            control.recv()

    store = SQLiteStateStore(Path(database), filesystem_seam=block_at_first_rename)
    try:
        PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), Path(output)
        )
    finally:
        store.close()


def _hold_publication_lock(output: str, control) -> None:
    """Hold the publication operation lock until the parent releases it."""

    anchor = AnchoredDirectory.open(Path(output), create=True)
    try:
        descriptor = os.open(
            ".publication-plan.json.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=anchor.descriptor,
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            control.send("locked")
            control.recv()
        finally:
            os.close(descriptor)
    finally:
        anchor.close()


def test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay(
    tmp_path: Path,
) -> None:
    database = tmp_path / "killed-writer.db"
    state_temporary = tmp_path / ".killed-writer.db.tmp"
    subject = load_fixture(APPROVED_FIXTURE)
    store = SQLiteStateStore(database)
    try:
        with pytest.raises(SafeFailure) as interrupted:
            PipelineRunner(store, FixtureProcessor()).run(
                subject, tmp_path / "prefix-output", fail_after="generator"
            )
        assert interrupted.value.code is ErrorCode.PIPELINE_INTERRUPTED
        prefix = tuple(
            tuple(row)
            for row in store.connection.execute(
                """SELECT result_row_id, output_hash, manifest_hash
                   FROM stage_results ORDER BY stage_index"""
            )
        )
        assert len(prefix) == 6
    finally:
        store.close()
    assert not state_temporary.exists()

    context = multiprocessing.get_context("spawn")
    parent_control, child_control = context.Pipe()
    process = context.Process(
        target=_killed_state_writer,
        args=(str(database), str(tmp_path / "child-output"), child_control),
    )
    process.start()
    try:
        assert parent_control.recv() == "temp-created"
        assert state_temporary.is_file()
        process.kill()
        process.join(timeout=10)
        assert not process.is_alive()
        assert state_temporary.is_file()

        reopened = SQLiteStateStore(database)
        try:
            assert not state_temporary.exists()
            summary = PipelineRunner(reopened, FixtureProcessor()).run(
                subject, tmp_path / "recovered-output"
            )
            assert summary.status.value == "planned_not_published"
            assert summary.reused_stage_count == 6
            checkpoints = reopened.connection.execute(
                "SELECT stage FROM checkpoints ORDER BY stage_index"
            ).fetchall()
            assert [str(row[0]) for row in checkpoints] == [
                stage.value for stage in PipelineStage
            ]
            assert (
                tuple(
                    tuple(row)
                    for row in reopened.connection.execute(
                        """SELECT result_row_id, output_hash, manifest_hash
                           FROM stage_results
                           WHERE stage_index < 6 ORDER BY stage_index"""
                    )
                )
                == prefix
            )
            assert not state_temporary.exists()
        finally:
            reopened.close()
    finally:
        if process.is_alive():
            process.kill()
            process.join(timeout=10)
        parent_control.close()
        child_control.close()


def test_publication_stale_temp_recovers_under_retained_operation_lock(
    tmp_path: Path,
) -> None:
    output = tmp_path / "publication-recovery-output"
    plan = output / "publication-plan.json"
    temporary = output / ".publication-plan.json.tmp"
    lock = output / ".publication-plan.json.lock"
    store = SQLiteStateStore(tmp_path / "publication-recovery.db")
    try:
        first = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), output
        )
        assert first.status.value == "planned_not_published"
    finally:
        store.close()
    lock_identity = (os.lstat(lock).st_dev, os.lstat(lock).st_ino)
    temporary.write_bytes(b"crash-left-candidate")
    temporary.chmod(0o600)

    reopened = SQLiteStateStore(tmp_path / "publication-recovery.db")
    try:
        rerun = PipelineRunner(reopened, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), output
        )
        assert rerun.status.value == "planned_not_published"
        assert rerun.remote_writes_attempted == 0
    finally:
        reopened.close()

    payload = json.loads(plan.read_text())
    assert payload["remote_writes_attempted"] == 0
    assert not temporary.exists()
    assert (os.lstat(lock).st_dev, os.lstat(lock).st_ino) == lock_identity


def test_concurrent_publication_write_fails_closed_until_lock_holder_exits(
    tmp_path: Path,
) -> None:
    output = tmp_path / "contended-output"
    database = tmp_path / "contended.db"
    context = multiprocessing.get_context("spawn")
    parent_control, child_control = context.Pipe()
    process = context.Process(
        target=_hold_publication_lock,
        args=(str(output), child_control),
    )
    process.start()
    try:
        assert parent_control.recv() == "locked"
        store = SQLiteStateStore(database)
        try:
            with pytest.raises(SafeFailure) as failure:
                PipelineRunner(store, FixtureProcessor()).run(
                    load_fixture(APPROVED_FIXTURE), output
                )
            assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
            assert (
                store.connection.execute("SELECT status FROM runs").fetchone()[0]
                == "running"
            )
        finally:
            store.close()
        parent_control.send("release")
        process.join(timeout=10)
        assert process.exitcode == 0

        reopened = SQLiteStateStore(database)
        try:
            summary = PipelineRunner(reopened, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), output
            )
            assert summary.status.value == "planned_not_published"
            assert summary.remote_writes_attempted == 0
        finally:
            reopened.close()
    finally:
        if process.is_alive():
            process.kill()
            process.join(timeout=10)
        parent_control.close()
        child_control.close()


class _SemanticOwner:
    def __init__(self) -> None:
        self.records: list[tuple[str, int, str, str, int, str, str]] = []

    def record_semantic_attempt(
        self,
        *,
        run_id: str,
        repository_id: int,
        workflow_authority_digest: str,
        stage: str,
        attempt_no: int,
        status: str,
        recorded_at: str,
    ):
        key = (
            run_id,
            repository_id,
            workflow_authority_digest,
            stage,
            attempt_no,
        )
        existing = next((item for item in self.records if item[:5] == key), None)
        if existing is not None:
            if existing[5] == status:
                recorded_at = existing[6]
            else:
                self.records.remove(existing)
        value = (*key, status, recorded_at)
        if value not in self.records:
            self.records.append(value)
        return type("Record", (), {"recorded_at": recorded_at})()

    def export_owned_state(self):
        return type(
            "Export",
            (),
            {"export_digest": sha256_digest({"records": self.records})},
        )()


class _StaticOwner:
    def __init__(self, label: str) -> None:
        self.label = label

    def export_owned_state(self):
        return type(
            "Export",
            (),
            {"export_digest": sha256_digest({"owner": self.label})},
        )()


class _RecordingBarrier:
    def __init__(self, *, fail_on: set[int] | None = None) -> None:
        self.transitions = []
        self.fail_on = fail_on or set()

    def confirm(self, *, transition, pipeline_store, operations_store, publication_store):
        del pipeline_store, operations_store, publication_store
        ordinal = len(self.transitions) + 1
        self.transitions.append(transition)
        if ordinal in self.fail_on:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        return DurabilityReceipt.from_remote_verification(
            transition=transition,
            verified_state_head=f"{ordinal:040x}",
            state_root_digest=sha256_digest({"root": ordinal}),
            pipeline_database_digest=sha256_digest({"pipeline": ordinal}),
            operations_database_digest=sha256_digest({"operations": ordinal}),
            publication_database_digest=sha256_digest({"publication": ordinal}),
            pipeline_projection_digest=sha256_digest({"pipeline-projection": ordinal}),
            operations_projection_digest=sha256_digest(
                {"operations-projection": ordinal}
            ),
            publication_projection_digest=sha256_digest(
                {"publication-projection": ordinal}
            ),
        )


class _SemanticPhaseTwoProcessor:
    producer_version = "phase2-v1"

    def __init__(self, failures: list[SemanticProviderFailure]) -> None:
        self.failures = failures
        self.extractor_requests = 0

    def process(self, stage_input: StageInput, _context) -> StageOutcome:
        if stage_input.stage is PipelineStage.EXTRACTOR:
            self.extractor_requests += 1
            if self.failures:
                raise self.failures.pop(0)
            return StageOutcome(
                payload={"outcome": "no_workflow", "workflows": []},
                telemetry=None,
            )
        return StageOutcome(payload={"outcome": "accepted"}, telemetry=None)


def _semantic_guard(
    barrier: _RecordingBarrier,
    *,
    provider: str = "openai",
    reservation_hook=None,
) -> SemanticDurabilityGuard:
    return SemanticDurabilityGuard(
        barrier=barrier,
        operations_store=_SemanticOwner(),
        publication_store=_StaticOwner("publication"),
        repository_id=101,
        workflow_authority_digest=sha256_digest({"workflow": 101}),
        provider=provider,  # type: ignore[arg-type]
        expected_prior_state_head="a" * 40,
        expected_prior_root_digest=sha256_digest({"prior": 101}),
        reservation_hook=reservation_hook,
    )


def _repository_subject() -> RepositorySubject:
    return RepositorySubject(
        schema_version="1",
        subject_id="repo:example/semantic",
        repository="https://github.com/example/semantic",
    )


def test_extractor_reservation_is_remotely_durable_before_provider_request(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    processor = _SemanticPhaseTwoProcessor([])
    original_process = processor.process

    def process(stage_input: StageInput, context) -> StageOutcome:
        if stage_input.stage is PipelineStage.EXTRACTOR:
            events.append("provider")
        return original_process(stage_input, context)

    processor.process = process  # type: ignore[method-assign]

    def reserve(*, pipeline_store, run_id: str):
        del pipeline_store, run_id
        events.append("reserve")
        return SemanticReservationReceipt(
            reservation_digest=sha256_digest({"reservation": 101}),
            verified_state_head="b" * 40,
            state_root_digest=sha256_digest({"root": "reserved"}),
        )

    store = SQLiteStateStore(tmp_path / "extractor-reservation.sqlite3")
    try:
        runner = PipelineRunner(
            store,
            processor,
            semantic_durability=_semantic_guard(
                _RecordingBarrier(),
                reservation_hook=reserve,
            ),
        )
        runner.run(_repository_subject(), tmp_path / "out")
    finally:
        store.close()

    assert events == ["reserve", "provider"]


def test_failed_extractor_reservation_blocks_provider_request(tmp_path: Path) -> None:
    processor = _SemanticPhaseTwoProcessor([])

    def reserve(**_kwargs):
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)

    store = SQLiteStateStore(tmp_path / "extractor-reservation-fail.sqlite3")
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(
                store,
                processor,
                semantic_durability=_semantic_guard(
                    _RecordingBarrier(),
                    reservation_hook=reserve,
                ),
            ).run(_repository_subject(), tmp_path / "out")
    finally:
        store.close()

    assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    assert processor.extractor_requests == 0


def test_extractor_confirmed_retry_is_remotely_durable_before_next_request(
    tmp_path: Path,
) -> None:
    processor = _SemanticPhaseTwoProcessor(
        [
            SemanticProviderFailure(
                disposition=SemanticTransportDisposition.CONFIRMED_RETRYABLE,
                code="semantic_rate_limited",
            )
        ]
    )
    barrier = _RecordingBarrier()
    store = SQLiteStateStore(tmp_path / "extractor-confirmed.sqlite3")
    try:
        with pytest.raises(SafeFailure) as first:
            PipelineRunner(
                store, processor, semantic_durability=_semantic_guard(barrier)
            ).run(_repository_subject(), tmp_path / "confirmed-first")
        assert first.value.code is ErrorCode.STAGE_TRANSIENT_FAILURE
        PipelineRunner(
            store, processor, semantic_durability=_semantic_guard(barrier)
        ).run(_repository_subject(), tmp_path / "confirmed-second")
    finally:
        store.close()
    assert processor.extractor_requests == 2
    assert [item.transition for item in barrier.transitions] == [
        "attempt_started",
        "result_confirmed_retryable",
        "result_confirmed_retryable",
        "attempt_started",
        "result_decided",
    ]


@pytest.mark.parametrize("provider", ("openai", "deepseek"))
def test_extractor_unknown_is_consumed_once_and_never_replayed(
    tmp_path: Path,
    provider: str,
) -> None:
    processor = _SemanticPhaseTwoProcessor(
        [
            SemanticProviderFailure(
                disposition=SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN,
                code="semantic_provider_outcome_unknown",
            )
        ]
    )
    barrier = _RecordingBarrier()
    store = SQLiteStateStore(tmp_path / "extractor-unknown.sqlite3")
    try:
        with pytest.raises(SemanticProviderFailure):
            PipelineRunner(
                store,
                processor,
                semantic_durability=_semantic_guard(barrier, provider=provider),
            ).run(_repository_subject(), tmp_path / "unknown-first")
        with pytest.raises(SemanticProviderFailure) as resumed:
            PipelineRunner(
                store,
                processor,
                semantic_durability=_semantic_guard(barrier, provider=provider),
            ).run(_repository_subject(), tmp_path / "unknown-second")
        assert resumed.value.disposition is (
            SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN
        )
    finally:
        store.close()
    assert processor.extractor_requests == 1
    assert [item.transition for item in barrier.transitions] == [
        "attempt_started",
        "result_outcome_unknown",
        "result_outcome_unknown",
    ]
    assert {item.provider for item in barrier.transitions} == {provider}


def test_extractor_pre_request_barrier_failure_issues_zero_requests(
    tmp_path: Path,
) -> None:
    processor = _SemanticPhaseTwoProcessor([])
    barrier = _RecordingBarrier(fail_on={1})
    store = SQLiteStateStore(tmp_path / "extractor-pre-barrier.sqlite3")
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(
                store, processor, semantic_durability=_semantic_guard(barrier)
            ).run(_repository_subject(), tmp_path / "pre-barrier")
        assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
        with pytest.raises(SemanticProviderFailure):
            PipelineRunner(
                store, processor, semantic_durability=_semantic_guard(barrier)
            ).run(_repository_subject(), tmp_path / "pre-barrier-restart")
    finally:
        store.close()
    assert processor.extractor_requests == 0


def test_extractor_post_result_barrier_failure_reconfirms_without_replay(
    tmp_path: Path,
) -> None:
    processor = _SemanticPhaseTwoProcessor(
        [
            SemanticProviderFailure(
                disposition=SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN,
                code="semantic_provider_outcome_unknown",
            )
        ]
    )
    barrier = _RecordingBarrier(fail_on={2})
    store = SQLiteStateStore(tmp_path / "extractor-post-barrier.sqlite3")
    try:
        with pytest.raises(SafeFailure) as blocked:
            PipelineRunner(
                store, processor, semantic_durability=_semantic_guard(barrier)
            ).run(_repository_subject(), tmp_path / "post-barrier-first")
        assert blocked.value.code is ErrorCode.STATE_OPERATION_FAILED
        with pytest.raises(SemanticProviderFailure):
            PipelineRunner(
                store, processor, semantic_durability=_semantic_guard(barrier)
            ).run(_repository_subject(), tmp_path / "post-barrier-second")
    finally:
        store.close()
    assert processor.extractor_requests == 1
    assert [item.transition for item in barrier.transitions] == [
        "attempt_started",
        "result_outcome_unknown",
        "result_outcome_unknown",
    ]
