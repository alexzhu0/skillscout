"""Capability-separated orchestration helpers for Phase 6 acceptance.

The acceptance layer composes existing owners; it does not add a second
discovery, semantic, publication, or persistence implementation.  Every
dependency surface is deliberately frozen so callers cannot smuggle evaluator
answers or a broader live capability into an offline transition.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable, Final, Literal, Mapping

from skillscout.adapters.operations_state import (
    AcceptanceFactRecord,
    AcceptanceRunSnapshot,
)
from skillscout.domain.acceptance import (
    AcceptanceScenarioResultV1,
    ChangedSourceDraftUpdateCompletionV1,
    ChangedSourceEvidenceV1,
    HumanSkillReviewAttestationV1,
    LockedBenchmarkManifestV1,
    NominationSetV1,
    ProbeCleanupAttestationV1,
    PublicationReplayCompletionV1,
    ReplayEvidenceV1,
)

AcceptanceTerminal = Literal[
    "business_terminal", "eligible", "system_failure"
]

_BUSINESS_TERMINALS: Final = frozenset(
    {
        "filter_rejected",
        "no_workflow",
        "qualification_rejected",
        "validation_rejected",
        "review_rejected",
    }
)
_ELIGIBLE_TERMINALS: Final = frozenset(
    {"eligible", "eligible_local_candidate"}
)
_SYSTEM_FAILURES: Final = frozenset(
    {
        "provider_exhausted",
        "schema_exhausted",
        "evidence_missing",
        "duplicate_effect",
        "unauthorized_effect",
        "secret_exposure",
        "untrusted_execution",
        "harness_failed",
        "rebuild_failed",
    }
)
_EVALUATOR_ONLY_FIELDS: Final = frozenset(
    {
        "expected_role",
        "expected_outcome",
        "evaluator_notes",
        "human_label",
        "coverage_role",
        "selection_notes",
    }
)


class AcceptanceApplicationError(RuntimeError):
    """Closed application failure that carries no provider or fixture detail."""

    def __init__(self, code: str) -> None:
        if code not in _SYSTEM_FAILURES:
            raise ValueError("invalid acceptance application error")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class NominationDependencies:
    """Search and operations state are the complete nomination authority."""

    search_factory: Callable[[], object]
    operations_store_factory: Callable[[], object]


@dataclass(frozen=True)
class LockedCampaignDependencies:
    """Late production capabilities admitted only after manifest revalidation."""

    discovery_factory: Callable[[], object]
    operations_store_factory: Callable[[], object]
    candidate_factory: Callable[[], object] | None = None
    publication_factory: Callable[[], object] | None = None


@dataclass(frozen=True)
class ReplayUpdateDependencies:
    """Completed-first replay/update composition with a late Draft publisher."""

    completed_projector_factory: Callable[[], object]
    operations_store_factory: Callable[[], object]
    publication_factory: Callable[[], object] | None = None


@dataclass(frozen=True)
class HumanAttestationDependencies:
    """Read/reconcile authority for exact-head human attestations."""

    operations_store_factory: Callable[[], object]
    observation_factory: Callable[[], object]


@dataclass(frozen=True)
class CleanupAttestationDependencies:
    """Read/reconcile authority for separately performed probe cleanup."""

    operations_store_factory: Callable[[], object]
    observation_factory: Callable[[], object]


@dataclass(frozen=True)
class AcceptanceRebuildDependencies:
    """Offline state owner used to reconstruct acceptance evidence."""

    operations_store_factory: Callable[[], object]


@dataclass(frozen=True)
class OfflineEvaluationDependencies:
    """Offline evaluators can read verified state but own no live adapter."""

    operations_store_factory: Callable[[], object]


def classify_acceptance_terminal(outcome: str) -> AcceptanceTerminal:
    """Map only the closed Phase 6 terminal vocabulary."""

    if outcome in _BUSINESS_TERMINALS:
        return "business_terminal"
    if outcome in _ELIGIBLE_TERMINALS:
        return "eligible"
    if outcome in _SYSTEM_FAILURES:
        return "system_failure"
    raise ValueError("unknown acceptance terminal")


def build_acceptance_semantic_payload(
    *,
    workflow_spec: Mapping[str, object],
    provenance: Mapping[str, object],
) -> dict[str, object]:
    """Return the sole evaluator-blind semantic request projection.

    A JSON round trip both detaches caller-owned containers and rejects values
    that could not cross the existing structured semantic boundary.
    """

    if not isinstance(workflow_spec, Mapping) or not isinstance(
        provenance, Mapping
    ):
        raise TypeError("acceptance semantic input must be structured")
    candidate = {
        "workflow_spec": dict(workflow_spec),
        "provenance": dict(provenance),
    }
    if _contains_evaluator_field(candidate):
        raise ValueError("evaluator-only field cannot enter semantic input")
    try:
        serialized = json.dumps(
            candidate,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        detached = json.loads(serialized)
    except (TypeError, ValueError):
        raise ValueError("acceptance semantic input is not canonical JSON") from None
    if type(detached) is not dict:
        raise ValueError("acceptance semantic input is not an object")
    return detached


def re_admit_locked_manifest(
    snapshot: AcceptanceRunSnapshot,
    manifest: LockedBenchmarkManifestV1,
) -> NominationSetV1:
    """Bind a five-entry lock back to its exact persisted nomination."""

    if (
        type(snapshot) is not AcceptanceRunSnapshot
        or type(manifest) is not LockedBenchmarkManifestV1
    ):
        raise TypeError("invalid benchmark re-admission input")
    nominations = tuple(
        record.fact
        for record in snapshot.facts
        if record.kind == "acceptance_nomination"
        and record.fact_digest == manifest.nomination_set_digest
    )
    if len(nominations) != 1 or type(nominations[0]) is not NominationSetV1:
        raise AcceptanceApplicationError("evidence_missing")
    nomination = nominations[0]
    nominated_by_digest = {
        entry.entry_digest: entry
        for entry in (
            nomination.search_derived_entries
            + nomination.user_nominated_entries
        )
    }
    if (
        len(manifest.entries) != 5
        or any(
            nominated_by_digest.get(entry.entry_digest) != entry
            for entry in manifest.entries
        )
    ):
        raise AcceptanceApplicationError("evidence_missing")
    return nomination


def record_nomination(
    dependencies: NominationDependencies,
    nomination: NominationSetV1,
    *,
    acceptance_run_id: str | None = None,
) -> AcceptanceFactRecord:
    """Persist one deterministic Search-derived nomination fact."""

    if type(dependencies) is not NominationDependencies:
        raise TypeError("invalid nomination dependencies")
    return _record_fact(
        dependencies.operations_store_factory,
        acceptance_run_id or nomination.nomination_set_id,
        "acceptance_nomination",
        nomination,
    )


def record_locked_manifest(
    dependencies: LockedCampaignDependencies,
    *,
    acceptance_run_id: str,
    manifest: LockedBenchmarkManifestV1,
) -> AcceptanceFactRecord:
    """Re-admit and persist the exact human-locked five-entry benchmark."""

    if type(dependencies) is not LockedCampaignDependencies:
        raise TypeError("invalid locked campaign dependencies")
    store = dependencies.operations_store_factory()
    try:
        snapshot = _snapshot(store, acceptance_run_id)
        re_admit_locked_manifest(snapshot, manifest)
        return _record_on_open_store(
            store,
            acceptance_run_id,
            "acceptance_benchmark_lock",
            manifest,
        )
    finally:
        _close(store)


def record_scenario_result(
    dependencies: LockedCampaignDependencies,
    result: AcceptanceScenarioResultV1,
) -> AcceptanceFactRecord:
    """Persist an observed terminal only after its closed class reconciles."""

    if type(dependencies) is not LockedCampaignDependencies:
        raise TypeError("invalid locked campaign dependencies")
    if classify_acceptance_terminal(result.outcome) != result.terminal_class:
        raise AcceptanceApplicationError("evidence_missing")
    return _record_fact(
        dependencies.operations_store_factory,
        result.acceptance_run_id,
        "acceptance_scenario",
        result,
    )


def record_replay_or_update_intent(
    dependencies: ReplayUpdateDependencies,
    fact: ReplayEvidenceV1 | ChangedSourceEvidenceV1,
) -> AcceptanceFactRecord:
    """Persist a verified intent without granting publication by itself."""

    if type(dependencies) is not ReplayUpdateDependencies:
        raise TypeError("invalid replay/update dependencies")
    if type(fact) is ReplayEvidenceV1:
        kind = "acceptance_replay"
    elif type(fact) is ChangedSourceEvidenceV1:
        kind = "acceptance_changed_source"
    else:
        raise TypeError("invalid replay/update intent")
    return _record_fact(
        dependencies.operations_store_factory,
        fact.acceptance_run_id,
        kind,
        fact,
    )


def record_replay_or_update_completion(
    dependencies: ReplayUpdateDependencies,
    fact: (
        PublicationReplayCompletionV1
        | ChangedSourceDraftUpdateCompletionV1
    ),
) -> AcceptanceFactRecord:
    """Persist post-effect completion separately from its prior intent."""

    if type(dependencies) is not ReplayUpdateDependencies:
        raise TypeError("invalid replay/update dependencies")
    if type(fact) is PublicationReplayCompletionV1:
        kind = "acceptance_publication_replay_completion"
    elif type(fact) is ChangedSourceDraftUpdateCompletionV1:
        kind = "acceptance_changed_source_draft_update_completion"
    else:
        raise TypeError("invalid replay/update completion")
    return _record_fact(
        dependencies.operations_store_factory,
        fact.acceptance_run_id,
        kind,
        fact,
    )


def record_human_attestation(
    dependencies: HumanAttestationDependencies,
    fact: HumanSkillReviewAttestationV1,
) -> AcceptanceFactRecord:
    """Record a reconciled exact-head human verdict without edit authority."""

    if type(dependencies) is not HumanAttestationDependencies:
        raise TypeError("invalid human attestation dependencies")
    return _record_fact(
        dependencies.operations_store_factory,
        fact.acceptance_run_id,
        "acceptance_human_review",
        fact,
    )


def record_cleanup_attestation(
    dependencies: CleanupAttestationDependencies,
    fact: ProbeCleanupAttestationV1,
) -> AcceptanceFactRecord:
    """Record separately performed cleanup without exposing cleanup methods."""

    if type(dependencies) is not CleanupAttestationDependencies:
        raise TypeError("invalid cleanup attestation dependencies")
    return _record_fact(
        dependencies.operations_store_factory,
        fact.acceptance_run_id,
        "acceptance_cleanup",
        fact,
    )


def rebuild_acceptance_snapshot(
    dependencies: AcceptanceRebuildDependencies,
    acceptance_run_id: str,
) -> AcceptanceRunSnapshot:
    """Read the canonical typed acceptance projection with no live client."""

    if type(dependencies) is not AcceptanceRebuildDependencies:
        raise TypeError("invalid rebuild dependencies")
    store = dependencies.operations_store_factory()
    try:
        return _snapshot(store, acceptance_run_id)
    finally:
        _close(store)


def classify_acceptance_terminal_from_fact(
    record: AcceptanceFactRecord,
) -> AcceptanceTerminal | None:
    """Classify scenario facts while leaving other fact kinds unlabelled."""

    if type(record) is not AcceptanceFactRecord:
        raise TypeError("invalid acceptance fact record")
    if type(record.fact) is not AcceptanceScenarioResultV1:
        return None
    return classify_acceptance_terminal(record.fact.outcome)


def _record_fact(
    factory: Callable[[], object],
    acceptance_run_id: str,
    kind: str,
    fact: object,
) -> AcceptanceFactRecord:
    store = factory()
    try:
        return _record_on_open_store(
            store, acceptance_run_id, kind, fact
        )
    finally:
        _close(store)


def _record_on_open_store(
    store: object,
    acceptance_run_id: str,
    kind: str,
    fact: object,
) -> AcceptanceFactRecord:
    record = getattr(store, "record_acceptance_fact", None)
    if not callable(record):
        raise AcceptanceApplicationError("evidence_missing")
    try:
        result = record(acceptance_run_id, kind, fact)
    except AcceptanceApplicationError:
        raise
    except Exception:
        raise AcceptanceApplicationError("evidence_missing") from None
    if type(result) is not AcceptanceFactRecord:
        raise AcceptanceApplicationError("evidence_missing")
    return result


def _snapshot(store: object, acceptance_run_id: str) -> AcceptanceRunSnapshot:
    read = getattr(store, "acceptance_snapshot", None)
    if not callable(read):
        raise AcceptanceApplicationError("evidence_missing")
    try:
        snapshot = read(acceptance_run_id)
    except AcceptanceApplicationError:
        raise
    except Exception:
        raise AcceptanceApplicationError("evidence_missing") from None
    if type(snapshot) is not AcceptanceRunSnapshot:
        raise AcceptanceApplicationError("evidence_missing")
    return snapshot


def _contains_evaluator_field(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold().replace("-", "_")
            in _EVALUATOR_ONLY_FIELDS
            or _contains_evaluator_field(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (tuple, list)):
        return any(_contains_evaluator_field(item) for item in value)
    return False


def _close(resource: object) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
