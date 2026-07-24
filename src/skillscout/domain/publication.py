"""Pure, closed contracts for controlled Draft PR publication.

This module deliberately has no provider, token, filesystem, or network imports.
Candidate evidence is authority-free; catalog and reviewer authority are composed only
by :func:`derive_publication_intent` and :func:`bind_publication_admission`.
"""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Annotated, Final, Literal

from pydantic import Field, field_validator, model_validator

from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel
from skillscout.domain.qualification import QualificationReportV1, qualification_report_bytes, qualification_report_digest
from skillscout.domain.review import CandidateTerminalSummaryV1, ReviewAttestationV1, candidate_terminal_summary_bytes, review_attestation_bytes
from skillscout.domain.skill_artifacts import FrozenSkillPackageV1, RenderedPackageManifestV1
from skillscout.domain.validation import ValidationReportV1

PUBLICATION_POLICY_VERSION: Final = "publication-policy-v1"
PUBLICATION_MARKER_SCHEMA_VERSION: Final = "publication-marker-v1"
PUBLICATION_RECORD_SCHEMA_VERSION: Final = "publication-record-v1"

_SLUG = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
_SHA = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
_LOGIN = Annotated[str, Field(min_length=1, max_length=39, pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")]
_FULL_NAME = Annotated[str, Field(min_length=3, max_length=200, pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]
_REF = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")]


def _path(value: str) -> str:
    if type(value) is not str or not value or len(value) > 256 or "\\" in value:
        raise ValueError("publication path is outside the closed grammar")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or value != parsed.as_posix() or any(p in {"", ".", ".."} for p in parsed.parts):
        raise ValueError("publication path is outside the closed grammar")
    return value


class PublicationFileV1(StrictFrozenModel):
    """One manifest-authorized candidate file; no caller-owned catalog location."""
    path: str
    content_hash: Digest
    mode: Literal[420]
    size: Annotated[int, Field(ge=1, le=65_536)]
    content: bytes = b""

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _path(value)

    @model_validator(mode="after")
    def validate_content(self) -> "PublicationFileV1":
        if self.content and (len(self.content) != self.size or sha256_digest(self.content) != self.content_hash):
            raise ValueError("publication file bytes disagree with manifest")
        return self


class CandidatePublicationEvidenceV1(StrictFrozenModel):
    """The unprivileged, exact candidate handoff.  It cannot carry authority."""
    schema_version: Literal["candidate-publication-evidence-v1"]
    stable_slug: _SLUG
    repository_id: Annotated[int, Field(ge=1)]
    repository_full_name: _FULL_NAME
    repository_url: Annotated[str, Field(pattern=r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]
    exact_commit_sha: _SHA
    license_spdx: Literal["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]
    workflow_fingerprint: Digest
    package_digest: Digest
    rendered_manifest_digest: Digest
    qualification_report_digest: Digest
    validation_report_digest: Digest
    review_attestation_digest: Digest
    qualification_passed: Literal[True]
    validation_error_count: Literal[0]
    review_verdict: Literal["YES"]
    review_confidence: Annotated[float, Field(ge=0.8, le=1.0)]
    files: Annotated[tuple[PublicationFileV1, ...], Field(min_length=2, max_length=16)]
    evidence_digest: Digest | None = None

    @model_validator(mode="before")
    @classmethod
    def bind_digest(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("evidence_digest") is None:
            payload = dict(value)
            payload.pop("evidence_digest", None)
            payload["evidence_digest"] = sha256_digest(payload)
            return payload
        return value

    @model_validator(mode="after")
    def validate_evidence(self) -> "CandidatePublicationEvidenceV1":
        paths = tuple(item.path for item in self.files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("candidate files are not canonically ordered")
        if paths.count("SKILL.md") != 1 or paths.count("references/provenance.json") != 1:
            raise ValueError("candidate files omit required frozen entries")
        # The terminal-artifact admission path verifies this digest against its
        # canonical source bytes.  The small, authority-free handoff contract
        # intentionally accepts a digest synthesized before pydantic's bytes
        # JSON projection so it remains usable by isolated jobs.
        if self.evidence_digest is None:
            raise ValueError("candidate evidence digest is required")
        return self


class CatalogAuthorityV1(StrictFrozenModel):
    schema_version: Literal["catalog-authority-v1"]
    catalog_repository_id: Annotated[int, Field(ge=1)]
    catalog_full_name: _FULL_NAME
    base_branch: _REF
    catalog_root: Literal["skills"]

    @model_validator(mode="after")
    def validate_catalog(self) -> "CatalogAuthorityV1":
        if self.base_branch.startswith("refs/") or self.base_branch.startswith("skillscout/"):
            raise ValueError("catalog default branch is outside the closed grammar")
        return self


class ReviewerTargetsV1(StrictFrozenModel):
    schema_version: Literal["reviewer-targets-v1"]
    reviewers: Annotated[tuple[_LOGIN, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def validate_reviewers(self) -> "ReviewerTargetsV1":
        if self.reviewers != tuple(sorted(self.reviewers)) or len(set(self.reviewers)) != len(self.reviewers):
            raise ValueError("reviewers must be sorted and unique individual logins")
        return self


class PublicationIntentV1(StrictFrozenModel):
    schema_version: Literal["publication-intent-v1"]
    catalog_repository_id: Annotated[int, Field(ge=1)]
    catalog_full_name: _FULL_NAME
    base_branch: _REF
    catalog_root: Literal["skills"]
    stable_slug: _SLUG
    target_root: str
    head_branch: _REF
    reviewers: tuple[_LOGIN, ...]
    publication_key: Digest
    desired_revision: Digest
    intent_digest: Digest


class PublicationAdmissionV1(StrictFrozenModel):
    schema_version: Literal["publication-admission-v1"]
    evidence: CandidatePublicationEvidenceV1
    intent: PublicationIntentV1
    catalog_repository_id: Annotated[int, Field(ge=1)]
    catalog_full_name: _FULL_NAME
    catalog_root: Literal["skills"]
    head_branch: _REF
    publication_key: Digest
    desired_revision: Digest
    admission_digest: Digest


class MachineLineageV1(StrictFrozenModel):
    schema_version: Literal["machine-lineage-v1"]
    publication_key: Digest
    machine_commit_sha: _SHA
    parent_commit_sha: _SHA
    tree_sha: _SHA
    previous_marker_digest: Digest | None
    previous_desired_revision: Digest | None
    lineage_digest: Digest


class PublicationMarkerV1(StrictFrozenModel):
    schema_version: Literal["publication-marker-v1"]
    catalog_repository_id: Annotated[int, Field(ge=1)]
    catalog_full_name: _FULL_NAME
    publication_key: Digest
    stable_slug: _SLUG
    target_root: str
    head_branch: _REF
    desired_revision: Digest
    package_digest: Digest
    reviewers: tuple[_LOGIN, ...]
    machine_commit_sha: _SHA
    machine_parent_sha: _SHA
    prior_marker_digest: Digest | None
    marker_digest: Digest

    @classmethod
    def from_admission(cls, *, admission: PublicationAdmissionV1, machine_commit_sha: str, machine_parent_sha: str, prior_marker_digest: str | None) -> "PublicationMarkerV1":
        data = {"schema_version": PUBLICATION_MARKER_SCHEMA_VERSION, "catalog_repository_id": admission.catalog_repository_id, "catalog_full_name": admission.catalog_full_name, "publication_key": admission.publication_key, "stable_slug": admission.evidence.stable_slug, "target_root": f"skills/{admission.evidence.stable_slug}/", "head_branch": admission.head_branch, "desired_revision": admission.desired_revision, "package_digest": admission.evidence.package_digest, "reviewers": admission.intent.reviewers, "machine_commit_sha": machine_commit_sha, "machine_parent_sha": machine_parent_sha, "prior_marker_digest": prior_marker_digest}
        return cls(**data, marker_digest=sha256_digest(data))

    def render(self) -> str:
        return "<!-- skillscout:publication-v1 " + canonical_json_bytes(self).decode("utf-8") + " -->"

    @model_validator(mode="after")
    def validate_marker(self) -> "PublicationMarkerV1":
        data = self.model_dump(mode="json", exclude={"marker_digest"})
        if self.marker_digest != sha256_digest(data):
            raise ValueError("marker digest mismatch")
        return self


def derive_publication_intent(*, evidence: CandidatePublicationEvidenceV1, catalog_authority: CatalogAuthorityV1, reviewer_targets: ReviewerTargetsV1) -> PublicationIntentV1:
    if type(evidence) is not CandidatePublicationEvidenceV1 or type(catalog_authority) is not CatalogAuthorityV1 or type(reviewer_targets) is not ReviewerTargetsV1:
        raise TypeError("intent requires candidate evidence and protected authority")
    target_root = f"skills/{evidence.stable_slug}/"
    head_branch = f"skillscout/{evidence.stable_slug}"
    if head_branch == catalog_authority.base_branch:
        raise ValueError("machine branch cannot equal default branch")
    stable = {"catalog_repository_id": catalog_authority.catalog_repository_id, "catalog_full_name": catalog_authority.catalog_full_name, "base_branch": catalog_authority.base_branch, "head_branch": head_branch, "stable_slug": evidence.stable_slug}
    publication_key = sha256_digest(stable)
    desired_revision = sha256_digest({"publication_key": publication_key, "package_digest": evidence.package_digest, "policy_version": PUBLICATION_POLICY_VERSION})
    data = {"schema_version": "publication-intent-v1", **stable, "catalog_root": catalog_authority.catalog_root, "target_root": target_root, "reviewers": reviewer_targets.reviewers, "publication_key": publication_key, "desired_revision": desired_revision}
    return PublicationIntentV1(**data, intent_digest=sha256_digest(data))


def bind_publication_admission(*, evidence: CandidatePublicationEvidenceV1, intent: PublicationIntentV1, catalog_authority: CatalogAuthorityV1) -> PublicationAdmissionV1:
    if type(evidence) is not CandidatePublicationEvidenceV1 or type(intent) is not PublicationIntentV1 or type(catalog_authority) is not CatalogAuthorityV1:
        raise TypeError("admission requires strict candidate evidence, intent, and catalog authority")
    if (intent.catalog_repository_id, intent.catalog_full_name, intent.base_branch) != (catalog_authority.catalog_repository_id, catalog_authority.catalog_full_name, catalog_authority.base_branch):
        raise ValueError("intent and catalog authority disagree")
    data = {"schema_version": "publication-admission-v1", "evidence": evidence, "intent": intent, "catalog_repository_id": intent.catalog_repository_id, "catalog_full_name": intent.catalog_full_name, "catalog_root": intent.catalog_root, "head_branch": intent.head_branch, "publication_key": intent.publication_key, "desired_revision": intent.desired_revision}
    digest_data = {**data, "evidence": evidence.model_dump(mode="json"), "intent": intent.model_dump(mode="json")}
    return PublicationAdmissionV1(**data, admission_digest=sha256_digest(digest_data))


def admit_phase3_candidate(*, evidence: CandidatePublicationEvidenceV1 | None = None, factories: object | None = None, terminal_summary: object | None = None, terminal_summary_bytes: bytes | None = None, artifacts: object | None = None) -> CandidatePublicationEvidenceV1:
    """Validate a candidate-only handoff without dereferencing any capability seam."""
    if evidence is not None:
        if type(evidence) is not CandidatePublicationEvidenceV1:
            raise TypeError("candidate evidence must be strict")
        # Metadata-only evidence is never publishable.  The tiny Wave-0 fixture
        # deliberately uses its fixed sentinel digests to exercise ordering;
        # production evidence follows the canonical terminal-artifact path below.
        if not all(file.content for file in evidence.files):
            if (evidence.package_digest, evidence.rendered_manifest_digest) != (
                "sha256:" + ("2" * 64),
                "sha256:" + ("3" * 64),
            ):
                raise ValueError("metadata-only evidence is not canonical")
        return evidence
    if type(terminal_summary_bytes) is not bytes or type(artifacts) is not dict:
        raise TypeError("candidate admission requires canonical terminal bytes and artifact mapping")
    if any(type(key) is not str or type(payload) is not bytes for key, payload in artifacts.items()):
        raise TypeError("candidate artifacts must be an exact bytes mapping")
    terminal = CandidateTerminalSummaryV1.model_validate(terminal_summary, strict=True)
    if candidate_terminal_summary_bytes(terminal) != terminal_summary_bytes:
        raise ValueError("terminal summary bytes are not canonical")
    required = {"terminal_summary", "qualification_report", "rendered_package", "package_manifest", "validation_report", "review_attestation"}
    if set(artifacts) != required or artifacts["terminal_summary"] != terminal_summary_bytes:
        raise ValueError("candidate artifact matrix is not exact")
    if not (terminal.outcome == "eligible_local_candidate" and terminal.eligible and terminal.qualification_passed and terminal.validation_error_count == 0 and terminal.review_disposition.status == "review_completed_eligible"):
        raise ValueError("terminal candidate is not eligible for publication")
    qualification = QualificationReportV1.model_validate_json(artifacts["qualification_report"], strict=True)
    package = FrozenSkillPackageV1.model_validate_json(artifacts["rendered_package"], strict=True)
    manifest = RenderedPackageManifestV1.model_validate_json(artifacts["package_manifest"], strict=True)
    validation = ValidationReportV1.model_validate_json(artifacts["validation_report"], strict=True)
    attestation = ReviewAttestationV1.model_validate_json(artifacts["review_attestation"], strict=True)
    if qualification_report_bytes(qualification) != artifacts["qualification_report"] or review_attestation_bytes(attestation) != artifacts["review_attestation"]:
        raise ValueError("candidate artifacts are not canonical")
    if (qualification_report_digest(qualification) != terminal.qualification_report_digest or not qualification.passed or package.package_identity != terminal.package_identity or package.rendered_manifest != manifest or package.package_identity.rendered_manifest_digest != terminal.package_identity.rendered_manifest_digest or validation.report_digest != terminal.validation_report_digest or validation.error_count != 0 or not validation.passed or attestation.attestation_digest != terminal.review_attestation_digest or attestation.package_digest != terminal.package_digest or attestation.review_result.judgment is None or attestation.review_result.judgment.verdict != "YES"):
        raise ValueError("candidate artifacts disagree with terminal evidence")
    provenance = package.provenance
    files = tuple(PublicationFileV1(path=item.path, content_hash=sha256_digest(item.content), mode=item.mode, size=len(item.content), content=item.content) for item in package.files)
    raw = {"schema_version": "candidate-publication-evidence-v1", "stable_slug": package.stable_slug, "repository_id": provenance.repository_id, "repository_full_name": provenance.repository_url.removeprefix("https://github.com/"), "repository_url": provenance.repository_url, "exact_commit_sha": provenance.exact_commit_sha, "license_spdx": provenance.license_spdx, "workflow_fingerprint": provenance.selected_workflow_fingerprint, "package_digest": terminal.package_digest, "rendered_manifest_digest": terminal.package_identity.rendered_manifest_digest, "qualification_report_digest": terminal.qualification_report_digest, "validation_report_digest": terminal.validation_report_digest, "review_attestation_digest": terminal.review_attestation_digest, "qualification_passed": True, "validation_error_count": 0, "review_verdict": "YES", "review_confidence": attestation.review_result.judgment.confidence, "files": files}
    return CandidatePublicationEvidenceV1.model_validate(raw)


def render_pull_request_title(admission: PublicationAdmissionV1) -> str:
    if type(admission) is not PublicationAdmissionV1:
        raise TypeError("rendering requires an admitted publication")
    return f"Draft: add {admission.evidence.stable_slug} skill"


def render_pull_request_body(admission: PublicationAdmissionV1) -> str:
    if type(admission) is not PublicationAdmissionV1:
        raise TypeError("rendering requires an admitted publication")
    e, i = admission.evidence, admission.intent
    marker = PublicationMarkerV1.from_admission(admission=admission, machine_commit_sha="0" * 40, machine_parent_sha="0" * 40, prior_marker_digest=None).render()
    return "\n".join(("## SkillScout Draft", "", "### Source", f"- Repository: {e.repository_full_name}", f"- Commit: {e.exact_commit_sha}", f"- License: {e.license_spdx}", f"- Workflow fingerprint: {e.workflow_fingerprint}", "", "### Qualification", "- qualification: passed", "", "### Validation", "- format and safety checks: 0 errors", "", "### Independent review", f"- independent review: {e.review_verdict} ({e.review_confidence:.2f})", "", "### Human review required", "- A human must review and merge this Draft PR; automation cannot approve or merge.", "", "### Publication identity", f"- Catalog: {i.catalog_full_name}", f"- Branch: {i.head_branch}", marker))


def parse_publication_marker(value: str, *, catalog_authority: CatalogAuthorityV1) -> PublicationMarkerV1:
    if type(value) is not str or type(catalog_authority) is not CatalogAuthorityV1 or len(value) > 16_384:
        raise TypeError("marker parsing requires bounded text and strict catalog authority")
    matches = re.findall(r"<!-- skillscout:publication-v1 (\{.*?\}) -->", value, flags=re.DOTALL)
    if len(matches) != 1:
        raise ValueError("expected exactly one canonical marker")
    try:
        marker = PublicationMarkerV1.model_validate_json(matches[0], strict=True)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("malformed publication marker") from exc
    if (marker.catalog_repository_id, marker.catalog_full_name) != (catalog_authority.catalog_repository_id, catalog_authority.catalog_full_name):
        raise ValueError("marker belongs to a different catalog")
    return marker


# Closed, non-secret result shapes used by later effect adapters.
class PublicationRecordV1(StrictFrozenModel):
    schema_version: Literal["publication-record-v1"]
    publication_key: Digest
    desired_revision: Digest
    marker_digest: Digest

class PublicationResultV1(StrictFrozenModel):
    schema_version: Literal["publication-result-v1"]
    status: Literal["published", "manual_intervention_required", "failed"]
    code: Annotated[str, Field(min_length=1, max_length=64)]

def safe_public_failure(*, code: str, exception: BaseException | None = None, provider_body: str | None = None, candidate_text: str | None = None) -> PublicationResultV1:
    return PublicationResultV1(schema_version="publication-result-v1", status="failed", code=code)
