"""Wave-0 RED audit for daily/manual two-zone production workflow."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-candidate.yml"
DISCOVER_WORKFLOW = ROOT / ".github" / "workflows" / "discover.yml"
ACTION_REFRESH_AUDIT = (
    ROOT
    / ".planning"
    / "phases"
    / "05-automated-discovery-operations"
    / "05-ACTION-AUDIT-REFRESH.md"
)
ACTION_REFRESH_APPROVAL = (
    ROOT
    / ".planning"
    / "phases"
    / "05-automated-discovery-operations"
    / "05-ACTION-PIN-REFRESH-APPROVAL.json"
)
PUBLISH_WORKFLOW_SHA256 = "224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c"
ACTION_REFRESH_AUDIT_SHA256 = "f33b1b47c20db6f728522a0e176687c78c19a1d748783f2376d6e28bb67209bb"
CHECKOUT_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"
APP_TOKEN_SHA = "bcd2ba49218906704ab6c1aa796996da409d3eb1"
OLD_APP_TOKEN_SHA = "67018539274d69449ef7c8cde82c3ff073ffe3b5"
SETUP_UV_SHA = "c771a70e6277c0a99b617c7a806ffedaca235ff9"


def _workflow() -> str:
    return DISCOVER_WORKFLOW.read_text()


def _job(text: str, name: str) -> str:
    match = re.search(
        rf"^  {name}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9_-]*:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match
    return match.group("body")


def test_action_refresh_approval_is_bound_to_exact_audit_bytes_and_commits() -> None:
    assert hashlib.sha256(ACTION_REFRESH_AUDIT.read_bytes()).hexdigest() == (
        ACTION_REFRESH_AUDIT_SHA256
    )
    assert ACTION_REFRESH_APPROVAL.is_file()
    approval = json.loads(ACTION_REFRESH_APPROVAL.read_text(encoding="utf-8"))
    assert approval == {
        "schema_version": "skillscout.action-pin-refresh-approval.v1",
        "decision": "approve-exact-shas",
        "audit": {
            "locator": ".planning/phases/05-automated-discovery-operations/"
            "05-ACTION-AUDIT-REFRESH.md",
            "sha256": ACTION_REFRESH_AUDIT_SHA256,
        },
        "approved_actions": [
            {
                "repository_id": 197814629,
                "repository_full_name": "actions/checkout",
                "commit_sha": CHECKOUT_SHA,
            },
            {
                "repository_id": 595047935,
                "repository_full_name": "actions/create-github-app-token",
                "commit_sha": APP_TOKEN_SHA,
            },
        ],
        "reviewer": "human requester via execute-phase orchestrator",
        "recorded_at": "2026-07-28T02:51:49Z",
        "human_response": "approve-exact-shas "
        f"audit_digest={ACTION_REFRESH_AUDIT_SHA256} "
        f"actions/checkout@{CHECKOUT_SHA} "
        f"actions/create-github-app-token@{APP_TOKEN_SHA}",
    }


def test_phase4_gate_b4_record_remains_historical_after_live_workflow_change() -> None:
    record = (
        ROOT / ".planning" / "phases" / "04-controlled-draft-pr" / "04-10-SUMMARY.md"
    ).read_text(encoding="utf-8")
    assert PUBLISH_WORKFLOW_SHA256 in record
    assert OLD_APP_TOKEN_SHA in record
    assert hashlib.sha256(PUBLISH_WORKFLOW.read_bytes()).hexdigest() != (PUBLISH_WORKFLOW_SHA256)


def test_discovery_workflow_has_exact_triggers_and_shared_non_cancel_group() -> None:
    text = _workflow()
    assert re.search(
        r'^on:\n(?:.*\n)*?  schedule:\n    - cron: "17 3 \* \* \*"',
        text,
        re.MULTILINE,
    )
    assert re.search(r"^  workflow_dispatch:\s*$", text, re.MULTILINE)
    assert re.search(
        r"^concurrency:\n  group: skillscout-production\n  cancel-in-progress: false",
        text,
        re.MULTILINE,
    )
    assert "@v" not in text
    actions = re.findall(r"^\s*uses:\s*([^@\s]+)@([^\s#]+)", text, re.MULTILINE)
    assert actions == [
        ("actions/checkout", CHECKOUT_SHA),
        ("astral-sh/setup-uv", SETUP_UV_SHA),
        ("actions/checkout", CHECKOUT_SHA),
        ("astral-sh/setup-uv", SETUP_UV_SHA),
        ("actions/create-github-app-token", APP_TOKEN_SHA),
    ]
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for _, ref in actions)
    assert OLD_APP_TOKEN_SHA not in text
    assert re.search(r"^permissions:\n  contents: read$", text, re.MULTILINE)
    discovery = _job(text, "discovery")
    publication = _job(text, "protected_publication")
    assert re.search(r"^    permissions:\n      contents: write$", discovery, re.MULTILINE)
    assert re.search(r"^    permissions:\n      contents: read$", publication, re.MULTILINE)
    setup = (
        f"uses: astral-sh/setup-uv@{SETUP_UV_SHA} # v9.0.0\n"
        "        with:\n"
        "          version: 0.11.29\n"
        "          enable-cache: false"
    )
    assert discovery.count(setup) == 1
    assert publication.count(setup) == 1
    local_uv = ".tools/uv-0.11.29/bin/uv"
    assert discovery.index(setup) < discovery.index(f"{local_uv} run --locked")
    assert publication.index(setup) < publication.index(f"{local_uv} run --locked")
    assert text.count("uv run --locked") == 3
    assert text.count(f"{local_uv} run --locked") == 3
    assert text.count("UV_LINK_MODE: copy") == 2
    for job in (discovery, publication):
        assert "      UV_LINK_MODE: copy" in job
        assert job.index("UV_LINK_MODE: copy") < job.index(f"{local_uv} run --locked")
        assert "ref: ${{ github.sha }}" in job
        assert "persist-credentials: false" in job
        assert f"test -x {local_uv}" in job
        assert f'uv_version_output="$({local_uv} --version)"' in job
        assert (
            'if [[ "$uv_version_output" != "uv 0.11.29" && '
            '! "$uv_version_output" =~ ^uv\\ 0\\.11\\.29\\ \\([^()]+\\)$ ]]; then' in job
        )
        assert f"{local_uv} sync --locked --python" in job
        assert "--no-install-project" not in job
    assert "UV_LINK_MODE: hardlink" not in text
    assert "--link-mode hardlink" not in text


def _assert_separate_authority_zones(text: str) -> None:
    discovery = _job(text, "discovery")
    publication = _job(text, "protected_publication")
    assert "environment:" not in discovery
    assert "SKILLSCOUT_GITHUB_APP_PRIVATE_KEY" not in discovery
    assert "SKILLSCOUT_CATALOG_" not in discovery
    assert "publish-candidate" not in discovery
    assert "skillscout.cli discover" in discovery
    assert "skillscout.cli publish-discovered" not in discovery
    assert "skillscout.cli publish-discovered" in publication
    assert "skillscout.cli discover" not in publication
    assert "environment: skillscout-catalog-publish" in publication
    assert "state = read_exact_discovery_state(" in publication
    assert "admissions = derive_discovery_publication_admissions(" in publication
    admission_index = publication.index("state = read_exact_discovery_state(")
    derivation_index = publication.index("admissions = derive_discovery_publication_admissions(")
    token_index = publication.index("actions/create-github-app-token")
    invocation_index = publication.index("skillscout.cli publish-discovered")
    assert admission_index < derivation_index < token_index < invocation_index
    for forbidden in (
        "build_publication_application",
        "PublicationApplication",
        "GitHubPublishClient",
    ):
        assert forbidden not in discovery
        assert forbidden not in publication[:token_index]
    assert publication.count("actions/create-github-app-token") == 1
    assert publication.count("skillscout.cli publish-discovered") == 1
    assert re.search(
        r"needs:\s*discovery",
        publication,
    )
    assert "persist-credentials: false" in discovery
    assert "persist-credentials: false" in publication


def test_discovery_and_protected_jobs_are_separate_authority_zones() -> None:
    _assert_separate_authority_zones(_workflow())


def _assert_bounded_handoff(text: str) -> None:
    discovery = _job(text, "discovery")
    expected = {
        "discovery_run_id",
        "state_root_digest",
        "state_commit_sha",
        "eligible_candidates_json",
        "eligible_candidates_digest",
    }
    output_block = re.search(
        r"^    outputs:\n(?P<body>.*?)(?=^    [a-z]|\Z)",
        discovery,
        re.MULTILINE | re.DOTALL,
    )
    assert output_block
    actual = set(re.findall(r"^      ([a-z][a-z0-9_]+):", output_block.group("body"), re.MULTILINE))
    assert actual == expected
    assert (
        'set(payload) != {"run_id", "state_root_digest", "state_commit_sha", "eligible_count", "eligible_candidates"}'
        in discovery
    )
    assert "len(candidates) > 60" in discovery
    assert "len(canonical) > 65_536" in discovery
    assert (
        'set(candidate) != {"locator", "authority_digest", "workflow_identity_digest"}' in discovery
    )
    publication = _job(text, "protected_publication")
    for output in expected:
        assert f"${{{{ needs.discovery.outputs.{output} }}}}" in publication
    for block in re.findall(r"run:\s*\|\n((?:\s{8,}.*\n?)*)", text):
        assert "${{" not in block
    assert "actions/cache" not in text
    assert "upload-artifact" not in text
    assert "download-artifact" not in text


def test_workflow_handoff_is_bounded_and_shell_never_interpolates_candidates() -> None:
    _assert_bounded_handoff(_workflow())


@pytest.mark.parametrize(
    ("needle", "replacement", "audit"),
    (
        (
            "skillscout.cli discover",
            "skillscout.cli publish-discovered",
            _assert_separate_authority_zones,
        ),
        (
            "state = read_exact_discovery_state(",
            "state = object(",
            _assert_separate_authority_zones,
        ),
        (
            "eligible_candidates_json:",
            "candidate_payload:",
            _assert_bounded_handoff,
        ),
        (
            "run: |\n          set -euo pipefail",
            'run: |\n          echo "${{ needs.discovery.outputs.eligible_candidates_json }}"\n          set -euo pipefail',
            _assert_bounded_handoff,
        ),
    ),
)
def test_workflow_security_audit_rejects_boundary_mutations(
    needle: str,
    replacement: str,
    audit: Callable[[str], None],
) -> None:
    text = _workflow()
    assert needle in text
    mutated = text.replace(needle, replacement, 1)
    with pytest.raises(AssertionError):
        audit(mutated)


def test_queue_grammar_requires_recorded_hosted_validation_or_fixed_fallback() -> None:
    text = _workflow()
    evidence = (
        ROOT
        / ".planning"
        / "phases"
        / "05-automated-discovery-operations"
        / "05-HOSTED-CONCURRENCY.json"
    )
    if re.search(r"^  queue: max$", text, re.MULTILINE):
        assert evidence.is_file()
        assert '"queue_max_accepted": true' in evidence.read_text()
    else:
        assert "cancel-in-progress: false" in text
        assert "pending run replacement" in text
