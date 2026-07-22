"""End-to-end extract-repo CLI evidence over recorded transports."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from recorded_transport import (
    RecordedResponse,
    RecordedTransport,
    make_blob_fixture,
    recorded_fixture,
    recorded_openai_fixture,
)

from skillscout import cli
from skillscout.adapters.github import GitHubReadClient
from skillscout.adapters.openai_extract import OpenAIExtractionClient
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode
from skillscout.domain.models import ExtractionSummary

APPROVED_SUBJECT = Path(__file__).parent / "fixtures" / "subject" / "approved.json"

PINNED = "0123456789abcdef0123456789abcdef01234567"
README_SHA = "aa01aa01aa01aa01aa01aa01aa01aa01aa01aa01"
GUIDE_SHA = "bb02bb02bb02bb02bb02bb02bb02bb02bb02bb02"
BASIC_SHA = "aa06aa06aa06aa06aa06aa06aa06aa06aa06aa06"
PYPROJECT_SHA = "cc08cc08cc08cc08cc08cc08cc08cc08cc08cc08"
HELPER_SHA = "ee10ee10ee10ee10ee10ee10ee10ee10ee10ee10"
SCRIPT_SHA = "aa11aa11aa11aa11aa11aa11aa11aa11aa11aa11"
CORE_SHA = "dd09dd09dd09dd09dd09dd09dd09dd09dd09dd09"
ACTUAL_MODEL = "gpt-5.6-terra-2026-07-22"
GITHUB_TOKEN = "github_pat_CLI_FAKE_0123456789abcdef"
OPENAI_KEY = "sk-CLI-FAKE-0123456789abcdef"
FULL_TEXT_CANARY = "CANARY_FULL_TEXT_SENTENCE_DO_NOT_PERSIST_9f3b"
INVALID_ARGUMENTS_DIAGNOSTIC = (
    b'{"error":{"code":"invalid_cli_arguments",'
    b'"summary":"Command-line arguments were rejected."}}\n'
)

META = ("GET", "/repos/example/approved-repo")
PIN = ("GET", "/repos/example/approved-repo/commits/main")
TREE = ("GET", f"/repos/example/approved-repo/git/trees/{PINNED}?recursive=1")
LICENSE = ("GET", f"/repos/example/approved-repo/license?ref={PINNED}")
RESPONSES = ("POST", "/v1/responses")


@pytest.fixture(autouse=True)
def _fake_env_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLSCOUT_GITHUB_TOKEN", GITHUB_TOKEN)
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)


def _blob(sha: str) -> tuple[str, str]:
    return ("GET", f"/repos/example/approved-repo/git/blobs/{sha}")


def _github_routes(*, repo: str = "repo_mit") -> dict[tuple[str, str], RecordedResponse]:
    return {
        META: recorded_fixture(repo),
        PIN: recorded_fixture("commits_pin"),
        TREE: recorded_fixture("tree_full"),
        LICENSE: recorded_fixture("license_mit"),
        _blob(README_SHA): recorded_fixture("blob_readme"),
        _blob(GUIDE_SHA): recorded_fixture("blob_doc"),
        _blob(BASIC_SHA): recorded_fixture("blob_example"),
        _blob(PYPROJECT_SHA): recorded_fixture("blob_pyproject"),
        _blob(HELPER_SHA): make_blob_fixture(
            b"# lib helper\n" + b"h" * (1500 - 14) + b"\n", sha=HELPER_SHA
        ),
        _blob(SCRIPT_SHA): make_blob_fixture(
            b"# script\n" + b"s" * (700 - 10) + b"\n", sha=SCRIPT_SHA
        ),
        _blob(CORE_SHA): recorded_fixture("blob_source"),
    }


def _recorders(
    *, repo: str = "repo_mit", openai: str = "parsed_2_workflows"
) -> tuple[RecordedTransport, RecordedTransport]:
    return (
        RecordedTransport(_github_routes(repo=repo)),
        RecordedTransport({RESPONSES: recorded_openai_fixture(openai)}),
    )


def _patch_client_constructors(
    monkeypatch: pytest.MonkeyPatch,
    github_rec: RecordedTransport,
    openai_rec: RecordedTransport,
) -> None:
    def github_factory() -> GitHubReadClient:
        return GitHubReadClient(
            transport=github_rec.transport(), sleeper=lambda _seconds: None
        )

    def openai_factory() -> OpenAIExtractionClient:
        return OpenAIExtractionClient(
            http_client=httpx.Client(transport=openai_rec.transport())
        )

    monkeypatch.setattr(cli, "GitHubReadClient", github_factory)
    monkeypatch.setattr(cli, "OpenAIExtractionClient", openai_factory)


def _argv(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "extract-repo",
        "--subject",
        str(APPROVED_SUBJECT),
        "--state",
        str(tmp_path / "state.db"),
        "--output",
        str(tmp_path / "out"),
        *extra,
    ]


def _attempts(tmp_path: Path) -> list[dict[str, object]]:
    import sqlite3

    connection = sqlite3.connect(tmp_path / "state.db")
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT stage, status, prompt_version, model_id, request_id,
                      prompt_tokens, completion_tokens, total_tokens
               FROM stage_attempts ORDER BY stage_index, attempt_no"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def test_extract_repo_happy_path_completes_with_durable_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outbound_socket_sentinel: list[object],
) -> None:
    github_rec, openai_rec = _recorders()
    _patch_client_constructors(monkeypatch, github_rec, openai_rec)

    status = cli.main(_argv(tmp_path))
    captured = capsys.readouterr()

    assert status == 0
    assert captured.err == ""
    summary = json.loads(captured.out)
    assert summary["status"] == "completed"
    assert summary["last_stage"] == "extractor"
    assert summary["remote_writes_attempted"] == 0
    assert summary["reused_stage_count"] == 0
    assert summary["publication_plan_path"] == "extraction-summary.json"

    artifact = ExtractionSummary.model_validate_json(
        (tmp_path / "out" / "extraction-summary.json").read_bytes()
    )
    assert [(entry.stage.value, entry.outcome) for entry in artifact.stage_outcomes] == [
        ("scout", "accepted"),
        ("filter", "accepted"),
        ("reader", "accepted"),
        ("extractor", "extracted"),
    ]
    assert artifact.extractor_outcome == "extracted"
    assert artifact.repository == "https://github.com/example/approved-repo"
    assert artifact.pinned_commit_sha == PINNED
    assert artifact.workflow_count == 2
    assert len(artifact.workflow_fingerprints) == 2
    assert all(
        fingerprint.startswith("sha256:")
        for fingerprint in artifact.workflow_fingerprints
    )
    assert artifact.remote_writes_attempted == 0

    attempts = _attempts(tmp_path)
    assert [row["status"] for row in attempts] == ["succeeded"] * 4
    extractor_attempt = attempts[-1]
    assert extractor_attempt["stage"] == "extractor"
    assert extractor_attempt["prompt_version"] == "extract-prompt-v1"
    assert extractor_attempt["model_id"] == ACTUAL_MODEL
    assert extractor_attempt["request_id"] == "resp_ext_0001"
    assert extractor_attempt["prompt_tokens"] == 812
    assert extractor_attempt["completion_tokens"] == 246
    assert extractor_attempt["total_tokens"] == 1058

    durable = b"".join(
        path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()
    )
    for canary in (GITHUB_TOKEN, OPENAI_KEY, FULL_TEXT_CANARY):
        assert canary.encode() not in durable
        assert canary not in captured.out
        assert canary not in captured.err
    assert outbound_socket_sentinel == []
    assert openai_rec.call_count(*RESPONSES) == 1


def test_extract_repo_filter_rejection_never_calls_openai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outbound_socket_sentinel: list[object],
) -> None:
    github_rec, openai_rec = _recorders(repo="repo_archived")
    _patch_client_constructors(monkeypatch, github_rec, openai_rec)

    status = cli.main(_argv(tmp_path))
    captured = capsys.readouterr()

    assert status == 0
    summary = json.loads(captured.out)
    assert summary["status"] == "completed"
    artifact = ExtractionSummary.model_validate_json(
        (tmp_path / "out" / "extraction-summary.json").read_bytes()
    )
    assert [(entry.stage.value, entry.outcome) for entry in artifact.stage_outcomes] == [
        ("scout", "accepted"),
        ("filter", "rejected"),
        ("reader", "skipped"),
        ("extractor", "skipped"),
    ]
    assert artifact.extractor_outcome == "skipped"
    assert artifact.workflow_count == 0
    assert openai_rec.requests == []
    assert outbound_socket_sentinel == []


def test_extract_repo_resume_and_idempotent_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outbound_socket_sentinel: list[object],
) -> None:
    github_rec, openai_rec = _recorders()
    _patch_client_constructors(monkeypatch, github_rec, openai_rec)

    interrupted = cli.main(_argv(tmp_path, "--fail-after", "reader"))
    first = capsys.readouterr()
    assert interrupted == 1
    assert first.out == ""
    assert json.loads(first.err) == {
        "error": {
            "code": ErrorCode.PIPELINE_INTERRUPTED.value,
            "summary": ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
        }
    }
    assert openai_rec.requests == []

    resumed = cli.main(_argv(tmp_path))
    second = capsys.readouterr()
    assert resumed == 0
    summary = json.loads(second.out)
    assert summary["status"] == "completed"
    assert summary["reused_stage_count"] == 3

    # Scout/Filter endpoints were never re-called; blob GETs beyond the first
    # reader pass are the extractor's hash-verified hydration only.
    assert github_rec.call_count(*META) == 1
    assert github_rec.call_count(*PIN) == 1
    assert github_rec.call_count(*TREE) == 1
    assert github_rec.call_count(*LICENSE) == 1
    for sha in (
        README_SHA,
        GUIDE_SHA,
        BASIC_SHA,
        PYPROJECT_SHA,
        HELPER_SHA,
        SCRIPT_SHA,
        CORE_SHA,
    ):
        assert github_rec.call_count(*_blob(sha)) == 2
    assert openai_rec.call_count(*RESPONSES) == 1

    again = cli.main(_argv(tmp_path))
    third = capsys.readouterr()
    assert again == 0
    summary = json.loads(third.out)
    assert summary["status"] == "completed"
    assert summary["reused_stage_count"] == 4

    # Full reuse: the third invocation records zero remote calls of any kind.
    assert github_rec.call_count(*META) == 1
    assert sum(github_rec.calls.values()) == 4 + 14
    assert openai_rec.call_count(*RESPONSES) == 1
    assert outbound_socket_sentinel == []


def test_extract_repo_hostile_subjects_fail_closed_without_state(
    run_cli,
    tmp_path: Path,
) -> None:
    canary = "SUBJECT_HOSTILE_CANARY_DO_NOT_ECHO_9d2f"
    malformed = tmp_path / "malformed.json"
    malformed.write_bytes(b'{"hostile":"' + canary.encode() + b'",')
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b'{"pad":"' + (b"x" * 70_000) + b'"}')
    target = tmp_path / "target.json"
    target.write_text(APPROVED_SUBJECT.read_text(encoding="utf-8"), encoding="utf-8")
    symlinked = tmp_path / "symlinked.json"
    os.symlink(target, symlinked)

    for hostile in (malformed, oversized, symlinked):
        state = tmp_path / f"{hostile.stem}.db"
        result = run_cli(
            "extract-repo",
            "--subject",
            str(hostile),
            "--state",
            str(state),
            "--output",
            str(tmp_path / "out"),
        )
        assert result.returncode == 1
        assert result.stdout == ""
        assert json.loads(result.stderr) == {
            "error": {
                "code": ErrorCode.INVALID_SUBJECT.value,
                "summary": ERROR_SUMMARIES[ErrorCode.INVALID_SUBJECT],
            }
        }
        assert not state.exists()
        assert canary not in result.stdout
        assert canary not in result.stderr


def test_extract_repo_rejects_a_bad_fail_after_choice(run_cli, tmp_path: Path) -> None:
    result = run_cli(
        "extract-repo",
        "--subject",
        str(APPROVED_SUBJECT),
        "--state",
        str(tmp_path / "state.db"),
        "--output",
        str(tmp_path / "out"),
        "--fail-after",
        "bogus-stage",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.encode() == INVALID_ARGUMENTS_DIAGNOSTIC
    assert not (tmp_path / "state.db").exists()
