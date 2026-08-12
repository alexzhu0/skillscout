#!/usr/bin/env python3
"""Offline consistency verification for the Phase 4 GitHub Action audit.

This verifier deliberately reads one bounded, local Markdown file.  It has no
project imports, network client, subprocess use, or file-writing behaviour.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


AUDIT_PATH = Path("evidence/phase-4-controlled-draft-pr/04-ACTION-AUDIT.md")
MAX_AUDIT_BYTES = 65_536
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED = (
    {
        "repository_full_name": "actions/checkout",
        "repository_id": 197814629,
        "candidate_commit_sha": "11bd71901bbe5b1630ceea73d27597364c9af683",
        "tree_sha": "d0af3a2e48f72b25f2c8a4ce85f9a86058d7eaa7",
        "evidence_digests": (
            "bc93395a4a6f2a012c91c40c3bf642d4217b8e76e5a25d9310a8a4ed1fa53238",
            "f1cb3bcd79e4c95fc8ce4e199621292aeaa5735f8d2e55223dd4213f8194cd85",
            "9d22852010dc49a5c8f0a02c3c4b10a4bb3b5e9dce832cb1d1a77b2235bb879f",
        ),
    },
    {
        "repository_full_name": "actions/create-github-app-token",
        "repository_id": 595047935,
        "candidate_commit_sha": "67018539274d69449ef7c8cde82c3ff073ffe3b5",
        "tree_sha": "eb5e5fc0e85f5c1c4d03aa0c0c51e6fb3e8e6ff8",
        "evidence_digests": (
            "71bb6500e20692e2f80c4af422513e6090f5b6d1c68c05b00be30d74272608a0",
            "eafcab61783827354cc3fbaa6b1c14e1db4cb6a34b7fe5e99ca78325a5d30ea6",
            "00c3762ec818e5f451b69c62a9d55d1ab0ace44bb177678b4ca1db4f5cbfc3a5",
        ),
    },
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


def _verify_action(action: object, expected: dict[str, object]) -> None:
    _require(isinstance(action, dict))
    _require(action.get("repository_full_name") == expected["repository_full_name"])
    _require(action.get("repository_id") == expected["repository_id"])
    _require(action.get("candidate_commit_sha") == expected["candidate_commit_sha"])
    _require(action.get("tree_sha") == expected["tree_sha"])
    tag = action.get("release_tag_metadata")
    _require(isinstance(tag, dict) and tag.get("non_authoritative") is True)
    _require(isinstance(tag.get("name"), str) and tag["name"].startswith("v"))
    _require(tag.get("authority") == "candidate_commit_sha_only")
    files = action.get("evidence_files")
    _require(isinstance(files, list) and len(files) >= 2)
    observed_digests = []
    for evidence in files:
        _require(isinstance(evidence, dict))
        _require(isinstance(evidence.get("path"), str) and evidence["path"])
        _require(_digest(evidence.get("sha256")))
        _require(evidence.get("read_only") is True)
        observed_digests.append(evidence["sha256"])
    _require(tuple(observed_digests) == expected["evidence_digests"])
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
    _require(candidates == [expected["candidate_commit_sha"] for expected in EXPECTED])


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
