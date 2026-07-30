"""Expanded untrusted-input and disclosure matrix for the packaged CLI."""

from __future__ import annotations

import argparse
import ast
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

from test_cli_validate_skill import _argv, _patch_phase3_ports
from test_phase3_pipeline import (
    _recursive_exact_snapshot,
    _workflow,
    _write_composition_descriptor_for_workflow,
)

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
    assert set(subparsers.choices) == {
        "build-candidate",
        "discover",
        "dry-run",
        "extract-repo",
        "inspect-run",
        "nominate-benchmark",
        "publish-discovered",
        "publish-candidate",
        "rebuild-acceptance",
        "record-acceptance-attestation",
        "resolve-acceptance-resume",
        "run-acceptance",
        "verify-acceptance-state",
        "verify-live-authority",
        "verify-publication-admission",
    }
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


def _candidate_descriptor(tmp_path: Path) -> tuple[Path, object]:
    workflow = _workflow()
    descriptor_root = tmp_path / "descriptor"
    descriptor_root.mkdir(mode=0o700)
    return (
        _write_composition_descriptor_for_workflow(
            descriptor_root,
            workflow=workflow,
        ),
        workflow,
    )


def test_skillscout_source_uses_argparse_and_never_imports_click() -> None:
    source_root = Path(cli.__file__).parent
    importers: dict[str, set[str]] = {}
    for path in source_root.rglob("*.py"):
        names: set[str] = set()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".", 1)[0])
        importers[path.relative_to(source_root).as_posix()] = names

    assert "argparse" in importers["cli.py"]
    assert all("click" not in names for names in importers.values())


def test_build_candidate_help_has_no_publish_shell_install_or_execution_route(
    run_cli,
) -> None:
    result = run_cli("build-candidate", "--help")

    assert result.returncode == 0
    assert result.stderr == ""
    help_text = result.stdout.casefold()
    assert {
        "--candidate",
        "--phase2-state",
        "--state",
        "--output",
        "--fail-after",
    }.issubset(help_text.split())
    for prohibited in (
        "click",
        "publish",
        "pull-request",
        "merge",
        "approve",
        "shell",
        "install",
        "execute",
        "renderer-version",
        "eligibility-policy-version",
        "workflow-fingerprint",
    ):
        assert prohibited not in help_text


def test_publication_command_help_has_only_closed_locator_contracts(run_cli) -> None:
    verifier = run_cli("verify-publication-admission", "--help")
    publisher = run_cli("publish-candidate", "--help")

    assert verifier.returncode == publisher.returncode == 0
    assert verifier.stderr == publisher.stderr == ""
    verifier_options = set(verifier.stdout.split())
    publisher_options = set(publisher.stdout.split())
    assert {"--candidate", "--phase2-state", "--phase3-state", "--compare-env"}.issubset(verifier_options)
    assert {"--candidate", "--phase2-state", "--phase3-state", "--publication-state"}.issubset(publisher_options)
    forbidden = {"--repository", "--branch", "--reviewer", "--merge", "--approve", "--ready", "--force", "--ruleset"}
    assert forbidden.isdisjoint(verifier_options)
    assert forbidden.isdisjoint(publisher_options)


def test_discovery_entrypoint_help_has_no_authority_widening_options(run_cli) -> None:
    discover = run_cli("discover", "--help")
    protected = run_cli("publish-discovered", "--help")

    assert discover.returncode == protected.returncode == 0
    assert discover.stderr == protected.stderr == ""
    discover_options = set(discover.stdout.split())
    protected_options = set(protected.stdout.split())
    assert {
        "--state-repository-id",
        "--state-repository-full-name",
        "--initial-state-root-digest",
    }.issubset(discover_options)
    assert {"--handoff"}.issubset(protected_options)
    forbidden = {
        "--query",
        "--budget",
        "--branch",
        "--reviewer",
        "--admission",
        "--token",
        "--retry",
        "--force",
        "--merge",
        "--approve",
    }
    assert forbidden.isdisjoint(discover_options)
    assert forbidden.isdisjoint(protected_options)


@pytest.mark.parametrize("unsafe_shape", ("nested-state", "nonempty-output"))
def test_build_candidate_rejects_unsafe_output_before_state_or_semantic_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    unsafe_shape: str,
) -> None:
    descriptor, workflow = _candidate_descriptor(tmp_path)
    calls: list[str] = []
    _patch_phase3_ports(
        monkeypatch,
        workflow=workflow,
        outcome="generator_refusal",
        calls=calls,
    )
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    state = (
        output / "phase3.db"
        if unsafe_shape == "nested-state"
        else tmp_path / "phase3.db"
    )
    if unsafe_shape == "nonempty-output":
        (output / "operator-file").write_bytes(b"must-not-be-overwritten")
    before = _recursive_exact_snapshot(tmp_path)

    status = cli.main(
        _argv(
            descriptor=descriptor,
            phase2_state=tmp_path / "phase2.db",
            state=state,
            output=output,
        )
    )
    captured = capsys.readouterr()

    assert status == 1
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "state_operation_failed"
    assert calls == []
    assert not state.exists()
    assert _recursive_exact_snapshot(tmp_path) == before


def test_completed_candidate_cli_uses_only_read_opens_and_private_memory_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    descriptor, workflow = _candidate_descriptor(tmp_path)
    calls: list[str] = []
    _patch_phase3_ports(
        monkeypatch,
        workflow=workflow,
        outcome="generator_refusal",
        calls=calls,
    )
    state = tmp_path / "phase3.db"
    output = tmp_path / "output"
    argv = _argv(
        descriptor=descriptor,
        phase2_state=tmp_path / "phase2.db",
        state=state,
        output=output,
    )
    assert cli.main(argv) == 0
    capsys.readouterr()
    first_calls = tuple(calls)
    before = _recursive_exact_snapshot(tmp_path)

    from skillscout.adapters import state as state_adapter

    real_open = os.open
    real_connect = state_adapter.sqlite3.connect
    sqlite_targets: list[object] = []
    mutation_calls: list[str] = []
    open_calls: list[int] = []
    forbidden_flags = (
        os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_TRUNC | os.O_APPEND
    )

    def read_only_open(path, flags, *args, **kwargs):
        open_calls.append(flags)
        assert flags & forbidden_flags == 0
        return real_open(path, flags, *args, **kwargs)

    def memory_connect(database, *args, **kwargs):
        sqlite_targets.append(database)
        assert database == ":memory:"
        return real_connect(database, *args, **kwargs)

    def forbidden(name: str):
        def reject(*_args, **_kwargs):
            mutation_calls.append(name)
            raise AssertionError("completed projection attempted mutation")

        return reject

    monkeypatch.setattr(state_adapter.os, "open", read_only_open)
    monkeypatch.setattr(state_adapter.sqlite3, "connect", memory_connect)
    supported_dir_fd = set(os.supports_dir_fd)
    supported_dir_fd.add(read_only_open)
    for name in (
        "mkdir",
        "write",
        "replace",
        "rename",
        "unlink",
        "chmod",
        "fchmod",
        "utime",
        "fsync",
        "fdatasync",
    ):
        if hasattr(state_adapter.os, name):
            original = getattr(state_adapter.os, name)
            replacement = forbidden(name)
            monkeypatch.setattr(state_adapter.os, name, replacement)
            if original in os.supports_dir_fd:
                supported_dir_fd.add(replacement)
    monkeypatch.setattr(state_adapter.os, "supports_dir_fd", supported_dir_fd)
    monkeypatch.setattr(cli, "SQLiteStateStore", forbidden("mutable-state"))
    monkeypatch.setattr(
        cli,
        "LocalCandidateArtifactProjector",
        forbidden("artifact-projector"),
    )

    status = cli.main(argv)
    captured = capsys.readouterr()

    assert mutation_calls == []
    assert status == 0, (captured.err, sqlite_targets, open_calls)
    assert json.loads(captured.out)["outcome"] == "generator_refusal"
    assert tuple(calls) == first_calls
    assert sqlite_targets == [":memory:"]
    assert _recursive_exact_snapshot(tmp_path) == before


def test_build_candidate_environment_secret_is_absent_from_every_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "sk-proj-CLI-SECRET-MUST-NOT-APPEAR-0123456789"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    descriptor, workflow = _candidate_descriptor(tmp_path)
    calls: list[str] = []
    _patch_phase3_ports(
        monkeypatch,
        workflow=workflow,
        outcome="eligible_local_candidate",
        calls=calls,
    )

    status = cli.main(
        _argv(
            descriptor=descriptor,
            phase2_state=tmp_path / "phase2.db",
            state=tmp_path / "phase3.db",
            output=tmp_path / "output",
        )
    )
    captured = capsys.readouterr()

    assert status == 0, captured.err
    surfaces = captured.out.encode() + captured.err.encode() + _all_bytes(tmp_path)
    assert secret.encode() not in surfaces
