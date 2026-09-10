"""Offline candidate export reuses verified Phase 2 authority, never model access."""

import json
import sqlite3
from pathlib import Path

import pytest

from skillscout import cli
from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
from skillscout.application.candidate_source import load_candidate_subject
from test_candidate_source import (
    PINNED_SHA,
    _all_persisted_bytes,
    _create_phase2_state,
    _workflow,
)


def _args(state: Path, run_id: str, output: Path) -> list[str]:
    return [
        "export-candidates",
        "--phase2-state",
        str(state),
        "--run-id",
        run_id,
        "--output",
        str(output),
    ]


def test_exported_descriptor_loads_without_editing_and_preserves_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    outbound_socket_sentinel: object,
) -> None:
    state, expected, workflow = _create_phase2_state(tmp_path)
    before = _all_persisted_bytes(state)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "invalid-no-provider-needed")
    output = tmp_path / "candidates"
    assert cli.main(_args(state, expected.phase2_run_id, output)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == "local-candidate-export-v1"
    assert result["status"] == "exported"
    assert result["remote_writes_attempted"] == 0
    assert result["candidate_count"] == 1
    entry = result["candidates"][0]
    assert entry["repository_url"] == "https://github.com/example/approved-repo"
    assert entry["pinned_commit_sha"] == PINNED_SHA
    assert entry["license_spdx"] == "MIT"
    path = output / entry["descriptor_path"]
    resolved = load_candidate_subject(path, SQLitePhaseTwoCandidateSource(state))
    assert resolved.descriptor == expected
    assert resolved.descriptor.selected_workflow_fingerprint == workflow.fingerprint
    assert path.stat().st_mode & 0o777 == 0o600
    assert output.stat().st_mode & 0o777 == 0o700
    assert _all_persisted_bytes(state) == before


def test_export_sorts_three_verified_candidates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workflows = tuple(_workflow(i).model_dump(mode="json") for i in (2, 0, 1))
    state, descriptor, _ = _create_phase2_state(tmp_path, workflows=workflows)
    output = tmp_path / "candidates"
    assert cli.main(_args(state, descriptor.phase2_run_id, output)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["candidate_count"] == 3
    assert [entry["workflow_fingerprint"] for entry in result["candidates"]] == sorted(
        workflow["fingerprint"] for workflow in workflows
    )[:3]
    assert len(list(output.iterdir())) == 3


@pytest.mark.parametrize("broken", ["missing", "unknown-run", "incomplete", "tampered"])
def test_invalid_source_emits_no_descriptor(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    broken: str,
) -> None:
    state, descriptor, _ = _create_phase2_state(
        tmp_path,
        fail_after="reader" if broken == "incomplete" else None,
    )
    if broken == "tampered":
        with sqlite3.connect(state) as connection:
            connection.execute("UPDATE runs SET producer_version = 'tampered'")
    input_state = tmp_path / "missing.db" if broken == "missing" else state
    run_id = "unknown" if broken == "unknown-run" else descriptor.phase2_run_id
    output = tmp_path / "candidates"
    assert cli.main(_args(input_state, run_id, output)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "candidate_source_unavailable"
    assert not output.exists()
    if broken == "missing":
        assert not input_state.exists()


def test_no_workflow_is_empty_export_not_an_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state, descriptor, _ = _create_phase2_state(tmp_path, outcome="no_workflow")
    output = tmp_path / "candidates"
    assert cli.main(_args(state, descriptor.phase2_run_id, output)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "no_candidates"
    assert result["candidate_count"] == 0
    assert result["candidates"] == []
    assert not output.exists()


@pytest.mark.parametrize("destination", ["existing", "symlink", "ancestor-symlink", "manifest"])
def test_export_never_overwrites_or_writes_into_source_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    destination: str,
) -> None:
    state, descriptor, _ = _create_phase2_state(tmp_path)
    output = tmp_path / "candidates"
    if destination == "existing":
        output.mkdir()
        (output / "keep").write_text("untouched")
    elif destination == "symlink":
        output.symlink_to(state.with_suffix(".manifests"), target_is_directory=True)
    elif destination == "ancestor-symlink":
        link = tmp_path / "link"
        link.symlink_to(tmp_path, target_is_directory=True)
        output = link / "candidates"
    else:
        output = state.with_suffix(".manifests") / "candidates"
    before = _all_persisted_bytes(state)
    assert cli.main(_args(state, descriptor.phase2_run_id, output)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "state_operation_failed"
    assert _all_persisted_bytes(state) == before
    if destination == "existing":
        assert (output / "keep").read_text() == "untouched"


def test_export_rejects_symlinked_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state, descriptor, _ = _create_phase2_state(tmp_path)
    alias = tmp_path / "alias.db"
    alias.symlink_to(state)
    output = tmp_path / "candidates"
    assert cli.main(_args(alias, descriptor.phase2_run_id, output)) == 1
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "candidate_source_unavailable"
    assert not output.exists()
