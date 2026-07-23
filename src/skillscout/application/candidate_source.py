"""Strict candidate descriptor loading and pre-run Phase 2 source resolution."""

from __future__ import annotations

import hmac
import json
import os
import stat
from pathlib import Path
from typing import Annotated, Literal, Mapping

from pydantic import Field, ValidationError

from skillscout.application.ports import (
    CandidateSourceUnavailable,
    PhaseTwoCandidateProjection,
    PhaseTwoCandidateSource,
)
from skillscout.domain.candidate_authority import (
    CANDIDATE_DESCRIPTOR_SCHEMA_VERSION,
    CandidateSubjectDescriptorV1,
    WorkflowSpecAuthorityV1,
    workflow_spec_authority,
)
from skillscout.domain.canonical import canonical_json_bytes
from skillscout.domain.extraction import WorkflowSpec
from skillscout.domain.models import Digest, StrictFrozenModel

MAX_CANDIDATE_DESCRIPTOR_BYTES = 16_384
MAX_CANDIDATE_DESCRIPTORS = 3
RESOLVED_CANDIDATE_SOURCE_SCHEMA_VERSION = "resolved-candidate-source-v1"
_READ_CHUNK_BYTES = 8192


class ResolvedCandidateSourceV1(StrictFrozenModel):
    """The only verified structured Phase 2 facts permitted into Phase 3."""

    schema_version: Literal["resolved-candidate-source-v1"]
    descriptor: CandidateSubjectDescriptorV1
    workflow_spec_bytes: bytes
    workflow_spec_authority: WorkflowSpecAuthorityV1
    repository_id: Annotated[int, Field(ge=1, le=9_223_372_036_854_775_807)]
    repository_url: Annotated[str, Field(min_length=20, max_length=300)]
    pinned_commit_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    license_spdx: Annotated[str, Field(min_length=1, max_length=32)]


def _effective_uid() -> int:
    getter = getattr(os, "geteuid", None)
    if not callable(getter):
        raise OSError("effective owner check unavailable")
    value = getter()
    if type(value) is not int or value < 0:
        raise OSError("effective owner check unavailable")
    return value


def _require_private_regular(metadata: os.stat_result, *, effective_uid: int) -> None:
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_uid != effective_uid
        or metadata.st_mode & 0o077
    ):
        raise OSError("candidate descriptor admission failed")


def _path_fd_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
    )


def _stable_identity(
    metadata: os.stat_result,
) -> tuple[int, int, int, int, int, int, int, int, int]:
    return (
        *_path_fd_identity(metadata),
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_candidate_descriptor(path: Path) -> CandidateSubjectDescriptorV1:
    descriptor_fd = -1
    try:
        effective_uid = _effective_uid()
        before_path = os.lstat(path)
        _require_private_regular(before_path, effective_uid=effective_uid)
        if before_path.st_size > MAX_CANDIDATE_DESCRIPTOR_BYTES:
            raise OSError("candidate descriptor too large")

        flags = os.O_RDONLY
        for flag_name in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
            flags |= getattr(os, flag_name, 0)
        descriptor_fd = os.open(path, flags)
        before_fd = os.fstat(descriptor_fd)
        _require_private_regular(before_fd, effective_uid=effective_uid)
        if (
            _path_fd_identity(before_path) != _path_fd_identity(before_fd)
            or before_fd.st_size > MAX_CANDIDATE_DESCRIPTOR_BYTES
        ):
            raise OSError("candidate descriptor identity changed")

        chunks: list[bytes] = []
        consumed = 0
        while True:
            remaining = MAX_CANDIDATE_DESCRIPTOR_BYTES + 1 - consumed
            chunk = os.read(descriptor_fd, min(_READ_CHUNK_BYTES, remaining))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > MAX_CANDIDATE_DESCRIPTOR_BYTES:
                raise OSError("candidate descriptor too large")
            chunks.append(chunk)

        after_fd = os.fstat(descriptor_fd)
        _require_private_regular(after_fd, effective_uid=effective_uid)
        if _stable_identity(before_fd) != _stable_identity(after_fd):
            raise OSError("candidate descriptor changed")
        after_path = os.lstat(path)
        _require_private_regular(after_path, effective_uid=effective_uid)
        if _stable_identity(after_path) != _stable_identity(after_fd):
            raise OSError("candidate descriptor path changed")

        raw = b"".join(chunks)
        decoded = raw.decode("utf-8", errors="strict")
        parsed = json.loads(decoded)
        validated = CandidateSubjectDescriptorV1.model_validate(parsed, strict=True)
        expected = canonical_json_bytes(validated.model_dump(mode="json"))
        if raw != expected:
            raise ValueError("candidate descriptor is not canonical")
        return validated
    except CandidateSourceUnavailable:
        raise
    except (
        AttributeError,
        json.JSONDecodeError,
        MemoryError,
        OSError,
        OverflowError,
        TypeError,
        UnicodeDecodeError,
        ValidationError,
        ValueError,
    ):
        raise CandidateSourceUnavailable() from None
    finally:
        if descriptor_fd >= 0:
            try:
                os.close(descriptor_fd)
            except OSError:
                pass


def _workflow_from_projection(
    projection: PhaseTwoCandidateProjection,
) -> WorkflowSpec:
    workflow = WorkflowSpec.model_validate_json(
        projection.workflow_spec_bytes,
        strict=True,
    )
    if projection.workflow_spec_bytes != canonical_json_bytes(
        workflow.model_dump(mode="json", exclude_none=False)
    ):
        raise ValueError("Phase 2 workflow bytes are not canonical")
    return workflow


def _projection_matches_descriptor(
    projection: PhaseTwoCandidateProjection,
    descriptor: CandidateSubjectDescriptorV1,
) -> bool:
    return (
        projection.phase2_run_id == descriptor.phase2_run_id
        and hmac.compare_digest(
            projection.extractor_output_hash,
            descriptor.extractor_output_hash,
        )
        and hmac.compare_digest(
            projection.verified_chain_anchor,
            descriptor.verified_chain_anchor,
        )
    )


def load_candidate_subject(
    path: Path,
    source: PhaseTwoCandidateSource,
) -> ResolvedCandidateSourceV1:
    """Load, reverify, and completely bind one descriptor before Phase 3 exists."""

    try:
        descriptor = _read_candidate_descriptor(path)
        projection = source.resolve(descriptor)
        if not _projection_matches_descriptor(projection, descriptor):
            raise ValueError("Phase 2 projection authority mismatch")
        workflow = _workflow_from_projection(projection)
        if not hmac.compare_digest(
            workflow.fingerprint,
            descriptor.selected_workflow_fingerprint,
        ):
            raise ValueError("selected workflow fingerprint mismatch")
        authority = workflow_spec_authority(
            workflow_spec=workflow,
            phase2_extractor_output_hash=projection.extractor_output_hash,
            phase2_verified_chain_anchor=projection.verified_chain_anchor,
        )
        if not hmac.compare_digest(
            authority.authority_digest,
            descriptor.expected_workflow_spec_authority_digest,
        ):
            raise ValueError("complete WorkflowSpec authority mismatch")
        return ResolvedCandidateSourceV1(
            schema_version=RESOLVED_CANDIDATE_SOURCE_SCHEMA_VERSION,
            descriptor=descriptor,
            workflow_spec_bytes=projection.workflow_spec_bytes,
            workflow_spec_authority=authority,
            repository_id=projection.repository_id,
            repository_url=projection.repository_url,
            pinned_commit_sha=projection.pinned_commit_sha,
            license_spdx=projection.license_spdx,
        )
    except CandidateSourceUnavailable:
        raise
    except Exception:
        raise CandidateSourceUnavailable() from None


def derive_candidate_subject_descriptors(
    source: PhaseTwoCandidateSource,
    *,
    phase2_run_id: str,
    phase2_profile_version: str = "phase2-v1",
    phase2_producer_version: str = "phase2-v1",
    approved_binding_digests: Mapping[str, Digest] | None = None,
) -> tuple[CandidateSubjectDescriptorV1, ...]:
    """Reverify one completed run once, then derive sorted isolated descriptors."""

    try:
        projections = source.resolve_all(
            phase2_run_id=phase2_run_id,
            phase2_profile_version=phase2_profile_version,
            phase2_producer_version=phase2_producer_version,
        )
        bindings = dict(approved_binding_digests or {})
        descriptors: list[CandidateSubjectDescriptorV1] = []
        fingerprints: set[str] = set()
        for projection in projections:
            workflow = _workflow_from_projection(projection)
            if workflow.fingerprint in fingerprints:
                raise ValueError("duplicate workflow fingerprint")
            fingerprints.add(workflow.fingerprint)
            authority = workflow_spec_authority(
                workflow_spec=workflow,
                phase2_extractor_output_hash=projection.extractor_output_hash,
                phase2_verified_chain_anchor=projection.verified_chain_anchor,
            )
            descriptors.append(
                CandidateSubjectDescriptorV1(
                    schema_version=CANDIDATE_DESCRIPTOR_SCHEMA_VERSION,
                    phase2_run_id=projection.phase2_run_id,
                    phase2_profile_version=phase2_profile_version,
                    phase2_producer_version=phase2_producer_version,
                    extractor_output_hash=projection.extractor_output_hash,
                    verified_chain_anchor=projection.verified_chain_anchor,
                    selected_workflow_fingerprint=workflow.fingerprint,
                    expected_workflow_spec_authority_digest=authority.authority_digest,
                    prior_lineage_binding_digest=bindings.get(workflow.fingerprint),
                )
            )
        descriptors.sort(
            key=lambda item: item.selected_workflow_fingerprint.encode("ascii")
        )
        return tuple(descriptors[:MAX_CANDIDATE_DESCRIPTORS])
    except CandidateSourceUnavailable:
        raise
    except Exception:
        raise CandidateSourceUnavailable() from None
