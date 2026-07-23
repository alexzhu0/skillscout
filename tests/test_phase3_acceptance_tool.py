"""Adversarial tests for the dependency-free Phase 3 acceptance inspector."""

from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path
from typing import Callable

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
INSPECTOR_PATH = PROJECT_ROOT / "tools/verify_phase3_acceptance.py"
INSPECTOR_SPEC = importlib.util.spec_from_file_location(
    "phase3_acceptance_inspector", INSPECTOR_PATH
)
assert INSPECTOR_SPEC is not None and INSPECTOR_SPEC.loader is not None
inspector = importlib.util.module_from_spec(INSPECTOR_SPEC)
INSPECTOR_SPEC.loader.exec_module(inspector)


@pytest.fixture
def acceptance_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    for relative in (
        "src",
        "tests",
        "config",
    ):
        shutil.copytree(PROJECT_ROOT / relative, repository / relative)
    (repository / "tools").mkdir()
    shutil.copy2(INSPECTOR_PATH, repository / "tools/verify_phase3_acceptance.py")
    shutil.copy2(PROJECT_ROOT / "uv.lock", repository / "uv.lock")
    shutil.copy2(PROJECT_ROOT / "pyproject.toml", repository / "pyproject.toml")
    return repository


def _mutate(repository: Path, relative: str, mutation: Callable[[str], str]) -> None:
    path = repository / relative
    original = path.read_text(encoding="utf-8")
    replacement = mutation(original)
    assert replacement != original
    path.write_text(replacement, encoding="utf-8")


def _replace_once(repository: Path, relative: str, old: str, new: str) -> None:
    def replacement(source: str) -> str:
        assert source.count(old) >= 1
        return source.replace(old, new, 1)

    _mutate(repository, relative, replacement)


def test_acceptance_inspector_is_stdlib_only_and_current_tree_passes() -> None:
    assert inspector.verify_phase3_acceptance(PROJECT_ROOT) is None
    imported = inspector.imported_top_level_modules(INSPECTOR_PATH)
    assert not imported & {"httpx", "openai", "pydantic", "pytest", "skillscout", "skills_ref"}


def test_authority_is_verified_before_registered_checks(
    acceptance_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoked: list[str] = []
    monkeypatch.setattr(
        inspector,
        "_run_registered_checks",
        lambda *_args, **_kwargs: invoked.append("registry"),
    )
    (acceptance_repository / "uv.lock").write_bytes(b"mutated lock\n")

    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)
    assert invoked == []


@pytest.mark.parametrize(
    "damage",
    ["malformed_hash", "uppercase_hash", "symlink", "directory", "oversized", "lock_mismatch"],
)
def test_authority_admission_fails_closed(
    acceptance_repository: Path, damage: str
) -> None:
    digest = (
        acceptance_repository
        / "config/supply-chain/phase3-gate-b3.lock.sha256"
    )
    if damage == "malformed_hash":
        digest.write_text("not-a-digest\n", encoding="ascii")
    elif damage == "uppercase_hash":
        digest.write_text("B" * 64 + "\n", encoding="ascii")
    elif damage == "symlink":
        digest.unlink()
        digest.symlink_to(acceptance_repository / "uv.lock")
    elif damage == "directory":
        digest.unlink()
        digest.mkdir()
    elif damage == "oversized":
        digest.write_bytes(b"0" * (inspector.MAX_DIGEST_BYTES + 1))
    else:
        (acceptance_repository / "uv.lock").write_bytes(b"different\n")

    with pytest.raises((inspector.AcceptanceError, OSError)):
        inspector.verify_phase3_acceptance(acceptance_repository)


def test_authority_snapshot_detects_post_check_mutation(
    acceptance_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = inspector._run_registered_checks

    def mutate_after_checks(repository: Path) -> object:
        result = original(repository)
        lock = repository / "uv.lock"
        lock.write_bytes(lock.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(inspector, "_run_registered_checks", mutate_after_checks)
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)


@pytest.mark.parametrize("damage", ["missing", "duplicate", "unexpected"])
def test_fixed_registry_rejects_missing_duplicate_or_unexpected_checks(
    acceptance_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    damage: str,
) -> None:
    registry = list(inspector.CHECK_REGISTRY)
    if damage == "missing":
        registry.pop()
    elif damage == "duplicate":
        registry.append(registry[0])
    else:
        registry[-1] = inspector.CheckSpec("self_asserted_success", registry[-1].check)
    monkeypatch.setattr(inspector, "CHECK_REGISTRY", tuple(registry))

    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)


@pytest.mark.parametrize(
    ("relative", "addition"),
    [
        ("application/ports.py", "\nimport openai\n"),
        ("domain/models.py", "\nfrom skills_ref import validate\n"),
        ("application/phase3.py", "\nimport subprocess\n"),
        ("application/phase3.py", "\nimport requests\n"),
    ],
)
def test_import_and_capability_allowlists_reject_additions(
    acceptance_repository: Path, relative: str, addition: str
) -> None:
    path = acceptance_repository / "src/skillscout" / relative
    path.write_text(path.read_text(encoding="utf-8") + addition, encoding="utf-8")
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)


def test_exact_openai_and_skills_ref_importer_sets_are_required(
    acceptance_repository: Path,
) -> None:
    _replace_once(
        acceptance_repository,
        "src/skillscout/adapters/openai_generate.py",
        "import openai",
        "import json",
    )
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)

    shutil.copytree(PROJECT_ROOT / "src", acceptance_repository / "src", dirs_exist_ok=True)
    _replace_once(
        acceptance_repository,
        "src/skillscout/adapters/skills_ref.py",
        "from skills_ref import validate as _official_validate",
        "_official_validate = None",
    )
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)


@pytest.mark.parametrize(
    ("relative", "old", "new"),
    [
        (
            "src/skillscout/domain/skill_artifacts.py",
            "draft_digest = sha256_digest(canonical_json_bytes(draft))",
            "draft_digest = sha256_digest(repr(draft).encode())",
        ),
        (
            "src/skillscout/adapters/state.py",
            'connection = sqlite3.connect(":memory:", isolation_level=None)',
            'connection = sqlite3.connect(self.path, isolation_level=None)',
        ),
        (
            "src/skillscout/adapters/state.py",
            "flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC",
            "flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC",
        ),
        (
            "src/skillscout/domain/review.py",
            'eligibility_policy_version: Literal["candidate-eligibility-v1"]',
            'eligibility_policy_version: str',
        ),
        (
            "src/skillscout/domain/review.py",
            "eligible: bool",
            "derived_eligible: bool",
        ),
        (
            "src/skillscout/domain/validation.py",
            "generated_artifact_identity: GeneratedArtifactIdentityV1",
            "generated_artifact_identity: object",
        ),
        (
            "src/skillscout/domain/qualification.py",
            "header: QualificationReportHeaderV1",
            "header: object",
        ),
    ],
)
def test_identity_report_and_completed_projection_mutations_fail(
    acceptance_repository: Path, relative: str, old: str, new: str
) -> None:
    path = acceptance_repository / relative
    if old not in path.read_text(encoding="utf-8"):
        pytest.skip(f"mutation anchor is intentionally absent: {old}")
    _replace_once(acceptance_repository, relative, old, new)
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("os.O_WRONLY | os.O_CREAT | os.O_EXCL", "os.O_WRONLY | os.O_CREAT"),
        ("os.fsync(anchor.descriptor)", "pass  # removed directory durability"),
        ("0o600", "0o666"),
        ("os.rename(", "os.replace("),
    ],
)
def test_materializer_durability_mutations_fail(
    acceptance_repository: Path, old: str, new: str
) -> None:
    _replace_once(
        acceptance_repository,
        "src/skillscout/domain/skill_artifacts.py",
        old,
        new,
    )
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)


def test_package_and_provenance_surface_rejects_scripts_and_secrets(
    acceptance_repository: Path,
) -> None:
    package = acceptance_repository / "tests/fixtures/skills/valid-skill"
    scripts = package / "scripts"
    scripts.mkdir()
    script = scripts / "run.sh"
    script.write_text("#!/bin/sh\nprintf secret\n", encoding="utf-8")
    script.chmod(0o755)
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase3_acceptance(acceptance_repository)


def test_cli_diagnostics_are_bounded_and_deterministic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert inspector.main(["--repository-root", str(PROJECT_ROOT)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "phase3 acceptance valid\n"
    assert captured.err == ""
    assert inspector.main(["--repository-root", "/definitely/missing"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "phase3 acceptance invalid\n"


def test_inspector_source_has_no_project_import_or_write_primitives() -> None:
    source = INSPECTOR_PATH.read_text(encoding="utf-8")
    assert "import skillscout" not in source
    assert "from skillscout" not in source
    assert ".write_text(" not in source
    assert ".write_bytes(" not in source
    assert not inspector.imported_top_level_modules(INSPECTOR_PATH) & {
        "httpx",
        "openai",
        "pydantic",
        "requests",
        "skillscout",
        "skills_ref",
        "subprocess",
    }
    assert os.path.isabs(str(INSPECTOR_PATH))
