"""Run one bounded, experiment-only workflow-selection trial."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from time import monotonic
from typing import Any, Iterator
from urllib.parse import quote

import openai
from pydantic import ValidationError

from skillscout.adapters.openai_extract import (
    EVIDENCE_SELECTION_INSTRUCTIONS_V1,
    MAX_EVIDENCE_SELECTION_INPUT_BYTES,
    MAX_EXTRACT_OUTPUT_TOKENS,
    SOURCE_ONLY_FIELDS_SUFFIX,
)
from skillscout.adapters.semantic_provider import (
    DEEPSEEK_CURRENT_FLASH_MODEL,
    SemanticStage,
    create_semantic_client,
    deepseek_json_instructions,
    request_deepseek_json,
    resolve_local_preview_semantic_provider,
    response_token_usage,
)
from skillscout.domain.evidence_selection import (
    EvidenceCatalog,
    EvidenceSelectionError,
    EvidenceSelectionResponse,
    build_evidence_catalog,
    materialize_workflow,
)
from skillscout.domain.extraction import validate_workflow_boundaries

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_DATASET = REPOSITORY_ROOT / "tests/fixtures/workflow_selection/extraction_cases.json"
CAMPAIGN_ROOT = REPOSITORY_ROOT / ".tmp/useful-skill-loop-20260914/runtime"
HOLDOUT_MANIFEST_NAME = "holdout-manifest.json"
LEDGER_NAME = "ledger.sqlite3"
CAMPAIGN_ID = "useful-skill-loop-20260914"
LEDGER_SCHEMA_VERSION = "workflow-selection-trial-ledger-v1"
FROZEN_CANDIDATE_META_KEY = "frozen_candidate_marker_digest"
FROZEN_CANDIDATE_SCHEMA_VERSION = "useful-skill-frozen-candidate-v1"
MAX_JSON_BYTES = 65_536
MODEL = DEEPSEEK_CURRENT_FLASH_MODEL
PROFILES = ("baseline", "r1", "r2", "r3")
GROUP_CAPS = {"development": 28, "heldout": 12, "artifact": 3, "usefulness": 6}
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")

# Prompt revisions remain unusable until the controller preregisters each
# hypothesis and fills its selection-only suffix before viewing that round.
_R1_SELECTION_SUFFIX = """

Selection focus r1:
Select source-supported core AI reasoning, analysis, or verification procedures,
not the operational lifecycle of a demonstration. Exclude dependency preparation,
installation, service startup, teardown and source-program execution from every
returned workflow, including alternative workflows next to a useful core review.
When the source describes data processing together with an explicit reviewable
contract or check, select only that supported read-only review: describe the
processing as the design being examined, not as actions to perform. Do not invent
a review or missing procedure when the source supplies none; return no workflow.
Keep all workflow fields within that same read-only scope. Source statements
such as approved events describe prerequisites, never grant operator permission
or authority to execute, access resources, or write data. Assumptions must remain
uncertainties, not grants of authority. Record only source-supported approval
requirements; do not invent reviewers, approvals, environmental guarantees or
extra steps to fill schema fields. Use empty lists where evidence is absent.
"""
# Offline repair candidate, not permission to resume the frozen September 14 run.
# Reuse r1 unchanged; only evidence fidelity is a new experimental variable.
_R2_FIDELITY_SUFFIX = """

Evidence fidelity r2:
Preserve each supplied evidence source and its distinct role in the workflow.
Do not narrow or broaden which evidence may support a claim without explicit
source support. Different claim types may require different evidence sources;
a rule for one type must not become a rule for every claim. Missing support
remains unresolved, not invented or silently replaced by another source.
Keep reported, alleged, inferred and confirmed facts distinct. Preserve source
qualifiers and conditions on what may be retained, changed or approved.
Never upgrade a source assertion or an assumption into a verified fact, and
never infer source completeness, authority or universal applicability.
Apply these constraints to every authored field, including steps, outputs,
assumptions and evidence supports. Check them against the catalogue before
returning a workflow; omit a workflow that cannot be described faithfully.
"""
_FROZEN_SUFFIXES: dict[str, str | None] = {
    "baseline": "",
    "r1": _R1_SELECTION_SUFFIX,
    "r2": _R1_SELECTION_SUFFIX + _R2_FIDELITY_SUFFIX,
    "r3": None,
    "source_only": SOURCE_ONLY_FIELDS_SUFFIX,
}


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _read_bounded_json(path: Path, *, error_message: str) -> tuple[object, str]:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_JSON_BYTES:
            raise ValueError
        raw = os.read(descriptor, MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES or len(raw) != info.st_size:
            raise ValueError
        parsed = json.loads(raw, object_pairs_hook=_unique_object)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        raise ValueError(error_message) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return parsed, _sha256(raw)


def read_dataset(path: Path) -> tuple[tuple[dict[str, object], ...], str]:
    """Read one regular bounded dataset, rejecting duplicate keys and IDs."""

    parsed, digest = _read_bounded_json(Path(path), error_message="invalid dataset")
    try:
        if type(parsed) is not dict or type(parsed.get("cases")) is not list:
            raise ValueError
        cases = parsed["cases"]
        if not cases or len(cases) > 64:
            raise ValueError
        seen: set[str] = set()
        validated: list[dict[str, object]] = []
        for case in cases:
            if type(case) is not dict:
                raise ValueError
            case_id = case.get("id")
            source_text = case.get("source_text")
            if (
                type(case_id) is not str
                or _CASE_ID.fullmatch(case_id) is None
                or case_id in seen
                or type(source_text) is not str
            ):
                raise ValueError
            seen.add(case_id)
            validated.append(case)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid dataset") from None
    return tuple(validated), digest


def prepare_case(case: Mapping[str, object]) -> EvidenceCatalog:
    """Build an inert catalogue from source text and no answer-key fields."""

    if not isinstance(case, Mapping) or type(case.get("source_text")) is not str:
        raise ValueError("invalid case")
    text = case["source_text"]
    raw = text.encode("utf-8")
    path = "SOURCE.md"
    return build_evidence_catalog(
        scope={"readme_path": path},
        path=path,
        blob_sha=hashlib.sha1(raw).hexdigest(),
        content_hash=_sha256(raw),
        text=text,
    )


def _profile_instructions(profile: str) -> str:
    if profile not in _FROZEN_SUFFIXES:
        raise ValueError("unknown profile")
    suffix = _FROZEN_SUFFIXES[profile]
    if suffix is None:
        raise ValueError("profile not frozen")
    return EVIDENCE_SELECTION_INSTRUCTIONS_V1 + suffix


def profile_prompt_digest(profile: str) -> str:
    """Return the digest of the exact trusted provider system content."""

    trusted = deepseek_json_instructions(_profile_instructions(profile), EvidenceSelectionResponse)
    return _sha256(trusted.encode("utf-8"))


def _read_holdout_manifest(path: Path) -> tuple[str, str]:
    parsed, manifest_digest = _read_bounded_json(path, error_message="invalid holdout manifest")
    try:
        if type(parsed) is not dict or set(parsed) != {
            "file_sha256",
            "byte_count",
            "case_count",
            "class_aggregate_counts",
            "origin",
        }:
            raise ValueError
        file_sha256 = parsed["file_sha256"]
        counts = parsed["class_aggregate_counts"]
        if (
            type(file_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", file_sha256) is None
            or type(parsed["byte_count"]) is not int
            or parsed["byte_count"] < 1
            or parsed["case_count"] != 6
            or type(counts) is not dict
            or set(counts) != {"select", "reject", "abstain"}
            or any(type(value) is not int or value < 0 for value in counts.values())
            or sum(counts.values()) != 6
            or type(parsed["origin"]) is not str
            or not parsed["origin"]
        ):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid holdout manifest") from None
    return manifest_digest, "sha256:" + file_sha256


def _connect_existing(root: Path) -> sqlite3.Connection:
    database = Path(root) / LEDGER_NAME
    try:
        root_info = root.lstat()
        database_info = database.lstat()
        if not stat.S_ISDIR(root_info.st_mode) or not stat.S_ISREG(database_info.st_mode):
            raise ValueError
        uri = f"file:{quote(str(database), safe='/')}?mode=rw"
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        row = connection.execute(
            "SELECT value FROM campaign_meta WHERE key = 'schema_version'"
        ).fetchone()
        if row != (LEDGER_SCHEMA_VERSION,):
            connection.close()
            raise ValueError
        return connection
    except (OSError, sqlite3.Error, ValueError):
        raise ValueError("campaign state missing or invalid") from None


@contextmanager
def _transaction(root: Path) -> Iterator[sqlite3.Connection]:
    connection = _connect_existing(root)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_campaign(root: Path) -> None:
    """Create the one exclusive runtime directory and frozen 49-slot ledger."""

    root = Path(root)
    cases, development_digest = read_dataset(DEVELOPMENT_DATASET)
    if len(cases) != 7:
        raise ValueError("invalid development manifest")
    holdout_manifest_digest, holdout_dataset_digest = _read_holdout_manifest(
        root.parent / HOLDOUT_MANIFEST_NAME
    )
    root.mkdir(mode=0o700)
    database = root / LEDGER_NAME
    connection = sqlite3.connect(database, isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE campaign_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) WITHOUT ROWID;
            CREATE TABLE allocations (
                group_name TEXT PRIMARY KEY,
                cap INTEGER NOT NULL CHECK (cap > 0)
            ) WITHOUT ROWID;
            CREATE TABLE allowed_slots (
                group_name TEXT NOT NULL REFERENCES allocations(group_name),
                slot TEXT NOT NULL,
                profile TEXT,
                case_key TEXT,
                expected_input_digest TEXT,
                PRIMARY KEY (group_name, slot)
            ) WITHOUT ROWID;
            CREATE TABLE profile_bindings (
                profile TEXT PRIMARY KEY,
                prompt_digest TEXT NOT NULL,
                model TEXT NOT NULL
            ) WITHOUT ROWID;
            CREATE TABLE reservations (
                group_name TEXT NOT NULL,
                slot TEXT NOT NULL,
                input_digest TEXT NOT NULL,
                prompt_digest TEXT NOT NULL,
                model TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('in_flight', 'decided')),
                outcome TEXT,
                result_json TEXT,
                PRIMARY KEY (group_name, slot),
                FOREIGN KEY (group_name, slot) REFERENCES allowed_slots(group_name, slot)
            ) WITHOUT ROWID;
            """
        )
        metadata = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "campaign_id": CAMPAIGN_ID,
            "development_dataset_digest": development_digest,
            "heldout_manifest_digest": holdout_manifest_digest,
            "heldout_dataset_digest": holdout_dataset_digest,
            "baseline_prompt_digest": profile_prompt_digest("baseline"),
        }
        connection.executemany(
            "INSERT INTO campaign_meta(key, value) VALUES (?, ?)", metadata.items()
        )
        connection.executemany(
            "INSERT INTO allocations(group_name, cap) VALUES (?, ?)", GROUP_CAPS.items()
        )
        development_rows: list[tuple[object, ...]] = []
        for case in cases:
            case_id = str(case["id"])
            input_digest = prepare_case(case).digest
            for profile in PROFILES:
                development_rows.append(
                    (
                        "development",
                        f"{profile}:{case_id}",
                        profile,
                        f"development:{case_id}",
                        input_digest,
                    )
                )
        connection.executemany(
            """INSERT INTO allowed_slots(
                   group_name, slot, profile, case_key, expected_input_digest
               ) VALUES (?, ?, ?, ?, ?)""",
            development_rows,
        )
        connection.executemany(
            """INSERT INTO allowed_slots(
                   group_name, slot, profile, case_key, expected_input_digest
               ) VALUES (?, ?, ?, ?, NULL)""",
            (
                ("heldout", f"{profile}:h{index:02d}", profile, f"heldout:h{index:02d}")
                for profile in ("baseline", "candidate")
                for index in range(1, 7)
            ),
        )
        connection.executemany(
            "INSERT INTO allowed_slots(group_name, slot) VALUES ('artifact', ?)",
            ((slot,) for slot in ("extraction", "generation", "review")),
        )
        connection.executemany(
            "INSERT INTO allowed_slots(group_name, slot) VALUES ('usefulness', ?)",
            (
                (f"task-{index}:{variant}",)
                for index in range(1, 4)
                for variant in ("without-skill", "with-skill")
            ),
        )
        connection.execute(
            "INSERT INTO profile_bindings(profile, prompt_digest, model) VALUES (?, ?, ?)",
            ("baseline", profile_prompt_digest("baseline"), MODEL),
        )
        for group_name, cap in GROUP_CAPS.items():
            count = connection.execute(
                "SELECT COUNT(*) FROM allowed_slots WHERE group_name = ?", (group_name,)
            ).fetchone()[0]
            if count != cap:
                raise ValueError("invalid slot manifest")
        connection.commit()
        os.chmod(database, 0o600)
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _require_digest(value: object) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError("invalid digest")
    return value


def bind_frozen_candidate(root: Path, marker_path: Path) -> None:
    """Bind one controller-approved candidate without reading held-out source."""

    parsed, marker_digest = _read_bounded_json(
        Path(marker_path), error_message="invalid frozen candidate marker"
    )
    expected_keys = {
        "schema_version",
        "campaign_id",
        "candidate_profile",
        "model",
        "candidate_prompt_digest",
        "baseline_prompt_digest",
        "development_dataset_digest",
        "heldout_dataset_digest",
        "heldout_manifest_digest",
        "development_result",
        "selection_reason",
        "controller_heldout_sources_read",
        "no_further_development_tuning",
    }
    if type(parsed) is not dict or set(parsed) != expected_keys:
        raise ValueError("invalid frozen candidate marker")
    try:
        candidate_profile = parsed["candidate_profile"]
        candidate_prompt_digest = _require_digest(parsed["candidate_prompt_digest"])
        baseline_prompt_digest = _require_digest(parsed["baseline_prompt_digest"])
        development_dataset_digest = _require_digest(parsed["development_dataset_digest"])
        heldout_dataset_digest = _require_digest(parsed["heldout_dataset_digest"])
        heldout_manifest_digest = _require_digest(parsed["heldout_manifest_digest"])
        development_result = parsed["development_result"]
        if (
            parsed["schema_version"] != FROZEN_CANDIDATE_SCHEMA_VERSION
            or parsed["campaign_id"] != CAMPAIGN_ID
            or type(candidate_profile) is not str
            or candidate_profile == "baseline"
            or candidate_profile not in PROFILES
            or parsed["model"] != MODEL
            or candidate_prompt_digest != profile_prompt_digest(candidate_profile)
            or baseline_prompt_digest != profile_prompt_digest("baseline")
            or type(development_result) is not dict
            or set(development_result)
            != {"baseline_passed", "candidate_passed", "case_count", "requests_consumed"}
            or any(type(value) is not int for value in development_result.values())
            or not 0 <= development_result["baseline_passed"] < 7
            or development_result["candidate_passed"] != 7
            or development_result["case_count"] != 7
            or development_result["requests_consumed"] != 14
            or type(parsed["selection_reason"]) is not str
            or not parsed["selection_reason"].strip()
            or parsed["controller_heldout_sources_read"] is not False
            or parsed["no_further_development_tuning"] is not True
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid frozen candidate marker") from None
    with _transaction(Path(root)) as connection:
        if (
            connection.execute(
                "SELECT 1 FROM campaign_meta WHERE key = ?", (FROZEN_CANDIDATE_META_KEY,)
            ).fetchone()
            is not None
            or connection.execute(
                "SELECT 1 FROM profile_bindings WHERE profile = 'candidate'"
            ).fetchone()
            is not None
        ):
            raise ValueError("campaign already frozen")
        metadata = dict(connection.execute("SELECT key, value FROM campaign_meta"))
        if (
            metadata.get("campaign_id") != CAMPAIGN_ID
            or metadata.get("development_dataset_digest") != development_dataset_digest
            or metadata.get("heldout_dataset_digest") != heldout_dataset_digest
            or metadata.get("heldout_manifest_digest") != heldout_manifest_digest
            or metadata.get("baseline_prompt_digest") != baseline_prompt_digest
        ):
            raise ValueError("invalid frozen candidate marker")
        bindings = {
            profile: (prompt_digest, model)
            for profile, prompt_digest, model in connection.execute(
                "SELECT profile, prompt_digest, model FROM profile_bindings"
            )
        }
        expected_bindings = {
            "baseline": (baseline_prompt_digest, MODEL),
            candidate_profile: (candidate_prompt_digest, MODEL),
        }
        rows = connection.execute(
            """SELECT r.group_name, a.profile, r.input_digest,
                      a.expected_input_digest, r.prompt_digest, r.model,
                      r.state, r.outcome
                 FROM reservations AS r
                 JOIN allowed_slots AS a
                   ON a.group_name = r.group_name AND a.slot = r.slot"""
        ).fetchall()
        profile_counts = {
            profile: sum(row[1] == profile for row in rows)
            for profile in ("baseline", candidate_profile)
        }
        if (
            len(rows) != 14
            or profile_counts != {"baseline": 7, candidate_profile: 7}
            or any(row[0] != "development" for row in rows)
            or any(row[1] not in expected_bindings for row in rows)
            or any(row[2] != row[3] or row[3] is None for row in rows)
            or any((row[4], row[5]) != expected_bindings[row[1]] for row in rows)
            or any(row[6] != "decided" for row in rows)
            or any(row[7] not in {"admitted", "no_workflows"} for row in rows)
            or any(
                bindings.get(profile) != binding for profile, binding in expected_bindings.items()
            )
        ):
            raise ValueError("invalid development history")
        connection.execute(
            "INSERT INTO campaign_meta(key, value) VALUES (?, ?)",
            (FROZEN_CANDIDATE_META_KEY, marker_digest),
        )
        connection.execute(
            "INSERT INTO profile_bindings(profile, prompt_digest, model) VALUES (?, ?, ?)",
            ("candidate", candidate_prompt_digest, MODEL),
        )


def reserve_slot(
    root: Path,
    group: str,
    slot: str,
    input_digest: str,
    prompt_digest: str,
    model: str,
) -> None:
    """Durably consume one frozen slot; every replay fails closed."""

    input_digest = _require_digest(input_digest)
    prompt_digest = _require_digest(prompt_digest)
    if type(group) is not str or type(slot) is not str or type(model) is not str:
        raise ValueError("invalid reservation")
    with _transaction(Path(root)) as connection:
        allocation = connection.execute(
            "SELECT cap FROM allocations WHERE group_name = ?", (group,)
        ).fetchone()
        if allocation is None:
            raise ValueError("unknown allocation")
        marker_bound = (
            connection.execute(
                "SELECT 1 FROM campaign_meta WHERE key = ?", (FROZEN_CANDIDATE_META_KEY,)
            ).fetchone()
            is not None
        )
        candidate_bound = (
            connection.execute(
                "SELECT 1 FROM profile_bindings WHERE profile = 'candidate'"
            ).fetchone()
            is not None
        )
        if marker_bound != candidate_bound:
            raise ValueError("candidate freeze invalid")
        if group == "development" and marker_bound:
            raise ValueError("development closed after freeze")
        if group == "heldout" and not marker_bound:
            raise ValueError("candidate not frozen")
        used = connection.execute(
            "SELECT COUNT(*) FROM reservations WHERE group_name = ?", (group,)
        ).fetchone()[0]
        if used >= allocation[0]:
            raise ValueError("allocation exhausted")
        allowed = connection.execute(
            """SELECT profile, case_key, expected_input_digest
               FROM allowed_slots WHERE group_name = ? AND slot = ?""",
            (group, slot),
        ).fetchone()
        if allowed is None:
            raise ValueError("unknown slot")
        if (
            connection.execute(
                "SELECT 1 FROM reservations WHERE group_name = ? AND slot = ?", (group, slot)
            ).fetchone()
            is not None
        ):
            raise ValueError("slot already reserved")
        if (
            connection.execute(
                "SELECT 1 FROM reservations WHERE state = 'in_flight' LIMIT 1"
            ).fetchone()
            is not None
        ):
            raise ValueError("campaign has in-flight reservation")
        profile, case_key, expected_input = allowed
        if expected_input is not None and input_digest != expected_input:
            raise ValueError("input identity mismatch")
        if profile is not None:
            if model != MODEL:
                raise ValueError("model identity mismatch")
            binding = connection.execute(
                "SELECT prompt_digest, model FROM profile_bindings WHERE profile = ?",
                (profile,),
            ).fetchone()
            if binding is None:
                if group == "heldout":
                    raise ValueError("prompt identity mismatch")
                connection.execute(
                    "INSERT INTO profile_bindings(profile, prompt_digest, model) VALUES (?, ?, ?)",
                    (profile, prompt_digest, model),
                )
            elif binding != (prompt_digest, model):
                raise ValueError("prompt identity mismatch")
        if case_key is not None:
            bindings = {
                row[0]
                for row in connection.execute(
                    "SELECT expected_input_digest FROM allowed_slots WHERE case_key = ?",
                    (case_key,),
                )
                if row[0] is not None
            }
            if not bindings:
                connection.execute(
                    "UPDATE allowed_slots SET expected_input_digest = ? WHERE case_key = ?",
                    (input_digest, case_key),
                )
            elif bindings != {input_digest}:
                raise ValueError("input identity mismatch")
        connection.execute(
            """INSERT INTO reservations(
                   group_name, slot, input_digest, prompt_digest, model, state
               ) VALUES (?, ?, ?, ?, ?, 'in_flight')""",
            (group, slot, input_digest, prompt_digest, model),
        )


def _zero_request_result(
    outcome: str, *, input_digest: str, prompt_digest: str
) -> dict[str, object]:
    return {
        "experiment_only": True,
        "outcome": outcome,
        "workflows": [],
        "usage": None,
        "latency_ms": 0,
        "digests": {"input": input_digest, "prompt": prompt_digest},
    }


def _frozen_heldout_profile(root: Path, variant: str) -> tuple[str, str]:
    if variant not in {"baseline", "candidate"}:
        raise ValueError("invalid held-out variant")
    connection = _connect_existing(Path(root))
    try:
        marker = connection.execute(
            "SELECT value FROM campaign_meta WHERE key = ?", (FROZEN_CANDIDATE_META_KEY,)
        ).fetchone()
        if marker is None:
            raise ValueError("candidate not frozen")
        _require_digest(marker[0])
        expected_dataset_digest = connection.execute(
            "SELECT value FROM campaign_meta WHERE key = 'heldout_dataset_digest'"
        ).fetchone()
        if expected_dataset_digest is None:
            raise ValueError("frozen binding invalid")
        heldout_dataset_digest = _require_digest(expected_dataset_digest[0])
        bindings = {
            profile: (prompt_digest, model)
            for profile, prompt_digest, model in connection.execute(
                "SELECT profile, prompt_digest, model FROM profile_bindings"
            )
        }
        baseline_digest = profile_prompt_digest("baseline")
        if bindings.get("baseline") != (baseline_digest, MODEL):
            raise ValueError("frozen binding invalid")
        candidate_binding = bindings.get("candidate")
        matches = [
            profile
            for profile in PROFILES
            if profile != "baseline"
            and _FROZEN_SUFFIXES[profile] is not None
            and (profile_prompt_digest(profile), MODEL) == candidate_binding
            and bindings.get(profile) == candidate_binding
        ]
        if len(matches) != 1:
            raise ValueError("frozen binding invalid")
        return (
            ("baseline" if variant == "baseline" else matches[0]),
            heldout_dataset_digest,
        )
    finally:
        connection.close()


def run_heldout_case(
    root: Path,
    dataset_path: Path,
    case_id: str,
    variant: str,
    *,
    http_client: Any = None,
    api_key: str | None = None,
) -> dict[str, object]:
    """Run one frozen held-out case after verifying campaign bindings."""

    profile, expected_dataset_digest = _frozen_heldout_profile(Path(root), variant)
    cases, dataset_digest = read_dataset(Path(dataset_path))
    if dataset_digest != expected_dataset_digest:
        raise ValueError("held-out dataset identity mismatch")
    if tuple(item["id"] for item in cases) != tuple(f"h{index:02d}" for index in range(1, 7)):
        raise ValueError("invalid held-out case manifest")
    case = next((item for item in cases if item["id"] == case_id), None)
    if case is None:
        raise ValueError("invalid held-out case")
    return _run_case(
        Path(root),
        case,
        profile,
        group="heldout",
        slot_profile=variant,
        http_client=http_client,
        api_key=api_key,
    )


def _finalize(root: Path, group: str, slot: str, outcome: str, result: dict[str, object]) -> None:
    with _transaction(root) as connection:
        cursor = connection.execute(
            """UPDATE reservations SET state = 'decided', outcome = ?, result_json = ?
               WHERE group_name = ? AND slot = ? AND state = 'in_flight'""",
            (
                outcome,
                json.dumps(result, sort_keys=True, separators=(",", ":")),
                group,
                slot,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("reservation state invalid")


def _run_case(
    root: Path,
    case: Mapping[str, object],
    profile: str,
    *,
    group: str,
    slot_profile: str,
    http_client: Any = None,
    api_key: str | None = None,
) -> dict[str, object]:
    """Run one selected case through the shared guarded request path."""

    instructions = _profile_instructions(profile)
    if type(api_key) is not str or not api_key:
        raise ValueError("credential missing")
    case_id = case.get("id") if isinstance(case, Mapping) else None
    if type(case_id) is not str or _CASE_ID.fullmatch(case_id) is None:
        raise ValueError("invalid case")
    catalog = prepare_case(case)
    prompt_digest = profile_prompt_digest(profile)
    if not catalog.entries:
        return _zero_request_result(
            "empty_catalogue", input_digest=catalog.digest, prompt_digest=prompt_digest
        )
    trusted = deepseek_json_instructions(instructions, EvidenceSelectionResponse)
    if (
        len(trusted.encode("utf-8")) + len(catalog.user_payload().encode("utf-8"))
        > MAX_EVIDENCE_SELECTION_INPUT_BYTES
    ):
        return _zero_request_result(
            "input_too_large", input_digest=catalog.digest, prompt_digest=prompt_digest
        )

    settings = resolve_local_preview_semantic_provider(
        {
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        },
        current_flash=True,
    )
    client = create_semantic_client(settings, sdk=openai, api_key=api_key, http_client=http_client)
    slot = f"{slot_profile}:{case_id}"
    try:
        reserve_slot(root, group, slot, catalog.digest, prompt_digest, MODEL)
        started = monotonic()
        response = request_deepseek_json(
            client,
            sdk=openai,
            stage=SemanticStage.EXTRACTION,
            model=MODEL,
            instructions=instructions,
            user_payload=catalog.user_payload(),
            response_model=EvidenceSelectionResponse,
            max_tokens=MAX_EXTRACT_OUTPUT_TOKENS,
        )
        latency_ms = max(0, int((monotonic() - started) * 1_000))
    finally:
        client.close()

    admitted: list[dict[str, object]] = []
    if response.status == "parsed" and response.parsed is not None:
        source_text = case["source_text"]
        source_sha = catalog.entries[0].blob_sha
        for selected in response.parsed.workflows:
            try:
                workflow = materialize_workflow(selected, catalog)
            except (EvidenceSelectionError, ValidationError, ValueError):
                continue
            if not validate_workflow_boundaries(
                workflow,
                bundle_texts={"SOURCE.md": source_text},
                recorded={"SOURCE.md": source_sha},
            ):
                admitted.append(workflow.model_dump(mode="json"))
        if admitted:
            outcome = "admitted"
        elif response.parsed.workflows:
            outcome = "mechanically_rejected"
        else:
            outcome = "no_workflows"
    else:
        outcome = response.status
    usage = response_token_usage(response)
    request_id = (
        response.request_id
        if type(response.request_id) is str
        and _SAFE_REQUEST_ID.fullmatch(response.request_id) is not None
        else None
    )
    result: dict[str, object] = {
        "experiment_only": True,
        "outcome": outcome,
        "workflows": admitted,
        "usage": usage.model_dump(mode="json") if usage is not None else None,
        "latency_ms": latency_ms,
        "digests": {"input": catalog.digest, "prompt": prompt_digest},
        "model": MODEL,
        "request_id": request_id,
    }
    if outcome == "no_workflows" and response.parsed is not None:
        # Closed lexical hints only: untrusted prose is never persisted or used
        # for admission/retry decisions. A mentioned topic is not a proven cause.
        reason = response.parsed.rejection_reason
        words = set(re.findall(r"[a-z]+(?:-[a-z]+)*", (reason or "").lower()))
        result["rejection_diagnostic"] = {
            "reason_present": reason is not None,
            "untrusted_lexical_hints": [
                label
                for label, vocabulary in (
                    ("evidence", {"evidence", "grounding"}),
                    ("fidelity", {"faithful", "faithfully", "fidelity"}),
                    ("read_only_scope", {"readonly", "read-only"}),
                    ("execution", {"execute", "execution", "installation", "operational"}),
                    ("reusability", {"reusable", "reusability"}),
                )
                if words & vocabulary
            ],
        }
    _finalize(Path(root), group, slot, outcome, result)
    return result


def run_case(
    root: Path,
    case: Mapping[str, object],
    profile: str,
    *,
    http_client: Any = None,
    api_key: str | None = None,
) -> dict[str, object]:
    """Run one named development case with at most one guarded request."""

    return _run_case(
        Path(root),
        case,
        profile,
        group="development",
        slot_profile=profile,
        http_client=http_client,
        api_key=api_key,
    )


def _preflight() -> dict[str, object]:
    cases, _ = read_dataset(DEVELOPMENT_DATASET)
    _read_holdout_manifest(CAMPAIGN_ROOT.parent / HOLDOUT_MANIFEST_NAME)
    if len(cases) != 7:
        raise ValueError("invalid development manifest")
    return {"development_case_count": 7, "external_requests": 0, "mode": "offline_preflight"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--init", action="store_true")
    mode.add_argument("--run-slot")
    arguments = parser.parse_args(argv)
    try:
        if arguments.init:
            initialize_campaign(CAMPAIGN_ROOT)
            output: dict[str, object] = {
                "external_requests": 0,
                "mode": "initialized",
            }
        elif arguments.run_slot is not None:
            profile, separator, case_id = arguments.run_slot.partition(":")
            if not separator or profile not in PROFILES:
                raise ValueError("invalid slot")
            cases, _ = read_dataset(DEVELOPMENT_DATASET)
            case = next((item for item in cases if item["id"] == case_id), None)
            if case is None:
                raise ValueError("invalid slot")
            output = run_case(
                CAMPAIGN_ROOT,
                case,
                profile,
                api_key=os.environ.get("DEEPSEEK_API_KEY"),
            )
        else:
            output = _preflight()
    except Exception:
        print("workflow selection trial failed", file=sys.stderr)
        return 2
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
