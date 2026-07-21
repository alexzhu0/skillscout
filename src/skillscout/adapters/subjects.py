"""Bounded single-descriptor loader for the repository subject input."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.subjects import RepositorySubject

MAX_SUBJECT_BYTES = 65_536


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def load_subject(path: Path) -> RepositorySubject:
    """Read one regular file descriptor, then strictly validate its bounded JSON."""

    descriptor = -1
    try:
        before_path = os.lstat(path)
        if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(before_path.st_mode):
            raise SafeFailure(ErrorCode.INVALID_SUBJECT)

        flags = os.O_RDONLY
        for flag_name in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
            flags |= getattr(os, flag_name, 0)
        descriptor = os.open(path, flags)

        before_fd = os.fstat(descriptor)
        if not stat.S_ISREG(before_fd.st_mode):
            raise SafeFailure(ErrorCode.INVALID_SUBJECT)
        if (before_path.st_dev, before_path.st_ino) != (before_fd.st_dev, before_fd.st_ino):
            raise SafeFailure(ErrorCode.INVALID_SUBJECT)
        if before_fd.st_size > MAX_SUBJECT_BYTES:
            raise SafeFailure(ErrorCode.INVALID_SUBJECT)

        chunks: list[bytes] = []
        consumed = 0
        while True:
            chunk = os.read(descriptor, min(8192, MAX_SUBJECT_BYTES + 1 - consumed))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > MAX_SUBJECT_BYTES:
                raise SafeFailure(ErrorCode.INVALID_SUBJECT)
            chunks.append(chunk)

        after_fd = os.fstat(descriptor)
        if _identity(before_fd) != _identity(after_fd):
            raise SafeFailure(ErrorCode.INVALID_SUBJECT)

        raw = b"".join(chunks)
        try:
            decoded = raw.decode("utf-8")
            parsed: Any = json.loads(decoded)
            return RepositorySubject.model_validate(parsed, strict=True)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            raise SafeFailure(ErrorCode.INVALID_SUBJECT) from None
    except SafeFailure:
        raise
    except (OSError, OverflowError):
        raise SafeFailure(ErrorCode.INVALID_SUBJECT) from None
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
