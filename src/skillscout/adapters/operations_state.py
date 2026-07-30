"""Descriptor-anchored durable ledger for Phase 5 discovery operations."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Callable, Final, Literal, Mapping, TypeAlias, TypeVar

from pydantic import Field, model_validator

from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.adapters.publication_state import (
    PublicationOwnedFactV1,
    PublicationOwnedStateV1,
    PublicationStateProjectionV1,
    PublicationStateStore,
)
from skillscout.adapters.state import (
    PipelineOwnedFactV1,
    PipelineOwnedStateV1,
    PipelineStateProjectionV1,
    SQLiteStateStore,
)
from skillscout.adapters.state_branch import (
    StateOwnedFile,
    VerifiedStateBundle,
    _validate_bundle,
)
from skillscout.domain.acceptance import (
    AcceptanceBudgetReservationV1,
    AcceptanceCampaignResumeLocatorV1,
    AcceptanceFixedCandidateAdmissionV1,
    AcceptanceSemanticRequestReservationV1,
    AcceptanceEvidenceRootV1,
    AcceptanceGateResultV1,
    AcceptanceScenarioResultV1,
    ChangedSourceDraftUpdateCompletionV1,
    ChangedSourceEvidenceV1,
    GateB4BindingV1,
    HostedIsolationCapabilityV1,
    HumanSkillReviewAttestationV1,
    LiveAcceptanceAuthorityV1,
    LockedBenchmarkManifestV1,
    NominationSetV1,
    OfflineAdversarialRunV1,
    ProbeCleanupAttestationV1,
    PublicationReplayCompletionV1,
    ReplayIntentV1,
    ReplayEvidenceV1,
    ReviewerCalibrationV1,
)
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
    DiscoveredCandidateV1,
    DiscoveryBudgetPolicyV1,
    DiscoveryCandidateTerminalV1,
    DiscoveryReservationV1,
    DiscoveryRunAuthorityV1,
    DiscoveryRunSummaryV1,
    SearchPageObservationV1,
    SemanticReservationV1,
    DiscoveryStateRebuildProjectionV1,
    DiscoveryStateDatabaseV1,
    DiscoveryStateObjectV1,
    DiscoveryStateRootV1,
)
from skillscout.domain.models import Digest, StrictFrozenModel


OPERATIONS_SCHEMA_VERSION: Final = 1
MAX_OPERATIONS_DB_BYTES: Final = 67_108_864
_DIGEST_PATTERN: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_STATE_OBJECT_LOCATOR: Final = re.compile(r"^state/objects/sha256/[0-9a-f]{2}/[0-9a-f]{64}\.json$")
_TIMESTAMP_PATTERN: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_TEST_RUN_SCHEMA: Final = "operations-test-run-v1"
_TEST_RESERVATION_SCHEMA: Final = "operations-test-reservation-v1"
_TEST_TERMINAL_SCHEMA: Final = "operations-test-terminal-v1"
_THREE_STORE_DATABASE_PATHS: Final = {
    "pipeline": "state/databases/pipeline.sqlite3",
    "operations": "state/databases/operations.sqlite3",
    "publication": "state/databases/publication.sqlite3",
}
_T = TypeVar("_T")


class OperationsStateError(RuntimeError):
    """Base class for closed operations-ledger failures."""


class OperationsIntegrityError(OperationsStateError):
    """Persisted operations authority is structurally or semantically invalid."""


class OperationsBusy(OperationsStateError):
    """Another process owns the retained operations-state lock."""


class BudgetExhausted(OperationsStateError):
    """A code-owned discovery or semantic reservation ceiling was reached."""


@dataclass(frozen=True)
class TestReservation:
    """Narrow deterministic record used by the Wave-0 budget contract."""

    kind: Literal["discovery", "semantic"]
    run_id: str
    repository_id: int
    ordinal: int
    reservation_digest: str


@dataclass(frozen=True)
class SemanticAttemptRecord:
    """Closed attempt transition without provider payload or diagnostic prose."""

    run_id: str
    repository_id: int
    workflow_authority_digest: str
    stage: Literal["extractor", "generator", "reviewer"]
    attempt_no: int
    status: Literal[
        "started",
        "decided",
        "confirmed_retryable",
        "semantic_outcome_unknown",
    ]
    recorded_at: str
    attempt_digest: str


@dataclass(frozen=True)
class WorkflowTerminalRecord:
    """Exact per-workflow outcome and optional eligible artifact handoff."""

    run_id: str
    repository_id: int
    workflow_authority_digest: str
    outcome: Literal[
        "qualification_rejected",
        "validation_rejected",
        "review_rejected",
        "completed_reuse",
        "eligible_local_candidate",
        "semantic_outcome_unknown",
        "permanent_failure",
    ]
    eligible_locator: str | None
    eligible_object_digest: str | None
    recorded_at: str
    terminal_digest: str


@dataclass(frozen=True)
class DiscoveryRunSnapshot:
    """Typed persisted prefix used as the sole discovery resume authority."""

    search_pages: tuple[SearchPageObservationV1, ...]
    candidates: tuple[DiscoveredCandidateV1, ...]
    discovery_reservations: tuple[DiscoveryReservationV1, ...]
    semantic_reservations: tuple[SemanticReservationV1, ...]
    semantic_attempts: tuple[SemanticAttemptRecord, ...]
    workflow_terminals: tuple[WorkflowTerminalRecord, ...]
    candidate_terminals: tuple[DiscoveryCandidateTerminalV1, ...]
    summary: DiscoveryRunSummaryV1 | None


_AcceptanceFactKind = Literal[
    "acceptance_nomination",
    "acceptance_benchmark_lock",
    "acceptance_live_authority",
    "acceptance_campaign_resume_locator",
    "acceptance_budget_reservation",
    "acceptance_fixed_candidate_admission",
    "acceptance_semantic_request_reservation",
    "acceptance_scenario",
    "acceptance_hosted_isolation_capability",
    "acceptance_offline_adversarial_run",
    "acceptance_replay",
    "acceptance_replay_evidence",
    "acceptance_changed_source",
    "acceptance_publication_replay_completion",
    "acceptance_changed_source_draft_update_completion",
    "acceptance_gate_b4",
    "acceptance_human_review",
    "acceptance_cleanup",
    "acceptance_reviewer_calibration",
    "acceptance_gate",
    "acceptance_report_root",
]

_FactKind = Literal[
    "run",
    "search_page",
    "candidate",
    "discovery_reservation",
    "semantic_reservation",
    "semantic_attempt",
    "workflow_terminal",
    "candidate_terminal",
    "run_summary",
    "root_checkpoint",
    "acceptance_nomination",
    "acceptance_benchmark_lock",
    "acceptance_live_authority",
    "acceptance_campaign_resume_locator",
    "acceptance_budget_reservation",
    "acceptance_fixed_candidate_admission",
    "acceptance_semantic_request_reservation",
    "acceptance_scenario",
    "acceptance_hosted_isolation_capability",
    "acceptance_offline_adversarial_run",
    "acceptance_replay",
    "acceptance_replay_evidence",
    "acceptance_changed_source",
    "acceptance_publication_replay_completion",
    "acceptance_changed_source_draft_update_completion",
    "acceptance_gate_b4",
    "acceptance_human_review",
    "acceptance_cleanup",
    "acceptance_reviewer_calibration",
    "acceptance_gate",
    "acceptance_report_root",
]

_AcceptanceFactModel: TypeAlias = (
    NominationSetV1
    | LockedBenchmarkManifestV1
    | LiveAcceptanceAuthorityV1
    | AcceptanceCampaignResumeLocatorV1
    | AcceptanceBudgetReservationV1
    | AcceptanceFixedCandidateAdmissionV1
    | AcceptanceSemanticRequestReservationV1
    | AcceptanceScenarioResultV1
    | HostedIsolationCapabilityV1
    | OfflineAdversarialRunV1
    | ReplayIntentV1
    | ReplayEvidenceV1
    | ChangedSourceEvidenceV1
    | PublicationReplayCompletionV1
    | ChangedSourceDraftUpdateCompletionV1
    | GateB4BindingV1
    | HumanSkillReviewAttestationV1
    | ProbeCleanupAttestationV1
    | ReviewerCalibrationV1
    | AcceptanceGateResultV1
    | AcceptanceEvidenceRootV1
)

_ACCEPTANCE_FACT_MODEL_VALUES: Final = {
    "acceptance_nomination": NominationSetV1,
    "acceptance_benchmark_lock": LockedBenchmarkManifestV1,
    "acceptance_live_authority": LiveAcceptanceAuthorityV1,
    "acceptance_campaign_resume_locator": AcceptanceCampaignResumeLocatorV1,
    "acceptance_budget_reservation": AcceptanceBudgetReservationV1,
    "acceptance_fixed_candidate_admission": AcceptanceFixedCandidateAdmissionV1,
    "acceptance_semantic_request_reservation": (
        AcceptanceSemanticRequestReservationV1
    ),
    "acceptance_scenario": AcceptanceScenarioResultV1,
    "acceptance_hosted_isolation_capability": HostedIsolationCapabilityV1,
    "acceptance_offline_adversarial_run": OfflineAdversarialRunV1,
    "acceptance_replay": ReplayIntentV1,
    "acceptance_replay_evidence": ReplayEvidenceV1,
    "acceptance_changed_source": ChangedSourceEvidenceV1,
    "acceptance_publication_replay_completion": PublicationReplayCompletionV1,
    "acceptance_changed_source_draft_update_completion": (ChangedSourceDraftUpdateCompletionV1),
    "acceptance_gate_b4": GateB4BindingV1,
    "acceptance_human_review": HumanSkillReviewAttestationV1,
    "acceptance_cleanup": ProbeCleanupAttestationV1,
    "acceptance_reviewer_calibration": ReviewerCalibrationV1,
    "acceptance_gate": AcceptanceGateResultV1,
    "acceptance_report_root": AcceptanceEvidenceRootV1,
}
ACCEPTANCE_FACT_MODELS: Final[Mapping[str, type[StrictFrozenModel]]] = MappingProxyType(
    _ACCEPTANCE_FACT_MODEL_VALUES
)
_ACCEPTANCE_DIGEST_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "acceptance_nomination": "nomination_set_digest",
        "acceptance_benchmark_lock": "manifest_digest",
        "acceptance_live_authority": "authority_digest",
        "acceptance_campaign_resume_locator": "locator_digest",
        "acceptance_budget_reservation": "reservation_digest",
        "acceptance_fixed_candidate_admission": "admission_digest",
        "acceptance_semantic_request_reservation": "reservation_digest",
        "acceptance_scenario": "result_digest",
        "acceptance_hosted_isolation_capability": "capability_digest",
        "acceptance_offline_adversarial_run": "run_digest",
        "acceptance_replay": "replay_digest",
        "acceptance_replay_evidence": "replay_digest",
        "acceptance_changed_source": "changed_source_digest",
        "acceptance_publication_replay_completion": "completion_digest",
        "acceptance_changed_source_draft_update_completion": "completion_digest",
        "acceptance_gate_b4": "binding_digest",
        "acceptance_human_review": "attestation_digest",
        "acceptance_cleanup": "attestation_digest",
        "acceptance_reviewer_calibration": "calibration_digest",
        "acceptance_gate": "gate_digest",
        "acceptance_report_root": "root_digest",
    }
)
_ACCEPTANCE_FACT_KINDS: Final = tuple(ACCEPTANCE_FACT_MODELS)
_PRE_REPLAY_EVIDENCE_ACCEPTANCE_FACT_KINDS: Final = tuple(
    kind
    for kind in _ACCEPTANCE_FACT_KINDS
    if kind != "acceptance_replay_evidence"
)
_PRE_REQUEST_RESERVATION_ACCEPTANCE_FACT_KINDS: Final = tuple(
    kind
    for kind in _PRE_REPLAY_EVIDENCE_ACCEPTANCE_FACT_KINDS
    if kind != "acceptance_semantic_request_reservation"
)
_PRE_FIXED_ADMISSION_ACCEPTANCE_FACT_KINDS: Final = tuple(
    kind
    for kind in _PRE_REQUEST_RESERVATION_ACCEPTANCE_FACT_KINDS
    if kind != "acceptance_fixed_candidate_admission"
)
_PRE_BUDGET_ACCEPTANCE_FACT_KINDS: Final = tuple(
    kind
    for kind in _PRE_FIXED_ADMISSION_ACCEPTANCE_FACT_KINDS
    if kind != "acceptance_budget_reservation"
)
_LEGACY_ACCEPTANCE_FACT_KINDS: Final = tuple(
    kind
    for kind in _PRE_BUDGET_ACCEPTANCE_FACT_KINDS
    if kind
    not in {
        "acceptance_live_authority",
        "acceptance_campaign_resume_locator",
    }
)


@dataclass(frozen=True)
class AcceptanceFactRecord:
    """One typed, redacted acceptance fact owned by the operations ledger."""

    acceptance_run_id: str
    kind: _AcceptanceFactKind
    fact_digest: str
    fact: _AcceptanceFactModel


@dataclass(frozen=True)
class AcceptanceRunSnapshot:
    """Canonical acceptance fact sequence for one acceptance run."""

    acceptance_run_id: str
    facts: tuple[AcceptanceFactRecord, ...]


class OperationsOwnedFactV1(StrictFrozenModel):
    """One canonical, content-addressed discovery-owned rebuild fact."""

    schema_version: Literal["operations-owned-fact-v1"]
    kind: _FactKind
    sequence: Annotated[int, Field(ge=0, le=8_192)]
    payload_json: Annotated[str, Field(min_length=2, max_length=1_048_576)]
    object_digest: Digest

    @model_validator(mode="after")
    def validate_canonical_payload(self) -> OperationsOwnedFactV1:
        decoded = _decoded_json(self.payload_json)
        if not isinstance(decoded, dict):
            raise ValueError("operations fact payload is not an object")
        if self.object_digest != sha256_digest(self.payload_json.encode("utf-8")):
            raise ValueError("operations fact digest mismatch")
        return self


class OperationsStateProjectionV1(StrictFrozenModel):
    """Canonical digest-only projection of discovery and acceptance facts."""

    schema_version: Literal["operations-state-projection-v1"]
    search_page_digests: tuple[Digest, ...]
    candidate_digests: tuple[Digest, ...]
    discovery_reservation_digests: tuple[Digest, ...]
    semantic_reservation_digests: tuple[Digest, ...]
    workflow_terminal_digests: tuple[Digest, ...]
    candidate_terminal_digests: tuple[Digest, ...]
    run_summary_digests: tuple[Digest, ...]
    acceptance_nomination_digests: tuple[Digest, ...]
    acceptance_benchmark_lock_digests: tuple[Digest, ...]
    acceptance_live_authority_digests: tuple[Digest, ...] = Field(
        default=(),
        exclude_if=lambda value: not value,
    )
    acceptance_campaign_resume_locator_digests: tuple[Digest, ...] = Field(
        default=(),
        exclude_if=lambda value: not value,
    )
    acceptance_budget_reservation_digests: tuple[Digest, ...] = Field(
        default=(),
        exclude_if=lambda value: not value,
    )
    acceptance_fixed_candidate_admission_digests: tuple[Digest, ...] = Field(
        default=(),
        exclude_if=lambda value: not value,
    )
    acceptance_semantic_request_reservation_digests: tuple[Digest, ...] = Field(
        default=(),
        exclude_if=lambda value: not value,
    )
    acceptance_scenario_digests: tuple[Digest, ...]
    acceptance_hosted_isolation_capability_digests: tuple[Digest, ...]
    acceptance_offline_adversarial_run_digests: tuple[Digest, ...]
    acceptance_replay_intent_digests: tuple[Digest, ...]
    acceptance_replay_evidence_digests: tuple[Digest, ...] = Field(
        default=(),
        exclude_if=lambda value: not value,
    )
    acceptance_changed_source_intent_digests: tuple[Digest, ...]
    acceptance_publication_replay_completion_digests: tuple[Digest, ...]
    acceptance_changed_source_draft_update_completion_digests: tuple[Digest, ...]
    acceptance_gate_b4_digests: tuple[Digest, ...]
    acceptance_human_review_digests: tuple[Digest, ...]
    acceptance_cleanup_digests: tuple[Digest, ...]
    acceptance_reviewer_calibration_digests: tuple[Digest, ...]
    acceptance_gate_digests: tuple[Digest, ...]
    acceptance_report_root_digests: tuple[Digest, ...]
    projection_digest: Digest

    @model_validator(mode="after")
    def validate_projection_digest(self) -> OperationsStateProjectionV1:
        values = self.model_dump(mode="json", exclude={"projection_digest"})
        if self.projection_digest != sha256_digest(values):
            raise ValueError("operations projection digest mismatch")
        for name, value in values.items():
            if name.endswith("_digests") and (
                value != sorted(value) or len(value) != len(set(value))
            ):
                raise ValueError("operations projection digests are not canonical")
        return self


class OperationsOwnedStateV1(StrictFrozenModel):
    """Complete operations-owned JSON authority plus a disposable SQLite index."""

    schema_version: Literal["operations-owned-state-v1"]
    owner: Literal["operations"]
    database_locator: Literal["state/databases/operations.sqlite3"]
    schema_fingerprint: Digest
    database_bytes: Annotated[bytes, Field(max_length=MAX_OPERATIONS_DB_BYTES)]
    database_digest: Digest
    facts: Annotated[tuple[OperationsOwnedFactV1, ...], Field(max_length=8_192)]
    projection: OperationsStateProjectionV1
    projection_digest: Digest
    export_digest: Digest

    @model_validator(mode="before")
    @classmethod
    def normalize_facts(cls, value: object) -> object:
        if isinstance(value, dict) and isinstance(value.get("facts"), list):
            payload = dict(value)
            payload["facts"] = tuple(payload["facts"])
            return payload
        return value

    @model_validator(mode="after")
    def validate_owned_authority(self) -> OperationsOwnedStateV1:
        if self.schema_fingerprint not in _SCHEMA_FINGERPRINTS:
            raise ValueError("operations schema fingerprint mismatch")
        if tuple(fact.sequence for fact in self.facts) != tuple(range(len(self.facts))):
            raise ValueError("operations facts are not canonically ordered")
        if len({fact.object_digest for fact in self.facts}) != len(self.facts):
            raise ValueError("operations facts are not unique")
        if self.projection != _projection_from_facts(self.facts):
            raise ValueError("operations projection disagrees with facts")
        if self.projection_digest != self.projection.projection_digest:
            raise ValueError("operations projection digest mismatch")
        if self.export_digest != _export_digest(
            schema_fingerprint=self.schema_fingerprint,
            facts=self.facts,
            projection=self.projection,
        ):
            raise ValueError("operations export digest mismatch")
        return self


class ThreeStoreProjectionV1(StrictFrozenModel):
    """Exact owner projections and export digests bound into one root object."""

    schema_version: Literal["three-store-projection-v1"]
    pipeline: PipelineStateProjectionV1
    operations: OperationsStateProjectionV1
    publication: PublicationStateProjectionV1
    pipeline_export_digest: Digest
    operations_export_digest: Digest
    publication_export_digest: Digest
    projection_digest: Digest

    @model_validator(mode="after")
    def validate_three_store_projection(self) -> ThreeStoreProjectionV1:
        values = self.model_dump(mode="json", exclude={"projection_digest"})
        if self.projection_digest != sha256_digest(values):
            raise ValueError("three-store projection digest mismatch")
        return self


def _schema_statements(
    acceptance_fact_kinds: tuple[str, ...] = _ACCEPTANCE_FACT_KINDS,
) -> tuple[str, ...]:
    acceptance_fact_kind_sql = ", ".join(f"'{kind}'" for kind in acceptance_fact_kinds)
    return (
        """CREATE TABLE operations_runs (
            run_id TEXT PRIMARY KEY,
            authority_digest TEXT NOT NULL UNIQUE,
            authority_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('running', 'interrupted', 'completed',
                           'completed_degraded', 'confirmed_retryable',
                           'integrity_conflict', 'permanent_failure')
            ),
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE operations_search_pages (
            observation_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            query_ordinal INTEGER NOT NULL CHECK (query_ordinal BETWEEN 1 AND 4),
            page INTEGER NOT NULL CHECK (page BETWEEN 1 AND 4),
            observation_json TEXT NOT NULL,
            UNIQUE (run_id, query_ordinal, page)
        )""",
        """CREATE TABLE operations_candidates (
            candidate_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            source_page_digest TEXT NOT NULL
                REFERENCES operations_search_pages(observation_digest),
            query_ordinal INTEGER NOT NULL CHECK (query_ordinal BETWEEN 1 AND 4),
            page INTEGER NOT NULL CHECK (page BETWEEN 1 AND 4),
            item_ordinal INTEGER NOT NULL CHECK (item_ordinal BETWEEN 1 AND 25),
            candidate_json TEXT NOT NULL,
            UNIQUE (run_id, query_ordinal, page, item_ordinal)
        )""",
        """CREATE TABLE operations_discovery_reservations (
            reservation_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            ordinal INTEGER NOT NULL CHECK (ordinal BETWEEN 1 AND 100),
            candidate_digest TEXT NOT NULL,
            reservation_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id),
            UNIQUE (run_id, ordinal)
        )""",
        """CREATE TABLE operations_semantic_reservations (
            reservation_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            ordinal INTEGER NOT NULL CHECK (ordinal BETWEEN 1 AND 20),
            discovery_reservation_digest TEXT NOT NULL,
            phase2_run_authority_digest TEXT NOT NULL,
            reservation_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id),
            UNIQUE (run_id, ordinal)
        )""",
        """CREATE TABLE operations_semantic_attempts (
            attempt_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            workflow_authority_digest TEXT NOT NULL,
            stage TEXT NOT NULL CHECK (
                stage IN ('extractor', 'generator', 'reviewer')
            ),
            attempt_no INTEGER NOT NULL CHECK (attempt_no BETWEEN 1 AND 16),
            status TEXT NOT NULL CHECK (
                status IN ('started', 'decided', 'confirmed_retryable',
                           'semantic_outcome_unknown')
            ),
            attempt_json TEXT NOT NULL,
            UNIQUE (
                run_id, repository_id, workflow_authority_digest,
                stage, attempt_no
            )
        )""",
        """CREATE TABLE operations_workflow_terminals (
            terminal_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            workflow_authority_digest TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK (
                outcome IN ('qualification_rejected', 'validation_rejected',
                            'review_rejected', 'completed_reuse',
                            'eligible_local_candidate',
                            'semantic_outcome_unknown', 'permanent_failure')
            ),
            eligible_locator TEXT,
            eligible_object_digest TEXT,
            recorded_at TEXT NOT NULL,
            terminal_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id, workflow_authority_digest)
        )""",
        """CREATE TABLE operations_candidate_terminals (
            terminal_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            semantic_reservation_digest TEXT,
            outcome TEXT NOT NULL CHECK (
                outcome IN ('filter_rejected', 'no_workflow',
                            'qualification_rejected', 'validation_rejected',
                            'review_rejected', 'completed_reuse',
                            'eligible_local_candidate', 'confirmed_retryable',
                            'semantic_outcome_unknown',
                            'state_integrity_conflict', 'permanent_failure')
            ),
            terminal_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id)
        )""",
        """CREATE TABLE operations_run_summaries (
            summary_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL UNIQUE REFERENCES operations_runs(run_id),
            summary_json TEXT NOT NULL
        )""",
        """CREATE TABLE operations_root_checkpoints (
            checkpoint_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            event_index INTEGER NOT NULL CHECK (event_index >= 0),
            prior_checkpoint_digest TEXT,
            state_root_digest TEXT NOT NULL,
            state_commit_sha TEXT NOT NULL,
            checkpoint_json TEXT NOT NULL,
            UNIQUE (run_id, event_index)
        )""",
        f"""CREATE TABLE operations_acceptance_facts (
            fact_digest TEXT PRIMARY KEY,
            acceptance_run_id TEXT NOT NULL
                CHECK (length(acceptance_run_id) BETWEEN 1 AND 256),
            fact_kind TEXT NOT NULL CHECK (
                fact_kind IN ({acceptance_fact_kind_sql})
            ),
            schema_version TEXT NOT NULL
                CHECK (length(schema_version) BETWEEN 1 AND 128),
            recorded_identity TEXT NOT NULL
                CHECK (length(recorded_identity) BETWEEN 1 AND 1024),
            fact_json TEXT NOT NULL,
            UNIQUE (acceptance_run_id, fact_kind, recorded_identity)
        )""",
    )


def _normalize_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _expected_schema(
    acceptance_fact_kinds: tuple[str, ...] = _ACCEPTANCE_FACT_KINDS,
) -> dict[str, str]:
    pattern = re.compile(r"^CREATE TABLE ([^\s(]+)", re.I)
    expected: dict[str, str] = {}
    for statement in _schema_statements(acceptance_fact_kinds):
        matched = pattern.match(statement)
        if matched is None:
            raise RuntimeError("invalid trusted operations schema")
        expected[matched.group(1)] = _normalize_sql(statement)
    return expected


_EXPECTED_SCHEMA: Final = _expected_schema()
_PRE_REPLAY_EVIDENCE_EXPECTED_SCHEMA: Final = _expected_schema(
    _PRE_REPLAY_EVIDENCE_ACCEPTANCE_FACT_KINDS
)
_PRE_REQUEST_RESERVATION_EXPECTED_SCHEMA: Final = _expected_schema(
    _PRE_REQUEST_RESERVATION_ACCEPTANCE_FACT_KINDS
)
_PRE_FIXED_ADMISSION_EXPECTED_SCHEMA: Final = _expected_schema(
    _PRE_FIXED_ADMISSION_ACCEPTANCE_FACT_KINDS
)
_PRE_BUDGET_EXPECTED_SCHEMA: Final = _expected_schema(
    _PRE_BUDGET_ACCEPTANCE_FACT_KINDS
)
_LEGACY_EXPECTED_SCHEMA: Final = _expected_schema(_LEGACY_ACCEPTANCE_FACT_KINDS)
_FACT_TABLES: Final[tuple[tuple[_FactKind, str, str, tuple[str, ...], tuple[str, ...]], ...]] = (
    (
        "run",
        "operations_runs",
        "authority_json",
        ("run_id",),
        ("run_id", "authority_digest", "status", "created_at"),
    ),
    (
        "search_page",
        "operations_search_pages",
        "observation_json",
        ("run_id", "query_ordinal", "page"),
        ("observation_digest", "run_id", "query_ordinal", "page"),
    ),
    (
        "candidate",
        "operations_candidates",
        "candidate_json",
        ("run_id", "query_ordinal", "page", "item_ordinal"),
        (
            "candidate_digest",
            "run_id",
            "repository_id",
            "source_page_digest",
            "query_ordinal",
            "page",
            "item_ordinal",
        ),
    ),
    (
        "discovery_reservation",
        "operations_discovery_reservations",
        "reservation_json",
        ("run_id", "ordinal"),
        (
            "reservation_digest",
            "run_id",
            "repository_id",
            "ordinal",
            "candidate_digest",
        ),
    ),
    (
        "semantic_reservation",
        "operations_semantic_reservations",
        "reservation_json",
        ("run_id", "ordinal"),
        (
            "reservation_digest",
            "run_id",
            "repository_id",
            "ordinal",
            "discovery_reservation_digest",
            "phase2_run_authority_digest",
        ),
    ),
    (
        "semantic_attempt",
        "operations_semantic_attempts",
        "attempt_json",
        (
            "run_id",
            "repository_id",
            "workflow_authority_digest",
            "stage",
            "attempt_no",
        ),
        (
            "attempt_digest",
            "run_id",
            "repository_id",
            "workflow_authority_digest",
            "stage",
            "attempt_no",
            "status",
        ),
    ),
    (
        "workflow_terminal",
        "operations_workflow_terminals",
        "terminal_json",
        ("run_id", "repository_id", "workflow_authority_digest"),
        (
            "terminal_digest",
            "run_id",
            "repository_id",
            "workflow_authority_digest",
            "outcome",
            "eligible_locator",
            "eligible_object_digest",
            "recorded_at",
        ),
    ),
    (
        "candidate_terminal",
        "operations_candidate_terminals",
        "terminal_json",
        ("run_id", "repository_id"),
        (
            "terminal_digest",
            "run_id",
            "repository_id",
            "semantic_reservation_digest",
            "outcome",
        ),
    ),
    (
        "run_summary",
        "operations_run_summaries",
        "summary_json",
        ("run_id",),
        ("summary_digest", "run_id"),
    ),
    (
        "root_checkpoint",
        "operations_root_checkpoints",
        "checkpoint_json",
        ("run_id", "event_index"),
        (
            "checkpoint_digest",
            "run_id",
            "event_index",
            "prior_checkpoint_digest",
            "state_root_digest",
            "state_commit_sha",
        ),
    ),
    (
        "acceptance_nomination",
        "operations_acceptance_facts",
        "fact_json",
        ("acceptance_run_id", "fact_kind", "fact_digest"),
        (
            "fact_digest",
            "acceptance_run_id",
            "fact_kind",
            "schema_version",
            "recorded_identity",
        ),
    ),
)


def _fingerprint_for_schema(schema: Mapping[str, str]) -> str:
    return sha256_digest(tuple((name, schema[name]) for name in sorted(schema)))


def _schema_fingerprint() -> str:
    return _fingerprint_for_schema(_EXPECTED_SCHEMA)


_SCHEMA_FINGERPRINTS: Final = frozenset(
    {
        _fingerprint_for_schema(_EXPECTED_SCHEMA),
        _fingerprint_for_schema(_PRE_REPLAY_EVIDENCE_EXPECTED_SCHEMA),
        _fingerprint_for_schema(_PRE_REQUEST_RESERVATION_EXPECTED_SCHEMA),
        _fingerprint_for_schema(_PRE_FIXED_ADMISSION_EXPECTED_SCHEMA),
        _fingerprint_for_schema(_PRE_BUDGET_EXPECTED_SCHEMA),
        _fingerprint_for_schema(_LEGACY_EXPECTED_SCHEMA),
    }
)


def _json_text(value: object) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _decoded_json(value: object) -> object:
    if type(value) is not str:
        raise OperationsIntegrityError("invalid canonical operations JSON")
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        raise OperationsIntegrityError("invalid canonical operations JSON") from None
    if _json_text(decoded) != value:
        raise OperationsIntegrityError("noncanonical operations JSON")
    return decoded


def _test_run_payload(run_id: str) -> dict[str, object]:
    values: dict[str, object] = {
        "schema_version": _TEST_RUN_SCHEMA,
        "run_id": run_id,
    }
    values["authority_digest"] = sha256_digest(values)
    return values


def _fact_payload(fact: OperationsOwnedFactV1) -> dict[str, object]:
    decoded = _decoded_json(fact.payload_json)
    if not isinstance(decoded, dict):
        raise OperationsIntegrityError("operations fact payload is not an object")
    return decoded


def _contains_forbidden_acceptance_key(value: object) -> bool:
    forbidden = {
        "raw_corpus",
        "raw_log",
        "raw_logs",
        "repository_body",
        "response_body",
        "fixture_prose",
        "authorization",
        "token",
        "api_key",
        "private_key",
        "credential",
        "home_path",
        "repository_path",
        "home_scan",
        "repository_scan",
        "unrestricted_path",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in forbidden or _contains_forbidden_acceptance_key(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_acceptance_key(item) for item in value)
    return False


def _acceptance_fact_digest(kind: str, fact: StrictFrozenModel) -> str:
    field = _ACCEPTANCE_DIGEST_FIELDS.get(kind)
    digest = None if field is None else getattr(fact, field, None)
    if type(digest) is not str or _DIGEST_PATTERN.fullmatch(digest) is None:
        raise OperationsIntegrityError("acceptance fact self-digest is invalid")
    return digest


def _validate_acceptance_model(
    kind: str,
    raw: object,
) -> _AcceptanceFactModel:
    model = ACCEPTANCE_FACT_MODELS.get(kind)
    if model is None or not isinstance(raw, dict) or _contains_forbidden_acceptance_key(raw):
        raise OperationsIntegrityError("acceptance fact kind or redaction boundary is invalid")
    try:
        # JSON arrays are the canonical wire form of frozen tuple fields.
        # Exact post-parse byte equality below rejects every coercive drift.
        fact = model.model_validate_json(_json_text(raw), strict=False)
    except Exception:
        raise OperationsIntegrityError("acceptance fact model is invalid") from None
    if _json_text(fact.model_dump(mode="json", exclude_none=False)) != _json_text(raw):
        raise OperationsIntegrityError("acceptance fact JSON is not exact")
    _acceptance_fact_digest(kind, fact)
    return fact  # type: ignore[return-value]


def _acceptance_recorded_identity(
    acceptance_run_id: str,
    kind: str,
    fact: _AcceptanceFactModel,
) -> str:
    if kind == "acceptance_publication_replay_completion":
        assert isinstance(fact, PublicationReplayCompletionV1)
        values = (
            acceptance_run_id,
            fact.replay_intent_digest,
            fact.publication_key,
            fact.pull_request_number,
            fact.head_commit_sha,
        )
    elif kind == "acceptance_changed_source_draft_update_completion":
        assert isinstance(fact, ChangedSourceDraftUpdateCompletionV1)
        values = (
            acceptance_run_id,
            fact.changed_source_intent_digest,
            fact.publication_key,
            fact.pull_request_number,
            fact.new_head_commit_sha,
        )
    elif kind == "acceptance_scenario":
        assert isinstance(fact, AcceptanceScenarioResultV1)
        values = (acceptance_run_id, kind, fact.scenario_id)
    elif kind == "acceptance_budget_reservation":
        assert isinstance(fact, AcceptanceBudgetReservationV1)
        values = (
            acceptance_run_id,
            kind,
            fact.benchmark_manifest_digest,
            fact.benchmark_entry_digest,
            fact.repository_id,
            fact.ordinal,
        )
    elif kind == "acceptance_fixed_candidate_admission":
        assert isinstance(fact, AcceptanceFixedCandidateAdmissionV1)
        values = (
            acceptance_run_id,
            kind,
            fact.benchmark_manifest_digest,
            fact.benchmark_entry_digest,
            fact.repository_id,
            fact.ordinal,
        )
    else:
        values = (acceptance_run_id, kind, _acceptance_fact_digest(kind, fact))
    return _json_text(values)


def _acceptance_run_binding(
    acceptance_run_id: str,
    fact: _AcceptanceFactModel,
) -> None:
    bound_run_id = getattr(fact, "acceptance_run_id", acceptance_run_id)
    if bound_run_id != acceptance_run_id:
        raise OperationsIntegrityError("acceptance fact is bound to another run")


def _acceptance_row_fact(row: sqlite3.Row) -> _AcceptanceFactModel:
    raw = _decoded_json(row["fact_json"])
    fact = _validate_acceptance_model(str(row["fact_kind"]), raw)
    if (
        str(getattr(fact, "schema_version")) != row["schema_version"]
        or _acceptance_fact_digest(str(row["fact_kind"]), fact) != row["fact_digest"]
    ):
        raise OperationsIntegrityError("acceptance row metadata mismatch")
    _acceptance_run_binding(str(row["acceptance_run_id"]), fact)
    if (
        _acceptance_recorded_identity(str(row["acceptance_run_id"]), str(row["fact_kind"]), fact)
        != row["recorded_identity"]
    ):
        raise OperationsIntegrityError("acceptance fact natural identity mismatch")
    return fact


def _acceptance_fact_by_digest(
    connection: sqlite3.Connection,
    *,
    acceptance_run_id: str,
    kind: str,
    digest: str,
) -> _AcceptanceFactModel:
    row = connection.execute(
        """SELECT * FROM operations_acceptance_facts
           WHERE acceptance_run_id = ? AND fact_kind = ? AND fact_digest = ?""",
        (acceptance_run_id, kind, digest),
    ).fetchone()
    if row is None:
        raise OperationsIntegrityError("required prior acceptance fact is missing")
    return _acceptance_row_fact(row)


def _validate_acceptance_references(
    connection: sqlite3.Connection,
    *,
    acceptance_run_id: str,
    kind: str,
    fact: _AcceptanceFactModel,
) -> None:
    if kind == "acceptance_scenario":
        assert isinstance(fact, AcceptanceScenarioResultV1)
        try:
            authority = _acceptance_fact_by_digest(
                connection,
                acceptance_run_id=acceptance_run_id,
                kind="acceptance_live_authority",
                digest=fact.live_acceptance_authority_digest,
            )
        except OperationsIntegrityError:
            raise OperationsIntegrityError(
                "scenario live authority is missing"
            ) from None
        assert isinstance(authority, LiveAcceptanceAuthorityV1)
        if authority.manifest_digest != fact.benchmark_manifest_digest:
            raise OperationsIntegrityError(
                "scenario live authority manifest binding mismatch"
            )
        manifest = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_benchmark_lock",
            digest=fact.benchmark_manifest_digest,
        )
        assert isinstance(manifest, LockedBenchmarkManifestV1)
        entries = tuple(
            entry
            for entry in manifest.entries
            if entry.repository_id == fact.repository_id
        )
        if len(entries) != 1:
            raise OperationsIntegrityError(
                "scenario benchmark entry is missing"
            )
        entry = entries[0]
        if (
            entry.entry_digest != fact.benchmark_entry_digest
            or (
                entry.repository_full_name,
                entry.exact_commit_sha,
                entry.license_spdx,
            )
            != (
                fact.repository_full_name,
                fact.exact_commit_sha,
                fact.license_spdx,
            )
        ):
            raise OperationsIntegrityError(
                "scenario benchmark repository binding mismatch"
            )
        reference_rows = connection.execute(
            """SELECT * FROM operations_acceptance_facts
               WHERE acceptance_run_id = ?
                 AND fact_kind IN (
                   'acceptance_budget_reservation',
                   'acceptance_fixed_candidate_admission',
                   'acceptance_semantic_request_reservation'
                 )""",
            (acceptance_run_id,),
        ).fetchall()
        references = tuple(_acceptance_row_fact(row) for row in reference_rows)
        budgets = tuple(
            item
            for item in references
            if isinstance(item, AcceptanceBudgetReservationV1)
            and item.repository_id == fact.repository_id
        )
        admissions = tuple(
            item
            for item in references
            if isinstance(item, AcceptanceFixedCandidateAdmissionV1)
            and item.repository_id == fact.repository_id
        )
        if len(budgets) != 1 or len(admissions) != 1:
            raise OperationsIntegrityError(
                "scenario budget or admission reference is missing"
            )
        budget = budgets[0]
        admission = admissions[0]
        expected_identity = (
            fact.benchmark_manifest_digest,
            entry.nomination_entry_digest,
            entry.entry_digest,
            fact.repository_id,
            fact.repository_full_name,
        )
        if (
            (
                budget.benchmark_manifest_digest,
                budget.nomination_entry_digest,
                budget.benchmark_entry_digest,
                budget.repository_id,
                budget.repository_full_name,
            )
            != expected_identity
            or (
                admission.benchmark_manifest_digest,
                admission.nomination_entry_digest,
                admission.benchmark_entry_digest,
                admission.repository_id,
                admission.repository_full_name,
            )
            != expected_identity
            or admission.exact_commit_sha != fact.exact_commit_sha
            or admission.license_spdx != fact.license_spdx
            or budget.ordinal != admission.ordinal
            or budget.reservation_digest != fact.budget_reservation_digest
            or admission.admission_digest
            != fact.fixed_candidate_admission_digest
        ):
            raise OperationsIntegrityError(
                "scenario budget or admission binding mismatch"
            )
        requests = tuple(
            item
            for item in references
            if isinstance(item, AcceptanceSemanticRequestReservationV1)
            and item.repository_id == fact.repository_id
        )
        request_keys = {
            (
                item.stage,
                item.workflow_spec_authority_digest,
                item.attempt_no,
            )
            for item in requests
        }
        telemetry_keys = {
            (
                item.stage,
                item.workflow_spec_authority_digest,
                item.attempt_no,
            )
            for item in fact.semantic_telemetry
        }
        run_row = connection.execute(
            """SELECT authority_digest FROM operations_runs
               WHERE run_id = ?""",
            (fact.discovery_run_id,),
        ).fetchone()
        semantic_rows = connection.execute(
            """SELECT reservation_json FROM operations_semantic_reservations
               WHERE run_id = ? AND repository_id = ?""",
            (fact.discovery_run_id, fact.repository_id),
        ).fetchall()
        semantic_reservations = tuple(
            SemanticReservationV1.model_validate_json(
                row["reservation_json"],
                strict=True,
            )
            for row in semantic_rows
        )
        attempt_rows = connection.execute(
            """SELECT attempt_digest, workflow_authority_digest, stage,
                      attempt_no
               FROM operations_semantic_attempts
               WHERE run_id = ? AND repository_id = ?
               ORDER BY attempt_digest""",
            (fact.discovery_run_id, fact.repository_id),
        ).fetchall()
        attempt_digests = tuple(
            sorted(str(row["attempt_digest"]) for row in attempt_rows)
        )
        attempt_keys = {
            (
                str(row["stage"]),
                str(row["workflow_authority_digest"]),
                int(row["attempt_no"]),
            )
            for row in attempt_rows
        }
        candidate_rows = connection.execute(
            """SELECT terminal_json FROM operations_candidate_terminals
               WHERE run_id = ? AND repository_id = ?""",
            (fact.discovery_run_id, fact.repository_id),
        ).fetchall()
        candidate_terminals = tuple(
            DiscoveryCandidateTerminalV1.model_validate_json(
                row["terminal_json"],
                strict=True,
            )
            for row in candidate_rows
        )
        workflow_rows = connection.execute(
            """SELECT workflow_authority_digest, eligible_locator,
                      eligible_object_digest, terminal_digest
               FROM operations_workflow_terminals
               WHERE run_id = ? AND repository_id = ?
               ORDER BY terminal_digest""",
            (fact.discovery_run_id, fact.repository_id),
        ).fetchall()
        workflow_digests = tuple(
            sorted(str(row["terminal_digest"]) for row in workflow_rows)
        )
        workflow_authorities = tuple(
            sorted(str(row["workflow_authority_digest"]) for row in workflow_rows)
        )
        eligible_rows = tuple(
            row for row in workflow_rows if row["eligible_locator"] is not None
        )
        expected_evidence = {
            fact.live_acceptance_authority_digest,
            fact.benchmark_manifest_digest,
            entry.nomination_entry_digest,
            fact.benchmark_entry_digest,
            fact.budget_reservation_digest,
            fact.fixed_candidate_admission_digest,
            fact.candidate_terminal_digest,
            *fact.semantic_request_reservation_digests,
            *fact.semantic_attempt_digests,
            *fact.workflow_execution_authority_digests,
            *fact.workflow_spec_authority_digests,
            *fact.workflow_terminal_digests,
            *fact.phase3_terminal_summary_digests,
            *fact.skill_artifact_digests,
            *fact.package_digests,
        }
        if fact.semantic_candidate_reservation_digest is not None:
            expected_evidence.add(fact.semantic_candidate_reservation_digest)
        if fact.eligible_object_digest is not None:
            expected_evidence.add(fact.eligible_object_digest)
        if (
            len(requests) != fact.semantic_request_count
            or tuple(sorted(item.reservation_digest for item in requests))
            != fact.semantic_request_reservation_digests
            or any(
                item.fixed_candidate_admission_digest
                != admission.admission_digest
                for item in requests
            )
            or not telemetry_keys.issubset(request_keys)
            or run_row is None
            or str(run_row["authority_digest"])
            != fact.discovery_run_authority_digest
            or len(semantic_reservations)
            != (1 if fact.semantic_candidate_reservation_digest is not None else 0)
            or (
                semantic_reservations
                and semantic_reservations[0].reservation_digest
                != fact.semantic_candidate_reservation_digest
            )
            or request_keys != attempt_keys
            or attempt_digests != fact.semantic_attempt_digests
            or len(candidate_terminals) != 1
            or candidate_terminals[0].terminal_digest
            != fact.candidate_terminal_digest
            or candidate_terminals[0].discovery_run_authority_digest
            != fact.discovery_run_authority_digest
            or candidate_terminals[0].repository_id != fact.repository_id
            or tuple(sorted(candidate_terminals[0].workflow_authority_digests))
            != fact.workflow_execution_authority_digests
            or workflow_digests != fact.workflow_terminal_digests
            or workflow_authorities
            != fact.workflow_execution_authority_digests
            or (
                fact.eligible_locator is None
                and eligible_rows
            )
            or (
                fact.eligible_locator is not None
                and (
                    len(eligible_rows) != 1
                    or eligible_rows[0]["eligible_locator"]
                    != fact.eligible_locator
                    or eligible_rows[0]["eligible_object_digest"]
                    != fact.eligible_object_digest
                )
            )
            or set(fact.evidence_digests) != expected_evidence
        ):
            raise OperationsIntegrityError(
                "scenario semantic request binding mismatch"
            )
    elif kind == "acceptance_offline_adversarial_run":
        assert isinstance(fact, OfflineAdversarialRunV1)
        hosted = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_hosted_isolation_capability",
            digest=fact.hosted_capability_digest,
        )
        assert isinstance(hosted, HostedIsolationCapabilityV1)
        if (
            fact.workflow_sha256,
            fact.source_commit_sha,
            fact.hosted_run_id,
            fact.run_attempt,
            fact.isolation_mechanism,
            fact.synthetic_scan_manifest_digest,
        ) != (
            hosted.workflow_sha256,
            hosted.source_commit_sha,
            hosted.hosted_run_id,
            hosted.run_attempt,
            hosted.isolation_mechanism,
            hosted.synthetic_scan_manifest_digest,
        ):
            raise OperationsIntegrityError("offline run capability binding mismatch")
    elif kind == "acceptance_replay_evidence":
        assert isinstance(fact, ReplayEvidenceV1)
        replay = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_replay",
            digest=fact.replay_fact_digest,
        )
        assert isinstance(replay, ReplayIntentV1)
        if (
            fact.repository_id,
            fact.source_commit_sha,
            fact.workflow_fingerprint,
            fact.workflow_spec_authority_digest,
            fact.benchmark_manifest_digest,
            fact.before_state_commit_sha,
            fact.before_state_root_digest,
            fact.before_projection_digest,
            fact.before_object_digests,
        ) != (
            replay.repository_id,
            replay.source_commit_sha,
            replay.workflow_fingerprint,
            replay.workflow_spec_authority_digest,
            replay.benchmark_manifest_digest,
            replay.before_state_commit_sha,
            replay.before_state_root_digest,
            replay.before_projection_digest,
            replay.before_object_digests,
        ):
            raise OperationsIntegrityError("replay evidence intent binding mismatch")
    elif kind == "acceptance_publication_replay_completion":
        assert isinstance(fact, PublicationReplayCompletionV1)
        replay = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_replay",
            digest=fact.replay_intent_digest,
        )
        assert isinstance(replay, ReplayIntentV1)
        if (
            fact.repository_id,
            fact.source_commit_sha,
            fact.workflow_fingerprint,
            fact.workflow_spec_authority_digest,
        ) != (
            replay.repository_id,
            replay.source_commit_sha,
            replay.workflow_fingerprint,
            replay.workflow_spec_authority_digest,
        ):
            raise OperationsIntegrityError("publication replay intent binding mismatch")
    elif kind == "acceptance_changed_source_draft_update_completion":
        assert isinstance(fact, ChangedSourceDraftUpdateCompletionV1)
        changed = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_changed_source",
            digest=fact.changed_source_intent_digest,
        )
        assert isinstance(changed, ChangedSourceEvidenceV1)
        if (
            fact.repository_id,
            fact.prior_source_commit_sha,
            fact.new_source_commit_sha,
            fact.prior_workflow_fingerprint,
            fact.new_workflow_fingerprint,
            fact.prior_workflow_spec_authority_digest,
            fact.new_workflow_spec_authority_digest,
            fact.prior_lineage_binding_digest,
            fact.lineage_approval_record_digest,
            fact.publication_key,
            fact.new_lineage_id,
        ) != (
            changed.repository_id,
            changed.prior_source_commit_sha,
            changed.new_source_commit_sha,
            changed.prior_workflow_fingerprint,
            changed.new_workflow_fingerprint,
            changed.prior_workflow_spec_authority_digest,
            changed.new_workflow_spec_authority_digest,
            changed.prior_lineage_binding_digest,
            changed.lineage_approval_record_digest,
            changed.planned_publication_key,
            changed.planned_lineage_id,
        ):
            raise OperationsIntegrityError("changed-source intent binding mismatch")
    elif kind == "acceptance_benchmark_lock":
        assert isinstance(fact, LockedBenchmarkManifestV1)
        _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_nomination",
            digest=fact.nomination_set_digest,
        )
    elif kind == "acceptance_live_authority":
        assert isinstance(fact, LiveAcceptanceAuthorityV1)
        manifest = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_benchmark_lock",
            digest=fact.manifest_digest,
        )
        assert isinstance(manifest, LockedBenchmarkManifestV1)
        if (
            fact.nomination_set_digest != manifest.nomination_set_digest
            or fact.lock_attestation_digest
            != manifest.lock_attestation.attestation_digest
        ):
            raise OperationsIntegrityError("live authority manifest binding mismatch")
    elif kind == "acceptance_campaign_resume_locator":
        assert isinstance(fact, AcceptanceCampaignResumeLocatorV1)
        authority = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_live_authority",
            digest=fact.live_acceptance_authority_digest,
        )
        assert isinstance(authority, LiveAcceptanceAuthorityV1)
        if (
            fact.source_commit_sha != authority.source_commit_sha
            or fact.manifest_digest != authority.manifest_digest
            or fact.state_repository_id != authority.state_repository_id
            or fact.state_repository_full_name
            != authority.state_repository_full_name
            or fact.original_state_commit_sha
            != authority.state_commit_sha
            or fact.original_state_root_digest
            != authority.state_root_digest
            or fact.semantic_provider != authority.semantic_provider
            or fact.stage_models != authority.stage_models
            or fact.prompt_versions != authority.prompt_versions
            or fact.schema_versions != authority.schema_versions
            or fact.policy_versions != authority.policy_versions
        ):
            raise OperationsIntegrityError(
                "campaign resume locator authority binding mismatch"
            )
    elif kind == "acceptance_budget_reservation":
        assert isinstance(fact, AcceptanceBudgetReservationV1)
        manifest = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_benchmark_lock",
            digest=fact.benchmark_manifest_digest,
        )
        assert isinstance(manifest, LockedBenchmarkManifestV1)
        entries = tuple(
            entry
            for entry in manifest.entries
            if entry.entry_digest == fact.benchmark_entry_digest
        )
        if (
            len(entries) != 1
            or entries[0].nomination_entry_digest
            != fact.nomination_entry_digest
            or entries[0].repository_id != fact.repository_id
            or entries[0].repository_full_name != fact.repository_full_name
        ):
            raise OperationsIntegrityError(
                "acceptance budget reservation binding mismatch"
            )
    elif kind == "acceptance_fixed_candidate_admission":
        assert isinstance(fact, AcceptanceFixedCandidateAdmissionV1)
        manifest = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_benchmark_lock",
            digest=fact.benchmark_manifest_digest,
        )
        assert isinstance(manifest, LockedBenchmarkManifestV1)
        entries = tuple(
            entry
            for entry in manifest.entries
            if entry.entry_digest == fact.benchmark_entry_digest
        )
        if (
            len(entries) != 1
            or entries[0].nomination_entry_digest
            != fact.nomination_entry_digest
            or entries[0].repository_id != fact.repository_id
            or entries[0].repository_full_name != fact.repository_full_name
            or entries[0].exact_commit_sha != fact.exact_commit_sha
            or entries[0].license_spdx != fact.license_spdx
        ):
            raise OperationsIntegrityError(
                "fixed acceptance admission binding mismatch"
            )
    elif kind == "acceptance_semantic_request_reservation":
        assert isinstance(fact, AcceptanceSemanticRequestReservationV1)
        admission = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_fixed_candidate_admission",
            digest=fact.fixed_candidate_admission_digest,
        )
        assert isinstance(admission, AcceptanceFixedCandidateAdmissionV1)
        if fact.repository_id != admission.repository_id:
            raise OperationsIntegrityError(
                "semantic request reservation admission mismatch"
            )
    elif kind == "acceptance_cleanup":
        assert isinstance(fact, ProbeCleanupAttestationV1)
        binding = _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_gate_b4",
            digest=fact.gate_b4_binding_digest,
        )
        assert isinstance(binding, GateB4BindingV1)
        if (
            fact.cleanup_target_digests
            != tuple(target.target_digest for target in binding.cleanup_targets)
            or fact.default_branch_before_sha != binding.default_branch_before_sha
            or fact.default_branch_after_sha != binding.default_branch_after_sha
        ):
            raise OperationsIntegrityError("cleanup attestation binding mismatch")
    elif kind == "acceptance_report_root":
        assert isinstance(fact, AcceptanceEvidenceRootV1)
        _acceptance_fact_by_digest(
            connection,
            acceptance_run_id=acceptance_run_id,
            kind="acceptance_benchmark_lock",
            digest=fact.benchmark_manifest_digest,
        )
        gate_digests = {
            str(row["fact_digest"])
            for row in connection.execute(
                """SELECT fact_digest FROM operations_acceptance_facts
                   WHERE acceptance_run_id = ? AND fact_kind = 'acceptance_gate'""",
                (acceptance_run_id,),
            ).fetchall()
        }
        if {gate.gate_digest for gate in fact.gate_results} != gate_digests:
            raise OperationsIntegrityError("acceptance report root gate set is stale")


def _projection_from_facts(
    facts: tuple[OperationsOwnedFactV1, ...],
) -> OperationsStateProjectionV1:
    fields: dict[str, list[str]] = {
        "search_page_digests": [],
        "candidate_digests": [],
        "discovery_reservation_digests": [],
        "semantic_reservation_digests": [],
        "workflow_terminal_digests": [],
        "candidate_terminal_digests": [],
        "run_summary_digests": [],
        "acceptance_nomination_digests": [],
        "acceptance_benchmark_lock_digests": [],
        "acceptance_live_authority_digests": [],
        "acceptance_campaign_resume_locator_digests": [],
        "acceptance_budget_reservation_digests": [],
        "acceptance_fixed_candidate_admission_digests": [],
        "acceptance_semantic_request_reservation_digests": [],
        "acceptance_scenario_digests": [],
        "acceptance_hosted_isolation_capability_digests": [],
        "acceptance_offline_adversarial_run_digests": [],
        "acceptance_replay_intent_digests": [],
        "acceptance_replay_evidence_digests": [],
        "acceptance_changed_source_intent_digests": [],
        "acceptance_publication_replay_completion_digests": [],
        "acceptance_changed_source_draft_update_completion_digests": [],
        "acceptance_gate_b4_digests": [],
        "acceptance_human_review_digests": [],
        "acceptance_cleanup_digests": [],
        "acceptance_reviewer_calibration_digests": [],
        "acceptance_gate_digests": [],
        "acceptance_report_root_digests": [],
    }
    mapping = {
        "search_page": ("search_page_digests", "observation_digest"),
        "candidate": ("candidate_digests", "candidate_digest"),
        "discovery_reservation": (
            "discovery_reservation_digests",
            "reservation_digest",
        ),
        "semantic_reservation": (
            "semantic_reservation_digests",
            "reservation_digest",
        ),
        "workflow_terminal": ("workflow_terminal_digests", "terminal_digest"),
        "candidate_terminal": ("candidate_terminal_digests", "terminal_digest"),
        "run_summary": ("run_summary_digests", "summary_digest"),
        "acceptance_nomination": (
            "acceptance_nomination_digests",
            "nomination_set_digest",
        ),
        "acceptance_benchmark_lock": (
            "acceptance_benchmark_lock_digests",
            "manifest_digest",
        ),
        "acceptance_live_authority": (
            "acceptance_live_authority_digests",
            "authority_digest",
        ),
        "acceptance_campaign_resume_locator": (
            "acceptance_campaign_resume_locator_digests",
            "locator_digest",
        ),
        "acceptance_budget_reservation": (
            "acceptance_budget_reservation_digests",
            "reservation_digest",
        ),
        "acceptance_fixed_candidate_admission": (
            "acceptance_fixed_candidate_admission_digests",
            "admission_digest",
        ),
        "acceptance_semantic_request_reservation": (
            "acceptance_semantic_request_reservation_digests",
            "reservation_digest",
        ),
        "acceptance_scenario": ("acceptance_scenario_digests", "result_digest"),
        "acceptance_hosted_isolation_capability": (
            "acceptance_hosted_isolation_capability_digests",
            "capability_digest",
        ),
        "acceptance_offline_adversarial_run": (
            "acceptance_offline_adversarial_run_digests",
            "run_digest",
        ),
        "acceptance_replay": (
            "acceptance_replay_intent_digests",
            "replay_digest",
        ),
        "acceptance_replay_evidence": (
            "acceptance_replay_evidence_digests",
            "replay_digest",
        ),
        "acceptance_changed_source": (
            "acceptance_changed_source_intent_digests",
            "changed_source_digest",
        ),
        "acceptance_publication_replay_completion": (
            "acceptance_publication_replay_completion_digests",
            "completion_digest",
        ),
        "acceptance_changed_source_draft_update_completion": (
            "acceptance_changed_source_draft_update_completion_digests",
            "completion_digest",
        ),
        "acceptance_gate_b4": ("acceptance_gate_b4_digests", "binding_digest"),
        "acceptance_human_review": (
            "acceptance_human_review_digests",
            "attestation_digest",
        ),
        "acceptance_cleanup": (
            "acceptance_cleanup_digests",
            "attestation_digest",
        ),
        "acceptance_reviewer_calibration": (
            "acceptance_reviewer_calibration_digests",
            "calibration_digest",
        ),
        "acceptance_gate": ("acceptance_gate_digests", "gate_digest"),
        "acceptance_report_root": (
            "acceptance_report_root_digests",
            "root_digest",
        ),
    }
    for fact in facts:
        target = mapping.get(fact.kind)
        if target is None:
            continue
        payload = _fact_payload(fact)
        nested = payload.get("value")
        if not isinstance(nested, dict) or type(nested.get(target[1])) is not str:
            raise OperationsIntegrityError("operations projection fact is malformed")
        fields[target[0]].append(str(nested[target[1]]))
    values: dict[str, object] = {
        "schema_version": "operations-state-projection-v1",
        **{name: tuple(sorted(digests)) for name, digests in fields.items()},
    }
    digest_values = dict(values)
    for field in (
        "acceptance_live_authority_digests",
        "acceptance_campaign_resume_locator_digests",
        "acceptance_budget_reservation_digests",
        "acceptance_fixed_candidate_admission_digests",
        "acceptance_semantic_request_reservation_digests",
        "acceptance_replay_evidence_digests",
    ):
        if not fields[field]:
            digest_values.pop(field)
    return OperationsStateProjectionV1(
        **values,
        projection_digest=sha256_digest(digest_values),
    )


def _export_digest(
    *,
    schema_fingerprint: str,
    facts: tuple[OperationsOwnedFactV1, ...],
    projection: OperationsStateProjectionV1,
) -> str:
    return sha256_digest(
        {
            "schema_version": "operations-owned-state-v1",
            "owner": "operations",
            "database_locator": "state/databases/operations.sqlite3",
            "schema_fingerprint": schema_fingerprint,
            "facts": tuple(fact.model_dump(mode="json", exclude_none=False) for fact in facts),
            "projection": projection.model_dump(mode="json", exclude_none=False),
        }
    )


class OperationsStateStore:
    """Exclusive serialized SQLite index over discovery-owned canonical facts."""

    def __init__(
        self,
        path: Path,
        *,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> None:
        if (
            not isinstance(path, Path)
            or not path.name
            or path.name.startswith(".")
            or path.parent == path
        ):
            raise ValueError("operations state requires one private regular filename")
        self.path = Path(os.path.abspath(os.fspath(path)))
        self._name = AnchoredDirectory.validate_child_name(self.path.name)
        self._lock_name = AnchoredDirectory.validate_child_name(f".{self._name}.lock")
        self._filesystem_seam = filesystem_seam
        self._parent: AnchoredDirectory | None = None
        self._lock_descriptor = -1
        self._connection: sqlite3.Connection | None = None
        self._durable_bytes: bytes | None = None
        self._poisoned = False
        self._thread_lock = threading.RLock()
        try:
            self._parent = AnchoredDirectory.open(
                self.path.parent,
                create=True,
                filesystem_seam=filesystem_seam,
            )
            self._acquire_lock()
            self._parent.recover_stale_temporary(self._name)
            raw = self._parent.read_bytes(
                self._name,
                max_bytes=MAX_OPERATIONS_DB_BYTES,
                missing_ok=True,
            )
            if raw is None:
                connection = self._new_connection()
                self._create_schema(connection)
                payload = self._serialize(connection)
                self._parent.atomic_write(
                    self._name,
                    payload,
                    max_bytes=MAX_OPERATIONS_DB_BYTES,
                    seam_prefix="operations_state_",
                )
                self._connection = connection
                self._durable_bytes = payload
            else:
                connection = self._new_connection()
                connection.deserialize(raw)
                connection.execute("PRAGMA foreign_keys = ON")
                self._verify_connection(connection)
                self._connection = connection
                self._durable_bytes = raw
        except Exception:
            self.close()
            raise

    @staticmethod
    def _new_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(
            ":memory:",
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _acquire_lock(self) -> None:
        assert self._parent is not None
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            descriptor = os.open(
                self._lock_name,
                flags,
                0o600,
                dir_fd=self._parent.descriptor,
            )
            metadata = os.fstat(descriptor)
            AnchoredDirectory._require_private_regular(metadata)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path_metadata = self._parent.stat_child(self._lock_name)
            if path_metadata is None or (
                metadata.st_dev,
                metadata.st_ino,
            ) != (
                path_metadata.st_dev,
                path_metadata.st_ino,
            ):
                raise OperationsIntegrityError("operations lock identity changed")
            self._lock_descriptor = descriptor
        except BlockingIOError:
            if "descriptor" in locals():
                os.close(descriptor)
            raise OperationsBusy("operations state is already locked") from None
        except Exception:
            if "descriptor" in locals():
                os.close(descriptor)
            raise

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in _schema_statements():
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {OPERATIONS_SCHEMA_VERSION}")
            connection.commit()
            OperationsStateStore._verify_connection(connection)
        except Exception:
            connection.rollback()
            connection.close()
            raise

    @staticmethod
    def _serialize(connection: sqlite3.Connection) -> bytes:
        try:
            payload = connection.serialize()
        except sqlite3.Error:
            raise OperationsStateError("operations state serialization failed") from None
        if type(payload) is not bytes or not payload or len(payload) > MAX_OPERATIONS_DB_BYTES:
            raise OperationsStateError("operations state snapshot is invalid")
        return payload

    @staticmethod
    def _verify_connection(connection: sqlite3.Connection) -> None:
        try:
            version = connection.execute("PRAGMA user_version").fetchone()
            if version is None or version[0] != OPERATIONS_SCHEMA_VERSION:
                raise OperationsIntegrityError("operations schema version mismatch")
            actual = {
                str(row["name"]): _normalize_sql(str(row["sql"]))
                for row in connection.execute(
                    """SELECT name, sql FROM sqlite_master
                       WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                       ORDER BY name"""
                ).fetchall()
            }
            if actual not in (
                _EXPECTED_SCHEMA,
                _PRE_REPLAY_EVIDENCE_EXPECTED_SCHEMA,
                _PRE_REQUEST_RESERVATION_EXPECTED_SCHEMA,
                _PRE_FIXED_ADMISSION_EXPECTED_SCHEMA,
                _PRE_BUDGET_EXPECTED_SCHEMA,
                _LEGACY_EXPECTED_SCHEMA,
            ):
                raise OperationsIntegrityError("operations schema fingerprint mismatch")
            integrity = tuple(
                str(row[0]) for row in connection.execute("PRAGMA integrity_check").fetchall()
            )
            if integrity != ("ok",):
                raise OperationsIntegrityError("operations integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise OperationsIntegrityError("operations foreign key check failed")
            OperationsStateStore._verify_rows(connection)
        except OperationsIntegrityError:
            raise
        except (sqlite3.Error, TypeError, ValueError):
            raise OperationsIntegrityError("operations verification failed") from None

    @staticmethod
    def _verify_rows(connection: sqlite3.Connection) -> None:
        run_rows = connection.execute("SELECT * FROM operations_runs ORDER BY run_id").fetchall()
        run_authorities: dict[str, str] = {}
        for row in run_rows:
            raw = _decoded_json(row["authority_json"])
            if not isinstance(raw, dict):
                raise OperationsIntegrityError("invalid operations run authority")
            if raw.get("schema_version") == _TEST_RUN_SCHEMA:
                expected = _test_run_payload(str(row["run_id"]))
                if raw != expected:
                    raise OperationsIntegrityError("invalid test run authority")
                authority_digest = str(expected["authority_digest"])
            else:
                authority = DiscoveryRunAuthorityV1.model_validate(raw, strict=True)
                if authority.run_id != row["run_id"]:
                    raise OperationsIntegrityError("run authority mismatch")
                authority_digest = authority.authority_digest
            if row["authority_digest"] != authority_digest or not _DIGEST_PATTERN.fullmatch(
                authority_digest
            ):
                raise OperationsIntegrityError("run authority digest mismatch")
            run_authorities[str(row["run_id"])] = authority_digest

        OperationsStateStore._verify_reservation_rows(
            connection,
            table="operations_discovery_reservations",
            maximum=DISCOVERY_MAX_CANDIDATES,
            model=DiscoveryReservationV1,
            run_authorities=run_authorities,
        )
        OperationsStateStore._verify_reservation_rows(
            connection,
            table="operations_semantic_reservations",
            maximum=DISCOVERY_MAX_SEMANTIC_CANDIDATES,
            model=SemanticReservationV1,
            run_authorities=run_authorities,
        )

        page_digests: set[str] = set()
        for row in connection.execute(
            "SELECT * FROM operations_search_pages ORDER BY run_id, query_ordinal, page"
        ).fetchall():
            page = SearchPageObservationV1.model_validate_json(row["observation_json"], strict=True)
            if (
                page.discovery_run_authority_digest != run_authorities.get(str(row["run_id"]))
                or page.observation_digest != row["observation_digest"]
                or page.query_ordinal != row["query_ordinal"]
                or page.page != row["page"]
            ):
                raise OperationsIntegrityError("search page authority mismatch")
            page_digests.add(page.observation_digest)

        for row in connection.execute(
            """SELECT * FROM operations_candidates
               ORDER BY run_id, query_ordinal, page, item_ordinal"""
        ).fetchall():
            candidate = DiscoveredCandidateV1.model_validate_json(
                row["candidate_json"], strict=True
            )
            if (
                candidate.discovery_run_authority_digest != run_authorities.get(str(row["run_id"]))
                or candidate.candidate_digest != row["candidate_digest"]
                or candidate.repository.repository_id != row["repository_id"]
                or candidate.source_page_digest != row["source_page_digest"]
                or candidate.source_page_digest not in page_digests
                or candidate.query_ordinal != row["query_ordinal"]
                or candidate.page != row["page"]
                or candidate.item_ordinal != row["item_ordinal"]
            ):
                raise OperationsIntegrityError("candidate observation mismatch")

        for row in connection.execute(
            "SELECT * FROM operations_candidate_terminals ORDER BY run_id, repository_id"
        ).fetchall():
            raw = _decoded_json(row["terminal_json"])
            if not isinstance(raw, dict):
                raise OperationsIntegrityError("invalid candidate terminal")
            if raw.get("schema_version") == _TEST_TERMINAL_SCHEMA:
                expected = {
                    "schema_version": _TEST_TERMINAL_SCHEMA,
                    "run_id": row["run_id"],
                    "repository_id": row["repository_id"],
                    "outcome": row["outcome"],
                }
                expected["terminal_digest"] = sha256_digest(expected)
                if raw != expected:
                    raise OperationsIntegrityError("invalid test candidate terminal")
                terminal_digest = str(expected["terminal_digest"])
            else:
                terminal = DiscoveryCandidateTerminalV1.model_validate(raw, strict=True)
                workflow_authorities = tuple(
                    str(item[0])
                    for item in connection.execute(
                        """SELECT workflow_authority_digest
                           FROM operations_workflow_terminals
                           WHERE run_id = ? AND repository_id = ?
                           ORDER BY workflow_authority_digest""",
                        (row["run_id"], row["repository_id"]),
                    ).fetchall()
                )
                if (
                    terminal.discovery_run_authority_digest
                    != run_authorities.get(str(row["run_id"]))
                    or terminal.repository_id != row["repository_id"]
                    or terminal.outcome != row["outcome"]
                    or terminal.semantic_reservation_digest != row["semantic_reservation_digest"]
                    or tuple(sorted(terminal.workflow_authority_digests)) != workflow_authorities
                ):
                    raise OperationsIntegrityError("candidate terminal mismatch")
                terminal_digest = terminal.terminal_digest
            if terminal_digest != row["terminal_digest"]:
                raise OperationsIntegrityError("candidate terminal digest mismatch")

        for row in connection.execute(
            """SELECT * FROM operations_semantic_attempts
               ORDER BY run_id, repository_id, workflow_authority_digest,
                        stage, attempt_no"""
        ).fetchall():
            raw = _decoded_json(row["attempt_json"])
            if not isinstance(raw, dict):
                raise OperationsIntegrityError("invalid semantic attempt")
            expected_fields = {
                "schema_version": "operations-semantic-attempt-v1",
                "run_id": row["run_id"],
                "repository_id": row["repository_id"],
                "workflow_authority_digest": row["workflow_authority_digest"],
                "stage": row["stage"],
                "attempt_no": row["attempt_no"],
                "status": row["status"],
                "recorded_at": raw.get("recorded_at"),
            }
            digest = sha256_digest(expected_fields)
            expected = {**expected_fields, "attempt_digest": digest}
            if raw != expected or row["attempt_digest"] != digest:
                raise OperationsIntegrityError("semantic attempt digest mismatch")

        for row in connection.execute(
            """SELECT * FROM operations_workflow_terminals
               ORDER BY run_id, repository_id, workflow_authority_digest"""
        ).fetchall():
            raw = _decoded_json(row["terminal_json"])
            if not isinstance(raw, dict):
                raise OperationsIntegrityError("invalid workflow terminal")
            expected_fields = {
                "schema_version": "operations-workflow-terminal-v1",
                "run_id": row["run_id"],
                "repository_id": row["repository_id"],
                "workflow_authority_digest": row["workflow_authority_digest"],
                "outcome": row["outcome"],
                "eligible_locator": row["eligible_locator"],
                "eligible_object_digest": row["eligible_object_digest"],
                "recorded_at": row["recorded_at"],
            }
            digest = sha256_digest(expected_fields)
            if (
                raw != {**expected_fields, "terminal_digest": digest}
                or row["terminal_digest"] != digest
            ):
                raise OperationsIntegrityError("workflow terminal mismatch")

        for row in connection.execute(
            "SELECT * FROM operations_run_summaries ORDER BY run_id"
        ).fetchall():
            summary = DiscoveryRunSummaryV1.model_validate_json(row["summary_json"], strict=True)
            run = connection.execute(
                "SELECT status FROM operations_runs WHERE run_id = ?",
                (row["run_id"],),
            ).fetchone()
            terminal_digests = tuple(
                str(item[0])
                for item in connection.execute(
                    """SELECT terminal_digest FROM operations_candidate_terminals
                       WHERE run_id = ? ORDER BY repository_id""",
                    (row["run_id"],),
                ).fetchall()
            )
            counts = OperationsStateStore._counts(connection, str(row["run_id"]))
            if (
                run is None
                or run["status"] != summary.status
                or summary.discovery_run_authority_digest != run_authorities.get(str(row["run_id"]))
                or summary.summary_digest != row["summary_digest"]
                or summary.selected_candidate_count != counts["discovery"]
                or summary.semantic_reservation_count != counts["semantic"]
                or summary.terminal_digests != terminal_digests
            ):
                raise OperationsIntegrityError("run summary projection mismatch")

        for run_id in run_authorities:
            statuses = connection.execute(
                "SELECT status FROM operations_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            summary_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM operations_run_summaries WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            if (
                statuses is None
                or (statuses["status"] not in {"running", "interrupted"} and summary_count != 1)
                or (statuses["status"] in {"running", "interrupted"} and summary_count != 0)
            ):
                raise OperationsIntegrityError("run status and summary disagree")

        acceptance_rows = connection.execute(
            """SELECT * FROM operations_acceptance_facts
               ORDER BY acceptance_run_id, fact_kind, fact_digest"""
        ).fetchall()
        for row in acceptance_rows:
            fact = _acceptance_row_fact(row)
            _validate_acceptance_references(
                connection,
                acceptance_run_id=str(row["acceptance_run_id"]),
                kind=str(row["fact_kind"]),
                fact=fact,
            )

    @staticmethod
    def _verify_reservation_rows(
        connection: sqlite3.Connection,
        *,
        table: str,
        maximum: int,
        model: type[DiscoveryReservationV1] | type[SemanticReservationV1],
        run_authorities: dict[str, str],
    ) -> None:
        rows = connection.execute(f"SELECT * FROM {table} ORDER BY run_id, ordinal").fetchall()
        by_run: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            by_run.setdefault(str(row["run_id"]), []).append(row)
        for run_id, run_rows in by_run.items():
            ordinals = tuple(int(row["ordinal"]) for row in run_rows)
            if len(run_rows) > maximum or ordinals != tuple(range(1, len(run_rows) + 1)):
                raise OperationsIntegrityError("reservation ordinals are not contiguous")
            for row in run_rows:
                raw = _decoded_json(row["reservation_json"])
                if not isinstance(raw, dict):
                    raise OperationsIntegrityError("invalid reservation JSON")
                if raw.get("schema_version") == _TEST_RESERVATION_SCHEMA:
                    expected = {
                        "schema_version": _TEST_RESERVATION_SCHEMA,
                        "kind": (
                            "discovery"
                            if table == "operations_discovery_reservations"
                            else "semantic"
                        ),
                        "run_id": run_id,
                        "repository_id": row["repository_id"],
                        "ordinal": row["ordinal"],
                    }
                    expected["reservation_digest"] = sha256_digest(expected)
                    if raw != expected:
                        raise OperationsIntegrityError("invalid test reservation")
                    digest = str(expected["reservation_digest"])
                else:
                    reservation = model.model_validate(raw, strict=True)
                    if (
                        reservation.discovery_run_authority_digest != run_authorities.get(run_id)
                        or reservation.repository_id != row["repository_id"]
                        or reservation.ordinal != row["ordinal"]
                    ):
                        raise OperationsIntegrityError("reservation authority mismatch")
                    digest = reservation.reservation_digest
                if digest != row["reservation_digest"]:
                    raise OperationsIntegrityError("reservation digest mismatch")

    def _snapshot_transaction(
        self,
        mutation: Callable[[sqlite3.Connection], _T],
    ) -> _T:
        with self._thread_lock:
            if (
                self._poisoned
                or self._durable_bytes is None
                or self._connection is None
                or self._parent is None
            ):
                raise OperationsStateError("operations state is unavailable")
            candidate = self._new_connection()
            try:
                candidate.deserialize(self._durable_bytes)
                candidate.execute("PRAGMA foreign_keys = ON")
                candidate.execute("BEGIN IMMEDIATE")
                result = mutation(candidate)
                candidate.commit()
                self._verify_connection(candidate)
                payload = self._serialize(candidate)
            except Exception:
                try:
                    candidate.rollback()
                except sqlite3.Error:
                    pass
                candidate.close()
                raise
            previous = self._durable_bytes
            try:
                if self._filesystem_seam is not None:
                    self._filesystem_seam("before_operations_state_persist")
                self._parent.atomic_write(
                    self._name,
                    payload,
                    max_bytes=MAX_OPERATIONS_DB_BYTES,
                    restore_bytes=previous,
                    seam_prefix="operations_state_",
                )
            except (DurableWriteError, OSError):
                candidate.close()
                self._poisoned = True
                self._connection.close()
                self._connection = None
                raise OperationsStateError("operations state persistence is uncertain") from None
            current = self._connection
            self._connection = candidate
            self._durable_bytes = payload
            current.close()
            return result

    @staticmethod
    def _ensure_test_run(connection: sqlite3.Connection, run_id: str) -> None:
        if type(run_id) is not str or not run_id or len(run_id) > 256:
            raise ValueError("invalid test run ID")
        existing = connection.execute(
            "SELECT authority_json FROM operations_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        expected = _test_run_payload(run_id)
        if existing is None:
            connection.execute(
                """INSERT INTO operations_runs
                   (run_id, authority_digest, authority_json, status, created_at)
                   VALUES (?, ?, ?, 'running', '2026-07-27T00:00:00.000000Z')""",
                (run_id, expected["authority_digest"], _json_text(expected)),
            )
        elif _decoded_json(existing["authority_json"]) != expected:
            raise OperationsIntegrityError("test run authority mismatch")

    def upgrade_acceptance_schema(self) -> None:
        """Explicitly widen only the acceptance fact-kind constraint."""

        def mutate(connection: sqlite3.Connection) -> None:
            actual = {
                str(row["name"]): _normalize_sql(str(row["sql"]))
                for row in connection.execute(
                    """SELECT name, sql FROM sqlite_master
                       WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                       ORDER BY name"""
                ).fetchall()
            }
            if actual == _EXPECTED_SCHEMA:
                return
            if actual not in (
                _PRE_REPLAY_EVIDENCE_EXPECTED_SCHEMA,
                _PRE_REQUEST_RESERVATION_EXPECTED_SCHEMA,
                _PRE_FIXED_ADMISSION_EXPECTED_SCHEMA,
                _PRE_BUDGET_EXPECTED_SCHEMA,
                _LEGACY_EXPECTED_SCHEMA,
            ):
                raise OperationsIntegrityError(
                    "operations schema cannot be upgraded"
                )
            connection.execute(
                """ALTER TABLE operations_acceptance_facts
                   RENAME TO operations_acceptance_facts_previous"""
            )
            statement = next(
                item
                for item in _schema_statements()
                if item.lstrip().startswith(
                    "CREATE TABLE operations_acceptance_facts"
                )
            )
            connection.execute(statement)
            connection.execute(
                """INSERT INTO operations_acceptance_facts
                   (fact_digest, acceptance_run_id, fact_kind, schema_version,
                    recorded_identity, fact_json)
                   SELECT fact_digest, acceptance_run_id, fact_kind,
                          schema_version, recorded_identity, fact_json
                   FROM operations_acceptance_facts_previous"""
            )
            connection.execute("DROP TABLE operations_acceptance_facts_previous")

        self._snapshot_transaction(mutate)

    def create_run(
        self,
        authority: DiscoveryRunAuthorityV1,
        created_at: str,
    ) -> DiscoveryRunAuthorityV1:
        if type(authority) is not DiscoveryRunAuthorityV1:
            raise TypeError("invalid discovery run authority")

        def mutate(connection: sqlite3.Connection) -> DiscoveryRunAuthorityV1:
            existing = connection.execute(
                "SELECT * FROM operations_runs WHERE run_id = ?",
                (authority.run_id,),
            ).fetchone()
            if existing is not None:
                if existing["authority_digest"] != authority.authority_digest or existing[
                    "authority_json"
                ] != _json_text(authority):
                    raise OperationsIntegrityError("run identity conflict")
                return authority
            connection.execute(
                """INSERT INTO operations_runs
                   (run_id, authority_digest, authority_json, status, created_at)
                   VALUES (?, ?, ?, 'running', ?)""",
                (
                    authority.run_id,
                    authority.authority_digest,
                    _json_text(authority),
                    created_at,
                ),
            )
            return authority

        return self._snapshot_transaction(mutate)

    def find_run_authority_digest(self, run_id: str) -> str | None:
        """Return one existing run authority without creating mutable state."""

        if type(run_id) is not str or not run_id:
            raise ValueError("invalid discovery run id")
        with self._thread_lock:
            if self._connection is None:
                raise OperationsIntegrityError("operations state is closed")
            row = self._connection.execute(
                "SELECT authority_digest FROM operations_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return None if row is None else str(row["authority_digest"])

    def record_search_page(
        self,
        run_id: str,
        page: SearchPageObservationV1,
        candidates: tuple[DiscoveredCandidateV1, ...],
    ) -> SearchPageObservationV1:
        if type(page) is not SearchPageObservationV1 or type(candidates) is not tuple:
            raise TypeError("invalid discovery page")

        def mutate(connection: sqlite3.Connection) -> SearchPageObservationV1:
            authority = self._run_authority_digest(connection, run_id)
            if page.discovery_run_authority_digest != authority:
                raise OperationsIntegrityError("page authority mismatch")
            existing = connection.execute(
                """SELECT observation_json FROM operations_search_pages
                   WHERE run_id = ? AND query_ordinal = ? AND page = ?""",
                (run_id, page.query_ordinal, page.page),
            ).fetchone()
            if existing is not None:
                if existing["observation_json"] != _json_text(page):
                    raise OperationsIntegrityError("search page conflict")
                return page
            connection.execute(
                """INSERT INTO operations_search_pages
                   (observation_digest, run_id, query_ordinal, page, observation_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    page.observation_digest,
                    run_id,
                    page.query_ordinal,
                    page.page,
                    _json_text(page),
                ),
            )
            if len(candidates) != page.item_count:
                raise OperationsIntegrityError("page candidate count mismatch")
            for candidate in candidates:
                if (
                    type(candidate) is not DiscoveredCandidateV1
                    or candidate.discovery_run_authority_digest != authority
                    or candidate.source_page_digest != page.observation_digest
                    or candidate.query_ordinal != page.query_ordinal
                    or candidate.page != page.page
                ):
                    raise OperationsIntegrityError("candidate page authority mismatch")
                connection.execute(
                    """INSERT INTO operations_candidates
                       (candidate_digest, run_id, repository_id, source_page_digest,
                        query_ordinal, page, item_ordinal, candidate_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate.candidate_digest,
                        run_id,
                        candidate.repository.repository_id,
                        candidate.source_page_digest,
                        candidate.query_ordinal,
                        candidate.page,
                        candidate.item_ordinal,
                        _json_text(candidate),
                    ),
                )
            return page

        return self._snapshot_transaction(mutate)

    @staticmethod
    def _run_authority_digest(
        connection: sqlite3.Connection,
        run_id: str,
    ) -> str:
        row = connection.execute(
            "SELECT authority_digest FROM operations_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise OperationsIntegrityError("unknown discovery run")
        return str(row["authority_digest"])

    def reserve_discovery_candidate(
        self,
        run_id: str,
        candidate: DiscoveredCandidateV1,
        reserved_at: str,
    ) -> DiscoveryReservationV1:
        if type(candidate) is not DiscoveredCandidateV1:
            raise TypeError("invalid discovery candidate")

        def mutate(connection: sqlite3.Connection) -> DiscoveryReservationV1:
            authority = self._run_authority_digest(connection, run_id)
            existing = connection.execute(
                """SELECT reservation_json
                   FROM operations_discovery_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, candidate.repository.repository_id),
            ).fetchone()
            if existing is not None:
                return DiscoveryReservationV1.model_validate_json(
                    existing["reservation_json"], strict=True
                )
            count = int(
                connection.execute(
                    """SELECT COUNT(*) FROM operations_discovery_reservations
                       WHERE run_id = ?""",
                    (run_id,),
                ).fetchone()[0]
            )
            ordinal = count + 1
            if count >= DISCOVERY_MAX_CANDIDATES:
                raise BudgetExhausted("discovery candidate budget exhausted")
            if (
                candidate.discovery_run_authority_digest != authority
                or candidate.dedup_disposition != "first_seen"
                or candidate.discovery_ordinal != ordinal
            ):
                raise OperationsIntegrityError("discovery reservation is not contiguous")
            stored = connection.execute(
                """SELECT candidate_digest FROM operations_candidates
                   WHERE candidate_digest = ? AND run_id = ?""",
                (candidate.candidate_digest, run_id),
            ).fetchone()
            if stored is None:
                raise OperationsIntegrityError("candidate observation is missing")
            values = {
                "schema_version": "discovery-reservation-v1",
                "discovery_run_authority_digest": authority,
                "repository_id": candidate.repository.repository_id,
                "ordinal": ordinal,
                "candidate_digest": candidate.candidate_digest,
                "reserved_at": reserved_at,
            }
            reservation = DiscoveryReservationV1(
                **values,
                reservation_digest=sha256_digest(values),
            )
            connection.execute(
                """INSERT INTO operations_discovery_reservations
                   (reservation_digest, run_id, repository_id, ordinal,
                    candidate_digest, reservation_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    reservation.reservation_digest,
                    run_id,
                    reservation.repository_id,
                    reservation.ordinal,
                    reservation.candidate_digest,
                    _json_text(reservation),
                ),
            )
            return reservation

        return self._snapshot_transaction(mutate)

    def reserve_acceptance_semantic_candidate(
        self,
        run_id: str,
        admission: AcceptanceFixedCandidateAdmissionV1,
        phase2_run_authority_digest: str,
        reserved_at: str,
    ) -> SemanticReservationV1:
        """Reserve a locked acceptance candidate without a Search-owned row."""

        if type(admission) is not AcceptanceFixedCandidateAdmissionV1:
            raise TypeError("invalid fixed acceptance admission")

        def mutate(connection: sqlite3.Connection) -> SemanticReservationV1:
            authority = self._run_authority_digest(connection, run_id)
            existing = connection.execute(
                """SELECT reservation_json
                   FROM operations_semantic_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, admission.repository_id),
            ).fetchone()
            if existing is not None:
                reservation = SemanticReservationV1.model_validate_json(
                    existing["reservation_json"], strict=True
                )
                if (
                    reservation.discovery_reservation_digest
                    != admission.admission_digest
                    or reservation.phase2_run_authority_digest
                    != phase2_run_authority_digest
                ):
                    raise OperationsIntegrityError(
                        "fixed acceptance semantic reservation conflict"
                    )
                return reservation
            count = int(
                connection.execute(
                    """SELECT COUNT(*) FROM operations_semantic_reservations
                       WHERE run_id = ?""",
                    (run_id,),
                ).fetchone()[0]
            )
            if count >= DISCOVERY_MAX_SEMANTIC_CANDIDATES:
                raise BudgetExhausted("semantic candidate budget exhausted")
            values = {
                "schema_version": "semantic-reservation-v1",
                "discovery_run_authority_digest": authority,
                "repository_id": admission.repository_id,
                "ordinal": count + 1,
                "discovery_reservation_digest": admission.admission_digest,
                "phase2_run_authority_digest": phase2_run_authority_digest,
                "reserved_at": reserved_at,
            }
            reservation = SemanticReservationV1(
                **values,
                reservation_digest=sha256_digest(values),
            )
            connection.execute(
                """INSERT INTO operations_semantic_reservations
                   (reservation_digest, run_id, repository_id, ordinal,
                    discovery_reservation_digest, phase2_run_authority_digest,
                    reservation_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    reservation.reservation_digest,
                    run_id,
                    admission.repository_id,
                    reservation.ordinal,
                    reservation.discovery_reservation_digest,
                    reservation.phase2_run_authority_digest,
                    _json_text(reservation),
                ),
            )
            return reservation

        return self._snapshot_transaction(mutate)

    def reserve_semantic_candidate(
        self,
        run_id: str,
        repository_id: int,
        phase2_run_authority_digest: str,
        reserved_at: str,
    ) -> SemanticReservationV1:
        def mutate(connection: sqlite3.Connection) -> SemanticReservationV1:
            authority = self._run_authority_digest(connection, run_id)
            existing = connection.execute(
                """SELECT reservation_json
                   FROM operations_semantic_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if existing is not None:
                return SemanticReservationV1.model_validate_json(
                    existing["reservation_json"], strict=True
                )
            discovery = connection.execute(
                """SELECT reservation_digest
                   FROM operations_discovery_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if discovery is None:
                raise OperationsIntegrityError("discovery reservation is missing")
            count = int(
                connection.execute(
                    """SELECT COUNT(*) FROM operations_semantic_reservations
                       WHERE run_id = ?""",
                    (run_id,),
                ).fetchone()[0]
            )
            if count >= DISCOVERY_MAX_SEMANTIC_CANDIDATES:
                raise BudgetExhausted("semantic candidate budget exhausted")
            values = {
                "schema_version": "semantic-reservation-v1",
                "discovery_run_authority_digest": authority,
                "repository_id": repository_id,
                "ordinal": count + 1,
                "discovery_reservation_digest": discovery["reservation_digest"],
                "phase2_run_authority_digest": phase2_run_authority_digest,
                "reserved_at": reserved_at,
            }
            reservation = SemanticReservationV1(
                **values,
                reservation_digest=sha256_digest(values),
            )
            connection.execute(
                """INSERT INTO operations_semantic_reservations
                   (reservation_digest, run_id, repository_id, ordinal,
                    discovery_reservation_digest, phase2_run_authority_digest,
                    reservation_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    reservation.reservation_digest,
                    run_id,
                    repository_id,
                    reservation.ordinal,
                    reservation.discovery_reservation_digest,
                    reservation.phase2_run_authority_digest,
                    _json_text(reservation),
                ),
            )
            return reservation

        return self._snapshot_transaction(mutate)

    def record_candidate_terminal(
        self,
        run_id: str,
        terminal: DiscoveryCandidateTerminalV1,
    ) -> DiscoveryCandidateTerminalV1:
        if type(terminal) is not DiscoveryCandidateTerminalV1:
            raise TypeError("invalid candidate terminal")

        def mutate(connection: sqlite3.Connection) -> DiscoveryCandidateTerminalV1:
            authority = self._run_authority_digest(connection, run_id)
            if terminal.discovery_run_authority_digest != authority:
                raise OperationsIntegrityError("terminal authority mismatch")
            existing = connection.execute(
                """SELECT terminal_json FROM operations_candidate_terminals
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, terminal.repository_id),
            ).fetchone()
            if existing is not None:
                if existing["terminal_json"] != _json_text(terminal):
                    raise OperationsIntegrityError("candidate terminal conflict")
                return terminal
            if terminal.semantic_reservation_digest is not None:
                reservation = connection.execute(
                    """SELECT reservation_digest
                       FROM operations_semantic_reservations
                       WHERE run_id = ? AND repository_id = ?""",
                    (run_id, terminal.repository_id),
                ).fetchone()
                if (
                    reservation is None
                    or reservation["reservation_digest"] != terminal.semantic_reservation_digest
                ):
                    raise OperationsIntegrityError("terminal reservation mismatch")
            workflow_authorities = tuple(
                str(item[0])
                for item in connection.execute(
                    """SELECT workflow_authority_digest
                       FROM operations_workflow_terminals
                       WHERE run_id = ? AND repository_id = ?
                       ORDER BY workflow_authority_digest""",
                    (run_id, terminal.repository_id),
                ).fetchall()
            )
            if tuple(sorted(terminal.workflow_authority_digests)) != workflow_authorities:
                raise OperationsIntegrityError("candidate terminal workflow set mismatch")
            connection.execute(
                """INSERT INTO operations_candidate_terminals
                   (terminal_digest, run_id, repository_id,
                    semantic_reservation_digest, outcome, terminal_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    terminal.terminal_digest,
                    run_id,
                    terminal.repository_id,
                    terminal.semantic_reservation_digest,
                    terminal.outcome,
                    _json_text(terminal),
                ),
            )
            return terminal

        return self._snapshot_transaction(mutate)

    def record_workflow_terminal(
        self,
        *,
        run_id: str,
        repository_id: int,
        workflow_authority_digest: str,
        outcome: Literal[
            "qualification_rejected",
            "validation_rejected",
            "review_rejected",
            "completed_reuse",
            "eligible_local_candidate",
            "semantic_outcome_unknown",
            "permanent_failure",
        ],
        eligible_locator: str | None,
        eligible_object_digest: str | None,
        recorded_at: str,
    ) -> WorkflowTerminalRecord:
        eligible = outcome == "eligible_local_candidate"
        if (
            type(repository_id) is not int
            or repository_id <= 0
            or _DIGEST_PATTERN.fullmatch(workflow_authority_digest) is None
            or _TIMESTAMP_PATTERN.fullmatch(recorded_at) is None
            or (
                eligible
                and (
                    type(eligible_locator) is not str
                    or _STATE_OBJECT_LOCATOR.fullmatch(eligible_locator) is None
                    or _DIGEST_PATTERN.fullmatch(eligible_object_digest or "") is None
                    or not eligible_locator.endswith(
                        eligible_object_digest.removeprefix("sha256:") + ".json"
                    )
                )
            )
            or (
                not eligible
                and (eligible_locator is not None or eligible_object_digest is not None)
            )
        ):
            raise ValueError("invalid workflow terminal")

        def mutate(connection: sqlite3.Connection) -> WorkflowTerminalRecord:
            if (
                connection.execute(
                    """SELECT 1 FROM operations_discovery_reservations
                       WHERE run_id = ? AND repository_id = ?""",
                    (run_id, repository_id),
                ).fetchone()
                is None
            ):
                raise OperationsIntegrityError("workflow terminal discovery reservation is missing")
            values: dict[str, object] = {
                "schema_version": "operations-workflow-terminal-v1",
                "run_id": run_id,
                "repository_id": repository_id,
                "workflow_authority_digest": workflow_authority_digest,
                "outcome": outcome,
                "eligible_locator": eligible_locator,
                "eligible_object_digest": eligible_object_digest,
                "recorded_at": recorded_at,
            }
            values["terminal_digest"] = sha256_digest(values)
            existing = connection.execute(
                """SELECT terminal_json FROM operations_workflow_terminals
                   WHERE run_id = ? AND repository_id = ?
                     AND workflow_authority_digest = ?""",
                (run_id, repository_id, workflow_authority_digest),
            ).fetchone()
            payload = _json_text(values)
            if existing is not None:
                if existing["terminal_json"] != payload:
                    raise OperationsIntegrityError("workflow terminal conflict")
            else:
                connection.execute(
                    """INSERT INTO operations_workflow_terminals
                       (terminal_digest, run_id, repository_id,
                        workflow_authority_digest, outcome, eligible_locator,
                        eligible_object_digest, recorded_at, terminal_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        values["terminal_digest"],
                        run_id,
                        repository_id,
                        workflow_authority_digest,
                        outcome,
                        eligible_locator,
                        eligible_object_digest,
                        recorded_at,
                        payload,
                    ),
                )
            return WorkflowTerminalRecord(
                run_id=run_id,
                repository_id=repository_id,
                workflow_authority_digest=workflow_authority_digest,
                outcome=outcome,
                eligible_locator=eligible_locator,
                eligible_object_digest=eligible_object_digest,
                recorded_at=recorded_at,
                terminal_digest=str(values["terminal_digest"]),
            )

        return self._snapshot_transaction(mutate)

    def record_acceptance_workflow_terminal(
        self,
        *,
        acceptance_run_id: str,
        fixed_candidate_admission_digest: str,
        semantic_reservation_digest: str,
        run_id: str,
        repository_id: int,
        workflow_authority_digest: str,
        outcome: Literal[
            "qualification_rejected",
            "validation_rejected",
            "review_rejected",
            "completed_reuse",
            "eligible_local_candidate",
            "semantic_outcome_unknown",
            "permanent_failure",
        ],
        eligible_locator: str | None,
        eligible_object_digest: str | None,
        recorded_at: str,
    ) -> WorkflowTerminalRecord:
        """Write a fixed-candidate terminal without inventing Search lineage."""

        eligible = outcome == "eligible_local_candidate"
        if (
            type(repository_id) is not int
            or repository_id <= 0
            or _DIGEST_PATTERN.fullmatch(fixed_candidate_admission_digest)
            is None
            or _DIGEST_PATTERN.fullmatch(semantic_reservation_digest) is None
            or _DIGEST_PATTERN.fullmatch(workflow_authority_digest) is None
            or _TIMESTAMP_PATTERN.fullmatch(recorded_at) is None
            or (
                eligible
                and (
                    type(eligible_locator) is not str
                    or _STATE_OBJECT_LOCATOR.fullmatch(eligible_locator)
                    is None
                    or _DIGEST_PATTERN.fullmatch(
                        eligible_object_digest or ""
                    )
                    is None
                    or not eligible_locator.endswith(
                        eligible_object_digest.removeprefix("sha256:")
                        + ".json"
                    )
                )
            )
            or (
                not eligible
                and (
                    eligible_locator is not None
                    or eligible_object_digest is not None
                )
            )
        ):
            raise ValueError("invalid acceptance workflow terminal")

        def mutate(connection: sqlite3.Connection) -> WorkflowTerminalRecord:
            admission = _acceptance_fact_by_digest(
                connection,
                acceptance_run_id=acceptance_run_id,
                kind="acceptance_fixed_candidate_admission",
                digest=fixed_candidate_admission_digest,
            )
            assert isinstance(admission, AcceptanceFixedCandidateAdmissionV1)
            reservation_row = connection.execute(
                """SELECT reservation_json
                   FROM operations_semantic_reservations
                   WHERE reservation_digest = ? AND run_id = ?
                     AND repository_id = ?""",
                (semantic_reservation_digest, run_id, repository_id),
            ).fetchone()
            if reservation_row is None:
                raise OperationsIntegrityError(
                    "acceptance terminal semantic reservation is missing"
                )
            reservation = SemanticReservationV1.model_validate_json(
                reservation_row["reservation_json"],
                strict=True,
            )
            if (
                admission.repository_id != repository_id
                or reservation.discovery_reservation_digest
                != fixed_candidate_admission_digest
            ):
                raise OperationsIntegrityError(
                    "acceptance terminal admission binding mismatch"
                )
            values: dict[str, object] = {
                "schema_version": "operations-workflow-terminal-v1",
                "run_id": run_id,
                "repository_id": repository_id,
                "workflow_authority_digest": workflow_authority_digest,
                "outcome": outcome,
                "eligible_locator": eligible_locator,
                "eligible_object_digest": eligible_object_digest,
                "recorded_at": recorded_at,
            }
            values["terminal_digest"] = sha256_digest(values)
            existing = connection.execute(
                """SELECT terminal_json FROM operations_workflow_terminals
                   WHERE run_id = ? AND repository_id = ?
                     AND workflow_authority_digest = ?""",
                (run_id, repository_id, workflow_authority_digest),
            ).fetchone()
            payload = _json_text(values)
            if existing is not None:
                if existing["terminal_json"] != payload:
                    raise OperationsIntegrityError(
                        "workflow terminal conflict"
                    )
            else:
                connection.execute(
                    """INSERT INTO operations_workflow_terminals
                       (terminal_digest, run_id, repository_id,
                        workflow_authority_digest, outcome, eligible_locator,
                        eligible_object_digest, recorded_at, terminal_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        values["terminal_digest"],
                        run_id,
                        repository_id,
                        workflow_authority_digest,
                        outcome,
                        eligible_locator,
                        eligible_object_digest,
                        recorded_at,
                        payload,
                    ),
                )
            return WorkflowTerminalRecord(
                run_id=run_id,
                repository_id=repository_id,
                workflow_authority_digest=workflow_authority_digest,
                outcome=outcome,
                eligible_locator=eligible_locator,
                eligible_object_digest=eligible_object_digest,
                recorded_at=recorded_at,
                terminal_digest=str(values["terminal_digest"]),
            )

        return self._snapshot_transaction(mutate)

    def snapshot_run(self, run_id: str) -> DiscoveryRunSnapshot:
        """Return the complete typed persisted prefix for one discovery run."""

        with self._thread_lock:
            connection = self._connection
            if connection is None:
                raise OperationsIntegrityError("operations state is closed")
            if (
                connection.execute(
                    "SELECT 1 FROM operations_runs WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
                is None
            ):
                raise OperationsIntegrityError("discovery run is missing")

            def models(table: str, column: str, model: object, order: str):
                return tuple(
                    model.model_validate_json(row[column], strict=True)
                    for row in connection.execute(
                        f"SELECT {column} FROM {table} WHERE run_id = ? ORDER BY {order}",
                        (run_id,),
                    ).fetchall()
                )

            attempts: list[SemanticAttemptRecord] = []
            for row in connection.execute(
                """SELECT * FROM operations_semantic_attempts
                   WHERE run_id = ?
                   ORDER BY repository_id, workflow_authority_digest,
                            stage, attempt_no""",
                (run_id,),
            ).fetchall():
                raw = _decoded_json(row["attempt_json"])
                assert isinstance(raw, dict)
                attempts.append(
                    SemanticAttemptRecord(
                        run_id=run_id,
                        repository_id=int(row["repository_id"]),
                        workflow_authority_digest=str(row["workflow_authority_digest"]),
                        stage=str(row["stage"]),  # type: ignore[arg-type]
                        attempt_no=int(row["attempt_no"]),
                        status=str(row["status"]),  # type: ignore[arg-type]
                        recorded_at=str(raw["recorded_at"]),
                        attempt_digest=str(row["attempt_digest"]),
                    )
                )
            workflows: list[WorkflowTerminalRecord] = []
            for row in connection.execute(
                """SELECT * FROM operations_workflow_terminals
                   WHERE run_id = ?
                   ORDER BY repository_id, workflow_authority_digest""",
                (run_id,),
            ).fetchall():
                workflows.append(
                    WorkflowTerminalRecord(
                        run_id=run_id,
                        repository_id=int(row["repository_id"]),
                        workflow_authority_digest=str(row["workflow_authority_digest"]),
                        outcome=str(row["outcome"]),  # type: ignore[arg-type]
                        eligible_locator=row["eligible_locator"],
                        eligible_object_digest=row["eligible_object_digest"],
                        recorded_at=str(row["recorded_at"]),
                        terminal_digest=str(row["terminal_digest"]),
                    )
                )
            summary_row = connection.execute(
                """SELECT summary_json FROM operations_run_summaries
                   WHERE run_id = ?""",
                (run_id,),
            ).fetchone()
            return DiscoveryRunSnapshot(
                search_pages=models(
                    "operations_search_pages",
                    "observation_json",
                    SearchPageObservationV1,
                    "query_ordinal, page",
                ),
                candidates=models(
                    "operations_candidates",
                    "candidate_json",
                    DiscoveredCandidateV1,
                    "query_ordinal, page, item_ordinal",
                ),
                discovery_reservations=models(
                    "operations_discovery_reservations",
                    "reservation_json",
                    DiscoveryReservationV1,
                    "ordinal",
                ),
                semantic_reservations=models(
                    "operations_semantic_reservations",
                    "reservation_json",
                    SemanticReservationV1,
                    "ordinal",
                ),
                semantic_attempts=tuple(attempts),
                workflow_terminals=tuple(workflows),
                candidate_terminals=models(
                    "operations_candidate_terminals",
                    "terminal_json",
                    DiscoveryCandidateTerminalV1,
                    "repository_id",
                ),
                summary=(
                    None
                    if summary_row is None
                    else DiscoveryRunSummaryV1.model_validate_json(
                        summary_row["summary_json"], strict=True
                    )
                ),
            )

    def record_acceptance_fact(
        self,
        acceptance_run_id: str,
        kind: _AcceptanceFactKind,
        fact: _AcceptanceFactModel,
    ) -> AcceptanceFactRecord:
        """Append one exact typed acceptance fact or return its exact duplicate."""

        model = ACCEPTANCE_FACT_MODELS.get(kind)
        if (
            model is None
            or type(fact) is not model
            or type(acceptance_run_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}", acceptance_run_id) is None
        ):
            raise TypeError("invalid typed acceptance fact")
        raw = fact.model_dump(mode="json", exclude_none=False)
        validated = _validate_acceptance_model(kind, raw)
        _acceptance_run_binding(acceptance_run_id, validated)
        fact_digest = _acceptance_fact_digest(kind, validated)
        fact_json = _json_text(raw)
        schema_version = str(getattr(validated, "schema_version"))
        recorded_identity = _acceptance_recorded_identity(acceptance_run_id, kind, validated)

        def record(value: _AcceptanceFactModel) -> AcceptanceFactRecord:
            return AcceptanceFactRecord(
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact_digest=fact_digest,
                fact=value,
            )

        def mutate(connection: sqlite3.Connection) -> AcceptanceFactRecord:
            digest_row = connection.execute(
                """SELECT * FROM operations_acceptance_facts
                   WHERE fact_digest = ?""",
                (fact_digest,),
            ).fetchone()
            if digest_row is not None:
                if (
                    digest_row["acceptance_run_id"] != acceptance_run_id
                    or digest_row["fact_kind"] != kind
                    or digest_row["schema_version"] != schema_version
                    or digest_row["recorded_identity"] != recorded_identity
                    or digest_row["fact_json"] != fact_json
                ):
                    raise OperationsIntegrityError(
                        "acceptance fact digest was reused across authority"
                    )
                return record(_acceptance_row_fact(digest_row))
            identity_row = connection.execute(
                """SELECT * FROM operations_acceptance_facts
                   WHERE acceptance_run_id = ? AND fact_kind = ?
                     AND recorded_identity = ?""",
                (acceptance_run_id, kind, recorded_identity),
            ).fetchone()
            if identity_row is not None:
                if kind in {
                    "acceptance_budget_reservation",
                    "acceptance_fixed_candidate_admission",
                }:
                    existing = _acceptance_row_fact(identity_row)
                    timestamp_field = (
                        "reserved_at"
                        if kind == "acceptance_budget_reservation"
                        else "admitted_at"
                    )
                    digest_field = (
                        "reservation_digest"
                        if kind == "acceptance_budget_reservation"
                        else "admission_digest"
                    )
                    if existing.model_dump(
                        mode="json",
                        exclude={timestamp_field, digest_field},
                    ) != validated.model_dump(
                        mode="json",
                        exclude={timestamp_field, digest_field},
                    ):
                        raise OperationsIntegrityError(
                            "acceptance fact natural identity conflict"
                        )
                    return AcceptanceFactRecord(
                        acceptance_run_id=acceptance_run_id,
                        kind=kind,
                        fact_digest=str(identity_row["fact_digest"]),
                        fact=existing,
                    )
                raise OperationsIntegrityError("acceptance fact natural identity conflict")
            _validate_acceptance_references(
                connection,
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact=validated,
            )
            connection.execute(
                """INSERT INTO operations_acceptance_facts
                   (fact_digest, acceptance_run_id, fact_kind, schema_version,
                    recorded_identity, fact_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    fact_digest,
                    acceptance_run_id,
                    kind,
                    schema_version,
                    recorded_identity,
                    fact_json,
                ),
            )
            return record(validated)

        return self._snapshot_transaction(mutate)

    def acceptance_snapshot(
        self,
        acceptance_run_id: str,
    ) -> AcceptanceRunSnapshot:
        """Return one run's exact typed acceptance facts in canonical order."""

        if (
            type(acceptance_run_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}", acceptance_run_id) is None
        ):
            raise ValueError("invalid acceptance run ID")
        with self._thread_lock:
            if self._connection is None or self._poisoned:
                raise OperationsStateError("operations state is unavailable")
            rows = self._connection.execute(
                """SELECT * FROM operations_acceptance_facts
                   WHERE acceptance_run_id = ?
                   ORDER BY fact_kind, fact_digest""",
                (acceptance_run_id,),
            ).fetchall()
            return AcceptanceRunSnapshot(
                acceptance_run_id=acceptance_run_id,
                facts=tuple(
                    AcceptanceFactRecord(
                        acceptance_run_id=acceptance_run_id,
                        kind=str(row["fact_kind"]),  # type: ignore[arg-type]
                        fact_digest=str(row["fact_digest"]),
                        fact=_acceptance_row_fact(row),
                    )
                    for row in rows
                ),
            )

    def reserve_acceptance_semantic_request(
        self,
        *,
        acceptance_run_id: str,
        fixed_candidate_admission_digest: str,
        repository_id: int,
        workflow_spec_authority_digest: str,
        stage: Literal["extractor", "generator", "reviewer"],
        attempt_no: int,
        reserved_at: str,
    ) -> AcceptanceSemanticRequestReservationV1:
        """Atomically consume one of the campaign's twenty provider requests."""

        def mutate(
            connection: sqlite3.Connection,
        ) -> AcceptanceSemanticRequestReservationV1:
            rows = connection.execute(
                """SELECT * FROM operations_acceptance_facts
                   WHERE acceptance_run_id = ?
                     AND fact_kind = 'acceptance_semantic_request_reservation'
                   ORDER BY fact_digest""",
                (acceptance_run_id,),
            ).fetchall()
            reservations = tuple(
                _acceptance_row_fact(row) for row in rows
            )
            if any(
                not isinstance(
                    item,
                    AcceptanceSemanticRequestReservationV1,
                )
                for item in reservations
            ):
                raise OperationsIntegrityError(
                    "semantic request ledger type mismatch"
                )
            existing = next(
                (
                    item
                    for item in reservations
                    if (
                        item.fixed_candidate_admission_digest,
                        item.workflow_spec_authority_digest,
                        item.stage,
                        item.attempt_no,
                    )
                    == (
                        fixed_candidate_admission_digest,
                        workflow_spec_authority_digest,
                        stage,
                        attempt_no,
                    )
                ),
                None,
            )
            if existing is not None:
                return existing
            if len(reservations) >= 20:
                raise BudgetExhausted(
                    "acceptance semantic request budget exhausted"
                )
            reservation = AcceptanceSemanticRequestReservationV1(
                schema_version="acceptance-semantic-request-reservation-v1",
                acceptance_run_id=acceptance_run_id,
                fixed_candidate_admission_digest=(
                    fixed_candidate_admission_digest
                ),
                repository_id=repository_id,
                workflow_spec_authority_digest=(
                    workflow_spec_authority_digest
                ),
                stage=stage,
                attempt_no=attempt_no,
                request_ordinal=len(reservations) + 1,
                reserved_at=reserved_at,
            )
            _validate_acceptance_references(
                connection,
                acceptance_run_id=acceptance_run_id,
                kind="acceptance_semantic_request_reservation",
                fact=reservation,
            )
            raw = reservation.model_dump(mode="json", exclude_none=False)
            connection.execute(
                """INSERT INTO operations_acceptance_facts
                   (fact_digest, acceptance_run_id, fact_kind, schema_version,
                    recorded_identity, fact_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    reservation.reservation_digest,
                    acceptance_run_id,
                    "acceptance_semantic_request_reservation",
                    reservation.schema_version,
                    _acceptance_recorded_identity(
                        acceptance_run_id,
                        "acceptance_semantic_request_reservation",
                        reservation,
                    ),
                    _json_text(raw),
                ),
            )
            return reservation

        return self._snapshot_transaction(mutate)

    def record_semantic_attempt(
        self,
        *,
        run_id: str,
        repository_id: int,
        workflow_authority_digest: str | None = None,
        stage: Literal["extractor", "generator", "reviewer"],
        attempt_no: int,
        status: Literal[
            "started",
            "decided",
            "confirmed_retryable",
            "semantic_outcome_unknown",
        ],
        recorded_at: str,
    ) -> SemanticAttemptRecord:
        if (
            stage not in {"extractor", "generator", "reviewer"}
            or status
            not in {
                "started",
                "decided",
                "confirmed_retryable",
                "semantic_outcome_unknown",
            }
            or type(attempt_no) is not int
            or not 1 <= attempt_no <= 16
        ):
            raise ValueError("invalid semantic attempt transition")

        def mutate(connection: sqlite3.Connection) -> SemanticAttemptRecord:
            reservation = connection.execute(
                """SELECT reservation_digest, phase2_run_authority_digest
                   FROM operations_semantic_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if reservation is None:
                raise OperationsIntegrityError("semantic reservation is missing")
            resolved_workflow_authority = workflow_authority_digest
            if resolved_workflow_authority is None:
                if stage != "extractor":
                    raise OperationsIntegrityError(
                        "workflow authority is required for sibling semantic stages"
                    )
                resolved_workflow_authority = str(reservation["phase2_run_authority_digest"])
            if _DIGEST_PATTERN.fullmatch(resolved_workflow_authority) is None:
                raise ValueError("invalid workflow authority digest")
            rows = connection.execute(
                """SELECT * FROM operations_semantic_attempts
                   WHERE run_id = ? AND repository_id = ?
                     AND workflow_authority_digest = ? AND stage = ?
                   ORDER BY attempt_no""",
                (
                    run_id,
                    repository_id,
                    resolved_workflow_authority,
                    stage,
                ),
            ).fetchall()
            existing = next(
                (row for row in rows if int(row["attempt_no"]) == attempt_no),
                None,
            )
            if existing is None:
                if (
                    status != "started"
                    or attempt_no != len(rows) + 1
                    or (rows and rows[-1]["status"] not in {"confirmed_retryable"})
                ):
                    raise OperationsIntegrityError("semantic attempt continuity is invalid")
            elif existing["status"] == status:
                raw = _decoded_json(existing["attempt_json"])
                assert isinstance(raw, dict)
                return SemanticAttemptRecord(
                    run_id=run_id,
                    repository_id=repository_id,
                    workflow_authority_digest=resolved_workflow_authority,
                    stage=stage,
                    attempt_no=attempt_no,
                    status=status,
                    recorded_at=str(raw["recorded_at"]),
                    attempt_digest=str(existing["attempt_digest"]),
                )
            elif existing["status"] != "started" or status == "started":
                raise OperationsIntegrityError("semantic attempt is already decided")

            values: dict[str, object] = {
                "schema_version": "operations-semantic-attempt-v1",
                "run_id": run_id,
                "repository_id": repository_id,
                "workflow_authority_digest": resolved_workflow_authority,
                "stage": stage,
                "attempt_no": attempt_no,
                "status": status,
                "recorded_at": recorded_at,
            }
            values["attempt_digest"] = sha256_digest(values)
            if existing is None:
                connection.execute(
                    """INSERT INTO operations_semantic_attempts
                       (attempt_digest, run_id, repository_id,
                        workflow_authority_digest, stage, attempt_no,
                        status, attempt_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        values["attempt_digest"],
                        run_id,
                        repository_id,
                        resolved_workflow_authority,
                        stage,
                        attempt_no,
                        status,
                        _json_text(values),
                    ),
                )
            else:
                connection.execute(
                    """UPDATE operations_semantic_attempts
                       SET attempt_digest = ?, status = ?, attempt_json = ?
                       WHERE run_id = ? AND repository_id = ?
                         AND workflow_authority_digest = ?
                         AND stage = ? AND attempt_no = ?""",
                    (
                        values["attempt_digest"],
                        status,
                        _json_text(values),
                        run_id,
                        repository_id,
                        resolved_workflow_authority,
                        stage,
                        attempt_no,
                    ),
                )
            return SemanticAttemptRecord(
                run_id=run_id,
                repository_id=repository_id,
                workflow_authority_digest=resolved_workflow_authority,
                stage=stage,
                attempt_no=attempt_no,
                status=status,
                recorded_at=recorded_at,
                attempt_digest=str(values["attempt_digest"]),
            )

        return self._snapshot_transaction(mutate)

    def record_run_summary(
        self,
        run_id: str,
        summary: DiscoveryRunSummaryV1,
    ) -> DiscoveryRunSummaryV1:
        if type(summary) is not DiscoveryRunSummaryV1:
            raise TypeError("invalid discovery run summary")

        def mutate(connection: sqlite3.Connection) -> DiscoveryRunSummaryV1:
            authority = self._run_authority_digest(connection, run_id)
            if summary.discovery_run_authority_digest != authority:
                raise OperationsIntegrityError("run summary authority mismatch")
            counts = self._counts(connection, run_id)
            terminal_digests = tuple(
                str(row[0])
                for row in connection.execute(
                    """SELECT terminal_digest FROM operations_candidate_terminals
                       WHERE run_id = ? ORDER BY repository_id""",
                    (run_id,),
                ).fetchall()
            )
            if (
                summary.selected_candidate_count != counts["discovery"]
                or summary.semantic_reservation_count != counts["semantic"]
                or summary.terminal_digests != terminal_digests
            ):
                raise OperationsIntegrityError("run summary projection mismatch")
            connection.execute(
                """INSERT INTO operations_run_summaries
                   (summary_digest, run_id, summary_json) VALUES (?, ?, ?)""",
                (summary.summary_digest, run_id, _json_text(summary)),
            )
            connection.execute(
                "UPDATE operations_runs SET status = ? WHERE run_id = ?",
                (summary.status, run_id),
            )
            return summary

        return self._snapshot_transaction(mutate)

    @staticmethod
    def _counts(
        connection: sqlite3.Connection,
        run_id: str,
    ) -> dict[str, int]:
        return {
            kind: int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            for kind, table in (
                ("discovery", "operations_discovery_reservations"),
                ("semantic", "operations_semantic_reservations"),
            )
        }

    def reserve_test_slot(
        self,
        *,
        kind: Literal["discovery", "semantic"],
        run_id: str,
        repository_id: int,
        requested_ordinal: int,
        policy: DiscoveryBudgetPolicyV1,
    ) -> TestReservation:
        if type(policy) is not DiscoveryBudgetPolicyV1 or kind not in {
            "discovery",
            "semantic",
        }:
            raise TypeError("invalid reservation policy")
        if type(repository_id) is not int or repository_id < 1:
            raise ValueError("invalid repository ID")
        table = (
            "operations_discovery_reservations"
            if kind == "discovery"
            else "operations_semantic_reservations"
        )
        maximum = (
            DISCOVERY_MAX_CANDIDATES if kind == "discovery" else DISCOVERY_MAX_SEMANTIC_CANDIDATES
        )

        def mutate(connection: sqlite3.Connection) -> TestReservation:
            self._ensure_test_run(connection, run_id)
            existing = connection.execute(
                f"""SELECT reservation_json FROM {table}
                    WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if existing is not None:
                raw = _decoded_json(existing["reservation_json"])
                assert isinstance(raw, dict)
                return TestReservation(
                    kind=kind,
                    run_id=run_id,
                    repository_id=repository_id,
                    ordinal=int(raw["ordinal"]),
                    reservation_digest=str(raw["reservation_digest"]),
                )
            count = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            if count >= maximum or requested_ordinal > maximum:
                raise BudgetExhausted(f"{kind} budget exhausted")
            if requested_ordinal != count + 1:
                raise OperationsIntegrityError("reservation ordinal is not contiguous")
            if kind == "discovery":
                policy.admit_discovery_ordinal(requested_ordinal)
            else:
                policy.admit_semantic_ordinal(requested_ordinal)
            values: dict[str, object] = {
                "schema_version": _TEST_RESERVATION_SCHEMA,
                "kind": kind,
                "run_id": run_id,
                "repository_id": repository_id,
                "ordinal": requested_ordinal,
            }
            values["reservation_digest"] = sha256_digest(values)
            if kind == "discovery":
                connection.execute(
                    """INSERT INTO operations_discovery_reservations
                       (reservation_digest, run_id, repository_id, ordinal,
                        candidate_digest, reservation_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        values["reservation_digest"],
                        run_id,
                        repository_id,
                        requested_ordinal,
                        sha256_digest({"run_id": run_id, "repository_id": repository_id}),
                        _json_text(values),
                    ),
                )
            else:
                connection.execute(
                    """INSERT INTO operations_semantic_reservations
                       (reservation_digest, run_id, repository_id, ordinal,
                        discovery_reservation_digest,
                        phase2_run_authority_digest, reservation_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        values["reservation_digest"],
                        run_id,
                        repository_id,
                        requested_ordinal,
                        sha256_digest({"run_id": run_id, "repository_id": repository_id}),
                        sha256_digest({"phase2": run_id, "repository_id": repository_id}),
                        _json_text(values),
                    ),
                )
            return TestReservation(
                kind=kind,
                run_id=run_id,
                repository_id=repository_id,
                ordinal=requested_ordinal,
                reservation_digest=str(values["reservation_digest"]),
            )

        return self._snapshot_transaction(mutate)

    def reservation_count(
        self,
        run_id: str,
        *,
        kind: Literal["discovery", "semantic"],
    ) -> int:
        with self._thread_lock:
            if self._connection is None:
                raise OperationsStateError("operations state is closed")
            return self._counts(self._connection, run_id)[kind]

    def seed_test_reservations(self, *, run_id: str, repository_id: int) -> None:
        policy = DiscoveryBudgetPolicyV1()
        self.reserve_test_slot(
            kind="discovery",
            run_id=run_id,
            repository_id=repository_id,
            requested_ordinal=1,
            policy=policy,
        )
        self.reserve_test_slot(
            kind="semantic",
            run_id=run_id,
            repository_id=repository_id,
            requested_ordinal=1,
            policy=policy,
        )

    def reservation_projection(
        self,
        run_id: str,
    ) -> tuple[tuple[object, ...], ...]:
        with self._thread_lock:
            if self._connection is None:
                raise OperationsStateError("operations state is closed")
            return tuple(
                tuple(row)
                for table in (
                    "operations_discovery_reservations",
                    "operations_semantic_reservations",
                )
                for row in self._connection.execute(
                    f"""SELECT run_id, repository_id, ordinal, reservation_digest
                        FROM {table} WHERE run_id = ?
                        ORDER BY ordinal""",
                    (run_id,),
                ).fetchall()
            )

    def record_test_terminal(
        self,
        *,
        run_id: str,
        repository_id: int,
        outcome: str,
    ) -> None:
        def mutate(connection: sqlite3.Connection) -> None:
            semantic = connection.execute(
                """SELECT reservation_digest
                   FROM operations_semantic_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if semantic is None:
                raise OperationsIntegrityError("semantic reservation is missing")
            values: dict[str, object] = {
                "schema_version": _TEST_TERMINAL_SCHEMA,
                "run_id": run_id,
                "repository_id": repository_id,
                "outcome": outcome,
            }
            values["terminal_digest"] = sha256_digest(values)
            connection.execute(
                """INSERT INTO operations_candidate_terminals
                   (terminal_digest, run_id, repository_id,
                    semantic_reservation_digest, outcome, terminal_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    values["terminal_digest"],
                    run_id,
                    repository_id,
                    semantic["reservation_digest"],
                    outcome,
                    _json_text(values),
                ),
            )

        self._snapshot_transaction(mutate)

    @staticmethod
    def _facts_from_connection(
        connection: sqlite3.Connection,
    ) -> tuple[OperationsOwnedFactV1, ...]:
        facts: list[OperationsOwnedFactV1] = []
        for kind, table, json_column, order_columns, stored_columns in _FACT_TABLES:
            order = ", ".join(order_columns)
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
            for row in rows:
                row_kind = str(row["fact_kind"]) if table == "operations_acceptance_facts" else kind
                if (
                    table == "operations_acceptance_facts"
                    and row_kind not in _ACCEPTANCE_FACT_KINDS
                ):
                    raise OperationsIntegrityError("operations fact kind is invalid")
                value = _decoded_json(row[json_column])
                if not isinstance(value, dict):
                    raise OperationsIntegrityError("operations row JSON is invalid")
                payload = {
                    "schema_version": "operations-rebuild-row-v1",
                    "kind": row_kind,
                    "columns": {column: row[column] for column in stored_columns},
                    "value": value,
                }
                payload_json = _json_text(payload)
                facts.append(
                    OperationsOwnedFactV1(
                        schema_version="operations-owned-fact-v1",
                        kind=row_kind,  # type: ignore[arg-type]
                        sequence=len(facts),
                        payload_json=payload_json,
                        object_digest=sha256_digest(payload_json.encode("utf-8")),
                    )
                )
        return tuple(facts)

    @classmethod
    def _export_connection(
        cls,
        connection: sqlite3.Connection,
    ) -> OperationsOwnedStateV1:
        cls._verify_connection(connection)
        database_bytes = cls._serialize(connection)
        facts = cls._facts_from_connection(connection)
        projection = _projection_from_facts(facts)
        actual_schema = {
            str(row["name"]): _normalize_sql(str(row["sql"]))
            for row in connection.execute(
                """SELECT name, sql FROM sqlite_master
                   WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                   ORDER BY name"""
            ).fetchall()
        }
        fingerprint = _fingerprint_for_schema(actual_schema)
        return OperationsOwnedStateV1(
            schema_version="operations-owned-state-v1",
            owner="operations",
            database_locator="state/databases/operations.sqlite3",
            schema_fingerprint=fingerprint,
            database_bytes=database_bytes,
            database_digest=sha256_digest(database_bytes),
            facts=facts,
            projection=projection,
            projection_digest=projection.projection_digest,
            export_digest=_export_digest(
                schema_fingerprint=fingerprint,
                facts=facts,
                projection=projection,
            ),
        )

    @staticmethod
    def _validated_export(exported: object) -> OperationsOwnedStateV1:
        try:
            if isinstance(exported, OperationsOwnedStateV1):
                raw = exported.model_dump(mode="python", exclude_none=False)
            elif isinstance(exported, dict):
                raw = exported
            else:
                raise TypeError("invalid operations export")
            return OperationsOwnedStateV1.model_validate(raw, strict=False)
        except Exception:
            raise OperationsIntegrityError("invalid operations owned export") from None

    @classmethod
    def _replay_facts(
        cls,
        facts: tuple[OperationsOwnedFactV1, ...],
    ) -> sqlite3.Connection:
        connection = cls._new_connection()
        try:
            cls._create_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            kind_positions = {definition[0]: index for index, definition in enumerate(_FACT_TABLES)}
            acceptance_position = kind_positions["acceptance_nomination"]
            kind_positions.update({kind: acceptance_position for kind in _ACCEPTANCE_FACT_KINDS})
            positions = tuple(kind_positions[fact.kind] for fact in facts)
            if positions != tuple(sorted(positions)):
                raise OperationsIntegrityError("operations fact kinds are not canonically ordered")
            definitions = {definition[0]: definition for definition in _FACT_TABLES}
            acceptance_definition = definitions["acceptance_nomination"]
            definitions.update({kind: acceptance_definition for kind in _ACCEPTANCE_FACT_KINDS})
            for fact in facts:
                payload = _fact_payload(fact)
                definition = definitions[fact.kind]
                _kind, table, json_column, _order_columns, stored_columns = definition
                if (
                    payload.get("schema_version") != "operations-rebuild-row-v1"
                    or payload.get("kind") != fact.kind
                    or not isinstance(payload.get("columns"), dict)
                    or not isinstance(payload.get("value"), dict)
                ):
                    raise OperationsIntegrityError("operations rebuild row is malformed")
                columns = payload["columns"]
                value = payload["value"]
                assert isinstance(columns, dict)
                assert isinstance(value, dict)
                if set(columns) != set(stored_columns):
                    raise OperationsIntegrityError("operations rebuild columns are not exact")
                insert_columns = (*stored_columns, json_column)
                placeholders = ", ".join("?" for _column in insert_columns)
                connection.execute(
                    f"""INSERT INTO {table} ({", ".join(insert_columns)})
                        VALUES ({placeholders})""",
                    (
                        *(columns[column] for column in stored_columns),
                        _json_text(value),
                    ),
                )
            connection.commit()
            cls._verify_connection(connection)
            return connection
        except Exception:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
            connection.close()
            raise

    @classmethod
    def _candidate_from_export(
        cls,
        exported: object,
    ) -> tuple[sqlite3.Connection, OperationsOwnedStateV1]:
        authority = cls._validated_export(exported)
        database_is_valid = False
        database_connection: sqlite3.Connection | None = None
        if authority.database_bytes:
            try:
                database_connection = cls._new_connection()
                database_connection.deserialize(authority.database_bytes)
                database_connection.execute("PRAGMA foreign_keys = ON")
                cls._verify_connection(database_connection)
                database_is_valid = True
            except Exception:
                if database_connection is not None:
                    database_connection.close()
                    database_connection = None
        if database_is_valid:
            assert database_connection is not None
            database_projection = cls._export_connection(database_connection)
            if (
                authority.database_digest != sha256_digest(authority.database_bytes)
                or database_projection.facts != authority.facts
                or database_projection.projection != authority.projection
                or database_projection.schema_fingerprint != authority.schema_fingerprint
            ):
                database_connection.close()
                raise OperationsIntegrityError(
                    "valid operations database disagrees with owned JSON"
                )
            return database_connection, authority

        candidate = cls._replay_facts(authority.facts)
        rebuilt = cls._export_connection(candidate)
        if (
            rebuilt.facts != authority.facts
            or rebuilt.projection != authority.projection
            or rebuilt.schema_fingerprint != authority.schema_fingerprint
        ):
            candidate.close()
            raise OperationsIntegrityError(
                "rebuilt operations projection disagrees with owned JSON"
            )
        return candidate, authority

    def export_owned_state(self) -> OperationsOwnedStateV1:
        with self._thread_lock:
            if self._connection is None or self._poisoned:
                raise OperationsStateError("operations state is unavailable")
            return self._export_connection(self._connection)

    def _install_candidate(self, candidate: sqlite3.Connection) -> None:
        if self._parent is None:
            candidate.close()
            raise OperationsStateError("operations state is closed")
        self._verify_connection(candidate)
        payload = self._serialize(candidate)
        previous = self._parent.read_bytes(
            self._name,
            max_bytes=MAX_OPERATIONS_DB_BYTES,
            missing_ok=True,
        )
        try:
            if previous is None:
                self._parent.atomic_write(
                    self._name,
                    payload,
                    max_bytes=MAX_OPERATIONS_DB_BYTES,
                    seam_prefix="operations_state_",
                )
            else:
                self._parent.atomic_write(
                    self._name,
                    payload,
                    max_bytes=MAX_OPERATIONS_DB_BYTES,
                    restore_bytes=previous,
                    seam_prefix="operations_state_",
                )
        except (DurableWriteError, OSError):
            candidate.close()
            self._poisoned = True
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            raise OperationsStateError("operations state persistence is uncertain") from None
        current = self._connection
        self._connection = candidate
        self._durable_bytes = payload
        if current is not None:
            current.close()

    def restore_owned_state(self, exported: object) -> None:
        candidate, authority = self._candidate_from_export(exported)
        with self._thread_lock:
            self._install_candidate(candidate)
            restored = self.export_owned_state()
            if restored.facts != authority.facts or restored.projection != authority.projection:
                self._poisoned = True
                raise OperationsIntegrityError("restored operations projection mismatch")

    @classmethod
    def rebuild_owned_state(cls, path: Path, exported: object) -> None:
        candidate, authority = cls._candidate_from_export(exported)
        store = cls.__new__(cls)
        store.path = Path(os.path.abspath(os.fspath(path)))
        store._name = AnchoredDirectory.validate_child_name(store.path.name)
        store._lock_name = AnchoredDirectory.validate_child_name(f".{store._name}.lock")
        store._filesystem_seam = None
        store._parent = None
        store._lock_descriptor = -1
        store._connection = None
        store._durable_bytes = None
        store._poisoned = False
        store._thread_lock = threading.RLock()
        try:
            if (
                not isinstance(path, Path)
                or not path.name
                or path.name.startswith(".")
                or path.parent == path
            ):
                raise ValueError("operations state requires one private regular filename")
            store._parent = AnchoredDirectory.open(store.path.parent, create=True)
            store._acquire_lock()
            store._parent.recover_stale_temporary(store._name)
            store._install_candidate(candidate)
            rebuilt = store.export_owned_state()
            if rebuilt.facts != authority.facts or rebuilt.projection != authority.projection:
                raise OperationsIntegrityError("rebuilt operations projection mismatch")
        except Exception:
            if store._connection is not candidate:
                candidate.close()
            raise
        finally:
            store.close()

    def close(self) -> None:
        with self._thread_lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            if self._lock_descriptor >= 0:
                try:
                    fcntl.flock(self._lock_descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
                os.close(self._lock_descriptor)
                self._lock_descriptor = -1
            if self._parent is not None:
                self._parent.close()
                self._parent = None

    def __enter__(self) -> OperationsStateStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _three_store_projection(
    pipeline: PipelineOwnedStateV1,
    operations: OperationsOwnedStateV1,
    publication: PublicationOwnedStateV1,
) -> ThreeStoreProjectionV1:
    values: dict[str, object] = {
        "schema_version": "three-store-projection-v1",
        "pipeline": pipeline.projection,
        "operations": operations.projection,
        "publication": publication.projection,
        "pipeline_export_digest": pipeline.export_digest,
        "operations_export_digest": operations.export_digest,
        "publication_export_digest": publication.export_digest,
    }
    return ThreeStoreProjectionV1(
        **values,
        projection_digest=sha256_digest(
            {
                key: (
                    value.model_dump(mode="json", exclude_none=False)
                    if hasattr(value, "model_dump")
                    else value
                )
                for key, value in values.items()
            }
        ),
    )


def _discovery_projection_from_operations(
    projection: OperationsStateProjectionV1,
) -> DiscoveryStateRebuildProjectionV1:
    values: dict[str, object] = {
        "schema_version": "discovery-state-rebuild-projection-v1",
        "search_page_digests": projection.search_page_digests,
        "candidate_digests": projection.candidate_digests,
        "discovery_reservation_digests": projection.discovery_reservation_digests,
        "semantic_reservation_digests": projection.semantic_reservation_digests,
        "workflow_terminal_digests": projection.workflow_terminal_digests,
        "candidate_terminal_digests": projection.candidate_terminal_digests,
        "run_summary_digests": projection.run_summary_digests,
    }
    return DiscoveryStateRebuildProjectionV1(
        **values,
        projection_digest=sha256_digest(values),
    )


def _object_locator(digest: str) -> str:
    if _DIGEST_PATTERN.fullmatch(digest) is None:
        raise OperationsIntegrityError("invalid state object digest")
    hex_digest = digest.removeprefix("sha256:")
    return f"state/objects/sha256/{hex_digest[:2]}/{hex_digest}.json"


def _owned_envelope(
    exported: object,
) -> bytes:
    owner = str(getattr(exported, "owner"))
    return canonical_json_bytes(
        {
            "schema_version": "three-store-owned-envelope-v1",
            "owner": owner,
            "database_locator": getattr(exported, "database_locator"),
            "schema_fingerprint": getattr(exported, "schema_fingerprint"),
            "database_digest": getattr(exported, "database_digest"),
            "fact_digests": tuple(fact.object_digest for fact in getattr(exported, "facts")),
            "projection": getattr(exported, "projection").model_dump(
                mode="json", exclude_none=False
            ),
            "projection_digest": getattr(exported, "projection_digest"),
            "export_digest": getattr(exported, "export_digest"),
        }
    )


def _bundle_from_exports(
    *,
    pipeline: PipelineOwnedStateV1,
    operations: OperationsOwnedStateV1,
    publication: PublicationOwnedStateV1,
    prior_root_digest: str | None,
    state_parent_commit_sha: str,
    query_set_digest: str,
    budget_policy_digest: str,
    created_at: str,
) -> tuple[VerifiedStateBundle, ThreeStoreProjectionV1]:
    if (
        type(pipeline) is not PipelineOwnedStateV1
        or type(operations) is not OperationsOwnedStateV1
        or type(publication) is not PublicationOwnedStateV1
    ):
        raise OperationsIntegrityError("three-store exports are not canonical")
    projection = _three_store_projection(pipeline, operations, publication)
    object_bytes: dict[str, bytes] = {}
    for exported in (pipeline, operations, publication):
        for fact in exported.facts:
            payload = fact.payload_json.encode("utf-8")
            if sha256_digest(payload) != fact.object_digest:
                raise OperationsIntegrityError("owned fact digest mismatch")
            existing = object_bytes.setdefault(fact.object_digest, payload)
            if existing != payload:
                raise OperationsIntegrityError("state object digest collision")
        envelope = _owned_envelope(exported)
        envelope_digest = sha256_digest(envelope)
        existing = object_bytes.setdefault(envelope_digest, envelope)
        if existing != envelope:
            raise OperationsIntegrityError("state envelope digest collision")
    projection_bytes = canonical_json_bytes(projection)
    object_bytes[sha256_digest(projection_bytes)] = projection_bytes

    objects = tuple(
        DiscoveryStateObjectV1(
            object_digest=digest,
            locator=_object_locator(digest),
            size_bytes=len(content),
        )
        for digest, content in sorted(object_bytes.items())
    )
    databases = tuple(
        DiscoveryStateDatabaseV1(
            owner=exported.owner,
            locator=exported.database_locator,
            content_digest=exported.database_digest,
            size_bytes=len(exported.database_bytes),
            schema_fingerprint=exported.schema_fingerprint,
        )
        for exported in (pipeline, operations, publication)
    )
    root_values: dict[str, object] = {
        "schema_version": "discovery-state-root-v1",
        "root_locator": "state/root.json",
        "prior_root_digest": prior_root_digest,
        "state_parent_commit_sha": state_parent_commit_sha,
        "query_set_digest": query_set_digest,
        "budget_policy_digest": budget_policy_digest,
        "objects": objects,
        "databases": databases,
        "rebuild_projection": _discovery_projection_from_operations(operations.projection),
        "created_at": created_at,
    }
    root = DiscoveryStateRootV1(
        **root_values,
        root_digest=sha256_digest(
            {
                key: (
                    tuple(item.model_dump(mode="json", exclude_none=False) for item in value)
                    if key in {"objects", "databases"}
                    else value.model_dump(mode="json", exclude_none=False)
                    if hasattr(value, "model_dump")
                    else value
                )
                for key, value in root_values.items()
            }
        ),
    )
    files = [
        StateOwnedFile(
            "state/root.json",
            canonical_json_bytes(root.model_dump(mode="json", exclude_none=False)),
        ),
        *(
            StateOwnedFile(_object_locator(digest), content)
            for digest, content in sorted(object_bytes.items())
        ),
        StateOwnedFile(pipeline.database_locator, pipeline.database_bytes),
        StateOwnedFile(operations.database_locator, operations.database_bytes),
        StateOwnedFile(publication.database_locator, publication.database_bytes),
    ]
    bundle = VerifiedStateBundle(root, tuple(files))
    _validate_bundle(bundle, expected_parent=state_parent_commit_sha)
    return bundle, projection


def assemble_three_store_bundle(
    *,
    pipeline_store: SQLiteStateStore,
    operations_store: OperationsStateStore,
    publication_store: PublicationStateStore,
    prior_root_digest: str | None,
    state_parent_commit_sha: str,
    query_set_digest: str,
    budget_policy_digest: str,
    created_at: str,
) -> VerifiedStateBundle:
    """Assemble exactly three store-owned snapshots without reading private schemas."""

    pipeline = pipeline_store.export_owned_state()
    operations = operations_store.export_owned_state()
    publication = publication_store.export_owned_state()
    bundle, _projection = _bundle_from_exports(
        pipeline=pipeline,
        operations=operations,
        publication=publication,
        prior_root_digest=prior_root_digest,
        state_parent_commit_sha=state_parent_commit_sha,
        query_set_digest=query_set_digest,
        budget_policy_digest=budget_policy_digest,
        created_at=created_at,
    )
    return bundle


def _parse_bundle_exports(
    bundle: VerifiedStateBundle,
) -> tuple[
    PipelineOwnedStateV1,
    OperationsOwnedStateV1,
    PublicationOwnedStateV1,
    ThreeStoreProjectionV1,
]:
    try:
        files = _validate_bundle(
            bundle,
            expected_parent=bundle.root.state_parent_commit_sha,
        )
        objects: dict[str, tuple[dict[str, object], bytes]] = {}
        for state_object in bundle.root.objects:
            content = files[state_object.locator]
            decoded = json.loads(content)
            if type(decoded) is not dict:
                raise OperationsIntegrityError("state object is not an object")
            objects[state_object.object_digest] = (decoded, content)
        envelopes = [
            decoded
            for decoded, _content in objects.values()
            if decoded.get("schema_version") == "three-store-owned-envelope-v1"
        ]
        if len(envelopes) != 3 or {item.get("owner") for item in envelopes} != {
            "pipeline",
            "operations",
            "publication",
        }:
            raise OperationsIntegrityError("owned state envelopes are not exact")
        projection_objects = [
            decoded
            for decoded, _content in objects.values()
            if decoded.get("schema_version") == "three-store-projection-v1"
        ]
        if len(projection_objects) != 1:
            raise OperationsIntegrityError("three-store projection is not exact")
        projection = ThreeStoreProjectionV1.model_validate(projection_objects[0], strict=False)
        envelope_by_owner = {str(item["owner"]): item for item in envelopes}

        def facts_for(owner: str) -> tuple[object, ...]:
            envelope = envelope_by_owner[owner]
            digests = envelope.get("fact_digests")
            if not isinstance(digests, list) or len(digests) != len(set(digests)):
                raise OperationsIntegrityError("owned fact index is invalid")
            fact_type = {
                "pipeline": PipelineOwnedFactV1,
                "operations": OperationsOwnedFactV1,
                "publication": PublicationOwnedFactV1,
            }[owner]
            schema_version = {
                "pipeline": "pipeline-owned-fact-v1",
                "operations": "operations-owned-fact-v1",
                "publication": "publication-owned-fact-v1",
            }[owner]
            output = []
            for sequence, digest in enumerate(digests):
                if type(digest) is not str or digest not in objects:
                    raise OperationsIntegrityError("owned fact object is missing")
                decoded, content = objects[digest]
                kind = decoded.get("kind")
                output.append(
                    fact_type.model_validate(
                        {
                            "schema_version": schema_version,
                            "kind": kind,
                            "sequence": sequence,
                            "payload_json": content.decode("utf-8"),
                            "object_digest": digest,
                        },
                        strict=True,
                    )
                )
            return tuple(output)

        database_bytes = {owner: files[path] for owner, path in _THREE_STORE_DATABASE_PATHS.items()}

        def export_values(owner: str, facts: tuple[object, ...]) -> dict[str, object]:
            envelope = envelope_by_owner[owner]
            if set(envelope) != {
                "schema_version",
                "owner",
                "database_locator",
                "schema_fingerprint",
                "database_digest",
                "fact_digests",
                "projection",
                "projection_digest",
                "export_digest",
            }:
                raise OperationsIntegrityError("owned envelope fields are not exact")
            return {
                "schema_version": f"{owner}-owned-state-v1",
                "owner": owner,
                "database_locator": envelope["database_locator"],
                "schema_fingerprint": envelope["schema_fingerprint"],
                "database_bytes": database_bytes[owner],
                "database_digest": envelope["database_digest"],
                "facts": facts,
                "projection": envelope["projection"],
                "projection_digest": envelope["projection_digest"],
                "export_digest": envelope["export_digest"],
            }

        pipeline = PipelineOwnedStateV1.model_validate(
            export_values("pipeline", facts_for("pipeline")), strict=False
        )
        operations = OperationsOwnedStateV1.model_validate(
            export_values("operations", facts_for("operations")), strict=False
        )
        publication = PublicationOwnedStateV1.model_validate(
            export_values("publication", facts_for("publication")), strict=False
        )
        expected_projection = _three_store_projection(pipeline, operations, publication)
        if projection != expected_projection:
            raise OperationsIntegrityError("three-store projection mismatch")
        return pipeline, operations, publication, projection
    except OperationsIntegrityError:
        raise
    except Exception:
        raise OperationsIntegrityError("invalid three-store state bundle") from None


def restore_three_store_bundle(
    bundle: VerifiedStateBundle,
    *,
    pipeline_path: Path,
    operations_path: Path,
    publication_path: Path,
) -> ThreeStoreProjectionV1:
    """Validate the complete root first, then invoke each owning rebuild seam."""

    pipeline, operations, publication, projection = _parse_bundle_exports(bundle)
    prospective, expected_projection = _bundle_from_exports(
        pipeline=pipeline,
        operations=operations,
        publication=publication,
        prior_root_digest=bundle.root.prior_root_digest,
        state_parent_commit_sha=bundle.root.state_parent_commit_sha,
        query_set_digest=bundle.root.query_set_digest,
        budget_policy_digest=bundle.root.budget_policy_digest,
        created_at=bundle.root.created_at,
    )
    if (
        prospective.root != bundle.root
        or len(prospective.files) != len(bundle.files)
        or prospective.content_by_path() != bundle.content_by_path()
        or expected_projection != projection
    ):
        raise OperationsIntegrityError("bundle projection equality failed")

    SQLiteStateStore.rebuild_owned_state(pipeline_path, pipeline)
    OperationsStateStore.rebuild_owned_state(operations_path, operations)
    PublicationStateStore.rebuild_owned_state(publication_path, publication)

    pipeline_store = SQLiteStateStore(pipeline_path, reconcile_orphans=False)
    operations_store = OperationsStateStore(operations_path)
    publication_store = PublicationStateStore(publication_path)
    try:
        fresh = _three_store_projection(
            pipeline_store.export_owned_state(),
            operations_store.export_owned_state(),
            publication_store.export_owned_state(),
        )
    finally:
        publication_store.close()
        operations_store.close()
        pipeline_store.close()
    if fresh != projection:
        raise OperationsIntegrityError("restored cross-store projection mismatch")
    return fresh


def restore_acceptance_state_bundle(
    bundle: VerifiedStateBundle,
    *,
    pipeline_path: Path,
    operations_path: Path,
) -> ThreeStoreProjectionV1:
    """Restore only acceptance-owned mutable stores.

    Publication remains an immutable, typed export.  Its schema, bytes, digest,
    and cross-store projection are validated without constructing its owner.
    """

    pipeline, operations, publication, projection = _parse_bundle_exports(bundle)
    prospective, expected_projection = _bundle_from_exports(
        pipeline=pipeline,
        operations=operations,
        publication=publication,
        prior_root_digest=bundle.root.prior_root_digest,
        state_parent_commit_sha=bundle.root.state_parent_commit_sha,
        query_set_digest=bundle.root.query_set_digest,
        budget_policy_digest=bundle.root.budget_policy_digest,
        created_at=bundle.root.created_at,
    )
    if (
        prospective.root != bundle.root
        or prospective.content_by_path() != bundle.content_by_path()
        or expected_projection != projection
    ):
        raise OperationsIntegrityError("acceptance bundle projection equality failed")

    SQLiteStateStore.rebuild_owned_state(pipeline_path, pipeline)
    OperationsStateStore.rebuild_owned_state(operations_path, operations)
    pipeline_store = SQLiteStateStore(pipeline_path, reconcile_orphans=False)
    operations_store = OperationsStateStore(operations_path)
    try:
        fresh = _three_store_projection(
            pipeline_store.export_owned_state(),
            operations_store.export_owned_state(),
            publication,
        )
    finally:
        operations_store.close()
        pipeline_store.close()
    if fresh != projection:
        raise OperationsIntegrityError("acceptance restored projection mismatch")
    return fresh
