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
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import StageInput


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
        "publication_plan_path": "publication-plan.json",
        "remote_writes_attempted": 0,
    }

    state_path = tmp_path / "state.db"
    with _connect(state_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
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
        def process(self, stage_input: StageInput):
            with _connect(probe_state_path) as probe:
                row = probe.execute(
                    """SELECT status, input_hash, producer_version, retry_policy_version,
                              reusable_key_digest
                       FROM stage_attempts WHERE stage = ?""",
                    (stage_input.stage.value,),
                ).fetchone()
                assert row is not None
                assert row["status"] == "running"
                assert all(row[field] for field in row.keys() if field != "status")
                observations.append((stage_input.stage.value, row["reusable_key_digest"]))
            return super().process(stage_input)

    try:
        PipelineRunner(probe_store, ProbeProcessor()).run(
            load_fixture(approved_fixture), tmp_path / "probe-output"
        )
    finally:
        probe_store.close()
    assert [stage for stage, _digest in observations] == list(STAGE_SEQUENCE)


def test_installed_main_completes_all_stages_with_socket_connects_disabled(
    approved_fixture: Path,
    outbound_socket_sentinel: list[object],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = tmp_path / "state.db"
    output = tmp_path / "output"
    status = cli.main(
        [
            "dry-run",
            "--fixture",
            str(approved_fixture),
            "--state",
            str(state),
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert status == 0, captured.err
    payload = json.loads(captured.out)
    assert payload["status"] == "planned_not_published"
    assert payload["last_stage"] == "publication_planner"
    assert payload["remote_writes_attempted"] == 0
    assert payload["publication_plan_path"] == "publication-plan.json"
    assert outbound_socket_sentinel == []

    with _connect(state) as connection:
        assert connection.execute("SELECT COUNT(*) FROM stage_results").fetchone()[0] == 9
        assert connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 9
        assert connection.execute("SELECT status FROM runs").fetchone()[0] == (
            "planned_not_published"
        )
    publication = json.loads((output / "publication-plan.json").read_text())
    assert publication["remote_writes_attempted"] == 0
    assert publication["status"] == "planned_not_published"


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
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
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


def test_fresh_interruption_rerun_and_inspect_are_persisted(
    approved_fixture: Path, run_cli, tmp_path: Path
) -> None:
    state = tmp_path / "state.db"
    first = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "first-output"),
        "--fail-after",
        "generator",
    )
    _assert_sanitized_error(first, ErrorCode.PIPELINE_INTERRUPTED)
    with _connect(state) as connection:
        run_id = connection.execute("SELECT run_id FROM runs").fetchone()[0]
        original = [
            tuple(row)
            for row in connection.execute(
                """SELECT result_id, output_hash, manifest_hash
                   FROM stage_results ORDER BY stage_index"""
            )
        ]

    second = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "second-output"),
    )
    summary = parse_cli_json(second)
    assert summary["run_id"] == run_id
    assert summary["reused_stage_count"] == 6
    with _connect(state) as connection:
        assert [
            tuple(row)
            for row in connection.execute(
                """SELECT result_id, output_hash, manifest_hash
                   FROM stage_results ORDER BY stage_index LIMIT 6"""
            )
        ] == original

    inspected = run_cli(
        "inspect-run", run_id, "--state", str(state), "--format", "json"
    )
    payload = parse_cli_json(inspected)
    assert payload["run"] == {
        "run_id": run_id,
        "schema_version": "2",
        "subject_id": "fixture:approved-workflow",
        "fixture_hash": sha256_digest(
            load_fixture(approved_fixture).model_dump(mode="json", exclude_none=False)
        ),
        "producer_version": "fixture-v1",
        "retry_policy_version": "retry-v1",
        "identity_state": "bound",
        "execution_mode": "dry_run",
        "status": "planned_not_published",
        "created_at": payload["run"]["created_at"],
        "updated_at": payload["run"]["updated_at"],
        "error_code": None,
        "error_summary": None,
        "reused_stage_count": 6,
    }
    assert len(payload["attempts"]) == 9
    assert len(payload["results"]) == 9
    assert payload["checkpoint"]["stage"] == "publication_planner"
    assert payload["reused_stage_count"] == 6
    required_attempt_fields = {
        "attempt_id",
        "run_id",
        "subject_id",
        "stage",
        "stage_index",
        "attempt_no",
        "status",
        "input_hash",
        "producer_version",
        "retry_policy_version",
        "reusable_key_digest",
        "started_at",
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
        "retryable",
    }
    assert required_attempt_fields == set(payload["attempts"][0])
    assert all(field in payload["attempts"][0] for field in ("request_id", "latency_ms"))
    assert payload["attempts"][0]["request_id"] is None
    assert payload["attempts"][0]["latency_ms"] is None


def test_corrupt_chain_blocks_inspect_and_resume_without_output_or_mutation(
    approved_fixture: Path, run_cli, tmp_path: Path
) -> None:
    state = tmp_path / "corrupt-shared-verifier.db"
    first_output = tmp_path / "corrupt-first"
    interrupted = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(first_output),
        "--fail-after",
        "generator",
    )
    _assert_sanitized_error(interrupted, ErrorCode.PIPELINE_INTERRUPTED)
    with _connect(state) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs").fetchone()[0])
        connection.execute(
            """UPDATE stage_attempts SET input_hash = ?
               WHERE run_id = ? AND stage = 'filter'""",
            ("sha256:" + "f" * 64, run_id),
        )
        connection.commit()
    before = state.read_bytes()

    inspected = run_cli(
        "inspect-run", run_id, "--state", str(state), "--format", "json"
    )
    _assert_sanitized_error(inspected, ErrorCode.STATE_INTEGRITY_ERROR)
    assert inspected.stdout == ""
    assert state.read_bytes() == before

    resumed_output = tmp_path / "corrupt-resume"
    resumed = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(resumed_output),
    )
    _assert_sanitized_error(resumed, ErrorCode.STATE_INTEGRITY_ERROR)
    assert resumed.stdout == ""
    assert not resumed_output.exists()
    assert state.read_bytes() == before


def test_inspect_run_exit_codes_preserve_not_found_and_usage(
    run_cli, tmp_path: Path
) -> None:
    state = tmp_path / "state.db"
    SQLiteStateStore(state).close()
    missing = run_cli("inspect-run", "missing", "--state", str(state), "--format", "json")
    _assert_sanitized_error(missing, ErrorCode.STATE_OPERATION_FAILED)
    usage = run_cli("inspect-run", "missing", "--state", str(state), "--format", "yaml")
    assert usage.returncode == 2
