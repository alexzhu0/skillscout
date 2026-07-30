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
from dataclasses import dataclass, replace
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
_ACCEPTANCE_MANIFEST_NAME = "06-BENCHMARK-MANIFEST.json"
_ACCEPTANCE_MANIFEST_BYTES = 1_048_576
_DISCOVERY_DATABASE_LOCATORS = (
    "state/databases/pipeline.sqlite3",
    "state/databases/operations.sqlite3",
    "state/databases/publication.sqlite3",
)
_DISCOVERY_DIGEST_BYTES = 65_536
ACCEPTANCE_CATALOG_FULL_NAME = "alexzhu0/skillscout-catalog-test"


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
    resume_lineage_commit_shas: tuple[str, ...] = ()
    resume_lineage_root_digests: tuple[str, ...] = ()

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
                    or len(self.resume_lineage_commit_shas)
                    != len(self.resume_lineage_root_digests)
                    or not self.resume_lineage_commit_shas
                    or len(self.resume_lineage_commit_shas) > 256
                    or self.resume_lineage_commit_shas[-1]
                    != self.state_commit_sha
                    or self.resume_lineage_root_digests[-1]
                    != self.state_root_digest
                    or any(
                        not _is_commit_sha(item)
                        for item in self.resume_lineage_commit_shas
                    )
                    or any(
                        not _is_digest(item)
                        for item in self.resume_lineage_root_digests
                    )
                    or (
                        self.resume_locator_digest is not None
                        and not _is_digest(self.resume_locator_digest)
                    )
                )
            )
            or (
                self.acceptance_run_id is None
                and (
                    self.resume_locator_digest is not None
                    or self.resume_lineage_commit_shas
                    or self.resume_lineage_root_digests
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
) -> object:
    """Verify a human-approved authority and its exact repository-owned bytes."""

    try:
        manifest_relative = Path(
            ".planning/phases/06-adversarial-mvp-acceptance/"
            "06-BENCHMARK-MANIFEST.json"
        )
        workflow_relative = Path(".github/workflows/phase6-acceptance.yml")
        query_relative = Path("config/discovery-queries-v1.json")
        root = _trusted_repository_root(repository_root)
        if (
            type(authority_bytes) is not bytes
            or not authority_bytes
            or len(authority_bytes) > _ACCEPTANCE_MANIFEST_BYTES
        ):
            raise ValueError
        manifest_bytes = _read_exact_repository_file(
            root,
            root / manifest_relative,
            manifest_relative,
            _ACCEPTANCE_MANIFEST_BYTES,
        )
        workflow_bytes = _read_exact_repository_file(
            root,
            root / workflow_relative,
            workflow_relative,
            _ACCEPTANCE_MANIFEST_BYTES,
        )
        query_bytes = _read_exact_repository_file(
            root,
            root / query_relative,
            query_relative,
            _DISCOVERY_DIGEST_BYTES,
        )
        from skillscout.adapters.semantic_provider import resolve_semantic_provider
        from skillscout.domain.acceptance import (
            LiveAcceptanceAuthorityV1,
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

        authority = LiveAcceptanceAuthorityV1.model_validate_json(
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
        provider = resolve_semantic_provider(
            os.environ if environ is None else environ
        )
        budget = DiscoveryBudgetPolicyV1()
        if (
            authority.source_commit_sha != observed_source_commit_sha
            or authority.state_commit_sha != observed_state_commit_sha
            or authority.state_root_digest != observed_state_root_digest
            or authority.state_repository_id != observed_state_repository_id
            or authority.state_repository_full_name
            != observed_state_repository_full_name
            or authority.acceptance_workflow_sha256
            != "sha256:" + hashlib.sha256(workflow_bytes).hexdigest()
            or authority.manifest_path != manifest_relative.as_posix()
            or authority.manifest_digest != manifest.manifest_digest
            or authority.nomination_set_digest != manifest.nomination_set_digest
            or authority.lock_attestation_digest
            != manifest.lock_attestation.attestation_digest
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
        ):
            raise ValueError
        return authority
    except Exception:
        raise ValueError("live acceptance authority rejected") from None


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
            or os.fspath(self.operations_state)
            != _DISCOVERY_DATABASE_LOCATORS[1]
            or not _is_digest(self.initial_state_root_digest)
        ):
            raise ValueError("nomination runtime configuration rejected")


def _is_commit_sha(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
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


def load_acceptance_runtime_config(
    *,
    manifest_path: Path,
    state_commit_sha: str,
    state_root_digest: str,
    acceptance_run_id: str | None = None,
    resume_proof_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AcceptanceRuntimeConfig:
    """Re-admit locked facts and provider identity before credential lookup."""

    try:
        if (
            not isinstance(manifest_path, Path)
            or manifest_path.name != _ACCEPTANCE_MANIFEST_NAME
            or not _is_commit_sha(state_commit_sha)
            or not _is_digest(state_root_digest)
        ):
            raise ValueError
        payload = _read_stable_private_file(
            manifest_path,
            max_bytes=_ACCEPTANCE_MANIFEST_BYTES,
        )
        from skillscout.adapters.semantic_provider import resolve_semantic_provider
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
        provider = resolve_semantic_provider(source)
        resume_locator_digest: str | None = None
        resume_commits: tuple[str, ...] = ()
        resume_roots: tuple[str, ...] = ()
        if resume_proof_path is not None:
            if acceptance_run_id is None:
                raise ValueError
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
                or (
                    proof["locator_digest"] is not None
                    and type(proof["locator_digest"]) is not str
                )
            ):
                raise ValueError
            resume_locator_digest = proof["locator_digest"]
            resume_commits = tuple(proof["lineage_commit_shas"])
            resume_roots = tuple(proof["lineage_root_digests"])
        return AcceptanceRuntimeConfig(
            manifest_path=manifest_path,
            manifest=manifest,
            state_commit_sha=state_commit_sha,
            state_root_digest=state_root_digest,
            semantic_provider=provider.provider.value,
            extractor_model_id=provider.extract_model,
            generator_model_id=provider.generator_model,
            reviewer_model_id=provider.reviewer_model,
            live_acceptance_authority_digest=source[
                "PHASE6_AUTHORITY_DIGEST"
            ],
            acceptance_run_id=(
                acceptance_run_id if resume_proof_path is not None else None
            ),
            resume_locator_digest=resume_locator_digest,
            resume_lineage_commit_shas=resume_commits,
            resume_lineage_root_digests=resume_roots,
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
            HumanSkillReviewAttestationV1
            if kind == "human-review"
            else ProbeCleanupAttestationV1
        )
        attestation = model.model_validate_json(payload, strict=True)
        canonical = canonical_json_bytes(attestation)
        if payload not in {canonical, canonical + b"\n"}:
            raise ValueError
        return attestation
    except Exception:
        raise ValueError("acceptance attestation rejected") from None


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
        config: DiscoveryRuntimeConfig | NominationRuntimeConfig,
        source: Mapping[str, str],
        *,
        frozen_publication_export: object | None = None,
    ) -> None:
        self._config = config
        self._source = source
        self._frozen_publication_export = frozen_publication_export
        self._acceptance_resume: dict[str, object] | None = None

    def configure_acceptance_resume(
        self,
        *,
        authority: object,
        acceptance_run_id: str,
        lineage_commit_shas: tuple[str, ...],
        lineage_root_digests: tuple[str, ...],
    ) -> None:
        """Bind locator creation to one immutable authority and verified lineage."""

        from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

        if (
            type(authority) is not LiveAcceptanceAuthorityV1
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
        ):
            raise ValueError("acceptance resume authority rejected")
        self._acceptance_resume = {
            "authority": authority,
            "acceptance_run_id": acceptance_run_id,
            "lineage_commit_shas": lineage_commit_shas,
            "lineage_root_digests": lineage_root_digests,
        }

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

    def anchor_acceptance_resume(
        self,
        *,
        operations_store: object,
        observed_head: str,
        prior_root_digest: str,
        created_at: str,
        pipeline_store: object | None = None,
    ) -> object:
        """Record the current parent locator, then make it durable by exact CAS."""

        from skillscout.domain.acceptance import (
            AcceptanceCampaignResumeLocatorV1,
            LiveAcceptanceAuthorityV1,
        )

        resume = self._acceptance_resume
        if resume is None:
            raise ValueError("acceptance resume lineage is not configured")
        authority = resume["authority"]
        if type(authority) is not LiveAcceptanceAuthorityV1:
            raise ValueError("acceptance resume authority rejected")
        commits = resume["lineage_commit_shas"]
        roots = resume["lineage_root_digests"]
        if (
            type(commits) is not tuple
            or type(roots) is not tuple
            or commits[-1] != observed_head
            or roots[-1] != prior_root_digest
            or len(commits) > 255
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
            current_state_commit_sha=observed_head,
            current_state_root_digest=prior_root_digest,
            semantic_provider=authority.semantic_provider,
            stage_models=authority.stage_models,
            prompt_versions=authority.prompt_versions,
            schema_versions=authority.schema_versions,
            policy_versions=authority.policy_versions,
            lineage_commit_shas=commits,
            lineage_root_digests=roots,
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
        synchronized = self.sync_discovery(
            operations_store=operations_store,
            observed_head=observed_head,
            prior_root_digest=prior_root_digest,
            created_at=created_at,
            pipeline_store=pipeline_store,
        )
        if (
            getattr(synchronized, "status", None) != "verified"
            or getattr(synchronized, "previous_head", None) != observed_head
            or not _is_commit_sha(getattr(synchronized, "commit_sha", ""))
            or not _is_digest(getattr(synchronized, "root_digest", ""))
        ):
            raise ValueError("acceptance resume locator was not durable")
        advanced = self._acceptance_resume
        if (
            advanced is None
            or advanced["lineage_commit_shas"][-1]
            != synchronized.commit_sha
        ):
            self._acceptance_resume = {
                **resume,
                "lineage_commit_shas": (
                    *commits,
                    synchronized.commit_sha,
                ),
                "lineage_root_digests": (
                    *roots,
                    synchronized.root_digest,
                ),
            }
        return synchronized

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
            resume = self._acceptance_resume
            if resume is not None:
                commits = resume["lineage_commit_shas"]
                roots = resume["lineage_root_digests"]
                if (
                    type(commits) is not tuple
                    or type(roots) is not tuple
                    or commits[-1] != observed_head
                    or roots[-1] != prior_root_digest
                    or len(commits) > 255
                ):
                    raise ValueError("acceptance resume lineage drifted")
                self._acceptance_resume = {
                    **resume,
                    "lineage_commit_shas": (
                        *commits,
                        synchronized.commit_sha,
                    ),
                    "lineage_root_digests": (
                        *roots,
                        synchronized.root_digest,
                    ),
                }
            return synchronized
        finally:
            client.close()
            publication.close()
            if owns_pipeline:
                pipeline.close()

    def sync_nomination(self, **arguments: object) -> object:
        """Reuse the exact three-store CAS for a Search-only nomination."""

        return self.sync_discovery(**arguments)  # type: ignore[arg-type]


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
            from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
            from skillscout.domain.discovery import (
                DiscoveredCandidateV1,
                DiscoveryCandidateTerminalV1,
                DiscoveryRunAuthorityV1,
                SemanticReservationV1,
            )
            from skillscout.domain.review import (
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
                type(candidate) not in {
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
                        type(pinned_commit_sha) is not str
                        or not _is_commit_sha(pinned_commit_sha)
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
            semantic_telemetry: list[DiscoverySemanticTelemetry] = []
            reader_telemetry: DiscoveryReaderTelemetry | None = None
            restored_snapshot = operations.snapshot_run(
                discovery_authority.run_id
            )
            restored_discovery_reservation = next(
                (
                    item
                    for item in restored_snapshot.discovery_reservations
                    if item.repository_id
                    == candidate.repository.repository_id
                ),
                None,
            )
            semantic_reservation = next(
                (
                    item
                    for item in restored_snapshot.semantic_reservations
                    if item.repository_id
                    == candidate.repository.repository_id
                ),
                None,
            )
            if recovery_only:
                recovered_extractor_attempts = tuple(
                    item
                    for item in restored_snapshot.semantic_attempts
                    if item.repository_id
                    == candidate.repository.repository_id
                    and item.workflow_authority_digest
                    == phase2_authority_digest
                    and item.stage == "extractor"
                )
                if len(recovered_extractor_attempts) != 3:
                    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
            fixed_admission = (
                candidate.admission
                if type(candidate) is FixedAcceptanceCandidate
                else None
            )
            if semantic_reservation is not None and (
                type(semantic_reservation) is not SemanticReservationV1
                or (
                    fixed_admission is None
                    and restored_discovery_reservation is None
                )
                or semantic_reservation.discovery_run_authority_digest
                != discovery_authority.authority_digest
                or semantic_reservation.repository_id
                != candidate.repository.repository_id
                or semantic_reservation.discovery_reservation_digest
                != (
                    fixed_admission.admission_digest
                    if fixed_admission is not None
                    else restored_discovery_reservation.reservation_digest
                )
                or semantic_reservation.phase2_run_authority_digest
                != phase2_authority_digest
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
                    semantic_reservation = (
                        operations.reserve_acceptance_semantic_candidate(
                            discovery_authority.run_id,
                            fixed_admission,
                            phase2_authority_digest,
                            _discovery_timestamp(),
                        )
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
            ) -> SemanticReservationReceipt:
                del run_id
                nonlocal state_head, state_root
                if fixed_admission is None:
                    raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
                anchor_resume = getattr(
                    barrier,
                    "anchor_acceptance_resume",
                    None,
                )
                if callable(anchor_resume):
                    anchored = anchor_resume(
                        operations_store=operations,
                        observed_head=state_head,
                        prior_root_digest=state_root,
                        created_at=_discovery_timestamp(),
                        pipeline_store=pipeline_store,
                    )
                    state_head = anchored.commit_sha
                    state_root = anchored.root_digest
                request = operations.reserve_acceptance_semantic_request(
                    acceptance_run_id=fixed_admission.acceptance_run_id,
                    fixed_candidate_admission_digest=(
                        fixed_admission.admission_digest or ""
                    ),
                    repository_id=repository_id,
                    workflow_spec_authority_digest=(
                        workflow_authority_digest
                    ),
                    stage=stage,  # type: ignore[arg-type]
                    attempt_no=attempt_no,
                    reserved_at=_discovery_timestamp(),
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
            github = _LazyDiscoveryCapability(
                (
                    lambda: (_ for _ in ()).throw(
                        SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                    )
                    if recovery_only
                    else lambda: GitHubReadClient(
                        token=_required_credential(
                            source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN"
                        )
                    )
                ),
                EffectScope.REMOTE_READ,
            )
            extractor = _LazyDiscoveryCapability(
                (
                    lambda: (_ for _ in ()).throw(
                        SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
                    )
                    if recovery_only
                    else lambda: (
                        OpenAIExtractionClient()
                        if provider.provider is SemanticProvider.OPENAI
                        else OpenAIExtractionClient(
                            model=provider.extract_model,
                            provider_settings=provider,
                        )
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
                request_reservation_hook=(
                    reserve_before_request
                    if fixed_admission is not None
                    else None
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
                    repository=(
                        f"https://github.com/{candidate.repository.full_name}"
                    ),
                    ref=pinned_commit_sha,
                )
                with tempfile.TemporaryDirectory(
                    prefix="skillscout-discovery-phase2-",
                    dir=Path(tempfile.gettempdir()).resolve(strict=True),
                ) as phase2_output:
                    phase2_summary = runtime.runner.run(
                        subject, Path(phase2_output)
                    )
                chain = phase2_state.verify_run_chain(phase2_summary.run_id)
                extractor_result = next(
                    (
                        result
                        for result in chain.results
                        if result.stage.value == "extractor"
                    ),
                    None,
                )
                reader_result = next(
                    (
                        result
                        for result in chain.results
                        if result.stage.value == "reader"
                    ),
                    None,
                )
                if reader_result is not None:
                    reader_budgets = reader_result.payload.get("budgets")
                    if isinstance(reader_budgets, dict):
                        reader_telemetry = DiscoveryReaderTelemetry(
                            file_count=int(reader_budgets["files_read"]),
                            source_file_count=int(
                                reader_budgets["source_files_read"]
                            ),
                            total_bytes=int(reader_budgets["total_bytes"]),
                            estimated_tokens=int(
                                reader_budgets["estimated_input_tokens"]
                            ),
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
                            schema_version=str(
                                extractor_result.payload[
                                    "output_schema_version"
                                ]
                            )
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
                    acceptance_system_outcome=(
                        "provider_exhausted"
                        if failure.code is ErrorCode.RETRY_EXHAUSTED
                        else None
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
                    "discovery_run_authority_digest": (
                        discovery_authority.authority_digest
                    ),
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
                    result
                    for result in chain.results
                    if result.stage.value == "filter"
                )
                if filter_result.payload.get("outcome") == "rejected":
                    outcome = "filter_rejected"
                elif extractor_result is None:
                    outcome = "permanent_failure"
                else:
                    outcome, acceptance_system_outcome = (
                        classify_extractor_terminal(
                            str(extractor_result.payload.get("outcome"))
                        )
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
                        prefix="skillscout-discovery-phase3-",
                        dir=Path(tempfile.gettempdir()).resolve(strict=True),
                    ) as directory:
                        descriptor_path = Path(directory) / "candidate.json"
                        descriptor_path.write_bytes(canonical_json_bytes(descriptor))
                        descriptor_path.chmod(0o600)
                        try:
                            resolved = load_candidate_subject(
                                descriptor_path, candidate_source
                            )
                        except CandidateSourceUnavailable:
                            fatal_outcome = "permanent_failure"
                            break
                        workflow_authority = _execution_authority(
                            source=resolved, profile=profile
                        )
                        workflow_authorities.append(
                            workflow_authority.authority_digest
                        )
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
                            workflow_authority_digest=(
                                workflow_authority.authority_digest
                            ),
                            provider=provider.provider.value,
                            expected_prior_state_head=state_head,
                            expected_prior_root_digest=state_root,
                            operations_run_id=discovery_authority.run_id,
                            request_reservation_hook=(
                                reserve_before_request
                                if fixed_admission is not None
                                else None
                            ),
                        )
                        clients: list[object] = []

                        def generator_factory() -> object:
                            if recovery_only:
                                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
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
                            if recovery_only:
                                raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
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
                                            workflow_fingerprint=(
                                                workflow_authority.selected_workflow_fingerprint
                                            ),
                                            workflow_spec_authority_digest=(
                                                workflow_authority.workflow_spec_authority.authority_digest
                                            ),
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
                        completed_projector = (
                            DescriptorAnchoredCompletedCandidateProjector(
                                config.pipeline_state
                            )
                        )
                        completed_projection = (
                            completed_projector.find_completed_candidate(
                                workflow_authority
                            )
                        )
                        if completed_projection is None:
                            raise SafeFailure(
                                ErrorCode.STATE_INTEGRITY_ERROR
                            )
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
                                generator_evidence.actual_generator_model_id
                                is None
                                or generator_evidence.request_id is None
                                or generator_evidence.usage is None
                                or not generator_attempts
                            ):
                                raise SafeFailure(
                                    ErrorCode.STATE_INTEGRITY_ERROR
                                )
                            semantic_telemetry.append(
                                DiscoverySemanticTelemetry(
                                    stage="generator",
                                    workflow_authority_digest=(
                                        workflow_authority.authority_digest
                                    ),
                                    attempt_no=generator_attempts[-1].attempt_no,
                                    request_id=generator_evidence.request_id,
                                    actual_model=(
                                        generator_evidence.actual_generator_model_id
                                    ),
                                    prompt_version=(
                                        generator_evidence.generator_prompt_version
                                    ),
                                    schema_version=(
                                        generator_evidence.generator_output_schema_version
                                    ),
                                    policy_version=(
                                        generator_evidence.generator_policy_version
                                    ),
                                    prompt_tokens=(
                                        generator_evidence.usage.prompt_tokens
                                    ),
                                    completion_tokens=(
                                        generator_evidence.usage.completion_tokens
                                    ),
                                    total_tokens=(
                                        generator_evidence.usage.total_tokens
                                    ),
                                    latency_ms=generator_evidence.latency_ms,
                                )
                            )
                        review_payload = completed_projection.artifacts.get(
                            "review_attestation"
                        )
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
                                raise SafeFailure(
                                    ErrorCode.STATE_INTEGRITY_ERROR
                                )
                            semantic_telemetry.append(
                                DiscoverySemanticTelemetry(
                                    stage="reviewer",
                                    workflow_authority_digest=(
                                        workflow_authority.authority_digest
                                    ),
                                    attempt_no=reviewer_attempts[-1].attempt_no,
                                    request_id=attestation.request_id,
                                    actual_model=(
                                        attestation.actual_reviewer_model_id
                                    ),
                                    prompt_version=(
                                        attestation.reviewer_prompt_version
                                    ),
                                    schema_version=(
                                        attestation.reviewer_output_schema_version
                                    ),
                                    policy_version=(
                                        attestation.reviewer_policy_version
                                    ),
                                    prompt_tokens=attestation.usage.prompt_tokens,
                                    completion_tokens=(
                                        attestation.usage.completion_tokens
                                    ),
                                    total_tokens=attestation.usage.total_tokens,
                                    latency_ms=attestation.latency_ms,
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
                                    workflow_authority_digest=(
                                        workflow_authority.authority_digest
                                    ),
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
                                        and terminal_summary.generated_artifact_identity
                                        is not None
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
            durability_barrier=_LateStateDurabilityBarrier(
                config,
                source,
                frozen_publication_export=frozen_owner_export,
            ),
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
        self._expected_live_authority_digest = (
            expected_live_authority_digest
        )
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
                scenario.live_acceptance_authority_digest
                != self._expected_live_authority_digest
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
        discovery_run_ids = {
            scenario.discovery_run_id for scenario in scenarios
        }
        if len(discovery_run_ids) != 1:
            raise ValueError("completed benchmark discovery authority rejected")
        with OperationsStateStore(self._operations_path) as operations:
            discovery_snapshot = operations.snapshot_run(
                next(iter(discovery_run_ids))
            )
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
                    digest
                    for scenario in scenarios
                    for digest in scenario.semantic_attempt_digests
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
            != tuple(
                sorted(
                    scenario.candidate_terminal_digest
                    for scenario in scenarios
                )
            )
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
                            envelope["schema_version"]
                            != "pipeline-rebuild-row-v1"
                            or type(columns) is not list
                            or type(values) is not list
                            or len(columns) != len(values)
                            or any(
                                type(column) is not str
                                for column in columns
                            )
                        ):
                            raise ValueError
                        raw = dict(zip(columns, values, strict=True))
                    except Exception:
                        raise ValueError(
                            "completed benchmark pipeline fact rejected"
                        ) from None
                else:
                    raw = envelope
                if owned_fact.kind == "phase3_runs":
                    if raw.get("status") != "completed":
                        continue
                    run_id = raw.get("run_id")
                    if type(run_id) is not str:
                        raise ValueError(
                            "completed benchmark typed Phase 3 run rejected"
                        )
                    chain = pipeline.verify_candidate_run_chain(run_id)
                    if (
                        raw.get("authority_digest")
                        != chain.identity.candidate_execution_authority_digest
                    ):
                        raise ValueError(
                            "completed benchmark typed Phase 3 authority rejected"
                        )
                    completed_chains.append(chain)
                elif owned_fact.kind == "phase3_artifact":
                    try:
                        content = base64.b64decode(
                            raw["content_base64"],
                            validate=True,
                        )
                        terminal = (
                            CandidateTerminalSummaryV1.model_validate_json(
                                content,
                                strict=True,
                            )
                        )
                    except Exception:
                        continue
                    terminal_objects.append((owned_fact, terminal))
        finally:
            pipeline.close()
        if (
            workflow_execution_authorities
            and (not completed_chains or not terminal_objects)
        ):
            raise ValueError(
                "completed benchmark typed Phase 3 objects are missing"
            )
        chain_authorities = {
            chain.identity.candidate_execution_authority_digest
            for chain in completed_chains
        }
        terminal_objects = tuple(
            (owned_fact, terminal)
            for owned_fact, terminal in terminal_objects
            if terminal.candidate_execution_authority.authority_digest
            in workflow_execution_authorities
        )
        if any(
            terminal.candidate_execution_authority.authority_digest
            not in chain_authorities
            for _owned_fact, terminal in terminal_objects
        ) or {
            terminal.candidate_execution_authority.authority_digest
            for _owned_fact, terminal in terminal_objects
        } != workflow_execution_authorities:
            raise ValueError(
                "completed benchmark typed Phase 3 terminal is unbound"
            )
        typed_workflow_authorities = {
            terminal.workflow_spec_authority.authority_digest
            for _owned_fact, terminal in terminal_objects
        }
        scenario_workflow_spec_authorities = {
            digest
            for scenario in scenarios
            for digest in scenario.workflow_spec_authority_digests
        }
        phase3_terminal_digests = {
            terminal.terminal_summary_digest
            for _owned_fact, terminal in terminal_objects
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
            or {
                digest
                for scenario in scenarios
                for digest in scenario.skill_artifact_digests
            }
            != phase3_skill_digests
            or {
                digest
                for scenario in scenarios
                for digest in scenario.package_digests
            }
            != phase3_package_digests
        ):
            raise ValueError(
                "completed benchmark typed Phase 3 graph is missing"
            )
        matching_eligible_objects = tuple(
            (owned_fact, terminal)
            for owned_fact, terminal in terminal_objects
            if terminal.eligible
            and terminal.workflow_spec_authority.authority_digest
            == selected.workflow_spec_authority_digest
            and eligible_candidate_locator(
                authority_digest=owned_fact.object_digest,
                workflow_identity_digest=(
                    terminal.workflow_spec_authority.authority_digest
                ),
            ).locator
            == selected.eligible_locator
        )
        if len(matching_eligible_objects) != 1:
            raise ValueError(
                "completed benchmark typed Phase 3 eligible object is missing"
            )
        workflow_authority_digests = tuple(
            sorted(typed_workflow_authorities)
        )
        candidate_fact_digests = tuple(
            sorted(fact.object_digest for fact in pipeline_export.facts)
        )
        acceptance_business_fact_digests = tuple(
            sorted(
                record.fact_digest
                for record in snapshot.facts
                if record.kind
                not in {"acceptance_replay", "acceptance_replay_evidence"}
            )
        )
        operations_fact_digests = tuple(
            sorted(
                fact.object_digest
                for fact in operations_export.facts
                if fact.kind
                not in {"acceptance_replay", "acceptance_replay_evidence"}
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
            raise ValueError(
                "completed benchmark typed Phase 3 skill identity is missing"
            )
        return CompletedBenchmarkProjection(
            manifest_digest=manifest.manifest_digest,
            scenario_result_digests=tuple(
                sorted(scenario.result_digest for scenario in scenarios)
            ),
            repository_id=selected.repository_id,
            source_commit_sha=selected.exact_commit_sha,
            workflow_fingerprint=selected.workflow_fingerprint,
            workflow_spec_authority_digest=(
                selected.workflow_spec_authority_digest
            ),
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
            acceptance_business_fact_digests=(
                acceptance_business_fact_digests
            ),
            operations_fact_digests=operations_fact_digests,
            semantic_request_count=sum(
                scenario.semantic_request_count for scenario in scenarios
            ),
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
        from skillscout.adapters.operations_state import OperationsStateStore
        from skillscout.domain.canonical import sha256_digest
        from skillscout.domain.discovery import DiscoveryBudgetPolicyV1, DiscoveryRunAuthorityV1

        self._config = config
        self._discovery_config = discovery_config
        self._barrier = barrier
        self._source = source
        self._operations = OperationsStateStore(discovery_config.operations_state)
        self._operations.upgrade_acceptance_schema()
        self._acceptance_run_id = acceptance_run_id
        authority_records = tuple(
            record.fact
            for record in self._operations.acceptance_snapshot(
                acceptance_run_id
            ).facts
            if record.kind == "acceptance_live_authority"
            and record.fact_digest
            == config.live_acceptance_authority_digest
        )
        if len(authority_records) != 1:
            raise ValueError("live acceptance authority is missing")
        self._live_authority = authority_records[0]
        if (
            self._live_authority.manifest_digest
            != config.manifest.manifest_digest
            or self._live_authority.semantic_provider
            != config.semantic_provider
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
            and config.state_root_digest
            == self._live_authority.state_root_digest
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
            item
            for item in snapshot.semantic_reservations
            if item.repository_id == repository_id
        )
        if len(reservations) > 1:
            raise ValueError("fixed acceptance semantic reservation conflict")
        phase2_authority = (
            reservations[0].phase2_run_authority_digest
            if reservations
            else None
        )
        prior_attempts = tuple(
            item
            for item in snapshot.semantic_attempts
            if item.repository_id == repository_id
            and item.stage == "extractor"
            and (
                phase2_authority is None
                or item.workflow_authority_digest == phase2_authority
            )
        )
        prior_attempt_count = max(
            (item.attempt_no for item in prior_attempts),
            default=0,
        )
        remaining_attempts = (
            RetryPolicy().max_attempts - prior_attempt_count
        )
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
            if execution.terminal.outcome != "confirmed_retryable":
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
                nominations[0].search_derived_entries
                + nominations[0].user_nominated_entries
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
            )
            self._state_head = synchronized.commit_sha
            self._state_root = synchronized.root_digest
        execution = self._run_phase2_with_retries(
            candidate=candidate,
            pinned_commit_sha=authority.exact_commit_sha,
        )
        workflow_terminals = []
        for workflow in execution.workflows:
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
                    outcome=(
                        "eligible_local_candidate"
                        if workflow.outcome == "eligible"
                        else workflow.outcome
                    ),
                    eligible_locator=(
                        workflow.locator.locator
                        if workflow.locator is not None
                        else None
                    ),
                    eligible_object_digest=(
                        workflow.locator.authority_digest
                        if workflow.locator is not None
                        else None
                    ),
                    recorded_at=_discovery_timestamp(),
                )
            )
        candidate_terminal = self._operations.record_candidate_terminal(
            self._authority.run_id,
            execution.terminal,
        )
        operations_snapshot = self._operations.snapshot_run(
            self._authority.run_id
        )
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
        acceptance_snapshot = self._operations.acceptance_snapshot(
            self._acceptance_run_id
        )
        request_reservations = tuple(
            record
            for record in acceptance_snapshot.facts
            if record.kind == "acceptance_semantic_request_reservation"
            and record.fact.repository_id == authority.repository_id
            and record.fact.fixed_candidate_admission_digest
            == admission.admission_digest
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
        if (
            not telemetry_keys.issubset(attempt_keys)
            or any(
                attempt.status == "decided"
                and (
                    attempt.stage,
                    attempt.workflow_authority_digest,
                    attempt.attempt_no,
                )
                not in telemetry_keys
                for attempt in semantic_attempts
            )
        ):
            raise ValueError("semantic provider telemetry is incomplete")
        semantic_telemetry = tuple(
            AcceptanceSemanticTelemetryV1(
                schema_version="acceptance-semantic-telemetry-v1",
                live_acceptance_authority_digest=(
                    self._live_authority.authority_digest
                ),
                stage=item.stage,
                workflow_spec_authority_digest=(
                    item.workflow_authority_digest
                ),
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
            (
                workflow
                for workflow in workflows
                if workflow.locator is not None
            ),
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
            sorted(
                item.package_digest
                for item in workflows
                if item.package_digest is not None
            )
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
            live_acceptance_authority_digest=(
                self._live_authority.authority_digest
            ),
            discovery_run_id=self._authority.run_id,
            discovery_run_authority_digest=self._authority.authority_digest,
            benchmark_entry_digest=authority.entry_digest,
            budget_reservation_digest=(
                budget_reservation.reservation_digest
            ),
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
            workflow_execution_authority_digests=(
                workflow_execution_authority_digests
            ),
            workflow_spec_authority_digests=(
                workflow_spec_authority_digests
            ),
            phase3_terminal_summary_digests=(
                phase3_terminal_summary_digests
            ),
            skill_artifact_digests=skill_artifact_digests,
            package_digests=package_digests,
            eligible_object_digest=(
                selected_workflow.locator.authority_digest
                if selected_workflow is not None
                and selected_workflow.locator is not None
                else None
            ),
            workflow_fingerprint=(
                selected_workflow.workflow_fingerprint
                if selected_workflow is not None
                else None
            ),
            workflow_spec_authority_digest=(
                selected_workflow.workflow_spec_authority_digest
                if selected_workflow is not None
                else None
            ),
            eligible_locator=(
                selected_workflow.locator.locator
                if selected_workflow is not None
                and selected_workflow.locator is not None
                else None
            ),
            semantic_request_count=len(semantic_attempts),
            semantic_attempt_digests=tuple(
                sorted(attempt.attempt_digest for attempt in semantic_attempts)
            ),
            semantic_telemetry=semantic_telemetry,
            actual_models=tuple(
                item.actual_model for item in semantic_telemetry
            ),
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

    def factory(state_commit_sha: str, state_root_digest: str) -> object:
        lineage_reader = getattr(
            barrier,
            "acceptance_resume_lineage",
            None,
        )
        if callable(lineage_reader):
            resume_commits, resume_roots = lineage_reader()
        else:
            resume_commits = config.resume_lineage_commit_shas
            resume_roots = config.resume_lineage_root_digests
        return _FixedRepositoryAcceptanceRunner(
            config=replace(
                config,
                state_commit_sha=state_commit_sha,
                state_root_digest=state_root_digest,
                resume_lineage_commit_shas=resume_commits,
                resume_lineage_root_digests=resume_roots,
            ),
            discovery_config=discovery_config,
            barrier=barrier,
            source=source,
            frozen_owner_export=frozen_owner_export,
            acceptance_run_id=acceptance_run_id,
        )

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
    )


def build_live_acceptance_execution(
    *,
    config: object,
    restored: object,
    action: str,
    acceptance_run_id: str,
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
        ReplayUpdateDependencies,
        run_exact_replay,
        run_locked_benchmark,
    )

    source = os.environ if environ is None else environ
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
            verified_state_locators.add(
                (synchronized.commit_sha, synchronized.root_digest)
            )
        return synchronized

    if action == "replay":
        def projector_factory() -> object:
            return _CompletedBenchmarkStateProjector(
                operations_path=discovery_config.operations_state,
                pipeline_path=discovery_config.pipeline_state,
                acceptance_run_id=acceptance_run_id,
                expected_live_authority_digest=(
                    config.live_acceptance_authority_digest
                ),
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
                resume_anchor=barrier.anchor_acceptance_resume,
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
            observation = StateBranchStore(client).restore()
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
            durability_barrier=_LateStateDurabilityBarrier(config, source),
        ),
        query_set=config.query_set,  # type: ignore[arg-type]
        initial_state_root_digest=config.initial_state_root_digest,
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


def read_exact_acceptance_state(
    *,
    state_commit_sha: str,
    state_repository_id: int,
    state_repository_full_name: str,
    pipeline_state: Path,
    operations_state: Path,
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
    ):
        raise ValueError("protected acceptance state configuration rejected")
    source = os.environ if environ is None else environ
    from skillscout.adapters.operations_state import (
        restore_acceptance_state_bundle,
    )
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
        completed = projector.find_completed_candidate(
            terminal.candidate_execution_authority
        )
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
