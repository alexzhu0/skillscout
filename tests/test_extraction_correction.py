"""Closed extraction-correction eligibility policy."""

from __future__ import annotations

import pytest

from skillscout.domain.extraction_correction import (
    ExtractionCorrectionReason,
    extraction_correction_reason,
)


def _payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "outcome": "schema_failure",
        "workflows": [],
        "dropped": [],
        "diagnostics": ["structured_output_validation_failed"],
    }
    payload.update(changes)
    return payload


def test_exact_structured_output_failure_is_schema_correctable() -> None:
    assert extraction_correction_reason(_payload()) is ExtractionCorrectionReason.SCHEMA


def test_all_excerpt_only_drops_are_excerpt_correctable() -> None:
    payload = _payload(
        diagnostics=["all_workflows_dropped"],
        dropped=[
            {"title": "One", "reasons": ["excerpt_not_verbatim"]},
            {"title": "Two", "reasons": ["excerpt_not_verbatim"]},
        ],
    )
    assert extraction_correction_reason(payload) is ExtractionCorrectionReason.EXCERPT


def test_one_excerpt_only_drop_makes_mixed_dropped_entries_correctable() -> None:
    payload = _payload(
        diagnostics=["all_workflows_dropped"],
        dropped=[
            {"title": "One", "reasons": ["excerpt_not_verbatim"]},
            {"title": "Two", "reasons": ["forbidden_text"]},
        ],
    )
    assert extraction_correction_reason(payload) is ExtractionCorrectionReason.EXCERPT


@pytest.mark.parametrize(
    "payload",
    [
        _payload(
            diagnostics=["all_workflows_dropped"],
            dropped=[{"title": "One", "reasons": ["forbidden_text"]}],
        ),
        _payload(
            diagnostics=["all_workflows_dropped"],
            dropped=[
                {
                    "title": "One",
                    "reasons": ["excerpt_not_verbatim", "forbidden_text"],
                }
            ],
        ),
        _payload(outcome="extracted"),
        _payload(workflows=[{"workflow_id": "wf-present"}]),
        _payload(diagnostics=["structured_output_validation_failed", "extra"]),
        _payload(diagnostics=["all_workflows_dropped"], dropped=[]),
        _payload(outcome="incomplete", diagnostics=[]),
        _payload(outcome="refused", diagnostics=[]),
        _payload(diagnostics="structured_output_validation_failed"),
        _payload(diagnostics=["all_workflows_dropped"], dropped=[{"reasons": []}]),
        _payload(
            diagnostics=["all_workflows_dropped"],
            dropped=[{"reasons": [{"untrusted": "shape"}]}],
        ),
    ],
)
def test_every_non_closed_or_malformed_payload_is_ineligible(payload: object) -> None:
    assert extraction_correction_reason(payload) is None
