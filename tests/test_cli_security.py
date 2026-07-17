"""Expanded untrusted-input and disclosure matrix for the packaged CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillscout import cli
from skillscout.adapters import fixtures
from skillscout.adapters.fixtures import load_fixture
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode, SafeFailure


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


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff\xfe\xfd",
        b'{"schema_version":"1"',
        json.dumps(_valid_fixture() | {"unexpected": "value"}).encode(),
        json.dumps(_valid_fixture() | {"schema_version": 1}).encode(),
        json.dumps(
            _valid_fixture()
            | {"subject_id": "fixture:../../GITHUB_TOKEN_DO_NOT_DISCLOSE"}
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
    from skillscout.adapters.state import SQLiteStateStore

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


def test_error_vocabulary_is_closed_ascii_and_bounded() -> None:
    assert set(ERROR_SUMMARIES) == set(ErrorCode)
    assert all(summary.isascii() and len(summary) <= 160 for summary in ERROR_SUMMARIES.values())
