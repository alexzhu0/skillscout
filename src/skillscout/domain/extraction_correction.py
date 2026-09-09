"""Closed extraction correction vocabulary and eligibility policy."""

from __future__ import annotations

from enum import StrEnum
from typing import Mapping

EXTRACTION_CORRECTION_POLICY_VERSION = "extract-correction-policy-v1"
EXTRACTION_CORRECTION_PROMPT_VERSION = "extract-correction-prompt-v1"


class ExtractionCorrectionReason(StrEnum):
    """The complete set of extraction failures eligible for correction."""

    SCHEMA = "extraction_correction_schema"
    EXCERPT = "extraction_correction_excerpt"


def extraction_correction_reason(
    payload: object,
) -> ExtractionCorrectionReason | None:
    """Return the closed correction reason for an extractor payload, if any."""

    if not isinstance(payload, Mapping):
        return None
    if payload.get("outcome") != "schema_failure" or payload.get("workflows") != []:
        return None
    diagnostics = payload.get("diagnostics")
    if diagnostics == ["structured_output_validation_failed"]:
        return ExtractionCorrectionReason.SCHEMA
    if diagnostics != ["all_workflows_dropped"]:
        return None
    dropped = payload.get("dropped")
    if not isinstance(dropped, list) or not dropped:
        return None
    reason_sets: list[set[str]] = []
    for entry in dropped:
        if not isinstance(entry, Mapping):
            return None
        reasons = entry.get("reasons")
        if not isinstance(reasons, list) or not reasons:
            return None
        if any(type(reason) is not str for reason in reasons):
            return None
        reason_sets.append(set(reasons))
    if {"excerpt_not_verbatim"} in reason_sets:
        return ExtractionCorrectionReason.EXCERPT
    return None
