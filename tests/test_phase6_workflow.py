"""Static and mutation contracts for the secretless Phase 6 isolation probe."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/phase6-acceptance.yml"
SUMMARY = ROOT / ".planning/phases/06-adversarial-mvp-acceptance/06-02-SUMMARY.md"
CHECKOUT_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"
SETUP_UV_SHA = "c771a70e6277c0a99b617c7a806ffedaca235ff9"
LOCAL_UV = ".tools/uv-0.11.29/bin/uv"


def _source(*, required: bool = True) -> str:
    if not WORKFLOW.is_file():
        if required:
            pytest.fail(
                "phase6-missing-workflow:phase6-acceptance.yml",
                pytrace=False,
            )
        pytest.skip("phase6-isolation-probe-workflow-not-yet-implemented")
    return WORKFLOW.read_text(encoding="utf-8")


def _job(source: str, name: str) -> str:
    match = re.search(
        rf"^  {name}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9_-]*:\n|\Z)",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return match.group("body")


def _assert_isolation_workflow(source: str) -> None:
    assert re.search(r"^on:\n  workflow_dispatch:\n    inputs:", source, re.MULTILINE)
    assert "phase6_action:" in source
    assert "isolation-probe" in source
    assert re.search(
        r"^concurrency:\n  group: skillscout-phase6-acceptance\n"
        r"  cancel-in-progress: false",
        source,
        re.MULTILINE,
    )
    assert re.search(r"^permissions:\n  contents: read$", source, re.MULTILINE)
    assert set(re.findall(r"^  ([a-z][a-z0-9_-]*):\n", source, re.MULTILINE)) == {
        "isolation_probe"
    }
    job = _job(source, "isolation_probe")
    assert "runs-on: ubuntu-24.04" in job
    assert re.search(r"timeout-minutes:\s*[1-9][0-9]?", job)
    assert re.search(r"^    permissions:\n      contents: read$", job, re.MULTILINE)
    assert f"actions/checkout@{CHECKOUT_SHA}" in job
    assert "ref: ${{ github.sha }}" in job
    assert "persist-credentials: false" in job
    assert f"astral-sh/setup-uv@{SETUP_UV_SHA}" in job
    assert "version: 0.11.29" in job
    assert "enable-cache: false" in job
    assert "docker run --network none" in job
    assert "retention-days: 1" in job
    assert "actions/upload-artifact@" in job
    assert "non_authoritative" in job
    assert "direct_network_outcome" in job
    assert "child_network_outcome" in job
    assert "control_outcome" in job
    assert "synthetic_canary_hit_count" in job
    assert job.count(f"{LOCAL_UV} run --locked") >= 2
    assert job.index(f"actions/checkout@{CHECKOUT_SHA}") < job.index(
        f"astral-sh/setup-uv@{SETUP_UV_SHA}"
    ) < job.index(f"{LOCAL_UV} run --locked")


def test_phase6_isolation_probe_workflow_is_required() -> None:
    _source(required=True)


def test_isolation_probe_workflow_is_secretless_least_privilege_and_non_cancelling() -> None:
    source = _source(required=False)
    _assert_isolation_workflow(source)
    forbidden = (
        "DEEPSEEK",
        "OPENAI",
        "SKILLSCOUT_GITHUB_APP",
        "SKILLSCOUT_CATALOG",
        "SKILLSCOUT_STATE_GITHUB_TOKEN",
        "contents: write",
        "pull-requests: write",
        "administration:",
        "merge",
        "approve",
        "mark-ready",
        "cleanup",
    )
    assert all(token not in source for token in forbidden)
    assert "${{ secrets." not in source


def test_isolation_probe_uses_locked_checked_out_source_without_an_execution_selector() -> None:
    source = _source(required=False)
    forbidden = (
        "source-selector",
        "wheel-selector",
        "download-artifact",
        "pip install",
        "uvx ",
        "uv tool ",
        "uv run --with",
        "dist/",
        "working-directory:",
    )
    assert all(token not in source for token in forbidden)
    assert "test -x .tools/uv-0.11.29/bin/uv" in source
    assert ".tools/uv-0.11.29/bin/uv --version" in source


def test_isolation_probe_shell_blocks_do_not_interpolate_repository_or_user_input() -> None:
    source = _source(required=False)
    for block in re.findall(r"run:\s*\|\n((?:\s{8,}.*\n?)*)", source):
        assert "${{ github.event.inputs" not in block
        assert "${{ inputs." not in block
        assert "${{ vars." not in block
        assert "${{ secrets." not in block


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ("docker run --network none", "docker run"),
        ("permissions:\n  contents: read", "permissions:\n  contents: write"),
        ("persist-credentials: false", "persist-credentials: true"),
        ("retention-days: 1", "retention-days: 30"),
        ("cancel-in-progress: false", "cancel-in-progress: true"),
        (f"actions/checkout@{CHECKOUT_SHA}", "actions/checkout@main"),
        (f"{LOCAL_UV} run --locked", "uv run"),
        ("synthetic_canary_hit_count", "secret_value"),
    ),
)
def test_isolation_workflow_mutations_fail_closed(needle: str, replacement: str) -> None:
    source = _source(required=False)
    assert needle in source
    with pytest.raises(AssertionError):
        _assert_isolation_workflow(source.replace(needle, replacement, 1))


def test_hosted_isolation_locator_remains_absent_or_explicitly_non_authoritative() -> None:
    if not SUMMARY.is_file():
        return
    source = SUMMARY.read_text(encoding="utf-8")
    assert "non-authoritative" in source.casefold()
    assert "artifact" in source.casefold()
    assert re.search(r"\b[0-9a-f]{64}\b", source)

