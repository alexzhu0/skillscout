"""Strict judge-only review, eligibility, attestation, and terminal contracts."""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from skillscout.domain.models import (
    NonNegativeInt,
    StrictFrozenModel,
    TokenUsage,
)
from skillscout.domain.validation import ValidationReportV1

REVIEW_PROMPT_VERSION: Final = "reviewer-prompt-v1"
REVIEW_OUTPUT_SCHEMA_VERSION: Final = "reviewer-judgment-v1"
REVIEW_POLICY_VERSION: Final = "reviewer-policy-v1"
REVIEW_RETRY_POLICY_VERSION: Final = "reviewer-no-retry-v1"
ELIGIBILITY_POLICY_VERSION: Final = "candidate-eligibility-v1"
ELIGIBILITY_CONFIDENCE_THRESHOLD: Final = 0.80

MAX_REVIEW_ITEMS: Final = 16
MAX_REVIEW_TEXT_CHARS: Final = 1_024
MAX_REVIEW_DIAGNOSTIC_CHARS: Final = 1_024

_ReasonCode = Annotated[
    str,
    Field(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_]*$"),
]
_ReviewText = Annotated[
    str,
    Field(min_length=1, max_length=MAX_REVIEW_TEXT_CHARS),
]
_ReviewTextItems = Annotated[
    tuple[_ReviewText, ...],
    Field(max_length=MAX_REVIEW_ITEMS),
]
_Diagnostic = Annotated[
    str,
    Field(min_length=1, max_length=MAX_REVIEW_DIAGNOSTIC_CHARS),
]
_Identifier = Annotated[str, Field(min_length=1, max_length=256)]


class ReviewReasonV1(StrictFrozenModel):
    """One bounded reason whose code is safe to persist and aggregate."""

    code: _ReasonCode
    text: _ReviewText


class ReviewerJudgment(StrictFrozenModel):
    """A strict judgment with no file, patch, body, or replacement channel."""

    schema_version: Literal["reviewer-judgment-v1"]
    verdict: Literal["YES", "NO"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasons: Annotated[
        tuple[ReviewReasonV1, ...],
        Field(min_length=1, max_length=MAX_REVIEW_ITEMS),
    ]
    missing_assumptions: _ReviewTextItems
    minimal_modifications: _ReviewTextItems


class ReviewResult(StrictFrozenModel):
    """One raw Reviewer attempt outcome and bounded response telemetry."""

    status: Literal["parsed", "refused", "incomplete", "schema_invalid"]
    judgment: ReviewerJudgment | None
    refusal_text: _Diagnostic | None
    incomplete_reason: _Diagnostic | None
    request_id: _Identifier | None
    model: _Identifier | None
    usage: TokenUsage | None
    latency_ms: NonNegativeInt

    @model_validator(mode="after")
    def validate_closed_result_shape(self) -> ReviewResult:
        if self.status == "parsed":
            if (
                self.judgment is None
                or self.refusal_text is not None
                or self.incomplete_reason is not None
            ):
                raise ValueError("parsed review result shape is inconsistent")
        elif self.status == "refused":
            if (
                self.judgment is not None
                or self.refusal_text is None
                or self.incomplete_reason is not None
            ):
                raise ValueError("refused review result shape is inconsistent")
        elif self.status == "incomplete":
            if (
                self.judgment is not None
                or self.refusal_text is not None
                or self.incomplete_reason is None
            ):
                raise ValueError("incomplete review result shape is inconsistent")
        elif (
            self.judgment is not None
            or self.refusal_text is not None
            or self.incomplete_reason is not None
        ):
            raise ValueError("schema-invalid review result shape is inconsistent")
        return self


def is_eligible(
    *,
    validation_report: ValidationReportV1,
    judgment: ReviewerJudgment,
) -> bool:
    """Apply the exact local eligibility rule without model-owned authority."""

    if (
        type(validation_report) is not ValidationReportV1
        or type(judgment) is not ReviewerJudgment
    ):
        raise TypeError("eligibility requires strict validation and review contracts")
    return (
        validation_report.error_count == 0
        and judgment.verdict == "YES"
        and judgment.confidence >= ELIGIBILITY_CONFIDENCE_THRESHOLD
    )
