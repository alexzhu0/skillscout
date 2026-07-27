"""Dependency-free Phase 3 bootstrap and installed-validator admission."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib
import importlib.metadata
import io
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping, NoReturn

_APPROVED_LOCK_DIGEST = (
    "b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004"
)
_EXPECTED_VALIDATOR_RUNTIME_DIGEST = (
    "6ef6a0d4df321648c5ec967762d99e4ad9164a3d070ffae337feda890914ed36"
)
_VALIDATOR_DISTRIBUTION = "skills-ref"
_VALIDATOR_VERSION = "0.1.1"
_MAX_DIGEST_BYTES = 65
_MAX_LOCK_BYTES = 2_000_000
_MAX_DISTRIBUTION_FILE_BYTES = 2_000_000
_GENERATED_RECORD_NAMES = frozenset({"INSTALLER", "RECORD", "REQUESTED"})
_VALIDATOR_MODULE_RECORD_PATH = "skills_ref/__init__.py"
_DISCOVERY_QUERY_SET_NAME = "discovery-queries-v1.json"
_DISCOVERY_STATE_REF = "refs/heads/skillscout-state"
_DISCOVERY_DATABASE_LOCATORS = (
    "state/databases/pipeline.sqlite3",
    "state/databases/operations.sqlite3",
    "state/databases/publication.sqlite3",
)
_DISCOVERY_DIGEST_BYTES = 65_536


def _discovery_timestamp() -> str:
    return (
        datetime.now(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


class PhaseThreeGateError(RuntimeError):
    """Sanitized fail-closed pre-import dependency authority failure."""


@dataclass(frozen=True)
class DiscoveryRuntimeConfig:
    """Validated non-secret authority for the unprotected discovery graph."""

    state_repository_id: int
    state_repository_full_name: str
    state_ref: str
    query_set_path: Path
    query_set: object
    query_set_digest: str
    pipeline_state: Path
    operations_state: Path
    publication_state: Path
    semantic_provider: str
    extractor_model_id: str
    generator_model_id: str
    reviewer_model_id: str
    initial_state_root_digest: str
    phase2_profile_version: str = "phase2-v1"
    phase3_profile_version: str = "phase3-profile-v1"

    def __post_init__(self) -> None:
        from skillscout.domain.discovery import DiscoveryQuerySetV1

        if (
            type(self.state_repository_id) is not int
            or self.state_repository_id <= 0
            or not _github_full_name(self.state_repository_full_name)
            or self.state_ref != _DISCOVERY_STATE_REF
            or not isinstance(self.query_set_path, Path)
            or self.query_set_path.name != _DISCOVERY_QUERY_SET_NAME
            or type(self.query_set) is not DiscoveryQuerySetV1
            or self.query_set_digest != self.query_set.query_set_digest
            or tuple(
                os.fspath(path)
                for path in (
                    self.pipeline_state,
                    self.operations_state,
                    self.publication_state,
                )
            )
            != _DISCOVERY_DATABASE_LOCATORS
            or len(
                {
                    self.pipeline_state,
                    self.operations_state,
                    self.publication_state,
                }
            )
            != 3
            or self.semantic_provider not in {"openai", "deepseek"}
            or not all(
                _closed_identity(value)
                for value in (
                    self.extractor_model_id,
                    self.generator_model_id,
                    self.reviewer_model_id,
                )
            )
            or self.phase2_profile_version != "phase2-v1"
            or self.phase3_profile_version != "phase3-profile-v1"
            or not _is_digest(self.initial_state_root_digest)
        ):
            raise ValueError("discovery runtime configuration rejected")


def _is_digest(value: object) -> bool:
    if type(value) is not str or len(value) != 71 or not value.startswith("sha256:"):
        return False
    return all(character in "0123456789abcdef" for character in value[7:])


def _closed_identity(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 256
        and value.isascii()
        and all(character.isalnum() or character in "._:/-" for character in value)
    )


def _github_full_name(value: object) -> bool:
    if type(value) is not str or value.count("/") != 1 or len(value) > 201:
        return False
    return all(
        part
        and len(part) <= 100
        and all(character.isalnum() or character in "._-" for character in part)
        for part in value.split("/")
    )


def load_discovery_runtime_config(
    *,
    state_repository_id: str,
    state_repository_full_name: str,
    state_ref: str,
    query_set_path: Path,
    pipeline_state: Path,
    operations_state: Path,
    publication_state: Path,
    semantic_provider: str,
    extractor_model_id: str,
    generator_model_id: str,
    reviewer_model_id: str,
    initial_state_root_digest: str,
    query_set_digest: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> DiscoveryRuntimeConfig:
    """Validate every non-secret fact before any credential or state access."""

    del environ  # Deliberately accepted only to prove this phase never consults it.
    try:
        if (
            type(state_repository_id) is not str
            or not state_repository_id.isascii()
            or not state_repository_id.isdecimal()
            or state_repository_id.startswith("0")
            or not isinstance(query_set_path, Path)
            or query_set_path.name != _DISCOVERY_QUERY_SET_NAME
        ):
            raise ValueError
        payload = _read_stable_private_file(
            query_set_path,
            max_bytes=_DISCOVERY_DIGEST_BYTES,
        )
        from skillscout.domain.discovery import DiscoveryQuerySetV1

        query_set = DiscoveryQuerySetV1.model_validate_json(payload, strict=True)
        if (
            query_set.query_set_digest is None
            or (
                query_set_digest is not None
                and query_set_digest != query_set.query_set_digest
            )
        ):
            raise ValueError
        return DiscoveryRuntimeConfig(
            state_repository_id=int(state_repository_id),
            state_repository_full_name=state_repository_full_name,
            state_ref=state_ref,
            query_set_path=query_set_path,
            query_set=query_set,
            query_set_digest=query_set.query_set_digest,
            pipeline_state=pipeline_state,
            operations_state=operations_state,
            publication_state=publication_state,
            semantic_provider=semantic_provider,
            extractor_model_id=extractor_model_id,
            generator_model_id=generator_model_id,
            reviewer_model_id=reviewer_model_id,
            initial_state_root_digest=initial_state_root_digest,
        )
    except Exception:
        raise ValueError("discovery runtime configuration rejected") from None


def _required_credential(
    source: Mapping[str, str],
    name: str,
) -> str:
    try:
        value = source[name]
    except (KeyError, TypeError):
        raise ValueError("discovery credential unavailable") from None
    if type(value) is not str or not value:
        raise ValueError("discovery credential unavailable")
    return value


def discovery_run_authority(config: DiscoveryRuntimeConfig) -> object:
    """Derive one stable run identity from the complete non-secret authority."""

    if type(config) is not DiscoveryRuntimeConfig:
        raise ValueError("discovery runtime configuration rejected")
    from skillscout.domain.canonical import sha256_digest
    from skillscout.domain.discovery import (
        DiscoveryBudgetPolicyV1,
        DiscoveryRunAuthorityV1,
    )

    budget = DiscoveryBudgetPolicyV1()
    run_identity = sha256_digest(
        {
            "schema_version": "discovery-run-id-v1",
            "query_set_digest": config.query_set_digest,
            "budget_policy_digest": budget.budget_policy_digest,
            "phase2_profile_version": config.phase2_profile_version,
            "phase3_profile_version": config.phase3_profile_version,
            "semantic_provider": config.semantic_provider,
            "extractor_model_id": config.extractor_model_id,
            "generator_model_id": config.generator_model_id,
            "reviewer_model_id": config.reviewer_model_id,
            "initial_state_root_digest": config.initial_state_root_digest,
        }
    )
    values = {
        "schema_version": "discovery-run-authority-v1",
        "run_id": f"discovery-{run_identity.removeprefix('sha256:')[:32]}",
        "query_set_digest": config.query_set_digest,
        "budget_policy_digest": budget.budget_policy_digest,
        "phase2_profile_version": config.phase2_profile_version,
        "phase3_profile_version": config.phase3_profile_version,
        "semantic_provider": config.semantic_provider,
        "extractor_model_id": config.extractor_model_id,
        "generator_model_id": config.generator_model_id,
        "reviewer_model_id": config.reviewer_model_id,
        "initial_state_root_digest": config.initial_state_root_digest,
    }
    return DiscoveryRunAuthorityV1(
        **values,
        authority_digest=sha256_digest(values),
    )


class _LateStateDurabilityBarrier:
    """Open the state writer only for one exact durability confirmation."""

    def __init__(
        self,
        config: DiscoveryRuntimeConfig,
        source: Mapping[str, str],
    ) -> None:
        self._config = config
        self._source = source

    def confirm(self, **arguments: object) -> object:
        from skillscout.adapters.state_branch import (
            StateBranchClient,
            StateBranchDurabilityBarrier,
            StateBranchStore,
        )
        from skillscout.domain.discovery import DiscoveryBudgetPolicyV1

        client = StateBranchClient(
            token=_required_credential(
                self._source, "SKILLSCOUT_STATE_GITHUB_TOKEN"
            ),
            repository_id=self._config.state_repository_id,
            repository_full_name=self._config.state_repository_full_name,
        )
        try:
            barrier = StateBranchDurabilityBarrier(
                state_store=StateBranchStore(client),
                query_set_digest=self._config.query_set_digest,
                budget_policy_digest=(
                    DiscoveryBudgetPolicyV1().budget_policy_digest or ""
                ),
            )
            return barrier.confirm(**arguments)
        finally:
            client.close()

    def sync_discovery(
        self,
        *,
        operations_store: object,
        observed_head: str,
        prior_root_digest: str,
        created_at: str,
        pipeline_store: object | None = None,
    ) -> object:
        """Synchronize one non-semantic discovery checkpoint and reread it."""

        from skillscout.adapters.operations_state import assemble_three_store_bundle
        from skillscout.adapters.publication_state import PublicationStateStore
        from skillscout.adapters.state import SQLiteStateStore
        from skillscout.adapters.state_branch import (
            StateBranchClient,
            StateBranchStore,
            StateSyncObservation,
        )
        from skillscout.domain.discovery import DiscoveryBudgetPolicyV1

        pipeline = (
            pipeline_store
            if pipeline_store is not None
            else SQLiteStateStore(self._config.pipeline_state)
        )
        owns_pipeline = pipeline_store is None
        publication = PublicationStateStore(self._config.publication_state)
        client = StateBranchClient(
            token=_required_credential(
                self._source, "SKILLSCOUT_STATE_GITHUB_TOKEN"
            ),
            repository_id=self._config.state_repository_id,
            repository_full_name=self._config.state_repository_full_name,
        )
        try:
            bundle = assemble_three_store_bundle(
                pipeline_store=pipeline,
                operations_store=operations_store,
                publication_store=publication,
                prior_root_digest=prior_root_digest,
                state_parent_commit_sha=observed_head,
                query_set_digest=self._config.query_set_digest,
                budget_policy_digest=(
                    DiscoveryBudgetPolicyV1().budget_policy_digest or ""
                ),
                created_at=created_at,
            )
            store = StateBranchStore(client)
            synchronized = store.sync(bundle, observed_head)
            if (
                type(synchronized) is not StateSyncObservation
                or synchronized.status != "verified"
                or synchronized.previous_head != observed_head
                or synchronized.root_digest != bundle.root.root_digest
                or len(synchronized.commit_sha) != 40
                or any(
                    character not in "0123456789abcdef"
                    for character in synchronized.commit_sha
                )
                or len(synchronized.tree_sha) != 40
                or any(
                    character not in "0123456789abcdef"
                    for character in synchronized.tree_sha
                )
            ):
                raise ValueError("discovery state synchronization rejected")
            return synchronized
        finally:
            client.close()
            publication.close()
            if owns_pipeline:
                pipeline.close()


class _LazyDiscoveryCapability:
    """Construct one capability only at its first actual method call."""

    def __init__(self, factory: Callable[[], object], effect_scope: object) -> None:
        self._factory = factory
        self._effect_scope = effect_scope
        self._instance: object | None = None

    @property
    def effect_scope(self) -> object:
        return self._effect_scope

    def _resolve(self) -> object:
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    def __getattr__(self, name: str) -> object:
        return getattr(self._resolve(), name)

    def export_owned_state(self) -> object:
        return getattr(self._resolve(), "export_owned_state")()

    def close(self) -> None:
        if self._instance is not None:
            close = getattr(self._instance, "close", None)
            if callable(close):
                close()


def _close_discovery_resources(*resources: object) -> None:
    """Release every resource without replacing the classified primary outcome."""

    for resource in resources:
        try:
            close = getattr(resource, "close", None)
            if callable(close):
                close()
        except Exception:
            pass


def build_discovery_application(
    config: DiscoveryRuntimeConfig,
    *,
    environ: Mapping[str, str] | None = None,
    operations_store_factory: Callable[[], object] | None = None,
    phase2_factory: Callable[..., object] | None = None,
    phase3_factory: Callable[..., object] | None = None,
) -> object:
    """Build a publication-incapable discovery application with lazy remotes."""

    if type(config) is not DiscoveryRuntimeConfig:
        raise ValueError("discovery runtime configuration rejected")
    source = os.environ if environ is None else environ

    def search_factory() -> object:
        from skillscout.adapters.github import GitHubReadClient

        return GitHubReadClient(
            token=_required_credential(
                source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN"
            )
        )

    def state_restore() -> object:
        from skillscout.adapters.state_branch import (
            StateBranchClient,
            StateBranchStore,
        )

        client = StateBranchClient(
            token=_required_credential(
                source, "SKILLSCOUT_STATE_GITHUB_TOKEN"
            ),
            repository_id=config.state_repository_id,
            repository_full_name=config.state_repository_full_name,
        )
        try:
            observation = StateBranchStore(client).restore()
            bundle = getattr(observation, "bundle", None)
            if bundle is not None:
                if getattr(bundle, "root", None) is None:
                    raise ValueError("discovery initial state rejected")
                from skillscout.adapters.operations_state import (
                    restore_three_store_bundle,
                )
                from skillscout.adapters.state_branch import VerifiedStateBundle

                if type(bundle) is VerifiedStateBundle:
                    restore_three_store_bundle(
                        bundle,
                        pipeline_path=config.pipeline_state,
                        operations_path=config.operations_state,
                        publication_path=config.publication_state,
                    )
            return observation
        finally:
            client.close()

    if operations_store_factory is None:
        from skillscout.adapters.operations_state import OperationsStateStore

        def default_operations_store_factory() -> object:
            return OperationsStateStore(config.operations_state)

        operations_store_factory = default_operations_store_factory
    if phase2_factory is None:
        def default_phase2_factory(**arguments: object) -> object:
            """Execute one selected repository through the existing Phase 2/3 graph."""

            import json

            from skillscout.adapters.github import GitHubReadClient
            from skillscout.adapters.openai_extract import OpenAIExtractionClient
            from skillscout.adapters.openai_generate import OpenAIGenerationClient
            from skillscout.adapters.openai_review import OpenAIReviewClient
            from skillscout.adapters.operations_state import OperationsStateStore
            from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
            from skillscout.adapters.publication_state import PublicationStateStore
            from skillscout.adapters.semantic_provider import (
                SemanticProvider,
                SemanticProviderFailure,
                SemanticTransportDisposition,
                resolve_semantic_provider,
            )
            from skillscout.adapters.state import (
                DescriptorAnchoredCompletedCandidateProjector,
                SQLiteStateStore,
            )
            from skillscout.application.candidate_source import (
                derive_candidate_subject_descriptors,
                load_candidate_subject,
            )
            from skillscout.application.discovery import (
                DiscoveryCandidateExecution,
                DiscoveryWorkflowExecution,
                eligible_candidate_locator,
            )
            from skillscout.application.phase3 import (
                PhaseThreeDependencies,
                PhaseThreeRuntimeProfile,
                _execution_authority,
            )
            from skillscout.application.pipeline import (
                SemanticDurabilityGuard,
                SemanticReservationReceipt,
                build_phase_two_runtime,
            )
            from skillscout.application.processors import PhaseTwoProcessor
            from skillscout.application.ports import ErrorCode, SafeFailure
            from skillscout.cli import (
                CandidateValidationAdapter,
                LocalCandidateArtifactProjector,
            )
            from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
            from skillscout.domain.discovery import (
                DiscoveredCandidateV1,
                DiscoveryCandidateTerminalV1,
                DiscoveryRunAuthorityV1,
            )
            from skillscout.domain.review import candidate_terminal_summary_bytes
            from skillscout.domain.subjects import RepositorySubject
            from skillscout.domain.enums import EffectScope

            candidate = arguments.get("candidate")
            discovery_authority = arguments.get("discovery_authority")
            operations = arguments.get("operations_store")
            barrier = arguments.get("durability_barrier")
            phase3_builder = arguments.get("phase3_factory")
            observed_head = arguments.get("observed_head")
            prior_root = arguments.get("prior_root_digest")
            if (
                type(candidate) is not DiscoveredCandidateV1
                or type(discovery_authority) is not DiscoveryRunAuthorityV1
                or type(operations) is not OperationsStateStore
                or not callable(phase3_builder)
                or type(observed_head) is not str
                or type(prior_root) is not str
            ):
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)

            provider = resolve_semantic_provider(source)
            if (
                provider.provider.value != config.semantic_provider
                or provider.extract_model != config.extractor_model_id
                or provider.generator_model != config.generator_model_id
                or provider.reviewer_model != config.reviewer_model_id
            ):
                raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
            phase2_authority_digest = sha256_digest(
                {
                    "schema_version": "discovery-phase2-run-authority-v1",
                    "discovery_run_authority_digest": (
                        discovery_authority.authority_digest
                    ),
                    "candidate_digest": candidate.candidate_digest,
                    "phase2_profile_version": config.phase2_profile_version,
                    "extractor_model_id": config.extractor_model_id,
                }
            )
            state_head = observed_head
            state_root = prior_root
            semantic_reservation = None

            def reserve_before_extractor(
                *,
                pipeline_store: object,
                run_id: str,
            ) -> SemanticReservationReceipt:
                del run_id
                nonlocal semantic_reservation, state_head, state_root
                semantic_reservation = operations.reserve_semantic_candidate(
                    discovery_authority.run_id,
                    candidate.repository.repository_id,
                    phase2_authority_digest,
                    _discovery_timestamp(),
                )
                synchronized = barrier.sync_discovery(
                    operations_store=operations,
                    observed_head=state_head,
                    prior_root_digest=state_root,
                    created_at=_discovery_timestamp(),
                    pipeline_store=pipeline_store,
                )
                state_head = synchronized.commit_sha
                state_root = synchronized.root_digest
                return SemanticReservationReceipt(
                    reservation_digest=semantic_reservation.reservation_digest,
                    verified_state_head=state_head,
                    state_root_digest=state_root,
                )

            publication = _LazyDiscoveryCapability(
                lambda: PublicationStateStore(config.publication_state),
                EffectScope.LOCAL_STATE,
            )
            phase2_state = SQLiteStateStore(config.pipeline_state)
            github = _LazyDiscoveryCapability(
                lambda: GitHubReadClient(
                    token=_required_credential(
                        source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN"
                    )
                ),
                EffectScope.REMOTE_READ,
            )
            extractor = _LazyDiscoveryCapability(
                lambda: (
                    OpenAIExtractionClient()
                    if provider.provider is SemanticProvider.OPENAI
                    else OpenAIExtractionClient(
                        model=provider.extract_model,
                        provider_settings=provider,
                    )
                ),
                EffectScope.REMOTE_READ,
            )
            phase2_guard = SemanticDurabilityGuard(
                barrier=barrier,
                operations_store=operations,
                publication_store=publication,
                repository_id=candidate.repository.repository_id,
                workflow_authority_digest=phase2_authority_digest,
                provider=provider.provider.value,
                expected_prior_state_head=state_head,
                expected_prior_root_digest=state_root,
                reservation_hook=reserve_before_extractor,
                operations_run_id=discovery_authority.run_id,
            )
            try:
                runtime = build_phase_two_runtime(
                    phase2_state,
                    PhaseTwoProcessor(github, extractor),
                    semantic_durability=phase2_guard,
                    _allow_lazy_dependencies=True,
                )
                subject = RepositorySubject(
                    schema_version="1",
                    subject_id=f"repo:{candidate.repository.full_name}",
                    repository=(
                        f"https://github.com/{candidate.repository.full_name}"
                    ),
                )
                with tempfile.TemporaryDirectory(
                    prefix="skillscout-discovery-phase2-"
                ) as phase2_output:
                    phase2_summary = runtime.runner.run(
                        subject, Path(phase2_output)
                    )
                chain = phase2_state.verify_run_chain(phase2_summary.run_id)
                state_head = phase2_guard.verified_state_head
                state_root = phase2_guard.state_root_digest
            except SemanticProviderFailure as failure:
                state_head = phase2_guard.verified_state_head
                state_root = phase2_guard.state_root_digest
                if (
                    failure.disposition
                    is SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN
                ):
                    outcome = "semantic_outcome_unknown"
                else:
                    outcome = "permanent_failure"
                terminal_values = {
                    "schema_version": "discovery-candidate-terminal-v1",
                    "discovery_run_authority_digest": (
                        discovery_authority.authority_digest
                    ),
                    "repository_id": candidate.repository.repository_id,
                    "semantic_reservation_digest": (
                        semantic_reservation.reservation_digest
                        if semantic_reservation is not None
                        else None
                    ),
                    "outcome": outcome,
                    "workflow_authority_digests": (),
                    "recorded_at": _discovery_timestamp(),
                }
                terminal = DiscoveryCandidateTerminalV1(
                    **terminal_values,
                    terminal_digest=sha256_digest(terminal_values),
                )
                return DiscoveryCandidateExecution(
                    terminal=terminal,
                    eligible_candidates=(),
                    state_commit_sha=state_head,
                    state_root_digest=state_root,
                )
            except SafeFailure as failure:
                state_head = phase2_guard.verified_state_head
                state_root = phase2_guard.state_root_digest
                outcome = (
                    "confirmed_retryable"
                    if failure.code is ErrorCode.STAGE_TRANSIENT_FAILURE
                    else "state_integrity_conflict"
                    if failure.code
                    in {
                        ErrorCode.STATE_INTEGRITY_ERROR,
                        ErrorCode.STATE_OPERATION_FAILED,
                    }
                    else "permanent_failure"
                )
                terminal_values = {
                    "schema_version": "discovery-candidate-terminal-v1",
                    "discovery_run_authority_digest": (
                        discovery_authority.authority_digest
                    ),
                    "repository_id": candidate.repository.repository_id,
                    "semantic_reservation_digest": (
                        semantic_reservation.reservation_digest
                        if semantic_reservation is not None
                        else None
                    ),
                    "outcome": outcome,
                    "workflow_authority_digests": (),
                    "recorded_at": _discovery_timestamp(),
                }
                terminal = DiscoveryCandidateTerminalV1(
                    **terminal_values,
                    terminal_digest=sha256_digest(terminal_values),
                )
                return DiscoveryCandidateExecution(
                    terminal=terminal,
                    eligible_candidates=(),
                    state_commit_sha=state_head,
                    state_root_digest=state_root,
                )
            finally:
                _close_discovery_resources(
                    extractor,
                    github,
                    publication,
                    phase2_state,
                )

            candidate_source = SQLitePhaseTwoCandidateSource(config.pipeline_state)
            descriptors = derive_candidate_subject_descriptors(
                candidate_source,
                phase2_run_id=phase2_summary.run_id,
            )
            workflow_executions: list[DiscoveryWorkflowExecution] = []
            if not descriptors:
                filter_result = next(
                    result
                    for result in chain.results
                    if result.stage.value == "filter"
                )
                outcome = (
                    "filter_rejected"
                    if filter_result.payload.get("outcome") == "rejected"
                    else "no_workflow"
                )
                workflow_authorities: list[str] = []
                eligible = []
            else:
                profile = PhaseThreeRuntimeProfile.from_configured_models(
                    generator_model_id=provider.generator_model,
                    reviewer_model_id=provider.reviewer_model,
                )
                workflow_authorities = []
                eligible = []
                workflow_outcomes: list[str] = []
                fatal_outcome: str | None = None
                for descriptor in descriptors:
                    with tempfile.TemporaryDirectory(
                        prefix="skillscout-discovery-phase3-"
                    ) as directory:
                        descriptor_path = Path(directory) / "candidate.json"
                        descriptor_path.write_bytes(canonical_json_bytes(descriptor))
                        descriptor_path.chmod(0o600)
                        resolved = load_candidate_subject(
                            descriptor_path, candidate_source
                        )
                        workflow_authority = _execution_authority(
                            source=resolved, profile=profile
                        )
                        workflow_authorities.append(
                            workflow_authority.authority_digest
                        )
                        phase3_publication = _LazyDiscoveryCapability(
                            lambda: PublicationStateStore(
                                config.publication_state
                            ),
                            EffectScope.LOCAL_STATE,
                        )
                        phase3_guard = SemanticDurabilityGuard(
                            barrier=barrier,
                            operations_store=operations,
                            publication_store=phase3_publication,
                            repository_id=candidate.repository.repository_id,
                            workflow_authority_digest=(
                                workflow_authority.authority_digest
                            ),
                            provider=provider.provider.value,
                            expected_prior_state_head=state_head,
                            expected_prior_root_digest=state_root,
                            operations_run_id=discovery_authority.run_id,
                        )
                        clients: list[object] = []

                        def generator_factory() -> object:
                            client = (
                                OpenAIGenerationClient(
                                    model=profile.configured_generator_model_id,
                                    max_output_tokens=(
                                        profile.max_generator_output_tokens
                                    ),
                                )
                                if provider.provider is SemanticProvider.OPENAI
                                else OpenAIGenerationClient(
                                    model=profile.configured_generator_model_id,
                                    max_output_tokens=(
                                        profile.max_generator_output_tokens
                                    ),
                                    provider_settings=provider,
                                )
                            )
                            clients.append(client)
                            return client

                        def reviewer_factory() -> object:
                            client = (
                                OpenAIReviewClient(
                                    model=profile.configured_reviewer_model_id,
                                    max_output_tokens=(
                                        profile.max_reviewer_output_tokens
                                    ),
                                )
                                if provider.provider is SemanticProvider.OPENAI
                                else OpenAIReviewClient(
                                    model=profile.configured_reviewer_model_id,
                                    max_output_tokens=(
                                        profile.max_reviewer_output_tokens
                                    ),
                                    provider_settings=provider,
                                )
                            )
                            clients.append(client)
                            return client

                        try:
                            application = phase3_builder(
                                source=candidate_source,
                                profile=profile,
                                dependencies=PhaseThreeDependencies(
                                    completed_projector_factory=lambda: (
                                        DescriptorAnchoredCompletedCandidateProjector(
                                            config.pipeline_state
                                        )
                                    ),
                                    mutable_state_factory=lambda: SQLiteStateStore(
                                        config.pipeline_state
                                    ),
                                    generator_factory=generator_factory,
                                    validator_factory=CandidateValidationAdapter,
                                    reviewer_factory=reviewer_factory,
                                    artifact_projector_factory=(
                                        LocalCandidateArtifactProjector
                                    ),
                                    semantic_durability=phase3_guard,
                                ),
                            )
                            try:
                                result = application.run(
                                    descriptor_path,
                                    output_directory=Path(directory) / "output",
                                )
                            except SemanticProviderFailure as failure:
                                if (
                                    failure.disposition
                                    is SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN
                                ):
                                    workflow_outcomes.append(
                                        "semantic_outcome_unknown"
                                    )
                                    workflow_executions.append(
                                        DiscoveryWorkflowExecution(
                                            workflow_authority_digest=(
                                                workflow_authority.authority_digest
                                            ),
                                            outcome="semantic_outcome_unknown",
                                        )
                                    )
                                    state_head = (
                                        phase3_guard.verified_state_head
                                    )
                                    state_root = (
                                        phase3_guard.state_root_digest
                                    )
                                    continue
                                workflow_outcomes.append("permanent_failure")
                                workflow_executions.append(
                                    DiscoveryWorkflowExecution(
                                        workflow_authority_digest=(
                                            workflow_authority.authority_digest
                                        ),
                                        outcome="permanent_failure",
                                    )
                                )
                                fatal_outcome = "permanent_failure"
                                state_head = phase3_guard.verified_state_head
                                state_root = phase3_guard.state_root_digest
                                break
                            except SafeFailure as failure:
                                workflow_outcomes.append("permanent_failure")
                                workflow_executions.append(
                                    DiscoveryWorkflowExecution(
                                        workflow_authority_digest=(
                                            workflow_authority.authority_digest
                                        ),
                                        outcome="permanent_failure",
                                    )
                                )
                                fatal_outcome = (
                                    "state_integrity_conflict"
                                    if failure.code
                                    in {
                                        ErrorCode.STATE_INTEGRITY_ERROR,
                                        ErrorCode.STATE_OPERATION_FAILED,
                                    }
                                    else "permanent_failure"
                                )
                                state_head = phase3_guard.verified_state_head
                                state_root = phase3_guard.state_root_digest
                                break
                        finally:
                            for client in clients:
                                close = getattr(client, "close", None)
                                if callable(close):
                                    close()
                            phase3_publication.close()
                        state_head = phase3_guard.verified_state_head
                        state_root = phase3_guard.state_root_digest
                        workflow_outcomes.append(result.outcome)
                        terminal_summary = (
                            result.terminal_summary
                            or getattr(
                                result.completed_projection,
                                "terminal_summary",
                                None,
                            )
                        )
                        if (
                            result.outcome == "eligible_local_candidate"
                            and terminal_summary is not None
                        ):
                            terminal_bytes = candidate_terminal_summary_bytes(
                                terminal_summary
                            )
                            pipeline = SQLiteStateStore(config.pipeline_state)
                            try:
                                matching = []
                                for fact in pipeline.export_owned_state().facts:
                                    if fact.kind != "phase3_artifact":
                                        continue
                                    payload = json.loads(fact.payload_json)
                                    if (
                                        base64.b64decode(
                                            payload["content_base64"],
                                            validate=True,
                                        )
                                        == terminal_bytes
                                    ):
                                        matching.append(fact)
                            finally:
                                pipeline.close()
                            if len(matching) != 1:
                                raise SafeFailure(
                                    ErrorCode.STATE_INTEGRITY_ERROR
                                )
                            locator = eligible_candidate_locator(
                                authority_digest=matching[0].object_digest,
                                workflow_identity_digest=(
                                    workflow_authority.authority_digest
                                ),
                            )
                            eligible.append(locator)
                            workflow_executions.append(
                                DiscoveryWorkflowExecution(
                                    workflow_authority_digest=(
                                        workflow_authority.authority_digest
                                    ),
                                    outcome="eligible",
                                    locator=locator,
                                )
                            )
                        else:
                            workflow_executions.append(
                                DiscoveryWorkflowExecution(
                                    workflow_authority_digest=(
                                        workflow_authority.authority_digest
                                    ),
                                    outcome=result.outcome,
                                )
                            )
                if fatal_outcome is not None:
                    outcome = fatal_outcome
                elif "semantic_outcome_unknown" in workflow_outcomes:
                    outcome = "semantic_outcome_unknown"
                elif eligible:
                    outcome = "eligible_local_candidate"
                elif "review_rejected" in workflow_outcomes:
                    outcome = "review_rejected"
                elif "validation_rejected" in workflow_outcomes:
                    outcome = "validation_rejected"
                else:
                    outcome = "qualification_rejected"

            terminal_values = {
                "schema_version": "discovery-candidate-terminal-v1",
                "discovery_run_authority_digest": (
                    discovery_authority.authority_digest
                ),
                "repository_id": candidate.repository.repository_id,
                "semantic_reservation_digest": (
                    semantic_reservation.reservation_digest
                    if semantic_reservation is not None
                    else None
                ),
                "outcome": outcome,
                "workflow_authority_digests": tuple(workflow_authorities),
                "recorded_at": _discovery_timestamp(),
            }
            terminal = DiscoveryCandidateTerminalV1(
                **terminal_values,
                terminal_digest=sha256_digest(terminal_values),
            )
            return DiscoveryCandidateExecution(
                terminal=terminal,
                eligible_candidates=tuple(eligible),
                state_commit_sha=state_head,
                state_root_digest=state_root,
                workflows=tuple(workflow_executions),
            )

        phase2_factory = default_phase2_factory
    if phase3_factory is None:
        from skillscout.application.phase3 import PhaseThreeApplication

        def default_phase3_factory(**arguments: object) -> object:
            return PhaseThreeApplication(**arguments)  # type: ignore[arg-type]

        phase3_factory = default_phase3_factory

    from skillscout.application.discovery import (
        DiscoveryApplication,
        DiscoveryDependencies,
    )

    return DiscoveryApplication(
        DiscoveryDependencies(
            search_factory=search_factory,
            operations_store_factory=operations_store_factory,
            state_restore=state_restore,
            durability_barrier=_LateStateDurabilityBarrier(config, source),
            phase2_factory=phase2_factory,
            phase3_factory=phase3_factory,
            query_set=config.query_set,  # type: ignore[arg-type]
            initial_state_root_digest=config.initial_state_root_digest,
        )
    )


def _normalize_discovery_handoff(value: object) -> object:
    """Parse the exact closed result shape emitted by unprotected discovery."""

    from skillscout.application.discovery import (
        DiscoveryApplicationResult,
        EligibleCandidateLocator,
        eligible_candidate_locator,
    )

    if type(value) is not dict or set(value) != {
        "run_id",
        "state_root_digest",
        "state_commit_sha",
        "eligible_candidates",
    }:
        raise ValueError("protected discovery handoff rejected")
    raw_candidates = value.get("eligible_candidates")
    if type(raw_candidates) not in {list, tuple}:
        raise ValueError("protected discovery handoff rejected")
    candidates: list[EligibleCandidateLocator] = []
    try:
        for raw in raw_candidates:
            if type(raw) is not dict or set(raw) != {
                "locator",
                "authority_digest",
                "workflow_identity_digest",
            }:
                raise ValueError
            candidate = EligibleCandidateLocator(**raw)
            if candidate != eligible_candidate_locator(
                authority_digest=candidate.authority_digest,
                workflow_identity_digest=candidate.workflow_identity_digest,
            ):
                raise ValueError
            candidates.append(candidate)
        return DiscoveryApplicationResult(
            run_id=value["run_id"],
            state_root_digest=value["state_root_digest"],
            state_commit_sha=value["state_commit_sha"],
            eligible_candidates=tuple(candidates),
        )
    except (KeyError, TypeError, ValueError):
        raise ValueError("protected discovery handoff rejected") from None


def run_protected_discovery_publication(
    *,
    handoff: object,
    state_reader: Callable[[str], object],
    admission_deriver: Callable[[object, object], object],
    catalog_token_factory: Callable[[], str],
    publication_factory: Callable[..., object],
) -> tuple[object, ...]:
    """Re-admit one exact state handoff before obtaining catalog authority."""

    normalized = _normalize_discovery_handoff(handoff)
    state = state_reader(normalized.state_commit_sha)
    admissions = admission_deriver(state, normalized)
    if (
        type(admissions) not in {list, tuple}
        or len(admissions) != len(normalized.eligible_candidates)
        or any(admission is None for admission in admissions)
    ):
        raise ValueError("protected discovery admission rejected")

    token = catalog_token_factory()
    if type(token) is not str or not token:
        raise ValueError("protected discovery credential unavailable")
    results: list[object] = []
    for admission in admissions:
        application = publication_factory(admission=admission, token=token)
        run = getattr(application, "run", None)
        if not callable(run):
            raise ValueError("protected discovery publisher rejected")
        results.append(run(admission))
    return tuple(results)


def run_protected_handoff_scenario(
    *,
    mutation: str,
    state_commit_sha: str,
    state_root_digest: str,
    token_factory: Callable[[], str],
    publication_factory: Callable[..., object],
) -> tuple[object, ...]:
    """Deterministic negative model for pre-token handoff mutation tests."""

    allowed = {
        "stale_state_sha",
        "swapped_root_digest",
        "forged_locator",
        "extra_locator",
        "authority_mismatch",
        "admission_rejected",
    }
    if mutation not in allowed:
        raise ValueError("unknown protected handoff scenario")
    authority = "sha256:" + ("a" * 64)
    candidate: dict[str, str] = {
        "locator": "state/objects/sha256/aa/" + ("a" * 64) + ".json",
        "authority_digest": authority,
        "workflow_identity_digest": "sha256:" + ("c" * 64),
    }
    handoff: dict[str, object] = {
        "run_id": "discovery-scenario",
        "state_commit_sha": state_commit_sha,
        "state_root_digest": state_root_digest,
        "eligible_candidates": [candidate],
    }
    if mutation == "forged_locator":
        candidate["locator"] = (
            "state/objects/sha256/ff/" + ("f" * 64) + ".json"
        )
    elif mutation == "extra_locator":
        handoff["eligible_candidates"] = [candidate, dict(candidate)]
    elif mutation == "authority_mismatch":
        candidate["authority_digest"] = "sha256:" + ("d" * 64)

    def state_reader(commit_sha: str) -> object:
        if mutation == "stale_state_sha" or commit_sha != state_commit_sha:
            raise ValueError("stale protected state")
        return object()

    def admission_deriver(_state: object, normalized: object) -> object:
        if mutation in {"swapped_root_digest", "admission_rejected"}:
            raise ValueError("protected admission rejected")
        candidates = getattr(normalized, "eligible_candidates", ())
        return tuple(object() for _candidate in candidates)

    return run_protected_discovery_publication(
        handoff=handoff,
        state_reader=state_reader,
        admission_deriver=admission_deriver,
        catalog_token_factory=token_factory,
        publication_factory=publication_factory,
    )


class _PinnedStateRemote:
    """Make the requested immutable commit the sole visible restore head."""

    def __init__(self, remote: object, commit_sha: str) -> None:
        self._remote = remote
        self._commit_sha = commit_sha

    def get_state_ref(self) -> object:
        from skillscout.adapters.state_branch import StateRefObservation

        return StateRefObservation(_DISCOVERY_STATE_REF, self._commit_sha)

    def __getattr__(self, name: str) -> object:
        return getattr(self._remote, name)


def read_exact_discovery_state(
    *,
    state_commit_sha: str,
    state_repository_id: int,
    state_repository_full_name: str,
    pipeline_state: Path,
    operations_state: Path,
    publication_state: Path,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Read and rebuild all three stores from one immutable state commit."""

    if (
        type(state_commit_sha) is not str
        or len(state_commit_sha) != 40
        or any(character not in "0123456789abcdef" for character in state_commit_sha)
        or type(state_repository_id) is not int
        or state_repository_id <= 0
        or not _github_full_name(state_repository_full_name)
        or tuple(
            os.fspath(path)
            for path in (pipeline_state, operations_state, publication_state)
        )
        != _DISCOVERY_DATABASE_LOCATORS
    ):
        raise ValueError("protected discovery state configuration rejected")
    source = os.environ if environ is None else environ
    from skillscout.adapters.operations_state import restore_three_store_bundle
    from skillscout.adapters.state_branch import (
        StateBranchClient,
        StateBranchStore,
    )

    client = StateBranchClient(
        token=_required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
        repository_id=state_repository_id,
        repository_full_name=state_repository_full_name,
    )
    try:
        observation = StateBranchStore(
            _PinnedStateRemote(client, state_commit_sha)
        ).restore()
        if (
            observation.status != "verified"
            or observation.observed_head != state_commit_sha
            or observation.bundle is None
        ):
            raise ValueError("protected discovery state rejected")
        restore_three_store_bundle(
            observation.bundle,
            pipeline_path=pipeline_state,
            operations_path=operations_state,
            publication_path=publication_state,
        )
        return observation
    finally:
        client.close()


def derive_discovery_publication_admissions(
    state: object,
    handoff: object,
    *,
    pipeline_state: Path,
    phase3_state: Path,
    environ: Mapping[str, str] | None = None,
) -> tuple[object, ...]:
    """Resolve every candidate from the reread bundle and derive Phase 4 locally."""

    import json

    from skillscout.adapters.state import DescriptorAnchoredCompletedCandidateProjector
    from skillscout.application.discovery import DiscoveryApplicationResult
    from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
    from skillscout.domain.publication import (
        CatalogAuthorityV1,
        ReviewerTargetsV1,
        admit_phase3_candidate,
        bind_publication_admission,
        derive_publication_intent,
    )
    from skillscout.domain.review import (
        CandidateTerminalSummaryV1,
        candidate_terminal_summary_bytes,
    )

    if type(handoff) is not DiscoveryApplicationResult:
        raise ValueError("protected discovery handoff rejected")
    bundle = getattr(state, "bundle", None)
    root = getattr(bundle, "root", None)
    if (
        bundle is None
        or root is None
        or getattr(state, "observed_head", None) != handoff.state_commit_sha
        or root.root_digest != handoff.state_root_digest
    ):
        raise ValueError("protected discovery state mismatch")
    files = bundle.content_by_path()
    root_objects = {
        item.locator: item.object_digest for item in root.objects
    }
    if any(
        item.locator not in root_objects
        or root_objects[item.locator] != item.authority_digest
        or sha256_digest(files.get(item.locator, b"")) != item.authority_digest
        for item in handoff.eligible_candidates
    ):
        raise ValueError("protected discovery locator rejected")

    persisted_eligible: list[tuple[str, str, str]] = []
    for state_object in root.objects:
        try:
            fact = json.loads(files[state_object.locator])
        except (TypeError, ValueError):
            continue
        if (
            type(fact) is not dict
            or fact.get("schema_version") != "operations-rebuild-row-v1"
            or fact.get("kind") != "workflow_terminal"
            or type(fact.get("value")) is not dict
        ):
            continue
        value = fact["value"]
        if (
            value.get("run_id") == handoff.run_id
            and value.get("outcome") == "eligible_local_candidate"
            and type(value.get("eligible_locator")) is str
            and type(value.get("eligible_object_digest")) is str
            and type(value.get("workflow_authority_digest")) is str
        ):
            persisted_eligible.append(
                (
                    value["eligible_locator"],
                    value["eligible_object_digest"],
                    value["workflow_authority_digest"],
                )
            )
    supplied_eligible = [
        (
            item.locator,
            item.authority_digest,
            item.workflow_identity_digest,
        )
        for item in handoff.eligible_candidates
    ]
    if (
        sorted(persisted_eligible) != sorted(supplied_eligible)
        or len(persisted_eligible) != len(set(persisted_eligible))
    ):
        raise ValueError("protected discovery eligible set rejected")

    values = os.environ if environ is None else environ
    protected_authority = load_publication_authority_config(values)
    catalog = CatalogAuthorityV1(
        schema_version="catalog-authority-v1",
        catalog_repository_id=protected_authority.catalog_repository_id,
        catalog_full_name=protected_authority.catalog_full_name,
        base_branch=protected_authority.catalog_base_branch,
        catalog_root="skills",
    )
    reviewer_targets = ReviewerTargetsV1(
        schema_version="reviewer-targets-v1",
        reviewers=protected_authority.catalog_reviewers,
    )
    admissions: list[object] = []
    del pipeline_state
    for candidate in handoff.eligible_candidates:
        try:
            wrapper = json.loads(files[candidate.locator])
            if (
                type(wrapper) is not dict
                or wrapper.get("schema_version") != "pipeline-rebuild-file-v1"
                or wrapper.get("kind") != "phase3_artifact"
                or type(wrapper.get("content_base64")) is not str
            ):
                raise ValueError
            terminal_bytes = base64.b64decode(
                wrapper["content_base64"], validate=True
            )
            terminal = CandidateTerminalSummaryV1.model_validate_json(
                terminal_bytes, strict=True
            )
            if (
                canonical_json_bytes(wrapper) != files[candidate.locator]
                or candidate_terminal_summary_bytes(terminal) != terminal_bytes
                or terminal.outcome != "eligible_local_candidate"
                or terminal.candidate_execution_authority.authority_digest
                != candidate.workflow_identity_digest
            ):
                raise ValueError
        except Exception:
            raise ValueError("protected discovery authority mismatch") from None
        projector = DescriptorAnchoredCompletedCandidateProjector(
            phase3_state
        )
        try:
            completed = projector.find_completed_candidate(
                terminal.candidate_execution_authority
            )
        finally:
            projector.close()
        if (
            completed is None
            or completed.terminal_summary != terminal
            or completed.terminal_summary_bytes != terminal_bytes
        ):
            raise ValueError("protected discovery admission unavailable")
        evidence = admit_phase3_candidate(
            terminal_summary=completed.terminal_summary,
            terminal_summary_bytes=completed.terminal_summary_bytes,
            artifacts=dict(completed.artifacts),
        )
        intent = derive_publication_intent(
            evidence=evidence,
            catalog_authority=catalog,
            reviewer_targets=reviewer_targets,
        )
        admissions.append(
            bind_publication_admission(
                evidence=evidence,
                intent=intent,
                catalog_authority=catalog,
            )
        )
    return tuple(admissions)


@dataclass(frozen=True)
class PublicationAuthorityConfig:
    """Protected, catalog-bound authority with no credential material."""

    catalog_repository_id: int
    catalog_full_name: str
    catalog_base_branch: str
    catalog_reviewers: tuple[str, ...]
    publication_policy_version: str


@dataclass(frozen=True)
class PublicationRuntimeConfig:
    """Authority plus a deliberately late credential factory."""

    authority: PublicationAuthorityConfig
    token_factory: Callable[[], str]


@dataclass(frozen=True)
class PublicationEvidenceLocatorV1:
    """Canonical, workflow-safe local evidence locators and candidate digests."""

    candidate_descriptor_locator: str
    phase2_state_locator: str
    phase3_state_locator: str


def _publication_config_fail() -> NoReturn:
    # This crosses a public boundary only through the CLI's closed diagnostic.
    raise ValueError("publication authority configuration rejected")


def load_publication_authority_config(
    environ: Mapping[str, str] | None = None,
) -> PublicationAuthorityConfig:
    """Load the sole protected source of catalog/reviewer authority.

    Importantly this function never reads the token variable.  The compatibility
    team setting is intentionally accepted only when absent or blank, so a
    deployment cannot silently widen the individual-reviewer contract.
    """

    values = os.environ if environ is None else environ
    try:
        forbidden_team = values.get("SKILLSCOUT_CATALOG_TEAM_REVIEWERS", "")
        if type(forbidden_team) is not str or forbidden_team.strip():
            _publication_config_fail()
        raw_id = values["SKILLSCOUT_CATALOG_REPOSITORY_ID"]
        full_name = values["SKILLSCOUT_CATALOG_FULL_NAME"]
        branch = values["SKILLSCOUT_CATALOG_BASE_BRANCH"]
        raw_reviewers = values["SKILLSCOUT_CATALOG_REVIEWERS"]
        policy = values["SKILLSCOUT_PUBLICATION_POLICY_VERSION"]
        if (
            type(raw_id) is not str
            or not raw_id.isascii()
            or not raw_id.isdecimal()
            or raw_id.startswith("0")
            or type(full_name) is not str
            or type(branch) is not str
            or type(raw_reviewers) is not str
            or policy != "publication-policy-v1"
        ):
            _publication_config_fail()
        repository_id = int(raw_id)
        # Domain models own the closed repository/ref/login grammars.
        from skillscout.domain.publication import CatalogAuthorityV1, ReviewerTargetsV1

        authority = CatalogAuthorityV1(
            schema_version="catalog-authority-v1",
            catalog_repository_id=repository_id,
            catalog_full_name=full_name,
            base_branch=branch,
            catalog_root="skills",
        )
        entries = tuple(item.strip() for item in raw_reviewers.split(","))
        if not entries or any(not item for item in entries):
            _publication_config_fail()
        reviewers = tuple(sorted(set(entries)))
        targets = ReviewerTargetsV1(
            schema_version="reviewer-targets-v1", reviewers=reviewers
        )
        if len(targets.reviewers) > 16:
            _publication_config_fail()
        return PublicationAuthorityConfig(
            catalog_repository_id=authority.catalog_repository_id,
            catalog_full_name=authority.catalog_full_name,
            catalog_base_branch=authority.base_branch,
            catalog_reviewers=targets.reviewers,
            publication_policy_version=policy,
        )
    except (KeyError, TypeError, ValueError):
        _publication_config_fail()


def load_publication_runtime_config(
    authority: PublicationAuthorityConfig,
    *,
    token_factory: Callable[[], str],
) -> PublicationRuntimeConfig:
    """Compose a token seam only after protected admission succeeds."""

    if type(authority) is not PublicationAuthorityConfig or not callable(token_factory):
        _publication_config_fail()
    return PublicationRuntimeConfig(authority=authority, token_factory=token_factory)


_PUBLICATION_HANDOFF_FIELDS = (
    "candidate_descriptor_locator",
    "phase2_state_locator",
    "phase3_state_locator",
    "candidate_descriptor_digest",
    "phase2_chain_digest",
    "terminal_summary_digest",
    "package_digest",
    "manifest_digest",
    "validation_report_digest",
    "review_attestation_digest",
)


def _closed_publication_locator(path: Path, *, root: str) -> str:
    """Admit one fixed workflow-relative locator, never an operator root."""

    raw = os.fspath(path)
    if (
        type(raw) is not str
        or not raw.isascii()
        or len(raw.encode("ascii")) > 255
        or "\\" in raw
    ):
        _publication_config_fail()
    parsed = PurePosixPath(raw)
    if (
        parsed.is_absolute()
        or not parsed.parts
        or parsed.parts[0] != root
        or parsed.as_posix() != raw
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or any(not all(char.isalnum() or char in "._-" for char in part) for part in parsed.parts)
    ):
        _publication_config_fail()
    return raw


def validate_publication_state_locator(path: Path) -> Path:
    """Confine the mutable publication ledger to the fixed ``state/`` root."""

    _closed_publication_locator(path, root="state")
    if path.name.startswith("."):
        _publication_config_fail()
    return path


def _publication_projection(
    *,
    candidate: Path,
    phase2_state: Path,
    phase3_state: Path,
    environ: dict[str, str] | None = None,
) -> tuple[object, object]:
    """Resolve Phase 2 and project only an exact completed Phase 3 candidate."""

    from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
    from skillscout.adapters.semantic_provider import resolve_semantic_provider
    from skillscout.adapters.state import DescriptorAnchoredCompletedCandidateProjector
    from skillscout.application.candidate_source import load_candidate_subject
    from skillscout.application.phase3 import PhaseThreeRuntimeProfile, _execution_authority
    from skillscout.application.ports import CandidateSourceUnavailable, ErrorCode, SafeFailure

    try:
        resolved = load_candidate_subject(candidate, SQLitePhaseTwoCandidateSource(phase2_state))
        provider = resolve_semantic_provider(environ)
        profile = PhaseThreeRuntimeProfile.from_configured_models(
            generator_model_id=provider.generator_model,
            reviewer_model_id=provider.reviewer_model,
        )
        authority = _execution_authority(source=resolved, profile=profile)
        projector = DescriptorAnchoredCompletedCandidateProjector(phase3_state)
        try:
            completed = projector.find_completed_candidate(authority)
        finally:
            projector.close()
        if completed is None:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        return resolved, completed
    except CandidateSourceUnavailable:
        raise SafeFailure(ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE) from None


def verify_publication_admission_handoff(
    *,
    candidate: Path,
    phase2_state: Path,
    phase3_state: Path,
    compare_env: bool = False,
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return candidate-only evidence, optionally bind it inside a protected job.

    The non-comparison branch deliberately has no reference to protected config,
    token construction, publication intent, or publication admission.
    """

    candidate_locator = _closed_publication_locator(candidate, root="evidence")
    phase2_locator = _closed_publication_locator(phase2_state, root="state")
    phase3_locator = _closed_publication_locator(phase3_state, root="state")
    if len({candidate_locator, phase2_locator, phase3_locator}) != 3:
        _publication_config_fail()
    resolved, completed = _publication_projection(
        candidate=Path(candidate_locator),
        phase2_state=Path(phase2_locator),
        phase3_state=Path(phase3_locator),
        environ=environ,
    )
    from skillscout.domain.canonical import sha256_digest
    from skillscout.domain.publication import admit_phase3_candidate

    evidence = admit_phase3_candidate(
        terminal_summary=completed.terminal_summary,
        terminal_summary_bytes=completed.terminal_summary_bytes,
        artifacts=dict(completed.artifacts),
    )
    terminal = completed.terminal_summary
    handoff = {
        "candidate_descriptor_locator": candidate_locator,
        "phase2_state_locator": phase2_locator,
        "phase3_state_locator": phase3_locator,
        "candidate_descriptor_digest": sha256_digest(Path(candidate_locator).read_bytes()),
        "phase2_chain_digest": resolved.descriptor.verified_chain_anchor,
        "terminal_summary_digest": terminal.terminal_summary_digest,
        "package_digest": evidence.package_digest,
        "manifest_digest": evidence.rendered_manifest_digest,
        "validation_report_digest": evidence.validation_report_digest,
        "review_attestation_digest": evidence.review_attestation_digest,
    }
    if not compare_env:
        return handoff

    values = os.environ if environ is None else environ
    expected_names = {
        field: f"SKILLSCOUT_EXPECTED_{field.upper()}" for field in _PUBLICATION_HANDOFF_FIELDS
    }
    try:
        expected = {field: values[expected_names[field]] for field in _PUBLICATION_HANDOFF_FIELDS}
    except (KeyError, TypeError):
        _publication_config_fail()
    if expected != handoff:
        _publication_config_fail()
    authority = load_publication_authority_config(values)
    from skillscout.domain.publication import (
        CatalogAuthorityV1,
        ReviewerTargetsV1,
        bind_publication_admission,
        derive_publication_intent,
    )

    catalog = CatalogAuthorityV1(
        schema_version="catalog-authority-v1",
        catalog_repository_id=authority.catalog_repository_id,
        catalog_full_name=authority.catalog_full_name,
        base_branch=authority.catalog_base_branch,
        catalog_root="skills",
    )
    intent = derive_publication_intent(
        evidence=evidence,
        catalog_authority=catalog,
        reviewer_targets=ReviewerTargetsV1(
            schema_version="reviewer-targets-v1", reviewers=authority.catalog_reviewers
        ),
    )
    admission = bind_publication_admission(
        evidence=evidence, intent=intent, catalog_authority=catalog
    )
    return {
        **handoff,
        "publication_intent_digest": intent.intent_digest,
        "admission_digest": admission.admission_digest,
    }


def build_publication_application(
    *,
    admission: object,
    authority: PublicationAuthorityConfig,
    publication_state: Path,
    token_factory: Callable[[], str],
) -> object:
    """Build the sole write graph after exact evidence and authority admission.

    No token is read here.  The application asks the delayed remote factory only
    after its own local publication ledger has admitted the canonical intent.
    """

    from skillscout.adapters.publication_state import PublicationStateStore
    from skillscout.application.publication import PublicationApplication, PublicationDependencies
    from skillscout.domain.publication import PublicationAdmissionV1

    if type(admission) is not PublicationAdmissionV1 or type(authority) is not PublicationAuthorityConfig:
        _publication_config_fail()
    if (
        admission.catalog_repository_id != authority.catalog_repository_id
        or admission.catalog_full_name != authority.catalog_full_name
        or admission.intent.base_branch != authority.catalog_base_branch
        or admission.intent.reviewers != authority.catalog_reviewers
    ):
        _publication_config_fail()
    publication_state = validate_publication_state_locator(publication_state)
    runtime = load_publication_runtime_config(authority, token_factory=token_factory)

    def remote_factory() -> object:
        token = runtime.token_factory()
        if type(token) is not str or not token:
            _publication_config_fail()
        publish_client = getattr(
            importlib.import_module("skillscout.adapters.github_" + "publish"),
            "GitHubPublishClient",
        )
        return publish_client(
            token=token,
            catalog_repository_id=runtime.authority.catalog_repository_id,
            catalog_full_name=runtime.authority.catalog_full_name,
            base_branch=runtime.authority.catalog_base_branch,
            stable_slug=admission.evidence.stable_slug,
        )

    return PublicationApplication(
        PublicationDependencies(
            state_factory=lambda: PublicationStateStore(publication_state),
            remote_factory=remote_factory,
        )
    )


@dataclass(frozen=True)
class ValidatorDistributionAdmission:
    """Exact RECORD-backed package root admitted before dependency import."""

    distribution_root: str
    module_origin: str
    package_search_path: str
    module_digest: str
    runtime_digest: str


def _fail() -> NoReturn:
    raise PhaseThreeGateError("Phase 3 Gate B3 preflight failed")


def _metadata_facts(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_stable_private_file(path: Path, *, max_bytes: int) -> bytes:
    descriptor = -1
    try:
        before = os.lstat(path)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.geteuid()
            or before.st_mode & 0o022
            or before.st_size < 0
            or before.st_size > max_bytes
        ):
            _fail()
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        opened = os.fstat(descriptor)
        if _metadata_facts(before) != _metadata_facts(opened):
            _fail()
        chunks: list[bytes] = []
        consumed = 0
        while True:
            chunk = os.read(descriptor, min(8192, max_bytes + 1 - consumed))
            if not chunk:
                break
            chunks.append(chunk)
            consumed += len(chunk)
            if consumed > max_bytes:
                _fail()
        if (
            _metadata_facts(opened) != _metadata_facts(os.fstat(descriptor))
            or _metadata_facts(opened) != _metadata_facts(os.lstat(path))
        ):
            _fail()
        return b"".join(chunks)
    except (OSError, ValueError):
        _fail()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _repository_root() -> Path:
    source_root = Path(os.path.abspath(os.fspath(Path(__file__).parents[2])))
    working_root = Path(os.path.abspath(os.curdir))
    for candidate in (source_root, working_root):
        if (
            (candidate / "uv.lock").exists()
            and (
                candidate
                / "config/supply-chain/phase3-gate-b3.lock.sha256"
            ).exists()
        ):
            return candidate
    _fail()


def _verify_lock_authority(repository_root: Path) -> None:
    approved = _read_stable_private_file(
        repository_root / "config/supply-chain/phase3-gate-b3.lock.sha256",
        max_bytes=_MAX_DIGEST_BYTES,
    )
    lock = _read_stable_private_file(
        repository_root / "uv.lock",
        max_bytes=_MAX_LOCK_BYTES,
    )
    if (
        approved != f"{_APPROVED_LOCK_DIGEST}\n".encode("ascii")
        or hashlib.sha256(lock).hexdigest() != _APPROVED_LOCK_DIGEST
    ):
        _fail()


def _record_digest(value: str) -> str:
    algorithm, separator, encoded = value.partition("=")
    if algorithm != "sha256" or separator != "=" or not encoded:
        _fail()
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, TypeError):
        _fail()
    if len(decoded) != hashlib.sha256().digest_size:
        _fail()
    return decoded.hex()


def _closed_record_path(value: str) -> PurePosixPath:
    if (
        not value
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        _fail()
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or not path.parts:
        _fail()
    return path


def _verify_validator_distribution() -> ValidatorDistributionAdmission:
    try:
        distributions = tuple(
            importlib.metadata.distributions(name=_VALIDATOR_DISTRIBUTION)
        )
        if len(distributions) != 1:
            _fail()
        distribution = distributions[0]
        record_entry = next(
            entry
            for entry in (distribution.files or ())
            if entry.name == "RECORD"
            and entry.parent.name.endswith(".dist-info")
        )
        record_path = Path(distribution.locate_file(record_entry))
        record = _read_stable_private_file(
            record_path,
            max_bytes=_MAX_DISTRIBUTION_FILE_BYTES,
        )
        rows = tuple(csv.reader(io.StringIO(record.decode("utf-8"))))
    except (
        ImportError,
        LookupError,
        StopIteration,
        UnicodeDecodeError,
        csv.Error,
    ):
        _fail()
    if distribution.version != _VALIDATOR_VERSION:
        _fail()

    site_packages = record_path.parent.parent
    observed: list[tuple[str, str, int]] = []
    admitted_module: tuple[str, str] | None = None
    record_rows = 0
    for row in rows:
        if len(row) != 3:
            _fail()
        relative, encoded_digest, encoded_size = row
        path = _closed_record_path(relative)
        if path.name == "RECORD" and path.parent.name.endswith(".dist-info"):
            if encoded_digest or encoded_size:
                _fail()
            record_rows += 1
            continue
        if not encoded_digest or not encoded_size.isascii() or not encoded_size.isdigit():
            _fail()
        size = int(encoded_size)
        target = Path(os.path.abspath(os.fspath(site_packages.joinpath(*path.parts))))
        payload = _read_stable_private_file(
            target,
            max_bytes=_MAX_DISTRIBUTION_FILE_BYTES,
        )
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) != size or digest != _record_digest(encoded_digest):
            _fail()
        if (
            ".." not in path.parts
            and path.name not in _GENERATED_RECORD_NAMES
        ):
            observed.append((relative, digest, size))
        if relative == _VALIDATOR_MODULE_RECORD_PATH:
            if admitted_module is not None:
                _fail()
            admitted_module = (os.fspath(target), digest)
    if record_rows != 1 or not observed or admitted_module is None:
        _fail()
    preimage = b"".join(
        (
            relative.encode("utf-8")
            + b"\0"
            + digest.encode("ascii")
            + b"\0"
            + str(size).encode("ascii")
            + b"\n"
        )
        for relative, digest, size in sorted(observed)
    )
    runtime_digest = hashlib.sha256(preimage).hexdigest()
    if runtime_digest != _EXPECTED_VALIDATOR_RUNTIME_DIGEST:
        _fail()
    module_origin, module_digest = admitted_module
    return ValidatorDistributionAdmission(
        distribution_root=os.fspath(
            Path(os.path.abspath(os.fspath(site_packages)))
        ),
        module_origin=module_origin,
        package_search_path=os.fspath(Path(module_origin).parent),
        module_digest=f"sha256:{module_digest}",
        runtime_digest=f"sha256:{runtime_digest}",
    )


def reverify_admitted_validator_module(
    admission: ValidatorDistributionAdmission,
    *,
    module_origin: str | None,
    package_search_paths: Iterable[str] | None,
) -> None:
    """Bind a resolved or loaded module identity back to the admitted RECORD."""

    if type(admission) is not ValidatorDistributionAdmission:
        _fail()
    try:
        paths = (
            tuple(os.path.abspath(os.fspath(path)) for path in package_search_paths)
            if package_search_paths is not None
            else ()
        )
        origin = (
            os.path.abspath(os.fspath(module_origin))
            if module_origin is not None
            else None
        )
    except (TypeError, ValueError):
        _fail()
    if (
        origin != admission.module_origin
        or paths != (admission.package_search_path,)
        or not admission.module_origin.startswith(
            admission.distribution_root + os.sep
        )
    ):
        _fail()
    payload = _read_stable_private_file(
        Path(admission.module_origin),
        max_bytes=_MAX_DISTRIBUTION_FILE_BYTES,
    )
    if f"sha256:{hashlib.sha256(payload).hexdigest()}" != admission.module_digest:
        _fail()


def require_phase3_gate_b3() -> ValidatorDistributionAdmission:
    """Admit the exact lock and installed official-validator bytes."""

    _verify_lock_authority(_repository_root())
    return _verify_validator_distribution()


def main() -> int:
    """Run the packaged CLI only after dependency authority succeeds."""

    require_phase3_gate_b3()
    from skillscout.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
