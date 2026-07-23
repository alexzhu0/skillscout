"""Immutable Phase 3 source, execution, and lineage authority contracts."""

from __future__ import annotations

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

_Identifier = Annotated[str, Field(min_length=1, max_length=512)]
_Version = Annotated[str, Field(min_length=1, max_length=128)]
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

    eligibility_policy_version: _Version
    phase3_producer_version: _Version
    phase3_profile_version: _Version
    retry_policy_version: _Version
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
    eligibility_policy_version: str,
    phase3_producer_version: str,
    phase3_profile_version: str,
    retry_policy_version: str,
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
        "eligibility_policy_version": eligibility_policy_version,
        "phase3_producer_version": phase3_producer_version,
        "phase3_profile_version": phase3_profile_version,
        "retry_policy_version": retry_policy_version,
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
        eligibility_policy_version=eligibility_policy_version,
        phase3_producer_version=phase3_producer_version,
        phase3_profile_version=phase3_profile_version,
        retry_policy_version=retry_policy_version,
        authority_digest=sha256_digest(preimage),
    )
