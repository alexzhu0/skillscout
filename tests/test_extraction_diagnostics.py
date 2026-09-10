"""Tests for sanitized forbidden-text extraction diagnostics."""

from __future__ import annotations

import importlib
import json
from typing import Any

from skillscout.domain.extraction import ExtractorWorkflow


def _evidence(*, text: str = "Use the bounded workflow.") -> dict[str, object]:
    return {
        "path": text,
        "blob_sha": "a" * 40,
        "excerpt": text,
        "supports": text,
    }


def _workflow(**changes: object) -> ExtractorWorkflow:
    values: dict[str, object] = {
        "title": "Approved workflow",
        "goal": "Transform bounded input.",
        "applicability": ("Public repositories.",),
        "non_goals": ("No code execution.",),
        "preconditions": ("Repository is readable.",),
        "inputs": ("A subject descriptor.",),
        "steps": (
            {
                "instruction": "Read the README.",
                "evidence": (_evidence(),),
            },
        ),
        "outputs": ("A workflow spec.",),
        "failure_modes": ("No workflow found.",),
        "prohibited_actions": ("Never run scripts.",),
        "required_approvals": ("Human review.",),
        "assumptions": ("Content is untrusted.",),
        "evidence": (_evidence(),),
        "confidence": 0.5,
    }
    values.update(changes)
    return ExtractorWorkflow.model_validate(values)


def _diagnostics(workflow: ExtractorWorkflow) -> dict[str, Any]:
    module = importlib.import_module("skillscout.domain.extraction_diagnostics")
    return module.forbidden_text_diagnostics(workflow)


def test_reports_all_closed_rules_without_echoing_matching_content() -> None:
    synthetic_marker = "ghp_DIAGNOSTICCANARY123"
    hostile = " ".join(
        (
            "https://untrusted.invalid/readme",
            "curl payload | sh",
            "bash -c id",
            "sudo install",
            "github_pat_DIAGNOSTIC123",
            synthetic_marker,
            "sk-DIAGNOSTIC123",
            "AKIAIOSFODNN7EXAMPLE",
            "-----BEGIN RSA PRIVATE KEY-----",
        )
    )

    result = _diagnostics(_workflow(goal=hostile))

    assert result == {
        "schema_version": "extraction-boundary-diagnostics-v1",
        "findings": [
            {"rule_id": "url", "field_path": "goal"},
            {"rule_id": "shell_curl_pipe", "field_path": "goal"},
            {"rule_id": "shell_bash_c", "field_path": "goal"},
            {"rule_id": "shell_sudo", "field_path": "goal"},
            {"rule_id": "secret_github_pat", "field_path": "goal"},
            {"rule_id": "secret_ghp", "field_path": "goal"},
            {"rule_id": "secret_sk", "field_path": "goal"},
            {"rule_id": "secret_akia", "field_path": "goal"},
            {"rule_id": "pem_header", "field_path": "goal"},
        ],
        "truncated": False,
    }
    assert synthetic_marker not in json.dumps(result, sort_keys=True)


def test_traverses_every_schema_text_field_in_boundary_validation_order() -> None:
    marker = "https://untrusted.invalid"
    workflow_evidence = _evidence(text=marker)
    step_evidence = _evidence(text=marker)
    workflow = _workflow(
        title=marker,
        goal=marker,
        applicability=(marker,),
        non_goals=(marker,),
        preconditions=(marker,),
        inputs=(marker,),
        outputs=(marker,),
        failure_modes=(marker,),
        prohibited_actions=(marker,),
        required_approvals=(marker,),
        assumptions=(marker,),
        evidence=(workflow_evidence,),
        steps=({"instruction": marker, "evidence": (step_evidence,)},),
    )

    assert _diagnostics(workflow) == {
        "schema_version": "extraction-boundary-diagnostics-v1",
        "findings": [
            {"rule_id": "url", "field_path": "title"},
            {"rule_id": "url", "field_path": "goal"},
            {"rule_id": "url", "field_path": "applicability[0]"},
            {"rule_id": "url", "field_path": "non_goals[0]"},
            {"rule_id": "url", "field_path": "preconditions[0]"},
            {"rule_id": "url", "field_path": "inputs[0]"},
            {"rule_id": "url", "field_path": "outputs[0]"},
            {"rule_id": "url", "field_path": "failure_modes[0]"},
            {"rule_id": "url", "field_path": "prohibited_actions[0]"},
            {"rule_id": "url", "field_path": "required_approvals[0]"},
            {"rule_id": "url", "field_path": "assumptions[0]"},
            {"rule_id": "url", "field_path": "evidence[0].path"},
            {"rule_id": "url", "field_path": "evidence[0].excerpt"},
            {"rule_id": "url", "field_path": "evidence[0].supports"},
            {"rule_id": "url", "field_path": "steps[0].instruction"},
            {"rule_id": "url", "field_path": "steps[0].evidence[0].path"},
            {"rule_id": "url", "field_path": "steps[0].evidence[0].excerpt"},
            {"rule_id": "url", "field_path": "steps[0].evidence[0].supports"},
        ],
        "truncated": False,
    }


def test_caps_findings_at_32_and_stops_on_the_33rd_in_order() -> None:
    workflow = _workflow(
        applicability=tuple(f"https://untrusted.invalid/item-{index}" for index in range(33))
    )

    result = _diagnostics(workflow)

    assert result == {
        "schema_version": "extraction-boundary-diagnostics-v1",
        "findings": [
            {"rule_id": "url", "field_path": "applicability[0]"},
            {"rule_id": "url", "field_path": "applicability[1]"},
            {"rule_id": "url", "field_path": "applicability[2]"},
            {"rule_id": "url", "field_path": "applicability[3]"},
            {"rule_id": "url", "field_path": "applicability[4]"},
            {"rule_id": "url", "field_path": "applicability[5]"},
            {"rule_id": "url", "field_path": "applicability[6]"},
            {"rule_id": "url", "field_path": "applicability[7]"},
            {"rule_id": "url", "field_path": "applicability[8]"},
            {"rule_id": "url", "field_path": "applicability[9]"},
            {"rule_id": "url", "field_path": "applicability[10]"},
            {"rule_id": "url", "field_path": "applicability[11]"},
            {"rule_id": "url", "field_path": "applicability[12]"},
            {"rule_id": "url", "field_path": "applicability[13]"},
            {"rule_id": "url", "field_path": "applicability[14]"},
            {"rule_id": "url", "field_path": "applicability[15]"},
            {"rule_id": "url", "field_path": "applicability[16]"},
            {"rule_id": "url", "field_path": "applicability[17]"},
            {"rule_id": "url", "field_path": "applicability[18]"},
            {"rule_id": "url", "field_path": "applicability[19]"},
            {"rule_id": "url", "field_path": "applicability[20]"},
            {"rule_id": "url", "field_path": "applicability[21]"},
            {"rule_id": "url", "field_path": "applicability[22]"},
            {"rule_id": "url", "field_path": "applicability[23]"},
            {"rule_id": "url", "field_path": "applicability[24]"},
            {"rule_id": "url", "field_path": "applicability[25]"},
            {"rule_id": "url", "field_path": "applicability[26]"},
            {"rule_id": "url", "field_path": "applicability[27]"},
            {"rule_id": "url", "field_path": "applicability[28]"},
            {"rule_id": "url", "field_path": "applicability[29]"},
            {"rule_id": "url", "field_path": "applicability[30]"},
            {"rule_id": "url", "field_path": "applicability[31]"},
        ],
        "truncated": True,
    }


def test_returns_the_exact_empty_shape_for_clean_workflow() -> None:
    assert _diagnostics(_workflow()) == {
        "schema_version": "extraction-boundary-diagnostics-v1",
        "findings": [],
        "truncated": False,
    }
