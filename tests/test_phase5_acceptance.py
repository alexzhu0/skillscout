"""Mutation tests for the independent Phase 5 acceptance inspector."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
INSPECTOR = PROJECT_ROOT / "tools/verify_phase5_acceptance.py"
PHASE = Path(".planning/phases/05-automated-discovery-operations")


@pytest.fixture
def acceptance_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    for directory in ("src", "config", ".github"):
        shutil.copytree(PROJECT_ROOT / directory, repository / directory)
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
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


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


def test_complete_tree_passes_read_only_from_external_cwd(
    acceptance_repository: Path, tmp_path: Path
) -> None:
    before = _metadata(acceptance_repository)
    completed = _run(acceptance_repository, cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "phase5 acceptance valid\n"
    assert completed.stderr == ""
    assert _metadata(acceptance_repository) == before


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
            '"result_committed"',
            '"result_maybe_committed"',
        ),
        (
            "src/skillscout/adapters/semantic_provider.py",
            "SEMANTIC_OUTCOME_UNKNOWN",
            "SEMANTIC_RETRY_UNKNOWN",
        ),
        (
            "src/skillscout/adapters/operations_state.py",
            "def export_rebuild_records(",
            "def export_unverified_records(",
        ),
        (
            "src/skillscout/adapters/state_branch.py",
            '"force": False',
            '"force": True',
        ),
        (
            "src/skillscout/application/discovery.py",
            "_DISCOVERY_PUBLICATION_STATE",
            "_DISCOVERY_EXTRA_STATE",
        ),
        (
            "src/skillscout/application/discovery.py",
            "_FORBIDDEN_DISCOVERY_DEPENDENCY_TOKENS",
            "_OPTIONAL_DISCOVERY_DEPENDENCY_TOKENS",
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
    assert "skillscout" not in source
    for forbidden in (
        "httpx",
        "openai",
        "pydantic",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "write_text",
        "write_bytes",
        "open(",
    ):
        assert forbidden not in source
