"""Isolated Phase 3 ledger, persistence, and exact-reuse proofs."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import BaseModel, ValidationError

from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.candidate_authority import (
    CandidateExecutionAuthorityV1,
    LineageResolutionV1,
    candidate_execution_authority,
    derive_new_lineage,
    workflow_spec_authority,
)
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.extraction import WorkflowSpec
from skillscout.domain.models import (
    CANDIDATE_CHECKPOINT_PROFILE_VERSION,
    CANDIDATE_CHECKPOINT_SCHEMA_VERSION,
    PHASE_THREE_GENESIS_CHECKPOINT_HASH,
    PHASE_THREE_PROFILE_VERSION,
    PHASE_THREE_SCHEMA_VERSION,
    CandidateResumeEventV1,
    CandidateRunIdentityV1,
    CandidateStageAttemptV1,
    CandidateStageCheckpointV1,
    CandidateStageResultV1,
    PhaseThreeStageV1,
    VerifiedCandidateRunChain,
)
from skillscout.domain.qualification import (
    evaluate_qualification_checks,
    qualification_report,
    qualification_report_bytes,
)
from skillscout.domain.review import (
    CandidateTerminalSummaryV1,
    candidate_terminal_summary,
    candidate_terminal_summary_bytes,
    generator_outcome_evidence,
    review_disposition,
)


def _digest(character: str) -> str:
    return f"sha256:{character * 64}"


def _workflow() -> WorkflowSpec:
    evidence = {
        "path": "README.md",
        "blob_sha": "a" * 40,
        "content_hash": _digest("1"),
        "excerpt": "Collect the inputs before running the workflow.",
        "supports": "The source describes the input collection step.",
    }
    return WorkflowSpec.model_validate(
        {
            "schema_version": "workflow-spec-v1",
            "workflow_id": "wf-1234567890abcdef",
            "fingerprint": _digest("2"),
            "fingerprint_version": "wf-fingerprint-v1",
            "title": "Review an automation workflow",
            "goal": "Turn a bounded workflow into a reviewable result.",
            "applicability": ("When a structured workflow is available.",),
            "non_goals": ("Do not publish the result.",),
            "preconditions": ("The source evidence is verified.",),
            "inputs": ("A verified workflow.",),
            "steps": (
                {"instruction": "Collect the inputs.", "evidence": (evidence,)},
                {"instruction": "Produce the artifact.", "evidence": (evidence,)},
                {"instruction": "Check the artifact.", "evidence": (evidence,)},
            ),
            "outputs": ("A reviewable artifact.",),
            "failure_modes": ("Reject missing evidence.",),
            "prohibited_actions": ("Do not execute source code.",),
            "required_approvals": ("Human approval before publication.",),
            "assumptions": ("The repository is public.",),
            "evidence": (evidence,),
            "confidence": 0.91,
        }
    )


def _execution_authority(**changes: object) -> CandidateExecutionAuthorityV1:
    workflow_authority = workflow_spec_authority(
        workflow_spec=_workflow(),
        phase2_extractor_output_hash=_digest("3"),
        phase2_verified_chain_anchor=_digest("4"),
    )
    values: dict[str, object] = {
        "workflow_spec_authority": workflow_authority,
        "selected_workflow_fingerprint": workflow_authority.workflow_spec.fingerprint,
        "prior_lineage_binding_digest": None,
        "qualification_policy_version": "qualification-policy-v1",
        "qualification_report_schema_version": "qualification-report-v1",
        "configured_generator_model_id": "gpt-generator-configured",
        "generator_prompt_version": "generator-prompt-v1",
        "generator_output_schema_version": "generator-output-v1",
        "generator_policy_version": "generator-policy-v1",
        "renderer_version": "skill-renderer-v1",
        "artifact_schema_version": "generated-artifact-v1",
        "provenance_schema_version": "skill-provenance-v1",
        "official_validator_distribution": "skills-ref",
        "official_validator_version": "0.1.1",
        "official_validator_distribution_hash": _digest("5"),
        "approved_lock_digest": (
            "sha256:b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004"
        ),
        "custom_validation_policy_version": "skill-validation-policy-v1",
        "validation_report_schema_version": "validation-report-v1",
        "configured_reviewer_model_id": "gpt-reviewer-configured",
        "reviewer_prompt_version": "reviewer-prompt-v1",
        "reviewer_output_schema_version": "reviewer-output-v1",
        "reviewer_policy_version": "reviewer-policy-v1",
        "eligibility_policy_version": "candidate-eligibility-v1",
        "phase3_producer_version": "phase3-v1",
        "phase3_profile_version": PHASE_THREE_PROFILE_VERSION,
        "retry_policy_version": "retry-v1",
    }
    values.update(changes)
    return candidate_execution_authority(**values)  # type: ignore[arg-type]


def _self_hash(values: dict[str, object], field: str) -> str:
    return sha256_digest(
        {
            key: (
                value.model_dump(mode="json", exclude_none=False)
                if isinstance(value, BaseModel)
                else value
            )
            for key, value in values.items()
            if key != field
        }
    )


def _identity(authority: CandidateExecutionAuthorityV1 | None = None) -> CandidateRunIdentityV1:
    execution = authority or _execution_authority()
    values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": "phase3-run",
        "candidate_execution_authority": execution,
        "candidate_execution_authority_digest": execution.authority_digest,
    }
    return CandidateRunIdentityV1(
        **values,
        identity_digest=_self_hash(values, "identity_digest"),
    )


def _attempt(
    *,
    identity: CandidateRunIdentityV1,
    stage: PhaseThreeStageV1,
    previous_checkpoint_hash: str,
    previous_output_hash: str | None,
) -> CandidateStageAttemptV1:
    stage_index = tuple(PhaseThreeStageV1).index(stage)
    values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": identity.run_id,
        "candidate_execution_authority_digest": (
            identity.candidate_execution_authority_digest
        ),
        "stage": stage,
        "stage_index": stage_index,
        "attempt_no": 1,
        "previous_checkpoint_hash": previous_checkpoint_hash,
        "previous_output_hash": previous_output_hash,
        "producer_version": identity.candidate_execution_authority.phase3_producer_version,
        "profile_version": identity.candidate_execution_authority.phase3_profile_version,
        "retry_policy_version": identity.candidate_execution_authority.retry_policy_version,
        "status": "succeeded",
        "outcome_code": "accepted",
        "payload_digest": sha256_digest({"stage": stage.value, "payload": "accepted"}),
    }
    return CandidateStageAttemptV1(
        **values,
        attempt_hash=_self_hash(values, "attempt_hash"),
    )


def _result(
    *,
    identity: CandidateRunIdentityV1,
    attempt: CandidateStageAttemptV1,
    previous_result_hash: str | None,
) -> CandidateStageResultV1:
    output_hash = sha256_digest(
        {
            "schema_version": PHASE_THREE_SCHEMA_VERSION,
            "run_id": identity.run_id,
            "stage": attempt.stage.value,
            "attempt_hash": attempt.attempt_hash,
            "payload_digest": attempt.payload_digest,
            "outcome_code": attempt.outcome_code,
        }
    )
    values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": identity.run_id,
        "candidate_execution_authority_digest": (
            identity.candidate_execution_authority_digest
        ),
        "stage": attempt.stage,
        "stage_index": attempt.stage_index,
        "attempt_no": attempt.attempt_no,
        "attempt_hash": attempt.attempt_hash,
        "previous_result_hash": previous_result_hash,
        "producer_version": attempt.producer_version,
        "profile_version": attempt.profile_version,
        "retry_policy_version": attempt.retry_policy_version,
        "outcome_code": attempt.outcome_code,
        "payload_digest": attempt.payload_digest,
        "output_hash": output_hash,
    }
    return CandidateStageResultV1(
        **values,
        result_hash=_self_hash(values, "result_hash"),
    )


def _checkpoint(
    *,
    identity: CandidateRunIdentityV1,
    result: CandidateStageResultV1,
    previous_checkpoint_hash: str,
) -> CandidateStageCheckpointV1:
    stages = tuple(PhaseThreeStageV1)
    next_stage: PhaseThreeStageV1 | None = (
        stages[result.stage_index + 1] if result.stage_index + 1 < len(stages) else None
    )
    values: dict[str, object] = {
        "schema_version": CANDIDATE_CHECKPOINT_SCHEMA_VERSION,
        "profile_version": CANDIDATE_CHECKPOINT_PROFILE_VERSION,
        "run_id": identity.run_id,
        "candidate_execution_authority_digest": (
            identity.candidate_execution_authority_digest
        ),
        "stage": result.stage,
        "stage_index": result.stage_index,
        "attempt_no": result.attempt_no,
        "result_hash": result.result_hash,
        "output_hash": result.output_hash,
        "previous_checkpoint_hash": previous_checkpoint_hash,
        "next_stage": next_stage,
        "terminal": next_stage is None,
    }
    return CandidateStageCheckpointV1(
        **values,
        checkpoint_hash=_self_hash(values, "checkpoint_hash"),
    )


def _event(
    *,
    identity: CandidateRunIdentityV1,
    event_index: int,
    prior_event_hash: str | None,
    checkpoint: CandidateStageCheckpointV1 | None,
) -> CandidateResumeEventV1:
    values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": identity.run_id,
        "candidate_execution_authority_digest": (
            identity.candidate_execution_authority_digest
        ),
        "event_index": event_index,
        "prior_event_hash": prior_event_hash,
        "checkpoint_hash": checkpoint.checkpoint_hash if checkpoint else None,
        "checkpoint_output_hash": checkpoint.output_hash if checkpoint else None,
        "next_stage": (
            checkpoint.next_stage if checkpoint else PhaseThreeStageV1.QUALIFIER
        ),
        "terminal": checkpoint.terminal if checkpoint else False,
    }
    return CandidateResumeEventV1(
        **values,
        event_hash=_self_hash(values, "event_hash"),
    )


def _domain_chain(
    *,
    authority: CandidateExecutionAuthorityV1 | None = None,
    stage_count: int = 4,
) -> VerifiedCandidateRunChain:
    identity = _identity(authority)
    attempts: list[CandidateStageAttemptV1] = []
    results: list[CandidateStageResultV1] = []
    checkpoints: list[CandidateStageCheckpointV1] = []
    events = [
        _event(
            identity=identity,
            event_index=0,
            prior_event_hash=None,
            checkpoint=None,
        )
    ]
    previous_checkpoint_hash = PHASE_THREE_GENESIS_CHECKPOINT_HASH
    previous_output_hash: str | None = None
    previous_result_hash: str | None = None
    for stage in tuple(PhaseThreeStageV1)[:stage_count]:
        attempt = _attempt(
            identity=identity,
            stage=stage,
            previous_checkpoint_hash=previous_checkpoint_hash,
            previous_output_hash=previous_output_hash,
        )
        result = _result(
            identity=identity,
            attempt=attempt,
            previous_result_hash=previous_result_hash,
        )
        checkpoint = _checkpoint(
            identity=identity,
            result=result,
            previous_checkpoint_hash=previous_checkpoint_hash,
        )
        event = _event(
            identity=identity,
            event_index=len(events),
            prior_event_hash=events[-1].event_hash,
            checkpoint=checkpoint,
        )
        attempts.append(attempt)
        results.append(result)
        checkpoints.append(checkpoint)
        events.append(event)
        previous_checkpoint_hash = checkpoint.checkpoint_hash
        previous_output_hash = result.output_hash
        previous_result_hash = result.result_hash
    return VerifiedCandidateRunChain(
        identity=identity,
        attempts=tuple(attempts),
        results=tuple(results),
        checkpoints=tuple(checkpoints),
        resume_events=tuple(events),
    )


def _revalidate_chain(
    chain: VerifiedCandidateRunChain,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    values = chain.model_dump(mode="python")
    for collection in ("attempts", "results", "checkpoints", "resume_events"):
        values[collection] = list(values[collection])
    mutate(values)
    with pytest.raises(ValidationError):
        VerifiedCandidateRunChain.model_validate(values)


def test_domain_chain_has_closed_isolated_stage_vocabulary() -> None:
    assert tuple(stage.name for stage in PhaseThreeStageV1) == (
        "QUALIFIER",
        "GENERATOR",
        "VALIDATOR",
        "REVIEWER",
    )
    assert tuple(stage.value for stage in PhaseThreeStageV1) == (
        "qualifier",
        "generator",
        "validator",
        "reviewer",
    )
    assert PHASE_THREE_SCHEMA_VERSION == "phase3-ledger-v1"
    assert PHASE_THREE_PROFILE_VERSION == "phase3-profile-v1"
    assert CANDIDATE_CHECKPOINT_SCHEMA_VERSION == "candidate-stage-checkpoint-v1"
    assert CANDIDATE_CHECKPOINT_PROFILE_VERSION == "phase3-checkpoint-v1"


def test_domain_chain_roots_every_record_in_complete_execution_authority() -> None:
    chain = _domain_chain()
    authority_digest = chain.identity.candidate_execution_authority.authority_digest
    assert chain.identity.candidate_execution_authority_digest == authority_digest
    for record in (
        *chain.attempts,
        *chain.results,
        *chain.checkpoints,
        *chain.resume_events,
    ):
        assert record.run_id == chain.identity.run_id
        assert record.candidate_execution_authority_digest == authority_digest

    changed = _domain_chain(
        authority=_execution_authority(configured_reviewer_model_id="other-reviewer")
    )
    assert changed.identity.identity_digest != chain.identity.identity_digest


def test_domain_chain_verifies_complete_checkpoint_and_output_continuity() -> None:
    chain = _domain_chain()
    assert tuple(item.stage for item in chain.results) == tuple(PhaseThreeStageV1)
    assert len(chain.attempts) == len(chain.results) == len(chain.checkpoints) == 4
    assert len(chain.resume_events) == 5
    assert chain.checkpoints[0].previous_checkpoint_hash == (
        PHASE_THREE_GENESIS_CHECKPOINT_HASH
    )
    assert chain.checkpoints[-1].next_stage is None
    assert chain.checkpoints[-1].terminal is True
    for index, checkpoint in enumerate(chain.checkpoints):
        assert checkpoint.result_hash == chain.results[index].result_hash
        assert checkpoint.output_hash == chain.results[index].output_hash
        if index:
            assert checkpoint.previous_checkpoint_hash == (
                chain.checkpoints[index - 1].checkpoint_hash
            )
            assert chain.attempts[index].previous_checkpoint_hash == (
                chain.checkpoints[index - 1].checkpoint_hash
            )
            assert chain.attempts[index].previous_output_hash == (
                chain.results[index - 1].output_hash
            )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["checkpoints"].pop(1),
        lambda value: value["checkpoints"].insert(1, value["checkpoints"][0]),
        lambda value: value["checkpoints"].__setitem__(
            slice(1, 3), reversed(value["checkpoints"][1:3])
        ),
        lambda value: value["results"].__setitem__(1, value["results"][0]),
        lambda value: value["attempts"].__setitem__(2, value["attempts"][1]),
        lambda value: value["resume_events"].pop(2),
        lambda value: value["resume_events"].__setitem__(
            2, value["resume_events"][1]
        ),
    ],
    ids=(
        "checkpoint_deleted",
        "checkpoint_duplicated",
        "checkpoint_reordered",
        "result_cross_stage_swap",
        "attempt_cross_stage_swap",
        "resume_event_deleted",
        "resume_event_spliced",
    ),
)
def test_domain_chain_rejects_missing_duplicate_reordered_or_spliced_records(
    mutate: Callable[[dict[str, object]], None],
) -> None:
    _revalidate_chain(_domain_chain(), mutate)


@pytest.mark.parametrize(
    ("collection", "index", "field", "value"),
    [
        ("attempts", 1, "previous_checkpoint_hash", _digest("8")),
        ("attempts", 1, "previous_output_hash", _digest("8")),
        ("attempts", 1, "payload_digest", _digest("8")),
        ("results", 1, "previous_result_hash", _digest("8")),
        ("results", 1, "payload_digest", _digest("8")),
        ("results", 1, "output_hash", _digest("8")),
        ("checkpoints", 1, "result_hash", _digest("8")),
        ("checkpoints", 1, "output_hash", _digest("8")),
        ("checkpoints", 1, "previous_checkpoint_hash", _digest("8")),
        ("checkpoints", 1, "next_stage", PhaseThreeStageV1.REVIEWER),
        ("checkpoints", 1, "terminal", True),
        ("resume_events", 2, "prior_event_hash", _digest("8")),
        ("resume_events", 2, "checkpoint_hash", _digest("8")),
        ("resume_events", 2, "checkpoint_output_hash", _digest("8")),
    ],
)
def test_domain_chain_rejects_every_hash_or_transition_mutation(
    collection: str,
    index: int,
    field: str,
    value: object,
) -> None:
    def mutate(values: dict[str, object]) -> None:
        values[collection][index][field] = value  # type: ignore[index]

    _revalidate_chain(_domain_chain(), mutate)


def test_domain_chain_rejects_cross_run_checkpoint_splice() -> None:
    original = _domain_chain()
    other = _domain_chain(
        authority=_execution_authority(configured_generator_model_id="other-generator")
    )

    def mutate(values: dict[str, object]) -> None:
        values["checkpoints"][1] = other.checkpoints[1].model_dump(mode="python")  # type: ignore[index]

    _revalidate_chain(original, mutate)


def test_domain_chain_accepts_only_a_legal_prefix_or_complete_terminal() -> None:
    prefix = _domain_chain(stage_count=2)
    assert prefix.checkpoints[-1].next_stage is PhaseThreeStageV1.VALIDATOR
    assert prefix.checkpoints[-1].terminal is False
    complete = _domain_chain()
    assert complete.checkpoints[-1].terminal is True


PHASE3_TABLES = {
    "phase3_runs",
    "phase3_attempts",
    "phase3_results",
    "phase3_checkpoints",
    "phase3_resume_events",
    "phase3_terminals",
    "phase3_artifacts",
}


def _qualification_and_generator_refusal(
    authority: CandidateExecutionAuthorityV1,
) -> tuple[bytes, CandidateTerminalSummaryV1]:
    report = qualification_report(
        checks=evaluate_qualification_checks(authority.workflow_spec_authority.workflow_spec),
        selected_workflow_fingerprint=authority.selected_workflow_fingerprint,
        workflow_spec_authority=authority.workflow_spec_authority,
        candidate_execution_authority=authority,
    )
    assert report.passed is True
    lineage = derive_new_lineage(
        repository_id=123,
        initial_workflow_spec_authority=authority.workflow_spec_authority,
    )
    generator = generator_outcome_evidence(
        candidate_execution_authority=authority,
        outcome="refused",
        actual_generator_model_id="gpt-generator-actual",
        request_id="req-generator-refusal",
        usage=None,
        latency_ms=7,
        generated_artifact_identity=None,
    )
    terminal = candidate_terminal_summary(
        outcome="generator_refusal",
        candidate_execution_authority=authority,
        qualification_passed=True,
        qualification_report_digest=sha256_digest(qualification_report_bytes(report)),
        lineage_resolution=lineage,
        generator_outcome_evidence=generator,
        generated_artifact_identity=None,
        package_identity=None,
        validation_report=None,
        review_disposition=review_disposition(
            generation_succeeded=False,
            validation_report=None,
            review_result=None,
        ),
        review_attestation=None,
    )
    return qualification_report_bytes(report), terminal


def test_state_ledger_adds_only_the_seven_isolated_phase3_tables(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "phase3-state.db")
    try:
        tables = {
            str(row[0])
            for row in store.connection.execute(
                """SELECT name FROM sqlite_master
                   WHERE type = 'table' AND name LIKE 'phase3_%'"""
            )
        }
        assert tables == PHASE3_TABLES
        assert set(store.connection.execute("PRAGMA table_list").fetchall()[0].keys())
        assert set(__import__("skillscout.application.pipeline", fromlist=["PIPELINE_PROFILES"]).PIPELINE_PROFILES) == {
            "fixture-v1",
            "phase2-v1",
        }
    finally:
        store.close()


def test_state_ledger_persists_and_reverifies_the_complete_candidate_chain(
    tmp_path,
) -> None:
    chain = _domain_chain()
    store = SQLiteStateStore(tmp_path / "phase3-state.db")
    try:
        store.persist_candidate_chain(chain, status="running")
        verified = store.verify_candidate_run_chain(
            chain.identity.run_id,
            expected_authority=chain.identity.candidate_execution_authority,
        )
        resumed = store.find_resumable_candidate(
            chain.identity.candidate_execution_authority
        )
        counts = {
            table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in PHASE3_TABLES
        }
    finally:
        store.close()

    assert verified == chain
    assert resumed == chain
    assert counts == {
        "phase3_runs": 1,
        "phase3_attempts": 4,
        "phase3_results": 4,
        "phase3_checkpoints": 4,
        "phase3_resume_events": 5,
        "phase3_terminals": 0,
        "phase3_artifacts": 0,
    }


@pytest.mark.parametrize(
    ("statement", "parameters"),
    [
        (
            "UPDATE phase3_runs SET authority_digest = ?",
            (_digest("8"),),
        ),
        (
            "UPDATE phase3_attempts SET attempt_json = ? WHERE stage_index = 1",
            (canonical_json_bytes({"tampered": True}).decode(),),
        ),
        (
            "UPDATE phase3_results SET output_hash = ? WHERE stage_index = 1",
            (_digest("8"),),
        ),
        (
            "DELETE FROM phase3_checkpoints WHERE stage_index = 1",
            (),
        ),
        (
            "UPDATE phase3_checkpoints SET previous_checkpoint_hash = ? "
            "WHERE stage_index = 2",
            (_digest("8"),),
        ),
        (
            "UPDATE phase3_resume_events SET prior_event_hash = ? WHERE event_index = 2",
            (_digest("8"),),
        ),
    ],
    ids=(
        "authority_swap",
        "attempt_payload",
        "result_output_hash",
        "checkpoint_deleted",
        "checkpoint_spliced",
        "resume_link",
    ),
)
def test_state_ledger_rejects_every_row_or_continuity_mutation(
    tmp_path,
    statement: str,
    parameters: tuple[object, ...],
) -> None:
    chain = _domain_chain()
    store = SQLiteStateStore(tmp_path / "phase3-state.db")
    try:
        store.persist_candidate_chain(chain, status="running")
        store.connection.execute(statement, parameters)
        with pytest.raises(SafeFailure) as failure:
            store.verify_candidate_run_chain(chain.identity.run_id)
        assert failure.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    finally:
        store.close()


def test_state_ledger_terminal_is_atomic_with_exact_external_records(tmp_path) -> None:
    chain = _domain_chain(stage_count=2)
    qualification_bytes, terminal = _qualification_and_generator_refusal(
        chain.identity.candidate_execution_authority
    )
    store = SQLiteStateStore(tmp_path / "phase3-state.db")
    try:
        store.persist_candidate_chain(chain, status="running")
        store.persist_candidate_terminal(
            chain.identity.run_id,
            terminal_summary=terminal,
            artifacts={"qualification_report": qualification_bytes},
        )
        verified = store.verify_candidate_run_chain(chain.identity.run_id)
        terminal_row = store.connection.execute(
            "SELECT * FROM phase3_terminals WHERE run_id = ?",
            (chain.identity.run_id,),
        ).fetchone()
        artifact_rows = store.connection.execute(
            """SELECT artifact_kind, artifact_digest, byte_count
               FROM phase3_artifacts WHERE run_id = ? ORDER BY artifact_kind""",
            (chain.identity.run_id,),
        ).fetchall()
        terminal_bytes = store.read_candidate_artifact(
            chain.identity.run_id, "terminal_summary"
        )
        report_bytes = store.read_candidate_artifact(
            chain.identity.run_id, "qualification_report"
        )
    finally:
        store.close()

    assert verified.identity == chain.identity
    assert terminal_row["terminal_summary_digest"] == terminal.terminal_summary_digest
    assert [(row["artifact_kind"], row["artifact_digest"]) for row in artifact_rows] == [
        ("qualification_report", terminal.qualification_report_digest),
        ("terminal_summary", terminal.terminal_summary_digest),
    ]
    assert terminal_bytes == candidate_terminal_summary_bytes(terminal)
    assert report_bytes == qualification_bytes


def test_state_ledger_rejects_terminal_with_missing_or_mismatched_artifact(
    tmp_path,
) -> None:
    chain = _domain_chain(stage_count=2)
    qualification_bytes, terminal = _qualification_and_generator_refusal(
        chain.identity.candidate_execution_authority
    )
    store = SQLiteStateStore(tmp_path / "phase3-state.db")
    try:
        store.persist_candidate_chain(chain, status="running")
        for artifacts in ({}, {"qualification_report": qualification_bytes + b"x"}):
            before = store.connection.execute(
                "SELECT COUNT(*) FROM phase3_terminals"
            ).fetchone()[0]
            with pytest.raises(SafeFailure) as failure:
                store.persist_candidate_terminal(
                    chain.identity.run_id,
                    terminal_summary=terminal,
                    artifacts=artifacts,
                )
            assert failure.value.code is ErrorCode.STATE_INTEGRITY_ERROR
            assert (
                store.connection.execute(
                    "SELECT COUNT(*) FROM phase3_terminals"
                ).fetchone()[0]
                == before
            )
    finally:
        store.close()


def test_state_ledger_prior_lineage_projection_has_no_unverified_fallback(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "phase3-state.db")
    try:
        assert store.project_verified_prior_lineage_evidence(_digest("8")) is None
    finally:
        store.close()
