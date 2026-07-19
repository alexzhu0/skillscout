"""Transactional schema-v2 SQLite ledger and content-addressed manifests."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, TypeVar

from pydantic import ValidationError

from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode, SafeFailure
from skillscout.domain.canonical import (
    canonical_json_bytes,
    make_result_id,
    make_result_row_id,
    reusable_key_digest,
    stage_input_hash,
    stage_manifest_hash,
    stage_output_hash,
)
from skillscout.domain.enums import (
    AttemptStatus,
    EffectScope,
    ExecutionMode,
    PipelineStage,
    RunStatus,
    validate_run_transition,
)
from skillscout.domain.models import (
    MAX_MANIFEST_BYTES,
    SUPPORTED_PRODUCER_SCHEMAS,
    Checkpoint,
    PersistedAttemptRecord,
    PersistedCheckpointRecord,
    PersistedRunRecord,
    RunIdentity,
    RunRecord,
    StageAttempt,
    StageEnvelope,
    StageInput,
    validate_manifest_bytes,
)

SCHEMA_VERSION = 2
MAX_STATE_DB_BYTES = 67_108_864
MAX_LEGACY_BIND_CANDIDATES = 32
_MIGRATION_SEAMS = frozenset({"after_schema", "after_copy", "after_validation"})
_DIGEST_PATTERN = re.compile(r"^sha256:([0-9a-f]{64})$")
_T = TypeVar("_T")


@dataclass(frozen=True)
class _ColumnDescriptor:
    cid: int
    name: str
    declared_type: str
    not_null: int
    default_value: str | None
    primary_key_position: int


@dataclass(frozen=True)
class _ForeignKeyDescriptor:
    identifier: int
    sequence: int
    target_table: str
    from_column: str
    to_column: str
    on_update: str
    on_delete: str
    match: str


@dataclass(frozen=True)
class _IndexDescriptor:
    name: str
    unique: int
    origin: str
    partial: int
    columns: tuple[tuple[int, int, str], ...]


def stat_is_private_regular(metadata: os.stat_result) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and metadata.st_uid == os.getuid()
        and metadata.st_mode & 0o077 == 0
    )


def _schema_statements(suffix: str = "") -> tuple[str, ...]:
    runs = f"runs{suffix}"
    attempts = f"stage_attempts{suffix}"
    results = f"stage_results{suffix}"
    checkpoints = f"checkpoints{suffix}"
    return (
        f"""CREATE TABLE {runs} (
            run_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            fixture_hash TEXT,
            producer_version TEXT NOT NULL,
            retry_policy_version TEXT NOT NULL,
            identity_state TEXT NOT NULL
                CHECK (identity_state IN ('bound', 'legacy_unbound')),
            execution_mode TEXT NOT NULL CHECK (execution_mode = 'dry_run'),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            error_code TEXT,
            error_summary TEXT,
            reused_stage_count INTEGER NOT NULL DEFAULT 0,
            CHECK (
                (identity_state = 'bound' AND fixture_hash IS NOT NULL)
                OR (identity_state = 'legacy_unbound' AND fixture_hash IS NULL)
            )
        )""",
        f"""CREATE INDEX idx_runs_resumable_identity{suffix} ON {runs}(
            schema_version, subject_id, fixture_hash, producer_version,
            retry_policy_version, identity_state, status, updated_at DESC, run_id DESC
        )""",
        f"""CREATE TABLE {attempts} (
            attempt_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES {runs}(run_id),
            subject_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_index INTEGER NOT NULL,
            attempt_no INTEGER NOT NULL,
            status TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            producer_version TEXT NOT NULL,
            retry_policy_version TEXT NOT NULL,
            reusable_key_digest TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            prompt_version TEXT,
            policy_version TEXT,
            model_id TEXT,
            request_id TEXT,
            latency_ms INTEGER,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            error_code TEXT,
            error_summary TEXT,
            retryable INTEGER NOT NULL DEFAULT 0,
            UNIQUE (run_id, subject_id, stage, attempt_no)
        )""",
        f"CREATE INDEX idx_attempts_reusable{suffix} ON {attempts}(reusable_key_digest)",
        f"""CREATE TABLE {results} (
            result_row_id TEXT PRIMARY KEY,
            result_id TEXT NOT NULL,
            attempt_id TEXT NOT NULL UNIQUE REFERENCES {attempts}(attempt_id),
            run_id TEXT NOT NULL REFERENCES {runs}(run_id),
            schema_version TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_index INTEGER NOT NULL,
            output_json TEXT NOT NULL,
            output_hash TEXT NOT NULL,
            producer_version TEXT NOT NULL,
            manifest_hash TEXT NOT NULL,
            manifest_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (run_id, stage),
            UNIQUE (result_row_id, run_id)
        )""",
        f"CREATE INDEX idx_results_semantic{suffix} ON {results}(result_id)",
        f"""CREATE TABLE {checkpoints} (
            run_id TEXT NOT NULL REFERENCES {runs}(run_id),
            subject_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_index INTEGER NOT NULL,
            result_row_id TEXT NOT NULL,
            result_id TEXT NOT NULL,
            output_hash TEXT NOT NULL,
            manifest_hash TEXT NOT NULL,
            manifest_path TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_id, stage),
            FOREIGN KEY (result_row_id, run_id)
                REFERENCES {results}(result_row_id, run_id)
        )""",
    )


def _normalize_schema_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _expected_schema_sql() -> MappingProxyType[str, str]:
    expected: dict[str, str] = {}
    pattern = re.compile(r"^CREATE (?:UNIQUE )?(?:TABLE|INDEX) ([^\s(]+)", re.I)
    for statement in _schema_statements():
        matched = pattern.match(statement)
        if matched is None:
            raise RuntimeError("invalid trusted schema statement")
        expected[matched.group(1)] = _normalize_schema_sql(statement)
    return MappingProxyType(expected)


_EXPECTED_SCHEMA_SQL = _expected_schema_sql()
_EXPECTED_NAMED_SCHEMA_OBJECTS = (
    ("index", "idx_attempts_reusable", "stage_attempts"),
    ("index", "idx_results_semantic", "stage_results"),
    ("index", "idx_runs_resumable_identity", "runs"),
    ("table", "checkpoints", "checkpoints"),
    ("table", "runs", "runs"),
    ("table", "stage_attempts", "stage_attempts"),
    ("table", "stage_results", "stage_results"),
)
_EXPECTED_COLUMNS = MappingProxyType(
    {
        "runs": (
            _ColumnDescriptor(0, "run_id", "TEXT", 0, None, 1),
            _ColumnDescriptor(1, "schema_version", "TEXT", 1, None, 0),
            _ColumnDescriptor(2, "subject_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(3, "fixture_hash", "TEXT", 0, None, 0),
            _ColumnDescriptor(4, "producer_version", "TEXT", 1, None, 0),
            _ColumnDescriptor(5, "retry_policy_version", "TEXT", 1, None, 0),
            _ColumnDescriptor(6, "identity_state", "TEXT", 1, None, 0),
            _ColumnDescriptor(7, "execution_mode", "TEXT", 1, None, 0),
            _ColumnDescriptor(8, "status", "TEXT", 1, None, 0),
            _ColumnDescriptor(9, "created_at", "TEXT", 1, None, 0),
            _ColumnDescriptor(10, "updated_at", "TEXT", 1, None, 0),
            _ColumnDescriptor(11, "error_code", "TEXT", 0, None, 0),
            _ColumnDescriptor(12, "error_summary", "TEXT", 0, None, 0),
            _ColumnDescriptor(13, "reused_stage_count", "INTEGER", 1, "0", 0),
        ),
        "stage_attempts": (
            _ColumnDescriptor(0, "attempt_id", "TEXT", 0, None, 1),
            _ColumnDescriptor(1, "run_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(2, "subject_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(3, "stage", "TEXT", 1, None, 0),
            _ColumnDescriptor(4, "stage_index", "INTEGER", 1, None, 0),
            _ColumnDescriptor(5, "attempt_no", "INTEGER", 1, None, 0),
            _ColumnDescriptor(6, "status", "TEXT", 1, None, 0),
            _ColumnDescriptor(7, "input_hash", "TEXT", 1, None, 0),
            _ColumnDescriptor(8, "producer_version", "TEXT", 1, None, 0),
            _ColumnDescriptor(9, "retry_policy_version", "TEXT", 1, None, 0),
            _ColumnDescriptor(10, "reusable_key_digest", "TEXT", 1, None, 0),
            _ColumnDescriptor(11, "started_at", "TEXT", 1, None, 0),
            _ColumnDescriptor(12, "finished_at", "TEXT", 0, None, 0),
            _ColumnDescriptor(13, "prompt_version", "TEXT", 0, None, 0),
            _ColumnDescriptor(14, "policy_version", "TEXT", 0, None, 0),
            _ColumnDescriptor(15, "model_id", "TEXT", 0, None, 0),
            _ColumnDescriptor(16, "request_id", "TEXT", 0, None, 0),
            _ColumnDescriptor(17, "latency_ms", "INTEGER", 0, None, 0),
            _ColumnDescriptor(18, "prompt_tokens", "INTEGER", 0, None, 0),
            _ColumnDescriptor(19, "completion_tokens", "INTEGER", 0, None, 0),
            _ColumnDescriptor(20, "total_tokens", "INTEGER", 0, None, 0),
            _ColumnDescriptor(21, "error_code", "TEXT", 0, None, 0),
            _ColumnDescriptor(22, "error_summary", "TEXT", 0, None, 0),
            _ColumnDescriptor(23, "retryable", "INTEGER", 1, "0", 0),
        ),
        "stage_results": (
            _ColumnDescriptor(0, "result_row_id", "TEXT", 0, None, 1),
            _ColumnDescriptor(1, "result_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(2, "attempt_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(3, "run_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(4, "schema_version", "TEXT", 1, None, 0),
            _ColumnDescriptor(5, "subject_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(6, "stage", "TEXT", 1, None, 0),
            _ColumnDescriptor(7, "stage_index", "INTEGER", 1, None, 0),
            _ColumnDescriptor(8, "output_json", "TEXT", 1, None, 0),
            _ColumnDescriptor(9, "output_hash", "TEXT", 1, None, 0),
            _ColumnDescriptor(10, "producer_version", "TEXT", 1, None, 0),
            _ColumnDescriptor(11, "manifest_hash", "TEXT", 1, None, 0),
            _ColumnDescriptor(12, "manifest_path", "TEXT", 1, None, 0),
            _ColumnDescriptor(13, "created_at", "TEXT", 1, None, 0),
        ),
        "checkpoints": (
            _ColumnDescriptor(0, "run_id", "TEXT", 1, None, 1),
            _ColumnDescriptor(1, "subject_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(2, "stage", "TEXT", 1, None, 2),
            _ColumnDescriptor(3, "stage_index", "INTEGER", 1, None, 0),
            _ColumnDescriptor(4, "result_row_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(5, "result_id", "TEXT", 1, None, 0),
            _ColumnDescriptor(6, "output_hash", "TEXT", 1, None, 0),
            _ColumnDescriptor(7, "manifest_hash", "TEXT", 1, None, 0),
            _ColumnDescriptor(8, "manifest_path", "TEXT", 1, None, 0),
            _ColumnDescriptor(9, "updated_at", "TEXT", 1, None, 0),
        ),
    }
)
_EXPECTED_FOREIGN_KEYS = MappingProxyType(
    {
        "runs": (),
        "stage_attempts": (
            _ForeignKeyDescriptor(
                0, 0, "runs", "run_id", "run_id", "NO ACTION", "NO ACTION", "NONE"
            ),
        ),
        "stage_results": (
            _ForeignKeyDescriptor(
                0, 0, "runs", "run_id", "run_id", "NO ACTION", "NO ACTION", "NONE"
            ),
            _ForeignKeyDescriptor(
                1,
                0,
                "stage_attempts",
                "attempt_id",
                "attempt_id",
                "NO ACTION",
                "NO ACTION",
                "NONE",
            ),
        ),
        "checkpoints": (
            _ForeignKeyDescriptor(
                0,
                0,
                "stage_results",
                "result_row_id",
                "result_row_id",
                "NO ACTION",
                "NO ACTION",
                "NONE",
            ),
            _ForeignKeyDescriptor(
                0,
                1,
                "stage_results",
                "run_id",
                "run_id",
                "NO ACTION",
                "NO ACTION",
                "NONE",
            ),
            _ForeignKeyDescriptor(
                1, 0, "runs", "run_id", "run_id", "NO ACTION", "NO ACTION", "NONE"
            ),
        ),
    }
)
_EXPECTED_INDEXES = MappingProxyType(
    {
        "runs": (
            _IndexDescriptor(
                "idx_runs_resumable_identity",
                0,
                "c",
                0,
                (
                    (0, 1, "schema_version"),
                    (1, 2, "subject_id"),
                    (2, 3, "fixture_hash"),
                    (3, 4, "producer_version"),
                    (4, 5, "retry_policy_version"),
                    (5, 6, "identity_state"),
                    (6, 8, "status"),
                    (7, 10, "updated_at"),
                    (8, 0, "run_id"),
                ),
            ),
            _IndexDescriptor("sqlite_autoindex_runs_1", 1, "pk", 0, ((0, 0, "run_id"),)),
        ),
        "stage_attempts": (
            _IndexDescriptor(
                "idx_attempts_reusable",
                0,
                "c",
                0,
                ((0, 10, "reusable_key_digest"),),
            ),
            _IndexDescriptor(
                "sqlite_autoindex_stage_attempts_2",
                1,
                "u",
                0,
                (
                    (0, 1, "run_id"),
                    (1, 2, "subject_id"),
                    (2, 3, "stage"),
                    (3, 5, "attempt_no"),
                ),
            ),
            _IndexDescriptor(
                "sqlite_autoindex_stage_attempts_1",
                1,
                "pk",
                0,
                ((0, 0, "attempt_id"),),
            ),
        ),
        "stage_results": (
            _IndexDescriptor("idx_results_semantic", 0, "c", 0, ((0, 1, "result_id"),)),
            _IndexDescriptor(
                "sqlite_autoindex_stage_results_4",
                1,
                "u",
                0,
                ((0, 0, "result_row_id"), (1, 3, "run_id")),
            ),
            _IndexDescriptor(
                "sqlite_autoindex_stage_results_3",
                1,
                "u",
                0,
                ((0, 3, "run_id"), (1, 6, "stage")),
            ),
            _IndexDescriptor(
                "sqlite_autoindex_stage_results_2",
                1,
                "u",
                0,
                ((0, 2, "attempt_id"),),
            ),
            _IndexDescriptor(
                "sqlite_autoindex_stage_results_1",
                1,
                "pk",
                0,
                ((0, 0, "result_row_id"),),
            ),
        ),
        "checkpoints": (
            _IndexDescriptor(
                "sqlite_autoindex_checkpoints_1",
                1,
                "pk",
                0,
                ((0, 0, "run_id"), (1, 2, "stage")),
            ),
        ),
    }
)


class SQLiteStateStore:
    """Exclusive descriptor-anchored serialized SQLite state adapter."""

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.LOCAL_STATE

    def __init__(
        self,
        path: Path,
        *,
        migration_fail_at: str | None = None,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> None:
        if migration_fail_at is not None and migration_fail_at not in _MIGRATION_SEAMS:
            raise ValueError("unknown migration failure seam")
        self.path = Path(os.path.abspath(os.fspath(path)))
        self.manifest_root = self.path.with_suffix(".manifests")
        self._state_name = AnchoredDirectory.validate_child_name(self.path.name)
        self._manifest_name = AnchoredDirectory.validate_child_name(self.manifest_root.name)
        self._filesystem_seam = filesystem_seam
        self._state_parent: AnchoredDirectory | None = None
        self._manifest_anchor: AnchoredDirectory | None = None
        self._manifest_stage_anchors: dict[PipelineStage, AnchoredDirectory] = {}
        self._lock_descriptor = -1
        self._durable_bytes: bytes | None = None
        self._poisoned = False
        self.connection: sqlite3.Connection | None = None
        existed = False
        try:
            self._require_snapshot_support()
            self._state_parent = AnchoredDirectory.open(
                self.path.parent,
                create=True,
                filesystem_seam=filesystem_seam,
            )
            self._trip_filesystem_seam("after_state_parent_anchor")
            self._acquire_lock()
            self._trip_filesystem_seam("before_state_read")
            existed = self._state_parent.stat_child(self._state_name) is not None
            raw = self._state_parent.read_bytes(
                self._state_name,
                max_bytes=MAX_STATE_DB_BYTES,
                missing_ok=True,
            )
            existed = raw is not None
            self.connection = self._new_memory_connection()
            if raw is None:
                self._create_current_schema()
                self._persist_startup_snapshot(previous=None)
            else:
                try:
                    self.connection.deserialize(raw)
                    self._durable_bytes = raw
                    version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
                except (MemoryError, OverflowError, sqlite3.Error):
                    raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE) from None
                if version == SCHEMA_VERSION:
                    self._validate_current_schema()
                elif version == 1:
                    self._migrate_v1(migration_fail_at)
                    self._persist_startup_snapshot(previous=raw)
                else:
                    raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)
            self.reconcile_orphan_running_attempts()
        except SafeFailure:
            self.close()
            raise
        except (DurableWriteError, OSError, sqlite3.Error):
            self.close()
            code = (
                ErrorCode.STATE_SCHEMA_INCOMPATIBLE if existed else ErrorCode.STATE_OPERATION_FAILED
            )
            raise SafeFailure(code) from None

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        migration_fail_at: str | None = None,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> SQLiteStateStore:
        return cls(
            path,
            migration_fail_at=migration_fail_at,
            filesystem_seam=filesystem_seam,
        )

    @property
    def _db(self) -> sqlite3.Connection:
        if self.connection is None or self._poisoned:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        return self.connection

    @staticmethod
    def _require_snapshot_support() -> None:
        if not all(
            callable(getattr(sqlite3.Connection, name, None))
            for name in ("serialize", "deserialize")
        ):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        if not all(hasattr(fcntl, name) for name in ("flock", "LOCK_EX", "LOCK_NB")):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)

    @staticmethod
    def _new_memory_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _trip_filesystem_seam(self, name: str) -> None:
        if self._filesystem_seam is not None:
            self._filesystem_seam(name)

    def _acquire_lock(self) -> None:
        assert self._state_parent is not None
        lock_name = AnchoredDirectory.validate_child_name(f".{self._state_name}.lock")
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            descriptor = os.open(
                lock_name,
                flags,
                0o600,
                dir_fd=self._state_parent.descriptor,
            )
            anchored = os.stat(
                lock_name,
                dir_fd=self._state_parent.descriptor,
                follow_symlinks=False,
            )
            opened = os.fstat(descriptor)
            if (anchored.st_dev, anchored.st_ino) != (
                opened.st_dev,
                opened.st_ino,
            ) or not stat_is_private_regular(opened):
                raise OSError("invalid lock file")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_descriptor = descriptor
        except (BlockingIOError, OSError):
            if "descriptor" in locals():
                os.close(descriptor)
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _serialize(self, connection: sqlite3.Connection) -> bytes:
        try:
            payload = connection.serialize()
        except (OverflowError, sqlite3.Error):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        if type(payload) is not bytes or len(payload) > MAX_STATE_DB_BYTES:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        return payload

    def _persist_startup_snapshot(self, *, previous: bytes | None) -> None:
        assert self._state_parent is not None
        payload = self._serialize(self._db)
        try:
            self._trip_filesystem_seam("before_state_persist")
            if previous is None:
                self._state_parent.atomic_write(
                    self._state_name,
                    payload,
                    max_bytes=MAX_STATE_DB_BYTES,
                    seam_prefix="state_",
                )
            else:
                self._state_parent.atomic_write(
                    self._state_name,
                    payload,
                    max_bytes=MAX_STATE_DB_BYTES,
                    restore_bytes=previous,
                    seam_prefix="state_",
                )
        except (DurableWriteError, OSError):
            self._poison()
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        self._durable_bytes = payload

    def _create_current_schema(self) -> None:
        try:
            self._db.execute("BEGIN IMMEDIATE")
            for statement in _schema_statements():
                self._db.execute(statement)
            self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._validate_current_schema()
            self._db.commit()
        except SafeFailure:
            self._db.rollback()
            raise
        except sqlite3.Error:
            self._db.rollback()
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _validate_current_schema(self) -> None:
        try:
            version = self._db.execute("PRAGMA user_version").fetchone()
            if version is None or int(version[0]) != SCHEMA_VERSION:
                raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)
            quick_check = self._db.execute("PRAGMA quick_check").fetchall()
            if len(quick_check) != 1 or tuple(quick_check[0]) != ("ok",):
                raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)

            named_objects = tuple(
                tuple(row)
                for row in self._db.execute(
                    """SELECT type, name, tbl_name FROM sqlite_master
                       WHERE name NOT LIKE 'sqlite_%'
                       ORDER BY type, name"""
                )
            )
            if named_objects != _EXPECTED_NAMED_SCHEMA_OBJECTS:
                raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)

            for name, expected_sql in _EXPECTED_SCHEMA_SQL.items():
                row = self._db.execute(
                    "SELECT sql FROM sqlite_master WHERE name = ?", (name,)
                ).fetchone()
                if (
                    row is None
                    or type(row["sql"]) is not str
                    or _normalize_schema_sql(row["sql"]) != expected_sql
                ):
                    raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)

            for table, expected_columns in _EXPECTED_COLUMNS.items():
                columns = tuple(
                    _ColumnDescriptor(
                        int(row["cid"]),
                        str(row["name"]),
                        str(row["type"]),
                        int(row["notnull"]),
                        row["dflt_value"],
                        int(row["pk"]),
                    )
                    for row in self._db.execute(f'PRAGMA table_info("{table}")').fetchall()
                )
                if columns != expected_columns:
                    raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)

                foreign_keys = tuple(
                    _ForeignKeyDescriptor(
                        int(row["id"]),
                        int(row["seq"]),
                        str(row["table"]),
                        str(row["from"]),
                        str(row["to"]),
                        str(row["on_update"]),
                        str(row["on_delete"]),
                        str(row["match"]),
                    )
                    for row in self._db.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
                )
                if foreign_keys != _EXPECTED_FOREIGN_KEYS[table]:
                    raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)

                indexes: list[_IndexDescriptor] = []
                for row in self._db.execute(f'PRAGMA index_list("{table}")').fetchall():
                    index_name = str(row["name"])
                    index_columns = tuple(
                        (int(item["seqno"]), int(item["cid"]), str(item["name"]))
                        for item in self._db.execute(
                            f'PRAGMA index_info("{index_name}")'
                        ).fetchall()
                    )
                    indexes.append(
                        _IndexDescriptor(
                            index_name,
                            int(row["unique"]),
                            str(row["origin"]),
                            int(row["partial"]),
                            index_columns,
                        )
                    )
                if tuple(indexes) != _EXPECTED_INDEXES[table]:
                    raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)

            if self._db.execute("PRAGMA foreign_key_check").fetchall():
                raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)
        except SafeFailure:
            raise
        except (KeyError, TypeError, ValueError, sqlite3.Error):
            raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE) from None

    def _migrate_v1(self, fail_at: str | None) -> None:
        created_manifests: list[Path] = []
        try:
            self._validate_v1_source_rows()
            self._db.execute("BEGIN IMMEDIATE")
            for statement in _schema_statements("_v2"):
                self._db.execute(statement)
            self._trip_migration_seam(fail_at, "after_schema")

            self._db.execute(
                """INSERT INTO runs_v2
                   (run_id, schema_version, subject_id, fixture_hash, producer_version,
                    retry_policy_version, identity_state, execution_mode, status,
                    created_at, updated_at, error_code, error_summary, reused_stage_count)
                   SELECT r.run_id, '1', r.subject_id, NULL,
                          (SELECT MIN(a.producer_version) FROM stage_attempts a
                           WHERE a.run_id = r.run_id),
                          (SELECT MIN(a.retry_policy_version) FROM stage_attempts a
                           WHERE a.run_id = r.run_id),
                          'legacy_unbound', r.execution_mode, r.status, r.created_at,
                          r.updated_at, r.error_code, r.error_summary, 0
                   FROM runs r"""
            )
            self._db.execute(
                """INSERT INTO stage_attempts_v2
                   SELECT attempt_id, run_id, subject_id, stage, stage_index, attempt_no,
                          status, input_hash, producer_version, retry_policy_version,
                          reusable_key_digest, started_at, finished_at, prompt_version,
                          policy_version, model_id, request_id, latency_ms, prompt_tokens,
                          completion_tokens, total_tokens, error_code, error_summary, retryable
                   FROM stage_attempts"""
            )

            rows = self._db.execute(
                """SELECT r.*, a.attempt_no, a.input_hash, a.retry_policy_version,
                          a.prompt_version, a.policy_version, a.model_id, a.request_id
                   FROM stage_results r
                   JOIN stage_attempts a USING (attempt_id)
                   ORDER BY r.stage_index"""
            ).fetchall()
            for row in rows:
                stage = PipelineStage(str(row["stage"]))
                payload = json.loads(str(row["output_json"]))
                producer_version = str(row["producer_version"])
                if ("1", producer_version) not in SUPPORTED_PRODUCER_SCHEMAS:
                    raise ValueError("unsupported migrated producer identity")
                provisional = StageEnvelope(
                    schema_version="1",
                    result_row_id=make_result_row_id(run_id=str(row["run_id"]), stage=stage),
                    result_id=str(row["result_id"]),
                    run_id=str(row["run_id"]),
                    attempt_id=str(row["attempt_id"]),
                    attempt_no=int(row["attempt_no"]),
                    subject_id=str(row["subject_id"]),
                    stage=stage,
                    stage_index=int(row["stage_index"]),
                    input_hash=str(row["input_hash"]),
                    output_hash=str(row["output_hash"]),
                    producer_version=producer_version,
                    retry_policy_version=str(row["retry_policy_version"]),
                    prompt_version=row["prompt_version"],
                    policy_version=row["policy_version"],
                    model_id=row["model_id"],
                    request_id=row["request_id"],
                    created_at=str(row["created_at"]),
                    payload=payload,
                    manifest_hash=None,
                )
                envelope = provisional.model_copy(
                    update={"manifest_hash": stage_manifest_hash(provisional)}
                )
                manifest_path = self._write_manifest(envelope)
                created_manifests.append(manifest_path)
                manifest_locator = self._manifest_locator(
                    envelope.stage, str(envelope.manifest_hash)
                )
                self._db.execute(
                    """INSERT INTO stage_results_v2
                       (result_row_id, result_id, attempt_id, run_id, schema_version,
                        subject_id, stage,
                        stage_index, output_json, output_hash, producer_version,
                        manifest_hash, manifest_path, created_at)
                       VALUES (?, ?, ?, ?, '1', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        envelope.result_row_id,
                        envelope.result_id,
                        envelope.attempt_id,
                        envelope.run_id,
                        envelope.subject_id,
                        envelope.stage.value,
                        envelope.stage_index,
                        canonical_json_bytes(envelope.payload).decode("utf-8"),
                        envelope.output_hash,
                        envelope.producer_version,
                        envelope.manifest_hash,
                        manifest_locator,
                        envelope.created_at,
                    ),
                )

            self._db.execute(
                """INSERT INTO checkpoints_v2
                   SELECT c.run_id, c.subject_id, c.stage, c.stage_index,
                          r.result_row_id, c.result_id, c.output_hash, r.manifest_hash,
                          r.manifest_path, c.updated_at
                   FROM checkpoints c JOIN stage_results_v2 r USING (result_id)"""
            )
            self._trip_migration_seam(fail_at, "after_copy")
            self._validate_migration_copy()
            self._trip_migration_seam(fail_at, "after_validation")

            for table in ("checkpoints", "stage_results", "stage_attempts", "runs"):
                self._db.execute(f"DROP TABLE {table}")
            for statement in _schema_statements():
                self._db.execute(statement)
            for table in ("runs", "stage_attempts", "stage_results", "checkpoints"):
                self._db.execute(f"INSERT INTO {table} SELECT * FROM {table}_v2")
            for table in (
                "checkpoints_v2",
                "stage_results_v2",
                "stage_attempts_v2",
                "runs_v2",
            ):
                self._db.execute(f"DROP TABLE {table}")
            self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._validate_current_schema()
            self._db.commit()
        except Exception:
            self._db.rollback()
            self._remove_migration_manifests(created_manifests)
            raise SafeFailure(ErrorCode.STATE_SCHEMA_MIGRATION_ERROR) from None

    @staticmethod
    def _trip_migration_seam(configured: str | None, current: str) -> None:
        if configured == current:
            raise RuntimeError("forced migration seam")

    @staticmethod
    def _validated_diagnostic(
        error_code: object, error_summary: object
    ) -> tuple[str | None, str | None]:
        if error_code is None and error_summary is None:
            return None, None
        if type(error_code) is not str or type(error_summary) is not str:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        try:
            code = ErrorCode(error_code)
        except ValueError:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None
        if error_summary != ERROR_SUMMARIES[code]:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        return code.value, ERROR_SUMMARIES[code]

    @classmethod
    def _persisted_run_record(cls, row: Mapping[str, object] | sqlite3.Row) -> PersistedRunRecord:
        try:
            error_code, error_summary = cls._validated_diagnostic(
                row["error_code"], row["error_summary"]
            )
            values = {
                "run_id": row["run_id"],
                "schema_version": row["schema_version"],
                "subject_id": row["subject_id"],
                "fixture_hash": row["fixture_hash"],
                "producer_version": row["producer_version"],
                "retry_policy_version": row["retry_policy_version"],
                "identity_state": row["identity_state"],
                "execution_mode": ExecutionMode(str(row["execution_mode"])),
                "status": RunStatus(str(row["status"])),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "error_code": error_code,
                "error_summary": error_summary,
                "reused_stage_count": row["reused_stage_count"],
            }
            return PersistedRunRecord.model_validate(values)
        except SafeFailure:
            raise
        except (IndexError, KeyError, ValidationError, ValueError, TypeError):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None

    @classmethod
    def _persisted_attempt_record(
        cls, row: Mapping[str, object] | sqlite3.Row
    ) -> PersistedAttemptRecord:
        try:
            error_code, error_summary = cls._validated_diagnostic(
                row["error_code"], row["error_summary"]
            )
            retryable = row["retryable"]
            if type(retryable) is not int or retryable not in (0, 1):
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            values = {
                "attempt_id": row["attempt_id"],
                "run_id": row["run_id"],
                "subject_id": row["subject_id"],
                "stage": PipelineStage(str(row["stage"])),
                "stage_index": row["stage_index"],
                "attempt_no": row["attempt_no"],
                "status": AttemptStatus(str(row["status"])),
                "input_hash": row["input_hash"],
                "producer_version": row["producer_version"],
                "retry_policy_version": row["retry_policy_version"],
                "reusable_key_digest": row["reusable_key_digest"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "prompt_version": row["prompt_version"],
                "policy_version": row["policy_version"],
                "model_id": row["model_id"],
                "request_id": row["request_id"],
                "latency_ms": row["latency_ms"],
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "total_tokens": row["total_tokens"],
                "error_code": error_code,
                "error_summary": error_summary,
                "retryable": bool(retryable),
            }
            record = PersistedAttemptRecord.model_validate(values)
            if record.producer_version == "fixture-v1" and any(
                value is not None
                for value in (
                    record.prompt_version,
                    record.policy_version,
                    record.model_id,
                    record.request_id,
                    record.latency_ms,
                    record.prompt_tokens,
                    record.completion_tokens,
                    record.total_tokens,
                )
            ):
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            return record
        except SafeFailure:
            raise
        except (IndexError, KeyError, ValidationError, ValueError, TypeError):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None

    @classmethod
    def _persisted_checkpoint_record(
        cls, row: Mapping[str, object] | sqlite3.Row
    ) -> PersistedCheckpointRecord:
        try:
            record = PersistedCheckpointRecord.model_validate(
                {
                    "run_id": row["run_id"],
                    "subject_id": row["subject_id"],
                    "stage": PipelineStage(str(row["stage"])),
                    "stage_index": row["stage_index"],
                    "result_row_id": row["result_row_id"],
                    "result_id": row["result_id"],
                    "output_hash": row["output_hash"],
                    "manifest_hash": row["manifest_hash"],
                    "manifest_path": row["manifest_path"],
                    "updated_at": row["updated_at"],
                }
            )
            expected = cls._manifest_locator(record.stage, record.manifest_hash)
            if record.manifest_path != expected:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            return record
        except SafeFailure:
            raise
        except (IndexError, KeyError, ValidationError, ValueError, TypeError):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None

    def _validate_v1_source_rows(self) -> None:
        attempts = self._db.execute("SELECT * FROM stage_attempts").fetchall()
        for attempt in attempts:
            self._persisted_attempt_record(attempt)

        for run in self._db.execute("SELECT * FROM runs").fetchall():
            facts = self._db.execute(
                """SELECT COUNT(DISTINCT producer_version) AS producer_count,
                          COUNT(DISTINCT retry_policy_version) AS retry_count,
                          MIN(producer_version) AS producer_version,
                          MIN(retry_policy_version) AS retry_policy_version
                   FROM stage_attempts WHERE run_id = ?""",
                (run["run_id"],),
            ).fetchone()
            if facts is None or int(facts["producer_count"]) != 1 or int(facts["retry_count"]) != 1:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            self._persisted_run_record(
                {
                    "run_id": run["run_id"],
                    "schema_version": "1",
                    "subject_id": run["subject_id"],
                    "fixture_hash": None,
                    "producer_version": facts["producer_version"],
                    "retry_policy_version": facts["retry_policy_version"],
                    "identity_state": "legacy_unbound",
                    "execution_mode": run["execution_mode"],
                    "status": run["status"],
                    "created_at": run["created_at"],
                    "updated_at": run["updated_at"],
                    "error_code": run["error_code"],
                    "error_summary": run["error_summary"],
                    "reused_stage_count": 0,
                }
            )

    def _validate_migration_copy(self) -> None:
        for source, target in (
            ("runs", "runs_v2"),
            ("stage_attempts", "stage_attempts_v2"),
            ("stage_results", "stage_results_v2"),
            ("checkpoints", "checkpoints_v2"),
        ):
            source_count = self._db.execute(f"SELECT COUNT(*) FROM {source}").fetchone()[0]
            target_count = self._db.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
            if source_count != target_count:
                raise ValueError("migration row count mismatch")

        for row in self._db.execute("SELECT * FROM stage_attempts_v2"):
            self._persisted_attempt_record(row)
            expected = reusable_key_digest(
                subject_id=str(row["subject_id"]),
                stage=PipelineStage(str(row["stage"])),
                input_hash=str(row["input_hash"]),
                producer_version=str(row["producer_version"]),
                retry_policy_version=str(row["retry_policy_version"]),
            )
            if expected != row["reusable_key_digest"]:
                raise ValueError("migration reusable digest mismatch")

        for run in self._db.execute("SELECT * FROM runs_v2"):
            self._persisted_run_record(run)
            facts = self._db.execute(
                """SELECT COUNT(DISTINCT producer_version) AS producer_count,
                          COUNT(DISTINCT retry_policy_version) AS retry_count,
                          MIN(producer_version) AS producer_version,
                          MIN(retry_policy_version) AS retry_policy_version
                   FROM stage_attempts_v2 WHERE run_id = ?""",
                (run["run_id"],),
            ).fetchone()
            if (
                int(facts["producer_count"]) != 1
                or int(facts["retry_count"]) != 1
                or run["producer_version"] != facts["producer_version"]
                or run["retry_policy_version"] != facts["retry_policy_version"]
                or run["fixture_hash"] is not None
                or run["identity_state"] != "legacy_unbound"
            ):
                raise ValueError("migration run identity facts are ambiguous")

        for row in self._db.execute(
            """SELECT r.*, a.input_hash, a.prompt_version, a.policy_version, a.model_id
               FROM stage_results_v2 r JOIN stage_attempts_v2 a USING (attempt_id)"""
        ):
            stage = PipelineStage(str(row["stage"]))
            payload = json.loads(str(row["output_json"]))
            expected_output = stage_output_hash(
                schema_version="1",
                subject_id=str(row["subject_id"]),
                stage=stage,
                producer_version=str(row["producer_version"]),
                prompt_version=row["prompt_version"],
                policy_version=row["policy_version"],
                model_id=row["model_id"],
                payload=payload,
            )
            expected_result = make_result_id(
                subject_id=str(row["subject_id"]),
                stage=stage,
                input_hash=str(row["input_hash"]),
                producer_version=str(row["producer_version"]),
                output_hash=str(row["output_hash"]),
            )
            if expected_output != row["output_hash"] or expected_result != row["result_id"]:
                raise ValueError("migration result identity mismatch")
            expected_row = make_result_row_id(run_id=str(row["run_id"]), stage=stage)
            if expected_row != row["result_row_id"]:
                raise ValueError("migration result row identity mismatch")
            self._verify_manifest_row(row)
        for checkpoint in self._db.execute("SELECT * FROM checkpoints_v2"):
            self._persisted_checkpoint_record(checkpoint)
        if self._db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("migration foreign key failure")

    def _remove_migration_manifests(self, paths: Iterable[Path]) -> None:
        stages: set[PipelineStage] = set()
        for path in paths:
            try:
                relative = path.relative_to(self.manifest_root)
                stage = PipelineStage(relative.parts[0])
                if len(relative.parts) != 2:
                    continue
                anchor = self._manifest_stage_anchor(stage, create=False)
                anchor.unlink(relative.parts[1], missing_ok=True, sync=True)
                stages.add(stage)
            except (DurableWriteError, OSError, ValueError):
                pass
        for stage in stages:
            anchor = self._manifest_stage_anchors.pop(stage, None)
            if anchor is not None:
                anchor.close()
            try:
                if self._manifest_anchor is not None:
                    self._manifest_anchor.remove_child_directory(stage.value, missing_ok=True)
            except DurableWriteError:
                pass
        if self._manifest_anchor is not None:
            self._manifest_anchor.close()
            self._manifest_anchor = None
        try:
            if self._state_parent is not None:
                self._state_parent.remove_child_directory(self._manifest_name, missing_ok=True)
        except DurableWriteError:
            pass

    def create_run(self, run_id: str, identity: RunIdentity, created_at: str) -> None:
        self._write_transaction(
            """INSERT INTO runs
               (run_id, schema_version, subject_id, fixture_hash, producer_version,
                retry_policy_version, identity_state, execution_mode, status,
                created_at, updated_at, error_code, error_summary, reused_stage_count)
               VALUES (?, ?, ?, ?, ?, ?, 'bound', 'dry_run', 'running', ?, ?,
                       NULL, NULL, 0)""",
            (
                run_id,
                identity.schema_version,
                identity.subject_id,
                identity.fixture_hash,
                identity.producer_version,
                identity.retry_policy_version,
                created_at,
                created_at,
            ),
        )

    def find_resumable_run(self, identity: RunIdentity) -> RunRecord | None:
        try:
            row = self._db.execute(
                """SELECT * FROM runs INDEXED BY idx_runs_resumable_identity
                   WHERE schema_version = ? AND subject_id = ? AND fixture_hash = ?
                     AND producer_version = ? AND retry_policy_version = ?
                     AND identity_state = 'bound'
                     AND status IN ('running', 'interrupted')
                   ORDER BY updated_at DESC, run_id DESC LIMIT 1""",
                (
                    identity.schema_version,
                    identity.subject_id,
                    identity.fixture_hash,
                    identity.producer_version,
                    identity.retry_policy_version,
                ),
            ).fetchone()
            if row is None:
                return None
            record = self._run_record(row)
            self._identity_chain_matches(
                self._db,
                record.run_id,
                identity,
                allow_first_input_mismatch=False,
                require_evidence=False,
            )
            return record
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def bind_legacy_run(self, expected: RunIdentity) -> RunRecord | None:
        """Bind one canonically proven v1 candidate without trusting missing facts."""

        try:
            candidates = self._db.execute(
                """SELECT run_id FROM runs
                   WHERE schema_version = ? AND subject_id = ?
                     AND producer_version = ? AND retry_policy_version = ?
                     AND identity_state = 'legacy_unbound'
                     AND status IN ('running', 'interrupted')
                   ORDER BY updated_at DESC, run_id DESC LIMIT ?""",
                (
                    expected.schema_version,
                    expected.subject_id,
                    expected.producer_version,
                    expected.retry_policy_version,
                    MAX_LEGACY_BIND_CANDIDATES,
                ),
            ).fetchall()
            selected: str | None = None
            for candidate in candidates:
                run_id = str(candidate["run_id"])
                if self._identity_chain_matches(
                    self._db,
                    run_id,
                    expected,
                    allow_first_input_mismatch=True,
                    require_evidence=True,
                ):
                    selected = run_id
                    break
            if selected is None:
                return None

            def bind(database: sqlite3.Connection) -> RunRecord:
                row = database.execute(
                    """SELECT * FROM runs WHERE run_id = ?
                       AND identity_state = 'legacy_unbound'""",
                    (selected,),
                ).fetchone()
                if row is None or not self._identity_chain_matches(
                    database,
                    selected,
                    expected,
                    allow_first_input_mismatch=False,
                    require_evidence=True,
                ):
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                updated = database.execute(
                    """UPDATE runs SET fixture_hash = ?, identity_state = 'bound'
                       WHERE run_id = ? AND identity_state = 'legacy_unbound'
                         AND fixture_hash IS NULL""",
                    (expected.fixture_hash, selected),
                )
                if updated.rowcount != 1:
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                bound = database.execute(
                    "SELECT * FROM runs WHERE run_id = ?", (selected,)
                ).fetchone()
                return self._run_record(bound)

            return self._snapshot_transaction(bind)
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def latest_checkpoint(self, run_id: str) -> Checkpoint | None:
        try:
            row = self._db.execute(
                """SELECT run_id, subject_id, stage, stage_index, result_row_id,
                          result_id, output_hash, manifest_hash, manifest_path, updated_at
                   FROM checkpoints WHERE run_id = ? ORDER BY stage_index DESC LIMIT 1""",
                (run_id,),
            ).fetchone()
            if row is not None:
                return self._persisted_checkpoint_record(row)
            return None
        except (ValidationError, ValueError, TypeError):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _identity_chain_matches(
        self,
        database: sqlite3.Connection,
        run_id: str,
        identity: RunIdentity,
        *,
        allow_first_input_mismatch: bool,
        require_evidence: bool,
    ) -> bool:
        """Verify every fact needed for exact reuse or one-time legacy binding."""

        try:
            rows = database.execute(
                """SELECT r.*, a.attempt_no, a.status AS attempt_status,
                          a.subject_id AS attempt_subject, a.stage AS attempt_stage,
                          a.stage_index AS attempt_stage_index,
                          a.input_hash AS attempt_input_hash,
                          a.producer_version AS attempt_producer,
                          a.retry_policy_version AS attempt_retry_policy,
                          a.reusable_key_digest,
                          c.subject_id AS checkpoint_subject,
                          c.stage AS checkpoint_stage,
                          c.stage_index AS checkpoint_stage_index,
                          c.result_row_id AS checkpoint_result_row_id,
                          c.result_id AS checkpoint_result_id,
                          c.output_hash AS checkpoint_output_hash,
                          c.manifest_hash AS checkpoint_manifest_hash
                   FROM stage_results r JOIN stage_attempts a USING (attempt_id)
                   LEFT JOIN checkpoints c
                     ON c.run_id = r.run_id AND c.stage = r.stage
                   WHERE r.run_id = ? ORDER BY r.stage_index""",
                (run_id,),
            ).fetchall()
            if require_evidence and not rows:
                return False
            previous_output_hash: str | None = None
            for expected_index, row in enumerate(rows):
                stage = PipelineStage(str(row["stage"]))
                if (
                    int(row["stage_index"]) != expected_index
                    or stage is not tuple(PipelineStage)[expected_index]
                ):
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                envelope = self._verify_manifest_row(row)
                stage_input = StageInput(
                    schema_version=identity.schema_version,
                    execution_mode=ExecutionMode.DRY_RUN,
                    subject_id=identity.subject_id,
                    stage=stage,
                    previous_output_hash=previous_output_hash,
                    fixture_hash=identity.fixture_hash if expected_index == 0 else None,
                )
                expected_input = stage_input_hash(stage_input)
                if row["attempt_input_hash"] != expected_input:
                    if expected_index == 0 and allow_first_input_mismatch:
                        return False
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                expected_digest = reusable_key_digest(
                    subject_id=identity.subject_id,
                    stage=stage_input.stage,
                    input_hash=expected_input,
                    producer_version=identity.producer_version,
                    retry_policy_version=identity.retry_policy_version,
                )
                expected_result = make_result_id(
                    subject_id=identity.subject_id,
                    stage=stage,
                    input_hash=expected_input,
                    producer_version=identity.producer_version,
                    output_hash=envelope.output_hash,
                    retry_policy_version=(
                        None if identity.schema_version == "1" else identity.retry_policy_version
                    ),
                )
                if (
                    row["attempt_status"] != "succeeded"
                    or row["attempt_subject"] != identity.subject_id
                    or row["attempt_stage"] != stage.value
                    or int(row["attempt_stage_index"]) != expected_index
                    or int(row["attempt_no"]) != envelope.attempt_no
                    or row["attempt_producer"] != identity.producer_version
                    or row["attempt_retry_policy"] != identity.retry_policy_version
                    or row["reusable_key_digest"] != expected_digest
                    or row["result_id"] != expected_result
                    or row["checkpoint_subject"] != identity.subject_id
                    or row["checkpoint_stage"] != stage.value
                    or int(row["checkpoint_stage_index"]) != expected_index
                    or row["checkpoint_result_row_id"] != row["result_row_id"]
                    or row["checkpoint_result_id"] != row["result_id"]
                    or row["checkpoint_output_hash"] != row["output_hash"]
                    or row["checkpoint_manifest_hash"] != row["manifest_hash"]
                ):
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                previous_output_hash = envelope.output_hash
            return True
        except SafeFailure:
            raise
        except (IndexError, TypeError, ValueError):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    @classmethod
    def _run_record(cls, row: sqlite3.Row) -> RunRecord:
        return cls._persisted_run_record(row)

    def set_reused_stage_count(self, run_id: str, count: int) -> None:
        self._write_transaction(
            "UPDATE runs SET reused_stage_count = ? WHERE run_id = ?", (count, run_id)
        )

    def abandon_stale_running(self, run_id: str, stage: PipelineStage, finished_at: str) -> None:
        summary = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED).as_dict()["summary"]
        self._write_transaction(
            """UPDATE stage_attempts
               SET status = 'abandoned', finished_at = ?, error_code = ?,
                   error_summary = ?, retryable = 1
               WHERE run_id = ? AND stage = ? AND status = 'running'""",
            (
                finished_at,
                ErrorCode.PIPELINE_INTERRUPTED.value,
                summary,
                run_id,
                stage.value,
            ),
        )

    def retry_attempt_count(self, reusable_digest: str) -> int:
        try:
            row = self._db.execute(
                """SELECT COUNT(*) FROM stage_attempts INDEXED BY idx_attempts_reusable
                   WHERE reusable_key_digest = ?
                     AND ((status = 'failed' AND retryable = 1) OR status = 'abandoned')""",
                (reusable_digest,),
            ).fetchone()
            return int(row[0])
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def has_permanent_failure(self, reusable_digest: str) -> bool:
        try:
            row = self._db.execute(
                """SELECT 1 FROM stage_attempts INDEXED BY idx_attempts_reusable
                   WHERE reusable_key_digest = ? AND status = 'failed' AND retryable = 0
                   LIMIT 1""",
                (reusable_digest,),
            ).fetchone()
            return row is not None
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def next_attempt_no(self, run_id: str, stage: PipelineStage, reusable_digest: str) -> int:
        del reusable_digest
        try:
            row = self._db.execute(
                """SELECT COALESCE(MAX(attempt_no), 0) + 1 FROM stage_attempts
                   WHERE run_id = ? AND stage = ?""",
                (run_id, stage.value),
            ).fetchone()
            return int(row[0])
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def start_attempt(self, attempt: StageAttempt) -> None:
        usage = attempt.token_usage
        self._write_transaction(
            """INSERT INTO stage_attempts (
                   attempt_id, run_id, subject_id, stage, stage_index, attempt_no, status,
                   input_hash, producer_version, retry_policy_version, reusable_key_digest,
                   started_at, finished_at, prompt_version, policy_version, model_id,
                   request_id, latency_ms, prompt_tokens, completion_tokens, total_tokens,
                   error_code, error_summary, retryable
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt.attempt_id,
                attempt.run_id,
                attempt.subject_id,
                attempt.stage.value,
                attempt.stage_index,
                attempt.attempt_no,
                attempt.status.value,
                attempt.input_hash,
                attempt.producer_version,
                attempt.retry_policy_version,
                attempt.reusable_key_digest,
                attempt.started_at,
                attempt.finished_at,
                attempt.prompt_version,
                attempt.policy_version,
                attempt.model_id,
                attempt.request_id,
                attempt.latency_ms,
                usage.prompt_tokens if usage else None,
                usage.completion_tokens if usage else None,
                usage.total_tokens if usage else None,
                attempt.error_code,
                attempt.error_summary,
                int(attempt.retryable),
            ),
        )

    def complete_stage(self, envelope: StageEnvelope) -> None:
        if envelope.manifest_hash is None:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        manifest_path = self._write_manifest(envelope)
        self._commit_success(envelope, manifest_path)

    def _write_manifest(self, envelope: StageEnvelope) -> Path:
        if envelope.manifest_hash is None:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        if (
            envelope.schema_version,
            envelope.producer_version,
        ) not in SUPPORTED_PRODUCER_SCHEMAS:
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
        try:
            payload = validate_manifest_bytes(canonical_json_bytes(envelope))
        except (OverflowError, TypeError, ValueError):
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID) from None
        target = self._manifest_path(envelope.stage, envelope.manifest_hash)
        try:
            anchor = self._manifest_stage_anchor(envelope.stage, create=True)
            name = target.name
            if anchor.stat_child(name) is not None:
                existing = anchor.read_bytes(name, max_bytes=MAX_MANIFEST_BYTES)
                if existing != payload:
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                return target
            self._trip_filesystem_seam("before_manifest_write")
            anchor.atomic_write(
                name,
                payload,
                max_bytes=MAX_MANIFEST_BYTES,
                seam_prefix="manifest_",
            )
            self._trip_filesystem_seam("after_manifest_durable")
            return target
        except SafeFailure:
            raise
        except (DurableWriteError, OSError):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _commit_success(self, envelope: StageEnvelope, manifest_path: Path) -> None:
        del manifest_path
        if envelope.manifest_hash is None:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        manifest_locator = self._manifest_locator(envelope.stage, envelope.manifest_hash)

        def mutate(database: sqlite3.Connection) -> None:
            run = database.execute(
                "SELECT status FROM runs WHERE run_id = ?", (envelope.run_id,)
            ).fetchone()
            previous = database.execute(
                "SELECT MAX(stage_index) FROM checkpoints WHERE run_id = ?",
                (envelope.run_id,),
            ).fetchone()
            expected_index = 0 if previous[0] is None else int(previous[0]) + 1
            if (
                run is None
                or str(run["status"]) != RunStatus.RUNNING.value
                or envelope.stage_index != expected_index
                or tuple(PipelineStage)[envelope.stage_index] is not envelope.stage
            ):
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            database.execute(
                """INSERT INTO stage_results
                   (result_row_id, result_id, attempt_id, run_id, schema_version,
                    subject_id, stage,
                    stage_index, output_json, output_hash, producer_version, manifest_hash,
                    manifest_path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    envelope.result_row_id,
                    envelope.result_id,
                    envelope.attempt_id,
                    envelope.run_id,
                    envelope.schema_version,
                    envelope.subject_id,
                    envelope.stage.value,
                    envelope.stage_index,
                    canonical_json_bytes(envelope.payload).decode("utf-8"),
                    envelope.output_hash,
                    envelope.producer_version,
                    envelope.manifest_hash,
                    manifest_locator,
                    envelope.created_at,
                ),
            )
            updated = database.execute(
                """UPDATE stage_attempts SET status = 'succeeded', finished_at = ?
                   WHERE attempt_id = ? AND status = 'running'""",
                (envelope.created_at, envelope.attempt_id),
            )
            if updated.rowcount != 1:
                raise sqlite3.IntegrityError("attempt was not running")
            database.execute(
                """INSERT INTO checkpoints
                   (run_id, subject_id, stage, stage_index, result_row_id, result_id,
                    output_hash,
                    manifest_hash, manifest_path, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    envelope.run_id,
                    envelope.subject_id,
                    envelope.stage.value,
                    envelope.stage_index,
                    envelope.result_row_id,
                    envelope.result_id,
                    envelope.output_hash,
                    envelope.manifest_hash,
                    manifest_locator,
                    envelope.created_at,
                ),
            )
            database.execute(
                "UPDATE runs SET updated_at = ? WHERE run_id = ?",
                (envelope.created_at, envelope.run_id),
            )

        self._snapshot_transaction(mutate)

    def verify_completed_results(self, run_id: str, count: int) -> None:
        try:
            rows = self._db.execute(
                """SELECT * FROM stage_results WHERE run_id = ? ORDER BY stage_index""",
                (run_id,),
            ).fetchall()
            if len(rows) != count:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            for expected_index, row in enumerate(rows):
                if int(row["stage_index"]) != expected_index:
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                self._verify_manifest_row(row)
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _verify_manifest_row(self, row: sqlite3.Row) -> StageEnvelope:
        try:
            stage = PipelineStage(str(row["stage"]))
            expected_path = self._manifest_path(stage, str(row["manifest_hash"]))
            expected_locator = self._manifest_locator(stage, str(row["manifest_hash"]))
            if str(row["manifest_path"]) != expected_locator:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            raw = self._read_manifest_bytes(expected_path)
            envelope = StageEnvelope.model_validate_json(raw, strict=True)
            if (
                (envelope.schema_version, envelope.producer_version)
                not in SUPPORTED_PRODUCER_SCHEMAS
                or str(row["schema_version"]) != envelope.schema_version
                or str(row["producer_version"]) != envelope.producer_version
                or str(row["run_id"]) != envelope.run_id
                or str(row["result_row_id"]) != envelope.result_row_id
                or str(row["attempt_id"]) != envelope.attempt_id
                or str(row["subject_id"]) != envelope.subject_id
                or stage is not envelope.stage
                or int(row["stage_index"]) != envelope.stage_index
            ):
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            if envelope.manifest_hash != row["manifest_hash"]:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            if stage_manifest_hash(envelope) != envelope.manifest_hash:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            expected_output = stage_output_hash(
                schema_version=envelope.schema_version,
                subject_id=envelope.subject_id,
                stage=envelope.stage,
                producer_version=envelope.producer_version,
                prompt_version=envelope.prompt_version,
                policy_version=envelope.policy_version,
                model_id=envelope.model_id,
                payload=envelope.payload,
            )
            if expected_output != envelope.output_hash or expected_output != row["output_hash"]:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            if envelope.result_id != row["result_id"]:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            if envelope.result_row_id != make_result_row_id(
                run_id=envelope.run_id, stage=envelope.stage
            ):
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            return envelope
        except SafeFailure:
            raise
        except (OSError, ValidationError, ValueError, TypeError, KeyError):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None

    def fail_attempt(
        self,
        attempt_id: str,
        run_id: str,
        failure: SafeFailure,
        finished_at: str,
        *,
        retryable: bool,
    ) -> None:
        def mutate(database: sqlite3.Connection) -> None:
            database.execute(
                """UPDATE stage_attempts
                   SET status = 'failed', finished_at = ?, error_code = ?, error_summary = ?,
                       retryable = ?
                   WHERE attempt_id = ?""",
                (
                    finished_at,
                    failure.code.value,
                    failure.as_dict()["summary"],
                    int(retryable),
                    attempt_id,
                ),
            )
            database.execute(
                """UPDATE runs SET status = 'interrupted', updated_at = ?, error_code = ?,
                          error_summary = ? WHERE run_id = ?""",
                (finished_at, failure.code.value, failure.as_dict()["summary"], run_id),
            )

        self._snapshot_transaction(mutate)

    def reconcile_orphan_running_attempts(self) -> None:
        """Deterministically close attempts left running by an indeterminate failure."""

        failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
        summary = failure.as_dict()["summary"]
        try:
            rows = self._db.execute(
                """SELECT a.run_id, MAX(a.started_at) AS last_started_at
                   FROM stage_attempts a JOIN runs r USING (run_id)
                   WHERE a.status = 'running' AND r.status = 'running'
                   GROUP BY a.run_id ORDER BY a.run_id"""
            ).fetchall()
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        if not rows:
            return

        def mutate(database: sqlite3.Connection) -> None:
            for row in rows:
                run_id = str(row["run_id"])
                updated_attempts = database.execute(
                    """UPDATE stage_attempts
                       SET status = 'abandoned', finished_at = started_at,
                           error_code = ?, error_summary = ?, retryable = 1
                       WHERE run_id = ? AND status = 'running'""",
                    (failure.code.value, summary, run_id),
                )
                updated_run = database.execute(
                    """UPDATE runs
                       SET status = 'interrupted', updated_at = ?, error_code = ?,
                           error_summary = ?
                       WHERE run_id = ? AND status = 'running'""",
                    (
                        str(row["last_started_at"]),
                        failure.code.value,
                        summary,
                        run_id,
                    ),
                )
                if updated_attempts.rowcount < 1 or updated_run.rowcount != 1:
                    raise sqlite3.IntegrityError("orphan reconciliation lost its target")

        self._snapshot_transaction(mutate)

    def set_run_status(
        self,
        run_id: str,
        status: str,
        updated_at: str,
        failure: SafeFailure | None = None,
    ) -> None:
        def mutate(database: sqlite3.Connection) -> None:
            row = database.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            current = RunStatus(str(row["status"]))
            successor = RunStatus(status)
            validate_run_transition(current, successor)
            updated = database.execute(
                """UPDATE runs SET status = ?, updated_at = ?, error_code = ?, error_summary = ?
                   WHERE run_id = ? AND status = ?""",
                (
                    successor.value,
                    updated_at,
                    failure.code.value if failure else None,
                    failure.as_dict()["summary"] if failure else None,
                    run_id,
                    current.value,
                ),
            )
            if updated.rowcount != 1:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)

        try:
            self._snapshot_transaction(mutate)
        except (ValueError, TypeError):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None

    def read_run(self, run_id: str) -> RunRecord:
        try:
            run = self._db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            record = self._run_record(run)
            if record.identity_state != "bound":
                raise SafeFailure(ErrorCode.STATE_IDENTITY_UNBOUND)
            return record
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        """Project one run exclusively from verified persisted state."""

        try:
            run = self._db.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            run_record = self._run_record(run)
            if run_record.identity_state != "bound":
                raise SafeFailure(ErrorCode.STATE_IDENTITY_UNBOUND)
            self._identity_chain_matches(
                self._db,
                run_id,
                run_record.identity,
                allow_first_input_mismatch=False,
                require_evidence=False,
            )
            attempts = [
                self._persisted_attempt_record(row).model_dump(mode="json", exclude_none=False)
                for row in self._db.execute(
                    """SELECT attempt_id, run_id, subject_id, stage, stage_index,
                              attempt_no, status, input_hash, producer_version,
                              retry_policy_version, reusable_key_digest, started_at,
                              finished_at, prompt_version, policy_version, model_id,
                              request_id, latency_ms, prompt_tokens, completion_tokens,
                              total_tokens, error_code, error_summary, retryable
                       FROM stage_attempts WHERE run_id = ?
                       ORDER BY stage_index, attempt_no""",
                    (run_id,),
                )
            ]
            result_rows = self._db.execute(
                """SELECT * FROM stage_results WHERE run_id = ? ORDER BY stage_index""",
                (run_id,),
            ).fetchall()
            results: list[dict[str, Any]] = []
            for row in result_rows:
                envelope = self._verify_manifest_row(row)
                results.append(envelope.model_dump(mode="json", exclude_none=False))
            checkpoint = self.latest_checkpoint(run_id)
            reused = run_record.reused_stage_count
            return {
                "run": run_record.model_dump(mode="json", exclude_none=False),
                "attempts": attempts,
                "results": results,
                "checkpoint": (
                    checkpoint.model_dump(mode="json", exclude_none=False)
                    if checkpoint is not None
                    else None
                ),
                "reused_stage_count": reused,
                "remote_writes_attempted": 0,
            }
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _write_transaction(self, statement: str, parameters: tuple[object, ...]) -> None:
        def mutate(database: sqlite3.Connection) -> None:
            database.execute(statement, parameters)

        self._snapshot_transaction(mutate)

    def _snapshot_transaction(self, mutation: Callable[[sqlite3.Connection], _T]) -> _T:
        if self._durable_bytes is None or self._poisoned:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        candidate = self._new_memory_connection()
        try:
            candidate.deserialize(self._durable_bytes)
            candidate.execute("PRAGMA foreign_keys = ON")
            candidate.execute("BEGIN IMMEDIATE")
            result = mutation(candidate)
            candidate.commit()
            payload = self._serialize(candidate)
        except SafeFailure:
            try:
                candidate.rollback()
            except sqlite3.Error:
                pass
            candidate.close()
            raise
        except (IndexError, OverflowError, sqlite3.Error):
            try:
                candidate.rollback()
            except sqlite3.Error:
                pass
            candidate.close()
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

        assert self._state_parent is not None
        previous = self._durable_bytes
        try:
            self._trip_filesystem_seam("before_state_persist")
            self._state_parent.atomic_write(
                self._state_name,
                payload,
                max_bytes=MAX_STATE_DB_BYTES,
                restore_bytes=previous,
                seam_prefix="state_",
            )
        except (DurableWriteError, OSError):
            candidate.close()
            self._poison()
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

        current = self.connection
        self.connection = candidate
        self._durable_bytes = payload
        if current is not None:
            current.close()
        return result

    def _poison(self) -> None:
        self._poisoned = True
        if self.connection is not None:
            try:
                self.connection.close()
            except sqlite3.Error:
                pass
            self.connection = None

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            except sqlite3.Error:
                pass
            self.connection = None
        for anchor in self._manifest_stage_anchors.values():
            anchor.close()
        self._manifest_stage_anchors.clear()
        if self._manifest_anchor is not None:
            self._manifest_anchor.close()
            self._manifest_anchor = None
        if self._lock_descriptor >= 0:
            try:
                os.close(self._lock_descriptor)
            except OSError:
                pass
            self._lock_descriptor = -1
        if self._state_parent is not None:
            self._state_parent.close()
            self._state_parent = None

    def _manifest_stage_anchor(self, stage: PipelineStage, *, create: bool) -> AnchoredDirectory:
        if not isinstance(stage, PipelineStage):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        cached = self._manifest_stage_anchors.get(stage)
        if cached is not None:
            return cached
        try:
            if self._manifest_anchor is None:
                assert self._state_parent is not None
                self._manifest_anchor = self._state_parent.open_child_directory(
                    self._manifest_name,
                    create=create,
                )
            anchor = self._manifest_anchor.open_child_directory(
                stage.value,
                create=create,
            )
        except DurableWriteError:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None
        self._manifest_stage_anchors[stage] = anchor
        return anchor

    def _manifest_path(self, stage: PipelineStage, manifest_hash: str) -> Path:
        return self.manifest_root / self._manifest_locator(stage, manifest_hash)

    @staticmethod
    def _manifest_locator(stage: PipelineStage, manifest_hash: str) -> str:
        if not isinstance(stage, PipelineStage):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        matched = _DIGEST_PATTERN.fullmatch(manifest_hash)
        if matched is None:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        return f"{stage.value}/{matched.group(1)}.json"

    def _read_manifest_bytes(self, path: Path) -> bytes:
        try:
            relative = path.relative_to(self.manifest_root)
            if len(relative.parts) != 2:
                raise ValueError("manifest locator depth")
            stage = PipelineStage(relative.parts[0])
            anchor = self._manifest_stage_anchor(stage, create=False)
            payload = anchor.read_bytes(
                relative.parts[1],
                max_bytes=MAX_MANIFEST_BYTES,
            )
            assert payload is not None
            return payload
        except SafeFailure:
            raise
        except (AssertionError, DurableWriteError, OSError, ValueError):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None
