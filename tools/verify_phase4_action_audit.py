#!/usr/bin/env python3
"""Offline consistency verification for the Phase 4 GitHub Action audit.

This verifier deliberately reads one bounded, local Markdown file.  It has no
project imports, network client, subprocess use, or file-writing behaviour.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


AUDIT_PATH = Path(".planning/phases/04-controlled-draft-pr/04-ACTION-AUDIT.md")
MAX_AUDIT_BYTES = 65_536
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED = (
    ("actions/checkout", 197814629, "11bd71901bbe5b1630ceea73d27597364c9af683"),
    (
        "actions/create-github-app-token",
        595047935,
        "67018539274d69449ef7c8cde82c3ff073ffe3b5",
    ),
)


class AuditError(ValueError):
    """The fixed audit contract is incomplete, mutable, or non-authorizing."""


def _require(condition: bool) -> None:
    if not condition:
        raise AuditError("phase4 action audit invalid")


def _text(path: Path) -> str:
    payload = path.read_bytes()
    _require(len(payload) <= MAX_AUDIT_BYTES)
    return payload.decode("utf-8")


def _audit(text: str) -> dict[str, Any]:
    match = re.search(r"<!-- phase4-action-audit\n(.*?)\n-->", text, re.DOTALL)
    _require(match is not None)
    value = json.loads(match.group(1))
    _require(isinstance(value, dict))
    return value


def _digest(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _sha(value: object) -> bool:
    return isinstance(value, str) and SHA1.fullmatch(value) is not None


def _verify_action(action: object, expected: tuple[str, int, str]) -> None:
    _require(isinstance(action, dict))
    repository, repository_id, candidate = expected
    _require(action.get("repository_full_name") == repository)
    _require(action.get("repository_id") == repository_id)
    _require(action.get("candidate_commit_sha") == candidate)
    _require(_sha(action.get("tree_sha")))
    tag = action.get("release_tag_metadata")
    _require(isinstance(tag, dict) and tag.get("non_authoritative") is True)
    _require(isinstance(tag.get("name"), str) and tag["name"].startswith("v"))
    _require(tag.get("authority") == "candidate_commit_sha_only")
    files = action.get("evidence_files")
    _require(isinstance(files, list) and len(files) >= 2)
    for evidence in files:
        _require(isinstance(evidence, dict))
        _require(isinstance(evidence.get("path"), str) and evidence["path"])
        _require(_digest(evidence.get("sha256")))
        _require(evidence.get("read_only") is True)
    _require(isinstance(action.get("runtime"), dict))
    _require(isinstance(action["runtime"].get("using"), str))
    _require(isinstance(action.get("permissions"), dict))
    _require(isinstance(action["permissions"].get("required"), list))
    nested = action.get("nested_actions")
    _require(isinstance(nested, list))
    for item in nested:
        _require(isinstance(item, dict))
        _require(isinstance(item.get("uses"), str) and "@" in item["uses"])
        _require(_sha(item.get("commit_sha")))
        _require(item.get("resolved") is True)
    hooks = action.get("install_hooks")
    _require(isinstance(hooks, dict) and hooks.get("resolved") is True)
    _require(hooks.get("executable_hooks") == [])
    _require(action.get("unresolved_claims") == [])
    _require(isinstance(action.get("behaviour"), dict))
    _require(isinstance(action["behaviour"].get("network"), str))
    _require(isinstance(action["behaviour"].get("code_execution"), str))
    _require(isinstance(action.get("provenance"), dict))
    _require(_digest(action["provenance"].get("release_metadata_sha256")))


def verify_audit(path: Path = AUDIT_PATH) -> None:
    audit = _audit(_text(path))
    _require(audit.get("status") == "audited_not_approved")
    _require(audit.get("approval") == "human_gate_a4_required")
    actions = audit.get("actions")
    _require(isinstance(actions, list) and len(actions) == len(EXPECTED))
    for action, expected in zip(actions, EXPECTED, strict=True):
        _verify_action(action, expected)
    candidates = audit.get("candidate_sha_set")
    _require(candidates == [expected[2] for expected in EXPECTED])


def main() -> int:
    try:
        verify_audit()
    except (AuditError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        print("phase4 action audit invalid")
        return 1
    print("phase4 action audit valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
