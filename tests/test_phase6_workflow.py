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
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
LOCAL_UV = ".tools/uv-0.11.29/bin/uv"
EVIDENCE_FIELDS = (
    "schema_version",
    "non_authoritative",
    "workflow_sha256",
    "source_commit_sha",
    "hosted_run_id",
    "run_attempt",
    "runner_image",
    "kernel_identity",
    "docker_server_version",
    "docker_image_id",
    "isolation_mechanism",
    "control_command_digest",
    "direct_probe_command_digest",
    "child_probe_command_digest",
    "control_outcome",
    "direct_network_outcome",
    "child_network_outcome",
    "credential_count",
    "state_write_capability",
    "synthetic_scan_manifest_digest",
    "synthetic_canary_hit_count",
    "artifact_retention_days",
)


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
    jobs = source.partition("\njobs:\n")[2]
    assert jobs
    assert set(re.findall(r"^  ([a-z][a-z0-9_-]*):\n", jobs, re.MULTILINE)) == {
        "isolation_probe",
        "nominate",
        "offline_adversarial",
        "live_benchmark",
        "changed_source",
        "fresh_gate_b4",
        "value_publication",
        "human_attestation",
        "cleanup_attestation",
        "rebuild_report",
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
    assert job.count("docker run --network none") == 3
    assert "retention-days: 1" in job
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in job
    assert "non_authoritative" in job
    assert "direct_network_outcome" in job
    assert "child_network_outcome" in job
    assert "control_outcome" in job
    assert "synthetic_canary_hit_count" in job
    assert (
        len(
            re.findall(
                rf"^\s+{re.escape(LOCAL_UV)} run --locked",
                job,
                re.MULTILINE,
            )
        )
        == 4
    )
    evidence_match = re.search(
        r"^          evidence = \{\n(?P<body>.*?)^          \}\n",
        job,
        re.MULTILINE | re.DOTALL,
    )
    assert evidence_match is not None
    assert (
        tuple(
            re.findall(
                r'^              "([a-z][a-z0-9_]*)":',
                evidence_match.group("body"),
                re.MULTILINE,
            )
        )
        == EVIDENCE_FIELDS
    )
    assert (
        job.index(f"actions/checkout@{CHECKOUT_SHA}")
        < job.index(f"astral-sh/setup-uv@{SETUP_UV_SHA}")
        < job.index(f"{LOCAL_UV} run --locked")
    )


def test_phase6_isolation_probe_workflow_is_required() -> None:
    _source(required=True)


def test_isolation_probe_workflow_is_secretless_least_privilege_and_non_cancelling() -> None:
    source = _source(required=False)
    _assert_isolation_workflow(source)
    isolation = _job(source, "isolation_probe")
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
    assert all(token not in isolation for token in forbidden)
    assert "${{ secrets." not in isolation


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


def test_phase6_actions_and_jobs_have_closed_authority_zones() -> None:
    source = _source(required=False)
    options = re.search(
        r"^        options:\n(?P<body>(?:          - [a-z0-9-]+\n)+)",
        source,
        re.MULTILINE,
    )
    assert options is not None
    assert tuple(
        re.findall(r"^          - ([a-z0-9-]+)$", options.group("body"), re.MULTILINE)
    ) == (
        "isolation-probe",
        "nominate",
        "offline-adversarial",
        "run-benchmark",
        "run-replay",
        "run-changed-source",
        "gate-b4-and-publish",
        "record-human-review",
        "record-probe-cleanup",
        "rebuild-report",
    )

    nomination = _job(source, "nominate")
    offline = _job(source, "offline_adversarial")
    live = _job(source, "live_benchmark")
    changed = _job(source, "changed_source")
    fresh_gate = _job(source, "fresh_gate_b4")
    publication = _job(source, "value_publication")
    human = _job(source, "human_attestation")
    cleanup = _job(source, "cleanup_attestation")
    rebuild = _job(source, "rebuild_report")

    assert "contents: write" in nomination
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" in nomination
    assert "DEEPSEEK" not in nomination
    assert "SKILLSCOUT_CATALOG" not in nomination
    assert "${{ secrets." not in nomination

    assert "contents: read" in offline
    assert "contents: write" not in offline
    assert "${{ secrets." not in offline
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" not in offline

    for semantic_job in (live, changed):
        assert "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}" in semantic_job
        assert "SKILLSCOUT_STATE_GITHUB_TOKEN" in semantic_job
        assert "SKILLSCOUT_CATALOG" not in semantic_job
        assert "SKILLSCOUT_GITHUB_APP" not in semantic_job
        assert "--state-commit-sha" in semantic_job
        assert "--state-root-digest" in semantic_job

    assert "${{ secrets." not in fresh_gate
    assert "SKILLSCOUT_CATALOG" not in fresh_gate
    assert re.search(r"^    needs: fresh_gate_b4$", publication, re.MULTILINE)
    assert "environment: skillscout-catalog-publish" in publication
    assert "SKILLSCOUT_CATALOG_FULL_NAME: alexzhu0/skillscout-catalog-test" in publication
    assert publication.index("run-acceptance") < publication.index(
        "actions/create-github-app-token"
    )
    assert "permission-contents: write" in publication
    assert "permission-pull-requests: write" in publication

    non_publication = source.replace(publication, "", 1)
    assert "actions/create-github-app-token" not in non_publication
    assert "SKILLSCOUT_GITHUB_APP_PRIVATE_KEY" not in non_publication
    assert "alexzhu0/skillscout-catalog-test" not in non_publication

    for attestation in (human, cleanup):
        assert "SKILLSCOUT_STATE_GITHUB_TOKEN" in attestation
        assert "DEEPSEEK" not in attestation
        assert "SKILLSCOUT_CATALOG" not in attestation
        assert "record-acceptance-attestation" in attestation
    assert "--kind human-review" in human
    assert "--kind probe-cleanup" in cleanup

    assert "contents: read" in rebuild
    assert "contents: write" not in rebuild
    assert "${{ secrets." not in rebuild
    assert "rebuild-acceptance" in rebuild

    upload_blocks = re.findall(
        r"uses: actions/upload-artifact@[0-9a-f]{40}\n(?P<body>(?:\s{8,}.*\n?)*)",
        source,
    )
    assert upload_blocks
    assert all("if-no-files-found: error" in block for block in upload_blocks)
    assert all("retention-days: 1" in block for block in upload_blocks)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ("docker run --network none", "docker run"),
        ("permissions:\n  contents: read", "permissions:\n  contents: write"),
        ("persist-credentials: false", "persist-credentials: true"),
        ("retention-days: 1", "retention-days: 30"),
        ("cancel-in-progress: false", "cancel-in-progress: true"),
        (f"actions/checkout@{CHECKOUT_SHA}", "actions/checkout@main"),
        (
            f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}",
            "actions/upload-artifact@main",
        ),
        (f"{LOCAL_UV} run --locked", "uv run"),
        ("control_command_digest", "command_digest"),
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
