"""Expanded untrusted-input and disclosure matrix for the packaged CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillscout import cli
from skillscout.adapters import fixtures
from skillscout.adapters.fixtures import load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode, SafeFailure

FROZEN_DATABASE = Path(__file__).parent / "fixtures" / "state" / "v1-cli.db"
FROZEN_DATABASE_SHA256 = "49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251"
INVALID_ARGUMENTS_DIAGNOSTIC = (
    b'{"error":{"code":"invalid_cli_arguments",'
    b'"summary":"Command-line arguments were rejected."}}\n'
)

_CREDENTIAL_CANARY = "github_pat_ARGV_DO_NOT_DISCLOSE_123456789"
_PATH_CANARY = "/private/argv/path/DO_NOT_DISCLOSE"
_CONTROL_CANARY = "argv-line-one\nargv-line-two\tDO_NOT_DISCLOSE"
_UNICODE_CANARY = "ARGV_\u79d8\u5bc6_\U0001f512_DO_NOT_DISCLOSE"
_OVERSIZED_CANARY = "ARGV_OVERSIZED_DO_NOT_DISCLOSE_" + ("x" * 4096)


@pytest.mark.parametrize(
    ("argv", "canaries"),
    [
        pytest.param(
            (
                "dry-run",
                "--fixture",
                _PATH_CANARY,
                "--state",
                "state.db",
                "--output",
                "output",
                "--fail-after",
                _CREDENTIAL_CANARY,
            ),
            (_PATH_CANARY, _CREDENTIAL_CANARY),
            id="invalid_choice",
        ),
        pytest.param(
            (
                "dry-run",
                "--fixture",
                _PATH_CANARY,
                "--state",
                "state.db",
                "--output",
                "output",
                "--unknown-option",
                _OVERSIZED_CANARY + _CONTROL_CANARY + _UNICODE_CANARY,
            ),
            (
                _PATH_CANARY,
                _OVERSIZED_CANARY,
                _CONTROL_CANARY,
                _UNICODE_CANARY,
            ),
            id="unknown_option",
        ),
        pytest.param(
            (_UNICODE_CANARY,),
            (_UNICODE_CANARY,),
            id="unknown_subcommand",
        ),
        pytest.param(
            (
                "dry-run",
                "--fixture",
                _CREDENTIAL_CANARY,
                "--state",
                _PATH_CANARY,
                "--output",
            ),
            (_CREDENTIAL_CANARY, _PATH_CANARY),
            id="missing_value",
        ),
        pytest.param(
            ("dry-run", "--fixture", _CONTROL_CANARY),
            (_CONTROL_CANARY,),
            id="missing_required_arguments",
        ),
    ],
)
def test_argparse_failures_are_byte_exact_non_echoing_and_non_durable(
    tmp_path: Path,
    argv: tuple[str, ...],
    canaries: tuple[str, ...],
) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "skillscout.cli", *argv],
        cwd=tmp_path,
        check=False,
        capture_output=True,
    )

    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == INVALID_ARGUMENTS_DIAGNOSTIC
    for canary in canaries:
        encoded = canary.encode()
        assert encoded not in result.stdout
        assert encoded not in result.stderr
        assert encoded not in _all_bytes(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_safe_argument_parser_is_used_for_root_and_subparsers() -> None:
    parser = cli.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert isinstance(parser, cli.SafeArgumentParser)
    assert set(subparsers.choices) == {"dry-run", "extract-repo", "inspect-run"}
    assert all(isinstance(child, cli.SafeArgumentParser) for child in subparsers.choices.values())


def test_help_remains_a_successful_stdout_only_boundary(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "skillscout.cli", "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
    )

    assert result.returncode == 0
    assert result.stderr == b""
    assert result.stdout.startswith(b"usage: skillscout")
    assert list(tmp_path.iterdir()) == []


def _valid_fixture() -> dict[str, object]:
    return {
        "schema_version": "1",
        "subject_id": "fixture:approved-workflow",
        "source": {
            "repository": "https://github.com/example/approved-workflow",
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "license": "MIT",
        },
        "workflow": {
            "goal": "Generate a review-only plan.",
            "inputs": ["request"],
            "steps": ["review"],
            "outputs": ["plan"],
        },
    }


def _all_bytes(root: Path, excluded: set[Path] | None = None) -> bytes:
    ignored = excluded or set()
    return b"".join(
        path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path not in ignored
    )


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff\xfe\xfd",
        b'{"schema_version":"1"',
        json.dumps(_valid_fixture() | {"unexpected": "value"}).encode(),
        json.dumps(_valid_fixture() | {"schema_version": 1}).encode(),
        json.dumps(
            _valid_fixture() | {"subject_id": "fixture:../../GITHUB_TOKEN_DO_NOT_DISCLOSE"}
        ).encode(),
    ],
)
def test_invalid_encoding_json_schema_and_hostile_ids_leave_no_state(
    raw: bytes, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = tmp_path / "untrusted.json"
    fixture.write_bytes(raw)
    state = tmp_path / "state.db"
    status = cli.main(
        [
            "dry-run",
            "--fixture",
            str(fixture),
            "--state",
            str(state),
            "--output",
            str(tmp_path / "out"),
        ]
    )
    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": ErrorCode.INVALID_FIXTURE.value,
            "summary": ERROR_SUMMARIES[ErrorCode.INVALID_FIXTURE],
        }
    }
    assert not state.exists()


@pytest.mark.parametrize("changed", ["device", "inode", "size", "mtime", "ctime"])
def test_every_repeated_descriptor_metadata_change_is_rejected(
    approved_fixture: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: str,
) -> None:
    actual = os.stat(approved_fixture)
    calls = 0

    def changing_fstat(_descriptor: int):
        nonlocal calls
        calls += 1
        delta = int(calls > 1)
        return SimpleNamespace(
            st_mode=actual.st_mode,
            st_dev=actual.st_dev + (delta if changed == "device" else 0),
            st_ino=actual.st_ino + (delta if changed == "inode" else 0),
            st_size=actual.st_size + (delta if changed == "size" else 0),
            st_mtime_ns=actual.st_mtime_ns + (delta if changed == "mtime" else 0),
            st_ctime_ns=actual.st_ctime_ns + (delta if changed == "ctime" else 0),
        )

    monkeypatch.setattr(fixtures.os, "fstat", changing_fstat)
    with pytest.raises(SafeFailure) as failure:
        load_fixture(approved_fixture)
    assert failure.value.code is ErrorCode.FIXTURE_CHANGED
    assert calls == 2


def test_success_json_does_not_echo_operator_selected_absolute_output_path(
    approved_fixture: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canary = "ATTACKER_SELECTED_PRIVATE_PATH_DO_NOT_DISCLOSE"
    output = tmp_path / canary
    status = cli.main(
        [
            "dry-run",
            "--fixture",
            str(approved_fixture),
            "--state",
            str(tmp_path / "state.db"),
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert status == 0, captured.err
    payload = json.loads(captured.out)
    assert payload["publication_plan_path"] == "publication-plan.json"
    assert canary not in captured.out
    assert canary.encode() not in _all_bytes(tmp_path)


def test_state_path_canary_is_not_persisted_or_emitted(
    approved_fixture: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    canary = "STATE_PATH_SECRET_DO_NOT_DISCLOSE"
    state = tmp_path / canary / "state.db"
    status = cli.main(
        [
            "dry-run",
            "--fixture",
            str(approved_fixture),
            "--state",
            str(state),
            "--output",
            str(tmp_path / "out"),
        ]
    )
    first = capsys.readouterr()
    assert status == 0, first.err
    run_id = str(json.loads(first.out)["run_id"])
    inspected_status = cli.main(["inspect-run", run_id, "--state", str(state), "--format", "json"])
    second = capsys.readouterr()
    assert inspected_status == 0, second.err
    assert canary not in first.out
    assert canary not in second.out
    assert canary.encode() not in _all_bytes(tmp_path)


def test_unexpected_state_exception_is_mapped_without_repr_or_args(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "OPENAI_API_KEY_DO_NOT_DISCLOSE_987654"
    selected_path = "/attacker/selected/diagnostic/path"

    def hostile_inspect(*_args, **_kwargs):
        raise RuntimeError(secret, selected_path)

    monkeypatch.setattr("skillscout.adapters.state.SQLiteStateStore.inspect_run", hostile_inspect)
    state = tmp_path / "state.db"
    SQLiteStateStore(state).close()
    status = cli.main(["inspect-run", "missing", "--state", str(state), "--format", "json"])
    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": ErrorCode.STATE_OPERATION_FAILED.value,
            "summary": ERROR_SUMMARIES[ErrorCode.STATE_OPERATION_FAILED],
        }
    }
    surfaces = captured.err.encode() + _all_bytes(tmp_path)
    assert secret.encode() not in surfaces
    assert selected_path.encode() not in surfaces


@pytest.mark.parametrize(
    "tamper",
    [
        "run_error_code",
        "run_error_summary",
        "run_status_error_coherence",
        "run_timestamp",
        "attempt_error_code",
        "attempt_error_summary",
        "attempt_status_error_coherence",
        "attempt_retryable",
        "attempt_finished_at",
        "attempt_request_id",
        "attempt_latency",
        "attempt_partial_tokens",
        "attempt_total_tokens",
    ],
)
def test_persisted_diagnostic_and_telemetry_tampering_is_never_projected(
    approved_fixture: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    tamper: str,
) -> None:
    canary = "github_pat_PERSISTED_DIAGNOSTIC_DO_NOT_DISCLOSE"
    attacker_path = "/attacker/persisted/private/path"
    state = tmp_path / f"{tamper}.db"
    status = cli.main(
        [
            "dry-run",
            "--fixture",
            str(approved_fixture),
            "--state",
            str(state),
            "--output",
            str(tmp_path / "out"),
        ]
    )
    first = capsys.readouterr()
    assert status == 0, first.err
    run_id = str(json.loads(first.out)["run_id"])

    with _connect(state) as connection:
        if tamper == "run_error_code":
            connection.execute(
                "UPDATE runs SET error_code = ?, error_summary = ?",
                ("attacker_error", canary),
            )
        elif tamper == "run_error_summary":
            connection.execute(
                "UPDATE runs SET error_code = ?, error_summary = ?",
                (ErrorCode.PIPELINE_INTERRUPTED.value, canary),
            )
        elif tamper == "run_status_error_coherence":
            connection.execute("UPDATE runs SET status = 'interrupted'")
        elif tamper == "run_timestamp":
            connection.execute("UPDATE runs SET updated_at = ?", (attacker_path,))
        elif tamper == "attempt_error_code":
            connection.execute(
                """UPDATE stage_attempts SET error_code = ?, error_summary = ?
                   WHERE stage = 'scout'""",
                ("attacker_error", canary),
            )
        elif tamper == "attempt_error_summary":
            connection.execute(
                """UPDATE stage_attempts SET error_code = ?, error_summary = ?
                   WHERE stage = 'scout'""",
                (ErrorCode.PIPELINE_INTERRUPTED.value, canary),
            )
        elif tamper == "attempt_status_error_coherence":
            connection.execute(
                """UPDATE stage_attempts SET error_code = ?, error_summary = ?
                   WHERE stage = 'scout'""",
                (
                    ErrorCode.PIPELINE_INTERRUPTED.value,
                    ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
                ),
            )
        elif tamper == "attempt_retryable":
            connection.execute("UPDATE stage_attempts SET retryable = 1 WHERE stage = 'scout'")
        elif tamper == "attempt_finished_at":
            connection.execute("UPDATE stage_attempts SET finished_at = NULL WHERE stage = 'scout'")
        elif tamper == "attempt_request_id":
            connection.execute(
                "UPDATE stage_attempts SET request_id = ? WHERE stage = 'scout'",
                (canary,),
            )
        elif tamper == "attempt_latency":
            connection.execute("UPDATE stage_attempts SET latency_ms = -1 WHERE stage = 'scout'")
        elif tamper == "attempt_partial_tokens":
            connection.execute("UPDATE stage_attempts SET prompt_tokens = 1 WHERE stage = 'scout'")
        elif tamper == "attempt_total_tokens":
            connection.execute(
                """UPDATE stage_attempts
                   SET prompt_tokens = 1, completion_tokens = 2, total_tokens = 99
                   WHERE stage = 'scout'"""
            )
        else:
            raise AssertionError("unknown persisted tamper")
        connection.commit()

    inspected = cli.main(["inspect-run", run_id, "--state", str(state), "--format", "json"])
    captured = capsys.readouterr()
    assert inspected == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": ErrorCode.STATE_INTEGRITY_ERROR.value,
            "summary": ERROR_SUMMARIES[ErrorCode.STATE_INTEGRITY_ERROR],
        }
    }
    surfaces = captured.err.encode() + _all_bytes(tmp_path, excluded={state})
    assert canary.encode() not in surfaces
    assert attacker_path.encode() not in surfaces


def test_legacy_diagnostic_canary_rejects_migration_without_new_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    canary = "OPENAI_API_KEY_LEGACY_DIAGNOSTIC_DO_NOT_DISCLOSE"
    attacker_path = "/attacker/legacy/private/path"
    copied = tmp_path / "legacy-canary.db"
    shutil.copy2(FROZEN_DATABASE, copied)
    copied.chmod(0o600)
    with _connect(copied) as connection:
        connection.execute(
            """UPDATE stage_attempts SET error_code = ?, error_summary = ?, request_id = ?
               WHERE stage = 'scout'""",
            (ErrorCode.PIPELINE_INTERRUPTED.value, canary, attacker_path),
        )
        connection.commit()
    tampered_source = copied.read_bytes()

    status = cli.main(["inspect-run", "884039fcafca4757a194a9a69ca0e306", "--state", str(copied)])
    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": ErrorCode.STATE_SCHEMA_MIGRATION_ERROR.value,
            "summary": ERROR_SUMMARIES[ErrorCode.STATE_SCHEMA_MIGRATION_ERROR],
        }
    }
    assert copied.read_bytes() == tampered_source
    assert not copied.with_suffix(".manifests").exists()
    surfaces = captured.err.encode() + _all_bytes(tmp_path, excluded={copied})
    assert canary.encode() not in surfaces
    assert attacker_path.encode() not in surfaces
    assert hashlib.sha256(FROZEN_DATABASE.read_bytes()).hexdigest() == (FROZEN_DATABASE_SHA256)


def test_cli_rejects_colliding_state_namespace_without_disclosure(
    approved_fixture: Path,
    tmp_path: Path,
    run_cli,
) -> None:
    canary = "github_pat_COLLIDING_STATE_DO_NOT_DISCLOSE"
    state = tmp_path / f"{canary}.manifests"

    result = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "output"),
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert json.loads(result.stderr) == {
        "error": {
            "code": ErrorCode.STATE_INTEGRITY_ERROR.value,
            "summary": ERROR_SUMMARIES[ErrorCode.STATE_INTEGRITY_ERROR],
        }
    }
    assert canary not in result.stdout
    assert canary not in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_error_vocabulary_is_closed_ascii_and_bounded() -> None:
    assert set(ERROR_SUMMARIES) == set(ErrorCode)
    assert all(summary.isascii() and len(summary) <= 160 for summary in ERROR_SUMMARIES.values())
