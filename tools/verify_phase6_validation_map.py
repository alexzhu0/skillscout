#!/usr/bin/env python3
"""Read-only, stdlib-only verifier for the exact Phase 6 validation contract."""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / ".planning/phases/06-adversarial-mvp-acceptance"
VALIDATION = PHASE / "06-VALIDATION.md"
SUCCESS = "phase6 validation map valid"
FAILURE = "phase6 validation map invalid"

CHECKPOINTS = {
    "06-02-03": ("checkpoint:human-verify", "06-02-02", "06-03-01"),
    "06-06-03": ("checkpoint:human-verify", "06-06-02", "06-07-01"),
    "06-07-01": ("checkpoint:decision", "06-06-03", "06-07-02"),
    "06-07-03": ("checkpoint:human-verify", "06-07-02", "06-08-01"),
    "06-08-01": ("checkpoint:decision", "06-07-03", "06-08-02"),
    "06-09-01": ("checkpoint:decision", "06-08-03", "06-09-02"),
    "06-10-01": ("checkpoint:decision", "06-09-02", "06-10-02"),
    "06-11-01": ("checkpoint:human-verify", "06-10-03", "06-11-02"),
    "06-12-01": ("checkpoint:human-action", "06-11-03", "06-12-02"),
}

WAVE_ZERO_FILES = {
    "tests/fixtures/acceptance/scenario_matrix.json": "06-01-01",
    "tests/test_acceptance_domain.py": "06-01-01",
    "tools/verify_phase6_red_contracts.py": "06-01-01",
    "tests/test_acceptance_application.py": "06-01-02",
    "tests/test_semantic_provider.py": "06-01-02",
    ".planning/phases/06-adversarial-mvp-acceptance/06-VALIDATION.md": "06-01-03",
    "tools/verify_phase6_validation_map.py": "06-01-03",
    "tools/verify_phase6_acceptance.py": "06-01-03",
    "tests/test_phase6_adversarial.py": "06-02-01",
    "tests/test_phase6_acceptance.py": "06-02-01",
    "tests/test_phase6_workflow.py": "06-02-01",
    "tests/test_phase6_source_execution.py": "06-02-01",
    ".github/workflows/phase6-acceptance.yml": "06-02-02",
}

OWNERS = {
    "BenchmarkSelectionSource": "06-04-01",
    "BenchmarkCoverageRole": "06-04-01",
    "AcceptanceTerminalClass": "06-04-01",
    "BenchmarkEntryV1": "06-04-01",
    "NominationSetV1": "06-04-01",
    "BenchmarkLockAttestationV1": "06-04-01",
    "LockedBenchmarkManifestV1": "06-04-01",
    "AcceptanceScenarioResultV1": "06-04-01",
    "HostedIsolationCapabilityV1": "06-04-01",
    "OfflineAdversarialRunV1": "06-04-01",
    "ReplayEvidenceV1": "06-04-01",
    "ChangedSourceEvidenceV1": "06-04-01",
    "PublicationReplayCompletionV1": "06-04-01",
    "ChangedSourceDraftUpdateCompletionV1": "06-04-01",
    "GateB4BindingV1": "06-04-01",
    "HumanSkillReviewAttestationV1": "06-04-01",
    "ProbeCleanupAttestationV1": "06-04-01",
    "ReviewerCalibrationV1": "06-04-01",
    "AcceptanceGateResultV1": "06-04-01",
    "AcceptanceEvidenceRootV1": "06-04-01",
    "AcceptanceReleaseVerdictV1": "06-04-01",
    "acceptance_nomination": "06-04-02",
    "acceptance_benchmark_lock": "06-04-02",
    "acceptance_scenario": "06-04-02",
    "acceptance_hosted_isolation_capability": "06-04-02",
    "acceptance_offline_adversarial_run": "06-04-02",
    "acceptance_replay": "06-04-02",
    "acceptance_changed_source": "06-04-02",
    "acceptance_publication_replay_completion": "06-04-02",
    "acceptance_changed_source_draft_update_completion": "06-04-02",
    "acceptance_gate_b4": "06-04-02",
    "acceptance_human_review": "06-04-02",
    "acceptance_cleanup": "06-04-02",
    "acceptance_reviewer_calibration": "06-04-02",
    "acceptance_gate": "06-04-02",
    "acceptance_report_root": "06-04-02",
    "OperationsStateStore.record_acceptance_fact": "06-04-02",
    "OperationsStateStore.acceptance_snapshot": "06-04-02",
    "export_owned_state": "06-04-02",
    "rebuild_owned_state": "06-04-02",
    "SemanticStage": "06-03-01",
    "DEEPSEEK_MODEL_BY_STAGE": "06-03-01",
    "NominationDependencies": "06-05-01",
    "LockedCampaignDependencies": "06-05-01",
    "ReplayUpdateDependencies": "06-05-01",
    "HumanAttestationDependencies": "06-05-01",
    "CleanupAttestationDependencies": "06-05-01",
    "AcceptanceRebuildDependencies": "06-05-01",
    "nominate-benchmark": "06-05-02",
    "run-acceptance": "06-05-02",
    "record-acceptance-attestation": "06-05-02",
    "rebuild-acceptance": "06-05-02",
    "phase6_action": "06-15-01",
    "isolation-probe": "06-02-02",
    "nominate": "06-15-01",
    "offline_adversarial": "06-06-02",
    "live_benchmark": "06-15-01",
    "changed_source": "06-15-01",
    "fresh_gate_b4": "06-15-01",
    "value_publication": "06-15-01",
    "human_attestation": "06-15-01",
    "cleanup_attestation": "06-15-01",
    "rebuild_report": "06-15-01",
    "verify_phase6_red_contracts.py": "06-01-01",
    "verify_phase6_validation_map.py": "06-01-03",
    "verify_phase6_acceptance.py": "06-01-03",
    "verify_phase6_source_execution.py": "06-15-01",
    "06-ACCEPTANCE-REPORT.md": "06-13-02",
    "06-RELEASE-REQUIREMENTS.json": "06-13-02",
}


class InvalidMap(Exception):
    pass


@dataclass(frozen=True)
class Plan:
    plan_id: str
    wave: int
    dependencies: tuple[str, ...]
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class Task:
    task_id: str
    plan_id: str
    task_type: str
    files: tuple[str, ...]
    command: str | None


@dataclass(frozen=True)
class Row:
    task_id: str
    plan_id: str
    wave: int
    requirements: tuple[str, ...]
    feedback: str
    command: str


def require(condition: bool) -> None:
    if not condition:
        raise InvalidMap


def read(path: Path) -> str:
    payload = path.read_bytes()
    require(len(payload) <= 2_000_000)
    return payload.decode("utf-8", errors="strict")


def ids(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"TEST-\d{2}", value))


def parse_list(source: str, field: str) -> tuple[str, ...]:
    match = re.search(rf"^{re.escape(field)}:\s*\[([^\]]*)\]", source, re.MULTILINE)
    require(match is not None)
    return tuple(item.strip() for item in match.group(1).split(",") if item.strip())


def parse_plans() -> tuple[dict[str, Plan], dict[str, Task]]:
    plans: dict[str, Plan] = {}
    tasks: dict[str, Task] = {}
    paths = tuple(sorted(PHASE.glob("06-??-PLAN.md")))
    require(len(paths) == 15)
    for path in paths:
        source = read(path)
        plan_number = re.search(r'^plan:\s*"(\d{2})"$', source, re.MULTILINE)
        wave = re.search(r"^wave:\s*(\d+)$", source, re.MULTILINE)
        require(plan_number is not None and wave is not None)
        plan_id = f"06-{plan_number.group(1)}"
        plan = Plan(
            plan_id=plan_id,
            wave=int(wave.group(1)),
            dependencies=parse_list(source, "depends_on"),
            requirements=parse_list(source, "requirements"),
        )
        require(plan_id not in plans)
        plans[plan_id] = plan
        blocks = re.findall(
            r'<task\s+type="([^"]+)"[^>]*>(.*?)</task>',
            source,
            re.DOTALL,
        )
        require(blocks)
        for task_type, block in blocks:
            name = re.search(r"<name>Task (06-\d{2}-\d{2}):", block)
            require(name is not None)
            task_id = name.group(1)
            file_match = re.search(r"<files>(.*?)</files>", block, re.DOTALL)
            command_match = re.search(
                r"<automated>(.*?)</automated>",
                block,
                re.DOTALL,
            )
            files = (
                tuple(
                    item.strip()
                    for item in file_match.group(1).split(",")
                    if item.strip()
                )
                if file_match
                else ()
            )
            command = (
                html.unescape(" ".join(command_match.group(1).split()))
                if command_match
                else None
            )
            require(task_id.startswith(plan_id + "-") and task_id not in tasks)
            tasks[task_id] = Task(task_id, plan_id, task_type, files, command)
    require(len(tasks) == 38)
    return plans, tasks


def parse_rows(source: str) -> dict[str, Row]:
    section = source.split("## Per-Task Verification Map", 1)[1].split(
        "## Requirement Inverse Coverage", 1
    )[0]
    rows: dict[str, Row] = {}
    for line in section.splitlines():
        if not re.match(r"^\| 06-\d{2}-\d{2} \|", line):
            continue
        cells = tuple(cell.strip().strip("`") for cell in line.strip().strip("|").split("|"))
        require(len(cells) == 7)
        task_id, plan_id, wave, requirement, feedback, command, _status = cells
        require(task_id not in rows)
        rows[task_id] = Row(
            task_id,
            plan_id,
            int(wave),
            ids(requirement.replace("TEST-01..04", "TEST-01 TEST-02 TEST-03 TEST-04")),
            feedback,
            html.unescape(command),
        )
    return rows


def parse_inverse(source: str) -> dict[str, set[str]]:
    section = source.split("## Requirement Inverse Coverage", 1)[1].split(
        "## Exact Cross-Plan Ownership Registry", 1
    )[0]
    result: dict[str, set[str]] = {}
    for line in section.splitlines():
        match = re.match(r"^\| (TEST-\d{2}) \| (.+) \|$", line)
        if match:
            result[match.group(1)] = set(re.findall(r"06-\d{2}-\d{2}", match.group(2)))
    return result


def parse_registry(source: str) -> tuple[dict[str, tuple[str, tuple[str, ...]]], dict[str, str]]:
    section = source.split("## Exact Cross-Plan Ownership Registry", 1)[1].split(
        "### Wave 0 File Ownership", 1
    )[0]
    registry: dict[str, tuple[str, tuple[str, ...]]] = {}
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        require(len(cells) == 4)
        surface = cells[0].strip("`")
        owner = cells[2]
        consumers = tuple(re.findall(r"06-\d{2}", cells[3]))
        require(surface not in registry)
        registry[surface] = (owner, consumers)
    file_section = source.split("### Wave 0 File Ownership", 1)[1].split(
        "\n---\n", 1
    )[0]
    files: dict[str, str] = {}
    for line in file_section.splitlines():
        if not line.startswith("| `"):
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        require(len(cells) == 2)
        files[cells[0].strip("`")] = cells[1]
    return registry, files


def reachable(owner: str, consumer: str, plans: dict[str, Plan]) -> bool:
    if owner == consumer:
        return True
    seen: set[str] = set()
    pending = list(plans[consumer].dependencies)
    while pending:
        current = pending.pop()
        if current == owner:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(plans[current].dependencies)
    return False


def verify(*, wave_zero_complete: bool) -> None:
    plans, tasks = parse_plans()
    source = read(VALIDATION)
    rows = parse_rows(source)
    require(set(rows) == set(tasks))
    for task_id, task in tasks.items():
        row = rows[task_id]
        plan = plans[task.plan_id]
        require(
            row.plan_id == task.plan_id
            and row.wave == plan.wave
            and row.command
            and row.requirements
            and set(row.requirements).issubset(plan.requirements)
        )
        require(".tools/uv-0.11.29/bin/uv" in row.command or "git diff" in row.command)
        if task.command is not None:
            require(row.command == task.command)
    for plan_id, plan in plans.items():
        forward = {
            requirement
            for row in rows.values()
            if row.plan_id == plan_id
            for requirement in row.requirements
        }
        require(forward == set(plan.requirements))
    inverse = parse_inverse(source)
    require(set(inverse) == {"TEST-01", "TEST-02", "TEST-03", "TEST-04"})
    for requirement in inverse:
        require(
            inverse[requirement]
            == {
                row.task_id
                for row in rows.values()
                if requirement in row.requirements
            }
        )
    actual_checkpoints = {
        task_id for task_id, task in tasks.items() if task.task_type.startswith("checkpoint:")
    }
    require(actual_checkpoints == set(CHECKPOINTS))
    for task_id, (kind, predecessor, post_ingest) in CHECKPOINTS.items():
        feedback = rows[task_id].feedback
        require(
            kind in feedback
            and f"predecessor {predecessor}" in feedback
            and f"post-ingest verifier {post_ingest}" in feedback
        )
    registry, wave_files = parse_registry(source)
    require(set(registry) == set(OWNERS))
    for surface, expected_owner in OWNERS.items():
        owner, consumers = registry[surface]
        require(owner == expected_owner and owner in tasks and consumers)
        owner_plan = tasks[owner].plan_id
        for consumer_plan in consumers:
            require(consumer_plan in plans and reachable(owner_plan, consumer_plan, plans))
    require(wave_files == WAVE_ZERO_FILES)
    for file, owner in wave_files.items():
        require(file in tasks[owner].files)
    require("nyquist_compliant: false" in source)
    if wave_zero_complete:
        for file in WAVE_ZERO_FILES:
            require((ROOT / file).is_file())
        require("wave_0_complete: true" in source)
    else:
        require("wave_0_complete: false" in source)
    forbidden = ("token value", "approved-gate", "hosted result:", "repository_sha:")
    require(all(value not in source.casefold() for value in forbidden))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--plan-contract", action="store_true")
    parser.add_argument("--wave-zero-complete", action="store_true")
    parser.add_argument("--repository-root", type=Path)
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
        global ROOT, PHASE, VALIDATION
        if args.repository_root is not None:
            ROOT = args.repository_root.resolve()
            PHASE = ROOT / ".planning/phases/06-adversarial-mvp-acceptance"
            VALIDATION = PHASE / "06-VALIDATION.md"
        require(not (args.plan_contract and args.wave_zero_complete))
        verify(wave_zero_complete=args.wave_zero_complete)
    except (InvalidMap, OSError, UnicodeError, ValueError, TypeError, SystemExit):
        print(FAILURE, file=sys.stderr)
        return 1
    print(SUCCESS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
