#!/usr/bin/env python3
"""Read-only literal Nyquist validation for all Phase 3 plan tasks."""

from __future__ import annotations

import argparse
import ast
import html
import os
import re
import stat
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple

MAX_PLAN_BYTES = 65_536
MAX_MAP_BYTES = 65_536
PHASE_DIRECTORY = Path(".planning/phases/03-validated-skill-candidate")
PLAN_NAMES = tuple(f"03-{number:02d}-PLAN.md" for number in range(1, 15))
VALIDATION_NAME = "03-VALIDATION.md"
SUCCESS_DIAGNOSTIC = "phase3 validation map valid"
FAILURE_DIAGNOSTIC = "phase3 validation map invalid"
JOIN = " && "
GATE = "sh tools/verify_phase3_gate_b3.sh"
SELF_CHECK = "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_phase3_validation_map.py"
UV = (
    'UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 '
    'UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"'
)
EXPECTED_REQUIREMENTS = (
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
EXPECTED_TASK_IDS = (
    "03-01-01",
    "03-02-01",
    "03-03-01",
    "03-04-01",
    "03-05-01",
    "03-05-02",
    "03-06-01",
    "03-06-02",
    "03-07-01",
    "03-07-02",
    "03-08-01",
    "03-08-02",
    "03-08-03",
    "03-09-01",
    "03-09-02",
    "03-09-03",
    "03-10-01",
    "03-10-02",
    "03-10-03",
    "03-11-01",
    "03-11-02",
    "03-11-03",
    "03-12-01",
    "03-12-02",
    "03-12-03",
    "03-13-01",
    "03-13-02",
    "03-14-01",
    "03-14-02",
)


class ValidationMapError(Exception):
    """Closed error for an unsafe or inconsistent planning validation map."""


class PlanRecord(NamedTuple):
    """Safely parsed immutable facts from one Phase 3 plan."""

    plan_id: str
    wave: str
    requirements: tuple[str, ...]
    commands: tuple[str, ...]


class MapRow(NamedTuple):
    """Strictly parsed fields needed from one per-task Markdown row."""

    task_id: str
    plan_id: str
    wave: str
    requirements: tuple[str, ...]
    command: str


class SafeInput(NamedTuple):
    """One stable bounded planning input."""

    payload: bytes
    metadata: tuple[int, ...]


READ_SEAM: Callable[[str, Path], None] | None = None


def _guarded(suffix: str) -> str:
    return JOIN.join((GATE, f"{UV} {suffix}"))


_command_pairs = (
    (
        "03-01-01",
        "N/A — this is a non-auto-approvable human supply-chain decision.",
    ),
    (
        "03-02-01",
        JOIN.join(
            (
                f"{UV} lock --no-build --no-sources --no-cache --managed-python "
                "--no-python-downloads --python 3.13.14",
                f"{UV} lock --check",
                f"{UV} tree --locked --package skills-ref",
            )
        ),
    ),
    ("03-03-01", "git diff --check -- pyproject.toml uv.lock"),
    ("03-04-01", _guarded("run --locked pytest -q tests/test_phase3_lock_preflight.py")),
    ("03-05-01", _guarded("run --locked pytest -q tests/test_candidate_authority.py")),
    ("03-05-02", _guarded("run --locked pytest -q tests/test_lineage.py")),
    (
        "03-06-01",
        _guarded("run --locked pytest -q tests/test_candidate_source.py -k phase2_query"),
    ),
    ("03-06-02", _guarded("run --locked pytest -q tests/test_candidate_source.py")),
    (
        "03-07-01",
        _guarded("run --locked pytest -q tests/test_qualification.py -k checks"),
    ),
    ("03-07-02", _guarded("run --locked pytest -q tests/test_qualification.py")),
    (
        "03-08-01",
        _guarded("run --locked pytest -q tests/test_skill_generation.py -k contracts"),
    ),
    ("03-08-02", _guarded("run --locked pytest -q tests/test_openai_generate.py")),
    ("03-08-03", _guarded("run --locked pytest -q tests/test_skill_generation.py")),
    (
        "03-09-01",
        _guarded(
            'run --locked pytest -q tests/test_skill_validation.py '
            '-k "official or admission"'
        ),
    ),
    (
        "03-09-02",
        _guarded(
            'run --locked pytest -q tests/test_skill_validation.py '
            '-k "local_structure or local_policy"'
        ),
    ),
    ("03-09-03", _guarded("run --locked pytest -q tests/test_skill_validation.py")),
    (
        "03-10-01",
        _guarded("run --locked pytest -q tests/test_openai_review.py -k domain"),
    ),
    (
        "03-10-02",
        _guarded("run --locked pytest -q tests/test_openai_review.py -k adapter"),
    ),
    ("03-10-03", _guarded("run --locked pytest -q tests/test_openai_review.py")),
    (
        "03-11-01",
        _guarded("run --locked pytest -q tests/test_phase3_pipeline.py -k domain_chain"),
    ),
    (
        "03-11-02",
        _guarded("run --locked pytest -q tests/test_phase3_pipeline.py -k state_ledger"),
    ),
    (
        "03-11-03",
        _guarded("run --locked pytest -q tests/test_phase3_pipeline.py -k exact_reuse"),
    ),
    (
        "03-12-01",
        _guarded(
            "run --locked pytest -q tests/test_phase3_pipeline.py -k composition_boundary"
        ),
    ),
    (
        "03-12-02",
        _guarded(
            "run --locked pytest -q tests/test_phase3_pipeline.py -k terminal_cascade"
        ),
    ),
    ("03-12-03", _guarded("run --locked pytest -q tests/test_phase3_pipeline.py")),
    ("03-13-01", _guarded("run --locked pytest -q tests/test_cli_validate_skill.py")),
    ("03-13-02", _guarded("run --locked pytest -q tests/test_cli_security.py")),
    (
        "03-14-01",
        JOIN.join(
            (
                GATE,
                f"{UV} run --locked pytest -q tests/test_phase3_acceptance_tool.py "
                "tests/test_phase3_bootstrap.py tests/test_phase1_gap_closure.py",
                GATE,
                f"{UV} run --locked python tools/verify_phase3_acceptance.py",
            )
        ),
    ),
)

EXPECTED_RELEASE_COMMAND = JOIN.join(
    (
        SELF_CHECK,
        GATE,
        f"{UV} run --locked pytest -q tests/test_phase3_validation_map.py",
        GATE,
        f"{UV} lock --check",
        GATE,
        f"{UV} build --no-sources",
        GATE,
        f"{UV} run --locked python tools/verify_phase3_acceptance.py",
        GATE,
        f"{UV} run --locked ruff check .",
        GATE,
        f"{UV} run --locked pytest -q",
        GATE,
    )
)
EXPECTED_TASK_COMMANDS = dict((*_command_pairs, ("03-14-02", EXPECTED_RELEASE_COMMAND)))


def _require(condition: bool) -> None:
    if not condition:
        raise ValidationMapError


def _metadata(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _trip(name: str, path: Path) -> None:
    if READ_SEAM is not None:
        READ_SEAM(name, path)


def _read_planning_input(path: Path, cap: int) -> SafeInput:
    """Admit one fixed plan/map input with no-follow descriptor stability."""

    try:
        nofollow = os.O_NOFOLLOW
        cloexec = os.O_CLOEXEC
    except AttributeError as error:
        raise ValidationMapError from error
    _require(nofollow != 0 and cloexec != 0 and type(cap) is int and cap >= 0)
    descriptor = -1
    try:
        before = os.lstat(path)
        _require(
            stat.S_ISREG(before.st_mode)
            and not stat.S_ISLNK(before.st_mode)
            and before.st_nlink == 1
            and 0 <= before.st_size <= cap
        )
        _trip("after_lstat", path)
        descriptor = os.open(path, os.O_RDONLY | nofollow | cloexec)
        opened = os.fstat(descriptor)
        _require(
            stat.S_ISREG(opened.st_mode)
            and opened.st_nlink == 1
            and _metadata(opened) == _metadata(before)
        )
        chunks: list[bytes] = []
        consumed = 0
        while True:
            remaining = cap + 1 - consumed
            _require(remaining > 0)
            chunk = os.read(descriptor, min(8192, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            consumed += len(chunk)
            _require(consumed <= cap)
        _trip("after_read", path)
        after_descriptor = os.fstat(descriptor)
        after_path = os.lstat(path)
        _require(_metadata(opened) == _metadata(after_descriptor))
        _require(_metadata(after_descriptor) == _metadata(after_path))
        payload = b"".join(chunks)
        payload.decode("utf-8", errors="strict")
        return SafeInput(payload, _metadata(after_descriptor))
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def imported_top_level_modules(path: Path) -> set[str]:
    """Return imported distribution roots for dependency-isolation tests."""

    tree = ast.parse(path.read_bytes(), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    return imported


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="strict")


def _frontmatter_list(source: str, key: str) -> tuple[str, ...]:
    match = re.search(
        rf"(?m)^{re.escape(key)}:\n((?:  - [A-Z]+-[0-9]{{2}}\n)+)",
        source,
    )
    _require(match is not None)
    values = tuple(re.findall(r"(?m)^  - ([A-Z]+-[0-9]{2})$", match.group(1)))
    _require(bool(values) and len(values) == len(set(values)))
    return values


def _parse_plan(name: str, source: str) -> PlanRecord:
    plan_number = name[3:5]
    plan_id = f"03-{plan_number}"
    _require(re.fullmatch(r"03-[0-9]{2}-PLAN\.md", name) is not None)
    _require(source.startswith("---\n") and source.count("<tasks>") == 1)
    phase = re.search(r"(?m)^phase: 03-validated-skill-candidate$", source)
    declared_plan = re.search(r"(?m)^plan: ([0-9]{2})$", source)
    wave = re.search(r"(?m)^wave: ([0-9]+)$", source)
    _require(
        phase is not None
        and declared_plan is not None
        and declared_plan.group(1) == plan_number
        and wave is not None
    )
    requirements = _frontmatter_list(source, "requirements")
    task_blocks = re.findall(r"<task\b[^>]*>.*?</task>", source, flags=re.DOTALL)
    _require(bool(task_blocks))
    commands: list[str] = []
    for block in task_blocks:
        matches = re.findall(r"<automated>(.*?)</automated>", block, flags=re.DOTALL)
        _require(len(matches) == 1)
        encoded = matches[0]
        _require(encoded == encoded.strip())
        command = html.unescape(encoded)
        commands.append(command)
    return PlanRecord(plan_id, wave.group(1), requirements, tuple(commands))


def _table_body(source: str, heading: str, header: str, separator: str) -> tuple[str, ...]:
    _require(source.count(heading) == 1)
    start = source.index(heading) + len(heading)
    remainder = source[start:]
    marker = f"{header}\n{separator}\n"
    _require(remainder.count(marker) == 1)
    lines = remainder.split(marker, 1)[1].splitlines()
    rows: list[str] = []
    for line in lines:
        if not line.startswith("|"):
            break
        rows.append(line)
    _require(bool(rows))
    return tuple(rows)


def _unwrap_code(value: str) -> str:
    if value.startswith("`") or value.endswith("`"):
        _require(value.startswith("`") and value.endswith("`") and len(value) >= 2)
        return value[1:-1]
    return value


def _parse_task_rows(source: str) -> tuple[MapRow, ...]:
    rows = _table_body(
        source,
        "## Per-Task Verification Map",
        (
            "| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | "
            "Test Type | Automated Command | File Exists | Status |"
        ),
        (
            "|---------|------|------|-------------|------------|-----------------|"
            "-----------|-------------------|-------------|--------|"
        ),
    )
    parsed: list[MapRow] = []
    for row in rows:
        cells = tuple(cell.strip() for cell in row[1:-1].split("|"))
        _require(len(cells) == 10)
        task_id, plan_id, wave, requirements = cells[:4]
        _require(re.fullmatch(r"03-[0-9]{2}-[0-9]{2}", task_id) is not None)
        _require(re.fullmatch(r"03-[0-9]{2}", plan_id) is not None)
        _require(re.fullmatch(r"[0-9]+", wave) is not None)
        requirement_values = tuple(part.strip() for part in requirements.split(","))
        _require(
            bool(requirement_values)
            and all(value in EXPECTED_REQUIREMENTS for value in requirement_values)
            and len(requirement_values) == len(set(requirement_values))
        )
        command = html.unescape(_unwrap_code(cells[7]))
        parsed.append(MapRow(task_id, plan_id, wave, requirement_values, command))
    return tuple(parsed)


def _parse_coverage(source: str) -> dict[str, tuple[str, ...]]:
    rows = _table_body(
        source,
        "## Requirement Coverage",
        "| Requirement | Validation evidence |",
        "|-------------|---------------------|",
    )
    parsed: dict[str, tuple[str, ...]] = {}
    for row in rows:
        cells = tuple(cell.strip() for cell in row[1:-1].split("|"))
        _require(len(cells) == 2)
        requirement, evidence = cells
        _require(requirement in EXPECTED_REQUIREMENTS and requirement not in parsed)
        tasks = tuple(part.strip() for part in evidence.split(","))
        _require(
            bool(tasks)
            and all(task in EXPECTED_TASK_IDS for task in tasks)
            and len(tasks) == len(set(tasks))
        )
        parsed[requirement] = tasks
    _require(tuple(parsed) == EXPECTED_REQUIREMENTS)
    return parsed


def _full_suite(source: str) -> str:
    prefix = "| **Full suite command** | `"
    lines = [line for line in source.splitlines() if line.startswith(prefix)]
    _require(len(lines) == 1 and lines[0].endswith("` |"))
    return html.unescape(lines[0][len(prefix) : -3])


def _validate_command_grammar(task_id: str, command: str) -> None:
    if task_id == "03-01-01":
        _require(command == EXPECTED_TASK_COMMANDS[task_id])
        return
    _require(
        command
        and command == command.strip()
        and re.fullmatch(r"[^\x00-\x1f\x7f]+", command) is not None
    )
    for forbidden in (
        "||",
        ";",
        "|&",
        "|",
        "`",
        "$(",
        "${",
        "$$",
        ">",
        "<",
        "#",
        "\\",
    ):
        _require(forbidden not in command)
    _require("$" not in command.replace("$PWD", ""))
    segments = command.split(JOIN)
    _require(JOIN.join(segments) == command and all(segment for segment in segments))
    _require(all("&" not in segment for segment in segments))
    canonical_segments = {
        segment
        for expected in EXPECTED_TASK_COMMANDS.values()
        if expected != EXPECTED_TASK_COMMANDS["03-01-01"]
        for segment in expected.split(JOIN)
    }
    _require(all(segment in canonical_segments for segment in segments))
    if SELF_CHECK in segments:
        _require(
            task_id == "03-14-02"
            and command == EXPECTED_RELEASE_COMMAND
            and segments[0] == SELF_CHECK
            and segments.count(SELF_CHECK) == 1
        )
    if task_id not in {"03-02-01", "03-03-01"}:
        for index, segment in enumerate(segments):
            if segment.startswith(UV):
                _require(index > 0 and segments[index - 1] == GATE)


def verify_validation_map(repository_root: Path) -> None:
    """Safely verify the literal 29-task/13-requirement Phase 3 map."""

    root = Path(os.path.abspath(os.fspath(repository_root)))
    _require(stat.S_ISDIR(os.lstat(root).st_mode))
    phase = root / PHASE_DIRECTORY
    plans: dict[str, PlanRecord] = {}
    derived_commands: dict[str, str] = {}
    for name in PLAN_NAMES:
        admitted = _read_planning_input(phase / name, MAX_PLAN_BYTES)
        record = _parse_plan(name, _decode(admitted.payload))
        _require(record.plan_id not in plans)
        plans[record.plan_id] = record
        for ordinal, command in enumerate(record.commands, 1):
            task_id = f"{record.plan_id}-{ordinal:02d}"
            _require(task_id not in derived_commands)
            derived_commands[task_id] = command
    validation = _decode(
        _read_planning_input(phase / VALIDATION_NAME, MAX_MAP_BYTES).payload
    )
    rows = _parse_task_rows(validation)
    _require(tuple(row.task_id for row in rows) == EXPECTED_TASK_IDS)
    _require(len(rows) == len({row.task_id for row in rows}))
    _require(tuple(derived_commands) == EXPECTED_TASK_IDS)
    _require(tuple(EXPECTED_TASK_COMMANDS) == EXPECTED_TASK_IDS)

    inverse: dict[str, list[str]] = {
        requirement: [] for requirement in EXPECTED_REQUIREMENTS
    }
    by_plan: dict[str, set[str]] = {plan_id: set() for plan_id in plans}
    for row in rows:
        plan = plans.get(row.plan_id)
        _require(
            plan is not None
            and row.task_id.startswith(f"{row.plan_id}-")
            and row.wave == plan.wave
            and derived_commands[row.task_id] == row.command
            and EXPECTED_TASK_COMMANDS[row.task_id] == row.command
        )
        _validate_command_grammar(row.task_id, row.command)
        by_plan[row.plan_id].update(row.requirements)
        for requirement in row.requirements:
            inverse[requirement].append(row.task_id)
    for plan_id, record in plans.items():
        _require(by_plan[plan_id] == set(record.requirements))

    coverage = _parse_coverage(validation)
    _require(
        coverage
        == {
            requirement: tuple(inverse[requirement])
            for requirement in EXPECTED_REQUIREMENTS
        }
    )
    full_suite = _full_suite(validation)
    _validate_command_grammar("03-14-02", full_suite)
    _require(
        full_suite == EXPECTED_RELEASE_COMMAND
        and rows[-1].command == EXPECTED_RELEASE_COMMAND
    )
    release_segments = EXPECTED_RELEASE_COMMAND.split(JOIN)
    _require(
        release_segments
        == [
            SELF_CHECK,
            GATE,
            f"{UV} run --locked pytest -q tests/test_phase3_validation_map.py",
            GATE,
            f"{UV} lock --check",
            GATE,
            f"{UV} build --no-sources",
            GATE,
            f"{UV} run --locked python tools/verify_phase3_acceptance.py",
            GATE,
            f"{UV} run --locked ruff check .",
            GATE,
            f"{UV} run --locked pytest -q",
            GATE,
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repository-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments:
            namespace = _parser().parse_args(arguments)
            _require(namespace.repository_root is not None)
            root = namespace.repository_root
        else:
            root = Path(__file__).resolve().parents[1]
        verify_validation_map(root)
    except (
        ValidationMapError,
        OSError,
        OverflowError,
        UnicodeError,
        SyntaxError,
        SystemExit,
        ValueError,
        TypeError,
    ):
        print(FAILURE_DIAGNOSTIC, file=sys.stderr)
        return 1
    print(SUCCESS_DIAGNOSTIC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
