#!/usr/bin/env python3
"""Fail-closed, dependency-free verifier for authoritative workflow execution."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple, Sequence

WORKFLOW_PATHS = (
    Path(".github/workflows/discover.yml"),
    Path(".github/workflows/publish-candidate.yml"),
    Path(".github/workflows/gate-b4-canary.yml"),
    Path(".github/workflows/phase6-acceptance.yml"),
)
CHECKOUT_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"
SETUP_UV_SHA = "c771a70e6277c0a99b617c7a806ffedaca235ff9"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
CHECKOUT = f"actions/checkout@{CHECKOUT_SHA}"
SETUP_UV = f"astral-sh/setup-uv@{SETUP_UV_SHA}"
UPLOAD_ARTIFACT = f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}"
LOCAL_UV = ".tools/uv-0.11.29/bin/uv"
LOCAL_LOCKED = f"{LOCAL_UV} run --locked"
CAMPAIGN_RUNNER = ".venv/bin/python -I -m skillscout.application.phase6_adversarial_runner"
MANAGED_PYTHON_VERSION = "3.13.14"
MANAGED_PYTHON_ROOT = "${GITHUB_WORKSPACE}/.tools/python"
FRESH_MATERIALIZATION_RUN_SHA256 = (
    "00e1268ea5957663acc02e1c213a42d24f7fdfca47dc3ad3b76999cd229b5e30"
)
LIVE_AUTHORITY_JOB = "record_live_authority"
LIVE_AUTHORITY_ENVIRONMENT = "skillscout-phase6-live-authority"
LIVE_AUTHORITY_STATE_SECRET = "SKILLSCOUT_LIVE_AUTHORITY_STATE_GITHUB_TOKEN"
FINAL_LIVE_AUTHORITY_JOB_SENTINEL = "__SKILLSCOUT_PHASE6_FINAL_LIVE_AUTHORITY_JOB__"
EXPECTED_CLOSED_WORKFLOW_SOURCE_DIGESTS = (
    (
        ".github/workflows/discover.yml",
        "71c174175b03355f432348bda9fca47ee72bee20a939d87720b7c32d4fe370e4",
    ),
    (
        ".github/workflows/publish-candidate.yml",
        "0bb486d9f06cc93d97a953bc1f40b6b2f206c9fdccdc914a90af1c9388faac19",
    ),
    (
        ".github/workflows/gate-b4-canary.yml",
        "ad06ccec08cf1df76a395b14574957e69aebe3ce78b2892c22c23912ed672ccc",
    ),
    (
        ".github/workflows/phase6-acceptance.yml",
        "fa8bfe71f252c5dc25abc456da03842d563a28701e4d0ddd9dfd42b934f152e9",
    ),
)
MANAGED_PYTHON_INSTALL = (
    'UV_PYTHON_INSTALL_DIR="${managed_python_root}" UV_MANAGED_PYTHON=1 '
    f"{LOCAL_UV} python install {MANAGED_PYTHON_VERSION} "
    '--install-dir "${managed_python_root}" --no-bin'
)
MANAGED_PYTHON_SYNC = (
    'UV_PYTHON_INSTALL_DIR="${managed_python_root}" UV_MANAGED_PYTHON=1 '
    f"UV_PYTHON_DOWNLOADS=never {LOCAL_UV} sync --locked "
    '--python "${managed_python_executable}" '
    "--managed-python --no-python-downloads"
)
MANAGED_PYTHON_TOOLCHAIN = (
    'repository_root="$(realpath -e -- "${GITHUB_WORKSPACE}")"',
    'test "${repository_root}" = "${GITHUB_WORKSPACE}"',
    'test "${repository_root}" = "$(pwd -P)"',
    'tools_root="${repository_root}/.tools"',
    'test ! -L "${tools_root}"',
    'test "$(realpath -e -- "${tools_root}")" = "${tools_root}"',
    'managed_python_root="${tools_root}/python"',
    'test "${managed_python_root}" = "${GITHUB_WORKSPACE}/.tools/python"',
    'if [[ -L "${managed_python_root}" ]]; then',
    'test "$(realpath -e -- "${managed_python_root}")" = "${managed_python_root}"',
    MANAGED_PYTHON_INSTALL,
    f"{LOCAL_UV} python find --managed-python {MANAGED_PYTHON_VERSION}",
    'managed_python_executable="$(realpath -e -- "${managed_python_executable}")"',
    '"${managed_python_root}"/*/bin/python*)',
    'venv_root="${repository_root}/.venv"',
    'test "${venv_root}" = "${GITHUB_WORKSPACE}/.venv"',
    'if [[ -L "${venv_root}" ]]; then',
    'test "$(realpath -e -- "${venv_root}")" = "${venv_root}"',
    'rm -rf -- "${venv_root}"',
    MANAGED_PYTHON_SYNC,
    'python_executable="$(realpath -e -- .venv/bin/python)"',
    '"${python_base_prefix}"/bin/python*)',
    'test "$(.venv/bin/python -I -c \'import sys; print(sys.implementation.name)\')" = "cpython"',
    "test \"$(.venv/bin/python -I -c 'import sys; "
    'print(".".join(map(str, sys.version_info[:3])))\')" = "3.13.14"',
    "printf 'UV_PYTHON_INSTALL_DIR=%s\\n' \"${managed_python_root}\"",
    "printf 'UV_MANAGED_PYTHON=1\\n'",
    "printf 'UV_PYTHON_DOWNLOADS=never\\n'",
    '>> "${GITHUB_ENV}"',
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
CONTAINER_MANAGED_ENV = frozenset(
    {
        '--env "UV_PYTHON_INSTALL_DIR=${repository_root}/.tools/python"',
        "--env UV_MANAGED_PYTHON=1",
        "--env UV_PYTHON_DOWNLOADS=never",
    }
)
REPOSITORY_MOUNT = '--volume "${repository_root}:${repository_root}:ro"'
ALLOWED_NETWORK_NONE_VOLUMES = frozenset(
    {
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
)
EXPECTED_NETWORK_NONE_INVOCATIONS = 6
EXPECTED_CONTROL_USER_MAPPINGS = 1
CONTROL_USER_OPTION = '--user "${host_uid}:${host_gid}"'
HOST_UID_DERIVATION = 'host_uid="$(id -u)"'
HOST_GID_DERIVATION = 'host_gid="$(id -g)"'
HOST_UID_VALIDATION = (
    '[[ -n "$host_uid" && "$host_uid" != *$\'\\n\'* && "$host_uid" =~ ^(0|[1-9][0-9]*)$ ]]'
)
HOST_GID_VALIDATION = (
    '[[ -n "$host_gid" && "$host_gid" != *$\'\\n\'* && "$host_gid" =~ ^(0|[1-9][0-9]*)$ ]]'
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
OFFLINE_DIAGNOSTIC_FORMAT = (
    '{"schema_version":"%s","source_commit_sha":"%s",'
    '"workflow_sha256":"%s","hosted_run_id":%d,"run_attempt":%d,'
    '"stage":"%s","overall_status":%d,"control_status":%d,'
    '"direct_status":%d,"child_status":%d,"artifact_retention_days":1}'
)
OFFLINE_DIAGNOSTIC_CONDITION = "if: ${{ always() && steps.offline_campaign.outcome == 'failure' }}"
OFFLINE_DIAGNOSTIC_ARTIFACT_NAME = (
    "name: phase6-offline-adversarial-diagnostic-${{ github.run_id }}-${{ github.run_attempt }}"
)
OFFLINE_DIAGNOSTIC_PATH = (
    "path: ${{ runner.temp }}/phase6-offline-adversarial/failure-diagnostic.json"
)
MAX_WORKFLOW_BYTES = 1_000_000
SUCCESS_DIAGNOSTIC = "phase6 source execution valid"
FAILURE_DIAGNOSTIC = "phase6 source execution invalid"

_KEY = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
_ACTION = re.compile(r"^\s*uses:\s*[^@\s]+@([0-9a-f]{40})(?:\s+#.*)?$", re.MULTILINE)
_SKILLSCOUT_ENTRY = re.compile(
    r"(?:(?:python|\.venv/bin/python)(?:\s+-I)?\s+-m\s+skillscout(?:\.[a-z0-9_]+)*\b|"
    r"^\s*(?:from|import)\s+skillscout(?:\.|\s|$))",
    re.MULTILINE,
)
_SKILLSCOUT_CLI_MARKER = re.compile(r"python\s+-m\s+skillscout\.cli\b")
_SKILLSCOUT_CLI_SUBCOMMAND = re.compile(
    r"python\s+-m\s+skillscout\.cli[ \t]+([a-z][a-z0-9-]*)(?=$|[ \t);])"
)
_TOOL_ENTRY = re.compile(r"\btools/[A-Za-z0-9_./-]+\.py\b")


class SourceExecutionError(ValueError):
    """A workflow is malformed or permits an untrusted execution source."""


class AuthoritativeStep(NamedTuple):
    workflow_path: str
    job_name: str
    step_name: str
    checkout_sha: str
    invocation_digest: str


class SourceExecutionResult(NamedTuple):
    workflow_paths: tuple[str, ...]
    authoritative_step_count: int
    authoritative_steps: tuple[AuthoritativeStep, ...]
    managed_python_job_count: int
    managed_python_version: str
    managed_python_root: str
    network_none_invocation_count: int
    control_user_mapping_count: int
    diagnostic_upload_count: int


class _Step(NamedTuple):
    name: str
    source: str
    run: str | None


class _Job(NamedTuple):
    name: str
    source: str
    steps: tuple[_Step, ...]


def _require(condition: bool) -> None:
    if not condition:
        raise SourceExecutionError(FAILURE_DIAGNOSTIC)


def _read(root: Path, relative: Path) -> str:
    path = root / relative
    payload = path.read_bytes()
    _require(0 < len(payload) <= MAX_WORKFLOW_BYTES)
    _require(b"\x00" not in payload)
    return payload.decode("utf-8", errors="strict")


def _direct_keys(
    lines: list[str],
    indent: int,
    *,
    first_item: bool = False,
    reject_unrecognized: bool = False,
) -> tuple[str, ...]:
    keys: list[str] = []
    prefix = " " * indent
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        _require(line.startswith(prefix))
        if len(line) - len(line.lstrip(" ")) != indent:
            continue
        tail = line[indent:]
        if first_item and tail.startswith("- "):
            tail = tail[2:]
        elif first_item and line.startswith(" " * (indent - 2) + "- "):
            tail = line[indent:]
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:\s*\S.*)?", tail)
        if match is None:
            if reject_unrecognized:
                _require(False)
            continue
        keys.append(match.group(1))
    _require(len(keys) == len(set(keys)))
    return tuple(keys)


def _step_from_lines(lines: list[str]) -> _Step:
    _require(bool(lines) and lines[0].startswith("      - "))
    normalized = ["        " + lines[0][8:], *lines[1:]]
    keys = _direct_keys(normalized, 8)
    _require("name" in keys)
    _require(("run" in keys) != ("uses" in keys))
    name_match = re.search(r"^\s{8}name:\s*(\S.*)$", "\n".join(normalized), re.MULTILINE)
    _require(name_match is not None)
    run: str | None = None
    run_index = next(
        (index for index, line in enumerate(normalized) if line == "        run: |"),
        None,
    )
    if "run" in keys:
        _require(run_index is not None)
        run_lines = normalized[run_index + 1 :]
        _require(bool(run_lines))
        _require(
            all(not line.strip() or len(line) - len(line.lstrip(" ")) >= 10 for line in run_lines)
        )
        run = "\n".join(line[10:] if line.strip() else "" for line in run_lines)
    return _Step(name=name_match.group(1).strip(), source="\n".join(lines), run=run)


def _job_from_lines(name: str, lines: list[str]) -> _Job:
    _require(_KEY.fullmatch(name) is not None)
    keys = _direct_keys(lines[1:], 4)
    _require("steps" in keys)
    steps_index = next(
        (index for index, line in enumerate(lines) if line == "    steps:"),
        None,
    )
    _require(steps_index is not None)
    step_groups: list[list[str]] = []
    for line in lines[steps_index + 1 :]:
        if line.startswith("      - "):
            step_groups.append([line])
        else:
            _require(bool(step_groups))
            step_groups[-1].append(line)
    steps = tuple(_step_from_lines(group) for group in step_groups)
    _require(bool(steps))
    return _Job(name=name, source="\n".join(lines), steps=steps)


def _direct_mapping(source: str, *, indent: int, name: str) -> dict[str, str]:
    """Read one flat, plain-key YAML mapping and reject every other syntax.

    This verifier deliberately does not deserialize untrusted workflow YAML.  These
    protected maps are a closed, scalar-only subset, so accepting quoted keys,
    aliases, merge keys, tags, or a nested value would create an authority bypass:
    GitHub would honor the addition while this line-oriented verifier ignored it.
    """

    lines = source.splitlines()
    header = " " * indent + name + ":"
    indexes = [index for index, line in enumerate(lines) if line == header]
    _require(len(indexes) == 1)
    values: dict[str, str] = {}
    child_prefix = " " * (indent + 2)
    for line in lines[indexes[0] + 1 :]:
        if line and len(line) - len(line.lstrip(" ")) <= indent:
            break
        if not line.strip():
            continue
        _require(line.startswith(child_prefix))
        _require(len(line) - len(line.lstrip(" ")) == indent + 2)
        tail = line[indent + 2 :]
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):\s*(\S.*)", tail)
        _require(match is not None)
        key, value = match.groups()
        _require(key not in values)
        values[key] = value
    return values


def _direct_scalar(source: str, *, indent: int, name: str) -> str:
    """Return one exact plain scalar from a closed protected mapping level.

    The caller compares this raw scalar to an expected literal.  That rules out
    YAML comments, quoted/tagged values, aliases, and other alternate syntax
    rather than treating a security-relevant substring in a comment as proof.
    """

    prefix = " " * indent + name + ":"
    lines = source.splitlines()
    matches = [line for line in lines if line.startswith(prefix)]
    _require(len(matches) == 1)
    value = matches[0][len(prefix) :]
    _require(value.startswith(" "))
    value = value[1:]
    _require(bool(value) and value == value.strip())
    return value


def _job_direct_keys(job: _Job) -> tuple[str, ...]:
    return _direct_keys(
        job.source.splitlines()[1:],
        4,
        reject_unrecognized=True,
    )


def _step_direct_keys(step: _Step) -> tuple[str, ...]:
    lines = step.source.splitlines()
    _require(bool(lines) and lines[0].startswith("      - "))
    normalized = ["        " + lines[0][8:], *lines[1:]]
    return _direct_keys(normalized, 8, reject_unrecognized=True)


def _parse_jobs(source: str) -> tuple[_Job, ...]:
    _require("\t" not in source and "\r" not in source)
    lines = source.splitlines()
    _require(sum(line == "jobs:" for line in lines) == 1)
    jobs_index = lines.index("jobs:")
    job_starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines[jobs_index + 1 :], jobs_index + 1):
        if line and not line.startswith(" "):
            break
        match = re.fullmatch(r"  ([a-z][a-z0-9_-]*):", line)
        if match:
            job_starts.append((index, match.group(1)))
    _require(bool(job_starts))
    names = tuple(name for _, name in job_starts)
    _require(len(names) == len(set(names)))
    jobs: list[_Job] = []
    for offset, (start, name) in enumerate(job_starts):
        end = job_starts[offset + 1][0] if offset + 1 < len(job_starts) else len(lines)
        jobs.append(_job_from_lines(name, lines[start:end]))
    return tuple(jobs)


def _closed_post_task2_workflow_sources(
    workflow_sources: tuple[tuple[Path, str, tuple[_Job, ...]], ...],
) -> None:
    """Bind every authoritative byte except the independently closed final job.

    The source parser intentionally recognizes a small YAML subset.  A per-job
    digest would leave root context and alternate YAML syntax outside that
    subset unbound.  Freeze each whole reviewed workflow instead, replacing
    only the final Environment-B job with a fixed sentinel because that job has
    its own exact structural and command closure.
    """

    observed: list[tuple[str, str]] = []
    for relative, source, jobs in workflow_sources:
        normalized = source
        if relative == Path(".github/workflows/phase6-acceptance.yml"):
            final = tuple(job for job in jobs if job.name == LIVE_AUTHORITY_JOB)
            _require(len(final) == 1)
            _require(source.count(final[0].source) == 1)
            normalized = source.replace(final[0].source, FINAL_LIVE_AUTHORITY_JOB_SENTINEL, 1)
        observed.append(
            (
                relative.as_posix(),
                hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            )
        )
    _require(tuple(observed) == EXPECTED_CLOSED_WORKFLOW_SOURCE_DIGESTS)


def _closed_phase6_root_context(source: str) -> None:
    """Close inherited workflow context before evaluating fresh-job boundaries.

    A root ``env`` or custom ``defaults.run.shell`` applies to the fresh jobs
    without appearing in their local source blocks.  This owned workflow uses
    a deliberately tiny root grammar so those inherited authorities cannot be
    smuggled in via quoted keys, aliases, comments, or an extra map.
    """

    lines = source.splitlines()
    root_keys: list[str] = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" "):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(\S.*))?", line)
        _require(match is not None)
        root_keys.append(match.group(1))
    _require(
        tuple(root_keys)
        == ("name", "on", "permissions", "concurrency", "defaults", "jobs")
    )
    _require(
        _direct_scalar(source, indent=0, name="name")
        == "Phase 6 adversarial MVP acceptance"
    )
    _require(_direct_mapping(source, indent=0, name="permissions") == {"contents": "read"})
    _require(
        _direct_mapping(source, indent=0, name="concurrency")
        == {
            "group": "skillscout-phase6-acceptance",
            "cancel-in-progress": "false",
        }
    )
    defaults_indexes = [index for index, line in enumerate(lines) if line == "defaults:"]
    _require(len(defaults_indexes) == 1)
    defaults_lines: list[str] = []
    for line in lines[defaults_indexes[0] + 1 :]:
        if line and not line.startswith(" "):
            break
        if line.strip() and not line.lstrip().startswith("#"):
            defaults_lines.append(line)
    _require(tuple(defaults_lines) == ("  run:", "    shell: bash"))


def _run_has_entry(run: str) -> bool:
    return _SKILLSCOUT_ENTRY.search(run) is not None or _TOOL_ENTRY.search(run) is not None


def _reject_forbidden_sources(source: str, jobs: tuple[_Job, ...]) -> None:
    lowered = source.casefold()
    for marker in (
        "pip install",
        "python -m pip",
        "download-artifact",
        "/releases/download",
        ".whl",
        "dist/",
        "uvx ",
        "uv tool ",
        "uv run --with",
        "working-directory:",
    ):
        _require(marker not in lowered)
    for line in source.splitlines():
        if "uses:" in line:
            _require(_ACTION.fullmatch(line) is not None)
        if "actions/checkout@" in line:
            _require(CHECKOUT in line)
        if "astral-sh/setup-uv@" in line:
            _require(SETUP_UV in line)
    for job in jobs:
        for step in job.steps:
            if step.run is None:
                continue
            run = step.run
            _require(re.search(r"(?m)^\s*(?:source|\.)\s+", run) is None)
            _require(re.search(r"(?m)^\s*(?:bash\s+\./|make\s+|alias\s+)", run) is None)
            _require(re.search(r"(?m)^\s*[A-Za-z_][A-Za-z0-9_]*\s*\(\)\s*\{", run) is None)
            _require(
                re.search(rf'(?m)^\s*[A-Za-z_][A-Za-z0-9_]*="{re.escape(LOCAL_LOCKED)}"', run)
                is None
            )
            _require(re.search(r"(?m)^\s*\$[A-Za-z_][A-Za-z0-9_]*\b", run) is None)
            _require(re.search(r"(?m)^\s*cd\s+/", run) is None)


def _recognized_entry(run: str) -> bool:
    lines = run.splitlines()
    heredoc_active = False
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(LOCAL_LOCKED + " ") and (
            " python -" in " " + stripped or " python tools/" in " " + stripped
        ):
            if re.search(r"<<'?PY'?", stripped):
                heredoc_active = True
            if "python -m skillscout" in stripped or "python tools/" in stripped:
                found = True
        if _SKILLSCOUT_ENTRY.search(line) or _TOOL_ENTRY.search(line):
            if (
                stripped.startswith(LOCAL_LOCKED + " ")
                or stripped.startswith(CAMPAIGN_RUNNER + " ")
                or stripped
                == f"handoff=\"$({LOCAL_LOCKED} python -m skillscout.cli prepare-fresh-lock-handoff)\""
                or heredoc_active
            ):
                found = True
            else:
                return False
        if heredoc_active and stripped == "PY":
            heredoc_active = False
    return found and not heredoc_active


def _static_skillscout_cli_subcommands(run: str) -> tuple[str, ...]:
    """Return only literal CLI subcommands, rejecting shell-built command words.

    The planned live recorder must be the sole route to a state write.  A quote,
    escape, or expansion in the subcommand word could execute the same command
    while evading a substring proof, so every visible ``skillscout.cli`` call is
    required to carry one plain static subcommand token.
    """

    markers = tuple(_SKILLSCOUT_CLI_MARKER.finditer(run))
    subcommands = tuple(_SKILLSCOUT_CLI_SUBCOMMAND.finditer(run))
    _require(len(markers) == len(subcommands))
    return tuple(match.group(1) for match in subcommands)


def _closed_action_step(
    step: _Step,
    *,
    action: str,
    with_values: dict[str, str],
    allowed_action_comment: str | None = None,
) -> bool:
    """Accept only one exact, plain-key action configuration.

    Actions execute before the workflow's shell guardrails.  The protected
    contract therefore treats their input maps as closed syntax, rather than
    accepting a required-looking substring that may be present in a comment.
    """

    if set(_step_direct_keys(step)) != {"name", "uses", "with"}:
        return False
    action_value = _direct_scalar(step.source, indent=8, name="uses")
    allowed_actions = {action}
    if allowed_action_comment is not None:
        allowed_actions.add(f"{action} # {allowed_action_comment}")
    return (
        action_value in allowed_actions
        and _direct_mapping(step.source, indent=8, name="with") == with_values
    )


def _checkout_is_closed(step: _Step) -> bool:
    return _closed_action_step(
        step,
        action=CHECKOUT,
        with_values={
            "ref": "${{ github.sha }}",
            "persist-credentials": "false",
        },
    )


def _authority_checkout_is_closed(step: _Step) -> bool:
    legacy_authority = _closed_action_step(
        step,
        action=CHECKOUT,
        with_values={
            "ref": "${{ env.PHASE6_AUTHORITY_STATE_COMMIT_SHA }}",
            "path": ".phase6-authority-state",
            "persist-credentials": "false",
        },
    )
    configured_preflight_authority = _closed_action_step(
        step,
        action=CHECKOUT,
        with_values={
            "repository": "${{ vars.SKILLSCOUT_STATE_REPOSITORY_FULL_NAME }}",
            "ref": "${{ env.PHASE6_AUTHORITY_STATE_COMMIT_SHA }}",
            "path": ".phase6-authority-state",
            "persist-credentials": "false",
            "token": "${{ github.token }}",
        },
    )
    verified_handoff = any(
        _closed_action_step(
            step,
            action=CHECKOUT,
            with_values=with_values,
        )
        for with_values in (
            {
                "repository": "${{ needs.live_authority_preflight.outputs.state_repository_full_name }}",
                "ref": "${{ needs.live_authority_preflight.outputs.authority_state_commit_sha }}",
                "path": ".phase6-authority-state",
                "persist-credentials": "false",
                "token": "''",
            },
            {
                "repository": "${{ needs.live_authority_preflight.outputs.state_repository_full_name }}",
                "ref": "${{ needs.live_authority_preflight.outputs.state_commit_sha }}",
                "path": ".phase6-campaign-state",
                "persist-credentials": "false",
                "token": "''",
            },
        )
    )
    return legacy_authority or configured_preflight_authority or verified_handoff


def _campaign_candidate_checkout_is_closed(step: _Step) -> bool:
    return _closed_action_step(
        step,
        action=CHECKOUT,
        with_values={
            "repository": "${{ vars.SKILLSCOUT_STATE_REPOSITORY_FULL_NAME }}",
            "ref": "skillscout-state",
            "path": ".phase6-campaign-state",
            "persist-credentials": "false",
            "token": "${{ github.token }}",
        },
    )


def _setup_is_closed(step: _Step) -> bool:
    return _closed_action_step(
        step,
        action=SETUP_UV,
        with_values={"version": "0.11.29", "enable-cache": "false"},
        allowed_action_comment="v9.0.0",
    )


def _materialization_is_closed(step: _Step) -> bool:
    if step.run is None:
        return False
    required = (
        "mkdir -p .tools/uv-0.11.29/bin",
        'install -m 0755 "$(command -v uv)" .tools/uv-0.11.29/bin/uv',
        "test -x .tools/uv-0.11.29/bin/uv",
        'uv_version_output="$(.tools/uv-0.11.29/bin/uv --version)"',
        (
            'if [[ "$uv_version_output" != "uv 0.11.29" && '
            '! "$uv_version_output" =~ ^uv\\ 0\\.11\\.29\\ \\([^()]+\\)$ ]]; then'
        ),
        "exit 1",
        "fi",
        *MANAGED_PYTHON_TOOLCHAIN,
    )
    return all(value in step.run for value in required)


def _fresh_materialization_is_exact(step: _Step) -> bool:
    """Require the pre-secret fresh-job toolchain block byte-for-byte.

    A substring check would allow an injected command to replace a required
    line with a comment, poisoning the local uv executable before a later step
    receives the state credential.
    """

    return (
        step.run is not None
        and hashlib.sha256(step.run.encode("utf-8")).hexdigest()
        == FRESH_MATERIALIZATION_RUN_SHA256
    )


def _python_runtime_preflight_is_closed(step: _Step) -> bool:
    return step.run is not None and all(value in step.run for value in PYTHON_BASE_PREFIX_PREFLIGHT)


def _closed_network_none_invocation_count(run: str) -> int:
    marker = "docker run --network none --rm \\"
    invocations = run.split(marker)[1:]
    for invocation in invocations:
        options, separator, _ = invocation.partition(LOCAL_LOCKED + " --offline --no-sync")
        if not separator:
            options, separator, _ = invocation.partition(CAMPAIGN_RUNNER)
        _require(bool(separator))
        volumes = {
            line.strip().removesuffix(" \\")
            for line in options.splitlines()
            if line.strip().startswith("--volume ")
        }
        container_environment = {
            line.strip().removesuffix(" \\")
            for line in options.splitlines()
            if line.strip().startswith("--env ")
        }
        _require(REPOSITORY_MOUNT in volumes)
        _require(volumes <= ALLOWED_NETWORK_NONE_VOLUMES)
        _require(CONTAINER_MANAGED_ENV <= container_environment)
    return len(invocations)


def _closed_control_user_mapping_count(jobs: tuple[_Job, ...]) -> int:
    offline_jobs = tuple(job for job in jobs if job.name == "offline_adversarial")
    _require(len(offline_jobs) == 1)
    campaign_steps = tuple(
        step
        for step in offline_jobs[0].steps
        if step.name == "Run the fresh kernel-isolated adversarial campaign"
    )
    _require(len(campaign_steps) == 1)
    campaign = campaign_steps[0].run
    _require(campaign is not None)
    for required in (
        HOST_UID_DERIVATION,
        HOST_GID_DERIVATION,
        HOST_UID_VALIDATION,
        HOST_GID_VALIDATION,
    ):
        _require(campaign.count(required) == 1)
    invocations = campaign.split("docker run --network none --rm \\")[1:]
    _require(len(invocations) == 3)
    mapping_count = 0
    for invocation in invocations:
        options, separator, _ = invocation.partition(f"{LOCAL_UV} run --locked --offline --no-sync")
        is_control = False
        if not separator:
            options, separator, _ = invocation.partition(CAMPAIGN_RUNNER)
            is_control = bool(separator)
        _require(bool(separator))
        user_options = tuple(
            line.strip().removesuffix(" \\")
            for line in options.splitlines()
            if line.strip().startswith("--user")
        )
        if is_control:
            _require(user_options == (CONTROL_USER_OPTION,))
            mapping_count += 1
        else:
            _require(not user_options)
    return mapping_count


def _closed_offline_diagnostic_upload_count(jobs: tuple[_Job, ...]) -> int:
    offline_jobs = tuple(job for job in jobs if job.name == "offline_adversarial")
    _require(len(offline_jobs) == 1)
    offline = offline_jobs[0]
    campaign_steps = tuple(
        step
        for step in offline.steps
        if step.name == "Run the fresh kernel-isolated adversarial campaign"
    )
    _require(len(campaign_steps) == 1)
    campaign_step = campaign_steps[0]
    _require(campaign_step.run is not None)
    _require(re.search(r"(?m)^\s+id: offline_campaign$", campaign_step.source) is not None)
    campaign = campaign_step.run
    format_matches = re.findall(
        r"(?m)^diagnostic_format='(\{.*\})\\n'$",
        campaign,
    )
    _require(format_matches == [OFFLINE_DIAGNOSTIC_FORMAT])
    _require(
        tuple(
            re.findall(
                r'(?m)^diagnostic_stage="([a-z-]+)"$',
                campaign,
            )
        )
        == OFFLINE_DIAGNOSTIC_STAGES
    )
    for required in (
        'diagnostic_path="${campaign_root}/failure-diagnostic.json"',
        'diagnostic_schema_version="phase6.offline-diagnostic.v1"',
        'diagnostic_workflow_sha256="absent"',
        "overall_status=1",
        "control_status=-1",
        "direct_status=-1",
        "child_status=-1",
        (
            'case "$diagnostic_stage" in '
            "runtime-preflight|control|direct-probe|child-probe|campaign-report|"
            "synthetic-scan|complete) ;;"
        ),
        "campaign_exit_status=$?",
        'overall_status="$campaign_exit_status"',
        'exit "$campaign_exit_status"',
        "diagnostic_write_status",
        'diagnostic_workflow_sha256="sha256:${PHASE6_WORKFLOW_SHA256}"',
        ('"$diagnostic_stage" = "control" && "$control_status" -ne 0 && -s "$diagnostic_path"'),
        (
            'if [[ "$campaign_exit_status" -ne 0 ]]; then '
            'exit "$campaign_exit_status"; fi; exit "$diagnostic_write_status"'
        ),
    ):
        _require(required in campaign)
    _require(campaign.count('printf "$diagnostic_format"') == 1)
    _require(campaign.count("diagnostic_path") == 3)
    _require(campaign.count("diagnostic_stage=") == len(OFFLINE_DIAGNOSTIC_STAGES))
    _require(campaign.count("diagnostic_workflow_sha256=") == 2)
    _require(campaign.count("overall_status=") == 3)
    _require(campaign.count("control_status=") == 2)
    _require(campaign.count("direct_status=") == 2)
    _require(campaign.count("child_status=") == 2)
    _require("continue-on-error" not in campaign_step.source)
    _require(campaign.index("diagnostic_format=") < campaign.index("python_base_prefix_output="))
    _require(CAMPAIGN_RUNNER in campaign)
    _require("pytest -q tests/test_phase6_adversarial.py" not in campaign)

    diagnostic_uploads = tuple(
        step
        for step in offline.steps
        if step.name == "Upload the bounded noncanonical campaign diagnostic"
    )
    _require(len(diagnostic_uploads) == 1)
    diagnostic_upload = diagnostic_uploads[0]
    _require(diagnostic_upload.run is None)
    for required in (
        OFFLINE_DIAGNOSTIC_CONDITION,
        f"uses: {UPLOAD_ARTIFACT}",
        OFFLINE_DIAGNOSTIC_ARTIFACT_NAME,
        OFFLINE_DIAGNOSTIC_PATH,
        "if-no-files-found: error",
        "retention-days: 1",
    ):
        _require(required in diagnostic_upload.source)
    lowered_upload = diagnostic_upload.source.casefold()
    for forbidden in (
        ".log",
        "offline-evidence",
        "state",
        "credential",
        "secret",
    ):
        _require(forbidden not in lowered_upload)

    evidence_uploads = tuple(
        step
        for step in offline.steps
        if step.name == "Upload the bounded noncanonical offline evidence"
    )
    _require(len(evidence_uploads) == 1)
    _require(re.search(r"(?m)^\s+if:", evidence_uploads[0].source) is None)
    upload_steps = tuple(
        step for step in offline.steps if "actions/upload-artifact@" in step.source
    )
    _require(len(upload_steps) == 2)
    return len(diagnostic_uploads)


def _fresh_campaign_jobs_are_closed(jobs: tuple[_Job, ...]) -> None:
    """Enforce trusted-source state routes and their separated approval handoff."""

    by_name = {job.name: job for job in jobs}
    _require(len(by_name) == len(jobs))
    _require({"prepare_fresh_campaign", "benchmark_lock"} <= set(by_name))
    prepare = by_name["prepare_fresh_campaign"]
    approval = by_name["benchmark_lock"]

    _require(
        set(_job_direct_keys(prepare))
        == {
            "name",
            "if",
            "environment",
            "runs-on",
            "timeout-minutes",
            "permissions",
            "env",
            "steps",
        }
    )
    _require(
        set(_job_direct_keys(approval))
        == {
            "name",
            "if",
            "environment",
            "runs-on",
            "timeout-minutes",
            "permissions",
            "env",
            "steps",
        }
    )
    _require(
        _direct_mapping(prepare.source, indent=4, name="permissions")
        == {"contents": "read"}
    )
    _require(
        _direct_mapping(approval.source, indent=4, name="permissions")
        == {"contents": "read", "actions": "read"}
    )
    job_environment = {
        "UV_LINK_MODE": "copy",
        "SKILLSCOUT_STATE_REPOSITORY_ID": "${{ vars.SKILLSCOUT_STATE_REPOSITORY_ID }}",
        "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME": "${{ vars.SKILLSCOUT_STATE_REPOSITORY_FULL_NAME }}",
    }
    _require(_direct_mapping(prepare.source, indent=4, name="env") == job_environment)
    _require(_direct_mapping(approval.source, indent=4, name="env") == job_environment)
    _require(
        _direct_scalar(prepare.source, indent=4, name="name")
        == "skillscout-phase6-prepare-fresh-campaign"
    )
    _require(
        _direct_scalar(prepare.source, indent=4, name="if")
        == "${{ inputs.phase6_action == 'prepare-fresh-campaign' && github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }}"
    )
    _require(
        _direct_scalar(prepare.source, indent=4, name="environment")
        == "phase6-fresh-nomination"
    )
    _require(_direct_scalar(prepare.source, indent=4, name="runs-on") == "ubuntu-24.04")
    _require(_direct_scalar(prepare.source, indent=4, name="timeout-minutes") == "30")
    _require(
        _direct_scalar(approval.source, indent=4, name="name")
        == "skillscout-phase6-benchmark-lock"
    )
    _require(
        _direct_scalar(approval.source, indent=4, name="if")
        == "${{ inputs.phase6_action == 'lock-fresh-campaign' && github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }}"
    )
    _require(
        _direct_scalar(approval.source, indent=4, name="environment")
        == "phase6-human-benchmark-lock"
    )
    _require(_direct_scalar(approval.source, indent=4, name="runs-on") == "ubuntu-24.04")
    _require(_direct_scalar(approval.source, indent=4, name="timeout-minutes") == "30")

    expected_prefix = (
        "Check out the dispatched commit",
        "Materialize the pinned uv binary",
        "Verify the repository-local locked toolchain",
    )
    _require(tuple(step.name for step in prepare.steps) == (*expected_prefix, "Prepare one bounded fresh Search nomination"))
    _require(
        tuple(step.name for step in approval.steps)
        == (
            *expected_prefix,
            "Verify and emit one environment-approved benchmark lock handoff",
            "Persist one verified environment-approved benchmark lock",
        )
    )
    for job in (prepare, approval):
        _require(
            tuple(_step_direct_keys(step) for step in job.steps[:3])
            == (("name", "uses", "with"), ("name", "uses", "with"), ("name", "run"))
        )
        _require(_checkout_is_closed(job.steps[0]))
        _require(_setup_is_closed(job.steps[1]))
        _require(_fresh_materialization_is_exact(job.steps[2]))

    prepare_step = prepare.steps[-1]
    approval_step = approval.steps[-2]
    persist_step = approval.steps[-1]
    _require(set(_step_direct_keys(prepare_step)) == {"name", "env", "run"})
    _require(set(_step_direct_keys(approval_step)) == {"name", "id", "env", "run"})
    _require(set(_step_direct_keys(persist_step)) == {"name", "env", "run"})
    _require(
        _direct_mapping(prepare_step.source, indent=8, name="env")
        == {
            "SKILLSCOUT_SOURCE_GITHUB_TOKEN": "${{ github.token }}",
            "SKILLSCOUT_STATE_GITHUB_TOKEN": "${{ secrets.SKILLSCOUT_FRESH_NOMINATION_STATE_GITHUB_TOKEN }}",
        }
    )
    _require(
        _direct_mapping(approval_step.source, indent=8, name="env")
        == {"GITHUB_TOKEN": "${{ github.token }}"}
    )
    _require(
        _direct_mapping(persist_step.source, indent=8, name="env")
        == {
            "SKILLSCOUT_STATE_GITHUB_TOKEN": "${{ secrets.SKILLSCOUT_BENCHMARK_LOCK_STATE_GITHUB_TOKEN }}",
            "PHASE6_FRESH_LOCK_HANDOFF": "${{ steps.prepare_handoff.outputs.fresh_lock_handoff }}",
        }
    )
    _require(
        tuple(prepare_step.run.splitlines())
        == (
            "set -euo pipefail",
            "umask 077",
            f"{LOCAL_LOCKED} python -m skillscout.cli prepare-fresh-campaign",
        )
    )
    _require(
        tuple(approval_step.run.splitlines())
        == (
            "set -euo pipefail",
            "umask 077",
            f"handoff=\"$({LOCAL_LOCKED} python -m skillscout.cli prepare-fresh-lock-handoff)\"",
            "[[ -n \"${handoff}\" && \"${handoff}\" != *$'\\n'* ]]",
            "printf 'fresh_lock_handoff=%s\\n' \"${handoff}\" >> \"${GITHUB_OUTPUT}\"",
        )
    )
    _require(
        tuple(persist_step.run.splitlines())
        == (
            "set -euo pipefail",
            "umask 077",
            f"{LOCAL_LOCKED} python -m skillscout.cli lock-fresh-campaign",
        )
    )
    for job in (prepare, approval):
        for forbidden in (
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
        ):
            _require(forbidden not in job.source.casefold())
    _require(
        all(
            "SKILLSCOUT_STATE_GITHUB_TOKEN" not in step.source
            for step in approval.steps[:-1]
        )
    )
    _require(re.search(r"(?m)^\s{10}GITHUB_TOKEN:", persist_step.source) is None)


def _closed_live_authority_job(job: _Job) -> None:
    """Accept only the planned environment-B, state-only V2 recorder route."""

    _require(job.name == LIVE_AUTHORITY_JOB)
    _require(
        set(_job_direct_keys(job))
        == {
            "name",
            "if",
            "environment",
            "runs-on",
            "timeout-minutes",
            "permissions",
            "env",
            "steps",
        }
    )
    _require(
        _direct_scalar(job.source, indent=4, name="name")
        == LIVE_AUTHORITY_ENVIRONMENT
    )
    _require(
        _direct_scalar(job.source, indent=4, name="if")
        == "${{ inputs.phase6_action == 'record-live-authority' && github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }}"
    )
    _require(
        _direct_scalar(job.source, indent=4, name="environment")
        == LIVE_AUTHORITY_ENVIRONMENT
    )
    _require(_direct_scalar(job.source, indent=4, name="runs-on") == "ubuntu-24.04")
    _require(_direct_scalar(job.source, indent=4, name="timeout-minutes") == "30")
    _require(
        _direct_mapping(job.source, indent=4, name="permissions")
        == {"contents": "read", "actions": "read"}
    )
    _require(
        _direct_mapping(job.source, indent=4, name="env")
        == {
            "UV_LINK_MODE": "copy",
            "SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID": "${{ vars.SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID }}",
            "SKILLSCOUT_STATE_REPOSITORY_ID": "${{ vars.SKILLSCOUT_STATE_REPOSITORY_ID }}",
            "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME": "${{ vars.SKILLSCOUT_STATE_REPOSITORY_FULL_NAME }}",
        }
    )

    expected_prefix = (
        "Check out the dispatched commit",
        "Materialize the pinned uv binary",
        "Verify the repository-local locked toolchain",
    )
    _require(
        tuple(step.name for step in job.steps)
        == (*expected_prefix, "Persist one environment-approved V2 live authority")
    )
    _require(
        tuple(_step_direct_keys(step) for step in job.steps[:3])
        == (("name", "uses", "with"), ("name", "uses", "with"), ("name", "run"))
    )
    _require(_checkout_is_closed(job.steps[0]))
    _require(_setup_is_closed(job.steps[1]))
    _require(_fresh_materialization_is_exact(job.steps[2]))

    persist = job.steps[-1]
    _require(set(_step_direct_keys(persist)) == {"name", "env", "run"})
    _require(
        _direct_mapping(persist.source, indent=8, name="env")
        == {
            "GITHUB_TOKEN": "${{ github.token }}",
            "SKILLSCOUT_STATE_GITHUB_TOKEN": f"${{{{ secrets.{LIVE_AUTHORITY_STATE_SECRET} }}}}",
        }
    )
    _require(
        persist.run is not None
        and tuple(persist.run.splitlines())
        == (
            "set -euo pipefail",
            "umask 077",
            f'{LOCAL_LOCKED} python -m skillscout.cli record-live-authority '
            '--acceptance-run-id "${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}"',
        )
    )
    for forbidden in (
        "live_authority_json",
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
    ):
        _require(forbidden not in job.source.casefold())
    _require(
        all(
            "SKILLSCOUT_STATE_GITHUB_TOKEN" not in step.source
            for step in job.steps[:-1]
        )
    )
    _require("SKILLSCOUT_SOURCE_GITHUB_TOKEN" not in job.source)


def _planned_live_authority_route_is_closed(source: str, jobs: tuple[_Job, ...]) -> bool:
    """Validate the required final Environment-B recorder route."""

    planned = tuple(job for job in jobs if job.name == LIVE_AUTHORITY_JOB)
    _require(len(planned) == 1)
    _require("live_authority_json" not in source.casefold())
    recorder_steps: list[tuple[_Job, _Step]] = []
    for job in jobs:
        for step in job.steps:
            if step.run is None:
                continue
            subcommands = _static_skillscout_cli_subcommands(step.run)
            if job != planned[0]:
                _require("record-live-authority" not in subcommands)
            if "record-live-authority" in subcommands:
                recorder_steps.append((job, step))
    _require(len(recorder_steps) == 1 and recorder_steps[0][0] == planned[0])
    _closed_live_authority_job(planned[0])
    return True


def verify_source_execution(repository_root: Path) -> SourceExecutionResult:
    root = Path(os.path.abspath(os.fspath(repository_root)))
    _require(root.is_dir())
    findings: list[AuthoritativeStep] = []
    managed_python_job_count = 0
    network_none_invocation_count = 0
    control_user_mapping_count = 0
    diagnostic_upload_count = 0
    planned_live_authority = False
    workflow_sources: list[tuple[Path, str, tuple[_Job, ...]]] = []
    for relative in WORKFLOW_PATHS:
        source = _read(root, relative)
        jobs = _parse_jobs(source)
        workflow_sources.append((relative, source, jobs))
        _reject_forbidden_sources(source, jobs)
        if relative == Path(".github/workflows/phase6-acceptance.yml"):
            _closed_phase6_root_context(source)
            diagnostic_upload_count += _closed_offline_diagnostic_upload_count(jobs)
            control_user_mapping_count += _closed_control_user_mapping_count(jobs)
            _fresh_campaign_jobs_are_closed(jobs)
            planned_live_authority = _planned_live_authority_route_is_closed(source, jobs)
        for job in jobs:
            checkout_indexes = tuple(
                index for index, step in enumerate(job.steps) if CHECKOUT in step.source
            )
            campaign_candidate_indexes = tuple(
                index
                for index, step in enumerate(job.steps)
                if _campaign_candidate_checkout_is_closed(step)
            )
            if job.name == "live_authority_preflight":
                authority_verification_indexes = tuple(
                    index
                    for index, step in enumerate(job.steps)
                    if step.run is not None
                    and "python -m skillscout.cli verify-live-authority" in step.run
                )
                resume_resolution_indexes = tuple(
                    index
                    for index, step in enumerate(job.steps)
                    if step.run is not None
                    and "python -m skillscout.cli resolve-acceptance-resume" in step.run
                )
                _require(
                    len(authority_verification_indexes)
                    == len(campaign_candidate_indexes)
                    == len(resume_resolution_indexes)
                    == 1
                )
                _require(
                    authority_verification_indexes[0]
                    < campaign_candidate_indexes[0]
                    < resume_resolution_indexes[0]
                )
            else:
                _require(not campaign_candidate_indexes)
            setup_indexes = tuple(
                index for index, step in enumerate(job.steps) if SETUP_UV in step.source
            )
            materialization_indexes = tuple(
                index for index, step in enumerate(job.steps) if _materialization_is_closed(step)
            )
            _require(len(materialization_indexes) == 1)
            managed_python_job_count += 1
            for index, step in enumerate(job.steps):
                if step.run is not None:
                    invocation_count = _closed_network_none_invocation_count(step.run)
                    if invocation_count:
                        _require(_python_runtime_preflight_is_closed(step))
                        network_none_invocation_count += invocation_count
                if step.run is None or not _run_has_entry(step.run):
                    continue
                _require(_recognized_entry(step.run))
                earlier_checkout = tuple(item for item in checkout_indexes if item < index)
                earlier_setup = tuple(item for item in setup_indexes if item < index)
                earlier_materialization = tuple(
                    item for item in materialization_indexes if item < index
                )
                _require(bool(earlier_checkout and earlier_setup and earlier_materialization))
                source_checkouts = tuple(
                    item
                    for item in earlier_checkout
                    if _checkout_is_closed(job.steps[item])
                )
                _require(bool(source_checkouts))
                checkout_step = job.steps[source_checkouts[-1]]
                setup_step = job.steps[earlier_setup[-1]]
                _require(_checkout_is_closed(checkout_step))
                _require(
                    all(
                        _checkout_is_closed(job.steps[item])
                        or _authority_checkout_is_closed(job.steps[item])
                        or (
                            job.name == "live_authority_preflight"
                            and _campaign_candidate_checkout_is_closed(job.steps[item])
                        )
                        for item in earlier_checkout
                    )
                )
                _require(_setup_is_closed(setup_step))
                _require(
                    source_checkouts[-1]
                    < earlier_setup[-1]
                    < earlier_materialization[-1]
                    < index
                )
                findings.append(
                    AuthoritativeStep(
                        workflow_path=relative.as_posix(),
                        job_name=job.name,
                        step_name=step.name,
                        checkout_sha=CHECKOUT_SHA,
                        invocation_digest=hashlib.sha256(step.run.encode("utf-8")).hexdigest(),
                    )
                )
    _closed_post_task2_workflow_sources(tuple(workflow_sources))
    _require(bool(findings))
    _require(planned_live_authority)
    _require(managed_python_job_count == 17)
    _require(network_none_invocation_count == EXPECTED_NETWORK_NONE_INVOCATIONS)
    _require(control_user_mapping_count == EXPECTED_CONTROL_USER_MAPPINGS)
    _require(diagnostic_upload_count == 1)
    return SourceExecutionResult(
        workflow_paths=tuple(path.as_posix() for path in WORKFLOW_PATHS),
        authoritative_step_count=len(findings),
        authoritative_steps=tuple(findings),
        managed_python_job_count=managed_python_job_count,
        managed_python_version=MANAGED_PYTHON_VERSION,
        managed_python_root=MANAGED_PYTHON_ROOT,
        network_none_invocation_count=network_none_invocation_count,
        control_user_mapping_count=control_user_mapping_count,
        diagnostic_upload_count=diagnostic_upload_count,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repository-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        root = Path(__file__).resolve().parents[1]
        if arguments:
            namespace = _parser().parse_args(arguments)
            _require(namespace.repository_root is not None)
            root = namespace.repository_root
        verify_source_execution(root)
    except (
        SourceExecutionError,
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        AttributeError,
        SystemExit,
    ):
        print(FAILURE_DIAGNOSTIC, file=sys.stderr)
        return 1
    print(SUCCESS_DIAGNOSTIC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
