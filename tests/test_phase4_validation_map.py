"""Mutation tests for the dependency-free Phase 4 validation-map verifier."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
CHECKER_PATH = PROJECT_ROOT / "tools/verify_phase4_validation_map.py"
SPEC = importlib.util.spec_from_file_location("phase4_validation_map", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


@pytest.fixture
def planning_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    target = repository / ".planning/phases/04-controlled-draft-pr"
    target.mkdir(parents=True)
    source = PROJECT_ROOT / ".planning/phases/04-controlled-draft-pr"
    for path in source.glob("04-??-PLAN.md"):
        shutil.copy2(path, target / path.name)
    shutil.copy2(source / "04-VALIDATION.md", target / "04-VALIDATION.md")
    return repository


def _validation(repository: Path) -> Path:
    return repository / ".planning/phases/04-controlled-draft-pr/04-VALIDATION.md"


def _replace(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    assert source.count(old) >= 1
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def test_current_map_is_exact_complete_and_stdlib_only() -> None:
    assert checker.verify_validation_map(PROJECT_ROOT) is None
    assert len(checker.EXPECTED_TASK_IDS) == 25
    assert checker.EXPECTED_REQUIREMENTS == (
        "PUB-01",
        "PUB-02",
        "PUB-03",
        "PUB-04",
        "PUB-05",
        "SEC-02",
    )
    assert checker.imported_top_level_modules(CHECKER_PATH).isdisjoint(
        {"httpx", "openai", "pydantic", "pytest", "requests", "skillscout", "subprocess"}
    )


@pytest.mark.parametrize("damage", ["missing", "duplicate", "orphan"])
def test_task_bijection_mutations_fail(
    planning_repository: Path, damage: str
) -> None:
    path = _validation(planning_repository)
    source = path.read_text(encoding="utf-8")
    row = next(
        line for line in source.splitlines() if line.startswith("| 04-03-01 |")
    )
    if damage == "missing":
        source = source.replace(row + "\n", "", 1)
    elif damage == "duplicate":
        source = source.replace(row + "\n", row + "\n" + row + "\n", 1)
    else:
        source = source.replace("| 04-03-01 |", "| 04-99-01 |", 1)
    path.write_text(source, encoding="utf-8")
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("| PUB-01 | Positive:", "| PUB-99 | Positive:"),
        ("tests/test_publication_domain.py -k 'identity or grammar or marker'", "tests/test_publication_domain.py"),
        ("tests/test_publication_domain.py |", "tests/renamed.py |"),
        ("| 04-03-01 | 04-03 | 2 |", "| 04-03-01 | 04-03 | 9 |"),
        ("| 04-03-01 | 04-03 |", "| 04-03-01 | 04-04 |"),
    ],
)
def test_requirement_command_path_wave_and_dependency_drift_fail(
    planning_repository: Path, old: str, new: str
) -> None:
    _replace(_validation(planning_repository), old, new)
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


@pytest.mark.parametrize("gate", ["Gate A4", "Gate B4"])
def test_both_non_auto_approvable_human_gates_are_mandatory(
    planning_repository: Path, gate: str
) -> None:
    _replace(_validation(planning_repository), gate, f"Removed {gate}")
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_mutable_action_reference_is_rejected(planning_repository: Path) -> None:
    _replace(
        _validation(planning_repository),
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "actions/checkout@v4",
    )
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_nonlocal_uv_and_release_chain_drift_are_rejected(
    planning_repository: Path,
) -> None:
    _replace(
        _validation(planning_repository),
        ".tools/uv-0.11.29/bin/uv run --locked ruff check .",
        "uv run ruff check .",
    )
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_plan_command_and_dependency_mutations_fail(planning_repository: Path) -> None:
    phase = planning_repository / ".planning/phases/04-controlled-draft-pr"
    _replace(
        phase / "04-03-PLAN.md",
        "depends_on: [04-01]",
        "depends_on: [04-02]",
    )
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_cli_has_bounded_fixed_diagnostics(capsys: pytest.CaptureFixture[str]) -> None:
    assert checker.main([]) == 0
    assert capsys.readouterr().out == "phase4 validation map valid\n"
    assert checker.main(["--repository-root", "/missing"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "phase4 validation map invalid\n"
