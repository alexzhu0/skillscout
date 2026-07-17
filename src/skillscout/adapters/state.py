"""SQLite schema-v1 operational ledger for the local walking skeleton."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from skillscout.application.ports import ErrorCode, SafeFailure


class SQLiteStateStore:
    """A small explicit schema whose identity fields support the v2 migration."""

    def __init__(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.path = path
            self.connection = sqlite3.connect(path)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            self._create_schema()
        except (OSError, sqlite3.Error):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _create_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            execution_mode TEXT NOT NULL CHECK (execution_mode = 'dry_run'),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            error_code TEXT,
            error_summary TEXT
        );
        CREATE TABLE IF NOT EXISTS stage_attempts (
            attempt_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES runs(run_id),
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
        );
        CREATE INDEX IF NOT EXISTS idx_attempts_reusable
            ON stage_attempts(reusable_key_digest);
        CREATE TABLE IF NOT EXISTS stage_results (
            result_id TEXT PRIMARY KEY,
            attempt_id TEXT NOT NULL UNIQUE REFERENCES stage_attempts(attempt_id),
            run_id TEXT NOT NULL REFERENCES runs(run_id),
            subject_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_index INTEGER NOT NULL,
            output_json TEXT NOT NULL,
            output_hash TEXT NOT NULL,
            producer_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (run_id, stage)
        );
        CREATE TABLE IF NOT EXISTS checkpoints (
            run_id TEXT NOT NULL REFERENCES runs(run_id),
            subject_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_index INTEGER NOT NULL,
            result_id TEXT NOT NULL REFERENCES stage_results(result_id),
            output_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_id, stage)
        );
        PRAGMA user_version = 1;
        """
        with self.connection:
            self.connection.executescript(schema)

    def create_run(self, run_id: str, subject_id: str, created_at: str) -> None:
        self._execute(
            """INSERT INTO runs
               (run_id, subject_id, execution_mode, status, created_at, updated_at)
               VALUES (?, ?, 'dry_run', 'running', ?, ?)""",
            (run_id, subject_id, created_at, created_at),
        )

    def start_attempt(
        self,
        *,
        attempt_id: str,
        run_id: str,
        subject_id: str,
        stage: str,
        stage_index: int,
        input_hash: str,
        producer_version: str,
        retry_policy_version: str,
        reusable_key_digest: str,
        started_at: str,
    ) -> None:
        self._execute(
            """INSERT INTO stage_attempts (
                   attempt_id, run_id, subject_id, stage, stage_index, attempt_no, status,
                   input_hash, producer_version, retry_policy_version, reusable_key_digest,
                   started_at, prompt_version, policy_version, model_id, request_id, latency_ms,
                   prompt_tokens, completion_tokens, total_tokens, error_code, error_summary,
                   retryable
               ) VALUES (?, ?, ?, ?, ?, 1, 'running', ?, ?, ?, ?, ?,
                         NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0)""",
            (
                attempt_id,
                run_id,
                subject_id,
                stage,
                stage_index,
                input_hash,
                producer_version,
                retry_policy_version,
                reusable_key_digest,
                started_at,
            ),
        )

    def complete_stage(
        self,
        *,
        result_id: str,
        attempt_id: str,
        run_id: str,
        subject_id: str,
        stage: str,
        stage_index: int,
        output_json: str,
        output_hash: str,
        producer_version: str,
        finished_at: str,
    ) -> None:
        try:
            with self.connection:
                self.connection.execute(
                    """INSERT INTO stage_results
                       (result_id, attempt_id, run_id, subject_id, stage, stage_index,
                        output_json, output_hash, producer_version, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result_id,
                        attempt_id,
                        run_id,
                        subject_id,
                        stage,
                        stage_index,
                        output_json,
                        output_hash,
                        producer_version,
                        finished_at,
                    ),
                )
                self.connection.execute(
                    """UPDATE stage_attempts
                       SET status = 'succeeded', finished_at = ?
                       WHERE attempt_id = ? AND status = 'running'""",
                    (finished_at, attempt_id),
                )
                self.connection.execute(
                    """INSERT INTO checkpoints
                       (run_id, subject_id, stage, stage_index, result_id, output_hash, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        subject_id,
                        stage,
                        stage_index,
                        result_id,
                        output_hash,
                        finished_at,
                    ),
                )
                self.connection.execute(
                    "UPDATE runs SET updated_at = ? WHERE run_id = ?",
                    (finished_at, run_id),
                )
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def fail_attempt(
        self, attempt_id: str, run_id: str, failure: SafeFailure, finished_at: str
    ) -> None:
        try:
            with self.connection:
                self.connection.execute(
                    """UPDATE stage_attempts
                       SET status = 'failed', finished_at = ?, error_code = ?, error_summary = ?
                       WHERE attempt_id = ?""",
                    (
                        finished_at,
                        failure.code.value,
                        failure.as_dict()["summary"],
                        attempt_id,
                    ),
                )
                self.connection.execute(
                    """UPDATE runs
                       SET status = 'interrupted', updated_at = ?, error_code = ?, error_summary = ?
                       WHERE run_id = ?""",
                    (
                        finished_at,
                        failure.code.value,
                        failure.as_dict()["summary"],
                        run_id,
                    ),
                )
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def set_run_status(
        self,
        run_id: str,
        status: str,
        updated_at: str,
        failure: SafeFailure | None = None,
    ) -> None:
        code = failure.code.value if failure else None
        summary = failure.as_dict()["summary"] if failure else None
        self._execute(
            """UPDATE runs
               SET status = ?, updated_at = ?, error_code = ?, error_summary = ?
               WHERE run_id = ?""",
            (status, updated_at, code, summary, run_id),
        )

    def read_run(self, run_id: str) -> dict[str, Any]:
        try:
            run = self.connection.execute(
                "SELECT run_id, status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            checkpoint = self.connection.execute(
                """SELECT stage FROM checkpoints
                   WHERE run_id = ? ORDER BY stage_index DESC LIMIT 1""",
                (run_id,),
            ).fetchone()
            if run is None or checkpoint is None:
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            return {"run_id": run["run_id"], "status": run["status"], "last_stage": checkpoint["stage"]}
        except SafeFailure:
            raise
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _execute(self, statement: str, parameters: tuple[object, ...]) -> None:
        try:
            with self.connection:
                self.connection.execute(statement, parameters)
        except sqlite3.Error:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def close(self) -> None:
        try:
            self.connection.close()
        except sqlite3.Error:
            pass
