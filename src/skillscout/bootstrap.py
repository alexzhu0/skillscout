"""Dependency-free Phase 3 bootstrap and installed-validator admission."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import re
import select
import shutil
import signal
import stat
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping, NoReturn

_APPROVED_LOCK_DIGEST = "b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004"
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
_ACCEPTANCE_MANIFEST_NAME = "benchmark-manifest.json"
_ACCEPTANCE_MANIFEST_BYTES = 1_048_576
_DISCOVERY_DATABASE_LOCATORS = (
    "state/databases/pipeline.sqlite3",
    "state/databases/operations.sqlite3",
    "state/databases/publication.sqlite3",
)
_DISCOVERY_DIGEST_BYTES = 65_536
ACCEPTANCE_CATALOG_FULL_NAME = "alexzhu0/skillscout-catalog-test"
# Phase-one hosted discovery is intentionally single-tenant: the checked
# baseline below is meaningful only in this state repository.  The workflow's
# token is scoped here as well, so accepting an arbitrary CLI target would
# only create an unreviewed state-authority mode.
_HOSTED_STATE_REPOSITORY_ID = 1_310_897_029
_HOSTED_STATE_REPOSITORY_FULL_NAME = "alexzhu0/skillscout"
_PHASE6_STATE_LINEAGE_ANCHOR_COMMIT_SHA = "37f8dcbf74c85f2471670373fd03f71d9f155bae"
_PHASE6_STATE_LINEAGE_ANCHOR_ROOT_DIGEST = (
    "sha256:b4167cffc31969854260d4acd58b804f4823a4d25d078ef3b5dc88445b75c2e5"
)
_ACCEPTANCE_STATE_LINEAGE_MAX_HOPS = 160
# The same code-reviewed baseline anchors ordinary discovery and Search-only
# nomination.  Those graphs can create hundreds of checkpoints in one run, so
# their bounded horizon is deliberately wider than Phase 6 recovery's 160.
_DISCOVERY_STATE_LINEAGE_MAX_HOPS = 4_096


def _discovery_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


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
    state_lineage_anchor_commit_sha: str = _PHASE6_STATE_LINEAGE_ANCHOR_COMMIT_SHA
    state_lineage_anchor_root_digest: str = _PHASE6_STATE_LINEAGE_ANCHOR_ROOT_DIGEST
    state_lineage_anchor_max_hops: int = _DISCOVERY_STATE_LINEAGE_MAX_HOPS

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
            or not _is_commit_sha(self.state_lineage_anchor_commit_sha)
            or not _is_digest(self.state_lineage_anchor_root_digest)
            or type(self.state_lineage_anchor_max_hops) is not int
            or not 1 <= self.state_lineage_anchor_max_hops <= _DISCOVERY_STATE_LINEAGE_MAX_HOPS
        ):
            raise ValueError("discovery runtime configuration rejected")


@dataclass(frozen=True)
class AcceptanceRuntimeConfig:
    """Validated, non-secret authority for one locked acceptance campaign."""

    manifest_path: Path
    manifest: object
    state_commit_sha: str
    state_root_digest: str
    semantic_provider: str
    extractor_model_id: str
    generator_model_id: str
    reviewer_model_id: str
    live_acceptance_authority_digest: str
    acceptance_run_id: str | None = None
    resume_locator_digest: str | None = None
    resume_transition_index: int = 0
    resume_lineage_commit_shas: tuple[str, ...] = ()
    resume_lineage_root_digests: tuple[str, ...] = ()
    state_lineage_anchor_commit_sha: str | None = None
    state_lineage_anchor_root_digest: str | None = None

    def __post_init__(self) -> None:
        from skillscout.domain.acceptance import LockedBenchmarkManifestV1

        if (
            not isinstance(self.manifest_path, Path)
            or self.manifest_path.name != _ACCEPTANCE_MANIFEST_NAME
            or type(self.manifest) is not LockedBenchmarkManifestV1
            or not _is_commit_sha(self.state_commit_sha)
            or not _is_digest(self.state_root_digest)
            or not _is_digest(self.live_acceptance_authority_digest)
            or (
                self.acceptance_run_id is not None
                and (
                    not _closed_identity(self.acceptance_run_id)
                    or len(self.resume_lineage_commit_shas) != len(self.resume_lineage_root_digests)
                    or not self.resume_lineage_commit_shas
                    or len(self.resume_lineage_commit_shas) > 256
                    or self.resume_lineage_commit_shas[-1] != self.state_commit_sha
                    or self.resume_lineage_root_digests[-1] != self.state_root_digest
                    or any(not _is_commit_sha(item) for item in self.resume_lineage_commit_shas)
                    or any(not _is_digest(item) for item in self.resume_lineage_root_digests)
                    or (
                        self.resume_locator_digest is not None
                        and not _is_digest(self.resume_locator_digest)
                    )
                    or self.resume_transition_index < 0
                    or self.resume_transition_index > 160
                    or (self.resume_transition_index == 0) != (self.resume_locator_digest is None)
                    or self.state_lineage_anchor_commit_sha is None
                    or self.state_lineage_anchor_root_digest is None
                    or not _is_commit_sha(self.state_lineage_anchor_commit_sha)
                    or not _is_digest(self.state_lineage_anchor_root_digest)
                    or len(self.resume_lineage_commit_shas) < 2
                    or (
                        self.state_lineage_anchor_commit_sha,
                        self.state_lineage_anchor_root_digest,
                    )
                    != (
                        self.resume_lineage_commit_shas[1],
                        self.resume_lineage_root_digests[1],
                    )
                )
            )
            or (
                self.acceptance_run_id is None
                and (
                    self.resume_locator_digest is not None
                    or self.resume_transition_index != 0
                    or self.resume_lineage_commit_shas
                    or self.resume_lineage_root_digests
                    or self.state_lineage_anchor_commit_sha is not None
                    or self.state_lineage_anchor_root_digest is not None
                )
            )
            or self.semantic_provider not in {"openai", "deepseek"}
            or not all(
                _closed_identity(value)
                for value in (
                    self.extractor_model_id,
                    self.generator_model_id,
                    self.reviewer_model_id,
                )
            )
        ):
            raise ValueError("acceptance runtime configuration rejected")


@dataclass(frozen=True)
class LiveAcceptanceAuthority:
    """Complete immutable acceptance authority, verified before secret lookup."""

    manifest: object
    manifest_path: Path
    source_commit_sha: str
    acceptance_workflow_sha256: str
    state_commit_sha: str
    state_root_digest: str
    provider: str
    models: tuple[str, str, str]
    max_candidates: int
    max_semantic_candidates: int


def verify_live_acceptance_authority(
    *,
    repository_root: Path,
    authority_bytes: bytes,
    observed_source_commit_sha: str,
    observed_state_commit_sha: str,
    observed_state_root_digest: str,
    observed_state_repository_id: int,
    observed_state_repository_full_name: str,
    environ: Mapping[str, str] | None = None,
    _authority_schema: str = "live-acceptance-authority-v1",
) -> object:
    """Verify a human-approved authority and its exact repository-owned bytes."""

    try:
        manifest_relative = Path(
            "config/acceptance/phase6/benchmark-manifest.json"
        )
        workflow_relative = Path(".github/workflows/phase6-acceptance.yml")
        query_relative = Path("config/discovery-queries-v1.json")
        root = _trusted_repository_root(repository_root)
        if (
            type(authority_bytes) is not bytes
            or not authority_bytes
            or len(authority_bytes) > _ACCEPTANCE_MANIFEST_BYTES
            or _checked_out_repository_commit(root) != observed_source_commit_sha
        ):
            raise ValueError
        manifest_bytes = _read_exact_checked_out_source_file(
            root,
            source_commit_sha=observed_source_commit_sha,
            relative_path=manifest_relative,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        workflow_bytes = _read_exact_checked_out_source_file(
            root,
            source_commit_sha=observed_source_commit_sha,
            relative_path=workflow_relative,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        query_bytes = _read_exact_checked_out_source_file(
            root,
            source_commit_sha=observed_source_commit_sha,
            relative_path=query_relative,
            max_bytes=_DISCOVERY_DIGEST_BYTES,
        )
        from skillscout.adapters.semantic_provider import resolve_semantic_provider
        from skillscout.domain.acceptance import (
            LiveAcceptanceAuthorityV1,
            LiveAcceptanceAuthorityV2,
            LockedBenchmarkManifestV1,
        )
        from skillscout.domain.canonical import canonical_json_bytes
        from skillscout.domain.discovery import (
            DiscoveryBudgetPolicyV1,
            DiscoveryQuerySetV1,
        )
        from skillscout.adapters.openai_generate import (
            GENERATOR_POLICY_VERSION,
            GENERATOR_PROMPT_VERSION,
        )
        from skillscout.domain.extraction import (
            EXTRACT_POLICY_VERSION,
            EXTRACT_PROMPT_VERSION,
            WORKFLOW_SPEC_SCHEMA_VERSION,
        )
        from skillscout.domain.qualification import QUALIFICATION_POLICY_VERSION
        from skillscout.domain.reading import READER_POLICY_VERSION
        from skillscout.domain.review import (
            REVIEW_OUTPUT_SCHEMA_VERSION,
            REVIEW_POLICY_VERSION,
            REVIEW_PROMPT_VERSION,
        )
        from skillscout.domain.skill_artifacts import (
            GENERATION_DRAFT_SCHEMA_VERSION,
        )

        if _authority_schema == "live-acceptance-authority-v1":
            authority_model = LiveAcceptanceAuthorityV1
        elif _authority_schema == "live-acceptance-authority-v2":
            authority_model = LiveAcceptanceAuthorityV2
        else:
            raise ValueError
        authority = authority_model.model_validate_json(
            authority_bytes,
            strict=True,
        )
        manifest = LockedBenchmarkManifestV1.model_validate_json(
            manifest_bytes,
            strict=True,
        )
        query_set = DiscoveryQuerySetV1.model_validate_json(query_bytes, strict=True)
        if authority_bytes not in {
            canonical_json_bytes(authority),
            canonical_json_bytes(authority) + b"\n",
        }:
            raise ValueError
        provider = resolve_semantic_provider(os.environ if environ is None else environ)
        budget = DiscoveryBudgetPolicyV1()
        if (
            authority.source_commit_sha != observed_source_commit_sha
            or authority.state_commit_sha != observed_state_commit_sha
            or authority.state_root_digest != observed_state_root_digest
            or authority.state_repository_id != observed_state_repository_id
            or authority.state_repository_full_name != observed_state_repository_full_name
            or authority.acceptance_workflow_sha256
            != "sha256:" + hashlib.sha256(workflow_bytes).hexdigest()
            or authority.manifest_path != manifest_relative.as_posix()
            or authority.manifest_digest != manifest.manifest_digest
            or authority.nomination_set_digest != manifest.nomination_set_digest
            or authority.lock_attestation_digest != manifest.lock_attestation.attestation_digest
            or authority.query_set_digest != query_set.query_set_digest
            or authority.budget_policy_digest != budget.budget_policy_digest
            or provider.provider.value != authority.semantic_provider
            or provider.base_url != authority.provider_base_url
            or (
                provider.extract_model,
                provider.generator_model,
                provider.reviewer_model,
            )
            != authority.stage_models
            or authority.prompt_versions
            != (
                EXTRACT_PROMPT_VERSION,
                GENERATOR_PROMPT_VERSION,
                REVIEW_PROMPT_VERSION,
            )
            or authority.schema_versions
            != (
                WORKFLOW_SPEC_SCHEMA_VERSION,
                GENERATION_DRAFT_SCHEMA_VERSION,
                REVIEW_OUTPUT_SCHEMA_VERSION,
            )
            or authority.policy_versions
            != tuple(
                sorted(
                    (
                        budget.budget_policy_version,
                        EXTRACT_POLICY_VERSION,
                        GENERATOR_POLICY_VERSION,
                        QUALIFICATION_POLICY_VERSION,
                        READER_POLICY_VERSION,
                        REVIEW_POLICY_VERSION,
                    )
                )
            )
            or (
                _authority_schema == "live-acceptance-authority-v2"
                and (
                    authority.benchmark_lock.selection_manifest != manifest
                    or authority.benchmark_lock_digest
                    != authority.benchmark_lock.lock_digest
                    or authority.selection_manifest_digest != manifest.manifest_digest
                    or authority.entries != authority.benchmark_lock.entries
                )
            )
        ):
            raise ValueError
        return authority
    except Exception:
        raise ValueError("live acceptance authority rejected") from None


def verify_live_acceptance_authority_v2(
    *,
    repository_root: Path,
    authority_bytes: bytes,
    observed_source_commit_sha: str,
    observed_state_commit_sha: str,
    observed_state_root_digest: str,
    observed_state_repository_id: int,
    observed_state_repository_full_name: str,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Verify a fresh V2 authority against the checked-out selection manifest."""

    return verify_live_acceptance_authority(
        repository_root=repository_root,
        authority_bytes=authority_bytes,
        observed_source_commit_sha=observed_source_commit_sha,
        observed_state_commit_sha=observed_state_commit_sha,
        observed_state_root_digest=observed_state_root_digest,
        observed_state_repository_id=observed_state_repository_id,
        observed_state_repository_full_name=observed_state_repository_full_name,
        environ=environ,
        _authority_schema="live-acceptance-authority-v2",
    )


def load_verified_state_checkout(
    *,
    checkout_root: Path,
    expected_root_digest: str,
) -> object:
    """Load and validate every file in one exact checked-out state bundle."""

    try:
        root = _trusted_repository_root(checkout_root)
        if not _is_digest(expected_root_digest):
            raise ValueError
        from skillscout.adapters.state_branch import (
            StateOwnedFile,
            VerifiedStateBundle,
            _validate_bundle,
        )
        from skillscout.domain.discovery import DiscoveryStateRootV1

        root_relative = Path("state/root.json")
        root_bytes = _read_exact_repository_file(
            root,
            root / root_relative,
            root_relative,
            _ACCEPTANCE_MANIFEST_BYTES,
        )
        state_root = DiscoveryStateRootV1.model_validate_json(root_bytes, strict=True)
        if state_root.root_digest != expected_root_digest:
            raise ValueError
        expected_paths = {
            "state/root.json",
            *(item.locator for item in state_root.objects),
            *(item.locator for item in state_root.databases),
        }
        state_directory = root / "state"
        observed_paths = {
            path.relative_to(root).as_posix()
            for path in state_directory.rglob("*")
            if path.is_file()
        }
        if observed_paths != expected_paths:
            raise ValueError
        files = []
        for relative_text in sorted(expected_paths):
            relative = Path(relative_text)
            path = root / relative
            maximum = (
                1_073_741_824
                if relative_text.startswith("state/databases/")
                else _ACCEPTANCE_MANIFEST_BYTES
            )
            files.append(
                StateOwnedFile(
                    relative_text,
                    _read_exact_repository_file(
                        root,
                        path,
                        relative,
                        maximum,
                    ),
                )
            )
        bundle = VerifiedStateBundle(state_root, tuple(files))
        _validate_bundle(
            bundle,
            expected_parent=state_root.state_parent_commit_sha,
        )
        return bundle
    except Exception:
        raise ValueError("checked-out acceptance state rejected") from None


def _trusted_repository_root(repository_root: Path) -> Path:
    if (
        not isinstance(repository_root, Path)
        or not repository_root.is_absolute()
        or repository_root.is_symlink()
    ):
        raise ValueError
    resolved = repository_root.resolve(strict=True)
    if resolved != repository_root or not resolved.is_dir():
        raise ValueError
    return resolved


def _checked_out_repository_commit(repository_root: Path) -> str:
    """Resolve the checked-out source commit without shelling out or following links."""

    git_directory = repository_root / ".git"
    if git_directory.is_symlink() or not git_directory.is_dir():
        raise ValueError
    head_path = git_directory / "HEAD"
    if head_path.is_symlink() or not head_path.is_file():
        raise ValueError
    head = head_path.read_text(encoding="ascii").strip()
    if _is_commit_sha(head):
        return head
    if not head.startswith("ref: "):
        raise ValueError
    reference = head.removeprefix("ref: ")
    if (
        not reference.startswith("refs/")
        or ".." in reference.split("/")
        or re.fullmatch(r"[A-Za-z0-9._/-]{1,256}", reference) is None
    ):
        raise ValueError
    reference_path = git_directory.joinpath(*reference.split("/"))
    if reference_path.is_symlink() or not reference_path.is_file():
        raise ValueError
    commit = reference_path.read_text(encoding="ascii").strip()
    if not _is_commit_sha(commit):
        raise ValueError
    return commit


def _read_exact_repository_file(
    root: Path,
    path: Path,
    expected_relative: Path,
    max_bytes: int,
) -> bytes:
    expected = root / expected_relative
    if path != expected or path.is_symlink():
        raise ValueError
    cursor = root
    for part in expected_relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError
    if path.resolve(strict=True) != expected or not path.is_file():
        raise ValueError
    return _read_stable_private_file(path, max_bytes=max_bytes)


def _read_checked_out_commit_blob(
    root: Path,
    *,
    source_commit_sha: str,
    relative_path: Path,
    max_bytes: int,
) -> bytes:
    """Read one fixed authority file from the checked-out commit, never the index."""

    if (
        not _is_commit_sha(source_commit_sha)
        or relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
        or type(max_bytes) is not int
        or max_bytes <= 0
    ):
        raise ValueError
    git = shutil.which("git", path=os.defpath)
    if git is None:
        raise ValueError
    executable = Path(git)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError
    object_name = f"{source_commit_sha}:{relative_path.as_posix()}"
    environment = {
        "PATH": os.defpath,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
    }

    def read_git(*arguments: str, output_limit: int) -> bytes:
        read_fd, write_fd = os.pipe()
        devnull = os.open(os.devnull, os.O_RDWR)
        child_pid: int | None = None
        child_status: int | None = None
        try:
            child_pid = os.posix_spawn(
                os.fspath(executable),
                (os.fspath(executable), "-C", os.fspath(root), *arguments),
                environment,
                file_actions=(
                    (os.POSIX_SPAWN_DUP2, devnull, 0),
                    (os.POSIX_SPAWN_DUP2, write_fd, 1),
                    (os.POSIX_SPAWN_DUP2, devnull, 2),
                    (os.POSIX_SPAWN_CLOSE, read_fd),
                    (os.POSIX_SPAWN_CLOSE, write_fd),
                ),
            )
            os.close(write_fd)
            write_fd = -1
            output = bytearray()
            deadline = time.monotonic() + 5
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                readable, _, _ = select.select((read_fd,), (), (), remaining)
                if not readable:
                    raise TimeoutError
                chunk = os.read(read_fd, min(65_536, output_limit + 1 - len(output)))
                if not chunk:
                    _, child_status = os.waitpid(child_pid, 0)
                    child_pid = None
                    break
                output.extend(chunk)
                if len(output) > output_limit:
                    raise ValueError
        except (OSError, TimeoutError, ValueError):
            raise ValueError from None
        finally:
            if read_fd >= 0:
                os.close(read_fd)
            if write_fd >= 0:
                os.close(write_fd)
            os.close(devnull)
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(child_pid, 0)
                except ChildProcessError:
                    pass
        if child_status is None or not os.WIFEXITED(child_status) or os.WEXITSTATUS(child_status) != 0:
            raise ValueError
        return bytes(output)

    size_text = read_git("cat-file", "-s", object_name, output_limit=_MAX_DIGEST_BYTES)
    try:
        size = int(size_text.decode("ascii").strip())
    except (UnicodeDecodeError, ValueError):
        raise ValueError from None
    if size < 0 or size > max_bytes:
        raise ValueError
    blob = read_git("cat-file", "blob", object_name, output_limit=max_bytes)
    if len(blob) != size:
        raise ValueError
    return blob


def _read_exact_checked_out_source_file(
    root: Path,
    *,
    source_commit_sha: str,
    relative_path: Path,
    max_bytes: int,
) -> bytes:
    """Require a fixed working-tree authority file to equal its exact commit blob."""

    working_tree = _read_exact_repository_file(
        root,
        root / relative_path,
        relative_path,
        max_bytes,
    )
    committed = _read_checked_out_commit_blob(
        root,
        source_commit_sha=source_commit_sha,
        relative_path=relative_path,
        max_bytes=max_bytes,
    )
    if working_tree != committed:
        raise ValueError
    return committed


@dataclass(frozen=True)
class NominationRuntimeConfig:
    """Search-only authority with no semantic or publication configuration."""

    state_repository_id: int
    state_repository_full_name: str
    query_set_path: Path
    query_set: object
    query_set_digest: str
    operations_state: Path
    initial_state_root_digest: str
    state_lineage_anchor_commit_sha: str = _PHASE6_STATE_LINEAGE_ANCHOR_COMMIT_SHA
    state_lineage_anchor_root_digest: str = _PHASE6_STATE_LINEAGE_ANCHOR_ROOT_DIGEST
    state_lineage_anchor_max_hops: int = _DISCOVERY_STATE_LINEAGE_MAX_HOPS

    def __post_init__(self) -> None:
        from skillscout.domain.discovery import DiscoveryQuerySetV1

        if (
            type(self.state_repository_id) is not int
            or self.state_repository_id <= 0
            or not _github_full_name(self.state_repository_full_name)
            or not isinstance(self.query_set_path, Path)
            or self.query_set_path.name != _DISCOVERY_QUERY_SET_NAME
            or type(self.query_set) is not DiscoveryQuerySetV1
            or self.query_set_digest != self.query_set.query_set_digest
            or os.fspath(self.operations_state) != _DISCOVERY_DATABASE_LOCATORS[1]
            or not _is_digest(self.initial_state_root_digest)
            or not _is_commit_sha(self.state_lineage_anchor_commit_sha)
            or not _is_digest(self.state_lineage_anchor_root_digest)
            or type(self.state_lineage_anchor_max_hops) is not int
            or not 1 <= self.state_lineage_anchor_max_hops <= _DISCOVERY_STATE_LINEAGE_MAX_HOPS
        ):
            raise ValueError("nomination runtime configuration rejected")


@dataclass(frozen=True)
class FreshCampaignPreparationRuntimeConfig:
    """Closed configuration for deriving a fresh nomination from current state."""

    state_repository_id: int
    state_repository_full_name: str
    query_set_path: Path
    query_set: object
    query_set_digest: str
    operations_state: Path
    state_lineage_anchor_commit_sha: str
    state_lineage_anchor_root_digest: str
    state_lineage_anchor_max_hops: int = _DISCOVERY_STATE_LINEAGE_MAX_HOPS

    def __post_init__(self) -> None:
        from skillscout.domain.discovery import DiscoveryQuerySetV1

        if (
            type(self.state_repository_id) is not int
            or self.state_repository_id <= 0
            or not _github_full_name(self.state_repository_full_name)
            or not isinstance(self.query_set_path, Path)
            or self.query_set_path.name != _DISCOVERY_QUERY_SET_NAME
            or type(self.query_set) is not DiscoveryQuerySetV1
            or self.query_set_digest != self.query_set.query_set_digest
            or os.fspath(self.operations_state) != _DISCOVERY_DATABASE_LOCATORS[1]
            or not _is_commit_sha(self.state_lineage_anchor_commit_sha)
            or not _is_digest(self.state_lineage_anchor_root_digest)
            or type(self.state_lineage_anchor_max_hops) is not int
            or not 1 <= self.state_lineage_anchor_max_hops <= _DISCOVERY_STATE_LINEAGE_MAX_HOPS
        ):
            raise ValueError("fresh campaign preparation configuration rejected")


@dataclass(frozen=True)
class FreshCampaignLockRuntimeConfig:
    """Fixed source and workflow identity for one protected, state-only V2 lock."""

    preparation: FreshCampaignPreparationRuntimeConfig
    repository_root: Path
    selection_manifest: object
    source_repository_id: int
    source_repository_full_name: str
    source_commit_sha: str
    acceptance_workflow_sha256: str
    workflow_run_id: int
    workflow_run_attempt: int
    trigger_identity: str

    def __post_init__(self) -> None:
        from skillscout.domain.acceptance import LockedBenchmarkManifestV1

        if (
            type(self.preparation) is not FreshCampaignPreparationRuntimeConfig
            or not isinstance(self.repository_root, Path)
            or type(self.selection_manifest) is not LockedBenchmarkManifestV1
            or type(self.source_repository_id) is not int
            or self.source_repository_id <= 0
            or not _github_full_name(self.source_repository_full_name)
            or not _is_commit_sha(self.source_commit_sha)
            or not _is_digest(self.acceptance_workflow_sha256)
            or type(self.workflow_run_id) is not int
            or self.workflow_run_id <= 0
            or type(self.workflow_run_attempt) is not int
            or self.workflow_run_attempt <= 0
            or self.workflow_run_attempt != 1
            or not _fresh_campaign_trigger_identity(self.trigger_identity)
        ):
            raise ValueError("fresh campaign lock configuration rejected")


@dataclass(frozen=True)
class LiveAuthorityRecordingRuntimeConfig:
    """Closed, non-secret inputs for one V2 live-authority transition."""

    acceptance_run_id: str
    preparation: FreshCampaignPreparationRuntimeConfig
    repository_root: Path
    selection_manifest: object
    source_repository_id: int
    source_repository_full_name: str
    source_commit_sha: str
    acceptance_workflow_sha256: str
    workflow_run_id: int
    workflow_run_attempt: int

    def __post_init__(self) -> None:
        from skillscout.domain.acceptance import LockedBenchmarkManifestV1

        if (
            not _closed_identity(self.acceptance_run_id)
            or type(self.preparation) is not FreshCampaignPreparationRuntimeConfig
            or not isinstance(self.repository_root, Path)
            or type(self.selection_manifest) is not LockedBenchmarkManifestV1
            or type(self.source_repository_id) is not int
            or self.source_repository_id <= 0
            or not _github_full_name(self.source_repository_full_name)
            or not _is_commit_sha(self.source_commit_sha)
            or not _is_digest(self.acceptance_workflow_sha256)
            or type(self.workflow_run_id) is not int
            or self.workflow_run_id <= 0
            or type(self.workflow_run_attempt) is not int
            or self.workflow_run_attempt != 1
        ):
            raise ValueError("live authority recording configuration rejected")


def _is_commit_sha(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def require_hosted_state_repository(
    *,
    state_repository_id: str,
    state_repository_full_name: str,
) -> None:
    """Close normal discovery to the sole code-reviewed state authority."""

    if (
        state_repository_id != str(_HOSTED_STATE_REPOSITORY_ID)
        or state_repository_full_name != _HOSTED_STATE_REPOSITORY_FULL_NAME
    ):
        raise ValueError("hosted state repository rejected")


def _fresh_campaign_trigger_identity(value: object) -> bool:
    """Accept the one initial actor identity emitted by a first workflow-dispatch attempt."""

    return (
        type(value) is str
        and re.fullmatch(
            r"workflow_dispatch:[1-9][0-9]*:[A-Za-z0-9-]{1,39}",
            value,
        )
        is not None
    )


def _fresh_campaign_trigger_actor(value: str) -> tuple[int, str]:
    """Unpack the reviewed initial actor identity without accepting a rerun identity."""

    match = re.fullmatch(
        r"workflow_dispatch:([1-9][0-9]*):([A-Za-z0-9-]{1,39})",
        value,
    )
    if match is None:
        raise ValueError("fresh campaign source identity rejected")
    return int(match.group(1)), match.group(2)


def _is_fresh_campaign_workflow_path(value: object) -> bool:
    """Require Actions metadata to name this exact workflow file, optionally at a bounded ref."""

    return (
        type(value) is str
        and re.fullmatch(
            r"\.github/workflows/phase6-acceptance\.yml(?:@[A-Za-z0-9._/-]{1,200})?",
            value,
        )
        is not None
    )


def load_nomination_runtime_config(
    *,
    state_repository_id: str,
    state_repository_full_name: str,
    query_set_path: Path,
    operations_state: Path,
    initial_state_root_digest: str,
) -> NominationRuntimeConfig:
    """Validate the complete Search-only nomination authority."""

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
        if query_set.query_set_digest is None:
            raise ValueError
        return NominationRuntimeConfig(
            state_repository_id=int(state_repository_id),
            state_repository_full_name=state_repository_full_name,
            query_set_path=query_set_path,
            query_set=query_set,
            query_set_digest=query_set.query_set_digest,
            operations_state=operations_state,
            initial_state_root_digest=initial_state_root_digest,
        )
    except Exception:
        raise ValueError("nomination runtime configuration rejected") from None


def load_fresh_campaign_preparation_runtime_config(
    *,
    state_repository_id: int,
    state_repository_full_name: str,
    query_set_path: Path,
    operations_state: Path,
) -> FreshCampaignPreparationRuntimeConfig:
    """Validate the closed, non-secret inputs for a current-state Search nomination."""

    try:
        if (
            type(state_repository_id) is not int
            or state_repository_id <= 0
            or not _github_full_name(state_repository_full_name)
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
        if query_set.query_set_digest is None:
            raise ValueError
        return FreshCampaignPreparationRuntimeConfig(
            state_repository_id=state_repository_id,
            state_repository_full_name=state_repository_full_name,
            query_set_path=query_set_path,
            query_set=query_set,
            query_set_digest=query_set.query_set_digest,
            operations_state=operations_state,
            state_lineage_anchor_commit_sha=(
                _PHASE6_STATE_LINEAGE_ANCHOR_COMMIT_SHA
            ),
            state_lineage_anchor_root_digest=(
                _PHASE6_STATE_LINEAGE_ANCHOR_ROOT_DIGEST
            ),
        )
    except Exception:
        raise ValueError("fresh campaign preparation configuration rejected") from None


def load_fresh_campaign_lock_runtime_config(
    *,
    preparation: FreshCampaignPreparationRuntimeConfig,
    repository_root: Path,
    source_repository_id: int,
    source_repository_full_name: str,
    source_commit_sha: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
    trigger_identity: str,
) -> FreshCampaignLockRuntimeConfig:
    """Read only the fixed checked-out selection and workflow before any credential lookup."""

    try:
        if type(preparation) is not FreshCampaignPreparationRuntimeConfig:
            raise ValueError
        root = _trusted_repository_root(repository_root)
        if _checked_out_repository_commit(root) != source_commit_sha:
            raise ValueError
        manifest_relative = Path(
            "config/acceptance/phase6/benchmark-manifest.json"
        )
        workflow_relative = Path(".github/workflows/phase6-acceptance.yml")
        manifest_bytes = _read_exact_checked_out_source_file(
            root,
            source_commit_sha=source_commit_sha,
            relative_path=manifest_relative,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        workflow_bytes = _read_exact_checked_out_source_file(
            root,
            source_commit_sha=source_commit_sha,
            relative_path=workflow_relative,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        from skillscout.domain.acceptance import LockedBenchmarkManifestV1
        from skillscout.domain.canonical import canonical_json_bytes

        manifest = LockedBenchmarkManifestV1.model_validate_json(manifest_bytes, strict=True)
        canonical = canonical_json_bytes(manifest)
        if manifest_bytes not in {canonical, canonical + b"\n"}:
            raise ValueError
        return FreshCampaignLockRuntimeConfig(
            preparation=preparation,
            repository_root=root,
            selection_manifest=manifest,
            source_repository_id=source_repository_id,
            source_repository_full_name=source_repository_full_name,
            source_commit_sha=source_commit_sha,
            acceptance_workflow_sha256="sha256:" + hashlib.sha256(workflow_bytes).hexdigest(),
            workflow_run_id=workflow_run_id,
            workflow_run_attempt=workflow_run_attempt,
            trigger_identity=trigger_identity,
        )
    except Exception:
        raise ValueError("fresh campaign lock configuration rejected") from None


def _fresh_campaign_lock_handoff_matches_config(
    *,
    config: FreshCampaignLockRuntimeConfig,
    handoff: object,
) -> bool:
    """Require a received approval handoff to bind this exact source configuration."""

    from skillscout.domain.acceptance import FreshBenchmarkLockHandoffV1

    return (
        type(handoff) is FreshBenchmarkLockHandoffV1
        and handoff.source_repository_id == config.source_repository_id
        and handoff.source_repository_full_name == config.source_repository_full_name
        and handoff.state_repository_id == config.preparation.state_repository_id
        and handoff.state_repository_full_name
        == config.preparation.state_repository_full_name
        and handoff.source_commit_sha == config.source_commit_sha
        and handoff.acceptance_workflow_sha256 == config.acceptance_workflow_sha256
        and handoff.workflow_run_id == config.workflow_run_id
        and handoff.workflow_run_attempt == config.workflow_run_attempt
        and handoff.trigger_identity == config.trigger_identity
        and handoff.selection_manifest == config.selection_manifest
    )


def load_fresh_campaign_lock_handoff(
    *,
    config: FreshCampaignLockRuntimeConfig,
    handoff_bytes: bytes,
) -> object:
    """Parse one exact canonical approval handoff before any state credential lookup."""

    try:
        if (
            type(config) is not FreshCampaignLockRuntimeConfig
            or type(handoff_bytes) is not bytes
            or not handoff_bytes
            or len(handoff_bytes) > _ACCEPTANCE_MANIFEST_BYTES
        ):
            raise ValueError
        from skillscout.domain.acceptance import FreshBenchmarkLockHandoffV1
        from skillscout.domain.canonical import canonical_json_bytes

        handoff = FreshBenchmarkLockHandoffV1.model_validate_json(
            handoff_bytes,
            strict=True,
        )
        if (
            handoff_bytes != canonical_json_bytes(handoff)
            or not _fresh_campaign_lock_handoff_matches_config(
                config=config,
                handoff=handoff,
            )
        ):
            raise ValueError
        return handoff
    except Exception:
        raise ValueError("fresh campaign lock handoff rejected") from None


def _required_positive_decimal_environment(
    source: Mapping[str, str],
    name: str,
) -> int:
    """Read one bounded non-secret Actions identity without exposing its value."""

    try:
        value = source[name]
        if (
            type(value) is not str
            or not value.isascii()
            or not value.isdecimal()
            or value.startswith("0")
        ):
            raise ValueError
        result = int(value)
        if result <= 0:
            raise ValueError
        return result
    except Exception:
        raise ValueError("live authority Actions identity rejected") from None


def load_live_authority_recording_runtime_config(
    *,
    acceptance_run_id: str,
    environ: Mapping[str, str] | None = None,
) -> LiveAuthorityRecordingRuntimeConfig:
    """Read only exact checked-out source and bounded Actions identities.

    This loader intentionally has no authority document, receipt, actor, or
    endpoint input.  The actor/trigger identity is derived later from the
    fixed-host Actions attempt response, after the current V2 lock is rebuilt.
    """

    try:
        source = os.environ if environ is None else environ
        if not _closed_identity(acceptance_run_id):
            raise ValueError
        source_repository_id = _required_positive_decimal_environment(
            source,
            "GITHUB_REPOSITORY_ID",
        )
        state_repository_id = _required_positive_decimal_environment(
            source,
            "SKILLSCOUT_STATE_REPOSITORY_ID",
        )
        source_repository_full_name = source["GITHUB_REPOSITORY"]
        state_repository_full_name = source["SKILLSCOUT_STATE_REPOSITORY_FULL_NAME"]
        source_commit_sha = source["GITHUB_SHA"]
        workflow_run_id = _required_positive_decimal_environment(source, "GITHUB_RUN_ID")
        workflow_run_attempt = _required_positive_decimal_environment(
            source,
            "GITHUB_RUN_ATTEMPT",
        )
        if (
            not _github_full_name(source_repository_full_name)
            or not _github_full_name(state_repository_full_name)
            or not _is_commit_sha(source_commit_sha)
            or workflow_run_attempt != 1
        ):
            raise ValueError
        root = _trusted_repository_root(Path.cwd().resolve(strict=True))
        if _checked_out_repository_commit(root) != source_commit_sha:
            raise ValueError
        manifest_relative = Path(
            "config/acceptance/phase6/benchmark-manifest.json"
        )
        workflow_relative = Path(".github/workflows/phase6-acceptance.yml")
        query_relative = Path("config") / _DISCOVERY_QUERY_SET_NAME
        manifest_bytes = _read_exact_checked_out_source_file(
            root,
            source_commit_sha=source_commit_sha,
            relative_path=manifest_relative,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        workflow_bytes = _read_exact_checked_out_source_file(
            root,
            source_commit_sha=source_commit_sha,
            relative_path=workflow_relative,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        query_bytes = _read_exact_checked_out_source_file(
            root,
            source_commit_sha=source_commit_sha,
            relative_path=query_relative,
            max_bytes=_DISCOVERY_DIGEST_BYTES,
        )
        from skillscout.domain.acceptance import LockedBenchmarkManifestV1
        from skillscout.domain.canonical import canonical_json_bytes
        from skillscout.domain.discovery import DiscoveryQuerySetV1

        selection_manifest = LockedBenchmarkManifestV1.model_validate_json(
            manifest_bytes,
            strict=True,
        )
        query_set = DiscoveryQuerySetV1.model_validate_json(query_bytes, strict=True)
        if (
            manifest_bytes not in {
                canonical_json_bytes(selection_manifest),
                canonical_json_bytes(selection_manifest) + b"\n",
            }
            or query_set.query_set_digest is None
        ):
            raise ValueError
        preparation = FreshCampaignPreparationRuntimeConfig(
            state_repository_id=state_repository_id,
            state_repository_full_name=state_repository_full_name,
            query_set_path=query_relative,
            query_set=query_set,
            query_set_digest=query_set.query_set_digest,
            operations_state=Path(_DISCOVERY_DATABASE_LOCATORS[1]),
            state_lineage_anchor_commit_sha=_PHASE6_STATE_LINEAGE_ANCHOR_COMMIT_SHA,
            state_lineage_anchor_root_digest=_PHASE6_STATE_LINEAGE_ANCHOR_ROOT_DIGEST,
        )
        return LiveAuthorityRecordingRuntimeConfig(
            acceptance_run_id=acceptance_run_id,
            preparation=preparation,
            repository_root=root,
            selection_manifest=selection_manifest,
            source_repository_id=source_repository_id,
            source_repository_full_name=source_repository_full_name,
            source_commit_sha=source_commit_sha,
            acceptance_workflow_sha256=(
                "sha256:" + hashlib.sha256(workflow_bytes).hexdigest()
            ),
            workflow_run_id=workflow_run_id,
            workflow_run_attempt=workflow_run_attempt,
        )
    except Exception:
        raise ValueError("live authority recording configuration rejected") from None


def load_acceptance_runtime_config(
    *,
    manifest_path: Path,
    state_commit_sha: str,
    state_root_digest: str,
    acceptance_run_id: str | None = None,
    resume_proof_path: Path | None = None,
    live_admission: object | None = None,
    environ: Mapping[str, str] | None = None,
) -> AcceptanceRuntimeConfig:
    """Build runtime configuration after the V2 admission boundary."""

    try:
        if (
            not isinstance(manifest_path, Path)
            or manifest_path.name != _ACCEPTANCE_MANIFEST_NAME
            or not _is_commit_sha(state_commit_sha)
            or not _is_digest(state_root_digest)
            or (acceptance_run_id is None) != (resume_proof_path is None)
        ):
            raise ValueError
        payload = _read_stable_private_file(
            manifest_path,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        from skillscout.domain.acceptance import LockedBenchmarkManifestV1
        from skillscout.domain.canonical import canonical_json_bytes

        manifest = LockedBenchmarkManifestV1.model_validate_json(
            payload,
            strict=True,
        )
        canonical = canonical_json_bytes(manifest)
        if payload not in {canonical, canonical + b"\n"}:
            raise ValueError

        source = os.environ if environ is None else environ
        from skillscout.application.acceptance import LiveExecutionAdmissionV2

        if (
            type(live_admission) is not LiveExecutionAdmissionV2
            or live_admission.authority.authority_digest is None
            or source["PHASE6_AUTHORITY_DIGEST"]
            != live_admission.authority.authority_digest
            or manifest != live_admission.lock.selection_manifest
        ):
            raise ValueError
        semantic_provider = live_admission.authority.semantic_provider
        extractor_model_id, generator_model_id, reviewer_model_id = (
            live_admission.authority.stage_models
        )
        live_authority_digest = live_admission.authority.authority_digest
        resume_locator_digest: str | None = None
        resume_transition_index = 0
        resume_commits: tuple[str, ...] = ()
        resume_roots: tuple[str, ...] = ()
        state_lineage_anchor_commit_sha: str | None = None
        state_lineage_anchor_root_digest: str | None = None
        if resume_proof_path is not None:
            proof_bytes = _read_stable_private_file(
                resume_proof_path,
                max_bytes=65_536,
            )
            proof = json.loads(proof_bytes)
            if not isinstance(proof, dict) or set(proof) != {
                "acceptance_run_id",
                "authority_digest",
                "lineage_commit_shas",
                "lineage_root_digests",
                "locator_digest",
                "transition_index",
                "state_commit_sha",
                "state_root_digest",
                "status",
            }:
                raise ValueError
            if (
                proof["status"] != "acceptance_resume_verified"
                or proof["acceptance_run_id"] != acceptance_run_id
                or proof["authority_digest"] != source["PHASE6_AUTHORITY_DIGEST"]
                or proof["state_commit_sha"] != state_commit_sha
                or proof["state_root_digest"] != state_root_digest
                or type(proof["lineage_commit_shas"]) is not list
                or type(proof["lineage_root_digests"]) is not list
                or type(proof["transition_index"]) is not int
                or (
                    proof["locator_digest"] is not None and type(proof["locator_digest"]) is not str
                )
            ):
                raise ValueError
            resume_locator_digest = proof["locator_digest"]
            resume_transition_index = proof["transition_index"]
            resume_commits = tuple(proof["lineage_commit_shas"])
            resume_roots = tuple(proof["lineage_root_digests"])
            try:
                state_lineage_anchor_commit_sha = source[
                    "PHASE6_AUTHORITY_STATE_COMMIT_SHA"
                ]
                state_lineage_anchor_root_digest = source[
                    "PHASE6_AUTHORITY_STATE_ROOT_DIGEST"
                ]
            except Exception:
                raise ValueError from None
            if (
                not resume_commits
                or len(resume_commits) != len(resume_roots)
                or any(not _is_commit_sha(item) for item in resume_commits)
                or any(not _is_digest(item) for item in resume_roots)
                or len(resume_commits) < 2
                or (
                    state_lineage_anchor_commit_sha,
                    state_lineage_anchor_root_digest,
                )
                != (resume_commits[1], resume_roots[1])
            ):
                raise ValueError
        return AcceptanceRuntimeConfig(
            manifest_path=manifest_path,
            manifest=manifest,
            state_commit_sha=state_commit_sha,
            state_root_digest=state_root_digest,
            semantic_provider=semantic_provider,
            extractor_model_id=extractor_model_id,
            generator_model_id=generator_model_id,
            reviewer_model_id=reviewer_model_id,
            live_acceptance_authority_digest=live_authority_digest,
            acceptance_run_id=(acceptance_run_id if resume_proof_path is not None else None),
            resume_locator_digest=resume_locator_digest,
            resume_transition_index=resume_transition_index,
            resume_lineage_commit_shas=resume_commits,
            resume_lineage_root_digests=resume_roots,
            state_lineage_anchor_commit_sha=state_lineage_anchor_commit_sha,
            state_lineage_anchor_root_digest=state_lineage_anchor_root_digest,
        )
    except Exception:
        raise ValueError("acceptance runtime configuration rejected") from None


def load_acceptance_attestation(
    *,
    attestation_path: Path,
    kind: str,
) -> object:
    """Read one canonical, typed human-owned acceptance attestation."""

    try:
        if (
            not isinstance(attestation_path, Path)
            or not attestation_path.name
            or kind not in {"human-review", "probe-cleanup"}
        ):
            raise ValueError
        payload = _read_stable_private_file(
            attestation_path,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        from skillscout.domain.acceptance import (
            HumanSkillReviewAttestationV1,
            ProbeCleanupAttestationV1,
        )
        from skillscout.domain.canonical import canonical_json_bytes

        model = (
            HumanSkillReviewAttestationV1 if kind == "human-review" else ProbeCleanupAttestationV1
        )
        attestation = model.model_validate_json(payload, strict=True)
        canonical = canonical_json_bytes(attestation)
        if payload not in {canonical, canonical + b"\n"}:
            raise ValueError
        return attestation
    except Exception:
        raise ValueError("acceptance attestation rejected") from None


def load_live_acceptance_authority(
    *,
    authority_path: Path,
    observed_source_commit_sha: str,
    observed_state_commit_sha: str,
    observed_state_root_digest: str,
    observed_state_repository_id: int,
    observed_state_repository_full_name: str,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Load one canonical human authority before opening any state credential."""

    try:
        payload = _read_stable_private_file(
            authority_path,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        return verify_live_acceptance_authority(
            repository_root=Path.cwd().resolve(strict=True),
            authority_bytes=payload,
            observed_source_commit_sha=observed_source_commit_sha,
            observed_state_commit_sha=observed_state_commit_sha,
            observed_state_root_digest=observed_state_root_digest,
            observed_state_repository_id=observed_state_repository_id,
            observed_state_repository_full_name=observed_state_repository_full_name,
            environ=environ,
        )
    except Exception:
        raise ValueError("live acceptance authority rejected") from None


def record_live_acceptance_authority(
    *,
    authority_path: Path,
    acceptance_run_id: str,
    source_commit_sha: str,
    state_commit_sha: str,
    state_root_digest: str,
    state_repository_id: int,
    state_repository_full_name: str,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Record and CAS-persist one verified authority without semantic access.

    All document, workflow, provider, state and budget identities are checked
    from the authority file first.  Only then does the function resolve the
    bounded state credential to restore and persist the operations fact.
    """

    source = os.environ if environ is None else environ
    authority = verify_live_acceptance_authority_state(
        authority_path=authority_path,
        source_commit_sha=source_commit_sha,
        state_commit_sha=state_commit_sha,
        state_root_digest=state_root_digest,
        state_repository_id=state_repository_id,
        state_repository_full_name=state_repository_full_name,
        environ=source,
    )
    from skillscout.adapters.operations_state import OperationsStateStore
    from skillscout.application.acceptance import (
        LiveAuthorityDependencies,
        record_live_authority,
    )
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

    if type(authority) is not LiveAcceptanceAuthorityV1:
        raise ValueError("live acceptance authority rejected")
    config = load_discovery_runtime_config(
        state_repository_id=str(state_repository_id),
        state_repository_full_name=state_repository_full_name,
        state_ref=_DISCOVERY_STATE_REF,
        query_set_path=Path("config") / _DISCOVERY_QUERY_SET_NAME,
        pipeline_state=Path(_DISCOVERY_DATABASE_LOCATORS[0]),
        operations_state=Path(_DISCOVERY_DATABASE_LOCATORS[1]),
        publication_state=Path(_DISCOVERY_DATABASE_LOCATORS[2]),
        semantic_provider=authority.semantic_provider,
        extractor_model_id=authority.stage_models[0],
        generator_model_id=authority.stage_models[1],
        reviewer_model_id=authority.stage_models[2],
        initial_state_root_digest=state_root_digest,
        query_set_digest=authority.query_set_digest,
        environ=source,
    )
    with OperationsStateStore(Path(_DISCOVERY_DATABASE_LOCATORS[1])) as operations:
        existing = tuple(
            item
            for item in operations.acceptance_snapshot(acceptance_run_id).facts
            if item.kind == "acceptance_live_authority"
        )
        # A parent-state fact cannot prove its own durable successor receipt.
        # Treat any such fact as a conflict instead of retrying, migrating, or
        # returning a stale parent identity as a successful record.
        if existing:
            raise ValueError("live acceptance authority already exists in parent state")
        # The public campaign state predates the authority fact kind.  Upgrade
        # only on this state-only path, after exact restoration and immediately
        # before its first authority-fact mutation.
        operations.upgrade_acceptance_schema()
    record = record_live_authority(
        LiveAuthorityDependencies(
            operations_store_factory=lambda: OperationsStateStore(
                Path(_DISCOVERY_DATABASE_LOCATORS[1])
            )
        ),
        acceptance_run_id=acceptance_run_id,
        fact=authority,
    )
    with OperationsStateStore(Path(_DISCOVERY_DATABASE_LOCATORS[1])) as operations:
        barrier = _LateStateDurabilityBarrier(config, source)
        barrier.configure_acceptance_resume(
            authority=authority,
            acceptance_run_id=acceptance_run_id,
            lineage_commit_shas=(state_commit_sha,),
            lineage_root_digests=(state_root_digest,),
        )
        synchronized = barrier.sync_discovery(
            operations_store=operations,
            observed_head=state_commit_sha,
            prior_root_digest=state_root_digest,
            created_at=_discovery_timestamp(),
            transition_phase="authority_carrier",
        )
    if (
        getattr(synchronized, "status", None) != "verified"
        or not _is_commit_sha(getattr(synchronized, "commit_sha", None))
        or not _is_digest(getattr(synchronized, "root_digest", None))
    ):
        raise ValueError("live acceptance authority persistence rejected")
    return {
        "acceptance_run_id": acceptance_run_id,
        "authority_digest": record.fact_digest,
        "authority_state_commit_sha": synchronized.commit_sha,
        "authority_state_root_digest": synchronized.root_digest,
        "source_commit_sha": authority.source_commit_sha,
        "state_commit_sha": authority.state_commit_sha,
        "state_root_digest": authority.state_root_digest,
        "state_repository_id": authority.state_repository_id,
        "state_repository_full_name": authority.state_repository_full_name,
        "status": "live_authority_persisted",
    }


def _restore_current_live_authority_recording_state(
    *,
    config: LiveAuthorityRecordingRuntimeConfig,
    source: Mapping[str, str],
) -> object:
    """Restore the current state branch without constructing a publication owner."""

    if type(config) is not LiveAuthorityRecordingRuntimeConfig:
        raise ValueError("live authority recording configuration rejected")
    from skillscout.adapters.operations_state import restore_acceptance_state_bundle
    from skillscout.adapters.state_branch import (
        StateBranchClient,
        StateBranchStore,
        StateLineageAnchor,
    )

    preparation = config.preparation
    client = StateBranchClient(
        token=_required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
        repository_id=preparation.state_repository_id,
        repository_full_name=preparation.state_repository_full_name,
    )
    try:
        observation = StateBranchStore(client).restore(
            lineage_anchor=StateLineageAnchor(
                commit_sha=preparation.state_lineage_anchor_commit_sha,
                root_digest=preparation.state_lineage_anchor_root_digest,
                max_hops=preparation.state_lineage_anchor_max_hops,
            )
        )
        bundle = getattr(observation, "bundle", None)
        root = getattr(bundle, "root", None)
        if (
            bundle is None
            or root is None
            or not _is_commit_sha(getattr(observation, "observed_head", None))
            or not _is_digest(getattr(root, "root_digest", None))
        ):
            raise ValueError
        restore_acceptance_state_bundle(
            bundle,
            pipeline_path=Path(_DISCOVERY_DATABASE_LOCATORS[0]),
            operations_path=preparation.operations_state,
        )
        return observation
    finally:
        client.close()


def _build_live_execution_approval_receipt(
    *,
    config: LiveAuthorityRecordingRuntimeConfig,
    lock: object,
    source: Mapping[str, str],
) -> object:
    """Read one fixed-host, redacted Environment-B receipt after lock rebuild."""

    from skillscout.adapters.github import GitHubReadClient
    from skillscout.domain.acceptance import (
        LiveExecutionApprovalReceiptV2,
        LockedBenchmarkManifestV2,
    )

    if type(config) is not LiveAuthorityRecordingRuntimeConfig or type(lock) is not LockedBenchmarkManifestV2:
        raise ValueError("live authority approval receipt rejected")
    owner, repository = config.source_repository_full_name.split("/", 1)
    client = GitHubReadClient(token=_required_credential(source, "GITHUB_TOKEN"))
    try:
        attempt = client.get_workflow_run_attempt(
            owner,
            repository,
            config.workflow_run_id,
            config.workflow_run_attempt,
        )
        approvals = client.get_workflow_run_approvals(
            owner,
            repository,
            config.workflow_run_id,
        )
    finally:
        client.close()
    trigger_identity = (
        f"{attempt.event}:{attempt.actor_id}:{attempt.actor_login}"
        if getattr(attempt, "event", None) == "workflow_dispatch"
        else ""
    )
    if (
        config.workflow_run_attempt != 1
        or attempt.source_commit_sha != config.source_commit_sha
        or attempt.source_commit_sha != lock.source_commit_sha
        or attempt.event != "workflow_dispatch"
        or not _is_fresh_campaign_workflow_path(attempt.workflow_path)
        or attempt.actor_id != attempt.triggering_actor_id
        or attempt.actor_login != attempt.triggering_actor_login
        or not _fresh_campaign_trigger_identity(trigger_identity)
    ):
        raise ValueError("live authority Actions attempt rejected")
    matching = tuple(
        approval
        for approval in approvals
        if (
            approval.environment == "skillscout-phase6-live-authority"
            and approval.reviewer_login == "alexzhu0"
            and approval.workflow_run_id == config.workflow_run_id
        )
    )
    if len(matching) != 1:
        raise ValueError("live authority approval is missing or ambiguous")
    approval = matching[0]
    return LiveExecutionApprovalReceiptV2(
        schema_version="live-execution-approval-receipt-v2",
        purpose="live_execution",
        environment="skillscout-phase6-live-authority",
        source_repository_id=config.source_repository_id,
        source_repository_full_name=config.source_repository_full_name,
        reviewer_login="alexzhu0",
        reviewer_id=approval.reviewer_id,
        workflow_run_id=config.workflow_run_id,
        workflow_run_attempt=config.workflow_run_attempt,
        source_commit_sha=config.source_commit_sha,
        workflow_sha256=config.acceptance_workflow_sha256,
        trigger_identity=trigger_identity,
        approval_record_digest=approval.approval_record_digest,
    )


def record_live_acceptance_authority_v2(
    *,
    acceptance_run_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Persist one V2 authority from rebuilt state and fixed-host approval facts.

    The public command input is solely the acceptance run identity.  No caller
    can supply authority JSON, approval prose, actor identity, endpoint, or a
    receipt.  State is restored once before the Actions-read token is resolved;
    all later state mutation is the one forward authority-carrier CAS.
    """

    try:
        source = os.environ if environ is None else environ
        config = load_live_authority_recording_runtime_config(
            acceptance_run_id=acceptance_run_id,
            environ=source,
        )
        restored = _restore_current_live_authority_recording_state(
            config=config,
            source=source,
        )
        root = getattr(getattr(restored, "bundle", None), "root", None)
        observed_head = getattr(restored, "observed_head", None)
        if root is None or not _is_commit_sha(observed_head):
            raise ValueError
        from skillscout.adapters.operations_state import OperationsStateStore
        from skillscout.application.acceptance import (
            LiveAuthorityDependencies,
            LiveAuthorityStateObservation,
            re_admit_fresh_benchmark_lock_v2,
            re_admit_live_execution_v2,
            record_live_authority,
        )
        from skillscout.domain.acceptance import LiveAcceptanceAuthorityV2
        from skillscout.domain.discovery import DiscoveryBudgetPolicyV1

        with OperationsStateStore(config.preparation.operations_state) as operations:
            snapshot = operations.acceptance_snapshot(acceptance_run_id)
            if any(record.kind == "acceptance_live_authority" for record in snapshot.facts):
                raise ValueError("live authority already exists")
            lock_admission = re_admit_fresh_benchmark_lock_v2(snapshot=snapshot)
        lock = lock_admission.lock
        budget = DiscoveryBudgetPolicyV1()
        if (
            lock.source_repository_id != config.source_repository_id
            or lock.source_repository_full_name != config.source_repository_full_name
            or lock.source_commit_sha != config.source_commit_sha
            or lock.acceptance_workflow_sha256 != config.acceptance_workflow_sha256
            or lock.state_repository_id != config.preparation.state_repository_id
            or lock.state_repository_full_name != config.preparation.state_repository_full_name
            or lock.selection_manifest != config.selection_manifest
            or getattr(root, "state_parent_commit_sha", None) != lock.parent_state_commit_sha
            or getattr(root, "prior_root_digest", None) != lock.parent_state_root_digest
            or getattr(root, "query_set_digest", None) != config.preparation.query_set_digest
            or getattr(root, "budget_policy_digest", None) != budget.budget_policy_digest
            or getattr(root, "root_digest", None) == lock.parent_state_root_digest
            or observed_head == lock.parent_state_commit_sha
        ):
            raise ValueError("live authority lock state binding rejected")
        receipt = _build_live_execution_approval_receipt(
            config=config,
            lock=lock,
            source=source,
        )
        from skillscout.adapters.openai_generate import (
            GENERATOR_POLICY_VERSION,
            GENERATOR_PROMPT_VERSION,
        )
        from skillscout.domain.extraction import (
            EXTRACT_POLICY_VERSION,
            EXTRACT_PROMPT_VERSION,
            WORKFLOW_SPEC_SCHEMA_VERSION,
        )
        from skillscout.domain.qualification import QUALIFICATION_POLICY_VERSION
        from skillscout.domain.reading import READER_POLICY_VERSION
        from skillscout.domain.review import (
            REVIEW_OUTPUT_SCHEMA_VERSION,
            REVIEW_POLICY_VERSION,
            REVIEW_PROMPT_VERSION,
        )
        from skillscout.domain.skill_artifacts import GENERATION_DRAFT_SCHEMA_VERSION

        authority = LiveAcceptanceAuthorityV2(
            schema_version="live-acceptance-authority-v2",
            authority_version=2,
            purpose="live_execution",
            benchmark_lock_digest=lock.lock_digest or "",
            benchmark_lock=lock,
            source_repository_id=lock.source_repository_id,
            source_repository_full_name=lock.source_repository_full_name,
            state_repository_id=lock.state_repository_id,
            state_repository_full_name=lock.state_repository_full_name,
            parent_state_commit_sha=lock.parent_state_commit_sha,
            parent_state_root_digest=lock.parent_state_root_digest,
            state_commit_sha=observed_head,
            state_root_digest=getattr(root, "root_digest", ""),
            source_commit_sha=lock.source_commit_sha,
            acceptance_workflow_sha256=lock.acceptance_workflow_sha256,
            source_state_binding_digest=lock.source_state_binding_digest,
            manifest_path=(
                "config/acceptance/phase6/benchmark-manifest.json"
            ),
            manifest_digest=lock.selection_manifest_digest,
            selection_manifest_digest=lock.selection_manifest_digest,
            nomination_set_digest=lock.nomination_set_digest,
            lock_attestation_digest=(
                lock.selection_manifest.lock_attestation.attestation_digest
            ),
            entries=lock.entries,
            environment="skillscout-phase6-live-authority",
            approved_reviewer_login="alexzhu0",
            approved_reviewer_id=receipt.reviewer_id,
            workflow_run_id=receipt.workflow_run_id,
            workflow_run_attempt=receipt.workflow_run_attempt,
            trigger_identity=receipt.trigger_identity,
            approval_record_digest=receipt.approval_record_digest,
            approval_receipt=receipt,
            approval_receipt_digest=receipt.receipt_digest or "",
            query_set_digest=config.preparation.query_set_digest,
            budget_policy_digest=budget.budget_policy_digest or "",
            semantic_provider="deepseek",
            provider_base_url="https://api.deepseek.com",
            stage_models=(
                "deepseek-v4-flash",
                "deepseek-v4-flash",
                "deepseek-v4-pro",
            ),
            prompt_versions=(
                EXTRACT_PROMPT_VERSION,
                GENERATOR_PROMPT_VERSION,
                REVIEW_PROMPT_VERSION,
            ),
            schema_versions=(
                WORKFLOW_SPEC_SCHEMA_VERSION,
                GENERATION_DRAFT_SCHEMA_VERSION,
                REVIEW_OUTPUT_SCHEMA_VERSION,
            ),
            policy_versions=tuple(
                sorted(
                    (
                        budget.budget_policy_version,
                        EXTRACT_POLICY_VERSION,
                        GENERATOR_POLICY_VERSION,
                        QUALIFICATION_POLICY_VERSION,
                        READER_POLICY_VERSION,
                        REVIEW_POLICY_VERSION,
                    )
                )
            ),
            max_candidates=100,
            max_semantic_candidates=20,
            max_semantic_requests=20,
            max_files_per_repository=25,
            max_source_files_per_repository=5,
            max_file_bytes=131_072,
            max_total_bytes_per_repository=524_288,
            max_tokens_per_repository=40_000,
            benchmark_scenario_write_count=5,
            replay_semantic_effect_count=0,
            replay_publication_effect_count=0,
            approved_at=_discovery_timestamp(),
        )
        record = record_live_authority(
            LiveAuthorityDependencies(
                operations_store_factory=lambda: OperationsStateStore(
                    config.preparation.operations_state
                )
            ),
            acceptance_run_id=acceptance_run_id,
            fact=authority,
        )
        with OperationsStateStore(config.preparation.operations_state) as operations:
            barrier = _LateStateDurabilityBarrier(config.preparation, source)
            barrier.configure_acceptance_resume(
                authority=authority,
                acceptance_run_id=acceptance_run_id,
                lineage_commit_shas=(authority.state_commit_sha,),
                lineage_root_digests=(authority.state_root_digest,),
            )
            synchronized = barrier.sync_discovery(
                operations_store=operations,
                observed_head=authority.state_commit_sha,
                prior_root_digest=authority.state_root_digest,
                created_at=_discovery_timestamp(),
                transition_phase="authority_carrier",
            )
        if (
            getattr(synchronized, "status", None) != "verified"
            or not _is_commit_sha(getattr(synchronized, "commit_sha", None))
            or not _is_digest(getattr(synchronized, "root_digest", None))
        ):
            raise ValueError("live authority persistence rejected")
        rebuilt = read_exact_acceptance_state(
            state_commit_sha=synchronized.commit_sha,
            state_repository_id=authority.state_repository_id,
            state_repository_full_name=authority.state_repository_full_name,
            pipeline_state=Path(_DISCOVERY_DATABASE_LOCATORS[0]),
            operations_state=Path(_DISCOVERY_DATABASE_LOCATORS[1]),
            state_lineage_anchor_commit_sha=authority.state_commit_sha,
            state_lineage_anchor_root_digest=authority.state_root_digest,
            environ=source,
        )
        rebuilt_root = getattr(getattr(rebuilt, "bundle", None), "root", None)
        if (
            getattr(rebuilt, "observed_head", None) != synchronized.commit_sha
            or rebuilt_root is None
            or rebuilt_root.root_digest != synchronized.root_digest
            or not _is_commit_sha(getattr(rebuilt_root, "state_parent_commit_sha", None))
            or not _is_digest(getattr(rebuilt_root, "prior_root_digest", None))
        ):
            raise ValueError("live authority rebuild rejected")
        with OperationsStateStore(Path(_DISCOVERY_DATABASE_LOCATORS[1])) as operations:
            rebuilt_snapshot = operations.acceptance_snapshot(acceptance_run_id)
        re_admit_live_execution_v2(
            snapshot=rebuilt_snapshot,
            authority_digest=record.fact_digest,
            state_observation=LiveAuthorityStateObservation(
                state_repository_id=authority.state_repository_id,
                state_repository_full_name=authority.state_repository_full_name,
                authority_carrier_commit_sha=synchronized.commit_sha,
                authority_carrier_root_digest=synchronized.root_digest,
                authority_carrier_parent_commit_sha=rebuilt_root.state_parent_commit_sha,
                authority_carrier_prior_root_digest=rebuilt_root.prior_root_digest,
                lock_state_parent_commit_sha=authority.parent_state_commit_sha,
                lock_state_prior_root_digest=authority.parent_state_root_digest,
            ),
        )
        return {
            "acceptance_run_id": acceptance_run_id,
            "authority_digest": record.fact_digest,
            "authority_state_commit_sha": synchronized.commit_sha,
            "authority_state_root_digest": synchronized.root_digest,
            "source_commit_sha": authority.source_commit_sha,
            "state_commit_sha": authority.state_commit_sha,
            "state_root_digest": authority.state_root_digest,
            "state_repository_id": authority.state_repository_id,
            "state_repository_full_name": authority.state_repository_full_name,
            "status": "live_authority_persisted",
        }
    except Exception:
        raise ValueError("live acceptance authority recording rejected") from None


def record_benchmark_lock_rebind_v2(
    *,
    source_acceptance_run_id: str,
    target_acceptance_run_id: str,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Rebind an admitted V2 source selection into one empty current run.

    This is deliberately a closed, state-only transition: immutable source
    configuration and the current state are checked before an approval read,
    then the reference and replacement lock are recorded before one late CAS.
    """

    try:
        source = os.environ if environ is None else environ
        config = load_live_authority_recording_runtime_config(
            acceptance_run_id=target_acceptance_run_id,
            environ=source,
        )
        restored = _restore_current_live_authority_recording_state(
            config=config,
            source=source,
        )
        root = getattr(getattr(restored, "bundle", None), "root", None)
        observed_head = getattr(restored, "observed_head", None)
        prior_root_digest = getattr(root, "root_digest", None)
        if (
            root is None
            or not _is_commit_sha(observed_head)
            or not _is_digest(prior_root_digest)
        ):
            raise ValueError
        from skillscout.adapters.operations_state import (
            AcceptanceFactRecord,
            AcceptanceRunSnapshot,
            OperationsStateStore,
        )
        from skillscout.application.acceptance import (
            re_admit_fresh_benchmark_lock_v2,
            rebind_benchmark_lock_v2,
        )

        with OperationsStateStore(config.preparation.operations_state) as operations:
            source_snapshot = operations.acceptance_snapshot(source_acceptance_run_id)
            target_snapshot = operations.acceptance_snapshot(target_acceptance_run_id)
            if (
                type(source_snapshot) is not AcceptanceRunSnapshot
                or type(target_snapshot) is not AcceptanceRunSnapshot
                or target_snapshot.acceptance_run_id != target_acceptance_run_id
                or target_snapshot.facts
            ):
                raise ValueError
            source_lock = re_admit_fresh_benchmark_lock_v2(
                snapshot=source_snapshot
            ).lock
            receipt = _build_live_execution_approval_receipt(
                config=config,
                lock=source_lock,
                source=source,
            )
            rebound = rebind_benchmark_lock_v2(
                source_snapshot=source_snapshot,
                target_acceptance_run_id=target_acceptance_run_id,
                selection_manifest=config.selection_manifest,
                state_repository_id=config.preparation.state_repository_id,
                state_repository_full_name=config.preparation.state_repository_full_name,
                parent_state_commit_sha=observed_head,
                parent_state_root_digest=prior_root_digest,
                approval_receipt=receipt,
            )
            reference_record = operations.record_acceptance_fact(
                target_acceptance_run_id,
                "acceptance_benchmark_rebind",
                rebound.reference,
            )
            lock_record = operations.record_acceptance_fact(
                target_acceptance_run_id,
                "acceptance_benchmark_lock",
                rebound.lock,
            )
            if (
                type(reference_record) is not AcceptanceFactRecord
                or type(lock_record) is not AcceptanceFactRecord
                or reference_record.fact_digest != rebound.reference.rebind_digest
                or lock_record.fact_digest != rebound.lock.lock_digest
            ):
                raise ValueError
            barrier = _LateStateDurabilityBarrier(config.preparation, source)
            synchronized = barrier.sync_benchmark_lock(
                operations_store=operations,
                observed_head=observed_head,
                prior_root_digest=prior_root_digest,
                created_at=_discovery_timestamp(),
            )
        if (
            getattr(synchronized, "status", None) != "verified"
            or getattr(synchronized, "previous_head", None) != observed_head
            or not _is_commit_sha(getattr(synchronized, "commit_sha", None))
            or not _is_digest(getattr(synchronized, "root_digest", None))
        ):
            raise ValueError
        return {
            "source_acceptance_run_id": source_acceptance_run_id,
            "acceptance_run_id": target_acceptance_run_id,
            "rebind_digest": rebound.reference.rebind_digest,
            "lock_digest": rebound.lock.lock_digest,
            "state_commit_sha": synchronized.commit_sha,
            "state_root_digest": synchronized.root_digest,
            "status": "benchmark_lock_rebound",
        }
    except Exception:
        raise ValueError("benchmark lock rebind rejected") from None


def _verify_live_execution_admission_source(admission: object) -> None:
    """Recheck only checked-out source bytes bound into a V2 authority."""

    from skillscout.application.acceptance import LiveExecutionAdmissionV2
    from skillscout.domain.acceptance import LockedBenchmarkManifestV1
    from skillscout.domain.canonical import canonical_json_bytes
    from skillscout.domain.discovery import DiscoveryQuerySetV1

    if type(admission) is not LiveExecutionAdmissionV2:
        raise ValueError("live execution source admission rejected")
    authority = admission.authority
    root = _trusted_repository_root(Path.cwd().resolve(strict=True))
    if _checked_out_repository_commit(root) != authority.source_commit_sha:
        raise ValueError("live execution source admission rejected")
    manifest_relative = Path(
        "config/acceptance/phase6/benchmark-manifest.json"
    )
    workflow_relative = Path(".github/workflows/phase6-acceptance.yml")
    query_relative = Path("config") / _DISCOVERY_QUERY_SET_NAME
    manifest_bytes = _read_exact_checked_out_source_file(
        root,
        source_commit_sha=authority.source_commit_sha,
        relative_path=manifest_relative,
        max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
    )
    workflow_bytes = _read_exact_checked_out_source_file(
        root,
        source_commit_sha=authority.source_commit_sha,
        relative_path=workflow_relative,
        max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
    )
    query_bytes = _read_exact_checked_out_source_file(
        root,
        source_commit_sha=authority.source_commit_sha,
        relative_path=query_relative,
        max_bytes=_DISCOVERY_DIGEST_BYTES,
    )
    manifest = LockedBenchmarkManifestV1.model_validate_json(
        manifest_bytes,
        strict=True,
    )
    query_set = DiscoveryQuerySetV1.model_validate_json(query_bytes, strict=True)
    if (
        manifest_bytes not in {
            canonical_json_bytes(manifest),
            canonical_json_bytes(manifest) + b"\n",
        }
        or query_bytes not in {
            canonical_json_bytes(query_set),
            canonical_json_bytes(query_set) + b"\n",
        }
        or manifest != admission.lock.selection_manifest
        or authority.acceptance_workflow_sha256
        != "sha256:" + hashlib.sha256(workflow_bytes).hexdigest()
        or authority.query_set_digest != query_set.query_set_digest
    ):
        raise ValueError("live execution source admission rejected")


def load_live_execution_admission_v2(
    *,
    authority_state_root: Path,
    authority_state_commit_sha: str,
    authority_state_root_digest: str,
    acceptance_run_id: str,
    state_repository_id: int,
    state_repository_full_name: str,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Rebuild V2 authority from a checked-out carrier before credentials.

    The only externally supplied values are canonical immutable checkout and
    state identities.  The authority digest itself comes from the protected
    runtime environment; its model, receipt, lock, and nomination are all
    decoded from operations-owned state before any state/source/provider token
    or client factory is touched.
    """

    try:
        source = os.environ if environ is None else environ
        authority_digest = source["PHASE6_AUTHORITY_DIGEST"]
        if (
            not _closed_identity(acceptance_run_id)
            or not _is_digest(authority_digest)
            or type(state_repository_id) is not int
            or state_repository_id <= 0
            or not _github_full_name(state_repository_full_name)
        ):
            raise ValueError
        carrier_commit_sha, carrier_root_digest = validate_acceptance_state_authority(
            state_commit_sha=authority_state_commit_sha,
            state_root_digest=authority_state_root_digest,
        )
        checkout = authority_state_root.resolve(strict=True)
        if _checked_out_repository_commit(checkout) != carrier_commit_sha:
            raise ValueError
        bundle = load_verified_state_checkout(
            checkout_root=checkout,
            expected_root_digest=carrier_root_digest,
        )
        root = bundle.root
        if (
            root.root_digest != carrier_root_digest
            or not _is_commit_sha(root.state_parent_commit_sha)
            or not _is_digest(root.prior_root_digest)
        ):
            raise ValueError
        from skillscout.adapters.operations_state import (
            OperationsStateStore,
            restore_acceptance_state_bundle,
        )
        from skillscout.application.acceptance import (
            LiveAuthorityStateObservation,
            LiveExecutionAdmissionV2,
            re_admit_live_execution_v2,
        )
        from skillscout.domain.acceptance import LiveAcceptanceAuthorityV2

        with tempfile.TemporaryDirectory(prefix="skillscout-v2-authority-") as temporary:
            temporary_root = Path(temporary).resolve(strict=True)
            operations_path = temporary_root / "operations.sqlite3"
            restore_acceptance_state_bundle(
                bundle,
                pipeline_path=temporary_root / "pipeline.sqlite3",
                operations_path=operations_path,
            )
            with OperationsStateStore(operations_path) as operations:
                snapshot = operations.acceptance_snapshot(acceptance_run_id)
        records = tuple(
            record
            for record in snapshot.facts
            if (
                record.kind == "acceptance_live_authority"
                and record.fact_digest == authority_digest
                and type(record.fact) is LiveAcceptanceAuthorityV2
            )
        )
        if len(records) != 1:
            raise ValueError
        authority = records[0].fact
        admission = re_admit_live_execution_v2(
            snapshot=snapshot,
            authority_digest=authority_digest,
            state_observation=LiveAuthorityStateObservation(
                state_repository_id=state_repository_id,
                state_repository_full_name=state_repository_full_name,
                authority_carrier_commit_sha=carrier_commit_sha,
                authority_carrier_root_digest=carrier_root_digest,
                authority_carrier_parent_commit_sha=root.state_parent_commit_sha,
                authority_carrier_prior_root_digest=root.prior_root_digest,
                lock_state_parent_commit_sha=authority.parent_state_commit_sha,
                lock_state_prior_root_digest=authority.parent_state_root_digest,
            ),
        )
        if (
            type(admission) is not LiveExecutionAdmissionV2
            or admission.authority.state_repository_id != state_repository_id
            or admission.authority.state_repository_full_name != state_repository_full_name
        ):
            raise ValueError
        _verify_live_execution_admission_source(admission)
        return admission
    except Exception:
        raise ValueError("live execution admission rejected") from None


def verify_live_acceptance_authority_state(
    *,
    authority_path: Path,
    source_commit_sha: str,
    state_commit_sha: str,
    state_root_digest: str,
    state_repository_id: int,
    state_repository_full_name: str,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Verify exact approved state read authority without mutating it."""

    source = os.environ if environ is None else environ
    authority = load_live_acceptance_authority(
        authority_path=authority_path,
        observed_source_commit_sha=source_commit_sha,
        observed_state_commit_sha=state_commit_sha,
        observed_state_root_digest=state_root_digest,
        observed_state_repository_id=state_repository_id,
        observed_state_repository_full_name=state_repository_full_name,
        environ=source,
    )
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

    if type(authority) is not LiveAcceptanceAuthorityV1:
        raise ValueError("live acceptance authority rejected")
    restored = read_exact_discovery_state(
        state_commit_sha=state_commit_sha,
        state_repository_id=state_repository_id,
        state_repository_full_name=state_repository_full_name,
        pipeline_state=Path(_DISCOVERY_DATABASE_LOCATORS[0]),
        operations_state=Path(_DISCOVERY_DATABASE_LOCATORS[1]),
        publication_state=Path(_DISCOVERY_DATABASE_LOCATORS[2]),
        environ=source,
    )
    if (
        getattr(restored, "observed_head", None) != state_commit_sha
        or getattr(getattr(restored, "bundle", None), "root", None) is None
        or getattr(restored.bundle.root, "root_digest", None) != state_root_digest
    ):
        raise ValueError("live acceptance state authority rejected")
    return authority


def validate_acceptance_state_authority(
    *,
    state_commit_sha: str,
    state_root_digest: str,
) -> tuple[str, str]:
    """Validate immutable state identity without consulting the environment."""

    if not _is_commit_sha(state_commit_sha) or not _is_digest(state_root_digest):
        raise ValueError("acceptance state authority rejected")
    return state_commit_sha, state_root_digest


def _is_digest(value: object) -> bool:
    if type(value) is not str or len(value) != 71 or not value.startswith("sha256:"):
        return False
    return all(character in "0123456789abcdef" for character in value[7:])


def _configured_state_lineage_anchor(config: object) -> object | None:
    """Build one externally verified state anchor from closed runtime config."""

    commit_sha = getattr(config, "state_lineage_anchor_commit_sha", None)
    root_digest = getattr(config, "state_lineage_anchor_root_digest", None)
    max_hops = getattr(config, "state_lineage_anchor_max_hops", 160)
    if commit_sha is None and root_digest is None:
        return None
    if (
        not _is_commit_sha(commit_sha)
        or not _is_digest(root_digest)
        or type(max_hops) is not int
        or not 1 <= max_hops <= _DISCOVERY_STATE_LINEAGE_MAX_HOPS
    ):
        raise ValueError("state lineage anchor rejected")
    from skillscout.adapters.state_branch import StateLineageAnchor

    return StateLineageAnchor(
        commit_sha=commit_sha,
        root_digest=root_digest,
        max_hops=max_hops,
    )


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
        if query_set.query_set_digest is None or (
            query_set_digest is not None and query_set_digest != query_set.query_set_digest
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


class _FrozenOwnedState:
    """Read-only owner export carried forward without opening its state adapter."""

    def __init__(self, exported: object) -> None:
        if exported is None or not hasattr(exported, "export_digest"):
            raise ValueError("frozen owned state rejected")
        self._exported = exported

    def export_owned_state(self) -> object:
        return self._exported

    def close(self) -> None:
        return None


def _default_publication_state(config: object) -> object:
    from skillscout.adapters.publication_state import PublicationStateStore

    return PublicationStateStore(
        getattr(
            config,
            "publication_state",
            Path(_DISCOVERY_DATABASE_LOCATORS[2]),
        )
    )


class _LateStateDurabilityBarrier:
    """Open the state writer only for one exact durability confirmation."""

    def __init__(
        self,
        config: (
            DiscoveryRuntimeConfig
            | NominationRuntimeConfig
            | FreshCampaignPreparationRuntimeConfig
        ),
        source: Mapping[str, str],
        *,
        frozen_publication_export: object | None = None,
    ) -> None:
        self._config = config
        self._source = source
        self._frozen_publication_export = frozen_publication_export
        self._acceptance_resume: dict[str, object] | None = None
        self._pending_resume_locator: object | None = None
        self._state_branch_read_cache: object | None = None

    def _state_lineage_anchor(self) -> object | None:
        """Return the independently verified bounded state anchor, when present."""

        return _configured_state_lineage_anchor(self._config)

    def state_branch_read_cache(self) -> object:
        """Return the run-scoped immutable Git-object cache for this writer."""

        if self._state_branch_read_cache is None:
            from skillscout.adapters.state_branch import StateBranchReadCache

            self._state_branch_read_cache = StateBranchReadCache()
        return self._state_branch_read_cache

    def configure_acceptance_resume(
        self,
        *,
        authority: object,
        acceptance_run_id: str,
        lineage_commit_shas: tuple[str, ...],
        lineage_root_digests: tuple[str, ...],
        locator_digest: str | None = None,
        transition_index: int = 0,
    ) -> None:
        """Bind locator creation to one immutable authority and verified lineage."""

        from skillscout.domain.acceptance import (
            LiveAcceptanceAuthorityV1,
            LiveAcceptanceAuthorityV2,
        )

        if (
            type(authority) not in {LiveAcceptanceAuthorityV1, LiveAcceptanceAuthorityV2}
            or authority.authority_digest is None
            or type(acceptance_run_id) is not str
            or not acceptance_run_id
            or len(lineage_commit_shas) != len(lineage_root_digests)
            or not lineage_commit_shas
            or len(lineage_commit_shas) > 255
            or lineage_commit_shas[0] != authority.state_commit_sha
            or lineage_root_digests[0] != authority.state_root_digest
            or any(not _is_commit_sha(item) for item in lineage_commit_shas)
            or any(not _is_digest(item) for item in lineage_root_digests)
            or (transition_index == 0) != (locator_digest is None)
            or transition_index < 0
            or transition_index > 160
            or (locator_digest is not None and not _is_digest(locator_digest))
        ):
            raise ValueError("acceptance resume authority rejected")
        self._acceptance_resume = {
            "authority": authority,
            "acceptance_run_id": acceptance_run_id,
            "lineage_commit_shas": lineage_commit_shas,
            "lineage_root_digests": lineage_root_digests,
            "locator_digest": locator_digest,
            "transition_index": transition_index,
        }
        self._pending_resume_locator = None

    def acceptance_resume_lineage(
        self,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return the active verified lineage for the next fixed runner."""

        resume = self._acceptance_resume
        if resume is None:
            raise ValueError("acceptance resume lineage is not configured")
        commits = resume["lineage_commit_shas"]
        roots = resume["lineage_root_digests"]
        if type(commits) is not tuple or type(roots) is not tuple:
            raise ValueError("acceptance resume lineage is invalid")
        return commits, roots

    def acceptance_resume_locator(self) -> tuple[str | None, int]:
        """Return the latest durable locator identity for runner reconstruction."""

        resume = self._acceptance_resume
        if resume is None:
            raise ValueError("acceptance resume lineage is not configured")
        digest = resume["locator_digest"]
        index = resume["transition_index"]
        if (
            digest is not None
            and (type(digest) is not str or not _is_digest(digest))
            or type(index) is not int
        ):
            raise ValueError("acceptance resume locator is invalid")
        return digest, index

    def _record_acceptance_transition(
        self,
        *,
        operations_store: object,
        observed_head: str,
        prior_root_digest: str,
        created_at: str,
        transition_phase: str,
        semantic_stage: str | None,
        attempt_no: int | None,
        semantic_status: str | None,
        workflow_authority_digest: str | None,
    ) -> object | None:
        """Append one locator whose object must first appear in the CAS child."""

        from skillscout.domain.acceptance import (
            AcceptanceCampaignResumeLocatorV1,
            LiveAcceptanceAuthorityV1,
            LiveAcceptanceAuthorityV2,
        )

        resume = self._acceptance_resume
        if resume is None:
            return None
        authority = resume["authority"]
        commits = resume["lineage_commit_shas"]
        roots = resume["lineage_root_digests"]
        index = resume["transition_index"]
        if (
            type(authority) not in {LiveAcceptanceAuthorityV1, LiveAcceptanceAuthorityV2}
            or type(commits) is not tuple
            or type(roots) is not tuple
            or type(index) is not int
            or commits[-1] != observed_head
            or roots[-1] != prior_root_digest
            or index >= 160
            or self._pending_resume_locator is not None
        ):
            raise ValueError("acceptance resume lineage drifted")
        locator = AcceptanceCampaignResumeLocatorV1(
            schema_version="acceptance-campaign-resume-locator-v1",
            acceptance_run_id=str(resume["acceptance_run_id"]),
            live_acceptance_authority_digest=authority.authority_digest or "",
            source_commit_sha=authority.source_commit_sha,
            manifest_digest=authority.manifest_digest,
            state_repository_id=authority.state_repository_id,
            state_repository_full_name=authority.state_repository_full_name,
            original_state_commit_sha=authority.state_commit_sha,
            original_state_root_digest=authority.state_root_digest,
            parent_state_commit_sha=observed_head,
            parent_state_root_digest=prior_root_digest,
            transition_index=index + 1,
            previous_locator_digest=resume["locator_digest"],
            transition_phase=transition_phase,
            semantic_stage=semantic_stage,
            attempt_no=attempt_no,
            semantic_status=semantic_status,
            workflow_authority_digest=workflow_authority_digest,
            semantic_provider=authority.semantic_provider,
            stage_models=authority.stage_models,
            prompt_versions=authority.prompt_versions,
            schema_versions=authority.schema_versions,
            policy_versions=authority.policy_versions,
            recorded_at=created_at,
        )
        record = getattr(operations_store, "record_acceptance_fact", None)
        if not callable(record):
            raise ValueError("acceptance operations state rejected")
        record(
            str(resume["acceptance_run_id"]),
            "acceptance_campaign_resume_locator",
            locator,
        )
        self._pending_resume_locator = locator
        return locator

    def _verify_authority_carrier_recovery(
        self,
        *,
        operations_store: object,
        observed_head: str,
        prior_root_digest: str,
    ) -> None:
        """Prove the one locally assembled authority-carrier fact delta.

        The state-branch recovery below compares the complete remote bundle
        byte-for-byte with this local bundle.  Before allowing that recovery,
        establish that this local child contains exactly the authority and
        first locator it is supposed to carry, rather than merely a matching
        root digest.
        """

        from skillscout.adapters.operations_state import (
            AcceptanceFactRecord,
            AcceptanceRunSnapshot,
        )
        from skillscout.domain.acceptance import (
            AcceptanceCampaignResumeLocatorV1,
            LiveAcceptanceAuthorityV1,
            LiveAcceptanceAuthorityV2,
        )

        resume = self._acceptance_resume
        locator = self._pending_resume_locator
        if (
            resume is None
            or type(locator) is not AcceptanceCampaignResumeLocatorV1
            or type(resume.get("authority"))
            not in {LiveAcceptanceAuthorityV1, LiveAcceptanceAuthorityV2}
            or type(resume.get("acceptance_run_id")) is not str
        ):
            raise ValueError("authority carrier recovery proof rejected")
        authority = resume["authority"]
        acceptance_run_id = resume["acceptance_run_id"]
        if (
            authority.authority_digest is None
            or locator.acceptance_run_id != acceptance_run_id
            or locator.live_acceptance_authority_digest != authority.authority_digest
            or locator.original_state_commit_sha != authority.state_commit_sha
            or locator.original_state_root_digest != authority.state_root_digest
            or locator.parent_state_commit_sha != observed_head
            or locator.parent_state_root_digest != prior_root_digest
            or locator.transition_index != 1
            or locator.previous_locator_digest is not None
            or locator.transition_phase != "authority_carrier"
        ):
            raise ValueError("authority carrier recovery proof rejected")
        snapshot_reader = getattr(operations_store, "acceptance_snapshot", None)
        if not callable(snapshot_reader):
            raise ValueError("authority carrier recovery proof rejected")
        snapshot = snapshot_reader(acceptance_run_id)
        if (
            type(snapshot) is not AcceptanceRunSnapshot
            or snapshot.acceptance_run_id != acceptance_run_id
            or any(type(record) is not AcceptanceFactRecord for record in snapshot.facts)
        ):
            raise ValueError("authority carrier recovery proof rejected")
        authorities = tuple(
            record
            for record in snapshot.facts
            if record.kind == "acceptance_live_authority"
        )
        locators = tuple(
            record
            for record in snapshot.facts
            if record.kind == "acceptance_campaign_resume_locator"
        )
        if (
            len(authorities) != 1
            or authorities[0].fact_digest != authority.authority_digest
            or authorities[0].fact != authority
            or len(locators) != 1
            or locators[0].fact_digest != locator.locator_digest
            or locators[0].fact != locator
        ):
            raise ValueError("authority carrier recovery proof rejected")

    def _verify_nomination_recovery(
        self,
        *,
        operations_store: object,
        observed_head: str,
        prior_root_digest: str,
        created_at: str,
    ) -> None:
        """Prove the exact Search-only fact that the local CAS child carries."""

        from skillscout.adapters.operations_state import (
            AcceptanceFactRecord,
            AcceptanceRunSnapshot,
        )
        from skillscout.application.acceptance import _fresh_nomination_authority_digest
        from skillscout.domain.acceptance import NominationSetV1

        authority_digest = _fresh_nomination_authority_digest(
            state_repository_id=self._config.state_repository_id,
            state_repository_full_name=self._config.state_repository_full_name,
            state_commit_sha=observed_head,
            state_root_digest=prior_root_digest,
            query_set_digest=self._config.query_set_digest,
        )
        nomination_set_id = "fresh-nomination-" + authority_digest.removeprefix("sha256:")[:32]
        snapshot_reader = getattr(operations_store, "acceptance_snapshot", None)
        if not callable(snapshot_reader):
            raise ValueError("nomination recovery proof rejected")
        try:
            snapshot = snapshot_reader(nomination_set_id)
        except Exception:
            raise ValueError("nomination recovery proof rejected") from None
        if (
            type(snapshot) is not AcceptanceRunSnapshot
            or snapshot.acceptance_run_id != nomination_set_id
            or type(snapshot.facts) is not tuple
            or len(snapshot.facts) != 1
            or type(snapshot.facts[0]) is not AcceptanceFactRecord
        ):
            raise ValueError("nomination recovery proof rejected")
        record = snapshot.facts[0]
        nomination = record.fact
        if (
            record.acceptance_run_id != nomination_set_id
            or record.kind != "acceptance_nomination"
            or type(nomination) is not NominationSetV1
            or nomination.nomination_set_id != nomination_set_id
            or nomination.nomination_set_digest is None
            or record.fact_digest != nomination.nomination_set_digest
            or nomination.query_set_digest != self._config.query_set_digest
            or nomination.search_run_authority_digest != authority_digest
            or nomination.created_at != created_at
            or len(nomination.search_derived_entries) < 5
            or bool(nomination.user_nominated_entries)
            or any(
                entry.selection_source != "search_derived"
                for entry in nomination.search_derived_entries
            )
        ):
            raise ValueError("nomination recovery proof rejected")

    def prepare_acceptance_transition(
        self,
        *,
        operations_store: object,
        observed_head: str,
        prior_root_digest: str,
        stage: str,
        attempt_no: int,
        status: str,
        recorded_at: str,
        workflow_authority_digest: str,
    ) -> None:
        """Bind a semantic attempt fact to the exact CAS child that carries it."""

        self._record_acceptance_transition(
            operations_store=operations_store,
            observed_head=observed_head,
            prior_root_digest=prior_root_digest,
            created_at=recorded_at,
            transition_phase=("started" if status == "started" else "result_durable"),
            semantic_stage=stage,
            attempt_no=attempt_no,
            semantic_status=status,
            workflow_authority_digest=workflow_authority_digest,
        )

    def _advance_acceptance_transition(self, synchronized: object) -> None:
        locator = self._pending_resume_locator
        resume = self._acceptance_resume
        if locator is None or resume is None:
            return
        commit_sha = getattr(
            synchronized,
            "commit_sha",
            getattr(synchronized, "verified_state_head", None),
        )
        root_digest = getattr(
            synchronized,
            "root_digest",
            getattr(synchronized, "state_root_digest", None),
        )
        status = getattr(synchronized, "status", "verified")
        previous_head = getattr(
            synchronized,
            "previous_head",
            locator.parent_state_commit_sha,
        )
        if (
            status != "verified"
            or previous_head != locator.parent_state_commit_sha
            or not _is_commit_sha(commit_sha)
            or not _is_digest(root_digest)
        ):
            raise ValueError("acceptance resume transition was not durable")
        self._acceptance_resume = {
            **resume,
            "lineage_commit_shas": (
                *resume["lineage_commit_shas"],
                commit_sha,
            ),
            "lineage_root_digests": (
                *resume["lineage_root_digests"],
                root_digest,
            ),
            "locator_digest": locator.locator_digest,
            "transition_index": locator.transition_index,
        }
        self._pending_resume_locator = None

    def confirm(self, **arguments: object) -> object:
        from skillscout.adapters.state_branch import (
            StateBranchClient,
            StateBranchDurabilityBarrier,
            StateBranchStore,
        )
        from skillscout.domain.discovery import DiscoveryBudgetPolicyV1

        client = StateBranchClient(
            token=_required_credential(self._source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
            repository_id=self._config.state_repository_id,
            repository_full_name=self._config.state_repository_full_name,
        )
        try:
            barrier = StateBranchDurabilityBarrier(
                state_store=StateBranchStore(
                    client,
                    read_cache=self.state_branch_read_cache(),
                ),
                query_set_digest=self._config.query_set_digest,
                budget_policy_digest=(DiscoveryBudgetPolicyV1().budget_policy_digest or ""),
                lineage_anchor=self._state_lineage_anchor(),
            )
            synchronized = barrier.confirm(**arguments)
            self._advance_acceptance_transition(synchronized)
            return synchronized
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
        transition_phase: str,
        semantic_stage: str | None = None,
        attempt_no: int | None = None,
        semantic_status: str | None = None,
        workflow_authority_digest: str | None = None,
    ) -> object:
        """Synchronize one non-semantic discovery checkpoint and reread it."""

        from skillscout.adapters.operations_state import assemble_three_store_bundle
        from skillscout.adapters.state import SQLiteStateStore
        from skillscout.adapters.state_branch import (
            StateBranchClient,
            StateBranchPostCasUncertain,
            StateBranchStore,
            StateSyncObservation,
        )
        from skillscout.domain.discovery import DiscoveryBudgetPolicyV1

        self._record_acceptance_transition(
            operations_store=operations_store,
            observed_head=observed_head,
            prior_root_digest=prior_root_digest,
            created_at=created_at,
            transition_phase=transition_phase,
            semantic_stage=semantic_stage,
            attempt_no=attempt_no,
            semantic_status=semantic_status,
            workflow_authority_digest=workflow_authority_digest,
        )
        pipeline = (
            pipeline_store
            if pipeline_store is not None
            else SQLiteStateStore(
                getattr(
                    self._config,
                    "pipeline_state",
                    Path(_DISCOVERY_DATABASE_LOCATORS[0]),
                )
            )
        )
        owns_pipeline = pipeline_store is None
        publication = (
            _FrozenOwnedState(self._frozen_publication_export)
            if self._frozen_publication_export is not None
            else _default_publication_state(self._config)
        )
        client = StateBranchClient(
            token=_required_credential(self._source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
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
                budget_policy_digest=(DiscoveryBudgetPolicyV1().budget_policy_digest or ""),
                created_at=created_at,
            )
            store = StateBranchStore(
                client,
                read_cache=self.state_branch_read_cache(),
            )
            lineage_anchor = self._state_lineage_anchor()
            try:
                if lineage_anchor is None:
                    synchronized = store.sync(bundle, observed_head)
                else:
                    synchronized = store.sync(
                        bundle,
                        observed_head,
                        lineage_anchor=lineage_anchor,
                    )
            except StateBranchPostCasUncertain as uncertainty:
                if transition_phase not in {"authority_carrier", "nomination"}:
                    raise
                if transition_phase == "authority_carrier":
                    self._verify_authority_carrier_recovery(
                        operations_store=operations_store,
                        observed_head=observed_head,
                        prior_root_digest=prior_root_digest,
                    )
                else:
                    self._verify_nomination_recovery(
                        operations_store=operations_store,
                        observed_head=observed_head,
                        prior_root_digest=prior_root_digest,
                        created_at=created_at,
                    )
                # Nomination is the sole other recoverable transition: it is a
                # Search-only state fact with no semantic, publication, or
                # protected-lock effect.  The store still proves the complete
                # immutable child bundle before returning it.
                if lineage_anchor is None:
                    synchronized = store.reconcile_post_cas_uncertainty(
                        uncertainty,
                        bundle,
                        observed_head,
                        expected_prior_root_digest=prior_root_digest,
                    )
                else:
                    synchronized = store.reconcile_post_cas_uncertainty(
                        uncertainty,
                        bundle,
                        observed_head,
                        expected_prior_root_digest=prior_root_digest,
                        lineage_anchor=lineage_anchor,
                    )
            if (
                type(synchronized) is not StateSyncObservation
                or synchronized.status != "verified"
                or synchronized.previous_head != observed_head
                or synchronized.root_digest != bundle.root.root_digest
                or len(synchronized.commit_sha) != 40
                or any(character not in "0123456789abcdef" for character in synchronized.commit_sha)
                or len(synchronized.tree_sha) != 40
                or any(character not in "0123456789abcdef" for character in synchronized.tree_sha)
            ):
                raise ValueError("discovery state synchronization rejected")
            self._advance_acceptance_transition(synchronized)
            return synchronized
        finally:
            client.close()
            publication.close()
            if owns_pipeline:
                pipeline.close()

    def sync_nomination(self, **arguments: object) -> object:
        """Reuse the exact three-store CAS for a Search-only nomination."""

        return self.sync_discovery(  # type: ignore[arg-type]
            **arguments,
            transition_phase="nomination",
        )

    def sync_benchmark_lock(self, **arguments: object) -> object:
        """Persist the protected fresh lock through one forward CAS with no recovery path."""

        return self.sync_discovery(  # type: ignore[arg-type]
            **arguments,
            transition_phase="benchmark_lock",
        )


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
    frozen_owner_export: object | None = None,
) -> object:
    """Build a publication-incapable discovery application with lazy remotes."""

    if type(config) is not DiscoveryRuntimeConfig:
        raise ValueError("discovery runtime configuration rejected")
    source = os.environ if environ is None else environ
    durability_barrier = _LateStateDurabilityBarrier(
        config,
        source,
        frozen_publication_export=frozen_owner_export,
    )

    def search_factory() -> object:
        from skillscout.adapters.github import GitHubReadClient

        return GitHubReadClient(
            token=_required_credential(source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN")
        )

    def state_restore() -> object:
        from skillscout.adapters.state_branch import (
            StateBranchClient,
            StateBranchStore,
        )

        client = StateBranchClient(
            token=_required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
            repository_id=config.state_repository_id,
            repository_full_name=config.state_repository_full_name,
        )
        try:
            store = StateBranchStore(
                client,
                read_cache=durability_barrier.state_branch_read_cache(),
            )
            lineage_anchor = _configured_state_lineage_anchor(config)
            observation = (
                store.restore()
                if lineage_anchor is None
                else store.restore(lineage_anchor=lineage_anchor)
            )
            bundle = getattr(observation, "bundle", None)
            if bundle is not None:
                if getattr(bundle, "root", None) is None:
                    raise ValueError("discovery initial state rejected")
                from skillscout.adapters.operations_state import (
                    restore_acceptance_state_bundle,
                    restore_three_store_bundle,
                )
                from skillscout.adapters.state_branch import VerifiedStateBundle

                if type(bundle) is VerifiedStateBundle:
                    if frozen_owner_export is None:
                        restore_three_store_bundle(
                            bundle,
                            pipeline_path=config.pipeline_state,
                            operations_path=config.operations_state,
                            publication_path=config.publication_state,
                        )
                    else:
                        restore_acceptance_state_bundle(
                            bundle,
                            pipeline_path=config.pipeline_state,
                            operations_path=config.operations_state,
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
            from skillscout.application.acceptance import FixedAcceptanceCandidate
            from skillscout.application.discovery import (
                DiscoveryCandidateExecution,
                DiscoveryReaderTelemetry,
                DiscoverySemanticTelemetry,
                DiscoveryWorkflowExecution,
                classify_extractor_terminal,
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
            from skillscout.application.ports import (
                CandidateSourceUnavailable,
                ErrorCode,
                SafeFailure,
            )
            from skillscout.cli import (
                CandidateValidationAdapter,
                LocalCandidateArtifactProjector,
            )
            from skillscout.domain.candidate_authority import (
                CandidateExecutionAuthorityV1,
            )
            from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
            from skillscout.domain.discovery import (
                DiscoveredCandidateV1,
                DiscoveryCandidateTerminalV1,
                DiscoveryRunAuthorityV1,
                SemanticReservationV1,
            )
            from skillscout.domain.review import (
                GeneratorOutcomeEvidenceV1,
                ReviewAttestationV1,
                candidate_terminal_summary_bytes,
            )
            from skillscout.domain.subjects import RepositorySubject
            from skillscout.domain.enums import EffectScope

            candidate = arguments.get("candidate")
            discovery_authority = arguments.get("discovery_authority")
            operations = arguments.get("operations_store")
            barrier = arguments.get("durability_barrier")
            phase3_builder = arguments.get("phase3_factory")
            observed_head = arguments.get("observed_head")
            prior_root = arguments.get("prior_root_digest")
            pinned_commit_sha = arguments.get("pinned_commit_sha")
            recovery_only = arguments.get("recovery_only", False)
            if (
                type(candidate)
                not in {
                    DiscoveredCandidateV1,
                    FixedAcceptanceCandidate,
                }
                or type(discovery_authority) is not DiscoveryRunAuthorityV1
                or type(operations) is not OperationsStateStore
                or not callable(phase3_builder)
                or type(observed_head) is not str
                or type(prior_root) is not str
                or type(recovery_only) is not bool
                or (
                    pinned_commit_sha is not None
                    and (
                        type(pinned_commit_sha) is not str or not _is_commit_sha(pinned_commit_sha)
                    )
                )
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
                    "discovery_run_authority_digest": (discovery_authority.authority_digest),
                    "candidate_digest": candidate.candidate_digest,
                    "phase2_profile_version": config.phase2_profile_version,
                    "extractor_model_id": config.extractor_model_id,
                }
            )
            state_head = observed_head
            state_root = prior_root
            semantic_telemetry: list[DiscoverySemanticTelemetry] = []
            reader_telemetry: DiscoveryReaderTelemetry | None = None
            restored_snapshot = operations.snapshot_run(discovery_authority.run_id)
            restored_discovery_reservation = next(
                (
                    item
                    for item in restored_snapshot.discovery_reservations
                    if item.repository_id == candidate.repository.repository_id
                ),
                None,
            )
            semantic_reservation = next(
                (
                    item
                    for item in restored_snapshot.semantic_reservations
                    if item.repository_id == candidate.repository.repository_id
                ),
                None,
            )
            if recovery_only:
                recovered_extractor_attempts = tuple(
                    item
                    for item in restored_snapshot.semantic_attempts
                    if item.repository_id == candidate.repository.repository_id
                    and item.workflow_authority_digest == phase2_authority_digest
                    and item.stage == "extractor"
                )
                if len(recovered_extractor_attempts) != 3:
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            fixed_admission = (
                candidate.admission if type(candidate) is FixedAcceptanceCandidate else None
            )
            if semantic_reservation is not None and (
                type(semantic_reservation) is not SemanticReservationV1
                or (fixed_admission is None and restored_discovery_reservation is None)
                or semantic_reservation.discovery_run_authority_digest
                != discovery_authority.authority_digest
                or semantic_reservation.repository_id != candidate.repository.repository_id
                or semantic_reservation.discovery_reservation_digest
                != (
                    fixed_admission.admission_digest
                    if fixed_admission is not None
                    else restored_discovery_reservation.reservation_digest
                )
                or semantic_reservation.phase2_run_authority_digest != phase2_authority_digest
            ):
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)

            def reserve_before_extractor(
                *,
                pipeline_store: object,
                run_id: str,
            ) -> SemanticReservationReceipt:
                del run_id
                nonlocal semantic_reservation, state_head, state_root
                if fixed_admission is not None:
                    semantic_reservation = operations.reserve_acceptance_semantic_candidate(
                        discovery_authority.run_id,
                        fixed_admission,
                        phase2_authority_digest,
                        _discovery_timestamp(),
                    )
                else:
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
                    transition_phase="semantic_candidate_reserved",
                )
                state_head = synchronized.commit_sha
                state_root = synchronized.root_digest
                return SemanticReservationReceipt(
                    reservation_digest=semantic_reservation.reservation_digest,
                    verified_state_head=state_head,
                    state_root_digest=state_root,
                )

            def reserve_before_request(
                *,
                pipeline_store: object,
                run_id: str,
                repository_id: int,
                workflow_authority_digest: str,
                stage: str,
                attempt_no: int,
                observed_head: str,
                prior_root_digest: str,
            ) -> SemanticReservationReceipt:
                del run_id
                nonlocal state_head, state_root
                if fixed_admission is None:
                    raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
                request = operations.reserve_acceptance_semantic_request(
                    acceptance_run_id=fixed_admission.acceptance_run_id,
                    fixed_candidate_admission_digest=(fixed_admission.admission_digest or ""),
                    repository_id=repository_id,
                    workflow_spec_authority_digest=(workflow_authority_digest),
                    stage=stage,  # type: ignore[arg-type]
                    attempt_no=attempt_no,
                    reserved_at=_discovery_timestamp(),
                )
                synchronized = barrier.sync_discovery(
                    operations_store=operations,
                    observed_head=observed_head,
                    prior_root_digest=prior_root_digest,
                    created_at=_discovery_timestamp(),
                    pipeline_store=pipeline_store,
                    transition_phase="request_reserved",
                    semantic_stage=stage,
                    attempt_no=attempt_no,
                    workflow_authority_digest=workflow_authority_digest,
                )
                state_head = synchronized.commit_sha
                state_root = synchronized.root_digest
                return SemanticReservationReceipt(
                    reservation_digest=request.reservation_digest or "",
                    verified_state_head=state_head,
                    state_root_digest=state_root,
                )

            publication = (
                _FrozenOwnedState(frozen_owner_export)
                if frozen_owner_export is not None
                else _LazyDiscoveryCapability(
                    lambda: _default_publication_state(config),
                    EffectScope.LOCAL_STATE,
                )
            )
            phase2_state = SQLiteStateStore(config.pipeline_state)

            def deny_recovery_capability() -> object:
                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)

            github_factory = (
                deny_recovery_capability
                if recovery_only
                else lambda: GitHubReadClient(
                    token=_required_credential(source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN")
                )
            )
            github = _LazyDiscoveryCapability(
                github_factory,
                EffectScope.REMOTE_READ,
            )
            extractor_factory = (
                deny_recovery_capability
                if recovery_only
                else lambda: (
                    OpenAIExtractionClient()
                    if provider.provider is SemanticProvider.OPENAI
                    else OpenAIExtractionClient(
                        model=provider.extract_model,
                        provider_settings=provider,
                    )
                )
            )
            extractor = _LazyDiscoveryCapability(
                extractor_factory,
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
                request_reservation_hook=(
                    reserve_before_request if fixed_admission is not None else None
                ),
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
                    repository=(f"https://github.com/{candidate.repository.full_name}"),
                    ref=pinned_commit_sha,
                )
                with tempfile.TemporaryDirectory(
                    prefix="skillscout-discovery-phase2-",
                    dir=Path(tempfile.gettempdir()).resolve(strict=True),
                ) as phase2_output:
                    phase2_summary = runtime.runner.run(subject, Path(phase2_output))
                chain = phase2_state.verify_run_chain(phase2_summary.run_id)
                extractor_result = next(
                    (result for result in chain.results if result.stage.value == "extractor"),
                    None,
                )
                reader_result = next(
                    (result for result in chain.results if result.stage.value == "reader"),
                    None,
                )
                if reader_result is not None:
                    reader_budgets = reader_result.payload.get("budgets")
                    if isinstance(reader_budgets, dict):
                        reader_telemetry = DiscoveryReaderTelemetry(
                            file_count=int(reader_budgets["files_read"]),
                            source_file_count=int(reader_budgets["source_files_read"]),
                            total_bytes=int(reader_budgets["total_bytes"]),
                            estimated_tokens=int(reader_budgets["estimated_input_tokens"]),
                        )
                for attempt in getattr(chain, "attempts", ()):
                    if attempt.stage.value != "extractor":
                        continue
                    if attempt.status.value == "failed":
                        continue
                    if (
                        attempt.status.value != "succeeded"
                        or attempt.request_id is None
                        or attempt.model_id is None
                        or attempt.prompt_version is None
                        or attempt.policy_version is None
                        or attempt.prompt_tokens is None
                        or attempt.completion_tokens is None
                        or attempt.total_tokens is None
                        or attempt.latency_ms is None
                    ):
                        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                    semantic_telemetry.append(
                        DiscoverySemanticTelemetry(
                            stage="extractor",
                            workflow_authority_digest=phase2_authority_digest,
                            attempt_no=attempt.attempt_no,
                            request_id=attempt.request_id,
                            actual_model=attempt.model_id,
                            prompt_version=attempt.prompt_version,
                            schema_version=str(extractor_result.payload["output_schema_version"])
                            if extractor_result is not None
                            else "",
                            policy_version=attempt.policy_version,
                            prompt_tokens=attempt.prompt_tokens,
                            completion_tokens=attempt.completion_tokens,
                            total_tokens=attempt.total_tokens,
                            latency_ms=attempt.latency_ms,
                        )
                    )
                state_head = phase2_guard.verified_state_head
                state_root = phase2_guard.state_root_digest
            except SemanticProviderFailure as failure:
                state_head = phase2_guard.verified_state_head
                state_root = phase2_guard.state_root_digest
                if failure.disposition is SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN:
                    outcome = "semantic_outcome_unknown"
                else:
                    outcome = "permanent_failure"
                terminal_values = {
                    "schema_version": "discovery-candidate-terminal-v1",
                    "discovery_run_authority_digest": (discovery_authority.authority_digest),
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
                    if failure.code
                    in {
                        ErrorCode.STAGE_TRANSIENT_FAILURE,
                        ErrorCode.RETRY_EXHAUSTED,
                    }
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
                    "discovery_run_authority_digest": (discovery_authority.authority_digest),
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
                    acceptance_system_outcome=(
                        "provider_exhausted" if failure.code is ErrorCode.RETRY_EXHAUSTED else None
                    ),
                )
            finally:
                _close_discovery_resources(
                    extractor,
                    github,
                    publication,
                    phase2_state,
                )

            candidate_source = SQLitePhaseTwoCandidateSource(config.pipeline_state)
            try:
                descriptors = derive_candidate_subject_descriptors(
                    candidate_source,
                    phase2_run_id=phase2_summary.run_id,
                )
            except CandidateSourceUnavailable:
                terminal_values = {
                    "schema_version": "discovery-candidate-terminal-v1",
                    "discovery_run_authority_digest": (discovery_authority.authority_digest),
                    "repository_id": candidate.repository.repository_id,
                    "semantic_reservation_digest": (
                        semantic_reservation.reservation_digest
                        if semantic_reservation is not None
                        else None
                    ),
                    "outcome": "permanent_failure",
                    "workflow_authority_digests": (),
                    "recorded_at": _discovery_timestamp(),
                }
                return DiscoveryCandidateExecution(
                    terminal=DiscoveryCandidateTerminalV1(
                        **terminal_values,
                        terminal_digest=sha256_digest(terminal_values),
                    ),
                    eligible_candidates=(),
                    state_commit_sha=state_head,
                    state_root_digest=state_root,
                )
            workflow_executions: list[DiscoveryWorkflowExecution] = []
            acceptance_system_outcome = None
            if not descriptors:
                filter_result = next(
                    result for result in chain.results if result.stage.value == "filter"
                )
                if filter_result.payload.get("outcome") == "rejected":
                    outcome = "filter_rejected"
                elif extractor_result is None:
                    outcome = "permanent_failure"
                else:
                    outcome, acceptance_system_outcome = classify_extractor_terminal(
                        str(extractor_result.payload.get("outcome"))
                    )
                workflow_authorities: list[str] = []
                eligible = []
            else:
                profile = PhaseThreeRuntimeProfile.from_configured_models(
                    generator_model_id=provider.generator_model,
                    reviewer_model_id=provider.reviewer_model,
                )

                def recover_phase3_success_telemetry(
                    workflow_authority: CandidateExecutionAuthorityV1,
                ) -> None:
                    """Project decided predecessors from an interrupted Phase 3 chain."""

                    phase3_state = SQLiteStateStore(config.pipeline_state)
                    try:
                        recovered_chain = phase3_state.find_resumable_candidate(workflow_authority)
                        if recovered_chain is None:
                            return
                        generator_attempts = tuple(
                            attempt
                            for attempt in recovered_chain.attempts
                            if attempt.stage.value == "generator" and attempt.status == "succeeded"
                        )
                        if not generator_attempts:
                            return
                        checkpoint_payloads = phase3_state.read_candidate_checkpoint_payloads(
                            recovered_chain.identity.run_id
                        )
                    finally:
                        phase3_state.close()
                    generator_payload = checkpoint_payloads.get("checkpoint_generator_payload")
                    if generator_payload is None:
                        return
                    if type(generator_payload) is not bytes:
                        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                    generator_evidence = GeneratorOutcomeEvidenceV1.model_validate_json(
                        generator_payload,
                        strict=True,
                    )
                    if (
                        canonical_json_bytes(generator_evidence) != generator_payload
                        or generator_evidence.actual_generator_model_id is None
                        or generator_evidence.request_id is None
                        or generator_evidence.usage is None
                    ):
                        raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                    recovered = DiscoverySemanticTelemetry(
                        stage="generator",
                        workflow_authority_digest=(workflow_authority.authority_digest),
                        attempt_no=generator_attempts[-1].attempt_no,
                        request_id=generator_evidence.request_id,
                        actual_model=(generator_evidence.actual_generator_model_id),
                        prompt_version=(generator_evidence.generator_prompt_version),
                        schema_version=(generator_evidence.generator_output_schema_version),
                        policy_version=(generator_evidence.generator_policy_version),
                        prompt_tokens=generator_evidence.usage.prompt_tokens,
                        completion_tokens=(generator_evidence.usage.completion_tokens),
                        total_tokens=generator_evidence.usage.total_tokens,
                        latency_ms=generator_evidence.latency_ms,
                    )
                    key = (
                        recovered.stage,
                        recovered.workflow_authority_digest,
                        recovered.attempt_no,
                    )
                    existing_keys = {
                        (
                            item.stage,
                            item.workflow_authority_digest,
                            item.attempt_no,
                        )
                        for item in semantic_telemetry
                    }
                    if key not in existing_keys:
                        semantic_telemetry.append(recovered)

                workflow_authorities = []
                eligible = []
                workflow_outcomes: list[str] = []
                fatal_outcome: str | None = None
                for descriptor in descriptors:
                    with tempfile.TemporaryDirectory(
                        prefix="skillscout-discovery-phase3-",
                        dir=Path(tempfile.gettempdir()).resolve(strict=True),
                    ) as directory:
                        descriptor_path = Path(directory) / "candidate.json"
                        descriptor_path.write_bytes(canonical_json_bytes(descriptor))
                        descriptor_path.chmod(0o600)
                        try:
                            resolved = load_candidate_subject(descriptor_path, candidate_source)
                        except CandidateSourceUnavailable:
                            fatal_outcome = "permanent_failure"
                            break
                        workflow_authority = _execution_authority(source=resolved, profile=profile)
                        workflow_authorities.append(workflow_authority.authority_digest)
                        phase3_publication = (
                            _FrozenOwnedState(frozen_owner_export)
                            if frozen_owner_export is not None
                            else _LazyDiscoveryCapability(
                                lambda: _default_publication_state(config),
                                EffectScope.LOCAL_STATE,
                            )
                        )
                        phase3_guard = SemanticDurabilityGuard(
                            barrier=barrier,
                            operations_store=operations,
                            publication_store=phase3_publication,
                            repository_id=candidate.repository.repository_id,
                            workflow_authority_digest=(workflow_authority.authority_digest),
                            provider=provider.provider.value,
                            expected_prior_state_head=state_head,
                            expected_prior_root_digest=state_root,
                            operations_run_id=discovery_authority.run_id,
                            request_reservation_hook=(
                                reserve_before_request if fixed_admission is not None else None
                            ),
                        )
                        clients: list[object] = []

                        def generator_factory() -> object:
                            client = (
                                OpenAIGenerationClient(
                                    model=profile.configured_generator_model_id,
                                    max_output_tokens=(profile.max_generator_output_tokens),
                                )
                                if provider.provider is SemanticProvider.OPENAI
                                else OpenAIGenerationClient(
                                    model=profile.configured_generator_model_id,
                                    max_output_tokens=(profile.max_generator_output_tokens),
                                    provider_settings=provider,
                                )
                            )
                            clients.append(client)
                            return client

                        def reviewer_factory() -> object:
                            client = (
                                OpenAIReviewClient(
                                    model=profile.configured_reviewer_model_id,
                                    max_output_tokens=(profile.max_reviewer_output_tokens),
                                )
                                if provider.provider is SemanticProvider.OPENAI
                                else OpenAIReviewClient(
                                    model=profile.configured_reviewer_model_id,
                                    max_output_tokens=(profile.max_reviewer_output_tokens),
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
                                    artifact_projector_factory=(LocalCandidateArtifactProjector),
                                    semantic_durability=phase3_guard,
                                ),
                            )
                            try:
                                result = application.run(
                                    descriptor_path,
                                    output_directory=Path(directory) / "output",
                                )
                            except SemanticProviderFailure as failure:
                                recover_phase3_success_telemetry(workflow_authority)
                                if (
                                    failure.disposition
                                    is SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN
                                ):
                                    workflow_outcomes.append("semantic_outcome_unknown")
                                    workflow_executions.append(
                                        DiscoveryWorkflowExecution(
                                            workflow_authority_digest=(
                                                workflow_authority.authority_digest
                                            ),
                                            outcome="semantic_outcome_unknown",
                                            workflow_fingerprint=(
                                                workflow_authority.selected_workflow_fingerprint
                                            ),
                                            workflow_spec_authority_digest=(
                                                workflow_authority.workflow_spec_authority.authority_digest
                                            ),
                                        )
                                    )
                                    state_head = phase3_guard.verified_state_head
                                    state_root = phase3_guard.state_root_digest
                                    continue
                                workflow_outcomes.append("permanent_failure")
                                workflow_executions.append(
                                    DiscoveryWorkflowExecution(
                                        workflow_authority_digest=(
                                            workflow_authority.authority_digest
                                        ),
                                        outcome="permanent_failure",
                                        workflow_fingerprint=(
                                            workflow_authority.selected_workflow_fingerprint
                                        ),
                                        workflow_spec_authority_digest=(
                                            workflow_authority.workflow_spec_authority.authority_digest
                                        ),
                                    )
                                )
                                fatal_outcome = "permanent_failure"
                                state_head = phase3_guard.verified_state_head
                                state_root = phase3_guard.state_root_digest
                                break
                            except SafeFailure as failure:
                                recover_phase3_success_telemetry(workflow_authority)
                                system_outcome, _reason_code = _phase3_safe_failure_outcome(
                                    failure.code
                                )
                                workflow_outcome = (
                                    "confirmed_retryable"
                                    if system_outcome == "provider_exhausted"
                                    else "permanent_failure"
                                )
                                workflow_outcomes.append(workflow_outcome)
                                workflow_executions.append(
                                    DiscoveryWorkflowExecution(
                                        workflow_authority_digest=(
                                            workflow_authority.authority_digest
                                        ),
                                        outcome=workflow_outcome,
                                        workflow_fingerprint=(
                                            workflow_authority.selected_workflow_fingerprint
                                        ),
                                        workflow_spec_authority_digest=(
                                            workflow_authority.workflow_spec_authority.authority_digest
                                        ),
                                    )
                                )
                                if system_outcome == "provider_exhausted":
                                    fatal_outcome = "confirmed_retryable"
                                    acceptance_system_outcome = system_outcome
                                else:
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
                        terminal_summary = result.terminal_summary or getattr(
                            result.completed_projection,
                            "terminal_summary",
                            None,
                        )
                        completed_projector = DescriptorAnchoredCompletedCandidateProjector(
                            config.pipeline_state
                        )
                        completed_projection = completed_projector.find_completed_candidate(
                            workflow_authority
                        )
                        if completed_projection is None:
                            raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                        generator_evidence = (
                            terminal_summary.generator_outcome_evidence
                            if terminal_summary is not None
                            else None
                        )
                        if generator_evidence is not None:
                            generator_attempts = tuple(
                                attempt
                                for attempt in completed_projection.chain.attempts
                                if attempt.stage.value == "generator"
                            )
                            if (
                                generator_evidence.actual_generator_model_id is None
                                or generator_evidence.request_id is None
                                or generator_evidence.usage is None
                                or not generator_attempts
                            ):
                                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                            semantic_telemetry.append(
                                DiscoverySemanticTelemetry(
                                    stage="generator",
                                    workflow_authority_digest=(workflow_authority.authority_digest),
                                    attempt_no=generator_attempts[-1].attempt_no,
                                    request_id=generator_evidence.request_id,
                                    actual_model=(generator_evidence.actual_generator_model_id),
                                    prompt_version=(generator_evidence.generator_prompt_version),
                                    schema_version=(
                                        generator_evidence.generator_output_schema_version
                                    ),
                                    policy_version=(generator_evidence.generator_policy_version),
                                    prompt_tokens=(generator_evidence.usage.prompt_tokens),
                                    completion_tokens=(generator_evidence.usage.completion_tokens),
                                    total_tokens=(generator_evidence.usage.total_tokens),
                                    latency_ms=generator_evidence.latency_ms,
                                )
                            )
                        review_payload = completed_projection.artifacts.get("review_attestation")
                        if review_payload is not None:
                            attestation = ReviewAttestationV1.model_validate_json(
                                review_payload,
                                strict=True,
                            )
                            reviewer_attempts = tuple(
                                attempt
                                for attempt in completed_projection.chain.attempts
                                if attempt.stage.value == "reviewer"
                            )
                            if (
                                attestation.request_id is None
                                or attestation.usage is None
                                or not reviewer_attempts
                            ):
                                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                            semantic_telemetry.append(
                                DiscoverySemanticTelemetry(
                                    stage="reviewer",
                                    workflow_authority_digest=(workflow_authority.authority_digest),
                                    attempt_no=reviewer_attempts[-1].attempt_no,
                                    request_id=attestation.request_id,
                                    actual_model=(attestation.actual_reviewer_model_id),
                                    prompt_version=(attestation.reviewer_prompt_version),
                                    schema_version=(attestation.reviewer_output_schema_version),
                                    policy_version=(attestation.reviewer_policy_version),
                                    prompt_tokens=attestation.usage.prompt_tokens,
                                    completion_tokens=(attestation.usage.completion_tokens),
                                    total_tokens=attestation.usage.total_tokens,
                                    latency_ms=attestation.latency_ms,
                                )
                            )
                        if (
                            result.outcome == "eligible_local_candidate"
                            and terminal_summary is not None
                        ):
                            terminal_bytes = candidate_terminal_summary_bytes(terminal_summary)
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
                                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                            locator = eligible_candidate_locator(
                                authority_digest=matching[0].object_digest,
                                workflow_identity_digest=(workflow_authority.authority_digest),
                            )
                            eligible.append(locator)
                            workflow_executions.append(
                                DiscoveryWorkflowExecution(
                                    workflow_authority_digest=(workflow_authority.authority_digest),
                                    outcome="eligible",
                                    workflow_fingerprint=(
                                        workflow_authority.selected_workflow_fingerprint
                                    ),
                                    workflow_spec_authority_digest=(
                                        workflow_authority.workflow_spec_authority.authority_digest
                                    ),
                                    phase3_terminal_summary_digest=(
                                        terminal_summary.terminal_summary_digest
                                    ),
                                    skill_artifact_digest=(
                                        terminal_summary.generated_artifact_identity.artifact_digest
                                    ),
                                    package_digest=(
                                        terminal_summary.package_identity.package_digest
                                    ),
                                    locator=locator,
                                )
                            )
                        else:
                            workflow_executions.append(
                                DiscoveryWorkflowExecution(
                                    workflow_authority_digest=(workflow_authority.authority_digest),
                                    outcome=result.outcome,
                                    workflow_fingerprint=(
                                        workflow_authority.selected_workflow_fingerprint
                                    ),
                                    workflow_spec_authority_digest=(
                                        workflow_authority.workflow_spec_authority.authority_digest
                                    ),
                                    phase3_terminal_summary_digest=(
                                        terminal_summary.terminal_summary_digest
                                        if terminal_summary is not None
                                        else None
                                    ),
                                    skill_artifact_digest=(
                                        terminal_summary.generated_artifact_identity.artifact_digest
                                        if terminal_summary is not None
                                        and terminal_summary.generated_artifact_identity is not None
                                        else None
                                    ),
                                    package_digest=(
                                        terminal_summary.package_identity.package_digest
                                        if terminal_summary is not None
                                        and terminal_summary.package_identity is not None
                                        else None
                                    ),
                                )
                            )
                if fatal_outcome is not None:
                    outcome = fatal_outcome
                    if fatal_outcome == "confirmed_retryable":
                        workflow_authorities = []
                        workflow_executions = []
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
                "discovery_run_authority_digest": (discovery_authority.authority_digest),
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
                semantic_telemetry=tuple(
                    sorted(
                        semantic_telemetry,
                        key=lambda item: (
                            item.stage,
                            item.workflow_authority_digest,
                            item.attempt_no,
                        ),
                    )
                ),
                reader_telemetry=reader_telemetry,
                acceptance_system_outcome=acceptance_system_outcome,
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
            durability_barrier=durability_barrier,
            phase2_factory=phase2_factory,
            phase3_factory=phase3_factory,
            query_set=config.query_set,  # type: ignore[arg-type]
            initial_state_root_digest=config.initial_state_root_digest,
        )
    )


class _LiveAcceptanceExecution:
    """Single closed action selected before any action-specific capability opens."""

    def __init__(self, action: str, execute: Callable[[], dict[str, object]]) -> None:
        if action not in {"benchmark", "replay"} or not callable(execute):
            raise ValueError("live acceptance execution rejected")
        self._action = action
        self._execute = execute

    def run(self) -> dict[str, object]:
        result = self._execute()
        expected = f"{self._action}_complete"
        if type(result) is not dict or result.get("status") != expected:
            raise ValueError("live acceptance execution result rejected")
        return result


class _CompletedBenchmarkStateProjector:
    """Measure the exact persisted campaign without opening a live capability."""

    def __init__(
        self,
        *,
        operations_path: Path,
        pipeline_path: Path,
        acceptance_run_id: str,
        expected_live_authority_digest: str,
        verified_state_locators: set[tuple[str, str]],
    ) -> None:
        if (
            type(verified_state_locators) is not set
            or not verified_state_locators
            or any(
                not _is_commit_sha(commit_sha) or not _is_digest(root_digest)
                for commit_sha, root_digest in verified_state_locators
            )
            or not _is_digest(expected_live_authority_digest)
        ):
            raise ValueError("completed benchmark state locators rejected")
        self._operations_path = operations_path
        self._pipeline_path = pipeline_path
        self._acceptance_run_id = acceptance_run_id
        self._expected_live_authority_digest = expected_live_authority_digest
        self._verified_state_locators = verified_state_locators

    def project(
        self,
        *,
        manifest: object,
        state_commit_sha: str,
        state_root_digest: str,
    ) -> object:
        if (
            state_commit_sha,
            state_root_digest,
        ) not in self._verified_state_locators:
            raise ValueError("completed benchmark state locator rejected")
        import json

        from skillscout.adapters.operations_state import OperationsStateStore
        from skillscout.adapters.state import SQLiteStateStore
        from skillscout.application.acceptance import CompletedBenchmarkProjection
        from skillscout.application.discovery import eligible_candidate_locator
        from skillscout.domain.acceptance import (
            AcceptanceScenarioResultV1,
            LockedBenchmarkManifestV1,
        )
        from skillscout.domain.review import CandidateTerminalSummaryV1

        if type(manifest) is not LockedBenchmarkManifestV1:
            raise ValueError("completed benchmark manifest rejected")
        with OperationsStateStore(self._operations_path) as operations:
            snapshot = operations.acceptance_snapshot(self._acceptance_run_id)
            operations_export = operations.export_owned_state()
        scenarios = tuple(
            record.fact
            for record in snapshot.facts
            if record.kind == "acceptance_scenario"
            and isinstance(record.fact, AcceptanceScenarioResultV1)
            and record.fact.benchmark_manifest_digest == manifest.manifest_digest
        )
        live_authorities = tuple(
            record.fact
            for record in snapshot.facts
            if record.kind == "acceptance_live_authority"
            and record.fact_digest == self._expected_live_authority_digest
        )
        if (
            len(scenarios) != 5
            or len(live_authorities) != 1
            or any(
                scenario.live_acceptance_authority_digest != self._expected_live_authority_digest
                for scenario in scenarios
            )
            or {scenario.repository_id for scenario in scenarios}
            != {entry.repository_id for entry in manifest.entries}
            or {
                (
                    scenario.repository_id,
                    scenario.repository_full_name,
                    scenario.exact_commit_sha,
                    scenario.license_spdx,
                    scenario.benchmark_entry_digest,
                )
                for scenario in scenarios
            }
            != {
                (
                    entry.repository_id,
                    entry.repository_full_name,
                    entry.exact_commit_sha,
                    entry.license_spdx,
                    entry.entry_digest,
                )
                for entry in manifest.entries
            }
            or any(scenario.terminal_class == "system_failure" for scenario in scenarios)
        ):
            raise ValueError("completed benchmark projection rejected")
        discovery_run_ids = {scenario.discovery_run_id for scenario in scenarios}
        if len(discovery_run_ids) != 1:
            raise ValueError("completed benchmark discovery authority rejected")
        with OperationsStateStore(self._operations_path) as operations:
            discovery_snapshot = operations.snapshot_run(next(iter(discovery_run_ids)))
        repository_ids = {scenario.repository_id for scenario in scenarios}
        semantic_attempt_digests = tuple(
            sorted(
                attempt.attempt_digest
                for attempt in discovery_snapshot.semantic_attempts
                if attempt.repository_id in repository_ids
            )
        )
        workflow_terminal_digests = tuple(
            sorted(
                terminal.terminal_digest
                for terminal in discovery_snapshot.workflow_terminals
                if terminal.repository_id in repository_ids
            )
        )
        workflow_execution_authorities = {
            terminal.workflow_authority_digest
            for terminal in discovery_snapshot.workflow_terminals
            if terminal.repository_id in repository_ids
        }
        candidate_terminal_digests = tuple(
            sorted(
                terminal.terminal_digest
                for terminal in discovery_snapshot.candidate_terminals
                if terminal.repository_id in repository_ids
            )
        )
        if (
            semantic_attempt_digests
            != tuple(
                sorted(
                    digest for scenario in scenarios for digest in scenario.semantic_attempt_digests
                )
            )
            or workflow_terminal_digests
            != tuple(
                sorted(
                    digest
                    for scenario in scenarios
                    for digest in scenario.workflow_terminal_digests
                )
            )
            or workflow_execution_authorities
            != {
                digest
                for scenario in scenarios
                for digest in scenario.workflow_execution_authority_digests
            }
            or candidate_terminal_digests
            != tuple(sorted(scenario.candidate_terminal_digest for scenario in scenarios))
        ):
            raise ValueError("completed benchmark operations graph rejected")
        eligible = tuple(
            scenario
            for scenario in scenarios
            if scenario.terminal_class == "eligible"
            and scenario.workflow_fingerprint is not None
            and scenario.workflow_spec_authority_digest is not None
            and scenario.eligible_locator is not None
        )
        if not eligible:
            raise ValueError("completed benchmark has no value-positive scenario")
        selected = sorted(eligible, key=lambda item: item.repository_id)[0]
        pipeline = SQLiteStateStore(self._pipeline_path)
        try:
            pipeline_export = pipeline.export_owned_state()
            completed_chains = []
            terminal_objects = []
            for owned_fact in pipeline_export.facts:
                if owned_fact.kind not in {
                    "phase3_runs",
                    "phase3_artifact",
                }:
                    continue
                envelope = json.loads(owned_fact.payload_json)
                if owned_fact.kind == "phase3_runs":
                    try:
                        columns = envelope["columns"]
                        values = envelope["values"]
                        if (
                            envelope["schema_version"] != "pipeline-rebuild-row-v1"
                            or type(columns) is not list
                            or type(values) is not list
                            or len(columns) != len(values)
                            or any(type(column) is not str for column in columns)
                        ):
                            raise ValueError
                        raw = dict(zip(columns, values, strict=True))
                    except Exception:
                        raise ValueError("completed benchmark pipeline fact rejected") from None
                else:
                    raw = envelope
                if owned_fact.kind == "phase3_runs":
                    if raw.get("status") != "completed":
                        continue
                    run_id = raw.get("run_id")
                    if type(run_id) is not str:
                        raise ValueError("completed benchmark typed Phase 3 run rejected")
                    chain = pipeline.verify_candidate_run_chain(run_id)
                    if (
                        raw.get("authority_digest")
                        != chain.identity.candidate_execution_authority_digest
                    ):
                        raise ValueError("completed benchmark typed Phase 3 authority rejected")
                    completed_chains.append(chain)
                elif owned_fact.kind == "phase3_artifact":
                    try:
                        content = base64.b64decode(
                            raw["content_base64"],
                            validate=True,
                        )
                        terminal = CandidateTerminalSummaryV1.model_validate_json(
                            content,
                            strict=True,
                        )
                    except Exception:
                        continue
                    terminal_objects.append((owned_fact, terminal))
        finally:
            pipeline.close()
        if workflow_execution_authorities and (not completed_chains or not terminal_objects):
            raise ValueError("completed benchmark typed Phase 3 objects are missing")
        chain_authorities = {
            chain.identity.candidate_execution_authority_digest for chain in completed_chains
        }
        terminal_objects = tuple(
            (owned_fact, terminal)
            for owned_fact, terminal in terminal_objects
            if terminal.candidate_execution_authority.authority_digest
            in workflow_execution_authorities
        )
        if (
            any(
                terminal.candidate_execution_authority.authority_digest not in chain_authorities
                for _owned_fact, terminal in terminal_objects
            )
            or {
                terminal.candidate_execution_authority.authority_digest
                for _owned_fact, terminal in terminal_objects
            }
            != workflow_execution_authorities
        ):
            raise ValueError("completed benchmark typed Phase 3 terminal is unbound")
        typed_workflow_authorities = {
            terminal.workflow_spec_authority.authority_digest
            for _owned_fact, terminal in terminal_objects
        }
        scenario_workflow_spec_authorities = {
            digest for scenario in scenarios for digest in scenario.workflow_spec_authority_digests
        }
        phase3_terminal_digests = {
            terminal.terminal_summary_digest for _owned_fact, terminal in terminal_objects
        }
        phase3_skill_digests = {
            terminal.generated_artifact_identity.artifact_digest
            for _owned_fact, terminal in terminal_objects
            if terminal.generated_artifact_identity is not None
        }
        phase3_package_digests = {
            terminal.package_identity.package_digest
            for _owned_fact, terminal in terminal_objects
            if terminal.package_identity is not None
        }
        if (
            scenario_workflow_spec_authorities != typed_workflow_authorities
            or {
                digest
                for scenario in scenarios
                for digest in scenario.phase3_terminal_summary_digests
            }
            != phase3_terminal_digests
            or {digest for scenario in scenarios for digest in scenario.skill_artifact_digests}
            != phase3_skill_digests
            or {digest for scenario in scenarios for digest in scenario.package_digests}
            != phase3_package_digests
        ):
            raise ValueError("completed benchmark typed Phase 3 graph is missing")
        matching_eligible_objects = tuple(
            (owned_fact, terminal)
            for owned_fact, terminal in terminal_objects
            if terminal.eligible
            and terminal.workflow_spec_authority.authority_digest
            == selected.workflow_spec_authority_digest
            and eligible_candidate_locator(
                authority_digest=owned_fact.object_digest,
                workflow_identity_digest=(terminal.workflow_spec_authority.authority_digest),
            ).locator
            == selected.eligible_locator
        )
        if len(matching_eligible_objects) != 1:
            raise ValueError("completed benchmark typed Phase 3 eligible object is missing")
        workflow_authority_digests = tuple(sorted(typed_workflow_authorities))
        candidate_fact_digests = tuple(sorted(fact.object_digest for fact in pipeline_export.facts))
        acceptance_business_fact_digests = tuple(
            sorted(
                record.fact_digest
                for record in snapshot.facts
                if record.kind not in {"acceptance_replay", "acceptance_replay_evidence"}
            )
        )
        operations_fact_digests = tuple(
            sorted(
                fact.object_digest
                for fact in operations_export.facts
                if fact.kind not in {"acceptance_replay", "acceptance_replay_evidence"}
            )
        )
        skill_identity_digests = tuple(
            sorted(
                {
                    digest
                    for _owned_fact, terminal in terminal_objects
                    for digest in (
                        (
                            terminal.generated_artifact_identity.artifact_digest
                            if terminal.generated_artifact_identity is not None
                            else None
                        ),
                        (
                            terminal.package_identity.package_digest
                            if terminal.package_identity is not None
                            else None
                        ),
                    )
                    if digest is not None
                }
            )
        )
        if not skill_identity_digests:
            raise ValueError("completed benchmark typed Phase 3 skill identity is missing")
        return CompletedBenchmarkProjection(
            manifest_digest=manifest.manifest_digest,
            scenario_result_digests=tuple(sorted(scenario.result_digest for scenario in scenarios)),
            repository_id=selected.repository_id,
            source_commit_sha=selected.exact_commit_sha,
            workflow_fingerprint=selected.workflow_fingerprint,
            workflow_spec_authority_digest=(selected.workflow_spec_authority_digest),
            eligible_locators=tuple(
                sorted(
                    scenario.eligible_locator
                    for scenario in eligible
                    if scenario.eligible_locator is not None
                )
            ),
            semantic_attempt_count=len(semantic_attempt_digests),
            semantic_attempt_digests=semantic_attempt_digests,
            workflow_spec_authority_digests=workflow_authority_digests,
            skill_identity_digests=skill_identity_digests,
            candidate_fact_digests=candidate_fact_digests,
            acceptance_business_fact_digests=(acceptance_business_fact_digests),
            operations_fact_digests=operations_fact_digests,
            semantic_request_count=sum(scenario.semantic_request_count for scenario in scenarios),
        )

    def close(self) -> None:
        return None


def _acceptance_reason_code(outcome: str) -> str:
    reasons = {
        "filter_rejected": "deterministic_filter_rejected",
        "no_workflow": "no_reusable_workflow",
        "qualification_rejected": "qualification_policy_rejected",
        "validation_rejected": "skill_validation_rejected",
        "review_rejected": "independent_review_rejected",
        "eligible_local_candidate": "eligible_candidate_completed",
        "provider_exhausted": "provider_attempts_exhausted",
        "schema_exhausted": "provider_schema_exhausted",
        "evidence_missing": "state_integrity_conflict",
        "duplicate_effect": "duplicate_effect_observed",
        "unauthorized_effect": "unauthorized_effect_observed",
        "secret_exposure": "secret_exposure_observed",
        "untrusted_execution": "untrusted_execution_observed",
        "harness_failed": "pipeline_permanent_failure",
        "rebuild_failed": "state_rebuild_failed",
    }
    try:
        return reasons[outcome]
    except KeyError:
        raise ValueError("unsupported normalized acceptance outcome") from None


def _phase3_safe_failure_outcome(error_code: object) -> tuple[str, str]:
    """Normalize Phase 3 system failures without converting exhaustion to harness."""

    from skillscout.application.ports import ErrorCode

    if error_code is ErrorCode.RETRY_EXHAUSTED:
        return "provider_exhausted", "provider_attempts_exhausted"
    return "harness_failed", "pipeline_permanent_failure"


class _FixedRepositoryAcceptanceRunner:
    """Run one locked identity through the existing production Phase 2/3 graph."""

    def __init__(
        self,
        *,
        config: AcceptanceRuntimeConfig,
        discovery_config: DiscoveryRuntimeConfig,
        barrier: object,
        source: Mapping[str, str],
        frozen_owner_export: object,
        acceptance_run_id: str,
    ) -> None:
        from skillscout.adapters.operations_state import (
            OperationsStateStore,
            _schema_fingerprint,
        )
        from skillscout.domain.acceptance import LiveAcceptanceAuthorityV2
        from skillscout.domain.canonical import sha256_digest
        from skillscout.domain.discovery import DiscoveryBudgetPolicyV1, DiscoveryRunAuthorityV1

        self._config = config
        self._discovery_config = discovery_config
        self._barrier = barrier
        self._source = source
        operations = OperationsStateStore(discovery_config.operations_state)
        try:
            if operations.export_owned_state().schema_fingerprint != _schema_fingerprint():
                raise ValueError("acceptance operations schema is not current")
        except Exception:
            operations.close()
            raise
        self._operations = operations
        self._acceptance_run_id = acceptance_run_id
        authority_records = tuple(
            record.fact
            for record in self._operations.acceptance_snapshot(acceptance_run_id).facts
            if record.kind == "acceptance_live_authority"
            and record.fact_digest == config.live_acceptance_authority_digest
        )
        if len(authority_records) != 1:
            raise ValueError("live acceptance authority is missing")
        self._live_authority = authority_records[0]
        if type(self._live_authority) is not LiveAcceptanceAuthorityV2:
            raise ValueError("fresh V2 live acceptance authority is required")
        if (
            self._live_authority.manifest_digest != config.manifest.manifest_digest
            or self._live_authority.semantic_provider != config.semantic_provider
            or self._live_authority.stage_models
            != (
                config.extractor_model_id,
                config.generator_model_id,
                config.reviewer_model_id,
            )
        ):
            raise ValueError("live acceptance runtime authority mismatch")
        application = build_discovery_application(
            discovery_config,
            environ=source,
            frozen_owner_export=frozen_owner_export,
        )
        (
            self._phase2_factory,
            self._phase3_factory,
            _unused_barrier,
        ) = application.candidate_execution_graph()
        run_id = f"{acceptance_run_id}-semantic"
        budget = DiscoveryBudgetPolicyV1()
        authority_values = {
            "schema_version": "discovery-run-authority-v1",
            "run_id": run_id,
            "query_set_digest": discovery_config.query_set_digest,
            "budget_policy_digest": budget.budget_policy_digest,
            "phase2_profile_version": discovery_config.phase2_profile_version,
            "phase3_profile_version": discovery_config.phase3_profile_version,
            "semantic_provider": discovery_config.semantic_provider,
            "extractor_model_id": discovery_config.extractor_model_id,
            "generator_model_id": discovery_config.generator_model_id,
            "reviewer_model_id": discovery_config.reviewer_model_id,
            "initial_state_root_digest": self._live_authority.state_root_digest,
        }
        self._authority = DiscoveryRunAuthorityV1(
            **authority_values,
            authority_digest=sha256_digest(authority_values),
        )
        self._operations.create_run(self._authority, _discovery_timestamp())
        self._state_head = config.state_commit_sha
        self._state_root = config.state_root_digest
        configure_resume = getattr(
            self._barrier,
            "configure_acceptance_resume",
            None,
        )
        if not callable(configure_resume) and config.acceptance_run_id is None:
            resume_commits = ()
            resume_roots = ()
        elif config.acceptance_run_id is not None:
            if config.acceptance_run_id != acceptance_run_id:
                raise ValueError("acceptance resume run mismatch")
            resume_commits = config.resume_lineage_commit_shas
            resume_roots = config.resume_lineage_root_digests
        elif (
            config.state_commit_sha == self._live_authority.state_commit_sha
            and config.state_root_digest == self._live_authority.state_root_digest
        ):
            resume_commits = (config.state_commit_sha,)
            resume_roots = (config.state_root_digest,)
        else:
            raise ValueError("verified acceptance resume proof is required")
        if callable(configure_resume):
            configure_resume(
                authority=self._live_authority,
                acceptance_run_id=acceptance_run_id,
                lineage_commit_shas=resume_commits,
                lineage_root_digests=resume_roots,
                locator_digest=config.resume_locator_digest,
                transition_index=config.resume_transition_index,
            )
        elif config.acceptance_run_id is not None:
            raise ValueError("acceptance resume barrier is unavailable")

    def _run_phase2_with_retries(
        self,
        *,
        candidate: object,
        pinned_commit_sha: str,
    ) -> object:
        """Resume only confirmed retryable work under the Phase 2 policy cap."""

        from skillscout.application.pipeline import RetryPolicy

        repository_id = candidate.repository.repository_id
        snapshot = self._operations.snapshot_run(self._authority.run_id)
        reservations = tuple(
            item for item in snapshot.semantic_reservations if item.repository_id == repository_id
        )
        if len(reservations) > 1:
            raise ValueError("fixed acceptance semantic reservation conflict")
        phase2_authority = reservations[0].phase2_run_authority_digest if reservations else None
        prior_attempts = tuple(
            item
            for item in snapshot.semantic_attempts
            if item.repository_id == repository_id
            and item.stage == "extractor"
            and (phase2_authority is None or item.workflow_authority_digest == phase2_authority)
        )
        prior_attempt_count = max(
            (item.attempt_no for item in prior_attempts),
            default=0,
        )
        remaining_attempts = RetryPolicy().max_attempts - prior_attempt_count
        if remaining_attempts < 0:
            raise ValueError("fixed acceptance semantic retry ledger exceeded")
        execution = None
        for _attempt in range(remaining_attempts):
            execution = self._phase2_factory(
                candidate=candidate,
                discovery_authority=self._authority,
                operations_store=self._operations,
                durability_barrier=self._barrier,
                observed_head=self._state_head,
                prior_root_digest=self._state_root,
                phase3_factory=self._phase3_factory,
                pinned_commit_sha=pinned_commit_sha,
            )
            self._state_head = execution.state_commit_sha
            self._state_root = execution.state_root_digest
            if (
                getattr(execution, "acceptance_system_outcome", None) == "provider_exhausted"
                or execution.terminal.outcome != "confirmed_retryable"
            ):
                break
        if execution is None:
            execution = self._phase2_factory(
                candidate=candidate,
                discovery_authority=self._authority,
                operations_store=self._operations,
                durability_barrier=self._barrier,
                observed_head=self._state_head,
                prior_root_digest=self._state_root,
                phase3_factory=self._phase3_factory,
                pinned_commit_sha=pinned_commit_sha,
                recovery_only=True,
            )
            self._state_head = execution.state_commit_sha
            self._state_root = execution.state_root_digest
        return execution

    def run(self, authority: object) -> object:
        from skillscout.adapters.github import GitHubReadClient
        from skillscout.application.acceptance import (
            FixedAcceptanceCandidate,
            LiveRepositoryAuthority,
            LiveScenarioObservation,
        )
        from skillscout.domain.acceptance import (
            AcceptanceBudgetReservationV1,
            AcceptanceFixedCandidateAdmissionV1,
            AcceptanceSemanticTelemetryV1,
            NominationSetV1,
        )
        from skillscout.domain.canonical import sha256_digest
        from skillscout.domain.discovery import SearchRepositoryObservationV1

        if type(authority) is not LiveRepositoryAuthority:
            raise ValueError("locked repository authority rejected")
        snapshot = self._operations.acceptance_snapshot(self._acceptance_run_id)
        nominations = tuple(
            record.fact
            for record in snapshot.facts
            if record.kind == "acceptance_nomination"
            and record.fact_digest == self._config.manifest.nomination_set_digest
            and isinstance(record.fact, NominationSetV1)
        )
        if len(nominations) != 1:
            raise ValueError("locked repository nomination missing")
        nominated = tuple(
            entry
            for entry in (
                nominations[0].search_derived_entries + nominations[0].user_nominated_entries
            )
            if entry.entry_digest == authority.nomination_entry_digest
        )
        if (
            len(nominated) != 1
            or nominated[0].selection_source != "search_derived"
            or (
                nominated[0].repository_full_name,
                nominated[0].repository_id,
                nominated[0].exact_commit_sha,
                nominated[0].license_spdx,
                nominated[0].selection_evidence_digests,
            )
            != (
                authority.repository_full_name,
                authority.repository_id,
                authority.exact_commit_sha,
                authority.license_spdx,
                authority.selection_evidence_digests,
            )
        ):
            raise ValueError("locked repository nomination mismatch")
        matching_entries = tuple(
            (ordinal, entry)
            for ordinal, entry in enumerate(
                self._config.manifest.entries,
                start=1,
            )
            if entry.entry_digest == authority.entry_digest
        )
        if len(matching_entries) != 1:
            raise ValueError("locked repository manifest entry missing")
        ordinal = matching_entries[0][0]
        existing_budget = tuple(
            record.fact
            for record in snapshot.facts
            if record.kind == "acceptance_budget_reservation"
            and record.fact.benchmark_entry_digest == authority.entry_digest
        )
        if len(existing_budget) > 1:
            raise ValueError("locked repository budget reservation conflict")
        budget_reservation = AcceptanceBudgetReservationV1(
            schema_version="acceptance-budget-reservation-v1",
            acceptance_run_id=self._acceptance_run_id,
            benchmark_manifest_digest=self._config.manifest.manifest_digest,
            nomination_entry_digest=authority.nomination_entry_digest,
            benchmark_entry_digest=authority.entry_digest,
            repository_id=authority.repository_id,
            repository_full_name=authority.repository_full_name,
            ordinal=ordinal,
            max_files=25,
            max_source_files=5,
            max_file_bytes=131_072,
            max_total_bytes=524_288,
            max_estimated_tokens=40_000,
            semantic_candidate_slots=1,
            campaign_semantic_request_limit=20,
            reserved_at=_discovery_timestamp(),
        )
        if existing_budget:
            budget_reservation = existing_budget[0]
        else:
            budget_reservation = self._operations.record_acceptance_fact(
                self._acceptance_run_id,
                "acceptance_budget_reservation",
                budget_reservation,
            ).fact
            synchronized = self._barrier.sync_discovery(
                operations_store=self._operations,
                observed_head=self._state_head,
                prior_root_digest=self._state_root,
                created_at=_discovery_timestamp(),
                transition_phase="budget_reserved",
            )
            self._state_head = synchronized.commit_sha
            self._state_root = synchronized.root_digest
        owner, repository_name = authority.repository_full_name.split("/")
        github = GitHubReadClient(
            token=_required_credential(
                self._source,
                "SKILLSCOUT_SOURCE_GITHUB_TOKEN",
            )
        )
        try:
            metadata = github.get_repo_metadata(owner, repository_name)
            commit_sha = github.resolve_commit(
                owner,
                repository_name,
                authority.exact_commit_sha,
            )
            license_observation = github.get_license(
                owner,
                repository_name,
                authority.exact_commit_sha,
            )
        finally:
            github.close()
        if (
            metadata.id != authority.repository_id
            or f"{metadata.owner}/{metadata.name}" != authority.repository_full_name
            or metadata.private
            or metadata.visibility != "public"
            or metadata.fork
            or metadata.archived
            or metadata.disabled
            or commit_sha != authority.exact_commit_sha
            or license_observation.status != "confirmed"
            or license_observation.spdx_id != authority.license_spdx
        ):
            raise ValueError("locked repository live admission mismatch")
        repository_values = {
            "schema_version": "search-repository-observation-v1",
            "repository_id": metadata.id,
            "owner": metadata.owner,
            "name": metadata.name,
            "full_name": authority.repository_full_name,
            "private": metadata.private,
            "visibility": metadata.visibility,
            "fork": metadata.fork,
            "archived": metadata.archived,
            "disabled": metadata.disabled,
            "default_branch": metadata.default_branch,
        }
        repository = SearchRepositoryObservationV1(
            **repository_values,
            observation_digest=sha256_digest(repository_values),
        )
        admission = AcceptanceFixedCandidateAdmissionV1(
            schema_version="acceptance-fixed-candidate-admission-v1",
            acceptance_run_id=self._acceptance_run_id,
            benchmark_manifest_digest=self._config.manifest.manifest_digest,
            nomination_entry_digest=authority.nomination_entry_digest,
            benchmark_entry_digest=authority.entry_digest,
            repository_id=authority.repository_id,
            repository_full_name=authority.repository_full_name,
            exact_commit_sha=authority.exact_commit_sha,
            license_spdx=authority.license_spdx,
            ordinal=ordinal,
            admitted_at=_discovery_timestamp(),
        )
        existing_admissions = tuple(
            record.fact
            for record in snapshot.facts
            if record.kind == "acceptance_fixed_candidate_admission"
            and record.fact.benchmark_entry_digest == authority.entry_digest
        )
        if len(existing_admissions) > 1:
            raise ValueError("locked repository candidate admission conflict")
        if existing_admissions:
            admission = existing_admissions[0]
        else:
            admission = self._operations.record_acceptance_fact(
                self._acceptance_run_id,
                "acceptance_fixed_candidate_admission",
                admission,
            ).fact
        candidate = FixedAcceptanceCandidate(
            repository=repository,
            admission=admission,
        )
        if not existing_admissions:
            synchronized = self._barrier.sync_discovery(
                operations_store=self._operations,
                observed_head=self._state_head,
                prior_root_digest=self._state_root,
                created_at=_discovery_timestamp(),
                transition_phase="candidate_admitted",
            )
            self._state_head = synchronized.commit_sha
            self._state_root = synchronized.root_digest
        execution = self._run_phase2_with_retries(
            candidate=candidate,
            pinned_commit_sha=authority.exact_commit_sha,
        )
        persisted_execution = self._operations.snapshot_run(self._authority.run_id)
        existing_workflow_terminals = {
            item.workflow_authority_digest: item
            for item in persisted_execution.workflow_terminals
            if item.repository_id == authority.repository_id
        }
        if len(existing_workflow_terminals) != sum(
            item.repository_id == authority.repository_id
            for item in persisted_execution.workflow_terminals
        ):
            raise ValueError("acceptance workflow terminal conflict")
        workflow_terminals = []
        terminal_changed = False
        for workflow in execution.workflows:
            terminal_outcome = (
                "eligible_local_candidate" if workflow.outcome == "eligible" else workflow.outcome
            )
            terminal_locator = workflow.locator.locator if workflow.locator is not None else None
            terminal_object_digest = (
                workflow.locator.authority_digest if workflow.locator is not None else None
            )
            existing_terminal = existing_workflow_terminals.get(workflow.workflow_authority_digest)
            if existing_terminal is not None:
                if (
                    existing_terminal.run_id,
                    existing_terminal.repository_id,
                    existing_terminal.workflow_authority_digest,
                    existing_terminal.outcome,
                    existing_terminal.eligible_locator,
                    existing_terminal.eligible_object_digest,
                ) != (
                    self._authority.run_id,
                    authority.repository_id,
                    workflow.workflow_authority_digest,
                    terminal_outcome,
                    terminal_locator,
                    terminal_object_digest,
                ):
                    raise ValueError("acceptance workflow terminal conflict")
                workflow_terminals.append(existing_terminal)
            else:
                workflow_terminals.append(
                    self._operations.record_acceptance_workflow_terminal(
                        acceptance_run_id=self._acceptance_run_id,
                        fixed_candidate_admission_digest=admission.admission_digest,
                        semantic_reservation_digest=(
                            execution.terminal.semantic_reservation_digest
                        ),
                        run_id=self._authority.run_id,
                        repository_id=authority.repository_id,
                        workflow_authority_digest=workflow.workflow_authority_digest,
                        outcome=terminal_outcome,
                        eligible_locator=terminal_locator,
                        eligible_object_digest=terminal_object_digest,
                        recorded_at=_discovery_timestamp(),
                    )
                )
                terminal_changed = True
        existing_candidate_terminals = tuple(
            item
            for item in persisted_execution.candidate_terminals
            if item.repository_id == authority.repository_id
        )
        if len(existing_candidate_terminals) > 1:
            raise ValueError("acceptance candidate terminal conflict")
        if existing_candidate_terminals:
            candidate_terminal = existing_candidate_terminals[0]
            if (
                candidate_terminal.discovery_run_authority_digest,
                candidate_terminal.repository_id,
                candidate_terminal.semantic_reservation_digest,
                candidate_terminal.outcome,
                candidate_terminal.workflow_authority_digests,
            ) != (
                execution.terminal.discovery_run_authority_digest,
                execution.terminal.repository_id,
                execution.terminal.semantic_reservation_digest,
                execution.terminal.outcome,
                execution.terminal.workflow_authority_digests,
            ):
                raise ValueError("acceptance candidate terminal conflict")
        else:
            candidate_terminal = self._operations.record_candidate_terminal(
                self._authority.run_id,
                execution.terminal,
            )
            terminal_changed = True
        if terminal_changed:
            synchronized = self._barrier.sync_discovery(
                operations_store=self._operations,
                observed_head=self._state_head,
                prior_root_digest=self._state_root,
                created_at=_discovery_timestamp(),
                transition_phase="terminal",
            )
            self._state_head = synchronized.commit_sha
            self._state_root = synchronized.root_digest
        operations_snapshot = self._operations.snapshot_run(self._authority.run_id)
        semantic_attempts = tuple(
            attempt
            for attempt in operations_snapshot.semantic_attempts
            if attempt.repository_id == authority.repository_id
        )
        semantic_reservations = tuple(
            reservation
            for reservation in operations_snapshot.semantic_reservations
            if reservation.repository_id == authority.repository_id
        )
        acceptance_snapshot = self._operations.acceptance_snapshot(self._acceptance_run_id)
        request_reservations = tuple(
            record
            for record in acceptance_snapshot.facts
            if record.kind == "acceptance_semantic_request_reservation"
            and record.fact.repository_id == authority.repository_id
            and record.fact.fixed_candidate_admission_digest == admission.admission_digest
        )
        telemetry_keys = {
            (
                item.stage,
                item.workflow_authority_digest,
                item.attempt_no,
            )
            for item in execution.semantic_telemetry
        }
        attempt_keys = {
            (
                item.stage,
                item.workflow_authority_digest,
                item.attempt_no,
            )
            for item in semantic_attempts
        }
        if not telemetry_keys.issubset(attempt_keys) or any(
            attempt.status == "decided"
            and (
                attempt.stage,
                attempt.workflow_authority_digest,
                attempt.attempt_no,
            )
            not in telemetry_keys
            for attempt in semantic_attempts
        ):
            raise ValueError("semantic provider telemetry is incomplete")
        semantic_telemetry = tuple(
            AcceptanceSemanticTelemetryV1(
                schema_version="acceptance-semantic-telemetry-v1",
                live_acceptance_authority_digest=(self._live_authority.authority_digest),
                stage=item.stage,
                workflow_spec_authority_digest=(item.workflow_authority_digest),
                attempt_no=item.attempt_no,
                request_id=item.request_id,
                actual_model=item.actual_model,
                prompt_version=item.prompt_version,
                output_schema_version=item.schema_version,
                policy_version=item.policy_version,
                prompt_tokens=item.prompt_tokens,
                completion_tokens=item.completion_tokens,
                total_tokens=item.total_tokens,
                latency_ms=item.latency_ms,
            )
            for item in execution.semantic_telemetry
        )
        workflows = execution.workflows
        selected_workflow = next(
            (workflow for workflow in workflows if workflow.locator is not None),
            workflows[0] if workflows else None,
        )
        workflow_execution_authority_digests = tuple(
            sorted(item.workflow_authority_digest for item in workflows)
        )
        workflow_spec_authority_digests = tuple(
            sorted(
                item.workflow_spec_authority_digest
                for item in workflows
                if item.workflow_spec_authority_digest is not None
                and item.phase3_terminal_summary_digest is not None
            )
        )
        phase3_terminal_summary_digests = tuple(
            sorted(
                item.phase3_terminal_summary_digest
                for item in workflows
                if item.phase3_terminal_summary_digest is not None
            )
        )
        skill_artifact_digests = tuple(
            sorted(
                item.skill_artifact_digest
                for item in workflows
                if item.skill_artifact_digest is not None
            )
        )
        package_digests = tuple(
            sorted(item.package_digest for item in workflows if item.package_digest is not None)
        )
        evidence = {
            self._live_authority.authority_digest,
            self._config.manifest.manifest_digest,
            authority.nomination_entry_digest,
            authority.entry_digest,
            budget_reservation.reservation_digest,
            admission.admission_digest,
            candidate_terminal.terminal_digest,
            *(item.reservation_digest for item in semantic_reservations),
            *(record.fact_digest for record in request_reservations),
            *(attempt.attempt_digest for attempt in semantic_attempts),
            *workflow_execution_authority_digests,
            *workflow_spec_authority_digests,
            *phase3_terminal_summary_digests,
            *skill_artifact_digests,
            *package_digests,
            *(terminal.terminal_digest for terminal in workflow_terminals),
            *(
                terminal.eligible_object_digest
                for terminal in workflow_terminals
                if terminal.eligible_object_digest is not None
            ),
        }
        acceptance_outcome = execution.acceptance_system_outcome or {
            "confirmed_retryable": "provider_exhausted",
            "semantic_outcome_unknown": "provider_exhausted",
            "state_integrity_conflict": "evidence_missing",
            "permanent_failure": "harness_failed",
        }.get(execution.terminal.outcome, execution.terminal.outcome)
        return LiveScenarioObservation(
            repository_id=authority.repository_id,
            repository_full_name=authority.repository_full_name,
            exact_commit_sha=authority.exact_commit_sha,
            license_spdx=authority.license_spdx,
            outcome=acceptance_outcome,
            reason_code=_acceptance_reason_code(acceptance_outcome),
            evidence_digests=tuple(sorted(evidence)),
            live_acceptance_authority_digest=(self._live_authority.authority_digest),
            discovery_run_id=self._authority.run_id,
            discovery_run_authority_digest=self._authority.authority_digest,
            benchmark_entry_digest=authority.entry_digest,
            budget_reservation_digest=(budget_reservation.reservation_digest),
            fixed_candidate_admission_digest=admission.admission_digest,
            semantic_candidate_reservation_digest=(
                semantic_reservations[0].reservation_digest
                if len(semantic_reservations) == 1
                else None
            ),
            semantic_request_reservation_digests=tuple(
                sorted(record.fact_digest for record in request_reservations)
            ),
            candidate_terminal_digest=candidate_terminal.terminal_digest,
            workflow_terminal_digests=tuple(
                sorted(terminal.terminal_digest for terminal in workflow_terminals)
            ),
            workflow_execution_authority_digests=(workflow_execution_authority_digests),
            workflow_spec_authority_digests=(workflow_spec_authority_digests),
            phase3_terminal_summary_digests=(phase3_terminal_summary_digests),
            skill_artifact_digests=skill_artifact_digests,
            package_digests=package_digests,
            eligible_object_digest=(
                selected_workflow.locator.authority_digest
                if selected_workflow is not None and selected_workflow.locator is not None
                else None
            ),
            workflow_fingerprint=(
                selected_workflow.workflow_fingerprint if selected_workflow is not None else None
            ),
            workflow_spec_authority_digest=(
                selected_workflow.workflow_spec_authority_digest
                if selected_workflow is not None
                else None
            ),
            eligible_locator=(
                selected_workflow.locator.locator
                if selected_workflow is not None and selected_workflow.locator is not None
                else None
            ),
            semantic_request_count=len(semantic_attempts),
            semantic_attempt_digests=tuple(
                sorted(attempt.attempt_digest for attempt in semantic_attempts)
            ),
            semantic_telemetry=semantic_telemetry,
            actual_models=tuple(item.actual_model for item in semantic_telemetry),
            reader_file_count=(
                execution.reader_telemetry.file_count
                if execution.reader_telemetry is not None
                else 0
            ),
            reader_source_file_count=(
                execution.reader_telemetry.source_file_count
                if execution.reader_telemetry is not None
                else 0
            ),
            reader_total_bytes=(
                execution.reader_telemetry.total_bytes
                if execution.reader_telemetry is not None
                else 0
            ),
            reader_estimated_tokens=(
                execution.reader_telemetry.estimated_tokens
                if execution.reader_telemetry is not None
                else 0
            ),
            state_commit_sha=self._state_head,
            state_root_digest=self._state_root,
        )

    def close(self) -> None:
        self._operations.close()


def _fixed_acceptance_runner_factory(
    *,
    config: AcceptanceRuntimeConfig,
    discovery_config: DiscoveryRuntimeConfig,
    restored: object,
    barrier: object,
    source: Mapping[str, str],
    frozen_owner_export: object,
    acceptance_run_id: str,
) -> Callable[[str, str], object]:
    del restored
    resume_configured = False

    def factory(state_commit_sha: str, state_root_digest: str) -> object:
        nonlocal resume_configured
        lineage_reader = getattr(
            barrier,
            "acceptance_resume_lineage",
            None,
        )
        if resume_configured and callable(lineage_reader):
            resume_commits, resume_roots = lineage_reader()
        else:
            resume_commits = config.resume_lineage_commit_shas
            resume_roots = config.resume_lineage_root_digests
        locator_reader = getattr(
            barrier,
            "acceptance_resume_locator",
            None,
        )
        if resume_configured and callable(locator_reader):
            resume_locator_digest, resume_transition_index = locator_reader()
        else:
            resume_locator_digest = config.resume_locator_digest
            resume_transition_index = config.resume_transition_index
        runner = _FixedRepositoryAcceptanceRunner(
            config=replace(
                config,
                state_commit_sha=state_commit_sha,
                state_root_digest=state_root_digest,
                resume_lineage_commit_shas=resume_commits,
                resume_lineage_root_digests=resume_roots,
                resume_locator_digest=resume_locator_digest,
                resume_transition_index=resume_transition_index,
            ),
            discovery_config=discovery_config,
            barrier=barrier,
            source=source,
            frozen_owner_export=frozen_owner_export,
            acceptance_run_id=acceptance_run_id,
        )
        resume_configured = True
        return runner

    return factory


def _acceptance_discovery_config(
    config: AcceptanceRuntimeConfig,
    source: Mapping[str, str],
) -> DiscoveryRuntimeConfig:
    from skillscout.domain.discovery import DiscoveryQuerySetV1

    query_path = Path("config") / _DISCOVERY_QUERY_SET_NAME
    query_bytes = _read_stable_private_file(
        query_path,
        max_bytes=_DISCOVERY_DIGEST_BYTES,
    )
    query_set = DiscoveryQuerySetV1.model_validate_json(query_bytes, strict=True)
    try:
        repository_id = int(source["SKILLSCOUT_STATE_REPOSITORY_ID"])
        repository_full_name = source["SKILLSCOUT_STATE_REPOSITORY_FULL_NAME"]
    except Exception:
        raise ValueError("acceptance state repository rejected") from None
    return DiscoveryRuntimeConfig(
        state_repository_id=repository_id,
        state_repository_full_name=repository_full_name,
        state_ref=_DISCOVERY_STATE_REF,
        query_set_path=query_path,
        query_set=query_set,
        query_set_digest=query_set.query_set_digest or "",
        pipeline_state=Path(_DISCOVERY_DATABASE_LOCATORS[0]),
        operations_state=Path(_DISCOVERY_DATABASE_LOCATORS[1]),
        publication_state=Path(_DISCOVERY_DATABASE_LOCATORS[2]),
        semantic_provider=config.semantic_provider,
        extractor_model_id=config.extractor_model_id,
        generator_model_id=config.generator_model_id,
        reviewer_model_id=config.reviewer_model_id,
        initial_state_root_digest=config.state_root_digest,
        state_lineage_anchor_commit_sha=config.state_lineage_anchor_commit_sha,
        state_lineage_anchor_root_digest=config.state_lineage_anchor_root_digest,
        state_lineage_anchor_max_hops=160,
    )


def build_live_acceptance_execution(
    *,
    config: object,
    restored: object,
    action: str,
    acceptance_run_id: str,
    live_admission: object | None = None,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Build one benchmark or replay graph from an exact restored authority."""

    if (
        type(config) is not AcceptanceRuntimeConfig
        or action not in {"benchmark", "replay"}
        or type(acceptance_run_id) is not str
        or not acceptance_run_id
        or len(acceptance_run_id) > 96
        or getattr(restored, "status", None) != "verified"
        or getattr(restored, "observed_head", None) != config.state_commit_sha
        or getattr(getattr(restored, "bundle", None), "root", None) is None
        or restored.bundle.root.root_digest != config.state_root_digest
    ):
        raise ValueError("live acceptance execution rejected")
    from skillscout.adapters.operations_state import (
        OperationsStateStore,
        _parse_bundle_exports,
    )
    from skillscout.application.acceptance import (
        LockedCampaignDependencies,
        LiveExecutionAdmissionV2,
        ReplayUpdateDependencies,
        re_admit_live_execution_v2,
        run_exact_replay,
        run_locked_benchmark,
    )

    source = os.environ if environ is None else environ
    if (
        type(live_admission) is not LiveExecutionAdmissionV2
        or live_admission.authority.authority_digest
        != config.live_acceptance_authority_digest
        or live_admission.lock.selection_manifest != config.manifest
        or live_admission.authority.state_repository_id
        != live_admission.state_observation.state_repository_id
        or live_admission.authority.state_repository_full_name
        != live_admission.state_observation.state_repository_full_name
    ):
        raise ValueError("live acceptance execution rejected")
    with OperationsStateStore(Path(_DISCOVERY_DATABASE_LOCATORS[1])) as operations:
        rechecked_admission = re_admit_live_execution_v2(
            snapshot=operations.acceptance_snapshot(acceptance_run_id),
            authority_digest=config.live_acceptance_authority_digest,
            state_observation=live_admission.state_observation,
        )
    if rechecked_admission != live_admission:
        raise ValueError("live acceptance execution rejected")
    discovery_config = _acceptance_discovery_config(config, source)
    _, _, frozen_owner_export, _ = _parse_bundle_exports(restored.bundle)
    verified_state_locators = {
        (config.state_commit_sha, config.state_root_digest),
    }
    barrier = _LateStateDurabilityBarrier(
        discovery_config,
        source,
        frozen_publication_export=frozen_owner_export,
    )

    def operations_factory() -> object:
        return OperationsStateStore(discovery_config.operations_state)

    def state_sync(**arguments: object) -> object:
        synchronized = barrier.sync_discovery(**arguments)
        if (
            getattr(synchronized, "status", None) == "verified"
            and _is_commit_sha(getattr(synchronized, "commit_sha", ""))
            and _is_digest(getattr(synchronized, "root_digest", ""))
        ):
            verified_state_locators.add((synchronized.commit_sha, synchronized.root_digest))
        return synchronized

    if action == "replay":

        def projector_factory() -> object:
            return _CompletedBenchmarkStateProjector(
                operations_path=discovery_config.operations_state,
                pipeline_path=discovery_config.pipeline_state,
                acceptance_run_id=acceptance_run_id,
                expected_live_authority_digest=(config.live_acceptance_authority_digest),
                verified_state_locators=verified_state_locators,
            )

        def execute_replay() -> dict[str, object]:
            replay = run_exact_replay(
                ReplayUpdateDependencies(
                    completed_projector_factory=projector_factory,
                    operations_store_factory=operations_factory,
                    state_sync=state_sync,
                ),
                manifest=config.manifest,
                acceptance_run_id=acceptance_run_id,
                state_commit_sha=config.state_commit_sha,
                state_root_digest=config.state_root_digest,
                recorded_at=_discovery_timestamp(),
            )
            return {
                "acceptance_run_id": acceptance_run_id,
                "replay_digest": replay.replay_digest,
                "status": "replay_complete",
            }

        return _LiveAcceptanceExecution("replay", execute_replay)

    runner_factory = _fixed_acceptance_runner_factory(
        config=config,
        discovery_config=discovery_config,
        restored=restored,
        barrier=barrier,
        source=source,
        frozen_owner_export=frozen_owner_export,
        acceptance_run_id=acceptance_run_id,
    )

    def execute_benchmark() -> dict[str, object]:
        result = run_locked_benchmark(
            LockedCampaignDependencies(
                discovery_factory=runner_factory,
                operations_store_factory=operations_factory,
                state_sync=state_sync,
            ),
            manifest=config.manifest,
            acceptance_run_id=acceptance_run_id,
            observed_head=config.state_commit_sha,
            prior_root_digest=config.state_root_digest,
            recorded_at=_discovery_timestamp(),
        )
        return {
            "acceptance_run_id": acceptance_run_id,
            "scenario_result_digests": tuple(
                item.result_digest for item in result.scenario_results
            ),
            "state_commit_sha": result.state_commit_sha,
            "state_root_digest": result.state_root_digest,
            "status": "benchmark_complete",
        }

    return _LiveAcceptanceExecution("benchmark", execute_benchmark)


def build_nomination_application(
    config: NominationRuntimeConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Build the Search-only nomination graph with exact state CAS."""

    if type(config) is not NominationRuntimeConfig:
        raise ValueError("nomination runtime configuration rejected")
    source = os.environ if environ is None else environ
    pipeline_path = Path(_DISCOVERY_DATABASE_LOCATORS[0])
    publication_path = Path(_DISCOVERY_DATABASE_LOCATORS[2])
    durability_barrier = _LateStateDurabilityBarrier(config, source)

    def search_factory() -> object:
        from skillscout.adapters.github import GitHubReadClient

        return GitHubReadClient(
            token=_required_credential(source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN")
        )

    def state_restore() -> object:
        from skillscout.adapters.operations_state import (
            restore_three_store_bundle,
        )
        from skillscout.adapters.state_branch import (
            StateBranchClient,
            StateBranchStore,
        )

        client = StateBranchClient(
            token=_required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
            repository_id=config.state_repository_id,
            repository_full_name=config.state_repository_full_name,
        )
        try:
            store = StateBranchStore(
                client,
                read_cache=durability_barrier.state_branch_read_cache(),
            )
            observation = store.restore(
                lineage_anchor=_configured_state_lineage_anchor(config)
            )
            bundle = getattr(observation, "bundle", None)
            if bundle is None or getattr(bundle, "root", None) is None:
                raise ValueError("nomination initial state rejected")
            restore_three_store_bundle(
                bundle,
                pipeline_path=pipeline_path,
                operations_path=config.operations_state,
                publication_path=publication_path,
            )
            return observation
        finally:
            client.close()

    def operations_store_factory() -> object:
        from skillscout.adapters.operations_state import OperationsStateStore

        return OperationsStateStore(config.operations_state)

    from skillscout.application.acceptance import (
        NominationApplication,
        NominationDependencies,
    )

    return NominationApplication(
        NominationDependencies(
            search_factory=search_factory,
            operations_store_factory=operations_store_factory,
            state_restore=state_restore,
            durability_barrier=durability_barrier,
        ),
        query_set=config.query_set,  # type: ignore[arg-type]
        initial_state_root_digest=config.initial_state_root_digest,
    )


def _restore_verified_fresh_campaign_state(
    *,
    config: FreshCampaignPreparationRuntimeConfig,
    source: Mapping[str, str],
    pipeline_path: Path,
    publication_path: Path,
    read_cache: object | None = None,
) -> object:
    """Read-verify the configured state repository identity before restoring it."""
    from skillscout.adapters.operations_state import restore_three_store_bundle
    _read_fresh_campaign_state_metadata(config=config, source=source)
    observation = _restore_fresh_campaign_state_read_only(
        config=config,
        source=source,
        bounded=False,
        read_cache=read_cache,
    )
    bundle = getattr(observation, "bundle", None)
    if bundle is None or getattr(bundle, "root", None) is None:
        raise ValueError("fresh campaign state rejected")
    if getattr(observation, "observed_head", None) is None:
        raise ValueError("fresh campaign state rejected")
    restore_three_store_bundle(
        bundle,
        pipeline_path=pipeline_path,
        operations_path=config.operations_state,
        publication_path=publication_path,
    )
    return observation


def _read_fresh_campaign_state_metadata(
    *,
    config: FreshCampaignPreparationRuntimeConfig,
    source: Mapping[str, str],
) -> object:
    """Read and verify only the configured state repository identity."""

    from skillscout.adapters.github import GitHubReadClient

    token = _required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN")
    owner, repository = config.state_repository_full_name.split("/", 1)
    client = GitHubReadClient(token=token)
    try:
        metadata = client.get_repo_metadata(owner, repository)
    finally:
        client.close()
    _verify_fresh_campaign_state_repository_identity(metadata=metadata, config=config)
    return metadata


def _restore_fresh_campaign_state_read_only(
    *,
    config: FreshCampaignPreparationRuntimeConfig,
    source: Mapping[str, str],
    bounded: bool = True,
    read_cache: object | None = None,
) -> object:
    """Verify the immutable state branch without restoring or mutating local stores."""

    from skillscout.adapters.state_branch import (
        ResolverReadBudget,
        StateBranchClient,
        StateBranchReadCache,
        StateBranchStore,
        StateLineageAnchor,
    )

    if read_cache is not None and type(read_cache) is not StateBranchReadCache:
        raise ValueError("fresh campaign state read cache rejected")

    token = _required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN")
    client = StateBranchClient(
        token=token,
        repository_id=config.state_repository_id,
        repository_full_name=config.state_repository_full_name,
    )
    try:
        store = (
            StateBranchStore(client)
            if read_cache is None
            else StateBranchStore(client, read_cache=read_cache)
        )
        anchor = StateLineageAnchor(
            commit_sha=config.state_lineage_anchor_commit_sha,
            root_digest=config.state_lineage_anchor_root_digest,
            max_hops=config.state_lineage_anchor_max_hops,
        )
        if bounded:
            observation = store.restore_with_split_budgets(
                lineage_anchor=anchor,
                lineage_read_budget=ResolverReadBudget(phase="lineage"),
                payload_read_budget=ResolverReadBudget.payload_phase(),
            )
        else:
            observation = store.restore(lineage_anchor=anchor)
        bundle = getattr(observation, "bundle", None)
        if bundle is None or getattr(bundle, "root", None) is None:
            raise ValueError("fresh campaign state rejected")
        if getattr(observation, "observed_head", None) is None:
            raise ValueError("fresh campaign state rejected")
        return observation
    finally:
        client.close()


def _verify_fresh_campaign_state_repository_identity(
    *,
    metadata: object,
    config: FreshCampaignPreparationRuntimeConfig,
) -> None:
    """Accept only the configured numeric state repository identity on the fixed host."""

    if (
        type(config) is not FreshCampaignPreparationRuntimeConfig
        or getattr(metadata, "id", None) != config.state_repository_id
        or getattr(metadata, "owner", None) is None
        or getattr(metadata, "name", None) is None
        or f"{getattr(metadata, 'owner')}/{getattr(metadata, 'name')}"
        != config.state_repository_full_name
    ):
        raise ValueError("fresh campaign state repository identity rejected")


def build_fresh_campaign_preparation_application(
    config: FreshCampaignPreparationRuntimeConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Compose only bounded Search, current-state restore, and one nomination CAS."""

    if type(config) is not FreshCampaignPreparationRuntimeConfig:
        raise ValueError("fresh campaign preparation configuration rejected")
    source = os.environ if environ is None else environ
    pipeline_path = Path(_DISCOVERY_DATABASE_LOCATORS[0])
    publication_path = Path(_DISCOVERY_DATABASE_LOCATORS[2])
    durability_barrier = _LateStateDurabilityBarrier(config, source)

    def search_factory() -> object:
        from skillscout.adapters.github import GitHubReadClient

        return GitHubReadClient(
            token=_required_credential(source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN")
        )

    def state_restore() -> object:
        return _restore_verified_fresh_campaign_state(
            config=config,
            source=source,
            pipeline_path=pipeline_path,
            publication_path=publication_path,
            read_cache=durability_barrier.state_branch_read_cache(),
        )

    def operations_store_factory() -> object:
        from skillscout.adapters.operations_state import OperationsStateStore

        return OperationsStateStore(config.operations_state)

    from skillscout.application.acceptance import (
        FreshCampaignPreparationApplication,
        FreshCampaignPreparationDependencies,
    )

    return FreshCampaignPreparationApplication(
        FreshCampaignPreparationDependencies(
            search_factory=search_factory,
            operations_store_factory=operations_store_factory,
            state_restore=state_restore,
            durability_barrier=durability_barrier,
        ),
        query_set=config.query_set,  # type: ignore[arg-type]
        state_repository_id=config.state_repository_id,
        state_repository_full_name=config.state_repository_full_name,
    )


def build_fresh_campaign_preflight_application(
    config: FreshCampaignPreparationRuntimeConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Compose only read-only state identity, immutable restore, and bounded Search probes."""

    if type(config) is not FreshCampaignPreparationRuntimeConfig:
        raise ValueError("fresh campaign preflight configuration rejected")
    source = os.environ if environ is None else environ

    def state_metadata_factory() -> object:
        return _read_fresh_campaign_state_metadata(config=config, source=source)

    def state_restore_factory() -> object:
        return _restore_fresh_campaign_state_read_only(config=config, source=source)

    def search_factory() -> object:
        from skillscout.adapters.github import GitHubReadClient

        return GitHubReadClient(
            token=_required_credential(source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN")
        )

    from skillscout.application.acceptance import (
        FreshCampaignPreflightApplication,
        FreshCampaignPreflightDependencies,
    )

    return FreshCampaignPreflightApplication(
        FreshCampaignPreflightDependencies(
            state_metadata_factory=state_metadata_factory,
            state_restore_factory=state_restore_factory,
            search_factory=search_factory,
        ),
        query_set=config.query_set,  # type: ignore[arg-type]
    )


def build_fresh_campaign_lock_handoff_application(
    config: FreshCampaignLockRuntimeConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Compose only protected approval reads and emit a redacted canonical handoff."""

    if type(config) is not FreshCampaignLockRuntimeConfig:
        raise ValueError("fresh campaign lock configuration rejected")
    source = os.environ if environ is None else environ
    preparation = config.preparation

    def source_binding_factory() -> object:
        from skillscout.application.acceptance import FreshCampaignSourceBinding

        return FreshCampaignSourceBinding(
            source_commit_sha=config.source_commit_sha,
            acceptance_workflow_sha256=config.acceptance_workflow_sha256,
            workflow_run_id=config.workflow_run_id,
            workflow_run_attempt=config.workflow_run_attempt,
            trigger_identity=config.trigger_identity,
        )

    def selection_manifest_factory() -> object:
        return config.selection_manifest

    def source_repository_id_factory() -> object:
        from skillscout.adapters.github import GitHubReadClient

        owner, repository = config.source_repository_full_name.split("/", 1)
        client = GitHubReadClient(token=_required_credential(source, "GITHUB_TOKEN"))
        try:
            metadata = client.get_repo_metadata(owner, repository)
        finally:
            client.close()
        if (
            metadata.id != config.source_repository_id
            or f"{metadata.owner}/{metadata.name}" != config.source_repository_full_name
        ):
            raise ValueError("fresh benchmark source repository identity is invalid")
        return metadata.id

    def approval_receipt_factory() -> object:
        from skillscout.adapters.github import GitHubReadClient
        from skillscout.domain.acceptance import BenchmarkLockApprovalReceiptV2

        owner, repository = config.source_repository_full_name.split("/", 1)
        expected_actor_id, expected_actor_login = _fresh_campaign_trigger_actor(
            config.trigger_identity
        )
        client = GitHubReadClient(token=_required_credential(source, "GITHUB_TOKEN"))
        try:
            attempt = client.get_workflow_run_attempt(
                owner,
                repository,
                config.workflow_run_id,
                config.workflow_run_attempt,
            )
            approvals = client.get_workflow_run_approvals(
                owner,
                repository,
                config.workflow_run_id,
            )
        finally:
            client.close()
        if (
            config.workflow_run_attempt != 1
            or attempt.source_commit_sha != config.source_commit_sha
            or attempt.event != "workflow_dispatch"
            or not _is_fresh_campaign_workflow_path(attempt.workflow_path)
            or attempt.actor_id != expected_actor_id
            or attempt.actor_login != expected_actor_login
            or attempt.triggering_actor_id != expected_actor_id
            or attempt.triggering_actor_login != expected_actor_login
        ):
            raise ValueError("fresh benchmark run attempt binding is invalid")
        matching = tuple(
            approval
            for approval in approvals
            if (
                approval.environment == "phase6-human-benchmark-lock"
                and approval.reviewer_login == "alexzhu0"
            )
        )
        if len(matching) != 1:
            raise ValueError("fresh benchmark approval is missing or ambiguous")
        approval = matching[0]
        return BenchmarkLockApprovalReceiptV2(
            schema_version="benchmark-lock-approval-receipt-v2",
            purpose="benchmark_lock",
            environment="phase6-human-benchmark-lock",
            source_repository_id=config.source_repository_id,
            source_repository_full_name=config.source_repository_full_name,
            reviewer_login="alexzhu0",
            reviewer_id=approval.reviewer_id,
            workflow_run_id=config.workflow_run_id,
            workflow_run_attempt=config.workflow_run_attempt,
            source_commit_sha=config.source_commit_sha,
            workflow_sha256=config.acceptance_workflow_sha256,
            trigger_identity=config.trigger_identity,
            approval_record_digest=approval.approval_record_digest,
        )

    from skillscout.application.acceptance import (
        FreshCampaignLockHandoffApplication,
        FreshCampaignLockHandoffDependencies,
    )

    return FreshCampaignLockHandoffApplication(
        FreshCampaignLockHandoffDependencies(
            approval_receipt_factory=approval_receipt_factory,
            selection_manifest_factory=selection_manifest_factory,
            source_binding_factory=source_binding_factory,
            source_repository_id_factory=source_repository_id_factory,
        ),
        source_repository_full_name=config.source_repository_full_name,
        state_repository_id=preparation.state_repository_id,
        state_repository_full_name=preparation.state_repository_full_name,
    )


def build_fresh_campaign_lock_application(
    config: FreshCampaignLockRuntimeConfig,
    handoff: object,
    *,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Compose state-only persistence after exact source and approval handoff admission."""

    if (
        type(config) is not FreshCampaignLockRuntimeConfig
        or not _fresh_campaign_lock_handoff_matches_config(
            config=config,
            handoff=handoff,
        )
    ):
        raise ValueError("fresh campaign lock configuration rejected")
    source = os.environ if environ is None else environ
    preparation = config.preparation
    pipeline_path = Path(_DISCOVERY_DATABASE_LOCATORS[0])
    publication_path = Path(_DISCOVERY_DATABASE_LOCATORS[2])

    def state_restore() -> object:
        return _restore_verified_fresh_campaign_state(
            config=preparation,
            source=source,
            pipeline_path=pipeline_path,
            publication_path=publication_path,
        )

    def operations_store_factory() -> object:
        from skillscout.adapters.operations_state import OperationsStateStore

        return OperationsStateStore(preparation.operations_state)

    from skillscout.application.acceptance import (
        FreshCampaignLockApplication,
        FreshCampaignLockDependencies,
    )

    return FreshCampaignLockApplication(
        FreshCampaignLockDependencies(
            handoff_factory=lambda: handoff,
            state_restore=state_restore,
            operations_store_factory=operations_store_factory,
            durability_barrier=_LateStateDurabilityBarrier(preparation, source),
        ),
        state_repository_id=preparation.state_repository_id,
        state_repository_full_name=preparation.state_repository_full_name,
        source_repository_id=config.source_repository_id,
        source_repository_full_name=config.source_repository_full_name,
        query_set_digest=preparation.query_set_digest,
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
        candidate["locator"] = "state/objects/sha256/ff/" + ("f" * 64) + ".json"
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
        or tuple(os.fspath(path) for path in (pipeline_state, operations_state, publication_state))
        != _DISCOVERY_DATABASE_LOCATORS
    ):
        raise ValueError("protected discovery state configuration rejected")
    require_hosted_state_repository(
        state_repository_id=str(state_repository_id),
        state_repository_full_name=state_repository_full_name,
    )
    source = os.environ if environ is None else environ
    from skillscout.adapters.operations_state import restore_three_store_bundle
    from skillscout.adapters.state_branch import (
        StateBranchClient,
        StateBranchStore,
        StateLineageAnchor,
    )

    client = StateBranchClient(
        token=_required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
        repository_id=state_repository_id,
        repository_full_name=state_repository_full_name,
    )
    try:
        observation = StateBranchStore(
            _PinnedStateRemote(client, state_commit_sha)
        ).restore(
            lineage_anchor=StateLineageAnchor(
                commit_sha=_PHASE6_STATE_LINEAGE_ANCHOR_COMMIT_SHA,
                root_digest=_PHASE6_STATE_LINEAGE_ANCHOR_ROOT_DIGEST,
                max_hops=_DISCOVERY_STATE_LINEAGE_MAX_HOPS,
            )
        )
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


def read_exact_acceptance_state(
    *,
    state_commit_sha: str,
    state_repository_id: int,
    state_repository_full_name: str,
    pipeline_state: Path,
    operations_state: Path,
    state_lineage_anchor_commit_sha: str,
    state_lineage_anchor_root_digest: str,
    environ: Mapping[str, str] | None = None,
) -> object:
    """Read exact state while keeping publication as immutable verified bytes."""

    if (
        not _is_commit_sha(state_commit_sha)
        or type(state_repository_id) is not int
        or state_repository_id <= 0
        or not _github_full_name(state_repository_full_name)
        or tuple(os.fspath(path) for path in (pipeline_state, operations_state))
        != _DISCOVERY_DATABASE_LOCATORS[:2]
        or not _is_commit_sha(state_lineage_anchor_commit_sha)
        or not _is_digest(state_lineage_anchor_root_digest)
    ):
        raise ValueError("protected acceptance state configuration rejected")
    source = os.environ if environ is None else environ
    from skillscout.adapters.operations_state import (
        restore_acceptance_state_bundle,
    )
    from skillscout.adapters.state_branch import (
        StateBranchClient,
        StateBranchStore,
        StateLineageAnchor,
    )

    client = StateBranchClient(
        token=_required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
        repository_id=state_repository_id,
        repository_full_name=state_repository_full_name,
    )
    try:
        store = StateBranchStore(_PinnedStateRemote(client, state_commit_sha))
        observation = store.restore(
            lineage_anchor=StateLineageAnchor(
                commit_sha=state_lineage_anchor_commit_sha,
                root_digest=state_lineage_anchor_root_digest,
                max_hops=_ACCEPTANCE_STATE_LINEAGE_MAX_HOPS,
            )
        )
        if (
            observation.status != "verified"
            or observation.observed_head != state_commit_sha
            or observation.bundle is None
        ):
            raise ValueError("protected acceptance state rejected")
        restore_acceptance_state_bundle(
            observation.bundle,
            pipeline_path=pipeline_state,
            operations_path=operations_state,
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
    root_objects = {item.locator: item.object_digest for item in root.objects}
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
    if sorted(persisted_eligible) != sorted(supplied_eligible) or len(persisted_eligible) != len(
        set(persisted_eligible)
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
            terminal_bytes = base64.b64decode(wrapper["content_base64"], validate=True)
            terminal = CandidateTerminalSummaryV1.model_validate_json(terminal_bytes, strict=True)
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
        projector = DescriptorAnchoredCompletedCandidateProjector(phase3_state)
        completed = projector.find_completed_candidate(terminal.candidate_execution_authority)
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
        targets = ReviewerTargetsV1(schema_version="reviewer-targets-v1", reviewers=reviewers)
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
    if type(raw) is not str or not raw.isascii() or len(raw.encode("ascii")) > 255 or "\\" in raw:
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
        completed = projector.find_completed_candidate(authority)
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

    if (
        type(admission) is not PublicationAdmissionV1
        or type(authority) is not PublicationAuthorityConfig
    ):
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
        if _metadata_facts(opened) != _metadata_facts(os.fstat(descriptor)) or _metadata_facts(
            opened
        ) != _metadata_facts(os.lstat(path)):
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
        if (candidate / "uv.lock").exists() and (
            candidate / "config/supply-chain/phase3-gate-b3.lock.sha256"
        ).exists():
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
    if not value or "\\" in value or any(ord(character) < 32 for character in value):
        _fail()
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or not path.parts:
        _fail()
    return path


def _verify_validator_distribution() -> ValidatorDistributionAdmission:
    try:
        distributions = tuple(importlib.metadata.distributions(name=_VALIDATOR_DISTRIBUTION))
        if len(distributions) != 1:
            _fail()
        distribution = distributions[0]
        record_entry = next(
            entry
            for entry in (distribution.files or ())
            if entry.name == "RECORD" and entry.parent.name.endswith(".dist-info")
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
        if ".." not in path.parts and path.name not in _GENERATED_RECORD_NAMES:
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
        distribution_root=os.fspath(Path(os.path.abspath(os.fspath(site_packages)))),
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
        origin = os.path.abspath(os.fspath(module_origin)) if module_origin is not None else None
    except (TypeError, ValueError):
        _fail()
    if (
        origin != admission.module_origin
        or paths != (admission.package_search_path,)
        or not admission.module_origin.startswith(admission.distribution_root + os.sep)
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
