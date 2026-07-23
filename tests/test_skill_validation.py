"""Official Agent Skills validator admission and isolation contracts."""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Callable

import pytest

import skillscout.adapters.skills_ref as skills_ref_adapter
from skillscout.adapters.skills_ref import validate_with_official_validator
from skillscout.domain.skill_artifacts import (
    FROZEN_PACKAGE_SCHEMA_VERSION,
    FrozenSkillPackageV1,
    RenderedFileV1,
    RenderedPackageManifestV1,
    package_digest,
)
from skillscout.domain.validation import (
    APPROVED_PHASE3_LOCK_DIGEST,
    OFFICIAL_VALIDATOR_ADAPTER_VERSION,
    OFFICIAL_VALIDATOR_DISTRIBUTION,
    OFFICIAL_VALIDATOR_DISTRIBUTION_HASH,
    OFFICIAL_VALIDATOR_VERSION,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "skills" / "valid-skill"


def _fixture_package() -> FrozenSkillPackageV1:
    files = tuple(
        RenderedFileV1(
            path=path.relative_to(FIXTURE_ROOT).as_posix(),
            content=path.read_bytes(),
            mode=0o644,
            is_symlink=False,
        )
        for path in sorted(FIXTURE_ROOT.rglob("*"))
        if path.is_file()
    )
    manifest = RenderedPackageManifestV1.from_files(files)
    return FrozenSkillPackageV1.model_construct(
        schema_version=FROZEN_PACKAGE_SCHEMA_VERSION,
        stable_slug="valid-skill",
        generated_artifact_identity=None,
        provenance=None,
        files=files,
        rendered_manifest=manifest,
        package_identity=package_digest(manifest),
    )


def _replace_file(path: Path, content: bytes) -> None:
    path.unlink()
    path.write_bytes(content)
    path.chmod(0o644)


def _mutate_missing(root: Path) -> None:
    (root / "SKILL.md").unlink()


def _mutate_extra(root: Path) -> None:
    extra = root / "extra.md"
    extra.write_text("undeclared", encoding="utf-8")
    extra.chmod(0o644)


def _mutate_changed(root: Path) -> None:
    (root / "SKILL.md").write_text("changed", encoding="utf-8")


def _mutate_symlink(root: Path) -> None:
    target = root / "SKILL.md"
    target.unlink()
    target.symlink_to(root / "references" / "provenance.json")


def _mutate_hardlink(root: Path) -> None:
    target = root / "references" / "provenance.json"
    target.unlink()
    os.link(root / "SKILL.md", target)


def _mutate_fifo(root: Path) -> None:
    target = root / "references" / "provenance.json"
    target.unlink()
    os.mkfifo(target, 0o644)


def _mutate_mode(root: Path) -> None:
    (root / "SKILL.md").chmod(0o755)


def _mutate_size(root: Path) -> None:
    with (root / "SKILL.md").open("ab") as stream:
        stream.write(b"x")


def _mutate_binary(root: Path) -> None:
    _replace_file(root / "SKILL.md", b"\x00binary")


def _mutate_non_utf8(root: Path) -> None:
    _replace_file(root / "SKILL.md", b"\xff")


@pytest.mark.parametrize(
    "mutator",
    (
        _mutate_missing,
        _mutate_extra,
        _mutate_changed,
        _mutate_symlink,
        _mutate_hardlink,
        _mutate_fifo,
        _mutate_mode,
        _mutate_size,
        _mutate_binary,
        _mutate_non_utf8,
    ),
)
def test_admission_rejects_workspace_mutation_before_official_invocation(
    monkeypatch: pytest.MonkeyPatch,
    mutator: Callable[[Path], None],
) -> None:
    calls = 0

    def official(_: Path) -> list[str]:
        nonlocal calls
        calls += 1
        return []

    def seam(operation: str, root: Path) -> None:
        if operation == "after_workspace_materialized":
            mutator(root)

    monkeypatch.setattr(skills_ref_adapter, "_official_validate", official)
    result = validate_with_official_validator(
        _fixture_package(),
        filesystem_seam=seam,
    )

    assert result.passed is False
    assert result.infrastructure_succeeded is False
    assert tuple(finding.code for finding in result.findings) == (
        "workspace_admission_failed",
    )
    assert calls == 0


def test_admission_rejects_traversal_in_tampered_frozen_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _fixture_package()
    files = list(package.files)
    files[0] = files[0].model_copy(update={"path": "../escape"})
    tampered = package.model_copy(update={"files": tuple(files)})
    calls = 0

    def official(_: Path) -> list[str]:
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(skills_ref_adapter, "_official_validate", official)
    result = validate_with_official_validator(tampered)
    assert result.infrastructure_succeeded is False
    assert calls == 0


@pytest.mark.parametrize(
    ("operation", "mutator"),
    (
        ("after_lstat:SKILL.md", _mutate_changed),
        ("before_official_invocation", _mutate_changed),
    ),
)
def test_admission_rechecks_descriptor_identity_and_immediate_pre_call_state(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    mutator: Callable[[Path], None],
) -> None:
    calls = 0
    attacked = False

    def official(_: Path) -> list[str]:
        nonlocal calls
        calls += 1
        return []

    def seam(current: str, root: Path) -> None:
        nonlocal attacked
        if current == operation and not attacked:
            attacked = True
            mutator(root)

    monkeypatch.setattr(skills_ref_adapter, "_official_validate", official)
    result = validate_with_official_validator(
        _fixture_package(),
        filesystem_seam=seam,
    )
    assert result.infrastructure_succeeded is False
    assert calls == 0


def test_official_validator_accepts_exact_fixture_and_records_authority() -> None:
    result = validate_with_official_validator(_fixture_package())

    assert result.passed is True
    assert result.infrastructure_succeeded is True
    assert result.findings == ()
    assert result.admission.admitted is True
    assert result.admission.manifest_digest == (
        _fixture_package().package_identity.rendered_manifest_digest
    )
    assert result.authority.distribution == OFFICIAL_VALIDATOR_DISTRIBUTION
    assert result.authority.version == OFFICIAL_VALIDATOR_VERSION
    assert result.authority.distribution_hash == OFFICIAL_VALIDATOR_DISTRIBUTION_HASH
    assert result.authority.approved_lock_digest == APPROVED_PHASE3_LOCK_DIGEST
    assert result.authority.adapter_version == OFFICIAL_VALIDATOR_ADAPTER_VERSION


def test_official_findings_are_stable_bounded_and_redact_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid(root: Path) -> list[str]:
        return [
            f"Path does not exist: {root}/secret",
            "Invalid skill name: Bad_Name",
        ]

    monkeypatch.setattr(skills_ref_adapter, "_official_validate", invalid)
    result = validate_with_official_validator(_fixture_package())

    assert result.passed is False
    assert tuple(finding.severity for finding in result.findings) == ("error", "error")
    assert tuple(finding.code for finding in result.findings) == (
        "official_invalid_name",
        "official_validation_error",
    )
    assert all(len(finding.message) <= 160 for finding in result.findings)
    assert all("/tmp/" not in finding.message for finding in result.findings)
    assert all("secret" not in finding.message for finding in result.findings)


@pytest.mark.parametrize(
    "failure",
    ("missing_interface", "wrong_version", "malformed_result", "crash"),
)
def test_official_validator_infrastructure_failures_close_without_leaking(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    canary = "sk-live-secret-validator-canary"
    if failure == "missing_interface":
        monkeypatch.setattr(skills_ref_adapter, "_official_validate", None)
    elif failure == "wrong_version":
        monkeypatch.setattr(
            skills_ref_adapter,
            "_installed_distribution_version",
            lambda: "9.9.9",
        )
    elif failure == "malformed_result":
        monkeypatch.setattr(skills_ref_adapter, "_official_validate", lambda _: [123])
    else:
        def crash(_: Path) -> list[str]:
            raise RuntimeError(canary)

        monkeypatch.setattr(skills_ref_adapter, "_official_validate", crash)

    result = validate_with_official_validator(_fixture_package())
    assert result.passed is False
    assert result.infrastructure_succeeded is False
    assert tuple(finding.code for finding in result.findings) == (
        "official_validator_infrastructure_failure",
    )
    assert canary not in result.findings[0].message
    assert canary not in caplog.text


@pytest.mark.parametrize("crash", (False, True))
def test_official_workspace_is_always_cleaned(
    monkeypatch: pytest.MonkeyPatch,
    crash: bool,
) -> None:
    observed: Path | None = None

    def official(_: Path) -> list[str]:
        if crash:
            raise RuntimeError("sanitized")
        return []

    def seam(operation: str, root: Path) -> None:
        nonlocal observed
        if operation == "after_workspace_materialized":
            observed = root

    monkeypatch.setattr(skills_ref_adapter, "_official_validate", official)
    validate_with_official_validator(_fixture_package(), filesystem_seam=seam)
    assert observed is not None
    assert not observed.exists()


def test_official_import_is_confined_to_one_adapter() -> None:
    importers: set[str] = set()
    source_root = Path(__file__).parents[1] / "src" / "skillscout"
    for source in source_root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        if any(
            (
                isinstance(node, ast.Import)
                and any(alias.name == "skills_ref" for alias in node.names)
            )
            or (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == "skills_ref"
                    or node.module.startswith("skills_ref.")
                )
            )
            for node in ast.walk(tree)
        ):
            importers.add(source.relative_to(source_root).as_posix())
    assert importers == {"adapters/skills_ref.py"}
