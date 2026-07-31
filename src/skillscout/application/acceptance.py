"""Capability-separated orchestration helpers for Phase 6 acceptance.

The acceptance layer composes existing owners; it does not add a second
discovery, semantic, publication, or persistence implementation.  Every
dependency surface is deliberately frozen so callers cannot smuggle evaluator
answers or a broader live capability into an offline transition.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Final, Literal, Mapping

from skillscout.adapters.operations_state import (
    AcceptanceFactRecord,
    AcceptanceRunSnapshot,
)
from skillscout.domain.acceptance import (
    AcceptanceCampaignResumeLocatorV1,
    AcceptanceFixedCandidateAdmissionV1,
    AcceptanceScenarioResultV1,
    AcceptanceSemanticTelemetryV1,
    AcceptanceWarningV1,
    ChangedSourceDraftUpdateCompletionV1,
    ChangedSourceEvidenceV1,
    HumanSkillReviewAttestationV1,
    LiveAcceptanceAuthorityV1,
    LockedBenchmarkManifestV1,
    NominationEntryV1,
    NominationSetV1,
    ProbeCleanupAttestationV1,
    PublicationReplayCompletionV1,
    ReplayEvidenceV1,
    ReplayIntentV1,
)
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DiscoveryQuerySetV1,
    SearchPageObservationV1,
    SearchRepositoryObservationV1,
)
from skillscout.domain.filtering import ALLOWED_LICENSE_SPDX

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


@dataclass(frozen=True)
class CampaignResumeLocatorObservation:
    """One locator plus its immutable operations-owned object identity."""

    locator: AcceptanceCampaignResumeLocatorV1
    object_digest: str


@dataclass(frozen=True)
class CampaignOwnedFactObservation:
    """One typed operations-owned fact present in an immutable state child."""

    kind: str
    object_digest: str
    semantic_stage: str | None = None
    attempt_no: int | None = None
    semantic_status: str | None = None


@dataclass(frozen=True)
class CampaignStateLineageObservation:
    """One bounded commit/tree/root proof in authority-to-head order."""

    commit_sha: str
    root_digest: str
    parent_commit_sha: str | None
    prior_root_digest: str | None
    object_digests: tuple[str, ...]
    declared_content_bytes: int = 0
    resume_locators: tuple[CampaignResumeLocatorObservation, ...] = ()
    owned_facts: tuple[CampaignOwnedFactObservation, ...] = ()


@dataclass(frozen=True)
class VerifiedCampaignResume:
    """Exact descendant state selected without trusting a mutable branch tip."""

    state_commit_sha: str
    state_root_digest: str
    locator_digest: str | None
    lineage_commit_shas: tuple[str, ...]
    lineage_root_digests: tuple[str, ...]


def resolve_campaign_resume_lineage(
    *,
    authority_digest: str,
    acceptance_run_id: str,
    original_state_commit_sha: str,
    original_state_root_digest: str,
    campaign_head_commit_sha: str,
    observations: tuple[CampaignStateLineageObservation, ...],
) -> VerifiedCampaignResume:
    """Resolve an exact descendant from a completely verified root chain."""

    digest = re.compile(r"sha256:[0-9a-f]{64}")
    commit = re.compile(r"[0-9a-f]{40}")
    if (
        digest.fullmatch(authority_digest) is None
        or not acceptance_run_id
        or commit.fullmatch(original_state_commit_sha) is None
        or digest.fullmatch(original_state_root_digest) is None
        or commit.fullmatch(campaign_head_commit_sha) is None
        or not observations
        or len(observations) > 256
        or any(type(item) is not CampaignStateLineageObservation for item in observations)
    ):
        raise ValueError("campaign resume lineage rejected")
    commits = tuple(item.commit_sha for item in observations)
    roots = tuple(item.root_digest for item in observations)
    if (
        commits[0] != original_state_commit_sha
        or roots[0] != original_state_root_digest
        or commits[-1] != campaign_head_commit_sha
        or len(set(commits)) != len(commits)
        or any(commit.fullmatch(item) is None for item in commits)
        or any(digest.fullmatch(item) is None for item in roots)
    ):
        raise ValueError("campaign resume lineage rejected")
    for index, item in enumerate(observations[1:], start=1):
        expected_parent = commits[index - 1]
        expected_root = roots[index - 1]
        if item.parent_commit_sha != expected_parent or item.prior_root_digest != expected_root:
            raise ValueError("campaign resume lineage rejected")

    final_locators = observations[-1].resume_locators
    if not final_locators:
        if len(observations) != 1:
            raise ValueError("campaign resume locator missing")
        return VerifiedCampaignResume(
            state_commit_sha=original_state_commit_sha,
            state_root_digest=original_state_root_digest,
            locator_digest=None,
            lineage_commit_shas=commits,
            lineage_root_digests=roots,
        )
    ordered = tuple(sorted(final_locators, key=lambda item: item.locator.transition_index))
    if len(ordered) != len(observations) - 1:
        raise ValueError("campaign resume transition graph is incomplete")
    previous_locator_digest = None
    for index, record in enumerate(ordered, start=1):
        locator = record.locator
        parent = observations[index - 1]
        child = observations[index]
        if (
            locator.transition_index != index
            or locator.previous_locator_digest != previous_locator_digest
            or locator.acceptance_run_id != acceptance_run_id
            or locator.live_acceptance_authority_digest != authority_digest
            or locator.original_state_commit_sha != original_state_commit_sha
            or locator.original_state_root_digest != original_state_root_digest
            or locator.parent_state_commit_sha != parent.commit_sha
            or locator.parent_state_root_digest != parent.root_digest
            or record.object_digest in parent.object_digests
            or record.object_digest not in child.object_digests
            or any(
                record.object_digest not in later.object_digests for later in observations[index:]
            )
        ):
            raise ValueError("campaign resume transition edge rejected")
        _verify_campaign_transition_fact_delta(
            locator=locator,
            parent=parent,
            child=child,
        )
        previous_locator_digest = locator.locator_digest
    locator = ordered[-1].locator
    selected_index = len(observations) - 1
    return VerifiedCampaignResume(
        state_commit_sha=commits[selected_index],
        state_root_digest=roots[selected_index],
        locator_digest=locator.locator_digest,
        lineage_commit_shas=commits[: selected_index + 1],
        lineage_root_digests=roots[: selected_index + 1],
    )


def _verify_campaign_transition_fact_delta(
    *,
    locator: AcceptanceCampaignResumeLocatorV1,
    parent: CampaignStateLineageObservation,
    child: CampaignStateLineageObservation,
) -> None:
    """Require the named child to be the first durable owner of its exact facts."""

    parent_facts = {item.object_digest: item for item in parent.owned_facts}
    child_facts = {item.object_digest: item for item in child.owned_facts}
    removed = tuple(parent_facts[digest] for digest in sorted(set(parent_facts) - set(child_facts)))
    if (
        len(parent_facts) != len(parent.owned_facts)
        or len(child_facts) != len(child.owned_facts)
        or any(
            child_facts[digest] != parent_facts[digest]
            for digest in set(parent_facts) & set(child_facts)
        )
        or (
            removed
            and (
                locator.transition_phase != "result_durable"
                or len(removed) != 1
                or removed[0].kind != "semantic_attempt"
                or removed[0].semantic_stage != locator.semantic_stage
                or removed[0].attempt_no != locator.attempt_no
                or removed[0].semantic_status != "started"
            )
        )
    ):
        raise ValueError("campaign resume typed fact delta rejected")
    added = tuple(child_facts[digest] for digest in sorted(set(child_facts) - set(parent_facts)))
    required_kinds = {
        "nomination": "acceptance_nomination",
        "discovery_page": "search_page",
        "discovery_reservation": "discovery_reservation",
        "discovery_summary": "run_summary",
        "budget_reserved": "acceptance_budget_reservation",
        "candidate_admitted": "acceptance_fixed_candidate_admission",
        "semantic_candidate_reserved": "semantic_reservation",
        "request_reserved": "acceptance_semantic_request_reservation",
        "started": "semantic_attempt",
        "result_durable": "semantic_attempt",
        "scenario": "acceptance_scenario",
        "replay_intent": "acceptance_replay",
        "replay_evidence": "acceptance_replay_evidence",
    }.get(locator.transition_phase)
    if locator.transition_phase == "terminal":
        kinds = tuple(item.kind for item in added)
        accepted = kinds.count("candidate_terminal") == 1 and all(
            kind in {"candidate_terminal", "workflow_terminal"} for kind in kinds
        )
    elif locator.transition_phase == "discovery_page":
        kinds = tuple(item.kind for item in added)
        accepted = kinds.count("search_page") == 1 and all(
            kind in {"search_page", "candidate"} for kind in kinds
        )
    elif locator.transition_phase in {
        "budget_reserved",
        "candidate_admitted",
    }:
        kinds = tuple(item.kind for item in added)
        required_kind = (
            "acceptance_budget_reservation"
            if locator.transition_phase == "budget_reserved"
            else "acceptance_fixed_candidate_admission"
        )
        accepted = (
            kinds.count(required_kind) == 1
            and kinds.count("run") <= 1
            and all(kind in {required_kind, "run"} for kind in kinds)
        )
    else:
        accepted = (
            required_kinds is not None and len(added) == 1 and added[0].kind == required_kinds
        )
    if not accepted:
        raise ValueError("campaign resume typed fact delta rejected")
    if locator.transition_phase in {"started", "result_durable"}:
        fact = added[0]
        if (
            fact.semantic_stage != locator.semantic_stage
            or fact.attempt_no != locator.attempt_no
            or fact.semantic_status != locator.semantic_status
        ):
            raise ValueError("campaign resume typed fact delta rejected")


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
    state_restore: Callable[[], object]
    durability_barrier: object


@dataclass(frozen=True)
class NominationApplicationResult:
    """One persisted nomination and its independently verified state CAS."""

    nomination: NominationSetV1
    state_commit_sha: str
    state_root_digest: str


class NominationApplication:
    """Search-only nomination orchestration with no semantic capability."""

    def __init__(
        self,
        dependencies: NominationDependencies,
        *,
        query_set: DiscoveryQuerySetV1,
        initial_state_root_digest: str,
    ) -> None:
        if (
            type(dependencies) is not NominationDependencies
            or type(query_set) is not DiscoveryQuerySetV1
            or re.fullmatch(r"sha256:[0-9a-f]{64}", initial_state_root_digest) is None
        ):
            raise TypeError("invalid nomination application")
        self._dependencies = dependencies
        self._query_set = query_set
        self._initial_state_root_digest = initial_state_root_digest

    def run(
        self,
        *,
        search_run_authority_digest: str,
        nomination_set_id: str,
        created_at: str,
    ) -> NominationApplicationResult:
        restored = self._dependencies.state_restore()
        observed_head = getattr(restored, "observed_head", None)
        prior_root = getattr(
            getattr(getattr(restored, "bundle", None), "root", None),
            "root_digest",
            None,
        )
        if (
            getattr(restored, "status", None) != "verified"
            or type(observed_head) is not str
            or re.fullmatch(r"[0-9a-f]{40}", observed_head) is None
            or prior_root != self._initial_state_root_digest
        ):
            raise AcceptanceApplicationError("evidence_missing")
        search = self._dependencies.search_factory()
        store = None
        try:
            nomination = nominate_search_candidates(
                search=search,
                query_set=self._query_set,
                search_run_authority_digest=search_run_authority_digest,
                nomination_set_id=nomination_set_id,
                created_at=created_at,
            )
            store = self._dependencies.operations_store_factory()
            _record_on_open_store(
                store,
                nomination.nomination_set_id,
                "acceptance_nomination",
                nomination,
            )
            sync = getattr(
                self._dependencies.durability_barrier,
                "sync_nomination",
                None,
            )
            if not callable(sync):
                raise AcceptanceApplicationError("evidence_missing")
            synchronized = sync(
                operations_store=store,
                observed_head=observed_head,
                prior_root_digest=prior_root,
                created_at=created_at,
            )
            state_commit_sha = getattr(synchronized, "commit_sha", None)
            state_root_digest = getattr(synchronized, "root_digest", None)
            if (
                getattr(synchronized, "status", None) != "verified"
                or getattr(synchronized, "previous_head", None) != observed_head
                or type(state_commit_sha) is not str
                or re.fullmatch(r"[0-9a-f]{40}", state_commit_sha) is None
                or type(state_root_digest) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", state_root_digest) is None
            ):
                raise AcceptanceApplicationError("evidence_missing")
            return NominationApplicationResult(
                nomination=nomination,
                state_commit_sha=state_commit_sha,
                state_root_digest=state_root_digest,
            )
        finally:
            _close(store)
            _close(search)


@dataclass(frozen=True)
class LockedCampaignDependencies:
    """Late production capabilities admitted only after manifest revalidation."""

    discovery_factory: Callable[[str, str], object]
    operations_store_factory: Callable[[], object]
    state_sync: Callable[..., object]
    candidate_factory: Callable[[], object] | None = None
    publication_factory: Callable[[], object] | None = None


@dataclass(frozen=True)
class ReplayUpdateDependencies:
    """Completed-first replay composition with exact state persistence."""

    completed_projector_factory: Callable[[], object]
    operations_store_factory: Callable[[], object]
    state_sync: Callable[..., object]
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
class LiveAuthorityDependencies:
    """Operations-owned recorder for one immutable human live authority."""

    operations_store_factory: Callable[[], object]


@dataclass(frozen=True)
class AcceptanceRebuildDependencies:
    """Offline state owner used to reconstruct acceptance evidence."""

    operations_store_factory: Callable[[], object]


@dataclass(frozen=True)
class OfflineEvaluationDependencies:
    """Offline evaluators can read verified state but own no live adapter."""

    operations_store_factory: Callable[[], object]


@dataclass(frozen=True)
class LiveRepositoryAuthority:
    """Role-free immutable identity passed into the untrusted-content runner."""

    repository_full_name: str
    repository_id: int
    exact_commit_sha: str
    license_spdx: str
    nomination_entry_digest: str
    entry_digest: str
    selection_evidence_digests: tuple[str, ...]


@dataclass(frozen=True)
class FixedAcceptanceCandidate:
    """Acceptance-only fixed identity exposing no fictitious Search provenance."""

    repository: SearchRepositoryObservationV1
    admission: AcceptanceFixedCandidateAdmissionV1

    def __post_init__(self) -> None:
        if (
            type(self.repository) is not SearchRepositoryObservationV1
            or type(self.admission) is not AcceptanceFixedCandidateAdmissionV1
            or self.repository.repository_id != self.admission.repository_id
            or self.repository.full_name != self.admission.repository_full_name
        ):
            raise ValueError("fixed acceptance candidate identity mismatch")

    @property
    def candidate_digest(self) -> str:
        return self.admission.admission_digest or ""


@dataclass(frozen=True)
class LiveScenarioObservation:
    """Sanitized production observation returned by one bounded repository run."""

    repository_id: int
    repository_full_name: str
    exact_commit_sha: str
    license_spdx: str
    outcome: str
    reason_code: str
    evidence_digests: tuple[str, ...]
    live_acceptance_authority_digest: str
    discovery_run_id: str
    discovery_run_authority_digest: str
    benchmark_entry_digest: str
    budget_reservation_digest: str
    fixed_candidate_admission_digest: str
    semantic_candidate_reservation_digest: str | None
    semantic_request_reservation_digests: tuple[str, ...]
    candidate_terminal_digest: str
    workflow_terminal_digests: tuple[str, ...]
    workflow_execution_authority_digests: tuple[str, ...]
    workflow_spec_authority_digests: tuple[str, ...]
    phase3_terminal_summary_digests: tuple[str, ...]
    skill_artifact_digests: tuple[str, ...]
    package_digests: tuple[str, ...]
    eligible_object_digest: str | None
    workflow_fingerprint: str | None
    workflow_spec_authority_digest: str | None
    eligible_locator: str | None
    semantic_request_count: int
    candidate_funnel: tuple[str, ...] = (
        "fixed_identity",
        "deterministic_filter",
        "bounded_read",
        "semantic_terminal",
    )
    reader_file_count: int = 0
    reader_source_file_count: int = 0
    reader_total_bytes: int = 0
    reader_estimated_tokens: int = 0
    semantic_attempt_digests: tuple[str, ...] = ()
    semantic_telemetry: tuple[AcceptanceSemanticTelemetryV1, ...] = ()
    actual_models: tuple[str, ...] = ()
    state_commit_sha: str | None = None
    state_root_digest: str | None = None


@dataclass(frozen=True)
class LockedBenchmarkResult:
    """Five terminal facts plus the exact state CAS resulting from persistence."""

    scenario_results: tuple[AcceptanceScenarioResultV1, ...]
    state_commit_sha: str
    state_root_digest: str


@dataclass(frozen=True)
class CompletedBenchmarkProjection:
    """Read-only completed projection used before replay opens mutable state."""

    manifest_digest: str
    scenario_result_digests: tuple[str, ...]
    repository_id: int
    source_commit_sha: str
    workflow_fingerprint: str
    workflow_spec_authority_digest: str
    eligible_locators: tuple[str, ...]
    semantic_attempt_count: int
    semantic_attempt_digests: tuple[str, ...]
    workflow_spec_authority_digests: tuple[str, ...]
    skill_identity_digests: tuple[str, ...]
    candidate_fact_digests: tuple[str, ...]
    acceptance_business_fact_digests: tuple[str, ...]
    operations_fact_digests: tuple[str, ...]
    semantic_request_count: int

    def __post_init__(self) -> None:
        digest_sets = (
            self.scenario_result_digests,
            self.semantic_attempt_digests,
            self.workflow_spec_authority_digests,
            self.skill_identity_digests,
            self.candidate_fact_digests,
            self.acceptance_business_fact_digests,
            self.operations_fact_digests,
        )
        if (
            len(self.scenario_result_digests) != 5
            or any(
                values != tuple(sorted(values))
                or len(values) != len(set(values))
                or any(re.fullmatch(r"sha256:[0-9a-f]{64}", item) is None for item in values)
                for values in digest_sets
            )
            or self.eligible_locators != tuple(sorted(self.eligible_locators))
            or len(self.eligible_locators) != len(set(self.eligible_locators))
            or self.semantic_attempt_count != len(self.semantic_attempt_digests)
            or self.semantic_request_count != self.semantic_attempt_count
        ):
            raise ValueError("completed benchmark projection is not exact")

    @property
    def object_digests(self) -> tuple[str, ...]:
        """All content-addressed benchmark objects, excluding replay facts."""

        return tuple(
            sorted(
                {
                    *self.scenario_result_digests,
                    *self.semantic_attempt_digests,
                    *self.workflow_spec_authority_digests,
                    *self.skill_identity_digests,
                    *self.candidate_fact_digests,
                    *self.acceptance_business_fact_digests,
                    *self.operations_fact_digests,
                }
            )
        )

    @property
    def projection_digest(self) -> str:
        """Canonical digest of the complete read-only benchmark projection."""

        return sha256_digest(asdict(self))


def _candidate_funnel_for_observation(
    outcome: str,
    telemetry: tuple[AcceptanceSemanticTelemetryV1, ...],
) -> tuple[str, ...]:
    """Derive the exact reached stage boundary from terminal facts."""

    business_funnels = {
        "filter_rejected": ("fixed_identity", "deterministic_filter"),
        "no_workflow": (
            "fixed_identity",
            "deterministic_filter",
            "bounded_read",
            "extractor",
        ),
        "qualification_rejected": (
            "fixed_identity",
            "deterministic_filter",
            "bounded_read",
            "extractor",
            "qualification",
        ),
        "validation_rejected": (
            "fixed_identity",
            "deterministic_filter",
            "bounded_read",
            "extractor",
            "qualification",
            "generator",
            "validation",
        ),
        "review_rejected": (
            "fixed_identity",
            "deterministic_filter",
            "bounded_read",
            "extractor",
            "qualification",
            "generator",
            "validation",
            "reviewer",
        ),
        "eligible_local_candidate": (
            "fixed_identity",
            "deterministic_filter",
            "bounded_read",
            "extractor",
            "qualification",
            "generator",
            "validation",
            "reviewer",
        ),
    }
    exact = business_funnels.get(outcome)
    if exact is not None:
        return exact
    reached = {item.stage for item in telemetry}
    funnel = ["fixed_identity", "deterministic_filter", "bounded_read"]
    if reached:
        funnel.append("extractor")
    if "generator" in reached or "reviewer" in reached:
        funnel.extend(("qualification", "generator"))
    if "reviewer" in reached:
        funnel.extend(("validation", "reviewer"))
    return tuple(funnel)


def load_locked_benchmark_manifest(path: Path) -> LockedBenchmarkManifestV1:
    """Strictly load the sole canonical checked-in manifest path."""

    if (
        not isinstance(path, Path)
        or path.name != "06-BENCHMARK-MANIFEST.json"
        or path.parent.name != "06-adversarial-mvp-acceptance"
    ):
        raise AcceptanceApplicationError("evidence_missing")
    try:
        payload = path.read_bytes()
        manifest = LockedBenchmarkManifestV1.model_validate_json(payload, strict=True)
        from skillscout.domain.canonical import canonical_json_bytes

        canonical = canonical_json_bytes(manifest)
        if payload not in {canonical, canonical + b"\n"}:
            raise ValueError
    except Exception:
        raise AcceptanceApplicationError("evidence_missing") from None
    return manifest


def run_locked_benchmark(
    dependencies: LockedCampaignDependencies,
    *,
    manifest: LockedBenchmarkManifestV1,
    acceptance_run_id: str,
    observed_head: str,
    prior_root_digest: str,
    recorded_at: str,
) -> LockedBenchmarkResult:
    """Run the exact locked five-entry campaign and persist every terminal by CAS."""

    if type(dependencies) is not LockedCampaignDependencies:
        raise TypeError("invalid locked campaign dependencies")
    store = dependencies.operations_store_factory()
    runner: object | None = None
    results: list[AcceptanceScenarioResultV1] = []
    current_head = observed_head
    current_root = prior_root_digest
    semantic_requests = 0
    try:
        snapshot = _snapshot(store, acceptance_run_id)
        locks = tuple(
            record.fact
            for record in snapshot.facts
            if record.kind == "acceptance_benchmark_lock"
            and record.fact_digest == manifest.manifest_digest
        )
        if len(locks) != 1 or locks[0] != manifest or len(manifest.entries) != 5:
            raise AcceptanceApplicationError("evidence_missing")
        live_authorities = tuple(
            record.fact
            for record in snapshot.facts
            if record.kind == "acceptance_live_authority"
            and isinstance(record.fact, LiveAcceptanceAuthorityV1)
            and record.fact.manifest_digest == manifest.manifest_digest
        )
        if len(live_authorities) != 1:
            raise AcceptanceApplicationError("evidence_missing")
        live_authority = live_authorities[0]
        existing_scenarios = {
            scenario.benchmark_entry_digest: scenario
            for scenario in (
                record.fact
                for record in snapshot.facts
                if record.kind == "acceptance_scenario"
                and isinstance(record.fact, AcceptanceScenarioResultV1)
            )
        }
        if len(existing_scenarios) != len(
            tuple(record for record in snapshot.facts if record.kind == "acceptance_scenario")
        ) or not set(existing_scenarios).issubset(
            {entry.entry_digest for entry in manifest.entries}
        ):
            raise AcceptanceApplicationError("evidence_missing")
        semantic_requests = sum(
            scenario.semantic_request_count for scenario in existing_scenarios.values()
        )
        if semantic_requests > 20:
            raise AcceptanceApplicationError("unauthorized_effect")
        _close(store)
        store = None
        for ordinal, entry in enumerate(manifest.entries, start=1):
            existing = existing_scenarios.get(entry.entry_digest)
            if existing is not None:
                if existing.scenario_id != f"locked-{ordinal}-{entry.repository_id}":
                    raise AcceptanceApplicationError("evidence_missing")
                results.append(existing)
                if existing.terminal_class == "system_failure":
                    raise AcceptanceApplicationError(existing.outcome)
                continue
            runner = dependencies.discovery_factory(current_head, current_root)
            run = getattr(runner, "run", None)
            if not callable(run):
                raise AcceptanceApplicationError("evidence_missing")
            authority = LiveRepositoryAuthority(
                repository_full_name=entry.repository_full_name,
                repository_id=entry.repository_id,
                exact_commit_sha=entry.exact_commit_sha,
                license_spdx=entry.license_spdx,
                nomination_entry_digest=entry.nomination_entry_digest,
                entry_digest=entry.entry_digest,
                selection_evidence_digests=entry.selection_evidence_digests,
            )
            try:
                observation = run(authority)
            except Exception:
                raise AcceptanceApplicationError("harness_failed") from None
            finally:
                _close(runner)
                runner = None
            if (
                type(observation) is not LiveScenarioObservation
                or (
                    observation.repository_full_name,
                    observation.repository_id,
                    observation.exact_commit_sha,
                    observation.license_spdx,
                )
                != (
                    authority.repository_full_name,
                    authority.repository_id,
                    authority.exact_commit_sha,
                    authority.license_spdx,
                )
                or observation.semantic_request_count != len(observation.semantic_attempt_digests)
                or observation.live_acceptance_authority_digest != live_authority.authority_digest
            ):
                raise AcceptanceApplicationError("evidence_missing")
            semantic_requests += observation.semantic_request_count
            if semantic_requests > 20:
                raise AcceptanceApplicationError("unauthorized_effect")
            if observation.state_commit_sha is not None:
                if (
                    re.fullmatch(r"[0-9a-f]{40}", observation.state_commit_sha) is None
                    or re.fullmatch(
                        r"sha256:[0-9a-f]{64}",
                        observation.state_root_digest or "",
                    )
                    is None
                ):
                    raise AcceptanceApplicationError("evidence_missing")
                current_head = observation.state_commit_sha
                current_root = observation.state_root_digest or ""

            terminal_class = classify_acceptance_terminal(observation.outcome)
            evaluator_match = (
                terminal_class == "eligible"
                if entry.coverage_role in {"positive", "positive_multi_workflow"}
                else terminal_class == "business_terminal"
            )
            result = AcceptanceScenarioResultV1(
                schema_version="acceptance-scenario-result-v1",
                acceptance_run_id=acceptance_run_id,
                scenario_id=f"locked-{ordinal}-{entry.repository_id}",
                repository_id=entry.repository_id,
                repository_full_name=entry.repository_full_name,
                exact_commit_sha=entry.exact_commit_sha,
                license_spdx=entry.license_spdx,
                benchmark_manifest_digest=manifest.manifest_digest,
                benchmark_entry_digest=observation.benchmark_entry_digest,
                live_acceptance_authority_digest=(observation.live_acceptance_authority_digest),
                discovery_run_id=observation.discovery_run_id,
                discovery_run_authority_digest=(observation.discovery_run_authority_digest),
                budget_reservation_digest=(observation.budget_reservation_digest),
                fixed_candidate_admission_digest=(observation.fixed_candidate_admission_digest),
                semantic_candidate_reservation_digest=(
                    observation.semantic_candidate_reservation_digest
                ),
                terminal_class=terminal_class,
                outcome=observation.outcome,
                reason_code=observation.reason_code,
                evidence_digests=tuple(sorted(set(observation.evidence_digests))),
                candidate_funnel=_candidate_funnel_for_observation(
                    observation.outcome,
                    observation.semantic_telemetry,
                ),
                reader_order="readme_docs_examples_manifests_source",
                reader_file_count=observation.reader_file_count,
                reader_source_file_count=observation.reader_source_file_count,
                reader_total_bytes=observation.reader_total_bytes,
                reader_estimated_tokens=observation.reader_estimated_tokens,
                semantic_request_count=observation.semantic_request_count,
                semantic_request_reservation_digests=tuple(
                    sorted(observation.semantic_request_reservation_digests)
                ),
                semantic_attempt_digests=tuple(sorted(observation.semantic_attempt_digests)),
                semantic_telemetry=observation.semantic_telemetry,
                actual_models=observation.actual_models,
                prompt_versions=tuple(
                    item.prompt_version for item in observation.semantic_telemetry
                ),
                schema_versions=tuple(
                    item.output_schema_version for item in observation.semantic_telemetry
                ),
                policy_versions=tuple(
                    item.policy_version for item in observation.semantic_telemetry
                ),
                workflow_fingerprint=observation.workflow_fingerprint,
                workflow_spec_authority_digest=(observation.workflow_spec_authority_digest),
                workflow_execution_authority_digests=tuple(
                    sorted(observation.workflow_execution_authority_digests)
                ),
                workflow_spec_authority_digests=tuple(
                    sorted(observation.workflow_spec_authority_digests)
                ),
                candidate_terminal_digest=observation.candidate_terminal_digest,
                workflow_terminal_digests=tuple(sorted(observation.workflow_terminal_digests)),
                phase3_terminal_summary_digests=tuple(
                    sorted(observation.phase3_terminal_summary_digests)
                ),
                skill_artifact_digests=tuple(sorted(observation.skill_artifact_digests)),
                package_digests=tuple(sorted(observation.package_digests)),
                eligible_locator=observation.eligible_locator,
                eligible_object_digest=observation.eligible_object_digest,
                expected_coverage_role=entry.coverage_role,
                evaluator_matches_observed=evaluator_match,
                publication_decision=(
                    "eligible_for_later_publication"
                    if terminal_class == "eligible"
                    else "not_eligible"
                ),
                warnings=(
                    AcceptanceWarningV1(
                        warning_code="openai_live_absent",
                        impact=(
                            "This locked campaign exercises the approved DeepSeek "
                            "provider path and does not provide live OpenAI evidence."
                        ),
                        follow_up=(
                            "Run a separately approved OpenAI acceptance campaign "
                            "before claiming cross-provider production authority."
                        ),
                        security_relevant=False,
                    ),
                ),
                recorded_at=recorded_at,
            )
            store = dependencies.operations_store_factory()
            _record_on_open_store(
                store,
                acceptance_run_id,
                "acceptance_scenario",
                result,
            )
            synchronized = dependencies.state_sync(
                operations_store=store,
                observed_head=current_head,
                prior_root_digest=current_root,
                created_at=recorded_at,
                transition_phase="scenario",
            )
            next_head = getattr(synchronized, "commit_sha", None)
            next_root = getattr(synchronized, "root_digest", None)
            if (
                getattr(synchronized, "status", None) != "verified"
                or getattr(synchronized, "previous_head", None) != current_head
                or type(next_head) is not str
                or re.fullmatch(r"[0-9a-f]{40}", next_head) is None
                or type(next_root) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", next_root) is None
            ):
                raise AcceptanceApplicationError("evidence_missing")
            current_head, current_root = next_head, next_root
            _close(store)
            store = None
            results.append(result)
            if terminal_class == "system_failure":
                raise AcceptanceApplicationError(observation.outcome)
        return LockedBenchmarkResult(
            scenario_results=tuple(results),
            state_commit_sha=current_head,
            state_root_digest=current_root,
        )
    finally:
        _close(runner)
        _close(store)


def run_exact_replay(
    dependencies: ReplayUpdateDependencies,
    *,
    manifest: LockedBenchmarkManifestV1,
    acceptance_run_id: str,
    state_commit_sha: str,
    state_root_digest: str,
    recorded_at: str,
) -> ReplayEvidenceV1:
    """Persist one replay fact, then measure the same campaign projection again."""

    if type(dependencies) is not ReplayUpdateDependencies:
        raise TypeError("invalid replay dependencies")
    projector = dependencies.completed_projector_factory()
    try:
        project = getattr(projector, "project", None)
        if not callable(project):
            raise AcceptanceApplicationError("evidence_missing")
        projection = project(
            manifest=manifest,
            state_commit_sha=state_commit_sha,
            state_root_digest=state_root_digest,
        )
    finally:
        _close(projector)
    if (
        type(projection) is not CompletedBenchmarkProjection
        or projection.manifest_digest != manifest.manifest_digest
        or len(projection.scenario_result_digests) != 5
        or len(set(projection.scenario_result_digests)) != 5
    ):
        raise AcceptanceApplicationError("evidence_missing")
    replay_intent = ReplayIntentV1(
        schema_version="replay-intent-v1",
        acceptance_run_id=acceptance_run_id,
        repository_id=projection.repository_id,
        source_commit_sha=projection.source_commit_sha,
        workflow_fingerprint=projection.workflow_fingerprint,
        workflow_spec_authority_digest=projection.workflow_spec_authority_digest,
        replay_policy_version="acceptance-replay-policy-v1",
        benchmark_manifest_digest=manifest.manifest_digest,
        before_state_commit_sha=state_commit_sha,
        before_state_root_digest=state_root_digest,
        before_projection_digest=projection.projection_digest,
        before_object_digests=projection.object_digests,
        semantic_request_count=0,
        remote_effect_count=0,
        recorded_at=recorded_at,
    )
    store = dependencies.operations_store_factory()
    try:
        _record_on_open_store(
            store,
            acceptance_run_id,
            "acceptance_replay",
            replay_intent,
        )
        synchronized = dependencies.state_sync(
            operations_store=store,
            observed_head=state_commit_sha,
            prior_root_digest=state_root_digest,
            created_at=recorded_at,
            transition_phase="replay_intent",
        )
        next_head = getattr(synchronized, "commit_sha", None)
        next_root = getattr(synchronized, "root_digest", None)
        if (
            getattr(synchronized, "status", None) != "verified"
            or getattr(synchronized, "previous_head", None) != state_commit_sha
            or type(next_head) is not str
            or re.fullmatch(r"[0-9a-f]{40}", next_head) is None
            or type(next_root) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", next_root) is None
        ):
            raise AcceptanceApplicationError("evidence_missing")
    finally:
        _close(store)

    after_projector = dependencies.completed_projector_factory()
    try:
        after_project = getattr(after_projector, "project", None)
        if not callable(after_project):
            raise AcceptanceApplicationError("evidence_missing")
        after_projection = after_project(
            manifest=manifest,
            state_commit_sha=next_head,
            state_root_digest=next_root,
        )
    finally:
        _close(after_projector)
    if type(after_projection) is not CompletedBenchmarkProjection or after_projection != projection:
        raise AcceptanceApplicationError("duplicate_effect")
    replay = ReplayEvidenceV1(
        schema_version="replay-evidence-v1",
        acceptance_run_id=acceptance_run_id,
        repository_id=projection.repository_id,
        source_commit_sha=projection.source_commit_sha,
        workflow_fingerprint=projection.workflow_fingerprint,
        workflow_spec_authority_digest=projection.workflow_spec_authority_digest,
        replay_policy_version="acceptance-replay-policy-v1",
        replay_fact_digest=replay_intent.replay_digest,
        allowed_delta_fact_digests=(replay_intent.replay_digest,),
        benchmark_manifest_digest=manifest.manifest_digest,
        before_state_commit_sha=state_commit_sha,
        before_state_root_digest=state_root_digest,
        after_state_commit_sha=next_head,
        after_state_root_digest=next_root,
        before_projection_digest=projection.projection_digest,
        after_projection_digest=after_projection.projection_digest,
        before_object_digests=projection.object_digests,
        after_object_digests=after_projection.object_digests,
        scenario_result_digests=tuple(sorted(projection.scenario_result_digests)),
        eligible_locators=tuple(sorted(projection.eligible_locators)),
        semantic_attempt_count_before=projection.semantic_attempt_count,
        semantic_attempt_count_after=after_projection.semantic_attempt_count,
        semantic_request_count=0,
        duplicate_workflow_spec_count=0,
        duplicate_skill_count=0,
        duplicate_fact_count=0,
        remote_effect_count=0,
        recorded_at=recorded_at,
    )
    evidence_store = dependencies.operations_store_factory()
    try:
        _record_on_open_store(
            evidence_store,
            acceptance_run_id,
            "acceptance_replay_evidence",
            replay,
        )
        evidence_sync = dependencies.state_sync(
            operations_store=evidence_store,
            observed_head=next_head,
            prior_root_digest=next_root,
            created_at=recorded_at,
            transition_phase="replay_evidence",
        )
        final_head = getattr(evidence_sync, "commit_sha", None)
        final_root = getattr(evidence_sync, "root_digest", None)
        if (
            getattr(evidence_sync, "status", None) != "verified"
            or getattr(evidence_sync, "previous_head", None) != next_head
            or type(final_head) is not str
            or re.fullmatch(r"[0-9a-f]{40}", final_head) is None
            or type(final_root) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", final_root) is None
        ):
            raise AcceptanceApplicationError("evidence_missing")
    finally:
        _close(evidence_store)

    final_projector = dependencies.completed_projector_factory()
    try:
        final_project = getattr(final_projector, "project", None)
        if not callable(final_project):
            raise AcceptanceApplicationError("evidence_missing")
        final_projection = final_project(
            manifest=manifest,
            state_commit_sha=final_head,
            state_root_digest=final_root,
        )
    finally:
        _close(final_projector)
    if type(final_projection) is not CompletedBenchmarkProjection or final_projection != projection:
        raise AcceptanceApplicationError("duplicate_effect")
    return replay


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
    nominated_by_digest: dict[str | None, NominationEntryV1] = {
        entry.entry_digest: entry
        for entry in (nomination.search_derived_entries + nomination.user_nominated_entries)
    }
    if len(manifest.entries) != 5:
        raise AcceptanceApplicationError("evidence_missing")
    for entry in manifest.entries:
        nominated = nominated_by_digest.get(entry.nomination_entry_digest)
        if nominated is None or (
            entry.repository_full_name,
            entry.repository_id,
            entry.exact_commit_sha,
            entry.license_spdx,
            entry.selection_source,
            entry.selection_evidence_digests,
        ) != (
            nominated.repository_full_name,
            nominated.repository_id,
            nominated.exact_commit_sha,
            nominated.license_spdx,
            nominated.selection_source,
            nominated.selection_evidence_digests,
        ):
            raise AcceptanceApplicationError("evidence_missing")
    return nomination


def nominate_search_candidates(
    *,
    search: object,
    query_set: DiscoveryQuerySetV1,
    search_run_authority_digest: str,
    nomination_set_id: str,
    created_at: str,
) -> NominationSetV1:
    """Acquire, filter, and pin at most 100 public Search candidates."""

    required = (
        "search_repositories",
        "get_repo_metadata",
        "resolve_commit",
        "get_license",
    )
    if type(query_set) is not DiscoveryQuerySetV1 or not all(
        callable(getattr(search, name, None)) for name in required
    ):
        raise AcceptanceApplicationError("evidence_missing")
    seen: set[int] = set()
    entries: list[NominationEntryV1] = []
    active_pages = {ordinal: 1 for ordinal in range(1, len(query_set.queries) + 1)}
    while active_pages and len(seen) < DISCOVERY_MAX_CANDIDATES:
        for query_ordinal in tuple(sorted(active_pages)):
            page_number = active_pages[query_ordinal]
            page, repositories = search.search_repositories(
                query_set=query_set,
                discovery_run_authority_digest=search_run_authority_digest,
                query_ordinal=query_ordinal,
                page=page_number,
            )
            if type(page) is not SearchPageObservationV1 or type(repositories) is not tuple:
                raise AcceptanceApplicationError("evidence_missing")
            for repository in repositories:
                if (
                    type(repository) is not SearchRepositoryObservationV1
                    or repository.repository_id in seen
                ):
                    continue
                seen.add(repository.repository_id)
                if len(seen) > DISCOVERY_MAX_CANDIDATES:
                    break
                if (
                    repository.private
                    or repository.visibility != "public"
                    or repository.fork
                    or repository.archived
                    or repository.disabled
                    or repository.default_branch is None
                ):
                    continue
                metadata = search.get_repo_metadata(repository.owner, repository.name)
                if (
                    getattr(metadata, "id", None) != repository.repository_id
                    or getattr(metadata, "owner", None) != repository.owner
                    or getattr(metadata, "name", None) != repository.name
                    or getattr(metadata, "private", None)
                    or getattr(metadata, "visibility", None) != "public"
                    or getattr(metadata, "fork", None)
                    or getattr(metadata, "archived", None)
                    or getattr(metadata, "disabled", None)
                    or getattr(metadata, "default_branch", None) != repository.default_branch
                    or getattr(metadata, "license_spdx", None) not in ALLOWED_LICENSE_SPDX
                ):
                    continue
                commit_sha = search.resolve_commit(
                    repository.owner,
                    repository.name,
                    repository.default_branch,
                )
                license_facts = search.get_license(
                    repository.owner,
                    repository.name,
                    commit_sha,
                )
                if (
                    type(commit_sha) is not str
                    or re.fullmatch(r"[0-9a-f]{40}", commit_sha) is None
                    or getattr(license_facts, "status", None) != "confirmed"
                    or getattr(license_facts, "spdx_id", None) != metadata.license_spdx
                    or getattr(license_facts, "license_blob_sha", None) is None
                ):
                    continue
                evidence = tuple(
                    sorted(
                        {
                            page.observation_digest,
                            repository.observation_digest,
                            sha256_digest(metadata.model_dump(mode="json", exclude_none=False)),
                            sha256_digest(
                                {
                                    "repository_id": repository.repository_id,
                                    "default_branch": repository.default_branch,
                                    "exact_commit_sha": commit_sha,
                                }
                            ),
                            sha256_digest(
                                {
                                    "repository_id": repository.repository_id,
                                    "exact_commit_sha": commit_sha,
                                    "status": license_facts.status,
                                    "spdx_id": license_facts.spdx_id,
                                    "license_blob_sha": (license_facts.license_blob_sha),
                                }
                            ),
                        }
                    )
                )
                entries.append(
                    NominationEntryV1(
                        schema_version="nomination-entry-v1",
                        repository_full_name=repository.full_name,
                        repository_id=repository.repository_id,
                        exact_commit_sha=commit_sha,
                        license_spdx=metadata.license_spdx,
                        selection_source="search_derived",
                        selection_evidence_digests=evidence,
                    )
                )
            active_pages.pop(query_ordinal, None)
            if page.next_page is not None and len(seen) < DISCOVERY_MAX_CANDIDATES:
                active_pages[query_ordinal] = page.next_page
    if len(entries) < 5:
        raise AcceptanceApplicationError("evidence_missing")
    return NominationSetV1.model_validate(
        {
            "schema_version": "nomination-set-v1",
            "nomination_set_id": nomination_set_id,
            "query_set_digest": query_set.query_set_digest,
            "search_run_authority_digest": search_run_authority_digest,
            "search_derived_entries": tuple(
                entry.model_dump(mode="python", exclude_none=False)
                for entry in sorted(entries, key=lambda entry: entry.entry_digest or "")
            ),
            "user_nominated_entries": (),
            "created_at": created_at,
        },
        strict=True,
    )


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


def record_live_authority(
    dependencies: LiveAuthorityDependencies,
    *,
    acceptance_run_id: str,
    fact: LiveAcceptanceAuthorityV1,
) -> AcceptanceFactRecord:
    """Persist the single authority that can unlock one live benchmark run.

    The durable-state boundary is deliberately outside this operation.  It is
    responsible for the subsequent compare-and-swap write and for returning
    the immutable state commit that later benchmark/replay jobs verify.
    """

    if (
        type(dependencies) is not LiveAuthorityDependencies
        or type(acceptance_run_id) is not str
        or not acceptance_run_id
        or type(fact) is not LiveAcceptanceAuthorityV1
        or fact.authority_digest is None
    ):
        raise TypeError("invalid live authority recorder")
    store = dependencies.operations_store_factory()
    try:
        snapshot = _snapshot(store, acceptance_run_id)
        existing = tuple(
            record for record in snapshot.facts if record.kind == "acceptance_live_authority"
        )
        if len(existing) > 1 or (
            len(existing) == 1 and existing[0].fact_digest != fact.authority_digest
        ):
            raise AcceptanceApplicationError("unauthorized_effect")
        return _record_on_open_store(
            store,
            acceptance_run_id,
            "acceptance_live_authority",
            fact,
        )
    finally:
        _close(store)


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
