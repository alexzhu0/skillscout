"""Mutation tests for the independent Phase 5 acceptance inspector."""

from __future__ import annotations

import ast
import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
INSPECTOR = PROJECT_ROOT / "tools/verify_phase5_acceptance.py"
PHASE = Path(".planning/phases/05-automated-discovery-operations")
PHASE5_GATE_B4_WORKFLOW_DIGESTS = {
    Path(".github/workflows/discover.yml"): (
        "8157cb686b9bf18bfa800811b1fe1529ed9a15ec371fe36ec1708233052b7cfd"
    ),
    Path(".github/workflows/publish-candidate.yml"): (
        "96ce9f39db49ce647a88b83ec4db3cb0135e5cf51c1eb2f11961cfd243b23cf0"
    ),
    Path(".github/workflows/gate-b4-canary.yml"): (
        "9c59cd9822eecec913f82d24c7880a443ba9416795b8996c6201f33c4df5805d"
    ),
}
REPOSITORY_LOCAL_TOOLCHAIN_STEP = """\
      - name: Verify the repository-local locked toolchain
        run: |
          set -euo pipefail
          mkdir -p .tools/uv-0.11.29/bin
          install -m 0755 "$(command -v uv)" .tools/uv-0.11.29/bin/uv
          test -x .tools/uv-0.11.29/bin/uv
          test "$(.tools/uv-0.11.29/bin/uv --version)" = "uv 0.11.29"
          .tools/uv-0.11.29/bin/uv sync --locked --no-install-project
"""
PUBLISH_LOCAL_TOOLCHAIN_STEPS = (
    """\
      - name: Install the exact locked uv tool
        uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9
        with:
          version: 0.11.29
          enable-cache: false
"""
    + REPOSITORY_LOCAL_TOOLCHAIN_STEP
)


def _replace_exact(repository: Path, relative: Path, old: str, new: str, *, count: int) -> None:
    path = repository / relative
    source = path.read_text(encoding="utf-8")
    assert source.count(old) == count
    path.write_text(source.replace(old, new), encoding="utf-8")


def _restore_phase5_gate_b4_workflows(repository: Path) -> None:
    discover = Path(".github/workflows/discover.yml")
    publish = Path(".github/workflows/publish-candidate.yml")
    canary = Path(".github/workflows/gate-b4-canary.yml")
    _replace_exact(
        repository,
        discover,
        REPOSITORY_LOCAL_TOOLCHAIN_STEP,
        "",
        count=2,
    )
    _replace_exact(
        repository,
        discover,
        ".tools/uv-0.11.29/bin/uv run --locked",
        "uv run --locked",
        count=3,
    )
    _replace_exact(
        repository,
        publish,
        "          ref: ${{ github.sha }}\n",
        "",
        count=2,
    )
    _replace_exact(
        repository,
        publish,
        PUBLISH_LOCAL_TOOLCHAIN_STEPS,
        "",
        count=2,
    )
    _replace_exact(
        repository,
        publish,
        '.tools/uv-0.11.29/bin/uv run --locked python - "$protected_admission"',
        'python - "$protected_admission"',
        count=1,
    )
    _replace_exact(
        repository,
        canary,
        REPOSITORY_LOCAL_TOOLCHAIN_STEP,
        "",
        count=1,
    )
    _replace_exact(
        repository,
        canary,
        ".tools/uv-0.11.29/bin/uv run --locked",
        "uv run --locked",
        count=2,
    )
    observed = {
        relative: hashlib.sha256((repository / relative).read_bytes()).hexdigest()
        for relative in PHASE5_GATE_B4_WORKFLOW_DIGESTS
    }
    assert observed == PHASE5_GATE_B4_WORKFLOW_DIGESTS


@pytest.fixture
def acceptance_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    for directory in ("src", "config", ".github"):
        shutil.copytree(PROJECT_ROOT / directory, repository / directory)
    _restore_phase5_gate_b4_workflows(repository)
    phase = repository / PHASE
    phase.mkdir(parents=True)
    for name in (
        "05-01-PLAN.md",
        "05-09-PLAN.md",
        "05-09-SUMMARY.md",
        "05-10-PLAN.md",
        "05-HOSTED-GATE-B4-EVIDENCE.json",
        "05-HOSTED-GATE-B4-APPROVAL.json",
    ):
        shutil.copy2(PROJECT_ROOT / PHASE / name, phase / name)
    return repository


def _run(repository: Path, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(PROJECT_ROOT / ".tools/uv-0.11.29/bin/uv"),
            "run",
            "--project",
            str(PROJECT_ROOT),
            "--locked",
            "python",
            str(INSPECTOR),
            "--repository-root",
            str(repository),
        ],
        cwd=cwd or PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={"UV_CACHE_DIR": str(PROJECT_ROOT / ".tools/uv-cache")},
    )


def _replace(repository: Path, relative: str, old: str, new: str) -> None:
    path = repository / relative
    source = path.read_text(encoding="utf-8")
    assert source.count(old) >= 1
    path.write_text(source.replace(old, new), encoding="utf-8")


def _metadata(root: Path) -> dict[str, tuple[int, int, str]]:
    result: dict[str, tuple[int, int, str]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        stat = path.stat()
        result[str(path.relative_to(root))] = (
            stat.st_mode,
            stat.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    return result


def test_historical_fixture_uses_gate_b4_bound_workflow_bytes(
    acceptance_repository: Path,
) -> None:
    observed = {
        relative: hashlib.sha256((acceptance_repository / relative).read_bytes()).hexdigest()
        for relative in PHASE5_GATE_B4_WORKFLOW_DIGESTS
    }
    assert observed == PHASE5_GATE_B4_WORKFLOW_DIGESTS


def test_complete_tree_passes_read_only_from_external_cwd(
    acceptance_repository: Path, tmp_path: Path
) -> None:
    before = _metadata(acceptance_repository)
    completed = _run(acceptance_repository, cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "phase5 acceptance valid\n"
    assert completed.stderr == ""
    assert _metadata(acceptance_repository) == before


def test_current_tree_fails_closed_until_fresh_gate_b4_evidence_is_recorded() -> None:
    completed = _run(PROJECT_ROOT)
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == "phase5 acceptance invalid\n"


@pytest.mark.parametrize(
    ("relative", "old", "new"),
    [
        (
            "src/skillscout/domain/discovery.py",
            "DISCOVERY_MAX_CANDIDATES: Final = 100",
            "DISCOVERY_MAX_CANDIDATES: Final = 101",
        ),
        (
            "src/skillscout/domain/discovery.py",
            "DISCOVERY_MAX_SEMANTIC_CANDIDATES: Final = 20",
            "DISCOVERY_MAX_SEMANTIC_CANDIDATES: Final = 21",
        ),
        (
            "config/discovery-queries-v1.json",
            "github-repository-search-v1",
            "github-repository-search-v2",
        ),
        (
            "src/skillscout/application/discovery.py",
            "reserve_discovery_candidate",
            "reserve_refundable_candidate",
        ),
        (
            "src/skillscout/application/discovery.py",
            "summary.semantic_reservation_count * 3",
            "summary.semantic_reservation_count * 4",
        ),
        (
            "src/skillscout/application/ports.py",
            '"attempt_started"',
            '"attempt_maybe_started"',
        ),
        (
            "src/skillscout/application/ports.py",
            '"result_decided"',
            '"result_maybe_decided"',
        ),
        (
            "src/skillscout/adapters/semantic_provider.py",
            "SEMANTIC_OUTCOME_UNKNOWN",
            "SEMANTIC_RETRY_UNKNOWN",
        ),
        (
            "src/skillscout/adapters/operations_state.py",
            "def export_owned_state(",
            "def export_unverified_records(",
        ),
        (
            "src/skillscout/adapters/state_branch.py",
            '"force": False',
            '"force": True',
        ),
        (
            "src/skillscout/cli.py",
            "_DISCOVERY_PUBLICATION_STATE",
            "_DISCOVERY_EXTRA_STATE",
        ),
        (
            "src/skillscout/application/discovery.py",
            "class DiscoveryDependencies:",
            "class DiscoveryAndPublicationDependencies:",
        ),
        (
            "src/skillscout/cli.py",
            "read_exact_discovery_state(",
            "trust_discovery_state(",
        ),
        (
            "src/skillscout/cli.py",
            "catalog_token_factory=lambda: os.environ",
            "catalog_token_factory=lambda: handoff",
        ),
        (
            ".github/workflows/discover.yml",
            "schedule:",
            "push:",
        ),
        (
            ".github/workflows/discover.yml",
            "cancel-in-progress: false",
            "cancel-in-progress: true",
        ),
        (
            ".github/workflows/discover.yml",
            "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1",
            "actions/create-github-app-token@main",
        ),
        (
            ".github/workflows/discover.yml",
            "environment: skillscout-catalog-publish",
            "environment: unprotected",
        ),
        (
            ".planning/phases/05-automated-discovery-operations/05-HOSTED-GATE-B4-APPROVAL.json",
            "1ee162ea47cf86b7faec68bfba37b7a9b2af3b25472066312b43c4a5e4414cdd",
            "0" * 64,
        ),
        (
            ".planning/phases/05-automated-discovery-operations/05-HOSTED-GATE-B4-APPROVAL.json",
            "concurrency_evidence_is_not_gate_b4",
            "concurrency_evidence_is_gate_b4",
        ),
    ],
)
def test_requirement_and_prohibition_mutations_fail_closed(
    acceptance_repository: Path, relative: str, old: str, new: str
) -> None:
    _replace(acceptance_repository, relative, old, new)
    completed = _run(acceptance_repository)
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == "phase5 acceptance invalid\n"


def test_hosted_evidence_bytes_and_current_workflows_are_exact(
    acceptance_repository: Path,
) -> None:
    evidence = acceptance_repository / PHASE / "05-HOSTED-GATE-B4-EVIDENCE.json"
    evidence.write_bytes(evidence.read_bytes() + b"\n")
    completed = _run(acceptance_repository)
    assert completed.returncode == 1
    assert completed.stderr == "phase5 acceptance invalid\n"


def test_inspector_has_no_project_network_or_write_authority() -> None:
    source = INSPECTOR.read_text(encoding="utf-8")
    tree = ast.parse(source)
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
        {
            "httpx",
            "openai",
            "pydantic",
            "requests",
            "skillscout",
            "socket",
            "subprocess",
            "urllib",
        }
    )
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_attributes.isdisjoint({"write_text", "write_bytes"})
    assert "open" not in called_names
