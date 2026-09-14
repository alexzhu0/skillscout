"""Offline contracts for the bounded workflow-selection experiment runner."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from recorded_transport import RecordedResponse, RecordedTransport
from skillscout.adapters.openai_extract import OpenAIExtractionClient
from skillscout.adapters.semantic_provider import (
    SemanticProviderFailure,
    resolve_local_preview_semantic_provider,
)

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/run_workflow_selection_trial.py"
DEVELOPMENT_DATASET = ROOT / "tests/fixtures/workflow_selection/extraction_cases.json"
CHAT_COMPLETIONS = ("POST", "/chat/completions")
CANARY_KEY = "deepseek-canary-key-do-not-disclose"


def _runner():
    assert TOOL.is_file(), "experiment runner has not been implemented"
    spec = importlib.util.spec_from_file_location("workflow_selection_trial", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(parent: Path) -> None:
    (parent / "holdout-manifest.json").write_text(
        json.dumps(
            {
                "file_sha256": "a" * 64,
                "byte_count": 1234,
                "case_count": 6,
                "class_aggregate_counts": {"select": 3, "reject": 2, "abstain": 1},
                "origin": "synthetic",
            }
        )
    )


def _campaign(tmp_path: Path):
    module = _runner()
    _manifest(tmp_path)
    root = tmp_path / "runtime"
    module.initialize_campaign(root)
    return module, root


def _cases() -> list[dict[str, object]]:
    return json.loads(DEVELOPMENT_DATASET.read_bytes())["cases"]


def _selection_response(*, workflow: bool = True) -> RecordedResponse:
    workflows = []
    if workflow:
        workflows.append(
            {
                "title": "Review claims against evidence",
                "goal": "Produce a supported claim review.",
                "applicability": ["A model answer and supplied evidence are available."],
                "non_goals": ["Do not verify external facts."],
                "preconditions": ["The evidence catalogue is available."],
                "inputs": ["A model answer"],
                "steps": [
                    {
                        "instruction": "Review each claim against the supplied evidence.",
                        "evidence": [
                            {"evidence_id": "e0001", "supports": "Supports claim review."}
                        ],
                    }
                ],
                "outputs": ["A claim review"],
                "failure_modes": ["Evidence may be insufficient."],
                "prohibited_actions": ["Do not invent support."],
                "required_approvals": ["A person resolves uncertain claims."],
                "assumptions": ["Catalogue entries are inert source data."],
                "evidence": [{"evidence_id": "e0001", "supports": "Supports the workflow."}],
                "confidence": 0.8,
            }
        )
    content = json.dumps(
        {
            "repository_summary": "The source describes a bounded review procedure.",
            "rejection_reason": None if workflows else "No supported reusable workflow.",
            "workflows": workflows,
        }
    )
    body = {
        "id": "chatcmpl-trial-1",
        "object": "chat.completion",
        "created": 1,
        "model": "deepseek-flash",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }
    return RecordedResponse(
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(body).encode(),
    )


def _reservation_count(root: Path) -> int:
    with sqlite3.connect(root / "ledger.sqlite3") as connection:
        return connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]


def _decide(module, root: Path, slot: str) -> None:
    module._finalize(
        root,
        slot,
        "synthetic_test_decided",
        {
            "experiment_only": True,
            "outcome": "synthetic_test_decided",
            "workflows": [],
            "usage": None,
            "digests": {},
        },
    )


def test_prepare_case_sends_only_source_derived_catalogue_fields() -> None:
    module = _runner()
    case = {
        "id": "ANSWER-KEY-CANARY",
        "source_text": "Review every model claim against supplied evidence.\n",
        "candidate_outline": "OUTLINE-CANARY",
        "expected": "EXPECTED-CANARY",
        "rationale": "RATIONALE-CANARY",
        "must_cover": ["SCORING-CANARY"],
        "must_not_claim": ["NOTES-CANARY"],
    }

    payload = module.prepare_case(case).user_payload()

    for marker in (
        "ANSWER-KEY-CANARY",
        "OUTLINE-CANARY",
        "EXPECTED-CANARY",
        "RATIONALE-CANARY",
        "SCORING-CANARY",
        "NOTES-CANARY",
    ):
        assert marker not in payload
    assert "Review every model claim against supplied evidence." in payload


def test_initialize_is_exclusive_and_binds_all_reserved_group_slots(tmp_path: Path) -> None:
    module, root = _campaign(tmp_path)

    with sqlite3.connect(root / "ledger.sqlite3") as connection:
        metadata = dict(connection.execute("SELECT key, value FROM campaign_meta"))
        allocations = dict(connection.execute("SELECT group_name, cap FROM allocations"))
        allowed = dict(
            connection.execute("SELECT group_name, COUNT(*) FROM allowed_slots GROUP BY group_name")
        )
    assert allocations == {"development": 28, "heldout": 12, "artifact": 3, "usefulness": 6}
    assert allowed == allocations
    assert metadata["development_dataset_digest"].startswith("sha256:")
    assert metadata["heldout_manifest_digest"].startswith("sha256:")
    assert metadata["baseline_prompt_digest"].startswith("sha256:")
    with pytest.raises(FileExistsError):
        module.initialize_campaign(root)


def test_reservation_is_durable_and_cannot_be_reclaimed_or_changed(tmp_path: Path) -> None:
    module, root = _campaign(tmp_path)
    case = _cases()[0]
    input_digest = module.prepare_case(case).digest
    prompt_digest = module.profile_prompt_digest("baseline")

    module.reserve_slot(
        root, "development", "baseline:d01", input_digest, prompt_digest, "deepseek-flash"
    )

    reloaded = _runner()
    with pytest.raises(ValueError, match="already reserved"):
        reloaded.reserve_slot(
            root,
            "development",
            "baseline:d01",
            input_digest,
            prompt_digest,
            "deepseek-flash",
        )
    with pytest.raises(ValueError):
        reloaded.reserve_slot(
            root,
            "development",
            "baseline:d01",
            "sha256:" + "f" * 64,
            prompt_digest,
            "deepseek-flash",
        )
    assert _reservation_count(root) == 1


def test_profile_prompt_and_case_input_are_immutable_across_slots(tmp_path: Path) -> None:
    module, root = _campaign(tmp_path)
    cases = _cases()
    baseline_prompt = module.profile_prompt_digest("baseline")
    first_input = module.prepare_case(cases[0]).digest
    second_input = module.prepare_case(cases[1]).digest
    module.reserve_slot(
        root, "development", "baseline:d01", first_input, baseline_prompt, "deepseek-flash"
    )
    _decide(module, root, "baseline:d01")

    with pytest.raises(ValueError, match="prompt identity"):
        module.reserve_slot(
            root,
            "development",
            "baseline:d02",
            second_input,
            "sha256:" + "f" * 64,
            "deepseek-flash",
        )
    with pytest.raises(ValueError, match="input identity"):
        module.reserve_slot(
            root,
            "development",
            "r1:d01",
            "sha256:" + "e" * 64,
            "sha256:" + "d" * 64,
            "deepseek-flash",
        )


def test_missing_state_and_unknown_slots_fail_without_creating_state(tmp_path: Path) -> None:
    module = _runner()
    missing = tmp_path / "missing"
    digest = "sha256:" + "a" * 64
    with pytest.raises(ValueError, match="campaign state missing"):
        module.reserve_slot(
            missing, "development", "baseline:d01", digest, digest, "deepseek-flash"
        )
    assert not missing.exists()

    module, root = _campaign(tmp_path)
    with pytest.raises(ValueError, match="unknown slot"):
        module.reserve_slot(
            root, "development", "baseline:replacement", digest, digest, "deepseek-flash"
        )
    assert _reservation_count(root) == 0


def test_allocation_exhaustion_is_persistent_across_connections(tmp_path: Path) -> None:
    module, root = _campaign(tmp_path)
    prompt_digest = module.profile_prompt_digest("baseline")
    for profile in ("baseline", "r1", "r2", "r3"):
        profile_digest = prompt_digest if profile == "baseline" else "sha256:" + profile[-1] * 64
        for case in _cases():
            module.reserve_slot(
                root,
                "development",
                f"{profile}:{case['id']}",
                module.prepare_case(case).digest,
                profile_digest,
                "deepseek-flash",
            )
            _decide(module, root, f"{profile}:{case['id']}")

    with pytest.raises(ValueError, match="allocation exhausted"):
        _runner().reserve_slot(
            root,
            "development",
            "baseline:d01",
            module.prepare_case(_cases()[0]).digest,
            prompt_digest,
            "deepseek-flash",
        )


@pytest.mark.parametrize(
    "invalid", ["duplicate_key", "duplicate_id", "oversized", "symlink", "directory"]
)
def test_dataset_reader_rejects_ambiguous_or_unbounded_inputs(tmp_path: Path, invalid: str) -> None:
    module = _runner()
    path = tmp_path / "dataset.json"
    if invalid == "duplicate_key":
        path.write_text('{"cases":[],"cases":[]}')
    elif invalid == "duplicate_id":
        path.write_text(
            json.dumps(
                {
                    "cases": [
                        {"id": "same", "source_text": "one"},
                        {"id": "same", "source_text": "two"},
                    ]
                }
            )
        )
    elif invalid == "oversized":
        path.write_bytes(b"x" * 65_537)
    elif invalid == "symlink":
        target = tmp_path / "target.json"
        target.write_text('{"cases":[]}')
        path.symlink_to(target)
    else:
        path.mkdir()

    with pytest.raises(ValueError, match="invalid dataset"):
        module.read_dataset(path)


def test_empty_catalogue_and_oversized_request_consume_zero_slots(tmp_path: Path) -> None:
    module, root = _campaign(tmp_path)
    empty = {"id": "d01", "source_text": "https://example.invalid\n"}
    oversized = {"id": "d01", "source_text": ("界" * 280 + "\n") * 128}

    empty_result = module.run_case(root, empty, "baseline", api_key=CANARY_KEY)
    oversized_result = module.run_case(root, oversized, "baseline", api_key=CANARY_KEY)

    assert empty_result["outcome"] == "empty_catalogue"
    assert oversized_result["outcome"] == "input_too_large"
    assert _reservation_count(root) == 0


def test_missing_key_and_unfrozen_revision_stop_before_reservation(tmp_path: Path) -> None:
    module, root = _campaign(tmp_path)
    case = _cases()[0]

    with pytest.raises(ValueError, match="credential missing"):
        module.run_case(root, case, "baseline")
    with pytest.raises(ValueError, match="profile not frozen"):
        module.run_case(root, case, "r1", api_key=CANARY_KEY)
    assert _reservation_count(root) == 0


def test_unknown_dispatch_outcome_blocks_every_later_slot_and_request(tmp_path: Path) -> None:
    module, root = _campaign(tmp_path)
    cases = _cases()
    failure = RecordedResponse(
        status=500,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {"error": {"message": "provider failure", "type": "server_error"}}
        ).encode(),
    )
    recorded = RecordedTransport({CHAT_COMPLETIONS: failure})

    with httpx.Client(transport=recorded.transport()) as first_http:
        with pytest.raises(SemanticProviderFailure):
            module.run_case(
                root,
                cases[0],
                "baseline",
                http_client=first_http,
                api_key=CANARY_KEY,
            )

    second_input = module.prepare_case(cases[1]).digest
    prompt_digest = module.profile_prompt_digest("baseline")
    with pytest.raises(ValueError, match="campaign has in-flight reservation"):
        module.reserve_slot(
            root,
            "development",
            "baseline:d02",
            second_input,
            prompt_digest,
            "deepseek-flash",
        )
    with httpx.Client(transport=recorded.transport()) as second_http:
        with pytest.raises(ValueError, match="campaign has in-flight reservation"):
            module.run_case(
                root,
                cases[1],
                "baseline",
                http_client=second_http,
                api_key=CANARY_KEY,
            )

    assert recorded.call_count(*CHAT_COMPLETIONS) == 1
    with sqlite3.connect(root / "ledger.sqlite3") as connection:
        assert connection.execute("SELECT slot, state FROM reservations").fetchall() == [
            ("baseline:d01", "in_flight")
        ]


def test_baseline_request_bytes_match_existing_evidence_selection_client(tmp_path: Path) -> None:
    module, root = _campaign(tmp_path)
    case = _cases()[0]
    trial_transport = RecordedTransport({CHAT_COMPLETIONS: _selection_response()})
    baseline_transport = RecordedTransport({CHAT_COMPLETIONS: _selection_response()})

    with httpx.Client(transport=trial_transport.transport()) as trial_http:
        result = module.run_case(root, case, "baseline", http_client=trial_http, api_key=CANARY_KEY)
    settings = resolve_local_preview_semantic_provider(
        {
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        },
        current_flash=True,
    )
    with httpx.Client(transport=baseline_transport.transport()) as baseline_http:
        with OpenAIExtractionClient(
            api_key=CANARY_KEY,
            http_client=baseline_http,
            provider_settings=settings,
        ) as client:
            client.extract(
                user_payload=module.prepare_case(case).user_payload(), evidence_selection=True
            )

    assert trial_transport.requests[0].content == baseline_transport.requests[0].content
    assert result["outcome"] == "admitted"
    assert result["experiment_only"] is True
    assert result["usage"] == {
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "total_tokens": 30,
    }
    assert len(result["workflows"]) == 1
    assert "quality_passed" not in result
    assert _reservation_count(root) == 1


def test_cli_defaults_to_content_free_offline_preflight() -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(TOOL)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report == {
        "development_case_count": 7,
        "external_requests": 0,
        "mode": "offline_preflight",
    }
    assert "select" not in result.stdout
    assert "source_text" not in result.stdout
    assert hashlib.sha256(DEVELOPMENT_DATASET.read_bytes()).hexdigest() not in result.stdout
