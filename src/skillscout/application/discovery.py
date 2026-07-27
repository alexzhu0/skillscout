"""Unprotected, bounded discovery composition through Phase 3.

This module deliberately owns no catalog or publication capability.  It
coordinates reviewed GitHub Search, the existing Phase 2 pipeline, and the
existing Phase 3 application, then stops at a content-addressed state handoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Callable, Literal, Protocol

from skillscout.application.phase3 import PhaseThreeApplication
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
    DiscoveredCandidateV1,
    DiscoveryQuerySetV1,
    DiscoveryCandidateTerminalV1,
    DiscoveryRunAuthorityV1,
    DiscoveryRunSummaryV1,
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
    query_set: DiscoveryQuerySetV1 | None = None
    initial_state_root_digest: str | None = None


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


def eligible_candidate_locator(
    *,
    authority_digest: str,
    workflow_identity_digest: str,
) -> EligibleCandidateLocator:
    """Derive the sole bounded locator form accepted by the protected reader."""

    if _DIGEST.fullmatch(authority_digest) is None:
        raise ValueError("invalid eligible authority")
    digest_hex = authority_digest.removeprefix("sha256:")
    return EligibleCandidateLocator(
        locator=(
            f"state/objects/sha256/{digest_hex[:2]}/{digest_hex}.json"
        ),
        authority_digest=authority_digest,
        workflow_identity_digest=workflow_identity_digest,
    )


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


@dataclass(frozen=True)
class DiscoveryCandidateExecution:
    """Complete Phase 2/3 result returned by the existing factory graph."""

    terminal: DiscoveryCandidateTerminalV1
    eligible_candidates: tuple[EligibleCandidateLocator, ...]
    state_commit_sha: str
    state_root_digest: str
    workflows: tuple[DiscoveryWorkflowExecution, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.terminal) is not DiscoveryCandidateTerminalV1
            or _STATE_SHA.fullmatch(self.state_commit_sha) is None
            or _DIGEST.fullmatch(self.state_root_digest) is None
            or len(self.eligible_candidates) > 3
            or tuple(
                workflow.locator
                for workflow in self.workflows
                if workflow.locator is not None
            )
            != tuple(item for item in self.eligible_candidates)
        ):
            raise ValueError("invalid discovery candidate execution")


@dataclass(frozen=True)
class DiscoveryWorkflowExecution:
    """One independently terminal sibling workflow."""

    workflow_authority_digest: str
    outcome: WorkflowOutcome | Literal[
        "completed_reuse", "permanent_failure"
    ]
    locator: EligibleCandidateLocator | None = None

    def __post_init__(self) -> None:
        eligible = self.outcome == "eligible"
        if (
            _DIGEST.fullmatch(self.workflow_authority_digest) is None
            or eligible is (self.locator is None)
            or (
                self.locator is not None
                and self.locator.workflow_identity_digest
                != self.workflow_authority_digest
            )
        ):
            raise ValueError("invalid discovery workflow execution")


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

        operations: object | None = None
        try:
            restored = self._dependencies.state_restore()
            operations = self._dependencies.operations_store_factory()
            run_discovery = getattr(operations, "run_discovery", None)
            if callable(run_discovery):
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
            else:
                result = self._run_operations_store(
                    operations=operations,
                    restored=restored,
                    authority=authority,
                )
            if type(result) is not DiscoveryApplicationResult:
                raise TypeError("invalid discovery result")
            return result
        except SafeFailure:
            raise
        except Exception:
            raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED) from None
        finally:
            close = getattr(operations, "close", None)
            if callable(close):
                close()

    def _run_operations_store(
        self,
        *,
        operations: object,
        restored: object,
        authority: object,
    ) -> DiscoveryApplicationResult:
        """Run the concrete operations-owned empty/business funnel safely.

        Candidate semantic processing remains delegated to the existing Phase
        2/3 factories. This method owns Search acquisition, deterministic
        deduplication, durable page checkpoints, and the terminal state handoff.
        """

        query_set = self._dependencies.query_set
        expected_root = self._dependencies.initial_state_root_digest
        if (
            type(authority) is not DiscoveryRunAuthorityV1
            or type(query_set) is not DiscoveryQuerySetV1
            or expected_root != authority.initial_state_root_digest
            or getattr(restored, "status", None) != "verified"
            or getattr(restored, "observed_head", None) is None
            or getattr(getattr(restored, "bundle", None), "root", None) is None
            or not all(
                callable(getattr(operations, name, None))
                for name in (
                    "create_run",
                    "find_run_authority_digest",
                    "snapshot_run",
                    "record_search_page",
                    "reserve_discovery_candidate",
                    "record_run_summary",
                    "close",
                )
            )
        ):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)

        existing_authority = operations.find_run_authority_digest(
            authority.run_id
        )
        if (
            existing_authority is None
            and restored.bundle.root.root_digest != expected_root
        ) or (
            existing_authority is not None
            and existing_authority != authority.authority_digest
        ):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        if existing_authority is not None:
            snapshot = operations.snapshot_run(authority.run_id)
            completed = _completed_result_from_snapshot(
                restored=restored, authority=authority, snapshot=snapshot
            )
            if completed is not None:
                return completed
        now = _timestamp()
        operations.create_run(authority, now)
        observed_head = restored.observed_head
        root_digest = restored.bundle.root.root_digest
        snapshot = operations.snapshot_run(authority.run_id)
        selected = sorted(
            (
                candidate
                for candidate in snapshot.candidates
                if candidate.dedup_disposition == "first_seen"
            ),
            key=lambda item: item.discovery_ordinal or 0,
        )
        seen = {
            candidate.repository.repository_id: (
                candidate.first_seen_query_ordinal,
                candidate.first_seen_page,
                candidate.first_seen_item_ordinal,
            )
            for candidate in snapshot.candidates
            if candidate.dedup_disposition
            in {"first_seen", "duplicate"}
        }
        search = self._dependencies.search_factory()
        try:
            page_by_query = {
                ordinal: sorted(
                    (
                        page
                        for page in snapshot.search_pages
                        if page.query_ordinal == ordinal
                    ),
                    key=lambda item: item.page,
                )
                for ordinal in range(1, len(query_set.queries) + 1)
            }
            active_pages = {}
            for ordinal, pages in page_by_query.items():
                if not pages:
                    active_pages[ordinal] = 1
                elif pages[-1].next_page is not None:
                    active_pages[ordinal] = pages[-1].next_page
            while active_pages and len(selected) < DISCOVERY_MAX_CANDIDATES:
                for query_ordinal in tuple(sorted(active_pages)):
                    page_number = active_pages[query_ordinal]
                    page, repositories = search.search_repositories(
                        query_set=query_set,
                        discovery_run_authority_digest=authority.authority_digest,
                        query_ordinal=query_ordinal,
                        page=page_number,
                    )
                    candidates: list[DiscoveredCandidateV1] = []
                    for item_ordinal, repository in enumerate(
                        repositories, start=1
                    ):
                        first = seen.get(repository.repository_id)
                        if first is None and len(selected) < DISCOVERY_MAX_CANDIDATES:
                            first = (query_ordinal, page_number, item_ordinal)
                            seen[repository.repository_id] = first
                            disposition = "first_seen"
                            discovery_ordinal = len(selected) + 1
                        else:
                            disposition = (
                                "duplicate"
                                if first is not None
                                else "budget_excluded"
                            )
                            discovery_ordinal = None
                            if first is None:
                                first = (
                                    query_ordinal,
                                    page_number,
                                    item_ordinal,
                                )
                        values = {
                            "schema_version": "discovered-candidate-v1",
                            "discovery_run_authority_digest": authority.authority_digest,
                            "repository": repository,
                            "source_page_digest": page.observation_digest,
                            "query_ordinal": query_ordinal,
                            "page": page_number,
                            "item_ordinal": item_ordinal,
                            "dedup_disposition": disposition,
                            "discovery_ordinal": discovery_ordinal,
                            "first_seen_query_ordinal": first[0],
                            "first_seen_page": first[1],
                            "first_seen_item_ordinal": first[2],
                        }
                        candidate = DiscoveredCandidateV1(
                            **values,
                            candidate_digest=sha256_digest(
                                {
                                    key: (
                                        value.model_dump(
                                            mode="json", exclude_none=False
                                        )
                                        if hasattr(value, "model_dump")
                                        else value
                                    )
                                    for key, value in values.items()
                                }
                            ),
                        )
                        candidates.append(candidate)
                        if disposition == "first_seen":
                            selected.append(candidate)
                    operations.record_search_page(
                        authority.run_id, page, tuple(candidates)
                    )
                    synchronized = self._sync(
                        operations=operations,
                        observed_head=observed_head,
                        root_digest=root_digest,
                    )
                    observed_head = synchronized.commit_sha
                    root_digest = synchronized.root_digest
                    if page.next_page is None:
                        active_pages.pop(query_ordinal)
                    else:
                        active_pages[query_ordinal] = page.next_page
                    if len(selected) >= DISCOVERY_MAX_CANDIDATES:
                        break
        finally:
            close = getattr(search, "close", None)
            if callable(close):
                close()

        eligible: list[EligibleCandidateLocator] = []
        terminals = list(snapshot.candidate_terminals)
        terminal_repository_ids = {
            terminal.repository_id for terminal in terminals
        }
        durable_discovery_reservations = {
            reservation.repository_id: reservation
            for reservation in snapshot.discovery_reservations
        }
        for candidate in selected:
            if candidate.repository.repository_id in terminal_repository_ids:
                continue
            durable_reservation = durable_discovery_reservations.get(
                candidate.repository.repository_id
            )
            reservation = operations.reserve_discovery_candidate(
                authority.run_id,
                candidate,
                _timestamp(),
            )
            if durable_reservation is not None:
                if (
                    reservation != durable_reservation
                    or reservation.discovery_run_authority_digest
                    != authority.authority_digest
                    or reservation.repository_id
                    != candidate.repository.repository_id
                    or reservation.candidate_digest
                    != candidate.candidate_digest
                    or reservation.ordinal != candidate.discovery_ordinal
                ):
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            else:
                synchronized = self._sync(
                    operations=operations,
                    observed_head=observed_head,
                    root_digest=root_digest,
                )
                observed_head = synchronized.commit_sha
                root_digest = synchronized.root_digest
            execution = self._dependencies.phase2_factory(
                candidate=candidate,
                discovery_reservation=reservation,
                discovery_authority=authority,
                operations_store=operations,
                durability_barrier=self._dependencies.durability_barrier,
                observed_head=observed_head,
                prior_root_digest=root_digest,
                phase3_factory=self._dependencies.phase3_factory,
            )
            if type(execution) is not DiscoveryCandidateExecution:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            for workflow in execution.workflows:
                operations.record_workflow_terminal(
                    run_id=authority.run_id,
                    repository_id=candidate.repository.repository_id,
                    workflow_authority_digest=(
                        workflow.workflow_authority_digest
                    ),
                    outcome=(
                        "eligible_local_candidate"
                        if workflow.outcome == "eligible"
                        else workflow.outcome
                    ),
                    eligible_locator=(
                        workflow.locator.locator
                        if workflow.locator is not None
                        else None
                    ),
                    eligible_object_digest=(
                        workflow.locator.authority_digest
                        if workflow.locator is not None
                        else None
                    ),
                    recorded_at=_timestamp(),
                )
            operations.record_candidate_terminal(
                authority.run_id, execution.terminal
            )
            observed_head = execution.state_commit_sha
            root_digest = execution.state_root_digest
            synchronized = self._sync(
                operations=operations,
                observed_head=observed_head,
                root_digest=root_digest,
            )
            observed_head = synchronized.commit_sha
            root_digest = synchronized.root_digest
            terminals.append(execution.terminal)
            eligible.extend(execution.eligible_candidates)
            if execution.terminal.outcome in _FATAL_OUTCOMES:
                break

        summary_values: dict[str, object] = {
            "schema_version": "discovery-run-summary-v1",
            "discovery_run_authority_digest": authority.authority_digest,
            "status": "completed",
            "selected_candidate_count": len(selected),
            "semantic_reservation_count": sum(
                terminal.semantic_reservation_digest is not None
                for terminal in terminals
            ),
            "business_terminal_count": sum(
                terminal.outcome in _BUSINESS_OUTCOMES for terminal in terminals
            ),
            "quarantined_candidate_count": sum(
                terminal.outcome == "semantic_outcome_unknown"
                for terminal in terminals
            ),
            "confirmed_retryable_count": sum(
                terminal.outcome == "confirmed_retryable"
                for terminal in terminals
            ),
            "integrity_conflict_count": sum(
                terminal.outcome == "state_integrity_conflict"
                for terminal in terminals
            ),
            "permanent_failure_count": sum(
                terminal.outcome == "permanent_failure"
                for terminal in terminals
            ),
            "terminal_digests": tuple(
                terminal.terminal_digest
                for terminal in sorted(
                    terminals, key=lambda item: item.repository_id
                )
            ),
            "completed_at": _timestamp(),
        }
        if any(
            terminal.outcome == "state_integrity_conflict"
            for terminal in terminals
        ):
            summary_values["status"] = "integrity_conflict"
        elif any(
            terminal.outcome == "permanent_failure" for terminal in terminals
        ):
            summary_values["status"] = "permanent_failure"
        elif any(
            terminal.outcome == "semantic_outcome_unknown"
            for terminal in terminals
        ):
            summary_values["status"] = "completed_degraded"
        elif any(
            terminal.outcome == "confirmed_retryable" for terminal in terminals
        ):
            summary_values["status"] = "confirmed_retryable"
        summary = DiscoveryRunSummaryV1(
            **summary_values,
            summary_digest=sha256_digest(summary_values),
        )
        operations.record_run_summary(authority.run_id, summary)
        synchronized = self._sync(
            operations=operations,
            observed_head=observed_head,
            root_digest=root_digest,
        )
        return DiscoveryApplicationResult(
            run_id=authority.run_id,
            state_root_digest=synchronized.root_digest,
            state_commit_sha=synchronized.commit_sha,
            eligible_candidates=tuple(eligible),
        )

    def _sync(
        self,
        *,
        operations: object,
        observed_head: str,
        root_digest: str,
    ) -> object:
        synchronize = getattr(
            self._dependencies.durability_barrier,
            "sync_discovery",
            None,
        )
        if not callable(synchronize):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        return synchronize(
            operations_store=operations,
            observed_head=observed_head,
            prior_root_digest=root_digest,
            created_at=_timestamp(),
        )


def _timestamp() -> str:
    return (
        datetime.now(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _completed_result_from_snapshot(
    *,
    restored: object,
    authority: DiscoveryRunAuthorityV1,
    snapshot: object,
) -> DiscoveryApplicationResult | None:
    """Reconstruct an immutable completed handoff without replaying Search."""

    try:
        summary = snapshot.summary
        if summary is None:
            return None
        files = restored.bundle.content_by_path()
        if (
            summary.discovery_run_authority_digest
            != authority.authority_digest
        ):
            raise ValueError
        eligible: list[EligibleCandidateLocator] = []
        root_objects = {
            item.locator: item.object_digest
            for item in restored.bundle.root.objects
        }
        for workflow in snapshot.workflow_terminals:
            if workflow.outcome != "eligible_local_candidate":
                continue
            locator = eligible_candidate_locator(
                authority_digest=workflow.eligible_object_digest,
                workflow_identity_digest=workflow.workflow_authority_digest,
            )
            if (
                workflow.eligible_locator != locator.locator
                or root_objects.get(locator.locator)
                != locator.authority_digest
                or sha256_digest(files[locator.locator])
                != locator.authority_digest
            ):
                raise ValueError
            eligible.append(locator)
        if len(eligible) > summary.semantic_reservation_count * 3:
            raise ValueError
        return DiscoveryApplicationResult(
            run_id=authority.run_id,
            state_root_digest=restored.bundle.root.root_digest,
            state_commit_sha=restored.observed_head,
            eligible_candidates=tuple(eligible),
        )
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


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
