"""Behavior contracts for the production-owned Phase 6 campaign runner."""

from __future__ import annotations

import importlib
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT_SHA = "a" * 40
WORKFLOW_SHA256 = "sha256:" + "b" * 64
HOSTED_RUN_ID = 123456789
RUN_ATTEMPT = 1
EXPECTED_INJECTION_CORPUS = {
    "action_solicitation": (
        "action_solicitation.md",
        "sha256:f1f3d7e1e5f63a98098f095bc1bc6c855e083126e001b70a101a885b0ae00839",
    ),
    "cross_stage_amplification": (
        "cross_stage_amplification.md",
        "sha256:aa7f20c74f3d98b216f0f57b45e743702e2c91c4b2591e8c038f50182a49b8bf",
    ),
    "direct_override": (
        "direct_override.md",
        "sha256:b0c8d5188416a8778fae08105fbf5a6bfba6cf24eb2b83746c701bd7012c9353",
    ),
    "encoded_payload": (
        "encoded_payload.md",
        "sha256:6f58f2f8764e21af542af5e536bceae948f44d7dbea7f24e7d1da0b82728fbbd",
    ),
    "exfiltration_markup": (
        "exfiltration_markup.md",
        "sha256:508b9b8ee9fd2139d528e752ad708501f1ed5fce5e83c84712a9198142e1984d",
    ),
    "privilege_masquerade": (
        "privilege_masquerade.md",
        "sha256:4457913423dd7f0265022e2433fc03446bd38953b08c618e294f7cd6cadaff2f",
    ),
    "secret_solicitation": (
        "secret_solicitation.md",
        "sha256:b4dadb43c42c5576d80968adbacb55ebc1a5c50fe192e291bcdff9521ed13f3b",
    ),
}


def _runner() -> Any:
    return importlib.import_module("skillscout.application.phase6_adversarial_runner")


def _bindings(module: Any) -> Any:
    return module.CampaignBindings(
        source_commit_sha=SOURCE_COMMIT_SHA,
        workflow_sha256=WORKFLOW_SHA256,
        hosted_run_id=HOSTED_RUN_ID,
        run_attempt=RUN_ATTEMPT,
        synthetic_header_canary="phase6-synthetic-header-canary",
        synthetic_payload_canary="phase6-synthetic-payload-canary",
    )


def _closed_corpus(module: Any) -> tuple[Any, ...]:
    corpus = getattr(module, "INJECTION_CORPUS", None)
    assert type(corpus) is tuple, "production runner must own an immutable injection corpus"
    return corpus


def _execute_with_corpus_mutation(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
    corpus: tuple[Any, ...],
) -> tuple[int, Any]:
    monkeypatch.setattr(module, "INJECTION_CORPUS", corpus)
    sink = module.MemoryCampaignSink()
    return module.execute_campaign(_bindings(module), sink=sink), sink


def test_runner_registry_is_exactly_bound_to_the_committed_scenario_matrix() -> None:
    module = _runner()
    matrix = json.loads((ROOT / "tests/fixtures/acceptance/scenario_matrix.json").read_bytes())
    assert tuple(item.name for item in module.SCENARIO_REGISTRY) == tuple(matrix)
    assert tuple(item.scenario_id for item in module.SCENARIO_REGISTRY) == tuple(
        scenario["scenario_id"] for scenario in matrix.values()
    )
    assert tuple((item.fixture_id, item.mutation) for item in module.SCENARIO_REGISTRY) == tuple(
        (
            scenario["payload"]["fixture_id"],
            scenario["payload"]["mutation"],
        )
        for scenario in matrix.values()
    )


def test_runner_embeds_the_exact_independently_digested_seven_fixture_corpus() -> None:
    module = _runner()
    corpus = _closed_corpus(module)
    observed = {entry.fixture_id: (entry.payload, entry.digest) for entry in corpus}
    assert set(observed) == set(EXPECTED_INJECTION_CORPUS)
    assert len(observed) == len(corpus) == 7
    for fixture_id, (filename, expected_digest) in EXPECTED_INJECTION_CORPUS.items():
        committed_bytes = (ROOT / "tests" / "fixtures" / "injection" / filename).read_bytes()
        assert "sha256:" + hashlib.sha256(committed_bytes).hexdigest() == expected_digest
        assert observed[fixture_id] == (committed_bytes, expected_digest)


def test_full_runner_delivers_each_exact_injection_payload_to_the_controlled_seams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner()
    corpus = {entry.fixture_id: entry.payload for entry in _closed_corpus(module)}
    observed: dict[str, bytes] = {}
    production_evaluator = module.evaluate_controlled_scenario

    def observe(**kwargs: object) -> dict[str, object]:
        scenario = kwargs["scenario"]
        assert isinstance(scenario, dict)
        payload = scenario["payload"]
        assert isinstance(payload, dict)
        mutation = payload["mutation"]
        if mutation in corpus:
            observed[str(mutation)] = kwargs["fixture_bytes"]  # type: ignore[assignment]
        return production_evaluator(**kwargs)

    monkeypatch.setattr(module, "evaluate_controlled_scenario", observe)
    sink = module.MemoryCampaignSink()
    assert module.execute_campaign(_bindings(module), sink=sink) == 0
    assert observed == corpus
    report = json.loads(sink.report_bytes)
    assert report["injection_fixture_digests"] == {
        fixture_id: expected_digest
        for fixture_id, (_, expected_digest) in EXPECTED_INJECTION_CORPUS.items()
    }
    assert str(report["injection_corpus_digest"]).startswith("sha256:")


def test_runner_fails_closed_when_one_injection_fixture_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner()
    status, sink = _execute_with_corpus_mutation(
        module,
        monkeypatch,
        _closed_corpus(module)[:-1],
    )
    assert status == 1
    assert sink.report_bytes is None


def test_runner_fails_closed_when_injection_fixture_bytes_are_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner()
    corpus = _closed_corpus(module)
    mutated = (
        replace(corpus[0], payload=corpus[0].payload + b"\nreplacement"),
        *corpus[1:],
    )
    status, sink = _execute_with_corpus_mutation(module, monkeypatch, mutated)
    assert status == 1
    assert sink.report_bytes is None


def test_runner_fails_closed_when_injection_fixture_identities_are_swapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner()
    corpus = _closed_corpus(module)
    mutated = (
        replace(corpus[0], fixture_id=corpus[1].fixture_id),
        replace(corpus[1], fixture_id=corpus[0].fixture_id),
        *corpus[2:],
    )
    status, sink = _execute_with_corpus_mutation(module, monkeypatch, mutated)
    assert status == 1
    assert sink.report_bytes is None


def test_runner_fails_closed_when_payload_acquisition_is_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner()
    _closed_corpus(module)
    acquire = getattr(module, "_fixture_bytes_for_scenario", None)
    assert callable(acquire), "runner must have one closed fixture acquisition seam"
    monkeypatch.setattr(
        module,
        "_fixture_bytes_for_scenario",
        lambda _scenario, _corpus: b"bypassed-payload",
    )
    sink = module.MemoryCampaignSink()
    assert module.execute_campaign(_bindings(module), sink=sink) == 1
    assert sink.report_bytes is None


def test_runner_classifies_known_scenario_failure_without_free_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _runner()
    sink = module.MemoryCampaignSink()
    production_evaluator = module.evaluate_controlled_scenario

    def fail_one_known_scenario(**kwargs: object) -> dict[str, object]:
        if kwargs["scenario_name"] == "negative_filter":
            raise module.CampaignAssertionFailure()
        return production_evaluator(**kwargs)

    monkeypatch.setattr(module, "evaluate_controlled_scenario", fail_one_known_scenario)
    assert (
        module.execute_campaign(
            _bindings(module),
            sink=sink,
        )
        == 1
    )
    diagnostic = json.loads(sink.diagnostic_bytes)
    assert diagnostic == {
        "schema_version": "phase6.offline-diagnostic.v2",
        "source_commit_sha": SOURCE_COMMIT_SHA,
        "workflow_sha256": WORKFLOW_SHA256,
        "hosted_run_id": HOSTED_RUN_ID,
        "run_attempt": RUN_ATTEMPT,
        "control_phase": "scenario-evaluation",
        "collected": 25,
        "passed": 2,
        "failed": 1,
        "errors": 0,
        "failed_node_index": 2,
        "failed_when": "assertion",
        "failure_class": "scenario_assertion_failure",
        "report_write_status": "not_attempted",
        "report_exists": False,
        "report_size": 0,
        "artifact_retention_days": 1,
    }
    assert sink.report_bytes is None
    serialized = sink.diagnostic_bytes.decode("ascii")
    assert "negative_filter" not in serialized
    assert "phase6-synthetic-" not in serialized


def test_runner_classifies_final_report_write_failure_separately() -> None:
    module = _runner()
    sink = module.MemoryCampaignSink(fail_report_write=True)

    assert module.execute_campaign(_bindings(module), sink=sink) == 1
    diagnostic = json.loads(sink.diagnostic_bytes)
    assert diagnostic["failure_class"] == "report_write_failure"
    assert diagnostic["control_phase"] == "report-write"
    assert diagnostic["failed_when"] == "report_write"
    assert diagnostic["collected"] == 25
    assert diagnostic["passed"] == 25
    assert diagnostic["failed"] == 0
    assert diagnostic["errors"] == 0
    assert diagnostic["failed_node_index"] == -1
    assert diagnostic["report_write_status"] == "failed"
    assert diagnostic["report_exists"] is False
    assert diagnostic["report_size"] == 0
    assert set(diagnostic) == {
        "schema_version",
        "source_commit_sha",
        "workflow_sha256",
        "hosted_run_id",
        "run_attempt",
        "control_phase",
        "collected",
        "passed",
        "failed",
        "errors",
        "failed_node_index",
        "failed_when",
        "failure_class",
        "report_write_status",
        "report_exists",
        "report_size",
        "artifact_retention_days",
    }


def test_runner_main_produces_bound_canonical_success_report() -> None:
    module = _runner()
    sink = module.MemoryCampaignSink()

    status = module.main(
        [
            "--source-commit-sha",
            SOURCE_COMMIT_SHA,
            "--workflow-sha256",
            WORKFLOW_SHA256,
            "--hosted-run-id",
            str(HOSTED_RUN_ID),
            "--run-attempt",
            str(RUN_ATTEMPT),
        ],
        sink=sink,
        synthetic_header_canary="phase6-synthetic-header-canary",
        synthetic_payload_canary="phase6-synthetic-payload-canary",
    )

    assert status == 0
    assert sink.diagnostic_bytes is None
    report = json.loads(sink.report_bytes)
    assert report["source_commit_sha"] == SOURCE_COMMIT_SHA
    assert report["workflow_sha256"] == WORKFLOW_SHA256
    assert report["hosted_run_id"] == HOSTED_RUN_ID
    assert report["run_attempt"] == RUN_ATTEMPT
    assert report["controlled_scenario_count"] == 22
    assert report["required_scenario_ids"] == report["completed_scenario_ids"]
    assert len(report["scenario_result_digests"]) == 22
    assert len(report["injection_fixture_digests"]) == 7
    assert str(report["injection_corpus_digest"]).startswith("sha256:")
    assert report["synthetic_canary_hit_count"] == 0
    assert sink.report_bytes == (
        json.dumps(
            report,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")
