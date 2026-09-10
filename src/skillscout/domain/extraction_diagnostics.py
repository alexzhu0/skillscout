"""Sanitized diagnostics for forbidden text at the extraction boundary."""

from __future__ import annotations

from collections.abc import Iterator

from skillscout.domain.extraction import ExtractorWorkflow, find_forbidden_text

_SCHEMA_VERSION = "extraction-boundary-diagnostics-v1"
_MAX_FINDINGS = 32


def _workflow_texts(workflow: ExtractorWorkflow) -> Iterator[tuple[str, str]]:
    yield "title", workflow.title
    yield "goal", workflow.goal

    for field_name, field_values in (
        ("applicability", workflow.applicability),
        ("non_goals", workflow.non_goals),
        ("preconditions", workflow.preconditions),
        ("inputs", workflow.inputs),
        ("outputs", workflow.outputs),
        ("failure_modes", workflow.failure_modes),
        ("prohibited_actions", workflow.prohibited_actions),
        ("required_approvals", workflow.required_approvals),
        ("assumptions", workflow.assumptions),
    ):
        for index, text in enumerate(field_values):
            yield f"{field_name}[{index}]", text

    for evidence_index, evidence in enumerate(workflow.evidence):
        prefix = f"evidence[{evidence_index}]"
        yield f"{prefix}.path", evidence.path
        yield f"{prefix}.excerpt", evidence.excerpt
        yield f"{prefix}.supports", evidence.supports

    for step_index, step in enumerate(workflow.steps):
        step_prefix = f"steps[{step_index}]"
        yield f"{step_prefix}.instruction", step.instruction
        for evidence_index, evidence in enumerate(step.evidence):
            prefix = f"{step_prefix}.evidence[{evidence_index}]"
            yield f"{prefix}.path", evidence.path
            yield f"{prefix}.excerpt", evidence.excerpt
            yield f"{prefix}.supports", evidence.supports


def forbidden_text_diagnostics(workflow: ExtractorWorkflow) -> dict[str, object]:
    """Return bounded rule and field diagnostics without echoing model content."""

    findings: list[dict[str, str]] = []
    for field_path, text in _workflow_texts(workflow):
        for rule_id in find_forbidden_text(text):
            if len(findings) == _MAX_FINDINGS:
                return {
                    "schema_version": _SCHEMA_VERSION,
                    "findings": findings,
                    "truncated": True,
                }
            findings.append({"rule_id": rule_id, "field_path": field_path})

    return {
        "schema_version": _SCHEMA_VERSION,
        "findings": findings,
        "truncated": False,
    }
