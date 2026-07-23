"""Independent completed-first Phase 3 composition and orchestration boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Callable, Final, Mapping
from uuid import uuid4

from pydantic import Field

from skillscout.adapters.openai_generate import (
    DEFAULT_GENERATOR_MODEL,
    GENERATOR_POLICY_VERSION,
    GENERATOR_PROMPT_VERSION,
    MAX_GENERATOR_INPUT_BYTES,
    MAX_GENERATOR_OUTPUT_TOKENS,
    GenerationRequestV1,
    GenerationResult,
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
    LINEAGE_RESOLUTION_SCHEMA_VERSION,
    LineageResolutionV1,
    candidate_execution_authority,
    derive_new_lineage,
)
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.models import (
    CANDIDATE_CHECKPOINT_PROFILE_VERSION,
    CANDIDATE_CHECKPOINT_SCHEMA_VERSION,
    PHASE_THREE_GENESIS_CHECKPOINT_HASH,
    PHASE_THREE_PROFILE_VERSION,
    PHASE_THREE_SCHEMA_VERSION,
    CandidateResumeEventV1,
    CandidateRunIdentityV1,
    CandidateStageAttemptV1,
    CandidateStageCheckpointV1,
    CandidateStageResultV1,
    PhaseThreeStageV1,
    StrictFrozenModel,
    VerifiedCandidateRunChain,
)
from skillscout.domain.qualification import (
    QUALIFICATION_POLICY_VERSION,
    QUALIFICATION_REPORT_SCHEMA_VERSION,
    QUALIFICATION_THRESHOLD_VERSION,
    evaluate_qualification_checks,
    qualification_report,
    qualification_report_bytes,
    qualification_report_digest,
)
from skillscout.domain.review import (
    ELIGIBILITY_POLICY_VERSION,
    REVIEW_OUTPUT_SCHEMA_VERSION,
    REVIEW_POLICY_VERSION,
    REVIEW_PROMPT_VERSION,
    candidate_terminal_summary,
    generator_outcome_evidence,
    review_attestation,
    review_attestation_bytes,
    review_disposition,
)
from skillscout.domain.skill_artifacts import (
    GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION,
    GENERATION_DRAFT_SCHEMA_VERSION,
    PROVENANCE_SCHEMA_VERSION,
    RENDERER_VERSION,
    GenerationAuthorityProjectionV1,
    render_skill_package,
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
    run_id_factory: Callable[[], str] = lambda: f"phase3-{uuid4().hex}"


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


def _self_hash(values: Mapping[str, object], field: str) -> str:
    return sha256_digest(
        {
            key: (
                value.model_dump(mode="json", exclude_none=False)
                if hasattr(value, "model_dump")
                else value
            )
            for key, value in values.items()
            if key != field
        }
    )


def _new_chain(
    run_id: str,
    authority: CandidateExecutionAuthorityV1,
) -> VerifiedCandidateRunChain:
    identity_values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": run_id,
        "candidate_execution_authority": authority,
        "candidate_execution_authority_digest": authority.authority_digest,
    }
    identity = CandidateRunIdentityV1(
        **identity_values,
        identity_digest=_self_hash(identity_values, "identity_digest"),
    )
    event_values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": run_id,
        "candidate_execution_authority_digest": authority.authority_digest,
        "event_index": 0,
        "prior_event_hash": None,
        "checkpoint_hash": None,
        "checkpoint_output_hash": None,
        "next_stage": PhaseThreeStageV1.QUALIFIER,
        "terminal": False,
    }
    genesis = CandidateResumeEventV1(
        **event_values,
        event_hash=_self_hash(event_values, "event_hash"),
    )
    return VerifiedCandidateRunChain(
        identity=identity,
        attempts=(),
        results=(),
        checkpoints=(),
        resume_events=(genesis,),
    )


def _append_success(
    chain: VerifiedCandidateRunChain,
    *,
    stage: PhaseThreeStageV1,
    attempt_no: int,
    outcome_code: str,
    payload: object,
) -> VerifiedCandidateRunChain:
    authority = chain.identity.candidate_execution_authority
    stage_index = tuple(PhaseThreeStageV1).index(stage)
    if stage_index != len(chain.results):
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
    payload_digest = sha256_digest(canonical_json_bytes(payload))
    previous_checkpoint_hash = (
        chain.checkpoints[-1].checkpoint_hash
        if chain.checkpoints
        else PHASE_THREE_GENESIS_CHECKPOINT_HASH
    )
    previous_output_hash = chain.results[-1].output_hash if chain.results else None
    attempt_values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": chain.identity.run_id,
        "candidate_execution_authority_digest": authority.authority_digest,
        "stage": stage,
        "stage_index": stage_index,
        "attempt_no": attempt_no,
        "previous_checkpoint_hash": previous_checkpoint_hash,
        "previous_output_hash": previous_output_hash,
        "producer_version": authority.phase3_producer_version,
        "profile_version": authority.phase3_profile_version,
        "retry_policy_version": authority.retry_policy_version,
        "status": "succeeded",
        "outcome_code": outcome_code,
        "payload_digest": payload_digest,
    }
    attempt = CandidateStageAttemptV1(
        **attempt_values,
        attempt_hash=_self_hash(attempt_values, "attempt_hash"),
    )
    output_hash = sha256_digest(
        {
            "schema_version": PHASE_THREE_SCHEMA_VERSION,
            "run_id": chain.identity.run_id,
            "stage": stage.value,
            "attempt_hash": attempt.attempt_hash,
            "payload_digest": payload_digest,
            "outcome_code": outcome_code,
        }
    )
    result_values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": chain.identity.run_id,
        "candidate_execution_authority_digest": authority.authority_digest,
        "stage": stage,
        "stage_index": stage_index,
        "attempt_no": attempt_no,
        "attempt_hash": attempt.attempt_hash,
        "previous_result_hash": (
            chain.results[-1].result_hash if chain.results else None
        ),
        "producer_version": authority.phase3_producer_version,
        "profile_version": authority.phase3_profile_version,
        "retry_policy_version": authority.retry_policy_version,
        "outcome_code": outcome_code,
        "payload_digest": payload_digest,
        "output_hash": output_hash,
    }
    result = CandidateStageResultV1(
        **result_values,
        result_hash=_self_hash(result_values, "result_hash"),
    )
    stages = tuple(PhaseThreeStageV1)
    next_stage = stages[stage_index + 1] if stage_index + 1 < len(stages) else None
    checkpoint_values: dict[str, object] = {
        "schema_version": CANDIDATE_CHECKPOINT_SCHEMA_VERSION,
        "profile_version": CANDIDATE_CHECKPOINT_PROFILE_VERSION,
        "run_id": chain.identity.run_id,
        "candidate_execution_authority_digest": authority.authority_digest,
        "stage": stage,
        "stage_index": stage_index,
        "attempt_no": attempt_no,
        "result_hash": result.result_hash,
        "output_hash": output_hash,
        "previous_checkpoint_hash": previous_checkpoint_hash,
        "next_stage": next_stage,
        "terminal": next_stage is None,
    }
    checkpoint = CandidateStageCheckpointV1(
        **checkpoint_values,
        checkpoint_hash=_self_hash(checkpoint_values, "checkpoint_hash"),
    )
    prior_event = chain.resume_events[-1]
    event_values: dict[str, object] = {
        "schema_version": PHASE_THREE_SCHEMA_VERSION,
        "run_id": chain.identity.run_id,
        "candidate_execution_authority_digest": authority.authority_digest,
        "event_index": len(chain.resume_events),
        "prior_event_hash": prior_event.event_hash,
        "checkpoint_hash": checkpoint.checkpoint_hash,
        "checkpoint_output_hash": checkpoint.output_hash,
        "next_stage": checkpoint.next_stage,
        "terminal": checkpoint.terminal,
    }
    event = CandidateResumeEventV1(
        **event_values,
        event_hash=_self_hash(event_values, "event_hash"),
    )
    return VerifiedCandidateRunChain(
        identity=chain.identity,
        attempts=(*chain.attempts, attempt),
        results=(*chain.results, result),
        checkpoints=(*chain.checkpoints, checkpoint),
        resume_events=(*chain.resume_events, event),
    )


class PhaseThreeRunner:
    """Exact semantic cascade over the dedicated candidate ledger."""

    def __init__(
        self,
        *,
        state: object,
        source: object,
        authority: CandidateExecutionAuthorityV1,
        profile: PhaseThreeRuntimeProfile,
        dependencies: PhaseThreeDependencies,
    ) -> None:
        self.state = state
        self.source = source
        self.authority = authority
        self.profile = profile
        self.dependencies = dependencies

    def run(self) -> tuple[object, dict[str, bytes]]:
        resumable = self.state.find_resumable_candidate(self.authority)
        if resumable is not None:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        chain = _new_chain(self.dependencies.run_id_factory(), self.authority)
        self.state.persist_candidate_chain(chain, status="running")

        report = qualification_report(
            checks=evaluate_qualification_checks(
                self.authority.workflow_spec_authority.workflow_spec
            ),
            selected_workflow_fingerprint=self.authority.selected_workflow_fingerprint,
            workflow_spec_authority=self.authority.workflow_spec_authority,
            candidate_execution_authority=self.authority,
        )
        chain = _append_success(
            chain,
            stage=PhaseThreeStageV1.QUALIFIER,
            attempt_no=1,
            outcome_code="accepted" if report.passed else "qualification_rejected",
            payload=report,
        )
        self.state.persist_candidate_chain(chain, status="running")
        artifacts = {"qualification_report": qualification_report_bytes(report)}
        if not report.passed:
            lineage = LineageResolutionV1(
                schema_version=LINEAGE_RESOLUTION_SCHEMA_VERSION,
                status="not_evaluated_qualification_rejected",
                lineage_authority_digest=None,
                lineage_id=None,
                stable_slug=None,
                initial_workflow_spec_authority_digest=None,
                reason_codes=("qualification_rejected",),
            )
            return self._terminal(
                chain=chain,
                outcome="qualification_rejected",
                report=report,
                lineage=lineage,
                artifacts=artifacts,
            )

        if self.authority.prior_lineage_binding_digest is not None:
            lineage = LineageResolutionV1(
                schema_version=LINEAGE_RESOLUTION_SCHEMA_VERSION,
                status="lineage_rejected",
                lineage_authority_digest=None,
                lineage_id=None,
                stable_slug=None,
                initial_workflow_spec_authority_digest=None,
                reason_codes=("missing_verified_evidence",),
            )
            return self._terminal(
                chain=chain,
                outcome="lineage_rejected",
                report=report,
                lineage=lineage,
                artifacts=artifacts,
            )
        lineage = derive_new_lineage(
            repository_id=self.source.repository_id,
            initial_workflow_spec_authority=self.authority.workflow_spec_authority,
        )
        request = GenerationRequestV1(
            schema_version="generation-request-v1",
            workflow_spec_authority=self.authority.workflow_spec_authority,
            repository_url=self.source.repository_url,
            repository_id=self.source.repository_id,
            exact_commit_sha=self.source.pinned_commit_sha,
            license_spdx=self.source.license_spdx,
            lineage_id=lineage.lineage_id,
            stable_slug=lineage.stable_slug,
            qualification_report_digest=qualification_report_digest(report),
            qualification_report_schema_version=QUALIFICATION_REPORT_SCHEMA_VERSION,
            qualification_policy_version=QUALIFICATION_POLICY_VERSION,
            qualification_threshold_version=QUALIFICATION_THRESHOLD_VERSION,
            qualification_score=report.total_score,
            qualification_passed=True,
            generation_policy_version=GENERATOR_POLICY_VERSION,
        )
        generator = self.dependencies.generator_factory()
        generation, generator_attempt = self._retry_generate(generator, request)
        generator_outcomes = {
            "refused": "generator_refusal",
            "incomplete": "generator_incomplete",
            "schema_invalid": "generator_schema_failure",
        }
        if generation.status != "parsed":
            evidence = generator_outcome_evidence(
                candidate_execution_authority=self.authority,
                outcome=generation.status,
                actual_generator_model_id=generation.model,
                request_id=generation.request_id,
                usage=generation.usage,
                latency_ms=generation.latency_ms,
                generated_artifact_identity=None,
            )
            chain = _append_success(
                chain,
                stage=PhaseThreeStageV1.GENERATOR,
                attempt_no=generator_attempt,
                outcome_code=generation.status,
                payload=evidence,
            )
            self.state.persist_candidate_chain(chain, status="running")
            return self._terminal(
                chain=chain,
                outcome=generator_outcomes[generation.status],
                report=report,
                lineage=lineage,
                generator_evidence=evidence,
                artifacts=artifacts,
            )
        if (
            generation.draft is None
            or generation.model is None
            or generation.request_id is None
            or generation.usage is None
        ):
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
        generation_authority = GenerationAuthorityProjectionV1(
            schema_version="generation-authority-v1",
            phase2_run_id=self.source.descriptor.phase2_run_id,
            phase2_terminal_summary_digest=self.source.descriptor.extractor_output_hash,
            phase2_verified_chain_anchor=self.source.descriptor.verified_chain_anchor,
            workflow_spec_authority=self.authority.workflow_spec_authority,
            selected_workflow_fingerprint=self.authority.selected_workflow_fingerprint,
            repository_url=self.source.repository_url,
            repository_id=self.source.repository_id,
            exact_commit_sha=self.source.pinned_commit_sha,
            license_spdx=self.source.license_spdx,
            lineage_id=lineage.lineage_id,
            stable_slug=lineage.stable_slug,
            qualification_report_digest=qualification_report_digest(report),
            qualification_report_schema_version=QUALIFICATION_REPORT_SCHEMA_VERSION,
            qualification_policy_version=QUALIFICATION_POLICY_VERSION,
            qualification_threshold_version=QUALIFICATION_THRESHOLD_VERSION,
            configured_generator_model_id=self.authority.configured_generator_model_id,
            actual_generator_model_id=generation.model,
            generator_prompt_version=self.authority.generator_prompt_version,
            generator_output_schema_version=self.authority.generator_output_schema_version,
            generator_policy_version=self.authority.generator_policy_version,
            renderer_version=RENDERER_VERSION,
            artifact_schema_version=GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION,
            provenance_schema_version=PROVENANCE_SCHEMA_VERSION,
            generator_producer_version=self.authority.phase3_producer_version,
            phase3_profile_version=self.authority.phase3_profile_version,
            retry_policy_version=self.authority.retry_policy_version,
        )
        package = render_skill_package(
            draft=generation.draft,
            authority=generation_authority,
            request_id=generation.request_id,
            usage=generation.usage,
            latency_ms=generation.latency_ms,
        )
        evidence = generator_outcome_evidence(
            candidate_execution_authority=self.authority,
            outcome="parsed",
            actual_generator_model_id=generation.model,
            request_id=generation.request_id,
            usage=generation.usage,
            latency_ms=generation.latency_ms,
            generated_artifact_identity=package.generated_artifact_identity,
        )
        chain = _append_success(
            chain,
            stage=PhaseThreeStageV1.GENERATOR,
            attempt_no=generator_attempt,
            outcome_code="parsed",
            payload=evidence,
        )
        self.state.persist_candidate_chain(chain, status="running")
        artifacts.update(
            {
                "generated_artifact_identity": canonical_json_bytes(
                    package.generated_artifact_identity
                ),
                "package_identity": canonical_json_bytes(package.package_identity),
                "rendered_package": canonical_json_bytes(package),
                "package_manifest": canonical_json_bytes(package.rendered_manifest),
            }
        )

        validator = self.dependencies.validator_factory()
        validation = validator.validate(package=package, authority=self.authority)
        if (
            validation.renderer_version != RENDERER_VERSION
            or validation.renderer_version != self.authority.renderer_version
        ):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        chain = _append_success(
            chain,
            stage=PhaseThreeStageV1.VALIDATOR,
            attempt_no=1,
            outcome_code="accepted" if validation.error_count == 0 else "rejected",
            payload=validation,
        )
        self.state.persist_candidate_chain(chain, status="running")
        artifacts["validation_report"] = canonical_json_bytes(validation)
        if validation.error_count:
            return self._terminal(
                chain=chain,
                outcome="validation_rejected",
                report=report,
                lineage=lineage,
                generator_evidence=evidence,
                package=package,
                validation=validation,
                artifacts=artifacts,
            )

        reviewer = self.dependencies.reviewer_factory()
        review_result, reviewer_attempt = self._retry_review(
            reviewer, package, validation
        )
        disposition = review_disposition(
            generation_succeeded=True,
            validation_report=validation,
            review_result=review_result,
        )
        outcome = {
            "reviewer_refusal": "reviewer_refusal",
            "reviewer_incomplete": "reviewer_incomplete",
            "reviewer_schema_failure": "reviewer_schema_failure",
            "review_completed_no": "review_rejected",
            "review_completed_low_confidence": "review_low_confidence",
            "review_completed_eligible": "eligible_local_candidate",
        }[disposition.status]
        attestation = review_attestation(
            candidate_execution_authority=self.authority,
            generated_artifact_identity=package.generated_artifact_identity,
            package_identity=package.package_identity,
            validation_report=validation,
            review_result=review_result,
        )
        chain = _append_success(
            chain,
            stage=PhaseThreeStageV1.REVIEWER,
            attempt_no=reviewer_attempt,
            outcome_code=disposition.status,
            payload=attestation,
        )
        self.state.persist_candidate_chain(chain, status="running")
        artifacts["review_attestation"] = review_attestation_bytes(attestation)
        return self._terminal(
            chain=chain,
            outcome=outcome,
            report=report,
            lineage=lineage,
            generator_evidence=evidence,
            package=package,
            validation=validation,
            review_result=review_result,
            attestation=attestation,
            artifacts=artifacts,
        )

    def _retry_generate(
        self, generator: object, request: GenerationRequestV1
    ) -> tuple[GenerationResult, int]:
        for attempt in range(1, self.profile.max_generator_attempts + 1):
            try:
                result = generator.generate(request=request)
                if type(result) is not GenerationResult:
                    raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
                return result, attempt
            except SafeFailure as failure:
                if (
                    failure.code is not ErrorCode.STAGE_TRANSIENT_FAILURE
                    or attempt == self.profile.max_generator_attempts
                ):
                    raise
        raise SafeFailure(ErrorCode.RETRY_EXHAUSTED)

    def _retry_review(
        self, reviewer: object, package: object, validation: object
    ) -> tuple[object, int]:
        from skillscout.domain.review import ReviewResult

        for attempt in range(1, self.profile.max_reviewer_attempts + 1):
            try:
                result = reviewer.review(
                    workflow_spec=self.authority.workflow_spec_authority.workflow_spec,
                    package=package,
                    validation_report=validation,
                )
                if type(result) is not ReviewResult:
                    raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
                return result, attempt
            except SafeFailure as failure:
                if (
                    failure.code is not ErrorCode.STAGE_TRANSIENT_FAILURE
                    or attempt == self.profile.max_reviewer_attempts
                ):
                    raise
        raise SafeFailure(ErrorCode.RETRY_EXHAUSTED)

    def _terminal(
        self,
        *,
        chain: VerifiedCandidateRunChain,
        outcome: str,
        report: object,
        lineage: LineageResolutionV1,
        artifacts: dict[str, bytes],
        generator_evidence: object | None = None,
        package: object | None = None,
        validation: object | None = None,
        review_result: object | None = None,
        attestation: object | None = None,
    ) -> tuple[object, dict[str, bytes]]:
        disposition = review_disposition(
            generation_succeeded=package is not None,
            validation_report=validation,
            review_result=review_result,
        )
        terminal = candidate_terminal_summary(
            outcome=outcome,
            candidate_execution_authority=self.authority,
            qualification_passed=report.passed,
            qualification_report_digest=qualification_report_digest(report),
            lineage_resolution=lineage,
            generator_outcome_evidence=generator_evidence,
            generated_artifact_identity=(
                package.generated_artifact_identity if package is not None else None
            ),
            package_identity=(
                package.package_identity if package is not None else None
            ),
            validation_report=validation,
            review_disposition=disposition,
            review_attestation=attestation,
        )
        if (
            terminal.eligibility_policy_version != ELIGIBILITY_POLICY_VERSION
            or terminal.eligibility_policy_version
            != self.authority.eligibility_policy_version
        ):
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        self.state.persist_candidate_terminal(
            chain.identity.run_id,
            terminal_summary=terminal,
            artifacts=artifacts,
        )
        return terminal, artifacts


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
            terminal, artifacts = PhaseThreeRunner(
                state=mutable,
                source=resolved,
                authority=authority,
                profile=self._profile,
                dependencies=self._dependencies,
            ).run()
            if output_directory is not None:
                output = self._dependencies.artifact_projector_factory()
                project = getattr(output, "project")
                project(
                    output_directory=output_directory,
                    terminal_summary=terminal,
                    artifacts=artifacts,
                )
            return PhaseThreeApplicationResult(
                outcome=terminal.outcome,
                authority=authority,
                terminal_summary=terminal,
                artifacts=artifacts,
            )
        finally:
            close = getattr(mutable, "close", None)
            if callable(close):
                close()
