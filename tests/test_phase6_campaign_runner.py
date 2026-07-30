"""Behavior contracts for the production-owned Phase 6 campaign runner."""

from __future__ import annotations

import importlib
import json
from typing import Any


SOURCE_COMMIT_SHA = "a" * 40
WORKFLOW_SHA256 = "sha256:" + "b" * 64
HOSTED_RUN_ID = 123456789
RUN_ATTEMPT = 1


def _runner() -> Any:
    return importlib.import_module(
        "skillscout.application.phase6_adversarial_runner"
    )


def _bindings(module: Any) -> Any:
    return module.CampaignBindings(
        source_commit_sha=SOURCE_COMMIT_SHA,
        workflow_sha256=WORKFLOW_SHA256,
        hosted_run_id=HOSTED_RUN_ID,
        run_attempt=RUN_ATTEMPT,
        synthetic_header_canary="phase6-synthetic-header-canary",
        synthetic_payload_canary="phase6-synthetic-payload-canary",
    )


def test_runner_classifies_known_scenario_failure_without_free_text() -> None:
    module = _runner()
    sink = module.MemoryCampaignSink()
    production_evaluator = module.evaluate_controlled_scenario

    def fail_one_known_scenario(**kwargs: object) -> dict[str, object]:
        if kwargs["scenario_name"] == "negative_filter":
            raise module.CampaignAssertionFailure()
        return production_evaluator(**kwargs)

    assert (
        module.execute_campaign(
            _bindings(module),
            sink=sink,
            evaluator=fail_one_known_scenario,
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

