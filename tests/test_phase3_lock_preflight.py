from __future__ import annotations

import hashlib
import os
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path

import pytest


APPROVED_LOCK_SHA256 = (
    "b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_SOURCE = REPOSITORY_ROOT / "tools/verify_phase3_gate_b3.sh"
LOCK_SOURCE = REPOSITORY_ROOT / "uv.lock"


def _make_repository(tmp_path: Path) -> tuple[Path, Path, Path]:
    repository = tmp_path / "repository"
    tools = repository / "tools"
    supply_chain = repository / "config/supply-chain"
    tools.mkdir(parents=True)
    supply_chain.mkdir(parents=True)

    preflight = tools / "verify_phase3_gate_b3.sh"
    preflight.write_bytes(PREFLIGHT_SOURCE.read_bytes())
    preflight.chmod(0o755)

    lock = repository / "uv.lock"
    lock.write_bytes(LOCK_SOURCE.read_bytes())
    digest = supply_chain / "phase3-gate-b3.lock.sha256"
    digest.write_text(f"{APPROVED_LOCK_SHA256}\n", encoding="ascii")
    return repository, preflight, digest


def _run_preflight(
    repository: Path,
    preflight: Path,
    *arguments: str,
    path: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    if path is not None:
        environment["PATH"] = path
    return subprocess.run(
        ["sh", str(preflight), *arguments],
        cwd=repository,
        env=environment,
        capture_output=True,
        check=False,
        timeout=10,
    )


def _run_with_downstream(
    repository: Path, preflight: Path, marker: Path
) -> subprocess.CompletedProcess[bytes]:
    downstream = repository / "downstream-sentinel"
    downstream.write_text('#!/bin/sh\nprintf "run\\n" >> "$1"\n', encoding="ascii")
    downstream.chmod(0o755)
    return subprocess.run(
        [
            "sh",
            "-c",
            'sh "$1" && "$2" "$3"',
            "phase3-preflight-test",
            str(preflight),
            str(downstream),
            str(marker),
        ],
        cwd=repository,
        env=os.environ.copy(),
        capture_output=True,
        check=False,
        timeout=10,
    )


def _assert_downstream_blocked(repository: Path, preflight: Path) -> None:
    marker = repository / "downstream-ran"
    completed = _run_with_downstream(repository, preflight, marker)
    assert completed.returncode != 0
    assert not marker.exists()
    assert b"uv.lock" not in completed.stderr
    assert LOCK_SOURCE.read_bytes() not in completed.stderr


def _wait_until_stopped(process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        waited, status = os.waitpid(process.pid, os.WUNTRACED | os.WNOHANG)
        if waited == process.pid:
            assert os.WIFSTOPPED(status)
            return
        time.sleep(0.01)
    process.kill()
    process.wait(timeout=5)
    raise AssertionError("preflight did not reach the requested descriptor test seam")


def _start_at_descriptor_seam(
    repository: Path, preflight: Path, seam: str
) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment["SKILLSCOUT_PHASE3_GATE_B3_TEST_SEAM"] = seam
    process = subprocess.Popen(
        ["sh", str(preflight)],
        cwd=repository,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_until_stopped(process)
    return process


def test_committed_digest_is_the_literal_gate_b3_approval() -> None:
    digest = REPOSITORY_ROOT / "config/supply-chain/phase3-gate-b3.lock.sha256"

    assert digest.read_bytes() == f"{APPROVED_LOCK_SHA256}\n".encode("ascii")
    assert hashlib.sha256(LOCK_SOURCE.read_bytes()).hexdigest() == APPROVED_LOCK_SHA256


def test_preflight_accepts_exact_lock_and_runs_fixed_downstream_once(
    tmp_path: Path,
) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    marker = repository / "downstream-ran"

    completed = _run_with_downstream(repository, preflight, marker)

    assert completed.returncode == 0
    assert marker.read_bytes() == b"run\n"


def test_non_executable_preflight_can_be_invoked_explicitly_through_sh(
    tmp_path: Path,
) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    preflight.chmod(0o644)

    assert _run_preflight(repository, preflight).returncode == 0


def test_repository_preflight_is_executable() -> None:
    assert os.lstat(PREFLIGHT_SOURCE).st_mode & stat.S_IXUSR


def test_preflight_rejects_stale_bound_lock_bytes_before_downstream(
    tmp_path: Path,
) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    lock = repository / "uv.lock"
    mutated = bytearray(lock.read_bytes())
    mutated[-1] ^= 1
    lock.write_bytes(mutated)

    _assert_downstream_blocked(repository, preflight)


@pytest.mark.parametrize("missing", ["lock", "digest"])
def test_preflight_rejects_missing_authority_before_downstream(
    tmp_path: Path, missing: str
) -> None:
    repository, preflight, digest = _make_repository(tmp_path)
    target = repository / "uv.lock" if missing == "lock" else digest
    target.unlink()

    _assert_downstream_blocked(repository, preflight)


@pytest.mark.parametrize("authority", ["lock", "digest"])
def test_preflight_rejects_symlink_authority_before_downstream(
    tmp_path: Path, authority: str
) -> None:
    repository, preflight, digest = _make_repository(tmp_path)
    target = repository / "uv.lock" if authority == "lock" else digest
    original = target.read_bytes()
    target.unlink()
    outside = repository / f"{authority}-outside"
    outside.write_bytes(original)
    target.symlink_to(outside)

    _assert_downstream_blocked(repository, preflight)


@pytest.mark.parametrize("authority", ["lock", "digest"])
def test_preflight_rejects_non_regular_authority_before_downstream(
    tmp_path: Path, authority: str
) -> None:
    repository, preflight, digest = _make_repository(tmp_path)
    target = repository / "uv.lock" if authority == "lock" else digest
    target.unlink()
    target.mkdir()

    _assert_downstream_blocked(repository, preflight)


@pytest.mark.parametrize(
    ("authority", "size"),
    [("lock", 2_000_001), ("digest", 66)],
)
def test_preflight_rejects_oversized_authority_before_downstream(
    tmp_path: Path, authority: str, size: int
) -> None:
    repository, preflight, digest = _make_repository(tmp_path)
    target = repository / "uv.lock" if authority == "lock" else digest
    with target.open("wb") as stream:
        stream.truncate(size)

    _assert_downstream_blocked(repository, preflight)


@pytest.mark.parametrize(
    "replacement",
    [
        b"",
        b"0" * 63 + b"\n",
        b"B87E7F1035D452EF1C5E66CA19E03E980398303FA8D3F99AEC1822DE75D85004\n",
        f"{APPROVED_LOCK_SHA256}\n{APPROVED_LOCK_SHA256}\n".encode("ascii"),
        f"{APPROVED_LOCK_SHA256}\nextra\n".encode("ascii"),
        f" {APPROVED_LOCK_SHA256}\n".encode("ascii"),
        f"{APPROVED_LOCK_SHA256}".encode("ascii"),
    ],
)
def test_preflight_rejects_malformed_uppercase_or_extra_line_hash(
    tmp_path: Path, replacement: bytes
) -> None:
    repository, preflight, digest = _make_repository(tmp_path)
    digest.write_bytes(replacement)

    _assert_downstream_blocked(repository, preflight)


def test_preflight_rejects_duplicate_or_unexpected_authority_claims(
    tmp_path: Path,
) -> None:
    repository, preflight, digest = _make_repository(tmp_path)
    digest.write_text(
        f"{APPROVED_LOCK_SHA256}\n{APPROVED_LOCK_SHA256}\n", encoding="ascii"
    )
    assert _run_preflight(repository, preflight).returncode != 0

    digest.write_text(f"{APPROVED_LOCK_SHA256}\n", encoding="ascii")
    assert _run_preflight(repository, preflight, "unexpected-authority").returncode != 0


def test_preflight_rejects_forged_success_hash_utilities(
    tmp_path: Path,
) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    lock = repository / "uv.lock"
    lock.write_bytes(lock.read_bytes() + b"mutation")
    forged_bin = repository / "forged-bin"
    forged_bin.mkdir()
    for name in ("shasum", "sha256sum"):
        forged = forged_bin / name
        forged.write_text(
            f'#!/bin/sh\nprintf "{APPROVED_LOCK_SHA256}  -\\n"\n', encoding="ascii"
        )
        forged.chmod(0o755)

    completed = _run_preflight(repository, preflight, path=str(forged_bin))

    assert completed.returncode != 0


@pytest.mark.parametrize("mode", [0o664, 0o602])
def test_preflight_requires_safe_permissions_before_hash_consumer(
    tmp_path: Path, mode: int
) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    (repository / "uv.lock").chmod(mode)

    _assert_downstream_blocked(repository, preflight)


def test_preflight_requires_one_link_before_hash_consumer(tmp_path: Path) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    os.link(repository / "uv.lock", repository / "uv.lock-alias")

    _assert_downstream_blocked(repository, preflight)


def test_preflight_rejects_path_to_descriptor_identity_swap(
    tmp_path: Path,
) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    lock = repository / "uv.lock"
    replacement = repository / "replacement.lock"
    replacement.write_bytes(lock.read_bytes())
    process = _start_at_descriptor_seam(repository, preflight, "lock_after_lstat")
    try:
        os.replace(replacement, lock)
        os.kill(process.pid, signal.SIGCONT)
        _stdout, _stderr = process.communicate(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert process.returncode != 0


def test_preflight_rejects_post_read_descriptor_mutation(
    tmp_path: Path,
) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    lock = repository / "uv.lock"
    process = _start_at_descriptor_seam(repository, preflight, "lock_after_read")
    try:
        with lock.open("ab") as stream:
            stream.write(b"post-read-mutation")
            stream.flush()
            os.fsync(stream.fileno())
        os.kill(process.pid, signal.SIGCONT)
        _stdout, _stderr = process.communicate(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    assert process.returncode != 0


def test_preflight_does_not_depend_on_caller_cwd(tmp_path: Path) -> None:
    repository, preflight, _digest = _make_repository(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    completed = subprocess.run(
        ["sh", str(preflight)],
        cwd=elsewhere,
        env=os.environ.copy(),
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 0


def test_preflight_does_not_import_project_or_invoke_python_or_uv() -> None:
    source = PREFLIGHT_SOURCE.read_text(encoding="utf-8")

    assert "src/skillscout" not in source
    assert "python" not in source.lower()
    assert "/uv" not in source.lower()
    assert " uv " not in source.lower()
    assert shutil.which("sh") is not None
