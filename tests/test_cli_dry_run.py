"""Executable and adversarial contract for the Phase 1 Walking Skeleton."""

from __future__ import annotations

import json
import hashlib
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import parse_cli_error, parse_cli_json
from skillscout import cli
from skillscout.adapters import fixtures
from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import (
    RETRY_POLICY_VERSION,
    STAGE_SEQUENCE,
    PipelineRunner,
    canonical_v1_digest,
)
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode, SafeFailure


def _all_file_bytes(root: Path, *, exclude: set[Path] | None = None) -> bytes:
    excluded = exclude or set()
    return b"".join(
        path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path not in excluded
    )


def _assert_sanitized_error(result, expected: ErrorCode) -> None:
    assert parse_cli_error(result) == {
        "error": {"code": expected.value, "summary": ERROR_SUMMARIES[expected]}
    }


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def test_approved_fixture_reaches_planned_not_published(
    approved_fixture: Path, run_cli, tmp_path: Path
) -> None:
    result = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(tmp_path / "state.db"),
        "--output",
        str(tmp_path / "output"),
    )
    assert result.returncode == 0, "dry-run CLI behavior is not implemented"
    payload = parse_cli_json(result)
    assert payload == {
        "run_id": payload["run_id"],
        "status": "planned_not_published",
        "last_stage": "publication_planner",
        "reused_stage_count": 0,
        "publication_plan_path": str(tmp_path / "output" / "publication-plan.json"),
        "remote_writes_attempted": 0,
    }

    state_path = tmp_path / "state.db"
    with _connect(state_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        attempts = connection.execute(
            """SELECT stage, status, input_hash, producer_version, retry_policy_version,
                      reusable_key_digest, prompt_version, policy_version, model_id,
                      request_id, latency_ms, prompt_tokens, completion_tokens, total_tokens
               FROM stage_attempts ORDER BY stage_index"""
        ).fetchall()
        assert [row["stage"] for row in attempts] == list(STAGE_SEQUENCE)
        assert all(row["status"] == "succeeded" for row in attempts)
        assert all(
            row["reusable_key_digest"]
            == canonical_v1_digest(
                subject_id="fixture:approved-workflow",
                stage=row["stage"],
                input_hash=row["input_hash"],
                producer_version=row["producer_version"],
                retry_policy_version=row["retry_policy_version"],
            )
            for row in attempts
        )
        assert all(row["retry_policy_version"] == RETRY_POLICY_VERSION for row in attempts)
        assert all(
            row[field] is None
            for row in attempts
            for field in (
                "prompt_version",
                "policy_version",
                "model_id",
                "request_id",
                "latency_ms",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            )
        )
        assert connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 9
        checkpoints = connection.execute(
            "SELECT stage FROM checkpoints ORDER BY stage_index"
        ).fetchall()
        assert [row["stage"] for row in checkpoints] == list(STAGE_SEQUENCE)

    publication_files = [path.name for path in (tmp_path / "output").iterdir()]
    assert publication_files == ["publication-plan.json"]
    publication_plan = json.loads((tmp_path / "output" / publication_files[0]).read_text())
    assert publication_plan == {
        "last_stage": "publication_planner",
        "remote_writes_attempted": 0,
        "run_id": payload["run_id"],
        "status": "planned_not_published",
    }

    # A processor probe proves the durable running identity exists before invocation.
    probe_state_path = tmp_path / "probe.db"
    probe_store = SQLiteStateStore(probe_state_path)
    observations: list[tuple[str, str]] = []

    class ProbeProcessor(FixtureProcessor):
        def process(self, stage: str, subject_id: str, previous_output_hash: str | None):
            with _connect(probe_state_path) as probe:
                row = probe.execute(
                    """SELECT status, input_hash, producer_version, retry_policy_version,
                              reusable_key_digest
                       FROM stage_attempts WHERE stage = ?""",
                    (stage,),
                ).fetchone()
                assert row is not None
                assert row["status"] == "running"
                assert all(row[field] for field in row.keys() if field != "status")
                observations.append((stage, row["reusable_key_digest"]))
            return super().process(stage, subject_id, previous_output_hash)

    try:
        PipelineRunner(probe_store, ProbeProcessor()).run(
            load_fixture(approved_fixture), tmp_path / "probe-output"
        )
    finally:
        probe_store.close()
    assert [stage for stage, _digest in observations] == list(STAGE_SEQUENCE)


def test_fixture_symlink_is_rejected_before_run_creation(
    approved_fixture: Path, run_cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(approved_fixture.read_bytes())
    link = tmp_path / "link.json"
    link.symlink_to(target)
    state = tmp_path / "state.db"
    result = run_cli(
        "dry-run", "--fixture", str(link), "--state", str(state), "--output", str(tmp_path / "out")
    )
    _assert_sanitized_error(result, ErrorCode.INVALID_FIXTURE)
    assert not state.exists()

    # The accepted path is opened exactly once and its bytes come from that descriptor.
    opened: list[int] = []
    original_open = fixtures.os.open

    def counting_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(fixtures.os, "open", counting_open)
    assert load_fixture(target).subject_id == "fixture:approved-workflow"
    assert len(opened) == 1


def test_non_regular_fixture_is_rejected_before_run_creation(run_cli, tmp_path: Path) -> None:
    state = tmp_path / "state.db"
    result = run_cli(
        "dry-run",
        "--fixture",
        str(tmp_path),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "out"),
    )
    _assert_sanitized_error(result, ErrorCode.INVALID_FIXTURE)
    assert not state.exists()


def test_declared_oversize_fixture_is_rejected_before_read(run_cli, tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (fixtures.MAX_FIXTURE_BYTES + 1))
    state = tmp_path / "state.db"
    result = run_cli(
        "dry-run",
        "--fixture",
        str(oversized),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "out"),
    )
    _assert_sanitized_error(result, ErrorCode.INVALID_FIXTURE)
    assert not state.exists()


def test_stream_overflow_is_rejected_at_cap_plus_one(
    approved_fixture: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_read = fixtures.os.read
    first = True

    def overflowing_read(descriptor: int, count: int) -> bytes:
        nonlocal first
        if first:
            first = False
            return b"x" * (fixtures.MAX_FIXTURE_BYTES + 1)
        return original_read(descriptor, count)

    monkeypatch.setattr(fixtures.os, "read", overflowing_read)
    with pytest.raises(SafeFailure) as failure:
        load_fixture(approved_fixture)
    assert failure.value.code is ErrorCode.INVALID_FIXTURE


def test_same_descriptor_change_is_rejected_before_parse(
    approved_fixture: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    actual = os.stat(approved_fixture)
    calls = 0

    def changing_fstat(_descriptor: int):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            st_mode=actual.st_mode,
            st_dev=actual.st_dev,
            st_ino=actual.st_ino,
            st_size=actual.st_size,
            st_mtime_ns=actual.st_mtime_ns + (1 if calls > 1 else 0),
            st_ctime_ns=actual.st_ctime_ns,
        )

    monkeypatch.setattr(fixtures.os, "fstat", changing_fstat)
    with pytest.raises(SafeFailure) as failure:
        load_fixture(approved_fixture)
    assert failure.value.code is ErrorCode.FIXTURE_CHANGED
    assert calls == 2


@pytest.mark.parametrize("pydantic_invalid", [False, True])
def test_invalid_fixture_diagnostics_do_not_disclose_hostile_canaries(
    run_cli, tmp_path: Path, pydantic_invalid: bool
) -> None:
    credential = "github_pat_DO_NOT_DISCLOSE_123456789"
    attacker_path = "/attacker/selected/private/path"
    raw = (
        json.dumps(
            {
                "schema_version": "1",
                "subject_id": credential,
                "source": {
                    "repository": attacker_path,
                    "commit_sha": "0" * 40,
                    "license": "MIT",
                },
                "workflow": {"goal": "x", "inputs": [], "steps": [], "outputs": []},
                "unexpected": credential,
            }
        ).encode()
        if pydantic_invalid
        else (b'{"hostile":"' + credential.encode() + b'","path":"' + attacker_path.encode())
    )
    fixture = tmp_path / "hostile.json"
    fixture.write_bytes(raw)
    result = run_cli(
        "dry-run",
        "--fixture",
        str(fixture),
        "--state",
        str(tmp_path / "state.db"),
        "--output",
        str(tmp_path / "out"),
    )
    _assert_sanitized_error(result, ErrorCode.INVALID_FIXTURE)
    surfaces = (
        result.stdout.encode()
        + result.stderr.encode()
        + _all_file_bytes(tmp_path, exclude={fixture})
    )
    assert credential.encode() not in surfaces
    assert attacker_path.encode() not in surfaces
    assert not (tmp_path / "state.db").exists()


def test_exception_arguments_do_not_reach_any_durable_surface(
    approved_fixture: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    credential = "OPENAI_API_KEY_DO_NOT_DISCLOSE_123456"
    attacker_path = "/attacker/exception/private/path"

    def hostile_exception(*_args, **_kwargs):
        raise RuntimeError(credential, attacker_path)

    monkeypatch.setattr(FixtureProcessor, "process", hostile_exception)
    status = cli.main(
        [
            "dry-run",
            "--fixture",
            str(approved_fixture),
            "--state",
            str(tmp_path / "state.db"),
            "--output",
            str(tmp_path / "out"),
        ]
    )
    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": ErrorCode.PIPELINE_INTERRUPTED.value,
            "summary": ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
        }
    }
    surfaces = captured.err.encode() + _all_file_bytes(tmp_path)
    assert credential.encode() not in surfaces
    assert attacker_path.encode() not in surfaces
    with _connect(tmp_path / "state.db") as connection:
        run = connection.execute(
            "SELECT status, error_code, error_summary FROM runs"
        ).fetchone()
        attempt = connection.execute(
            "SELECT status, error_code, error_summary FROM stage_attempts"
        ).fetchone()
        assert tuple(run) == (
            "interrupted",
            ErrorCode.PIPELINE_INTERRUPTED.value,
            ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
        )
        assert tuple(attempt) == (
            "failed",
            ErrorCode.PIPELINE_INTERRUPTED.value,
            ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
        )


def test_fail_after_generator_is_durable_and_stops_before_validators(
    approved_fixture: Path, run_cli, tmp_path: Path
) -> None:
    state = tmp_path / "state.db"
    result = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "out"),
        "--fail-after",
        "generator",
    )
    _assert_sanitized_error(result, ErrorCode.PIPELINE_INTERRUPTED)
    with _connect(state) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        run = connection.execute("SELECT status FROM runs").fetchone()
        assert run["status"] == "interrupted"
        checkpoints = connection.execute(
            "SELECT stage FROM checkpoints ORDER BY stage_index"
        ).fetchall()
        assert [row["stage"] for row in checkpoints] == list(STAGE_SEQUENCE[:6])
        assert connection.execute(
            "SELECT COUNT(*) FROM stage_attempts WHERE stage = 'validators'"
        ).fetchone()[0] == 0
        generator = connection.execute(
            """SELECT a.status AS attempt_status, r.output_hash
               FROM stage_attempts a JOIN stage_results r USING (attempt_id)
               WHERE a.stage = 'generator'"""
        ).fetchone()
        assert generator["attempt_status"] == "succeeded"
        assert generator["output_hash"].startswith("sha256:")
    assert not (tmp_path / "out").exists()


def test_frozen_v1_cli_fixture_matches_provenance() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "state"
    database = fixture_root / "v1-cli.db"
    provenance = json.loads((fixture_root / "v1-cli-provenance.json").read_text())
    assert hashlib.sha256(database.read_bytes()).hexdigest() == provenance["database_sha256"]
    assert provenance["raw_exit_code"] == 1
    with _connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        run = connection.execute("SELECT run_id, status FROM runs").fetchone()
        checkpoint = connection.execute(
            "SELECT stage, stage_index, output_hash FROM checkpoints ORDER BY stage_index DESC LIMIT 1"
        ).fetchone()
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("runs", "stage_attempts", "stage_results", "checkpoints")
        }
        assert dict(run) == {
            "run_id": provenance["run_id"],
            "status": provenance["run_status"],
        }
        assert dict(checkpoint) == provenance["last_checkpoint"]
        assert counts == provenance["row_counts"]
        assert connection.execute(
            "SELECT COUNT(*) FROM stage_attempts WHERE stage = 'validators'"
        ).fetchone()[0] == provenance["validators_attempt_count"] == 0
