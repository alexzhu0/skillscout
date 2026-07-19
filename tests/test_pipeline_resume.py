"""Migration, durable-manifest and no-replay evidence for schema v2."""

from __future__ import annotations

import hashlib
import inspect
import json
import shutil
import sqlite3
from pathlib import Path
from typing import get_type_hints

import pytest

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import PipelineRunner, RetryPolicy
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode, SafeFailure, StateStore
from skillscout.domain.canonical import (
    reusable_key_digest,
    sha256_digest,
    stage_input_hash,
)
from skillscout.domain.enums import AttemptStatus, ExecutionMode, PipelineStage
from skillscout.domain.models import (
    MAX_STAGE_STRING_BYTES,
    RunIdentity,
    RunRecord,
    StageAttempt,
    StageInput,
    VerifiedRunChain,
)

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
