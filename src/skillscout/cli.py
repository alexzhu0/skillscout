"""Packaged command-line boundary for the local-only dry-run."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Mapping, NoReturn, Sequence

from skillscout.bootstrap import (
    build_discovery_application,
    build_publication_application,
    derive_discovery_publication_admissions,
    load_discovery_runtime_config,
    load_publication_authority_config,
    read_exact_discovery_state,
    require_phase3_gate_b3,
    run_protected_discovery_publication,
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
        diagnostic = json.dumps(
            {"error": failure.as_dict()}, sort_keys=True, separators=(",", ":")
        )
        sys.stderr.write(f"{diagnostic}\n")
        raise SystemExit(2)


def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(prog="skillscout")
    commands = parser.add_subparsers(
        dest="command", required=True, parser_class=SafeArgumentParser
    )
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
        if (
            not self._tripped
            and len(getattr(chain, "results", ())) == self._stage_count
        ):
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
                completed_projector_factory=lambda: (
                    DescriptorAnchoredCompletedCandidateProjector(arguments.state)
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


_DISCOVERY_QUERY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "discovery-queries-v1.json"
)
_DISCOVERY_PIPELINE_STATE = Path("state/databases/pipeline.sqlite3")
_DISCOVERY_OPERATIONS_STATE = Path("state/databases/operations.sqlite3")
_DISCOVERY_PUBLICATION_STATE = Path("state/databases/publication.sqlite3")
_MAX_DISCOVERY_HANDOFF_BYTES = 65_536


def _run_discover(arguments: argparse.Namespace) -> dict[str, object]:
    """Run only the unprotected Phase 2/3 discovery graph."""

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
    result = build_discovery_application(config).run()
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
        return 0
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
