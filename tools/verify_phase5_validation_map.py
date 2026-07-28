#!/usr/bin/env python3
"""Dependency-free, read-only exact validation-map verifier for Phase 5."""

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

PHASE_DIRECTORY = Path(".planning/phases/05-automated-discovery-operations")
PLAN_NAMES = tuple(f"05-{number:02d}-PLAN.md" for number in range(1, 15))
VALIDATION_NAME = "05-VALIDATION.md"
SUMMARY_NAME = "05-10-SUMMARY.md"
VERIFICATION_NAME = "05-VERIFICATION.md"
MAX_INPUT_BYTES = 512_000
SUCCESS_DIAGNOSTIC = "phase5 validation map valid"
FAILURE_DIAGNOSTIC = "phase5 validation map invalid"
LOCAL_UV = ".tools/uv-0.11.29/bin/uv"
EXPECTED_REQUIREMENTS = ("DISC-01", "DISC-02", "DISC-03", "OPS-02", "OPS-03")
EXPECTED_PLAN_FACTS = {
    "05-01": ("1", (), EXPECTED_REQUIREMENTS),
    "05-02": ("1", (), ("DISC-01", "DISC-02", "DISC-03", "OPS-03")),
    "05-03": ("1", (), EXPECTED_REQUIREMENTS),
    "05-04": ("2", ("05-01", "05-02"), ("DISC-01", "DISC-02", "DISC-03", "OPS-03")),
    "05-05": ("2", ("05-01", "05-03"), ("DISC-02", "DISC-03", "OPS-02", "OPS-03")),
    "05-06": ("2", ("05-01", "05-03"), ("OPS-02", "OPS-03")),
    "05-07": ("6", ("05-04", "05-12", "05-13", "05-14"), EXPECTED_REQUIREMENTS),
    "05-08": ("7", ("05-07",), EXPECTED_REQUIREMENTS),
    "05-09": ("8", ("05-08",), ("DISC-01", "OPS-02", "OPS-03")),
    "05-10": ("9", ("05-09",), EXPECTED_REQUIREMENTS),
    "05-11": ("2", ("05-01", "05-03"), ("DISC-02", "OPS-03")),
    "05-12": ("3", ("05-05", "05-06"), ("OPS-02", "OPS-03")),
    "05-13": ("5", ("05-11", "05-14"), ("DISC-02", "OPS-02", "OPS-03")),
    "05-14": ("4", ("05-06", "05-11", "05-12"), ("DISC-02", "OPS-02", "OPS-03")),
}
EXPECTED_TASK_IDS = tuple(
    f"05-{plan:02d}-{task:02d}" for plan in range(1, 15) for task in (1, 2)
)
ACTION_IDENTITIES = (
    "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
    "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1",
)
HOSTED_IDENTITIES = (
    "1ee162ea47cf86b7faec68bfba37b7a9b2af3b25472066312b43c4a5e4414cdd",
    "e1c6687d4c85c4881a433d03da8d66168915c8e316e4817e1415835b52e3ba72",
    "8157cb686b9bf18bfa800811b1fe1529ed9a15ec371fe36ec1708233052b7cfd",
    "96ce9f39db49ce647a88b83ec4db3cb0135e5cf51c1eb2f11961cfd243b23cf0",
    "9c59cd9822eecec913f82d24c7880a443ba9416795b8996c6201f33c4df5805d",
)
EXPECTED_RELEASE_COMMAND = (
    f"{LOCAL_UV} run --locked python tools/verify_phase5_validation_map.py && "
    f"{LOCAL_UV} run --locked pytest -q tests/test_phase5_validation_map.py "
    "tests/test_phase5_acceptance.py tests/test_discovery_domain.py "
    "tests/test_github_search.py tests/test_operations_state.py "
    "tests/test_state_branch.py tests/test_discovery_application.py "
    "tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py "
    "tests/test_discovery_workflow.py tests/test_discovery_security.py "
    "tests/test_semantic_provider.py tests/test_openai_extract.py "
    "tests/test_openai_generate.py tests/test_openai_review.py "
    "tests/test_state_integrity.py tests/test_pipeline_resume.py "
    "tests/test_phase3_pipeline.py tests/test_publication_recovery.py "
    f"tests/test_publication_security.py -x && {LOCAL_UV} run --locked ruff check . && "
    f"{LOCAL_UV} run --locked pytest -q && "
    f"{LOCAL_UV} run --locked python tools/verify_phase5_acceptance.py"
)
PROHIBITION_EVIDENCE = (
    "D-01 | Fixed reviewed query set and daily/manual triggers only",
    "D-02 | Numeric repository ID is deduplication authority",
    "D-03 | Durable literal 100/20 reservations are non-refundable",
    "D-04 | Unknown semantic outcomes quarantine without replay",
    "D-05 | Exact three-store JSON/SQLite rebuild and equality",
    "D-06 | Parent-bound non-force CAS with exact reread",
    "D-07 | Fixed shared non-cancelling production concurrency",
    "D-08 | Allowlisted state, handoff, logs and outputs only",
    "D-09 | No state-object pruning",
)


class ValidationMapError(Exception):
    """Closed failure for a missing or inconsistent validation fact."""


class PlanRecord(NamedTuple):
    plan_id: str
    wave: str
    dependencies: tuple[str, ...]
    requirements: tuple[str, ...]
    commands: tuple[str, ...]
    artifacts: tuple[tuple[str, ...], ...]


class MapRow(NamedTuple):
    task_id: str
    plan_id: str
    wave: str
    dependencies: tuple[str, ...]
    requirements: tuple[str, ...]
    command: str
    artifacts: tuple[str, ...]
    evidence: str


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
    match = re.fullmatch(r"05-([0-9]{2})-PLAN\.md", name)
    _require(match is not None)
    number = match.group(1)
    plan_id = f"05-{number}"
    declared = re.search(r'(?m)^plan: "([0-9]{2})"$', source)
    wave = re.search(r"(?m)^wave: ([0-9]+)$", source)
    _require(
        source.startswith("---\n")
        and re.search(r"(?m)^phase: 05-automated-discovery-operations$", source)
        is not None
        and declared is not None
        and declared.group(1) == number
        and wave is not None
    )
    dependencies = _frontmatter_list(source, "depends_on")
    requirements = _frontmatter_list(source, "requirements")
    blocks = re.findall(r"<task\b[^>]*>.*?</task>", source, flags=re.DOTALL)
    _require(len(blocks) == 2)
    commands: list[str] = []
    artifacts: list[tuple[str, ...]] = []
    for ordinal, block in enumerate(blocks, 1):
        task_name = re.search(r"<name>Task (05-[0-9]{2}-[0-9]{2}):", block)
        automated = re.findall(r"<automated>(.*?)</automated>", block, flags=re.DOTALL)
        files = re.search(r"<files>(.*?)</files>", block, flags=re.DOTALL)
        _require(
            task_name is not None
            and task_name.group(1) == f"{plan_id}-{ordinal:02d}"
            and len(automated) == 1
            and files is not None
        )
        commands.append(html.unescape(automated[0].strip()))
        artifacts.append(_csv(" ".join(files.group(1).split())))
    return PlanRecord(
        plan_id,
        wave.group(1),
        dependencies,
        requirements,
        tuple(commands),
        tuple(artifacts),
    )


def parse_plan_tasks(
    phase: Path,
) -> tuple[dict[str, PlanRecord], dict[str, str], dict[str, tuple[str, ...]]]:
    plans: dict[str, PlanRecord] = {}
    commands: dict[str, str] = {}
    artifacts: dict[str, tuple[str, ...]] = {}
    for name in PLAN_NAMES:
        record = _parse_plan(name, _read(phase / name))
        _require(record.plan_id not in plans)
        plans[record.plan_id] = record
        for ordinal, (command, task_artifacts) in enumerate(
            zip(record.commands, record.artifacts, strict=True), 1
        ):
            task_id = f"{record.plan_id}-{ordinal:02d}"
            _require(task_id not in commands)
            commands[task_id] = command
            artifacts[task_id] = task_artifacts
    return plans, commands, artifacts


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
        _require(len(cells) == 8)
        command = cells[5]
        _require(command.startswith("`") and command.endswith("`"))
        rows.append(
            MapRow(
                cells[0],
                cells[1],
                cells[2],
                _csv(cells[3]),
                _csv(cells[4]),
                html.unescape(command[1:-1]),
                _csv(cells[6]),
                cells[7],
            )
        )
    return tuple(rows)


def _validate_command(command: str) -> None:
    _require(command and command == command.strip())
    _require("||" not in command and ";" not in command and "| " not in command)
    for segment in command.split(" && "):
        _require(segment.startswith(LOCAL_UV))
        _require(" run --locked " in segment)


def _verify_inverse(rows: tuple[MapRow, ...], source: str) -> None:
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
            and tuple(re.findall(r"05-[0-9]{2}-[0-9]{2}", cells[1]))
            == inverse[requirement]
            and cells[2].startswith("Prohibition:")
            and len(cells[2]) > len("Prohibition:")
        )


def _frontmatter(source: str) -> str:
    _require(source.startswith("---\n"))
    end = source.find("\n---\n", 4)
    _require(end != -1)
    return source[4:end]


def _frontmatter_has(source: str, key: str, value: str) -> bool:
    return (
        re.search(
            rf"(?m)^{re.escape(key)}: {re.escape(value)}$",
            _frontmatter(source),
        )
        is not None
    )


def _verify_completion(phase: Path, validation: str) -> None:
    summary = _read(phase / SUMMARY_NAME)
    verification = _read(phase / VERIFICATION_NAME)
    _require(
        _frontmatter_has(validation, "phase", "05")
        and _frontmatter_has(validation, "status", "complete")
        and _frontmatter_has(validation, "execution_status", "complete")
        and validation.count(
            "- [x] Plan 05-10 release-chain execution is recorded in "
            "`05-10-SUMMARY.md`."
        )
        == 1
        and "Execution completion is established separately by the Plan 05-10 "
        "release chain and `05-VERIFICATION.md`;" in validation
        and "**Validation result:** Nyquist-compliant, exact release chain passed, "
        "hosted Gate B4 approved, and Phase 05 independently verified."
        in validation
    )
    _require(
        _frontmatter_has(summary, "phase", "05-automated-discovery-operations")
        and _frontmatter_has(summary, "plan", '"10"')
        and _frontmatter_has(summary, "status", "complete")
        and _frontmatter_has(
            summary,
            "requirements-completed",
            "[DISC-01, DISC-02, DISC-03, OPS-02, OPS-03]",
        )
        and summary.count("\n        status: pass\n") == 5
        and 'ref: "05-10-PLAN.md Task 05-10-02 exact automated command"' in summary
        and "## Self-Check: PASSED" in summary
        and all(identity in summary for identity in HOSTED_IDENTITIES)
    )
    _require(
        _frontmatter_has(verification, "phase", "05-automated-discovery-operations")
        and _frontmatter_has(verification, "status", "passed")
        and _frontmatter_has(verification, "score", "6/6 must-haves verified")
        and _frontmatter_has(verification, "behavior_unverified", "0")
        and _frontmatter_has(verification, "overrides_applied", "0")
        and _frontmatter_has(verification, "gaps", "[]")
        and _frontmatter_has(verification, "human_verification", "[]")
        and "| Independent validation-map integrity |" in verification
        and "| Phase 5 and cross-phase focused release set |" in verification
        and "**No goal-blocking gaps found.**" in verification
        and all(identity in verification for identity in HOSTED_IDENTITIES)
    )


def verify_validation_map(repository_root: Path) -> None:
    root = Path(os.path.abspath(os.fspath(repository_root)))
    phase = root / PHASE_DIRECTORY
    plans, commands, artifacts = parse_plan_tasks(phase)
    _require(tuple(plans) == tuple(EXPECTED_PLAN_FACTS))
    _require(tuple(commands) == EXPECTED_TASK_IDS)
    for plan_id, record in plans.items():
        _require(
            (record.wave, record.dependencies, record.requirements)
            == EXPECTED_PLAN_FACTS[plan_id]
        )

    source = _read(phase / VALIDATION_NAME)
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
            and row.artifacts == artifacts[row.task_id]
            and row.evidence not in {"", "—"}
        )
        _validate_command(row.command)
    for plan_id, record in plans.items():
        mapped = {
            requirement
            for row in rows
            if row.plan_id == plan_id
            for requirement in row.requirements
        }
        _require(mapped == set(record.requirements))
    _verify_inverse(rows, source)

    _require(all(source.count(value) == 1 for value in PROHIBITION_EVIDENCE))
    _require(all(source.count(identity) >= 1 for identity in ACTION_IDENTITIES))
    _require(all(source.count(identity) >= 1 for identity in HOSTED_IDENTITIES))
    _require(source.count(EXPECTED_RELEASE_COMMAND) >= 2)
    for required_suite in (
        "tests/test_semantic_durability.py",
        "tests/test_discovery_publication_handoff.py",
        "tests/test_semantic_provider.py",
        "tests/test_openai_extract.py",
        "tests/test_openai_generate.py",
        "tests/test_openai_review.py",
        "tests/test_state_integrity.py",
        "tests/test_pipeline_resume.py",
        "tests/test_phase3_pipeline.py",
        "tests/test_publication_recovery.py",
        "tests/test_publication_security.py",
    ):
        _require(required_suite in EXPECTED_RELEASE_COMMAND)
    _require(
        "nyquist_compliant: true" in source
        and "wave_0_complete: true" in source
        and "hosted_gate_b4_status: approved" in source
        and "Phase 6 real-repository acceptance is not claimed." in source
    )
    _verify_completion(phase, source)


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
    except (
        ValidationMapError,
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        KeyError,
        SystemExit,
    ):
        print(FAILURE_DIAGNOSTIC, file=sys.stderr)
        return 1
    print(SUCCESS_DIAGNOSTIC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
