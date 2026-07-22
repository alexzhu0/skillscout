"""Closed reader-policy-v1 budgets, tiers, allowlists, and path predicates."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from skillscout.domain.models import StrictFrozenModel

READER_POLICY_VERSION = "reader-policy-v1"

MAX_PATH_CHARS = 512
MAX_PATH_DEPTH = 8

LFS_POINTER_PREFIX = "version https://git-lfs.github.com/spec/v1"

MANIFEST_FILENAMES = frozenset(
    {
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "setup.py",
        "setup.cfg",
        "package.json",
        "Cargo.toml",
        "go.mod",
    }
)
DOCUMENTATION_EXTENSIONS = frozenset({".md", ".rst", ".txt"})
SOURCE_EXTENSION = ".py"
SOURCE_ROOTS = frozenset({"src", "lib"})

READER_ORG_MAX_FILES = 25
READER_ORG_MAX_SOURCE_FILES = 5
READER_ORG_MAX_FILE_BYTES = 131_072
READER_ORG_MAX_TOTAL_BYTES = 524_288
READER_ORG_MAX_TOKENS = 40_000
READER_ORG_MAX_EARLY_STOP_SOFT_TOKENS = 24_000


class ReadTier(StrEnum):
    README = "readme"
    DOCS = "docs"
    EXAMPLES = "examples"
    MANIFESTS = "manifests"
    SOURCE = "source"


TIER_ORDER: tuple[ReadTier, ...] = (
    ReadTier.README,
    ReadTier.DOCS,
    ReadTier.EXAMPLES,
    ReadTier.MANIFESTS,
    ReadTier.SOURCE,
)


class StopReason(StrEnum):
    SOFT_TARGET_REACHED = "soft_target_reached"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANDIDATES_EXHAUSTED = "candidates_exhausted"
    NO_ALLOWLISTED_FILES = "no_allowlisted_files"


class RejectionRule(StrEnum):
    SUBMODULE = "submodule"
    SYMLINK = "symlink"
    PATH_VIOLATION = "path_violation"
    NON_ALLOWLISTED_EXTENSION = "non_allowlisted_extension"
    OVER_BUDGET_SIZE = "over_budget_size"
    BINARY_CONTENT = "binary_content"
    LFS_POINTER = "lfs_pointer"


class ReaderPolicy(StrictFrozenModel):
    """The frozen per-run reading budgets, never above organization ceilings."""

    max_files: Annotated[int, Field(ge=0)] = READER_ORG_MAX_FILES
    max_source_files: Annotated[int, Field(ge=0)] = READER_ORG_MAX_SOURCE_FILES
    max_file_bytes: Annotated[int, Field(ge=0)] = READER_ORG_MAX_FILE_BYTES
    max_total_bytes: Annotated[int, Field(ge=0)] = READER_ORG_MAX_TOTAL_BYTES
    max_estimated_input_tokens: Annotated[int, Field(ge=0)] = READER_ORG_MAX_TOKENS
    early_stop_soft_tokens: Annotated[int, Field(ge=0)] = READER_ORG_MAX_EARLY_STOP_SOFT_TOKENS

    @model_validator(mode="after")
    def validate_within_org_ceilings(self) -> ReaderPolicy:
        ceilings = (
            ("max_files", self.max_files, READER_ORG_MAX_FILES),
            ("max_source_files", self.max_source_files, READER_ORG_MAX_SOURCE_FILES),
            ("max_file_bytes", self.max_file_bytes, READER_ORG_MAX_FILE_BYTES),
            ("max_total_bytes", self.max_total_bytes, READER_ORG_MAX_TOTAL_BYTES),
            (
                "max_estimated_input_tokens",
                self.max_estimated_input_tokens,
                READER_ORG_MAX_TOKENS,
            ),
            (
                "early_stop_soft_tokens",
                self.early_stop_soft_tokens,
                READER_ORG_MAX_EARLY_STOP_SOFT_TOKENS,
            ),
        )
        for name, value, ceiling in ceilings:
            if value > ceiling:
                raise ValueError(f"{name} exceeds the organization ceiling")
        return self


def validate_repo_path(path: str) -> bool:
    """Return whether one tree-relative path stays inside the closed shape."""

    if not path or len(path) > MAX_PATH_CHARS:
        return False
    if path.startswith("/") or "\\" in path:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        return False
    # Framing metacharacters could forge the untrusted prompt envelope's
    # quoted attributes or <<<...>>> delimiters downstream.
    if any(char in path for char in ('"', "<", ">", "`")):
        return False
    segments = path.split("/")
    if len(segments) > MAX_PATH_DEPTH:
        return False
    return all(segment not in {"", ".."} for segment in segments)


def assign_tier(path: str) -> ReadTier | None:
    """Classify one tree path into its fixed reader tier, if any."""

    segments = path.split("/")
    name = segments[-1]
    if len(segments) == 1:
        if name.lower().startswith("readme"):
            return ReadTier.README
        if name in MANIFEST_FILENAMES:
            return ReadTier.MANIFESTS
        if name.endswith(SOURCE_EXTENSION):
            return ReadTier.SOURCE
        return None
    first = segments[0]
    if first == "docs":
        return ReadTier.DOCS
    if first == "examples":
        return ReadTier.EXAMPLES
    if first in SOURCE_ROOTS and name.endswith(SOURCE_EXTENSION):
        return ReadTier.SOURCE
    return None


def is_allowlisted_for_tier(tier: ReadTier, path: str) -> bool:
    """Return whether a tier-classified path matches that tier's closed allowlist."""

    name = path.rsplit("/", 1)[-1]
    lowered = name.lower()
    if tier in (ReadTier.README, ReadTier.DOCS, ReadTier.EXAMPLES):
        return any(lowered.endswith(extension) for extension in DOCUMENTATION_EXTENSIONS)
    if tier is ReadTier.MANIFESTS:
        return name in MANIFEST_FILENAMES
    segments = path.split("/")
    return lowered.endswith(SOURCE_EXTENSION) and (
        len(segments) == 1 or segments[0] in SOURCE_ROOTS
    )


def estimate_tokens(byte_count: int) -> int:
    """Estimate input tokens as ceil(bytes / 4) without a tokenizer dependency."""

    if byte_count < 0:
        raise ValueError("byte count must not be negative")
    return -(-byte_count // 4)
