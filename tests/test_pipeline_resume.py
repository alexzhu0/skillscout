"""Migration, durable-manifest and no-replay evidence for schema v2."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

import skillscout.adapters.state as state_adapter
from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import PipelineRunner, RetryPolicy
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode, SafeFailure
from skillscout.domain.canonical import (
    reusable_key_digest,
    sha256_digest,
    stage_input_hash,
)
from skillscout.domain.enums import AttemptStatus, ExecutionMode, PipelineStage
from skillscout.domain.models import MAX_STAGE_STRING_BYTES, StageAttempt, StageInput

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
    return copied


def test_frozen_fixture_provenance_is_real_interrupted_schema_v1() -> None:
    provenance = json.loads(FROZEN_PROVENANCE.read_text())
    assert hashlib.sha256(FROZEN_DATABASE.read_bytes()).hexdigest() == (
        provenance["database_sha256"]
    )
    assert "skillscout dry-run" in provenance["command"]
    assert "--fail-after generator" in provenance["command"]
    with _connect(FROZEN_DATABASE) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert dict(connection.execute("SELECT run_id, status FROM runs").fetchone()) == {
            "run_id": provenance["run_id"],
            "status": "interrupted",
        }
        assert connection.execute(
            "SELECT COUNT(*) FROM stage_attempts WHERE stage = 'validators'"
        ).fetchone()[0] == 0


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
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        summary = PipelineRunner(store, CanaryProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "output"
        )
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

    assert hashlib.sha256(FROZEN_DATABASE.read_bytes()).hexdigest() == (
        provenance["database_sha256"]
    )


@pytest.mark.parametrize("seam", ["after_schema", "after_copy", "after_validation"])
def test_forced_migration_failure_rolls_back_to_intact_v1(
    tmp_path: Path, seam: str
) -> None:
    copied = _copy_frozen(tmp_path)
    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(copied, migration_fail_at=seam)
    assert failure.value.code is ErrorCode.STATE_SCHEMA_MIGRATION_ERROR

    with _connect(copied) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert tables == {"runs", "stage_attempts", "stage_results", "checkpoints"}
        assert connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 6
    assert not copied.with_suffix(".manifests").exists()


def test_missing_database_creates_v2_and_existing_v2_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "new.db"
    first = SQLiteStateStore(database)
    first.close()
    with _connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"runs", "stage_attempts", "stage_results", "checkpoints"} <= tables
    second = SQLiteStateStore(database)
    second.close()


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
    store.create_run(run_id, subject.subject_id, "2026-07-17T00:00:00.000000Z", "2")
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
        summary = PipelineRunner(
            budget_store, success, retry_policy=new_policy
        ).run(changed_subject, tmp_path / "new-output")
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
            PipelineRunner(
                checkpoint_store, first_processor, retry_policy=old_policy
            ).run(original, tmp_path / "checkpoint-old", fail_after="scout")
        old_run_id = checkpoint_store.connection.execute("SELECT run_id FROM runs").fetchone()[0]
        second_processor = VersionedSuccess(new_processor_version)
        summary = PipelineRunner(
            checkpoint_store, second_processor, retry_policy=new_policy
        ).run(changed_subject, tmp_path / "checkpoint-new")
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
    monkeypatch: pytest.MonkeyPatch,
    output: dict[str, object],
) -> None:
    subject = load_fixture(APPROVED_FIXTURE)

    class InvalidOutputProcessor(FixtureProcessor):
        def process(self, stage_input: StageInput) -> dict[str, object]:
            return output

    opened_paths: list[object] = []
    original_open = state_adapter.os.open

    def observe_open(path: object, *args: object, **kwargs: object) -> int:
        opened_paths.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(state_adapter.os, "open", observe_open)
    database = tmp_path / "invalid-output.db"
    store = SQLiteStateStore(database)
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, InvalidOutputProcessor()).run(
                subject, tmp_path / "output"
            )
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
        assert opened_paths == []
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
    finally:
        store.close()


def test_migration_rejects_oversized_output_before_manifest_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copied = _copy_frozen(tmp_path)
    oversized = {str(index): "x" * MAX_STAGE_STRING_BYTES for index in range(4)}
    with _connect(copied) as connection:
        connection.execute(
            "UPDATE stage_results SET output_json = ? WHERE stage = 'scout'",
            (json.dumps(oversized, separators=(",", ":")),),
        )
        connection.commit()

    opened_paths: list[object] = []
    original_open = state_adapter.os.open

    def observe_open(path: object, *args: object, **kwargs: object) -> int:
        opened_paths.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(state_adapter.os, "open", observe_open)
    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(copied)
    assert failure.value.code is ErrorCode.STATE_SCHEMA_MIGRATION_ERROR
    assert opened_paths == []
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
        store.create_run("not-durable", "subject", "2026-07-19T00:00:00.000000Z")
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
