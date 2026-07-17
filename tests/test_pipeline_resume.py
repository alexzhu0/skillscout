"""Migration, durable-manifest and no-replay evidence for schema v2."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.enums import PipelineStage
from skillscout.domain.models import StageInput

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
    finally:
        store.close()
