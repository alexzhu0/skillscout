"""Fail-closed integrity checks for SQLite, manifests and local output targets."""

from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import sqlite3
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
import skillscout.adapters.localfs as localfs_adapter
import skillscout.adapters.state as state_adapter
from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode, SafeFailure
from skillscout.domain.canonical import (
    canonical_json_bytes,
    make_result_id,
    make_result_row_id,
    resume_event_hash,
    reusable_key_digest,
    sha256_digest,
    stage_manifest_hash,
)
from skillscout.domain.enums import PipelineStage, RunStatus
from skillscout.domain.models import ResumeEvent, RunIdentity, StageEnvelope

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


def _schema_fingerprint(path: Path) -> tuple[tuple[object, ...], ...]:
    with _connect(path) as connection:
        return tuple(
            tuple(row)
            for row in connection.execute(
                """SELECT type, name, tbl_name, sql FROM sqlite_master
                   WHERE type IN ('table', 'index') ORDER BY type, name"""
            )
        )


def _write_schema_v2_variant(path: Path, variant: str) -> None:
    statements = list(state_adapter._schema_statements())

    def replace(prefix: str, old: str, new: str) -> None:
        index = next(
            position
            for position, statement in enumerate(statements)
            if statement.startswith(prefix)
        )
        assert old in statements[index]
        statements[index] = statements[index].replace(old, new, 1)

    if variant == "extra_table":
        statements.append("CREATE TABLE shadow_ledger (value TEXT)")
    elif variant == "extra_column":
        replace(
            "CREATE TABLE runs",
            "run_id TEXT PRIMARY KEY,",
            "run_id TEXT PRIMARY KEY, shadow_value TEXT,",
        )
    elif variant == "changed_type":
        replace(
            "CREATE TABLE runs",
            "reused_stage_count INTEGER NOT NULL DEFAULT 0",
            "reused_stage_count TEXT NOT NULL DEFAULT 0",
        )
    elif variant == "changed_nullability":
        replace(
            "CREATE TABLE runs",
            "subject_id TEXT NOT NULL,",
            "subject_id TEXT,",
        )
    elif variant == "changed_default":
        replace(
            "CREATE TABLE runs",
            "reused_stage_count INTEGER NOT NULL DEFAULT 0",
            "reused_stage_count INTEGER NOT NULL DEFAULT 1",
        )
    elif variant == "missing_check":
        replace(
            "CREATE TABLE runs",
            "execution_mode TEXT NOT NULL CHECK (execution_mode = 'dry_run'),",
            "execution_mode TEXT NOT NULL,",
        )
    elif variant == "missing_unique":
        replace(
            "CREATE TABLE stage_attempts",
            ",\n            UNIQUE (run_id, subject_id, stage, attempt_no)",
            "",
        )
    elif variant == "missing_foreign_key":
        replace(
            "CREATE TABLE stage_attempts",
            "run_id TEXT NOT NULL REFERENCES runs(run_id),",
            "run_id TEXT NOT NULL,",
        )
    elif variant == "missing_index":
        statements = [
            statement
            for statement in statements
            if not statement.startswith("CREATE INDEX idx_results_semantic")
        ]
    elif variant == "changed_index_order":
        replace(
            "CREATE INDEX idx_runs_resumable_identity",
            "schema_version, subject_id, fixture_hash, producer_version,",
            "subject_id, schema_version, fixture_hash, producer_version,",
        )
    elif variant == "unique_index":
        replace(
            "CREATE INDEX idx_results_semantic",
            "CREATE INDEX",
            "CREATE UNIQUE INDEX",
        )
    elif variant == "partial_index":
        replace(
            "CREATE INDEX idx_results_semantic",
            "(result_id)",
            "(result_id) WHERE result_id IS NOT NULL",
        )
    elif variant == "extra_index":
        statements.append("CREATE INDEX idx_shadow_status ON runs(status)")
    else:
        raise AssertionError(f"unknown schema variant: {variant}")

    with _connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in statements:
            connection.execute(statement)
        connection.execute(f"PRAGMA user_version = {state_adapter.SCHEMA_VERSION}")
        connection.commit()


def _write_pre_event_schema_v2(path: Path, *, reused_stage_count: int = 0) -> bytes:
    with _connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in state_adapter._schema_v2_statements():
            connection.execute(statement)
        connection.execute(
            """INSERT INTO runs
               (run_id, schema_version, subject_id, fixture_hash, producer_version,
                retry_policy_version, identity_state, execution_mode, status,
                created_at, updated_at, error_code, error_summary, reused_stage_count)
               VALUES ('pre-event-run', '2', 'fixture:pre-event', ?, 'fixture-v1',
                       'retry-v1', 'bound', 'dry_run', 'running', ?, ?, NULL, NULL, ?)""",
            (
                "sha256:" + "1" * 64,
                "2026-07-19T00:00:00.000000Z",
                "2026-07-19T00:00:00.000000Z",
                reused_stage_count,
            ),
        )
        connection.execute("PRAGMA user_version = 2")
        connection.commit()
    path.chmod(0o600)
    return path.read_bytes()


def _resume_event(**updates: object) -> ResumeEvent:
    values: dict[str, object] = {
        "run_id": "resume-run",
        "event_index": 0,
        "prior_event_hash": None,
        "reused_stage_count": 0,
        "checkpoint_stage": None,
        "checkpoint_result_row_id": None,
        "checkpoint_manifest_hash": None,
        "recorded_at": "2026-07-19T00:00:00.000000Z",
    }
    values.update(updates)
    event_hash = resume_event_hash(**values)
    return ResumeEvent.model_validate({"event_hash": event_hash, **values})


def test_resume_event_contract_accepts_only_genesis_zero_and_positive_prefix_shapes() -> None:
    genesis = _resume_event()
    zero_prefix = _resume_event(
        event_index=1,
        prior_event_hash=genesis.event_hash,
        recorded_at="2026-07-19T00:00:01.000000Z",
    )
    positive_prefix = _resume_event(
        event_index=2,
        prior_event_hash=zero_prefix.event_hash,
        reused_stage_count=6,
        checkpoint_stage=PipelineStage.GENERATOR,
        checkpoint_result_row_id="sha256:" + "2" * 64,
        checkpoint_manifest_hash="sha256:" + "3" * 64,
        recorded_at="2026-07-19T00:00:02.000000Z",
    )

    assert genesis.event_index == 0 and genesis.prior_event_hash is None
    assert zero_prefix.reused_stage_count == 0
    assert positive_prefix.checkpoint_stage is PipelineStage.GENERATOR
    assert positive_prefix.reused_stage_count == positive_prefix.checkpoint_stage_index + 1
    assert resume_event_hash(
        **positive_prefix.model_dump(mode="json", exclude={"event_hash"})
    ) == positive_prefix.event_hash


@pytest.mark.parametrize(
    "updates",
    [
        {"event_index": 0, "prior_event_hash": "sha256:" + "1" * 64},
        {"event_index": 0, "reused_stage_count": 1},
        {"event_index": 1, "prior_event_hash": None},
        {
            "event_index": 1,
            "prior_event_hash": "sha256:" + "1" * 64,
            "checkpoint_stage": PipelineStage.SCOUT,
        },
        {
            "event_index": 1,
            "prior_event_hash": "sha256:" + "1" * 64,
            "reused_stage_count": 2,
            "checkpoint_stage": PipelineStage.SCOUT,
            "checkpoint_result_row_id": "sha256:" + "2" * 64,
            "checkpoint_manifest_hash": "sha256:" + "3" * 64,
        },
    ],
)
def test_resume_event_contract_rejects_invalid_shape(updates: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _resume_event(**updates)


def test_resume_event_contract_rejects_unknown_fields_and_inconsistent_hash() -> None:
    event = _resume_event()
    values = event.model_dump(mode="json")
    values["unknown"] = "forbidden"
    with pytest.raises(ValueError):
        ResumeEvent.model_validate(values)
    values.pop("unknown")
    values["event_hash"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError):
        ResumeEvent.model_validate(values)


def test_fresh_run_creation_atomically_heads_one_genesis_event(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "genesis.db")
    created_at = "2026-07-19T00:00:00.000000Z"
    try:
        store.create_run("genesis-run", _run_identity("genesis-subject"), created_at)
        run = store.connection.execute(
            """SELECT latest_resume_event_hash, reused_stage_count
               FROM runs WHERE run_id = 'genesis-run'"""
        ).fetchone()
        events = store.connection.execute(
            "SELECT * FROM resume_events WHERE run_id = 'genesis-run'"
        ).fetchall()
        attempts = store.connection.execute(
            "SELECT COUNT(*) FROM stage_attempts WHERE run_id = 'genesis-run'"
        ).fetchone()[0]
    finally:
        store.close()

    assert len(events) == 1
    event = ResumeEvent.model_validate(dict(events[0]))
    assert event == _resume_event(run_id="genesis-run", recorded_at=created_at)
    assert tuple(run) == (event.event_hash, 0)
    assert attempts == 0


def test_zero_reuse_v2_migrates_to_schema_v3_genesis_only(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh-v3.db"
    SQLiteStateStore(fresh).close()
    migrated = tmp_path / "zero-v2.db"
    _write_pre_event_schema_v2(migrated)

    SQLiteStateStore(migrated).close()

    assert _schema_fingerprint(migrated) == _schema_fingerprint(fresh)
    with _connect(migrated) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        event = ResumeEvent.model_validate(
            dict(connection.execute("SELECT * FROM resume_events").fetchone())
        )
        run = connection.execute(
            "SELECT latest_resume_event_hash, reused_stage_count FROM runs"
        ).fetchone()
    assert event.event_index == 0
    assert event.reused_stage_count == 0
    assert tuple(run) == (event.event_hash, 0)


def test_unattested_nonzero_v2_reuse_is_rejected_without_mutation(tmp_path: Path) -> None:
    database = tmp_path / "nonzero-v2.db"
    before = _write_pre_event_schema_v2(database, reused_stage_count=1)

    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(database)

    assert failure.value.code is ErrorCode.STATE_SCHEMA_MIGRATION_ERROR
    assert database.read_bytes() == before
    assert not database.with_suffix(".manifests").exists()


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


def _run_interrupted_in_store(store: SQLiteStateStore, output: Path) -> str:
    with pytest.raises(SafeFailure) as failure:
        PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), output, fail_after="generator"
        )
    assert failure.value.code is ErrorCode.PIPELINE_INTERRUPTED
    return str(store.connection.execute("SELECT run_id FROM runs").fetchone()[0])


def _checkpoint_facts(database: Path) -> list[tuple[object, ...]]:
    with _connect(database) as connection:
        return [
            tuple(row)
            for row in connection.execute(
                "SELECT stage, stage_index, result_id, output_hash, manifest_hash "
                "FROM checkpoints ORDER BY stage_index"
            )
        ]


def _coherently_rewrite_manifest(
    store: SQLiteStateStore,
    stage: PipelineStage,
    **updates: object,
) -> tuple[str, str]:
    """Rewrite one envelope and every attacker-controlled manifest locator."""

    row = store.connection.execute(
        "SELECT * FROM stage_results WHERE stage = ?", (stage.value,)
    ).fetchone()
    assert row is not None
    old_path = store.manifest_root / str(row["manifest_path"])
    payload = json.loads(old_path.read_bytes())
    payload.update(updates)
    payload["manifest_hash"] = None
    provisional = StageEnvelope.model_validate_json(
        canonical_json_bytes(payload), strict=True
    )
    manifest_hash = stage_manifest_hash(provisional)
    envelope = provisional.model_copy(update={"manifest_hash": manifest_hash})
    locator = store._manifest_locator(stage, manifest_hash)
    target = store.manifest_root / locator
    target.write_bytes(canonical_json_bytes(envelope))
    return manifest_hash, locator


def _assert_full_chain_integrity_failure(store: SQLiteStateStore, run_id: str) -> None:
    before = tuple(
        store.connection.execute(
            "SELECT COUNT(*) FROM stage_results UNION ALL "
            "SELECT COUNT(*) FROM checkpoints UNION ALL "
            "SELECT COUNT(*) FROM stage_attempts"
        ).fetchall()
    )
    with pytest.raises(SafeFailure) as failure:
        store.verify_run_chain(run_id)
    assert failure.value.as_dict() == {
        "code": ErrorCode.STATE_INTEGRITY_ERROR.value,
        "summary": ERROR_SUMMARIES[ErrorCode.STATE_INTEGRITY_ERROR],
    }
    after = tuple(
        store.connection.execute(
            "SELECT COUNT(*) FROM stage_results UNION ALL "
            "SELECT COUNT(*) FROM checkpoints UNION ALL "
            "SELECT COUNT(*) FROM stage_attempts"
        ).fetchall()
    )
    assert after == before


def _assert_resume_integrity_failure(store: SQLiteStateStore, run_id: str) -> None:
    before = store.connection.serialize()
    with pytest.raises(SafeFailure) as failure:
        store.verify_run_chain(run_id)
    assert failure.value.as_dict() == {
        "code": ErrorCode.STATE_INTEGRITY_ERROR.value,
        "summary": ERROR_SUMMARIES[ErrorCode.STATE_INTEGRITY_ERROR],
    }
    assert store.connection.serialize() == before


def _rewrite_resume_event(
    store: SQLiteStateStore,
    run_id: str,
    target_event_index: int,
    **updates: object,
) -> str:
    row = store.connection.execute(
        "SELECT * FROM resume_events WHERE run_id = ? AND event_index = ?",
        (run_id, target_event_index),
    ).fetchone()
    assert row is not None
    values = {
        "run_id": row["run_id"],
        "event_index": row["event_index"],
        "prior_event_hash": row["prior_event_hash"],
        "reused_stage_count": row["reused_stage_count"],
        "checkpoint_stage": row["checkpoint_stage"],
        "checkpoint_result_row_id": row["checkpoint_result_row_id"],
        "checkpoint_manifest_hash": row["checkpoint_manifest_hash"],
        "recorded_at": row["recorded_at"],
    }
    values.update(updates)
    rewritten_hash = resume_event_hash(**values)
    store.connection.execute("PRAGMA foreign_keys = OFF")
    try:
        store.connection.execute(
            """UPDATE resume_events
               SET event_hash = ?, event_index = ?, prior_event_hash = ?,
                   reused_stage_count = ?, checkpoint_stage = ?,
                   checkpoint_result_row_id = ?, checkpoint_manifest_hash = ?,
                   recorded_at = ?
               WHERE event_hash = ?""",
            (
                rewritten_hash,
                values["event_index"],
                values["prior_event_hash"],
                values["reused_stage_count"],
                values["checkpoint_stage"],
                values["checkpoint_result_row_id"],
                values["checkpoint_manifest_hash"],
                values["recorded_at"],
                row["event_hash"],
            ),
        )
        store.connection.execute(
            """UPDATE runs SET latest_resume_event_hash = ?
               WHERE run_id = ? AND latest_resume_event_hash = ?""",
            (rewritten_hash, run_id, row["event_hash"]),
        )
    finally:
        store.connection.execute("PRAGMA foreign_keys = ON")
    return rewritten_hash


def _create_zero_prefix_chain(store: SQLiteStateStore, run_id: str) -> None:
    store.create_run(
        run_id,
        _run_identity(f"subject:{run_id}"),
        "2026-07-19T00:00:00.000000Z",
    )
    store.record_resume_decision(
        run_id,
        None,
        "2026-07-19T00:00:01.000000Z",
    )


@pytest.mark.parametrize(
    ("fail_after", "expected_count", "expected_status"),
    [
        (None, len(tuple(PipelineStage)), RunStatus.PLANNED_NOT_PUBLISHED),
        ("generator", 6, RunStatus.INTERRUPTED),
    ],
)
def test_verify_run_chain_returns_one_typed_closed_prefix(
    tmp_path: Path,
    fail_after: str | None,
    expected_count: int,
    expected_status: RunStatus,
) -> None:
    store = SQLiteStateStore(tmp_path / f"verified-{fail_after or 'complete'}.db")
    try:
        if fail_after is None:
            run_id = PipelineRunner(store, FixtureProcessor()).run(
                load_fixture(APPROVED_FIXTURE), tmp_path / "complete"
            ).run_id
        else:
            run_id = _run_interrupted_in_store(store, tmp_path / "interrupted")
        chain = store.verify_run_chain(run_id)
        assert type(chain).__name__ == "VerifiedRunChain"
        assert chain.run.status is expected_status
        assert chain.identity == chain.run.identity
        assert len(chain.results) == expected_count
        assert len(chain.checkpoints) == expected_count
        assert tuple(result.stage for result in chain.results) == tuple(PipelineStage)[
            :expected_count
        ]
        assert tuple(checkpoint.stage for checkpoint in chain.checkpoints) == tuple(
            PipelineStage
        )[:expected_count]
        assert all(
            type(attempt).__name__ == "PersistedAttemptRecord"
            for attempt in chain.attempts
        )
        assert tuple(event.event_index for event in chain.resume_events) == tuple(
            range(len(chain.resume_events))
        )
        assert chain.reused_stage_count == chain.resume_events[-1].reused_stage_count
    finally:
        store.close()


def test_full_chain_accepts_genesis_only_and_consecutive_zero_prefix_events(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "zero-prefix-authority.db")
    try:
        store.create_run(
            "genesis-only",
            _run_identity("subject:genesis-only"),
            "2026-07-19T00:00:00.000000Z",
        )
        genesis = store.verify_run_chain("genesis-only")
        assert len(genesis.resume_events) == 1
        assert genesis.reused_stage_count == 0

        _create_zero_prefix_chain(store, "consecutive-zero")
        store.record_resume_decision(
            "consecutive-zero",
            None,
            "2026-07-19T00:00:02.000000Z",
        )
        zero_chain = store.verify_run_chain("consecutive-zero")
        assert [event.reused_stage_count for event in zero_chain.resume_events] == [
            0,
            0,
            0,
        ]
        assert zero_chain.reused_stage_count == 0
    finally:
        store.close()


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "extra",
        "broken_prior",
        "wrong_ordinal",
        "genesis_relabelled",
        "genesis_time",
        "zero_null_prior",
        "zero_checkpoint_tuple",
        "non_monotonic_time",
        "wrong_head",
        "wrong_count",
        "unrehashed_payload",
    ],
)
def test_full_chain_rejects_resume_event_order_shape_head_and_count_tamper(
    tmp_path: Path,
    damage: str,
) -> None:
    store = SQLiteStateStore(tmp_path / f"resume-chain-{damage}.db")
    try:
        _create_zero_prefix_chain(store, "resume-chain")
        genesis = store.connection.execute(
            "SELECT * FROM resume_events WHERE run_id = ? AND event_index = 0",
            ("resume-chain",),
        ).fetchone()
        latest = store.connection.execute(
            "SELECT * FROM resume_events WHERE run_id = ? AND event_index = 1",
            ("resume-chain",),
        ).fetchone()
        assert genesis is not None and latest is not None

        if damage == "missing":
            store.connection.execute("PRAGMA foreign_keys = OFF")
            store.connection.execute(
                "DELETE FROM resume_events WHERE event_hash = ?",
                (latest["event_hash"],),
            )
            store.connection.execute("PRAGMA foreign_keys = ON")
        elif damage == "extra":
            extra = store._new_resume_event(
                run_id="resume-chain",
                event_index=2,
                prior_event_hash=str(latest["event_hash"]),
                reused_stage_count=0,
                checkpoint=None,
                recorded_at="2026-07-19T00:00:02.000000Z",
            )
            store._insert_resume_event(store.connection, extra)
        elif damage == "broken_prior":
            _rewrite_resume_event(
                store,
                "resume-chain",
                1,
                prior_event_hash="sha256:" + "f" * 64,
            )
        elif damage == "wrong_ordinal":
            _rewrite_resume_event(store, "resume-chain", 1, event_index=3)
        elif damage == "genesis_relabelled":
            store.connection.execute("PRAGMA foreign_keys = OFF")
            store.connection.execute(
                "DELETE FROM resume_events WHERE event_index = 1"
            )
            store.connection.execute(
                "UPDATE runs SET latest_resume_event_hash = ? WHERE run_id = ?",
                (genesis["event_hash"], "resume-chain"),
            )
            store.connection.execute("PRAGMA foreign_keys = ON")
            _rewrite_resume_event(
                store,
                "resume-chain",
                0,
                event_index=1,
                prior_event_hash="sha256:" + "e" * 64,
            )
        elif damage == "genesis_time":
            store.connection.execute("PRAGMA foreign_keys = OFF")
            store.connection.execute(
                "DELETE FROM resume_events WHERE event_index = 1"
            )
            store.connection.execute(
                "UPDATE runs SET latest_resume_event_hash = ? WHERE run_id = ?",
                (genesis["event_hash"], "resume-chain"),
            )
            store.connection.execute("PRAGMA foreign_keys = ON")
            _rewrite_resume_event(
                store,
                "resume-chain",
                0,
                recorded_at="2026-07-19T00:00:00.000001Z",
            )
        elif damage == "zero_null_prior":
            _rewrite_resume_event(
                store,
                "resume-chain",
                1,
                prior_event_hash=None,
            )
        elif damage == "zero_checkpoint_tuple":
            _rewrite_resume_event(
                store,
                "resume-chain",
                1,
                checkpoint_stage="scout",
                checkpoint_result_row_id="sha256:" + "a" * 64,
                checkpoint_manifest_hash="sha256:" + "b" * 64,
            )
        elif damage == "non_monotonic_time":
            _rewrite_resume_event(
                store,
                "resume-chain",
                1,
                recorded_at="2026-07-18T23:59:59.999999Z",
            )
        elif damage == "wrong_head":
            store.connection.execute(
                "UPDATE runs SET latest_resume_event_hash = ? WHERE run_id = ?",
                (genesis["event_hash"], "resume-chain"),
            )
        elif damage == "wrong_count":
            store.connection.execute(
                "UPDATE runs SET reused_stage_count = 1 WHERE run_id = ?",
                ("resume-chain",),
            )
        else:
            store.connection.execute(
                """UPDATE resume_events SET recorded_at = ?
                   WHERE run_id = ? AND event_index = 1""",
                ("2026-07-19T00:00:02.000000Z", "resume-chain"),
            )

        _assert_resume_integrity_failure(store, "resume-chain")
    finally:
        store.close()


def test_resume_event_schema_rejects_duplicate_hash_and_ordinal(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "duplicate-resume-event.db")
    try:
        store.create_run(
            "duplicate-resume-event",
            _run_identity("subject:duplicate-resume-event"),
            "2026-07-19T00:00:00.000000Z",
        )
        event = store._new_resume_event(
            run_id="duplicate-resume-event",
            event_index=1,
            prior_event_hash=str(
                store.connection.execute(
                    "SELECT latest_resume_event_hash FROM runs"
                ).fetchone()[0]
            ),
            reused_stage_count=0,
            checkpoint=None,
            recorded_at="2026-07-19T00:00:01.000000Z",
        )
        store._insert_resume_event(store.connection, event)
        with pytest.raises(sqlite3.IntegrityError):
            store._insert_resume_event(store.connection, event)

        same_ordinal = store._new_resume_event(
            run_id="duplicate-resume-event",
            event_index=1,
            prior_event_hash=event.prior_event_hash,
            reused_stage_count=0,
            checkpoint=None,
            recorded_at="2026-07-19T00:00:02.000000Z",
        )
        with pytest.raises(sqlite3.IntegrityError):
            store._insert_resume_event(store.connection, same_ordinal)
    finally:
        store.close()


@pytest.mark.parametrize(
    "damage",
    [
        "partial_tuple",
        "wrong_stage",
        "wrong_result_row",
        "wrong_manifest",
        "before_checkpoint",
    ],
)
def test_full_chain_rejects_positive_event_checkpoint_and_timing_tamper(
    tmp_path: Path,
    damage: str,
) -> None:
    store = SQLiteStateStore(tmp_path / f"positive-event-{damage}.db")
    try:
        run_id = _run_interrupted_in_store(
            store,
            tmp_path / f"positive-event-{damage}-out",
        )
        checkpoint = store.latest_checkpoint(run_id)
        assert checkpoint is not None
        store.record_resume_decision(run_id, checkpoint, checkpoint.updated_at)
        run = store.connection.execute(
            "SELECT created_at FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        first_checkpoint = store.connection.execute(
            """SELECT result_row_id FROM checkpoints
               WHERE run_id = ? AND stage_index = 0""",
            (run_id,),
        ).fetchone()
        assert run is not None and first_checkpoint is not None

        if damage == "partial_tuple":
            updates = {"checkpoint_manifest_hash": None}
        elif damage == "wrong_stage":
            updates = {"checkpoint_stage": "reader"}
        elif damage == "wrong_result_row":
            updates = {"checkpoint_result_row_id": first_checkpoint["result_row_id"]}
        elif damage == "wrong_manifest":
            updates = {"checkpoint_manifest_hash": "sha256:" + "d" * 64}
        else:
            updates = {"recorded_at": run["created_at"]}
        _rewrite_resume_event(store, run_id, 1, **updates)

        _assert_resume_integrity_failure(store, run_id)
    finally:
        store.close()


def test_full_chain_accepts_repeated_positive_events_and_derives_latest_count(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "repeated-positive.db")
    try:
        run_id = _run_interrupted_in_store(store, tmp_path / "repeated-positive-out")
        checkpoint = store.latest_checkpoint(run_id)
        assert checkpoint is not None
        store.record_resume_decision(run_id, checkpoint, checkpoint.updated_at)
        store.record_resume_decision(run_id, checkpoint, checkpoint.updated_at)

        chain = store.verify_run_chain(run_id)
        assert [event.event_index for event in chain.resume_events] == [0, 1, 2]
        assert [event.reused_stage_count for event in chain.resume_events] == [0, 6, 6]
        assert chain.reused_stage_count == 6
    finally:
        store.close()


@pytest.mark.parametrize("source_version", [1, 2])
def test_zero_reuse_migration_verifies_with_exactly_one_genesis_event(
    tmp_path: Path,
    source_version: int,
) -> None:
    database = tmp_path / f"migrated-v{source_version}-genesis.db"
    if source_version == 1:
        shutil.copy2(FROZEN_DATABASE, database)
        database.chmod(0o600)
    else:
        _write_pre_event_schema_v2(database)

    store = SQLiteStateStore(database)
    try:
        row = store.connection.execute("SELECT * FROM runs").fetchone()
        assert row is not None
        if source_version == 1:
            fixture = load_fixture(APPROVED_FIXTURE)
            expected = RunIdentity(
                schema_version=str(row["schema_version"]),
                subject_id=str(row["subject_id"]),
                fixture_hash=sha256_digest(
                    fixture.model_dump(mode="json", exclude_none=False)
                ),
                producer_version=str(row["producer_version"]),
                retry_policy_version=str(row["retry_policy_version"]),
            )
            bound = store.bind_legacy_run(expected)
            assert bound is not None
        chain = store.verify_run_chain(str(row["run_id"]))
        assert len(chain.resume_events) == 1
        assert chain.resume_events[0].recorded_at == chain.run.created_at
        assert chain.reused_stage_count == 0
    finally:
        store.close()


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        ("runs", "schema_version", "1"),
        ("runs", "subject_id", "other-subject"),
        ("runs", "fixture_hash", "sha256:" + "2" * 64),
        ("runs", "producer_version", "fixture-v2"),
        ("runs", "retry_policy_version", "retry-v2"),
        ("stage_attempts", "subject_id", "other-subject"),
        ("stage_attempts", "stage", "publication_planner"),
        ("stage_attempts", "stage_index", 8),
        ("stage_attempts", "attempt_no", 99),
        ("stage_attempts", "input_hash", "sha256:" + "2" * 64),
        ("stage_attempts", "producer_version", "fixture-v2"),
        ("stage_attempts", "retry_policy_version", "retry-v2"),
        ("stage_attempts", "reusable_key_digest", "sha256:" + "2" * 64),
        ("stage_results", "schema_version", "1"),
        ("stage_results", "subject_id", "other-subject"),
        ("stage_results", "stage", "publication_planner"),
        ("stage_results", "stage_index", 8),
        ("stage_results", "output_json", "{}"),
        ("stage_results", "output_hash", "sha256:" + "2" * 64),
        ("stage_results", "producer_version", "fixture-v2"),
        ("stage_results", "result_id", "sha256:" + "2" * 64),
        ("checkpoints", "subject_id", "other-subject"),
        ("checkpoints", "stage", "publication_planner"),
        ("checkpoints", "stage_index", 8),
        ("checkpoints", "result_row_id", "sha256:" + "2" * 64),
        ("checkpoints", "result_id", "sha256:" + "2" * 64),
        ("checkpoints", "output_hash", "sha256:" + "2" * 64),
        ("checkpoints", "manifest_hash", "sha256:" + "2" * 64),
        ("checkpoints", "manifest_path", "scout/" + "2" * 64 + ".json"),
    ],
)
def test_full_chain_rejects_each_duplicated_persisted_field_tamper(
    tmp_path: Path,
    table: str,
    column: str,
    value: object,
) -> None:
    store = SQLiteStateStore(tmp_path / f"tamper-{table}-{column}.db")
    try:
        run_id = _run_interrupted_in_store(
            store, tmp_path / f"out-{table}-{column}"
        )
        if table == "checkpoints" and column == "result_row_id":
            value = store.connection.execute(
                """SELECT result_row_id FROM stage_results
                   WHERE run_id = ? AND stage = 'filter'""",
                (run_id,),
            ).fetchone()[0]
        where = "run_id = ?" if table == "runs" else "run_id = ? AND stage = 'scout'"
        store.connection.execute(
            f"UPDATE {table} SET {column} = ? WHERE {where}",
            (value, run_id),
        )
        _assert_full_chain_integrity_failure(store, run_id)
    finally:
        store.close()


def test_full_chain_recomputes_result_id_after_coherent_manifest_rehash(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "coherent-result-id.db")
    try:
        run_id = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "coherent-result-id-out"
        ).run_id
        forged = "sha256:" + "f" * 64
        manifest_hash, locator = _coherently_rewrite_manifest(
            store, PipelineStage.SCOUT, result_id=forged
        )
        store.connection.execute(
            """UPDATE stage_results
               SET result_id = ?, manifest_hash = ?, manifest_path = ?
               WHERE run_id = ? AND stage = 'scout'""",
            (forged, manifest_hash, locator, run_id),
        )
        store.connection.execute(
            """UPDATE checkpoints
               SET result_id = ?, manifest_hash = ?, manifest_path = ?
               WHERE run_id = ? AND stage = 'scout'""",
            (forged, manifest_hash, locator, run_id),
        )
        _assert_full_chain_integrity_failure(store, run_id)
    finally:
        store.close()


def test_full_chain_rebuilds_prior_output_input_and_reusable_identity(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "prior-output.db")
    try:
        run_id = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "prior-output-out"
        ).run_id
        row = store.connection.execute(
            """SELECT r.*, a.retry_policy_version FROM stage_results r
               JOIN stage_attempts a USING (attempt_id)
               WHERE r.run_id = ? AND r.stage = 'filter'""",
            (run_id,),
        ).fetchone()
        assert row is not None
        forged_input = "sha256:" + "3" * 64
        forged_reusable = reusable_key_digest(
            subject_id=str(row["subject_id"]),
            stage=PipelineStage.FILTER,
            input_hash=forged_input,
            producer_version=str(row["producer_version"]),
            retry_policy_version=str(row["retry_policy_version"]),
        )
        forged_result = make_result_id(
            subject_id=str(row["subject_id"]),
            stage=PipelineStage.FILTER,
            input_hash=forged_input,
            producer_version=str(row["producer_version"]),
            output_hash=str(row["output_hash"]),
            retry_policy_version=str(row["retry_policy_version"]),
        )
        manifest_hash, locator = _coherently_rewrite_manifest(
            store,
            PipelineStage.FILTER,
            input_hash=forged_input,
            result_id=forged_result,
        )
        store.connection.execute(
            """UPDATE stage_attempts
               SET input_hash = ?, reusable_key_digest = ?
               WHERE run_id = ? AND stage = 'filter'""",
            (forged_input, forged_reusable, run_id),
        )
        store.connection.execute(
            """UPDATE stage_results
               SET result_id = ?, manifest_hash = ?, manifest_path = ?
               WHERE run_id = ? AND stage = 'filter'""",
            (forged_result, manifest_hash, locator, run_id),
        )
        store.connection.execute(
            """UPDATE checkpoints
               SET result_id = ?, manifest_hash = ?, manifest_path = ?
               WHERE run_id = ? AND stage = 'filter'""",
            (forged_result, manifest_hash, locator, run_id),
        )
        _assert_full_chain_integrity_failure(store, run_id)
    finally:
        store.close()


@pytest.mark.parametrize(
    "damage",
    ["missing_checkpoint", "missing_pair", "extra_result", "extra_checkpoint", "reordered"],
)
def test_full_chain_rejects_result_checkpoint_order_and_cardinality_damage(
    tmp_path: Path, damage: str
) -> None:
    store = SQLiteStateStore(tmp_path / f"cardinality-{damage}.db")
    try:
        run_id = _run_interrupted_in_store(
            store, tmp_path / f"cardinality-{damage}-out"
        )
        if damage == "missing_checkpoint":
            store.connection.execute(
                "DELETE FROM checkpoints WHERE run_id = ? AND stage = 'scout'", (run_id,)
            )
        elif damage == "missing_pair":
            store.connection.execute(
                "DELETE FROM checkpoints WHERE run_id = ? AND stage = 'scout'", (run_id,)
            )
            store.connection.execute(
                "DELETE FROM stage_results WHERE run_id = ? AND stage = 'scout'", (run_id,)
            )
        elif damage == "extra_result":
            source_attempt = store.connection.execute(
                "SELECT * FROM stage_attempts WHERE run_id = ? AND stage = 'scout'",
                (run_id,),
            ).fetchone()
            source_result = store.connection.execute(
                "SELECT * FROM stage_results WHERE run_id = ? AND stage = 'scout'",
                (run_id,),
            ).fetchone()
            assert source_attempt is not None and source_result is not None
            attempt_id = f"{run_id}:publication_planner:2"
            store.connection.execute(
                """INSERT INTO stage_attempts
                   SELECT ?, run_id, subject_id, 'publication_planner', 8, 2, status,
                          input_hash, producer_version, retry_policy_version,
                          reusable_key_digest, started_at, finished_at, prompt_version,
                          policy_version, model_id, request_id, latency_ms, prompt_tokens,
                          completion_tokens, total_tokens, error_code, error_summary, retryable
                   FROM stage_attempts WHERE attempt_id = ?""",
                (attempt_id, source_attempt["attempt_id"]),
            )
            store.connection.execute(
                """INSERT INTO stage_results
                   SELECT ?, result_id, ?, run_id, schema_version, subject_id,
                          'publication_planner', 8, output_json, output_hash,
                          producer_version, manifest_hash, manifest_path, created_at
                   FROM stage_results WHERE result_row_id = ?""",
                (
                    "sha256:" + "4" * 64,
                    attempt_id,
                    source_result["result_row_id"],
                ),
            )
        elif damage == "extra_checkpoint":
            store.connection.execute(
                """INSERT INTO checkpoints
                   SELECT run_id, subject_id, 'publication_planner', 8, result_row_id,
                          result_id, output_hash, manifest_hash, manifest_path, updated_at
                   FROM checkpoints WHERE run_id = ? AND stage = 'scout'""",
                (run_id,),
            )
        else:
            for table in ("stage_attempts", "stage_results", "checkpoints"):
                store.connection.execute(
                    f"UPDATE {table} SET stage_index = 99 WHERE run_id = ? AND stage = 'scout'",
                    (run_id,),
                )
                store.connection.execute(
                    f"UPDATE {table} SET stage_index = 0 WHERE run_id = ? AND stage = 'filter'",
                    (run_id,),
                )
                store.connection.execute(
                    f"UPDATE {table} SET stage_index = 1 WHERE run_id = ? AND stage = 'scout'",
                    (run_id,),
                )
        _assert_full_chain_integrity_failure(store, run_id)
    finally:
        store.close()


def test_every_bound_trust_entry_point_delegates_to_one_full_chain_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SQLiteStateStore(tmp_path / "shared-verifier.db")
    try:
        run_id = _run_interrupted_in_store(store, tmp_path / "shared-verifier-out")
        identity = store.read_run(run_id).identity
        original = store.verify_run_chain
        calls: list[tuple[str, RunIdentity | None]] = []

        def observed(
            candidate_run_id: str,
            expected_identity: RunIdentity | None = None,
        ):
            calls.append((candidate_run_id, expected_identity))
            return original(candidate_run_id, expected_identity)

        monkeypatch.setattr(store, "verify_run_chain", observed)
        assert store.find_resumable_run(identity).run_id == run_id
        assert store.latest_checkpoint(run_id).stage is PipelineStage.GENERATOR
        store.verify_completed_results(run_id, 6)
        assert store.inspect_run(run_id)["run"]["run_id"] == run_id
        assert calls == [
            (run_id, identity),
            (run_id, None),
            (run_id, None),
            (run_id, None),
        ]
    finally:
        store.close()


def test_forged_semantic_result_is_rejected_consistently_by_every_trust_path(
    tmp_path: Path,
) -> None:
    store = SQLiteStateStore(tmp_path / "shared-forgery.db")
    try:
        run_id = _run_interrupted_in_store(store, tmp_path / "shared-forgery-out")
        identity = store.read_run(run_id).identity
        before = tuple(
            store.connection.execute(
                """SELECT r.status, r.updated_at, COUNT(DISTINCT a.attempt_id),
                          COUNT(DISTINCT s.result_row_id), COUNT(DISTINCT c.stage)
                   FROM runs r
                   LEFT JOIN stage_attempts a USING (run_id)
                   LEFT JOIN stage_results s USING (run_id)
                   LEFT JOIN checkpoints c USING (run_id)
                   WHERE r.run_id = ? GROUP BY r.run_id""",
                (run_id,),
            ).fetchone()
        )
        forged = "sha256:" + "f" * 64
        manifest_hash, locator = _coherently_rewrite_manifest(
            store, PipelineStage.SCOUT, result_id=forged
        )
        store.connection.execute(
            """UPDATE stage_results
               SET result_id = ?, manifest_hash = ?, manifest_path = ?
               WHERE run_id = ? AND stage = 'scout'""",
            (forged, manifest_hash, locator, run_id),
        )
        store.connection.execute(
            """UPDATE checkpoints
               SET result_id = ?, manifest_hash = ?, manifest_path = ?
               WHERE run_id = ? AND stage = 'scout'""",
            (forged, manifest_hash, locator, run_id),
        )

        operations = (
            lambda: store.find_resumable_run(identity),
            lambda: store.latest_checkpoint(run_id),
            lambda: store.verify_completed_results(run_id, 6),
            lambda: store.inspect_run(run_id),
        )
        for operation in operations:
            with pytest.raises(SafeFailure) as failure:
                operation()
            assert failure.value.as_dict() == {
                "code": ErrorCode.STATE_INTEGRITY_ERROR.value,
                "summary": ERROR_SUMMARIES[ErrorCode.STATE_INTEGRITY_ERROR],
            }
        after = tuple(
            store.connection.execute(
                """SELECT r.status, r.updated_at, COUNT(DISTINCT a.attempt_id),
                          COUNT(DISTINCT s.result_row_id), COUNT(DISTINCT c.stage)
                   FROM runs r
                   LEFT JOIN stage_attempts a USING (run_id)
                   LEFT JOIN stage_results s USING (run_id)
                   LEFT JOIN checkpoints c USING (run_id)
                   WHERE r.run_id = ? GROUP BY r.run_id""",
                (run_id,),
            ).fetchone()
        )
        assert after == before
    finally:
        store.close()


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
        expected = (
            database.with_suffix(".manifests")
            / str(row["stage"])
            / (digest.removeprefix("sha256:") + ".json")
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
        connection.execute(f"UPDATE stage_results SET {column} = ? WHERE stage = 'scout'", (value,))
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


def test_state_manifest_namespace_collision_is_rejected_before_creation(
    tmp_path: Path,
) -> None:
    state = tmp_path / "COLLISION_CANARY_DO_NOT_DISCLOSE.manifests"

    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(state)

    assert failure.value.as_dict() == {
        "code": ErrorCode.STATE_INTEGRITY_ERROR.value,
        "summary": ERROR_SUMMARIES[ErrorCode.STATE_INTEGRITY_ERROR],
    }
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("mode", [0o640, 0o602])
def test_existing_state_requires_private_permissions_before_deserialize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: int,
) -> None:
    database = tmp_path / f"unsafe-mode-{mode:o}.db"
    SQLiteStateStore(database).close()
    database.chmod(mode)

    def reject_deserialize() -> None:
        raise AssertionError("unsafe state reached SQLite")

    monkeypatch.setattr(
        SQLiteStateStore,
        "_new_memory_connection",
        staticmethod(reject_deserialize),
    )
    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(database)
    assert failure.value.code is ErrorCode.STATE_SCHEMA_INCOMPATIBLE


def test_existing_state_requires_one_link(tmp_path: Path) -> None:
    database = tmp_path / "linked.db"
    SQLiteStateStore(database).close()
    os.link(database, tmp_path / "linked-alias.db")

    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(database)

    assert failure.value.code is ErrorCode.STATE_SCHEMA_INCOMPATIBLE


def test_private_file_predicate_rejects_foreign_owner_and_missing_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    effective_uid = os.geteuid()
    foreign = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o600,
        st_nlink=1,
        st_uid=effective_uid + 1,
    )
    with pytest.raises(DurableWriteError):
        AnchoredDirectory._require_private_regular(foreign)

    private = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o600,
        st_nlink=1,
        st_uid=effective_uid,
    )
    monkeypatch.setattr(localfs_adapter.os, "geteuid", None)
    with pytest.raises(DurableWriteError):
        AnchoredDirectory._require_private_regular(private)


def test_new_state_lock_backup_temporary_and_manifest_files_are_private(
    tmp_path: Path,
) -> None:
    transient: list[os.stat_result] = []
    saw_backup_temporary = False

    def observe_private_temporary(operation: str) -> None:
        nonlocal saw_backup_temporary
        if not operation.endswith("file_fsync"):
            return
        for candidate in tmp_path.rglob("*"):
            if candidate.name.endswith(".tmp") and candidate.is_file():
                metadata = os.lstat(candidate)
                transient.append(metadata)
                saw_backup_temporary |= "backup" in candidate.name

    database = tmp_path / "private.db"
    store = SQLiteStateStore(database, filesystem_seam=observe_private_temporary)
    try:
        PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / "private-output"
        )
    finally:
        store.close()

    authorities = [database, tmp_path / ".private.db.lock"]
    authorities.extend(database.with_suffix(".manifests").rglob("*.json"))
    metadata = [os.lstat(path) for path in authorities]
    assert transient
    assert saw_backup_temporary is True
    assert metadata
    assert all(item.st_mode & 0o077 == 0 for item in [*transient, *metadata])
    assert all(item.st_nlink == 1 for item in [*transient, *metadata])
    assert all(item.st_uid == os.geteuid() for item in [*transient, *metadata])


@pytest.mark.parametrize("damage", ["permission", "hardlink"])
def test_existing_manifest_requires_private_single_owner_file_before_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    store = SQLiteStateStore(tmp_path / f"manifest-{damage}.db")
    try:
        run_id = PipelineRunner(store, FixtureProcessor()).run(
            load_fixture(APPROVED_FIXTURE), tmp_path / f"manifest-{damage}-out"
        ).run_id
        row = store.connection.execute(
            "SELECT manifest_path FROM stage_results ORDER BY stage_index LIMIT 1"
        ).fetchone()
        manifest = store.manifest_root / str(row["manifest_path"])
        if damage == "permission":
            manifest.chmod(0o640)
        else:
            os.link(manifest, manifest.with_suffix(".linked"))

        def reject_decode(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("unsafe manifest reached JSON decoding")

        monkeypatch.setattr(StageEnvelope, "model_validate_json", reject_decode)
        with pytest.raises(SafeFailure) as failure:
            store.verify_run_chain(run_id)
        assert failure.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    finally:
        store.close()


@pytest.mark.parametrize(
    "variant",
    [
        "extra_table",
        "extra_column",
        "changed_type",
        "changed_nullability",
        "changed_default",
        "missing_check",
        "missing_unique",
        "missing_foreign_key",
        "missing_index",
        "changed_index_order",
        "unique_index",
        "partial_index",
        "extra_index",
    ],
)
def test_malformed_schema_v2_fingerprint_is_rejected_without_mutation(
    tmp_path: Path, variant: str
) -> None:
    database = tmp_path / f"malformed-schema-{variant}.db"
    _write_schema_v2_variant(database, variant)
    before = database.read_bytes()

    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(database)

    assert failure.value.code is ErrorCode.STATE_SCHEMA_INCOMPATIBLE
    assert database.read_bytes() == before


@pytest.mark.parametrize("damage", ["quick_check", "foreign_key_check"])
def test_schema_v2_integrity_failures_are_fixed_and_sanitized(tmp_path: Path, damage: str) -> None:
    database = tmp_path / f"schema-integrity-{damage}.db"
    SQLiteStateStore(database).close()
    with _connect(database) as connection:
        if damage == "quick_check":
            connection.execute("PRAGMA ignore_check_constraints = ON")
            connection.execute(
                """INSERT INTO runs
                   (run_id, schema_version, subject_id, fixture_hash,
                    producer_version, retry_policy_version, identity_state,
                    execution_mode, status, created_at, updated_at,
                    error_code, error_summary, reused_stage_count,
                    latest_resume_event_hash)
                   VALUES ('corrupt-run', '2', 'subject', NULL, 'fixture-v1',
                           'retry-v1', 'corrupt', 'dry_run', 'running',
                           '2026-07-19T00:00:00.000000Z',
                           '2026-07-19T00:00:00.000000Z', NULL, NULL, 0,
                           'sha256:4444444444444444444444444444444444444444444444444444444444444444')"""
                )
        else:
            connection.execute(
                """INSERT INTO checkpoints
                   (run_id, subject_id, stage, stage_index, result_row_id,
                    result_id, output_hash, manifest_hash, manifest_path, updated_at)
                   VALUES ('orphan-run', 'subject', 'scout', 0, 'orphan-row',
                           'orphan-result', 'orphan-output', 'orphan-manifest',
                           'scout/orphan.json', '2026-07-19T00:00:00.000000Z')"""
            )
        connection.commit()
    before = database.read_bytes()

    with pytest.raises(SafeFailure) as failure:
        SQLiteStateStore(database)

    assert failure.value.as_dict() == {
        "code": ErrorCode.STATE_SCHEMA_INCOMPATIBLE.value,
        "summary": ERROR_SUMMARIES[ErrorCode.STATE_SCHEMA_INCOMPATIBLE],
    }
    assert database.read_bytes() == before


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
            PipelineRunner(store, FixtureProcessor()).run(load_fixture(APPROVED_FIXTURE), output)
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
        first.create_run("run-1", _run_identity("subject-1"), "2026-07-19T00:00:00.000000Z")
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
        store.create_run("not-durable", _run_identity("subject"), "2026-07-19T00:00:00.000000Z")
    assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    store.close()

    assert (anchored_parent / "state.db").read_bytes() == prior
    assert attacker_canary.read_bytes() == b"attacker-unchanged"
    assert sorted(path.name for path in attacker_parent.iterdir()) == ["canary"]


@pytest.mark.parametrize(
    "seam",
    ["after_backup_unlink", "before_backup_cleanup_directory_fsync"],
)
def test_post_commit_backup_cleanup_failure_returns_success_and_reopen_observes_mutation(
    tmp_path: Path,
    seam: str,
) -> None:
    active = False
    observed: list[str] = []

    def fail_selected(operation: str) -> None:
        observed.append(operation)
        if active and operation == seam:
            raise OSError("forced post-commit cleanup failure")

    database = tmp_path / f"post-commit-{seam}.db"
    store = SQLiteStateStore(database, filesystem_seam=fail_selected)
    active = True
    store.create_run(
        "committed-once",
        _run_identity("post-commit-subject"),
        "2026-07-19T00:00:00.000000Z",
    )
    assert seam in observed
    assert store.connection.execute(
        "SELECT COUNT(*) FROM runs WHERE run_id = 'committed-once'"
    ).fetchone()[0] == 1
    store.close()

    reopened = SQLiteStateStore(database)
    try:
        assert reopened.connection.execute(
            "SELECT COUNT(*) FROM runs WHERE run_id = 'committed-once'"
        ).fetchone()[0] == 1
        assert reopened.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "seam",
    ["before_state_file_fsync", "before_state_rename", "before_state_directory_fsync"],
)
def test_pre_commit_snapshot_failure_restores_prior_authority(
    tmp_path: Path,
    seam: str,
) -> None:
    active = False

    def fail_selected(operation: str) -> None:
        if active and operation == seam:
            raise OSError("forced pre-commit failure")

    database = tmp_path / f"pre-commit-{seam}.db"
    store = SQLiteStateStore(database, filesystem_seam=fail_selected)
    prior = database.read_bytes()
    active = True
    with pytest.raises(SafeFailure) as failure:
        store.create_run(
            "not-committed",
            _run_identity("pre-commit-subject"),
            "2026-07-19T00:00:00.000000Z",
        )
    assert failure.value.code is ErrorCode.STATE_OPERATION_FAILED
    assert store.connection is None
    assert database.read_bytes() == prior
    store.close()

    reopened = SQLiteStateStore(database)
    try:
        assert reopened.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
    finally:
        reopened.close()


def test_stale_backup_never_supersedes_valid_state_target(tmp_path: Path) -> None:
    database = tmp_path / "authoritative.db"
    SQLiteStateStore(database).close()

    stale_database = tmp_path / "stale.db"
    stale = SQLiteStateStore(stale_database)
    stale.create_run(
        "stale-run",
        _run_identity("stale-subject"),
        "2026-07-19T00:00:00.000000Z",
    )
    stale.close()
    backup = tmp_path / ".authoritative.db.backup"
    backup.write_bytes(stale_database.read_bytes())
    backup.chmod(0o600)

    reopened = SQLiteStateStore(database)
    try:
        assert reopened.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
        reopened.create_run(
            "authoritative-run",
            _run_identity("authoritative-subject"),
            "2026-07-19T00:00:01.000000Z",
        )
    finally:
        reopened.close()

    final = SQLiteStateStore(database)
    try:
        assert [
            row[0] for row in final.connection.execute("SELECT run_id FROM runs").fetchall()
        ] == ["authoritative-run"]
    finally:
        final.close()


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
        assert {row["result_row_id"] for row in twins} == {
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
        foreign_keys = store.connection.execute("PRAGMA foreign_key_list(checkpoints)").fetchall()
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
    database.chmod(0o600)
    with _connect(database) as legacy:
        legacy_results = [
            str(row[0])
            for row in legacy.execute("SELECT result_id FROM stage_results ORDER BY stage_index")
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
            == make_result_row_id(run_id=str(row["run_id"]), stage=PipelineStage(str(row["stage"])))
            for row in migrated
        )
        assert store.connection.execute("PRAGMA foreign_key_check").fetchone() is None
    finally:
        store.close()
