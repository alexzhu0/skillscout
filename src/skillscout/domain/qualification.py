"""Pure versioned qualification policy over the verified WorkflowSpec boundary."""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from skillscout.domain.extraction import WorkflowEvidence, WorkflowSpec
from skillscout.domain.models import StrictFrozenModel

QUALIFICATION_CHECK_SCHEMA_VERSION: Final = "qualification-check-v1"
QUALIFICATION_POLICY_VERSION: Final = "qualification-policy-v1"
EVIDENCE_CONFIDENCE_FLOOR: Final = 0.70

QualificationCheckId = Literal[
    "specificity",
    "reusability",
    "verifiability",
    "evidence_sufficiency",
    "unauthorized_execution_safety",
]

QualificationReasonCode = Literal[
    "specificity_incomplete",
    "fewer_than_three_steps",
    "empty_inputs",
    "empty_outputs",
    "reusability_incomplete",
    "source_specific_dependency",
    "verifiability_incomplete",
    "missing_evidence",
    "unknown_evidence_source",
    "evidence_blob_sha_mismatch",
    "evidence_content_hash_mismatch",
    "evidence_insufficient",
    "evidence_confidence_below_floor",
    "safety_controls_incomplete",
    "credential_access",
    "destructive_action",
    "permission_bypass",
    "prompt_injection_residue",
    "approval_required_without_named_step",
    "source_code_execution",
    "dependency_installation",
    "repository_script_invocation",
    "download_and_execute",
    "unauthorized_capability",
]

QUALIFICATION_CHECK_ORDER: Final[tuple[QualificationCheckId, ...]] = (
    "specificity",
    "reusability",
    "verifiability",
    "evidence_sufficiency",
    "unauthorized_execution_safety",
)
QUALIFICATION_CHECK_WEIGHTS: Final[dict[QualificationCheckId, int]] = {
    "specificity": 25,
    "reusability": 20,
    "verifiability": 20,
    "evidence_sufficiency": 25,
    "unauthorized_execution_safety": 10,
}
HARD_FAILURE_REASON_CODES: Final[tuple[QualificationReasonCode, ...]] = (
    "fewer_than_three_steps",
    "empty_inputs",
    "empty_outputs",
    "missing_evidence",
    "unknown_evidence_source",
    "evidence_blob_sha_mismatch",
    "evidence_content_hash_mismatch",
    "credential_access",
    "destructive_action",
    "permission_bypass",
    "prompt_injection_residue",
    "approval_required_without_named_step",
    "source_code_execution",
    "dependency_installation",
    "repository_script_invocation",
    "download_and_execute",
    "unauthorized_capability",
    "evidence_confidence_below_floor",
)
_HARD_FAILURES = frozenset(HARD_FAILURE_REASON_CODES)
_ReasonTuple = Annotated[
    tuple[QualificationReasonCode, ...],
    Field(max_length=len(QualificationReasonCode.__args__)),
]


class QualificationCheckResultV1(StrictFrozenModel):
    """One immutable score decision under the closed qualification policy."""

    schema_version: Literal["qualification-check-v1"]
    policy_version: Literal["qualification-policy-v1"]
    check_id: QualificationCheckId
    weight: Annotated[int, Field(ge=1, le=100)]
    awarded_points: Annotated[int, Field(ge=0, le=100)]
    passed: bool
    hard_failure: bool
    reason_codes: _ReasonTuple

    @model_validator(mode="after")
    def validate_check_result(self) -> QualificationCheckResultV1:
        expected_weight = QUALIFICATION_CHECK_WEIGHTS[self.check_id]
        if self.weight != expected_weight or self.awarded_points > self.weight:
            raise ValueError("qualification check score is inconsistent")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("qualification check reasons must be unique")
        expected_reasons = tuple(
            reason
            for reason in QualificationReasonCode.__args__
            if reason in self.reason_codes
        )
        if self.reason_codes != expected_reasons:
            raise ValueError("qualification check reasons are not canonically ordered")
        expected_hard_failure = any(
            reason in _HARD_FAILURES for reason in self.reason_codes
        )
        if self.hard_failure is not expected_hard_failure:
            raise ValueError("qualification hard-failure flag is inconsistent")
        expected_passed = (
            self.awarded_points == self.weight and not self.hard_failure
        )
        if self.passed is not expected_passed:
            raise ValueError("qualification check pass flag is inconsistent")
        return self


def _ordered_reasons(
    reasons: set[QualificationReasonCode],
) -> tuple[QualificationReasonCode, ...]:
    return tuple(
        reason
        for reason in QualificationReasonCode.__args__
        if reason in reasons
    )


def _check(
    *,
    check_id: QualificationCheckId,
    awarded_points: int,
    reasons: set[QualificationReasonCode],
) -> QualificationCheckResultV1:
    ordered_reasons = _ordered_reasons(reasons)
    hard_failure = any(reason in _HARD_FAILURES for reason in ordered_reasons)
    weight = QUALIFICATION_CHECK_WEIGHTS[check_id]
    return QualificationCheckResultV1(
        schema_version=QUALIFICATION_CHECK_SCHEMA_VERSION,
        policy_version=QUALIFICATION_POLICY_VERSION,
        check_id=check_id,
        weight=weight,
        awarded_points=awarded_points,
        passed=awarded_points == weight and not hard_failure,
        hard_failure=hard_failure,
        reason_codes=ordered_reasons,
    )


def _semantic_action_texts(workflow: WorkflowSpec) -> tuple[str, ...]:
    texts = [
        workflow.goal,
        *workflow.applicability,
        *workflow.preconditions,
        *workflow.inputs,
        *(step.instruction for step in workflow.steps),
        *workflow.outputs,
        *workflow.assumptions,
    ]
    return tuple(text.casefold() for text in texts)


def _has_source_specific_dependency(workflow: WorkflowSpec) -> bool:
    semantic_text = "\n".join(
        (workflow.goal, *(step.instruction for step in workflow.steps))
    ).casefold()
    if any(evidence.path.casefold() in semantic_text for evidence in workflow.evidence):
        return True
    return bool(
        re.search(
            r"\b(?:this|source|candidate)\s+repo(?:sitory)?\b"
            r"|\b(?:owner|repo(?:sitory)?)\s*[:=/]",
            semantic_text,
        )
    )


def _evidence_failures(
    workflow: WorkflowSpec,
) -> tuple[
    set[QualificationReasonCode],
    bool,
    bool,
]:
    reasons: set[QualificationReasonCode] = set()
    authoritative = tuple(workflow.evidence)
    registry: dict[str, tuple[WorkflowEvidence, ...]] = {}
    for evidence in authoritative:
        registry[evidence.path] = (*registry.get(evidence.path, ()), evidence)

    if not authoritative or any(not step.evidence for step in workflow.steps):
        reasons.add("missing_evidence")

    all_step_evidence_present = bool(workflow.steps) and all(
        step.evidence for step in workflow.steps
    )
    all_references_match = bool(authoritative)
    for step in workflow.steps:
        for evidence in step.evidence:
            candidates = registry.get(evidence.path, ())
            if not candidates:
                reasons.add("unknown_evidence_source")
                all_references_match = False
                continue
            blob_matches = tuple(
                candidate
                for candidate in candidates
                if candidate.blob_sha == evidence.blob_sha
            )
            if not blob_matches:
                reasons.add("evidence_blob_sha_mismatch")
                all_references_match = False
            content_matches = tuple(
                candidate
                for candidate in candidates
                if candidate.content_hash == evidence.content_hash
            )
            if not content_matches:
                reasons.add("evidence_content_hash_mismatch")
                all_references_match = False
            if not any(
                candidate.blob_sha == evidence.blob_sha
                and candidate.content_hash == evidence.content_hash
                for candidate in candidates
            ):
                all_references_match = False
    return reasons, all_step_evidence_present, all_references_match


_CREDENTIAL_ACCESS = re.compile(
    r"\b(?:access|read|retrieve|load|use|expose|print|log)\b.{0,48}"
    r"\b(?:credential|secret|api[ _-]?key|token|password)s?\b"
)
_DESTRUCTIVE_ACTION = re.compile(
    r"\b(?:delete|destroy|wipe|erase|truncate|drop)\b.{0,48}"
    r"\b(?:record|data|database|table|file|branch|resource|environment)s?\b"
)
_PERMISSION_BYPASS = re.compile(
    r"\b(?:bypass|circumvent|disable|override|skip)\b.{0,48}"
    r"\b(?:permission|approval|authorization|access control|safeguard|ruleset)s?\b"
)
_INJECTION_RESIDUE = re.compile(
    r"\bignore (?:all |any )?(?:previous|prior|system|developer) instructions?\b"
    r"|\b(?:reveal|print|expose)\b.{0,32}\b(?:system prompt|developer message)\b"
    r"|\bjailbreak\b"
)
_SOURCE_EXECUTION = re.compile(
    r"\b(?:execute|run|import|build|compile)\b.{0,64}"
    r"\b(?:candidate|source|repository|repo)\b.{0,24}"
    r"\b(?:code|package|project)\b"
)
_DEPENDENCY_INSTALL = re.compile(
    r"\b(?:pip|npm|pnpm|yarn|uv|cargo)\s+(?:install|add)\b"
    r"|\binstall\b.{0,32}\b(?:dependencies|dependency|packages|package)\b"
)
_REPOSITORY_SCRIPT = re.compile(
    r"\b(?:execute|run|invoke)\b.{0,64}"
    r"(?:\b(?:candidate|source|repository|repo)\b.{0,24}\b(?:script|tool)\b"
    r"|(?:^|[\s`])(?:\./)?scripts?/[A-Za-z0-9_.\-/]+)"
)
_DOWNLOAD_EXECUTE = re.compile(
    r"\b(?:download|fetch|curl|wget)\b.{0,96}\b(?:execute|run|source|shell)\b"
)
_UNAUTHORIZED_CAPABILITY = re.compile(
    r"\bpush directly\b.{0,48}\b(?:default|main|master|protected) branch\b"
    r"|\bauto(?:matically)?[ -]?(?:merge|approve|publish|release)\b"
    r"|\bmodify\b.{0,32}\brulesets?\b"
    r"|\bmark\b.{0,32}\bready for review\b"
    r"|\bclone\b.{0,32}\b(?:candidate|source) repo(?:sitory)?\b"
)
_SIDE_EFFECT = re.compile(
    r"\b(?:publish|deploy|upload|send|push|merge|release|delete|destroy|"
    r"modify|write|approve|mark ready)\b"
)
_NAMED_APPROVAL = re.compile(
    r"\b(?:human|reviewer|operator|owner|maintainer|security|team)\b.{0,48}"
    r"\b(?:approval|authorization|consent)\b"
    r"|\b(?:approval|authorization|consent)\b.{0,48}"
    r"\b(?:human|reviewer|operator|owner|maintainer|security|team)\b"
)


def _safety_failures(workflow: WorkflowSpec) -> set[QualificationReasonCode]:
    reasons: set[QualificationReasonCode] = set()
    texts = _semantic_action_texts(workflow)
    joined = "\n".join(texts)
    patterns: tuple[
        tuple[QualificationReasonCode, re.Pattern[str]], ...
    ] = (
        ("credential_access", _CREDENTIAL_ACCESS),
        ("destructive_action", _DESTRUCTIVE_ACTION),
        ("permission_bypass", _PERMISSION_BYPASS),
        ("prompt_injection_residue", _INJECTION_RESIDUE),
        ("source_code_execution", _SOURCE_EXECUTION),
        ("dependency_installation", _DEPENDENCY_INSTALL),
        ("repository_script_invocation", _REPOSITORY_SCRIPT),
        ("download_and_execute", _DOWNLOAD_EXECUTE),
        ("unauthorized_capability", _UNAUTHORIZED_CAPABILITY),
    )
    for reason, pattern in patterns:
        if pattern.search(joined):
            reasons.add(reason)

    side_effect_present = any(_SIDE_EFFECT.search(text) for text in texts)
    named_approval_step = any(
        _NAMED_APPROVAL.search(step.instruction.casefold())
        for step in workflow.steps
    )
    if side_effect_present and not named_approval_step:
        reasons.add("approval_required_without_named_step")
    return reasons


def evaluate_qualification_checks(
    workflow: WorkflowSpec,
) -> tuple[QualificationCheckResultV1, ...]:
    """Evaluate the fixed policy without I/O, configuration, tools, or model use."""

    if not isinstance(workflow, WorkflowSpec):
        raise TypeError("qualification requires a WorkflowSpec")

    specificity_reasons: set[QualificationReasonCode] = set()
    specificity_points = 0
    if workflow.goal:
        specificity_points += 5
    else:
        specificity_reasons.add("specificity_incomplete")
    if len(workflow.steps) >= 3:
        specificity_points += 10
    else:
        specificity_reasons.add("fewer_than_three_steps")
    if workflow.inputs:
        specificity_points += 5
    else:
        specificity_reasons.add("empty_inputs")
    if workflow.outputs:
        specificity_points += 5
    else:
        specificity_reasons.add("empty_outputs")

    reusability_reasons: set[QualificationReasonCode] = set()
    reusability_points = 0
    for values in (
        workflow.applicability,
        workflow.preconditions,
        workflow.non_goals,
    ):
        if values:
            reusability_points += 5
        else:
            reusability_reasons.add("reusability_incomplete")
    if _has_source_specific_dependency(workflow):
        reusability_reasons.add("source_specific_dependency")
    else:
        reusability_points += 5

    evidence_reasons, all_step_evidence_present, all_references_match = (
        _evidence_failures(workflow)
    )
    verifiability_reasons = set(evidence_reasons)
    verifiability_points = 0
    if workflow.failure_modes:
        verifiability_points += 5
    else:
        verifiability_reasons.add("verifiability_incomplete")
    if all_step_evidence_present:
        verifiability_points += 5
    else:
        verifiability_reasons.add("verifiability_incomplete")
    if workflow.evidence:
        verifiability_points += 5
    else:
        verifiability_reasons.add("verifiability_incomplete")
    if all_references_match:
        verifiability_points += 5
    else:
        verifiability_reasons.add("verifiability_incomplete")

    sufficiency_reasons = set(evidence_reasons)
    sufficiency_points = 0
    if {evidence.path for evidence in workflow.evidence}:
        sufficiency_points += 5
    else:
        sufficiency_reasons.add("evidence_insufficient")
    if all_step_evidence_present:
        sufficiency_points += 10
    else:
        sufficiency_reasons.add("evidence_insufficient")
    all_evidence = (
        *workflow.evidence,
        *(evidence for step in workflow.steps for evidence in step.evidence),
    )
    if all_evidence and all(evidence.supports for evidence in all_evidence):
        sufficiency_points += 5
    else:
        sufficiency_reasons.add("evidence_insufficient")
    if all_references_match:
        sufficiency_points += 5
    else:
        sufficiency_reasons.add("evidence_insufficient")
    if workflow.confidence < EVIDENCE_CONFIDENCE_FLOOR:
        sufficiency_points -= 5
        sufficiency_reasons.add("evidence_confidence_below_floor")

    safety_reasons = _safety_failures(workflow)
    safety_points = 0
    if workflow.prohibited_actions:
        safety_points += 5
    else:
        safety_reasons.add("safety_controls_incomplete")
    side_effect_present = any(
        _SIDE_EFFECT.search(text) for text in _semantic_action_texts(workflow)
    )
    named_approval_step = any(
        _NAMED_APPROVAL.search(step.instruction.casefold())
        for step in workflow.steps
    )
    if not side_effect_present or named_approval_step:
        safety_points += 5
    else:
        safety_reasons.add("safety_controls_incomplete")

    return (
        _check(
            check_id="specificity",
            awarded_points=specificity_points,
            reasons=specificity_reasons,
        ),
        _check(
            check_id="reusability",
            awarded_points=reusability_points,
            reasons=reusability_reasons,
        ),
        _check(
            check_id="verifiability",
            awarded_points=verifiability_points,
            reasons=verifiability_reasons,
        ),
        _check(
            check_id="evidence_sufficiency",
            awarded_points=sufficiency_points,
            reasons=sufficiency_reasons,
        ),
        _check(
            check_id="unauthorized_execution_safety",
            awarded_points=safety_points,
            reasons=safety_reasons,
        ),
    )
