#!/usr/bin/env python3
"""Dependency-free, read-only mechanical acceptance for Phase 3."""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import stat
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple

MAX_DIGEST_BYTES = 65
MAX_LOCK_BYTES = 2_000_000
MAX_SOURCE_BYTES = 2_000_000
MAX_PACKAGE_FILE_BYTES = 65_536
APPROVED_LOCK_SHA256 = (
    "b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004"
)
EXPECTED_VALIDATOR_RUNTIME_SHA256 = (
    "6ef6a0d4df321648c5ec967762d99e4ad9164a3d070ffae337feda890914ed36"
)
DIGEST_PATH = Path("config/supply-chain/phase3-gate-b3.lock.sha256")
LOCK_PATH = Path("uv.lock")
SOURCE_ROOT = Path("src/skillscout")
PACKAGE_FIXTURE = Path("tests/fixtures/skills/valid-skill")
SUCCESS_DIAGNOSTIC = "phase3 acceptance valid"
FAILURE_DIAGNOSTIC = "phase3 acceptance invalid"

EXPECTED_OPENAI_IMPORTERS = frozenset(
    {
        "adapters/openai_extract.py",
        "adapters/openai_generate.py",
        "adapters/openai_review.py",
    }
)
EXPECTED_SKILLS_REF_IMPORTERS = frozenset({"adapters/skills_ref.py"})
EXPECTED_CHECK_IDS = (
    "dependency_bootstrap_authority",
    "import_capability_isolation",
    "package_provenance_surface",
    "identity_and_evidence_ownership",
    "anchored_materialization",
    "completed_projection_read_only",
    "protected_contract_evidence",
)

_FORBIDDEN_PRODUCTION_IMPORTS = frozenset(
    {
        "aiohttp",
        "asyncio.subprocess",
        "github",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
)
_FORBIDDEN_CALLS = frozenset(
    {
        "compile",
        "eval",
        "exec",
        "os.popen",
        "os.system",
        "subprocess.call",
        "subprocess.Popen",
        "subprocess.run",
    }
)
_SECRET_PATTERNS = (
    re.compile(rb"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(rb"ghp_[A-Za-z0-9]{8,}"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
)


class AcceptanceError(Exception):
    """Closed failure for an invalid Phase 3 acceptance surface."""


class SecureRecord(NamedTuple):
    """Retained bytes plus complete immutable admission metadata."""

    relative_path: str
    payload: bytes
    digest: str
    metadata: tuple[int, ...]


class AuthoritySnapshot(NamedTuple):
    """Exact approved-digest and lock authority at one instant."""

    digest_record: SecureRecord
    lock_record: SecureRecord


class CheckResult(NamedTuple):
    """Result derived from one actual registered check invocation."""

    identifier: str
    count: int
    output_sha256: str


Check = Callable[[Path], tuple[str, ...]]


class CheckSpec(NamedTuple):
    """One fixed acceptance check; input cannot add registry credit."""

    identifier: str
    check: Check


def _require(condition: bool) -> None:
    if not condition:
        raise AcceptanceError


def _metadata(metadata: os.stat_result) -> tuple[int, ...]:
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


def _secure_read(repository_root: Path, relative: Path, cap: int) -> SecureRecord:
    """Read one bounded authority exactly once without following a link."""

    _require(type(cap) is int and cap >= 0)
    try:
        nofollow = os.O_NOFOLLOW
        cloexec = os.O_CLOEXEC
    except AttributeError as error:
        raise AcceptanceError from error
    _require(nofollow != 0 and cloexec != 0)
    path = repository_root / relative
    descriptor = -1
    try:
        before_path = os.lstat(path)
        _require(
            stat.S_ISREG(before_path.st_mode)
            and not stat.S_ISLNK(before_path.st_mode)
            and before_path.st_nlink == 1
            and before_path.st_uid == os.geteuid()
            and before_path.st_mode & 0o022 == 0
            and 0 <= before_path.st_size <= cap
        )
        descriptor = os.open(path, os.O_RDONLY | nofollow | cloexec)
        opened = os.fstat(descriptor)
        _require(_metadata(opened) == _metadata(before_path))
        chunks: list[bytes] = []
        consumed = 0
        while True:
            remaining = cap + 1 - consumed
            _require(remaining > 0)
            chunk = os.read(descriptor, min(8192, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            consumed += len(chunk)
            _require(consumed <= cap)
        after_descriptor = os.fstat(descriptor)
        after_path = os.lstat(path)
        _require(_metadata(opened) == _metadata(after_descriptor))
        _require(_metadata(after_descriptor) == _metadata(after_path))
        payload = b"".join(chunks)
        return SecureRecord(
            relative.as_posix(),
            payload,
            hashlib.sha256(payload).hexdigest(),
            _metadata(after_descriptor),
        )
    except (AcceptanceError, OSError, OverflowError):
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _authority_snapshot(repository_root: Path) -> AuthoritySnapshot:
    digest_record = _secure_read(repository_root, DIGEST_PATH, MAX_DIGEST_BYTES)
    _require(
        digest_record.payload
        == (APPROVED_LOCK_SHA256 + "\n").encode("ascii")
    )
    _require(re.fullmatch(rb"[0-9a-f]{64}\n", digest_record.payload) is not None)
    lock_record = _secure_read(repository_root, LOCK_PATH, MAX_LOCK_BYTES)
    _require(lock_record.digest == APPROVED_LOCK_SHA256)
    return AuthoritySnapshot(digest_record, lock_record)


def _read_source(repository_root: Path, relative: Path) -> bytes:
    return _secure_read(repository_root, relative, MAX_SOURCE_BYTES).payload


def _source_modules(repository_root: Path) -> tuple[tuple[str, Path, ast.Module], ...]:
    source_root = repository_root / SOURCE_ROOT
    root_metadata = os.lstat(source_root)
    _require(stat.S_ISDIR(root_metadata.st_mode) and not stat.S_ISLNK(root_metadata.st_mode))
    records: list[tuple[str, Path, ast.Module]] = []
    for directory, directories, filenames in os.walk(source_root, followlinks=False):
        directory_path = Path(directory)
        directories.sort()
        filenames.sort()
        for name in directories:
            metadata = os.lstat(directory_path / name)
            _require(stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode))
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = directory_path / name
            relative = path.relative_to(repository_root)
            module_relative = path.relative_to(source_root).as_posix()
            raw = _read_source(repository_root, relative)
            records.append(
                (module_relative, relative, ast.parse(raw, filename=relative.as_posix()))
            )
    records.sort(key=lambda item: item[0])
    _require(bool(records) and len(records) == len({item[0] for item in records}))
    return tuple(records)


def imported_top_level_modules(path: Path) -> set[str]:
    """Return only top-level imported distribution names from one Python file."""

    tree = ast.parse(path.read_bytes(), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    return imported


def _qualified_name(node: ast.expr, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value, aliases)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _imports_and_calls(tree: ast.Module) -> tuple[set[str], set[str]]:
    imported: set[str] = set()
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
                aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    calls = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for name in (_qualified_name(node.func, aliases),)
        if name is not None
    }
    return imported, calls


def _check_import_capability_isolation(repository_root: Path) -> tuple[str, ...]:
    openai_importers: set[str] = set()
    skills_ref_importers: set[str] = set()
    forbidden: list[str] = []
    httpx_importers: set[str] = set()
    for module_relative, _relative, tree in _source_modules(repository_root):
        imports, calls = _imports_and_calls(tree)
        for imported in imports:
            if imported == "openai" or imported.startswith("openai."):
                openai_importers.add(module_relative)
            if imported == "skills_ref" or imported.startswith("skills_ref."):
                skills_ref_importers.add(module_relative)
            if imported == "httpx" or imported.startswith("httpx."):
                httpx_importers.add(module_relative)
            if any(
                imported == blocked or imported.startswith(f"{blocked}.")
                for blocked in _FORBIDDEN_PRODUCTION_IMPORTS
            ):
                forbidden.append(f"{module_relative}:{imported}")
        forbidden.extend(
            f"{module_relative}:{call}" for call in calls if call in _FORBIDDEN_CALLS
        )
    _require(openai_importers == EXPECTED_OPENAI_IMPORTERS)
    _require(skills_ref_importers == EXPECTED_SKILLS_REF_IMPORTERS)
    _require(httpx_importers == {"adapters/github.py"})
    _require(not forbidden)

    github = _read_source(
        repository_root, SOURCE_ROOT / "adapters/github.py"
    ).decode("utf-8")
    _require(".post(" not in github and ".put(" not in github)
    _require(".patch(" not in github and ".delete(" not in github)
    cli = _read_source(repository_root, SOURCE_ROOT / "cli.py").decode("utf-8")
    for prohibited in ("publish", "merge", "mark-ready", "install-dependencies"):
        _require(prohibited not in cli)
    return (
        "exact three OpenAI importers",
        "sole skills_ref importer",
        "closed local/static production capability surface",
    )


def _gate_precedes_project_imports(tree: ast.Module) -> None:
    def gate_call(node: ast.stmt) -> ast.Call | None:
        value: ast.expr | None = None
        if isinstance(node, ast.Expr):
            value = node.value
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "require_phase3_gate_b3"
        ):
            return value
        return None

    calls = [
        index
        for index, node in enumerate(tree.body)
        if gate_call(node) is not None
    ]
    _require(len(calls) == 1)
    gate_index = calls[0]
    for index, node in enumerate(tree.body):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("skillscout.")
            and node.module != "skillscout.bootstrap"
        ):
            _require(index > gate_index)


def _check_dependency_bootstrap_authority(
    repository_root: Path,
) -> tuple[str, ...]:
    project = _secure_read(
        repository_root, Path("pyproject.toml"), MAX_SOURCE_BYTES
    ).payload.decode("utf-8")
    _require(project.count('skillscout = "skillscout.bootstrap:main"') == 1)
    _require('skillscout = "skillscout.cli:main"' not in project)

    bootstrap = _read_source(
        repository_root, SOURCE_ROOT / "bootstrap.py"
    ).decode("utf-8")
    bootstrap_tree = ast.parse(bootstrap)
    imports, calls = _imports_and_calls(bootstrap_tree)
    _require(
        not imports & {"httpx", "openai", "pydantic", "skills_ref"}
        and imports & {"skillscout.cli"} == {"skillscout.cli"}
        and "subprocess.run" not in calls
    )
    _require_tokens(
        bootstrap,
        (
            f'"{APPROVED_LOCK_SHA256}"',
            f'"{EXPECTED_VALIDATOR_RUNTIME_SHA256}"',
            "os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC",
            "class ValidatorDistributionAdmission:",
            "def _verify_validator_distribution() -> ValidatorDistributionAdmission:",
            "def reverify_admitted_validator_module(",
            "def require_phase3_gate_b3() -> ValidatorDistributionAdmission:",
            'relative == _VALIDATOR_MODULE_RECORD_PATH',
            "len(distributions) != 1",
        ),
    )

    cli_tree = ast.parse(
        _read_source(repository_root, SOURCE_ROOT / "cli.py")
    )
    adapter_tree = ast.parse(
        _read_source(repository_root, SOURCE_ROOT / "adapters/skills_ref.py")
    )
    _gate_precedes_project_imports(cli_tree)
    _gate_precedes_project_imports(adapter_tree)
    _require(
        all(
            not (
                isinstance(node, (ast.Import, ast.ImportFrom))
                and (
                    (
                        isinstance(node, ast.Import)
                        and any(
                            alias.name == "skills_ref"
                            or alias.name.startswith("skills_ref.")
                            for alias in node.names
                        )
                    )
                    or (
                        isinstance(node, ast.ImportFrom)
                        and node.module is not None
                        and (
                            node.module == "skills_ref"
                            or node.module.startswith("skills_ref.")
                        )
                    )
                )
            )
            for node in adapter_tree.body
        )
    )

    validation_tree = ast.parse(
        _read_source(repository_root, SOURCE_ROOT / "domain/validation.py")
    )
    authority_fields = _class_fields(
        validation_tree, "OfficialValidatorAuthorityV1"
    )
    _require(
        "approved_distribution_hash" in authority_fields
        and "observed_distribution_digest" in authority_fields
        and "distribution_hash" not in authority_fields
    )
    return (
        "dependency-free bootstrap is the sole console entry",
        "lock and installed-validator bytes precede project dependency imports",
        "approved wheel and observed runtime distribution remain distinct",
    )


def _class_fields(tree: ast.Module, class_name: str) -> tuple[str, ...]:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    _require(len(classes) == 1)
    return tuple(
        target.id
        for node in classes[0].body
        if isinstance(node, ast.AnnAssign)
        and isinstance((target := node.target), ast.Name)
    )


def _class_annotations(tree: ast.Module, class_name: str) -> dict[str, str]:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    _require(len(classes) == 1)
    return {
        node.target.id: ast.unparse(node.annotation)
        for node in classes[0].body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }


def _check_package_provenance_surface(repository_root: Path) -> tuple[str, ...]:
    package_root = repository_root / PACKAGE_FIXTURE
    metadata = os.lstat(package_root)
    _require(stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode))
    seen: set[str] = set()
    total = 0
    for directory, directories, filenames in os.walk(package_root, followlinks=False):
        directory_path = Path(directory)
        directories.sort()
        filenames.sort()
        for name in directories:
            child = directory_path / name
            child_metadata = os.lstat(child)
            _require(
                stat.S_ISDIR(child_metadata.st_mode)
                and not stat.S_ISLNK(child_metadata.st_mode)
                and name not in {"scripts", "bin", "__pycache__"}
            )
        for name in filenames:
            path = directory_path / name
            file_metadata = os.lstat(path)
            relative = path.relative_to(package_root).as_posix()
            _require(
                stat.S_ISREG(file_metadata.st_mode)
                and not stat.S_ISLNK(file_metadata.st_mode)
                and file_metadata.st_nlink == 1
                and stat.S_IMODE(file_metadata.st_mode) == 0o644
                and 0 < file_metadata.st_size <= MAX_PACKAGE_FILE_BYTES
            )
            raw = _read_source(repository_root, path.relative_to(repository_root))
            raw.decode("utf-8")
            _require(not any(pattern.search(raw) for pattern in _SECRET_PATTERNS))
            _require(b"allowed-tools:" not in raw.lower())
            total += len(raw)
            seen.add(relative)
    _require(
        {"SKILL.md", "references/provenance.json"}.issubset(seen)
        and not any(path.startswith("scripts/") for path in seen)
        and total <= 131_072
    )

    relative = SOURCE_ROOT / "domain/skill_artifacts.py"
    tree = ast.parse(_read_source(repository_root, relative), filename=relative.as_posix())
    provenance = set(_class_fields(tree, "PackageProvenanceV1"))
    required = {
        "generated_artifact_identity",
        "generation_authority",
        "workflow_spec_authority",
        "selected_workflow_fingerprint",
        "repository_url",
        "repository_id",
        "exact_commit_sha",
        "license_spdx",
        "source_evidence",
        "phase2_run_id",
        "phase2_verified_chain_anchor",
        "lineage_id",
        "qualification_report_digest",
        "configured_generator_model_id",
        "actual_generator_model_id",
        "generator_prompt_version",
        "generator_output_schema_version",
        "generator_policy_version",
        "generator_producer_version",
        "phase3_profile_version",
        "retry_policy_version",
        "request_id",
        "usage",
    }
    _require(required.issubset(provenance))
    _require(
        not provenance
        & {
            "package_digest",
            "review_attestation",
            "reviewer_model_id",
            "eligible",
            "terminal_summary",
            "validation_report",
        }
    )
    return (
        "documentation-only fixed-mode package tree",
        "complete generation provenance without future/self facts",
    )


def _require_tokens(source: str, tokens: Sequence[str]) -> None:
    _require(all(token in source for token in tokens))


def _check_identity_and_evidence_ownership(repository_root: Path) -> tuple[str, ...]:
    artifacts_relative = SOURCE_ROOT / "domain/skill_artifacts.py"
    artifacts_raw = _read_source(repository_root, artifacts_relative)
    artifacts = artifacts_raw.decode("utf-8")
    _require_tokens(
        artifacts,
        (
            "draft_digest = sha256_digest(canonical_json_bytes(draft))",
            "authority_digest = sha256_digest(canonical_json_bytes(authority))",
            '"generation_authority_digest": authority_digest',
            "manifest_digest = sha256_digest(canonical_json_bytes(manifest))",
            '"rendered_manifest_digest": manifest_digest',
            'paths.count("SKILL.md") != 1',
            'paths.count("references/provenance.json") != 1',
        ),
    )
    _require(
        artifacts.index("def generated_artifact_identity")
        < artifacts.index("def package_digest")
    )
    artifacts_tree = ast.parse(artifacts_raw, filename=artifacts_relative.as_posix())
    generated_fields = set(_class_fields(artifacts_tree, "GeneratedArtifactIdentityV1"))
    package_fields = set(_class_fields(artifacts_tree, "PackageIdentityV1"))
    _require(
        generated_fields == {"schema_version", "draft_digest", "generation_authority_digest", "artifact_digest"}
    )
    _require(
        package_fields == {"schema_version", "rendered_manifest_digest", "package_digest"}
    )
    _require(generated_fields.isdisjoint({"rendered_manifest_digest", "package_digest"}))

    authority_tree = ast.parse(
        _read_source(
            repository_root,
            SOURCE_ROOT / "domain/candidate_authority.py",
        )
    )
    execution_fields = set(
        _class_fields(authority_tree, "CandidateExecutionAuthorityV1")
    )
    _require(
        {
            "reviewer_retry_policy_version",
            "max_reviewer_attempts",
        }.issubset(execution_fields)
    )

    qualification_relative = SOURCE_ROOT / "domain/qualification.py"
    qualification_raw = _read_source(repository_root, qualification_relative)
    qualification_tree = ast.parse(
        qualification_raw, filename=qualification_relative.as_posix()
    )
    qualification_annotations = _class_annotations(
        qualification_tree, "QualificationReportV1"
    )
    _require(
        qualification_annotations.get("header") == "QualificationReportHeaderV1"
    )
    header_fields = set(_class_fields(qualification_tree, "QualificationReportHeaderV1"))
    _require(
        {
            "selected_workflow_fingerprint",
            "workflow_spec_authority",
            "candidate_execution_authority",
            "report_schema_version",
            "policy_version",
            "threshold_version",
        }.issubset(header_fields)
    )

    validation_relative = SOURCE_ROOT / "domain/validation.py"
    validation_raw = _read_source(repository_root, validation_relative)
    validation_tree = ast.parse(validation_raw, filename=validation_relative.as_posix())
    validation_fields = set(_class_fields(validation_tree, "ValidationReportV1"))
    _require(
        {
            "workflow_spec_authority",
            "candidate_execution_authority",
            "generated_artifact_identity",
            "package_identity",
            "package_digest",
            "report_digest",
        }.issubset(validation_fields)
    )
    validation_annotations = _class_annotations(validation_tree, "ValidationReportV1")
    _require(
        validation_annotations.get("generated_artifact_identity")
        == "GeneratedArtifactIdentityV1"
        and validation_annotations.get("package_identity") == "PackageIdentityV1"
    )

    review_relative = SOURCE_ROOT / "domain/review.py"
    review_raw = _read_source(repository_root, review_relative)
    review = review_raw.decode("utf-8")
    review_tree = ast.parse(review_raw, filename=review_relative.as_posix())
    attestation = set(_class_fields(review_tree, "ReviewAttestationV1"))
    reviewer_failures = set(
        _class_fields(review_tree, "ReviewerFailedAttemptV1")
    )
    terminal = set(_class_fields(review_tree, "CandidateTerminalSummaryV1"))
    terminal_annotations = _class_annotations(
        review_tree, "CandidateTerminalSummaryV1"
    )
    _require(
        "eligible" not in attestation
        and "eligibility_policy_version" not in attestation
        and {
            "reviewer_retry_policy_version",
            "max_reviewer_attempts",
            "attempt_count",
            "failed_attempts",
        }.issubset(attestation)
        and reviewer_failures == {"attempt_no", "error_code"}
    )
    _require(
        {
            "eligible",
            "eligibility_policy_version",
            "generator_outcome_evidence",
            "lineage_resolution",
            "review_disposition",
            "outcome",
        }.issubset(terminal)
    )
    _require(
        terminal_annotations.get("eligible") == "bool"
        and terminal_annotations.get("eligibility_policy_version")
        == "Literal['candidate-eligibility-v1']"
    )
    _require_tokens(
        review,
        (
            'ELIGIBILITY_POLICY_VERSION: Final = "candidate-eligibility-v1"',
            'REVIEW_RETRY_POLICY_VERSION: Final = "reviewer-bounded-transient-retry-v1"',
            '"not_evaluated_qualification_rejected"',
            '"review_skipped_validation_errors"',
            "expected_failed_attempts = tuple(range(1, self.attempt_count))",
            'expected_eligible = self.outcome == "eligible_local_candidate"',
        ),
    )
    phase3 = _read_source(
        repository_root, SOURCE_ROOT / "application/phase3.py"
    ).decode("utf-8")
    models = _read_source(
        repository_root, SOURCE_ROOT / "domain/models.py"
    ).decode("utf-8")
    state = _read_source(
        repository_root, SOURCE_ROOT / "adapters/state.py"
    ).decode("utf-8")
    _require_tokens(
        phase3,
        (
            "def _record_reviewer_attempt(",
            "self.state.persist_reviewer_attempt(chain)",
            'status="abandoned"',
            'error_code="attempt_interrupted"',
        ),
    )
    _require_tokens(
        models,
        (
            'attempt.status not in {"failed", "abandoned"}',
            'terminal_attempt.status != "succeeded"',
        ),
    )
    _require_tokens(
        state,
        (
            "def persist_reviewer_attempt(",
            'prior.attempts[-1].status == "running"',
            'chain.attempts[-1].status in {"failed", "abandoned", "succeeded"}',
        ),
    )
    return (
        "distinct canonical semantic and rendered identities",
        "direct qualification/validation authority headers",
        "raw attestation and terminal-only eligibility ownership",
    )


def _check_anchored_materialization(repository_root: Path) -> tuple[str, ...]:
    artifacts_relative = SOURCE_ROOT / "domain/skill_artifacts.py"
    artifacts = _read_source(repository_root, artifacts_relative).decode("utf-8")
    localfs_relative = SOURCE_ROOT / "adapters/localfs.py"
    localfs = _read_source(repository_root, localfs_relative).decode("utf-8")
    _require(artifacts.count("def materialize_skill_package(") == 1)
    _require(
        artifacts.count("os.fsync(anchor.descriptor)") == 5
        and artifacts.count("0o600") == 2
        and artifacts.count("os.rename(") == 7
    )
    _require_tokens(
        artifacts,
        (
            "AnchoredDirectory.open(",
            "_acquire_package_lock(anchor, package.stable_slug)",
            "fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)",
            "os.fchmod(descriptor, 0o644)",
            "os.fsync(descriptor)",
            "os.fsync(directory.descriptor)",
            "os.fsync(anchor.descriptor)",
            "src_dir_fd=anchor.descriptor",
            "dst_dir_fd=anchor.descriptor",
            "moved_prior",
            "moved_stage",
        ),
    )
    _require_tokens(
        localfs,
        (
            "os.O_WRONLY | os.O_CREAT | os.O_EXCL",
            "0o600",
            "os.fsync(descriptor)",
            "os.fsync(self.descriptor)",
            "_restore_after_failed_replace",
            "os.rename(",
        ),
    )
    return (
        "sole descriptor-anchored package writer",
        "retained lock, fixed modes, create-new temporary and full durability",
        "atomic prior-byte restore boundary",
    )


def _class_source(source: str, tree: ast.Module, class_name: str) -> str:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    _require(len(classes) == 1)
    segment = ast.get_source_segment(source, classes[0])
    _require(segment is not None)
    return segment


def _check_completed_projection_read_only(repository_root: Path) -> tuple[str, ...]:
    relative = SOURCE_ROOT / "adapters/state.py"
    raw = _read_source(repository_root, relative)
    source = raw.decode("utf-8")
    tree = ast.parse(raw, filename=relative.as_posix())
    projector = _class_source(
        source, tree, "DescriptorAnchoredCompletedCandidateProjector"
    )
    _require_tokens(
        projector,
        (
            "flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC",
            "fcntl.flock(lock_descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)",
            "_read_stable_private_file(",
            'sqlite3.connect(":memory:", isolation_level=None)',
            "connection.deserialize(payload)",
            'connection.execute("PRAGMA query_only = ON")',
            "artifact_anchor = AnchoredDirectory.open(",
        ),
    )
    for prohibited in (
        "SQLiteStateStore(",
        "sqlite3.connect(self.path",
        ".serialize(",
        "atomic_write(",
        "materialize_skill_package(",
        "os.mkdir(",
        "os.rename(",
        "os.unlink(",
        "os.write(",
        "os.fsync(",
    ):
        _require(prohibited not in projector)
    return (
        "existing retained shared lock and O_RDONLY descriptor snapshot",
        "query-only private-memory SQLite projection",
        "descriptor artifact reads with no mutation primitive",
    )


_REQUIRED_TEST_FUNCTIONS: dict[Path, frozenset[str]] = {
    Path("tests/test_state_integrity.py"): frozenset(
        {
            "test_new_state_lock_backup_temporary_and_manifest_files_are_private",
            "test_state_uses_private_memory_sqlite_and_one_reusable_live_lock",
            "test_parent_swap_after_state_anchor_cannot_redirect_state_or_manifests",
            "test_pre_commit_snapshot_failure_restores_prior_authority",
            "test_post_commit_backup_cleanup_failure_returns_success_and_reopen_observes_mutation",
            "test_recover_stale_temporary_removes_private_temp_and_fsyncs_directory",
            "test_symlinked_output_directory_is_rejected_without_external_write",
        }
    ),
    Path("tests/test_phase3_pipeline.py"): frozenset(
        {
            "test_exact_reuse_projects_admitted_bytes_without_any_path_mutation",
            "test_exact_reuse_exact_authority_miss_is_clean_and_releases_lock",
            "test_exact_reuse_rejects_tampered_completed_chain_without_fallback",
            "test_exact_reuse_rejects_each_external_artifact_byte_mutation",
            "test_exact_reuse_rejects_external_digest_mutation",
            "test_exact_reuse_existing_state_requires_the_retained_lock",
            "test_exact_reuse_clean_running_miss_releases_descriptors_for_durable_resume",
            "test_exact_reuse_covers_every_terminal_branch_with_exact_full_tree_snapshot",
            "test_resume_budgets_completed_application_reuse_bypasses_every_mutable_factory",
            "test_resume_budgets_authority_mutation_is_a_clean_completed_miss",
            "test_reviewer_retry_resume_preserves_durable_failure_history",
            "test_reviewer_inflight_attempt_is_abandoned_and_consumes_budget_on_resume",
            "test_reviewer_retry_exhaustion_is_durable_across_restarts",
        }
    ),
    Path("tests/test_phase1_gap_closure.py"): frozenset(
        {
            "test_phase3_acceptance_protects_repository_subject_and_loader_contract",
            "test_phase3_acceptance_protects_phase_two_processor_contract",
            "test_phase3_acceptance_protects_pipeline_profiles_exactly",
            "test_phase3_acceptance_protects_verify_run_chain_signature_and_delegation",
        }
    ),
    Path("tests/test_phase2_pipeline.py"): frozenset(
        {
            "test_profiles_are_closed_prefix_slices_with_declared_terminals",
            "test_completed_phase_two_run_is_fully_reused_without_reexecution",
        }
    ),
}


def _check_protected_contract_evidence(repository_root: Path) -> tuple[str, ...]:
    for relative, required in _REQUIRED_TEST_FUNCTIONS.items():
        tree = ast.parse(_read_source(repository_root, relative), filename=relative.as_posix())
        definitions = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        _require(required.issubset(definitions))
    pipeline = _read_source(
        repository_root, SOURCE_ROOT / "application/pipeline.py"
    ).decode("utf-8")
    _require_tokens(
        pipeline,
        (
            'PIPELINE_PROFILES: Final[dict[str, PipelineProfile]] = {',
            '"fixture-v1": PipelineProfile(',
            '"phase2-v1": PipelineProfile(',
        ),
    )
    _require(pipeline.count('"phase2-v1": PipelineProfile(') == 1)
    subjects = _read_source(
        repository_root, SOURCE_ROOT / "domain/subjects.py"
    ).decode("utf-8")
    loader = _read_source(
        repository_root, SOURCE_ROOT / "adapters/subjects.py"
    ).decode("utf-8")
    processors = _read_source(
        repository_root, SOURCE_ROOT / "application/processors.py"
    ).decode("utf-8")
    state = _read_source(repository_root, SOURCE_ROOT / "adapters/state.py").decode(
        "utf-8"
    )
    _require_tokens(subjects, ("class RepositorySubject(", "schema_version: Literal[\"1\"]"))
    _require_tokens(loader, ("def load_subject(path: Path)", "os.O_RDONLY"))
    _require_tokens(
        processors,
        (
            "class PhaseTwoProcessor:",
            'producer_version = "phase2-v1"',
            "def process(self, stage_input: StageInput, context: StageContext)",
        ),
    )
    _require_tokens(
        state,
        (
            "def verify_run_chain(",
            "return self._verify_run_chain(self._db, run_id, expected_identity)",
        ),
    )
    return (
        "named materialization and all-branch exact-reuse evidence",
        "protected Phase 1/2 subjects, processor, profiles and verifier seams",
    )


CHECK_REGISTRY = (
    CheckSpec(
        "dependency_bootstrap_authority",
        _check_dependency_bootstrap_authority,
    ),
    CheckSpec("import_capability_isolation", _check_import_capability_isolation),
    CheckSpec("package_provenance_surface", _check_package_provenance_surface),
    CheckSpec("identity_and_evidence_ownership", _check_identity_and_evidence_ownership),
    CheckSpec("anchored_materialization", _check_anchored_materialization),
    CheckSpec("completed_projection_read_only", _check_completed_projection_read_only),
    CheckSpec("protected_contract_evidence", _check_protected_contract_evidence),
)


def _run_registered_checks(repository_root: Path) -> tuple[CheckResult, ...]:
    identifiers = tuple(spec.identifier for spec in CHECK_REGISTRY)
    _require(identifiers == EXPECTED_CHECK_IDS)
    _require(len(identifiers) == len(set(identifiers)))
    results: list[CheckResult] = []
    for spec in CHECK_REGISTRY:
        output = spec.check(repository_root)
        _require(
            type(output) is tuple
            and bool(output)
            and all(type(line) is str and line and "\n" not in line for line in output)
        )
        encoded = ("\n".join(output) + "\n").encode("utf-8")
        results.append(
            CheckResult(
                spec.identifier,
                len(output),
                hashlib.sha256(encoded).hexdigest(),
            )
        )
    _require(
        tuple(result.identifier for result in results) == EXPECTED_CHECK_IDS
        and all(result.count > 0 for result in results)
        and all(re.fullmatch(r"[0-9a-f]{64}", result.output_sha256) for result in results)
    )
    return tuple(results)


def verify_phase3_acceptance(repository_root: Path) -> None:
    """Verify exact lock authority, then every fixed read-only Phase 3 check."""

    root = Path(os.path.abspath(os.fspath(repository_root)))
    _require(stat.S_ISDIR(os.lstat(root).st_mode))
    before = _authority_snapshot(root)
    results = _run_registered_checks(root)
    _require(tuple(result.identifier for result in results) == EXPECTED_CHECK_IDS)
    after = _authority_snapshot(root)
    _require(after == before)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repository-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments:
            namespace = _parser().parse_args(arguments)
            _require(namespace.repository_root is not None)
            root = namespace.repository_root
        else:
            root = Path(__file__).resolve().parents[1]
        verify_phase3_acceptance(root)
    except (
        AcceptanceError,
        OSError,
        OverflowError,
        UnicodeError,
        SyntaxError,
        SystemExit,
        ValueError,
        TypeError,
    ):
        print(FAILURE_DIAGNOSTIC, file=sys.stderr)
        return 1
    print(SUCCESS_DIAGNOSTIC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
