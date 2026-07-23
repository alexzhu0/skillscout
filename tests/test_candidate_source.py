"""Strict read-only bridge from completed Phase 2 results into Phase 3."""

from __future__ import annotations

import inspect
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillscout.application import candidate_source
from skillscout.application.candidate_source import (
    MAX_CANDIDATE_DESCRIPTOR_BYTES,
    MAX_CANDIDATE_DESCRIPTORS,
    ResolvedCandidateSourceV1,
    derive_candidate_subject_descriptors,
    load_candidate_subject,
)
from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
from skillscout.adapters.state import SQLiteStateStore
from skillscout.adapters.subjects import load_subject
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import (
    CandidateSourceUnavailable,
    ErrorCode,
    PhaseTwoCandidateProjection,
    PhaseTwoCandidateSource,
    SafeFailure,
    StageContext,
    StageOutcome,
)
from skillscout.domain.candidate_authority import (
    CANDIDATE_DESCRIPTOR_SCHEMA_VERSION,
    CandidateSubjectDescriptorV1,
    workflow_spec_authority,
)
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.enums import PipelineStage
from skillscout.domain.extraction import (
    FINGERPRINT_VERSION,
    WORKFLOW_SPEC_SCHEMA_VERSION,
    WorkflowEvidence,
    WorkflowSpec,
    WorkflowSpecStep,
    workflow_fingerprint,
)
from skillscout.domain.models import StageInput

APPROVED_SUBJECT = Path(__file__).parent / "fixtures" / "subject" / "approved.json"
PINNED_SHA = "0123456789abcdef0123456789abcdef01234567"
README_SHA = "a" * 40
CONTENT_HASH = "sha256:" + "b" * 64
PHASE_TWO_PROFILE_VERSION = "phase2-v1"


def _workflow(index: int = 0) -> WorkflowSpec:
    goal = f"Review one repository deterministically {index}"
    instructions = (
        f"Inspect the bounded repository summary {index}",
        f"Check the recorded evidence references {index}",
        f"Report a reusable workflow result {index}",
    )
    fingerprint = workflow_fingerprint(
        repo_id="1234",
        goal=goal,
        steps=instructions,
    )
    evidence = WorkflowEvidence(
        path="README.md",
        blob_sha=README_SHA,
        content_hash=CONTENT_HASH,
        excerpt="Recorded workflow evidence.",
        supports="Supports the workflow.",
    )
    return WorkflowSpec(
        schema_version=WORKFLOW_SPEC_SCHEMA_VERSION,
        workflow_id="wf-" + fingerprint[7:23],
        fingerprint=fingerprint,
        fingerprint_version=FINGERPRINT_VERSION,
        title=f"Repository review {index}",
        goal=goal,
        applicability=("public repositories",),
        non_goals=("executing repository code",),
        preconditions=("a pinned commit",),
        inputs=("verified repository metadata",),
        steps=tuple(
            WorkflowSpecStep(instruction=instruction, evidence=(evidence,))
            for instruction in instructions
        ),
        outputs=("a bounded workflow report",),
        failure_modes=("missing evidence",),
        prohibited_actions=("do not execute repository code",),
        required_approvals=(),
        assumptions=("repository content is untrusted",),
        evidence=(evidence,),
        confidence=0.95,
    )


class _PhaseTwoResultProcessor:
    producer_version = PHASE_TWO_PROFILE_VERSION

    def __init__(
        self,
        *,
        outcome: str = "extracted",
        workflows: tuple[dict[str, object], ...] | None = None,
    ) -> None:
        self._outcome = outcome
        self._workflows = workflows

    def process(self, stage_input: StageInput, context: StageContext) -> StageOutcome:
        del context
        base: dict[str, object] = {
            "schema_version": stage_input.schema_version,
            "stage": stage_input.stage.value,
            "subject_id": stage_input.subject_id,
            "outcome": "accepted",
        }
        if stage_input.stage is PipelineStage.SCOUT:
            base.update(
                {
                    "repository": {
                        "id": 1234,
                        "owner": "example",
                        "name": "approved-repo",
                        "license_spdx": "MIT",
                    },
                    "pinned_commit_sha": PINNED_SHA,
                }
            )
        elif stage_input.stage is PipelineStage.FILTER:
            base["license_spdx"] = "MIT"
        elif stage_input.stage is PipelineStage.EXTRACTOR:
            base.update(
                {
                    "outcome": self._outcome,
                    "workflows": list(self._workflows or ()),
                }
            )
        return StageOutcome(payload=base)


def _create_phase2_state(
    tmp_path: Path,
    *,
    outcome: str = "extracted",
    workflows: tuple[dict[str, object], ...] | None = None,
    fail_after: str | None = None,
) -> tuple[Path, CandidateSubjectDescriptorV1, WorkflowSpec]:
    selected = _workflow()
    projected = workflows
    if projected is None and outcome == "extracted":
        projected = (selected.model_dump(mode="json", exclude_none=False),)
    state_path = tmp_path / "phase2.db"
    store = SQLiteStateStore(state_path)
    try:
        try:
            summary = PipelineRunner(
                store,
                _PhaseTwoResultProcessor(
                    outcome=outcome,
                    workflows=projected,
                ),
            ).run(
                load_subject(APPROVED_SUBJECT),
                tmp_path / "phase2-output",
                fail_after=fail_after,
            )
            run_id = summary.run_id
        except SafeFailure as failure:
            if fail_after is None or failure.code is not ErrorCode.PIPELINE_INTERRUPTED:
                raise
            row = store.connection.execute("SELECT run_id FROM runs").fetchone()
            assert row is not None
            run_id = str(row["run_id"])
        chain = store.verify_run_chain(run_id)
        extractor = chain.results[-1]
        chain_anchor = sha256_digest(
            chain.model_dump(mode="json", exclude_none=False)
        )
        authority = workflow_spec_authority(
            workflow_spec=selected,
            phase2_extractor_output_hash=extractor.output_hash,
            phase2_verified_chain_anchor=chain_anchor,
        )
        descriptor = CandidateSubjectDescriptorV1(
            schema_version=CANDIDATE_DESCRIPTOR_SCHEMA_VERSION,
            phase2_run_id=run_id,
            phase2_profile_version=PHASE_TWO_PROFILE_VERSION,
            phase2_producer_version=PHASE_TWO_PROFILE_VERSION,
            extractor_output_hash=extractor.output_hash,
            verified_chain_anchor=chain_anchor,
            selected_workflow_fingerprint=selected.fingerprint,
            expected_workflow_spec_authority_digest=authority.authority_digest,
            prior_lineage_binding_digest=None,
        )
    finally:
        store.close()
    return state_path, descriptor, selected


def _all_persisted_bytes(state_path: Path) -> dict[str, bytes]:
    roots = (state_path, state_path.with_suffix(".manifests"))
    paths: list[Path] = []
    for root in roots:
        if root.is_file():
            paths.append(root)
        elif root.is_dir():
            paths.extend(path for path in root.rglob("*") if path.is_file())
    return {
        str(path.relative_to(state_path.parent)): path.read_bytes()
        for path in sorted(paths)
    }


def _assert_unavailable(
    source: SQLitePhaseTwoCandidateSource,
    descriptor: CandidateSubjectDescriptorV1,
) -> None:
    with pytest.raises(CandidateSourceUnavailable) as failure:
        source.resolve(descriptor)
    assert failure.value.as_dict() == {
        "code": "candidate_source_unavailable",
        "summary": "Candidate source is unavailable.",
    }
    assert str(failure.value) == "Candidate source is unavailable."


def test_phase2_query_is_read_only_and_returns_exact_canonical_workflow(
    tmp_path: Path,
) -> None:
    state_path, descriptor, workflow = _create_phase2_state(tmp_path)
    before = _all_persisted_bytes(state_path)

    projection = SQLitePhaseTwoCandidateSource(state_path).resolve(descriptor)

    assert projection.phase2_run_id == descriptor.phase2_run_id
    assert projection.workflow_spec_bytes == canonical_json_bytes(
        workflow.model_dump(mode="json", exclude_none=False)
    )
    assert projection.extractor_output_hash == descriptor.extractor_output_hash
    assert projection.verified_chain_anchor == descriptor.verified_chain_anchor
    assert projection.repository_id == 1234
    assert projection.repository_url == "https://github.com/example/approved-repo"
    assert projection.pinned_commit_sha == PINNED_SHA
    assert projection.license_spdx == "MIT"
    assert _all_persisted_bytes(state_path) == before
    assert not tuple(state_path.parent.glob("*-journal"))
    assert not tuple(state_path.parent.glob("*-wal"))


def test_phase2_query_protocol_and_adapter_expose_no_mutation_methods() -> None:
    assert tuple(inspect.signature(PhaseTwoCandidateSource.resolve).parameters) == (
        "self",
        "descriptor",
    )
    public = {
        name
        for name, member in inspect.getmembers(
            SQLitePhaseTwoCandidateSource, predicate=inspect.isfunction
        )
        if not name.startswith("_")
    }
    assert public == {"resolve", "resolve_all"}


@pytest.mark.parametrize(
    "outcome",
    ("rejected", "no_workflow", "refused", "incomplete", "schema_failure"),
)
def test_phase2_query_rejects_every_non_success_outcome(
    tmp_path: Path,
    outcome: str,
) -> None:
    state_path, descriptor, _workflow_spec = _create_phase2_state(
        tmp_path,
        outcome=outcome,
        workflows=(),
    )
    _assert_unavailable(SQLitePhaseTwoCandidateSource(state_path), descriptor)


def test_phase2_query_rejects_incomplete_run(tmp_path: Path) -> None:
    state_path, descriptor, _workflow_spec = _create_phase2_state(
        tmp_path,
        fail_after="extractor",
    )
    _assert_unavailable(SQLitePhaseTwoCandidateSource(state_path), descriptor)


def test_phase2_query_rejects_missing_duplicate_and_invalid_workflows(
    tmp_path: Path,
) -> None:
    workflow = _workflow()
    duplicate = workflow.model_dump(mode="json", exclude_none=False)
    cases = (
        ((_workflow(1).model_dump(mode="json", exclude_none=False),), "missing"),
        ((duplicate, dict(duplicate)), "duplicate"),
        ((duplicate | {"unexpected": "CANARY"},), "invalid"),
    )
    for index, (workflows, _label) in enumerate(cases):
        root = tmp_path / str(index)
        root.mkdir()
        state_path, descriptor, _workflow_spec = _create_phase2_state(
            root,
            workflows=workflows,
        )
        _assert_unavailable(SQLitePhaseTwoCandidateSource(state_path), descriptor)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("phase2_run_id", "run-missing"),
        ("phase2_profile_version", "phase2-other"),
        ("phase2_producer_version", "phase2-other"),
        ("extractor_output_hash", "sha256:" + "c" * 64),
        ("verified_chain_anchor", "sha256:" + "d" * 64),
    ),
)
def test_phase2_query_rejects_identity_and_anchor_mismatches(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    state_path, descriptor, _workflow_spec = _create_phase2_state(tmp_path)
    changed = descriptor.model_copy(update={field: value})
    _assert_unavailable(SQLitePhaseTwoCandidateSource(state_path), changed)


def test_phase2_query_rejects_broken_chain_without_echo(tmp_path: Path) -> None:
    state_path, descriptor, _workflow_spec = _create_phase2_state(tmp_path)
    canary = "DO_NOT_ECHO_PHASE2_SQL_CANARY"
    connection = sqlite3.connect(state_path)
    try:
        connection.execute(
            "UPDATE stage_results SET output_json = ? WHERE stage = 'extractor'",
            (canary,),
        )
        connection.commit()
    finally:
        connection.close()

    source = SQLitePhaseTwoCandidateSource(state_path)
    with pytest.raises(CandidateSourceUnavailable) as failure:
        source.resolve(descriptor)
    assert canary not in str(failure.value)
    assert canary not in repr(failure.value)


class _ProjectionSource:
    def __init__(
        self,
        projections: tuple[PhaseTwoCandidateProjection, ...],
    ) -> None:
        self.projections = projections
        self.resolve_calls: list[str] = []
        self.resolve_all_calls: list[str] = []

    def resolve(
        self,
        descriptor: CandidateSubjectDescriptorV1,
    ) -> PhaseTwoCandidateProjection:
        self.resolve_calls.append(descriptor.selected_workflow_fingerprint)
        matches = [
            projection
            for projection in self.projections
            if WorkflowSpec.model_validate_json(
                projection.workflow_spec_bytes, strict=True
            ).fingerprint
            == descriptor.selected_workflow_fingerprint
        ]
        if len(matches) != 1:
            raise CandidateSourceUnavailable()
        return matches[0]

    def resolve_all(
        self,
        *,
        phase2_run_id: str,
        phase2_profile_version: str,
        phase2_producer_version: str,
    ) -> tuple[PhaseTwoCandidateProjection, ...]:
        del phase2_profile_version, phase2_producer_version
        self.resolve_all_calls.append(phase2_run_id)
        return self.projections


def _projection(
    workflow: WorkflowSpec,
    *,
    run_id: str = "run-phase2",
    output_hash: str = "sha256:" + "c" * 64,
    chain_anchor: str = "sha256:" + "d" * 64,
) -> PhaseTwoCandidateProjection:
    return PhaseTwoCandidateProjection(
        phase2_run_id=run_id,
        workflow_spec_bytes=canonical_json_bytes(
            workflow.model_dump(mode="json", exclude_none=False)
        ),
        extractor_output_hash=output_hash,
        verified_chain_anchor=chain_anchor,
        repository_id=1234,
        repository_url="https://github.com/example/approved-repo",
        pinned_commit_sha=PINNED_SHA,
        license_spdx="MIT",
    )


def _descriptor_for_projection(
    projection: PhaseTwoCandidateProjection,
    *,
    workflow: WorkflowSpec | None = None,
    binding_digest: str | None = None,
) -> CandidateSubjectDescriptorV1:
    selected = workflow or WorkflowSpec.model_validate_json(
        projection.workflow_spec_bytes,
        strict=True,
    )
    authority = workflow_spec_authority(
        workflow_spec=selected,
        phase2_extractor_output_hash=projection.extractor_output_hash,
        phase2_verified_chain_anchor=projection.verified_chain_anchor,
    )
    return CandidateSubjectDescriptorV1(
        schema_version=CANDIDATE_DESCRIPTOR_SCHEMA_VERSION,
        phase2_run_id=projection.phase2_run_id,
        phase2_profile_version=PHASE_TWO_PROFILE_VERSION,
        phase2_producer_version=PHASE_TWO_PROFILE_VERSION,
        extractor_output_hash=projection.extractor_output_hash,
        verified_chain_anchor=projection.verified_chain_anchor,
        selected_workflow_fingerprint=selected.fingerprint,
        expected_workflow_spec_authority_digest=authority.authority_digest,
        prior_lineage_binding_digest=binding_digest,
    )


def _write_descriptor(
    tmp_path: Path,
    descriptor: CandidateSubjectDescriptorV1,
    *,
    raw: bytes | None = None,
) -> Path:
    path = tmp_path / "candidate.json"
    path.write_bytes(raw if raw is not None else canonical_json_bytes(descriptor))
    path.chmod(0o600)
    return path


def _metadata(
    source: os.stat_result,
    **changes: int,
) -> SimpleNamespace:
    fields = {
        name: getattr(source, name)
        for name in (
            "st_mode",
            "st_dev",
            "st_ino",
            "st_nlink",
            "st_uid",
            "st_gid",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
    }
    fields.update(changes)
    return SimpleNamespace(**fields)


def test_load_candidate_subject_accepts_only_exact_canonical_private_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _workflow()
    projection = _projection(workflow)
    descriptor = _descriptor_for_projection(projection)
    path = _write_descriptor(tmp_path, descriptor)
    source = _ProjectionSource((projection,))
    flags_seen = 0
    real_open = candidate_source.os.open

    def recording_open(open_path: object, flags: int) -> int:
        nonlocal flags_seen
        flags_seen = flags
        return real_open(open_path, flags)

    monkeypatch.setattr(candidate_source.os, "open", recording_open)
    resolved = load_candidate_subject(path, source)

    assert isinstance(resolved, ResolvedCandidateSourceV1)
    assert resolved.descriptor == descriptor
    assert resolved.workflow_spec_authority.workflow_spec == workflow
    assert resolved.workflow_spec_authority.authority_digest == (
        descriptor.expected_workflow_spec_authority_digest
    )
    assert resolved.workflow_spec_bytes == projection.workflow_spec_bytes
    assert resolved.repository_id == 1234
    assert source.resolve_calls == [workflow.fingerprint]
    for flag_name in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
        flag = getattr(os, flag_name, 0)
        if flag:
            assert flags_seen & flag


@pytest.mark.parametrize("mode", (0o640, 0o602))
def test_load_candidate_subject_rejects_group_or_other_permissions_before_query(
    tmp_path: Path,
    mode: int,
) -> None:
    projection = _projection(_workflow())
    descriptor = _descriptor_for_projection(projection)
    path = _write_descriptor(tmp_path, descriptor)
    path.chmod(mode)
    source = _ProjectionSource((projection,))
    _assert_loader_unavailable(path, source)


def _assert_loader_unavailable(
    path: Path,
    source: _ProjectionSource,
) -> None:
    with pytest.raises(CandidateSourceUnavailable) as failure:
        load_candidate_subject(path, source)
    assert failure.value.as_dict() == {
        "code": "candidate_source_unavailable",
        "summary": "Candidate source is unavailable.",
    }
    assert source.resolve_calls == []


def test_load_candidate_subject_rejects_owner_check_unavailable_and_foreign_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection(_workflow())
    descriptor = _descriptor_for_projection(projection)
    path = _write_descriptor(tmp_path, descriptor)
    source = _ProjectionSource((projection,))

    monkeypatch.setattr(candidate_source.os, "geteuid", None)
    _assert_loader_unavailable(path, source)

    monkeypatch.undo()
    actual = os.lstat(path)
    monkeypatch.setattr(
        candidate_source.os,
        "lstat",
        lambda _path: _metadata(actual, st_uid=os.geteuid() + 1),
    )
    _assert_loader_unavailable(path, source)


def test_load_candidate_subject_rejects_owner_check_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection(_workflow())
    descriptor = _descriptor_for_projection(projection)
    path = _write_descriptor(tmp_path, descriptor)
    source = _ProjectionSource((projection,))

    def unavailable() -> int:
        raise OSError("CANARY_OWNER_FAILURE")

    monkeypatch.setattr(candidate_source.os, "geteuid", unavailable)
    _assert_loader_unavailable(path, source)


def test_load_candidate_subject_rejects_hardlink_symlink_fifo_and_directory(
    tmp_path: Path,
) -> None:
    for index, damage in enumerate(("hardlink", "symlink", "fifo", "directory")):
        root = tmp_path / str(index)
        root.mkdir()
        projection = _projection(_workflow())
        descriptor = _descriptor_for_projection(projection)
        path = _write_descriptor(root, descriptor)
        if damage == "hardlink":
            os.link(path, root / "alias.json")
        elif damage == "symlink":
            linked = root / "linked.json"
            linked.symlink_to(path)
            path = linked
        elif damage == "fifo":
            path.unlink()
            os.mkfifo(path, 0o600)
        else:
            path.unlink()
            path.mkdir()
        _assert_loader_unavailable(path, _ProjectionSource((projection,)))


def test_load_candidate_subject_rejects_path_fd_swap_and_post_read_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection(_workflow())
    descriptor = _descriptor_for_projection(projection)
    path = _write_descriptor(tmp_path, descriptor)
    actual = os.lstat(path)

    monkeypatch.setattr(
        candidate_source.os,
        "lstat",
        lambda _path: _metadata(actual, st_ino=actual.st_ino + 1),
    )
    _assert_loader_unavailable(path, _ProjectionSource((projection,)))

    monkeypatch.undo()
    calls = 0
    real_fstat = os.fstat

    def changing_fstat(descriptor_fd: int) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        observed = real_fstat(descriptor_fd)
        return _metadata(
            observed,
            st_mtime_ns=observed.st_mtime_ns + int(calls > 1),
        )

    monkeypatch.setattr(candidate_source.os, "fstat", changing_fstat)
    _assert_loader_unavailable(path, _ProjectionSource((projection,)))
    assert calls == 2


def test_load_candidate_subject_cap_plus_one_rejects_lied_about_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection(_workflow())
    descriptor = _descriptor_for_projection(projection)
    path = _write_descriptor(
        tmp_path,
        descriptor,
        raw=b"x" * (MAX_CANDIDATE_DESCRIPTOR_BYTES + 1),
    )
    actual = os.lstat(path)
    lied = _metadata(actual, st_size=0)
    monkeypatch.setattr(candidate_source.os, "lstat", lambda _path: lied)
    monkeypatch.setattr(candidate_source.os, "fstat", lambda _descriptor: lied)
    _assert_loader_unavailable(path, _ProjectionSource((projection,)))


def test_load_candidate_subject_rejects_oversize_stat_before_query(
    tmp_path: Path,
) -> None:
    projection = _projection(_workflow())
    descriptor = _descriptor_for_projection(projection)
    path = _write_descriptor(
        tmp_path,
        descriptor,
        raw=b"x" * (MAX_CANDIDATE_DESCRIPTOR_BYTES + 1),
    )
    _assert_loader_unavailable(path, _ProjectionSource((projection,)))


@pytest.mark.parametrize(
    "raw",
    (
        b"\xff",
        b'{"broken":',
        b"{}",
        b'{ "schema_version": "candidate-subject-descriptor-v1" }',
    ),
)
def test_load_candidate_subject_rejects_invalid_utf8_malformed_and_noncanonical(
    tmp_path: Path,
    raw: bytes,
) -> None:
    projection = _projection(_workflow())
    descriptor = _descriptor_for_projection(projection)
    path = _write_descriptor(tmp_path, descriptor, raw=raw)
    _assert_loader_unavailable(path, _ProjectionSource((projection,)))


def test_load_candidate_subject_rejects_duplicate_key_and_does_not_echo(
    tmp_path: Path,
) -> None:
    canary = "CANDIDATE_DESCRIPTOR_CANARY_DO_NOT_ECHO"
    projection = _projection(_workflow())
    descriptor = _descriptor_for_projection(projection)
    canonical = canonical_json_bytes(descriptor)
    duplicate = canonical[:-1] + (
        b',"phase2_run_id":"' + canary.encode() + b'"}'
    )
    path = _write_descriptor(tmp_path, descriptor, raw=duplicate)
    source = _ProjectionSource((projection,))
    with pytest.raises(CandidateSourceUnavailable) as failure:
        load_candidate_subject(path, source)
    assert canary not in str(failure.value)
    assert canary not in repr(failure.value)
    assert str(path) not in str(failure.value)
    assert source.resolve_calls == []


def _mutated_workflow(workflow: WorkflowSpec, field: str) -> WorkflowSpec:
    evidence = workflow.evidence[0]
    replacements: dict[str, object] = {
        "schema_version": "workflow-spec-v1",
        "workflow_id": workflow.workflow_id + "-changed",
        "fingerprint_version": "wf-fingerprint-v1",
        "title": workflow.title + " changed",
        "goal": workflow.goal + " changed",
        "applicability": workflow.applicability + ("changed",),
        "non_goals": workflow.non_goals + ("changed",),
        "preconditions": workflow.preconditions + ("changed",),
        "inputs": workflow.inputs + ("changed",),
        "steps": workflow.steps[:-1],
        "outputs": workflow.outputs + ("changed",),
        "failure_modes": workflow.failure_modes + ("changed",),
        "prohibited_actions": workflow.prohibited_actions + ("changed",),
        "required_approvals": ("changed",),
        "assumptions": workflow.assumptions + ("changed",),
        "evidence": (
            evidence.model_copy(update={"supports": evidence.supports + " changed"}),
        ),
        "confidence": 0.91,
    }
    return workflow.model_copy(update={field: replacements[field]})


@pytest.mark.parametrize(
    "field",
    (
        "workflow_id",
        "title",
        "goal",
        "applicability",
        "non_goals",
        "preconditions",
        "inputs",
        "steps",
        "outputs",
        "failure_modes",
        "prohibited_actions",
        "required_approvals",
        "assumptions",
        "evidence",
        "confidence",
    ),
)
def test_load_candidate_subject_recomputes_complete_authority(
    tmp_path: Path,
    field: str,
) -> None:
    original = _workflow()
    expected_projection = _projection(original)
    descriptor = _descriptor_for_projection(expected_projection)
    changed = _mutated_workflow(original, field)
    changed_projection = _projection(changed)
    source = _ProjectionSource((changed_projection,))
    path = _write_descriptor(tmp_path, descriptor)

    with pytest.raises(CandidateSourceUnavailable):
        load_candidate_subject(path, source)
    assert source.resolve_calls == [original.fingerprint]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("extractor_output_hash", "sha256:" + "e" * 64),
        ("verified_chain_anchor", "sha256:" + "f" * 64),
    ),
)
def test_load_candidate_subject_rejects_source_authority_mutation(
    tmp_path: Path,
    field: str,
    value: str | int,
) -> None:
    workflow = _workflow()
    projection = _projection(workflow)
    descriptor = _descriptor_for_projection(projection)
    changed = PhaseTwoCandidateProjection(
        **(projection.__dict__ | {field: value})
    )
    source = _ProjectionSource((changed,))
    path = _write_descriptor(tmp_path, descriptor)
    with pytest.raises(CandidateSourceUnavailable):
        load_candidate_subject(path, source)
    assert source.resolve_calls == [workflow.fingerprint]


def test_derive_descriptors_sorts_full_fingerprints_caps_three_and_is_stable() -> None:
    workflows = tuple(_workflow(index) for index in range(4))
    projections = tuple(_projection(workflow) for workflow in workflows)
    source_a = _ProjectionSource(tuple(reversed(projections)))
    source_b = _ProjectionSource((projections[1], projections[3], projections[0], projections[2]))

    derived_a = derive_candidate_subject_descriptors(
        source_a,
        phase2_run_id="run-phase2",
    )
    derived_b = derive_candidate_subject_descriptors(
        source_b,
        phase2_run_id="run-phase2",
    )

    assert MAX_CANDIDATE_DESCRIPTORS == 3
    assert derived_a == derived_b
    assert len(derived_a) == 3
    expected = sorted(workflow.fingerprint for workflow in workflows)[:3]
    assert [item.selected_workflow_fingerprint for item in derived_a] == expected
    excluded = (set(workflow.fingerprint for workflow in workflows) - set(expected)).pop()
    assert excluded not in {item.selected_workflow_fingerprint for item in derived_a}
    assert source_a.resolve_all_calls == ["run-phase2"]
    assert source_b.resolve_all_calls == ["run-phase2"]


def test_derive_descriptors_attaches_only_exact_explicit_binding_mapping() -> None:
    workflows = (_workflow(0), _workflow(1))
    projections = tuple(_projection(workflow) for workflow in workflows)
    binding = "sha256:" + "9" * 64
    source = _ProjectionSource(projections)

    absent = derive_candidate_subject_descriptors(
        source,
        phase2_run_id="run-phase2",
    )
    attached = derive_candidate_subject_descriptors(
        source,
        phase2_run_id="run-phase2",
        approved_binding_digests={
            workflows[1].fingerprint: binding,
            "sha256:" + "0" * 64: "sha256:" + "8" * 64,
        },
    )

    assert all(item.prior_lineage_binding_digest is None for item in absent)
    by_fingerprint = {
        item.selected_workflow_fingerprint: item.prior_lineage_binding_digest
        for item in attached
    }
    assert by_fingerprint[workflows[0].fingerprint] is None
    assert by_fingerprint[workflows[1].fingerprint] == binding


def test_sibling_resolution_is_independent_after_one_authority_failure(
    tmp_path: Path,
) -> None:
    workflows = tuple(_workflow(index) for index in range(3))
    projections = list(_projection(workflow) for workflow in workflows)
    descriptors = derive_candidate_subject_descriptors(
        _ProjectionSource(tuple(projections)),
        phase2_run_id="run-phase2",
    )
    failing_fingerprint = descriptors[1].selected_workflow_fingerprint
    projection_by_fingerprint = {
        WorkflowSpec.model_validate_json(
            projection.workflow_spec_bytes, strict=True
        ).fingerprint: projection
        for projection in projections
    }
    bad = projection_by_fingerprint[failing_fingerprint]
    projection_by_fingerprint[failing_fingerprint] = PhaseTwoCandidateProjection(
        **(bad.__dict__ | {"verified_chain_anchor": "sha256:" + "1" * 64})
    )
    source = _ProjectionSource(tuple(projection_by_fingerprint.values()))
    outcomes: dict[str, str] = {}

    for index, descriptor in enumerate(descriptors):
        root = tmp_path / str(index)
        root.mkdir()
        path = _write_descriptor(root, descriptor)
        try:
            resolved = load_candidate_subject(path, source)
            outcomes[descriptor.selected_workflow_fingerprint] = (
                resolved.workflow_spec_authority.authority_digest
            )
        except CandidateSourceUnavailable:
            outcomes[descriptor.selected_workflow_fingerprint] = "unavailable"

    assert outcomes[failing_fingerprint] == "unavailable"
    assert sum(value == "unavailable" for value in outcomes.values()) == 1
    assert len(source.resolve_calls) == 3
    assert len(set(source.resolve_calls)) == 3
