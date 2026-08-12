#!/usr/bin/env python3
"""Dependency-free, read-only exact validation-map verifier for Phase 4."""

from __future__ import annotations

import argparse
import ast
import html
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

PHASE_DIRECTORY = Path("evidence/phase-4-controlled-draft-pr")
PLAN_NAMES = tuple(f"04-{number:02d}-PLAN.md" for number in range(1, 12))
VALIDATION_NAME = "04-VALIDATION.md"
MAX_INPUT_BYTES = 256_000
SUCCESS_DIAGNOSTIC = "phase4 validation map valid"
FAILURE_DIAGNOSTIC = "phase4 validation map invalid"
EXPECTED_REQUIREMENTS = ("PUB-01", "PUB-02", "PUB-03", "PUB-04", "PUB-05", "SEC-02")
EXPECTED_PLAN_FACTS = {
    "04-01": ("1", (), ("PUB-01", "PUB-02", "PUB-03", "SEC-02")),
    "04-02": ("1", (), ("PUB-01", "PUB-04", "PUB-05")),
    "04-03": ("2", ("04-01",), ("PUB-01", "PUB-02", "PUB-03", "PUB-05")),
    "04-04": ("3", ("04-02", "04-03"), ("PUB-01", "PUB-03", "PUB-05", "SEC-02")),
    "04-05": ("4", ("04-03", "04-04"), ("PUB-01", "PUB-05")),
    "04-06": ("5", ("04-05",), ("PUB-01", "PUB-02", "PUB-03", "PUB-05", "SEC-02")),
    "04-07": ("1", (), ("PUB-04", "SEC-02")),
    "04-08": ("2", ("04-07",), ("PUB-04", "SEC-02")),
    "04-09": ("6", ("04-06", "04-08"), ("PUB-01", "PUB-03", "PUB-04", "SEC-02")),
    "04-10": ("7", ("04-09",), ("PUB-01", "PUB-03", "PUB-04", "PUB-05", "SEC-02")),
    "04-11": ("8", ("04-10",), EXPECTED_REQUIREMENTS),
}
EXPECTED_TASK_IDS = (
    "04-01-01", "04-01-02",
    "04-02-01", "04-02-02", "04-02-03",
    "04-03-01", "04-03-02", "04-03-03",
    "04-04-01", "04-04-02",
    "04-05-01", "04-05-02", "04-05-03",
    "04-06-01", "04-06-02", "04-06-03",
    "04-07-01", "04-07-02",
    "04-08-01",
    "04-09-01", "04-09-02",
    "04-10-01",
    "04-11-01", "04-11-02", "04-11-03",
)
LOCAL_UV = ".tools/uv-0.11.29/bin/uv"
EXPECTED_RELEASE_COMMAND = (
    f"{LOCAL_UV} run --locked python tools/verify_phase4_validation_map.py && "
    f"{LOCAL_UV} run --locked python tools/verify_phase4_action_audit.py && "
    f"{LOCAL_UV} run --locked ruff check . && "
    f"{LOCAL_UV} run --locked pytest -q && "
    f"{LOCAL_UV} run --locked python tools/verify_phase4_acceptance.py"
)
ACTION_IDENTITIES = (
    "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
    "actions/create-github-app-token@67018539274d69449ef7c8cde82c3ff073ffe3b5",
)


class ValidationMapError(Exception):
    """Closed failure for a missing or inconsistent validation fact."""


class PlanRecord(NamedTuple):
    plan_id: str
    wave: str
    dependencies: tuple[str, ...]
    requirements: tuple[str, ...]
    commands: tuple[str, ...]


class MapRow(NamedTuple):
    task_id: str
    plan_id: str
    wave: str
    dependencies: tuple[str, ...]
    requirements: tuple[str, ...]
    command: str
    evidence: str
    human_gate: str


def _require(condition: bool) -> None:
    if not condition:
        raise ValidationMapError


def imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_bytes(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".", 1)[0])
    return modules


def _read(path: Path) -> str:
    payload = path.read_bytes()
    _require(len(payload) <= MAX_INPUT_BYTES)
    return payload.decode("utf-8", errors="strict")


def _csv(value: str) -> tuple[str, ...]:
    stripped = value.strip()
    if stripped in {"", "—"}:
        return ()
    return tuple(part.strip() for part in stripped.split(","))


def _frontmatter_list(source: str, key: str) -> tuple[str, ...]:
    match = re.search(rf"(?m)^{re.escape(key)}: \[([^\]]*)\]$", source)
    _require(match is not None)
    return _csv(match.group(1))


def _parse_plan(name: str, source: str) -> PlanRecord:
    match = re.fullmatch(r"04-([0-9]{2})-PLAN\.md", name)
    _require(match is not None)
    number = match.group(1)
    plan_id = f"04-{number}"
    declared = re.search(r"(?m)^plan: ([0-9]{2})$", source)
    wave = re.search(r"(?m)^wave: ([0-9]+)$", source)
    _require(
        source.startswith("---\n")
        and re.search(r"(?m)^phase: 04-controlled-draft-pr$", source) is not None
        and declared is not None
        and declared.group(1) == number
        and wave is not None
    )
    dependencies = _frontmatter_list(source, "depends_on")
    requirements = _frontmatter_list(source, "requirements")
    blocks = re.findall(r"<task\b[^>]*>.*?</task>", source, flags=re.DOTALL)
    _require(bool(blocks))
    commands: list[str] = []
    for ordinal, block in enumerate(blocks, 1):
        task_name = re.search(r"<name>(04-[0-9]{2}-[0-9]{2}):", block)
        automated = re.findall(r"<automated>(.*?)</automated>", block, flags=re.DOTALL)
        _require(
            task_name is not None
            and task_name.group(1) == f"{plan_id}-{ordinal:02d}"
            and len(automated) == 1
        )
        commands.append(html.unescape(automated[0].strip()))
    return PlanRecord(plan_id, wave.group(1), dependencies, requirements, tuple(commands))


def parse_plan_tasks(phase: Path) -> tuple[dict[str, PlanRecord], dict[str, str]]:
    plans: dict[str, PlanRecord] = {}
    commands: dict[str, str] = {}
    for name in PLAN_NAMES:
        record = _parse_plan(name, _read(phase / name))
        _require(record.plan_id not in plans)
        plans[record.plan_id] = record
        for ordinal, command in enumerate(record.commands, 1):
            task_id = f"{record.plan_id}-{ordinal:02d}"
            _require(task_id not in commands)
            commands[task_id] = command
    return plans, commands


def _table_rows(source: str, heading: str) -> tuple[str, ...]:
    _require(source.count(heading) == 1)
    lines = source.split(heading, 1)[1].splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith("|")), None)
    _require(start is not None and start + 2 < len(lines))
    rows: list[str] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append(line)
    _require(bool(rows))
    return tuple(rows)


def _parse_task_rows(source: str) -> tuple[MapRow, ...]:
    rows: list[MapRow] = []
    for line in _table_rows(source, "## Exact Per-Task Verification Map"):
        cells = tuple(cell.strip() for cell in line[1:-1].split("|"))
        _require(len(cells) == 10)
        task_id, plan_id, wave, dependency_text, requirement_text = cells[:5]
        command = html.unescape(cells[5][1:-1]) if cells[5].startswith("`") and cells[5].endswith("`") else cells[5]
        rows.append(
            MapRow(
                task_id,
                plan_id,
                wave,
                _csv(dependency_text),
                _csv(requirement_text),
                command,
                cells[6],
                cells[7],
            )
        )
    return tuple(rows)


def verify_requirement_inverse_map(
    rows: tuple[MapRow, ...], source: str
) -> dict[str, tuple[str, ...]]:
    inverse = {
        requirement: tuple(row.task_id for row in rows if requirement in row.requirements)
        for requirement in EXPECTED_REQUIREMENTS
    }
    _require(all(inverse.values()))
    coverage_rows = _table_rows(source, "## Requirement Inverse Map")
    _require(len(coverage_rows) == len(EXPECTED_REQUIREMENTS))
    for line, requirement in zip(coverage_rows, EXPECTED_REQUIREMENTS, strict=True):
        cells = tuple(cell.strip() for cell in line[1:-1].split("|"))
        _require(
            len(cells) == 3
            and cells[0] == requirement
            and cells[1].startswith("Positive:")
            and tuple(re.findall(r"04-[0-9]{2}-[0-9]{2}", cells[1])) == inverse[requirement]
            and cells[2].startswith("Prohibition:")
            and len(cells[2]) > len("Prohibition:")
        )
    return inverse


def _validate_command(command: str) -> None:
    _require(command and command == command.strip())
    _require(" uv " not in f" {command} " and not command.startswith("uv "))
    _require("||" not in command and ";" not in command and "| " not in command)
    for segment in command.split(" && "):
        if "uv" in segment or "pytest" in segment or "ruff" in segment:
            _require(segment.startswith(LOCAL_UV) or segment.startswith("SKILLSCOUT_LIVE_CANARY=1 " + LOCAL_UV))


def verify_validation_map(repository_root: Path) -> None:
    root = Path(os.path.abspath(os.fspath(repository_root)))
    phase = root / PHASE_DIRECTORY
    plans, commands = parse_plan_tasks(phase)
    _require(tuple(plans) == tuple(EXPECTED_PLAN_FACTS))
    _require(tuple(commands) == EXPECTED_TASK_IDS)
    for plan_id, record in plans.items():
        _require((record.wave, record.dependencies, record.requirements) == EXPECTED_PLAN_FACTS[plan_id])

    source = _read(phase / VALIDATION_NAME)
    _require(
        "The live command in task `04-10-01` is historical Gate B4 evidence"
        in source
    )
    rows = _parse_task_rows(source)
    _require(tuple(row.task_id for row in rows) == EXPECTED_TASK_IDS)
    _require(len(rows) == len({row.task_id for row in rows}))
    for row in rows:
        record = plans.get(row.plan_id)
        _require(
            record is not None
            and row.task_id.startswith(row.plan_id + "-")
            and row.wave == record.wave
            and row.dependencies == record.dependencies
            and row.requirements
            and set(row.requirements).issubset(record.requirements)
            and row.command == commands[row.task_id]
            and row.evidence not in {"", "—"}
        )
        _validate_command(row.command)
    _require(
        next(row for row in rows if row.task_id == "04-01-01").evidence
        == "tests/test_publication_domain.py"
    )
    for plan_id, record in plans.items():
        mapped = {
            requirement
            for row in rows
            if row.plan_id == plan_id
            for requirement in row.requirements
        }
        _require(mapped == set(record.requirements))
    verify_requirement_inverse_map(rows, source)

    _require(
        tuple(row.human_gate for row in rows if row.human_gate != "—")
        == ("Gate A4", "Gate A4", "Gate B4")
    )
    _require(
        "| **Human gates** | Gate A4 exact action identity; Gate B4 live governance/canary evidence |"
        in source
    )
    _require(
        "- Gate A4 is non-auto-approvable." in source
        and "- Gate B4 is non-auto-approvable." in source
    )
    _require(all(source.count(identity) >= 1 for identity in ACTION_IDENTITIES))
    _require("audit digest `d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622`" in source)
    _require("workflow SHA-256 `224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c`" in source)
    _require("ruleset digest `sha256:e58e74403d890296e44105cb60b42abffe522f11d169884d6d51f285b63948b5`" in source)
    _require(source.count(EXPECTED_RELEASE_COMMAND) >= 2)
    _require(
        "| **Static quality command** | `.tools/uv-0.11.29/bin/uv run --locked ruff check .` |"
        in source
    )
    _require("status: complete" in source and "nyquist_compliant: true" in source and "wave_0_complete: true" in source)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repository-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        root = Path(__file__).resolve().parents[1]
        if arguments:
            namespace = _parser().parse_args(arguments)
            _require(namespace.repository_root is not None)
            root = namespace.repository_root
        verify_validation_map(root)
    except (ValidationMapError, OSError, UnicodeError, ValueError, TypeError, SystemExit):
        print(FAILURE_DIAGNOSTIC, file=sys.stderr)
        return 1
    print(SUCCESS_DIAGNOSTIC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
