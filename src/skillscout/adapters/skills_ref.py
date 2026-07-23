"""Sole import and invocation boundary for the approved skills-ref validator."""

# ruff: noqa: E402

from __future__ import annotations

from skillscout.bootstrap import require_phase3_gate_b3

_OBSERVED_VALIDATOR_DISTRIBUTION_DIGEST = require_phase3_gate_b3()

import importlib.metadata
from pathlib import Path
from typing import Callable

from skillscout.domain.skill_artifacts import FrozenSkillPackageV1
from skillscout.domain.validation import (
    APPROVED_PHASE3_LOCK_DIGEST,
    OFFICIAL_VALIDATION_RESULT_SCHEMA_VERSION,
    OFFICIAL_VALIDATOR_ADAPTER_VERSION,
    OFFICIAL_VALIDATOR_DISTRIBUTION,
    OFFICIAL_VALIDATOR_VERSION,
    VALIDATION_FINDING_SCHEMA_VERSION,
    FilesystemSeam,
    OfficialValidationResultV1,
    ValidationFindingV1,
    WorkspaceAdmissionError,
    admitted_skill_workspace,
    normalize_official_problems,
    official_validator_authority as _official_validator_authority,
    secure_sha256_file,
)

_APPROVED_LOCK_HEX = APPROVED_PHASE3_LOCK_DIGEST.removeprefix("sha256:")
_UNLOADED = object()
_official_validate: object = _UNLOADED


def official_validator_authority():
    """Bind the approved wheel separately from verified installed bytes."""

    return _official_validator_authority(
        observed_distribution_digest=_OBSERVED_VALIDATOR_DISTRIBUTION_DIGEST
    )


def _official_validator() -> Callable[[Path], list[str]] | None:
    global _official_validate
    if _official_validate is _UNLOADED:
        from skills_ref import validate as _official_validate

    if _official_validate is None:
        return None
    if not callable(_official_validate):
        return None
    return _official_validate


def _installed_distribution_version() -> str:
    return importlib.metadata.version(OFFICIAL_VALIDATOR_DISTRIBUTION)


def _verify_approved_lock_authority() -> None:
    repository_root = Path(__file__).parents[3]
    digest_bytes, _ = secure_sha256_file(
        repository_root / "config" / "supply-chain" / "phase3-gate-b3.lock.sha256",
        max_bytes=65,
    )
    _, lock_digest = secure_sha256_file(
        repository_root / "uv.lock",
        max_bytes=2_000_000,
    )
    if digest_bytes != f"{_APPROVED_LOCK_HEX}\n".encode("ascii"):
        raise WorkspaceAdmissionError
    if lock_digest != _APPROVED_LOCK_HEX:
        raise WorkspaceAdmissionError


def _failure(
    *,
    code: str,
    message: str,
) -> OfficialValidationResultV1:
    return OfficialValidationResultV1(
        schema_version=OFFICIAL_VALIDATION_RESULT_SCHEMA_VERSION,
        infrastructure_succeeded=False,
        passed=False,
        admission=None,
        authority=official_validator_authority(),
        findings=(
            ValidationFindingV1(
                schema_version=VALIDATION_FINDING_SCHEMA_VERSION,
                severity="error",
                code=code,
                location="SKILL.md",
                message=message,
                validator_version=OFFICIAL_VALIDATOR_ADAPTER_VERSION,
            ),
        ),
    )


def validate_with_official_validator(
    package: FrozenSkillPackageV1,
    *,
    filesystem_seam: FilesystemSeam | None = None,
) -> OfficialValidationResultV1:
    """Validate one exact frozen package without accepting a caller workspace."""

    try:
        _verify_approved_lock_authority()
        if _installed_distribution_version() != OFFICIAL_VALIDATOR_VERSION:
            raise RuntimeError
        official_validate = _official_validator()
        if official_validate is None:
            raise RuntimeError
        with admitted_skill_workspace(
            package,
            filesystem_seam=filesystem_seam,
        ) as workspace:
            workspace.reverify()
            if filesystem_seam is not None:
                filesystem_seam("before_official_invocation", workspace.root)
            workspace.reverify()
            problems = official_validate(workspace.root)
            if type(problems) is not list or any(
                type(problem) is not str for problem in problems
            ):
                raise RuntimeError
            workspace.reverify()
            findings = normalize_official_problems(problems)
            return OfficialValidationResultV1(
                schema_version=OFFICIAL_VALIDATION_RESULT_SCHEMA_VERSION,
                infrastructure_succeeded=True,
                passed=not findings,
                admission=workspace.admission,
                authority=official_validator_authority(),
                findings=findings,
            )
    except WorkspaceAdmissionError:
        return _failure(
            code="workspace_admission_failed",
            message="The frozen Skill workspace failed exact admission.",
        )
    except Exception:
        return _failure(
            code="official_validator_infrastructure_failure",
            message="The official validator infrastructure failed closed.",
        )
