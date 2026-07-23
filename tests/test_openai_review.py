"""Independent Reviewer, eligibility, attestation, and terminal contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from skillscout.domain.review import (
    ELIGIBILITY_POLICY_VERSION,
    REVIEW_OUTPUT_SCHEMA_VERSION,
    REVIEW_POLICY_VERSION,
    REVIEW_PROMPT_VERSION,
    ReviewReasonV1,
    ReviewResult,
    ReviewerJudgment,
    is_eligible,
)
from skillscout.domain.validation import ValidationReportV1


def _judgment(
    *,
    verdict: str = "YES",
    confidence: float = 0.80,
) -> ReviewerJudgment:
    return ReviewerJudgment.model_validate(
        {
            "schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
            "verdict": verdict,
            "confidence": confidence,
            "reasons": (
                {
                    "code": "clear_scope",
                    "text": "The candidate is bounded and reviewable.",
                },
            ),
            "missing_assumptions": (),
            "minimal_modifications": (),
        }
    )


def _report(*, error_count: int) -> ValidationReportV1:
    return ValidationReportV1.model_construct(error_count=error_count)


def test_domain_versions_and_judgment_are_strict_and_judge_only() -> None:
    assert ELIGIBILITY_POLICY_VERSION == "candidate-eligibility-v1"
    assert REVIEW_PROMPT_VERSION == "reviewer-prompt-v1"
    assert REVIEW_OUTPUT_SCHEMA_VERSION == "reviewer-judgment-v1"
    assert REVIEW_POLICY_VERSION == "reviewer-policy-v1"

    judgment = _judgment()
    assert judgment.verdict == "YES"
    assert judgment.reasons == (
        ReviewReasonV1(
            code="clear_scope",
            text="The candidate is bounded and reviewable.",
        ),
    )
    assert judgment.missing_assumptions == ()
    assert judgment.minimal_modifications == ()

    schema = ReviewerJudgment.model_json_schema()
    properties = set(schema["properties"])
    assert properties == {
        "schema_version",
        "verdict",
        "confidence",
        "reasons",
        "missing_assumptions",
        "minimal_modifications",
    }
    assert not properties.intersection(
        {
            "files",
            "replacement",
            "replacement_skill",
            "skill_md",
            "patch",
            "body",
            "rewrite",
        }
    )

    payload = judgment.model_dump(mode="python")
    for forbidden_field in (
        "files",
        "replacement",
        "replacement_skill",
        "skill_md",
        "patch",
        "body",
        "rewrite",
    ):
        with pytest.raises(ValidationError):
            ReviewerJudgment.model_validate(
                {**payload, forbidden_field: "replacement content"}
            )


@pytest.mark.parametrize("verdict", ("MAYBE", "yes", "", "NO "))
def test_domain_judgment_accepts_only_exact_yes_or_no(verdict: str) -> None:
    with pytest.raises(ValidationError):
        _judgment(verdict=verdict)


@pytest.mark.parametrize("confidence", (-0.01, 1.01))
def test_domain_judgment_confidence_is_closed_to_unit_interval(
    confidence: float,
) -> None:
    with pytest.raises(ValidationError):
        _judgment(confidence=confidence)


def test_domain_review_result_has_closed_cross_field_shapes() -> None:
    parsed = ReviewResult(
        status="parsed",
        judgment=_judgment(),
        refusal_text=None,
        incomplete_reason=None,
        request_id="resp_review_0001",
        model="gpt-reviewer-actual",
        usage=None,
        latency_ms=1,
    )
    assert parsed.judgment is not None

    for status, detail in (
        ("refused", {"refusal_text": "policy refusal"}),
        ("incomplete", {"incomplete_reason": "max_output_tokens"}),
        ("schema_invalid", {}),
    ):
        result = ReviewResult(
            status=status,
            judgment=None,
            refusal_text=detail.get("refusal_text"),
            incomplete_reason=detail.get("incomplete_reason"),
            request_id="resp_review_0002",
            model="gpt-reviewer-actual",
            usage=None,
            latency_ms=1,
        )
        assert result.judgment is None

    with pytest.raises(ValidationError):
        ReviewResult(
            status="parsed",
            judgment=None,
            refusal_text=None,
            incomplete_reason=None,
            request_id="resp_review_0003",
            model="gpt-reviewer-actual",
            usage=None,
            latency_ms=1,
        )


@pytest.mark.parametrize(
    ("error_count", "verdict", "confidence", "expected"),
    (
        (0, "YES", 0.79, False),
        (0, "YES", 0.80, True),
        (0, "YES", 1.00, True),
        (0, "NO", 0.79, False),
        (0, "NO", 0.80, False),
        (0, "NO", 1.00, False),
        (1, "YES", 0.79, False),
        (1, "YES", 0.80, False),
        (1, "YES", 1.00, False),
        (1, "NO", 0.79, False),
        (1, "NO", 0.80, False),
        (1, "NO", 1.00, False),
    ),
)
def test_domain_exact_validation_verdict_confidence_cross_product(
    error_count: int,
    verdict: str,
    confidence: float,
    expected: bool,
) -> None:
    assert (
        is_eligible(
            validation_report=_report(error_count=error_count),
            judgment=_judgment(verdict=verdict, confidence=confidence),
        )
        is expected
    )
