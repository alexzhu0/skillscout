"""Independent completed-first Phase 3 composition and orchestration boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Callable, Final

from pydantic import Field

from skillscout.adapters.openai_generate import (
    DEFAULT_GENERATOR_MODEL,
    GENERATOR_POLICY_VERSION,
    GENERATOR_PROMPT_VERSION,
    MAX_GENERATOR_INPUT_BYTES,
    MAX_GENERATOR_OUTPUT_TOKENS,
)
from skillscout.adapters.openai_review import (
    DEFAULT_REVIEWER_MODEL,
    MAX_REVIEWER_INPUT_BYTES,
    MAX_REVIEWER_OUTPUT_TOKENS,
)
from skillscout.application.candidate_source import load_candidate_subject
from skillscout.application.ports import (
    CandidateSourceUnavailable,
    ErrorCode,
    PhaseTwoCandidateSource,
    SafeFailure,
)
from skillscout.domain.candidate_authority import (
    CandidateExecutionAuthorityV1,
    candidate_execution_authority,
)
from skillscout.domain.models import PHASE_THREE_PROFILE_VERSION, StrictFrozenModel
from skillscout.domain.qualification import (
    QUALIFICATION_POLICY_VERSION,
    QUALIFICATION_REPORT_SCHEMA_VERSION,
)
from skillscout.domain.review import (
    ELIGIBILITY_POLICY_VERSION,
    REVIEW_OUTPUT_SCHEMA_VERSION,
    REVIEW_POLICY_VERSION,
    REVIEW_PROMPT_VERSION,
)
from skillscout.domain.skill_artifacts import (
    GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION,
    GENERATION_DRAFT_SCHEMA_VERSION,
    PROVENANCE_SCHEMA_VERSION,
    RENDERER_VERSION,
)
from skillscout.domain.validation import (
    APPROVED_PHASE3_LOCK_DIGEST,
    CUSTOM_VALIDATION_POLICY_VERSION,
    OFFICIAL_VALIDATOR_DISTRIBUTION,
    OFFICIAL_VALIDATOR_DISTRIBUTION_HASH,
    OFFICIAL_VALIDATOR_VERSION,
    VALIDATION_REPORT_SCHEMA_VERSION,
)

PHASE_THREE_STAGE_SEQUENCE: Final[tuple[str, ...]] = (
    "qualifier",
    "generator",
    "validator",
    "reviewer",
)
PHASE_THREE_PRODUCER_VERSION: Final = "phase3-v1"
PHASE_THREE_RETRY_POLICY_VERSION: Final = "phase3-runner-retry-v1"
PHASE_THREE_BUDGET_POLICY_VERSION: Final = "phase3-budget-v1"


class PhaseThreeRuntimeProfile(StrictFrozenModel):
    """Versioned hard limits and configurable identities known before lookup."""

    profile_version: str = PHASE_THREE_PROFILE_VERSION
    producer_version: str = PHASE_THREE_PRODUCER_VERSION
    retry_policy_version: str = PHASE_THREE_RETRY_POLICY_VERSION
    budget_policy_version: str = PHASE_THREE_BUDGET_POLICY_VERSION
    configured_generator_model_id: str = DEFAULT_GENERATOR_MODEL
    configured_reviewer_model_id: str = DEFAULT_REVIEWER_MODEL
    max_candidates: Annotated[int, Field(ge=1, le=3)] = 3
    max_generator_attempts: Annotated[int, Field(ge=1, le=3)] = 3
    max_reviewer_attempts: Annotated[int, Field(ge=1, le=3)] = 3
    max_generator_input_bytes: Annotated[
        int, Field(ge=1, le=MAX_GENERATOR_INPUT_BYTES)
    ] = MAX_GENERATOR_INPUT_BYTES
    max_reviewer_input_bytes: Annotated[
        int, Field(ge=1, le=MAX_REVIEWER_INPUT_BYTES)
    ] = MAX_REVIEWER_INPUT_BYTES
    max_generator_output_tokens: Annotated[
        int, Field(ge=1, le=MAX_GENERATOR_OUTPUT_TOKENS)
    ] = MAX_GENERATOR_OUTPUT_TOKENS
    max_reviewer_output_tokens: Annotated[
        int, Field(ge=1, le=MAX_REVIEWER_OUTPUT_TOKENS)
    ] = MAX_REVIEWER_OUTPUT_TOKENS


@dataclass(frozen=True)
class PhaseThreeDependencies:
    """Lazy factories; none may be invoked before verified source and authority."""

    completed_projector_factory: Callable[[], object]
    mutable_state_factory: Callable[[], object]
    generator_factory: Callable[[], object]
    validator_factory: Callable[[], object]
    reviewer_factory: Callable[[], object]
    artifact_projector_factory: Callable[[], object]


@dataclass(frozen=True)
class PhaseThreeApplicationResult:
    """One pre-run, completed-reuse, or newly orchestrated candidate result."""

    outcome: str
    authority: CandidateExecutionAuthorityV1 | None = None
    completed_projection: object | None = None
    terminal_summary: object | None = None
    artifacts: object | None = None


def _execution_authority(
    *,
    source: object,
    profile: PhaseThreeRuntimeProfile,
) -> CandidateExecutionAuthorityV1:
    descriptor = source.descriptor
    return candidate_execution_authority(
        workflow_spec_authority=source.workflow_spec_authority,
        selected_workflow_fingerprint=descriptor.selected_workflow_fingerprint,
        prior_lineage_binding_digest=descriptor.prior_lineage_binding_digest,
        qualification_policy_version=QUALIFICATION_POLICY_VERSION,
        qualification_report_schema_version=QUALIFICATION_REPORT_SCHEMA_VERSION,
        configured_generator_model_id=profile.configured_generator_model_id,
        generator_prompt_version=GENERATOR_PROMPT_VERSION,
        generator_output_schema_version=GENERATION_DRAFT_SCHEMA_VERSION,
        generator_policy_version=GENERATOR_POLICY_VERSION,
        renderer_version=RENDERER_VERSION,
        artifact_schema_version=GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION,
        provenance_schema_version=PROVENANCE_SCHEMA_VERSION,
        official_validator_distribution=OFFICIAL_VALIDATOR_DISTRIBUTION,
        official_validator_version=OFFICIAL_VALIDATOR_VERSION,
        official_validator_distribution_hash=OFFICIAL_VALIDATOR_DISTRIBUTION_HASH,
        approved_lock_digest=APPROVED_PHASE3_LOCK_DIGEST,
        custom_validation_policy_version=CUSTOM_VALIDATION_POLICY_VERSION,
        validation_report_schema_version=VALIDATION_REPORT_SCHEMA_VERSION,
        configured_reviewer_model_id=profile.configured_reviewer_model_id,
        reviewer_prompt_version=REVIEW_PROMPT_VERSION,
        reviewer_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
        reviewer_policy_version=REVIEW_POLICY_VERSION,
        eligibility_policy_version=ELIGIBILITY_POLICY_VERSION,
        phase3_producer_version=profile.producer_version,
        phase3_profile_version=profile.profile_version,
        retry_policy_version=profile.retry_policy_version,
    )


class PhaseThreeApplication:
    """Resolve source, bind authority, project completed state, then mutate."""

    def __init__(
        self,
        *,
        source: PhaseTwoCandidateSource,
        profile: PhaseThreeRuntimeProfile,
        dependencies: PhaseThreeDependencies,
    ) -> None:
        self._source = source
        self._profile = profile
        self._dependencies = dependencies

    def run(
        self,
        descriptor_path: Path,
        *,
        output_directory: Path | None = None,
    ) -> PhaseThreeApplicationResult:
        try:
            resolved = load_candidate_subject(descriptor_path, self._source)
        except CandidateSourceUnavailable:
            return PhaseThreeApplicationResult(
                outcome=ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE.value
            )
        authority = _execution_authority(source=resolved, profile=self._profile)

        projector = self._dependencies.completed_projector_factory()
        try:
            lookup = getattr(projector, "find_completed_candidate")
            completed = lookup(authority)
        finally:
            close = getattr(projector, "close", None)
            if callable(close):
                close()
        if completed is not None:
            return PhaseThreeApplicationResult(
                outcome=completed.terminal_summary.outcome
                if hasattr(completed, "terminal_summary")
                else "completed_reuse",
                authority=authority,
                completed_projection=completed,
            )

        mutable = self._dependencies.mutable_state_factory()
        try:
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
        finally:
            close = getattr(mutable, "close", None)
            if callable(close):
                close()
