"""Strict read-only bridge from completed Phase 2 results into Phase 3."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest

from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
from skillscout.adapters.state import SQLiteStateStore
from skillscout.adapters.subjects import load_subject
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import (
    CandidateSourceUnavailable,
    ErrorCode,
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
    assert public == {"resolve"}


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
