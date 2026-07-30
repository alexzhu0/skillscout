"""Strict, redacted contracts for the Phase 6 acceptance evidence graph."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Final, Literal, Self

from pydantic import Field, field_validator, model_validator

from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel

_Identifier = Annotated[
    str,
    Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]
_Version = Annotated[str, Field(min_length=1, max_length=128)]
_Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
_FullName = Annotated[
    str,
    Field(
        min_length=3,
        max_length=201,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    ),
]
_Ref = Annotated[
    str,
    Field(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$",
    ),
]
_Timestamp = Annotated[
    str,
    Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"),
]
_NonNegative = Annotated[int, Field(ge=0, le=9_223_372_036_854_775_807)]
_Positive = Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
_Spdx = Literal["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]


def _self_digest(model: StrictFrozenModel, field: str) -> str:
    return sha256_digest(
        model.model_dump(mode="json", exclude_none=False, exclude={field})
    )


def _canonical_input(value: object) -> object:
    if isinstance(value, StrictFrozenModel):
        return value.model_dump(mode="json", exclude_none=False)
    if isinstance(value, dict):
        return {key: _canonical_input(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_input(item) for item in value]
    return value


class _SelfDigestedModel(StrictFrozenModel):
    """Bind an omitted self-digest and reject every stale supplied digest."""

    _digest_field: ClassVar[str]

    @model_validator(mode="before")
    @classmethod
    def bind_self_digest(cls, value: object) -> object:
        if isinstance(value, dict) and value.get(cls._digest_field) is None:
            payload = dict(value)
            payload.pop(cls._digest_field, None)
            payload[cls._digest_field] = sha256_digest(_canonical_input(payload))
            return payload
        return value

    @model_validator(mode="after")
    def validate_self_digest(self) -> Self:
        if getattr(self, self._digest_field) != _self_digest(
            self, self._digest_field
        ):
            raise ValueError(f"{self._digest_field} mismatch")
        return self


class BenchmarkSelectionSource(StrEnum):
    SEARCH_DERIVED = "search_derived"
    USER_NOMINATED = "user_nominated"


class BenchmarkCoverageRole(StrEnum):
    POSITIVE = "positive"
    POSITIVE_MULTI_WORKFLOW = "positive_multi_workflow"
    NEGATIVE = "negative"
    BORDERLINE = "borderline"


class NominationEntryV1(_SelfDigestedModel):
    """Role-neutral, immutable repository identity admitted by nomination."""

    _digest_field = "entry_digest"

    schema_version: Literal["nomination-entry-v1"]
    repository_full_name: _FullName
    repository_id: _Positive
    exact_commit_sha: _Sha
    license_spdx: _Spdx
    selection_source: Literal["search_derived", "user_nominated"]
    selection_evidence_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=32)
    ]
    entry_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_selection_evidence(self) -> Self:
        if self.selection_evidence_digests != tuple(
            sorted(self.selection_evidence_digests)
        ) or len(set(self.selection_evidence_digests)) != len(
            self.selection_evidence_digests
        ):
            raise ValueError("nomination selection evidence must be sorted and unique")
        return self


class BenchmarkEntryV1(_SelfDigestedModel):
    """Human-assigned coverage role bound to one exact nomination entry."""

    _digest_field = "entry_digest"

    schema_version: Literal["benchmark-entry-v1"]
    repository_full_name: _FullName
    repository_id: _Positive
    exact_commit_sha: _Sha
    license_spdx: _Spdx
    selection_source: Literal["search_derived", "user_nominated"]
    coverage_role: Literal[
        "positive", "positive_multi_workflow", "negative", "borderline"
    ]
    nomination_entry_digest: Digest
    selection_evidence_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=32)
    ]
    entry_digest: Digest | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_selection_evidence(cls, value: object) -> object:
        if isinstance(value, dict):
            payload = dict(value)
            if isinstance(payload.get("selection_evidence_digests"), list):
                payload["selection_evidence_digests"] = tuple(
                    payload["selection_evidence_digests"]
                )
            return payload
        return value

    @model_validator(mode="after")
    def validate_selection_evidence(self) -> Self:
        if (
            self.selection_evidence_digests
            != tuple(sorted(self.selection_evidence_digests))
            or len(set(self.selection_evidence_digests))
            != len(self.selection_evidence_digests)
        ):
            raise ValueError("benchmark selection evidence must be sorted and unique")
        return self


class NominationSetV1(_SelfDigestedModel):
    _digest_field = "nomination_set_digest"

    schema_version: Literal["nomination-set-v1"]
    nomination_set_id: _Identifier
    query_set_digest: Digest
    search_run_authority_digest: Digest
    search_derived_entries: Annotated[
        tuple[NominationEntryV1, ...], Field(min_length=5, max_length=100)
    ]
    user_nominated_entries: Annotated[
        tuple[NominationEntryV1, ...], Field(max_length=100)
    ]
    created_at: _Timestamp
    nomination_set_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_nomination_lanes(self) -> Self:
        if any(
            entry.selection_source != BenchmarkSelectionSource.SEARCH_DERIVED
            for entry in self.search_derived_entries
        ) or any(
            entry.selection_source != BenchmarkSelectionSource.USER_NOMINATED
            for entry in self.user_nominated_entries
        ):
            raise ValueError("benchmark nomination entry is in the wrong lane")
        all_entries = self.search_derived_entries + self.user_nominated_entries
        entry_digests = tuple(entry.entry_digest for entry in all_entries)
        repository_ids = tuple(entry.repository_id for entry in all_entries)
        if (
            entry_digests != tuple(sorted(entry_digests))
            or len(set(entry_digests)) != len(entry_digests)
            or len(set(repository_ids)) != len(repository_ids)
        ):
            raise ValueError("benchmark nominations are not canonical and unique")
        return self


class BenchmarkLockAttestationV1(_SelfDigestedModel):
    _digest_field = "attestation_digest"

    schema_version: Literal["benchmark-lock-attestation-v1"]
    manifest_version: _Positive
    nomination_set_digest: Digest
    manifest_digest: Digest
    reviewer_id: _Identifier
    locked_at: _Timestamp
    attestation_digest: Digest | None = None


class LockedBenchmarkManifestV1(StrictFrozenModel):
    schema_version: Literal["locked-benchmark-manifest-v1"]
    manifest_version: _Positive
    nomination_set_digest: Digest
    entries: Annotated[tuple[BenchmarkEntryV1, ...], Field(min_length=5, max_length=5)]
    lock_attestation: BenchmarkLockAttestationV1
    prior_manifest_digest: Digest | None
    manifest_digest: Digest

    @model_validator(mode="before")
    @classmethod
    def normalize_entries(cls, value: object) -> object:
        if isinstance(value, dict):
            payload = dict(value)
            if isinstance(payload.get("entries"), list):
                payload["entries"] = tuple(payload["entries"])
            return payload
        return value

    @model_validator(mode="after")
    def validate_locked_manifest(self) -> Self:
        roles = tuple(entry.coverage_role for entry in self.entries)
        if (
            roles.count(BenchmarkCoverageRole.POSITIVE) != 1
            or roles.count(BenchmarkCoverageRole.POSITIVE_MULTI_WORKFLOW) != 1
            or roles.count(BenchmarkCoverageRole.NEGATIVE) != 2
            or roles.count(BenchmarkCoverageRole.BORDERLINE) != 1
        ):
            raise ValueError("locked benchmark does not have the exact role distribution")
        entry_digests = tuple(entry.entry_digest for entry in self.entries)
        if (
            entry_digests != tuple(sorted(entry_digests))
            or len(set(entry_digests)) != 5
            or len({entry.repository_id for entry in self.entries}) != 5
        ):
            raise ValueError("locked benchmark entries are not canonical and unique")
        preimage = self.model_dump(
            mode="json",
            exclude_none=False,
            exclude={"lock_attestation", "manifest_digest"},
        )
        if self.manifest_digest != sha256_digest(preimage):
            raise ValueError("locked benchmark manifest digest mismatch")
        if (
            self.lock_attestation.manifest_version != self.manifest_version
            or self.lock_attestation.nomination_set_digest
            != self.nomination_set_digest
            or self.lock_attestation.manifest_digest != self.manifest_digest
        ):
            raise ValueError("benchmark lock attestation does not bind the manifest")
        if self.manifest_version == 1 and self.prior_manifest_digest is not None:
            raise ValueError("initial benchmark manifest cannot have a prior revision")
        if self.manifest_version > 1 and self.prior_manifest_digest is None:
            raise ValueError("benchmark revision must bind its prior manifest")
        return self


class LiveAcceptanceAuthorityV1(_SelfDigestedModel):
    """Human-approved immutable authority consumed by protected live execution."""

    _digest_field = "authority_digest"

    schema_version: Literal["live-acceptance-authority-v1"]
    authority_version: Literal[1]
    source_commit_sha: _Sha
    acceptance_workflow_sha256: Digest
    manifest_path: Literal[
        ".planning/phases/06-adversarial-mvp-acceptance/"
        "06-BENCHMARK-MANIFEST.json"
    ]
    manifest_digest: Digest
    nomination_set_digest: Digest
    lock_attestation_digest: Digest
    state_commit_sha: _Sha
    state_root_digest: Digest
    state_repository_id: _Positive
    state_repository_full_name: _FullName
    query_set_digest: Digest
    budget_policy_digest: Digest
    semantic_provider: Literal["deepseek"]
    provider_base_url: Literal["https://api.deepseek.com"]
    stage_models: tuple[
        Literal["deepseek-v4-flash"],
        Literal["deepseek-v4-flash"],
        Literal["deepseek-v4-pro"],
    ]
    prompt_versions: tuple[
        Literal["extract-prompt-v1"],
        Literal["generator-prompt-v1"],
        Literal["reviewer-prompt-v1"],
    ]
    schema_versions: tuple[
        Literal["workflow-spec-v1"],
        Literal["generation-draft-v1"],
        Literal["reviewer-judgment-v1"],
    ]
    policy_versions: Annotated[tuple[_Version, ...], Field(min_length=5, max_length=16)]
    max_candidates: Literal[100]
    max_semantic_candidates: Literal[20]
    max_semantic_requests: Literal[20]
    max_files_per_repository: Literal[25]
    max_source_files_per_repository: Literal[5]
    max_file_bytes: Literal[131_072]
    max_total_bytes_per_repository: Literal[524_288]
    max_tokens_per_repository: Literal[40_000]
    benchmark_scenario_write_count: Literal[5]
    replay_semantic_effect_count: Literal[0]
    replay_publication_effect_count: Literal[0]
    reviewer_id: _Identifier
    approved_at: _Timestamp
    authority_digest: Digest | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> object:
        if isinstance(value, dict):
            payload = dict(value)
            for field in (
                "stage_models",
                "prompt_versions",
                "schema_versions",
                "policy_versions",
            ):
                if isinstance(payload.get(field), list):
                    payload[field] = tuple(payload[field])
            return payload
        return value

    @model_validator(mode="after")
    def validate_complete_authority(self) -> Self:
        required_policies = {
            "discovery-budget-policy-v1",
            "extract-policy-v1",
            "generator-policy-v1",
            "qualification-policy-v1",
            "reader-policy-v1",
            "reviewer-policy-v1",
        }
        if (
            self.policy_versions != tuple(sorted(self.policy_versions))
            or len(set(self.policy_versions)) != len(self.policy_versions)
            or not required_policies.issubset(self.policy_versions)
        ):
            raise ValueError("live acceptance policies are incomplete or noncanonical")
        return self


class AcceptanceBudgetReservationV1(_SelfDigestedModel):
    """Non-refundable fixed-entry read and semantic budget reservation."""

    _digest_field = "reservation_digest"

    schema_version: Literal["acceptance-budget-reservation-v1"]
    acceptance_run_id: _Identifier
    benchmark_manifest_digest: Digest
    nomination_entry_digest: Digest
    benchmark_entry_digest: Digest
    repository_id: _Positive
    repository_full_name: _FullName
    ordinal: Annotated[int, Field(ge=1, le=5)]
    max_files: Literal[25]
    max_source_files: Literal[5]
    max_file_bytes: Literal[131_072]
    max_total_bytes: Literal[524_288]
    max_estimated_tokens: Literal[40_000]
    semantic_candidate_slots: Literal[1]
    campaign_semantic_request_limit: Literal[20]
    reserved_at: _Timestamp
    reservation_digest: Digest | None = None


class AcceptanceFixedCandidateAdmissionV1(_SelfDigestedModel):
    """Exact locked repository identity admitted without a Search-page fiction."""

    _digest_field = "admission_digest"

    schema_version: Literal["acceptance-fixed-candidate-admission-v1"]
    acceptance_run_id: _Identifier
    benchmark_manifest_digest: Digest
    nomination_entry_digest: Digest
    benchmark_entry_digest: Digest
    repository_id: _Positive
    repository_full_name: _FullName
    exact_commit_sha: _Sha
    license_spdx: _Spdx
    ordinal: Annotated[int, Field(ge=1, le=5)]
    admitted_at: _Timestamp
    admission_digest: Digest | None = None


class AcceptanceSemanticRequestReservationV1(_SelfDigestedModel):
    """One non-refundable campaign request slot reserved before provider I/O."""

    _digest_field = "reservation_digest"

    schema_version: Literal["acceptance-semantic-request-reservation-v1"]
    acceptance_run_id: _Identifier
    fixed_candidate_admission_digest: Digest
    repository_id: _Positive
    workflow_spec_authority_digest: Digest
    stage: Literal["extractor", "generator", "reviewer"]
    attempt_no: Annotated[int, Field(ge=1, le=16)]
    request_ordinal: Annotated[int, Field(ge=1, le=20)]
    reserved_at: _Timestamp
    reservation_digest: Digest | None = None


class AcceptanceTerminalClass(StrEnum):
    ELIGIBLE = "eligible"
    BUSINESS_TERMINAL = "business_terminal"
    SYSTEM_FAILURE = "system_failure"


_BusinessOutcome = Literal[
    "filter_rejected",
    "no_workflow",
    "qualification_rejected",
    "validation_rejected",
    "review_rejected",
]
_SystemOutcome = Literal[
    "provider_exhausted",
    "schema_exhausted",
    "evidence_missing",
    "duplicate_effect",
    "unauthorized_effect",
    "secret_exposure",
    "untrusted_execution",
    "harness_failed",
    "rebuild_failed",
]


class AcceptanceWarningV1(StrictFrozenModel):
    warning_code: Annotated[
        str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    ]
    impact: Annotated[str, Field(min_length=1, max_length=512)]
    follow_up: Annotated[str, Field(min_length=1, max_length=512)]
    security_relevant: Literal[False]


class AcceptanceSemanticTelemetryV1(_SelfDigestedModel):
    """One provider-returned semantic response bound to its durable attempt."""

    _digest_field = "telemetry_digest"

    schema_version: Literal["acceptance-semantic-telemetry-v1"]
    live_acceptance_authority_digest: Digest
    stage: Literal["extractor", "generator", "reviewer"]
    workflow_spec_authority_digest: Digest
    attempt_no: Annotated[int, Field(ge=1, le=16)]
    request_id: _Identifier
    actual_model: Literal[
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ]
    prompt_version: _Version
    output_schema_version: _Version
    policy_version: _Version
    prompt_tokens: _NonNegative
    completion_tokens: _NonNegative
    total_tokens: _NonNegative
    latency_ms: _NonNegative
    telemetry_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_provider_response(self) -> Self:
        expected = {
            "extractor": (
                "deepseek-v4-flash",
                "extract-prompt-v1",
                "workflow-spec-v1",
                "extract-policy-v1",
            ),
            "generator": (
                "deepseek-v4-flash",
                "generator-prompt-v1",
                "generation-draft-v1",
                "generator-policy-v1",
            ),
            "reviewer": (
                "deepseek-v4-pro",
                "reviewer-prompt-v1",
                "reviewer-judgment-v1",
                "reviewer-policy-v1",
            ),
        }[self.stage]
        if (
            (
                self.actual_model,
                self.prompt_version,
                self.output_schema_version,
                self.policy_version,
            )
            != expected
            or self.total_tokens
            != self.prompt_tokens + self.completion_tokens
        ):
            raise ValueError("acceptance semantic telemetry is incoherent")
        return self


class AcceptanceScenarioResultV1(_SelfDigestedModel):
    _digest_field = "result_digest"

    schema_version: Literal["acceptance-scenario-result-v1"]
    acceptance_run_id: _Identifier
    scenario_id: _Identifier
    repository_id: _Positive
    repository_full_name: _FullName
    exact_commit_sha: _Sha
    license_spdx: _Spdx
    benchmark_manifest_digest: Digest
    live_acceptance_authority_digest: Digest
    terminal_class: Literal["eligible", "business_terminal", "system_failure"]
    outcome: Literal["eligible_local_candidate"] | _BusinessOutcome | _SystemOutcome
    reason_code: Annotated[
        str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    ]
    evidence_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=128)
    ]
    candidate_funnel: Annotated[tuple[str, ...], Field(min_length=1, max_length=16)]
    reader_order: Literal["readme_docs_examples_manifests_source"]
    reader_file_count: Annotated[int, Field(ge=0, le=25)]
    reader_source_file_count: Annotated[int, Field(ge=0, le=5)]
    reader_total_bytes: Annotated[int, Field(ge=0, le=524_288)]
    reader_estimated_tokens: Annotated[int, Field(ge=0, le=40_000)]
    semantic_request_count: Annotated[int, Field(ge=0, le=20)]
    semantic_attempt_digests: Annotated[tuple[Digest, ...], Field(max_length=20)]
    semantic_telemetry: Annotated[
        tuple[AcceptanceSemanticTelemetryV1, ...],
        Field(max_length=20),
    ]
    actual_models: Annotated[tuple[str, ...], Field(max_length=20)]
    prompt_versions: Annotated[tuple[_Version, ...], Field(max_length=20)]
    schema_versions: Annotated[tuple[_Version, ...], Field(max_length=20)]
    policy_versions: Annotated[tuple[_Version, ...], Field(max_length=20)]
    workflow_fingerprint: Digest | None
    workflow_spec_authority_digest: Digest | None
    eligible_locator: _Identifier | None
    expected_coverage_role: Literal[
        "positive", "positive_multi_workflow", "negative", "borderline"
    ]
    evaluator_matches_observed: bool
    publication_decision: Literal["eligible_for_later_publication", "not_eligible"]
    warnings: Annotated[tuple[AcceptanceWarningV1, ...], Field(max_length=16)]
    recorded_at: _Timestamp
    result_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_terminal_taxonomy(self) -> Self:
        business = {
            "filter_rejected",
            "no_workflow",
            "qualification_rejected",
            "validation_rejected",
            "review_rejected",
        }
        system = {
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
        expected = (
            AcceptanceTerminalClass.BUSINESS_TERMINAL
            if self.outcome in business
            else AcceptanceTerminalClass.SYSTEM_FAILURE
            if self.outcome in system
            else AcceptanceTerminalClass.ELIGIBLE
        )
        if self.terminal_class != expected:
            raise ValueError("acceptance terminal class and outcome disagree")
        reason_by_outcome = {
            "filter_rejected": "deterministic_filter_rejected",
            "no_workflow": "no_reusable_workflow",
            "qualification_rejected": "qualification_policy_rejected",
            "validation_rejected": "skill_validation_rejected",
            "review_rejected": "independent_review_rejected",
            "eligible_local_candidate": "eligible_candidate_completed",
            "provider_exhausted": "provider_outcome_unknown",
            "schema_exhausted": "provider_schema_exhausted",
            "evidence_missing": "state_integrity_conflict",
            "duplicate_effect": "duplicate_effect_observed",
            "unauthorized_effect": "unauthorized_effect_observed",
            "secret_exposure": "secret_exposure_observed",
            "untrusted_execution": "untrusted_execution_observed",
            "harness_failed": "pipeline_permanent_failure",
            "rebuild_failed": "state_rebuild_failed",
        }
        if self.reason_code != reason_by_outcome[self.outcome]:
            raise ValueError("acceptance outcome and reason code disagree")
        if (
            self.evidence_digests != tuple(sorted(self.evidence_digests))
            or len(set(self.evidence_digests)) != len(self.evidence_digests)
        ):
            raise ValueError("scenario evidence must be sorted and unique")
        if (
            self.semantic_attempt_digests
            != tuple(sorted(self.semantic_attempt_digests))
            or len(set(self.semantic_attempt_digests))
            != len(self.semantic_attempt_digests)
            or len(self.semantic_attempt_digests) != self.semantic_request_count
            or len(self.semantic_telemetry) != self.semantic_request_count
            or tuple(
                (
                    item.stage,
                    item.workflow_spec_authority_digest,
                    item.attempt_no,
                )
                for item in self.semantic_telemetry
            )
            != tuple(
                sorted(
                    (
                        item.stage,
                        item.workflow_spec_authority_digest,
                        item.attempt_no,
                    )
                    for item in self.semantic_telemetry
                )
            )
            or self.actual_models
            != tuple(item.actual_model for item in self.semantic_telemetry)
            or self.prompt_versions
            != tuple(item.prompt_version for item in self.semantic_telemetry)
            or self.schema_versions
            != tuple(item.output_schema_version for item in self.semantic_telemetry)
            or self.policy_versions
            != tuple(item.policy_version for item in self.semantic_telemetry)
            or any(
                item.live_acceptance_authority_digest
                != self.live_acceptance_authority_digest
                for item in self.semantic_telemetry
            )
            or (
                self.publication_decision == "eligible_for_later_publication"
                and self.terminal_class != AcceptanceTerminalClass.ELIGIBLE
            )
            or (
                self.terminal_class == AcceptanceTerminalClass.ELIGIBLE
                and self.publication_decision
                != "eligible_for_later_publication"
            )
        ):
            raise ValueError("scenario telemetry or publication decision is incoherent")
        observed_stages = frozenset(
            item.stage for item in self.semantic_telemetry
        )
        required_stages = {
            "filter_rejected": frozenset(),
            "no_workflow": frozenset({"extractor"}),
            "qualification_rejected": frozenset({"extractor"}),
            "validation_rejected": frozenset({"extractor", "generator"}),
            "review_rejected": frozenset(
                {"extractor", "generator", "reviewer"}
            ),
            "eligible_local_candidate": frozenset(
                {"extractor", "generator", "reviewer"}
            ),
        }.get(self.outcome)
        valid_system_prefixes = {
            frozenset(),
            frozenset({"extractor"}),
            frozenset({"extractor", "generator"}),
            frozenset({"extractor", "generator", "reviewer"}),
        }
        if (
            (
                required_stages is not None
                and observed_stages != required_stages
            )
            or (
                required_stages is None
                and observed_stages not in valid_system_prefixes
            )
            or bool(self.semantic_telemetry)
            != bool(self.semantic_request_count)
        ):
            raise ValueError("scenario semantic stages do not match terminal")
        funnel_by_outcome = {
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
        expected_funnel = funnel_by_outcome.get(self.outcome)
        if (
            (
                expected_funnel is not None
                and self.candidate_funnel != expected_funnel
            )
            or (
                self.terminal_class == AcceptanceTerminalClass.ELIGIBLE
                and (
                    self.workflow_fingerprint is None
                    or self.workflow_spec_authority_digest is None
                    or self.eligible_locator is None
                )
            )
            or (
                self.outcome in {"filter_rejected", "no_workflow"}
                and (
                    self.workflow_fingerprint is not None
                    or self.workflow_spec_authority_digest is not None
                )
            )
            or (
                self.outcome
                in {
                    "qualification_rejected",
                    "validation_rejected",
                    "review_rejected",
                }
                and (
                    self.workflow_fingerprint is None
                    or self.workflow_spec_authority_digest is None
                )
            )
            or (
                self.terminal_class != AcceptanceTerminalClass.ELIGIBLE
                and self.eligible_locator is not None
            )
        ):
            raise ValueError("scenario terminal evidence is incoherent")
        return self


class HostedIsolationCapabilityV1(_SelfDigestedModel):
    _digest_field = "capability_digest"

    schema_version: Literal["hosted-isolation-capability-v1"]
    workflow_sha256: Digest
    source_commit_sha: _Sha
    hosted_run_id: _Positive
    run_attempt: Annotated[int, Field(ge=1, le=1_000)]
    runner_image: Annotated[str, Field(min_length=1, max_length=128)]
    isolation_mechanism: Literal["docker_network_none"]
    probe_artifact_locator: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
        ),
    ]
    probe_artifact_digest: Digest
    control_command_digest: Digest
    direct_probe_command_digest: Digest
    child_probe_command_digest: Digest
    control_outcome: Literal["passed"]
    direct_network_outcome: Literal["denied"]
    child_network_outcome: Literal["denied"]
    credential_count: Literal[0]
    state_write_capability: Literal[False]
    synthetic_scan_manifest_digest: Digest
    synthetic_canary_hit_count: Literal[0]
    reviewer_id: _Identifier
    reviewed_at: _Timestamp
    capability_digest: Digest | None = None

    @field_validator("probe_artifact_locator")
    @classmethod
    def validate_probe_locator(cls, value: str) -> str:
        if ".." in value.split("/") or value.startswith("/"):
            raise ValueError("probe artifact locator is outside the closed namespace")
        return value


class OfflineAdversarialRunV1(_SelfDigestedModel):
    _digest_field = "run_digest"

    schema_version: Literal["offline-adversarial-run-v1"]
    acceptance_run_id: _Identifier
    hosted_capability_digest: Digest
    workflow_sha256: Digest
    source_commit_sha: _Sha
    hosted_run_id: _Positive
    run_attempt: Annotated[int, Field(ge=1, le=1_000)]
    isolation_mechanism: Literal["docker_network_none"]
    scenario_matrix_digest: Digest
    required_scenario_ids: Annotated[
        tuple[_Identifier, ...], Field(min_length=15, max_length=64)
    ]
    completed_scenario_ids: Annotated[
        tuple[_Identifier, ...], Field(min_length=15, max_length=64)
    ]
    scenario_result_digests: Annotated[
        tuple[Digest, ...], Field(min_length=15, max_length=64)
    ]
    controlled_scenario_count: Annotated[int, Field(ge=15, le=64)]
    os_syscall_network_denied: Literal[True]
    direct_network_denied: Literal[True]
    child_network_denied: Literal[True]
    untrusted_execution_count: Literal[0]
    unapproved_network_effect_count: Literal[0]
    unauthorized_effect_count: Literal[0]
    synthetic_scan_manifest_digest: Digest
    synthetic_canary_hit_count: Literal[0]
    started_at: _Timestamp
    completed_at: _Timestamp
    run_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_offline_run(self) -> Self:
        sequences = (
            self.required_scenario_ids,
            self.completed_scenario_ids,
            self.scenario_result_digests,
        )
        if any(
            sequence != tuple(sorted(sequence))
            or len(set(sequence)) != len(sequence)
            for sequence in sequences
        ):
            raise ValueError("offline scenario facts must be sorted and unique")
        if (
            self.hosted_capability_digest
            in {
                self.workflow_sha256,
                self.scenario_matrix_digest,
                self.synthetic_scan_manifest_digest,
            }
            or
            self.completed_scenario_ids != self.required_scenario_ids
            or self.controlled_scenario_count != len(self.required_scenario_ids)
            or len(self.scenario_result_digests) != self.controlled_scenario_count
            or self.completed_at < self.started_at
        ):
            raise ValueError("offline adversarial run is incomplete or non-monotonic")
        return self


class ReplayIntentV1(_SelfDigestedModel):
    """The sole durable replay delta, recorded before the state transition."""

    _digest_field = "replay_digest"

    schema_version: Literal["replay-intent-v1"]
    acceptance_run_id: _Identifier
    repository_id: _Positive
    source_commit_sha: _Sha
    workflow_fingerprint: Digest
    workflow_spec_authority_digest: Digest
    replay_policy_version: Literal["acceptance-replay-policy-v1"]
    benchmark_manifest_digest: Digest
    before_state_commit_sha: _Sha
    before_state_root_digest: Digest
    before_projection_digest: Digest
    before_object_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=512)
    ]
    semantic_request_count: Literal[0]
    remote_effect_count: Literal[0]
    recorded_at: _Timestamp
    replay_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_replay_intent(self) -> Self:
        if (
            self.before_object_digests != tuple(sorted(self.before_object_digests))
            or len(set(self.before_object_digests)) != len(self.before_object_digests)
        ):
            raise ValueError("replay intent object set is not exact")
        return self


class ReplayEvidenceV1(_SelfDigestedModel):
    _digest_field = "replay_digest"

    schema_version: Literal["replay-evidence-v1"]
    acceptance_run_id: _Identifier
    repository_id: _Positive
    source_commit_sha: _Sha
    workflow_fingerprint: Digest
    workflow_spec_authority_digest: Digest
    replay_policy_version: Literal["acceptance-replay-policy-v1"]
    replay_fact_digest: Digest
    allowed_delta_fact_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=2)
    ]
    benchmark_manifest_digest: Digest
    before_state_commit_sha: _Sha
    before_state_root_digest: Digest
    after_state_commit_sha: _Sha
    after_state_root_digest: Digest
    before_projection_digest: Digest
    after_projection_digest: Digest
    before_object_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=512)
    ]
    after_object_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=512)
    ]
    scenario_result_digests: Annotated[
        tuple[Digest, ...], Field(min_length=5, max_length=5)
    ]
    eligible_locators: Annotated[tuple[_Identifier, ...], Field(max_length=60)]
    semantic_attempt_count_before: _NonNegative
    semantic_attempt_count_after: _NonNegative
    semantic_request_count: Literal[0]
    duplicate_workflow_spec_count: Literal[0]
    duplicate_skill_count: Literal[0]
    duplicate_fact_count: Literal[0]
    remote_effect_count: Literal[0]
    recorded_at: _Timestamp
    replay_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_exact_replay(self) -> Self:
        if (
            self.before_state_commit_sha == self.after_state_commit_sha
            or self.before_state_root_digest == self.after_state_root_digest
            or self.before_projection_digest != self.after_projection_digest
            or self.allowed_delta_fact_digests != (self.replay_fact_digest,)
            or self.before_object_digests != self.after_object_digests
            or self.before_object_digests
            != tuple(sorted(self.before_object_digests))
            or len(set(self.before_object_digests))
            != len(self.before_object_digests)
            or self.semantic_attempt_count_before
            != self.semantic_attempt_count_after
            or self.scenario_result_digests
            != tuple(sorted(self.scenario_result_digests))
            or len(set(self.scenario_result_digests)) != 5
            or self.eligible_locators != tuple(sorted(self.eligible_locators))
            or len(set(self.eligible_locators)) != len(self.eligible_locators)
        ):
            raise ValueError("replay evidence is not an exact zero-effect projection")
        return self


class ChangedSourceEvidenceV1(_SelfDigestedModel):
    _digest_field = "changed_source_digest"

    schema_version: Literal["changed-source-evidence-v1"]
    acceptance_run_id: _Identifier
    repository_id: _Positive
    prior_source_commit_sha: _Sha
    new_source_commit_sha: _Sha
    prior_workflow_fingerprint: Digest
    new_workflow_fingerprint: Digest
    prior_workflow_spec_authority_digest: Digest
    new_workflow_spec_authority_digest: Digest
    prior_package_digest: Digest
    new_package_digest: Digest
    prior_lineage_binding_digest: Digest
    lineage_approval_record_digest: Digest
    affected_evidence_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=128)
    ]
    planned_publication_key: Digest
    planned_lineage_id: Digest
    publication_effect_count: Literal[0]
    recorded_at: _Timestamp
    changed_source_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_changed_source(self) -> Self:
        pairs = (
            (self.prior_source_commit_sha, self.new_source_commit_sha),
            (self.prior_workflow_fingerprint, self.new_workflow_fingerprint),
            (
                self.prior_workflow_spec_authority_digest,
                self.new_workflow_spec_authority_digest,
            ),
            (self.prior_package_digest, self.new_package_digest),
        )
        if any(old == new for old, new in pairs):
            raise ValueError("changed-source evidence does not establish new authority")
        if (
            self.affected_evidence_digests
            != tuple(sorted(self.affected_evidence_digests))
            or len(set(self.affected_evidence_digests))
            != len(self.affected_evidence_digests)
        ):
            raise ValueError("affected evidence must be sorted and unique")
        return self


class PublicationReplayCompletionV1(_SelfDigestedModel):
    _digest_field = "completion_digest"

    schema_version: Literal["publication-replay-completion-v1"]
    acceptance_run_id: _Identifier
    replay_intent_digest: Digest
    repository_id: _Positive
    source_commit_sha: _Sha
    workflow_fingerprint: Digest
    workflow_spec_authority_digest: Digest
    publication_policy_version: _Version
    publication_key: Digest
    publication_marker: Digest
    target_repository_id: _Positive
    target_repository_full_name: _FullName
    pull_request_number: _Positive
    head_branch: _Ref
    head_commit_sha: _Sha
    draft: Literal[True]
    open: Literal[True]
    prior_publication_receipt_digest: Digest
    before_remote_observation_digest: Digest
    after_remote_observation_digest: Digest
    branch_create_count: Literal[0]
    commit_create_count: Literal[0]
    pull_request_create_count: Literal[0]
    pull_request_update_count: Literal[0]
    reviewer_request_count: Literal[0]
    completion_recorded_at: _Timestamp
    completion_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_replay_completion(self) -> Self:
        if (
            self.before_remote_observation_digest
            != self.after_remote_observation_digest
        ):
            raise ValueError("publication replay changed the remote observation")
        return self


class ChangedSourceDraftUpdateCompletionV1(_SelfDigestedModel):
    _digest_field = "completion_digest"

    schema_version: Literal["changed-source-draft-update-completion-v1"]
    acceptance_run_id: _Identifier
    changed_source_intent_digest: Digest
    repository_id: _Positive
    prior_source_commit_sha: _Sha
    new_source_commit_sha: _Sha
    prior_workflow_fingerprint: Digest
    new_workflow_fingerprint: Digest
    prior_workflow_spec_authority_digest: Digest
    new_workflow_spec_authority_digest: Digest
    publication_policy_version: _Version
    publication_key: Digest
    publication_marker: Digest
    target_repository_id: _Positive
    target_repository_full_name: _FullName
    pull_request_number: _Positive
    head_branch: _Ref
    previous_head_commit_sha: _Sha
    new_head_commit_sha: _Sha
    previous_desired_revision_digest: Digest
    new_desired_revision_digest: Digest
    previous_lineage_id: Digest
    new_lineage_id: Digest
    prior_lineage_binding_digest: Digest
    lineage_approval_record_digest: Digest
    remote_reconciliation_digest: Digest
    new_branch_count: Literal[0]
    new_pull_request_count: Literal[0]
    new_reviewer_request_count: Literal[0]
    head_update_count: Literal[1]
    remote_commit_count: Literal[1]
    draft: Literal[True]
    open: Literal[True]
    completion_recorded_at: _Timestamp
    completion_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_changed_update(self) -> Self:
        changed_pairs = (
            (self.prior_source_commit_sha, self.new_source_commit_sha),
            (self.prior_workflow_fingerprint, self.new_workflow_fingerprint),
            (
                self.prior_workflow_spec_authority_digest,
                self.new_workflow_spec_authority_digest,
            ),
            (
                self.previous_desired_revision_digest,
                self.new_desired_revision_digest,
            ),
            (self.previous_head_commit_sha, self.new_head_commit_sha),
        )
        if any(old == new for old, new in changed_pairs):
            raise ValueError("changed-source completion did not change exact authority")
        if self.previous_lineage_id != self.new_lineage_id:
            raise ValueError("changed-source completion changed stable lineage")
        return self


class ProbeCleanupTargetV1(_SelfDigestedModel):
    _digest_field = "target_digest"

    schema_version: Literal["probe-cleanup-target-v1"]
    target_repository_id: _Positive
    pull_request_number: _Positive
    head_branch: _Ref
    head_commit_sha: _Sha
    target_digest: Digest | None = None


class GateB4BindingV1(_SelfDigestedModel):
    _digest_field = "binding_digest"

    schema_version: Literal["gate-b4-binding-v1"]
    acceptance_run_id: _Identifier
    source_commit_sha: _Sha
    discover_workflow_sha256: Digest
    publish_workflow_sha256: Digest
    canary_workflow_sha256: Digest
    acceptance_workflow_sha256: Digest
    installation_id: _Positive
    catalog_repository_id: _Positive
    catalog_repository_full_name: _FullName
    ruleset_id: _Positive
    protected_environment: _Identifier
    reviewer_configuration_digest: Digest
    installation_identity_digest: Digest
    default_branch_before_sha: _Sha
    default_branch_after_sha: _Sha
    draft_creation_passed: Literal[True]
    reviewer_request_passed: Literal[True]
    default_branch_write_denied: Literal[True]
    merge_denied: Literal[True]
    ruleset_admin_denied: Literal[True]
    unauthorized_repository_denied: Literal[True]
    secret_access_denied: Literal[True]
    cleanup_targets: Annotated[
        tuple[ProbeCleanupTargetV1, ...], Field(min_length=1, max_length=16)
    ]
    recorded_at: _Timestamp
    binding_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_gate_binding(self) -> Self:
        target_digests = tuple(target.target_digest for target in self.cleanup_targets)
        if (
            self.default_branch_before_sha != self.default_branch_after_sha
            or target_digests != tuple(sorted(target_digests))
            or len(set(target_digests)) != len(target_digests)
        ):
            raise ValueError("Gate B4 binding or cleanup manifest is incoherent")
        return self


class HumanSkillReviewAttestationV1(_SelfDigestedModel):
    _digest_field = "attestation_digest"

    schema_version: Literal["human-skill-review-attestation-v1"]
    acceptance_run_id: _Identifier
    target_repository_id: _Positive
    target_repository_full_name: _FullName
    pull_request_number: _Positive
    pr_head_sha: _Sha
    source_commit_sha: _Sha
    package_digest: Digest
    publication_marker_digest: Digest
    verdict: Literal["publishable", "publishable_with_changes", "rejected"]
    usefulness_checked: bool
    fidelity_checked: bool
    provenance_license_checked: bool
    instruction_safety_checked: bool
    diff_scope_checked: bool
    reviewer_id: _Identifier
    reviewed_at: _Timestamp
    attestation_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_complete_checklist(self) -> Self:
        if not all(
            (
                self.usefulness_checked,
                self.fidelity_checked,
                self.provenance_license_checked,
                self.instruction_safety_checked,
                self.diff_scope_checked,
            )
        ):
            raise ValueError("human Skill review checklist is incomplete")
        return self


class ProbeCleanupAttestationV1(_SelfDigestedModel):
    _digest_field = "attestation_digest"

    schema_version: Literal["probe-cleanup-attestation-v1"]
    acceptance_run_id: _Identifier
    gate_b4_binding_digest: Digest
    actor_id: _Identifier
    cleanup_target_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=16)
    ]
    closed_pull_request_count: _Positive
    deleted_branch_count: _Positive
    default_branch_before_sha: _Sha
    default_branch_after_sha: _Sha
    value_pull_request_number: _Positive
    value_pr_head_sha: _Sha
    value_pr_draft: Literal[True]
    value_pr_open: Literal[True]
    observed_at: _Timestamp
    attestation_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_cleanup(self) -> Self:
        if (
            self.cleanup_target_digests
            != tuple(sorted(self.cleanup_target_digests))
            or len(set(self.cleanup_target_digests))
            != len(self.cleanup_target_digests)
            or self.closed_pull_request_count != len(self.cleanup_target_digests)
            or self.deleted_branch_count != len(self.cleanup_target_digests)
            or self.default_branch_before_sha != self.default_branch_after_sha
        ):
            raise ValueError("probe cleanup attestation is incomplete")
        return self


class ReviewerCalibrationV1(_SelfDigestedModel):
    _digest_field = "calibration_digest"

    schema_version: Literal["reviewer-calibration-v1"]
    acceptance_run_id: _Identifier
    label_digests: Annotated[tuple[Digest, ...], Field(min_length=10, max_length=256)]
    review_result_digests: Annotated[
        tuple[Digest, ...], Field(min_length=10, max_length=256)
    ]
    case_count: Annotated[int, Field(ge=10, le=256)]
    agreement_count: Annotated[int, Field(ge=0, le=256)]
    agreement_rate: Annotated[float, Field(ge=0.0, le=1.0)]
    cohen_kappa: Annotated[float, Field(ge=-1.0, le=1.0)]
    disagreement_case_digests: Annotated[
        tuple[Digest, ...], Field(max_length=256)
    ]
    advice_only: Literal[True]
    calibration_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_calibration(self) -> Self:
        sequences = (
            self.label_digests,
            self.review_result_digests,
            self.disagreement_case_digests,
        )
        if any(
            sequence != tuple(sorted(sequence))
            or len(set(sequence)) != len(sequence)
            for sequence in sequences
        ):
            raise ValueError("reviewer calibration digests are not canonical")
        if (
            len(self.label_digests) != self.case_count
            or len(self.review_result_digests) != self.case_count
            or self.agreement_count > self.case_count
            or abs(self.agreement_rate - self.agreement_count / self.case_count)
            > 1e-12
            or len(self.disagreement_case_digests)
            != self.case_count - self.agreement_count
        ):
            raise ValueError("reviewer calibration accounting does not reconcile")
        return self


HARD_ACCEPTANCE_GATES: Final[tuple[str, ...]] = (
    "benchmark_human_lock",
    "five_fixed_sha_repositories",
    "controlled_scenario_coverage",
    "hosted_kernel_isolation",
    "synthetic_secret_absence",
    "no_untrusted_execution",
    "closed_provider_policy",
    "license_custody",
    "provenance_custody",
    "evidence_integrity",
    "identical_replay_zero_effects",
    "changed_source_same_draft_update",
    "fresh_gate_b4_binding",
    "permission_causal_denials",
    "open_value_draft",
    "exact_head_human_review",
    "probe_cleanup_attestation",
    "report_rebuild",
    "all_44_requirements",
)


class AcceptanceGateResultV1(_SelfDigestedModel):
    _digest_field = "gate_digest"

    schema_version: Literal["acceptance-gate-result-v1"]
    acceptance_run_id: _Identifier
    gate_id: Literal[*HARD_ACCEPTANCE_GATES]
    blocking: Literal[True]
    status: Literal["PASS", "FAIL", "INCOMPLETE"]
    evidence_digests: Annotated[tuple[Digest, ...], Field(max_length=256)]
    evaluated_at: _Timestamp
    gate_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_gate_evidence(self) -> Self:
        if (
            self.evidence_digests != tuple(sorted(self.evidence_digests))
            or len(set(self.evidence_digests)) != len(self.evidence_digests)
            or (self.status == "PASS" and not self.evidence_digests)
        ):
            raise ValueError("acceptance gate evidence is not canonical")
        return self


class AcceptanceEvidenceRootV1(_SelfDigestedModel):
    _digest_field = "root_digest"

    schema_version: Literal["acceptance-evidence-root-v1"]
    acceptance_run_id: _Identifier
    benchmark_manifest_digest: Digest
    gate_results: Annotated[
        tuple[AcceptanceGateResultV1, ...], Field(min_length=19, max_length=19)
    ]
    evidence_digests: Annotated[
        tuple[Digest, ...], Field(min_length=1, max_length=4_096)
    ]
    prior_root_digest: Digest | None
    created_at: _Timestamp
    root_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_evidence_root(self) -> Self:
        gate_ids = tuple(gate.gate_id for gate in self.gate_results)
        if gate_ids != HARD_ACCEPTANCE_GATES:
            raise ValueError("acceptance root does not contain the exact hard gates")
        if any(gate.acceptance_run_id != self.acceptance_run_id for gate in self.gate_results):
            raise ValueError("acceptance root contains a cross-run gate")
        if (
            self.evidence_digests != tuple(sorted(self.evidence_digests))
            or len(set(self.evidence_digests)) != len(self.evidence_digests)
        ):
            raise ValueError("acceptance root evidence is not canonical")
        return self


class AcceptanceReleaseVerdictV1(_SelfDigestedModel):
    _digest_field = "verdict_digest"

    schema_version: Literal["acceptance-release-verdict-v1"]
    acceptance_run_id: _Identifier
    evidence_root_digest: Digest
    gate_digests: Annotated[tuple[Digest, ...], Field(min_length=19, max_length=19)]
    verdict: Literal["PASS", "FAIL", "INCOMPLETE"]
    warnings: Annotated[tuple[AcceptanceWarningV1, ...], Field(max_length=16)]
    evaluated_at: _Timestamp
    verdict_digest: Digest | None = None

    @classmethod
    def from_evidence_root(
        cls,
        root: AcceptanceEvidenceRootV1,
        *,
        warnings: tuple[AcceptanceWarningV1, ...] = (),
        evaluated_at: str,
    ) -> AcceptanceReleaseVerdictV1:
        statuses = tuple(gate.status for gate in root.gate_results)
        verdict = (
            "PASS"
            if all(status == "PASS" for status in statuses)
            else "FAIL"
            if any(status == "FAIL" for status in statuses)
            else "INCOMPLETE"
        )
        return cls(
            schema_version="acceptance-release-verdict-v1",
            acceptance_run_id=root.acceptance_run_id,
            evidence_root_digest=root.root_digest,
            gate_digests=tuple(gate.gate_digest for gate in root.gate_results),
            verdict=verdict,
            warnings=warnings,
            evaluated_at=evaluated_at,
        )

    @model_validator(mode="after")
    def validate_verdict(self) -> Self:
        if len(set(self.gate_digests)) != len(self.gate_digests):
            raise ValueError("release verdict contains duplicate gate evidence")
        return self
