"""Authority-bound Phase 3 lineage resolution."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from skillscout.domain.candidate_authority import (
    LINEAGE_RESOLUTION_SCHEMA_VERSION,
    PRIOR_LINEAGE_BINDING_SCHEMA_VERSION,
    LineageResolutionV1,
    PriorLineageBindingV1,
    VerifiedPriorLineageEvidenceV1,
    derive_new_lineage,
    prior_lineage_binding,
    resolve_lineage,
    verified_prior_lineage_evidence,
    workflow_spec_authority,
)
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.extraction import WorkflowSpec


def _digest(character: str) -> str:
    return f"sha256:{character * 64}"


def _workflow(
    *,
    title: str = "Review a generated workflow",
    evidence_path: str = "README.md",
    goal: str = "Produce a bounded review artifact.",
) -> WorkflowSpec:
    evidence = {
        "path": evidence_path,
        "blob_sha": "a" * 40,
        "content_hash": _digest("1"),
        "excerpt": "Verify the workflow before handing it to a reviewer.",
        "supports": "The source requires a verification step.",
    }
    return WorkflowSpec.model_validate(
        {
            "schema_version": "workflow-spec-v1",
            "workflow_id": "wf-1234567890abcdef",
            "fingerprint": _digest("2"),
            "fingerprint_version": "wf-fingerprint-v1",
            "title": title,
            "goal": goal,
            "applicability": ("When a verified workflow is available.",),
            "non_goals": ("Do not publish automatically.",),
            "preconditions": ("Evidence is verified.",),
            "inputs": ("A workflow.",),
            "steps": (
                {"instruction": "Collect inputs.", "evidence": (evidence,)},
                {"instruction": "Render the result.", "evidence": (evidence,)},
                {"instruction": "Verify the result.", "evidence": (evidence,)},
            ),
            "outputs": ("A review artifact.",),
            "failure_modes": ("Reject missing evidence.",),
            "prohibited_actions": ("Do not execute source code.",),
            "required_approvals": ("Require human publication approval.",),
            "assumptions": ("The repository is public.",),
            "evidence": (evidence,),
            "confidence": 0.9,
        }
    )


def _authority(
    *,
    title: str = "Review a generated workflow",
    evidence_path: str = "README.md",
    goal: str = "Produce a bounded review artifact.",
    anchor: str = "3",
):
    return workflow_spec_authority(
        workflow_spec=_workflow(title=title, evidence_path=evidence_path, goal=goal),
        phase2_extractor_output_hash=_digest(anchor),
        phase2_verified_chain_anchor=_digest("4"),
    )


def _binding_fixture():
    repository_id = 9_876_543
    initial_authority = _authority()
    prior_resolution = derive_new_lineage(
        repository_id=repository_id,
        initial_workflow_spec_authority=initial_authority,
    )
    new_authority = _authority(
        title="A renamed workflow",
        evidence_path="docs/renamed.md",
        goal="Produce a changed bounded review artifact.",
        anchor="5",
    )
    binding = prior_lineage_binding(
        repository_id=repository_id,
        lineage_authority_digest=prior_resolution.lineage_authority_digest,
        lineage_id=prior_resolution.lineage_id,
        stable_slug=prior_resolution.stable_slug,
        prior_package_digest=_digest("6"),
        prior_terminal_summary_digest=_digest("7"),
        new_workflow_spec_authority_digest=new_authority.authority_digest,
        binding_policy_version="lineage-binding-policy-v1",
    )
    evidence = verified_prior_lineage_evidence(
        binding_id=binding.binding_id,
        repository_id=repository_id,
        lineage_authority_digest=prior_resolution.lineage_authority_digest,
        lineage_id=prior_resolution.lineage_id,
        stable_slug=prior_resolution.stable_slug,
        initial_workflow_spec_authority=initial_authority,
        prior_package_digest=binding.prior_package_digest,
        prior_terminal_summary_digest=binding.prior_terminal_summary_digest,
        approval_record_digest=binding.approval_record_digest,
    )
    return repository_id, initial_authority, new_authority, binding, evidence


def _replace_binding(
    binding: PriorLineageBindingV1, **changes: object
) -> PriorLineageBindingV1:
    values = binding.model_dump(mode="python")
    values.update(changes)
    return PriorLineageBindingV1.model_validate(values)


def _replace_evidence(
    evidence: VerifiedPriorLineageEvidenceV1, **changes: object
) -> VerifiedPriorLineageEvidenceV1:
    values = evidence.model_dump(mode="python")
    values.update(changes)
    return VerifiedPriorLineageEvidenceV1.model_validate(values)


def test_new_lineage_uses_only_repository_and_initial_complete_authority() -> None:
    authority = _authority()
    resolution = derive_new_lineage(
        repository_id=9_876_543,
        initial_workflow_spec_authority=authority,
    )
    expected = sha256_digest(
        {
            "lineage_version": "lineage-v1",
            "repository_id": 9_876_543,
            "initial_workflow_spec_authority_digest": authority.authority_digest,
        }
    )

    assert resolution.status == "new_lineage"
    assert resolution.lineage_authority_digest == expected
    assert resolution.lineage_id == expected
    assert resolution.initial_workflow_spec_authority_digest == authority.authority_digest
    assert resolution.reason_codes == ()
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", resolution.stable_slug or "")
    assert len(resolution.stable_slug or "") <= 64
    assert resolution == derive_new_lineage(
        repository_id=9_876_543,
        initial_workflow_spec_authority=authority,
    )


def test_no_binding_never_uses_title_path_or_content_as_matching_authority() -> None:
    repository_id = 9_876_543
    original = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=_authority(),
        prior_bindings=(),
        verified_prior_evidence=(),
        slug_owner_lineage_ids=(),
    )
    changed = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=_authority(
            title="Renamed",
            evidence_path="docs/new-path.md",
            goal="Entirely changed semantic content.",
            anchor="5",
        ),
        prior_bindings=(),
        verified_prior_evidence=(),
        slug_owner_lineage_ids=(),
    )

    assert original.status == changed.status == "new_lineage"
    assert original.lineage_id != changed.lineage_id


def test_one_exact_binding_retains_lineage_despite_title_path_and_content_change() -> None:
    repository_id, _, new_authority, binding, evidence = _binding_fixture()

    resolution = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=new_authority,
        prior_bindings=(binding,),
        verified_prior_evidence=(evidence,),
        slug_owner_lineage_ids=(binding.lineage_id,),
    )

    assert resolution.status == "retained_lineage"
    assert resolution.lineage_id == binding.lineage_id
    assert resolution.stable_slug == binding.stable_slug
    assert resolution.initial_workflow_spec_authority_digest == (
        evidence.initial_workflow_spec_authority.authority_digest
    )


@pytest.mark.parametrize(
    ("field_name", "changed_value", "expected_reason"),
    (
        ("binding_id", _digest("8"), "binding_id_mismatch"),
        ("repository_id", 111, "repository_mismatch"),
        ("lineage_authority_digest", _digest("8"), "lineage_authority_mismatch"),
        ("lineage_id", _digest("8"), "lineage_id_mismatch"),
        ("stable_slug", "another-valid-slug", "slug_mismatch"),
        ("prior_package_digest", _digest("8"), "prior_package_mismatch"),
        (
            "prior_terminal_summary_digest",
            _digest("8"),
            "prior_terminal_summary_mismatch",
        ),
        (
            "new_workflow_spec_authority_digest",
            _digest("8"),
            "binding_target_mismatch",
        ),
        ("binding_policy_version", "lineage-binding-policy-v2", "binding_id_mismatch"),
        ("approval_record_digest", _digest("8"), "approval_record_mismatch"),
    ),
)
def test_every_binding_field_mutation_rejects_without_new_lineage(
    field_name: str, changed_value: object, expected_reason: str
) -> None:
    repository_id, _, new_authority, binding, evidence = _binding_fixture()
    changed = _replace_binding(binding, **{field_name: changed_value})

    resolution = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=new_authority,
        prior_bindings=(changed,),
        verified_prior_evidence=(evidence,),
        slug_owner_lineage_ids=(binding.lineage_id,),
    )

    assert resolution.status == "lineage_rejected"
    assert resolution.lineage_id is None
    assert expected_reason in resolution.reason_codes


@pytest.mark.parametrize(
    ("field_name", "changed_value", "expected_reason"),
    (
        ("binding_id", _digest("8"), "binding_id_mismatch"),
        ("repository_id", 111, "repository_mismatch"),
        ("lineage_authority_digest", _digest("8"), "lineage_authority_mismatch"),
        ("lineage_id", _digest("8"), "lineage_id_mismatch"),
        ("stable_slug", "another-valid-slug", "slug_mismatch"),
        ("prior_package_digest", _digest("8"), "prior_package_mismatch"),
        (
            "prior_terminal_summary_digest",
            _digest("8"),
            "prior_terminal_summary_mismatch",
        ),
        ("approval_record_digest", _digest("8"), "approval_record_mismatch"),
    ),
)
def test_every_verified_prior_evidence_mutation_rejects(
    field_name: str, changed_value: object, expected_reason: str
) -> None:
    repository_id, _, new_authority, binding, evidence = _binding_fixture()
    changed = _replace_evidence(evidence, **{field_name: changed_value})

    resolution = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=new_authority,
        prior_bindings=(binding,),
        verified_prior_evidence=(changed,),
        slug_owner_lineage_ids=(binding.lineage_id,),
    )

    assert resolution.status == "lineage_rejected"
    assert expected_reason in resolution.reason_codes


def test_tampered_initial_authority_rejects() -> None:
    repository_id, _, new_authority, binding, evidence = _binding_fixture()
    changed = _replace_evidence(
        evidence,
        initial_workflow_spec_authority=_authority(
            title="Tampered prior title",
            anchor="9",
        ),
    )

    resolution = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=new_authority,
        prior_bindings=(binding,),
        verified_prior_evidence=(changed,),
        slug_owner_lineage_ids=(binding.lineage_id,),
    )

    assert resolution.status == "lineage_rejected"
    assert "initial_authority_mismatch" in resolution.reason_codes


@pytest.mark.parametrize(
    ("bindings_mode", "evidence_mode", "expected_reason"),
    (
        ("duplicate", "single", "duplicate_binding_id"),
        ("multiple", "single", "multiple_bindings"),
        ("single", "none", "missing_verified_evidence"),
        ("single", "multiple", "ambiguous_verified_evidence"),
    ),
)
def test_duplicate_multiple_and_ambiguous_candidates_close(
    bindings_mode: str, evidence_mode: str, expected_reason: str
) -> None:
    repository_id, _, new_authority, binding, evidence = _binding_fixture()
    second_binding = _replace_binding(
        binding,
        binding_id=_digest("9"),
        approval_record_digest=_digest("8"),
    )
    bindings = {
        "single": (binding,),
        "duplicate": (binding, binding),
        "multiple": (binding, second_binding),
    }[bindings_mode]
    evidences = {
        "single": (evidence,),
        "none": (),
        "multiple": (evidence, evidence),
    }[evidence_mode]

    resolution = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=new_authority,
        prior_bindings=bindings,
        verified_prior_evidence=evidences,
        slug_owner_lineage_ids=(binding.lineage_id,),
    )

    assert resolution.status == "lineage_rejected"
    assert expected_reason in resolution.reason_codes


def test_slug_collision_and_ambiguous_ownership_close() -> None:
    repository_id, _, new_authority, binding, evidence = _binding_fixture()

    collision = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=new_authority,
        prior_bindings=(binding,),
        verified_prior_evidence=(evidence,),
        slug_owner_lineage_ids=(_digest("8"),),
    )
    ambiguous = resolve_lineage(
        repository_id=repository_id,
        new_workflow_spec_authority=new_authority,
        prior_bindings=(binding,),
        verified_prior_evidence=(evidence,),
        slug_owner_lineage_ids=(binding.lineage_id, binding.lineage_id),
    )

    assert collision.status == ambiguous.status == "lineage_rejected"
    assert "slug_collision" in collision.reason_codes
    assert "ambiguous_ownership" in ambiguous.reason_codes


def test_binding_and_evidence_are_canonical_strict_records() -> None:
    _, _, _, binding, evidence = _binding_fixture()

    assert binding.schema_version == PRIOR_LINEAGE_BINDING_SCHEMA_VERSION
    assert canonical_json_bytes(binding) == canonical_json_bytes(
        PriorLineageBindingV1.model_validate(binding.model_dump(mode="python"))
    )
    with pytest.raises(ValidationError):
        PriorLineageBindingV1.model_validate(
            {**binding.model_dump(mode="python"), "approved": True}
        )
    with pytest.raises(ValidationError):
        VerifiedPriorLineageEvidenceV1.model_validate(
            {**evidence.model_dump(mode="python"), "stable_slug": ""}
        )


def test_not_evaluated_qualification_rejected_carries_no_identity() -> None:
    valid = LineageResolutionV1(
        schema_version=LINEAGE_RESOLUTION_SCHEMA_VERSION,
        status="not_evaluated_qualification_rejected",
        lineage_authority_digest=None,
        lineage_id=None,
        stable_slug=None,
        initial_workflow_spec_authority_digest=None,
        reason_codes=("qualification_rejected",),
    )
    assert valid.lineage_id is None

    for field_name, changed_value in (
        ("lineage_authority_digest", _digest("1")),
        ("lineage_id", _digest("1")),
        ("stable_slug", "forbidden-slug"),
        ("initial_workflow_spec_authority_digest", _digest("1")),
    ):
        with pytest.raises(ValidationError):
            LineageResolutionV1.model_validate(
                {**valid.model_dump(mode="python"), field_name: changed_value}
            )
