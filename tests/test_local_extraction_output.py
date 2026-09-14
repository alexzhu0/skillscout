"""Local output-policy identity and non-content failure evidence."""

import json
import sqlite3

import httpx
import pytest

from recorded_transport import RecordedResponse, RecordedTransport, recorded_openai_fixture
from test_local_readme_preview import SELECTED, _argv, _results, _transports
from test_semantic_provider import CHAT_COMPLETIONS, _chat_response

from skillscout import cli
from skillscout.adapters.github import GitHubReadClient
from skillscout.adapters.openai_extract import OpenAIExtractionClient


def _response_payload():
    body = json.loads(recorded_openai_fixture("parsed_2_workflows").body)
    parsed = json.loads(body["output"][0]["content"][0]["text"])
    parsed["workflows"] = parsed["workflows"][:1]
    workflow = parsed["workflows"][0]
    for evidence in workflow["evidence"] + [
        e for step in workflow["steps"] for e in step["evidence"]
    ]:
        evidence["path"] = SELECTED
    return parsed


def _setup(monkeypatch, response):
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-local-output-key")
    monkeypatch.delenv("SKILLSCOUT_GITHUB_TOKEN", raising=False)
    github, _ = _transports()
    semantic = RecordedTransport({CHAT_COMPLETIONS: response})
    monkeypatch.setattr(
        cli,
        "GitHubReadClient",
        lambda: GitHubReadClient(
            token="",
            transport=github.transport(),
            sleeper=lambda _seconds: None,
        ),
    )
    monkeypatch.setattr(
        cli,
        "OpenAIExtractionClient",
        lambda **kwargs: OpenAIExtractionClient(
            http_client=httpx.Client(transport=semantic.transport()),
            **kwargs,
        ),
    )
    return semantic


def test_selected_v2_sends_aligned_prompt_and_binds_telemetry(tmp_path, monkeypatch, capsys):
    semantic = _setup(
        monkeypatch, _chat_response(json.dumps(_response_payload()), model="deepseek-flash")
    )
    assert cli.main(_argv(tmp_path) + ["--deepseek-current-flash"]) == 0
    capsys.readouterr()
    payload = _results(tmp_path)["extractor"]
    request = json.loads(semantic.requests[0].content)
    instructions = request["messages"][0]["content"]
    assert instructions.startswith("extract-local-output-prompt-v1")
    assert payload["prompt_version"] == "extract-local-output-prompt-v1"
    assert payload["local_readme_scope"]["scope_version"] == "local-readme-v2"
    assert payload["repository_summary"] is None
    assert payload["outcome"] == "extracted"
    assert request.get("tools", []) == []
    assert semantic.call_count(*CHAT_COMPLETIONS) == 1


def test_forbidden_output_records_only_field_and_rule_not_rejected_text(
    tmp_path, monkeypatch, capsys
):
    response = _response_payload()
    marker = "synthetic-private-output-5f8c"
    response["repository_summary"] = marker
    response["workflows"][0]["title"] = marker + " https://blocked.invalid"
    response["workflows"][0]["goal"] = "Use sudo to read the input"
    semantic = _setup(monkeypatch, _chat_response(json.dumps(response), model="deepseek-flash"))
    argv = _argv(tmp_path) + ["--deepseek-current-flash"]
    assert cli.main(argv) == 0
    first = json.loads(capsys.readouterr().out)
    result = _results(tmp_path)["extractor"]
    assert result["dropped"] == [
        {
            "workflow_index": 0,
            "reasons": ["forbidden_text"],
            "boundary_diagnostics": {
                "schema_version": "extraction-boundary-diagnostics-v1",
                "findings": [
                    {"rule_id": "url", "field_path": "title"},
                    {"rule_id": "shell_sudo", "field_path": "goal"},
                ],
                "truncated": False,
            },
        }
    ]
    assert result["outcome"] == "schema_failure"
    assert result["repository_summary"] is None
    for path in tmp_path.rglob("*"):
        if path.is_file() and path.name != "subject.json":
            assert marker.encode() not in path.read_bytes()
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["run_id"] == first["run_id"]
    assert semantic.call_count(*CHAT_COMPLETIONS) == 1


@pytest.mark.parametrize("failure", ["schema", "excerpt", "transient", "unknown"])
def test_v2_failure_never_dispatches_correction_or_retry(tmp_path, monkeypatch, capsys, failure):
    payload = _response_payload()
    if failure == "schema":
        response = _chat_response("{}", model="deepseek-flash")
    elif failure == "excerpt":
        payload["workflows"][0]["evidence"][0]["excerpt"] = "not in source"
        response = _chat_response(json.dumps(payload), model="deepseek-flash")
    elif failure == "transient":
        response = RecordedResponse(
            429, {"content-type": "application/json"}, b'{"error":{"message":"limited"}}'
        )
    else:
        response = _chat_response(json.dumps(payload), model="different-model")
    semantic = _setup(monkeypatch, response)
    argv = _argv(tmp_path) + ["--deepseek-current-flash"]
    cli.main(argv)
    capsys.readouterr()
    cli.main(argv)
    capsys.readouterr()
    assert semantic.call_count(*CHAT_COMPLETIONS) == 1
    with sqlite3.connect(tmp_path / "state.db") as database:
        rows = database.execute(
            "SELECT attempt_no,retry_policy_version FROM stage_attempts WHERE stage='extractor'"
        ).fetchall()
    assert rows == [(1, "retry-local-readme-v2-once+extract-correction-policy-v1")]


@pytest.mark.parametrize("outcome", ["no_workflow", "refused", "incomplete"])
def test_v2_nonworkflow_branches_drop_provider_free_text(tmp_path, monkeypatch, capsys, outcome):
    marker = "synthetic-nonworkflow-private-47ca"
    payload = {"repository_summary": marker, "rejection_reason": marker, "workflows": []}
    response = _chat_response(
        json.dumps(payload),
        model="deepseek-flash",
        finish_reason="length" if outcome == "incomplete" else "stop",
    )
    if outcome == "refused":
        body = json.loads(response.body)
        body["choices"][0]["message"]["refusal"] = marker
        response = RecordedResponse(response.status, response.headers, json.dumps(body).encode())
    semantic = _setup(monkeypatch, response)
    assert cli.main(_argv(tmp_path) + ["--deepseek-current-flash"]) == 0
    capsys.readouterr()
    result = _results(tmp_path)["extractor"]
    assert result["outcome"] == outcome
    assert marker not in json.dumps(result)
    assert result["repository_summary"] is result["rejection_reason"] is None
    assert semantic.call_count(*CHAT_COMPLETIONS) == 1


def test_lost_v2_response_is_not_replayed(tmp_path, monkeypatch, capsys):
    semantic = _setup(
        monkeypatch, _chat_response(json.dumps(_response_payload()), model="deepseek-flash")
    )
    original = OpenAIExtractionClient.extract

    def lost(self, **kwargs):
        original(self, **kwargs)
        raise KeyboardInterrupt("test process loss after response")

    monkeypatch.setattr(OpenAIExtractionClient, "extract", lost)
    argv = _argv(tmp_path) + ["--deepseek-current-flash"]
    with pytest.raises(KeyboardInterrupt):
        cli.main(argv)
    capsys.readouterr()
    monkeypatch.setattr(OpenAIExtractionClient, "extract", original)
    assert cli.main(argv) == 1
    capsys.readouterr()
    assert semantic.call_count(*CHAT_COMPLETIONS) == 1


@pytest.mark.parametrize("mutation", ["prompt", "policy", "retry", "attempt"])
def test_v2_candidate_source_rejects_wrong_execution_identity(
    tmp_path, monkeypatch, capsys, mutation
):
    from copy import deepcopy
    from skillscout.adapters.phase2_state import _validate_local_readme_chain
    from skillscout.adapters.state import SQLiteStateStore

    _setup(monkeypatch, _chat_response(json.dumps(_response_payload()), model="deepseek-flash"))
    assert cli.main(_argv(tmp_path) + ["--deepseek-current-flash"]) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    state = SQLiteStateStore(tmp_path / "state.db")
    try:
        chain = state.verify_run_chain(run_id)
    finally:
        state.close()
    assert _validate_local_readme_chain(chain, allow=True)["path"] == SELECTED
    results = list(chain.results)
    changed = deepcopy(results[-1].payload)
    if mutation == "prompt":
        changed["prompt_version"] = "extract-prompt-v1"
        results[-1] = results[-1].model_copy(update={"payload": changed})
    elif mutation == "policy":
        results[-1] = results[-1].model_copy(
            update={"policy_version": "extract-correction-policy-v1"}
        )
    elif mutation == "retry":
        chain = chain.model_copy(
            update={
                "identity": chain.identity.model_copy(update={"retry_policy_version": "retry-v1"})
            }
        )
    else:
        results[-1] = results[-1].model_copy(update={"attempt_no": 2})
    with pytest.raises(ValueError):
        _validate_local_readme_chain(
            chain.model_copy(update={"results": tuple(results)}), allow=True
        )


@pytest.mark.parametrize("legacy_failure", [False, True])
def test_legacy_selected_run_is_not_reused_by_v2_and_remains_readable(
    tmp_path, monkeypatch, capsys, legacy_failure
):
    from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
    from skillscout.adapters.semantic_provider import (
        resolve_local_preview_semantic_provider,
        SemanticProvider,
    )
    from skillscout.adapters.state import SQLiteStateStore
    from skillscout.application.pipeline import PipelineRunner
    from skillscout.application.processors import PhaseTwoProcessor
    from skillscout.application.candidate_source import derive_candidate_subject_descriptors
    from skillscout.domain.local_preview import LocalReadmeSubject
    from test_local_readme_preview import PINNED

    semantic = _setup(
        monkeypatch, _chat_response(json.dumps(_response_payload()), model="deepseek-flash")
    )
    subject = LocalReadmeSubject(
        schema_version="1",
        subject_id="repo:example/approved-repo",
        repository="https://github.com/example/approved-repo",
        ref=PINNED,
        readme_path=SELECTED,
    )
    provider = resolve_local_preview_semantic_provider(current_flash=True)
    client = cli.OpenAIExtractionClient(model=provider.extract_model, provider_settings=provider)
    github = cli.GitHubReadClient()
    state = SQLiteStateStore(tmp_path / "state.db")
    if legacy_failure:
        from skillscout.application.ports import SafeFailure, ErrorCode

        def fail(**kwargs):
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)

        client.extract = fail
    try:
        runner = PipelineRunner(
            state, PhaseTwoProcessor(github, client, semantic_provider=SemanticProvider.DEEPSEEK)
        )
        if legacy_failure:
            with pytest.raises(SafeFailure):
                runner.run(subject, tmp_path / "legacy-output")
            old_id = state.connection.execute("SELECT run_id FROM runs").fetchone()[0]
        else:
            old_id = runner.run(subject, tmp_path / "legacy-output").run_id
        before = state.verify_run_chain(old_id).model_dump(mode="json")
    finally:
        state.close()
        client.close()
        github.close()
    argv = _argv(tmp_path) + ["--deepseek-current-flash"]
    assert cli.main(argv) == 0
    current_id = json.loads(capsys.readouterr().out)["run_id"]
    assert current_id != old_id
    state = SQLiteStateStore(tmp_path / "state.db")
    try:
        assert state.verify_run_chain(old_id).model_dump(mode="json") == before
        assert (
            state.verify_run_chain(current_id).results[-1].prompt_version
            == "extract-local-output-prompt-v1"
        )
    finally:
        state.close()
    if not legacy_failure:
        old_descriptors = derive_candidate_subject_descriptors(
            SQLitePhaseTwoCandidateSource(tmp_path / "state.db", allow_local_readme=True),
            phase2_run_id=old_id,
        )
        assert len(old_descriptors) == 1
    assert cli.main(argv) == 0
    capsys.readouterr()
    assert semantic.call_count(*CHAT_COMPLETIONS) == (1 if legacy_failure else 2)


@pytest.mark.parametrize("local_preview,correction", [("true", None), (1, None), (True, "excerpt")])
def test_local_adapter_rejects_nonboolean_or_correction_before_request(
    monkeypatch, local_preview, correction
):
    from skillscout.adapters.semantic_provider import resolve_local_preview_semantic_provider
    from skillscout.domain.extraction_correction import ExtractionCorrectionReason
    from skillscout.application.ports import SafeFailure

    semantic = _setup(monkeypatch, _chat_response("{}", model="deepseek-flash"))
    provider = resolve_local_preview_semantic_provider(current_flash=True)
    with cli.OpenAIExtractionClient(
        model=provider.extract_model, provider_settings=provider
    ) as client:
        with pytest.raises(SafeFailure):
            client.extract(
                user_payload="inert",
                local_preview=local_preview,
                correction=ExtractionCorrectionReason.EXCERPT if correction else None,
            )
    assert semantic.requests == []
