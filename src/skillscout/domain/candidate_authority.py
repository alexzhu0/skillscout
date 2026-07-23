"""Immutable Phase 3 source, execution, and lineage authority contracts."""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Literal

from pydantic import Field, model_validator

from skillscout.domain.canonical import sha256_digest
from skillscout.domain.extraction import WorkflowSpec
from skillscout.domain.models import Digest, StrictFrozenModel

CANDIDATE_DESCRIPTOR_SCHEMA_VERSION = "candidate-subject-descriptor-v1"
WORKFLOW_SPEC_AUTHORITY_SCHEMA_VERSION = "workflow-spec-authority-v1"
PRIOR_LINEAGE_BINDING_SCHEMA_VERSION = "prior-lineage-binding-v1"
LINEAGE_RESOLUTION_SCHEMA_VERSION = "lineage-resolution-v1"
CANDIDATE_EXECUTION_AUTHORITY_SCHEMA_VERSION = "candidate-execution-authority-v1"
VERIFIED_PRIOR_LINEAGE_EVIDENCE_SCHEMA_VERSION = "verified-prior-lineage-evidence-v1"
LINEAGE_VERSION = "lineage-v1"
LINEAGE_APPROVAL_RECORD_SCHEMA_VERSION = "lineage-approval-record-v1"

_Identifier = Annotated[str, Field(min_length=1, max_length=512)]
_Version = Annotated[str, Field(min_length=1, max_length=128)]
_RepositoryId = Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
_StableSlug = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
_LineageReason = Literal[
    "approval_record_mismatch",
    "ambiguous_ownership",
    "ambiguous_verified_evidence",
    "binding_id_mismatch",
    "binding_target_mismatch",
    "duplicate_binding_id",
    "evidence_without_binding",
    "initial_authority_mismatch",
    "lineage_authority_mismatch",
    "lineage_id_mismatch",
    "missing_verified_evidence",
    "multiple_bindings",
    "prior_package_mismatch",
    "prior_terminal_summary_mismatch",
    "qualification_rejected",
    "repository_mismatch",
    "slug_collision",
    "slug_mismatch",
]
_DistributionName = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
]


class CandidateSubjectDescriptorV1(StrictFrozenModel):
    """One completed Phase 2 run and exactly one selected workflow version."""

    schema_version: Literal["candidate-subject-descriptor-v1"]
    phase2_run_id: _Identifier
    phase2_profile_version: _Version
    phase2_producer_version: _Version
    extractor_output_hash: Digest
    verified_chain_anchor: Digest
    selected_workflow_fingerprint: Digest
    expected_workflow_spec_authority_digest: Digest
    prior_lineage_binding_digest: Digest | None


class WorkflowSpecAuthorityV1(StrictFrozenModel):
    """The complete semantic boundary plus its verified Phase 2 source anchors."""

    schema_version: Literal["workflow-spec-authority-v1"]
    workflow_spec: WorkflowSpec
    phase2_extractor_output_hash: Digest
    phase2_verified_chain_anchor: Digest
    authority_digest: Digest

    @model_validator(mode="after")
    def validate_authority_digest(self) -> WorkflowSpecAuthorityV1:
        expected = sha256_digest(
            self.model_dump(
                mode="json",
                exclude_none=False,
                exclude={"authority_digest"},
            )
        )
        if self.authority_digest != expected:
            raise ValueError("workflow authority digest mismatch")
        return self


def workflow_spec_authority(
    *,
    workflow_spec: WorkflowSpec,
    phase2_extractor_output_hash: Digest,
    phase2_verified_chain_anchor: Digest,
) -> WorkflowSpecAuthorityV1:
    """Construct the complete canonical WorkflowSpec authority."""

    preimage: dict[str, object] = {
        "schema_version": WORKFLOW_SPEC_AUTHORITY_SCHEMA_VERSION,
        "workflow_spec": workflow_spec.model_dump(mode="json", exclude_none=False),
        "phase2_extractor_output_hash": phase2_extractor_output_hash,
        "phase2_verified_chain_anchor": phase2_verified_chain_anchor,
    }
    return WorkflowSpecAuthorityV1(
        schema_version=WORKFLOW_SPEC_AUTHORITY_SCHEMA_VERSION,
        workflow_spec=workflow_spec,
        phase2_extractor_output_hash=phase2_extractor_output_hash,
        phase2_verified_chain_anchor=phase2_verified_chain_anchor,
        authority_digest=sha256_digest(preimage),
    )


class CandidateExecutionAuthorityV1(StrictFrozenModel):
    """Every reuse-sensitive value knowable before the first Phase 3 lookup."""

    schema_version: Literal["candidate-execution-authority-v1"]
    workflow_spec_authority: WorkflowSpecAuthorityV1
    selected_workflow_fingerprint: Digest
    prior_lineage_binding_digest: Digest | None

    qualification_policy_version: _Version
    qualification_report_schema_version: _Version

    configured_generator_model_id: _Identifier
    generator_prompt_version: _Version
    generator_output_schema_version: _Version
    generator_policy_version: _Version

    renderer_version: _Version
    artifact_schema_version: _Version
    provenance_schema_version: _Version

    official_validator_distribution: _DistributionName
    official_validator_version: _Version
    official_validator_distribution_hash: Digest
    approved_lock_digest: Digest
    custom_validation_policy_version: _Version
    validation_report_schema_version: _Version

    configured_reviewer_model_id: _Identifier
    reviewer_prompt_version: _Version
    reviewer_output_schema_version: _Version
    reviewer_policy_version: _Version
    reviewer_retry_policy_version: _Version
    max_reviewer_attempts: Annotated[int, Field(ge=1, le=3)]

    eligibility_policy_version: _Version
    phase3_producer_version: _Version
    phase3_profile_version: _Version
    retry_policy_version: _Version
    runtime_profile_digest: Digest
    authority_digest: Digest

    @model_validator(mode="after")
    def validate_complete_authority(self) -> CandidateExecutionAuthorityV1:
        if (
            self.selected_workflow_fingerprint
            != self.workflow_spec_authority.workflow_spec.fingerprint
        ):
            raise ValueError("selected fingerprint and workflow authority disagree")
        expected = sha256_digest(
            self.model_dump(
                mode="json",
                exclude_none=False,
                exclude={"authority_digest"},
            )
        )
        if self.authority_digest != expected:
            raise ValueError("candidate execution authority digest mismatch")
        return self


def candidate_execution_authority(
    *,
    workflow_spec_authority: WorkflowSpecAuthorityV1,
    selected_workflow_fingerprint: Digest,
    prior_lineage_binding_digest: Digest | None,
    qualification_policy_version: str,
    qualification_report_schema_version: str,
    configured_generator_model_id: str,
    generator_prompt_version: str,
    generator_output_schema_version: str,
    generator_policy_version: str,
    renderer_version: str,
    artifact_schema_version: str,
    provenance_schema_version: str,
    official_validator_distribution: str,
    official_validator_version: str,
    official_validator_distribution_hash: Digest,
    approved_lock_digest: Digest,
    custom_validation_policy_version: str,
    validation_report_schema_version: str,
    configured_reviewer_model_id: str,
    reviewer_prompt_version: str,
    reviewer_output_schema_version: str,
    reviewer_policy_version: str,
    reviewer_retry_policy_version: str,
    max_reviewer_attempts: int,
    eligibility_policy_version: str,
    phase3_producer_version: str,
    phase3_profile_version: str,
    retry_policy_version: str,
    runtime_profile_digest: Digest,
) -> CandidateExecutionAuthorityV1:
    """Construct the sole complete prelookup Phase 3 execution identity."""

    preimage: dict[str, object] = {
        "schema_version": CANDIDATE_EXECUTION_AUTHORITY_SCHEMA_VERSION,
        "workflow_spec_authority": workflow_spec_authority.model_dump(
            mode="json", exclude_none=False
        ),
        "selected_workflow_fingerprint": selected_workflow_fingerprint,
        "prior_lineage_binding_digest": prior_lineage_binding_digest,
        "qualification_policy_version": qualification_policy_version,
        "qualification_report_schema_version": qualification_report_schema_version,
        "configured_generator_model_id": configured_generator_model_id,
        "generator_prompt_version": generator_prompt_version,
        "generator_output_schema_version": generator_output_schema_version,
        "generator_policy_version": generator_policy_version,
        "renderer_version": renderer_version,
        "artifact_schema_version": artifact_schema_version,
        "provenance_schema_version": provenance_schema_version,
        "official_validator_distribution": official_validator_distribution,
        "official_validator_version": official_validator_version,
        "official_validator_distribution_hash": official_validator_distribution_hash,
        "approved_lock_digest": approved_lock_digest,
        "custom_validation_policy_version": custom_validation_policy_version,
        "validation_report_schema_version": validation_report_schema_version,
        "configured_reviewer_model_id": configured_reviewer_model_id,
        "reviewer_prompt_version": reviewer_prompt_version,
        "reviewer_output_schema_version": reviewer_output_schema_version,
        "reviewer_policy_version": reviewer_policy_version,
        "reviewer_retry_policy_version": reviewer_retry_policy_version,
        "max_reviewer_attempts": max_reviewer_attempts,
        "eligibility_policy_version": eligibility_policy_version,
        "phase3_producer_version": phase3_producer_version,
        "phase3_profile_version": phase3_profile_version,
        "retry_policy_version": retry_policy_version,
        "runtime_profile_digest": runtime_profile_digest,
    }
    return CandidateExecutionAuthorityV1(
        schema_version=CANDIDATE_EXECUTION_AUTHORITY_SCHEMA_VERSION,
        workflow_spec_authority=workflow_spec_authority,
        selected_workflow_fingerprint=selected_workflow_fingerprint,
        prior_lineage_binding_digest=prior_lineage_binding_digest,
        qualification_policy_version=qualification_policy_version,
        qualification_report_schema_version=qualification_report_schema_version,
        configured_generator_model_id=configured_generator_model_id,
        generator_prompt_version=generator_prompt_version,
        generator_output_schema_version=generator_output_schema_version,
        generator_policy_version=generator_policy_version,
        renderer_version=renderer_version,
        artifact_schema_version=artifact_schema_version,
        provenance_schema_version=provenance_schema_version,
        official_validator_distribution=official_validator_distribution,
        official_validator_version=official_validator_version,
        official_validator_distribution_hash=official_validator_distribution_hash,
        approved_lock_digest=approved_lock_digest,
        custom_validation_policy_version=custom_validation_policy_version,
        validation_report_schema_version=validation_report_schema_version,
        configured_reviewer_model_id=configured_reviewer_model_id,
        reviewer_prompt_version=reviewer_prompt_version,
        reviewer_output_schema_version=reviewer_output_schema_version,
        reviewer_policy_version=reviewer_policy_version,
        reviewer_retry_policy_version=reviewer_retry_policy_version,
        max_reviewer_attempts=max_reviewer_attempts,
        eligibility_policy_version=eligibility_policy_version,
        phase3_producer_version=phase3_producer_version,
        phase3_profile_version=phase3_profile_version,
        retry_policy_version=retry_policy_version,
        runtime_profile_digest=runtime_profile_digest,
        authority_digest=sha256_digest(preimage),
    )


class PriorLineageBindingV1(StrictFrozenModel):
    """Canonical target from one prior lineage to one new authority."""

    schema_version: Literal["prior-lineage-binding-v1"]
    binding_id: Digest
    binding_policy_version: _Version
    repository_id: _RepositoryId
    lineage_authority_digest: Digest
    lineage_id: Digest
    stable_slug: _StableSlug
    prior_package_digest: Digest
    prior_terminal_summary_digest: Digest
    new_workflow_spec_authority_digest: Digest


class PriorLineageApprovalRecordV1(StrictFrozenModel):
    """Independent durable human decision over one exact lineage binding."""

    schema_version: Literal["lineage-approval-record-v1"]
    binding_schema_version: Literal["prior-lineage-binding-v1"]
    binding_policy_version: _Version
    binding_digest: Digest
    new_workflow_spec_authority_digest: Digest
    decision: Literal["approved"]
    reviewer_identity: _Identifier
    audit_identity: _Identifier
    approval_record_digest: Digest

    @model_validator(mode="after")
    def validate_record_digest(self) -> PriorLineageApprovalRecordV1:
        expected = sha256_digest(
            self.model_dump(
                mode="json",
                exclude_none=False,
                exclude={"approval_record_digest"},
            )
        )
        if self.approval_record_digest != expected:
            raise ValueError("lineage approval record digest mismatch")
        return self


class VerifiedPriorLineageEvidenceV1(StrictFrozenModel):
    """Narrow projection available only after the prior Phase 3 chain is verified."""

    schema_version: Literal["verified-prior-lineage-evidence-v1"]
    binding_id: Digest
    repository_id: _RepositoryId
    lineage_authority_digest: Digest
    lineage_id: Digest
    stable_slug: _StableSlug
    initial_workflow_spec_authority: WorkflowSpecAuthorityV1
    prior_package_digest: Digest
    prior_terminal_summary_digest: Digest
    approval_record: PriorLineageApprovalRecordV1
    approval_record_digest: Digest

    @model_validator(mode="after")
    def validate_approval_evidence(self) -> VerifiedPriorLineageEvidenceV1:
        if self.approval_record_digest != self.approval_record.approval_record_digest:
            raise ValueError("verified lineage approval evidence disagrees")
        return self


class LineageResolutionV1(StrictFrozenModel):
    """One closed lineage decision with no heuristic or external-text reasons."""

    schema_version: Literal["lineage-resolution-v1"]
    status: Literal[
        "new_lineage",
        "retained_lineage",
        "lineage_rejected",
        "not_evaluated_qualification_rejected",
    ]
    lineage_authority_digest: Digest | None
    lineage_id: Digest | None
    stable_slug: _StableSlug | None
    initial_workflow_spec_authority_digest: Digest | None
    reason_codes: Annotated[tuple[_LineageReason, ...], Field(max_length=16)]

    @model_validator(mode="after")
    def validate_resolution_shape(self) -> LineageResolutionV1:
        identity = (
            self.lineage_authority_digest,
            self.lineage_id,
            self.stable_slug,
            self.initial_workflow_spec_authority_digest,
        )
        has_complete_identity = all(value is not None for value in identity)
        has_any_identity = any(value is not None for value in identity)
        if self.status in {"new_lineage", "retained_lineage"}:
            if not has_complete_identity or self.reason_codes:
                raise ValueError("resolved lineage shape is inconsistent")
        elif self.status == "lineage_rejected":
            if has_any_identity or not self.reason_codes:
                raise ValueError("rejected lineage shape is inconsistent")
        elif (
            has_any_identity
            or self.reason_codes != ("qualification_rejected",)
        ):
            raise ValueError("not-evaluated lineage shape is inconsistent")
        return self


def _approval_record_preimage(
    *,
    binding_policy_version: str,
    binding_digest: Digest,
    new_workflow_spec_authority_digest: Digest,
    decision: Literal["approved"],
    reviewer_identity: str,
    audit_identity: str,
) -> dict[str, object]:
    return {
        "schema_version": LINEAGE_APPROVAL_RECORD_SCHEMA_VERSION,
        "binding_schema_version": PRIOR_LINEAGE_BINDING_SCHEMA_VERSION,
        "binding_policy_version": binding_policy_version,
        "binding_digest": binding_digest,
        "new_workflow_spec_authority_digest": new_workflow_spec_authority_digest,
        "decision": decision,
        "reviewer_identity": reviewer_identity,
        "audit_identity": audit_identity,
    }


def prior_lineage_approval_record_digest(
    *,
    binding_policy_version: str,
    binding_digest: Digest,
    new_workflow_spec_authority_digest: Digest,
    decision: Literal["approved"],
    reviewer_identity: str,
    audit_identity: str,
) -> str:
    """Digest one independent affirmative human decision."""

    return sha256_digest(
        _approval_record_preimage(
            binding_policy_version=binding_policy_version,
            binding_digest=binding_digest,
            new_workflow_spec_authority_digest=new_workflow_spec_authority_digest,
            decision=decision,
            reviewer_identity=reviewer_identity,
            audit_identity=audit_identity,
        )
    )


def prior_lineage_approval_record(
    *,
    binding_policy_version: str,
    binding_digest: Digest,
    new_workflow_spec_authority_digest: Digest,
    decision: Literal["approved"],
    reviewer_identity: str,
    audit_identity: str,
) -> PriorLineageApprovalRecordV1:
    """Construct an independently supplied human approval artifact."""

    values = _approval_record_preimage(
        binding_policy_version=binding_policy_version,
        binding_digest=binding_digest,
        new_workflow_spec_authority_digest=new_workflow_spec_authority_digest,
        decision=decision,
        reviewer_identity=reviewer_identity,
        audit_identity=audit_identity,
    )
    return PriorLineageApprovalRecordV1(
        **values,
        approval_record_digest=sha256_digest(values),
    )


def _binding_preimage(
    *,
    binding_policy_version: str,
    repository_id: int,
    lineage_authority_digest: Digest,
    lineage_id: Digest,
    stable_slug: str,
    prior_package_digest: Digest,
    prior_terminal_summary_digest: Digest,
    new_workflow_spec_authority_digest: Digest,
) -> dict[str, object]:
    return {
        "schema_version": PRIOR_LINEAGE_BINDING_SCHEMA_VERSION,
        "binding_policy_version": binding_policy_version,
        "repository_id": repository_id,
        "lineage_authority_digest": lineage_authority_digest,
        "lineage_id": lineage_id,
        "stable_slug": stable_slug,
        "prior_package_digest": prior_package_digest,
        "prior_terminal_summary_digest": prior_terminal_summary_digest,
        "new_workflow_spec_authority_digest": new_workflow_spec_authority_digest,
    }


def prior_lineage_binding(
    *,
    binding_policy_version: str,
    repository_id: int,
    lineage_authority_digest: Digest,
    lineage_id: Digest,
    stable_slug: str,
    prior_package_digest: Digest,
    prior_terminal_summary_digest: Digest,
    new_workflow_spec_authority_digest: Digest,
) -> PriorLineageBindingV1:
    """Construct a canonical prior-lineage target without approval evidence."""

    preimage = _binding_preimage(
        binding_policy_version=binding_policy_version,
        repository_id=repository_id,
        lineage_authority_digest=lineage_authority_digest,
        lineage_id=lineage_id,
        stable_slug=stable_slug,
        prior_package_digest=prior_package_digest,
        prior_terminal_summary_digest=prior_terminal_summary_digest,
        new_workflow_spec_authority_digest=new_workflow_spec_authority_digest,
    )
    return PriorLineageBindingV1(
        schema_version=PRIOR_LINEAGE_BINDING_SCHEMA_VERSION,
        binding_id=sha256_digest(preimage),
        binding_policy_version=binding_policy_version,
        repository_id=repository_id,
        lineage_authority_digest=lineage_authority_digest,
        lineage_id=lineage_id,
        stable_slug=stable_slug,
        prior_package_digest=prior_package_digest,
        prior_terminal_summary_digest=prior_terminal_summary_digest,
        new_workflow_spec_authority_digest=new_workflow_spec_authority_digest,
    )


def prior_lineage_binding_digest(binding: PriorLineageBindingV1) -> str:
    """Recompute the canonical digest one descriptor may carry."""

    return sha256_digest(
        _binding_preimage(
            binding_policy_version=binding.binding_policy_version,
            repository_id=binding.repository_id,
            lineage_authority_digest=binding.lineage_authority_digest,
            lineage_id=binding.lineage_id,
            stable_slug=binding.stable_slug,
            prior_package_digest=binding.prior_package_digest,
            prior_terminal_summary_digest=binding.prior_terminal_summary_digest,
            new_workflow_spec_authority_digest=(
                binding.new_workflow_spec_authority_digest
            ),
        )
    )


def verified_prior_lineage_evidence(
    *,
    binding_id: Digest,
    repository_id: int,
    lineage_authority_digest: Digest,
    lineage_id: Digest,
    stable_slug: str,
    initial_workflow_spec_authority: WorkflowSpecAuthorityV1,
    prior_package_digest: Digest,
    prior_terminal_summary_digest: Digest,
    approval_record: PriorLineageApprovalRecordV1,
) -> VerifiedPriorLineageEvidenceV1:
    """Construct the narrow projection returned by a future verified state adapter."""

    return VerifiedPriorLineageEvidenceV1(
        schema_version=VERIFIED_PRIOR_LINEAGE_EVIDENCE_SCHEMA_VERSION,
        binding_id=binding_id,
        repository_id=repository_id,
        lineage_authority_digest=lineage_authority_digest,
        lineage_id=lineage_id,
        stable_slug=stable_slug,
        initial_workflow_spec_authority=initial_workflow_spec_authority,
        prior_package_digest=prior_package_digest,
        prior_terminal_summary_digest=prior_terminal_summary_digest,
        approval_record=approval_record,
        approval_record_digest=approval_record.approval_record_digest,
    )


def _lineage_digest(
    *,
    repository_id: int,
    initial_workflow_spec_authority_digest: Digest,
) -> str:
    return sha256_digest(
        {
            "lineage_version": LINEAGE_VERSION,
            "repository_id": repository_id,
            "initial_workflow_spec_authority_digest": (
                initial_workflow_spec_authority_digest
            ),
        }
    )


def _stable_slug(*, title: str, lineage_id: Digest) -> str:
    normalized = unicodedata.normalize("NFKD", title).encode(
        "ascii", errors="ignore"
    ).decode("ascii")
    words = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    base = (words or "skill")[:54].rstrip("-") or "skill"
    return f"{base}-{lineage_id.removeprefix('sha256:')[:8]}"


def derive_new_lineage(
    *,
    repository_id: int,
    initial_workflow_spec_authority: WorkflowSpecAuthorityV1,
) -> LineageResolutionV1:
    """Derive a deterministic lineage from repository ID and initial authority."""

    if type(repository_id) is not int or not 1 <= repository_id <= 9_223_372_036_854_775_807:
        raise ValueError("repository id is outside the closed lineage contract")
    lineage_id = _lineage_digest(
        repository_id=repository_id,
        initial_workflow_spec_authority_digest=(
            initial_workflow_spec_authority.authority_digest
        ),
    )
    return LineageResolutionV1(
        schema_version=LINEAGE_RESOLUTION_SCHEMA_VERSION,
        status="new_lineage",
        lineage_authority_digest=lineage_id,
        lineage_id=lineage_id,
        stable_slug=_stable_slug(
            title=initial_workflow_spec_authority.workflow_spec.title,
            lineage_id=lineage_id,
        ),
        initial_workflow_spec_authority_digest=(
            initial_workflow_spec_authority.authority_digest
        ),
        reason_codes=(),
    )


def _lineage_rejected(*reasons: _LineageReason) -> LineageResolutionV1:
    ordered = tuple(dict.fromkeys(reasons))
    return LineageResolutionV1(
        schema_version=LINEAGE_RESOLUTION_SCHEMA_VERSION,
        status="lineage_rejected",
        lineage_authority_digest=None,
        lineage_id=None,
        stable_slug=None,
        initial_workflow_spec_authority_digest=None,
        reason_codes=ordered,
    )


def _slug_ownership_reasons(
    *,
    expected_lineage_id: Digest,
    slug_owner_lineage_ids: tuple[Digest, ...],
) -> tuple[_LineageReason, ...]:
    if len(slug_owner_lineage_ids) > 1:
        return ("ambiguous_ownership",)
    if slug_owner_lineage_ids and slug_owner_lineage_ids[0] != expected_lineage_id:
        return ("slug_collision",)
    return ()


def resolve_lineage(
    *,
    repository_id: int,
    new_workflow_spec_authority: WorkflowSpecAuthorityV1,
    prior_bindings: tuple[PriorLineageBindingV1, ...],
    verified_prior_evidence: tuple[VerifiedPriorLineageEvidenceV1, ...],
    slug_owner_lineage_ids: tuple[Digest, ...],
) -> LineageResolutionV1:
    """Resolve only a new lineage or one exact fully reverified prior binding."""

    if not prior_bindings:
        if verified_prior_evidence:
            return _lineage_rejected("evidence_without_binding")
        resolution = derive_new_lineage(
            repository_id=repository_id,
            initial_workflow_spec_authority=new_workflow_spec_authority,
        )
        ownership_reasons = _slug_ownership_reasons(
            expected_lineage_id=resolution.lineage_id,
            slug_owner_lineage_ids=slug_owner_lineage_ids,
        )
        if ownership_reasons:
            return _lineage_rejected(*ownership_reasons)
        return resolution

    binding_ids = tuple(binding.binding_id for binding in prior_bindings)
    if len(set(binding_ids)) != len(binding_ids):
        return _lineage_rejected("duplicate_binding_id")
    if len(prior_bindings) != 1:
        return _lineage_rejected("multiple_bindings")
    if not verified_prior_evidence:
        return _lineage_rejected("missing_verified_evidence")
    if len(verified_prior_evidence) != 1:
        return _lineage_rejected("ambiguous_verified_evidence")

    binding = prior_bindings[0]
    evidence = verified_prior_evidence[0]
    approval = evidence.approval_record
    expected_binding_id = prior_lineage_binding_digest(binding)
    recomputed_initial_lineage = _lineage_digest(
        repository_id=evidence.repository_id,
        initial_workflow_spec_authority_digest=(
            evidence.initial_workflow_spec_authority.authority_digest
        ),
    )

    reasons: list[_LineageReason] = []

    def note(reason: _LineageReason) -> None:
        if reason not in reasons:
            reasons.append(reason)

    if (
        binding.binding_id != expected_binding_id
        or evidence.binding_id != binding.binding_id
    ):
        note("binding_id_mismatch")
    if (
        binding.repository_id != repository_id
        or evidence.repository_id != repository_id
        or evidence.repository_id != binding.repository_id
    ):
        note("repository_mismatch")
    if (
        binding.new_workflow_spec_authority_digest
        != new_workflow_spec_authority.authority_digest
    ):
        note("binding_target_mismatch")
    if (
        approval.binding_digest != binding.binding_id
        or approval.binding_policy_version != binding.binding_policy_version
        or approval.new_workflow_spec_authority_digest
        != binding.new_workflow_spec_authority_digest
        or approval.decision != "approved"
        or evidence.approval_record_digest != approval.approval_record_digest
    ):
        note("approval_record_mismatch")
    if (
        binding.lineage_authority_digest != evidence.lineage_authority_digest
        or binding.lineage_authority_digest != recomputed_initial_lineage
    ):
        note("lineage_authority_mismatch")
    if (
        binding.lineage_id != evidence.lineage_id
        or binding.lineage_id != recomputed_initial_lineage
    ):
        note("lineage_id_mismatch")
    if (
        evidence.lineage_authority_digest != recomputed_initial_lineage
        or evidence.lineage_id != recomputed_initial_lineage
    ):
        note("initial_authority_mismatch")
    if binding.stable_slug != evidence.stable_slug:
        note("slug_mismatch")
    if binding.prior_package_digest != evidence.prior_package_digest:
        note("prior_package_mismatch")
    if (
        binding.prior_terminal_summary_digest
        != evidence.prior_terminal_summary_digest
    ):
        note("prior_terminal_summary_mismatch")
    for ownership_reason in _slug_ownership_reasons(
        expected_lineage_id=binding.lineage_id,
        slug_owner_lineage_ids=slug_owner_lineage_ids,
    ):
        note(ownership_reason)

    if reasons:
        return _lineage_rejected(*reasons)
    return LineageResolutionV1(
        schema_version=LINEAGE_RESOLUTION_SCHEMA_VERSION,
        status="retained_lineage",
        lineage_authority_digest=binding.lineage_authority_digest,
        lineage_id=binding.lineage_id,
        stable_slug=binding.stable_slug,
        initial_workflow_spec_authority_digest=(
            evidence.initial_workflow_spec_authority.authority_digest
        ),
        reason_codes=(),
    )
