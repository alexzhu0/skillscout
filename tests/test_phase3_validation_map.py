"""Adversarial tests for the read-only Phase 3 validation-map checker."""

from __future__ import annotations

import html
import importlib.util
import os
import shutil
from pathlib import Path
from typing import Callable

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
CHECKER_PATH = PROJECT_ROOT / "tools/verify_phase3_validation_map.py"
CHECKER_SPEC = importlib.util.spec_from_file_location(
    "phase3_validation_map_checker", CHECKER_PATH
)
assert CHECKER_SPEC is not None and CHECKER_SPEC.loader is not None
checker = importlib.util.module_from_spec(CHECKER_SPEC)
CHECKER_SPEC.loader.exec_module(checker)


@pytest.fixture
def planning_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    target = repository / ".planning/phases/03-validated-skill-candidate"
    shutil.copytree(
        PROJECT_ROOT / ".planning/phases/03-validated-skill-candidate",
        target,
        ignore=shutil.ignore_patterns("*-SUMMARY.md", "03-RESEARCH.md", "03-PATTERNS.md"),
    )
    return repository


def _phase(repository: Path) -> Path:
    return repository / ".planning/phases/03-validated-skill-candidate"


def _map(repository: Path) -> Path:
    return _phase(repository) / "03-VALIDATION.md"


def _mutate(path: Path, mutation: Callable[[str], str]) -> None:
    original = path.read_text(encoding="utf-8")
    replacement = mutation(original)
    assert replacement != original
    path.write_text(replacement, encoding="utf-8")


def _replace_once(path: Path, old: str, new: str) -> None:
    def replace(source: str) -> str:
        assert source.count(old) >= 1
        return source.replace(old, new, 1)

    _mutate(path, replace)


def _synchronize_release(repository: Path, mutated: str) -> None:
    plan = _phase(repository) / "03-14-PLAN.md"
    validation = _map(repository)
    expected = checker.EXPECTED_RELEASE_COMMAND
    assert plan.read_text(encoding="utf-8").count(expected.replace("&", "&amp;")) == 1
    _replace_once(plan, expected.replace("&", "&amp;"), mutated.replace("&", "&amp;"))
    assert validation.read_text(encoding="utf-8").count(expected) == 2
    _mutate(validation, lambda source: source.replace(expected, mutated))


def test_current_planning_tree_passes_and_constants_are_closed() -> None:
    assert checker.verify_validation_map(PROJECT_ROOT) is None
    assert tuple(checker.EXPECTED_TASK_COMMANDS) == checker.EXPECTED_TASK_IDS
    assert len(checker.EXPECTED_TASK_IDS) == 29
    assert checker.EXPECTED_REQUIREMENTS == (
        "QUAL-01",
        "QUAL-02",
        "GEN-01",
        "GEN-02",
        "GEN-03",
        "GEN-04",
        "GEN-05",
        "VAL-01",
        "VAL-02",
        "VAL-03",
        "REV-01",
        "REV-02",
        "REV-03",
    )
    assert checker.EXPECTED_TASK_COMMANDS["03-14-02"] == checker.EXPECTED_RELEASE_COMMAND


def test_checker_is_stdlib_only_read_only_and_never_executes_commands() -> None:
    source = CHECKER_PATH.read_text(encoding="utf-8")
    imported = checker.imported_top_level_modules(CHECKER_PATH)
    assert not imported & {
        "httpx",
        "openai",
        "pydantic",
        "pytest",
        "requests",
        "skillscout",
        "skills_ref",
        "subprocess",
    }
    assert ".write_text(" not in source
    assert ".write_bytes(" not in source
    assert "os.system" not in source
    assert "eval(" not in source
    assert "shell=True" not in source


@pytest.mark.parametrize("damage", ["missing", "duplicate", "unexpected", "malformed"])
def test_task_row_bijection_rejects_damage(
    planning_repository: Path, damage: str
) -> None:
    validation = _map(planning_repository)
    marker = "| 03-05-01 |"
    lines = validation.read_text(encoding="utf-8").splitlines()
    row = next(line for line in lines if line.startswith(marker))
    if damage == "missing":
        replacement = [line for line in lines if line != row]
    elif damage == "duplicate":
        replacement = lines[: lines.index(row) + 1] + [row] + lines[lines.index(row) + 1 :]
    elif damage == "unexpected":
        replacement = [line.replace(marker, "| 03-99-01 |", 1) if line == row else line for line in lines]
    else:
        replacement = [line.replace(" | 03-05 | ", " | ") if line == row else line for line in lines]
    validation.write_text("\n".join(replacement) + "\n", encoding="utf-8")
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


@pytest.mark.parametrize("table", ["task", "coverage"])
def test_duplicate_tables_are_rejected(planning_repository: Path, table: str) -> None:
    validation = _map(planning_repository)
    source = validation.read_text(encoding="utf-8")
    if table == "task":
        start = source.index("## Per-Task Verification Map")
        end = source.index("\n*Status:", start)
    else:
        start = source.index("## Requirement Coverage")
        end = source.index("\n---", start)
    duplicate = source[start:end]
    validation.write_text(source + "\n" + duplicate + "\n", encoding="utf-8")
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_malformed_coverage_and_dropped_requirement_are_rejected(
    planning_repository: Path,
) -> None:
    validation = _map(planning_repository)
    _replace_once(
        validation,
        "| QUAL-01 | 03-07-01,",
        "| QUAL-01..QUAL-02 | 03-07-01,",
    )
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)

    shutil.copy2(
        PROJECT_ROOT / ".planning/phases/03-validated-skill-candidate/03-VALIDATION.md",
        validation,
    )
    _replace_once(
        validation,
        "| QUAL-01 | 03-07-01, 03-12-01,",
        "| QUAL-01 | 03-07-01,",
    )
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_plan_map_command_drift_is_rejected(planning_repository: Path) -> None:
    plan = _phase(planning_repository) / "03-05-PLAN.md"
    _replace_once(plan, "tests/test_lineage.py", "tests/test_candidate_authority.py")
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


@pytest.mark.parametrize(
    "suffix",
    [
        " || true",
        "; true",
        " | true",
        " |& true",
        " `id`",
        " $(id)",
        " ${PATH}",
        " > result",
        " < input",
        " >(true)",
        " <(true)",
        " <<EOF",
        " # bypass",
        " \\ ",
        "&#10;true",
        "&#13;true",
        "&#9;true",
        "\ntrue",
        "\rtrue",
        "\ttrue",
        "\x00true",
        "\x7ftrue",
    ],
)
def test_parity_preserving_release_shell_bypasses_are_rejected(
    planning_repository: Path, suffix: str
) -> None:
    mutated = checker.EXPECTED_RELEASE_COMMAND + suffix
    _synchronize_release(planning_repository, mutated)
    plan = (_phase(planning_repository) / "03-14-PLAN.md").read_text(encoding="utf-8")
    validation = _map(planning_repository).read_text(encoding="utf-8")
    assert html.unescape(mutated.replace("&", "&amp;")) in html.unescape(plan)
    assert validation.count(mutated) == 2
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_missing_terminal_postflight_is_rejected(planning_repository: Path) -> None:
    gate = " && sh tools/verify_phase3_gate_b3.sh"
    assert checker.EXPECTED_RELEASE_COMMAND.endswith(gate)
    _synchronize_release(
        planning_repository, checker.EXPECTED_RELEASE_COMMAND[: -len(gate)]
    )
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_missing_dependency_preflight_is_rejected(planning_repository: Path) -> None:
    guarded = (
        'sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" '
        'UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never '
        '"$PWD/.tools/uv-0.11.29/bin/uv" build --no-sources'
    )
    unguarded = guarded.split(" && ", 1)[1]
    assert guarded in checker.EXPECTED_RELEASE_COMMAND
    _synchronize_release(
        planning_repository,
        checker.EXPECTED_RELEASE_COMMAND.replace(guarded, unguarded, 1),
    )
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


@pytest.mark.parametrize(
    "damage", ["symlink", "directory", "oversized", "invalid_utf8"]
)
def test_planning_input_admission_fails_closed(
    planning_repository: Path, damage: str
) -> None:
    target = _phase(planning_repository) / "03-08-PLAN.md"
    if damage == "symlink":
        target.unlink()
        target.symlink_to(_phase(planning_repository) / "03-07-PLAN.md")
    elif damage == "directory":
        target.unlink()
        target.mkdir()
    elif damage == "oversized":
        target.write_bytes(b"x" * (checker.MAX_PLAN_BYTES + 1))
    else:
        target.write_bytes(b"\xff")
    with pytest.raises((checker.ValidationMapError, OSError, UnicodeError)):
        checker.verify_validation_map(planning_repository)


@pytest.mark.parametrize("seam", ["after_lstat", "after_read"])
def test_atomic_input_swaps_are_rejected(
    planning_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    seam: str,
) -> None:
    target = _phase(planning_repository) / "03-08-PLAN.md"
    replacement = target.with_name("replacement")
    replacement.write_bytes(target.read_bytes())
    replacement.chmod(target.stat().st_mode & 0o777)
    original = checker.READ_SEAM

    def swap(name: str, path: Path) -> None:
        if name == seam and path == target:
            moved = target.with_name("original")
            target.rename(moved)
            replacement.rename(target)
        if original is not None:
            original(name, path)

    monkeypatch.setattr(checker, "READ_SEAM", swap)
    with pytest.raises(checker.ValidationMapError):
        checker.verify_validation_map(planning_repository)


def test_cli_diagnostics_are_fixed_and_root_is_tool_relative(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert checker.main([]) == 0
    captured = capsys.readouterr()
    assert captured.out == "phase3 validation map valid\n"
    assert captured.err == ""
    assert checker.main(["--repository-root", "/definitely/missing"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "phase3 validation map invalid\n"
    assert os.getcwd() == str(tmp_path)
