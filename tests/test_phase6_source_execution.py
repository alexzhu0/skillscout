"""Wave-0 RED contract for the closed four-workflow source-execution verifier."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
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
UPLOAD_ARTIFACT = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
MANAGED_PYTHON_VERSION = "3.13.14"
MANAGED_PYTHON_ROOT = "${GITHUB_WORKSPACE}/.tools/python"
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
CONTAINER_MANAGED_ENV = (
    '--env "UV_PYTHON_INSTALL_DIR=${repository_root}/.tools/python"',
    "--env UV_MANAGED_PYTHON=1",
    "--env UV_PYTHON_DOWNLOADS=never",
)
REPOSITORY_MOUNT = '--volume "${repository_root}:${repository_root}:ro"'
CONTROL_USER_OPTION = '--user "${host_uid}:${host_gid}"'
LIVE_AUTHORITY_ENVIRONMENT = "skillscout-phase6-live-authority"
LIVE_AUTHORITY_STATE_SECRET = "SKILLSCOUT_LIVE_AUTHORITY_STATE_GITHUB_TOKEN"
LIVE_AUTHORITY_JOB_NAME = "record_live_authority"


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


def _replace_live_authority_route(path: Path, old: str, new: str) -> None:
    module = _module()
    source = path.read_text(encoding="utf-8")
    job = next(
        job
        for job in module._parse_jobs(source)
        if job.name == LIVE_AUTHORITY_JOB_NAME
    )
    assert job.source.count(old) == 1
    replacement = job.source.replace(old, new, 1)
    assert source.count(job.source) == 1
    path.write_text(source.replace(job.source, replacement, 1), encoding="utf-8")


def _replace_phase6_job(path: Path, name: str, old: str, new: str) -> None:
    module = _module()
    source = path.read_text(encoding="utf-8")
    job = next(job for job in module._parse_jobs(source) if job.name == name)
    assert job.source.count(old) == 1
    replacement = job.source.replace(old, new, 1)
    assert source.count(job.source) == 1
    path.write_text(source.replace(job.source, replacement, 1), encoding="utf-8")


def _remove_phase6_job(path: Path, name: str) -> None:
    module = _module()
    source = path.read_text(encoding="utf-8")
    job = next(job for job in module._parse_jobs(source) if job.name == name)
    assert source.count(job.source) == 1
    path.write_text(source.replace(job.source, "", 1), encoding="utf-8")


def _version_guards(repository: Path) -> tuple[str, ...]:
    module = _module()
    guards: list[str] = []
    for relative in WORKFLOW_PATHS:
        source = (repository / relative).read_text(encoding="utf-8")
        for job in module._parse_jobs(source):
            for step in job.steps:
                if step.name != "Verify the repository-local locked toolchain":
                    continue
                assert step.run is not None
                lines = step.run.splitlines()
                start = lines.index("test -x .tools/uv-0.11.29/bin/uv") + 1
                end = lines.index("fi", start) + 1
                guards.append("\n".join(lines[start:end]))
    return tuple(guards)


def _run_guard(repository: Path, guard: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + guard],
        cwd=repository,
        text=True,
        capture_output=True,
        check=False,
    )


def _fresh_toolchain_fragment(repository: Path) -> str:
    module = _module()
    fragments: list[str] = []
    for relative in WORKFLOW_PATHS:
        source = (repository / relative).read_text(encoding="utf-8")
        for job in module._parse_jobs(source):
            materialization = tuple(
                step
                for step in job.steps
                if step.name == "Verify the repository-local locked toolchain"
            )
            assert len(materialization) == 1
            run = materialization[0].run
            assert run is not None
            lines = run.splitlines()
            start = lines.index('venv_root="${repository_root}/.venv"')
            end = lines.index(MANAGED_PYTHON_SYNC, start) + 1
            fragments.append("\n".join(lines[start:end]))
    assert len(fragments) == 17
    assert len(set(fragments)) == 1
    return fragments[0]


def _copy_fresh_control_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "fresh-control-repository"
    repository.mkdir()
    for filename in ("pyproject.toml", "uv.lock"):
        shutil.copy2(ROOT / filename, repository / filename)
    shutil.copytree(ROOT / "src", repository / "src")
    tests = repository / "tests"
    tests.mkdir()
    shutil.copy2(ROOT / "tests/conftest.py", tests / "conftest.py")
    shutil.copy2(
        ROOT / "tests/test_phase6_adversarial.py",
        tests / "test_phase6_adversarial.py",
    )
    for fixture_directory in ("acceptance", "injection"):
        shutil.copytree(
            ROOT / "tests/fixtures" / fixture_directory,
            tests / "fixtures" / fixture_directory,
        )
    local_uv = repository / ".tools/uv-0.11.29/bin/uv"
    local_uv.parent.mkdir(parents=True)
    shutil.copy2(ROOT / ".tools/uv-0.11.29/bin/uv", local_uv)
    local_uv.chmod(0o755)
    return repository


def _initialize_fresh_control_runtime(
    repository: Path,
    fragment: str,
) -> subprocess.CompletedProcess[str]:
    stale_venv = repository / ".venv"
    stale_venv.mkdir(exist_ok=True)
    stale_marker = stale_venv / "preexisting-environment"
    stale_marker.write_text("must be removed\n", encoding="utf-8")
    shim_root = repository / ".test-bin"
    shim_root.mkdir(exist_ok=True)
    realpath_shim = shim_root / "realpath"
    realpath_shim.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = "-e" ]; then shift; fi\n'
        'if [ "${1:-}" = "--" ]; then shift; fi\n'
        'exec "${PHASE6_TEST_REALPATH}" "$@"\n',
        encoding="utf-8",
    )
    realpath_shim.chmod(0o755)
    system_realpath = shutil.which("realpath")
    assert system_realpath is not None
    environment = {
        **os.environ,
        "GITHUB_WORKSPACE": str(repository),
        "PATH": str(shim_root) + os.pathsep + os.environ["PATH"],
        "PHASE6_TEST_REALPATH": system_realpath,
        "PYTHONDONTWRITEBYTECODE": "1",
        "UV_LINK_MODE": "copy",
        "UV_OFFLINE": "1",
        "managed_python_executable": str(Path(sys.executable).resolve()),
        "managed_python_root": str(Path(sys.base_prefix).resolve().parent),
        "repository_root": str(repository),
    }
    environment.pop("VIRTUAL_ENV", None)
    deletion_fragment, sync_command = fragment.rsplit("\n", 1)
    deletion = subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + deletion_fragment],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert deletion.returncode == 0, deletion.stderr
    assert not stale_marker.exists()
    assert not stale_venv.exists()

    create_venv = subprocess.run(
        [
            str(repository / ".tools/uv-0.11.29/bin/uv"),
            "venv",
            "--prompt",
            "skillscout",
            "--python",
            environment["managed_python_executable"],
            "--managed-python",
            "--no-python-downloads",
        ],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert create_venv.returncode == 0, create_venv.stderr
    source_site_packages = tuple((ROOT / ".venv/lib").glob("python3.*/site-packages"))
    destination_site_packages = tuple((stale_venv / "lib").glob("python3.*/site-packages"))
    assert len(source_site_packages) == len(destination_site_packages) == 1
    for installed_path in source_site_packages[0].iterdir():
        if installed_path.name == "skillscout.pth" or (
            installed_path.name.startswith("skillscout-")
            and installed_path.name.endswith(".dist-info")
        ):
            continue
        destination = destination_site_packages[0] / installed_path.name
        if installed_path.is_dir():
            shutil.copytree(installed_path, destination, symlinks=True)
        else:
            shutil.copy2(installed_path, destination, follow_symlinks=False)
    assert not (destination_site_packages[0] / "skillscout.pth").exists()
    assert not tuple(destination_site_packages[0].glob("skillscout-*.dist-info"))

    sync = subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + sync_command],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert sync.returncode == 0, sync.stderr
    return sync


def _run_fresh_control_import(repository: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(repository / ".venv/bin/python"),
            "-I",
            "-c",
            "import skillscout.application.acceptance",
        ],
        cwd=repository,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_fresh_control_test(repository: Path) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "UV_OFFLINE": "1",
    }
    environment.pop("VIRTUAL_ENV", None)
    return subprocess.run(
        [
            str(repository / ".tools/uv-0.11.29/bin/uv"),
            "run",
            "--locked",
            "--offline",
            "--no-sync",
            "python",
            "-m",
            "pytest",
            "-q",
            "tests/test_phase6_adversarial.py::"
            "test_required_phase6_adversarial_contract_is_missing",
            "-p",
            "no:cacheprovider",
        ],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


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


def test_source_execution_verifier_requires_repo_managed_cpython_for_every_job(
    tmp_path: Path,
) -> None:
    module = _module()
    result = module.verify_source_execution(_copy_workflows(tmp_path))
    assert result.managed_python_job_count == 17
    assert result.managed_python_version == MANAGED_PYTHON_VERSION
    assert result.managed_python_root == MANAGED_PYTHON_ROOT
    assert result.network_none_invocation_count == 6


def test_source_execution_fixture_accepts_protected_live_authority_route(
    tmp_path: Path,
) -> None:
    """The final V2 route is a closed state-only checkout-local command."""

    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")

    module._planned_live_authority_route_is_closed(
        path.read_text(encoding="utf-8"),
        module._parse_jobs(path.read_text(encoding="utf-8")),
    )


def test_source_execution_verifier_accepts_protected_authority_route(
    tmp_path: Path,
) -> None:
    """The final route joins the all-workflow source proof."""

    module = _module()
    repository = _copy_workflows(tmp_path)

    result = module.verify_source_execution(repository)

    assert result.managed_python_job_count == 17
    assert any(step.job_name == LIVE_AUTHORITY_JOB_NAME for step in result.authoritative_steps)


def test_source_execution_verifier_requires_final_live_authority_job(
    tmp_path: Path,
) -> None:
    """The post-Task2 source proof has no transitional 16-job route."""

    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")
    _remove_phase6_job(path, LIVE_AUTHORITY_JOB_NAME)

    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ("shell: bash", "shell: bash -e {0}"),
        (
            "defaults:\n  run:\n    shell: bash",
            "env:\n"
            "  SKILLSCOUT_STATE_GITHUB_TOKEN: "
            "${{ secrets.SKILLSCOUT_LIVE_AUTHORITY_STATE_GITHUB_TOKEN }}\n"
            "defaults:\n  run:\n    shell: bash",
        ),
    ),
    ids=("root-shell", "root-state-env"),
)
def test_source_execution_verifier_binds_non_phase6_workflow_root_bytes(
    tmp_path: Path,
    needle: str,
    replacement: str,
) -> None:
    """Unparsed root context cannot add shell or credential authority."""

    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/discover.yml")
    source = path.read_text(encoding="utf-8")
    assert source.count(needle) == 1
    path.write_text(source.replace(needle, replacement, 1), encoding="utf-8")

    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


def test_source_execution_verifier_rejects_unparsed_quoted_live_recorder_job(
    tmp_path: Path,
) -> None:
    """A quoted YAML job ID cannot evade the exclusive recorder closure."""

    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")
    source = path.read_text(encoding="utf-8")
    final = next(
        job for job in module._parse_jobs(source) if job.name == LIVE_AUTHORITY_JOB_NAME
    )
    hidden_job = final.source.replace(
        f"  {LIVE_AUTHORITY_JOB_NAME}:\n",
        '  "shadow_live_authority":\n',
        1,
    ).replace(
        f"{LOCAL_LOCKED} python -m skillscout.cli record-live-authority ",
        f"{LOCAL_LOCKED} .venv/bin/py''thon -m skillscout.cli record-live''-authority ",
        1,
    )
    assert hidden_job != final.source
    assert source.count("jobs:\n") == 1
    path.write_text(
        source.replace("jobs:\n", "jobs:\n" + hidden_job + "\n\n", 1),
        encoding="utf-8",
    )

    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


@pytest.mark.parametrize(
    "obfuscated_subcommand",
    ("record-live''-authority", "record-live\\-authority"),
)
def test_source_execution_rejects_obfuscated_recorder_outside_dedicated_job(
    tmp_path: Path,
    obfuscated_subcommand: str,
) -> None:
    """A shell-concatenated recorder name cannot bypass the dedicated route."""

    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")
    source = path.read_text(encoding="utf-8")
    needle = '          test -s "$result_file"\n      - name: Upload the bounded nomination result\n'
    replacement = (
        '          test -s "$result_file"\n'
        f"          {LOCAL_LOCKED} python -m skillscout.cli {obfuscated_subcommand} "
        '--acceptance-run-id "${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}"\n'
        "      - name: Upload the bounded nomination result\n"
    )
    assert source.count(needle) == 1
    path.write_text(source.replace(needle, replacement, 1), encoding="utf-8")

    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


@pytest.mark.parametrize(
    "shell_built_recorder",
    (
        '.venv/bin/py\\thon -m skillscout.cli record-live\\-authority '
        '--acceptance-run-id "${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}"',
        "$(printf '%s' .venv/bin/py)thon -m skillscout.cli record-live''-authority "
        '--acceptance-run-id "${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}"',
        "eval .venv/bin/py''thon -m skillscout.cli record-live''-authority "
        '--acceptance-run-id "${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}"',
        "printf 'ignored\\n' | .venv/bin/py''thon -m skillscout.cli "
        "record-live''-authority "
        '--acceptance-run-id "${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}"',
    ),
    ids=("escaped", "command-substitution", "eval", "pipe"),
)
def test_source_execution_rejects_shell_built_live_recorder_outside_environment_b(
    tmp_path: Path,
    shell_built_recorder: str,
) -> None:
    """A non-final state-writer job cannot add an unparsed shell recorder."""

    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")
    needle = '          test -f "$PHASE6_ATTESTATION"\n'
    replacement = f"{needle}          {shell_built_recorder}\n"
    _replace_phase6_job(path, "human_attestation", needle, replacement)

    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


def test_source_execution_rejects_human_if_comment_spoof_with_live_recorder(
    tmp_path: Path,
) -> None:
    """A comment cannot stand in for the human-only action gate."""

    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")
    _replace_phase6_job(
        path,
        "human_attestation",
        "    if: ${{ inputs.phase6_action == 'record-human-review' }}",
        "    if: ${{ inputs.phase6_action == format('{0}{1}', 'record-live-', 'authority') }}\n"
        "    # if: ${{ inputs.phase6_action == 'record-human-review' }}",
    )
    _replace_phase6_job(
        path,
        "human_attestation",
        '          test -f "$PHASE6_ATTESTATION"\n',
        '          test -f "$PHASE6_ATTESTATION"\n'
        "          .venv/bin/py''thon -m skillscout.cli record-live''-authority "
        '--acceptance-run-id "${SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID:?}"\n',
    )

    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


@pytest.mark.parametrize(
    ("mutation", "old", "new"),
    (
        (
            "alternate_command",
            "skillscout.cli record-live-authority --acceptance-run-id ",
            "skillscout.cli run-acceptance --action benchmark ",
        ),
        (
            "permission_widening",
            "      contents: read\n      actions: read",
            "      contents: write",
        ),
        (
            "actor_gate",
            "github.ref == 'refs/heads/main' }}",
            "github.ref == 'refs/heads/main' && github.actor == 'alexzhu0' }}",
        ),
        (
            "free_authority_json",
            "      SKILLSCOUT_STATE_REPOSITORY_FULL_NAME: ${{ vars.SKILLSCOUT_STATE_REPOSITORY_FULL_NAME }}",
            "      SKILLSCOUT_STATE_REPOSITORY_FULL_NAME: ${{ vars.SKILLSCOUT_STATE_REPOSITORY_FULL_NAME }}\n"
            "      PHASE6_LIVE_AUTHORITY_JSON: ${{ inputs.live_authority_json }}",
        ),
        (
            "wrong_environment",
            f"    environment: {LIVE_AUTHORITY_ENVIRONMENT}",
            "    environment: phase6-human-benchmark-lock",
        ),
        (
            "approval_reader_drift",
            "          GITHUB_TOKEN: ${{ github.token }}",
            "          GITHUB_TOKEN: ${{ vars.UNRELATED_TOKEN }}",
        ),
        (
            "state_secret_drift",
            f"${{{{ secrets.{LIVE_AUTHORITY_STATE_SECRET} }}}}",
            "${{ secrets.SKILLSCOUT_STATE_GITHUB_TOKEN }}",
        ),
        (
            "checkout_ref_drift",
            "          ref: ${{ github.sha }}",
            "          ref: attacker-ref",
        ),
    ),
)
def test_source_execution_fixture_rejects_protected_live_authority_mutations(
    tmp_path: Path,
    mutation: str,
    old: str,
    new: str,
) -> None:
    """Each mutation broadens or substitutes authority in the final route."""

    del mutation
    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")
    _replace_live_authority_route(path, old, new)
    source = path.read_text(encoding="utf-8")

    with pytest.raises(module.SourceExecutionError):
        module._planned_live_authority_route_is_closed(
            source,
            module._parse_jobs(source),
        )


def test_fresh_locked_toolchain_installs_project_for_phase6_control_runtime(
    tmp_path: Path,
) -> None:
    repository = _copy_fresh_control_repository(tmp_path)
    fragment = _fresh_toolchain_fragment(ROOT)

    _initialize_fresh_control_runtime(repository, fragment)
    import_result = _run_fresh_control_import(repository)
    assert import_result.returncode == 0, import_result.stderr
    control_result = _run_fresh_control_test(repository)
    assert control_result.returncode == 0, control_result.stderr

    no_project_fragment = fragment.replace(
        " sync --locked ",
        " sync --locked --no-install-project ",
        1,
    )
    assert no_project_fragment != fragment
    _initialize_fresh_control_runtime(repository, no_project_fragment)
    mutated_import = _run_fresh_control_import(repository)
    assert mutated_import.returncode == 1
    assert "ModuleNotFoundError" in mutated_import.stderr
    mutated_control = _run_fresh_control_test(repository)
    assert mutated_control.returncode == 1


def test_source_execution_verifier_requires_one_failure_only_diagnostic_upload(
    tmp_path: Path,
) -> None:
    module = _module()
    result = module.verify_source_execution(_copy_workflows(tmp_path))
    assert getattr(result, "diagnostic_upload_count", 0) == 1


def test_source_execution_verifier_binds_one_control_container_to_host_numeric_identity(
    tmp_path: Path,
) -> None:
    module = _module()
    result = module.verify_source_execution(_copy_workflows(tmp_path))
    assert getattr(result, "control_user_mapping_count", 0) == 1


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ('host_uid="$(id -u)"', 'host_uid="0"'),
        ('host_gid="$(id -g)"', 'host_gid="0"'),
        (CONTROL_USER_OPTION, '--user "0:0"'),
        (CONTROL_USER_OPTION, ""),
        (CONTROL_USER_OPTION, CONTROL_USER_OPTION + " \\\n            " + CONTROL_USER_OPTION),
        (CONTROL_USER_OPTION, '--user "$(id -u):$(id -g)"'),
    ),
)
def test_source_execution_verifier_rejects_control_user_mapping_mutations(
    tmp_path: Path,
    needle: str,
    replacement: str,
) -> None:
    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")
    source = path.read_text(encoding="utf-8")
    assert needle in source
    path.write_text(source.replace(needle, replacement, 1), encoding="utf-8")
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


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
        (
            "failure-diagnostic.json\n"
            "          if-no-files-found: error\n"
            "          retention-days: 1",
            "failure-diagnostic.json\n"
            "          if-no-files-found: error\n"
            "          retention-days: 2",
        ),
        (
            "Upload the bounded noncanonical campaign diagnostic\n"
            "        if: ${{ always() && steps.offline_campaign.outcome == 'failure' }}\n"
            f"        uses: {UPLOAD_ARTIFACT}",
            "Upload the bounded noncanonical campaign diagnostic\n"
            "        if: ${{ always() && steps.offline_campaign.outcome == 'failure' }}\n"
            "        uses: actions/upload-artifact@main",
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
def test_source_execution_verifier_rejects_diagnostic_mutations(
    tmp_path: Path,
    needle: str,
    replacement: str,
) -> None:
    module = _module()
    repository = _copy_workflows(tmp_path)
    _replace_first(repository, needle, replacement)
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        (MANAGED_PYTHON_INSTALL, MANAGED_PYTHON_INSTALL.replace("3.13.14", "3.13.13")),
        (
            MANAGED_PYTHON_INSTALL,
            MANAGED_PYTHON_INSTALL.replace(
                ' --install-dir "${managed_python_root}"',
                "",
            ),
        ),
        (
            'managed_python_root="${tools_root}/python"',
            'managed_python_root="${RUNNER_TOOL_CACHE}/Python"',
        ),
        (
            'managed_python_root="${tools_root}/python"',
            'managed_python_root="${HOME}/.local/share/uv/python"',
        ),
        (
            'managed_python_root="${tools_root}/python"',
            'managed_python_root="/usr/local/python"',
        ),
        (
            'managed_python_root="${tools_root}/python"',
            'managed_python_root="${GITHUB_WORKSPACE}/../python"',
        ),
        (
            'test "${managed_python_root}" = "${GITHUB_WORKSPACE}/.tools/python"',
            ":",
        ),
        ('if [[ -L "${managed_python_root}" ]]; then', "if false; then"),
        (
            MANAGED_PYTHON_INSTALL,
            MANAGED_PYTHON_INSTALL.replace("UV_MANAGED_PYTHON=1 ", ""),
        ),
        (
            MANAGED_PYTHON_SYNC,
            MANAGED_PYTHON_SYNC.replace(
                '--python "${managed_python_executable}"',
                "--python /usr/bin/python3",
            ),
        ),
        (
            MANAGED_PYTHON_SYNC,
            MANAGED_PYTHON_SYNC.replace("UV_MANAGED_PYTHON=1 ", ""),
        ),
        (
            MANAGED_PYTHON_INSTALL,
            MANAGED_PYTHON_INSTALL.replace("3.13.14", "3.13"),
        ),
    ),
)
def test_source_execution_verifier_rejects_managed_python_mutations(
    tmp_path: Path,
    needle: str,
    replacement: str,
) -> None:
    module = _module()
    repository = _copy_workflows(tmp_path)
    _replace_first(repository, needle, replacement)
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


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
        '--volume "${repository_root}:/workspace:ro"',
    ),
)
def test_source_execution_verifier_rejects_external_runtime_and_broad_mounts(
    tmp_path: Path,
    replacement: str,
) -> None:
    module = _module()
    repository = _copy_workflows(tmp_path)
    _replace_first(repository, REPOSITORY_MOUNT, replacement)
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        (CONTAINER_MANAGED_ENV[0], '--env "UV_PYTHON_INSTALL_DIR=/usr/local/python"'),
        (CONTAINER_MANAGED_ENV[1], "--env UV_MANAGED_PYTHON=0"),
        (CONTAINER_MANAGED_ENV[2], "--env UV_PYTHON_DOWNLOADS=automatic"),
    ),
)
def test_source_execution_verifier_rejects_unmanaged_container_runtime(
    tmp_path: Path,
    needle: str,
    replacement: str,
) -> None:
    module = _module()
    repository = _copy_workflows(tmp_path)
    _replace_first(repository, needle, replacement)
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


def test_toolchain_version_guard_accepts_official_metadata_and_rejects_invalid_versions(
    tmp_path: Path,
) -> None:
    guards = _version_guards(ROOT)
    assert len(guards) == 17
    assert all(_run_guard(ROOT, guard).returncode == 0 for guard in guards)

    fake_repository = tmp_path / "repository"
    fake_uv = fake_repository / ".tools/uv-0.11.29/bin/uv"
    fake_uv.parent.mkdir(parents=True)
    fake_uv.write_text("#!/bin/sh\nprintf '%s\\n' 'uv 0.11.29'\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    assert all(_run_guard(fake_repository, guard).returncode == 0 for guard in guards)

    for output in (
        "uvx 0.11.29",
        "uv 0.11.28 (901092ee1 2026-07-15 aarch64-apple-darwin)",
        "uv",
        "uv 0.11.29 malformed",
    ):
        fake_uv.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\n", encoding="utf-8")
        fake_uv.chmod(0o755)
        assert all(_run_guard(fake_repository, guard).returncode != 0 for guard in guards)


@pytest.mark.parametrize(
    ("mutation", "needle", "replacement"),
    (
        ("missing_checkout", CHECKOUT, "name: checkout omitted"),
        ("non_full_sha_checkout", CHECKOUT, "actions/checkout@main"),
        (
            "non_root_checkout",
            "persist-credentials: false",
            "persist-credentials: false\n          path: external",
        ),
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
        (
            "alias",
            LOCAL_LOCKED,
            "alias run_skillscout='" + LOCAL_LOCKED + "'\n          run_skillscout",
        ),
        (
            "function",
            LOCAL_LOCKED,
            "run_skillscout() { " + LOCAL_LOCKED + "; }\n          run_skillscout",
        ),
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


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        (
            "skillscout.cli lock-fresh-campaign",
            "skillscout.cli run-acceptance --action benchmark",
        ),
        (
            "environment: phase6-human-benchmark-lock",
            "environment: unprotected-environment",
        ),
        (
            "environment: phase6-human-benchmark-lock",
            "environment: unprotected-environment # phase6-human-benchmark-lock",
        ),
        (
            "if: ${{ inputs.phase6_action == 'lock-fresh-campaign' && github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }}",
            "if: ${{ inputs.phase6_action == 'lock-fresh-campaign' && github.repository == 'alexzhu0/skillscout' }}",
        ),
        (
            "if: ${{ inputs.phase6_action == 'lock-fresh-campaign' && github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }}",
            "if: ${{ inputs.phase6_action == 'lock-fresh-campaign' && github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }} # trusted",
        ),
        (
            "if: ${{ inputs.phase6_action == 'prepare-fresh-campaign' && github.repository == 'alexzhu0/skillscout' && github.ref == 'refs/heads/main' }}",
            "if: ${{ inputs.phase6_action == 'prepare-fresh-campaign' && github.ref == 'refs/heads/main' }}",
        ),
        (
            "environment: phase6-fresh-nomination",
            "environment: unprotected-fresh-nomination",
        ),
        (
            "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ secrets.SKILLSCOUT_FRESH_NOMINATION_STATE_GITHUB_TOKEN }}",
            "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ secrets.SKILLSCOUT_STATE_GITHUB_TOKEN }}",
        ),
        (
            "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ secrets.SKILLSCOUT_BENCHMARK_LOCK_STATE_GITHUB_TOKEN }}",
            "SKILLSCOUT_STATE_GITHUB_TOKEN: ${{ secrets.SKILLSCOUT_STATE_GITHUB_TOKEN }}",
        ),
        (
            "permissions:\n      contents: read\n      actions: read",
            "permissions:\n      contents: write",
        ),
        (
            "permissions:\n      contents: read\n      actions: read",
            "permissions:\n      contents: read\n      actions: read\n      \"issues\": write",
        ),
        (
            "        env:\n          GITHUB_TOKEN: ${{ github.token }}",
            "        env:\n          GITHUB_TOKEN: ${{ vars.UNRELATED_TOKEN }}",
        ),
        (
            "        env:\n          GITHUB_TOKEN: ${{ github.token }}",
            "        env:\n          GITHUB_TOKEN: ${{ github.token }}\n"
            "          \"SKILLSCOUT_STATE_GITHUB_TOKEN\": "
            "${{ secrets.SKILLSCOUT_STATE_GITHUB_TOKEN }}",
        ),
    ),
)
def test_source_execution_verifier_rejects_protected_fresh_lock_mutations(
    tmp_path: Path,
    needle: str,
    replacement: str,
) -> None:
    module = _module()
    repository = _copy_workflows(tmp_path)
    _replace_first(repository, needle, replacement)
    with pytest.raises(module.SourceExecutionError):
        module.verify_source_execution(repository)


@pytest.mark.parametrize(
    "mutation",
    (
        "commented_checkout_ref",
        "poisoned_materialization",
        "inherited_state_secret",
        "custom_default_shell",
    ),
)
def test_source_execution_verifier_closes_fresh_job_inherited_context(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Fresh-job authority cannot be changed by comments or root inheritance."""

    module = _module()
    repository = _copy_workflows(tmp_path)
    path = repository / Path(".github/workflows/phase6-acceptance.yml")
    source = path.read_text(encoding="utf-8")
    if mutation == "commented_checkout_ref":
        prefix, marker, suffix = source.partition("  prepare_fresh_campaign:\n")
        assert marker
        needle = "ref: ${{ github.sha }}\n          persist-credentials: false"
        assert needle in suffix
        source = prefix + marker + suffix.replace(
            needle,
            "ref: attacker-ref # ${{ github.sha }}\n          persist-credentials: false",
            1,
        )
    elif mutation == "poisoned_materialization":
        prefix, marker, suffix = source.partition("  prepare_fresh_campaign:\n")
        assert marker
        needle = "          mkdir -p .tools/uv-0.11.29/bin"
        assert needle in suffix
        source = prefix + marker + suffix.replace(
            needle,
            "          python -c 'raise SystemExit(0)'\n"
            "          # mkdir -p .tools/uv-0.11.29/bin",
            1,
        )
    elif mutation == "inherited_state_secret":
        needle = "defaults:\n  run:\n    shell: bash"
        assert needle in source
        source = source.replace(
            needle,
            "env:\n  SKILLSCOUT_STATE_GITHUB_TOKEN: "
            "${{ secrets.SKILLSCOUT_STATE_GITHUB_TOKEN }}\n" + needle,
            1,
        )
    else:
        needle = "defaults:\n  run:\n    shell: bash"
        assert needle in source
        source = source.replace(
            needle,
            "defaults:\n  run:\n    shell: bash -c 'curl https://attacker.invalid' --",
            1,
        )
    path.write_text(source, encoding="utf-8")
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
