"""Strict judge-only review, eligibility, attestation, and terminal contracts."""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from skillscout.domain.candidate_authority import (
    CandidateExecutionAuthorityV1,
    LineageResolutionV1,
    WorkflowSpecAuthorityV1,
)
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.models import (
    Digest,
    NonNegativeInt,
    StrictFrozenModel,
    TokenUsage,
)
from skillscout.domain.skill_artifacts import (
    GeneratedArtifactIdentityV1,
    PackageIdentityV1,
)
from skillscout.domain.validation import ValidationReportV1

REVIEW_PROMPT_VERSION: Final = "reviewer-prompt-v1"
REVIEW_OUTPUT_SCHEMA_VERSION: Final = "reviewer-judgment-v1"
REVIEW_POLICY_VERSION: Final = "reviewer-policy-v1"
REVIEW_RETRY_POLICY_VERSION: Final = "reviewer-bounded-transient-retry-v1"
ELIGIBILITY_POLICY_VERSION: Final = "candidate-eligibility-v1"
ELIGIBILITY_CONFIDENCE_THRESHOLD: Final = 0.80
GENERATOR_OUTCOME_EVIDENCE_SCHEMA_VERSION: Final = "generator-outcome-evidence-v1"
REVIEW_DISPOSITION_SCHEMA_VERSION: Final = "review-disposition-v1"
REVIEW_ATTESTATION_SCHEMA_VERSION: Final = "review-attestation-v1"
CANDIDATE_TERMINAL_SUMMARY_SCHEMA_VERSION: Final = "candidate-terminal-summary-v1"

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
_Version = Annotated[str, Field(min_length=1, max_length=128)]
_GeneratorOutcome = Literal["parsed", "refused", "incomplete", "schema_invalid"]
_ReviewDispositionStatus = Literal[
    "review_not_reached_generation_unsuccessful",
    "review_skipped_validation_errors",
    "reviewer_refusal",
    "reviewer_incomplete",
    "reviewer_schema_failure",
    "review_completed_no",
    "review_completed_low_confidence",
    "review_completed_eligible",
]
_TerminalOutcome = Literal[
    "qualification_rejected",
    "lineage_rejected",
    "generator_refusal",
    "generator_incomplete",
    "generator_schema_failure",
    "validation_rejected",
    "reviewer_refusal",
    "reviewer_incomplete",
    "reviewer_schema_failure",
    "review_rejected",
    "review_low_confidence",
    "eligible_local_candidate",
]


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


class GeneratorOutcomeEvidenceV1(StrictFrozenModel):
    """Bounded external evidence for exactly one attempted Generator result."""

    schema_version: Literal["generator-outcome-evidence-v1"]
    outcome: _GeneratorOutcome
    configured_generator_model_id: _Identifier
    actual_generator_model_id: _Identifier | None
    generator_prompt_version: _Version
    generator_output_schema_version: _Version
    generator_policy_version: _Version
    phase3_producer_version: _Version
    phase3_profile_version: _Version
    retry_policy_version: _Version
    request_id: _Identifier | None
    usage: TokenUsage | None
    latency_ms: NonNegativeInt
    generated_artifact_identity: GeneratedArtifactIdentityV1 | None

    @model_validator(mode="after")
    def validate_outcome_shape(self) -> GeneratorOutcomeEvidenceV1:
        if self.outcome == "parsed":
            if (
                self.generated_artifact_identity is None
                or self.actual_generator_model_id is None
            ):
                raise ValueError(
                    "parsed generator evidence requires actual model and artifact"
                )
        elif self.generated_artifact_identity is not None:
            raise ValueError("failed generator evidence cannot bind an artifact")
        return self


def generator_outcome_evidence(
    *,
    candidate_execution_authority: CandidateExecutionAuthorityV1,
    outcome: _GeneratorOutcome,
    actual_generator_model_id: str | None,
    request_id: str | None,
    usage: TokenUsage | None,
    latency_ms: int,
    generated_artifact_identity: GeneratedArtifactIdentityV1 | None,
) -> GeneratorOutcomeEvidenceV1:
    """Project one raw Generator attempt onto its configured execution authority."""

    if type(candidate_execution_authority) is not CandidateExecutionAuthorityV1:
        raise TypeError("generator evidence requires strict execution authority")
    if usage is not None and type(usage) is not TokenUsage:
        raise TypeError("generator evidence requires strict token usage")
    if (
        generated_artifact_identity is not None
        and type(generated_artifact_identity) is not GeneratedArtifactIdentityV1
    ):
        raise TypeError("generator evidence requires strict artifact identity")
    return GeneratorOutcomeEvidenceV1(
        schema_version=GENERATOR_OUTCOME_EVIDENCE_SCHEMA_VERSION,
        outcome=outcome,
        configured_generator_model_id=(
            candidate_execution_authority.configured_generator_model_id
        ),
        actual_generator_model_id=actual_generator_model_id,
        generator_prompt_version=(
            candidate_execution_authority.generator_prompt_version
        ),
        generator_output_schema_version=(
            candidate_execution_authority.generator_output_schema_version
        ),
        generator_policy_version=(
            candidate_execution_authority.generator_policy_version
        ),
        phase3_producer_version=candidate_execution_authority.phase3_producer_version,
        phase3_profile_version=candidate_execution_authority.phase3_profile_version,
        retry_policy_version=candidate_execution_authority.retry_policy_version,
        request_id=request_id,
        usage=usage,
        latency_ms=latency_ms,
        generated_artifact_identity=generated_artifact_identity,
    )


class ReviewDispositionV1(StrictFrozenModel):
    """Closed local classification of whether and how independent review ended."""

    schema_version: Literal["review-disposition-v1"]
    status: _ReviewDispositionStatus


def review_disposition(
    *,
    generation_succeeded: bool,
    validation_report: ValidationReportV1 | None,
    review_result: ReviewResult | None,
) -> ReviewDispositionV1:
    """Derive the only valid review disposition from preceding stage evidence."""

    return _review_disposition_from_evidence(
        generation_succeeded=generation_succeeded,
        validation_report=validation_report,
        review_result=review_result,
    )


def _review_disposition_from_evidence(
    *,
    generation_succeeded: bool,
    validation_report: ValidationReportV1 | None,
    review_result: ReviewResult | None,
) -> ReviewDispositionV1:
    if type(generation_succeeded) is not bool:
        raise TypeError("generation_succeeded must be a boolean")
    if not generation_succeeded:
        if validation_report is not None or review_result is not None:
            raise ValueError("unsuccessful generation cannot have review evidence")
        status: _ReviewDispositionStatus = (
            "review_not_reached_generation_unsuccessful"
        )
    else:
        if type(validation_report) is not ValidationReportV1:
            raise TypeError("successful generation requires a validation report")
        if validation_report.error_count > 0:
            if review_result is not None:
                raise ValueError("validation errors must skip Reviewer")
            status = "review_skipped_validation_errors"
        else:
            if type(review_result) is not ReviewResult:
                raise TypeError("clean validation requires a strict review result")
            if review_result.status == "refused":
                status = "reviewer_refusal"
            elif review_result.status == "incomplete":
                status = "reviewer_incomplete"
            elif review_result.status == "schema_invalid":
                status = "reviewer_schema_failure"
            else:
                judgment = review_result.judgment
                if judgment is None:
                    raise ValueError("parsed review result is missing judgment")
                if judgment.verdict == "NO":
                    status = "review_completed_no"
                elif judgment.confidence < ELIGIBILITY_CONFIDENCE_THRESHOLD:
                    status = "review_completed_low_confidence"
                else:
                    status = "review_completed_eligible"
    return ReviewDispositionV1(
        schema_version=REVIEW_DISPOSITION_SCHEMA_VERSION,
        status=status,
    )


class ReviewerFailedAttemptV1(StrictFrozenModel):
    """One sanitized transient remote-call failure before the retained result."""

    attempt_no: Annotated[int, Field(ge=1, le=2)]
    error_code: Literal["stage_transient_failure"]


class ReviewAttestationV1(StrictFrozenModel):
    """External Reviewer evidence over immutable artifact, package, and report."""

    schema_version: Literal["review-attestation-v1"]
    generated_artifact_identity: GeneratedArtifactIdentityV1
    package_identity: PackageIdentityV1
    package_digest: Digest
    validation_report_digest: Digest
    configured_reviewer_model_id: _Identifier
    actual_reviewer_model_id: _Identifier
    reviewer_prompt_version: _Version
    reviewer_output_schema_version: _Version
    reviewer_policy_version: _Version
    reviewer_retry_policy_version: _Version
    max_reviewer_attempts: Annotated[int, Field(ge=1, le=3)]
    attempt_count: Annotated[int, Field(ge=1, le=3)]
    failed_attempts: Annotated[
        tuple[ReviewerFailedAttemptV1, ...],
        Field(max_length=2),
    ]
    review_result: ReviewResult
    request_id: _Identifier | None
    usage: TokenUsage | None
    latency_ms: NonNegativeInt
    attestation_digest: Digest

    @model_validator(mode="after")
    def validate_complete_attestation(self) -> ReviewAttestationV1:
        if self.package_digest != self.package_identity.package_digest:
            raise ValueError("attestation package identities disagree")
        if (
            self.actual_reviewer_model_id != self.review_result.model
            or self.request_id != self.review_result.request_id
            or self.usage != self.review_result.usage
            or self.latency_ms != self.review_result.latency_ms
        ):
            raise ValueError("attestation Reviewer telemetry disagrees")
        expected_failed_attempts = tuple(range(1, self.attempt_count))
        if (
            self.attempt_count > self.max_reviewer_attempts
            or tuple(item.attempt_no for item in self.failed_attempts)
            != expected_failed_attempts
            or any(
                item.error_code != "stage_transient_failure"
                for item in self.failed_attempts
            )
        ):
            raise ValueError("attestation Reviewer attempt history disagrees")
        expected = sha256_digest(
            self.model_dump(
                mode="json",
                exclude_none=False,
                exclude={"attestation_digest"},
            )
        )
        if self.attestation_digest != expected:
            raise ValueError("review attestation digest mismatch")
        return self


def review_attestation(
    *,
    candidate_execution_authority: CandidateExecutionAuthorityV1,
    generated_artifact_identity: GeneratedArtifactIdentityV1,
    package_identity: PackageIdentityV1,
    validation_report: ValidationReportV1,
    review_result: ReviewResult,
    attempt_count: int = 1,
    failed_attempts: tuple[ReviewerFailedAttemptV1, ...] = (),
) -> ReviewAttestationV1:
    """Bind an exact raw Reviewer result without deriving eligibility."""

    strict_types = (
        (
            candidate_execution_authority,
            CandidateExecutionAuthorityV1,
            "execution authority",
        ),
        (
            generated_artifact_identity,
            GeneratedArtifactIdentityV1,
            "artifact identity",
        ),
        (package_identity, PackageIdentityV1, "package identity"),
        (validation_report, ValidationReportV1, "validation report"),
        (review_result, ReviewResult, "review result"),
    )
    for value, expected_type, label in strict_types:
        if type(value) is not expected_type:
            raise TypeError(f"attestation requires strict {label}")
    execution = candidate_execution_authority
    if (
        validation_report.candidate_execution_authority != execution
        or validation_report.workflow_spec_authority
        != execution.workflow_spec_authority
        or validation_report.generated_artifact_identity
        != generated_artifact_identity
        or validation_report.package_identity != package_identity
        or validation_report.package_digest != package_identity.package_digest
    ):
        raise ValueError("attestation evidence authority disagrees")
    if review_result.model is None:
        raise ValueError("attestation requires actual Reviewer identity")
    values: dict[str, object] = {
        "schema_version": REVIEW_ATTESTATION_SCHEMA_VERSION,
        "generated_artifact_identity": generated_artifact_identity,
        "package_identity": package_identity,
        "package_digest": package_identity.package_digest,
        "validation_report_digest": validation_report.report_digest,
        "configured_reviewer_model_id": execution.configured_reviewer_model_id,
        "actual_reviewer_model_id": review_result.model,
        "reviewer_prompt_version": execution.reviewer_prompt_version,
        "reviewer_output_schema_version": execution.reviewer_output_schema_version,
        "reviewer_policy_version": execution.reviewer_policy_version,
        "reviewer_retry_policy_version": execution.reviewer_retry_policy_version,
        "max_reviewer_attempts": execution.max_reviewer_attempts,
        "attempt_count": attempt_count,
        "failed_attempts": failed_attempts,
        "review_result": review_result,
        "request_id": review_result.request_id,
        "usage": review_result.usage,
        "latency_ms": review_result.latency_ms,
    }
    preimage = ReviewAttestationV1.model_construct(
        **values,
        attestation_digest="sha256:" + ("0" * 64),
    ).model_dump(
        mode="json",
        exclude_none=False,
        exclude={"attestation_digest"},
    )
    return ReviewAttestationV1(
        **values,
        attestation_digest=sha256_digest(preimage),
    )


class CandidateTerminalSummaryV1(StrictFrozenModel):
    """Complete external result for exactly one terminal Phase 3 branch."""

    schema_version: Literal["candidate-terminal-summary-v1"]
    workflow_spec_authority: WorkflowSpecAuthorityV1
    candidate_execution_authority: CandidateExecutionAuthorityV1
    qualification_passed: bool
    qualification_report_digest: Digest
    lineage_resolution: LineageResolutionV1
    generator_outcome_evidence: GeneratorOutcomeEvidenceV1 | None
    generated_artifact_identity: GeneratedArtifactIdentityV1 | None
    package_identity: PackageIdentityV1 | None
    package_digest: Digest | None
    validation_report_digest: Digest | None
    validation_error_count: Annotated[int, Field(ge=0, le=256)] | None
    review_disposition: ReviewDispositionV1
    review_attestation_digest: Digest | None
    eligible: bool
    eligibility_policy_version: Literal["candidate-eligibility-v1"]
    outcome: _TerminalOutcome
    terminal_summary_digest: Digest

    @model_validator(mode="after")
    def validate_terminal_matrix(self) -> CandidateTerminalSummaryV1:
        execution = self.candidate_execution_authority
        if (
            self.workflow_spec_authority != execution.workflow_spec_authority
            or self.eligibility_policy_version
            != execution.eligibility_policy_version
            or self.eligibility_policy_version != ELIGIBILITY_POLICY_VERSION
        ):
            raise ValueError("terminal authority or policy disagrees")
        if (self.package_identity is None) != (self.package_digest is None):
            raise ValueError("terminal package identity is incomplete")
        if (
            self.package_identity is not None
            and self.package_digest != self.package_identity.package_digest
        ):
            raise ValueError("terminal package identities disagree")
        if (self.validation_report_digest is None) != (
            self.validation_error_count is None
        ):
            raise ValueError("terminal validation evidence is incomplete")

        empty_post_qualification = (
            self.generator_outcome_evidence is None
            and self.generated_artifact_identity is None
            and self.package_identity is None
            and self.validation_report_digest is None
            and self.review_attestation_digest is None
            and self.review_disposition.status
            == "review_not_reached_generation_unsuccessful"
        )
        if self.outcome == "qualification_rejected":
            if (
                self.qualification_passed
                or self.lineage_resolution.status
                != "not_evaluated_qualification_rejected"
                or not empty_post_qualification
            ):
                raise ValueError("qualification rejection evidence is inconsistent")
        else:
            if not self.qualification_passed:
                raise ValueError("post-qualification branch requires qualification")
            if self.outcome == "lineage_rejected":
                if (
                    self.lineage_resolution.status != "lineage_rejected"
                    or not empty_post_qualification
                ):
                    raise ValueError("lineage rejection evidence is inconsistent")
            elif self.lineage_resolution.status not in {
                "new_lineage",
                "retained_lineage",
            }:
                raise ValueError("post-lineage branch requires resolved lineage")

        generator_failures = {
            "generator_refusal": "refused",
            "generator_incomplete": "incomplete",
            "generator_schema_failure": "schema_invalid",
        }
        if self.outcome in generator_failures:
            if (
                self.generator_outcome_evidence is None
                or self.generator_outcome_evidence.outcome
                != generator_failures[self.outcome]
                or self.generated_artifact_identity is not None
                or self.package_identity is not None
                or self.validation_report_digest is not None
                or self.review_attestation_digest is not None
                or self.review_disposition.status
                != "review_not_reached_generation_unsuccessful"
            ):
                raise ValueError("generator failure evidence is inconsistent")
        elif self.outcome not in {"qualification_rejected", "lineage_rejected"}:
            if (
                self.generator_outcome_evidence is None
                or self.generator_outcome_evidence.outcome != "parsed"
                or self.generated_artifact_identity is None
                or self.generator_outcome_evidence.generated_artifact_identity
                != self.generated_artifact_identity
                or self.package_identity is None
                or self.validation_report_digest is None
            ):
                raise ValueError("post-generation evidence is incomplete")

        review_outcomes = {
            "reviewer_refusal": "reviewer_refusal",
            "reviewer_incomplete": "reviewer_incomplete",
            "reviewer_schema_failure": "reviewer_schema_failure",
            "review_rejected": "review_completed_no",
            "review_low_confidence": "review_completed_low_confidence",
            "eligible_local_candidate": "review_completed_eligible",
        }
        if self.outcome == "validation_rejected":
            if (
                self.validation_error_count is None
                or self.validation_error_count == 0
                or self.review_disposition.status
                != "review_skipped_validation_errors"
                or self.review_attestation_digest is not None
            ):
                raise ValueError("validation rejection evidence is inconsistent")
        elif self.outcome in review_outcomes:
            if (
                self.validation_error_count != 0
                or self.review_disposition.status
                != review_outcomes[self.outcome]
                or self.review_attestation_digest is None
            ):
                raise ValueError("review terminal evidence is inconsistent")

        expected_eligible = self.outcome == "eligible_local_candidate"
        if self.eligible is not expected_eligible:
            raise ValueError("terminal eligibility ownership is inconsistent")
        expected_digest = sha256_digest(
            self.model_dump(
                mode="json",
                exclude_none=False,
                exclude={"terminal_summary_digest"},
            )
        )
        if self.terminal_summary_digest != expected_digest:
            raise ValueError("terminal summary digest mismatch")
        return self


def candidate_terminal_summary(
    *,
    outcome: _TerminalOutcome,
    candidate_execution_authority: CandidateExecutionAuthorityV1,
    qualification_passed: bool,
    qualification_report_digest: Digest,
    lineage_resolution: LineageResolutionV1,
    generator_outcome_evidence: GeneratorOutcomeEvidenceV1 | None,
    generated_artifact_identity: GeneratedArtifactIdentityV1 | None,
    package_identity: PackageIdentityV1 | None,
    validation_report: ValidationReportV1 | None,
    review_disposition: ReviewDispositionV1,
    review_attestation: ReviewAttestationV1 | None,
) -> CandidateTerminalSummaryV1:
    """Construct and validate one exact terminal branch without mutating a package."""

    if type(candidate_execution_authority) is not CandidateExecutionAuthorityV1:
        raise TypeError("terminal summary requires strict execution authority")
    if type(qualification_passed) is not bool:
        raise TypeError("terminal summary requires boolean qualification")
    if type(lineage_resolution) is not LineageResolutionV1:
        raise TypeError("terminal summary requires strict lineage resolution")
    if type(review_disposition) is not ReviewDispositionV1:
        raise TypeError("terminal summary requires strict review disposition")
    optional_types = (
        (
            generator_outcome_evidence,
            GeneratorOutcomeEvidenceV1,
            "generator evidence",
        ),
        (
            generated_artifact_identity,
            GeneratedArtifactIdentityV1,
            "artifact identity",
        ),
        (package_identity, PackageIdentityV1, "package identity"),
        (validation_report, ValidationReportV1, "validation report"),
        (review_attestation, ReviewAttestationV1, "review attestation"),
    )
    for value, expected_type, label in optional_types:
        if value is not None and type(value) is not expected_type:
            raise TypeError(f"terminal summary requires strict {label}")

    execution = candidate_execution_authority
    if (
        generator_outcome_evidence is not None
        and (
            generator_outcome_evidence.configured_generator_model_id
            != execution.configured_generator_model_id
            or generator_outcome_evidence.generator_prompt_version
            != execution.generator_prompt_version
            or generator_outcome_evidence.generator_output_schema_version
            != execution.generator_output_schema_version
            or generator_outcome_evidence.generator_policy_version
            != execution.generator_policy_version
            or generator_outcome_evidence.phase3_producer_version
            != execution.phase3_producer_version
            or generator_outcome_evidence.phase3_profile_version
            != execution.phase3_profile_version
            or generator_outcome_evidence.retry_policy_version
            != execution.retry_policy_version
        )
    ):
        raise ValueError("terminal Generator evidence authority disagrees")
    if validation_report is not None:
        if (
            validation_report.candidate_execution_authority != execution
            or validation_report.workflow_spec_authority
            != execution.workflow_spec_authority
            or validation_report.generated_artifact_identity
            != generated_artifact_identity
            or validation_report.package_identity != package_identity
        ):
            raise ValueError("terminal validation evidence authority disagrees")
    if review_attestation is not None:
        if (
            validation_report is None
            or review_attestation.generated_artifact_identity
            != generated_artifact_identity
            or review_attestation.package_identity != package_identity
            or review_attestation.validation_report_digest
            != validation_report.report_digest
            or review_attestation.configured_reviewer_model_id
            != execution.configured_reviewer_model_id
            or review_attestation.reviewer_prompt_version
            != execution.reviewer_prompt_version
            or review_attestation.reviewer_output_schema_version
            != execution.reviewer_output_schema_version
            or review_attestation.reviewer_policy_version
            != execution.reviewer_policy_version
        ):
            raise ValueError("terminal review attestation authority disagrees")
        expected_disposition = _review_disposition_from_evidence(
            generation_succeeded=True,
            validation_report=validation_report,
            review_result=review_attestation.review_result,
        )
        if review_disposition != expected_disposition:
            raise ValueError("terminal disposition and raw review result disagree")

    values: dict[str, object] = {
        "schema_version": CANDIDATE_TERMINAL_SUMMARY_SCHEMA_VERSION,
        "workflow_spec_authority": execution.workflow_spec_authority,
        "candidate_execution_authority": execution,
        "qualification_passed": qualification_passed,
        "qualification_report_digest": qualification_report_digest,
        "lineage_resolution": lineage_resolution,
        "generator_outcome_evidence": generator_outcome_evidence,
        "generated_artifact_identity": generated_artifact_identity,
        "package_identity": package_identity,
        "package_digest": (
            package_identity.package_digest if package_identity is not None else None
        ),
        "validation_report_digest": (
            validation_report.report_digest if validation_report is not None else None
        ),
        "validation_error_count": (
            validation_report.error_count if validation_report is not None else None
        ),
        "review_disposition": review_disposition,
        "review_attestation_digest": (
            review_attestation.attestation_digest
            if review_attestation is not None
            else None
        ),
        "eligible": outcome == "eligible_local_candidate",
        "eligibility_policy_version": ELIGIBILITY_POLICY_VERSION,
        "outcome": outcome,
    }
    preimage = CandidateTerminalSummaryV1.model_construct(
        **values,
        terminal_summary_digest="sha256:" + ("0" * 64),
    ).model_dump(
        mode="json",
        exclude_none=False,
        exclude={"terminal_summary_digest"},
    )
    return CandidateTerminalSummaryV1(
        **values,
        terminal_summary_digest=sha256_digest(preimage),
    )


def review_attestation_bytes(attestation: ReviewAttestationV1) -> bytes:
    """Return canonical external attestation bytes."""

    if type(attestation) is not ReviewAttestationV1:
        raise TypeError("canonical attestation bytes require strict attestation")
    return canonical_json_bytes(attestation)


def candidate_terminal_summary_bytes(summary: CandidateTerminalSummaryV1) -> bytes:
    """Return canonical external terminal-summary bytes."""

    if type(summary) is not CandidateTerminalSummaryV1:
        raise TypeError("canonical terminal bytes require strict summary")
    return canonical_json_bytes(summary)
