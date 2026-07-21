"""Closed stage and lifecycle vocabularies for the audit ledger."""

from __future__ import annotations

from enum import StrEnum


class PipelineStage(StrEnum):
    SCOUT = "scout"
    FILTER = "filter"
    READER = "reader"
    EXTRACTOR = "extractor"
    QUALIFIER = "qualifier"
    GENERATOR = "generator"
    VALIDATORS = "validators"
    REVIEWER = "reviewer"
    PUBLICATION_PLANNER = "publication_planner"


class ExecutionMode(StrEnum):
    DRY_RUN = "dry_run"


class EffectScope(StrEnum):
    """Closed authority vocabulary for runtime adapter registration."""

    NONE = "none"
    LOCAL_STATE = "local_state"
    REMOTE_READ = "remote_read"
    REMOTE_WRITE = "remote_write"


class RunStatus(StrEnum):
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    PLANNED_NOT_PUBLISHED = "planned_not_published"
    COMPLETED = "completed"


class AttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


_STAGE_SUCCESSORS = {
    current: successor
    for current, successor in zip(tuple(PipelineStage), tuple(PipelineStage)[1:])
}
_RUN_TRANSITIONS = {
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.INTERRUPTED,
            RunStatus.FAILED,
            RunStatus.PLANNED_NOT_PUBLISHED,
            RunStatus.COMPLETED,
        }
    ),
    RunStatus.INTERRUPTED: frozenset({RunStatus.RUNNING, RunStatus.FAILED}),
    RunStatus.FAILED: frozenset(),
    RunStatus.PLANNED_NOT_PUBLISHED: frozenset(),
    RunStatus.COMPLETED: frozenset(),
}
_ATTEMPT_TRANSITIONS = {
    AttemptStatus.RUNNING: frozenset(
        {AttemptStatus.SUCCEEDED, AttemptStatus.FAILED, AttemptStatus.ABANDONED}
    ),
    AttemptStatus.SUCCEEDED: frozenset(),
    AttemptStatus.FAILED: frozenset(),
    AttemptStatus.ABANDONED: frozenset(),
}


def validate_stage_successor(current: PipelineStage, successor: PipelineStage) -> PipelineStage:
    """Return the successor only when it is the next closed pipeline stage."""

    if _STAGE_SUCCESSORS.get(current) is not successor:
        raise ValueError("illegal pipeline stage successor")
    return successor


def validate_run_transition(current: RunStatus, successor: RunStatus) -> RunStatus:
    """Return a legal run transition and reject terminal-state rewinds."""

    if successor not in _RUN_TRANSITIONS[current]:
        raise ValueError("illegal run status transition")
    return successor


def validate_attempt_transition(
    current: AttemptStatus, successor: AttemptStatus
) -> AttemptStatus:
    """Return a legal attempt transition and reject terminal-state rewinds."""

    if successor not in _ATTEMPT_TRANSITIONS[current]:
        raise ValueError("illegal attempt status transition")
    return successor
