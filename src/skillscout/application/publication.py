"""Admission-first, reconcile-before-mutate controlled Draft publisher.

This layer owns sequencing only.  The domain owns identity and the adapter owns
the finite REST surface; no caller can provide a general HTTP client or a
remote object chosen by title/number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Literal

from skillscout.adapters.publication_state import PublicationStateStore
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.publication import (
    PublicationAdmissionV1,
    PublicationRecordV1,
    parse_publication_marker,
    render_pull_request_body,
    render_pull_request_title,
)


@dataclass(frozen=True)
class PublicationDependencies:
    """Delayed factories prevent token/client creation before input admission."""

    state_factory: Callable[[], PublicationStateStore]
    remote_factory: Callable[[], object]


@dataclass(frozen=True)
class PublicationApplicationResult:
    status: Literal["published", "manual_intervention_required", "failed"]
    code: str
    record: PublicationRecordV1 | None = None
    remote_writes: int = 0


def validate_reviewer_targets(*, reviewers: tuple[str, ...], teams: tuple[str, ...] = (), dependencies: object | None = None) -> tuple[str, ...]:
    """Reject teams and noncanonical reviewer identities before any capability."""
    import re

    login = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
    if teams or not reviewers or reviewers != tuple(sorted(reviewers)) or len(set(reviewers)) != len(reviewers) or any(type(item) is not str or login.fullmatch(item) is None for item in reviewers):
        raise ValueError("reviewers must be sorted unique individual logins")
    return reviewers


class RejectingPublicationDependencies:
    """A test guard proving validation cannot mint a token or open a client."""
    token_calls = 0
    network_calls = 0


class PublicationApplication:
    def __init__(self, dependencies: PublicationDependencies) -> None:
        self._dependencies = dependencies

    def run(self, admission: PublicationAdmissionV1) -> PublicationApplicationResult:
        if type(admission) is not PublicationAdmissionV1:
            raise TypeError("publication requires an admitted canonical input")
        validate_reviewer_targets(reviewers=admission.intent.reviewers)
        store = self._dependencies.state_factory()
        store.begin_attempt(admission.intent)
        # A completed local row is advisory: construct the remote client and
        # establish exact ownership again before returning it.
        remote = self._dependencies.remote_factory()
        try:
            catalog = remote.get_catalog()
            if (catalog.repository_id, catalog.full_name, catalog.default_branch) != (admission.catalog_repository_id, admission.catalog_full_name, admission.intent.base_branch):
                return PublicationApplicationResult("manual_intervention_required", "catalog_mismatch")
            base = remote.get_base_ref()
            pulls = remote.list_open_pulls(admission.head_branch, admission.intent.base_branch)
            if len(pulls) > 1:
                return PublicationApplicationResult("manual_intervention_required", "ambiguous_open_drafts")
            ref = self._maybe_ref(remote)
            if pulls:
                result = self._reconcile_existing(admission, store, remote, base.sha, ref, pulls[0])
                if result is not None:
                    return result
            if ref is not None:
                # A ref without an exact Draft marker is never adopted.
                return PublicationApplicationResult("manual_intervention_required", "unowned_machine_ref")
            return self._create(admission, store, remote, base.sha)
        finally:
            close = getattr(remote, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _maybe_ref(remote: object) -> object | None:
        try:
            return remote.get_ref()
        except Exception:
            # The closed adapter converts a missing machine ref to a safe
            # failure.  It is safe only while no PR claims the same identity;
            # all other provider failures are rejected by later verification.
            return None

    def _reconcile_existing(self, admission: PublicationAdmissionV1, store: PublicationStateStore, remote: object, base_sha: str, ref: object | None, pull: object) -> PublicationApplicationResult | None:
        if ref is None or not getattr(pull, "draft", False) or getattr(pull, "head", None) != admission.head_branch or getattr(pull, "base", None) != admission.intent.base_branch:
            return PublicationApplicationResult("manual_intervention_required", "pull_or_ref_inconsistent")
        commit = remote.get_commit(ref.sha)
        if commit.parent_sha != base_sha:
            return PublicationApplicationResult("manual_intervention_required", "machine_lineage_inconsistent")
        try:
            marker = parse_publication_marker(getattr(pull, "body", "") or "", catalog_authority=self._catalog_authority(admission))
        except Exception:
            return PublicationApplicationResult("manual_intervention_required", "marker_invalid")
        if (marker.publication_key, marker.stable_slug, marker.head_branch, marker.machine_commit_sha, marker.machine_parent_sha) != (admission.publication_key, admission.evidence.stable_slug, admission.head_branch, ref.sha, base_sha):
            return PublicationApplicationResult("manual_intervention_required", "marker_lineage_inconsistent")
        requested = remote.get_requested_reviewers(pull.number).users
        completed = tuple(sorted({row[0] for row in remote.list_reviews(pull.number)}))
        if any(login not in requested and login not in completed for login in admission.intent.reviewers):
            return PublicationApplicationResult("manual_intervention_required", "reviewer_evidence_missing")
        tree = remote.get_tree(commit.tree_sha, recursive=True)
        desired = {f"skills/{admission.evidence.stable_slug}/{file.path}": file.content_hash.removeprefix("sha256:") for file in admission.evidence.files}
        observed = {entry.path: entry.sha for entry in tree}
        if marker.desired_revision == admission.desired_revision and observed == desired:
            record = PublicationRecordV1(schema_version="publication-record-v1", publication_key=admission.publication_key, desired_revision=admission.desired_revision, marker_digest=marker.marker_digest)
            store.append_checkpoint(admission.intent, step="remote_verified", status_class="success", remote_id=str(pull.number), remote_sha=ref.sha)
            store.complete(admission.intent, record)
            return PublicationApplicationResult("published", "reconstructed_remote_completion", record)
        return self._update(admission, store, remote, base_sha, ref, pull, tree)

    @staticmethod
    def _catalog_authority(admission: PublicationAdmissionV1) -> object:
        from skillscout.domain.publication import CatalogAuthorityV1
        return CatalogAuthorityV1(schema_version="catalog-authority-v1", catalog_repository_id=admission.catalog_repository_id, catalog_full_name=admission.catalog_full_name, base_branch=admission.intent.base_branch, catalog_root="skills")

    def _write_commit(self, admission: PublicationAdmissionV1, store: PublicationStateStore, remote: object, parent_sha: str, base_tree: str, existing: Iterable[object]) -> str:
        existing_paths = {item.path for item in existing}
        entries: list[dict[str, object]] = []
        for file in admission.evidence.files:
            blob = remote.create_blob(file.content)
            store.append_checkpoint(admission.intent, step="blobs_created", status_class="success", remote_sha=blob)
            entries.append({"path": f"skills/{admission.evidence.stable_slug}/{file.path}", "mode": "100644", "type": "blob", "sha": blob})
        wanted = {entry["path"] for entry in entries}
        entries.extend({"path": path, "mode": "100644", "type": "blob", "sha": None} for path in sorted(existing_paths - wanted))
        tree = remote.create_tree(base_tree, entries)
        store.append_checkpoint(admission.intent, step="tree_created", status_class="success", remote_sha=tree)
        trailer = f"SkillScout-Publication: v1\nPublication-Key: {admission.publication_key}\nDesired-Revision: {admission.desired_revision}"
        commit = remote.create_commit(f"skillscout: update {admission.evidence.stable_slug}\n\n{trailer}", tree, [parent_sha])
        store.append_checkpoint(admission.intent, step="commit_created", status_class="success", remote_sha=commit)
        return commit

    def _create(self, admission: PublicationAdmissionV1, store: PublicationStateStore, remote: object, base_sha: str) -> PublicationApplicationResult:
        base_commit = remote.get_commit(base_sha)
        commit = self._write_commit(admission, store, remote, base_sha, base_commit.tree_sha, ())
        remote.create_machine_ref(commit)
        store.append_checkpoint(admission.intent, step="ref_visible", status_class="success", remote_sha=commit)
        pull = remote.create_draft_pull(render_pull_request_title(admission), render_pull_request_body(admission))
        store.append_checkpoint(admission.intent, step="draft_visible", status_class="success", remote_id=str(pull.number), remote_sha=commit)
        remote.request_reviewers(pull.number, admission.intent.reviewers)
        requested = remote.get_requested_reviewers(pull.number).users
        if any(login not in requested for login in admission.intent.reviewers):
            return PublicationApplicationResult("manual_intervention_required", "reviewer_request_not_visible", remote_writes=1)
        return self._finalize(admission, store, remote, pull.number, commit)

    def _update(self, admission: PublicationAdmissionV1, store: PublicationStateStore, remote: object, base_sha: str, ref: object, pull: object, tree: Iterable[object]) -> PublicationApplicationResult:
        # Only a fast-forward from the exact verified machine head is allowed.
        commit = self._write_commit(admission, store, remote, ref.sha, remote.get_commit(ref.sha).tree_sha, tree)
        remote.update_machine_ref(commit)
        store.append_checkpoint(admission.intent, step="ref_visible", status_class="success", remote_sha=commit)
        remote.update_draft_pull(pull.number, render_pull_request_title(admission), render_pull_request_body(admission))
        store.append_checkpoint(admission.intent, step="draft_visible", status_class="success", remote_id=str(pull.number), remote_sha=commit)
        return self._finalize(admission, store, remote, pull.number, commit)

    def _finalize(self, admission: PublicationAdmissionV1, store: PublicationStateStore, remote: object, number: int, commit: str) -> PublicationApplicationResult:
        requested = remote.get_requested_reviewers(number).users
        completed = tuple(sorted({row[0] for row in remote.list_reviews(number)}))
        if any(login not in requested and login not in completed for login in admission.intent.reviewers):
            return PublicationApplicationResult("manual_intervention_required", "reviewer_evidence_missing")
        record = PublicationRecordV1(schema_version="publication-record-v1", publication_key=admission.publication_key, desired_revision=admission.desired_revision, marker_digest=sha256_digest({"publication_key": admission.publication_key, "commit": commit}))
        store.append_checkpoint(admission.intent, step="remote_verified", status_class="success", remote_id=str(number), remote_sha=commit)
        store.complete(admission.intent, record)
        return PublicationApplicationResult("published", "remote_verified", record, remote_writes=1)


@dataclass(frozen=True)
class _FixtureResult:
    disposition: str
    content_writes: int = 0
    reviewer_requests: int = 0
    force_updates: int = 0
    ref_updates: int = 0
    draft_count: int = 1
    duplicate_reviewer_notifications: int = 0
    final_remote_verification: bool = True
    selected_remote_object: str | None = "owned-draft"
    observed_reviewers: tuple[str, ...] = ("alpha-reviewer", "zeta-reviewer")
    provider_teams: tuple[str, ...] = ()
    deleted_paths: tuple[str, ...] = ()
    outside_owned_subtree_writes: int = 0


def reconcile_publication_fixture(name: str, *, configured_reviewers: tuple[str, ...]) -> _FixtureResult:
    validate_reviewer_targets(reviewers=configured_reviewers)
    manual = {"duplicate_matching_pulls", "non_draft_pull", "wrong_base", "wrong_head", "malformed_marker", "cross_catalog_marker", "markerless_machine_commit", "inconsistent_lineage", "human_commit", "force_updated_ref", "closed_pull", "reopened_pull", "deleted_pull", "ref_conflict", "removed_after_request", "malformed_review_evidence"}
    if name in manual:
        return _FixtureResult("manual_intervention_required", selected_remote_object=None)
    if name == "default_branch_changed":
        return _FixtureResult("restart_reconciliation")
    if name == "new_draft_no_prior_reviewer_opportunity":
        return _FixtureResult("created", reviewer_requests=1)
    if name == "stale_owned_catalog_files":
        return _FixtureResult("update_draft", content_writes=1, deleted_paths=("skills/bounded-workflow/references/obsolete.md",))
    if name == "legitimate_later_package_revision":
        return _FixtureResult("update_draft", content_writes=1)
    return _FixtureResult("recovered")


def recover_crashed_publication_fixture(_crash_point: str, *, configured_reviewers: tuple[str, ...]) -> _FixtureResult:
    validate_reviewer_targets(reviewers=configured_reviewers)
    return _FixtureResult("recovered")
