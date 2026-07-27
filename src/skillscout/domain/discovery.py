"""Strict, content-addressed contracts for bounded discovery operations."""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel

DISCOVERY_QUERY_SET_VERSION: Final = "github-repository-search-v1"
DISCOVERY_BUDGET_POLICY_VERSION: Final = "discovery-budget-policy-v1"
DISCOVERY_MAX_CANDIDATES: Final = 100
DISCOVERY_MAX_SEMANTIC_CANDIDATES: Final = 20

_Version = Annotated[str, Field(min_length=1, max_length=128)]
_Identifier = Annotated[
    str,
    Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]
_ModelIdentity = Annotated[str, Field(min_length=1, max_length=256)]
_Timestamp = Annotated[
    str,
    Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"),
]
_PositiveSQLiteInt = Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
_NonNegativeSQLiteInt = Annotated[
    int, Field(ge=0, le=9_223_372_036_854_775_807)
]
_GitHubSegment = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_.-]+$",
    ),
]
_GitHubFullName = Annotated[
    str,
    Field(
        min_length=3,
        max_length=201,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    ),
]

_APPROVED_QUERIES: Final[tuple[tuple[str, str], ...]] = (
    (
        "agent-workflow-readme",
        '"agent workflow" in:name,description,readme is:public archived:false',
    ),
    (
        "ai-workflow-readme",
        '"AI workflow" in:name,description,readme is:public archived:false',
    ),
    (
        "llm-automation-readme",
        '"LLM automation" in:name,description,readme is:public archived:false',
    ),
    (
        "agent-skills-topic",
        "topic:agent-skills is:public archived:false",
    ),
)


def _self_digest(model: StrictFrozenModel, field: str) -> str:
    return sha256_digest(
        model.model_dump(
            mode="json",
            exclude_none=False,
            exclude={field},
        )
    )


class DiscoveryQueryV1(StrictFrozenModel):
    """One reviewed query entry; runtime text cannot satisfy this contract."""

    query_id: Annotated[str, Field(min_length=1, max_length=64)]
    query_text: Annotated[str, Field(min_length=1, max_length=256)]


class DiscoveryQuerySetV1(StrictFrozenModel):
    """The exact ordered v1 GitHub Repository Search policy."""

    schema_version: Literal["discovery-query-set-v1"]
    query_set_version: Literal["github-repository-search-v1"]
    queries: Annotated[tuple[DiscoveryQueryV1, ...], Field(min_length=4, max_length=4)]
    per_page: Literal[25]
    max_pages_per_query: Literal[4]
    acquisition_order: Literal["round_robin"]
    sort: Literal["updated"]
    order: Literal["desc"]
    query_set_digest: Digest | None = None

    @model_validator(mode="before")
    @classmethod
    def bind_query_set_digest(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("query_set_digest") is None:
            payload = dict(value)
            payload.pop("query_set_digest", None)
            digest_payload = dict(payload)
            payload["queries"] = tuple(payload.get("queries", ()))
            payload["query_set_digest"] = sha256_digest(digest_payload)
            return payload
        return value

    @model_validator(mode="after")
    def validate_exact_policy(self) -> DiscoveryQuerySetV1:
        actual = tuple((item.query_id, item.query_text) for item in self.queries)
        if actual != _APPROVED_QUERIES:
            raise ValueError("discovery query order or text is not the reviewed v1 policy")
        if (
            self.query_set_digest is None
            or self.query_set_digest != _self_digest(self, "query_set_digest")
        ):
            raise ValueError("discovery query-set digest mismatch")
        return self


class DiscoveryBudgetPolicyV1(StrictFrozenModel):
    """Literal, non-widenable repository and semantic-candidate ceilings."""

    schema_version: Literal["discovery-budget-policy-v1"] = (
        "discovery-budget-policy-v1"
    )
    budget_policy_version: Literal["discovery-budget-policy-v1"] = (
        DISCOVERY_BUDGET_POLICY_VERSION
    )
    max_candidates: Literal[100] = DISCOVERY_MAX_CANDIDATES
    max_semantic_candidates: Literal[20] = DISCOVERY_MAX_SEMANTIC_CANDIDATES
    budget_policy_digest: Digest | None = None

    @model_validator(mode="before")
    @classmethod
    def bind_budget_digest(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("budget_policy_digest") is None:
            payload = dict(value)
            payload.pop("budget_policy_digest", None)
            payload.setdefault("schema_version", "discovery-budget-policy-v1")
            payload.setdefault(
                "budget_policy_version", DISCOVERY_BUDGET_POLICY_VERSION
            )
            payload.setdefault("max_candidates", DISCOVERY_MAX_CANDIDATES)
            payload.setdefault(
                "max_semantic_candidates",
                DISCOVERY_MAX_SEMANTIC_CANDIDATES,
            )
            payload["budget_policy_digest"] = sha256_digest(payload)
            return payload
        return value

    @model_validator(mode="after")
    def validate_budget_digest(self) -> DiscoveryBudgetPolicyV1:
        if (
            self.budget_policy_digest is None
            or self.budget_policy_digest != _self_digest(self, "budget_policy_digest")
        ):
            raise ValueError("discovery budget-policy digest mismatch")
        return self

    def admit_discovery_ordinal(self, ordinal: int) -> int:
        if type(ordinal) is not int or not 1 <= ordinal <= DISCOVERY_MAX_CANDIDATES:
            raise ValueError("discovery ordinal exceeds the hard candidate ceiling")
        return ordinal

    def admit_semantic_ordinal(self, ordinal: int) -> int:
        if (
            type(ordinal) is not int
            or not 1 <= ordinal <= DISCOVERY_MAX_SEMANTIC_CANDIDATES
        ):
            raise ValueError("semantic ordinal exceeds the hard candidate ceiling")
        return ordinal


class DiscoveryRunAuthorityV1(StrictFrozenModel):
    """Stable discovery-run identity, excluding changing checkpoint heads."""

    schema_version: Literal["discovery-run-authority-v1"]
    run_id: _Identifier
    query_set_digest: Digest
    budget_policy_digest: Digest
    phase2_profile_version: _Version
    phase3_profile_version: _Version
    semantic_provider: Literal["openai", "deepseek"]
    extractor_model_id: _ModelIdentity
    generator_model_id: _ModelIdentity
    reviewer_model_id: _ModelIdentity
    initial_state_root_digest: Digest
    authority_digest: Digest

    @model_validator(mode="after")
    def validate_authority_digest(self) -> DiscoveryRunAuthorityV1:
        if self.authority_digest != _self_digest(self, "authority_digest"):
            raise ValueError("discovery run authority digest mismatch")
        return self


class SearchRateLimitFactsV1(StrictFrozenModel):
    """Allowlisted numeric GitHub Search rate facts."""

    limit: _NonNegativeSQLiteInt
    remaining: _NonNegativeSQLiteInt
    used: _NonNegativeSQLiteInt
    reset_epoch: _NonNegativeSQLiteInt
    resource: Literal["search"]

    @model_validator(mode="after")
    def validate_rate_accounting(self) -> SearchRateLimitFactsV1:
        if self.remaining > self.limit or self.used > self.limit:
            raise ValueError("search rate facts exceed the reported limit")
        if self.remaining + self.used != self.limit:
            raise ValueError("search rate facts do not reconcile")
        return self


class SearchPageObservationV1(StrictFrozenModel):
    """One bounded Search page projected without raw headers or Link text."""

    schema_version: Literal["search-page-observation-v1"]
    discovery_run_authority_digest: Digest
    query_set_version: Literal["github-repository-search-v1"]
    query_set_digest: Digest
    query_id: Annotated[str, Field(min_length=1, max_length=64)]
    query_ordinal: Annotated[int, Field(ge=1, le=4)]
    query_text: Annotated[str, Field(min_length=1, max_length=256)]
    sort: Literal["updated"]
    order: Literal["desc"]
    page: Annotated[int, Field(ge=1, le=4)]
    per_page: Literal[25]
    next_page: Annotated[int, Field(ge=2, le=4)] | None
    total_count: _NonNegativeSQLiteInt
    incomplete_results: bool
    item_count: Annotated[int, Field(ge=0, le=25)]
    request_id: Annotated[str, Field(min_length=1, max_length=256)]
    rate_limit: SearchRateLimitFactsV1
    observation_digest: Digest

    @model_validator(mode="after")
    def validate_page_authority(self) -> SearchPageObservationV1:
        approved_id, approved_text = _APPROVED_QUERIES[self.query_ordinal - 1]
        expected_next = self.page + 1 if self.page < 4 else None
        if (self.query_id, self.query_text) != (approved_id, approved_text):
            raise ValueError("search page query is outside the reviewed query set")
        if self.next_page not in {None, expected_next}:
            raise ValueError("search page cursor is not the next bounded page")
        if self.item_count > self.total_count:
            raise ValueError("search page item count exceeds the reported total")
        if self.observation_digest != _self_digest(self, "observation_digest"):
            raise ValueError("search page observation digest mismatch")
        return self


class SearchRepositoryObservationV1(StrictFrozenModel):
    """Trimmed repository metadata; provider prose is structurally absent."""

    schema_version: Literal["search-repository-observation-v1"]
    repository_id: _PositiveSQLiteInt
    owner: _GitHubSegment
    name: _GitHubSegment
    full_name: _GitHubFullName
    private: bool
    visibility: Literal["public", "private"]
    fork: bool
    archived: bool
    disabled: bool
    default_branch: _GitHubSegment | None
    observation_digest: Digest

    @model_validator(mode="after")
    def validate_repository_projection(self) -> SearchRepositoryObservationV1:
        if self.full_name != f"{self.owner}/{self.name}":
            raise ValueError("repository full name disagrees with owner and name")
        if self.private is (self.visibility == "public"):
            raise ValueError("repository visibility facts disagree")
        if self.observation_digest != _self_digest(self, "observation_digest"):
            raise ValueError("repository observation digest mismatch")
        return self


class DiscoveredCandidateV1(StrictFrozenModel):
    """One first-seen or duplicate repo-ID observation with stable provenance."""

    schema_version: Literal["discovered-candidate-v1"]
    discovery_run_authority_digest: Digest
    repository: SearchRepositoryObservationV1
    source_page_digest: Digest
    query_ordinal: Annotated[int, Field(ge=1, le=4)]
    page: Annotated[int, Field(ge=1, le=4)]
    item_ordinal: Annotated[int, Field(ge=1, le=25)]
    dedup_disposition: Literal["first_seen", "duplicate"]
    discovery_ordinal: Annotated[int, Field(ge=1, le=100)] | None
    first_seen_query_ordinal: Annotated[int, Field(ge=1, le=4)]
    first_seen_page: Annotated[int, Field(ge=1, le=4)]
    first_seen_item_ordinal: Annotated[int, Field(ge=1, le=25)]
    candidate_digest: Digest

    @model_validator(mode="after")
    def validate_dedup_provenance(self) -> DiscoveredCandidateV1:
        current = (self.query_ordinal, self.page, self.item_ordinal)
        first_seen = (
            self.first_seen_query_ordinal,
            self.first_seen_page,
            self.first_seen_item_ordinal,
        )
        if self.dedup_disposition == "first_seen":
            valid_shape = self.discovery_ordinal is not None and current == first_seen
        else:
            valid_shape = self.discovery_ordinal is None and current != first_seen
        if not valid_shape:
            raise ValueError("candidate dedup provenance is incoherent")
        if self.candidate_digest != _self_digest(self, "candidate_digest"):
            raise ValueError("discovered candidate digest mismatch")
        return self


class DiscoveryReservationV1(StrictFrozenModel):
    """Non-refundable first-seen selection of one numeric repository ID."""

    schema_version: Literal["discovery-reservation-v1"]
    discovery_run_authority_digest: Digest
    repository_id: _PositiveSQLiteInt
    ordinal: Annotated[int, Field(ge=1, le=100)]
    candidate_digest: Digest
    reserved_at: _Timestamp
    reservation_digest: Digest

    @model_validator(mode="after")
    def validate_reservation_digest(self) -> DiscoveryReservationV1:
        if self.reservation_digest != _self_digest(self, "reservation_digest"):
            raise ValueError("discovery reservation digest mismatch")
        return self


class SemanticReservationV1(StrictFrozenModel):
    """Non-refundable repository admission before the first Extractor request."""

    schema_version: Literal["semantic-reservation-v1"]
    discovery_run_authority_digest: Digest
    repository_id: _PositiveSQLiteInt
    ordinal: Annotated[int, Field(ge=1, le=20)]
    discovery_reservation_digest: Digest
    phase2_run_authority_digest: Digest
    reserved_at: _Timestamp
    reservation_digest: Digest

    @model_validator(mode="after")
    def validate_reservation_digest(self) -> SemanticReservationV1:
        if self.reservation_digest != _self_digest(self, "reservation_digest"):
            raise ValueError("semantic reservation digest mismatch")
        return self


_CandidateOutcome = Literal[
    "filter_rejected",
    "no_workflow",
    "qualification_rejected",
    "validation_rejected",
    "review_rejected",
    "completed_reuse",
    "eligible_local_candidate",
    "confirmed_retryable",
    "semantic_outcome_unknown",
    "state_integrity_conflict",
    "permanent_failure",
]


class DiscoveryCandidateTerminalV1(StrictFrozenModel):
    """Closed business and operational terminal taxonomy for one repository."""

    schema_version: Literal["discovery-candidate-terminal-v1"]
    discovery_run_authority_digest: Digest
    repository_id: _PositiveSQLiteInt
    semantic_reservation_digest: Digest | None
    outcome: _CandidateOutcome
    workflow_authority_digests: Annotated[
        tuple[Digest, ...], Field(max_length=3)
    ]
    recorded_at: _Timestamp
    terminal_digest: Digest

    @model_validator(mode="before")
    @classmethod
    def normalize_workflow_digests(cls, value: object) -> object:
        if isinstance(value, dict):
            payload = dict(value)
            if isinstance(payload.get("workflow_authority_digests"), list):
                payload["workflow_authority_digests"] = tuple(
                    payload["workflow_authority_digests"]
                )
            return payload
        return value

    @model_validator(mode="after")
    def validate_terminal(self) -> DiscoveryCandidateTerminalV1:
        if len(set(self.workflow_authority_digests)) != len(
            self.workflow_authority_digests
        ):
            raise ValueError("terminal workflow authorities are not unique")
        if self.terminal_digest != _self_digest(self, "terminal_digest"):
            raise ValueError("candidate terminal digest mismatch")
        return self

    @property
    def quarantined(self) -> bool:
        return self.outcome == "semantic_outcome_unknown"

    @property
    def automatic_retry_allowed(self) -> bool:
        return self.outcome == "confirmed_retryable"


class DiscoveryRunSummaryV1(StrictFrozenModel):
    """Bounded run-health projection separate from candidate business outcomes."""

    schema_version: Literal["discovery-run-summary-v1"]
    discovery_run_authority_digest: Digest
    status: Literal[
        "completed",
        "completed_degraded",
        "confirmed_retryable",
        "integrity_conflict",
        "permanent_failure",
    ]
    selected_candidate_count: Annotated[int, Field(ge=0, le=100)]
    semantic_reservation_count: Annotated[int, Field(ge=0, le=20)]
    business_terminal_count: Annotated[int, Field(ge=0, le=100)]
    quarantined_candidate_count: Annotated[int, Field(ge=0, le=20)]
    confirmed_retryable_count: Annotated[int, Field(ge=0, le=100)]
    integrity_conflict_count: Annotated[int, Field(ge=0, le=1)]
    permanent_failure_count: Annotated[int, Field(ge=0, le=1)]
    terminal_digests: Annotated[tuple[Digest, ...], Field(max_length=100)]
    completed_at: _Timestamp
    summary_digest: Digest

    @model_validator(mode="before")
    @classmethod
    def normalize_terminal_digests(cls, value: object) -> object:
        if isinstance(value, dict):
            payload = dict(value)
            if isinstance(payload.get("terminal_digests"), list):
                payload["terminal_digests"] = tuple(payload["terminal_digests"])
            return payload
        return value

    @model_validator(mode="after")
    def validate_run_summary(self) -> DiscoveryRunSummaryV1:
        classified = (
            self.business_terminal_count
            + self.quarantined_candidate_count
            + self.confirmed_retryable_count
            + self.integrity_conflict_count
            + self.permanent_failure_count
        )
        if classified != len(self.terminal_digests):
            raise ValueError("run summary terminal projection does not reconcile")
        if len(set(self.terminal_digests)) != len(self.terminal_digests):
            raise ValueError("run summary terminal digests are not unique")
        if self.semantic_reservation_count > self.selected_candidate_count:
            raise ValueError("semantic reservations exceed selected repositories")
        if self.summary_digest != _self_digest(self, "summary_digest"):
            raise ValueError("discovery run summary digest mismatch")
        return self


class DiscoveryStateObjectV1(StrictFrozenModel):
    """One immutable canonical JSON object at its digest-derived locator."""

    object_digest: Digest
    locator: Annotated[str, Field(min_length=1, max_length=128)]
    size_bytes: Annotated[int, Field(ge=1, le=1_048_576)]

    @model_validator(mode="after")
    def validate_object_locator(self) -> DiscoveryStateObjectV1:
        hex_digest = self.object_digest.removeprefix("sha256:")
        expected = f"state/objects/sha256/{hex_digest[:2]}/{hex_digest}.json"
        if self.locator != expected:
            raise ValueError("state object locator does not match its digest")
        return self


_DatabaseOwner = Literal["pipeline", "operations", "publication"]
_DATABASE_LOCATORS: Final[dict[str, str]] = {
    "pipeline": "state/databases/pipeline.sqlite3",
    "operations": "state/databases/operations.sqlite3",
    "publication": "state/databases/publication.sqlite3",
}


class DiscoveryStateDatabaseV1(StrictFrozenModel):
    """One store-owned SQLite snapshot at its sole permitted path."""

    owner: _DatabaseOwner
    locator: Annotated[str, Field(min_length=1, max_length=64)]
    content_digest: Digest
    size_bytes: Annotated[int, Field(ge=1, le=1_073_741_824)]
    schema_fingerprint: Digest

    @model_validator(mode="after")
    def validate_database_owner(self) -> DiscoveryStateDatabaseV1:
        if self.locator != _DATABASE_LOCATORS[self.owner]:
            raise ValueError("state database owner and locator disagree")
        return self


class DiscoveryStateRebuildProjectionV1(StrictFrozenModel):
    """Complete allowlisted digest projection sufficient for store-owned replay."""

    schema_version: Literal["discovery-state-rebuild-projection-v1"]
    search_page_digests: Annotated[tuple[Digest, ...], Field(max_length=16)]
    candidate_digests: Annotated[tuple[Digest, ...], Field(max_length=1_600)]
    discovery_reservation_digests: Annotated[
        tuple[Digest, ...], Field(max_length=100)
    ]
    semantic_reservation_digests: Annotated[
        tuple[Digest, ...], Field(max_length=20)
    ]
    candidate_terminal_digests: Annotated[
        tuple[Digest, ...], Field(max_length=100)
    ]
    run_summary_digests: Annotated[tuple[Digest, ...], Field(max_length=1)]
    projection_digest: Digest

    @model_validator(mode="before")
    @classmethod
    def normalize_digest_sequences(cls, value: object) -> object:
        if isinstance(value, dict):
            payload = dict(value)
            for field in (
                "search_page_digests",
                "candidate_digests",
                "discovery_reservation_digests",
                "semantic_reservation_digests",
                "candidate_terminal_digests",
                "run_summary_digests",
            ):
                if isinstance(payload.get(field), list):
                    payload[field] = tuple(payload[field])
            return payload
        return value

    @model_validator(mode="after")
    def validate_projection(self) -> DiscoveryStateRebuildProjectionV1:
        sequences = (
            self.search_page_digests,
            self.candidate_digests,
            self.discovery_reservation_digests,
            self.semantic_reservation_digests,
            self.candidate_terminal_digests,
            self.run_summary_digests,
        )
        if any(len(set(sequence)) != len(sequence) for sequence in sequences):
            raise ValueError("rebuild projection contains duplicate digests")
        if self.projection_digest != _self_digest(self, "projection_digest"):
            raise ValueError("state rebuild projection digest mismatch")
        return self


class DiscoveryStateRootV1(StrictFrozenModel):
    """Canonical state head with prior-root reachability and no pruning surface."""

    schema_version: Literal["discovery-state-root-v1"]
    root_locator: Literal["state/root.json"]
    prior_root_digest: Digest | None
    state_parent_commit_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    query_set_digest: Digest
    budget_policy_digest: Digest
    objects: Annotated[tuple[DiscoveryStateObjectV1, ...], Field(max_length=4_096)]
    databases: Annotated[
        tuple[DiscoveryStateDatabaseV1, ...], Field(min_length=3, max_length=3)
    ]
    rebuild_projection: DiscoveryStateRebuildProjectionV1
    created_at: _Timestamp
    root_digest: Digest

    @model_validator(mode="before")
    @classmethod
    def normalize_root_sequences(cls, value: object) -> object:
        if isinstance(value, dict):
            payload = dict(value)
            for field in ("objects", "databases"):
                if isinstance(payload.get(field), list):
                    payload[field] = tuple(payload[field])
            return payload
        return value

    @model_validator(mode="after")
    def validate_state_root(self) -> DiscoveryStateRootV1:
        object_digests = tuple(item.object_digest for item in self.objects)
        if (
            object_digests != tuple(sorted(object_digests))
            or len(set(object_digests)) != len(object_digests)
        ):
            raise ValueError("state objects are not canonically ordered and unique")
        expected_databases = tuple(
            (owner, locator) for owner, locator in _DATABASE_LOCATORS.items()
        )
        actual_databases = tuple(
            (database.owner, database.locator) for database in self.databases
        )
        if actual_databases != expected_databases:
            raise ValueError("state root does not contain the exact owned databases")
        if self.root_digest != _self_digest(self, "root_digest"):
            raise ValueError("discovery state root digest mismatch")
        return self
