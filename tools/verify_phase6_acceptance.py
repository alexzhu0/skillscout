#!/usr/bin/env python3
"""Independent Phase 6 hard-gate registry; live facts start explicitly absent."""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
from dataclasses import dataclass
from tempfile import TemporaryDirectory
from typing import Sequence


SUCCESS = "phase6 hard-gate registry valid"
OFFLINE_SUCCESS = "phase6 offline authorization prerequisite valid"
INCOMPLETE = "phase6 acceptance incomplete"
INVALID = "phase6 acceptance registry invalid"
REPOSITORY_SUCCESS = "phase6 repository contract valid"
_MAX_REPOSITORY_FILE_BYTES = 2_000_000
_PHASE = Path(".planning/phases/06-adversarial-mvp-acceptance")
_PHASE_PLAN_COUNT = 18
_PHASE_TASK_COUNT = 47
_PHASE_REGISTRY_SURFACE_COUNT = 85
_PHASE_REGISTRY_UNIQUE_SURFACE_COUNT = 85
_VERSIONED_FACT_REGISTRY_SURFACES = frozenset(
    {
        "acceptance_benchmark_lock/v1",
        "acceptance_benchmark_lock/v2",
        "acceptance_live_authority/v1",
        "acceptance_live_authority/v2",
    }
)
_WORKFLOWS = (
    Path(".github/workflows/discover.yml"),
    Path(".github/workflows/publish-candidate.yml"),
    Path(".github/workflows/gate-b4-canary.yml"),
    Path(".github/workflows/phase6-acceptance.yml"),
)
_REQUIRED_REPOSITORY_FILES = (
    Path("pyproject.toml"),
    Path("uv.lock"),
    Path("AGENTS.md"),
    Path("RELEASE.md"),
    Path(".planning/PROJECT.md"),
    Path(".planning/ROADMAP.md"),
    Path(".planning/REQUIREMENTS.md"),
    Path(".planning/STATE.md"),
    _PHASE / "06-AI-SPEC.md",
    _PHASE / "06-BENCHMARK-MANIFEST.json",
    _PHASE / "06-CONTEXT.md",
    _PHASE / "06-PATTERNS.md",
    _PHASE / "06-RESEARCH.md",
    _PHASE / "06-VALIDATION.md",
    Path("src/skillscout/domain/acceptance.py"),
    Path("src/skillscout/application/acceptance.py"),
    Path("src/skillscout/application/pipeline.py"),
    Path("src/skillscout/application/phase3.py"),
    Path("src/skillscout/adapters/operations_state.py"),
    Path("src/skillscout/adapters/openai_extract.py"),
    Path("src/skillscout/adapters/openai_generate.py"),
    Path("src/skillscout/adapters/openai_review.py"),
    Path("src/skillscout/adapters/semantic_provider.py"),
    Path("src/skillscout/adapters/state_branch.py"),
    Path("src/skillscout/bootstrap.py"),
    Path("src/skillscout/cli.py"),
    Path("tools/verify_phase6_acceptance.py"),
    Path("tools/verify_phase6_source_execution.py"),
    Path("tools/verify_phase6_validation_map.py"),
    *_WORKFLOWS,
    *(
        _PHASE / f"06-{index:02d}-PLAN.md"
        for index in range(1, _PHASE_PLAN_COUNT + 1)
    ),
)

PLAN_06_06_STATE_COMMIT = "37f8dcbf74c85f2471670373fd03f71d9f155bae"
PLAN_06_06_STATE_ROOT = "sha256:b4167cffc31969854260d4acd58b804f4823a4d25d078ef3b5dc88445b75c2e5"
PLAN_06_06_WORKFLOW_SHA256 = (
    "sha256:7eca32de7c0468d18c180ebecf567d7239412e54c2776e43621930b894570f63"
)
PLAN_06_06_SOURCE_COMMIT = "a3c41cf8501bec435a646f140f52acedf1c5f312"
PLAN_06_06_HOSTED_RUN_ID = 30_519_607_061
PLAN_06_06_RUN_ATTEMPT = 1
PLAN_06_06_ACCEPTANCE_RUN_ID = "phase6-offline-30519607061-1"
PLAN_06_06_HOSTED_DIGEST = "sha256:cc6f4802e74ec07450958224235b8f0baa8748e74f64b5a1f67c3484998b500a"
PLAN_06_06_OFFLINE_DIGEST = (
    "sha256:f37b81258d966c6683fb16d50aee537e35851dfd41f232490f89d7b0dc228e0b"
)
PLAN_06_06_THREE_STORE_PROJECTION = (
    "sha256:c69f87f4fc213daa36faed3151f0ffe7f99da243363e197db8e59cfb2640b69c"
)


@dataclass(frozen=True)
class HardGate:
    identifier: str
    blocking: bool = True


HARD_GATE_REGISTRY = tuple(
    HardGate(identifier)
    for identifier in (
        "benchmark_human_lock",
        "five_fixed_sha_repositories",
        "controlled_scenario_coverage",
        "hosted_kernel_isolation",
        "synthetic_secret_absence",
        "no_untrusted_execution",
        "closed_provider_policy",
        "license_custody",
        "provenance_custody",
        "evidence_integrity",
        "identical_replay_zero_effects",
        "changed_source_same_draft_update",
        "fresh_gate_b4_binding",
        "permission_causal_denials",
        "open_value_draft",
        "exact_head_human_review",
        "probe_cleanup_attestation",
        "report_rebuild",
        "all_44_requirements",
    )
)


class OfflineStateError(RuntimeError):
    """Fail-closed local verification error with no state or credential detail."""


class AcceptanceError(RuntimeError):
    """Fail-closed independent repository verification error."""


@dataclass(frozen=True)
class RepositoryVerification:
    """Sanitized structural result; never grants hosted or live authority."""

    status: str
    structural_valid: bool
    acceptance_complete: bool
    plan_count: int
    task_count: int
    requirement_count: int
    source_execution_step_count: int
    missing_live_artifacts: tuple[str, ...]


@dataclass(frozen=True)
class OfflineStateVerification:
    """Sanitized exact identities admitted by the Plan 06-07 checkpoint."""

    state_commit_sha: str
    state_root_digest: str
    acceptance_run_id: str
    workflow_sha256: str
    source_commit_sha: str
    hosted_run_id: int
    run_attempt: int
    isolation_mechanism: str
    hosted_capability_digest: str
    offline_run_digest: str
    three_store_projection_digest: str


def registry_is_exact() -> bool:
    identifiers = tuple(gate.identifier for gate in HARD_GATE_REGISTRY)
    return (
        len(identifiers) == 19
        and len(set(identifiers)) == len(identifiers)
        and all(gate.blocking is True for gate in HARD_GATE_REGISTRY)
        and identifiers[0] == "benchmark_human_lock"
        and identifiers[-1] == "all_44_requirements"
    )


def _reject() -> None:
    raise AcceptanceError("repository_contract_rejected")


def _trusted_repository_root(repository_root: Path) -> Path:
    if not isinstance(repository_root, Path):
        _reject()
    lexical = repository_root.absolute()
    try:
        if lexical.is_symlink() or not lexical.is_dir():
            _reject()
        current = Path(lexical.anchor)
        for component in lexical.parts[1:]:
            current /= component
            if current.is_symlink():
                _reject()
        root = lexical.resolve(strict=True)
        if root != lexical:
            _reject()
        git_directory = root / ".git"
        if git_directory.is_symlink() or not git_directory.is_dir():
            _reject()
        result = subprocess.run(
            ("git", "rev-parse", "--show-toplevel"),
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        if result.returncode != 0 or result.stdout.decode("utf-8").strip() != str(root):
            _reject()
        return root
    except AcceptanceError:
        raise
    except (OSError, UnicodeError, subprocess.SubprocessError):
        _reject()


def _repository_bytes(root: Path, relative: Path) -> bytes:
    if relative.is_absolute() or ".." in relative.parts:
        _reject()
    path = root
    try:
        for component in relative.parts:
            path /= component
            if path.is_symlink():
                _reject()
        if not path.is_file():
            _reject()
        resolved = path.resolve(strict=True)
        if resolved != root / relative or not resolved.is_relative_to(root):
            _reject()
        payload = resolved.read_bytes()
        if not 0 < len(payload) <= _MAX_REPOSITORY_FILE_BYTES:
            _reject()
        return payload
    except AcceptanceError:
        raise
    except OSError:
        _reject()


def _repository_text(root: Path, relative: Path) -> str:
    try:
        return _repository_bytes(root, relative).decode("utf-8", errors="strict")
    except UnicodeError:
        _reject()


def _assignment_string_tuple(source: str, name: str) -> tuple[str, ...]:
    try:
        tree = ast.parse(source)
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
                continue
            value = ast.literal_eval(node.value)
            if type(value) is not tuple or not all(type(item) is str for item in value):
                _reject()
            return value
    except (SyntaxError, ValueError):
        _reject()
    _reject()


def _mapping_literal_keys(source: str, name: str) -> tuple[str, ...]:
    try:
        tree = ast.parse(source)
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
                continue
            if not isinstance(node.value, ast.Dict):
                _reject()
            keys = tuple(ast.literal_eval(key) for key in node.value.keys)
            if not all(type(item) is str for item in keys):
                _reject()
            return keys
    except (SyntaxError, ValueError):
        _reject()
    _reject()


def _verify_plan_validation_contract(root: Path) -> tuple[int, int]:
    try:
        helper = _repository_text(root, Path("tools/verify_phase6_validation_map.py"))
        helper_tree = ast.parse(helper)
        helper_functions = {
            node.name for node in helper_tree.body if isinstance(node, ast.FunctionDef)
        }
        if (
            not {
                "parse_plans",
                "parse_rows",
                "parse_inverse",
                "parse_registry",
                "verify_checkpoint_topology",
                "verify_dependency_topology",
                "verify",
            }
            <= helper_functions
        ):
            _reject()

        plans: dict[str, tuple[int, tuple[str, ...]]] = {}
        tasks: dict[str, tuple[str, str | None]] = {}
        for index in range(1, _PHASE_PLAN_COUNT + 1):
            source = _repository_text(root, _PHASE / f"06-{index:02d}-PLAN.md")
            number = re.search(r'^plan:\s*"(\d{2})"$', source, re.MULTILINE)
            wave = re.search(r"^wave:\s*(\d+)$", source, re.MULTILINE)
            requirements = re.search(
                r"^requirements:\s*\[([^\]]*)\]",
                source,
                re.MULTILINE,
            )
            if number is None or wave is None or requirements is None:
                _reject()
            plan_id = f"06-{number.group(1)}"
            requirement_ids = tuple(
                item.strip() for item in requirements.group(1).split(",") if item.strip()
            )
            if (
                plan_id != f"06-{index:02d}"
                or plan_id in plans
                or not requirement_ids
                or not set(requirement_ids) <= {"TEST-01", "TEST-02", "TEST-03", "TEST-04"}
            ):
                _reject()
            plans[plan_id] = (int(wave.group(1)), requirement_ids)
            blocks = re.findall(
                r'<task\s+type="([^"]+)"[^>]*>(.*?)</task>',
                source,
                re.DOTALL,
            )
            if not blocks:
                _reject()
            for task_type, block in blocks:
                name = re.search(r"<name>Task (06-\d{2}-\d{2}):", block)
                command = re.search(r"<automated>(.*?)</automated>", block, re.DOTALL)
                if name is None or name.group(1) in tasks:
                    _reject()
                task_id = name.group(1)
                if not task_id.startswith(plan_id + "-"):
                    _reject()
                tasks[task_id] = (
                    task_type,
                    (
                        html.unescape(" ".join(command.group(1).split()))
                        if command is not None
                        else None
                    ),
                )

        fresh_lock_plan = _repository_text(root, _PHASE / "06-16-PLAN.md")
        required_environment_setup = (
            "Create environment `phase6-fresh-nomination`; require no reviewer or "
            "custom deployment rule, restrict deployment branches to the protected "
            "default branch `main` only, and store "
            "`SKILLSCOUT_FRESH_NOMINATION_STATE_GITHUB_TOKEN` only as this "
            "environment's secret (not as a repository-level fallback).",
            "Create environment `phase6-human-benchmark-lock`; require reviewer "
            "`alexzhu0`, restrict deployment branches to the protected default branch "
            "`main` only, leave Prevent self-review disabled because the sole required "
            "reviewer may approve a run they initiated, enable no custom deployment "
            "protection rule or signature/key scheme, and store "
            "`SKILLSCOUT_BENCHMARK_LOCK_STATE_GITHUB_TOKEN` only as this "
            "environment's secret (not as a repository-level fallback).",
        )
        if any(requirement not in fresh_lock_plan for requirement in required_environment_setup):
            _reject()

        validation = _repository_text(root, _PHASE / "06-VALIDATION.md")
        manual_section = validation.split("## Manual-Only Verifications", 1)[1].split(
            "## Validation Sign-Off", 1
        )[0]
        benchmark_lock_row = next(
            (
                line
                for line in manual_section.splitlines()
                if line.startswith("| Lock the five-repository benchmark |")
            ),
            None,
        )
        required_benchmark_lock_manual_contract = (
            "configure `phase6-human-benchmark-lock` with required reviewer "
            "`alexzhu0`, selected deployment branch `main` only",
            "Prevent self-review disabled for the sole reviewer",
            "no custom protection rule",
            "`SKILLSCOUT_BENCHMARK_LOCK_STATE_GITHUB_TOKEN` only as an "
            "environment secret with no repository-level fallback",
        )
        if benchmark_lock_row is None or any(
            requirement not in benchmark_lock_row
            for requirement in required_benchmark_lock_manual_contract
        ):
            _reject()

        row_section = validation.split("## Per-Task Verification Map", 1)[1].split(
            "## Requirement Inverse Coverage", 1
        )[0]
        rows: dict[str, tuple[str, int, tuple[str, ...], str]] = {}
        for line in row_section.splitlines():
            if not re.match(r"^\| 06-\d{2}-\d{2} \|", line):
                continue
            cells = tuple(cell.strip().strip("`") for cell in line.strip().strip("|").split("|"))
            if len(cells) != 7 or cells[0] in rows:
                _reject()
            task_id, plan_id, row_wave, requirement_text, _feedback, command, _status = cells
            requirement_ids = tuple(
                re.findall(
                    r"TEST-\d{2}",
                    requirement_text.replace(
                        "TEST-01..04",
                        "TEST-01 TEST-02 TEST-03 TEST-04",
                    ),
                )
            )
            if (
                task_id not in tasks
                or plan_id not in plans
                or not requirement_ids
                or not set(requirement_ids) <= set(plans[plan_id][1])
            ):
                _reject()
            rows[task_id] = (
                plan_id,
                int(row_wave),
                requirement_ids,
                html.unescape(command),
            )
        if (
            len(plans) != _PHASE_PLAN_COUNT
            or len(tasks) != _PHASE_TASK_COUNT
            or set(rows) != set(tasks)
        ):
            _reject()
        for task_id, (plan_id, row_wave, _requirements, command) in rows.items():
            task_command = tasks[task_id][1]
            if (
                row_wave != plans[plan_id][0]
                or not command
                or (task_command is not None and task_command != command)
            ):
                _reject()

        inverse_section = validation.split("## Requirement Inverse Coverage", 1)[1].split(
            "## Exact Cross-Plan Ownership Registry", 1
        )[0]
        inverse: dict[str, set[str]] = {}
        for line in inverse_section.splitlines():
            match = re.match(r"^\| (TEST-\d{2}) \| (.+) \|$", line)
            if match is not None:
                inverse[match.group(1)] = set(re.findall(r"06-\d{2}-\d{2}", match.group(2)))
        if set(inverse) != {"TEST-01", "TEST-02", "TEST-03", "TEST-04"}:
            _reject()
        for requirement, task_ids in inverse.items():
            actual = {
                task_id
                for task_id, (_plan, _wave, requirements, _command) in rows.items()
                if requirement in requirements
            }
            if task_ids != actual:
                _reject()

        registry_section = validation.split(
            "## Exact Cross-Plan Ownership Registry",
            1,
        )[1].split("### Wave 0 File Ownership", 1)[0]
        registry_surfaces = tuple(
            cells[0].strip("`")
            for line in registry_section.splitlines()
            if line.startswith("| `")
            for cells in (tuple(cell.strip() for cell in line.strip().strip("|").split("|")),)
            if len(cells) == 4
        )
        registry_counts = {
            surface: registry_surfaces.count(surface) for surface in set(registry_surfaces)
        }
        if (
            len(registry_surfaces) != _PHASE_REGISTRY_SURFACE_COUNT
            or len(registry_counts) != _PHASE_REGISTRY_UNIQUE_SURFACE_COUNT
            or any(count != 1 for count in registry_counts.values())
            or not _VERSIONED_FACT_REGISTRY_SURFACES <= set(registry_surfaces)
            or "SemanticStage" not in registry_surfaces
            or "verify_phase6_source_execution.py" not in registry_surfaces
        ):
            _reject()
        wave_zero_section = validation.split("### Wave 0 File Ownership", 1)[1].split(
            "\n---\n",
            1,
        )[0]
        wave_zero_files = tuple(
            cells[0].strip("`")
            for line in wave_zero_section.splitlines()
            if line.startswith("| `")
            for cells in (tuple(cell.strip() for cell in line.strip().strip("|").split("|")),)
            if len(cells) == 2
        )
        if len(wave_zero_files) != 13 or len(set(wave_zero_files)) != 13:
            _reject()
        return len(plans), len(tasks)
    except AcceptanceError:
        raise
    except (IndexError, SyntaxError, UnicodeError, ValueError):
        _reject()


def _verify_requirement_contract(root: Path) -> tuple[str, ...]:
    source = _repository_text(root, Path(".planning/REQUIREMENTS.md"))
    identifiers = tuple(
        re.findall(
            r"^- \[[ x]\] \*\*([A-Z]+-\d{2})\*\*:",
            source.split("## v2 Requirements", 1)[0],
            re.MULTILINE,
        )
    )
    if len(identifiers) != 44 or len(set(identifiers)) != 44:
        _reject()
    return identifiers


def _verify_source_and_workflow_contract(root: Path) -> int:
    try:
        helper = _repository_text(root, Path("tools/verify_phase6_source_execution.py"))
        helper_tree = ast.parse(helper)
        helper_functions = {
            node.name for node in helper_tree.body if isinstance(node, ast.FunctionDef)
        }
        if "verify_source_execution" not in helper_functions:
            _reject()
        sources = tuple(_repository_text(root, path) for path in _WORKFLOWS)
        if any(
            re.search(r"uses:\s*[^@\s]+@(?![0-9a-f]{40}(?:\s|#|$))", source) for source in sources
        ):
            _reject()
        forbidden = (
            r"\bcurl\b",
            r"\bwget\b",
            r"\bgit\s+clone\b",
            r"\bpip(?:3)?\s+install\b",
            r"\buv\s+add\b",
            r"\bnpx\b",
        )
        if any(re.search(pattern, source) for source in sources for pattern in forbidden):
            _reject()
        required_by_workflow = (
            ("discovery:", "skillscout.cli discover", "publish-discovered"),
            ("admit:", "verify-publication-admission", "publish-candidate"),
            ("controlled_canary:", "tools/gate_b4_canary.py"),
            ("offline_adversarial", "run-acceptance"),
        )
        for source, required in zip(sources, required_by_workflow):
            if any(marker not in source for marker in required):
                _reject()
        authoritative_steps = sum(
            1
            for source in sources
            for line in source.splitlines()
            if re.search(
                r"(?:python(?:\s+-I)?\s+-m\s+skillscout|"
                r"\bskillscout\s+[a-z-]+|tools/[A-Za-z0-9_./-]+\.py)",
                line,
            )
        )
        if authoritative_steps <= 0:
            _reject()
        return authoritative_steps
    except AcceptanceError:
        raise
    except (SyntaxError, UnicodeError):
        _reject()


def _verify_manifest_and_model_contract(root: Path) -> None:
    from skillscout.domain.acceptance import LockedBenchmarkManifestV1
    from skillscout.domain.canonical import canonical_json_bytes

    manifest_bytes = _repository_bytes(root, _PHASE / "06-BENCHMARK-MANIFEST.json")
    try:
        manifest = LockedBenchmarkManifestV1.model_validate_json(manifest_bytes, strict=True)
    except Exception:
        _reject()
    if (
        len(manifest.entries) != 5
        or manifest.prior_manifest_digest is not None
        or manifest.lock_attestation.manifest_digest != manifest.manifest_digest
        or manifest.lock_attestation.nomination_set_digest != manifest.nomination_set_digest
        or manifest_bytes
        not in {
            canonical_json_bytes(manifest),
            canonical_json_bytes(manifest) + b"\n",
        }
    ):
        _reject()

    domain = _repository_text(root, Path("src/skillscout/domain/acceptance.py"))
    operations = _repository_text(root, Path("src/skillscout/adapters/operations_state.py"))
    gates = _assignment_string_tuple(domain, "HARD_ACCEPTANCE_GATES")
    if gates != tuple(gate.identifier for gate in HARD_GATE_REGISTRY):
        _reject()
    required_model_markers = (
        "replay_semantic_effect_count: Literal[0]",
        "replay_publication_effect_count: Literal[0]",
        "semantic_request_count: Literal[0]",
        "duplicate_workflow_spec_count: Literal[0]",
        "duplicate_skill_count: Literal[0]",
        "duplicate_fact_count: Literal[0]",
        "remote_effect_count: Literal[0]",
        "publication_effect_count: Literal[0]",
        "branch_create_count: Literal[0]",
        "pull_request_create_count: Literal[0]",
        "new_pull_request_count: Literal[0]",
        "new_reviewer_request_count: Literal[0]",
    )
    if any(marker not in domain for marker in required_model_markers):
        _reject()
    human_review_source = domain.split("class HumanSkillReviewAttestationV1", 1)[1].split(
        "\nclass ", 1
    )[0]
    if "pr_head_sha: _Sha" not in human_review_source:
        _reject()
    kinds = _mapping_literal_keys(operations, "_ACCEPTANCE_FACT_MODEL_VALUES")
    expected_kinds = (
        "acceptance_replay",
        "acceptance_replay_evidence",
        "acceptance_changed_source",
        "acceptance_publication_replay_completion",
        "acceptance_changed_source_draft_update_completion",
        "acceptance_gate_b4",
        "acceptance_human_review",
        "acceptance_gate",
        "acceptance_report_root",
    )
    if len(kinds) != len(set(kinds)) or any(kinds.count(kind) != 1 for kind in expected_kinds):
        _reject()


def _verify_current_and_historical_state(root: Path) -> None:
    state = _repository_text(root, Path(".planning/STATE.md"))
    summary = _repository_text(root, _PHASE / "06-15-SUMMARY.md")
    actual = tuple(
        hashlib.sha256(_repository_bytes(root, workflow)).hexdigest() for workflow in _WORKFLOWS
    )
    current_match = re.search(
        r"The current authoritative workflow SHA-256 values are discover "
        r"`([0-9a-f]{64})`, publish `([0-9a-f]{64})`, canary "
        r"`([0-9a-f]{64})`, and Phase 6 acceptance `([0-9a-f]{64})`\.",
        state,
    )
    if (
        current_match is None
        or current_match.groups()[:3] != actual[:3]
        or current_match.group(4) != PLAN_06_06_WORKFLOW_SHA256.removeprefix("sha256:")
        or actual[3] == current_match.group(4)
        or "Gate B4 evidence remains historical" not in state
        or "grant no current authority" not in state
        or "prior exact-source/workflow authorization" not in state
        or "workflow-byte correction" not in state
        or PLAN_06_06_STATE_COMMIT not in state
        or PLAN_06_06_STATE_ROOT not in state
        or PLAN_06_06_WORKFLOW_SHA256.removeprefix("sha256:") not in state
        or any(digest not in summary for digest in actual[:3])
    ):
        _reject()


def verify_repository(repository_root: Path) -> RepositoryVerification:
    """Independently verify the trusted local repository without live authority."""

    try:
        root = _trusted_repository_root(repository_root)
        for relative in _REQUIRED_REPOSITORY_FILES:
            _repository_bytes(root, relative)
        plan_count, task_count = _verify_plan_validation_contract(root)
        requirements = _verify_requirement_contract(root)
        source_steps = _verify_source_and_workflow_contract(root)
        _verify_manifest_and_model_contract(root)
        _verify_current_and_historical_state(root)
        live_artifacts = (
            _PHASE / "06-ACCEPTANCE-REPORT.md",
            _PHASE / "06-RELEASE-REQUIREMENTS.json",
        )
        present = tuple((root / path).exists() for path in live_artifacts)
        if any(present) and not all(present):
            _reject()
        if all(present):
            report = _repository_text(root, live_artifacts[0])
            release = json.loads(_repository_bytes(root, live_artifacts[1]))
            if (
                type(release) is not dict
                or type(release.get("requirements")) is not list
                or set(release["requirements"]) != set(requirements)
                or set(release.get("inverse_requirement_map", ())) != set(requirements)
                or "release recommendation" not in report.casefold()
            ):
                _reject()
        missing = tuple(path.name for path, exists in zip(live_artifacts, present) if not exists)
        return RepositoryVerification(
            status=(
                "repository_contract_valid_acceptance_complete_unverified"
                if not missing
                else "repository_contract_valid_acceptance_incomplete"
            ),
            structural_valid=True,
            acceptance_complete=False,
            plan_count=plan_count,
            task_count=task_count,
            requirement_count=len(requirements),
            source_execution_step_count=source_steps,
            missing_live_artifacts=missing,
        )
    except AcceptanceError:
        raise
    except Exception:
        _reject()


def _git(repository_root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=repository_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise OfflineStateError("local_git_unavailable") from None
    if result.returncode != 0:
        raise OfflineStateError("local_git_object_missing")
    return result.stdout


def _local_state_remote(repository_root: Path, expected_state_commit: str) -> object:
    from skillscout.adapters.state_branch import (
        STATE_REF,
        StateCommitObservation,
        StateRefObservation,
        StateTreeEntry,
    )

    class LocalStateRemote:
        def get_state_ref(self) -> StateRefObservation:
            observed = (
                _git(
                    repository_root,
                    "rev-parse",
                    "--verify",
                    f"{expected_state_commit}^{{commit}}",
                )
                .decode("ascii")
                .strip()
            )
            if observed != expected_state_commit:
                raise OfflineStateError("canonical_state_object_mismatch")
            return StateRefObservation(STATE_REF, observed)

        def get_commit(self, sha: str) -> StateCommitObservation:
            raw = _git(repository_root, "cat-file", "-p", sha)
            try:
                header, message = raw.split(b"\n\n", 1)
                lines = header.splitlines()
                tree_sha = next(
                    line.removeprefix(b"tree ").decode("ascii")
                    for line in lines
                    if line.startswith(b"tree ")
                )
                parents = tuple(
                    line.removeprefix(b"parent ").decode("ascii")
                    for line in lines
                    if line.startswith(b"parent ")
                )
                decoded_message = message.decode("utf-8").removesuffix("\n")
            except (StopIteration, UnicodeDecodeError, ValueError):
                raise OfflineStateError("canonical_state_commit_invalid") from None
            return StateCommitObservation(
                sha=sha,
                tree_sha=tree_sha,
                parents=parents,
                message=decoded_message,
            )

        def get_tree(self, tree_sha: str) -> tuple[StateTreeEntry, ...]:
            raw = _git(
                repository_root,
                "ls-tree",
                "-r",
                "-l",
                "-z",
                tree_sha,
            )
            entries: list[StateTreeEntry] = []
            try:
                for item in raw.split(b"\0"):
                    if not item:
                        continue
                    metadata, path = item.split(b"\t", 1)
                    mode, object_type, sha, size = metadata.split()
                    if object_type != b"blob":
                        raise ValueError
                    entries.append(
                        StateTreeEntry(
                            path=path.decode("utf-8"),
                            sha=sha.decode("ascii"),
                            mode=mode.decode("ascii"),
                            size=int(size),
                        )
                    )
            except (UnicodeDecodeError, ValueError):
                raise OfflineStateError("canonical_state_tree_invalid") from None
            return tuple(entries)

        def get_blob(self, sha: str) -> bytes:
            return _git(repository_root, "cat-file", "blob", sha)

    return LocalStateRemote()


def verify_offline_state(
    repository_root: Path,
    *,
    expected_state_commit: str = PLAN_06_06_STATE_COMMIT,
) -> OfflineStateVerification:
    """Rebuild and compare the exact Plan 06-06 canonical facts without network."""

    from skillscout.adapters.operations_state import (
        OperationsStateStore,
        _parse_bundle_exports,
        restore_three_store_bundle,
    )
    from skillscout.adapters.state_branch import StateBranchStore
    from skillscout.domain.acceptance import (
        HostedIsolationCapabilityV1,
        OfflineAdversarialRunV1,
    )

    if not isinstance(repository_root, Path) or expected_state_commit != PLAN_06_06_STATE_COMMIT:
        raise OfflineStateError("canonical_state_identity_invalid")
    root = repository_root.resolve()
    if _git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip() != str(root):
        raise OfflineStateError("canonical_state_identity_invalid")

    try:
        observation = StateBranchStore(_local_state_remote(root, expected_state_commit)).restore()
        if (
            observation.status != "verified"
            or observation.observed_head != expected_state_commit
            or observation.bundle is None
            or observation.bundle.root.root_digest != PLAN_06_06_STATE_ROOT
        ):
            raise OfflineStateError("canonical_state_restore_mismatch")
        bundle = observation.bundle
        _, operations_export, _, original_projection = _parse_bundle_exports(bundle)
        if (
            operations_export.projection.acceptance_hosted_isolation_capability_digests
            != (PLAN_06_06_HOSTED_DIGEST,)
            or operations_export.projection.acceptance_offline_adversarial_run_digests
            != (PLAN_06_06_OFFLINE_DIGEST,)
            or original_projection.projection_digest != PLAN_06_06_THREE_STORE_PROJECTION
        ):
            raise OfflineStateError("canonical_acceptance_projection_mismatch")

        acceptance_facts = tuple(
            fact for fact in operations_export.facts if fact.kind.startswith("acceptance_")
        )
        if tuple(fact.kind for fact in acceptance_facts) != (
            "acceptance_hosted_isolation_capability",
            "acceptance_offline_adversarial_run",
        ):
            raise OfflineStateError("canonical_acceptance_fact_set_mismatch")
        run_ids = set()
        for fact in acceptance_facts:
            payload = json.loads(fact.payload_json)
            columns = payload.get("columns")
            if type(columns) is not dict:
                raise OfflineStateError("canonical_acceptance_fact_invalid")
            run_ids.add(columns.get("acceptance_run_id"))
        if run_ids != {PLAN_06_06_ACCEPTANCE_RUN_ID}:
            raise OfflineStateError("canonical_acceptance_run_mismatch")

        with TemporaryDirectory(prefix="skillscout-phase6-offline-") as temporary:
            # macOS exposes /tmp and /var as symlink aliases.  The state owners
            # intentionally reject symlinked ancestors, so use the canonical
            # private path to the already-created temporary directory.
            temporary_root = Path(temporary).resolve()
            pipeline_path = temporary_root / "pipeline.sqlite3"
            operations_path = temporary_root / "operations.sqlite3"
            publication_path = temporary_root / "publication.sqlite3"
            rebuilt_projection = restore_three_store_bundle(
                bundle,
                pipeline_path=pipeline_path,
                operations_path=operations_path,
                publication_path=publication_path,
            )
            if rebuilt_projection != original_projection:
                raise OfflineStateError("canonical_three_store_rebuild_mismatch")
            store = OperationsStateStore(operations_path)
            try:
                fresh_export = store.export_owned_state()
                snapshot = store.acceptance_snapshot(PLAN_06_06_ACCEPTANCE_RUN_ID)
            finally:
                store.close()
            if fresh_export != operations_export or tuple(
                record.kind for record in snapshot.facts
            ) != (
                "acceptance_hosted_isolation_capability",
                "acceptance_offline_adversarial_run",
            ):
                raise OfflineStateError("canonical_acceptance_rebuild_mismatch")

        hosted_record, offline_record = snapshot.facts
        hosted = hosted_record.fact
        offline = offline_record.fact
        if (
            type(hosted) is not HostedIsolationCapabilityV1
            or type(offline) is not OfflineAdversarialRunV1
            or hosted_record.fact_digest != PLAN_06_06_HOSTED_DIGEST
            or offline_record.fact_digest != PLAN_06_06_OFFLINE_DIGEST
            or hosted.capability_digest != offline.hosted_capability_digest
            or hosted.workflow_sha256 != offline.workflow_sha256
            or hosted.source_commit_sha != offline.source_commit_sha
            or hosted.hosted_run_id != offline.hosted_run_id
            or hosted.run_attempt != offline.run_attempt
            or hosted.isolation_mechanism != offline.isolation_mechanism
            or hosted.workflow_sha256 != PLAN_06_06_WORKFLOW_SHA256
            or hosted.source_commit_sha != PLAN_06_06_SOURCE_COMMIT
            or hosted.hosted_run_id != PLAN_06_06_HOSTED_RUN_ID
            or hosted.run_attempt != PLAN_06_06_RUN_ATTEMPT
        ):
            raise OfflineStateError("canonical_hosted_offline_binding_mismatch")
        return OfflineStateVerification(
            state_commit_sha=expected_state_commit,
            state_root_digest=bundle.root.root_digest,
            acceptance_run_id=PLAN_06_06_ACCEPTANCE_RUN_ID,
            workflow_sha256=hosted.workflow_sha256,
            source_commit_sha=hosted.source_commit_sha,
            hosted_run_id=hosted.hosted_run_id,
            run_attempt=hosted.run_attempt,
            isolation_mechanism=hosted.isolation_mechanism,
            hosted_capability_digest=hosted_record.fact_digest,
            offline_run_digest=offline_record.fact_digest,
            three_store_projection_digest=rebuilt_projection.projection_digest,
        )
    except OfflineStateError:
        raise
    except Exception:
        raise OfflineStateError("canonical_offline_verification_failed") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--registry-only", action="store_true")
    parser.add_argument("--offline-only", action="store_true")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        print(INVALID, file=sys.stderr)
        return 1
    if not registry_is_exact() or (args.registry_only and args.offline_only):
        print(INVALID, file=sys.stderr)
        return 1
    if args.registry_only:
        print(SUCCESS)
        return 0
    if args.offline_only:
        try:
            report = verify_offline_state(Path.cwd())
        except OfflineStateError:
            print(INCOMPLETE, file=sys.stderr)
            return 1
        print(OFFLINE_SUCCESS)
        print(
            json.dumps(
                report.__dict__,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    try:
        repository = verify_repository(Path.cwd())
    except AcceptanceError:
        print(INVALID, file=sys.stderr)
        return 1
    if not repository.structural_valid:
        print(INVALID, file=sys.stderr)
        return 1
    # A structurally valid repository still has no authority to fabricate
    # absent hosted/live/human facts into PASS.
    print(INCOMPLETE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
