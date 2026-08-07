"""Packaged command-line boundary for the local-only dry-run."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
import re
import stat
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Mapping, NoReturn, Sequence

from skillscout.bootstrap import (
    build_discovery_application,
    build_fresh_campaign_lock_application,
    build_fresh_campaign_lock_handoff_application,
    build_fresh_campaign_preflight_application,
    build_fresh_campaign_preparation_application,
    build_nomination_application,
    build_publication_application,
    derive_discovery_publication_admissions,
    discovery_run_authority,
    load_acceptance_attestation,
    load_live_execution_admission_v2,
    record_live_acceptance_authority_v2,
    verify_live_acceptance_authority_state,
    load_acceptance_runtime_config,
    load_verified_state_checkout,
    load_discovery_runtime_config,
    load_fresh_campaign_lock_runtime_config,
    load_fresh_campaign_lock_handoff,
    load_fresh_campaign_preparation_runtime_config,
    load_nomination_runtime_config,
    load_publication_authority_config,
    read_exact_acceptance_state,
    read_exact_discovery_state,
    require_hosted_state_repository,
    require_phase3_gate_b3,
    run_protected_discovery_publication,
    validate_acceptance_state_authority,
    verify_live_acceptance_authority_v2,
    verify_publication_admission_handoff,
)

require_phase3_gate_b3()

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.github import GitHubReadClient
from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.adapters.openai_extract import OpenAIExtractionClient
from skillscout.adapters.openai_generate import OpenAIGenerationClient
from skillscout.adapters.openai_review import OpenAIReviewClient
from skillscout.adapters.semantic_provider import resolve_semantic_provider
from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
from skillscout.adapters.skills_ref import validate_with_official_validator
from skillscout.adapters.state import (
    DescriptorAnchoredCompletedCandidateProjector,
    SQLiteStateStore,
)
from skillscout.adapters.subjects import load_subject
from skillscout.application.phase3 import (
    PHASE_THREE_STAGE_SEQUENCE,
    PhaseThreeApplication,
    PhaseThreeDependencies,
    PhaseThreeRuntimeProfile,
)
from skillscout.application.pipeline import (
    PHASE_TWO_STAGE_SEQUENCE,
    STAGE_SEQUENCE,
    build_dry_run_runtime,
    build_phase_two_runtime,
)
from skillscout.application.ports import (
    ERROR_SUMMARIES,
    CandidateSourceUnavailable,
    ErrorCode,
    SafeFailure,
)
from skillscout.application.processors import PhaseTwoProcessor
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.review import candidate_terminal_summary_bytes
from skillscout.domain.skill_artifacts import (
    FrozenSkillPackageV1,
    materialize_skill_package,
)
from skillscout.domain.validation import (
    build_validation_report,
    validate_local_policy,
    validate_local_structure,
)

__all__ = ["ERROR_SUMMARIES", "ErrorCode", "SafeArgumentParser", "build_parser", "main"]


class SafeArgumentParser(argparse.ArgumentParser):
    """Argument parser that discards rejected input and generated failure detail."""

    def error(self, _message: str) -> NoReturn:
        self.exit(2)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if status == 0:
            super().exit(status, message)
        failure = SafeFailure(ErrorCode.INVALID_CLI_ARGUMENTS)
        diagnostic = json.dumps({"error": failure.as_dict()}, sort_keys=True, separators=(",", ":"))
        sys.stderr.write(f"{diagnostic}\n")
        raise SystemExit(2)


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(prog="skillscout")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=SafeArgumentParser)
    dry_run = commands.add_parser("dry-run")
    dry_run.add_argument("--fixture", required=True, type=Path)
    dry_run.add_argument("--state", required=True, type=Path)
    dry_run.add_argument("--output", required=True, type=Path)
    dry_run.add_argument("--fail-after", choices=STAGE_SEQUENCE)
    extract_repo = commands.add_parser("extract-repo")
    extract_repo.add_argument("--subject", required=True, type=Path)
    extract_repo.add_argument("--state", required=True, type=Path)
    extract_repo.add_argument("--output", required=True, type=Path)
    extract_repo.add_argument("--fail-after", choices=PHASE_TWO_STAGE_SEQUENCE)
    build_candidate = commands.add_parser("build-candidate")
    build_candidate.add_argument("--candidate", required=True, type=Path)
    build_candidate.add_argument("--phase2-state", required=True, type=Path)
    build_candidate.add_argument("--state", required=True, type=Path)
    build_candidate.add_argument("--output", required=True, type=Path)
    build_candidate.add_argument(
        "--fail-after",
        choices=PHASE_THREE_STAGE_SEQUENCE,
    )
    inspect_run = commands.add_parser("inspect-run")
    inspect_run.add_argument("run_id")
    inspect_run.add_argument("--state", required=True, type=Path)
    inspect_run.add_argument("--format", choices=("json",), default="json")
    verify_admission = commands.add_parser("verify-publication-admission")
    verify_admission.add_argument("--candidate", required=True, type=Path)
    verify_admission.add_argument("--phase2-state", required=True, type=Path)
    verify_admission.add_argument("--phase3-state", required=True, type=Path)
    verify_admission.add_argument("--compare-env", action="store_true")
    publish = commands.add_parser("publish-candidate")
    publish.add_argument("--candidate", required=True, type=Path)
    publish.add_argument("--phase2-state", required=True, type=Path)
    publish.add_argument("--phase3-state", required=True, type=Path)
    publish.add_argument("--publication-state", required=True, type=Path)
    discover = commands.add_parser("discover")
    discover.add_argument("--state-repository-id", required=True)
    discover.add_argument("--state-repository-full-name", required=True)
    discover.add_argument("--initial-state-root-digest", required=True)
    publish_discovered = commands.add_parser("publish-discovered")
    publish_discovered.add_argument("--handoff", required=True, type=Path)
    nominate_benchmark = commands.add_parser("nominate-benchmark")
    nominate_benchmark.add_argument("--state-repository-id", required=True)
    nominate_benchmark.add_argument("--state-repository-full-name", required=True)
    nominate_benchmark.add_argument("--initial-state-root-digest", required=True)
    commands.add_parser("prepare-fresh-campaign")
    commands.add_parser("preflight-fresh-campaign")
    commands.add_parser("prepare-fresh-lock-handoff")
    commands.add_parser("lock-fresh-campaign")
    run_acceptance = commands.add_parser("run-acceptance")
    run_acceptance.add_argument(
        "--action",
        required=True,
        choices=("benchmark", "replay"),
    )
    run_acceptance.add_argument("--manifest", required=True, type=Path)
    run_acceptance.add_argument("--acceptance-run-id", required=True)
    run_acceptance.add_argument("--resume-proof", type=Path)
    run_acceptance.add_argument("--state-commit-sha", required=True)
    run_acceptance.add_argument("--state-root-digest", required=True)
    run_acceptance.add_argument("--authority-state-root", required=True, type=Path)
    run_acceptance.add_argument("--authority-state-commit-sha", required=True)
    run_acceptance.add_argument("--authority-state-root-digest", required=True)
    verify_live = commands.add_parser("verify-live-authority")
    verify_live.add_argument("--authority-state-root", required=True, type=Path)
    verify_live.add_argument("--authority-state-root-digest", required=True)
    verify_live.add_argument("--acceptance-run-id", required=True)
    verify_live.add_argument("--authority-digest", required=True)
    verify_live.add_argument("--source-commit-sha", required=True)
    verify_live.add_argument("--runtime-state-commit-sha", required=True)
    verify_live.add_argument("--runtime-state-root-digest", required=True)
    verify_live.add_argument("--state-repository-id", required=True, type=int)
    verify_live.add_argument("--state-repository-full-name", required=True)
    verify_state = commands.add_parser("verify-acceptance-state")
    verify_state.add_argument("--checkout-root", required=True, type=Path)
    verify_state.add_argument("--state-commit-sha", required=True)
    verify_state.add_argument("--state-root-digest", required=True)
    resolve_resume = commands.add_parser("resolve-acceptance-resume")
    resolve_resume.add_argument(
        "--authority-state-root",
        required=True,
        type=Path,
    )
    resolve_resume.add_argument(
        "--authority-state-commit-sha",
        required=True,
    )
    resolve_resume.add_argument(
        "--authority-state-root-digest",
        required=True,
    )
    resolve_resume.add_argument(
        "--campaign-state-root",
        required=True,
        type=Path,
    )
    resolve_resume.add_argument("--acceptance-run-id", required=True)
    resolve_resume.add_argument("--authority-digest", required=True)
    resolve_resume.add_argument("--source-commit-sha", required=True)
    resolve_resume.add_argument(
        "--state-repository-id",
        required=True,
        type=int,
    )
    resolve_resume.add_argument(
        "--state-repository-full-name",
        required=True,
    )
    record_attestation = commands.add_parser("record-acceptance-attestation")
    record_attestation.add_argument("--attestation", required=True, type=Path)
    record_attestation.add_argument(
        "--kind",
        required=True,
        choices=("human-review", "probe-cleanup"),
    )
    record_attestation.add_argument("--state-commit-sha", required=True)
    record_attestation.add_argument("--state-root-digest", required=True)
    record_authority = commands.add_parser("record-live-authority")
    record_authority.add_argument("--acceptance-run-id", required=True)
    verify_authority_state = commands.add_parser("verify-live-authority-state")
    verify_authority_state.add_argument("--authority", required=True, type=Path)
    verify_authority_state.add_argument("--source-commit-sha", required=True)
    rebuild_acceptance = commands.add_parser("rebuild-acceptance")
    rebuild_acceptance.add_argument("--acceptance-run-id", required=True)
    rebuild_acceptance.add_argument("--evidence-root-digest", required=True)
    rebuild_acceptance.add_argument("--state-commit-sha", required=True)
    rebuild_acceptance.add_argument("--state-root-digest", required=True)
    return parser


class CandidateValidationAdapter:
    """Official plus deterministic local validation over one frozen package."""

    def validate(self, *, package: object, authority: object) -> object:
        if type(package) is not FrozenSkillPackageV1:
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID)
        try:
            return build_validation_report(
                package=package,
                candidate_execution_authority=authority,
                official_result=validate_with_official_validator(package),
                local_structure_findings=validate_local_structure(package),
                local_policy_findings=validate_local_policy(package),
            )
        except SafeFailure:
            raise
        except (AttributeError, TypeError, ValueError):
            raise SafeFailure(ErrorCode.STAGE_OUTPUT_INVALID) from None


_EVIDENCE_FILENAMES = {
    "qualification_report": "qualification-report.json",
    "generated_artifact_identity": "generated-artifact-identity.json",
    "package_identity": "package-identity.json",
    "package_manifest": "package-manifest.json",
    "validation_report": "validation-report.json",
    "review_attestation": "review-attestation.json",
    "terminal_summary": "candidate-terminal-summary.json",
}
_MAX_CANDIDATE_EVIDENCE_BYTES = 1_048_576


def _complete_artifacts(
    *,
    terminal_summary: object,
    artifacts: Mapping[str, bytes],
) -> dict[str, bytes]:
    complete = dict(artifacts)
    complete["terminal_summary"] = candidate_terminal_summary_bytes(terminal_summary)
    return complete


def _public_candidate_payload(
    *,
    outcome: str,
    terminal_summary: object,
    artifacts: Mapping[str, bytes],
) -> dict[str, object]:
    complete = _complete_artifacts(
        terminal_summary=terminal_summary,
        artifacts=artifacts,
    )
    evidence = [
        {
            "digest": sha256_digest(payload),
            "kind": kind,
            "path": filename,
        }
        for kind, filename in sorted(_EVIDENCE_FILENAMES.items())
        if (payload := complete.get(kind)) is not None
    ]
    package_payload = complete.get("rendered_package")
    if package_payload is not None:
        package = FrozenSkillPackageV1.model_validate_json(
            package_payload,
            strict=True,
        )
        evidence.append(
            {
                "digest": package.package_identity.package_digest,
                "kind": "skill_package",
                "path": package.stable_slug,
            }
        )
    evidence.sort(key=lambda item: (str(item["kind"]), str(item["path"])))
    return {"evidence": evidence, "outcome": outcome}


class LocalCandidateArtifactProjector:
    """Descriptor-anchored local projection used only for new/resumed results."""

    def project(
        self,
        *,
        output_directory: Path,
        terminal_summary: object,
        artifacts: Mapping[str, bytes],
    ) -> object:
        complete = _complete_artifacts(
            terminal_summary=terminal_summary,
            artifacts=artifacts,
        )
        package_payload = complete.get("rendered_package")
        if package_payload is not None:
            try:
                package = FrozenSkillPackageV1.model_validate_json(
                    package_payload,
                    strict=True,
                )
                if canonical_json_bytes(package) != package_payload:
                    raise ValueError("noncanonical package")
                materialize_skill_package(output_directory, package)
            except (DurableWriteError, TypeError, ValueError):
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

        anchor: AnchoredDirectory | None = None
        try:
            anchor = AnchoredDirectory.open(output_directory, create=True)
            for kind, filename in _EVIDENCE_FILENAMES.items():
                payload = complete.get(kind)
                if payload is None:
                    continue
                existing = anchor.read_bytes(
                    filename,
                    max_bytes=_MAX_CANDIDATE_EVIDENCE_BYTES,
                    missing_ok=True,
                )
                if existing is not None and existing != payload:
                    raise DurableWriteError("immutable_evidence_conflict")
                if existing is None:
                    anchor.atomic_write(
                        filename,
                        payload,
                        max_bytes=_MAX_CANDIDATE_EVIDENCE_BYTES,
                    )
            return _public_candidate_payload(
                outcome=str(getattr(terminal_summary, "outcome")),
                terminal_summary=terminal_summary,
                artifacts=complete,
            )
        except (AttributeError, DurableWriteError, OSError, TypeError, ValueError):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        finally:
            if anchor is not None:
                anchor.close()


class _InterruptingCandidateState:
    """Test seam that interrupts only after a durable Phase 3 checkpoint."""

    def __init__(self, state: SQLiteStateStore, stage: str) -> None:
        self._state = state
        self._stage_count = PHASE_THREE_STAGE_SEQUENCE.index(stage) + 1
        self._tripped = False

    def __getattr__(self, name: str) -> object:
        return getattr(self._state, name)

    def _trip(self, chain: object) -> None:
        if not self._tripped and len(getattr(chain, "results", ())) == self._stage_count:
            self._tripped = True
            raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)

    def persist_candidate_chain(self, chain: object, *, status: str) -> None:
        self._state.persist_candidate_chain(chain, status=status)
        self._trip(chain)

    def persist_candidate_stage(
        self,
        chain: object,
        *,
        stage_payload: bytes,
        recovery_artifacts: Mapping[str, bytes],
        status: str,
    ) -> None:
        self._state.persist_candidate_stage(
            chain,
            stage_payload=stage_payload,
            recovery_artifacts=recovery_artifacts,
            status=status,
        )
        self._trip(chain)

    def close(self) -> None:
        self._state.close()


def _path_identity(path: Path) -> tuple[int, int] | None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(metadata.st_mode):
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
    return (metadata.st_dev, metadata.st_ino)


def _validate_candidate_paths(arguments: argparse.Namespace) -> None:
    candidate = Path(os.path.abspath(os.fspath(arguments.candidate)))
    phase2 = Path(os.path.abspath(os.fspath(arguments.phase2_state)))
    state = Path(os.path.abspath(os.fspath(arguments.state)))
    output = Path(os.path.abspath(os.fspath(arguments.output)))
    if len({candidate, phase2, state, output}) != 4:
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
    if output in state.parents:
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
    existing = [
        identity
        for identity in (
            _path_identity(candidate),
            _path_identity(phase2),
            _path_identity(state),
            _path_identity(output),
        )
        if identity is not None
    ]
    if len(existing) != len(set(existing)):
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
    output_identity = _path_identity(output)
    if output_identity is not None:
        metadata = os.lstat(output)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o022
        ):
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)


def _require_mutable_output_ready(path: Path) -> None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o022
    ):
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
    try:
        with os.scandir(path) as entries:
            if next(entries, None) is not None:
                raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
    except SafeFailure:
        raise
    except OSError:
        raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None


def _run_build_candidate(arguments: argparse.Namespace) -> dict[str, object]:
    _validate_candidate_paths(arguments)
    clients: list[object] = []
    provider = resolve_semantic_provider()
    profile = PhaseThreeRuntimeProfile.from_configured_models(
        generator_model_id=provider.generator_model,
        reviewer_model_id=provider.reviewer_model,
    )

    def generator_factory() -> object:
        client = (
            OpenAIGenerationClient(
                model=profile.configured_generator_model_id,
                max_output_tokens=profile.max_generator_output_tokens,
            )
            if provider.provider.value == "openai"
            else OpenAIGenerationClient(
                model=profile.configured_generator_model_id,
                max_output_tokens=profile.max_generator_output_tokens,
                provider_settings=provider,
            )
        )
        clients.append(client)
        return client

    def reviewer_factory() -> object:
        client = (
            OpenAIReviewClient(
                model=profile.configured_reviewer_model_id,
                max_output_tokens=profile.max_reviewer_output_tokens,
            )
            if provider.provider.value == "openai"
            else OpenAIReviewClient(
                model=profile.configured_reviewer_model_id,
                max_output_tokens=profile.max_reviewer_output_tokens,
                provider_settings=provider,
            )
        )
        clients.append(client)
        return client

    def mutable_state_factory() -> object:
        state: SQLiteStateStore | None = None
        try:
            _require_mutable_output_ready(arguments.output)
        except SafeFailure:
            if not arguments.state.is_file():
                raise
            state = SQLiteStateStore(arguments.state)
            if not state.has_pending_candidate_projection():
                state.close()
                raise
        if state is None:
            state = SQLiteStateStore(arguments.state)
        if arguments.fail_after is not None:
            return _InterruptingCandidateState(state, arguments.fail_after)
        return state

    try:
        result = PhaseThreeApplication(
            source=SQLitePhaseTwoCandidateSource(arguments.phase2_state),
            profile=profile,
            dependencies=PhaseThreeDependencies(
                completed_projector_factory=lambda: DescriptorAnchoredCompletedCandidateProjector(
                    arguments.state
                ),
                mutable_state_factory=mutable_state_factory,
                generator_factory=generator_factory,
                validator_factory=CandidateValidationAdapter,
                reviewer_factory=reviewer_factory,
                artifact_projector_factory=LocalCandidateArtifactProjector,
            ),
        ).run(arguments.candidate, output_directory=arguments.output)
        if result.outcome == ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE.value:
            raise CandidateSourceUnavailable
        if result.completed_projection is not None:
            projection = result.completed_projection
            return _public_candidate_payload(
                outcome=result.outcome,
                terminal_summary=projection.terminal_summary,
                artifacts=projection.artifacts,
            )
        if result.terminal_summary is None or result.artifacts is None:
            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
        return _public_candidate_payload(
            outcome=result.outcome,
            terminal_summary=result.terminal_summary,
            artifacts=result.artifacts,
        )
    finally:
        for client in clients:
            close = getattr(client, "close", None)
            if callable(close):
                close()


def _run_verify_publication_admission(arguments: argparse.Namespace) -> dict[str, str]:
    """Run the authority-blind handoff, or its protected comparison variant."""

    try:
        return verify_publication_admission_handoff(
            candidate=arguments.candidate,
            phase2_state=arguments.phase2_state,
            phase3_state=arguments.phase3_state,
            compare_env=arguments.compare_env,
        )
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _publication_admission_for_publish(arguments: argparse.Namespace) -> tuple[object, object]:
    """Rebuild the exact protected admission after comparison has succeeded."""

    from skillscout.bootstrap import _publication_projection
    from skillscout.domain.publication import (
        CatalogAuthorityV1,
        ReviewerTargetsV1,
        admit_phase3_candidate,
        bind_publication_admission,
        derive_publication_intent,
    )

    verify_publication_admission_handoff(
        candidate=arguments.candidate,
        phase2_state=arguments.phase2_state,
        phase3_state=arguments.phase3_state,
        compare_env=True,
    )
    authority = load_publication_authority_config()
    _resolved, completed = _publication_projection(
        candidate=arguments.candidate,
        phase2_state=arguments.phase2_state,
        phase3_state=arguments.phase3_state,
    )
    evidence = admit_phase3_candidate(
        terminal_summary=completed.terminal_summary,
        terminal_summary_bytes=completed.terminal_summary_bytes,
        artifacts=dict(completed.artifacts),
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
    return bind_publication_admission(
        evidence=evidence, intent=intent, catalog_authority=catalog
    ), authority


def _public_publication_payload(*, result: object, admission: object) -> dict[str, object]:
    """Project the publisher's bounded public result without provider bodies."""

    status = str(getattr(result, "status", "manual_intervention_required"))
    outcome = (
        str(getattr(result, "disposition"))
        if status == "published"
        else "manual_intervention_required"
    )
    if outcome not in {
        "draft_created",
        "draft_updated",
        "draft_reused",
        "manual_intervention_required",
    }:
        outcome = "manual_intervention_required"
    intent = getattr(admission, "intent")
    evidence = getattr(admission, "evidence")
    return {
        "outcome": outcome,
        "catalog_repository_id": getattr(admission, "catalog_repository_id"),
        "base_branch": getattr(intent, "base_branch"),
        "head_branch": getattr(admission, "head_branch"),
        "commit_sha": getattr(result, "commit_sha", None),
        "pull_number": getattr(result, "pull_number", None),
        "pull_url": getattr(result, "pull_url", None),
        "package_digest": getattr(evidence, "package_digest"),
        "marker_digest": getattr(getattr(result, "record", None), "marker_digest", None),
        "reviewers": list(getattr(intent, "reviewers")),
        "reason_code": str(getattr(result, "code", "publication_failed")),
    }


def _run_publish_candidate(arguments: argparse.Namespace) -> dict[str, object]:
    """The only credentialed path; protected comparison completes before token use."""

    try:
        admission, authority = _publication_admission_for_publish(arguments)
        application = build_publication_application(
            admission=admission,
            authority=authority,
            publication_state=arguments.publication_state,
            token_factory=lambda: os.environ["SKILLSCOUT_GITHUB_TOKEN"],
        )
        result = application.run(admission)
        return _public_publication_payload(result=result, admission=admission)
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


_DISCOVERY_QUERY_PATH = Path(__file__).resolve().parents[2] / "config" / "discovery-queries-v1.json"
_DISCOVERY_PIPELINE_STATE = Path("state/databases/pipeline.sqlite3")
_DISCOVERY_OPERATIONS_STATE = Path("state/databases/operations.sqlite3")
_DISCOVERY_PUBLICATION_STATE = Path("state/databases/publication.sqlite3")
_MAX_DISCOVERY_HANDOFF_BYTES = 65_536


def _run_discover(arguments: argparse.Namespace) -> dict[str, object]:
    """Run only the unprotected Phase 2/3 discovery graph."""

    require_hosted_state_repository(
        state_repository_id=arguments.state_repository_id,
        state_repository_full_name=arguments.state_repository_full_name,
    )
    provider = resolve_semantic_provider()
    config = load_discovery_runtime_config(
        state_repository_id=arguments.state_repository_id,
        state_repository_full_name=arguments.state_repository_full_name,
        state_ref="refs/heads/skillscout-state",
        query_set_path=_DISCOVERY_QUERY_PATH,
        pipeline_state=_DISCOVERY_PIPELINE_STATE,
        operations_state=_DISCOVERY_OPERATIONS_STATE,
        publication_state=_DISCOVERY_PUBLICATION_STATE,
        semantic_provider=provider.provider.value,
        extractor_model_id=provider.extract_model,
        generator_model_id=provider.generator_model,
        reviewer_model_id=provider.reviewer_model,
        initial_state_root_digest=arguments.initial_state_root_digest,
    )
    result = build_discovery_application(config).run(discovery_run_authority(config))
    return {
        "run_id": result.run_id,
        "state_root_digest": result.state_root_digest,
        "state_commit_sha": result.state_commit_sha,
        "eligible_count": len(result.eligible_candidates),
        "eligible_candidates": [
            {
                "locator": item.locator,
                "authority_digest": item.authority_digest,
                "workflow_identity_digest": item.workflow_identity_digest,
            }
            for item in result.eligible_candidates
        ],
    }


def _run_nominate_benchmark(arguments: argparse.Namespace) -> dict[str, object]:
    """Run and persist the bounded role-neutral Search nomination."""

    require_hosted_state_repository(
        state_repository_id=arguments.state_repository_id,
        state_repository_full_name=arguments.state_repository_full_name,
    )
    config = load_nomination_runtime_config(
        state_repository_id=arguments.state_repository_id,
        state_repository_full_name=arguments.state_repository_full_name,
        query_set_path=_DISCOVERY_QUERY_PATH,
        operations_state=_DISCOVERY_OPERATIONS_STATE,
        initial_state_root_digest=arguments.initial_state_root_digest,
    )
    authority_digest = sha256_digest(
        {
            "schema_version": "acceptance-nomination-authority-v1",
            "state_repository_id": config.state_repository_id,
            "state_repository_full_name": config.state_repository_full_name,
            "query_set_digest": config.query_set_digest,
            "initial_state_root_digest": config.initial_state_root_digest,
        }
    )
    nomination_run_id = f"nomination-{authority_digest.removeprefix('sha256:')[:32]}"
    result = build_nomination_application(config).run(
        search_run_authority_digest=authority_digest,
        nomination_set_id=nomination_run_id,
        created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    )
    nomination = result.nomination
    return {
        "nomination_run_id": nomination.nomination_set_id,
        "nomination_set_digest": nomination.nomination_set_digest,
        "query_set_digest": nomination.query_set_digest,
        "search_run_authority_digest": authority_digest,
        "state_commit_sha": result.state_commit_sha,
        "state_root_digest": result.state_root_digest,
        "candidate_count": len(nomination.search_derived_entries),
        "search_derived_entries": [
            entry.model_dump(mode="json", exclude_none=False)
            for entry in nomination.search_derived_entries
        ],
        "user_nominated_entries": [
            entry.model_dump(mode="json", exclude_none=False)
            for entry in nomination.user_nominated_entries
        ],
        "status": "nomination_persisted",
    }


def _fresh_campaign_preparation_config() -> object:
    """Derive the state-only fresh preparation authority from fixed repository settings."""

    repository_id, repository_full_name = _protected_state_repository()
    return load_fresh_campaign_preparation_runtime_config(
        state_repository_id=repository_id,
        state_repository_full_name=repository_full_name,
        query_set_path=_DISCOVERY_QUERY_PATH,
        operations_state=_DISCOVERY_OPERATIONS_STATE,
    )


def _fresh_campaign_lock_source_context() -> tuple[int, str, str, int, int, str]:
    """Accept only GitHub-provided workflow-dispatch identity, never a caller assertion."""

    try:
        source_repository_id = os.environ["GITHUB_REPOSITORY_ID"]
        source_repository = os.environ["GITHUB_REPOSITORY"]
        source_commit_sha = os.environ["GITHUB_SHA"]
        run_id = os.environ["GITHUB_RUN_ID"]
        run_attempt = os.environ["GITHUB_RUN_ATTEMPT"]
        actor_id = os.environ["GITHUB_ACTOR_ID"]
        actor_login = os.environ["GITHUB_ACTOR"]
        triggering_actor_login = os.environ["GITHUB_TRIGGERING_ACTOR"]
        if (
            os.environ["GITHUB_EVENT_NAME"] != "workflow_dispatch"
            or not source_repository_id.isascii()
            or not source_repository_id.isdecimal()
            or source_repository_id.startswith("0")
            or source_repository.count("/") != 1
            or len(source_commit_sha) != 40
            or any(character not in "0123456789abcdef" for character in source_commit_sha)
            or not run_id.isdecimal()
            or run_id.startswith("0")
            or not run_attempt.isdecimal()
            or run_attempt != "1"
            or not actor_id.isdecimal()
            or actor_id.startswith("0")
            or re.fullmatch(r"[A-Za-z0-9-]{1,39}", actor_login) is None
            or triggering_actor_login != actor_login
        ):
            raise ValueError
        return (
            int(source_repository_id),
            source_repository,
            source_commit_sha,
            int(run_id),
            int(run_attempt),
            f"workflow_dispatch:{actor_id}:{actor_login}",
        )
    except Exception:
        raise ValueError("fresh campaign source context rejected") from None


def _run_prepare_fresh_campaign() -> dict[str, object]:
    """Run only the bounded Search nomination from the current canonical parent."""

    from skillscout.application.acceptance import FreshCampaignPreparationError

    try:
        config = _fresh_campaign_preparation_config()
        result = build_fresh_campaign_preparation_application(config).run(
            created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        nomination = result.nomination
        return {
            "nomination_set_id": nomination.nomination_set_id,
            "nomination_set_digest": nomination.nomination_set_digest,
            "search_run_authority_digest": nomination.search_run_authority_digest,
            "state_commit_sha": result.state_commit_sha,
            "state_root_digest": result.state_root_digest,
            "candidate_count": len(nomination.search_derived_entries),
            "search_derived_entries": [
                entry.model_dump(mode="json", exclude_none=False)
                for entry in nomination.search_derived_entries
            ],
            "status": "fresh_campaign_prepared",
        }
    except FreshCampaignPreparationError as failure:
        print(
            json.dumps(
                {
                    "diagnostic": {
                        "stage": failure.stage,
                        "error_code": failure.error_code,
                    }
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        try:
            code = ErrorCode(failure.error_code)
        except ValueError:
            code = ErrorCode.STATE_INTEGRITY_ERROR
        raise SafeFailure(code) from None
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_preflight_fresh_campaign() -> dict[str, object]:
    """Run bounded read-only state and Search probes and print only safe facts."""

    try:
        config = _fresh_campaign_preparation_config()
        result = build_fresh_campaign_preflight_application(config).run()
        return result.to_json()
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_lock_fresh_campaign() -> dict[str, object]:
    """Read protected approval then persist exactly one fresh V2 benchmark lock."""

    try:
        preparation = _fresh_campaign_preparation_config()
        (
            source_repository_id,
            source_repository_full_name,
            source_commit_sha,
            workflow_run_id,
            workflow_run_attempt,
            trigger_identity,
        ) = _fresh_campaign_lock_source_context()
        config = load_fresh_campaign_lock_runtime_config(
            preparation=preparation,
            repository_root=Path.cwd().resolve(strict=True),
            source_repository_id=source_repository_id,
            source_repository_full_name=source_repository_full_name,
            source_commit_sha=source_commit_sha,
            workflow_run_id=workflow_run_id,
            workflow_run_attempt=workflow_run_attempt,
            trigger_identity=trigger_identity,
        )
        handoff = load_fresh_campaign_lock_handoff(
            config=config,
            handoff_bytes=os.environ["PHASE6_FRESH_LOCK_HANDOFF"].encode("utf-8"),
        )
        result = build_fresh_campaign_lock_application(config, handoff).run(
            created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        lock = result.lock
        return {
            "lock_digest": lock.lock_digest,
            "source_repository_id": lock.source_repository_id,
            "source_repository_full_name": lock.source_repository_full_name,
            "selection_manifest_digest": lock.selection_manifest_digest,
            "nomination_set_digest": lock.nomination_set_digest,
            "approval_record_digest": lock.approval_record_digest,
            "approval_receipt_digest": lock.approval_receipt_digest,
            "state_commit_sha": result.state_commit_sha,
            "state_root_digest": result.state_root_digest,
            "status": "fresh_campaign_locked",
        }
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_prepare_fresh_lock_handoff() -> dict[str, object]:
    """Emit only the canonical protected approval receipt and fixed source handoff."""

    try:
        preparation = _fresh_campaign_preparation_config()
        (
            source_repository_id,
            source_repository_full_name,
            source_commit_sha,
            workflow_run_id,
            workflow_run_attempt,
            trigger_identity,
        ) = _fresh_campaign_lock_source_context()
        config = load_fresh_campaign_lock_runtime_config(
            preparation=preparation,
            repository_root=Path.cwd().resolve(strict=True),
            source_repository_id=source_repository_id,
            source_repository_full_name=source_repository_full_name,
            source_commit_sha=source_commit_sha,
            workflow_run_id=workflow_run_id,
            workflow_run_attempt=workflow_run_attempt,
            trigger_identity=trigger_identity,
        )
        handoff = build_fresh_campaign_lock_handoff_application(config).run()
        return handoff.model_dump(mode="json", exclude_none=False)
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _restore_acceptance_state(
    *,
    state_commit_sha: str,
    state_root_digest: str,
    state_lineage_anchor_commit_sha: str,
    state_lineage_anchor_root_digest: str,
) -> object:
    """Restore one exact state commit only after all caller facts are closed."""

    validate_acceptance_state_authority(
        state_commit_sha=state_commit_sha,
        state_root_digest=state_root_digest,
    )
    validate_acceptance_state_authority(
        state_commit_sha=state_lineage_anchor_commit_sha,
        state_root_digest=state_lineage_anchor_root_digest,
    )
    repository_id, repository_full_name = _protected_state_repository()
    observation = read_exact_acceptance_state(
        state_commit_sha=state_commit_sha,
        state_repository_id=repository_id,
        state_repository_full_name=repository_full_name,
        pipeline_state=_DISCOVERY_PIPELINE_STATE,
        operations_state=_DISCOVERY_OPERATIONS_STATE,
        state_lineage_anchor_commit_sha=state_lineage_anchor_commit_sha,
        state_lineage_anchor_root_digest=state_lineage_anchor_root_digest,
    )
    restored_root = getattr(
        getattr(getattr(observation, "bundle", None), "root", None),
        "root_digest",
        None,
    )
    if restored_root != state_root_digest:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
    return observation


def _phase6_authority_state_lineage_anchor() -> tuple[str, str]:
    """Read the non-secret, independently recorded Phase 6 carrier anchor."""

    try:
        return validate_acceptance_state_authority(
            state_commit_sha=os.environ["PHASE6_AUTHORITY_STATE_COMMIT_SHA"],
            state_root_digest=os.environ["PHASE6_AUTHORITY_STATE_ROOT_DIGEST"],
        )
    except Exception:
        raise ValueError("Phase 6 authority state anchor rejected") from None


def _run_verify_acceptance_state(arguments: argparse.Namespace) -> dict[str, object]:
    """Verify a credential-free complete state checkout and its exact git identity."""

    try:
        checkout = arguments.checkout_root.resolve(strict=True)
        if _checked_out_git_commit(checkout) != arguments.state_commit_sha:
            raise ValueError
        bundle = load_verified_state_checkout(
            checkout_root=checkout,
            expected_root_digest=arguments.state_root_digest,
        )
        if bundle.root.root_digest != arguments.state_root_digest:
            raise ValueError
        return {
            "state_commit_sha": arguments.state_commit_sha,
            "state_root_digest": bundle.root.root_digest,
            "status": "acceptance_state_verified",
        }
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _checked_out_git_commit(checkout: Path) -> str:
    """Resolve a detached or directly referenced checkout without subprocess."""

    git_directory = checkout / ".git"
    if git_directory.is_symlink() or not git_directory.is_dir():
        raise ValueError
    head = (git_directory / "HEAD").read_text(encoding="ascii").strip()
    if len(head) == 40 and all(character in "0123456789abcdef" for character in head):
        return head
    prefix = "ref: "
    if not head.startswith(prefix):
        raise ValueError
    reference = head.removeprefix(prefix)
    if (
        not reference.startswith("refs/")
        or ".." in reference.split("/")
        or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._/-"
            for character in reference
        )
    ):
        raise ValueError
    reference_path = git_directory.joinpath(*reference.split("/"))
    if reference_path.is_symlink() or not reference_path.is_file():
        raise ValueError
    commit = reference_path.read_text(encoding="ascii").strip()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError
    return commit


def _run_acceptance(arguments: argparse.Namespace) -> dict[str, object]:
    """Dispatch one closed acceptance action after immutable state readmission."""

    try:
        if arguments.action not in {"benchmark", "replay"}:
            raise ValueError
        repository_id, repository_full_name = _protected_state_repository()
        admission = load_live_execution_admission_v2(
            authority_state_root=arguments.authority_state_root,
            authority_state_commit_sha=arguments.authority_state_commit_sha,
            authority_state_root_digest=arguments.authority_state_root_digest,
            acceptance_run_id=arguments.acceptance_run_id,
            state_repository_id=repository_id,
            state_repository_full_name=repository_full_name,
        )
        config = load_acceptance_runtime_config(
            manifest_path=arguments.manifest,
            state_commit_sha=arguments.state_commit_sha,
            state_root_digest=arguments.state_root_digest,
            acceptance_run_id=arguments.acceptance_run_id,
            resume_proof_path=getattr(arguments, "resume_proof", None),
            live_admission=admission,
        )
        restored = _restore_acceptance_state(
            state_commit_sha=config.state_commit_sha,
            state_root_digest=config.state_root_digest,
            state_lineage_anchor_commit_sha=config.state_lineage_anchor_commit_sha,
            state_lineage_anchor_root_digest=config.state_lineage_anchor_root_digest,
        )
        if arguments.action == "benchmark":
            return _run_live_benchmark(
                config=config,
                restored=restored,
                acceptance_run_id=arguments.acceptance_run_id,
                live_admission=admission,
            )
        if arguments.action == "replay":
            return _run_live_replay(
                config=config,
                restored=restored,
                acceptance_run_id=arguments.acceptance_run_id,
                live_admission=admission,
            )
        raise ValueError
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_live_benchmark(
    *,
    config: object,
    restored: object,
    acceptance_run_id: str,
    live_admission: object | None = None,
) -> dict[str, object]:
    """Execute the benchmark through the protected production composition."""

    from skillscout.bootstrap import build_live_acceptance_execution

    runtime = build_live_acceptance_execution(
        config=config,
        restored=restored,
        action="benchmark",
        acceptance_run_id=acceptance_run_id,
        live_admission=live_admission,
    )
    result = runtime.run()
    if type(result) is not dict or result.get("status") != "benchmark_complete":
        raise ValueError("invalid benchmark execution result")
    return result


def _run_live_replay(
    *,
    config: object,
    restored: object,
    acceptance_run_id: str,
    live_admission: object | None = None,
) -> dict[str, object]:
    """Execute replay through a composition with no semantic/publication factory."""

    from skillscout.bootstrap import build_live_acceptance_execution

    runtime = build_live_acceptance_execution(
        config=config,
        restored=restored,
        action="replay",
        acceptance_run_id=acceptance_run_id,
        live_admission=live_admission,
    )
    result = runtime.run()
    if type(result) is not dict or result.get("status") != "replay_complete":
        raise ValueError("invalid replay execution result")
    return result


def _load_verified_live_authority(arguments: argparse.Namespace) -> tuple[object, object]:
    """Load an exact carrier checkout and its immutable authority fact."""

    from skillscout.adapters.operations_state import (
        OperationsStateStore,
        restore_acceptance_state_bundle,
    )
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV2

    carrier_commit_sha, carrier_root_digest = validate_acceptance_state_authority(
        state_commit_sha=arguments.authority_state_commit_sha,
        state_root_digest=arguments.authority_state_root_digest,
    )
    checkout = arguments.authority_state_root.resolve(strict=True)
    if _checked_out_git_commit(checkout) != carrier_commit_sha:
        raise ValueError
    bundle = load_verified_state_checkout(
        checkout_root=checkout,
        expected_root_digest=carrier_root_digest,
    )
    with TemporaryDirectory(prefix="skillscout-authority-state-") as temporary:
        temporary_root = Path(temporary).resolve(strict=True)
        operations_path = temporary_root / "operations.sqlite3"
        restore_acceptance_state_bundle(
            bundle,
            pipeline_path=temporary_root / "pipeline.sqlite3",
            operations_path=operations_path,
        )
        with OperationsStateStore(operations_path) as store:
            snapshot = store.acceptance_snapshot(arguments.acceptance_run_id)
    records = tuple(
        record
        for record in snapshot.facts
        if record.kind == "acceptance_live_authority"
        and record.fact_digest == arguments.authority_digest
        and type(record.fact) is LiveAcceptanceAuthorityV2
    )
    if len(records) != 1:
        raise ValueError
    recorded = records[0].fact
    return (
        verify_live_acceptance_authority_v2(
            repository_root=Path.cwd().resolve(strict=True),
            authority_bytes=canonical_json_bytes(recorded) + b"\n",
            observed_source_commit_sha=arguments.source_commit_sha,
            observed_state_commit_sha=recorded.state_commit_sha,
            observed_state_root_digest=recorded.state_root_digest,
            observed_state_repository_id=arguments.state_repository_id,
            observed_state_repository_full_name=arguments.state_repository_full_name,
        ),
        bundle,
    )


def _acceptance_resume_locators_from_bundle(
    bundle: object,
    acceptance_run_id: str,
) -> tuple[object, ...]:
    """Extract only strict operations-owned locator facts from one bundle."""

    locators, _owned_facts = _acceptance_resume_projection_from_bundle(
        bundle,
        acceptance_run_id,
    )
    return locators


def _acceptance_resume_projection_from_bundle(
    bundle: object,
    acceptance_run_id: str,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    """Project strict locators and transition-owned facts from one bundle."""

    from skillscout.adapters.operations_state import (
        OperationsStateStore,
        restore_acceptance_state_bundle,
    )
    from skillscout.application.acceptance import (
        CampaignOwnedFactObservation,
        CampaignResumeLocatorObservation,
    )
    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    with TemporaryDirectory(prefix="skillscout-resume-state-") as temporary:
        temporary_root = Path(temporary).resolve(strict=True)
        operations_path = temporary_root / "operations.sqlite3"
        restore_acceptance_state_bundle(
            bundle,
            pipeline_path=temporary_root / "pipeline.sqlite3",
            operations_path=operations_path,
        )
        with OperationsStateStore(operations_path) as store:
            snapshot = store.acceptance_snapshot(acceptance_run_id)
            exported = store.export_owned_state()
    locators = tuple(
        record
        for record in snapshot.facts
        if record.kind == "acceptance_campaign_resume_locator"
        and type(record.fact) is AcceptanceCampaignResumeLocatorV1
    )
    object_digests: dict[str, str] = {}
    owned_facts: list[CampaignOwnedFactObservation] = []
    semantic_run_id = f"{acceptance_run_id}-semantic"
    transition_kinds = {
        "run",
        "search_page",
        "candidate",
        "discovery_reservation",
        "semantic_reservation",
        "semantic_attempt",
        "workflow_terminal",
        "candidate_terminal",
        "run_summary",
        "acceptance_nomination",
        "acceptance_live_authority",
        "acceptance_budget_reservation",
        "acceptance_fixed_candidate_admission",
        "acceptance_semantic_request_reservation",
        "acceptance_scenario",
        "acceptance_replay",
        "acceptance_replay_evidence",
    }
    for fact in exported.facts:
        payload = json.loads(fact.payload_json)
        if type(payload) is not dict:
            raise ValueError
        value = payload.get("value")
        columns = payload.get("columns")
        if type(value) is not dict or type(columns) is not dict:
            raise ValueError
        if fact.kind == "acceptance_campaign_resume_locator":
            # The durable operations database retains locators from prior
            # campaigns.  Only the locator rows owned by this run belong in
            # the current transition graph; stale rows must not make an
            # otherwise valid fresh campaign fail closed.
            if (
                value.get("acceptance_run_id") != acceptance_run_id
                or columns.get("acceptance_run_id") != acceptance_run_id
            ):
                continue
            if type(value.get("locator_digest")) is not str:
                raise ValueError
            object_digests[value["locator_digest"]] = fact.object_digest
            continue
        if fact.kind not in transition_kinds:
            continue
        owner_run_id = columns.get(
            "acceptance_run_id",
            columns.get("run_id"),
        )
        expected_run_id = (
            acceptance_run_id if fact.kind.startswith("acceptance_") else semantic_run_id
        )
        if owner_run_id != expected_run_id:
            continue
        owned_facts.append(
            CampaignOwnedFactObservation(
                kind=fact.kind,
                object_digest=fact.object_digest,
                semantic_stage=(str(value["stage"]) if fact.kind == "semantic_attempt" else None),
                attempt_no=(int(value["attempt_no"]) if fact.kind == "semantic_attempt" else None),
                semantic_status=(str(value["status"]) if fact.kind == "semantic_attempt" else None),
            )
        )
    if len({item.fact.locator_digest for item in locators}) != len(locators) or set(
        object_digests
    ) != {item.fact.locator_digest for item in locators}:
        raise ValueError
    return (
        tuple(
            CampaignResumeLocatorObservation(
                locator=record.fact,
                object_digest=object_digests[record.fact.locator_digest or ""],
            )
            for record in locators
        ),
        tuple(owned_facts),
    )


def _run_resolve_acceptance_resume(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Resolve one exact campaign descendant from an immutable authority."""

    try:
        from skillscout.adapters.state_branch import (
            ResolverReadBudget,
            StateBranchReadClient,
            StateBranchStore,
            StateLineageAnchor,
        )
        from skillscout.application.acceptance import (
            CampaignStateLineageObservation,
            resolve_campaign_resume_lineage,
        )

        authority, carrier_bundle = _load_verified_live_authority(arguments)
        if (
            authority.authority_digest != arguments.authority_digest
            or authority.source_commit_sha != arguments.source_commit_sha
            or authority.state_repository_id != arguments.state_repository_id
            or authority.state_repository_full_name != arguments.state_repository_full_name
        ):
            raise ValueError
        carrier_commit_sha, carrier_root_digest = validate_acceptance_state_authority(
            state_commit_sha=arguments.authority_state_commit_sha,
            state_root_digest=arguments.authority_state_root_digest,
        )
        if carrier_commit_sha == authority.state_commit_sha:
            raise ValueError
        token = os.environ["SKILLSCOUT_STATE_GITHUB_TOKEN"]
        reader = StateBranchReadClient(
            token=token,
            repository_id=arguments.state_repository_id,
            repository_full_name=arguments.state_repository_full_name,
        )
        try:
            max_campaign_transitions = 160
            # The carrier itself is campaign transition #1, leaving at most
            # 159 descendant edges below it.  Counting the carrier gives an
            # exact 160-commit metadata walk.  The authority's original state
            # is verified only as the carrier's single direct predecessor.
            max_carrier_descendant_hops = max_campaign_transitions - 1
            max_lineage_visits = max_campaign_transitions
            read_budget = ResolverReadBudget()
            head = reader.get_state_ref(read_budget=read_budget).sha
            store = StateBranchStore(reader)
            descending: list[CampaignStateLineageObservation] = []
            restored_bundles: dict[str, object] = {}
            predecessor_anchor = StateLineageAnchor(
                commit_sha=authority.state_commit_sha,
                root_digest=authority.state_root_digest,
                max_hops=1,
            )
            carrier_anchor = StateLineageAnchor(
                commit_sha=carrier_commit_sha,
                root_digest=carrier_root_digest,
                max_hops=max_carrier_descendant_hops,
            )
            # A carrier must be the immediate, typed successor of the
            # human-approved predecessor, and its remote bytes must equal the
            # independently checked-out carrier.  It is deliberately not a
            # mutable descendant of the predecessor anchor.
            store.verify_lineage_anchor(
                commit_sha=carrier_commit_sha,
                root_digest=carrier_root_digest,
                anchor=predecessor_anchor,
                read_budget=read_budget,
            )
            remote_carrier_bundle = store.restore_commit(
                carrier_commit_sha,
                lineage_anchor=carrier_anchor,
                read_budget=read_budget,
            )
            if (
                remote_carrier_bundle.root != carrier_bundle.root
                or remote_carrier_bundle.content_by_path()
                != carrier_bundle.content_by_path()
            ):
                raise ValueError
            predecessor_inspected = store.inspect_commit_root(
                authority.state_commit_sha,
                read_budget=read_budget,
            )
            if predecessor_inspected.root.root_digest != authority.state_root_digest:
                raise ValueError
            predecessor_bundle = store.restore_commit(
                authority.state_commit_sha,
                lineage_anchor=predecessor_anchor,
                read_budget=read_budget,
            )
            predecessor_locators, predecessor_owned_facts = (
                _acceptance_resume_projection_from_bundle(
                    predecessor_bundle,
                    arguments.acceptance_run_id,
                )
            )
            predecessor_observation = CampaignStateLineageObservation(
                commit_sha=authority.state_commit_sha,
                root_digest=predecessor_inspected.root.root_digest,
                parent_commit_sha=(
                    predecessor_inspected.commit.parents[0]
                    if predecessor_inspected.commit.parents
                    else None
                ),
                prior_root_digest=predecessor_inspected.root.prior_root_digest,
                object_digests=predecessor_inspected.object_digests,
                declared_content_bytes=predecessor_inspected.declared_content_bytes,
                resume_locators=predecessor_locators,
                owned_facts=predecessor_owned_facts,
            )
            current = head
            for _index in range(max_lineage_visits):
                inspected = store.inspect_commit_root(
                    current,
                    read_budget=read_budget,
                )
                descending.append(
                    CampaignStateLineageObservation(
                        commit_sha=current,
                        root_digest=inspected.root.root_digest,
                        parent_commit_sha=(
                            inspected.commit.parents[0] if inspected.commit.parents else None
                        ),
                        prior_root_digest=inspected.root.prior_root_digest,
                        object_digests=inspected.object_digests,
                        declared_content_bytes=inspected.declared_content_bytes,
                    )
                )
                if current == carrier_commit_sha:
                    if inspected.root.root_digest != carrier_root_digest:
                        raise ValueError
                    break
                if len(inspected.commit.parents) != 1:
                    raise ValueError
                current = inspected.commit.parents[0]
            else:
                raise ValueError
            for index, observation in enumerate(descending):
                restored = store.restore_commit(
                    observation.commit_sha,
                    lineage_anchor=carrier_anchor,
                    read_budget=read_budget,
                )
                locators, owned_facts = _acceptance_resume_projection_from_bundle(
                    restored,
                    arguments.acceptance_run_id,
                )
                restored_bundles[observation.commit_sha] = restored
                descending[index] = CampaignStateLineageObservation(
                    **{
                        **observation.__dict__,
                        "resume_locators": locators,
                        "owned_facts": owned_facts,
                    }
                )
            head_bundle = restored_bundles[head]
            locators = descending[0].resume_locators
        finally:
            reader.close()
        campaign_checkout = arguments.campaign_state_root.resolve(strict=True)
        if _checked_out_git_commit(campaign_checkout) != head:
            raise ValueError
        checkout_bundle = load_verified_state_checkout(
            checkout_root=campaign_checkout,
            expected_root_digest=head_bundle.root.root_digest,
        )
        if (
            checkout_bundle.root != head_bundle.root
            or checkout_bundle.content_by_path() != head_bundle.content_by_path()
        ):
            raise ValueError
        verified = resolve_campaign_resume_lineage(
            authority_digest=authority.authority_digest,
            acceptance_run_id=arguments.acceptance_run_id,
            original_state_commit_sha=authority.state_commit_sha,
            original_state_root_digest=authority.state_root_digest,
            campaign_head_commit_sha=head,
            observations=(predecessor_observation, *reversed(descending)),
        )
        return {
            "authority_digest": authority.authority_digest,
            "acceptance_run_id": arguments.acceptance_run_id,
            "lineage_commit_shas": list(verified.lineage_commit_shas),
            "lineage_root_digests": list(verified.lineage_root_digests),
            "locator_digest": verified.locator_digest,
            "transition_index": (
                max(
                    (item.locator.transition_index for item in locators),
                    default=0,
                )
            ),
            "state_commit_sha": verified.state_commit_sha,
            "state_root_digest": verified.state_root_digest,
            "status": "acceptance_resume_verified",
        }
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_verify_live_authority(arguments: argparse.Namespace) -> dict[str, object]:
    """Return only sanitized immutable identities from credential-free preflight."""

    try:
        from skillscout.adapters.operations_state import (
            OperationsStateStore,
            restore_acceptance_state_bundle,
        )

        authority_commit_sha, authority_root_digest = validate_acceptance_state_authority(
            state_commit_sha=arguments.runtime_state_commit_sha,
            state_root_digest=arguments.authority_state_root_digest,
        )
        runtime_commit_sha, runtime_root_digest = validate_acceptance_state_authority(
            state_commit_sha=arguments.runtime_state_commit_sha,
            state_root_digest=arguments.runtime_state_root_digest,
        )
        if (authority_commit_sha, authority_root_digest) != (
            runtime_commit_sha,
            runtime_root_digest,
        ):
            raise ValueError
        checkout = arguments.authority_state_root.resolve(strict=True)
        if _checked_out_git_commit(checkout) != runtime_commit_sha:
            raise ValueError
        bundle = load_verified_state_checkout(
            checkout_root=checkout,
            expected_root_digest=runtime_root_digest,
        )
        with TemporaryDirectory(prefix="skillscout-authority-state-") as temporary:
            temporary_root = Path(temporary).resolve(strict=True)
            operations_path = temporary_root / "operations.sqlite3"
            restore_acceptance_state_bundle(
                bundle,
                pipeline_path=temporary_root / "pipeline.sqlite3",
                operations_path=operations_path,
            )
            with OperationsStateStore(operations_path) as store:
                snapshot = store.acceptance_snapshot(arguments.acceptance_run_id)
        records = tuple(
            record
            for record in snapshot.facts
            if record.kind == "acceptance_live_authority"
            and record.fact_digest == arguments.authority_digest
        )
        if len(records) != 1:
            raise ValueError
        authority = verify_live_acceptance_authority_v2(
            repository_root=Path.cwd().resolve(strict=True),
            authority_bytes=canonical_json_bytes(records[0].fact) + b"\n",
            observed_source_commit_sha=arguments.source_commit_sha,
            # The checkout carries the authority fact as a later immutable
            # state object.  The authority itself intentionally binds the
            # earlier human-approved campaign root, not that carrier commit.
            observed_state_commit_sha=records[0].fact.state_commit_sha,
            observed_state_root_digest=records[0].fact.state_root_digest,
            observed_state_repository_id=arguments.state_repository_id,
            observed_state_repository_full_name=(arguments.state_repository_full_name),
        )
        return {
            "acceptance_run_id": arguments.acceptance_run_id,
            "acceptance_workflow_sha256": authority.acceptance_workflow_sha256,
            "authority_digest": authority.authority_digest,
            "manifest_digest": authority.manifest_digest,
            "models": authority.stage_models,
            "provider": authority.semantic_provider,
            "source_commit_sha": authority.source_commit_sha,
            "state_commit_sha": authority.state_commit_sha,
            "state_repository_full_name": (authority.state_repository_full_name),
            "state_repository_id": authority.state_repository_id,
            "state_root_digest": authority.state_root_digest,
            "status": "live_authority_verified",
        }
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_record_acceptance_attestation(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Persist one typed human attestation after exact state readmission."""

    try:
        attestation = load_acceptance_attestation(
            attestation_path=arguments.attestation,
            kind=arguments.kind,
        )
        anchor_commit_sha, anchor_root_digest = _phase6_authority_state_lineage_anchor()
        observation = _restore_acceptance_state(
            state_commit_sha=arguments.state_commit_sha,
            state_root_digest=arguments.state_root_digest,
            state_lineage_anchor_commit_sha=anchor_commit_sha,
            state_lineage_anchor_root_digest=anchor_root_digest,
        )
        from skillscout.adapters.operations_state import OperationsStateStore
        from skillscout.application.acceptance import (
            CleanupAttestationDependencies,
            HumanAttestationDependencies,
            record_cleanup_attestation,
            record_human_attestation,
        )
        from skillscout.domain.acceptance import (
            HumanSkillReviewAttestationV1,
            ProbeCleanupAttestationV1,
        )

        def store_factory() -> object:
            return OperationsStateStore(_DISCOVERY_OPERATIONS_STATE)

        if type(attestation) is HumanSkillReviewAttestationV1:
            dependencies = HumanAttestationDependencies(
                operations_store_factory=store_factory,
                observation_factory=lambda: observation,
            )
            record = record_human_attestation(dependencies, attestation)
        elif type(attestation) is ProbeCleanupAttestationV1:
            cleanup_dependencies = CleanupAttestationDependencies(
                operations_store_factory=store_factory,
                observation_factory=lambda: observation,
            )
            record = record_cleanup_attestation(
                cleanup_dependencies,
                attestation,
            )
        else:
            raise ValueError
        return {
            "acceptance_run_id": record.acceptance_run_id,
            "fact_digest": record.fact_digest,
            "kind": record.kind,
            "state_commit_sha": arguments.state_commit_sha,
            "state_root_digest": arguments.state_root_digest,
        }
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_record_live_authority(arguments: argparse.Namespace) -> dict[str, object]:
    """Persist one V2 authority from fixed state and Actions evidence only."""

    try:
        result = record_live_acceptance_authority_v2(
            acceptance_run_id=arguments.acceptance_run_id,
        )
        if type(result) is not dict or result.get("status") != "live_authority_persisted":
            raise ValueError
        return result
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_verify_live_authority_state(arguments: argparse.Namespace) -> dict[str, object]:
    """Prove the state read boundary before authority persistence is attempted."""

    try:
        protected_id, protected_name = _protected_state_repository()
        from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

        raw = _read_live_authority_input(arguments.authority)
        proposed = LiveAcceptanceAuthorityV1.model_validate_json(raw, strict=True)
        if (
            proposed.state_repository_id != protected_id
            or proposed.state_repository_full_name != protected_name
        ):
            raise ValueError
        authority = verify_live_acceptance_authority_state(
            authority_path=arguments.authority,
            source_commit_sha=arguments.source_commit_sha,
            state_commit_sha=proposed.state_commit_sha,
            state_root_digest=proposed.state_root_digest,
            state_repository_id=protected_id,
            state_repository_full_name=protected_name,
        )
        if type(authority) is not LiveAcceptanceAuthorityV1:
            raise ValueError
        return {
            "authority_digest": authority.authority_digest,
            "source_commit_sha": authority.source_commit_sha,
            "state_commit_sha": authority.state_commit_sha,
            "state_root_digest": authority.state_root_digest,
            "status": "live_authority_state_read_verified",
        }
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_rebuild_acceptance(arguments: argparse.Namespace) -> dict[str, object]:
    """Rebuild one report-root fact from the operations-owned projection."""

    try:
        validate_acceptance_state_authority(
            state_commit_sha=arguments.state_commit_sha,
            state_root_digest=arguments.state_root_digest,
        )
        validate_acceptance_state_authority(
            state_commit_sha=arguments.state_commit_sha,
            state_root_digest=arguments.evidence_root_digest,
        )
        anchor_commit_sha, anchor_root_digest = _phase6_authority_state_lineage_anchor()
        _restore_acceptance_state(
            state_commit_sha=arguments.state_commit_sha,
            state_root_digest=arguments.state_root_digest,
            state_lineage_anchor_commit_sha=anchor_commit_sha,
            state_lineage_anchor_root_digest=anchor_root_digest,
        )
        from skillscout.adapters.operations_state import OperationsStateStore
        from skillscout.application.acceptance import (
            AcceptanceRebuildDependencies,
            rebuild_acceptance_snapshot,
        )

        dependencies = AcceptanceRebuildDependencies(
            operations_store_factory=lambda: OperationsStateStore(_DISCOVERY_OPERATIONS_STATE)
        )
        snapshot = rebuild_acceptance_snapshot(
            dependencies,
            arguments.acceptance_run_id,
        )
        roots = tuple(
            record
            for record in snapshot.facts
            if record.kind == "acceptance_report_root"
            and record.fact_digest == arguments.evidence_root_digest
        )
        if len(roots) != 1:
            raise ValueError
        root = roots[0]
        return {
            "acceptance_run_id": snapshot.acceptance_run_id,
            "evidence_root": root.fact.model_dump(
                mode="json",
                exclude_none=False,
            ),
            "evidence_root_digest": root.fact_digest,
            "state_commit_sha": arguments.state_commit_sha,
            "state_root_digest": arguments.state_root_digest,
        }
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _read_discovery_handoff(path: Path) -> dict[str, object]:
    try:
        metadata = os.lstat(path)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o022
            or not 1 <= metadata.st_size <= _MAX_DISCOVERY_HANDOFF_BYTES
        ):
            raise ValueError
        payload = path.read_bytes()
        if len(payload) != metadata.st_size:
            raise ValueError
        decoded = json.loads(payload)
        if type(decoded) is not dict:
            raise ValueError
        return decoded
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _read_live_authority_input(path: Path) -> bytes:
    """Read one private canonical authority file without following links."""

    try:
        metadata = os.lstat(path)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o022
            or not 1 <= metadata.st_size <= _MAX_CANDIDATE_EVIDENCE_BYTES
        ):
            raise ValueError
        payload = path.read_bytes()
        if len(payload) != metadata.st_size:
            raise ValueError
        return payload
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _protected_state_repository() -> tuple[int, str]:
    try:
        raw_id = os.environ["SKILLSCOUT_STATE_REPOSITORY_ID"]
        full_name = os.environ["SKILLSCOUT_STATE_REPOSITORY_FULL_NAME"]
        if (
            not raw_id.isascii()
            or not raw_id.isdecimal()
            or raw_id.startswith("0")
            or full_name.count("/") != 1
        ):
            raise ValueError
        return int(raw_id), full_name
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def _run_publish_discovered(arguments: argparse.Namespace) -> dict[str, object]:
    """Protected exact-state readmission followed by sequential Draft publishing."""

    try:
        handoff = _read_discovery_handoff(arguments.handoff)
        handoff.pop("eligible_count", None)
        repository_id, repository_full_name = _protected_state_repository()

        def state_reader(commit_sha: str) -> object:
            return read_exact_discovery_state(
                state_commit_sha=commit_sha,
                state_repository_id=repository_id,
                state_repository_full_name=repository_full_name,
                pipeline_state=_DISCOVERY_PIPELINE_STATE,
                operations_state=_DISCOVERY_OPERATIONS_STATE,
                publication_state=_DISCOVERY_PUBLICATION_STATE,
            )

        def admission_deriver(state: object, normalized: object) -> object:
            return derive_discovery_publication_admissions(
                state,
                normalized,
                pipeline_state=_DISCOVERY_PIPELINE_STATE,
                phase3_state=_DISCOVERY_PIPELINE_STATE,
            )

        def publication_factory(*, admission: object, token: str) -> object:
            authority = load_publication_authority_config()
            return build_publication_application(
                admission=admission,
                authority=authority,
                publication_state=_DISCOVERY_PUBLICATION_STATE,
                token_factory=lambda: token,
            )

        results = run_protected_discovery_publication(
            handoff=handoff,
            state_reader=state_reader,
            admission_deriver=admission_deriver,
            catalog_token_factory=lambda: os.environ["SKILLSCOUT_GITHUB_TOKEN"],
            publication_factory=publication_factory,
        )
        return {
            "published_count": len(results),
            "outcomes": [
                {
                    "status": str(getattr(result, "status")),
                    "reason_code": str(getattr(result, "code")),
                    "commit_sha": getattr(result, "commit_sha", None),
                    "pull_number": getattr(result, "pull_number", None),
                    "pull_url": getattr(result, "pull_url", None),
                }
                for result in results
            ],
        }
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    state: SQLiteStateStore | None = None
    command_status = 0
    try:
        if arguments.command == "inspect-run":
            state = SQLiteStateStore(arguments.state)
            payload = state.inspect_run(arguments.run_id)
        elif arguments.command == "build-candidate":
            payload = _run_build_candidate(arguments)
        elif arguments.command == "verify-publication-admission":
            payload = _run_verify_publication_admission(arguments)
        elif arguments.command == "publish-candidate":
            payload = _run_publish_candidate(arguments)
        elif arguments.command == "discover":
            payload = _run_discover(arguments)
        elif arguments.command == "nominate-benchmark":
            payload = _run_nominate_benchmark(arguments)
        elif arguments.command == "prepare-fresh-campaign":
            payload = _run_prepare_fresh_campaign()
        elif arguments.command == "preflight-fresh-campaign":
            payload = _run_preflight_fresh_campaign()
            command_status = 0 if payload.get("status") == "verified" else 1
        elif arguments.command == "prepare-fresh-lock-handoff":
            payload = _run_prepare_fresh_lock_handoff()
        elif arguments.command == "lock-fresh-campaign":
            payload = _run_lock_fresh_campaign()
        elif arguments.command == "run-acceptance":
            payload = _run_acceptance(arguments)
        elif arguments.command == "verify-live-authority":
            payload = _run_verify_live_authority(arguments)
        elif arguments.command == "resolve-acceptance-resume":
            payload = _run_resolve_acceptance_resume(arguments)
        elif arguments.command == "verify-acceptance-state":
            payload = _run_verify_acceptance_state(arguments)
        elif arguments.command == "record-acceptance-attestation":
            payload = _run_record_acceptance_attestation(arguments)
        elif arguments.command == "record-live-authority":
            payload = _run_record_live_authority(arguments)
        elif arguments.command == "verify-live-authority-state":
            payload = _run_verify_live_authority_state(arguments)
        elif arguments.command == "rebuild-acceptance":
            payload = _run_rebuild_acceptance(arguments)
        elif arguments.command == "publish-discovered":
            payload = _run_publish_discovered(arguments)
        elif arguments.command == "extract-repo":
            provider = resolve_semantic_provider()
            subject = load_subject(arguments.subject)
            state = SQLiteStateStore(arguments.state)
            extractor = (
                OpenAIExtractionClient()
                if provider.provider.value == "openai"
                else OpenAIExtractionClient(
                    model=provider.extract_model,
                    provider_settings=provider,
                )
            )
            runtime = build_phase_two_runtime(
                state,
                PhaseTwoProcessor(
                    GitHubReadClient(),
                    extractor,
                ),
            )
            payload = runtime.runner.run(
                subject,
                arguments.output,
                fail_after=arguments.fail_after,
            ).as_dict()
        else:
            subject = load_fixture(arguments.fixture)
            state = SQLiteStateStore(arguments.state)
            runtime = build_dry_run_runtime(state, FixtureProcessor())
            payload = runtime.runner.run(
                subject,
                arguments.output,
                fail_after=arguments.fail_after,
            ).as_dict()
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return command_status
    except SafeFailure as failure:
        print(
            json.dumps({"error": failure.as_dict()}, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 1
    except Exception:
        failure = SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        print(
            json.dumps({"error": failure.as_dict()}, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 1
    finally:
        if state is not None:
            state.close()


if __name__ == "__main__":
    raise SystemExit(main())
