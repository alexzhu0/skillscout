"""Admission-first, reconcile-before-mutate controlled Draft publisher.

This layer owns sequencing only.  The domain owns identity and the adapter owns
the finite REST surface; no caller can provide a general HTTP client or a
remote object chosen by title/number.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Callable, Iterable, Literal

from skillscout.adapters.publication_state import PublicationStateStore
from skillscout.domain.publication import (
    PublicationAdmissionV1,
    PublicationMarkerV1,
    PublicationRecordV1,
    parse_publication_marker,
    render_pull_request_body,
    render_pull_request_title,
)

_LOGIN_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$"
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_COMPLETED_REVIEW_STATES = {
    "APPROVED",
    "CHANGES_REQUESTED",
    "COMMENTED",
    "DISMISSED",
}


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
    disposition: Literal["draft_created", "draft_updated", "draft_reused"] | None = None
    commit_sha: str | None = None
    pull_number: int | None = None
    pull_url: str | None = None
    remote_writes: int = 0


def validate_reviewer_targets(*, reviewers: tuple[str, ...], teams: tuple[str, ...] = (), dependencies: object | None = None) -> tuple[str, ...]:
    """Reject teams and noncanonical reviewer identities before any capability."""
    if teams or not reviewers or reviewers != tuple(sorted(reviewers)) or len(set(reviewers)) != len(reviewers) or any(type(item) is not str or _LOGIN_RE.fullmatch(item) is None for item in reviewers):
        raise ValueError("reviewers must be sorted unique individual logins")
    return reviewers


class RejectingPublicationDependencies:
    """A test guard proving validation cannot mint a token or open a client."""
    token_calls = 0
    network_calls = 0


def _git_blob_object_id(content: bytes) -> str:
    if type(content) is not bytes:
        raise TypeError("git blob identity requires exact bytes")
    return hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + b"\0" + content,
        usedforsecurity=False,
    ).hexdigest()


class PublicationApplication:
    def __init__(self, dependencies: PublicationDependencies) -> None:
        self._dependencies = dependencies

    def run(self, admission: PublicationAdmissionV1) -> PublicationApplicationResult:
        if type(admission) is not PublicationAdmissionV1:
            raise TypeError("publication requires an admitted canonical input")
        validate_reviewer_targets(reviewers=admission.intent.reviewers)
        store = self._dependencies.state_factory()
        try:
            attempt = store.begin_attempt(admission.intent)
            remote = self._dependencies.remote_factory()
            try:
                catalog = remote.get_catalog()
                if (
                    catalog.repository_id,
                    catalog.full_name,
                    catalog.default_branch,
                ) != (
                    admission.catalog_repository_id,
                    admission.catalog_full_name,
                    admission.intent.base_branch,
                ):
                    return self._manual("catalog_mismatch")
                base = remote.get_base_ref()
                pulls = remote.list_open_pulls(
                    admission.head_branch, admission.intent.base_branch
                )
                if len(pulls) > 1:
                    return self._manual("ambiguous_open_drafts")
                ref = self._maybe_ref(remote)
                if pulls:
                    return self._reconcile_existing(
                        admission,
                        store,
                        remote,
                        base.sha,
                        ref,
                        pulls[0],
                        attempt.record,
                    )
                if ref is not None:
                    return self._manual("unowned_machine_ref")
                if attempt.record is not None:
                    return self._manual("completed_remote_state_missing")
                return self._create(admission, store, remote, base.sha)
            finally:
                close = getattr(remote, "close", None)
                if callable(close):
                    close()
        finally:
            store.close()

    @staticmethod
    def _maybe_ref(remote: object) -> object | None:
        from skillscout.adapters.github_publish import RefNotFound

        try:
            return remote.get_ref()
        except RefNotFound:
            return None

    @staticmethod
    def _manual(code: str) -> PublicationApplicationResult:
        return PublicationApplicationResult("manual_intervention_required", code)

    def _reconcile_existing(
        self,
        admission: PublicationAdmissionV1,
        store: PublicationStateStore,
        remote: object,
        base_sha: str,
        ref: object | None,
        pull: object,
        completed: PublicationRecordV1 | None,
    ) -> PublicationApplicationResult:
        if (
            ref is None
            or not getattr(pull, "draft", False)
            or getattr(pull, "head", None) != admission.head_branch
            or getattr(pull, "base", None) != admission.intent.base_branch
            or getattr(pull, "head_sha", None) != ref.sha
            or getattr(pull, "base_sha", None) != base_sha
        ):
            return self._manual("pull_or_ref_inconsistent")
        commit = remote.get_commit(ref.sha)
        try:
            marker = parse_publication_marker(getattr(pull, "body", "") or "", catalog_authority=self._catalog_authority(admission))
        except Exception:
            return self._manual("marker_invalid")
        if not self._marker_owns_admission(marker, admission):
            return self._manual("marker_identity_inconsistent")
        if not self._validate_machine_lineage(
            admission, remote, base_sha, commit, marker
        ):
            return self._manual("machine_lineage_inconsistent")
        if not self._reviewers_are_durable(admission, remote, pull.number):
            return self._manual("reviewer_evidence_missing")
        tree = remote.get_tree(commit.tree_sha, recursive=True)
        desired = self._desired_tree(admission)
        observed = {entry.path: entry.sha for entry in tree}
        if (
            marker.desired_revision == admission.desired_revision
            and marker.package_digest == admission.evidence.package_digest
            and observed == desired
        ):
            verified = self._verify_remote(
                admission,
                remote,
                base_sha=base_sha,
                commit_sha=ref.sha,
                pull_number=pull.number,
                marker=marker,
            )
            if verified is None:
                return self._manual("remote_verification_failed")
            return self._persist_verified(
                admission,
                store,
                verified,
                marker,
                completed=completed,
                disposition="draft_reused",
                code=(
                    "revalidated_completed"
                    if completed is not None
                    else "reconstructed_remote_completion"
                ),
                remote_writes=0,
            )
        if completed is not None:
            return self._manual("completed_remote_state_changed")
        return self._update(admission, store, remote, base_sha, ref, pull, tree, marker)

    @staticmethod
    def _catalog_authority(admission: PublicationAdmissionV1) -> object:
        from skillscout.domain.publication import CatalogAuthorityV1
        return CatalogAuthorityV1(schema_version="catalog-authority-v1", catalog_repository_id=admission.catalog_repository_id, catalog_full_name=admission.catalog_full_name, base_branch=admission.intent.base_branch, catalog_root="skills")

    @staticmethod
    def _desired_tree(admission: PublicationAdmissionV1) -> dict[str, str]:
        return {
            f"skills/{admission.evidence.stable_slug}/{file.path}": _git_blob_object_id(
                file.content
            )
            for file in admission.evidence.files
        }

    @staticmethod
    def _marker_owns_admission(
        marker: PublicationMarkerV1, admission: PublicationAdmissionV1
    ) -> bool:
        return (
            marker.publication_key,
            marker.stable_slug,
            marker.target_root,
            marker.head_branch,
            marker.reviewers,
        ) == (
            admission.publication_key,
            admission.evidence.stable_slug,
            admission.intent.target_root,
            admission.head_branch,
            admission.intent.reviewers,
        )

    @staticmethod
    def _machine_trailers(message: str) -> dict[str, str] | None:
        if type(message) is not str or len(message) > 4_096:
            return None
        trailers: dict[str, str] = {}
        allowed = {
            "SkillScout-Publication",
            "Publication-Key",
            "Desired-Revision",
            "Prior-Marker-Digest",
        }
        for line in message.splitlines():
            if ": " not in line:
                continue
            key, value = line.split(": ", 1)
            if key in allowed:
                if key in trailers or not value:
                    return None
                trailers[key] = value
        return trailers if set(trailers) == allowed else None

    def _validate_machine_lineage(
        self,
        admission: PublicationAdmissionV1,
        remote: object,
        base_sha: str,
        commit: object,
        marker: PublicationMarkerV1,
    ) -> bool:
        if (
            getattr(commit, "sha", None) != marker.machine_commit_sha
            or getattr(commit, "parent_sha", None) != marker.machine_parent_sha
        ):
            return False
        trailers = self._machine_trailers(getattr(commit, "message", ""))
        expected_prior = marker.prior_marker_digest or "none"
        if trailers is None or trailers != {
            "SkillScout-Publication": "v1",
            "Publication-Key": admission.publication_key,
            "Desired-Revision": marker.desired_revision,
            "Prior-Marker-Digest": expected_prior,
        }:
            return False
        if (marker.prior_marker_digest is None) != (marker.machine_parent_sha == base_sha):
            return False
        cursor = commit
        seen = {marker.machine_commit_sha}
        for _ in range(32):
            parent_sha = getattr(cursor, "parent_sha", None)
            if parent_sha == base_sha:
                return True
            if type(parent_sha) is not str or parent_sha in seen:
                return False
            seen.add(parent_sha)
            cursor = remote.get_commit(parent_sha)
            parent_trailers = self._machine_trailers(getattr(cursor, "message", ""))
            if (
                parent_trailers is None
                or parent_trailers["SkillScout-Publication"] != "v1"
                or parent_trailers["Publication-Key"] != admission.publication_key
            ):
                return False
        return False

    @staticmethod
    def _reviewers_are_durable(
        admission: PublicationAdmissionV1,
        remote: object,
        number: int,
    ) -> bool:
        requested = getattr(
            remote.get_requested_reviewers(number), "users", None
        )
        if (
            type(requested) is not tuple
            or any(
                type(login) is not str
                or _LOGIN_RE.fullmatch(login) is None
                for login in requested
            )
            or requested != tuple(sorted(requested))
            or len(set(requested)) != len(requested)
        ):
            return False
        reviews = remote.list_reviews(number)
        if type(reviews) is not tuple:
            return False
        completed: set[str] = set()
        review_ids: set[int] = set()
        for row in reviews:
            if type(row) is not tuple or len(row) != 4:
                return False
            login, review_id, review_commit, state = row
            if (
                type(login) is not str
                or _LOGIN_RE.fullmatch(login) is None
                or type(review_id) is not int
                or review_id <= 0
                or review_id in review_ids
                or type(review_commit) is not str
                or _SHA_RE.fullmatch(review_commit) is None
                or type(state) is not str
                or state not in _COMPLETED_REVIEW_STATES
            ):
                return False
            review_ids.add(review_id)
            if login in admission.intent.reviewers:
                completed.add(login)
        return all(
            login in requested or login in completed
            for login in admission.intent.reviewers
        )

    def _write_commit(
        self,
        admission: PublicationAdmissionV1,
        store: PublicationStateStore,
        remote: object,
        parent_sha: str,
        base_tree: str,
        existing: Iterable[object],
        *,
        prior_marker_digest: str | None,
    ) -> str:
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
        trailer = (
            "SkillScout-Publication: v1\n"
            f"Publication-Key: {admission.publication_key}\n"
            f"Desired-Revision: {admission.desired_revision}\n"
            f"Prior-Marker-Digest: {prior_marker_digest or 'none'}"
        )
        commit = remote.create_commit(f"skillscout: update {admission.evidence.stable_slug}\n\n{trailer}", tree, [parent_sha])
        store.append_checkpoint(admission.intent, step="commit_created", status_class="success", remote_sha=commit)
        return commit

    def _create(self, admission: PublicationAdmissionV1, store: PublicationStateStore, remote: object, base_sha: str) -> PublicationApplicationResult:
        base_commit = remote.get_commit(base_sha)
        commit = self._write_commit(
            admission,
            store,
            remote,
            base_sha,
            base_commit.tree_sha,
            (),
            prior_marker_digest=None,
        )
        visible = remote.create_machine_ref(commit)
        if getattr(visible, "sha", None) != commit:
            return self._manual("ref_write_not_visible")
        store.append_checkpoint(admission.intent, step="ref_visible", status_class="success", remote_sha=commit)
        marker = PublicationMarkerV1.from_admission(
            admission=admission,
            machine_commit_sha=commit,
            machine_parent_sha=base_sha,
            prior_marker_digest=None,
        )
        pull = remote.create_draft_pull(
            render_pull_request_title(admission),
            render_pull_request_body(
                admission,
                machine_commit_sha=commit,
                machine_parent_sha=base_sha,
                prior_marker_digest=None,
            ),
        )
        store.append_checkpoint(admission.intent, step="draft_visible", status_class="success", remote_id=str(pull.number), remote_sha=commit)
        remote.request_reviewers(pull.number, admission.intent.reviewers)
        requested = remote.get_requested_reviewers(pull.number).users
        if any(login not in requested for login in admission.intent.reviewers):
            return PublicationApplicationResult("manual_intervention_required", "reviewer_request_not_visible", remote_writes=1)
        verified = self._verify_remote(
            admission,
            remote,
            base_sha=base_sha,
            commit_sha=commit,
            pull_number=pull.number,
            marker=marker,
        )
        if verified is None:
            return self._manual("remote_verification_failed")
        return self._persist_verified(
            admission,
            store,
            verified,
            marker,
            completed=None,
            disposition="draft_created",
            code="remote_verified",
            remote_writes=len(admission.evidence.files) + 5,
        )

    def _update(self, admission: PublicationAdmissionV1, store: PublicationStateStore, remote: object, base_sha: str, ref: object, pull: object, tree: Iterable[object], prior_marker: PublicationMarkerV1) -> PublicationApplicationResult:
        # Only a fast-forward from the exact verified machine head is allowed.
        commit = self._write_commit(
            admission,
            store,
            remote,
            ref.sha,
            remote.get_commit(ref.sha).tree_sha,
            tree,
            prior_marker_digest=prior_marker.marker_digest,
        )
        visible = remote.update_machine_ref(commit)
        if getattr(visible, "sha", None) != commit:
            return self._manual("ref_write_not_visible")
        store.append_checkpoint(admission.intent, step="ref_visible", status_class="success", remote_sha=commit)
        marker = PublicationMarkerV1.from_admission(
            admission=admission,
            machine_commit_sha=commit,
            machine_parent_sha=ref.sha,
            prior_marker_digest=prior_marker.marker_digest,
        )
        remote.update_draft_pull(
            pull.number,
            render_pull_request_title(admission),
            render_pull_request_body(
                admission,
                machine_commit_sha=commit,
                machine_parent_sha=ref.sha,
                prior_marker_digest=prior_marker.marker_digest,
            ),
        )
        store.append_checkpoint(admission.intent, step="draft_visible", status_class="success", remote_id=str(pull.number), remote_sha=commit)
        verified = self._verify_remote(
            admission,
            remote,
            base_sha=base_sha,
            commit_sha=commit,
            pull_number=pull.number,
            marker=marker,
        )
        if verified is None:
            return self._manual("remote_verification_failed")
        return self._persist_verified(
            admission,
            store,
            verified,
            marker,
            completed=None,
            disposition="draft_updated",
            code="remote_verified",
            remote_writes=len(admission.evidence.files) + 4,
        )

    def _verify_remote(
        self,
        admission: PublicationAdmissionV1,
        remote: object,
        *,
        base_sha: str,
        commit_sha: str,
        pull_number: int,
        marker: PublicationMarkerV1,
    ) -> object | None:
        catalog = remote.get_catalog()
        if (
            catalog.repository_id,
            catalog.full_name,
            catalog.default_branch,
        ) != (
            admission.catalog_repository_id,
            admission.catalog_full_name,
            admission.intent.base_branch,
        ):
            return None
        observed_base = remote.get_base_ref()
        if observed_base.sha != base_sha:
            return None
        observed_ref = self._maybe_ref(remote)
        if observed_ref is None or observed_ref.sha != commit_sha:
            return None
        commit = remote.get_commit(commit_sha)
        if not self._validate_machine_lineage(
            admission, remote, base_sha, commit, marker
        ):
            return None
        observed_tree = {
            item.path: item.sha
            for item in remote.get_tree(commit.tree_sha, recursive=True)
        }
        if observed_tree != self._desired_tree(admission):
            return None
        pulls = remote.list_open_pulls(
            admission.head_branch, admission.intent.base_branch
        )
        if len(pulls) != 1:
            return None
        pull = pulls[0]
        if (
            pull.number != pull_number
            or not pull.draft
            or pull.head != admission.head_branch
            or pull.base != admission.intent.base_branch
            or pull.head_sha != commit_sha
            or pull.base_sha != base_sha
        ):
            return None
        try:
            observed_marker = parse_publication_marker(
                pull.body or "", catalog_authority=self._catalog_authority(admission)
            )
        except Exception:
            return None
        if observed_marker != marker:
            return None
        if not self._reviewers_are_durable(admission, remote, pull_number):
            return None
        return pull

    def _persist_verified(
        self,
        admission: PublicationAdmissionV1,
        store: PublicationStateStore,
        pull: object,
        marker: PublicationMarkerV1,
        *,
        completed: PublicationRecordV1 | None,
        disposition: Literal["draft_created", "draft_updated", "draft_reused"],
        code: str,
        remote_writes: int,
    ) -> PublicationApplicationResult:
        record = PublicationRecordV1(
            schema_version="publication-record-v1",
            publication_key=admission.publication_key,
            desired_revision=admission.desired_revision,
            marker_digest=marker.marker_digest,
            commit_sha=marker.machine_commit_sha,
            pull_number=pull.number,
            pull_url=pull.url,
            disposition=disposition,
        )
        if completed is not None:
            if (
                completed.publication_key,
                completed.desired_revision,
                completed.marker_digest,
                completed.commit_sha,
                completed.pull_number,
                completed.pull_url,
            ) != (
                record.publication_key,
                record.desired_revision,
                record.marker_digest,
                record.commit_sha,
                record.pull_number,
                record.pull_url,
            ):
                return self._manual("completed_record_mismatch")
            return PublicationApplicationResult(
                "published",
                code,
                completed,
                "draft_reused",
                completed.commit_sha,
                completed.pull_number,
                completed.pull_url,
                remote_writes,
            )
        store.append_checkpoint(
            admission.intent,
            step="remote_verified",
            status_class="success",
            remote_id=str(pull.number),
            remote_sha=marker.machine_commit_sha,
        )
        store.complete(admission.intent, record)
        return PublicationApplicationResult(
            "published",
            code,
            record,
            disposition,
            record.commit_sha,
            record.pull_number,
            record.pull_url,
            remote_writes,
        )
