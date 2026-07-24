"""Mutation coverage for the dependency-free Phase 4 action-audit verifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / ".planning/phases/04-controlled-draft-pr/04-ACTION-AUDIT.md"
VERIFIER = ROOT / "tools/verify_phase4_action_audit.py"
SPEC = importlib.util.spec_from_file_location("phase4_action_audit", VERIFIER)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _mutated(tmp_path: Path, before: str, after: str) -> Path:
    text = AUDIT.read_text(encoding="utf-8")
    prefix, audit = text.split("<!-- phase4-action-audit\n", 1)
    assert before in audit
    path = tmp_path / "audit.md"
    path.write_text(prefix + "<!-- phase4-action-audit\n" + audit.replace(before, after, 1), encoding="utf-8")
    return path


def test_original_audit_passes() -> None:
    MODULE.verify_audit(AUDIT)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("actions/checkout", "evil/checkout"),
        ("197814629", "197814628"),
        ("11bd71901bbe5b1630ceea73d27597364c9af683", "0" * 40),
        ("d0af3a2e48f72b25f2c8a4ce85f9a86058d7eaa7", "1" * 40),
        ("bc93395a4a6f2a012c91c40c3bf642d4217b8e76e5a25d9310a8a4ed1fa53238", "2" * 64),
        ("\"non_authoritative\":true", "\"non_authoritative\":false"),
        ("\"resolved\":true,\"executable_hooks\":[]", "\"resolved\":false,\"executable_hooks\":[]"),
        ("\"status\":\"audited_not_approved\"", "\"status\":\"approved\""),
    ],
)
def test_authority_mutations_fail(tmp_path: Path, before: str, after: str) -> None:
    with pytest.raises(MODULE.AuditError):
        MODULE.verify_audit(_mutated(tmp_path, before, after))


def test_unresolved_nested_action_fails(tmp_path: Path) -> None:
    path = _mutated(
        tmp_path,
        '"nested_actions":[]',
        '"nested_actions":[{"uses":"evil/action@v1","commit_sha":"' + "a" * 40 + '","resolved":false}]',
    )
    with pytest.raises(MODULE.AuditError):
        MODULE.verify_audit(path)


def test_unresolved_claim_fails(tmp_path: Path) -> None:
    path = _mutated(tmp_path, '"unresolved_claims":[]', '"unresolved_claims":["not reviewed"]')
    with pytest.raises(MODULE.AuditError):
        MODULE.verify_audit(path)
