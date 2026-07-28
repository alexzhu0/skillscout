"""Static and mutation audit for the workflow-dispatch-only Gate B4 canary."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "gate-b4-canary.yml"
CHECKOUT_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"
APP_TOKEN_SHA = "bcd2ba49218906704ab6c1aa796996da409d3eb1"
SETUP_UV_SHA = "c771a70e6277c0a99b617c7a806ffedaca235ff9"
ACTION_AUDIT_SHA256 = "f33b1b47c20db6f728522a0e176687c78c19a1d748783f2376d6e28bb67209bb"


def _source() -> str:
    assert WORKFLOW.is_file(), "the controlled Gate B4 canary workflow is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def _assert_trigger_and_authority(text: str) -> None:
    assert re.search(r"^on:\n  workflow_dispatch:\s*$", text, re.MULTILINE)
    assert "schedule:" not in text
    assert "push:" not in text
    assert "pull_request:" not in text
    assert "inputs:" not in text
    assert re.search(r"^permissions:\n  contents: read$", text, re.MULTILINE)
    assert text.count("environment: skillscout-catalog-publish") == 1
    assert re.search(r"^    permissions:\n      contents: read$", text, re.MULTILINE)
    assert "administration:" not in text
    assert "actions/cache" not in text
    assert "upload-artifact" not in text
    assert "download-artifact" not in text


def _assert_ordering(text: str) -> None:
    checkout = text.index(f"actions/checkout@{CHECKOUT_SHA}")
    preflight = text.index("gate_b4_canary.py preflight")
    token = text.index(f"actions/create-github-app-token@{APP_TOKEN_SHA}")
    run = text.index("gate_b4_canary.py run")
    assert checkout < preflight < token < run
    assert text.count("gate_b4_canary.py preflight") == 1
    assert text.count("gate_b4_canary.py run") == 1
    pretoken = text[:token]
    assert "SKILLSCOUT_CANARY_APP_TOKEN" not in pretoken
    assert "steps.app-token.outputs.token" not in pretoken
    assert "SKILLSCOUT_GITHUB_APP_PRIVATE_KEY" not in pretoken
    assert "SKILLSCOUT_CANARY_APP_TOKEN: ${{ steps.app-token.outputs.token }}" in text
    assert (
        "SKILLSCOUT_CANARY_ACTUAL_INSTALLATION_ID: ${{ steps.app-token.outputs.installation-id }}"
    ) in text


def test_workflow_is_manual_protected_minimal_and_dependency_locked() -> None:
    text = _source()
    _assert_trigger_and_authority(text)
    _assert_ordering(text)
    assert f"# action-audit-sha256: {ACTION_AUDIT_SHA256}" in text
    actions = re.findall(r"uses:\s*([^@\s]+)@([^\s#]+)", text)
    assert actions == [
        ("actions/checkout", CHECKOUT_SHA),
        ("astral-sh/setup-uv", SETUP_UV_SHA),
        ("actions/create-github-app-token", APP_TOKEN_SHA),
    ]
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for _, sha in actions)
    assert text.count("persist-credentials: false") == 1
    assert "version: 0.11.29" in text
    assert "enable-cache: false" in text
    assert text.count("uv run --locked python tools/gate_b4_canary.py") == 2
    assert "permission-contents: write" in text
    assert "permission-pull-requests: write" in text
    assert "permission-administration" not in text
    assert "owner: ${{ vars.SKILLSCOUT_CANARY_CATALOG_OWNER }}" in text
    assert "repositories: ${{ vars.SKILLSCOUT_CANARY_CATALOG_REPOSITORY }}" in text


def test_preflight_has_no_secret_projection_and_shell_blocks_are_fixed() -> None:
    text = _source()
    token = text.index(f"actions/create-github-app-token@{APP_TOKEN_SHA}")
    pretoken = text[:token]
    assert "${{ secrets." not in pretoken
    assert "env:" in pretoken
    for block in re.findall(r"run:\s*\|\n((?:\s{8,}.*\n?)*)", text):
        assert "${{" not in block
        assert "set -euo pipefail" in block
    assert "github.event.inputs" not in text
    assert "inputs." not in text
    assert "env |" not in text
    assert "printenv" not in text
    assert "set -x" not in text


def test_failure_evidence_is_printed_and_summarized_before_nonzero_exit() -> None:
    text = _source()
    run_step = text[text.index("gate_b4_canary.py run"):]
    assert "| tee" not in run_step
    assert "set +e" in run_step
    assert 'status="$?"' in run_step
    assert 'cat "$evidence_file"' in run_step
    assert '>> "$GITHUB_STEP_SUMMARY"' in run_step
    assert 'exit "$status"' in run_step
    run_index = run_step.index("gate_b4_canary.py run")
    print_index = run_step.index('cat "$evidence_file"')
    summary_index = run_step.index('>> "$GITHUB_STEP_SUMMARY"')
    exit_index = run_step.index('exit "$status"')
    assert run_index < print_index < summary_index < exit_index


@pytest.mark.parametrize(
    ("needle", "replacement", "audit"),
    [
        (
            "on:\n  workflow_dispatch:",
            "on:\n  push:\n  workflow_dispatch:",
            _assert_trigger_and_authority,
        ),
        (
            "permissions:\n  contents: read",
            "permissions:\n  contents: write",
            _assert_trigger_and_authority,
        ),
        (
            "gate_b4_canary.py preflight",
            "gate_b4_canary.py omitted",
            _assert_ordering,
        ),
        (
            "gate_b4_canary.py preflight",
            "${{ secrets.SKILLSCOUT_GITHUB_APP_PRIVATE_KEY }} gate_b4_canary.py preflight",
            _assert_ordering,
        ),
    ],
)
def test_workflow_audit_rejects_security_mutations(
    needle: str,
    replacement: str,
    audit: Callable[[str], None],
) -> None:
    text = _source()
    assert needle in text
    with pytest.raises((AssertionError, ValueError)):
        audit(text.replace(needle, replacement, 1))
