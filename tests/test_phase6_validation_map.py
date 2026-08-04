"""Isolated-tree mutation tests for the Phase 6 validation-map verifier."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[1]
CHECKER_PATH = PROJECT_ROOT / "tools/verify_phase6_validation_map.py"
CHECKER_SPEC = importlib.util.spec_from_file_location(
    "phase6_validation_map_checker", CHECKER_PATH
)
assert CHECKER_SPEC is not None and CHECKER_SPEC.loader is not None
checker = importlib.util.module_from_spec(CHECKER_SPEC)
sys.modules[CHECKER_SPEC.name] = checker
CHECKER_SPEC.loader.exec_module(checker)


@pytest.fixture
def planning_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(
        PROJECT_ROOT / ".planning/phases/06-adversarial-mvp-acceptance",
        repository / ".planning/phases/06-adversarial-mvp-acceptance",
        ignore=shutil.ignore_patterns("*-SUMMARY.md", "06-RESEARCH.md"),
    )
    return repository


def _phase(repository: Path) -> Path:
    return repository / ".planning/phases/06-adversarial-mvp-acceptance"


def _mutate(path: Path, mutation: Callable[[str], str]) -> None:
    original = path.read_text(encoding="utf-8")
    replacement = mutation(original)
    assert replacement != original
    path.write_text(replacement, encoding="utf-8")


def _replace_once(path: Path, old: str, new: str) -> None:
    def replace(source: str) -> str:
        assert source.count(old) == 1
        return source.replace(old, new, 1)

    _mutate(path, replace)


def _run_contract(repository: Path) -> int:
    original_root = checker.ROOT
    original_phase = checker.PHASE
    original_validation = checker.VALIDATION
    try:
        return checker.main(["--plan-contract", "--repository-root", str(repository)])
    finally:
        checker.ROOT = original_root
        checker.PHASE = original_phase
        checker.VALIDATION = original_validation


def test_dependency_topology_accepts_current_planning_tree() -> None:
    assert _run_contract(PROJECT_ROOT) == 0


@pytest.mark.parametrize(
    ("plan_name", "old", "new"),
    [
        ("06-18-PLAN.md", "depends_on: [06-17]", "depends_on: [06-99]"),
        ("06-17-PLAN.md", "depends_on: [06-16]", "depends_on: [06-18]"),
        ("06-18-PLAN.md", "wave: 8", "wave: 7"),
        ("06-18-PLAN.md", "depends_on: [06-17]", "depends_on: [06-13]"),
        ("06-18-PLAN.md", "wave: 8", "wave: 9"),
    ],
    ids=("missing", "cycle", "same-wave", "future-wave", "wrong-derived-wave"),
)
def test_dependency_topology_rejects_mutated_planning_tree(
    planning_repository: Path,
    plan_name: str,
    old: str,
    new: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _replace_once(_phase(planning_repository) / plan_name, old, new)

    assert _run_contract(planning_repository) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "phase6 validation map invalid\n"


def test_live_admission_checkpoint_rejects_another_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint = checker.CHECKPOINTS["06-16-03"]
    monkeypatch.setitem(
        checker.CHECKPOINTS,
        "06-16-03",
        (checkpoint[0], checkpoint[1], "06-08-01"),
    )

    with pytest.raises(checker.InvalidMap):
        checker.verify_checkpoint_topology()
