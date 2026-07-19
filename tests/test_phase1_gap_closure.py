"""Cross-root acceptance evidence for the closed Phase 1 gaps."""

from __future__ import annotations

import ast
import json
import sqlite3
import tomllib
from pathlib import Path
from typing import Any

from conftest import parse_cli_error, parse_cli_json
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode
from skillscout.domain.enums import PipelineStage

PROJECT_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "skillscout"
EXPECTED_FINDINGS = tuple(
    [f"CR-{number:02d}" for number in range(1, 9)]
    + [f"WR-{number:02d}" for number in range(1, 4)]
)

FINDING_NODES: dict[str, tuple[str, ...]] = {
    "CR-01": (
        "tests/test_side_effect_policy.py::test_prior_permissive_policy_path_is_not_a_public_runtime_input",
        "tests/test_side_effect_policy.py::test_remote_declaring_processor_is_rejected_before_invocation",
    ),
    "CR-02": (
        "tests/test_pipeline_resume.py::test_changed_a_prime_completes_without_reuse_and_both_runs_inspect",
        "tests/test_state_integrity.py::test_semantic_result_twins_use_distinct_run_scoped_rows",
    ),
    "CR-03": (
        "tests/test_pipeline_resume.py::test_unsupported_producer_is_rejected_before_run_creation",
    ),
    "CR-04": (
        "tests/test_pipeline_resume.py::test_invalid_or_oversized_output_closes_lifecycle_before_manifest_io",
    ),
    "CR-05": (
        "tests/test_state_integrity.py::test_full_chain_recomputes_result_id_after_coherent_manifest_rehash",
        "tests/test_state_integrity.py::test_every_bound_trust_entry_point_delegates_to_one_full_chain_verifier",
    ),
    "CR-06": (
        "tests/test_cli_security.py::test_persisted_diagnostic_and_telemetry_tampering_is_never_projected",
    ),
    "CR-07": (
        "tests/test_state_integrity.py::test_parent_swap_after_state_anchor_cannot_redirect_state_or_manifests",
        "tests/test_state_integrity.py::test_parent_swap_during_failed_snapshot_cleanup_never_touches_attacker",
    ),
    "CR-08": (
        "tests/test_pipeline_resume.py::test_manifest_sync_failure_never_advances_checkpoint",
        "tests/test_pipeline_resume.py::test_publication_sync_failure_prevents_terminal_transition",
    ),
    "WR-01": (
        "tests/test_pipeline_resume.py::test_database_failure_after_manifest_never_advances_checkpoint",
        "tests/test_pipeline_resume.py::test_indeterminate_failure_closure_is_reconciled_on_next_open",
    ),
    "WR-02": (
        "tests/test_state_integrity.py::test_malformed_schema_v2_fingerprint_is_rejected_without_mutation",
        "tests/test_state_integrity.py::test_schema_v2_integrity_failures_are_fixed_and_sanitized",
    ),
    "WR-03": (
        "tests/test_pipeline_resume.py::test_a_interrupt_b_interrupt_a_rerun_resumes_exact_a_without_touching_b",
    ),
}

ROOT_GAP_NODES: dict[str, tuple[str, ...]] = {
    "1": (
        "tests/test_phase1_gap_closure.py::test_production_capability_surface_remains_local_only",
        *FINDING_NODES["CR-01"],
    ),
    "2": (
        *FINDING_NODES["CR-03"],
        *FINDING_NODES["CR-04"],
        *FINDING_NODES["CR-07"],
        *FINDING_NODES["CR-08"],
        *FINDING_NODES["WR-01"],
    ),
    "3": (
        *FINDING_NODES["CR-05"],
        *FINDING_NODES["CR-06"],
        *FINDING_NODES["WR-02"],
    ),
    "4": (
        *FINDING_NODES["CR-02"],
        *FINDING_NODES["WR-03"],
        "tests/test_phase1_gap_closure.py::test_packaged_cli_changed_a_prime_dual_inspect_gap_acceptance",
        "tests/test_phase1_gap_closure.py::test_packaged_cli_a_b_a_exact_resume_gap_acceptance",
    ),
}

FORBIDDEN_PRODUCTION_MODULES = frozenset(
    {
        "aiohttp",
        "asyncio.subprocess",
        "github",
        "http",
        "httpx",
        "importlib",
        "openai",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
)
FORBIDDEN_DIRECT_CALLS = frozenset({"compile", "eval", "exec"})
FORBIDDEN_ATTRIBUTE_CALLS = frozenset(
    {
        "create_connection",
        "connect",
        "connect_ex",
        "popen",
        "sendmsg",
        "sendto",
        "system",
    }
)


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _fixture_with_goal(source: Path, target: Path, goal: str) -> Path:
    payload = json.loads(source.read_bytes())
    payload["workflow"]["goal"] = goal
    target.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return target


def _assert_summary(payload: dict[str, Any], *, reused: int) -> None:
    assert payload == {
        "last_stage": "publication_planner",
        "publication_plan_path": "publication-plan.json",
        "remote_writes_attempted": 0,
        "reused_stage_count": reused,
        "run_id": payload["run_id"],
        "status": "planned_not_published",
    }


def _assert_inspection(
    payload: dict[str, Any],
    *,
    run_id: str,
    status: str,
    stages: int,
    reused: int,
) -> None:
    assert payload["run"]["run_id"] == run_id
    assert payload["run"]["status"] == status
    assert payload["run"]["identity_state"] == "bound"
    assert payload["reused_stage_count"] == reused
    assert len(payload["results"]) == stages
    assert len(payload["attempts"]) == stages
    assert [result["stage"] for result in payload["results"]] == [
        stage.value for stage in tuple(PipelineStage)[:stages]
    ]
    assert payload["checkpoint"]["stage"] == tuple(PipelineStage)[stages - 1].value


def _all_regular_file_bytes(root: Path) -> bytes:
    return b"".join(
        path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    )


def _run_facts(connection: sqlite3.Connection, run_id: str) -> dict[str, object]:
    run = tuple(
        connection.execute(
            """SELECT schema_version, subject_id, fixture_hash, producer_version,
                      retry_policy_version, identity_state, status, created_at,
                      updated_at, error_code, error_summary, reused_stage_count
               FROM runs WHERE run_id = ?""",
            (run_id,),
        ).fetchone()
    )
    attempts = [
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM stage_attempts WHERE run_id = ? ORDER BY stage_index, attempt_no",
            (run_id,),
        )
    ]
    results = [
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM stage_results WHERE run_id = ? ORDER BY stage_index",
            (run_id,),
        )
    ]
    checkpoints = [
        tuple(row)
        for row in connection.execute(
            "SELECT * FROM checkpoints WHERE run_id = ? ORDER BY stage_index",
            (run_id,),
        )
    ]
    return {
        "run": run,
        "attempts": attempts,
        "results": results,
        "checkpoints": checkpoints,
    }


def _manifest_bytes_for_run(
    connection: sqlite3.Connection, state: Path, run_id: str
) -> dict[str, bytes]:
    locators = [
        str(row[0])
        for row in connection.execute(
            "SELECT manifest_path FROM stage_results WHERE run_id = ? ORDER BY stage_index",
            (run_id,),
        )
    ]
    root = state.with_suffix(".manifests")
    return {locator: (root / locator).read_bytes() for locator in locators}


def test_packaged_cli_happy_interrupt_resume_inspect_gap_acceptance(
    approved_fixture: Path, run_cli, tmp_path: Path
) -> None:
    canary = "OPENAI_API_KEY_PHASE1_GAP_DO_NOT_DISCLOSE"
    observed_output = bytearray()

    happy_state = tmp_path / canary / "happy.db"
    happy_output = tmp_path / canary / "happy-output"
    happy = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(happy_state),
        "--output",
        str(happy_output),
    )
    observed_output.extend(happy.stdout.encode())
    observed_output.extend(happy.stderr.encode())
    happy_payload = parse_cli_json(happy)
    _assert_summary(happy_payload, reused=0)
    happy_inspect = run_cli(
        "inspect-run",
        str(happy_payload["run_id"]),
        "--state",
        str(happy_state),
        "--format",
        "json",
    )
    observed_output.extend(happy_inspect.stdout.encode())
    observed_output.extend(happy_inspect.stderr.encode())
    _assert_inspection(
        parse_cli_json(happy_inspect),
        run_id=str(happy_payload["run_id"]),
        status="planned_not_published",
        stages=9,
        reused=0,
    )
    assert json.loads((happy_output / "publication-plan.json").read_bytes())[
        "remote_writes_attempted"
    ] == 0

    resume_state = tmp_path / canary / "resume.db"
    interrupted = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(resume_state),
        "--output",
        str(tmp_path / "never-written"),
        "--fail-after",
        "generator",
    )
    observed_output.extend(interrupted.stdout.encode())
    observed_output.extend(interrupted.stderr.encode())
    assert parse_cli_error(interrupted) == {
        "error": {
            "code": ErrorCode.PIPELINE_INTERRUPTED.value,
            "summary": ERROR_SUMMARIES[ErrorCode.PIPELINE_INTERRUPTED],
        }
    }
    with _connect(resume_state) as connection:
        run_id = str(connection.execute("SELECT run_id FROM runs").fetchone()[0])
        prefix = [
            tuple(row)
            for row in connection.execute(
                """SELECT result_row_id, result_id, output_hash, manifest_hash
                   FROM stage_results ORDER BY stage_index"""
            )
        ]
    assert len(prefix) == 6

    resumed_output = tmp_path / canary / "resumed-output"
    resumed = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(resume_state),
        "--output",
        str(resumed_output),
    )
    observed_output.extend(resumed.stdout.encode())
    observed_output.extend(resumed.stderr.encode())
    resumed_payload = parse_cli_json(resumed)
    _assert_summary(resumed_payload, reused=6)
    assert resumed_payload["run_id"] == run_id
    with _connect(resume_state) as connection:
        assert [
            tuple(row)
            for row in connection.execute(
                """SELECT result_row_id, result_id, output_hash, manifest_hash
                   FROM stage_results ORDER BY stage_index LIMIT 6"""
            )
        ] == prefix
    resumed_inspect = run_cli(
        "inspect-run",
        run_id,
        "--state",
        str(resume_state),
        "--format",
        "json",
    )
    observed_output.extend(resumed_inspect.stdout.encode())
    observed_output.extend(resumed_inspect.stderr.encode())
    _assert_inspection(
        parse_cli_json(resumed_inspect),
        run_id=run_id,
        status="planned_not_published",
        stages=9,
        reused=6,
    )
    assert json.loads((resumed_output / "publication-plan.json").read_bytes())[
        "remote_writes_attempted"
    ] == 0
    assert canary.encode() not in observed_output
    assert canary.encode() not in _all_regular_file_bytes(tmp_path)


def test_packaged_cli_changed_a_prime_dual_inspect_gap_acceptance(
    approved_fixture: Path, run_cli, tmp_path: Path
) -> None:
    state = tmp_path / "changed-a-prime.db"
    interrupted = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "original-output"),
        "--fail-after",
        "generator",
    )
    assert parse_cli_error(interrupted)["error"]["code"] == (
        ErrorCode.PIPELINE_INTERRUPTED.value
    )
    with _connect(state) as connection:
        original_run = str(connection.execute("SELECT run_id FROM runs").fetchone()[0])

    changed_fixture = _fixture_with_goal(
        approved_fixture,
        tmp_path / "changed-a-prime.json",
        "A-prime canonical local-only review plan.",
    )
    changed = run_cli(
        "dry-run",
        "--fixture",
        str(changed_fixture),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "changed-output"),
    )
    changed_payload = parse_cli_json(changed)
    _assert_summary(changed_payload, reused=0)
    changed_run = str(changed_payload["run_id"])
    assert changed_run != original_run

    original_inspect = parse_cli_json(
        run_cli(
            "inspect-run",
            original_run,
            "--state",
            str(state),
            "--format",
            "json",
        )
    )
    changed_inspect = parse_cli_json(
        run_cli(
            "inspect-run",
            changed_run,
            "--state",
            str(state),
            "--format",
            "json",
        )
    )
    _assert_inspection(
        original_inspect,
        run_id=original_run,
        status="interrupted",
        stages=6,
        reused=0,
    )
    _assert_inspection(
        changed_inspect,
        run_id=changed_run,
        status="planned_not_published",
        stages=9,
        reused=0,
    )
    assert original_inspect["run"]["fixture_hash"] != changed_inspect["run"][
        "fixture_hash"
    ]
    assert json.loads((tmp_path / "changed-output" / "publication-plan.json").read_bytes())[
        "remote_writes_attempted"
    ] == 0


def test_packaged_cli_a_b_a_exact_resume_gap_acceptance(
    approved_fixture: Path, run_cli, tmp_path: Path
) -> None:
    state = tmp_path / "a-b-a.db"
    interrupted_a = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "a-first"),
        "--fail-after",
        "generator",
    )
    assert parse_cli_error(interrupted_a)["error"]["code"] == (
        ErrorCode.PIPELINE_INTERRUPTED.value
    )
    with _connect(state) as connection:
        a_run = str(connection.execute("SELECT run_id FROM runs").fetchone()[0])

    fixture_b = _fixture_with_goal(
        approved_fixture,
        tmp_path / "fixture-b.json",
        "B canonical local-only review plan.",
    )
    interrupted_b = run_cli(
        "dry-run",
        "--fixture",
        str(fixture_b),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "b-first"),
        "--fail-after",
        "reader",
    )
    assert parse_cli_error(interrupted_b)["error"]["code"] == (
        ErrorCode.PIPELINE_INTERRUPTED.value
    )
    with _connect(state) as connection:
        b_run = str(
            connection.execute(
                "SELECT run_id FROM runs WHERE run_id != ?", (a_run,)
            ).fetchone()[0]
        )
        b_rows_before = _run_facts(connection, b_run)
        b_manifests_before = _manifest_bytes_for_run(connection, state, b_run)

    resumed_a = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(state),
        "--output",
        str(tmp_path / "a-resumed"),
    )
    resumed_payload = parse_cli_json(resumed_a)
    _assert_summary(resumed_payload, reused=6)
    assert resumed_payload["run_id"] == a_run
    with _connect(state) as connection:
        assert _run_facts(connection, b_run) == b_rows_before
        assert _manifest_bytes_for_run(connection, state, b_run) == b_manifests_before

    inspected_a = parse_cli_json(
        run_cli(
            "inspect-run", a_run, "--state", str(state), "--format", "json"
        )
    )
    inspected_b = parse_cli_json(
        run_cli(
            "inspect-run", b_run, "--state", str(state), "--format", "json"
        )
    )
    _assert_inspection(
        inspected_a,
        run_id=a_run,
        status="planned_not_published",
        stages=9,
        reused=6,
    )
    _assert_inspection(
        inspected_b,
        run_id=b_run,
        status="interrupted",
        stages=3,
        reused=0,
    )
    assert json.loads((tmp_path / "a-resumed" / "publication-plan.json").read_bytes())[
        "remote_writes_attempted"
    ] == 0


def test_gap_finding_node_definitions_exist() -> None:
    assert tuple(FINDING_NODES) == EXPECTED_FINDINGS
    assert tuple(ROOT_GAP_NODES) == ("1", "2", "3", "4")
    definitions: dict[Path, set[str]] = {}
    for nodes in (*FINDING_NODES.values(), *ROOT_GAP_NODES.values()):
        assert nodes
        for node_id in nodes:
            module_name, separator, function_name = node_id.partition("::")
            assert separator == "::"
            module = PROJECT_ROOT / module_name
            if module not in definitions:
                tree = ast.parse(module.read_bytes(), filename=str(module))
                definitions[module] = {
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
            assert function_name in definitions[module], node_id


def test_production_capability_surface_remains_local_only() -> None:
    imported_modules: set[str] = set()
    forbidden_calls: list[str] = []
    for module in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(module.read_bytes(), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_DIRECT_CALLS:
                    forbidden_calls.append(f"{module.relative_to(PROJECT_ROOT)}:{node.func.id}")
                elif (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr in FORBIDDEN_ATTRIBUTE_CALLS
                ):
                    forbidden_calls.append(
                        f"{module.relative_to(PROJECT_ROOT)}:{node.func.attr}"
                    )

    forbidden_imports = {
        module
        for module in imported_modules
        if any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_PRODUCTION_MODULES
        )
    }
    assert forbidden_imports == set()
    assert forbidden_calls == []

    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["dependencies"] == ["pydantic==2.13.4"]
    assert metadata["build-system"]["requires"] == ["uv_build==0.11.29"]
    assert metadata["project"]["scripts"] == {"skillscout": "skillscout.cli:main"}
    assert set(metadata["dependency-groups"]["dev"]) == {
        "pytest==9.1.1",
        "ruff==0.15.21",
    }
