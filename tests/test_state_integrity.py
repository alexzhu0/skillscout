"""Fail-closed integrity checks for SQLite, manifests and local output targets."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.enums import RunStatus

APPROVED_FIXTURE = Path(__file__).parent / "fixtures" / "pipeline" / "approved.json"


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
