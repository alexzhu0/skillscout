"""Strict semantic-draft, provenance, and frozen-package contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from skillscout.domain.candidate_authority import workflow_spec_authority
from skillscout.domain.extraction import WorkflowSpec
from skillscout.domain.skill_artifacts import (
    GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION,
    GENERATION_DRAFT_SCHEMA_VERSION,
    PACKAGE_IDENTITY_SCHEMA_VERSION,
    PROVENANCE_SCHEMA_VERSION,
    QUOTE_SCHEMA_VERSION,
    RENDERED_MANIFEST_SCHEMA_VERSION,
    RENDERER_VERSION,
    AttributedQuoteV1,
    GeneratedSkillDraft,
    GenerationAuthorityProjectionV1,
    PackageProvenanceV1,
    RenderedFileV1,
    RenderedPackageManifestV1,
    generated_artifact_identity,
    package_digest,
)


def _digest(character: str) -> str:
    return f"sha256:{character * 64}"


def _workflow() -> WorkflowSpec:
    evidence = {
        "path": "README.md",
        "blob_sha": "a" * 40,
        "content_hash": _digest("1"),
        "excerpt": "Collect, validate, and report the bounded workflow inputs.",
        "supports": "The source describes the workflow.",
    }
    return WorkflowSpec.model_validate(
        {
            "schema_version": "workflow-spec-v1",
            "workflow_id": "wf-generation-contract",
            "fingerprint": _digest("2"),
            "fingerprint_version": "wf-fingerprint-v1",
            "title": "Review a bounded workflow",
            "goal": "Turn verified structured inputs into a reviewable report.",
            "applicability": ("When a bounded workflow needs review.",),
            "non_goals": ("Do not publish or execute candidate code.",),
            "preconditions": ("Verified evidence is available.",),
            "inputs": ("A verified WorkflowSpec.",),
            "steps": (
                {"instruction": "Collect the inputs.", "evidence": (evidence,)},
                {"instruction": "Validate the inputs.", "evidence": (evidence,)},
                {"instruction": "Produce the report.", "evidence": (evidence,)},
            ),
            "outputs": ("A reviewable local report.",),
            "failure_modes": ("Reject inconsistent evidence.",),
            "prohibited_actions": ("Never execute source code.",),
            "required_approvals": ("Human approval before publication.",),
            "assumptions": ("Inputs crossed the semantic boundary.",),
            "evidence": (evidence,),
            "confidence": 0.91,
        }
    )


def _draft(**changes: object) -> GeneratedSkillDraft:
    values: dict[str, object] = {
        "schema_version": GENERATION_DRAFT_SCHEMA_VERSION,
        "description": "Review a bounded workflow using deterministic checks.",
        "overview": "Apply a reusable review process to verified structured inputs.",
        "when_to_use": ("A structured workflow requires a local review.",),
        "inputs": ("A verified workflow specification.",),
        "steps": (
            "Collect only the declared structured inputs.",
            "Validate each input against the bounded policy.",
            "Produce a local review report for human assessment.",
        ),
        "outputs": ("A deterministic review report.",),
        "failure_handling": ("Stop when required evidence is missing.",),
        "approvals": ("Require human approval before publication.",),
        "limitations": ("This workflow does not execute candidate code.",),
        "references": (),
        "quotes": (),
    }
    values.update(changes)
    return GeneratedSkillDraft.model_validate(values)


def _authority(**changes: object) -> GenerationAuthorityProjectionV1:
    workflow = _workflow()
    authority = workflow_spec_authority(
        workflow_spec=workflow,
        phase2_extractor_output_hash=_digest("3"),
        phase2_verified_chain_anchor=_digest("4"),
    )
    values: dict[str, object] = {
        "schema_version": "generation-authority-v1",
        "phase2_run_id": "phase2-run-1",
        "phase2_terminal_summary_digest": _digest("5"),
        "phase2_verified_chain_anchor": _digest("4"),
        "workflow_spec_authority": authority,
        "selected_workflow_fingerprint": workflow.fingerprint,
        "repository_url": "https://github.com/example/repository",
        "repository_id": 12345,
        "exact_commit_sha": "b" * 40,
        "license_spdx": "MIT",
        "lineage_id": _digest("6"),
        "stable_slug": "review-workflow-1234abcd",
        "qualification_report_digest": _digest("7"),
        "qualification_report_schema_version": "qualification-report-v1",
        "qualification_policy_version": "qualification-policy-v1",
        "qualification_threshold_version": "qualification-threshold-v1",
        "configured_generator_model_id": "gpt-generator-configured",
        "actual_generator_model_id": "gpt-generator-actual",
        "generator_prompt_version": "generator-prompt-v1",
        "generator_output_schema_version": GENERATION_DRAFT_SCHEMA_VERSION,
        "generator_policy_version": "generator-policy-v1",
        "renderer_version": RENDERER_VERSION,
        "artifact_schema_version": GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION,
        "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
        "generator_producer_version": "phase3-generator-v1",
        "phase3_profile_version": "phase3-profile-v1",
        "retry_policy_version": "retry-v1",
    }
    values.update(changes)
    return GenerationAuthorityProjectionV1.model_validate(values)


def test_contracts_export_separate_versions_and_renderer_authority() -> None:
    assert GENERATION_DRAFT_SCHEMA_VERSION == "generation-draft-v1"
    assert GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION == "generated-artifact-identity-v1"
    assert PROVENANCE_SCHEMA_VERSION == "skill-provenance-v1"
    assert QUOTE_SCHEMA_VERSION == "attributed-quote-v1"
    assert RENDERED_MANIFEST_SCHEMA_VERSION == "rendered-package-manifest-v1"
    assert PACKAGE_IDENTITY_SCHEMA_VERSION == "package-identity-v1"
    assert RENDERER_VERSION == "skill-renderer-v1"


def test_contracts_are_strict_frozen_and_enforce_quote_boundaries() -> None:
    quote = AttributedQuoteV1(
        schema_version=QUOTE_SCHEMA_VERSION,
        text="q" * 120,
        source_path="README.md",
        commit_sha="b" * 40,
    )
    with pytest.raises(ValidationError):
        AttributedQuoteV1.model_validate(
            {**quote.model_dump(mode="python"), "unknown": "forbidden"}
        )
    with pytest.raises(ValidationError):
        AttributedQuoteV1(
            schema_version=QUOTE_SCHEMA_VERSION,
            text="q" * 121,
            source_path="README.md",
            commit_sha="b" * 40,
        )
    with pytest.raises(ValidationError):
        _draft(quotes=(quote, quote, AttributedQuoteV1(
            schema_version=QUOTE_SCHEMA_VERSION,
            text="x",
            source_path="README.md",
            commit_sha="b" * 40,
        )))
    with pytest.raises(ValidationError):
        quote.text = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "path",
    (
        "/SKILL.md",
        "../SKILL.md",
        "references/../SKILL.md",
        "scripts/run.sh",
        "references/deep/topic.md",
        "REFERENCES/topic.md",
        "assets/tool.bin",
    ),
)
def test_contracts_reject_unsafe_rendered_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        RenderedFileV1(path=path, content=b"text", mode=0o644, is_symlink=False)


def test_contracts_reject_binary_executable_links_and_case_collisions() -> None:
    for values in (
        {"path": "SKILL.md", "content": b"\x00binary", "mode": 0o644, "is_symlink": False},
        {"path": "SKILL.md", "content": b"text", "mode": 0o755, "is_symlink": False},
        {"path": "SKILL.md", "content": b"text", "mode": 0o644, "is_symlink": True},
    ):
        with pytest.raises(ValidationError):
            RenderedFileV1(**values)

    first = RenderedFileV1(
        path="references/topic.md", content=b"one", mode=0o644, is_symlink=False
    )
    second = first.model_copy(update={"path": "references/TOPIC.md"})
    with pytest.raises(ValidationError):
        RenderedPackageManifestV1.from_files((first, second))


def test_contracts_generated_identity_is_semantic_and_authority_sensitive() -> None:
    draft = _draft()
    authority = _authority()
    identity = generated_artifact_identity(draft=draft, authority=authority)
    assert identity.schema_version == GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION
    assert identity.artifact_digest.startswith("sha256:")
    assert "request_id" not in GenerationAuthorityProjectionV1.model_fields
    assert "usage" not in GenerationAuthorityProjectionV1.model_fields
    assert "validator" not in " ".join(GenerationAuthorityProjectionV1.model_fields)
    assert "reviewer" not in " ".join(GenerationAuthorityProjectionV1.model_fields)
    assert "eligibility" not in " ".join(GenerationAuthorityProjectionV1.model_fields)

    changed_draft = _draft(description="A changed semantic description.")
    changed_authority = _authority(actual_generator_model_id="gpt-generator-other")
    assert (
        generated_artifact_identity(draft=changed_draft, authority=authority).artifact_digest
        != identity.artifact_digest
    )
    assert (
        generated_artifact_identity(draft=draft, authority=changed_authority).artifact_digest
        != identity.artifact_digest
    )


def test_contracts_provenance_has_generation_facts_and_no_future_facts() -> None:
    names = set(PackageProvenanceV1.model_fields)
    required = {
        "generated_artifact_identity",
        "workflow_spec_authority",
        "repository_url",
        "repository_id",
        "exact_commit_sha",
        "license_spdx",
        "source_evidence",
        "lineage_id",
        "stable_slug",
        "qualification_report_digest",
        "configured_generator_model_id",
        "actual_generator_model_id",
        "request_id",
        "usage",
        "latency_ms",
    }
    assert required <= names
    assert not any(
        forbidden in name
        for name in names
        for forbidden in ("validator", "reviewer", "eligibility", "terminal", "package_digest")
    )


def test_contracts_package_identity_binds_path_hash_mode_and_size() -> None:
    skill = RenderedFileV1(
        path="SKILL.md", content=b"skill", mode=0o644, is_symlink=False
    )
    provenance = RenderedFileV1(
        path="references/provenance.json",
        content=b"{}",
        mode=0o644,
        is_symlink=False,
    )
    manifest = RenderedPackageManifestV1.from_files((skill, provenance))
    identity = package_digest(manifest)
    assert identity.schema_version == PACKAGE_IDENTITY_SCHEMA_VERSION
    assert identity.package_digest.startswith("sha256:")
    assert "package_digest" not in RenderedPackageManifestV1.model_fields

    changed = RenderedFileV1(
        path="references/provenance.json",
        content=b"{\"changed\":true}",
        mode=0o644,
        is_symlink=False,
    )
    assert (
        package_digest(RenderedPackageManifestV1.from_files((skill, changed))).package_digest
        != identity.package_digest
    )
