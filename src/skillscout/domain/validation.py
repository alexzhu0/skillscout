"""Deterministic admission and normalized validation contracts for frozen Skills."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Callable, Final, Iterator, Literal

from pydantic import Field, model_validator

from skillscout.domain.candidate_authority import (
    CandidateExecutionAuthorityV1,
    WorkflowSpecAuthorityV1,
)
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel
from skillscout.domain.skill_artifacts import (
    GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION,
    MAX_RENDERED_FILE_BYTES,
    MAX_RENDERED_PACKAGE_BYTES,
    PROVENANCE_SCHEMA_VERSION,
    RENDERER_VERSION,
    FrozenSkillPackageV1,
    GeneratedArtifactIdentityV1,
    PackageIdentityV1,
    PackageProvenanceV1,
    RenderedFileV1,
    RenderedPackageManifestV1,
    package_digest,
)

WORKSPACE_ADMISSION_SCHEMA_VERSION: Final = "workspace-admission-v1"
OFFICIAL_VALIDATOR_AUTHORITY_SCHEMA_VERSION: Final = (
    "official-validator-authority-v1"
)
OFFICIAL_VALIDATION_RESULT_SCHEMA_VERSION: Final = "official-validation-result-v1"
VALIDATION_FINDING_SCHEMA_VERSION: Final = "validation-finding-v1"
OFFICIAL_VALIDATOR_ADAPTER_VERSION: Final = "skills-ref-adapter-v1"
OFFICIAL_VALIDATOR_DISTRIBUTION: Final = "skills-ref"
OFFICIAL_VALIDATOR_VERSION: Final = "0.1.1"
OFFICIAL_VALIDATOR_DISTRIBUTION_HASH: Final = (
    "sha256:d35db5bb8de71ae301daf5ca9cb71f8a555e8c6f83a6d40e46a5bc09f8f461b5"
)
APPROVED_PHASE3_LOCK_DIGEST: Final = (
    "sha256:b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004"
)
LOCAL_STRUCTURE_POLICY_VERSION: Final = "local-structure-v1"
PROGRESSIVE_DISCLOSURE_POLICY_VERSION: Final = "progressive-disclosure-v1"
LOCAL_SAFETY_POLICY_VERSION: Final = "local-safety-v1"
LOCAL_PROVENANCE_POLICY_VERSION: Final = "local-provenance-v1"
URL_POLICY_VERSION: Final = "local-url-v1"
OVERCOPY_POLICY_VERSION: Final = "overcopy-policy-v1"
CUSTOM_VALIDATION_POLICY_VERSION: Final = "local-validation-policy-v1"
VALIDATION_REPORT_SCHEMA_VERSION: Final = "validation-report-v1"
MAX_SKILL_LINES: Final = 500
MAX_SKILL_ESTIMATED_TOKENS: Final = 5_000
MAX_REGISTERED_QUOTE_CHARS: Final = 120
MAX_TOTAL_REGISTERED_QUOTE_CHARS: Final = 240
MIN_UNREGISTERED_SOURCE_MATCH_CHARS: Final = 80

_Severity = Literal["error", "warning", "info"]
_Version = Annotated[str, Field(min_length=1, max_length=128)]
_Code = Annotated[
    str,
    Field(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_]*$"),
]
_Location = Annotated[str, Field(min_length=1, max_length=256)]
_Message = Annotated[str, Field(min_length=1, max_length=160)]
FilesystemSeam = Callable[[str, Path], None]


class WorkspaceAdmissionError(Exception):
    """Closed internal failure raised before third-party validation can run."""


class ValidationFindingV1(StrictFrozenModel):
    """One bounded, stable, non-echoing validation observation."""

    schema_version: Literal["validation-finding-v1"] = VALIDATION_FINDING_SCHEMA_VERSION
    severity: _Severity
    code: _Code
    location: _Location
    message: _Message
    validator_version: _Version


class WorkspaceAdmissionV1(StrictFrozenModel):
    """Exact frozen-manifest facts proven immediately before validation."""

    schema_version: Literal["workspace-admission-v1"]
    admitted: Literal[True]
    manifest_digest: Digest
    package_digest: Digest
    file_count: Annotated[int, Field(ge=2, le=16)]
    total_bytes: Annotated[int, Field(ge=1, le=MAX_RENDERED_PACKAGE_BYTES)]


class OfficialValidatorAuthorityV1(StrictFrozenModel):
    """Separate approved wheel, observed installation, and lock authorities."""

    schema_version: Literal["official-validator-authority-v1"]
    distribution: Literal["skills-ref"]
    version: Literal["0.1.1"]
    approved_distribution_hash: Digest
    observed_distribution_digest: Digest
    approved_lock_digest: Digest
    adapter_version: Literal["skills-ref-adapter-v1"]


class OfficialValidationResultV1(StrictFrozenModel):
    """Fail-closed official result over one admitted private workspace."""

    schema_version: Literal["official-validation-result-v1"]
    infrastructure_succeeded: bool
    passed: bool
    admission: WorkspaceAdmissionV1 | None
    authority: OfficialValidatorAuthorityV1
    findings: Annotated[tuple[ValidationFindingV1, ...], Field(max_length=64)]

    @model_validator(mode="after")
    def validate_result_gate(self) -> OfficialValidationResultV1:
        expected = (
            self.infrastructure_succeeded
            and self.admission is not None
            and not any(finding.severity == "error" for finding in self.findings)
        )
        if self.passed is not expected:
            raise ValueError("official validation pass flag is inconsistent")
        if self.infrastructure_succeeded != (self.admission is not None):
            raise ValueError("official validation admission state is inconsistent")
        return self


class ValidationReportV1(StrictFrozenModel):
    """Complete immutable authority and finding gate over one frozen package."""

    schema_version: Literal["validation-report-v1"]
    validation_report_schema_version: Literal["validation-report-v1"]
    selected_workflow_fingerprint: Digest
    workflow_spec_authority: WorkflowSpecAuthorityV1
    candidate_execution_authority: CandidateExecutionAuthorityV1
    renderer_version: Literal["skill-renderer-v1"]
    generated_artifact_identity: GeneratedArtifactIdentityV1
    package_identity: PackageIdentityV1
    package_digest: Digest
    workspace_admission: WorkspaceAdmissionV1 | None
    official_validator_authority: OfficialValidatorAuthorityV1
    official_infrastructure_succeeded: bool
    custom_validation_policy_version: Literal["local-validation-policy-v1"]
    local_structure_policy_version: Literal["local-structure-v1"]
    progressive_disclosure_policy_version: Literal["progressive-disclosure-v1"]
    local_safety_policy_version: Literal["local-safety-v1"]
    local_provenance_policy_version: Literal["local-provenance-v1"]
    url_policy_version: Literal["local-url-v1"]
    overcopy_policy_version: Literal["overcopy-policy-v1"]
    findings: Annotated[tuple[ValidationFindingV1, ...], Field(max_length=256)]
    error_count: Annotated[int, Field(ge=0, le=256)]
    warning_count: Annotated[int, Field(ge=0, le=256)]
    info_count: Annotated[int, Field(ge=0, le=256)]
    passed: bool
    report_digest: Digest

    @model_validator(mode="after")
    def validate_complete_report(self) -> ValidationReportV1:
        execution = CandidateExecutionAuthorityV1.model_validate(
            self.candidate_execution_authority.model_dump(
                mode="python",
                exclude_none=False,
            )
        )
        if (
            self.workflow_spec_authority != execution.workflow_spec_authority
            or self.selected_workflow_fingerprint
            != execution.selected_workflow_fingerprint
            or self.selected_workflow_fingerprint
            != self.workflow_spec_authority.workflow_spec.fingerprint
            or execution.renderer_version != self.renderer_version
            or execution.artifact_schema_version
            != self.generated_artifact_identity.schema_version
            or execution.provenance_schema_version != PROVENANCE_SCHEMA_VERSION
            or execution.official_validator_distribution
            != self.official_validator_authority.distribution
            or execution.official_validator_version
            != self.official_validator_authority.version
            or execution.official_validator_distribution_hash
            != self.official_validator_authority.approved_distribution_hash
            or execution.approved_lock_digest
            != self.official_validator_authority.approved_lock_digest
            or execution.custom_validation_policy_version
            != self.custom_validation_policy_version
            or execution.validation_report_schema_version
            != self.validation_report_schema_version
            or self.package_digest != self.package_identity.package_digest
        ):
            raise ValueError("validation report authority bindings disagree")
        if self.official_infrastructure_succeeded != (
            self.workspace_admission is not None
        ):
            raise ValueError("validation report workspace state is inconsistent")
        if (
            self.workspace_admission is not None
            and (
                self.workspace_admission.package_digest != self.package_digest
                or self.workspace_admission.manifest_digest
                != self.package_identity.rendered_manifest_digest
            )
        ):
            raise ValueError("validation report admission identity disagrees")

        identities = tuple(
            (
                finding.severity,
                finding.code,
                finding.location,
                finding.validator_version,
            )
            for finding in self.findings
        )
        if len(identities) != len(set(identities)):
            raise ValueError("validation report contains duplicate finding identities")
        ordered = tuple(
            sorted(
                self.findings,
                key=lambda finding: (
                    finding.severity,
                    finding.code,
                    finding.location,
                    finding.message,
                    finding.validator_version,
                ),
            )
        )
        if self.findings != ordered:
            raise ValueError("validation report findings are not canonically ordered")
        counts = {
            severity: sum(
                finding.severity == severity for finding in self.findings
            )
            for severity in ("error", "warning", "info")
        }
        if (
            self.error_count != counts["error"]
            or self.warning_count != counts["warning"]
            or self.info_count != counts["info"]
        ):
            raise ValueError("validation report counts are inconsistent")
        expected_passed = (
            self.official_infrastructure_succeeded
            and self.workspace_admission is not None
            and self.error_count == 0
        )
        if self.passed is not expected_passed:
            raise ValueError("validation report pass gate is inconsistent")
        expected_digest = sha256_digest(
            self.model_dump(
                mode="json",
                exclude_none=False,
                exclude={"report_digest"},
            )
        )
        if self.report_digest != expected_digest:
            raise ValueError("validation report digest mismatch")
        return self


def official_validator_authority(
    *,
    observed_distribution_digest: str,
) -> OfficialValidatorAuthorityV1:
    """Bind immutable approval to an independently verified runtime digest."""

    return OfficialValidatorAuthorityV1(
        schema_version=OFFICIAL_VALIDATOR_AUTHORITY_SCHEMA_VERSION,
        distribution=OFFICIAL_VALIDATOR_DISTRIBUTION,
        version=OFFICIAL_VALIDATOR_VERSION,
        approved_distribution_hash=OFFICIAL_VALIDATOR_DISTRIBUTION_HASH,
        observed_distribution_digest=observed_distribution_digest,
        approved_lock_digest=APPROVED_PHASE3_LOCK_DIGEST,
        adapter_version=OFFICIAL_VALIDATOR_ADAPTER_VERSION,
    )


def _closed_rendered_path(value: str) -> PurePosixPath:
    if (
        type(value) is not str
        or not value
        or len(value) > 256
        or "\\" in value
        or "\x00" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise WorkspaceAdmissionError
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
        or len(path.parts) not in {1, 2}
        or (len(path.parts) == 1 and value != "SKILL.md")
        or (
            len(path.parts) == 2
            and path.parts[0] not in {"references", "assets"}
        )
    ):
        raise WorkspaceAdmissionError
    return path


def _validated_package_files(
    package: FrozenSkillPackageV1,
) -> tuple[RenderedFileV1, ...]:
    if type(package) is not FrozenSkillPackageV1:
        raise WorkspaceAdmissionError
    try:
        files = tuple(
            RenderedFileV1.model_validate(
                rendered.model_dump(mode="python", exclude_none=False)
            )
            for rendered in package.files
        )
        for rendered in files:
            _closed_rendered_path(rendered.path)
        paths = tuple(rendered.path for rendered in files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise WorkspaceAdmissionError
        manifest = RenderedPackageManifestV1.from_files(files)
        if manifest != package.rendered_manifest:
            raise WorkspaceAdmissionError
        if package_digest(manifest) != package.package_identity:
            raise WorkspaceAdmissionError
        if sum(len(rendered.content) for rendered in files) > MAX_RENDERED_PACKAGE_BYTES:
            raise WorkspaceAdmissionError
    except (AttributeError, TypeError, ValueError):
        raise WorkspaceAdmissionError from None
    return files


def _write_all(descriptor: int, content: bytes) -> None:
    offset = 0
    while offset < len(content):
        written = os.write(descriptor, content[offset:])
        if written <= 0:
            raise WorkspaceAdmissionError
        offset += written


def _materialize_workspace(root: Path, files: tuple[RenderedFileV1, ...]) -> None:
    root_descriptor = -1
    directory_descriptors: dict[str, int] = {}
    try:
        root_descriptor = os.open(
            root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        required_directories = sorted(
            {PurePosixPath(rendered.path).parts[0] for rendered in files}
            - {"SKILL.md"}
        )
        for name in required_directories:
            os.mkdir(name, 0o700, dir_fd=root_descriptor)
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=root_descriptor,
            )
            directory_descriptors[name] = descriptor
        for rendered in files:
            path = PurePosixPath(rendered.path)
            parent_descriptor = (
                root_descriptor
                if len(path.parts) == 1
                else directory_descriptors[path.parts[0]]
            )
            descriptor = os.open(
                path.name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                0o600,
                dir_fd=parent_descriptor,
            )
            try:
                _write_all(descriptor, rendered.content)
                os.fchmod(descriptor, 0o644)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        for descriptor in directory_descriptors.values():
            os.fsync(descriptor)
        os.fsync(root_descriptor)
    except (KeyError, OSError):
        raise WorkspaceAdmissionError from None
    finally:
        for descriptor in directory_descriptors.values():
            os.close(descriptor)
        if root_descriptor >= 0:
            os.close(root_descriptor)


def _actual_workspace_entries(root: Path) -> tuple[str, ...]:
    entries: list[str] = []
    try:
        for first in os.scandir(root):
            entries.append(first.name)
            metadata = first.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                for second in os.scandir(first.path):
                    entries.append(f"{first.name}/{second.name}")
                    second_metadata = second.stat(follow_symlinks=False)
                    if stat.S_ISDIR(second_metadata.st_mode):
                        raise WorkspaceAdmissionError
    except OSError:
        raise WorkspaceAdmissionError from None
    return tuple(sorted(entries))


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_mode,
        left.st_nlink,
        left.st_uid,
        left.st_size,
        left.st_mtime_ns,
        left.st_ctime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
        right.st_nlink,
        right.st_uid,
        right.st_size,
        right.st_mtime_ns,
        right.st_ctime_ns,
    )


def _read_exact_admitted_file(
    root: Path,
    rendered: RenderedFileV1,
    *,
    filesystem_seam: FilesystemSeam | None,
) -> bytes:
    path = root.joinpath(*PurePosixPath(rendered.path).parts)
    descriptor = -1
    try:
        before = os.lstat(path)
        if filesystem_seam is not None:
            filesystem_seam(f"after_lstat:{rendered.path}", root)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o644
            or before.st_size != len(rendered.content)
            or before.st_size > MAX_RENDERED_FILE_BYTES
        ):
            raise WorkspaceAdmissionError
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        opened = os.fstat(descriptor)
        if not _same_file_identity(before, opened):
            raise WorkspaceAdmissionError
        chunks: list[bytes] = []
        consumed = 0
        while True:
            chunk = os.read(descriptor, min(8192, MAX_RENDERED_FILE_BYTES + 1 - consumed))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > MAX_RENDERED_FILE_BYTES:
                raise WorkspaceAdmissionError
            chunks.append(chunk)
        content = b"".join(chunks)
        after_descriptor = os.fstat(descriptor)
        after_path = os.lstat(path)
        if (
            not _same_file_identity(opened, after_descriptor)
            or not _same_file_identity(after_descriptor, after_path)
            or len(content) != len(rendered.content)
            or b"\x00" in content
        ):
            raise WorkspaceAdmissionError
        content.decode("utf-8")
        if content != rendered.content or sha256_digest(content) != sha256_digest(
            rendered.content
        ):
            raise WorkspaceAdmissionError
        return content
    except (OSError, UnicodeDecodeError):
        raise WorkspaceAdmissionError from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _verify_workspace(
    root: Path,
    package: FrozenSkillPackageV1,
    files: tuple[RenderedFileV1, ...],
    *,
    filesystem_seam: FilesystemSeam | None,
) -> WorkspaceAdmissionV1:
    expected_files = {rendered.path for rendered in files}
    expected_directories = {
        PurePosixPath(rendered.path).parts[0]
        for rendered in files
        if len(PurePosixPath(rendered.path).parts) == 2
    }
    if set(_actual_workspace_entries(root)) != expected_files | expected_directories:
        raise WorkspaceAdmissionError
    try:
        root_metadata = os.lstat(root)
        if (
            not stat.S_ISDIR(root_metadata.st_mode)
            or stat.S_ISLNK(root_metadata.st_mode)
            or root_metadata.st_uid != os.geteuid()
            or stat.S_IMODE(root_metadata.st_mode) != 0o700
        ):
            raise WorkspaceAdmissionError
        for directory in expected_directories:
            metadata = os.lstat(root / directory)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or stat.S_IMODE(metadata.st_mode) != 0o700
            ):
                raise WorkspaceAdmissionError
        for rendered in files:
            _read_exact_admitted_file(
                root,
                rendered,
                filesystem_seam=filesystem_seam,
            )
    except OSError:
        raise WorkspaceAdmissionError from None
    return WorkspaceAdmissionV1(
        schema_version=WORKSPACE_ADMISSION_SCHEMA_VERSION,
        admitted=True,
        manifest_digest=package.package_identity.rendered_manifest_digest,
        package_digest=package.package_identity.package_digest,
        file_count=len(files),
        total_bytes=sum(len(rendered.content) for rendered in files),
    )


@dataclass(frozen=True)
class AdmittedSkillWorkspace:
    """Private ephemeral workspace plus its exact repeatable admission proof."""

    root: Path
    admission: WorkspaceAdmissionV1
    _package: FrozenSkillPackageV1
    _files: tuple[RenderedFileV1, ...]
    _filesystem_seam: FilesystemSeam | None

    def reverify(self) -> WorkspaceAdmissionV1:
        admission = _verify_workspace(
            self.root,
            self._package,
            self._files,
            filesystem_seam=self._filesystem_seam,
        )
        if admission != self.admission:
            raise WorkspaceAdmissionError
        return admission


@contextmanager
def admitted_skill_workspace(
    package: FrozenSkillPackageV1,
    *,
    filesystem_seam: FilesystemSeam | None = None,
) -> Iterator[AdmittedSkillWorkspace]:
    """Materialize and admit exact package bytes in a private disposable tree."""

    files = _validated_package_files(package)
    with tempfile.TemporaryDirectory(prefix="skillscout-validator-") as temporary:
        temporary_root = Path(temporary)
        os.chmod(temporary_root, 0o700)
        skill_root = temporary_root / package.stable_slug
        try:
            os.mkdir(skill_root, 0o700)
            _materialize_workspace(skill_root, files)
            if filesystem_seam is not None:
                filesystem_seam("after_workspace_materialized", skill_root)
            admission = _verify_workspace(
                skill_root,
                package,
                files,
                filesystem_seam=filesystem_seam,
            )
            yield AdmittedSkillWorkspace(
                root=skill_root,
                admission=admission,
                _package=package,
                _files=files,
                _filesystem_seam=filesystem_seam,
            )
        except OSError:
            raise WorkspaceAdmissionError from None


def secure_sha256_file(path: Path, *, max_bytes: int) -> tuple[bytes, str]:
    """Read one owned regular non-linked file through a stable no-follow descriptor."""

    descriptor = -1
    try:
        before = os.lstat(path)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) & 0o022
            or before.st_size < 0
            or before.st_size > max_bytes
        ):
            raise WorkspaceAdmissionError
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened = os.fstat(descriptor)
        if not _same_file_identity(before, opened):
            raise WorkspaceAdmissionError
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        consumed = 0
        while True:
            chunk = os.read(descriptor, min(8192, max_bytes + 1 - consumed))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > max_bytes:
                raise WorkspaceAdmissionError
            chunks.append(chunk)
            digest.update(chunk)
        after_descriptor = os.fstat(descriptor)
        after_path = os.lstat(path)
        if not _same_file_identity(opened, after_descriptor) or not _same_file_identity(
            after_descriptor, after_path
        ):
            raise WorkspaceAdmissionError
        return b"".join(chunks), digest.hexdigest()
    except OSError:
        raise WorkspaceAdmissionError from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def normalize_official_problems(
    problems: list[str],
) -> tuple[ValidationFindingV1, ...]:
    """Map only actual skills-ref problems into a closed capability vocabulary."""

    normalized: list[ValidationFindingV1] = []
    mappings = (
        (re.compile(r"name", re.IGNORECASE), "official_invalid_name", "Skill name is invalid."),
        (
            re.compile(r"frontmatter|yaml|metadata", re.IGNORECASE),
            "official_invalid_frontmatter",
            "Skill frontmatter is invalid.",
        ),
        (
            re.compile(r"description", re.IGNORECASE),
            "official_invalid_description",
            "Skill description is invalid.",
        ),
        (
            re.compile(r"missing required file", re.IGNORECASE),
            "official_missing_skill_md",
            "The required SKILL.md file is missing.",
        ),
    )
    for problem in problems:
        if type(problem) is not str or not problem or len(problem) > 4096:
            raise WorkspaceAdmissionError
        code = "official_validation_error"
        message = "The official validator rejected the Skill."
        for pattern, mapped_code, mapped_message in mappings:
            if pattern.search(problem):
                code = mapped_code
                message = mapped_message
                break
        normalized.append(
            ValidationFindingV1(
                severity="error",
                code=code,
                location="SKILL.md",
                message=message,
                validator_version=OFFICIAL_VALIDATOR_ADAPTER_VERSION,
            )
        )
    return tuple(
        sorted(
            normalized,
            key=lambda finding: (
                finding.code,
                finding.location,
                finding.message,
                finding.validator_version,
            ),
        )
    )


def _finding(
    *,
    code: str,
    location: str,
    message: str,
    version: str,
    severity: _Severity = "error",
) -> ValidationFindingV1:
    return ValidationFindingV1(
        severity=severity,
        code=code,
        location=location[:256] or "package",
        message=message,
        validator_version=version,
    )


def _sort_findings(
    findings: list[ValidationFindingV1],
) -> tuple[ValidationFindingV1, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.severity,
                finding.code,
                finding.location,
                finding.message,
                finding.validator_version,
            ),
        )
    )


def _report_json_preimage(values: dict[str, object]) -> dict[str, object]:
    converted: dict[str, object] = {}
    for key, value in values.items():
        if hasattr(value, "model_dump"):
            converted[key] = value.model_dump(mode="json", exclude_none=False)
        elif isinstance(value, tuple):
            converted[key] = [
                item.model_dump(mode="json", exclude_none=False)
                if hasattr(item, "model_dump")
                else item
                for item in value
            ]
        else:
            converted[key] = value
    return converted


def _raw_files(package: FrozenSkillPackageV1) -> tuple[object, ...]:
    try:
        files = tuple(package.files)
    except (AttributeError, TypeError):
        return ()
    return files


def _file_values(rendered: object) -> tuple[str, bytes, int] | None:
    try:
        path = rendered.path
        content = rendered.content
        mode = rendered.mode
    except AttributeError:
        return None
    if type(path) is not str or type(content) is not bytes or type(mode) is not int:
        return None
    return path, content, mode


def _decoded_files(package: FrozenSkillPackageV1) -> dict[str, str]:
    decoded: dict[str, str] = {}
    for rendered in _raw_files(package):
        values = _file_values(rendered)
        if values is None:
            continue
        path, content, _ = values
        try:
            decoded[path] = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
    return decoded


def _frontmatter_name(skill_text: str) -> str | None:
    if not skill_text.startswith("---\n"):
        return None
    end = skill_text.find("\n---\n", 4)
    if end < 0:
        return None
    block = skill_text[4:end]
    match = re.search(r"^name:\s*(.+?)\s*$", block, re.MULTILINE)
    description = re.search(r"^description:\s*(.+?)\s*$", block, re.MULTILINE)
    if match is None or description is None:
        return None
    raw_name = match.group(1)
    try:
        parsed = json.loads(raw_name)
    except json.JSONDecodeError:
        parsed = raw_name
    if type(parsed) is not str or not parsed:
        return None
    return parsed


_MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]\r\n]{1,256}\]\(([^)\r\n]{1,512})\)")


def _internal_links(text: str) -> tuple[str, ...]:
    links: list[str] = []
    for match in _MARKDOWN_LINK.finditer(text):
        target = match.group(1).strip()
        if (
            not target
            or target.startswith("#")
            or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
            or target.startswith("//")
        ):
            continue
        links.append(target.split("#", 1)[0])
    return tuple(links)


def validate_local_structure(
    package: FrozenSkillPackageV1,
) -> tuple[ValidationFindingV1, ...]:
    """Check the structure and disclosure rules that skills-ref does not cover."""

    findings: list[ValidationFindingV1] = []
    decoded = _decoded_files(package)
    paths = {
        values[0]
        for rendered in _raw_files(package)
        if (values := _file_values(rendered)) is not None
    }
    skill_text = decoded.get("SKILL.md")
    if skill_text is None:
        findings.append(
            _finding(
                code="structure_missing_skill_md",
                location="SKILL.md",
                message="The package lacks a readable SKILL.md.",
                version=LOCAL_STRUCTURE_POLICY_VERSION,
            )
        )
    else:
        name = _frontmatter_name(skill_text)
        if name is None:
            findings.append(
                _finding(
                    code="structure_invalid_frontmatter",
                    location="SKILL.md",
                    message="The expected bounded frontmatter is invalid.",
                    version=LOCAL_STRUCTURE_POLICY_VERSION,
                )
            )
        elif name != getattr(package, "stable_slug", None):
            findings.append(
                _finding(
                    code="structure_name_mismatch",
                    location="SKILL.md",
                    message="The Skill name does not match its stable package slug.",
                    version=LOCAL_STRUCTURE_POLICY_VERSION,
                )
            )

        referenced: set[str] = set()
        for target in _internal_links(skill_text):
            try:
                normalized = PurePosixPath(target)
                if (
                    normalized.is_absolute()
                    or target != normalized.as_posix()
                    or any(part in {"", ".", ".."} for part in normalized.parts)
                ):
                    raise ValueError
                target_path = normalized.as_posix()
            except (TypeError, ValueError):
                target_path = target
            referenced.add(target_path)
            if target_path not in paths:
                findings.append(
                    _finding(
                        code="structure_broken_reference",
                        location="SKILL.md",
                        message="SKILL.md contains a broken internal resource reference.",
                        version=LOCAL_STRUCTURE_POLICY_VERSION,
                    )
                )

        for path in sorted(paths - {"SKILL.md", "references/provenance.json"}):
            parts = PurePosixPath(path).parts
            if (
                len(parts) != 2
                or parts[0] not in {"references", "assets"}
                or any(part in {"", ".", ".."} for part in parts)
            ):
                findings.append(
                    _finding(
                        code="structure_resource_depth",
                        location=path,
                        message="A resource is outside the single-layer package grammar.",
                        version=LOCAL_STRUCTURE_POLICY_VERSION,
                    )
                )
            if path not in referenced:
                findings.append(
                    _finding(
                        code="structure_orphan_resource",
                        location=path,
                        message="A package resource is not referenced by SKILL.md.",
                        version=LOCAL_STRUCTURE_POLICY_VERSION,
                    )
                )

        for path, text in sorted(decoded.items()):
            if path == "SKILL.md":
                continue
            if _internal_links(text):
                findings.append(
                    _finding(
                        code="structure_nested_reference",
                        location=path,
                        message="A resource links to another resource layer.",
                        version=LOCAL_STRUCTURE_POLICY_VERSION,
                    )
                )

        if len(skill_text.splitlines()) > MAX_SKILL_LINES:
            findings.append(
                _finding(
                    code="progressive_skill_too_long",
                    location="SKILL.md",
                    message="SKILL.md exceeds the progressive-disclosure line limit.",
                    version=PROGRESSIVE_DISCLOSURE_POLICY_VERSION,
                )
            )
        estimated_tokens = (len(skill_text.encode("utf-8")) + 3) // 4
        if estimated_tokens > MAX_SKILL_ESTIMATED_TOKENS:
            findings.append(
                _finding(
                    code="progressive_skill_token_budget",
                    location="SKILL.md",
                    message="SKILL.md exceeds the progressive-disclosure token estimate.",
                    version=PROGRESSIVE_DISCLOSURE_POLICY_VERSION,
                )
            )
        required_sections = ("# Overview", "## Procedure")
        if any(section not in skill_text for section in required_sections):
            findings.append(
                _finding(
                    code="progressive_required_section_missing",
                    location="SKILL.md",
                    message="SKILL.md lacks a required progressive-disclosure section.",
                    version=PROGRESSIVE_DISCLOSURE_POLICY_VERSION,
                )
            )
    return _sort_findings(findings)


def _normalize_comparison_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _policy_text_findings(
    *,
    path: str,
    text: str,
    allowed_urls: set[str],
) -> list[ValidationFindingV1]:
    findings: list[ValidationFindingV1] = []
    normalized = _normalize_comparison_text(text)
    secret_patterns = (
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b", re.IGNORECASE),
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\b(?:password|api[_-]?key)\s*[:=]\s*\S+", re.IGNORECASE),
    )
    if any(pattern.search(text) for pattern in secret_patterns):
        findings.append(
            _finding(
                code="policy_secret_shape",
                location=path,
                message="A secret-shaped value is present.",
                version=LOCAL_SAFETY_POLICY_VERSION,
            )
        )

    dangerous_patterns = (
        r"\bsudo\b",
        r"\brm\s+-rf\b",
        r"\bchmod\s+\+x\b",
        r"\b(?:pip|npm|pnpm|yarn)\s+install\b",
        r"\b(?:eval|exec)\s*\(",
        r"\b(?:merge|approve|publish)\s+(?:the\s+)?(?:pr|pull request|release)\b",
    )
    if any(re.search(pattern, normalized) for pattern in dangerous_patterns):
        findings.append(
            _finding(
                code="policy_dangerous_command",
                location=path,
                message="A dangerous command or privileged action is present.",
                version=LOCAL_SAFETY_POLICY_VERSION,
            )
        )

    unauthorized_patterns = (
        "allowed-tools",
        "bypass approval",
        "access credentials",
        "enable network",
        "pre-approved tool",
    )
    if any(marker in normalized for marker in unauthorized_patterns):
        findings.append(
            _finding(
                code="policy_unauthorized_tool",
                location=path,
                message="An unauthorized tool or approval grant is present.",
                version=LOCAL_SAFETY_POLICY_VERSION,
            )
        )

    download_execute = (
        re.search(r"\b(?:curl|wget)\b[^\r\n]{0,512}\|\s*(?:ba)?sh\b", normalized)
        or "download and execute" in normalized
        or re.search(r"\bfetch\b[^\r\n]{0,256}\bthen\s+run\b", normalized)
    )
    if download_execute:
        findings.append(
            _finding(
                code="policy_download_execute",
                location=path,
                message="A download-and-execute sequence is present.",
                version=LOCAL_SAFETY_POLICY_VERSION,
            )
        )

    injection_markers = (
        "ignore previous instructions",
        "ignore prior instructions",
        "act as system",
        "<system>",
        "</system>",
        "developer message",
        "reveal the prompt",
    )
    injection_controls = ("\u202a", "\u202b", "\u202d", "\u202e", "\u2066", "\u2067")
    if any(marker in normalized for marker in injection_markers) or any(
        marker in text for marker in injection_controls
    ):
        findings.append(
            _finding(
                code="policy_injection_residue",
                location=path,
                message="Prompt-injection residue is present.",
                version=LOCAL_SAFETY_POLICY_VERSION,
            )
        )

    urls = re.findall(r"https?://[^\s\"'<>)}\]]+", text)
    if any(url.rstrip(".,") not in allowed_urls for url in urls):
        findings.append(
            _finding(
                code="policy_unapproved_url",
                location=path,
                message="A URL is outside the provenance allowlist.",
                version=URL_POLICY_VERSION,
            )
        )

    if "```" in text or re.search(r"\b(?:eval|exec)\s*\(", normalized):
        findings.append(
            _finding(
                code="policy_executable_content",
                location=path,
                message="Executable or code-fenced content is forbidden.",
                version=LOCAL_SAFETY_POLICY_VERSION,
            )
        )
    return findings


def _file_policy_findings(
    package: FrozenSkillPackageV1,
) -> list[ValidationFindingV1]:
    findings: list[ValidationFindingV1] = []
    for rendered in _raw_files(package):
        values = _file_values(rendered)
        if values is None:
            findings.append(
                _finding(
                    code="policy_invalid_file_contract",
                    location="package",
                    message="A rendered file contract is malformed.",
                    version=LOCAL_SAFETY_POLICY_VERSION,
                )
            )
            continue
        path, content, mode = values
        parts = PurePosixPath(path).parts
        if "scripts" in parts:
            findings.append(
                _finding(
                    code="policy_forbidden_scripts",
                    location=path,
                    message="The documentation-only package contains scripts.",
                    version=LOCAL_SAFETY_POLICY_VERSION,
                )
            )
        if mode != 0o644:
            findings.append(
                _finding(
                    code="policy_executable_mode",
                    location=path,
                    message="A package leaf does not use the fixed non-executable mode.",
                    version=LOCAL_SAFETY_POLICY_VERSION,
                )
            )
        try:
            content.decode("utf-8")
            if b"\x00" in content:
                raise UnicodeDecodeError("utf-8", b"", 0, 1, "binary")
        except UnicodeDecodeError:
            findings.append(
                _finding(
                    code="policy_binary_content",
                    location=path,
                    message="Binary package content is forbidden.",
                    version=LOCAL_SAFETY_POLICY_VERSION,
                )
            )
    return findings


def _provenance_findings(
    package: FrozenSkillPackageV1,
) -> list[ValidationFindingV1]:
    findings: list[ValidationFindingV1] = []
    files = {
        values[0]: values[1]
        for rendered in _raw_files(package)
        if (values := _file_values(rendered)) is not None
    }
    provenance_bytes = files.get("references/provenance.json")
    if provenance_bytes is None:
        return [
            _finding(
                code="provenance_missing",
                location="references/provenance.json",
                message="The required machine-readable provenance is missing.",
                version=LOCAL_PROVENANCE_POLICY_VERSION,
            )
        ]
    try:
        decoded = json.loads(provenance_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return [
            _finding(
                code="provenance_invalid",
                location="references/provenance.json",
                message="The machine-readable provenance is invalid.",
                version=LOCAL_PROVENANCE_POLICY_VERSION,
            )
        ]
    expected = getattr(package, "provenance", None)
    if (
        type(decoded) is not dict
        or expected is None
        or decoded.get("exact_commit_sha") != getattr(expected, "exact_commit_sha", None)
        or decoded.get("repository_id") != getattr(expected, "repository_id", None)
        or decoded.get("repository_url") != getattr(expected, "repository_url", None)
        or decoded.get("license_spdx") != getattr(expected, "license_spdx", None)
        or decoded.get("selected_workflow_fingerprint")
        != getattr(expected, "selected_workflow_fingerprint", None)
        or decoded.get("source_evidence")
        != [
            item.model_dump(mode="json", exclude_none=False)
            for item in getattr(expected, "source_evidence", ())
        ]
    ):
        findings.append(
            _finding(
                code="provenance_authority_mismatch",
                location="references/provenance.json",
                message="Provenance disagrees with verified generation authority.",
                version=LOCAL_PROVENANCE_POLICY_VERSION,
            )
        )
    try:
        parsed = PackageProvenanceV1.model_validate_json(provenance_bytes)
        if parsed != expected:
            raise ValueError
    except (TypeError, ValueError):
        if not any(
            finding.code == "provenance_authority_mismatch" for finding in findings
        ):
            findings.append(
                _finding(
                    code="provenance_authority_mismatch",
                    location="references/provenance.json",
                    message="Provenance disagrees with verified generation authority.",
                    version=LOCAL_PROVENANCE_POLICY_VERSION,
                )
            )

    raw_valid_files: list[RenderedFileV1] = []
    try:
        for rendered in _raw_files(package):
            values = _file_values(rendered)
            if values is None:
                raise ValueError
            raw_valid_files.append(
                RenderedFileV1.model_validate(
                    {
                        "path": values[0],
                        "content": values[1],
                        "mode": values[2],
                        "is_symlink": getattr(rendered, "is_symlink", False),
                    }
                )
            )
        recomputed_manifest = RenderedPackageManifestV1.from_files(
            tuple(raw_valid_files)
        )
        if (
            recomputed_manifest != package.rendered_manifest
            or package_digest(recomputed_manifest) != package.package_identity
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        findings.append(
            _finding(
                code="provenance_manifest_mismatch",
                location="package",
                message="Package path, hash, size, mode, or identity facts disagree.",
                version=LOCAL_PROVENANCE_POLICY_VERSION,
            )
        )
    return findings


def _overcopy_findings(
    package: FrozenSkillPackageV1,
    decoded: dict[str, str],
) -> list[ValidationFindingV1]:
    findings: list[ValidationFindingV1] = []
    provenance = getattr(package, "provenance", None)
    quotes = tuple(getattr(provenance, "quotes", ()))
    quote_lengths = [len(getattr(quote, "text", "")) for quote in quotes]
    if any(length > MAX_REGISTERED_QUOTE_CHARS for length in quote_lengths):
        findings.append(
            _finding(
                code="overcopy_quote_too_long",
                location="SKILL.md",
                message="A registered quote exceeds the per-item project limit.",
                version=OVERCOPY_POLICY_VERSION,
            )
        )
    if sum(quote_lengths) > MAX_TOTAL_REGISTERED_QUOTE_CHARS:
        findings.append(
            _finding(
                code="overcopy_total_quote_budget",
                location="SKILL.md",
                message="Registered quotes exceed the total project limit.",
                version=OVERCOPY_POLICY_VERSION,
            )
        )
    exact_commit = getattr(provenance, "exact_commit_sha", None)
    evidence = tuple(getattr(provenance, "source_evidence", ()))
    if any(
        getattr(quote, "commit_sha", None) != exact_commit
        or not any(
            getattr(item, "path", None) == getattr(quote, "source_path", None)
            and getattr(quote, "text", "") in getattr(item, "excerpt", "")
            for item in evidence
        )
        for quote in quotes
    ):
        findings.append(
            _finding(
                code="overcopy_quote_attribution_mismatch",
                location="SKILL.md",
                message="A registered quote lacks exact source and commit attribution.",
                version=OVERCOPY_POLICY_VERSION,
            )
        )
    registered = {
        (
            getattr(quote, "source_path", None),
            getattr(quote, "commit_sha", None),
            _normalize_comparison_text(getattr(quote, "text", "")),
        )
        for quote in quotes
    }
    corpus = _normalize_comparison_text(
        "\n".join(
            text
            for path, text in sorted(decoded.items())
            if path != "references/provenance.json"
        )
    )
    for item in evidence:
        source_path = getattr(item, "path", None)
        excerpt = _normalize_comparison_text(getattr(item, "excerpt", ""))
        if (
            (source_path, exact_commit, excerpt) in registered
            or len(excerpt) < MIN_UNREGISTERED_SOURCE_MATCH_CHARS
        ):
            continue
        if any(
            excerpt[index : index + MIN_UNREGISTERED_SOURCE_MATCH_CHARS] in corpus
            for index in range(
                len(excerpt) - MIN_UNREGISTERED_SOURCE_MATCH_CHARS + 1
            )
        ):
            findings.append(
                _finding(
                    code="overcopy_unregistered_source_match",
                    location="SKILL.md",
                    message="An unregistered source match reaches the project limit.",
                    version=OVERCOPY_POLICY_VERSION,
                )
            )
            break
    return findings


def validate_local_policy(
    package: FrozenSkillPackageV1,
) -> tuple[ValidationFindingV1, ...]:
    """Run pure safety, provenance, URL, and over-copy policy checks."""

    findings = _file_policy_findings(package)
    decoded = _decoded_files(package)
    provenance = getattr(package, "provenance", None)
    repository_url = getattr(provenance, "repository_url", None)
    allowed_urls = {repository_url} if type(repository_url) is str else set()
    for path, text in sorted(decoded.items()):
        findings.extend(
            _policy_text_findings(
                path=path,
                text=text,
                allowed_urls=allowed_urls,
            )
        )
    findings.extend(_provenance_findings(package))
    findings.extend(_overcopy_findings(package, decoded))
    return _sort_findings(findings)


def build_validation_report(
    *,
    package: FrozenSkillPackageV1,
    candidate_execution_authority: CandidateExecutionAuthorityV1,
    official_result: OfficialValidationResultV1,
    local_structure_findings: tuple[ValidationFindingV1, ...],
    local_policy_findings: tuple[ValidationFindingV1, ...],
) -> ValidationReportV1:
    """Compose one strict report after independently validating every direct link."""

    if (
        type(package) is not FrozenSkillPackageV1
        or type(candidate_execution_authority) is not CandidateExecutionAuthorityV1
        or type(official_result) is not OfficialValidationResultV1
        or type(local_structure_findings) is not tuple
        or type(local_policy_findings) is not tuple
    ):
        raise TypeError("validation report requires strict input contracts")
    try:
        frozen = FrozenSkillPackageV1.model_validate(
            package.model_dump(mode="python", exclude_none=False)
        )
        execution = CandidateExecutionAuthorityV1.model_validate(
            candidate_execution_authority.model_dump(
                mode="python",
                exclude_none=False,
            )
        )
        official = OfficialValidationResultV1.model_validate(
            official_result.model_dump(mode="python", exclude_none=False)
        )
    except (AttributeError, TypeError, ValueError):
        raise ValueError("validation report input contract failed verification") from None

    provenance = frozen.provenance
    direct_pairs = (
        (execution.workflow_spec_authority, provenance.workflow_spec_authority),
        (
            execution.selected_workflow_fingerprint,
            provenance.selected_workflow_fingerprint,
        ),
        (
            execution.configured_generator_model_id,
            provenance.configured_generator_model_id,
        ),
        (execution.generator_prompt_version, provenance.generator_prompt_version),
        (
            execution.generator_output_schema_version,
            provenance.generator_output_schema_version,
        ),
        (execution.generator_policy_version, provenance.generator_policy_version),
        (execution.renderer_version, provenance.renderer_version),
        (execution.artifact_schema_version, provenance.artifact_schema_version),
        (execution.provenance_schema_version, provenance.provenance_schema_version),
        (execution.phase3_profile_version, provenance.phase3_profile_version),
        (execution.retry_policy_version, provenance.retry_policy_version),
        (official.authority.distribution, execution.official_validator_distribution),
        (official.authority.version, execution.official_validator_version),
        (
            official.authority.approved_distribution_hash,
            execution.official_validator_distribution_hash,
        ),
        (official.authority.approved_lock_digest, execution.approved_lock_digest),
    )
    if (
        any(left != right for left, right in direct_pairs)
        or execution.renderer_version != RENDERER_VERSION
        or execution.artifact_schema_version
        != GENERATED_ARTIFACT_IDENTITY_SCHEMA_VERSION
        or execution.provenance_schema_version != PROVENANCE_SCHEMA_VERSION
        or execution.custom_validation_policy_version
        != CUSTOM_VALIDATION_POLICY_VERSION
        or execution.validation_report_schema_version
        != VALIDATION_REPORT_SCHEMA_VERSION
        or frozen.generated_artifact_identity
        != provenance.generated_artifact_identity
        or frozen.package_identity.package_digest
        != getattr(official.admission, "package_digest", frozen.package_identity.package_digest)
        or frozen.package_identity.rendered_manifest_digest
        != getattr(
            official.admission,
            "manifest_digest",
            frozen.package_identity.rendered_manifest_digest,
        )
    ):
        raise ValueError("validation report direct authority mismatch")

    allowed_structure_versions = {
        LOCAL_STRUCTURE_POLICY_VERSION,
        PROGRESSIVE_DISCLOSURE_POLICY_VERSION,
    }
    allowed_policy_versions = {
        LOCAL_SAFETY_POLICY_VERSION,
        LOCAL_PROVENANCE_POLICY_VERSION,
        URL_POLICY_VERSION,
        OVERCOPY_POLICY_VERSION,
    }
    if any(
        type(finding) is not ValidationFindingV1
        or finding.validator_version not in allowed_structure_versions
        for finding in local_structure_findings
    ):
        raise ValueError("local structural finding authority mismatch")
    if any(
        type(finding) is not ValidationFindingV1
        or finding.validator_version not in allowed_policy_versions
        for finding in local_policy_findings
    ):
        raise ValueError("local policy finding authority mismatch")
    if any(
        finding.validator_version != OFFICIAL_VALIDATOR_ADAPTER_VERSION
        for finding in official.findings
    ):
        raise ValueError("official finding authority mismatch")

    findings = _sort_findings(
        [
            *official.findings,
            *local_structure_findings,
            *local_policy_findings,
        ]
    )
    identities = tuple(
        (
            finding.severity,
            finding.code,
            finding.location,
            finding.validator_version,
        )
        for finding in findings
    )
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate validation finding identity")
    error_count = sum(finding.severity == "error" for finding in findings)
    warning_count = sum(finding.severity == "warning" for finding in findings)
    info_count = sum(finding.severity == "info" for finding in findings)
    preimage: dict[str, object] = {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "validation_report_schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "selected_workflow_fingerprint": execution.selected_workflow_fingerprint,
        "workflow_spec_authority": execution.workflow_spec_authority,
        "candidate_execution_authority": execution,
        "renderer_version": RENDERER_VERSION,
        "generated_artifact_identity": frozen.generated_artifact_identity,
        "package_identity": frozen.package_identity,
        "package_digest": frozen.package_identity.package_digest,
        "workspace_admission": official.admission,
        "official_validator_authority": official.authority,
        "official_infrastructure_succeeded": official.infrastructure_succeeded,
        "custom_validation_policy_version": CUSTOM_VALIDATION_POLICY_VERSION,
        "local_structure_policy_version": LOCAL_STRUCTURE_POLICY_VERSION,
        "progressive_disclosure_policy_version": (
            PROGRESSIVE_DISCLOSURE_POLICY_VERSION
        ),
        "local_safety_policy_version": LOCAL_SAFETY_POLICY_VERSION,
        "local_provenance_policy_version": LOCAL_PROVENANCE_POLICY_VERSION,
        "url_policy_version": URL_POLICY_VERSION,
        "overcopy_policy_version": OVERCOPY_POLICY_VERSION,
        "findings": findings,
        "error_count": error_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "passed": (
            official.infrastructure_succeeded
            and official.admission is not None
            and error_count == 0
        ),
    }
    return ValidationReportV1(
        **preimage,
        report_digest=sha256_digest(_report_json_preimage(preimage)),
    )
