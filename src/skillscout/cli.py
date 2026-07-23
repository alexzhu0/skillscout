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

from skillscout.bootstrap import require_phase3_gate_b3

require_phase3_gate_b3()

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.github import GitHubReadClient
from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.adapters.openai_extract import OpenAIExtractionClient
from skillscout.adapters.openai_generate import OpenAIGenerationClient
from skillscout.adapters.openai_review import OpenAIReviewClient
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
    profile = PhaseThreeRuntimeProfile()

    def generator_factory() -> object:
        client = OpenAIGenerationClient(
            model=profile.configured_generator_model_id,
            max_output_tokens=profile.max_generator_output_tokens,
        )
        clients.append(client)
        return client

    def reviewer_factory() -> object:
        client = OpenAIReviewClient(
            model=profile.configured_reviewer_model_id,
            max_output_tokens=profile.max_reviewer_output_tokens,
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


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    state: SQLiteStateStore | None = None
    try:
        if arguments.command == "inspect-run":
            state = SQLiteStateStore(arguments.state)
            payload = state.inspect_run(arguments.run_id)
        elif arguments.command == "build-candidate":
            payload = _run_build_candidate(arguments)
        elif arguments.command == "extract-repo":
            subject = load_subject(arguments.subject)
            state = SQLiteStateStore(arguments.state)
            runtime = build_phase_two_runtime(
                state,
                PhaseTwoProcessor(GitHubReadClient(), OpenAIExtractionClient()),
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
