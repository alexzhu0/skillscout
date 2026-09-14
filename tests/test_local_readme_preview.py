"""Selected README previews bind one inert file without changing hosted reads."""

import json
import sqlite3
from copy import deepcopy

import pytest

from recorded_transport import (
    RecordedResponse,
    RecordedTransport,
    recorded_fixture,
    recorded_openai_fixture,
)
from test_cli_extract_repo import (
    GUIDE_SHA,
    PINNED,
    RESPONSES,
    TREE,
    _blob,
    _github_routes,
    _patch_client_constructors,
)

from skillscout import cli
from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
from skillscout.application.candidate_source import derive_candidate_subject_descriptors
from skillscout.application.ports import CandidateSourceUnavailable
from skillscout.adapters.state import SQLiteStateStore
from skillscout.adapters.phase2_state import _validate_local_readme_chain


SELECTED = "python/end-to-end-applications/rag-ingestion/README.md"


@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-selected-readme")
    monkeypatch.delenv("SKILLSCOUT_GITHUB_TOKEN", raising=False)


def _response(body):
    return RecordedResponse(200, {"content-type": "application/json"}, json.dumps(body).encode())


def _transports(*, path=SELECTED, mode="100644", include=True):
    routes = _github_routes()
    routes[("GET", f"/repos/example/approved-repo/commits/{PINNED}")] = recorded_fixture(
        "commits_pin"
    )
    tree = json.loads(routes[TREE].body)
    if include:
        tree["tree"].append(
            {
                "path": path,
                "mode": mode,
                "type": "blob",
                "sha": GUIDE_SHA,
                "size": json.loads(recorded_fixture("blob_doc").body)["size"],
            }
        )
    routes[TREE] = _response(tree)
    response = json.loads(recorded_openai_fixture("parsed_2_workflows").body)
    content = response["output"][0]["content"][0]
    parsed = json.loads(content["text"])
    parsed["workflows"] = parsed["workflows"][:1]
    workflow = parsed["workflows"][0]
    for evidence in workflow["evidence"] + [
        e for step in workflow["steps"] for e in step["evidence"]
    ]:
        evidence["path"] = path
    content["text"] = json.dumps(parsed)
    return RecordedTransport(routes), RecordedTransport({RESPONSES: _response(response)})


def _argv(tmp_path, *, selected=SELECTED, ref=PINNED):
    subject = tmp_path / "subject.json"
    subject.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "subject_id": "repo:example/approved-repo",
                "repository": "https://github.com/example/approved-repo",
                "ref": ref,
            }
        )
    )
    args = [
        "extract-repo",
        "--subject",
        str(subject),
        "--state",
        str(tmp_path / "state.db"),
        "--output",
        str(tmp_path / "out"),
    ]
    return args + (["--readme-path", selected] if selected is not None else [])


def _results(tmp_path):
    with sqlite3.connect(f"file:{tmp_path / 'state.db'}?mode=ro", uri=True) as connection:
        return {
            stage: json.loads(raw)
            for stage, raw in connection.execute(
                "SELECT stage, output_json FROM stage_results ORDER BY stage_index"
            )
        }


def test_selected_readme_only_is_read_and_is_bound_into_the_workflow(
    tmp_path, monkeypatch, capsys, outbound_socket_sentinel
):
    github, semantic = _transports()
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path)) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    results = _results(tmp_path)
    reader = results["reader"]
    assert [file["path"] for file in reader["files"]] == [SELECTED]
    assert reader["policy_version"] == "reader-selected-readme-v1"
    assert reader["source_code_loaded"] is False
    workflow = results["extractor"]["workflows"][0]
    assert workflow["evidence"][0]["path"] == SELECTED
    assert workflow["evidence"][0]["blob_sha"] == GUIDE_SHA
    blob_requests = [request for request in github.requests if "/git/blobs/" in request.url.path]
    # Reader observes the file, then Extractor rehydrates the same immutable blob.
    assert [request.url.path for request in blob_requests] == [_blob(GUIDE_SHA)[1]] * 2
    assert semantic.call_count(*RESPONSES) == 1
    assert outbound_socket_sentinel == []


@pytest.mark.parametrize(
    ("path", "ref"),
    [
        (SELECTED, "main"),
        (SELECTED, None),
        ("../README.md", PINNED),
        ("/tmp/README.md", PINNED),
        ("python/./README.md", PINNED),
        ("python//README.md", PINNED),
        ("python/script.py", PINNED),
        (".env", PINNED),
        ("python/README.md\n", PINNED),
    ],
)
def test_invalid_selected_input_stops_before_state_or_network(
    tmp_path, monkeypatch, capsys, path, ref
):
    github, semantic = _transports()
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path, selected=path, ref=ref)) == 1
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_subject"
    assert not (tmp_path / "state.db").exists()
    assert github.requests == semantic.requests == []


@pytest.mark.parametrize(
    ("include", "mode"), [(False, "100644"), (True, "120000"), (True, "160000")]
)
def test_missing_or_indirect_selected_file_never_falls_back(
    tmp_path, monkeypatch, capsys, include, mode
):
    github, semantic = _transports(include=include, mode=mode)
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path)) == 0
    capsys.readouterr()
    results = _results(tmp_path)
    assert results["reader"]["files"] == []
    assert results["extractor"]["skip_reason"] == "reader_empty"
    assert not [r for r in github.requests if "/git/blobs/" in r.url.path]
    assert semantic.requests == []


def test_selected_candidates_are_local_only_and_export_keeps_their_chain(
    tmp_path, monkeypatch, capsys
):
    github, semantic = _transports()
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path)) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    with pytest.raises(CandidateSourceUnavailable):
        derive_candidate_subject_descriptors(
            SQLitePhaseTwoCandidateSource(tmp_path / "state.db"),
            phase2_run_id=run_id,
        )
    source = SQLitePhaseTwoCandidateSource(tmp_path / "state.db", allow_local_readme=True)
    descriptors = derive_candidate_subject_descriptors(source, phase2_run_id=run_id)
    assert len(descriptors) == 1
    projection = source.resolve(descriptors[0])
    assert projection.pinned_commit_sha == PINNED
    assert projection.license_spdx == "MIT"
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
    assert exported["candidates"][0]["pinned_commit_sha"] == PINNED
    assert semantic.call_count(*RESPONSES) == 1


def test_selected_completed_replay_makes_no_more_requests(tmp_path, monkeypatch, capsys):
    github, semantic = _transports()
    _patch_client_constructors(monkeypatch, github, semantic)
    argv = _argv(tmp_path)
    assert cli.main(argv) == 0
    first = json.loads(capsys.readouterr().out)
    observed_reads = len(github.requests)
    assert cli.main(argv) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["run_id"] == first["run_id"]
    assert second["reused_stage_count"] == 4
    assert len(github.requests) == observed_reads
    assert semantic.call_count(*RESPONSES) == 1


def test_missing_exact_ref_exports_zero_candidates_without_model_call(
    tmp_path, monkeypatch, capsys
):
    routes = _github_routes()
    routes[("GET", f"/repos/example/approved-repo/commits/{PINNED}")] = RecordedResponse(
        404, {}, b"{}"
    )
    github = RecordedTransport(routes)
    semantic = RecordedTransport({})
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path)) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
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
    assert json.loads(capsys.readouterr().out)["candidate_count"] == 0
    assert semantic.requests == []


def test_real_selected_chain_builds_locally_but_publication_projection_rejects_it(
    tmp_path, monkeypatch, capsys
):
    from test_cli_validate_skill import _argv as build_argv, _patch_phase3_ports
    from skillscout.bootstrap import _publication_projection
    from skillscout.application.ports import SafeFailure, ErrorCode
    from skillscout.domain.extraction import WorkflowSpec
    from skillscout.domain.canonical import canonical_json_bytes

    github, semantic = _transports()
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path)) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    source = SQLitePhaseTwoCandidateSource(tmp_path / "state.db", allow_local_readme=True)
    descriptor = derive_candidate_subject_descriptors(source, phase2_run_id=run_id)[0]
    descriptor_path = tmp_path / "candidate.json"
    descriptor_path.write_bytes(canonical_json_bytes(descriptor.model_dump(mode="json")))
    descriptor_path.chmod(0o600)
    workflow = WorkflowSpec.model_validate_json(
        json.dumps(_results(tmp_path)["extractor"]["workflows"][0]), strict=True
    )
    calls = []
    _patch_phase3_ports(
        monkeypatch, workflow=workflow, outcome="eligible_local_candidate", calls=calls
    )
    monkeypatch.setattr(cli, "SQLitePhaseTwoCandidateSource", SQLitePhaseTwoCandidateSource)
    assert (
        cli.main(
            build_argv(
                descriptor=descriptor_path,
                phase2_state=tmp_path / "state.db",
                state=tmp_path / "phase3.db",
                output=tmp_path / "candidate-output",
            )
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["outcome"] == "eligible_local_candidate"
    assert "generator" in calls and "reviewer" in calls
    with pytest.raises(SafeFailure) as failure:
        _publication_projection(
            candidate=descriptor_path,
            phase2_state=tmp_path / "state.db",
            phase3_state=tmp_path / "phase3.db",
            environ={},
        )
    assert failure.value.code is ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE


def test_selected_reader_does_not_inherit_ordinary_permanent_failure(tmp_path, monkeypatch, capsys):
    from test_cli_extract_repo import README_SHA

    github, semantic = _transports()
    routes = _github_routes()
    routes[("GET", f"/repos/example/approved-repo/commits/{PINNED}")] = recorded_fixture(
        "commits_pin"
    )
    routes[_blob(README_SHA)] = RecordedResponse(400, {}, b"{}")
    ordinary = RecordedTransport(routes)
    _patch_client_constructors(monkeypatch, ordinary, semantic)
    assert cli.main(_argv(tmp_path, selected=None)) == 1
    capsys.readouterr()
    assert semantic.requests == []
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path)) == 0
    capsys.readouterr()
    with sqlite3.connect(tmp_path / "state.db") as connection:
        readers = connection.execute(
            "SELECT status, reusable_key_digest FROM stage_attempts WHERE stage='reader' ORDER BY started_at"
        ).fetchall()
        hashes = connection.execute("SELECT fixture_hash FROM runs").fetchall()
    assert [row[0] for row in readers] == ["failed", "succeeded"]
    assert len({row[1] for row in readers}) == 2
    assert len(set(hashes)) == 2
    assert semantic.call_count(*RESPONSES) == 1


def test_selected_mode_rejects_nonregular_tree_mode_before_blob_or_model(
    tmp_path, monkeypatch, capsys
):
    github, semantic = _transports(mode="040000")
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path)) == 0
    capsys.readouterr()
    assert _results(tmp_path)["reader"]["files"] == []
    assert not [r for r in github.requests if "/git/blobs/" in r.url.path]
    assert semantic.requests == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_filter_scope",
        "changed_path",
        "wrong_fixture",
        "wrong_ref",
        "extra_file",
        "wrong_policy",
        "wrong_blob",
        "wrong_budget",
    ],
)
def test_scoped_chain_rejects_inconsistent_authority(tmp_path, monkeypatch, capsys, mutation):
    github, semantic = _transports()
    _patch_client_constructors(monkeypatch, github, semantic)
    assert cli.main(_argv(tmp_path)) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    state = SQLiteStateStore(tmp_path / "state.db")
    try:
        chain = state.verify_run_chain(run_id)
    finally:
        state.close()
    assert _validate_local_readme_chain(chain, allow=True)["path"] == SELECTED
    results = list(chain.results)
    payloads = [deepcopy(result.payload) for result in results]
    if mutation == "missing_filter_scope":
        del payloads[1]["local_readme_scope"]
    elif mutation == "changed_path":
        payloads[2]["local_readme_scope"]["readme_path"] = "elsewhere/README.md"
    elif mutation == "wrong_fixture":
        chain = chain.model_copy(
            update={
                "identity": chain.identity.model_copy(update={"fixture_hash": "sha256:" + "0" * 64})
            }
        )
    elif mutation == "wrong_ref":
        payloads[0]["ref_requested"] = "f" * 40
    elif mutation == "extra_file":
        payloads[2]["files"].append(deepcopy(payloads[2]["files"][0]))
    elif mutation == "wrong_policy":
        payloads[2]["policy_version"] = "reader-policy-v1"
    elif mutation == "wrong_blob":
        payloads[2]["files"][0]["blob_sha"] = "f" * 40
    else:
        payloads[2]["budgets"]["files_read"] = 2
    changed = tuple(
        result.model_copy(update={"payload": payload})
        for result, payload in zip(results, payloads, strict=True)
    )
    # Exercise the additional scoped verifier independently of generic hash checks.
    with pytest.raises(ValueError):
        _validate_local_readme_chain(chain.model_copy(update={"results": changed}), allow=True)
