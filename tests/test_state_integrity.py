"""Fail-closed integrity checks for SQLite, manifests and local output targets."""

from __future__ import annotations

import multiprocessing
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
import skillscout.adapters.state as state_adapter
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.canonical import make_result_row_id
from skillscout.domain.enums import PipelineStage, RunStatus
from skillscout.domain.models import RunIdentity

APPROVED_FIXTURE = Path(__file__).parent / "fixtures" / "pipeline" / "approved.json"
FROZEN_DATABASE = Path(__file__).parent / "fixtures" / "state" / "v1-cli.db"


def _run_identity(subject_id: str) -> RunIdentity:
    return RunIdentity(
        schema_version="2",
        subject_id=subject_id,
        fixture_hash="sha256:" + "1" * 64,
        producer_version="fixture-v1",
        retry_policy_version="retry-v1",
    )


def _hold_state_lock(database: str, control) -> None:
    store = SQLiteStateStore(Path(database))
    control.send("locked")
    control.recv()
    store.close()


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _run_interrupted(database: Path, output: Path) -> str:
    store = SQLiteStateStore(database)
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), output, fail_after="generator"
            )
        assert failure.value.code is ErrorCode.PIPELINE_INTERRUPTED
        return str(store.connection.execute("SELECT run_id FROM runs").fetchone()[0])
    finally:
        store.close()


def _checkpoint_facts(database: Path) -> list[tuple[object, ...]]:
    with _connect(database) as connection:
        return [
            tuple(row)
            for row in connection.execute(
                "SELECT stage, stage_index, result_id, output_hash, manifest_hash "
                "FROM checkpoints ORDER BY stage_index"
            )
        ]


def test_manifest_paths_use_closed_stage_and_bare_lowercase_hash(tmp_path: Path) -> None:
    database = tmp_path / "ledger.db"
    store = SQLiteStateStore(database)
    try:
        PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "out"
        )
        rows = store.connection.execute(
            "SELECT stage, manifest_hash, manifest_path FROM stage_results ORDER BY stage_index"
        ).fetchall()
    finally:
        store.close()

    for row in rows:
        digest = str(row["manifest_hash"])
        expected = database.with_suffix(".manifests") / str(row["stage"]) / (
            digest.removeprefix("sha256:") + ".json"
        )
        assert Path(str(row["manifest_path"])) == Path(str(row["stage"])) / (
            digest.removeprefix("sha256:") + ".json"
        )
        assert expected.is_file()


@pytest.mark.parametrize("damage", ["missing", "tampered"])
def test_missing_or_tampered_manifest_never_advances_checkpoint(
    tmp_path: Path, damage: str
) -> None:
    database = tmp_path / f"{damage}.db"
    _run_interrupted(database, tmp_path / "first")
    before = _checkpoint_facts(database)
    with _connect(database) as connection:
        path = database.with_suffix(".manifests") / str(
            connection.execute(
                "SELECT manifest_path FROM stage_results ORDER BY stage_index LIMIT 1"
            ).fetchone()[0]
        )
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b"tampered")

    store = SQLiteStateStore(database)
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), tmp_path / "resume"
            )
        assert failure.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    finally:
        store.close()
    assert _checkpoint_facts(database) == before


def test_stored_manifest_path_cannot_redirect_verified_reads(tmp_path: Path) -> None:
    database = tmp_path / "redirect.db"
    _run_interrupted(database, tmp_path / "first")
    with _connect(database) as connection:
        row = connection.execute(
            "SELECT result_id, manifest_path FROM stage_results ORDER BY stage_index LIMIT 1"
        ).fetchone()
        external = tmp_path / "attacker-selected.json"
        shutil.copy2(database.with_suffix(".manifests") / str(row["manifest_path"]), external)
        connection.execute(
            "UPDATE stage_results SET manifest_path = ? WHERE result_id = ?",
            (str(external), row["result_id"]),
        )
        connection.execute(
            "UPDATE checkpoints SET manifest_path = ? WHERE result_id = ?",
            (str(external), row["result_id"]),
        )
        connection.commit()
    before = _checkpoint_facts(database)

    store = SQLiteStateStore(database)
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), tmp_path / "resume"
            )
        assert failure.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    finally:
        store.close()
    assert _checkpoint_facts(database) == before


@pytest.mark.parametrize(
    ("column", "value"), [("schema_version", "99"), ("producer_version", "unknown-v9")]
)
def test_unsupported_persisted_identity_fails_closed(
    tmp_path: Path, column: str, value: str
) -> None:
    database = tmp_path / f"unsupported-{column}.db"
    store = SQLiteStateStore(database)
    try:
        summary = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "out"
        )
    finally:
        store.close()
    with _connect(database) as connection:
        connection.execute(
            f"UPDATE stage_results SET {column} = ? WHERE stage = 'scout'", (value,)
        )
        connection.commit()

    store = SQLiteStateStore(database)
    try:
        with pytest.raises(SafeFailure) as failure:
            store.verify_completed_results(summary.run_id, 9)
        assert failure.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    finally:
        store.close()


def test_illegal_terminal_run_transition_is_rejected_without_mutation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "terminal.db"
    store = SQLiteStateStore(database)
    try:
        summary = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "out"
        )
        before = dict(
            store.connection.execute(
                "SELECT status, updated_at, error_code, error_summary FROM runs WHERE run_id = ?",
                (summary.run_id,),
            ).fetchone()
        )
        with pytest.raises(SafeFailure) as failure:
            store.set_run_status(summary.run_id, RunStatus.RUNNING.value, "hostile-time")
        assert failure.value.code is ErrorCode.STATE_INTEGRITY_ERROR
        after = dict(
            store.connection.execute(
                "SELECT status, updated_at, error_code, error_summary FROM runs WHERE run_id = ?",
                (summary.run_id,),
            ).fetchone()
        )
        assert after == before
    finally:
        store.close()


def test_symlinked_state_target_is_rejected_without_touching_target(tmp_path: Path) -> None:
    target = tmp_path / "target.db"
    SQLiteStateStore(target).close()
    before = target.read_bytes()
    link = tmp_path / "state.db"
    link.symlink_to(target)
    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(link)
    assert failure.value.code is ErrorCode.STATE_SCHEMA_INCOMPATIBLE
    assert target.read_bytes() == before


def test_symlinked_manifest_root_is_rejected_without_external_write(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    store = SQLiteStateStore(database)
    external = tmp_path / "external-manifests"
    external.mkdir()
    database.with_suffix(".manifests").symlink_to(external, target_is_directory=True)
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), tmp_path / "out"
            )
        assert failure.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    finally:
        store.close()
    assert list(external.iterdir()) == []


def test_symlinked_output_directory_is_rejected_without_external_write(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external-output"
    external.mkdir()
    output = tmp_path / "output"
    output.symlink_to(external, target_is_directory=True)
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), output
            )
        assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    finally:
        store.close()
    assert list(external.iterdir()) == []


def test_state_uses_private_memory_sqlite_and_one_reusable_live_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened_databases: list[object] = []
    original_connect = state_adapter.sqlite3.connect

    def observed_connect(database: object, *args: object, **kwargs: object):
        opened_databases.append(database)
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(state_adapter.sqlite3, "connect", observed_connect)
    database = tmp_path / "serialized.db"
    first = SQLiteStateStore(database)
    lock = tmp_path / ".serialized.db.lock"
    first_lock_identity = (os.lstat(lock).st_dev, os.lstat(lock).st_ino)
    try:
        first.create_run(
            "run-1", _run_identity("subject-1"), "2026-07-19T00:00:00.000000Z"
        )
        with pytest.raises(SafeFailure) as failure:
            SQLiteStateStore(database)
        assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    finally:
        first.close()

    second = SQLiteStateStore(database)
    try:
        assert second.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        assert (os.lstat(lock).st_dev, os.lstat(lock).st_ino) == first_lock_identity
    finally:
        second.close()

    assert opened_databases
    assert set(opened_databases) == {":memory:"}


def test_parent_swap_after_state_anchor_cannot_redirect_state_or_manifests(
    tmp_path: Path,
) -> None:
    visible_parent = tmp_path / "visible"
    anchored_parent = tmp_path / "anchored"
    attacker_parent = tmp_path / "attacker"
    visible_parent.mkdir(mode=0o700)
    attacker_parent.mkdir(mode=0o700)
    attacker_canary = attacker_parent / "canary"
    attacker_canary.write_bytes(b"unchanged")
    swapped = False

    def swap_parent(seam: str) -> None:
        nonlocal swapped
        if seam != "after_state_parent_anchor" or swapped:
            return
        visible_parent.rename(anchored_parent)
        visible_parent.symlink_to(attacker_parent, target_is_directory=True)
        swapped = True

    store = SQLiteStateStore(visible_parent / "state.db", filesystem_seam=swap_parent)
    try:
        PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), anchored_parent / "output"
        )
    finally:
        store.close()

    assert swapped is True
    assert (anchored_parent / "state.db").is_file()
    assert any((anchored_parent / "state.manifests").rglob("*.json"))
    assert attacker_canary.read_bytes() == b"unchanged"
    assert sorted(path.name for path in attacker_parent.iterdir()) == ["canary"]


def test_oversized_serialized_state_fails_before_sqlite_deserialize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "oversized.db"
    with database.open("wb") as stream:
        stream.truncate(67_108_864 + 1)
    before = os.lstat(database)
    connect_calls: list[object] = []

    def reject_connect(database_name: object, *_args: object, **_kwargs: object) -> None:
        connect_calls.append(database_name)
        raise AssertionError("oversized bytes reached sqlite")

    monkeypatch.setattr(state_adapter.sqlite3, "connect", reject_connect)

    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(database)

    assert failure.value.code is ErrorCode.STATE_SCHEMA_INCOMPATIBLE
    assert connect_calls == []
    after = os.lstat(database)
    assert (after.st_dev, after.st_ino, after.st_size) == (
        before.st_dev,
        before.st_ino,
        before.st_size,
    )


def test_killed_lock_owner_releases_flock_without_recreating_lock_inode(
    tmp_path: Path,
) -> None:
    database = tmp_path / "killed.db"
    lock = tmp_path / ".killed.db.lock"
    context = multiprocessing.get_context("spawn")
    parent_control, child_control = context.Pipe()
    process = context.Process(
        target=_hold_state_lock,
        args=(str(database), child_control),
    )
    process.start()
    try:
        assert parent_control.recv() == "locked"
        identity = (os.lstat(lock).st_dev, os.lstat(lock).st_ino)
        with pytest.raises(SafeFailure) as failure:
            SQLiteStateStore(database)
        assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
        process.kill()
        process.join(timeout=10)
        assert not process.is_alive()

        reopened = SQLiteStateStore(database)
        try:
            assert reopened.connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert (os.lstat(lock).st_dev, os.lstat(lock).st_ino) == identity
        finally:
            reopened.close()
    finally:
        if process.is_alive():
            process.kill()
            process.join(timeout=10)
        parent_control.close()
        child_control.close()


def test_parent_swap_during_failed_snapshot_cleanup_never_touches_attacker(
    tmp_path: Path,
) -> None:
    visible_parent = tmp_path / "visible-failure"
    anchored_parent = tmp_path / "anchored-failure"
    attacker_parent = tmp_path / "attacker-failure"
    visible_parent.mkdir(mode=0o700)
    attacker_parent.mkdir(mode=0o700)
    attacker_canary = attacker_parent / "canary"
    attacker_canary.write_bytes(b"attacker-unchanged")
    swapped = False
    fail_persist = False

    def swap_then_fail(seam: str) -> None:
        nonlocal swapped
        if seam == "after_state_parent_anchor" and not swapped:
            visible_parent.rename(anchored_parent)
            visible_parent.symlink_to(attacker_parent, target_is_directory=True)
            swapped = True
        if fail_persist and seam == "before_state_directory_fsync":
            raise OSError("forced post-rename sync failure")

    store = SQLiteStateStore(
        visible_parent / "state.db",
        filesystem_seam=swap_then_fail,
    )
    prior = (anchored_parent / "state.db").read_bytes()
    fail_persist = True
    with pytest.raises(SafeFailure) as failure:
        store.create_run(
            "not-durable", _run_identity("subject"), "2026-07-19T00:00:00.000000Z"
        )
    assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    store.close()

    assert (anchored_parent / "state.db").read_bytes() == prior
    assert attacker_canary.read_bytes() == b"attacker-unchanged"
    assert sorted(path.name for path in attacker_parent.iterdir()) == ["canary"]


def test_semantic_result_twins_use_distinct_run_scoped_rows(tmp_path: Path) -> None:
    database = tmp_path / "semantic-twins.db"
    store = SQLiteStateStore(database)
    try:
        first = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "first"
        )
        second = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "second"
        )
        rows = store.connection.execute(
            """SELECT run_id, stage, result_row_id, result_id
               FROM stage_results ORDER BY stage_index, run_id"""
        ).fetchall()
        checkpoints = store.connection.execute(
            """SELECT c.run_id, c.stage, c.result_row_id, r.run_id AS result_run_id,
                      c.result_id, r.result_id AS stored_result_id
               FROM checkpoints c
               JOIN stage_results r ON r.result_row_id = c.result_row_id
               ORDER BY c.stage_index, c.run_id"""
        ).fetchall()
    finally:
        store.close()

    assert first.run_id != second.run_id
    assert len(rows) == 18
    for stage in PipelineStage:
        twins = [row for row in rows if row["stage"] == stage.value]
        assert len(twins) == 2
        assert twins[0]["result_id"] == twins[1]["result_id"]
        assert twins[0]["result_row_id"] != twins[1]["result_row_id"]
        assert {
            row["result_row_id"] for row in twins
        } == {
            make_result_row_id(run_id=first.run_id, stage=stage),
            make_result_row_id(run_id=second.run_id, stage=stage),
        }
    assert all(row["run_id"] == row["result_run_id"] for row in checkpoints)
    assert all(row["result_id"] == row["stored_result_id"] for row in checkpoints)


def test_result_row_constraints_reject_cross_run_checkpoint_and_duplicates(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "constraints.db")
    try:
        first = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "out"
        )
        second = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "out-second"
        )
        foreign_keys = store.connection.execute(
            "PRAGMA foreign_key_list(checkpoints)"
        ).fetchall()
        assert any(
            row["table"] == "stage_results"
            and row["from"] == "result_row_id"
            and row["to"] == "result_row_id"
            for row in foreign_keys
        )

        semantic_twin = store.connection.execute(
            """SELECT result_row_id FROM stage_results
               WHERE run_id = ? AND stage = 'scout'""",
            (second.run_id,),
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            store.connection.execute(
                """UPDATE checkpoints SET result_row_id = ?
                   WHERE run_id = ? AND stage = 'scout'""",
                (semantic_twin["result_row_id"], first.run_id),
            )

        result = store.connection.execute(
            "SELECT * FROM stage_results WHERE run_id = ? AND stage = 'scout'",
            (first.run_id,),
        ).fetchone()
        attempt = store.connection.execute(
            "SELECT * FROM stage_attempts WHERE run_id = ? AND stage = 'scout'",
            (first.run_id,),
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            store.connection.execute(
                """INSERT INTO stage_results
                   SELECT ?, result_id, attempt_id, run_id, schema_version, subject_id,
                          stage, stage_index, output_json, output_hash, producer_version,
                          manifest_hash, manifest_path, created_at
                   FROM stage_results WHERE result_row_id = ?""",
                ("sha256:" + "a" * 64, result["result_row_id"]),
            )
        with pytest.raises(sqlite3.IntegrityError):
            store.connection.execute(
                """INSERT INTO stage_results
                   SELECT ?, result_id, ?, run_id, schema_version, subject_id,
                          stage, stage_index, output_json, output_hash, producer_version,
                          manifest_hash, manifest_path, created_at
                   FROM stage_results WHERE result_row_id = ?""",
                (
                    "sha256:" + "b" * 64,
                    attempt["attempt_id"],
                    result["result_row_id"],
                ),
            )
    finally:
        store.close()


def test_v1_migration_preserves_semantic_results_and_adds_row_identity(
    tmp_path: Path,
) -> None:
    database = tmp_path / "migrated.db"
    shutil.copy2(FROZEN_DATABASE, database)
    with _connect(database) as legacy:
        legacy_results = [
            str(row[0])
            for row in legacy.execute(
                "SELECT result_id FROM stage_results ORDER BY stage_index"
            )
        ]

    store = SQLiteStateStore(database)
    try:
        migrated = store.connection.execute(
            """SELECT run_id, stage, result_row_id, result_id
               FROM stage_results ORDER BY stage_index"""
        ).fetchall()
        assert [str(row["result_id"]) for row in migrated] == legacy_results
        assert all(
            row["result_row_id"]
            == make_result_row_id(
                run_id=str(row["run_id"]), stage=PipelineStage(str(row["stage"]))
            )
            for row in migrated
        )
        assert store.connection.execute("PRAGMA foreign_key_check").fetchone() is None
    finally:
        store.close()
