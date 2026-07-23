"""Cross-root acceptance evidence for the closed Phase 1 gaps."""

from __future__ import annotations

import ast
import json
import os
import re
import sqlite3
import subprocess
import sys
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

LEGACY_GAP_FINDING_NODES: dict[str, tuple[str, ...]] = {
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

PRIOR_REVIEW_FINDING_NODES: dict[str, tuple[str, ...]] = {
    "CR-01": (
        "tests/test_state_integrity.py::"
        "test_post_commit_backup_cleanup_failure_returns_success_and_reopen_observes_mutation",
    ),
    "CR-02": (
        "tests/test_state_integrity.py::"
        "test_resume_event_tamper_is_rejected_by_every_bound_trust_path",
    ),
    "CR-03": (
        "tests/test_cli_security.py::"
        "test_argparse_failures_are_byte_exact_non_echoing_and_non_durable",
    ),
    "WR-01": (
        "tests/test_pipeline_resume.py::"
        "test_fail_once_unexpected_exception_resumes_failed_stage_without_prefix_replay",
    ),
    "WR-02": (
        "tests/test_phase1_evidence_verifier.py::"
        "test_verify_reruns_closed_registry_and_rejects_mismatched_output",
    ),
    "WR-03": (
        "tests/test_state_integrity.py::"
        "test_state_manifest_namespace_collision_is_rejected_before_creation",
    ),
    "WR-04": (
        "tests/test_state_integrity.py::"
        "test_existing_state_requires_private_permissions_before_deserialize",
        "tests/test_state_integrity.py::"
        "test_existing_manifest_requires_private_single_owner_file_before_decode",
    ),
}

CLOSED_REVIEW_FINDING_NODES: dict[str, tuple[str, ...]] = {
    "CR-01": (
        "tests/test_pipeline_resume.py::"
        "test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay",
    ),
    "WR-01": (
        "tests/test_phase1_evidence_verifier.py::"
        "test_stale_json_fixture_bytes_are_rejected_before_command_credit",
    ),
}

CURRENT_REVIEW_FINDING_NODES: dict[str, tuple[str, ...]] = {
    "IN-01": (
        "tests/test_phase1_gap_closure.py::"
        "test_known_issue_in01_dead_local_state_store_alias_remains_as_documented",
    ),
    "IN-02": (
        "tests/test_phase1_gap_closure.py::"
        "test_known_issue_in02_lock_acquisition_duplication_remains_as_documented",
    ),
}

ROOT_GAP_NODES: dict[str, tuple[str, ...]] = {
    "1": (
        "tests/test_phase1_gap_closure.py::test_production_capability_surface_remains_local_only",
        *LEGACY_GAP_FINDING_NODES["CR-01"],
    ),
    "2": (
        *LEGACY_GAP_FINDING_NODES["CR-03"],
        *LEGACY_GAP_FINDING_NODES["CR-04"],
        *LEGACY_GAP_FINDING_NODES["CR-07"],
        *LEGACY_GAP_FINDING_NODES["CR-08"],
        *LEGACY_GAP_FINDING_NODES["WR-01"],
    ),
    "3": (
        *LEGACY_GAP_FINDING_NODES["CR-05"],
        *LEGACY_GAP_FINDING_NODES["CR-06"],
        *LEGACY_GAP_FINDING_NODES["WR-02"],
    ),
    "4": (
        *LEGACY_GAP_FINDING_NODES["CR-02"],
        *LEGACY_GAP_FINDING_NODES["WR-03"],
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
FORBIDDEN_QUALIFIED_CALLS = frozenset({"os.popen", "os.system"})
IMPORT_CARVE_OUTS: dict[str, frozenset[str]] = {
    "adapters/github.py": frozenset({"httpx"}),
    "adapters/openai_extract.py": frozenset({"openai"}),
    "adapters/openai_generate.py": frozenset({"openai"}),
}


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _qualified_name(node: ast.expr, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value, aliases)
        return f"{parent}.{node.attr}" if parent else None
    return None


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


class _LockHelperNormalizer(ast.NodeTransformer):
    """Collapse the documented incidental differences between the two lock helpers."""

    def visit_Expr(self, node: ast.Expr) -> ast.stmt | None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        return None

    def visit_Return(self, node: ast.Return) -> ast.Expr:
        return ast.Expr(value=ast.Constant(value="<released>"))

    def visit_Assign(self, node: ast.Assign) -> ast.stmt:
        if any(
            isinstance(target, ast.Attribute) and target.attr == "_lock_descriptor"
            for target in node.targets
        ):
            return ast.Expr(value=ast.Constant(value="<released>"))
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            if node.attr == "_state_parent":
                return ast.Name(id="anchor", ctx=node.ctx)
            if node.attr == "_state_name":
                return ast.Name(id="target_name", ctx=node.ctx)
        return node


def _normalized_lock_helper_dump(module: Path, function_name: str) -> str:
    tree = ast.parse(module.read_bytes(), filename=str(module))
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    assert len(matches) == 1
    normalized = _LockHelperNormalizer().visit(matches[0])
    assert isinstance(normalized, ast.FunctionDef)
    return ast.dump(ast.Module(body=normalized.body, type_ignores=[]))


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
    assert tuple(LEGACY_GAP_FINDING_NODES) == EXPECTED_FINDINGS
    assert tuple(ROOT_GAP_NODES) == ("1", "2", "3", "4")
    definitions: dict[Path, set[str]] = {}
    for nodes in (*LEGACY_GAP_FINDING_NODES.values(), *ROOT_GAP_NODES.values()):
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


def test_prior_review_finding_node_definitions_exist() -> None:
    assert tuple(PRIOR_REVIEW_FINDING_NODES) == (
        "CR-01",
        "CR-02",
        "CR-03",
        "WR-01",
        "WR-02",
        "WR-03",
        "WR-04",
    )
    definitions: dict[Path, set[str]] = {}
    for nodes in PRIOR_REVIEW_FINDING_NODES.values():
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


def test_closed_review_finding_node_definitions_exist() -> None:
    assert tuple(CLOSED_REVIEW_FINDING_NODES) == ("CR-01", "WR-01")
    definitions: dict[Path, set[str]] = {}
    for nodes in CLOSED_REVIEW_FINDING_NODES.values():
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


def test_current_review_finding_node_definitions_exist() -> None:
    assert tuple(CURRENT_REVIEW_FINDING_NODES) == ("IN-01", "IN-02")
    definitions: dict[Path, set[str]] = {}
    for nodes in CURRENT_REVIEW_FINDING_NODES.values():
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


def test_known_issue_in01_dead_local_state_store_alias_remains_as_documented() -> None:
    ports_module = PROJECT_ROOT / "src" / "skillscout" / "application" / "ports.py"
    ports_tree = ast.parse(ports_module.read_bytes(), filename=str(ports_module))
    alias_definitions = [
        node
        for node in ports_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "LocalStateStore"
            for target in node.targets
        )
        and isinstance(node.value, ast.Name)
        and node.value.id == "StateStore"
    ]
    assert len(alias_definitions) == 1
    references: list[str] = []
    for root in (SOURCE_ROOT, PROJECT_ROOT / "tests", PROJECT_ROOT / "tools"):
        for module in sorted(root.rglob("*.py")):
            tree = ast.parse(module.read_bytes(), filename=str(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == "LocalStateStore":
                    references.append(f"{module}:{node.lineno}")
                elif isinstance(node, ast.Attribute) and node.attr == "LocalStateStore":
                    references.append(f"{module}:{node.lineno}")
    assert references == [f"{ports_module}:{alias_definitions[0].lineno}"]


def test_known_issue_in02_lock_acquisition_duplication_remains_as_documented() -> None:
    state_dump = _normalized_lock_helper_dump(
        SOURCE_ROOT / "adapters" / "state.py", "_acquire_lock"
    )
    pipeline_dump = _normalized_lock_helper_dump(
        SOURCE_ROOT / "application" / "pipeline.py", "_acquire_publication_lock"
    )
    assert state_dump == pipeline_dump


def test_current_review_composed_packaged_smoke(tmp_path: Path) -> None:
    node_ids = [
        str(PROJECT_ROOT / module_name) + "::" + function_name
        for nodes in CURRENT_REVIEW_FINDING_NODES.values()
        for node_id in nodes
        for module_name, separator, function_name in (node_id.partition("::"),)
        if separator == "::"
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(PROJECT_ROOT),
            "--basetemp",
            str(tmp_path / "nested-pytest"),
            *node_ids,
        ),
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    counts = re.findall(rb"(?<!\d)(\d+) passed\b", completed.stdout + completed.stderr)
    assert len(counts) == 1 and int(counts[0]) >= len(node_ids)
    assert b"DO_NOT_DISCLOSE" not in completed.stdout + completed.stderr


def test_production_capability_surface_remains_local_only() -> None:
    module_imports: dict[str, set[str]] = {}
    forbidden_calls: list[str] = []
    for module in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = module.relative_to(SOURCE_ROOT).as_posix()
        imported = module_imports.setdefault(relative, set())
        tree = ast.parse(module.read_bytes(), filename=str(module))
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
                    aliases[alias.asname or alias.name.split(".")[0]] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                for alias in node.names:
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
            elif isinstance(node, ast.Call):
                call_name = _qualified_name(node.func, aliases)
                if call_name in FORBIDDEN_DIRECT_CALLS | FORBIDDEN_QUALIFIED_CALLS:
                    forbidden_calls.append(
                        f"{module.relative_to(PROJECT_ROOT)}:{call_name}"
                    )

    forbidden_imports = {
        f"{relative}:{imported_module}"
        for relative, imported in module_imports.items()
        for imported_module in imported
        if any(
            imported_module == forbidden or imported_module.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_PRODUCTION_MODULES
            - IMPORT_CARVE_OUTS.get(relative, frozenset())
        )
    }
    assert forbidden_imports == set()
    assert forbidden_calls == []

    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["dependencies"] == [
        "httpx==0.28.1",
        "openai==2.46.0",
        "pydantic==2.13.4",
        "skills-ref==0.1.1",
    ]
    assert metadata["build-system"]["requires"] == ["uv_build==0.11.29"]
    assert metadata["project"]["scripts"] == {"skillscout": "skillscout.cli:main"}
    assert set(metadata["dependency-groups"]["dev"]) == {
        "pytest==9.1.1",
        "ruff==0.15.21",
    }
