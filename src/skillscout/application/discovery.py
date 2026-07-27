"""Unprotected, bounded discovery composition through Phase 3.

This module deliberately owns no catalog or publication capability.  It
coordinates reviewed GitHub Search, the existing Phase 2 pipeline, and the
existing Phase 3 application, then stops at a content-addressed state handoff.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Literal, Protocol

from skillscout.application.phase3 import PhaseThreeApplication
from skillscout.application.pipeline import PipelineRunner
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
)

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_STATE_SHA = re.compile(r"^[0-9a-f]{40}$")
_LOCATOR = re.compile(
    r"^state/objects/sha256/[0-9a-f]{2}/[0-9a-f]{64}\.json$"
)

BusinessOutcome = Literal[
    "filter_rejected",
    "no_workflow",
    "qualification_rejected",
    "validation_rejected",
    "review_rejected",
    "completed_reuse",
    "eligible_local_candidate",
]
ContinuableOutcome = Literal[
    "filter_rejected",
    "no_workflow",
    "qualification_rejected",
    "validation_rejected",
    "review_rejected",
    "completed_reuse",
    "eligible_local_candidate",
    "semantic_outcome_unknown",
]
FatalOutcome = Literal["state_integrity_conflict", "permanent_failure"]
WorkflowOutcome = Literal[
    "eligible",
    "qualification_rejected",
    "validation_rejected",
    "review_rejected",
    "semantic_outcome_unknown",
]

_BUSINESS_OUTCOMES = frozenset(
    {
        "filter_rejected",
        "no_workflow",
        "qualification_rejected",
        "validation_rejected",
        "review_rejected",
        "completed_reuse",
        "eligible_local_candidate",
    }
)
_CONTINUABLE_OUTCOMES = _BUSINESS_OUTCOMES | {"semantic_outcome_unknown"}
_FATAL_OUTCOMES = frozenset({"state_integrity_conflict", "permanent_failure"})
_WORKFLOW_RESULT = {
    "eligible": "eligible_local_candidate",
    "qualification_rejected": "qualification_rejected",
    "validation_rejected": "validation_rejected",
    "review_rejected": "review_rejected",
    "semantic_outcome_unknown": "semantic_outcome_unknown",
}


class _SearchPort(Protocol):
    """Reviewed Search client; concrete construction is supplied by bootstrap."""


class _OperationsPort(Protocol):
    """Owner of durable discovery facts and non-refundable reservations."""


class _StateRestorePort(Protocol):
    def __call__(self) -> object: ...


class _DurabilityPort(Protocol):
    """Remote three-store synchronization boundary."""


@dataclass(frozen=True)
class DiscoveryDependencies:
    """Factories available to unprotected discovery.

    Phase 4 dependencies are intentionally not representable.  Phase 2 and
    Phase 3 stay as the already-verified application types; discovery does not
    reimplement either semantic pipeline.
    """

    search_factory: Callable[[], _SearchPort]
    operations_store_factory: Callable[[], _OperationsPort]
    state_restore: _StateRestorePort
    durability_barrier: _DurabilityPort
    phase2_factory: Callable[..., PipelineRunner]
    phase3_factory: Callable[..., PhaseThreeApplication]


@dataclass(frozen=True)
class EligibleCandidateLocator:
    """Non-authorizing locator persisted in one exact state commit."""

    locator: str
    authority_digest: str
    workflow_identity_digest: str

    def __post_init__(self) -> None:
        if (
            _LOCATOR.fullmatch(self.locator) is None
            or _DIGEST.fullmatch(self.authority_digest) is None
            or _DIGEST.fullmatch(self.workflow_identity_digest) is None
        ):
            raise ValueError("invalid eligible candidate locator")


@dataclass(frozen=True)
class DiscoveryApplicationResult:
    """Bounded discovery handoff; it grants no publication admission."""

    run_id: str
    state_root_digest: str
    state_commit_sha: str
    eligible_candidates: tuple[EligibleCandidateLocator, ...]

    def __post_init__(self) -> None:
        if (
            not self.run_id
            or len(self.run_id) > 128
            or _DIGEST.fullmatch(self.state_root_digest) is None
            or _STATE_SHA.fullmatch(self.state_commit_sha) is None
            or len(self.eligible_candidates) > DISCOVERY_MAX_SEMANTIC_CANDIDATES * 3
            or len({item.locator for item in self.eligible_candidates})
            != len(self.eligible_candidates)
        ):
            raise ValueError("invalid discovery application result")


class DiscoveryApplication:
    """Thin dependency boundary for the production composition in Plan 05-08.

    The bootstrap layer supplies an operations-owned coordinator after all
    non-secret authority has been validated.  Keeping the only invocation
    behind ``run_discovery`` lets that coordinator own its schema and exact
    restore/sync protocol without copying private store logic here.
    """

    def __init__(self, dependencies: DiscoveryDependencies) -> None:
        if type(dependencies) is not DiscoveryDependencies:
            raise TypeError("invalid discovery dependencies")
        self._dependencies = dependencies

    def run(self, authority: object | None = None) -> DiscoveryApplicationResult:
        """Restore exact state and execute the owner-provided bounded controller."""

        restored = self._dependencies.state_restore()
        operations = self._dependencies.operations_store_factory()
        run_discovery = getattr(operations, "run_discovery", None)
        if not callable(run_discovery):
            raise TypeError("operations controller is unavailable")
        result = run_discovery(
            authority=authority,
            restored_state=restored,
            search_factory=self._dependencies.search_factory,
            durability_barrier=self._dependencies.durability_barrier,
            phase2_factory=self._dependencies.phase2_factory,
            phase3_factory=self._dependencies.phase3_factory,
            max_candidates=DISCOVERY_MAX_CANDIDATES,
            max_semantic_candidates=DISCOVERY_MAX_SEMANTIC_CANDIDATES,
        )
        if type(result) is not DiscoveryApplicationResult:
            raise TypeError("invalid discovery result")
        return result


@dataclass(frozen=True)
class WorkflowScenario:
    """One deterministic workflow outcome for orchestration contract tests."""

    outcome: WorkflowOutcome

    def __post_init__(self) -> None:
        if self.outcome not in _WORKFLOW_RESULT:
            raise ValueError("invalid workflow outcome")


@dataclass(frozen=True)
class DiscoveryScenario:
    """Bounded offline model of one repository and an optional safe successor."""

    repository_id: int
    workflows: tuple[WorkflowScenario, ...] = ()
    terminal: str | None = None
    later_repository_id: int | None = None

    def __post_init__(self) -> None:
        if (
            type(self.repository_id) is not int
            or self.repository_id <= 0
            or len(self.workflows) > 3
            or (
                self.later_repository_id is not None
                and (
                    type(self.later_repository_id) is not int
                    or self.later_repository_id <= 0
                    or self.later_repository_id == self.repository_id
                )
            )
            or (
                self.terminal is not None
                and self.terminal
                not in _CONTINUABLE_OUTCOMES | _FATAL_OUTCOMES
            )
            or (self.workflows and self.terminal is not None)
        ):
            raise ValueError("invalid discovery scenario")


@dataclass(frozen=True)
class DiscoveryScenarioResult:
    semantic_reservation_count: int
    workflow_outcomes: tuple[str, ...]
    workflow_authority_digests: tuple[str, ...]
    processed_repository_ids: tuple[int, ...]
    provider_request_count: int
    automatic_replay_count: int
    run_status: str


def evaluate_discovery_scenario(
    scenario: DiscoveryScenario,
) -> DiscoveryScenarioResult:
    """Evaluate bounded fan-out and terminal continuation without remote effects."""

    if type(scenario) is not DiscoveryScenario:
        raise TypeError("invalid discovery scenario")
    workflow_outcomes = tuple(
        _WORKFLOW_RESULT[workflow.outcome] for workflow in scenario.workflows
    )
    authorities = tuple(
        sha256_digest(
            {
                "schema_version": "discovery-workflow-scenario-v1",
                "repository_id": scenario.repository_id,
                "workflow_ordinal": ordinal,
                "outcome": workflow.outcome,
            }
        )
        for ordinal, workflow in enumerate(scenario.workflows, start=1)
    )
    terminal = scenario.terminal
    fatal = terminal in _FATAL_OUTCOMES
    processed = (scenario.repository_id,)
    if scenario.later_repository_id is not None and not fatal:
        processed += (scenario.later_repository_id,)
    unknown_count = (
        sum(outcome == "semantic_outcome_unknown" for outcome in workflow_outcomes)
        + (1 if terminal == "semantic_outcome_unknown" else 0)
    )
    if terminal == "state_integrity_conflict":
        run_status = "integrity_conflict"
    elif terminal == "permanent_failure":
        run_status = "permanent_failure"
    elif unknown_count:
        run_status = "completed_degraded"
    else:
        run_status = "completed"
    semantic_reserved = int(bool(scenario.workflows)) or int(
        terminal == "semantic_outcome_unknown"
    )
    return DiscoveryScenarioResult(
        semantic_reservation_count=semantic_reserved,
        workflow_outcomes=workflow_outcomes,
        workflow_authority_digests=authorities,
        processed_repository_ids=processed,
        provider_request_count=unknown_count,
        automatic_replay_count=0,
        run_status=run_status,
    )
