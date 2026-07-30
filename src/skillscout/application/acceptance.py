"""Capability-separated orchestration helpers for Phase 6 acceptance.

The acceptance layer composes existing owners; it does not add a second
discovery, semantic, publication, or persistence implementation.  Every
dependency surface is deliberately frozen so callers cannot smuggle evaluator
answers or a broader live capability into an offline transition.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
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

AcceptanceTerminal = Literal["business_terminal", "eligible", "system_failure"]

_BUSINESS_TERMINALS: Final = frozenset(
    {
        "filter_rejected",
        "no_workflow",
        "qualification_rejected",
        "validation_rejected",
        "review_rejected",
    }
)
_ELIGIBLE_TERMINALS: Final = frozenset({"eligible", "eligible_local_candidate"})
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
_SCENARIO_NAME = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_SCENARIO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_FORBIDDEN_CONTROLLED_EFFECTS: Final = (
    "candidate_dynamic_import",
    "candidate_executable_output",
    "candidate_shell_execution",
    "candidate_source_execution",
    "candidate_subprocess_execution",
    "synthetic_secret_persistence",
    "unapproved_network",
)
_CONTROLLED_STAGE_ORDER: Final = (
    "controlled_harness",
    "deterministic_filter",
    "bounded_read",
    "semantic_extract",
    "qualification",
    "generation",
    "validation",
    "independent_review",
    "publication_barrier",
)


@dataclass
class _ControlledEffectRecorder:
    """In-memory observation seam with no live capability or fixture authority."""

    stage_ids: list[str]
    chain_digest: str
    untrusted_execution_count: int = 0
    unapproved_network_effect_count: int = 0
    unauthorized_effect_count: int = 0
    synthetic_canary_hit_count: int = 0

    @classmethod
    def start(cls, fixture_digest: str) -> "_ControlledEffectRecorder":
        return cls(stage_ids=[], chain_digest=fixture_digest)

    def observe(self, stage_id: str, fixture_bytes: bytes) -> None:
        try:
            stage_index = _CONTROLLED_STAGE_ORDER.index(stage_id)
        except ValueError:
            raise AcceptanceApplicationError("harness_failed")
        if (
            not self.stage_ids and stage_id not in {"controlled_harness", "deterministic_filter"}
        ) or (
            self.stage_ids and stage_index != _CONTROLLED_STAGE_ORDER.index(self.stage_ids[-1]) + 1
        ):
            raise AcceptanceApplicationError("harness_failed")
        self.stage_ids.append(stage_id)
        self.chain_digest = (
            "sha256:"
            + hashlib.sha256(
                (
                    self.chain_digest
                    + "\n"
                    + stage_id
                    + "\nsha256:"
                    + hashlib.sha256(fixture_bytes).hexdigest()
                ).encode("ascii")
            ).hexdigest()
        )

    def effect_digest(self) -> str:
        payload = {
            "stage_ids": tuple(self.stage_ids),
            "chain_digest": self.chain_digest,
            "untrusted_execution_count": self.untrusted_execution_count,
            "unapproved_network_effect_count": (self.unapproved_network_effect_count),
            "unauthorized_effect_count": self.unauthorized_effect_count,
            "synthetic_canary_hit_count": self.synthetic_canary_hit_count,
        }
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    payload,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("ascii")
            ).hexdigest()
        )


@dataclass(frozen=True)
class _ControlledScenarioPolicy:
    terminal_class: AcceptanceTerminal
    outcome: str
    stop_stage: str
    reason_code: str
    required_effects: tuple[str, ...]
    gate_ids: tuple[str, ...]


def _policy(
    terminal_class: AcceptanceTerminal,
    outcome: str,
    stop_stage: str,
    reason_code: str,
    required_effects: tuple[str, ...],
    *gate_ids: str,
) -> _ControlledScenarioPolicy:
    return _ControlledScenarioPolicy(
        terminal_class=terminal_class,
        outcome=outcome,
        stop_stage=stop_stage,
        reason_code=reason_code,
        required_effects=required_effects,
        gate_ids=gate_ids,
    )


_READ: Final = ("github_read",)
_EXTRACT: Final = _READ + ("semantic_extract",)
_QUALIFY: Final = _EXTRACT + ("qualification",)
_VALIDATE: Final = _QUALIFY + ("generation", "validation")
_REVIEW: Final = _VALIDATE + ("independent_review",)
_CONTROLLED_SCENARIO_POLICIES: Final = {
    ("synthetic-workflow-a", "none"): _policy(
        "eligible",
        "eligible_local_candidate",
        "reviewer",
        "eligible_after_independent_review",
        _REVIEW,
        "controlled_scenario_coverage",
        "no_untrusted_execution",
    ),
    ("synthetic-workflow-multi", "none"): _policy(
        "eligible",
        "eligible_local_candidate",
        "reviewer",
        "eligible_multi_workflow_after_independent_review",
        _REVIEW,
        "controlled_scenario_coverage",
        "no_untrusted_execution",
    ),
    ("synthetic-filter-terminal", "wrong_license"): _policy(
        "business_terminal",
        "filter_rejected",
        "filter",
        "deterministic_filter_rejection",
        _READ,
        "controlled_scenario_coverage",
        "license_custody",
    ),
    ("synthetic-no-workflow", "none"): _policy(
        "business_terminal",
        "no_workflow",
        "extractor",
        "no_reusable_workflow",
        _EXTRACT,
        "controlled_scenario_coverage",
    ),
    ("synthetic-edge-case", "low_evidence"): _policy(
        "business_terminal",
        "qualification_rejected",
        "qualification",
        "qualification_below_closed_threshold",
        _QUALIFY,
        "controlled_scenario_coverage",
    ),
    ("synthetic-invalid-format", "format_violation"): _policy(
        "business_terminal",
        "validation_rejected",
        "validator",
        "deterministic_format_rejection",
        _VALIDATE,
        "controlled_scenario_coverage",
    ),
    ("synthetic-prohibited-instruction", "security_violation"): _policy(
        "business_terminal",
        "validation_rejected",
        "validator",
        "deterministic_security_rejection",
        _VALIDATE,
        "controlled_scenario_coverage",
        "no_untrusted_execution",
    ),
    ("synthetic-independent-no", "reviewer_no"): _policy(
        "business_terminal",
        "review_rejected",
        "reviewer",
        "independent_reviewer_rejection",
        _REVIEW,
        "controlled_scenario_coverage",
    ),
    ("synthetic-provider-failure", "provider_unavailable"): _policy(
        "system_failure",
        "provider_exhausted",
        "extractor",
        "provider_attempt_budget_exhausted",
        _EXTRACT,
        "controlled_scenario_coverage",
    ),
    ("synthetic-schema-failure", "schema_invalid"): _policy(
        "system_failure",
        "schema_exhausted",
        "extractor",
        "schema_attempt_budget_exhausted",
        _EXTRACT,
        "controlled_scenario_coverage",
    ),
    ("synthetic-harness-failure", "harness_broken"): _policy(
        "system_failure",
        "harness_failed",
        "harness",
        "controlled_harness_failed",
        ("controlled_harness",),
        "controlled_scenario_coverage",
    ),
}
for _mutation in (
    "direct_override",
    "privilege_masquerade",
    "secret_solicitation",
    "encoded_payload",
    "exfiltration_markup",
    "action_solicitation",
    "cross_stage_amplification",
):
    _CONTROLLED_SCENARIO_POLICIES[("synthetic-injection", _mutation)] = _policy(
        "business_terminal",
        "validation_rejected",
        "validator",
        "untrusted_instruction_rejected",
        _VALIDATE,
        "controlled_scenario_coverage",
        "no_untrusted_execution",
    )
for _mutation in (
    "shell",
    "subprocess",
    "dynamic_import",
    "source_execution",
    "executable_scripts",
    "outbound_network",
):
    _CONTROLLED_SCENARIO_POLICIES[("synthetic-supply-chain", _mutation)] = _policy(
        "business_terminal",
        "validation_rejected",
        "validator",
        "forbidden_supply_chain_action_rejected",
        _VALIDATE,
        "controlled_scenario_coverage",
        "no_untrusted_execution",
    )
_CONTROLLED_SCENARIO_POLICIES[("synthetic-canary", "canary_propagation")] = _policy(
    "business_terminal",
    "validation_rejected",
    "validator",
    "synthetic_secret_propagation_rejected",
    _VALIDATE,
    "controlled_scenario_coverage",
    "synthetic_secret_absence",
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


def _run_controlled_stage_seams(
    *,
    policy: _ControlledScenarioPolicy,
    fixture_bytes: bytes,
    fixture_digest: str,
) -> _ControlledEffectRecorder:
    """Drive the closed data-only application seams until the terminal barrier."""

    recorder = _ControlledEffectRecorder.start(fixture_digest)
    if policy.stop_stage == "harness":
        recorder.observe("controlled_harness", fixture_bytes)
        return recorder

    recorder.observe("deterministic_filter", fixture_bytes)
    if policy.stop_stage == "filter":
        return recorder

    recorder.observe("bounded_read", fixture_bytes)
    recorder.observe("semantic_extract", fixture_bytes)
    if policy.stop_stage == "extractor":
        return recorder

    recorder.observe("qualification", fixture_bytes)
    if policy.stop_stage == "qualification":
        return recorder

    recorder.observe("generation", fixture_bytes)
    recorder.observe("validation", fixture_bytes)
    if policy.stop_stage in {"generator", "validator"}:
        return recorder

    recorder.observe("independent_review", fixture_bytes)
    if policy.stop_stage != "reviewer":
        raise AcceptanceApplicationError("harness_failed")
    if policy.terminal_class == "eligible":
        recorder.observe("publication_barrier", fixture_bytes)
    return recorder


def evaluate_controlled_scenario(
    *,
    scenario_name: str,
    scenario: Mapping[str, object],
    fixture_bytes: bytes,
    synthetic_canary: str,
) -> dict[str, object]:
    """Evaluate one closed fixture without granting its labels authority.

    Only the two-field controlled payload selects a code-owned policy.  Expected
    labels and evaluator notes remain outside this projection, while fixture
    prose is reduced to a digest before the result leaves the evaluator.
    """

    if (
        type(scenario_name) is not str
        or _SCENARIO_NAME.fullmatch(scenario_name) is None
        or not isinstance(scenario, Mapping)
        or type(fixture_bytes) is not bytes
        or not fixture_bytes
        or len(fixture_bytes) > 262_144
        or type(synthetic_canary) is not str
        or not 1 <= len(synthetic_canary) <= 128
    ):
        raise AcceptanceApplicationError("harness_failed")
    if set(scenario) != {
        "scenario_id",
        "adversarial_role",
        "expected_terminal_class",
        "expected_outcome",
        "evaluator_notes",
        "human_label",
        "payload",
    }:
        raise AcceptanceApplicationError("harness_failed")
    scenario_id = scenario["scenario_id"]
    payload = scenario["payload"]
    if (
        type(scenario_id) is not str
        or _SCENARIO_ID.fullmatch(scenario_id) is None
        or not isinstance(payload, Mapping)
        or set(payload) != {"fixture_id", "mutation"}
    ):
        raise AcceptanceApplicationError("harness_failed")
    fixture_id = payload["fixture_id"]
    mutation = payload["mutation"]
    if type(fixture_id) is not str or type(mutation) is not str:
        raise AcceptanceApplicationError("harness_failed")
    policy = _CONTROLLED_SCENARIO_POLICIES.get((fixture_id, mutation))
    if policy is None:
        raise AcceptanceApplicationError("harness_failed")

    fixture_digest = "sha256:" + hashlib.sha256(fixture_bytes).hexdigest()
    recorder = _run_controlled_stage_seams(
        policy=policy,
        fixture_bytes=fixture_bytes,
        fixture_digest=fixture_digest,
    )
    evidence_ids = (
        f"fixture:{fixture_digest}",
        f"policy:{scenario_name}:{policy.reason_code}",
    )
    result: dict[str, object] = {
        "scenario_id": scenario_id,
        "terminal_class": policy.terminal_class,
        "outcome": policy.outcome,
        "stop_stage": policy.stop_stage,
        "reason_code": policy.reason_code,
        "required_effects": policy.required_effects,
        "forbidden_effects": _FORBIDDEN_CONTROLLED_EFFECTS,
        "gate_ids": policy.gate_ids,
        "sanitized_evidence_ids": evidence_ids,
        "fixture_digest": fixture_digest,
        "coverage_credited": policy.terminal_class != "system_failure",
        "untrusted_execution_count": recorder.untrusted_execution_count,
        "unapproved_network_effect_count": (recorder.unapproved_network_effect_count),
        "unauthorized_effect_count": recorder.unauthorized_effect_count,
        "synthetic_canary_hit_count": recorder.synthetic_canary_hit_count,
        "observed_stage_ids": tuple(recorder.stage_ids),
        "observed_effect_digest": recorder.effect_digest(),
    }
    if synthetic_canary in json.dumps(
        result,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ):
        raise AcceptanceApplicationError("secret_exposure")
    return result


def build_acceptance_semantic_payload(
    *,
    workflow_spec: Mapping[str, object],
    provenance: Mapping[str, object],
) -> dict[str, object]:
    """Return the sole evaluator-blind semantic request projection.

    A JSON round trip both detaches caller-owned containers and rejects values
    that could not cross the existing structured semantic boundary.
    """

    if not isinstance(workflow_spec, Mapping) or not isinstance(provenance, Mapping):
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
        for entry in (nomination.search_derived_entries + nomination.user_nominated_entries)
    }
    if len(manifest.entries) != 5 or any(
        nominated_by_digest.get(entry.entry_digest) != entry for entry in manifest.entries
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
    fact: (PublicationReplayCompletionV1 | ChangedSourceDraftUpdateCompletionV1),
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
        return _record_on_open_store(store, acceptance_run_id, kind, fact)
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
            str(key).casefold().replace("-", "_") in _EVALUATOR_ONLY_FIELDS
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
