"""Extractor boundary: injection corpus, compromised-model drops and canary sweeps."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from recorded_transport import (
    RecordedResponse,
    RecordedTransport,
    make_blob_entry,
    make_blob_fixture,
    make_tree_fixture,
    recorded_fixture,
    recorded_openai_fixture,
)

from skillscout.adapters.github import GitHubReadClient
from skillscout.adapters.openai_extract import (
    DEFAULT_EXTRACT_MODEL,
    EXTRACT_INSTRUCTIONS_V1,
    OpenAIExtractionClient,
)
from skillscout.adapters.state import SQLiteStateStore
from skillscout.adapters.subjects import load_subject
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import StageContext
from skillscout.application.processors import PhaseTwoProcessor
from skillscout.domain.enums import (
    AttemptStatus,
    ExecutionMode,
    PipelineStage,
    RunStatus,
)
from skillscout.domain.extraction import (
    EXTRACT_PROMPT_VERSION,
    FINGERPRINT_VERSION,
    MAX_EVIDENCE_EXCERPT_CHARS,
    WORKFLOW_SPEC_SCHEMA_VERSION,
)
from skillscout.domain.models import StageInput, TokenUsage

APPROVED_SUBJECT = Path(__file__).parent / "fixtures" / "subject" / "approved.json"
INJECTION_DIR = Path(__file__).parent / "fixtures" / "injection"
SUBJECT = load_subject(APPROVED_SUBJECT)

PINNED = "0123456789abcdef0123456789abcdef01234567"
README_SHA = "aa01aa01aa01aa01aa01aa01aa01aa01aa01aa01"
GUIDE_SHA = "bb02bb02bb02bb02bb02bb02bb02bb02bb02bb02"
LICENSE_SHA = "bb12bb12bb12bb12bb12bb12bb12bb12bb12bb12"
ACTUAL_MODEL = "gpt-5.6-terra-2026-07-22"
OPENAI_KEY = "sk-CANARY-DO-NOT-DISCLOSE-0123456789"
GITHUB_TOKEN = "github_pat_CANARY_DO_NOT_DISCLOSE_0123456789"
FULL_TEXT_CANARY = "CANARY_FULL_TEXT_SENTENCE_DO_NOT_PERSIST_9f3b"
EVIDENCE_CANARY = "CANARY_EVIDENCE_SENTENCE_VERBATIM_7a21"

META = ("GET", "/repos/example/approved-repo")
PIN = ("GET", "/repos/example/approved-repo/commits/main")
TREE = ("GET", f"/repos/example/approved-repo/git/trees/{PINNED}?recursive=1")
LICENSE = ("GET", f"/repos/example/approved-repo/license?ref={PINNED}")
RESPONSES = ("POST", "/v1/responses")

README_SIZE = json.loads(recorded_fixture("blob_readme").body)["size"]

PAYLOAD_KEYS = {
    "schema_version",
    "stage",
    "subject_id",
    "outcome",
    "prompt_version",
    "model_configured",
    "model_actual",
    "repository_summary",
    "rejection_reason",
    "workflows",
    "dropped",
}
WORKFLOW_KEYS = {
    "schema_version",
    "workflow_id",
    "fingerprint",
    "fingerprint_version",
    "title",
    "goal",
    "applicability",
    "non_goals",
    "preconditions",
    "inputs",
    "steps",
    "outputs",
    "failure_modes",
    "prohibited_actions",
    "required_approvals",
    "assumptions",
    "evidence",
    "confidence",
}


@pytest.fixture(autouse=True)
def _clear_credential_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLSCOUT_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _blob(sha: str) -> tuple[str, str]:
    return ("GET", f"/repos/example/approved-repo/git/blobs/{sha}")


def _small_tree_entries(*, extra: list[dict[str, object]] | None = None) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = [
        {"path": "LICENSE", "mode": "100644", "type": "blob", "size": 1100, "sha": LICENSE_SHA},
        {
            "path": "README.md",
            "mode": "100644",
            "type": "blob",
            "size": README_SIZE,
            "sha": README_SHA,
        },
        {"path": "docs/guide.md", "mode": "100644", "type": "blob", "size": 800, "sha": GUIDE_SHA},
    ]
    if extra:
        entries.extend(extra)
    return entries


def _github_routes(
    *,
    tree: RecordedResponse | None = None,
    repo: str = "repo_mit",
    extra_blobs: dict[tuple[str, str], RecordedResponse] | None = None,
) -> dict[tuple[str, str], RecordedResponse]:
    routes = {
        META: recorded_fixture(repo),
        PIN: recorded_fixture("commits_pin"),
        TREE: tree if tree is not None else make_tree_fixture(_small_tree_entries()),
        LICENSE: recorded_fixture("license_mit"),
        _blob(README_SHA): recorded_fixture("blob_readme"),
        _blob(GUIDE_SHA): recorded_fixture("blob_doc"),
    }
    if extra_blobs:
        routes.update(extra_blobs)
    return routes


def _openai_response(
    workflows: list[dict[str, object]],
    *,
    summary: str = "Recorded repository summary.",
    rejection_reason: str | None = None,
    resp_id: str = "resp_synth_0001",
) -> RecordedResponse:
    payload = {
        "repository_summary": summary,
        "rejection_reason": rejection_reason,
        "workflows": workflows,
    }
    body = {
        "id": resp_id,
        "object": "response",
        "created_at": 1783000000,
        "status": "completed",
        "model": ACTUAL_MODEL,
        "output": [
            {
                "id": "msg_synth",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": json.dumps(payload), "annotations": []}
                ],
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    }
    return RecordedResponse(
        status=200, headers={"content-type": "application/json"}, body=json.dumps(body).encode()
    )


def _template_workflow(index: int = 0) -> dict[str, object]:
    body = json.loads(recorded_openai_fixture("parsed_2_workflows").body)
    embedded = json.loads(body["output"][0]["content"][0]["text"])
    return json.loads(json.dumps(embedded["workflows"][index]))


def _clients(
    github_routes: dict[tuple[str, str], RecordedResponse],
    openai_response: RecordedResponse,
    *,
    github_token: str | None = None,
    openai_key: str | None = OPENAI_KEY,
) -> tuple[PhaseTwoProcessor, RecordedTransport, RecordedTransport]:
    github_rec = RecordedTransport(github_routes)
    openai_rec = RecordedTransport({RESPONSES: openai_response})
    github = GitHubReadClient(
        token=github_token,
        transport=github_rec.transport(),
        sleeper=lambda _seconds: None,
    )
    openai_client = OpenAIExtractionClient(
        api_key=openai_key,
        http_client=httpx.Client(transport=openai_rec.transport()),
    )
    return PhaseTwoProcessor(github, openai_client), github_rec, openai_rec


def _stage_input(stage: PipelineStage) -> StageInput:
    return StageInput(
        schema_version="2",
        execution_mode=ExecutionMode.DRY_RUN,
        subject_id=SUBJECT.subject_id,
        stage=stage,
        previous_output_hash=None,
        fixture_hash="sha256:" + "0" * 64,
    )


def _direct(
    github_routes: dict[tuple[str, str], RecordedResponse],
    openai_response: RecordedResponse,
) -> tuple[dict[str, object], StageContext, RecordedTransport, RecordedTransport]:
    processor, github_rec, openai_rec = _clients(github_routes, openai_response)
    context = StageContext(subject=SUBJECT, prior_payloads={}, scratch={})
    outcomes: dict[str, object] = {}
    for stage in (
        PipelineStage.SCOUT,
        PipelineStage.FILTER,
        PipelineStage.READER,
        PipelineStage.EXTRACTOR,
    ):
        outcome = processor.process(_stage_input(stage), context)
        outcomes[stage.value] = outcome
        context.prior_payloads[stage.value] = outcome.payload
    return outcomes, context, github_rec, openai_rec


def _run(
    tmp_path: Path,
    github_routes: dict[tuple[str, str], RecordedResponse],
    openai_response: RecordedResponse,
    *,
    github_token: str | None = None,
    openai_key: str | None = OPENAI_KEY,
) -> tuple[object, list[str], list[object], RecordedTransport, RecordedTransport]:
    processor, github_rec, openai_rec = _clients(
        github_routes,
        openai_response,
        github_token=github_token,
        openai_key=openai_key,
    )
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        summary = PipelineRunner(store, processor).run(
            load_subject(APPROVED_SUBJECT), tmp_path / "output"
        )
        chain = store.verify_run_chain(summary.run_id)
        outcomes = [str(envelope.payload["outcome"]) for envelope in chain.results]
        attempts = store.connection.execute(
            """SELECT stage, attempt_no, status, retryable, prompt_version,
                      policy_version, model_id
               FROM stage_attempts
               ORDER BY stage_index"""
        ).fetchall()
    finally:
        store.close()
    return summary, outcomes, attempts, github_rec, openai_rec


def _durable_bytes(root: Path) -> bytes:
    return b"".join(path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file())


def _request_body(rec: RecordedTransport) -> dict[str, object]:
    assert len(rec.requests) == 1
    return json.loads(rec.requests[0].content.decode())


def test_extracted_two_workflows_payload_is_contract_valid() -> None:
    outcomes, context, _github_rec, openai_rec = _direct(
        _github_routes(), recorded_openai_fixture("parsed_2_workflows")
    )
    outcome = outcomes["extractor"]
    payload = outcome.payload

    assert set(payload) == PAYLOAD_KEYS
    assert payload["schema_version"] == "2"
    assert payload["stage"] == "extractor"
    assert payload["subject_id"] == SUBJECT.subject_id
    assert payload["outcome"] == "extracted"
    assert payload["prompt_version"] == EXTRACT_PROMPT_VERSION
    assert payload["model_configured"] == DEFAULT_EXTRACT_MODEL
    assert payload["model_actual"] == ACTUAL_MODEL
    assert payload["repository_summary"].startswith("Approved Repo demonstrates")
    assert payload["rejection_reason"] is None
    assert payload["dropped"] == []

    recorded_hashes = {
        entry["path"]: entry["content_hash"] for entry in outcomes["reader"].payload["files"]
    }
    workflows = payload["workflows"]
    assert [workflow["title"] for workflow in workflows] == [
        "Guided repository review",
        "README quick-start routine",
    ]
    for workflow in workflows:
        assert set(workflow) == WORKFLOW_KEYS
        assert workflow["schema_version"] == WORKFLOW_SPEC_SCHEMA_VERSION
        assert workflow["fingerprint_version"] == FINGERPRINT_VERSION
        assert workflow["fingerprint"].startswith("sha256:")
        assert workflow["workflow_id"] == "wf-" + workflow["fingerprint"][7:23]
        refs = list(workflow["evidence"]) + [
            ref for step in workflow["steps"] for ref in step["evidence"]
        ]
        assert workflow["evidence"], "workflow-level evidence is required"
        for step in workflow["steps"]:
            assert step["evidence"], "per-step evidence is required"
        for ref in refs:
            assert set(ref) == {"path", "blob_sha", "content_hash", "excerpt", "supports"}
            assert ref["content_hash"] == recorded_hashes[ref["path"]]
            assert len(ref["excerpt"]) <= MAX_EVIDENCE_EXCERPT_CHARS

    telemetry = outcome.telemetry
    assert telemetry is not None
    assert telemetry.prompt_version == EXTRACT_PROMPT_VERSION
    assert telemetry.policy_version == "extract-policy-v1"
    assert telemetry.model_id == ACTUAL_MODEL
    assert telemetry.request_id == "resp_ext_0001"
    assert telemetry.token_usage == TokenUsage(
        prompt_tokens=812, completion_tokens=246, total_tokens=1058
    )
    assert telemetry.latency_ms is not None and telemetry.latency_ms >= 0

    assert openai_rec.call_count(*RESPONSES) == 1
    body = _request_body(openai_rec)
    assert body["store"] is False
    assert "tools" not in body
    developer, user = body["input"]
    assert developer == {"role": "developer", "content": EXTRACT_INSTRUCTIONS_V1}
    assert user["role"] == "user"
    content = user["content"]
    assert content.startswith("UNTRUSTED repository snapshot follows")
    assert content.index('<<<UNTRUSTED REPOSITORY FILE path="README.md"') < content.index(
        '<<<UNTRUSTED REPOSITORY FILE path="docs/guide.md"'
    )
    assert f'blob_sha="{README_SHA}"' in content
    assert f'blob_sha="{GUIDE_SHA}"' in content
    assert content.count("<<<END UNTRUSTED FILE>>>") == 2
    assert context.scratch["read_bundle"]["README.md"].startswith("# Approved Repo")


def test_zero_workflows_yields_the_no_workflow_outcome() -> None:
    outcomes, _context, _github_rec, openai_rec = _direct(
        _github_routes(), recorded_openai_fixture("parsed_zero_workflows")
    )
    payload = outcomes["extractor"].payload

    assert set(payload) == PAYLOAD_KEYS
    assert payload["outcome"] == "no_workflow"
    assert payload["workflows"] == []
    assert payload["dropped"] == []
    assert payload["rejection_reason"] == (
        "No reusable agent workflow could be identified in the read files."
    )
    assert payload["repository_summary"].startswith("The repository holds")
    assert openai_rec.call_count(*RESPONSES) == 1


@pytest.mark.parametrize("count", [1, 3])
def test_one_and_three_workflow_responses_produce_contract_valid_payloads(
    count: int,
) -> None:
    workflows = [_template_workflow(0), _template_workflow(1)]
    if count == 3:
        third = _template_workflow(0)
        third["title"] = "Guide audit routine"
        third["goal"] = (
            "Audit a repository guide against its ordered checklist "
            "while recording each outcome in the run log."
        )
        workflows.append(third)
    outcomes, _context, _github_rec, openai_rec = _direct(
        _github_routes(), _openai_response(workflows[:count])
    )
    payload = outcomes["extractor"].payload

    assert set(payload) == PAYLOAD_KEYS
    assert payload["outcome"] == "extracted"
    assert len(payload["workflows"]) == count
    for workflow in payload["workflows"]:
        assert set(workflow) == WORKFLOW_KEYS
    assert openai_rec.call_count(*RESPONSES) == 1


def test_four_workflow_response_is_a_schema_failure() -> None:
    workflows = [_template_workflow(0), _template_workflow(1)]
    for index in range(2):
        extra = _template_workflow(0)
        extra["title"] = f"Extra routine {index}"
        extra["goal"] = f"Run an extra recorded routine number {index} end to end."
        workflows.append(extra)
    outcomes, _context, _github_rec, openai_rec = _direct(
        _github_routes(), _openai_response(workflows)
    )
    payload = outcomes["extractor"].payload

    assert set(payload) == PAYLOAD_KEYS | {"diagnostics"}
    assert payload["outcome"] == "schema_failure"
    assert payload["workflows"] == []
    assert payload["dropped"] == []
    assert payload["diagnostics"] == ["structured_output_validation_failed"]
    assert openai_rec.call_count(*RESPONSES) == 1


def test_refusal_maps_to_a_succeeded_refused_outcome() -> None:
    outcomes, _context, _github_rec, openai_rec = _direct(
        _github_routes(), recorded_openai_fixture("refusal")
    )
    payload = outcomes["extractor"].payload

    assert set(payload) == PAYLOAD_KEYS
    assert payload["outcome"] == "refused"
    assert payload["rejection_reason"] == "I cannot extract workflows from this content."
    assert payload["repository_summary"] is None
    assert payload["workflows"] == []
    telemetry = outcomes["extractor"].telemetry
    assert telemetry is not None
    assert telemetry.request_id == "resp_ext_0003"
    assert openai_rec.call_count(*RESPONSES) == 1


def test_incomplete_maps_to_a_succeeded_incomplete_outcome() -> None:
    outcomes, _context, _github_rec, openai_rec = _direct(
        _github_routes(), recorded_openai_fixture("incomplete_max_tokens")
    )
    payload = outcomes["extractor"].payload

    assert set(payload) == PAYLOAD_KEYS | {"incomplete_reason"}
    assert payload["outcome"] == "incomplete"
    assert payload["incomplete_reason"] == "max_output_tokens"
    assert payload["repository_summary"] is None
    assert payload["workflows"] == []
    assert openai_rec.call_count(*RESPONSES) == 1


def test_schema_invalid_maps_to_schema_failure_with_sanitized_diagnostics() -> None:
    outcomes, _context, _github_rec, openai_rec = _direct(
        _github_routes(), recorded_openai_fixture("schema_invalid")
    )
    payload = outcomes["extractor"].payload

    assert set(payload) == PAYLOAD_KEYS | {"diagnostics"}
    assert payload["outcome"] == "schema_failure"
    assert payload["diagnostics"] == ["structured_output_validation_failed"]
    assert payload["repository_summary"] is None
    assert payload["workflows"] == []
    assert payload["dropped"] == []
    assert openai_rec.call_count(*RESPONSES) == 1


def _fingerprint_of_extracted(workflows: list[dict[str, object]]) -> str:
    outcomes, _context, _github_rec, _openai_rec = _direct(
        _github_routes(), _openai_response(workflows)
    )
    payload = outcomes["extractor"].payload
    assert payload["outcome"] == "extracted"
    return str(payload["workflows"][0]["fingerprint"])


def test_fingerprint_is_stable_under_rewording_only_variants() -> None:
    baseline = _template_workflow(0)
    reworded = _template_workflow(0)
    reworded["goal"] = (
        "REVIEW a  repository, with an ordered checklist, "
        "while recording each outcome in the run log!!"
    )
    reworded["steps"] = [
        {**step, "instruction": step["instruction"].upper() + "!"}
        for step in reworded["steps"]
    ]

    assert _fingerprint_of_extracted([baseline]) == _fingerprint_of_extracted([reworded])


def test_fingerprint_is_sensitive_to_semantic_change() -> None:
    baseline = _template_workflow(0)
    changed = _template_workflow(0)
    changed["goal"] = (
        "Document a repository with an ordered checklist "
        "while recording each outcome in the run log."
    )

    assert _fingerprint_of_extracted([baseline]) != _fingerprint_of_extracted([changed])


def test_fingerprint_is_sensitive_to_step_order() -> None:
    baseline = _template_workflow(0)
    reordered = _template_workflow(0)
    reordered["steps"] = list(reversed(reordered["steps"]))

    assert _fingerprint_of_extracted([baseline]) != _fingerprint_of_extracted([reordered])


def test_compromised_url_in_steps_workflow_is_dropped_without_retry(tmp_path: Path) -> None:
    summary, outcomes, attempts, _github_rec, openai_rec = _run(
        tmp_path, _github_routes(), recorded_openai_fixture("compromised_url_in_steps")
    )

    assert summary.status is RunStatus.COMPLETED
    assert outcomes == ["accepted", "accepted", "accepted", "schema_failure"]
    assert openai_rec.call_count(*RESPONSES) == 1
    assert [(row["stage"], row["attempt_no"], row["status"], row["retryable"]) for row in attempts] == [
        ("scout", 1, AttemptStatus.SUCCEEDED.value, 0),
        ("filter", 1, AttemptStatus.SUCCEEDED.value, 0),
        ("reader", 1, AttemptStatus.SUCCEEDED.value, 0),
        ("extractor", 1, AttemptStatus.SUCCEEDED.value, 0),
    ]
    manifest_root = (tmp_path / "state.db").with_suffix(".manifests")
    extractor_manifest = json.loads(
        next(iter((manifest_root / "extractor").glob("*.json"))).read_bytes()
    )
    payload = extractor_manifest["payload"]
    assert payload["diagnostics"] == ["all_workflows_dropped"]
    assert payload["dropped"] == [
        {"title": "Compromised installer workflow", "reasons": ["forbidden_text"]}
    ]
    assert payload["workflows"] == []
    assert b"evil.example" not in _durable_bytes(tmp_path)


def test_compromised_fake_evidence_workflow_is_dropped_with_reasons(tmp_path: Path) -> None:
    summary, outcomes, attempts, _github_rec, openai_rec = _run(
        tmp_path, _github_routes(), recorded_openai_fixture("compromised_fake_evidence")
    )

    assert summary.status is RunStatus.COMPLETED
    assert outcomes == ["accepted", "accepted", "accepted", "schema_failure"]
    assert openai_rec.call_count(*RESPONSES) == 1
    assert all(row["attempt_no"] == 1 for row in attempts)
    manifest_root = (tmp_path / "state.db").with_suffix(".manifests")
    extractor_manifest = json.loads(
        next(iter((manifest_root / "extractor").glob("*.json"))).read_bytes()
    )
    payload = extractor_manifest["payload"]
    assert payload["diagnostics"] == ["all_workflows_dropped"]
    assert payload["dropped"] == [
        {
            "title": "Fabricated evidence workflow",
            "reasons": [
                "excerpt_not_verbatim",
                "unknown_evidence_path",
                "blob_sha_mismatch",
            ],
        }
    ]
    assert payload["workflows"] == []


@pytest.mark.parametrize(
    "injection_path",
    sorted(INJECTION_DIR.glob("*.md")),
    ids=lambda path: path.stem,
)
def test_injection_corpus_never_gains_instruction_authority(
    injection_path: Path, tmp_path: Path
) -> None:
    content = injection_path.read_bytes()
    entry = make_blob_entry("docs/injected.md", content)
    github_routes = _github_routes(
        tree=make_tree_fixture(_small_tree_entries(extra=[entry])),
        extra_blobs={
            _blob(str(entry["sha"])): make_blob_fixture(content, sha=str(entry["sha"]))
        },
    )
    summary, outcomes, attempts, _github_rec, openai_rec = _run(
        tmp_path, github_routes, recorded_openai_fixture("parsed_zero_workflows")
    )

    assert summary.status is RunStatus.COMPLETED
    assert outcomes == ["accepted", "accepted", "accepted", "no_workflow"]
    assert openai_rec.call_count(*RESPONSES) == 1
    assert all(row["attempt_no"] == 1 for row in attempts)

    body = _request_body(openai_rec)
    assert body["store"] is False
    assert "tools" not in body
    developer, user = body["input"]
    assert developer == {"role": "developer", "content": EXTRACT_INSTRUCTIONS_V1}
    assert FULL_TEXT_CANARY not in developer["content"]
    injected_first_line = content.decode().splitlines()[0]
    assert injected_first_line in user["content"]
    assert '<<<UNTRUSTED REPOSITORY FILE path="docs/injected.md"' in user["content"]
    assert "<<<END UNTRUSTED FILE>>>" in user["content"]

    durable = _durable_bytes(tmp_path)
    assert FULL_TEXT_CANARY.encode() not in durable
    assert b"docs/injected.md" in durable  # bounded path metadata persists, text never does


def test_filter_rejection_records_zero_openai_requests(tmp_path: Path) -> None:
    summary, outcomes, attempts, _github_rec, openai_rec = _run(
        tmp_path,
        _github_routes(repo="repo_archived"),
        recorded_openai_fixture("parsed_2_workflows"),
    )

    assert summary.status is RunStatus.COMPLETED
    assert outcomes == ["accepted", "rejected", "skipped", "skipped"]
    assert openai_rec.requests == []
    assert all(row["attempt_no"] == 1 for row in attempts)


def test_reader_empty_skips_the_extractor_without_an_openai_request(tmp_path: Path) -> None:
    entries = [
        {"path": "LICENSE", "mode": "100644", "type": "blob", "size": 1100, "sha": LICENSE_SHA},
        {
            "path": "README.md",
            "mode": "100644",
            "type": "blob",
            "size": 200000,
            "sha": README_SHA,
        },
    ]
    summary, outcomes, attempts, _github_rec, openai_rec = _run(
        tmp_path,
        _github_routes(tree=make_tree_fixture(entries)),
        recorded_openai_fixture("parsed_2_workflows"),
    )

    assert summary.status is RunStatus.COMPLETED
    assert outcomes == ["accepted", "accepted", "accepted", "skipped"]
    assert openai_rec.requests == []
    assert all(row["attempt_no"] == 1 for row in attempts)
    manifest_root = (tmp_path / "state.db").with_suffix(".manifests")
    extractor_manifest = json.loads(
        next(iter((manifest_root / "extractor").glob("*.json"))).read_bytes()
    )
    assert extractor_manifest["payload"] == {
        "outcome": "skipped",
        "skip_reason": "reader_empty",
    }


def test_canary_disciplines_hold_on_the_extracted_happy_path(tmp_path: Path) -> None:
    summary, outcomes, attempts, _github_rec, openai_rec = _run(
        tmp_path, _github_routes(), recorded_openai_fixture("parsed_2_workflows")
    )

    assert summary.status is RunStatus.COMPLETED
    assert outcomes == ["accepted", "accepted", "accepted", "extracted"]
    extractor_attempt = attempts[-1]
    assert extractor_attempt["stage"] == "extractor"
    assert extractor_attempt["prompt_version"] == EXTRACT_PROMPT_VERSION
    assert extractor_attempt["policy_version"] == "extract-policy-v1"
    assert extractor_attempt["model_id"] == ACTUAL_MODEL
    durable = _durable_bytes(tmp_path)
    assert FULL_TEXT_CANARY.encode() not in durable

    manifest_root = (tmp_path / "state.db").with_suffix(".manifests")
    extractor_manifest = json.loads(
        next(iter((manifest_root / "extractor").glob("*.json"))).read_bytes()
    )
    payload = extractor_manifest["payload"]
    assert FULL_TEXT_CANARY not in json.dumps(payload)
    excerpts = [
        ref["excerpt"]
        for workflow in payload["workflows"]
        for ref in (
            list(workflow["evidence"])
            + [ref for step in workflow["steps"] for ref in step["evidence"]]
        )
    ]
    assert EVIDENCE_CANARY in excerpts
    assert all(len(excerpt) <= MAX_EVIDENCE_EXCERPT_CHARS for excerpt in excerpts)
    summary_bytes = (tmp_path / "output" / "extraction-summary.json").read_bytes()
    assert EVIDENCE_CANARY.encode() not in summary_bytes
    assert FULL_TEXT_CANARY.encode() not in summary_bytes
    assert len(summary_bytes) <= 65_536
    assert openai_rec.call_count(*RESPONSES) == 1


def test_secret_canaries_stay_in_authorization_headers_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SKILLSCOUT_GITHUB_TOKEN", GITHUB_TOKEN)
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    summary, outcomes, _attempts, github_rec, openai_rec = _run(
        tmp_path,
        _github_routes(),
        recorded_openai_fixture("parsed_2_workflows"),
        github_token=None,
        openai_key=None,
    )

    assert summary.status is RunStatus.COMPLETED
    assert outcomes[-1] == "extracted"
    assert github_rec.requests
    for request in github_rec.requests:
        assert request.headers["authorization"] == f"Bearer {GITHUB_TOKEN}"
        assert not request.content or GITHUB_TOKEN.encode() not in request.content
    openai_request = openai_rec.requests[0]
    assert openai_request.headers["authorization"] == f"Bearer {OPENAI_KEY}"
    assert OPENAI_KEY.encode() not in openai_request.content

    durable = _durable_bytes(tmp_path)
    assert GITHUB_TOKEN.encode() not in durable
    assert OPENAI_KEY.encode() not in durable


def test_hydration_rebuilds_the_bundle_when_scratch_is_empty() -> None:
    outcomes, context, github_rec, openai_rec = _direct(
        _github_routes(), recorded_openai_fixture("parsed_2_workflows")
    )
    assert outcomes["extractor"].payload["outcome"] == "extracted"
    assert context.scratch["read_bundle"]

    # A fresh per-invocation context (the runner shape) has no scratch bundle:
    # the extractor rebuilds it byte-verified through hydrate_read_bundle.
    processor, github_rec2, openai_rec2 = _clients(
        _github_routes(), recorded_openai_fixture("parsed_2_workflows")
    )
    extractor_context = StageContext(
        subject=SUBJECT,
        prior_payloads={
            "scout": outcomes["scout"].payload,
            "filter": outcomes["filter"].payload,
            "reader": outcomes["reader"].payload,
        },
        scratch={},
    )
    hydrated = processor.process(_stage_input(PipelineStage.EXTRACTOR), extractor_context)

    assert hydrated.payload["outcome"] == "extracted"
    assert hydrated.payload["workflows"] == outcomes["extractor"].payload["workflows"]
    blob_gets = sum(
        count
        for (method, path), count in github_rec2.calls.items()
        if method == "GET" and "/git/blobs/" in path
    )
    assert blob_gets == 2  # one hash-verified GET per recorded file, no scout/filter traffic
    assert github_rec2.call_count(*META) == 0
    assert github_rec2.call_count(*TREE) == 0
    assert openai_rec2.call_count(*RESPONSES) == 1
