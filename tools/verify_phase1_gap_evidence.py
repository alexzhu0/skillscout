#!/usr/bin/env python3
"""Record and independently rerun Phase 1 authority-bound evidence."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

SCHEMA_VERSION = "2"
START_SENTINEL = "<!-- phase1-gap-evidence-json:start -->"
END_SENTINEL = "<!-- phase1-gap-evidence-json:end -->"
INVALID_DIAGNOSTIC = "phase1 gap evidence invalid"
MAX_DOCUMENT_BYTES = 1_000_000
MAX_SOURCE_BYTES = 2_000_000
MAX_CAPTURE_BYTES = 4_000_000
COMMAND_TIMEOUT_SECONDS = 300
LOCK_HASH = "b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004"
FROZEN_DB_HASH = "49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = ".planning/phases/01-auditable-dry-run-spine/01-REVIEW.md"
VERIFICATION_PATH = ".planning/phases/01-auditable-dry-run-spine/01-VERIFICATION.md"
VERIFIER_PATH = "tools/verify_phase1_gap_evidence.py"
FROZEN_DB_PATH = "tests/fixtures/state/v1-cli.db"
EXPECTED_TOP_LEVEL = {
    "schema_version",
    "source_digests",
    "command_results",
    "current_findings",
    "cli_facts",
    "immutable_inputs",
    "normalization",
    "deferred",
}
NORMALIZATION = {
    "elapsed_time": "decimal ns/us/ms/s duration following the literal ' in '",
    "temporary_root": "exact per-command temporary workspace path",
}
CLI_FACTS = {
    "snapshot_reopen_truth": True,
    "event_reuse_tamper_rejected": True,
    "invalid_argv_fixed_diagnostic": True,
    "fail_once_resume_without_replay": True,
    "namespace_collision_rejected": True,
    "private_file_policy_enforced": True,
    "remote_writes_attempted": 0,
}
CURRENT_FINDING_NODES: dict[str, tuple[str, ...]] = {
    "IN-01": (
        "tests/test_phase1_gap_closure.py::"
        "test_known_issue_in01_dead_local_state_store_alias_remains_as_documented",
    ),
    "IN-02": (
        "tests/test_phase1_gap_closure.py::"
        "test_known_issue_in02_lock_acquisition_duplication_remains_as_documented",
    ),
}
CURRENT_FINDING_STATUS: dict[str, str] = {
    "IN-01": "documented",
    "IN-02": "documented",
}
COMPOSED_SMOKE_NODE = (
    "{repo}/tests/test_phase1_gap_closure.py::"
    "test_current_review_composed_packaged_smoke"
)


class EvidenceError(Exception):
    """Closed internal failure for invalid or unreproducible evidence."""


class CommandSpec(NamedTuple):
    """One immutable command in the only accepted evidence registry."""

    id: str
    argv: tuple[str, ...]
    result_kind: str
    exact_count: int | None = None


class ProcessCapture(NamedTuple):
    """Bounded process facts returned by a registry runner."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    artifact_count: int | None = None


CURRENT_FINDING_ARGV = tuple(
    f"{{repo}}/{node}" for nodes in CURRENT_FINDING_NODES.values() for node in nodes
)
COMMAND_REGISTRY = (
    CommandSpec(
        "packaged_smoke",
        (
            "{uv}",
            "run",
            "--project",
            "{repo}",
            "--locked",
            "--offline",
            "pytest",
            "-q",
            "--basetemp",
            "{temp}/pytest",
            COMPOSED_SMOKE_NODE,
        ),
        "passed",
        1,
    ),
    CommandSpec(
        "current_findings",
        (
            "{uv}",
            "run",
            "--project",
            "{repo}",
            "--locked",
            "--offline",
            "pytest",
            "-q",
            "--basetemp",
            "{temp}/pytest",
            *CURRENT_FINDING_ARGV,
        ),
        "passed",
    ),
    CommandSpec(
        "full_pytest",
        (
            "{uv}",
            "run",
            "--project",
            "{repo}",
            "--locked",
            "--offline",
            "pytest",
            "-q",
            "--basetemp",
            "{temp}/pytest",
            "{repo}/tests",
        ),
        "passed",
    ),
    CommandSpec(
        "ruff",
        (
            "{uv}",
            "run",
            "--project",
            "{repo}",
            "--locked",
            "--offline",
            "ruff",
            "check",
            "{repo}/src",
            "{repo}/tests",
            "{repo}/tools/verify_phase1_gap_evidence.py",
        ),
        "checks",
        1,
    ),
    CommandSpec(
        "lock_check",
        ("{uv}", "lock", "--project", "{repo}", "--check", "--offline"),
        "checks",
        1,
    ),
    CommandSpec(
        "build",
        (
            "{uv}",
            "build",
            "--project",
            "{repo}",
            "--offline",
            "--no-sources",
            "--out-dir",
            "{temp}/dist",
        ),
        "artifacts",
        2,
    ),
)
CommandRunner = Callable[[CommandSpec, Path], ProcessCapture]


def _require(condition: bool) -> None:
    if not condition:
        raise EvidenceError


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_regular_bytes(path: Path, limit: int) -> bytes:
    metadata = path.lstat()
    _require(stat.S_ISREG(metadata.st_mode) and not path.is_symlink())
    _require(0 <= metadata.st_size <= limit)
    raw = path.read_bytes()
    _require(len(raw) <= limit)
    return raw


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path, *, limit: int) -> str:
    return _sha256_bytes(_read_regular_bytes(path, limit))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError
        result[key] = value
    return result


def extract_payload(document: str) -> dict[str, Any]:
    """Extract one canonical JSON evidence object from a Markdown document."""

    _require(document.count(START_SENTINEL) == 1)
    _require(document.count(END_SENTINEL) == 1)
    _, remainder = document.split(START_SENTINEL, 1)
    enclosed, _ = remainder.split(END_SENTINEL, 1)
    _require(enclosed.startswith("\n") and enclosed.endswith("\n"))
    encoded = enclosed[1:-1]
    _require(bool(encoded) and "\n" not in encoded and "\r" not in encoded)
    payload = json.loads(
        encoded,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda _value: (_ for _ in ()).throw(EvidenceError()),
    )
    _require(isinstance(payload, dict))
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    _require(encoded == canonical)
    return payload


def _source_paths(repository_root: Path) -> tuple[Path, ...]:
    relative_paths = {
        Path("pyproject.toml"),
        Path(VERIFIER_PATH),
        Path(REVIEW_PATH),
        Path(VERIFICATION_PATH),
        Path("tests/fixtures/pipeline/approved.json"),
        Path("tests/fixtures/state/v1-cli-provenance.json"),
    }
    for relative_root in (Path("src/skillscout"), Path("tests")):
        root = repository_root / relative_root
        metadata = root.lstat()
        _require(stat.S_ISDIR(metadata.st_mode) and not root.is_symlink())
        for directory, directories, filenames in os.walk(root, followlinks=False):
            directory_path = Path(directory)
            for name in directories:
                _require(not (directory_path / name).is_symlink())
            for name in filenames:
                if name.endswith(".py"):
                    relative_paths.add((directory_path / name).relative_to(repository_root))
    ordered = tuple(sorted(relative_paths, key=lambda path: path.as_posix()))
    _require(len(ordered) == len(relative_paths))
    return ordered


def _collect_source_digests(repository_root: Path) -> list[dict[str, str]]:
    return [
        {
            "path": relative.as_posix(),
            "sha256": _sha256(repository_root / relative, limit=MAX_SOURCE_BYTES),
        }
        for relative in _source_paths(repository_root)
    ]


def _immutable_hashes(repository_root: Path) -> dict[str, str]:
    current = {
        "uv_lock": _sha256(repository_root / "uv.lock", limit=MAX_SOURCE_BYTES),
        "frozen_v1_db": _sha256(
            repository_root / FROZEN_DB_PATH, limit=MAX_SOURCE_BYTES
        ),
    }
    _require(current == {"uv_lock": LOCK_HASH, "frozen_v1_db": FROZEN_DB_HASH})
    return current


def _immutable_records(pre: dict[str, str], post: dict[str, str]) -> dict[str, Any]:
    expected = {
        "uv_lock": ("uv.lock", LOCK_HASH),
        "frozen_v1_db": (FROZEN_DB_PATH, FROZEN_DB_HASH),
    }
    return {
        identifier: {
            "path": path,
            "expected": digest,
            "pre": pre[identifier],
            "post": post[identifier],
        }
        for identifier, (path, digest) in expected.items()
    }


def _resolve_nodes(repository_root: Path) -> None:
    definitions: dict[str, set[str]] = {}
    for nodes in CURRENT_FINDING_NODES.values():
        for node_id in nodes:
            module_name, separator, function_name = node_id.partition("::")
            _require(separator == "::" and function_name.startswith("test_"))
            _require(module_name.startswith("tests/test_") and module_name.endswith(".py"))
            if module_name not in definitions:
                raw = _read_regular_bytes(
                    repository_root / module_name, MAX_SOURCE_BYTES
                )
                tree = ast.parse(raw, filename=module_name)
                definitions[module_name] = {
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
            _require(function_name in definitions[module_name])


def normalize_output(raw: bytes, repository_root: Path, temporary_root: Path) -> bytes:
    """Normalize only the per-command temporary root and pytest-style elapsed seconds."""

    del repository_root
    normalized = raw.replace(os.fsencode(str(temporary_root)), b"<TEMP_ROOT>")
    return re.sub(
        rb"(?<= in )\d+(?:\.\d+)?(?:ns|us|ms|s)\b", b"<ELAPSED>", normalized
    )


def _materialize_argv(
    spec: CommandSpec, repository_root: Path, temporary_root: Path
) -> tuple[str, ...]:
    replacements = {
        "{uv}": str(repository_root / ".tools/uv-0.11.29/bin/uv"),
        "{repo}": str(repository_root),
        "{temp}": str(temporary_root),
    }
    return tuple(
        token.replace("{uv}", replacements["{uv}"])
        .replace("{repo}", replacements["{repo}"])
        .replace("{temp}", replacements["{temp}"])
        for token in spec.argv
    )


def _execution_environment(repository_root: Path, temporary_root: Path) -> dict[str, str]:
    home = temporary_root / "home"
    temp = temporary_root / "tmp"
    home.mkdir(mode=0o700, exist_ok=True)
    temp.mkdir(mode=0o700, exist_ok=True)
    environment = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TMPDIR": str(temp),
        "UV_CACHE_DIR": str(repository_root / ".tools/uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(repository_root / ".tools/python"),
        "UV_MANAGED_PYTHON": "1",
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_OFFLINE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }
    for name in ("LANG", "LC_ALL", "SYSTEMROOT"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return environment


def _execute_command(
    spec: CommandSpec, repository_root: Path, temporary_root: Path
) -> ProcessCapture:
    argv = _materialize_argv(spec, repository_root, temporary_root)
    completed = subprocess.run(
        argv,
        cwd=temporary_root,
        env=_execution_environment(repository_root, temporary_root),
        capture_output=True,
        check=False,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    _require(
        len(completed.stdout) <= MAX_CAPTURE_BYTES
        and len(completed.stderr) <= MAX_CAPTURE_BYTES
    )
    artifact_count = None
    if spec.id == "build":
        output = temporary_root / "dist"
        artifact_count = sum(
            1
            for path in output.iterdir()
            if path.is_file() and (path.name.endswith(".whl") or path.name.endswith(".tar.gz"))
        )
    return ProcessCapture(
        completed.returncode, completed.stdout, completed.stderr, artifact_count
    )


def _parse_count(spec: CommandSpec, capture: ProcessCapture) -> int:
    combined = capture.stdout + b"\n" + capture.stderr
    if spec.result_kind == "passed":
        matches = re.findall(rb"(?<!\d)(\d+) passed\b", combined)
        _require(len(matches) == 1)
        count = int(matches[0])
    elif spec.id == "ruff":
        _require(b"All checks passed!" in combined)
        count = 1
    elif spec.id == "lock_check":
        count = 1
    else:
        _require(spec.id == "build" and capture.artifact_count is not None)
        count = capture.artifact_count
    _require(count > 0)
    if spec.exact_count is not None:
        _require(count == spec.exact_count)
    return count


def _command_result(
    spec: CommandSpec,
    capture: ProcessCapture,
    repository_root: Path,
    temporary_root: Path,
) -> dict[str, Any]:
    _require(type(capture.exit_code) is int and capture.exit_code == 0)
    _require(type(capture.stdout) is bytes and type(capture.stderr) is bytes)
    _require(
        len(capture.stdout) <= MAX_CAPTURE_BYTES
        and len(capture.stderr) <= MAX_CAPTURE_BYTES
    )
    stdout = normalize_output(capture.stdout, repository_root, temporary_root)
    stderr = normalize_output(capture.stderr, repository_root, temporary_root)
    return {
        "id": spec.id,
        "argv": list(spec.argv),
        "exit_code": capture.exit_code,
        "count": {"kind": spec.result_kind, "value": _parse_count(spec, capture)},
        "stdout_sha256": _sha256_bytes(stdout),
        "stderr_sha256": _sha256_bytes(stderr),
    }


def _run_registry(
    repository_root: Path, runner: CommandRunner | None
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="skillscout-phase1-evidence-") as directory:
        root = Path(directory)
        for spec in COMMAND_REGISTRY:
            workspace = root / spec.id
            workspace.mkdir(mode=0o700)
            capture = (
                runner(spec, workspace)
                if runner is not None
                else _execute_command(spec, repository_root, workspace)
            )
            results.append(_command_result(spec, capture, repository_root, workspace))
    return results


def _finding_records() -> dict[str, dict[str, Any]]:
    """Map each current review finding to its disposition and digest-bound nodes."""

    _require(tuple(CURRENT_FINDING_STATUS) == tuple(CURRENT_FINDING_NODES))
    return {
        finding: {"status": CURRENT_FINDING_STATUS[finding], "nodes": list(nodes)}
        for finding, nodes in CURRENT_FINDING_NODES.items()
    }


def _validate_source_claims(value: object, repository_root: Path) -> None:
    _require(isinstance(value, list))
    records = value
    expected = _collect_source_digests(repository_root)
    _require(records == expected)
    paths: list[str] = []
    for record in records:
        _require(isinstance(record, dict) and set(record) == {"path", "sha256"})
        path = record["path"]
        _require(type(path) is str and type(record["sha256"]) is str)
        _require(_is_sha256(record["sha256"]))
        paths.append(path)
    _require(paths == sorted(paths) and len(paths) == len(set(paths)))
    _require(".planning/config.json" not in paths)


def _validate_immutable_claims(value: object, repository_root: Path) -> None:
    _require(isinstance(value, dict))
    current = _immutable_hashes(repository_root)
    expected = _immutable_records(current, current)
    _require(value == expected)


def _validate_command_claims(value: object) -> None:
    _require(isinstance(value, list) and len(value) == len(COMMAND_REGISTRY))
    identifiers: list[str] = []
    for spec, result in zip(COMMAND_REGISTRY, value, strict=True):
        _require(
            isinstance(result, dict)
            and set(result)
            == {
                "id",
                "argv",
                "exit_code",
                "count",
                "stdout_sha256",
                "stderr_sha256",
            }
        )
        _require(result["id"] == spec.id and result["argv"] == list(spec.argv))
        _require(type(result["exit_code"]) is int and result["exit_code"] == 0)
        count = result["count"]
        _require(isinstance(count, dict) and set(count) == {"kind", "value"})
        _require(count["kind"] == spec.result_kind)
        _require(type(count["value"]) is int and count["value"] > 0)
        if spec.exact_count is not None:
            _require(count["value"] == spec.exact_count)
        _require(
            _is_sha256(result["stdout_sha256"])
            and _is_sha256(result["stderr_sha256"])
        )
        _require("record" not in result["argv"] and "verify" not in result["argv"])
        identifiers.append(result["id"])
    _require(identifiers == [spec.id for spec in COMMAND_REGISTRY])
    _require(len(identifiers) == len(set(identifiers)))


def _validate_payload(payload: dict[str, Any], repository_root: Path) -> None:
    _require(set(payload) == EXPECTED_TOP_LEVEL)
    _require(payload["schema_version"] == SCHEMA_VERSION)
    _validate_source_claims(payload["source_digests"], repository_root)
    _validate_immutable_claims(payload["immutable_inputs"], repository_root)
    _validate_command_claims(payload["command_results"])
    _require(payload["current_findings"] == _finding_records())
    _require(payload["cli_facts"] == CLI_FACTS)
    _require(payload["normalization"] == NORMALIZATION)
    _require(
        payload["deferred"]
        == {"os_syscall_network_denial": {"addressed_in": "Phase 6"}}
    )
    _resolve_nodes(repository_root)


def render_document(payload: dict[str, Any]) -> str:
    """Render the generated evidence index without adding self-validating claims."""

    immutable = payload.get("immutable_inputs", {})
    commands = payload.get("command_results", [])
    findings = payload.get("current_findings", {})
    lines = [
        "# Phase 1 Gap Closure Validation",
        "",
        "This schema-version-2 index binds the exact current production, test, tool, review,",
        "verification, and project-metadata bytes to normalized outputs captured from one",
        "closed local command registry. The evidence document itself is outside that authority",
        "set. All commands use the repository-local uv and managed Python with downloads",
        "disabled, the frozen dependency graph, offline mode, and temporary state/output roots.",
        "",
        "## Immutable Inputs",
        "",
        "| Input | Expected SHA-256 | Pre | Post |",
        "|---|---|---|---|",
    ]
    for identifier in ("uv_lock", "frozen_v1_db"):
        record = immutable.get(identifier, {})
        lines.append(
            f"| `{record.get('path', identifier)}` | `{record.get('expected', '')}` | "
            f"`{record.get('pre', '')}` | `{record.get('post', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Captured Command Results",
            "",
            "| ID | Exit | Parsed result | stdout SHA-256 | stderr SHA-256 |",
            "|---|---:|---|---|---|",
        ]
    )
    for result in commands:
        count = result.get("count", {})
        lines.append(
            f"| `{result.get('id', '')}` | {result.get('exit_code', '')} | "
            f"{count.get('value', '')} {count.get('kind', '')} | "
            f"`{result.get('stdout_sha256', '')}` | "
            f"`{result.get('stderr_sha256', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Current Two-Finding Known-Issue Matrix",
            "",
            "Both current findings are Info-severity items documented (not fixed) in the",
            "current review. Each bound node is a deterministic known-issue marker for the",
            "documented source state, not a fix proof; resolving a finding must break its",
            "marker and force a fresh re-baseline.",
            "",
            "| Finding | Status | Digest-bound top-level test nodes |",
            "|---|---|---|",
        ]
    )
    for finding, record in findings.items():
        nodes = "; ".join(f"`{node}`" for node in record.get("nodes", []))
        lines.append(f"| {finding} | {str(record.get('status', '')).upper()} | {nodes} |")
    lines.extend(
        [
            "",
            "## Deferred Item",
            "",
            "The older OS/syscall-boundary outbound-network denial remains assigned only to",
            "Phase 6. It is not owned by any current finding and is distinct from the two",
            "documented Info findings above.",
            "",
            "## Canonical Machine Evidence",
            "",
            START_SENTINEL,
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ),
            END_SENTINEL,
            "",
        ]
    )
    return "\n".join(lines)


def record_evidence(
    document: Path,
    repository_root: Path,
    *,
    runner: CommandRunner | None = None,
) -> None:
    """Execute the closed registry and replace DOCUMENT with fresh schema-v2 evidence."""

    repository_root = repository_root.resolve(strict=True)
    pre = _immutable_hashes(repository_root)
    sources = _collect_source_digests(repository_root)
    _resolve_nodes(repository_root)
    results = _run_registry(repository_root, runner)
    _require(_collect_source_digests(repository_root) == sources)
    post = _immutable_hashes(repository_root)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_digests": sources,
        "command_results": results,
        "current_findings": _finding_records(),
        "cli_facts": CLI_FACTS,
        "immutable_inputs": _immutable_records(pre, post),
        "normalization": NORMALIZATION,
        "deferred": {"os_syscall_network_denial": {"addressed_in": "Phase 6"}},
    }
    _validate_payload(payload, repository_root)
    document.parent.mkdir(parents=True, exist_ok=True)
    if document.exists() or document.is_symlink():
        metadata = document.lstat()
        _require(stat.S_ISREG(metadata.st_mode) and not document.is_symlink())
    rendered = render_document(payload).encode("utf-8")
    _require(len(rendered) <= MAX_DOCUMENT_BYTES)
    temporary = document.with_name(f".{document.name}.recording-{os.getpid()}")
    try:
        temporary.write_bytes(rendered)
        temporary.replace(document)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify_evidence(
    document: Path,
    repository_root: Path,
    *,
    rerun: bool,
    runner: CommandRunner | None = None,
) -> None:
    """Read current authority, rerun every registry command, and compare exact results."""

    _require(rerun)
    repository_root = repository_root.resolve(strict=True)
    before = _read_regular_bytes(document, MAX_DOCUMENT_BYTES)
    payload = extract_payload(before.decode("utf-8"))
    _validate_payload(payload, repository_root)
    sources = _collect_source_digests(repository_root)
    fresh_results = _run_registry(repository_root, runner)
    _require(fresh_results == payload["command_results"])
    _require(_collect_source_digests(repository_root) == sources)
    _validate_immutable_claims(payload["immutable_inputs"], repository_root)
    _require(_read_regular_bytes(document, MAX_DOCUMENT_BYTES) == before)


def main(argv: list[str], *, runner: CommandRunner | None = None) -> int:
    try:
        if len(argv) == 2 and argv[0] == "record":
            record_evidence(Path(argv[1]), REPOSITORY_ROOT, runner=runner)
        elif len(argv) == 3 and argv[:2] == ["verify", "--rerun"]:
            verify_evidence(
                Path(argv[2]), REPOSITORY_ROOT, rerun=True, runner=runner
            )
        else:
            print(INVALID_DIAGNOSTIC, file=sys.stderr)
            return 2
    except (
        EvidenceError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        SyntaxError,
        subprocess.SubprocessError,
        ValueError,
        TypeError,
    ):
        print(INVALID_DIAGNOSTIC, file=sys.stderr)
        return 1
    print("phase1 gap evidence recorded" if argv[0] == "record" else "phase1 gap evidence valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
