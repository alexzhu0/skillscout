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
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, NoReturn

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


class PhaseThreeGateError(RuntimeError):
    """Sanitized fail-closed pre-import dependency authority failure."""


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
    environ: dict[str, str] | None = None,
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


def _publication_projection(
    *, candidate: Path, phase2_state: Path, phase3_state: Path
) -> tuple[object, object]:
    """Resolve Phase 2 and project only an exact completed Phase 3 candidate."""

    from skillscout.adapters.phase2_state import SQLitePhaseTwoCandidateSource
    from skillscout.adapters.state import DescriptorAnchoredCompletedCandidateProjector
    from skillscout.application.candidate_source import load_candidate_subject
    from skillscout.application.phase3 import PhaseThreeRuntimeProfile, _execution_authority
    from skillscout.application.ports import CandidateSourceUnavailable, ErrorCode, SafeFailure

    try:
        resolved = load_candidate_subject(candidate, SQLitePhaseTwoCandidateSource(phase2_state))
        authority = _execution_authority(source=resolved, profile=PhaseThreeRuntimeProfile())
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
