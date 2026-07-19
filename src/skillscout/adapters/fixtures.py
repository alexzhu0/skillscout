"""Bounded, single-descriptor fixture input and deterministic processors."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.enums import EffectScope
from skillscout.domain.models import StageInput

MAX_FIXTURE_BYTES = 65_536
FixtureId = Annotated[
    str,
    Field(min_length=9, max_length=128, pattern=r"^fixture:[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
RepositoryUrl = Annotated[
    str,
    Field(
        min_length=20,
        max_length=300,
        pattern=r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$",
    ),
]
CommitSha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
BoundedText = Annotated[str, Field(min_length=1, max_length=4096)]
BoundedToken = Annotated[str, Field(min_length=1, max_length=160)]
BoundedTokens = Annotated[list[BoundedToken], Field(max_length=64)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FixtureSource(_StrictModel):
    repository: RepositoryUrl
    commit_sha: CommitSha
    license: Literal["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]


class FixtureWorkflow(_StrictModel):
    goal: BoundedText
    inputs: BoundedTokens
    steps: BoundedTokens
    outputs: BoundedTokens


class FixtureSubject(_StrictModel):
    schema_version: Literal["1"]
    subject_id: FixtureId
    source: FixtureSource
    workflow: FixtureWorkflow


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def load_fixture(path: Path) -> FixtureSubject:
    """Read one regular file descriptor, then strictly validate its bounded JSON."""

    descriptor = -1
    try:
        before_path = os.lstat(path)
        if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(before_path.st_mode):
            raise SafeFailure(ErrorCode.INVALID_FIXTURE)

        flags = os.O_RDONLY
        for flag_name in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
            flags |= getattr(os, flag_name, 0)
        descriptor = os.open(path, flags)

        before_fd = os.fstat(descriptor)
        if not stat.S_ISREG(before_fd.st_mode):
            raise SafeFailure(ErrorCode.INVALID_FIXTURE)
        if (before_path.st_dev, before_path.st_ino) != (before_fd.st_dev, before_fd.st_ino):
            raise SafeFailure(ErrorCode.FIXTURE_CHANGED)
        if before_fd.st_size > MAX_FIXTURE_BYTES:
            raise SafeFailure(ErrorCode.INVALID_FIXTURE)

        chunks: list[bytes] = []
        consumed = 0
        while True:
            chunk = os.read(descriptor, min(8192, MAX_FIXTURE_BYTES + 1 - consumed))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > MAX_FIXTURE_BYTES:
                raise SafeFailure(ErrorCode.INVALID_FIXTURE)
            chunks.append(chunk)

        after_fd = os.fstat(descriptor)
        if _identity(before_fd) != _identity(after_fd):
            raise SafeFailure(ErrorCode.FIXTURE_CHANGED)

        raw = b"".join(chunks)
        try:
            decoded = raw.decode("utf-8")
            parsed: Any = json.loads(decoded)
            return FixtureSubject.model_validate(parsed, strict=True)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            raise SafeFailure(ErrorCode.INVALID_FIXTURE) from None
    except SafeFailure:
        raise
    except (OSError, OverflowError):
        raise SafeFailure(ErrorCode.INVALID_FIXTURE) from None
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


class FixtureProcessor:
    """Deterministic local processor with no provider or execution capability."""

    producer_version = "fixture-v1"

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.NONE

    def process(
        self,
        stage_input: StageInput,
    ) -> dict[str, object]:
        return {
            "schema_version": stage_input.schema_version,
            "stage": stage_input.stage.value,
            "subject_id": stage_input.subject_id,
            "previous_output_hash": stage_input.previous_output_hash,
            "outcome": (
                "accepted"
                if stage_input.stage.value != "publication_planner"
                else "planned_not_published"
            ),
        }
