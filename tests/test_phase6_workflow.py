"""Static and mutation contracts for the secretless Phase 6 isolation probe."""

from __future__ import annotations

import json
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
MANAGED_PYTHON_INSTALL = (
    'UV_PYTHON_INSTALL_DIR="${managed_python_root}" UV_MANAGED_PYTHON=1 '
    ".tools/uv-0.11.29/bin/uv python install 3.13.14 "
    '--install-dir "${managed_python_root}" --no-bin'
)
MANAGED_PYTHON_SYNC = (
    'UV_PYTHON_INSTALL_DIR="${managed_python_root}" UV_MANAGED_PYTHON=1 '
    "UV_PYTHON_DOWNLOADS=never .tools/uv-0.11.29/bin/uv sync --locked "
    '--python "${managed_python_executable}" '
    "--managed-python --no-python-downloads"
)
PYTHON_BASE_PREFIX_PREFLIGHT = (
    'repository_root="$(realpath -e -- "${GITHUB_WORKSPACE}")"',
    'test "${repository_root}" = "${GITHUB_WORKSPACE}"',
    'test "${repository_root}" = "$(pwd -P)"',
    'managed_python_root="$(realpath -e -- "${repository_root}/.tools/python")"',
    'test "${managed_python_root}" = "${repository_root}/.tools/python"',
    ".venv/bin/python -I -c 'import sys; print(sys.base_prefix, "
    'end="\\n__PHASE6_BASE_PREFIX_END__")\'',
    "python_base_prefix_sentinel=$'\\n__PHASE6_BASE_PREFIX_END__'",
    '[[ "$python_base_prefix_output" == *"$python_base_prefix_sentinel" ]]',
    'python_base_prefix="${python_base_prefix_output%"$python_base_prefix_sentinel"}"',
    '[[ -n "$python_base_prefix" && "$python_base_prefix" != *$\'\\n\'* '
    '&& "$python_base_prefix" == /* ]]',
    'python_base_prefix="$(realpath -e -- "${python_base_prefix}")"',
    '"${managed_python_root}"/*)',
    'python_executable="$(realpath -e -- .venv/bin/python)"',
    '"${python_base_prefix}"/bin/python*)',
    'test -x "${python_executable}"',
    'test "$(.venv/bin/python -I -c \'import sys; print(sys.implementation.name)\')" = "cpython"',
    "test \"$(.venv/bin/python -I -c 'import sys; "
    'print(".".join(map(str, sys.version_info[:3])))\')" = "3.13.14"',
    'test -d "${python_base_prefix}/lib/python3.13"',
    'test -f "${python_base_prefix}/lib/python3.13/os.py"',
    'test -f "${python_base_prefix}/lib/python3.13/encodings/__init__.py"',
)
CONTAINER_MANAGED_ENV = {
    '--env "UV_PYTHON_INSTALL_DIR=${repository_root}/.tools/python"',
    "--env UV_MANAGED_PYTHON=1",
    "--env UV_PYTHON_DOWNLOADS=never",
}
REPOSITORY_MOUNT = '--volume "${repository_root}:${repository_root}:ro"'
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
OFFLINE_EVIDENCE_FIELDS = (
    "schema_version",
    "non_authoritative",
    "supersedes_failed_probe_run_id",
    "workflow_sha256",
    "source_commit_sha",
    "hosted_run_id",
    "run_attempt",
    "runner_image",
    "isolation_mechanism",
    "control_command_digest",
    "direct_probe_command_digest",
    "child_probe_command_digest",
    "control_outcome",
    "direct_network_outcome",
    "child_network_outcome",
    "scenario_matrix_digest",
    "required_scenario_ids",
    "completed_scenario_ids",
    "scenario_result_digests",
    "controlled_scenario_count",
    "credential_count",
    "state_write_capability",
    "untrusted_execution_count",
    "unapproved_network_effect_count",
    "unauthorized_effect_count",
    "synthetic_scan_manifest",
    "synthetic_scan_manifest_digest",
    "synthetic_canary_hit_count",
    "artifact_retention_days",
)
OFFLINE_DIAGNOSTIC_FIELDS = (
    "schema_version",
    "source_commit_sha",
    "workflow_sha256",
    "hosted_run_id",
    "run_attempt",
    "stage",
    "overall_status",
    "control_status",
    "direct_status",
    "child_status",
    "artifact_retention_days",
)
OFFLINE_DIAGNOSTIC_STAGES = (
    "runtime-preflight",
    "control",
    "direct-probe",
    "child-probe",
    "campaign-report",
    "synthetic-scan",
    "complete",
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


def _assert_network_none_python_runtime_mounts(job: str) -> None:
    assert MANAGED_PYTHON_INSTALL in job
    assert MANAGED_PYTHON_SYNC in job
    assert all(token in job for token in PYTHON_BASE_PREFIX_PREFLIGHT)
    assert "RUNNER_TOOL_CACHE" not in job
    assert '--volume "${python_base_prefix}:${python_base_prefix}:ro"' not in job
    invocations = job.split("docker run --network none --rm \\")[1:]
    assert invocations
    allowed_volumes = {
        "--volume /bin:/bin:ro",
        "--volume /etc:/etc:ro",
        "--volume /lib:/lib:ro",
        "--volume /lib64:/lib64:ro",
        "--volume /usr:/usr:ro",
        REPOSITORY_MOUNT,
        '--volume "${probe_root}:/probe:ro"',
        '--volume "${campaign_root}:/probe:ro"',
        '--volume "${campaign_root}:/probe:rw"',
    }
    for invocation in invocations:
        options, separator, _ = invocation.partition(f"{LOCAL_UV} run --locked --offline --no-sync")
        assert separator
        volume_lines = {
            line.strip().removesuffix(" \\")
            for line in options.splitlines()
            if line.strip().startswith("--volume ")
        }
        assert REPOSITORY_MOUNT in volume_lines
        assert volume_lines <= allowed_volumes
        assert CONTAINER_MANAGED_ENV <= {
            line.strip().removesuffix(" \\")
            for line in options.splitlines()
            if line.strip().startswith("--env ")
        }


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
    _assert_network_none_python_runtime_mounts(job)
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


def _assert_offline_adversarial_workflow(source: str) -> None:
    job = _job(source, "offline_adversarial")
    assert "runs-on: ubuntu-24.04" in job
    assert re.search(r"^    permissions:\n      contents: read$", job, re.MULTILINE)
    assert f"actions/checkout@{CHECKOUT_SHA}" in job
    assert f"astral-sh/setup-uv@{SETUP_UV_SHA}" in job
    assert job.count("docker run --network none") == 3
    _assert_network_none_python_runtime_mounts(job)
    assert "tests/test_phase6_adversarial.py" in job
    assert "python /probe/direct_probe.py" in job
    assert "python /probe/child_probe.py" in job
    assert 'PHASE6_PRIOR_FAILED_PROBE_RUN_ID="30430010273"' in job
    assert "observed artifact count was zero" in job
    assert "phase6-synthetic-header-canary" in job
    assert "phase6-synthetic-payload-canary" in job
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in job
    assert "retention-days: 1" in job
    assert "if-no-files-found: error" in job
    assert "offline-evidence.json" in job
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
        == OFFLINE_EVIDENCE_FIELDS
    )
    _assert_offline_failure_diagnostic(job)


def _assert_offline_failure_diagnostic(job: str) -> None:
    campaign_match = re.search(
        r"^      - name: Run the fresh kernel-isolated adversarial campaign\n"
        r"        id: offline_campaign\n"
        r"        run: \|\n"
        r"(?P<body>.*?)(?=^      - name: )",
        job,
        re.MULTILINE | re.DOTALL,
    )
    assert campaign_match is not None
    campaign = campaign_match.group("body")
    format_match = re.search(
        r"^          diagnostic_format='(?P<format>\{.*\})\\n'$",
        campaign,
        re.MULTILINE,
    )
    assert format_match is not None
    rendered = format_match.group("format") % (
        "phase6.offline-diagnostic.v1",
        "a" * 40,
        "absent",
        123,
        1,
        "runtime-preflight",
        1,
        -1,
        -1,
        -1,
    )
    diagnostic = json.loads(rendered)
    assert tuple(diagnostic) == OFFLINE_DIAGNOSTIC_FIELDS
    assert diagnostic["artifact_retention_days"] == 1
    for field in (
        "hosted_run_id",
        "run_attempt",
        "overall_status",
        "control_status",
        "direct_status",
        "child_status",
        "artifact_retention_days",
    ):
        assert type(diagnostic[field]) is int
    assert diagnostic["workflow_sha256"] == "absent"
    assert (
        tuple(
            re.findall(
                r'^          diagnostic_stage="([a-z-]+)"$',
                campaign,
                re.MULTILINE,
            )
        )
        == OFFLINE_DIAGNOSTIC_STAGES
    )
    assert "control_status=-1" in campaign
    assert "direct_status=-1" in campaign
    assert "child_status=-1" in campaign
    assert "campaign_exit_status=$?" in campaign
    assert 'overall_status="$campaign_exit_status"' in campaign
    assert 'exit "$campaign_exit_status"' in campaign
    assert "diagnostic_write_status" in campaign
    assert (
        'case "$diagnostic_stage" in '
        "runtime-preflight|control|direct-probe|child-probe|campaign-report|"
        "synthetic-scan|complete) ;;"
    ) in campaign
    assert campaign.index("diagnostic_format=") < campaign.index("python_base_prefix_output=")

    diagnostic_upload = re.search(
        r"^      - name: Upload the bounded noncanonical campaign diagnostic\n"
        r"(?P<body>.*?)(?=^      - name: )",
        job,
        re.MULTILINE | re.DOTALL,
    )
    assert diagnostic_upload is not None
    upload = diagnostic_upload.group("body")
    assert "if: ${{ always() && steps.offline_campaign.outcome == 'failure' }}" in upload
    assert f"uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in upload
    assert (
        "name: phase6-offline-adversarial-diagnostic-${{ github.run_id }}-${{ github.run_attempt }}"
    ) in upload
    assert ("path: ${{ runner.temp }}/phase6-offline-adversarial/failure-diagnostic.json") in upload
    assert "if-no-files-found: error" in upload
    assert "retention-days: 1" in upload
    assert all(
        token not in upload.casefold()
        for token in (
            ".log",
            "offline-evidence",
            "canonical",
            "state",
            "credential",
            "secret",
        )
    )
    assert job.count(f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}") == 2

    evidence_upload = job.partition("- name: Upload the bounded noncanonical offline evidence")[2]
    assert evidence_upload
    assert "if: always()" not in evidence_upload


def test_offline_campaign_failure_uploads_one_bounded_diagnostic_without_authority() -> None:
    job = _job(_source(required=False), "offline_adversarial")
    _assert_offline_failure_diagnostic(job)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        (
            "runtime-preflight|control|direct-probe|child-probe|campaign-report|"
            "synthetic-scan|complete",
            "runtime-preflight|control|direct-probe|child-probe|campaign-report|"
            "synthetic-scan|complete|debug",
        ),
        ("control_status=-1", 'control_status="not-run"'),
        (
            '"artifact_retention_days":1}',
            '"message":"campaign failed","artifact_retention_days":1}',
        ),
        (
            '"artifact_retention_days":1}',
            '"log_path":"/tmp/control.log","artifact_retention_days":1}',
        ),
        ("retention-days: 1", "retention-days: 2"),
        (
            f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}",
            "actions/upload-artifact@main",
        ),
        (
            "phase6-offline-adversarial-diagnostic-",
            "phase6-offline-adversarial-canonical-evidence-",
        ),
        (
            "if: ${{ always() && steps.offline_campaign.outcome == 'failure' }}",
            "if: ${{ always() }}",
        ),
    ),
)
def test_offline_failure_diagnostic_mutations_fail_closed(
    needle: str,
    replacement: str,
) -> None:
    source = _source(required=False)
    job = _job(source, "offline_adversarial")
    assert needle in job
    mutated_job = job.replace(needle, replacement, 1)
    with pytest.raises(AssertionError):
        _assert_offline_failure_diagnostic(mutated_job)


def test_offline_adversarial_runs_complete_kernel_isolated_campaign_without_credentials() -> None:
    source = _source(required=False)
    _assert_offline_adversarial_workflow(source)
    job = _job(source, "offline_adversarial")
    forbidden = (
        "DEEPSEEK",
        "OPENAI",
        "SKILLSCOUT_GITHUB_APP",
        "SKILLSCOUT_CATALOG",
        "SKILLSCOUT_STATE_GITHUB_TOKEN",
        "contents: write",
        "pull-requests: write",
        "administration:",
        "${{ secrets.",
    )
    assert all(token not in job for token in forbidden)


def test_offline_adversarial_synthetic_scan_manifest_is_explicit_and_path_closed() -> None:
    job = _job(_source(required=False), "offline_adversarial")
    assert (
        'scan_names = ("control.log", "redacted-state.json", '
        '"campaign-report.json", "one-day-artifact.json", "pr-diff-fixture.txt")'
    ) in job
    forbidden = (
        "rglob(",
        "os.walk(",
        "path.home(",
        ".pem",
        ".jwt",
        "private-key",
        "private_key",
    )
    assert all(token not in job.casefold() for token in forbidden)
    assert re.search(r"""(?i)(?:["'/])\.env(?:["'/\s]|$)""", job) is None
    assert 'raise SystemExit("synthetic canary reached an allowlisted surface")' in job


@pytest.mark.parametrize(
    "replacement",
    (
        '--volume "${python_base_prefix}:${python_base_prefix}:ro" \\\n            '
        + REPOSITORY_MOUNT,
        '--volume "${RUNNER_TOOL_CACHE}:${RUNNER_TOOL_CACHE}:ro" \\\n            '
        + REPOSITORY_MOUNT,
        "--volume /opt:/opt:ro \\\n            " + REPOSITORY_MOUNT,
        "--volume /srv/unvalidated:/srv/unvalidated:ro \\\n            " + REPOSITORY_MOUNT,
        '--volume "${repository_root}:${repository_root}:rw"',
        '--volume "${repository_root}:/runtime:ro"',
    ),
)
def test_network_none_python_runtime_mount_mutations_fail_closed(
    replacement: str,
) -> None:
    source = _source(required=False)
    job = _job(source, "offline_adversarial")
    assert REPOSITORY_MOUNT in job
    mutated = job.replace(REPOSITORY_MOUNT, replacement, 1)
    with pytest.raises(AssertionError):
        _assert_network_none_python_runtime_mounts(mutated)


def test_network_none_python_runtime_mount_requires_validated_base_prefix() -> None:
    source = _source(required=False)
    for name in ("isolation_probe", "offline_adversarial"):
        job = _job(source, name)
        _assert_network_none_python_runtime_mounts(job)
        mutated = job.replace(
            'managed_python_root="$(realpath -e -- "${repository_root}/.tools/python")"',
            'managed_python_root="${repository_root}/.tools/python"',
            1,
        )
        with pytest.raises(AssertionError):
            _assert_network_none_python_runtime_mounts(mutated)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ("docker run --network none", "docker run"),
        (
            'PHASE6_PRIOR_FAILED_PROBE_RUN_ID="30430010273"',
            'PHASE6_PRIOR_FAILED_PROBE_RUN_ID="1"',
        ),
        ("phase6-synthetic-header-canary", "removed-header-seed"),
        ("synthetic_scan_manifest_digest", "unbounded_scan_digest"),
        ("retention-days: 1", "retention-days: 30"),
    ),
)
def test_offline_adversarial_mutations_fail_closed(
    needle: str,
    replacement: str,
) -> None:
    source = _source(required=False)
    job = _job(source, "offline_adversarial")
    assert needle in job
    mutated_job = job.replace(needle, replacement, 1)
    with pytest.raises(AssertionError):
        _assert_offline_adversarial_workflow(source.replace(job, mutated_job, 1))


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
