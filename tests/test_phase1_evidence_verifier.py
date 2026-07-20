"""Adversarial tests for the Phase 1 authority-bound evidence verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

VERIFIER_PATH = Path(__file__).parents[1] / "tools/verify_phase1_gap_evidence.py"
PROJECT_ROOT = Path(__file__).parents[1]
VERIFIER_SPEC = importlib.util.spec_from_file_location(
    "phase1_gap_evidence_verifier", VERIFIER_PATH
)
assert VERIFIER_SPEC is not None and VERIFIER_SPEC.loader is not None
verifier = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(verifier)


CommandRunner = Callable[
    [verifier.CommandSpec, Path], verifier.ProcessCapture
]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def evidence_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    _write(repository / "pyproject.toml", "[project]\nname='evidence-fixture'\n")
    _write(repository / "src/skillscout/__init__.py", 'VALUE = "bound"\n')
    _write(
        repository / ".planning/phases/01-auditable-dry-run-spine/01-REVIEW.md",
        "# Current review\n",
    )
    _write(
        repository / ".planning/phases/01-auditable-dry-run-spine/01-VERIFICATION.md",
        "# Current verification\n",
    )
    (repository / "tools").mkdir(parents=True)
    shutil.copyfile(
        Path(verifier.__file__), repository / "tools/verify_phase1_gap_evidence.py"
    )
    shutil.copyfile(PROJECT_ROOT / "uv.lock", repository / "uv.lock")
    frozen = repository / "tests/fixtures/state/v1-cli.db"
    frozen.parent.mkdir(parents=True)
    shutil.copyfile(PROJECT_ROOT / "tests/fixtures/state/v1-cli.db", frozen)
    approved = repository / "tests/fixtures/pipeline/approved.json"
    approved.parent.mkdir(parents=True)
    shutil.copyfile(PROJECT_ROOT / "tests/fixtures/pipeline/approved.json", approved)
    provenance = repository / "tests/fixtures/state/v1-cli-provenance.json"
    shutil.copyfile(
        PROJECT_ROOT / "tests/fixtures/state/v1-cli-provenance.json", provenance
    )

    definitions: dict[str, list[str]] = {}
    for nodes in verifier.CURRENT_FINDING_NODES.values():
        for node_id in nodes:
            module, function = node_id.split("::", 1)
            definitions.setdefault(module, []).append(function)
    for module, functions in definitions.items():
        _write(
            repository / module,
            "\n\n".join(f"def {function}():\n    pass" for function in functions)
            + "\n",
        )
    return repository


def _successful_runner() -> CommandRunner:
    def run(spec: verifier.CommandSpec, workspace: Path) -> verifier.ProcessCapture:
        if spec.result_kind == "passed":
            count = spec.exact_count or 37
            stdout = f"{'.' * min(count, 5)} [{count:3d}%]\n{count} passed in 0.41s\n"
            return verifier.ProcessCapture(0, stdout.encode(), b"")
        if spec.id == "ruff":
            return verifier.ProcessCapture(0, b"All checks passed!\n", b"")
        if spec.id == "lock_check":
            return verifier.ProcessCapture(0, b"Resolved 7 packages in 0.02s\n", b"")
        assert spec.id == "build"
        return verifier.ProcessCapture(
            0,
            f"Built {workspace}/dist/skillscout.whl\nBuilt {workspace}/dist/skillscout.tar.gz\n".encode(),
            b"",
            artifact_count=2,
        )

    return run


def _document(repository: Path) -> Path:
    document = repository / ".planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text("untrusted prior document bytes\n", encoding="utf-8")
    verifier.record_evidence(document, repository, runner=_successful_runner())
    return document


def _payload(document: Path) -> dict[str, Any]:
    return verifier.extract_payload(document.read_text(encoding="utf-8"))


def _rewrite(document: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    payload = _payload(document)
    mutate(payload)
    document.write_text(verifier.render_document(payload), encoding="utf-8")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _replace_source_digest(payload: dict[str, Any], relative: str, digest: str) -> None:
    for record in payload["source_digests"]:
        if record["path"] == relative:
            record["sha256"] = digest
            return
    raise AssertionError(relative)


def _drop_source_claim(payload: dict[str, Any], relative: str) -> None:
    payload["source_digests"] = [
        record for record in payload["source_digests"] if record["path"] != relative
    ]


def _rename_source_claim(payload: dict[str, Any], relative: str, replacement: str) -> None:
    for record in payload["source_digests"]:
        if record["path"] == relative:
            record["path"] = replacement
            return
    raise AssertionError(relative)


@pytest.mark.parametrize(
    ("relative", "replacement"),
    [
        ("src/skillscout/__init__.py", 'VALUE = "stale production"\n'),
        (
            "tests/test_phase1_evidence_verifier.py",
            "def test_unrelated_replacement():\n    pass\n",
        ),
    ],
)
def test_verify_rejects_stale_bound_source_bytes(
    evidence_repository: Path, relative: str, replacement: str
) -> None:
    document = _document(evidence_repository)
    (evidence_repository / relative).write_text(replacement, encoding="utf-8")

    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(
            document, evidence_repository, rerun=True, runner=_successful_runner()
        )


def test_stale_json_fixture_bytes_are_rejected_before_command_credit(
    evidence_repository: Path,
) -> None:
    document = _document(evidence_repository)
    document_bytes = document.read_bytes()
    approved = evidence_repository / "tests/fixtures/pipeline/approved.json"
    provenance = evidence_repository / "tests/fixtures/state/v1-cli-provenance.json"
    fixture_paths = (
        "tests/fixtures/pipeline/approved.json",
        "tests/fixtures/state/v1-cli-provenance.json",
    )
    calls: list[str] = []

    def spy(spec: verifier.CommandSpec, workspace: Path) -> verifier.ProcessCapture:
        calls.append(spec.id)
        return _successful_runner()(spec, workspace)

    original_approved = approved.read_bytes()
    whitespace_only = original_approved.replace(
        b'\n  "schema_version"', b'\n   "schema_version"', 1
    )
    assert whitespace_only != original_approved
    assert json.loads(whitespace_only) == json.loads(original_approved)
    approved.write_bytes(whitespace_only)
    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(document, evidence_repository, rerun=True, runner=spy)
    assert calls == []
    approved.write_bytes(original_approved)

    original_provenance = provenance.read_bytes()
    parsed_provenance = json.loads(original_provenance)
    reordered = {key: parsed_provenance[key] for key in reversed(list(parsed_provenance))}
    key_order_only = (json.dumps(reordered, indent=2) + "\n").encode()
    assert key_order_only != original_provenance
    assert json.loads(key_order_only) == parsed_provenance
    provenance.write_bytes(key_order_only)
    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(document, evidence_repository, rerun=True, runner=spy)
    assert calls == []
    provenance.write_bytes(original_provenance)

    claimed_paths = [record["path"] for record in _payload(document)["source_digests"]]
    for relative in fixture_paths:
        assert claimed_paths.count(relative) == 1

    _rewrite(document, lambda payload: _drop_source_claim(payload, fixture_paths[0]))
    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(document, evidence_repository, rerun=True, runner=spy)
    assert calls == []
    document.write_bytes(document_bytes)

    _rewrite(document, lambda payload: _drop_source_claim(payload, fixture_paths[1]))
    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(document, evidence_repository, rerun=True, runner=spy)
    assert calls == []
    document.write_bytes(document_bytes)

    _rewrite(
        document,
        lambda payload: _rename_source_claim(
            payload, fixture_paths[0], "tests/fixtures/pipeline/not-bound.json"
        ),
    )
    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(document, evidence_repository, rerun=True, runner=spy)
    assert calls == []
    document.write_bytes(document_bytes)


def test_verify_rejects_new_in_scope_source_until_recorded(
    evidence_repository: Path,
) -> None:
    document = _document(evidence_repository)
    _write(evidence_repository / "tests/test_added_after_record.py", "def test_new():\n    pass\n")

    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(
            document, evidence_repository, rerun=True, runner=_successful_runner()
        )


@pytest.mark.parametrize("damage", ["missing", "symlink", "non_regular", "oversized"])
def test_record_rejects_unsafe_or_unbounded_source_authority(
    evidence_repository: Path, damage: str
) -> None:
    source = evidence_repository / "tools/verify_phase1_gap_evidence.py"
    if damage == "missing":
        source.unlink()
    elif damage == "symlink":
        source.unlink()
        source.symlink_to(evidence_repository / "pyproject.toml")
    elif damage == "non_regular":
        source.unlink()
        source.mkdir()
    else:
        source.write_bytes(b"x" * (verifier.MAX_SOURCE_BYTES + 1))
    document = (
        evidence_repository
        / ".planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md"
    )

    with pytest.raises((verifier.EvidenceError, OSError)):
        verifier.record_evidence(document, evidence_repository, runner=_successful_runner())


def test_verify_resolves_named_nodes_from_the_digest_bound_ast(
    evidence_repository: Path,
) -> None:
    document = _document(evidence_repository)
    node_id = verifier.CURRENT_FINDING_NODES["IN-01"][0]
    module_name, function_name = node_id.split("::", 1)
    module = evidence_repository / module_name
    module.write_text(
        module.read_text(encoding="utf-8").replace(function_name, f"renamed_{function_name}"),
        encoding="utf-8",
    )
    _rewrite(
        document,
        lambda payload: _replace_source_digest(payload, module_name, _digest(module)),
    )

    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(
            document, evidence_repository, rerun=True, runner=_successful_runner()
        )


@pytest.mark.parametrize("claim", ["duplicate_path", "duplicate_command", "unexpected_command"])
def test_verify_rejects_duplicate_or_unexpected_registry_claims(
    evidence_repository: Path, claim: str
) -> None:
    document = _document(evidence_repository)

    def mutate(payload: dict[str, Any]) -> None:
        if claim == "duplicate_path":
            payload["source_digests"].append(dict(payload["source_digests"][0]))
        elif claim == "duplicate_command":
            payload["command_results"].append(dict(payload["command_results"][0]))
        else:
            payload["command_results"][0]["id"] = "self_asserted_success"

    _rewrite(document, mutate)
    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(
            document, evidence_repository, rerun=True, runner=_successful_runner()
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exit_code", 9),
        ("count", {"kind": "passed", "value": 999}),
        ("stdout_sha256", "0" * 64),
        ("stderr_sha256", "f" * 64),
    ],
)
def test_verify_rejects_forged_exit_count_or_output_digest(
    evidence_repository: Path, field: str, value: object
) -> None:
    document = _document(evidence_repository)
    _rewrite(document, lambda payload: payload["command_results"][0].__setitem__(field, value))

    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(
            document, evidence_repository, rerun=True, runner=_successful_runner()
        )


@pytest.mark.parametrize(
    "claim",
    [
        ("document_sha256", "0" * 64),
        ("verifier_outcome", "pass"),
        ("record_command", "python tools/verify_phase1_gap_evidence.py record"),
    ],
)
def test_verify_rejects_self_hash_and_self_success_claims(
    evidence_repository: Path, claim: tuple[str, str]
) -> None:
    document = _document(evidence_repository)
    _rewrite(document, lambda payload: payload.__setitem__(*claim))

    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(
            document, evidence_repository, rerun=True, runner=_successful_runner()
        )


def test_verify_reruns_closed_registry_and_rejects_mismatched_output(
    evidence_repository: Path,
) -> None:
    document = _document(evidence_repository)
    original = _successful_runner()
    invoked: list[str] = []

    def changed(spec: verifier.CommandSpec, workspace: Path) -> verifier.ProcessCapture:
        invoked.append(spec.id)
        capture = original(spec, workspace)
        if spec.id == "full_pytest":
            return verifier.ProcessCapture(
                capture.exit_code,
                capture.stdout.replace(b"37 passed", b"38 passed"),
                capture.stderr,
            )
        return capture

    before = document.read_bytes()
    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(document, evidence_repository, rerun=True, runner=changed)
    assert invoked == [spec.id for spec in verifier.COMMAND_REGISTRY]
    assert document.read_bytes() == before


def test_verify_rejects_a_forged_zero_exit_when_fresh_execution_fails(
    evidence_repository: Path,
) -> None:
    document = _document(evidence_repository)
    original = _successful_runner()

    def failing(spec: verifier.CommandSpec, workspace: Path) -> verifier.ProcessCapture:
        if spec.id == "full_pytest":
            return verifier.ProcessCapture(
                1,
                b"36 passed, 1 failed in 0.40s\n",
                b"FAILED tests/test_current.py::test_failure\n",
            )
        return original(spec, workspace)

    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(document, evidence_repository, rerun=True, runner=failing)


def test_output_normalization_is_narrow_and_preserves_failure_facts(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    workspace = tmp_path / "evidence-run-123"
    raw = (
        f"failure at {workspace}/state.db\n"
        "node tests/test_x.py::test_failure\n"
        "FAILED arbitrary failure text\n"
        "7 failed, 2 passed in 12.34s\n"
        "Resolved 13 packages in 0.76ms\n"
    ).encode()

    normalized = verifier.normalize_output(raw, repository, workspace)

    assert str(workspace).encode() not in normalized
    assert b"<TEMP_ROOT>/state.db" in normalized
    assert normalized.count(b"in <ELAPSED>") == 2
    assert b"tests/test_x.py::test_failure" in normalized
    assert b"FAILED arbitrary failure text" in normalized
    assert b"7 failed, 2 passed" in normalized


def test_cli_resolves_repository_from_verifier_file_not_caller_cwd(
    evidence_repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _document(evidence_repository)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(verifier, "REPOSITORY_ROOT", evidence_repository)

    assert verifier.main(["verify", "--rerun", str(document)], runner=_successful_runner()) == 0
    assert os.getcwd() == str(tmp_path)


def test_rendered_payload_is_canonical_and_rejects_duplicate_json_keys(
    evidence_repository: Path,
) -> None:
    document = _document(evidence_repository)
    payload = _payload(document)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert canonical in document.read_text(encoding="utf-8")

    duplicate = canonical[:-1] + ',"schema_version":"2"}'
    document.write_text(
        f"{verifier.START_SENTINEL}\n{duplicate}\n{verifier.END_SENTINEL}\n",
        encoding="utf-8",
    )
    with pytest.raises(verifier.EvidenceError):
        verifier.verify_evidence(
            document, evidence_repository, rerun=True, runner=_successful_runner()
        )
