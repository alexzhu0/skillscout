"""Ordered, resumable local-only pipeline over strict schema-v3 contracts."""

from __future__ import annotations

import fcntl
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Final, Iterable, Literal, Mapping, Protocol

from skillscout.adapters.fixtures import FixtureProcessor, FixtureSubject
from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.adapters.semantic_provider import (
    SemanticProviderFailure,
    SemanticTransportDisposition,
)
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.ports import (
    AdapterRegistration,
    Clock,
    DurabilityReceipt,
    ErrorCode,
    IdProvider,
    SafeFailure,
    SemanticDurabilityTransition,
    StageContext,
    StageOutcome,
    StageProcessor,
    StageTelemetry,
    StateStore,
    ThreeStoreDurabilityBarrier,
    require_durability_receipt,
)
from skillscout.application.processors import PhaseTwoProcessor
from skillscout.domain.canonical import (
    canonical_json_bytes,
    make_result_id,
    make_result_row_id,
    reusable_key_digest,
    sha256_digest,
    stage_input_hash,
    stage_manifest_hash,
    stage_output_hash,
)
from skillscout.domain.enums import (
    AttemptStatus,
    EffectScope,
    ExecutionMode,
    PipelineStage,
    RunStatus,
)
from skillscout.domain.models import (
    ExtractionSummary,
    PublicationPlan,
    RunIdentity,
    RunSummary,
    SUPPORTED_PRODUCER_SCHEMAS,
    StageAttempt,
    StageEnvelope,
    StageInput,
    StageOutcomeEntry,
    StagePayload,
    VerifiedRunChain,
)
from skillscout.domain.subjects import RepositorySubject

_DIGEST_PATTERN: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_STATE_SHA_PATTERN: Final = re.compile(r"^[0-9a-f]{40}$")

STAGE_SEQUENCE = tuple(stage.value for stage in PipelineStage)
RETRY_POLICY_VERSION = "retry-v1"
PHASE_ONE_MAX_SCOPES: Final[frozenset[EffectScope]] = frozenset(
    {EffectScope.NONE, EffectScope.LOCAL_STATE}
)
PHASE_TWO_MAX_SCOPES: Final[frozenset[EffectScope]] = frozenset(
    {EffectScope.NONE, EffectScope.LOCAL_STATE, EffectScope.REMOTE_READ}
)
PHASE_TWO_STAGE_SEQUENCE: Final[tuple[str, ...]] = tuple(
    stage.value
    for stage in (
        PipelineStage.SCOUT,
        PipelineStage.FILTER,
        PipelineStage.READER,
        PipelineStage.EXTRACTOR,
    )
)
MAX_PUBLICATION_PLAN_BYTES: Final[int] = 65_536
MAX_EXTRACTION_SUMMARY_BYTES: Final[int] = 65_536


@dataclass(frozen=True)
class RetryPolicy:
    """Finite retry authority scoped only to a canonical reusable digest."""

    version: str = RETRY_POLICY_VERSION
    max_attempts: int = 3
    transient_error_codes: frozenset[ErrorCode] = frozenset(
        {ErrorCode.PIPELINE_INTERRUPTED, ErrorCode.STAGE_TRANSIENT_FAILURE}
    )

    def __post_init__(self) -> None:
        if not self.version or self.max_attempts < 1:
            raise ValueError("invalid retry policy")


def canonical_v1_digest(
    *,
    subject_id: str,
    stage: str,
    input_hash: str,
    producer_version: str,
    retry_policy_version: str,
) -> str:
    """Compatibility seam for frozen schema-v1 provenance tests."""

    return reusable_key_digest(
        subject_id=subject_id,
        stage=PipelineStage(stage),
        input_hash=input_hash,
        producer_version=producer_version,
        retry_policy_version=retry_policy_version,
    )


class SystemClock:
    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.NONE

    def now(self) -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class UUIDIdProvider:
    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.NONE

    def new_run_id(self) -> str:
        return uuid.uuid4().hex


@dataclass(frozen=True)
class SideEffectPolicy:
    """Fail-closed authority policy applied before runtime construction."""

    allowed_scopes: frozenset[EffectScope]

    @classmethod
    def phase_one(cls) -> SideEffectPolicy:
        return cls(PHASE_ONE_MAX_SCOPES)

    @classmethod
    def phase_two(cls) -> SideEffectPolicy:
        return cls(PHASE_TWO_MAX_SCOPES)

    def validate(
        self, registrations: Iterable[AdapterRegistration]
    ) -> tuple[AdapterRegistration, ...]:
        registry = tuple(registrations)
        if any(registration.scope not in self.allowed_scopes for registration in registry):
            raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE)
        return registry


@dataclass(frozen=True)
class PipelineProfile:
    """Closed producer-resolved stage slice and terminal behavior."""

    stages: tuple[PipelineStage, ...]
    uses_context: bool
    terminal_status: RunStatus


PIPELINE_PROFILES: Final[dict[str, PipelineProfile]] = {
    "fixture-v1": PipelineProfile(tuple(PipelineStage), False, RunStatus.PLANNED_NOT_PUBLISHED),
    "phase2-v1": PipelineProfile(
        (
            PipelineStage.SCOUT,
            PipelineStage.FILTER,
            PipelineStage.READER,
            PipelineStage.EXTRACTOR,
        ),
        True,
        RunStatus.COMPLETED,
    ),
}

if any(
    profile.stages != tuple(PipelineStage)[: len(profile.stages)]
    for profile in PIPELINE_PROFILES.values()
):
    raise RuntimeError("pipeline profile stages must be a spine prefix")


@dataclass(frozen=True)
class DryRunRuntime:
    """Validated local-only runtime returned by the sole composition root."""

    runner: PipelineRunner
    registrations: tuple[AdapterRegistration, ...]
    policy: SideEffectPolicy


@dataclass(frozen=True)
class PhaseTwoRuntime:
    """Validated remote-read runtime returned by the phase-two composition root."""

    runner: PipelineRunner
    registrations: tuple[AdapterRegistration, ...]
    policy: SideEffectPolicy


class _PublicationWriter(Protocol):
    def write(self, output_directory: Path, plan: PublicationPlan) -> Path: ...


class _LocalPublicationPlanner:
    """The only publication capability present in the Phase 1 runtime."""

    def __init__(
        self,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> None:
        self._filesystem_seam = filesystem_seam

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.LOCAL_STATE

    def write(self, output_directory: Path, plan: PublicationPlan) -> Path:
        return PipelineRunner._write_publication_plan(
            output_directory,
            plan,
            filesystem_seam=self._filesystem_seam,
        )


class _ExtractionSummaryWriter:
    """The only extraction-summary capability present in the phase-two runtime."""

    def __init__(
        self,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> None:
        self._filesystem_seam = filesystem_seam

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.LOCAL_STATE

    def write(self, output_directory: Path, summary: ExtractionSummary) -> Path:
        return PipelineRunner._write_extraction_summary(
            output_directory,
            summary,
            filesystem_seam=self._filesystem_seam,
        )


@dataclass(frozen=True)
class SemanticReservationReceipt:
    """Closed proof that semantic budget is remotely durable before a request."""

    reservation_digest: str
    verified_state_head: str
    state_root_digest: str

    def __post_init__(self) -> None:
        if (
            _DIGEST_PATTERN.fullmatch(self.reservation_digest) is None
            or _STATE_SHA_PATTERN.fullmatch(self.verified_state_head) is None
            or _DIGEST_PATTERN.fullmatch(self.state_root_digest) is None
        ):
            raise ValueError("invalid semantic reservation receipt")


class SemanticDurabilityGuard:
    """Bind semantic attempt authority to an exact remotely confirmed state."""

    def __init__(
        self,
        *,
        barrier: ThreeStoreDurabilityBarrier,
        operations_store: object,
        publication_store: object,
        repository_id: int,
        workflow_authority_digest: str,
        provider: Literal["openai", "deepseek"],
        expected_prior_state_head: str,
        expected_prior_root_digest: str,
        reservation_hook: Callable[..., SemanticReservationReceipt] | None = None,
        request_reservation_hook: (Callable[..., SemanticReservationReceipt] | None) = None,
        operations_run_id: str | None = None,
    ) -> None:
        if (
            not callable(getattr(barrier, "confirm", None))
            or not hasattr(operations_store, "record_semantic_attempt")
            or not hasattr(operations_store, "export_owned_state")
            or not hasattr(publication_store, "export_owned_state")
            or type(repository_id) is not int
            or repository_id <= 0
            or provider not in {"openai", "deepseek"}
        ):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        self._barrier = barrier
        self._operations_store = operations_store
        self._publication_store = publication_store
        self._repository_id = repository_id
        self._workflow_authority_digest = workflow_authority_digest
        self._provider = provider
        self._expected_prior_state_head = expected_prior_state_head
        self._expected_prior_root_digest = expected_prior_root_digest
        self._reservation_hook = reservation_hook
        self._request_reservation_hook = request_reservation_hook
        self._operations_run_id = operations_run_id

    def reserve_before_extractor(
        self,
        *,
        pipeline_store: object,
        run_id: str,
    ) -> SemanticReservationReceipt | None:
        """Confirm a non-refundable reservation before the first provider call."""

        if self._reservation_hook is None:
            return None
        try:
            receipt = self._reservation_hook(
                pipeline_store=pipeline_store,
                run_id=run_id,
            )
            if type(receipt) is not SemanticReservationReceipt:
                raise TypeError("invalid semantic reservation receipt")
        except SafeFailure:
            raise
        except Exception:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        self._expected_prior_state_head = receipt.verified_state_head
        self._expected_prior_root_digest = receipt.state_root_digest
        return receipt

    @property
    def verified_state_head(self) -> str:
        return self._expected_prior_state_head

    @property
    def state_root_digest(self) -> str:
        return self._expected_prior_root_digest

    @property
    def operations_run_id(self) -> str | None:
        return self._operations_run_id

    def already_durable(
        self,
        *,
        run_id: str,
        stage: Literal["extractor", "generator", "reviewer"],
        attempt_no: int,
        status: Literal[
            "started",
            "decided",
            "confirmed_retryable",
            "semantic_outcome_unknown",
        ],
        provider_disposition: Literal["permanent_rejection"] | None = None,
    ) -> bool:
        """Report an exact durable attempt without creating another transition."""

        snapshot = getattr(self._operations_store, "snapshot_run", None)
        if not callable(snapshot):
            return False
        operations_run_id = self._operations_run_id or run_id
        try:
            matches = tuple(
                item
                for item in snapshot(operations_run_id).semantic_attempts
                if item.repository_id == self._repository_id
                and item.workflow_authority_digest == self._workflow_authority_digest
                and item.stage == stage
                and item.attempt_no == attempt_no
            )
        except Exception:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        if len(matches) > 1:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        return (
            len(matches) == 1
            and matches[0].status == status
            and getattr(matches[0], "provider_disposition", None) == provider_disposition
        )

    def confirm(
        self,
        *,
        pipeline_store: object,
        run_id: str,
        stage: Literal["extractor", "generator", "reviewer"],
        attempt_no: int,
        status: Literal[
            "started",
            "decided",
            "confirmed_retryable",
            "semantic_outcome_unknown",
        ],
        recorded_at: str,
        provider_disposition: Literal["permanent_rejection"] | None = None,
    ) -> DurabilityReceipt:
        """Persist one owner fact and return only an exact barrier receipt."""

        try:
            operations_run_id = self._operations_run_id or run_id
            if status == "started" and self._request_reservation_hook is not None:
                request_receipt = self._request_reservation_hook(
                    pipeline_store=pipeline_store,
                    run_id=operations_run_id,
                    repository_id=self._repository_id,
                    workflow_authority_digest=self._workflow_authority_digest,
                    stage=stage,
                    attempt_no=attempt_no,
                    observed_head=self._expected_prior_state_head,
                    prior_root_digest=self._expected_prior_root_digest,
                )
                if type(request_receipt) is not SemanticReservationReceipt:
                    raise TypeError("invalid semantic request reservation receipt")
                self._expected_prior_state_head = request_receipt.verified_state_head
                self._expected_prior_root_digest = request_receipt.state_root_digest
            record_arguments: dict[str, object] = {
                "run_id": operations_run_id,
                "repository_id": self._repository_id,
                "workflow_authority_digest": self._workflow_authority_digest,
                "stage": stage,
                "attempt_no": attempt_no,
                "status": status,
                "recorded_at": recorded_at,
            }
            if provider_disposition is not None:
                record_arguments["provider_disposition"] = provider_disposition
            record = self._operations_store.record_semantic_attempt(**record_arguments)
            prepare_transition = getattr(
                self._barrier,
                "prepare_acceptance_transition",
                None,
            )
            if callable(prepare_transition):
                prepare_transition(
                    operations_store=self._operations_store,
                    observed_head=self._expected_prior_state_head,
                    prior_root_digest=self._expected_prior_root_digest,
                    stage=stage,
                    attempt_no=attempt_no,
                    status=status,
                    recorded_at=record.recorded_at,
                    workflow_authority_digest=self._workflow_authority_digest,
                )
            pipeline = pipeline_store.export_owned_state()
            operations = self._operations_store.export_owned_state()
            publication = self._publication_store.export_owned_state()
            transition = SemanticDurabilityTransition.create(
                run_id=run_id,
                operations_run_id=operations_run_id,
                repository_id=self._repository_id,
                workflow_authority_digest=self._workflow_authority_digest,
                provider=self._provider,
                stage=stage,
                attempt_no=attempt_no,
                recorded_at=record.recorded_at,
                transition={
                    "started": "attempt_started",
                    "decided": "result_decided",
                    "confirmed_retryable": "result_confirmed_retryable",
                    "semantic_outcome_unknown": "result_outcome_unknown",
                }[status],
                expected_prior_state_head=self._expected_prior_state_head,
                expected_prior_root_digest=self._expected_prior_root_digest,
                pipeline_export_digest=pipeline.export_digest,
                operations_export_digest=operations.export_digest,
                publication_export_digest=publication.export_digest,
            )
            receipt = require_durability_receipt(
                transition,
                self._barrier.confirm(
                    transition=transition,
                    pipeline_store=pipeline_store,
                    operations_store=self._operations_store,
                    publication_store=self._publication_store,
                ),
            )
        except SafeFailure:
            raise
        except Exception:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        self._expected_prior_state_head = receipt.verified_state_head
        self._expected_prior_root_digest = receipt.state_root_digest
        return receipt


class PipelineRunner:
    """Persist running identity before work and atomic evidence after work."""

    def __init__(
        self,
        state: StateStore,
        processor: StageProcessor,
        *,
        clock: Clock | None = None,
        ids: IdProvider | None = None,
        retry_policy: RetryPolicy | None = None,
        publication_writer: _PublicationWriter | None = None,
        extraction_writer: _ExtractionSummaryWriter | None = None,
        semantic_durability: SemanticDurabilityGuard | None = None,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> None:
        self.state = state
        self.processor = processor
        self.clock = clock or SystemClock()
        self.ids = ids or UUIDIdProvider()
        self.retry_policy = retry_policy or RetryPolicy()
        self.publication_writer = publication_writer or _LocalPublicationPlanner(filesystem_seam)
        self.extraction_writer = extraction_writer or _ExtractionSummaryWriter(filesystem_seam)
        self.semantic_durability = semantic_durability

    def run(
        self,
        subject: FixtureSubject | RepositorySubject,
        output_directory: Path,
        fail_after: str | None = None,
    ) -> RunSummary:
        if fail_after is not None and fail_after not in STAGE_SEQUENCE:
            raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)

        try:
            producer_version = self.processor.producer_version
            producer_supported = (
                type(producer_version) is str
                and ("2", producer_version) in SUPPORTED_PRODUCER_SCHEMAS
            )
        except Exception:
            producer_supported = False
        if not producer_supported:
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
        profile = PIPELINE_PROFILES.get(producer_version)
        if profile is None:
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)

        fixture_hash = sha256_digest(subject.model_dump(mode="json", exclude_none=False))
        current_identity = RunIdentity(
            schema_version="2",
            subject_id=subject.subject_id,
            fixture_hash=fixture_hash,
            producer_version=producer_version,
            retry_policy_version=self.retry_policy.version,
        )
        resumable = self.state.find_resumable_run(current_identity)
        if resumable is None and ("1", producer_version) in SUPPORTED_PRODUCER_SCHEMAS:
            legacy_identity = current_identity.model_copy(update={"schema_version": "1"})
            resumable = self.state.find_resumable_run(legacy_identity)
            if resumable is None:
                resumable = self.state.bind_legacy_run(legacy_identity)
        if resumable is None and profile.terminal_status is RunStatus.COMPLETED:
            completed = self.state.find_completed_run(current_identity)
            if completed is not None:
                chain = self.state.verify_run_chain(completed.run_id, current_identity)
                self.extraction_writer.write(
                    output_directory, _build_extraction_summary(chain, subject)
                )
                completed_checkpoint = self.state.latest_checkpoint(completed.run_id)
                if completed_checkpoint is None:
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                return RunSummary(
                    run_id=completed.run_id,
                    status=RunStatus.COMPLETED,
                    last_stage=completed_checkpoint.stage,
                    reused_stage_count=len(profile.stages),
                    publication_plan_path="extraction-summary.json",
                    remote_writes_attempted=0,
                )
        if resumable is None:
            run_id = self.ids.new_run_id()
            schema_version = current_identity.schema_version
            invocation_event = self.state.create_run(run_id, current_identity, self.clock.now())
            start_index = invocation_event.reused_stage_count
            previous_output_hash: str | None = None
        else:
            run_id = resumable.run_id
            schema_version = resumable.schema_version
            checkpoint = self.state.latest_checkpoint(run_id)
            invocation_event = self.state.record_resume_decision(
                run_id,
                checkpoint,
                self.clock.now(),
            )
            start_index = invocation_event.reused_stage_count
            previous_output_hash = checkpoint.output_hash if checkpoint else None

        prior_payloads: dict[str, Mapping[str, object]] = {}
        if profile.uses_context and resumable is not None and start_index > 0:
            for envelope in self.state.verify_run_chain(run_id).results:
                prior_payloads[envelope.stage.value] = envelope.payload

        for stage_index, stage in enumerate(profile.stages):
            if stage_index < start_index:
                continue
            stage_input = StageInput(
                schema_version=schema_version,
                execution_mode=ExecutionMode.DRY_RUN,
                subject_id=subject.subject_id,
                stage=stage,
                previous_output_hash=previous_output_hash,
                fixture_hash=fixture_hash if stage_index == 0 else None,
            )
            input_hash = stage_input_hash(stage_input)
            reusable_digest = reusable_key_digest(
                subject_id=subject.subject_id,
                stage=stage,
                input_hash=input_hash,
                producer_version=producer_version,
                retry_policy_version=self.retry_policy.version,
            )
            semantic_stage = (
                self.semantic_durability is not None
                and profile.uses_context
                and stage is PipelineStage.EXTRACTOR
            )
            if semantic_stage:
                requires_request = getattr(self.processor, "semantic_request_required", None)
                if callable(requires_request):
                    semantic_stage = bool(
                        requires_request(
                            StageContext(
                                subject=subject,
                                prior_payloads=dict(prior_payloads),
                                scratch={},
                            )
                        )
                    )
            if semantic_stage:
                prior_attempt = self._latest_attempt(run_id, stage)
                if prior_attempt is not None:
                    prior_status = str(prior_attempt["status"])
                    prior_error = prior_attempt["error_code"]
                    prior_attempt_no = int(prior_attempt["attempt_no"])
                    if prior_status in {"running", "abandoned"}:
                        unknown = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                        self.state.fail_attempt(
                            str(prior_attempt["attempt_id"]),
                            run_id,
                            unknown,
                            self.clock.now(),
                            retryable=False,
                        )
                        self._confirm_semantic(
                            run_id=run_id,
                            attempt_no=prior_attempt_no,
                            status="semantic_outcome_unknown",
                        )
                        raise SemanticProviderFailure(
                            disposition=(SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN),
                            code="semantic_provider_outcome_unknown",
                        )
                    if prior_status == "failed":
                        if prior_error == ErrorCode.STAGE_TRANSIENT_FAILURE.value:
                            if not self.semantic_durability.already_durable(
                                run_id=run_id,
                                stage="extractor",
                                attempt_no=prior_attempt_no,
                                status="confirmed_retryable",
                            ):
                                self._confirm_semantic(
                                    run_id=run_id,
                                    attempt_no=prior_attempt_no,
                                    status="confirmed_retryable",
                                )
                        elif prior_error == ErrorCode.PIPELINE_INTERRUPTED.value:
                            if not self.semantic_durability.already_durable(
                                run_id=run_id,
                                stage="extractor",
                                attempt_no=prior_attempt_no,
                                status="semantic_outcome_unknown",
                            ):
                                self._confirm_semantic(
                                    run_id=run_id,
                                    attempt_no=prior_attempt_no,
                                    status="semantic_outcome_unknown",
                                )
                            raise SemanticProviderFailure(
                                disposition=(SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN),
                                code="semantic_provider_outcome_unknown",
                            )
            self.state.abandon_stale_running(run_id, stage, self.clock.now())
            if self.state.has_permanent_failure(reusable_digest):
                failure = SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
                self.state.set_run_status(
                    run_id, RunStatus.INTERRUPTED.value, self.clock.now(), failure
                )
                raise failure
            if self.state.retry_attempt_count(reusable_digest) >= self.retry_policy.max_attempts:
                failure = SafeFailure(ErrorCode.RETRY_EXHAUSTED)
                self.state.set_run_status(
                    run_id, RunStatus.INTERRUPTED.value, self.clock.now(), failure
                )
                raise failure
            attempt_no = self.state.next_attempt_no(run_id, stage, reusable_digest)
            attempt_id = f"{run_id}:{stage.value}:{attempt_no}"
            attempt = StageAttempt(
                attempt_id=attempt_id,
                run_id=run_id,
                subject_id=subject.subject_id,
                stage=stage,
                stage_index=stage_index,
                attempt_no=attempt_no,
                status=AttemptStatus.RUNNING,
                input_hash=input_hash,
                producer_version=producer_version,
                retry_policy_version=self.retry_policy.version,
                reusable_key_digest=reusable_digest,
                started_at=self.clock.now(),
                finished_at=None,
                prompt_version=None,
                policy_version=None,
                model_id=None,
                request_id=None,
                latency_ms=None,
                token_usage=None,
                error_code=None,
                error_summary=None,
                retryable=False,
            )
            if semantic_stage:
                if attempt_no == 1:
                    self.semantic_durability.reserve_before_extractor(
                        pipeline_store=self.state,
                        run_id=run_id,
                    )
            self.state.start_attempt(attempt)
            if semantic_stage:
                self._confirm_semantic(
                    run_id=run_id,
                    attempt_no=attempt_no,
                    status="started",
                )

            try:
                if profile.uses_context:
                    context = StageContext(
                        subject=subject,
                        prior_payloads=dict(prior_payloads),
                        scratch={},
                    )
                    outcome: StageOutcome | Mapping[str, object] = self.processor.process(  # type: ignore[call-arg]
                        stage_input,
                        context,
                    )
                else:
                    outcome = StageOutcome(
                        payload=self.processor.process(stage_input),
                        telemetry=None,
                    )
            except SemanticProviderFailure as failure:
                if failure.disposition is SemanticTransportDisposition.CONFIRMED_RETRYABLE:
                    closed = SafeFailure(ErrorCode.STAGE_TRANSIENT_FAILURE)
                    status = "confirmed_retryable"
                elif failure.disposition is SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN:
                    closed = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                    status = "semantic_outcome_unknown"
                else:
                    closed = SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
                    status = "decided"
                    provider_disposition = "permanent_rejection"
                if failure.disposition is not SemanticTransportDisposition.PERMANENT:
                    provider_disposition = None
                self.state.fail_attempt(
                    attempt_id,
                    run_id,
                    closed,
                    self.clock.now(),
                    retryable=(
                        failure.disposition is SemanticTransportDisposition.CONFIRMED_RETRYABLE
                    ),
                )
                if semantic_stage:
                    self._confirm_semantic(
                        run_id=run_id,
                        attempt_no=attempt_no,
                        status=status,
                        provider_disposition=provider_disposition,
                    )
                if failure.disposition is SemanticTransportDisposition.CONFIRMED_RETRYABLE:
                    raise closed from None
                if failure.disposition is SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN:
                    raise
                raise closed from None
            except SafeFailure as failure:
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise
            except Exception:
                failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise failure from None

            if (
                not isinstance(outcome, StageOutcome)
                or not isinstance(outcome.payload, Mapping)
                or (
                    outcome.telemetry is not None
                    and not isinstance(outcome.telemetry, StageTelemetry)
                )
            ):
                failure = SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise failure

            telemetry = outcome.telemetry
            try:
                payload = StagePayload.model_validate(outcome.payload).root
                output_hash = stage_output_hash(
                    schema_version=schema_version,
                    subject_id=subject.subject_id,
                    stage=stage,
                    producer_version=producer_version,
                    prompt_version=telemetry.prompt_version if telemetry else None,
                    policy_version=telemetry.policy_version if telemetry else None,
                    model_id=telemetry.model_id if telemetry else None,
                    payload=payload,
                )
                result_id = make_result_id(
                    subject_id=subject.subject_id,
                    stage=stage,
                    input_hash=input_hash,
                    producer_version=producer_version,
                    output_hash=output_hash,
                    retry_policy_version=(
                        None if schema_version == "1" else self.retry_policy.version
                    ),
                )
                provisional = StageEnvelope(
                    schema_version=schema_version,
                    result_row_id=make_result_row_id(run_id=run_id, stage=stage),
                    result_id=result_id,
                    run_id=run_id,
                    attempt_id=attempt_id,
                    attempt_no=attempt_no,
                    subject_id=subject.subject_id,
                    stage=stage,
                    stage_index=stage_index,
                    input_hash=input_hash,
                    output_hash=output_hash,
                    producer_version=producer_version,
                    retry_policy_version=self.retry_policy.version,
                    prompt_version=telemetry.prompt_version if telemetry else None,
                    policy_version=telemetry.policy_version if telemetry else None,
                    model_id=telemetry.model_id if telemetry else None,
                    request_id=telemetry.request_id if telemetry else None,
                    created_at=self.clock.now(),
                    payload=payload,
                    manifest_hash=None,
                )
                envelope = provisional.model_copy(
                    update={"manifest_hash": stage_manifest_hash(provisional)}
                )
            except Exception:
                failure = SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise failure from None

            try:
                if telemetry is not None:
                    self.state.record_attempt_telemetry(attempt_id, telemetry)
                self.state.complete_stage(envelope)
                if semantic_stage:
                    self._confirm_semantic(
                        run_id=run_id,
                        attempt_no=attempt_no,
                        status="decided",
                    )
            except SafeFailure as failure:
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise
            except Exception:
                failure = SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
                self._close_started_attempt(
                    attempt_id=attempt_id,
                    run_id=run_id,
                    failure=failure,
                )
                raise failure from None
            previous_output_hash = output_hash
            if profile.uses_context:
                prior_payloads[stage.value] = payload

            if fail_after == stage.value:
                failure = SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                self.state.set_run_status(
                    run_id, RunStatus.INTERRUPTED.value, self.clock.now(), failure
                )
                raise failure

        if profile.terminal_status is RunStatus.COMPLETED:
            chain = self.state.verify_run_chain(run_id)
            extraction = _build_extraction_summary(chain, subject)
            self.extraction_writer.write(output_directory, extraction)
            self.state.set_run_status(run_id, RunStatus.COMPLETED.value, self.clock.now())
            artifact_name = "extraction-summary.json"
        else:
            self.publication_writer.write(output_directory, PublicationPlan(run_id=run_id))
            self.state.set_run_status(
                run_id, RunStatus.PLANNED_NOT_PUBLISHED.value, self.clock.now()
            )
            artifact_name = "publication-plan.json"
        persisted = self.state.read_run(run_id)
        checkpoint = self.state.latest_checkpoint(run_id)
        if checkpoint is None:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        return RunSummary(
            run_id=persisted.run_id,
            status=persisted.status,
            last_stage=checkpoint.stage,
            reused_stage_count=invocation_event.reused_stage_count,
            publication_plan_path=artifact_name,
            remote_writes_attempted=0,
        )

    def _latest_attempt(
        self,
        run_id: str,
        stage: PipelineStage,
    ) -> Mapping[str, object] | None:
        connection = getattr(self.state, "connection", None)
        if connection is None:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        try:
            row = connection.execute(
                """SELECT attempt_id, attempt_no, status, error_code
                   FROM stage_attempts
                   WHERE run_id = ? AND stage = ?
                   ORDER BY attempt_no DESC LIMIT 1""",
                (run_id, stage.value),
            ).fetchone()
        except Exception:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        return row

    def _confirm_semantic(
        self,
        *,
        run_id: str,
        attempt_no: int,
        status: Literal[
            "started",
            "decided",
            "confirmed_retryable",
            "semantic_outcome_unknown",
        ],
        provider_disposition: Literal["permanent_rejection"] | None = None,
    ) -> DurabilityReceipt:
        guard = self.semantic_durability
        if guard is None:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        return guard.confirm(
            pipeline_store=self.state,
            run_id=run_id,
            stage="extractor",
            attempt_no=attempt_no,
            status=status,
            recorded_at=self.clock.now(),
            provider_disposition=provider_disposition,
        )

    def _close_started_attempt(
        self,
        *,
        attempt_id: str,
        run_id: str,
        failure: SafeFailure,
    ) -> None:
        """Close a known running lifecycle or expose only a closed state failure."""

        try:
            self.state.fail_attempt(
                attempt_id,
                run_id,
                failure,
                self.clock.now(),
                retryable=failure.code in self.retry_policy.transient_error_codes,
            )
        except SafeFailure:
            raise
        except Exception:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    @staticmethod
    def _acquire_publication_lock(anchor: AnchoredDirectory, target_name: str) -> int:
        """Serialize publication writers on a retained kernel-flock inode."""

        lock_name = AnchoredDirectory.validate_child_name(f".{target_name}.lock")
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            descriptor = os.open(lock_name, flags, 0o600, dir_fd=anchor.descriptor)
            anchored = os.stat(
                lock_name,
                dir_fd=anchor.descriptor,
                follow_symlinks=False,
            )
            opened = os.fstat(descriptor)
            AnchoredDirectory._require_private_regular(anchored)
            AnchoredDirectory._require_private_regular(opened)
            if (anchored.st_dev, anchored.st_ino) != (
                opened.st_dev,
                opened.st_ino,
            ):
                raise OSError("invalid lock file")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return descriptor
        except (BlockingIOError, OSError):
            if "descriptor" in locals():
                os.close(descriptor)
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    @staticmethod
    def _write_durable_artifact(
        output_directory: Path,
        target_name: str,
        payload: bytes,
        *,
        max_bytes: int,
        seam_prefix: str,
        durable_marker: str,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> Path:
        anchor: AnchoredDirectory | None = None
        lock_descriptor = -1
        try:
            if len(payload) > max_bytes:
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
            anchor = AnchoredDirectory.open(
                output_directory,
                create=True,
                filesystem_seam=filesystem_seam,
            )
            lock_descriptor = PipelineRunner._acquire_publication_lock(anchor, target_name)
            anchor.recover_stale_temporary(target_name)
            anchor.recover_stale_temporary(f".{target_name}.backup")
            previous = anchor.read_bytes(
                target_name,
                max_bytes=max_bytes,
                missing_ok=True,
            )
            if previous is None:
                anchor.atomic_write(
                    target_name,
                    payload,
                    max_bytes=max_bytes,
                    seam_prefix=seam_prefix,
                )
            else:
                anchor.atomic_write(
                    target_name,
                    payload,
                    max_bytes=max_bytes,
                    restore_bytes=previous,
                    seam_prefix=seam_prefix,
                )
            if filesystem_seam is not None:
                filesystem_seam(durable_marker)
            return output_directory / target_name
        except SafeFailure:
            raise
        except (DurableWriteError, OSError):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        finally:
            if lock_descriptor >= 0:
                try:
                    os.close(lock_descriptor)
                except OSError:
                    pass
            if anchor is not None:
                anchor.close()

    @staticmethod
    def _write_publication_plan(
        output_directory: Path,
        plan: PublicationPlan,
        *,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> Path:
        payload = canonical_json_bytes(plan) + b"\n"
        return PipelineRunner._write_durable_artifact(
            output_directory,
            "publication-plan.json",
            payload,
            max_bytes=MAX_PUBLICATION_PLAN_BYTES,
            seam_prefix="publication_",
            durable_marker="after_publication_durable",
            filesystem_seam=filesystem_seam,
        )

    @staticmethod
    def _write_extraction_summary(
        output_directory: Path,
        summary: ExtractionSummary,
        *,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> Path:
        payload = canonical_json_bytes(summary) + b"\n"
        return PipelineRunner._write_durable_artifact(
            output_directory,
            "extraction-summary.json",
            payload,
            max_bytes=MAX_EXTRACTION_SUMMARY_BYTES,
            seam_prefix="extraction_",
            durable_marker="after_extraction_durable",
            filesystem_seam=filesystem_seam,
        )


def _build_extraction_summary(
    chain: VerifiedRunChain,
    subject: FixtureSubject | RepositorySubject,
) -> ExtractionSummary:
    """Project the verified chain into the bounded phase-two terminal artifact."""

    entries: list[StageOutcomeEntry] = []
    payloads: dict[PipelineStage, Mapping[str, object]] = {}
    for envelope in chain.results:
        outcome = envelope.payload.get("outcome")
        if not isinstance(outcome, str):
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
        entries.append(StageOutcomeEntry(stage=envelope.stage, outcome=outcome))
        payloads[envelope.stage] = envelope.payload
    extractor_payload = payloads.get(PipelineStage.EXTRACTOR)
    if extractor_payload is None:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)

    pinned = payloads.get(PipelineStage.SCOUT, {}).get("pinned_commit_sha")
    if pinned is not None and not isinstance(pinned, str):
        raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)

    workflows = extractor_payload.get("workflows", [])
    if not isinstance(workflows, list):
        raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
    fingerprints: list[str] = []
    for item in workflows:
        fingerprint = item.get("fingerprint") if isinstance(item, dict) else None
        if not isinstance(fingerprint, str):
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
        fingerprints.append(fingerprint)

    return ExtractionSummary(
        run_id=chain.run.run_id,
        subject_id=chain.run.subject_id,
        repository=(
            subject.repository if isinstance(subject, RepositorySubject) else subject.subject_id
        ),
        pinned_commit_sha=pinned,
        stage_outcomes=tuple(entries),
        extractor_outcome=next(
            entry.outcome for entry in entries if entry.stage is PipelineStage.EXTRACTOR
        ),
        workflow_count=len(fingerprints),
        workflow_fingerprints=tuple(fingerprints),
    )


def build_dry_run_runtime(
    state: SQLiteStateStore,
    processor: FixtureProcessor,
    *,
    retry_policy: RetryPolicy | None = None,
) -> DryRunRuntime:
    """Construct the closed Phase 1 runtime under its immutable authority ceiling."""

    resolved_clock = SystemClock()
    resolved_ids = UUIDIdProvider()
    publication_writer = _LocalPublicationPlanner()
    try:
        complete_registry = (
            AdapterRegistration("fixture_processor", processor),
            AdapterRegistration("sqlite_and_manifests", state),
            AdapterRegistration("clock", resolved_clock),
            AdapterRegistration("run_ids", resolved_ids),
            AdapterRegistration("local_publication_planner", publication_writer),
        )
    except ValueError:
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE) from None

    resolved_policy = SideEffectPolicy.phase_one()
    validated = resolved_policy.validate(complete_registry)
    expected_types = (
        FixtureProcessor,
        SQLiteStateStore,
        SystemClock,
        UUIDIdProvider,
        _LocalPublicationPlanner,
    )
    if any(
        type(registration.adapter) is not expected
        for registration, expected in zip(validated, expected_types, strict=True)
    ):
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE)

    runner = PipelineRunner(
        state,
        processor,
        clock=resolved_clock,
        ids=resolved_ids,
        retry_policy=retry_policy,
        publication_writer=publication_writer,
    )
    return DryRunRuntime(runner=runner, registrations=validated, policy=resolved_policy)


def build_phase_two_runtime(
    state: SQLiteStateStore,
    processor: PhaseTwoProcessor,
    *,
    semantic_durability: SemanticDurabilityGuard | None = None,
    _allow_lazy_dependencies: bool = False,
) -> PhaseTwoRuntime:
    """Construct the closed phase-two runtime under its remote-read ceiling."""

    from skillscout.adapters.github import (
        GitHubReadClient as CurrentGitHubReadClient,
    )
    from skillscout.adapters.openai_extract import (
        OpenAIExtractionClient as CurrentOpenAIExtractionClient,
    )
    from skillscout.adapters.state import (
        SQLiteStateStore as CurrentSQLiteStateStore,
    )

    if (
        type(processor) is not PhaseTwoProcessor
        or type(state) is not CurrentSQLiteStateStore
        or type(_allow_lazy_dependencies) is not bool
    ):
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE)
    openai_client = processor.openai
    if (
        not _allow_lazy_dependencies and type(openai_client) is not CurrentOpenAIExtractionClient
    ) or (
        _allow_lazy_dependencies
        and (
            getattr(processor.github, "effect_scope", None) is not EffectScope.REMOTE_READ
            or getattr(openai_client, "effect_scope", None) is not EffectScope.REMOTE_READ
        )
    ):
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE)
    resolved_clock = SystemClock()
    resolved_ids = UUIDIdProvider()
    extraction_writer = _ExtractionSummaryWriter()
    try:
        complete_registry = (
            AdapterRegistration("phase2_processor", processor),
            AdapterRegistration("sqlite_and_manifests", state),
            AdapterRegistration("github_read", processor.github),
            AdapterRegistration("openai_extract", openai_client),
            AdapterRegistration("clock", resolved_clock),
            AdapterRegistration("run_ids", resolved_ids),
            AdapterRegistration("extraction_summary_writer", extraction_writer),
        )
    except ValueError:
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE) from None

    resolved_policy = SideEffectPolicy.phase_two()
    validated = resolved_policy.validate(complete_registry)
    expected_types = (
        PhaseTwoProcessor,
        CurrentSQLiteStateStore,
        CurrentGitHubReadClient,
        CurrentOpenAIExtractionClient,
        SystemClock,
        UUIDIdProvider,
        _ExtractionSummaryWriter,
    )
    if not _allow_lazy_dependencies and any(
        type(registration.adapter) is not expected
        for registration, expected in zip(validated, expected_types, strict=True)
    ):
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE)

    runner = PipelineRunner(
        state,
        processor,
        clock=resolved_clock,
        ids=resolved_ids,
        extraction_writer=extraction_writer,
        semantic_durability=semantic_durability,
    )
    return PhaseTwoRuntime(runner=runner, registrations=validated, policy=resolved_policy)
