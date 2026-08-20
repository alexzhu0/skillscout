"""Static and mutation contracts for the secretless Phase 6 isolation probe."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/phase6-acceptance.yml"
SUMMARY = ROOT / "evidence/phase-6-adversarial-mvp-acceptance/06-02-SUMMARY.md"
CHECKOUT_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"
SETUP_UV_SHA = "c771a70e6277c0a99b617c7a806ffedaca235ff9"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
LOCAL_UV = ".tools/uv-0.11.29/bin/uv"
CAMPAIGN_RUNNER = ".venv/bin/python -I -m skillscout.application.phase6_adversarial_runner"
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
CONTROL_USER_OPTION = '--user "${host_uid}:${host_gid}"'


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


def _offline_campaign_script(source: str) -> str:
    job = _job(source, "offline_adversarial")
    match = re.search(
        r"^      - name: Run the fresh kernel-isolated adversarial campaign\n"
        r"        id: offline_campaign\n"
        r"        run: \|\n"
        r"(?P<body>.*?)(?=^      - name: )",
        job,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    return textwrap.dedent(match.group("body"))


def _control_fragment(script: str) -> str:
    start = script.index('export PHASE6_SYNTHETIC_HEADER_CANARY="phase6-synthetic-header-canary-')
    end = script.index("control_status=$?", start) + len("control_status=$?")
    return script[start:end] + '\ntest "${control_status}" -eq 0\n'


def _synthetic_scan_program(script: str) -> str:
    marker = ".tools/uv-0.11.29/bin/uv run --locked --offline --no-sync python - <<'PY'\n"
    start = script.index(marker) + len(marker)
    end = script.index("\nPY", start)
    return script[start:end]


def _write_control_docker_fake(directory: Path) -> None:
    fake = directory / "docker"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "arguments = sys.argv[1:]\n"
        "users = [arguments[index + 1] for index, value in enumerate(arguments) "
        "if value == '--user' and index + 1 < len(arguments)]\n"
        "if users != [os.environ['EXPECTED_CONTROL_USER']]:\n"
        "    raise SystemExit(64)\n"
        "mounts = [arguments[index + 1] for index, value in enumerate(arguments) "
        "if value == '--volume' and index + 1 < len(arguments)]\n"
        "writable = [value for value in mounts if value.endswith(':/probe:rw')]\n"
        "if len(writable) != 1:\n"
        "    raise SystemExit(65)\n"
        "root = Path(writable[0].removesuffix(':/probe:rw'))\n"
        "scenario_ids = [f'scenario-{index:02d}' for index in range(15)]\n"
        "report = {\n"
        "    'schema_version': 'phase6.offline-campaign-report.v1',\n"
        "    'scenario_matrix_digest': 'sha256:' + 'a' * 64,\n"
        "    'required_scenario_ids': scenario_ids,\n"
        "    'completed_scenario_ids': scenario_ids,\n"
        "    'scenario_result_digests': ['sha256:' + f'{index:064x}' "
        "for index in range(15)],\n"
        "    'controlled_scenario_count': 15,\n"
        "    'untrusted_execution_count': 0,\n"
        "    'unapproved_network_effect_count': 0,\n"
        "    'unauthorized_effect_count': 0,\n"
        "    'synthetic_canary_hit_count': 0,\n"
        "}\n"
        "payload = (json.dumps(report, sort_keys=True) + '\\n').encode('ascii')\n"
        "descriptor = os.open(\n"
        "    root / 'campaign-report.json',\n"
        "    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,\n"
        "    0o600,\n"
        ")\n"
        "with os.fdopen(descriptor, 'wb') as stream:\n"
        "    stream.write(payload)\n"
        "    stream.flush()\n"
        "    os.fsync(stream.fileno())\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)


def _execute_control_fragment(tmp_path: Path) -> tuple[Path, str]:
    source = _source(required=False)
    script = _offline_campaign_script(source)
    campaign_root = tmp_path / "campaign"
    campaign_root.mkdir()
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    _write_control_docker_fake(fake_bin)
    environment = {
        **os.environ,
        "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
        "EXPECTED_CONTROL_USER": f"{os.getuid()}:{os.getgid()}",
        "PHASE6_RUN_ID": "123456789",
        "PHASE6_RUN_ATTEMPT": "1",
        "PHASE6_SOURCE_COMMIT": "a" * 40,
        "PHASE6_WORKFLOW_SHA256": "b" * 64,
        "repository_root": str(ROOT),
        "campaign_root": str(campaign_root),
        "image_tag": "phase6-test:local",
    }
    completed = subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + _control_fragment(script)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    report = campaign_root / "campaign-report.json"
    assert stat.S_IMODE(report.stat().st_mode) == 0o600
    return campaign_root, _synthetic_scan_program(script)


def _run_synthetic_scan(campaign_root: Path, program: str) -> subprocess.CompletedProcess[str]:
    (campaign_root / "direct_probe.py").write_text("raise SystemExit(97)\n", encoding="utf-8")
    (campaign_root / "child_probe.py").write_text("raise SystemExit(97)\n", encoding="utf-8")
    environment = {
        **os.environ,
        "PHASE6_CAMPAIGN_ROOT": str(campaign_root),
        "PHASE6_PRIOR_FAILED_PROBE_RUN_ID": "30430010273",
        "PHASE6_CONTROL_OUTCOME": "passed",
        "PHASE6_DIRECT_OUTCOME": "denied",
        "PHASE6_CHILD_OUTCOME": "denied",
        "PHASE6_SYNTHETIC_HEADER_CANARY": "phase6-synthetic-header-canary-123456789-1",
        "PHASE6_SYNTHETIC_PAYLOAD_CANARY": "phase6-synthetic-payload-canary-123456789-1",
        "PHASE6_WORKFLOW_SHA256": "b" * 64,
        "PHASE6_SOURCE_COMMIT": "a" * 40,
        "PHASE6_RUN_ID": "123456789",
        "PHASE6_RUN_ATTEMPT": "1",
    }
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


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
        if not separator:
            options, separator, _ = invocation.partition(CAMPAIGN_RUNNER)
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
        "prepare_fresh_campaign",
        "benchmark_lock",
        "rebind_benchmark_lock",
        "offline_adversarial",
        "live_authority_preflight",
        "live_benchmark",
        "live_replay",
        "human_attestation",
        "record_live_authority",
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
    assert CAMPAIGN_RUNNER in job
    assert "pytest -q tests/test_phase6_adversarial.py" not in job
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
    assert (
        '"$diagnostic_stage" = "control" && "$control_status" -ne 0 && -s "$diagnostic_path"'
    ) in campaign
    assert campaign.count('printf "$diagnostic_format"') == 1

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


def test_offline_campaign_invokes_production_runner_instead_of_pytest_teardown() -> None:
    job = _job(_source(required=False), "offline_adversarial")
    assert "pytest -q tests/test_phase6_adversarial.py" not in job
    assert CAMPAIGN_RUNNER in job


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


def test_control_report_created_with_mode_0600_is_readable_by_host_synthetic_scanner(
    tmp_path: Path,
) -> None:
    campaign_root, scan_program = _execute_control_fragment(tmp_path)
    completed = _run_synthetic_scan(campaign_root, scan_program)
    assert completed.returncode == 0, completed.stderr
    assert (campaign_root / "offline-evidence.json").is_file()


def test_host_synthetic_scanner_fails_closed_when_control_report_is_unreadable(
    tmp_path: Path,
) -> None:
    if os.geteuid() == 0:
        pytest.skip("mode-only unreadability requires a non-root scanner identity")
    campaign_root, scan_program = _execute_control_fragment(tmp_path)
    report = campaign_root / "campaign-report.json"
    report.chmod(0)
    completed = _run_synthetic_scan(campaign_root, scan_program)
    assert completed.returncode != 0
    assert "PermissionError" in completed.stderr


def test_host_synthetic_scanner_detects_exact_canary_in_control_report(
    tmp_path: Path,
) -> None:
    campaign_root, scan_program = _execute_control_fragment(tmp_path)
    report = campaign_root / "campaign-report.json"
    payload = json.loads(report.read_bytes())
    canary = "phase6-synthetic-header-canary-123456789-1"
    payload["mutation_probe"] = canary
    report.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    report.chmod(0o600)
    completed = _run_synthetic_scan(campaign_root, scan_program)
    assert completed.returncode != 0
    assert completed.stderr.strip() == "synthetic canary reached an allowlisted surface"
    assert canary not in completed.stderr


def test_offline_control_container_has_one_numeric_host_identity_mapping() -> None:
    job = _job(_source(required=False), "offline_adversarial")
    assert job.count('host_uid="$(id -u)"') == 1
    assert job.count('host_gid="$(id -g)"') == 1
    assert job.count(CONTROL_USER_OPTION) == 1
    control = job.partition('diagnostic_stage="control"')[2].partition(
        'diagnostic_stage="direct-probe"'
    )[0]
    assert control.count(CONTROL_USER_OPTION) == 1
    assert CONTROL_USER_OPTION not in job.partition('diagnostic_stage="direct-probe"')[2]


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
        "preflight-fresh-campaign",
        "prepare-fresh-campaign",
        "lock-fresh-campaign",
        "rebind-benchmark-lock",
        "offline-adversarial",
        "run-benchmark",
        "run-replay",
        "record-live-authority",
        "record-human-review",
        "record-probe-cleanup",
        "rebuild-report",
    )

    nomination = _job(source, "nominate")
    fresh_prepare = _job(source, "prepare_fresh_campaign")
    benchmark_lock = _job(source, "benchmark_lock")
    offline = _job(source, "offline_adversarial")
    preflight = _job(source, "live_authority_preflight")
    benchmark = _job(source, "live_benchmark")
    replay = _job(source, "live_replay")
    human = _job(source, "human_attestation")
    live_authority = _job(source, "record_live_authority")
    cleanup = _job(source, "cleanup_attestation")
    rebuild = _job(source, "rebuild_report")

    assert "contents: write" in nomination
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" in nomination
    assert "SKILLSCOUT_STATE_REPOSITORY_ID: ${{ vars.SKILLSCOUT_STATE_REPOSITORY_ID }}" in nomination
    assert "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME: ${{ vars.SKILLSCOUT_STATE_REPOSITORY_FULL_NAME }}" in nomination
    assert "DEEPSEEK" not in nomination
    assert "SKILLSCOUT_CATALOG" not in nomination
    assert "${{ secrets." not in nomination

    assert "DEEPSEEK" not in fresh_prepare
    assert "SKILLSCOUT_CATALOG" not in fresh_prepare
    assert "run-acceptance" not in fresh_prepare
    assert "prepare-fresh-campaign" in fresh_prepare
    assert "preflight-fresh-campaign" in fresh_prepare
    assert "environment: phase6-fresh-nomination" in fresh_prepare
    assert (
        "if: ${{ (inputs.phase6_action == 'prepare-fresh-campaign' || "
        "inputs.phase6_action == 'preflight-fresh-campaign') && "
        "github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }}"
        in fresh_prepare
    )
    preflight_prefix, _, preflight_operation = fresh_prepare.partition(
        "      - name: Run read-only fresh campaign preflight"
    )
    assert preflight_operation
    assert "if: ${{ inputs.phase6_action == 'preflight-fresh-campaign' }}" in preflight_operation
    assert "python -m skillscout.cli preflight-fresh-campaign" in preflight_operation
    assert "SKILLSCOUT_SOURCE_GITHUB_TOKEN: ${{ github.token }}" in preflight_operation
    assert (
        "SKILLSCOUT_STATE_GITHUB_TOKEN: "
        "${{ secrets.SKILLSCOUT_FRESH_NOMINATION_STATE_GITHUB_TOKEN }}"
        in preflight_operation
    )
    assert "SKILLSCOUT_SOURCE_GITHUB_TOKEN" not in preflight_prefix
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" not in preflight_prefix
    prepare_prefix, _, prepare_operation = fresh_prepare.partition(
        "      - name: Prepare one bounded fresh Search nomination"
    )
    assert prepare_operation
    assert "if: ${{ inputs.phase6_action == 'prepare-fresh-campaign' }}" in prepare_operation
    assert "SKILLSCOUT_SOURCE_GITHUB_TOKEN: ${{ github.token }}" in prepare_operation
    assert (
        "SKILLSCOUT_STATE_GITHUB_TOKEN: "
        "${{ secrets.SKILLSCOUT_FRESH_NOMINATION_STATE_GITHUB_TOKEN }}"
        in prepare_operation
    )
    assert "${{ secrets.SKILLSCOUT_STATE_GITHUB_TOKEN }}" not in prepare_operation

    assert "name: skillscout-phase6-benchmark-lock" in benchmark_lock
    assert "environment: phase6-human-benchmark-lock" in benchmark_lock
    assert (
        "if: ${{ inputs.phase6_action == 'lock-fresh-campaign' && "
        "github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }}"
        in benchmark_lock
    )
    assert re.search(
        r"^    permissions:\n      contents: read\n      actions: read$",
        benchmark_lock,
        re.MULTILINE,
    )
    assert "prepare-fresh-lock-handoff" in benchmark_lock
    for forbidden in (
        "DEEPSEEK",
        "semantic",
        "candidate",
        "catalog",
        "pull-request",
        "reviewer",
        "publication",
        "create-github-app-token",
    ):
        assert forbidden.casefold() not in benchmark_lock.casefold()
    approval_prefix, _, approval_and_persist = benchmark_lock.partition(
        "      - name: Verify and emit one environment-approved benchmark lock handoff"
    )
    assert approval_and_persist
    approval_operation, _, persist_operation = approval_and_persist.partition(
        "      - name: Persist one verified environment-approved benchmark lock"
    )
    assert persist_operation
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" not in approval_prefix
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" not in approval_operation
    assert "GITHUB_TOKEN: ${{ github.token }}" in approval_operation
    assert "PHASE6_FRESH_LOCK_HANDOFF: ${{ steps.prepare_handoff.outputs.fresh_lock_handoff }}" in persist_operation
    assert (
        "SKILLSCOUT_STATE_GITHUB_TOKEN: "
        "${{ secrets.SKILLSCOUT_BENCHMARK_LOCK_STATE_GITHUB_TOKEN }}"
        in persist_operation
    )
    assert "${{ secrets.SKILLSCOUT_STATE_GITHUB_TOKEN }}" not in persist_operation
    assert "lock-fresh-campaign" in persist_operation

    assert "contents: read" in offline
    assert "contents: write" not in offline
    assert "${{ secrets." not in offline
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" not in offline

    for semantic_job in (benchmark,):
        assert "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}" in semantic_job
        assert "SKILLSCOUT_STATE_GITHUB_TOKEN" in semantic_job
        assert "SKILLSCOUT_CATALOG" not in semantic_job
        assert "SKILLSCOUT_GITHUB_APP" not in semantic_job
        assert "--state-commit-sha" in semantic_job
        assert "--state-root-digest" in semantic_job

    for removed_job in ("changed_source", "fresh_gate_b4", "value_publication"):
        assert f"\n  {removed_job}:\n" not in source
    for removed_action in ("run-changed-source", "gate-b4-and-publish"):
        assert removed_action not in source
    for forbidden_publication_capability in (
        "actions/create-github-app-token",
        "SKILLSCOUT_GITHUB_APP_PRIVATE_KEY",
        "SKILLSCOUT_CATALOG_FULL_NAME",
        "skillscout-catalog-test",
        "permission-pull-requests: write",
    ):
        assert forbidden_publication_capability not in source

    for attestation in (human, cleanup):
        assert "SKILLSCOUT_STATE_GITHUB_TOKEN" in attestation
        assert "DEEPSEEK_API_KEY" not in attestation
        assert "SKILLSCOUT_CATALOG" not in attestation
        assert "record-acceptance-attestation" in attestation
        assert "PHASE6_AUTHORITY_STATE_COMMIT_SHA" in attestation
        assert "PHASE6_AUTHORITY_STATE_ROOT_DIGEST" in attestation
    assert (
        "if: ${{ inputs.phase6_action == 'record-human-review' }}" in human
    )
    assert "record-live-authority" not in human
    assert "github.actor" not in human
    assert "environment: skillscout-phase6-live-authority" in live_authority
    for job in (preflight, benchmark, replay, human):
        assert "UV_LINK_MODE: copy" in job
    assert "DEEPSEEK_API_KEY" not in human
    assert "SKILLSCOUT_LLM_PROVIDER: deepseek" in human
    assert "SKILLSCOUT_CATALOG" not in human
    assert "--kind human-review" in human
    assert "--kind probe-cleanup" in cleanup

    assert "contents: read" in rebuild
    assert "contents: write" not in rebuild
    assert "${{ secrets." not in rebuild
    assert "PHASE6_AUTHORITY_STATE_COMMIT_SHA" in rebuild
    assert "PHASE6_AUTHORITY_STATE_ROOT_DIGEST" in rebuild
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ github.token }}" in rebuild
    assert "rebuild-acceptance" in rebuild

    upload_blocks = re.findall(
        r"uses: actions/upload-artifact@[0-9a-f]{40}\n(?P<body>(?:\s{8,}.*\n?)*)",
        source,
    )
    assert upload_blocks
    assert all("if-no-files-found: error" in block for block in upload_blocks)
    assert all("retention-days: 1" in block for block in upload_blocks)


def test_record_live_authority_requires_environment_b_before_state_credential() -> None:
    """Reject the legacy caller/actor route before it can persist V2 authority."""

    source = _source(required=False)
    human = _job(source, "human_attestation")
    live = _job(source, "record_live_authority")

    assert "live_authority_json" not in source.casefold()
    assert "record-live-authority" not in human
    assert "github.actor" not in human
    assert "name: skillscout-phase6-live-authority" in live
    assert (
        "if: ${{ inputs.phase6_action == 'record-live-authority' && "
        "github.repository == 'alexzhu0/skillscout' && "
        "github.ref == 'refs/heads/main' }}" in live
    )
    assert "environment: skillscout-phase6-live-authority" in live
    assert re.search(
        r"^    permissions:\n      contents: read\n      actions: read$",
        live,
        re.MULTILINE,
    )
    assert "contents: write" not in live

    route_prefix, separator, persist = live.partition(
        "      - name: Persist one environment-approved V2 live authority"
    )
    assert separator and persist
    assert route_prefix.count("SKILLSCOUT_STATE_GITHUB_TOKEN") == 0
    assert "SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:" in route_prefix
    assert "SKILLSCOUT_STATE_REPOSITORY_ID:" in route_prefix
    assert "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME:" in route_prefix
    assert f"actions/checkout@{CHECKOUT_SHA}" in route_prefix
    assert "ref: ${{ github.sha }}" in route_prefix
    assert "persist-credentials: false" in route_prefix
    assert f"astral-sh/setup-uv@{SETUP_UV_SHA}" in route_prefix
    assert "version: 0.11.29" in route_prefix
    assert "enable-cache: false" in route_prefix
    assert "Verify the repository-local locked toolchain" in route_prefix

    assert "GITHUB_TOKEN: ${{ github.token }}" in persist
    assert (
        "SKILLSCOUT_STATE_GITHUB_TOKEN: "
        "${{ secrets.SKILLSCOUT_LIVE_AUTHORITY_STATE_GITHUB_TOKEN }}" in persist
    )
    assert "set -euo pipefail" in persist
    assert "umask 077" in persist
    assert (
        ".tools/uv-0.11.29/bin/uv run --locked python -m skillscout.cli "
        "record-live-authority --acceptance-run-id "
        "\"${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}\"" in persist
    )
    assert "--authority" not in persist
    assert "--source-commit-sha" not in persist
    for forbidden in (
        "github.actor",
        "deepseek",
        "semantic",
        "candidate",
        "catalog",
        "pull-request",
        "reviewer",
        "publication",
        "create-github-app-token",
        "curl",
        "wget",
        "http://",
        "https://",
        "SKILLSCOUT_SOURCE_GITHUB_TOKEN",
    ):
        assert forbidden.casefold() not in live.casefold()


def test_rebind_benchmark_lock_requires_environment_approval_before_state_credential() -> None:
    """The rebind route is a distinct, closed state-only environment transition."""

    rebind = _job(_source(required=False), "rebind_benchmark_lock")

    assert "name: skillscout-phase6-benchmark-lock-rebind" in rebind
    assert (
        "if: ${{ inputs.phase6_action == 'rebind-benchmark-lock' && "
        "github.repository == 'alexzhu0/skillscout' && "
        "github.ref == 'refs/heads/main' && github.run_attempt == '1' }}" in rebind
    )
    assert "environment: phase6-human-benchmark-lock" in rebind
    assert re.search(
        r"^    permissions:\n      contents: read\n      actions: read$",
        rebind,
        re.MULTILINE,
    )
    assert "contents: write" not in rebind

    prefix, separator, persist = rebind.partition(
        "      - name: Persist one environment-approved benchmark lock rebind"
    )
    assert separator and persist
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" not in prefix
    assert "SKILLSCOUT_PHASE6_SOURCE_ACCEPTANCE_RUN_ID:" in prefix
    assert "SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:" in prefix
    assert "SKILLSCOUT_STATE_REPOSITORY_ID" not in rebind
    assert "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME" not in rebind
    assert "GITHUB_TOKEN: ${{ github.token }}" in prefix
    assert "prepare-benchmark-lock-rebind-handoff" in prefix
    assert f"actions/checkout@{CHECKOUT_SHA}" in prefix
    assert "ref: ${{ github.sha }}" in prefix
    assert "persist-credentials: false" in prefix
    assert f"astral-sh/setup-uv@{SETUP_UV_SHA}" in prefix
    assert "Verify the repository-local locked toolchain" in prefix

    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: " in persist
    assert (
        "${{ secrets.SKILLSCOUT_BENCHMARK_LOCK_STATE_GITHUB_TOKEN }}" in persist
    )
    assert "GITHUB_TOKEN: ${{ github.token }}" not in persist
    assert "set -euo pipefail" in persist
    assert "umask 077" in persist
    assert "skillscout.cli rebind-benchmark-lock" in persist
    assert '--source-acceptance-run-id "${SKILLSCOUT_PHASE6_SOURCE_ACCEPTANCE_RUN_ID:?}"' in persist
    assert '--target-acceptance-run-id "${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}"' in persist
    for forbidden in (
        "deepseek",
        "github_app",
        "catalog",
        "publish",
        "run-acceptance",
        "curl",
        "wget",
        "http://",
        "https://",
        "SKILLSCOUT_SOURCE_GITHUB_TOKEN",
    ):
        assert forbidden.casefold() not in rebind.casefold()


def test_live_authority_preflight_precedes_all_semantic_credentials() -> None:
    """Catches credential-bearing execution without an independent exact-byte gate."""

    source = _source(required=False)
    preflight = _job(source, "live_authority_preflight")
    live = _job(source, "live_benchmark")

    assert "contents: read" in preflight
    assert "${{ secrets." not in preflight
    assert "SKILLSCOUT_SOURCE_GITHUB_TOKEN" not in preflight
    authority_prefix, separator, resume_suffix = preflight.partition(
        "      - name: Resolve the exact campaign resume descendant"
    )
    assert separator and resume_suffix
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN" not in authority_prefix
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ github.token }}" in resume_suffix
    assert (
        "PHASE6_MANIFEST: "
        "config/acceptance/phase6/benchmark-manifest.json" in preflight
    )
    assert "verify-live-authority" in preflight
    assert "resolve-acceptance-resume" in preflight
    assert "--authority-state-root" in preflight
    assert '--authority-state-commit-sha "$PHASE6_AUTHORITY_STATE_COMMIT_SHA"' in preflight
    assert "--authority-operations-state" not in preflight
    assert "git -C .phase6-authority-state rev-parse HEAD" in preflight
    assert re.search(r"^    needs: live_authority_preflight$", live, re.MULTILINE)
    assert "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}" in live
    assert "SKILLSCOUT_CATALOG" not in live
    assert "actions/create-github-app-token" not in live


def test_live_preflight_checks_out_authority_from_configured_state_repository() -> None:
    """The approved authority must not silently resolve against the workflow repo."""

    preflight = _job(_source(required=False), "live_authority_preflight")
    authority_checkout, separator, _ = preflight.partition(
        "      - name: Verify the immutable original live authority"
    )

    assert separator
    assert "Check out the exact independently approved authority state" in authority_checkout
    assert "repository: ${{ vars.SKILLSCOUT_STATE_REPOSITORY_FULL_NAME }}" in authority_checkout
    assert "ref: ${{ env.PHASE6_AUTHORITY_STATE_COMMIT_SHA }}" in authority_checkout
    assert "path: .phase6-authority-state" in authority_checkout
    assert "persist-credentials: false" in authority_checkout
    assert "token: ${{ github.token }}" in authority_checkout


def test_deepseek_only_exact_manifest_jobs_are_distinct_and_bounded() -> None:
    """Catches one ambiguous command silently deciding benchmark versus replay."""

    source = _source(required=False)
    preflight = _job(source, "live_authority_preflight")
    live = _job(source, "live_benchmark")
    replay = _job(source, "live_replay")

    canonical = "config/acceptance/phase6/benchmark-manifest.json"
    assert f"PHASE6_MANIFEST: {canonical}" in preflight
    assert f"PHASE6_MANIFEST: {canonical}" in live
    assert f"PHASE6_MANIFEST: {canonical}" in replay
    assert "--action benchmark" in live
    assert "--action replay" in replay
    assert "SKILLSCOUT_LLM_PROVIDER: deepseek" in live
    assert "OPENAI_API_KEY" not in live
    assert "DEEPSEEK_API_KEY" not in replay


def test_benchmark_and_replay_have_separate_late_capability_steps() -> None:
    """Replay cannot inherit the live reader, provider, or publication graph."""

    source = _source(required=False)
    benchmark = _job(source, "live_benchmark")
    replay = _job(source, "live_replay")

    benchmark_prefix, _, benchmark_execution = benchmark.partition(
        "      - name: Execute the approved live benchmark"
    )
    assert benchmark_execution
    assert benchmark_prefix.count("token: ${{ github.token }}") == 2
    assert "token: ''" not in benchmark_prefix
    assert "DEEPSEEK_API_KEY" not in benchmark_prefix
    assert "SKILLSCOUT_SOURCE_GITHUB_TOKEN" not in benchmark_prefix
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ github.token }}" in benchmark_prefix
    assert "resolve-acceptance-resume" in benchmark_prefix
    assert (
        '--authority-state-commit-sha "$PHASE6_AUTHORITY_STATE_COMMIT_SHA"'
        in benchmark_prefix
    )
    assert "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}" in benchmark_execution
    assert "SKILLSCOUT_SOURCE_GITHUB_TOKEN: ${{ github.token }}" in benchmark_execution
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ github.token }}" in benchmark_execution
    assert "--action benchmark" in benchmark_execution

    assert re.search(r"^    needs: live_authority_preflight$", replay, re.MULTILINE)
    assert "DEEPSEEK_API_KEY" not in replay
    assert "SKILLSCOUT_SOURCE_GITHUB_TOKEN" not in replay
    assert "SKILLSCOUT_CATALOG" not in replay
    assert "actions/create-github-app-token" not in replay
    assert "resolve-acceptance-resume" in replay
    assert replay.count("token: ${{ github.token }}") == 2
    assert "token: ''" not in replay
    assert (
        '--authority-state-commit-sha "$PHASE6_AUTHORITY_STATE_COMMIT_SHA"'
        in replay
    )
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ github.token }}" in replay
    assert "--action replay" in replay


def test_live_preflight_exports_complete_immutable_handoff_to_consumers() -> None:
    """Benchmark/replay may consume only verified preflight outputs, never vars."""

    source = _source(required=False)
    preflight = _job(source, "live_authority_preflight")
    benchmark = _job(source, "live_benchmark")
    replay = _job(source, "live_replay")
    required = {
        "acceptance_run_id",
        "authority_digest",
        "authority_state_commit_sha",
        "authority_state_root_digest",
        "state_commit_sha",
        "state_root_digest",
        "state_repository_id",
        "state_repository_full_name",
        "source_commit_sha",
        "manifest_digest",
    }
    assert "outputs:" in preflight
    for name in required:
        assert f"{name}: ${{{{ steps.authority_handoff.outputs.{name} }}}}" in preflight
        expression = "${{ needs.live_authority_preflight.outputs." + name + " }}"
        assert expression in benchmark
        assert expression in replay
    for consumer in (benchmark, replay):
        assert "${{ vars." not in consumer
        assert "SKILLSCOUT_STATE_REPOSITORY_ID" in consumer
        assert "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME" in consumer
        assert "PHASE6_ACCEPTANCE_RUN_ID" in consumer


def test_benchmark_repeats_authority_and_complete_state_gate_before_secrets() -> None:
    """The final secret-bearing step is preceded by a full local re-verification."""

    benchmark = _job(_source(required=False), "live_benchmark")
    prefix, separator, execution = benchmark.partition(
        "      - name: Execute the approved live benchmark"
    )
    assert separator and execution
    assert "Check out the exact independently approved authority state" in prefix
    assert "Check out the exact complete campaign state" in prefix
    assert "verify-live-authority" in prefix
    assert '--runtime-state-commit-sha "$PHASE6_AUTHORITY_STATE_COMMIT_SHA"' in prefix
    assert '--runtime-state-root-digest "$PHASE6_AUTHORITY_STATE_ROOT_DIGEST"' in prefix
    assert "resolve-acceptance-resume" in prefix
    assert "verify-acceptance-state" in prefix
    assert "DEEPSEEK_API_KEY" not in prefix
    assert "SKILLSCOUT_SOURCE_GITHUB_TOKEN" not in prefix
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ github.token }}" in prefix
    assert "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}" in execution


def test_replay_reconstructs_live_authority_before_state_write_token() -> None:
    """Replay re-verifies the approved authority and complete post-benchmark state."""

    replay = _job(_source(required=False), "live_replay")
    prefix, separator, execution = replay.partition(
        "      - name: Execute the approved zero-effect replay"
    )
    assert separator and execution
    assert "Check out the exact independently approved authority state" in prefix
    assert "Check out the exact complete campaign state" in prefix
    assert "verify-live-authority" in prefix
    assert "resolve-acceptance-resume" in prefix
    assert "verify-acceptance-state" in prefix
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ github.token }}" in prefix
    assert "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ github.token }}" in execution


@pytest.mark.parametrize("job_name", ("live_benchmark", "live_replay"))
def test_live_execution_passes_complete_authority_state_to_run_acceptance(
    job_name: str,
) -> None:
    """The final CLI command must retain the immutable authority checkout."""

    job = _job(_source(required=False), job_name)
    execution_step = {
        "live_benchmark": "      - name: Execute the approved live benchmark",
        "live_replay": "      - name: Execute the approved zero-effect replay",
    }[job_name]
    _, separator, execution = job.partition(execution_step)
    commands = [line for line in execution.splitlines() if "run-acceptance" in line]

    assert separator and execution
    assert len(commands) == 1
    command = commands[0]
    assert '--authority-state-root ".phase6-authority-state"' in command
    assert '--authority-state-commit-sha "$PHASE6_AUTHORITY_STATE_COMMIT_SHA"' in command
    assert (
        '--authority-state-root-digest "$PHASE6_AUTHORITY_STATE_ROOT_DIGEST"'
        in command
    )


def test_live_resume_uses_no_mutable_commit_or_root_variables() -> None:
    source = _source(required=False)
    preflight = _job(source, "live_authority_preflight")
    benchmark = _job(source, "live_benchmark")
    replay = _job(source, "live_replay")

    for forbidden in (
        "vars.SKILLSCOUT_PHASE6_STATE_COMMIT_SHA",
        "vars.SKILLSCOUT_PHASE6_STATE_ROOT_DIGEST",
    ):
        assert forbidden not in preflight
        assert forbidden not in benchmark
        assert forbidden not in replay
    assert "ref: skillscout-state" in preflight
    assert (
        preflight.index("verify-live-authority")
        < preflight.index("ref: skillscout-state")
        < preflight.index("resolve-acceptance-resume")
    )
    for consumer in (benchmark, replay):
        assert "resolve-acceptance-resume" in consumer
        assert "--resume-proof" in consumer
        assert '--state-commit-sha "$PHASE6_STATE_COMMIT_SHA"' in consumer
        assert '--state-root-digest "$PHASE6_STATE_ROOT_DIGEST"' in consumer


def test_nomination_installation_and_state_cas_are_source_bound() -> None:
    nomination = _job(_source(required=False), "nominate")

    assert "UV_LINK_MODE: copy" in nomination
    assert (
        "SKILLSCOUT_INITIAL_STATE_ROOT_DIGEST: "
        "sha256:b4167cffc31969854260d4acd58b804f4823a4d25d078ef3b5dc88445b75c2e5" in nomination
    )
    assert (
        "SKILLSCOUT_INITIAL_STATE_ROOT_DIGEST: "
        "${{ vars.SKILLSCOUT_INITIAL_STATE_ROOT_DIGEST }}" not in nomination
    )


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
