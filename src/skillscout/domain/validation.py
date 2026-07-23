"""Deterministic admission and normalized validation contracts for frozen Skills."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Callable, Final, Iterator, Literal

from pydantic import Field, model_validator

from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel
from skillscout.domain.skill_artifacts import (
    MAX_RENDERED_FILE_BYTES,
    MAX_RENDERED_PACKAGE_BYTES,
    FrozenSkillPackageV1,
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
    """The approved installed distribution and lock authorities."""

    schema_version: Literal["official-validator-authority-v1"]
    distribution: Literal["skills-ref"]
    version: Literal["0.1.1"]
    distribution_hash: Digest
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


def official_validator_authority() -> OfficialValidatorAuthorityV1:
    """Return the immutable Gate-B3-approved official validator authority."""

    return OfficialValidatorAuthorityV1(
        schema_version=OFFICIAL_VALIDATOR_AUTHORITY_SCHEMA_VERSION,
        distribution=OFFICIAL_VALIDATOR_DISTRIBUTION,
        version=OFFICIAL_VALIDATOR_VERSION,
        distribution_hash=OFFICIAL_VALIDATOR_DISTRIBUTION_HASH,
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
