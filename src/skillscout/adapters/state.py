"""Transactional schema-v2 SQLite ledger and content-addressed manifests."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.canonical import (
    canonical_json_bytes,
    make_result_id,
    reusable_key_digest,
    stage_input_hash,
    stage_manifest_hash,
    stage_output_hash,
)
from skillscout.domain.enums import ExecutionMode, PipelineStage
from skillscout.domain.models import StageAttempt, StageEnvelope, StageInput

SCHEMA_VERSION = 2
_MIGRATION_SEAMS = frozenset({"after_schema", "after_copy", "after_validation"})


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
            execution_mode TEXT NOT NULL CHECK (execution_mode = 'dry_run'),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            error_code TEXT,
            error_summary TEXT,
            reused_stage_count INTEGER NOT NULL DEFAULT 0
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
            result_id TEXT PRIMARY KEY,
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
            UNIQUE (run_id, stage)
        )""",
        f"""CREATE TABLE {checkpoints} (
            run_id TEXT NOT NULL REFERENCES {runs}(run_id),
            subject_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_index INTEGER NOT NULL,
            result_id TEXT NOT NULL REFERENCES {results}(result_id),
            output_hash TEXT NOT NULL,
            manifest_hash TEXT NOT NULL,
            manifest_path TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_id, stage)
        )""",
    )


class SQLiteStateStore:
    """Fail-closed state adapter with explicit v1-to-v2 migration."""

    def __init__(self, path: Path, *, migration_fail_at: str | None = None) -> None:
        if migration_fail_at is not None and migration_fail_at not in _MIGRATION_SEAMS:
            raise ValueError("unknown migration failure seam")
        self.path = path
        self.manifest_root = path.with_suffix(".manifests")
        existed = path.exists()
        self.connection: sqlite3.Connection | None = None
        try:
            if not existed:
                path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(path, isolation_level=None)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            if not existed:
                self._create_current_schema()
                return
            try:
                version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
            except sqlite3.Error:
                raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE) from None
            if version == SCHEMA_VERSION:
                self._validate_current_schema()
            elif version == 1:
                self._migrate_v1(migration_fail_at)
            else:
                raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)
        except SafeFailure:
            if self.connection is not None:
                self.connection.close()
            raise
        except (OSError, sqlite3.Error):
            if self.connection is not None:
                self.connection.close()
            code = ErrorCode.STATE_SCHEMA_INCOMPATIBLE if existed else ErrorCode.STATE_OPERATION_FAILED
            raise SafeFailure(code) from None

    @classmethod
    def open(
        cls, path: Path, *, migration_fail_at: str | None = None
    ) -> SQLiteStateStore:
        return cls(path, migration_fail_at=migration_fail_at)

    @property
    def _db(self) -> sqlite3.Connection:
        if self.connection is None:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        return self.connection

    def _create_current_schema(self) -> None:
        try:
            self._db.execute("BEGIN IMMEDIATE")
            for statement in _schema_statements():
                self._db.execute(statement)
            self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._db.commit()
        except sqlite3.Error:
            self._db.rollback()
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _validate_current_schema(self) -> None:
        required = {
            "runs": {
                "run_id",
                "schema_version",
                "subject_id",
                "status",
                "reused_stage_count",
            },
            "stage_attempts": {
                "attempt_id",
                "input_hash",
                "producer_version",
                "retry_policy_version",
                "reusable_key_digest",
            },
            "stage_results": {"result_id", "manifest_hash", "manifest_path", "output_hash"},
            "checkpoints": {"result_id", "manifest_hash", "manifest_path", "output_hash"},
        }
        try:
            for table, columns in required.items():
                actual = {
                    str(row["name"])
                    for row in self._db.execute(f"PRAGMA table_info({table})").fetchall()
                }
                if not columns <= actual:
                    raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)
            if self._db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE)
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_SCHEMA_INCOMPATIBLE) from None

    def _migrate_v1(self, fail_at: str | None) -> None:
        created_manifests: list[Path] = []
        try:
            self._db.execute("BEGIN IMMEDIATE")
            for statement in _schema_statements("_v2"):
                self._db.execute(statement)
            self._trip_migration_seam(fail_at, "after_schema")

            self._db.execute(
                """INSERT INTO runs_v2
                   SELECT run_id, '1', subject_id, execution_mode, status, created_at,
                          updated_at, error_code, error_summary, 0
                   FROM runs"""
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
                provisional = StageEnvelope(
                    schema_version="1",
                    result_id=str(row["result_id"]),
                    run_id=str(row["run_id"]),
                    attempt_id=str(row["attempt_id"]),
                    attempt_no=int(row["attempt_no"]),
                    subject_id=str(row["subject_id"]),
                    stage=stage,
                    stage_index=int(row["stage_index"]),
                    input_hash=str(row["input_hash"]),
                    output_hash=str(row["output_hash"]),
                    producer_version=str(row["producer_version"]),
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
                self._db.execute(
                    """INSERT INTO stage_results_v2
                       (result_id, attempt_id, run_id, schema_version, subject_id, stage,
                        stage_index, output_json, output_hash, producer_version,
                        manifest_hash, manifest_path, created_at)
                       VALUES (?, ?, ?, '1', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
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
                        str(manifest_path),
                        envelope.created_at,
                    ),
                )

            self._db.execute(
                """INSERT INTO checkpoints_v2
                   SELECT c.run_id, c.subject_id, c.stage, c.stage_index, c.result_id,
                          c.output_hash, r.manifest_hash, r.manifest_path, c.updated_at
                   FROM checkpoints c JOIN stage_results_v2 r USING (result_id)"""
            )
            self._trip_migration_seam(fail_at, "after_copy")
            self._validate_migration_copy()
            self._trip_migration_seam(fail_at, "after_validation")

            for table in ("checkpoints", "stage_results", "stage_attempts", "runs"):
                self._db.execute(f"DROP TABLE {table}")
            for old, new in (
                ("runs_v2", "runs"),
                ("stage_attempts_v2", "stage_attempts"),
                ("stage_results_v2", "stage_results"),
                ("checkpoints_v2", "checkpoints"),
            ):
                self._db.execute(f"ALTER TABLE {old} RENAME TO {new}")
            self._db.execute("DROP INDEX idx_attempts_reusable_v2")
            self._db.execute(
                "CREATE INDEX idx_attempts_reusable ON stage_attempts(reusable_key_digest)"
            )
            self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._db.commit()
        except Exception:
            self._db.rollback()
            self._remove_migration_manifests(created_manifests)
            raise SafeFailure(ErrorCode.STATE_SCHEMA_MIGRATION_ERROR) from None

    @staticmethod
    def _trip_migration_seam(configured: str | None, current: str) -> None:
        if configured == current:
            raise RuntimeError("forced migration seam")

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
            expected = reusable_key_digest(
                subject_id=str(row["subject_id"]),
                stage=PipelineStage(str(row["stage"])),
                input_hash=str(row["input_hash"]),
                producer_version=str(row["producer_version"]),
                retry_policy_version=str(row["retry_policy_version"]),
            )
            if expected != row["reusable_key_digest"]:
                raise ValueError("migration reusable digest mismatch")

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
            self._verify_manifest_row(row)
        if self._db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("migration foreign key failure")

    def _remove_migration_manifests(self, paths: Iterable[Path]) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        if self.manifest_root.exists():
            for directory in sorted(
                (path for path in self.manifest_root.rglob("*") if path.is_dir()), reverse=True
            ):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            try:
                self.manifest_root.rmdir()
            except OSError:
                pass

    def create_run(
        self, run_id: str, subject_id: str, created_at: str, schema_version: str = "2"
    ) -> None:
        self._write_transaction(
            """INSERT INTO runs
               (run_id, schema_version, subject_id, execution_mode, status, created_at,
                updated_at, error_code, error_summary, reused_stage_count)
               VALUES (?, ?, ?, 'dry_run', 'running', ?, ?, NULL, NULL, 0)""",
            (run_id, schema_version, subject_id, created_at, created_at),
        )

    def find_resumable_run(self, subject_id: str) -> sqlite3.Row | None:
        try:
            return self._db.execute(
                """SELECT run_id, schema_version, status FROM runs
                   WHERE subject_id = ? AND status IN ('running', 'interrupted')
                   ORDER BY updated_at DESC LIMIT 1""",
                (subject_id,),
            ).fetchone()
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def latest_checkpoint(self, run_id: str) -> sqlite3.Row | None:
        try:
            return self._db.execute(
                """SELECT stage, stage_index, result_id, output_hash, manifest_hash,
                          manifest_path, updated_at
                   FROM checkpoints WHERE run_id = ? ORDER BY stage_index DESC LIMIT 1""",
                (run_id,),
            ).fetchone()
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def resume_identity_matches(
        self,
        run_id: str,
        *,
        schema_version: str,
        subject_id: str,
        fixture_hash: str,
        producer_version: str,
        retry_policy_version: str,
    ) -> bool:
        """Verify both manifest bytes and current canonical identity before reuse."""

        try:
            rows = self._db.execute(
                """SELECT r.*, a.input_hash, a.producer_version AS attempt_producer,
                          a.retry_policy_version, a.reusable_key_digest
                   FROM stage_results r JOIN stage_attempts a USING (attempt_id)
                   WHERE r.run_id = ? ORDER BY r.stage_index""",
                (run_id,),
            ).fetchall()
            previous_output_hash: str | None = None
            for expected_index, row in enumerate(rows):
                if int(row["stage_index"]) != expected_index:
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                envelope = self._verify_manifest_row(row)
                stage_input = StageInput(
                    schema_version=schema_version,
                    execution_mode=ExecutionMode.DRY_RUN,
                    subject_id=subject_id,
                    stage=PipelineStage(str(row["stage"])),
                    previous_output_hash=previous_output_hash,
                    fixture_hash=fixture_hash if expected_index == 0 else None,
                )
                expected_input = stage_input_hash(stage_input)
                expected_digest = reusable_key_digest(
                    subject_id=subject_id,
                    stage=stage_input.stage,
                    input_hash=expected_input,
                    producer_version=producer_version,
                    retry_policy_version=retry_policy_version,
                )
                if (
                    row["input_hash"] != expected_input
                    or row["attempt_producer"] != producer_version
                    or row["retry_policy_version"] != retry_policy_version
                    or row["reusable_key_digest"] != expected_digest
                ):
                    return False
                previous_output_hash = envelope.output_hash
            return True
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def set_reused_stage_count(self, run_id: str, count: int) -> None:
        self._write_transaction(
            "UPDATE runs SET reused_stage_count = ? WHERE run_id = ?", (count, run_id)
        )

    def abandon_stale_running(
        self, run_id: str, stage: PipelineStage, finished_at: str
    ) -> None:
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

    def next_attempt_no(
        self, run_id: str, stage: PipelineStage, reusable_digest: str
    ) -> int:
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
        target = self.manifest_root / envelope.stage.value / f"{envelope.manifest_hash}.json"
        payload = canonical_json_bytes(envelope)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != payload:
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                return target
            temporary = target.with_name(f".{target.name}.tmp")
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
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
            try:
                directory = os.open(target.parent, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                pass
            return target
        except SafeFailure:
            raise
        except OSError:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _commit_success(self, envelope: StageEnvelope, manifest_path: Path) -> None:
        try:
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute(
                """INSERT INTO stage_results
                   (result_id, attempt_id, run_id, schema_version, subject_id, stage,
                    stage_index, output_json, output_hash, producer_version, manifest_hash,
                    manifest_path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
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
                    str(manifest_path),
                    envelope.created_at,
                ),
            )
            updated = self._db.execute(
                """UPDATE stage_attempts SET status = 'succeeded', finished_at = ?
                   WHERE attempt_id = ? AND status = 'running'""",
                (envelope.created_at, envelope.attempt_id),
            )
            if updated.rowcount != 1:
                raise sqlite3.IntegrityError("attempt was not running")
            self._db.execute(
                """INSERT INTO checkpoints
                   (run_id, subject_id, stage, stage_index, result_id, output_hash,
                    manifest_hash, manifest_path, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    envelope.run_id,
                    envelope.subject_id,
                    envelope.stage.value,
                    envelope.stage_index,
                    envelope.result_id,
                    envelope.output_hash,
                    envelope.manifest_hash,
                    str(manifest_path),
                    envelope.created_at,
                ),
            )
            self._db.execute(
                "UPDATE runs SET updated_at = ? WHERE run_id = ?",
                (envelope.created_at, envelope.run_id),
            )
            self._db.commit()
        except sqlite3.Error:
            self._db.rollback()
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

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
            raw = Path(str(row["manifest_path"])).read_bytes()
            envelope = StageEnvelope.model_validate_json(raw, strict=True)
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
            return envelope
        except SafeFailure:
            raise
        except (OSError, ValidationError, ValueError, TypeError):
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
        try:
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute(
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
            self._db.execute(
                """UPDATE runs SET status = 'interrupted', updated_at = ?, error_code = ?,
                          error_summary = ? WHERE run_id = ?""",
                (finished_at, failure.code.value, failure.as_dict()["summary"], run_id),
            )
            self._db.commit()
        except sqlite3.Error:
            self._db.rollback()
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def set_run_status(
        self,
        run_id: str,
        status: str,
        updated_at: str,
        failure: SafeFailure | None = None,
    ) -> None:
        self._write_transaction(
            """UPDATE runs SET status = ?, updated_at = ?, error_code = ?, error_summary = ?
               WHERE run_id = ?""",
            (
                status,
                updated_at,
                failure.code.value if failure else None,
                failure.as_dict()["summary"] if failure else None,
                run_id,
            ),
        )

    def read_run(self, run_id: str) -> dict[str, Any]:
        try:
            run = self._db.execute(
                "SELECT run_id, status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            checkpoint = self.latest_checkpoint(run_id)
            if run is None or checkpoint is None:
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            return {
                "run_id": run["run_id"],
                "status": run["status"],
                "last_stage": checkpoint["stage"],
            }
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        """Project one run exclusively from verified persisted state."""

        try:
            run = self._db.execute(
                """SELECT run_id, schema_version, subject_id, execution_mode, status,
                          created_at, updated_at, error_code, error_summary,
                          reused_stage_count
                   FROM runs WHERE run_id = ?""",
                (run_id,),
            ).fetchone()
            if run is None:
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            attempts = [
                dict(row)
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
            for attempt in attempts:
                attempt["retryable"] = bool(attempt["retryable"])
            result_rows = self._db.execute(
                """SELECT * FROM stage_results WHERE run_id = ? ORDER BY stage_index""",
                (run_id,),
            ).fetchall()
            results: list[dict[str, Any]] = []
            for row in result_rows:
                envelope = self._verify_manifest_row(row)
                results.append(envelope.model_dump(mode="json", exclude_none=False))
            checkpoint = self.latest_checkpoint(run_id)
            reused = int(run["reused_stage_count"])
            return {
                "run": dict(run),
                "attempts": attempts,
                "results": results,
                "checkpoint": dict(checkpoint) if checkpoint is not None else None,
                "reused_stage_count": reused,
                "remote_writes_attempted": 0,
            }
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _write_transaction(self, statement: str, parameters: tuple[object, ...]) -> None:
        try:
            self._db.execute("BEGIN IMMEDIATE")
            self._db.execute(statement, parameters)
            self._db.commit()
        except sqlite3.Error:
            self._db.rollback()
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            except sqlite3.Error:
                pass
            self.connection = None
