"""Strict semantic generation contracts and deterministic Skill package identity."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from pathlib import PurePosixPath
from pathlib import Path
from typing import Annotated, Callable, Final, Literal

from pydantic import Field, field_validator, model_validator

from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.domain.candidate_authority import WorkflowSpecAuthorityV1
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.extraction import WorkflowEvidence
from skillscout.domain.models import Digest, NonNegativeInt, StrictFrozenModel, TokenUsage

GENERATION_DRAFT_SCHEMA_VERSION: Final = "generation-draft-v1"
GENERATION_AUTHORITY_SCHEMA_VERSION: Final = "generation-authority-v1"
GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION: Final = "generated-artifact-identity-v1"
PROVENANCE_SCHEMA_VERSION: Final = "skill-provenance-v1"
QUOTE_SCHEMA_VERSION: Final = "attributed-quote-v1"
RENDERED_MANIFEST_SCHEMA_VERSION: Final = "rendered-package-manifest-v1"
PACKAGE_IDENTITY_SCHEMA_VERSION: Final = "package-identity-v1"
FROZEN_PACKAGE_SCHEMA_VERSION: Final = "frozen-skill-package-v1"
REFERENCE_SCHEMA_VERSION: Final = "generated-reference-v1"
RENDERED_FILE_SCHEMA_VERSION: Final = "rendered-file-v1"
RENDERER_VERSION: Final = "skill-renderer-v1"

MAX_QUOTE_CHARS: Final = 120
MAX_TOTAL_QUOTE_CHARS: Final = 240
MAX_GENERATED_REFERENCES: Final = 4
MAX_RENDERED_FILE_BYTES: Final = 65_536
MAX_RENDERED_PACKAGE_BYTES: Final = 131_072

_Text = Annotated[str, Field(min_length=1, max_length=4_096)]
_ShortText = Annotated[str, Field(min_length=1, max_length=512)]
_Version = Annotated[str, Field(min_length=1, max_length=128)]
_Identifier = Annotated[str, Field(min_length=1, max_length=512)]
_RepositoryId = Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
_CommitSha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
_Spdx = Annotated[
    str,
    Field(pattern=r"^(?:MIT|Apache-2\.0|BSD-2-Clause|BSD-3-Clause)$"),
]
_StableSlug = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
_ReferenceName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
_TextList = Annotated[tuple[_Text, ...], Field(min_length=1, max_length=64)]


def _relative_source_path(value: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 512
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("source path is outside the closed grammar")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise ValueError("source path is outside the closed grammar")
    return value


def _rendered_path(value: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 256
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("rendered path is outside the closed grammar")
    if value == "SKILL.md":
        return value
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or len(path.parts) != 2
        or path.parts[0] not in {"references", "assets"}
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("rendered path is outside the closed grammar")
    suffix = path.suffix
    allowed = {".md", ".json"} if path.parts[0] == "references" else {
        ".md",
        ".txt",
        ".json",
    }
    if suffix not in allowed or path.name.startswith("."):
        raise ValueError("rendered path is outside the closed grammar")
    return value


def _text_bytes(value: bytes) -> bytes:
    if type(value) is not bytes or not value or len(value) > MAX_RENDERED_FILE_BYTES:
        raise ValueError("rendered content is outside the closed bounds")
    if b"\x00" in value:
        raise ValueError("binary rendered content is forbidden")
    try:
        value.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("binary rendered content is forbidden") from None
    return value


class AttributedQuoteV1(StrictFrozenModel):
    """One optional bounded verbatim quote with exact source attribution."""

    schema_version: Literal["attributed-quote-v1"]
    text: Annotated[str, Field(min_length=1, max_length=MAX_QUOTE_CHARS)]
    source_path: Annotated[str, Field(min_length=1, max_length=512)]
    commit_sha: _CommitSha

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        return _relative_source_path(value)


class GeneratedReferenceV1(StrictFrozenModel):
    """One semantic reference topic; trusted code owns its eventual path."""

    schema_version: Literal["generated-reference-v1"]
    name: _ReferenceName
    title: _ShortText
    body: _Text


class GeneratedSkillDraft(StrictFrozenModel):
    """The model-owned meaning only, with no pathname or permission authority."""

    schema_version: Literal["generation-draft-v1"]
    description: Annotated[str, Field(min_length=1, max_length=1_024)]
    overview: _Text
    when_to_use: _TextList
    inputs: _TextList
    steps: Annotated[tuple[_Text, ...], Field(min_length=1, max_length=64)]
    outputs: _TextList
    failure_handling: _TextList
    approvals: _TextList
    limitations: _TextList
    references: Annotated[
        tuple[GeneratedReferenceV1, ...],
        Field(max_length=MAX_GENERATED_REFERENCES),
    ]
    quotes: Annotated[tuple[AttributedQuoteV1, ...], Field(max_length=8)]

    @model_validator(mode="after")
    def validate_draft_boundaries(self) -> GeneratedSkillDraft:
        if sum(len(quote.text) for quote in self.quotes) > MAX_TOTAL_QUOTE_CHARS:
            raise ValueError("total quote budget exceeded")
        names = tuple(reference.name.casefold() for reference in self.references)
        if len(names) != len(set(names)):
            raise ValueError("reference names collide")
        return self


class GenerationAuthorityProjectionV1(StrictFrozenModel):
    """Only generation-time facts allowed to affect semantic artifact identity."""

    schema_version: Literal["generation-authority-v1"]
    phase2_run_id: _Identifier
    phase2_terminal_summary_digest: Digest
    phase2_verified_chain_anchor: Digest
    workflow_spec_authority: WorkflowSpecAuthorityV1
    selected_workflow_fingerprint: Digest
    repository_url: Annotated[
        str,
        Field(
            min_length=1,
            max_length=512,
            pattern=r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        ),
    ]
    repository_id: _RepositoryId
    exact_commit_sha: _CommitSha
    license_spdx: _Spdx
    lineage_id: Digest
    stable_slug: _StableSlug
    qualification_report_digest: Digest
    qualification_report_schema_version: _Version
    qualification_policy_version: _Version
    qualification_threshold_version: _Version
    configured_generator_model_id: _Identifier
    actual_generator_model_id: _Identifier
    generator_prompt_version: _Version
    generator_output_schema_version: _Version
    generator_policy_version: _Version
    renderer_version: Literal["skill-renderer-v1"]
    artifact_schema_version: Literal["generated-artifact-identity-v1"]
    provenance_schema_version: Literal["skill-provenance-v1"]
    generator_producer_version: _Version
    phase3_profile_version: _Version
    retry_policy_version: _Version

    @model_validator(mode="after")
    def validate_authority_links(self) -> GenerationAuthorityProjectionV1:
        workflow = self.workflow_spec_authority.workflow_spec
        if self.selected_workflow_fingerprint != workflow.fingerprint:
            raise ValueError("selected fingerprint and workflow authority disagree")
        if (
            self.phase2_verified_chain_anchor
            != self.workflow_spec_authority.phase2_verified_chain_anchor
        ):
            raise ValueError("phase two chain anchors disagree")
        if self.generator_output_schema_version != GENERATION_DRAFT_SCHEMA_VERSION:
            raise ValueError("generator output schema authority disagrees")
        return self


class GeneratedArtifactIdentityV1(StrictFrozenModel):
    """External semantic identity, finalized before any rendered path or mode exists."""

    schema_version: Literal["generated-artifact-identity-v1"]
    draft_digest: Digest
    generation_authority_digest: Digest
    artifact_digest: Digest

    @model_validator(mode="after")
    def validate_artifact_digest(self) -> GeneratedArtifactIdentityV1:
        expected = sha256_digest(
            {
                "schema_version": self.schema_version,
                "draft_digest": self.draft_digest,
                "generation_authority_digest": self.generation_authority_digest,
            }
        )
        if self.artifact_digest != expected:
            raise ValueError("generated artifact digest mismatch")
        return self


def generated_artifact_identity(
    *,
    draft: GeneratedSkillDraft,
    authority: GenerationAuthorityProjectionV1,
) -> GeneratedArtifactIdentityV1:
    """Bind canonical model meaning to explicit generation-only authority."""

    if (
        type(draft) is not GeneratedSkillDraft
        or type(authority) is not GenerationAuthorityProjectionV1
    ):
        raise TypeError("generated artifact identity requires strict generation contracts")
    draft_digest = sha256_digest(canonical_json_bytes(draft))
    authority_digest = sha256_digest(canonical_json_bytes(authority))
    preimage = {
        "schema_version": GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION,
        "draft_digest": draft_digest,
        "generation_authority_digest": authority_digest,
    }
    return GeneratedArtifactIdentityV1(
        **preimage,
        artifact_digest=sha256_digest(preimage),
    )


class PackageProvenanceV1(StrictFrozenModel):
    """Complete generation-time provenance; later review facts cannot fit."""

    schema_version: Literal["skill-provenance-v1"]
    generated_artifact_identity: GeneratedArtifactIdentityV1
    generation_authority: GenerationAuthorityProjectionV1
    workflow_spec_authority: WorkflowSpecAuthorityV1
    selected_workflow_fingerprint: Digest
    repository_url: Annotated[str, Field(min_length=1, max_length=512)]
    repository_id: _RepositoryId
    exact_commit_sha: _CommitSha
    license_spdx: _Spdx
    source_evidence: Annotated[
        tuple[WorkflowEvidence, ...],
        Field(min_length=1, max_length=64),
    ]
    quotes: Annotated[tuple[AttributedQuoteV1, ...], Field(max_length=8)]
    phase2_run_id: _Identifier
    phase2_verified_chain_anchor: Digest
    lineage_id: Digest
    stable_slug: _StableSlug
    qualification_report_digest: Digest
    qualification_report_schema_version: _Version
    qualification_policy_version: _Version
    qualification_threshold_version: _Version
    configured_generator_model_id: _Identifier
    actual_generator_model_id: _Identifier
    generator_prompt_version: _Version
    generator_output_schema_version: _Version
    generator_policy_version: _Version
    generator_producer_version: _Version
    phase3_profile_version: _Version
    retry_policy_version: _Version
    renderer_version: Literal["skill-renderer-v1"]
    artifact_schema_version: Literal["generated-artifact-identity-v1"]
    provenance_schema_version: Literal["skill-provenance-v1"]
    request_id: Annotated[str, Field(min_length=1, max_length=256)]
    usage: TokenUsage
    latency_ms: NonNegativeInt

    @model_validator(mode="after")
    def validate_provenance_bindings(self) -> PackageProvenanceV1:
        authority = self.generation_authority
        direct_pairs = (
            (self.workflow_spec_authority, authority.workflow_spec_authority),
            (self.selected_workflow_fingerprint, authority.selected_workflow_fingerprint),
            (self.repository_url, authority.repository_url),
            (self.repository_id, authority.repository_id),
            (self.exact_commit_sha, authority.exact_commit_sha),
            (self.license_spdx, authority.license_spdx),
            (self.phase2_run_id, authority.phase2_run_id),
            (self.phase2_verified_chain_anchor, authority.phase2_verified_chain_anchor),
            (self.lineage_id, authority.lineage_id),
            (self.stable_slug, authority.stable_slug),
            (self.qualification_report_digest, authority.qualification_report_digest),
            (
                self.qualification_report_schema_version,
                authority.qualification_report_schema_version,
            ),
            (self.qualification_policy_version, authority.qualification_policy_version),
            (
                self.qualification_threshold_version,
                authority.qualification_threshold_version,
            ),
            (
                self.configured_generator_model_id,
                authority.configured_generator_model_id,
            ),
            (self.actual_generator_model_id, authority.actual_generator_model_id),
            (self.generator_prompt_version, authority.generator_prompt_version),
            (
                self.generator_output_schema_version,
                authority.generator_output_schema_version,
            ),
            (self.generator_policy_version, authority.generator_policy_version),
            (self.generator_producer_version, authority.generator_producer_version),
            (self.phase3_profile_version, authority.phase3_profile_version),
            (self.retry_policy_version, authority.retry_policy_version),
            (self.renderer_version, authority.renderer_version),
            (self.artifact_schema_version, authority.artifact_schema_version),
            (self.provenance_schema_version, authority.provenance_schema_version),
        )
        if any(left != right for left, right in direct_pairs):
            raise ValueError("provenance and generation authority disagree")
        if (
            self.generated_artifact_identity.generation_authority_digest
            != sha256_digest(canonical_json_bytes(authority))
        ):
            raise ValueError("provenance artifact identity and authority disagree")
        if self.source_evidence != authority.workflow_spec_authority.workflow_spec.evidence:
            raise ValueError("provenance source evidence is incomplete")
        if sum(len(quote.text) for quote in self.quotes) > MAX_TOTAL_QUOTE_CHARS:
            raise ValueError("total quote budget exceeded")
        if any(quote.commit_sha != self.exact_commit_sha for quote in self.quotes):
            raise ValueError("quote commit authority disagrees")
        return self


class RenderedFileV1(StrictFrozenModel):
    """One immutable admitted documentation-only package leaf."""

    schema_version: Literal["rendered-file-v1"] = RENDERED_FILE_SCHEMA_VERSION
    path: Annotated[str, Field(min_length=1, max_length=256)]
    content: Annotated[bytes, Field(min_length=1, max_length=MAX_RENDERED_FILE_BYTES)]
    mode: Literal[420]
    is_symlink: Literal[False]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _rendered_path(value)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: bytes) -> bytes:
        return _text_bytes(value)


class RenderedManifestEntryV1(StrictFrozenModel):
    """One external exact path/hash/mode/size fact."""

    path: Annotated[str, Field(min_length=1, max_length=256)]
    content_hash: Digest
    mode: Literal[420]
    size: Annotated[int, Field(ge=1, le=MAX_RENDERED_FILE_BYTES)]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _rendered_path(value)


class RenderedPackageManifestV1(StrictFrozenModel):
    """Canonical ordered manifest finalized only after provenance bytes exist."""

    schema_version: Literal["rendered-package-manifest-v1"]
    entries: Annotated[
        tuple[RenderedManifestEntryV1, ...],
        Field(min_length=2, max_length=16),
    ]

    @model_validator(mode="after")
    def validate_manifest(self) -> RenderedPackageManifestV1:
        paths = tuple(entry.path for entry in self.entries)
        if paths != tuple(sorted(paths)):
            raise ValueError("rendered manifest is not canonically ordered")
        folded = tuple(path.casefold() for path in paths)
        if len(folded) != len(set(folded)):
            raise ValueError("rendered manifest paths collide")
        if paths.count("SKILL.md") != 1 or paths.count("references/provenance.json") != 1:
            raise ValueError("required package files are missing")
        if sum(entry.size for entry in self.entries) > MAX_RENDERED_PACKAGE_BYTES:
            raise ValueError("rendered package exceeds the closed byte budget")
        return self

    @classmethod
    def from_files(
        cls, files: tuple[RenderedFileV1, ...]
    ) -> RenderedPackageManifestV1:
        if not files:
            raise ValueError("rendered package cannot be empty")
        entries = tuple(
            sorted(
                (
                    RenderedManifestEntryV1(
                        path=file.path,
                        content_hash=sha256_digest(file.content),
                        mode=file.mode,
                        size=len(file.content),
                    )
                    for file in files
                ),
                key=lambda entry: entry.path,
            )
        )
        return cls(
            schema_version=RENDERED_MANIFEST_SCHEMA_VERSION,
            entries=entries,
        )


class PackageIdentityV1(StrictFrozenModel):
    """External package identity over rendered manifest facts only."""

    schema_version: Literal["package-identity-v1"]
    rendered_manifest_digest: Digest
    package_digest: Digest

    @model_validator(mode="after")
    def validate_package_digest(self) -> PackageIdentityV1:
        expected = sha256_digest(
            {
                "schema_version": self.schema_version,
                "rendered_manifest_digest": self.rendered_manifest_digest,
            }
        )
        if self.package_digest != expected:
            raise ValueError("package digest mismatch")
        return self


def package_digest(manifest: RenderedPackageManifestV1) -> PackageIdentityV1:
    """Derive the separate external identity from exact rendered manifest facts."""

    if type(manifest) is not RenderedPackageManifestV1:
        raise TypeError("package identity requires a rendered package manifest")
    manifest_digest = sha256_digest(canonical_json_bytes(manifest))
    preimage = {
        "schema_version": PACKAGE_IDENTITY_SCHEMA_VERSION,
        "rendered_manifest_digest": manifest_digest,
    }
    return PackageIdentityV1(
        **preimage,
        package_digest=sha256_digest(preimage),
    )


class FrozenSkillPackageV1(StrictFrozenModel):
    """Exact package bytes plus both distinct non-circular identity layers."""

    schema_version: Literal["frozen-skill-package-v1"]
    stable_slug: _StableSlug
    generated_artifact_identity: GeneratedArtifactIdentityV1
    provenance: PackageProvenanceV1
    files: Annotated[tuple[RenderedFileV1, ...], Field(min_length=2, max_length=16)]
    rendered_manifest: RenderedPackageManifestV1
    package_identity: PackageIdentityV1

    @model_validator(mode="after")
    def validate_frozen_package(self) -> FrozenSkillPackageV1:
        if self.provenance.generated_artifact_identity != self.generated_artifact_identity:
            raise ValueError("package provenance and artifact identity disagree")
        if self.provenance.stable_slug != self.stable_slug:
            raise ValueError("package provenance and stable slug disagree")
        manifest = RenderedPackageManifestV1.from_files(self.files)
        if manifest != self.rendered_manifest:
            raise ValueError("frozen package manifest mismatch")
        if package_digest(manifest) != self.package_identity:
            raise ValueError("frozen package identity mismatch")
        return self


def _yaml_scalar(value: str) -> str:
    """Serialize one scalar through YAML's JSON-compatible quoted subset."""

    return json.dumps(value, ensure_ascii=False)


def _markdown_list(values: tuple[str, ...]) -> str:
    return "\n".join(f"- {value}" for value in values)


def _validate_semantic_safety(
    draft: GeneratedSkillDraft,
    authority: GenerationAuthorityProjectionV1,
) -> None:
    semantic_text = "\n".join(
        (
            draft.description,
            draft.overview,
            *draft.when_to_use,
            *draft.inputs,
            *draft.steps,
            *draft.outputs,
            *draft.failure_handling,
            *draft.approvals,
            *draft.limitations,
            *(reference.body for reference in draft.references),
        )
    ).casefold()
    forbidden = (
        "```",
        "scripts/",
        "chmod +x",
        "curl ",
        "| sh",
        "| bash",
        "pip install",
        "npm install",
        "download and execute",
    )
    if any(marker in semantic_text for marker in forbidden):
        raise ValueError("generated draft requests executable or supply-chain behavior")

    evidence_by_path: dict[str, tuple[str, ...]] = {}
    for evidence in authority.workflow_spec_authority.workflow_spec.evidence:
        evidence_by_path[evidence.path] = (
            *evidence_by_path.get(evidence.path, ()),
            evidence.excerpt,
        )
    for quote in draft.quotes:
        if quote.commit_sha != authority.exact_commit_sha:
            raise ValueError("quote does not cite the exact source commit")
        excerpts = evidence_by_path.get(quote.source_path, ())
        if not any(quote.text in excerpt for excerpt in excerpts):
            raise ValueError("quote is not supported by verified source evidence")


def _provenance(
    *,
    draft: GeneratedSkillDraft,
    authority: GenerationAuthorityProjectionV1,
    identity: GeneratedArtifactIdentityV1,
    request_id: str,
    usage: TokenUsage,
    latency_ms: int,
) -> PackageProvenanceV1:
    workflow_authority = authority.workflow_spec_authority
    return PackageProvenanceV1(
        schema_version=PROVENANCE_SCHEMA_VERSION,
        generated_artifact_identity=identity,
        generation_authority=authority,
        workflow_spec_authority=workflow_authority,
        selected_workflow_fingerprint=authority.selected_workflow_fingerprint,
        repository_url=authority.repository_url,
        repository_id=authority.repository_id,
        exact_commit_sha=authority.exact_commit_sha,
        license_spdx=authority.license_spdx,
        source_evidence=workflow_authority.workflow_spec.evidence,
        quotes=draft.quotes,
        phase2_run_id=authority.phase2_run_id,
        phase2_verified_chain_anchor=authority.phase2_verified_chain_anchor,
        lineage_id=authority.lineage_id,
        stable_slug=authority.stable_slug,
        qualification_report_digest=authority.qualification_report_digest,
        qualification_report_schema_version=(
            authority.qualification_report_schema_version
        ),
        qualification_policy_version=authority.qualification_policy_version,
        qualification_threshold_version=authority.qualification_threshold_version,
        configured_generator_model_id=authority.configured_generator_model_id,
        actual_generator_model_id=authority.actual_generator_model_id,
        generator_prompt_version=authority.generator_prompt_version,
        generator_output_schema_version=authority.generator_output_schema_version,
        generator_policy_version=authority.generator_policy_version,
        generator_producer_version=authority.generator_producer_version,
        phase3_profile_version=authority.phase3_profile_version,
        retry_policy_version=authority.retry_policy_version,
        renderer_version=authority.renderer_version,
        artifact_schema_version=authority.artifact_schema_version,
        provenance_schema_version=authority.provenance_schema_version,
        request_id=request_id,
        usage=usage,
        latency_ms=latency_ms,
    )


def _skill_markdown(
    *,
    draft: GeneratedSkillDraft,
    authority: GenerationAuthorityProjectionV1,
) -> bytes:
    sections = (
        "---",
        f"name: {_yaml_scalar(authority.stable_slug)}",
        f"description: {_yaml_scalar(draft.description)}",
        f"license: {_yaml_scalar(authority.license_spdx)}",
        "metadata:",
        f"  source_repository: {_yaml_scalar(authority.repository_url)}",
        f"  source_commit: {_yaml_scalar(authority.exact_commit_sha)}",
        "---",
        "",
        "# Overview",
        "",
        draft.overview,
        "",
        "## When to use",
        "",
        _markdown_list(draft.when_to_use),
        "",
        "## Inputs",
        "",
        _markdown_list(draft.inputs),
        "",
        "## Procedure",
        "",
        "\n".join(
            f"{index}. {instruction}"
            for index, instruction in enumerate(draft.steps, start=1)
        ),
        "",
        "## Outputs",
        "",
        _markdown_list(draft.outputs),
        "",
        "## Failure handling",
        "",
        _markdown_list(draft.failure_handling),
        "",
        "## Required approvals",
        "",
        _markdown_list(draft.approvals),
        "",
        "## Limitations",
        "",
        _markdown_list(draft.limitations),
    )
    quote_section: tuple[str, ...] = ()
    if draft.quotes:
        quote_lines = tuple(
            (
                f'> "{quote.text}" — `{quote.source_path}` at '
                f"`{quote.commit_sha}`"
            )
            for quote in draft.quotes
        )
        quote_section = ("", "## Source excerpts", "", *quote_lines)
    return ("\n".join((*sections, *quote_section)) + "\n").encode("utf-8")


def render_skill_package(
    *,
    draft: GeneratedSkillDraft,
    authority: GenerationAuthorityProjectionV1,
    request_id: str,
    usage: TokenUsage,
    latency_ms: int,
) -> FrozenSkillPackageV1:
    """Render one deterministic documentation-only Skill package in memory."""

    if (
        type(draft) is not GeneratedSkillDraft
        or type(authority) is not GenerationAuthorityProjectionV1
        or type(usage) is not TokenUsage
    ):
        raise TypeError("renderer requires strict generation contracts")
    if type(request_id) is not str or not request_id or len(request_id) > 256:
        raise ValueError("request id is outside the closed bounds")
    if type(latency_ms) is not int or latency_ms < 0:
        raise ValueError("latency is outside the closed bounds")

    _validate_semantic_safety(draft, authority)
    identity = generated_artifact_identity(draft=draft, authority=authority)
    provenance = _provenance(
        draft=draft,
        authority=authority,
        identity=identity,
        request_id=request_id,
        usage=usage,
        latency_ms=latency_ms,
    )
    files: list[RenderedFileV1] = [
        RenderedFileV1(
            path="SKILL.md",
            content=_skill_markdown(draft=draft, authority=authority),
            mode=0o644,
            is_symlink=False,
        ),
        RenderedFileV1(
            path="references/provenance.json",
            content=canonical_json_bytes(provenance) + b"\n",
            mode=0o644,
            is_symlink=False,
        ),
    ]
    files.extend(
        RenderedFileV1(
            path=f"references/{reference.name}.md",
            content=(f"# {reference.title}\n\n{reference.body}\n").encode("utf-8"),
            mode=0o644,
            is_symlink=False,
        )
        for reference in draft.references
    )
    frozen_files = tuple(sorted(files, key=lambda file: file.path))
    manifest = RenderedPackageManifestV1.from_files(frozen_files)
    return FrozenSkillPackageV1(
        schema_version=FROZEN_PACKAGE_SCHEMA_VERSION,
        stable_slug=authority.stable_slug,
        generated_artifact_identity=identity,
        provenance=provenance,
        files=frozen_files,
        rendered_manifest=manifest,
        package_identity=package_digest(manifest),
    )


def _acquire_package_lock(anchor: AnchoredDirectory, stable_slug: str) -> int:
    lock_name = AnchoredDirectory.validate_child_name(f".{stable_slug}.lock")
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = -1
    try:
        descriptor = os.open(lock_name, flags, 0o600, dir_fd=anchor.descriptor)
        anchored = os.stat(
            lock_name,
            dir_fd=anchor.descriptor,
            follow_symlinks=False,
        )
        opened = os.fstat(descriptor)
        AnchoredDirectory._require_private_regular(anchored)
        AnchoredDirectory._require_private_regular(opened)
        if (anchored.st_dev, anchored.st_ino) != (opened.st_dev, opened.st_ino):
            raise OSError("package lock identity changed")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except (BlockingIOError, OSError) as error:
        if descriptor >= 0:
            os.close(descriptor)
        raise DurableWriteError("package_lock") from error


def _write_rendered_leaf(
    directory: AnchoredDirectory,
    name: str,
    content: bytes,
) -> None:
    directory.atomic_write(
        name,
        content,
        max_bytes=MAX_RENDERED_FILE_BYTES,
        seam_prefix="package_",
    )
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory.descriptor,
        )
        metadata = os.fstat(descriptor)
        AnchoredDirectory._require_private_regular(metadata)
        os.fchmod(descriptor, 0o644)
        os.fsync(descriptor)
        os.fsync(directory.descriptor)
    except OSError as error:
        raise DurableWriteError("package_leaf_mode") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _remove_open_tree(directory: AnchoredDirectory) -> None:
    for name in os.listdir(directory.descriptor):
        AnchoredDirectory.validate_child_name(name)
        metadata = os.stat(name, dir_fd=directory.descriptor, follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            child = directory.open_child_directory(name)
            try:
                _remove_open_tree(child)
            finally:
                child.close()
            directory.remove_child_directory(name)
            continue
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) not in {0o600, 0o644}
        ):
            raise DurableWriteError("package_cleanup_entry")
        directory.unlink(name, missing_ok=False, sync=True)


def _remove_tree(parent: AnchoredDirectory, name: str) -> None:
    child = parent.open_child_directory(name)
    try:
        _remove_open_tree(child)
    finally:
        child.close()
    parent.remove_child_directory(name)


def _best_effort_remove_tree(parent: AnchoredDirectory, name: str) -> None:
    try:
        if parent.stat_child(name) is not None:
            _remove_tree(parent, name)
    except (DurableWriteError, OSError):
        pass


def _build_staged_tree(
    parent: AnchoredDirectory,
    temporary_name: str,
    package: FrozenSkillPackageV1,
) -> None:
    stage = parent.open_child_directory(temporary_name, create=True)
    directories: dict[str, AnchoredDirectory] = {}
    try:
        for rendered in package.files:
            path = PurePosixPath(rendered.path)
            if len(path.parts) == 1:
                directory = stage
            else:
                directory_name = path.parts[0]
                directory = directories.get(directory_name)
                if directory is None:
                    directory = stage.open_child_directory(
                        directory_name,
                        create=True,
                    )
                    directories[directory_name] = directory
            _write_rendered_leaf(directory, path.name, rendered.content)
        for directory in directories.values():
            os.fsync(directory.descriptor)
        os.fsync(stage.descriptor)
        os.fsync(parent.descriptor)
    finally:
        for directory in directories.values():
            directory.close()
        stage.close()


def _trip(seam: Callable[[str], None] | None, name: str) -> None:
    if seam is not None:
        seam(name)


def materialize_skill_package(
    output_directory: Path,
    package: FrozenSkillPackageV1,
    *,
    filesystem_seam: Callable[[str], None] | None = None,
) -> Path:
    """Durably replace one slug tree without following caller-controlled links."""

    if not isinstance(output_directory, Path) or type(package) is not FrozenSkillPackageV1:
        raise TypeError("materializer requires a Path and frozen package")
    anchor: AnchoredDirectory | None = None
    lock_descriptor = -1
    temporary_name = f".{package.stable_slug}.tmp"
    backup_name = f".{package.stable_slug}.backup"
    moved_prior = False
    moved_stage = False
    try:
        anchor = AnchoredDirectory.open(
            output_directory,
            create=True,
            filesystem_seam=filesystem_seam,
        )
        root_identity = os.fstat(anchor.descriptor)
        lock_descriptor = _acquire_package_lock(anchor, package.stable_slug)
        existing = anchor.stat_child(package.stable_slug)
        if existing is not None:
            target = anchor.open_child_directory(package.stable_slug)
            target.close()
        if anchor.stat_child(temporary_name) is not None:
            _remove_tree(anchor, temporary_name)
        if anchor.stat_child(backup_name) is not None:
            if existing is None:
                os.rename(
                    backup_name,
                    package.stable_slug,
                    src_dir_fd=anchor.descriptor,
                    dst_dir_fd=anchor.descriptor,
                )
                os.fsync(anchor.descriptor)
                existing = anchor.stat_child(package.stable_slug)
            else:
                _remove_tree(anchor, backup_name)

        _build_staged_tree(anchor, temporary_name, package)
        if existing is not None:
            os.rename(
                package.stable_slug,
                backup_name,
                src_dir_fd=anchor.descriptor,
                dst_dir_fd=anchor.descriptor,
            )
            moved_prior = True
        _trip(filesystem_seam, "before_package_tree_rename")
        os.rename(
            temporary_name,
            package.stable_slug,
            src_dir_fd=anchor.descriptor,
            dst_dir_fd=anchor.descriptor,
        )
        moved_stage = True
        _trip(filesystem_seam, "before_package_root_directory_fsync")
        os.fsync(anchor.descriptor)

        if moved_prior:
            try:
                _remove_tree(anchor, backup_name)
                _trip(filesystem_seam, "after_package_backup_unlink")
                os.fsync(anchor.descriptor)
            except (DurableWriteError, OSError):
                pass

        current_root = os.stat(output_directory, follow_symlinks=False)
        if (
            stat.S_ISLNK(current_root.st_mode)
            or (current_root.st_dev, current_root.st_ino)
            != (root_identity.st_dev, root_identity.st_ino)
        ):
            raise DurableWriteError("package_parent_identity")
        return output_directory / package.stable_slug
    except DurableWriteError:
        if anchor is not None:
            if moved_stage:
                try:
                    os.rename(
                        package.stable_slug,
                        temporary_name,
                        src_dir_fd=anchor.descriptor,
                        dst_dir_fd=anchor.descriptor,
                    )
                except OSError:
                    pass
            if moved_prior:
                try:
                    os.rename(
                        backup_name,
                        package.stable_slug,
                        src_dir_fd=anchor.descriptor,
                        dst_dir_fd=anchor.descriptor,
                    )
                    os.fsync(anchor.descriptor)
                except OSError:
                    pass
            _best_effort_remove_tree(anchor, temporary_name)
        raise
    except OSError as error:
        if anchor is not None:
            if moved_stage:
                try:
                    os.rename(
                        package.stable_slug,
                        temporary_name,
                        src_dir_fd=anchor.descriptor,
                        dst_dir_fd=anchor.descriptor,
                    )
                except OSError:
                    pass
            if moved_prior:
                try:
                    os.rename(
                        backup_name,
                        package.stable_slug,
                        src_dir_fd=anchor.descriptor,
                        dst_dir_fd=anchor.descriptor,
                    )
                    os.fsync(anchor.descriptor)
                except OSError:
                    pass
            _best_effort_remove_tree(anchor, temporary_name)
        raise DurableWriteError("package_materialization") from error
    finally:
        if lock_descriptor >= 0:
            os.close(lock_descriptor)
        if anchor is not None:
            anchor.close()
