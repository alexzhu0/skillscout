"""Complete Phase 3 candidate authority contracts."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from skillscout.domain.candidate_authority import (
    CANDIDATE_DESCRIPTOR_SCHEMA_VERSION,
    CANDIDATE_EXECUTION_AUTHORITY_SCHEMA_VERSION,
    WORKFLOW_SPEC_AUTHORITY_SCHEMA_VERSION,
    CandidateExecutionAuthorityV1,
    CandidateSubjectDescriptorV1,
    WorkflowSpecAuthorityV1,
    candidate_execution_authority,
    workflow_spec_authority,
)
from skillscout.domain.canonical import canonical_json_bytes
from skillscout.domain.extraction import WorkflowSpec


def _digest(character: str) -> str:
    return f"sha256:{character * 64}"


def _workflow(**changes: object) -> WorkflowSpec:
    evidence = {
        "path": "README.md",
        "blob_sha": "a" * 40,
        "content_hash": _digest("1"),
        "excerpt": "Collect the inputs before running the workflow.",
        "supports": "The source describes the input collection step.",
    }
    values: dict[str, object] = {
        "schema_version": "workflow-spec-v1",
        "workflow_id": "wf-1234567890abcdef",
        "fingerprint": _digest("2"),
        "fingerprint_version": "wf-fingerprint-v1",
        "title": "Review an automation workflow",
        "goal": "Turn a bounded workflow into a reviewable result.",
        "applicability": ("When a structured workflow is available.",),
        "non_goals": ("Do not publish the result.",),
        "preconditions": ("The source evidence is verified.",),
        "inputs": ("A verified workflow.",),
        "steps": (
            {
                "instruction": "Collect and validate the workflow inputs.",
                "evidence": (evidence,),
            },
            {
                "instruction": "Produce a bounded review artifact.",
                "evidence": (evidence,),
            },
            {
                "instruction": "Check the artifact before handoff.",
                "evidence": (evidence,),
            },
        ),
        "outputs": ("A reviewable artifact.",),
        "failure_modes": ("Reject missing evidence.",),
        "prohibited_actions": ("Do not execute source code.",),
        "required_approvals": ("Human approval before publication.",),
        "assumptions": ("The repository is public.",),
        "evidence": (evidence,),
        "confidence": 0.91,
    }
    values.update(changes)
    return WorkflowSpec.model_validate(values)


def _workflow_authority(**changes: object) -> WorkflowSpecAuthorityV1:
    values: dict[str, object] = {
        "workflow_spec": _workflow(),
        "phase2_extractor_output_hash": _digest("3"),
        "phase2_verified_chain_anchor": _digest("4"),
    }
    values.update(changes)
    return workflow_spec_authority(**values)


def _execution_kwargs(**changes: object) -> dict[str, object]:
    workflow_authority = _workflow_authority()
    values: dict[str, object] = {
        "workflow_spec_authority": workflow_authority,
        "selected_workflow_fingerprint": workflow_authority.workflow_spec.fingerprint,
        "prior_lineage_binding_digest": None,
        "qualification_policy_version": "qualification-policy-v1",
        "qualification_report_schema_version": "qualification-report-v1",
        "configured_generator_model_id": "gpt-generator-configured",
        "generator_prompt_version": "generator-prompt-v1",
        "generator_output_schema_version": "generator-output-v1",
        "generator_policy_version": "generator-policy-v1",
        "renderer_version": "skill-renderer-v1",
        "artifact_schema_version": "generated-artifact-v1",
        "provenance_schema_version": "skill-provenance-v1",
        "official_validator_distribution": "skills-ref",
        "official_validator_version": "0.1.1",
        "official_validator_distribution_hash": _digest("5"),
        "approved_lock_digest": (
            "sha256:b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004"
        ),
        "custom_validation_policy_version": "skill-validation-policy-v1",
        "validation_report_schema_version": "validation-report-v1",
        "configured_reviewer_model_id": "gpt-reviewer-configured",
        "reviewer_prompt_version": "reviewer-prompt-v1",
        "reviewer_output_schema_version": "reviewer-output-v1",
        "reviewer_policy_version": "reviewer-policy-v1",
        "reviewer_retry_policy_version": "reviewer-bounded-transient-retry-v1",
        "max_reviewer_attempts": 3,
        "eligibility_policy_version": "candidate-eligibility-v1",
        "phase3_producer_version": "phase3-v1",
        "phase3_profile_version": "phase3-profile-v1",
        "retry_policy_version": "retry-v1",
        "runtime_profile_digest": _digest("a"),
    }
    values.update(changes)
    return values


def _revalidate_workflow(
    workflow: WorkflowSpec,
    mutate: Callable[[dict[str, object]], None],
) -> WorkflowSpec:
    values = workflow.model_dump(mode="python")
    mutate(values)
    return WorkflowSpec.model_validate(values)


WORKFLOW_MUTATIONS: tuple[
    tuple[str, Callable[[dict[str, object]], None]], ...
] = (
    ("workflow_id", lambda value: value.__setitem__("workflow_id", "wf-fedcba0987654321")),
    ("fingerprint", lambda value: value.__setitem__("fingerprint", _digest("9"))),
    ("title", lambda value: value.__setitem__("title", "A different workflow title")),
    ("goal", lambda value: value.__setitem__("goal", "A different workflow goal.")),
    ("applicability", lambda value: value.__setitem__("applicability", ("A new use case.",))),
    ("non_goals", lambda value: value.__setitem__("non_goals", ("A new excluded goal.",))),
    (
        "preconditions",
        lambda value: value.__setitem__("preconditions", ("A new precondition.",)),
    ),
    ("inputs", lambda value: value.__setitem__("inputs", ("A different input.",))),
    (
        "step_instruction",
        lambda value: value["steps"][0].__setitem__(  # type: ignore[index,union-attr]
            "instruction", "Use a different first instruction."
        ),
    ),
    (
        "step_evidence_path",
        lambda value: value["steps"][0]["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "path", "docs/workflow.md"
        ),
    ),
    (
        "step_evidence_blob_sha",
        lambda value: value["steps"][0]["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "blob_sha", "b" * 40
        ),
    ),
    (
        "step_evidence_content_hash",
        lambda value: value["steps"][0]["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "content_hash", _digest("8")
        ),
    ),
    (
        "step_evidence_excerpt",
        lambda value: value["steps"][0]["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "excerpt", "A different bounded excerpt."
        ),
    ),
    (
        "step_evidence_supports",
        lambda value: value["steps"][0]["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "supports", "A different support statement."
        ),
    ),
    ("outputs", lambda value: value.__setitem__("outputs", ("A different output.",))),
    (
        "failure_modes",
        lambda value: value.__setitem__("failure_modes", ("A different failure.",)),
    ),
    (
        "prohibited_actions",
        lambda value: value.__setitem__(
            "prohibited_actions", ("A different prohibition.",)
        ),
    ),
    (
        "required_approvals",
        lambda value: value.__setitem__(
            "required_approvals", ("A different approval.",)
        ),
    ),
    (
        "assumptions",
        lambda value: value.__setitem__("assumptions", ("A different assumption.",)),
    ),
    (
        "workflow_evidence_path",
        lambda value: value["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "path", "docs/evidence.md"
        ),
    ),
    (
        "workflow_evidence_blob_sha",
        lambda value: value["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "blob_sha", "c" * 40
        ),
    ),
    (
        "workflow_evidence_content_hash",
        lambda value: value["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "content_hash", _digest("7")
        ),
    ),
    (
        "workflow_evidence_excerpt",
        lambda value: value["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "excerpt", "A changed workflow-level excerpt."
        ),
    ),
    (
        "workflow_evidence_supports",
        lambda value: value["evidence"][0].__setitem__(  # type: ignore[index,union-attr]
            "supports", "A changed workflow support statement."
        ),
    ),
    ("confidence", lambda value: value.__setitem__("confidence", 0.92)),
)


@pytest.mark.parametrize(
    ("field_name", "mutate"),
    WORKFLOW_MUTATIONS,
    ids=[item[0] for item in WORKFLOW_MUTATIONS],
)
def test_every_complete_workflow_field_changes_authority(
    field_name: str,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    original = _workflow_authority()
    changed_workflow = _revalidate_workflow(original.workflow_spec, mutate)

    changed = _workflow_authority(workflow_spec=changed_workflow)

    assert changed.authority_digest != original.authority_digest, field_name


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    (
        ("phase2_extractor_output_hash", _digest("8")),
        ("phase2_verified_chain_anchor", _digest("9")),
    ),
)
def test_every_upstream_source_anchor_changes_workflow_authority(
    field_name: str, changed_value: object
) -> None:
    original = _workflow_authority()
    changed = _workflow_authority(**{field_name: changed_value})
    assert changed.authority_digest != original.authority_digest


EXECUTION_MUTATIONS: tuple[tuple[str, object], ...] = (
    ("prior_lineage_binding_digest", _digest("6")),
    ("qualification_policy_version", "qualification-policy-v2"),
    ("qualification_report_schema_version", "qualification-report-v2"),
    ("configured_generator_model_id", "gpt-generator-configured-v2"),
    ("generator_prompt_version", "generator-prompt-v2"),
    ("generator_output_schema_version", "generator-output-v2"),
    ("generator_policy_version", "generator-policy-v2"),
    ("renderer_version", "skill-renderer-v2"),
    ("artifact_schema_version", "generated-artifact-v2"),
    ("provenance_schema_version", "skill-provenance-v2"),
    ("official_validator_distribution", "skills-ref-renamed"),
    ("official_validator_version", "0.1.2"),
    ("official_validator_distribution_hash", _digest("7")),
    ("approved_lock_digest", _digest("8")),
    ("custom_validation_policy_version", "skill-validation-policy-v2"),
    ("validation_report_schema_version", "validation-report-v2"),
    ("configured_reviewer_model_id", "gpt-reviewer-configured-v2"),
    ("reviewer_prompt_version", "reviewer-prompt-v2"),
    ("reviewer_output_schema_version", "reviewer-output-v2"),
    ("reviewer_policy_version", "reviewer-policy-v2"),
    ("reviewer_retry_policy_version", "reviewer-retry-policy-v2"),
    ("max_reviewer_attempts", 2),
    ("eligibility_policy_version", "candidate-eligibility-v2"),
    ("phase3_producer_version", "phase3-v2"),
    ("phase3_profile_version", "phase3-profile-v2"),
    ("retry_policy_version", "retry-v2"),
    ("runtime_profile_digest", _digest("b")),
)


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    EXECUTION_MUTATIONS,
    ids=[item[0] for item in EXECUTION_MUTATIONS],
)
def test_every_prelookup_execution_field_changes_authority(
    field_name: str, changed_value: object
) -> None:
    original = candidate_execution_authority(**_execution_kwargs())
    changed = candidate_execution_authority(
        **_execution_kwargs(**{field_name: changed_value})
    )
    assert changed.authority_digest != original.authority_digest


def test_complete_workflow_and_selected_fingerprint_independently_change_execution() -> None:
    original = candidate_execution_authority(**_execution_kwargs())
    changed_workflow = _workflow_authority(
        workflow_spec=_workflow(
            fingerprint=_digest("9"),
            workflow_id="wf-fedcba0987654321",
        )
    )
    changed = candidate_execution_authority(
        **_execution_kwargs(
            workflow_spec_authority=changed_workflow,
            selected_workflow_fingerprint=changed_workflow.workflow_spec.fingerprint,
        )
    )
    assert changed.authority_digest != original.authority_digest


def test_renderer_authority_alone_invalidates_reuse_identity() -> None:
    original = candidate_execution_authority(**_execution_kwargs())
    changed = candidate_execution_authority(
        **_execution_kwargs(renderer_version="skill-renderer-v2")
    )
    assert changed.authority_digest != original.authority_digest


def test_eligibility_policy_authority_alone_invalidates_reuse_identity() -> None:
    original = candidate_execution_authority(**_execution_kwargs())
    changed = candidate_execution_authority(
        **_execution_kwargs(eligibility_policy_version="candidate-eligibility-v2")
    )
    assert changed.authority_digest != original.authority_digest


def test_canonical_authority_is_stable_across_mapping_construction_order() -> None:
    kwargs = _execution_kwargs()
    forward = candidate_execution_authority(**kwargs)
    reverse = candidate_execution_authority(**dict(reversed(tuple(kwargs.items()))))

    assert forward == reverse
    assert canonical_json_bytes(forward) == canonical_json_bytes(reverse)
    assert json.loads(canonical_json_bytes(forward))["prior_lineage_binding_digest"] is None


def test_descriptor_carries_one_optional_exact_binding_digest_and_no_workflow() -> None:
    values = {
        "schema_version": CANDIDATE_DESCRIPTOR_SCHEMA_VERSION,
        "phase2_run_id": "phase2-run-1",
        "phase2_profile_version": "phase2-profile-v1",
        "phase2_producer_version": "phase2-v1",
        "extractor_output_hash": _digest("1"),
        "verified_chain_anchor": _digest("2"),
        "selected_workflow_fingerprint": _digest("3"),
        "expected_workflow_spec_authority_digest": _digest("4"),
        "prior_lineage_binding_digest": None,
    }
    without_binding = CandidateSubjectDescriptorV1.model_validate(values)
    with_binding = CandidateSubjectDescriptorV1.model_validate(
        {**values, "prior_lineage_binding_digest": _digest("5")}
    )

    assert without_binding.prior_lineage_binding_digest is None
    assert with_binding.prior_lineage_binding_digest == _digest("5")
    assert "workflow_spec" not in CandidateSubjectDescriptorV1.model_fields
    with pytest.raises(ValidationError):
        CandidateSubjectDescriptorV1.model_validate(
            {**values, "prior_lineage_binding_digests": [_digest("5"), _digest("6")]}
        )


def test_contracts_reject_missing_blank_extra_and_actual_model_fields() -> None:
    execution = candidate_execution_authority(**_execution_kwargs())
    values = execution.model_dump(mode="json")

    assert execution.schema_version == CANDIDATE_EXECUTION_AUTHORITY_SCHEMA_VERSION
    assert execution.workflow_spec_authority.schema_version == (
        WORKFLOW_SPEC_AUTHORITY_SCHEMA_VERSION
    )
    assert not any("actual" in name for name in CandidateExecutionAuthorityV1.model_fields)

    for missing in (
        "configured_generator_model_id",
        "renderer_version",
        "eligibility_policy_version",
        "approved_lock_digest",
    ):
        with pytest.raises(ValidationError):
            CandidateExecutionAuthorityV1.model_validate(
                {key: value for key, value in values.items() if key != missing}
            )
    with pytest.raises(ValidationError):
        CandidateExecutionAuthorityV1.model_validate(
            {**values, "configured_generator_model_id": ""}
        )
    with pytest.raises(ValidationError):
        CandidateExecutionAuthorityV1.model_validate(
            {**values, "actual_generator_model_id": "response-model"}
        )
    with pytest.raises(ValidationError):
        WorkflowSpecAuthorityV1.model_validate(
            {
                **execution.workflow_spec_authority.model_dump(mode="json"),
                "unexpected": True,
            }
        )


def test_hand_authored_or_cross_candidate_authority_is_rejected() -> None:
    execution = candidate_execution_authority(**_execution_kwargs())
    workflow_values = execution.workflow_spec_authority.model_dump(mode="json")
    with pytest.raises(ValidationError):
        WorkflowSpecAuthorityV1.model_validate(
            {**workflow_values, "authority_digest": _digest("0")}
        )

    execution_values = execution.model_dump(mode="json")
    with pytest.raises(ValidationError):
        CandidateExecutionAuthorityV1.model_validate(
            {**execution_values, "selected_workflow_fingerprint": _digest("0")}
        )
    with pytest.raises(ValidationError):
        CandidateExecutionAuthorityV1.model_validate(
            {**execution_values, "authority_digest": _digest("0")}
        )
