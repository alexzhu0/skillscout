"""Pre-import Gate-B3 and installed-validator authority proofs."""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from skillscout.adapters.skills_ref import official_validator_authority


PROJECT_ROOT = Path(__file__).parents[1]


def _copy_repository(tmp_path: Path, *, corrupt_lock: bool) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(PROJECT_ROOT / "src", repository / "src")
    shutil.copytree(
        PROJECT_ROOT / "config/supply-chain",
        repository / "config/supply-chain",
    )
    shutil.copy2(PROJECT_ROOT / "uv.lock", repository / "uv.lock")
    if corrupt_lock:
        with (repository / "uv.lock").open("ab") as stream:
            stream.write(b"\ncorrupt\n")
    return repository


def _run_import(
    *,
    repository: Path,
    module: str,
    extra_pythonpath: Path,
    marker: Path,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(repository / "src"), str(extra_pythonpath))
    )
    environment["SKILLSCOUT_IMPORT_CANARY"] = str(marker)
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=repository,
        env=environment,
        capture_output=True,
        check=False,
        timeout=10,
    )


@pytest.mark.parametrize(
    "module",
    ("skillscout.cli", "skillscout.adapters.skills_ref"),
)
def test_failed_gate_b3_preflight_blocks_every_dependency_import(
    tmp_path: Path,
    module: str,
) -> None:
    repository = _copy_repository(tmp_path, corrupt_lock=True)
    canary = tmp_path / "canary"
    marker = tmp_path / "dependency-imported"
    canary.mkdir()
    (canary / "pydantic.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['SKILLSCOUT_IMPORT_CANARY']).write_text('executed')\n"
        "raise RuntimeError('dependency import canary executed')\n",
        encoding="utf-8",
    )

    completed = _run_import(
        repository=repository,
        module=module,
        extra_pythonpath=canary,
        marker=marker,
    )

    assert completed.returncode != 0
    assert not marker.exists()
    assert b"Gate B3" in completed.stderr
    assert b"uv.lock" not in completed.stderr


def test_same_version_modified_validator_is_rejected_before_module_execution(
    tmp_path: Path,
) -> None:
    repository = _copy_repository(tmp_path, corrupt_lock=False)
    installed = importlib.metadata.distribution("skills-ref")
    distribution_info = Path(str(installed._path))  # type: ignore[attr-defined]
    installed_package = distribution_info.parent / "skills_ref"
    fake_site = tmp_path / "site"
    shutil.copytree(distribution_info, fake_site / distribution_info.name)
    shutil.copytree(installed_package, fake_site / "skills_ref")
    marker = tmp_path / "validator-imported"
    init = fake_site / "skills_ref/__init__.py"
    init.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['SKILLSCOUT_IMPORT_CANARY']).write_text('executed')\n"
        + init.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    completed = _run_import(
        repository=repository,
        module="skillscout.adapters.skills_ref",
        extra_pythonpath=fake_site,
        marker=marker,
    )

    assert completed.returncode != 0
    assert not marker.exists()
    assert b"Gate B3" in completed.stderr


def test_shadow_validator_is_rejected_before_module_execution(
    tmp_path: Path,
) -> None:
    repository = _copy_repository(tmp_path, corrupt_lock=False)
    shadow_site = tmp_path / "shadow-site"
    shadow_package = shadow_site / "skills_ref"
    shadow_package.mkdir(parents=True)
    marker = tmp_path / "shadow-validator-imported"
    (shadow_package / "__init__.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "Path(os.environ['SKILLSCOUT_IMPORT_CANARY']).write_text('executed')\n"
        "def validate(_root): return []\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(repository / "src"), str(shadow_site))
    )
    environment["SKILLSCOUT_IMPORT_CANARY"] = str(marker)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from skillscout.adapters.skills_ref import _official_validator;"
                "_official_validator()"
            ),
        ],
        cwd=repository,
        env=environment,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode != 0
    assert not marker.exists()
    assert b"Gate B3" in completed.stderr


def test_official_authority_distinguishes_approved_wheel_and_observed_runtime() -> None:
    authority = official_validator_authority()

    assert authority.approved_distribution_hash.startswith("sha256:")
    assert authority.observed_distribution_digest.startswith("sha256:")
    assert (
        authority.approved_distribution_hash
        != authority.observed_distribution_digest
    )


def test_console_script_uses_dependency_free_bootstrap() -> None:
    project = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'skillscout = "skillscout.bootstrap:main"' in project
