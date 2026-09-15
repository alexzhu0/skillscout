"""Explicit local v4 source-field extraction boundaries."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy

import httpx
import pytest

from recorded_transport import RecordedResponse, RecordedTransport, recorded_openai_fixture
from test_local_evidence_preview import (
    _selection_payload,
    _source_setup,
)
from test_local_extraction_output import _setup
from test_cli_extract_repo import RESPONSES
from test_local_readme_preview import SELECTED, _argv, _results
from test_semantic_provider import CHAT_COMPLETIONS, _chat_response

from skillscout import cli
from skillscout.adapters.openai_extract import (
    MAX_EVIDENCE_SELECTION_INPUT_BYTES,
    EvidenceSelectionInputTooLarge,
    OpenAIExtractionClient,
)
from skillscout.adapters.phase2_state import (
    SQLitePhaseTwoCandidateSource,
    _validate_local_readme_chain,
)
from skillscout.adapters.semantic_provider import (
    resolve_local_preview_semantic_provider,
    resolve_semantic_provider,
)
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.candidate_source import derive_candidate_subject_descriptors
from skillscout.application.ports import ErrorCode, SafeFailure

SOURCE_ONLY_FLAGS = [
    "--deepseek-current-flash",
    "--evidence-selection",
    "--source-only-fields",
]
SOURCE_ONLY_PROMPT = "extract-local-evidence-source-only-fields-v1"
SOURCE_ONLY_RETRY = "retry-local-readme-v4-once+extract-correction-policy-v1"
SOURCE_ONLY_SUFFIX = """

Source-only workflow semantics:
Describe every workflow field solely from semantics explicitly supported by the
supplied source evidence. Never copy or translate trusted operator, experiment,
security, validation or execution policy into source obligations or deliverables.
When the source does not state a required approval, prohibited action or non-goal,
return an empty list for that field. Preserve genuine source approvals and
prohibitions, including their exact conditions and scope.
Outputs must contain only deliverables called for by the source. Do not add audit
logs, iteration reports, review summaries or other process artifacts unless
explicitly called for by the source.
Assumptions may express explicit source uncertainty or unresolved conditions, but
must not grant authority, permission, access, execution or policy exceptions.
These field-attribution rules do not relax the trusted safety or execution
restrictions above.
"""


def _chain(path, run_id):
    state = SQLiteStateStore(path)
    try:
        return state.verify_run_chain(run_id)
    finally:
        state.close()


def test_v4_adapter_request_changes_only_prompt_identity_and_source_field_suffix():
    response = _chat_response(json.dumps(_selection_payload()), model="deepseek-flash")
    v3_transport = RecordedTransport({CHAT_COMPLETIONS: response})
    v4_transport = RecordedTransport({CHAT_COMPLETIONS: response})
    settings = resolve_local_preview_semantic_provider(
        {
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        },
        current_flash=True,
    )

    with OpenAIExtractionClient(
        api_key="test-only-source-fields",
        provider_settings=settings,
        http_client=httpx.Client(transport=v3_transport.transport()),
    ) as client:
        client.extract(user_payload='{"catalogue":"inert"}', evidence_selection=True)
    with OpenAIExtractionClient(
        api_key="test-only-source-fields",
        provider_settings=settings,
        http_client=httpx.Client(transport=v4_transport.transport()),
    ) as client:
        client.extract(
            user_payload='{"catalogue":"inert"}',
            evidence_selection=True,
            source_only_fields=True,
        )

    actual = json.loads(v4_transport.requests[0].content)
    expected = json.loads(v3_transport.requests[0].content)
    trusted = expected["messages"][0]["content"].replace(
        "extract-local-evidence-select-v1", SOURCE_ONLY_PROMPT, 1
    )
    expected["messages"][0]["content"] = trusted.replace(
        "\n\nReturn one JSON object only.",
        SOURCE_ONLY_SUFFIX + "\n\nReturn one JSON object only.",
        1,
    )
    assert actual == expected


@pytest.mark.parametrize("provider", ["openai", "deepseek"])
def test_v4_full_rendered_request_input_byte_boundary(provider):
    settings = resolve_semantic_provider(
        {
            "SKILLSCOUT_LLM_PROVIDER": provider,
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        }
    )
    response = _chat_response(json.dumps(_selection_payload()), model=settings.extract_model)
    route = CHAT_COMPLETIONS
    if provider == "openai":
        body = json.loads(recorded_openai_fixture("parsed_2_workflows").body)
        body["output"][0]["content"][0]["text"] = json.dumps(_selection_payload())
        response = RecordedResponse(
            200,
            {"content-type": "application/json"},
            json.dumps(body).encode(),
        )
        route = RESPONSES
    transport = RecordedTransport({route: response})
    with OpenAIExtractionClient(
        api_key="test-only-source-fields",
        provider_settings=settings,
        http_client=httpx.Client(transport=transport.transport()),
    ) as client:
        assert (
            client.extract(
                user_payload="x",
                evidence_selection=True,
                source_only_fields=True,
            ).status
            == "parsed"
        )
        request = json.loads(transport.requests[0].content)
        if provider == "deepseek":
            overhead = len(request["messages"][0]["content"].encode())
        else:
            overhead = len(request["input"][0]["content"].encode()) + len(
                json.dumps(
                    request["text"]["format"],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
        exact = "x" * (MAX_EVIDENCE_SELECTION_INPUT_BYTES - overhead)
        assert (
            client.extract(
                user_payload=exact,
                evidence_selection=True,
                source_only_fields=True,
            ).status
            == "parsed"
        )
        with pytest.raises(EvidenceSelectionInputTooLarge):
            client.extract(
                user_payload=exact + "x",
                evidence_selection=True,
                source_only_fields=True,
            )
    assert transport.call_count(*route) == 2


@pytest.mark.parametrize(
    "extra",
    [
        ["--readme-path", SELECTED, "--source-only-fields"],
        ["--evidence-selection", "--source-only-fields"],
    ],
    ids=["missing-evidence-selection", "missing-readme"],
)
def test_v4_cli_rejects_incomplete_opt_in_before_state_or_clients(
    tmp_path, monkeypatch, capsys, extra
):
    constructed = []
    monkeypatch.setattr(cli, "GitHubReadClient", lambda: constructed.append("github"))
    monkeypatch.setattr(cli, "OpenAIExtractionClient", lambda **_kwargs: constructed.append("llm"))

    assert cli.main(_argv(tmp_path, selected=None) + extra) == 1
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "invalid_subject"
    assert not (tmp_path / "state.db").exists()
    assert constructed == []


@pytest.mark.parametrize("value", [1, "true", None])
def test_v4_adapter_rejects_non_boolean_or_unscoped_flag_before_request(value):
    transport = RecordedTransport({})
    with OpenAIExtractionClient(
        api_key="test-only-source-fields",
        http_client=httpx.Client(transport=transport.transport()),
    ) as client:
        with pytest.raises(SafeFailure):
            client.extract(
                user_payload="{}",
                evidence_selection=value is None,
                source_only_fields=value,
            )
    assert transport.requests == []


def test_v4_cli_persists_exact_scope_prompt_and_one_shot_retry(tmp_path, monkeypatch, capsys):
    semantic = _setup(
        monkeypatch,
        _chat_response(json.dumps(_selection_payload()), model="deepseek-flash"),
    )
    assert cli.main(_argv(tmp_path) + SOURCE_ONLY_FLAGS) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    output = _results(tmp_path)["extractor"]
    assert output["local_readme_scope"]["scope_version"] == "local-readme-v4"
    assert output["prompt_version"] == SOURCE_ONLY_PROMPT
    assert output["outcome"] == "extracted"
    assert semantic.call_count(*CHAT_COMPLETIONS) == 1
    with sqlite3.connect(tmp_path / "state.db") as database:
        assert database.execute(
            "SELECT attempt_no,retry_policy_version FROM stage_attempts WHERE stage='extractor'"
        ).fetchall() == [(1, SOURCE_ONLY_RETRY)]
    assert (
        _validate_local_readme_chain(_chain(tmp_path / "state.db", run_id), allow=True)["path"]
        == SELECTED
    )


def test_v4_empty_catalogue_records_v4_identity_without_provider_request(
    tmp_path, monkeypatch, capsys
):
    semantic = _source_setup(monkeypatch, "https://ignored.invalid\n")
    assert cli.main(_argv(tmp_path) + SOURCE_ONLY_FLAGS) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]

    output = _results(tmp_path)["extractor"]
    assert output["prompt_version"] == SOURCE_ONLY_PROMPT
    assert output["local_readme_scope"]["scope_version"] == "local-readme-v4"
    assert output["skip_reason"] == "no_eligible_evidence"
    assert output["evidence_catalog"]["entry_count"] == 0
    assert semantic.requests == []
    assert (
        _validate_local_readme_chain(_chain(tmp_path / "state.db", run_id), allow=True)["path"]
        == SELECTED
    )


def test_v3_and_v4_use_distinct_runs_without_invalidating_old_state(tmp_path, monkeypatch, capsys):
    semantic = _setup(
        monkeypatch,
        _chat_response(json.dumps(_selection_payload()), model="deepseek-flash"),
    )
    base = _argv(tmp_path) + ["--deepseek-current-flash", "--evidence-selection"]
    assert cli.main(base) == 0
    v3_run = json.loads(capsys.readouterr().out)["run_id"]
    assert cli.main(base + ["--source-only-fields"]) == 0
    v4_run = json.loads(capsys.readouterr().out)["run_id"]

    assert v4_run != v3_run
    assert semantic.call_count(*CHAT_COMPLETIONS) == 2
    source = SQLitePhaseTwoCandidateSource(tmp_path / "state.db", allow_local_readme=True)
    assert len(derive_candidate_subject_descriptors(source, phase2_run_id=v3_run)) == 1
    assert len(derive_candidate_subject_descriptors(source, phase2_run_id=v4_run)) == 1


@pytest.mark.parametrize("mutation", ["prompt", "retry", "attempt"])
def test_v4_bridge_rejects_mismatched_execution_identity(tmp_path, monkeypatch, capsys, mutation):
    _setup(monkeypatch, _chat_response(json.dumps(_selection_payload()), model="deepseek-flash"))
    assert cli.main(_argv(tmp_path) + SOURCE_ONLY_FLAGS) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    chain = _chain(tmp_path / "state.db", run_id)
    results = list(chain.results)
    if mutation == "prompt":
        payload = deepcopy(results[-1].payload)
        payload["prompt_version"] = "extract-local-evidence-select-v1"
        results[-1] = results[-1].model_copy(update={"payload": payload})
    elif mutation == "retry":
        chain = chain.model_copy(
            update={
                "identity": chain.identity.model_copy(
                    update={"retry_policy_version": "retry-local-readme-v3-once"}
                )
            }
        )
    else:
        results[-1] = results[-1].model_copy(update={"attempt_no": 2})
    with pytest.raises(ValueError):
        _validate_local_readme_chain(
            chain.model_copy(update={"results": tuple(results)}), allow=True
        )


def test_v4_unknown_provider_outcome_is_consumed_once_without_retry(tmp_path, monkeypatch, capsys):
    semantic = _setup(
        monkeypatch,
        _chat_response(json.dumps(_selection_payload()), model="different-model"),
    )
    argv = _argv(tmp_path) + SOURCE_ONLY_FLAGS
    assert cli.main(argv) == 1
    capsys.readouterr()
    assert cli.main(argv) == 1
    capsys.readouterr()

    assert semantic.call_count(*CHAT_COMPLETIONS) == 1
    with sqlite3.connect(tmp_path / "state.db") as database:
        assert database.execute(
            "SELECT attempt_no,retry_policy_version,retryable FROM stage_attempts "
            "WHERE stage='extractor'"
        ).fetchall() == [(1, SOURCE_ONLY_RETRY, 0)]


def test_v4_export_readmits_locally_while_publication_projection_denies_it(
    tmp_path, monkeypatch, capsys
):
    from skillscout.bootstrap import _publication_projection

    _setup(monkeypatch, _chat_response(json.dumps(_selection_payload()), model="deepseek-flash"))
    assert cli.main(_argv(tmp_path) + SOURCE_ONLY_FLAGS) == 0
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
    exported = json.loads(capsys.readouterr().out)
    assert exported["status"] == "exported"
    assert exported["candidate_count"] == 1
    descriptor = tmp_path / "export" / exported["candidates"][0]["descriptor_path"]

    with pytest.raises(SafeFailure) as failure:
        _publication_projection(
            candidate=descriptor,
            phase2_state=tmp_path / "state.db",
            phase3_state=tmp_path / "unused-phase3.db",
            environ={},
        )
    assert failure.value.code is ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE
