#!/usr/bin/env python3
"""Validate Phase 1 gap evidence without importing project code."""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"
START_SENTINEL = "<!-- phase1-gap-evidence-json:start -->"
END_SENTINEL = "<!-- phase1-gap-evidence-json:end -->"
MAX_DOCUMENT_BYTES = 1_000_000
LOCK_HASH = "caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32"
FROZEN_DB_HASH = "49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251"
EXPECTED_FINDINGS = tuple(
    [f"CR-{number:02d}" for number in range(1, 9)]
    + [f"WR-{number:02d}" for number in range(1, 4)]
)
EXPECTED_COMMANDS = (
    "packaged_cli",
    "mapping_capability",
    "focused_findings",
    "phase1_collect",
    "full_pytest",
    "ruff",
    "lock_check",
    "build",
)
EXPECTED_TOP_LEVEL = {
    "schema_version",
    "hashes",
    "commands",
    "roots",
    "findings",
    "cli_facts",
    "wr_04",
}
EXPECTED_CLI_FACTS: dict[str, dict[str, object]] = {
    "happy_resume_inspect": {
        "structured": True,
        "verified": True,
        "stage_count": 9,
        "reused_stage_count": 6,
        "remote_writes_attempted": 0,
        "disclosure_canary_present": False,
    },
    "changed_a_prime": {
        "distinct_runs": True,
        "dual_inspect_verified": True,
        "new_run_reused_stage_count": 0,
        "remote_writes_attempted": 0,
    },
    "a_b_a": {
        "exact_a_resumed": True,
        "reused_stage_count": 6,
        "b_rows_unchanged": True,
        "b_manifest_bytes_unchanged": True,
        "remote_writes_attempted": 0,
    },
}


class EvidenceError(Exception):
    """Closed internal failure for invalid evidence."""


def _require(condition: bool) -> None:
    if not condition:
        raise EvidenceError


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(131_072):
            digest.update(chunk)
    return digest.hexdigest()


def _read_document(path: Path) -> str:
    metadata = path.lstat()
    _require(stat.S_ISREG(metadata.st_mode) and metadata.st_size <= MAX_DOCUMENT_BYTES)
    raw = path.read_bytes()
    _require(len(raw) <= MAX_DOCUMENT_BYTES)
    return raw.decode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError
        result[key] = value
    return result


def _extract_payload(document: str) -> dict[str, Any]:
    _require(document.count(START_SENTINEL) == 1)
    _require(document.count(END_SENTINEL) == 1)
    before, remainder = document.split(START_SENTINEL, 1)
    enclosed, after = remainder.split(END_SENTINEL, 1)
    del before, after
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
        ensure_ascii=False,
        allow_nan=False,
    )
    _require(encoded == canonical)
    return payload


def _require_exact_keys(value: object, expected: set[str]) -> dict[str, Any]:
    _require(isinstance(value, dict))
    mapping = value
    _require(set(mapping) == expected)
    return mapping


def _validate_hashes(value: object, repository_root: Path) -> None:
    hashes = _require_exact_keys(value, {"uv_lock", "frozen_v1_db"})
    expected = {
        "uv_lock": ("uv.lock", LOCK_HASH),
        "frozen_v1_db": ("tests/fixtures/state/v1-cli.db", FROZEN_DB_HASH),
    }
    for identifier, (path, digest) in expected.items():
        record = _require_exact_keys(
            hashes[identifier], {"path", "expected", "pre", "post"}
        )
        _require(record == {"path": path, "expected": digest, "pre": digest, "post": digest})
        _require(_sha256(repository_root / path) == digest)


def _validate_count(value: object, *, kind: str, exact: int | None = None) -> int:
    count = _require_exact_keys(value, {"kind", "value"})
    _require(count["kind"] == kind)
    number = count["value"]
    _require(type(number) is int and number > 0)
    if exact is not None:
        _require(number == exact)
    return number


def _validate_commands(value: object) -> None:
    _require(isinstance(value, list))
    commands = value
    _require(len(commands) == len(EXPECTED_COMMANDS))
    counts: dict[str, int] = {}
    for index, expected_id in enumerate(EXPECTED_COMMANDS):
        command = _require_exact_keys(
            commands[index], {"id", "argv_summary", "exit_code", "count"}
        )
        _require(command["id"] == expected_id)
        _require(command["exit_code"] == 0 and type(command["exit_code"]) is int)
        summary = command["argv_summary"]
        _require(
            type(summary) is str
            and 1 <= len(summary) <= 500
            and summary.isascii()
            and "verify_phase1_gap_evidence" not in summary
        )
        if expected_id == "packaged_cli":
            counts[expected_id] = _validate_count(command["count"], kind="passed", exact=3)
        elif expected_id == "mapping_capability":
            counts[expected_id] = _validate_count(command["count"], kind="passed", exact=2)
        elif expected_id in {"focused_findings", "full_pytest"}:
            counts[expected_id] = _validate_count(command["count"], kind="passed")
        elif expected_id == "phase1_collect":
            counts[expected_id] = _validate_count(command["count"], kind="collected")
        elif expected_id in {"ruff", "lock_check"}:
            counts[expected_id] = _validate_count(command["count"], kind="checks", exact=1)
        else:
            counts[expected_id] = _validate_count(command["count"], kind="artifacts", exact=2)
    _require(counts["focused_findings"] + 5 == counts["phase1_collect"])
    _require(counts["phase1_collect"] == counts["full_pytest"])


def _validate_node_matrix(value: object, expected_keys: tuple[str, ...]) -> None:
    _require(isinstance(value, dict))
    matrix = value
    _require(tuple(matrix) == expected_keys)
    for key in expected_keys:
        record = _require_exact_keys(matrix[key], {"status", "nodes"})
        _require(record["status"] == "pass")
        nodes = record["nodes"]
        _require(isinstance(nodes, list) and bool(nodes))
        _require(len(nodes) == len(set(nodes)))
        _require(
            all(
                type(node) is str
                and node.startswith("tests/test_")
                and ".py::test_" in node
                and "verify_phase1_gap_evidence" not in node
                for node in nodes
            )
        )


def _validate_cli_facts(value: object) -> None:
    facts = _require_exact_keys(value, set(EXPECTED_CLI_FACTS))
    _require(facts == EXPECTED_CLI_FACTS)


def _validate(payload: dict[str, Any], repository_root: Path) -> None:
    _require(set(payload) == EXPECTED_TOP_LEVEL)
    _require(payload["schema_version"] == SCHEMA_VERSION)
    _validate_hashes(payload["hashes"], repository_root)
    _validate_commands(payload["commands"])
    _validate_node_matrix(payload["roots"], ("1", "2", "3", "4"))
    _validate_node_matrix(payload["findings"], EXPECTED_FINDINGS)
    _validate_cli_facts(payload["cli_facts"])
    _require(
        payload["wr_04"] == {"status": "deferred", "addressed_in": "Phase 6"}
    )


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("phase1 gap evidence invalid", file=sys.stderr)
        return 2
    try:
        document = _read_document(Path(argv[0]))
        payload = _extract_payload(document)
        _validate(payload, Path(__file__).resolve().parents[1])
    except (EvidenceError, OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        print("phase1 gap evidence invalid", file=sys.stderr)
        return 1
    print("phase1 gap evidence valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
