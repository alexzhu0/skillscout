"""Stateful recovery tests for the real controlled-publication application."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from skillscout.adapters.github_publish import RefNotFound
from skillscout.adapters.publication_state import PublicationStateStore
from skillscout.application.publication import (
    PublicationApplication,
    PublicationDependencies,
    _git_blob_object_id,
)
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.publication import (
    CandidatePublicationEvidenceV1,
    CatalogAuthorityV1,
    PublicationFileV1,
    PublicationRecordV1,
    ReviewerTargetsV1,
    bind_publication_admission,
    derive_publication_intent,
    parse_publication_marker,
)


def _admission(*, revision: int = 1) -> Any:
    skill = f"---\nname: bounded-workflow\n---\nrevision {revision}\n".encode()
    provenance = (
        b'{"repository":"source-org/bounded-workflow","revision":'
        + str(revision).encode()
        + b"}"
    )
    files = tuple(
        PublicationFileV1(
            path=path,
            content_hash=sha256_digest(content),
            mode=420,
            size=len(content),
            content=content,
        )
        for path, content in (
            ("SKILL.md", skill),
            ("references/provenance.json", provenance),
        )
    )
    package_digest = sha256_digest(
        {item.path: item.content_hash for item in files}
    )
    evidence = CandidatePublicationEvidenceV1(
        schema_version="candidate-publication-evidence-v1",
        stable_slug="bounded-workflow",
        repository_id=101,
        repository_full_name="source-org/bounded-workflow",
        repository_url="https://github.com/source-org/bounded-workflow",
        exact_commit_sha="a" * 40,
        license_spdx="MIT",
        workflow_fingerprint="sha256:" + "1" * 64,
        package_digest=package_digest,
        rendered_manifest_digest="sha256:" + "3" * 64,
        qualification_report_digest="sha256:" + "4" * 64,
        validation_report_digest="sha256:" + "5" * 64,
        review_attestation_digest="sha256:" + "6" * 64,
        qualification_passed=True,
        validation_error_count=0,
        review_verdict="YES",
        review_confidence=0.9,
        files=files,
        evidence_digest=sha256_digest(
            {"package_digest": package_digest, "revision": revision}
        ),
    )
    authority = CatalogAuthorityV1(
        schema_version="catalog-authority-v1",
        catalog_repository_id=202,
        catalog_full_name="catalog-org/skills",
        base_branch="main",
        catalog_root="skills",
    )
    intent = derive_publication_intent(
        evidence=evidence,
        catalog_authority=authority,
        reviewer_targets=ReviewerTargetsV1(
            schema_version="reviewer-targets-v1",
            reviewers=("alpha-reviewer",),
        ),
    )
    return bind_publication_admission(
        evidence=evidence,
        intent=intent,
        catalog_authority=authority,
    )


class StatefulRemote:
    """Small remote truth model that applies the production operation protocol."""

    def __init__(self) -> None:
        self.base_sha = "1" * 40
        self.base_tree = "2" * 40
        self.commits: dict[str, Any] = {
            self.base_sha: SimpleNamespace(
                sha=self.base_sha,
                tree_sha=self.base_tree,
                parent_sha=None,
                message="catalog base",
            )
        }
        self.trees: dict[str, dict[str, str]] = {self.base_tree: {}}
        self.ref_sha: str | None = None
        self.last_ref_request: str | None = None
        self.pull: Any | None = None
        self.requested: set[str] = set()
        self.reviews: list[tuple[str, int, str, str]] = []
        self.writes: list[tuple[str, object]] = []
        self.deleted_paths: list[str] = []
        self.close_calls = 0
        self.ref_error: BaseException | None = None
        self.suppress_ref_visibility = False
        self._counter = 10

    def _sha(self) -> str:
        self._counter += 1
        return f"{self._counter:040x}"

    def close(self) -> None:
        self.close_calls += 1

    def get_catalog(self) -> Any:
        return SimpleNamespace(
            repository_id=202,
            full_name="catalog-org/skills",
            default_branch="main",
        )

    def get_base_ref(self) -> Any:
        return SimpleNamespace(ref="refs/heads/main", sha=self.base_sha)

    def get_ref(self) -> Any:
        if self.ref_error is not None:
            raise self.ref_error
        if self.ref_sha is None:
            raise RefNotFound
        return SimpleNamespace(
            ref="refs/heads/skillscout/bounded-workflow", sha=self.ref_sha
        )

    def get_commit(self, sha: str) -> Any:
        return self.commits[sha]

    def get_tree(self, sha: str, recursive: bool = True) -> tuple[Any, ...]:
        assert recursive is True
        return tuple(
            SimpleNamespace(path=path, sha=value, mode="100644")
            for path, value in sorted(self.trees[sha].items())
        )

    def list_open_pulls(self, head: str, base: str) -> tuple[Any, ...]:
        assert head == "skillscout/bounded-workflow"
        assert base == "main"
        return () if self.pull is None else (self.pull,)

    def get_requested_reviewers(self, number: int) -> Any:
        assert self.pull is not None and number == self.pull.number
        return SimpleNamespace(users=tuple(sorted(self.requested)))

    def list_reviews(self, number: int) -> tuple[tuple[str, int, str, str], ...]:
        assert self.pull is not None and number == self.pull.number
        return tuple(self.reviews)

    def create_blob(self, content: bytes) -> str:
        sha = _git_blob_object_id(content)
        self.writes.append(("blob", sha))
        return sha

    def create_tree(self, base_tree: str, entries: list[dict[str, object]]) -> str:
        tree = dict(self.trees[base_tree])
        for entry in entries:
            path = str(entry["path"])
            if entry["sha"] is None:
                tree.pop(path, None)
                self.deleted_paths.append(path)
            else:
                tree[path] = str(entry["sha"])
        sha = self._sha()
        self.trees[sha] = tree
        self.writes.append(("tree", sha))
        return sha

    def create_commit(
        self, message: str, tree: str, parents: list[str]
    ) -> str:
        sha = self._sha()
        self.commits[sha] = SimpleNamespace(
            sha=sha,
            tree_sha=tree,
            parent_sha=parents[0],
            message=message,
        )
        self.writes.append(("commit", sha))
        return sha

    def create_machine_ref(self, sha: str) -> Any:
        self.last_ref_request = sha
        if not self.suppress_ref_visibility:
            self.ref_sha = sha
        self.writes.append(("create_ref", sha))
        return SimpleNamespace(
            ref="refs/heads/skillscout/bounded-workflow", sha=sha
        )

    def update_machine_ref(self, sha: str) -> Any:
        self.last_ref_request = sha
        if not self.suppress_ref_visibility:
            self.ref_sha = sha
        self.writes.append(("update_ref", sha))
        return SimpleNamespace(
            ref="refs/heads/skillscout/bounded-workflow", sha=sha
        )

    def _pull_observation(self, body: str) -> Any:
        head_sha = self.ref_sha or self.last_ref_request
        assert head_sha is not None
        return SimpleNamespace(
            number=42,
            draft=True,
            head="skillscout/bounded-workflow",
            base="main",
            body=body,
            head_sha=head_sha,
            base_sha=self.base_sha,
            url="https://github.com/catalog-org/skills/pull/42",
        )

    def create_draft_pull(self, title: str, body: str) -> Any:
        assert title == "Draft: add bounded-workflow skill"
        self.pull = self._pull_observation(body)
        self.writes.append(("create_pull", 42))
        return self.pull

    def update_draft_pull(self, number: int, title: str, body: str) -> Any:
        assert number == 42
        assert title == "Draft: add bounded-workflow skill"
        self.pull = self._pull_observation(body)
        self.writes.append(("update_pull", 42))
        return self.pull

    def request_reviewers(self, number: int, reviewers: tuple[str, ...]) -> Any:
        assert number == 42
        self.requested.update(reviewers)
        self.writes.append(("request_reviewers", reviewers))
        return SimpleNamespace(users=tuple(sorted(self.requested)))


def _application(
    state_path: Path,
    remote: StatefulRemote,
    *,
    state_factory: Any | None = None,
) -> PublicationApplication:
    return PublicationApplication(
        PublicationDependencies(
            state_factory=state_factory or (lambda: PublicationStateStore(state_path)),
            remote_factory=lambda: remote,
        )
    )


def _run(
    tmp_path: Path,
    remote: StatefulRemote,
    admission: Any,
    *,
    state_name: str = "publication.db",
) -> Any:
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700, exist_ok=True)
    return _application(state_dir / state_name, remote).run(admission)


def test_remote_tree_reconciliation_uses_git_blob_object_ids() -> None:
    assert _git_blob_object_id(b"test content\n") == (
        "d670460b4b4aece5915caf5c68d12f560a9fe3e4"
    )
    assert len(_git_blob_object_id(b"candidate bytes")) == 40


def test_create_revalidates_remote_and_persists_the_exact_written_marker(
    tmp_path: Path,
) -> None:
    admission = _admission()
    remote = StatefulRemote()

    result = _run(tmp_path, remote, admission)

    assert result.status == "published"
    assert result.disposition == "draft_created"
    assert result.commit_sha == remote.ref_sha
    assert result.pull_number == 42
    assert result.pull_url == "https://github.com/catalog-org/skills/pull/42"
    marker = parse_publication_marker(
        remote.pull.body,
        catalog_authority=CatalogAuthorityV1(
            schema_version="catalog-authority-v1",
            catalog_repository_id=202,
            catalog_full_name="catalog-org/skills",
            base_branch="main",
            catalog_root="skills",
        ),
    )
    assert marker.machine_commit_sha == remote.ref_sha
    assert marker.machine_parent_sha == remote.base_sha
    assert result.record is not None
    assert result.record.marker_digest == marker.marker_digest
    assert result.record.commit_sha == remote.ref_sha


def test_completed_intent_is_remotely_revalidated_without_reopening_ledger(
    tmp_path: Path,
) -> None:
    admission = _admission()
    remote = StatefulRemote()
    created = _run(tmp_path, remote, admission)
    write_count = len(remote.writes)

    reused = _run(tmp_path, remote, admission)

    assert created.record is not None
    assert reused.status == "published"
    assert reused.code == "revalidated_completed"
    assert reused.disposition == "draft_reused"
    assert reused.record == created.record
    assert len(remote.writes) == write_count
    assert remote.close_calls == 2
    store = PublicationStateStore(tmp_path / "state" / "publication.db")
    assert store.find_completed(admission.intent) == created.record
    assert store.find_pending(admission.intent) is None
    store.close()


def test_local_state_loss_reconstructs_exact_remote_completion_without_writes(
    tmp_path: Path,
) -> None:
    admission = _admission()
    remote = StatefulRemote()
    _run(tmp_path, remote, admission)
    write_count = len(remote.writes)

    recovered = _run(
        tmp_path,
        remote,
        admission,
        state_name="replacement-publication.db",
    )

    assert recovered.status == "published"
    assert recovered.code == "reconstructed_remote_completion"
    assert recovered.disposition == "draft_reused"
    assert len(remote.writes) == write_count


def test_later_revisions_follow_a_bounded_machine_owned_commit_chain(
    tmp_path: Path,
) -> None:
    remote = StatefulRemote()
    first = _admission(revision=1)
    second = _admission(revision=2)
    third = _admission(revision=3)
    assert first.publication_key == second.publication_key == third.publication_key

    _run(tmp_path, remote, first, state_name="first.db")
    first_head = remote.ref_sha
    updated = _run(tmp_path, remote, second, state_name="second.db")
    second_head = remote.ref_sha
    updated_again = _run(tmp_path, remote, third, state_name="third.db")

    assert updated.disposition == "draft_updated"
    assert updated_again.disposition == "draft_updated"
    assert remote.commits[second_head].parent_sha == first_head
    assert remote.commits[remote.ref_sha].parent_sha == second_head
    marker = parse_publication_marker(
        remote.pull.body,
        catalog_authority=CatalogAuthorityV1(
            schema_version="catalog-authority-v1",
            catalog_repository_id=202,
            catalog_full_name="catalog-org/skills",
            base_branch="main",
            catalog_root="skills",
        ),
    )
    assert marker.prior_marker_digest is not None


def test_completed_reviewer_remains_durable_across_later_revision(
    tmp_path: Path,
) -> None:
    remote = StatefulRemote()
    first = _admission(revision=1)
    second = _admission(revision=2)
    created = _run(tmp_path, remote, first, state_name="first.db")
    assert created.status == "published"
    reviewed_head = remote.ref_sha
    assert reviewed_head is not None
    remote.requested.clear()
    remote.reviews = [
        ("alpha-reviewer", 7001, reviewed_head, "APPROVED")
    ]
    writes_before_update = len(remote.writes)
    notifications_before_update = [
        write for write in remote.writes if write[0] == "request_reviewers"
    ]

    updated = _run(tmp_path, remote, second, state_name="second.db")

    assert updated.status == "published"
    assert updated.code == "remote_verified"
    assert updated.disposition == "draft_updated"
    assert remote.ref_sha != reviewed_head
    assert len(remote.writes) == writes_before_update + 6
    assert [
        write for write in remote.writes if write[0] == "request_reviewers"
    ] == notifications_before_update
    assert remote.requested == set()


@pytest.mark.parametrize(
    "reviews",
    (
        (("other-reviewer", 7001, "a" * 40, "APPROVED"),),
        (("alpha-reviewer", 7001, "a" * 40),),
        (
            ("alpha-reviewer", 7001, "a" * 40, "APPROVED"),
            ("other-reviewer", 7001, "a" * 40, "APPROVED"),
        ),
    ),
    ids=("unconfigured", "malformed", "ambiguous-review-id"),
)
def test_invalid_completed_reviewer_evidence_fails_before_revision_write(
    tmp_path: Path,
    reviews: tuple[tuple[object, ...], ...],
) -> None:
    remote = StatefulRemote()
    first = _admission(revision=1)
    second = _admission(revision=2)
    _run(tmp_path, remote, first, state_name="first.db")
    remote.requested.clear()
    remote.reviews = list(reviews)
    writes_before_update = len(remote.writes)

    result = _run(tmp_path, remote, second, state_name="second.db")

    assert result.status == "manual_intervention_required"
    assert result.code == "reviewer_evidence_missing"
    assert len(remote.writes) == writes_before_update


def test_human_or_force_rewritten_machine_lineage_is_never_overwritten(
    tmp_path: Path,
) -> None:
    admission = _admission()
    remote = StatefulRemote()
    _run(tmp_path, remote, admission)
    assert remote.ref_sha is not None
    current = remote.commits[remote.ref_sha]
    remote.commits[remote.ref_sha] = SimpleNamespace(
        **{
            **vars(current),
            "message": "human commit without machine trailers",
        }
    )
    writes = len(remote.writes)

    result = _run(
        tmp_path,
        remote,
        admission,
        state_name="lost-local-state.db",
    )

    assert result.status == "manual_intervention_required"
    assert result.code == "machine_lineage_inconsistent"
    assert len(remote.writes) == writes


def test_default_branch_drift_rejects_an_otherwise_machine_owned_chain(
    tmp_path: Path,
) -> None:
    admission = _admission()
    remote = StatefulRemote()
    _run(tmp_path, remote, admission)
    writes = len(remote.writes)
    remote.base_sha = "9" * 40

    result = _run(
        tmp_path,
        remote,
        admission,
        state_name="drifted-default.db",
    )

    assert result.status == "manual_intervention_required"
    assert result.code == "pull_or_ref_inconsistent"
    assert len(remote.writes) == writes


def test_transient_ref_read_failure_propagates_with_zero_remote_writes(
    tmp_path: Path,
) -> None:
    admission = _admission()
    remote = StatefulRemote()
    remote.ref_error = TimeoutError("provider timeout")

    with pytest.raises(TimeoutError):
        _run(tmp_path, remote, admission)

    assert remote.writes == []
    assert remote.close_calls == 1


def test_state_store_closes_when_remote_construction_fails(tmp_path: Path) -> None:
    admission = _admission()
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    state_path = state_dir / "publication.db"
    created: list[Any] = []

    class TrackingStore(PublicationStateStore):
        closed = False

        def close(self) -> None:
            self.closed = True
            super().close()

    def state_factory() -> TrackingStore:
        store = TrackingStore(state_path)
        created.append(store)
        return store

    def remote_factory() -> object:
        raise RuntimeError("remote construction failed")

    application = PublicationApplication(
        PublicationDependencies(
            state_factory=state_factory,
            remote_factory=remote_factory,
        )
    )
    with pytest.raises(RuntimeError, match="remote construction failed"):
        application.run(admission)

    assert len(created) == 1
    assert created[0].closed is True


def test_mutation_response_is_not_enough_to_record_success(tmp_path: Path) -> None:
    admission = _admission()
    remote = StatefulRemote()
    remote.suppress_ref_visibility = True

    result = _run(tmp_path, remote, admission)

    assert result.status == "manual_intervention_required"
    assert result.code == "remote_verification_failed"
    state_path = tmp_path / "state" / "publication.db"
    store = PublicationStateStore(state_path)
    assert store.find_completed(admission.intent) is None
    store.close()


def test_stale_owned_files_are_deleted_and_final_tree_is_exact(
    tmp_path: Path,
) -> None:
    remote = StatefulRemote()
    first = _admission(revision=1)
    second = _admission(revision=2)
    _run(tmp_path, remote, first, state_name="first.db")
    current = remote.commits[remote.ref_sha]
    remote.trees[current.tree_sha][
        "skills/bounded-workflow/references/obsolete.md"
    ] = "f" * 40

    result = _run(tmp_path, remote, second, state_name="second.db")

    assert result.status == "published"
    assert remote.deleted_paths == [
        "skills/bounded-workflow/references/obsolete.md"
    ]
    observed = remote.trees[remote.commits[remote.ref_sha].tree_sha]
    assert observed == {
        f"skills/bounded-workflow/{item.path}": _git_blob_object_id(item.content)
        for item in second.evidence.files
    }


def test_remote_success_before_local_commit_recovers_from_pending_state(
    tmp_path: Path,
) -> None:
    admission = _admission()
    remote = StatefulRemote()
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    state_path = state_dir / "publication.db"
    interrupted = False

    class InterruptingStore(PublicationStateStore):
        def complete(
            self, intent: Any, record: PublicationRecordV1
        ) -> None:
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise RuntimeError("crash after remote verification")
            super().complete(intent, record)

    with pytest.raises(RuntimeError, match="crash after remote verification"):
        _application(
            state_path,
            remote,
            state_factory=lambda: InterruptingStore(state_path),
        ).run(admission)
    write_count = len(remote.writes)

    recovered = _application(state_path, remote).run(admission)

    assert recovered.status == "published"
    assert recovered.code == "reconstructed_remote_completion"
    assert len(remote.writes) == write_count


def _state_intent() -> Any:
    admission = _admission()
    return admission.intent


def test_state_checkpoints_are_canonical_durable_and_terminal(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    intent = _state_intent()
    store = PublicationStateStore(state_dir / "publication-state.db")
    assert store.find_pending(intent) is None
    store.begin_attempt(intent)
    checkpoint = store.append_checkpoint(
        intent,
        step="reconciled",
        status_class="read",
        request_id="REQ-1",
    )
    assert checkpoint.event_index == 0
    record = PublicationRecordV1(
        schema_version="publication-record-v1",
        publication_key=intent.publication_key,
        desired_revision=intent.desired_revision,
        marker_digest="sha256:" + "d" * 64,
    )
    store.complete(intent, record)
    store.close()
    reopened = PublicationStateStore(state_dir / "publication-state.db")
    assert reopened.find_completed(intent) == record
    reopened.close()


def test_state_rejects_checkpoint_corruption_before_projection(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    intent = _state_intent()
    store = PublicationStateStore(state_dir / "publication-state.db")
    store.begin_attempt(intent)
    store.append_checkpoint(intent, step="reconciled", status_class="read")
    store._conn.execute(
        "UPDATE publication_checkpoints SET checkpoint_json = ?", ("{}",)
    )
    with pytest.raises(Exception):
        store.find_pending(intent)
    store.close()


def test_state_rejects_terminal_record_revision_mismatch(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    intent = _state_intent()
    store = PublicationStateStore(state_dir / "publication-state.db")
    store.begin_attempt(intent)
    mismatched = PublicationRecordV1(
        schema_version="publication-record-v1",
        publication_key=intent.publication_key,
        desired_revision="sha256:" + "d" * 64,
        marker_digest="sha256:" + "e" * 64,
    )
    with pytest.raises(ValueError, match="disagrees with intent"):
        store.complete(intent, mismatched)
    store.close()
