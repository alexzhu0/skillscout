"""Remote-confirmed semantic durability contract and state-branch barrier tests."""

from __future__ import annotations

from dataclasses import fields
import hashlib
import importlib
import inspect
from pathlib import Path

import pytest

from skillscout.domain.canonical import sha256_digest


DIGEST_A = "sha256:" + ("a" * 64)
DIGEST_B = "sha256:" + ("b" * 64)
DIGEST_C = "sha256:" + ("c" * 64)
PRIOR_HEAD = "d" * 40
STATE_SHA = "e" * 40
STAGES = ("extractor", "generator", "reviewer")
PROVIDERS = ("openai", "deepseek")
TRANSITIONS = (
    "attempt_started",
    "result_decided",
    "result_confirmed_retryable",
    "result_outcome_unknown",
)


def _ports():
    return importlib.import_module("skillscout.application.ports")


def _transition(
    *,
    provider: str = "openai",
    stage: str = "extractor",
    attempt_no: int = 1,
    transition: str = "attempt_started",
):
    return _ports().SemanticDurabilityTransition.create(
        run_id="discovery-run-1",
        repository_id=101,
        workflow_authority_digest=DIGEST_A,
        provider=provider,
        stage=stage,
        attempt_no=attempt_no,
        recorded_at="2026-07-27T12:00:00.000000Z",
        transition=transition,
        expected_prior_state_head=PRIOR_HEAD,
        expected_prior_root_digest=DIGEST_B,
        pipeline_export_digest=DIGEST_A,
        operations_export_digest=DIGEST_B,
        publication_export_digest=DIGEST_C,
    )


def _receipt(request=None):
    module = _ports()
    transition = request or _transition()
    return module.DurabilityReceipt.from_remote_verification(
        transition=transition,
        verified_state_head=STATE_SHA,
        state_root_digest="sha256:" + ("f" * 64),
        pipeline_database_digest="sha256:" + ("1" * 64),
        operations_database_digest="sha256:" + ("2" * 64),
        publication_database_digest="sha256:" + ("3" * 64),
        pipeline_projection_digest="sha256:" + ("4" * 64),
        operations_projection_digest="sha256:" + ("5" * 64),
        publication_projection_digest="sha256:" + ("6" * 64),
    )


def test_contract_matrix_covers_two_providers_three_stages_and_four_transitions() -> None:
    matrix = {
        (provider, stage, transition)
        for provider in PROVIDERS
        for stage in STAGES
        for transition in TRANSITIONS
    }
    assert len(matrix) == 24
    for provider, stage, transition in matrix:
        request = _transition(
            provider=provider,
            stage=stage,
            transition=transition,
        )
        assert (request.provider, request.stage, request.transition) == (
            provider,
            stage,
            transition,
        )


def test_transition_authority_is_self_hashed_and_has_no_untrusted_payload_surface() -> None:
    module = _ports()
    request = _transition()
    assert request.transition_authority_digest.startswith("sha256:")
    assert module.SemanticDurabilityTransition.from_dict(
        request.as_dict()
    ) == request
    exposed = {field.name for field in fields(request)}
    assert not exposed.intersection(
        {
            "provider_payload",
            "provider_response",
            "repository_text",
            "exception",
            "error_message",
            "token",
            "secret",
        }
    )

    tampered = request.as_dict()
    tampered["attempt_no"] = 2
    with pytest.raises(ValueError, match="transition authority"):
        module.SemanticDurabilityTransition.from_dict(tampered)


def test_transition_separates_execution_and_operations_run_identity() -> None:
    transition = _ports().SemanticDurabilityTransition.create(
        run_id="phase3-execution-1",
        operations_run_id="discovery-operations-1",
        repository_id=101,
        workflow_authority_digest=DIGEST_A,
        provider="openai",
        stage="generator",
        attempt_no=1,
        recorded_at="2026-07-27T12:00:00.000000Z",
        transition="attempt_started",
        expected_prior_state_head="a" * 40,
        expected_prior_root_digest=DIGEST_B,
        pipeline_export_digest=DIGEST_A,
        operations_export_digest=DIGEST_B,
        publication_export_digest=DIGEST_C,
    )

    assert transition.run_id == "phase3-execution-1"
    assert transition.operations_run_id == "discovery-operations-1"
    assert transition.transition_authority_digest == sha256_digest(
        transition.as_dict(exclude_authority=True)
    )


@pytest.mark.parametrize("provider", ("", "OPENAI", "other", None))
def test_transition_rejects_invalid_provider(provider: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _ports().SemanticDurabilityTransition.create(
            run_id="discovery-run-1",
            repository_id=101,
            workflow_authority_digest=DIGEST_A,
            provider=provider,
            stage="extractor",
            attempt_no=1,
            recorded_at="2026-07-27T12:00:00.000000Z",
            transition="attempt_started",
            expected_prior_state_head=PRIOR_HEAD,
            expected_prior_root_digest=DIGEST_B,
            pipeline_export_digest=DIGEST_A,
            operations_export_digest=DIGEST_B,
            publication_export_digest=DIGEST_C,
        )


@pytest.mark.parametrize(
    ("stage", "attempt_no", "transition"),
    (
        ("scout", 1, "attempt_started"),
        ("extractor", 0, "attempt_started"),
        ("extractor", 17, "attempt_started"),
        ("extractor", 1, "started"),
        ("reviewer", 1, "result_retryable"),
    ),
)
def test_transition_rejects_invalid_stage_attempt_and_transition_combinations(
    stage: str,
    attempt_no: int,
    transition: str,
) -> None:
    with pytest.raises(ValueError):
        _transition(
            stage=stage,
            attempt_no=attempt_no,
            transition=transition,
        )


def test_receipt_binds_parent_root_transition_and_all_three_stores() -> None:
    request = _transition()
    receipt = _receipt(request)
    assert receipt.authorizes(request)
    assert receipt.verified_state_head == STATE_SHA
    assert receipt.expected_prior_state_head == PRIOR_HEAD
    assert receipt.transition_authority_digest == (
        request.transition_authority_digest
    )
    assert receipt.database_digests == (
        "sha256:" + ("1" * 64),
        "sha256:" + ("2" * 64),
        "sha256:" + ("3" * 64),
    )


@pytest.mark.parametrize(
    "field",
    (
        "transition_authority_digest",
        "expected_prior_state_head",
        "expected_prior_root_digest",
        "pipeline_export_digest",
        "operations_export_digest",
        "publication_export_digest",
    ),
)
def test_incomplete_or_mismatched_receipt_never_grants_authority(
    field: str,
) -> None:
    module = _ports()
    request = _transition()
    receipt = _receipt(request)
    changed = request.as_dict()
    changed[field] = (
        "a" * 40
        if field == "expected_prior_state_head"
        else "sha256:" + ("9" * 64)
    )
    if field != "transition_authority_digest":
        changed.pop("transition_authority_digest")
        changed.pop("schema_version")
        other = module.SemanticDurabilityTransition.create(**changed)
    else:
        with pytest.raises(ValueError):
            module.SemanticDurabilityTransition.from_dict(changed)
        return
    assert receipt.authorizes(other) is False
    assert module.receipt_authorizes(other, receipt) is False
    with pytest.raises(module.SafeFailure) as failure:
        module.require_durability_receipt(other, receipt)
    assert failure.value.code is module.ErrorCode.STATE_OPERATION_FAILED


def test_missing_receipt_and_malformed_receipt_fail_with_closed_sanitized_error() -> None:
    module = _ports()
    request = _transition()
    for receipt in (None, object()):
        assert module.receipt_authorizes(request, receipt) is False
        with pytest.raises(module.SafeFailure) as failure:
            module.require_durability_receipt(request, receipt)
        assert failure.value.as_dict() == {
            "code": "state_operation_failed",
            "summary": "Local state operation failed.",
        }


def test_barrier_port_is_narrow_and_runtime_checkable() -> None:
    module = _ports()

    class Barrier:
        def confirm(self, *, transition, pipeline_store, operations_store, publication_store):
            del pipeline_store, operations_store, publication_store
            return _receipt(transition)

    assert isinstance(Barrier(), module.ThreeStoreDurabilityBarrier)
    parameters = inspect.signature(
        module.ThreeStoreDurabilityBarrier.confirm
    ).parameters
    assert tuple(parameters) == (
        "self",
        "transition",
        "pipeline_store",
        "operations_store",
        "publication_store",
    )


def test_receipt_digest_detects_forged_remote_confirmation() -> None:
    module = _ports()
    receipt = _receipt()
    raw = receipt.as_dict()
    raw["verified_state_head"] = "9" * 40
    with pytest.raises(ValueError, match="receipt digest"):
        module.DurabilityReceipt.from_dict(raw)
    assert hashlib.sha256(receipt.receipt_digest.encode("ascii")).digest()


def _state_branch():
    return importlib.import_module("skillscout.adapters.state_branch")


class _Remote:
    def __init__(
        self,
        module,
        *,
        prior_bundle,
        head: str = PRIOR_HEAD,
        fail_at: str | None = None,
    ):
        self.module = module
        self.head = head
        self.fail_at = fail_at
        self.blobs: dict[str, bytes] = {}
        self.trees: dict[str, tuple[object, ...]] = {}
        self.commits: dict[str, object] = {}
        self.counter = 100
        self.force_values: list[bool] = []
        self.provider_requests = 0
        self.retry_or_terminal = 0
        self._rereading = False
        for item in prior_bundle.files:
            self.blobs[module._git_blob_id(item.content)] = item.content
        prior_tree = "b" * 40
        self.trees[prior_tree] = tuple(
            module.StateTreeEntry(
                path=item.path,
                sha=module._git_blob_id(item.content),
                mode="100644",
                size=len(item.content),
            )
            for item in prior_bundle.files
        )
        self.commits[head] = module.StateCommitObservation(
            sha=head,
            tree_sha=prior_tree,
            parents=("c" * 40,),
            message="skillscout: prior state",
        )

    def _sha(self) -> str:
        self.counter += 1
        return f"{self.counter:040x}"

    def get_state_ref(self):
        if self.fail_at == "reread" and self._rereading:
            raise RuntimeError("SECRET remote reread payload")
        return self.module.StateRefObservation(self.module.STATE_REF, self.head)

    def create_blob(self, content: bytes) -> str:
        if self.fail_at == "blob":
            raise RuntimeError("SECRET pipeline export")
        sha = self.module._git_blob_id(content)
        self.blobs[sha] = content
        return sha

    def create_tree(self, entries):
        sha = self._sha()
        self.trees[sha] = tuple(
            self.module.StateTreeEntry(
                path=str(entry["path"]),
                sha=str(entry["sha"]),
                mode="100644",
                size=len(self.blobs[str(entry["sha"])]),
            )
            for entry in entries
        )
        return sha

    def create_commit(self, message: str, tree: str, parents: tuple[str, ...]):
        sha = self._sha()
        self.commits[sha] = self.module.StateCommitObservation(
            sha=sha,
            tree_sha=tree,
            parents=parents,
            message=message,
        )
        return sha

    def update_state_ref(self, sha: str, *, force: bool):
        self.force_values.append(force)
        if self.fail_at == "cas":
            raise self.module.StateBranchConflict
        self.head = sha
        self._rereading = True
        return self.module.StateRefObservation(self.module.STATE_REF, sha)

    def create_state_ref(self, sha: str):
        raise AssertionError("semantic durability never bootstraps an absent branch")

    def get_commit(self, sha: str):
        return self.commits[sha]

    def get_tree(self, sha: str):
        return self.trees[sha]

    def get_blob(self, sha: str) -> bytes:
        content = self.blobs[sha]
        if self.fail_at == "projection" and self._rereading:
            return content + b"x"
        return content


class _ExportFailure:
    def __init__(self, wrapped, *, fail: bool):
        self.wrapped = wrapped
        self.fail = fail

    def export_owned_state(self):
        if self.fail:
            raise RuntimeError("SECRET export failure")
        return self.wrapped.export_owned_state()


def _owned_stores(
    tmp_path: Path,
    *,
    stage: str,
    transition: str,
):
    state_module = importlib.import_module("skillscout.adapters.state")
    operations_module = importlib.import_module(
        "skillscout.adapters.operations_state"
    )
    publication_module = importlib.import_module(
        "skillscout.adapters.publication_state"
    )
    pipeline = state_module.SQLiteStateStore(tmp_path / "pipeline.sqlite3")
    operations = operations_module.OperationsStateStore(
        tmp_path / "operations.sqlite3"
    )
    publication = publication_module.PublicationStateStore(
        tmp_path / "publication.sqlite3"
    )
    operations.seed_test_reservations(
        run_id="discovery-run-1",
        repository_id=101,
    )
    coordinator = importlib.import_module(
        "skillscout.adapters.operations_state"
    )
    prior_bundle, _ = coordinator._bundle_from_exports(
        pipeline=pipeline.export_owned_state(),
        operations=operations.export_owned_state(),
        publication=publication.export_owned_state(),
        prior_root_digest=DIGEST_B,
        state_parent_commit_sha="c" * 40,
        query_set_digest="sha256:" + ("7" * 64),
        budget_policy_digest="sha256:" + ("8" * 64),
        created_at="2026-07-27T11:59:59.000000Z",
    )
    operations.record_semantic_attempt(
        run_id="discovery-run-1",
        repository_id=101,
        workflow_authority_digest=DIGEST_A,
        stage=stage,
        attempt_no=1,
        status="started",
        recorded_at="2026-07-27T12:00:00.000000Z",
    )
    status = {
        "attempt_started": "started",
        "result_decided": "decided",
        "result_confirmed_retryable": "confirmed_retryable",
        "result_outcome_unknown": "semantic_outcome_unknown",
    }[transition]
    if status != "started":
        operations.record_semantic_attempt(
            run_id="discovery-run-1",
            repository_id=101,
            workflow_authority_digest=DIGEST_A,
            stage=stage,
            attempt_no=1,
            status=status,
            recorded_at="2026-07-27T12:00:01.000000Z",
        )
    exports = (
        pipeline.export_owned_state(),
        operations.export_owned_state(),
        publication.export_owned_state(),
    )
    request = _ports().SemanticDurabilityTransition.create(
        run_id="discovery-run-1",
        repository_id=101,
        workflow_authority_digest=DIGEST_A,
        provider="openai",
        stage=stage,
        attempt_no=1,
        recorded_at=(
            "2026-07-27T12:00:00.000000Z"
            if transition == "attempt_started"
            else "2026-07-27T12:00:01.000000Z"
        ),
        transition=transition,
        expected_prior_state_head=PRIOR_HEAD,
        expected_prior_root_digest=prior_bundle.root.root_digest,
        pipeline_export_digest=exports[0].export_digest,
        operations_export_digest=exports[1].export_digest,
        publication_export_digest=exports[2].export_digest,
    )
    return pipeline, operations, publication, request, prior_bundle


def _barrier(remote):
    module = _state_branch()
    return module.StateBranchDurabilityBarrier(
        state_store=module.StateBranchStore(remote),
        query_set_digest="sha256:" + ("7" * 64),
        budget_policy_digest="sha256:" + ("8" * 64),
    )


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("transition", TRANSITIONS)
def test_two_provider_three_stage_transition_matrix_is_remote_confirmed_and_idempotent(
    tmp_path: Path,
    provider: str,
    stage: str,
    transition: str,
) -> None:
    pipeline, operations, publication, base, prior_bundle = _owned_stores(
        tmp_path,
        stage=stage,
        transition=transition,
    )
    request_values = base.as_dict()
    request_values.pop("schema_version")
    request_values.pop("transition_authority_digest")
    request_values["provider"] = provider
    request = _ports().SemanticDurabilityTransition.create(**request_values)
    remote = _Remote(_state_branch(), prior_bundle=prior_bundle)
    barrier = _barrier(remote)
    try:
        receipt = barrier.confirm(
            transition=request,
            pipeline_store=pipeline,
            operations_store=operations,
            publication_store=publication,
        )
        assert receipt.authorizes(request)
        first_head = remote.head
        repeated = barrier.confirm(
            transition=request,
            pipeline_store=pipeline,
            operations_store=operations,
            publication_store=publication,
        )
        assert repeated == receipt
        assert remote.head == first_head
        assert remote.force_values == [False]
    finally:
        publication.close()
        operations.close()
        pipeline.close()


@pytest.mark.parametrize(
    "seam",
    (
        "pipeline_export",
        "operations_export",
        "publication_export",
        "cas",
        "reread",
        "projection",
    ),
)
def test_every_export_cas_reread_and_verification_failure_blocks_guarded_effect(
    tmp_path: Path,
    seam: str,
) -> None:
    pipeline, operations, publication, request, prior_bundle = _owned_stores(
        tmp_path,
        stage="extractor",
        transition="attempt_started",
    )
    remote = _Remote(
        _state_branch(),
        prior_bundle=prior_bundle,
        fail_at=seam if seam in {"cas", "reread", "projection"} else None,
    )
    stores = {
        "pipeline_store": _ExportFailure(
            pipeline, fail=seam == "pipeline_export"
        ),
        "operations_store": _ExportFailure(
            operations, fail=seam == "operations_export"
        ),
        "publication_store": _ExportFailure(
            publication, fail=seam == "publication_export"
        ),
    }
    try:
        with pytest.raises(_ports().SafeFailure) as failure:
            _barrier(remote).confirm(transition=request, **stores)
        assert failure.value.as_dict() == {
            "code": "state_operation_failed",
            "summary": "Local state operation failed.",
        }
        assert remote.provider_requests == 0
        assert remote.retry_or_terminal == 0
        assert remote.force_values in ([], [False])
    finally:
        publication.close()
        operations.close()
        pipeline.close()


def test_stale_export_and_missing_attempt_transition_fail_before_remote_write(
    tmp_path: Path,
) -> None:
    pipeline, operations, publication, request, prior_bundle = _owned_stores(
        tmp_path,
        stage="reviewer",
        transition="attempt_started",
    )
    operations.record_semantic_attempt(
        run_id="discovery-run-1",
        repository_id=101,
        workflow_authority_digest=DIGEST_A,
        stage="reviewer",
        attempt_no=1,
        status="decided",
        recorded_at="2026-07-27T12:00:03.000000Z",
    )
    remote = _Remote(_state_branch(), prior_bundle=prior_bundle)
    prior_blobs = dict(remote.blobs)
    try:
        with pytest.raises(_ports().SafeFailure):
            _barrier(remote).confirm(
                transition=request,
                pipeline_store=pipeline,
                operations_store=operations,
                publication_store=publication,
            )
        assert remote.blobs == prior_blobs
        assert remote.head == PRIOR_HEAD
    finally:
        publication.close()
        operations.close()
        pipeline.close()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize(
    "crash_seam",
    (
        "before_attempt_started_barrier",
        "after_attempt_started_barrier",
        "before_result_barrier",
        "after_result_barrier",
    ),
)
def test_crash_restart_matrix_never_replays_ambiguous_semantic_effect(
    tmp_path: Path,
    provider: str,
    stage: str,
    crash_seam: str,
) -> None:
    transition = (
        "attempt_started"
        if "attempt_started" in crash_seam
        else "result_outcome_unknown"
    )
    pipeline, operations, publication, base, prior_bundle = _owned_stores(
        tmp_path,
        stage=stage,
        transition=transition,
    )
    values = base.as_dict()
    values.pop("schema_version")
    values.pop("transition_authority_digest")
    values["provider"] = provider
    request = _ports().SemanticDurabilityTransition.create(**values)
    remote = _Remote(_state_branch(), prior_bundle=prior_bundle)
    barrier = _barrier(remote)
    provider_requests = 0 if "attempt_started" in crash_seam else 1
    guarded_followups = 0
    try:
        receipt = None
        if crash_seam.startswith("after"):
            receipt = barrier.confirm(
                transition=request,
                pipeline_store=pipeline,
                operations_store=operations,
                publication_store=publication,
            )

        # Restart: an already-confirmed transition is reread idempotently; an
        # unconfirmed transition is persisted once. Neither path infers that an
        # outcome-unknown provider request is safe to replay.
        receipt = barrier.confirm(
            transition=request,
            pipeline_store=pipeline,
            operations_store=operations,
            publication_store=publication,
        )
        if transition == "attempt_started" and receipt.authorizes(request):
            provider_requests += 1
        elif transition == "result_outcome_unknown":
            guarded_followups += 0
        assert provider_requests == 1
        assert guarded_followups == 0
        assert remote.force_values == [False]
    finally:
        publication.close()
        operations.close()
        pipeline.close()
