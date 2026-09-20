"""Selected Markdown previews reuse the bounded local evidence route."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy

import httpx
import pytest

from recorded_transport import (
    RecordedTransport,
    make_blob_entry,
    make_blob_fixture,
    make_tree_fixture,
    recorded_fixture,
)
from test_cli_extract_repo import GUIDE_SHA, PINNED, TREE, _blob, _github_routes
from test_local_evidence_preview import _selection_payload
from test_local_readme_preview import _argv, _results, _transports
from test_semantic_provider import CHAT_COMPLETIONS, _chat_response

from skillscout import cli
from skillscout.adapters.github import GitHubReadClient
from skillscout.adapters.openai_extract import OpenAIExtractionClient
from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
from skillscout.adapters.phase2_state import _validate_local_readme_chain
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.candidate_source import derive_candidate_subject_descriptors
from skillscout.application.ports import CandidateSourceUnavailable
from skillscout.domain.local_preview import LocalReadmeSubject
from skillscout.domain.reading import READER_ORG_MAX_FILE_BYTES
from skillscout.domain.subjects import RepositorySubject


MARKDOWN = "notes/Workflow Notes.MD"
MARKDOWN_FLAGS = [
    "--markdown-path",
    MARKDOWN,
    "--evidence-selection",
    "--source-only-fields",
    "--deepseek-current-flash",
]
MARKDOWN_POLICY = "reader-selected-markdown-v1"
MARKDOWN_RETRY = "retry-local-markdown-v1-once+extract-correction-policy-v1"
SOURCE_ONLY_PROMPT = "extract-local-evidence-source-only-fields-v1"


def _setup(monkeypatch, response=None, *, path=MARKDOWN, mode="100644", include=True):
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-selected-markdown")
    monkeypatch.delenv("SKILLSCOUT_GITHUB_TOKEN", raising=False)
    github, _unused = _transports(path=path, mode=mode, include=include)
    semantic = RecordedTransport(
        {}
        if response is None
        else {CHAT_COMPLETIONS: response}
    )
    monkeypatch.setattr(
        cli,
        "GitHubReadClient",
        lambda: GitHubReadClient(
            token="", transport=github.transport(), sleeper=lambda _seconds: None
        ),
    )
    monkeypatch.setattr(
        cli,
        "OpenAIExtractionClient",
        lambda **kwargs: OpenAIExtractionClient(
            http_client=httpx.Client(transport=semantic.transport()), **kwargs
        ),
    )
    return github, semantic


def _setup_entry(
    monkeypatch,
    *,
    raw: bytes | None,
    mode: str = "100644",
    entry_type: str = "blob",
    size: int | None = None,
):
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-selected-markdown")
    monkeypatch.delenv("SKILLSCOUT_GITHUB_TOKEN", raising=False)
    routes = _github_routes()
    routes[("GET", f"/repos/example/approved-repo/commits/{PINNED}")] = recorded_fixture(
        "commits_pin"
    )
    if raw is None:
        entry = {
            "path": MARKDOWN,
            "mode": mode,
            "type": entry_type,
            "sha": GUIDE_SHA,
            "size": size,
        }
    else:
        entry = make_blob_entry(MARKDOWN, raw)
        entry["mode"] = mode
        entry["type"] = entry_type
        if size is not None:
            entry["size"] = size
        routes[_blob(entry["sha"])] = make_blob_fixture(raw)
    tree = json.loads(routes[TREE].body)["tree"]
    routes[TREE] = make_tree_fixture(tree + [entry])
    github = RecordedTransport(routes)
    semantic = RecordedTransport({})
    monkeypatch.setattr(
        cli,
        "GitHubReadClient",
        lambda: GitHubReadClient(
            token="", transport=github.transport(), sleeper=lambda _seconds: None
        ),
    )
    monkeypatch.setattr(
        cli,
        "OpenAIExtractionClient",
        lambda **kwargs: OpenAIExtractionClient(
            http_client=httpx.Client(transport=semantic.transport()), **kwargs
        ),
    )
    return github, semantic


def _chain(path, run_id):
    state = SQLiteStateStore(path)
    try:
        return state.verify_run_chain(run_id)
    finally:
        state.close()


def test_selected_markdown_uses_v4_semantics_and_exports_one_local_descriptor(
    tmp_path, monkeypatch, capsys
):
    github, semantic = _setup(
        monkeypatch,
        _chat_response(json.dumps(_selection_payload()), model="deepseek-flash"),
    )

    assert cli.main(_argv(tmp_path, selected=None) + MARKDOWN_FLAGS) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    results = _results(tmp_path)
    reader = results["reader"]
    extractor = results["extractor"]
    assert reader["local_readme_scope"] == {
        "schema_version": "1",
        "subject_id": "repo:example/approved-repo",
        "repository": "https://github.com/example/approved-repo",
        "ref": PINNED,
        "scope_version": "local-markdown-v1",
        "readme_path": MARKDOWN,
    }
    assert reader["policy_version"] == MARKDOWN_POLICY
    assert [(item["path"], item["tier"]) for item in reader["files"]] == [
        (MARKDOWN, "docs")
    ]
    assert extractor["prompt_version"] == SOURCE_ONLY_PROMPT
    assert extractor["local_readme_scope"]["scope_version"] == "local-markdown-v1"
    assert extractor["workflows"][0]["evidence"][0]["path"] == MARKDOWN
    with sqlite3.connect(tmp_path / "state.db") as database:
        assert database.execute(
            "SELECT attempt_no,retry_policy_version FROM stage_attempts "
            "WHERE stage='extractor'"
        ).fetchall() == [(1, MARKDOWN_RETRY)]
    assert [
        request.url.path for request in github.requests if "/git/blobs/" in request.url.path
    ] == [_blob(GUIDE_SHA)[1]] * 2
    request = json.loads(semantic.requests[0].content)
    assert request["messages"][0]["content"].startswith(SOURCE_ONLY_PROMPT)
    assert request.get("tools", []) == []

    assert (
        cli.main(
            [
                "export-candidates",
                "--phase2-state",
                str(tmp_path / "state.db"),
                "--run-id",
                run_id,
                "--output",
                str(tmp_path / "export"),
            ]
        )
        == 0
    )
    exported = json.loads(capsys.readouterr().out)
    assert exported["candidate_count"] == 1
    descriptor_path = tmp_path / "export" / exported["candidates"][0]["descriptor_path"]
    descriptor_bytes = descriptor_path.read_bytes()
    source = SQLitePhaseTwoCandidateSource(tmp_path / "state.db", allow_local_readme=True)
    descriptor = derive_candidate_subject_descriptors(source, phase2_run_id=run_id)[0]
    assert json.loads(descriptor_bytes) == descriptor.model_dump(mode="json")
    assert source.resolve(descriptor).pinned_commit_sha == PINNED


@pytest.mark.parametrize(
    "extra",
    [
        ["--markdown-path", "../Workflow.md", "--evidence-selection", "--source-only-fields"],
        ["--markdown-path", "", "--evidence-selection", "--source-only-fields"],
        ["--markdown-path", "notes/Workflow.txt", "--evidence-selection", "--source-only-fields"],
        ["--markdown-path", MARKDOWN, "--source-only-fields"],
        ["--markdown-path", MARKDOWN, "--evidence-selection"],
        [
            "--readme-path",
            "README.md",
            "--markdown-path",
            MARKDOWN,
            "--evidence-selection",
            "--source-only-fields",
        ],
    ],
    ids=[
        "unsafe",
        "empty",
        "non-markdown",
        "missing-evidence",
        "missing-source",
        "two-paths",
    ],
)
def test_markdown_cli_rejects_invalid_opt_in_before_state_or_clients(
    tmp_path, monkeypatch, capsys, extra
):
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-selected-markdown")
    constructed = []
    monkeypatch.setattr(cli, "SQLiteStateStore", lambda *_args: constructed.append("state"))
    monkeypatch.setattr(cli, "GitHubReadClient", lambda: constructed.append("github"))
    monkeypatch.setattr(
        cli, "OpenAIExtractionClient", lambda **_kwargs: constructed.append("semantic")
    )

    try:
        status = cli.main(_argv(tmp_path, selected=None) + extra)
    except SystemExit as failure:
        status = failure.code

    assert status in {1, 2}
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] in {"invalid_subject", "invalid_cli_arguments"}
    assert not (tmp_path / "state.db").exists()
    assert constructed == []


@pytest.mark.parametrize("mutation", ["reader-policy", "retry", "path", "extra-file"])
def test_markdown_chain_rejects_mismatched_scope_file_and_execution_identity(
    tmp_path, monkeypatch, capsys, mutation
):
    _github, _semantic = _setup(
        monkeypatch,
        _chat_response(json.dumps(_selection_payload()), model="deepseek-flash"),
    )
    assert cli.main(_argv(tmp_path, selected=None) + MARKDOWN_FLAGS) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    chain = _chain(tmp_path / "state.db", run_id)
    assert _validate_local_readme_chain(chain, allow=True)["path"] == MARKDOWN

    results = list(chain.results)
    if mutation == "retry":
        chain = chain.model_copy(
            update={
                "identity": chain.identity.model_copy(
                    update={"retry_policy_version": "retry-local-readme-v4-once"}
                )
            }
        )
    else:
        reader = results[2]
        payload = deepcopy(reader.payload)
        if mutation == "reader-policy":
            payload["policy_version"] = "reader-selected-readme-v1"
            reader = reader.model_copy(update={"policy_version": "reader-selected-readme-v1"})
        elif mutation == "path":
            payload["files"][0]["path"] = "notes/Other.MD"
        else:
            payload["files"].append(deepcopy(payload["files"][0]))
        results[2] = reader.model_copy(update={"payload": payload})
        chain = chain.model_copy(update={"results": tuple(results)})

    with pytest.raises(ValueError):
        _validate_local_readme_chain(chain, allow=True)


@pytest.mark.parametrize(
    ("raw", "mode", "entry_type", "size", "expected_blob_reads"),
    [
        (None, "040000", "tree", None, 0),
        (b"\xff", "100644", "blob", None, 1),
        (None, "100644", "blob", READER_ORG_MAX_FILE_BYTES + 1, 0),
    ],
    ids=["non-regular", "invalid-utf8", "oversize"],
)
def test_invalid_markdown_source_never_falls_back_or_requests_model(
    tmp_path, monkeypatch, capsys, raw, mode, entry_type, size, expected_blob_reads
):
    github, semantic = _setup_entry(
        monkeypatch, raw=raw, mode=mode, entry_type=entry_type, size=size
    )
    assert cli.main(_argv(tmp_path, selected=None) + MARKDOWN_FLAGS) == 0
    capsys.readouterr()

    results = _results(tmp_path)
    assert results["reader"]["files"] == []
    assert results["extractor"]["skip_reason"] == "reader_empty"
    assert len([r for r in github.requests if "/git/blobs/" in r.url.path]) == expected_blob_reads
    assert semantic.requests == []


def test_empty_markdown_catalogue_records_identity_without_model_request(
    tmp_path, monkeypatch, capsys
):
    _github, semantic = _setup_entry(monkeypatch, raw=b"https://ignored.invalid\n")
    assert cli.main(_argv(tmp_path, selected=None) + MARKDOWN_FLAGS) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    extractor = _results(tmp_path)["extractor"]
    assert extractor["skip_reason"] == "no_eligible_evidence"
    assert extractor["prompt_version"] == SOURCE_ONLY_PROMPT
    assert extractor["local_readme_scope"]["scope_version"] == "local-markdown-v1"
    assert semantic.requests == []
    assert _validate_local_readme_chain(
        _chain(tmp_path / "state.db", run_id), allow=True
    )["path"] == MARKDOWN


def test_unknown_markdown_outcome_is_consumed_without_replay(
    tmp_path, monkeypatch, capsys
):
    _github, semantic = _setup(
        monkeypatch,
        _chat_response(json.dumps(_selection_payload()), model="different-model"),
    )
    argv = _argv(tmp_path, selected=None) + MARKDOWN_FLAGS
    assert cli.main(argv) == 1
    capsys.readouterr()
    assert cli.main(argv) == 1
    capsys.readouterr()

    assert semantic.call_count(*CHAT_COMPLETIONS) == 1
    with sqlite3.connect(tmp_path / "state.db") as database:
        assert database.execute(
            "SELECT attempt_no,retry_policy_version,retryable FROM stage_attempts "
            "WHERE stage='extractor'"
        ).fetchall() == [(1, MARKDOWN_RETRY, 0)]


def test_markdown_policy_marker_is_local_even_without_scope_envelopes(
    tmp_path, monkeypatch, capsys
):
    _github, _semantic = _setup(
        monkeypatch,
        _chat_response(json.dumps(_selection_payload()), model="deepseek-flash"),
    )
    assert cli.main(_argv(tmp_path, selected=None) + MARKDOWN_FLAGS) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    chain = _chain(tmp_path / "state.db", run_id)
    stripped = tuple(
        result.model_copy(
            update={
                "payload": {
                    key: value
                    for key, value in result.payload.items()
                    if key != "local_readme_scope"
                }
            }
        )
        for result in chain.results
    )
    with pytest.raises(ValueError):
        _validate_local_readme_chain(
            chain.model_copy(update={"results": stripped}), allow=True
        )

    source = SQLitePhaseTwoCandidateSource(tmp_path / "state.db")
    with pytest.raises(CandidateSourceUnavailable):
        derive_candidate_subject_descriptors(source, phase2_run_id=run_id)


def test_legacy_readme_scopes_and_unscoped_subject_keep_their_input_contracts():
    common = {
        "schema_version": "1",
        "subject_id": "repo:example/approved-repo",
        "repository": "https://github.com/example/approved-repo",
        "ref": PINNED,
        "readme_path": "docs/README.MD",
    }
    assert [
        LocalReadmeSubject.model_validate(
            common | {"scope_version": scope}, strict=True
        ).scope_version
        for scope in (
            "local-readme-v1",
            "local-readme-v2",
            "local-readme-v3",
            "local-readme-v4",
        )
    ] == [
        "local-readme-v1",
        "local-readme-v2",
        "local-readme-v3",
        "local-readme-v4",
    ]
    ordinary = RepositorySubject.model_validate(
        {key: value for key, value in common.items() if key != "readme_path"},
        strict=True,
    )
    assert ordinary.model_dump(mode="json", exclude_none=False) == {
        "schema_version": "1",
        "subject_id": "repo:example/approved-repo",
        "repository": "https://github.com/example/approved-repo",
        "ref": PINNED,
    }
