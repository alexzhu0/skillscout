"""Mutation tests for the independent Phase 5 validation-map verifier."""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
CHECKER = PROJECT_ROOT / "tools/verify_phase5_validation_map.py"
PHASE = Path(".planning/phases/05-automated-discovery-operations")


@pytest.fixture
def planning_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    target = repository / PHASE
    target.mkdir(parents=True)
    source = PROJECT_ROOT / PHASE
    for path in source.glob("05-??-PLAN.md"):
        shutil.copy2(path, target / path.name)
    shutil.copy2(source / "05-VALIDATION.md", target / "05-VALIDATION.md")
    return repository


def _run(repository: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(PROJECT_ROOT / ".tools/uv-0.11.29/bin/uv"),
            "run",
            "--project",
            str(PROJECT_ROOT),
            "--locked",
            "python",
            str(CHECKER),
            "--repository-root",
            str(repository),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={"UV_CACHE_DIR": str(PROJECT_ROOT / ".tools/uv-cache")},
    )


def _validation(repository: Path) -> Path:
    return repository / PHASE / "05-VALIDATION.md"


def _replace(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    assert source.count(old) >= 1
    path.write_text(source.replace(old, new), encoding="utf-8")


def _assert_invalid(repository: Path) -> None:
    completed = _run(repository)
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == "phase5 validation map invalid\n"


def test_current_map_is_exact_complete_and_stdlib_only(
    planning_repository: Path,
) -> None:
    completed = _run(planning_repository)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "phase5 validation map valid\n"
    tree = ast.parse(CHECKER.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported.isdisjoint(
        {"httpx", "openai", "pydantic", "pytest", "requests", "skillscout", "subprocess"}
    )


@pytest.mark.parametrize("damage", ["missing", "duplicate", "orphan"])
def test_task_bijection_mutations_fail(
    planning_repository: Path, damage: str
) -> None:
    path = _validation(planning_repository)
    source = path.read_text(encoding="utf-8")
    row = next(line for line in source.splitlines() if line.startswith("| 05-07-01 |"))
    if damage == "missing":
        source = source.replace(row + "\n", "", 1)
    elif damage == "duplicate":
        source = source.replace(row + "\n", row + "\n" + row + "\n", 1)
    else:
        source = source.replace("| 05-07-01 |", "| 05-99-01 |", 1)
    path.write_text(source, encoding="utf-8")
    _assert_invalid(planning_repository)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("| 05-07-01 | 05-07 | 6 |", "| 05-07-01 | 05-07 | 9 |"),
        ("| 05-07-01 | 05-07 |", "| 05-07-01 | 05-08 |"),
        ("05-04, 05-12, 05-13, 05-14", "05-04, 05-12"),
        ("tests/test_discovery_application.py", "tests/test_renamed.py"),
        ("DISC-01, DISC-02, DISC-03, OPS-02, OPS-03", "DISC-01, OPS-03"),
    ],
)
def test_wave_plan_dependency_artifact_and_requirement_drift_fail(
    planning_repository: Path, old: str, new: str
) -> None:
    _replace(_validation(planning_repository), old, new)
    _assert_invalid(planning_repository)


def test_plan_drift_cannot_self_certify(planning_repository: Path) -> None:
    plan = planning_repository / PHASE / "05-07-PLAN.md"
    _replace(plan, "depends_on: [05-04, 05-12, 05-13, 05-14]", "depends_on: [05-04]")
    _assert_invalid(planning_repository)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1",
            "actions/create-github-app-token@main",
        ),
        (
            ".tools/uv-0.11.29/bin/uv run --locked ruff check .",
            "uv run ruff check .",
        ),
        (
            "D-04 | Unknown semantic outcomes quarantine without replay",
            "D-04 | Unknown semantic outcomes may retry",
        ),
        (
            "1ee162ea47cf86b7faec68bfba37b7a9b2af3b25472066312b43c4a5e4414cdd",
            "0" * 64,
        ),
        (
            "tests/test_discovery_publication_handoff.py",
            "tests/test_discovery_workflow.py",
        ),
        (
            "tests/test_semantic_durability.py",
            "tests/test_discovery_domain.py",
        ),
    ],
)
def test_release_prohibition_action_and_hosted_identity_mutations_fail(
    planning_repository: Path, old: str, new: str
) -> None:
    _replace(_validation(planning_repository), old, new)
    _assert_invalid(planning_repository)


def test_planning_flag_cannot_claim_execution_or_phase6(
    planning_repository: Path,
) -> None:
    _replace(
        _validation(planning_repository),
        "execution_status: pending",
        "execution_status: complete",
    )
    _assert_invalid(planning_repository)
