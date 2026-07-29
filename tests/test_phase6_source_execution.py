"""Wave-0 RED contract for the closed four-workflow source-execution verifier."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "tools/verify_phase6_source_execution.py"
WORKFLOW_PATHS = (
    Path(".github/workflows/discover.yml"),
    Path(".github/workflows/publish-candidate.yml"),
    Path(".github/workflows/gate-b4-canary.yml"),
    Path(".github/workflows/phase6-acceptance.yml"),
)
LOCAL_LOCKED = ".tools/uv-0.11.29/bin/uv run --locked"
CHECKOUT = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
SETUP_UV = "astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9"


def _module(*, skip_if_missing: bool = True) -> Any:
    if not VERIFIER_PATH.is_file():
        if skip_if_missing:
            pytest.skip("phase6-source-execution-verifier-not-yet-implemented")
        pytest.fail(
            "phase6-missing-source-execution-verifier:verify_source_execution",
            pytrace=False,
        )
    spec = importlib.util.spec_from_file_location("phase6_source_execution", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    verifier = getattr(module, "verify_source_execution", None)
    if verifier is None:
        if skip_if_missing:
            pytest.skip("phase6-source-execution-verifier-not-yet-implemented")
        pytest.fail(
            "phase6-missing-source-execution-verifier:verify_source_execution",
            pytrace=False,
        )
    return module


def _copy_workflows(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    for relative in WORKFLOW_PATHS:
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return repository


def _replace_first(repository: Path, needle: str, replacement: str) -> None:
    for relative in WORKFLOW_PATHS:
        path = repository / relative
        source = path.read_text(encoding="utf-8")
        if needle in source:
            path.write_text(source.replace(needle, replacement, 1), encoding="utf-8")
            return
    raise AssertionError(f"mutation needle not found: {needle}")


def test_required_phase6_source_execution_verifier_is_missing() -> None:
    _module(skip_if_missing=False)


def test_source_execution_contract_names_exactly_four_authoritative_workflows() -> None:
    assert WORKFLOW_PATHS == (
        Path(".github/workflows/discover.yml"),
        Path(".github/workflows/publish-candidate.yml"),
        Path(".github/workflows/gate-b4-canary.yml"),
        Path(".github/workflows/phase6-acceptance.yml"),
    )
    assert all((ROOT / path).is_file() for path in WORKFLOW_PATHS[:3])


def test_source_execution_verifier_discovers_every_authoritative_entry_point(
    tmp_path: Path,
) -> None:
    module = _module()
    result = module.verify_source_execution(_copy_workflows(tmp_path))
    assert tuple(result.workflow_paths) == tuple(path.as_posix() for path in WORKFLOW_PATHS)
    assert result.authoritative_step_count > 0
    assert result.authoritative_step_count == len(result.authoritative_steps)
    assert all(step.checkout_sha and step.invocation_digest for step in result.authoritative_steps)


@pytest.mark.parametrize(
    ("mutation", "needle", "replacement"),
    (
        ("missing_checkout", CHECKOUT, "name: checkout omitted"),
        ("non_full_sha_checkout", CHECKOUT, "actions/checkout@main"),
        ("non_root_checkout", "persist-credentials: false", "persist-credentials: false\n          path: external"),
        ("missing_setup_uv", SETUP_UV, "name: setup omitted"),
        ("late_setup_uv", SETUP_UV, "astral-sh/setup-uv@main"),
        ("bare_uv", LOCAL_LOCKED, "uv run --locked"),
        ("unlocked_uv", LOCAL_LOCKED, ".tools/uv-0.11.29/bin/uv run"),
        ("bare_python", LOCAL_LOCKED + " python", "python"),
        ("pip", LOCAL_LOCKED, "pip install skillscout && " + LOCAL_LOCKED),
        ("registry", LOCAL_LOCKED, "python -m pip install skillscout && " + LOCAL_LOCKED),
        ("wheel", LOCAL_LOCKED, LOCAL_LOCKED + " dist/skillscout.whl"),
        ("dist", LOCAL_LOCKED, "dist/skillscout " + LOCAL_LOCKED),
        ("uvx", LOCAL_LOCKED, "uvx skillscout"),
        ("uv_tool", LOCAL_LOCKED, "uv tool run skillscout"),
        ("uv_with", LOCAL_LOCKED, "uv run --with skillscout"),
        ("downloaded_artifact", LOCAL_LOCKED, "download-artifact && " + LOCAL_LOCKED),
        ("external_working_directory", LOCAL_LOCKED, "cd /tmp && " + LOCAL_LOCKED),
        ("command_variable", LOCAL_LOCKED, 'runner="' + LOCAL_LOCKED + '"\n          $runner'),
        ("alias", LOCAL_LOCKED, "alias run_skillscout='" + LOCAL_LOCKED + "'\n          run_skillscout"),
        ("function", LOCAL_LOCKED, "run_skillscout() { " + LOCAL_LOCKED + "; }\n          run_skillscout"),
        ("sourced_wrapper", LOCAL_LOCKED, "source ./run-skillscout.sh"),
        ("delegated_wrapper", LOCAL_LOCKED, "bash ./run-skillscout.sh"),
        ("indirect_script", LOCAL_LOCKED, "make run-skillscout"),
        ("unknown_form", LOCAL_LOCKED, "command --opaque-launcher"),
    ),
)
def test_source_execution_mutations_fail_closed(
    tmp_path: Path,
    mutation: str,
    needle: str,
    replacement: str,
) -> None:
    del mutation
    module = _module()
    repository = _copy_workflows(tmp_path)
    _replace_first(repository, needle, replacement)
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


def test_late_checkout_mutation_fails_closed(tmp_path: Path) -> None:
    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / WORKFLOW_PATHS[0]
    source = path.read_text(encoding="utf-8")
    checkout_index = source.index(CHECKOUT)
    invocation_index = source.index(LOCAL_LOCKED)
    assert checkout_index < invocation_index
    source = source.replace(CHECKOUT, "name: checkout delayed", 1)
    source += f"\n      - name: Too-late checkout\n        uses: {CHECKOUT}\n"
    path.write_text(source, encoding="utf-8")
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


def test_empty_authoritative_step_scan_fails_closed(tmp_path: Path) -> None:
    module = _module()
    repository = _copy_workflows(tmp_path)
    for relative in WORKFLOW_PATHS:
        path = repository / relative
        source = path.read_text(encoding="utf-8")
        source = source.replace("skillscout", "bounded_application")
        source = source.replace("tools/", "checked_tools/")
        path.write_text(source, encoding="utf-8")
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)
