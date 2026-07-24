"""Wave-0 executable contract for controlled Draft PR admission.

The publication implementation deliberately does not exist while this module is
introduced.  Imports therefore stay inside tests: collection is a usable
specification gate, while an attempt to execute the contract fails until the
closed Phase 4 domain is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest
from pydantic import ValidationError


@dataclass
class RejectingDependencyFactories:
    """A dependency seam that proves admission happens before side effects."""

    protected_config_calls: int = 0
    token_calls: int = 0
    transport_calls: int = 0
    state_calls: int = 0
    filesystem_calls: int = 0

    def _reject(self, name: str) -> None:
        setattr(self, f"{name}_calls", getattr(self, f"{name}_calls") + 1)
        raise AssertionError(f"rejected candidate touched {name}")

    def protected_config(self) -> None:
        self._reject("protected_config")

    def token(self) -> None:
        self._reject("token")

    def transport(self) -> None:
        self._reject("transport")

    def publication_state(self) -> None:
        self._reject("state")

    def filesystem(self) -> None:
        self._reject("filesystem")

    def assert_untouched(self) -> None:
        assert self.protected_config_calls == 0
        assert self.token_calls == 0
        assert self.transport_calls == 0
        assert self.state_calls == 0
        assert self.filesystem_calls == 0


def _publication_symbols() -> Any:
    from skillscout.domain import publication

    return publication


def _valid_evidence_payload() -> dict[str, object]:
    """A deliberately small, candidate-bound Phase 3 handoff fixture."""

    return {
        "schema_version": "candidate-publication-evidence-v1",
        "stable_slug": "bounded-workflow",
        "repository_id": 101,
        "repository_full_name": "source-org/bounded-workflow",
        "repository_url": "https://github.com/source-org/bounded-workflow",
        "exact_commit_sha": "a" * 40,
        "license_spdx": "MIT",
        "workflow_fingerprint": "sha256:" + "1" * 64,
        "package_digest": "sha256:" + "2" * 64,
        "rendered_manifest_digest": "sha256:" + "3" * 64,
        "qualification_report_digest": "sha256:" + "4" * 64,
        "validation_report_digest": "sha256:" + "5" * 64,
        "review_attestation_digest": "sha256:" + "6" * 64,
        "qualification_passed": True,
        "validation_error_count": 0,
        "review_verdict": "YES",
        "review_confidence": 0.90,
        "files": (
            {
                "path": "SKILL.md",
                "content_hash": "sha256:" + "7" * 64,
                "mode": 420,
                "size": 128,
            },
            {
                "path": "references/provenance.json",
                "content_hash": "sha256:" + "8" * 64,
                "mode": 420,
                "size": 128,
            },
        ),
    }


def _authority_payload() -> dict[str, object]:
    return {
        "schema_version": "catalog-authority-v1",
        "catalog_repository_id": 202,
        "catalog_full_name": "catalog-org/skills",
        "base_branch": "main",
        "catalog_root": "skills",
    }


def _reviewers_payload() -> dict[str, object]:
    return {
        "schema_version": "reviewer-targets-v1",
        "reviewers": ("skill-maintainer",),
    }


def _admitted_bundle() -> tuple[Any, Any, Any, Any]:
    publication = _publication_symbols()
    evidence = publication.CandidatePublicationEvidenceV1.model_validate(
        _valid_evidence_payload()
    )
    authority = publication.CatalogAuthorityV1.model_validate(_authority_payload())
    reviewers = publication.ReviewerTargetsV1.model_validate(_reviewers_payload())
    intent = publication.derive_publication_intent(
        evidence=evidence, catalog_authority=authority, reviewer_targets=reviewers
    )
    return publication, evidence, authority, intent


def test_admission_is_deterministic_and_renders_complete_human_review_body() -> None:
    publication, evidence, authority, intent = _admitted_bundle()
    admission = publication.bind_publication_admission(
        evidence=evidence, intent=intent, catalog_authority=authority
    )

    assert admission.catalog_root == "skills"
    assert admission.head_branch == "skillscout/bounded-workflow"
    assert admission.publication_key == intent.publication_key
    assert admission.desired_revision == intent.desired_revision
    assert publication.render_pull_request_title(admission) == (
        "Draft: add bounded-workflow skill"
    )
    body = publication.render_pull_request_body(admission)
    for field in (
        "source-org/bounded-workflow",
        "a" * 40,
        "MIT",
        "sha256:" + "1" * 64,
        "qualification",
        "format",
        "safety",
        "independent review",
        "human review",
    ):
        assert field.casefold() in body.casefold()
    assert body == publication.render_pull_request_body(admission)


@pytest.mark.parametrize(
    ("name", "mutate"),
    (
        ("canonical_artifact_bytes", lambda value: {**value, "package_digest": "sha256:" + "f" * 64}),
        ("digest_binding", lambda value: {**value, "rendered_manifest_digest": "sha256:" + "e" * 64}),
        ("qualification_eligibility", lambda value: {**value, "qualification_passed": False}),
        ("validation_error_count", lambda value: {**value, "validation_error_count": 1}),
        ("review_evidence", lambda value: {**value, "review_verdict": "NO"}),
        ("path", lambda value: {**value, "files": ({**value["files"][0], "path": "../SKILL.md"}, value["files"][1])}),
        ("mode", lambda value: {**value, "files": ({**value["files"][0], "mode": 493}, value["files"][1])}),
        ("size", lambda value: {**value, "files": ({**value["files"][0], "size": 0}, value["files"][1])}),
        ("repository_identity", lambda value: {**value, "repository_id": 0}),
        ("reviewer_grammar", lambda value: {"schema_version": "reviewer-targets-v1", "reviewers": ("bad reviewer",)}),
    ),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_each_invalid_phase3_relationship_rejects_before_dependency_factories(
    name: str, mutate: Callable[[dict[str, object]], dict[str, object]]
) -> None:
    publication = _publication_symbols()
    factories = RejectingDependencyFactories()
    payload = _valid_evidence_payload()
    with pytest.raises((ValidationError, ValueError, TypeError)):
        if name == "reviewer_grammar":
            publication.ReviewerTargetsV1.model_validate(mutate(payload))
        else:
            evidence = publication.CandidatePublicationEvidenceV1.model_validate(mutate(payload))
            publication.admit_phase3_candidate(evidence=evidence, factories=factories)
    factories.assert_untouched()


def test_candidate_evidence_excludes_catalog_reviewer_intent_and_authority_fields() -> None:
    publication = _publication_symbols()
    forbidden = {
        "catalog_repository_id",
        "catalog_full_name",
        "base_branch",
        "reviewers",
        "publication_key",
        "desired_revision",
        "token",
    }
    fields = set(publication.CandidatePublicationEvidenceV1.model_fields)
    assert fields.isdisjoint(forbidden)
    evidence = publication.CandidatePublicationEvidenceV1.model_validate(_valid_evidence_payload())
    assert evidence.model_dump(mode="json")


def test_authority_changes_intent_and_admission_digest_not_candidate_digest() -> None:
    publication, evidence, authority, intent = _admitted_bundle()
    other_authority = publication.CatalogAuthorityV1.model_validate(
        {**_authority_payload(), "catalog_repository_id": 203, "catalog_full_name": "catalog-org/other"}
    )
    other_intent = publication.derive_publication_intent(
        evidence=evidence,
        catalog_authority=other_authority,
        reviewer_targets=publication.ReviewerTargetsV1.model_validate(_reviewers_payload()),
    )
    assert evidence.evidence_digest == publication.CandidatePublicationEvidenceV1.model_validate(_valid_evidence_payload()).evidence_digest
    assert intent.intent_digest != other_intent.intent_digest
    assert publication.bind_publication_admission(evidence=evidence, intent=intent, catalog_authority=authority).admission_digest != publication.bind_publication_admission(evidence=evidence, intent=other_intent, catalog_authority=other_authority).admission_digest


@pytest.mark.parametrize("invalid_marker", ("", "not-a-marker", "<!-- skillscout:publication-v0 {} -->", "<!-- skillscout:publication-v1 duplicate -->\n<!-- skillscout:publication-v1 duplicate -->"), ids=("empty", "malformed", "unknown_schema", "duplicate"))
def test_marker_parser_rejects_malformed_spoofed_and_duplicate_markers(invalid_marker: str) -> None:
    publication, _, authority, _ = _admitted_bundle()
    with pytest.raises((ValidationError, ValueError, TypeError)):
        publication.parse_publication_marker(invalid_marker, catalog_authority=authority)


def test_marker_recovery_keeps_stable_identity_and_updates_revision_evidence() -> None:
    publication, evidence, authority, intent = _admitted_bundle()
    admission = publication.bind_publication_admission(evidence=evidence, intent=intent, catalog_authority=authority)
    marker = publication.PublicationMarkerV1.from_admission(
        admission=admission,
        machine_commit_sha="b" * 40,
        machine_parent_sha="c" * 40,
        prior_marker_digest=None,
    )
    later = publication.CandidatePublicationEvidenceV1.model_validate(
        {**_valid_evidence_payload(), "package_digest": "sha256:" + "9" * 64}
    )
    later_intent = publication.derive_publication_intent(
        evidence=later, catalog_authority=authority, reviewer_targets=publication.ReviewerTargetsV1.model_validate(_reviewers_payload())
    )
    assert later_intent.publication_key == intent.publication_key
    assert later_intent.desired_revision != intent.desired_revision
    recovered = publication.parse_publication_marker(marker.render(), catalog_authority=authority)
    assert recovered.publication_key == marker.publication_key
    assert recovered.package_digest == marker.package_digest
    assert recovered.machine_parent_sha == "c" * 40

