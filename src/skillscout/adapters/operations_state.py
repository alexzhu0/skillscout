"""Descriptor-anchored durable ledger for Phase 5 discovery operations."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Callable, Final, Literal, TypeVar

from pydantic import Field, model_validator

from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
    DiscoveredCandidateV1,
    DiscoveryBudgetPolicyV1,
    DiscoveryCandidateTerminalV1,
    DiscoveryReservationV1,
    DiscoveryRunAuthorityV1,
    DiscoveryRunSummaryV1,
    SearchPageObservationV1,
    SemanticReservationV1,
    DiscoveryStateRebuildProjectionV1,
)
from skillscout.domain.models import Digest, StrictFrozenModel


OPERATIONS_SCHEMA_VERSION: Final = 1
MAX_OPERATIONS_DB_BYTES: Final = 67_108_864
_DIGEST_PATTERN: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_TEST_RUN_SCHEMA: Final = "operations-test-run-v1"
_TEST_RESERVATION_SCHEMA: Final = "operations-test-reservation-v1"
_TEST_TERMINAL_SCHEMA: Final = "operations-test-terminal-v1"
_T = TypeVar("_T")


class OperationsStateError(RuntimeError):
    """Base class for closed operations-ledger failures."""


class OperationsIntegrityError(OperationsStateError):
    """Persisted operations authority is structurally or semantically invalid."""


class OperationsBusy(OperationsStateError):
    """Another process owns the retained operations-state lock."""


class BudgetExhausted(OperationsStateError):
    """A code-owned discovery or semantic reservation ceiling was reached."""


@dataclass(frozen=True)
class TestReservation:
    """Narrow deterministic record used by the Wave-0 budget contract."""

    kind: Literal["discovery", "semantic"]
    run_id: str
    repository_id: int
    ordinal: int
    reservation_digest: str


@dataclass(frozen=True)
class SemanticAttemptRecord:
    """Closed attempt transition without provider payload or diagnostic prose."""

    run_id: str
    repository_id: int
    stage: Literal["extractor", "generator", "reviewer"]
    attempt_no: int
    status: Literal[
        "started",
        "decided",
        "confirmed_retryable",
        "semantic_outcome_unknown",
    ]
    recorded_at: str
    attempt_digest: str


_FactKind = Literal[
    "run",
    "search_page",
    "candidate",
    "discovery_reservation",
    "semantic_reservation",
    "semantic_attempt",
    "candidate_terminal",
    "run_summary",
    "root_checkpoint",
]


class OperationsOwnedFactV1(StrictFrozenModel):
    """One canonical, content-addressed discovery-owned rebuild fact."""

    schema_version: Literal["operations-owned-fact-v1"]
    kind: _FactKind
    sequence: Annotated[int, Field(ge=0, le=8_192)]
    payload_json: Annotated[str, Field(min_length=2, max_length=1_048_576)]
    object_digest: Digest

    @model_validator(mode="after")
    def validate_canonical_payload(self) -> OperationsOwnedFactV1:
        decoded = _decoded_json(self.payload_json)
        if not isinstance(decoded, dict):
            raise ValueError("operations fact payload is not an object")
        if self.object_digest != sha256_digest(self.payload_json.encode("utf-8")):
            raise ValueError("operations fact digest mismatch")
        return self


class OperationsOwnedStateV1(StrictFrozenModel):
    """Complete operations-owned JSON authority plus a disposable SQLite index."""

    schema_version: Literal["operations-owned-state-v1"]
    owner: Literal["operations"]
    database_locator: Literal["state/databases/operations.sqlite3"]
    schema_fingerprint: Digest
    database_bytes: Annotated[bytes, Field(max_length=MAX_OPERATIONS_DB_BYTES)]
    database_digest: Digest
    facts: Annotated[tuple[OperationsOwnedFactV1, ...], Field(max_length=8_192)]
    projection: DiscoveryStateRebuildProjectionV1
    projection_digest: Digest
    export_digest: Digest

    @model_validator(mode="before")
    @classmethod
    def normalize_facts(cls, value: object) -> object:
        if isinstance(value, dict) and isinstance(value.get("facts"), list):
            payload = dict(value)
            payload["facts"] = tuple(payload["facts"])
            return payload
        return value

    @model_validator(mode="after")
    def validate_owned_authority(self) -> OperationsOwnedStateV1:
        if self.schema_fingerprint != _schema_fingerprint():
            raise ValueError("operations schema fingerprint mismatch")
        if tuple(fact.sequence for fact in self.facts) != tuple(range(len(self.facts))):
            raise ValueError("operations facts are not canonically ordered")
        if len({fact.object_digest for fact in self.facts}) != len(self.facts):
            raise ValueError("operations facts are not unique")
        if self.projection != _projection_from_facts(self.facts):
            raise ValueError("operations projection disagrees with facts")
        if self.projection_digest != self.projection.projection_digest:
            raise ValueError("operations projection digest mismatch")
        if self.export_digest != _export_digest(
            schema_fingerprint=self.schema_fingerprint,
            facts=self.facts,
            projection=self.projection,
        ):
            raise ValueError("operations export digest mismatch")
        return self


def _schema_statements() -> tuple[str, ...]:
    return (
        """CREATE TABLE operations_runs (
            run_id TEXT PRIMARY KEY,
            authority_digest TEXT NOT NULL UNIQUE,
            authority_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('running', 'interrupted', 'completed',
                           'completed_degraded', 'confirmed_retryable',
                           'integrity_conflict', 'permanent_failure')
            ),
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE operations_search_pages (
            observation_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            query_ordinal INTEGER NOT NULL CHECK (query_ordinal BETWEEN 1 AND 4),
            page INTEGER NOT NULL CHECK (page BETWEEN 1 AND 4),
            observation_json TEXT NOT NULL,
            UNIQUE (run_id, query_ordinal, page)
        )""",
        """CREATE TABLE operations_candidates (
            candidate_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            source_page_digest TEXT NOT NULL
                REFERENCES operations_search_pages(observation_digest),
            query_ordinal INTEGER NOT NULL CHECK (query_ordinal BETWEEN 1 AND 4),
            page INTEGER NOT NULL CHECK (page BETWEEN 1 AND 4),
            item_ordinal INTEGER NOT NULL CHECK (item_ordinal BETWEEN 1 AND 25),
            candidate_json TEXT NOT NULL,
            UNIQUE (run_id, query_ordinal, page, item_ordinal)
        )""",
        """CREATE TABLE operations_discovery_reservations (
            reservation_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            ordinal INTEGER NOT NULL CHECK (ordinal BETWEEN 1 AND 100),
            candidate_digest TEXT NOT NULL,
            reservation_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id),
            UNIQUE (run_id, ordinal)
        )""",
        """CREATE TABLE operations_semantic_reservations (
            reservation_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            ordinal INTEGER NOT NULL CHECK (ordinal BETWEEN 1 AND 20),
            discovery_reservation_digest TEXT NOT NULL,
            phase2_run_authority_digest TEXT NOT NULL,
            reservation_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id),
            UNIQUE (run_id, ordinal)
        )""",
        """CREATE TABLE operations_semantic_attempts (
            attempt_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            stage TEXT NOT NULL CHECK (
                stage IN ('extractor', 'generator', 'reviewer')
            ),
            attempt_no INTEGER NOT NULL CHECK (attempt_no BETWEEN 1 AND 16),
            status TEXT NOT NULL CHECK (
                status IN ('started', 'decided', 'confirmed_retryable',
                           'semantic_outcome_unknown')
            ),
            attempt_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id, stage, attempt_no)
        )""",
        """CREATE TABLE operations_candidate_terminals (
            terminal_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            repository_id INTEGER NOT NULL CHECK (repository_id > 0),
            semantic_reservation_digest TEXT,
            outcome TEXT NOT NULL CHECK (
                outcome IN ('filter_rejected', 'no_workflow',
                            'qualification_rejected', 'validation_rejected',
                            'review_rejected', 'completed_reuse',
                            'eligible_local_candidate', 'confirmed_retryable',
                            'semantic_outcome_unknown',
                            'state_integrity_conflict', 'permanent_failure')
            ),
            terminal_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id)
        )""",
        """CREATE TABLE operations_run_summaries (
            summary_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL UNIQUE REFERENCES operations_runs(run_id),
            summary_json TEXT NOT NULL
        )""",
        """CREATE TABLE operations_root_checkpoints (
            checkpoint_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES operations_runs(run_id),
            event_index INTEGER NOT NULL CHECK (event_index >= 0),
            prior_checkpoint_digest TEXT,
            state_root_digest TEXT NOT NULL,
            state_commit_sha TEXT NOT NULL,
            checkpoint_json TEXT NOT NULL,
            UNIQUE (run_id, event_index)
        )""",
    )


def _normalize_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _expected_schema() -> dict[str, str]:
    pattern = re.compile(r"^CREATE TABLE ([^\s(]+)", re.I)
    expected: dict[str, str] = {}
    for statement in _schema_statements():
        matched = pattern.match(statement)
        if matched is None:
            raise RuntimeError("invalid trusted operations schema")
        expected[matched.group(1)] = _normalize_sql(statement)
    return expected


_EXPECTED_SCHEMA: Final = _expected_schema()
_FACT_TABLES: Final[tuple[tuple[_FactKind, str, str, tuple[str, ...], tuple[str, ...]], ...]] = (
    (
        "run",
        "operations_runs",
        "authority_json",
        ("run_id",),
        ("run_id", "authority_digest", "status", "created_at"),
    ),
    (
        "search_page",
        "operations_search_pages",
        "observation_json",
        ("run_id", "query_ordinal", "page"),
        ("observation_digest", "run_id", "query_ordinal", "page"),
    ),
    (
        "candidate",
        "operations_candidates",
        "candidate_json",
        ("run_id", "query_ordinal", "page", "item_ordinal"),
        (
            "candidate_digest",
            "run_id",
            "repository_id",
            "source_page_digest",
            "query_ordinal",
            "page",
            "item_ordinal",
        ),
    ),
    (
        "discovery_reservation",
        "operations_discovery_reservations",
        "reservation_json",
        ("run_id", "ordinal"),
        (
            "reservation_digest",
            "run_id",
            "repository_id",
            "ordinal",
            "candidate_digest",
        ),
    ),
    (
        "semantic_reservation",
        "operations_semantic_reservations",
        "reservation_json",
        ("run_id", "ordinal"),
        (
            "reservation_digest",
            "run_id",
            "repository_id",
            "ordinal",
            "discovery_reservation_digest",
            "phase2_run_authority_digest",
        ),
    ),
    (
        "semantic_attempt",
        "operations_semantic_attempts",
        "attempt_json",
        ("run_id", "repository_id", "stage", "attempt_no"),
        (
            "attempt_digest",
            "run_id",
            "repository_id",
            "stage",
            "attempt_no",
            "status",
        ),
    ),
    (
        "candidate_terminal",
        "operations_candidate_terminals",
        "terminal_json",
        ("run_id", "repository_id"),
        (
            "terminal_digest",
            "run_id",
            "repository_id",
            "semantic_reservation_digest",
            "outcome",
        ),
    ),
    (
        "run_summary",
        "operations_run_summaries",
        "summary_json",
        ("run_id",),
        ("summary_digest", "run_id"),
    ),
    (
        "root_checkpoint",
        "operations_root_checkpoints",
        "checkpoint_json",
        ("run_id", "event_index"),
        (
            "checkpoint_digest",
            "run_id",
            "event_index",
            "prior_checkpoint_digest",
            "state_root_digest",
            "state_commit_sha",
        ),
    ),
)


def _schema_fingerprint() -> str:
    return sha256_digest(tuple((name, _EXPECTED_SCHEMA[name]) for name in sorted(_EXPECTED_SCHEMA)))


def _json_text(value: object) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _decoded_json(value: object) -> object:
    if type(value) is not str:
        raise OperationsIntegrityError("invalid canonical operations JSON")
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        raise OperationsIntegrityError("invalid canonical operations JSON") from None
    if _json_text(decoded) != value:
        raise OperationsIntegrityError("noncanonical operations JSON")
    return decoded


def _test_run_payload(run_id: str) -> dict[str, object]:
    values: dict[str, object] = {
        "schema_version": _TEST_RUN_SCHEMA,
        "run_id": run_id,
    }
    values["authority_digest"] = sha256_digest(values)
    return values


def _fact_payload(fact: OperationsOwnedFactV1) -> dict[str, object]:
    decoded = _decoded_json(fact.payload_json)
    if not isinstance(decoded, dict):
        raise OperationsIntegrityError("operations fact payload is not an object")
    return decoded


def _projection_from_facts(
    facts: tuple[OperationsOwnedFactV1, ...],
) -> DiscoveryStateRebuildProjectionV1:
    fields: dict[str, list[str]] = {
        "search_page_digests": [],
        "candidate_digests": [],
        "discovery_reservation_digests": [],
        "semantic_reservation_digests": [],
        "candidate_terminal_digests": [],
        "run_summary_digests": [],
    }
    mapping = {
        "search_page": ("search_page_digests", "observation_digest"),
        "candidate": ("candidate_digests", "candidate_digest"),
        "discovery_reservation": (
            "discovery_reservation_digests",
            "reservation_digest",
        ),
        "semantic_reservation": (
            "semantic_reservation_digests",
            "reservation_digest",
        ),
        "candidate_terminal": ("candidate_terminal_digests", "terminal_digest"),
        "run_summary": ("run_summary_digests", "summary_digest"),
    }
    for fact in facts:
        target = mapping.get(fact.kind)
        if target is None:
            continue
        payload = _fact_payload(fact)
        nested = payload.get("value")
        if not isinstance(nested, dict) or type(nested.get(target[1])) is not str:
            raise OperationsIntegrityError("operations projection fact is malformed")
        fields[target[0]].append(str(nested[target[1]]))
    values: dict[str, object] = {
        "schema_version": "discovery-state-rebuild-projection-v1",
        **{name: tuple(digests) for name, digests in fields.items()},
    }
    return DiscoveryStateRebuildProjectionV1(
        **values,
        projection_digest=sha256_digest(values),
    )


def _export_digest(
    *,
    schema_fingerprint: str,
    facts: tuple[OperationsOwnedFactV1, ...],
    projection: DiscoveryStateRebuildProjectionV1,
) -> str:
    return sha256_digest(
        {
            "schema_version": "operations-owned-state-v1",
            "owner": "operations",
            "database_locator": "state/databases/operations.sqlite3",
            "schema_fingerprint": schema_fingerprint,
            "facts": tuple(fact.model_dump(mode="json", exclude_none=False) for fact in facts),
            "projection": projection.model_dump(mode="json", exclude_none=False),
        }
    )


class OperationsStateStore:
    """Exclusive serialized SQLite index over discovery-owned canonical facts."""

    def __init__(
        self,
        path: Path,
        *,
        filesystem_seam: Callable[[str], None] | None = None,
    ) -> None:
        if (
            not isinstance(path, Path)
            or not path.name
            or path.name.startswith(".")
            or path.parent == path
        ):
            raise ValueError("operations state requires one private regular filename")
        self.path = Path(os.path.abspath(os.fspath(path)))
        self._name = AnchoredDirectory.validate_child_name(self.path.name)
        self._lock_name = AnchoredDirectory.validate_child_name(f".{self._name}.lock")
        self._filesystem_seam = filesystem_seam
        self._parent: AnchoredDirectory | None = None
        self._lock_descriptor = -1
        self._connection: sqlite3.Connection | None = None
        self._durable_bytes: bytes | None = None
        self._poisoned = False
        self._thread_lock = threading.RLock()
        try:
            self._parent = AnchoredDirectory.open(
                self.path.parent,
                create=True,
                filesystem_seam=filesystem_seam,
            )
            self._acquire_lock()
            self._parent.recover_stale_temporary(self._name)
            raw = self._parent.read_bytes(
                self._name,
                max_bytes=MAX_OPERATIONS_DB_BYTES,
                missing_ok=True,
            )
            if raw is None:
                connection = self._new_connection()
                self._create_schema(connection)
                payload = self._serialize(connection)
                self._parent.atomic_write(
                    self._name,
                    payload,
                    max_bytes=MAX_OPERATIONS_DB_BYTES,
                    seam_prefix="operations_state_",
                )
                self._connection = connection
                self._durable_bytes = payload
            else:
                connection = self._new_connection()
                connection.deserialize(raw)
                connection.execute("PRAGMA foreign_keys = ON")
                self._verify_connection(connection)
                self._connection = connection
                self._durable_bytes = raw
        except Exception:
            self.close()
            raise

    @staticmethod
    def _new_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(
            ":memory:",
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _acquire_lock(self) -> None:
        assert self._parent is not None
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            descriptor = os.open(
                self._lock_name,
                flags,
                0o600,
                dir_fd=self._parent.descriptor,
            )
            metadata = os.fstat(descriptor)
            AnchoredDirectory._require_private_regular(metadata)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            path_metadata = self._parent.stat_child(self._lock_name)
            if path_metadata is None or (
                metadata.st_dev,
                metadata.st_ino,
            ) != (
                path_metadata.st_dev,
                path_metadata.st_ino,
            ):
                raise OperationsIntegrityError("operations lock identity changed")
            self._lock_descriptor = descriptor
        except BlockingIOError:
            if "descriptor" in locals():
                os.close(descriptor)
            raise OperationsBusy("operations state is already locked") from None
        except Exception:
            if "descriptor" in locals():
                os.close(descriptor)
            raise

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in _schema_statements():
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {OPERATIONS_SCHEMA_VERSION}")
            connection.commit()
            OperationsStateStore._verify_connection(connection)
        except Exception:
            connection.rollback()
            connection.close()
            raise

    @staticmethod
    def _serialize(connection: sqlite3.Connection) -> bytes:
        try:
            payload = connection.serialize()
        except sqlite3.Error:
            raise OperationsStateError("operations state serialization failed") from None
        if type(payload) is not bytes or not payload or len(payload) > MAX_OPERATIONS_DB_BYTES:
            raise OperationsStateError("operations state snapshot is invalid")
        return payload

    @staticmethod
    def _verify_connection(connection: sqlite3.Connection) -> None:
        try:
            version = connection.execute("PRAGMA user_version").fetchone()
            if version is None or version[0] != OPERATIONS_SCHEMA_VERSION:
                raise OperationsIntegrityError("operations schema version mismatch")
            actual = {
                str(row["name"]): _normalize_sql(str(row["sql"]))
                for row in connection.execute(
                    """SELECT name, sql FROM sqlite_master
                       WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                       ORDER BY name"""
                ).fetchall()
            }
            if actual != _EXPECTED_SCHEMA:
                raise OperationsIntegrityError("operations schema fingerprint mismatch")
            integrity = tuple(
                str(row[0]) for row in connection.execute("PRAGMA integrity_check").fetchall()
            )
            if integrity != ("ok",):
                raise OperationsIntegrityError("operations integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise OperationsIntegrityError("operations foreign key check failed")
            OperationsStateStore._verify_rows(connection)
        except OperationsIntegrityError:
            raise
        except (sqlite3.Error, TypeError, ValueError):
            raise OperationsIntegrityError("operations verification failed") from None

    @staticmethod
    def _verify_rows(connection: sqlite3.Connection) -> None:
        run_rows = connection.execute("SELECT * FROM operations_runs ORDER BY run_id").fetchall()
        run_authorities: dict[str, str] = {}
        for row in run_rows:
            raw = _decoded_json(row["authority_json"])
            if not isinstance(raw, dict):
                raise OperationsIntegrityError("invalid operations run authority")
            if raw.get("schema_version") == _TEST_RUN_SCHEMA:
                expected = _test_run_payload(str(row["run_id"]))
                if raw != expected:
                    raise OperationsIntegrityError("invalid test run authority")
                authority_digest = str(expected["authority_digest"])
            else:
                authority = DiscoveryRunAuthorityV1.model_validate(raw, strict=True)
                if authority.run_id != row["run_id"]:
                    raise OperationsIntegrityError("run authority mismatch")
                authority_digest = authority.authority_digest
            if row["authority_digest"] != authority_digest or not _DIGEST_PATTERN.fullmatch(
                authority_digest
            ):
                raise OperationsIntegrityError("run authority digest mismatch")
            run_authorities[str(row["run_id"])] = authority_digest

        OperationsStateStore._verify_reservation_rows(
            connection,
            table="operations_discovery_reservations",
            maximum=DISCOVERY_MAX_CANDIDATES,
            model=DiscoveryReservationV1,
            run_authorities=run_authorities,
        )
        OperationsStateStore._verify_reservation_rows(
            connection,
            table="operations_semantic_reservations",
            maximum=DISCOVERY_MAX_SEMANTIC_CANDIDATES,
            model=SemanticReservationV1,
            run_authorities=run_authorities,
        )

        page_digests: set[str] = set()
        for row in connection.execute(
            "SELECT * FROM operations_search_pages ORDER BY run_id, query_ordinal, page"
        ).fetchall():
            page = SearchPageObservationV1.model_validate_json(row["observation_json"], strict=True)
            if (
                page.discovery_run_authority_digest != run_authorities.get(str(row["run_id"]))
                or page.observation_digest != row["observation_digest"]
                or page.query_ordinal != row["query_ordinal"]
                or page.page != row["page"]
            ):
                raise OperationsIntegrityError("search page authority mismatch")
            page_digests.add(page.observation_digest)

        for row in connection.execute(
            """SELECT * FROM operations_candidates
               ORDER BY run_id, query_ordinal, page, item_ordinal"""
        ).fetchall():
            candidate = DiscoveredCandidateV1.model_validate_json(
                row["candidate_json"], strict=True
            )
            if (
                candidate.discovery_run_authority_digest != run_authorities.get(str(row["run_id"]))
                or candidate.candidate_digest != row["candidate_digest"]
                or candidate.repository.repository_id != row["repository_id"]
                or candidate.source_page_digest != row["source_page_digest"]
                or candidate.source_page_digest not in page_digests
                or candidate.query_ordinal != row["query_ordinal"]
                or candidate.page != row["page"]
                or candidate.item_ordinal != row["item_ordinal"]
            ):
                raise OperationsIntegrityError("candidate observation mismatch")

        for row in connection.execute(
            "SELECT * FROM operations_candidate_terminals ORDER BY run_id, repository_id"
        ).fetchall():
            raw = _decoded_json(row["terminal_json"])
            if not isinstance(raw, dict):
                raise OperationsIntegrityError("invalid candidate terminal")
            if raw.get("schema_version") == _TEST_TERMINAL_SCHEMA:
                expected = {
                    "schema_version": _TEST_TERMINAL_SCHEMA,
                    "run_id": row["run_id"],
                    "repository_id": row["repository_id"],
                    "outcome": row["outcome"],
                }
                expected["terminal_digest"] = sha256_digest(expected)
                if raw != expected:
                    raise OperationsIntegrityError("invalid test candidate terminal")
                terminal_digest = str(expected["terminal_digest"])
            else:
                terminal = DiscoveryCandidateTerminalV1.model_validate(raw, strict=True)
                if (
                    terminal.discovery_run_authority_digest
                    != run_authorities.get(str(row["run_id"]))
                    or terminal.repository_id != row["repository_id"]
                    or terminal.outcome != row["outcome"]
                    or terminal.semantic_reservation_digest != row["semantic_reservation_digest"]
                ):
                    raise OperationsIntegrityError("candidate terminal mismatch")
                terminal_digest = terminal.terminal_digest
            if terminal_digest != row["terminal_digest"]:
                raise OperationsIntegrityError("candidate terminal digest mismatch")

        for row in connection.execute(
            """SELECT * FROM operations_semantic_attempts
               ORDER BY run_id, repository_id, stage, attempt_no"""
        ).fetchall():
            raw = _decoded_json(row["attempt_json"])
            if not isinstance(raw, dict):
                raise OperationsIntegrityError("invalid semantic attempt")
            expected_fields = {
                "schema_version": "operations-semantic-attempt-v1",
                "run_id": row["run_id"],
                "repository_id": row["repository_id"],
                "stage": row["stage"],
                "attempt_no": row["attempt_no"],
                "status": row["status"],
                "recorded_at": raw.get("recorded_at"),
            }
            digest = sha256_digest(expected_fields)
            expected = {**expected_fields, "attempt_digest": digest}
            if raw != expected or row["attempt_digest"] != digest:
                raise OperationsIntegrityError("semantic attempt digest mismatch")

        for row in connection.execute(
            "SELECT * FROM operations_run_summaries ORDER BY run_id"
        ).fetchall():
            summary = DiscoveryRunSummaryV1.model_validate_json(row["summary_json"], strict=True)
            run = connection.execute(
                "SELECT status FROM operations_runs WHERE run_id = ?",
                (row["run_id"],),
            ).fetchone()
            terminal_digests = tuple(
                str(item[0])
                for item in connection.execute(
                    """SELECT terminal_digest FROM operations_candidate_terminals
                       WHERE run_id = ? ORDER BY repository_id""",
                    (row["run_id"],),
                ).fetchall()
            )
            counts = OperationsStateStore._counts(connection, str(row["run_id"]))
            if (
                run is None
                or run["status"] != summary.status
                or summary.discovery_run_authority_digest != run_authorities.get(str(row["run_id"]))
                or summary.summary_digest != row["summary_digest"]
                or summary.selected_candidate_count != counts["discovery"]
                or summary.semantic_reservation_count != counts["semantic"]
                or summary.terminal_digests != terminal_digests
            ):
                raise OperationsIntegrityError("run summary projection mismatch")

        for run_id in run_authorities:
            statuses = connection.execute(
                "SELECT status FROM operations_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            summary_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM operations_run_summaries WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            if (
                statuses is None
                or (statuses["status"] not in {"running", "interrupted"} and summary_count != 1)
                or (statuses["status"] in {"running", "interrupted"} and summary_count != 0)
            ):
                raise OperationsIntegrityError("run status and summary disagree")

    @staticmethod
    def _verify_reservation_rows(
        connection: sqlite3.Connection,
        *,
        table: str,
        maximum: int,
        model: type[DiscoveryReservationV1] | type[SemanticReservationV1],
        run_authorities: dict[str, str],
    ) -> None:
        rows = connection.execute(f"SELECT * FROM {table} ORDER BY run_id, ordinal").fetchall()
        by_run: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            by_run.setdefault(str(row["run_id"]), []).append(row)
        for run_id, run_rows in by_run.items():
            ordinals = tuple(int(row["ordinal"]) for row in run_rows)
            if len(run_rows) > maximum or ordinals != tuple(range(1, len(run_rows) + 1)):
                raise OperationsIntegrityError("reservation ordinals are not contiguous")
            for row in run_rows:
                raw = _decoded_json(row["reservation_json"])
                if not isinstance(raw, dict):
                    raise OperationsIntegrityError("invalid reservation JSON")
                if raw.get("schema_version") == _TEST_RESERVATION_SCHEMA:
                    expected = {
                        "schema_version": _TEST_RESERVATION_SCHEMA,
                        "kind": (
                            "discovery"
                            if table == "operations_discovery_reservations"
                            else "semantic"
                        ),
                        "run_id": run_id,
                        "repository_id": row["repository_id"],
                        "ordinal": row["ordinal"],
                    }
                    expected["reservation_digest"] = sha256_digest(expected)
                    if raw != expected:
                        raise OperationsIntegrityError("invalid test reservation")
                    digest = str(expected["reservation_digest"])
                else:
                    reservation = model.model_validate(raw, strict=True)
                    if (
                        reservation.discovery_run_authority_digest != run_authorities.get(run_id)
                        or reservation.repository_id != row["repository_id"]
                        or reservation.ordinal != row["ordinal"]
                    ):
                        raise OperationsIntegrityError("reservation authority mismatch")
                    digest = reservation.reservation_digest
                if digest != row["reservation_digest"]:
                    raise OperationsIntegrityError("reservation digest mismatch")

    def _snapshot_transaction(
        self,
        mutation: Callable[[sqlite3.Connection], _T],
    ) -> _T:
        with self._thread_lock:
            if (
                self._poisoned
                or self._durable_bytes is None
                or self._connection is None
                or self._parent is None
            ):
                raise OperationsStateError("operations state is unavailable")
            candidate = self._new_connection()
            try:
                candidate.deserialize(self._durable_bytes)
                candidate.execute("PRAGMA foreign_keys = ON")
                candidate.execute("BEGIN IMMEDIATE")
                result = mutation(candidate)
                candidate.commit()
                self._verify_connection(candidate)
                payload = self._serialize(candidate)
            except Exception:
                try:
                    candidate.rollback()
                except sqlite3.Error:
                    pass
                candidate.close()
                raise
            previous = self._durable_bytes
            try:
                if self._filesystem_seam is not None:
                    self._filesystem_seam("before_operations_state_persist")
                self._parent.atomic_write(
                    self._name,
                    payload,
                    max_bytes=MAX_OPERATIONS_DB_BYTES,
                    restore_bytes=previous,
                    seam_prefix="operations_state_",
                )
            except (DurableWriteError, OSError):
                candidate.close()
                self._poisoned = True
                self._connection.close()
                self._connection = None
                raise OperationsStateError("operations state persistence is uncertain") from None
            current = self._connection
            self._connection = candidate
            self._durable_bytes = payload
            current.close()
            return result

    @staticmethod
    def _ensure_test_run(connection: sqlite3.Connection, run_id: str) -> None:
        if type(run_id) is not str or not run_id or len(run_id) > 256:
            raise ValueError("invalid test run ID")
        existing = connection.execute(
            "SELECT authority_json FROM operations_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        expected = _test_run_payload(run_id)
        if existing is None:
            connection.execute(
                """INSERT INTO operations_runs
                   (run_id, authority_digest, authority_json, status, created_at)
                   VALUES (?, ?, ?, 'running', '2026-07-27T00:00:00.000000Z')""",
                (run_id, expected["authority_digest"], _json_text(expected)),
            )
        elif _decoded_json(existing["authority_json"]) != expected:
            raise OperationsIntegrityError("test run authority mismatch")

    def create_run(
        self,
        authority: DiscoveryRunAuthorityV1,
        created_at: str,
    ) -> DiscoveryRunAuthorityV1:
        if type(authority) is not DiscoveryRunAuthorityV1:
            raise TypeError("invalid discovery run authority")

        def mutate(connection: sqlite3.Connection) -> DiscoveryRunAuthorityV1:
            existing = connection.execute(
                "SELECT * FROM operations_runs WHERE run_id = ?",
                (authority.run_id,),
            ).fetchone()
            if existing is not None:
                if existing["authority_digest"] != authority.authority_digest or existing[
                    "authority_json"
                ] != _json_text(authority):
                    raise OperationsIntegrityError("run identity conflict")
                return authority
            connection.execute(
                """INSERT INTO operations_runs
                   (run_id, authority_digest, authority_json, status, created_at)
                   VALUES (?, ?, ?, 'running', ?)""",
                (
                    authority.run_id,
                    authority.authority_digest,
                    _json_text(authority),
                    created_at,
                ),
            )
            return authority

        return self._snapshot_transaction(mutate)

    def record_search_page(
        self,
        run_id: str,
        page: SearchPageObservationV1,
        candidates: tuple[DiscoveredCandidateV1, ...],
    ) -> SearchPageObservationV1:
        if type(page) is not SearchPageObservationV1 or type(candidates) is not tuple:
            raise TypeError("invalid discovery page")

        def mutate(connection: sqlite3.Connection) -> SearchPageObservationV1:
            authority = self._run_authority_digest(connection, run_id)
            if page.discovery_run_authority_digest != authority:
                raise OperationsIntegrityError("page authority mismatch")
            existing = connection.execute(
                """SELECT observation_json FROM operations_search_pages
                   WHERE run_id = ? AND query_ordinal = ? AND page = ?""",
                (run_id, page.query_ordinal, page.page),
            ).fetchone()
            if existing is not None:
                if existing["observation_json"] != _json_text(page):
                    raise OperationsIntegrityError("search page conflict")
                return page
            connection.execute(
                """INSERT INTO operations_search_pages
                   (observation_digest, run_id, query_ordinal, page, observation_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    page.observation_digest,
                    run_id,
                    page.query_ordinal,
                    page.page,
                    _json_text(page),
                ),
            )
            if len(candidates) != page.item_count:
                raise OperationsIntegrityError("page candidate count mismatch")
            for candidate in candidates:
                if (
                    type(candidate) is not DiscoveredCandidateV1
                    or candidate.discovery_run_authority_digest != authority
                    or candidate.source_page_digest != page.observation_digest
                    or candidate.query_ordinal != page.query_ordinal
                    or candidate.page != page.page
                ):
                    raise OperationsIntegrityError("candidate page authority mismatch")
                connection.execute(
                    """INSERT INTO operations_candidates
                       (candidate_digest, run_id, repository_id, source_page_digest,
                        query_ordinal, page, item_ordinal, candidate_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate.candidate_digest,
                        run_id,
                        candidate.repository.repository_id,
                        candidate.source_page_digest,
                        candidate.query_ordinal,
                        candidate.page,
                        candidate.item_ordinal,
                        _json_text(candidate),
                    ),
                )
            return page

        return self._snapshot_transaction(mutate)

    @staticmethod
    def _run_authority_digest(
        connection: sqlite3.Connection,
        run_id: str,
    ) -> str:
        row = connection.execute(
            "SELECT authority_digest FROM operations_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise OperationsIntegrityError("unknown discovery run")
        return str(row["authority_digest"])

    def reserve_discovery_candidate(
        self,
        run_id: str,
        candidate: DiscoveredCandidateV1,
        reserved_at: str,
    ) -> DiscoveryReservationV1:
        if type(candidate) is not DiscoveredCandidateV1:
            raise TypeError("invalid discovery candidate")

        def mutate(connection: sqlite3.Connection) -> DiscoveryReservationV1:
            authority = self._run_authority_digest(connection, run_id)
            existing = connection.execute(
                """SELECT reservation_json
                   FROM operations_discovery_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, candidate.repository.repository_id),
            ).fetchone()
            if existing is not None:
                return DiscoveryReservationV1.model_validate_json(
                    existing["reservation_json"], strict=True
                )
            count = int(
                connection.execute(
                    """SELECT COUNT(*) FROM operations_discovery_reservations
                       WHERE run_id = ?""",
                    (run_id,),
                ).fetchone()[0]
            )
            ordinal = count + 1
            if count >= DISCOVERY_MAX_CANDIDATES:
                raise BudgetExhausted("discovery candidate budget exhausted")
            if (
                candidate.discovery_run_authority_digest != authority
                or candidate.dedup_disposition != "first_seen"
                or candidate.discovery_ordinal != ordinal
            ):
                raise OperationsIntegrityError("discovery reservation is not contiguous")
            stored = connection.execute(
                """SELECT candidate_digest FROM operations_candidates
                   WHERE candidate_digest = ? AND run_id = ?""",
                (candidate.candidate_digest, run_id),
            ).fetchone()
            if stored is None:
                raise OperationsIntegrityError("candidate observation is missing")
            values = {
                "schema_version": "discovery-reservation-v1",
                "discovery_run_authority_digest": authority,
                "repository_id": candidate.repository.repository_id,
                "ordinal": ordinal,
                "candidate_digest": candidate.candidate_digest,
                "reserved_at": reserved_at,
            }
            reservation = DiscoveryReservationV1(
                **values,
                reservation_digest=sha256_digest(values),
            )
            connection.execute(
                """INSERT INTO operations_discovery_reservations
                   (reservation_digest, run_id, repository_id, ordinal,
                    candidate_digest, reservation_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    reservation.reservation_digest,
                    run_id,
                    reservation.repository_id,
                    reservation.ordinal,
                    reservation.candidate_digest,
                    _json_text(reservation),
                ),
            )
            return reservation

        return self._snapshot_transaction(mutate)

    def reserve_semantic_candidate(
        self,
        run_id: str,
        repository_id: int,
        phase2_run_authority_digest: str,
        reserved_at: str,
    ) -> SemanticReservationV1:
        def mutate(connection: sqlite3.Connection) -> SemanticReservationV1:
            authority = self._run_authority_digest(connection, run_id)
            existing = connection.execute(
                """SELECT reservation_json
                   FROM operations_semantic_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if existing is not None:
                return SemanticReservationV1.model_validate_json(
                    existing["reservation_json"], strict=True
                )
            discovery = connection.execute(
                """SELECT reservation_digest
                   FROM operations_discovery_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if discovery is None:
                raise OperationsIntegrityError("discovery reservation is missing")
            count = int(
                connection.execute(
                    """SELECT COUNT(*) FROM operations_semantic_reservations
                       WHERE run_id = ?""",
                    (run_id,),
                ).fetchone()[0]
            )
            if count >= DISCOVERY_MAX_SEMANTIC_CANDIDATES:
                raise BudgetExhausted("semantic candidate budget exhausted")
            values = {
                "schema_version": "semantic-reservation-v1",
                "discovery_run_authority_digest": authority,
                "repository_id": repository_id,
                "ordinal": count + 1,
                "discovery_reservation_digest": discovery["reservation_digest"],
                "phase2_run_authority_digest": phase2_run_authority_digest,
                "reserved_at": reserved_at,
            }
            reservation = SemanticReservationV1(
                **values,
                reservation_digest=sha256_digest(values),
            )
            connection.execute(
                """INSERT INTO operations_semantic_reservations
                   (reservation_digest, run_id, repository_id, ordinal,
                    discovery_reservation_digest, phase2_run_authority_digest,
                    reservation_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    reservation.reservation_digest,
                    run_id,
                    repository_id,
                    reservation.ordinal,
                    reservation.discovery_reservation_digest,
                    reservation.phase2_run_authority_digest,
                    _json_text(reservation),
                ),
            )
            return reservation

        return self._snapshot_transaction(mutate)

    def record_candidate_terminal(
        self,
        run_id: str,
        terminal: DiscoveryCandidateTerminalV1,
    ) -> DiscoveryCandidateTerminalV1:
        if type(terminal) is not DiscoveryCandidateTerminalV1:
            raise TypeError("invalid candidate terminal")

        def mutate(connection: sqlite3.Connection) -> DiscoveryCandidateTerminalV1:
            authority = self._run_authority_digest(connection, run_id)
            if terminal.discovery_run_authority_digest != authority:
                raise OperationsIntegrityError("terminal authority mismatch")
            existing = connection.execute(
                """SELECT terminal_json FROM operations_candidate_terminals
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, terminal.repository_id),
            ).fetchone()
            if existing is not None:
                if existing["terminal_json"] != _json_text(terminal):
                    raise OperationsIntegrityError("candidate terminal conflict")
                return terminal
            if terminal.semantic_reservation_digest is not None:
                reservation = connection.execute(
                    """SELECT reservation_digest
                       FROM operations_semantic_reservations
                       WHERE run_id = ? AND repository_id = ?""",
                    (run_id, terminal.repository_id),
                ).fetchone()
                if (
                    reservation is None
                    or reservation["reservation_digest"] != terminal.semantic_reservation_digest
                ):
                    raise OperationsIntegrityError("terminal reservation mismatch")
            connection.execute(
                """INSERT INTO operations_candidate_terminals
                   (terminal_digest, run_id, repository_id,
                    semantic_reservation_digest, outcome, terminal_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    terminal.terminal_digest,
                    run_id,
                    terminal.repository_id,
                    terminal.semantic_reservation_digest,
                    terminal.outcome,
                    _json_text(terminal),
                ),
            )
            return terminal

        return self._snapshot_transaction(mutate)

    def record_semantic_attempt(
        self,
        *,
        run_id: str,
        repository_id: int,
        stage: Literal["extractor", "generator", "reviewer"],
        attempt_no: int,
        status: Literal[
            "started",
            "decided",
            "confirmed_retryable",
            "semantic_outcome_unknown",
        ],
        recorded_at: str,
    ) -> SemanticAttemptRecord:
        if (
            stage not in {"extractor", "generator", "reviewer"}
            or status
            not in {
                "started",
                "decided",
                "confirmed_retryable",
                "semantic_outcome_unknown",
            }
            or type(attempt_no) is not int
            or not 1 <= attempt_no <= 16
        ):
            raise ValueError("invalid semantic attempt transition")

        def mutate(connection: sqlite3.Connection) -> SemanticAttemptRecord:
            reservation = connection.execute(
                """SELECT reservation_digest
                   FROM operations_semantic_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if reservation is None:
                raise OperationsIntegrityError("semantic reservation is missing")
            rows = connection.execute(
                """SELECT * FROM operations_semantic_attempts
                   WHERE run_id = ? AND repository_id = ? AND stage = ?
                   ORDER BY attempt_no""",
                (run_id, repository_id, stage),
            ).fetchall()
            existing = next(
                (row for row in rows if int(row["attempt_no"]) == attempt_no),
                None,
            )
            if existing is None:
                if (
                    status != "started"
                    or attempt_no != len(rows) + 1
                    or (rows and rows[-1]["status"] not in {"confirmed_retryable"})
                ):
                    raise OperationsIntegrityError("semantic attempt continuity is invalid")
            elif existing["status"] == status:
                raw = _decoded_json(existing["attempt_json"])
                assert isinstance(raw, dict)
                return SemanticAttemptRecord(
                    run_id=run_id,
                    repository_id=repository_id,
                    stage=stage,
                    attempt_no=attempt_no,
                    status=status,
                    recorded_at=str(raw["recorded_at"]),
                    attempt_digest=str(existing["attempt_digest"]),
                )
            elif existing["status"] != "started" or status == "started":
                raise OperationsIntegrityError("semantic attempt is already decided")

            values: dict[str, object] = {
                "schema_version": "operations-semantic-attempt-v1",
                "run_id": run_id,
                "repository_id": repository_id,
                "stage": stage,
                "attempt_no": attempt_no,
                "status": status,
                "recorded_at": recorded_at,
            }
            values["attempt_digest"] = sha256_digest(values)
            if existing is None:
                connection.execute(
                    """INSERT INTO operations_semantic_attempts
                       (attempt_digest, run_id, repository_id, stage, attempt_no,
                        status, attempt_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        values["attempt_digest"],
                        run_id,
                        repository_id,
                        stage,
                        attempt_no,
                        status,
                        _json_text(values),
                    ),
                )
            else:
                connection.execute(
                    """UPDATE operations_semantic_attempts
                       SET attempt_digest = ?, status = ?, attempt_json = ?
                       WHERE run_id = ? AND repository_id = ?
                         AND stage = ? AND attempt_no = ?""",
                    (
                        values["attempt_digest"],
                        status,
                        _json_text(values),
                        run_id,
                        repository_id,
                        stage,
                        attempt_no,
                    ),
                )
            return SemanticAttemptRecord(
                run_id=run_id,
                repository_id=repository_id,
                stage=stage,
                attempt_no=attempt_no,
                status=status,
                recorded_at=recorded_at,
                attempt_digest=str(values["attempt_digest"]),
            )

        return self._snapshot_transaction(mutate)

    def record_run_summary(
        self,
        run_id: str,
        summary: DiscoveryRunSummaryV1,
    ) -> DiscoveryRunSummaryV1:
        if type(summary) is not DiscoveryRunSummaryV1:
            raise TypeError("invalid discovery run summary")

        def mutate(connection: sqlite3.Connection) -> DiscoveryRunSummaryV1:
            authority = self._run_authority_digest(connection, run_id)
            if summary.discovery_run_authority_digest != authority:
                raise OperationsIntegrityError("run summary authority mismatch")
            counts = self._counts(connection, run_id)
            terminal_digests = tuple(
                str(row[0])
                for row in connection.execute(
                    """SELECT terminal_digest FROM operations_candidate_terminals
                       WHERE run_id = ? ORDER BY repository_id""",
                    (run_id,),
                ).fetchall()
            )
            if (
                summary.selected_candidate_count != counts["discovery"]
                or summary.semantic_reservation_count != counts["semantic"]
                or summary.terminal_digests != terminal_digests
            ):
                raise OperationsIntegrityError("run summary projection mismatch")
            connection.execute(
                """INSERT INTO operations_run_summaries
                   (summary_digest, run_id, summary_json) VALUES (?, ?, ?)""",
                (summary.summary_digest, run_id, _json_text(summary)),
            )
            connection.execute(
                "UPDATE operations_runs SET status = ? WHERE run_id = ?",
                (summary.status, run_id),
            )
            return summary

        return self._snapshot_transaction(mutate)

    @staticmethod
    def _counts(
        connection: sqlite3.Connection,
        run_id: str,
    ) -> dict[str, int]:
        return {
            kind: int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            for kind, table in (
                ("discovery", "operations_discovery_reservations"),
                ("semantic", "operations_semantic_reservations"),
            )
        }

    def reserve_test_slot(
        self,
        *,
        kind: Literal["discovery", "semantic"],
        run_id: str,
        repository_id: int,
        requested_ordinal: int,
        policy: DiscoveryBudgetPolicyV1,
    ) -> TestReservation:
        if type(policy) is not DiscoveryBudgetPolicyV1 or kind not in {
            "discovery",
            "semantic",
        }:
            raise TypeError("invalid reservation policy")
        if type(repository_id) is not int or repository_id < 1:
            raise ValueError("invalid repository ID")
        table = (
            "operations_discovery_reservations"
            if kind == "discovery"
            else "operations_semantic_reservations"
        )
        maximum = (
            DISCOVERY_MAX_CANDIDATES if kind == "discovery" else DISCOVERY_MAX_SEMANTIC_CANDIDATES
        )

        def mutate(connection: sqlite3.Connection) -> TestReservation:
            self._ensure_test_run(connection, run_id)
            existing = connection.execute(
                f"""SELECT reservation_json FROM {table}
                    WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if existing is not None:
                raw = _decoded_json(existing["reservation_json"])
                assert isinstance(raw, dict)
                return TestReservation(
                    kind=kind,
                    run_id=run_id,
                    repository_id=repository_id,
                    ordinal=int(raw["ordinal"]),
                    reservation_digest=str(raw["reservation_digest"]),
                )
            count = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            if count >= maximum or requested_ordinal > maximum:
                raise BudgetExhausted(f"{kind} budget exhausted")
            if requested_ordinal != count + 1:
                raise OperationsIntegrityError("reservation ordinal is not contiguous")
            if kind == "discovery":
                policy.admit_discovery_ordinal(requested_ordinal)
            else:
                policy.admit_semantic_ordinal(requested_ordinal)
            values: dict[str, object] = {
                "schema_version": _TEST_RESERVATION_SCHEMA,
                "kind": kind,
                "run_id": run_id,
                "repository_id": repository_id,
                "ordinal": requested_ordinal,
            }
            values["reservation_digest"] = sha256_digest(values)
            if kind == "discovery":
                connection.execute(
                    """INSERT INTO operations_discovery_reservations
                       (reservation_digest, run_id, repository_id, ordinal,
                        candidate_digest, reservation_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        values["reservation_digest"],
                        run_id,
                        repository_id,
                        requested_ordinal,
                        sha256_digest({"run_id": run_id, "repository_id": repository_id}),
                        _json_text(values),
                    ),
                )
            else:
                connection.execute(
                    """INSERT INTO operations_semantic_reservations
                       (reservation_digest, run_id, repository_id, ordinal,
                        discovery_reservation_digest,
                        phase2_run_authority_digest, reservation_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        values["reservation_digest"],
                        run_id,
                        repository_id,
                        requested_ordinal,
                        sha256_digest({"run_id": run_id, "repository_id": repository_id}),
                        sha256_digest({"phase2": run_id, "repository_id": repository_id}),
                        _json_text(values),
                    ),
                )
            return TestReservation(
                kind=kind,
                run_id=run_id,
                repository_id=repository_id,
                ordinal=requested_ordinal,
                reservation_digest=str(values["reservation_digest"]),
            )

        return self._snapshot_transaction(mutate)

    def reservation_count(
        self,
        run_id: str,
        *,
        kind: Literal["discovery", "semantic"],
    ) -> int:
        with self._thread_lock:
            if self._connection is None:
                raise OperationsStateError("operations state is closed")
            return self._counts(self._connection, run_id)[kind]

    def seed_test_reservations(self, *, run_id: str, repository_id: int) -> None:
        policy = DiscoveryBudgetPolicyV1()
        self.reserve_test_slot(
            kind="discovery",
            run_id=run_id,
            repository_id=repository_id,
            requested_ordinal=1,
            policy=policy,
        )
        self.reserve_test_slot(
            kind="semantic",
            run_id=run_id,
            repository_id=repository_id,
            requested_ordinal=1,
            policy=policy,
        )

    def reservation_projection(
        self,
        run_id: str,
    ) -> tuple[tuple[object, ...], ...]:
        with self._thread_lock:
            if self._connection is None:
                raise OperationsStateError("operations state is closed")
            return tuple(
                tuple(row)
                for table in (
                    "operations_discovery_reservations",
                    "operations_semantic_reservations",
                )
                for row in self._connection.execute(
                    f"""SELECT run_id, repository_id, ordinal, reservation_digest
                        FROM {table} WHERE run_id = ?
                        ORDER BY ordinal""",
                    (run_id,),
                ).fetchall()
            )

    def record_test_terminal(
        self,
        *,
        run_id: str,
        repository_id: int,
        outcome: str,
    ) -> None:
        def mutate(connection: sqlite3.Connection) -> None:
            semantic = connection.execute(
                """SELECT reservation_digest
                   FROM operations_semantic_reservations
                   WHERE run_id = ? AND repository_id = ?""",
                (run_id, repository_id),
            ).fetchone()
            if semantic is None:
                raise OperationsIntegrityError("semantic reservation is missing")
            values: dict[str, object] = {
                "schema_version": _TEST_TERMINAL_SCHEMA,
                "run_id": run_id,
                "repository_id": repository_id,
                "outcome": outcome,
            }
            values["terminal_digest"] = sha256_digest(values)
            connection.execute(
                """INSERT INTO operations_candidate_terminals
                   (terminal_digest, run_id, repository_id,
                    semantic_reservation_digest, outcome, terminal_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    values["terminal_digest"],
                    run_id,
                    repository_id,
                    semantic["reservation_digest"],
                    outcome,
                    _json_text(values),
                ),
            )

        self._snapshot_transaction(mutate)

    @staticmethod
    def _facts_from_connection(
        connection: sqlite3.Connection,
    ) -> tuple[OperationsOwnedFactV1, ...]:
        facts: list[OperationsOwnedFactV1] = []
        for kind, table, json_column, order_columns, stored_columns in _FACT_TABLES:
            order = ", ".join(order_columns)
            rows = connection.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
            for row in rows:
                value = _decoded_json(row[json_column])
                if not isinstance(value, dict):
                    raise OperationsIntegrityError("operations row JSON is invalid")
                payload = {
                    "schema_version": "operations-rebuild-row-v1",
                    "kind": kind,
                    "columns": {column: row[column] for column in stored_columns},
                    "value": value,
                }
                payload_json = _json_text(payload)
                facts.append(
                    OperationsOwnedFactV1(
                        schema_version="operations-owned-fact-v1",
                        kind=kind,
                        sequence=len(facts),
                        payload_json=payload_json,
                        object_digest=sha256_digest(payload_json.encode("utf-8")),
                    )
                )
        return tuple(facts)

    @classmethod
    def _export_connection(
        cls,
        connection: sqlite3.Connection,
    ) -> OperationsOwnedStateV1:
        cls._verify_connection(connection)
        database_bytes = cls._serialize(connection)
        facts = cls._facts_from_connection(connection)
        projection = _projection_from_facts(facts)
        fingerprint = _schema_fingerprint()
        return OperationsOwnedStateV1(
            schema_version="operations-owned-state-v1",
            owner="operations",
            database_locator="state/databases/operations.sqlite3",
            schema_fingerprint=fingerprint,
            database_bytes=database_bytes,
            database_digest=sha256_digest(database_bytes),
            facts=facts,
            projection=projection,
            projection_digest=projection.projection_digest,
            export_digest=_export_digest(
                schema_fingerprint=fingerprint,
                facts=facts,
                projection=projection,
            ),
        )

    @staticmethod
    def _validated_export(exported: object) -> OperationsOwnedStateV1:
        try:
            if isinstance(exported, OperationsOwnedStateV1):
                raw = exported.model_dump(mode="python", exclude_none=False)
            elif isinstance(exported, dict):
                raw = exported
            else:
                raise TypeError("invalid operations export")
            return OperationsOwnedStateV1.model_validate(raw, strict=True)
        except Exception:
            raise OperationsIntegrityError("invalid operations owned export") from None

    @classmethod
    def _replay_facts(
        cls,
        facts: tuple[OperationsOwnedFactV1, ...],
    ) -> sqlite3.Connection:
        connection = cls._new_connection()
        try:
            cls._create_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            kind_positions = {definition[0]: index for index, definition in enumerate(_FACT_TABLES)}
            positions = tuple(kind_positions[fact.kind] for fact in facts)
            if positions != tuple(sorted(positions)):
                raise OperationsIntegrityError("operations fact kinds are not canonically ordered")
            definitions = {definition[0]: definition for definition in _FACT_TABLES}
            for fact in facts:
                payload = _fact_payload(fact)
                definition = definitions[fact.kind]
                _kind, table, json_column, _order_columns, stored_columns = definition
                if (
                    payload.get("schema_version") != "operations-rebuild-row-v1"
                    or payload.get("kind") != fact.kind
                    or not isinstance(payload.get("columns"), dict)
                    or not isinstance(payload.get("value"), dict)
                ):
                    raise OperationsIntegrityError("operations rebuild row is malformed")
                columns = payload["columns"]
                value = payload["value"]
                assert isinstance(columns, dict)
                assert isinstance(value, dict)
                if set(columns) != set(stored_columns):
                    raise OperationsIntegrityError("operations rebuild columns are not exact")
                insert_columns = (*stored_columns, json_column)
                placeholders = ", ".join("?" for _column in insert_columns)
                connection.execute(
                    f"""INSERT INTO {table} ({", ".join(insert_columns)})
                        VALUES ({placeholders})""",
                    (
                        *(columns[column] for column in stored_columns),
                        _json_text(value),
                    ),
                )
            connection.commit()
            cls._verify_connection(connection)
            return connection
        except Exception:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
            connection.close()
            raise

    @classmethod
    def _candidate_from_export(
        cls,
        exported: object,
    ) -> tuple[sqlite3.Connection, OperationsOwnedStateV1]:
        authority = cls._validated_export(exported)
        database_is_valid = False
        database_connection: sqlite3.Connection | None = None
        if authority.database_bytes:
            try:
                database_connection = cls._new_connection()
                database_connection.deserialize(authority.database_bytes)
                database_connection.execute("PRAGMA foreign_keys = ON")
                cls._verify_connection(database_connection)
                database_is_valid = True
            except Exception:
                if database_connection is not None:
                    database_connection.close()
                    database_connection = None
        if database_is_valid:
            assert database_connection is not None
            database_projection = cls._export_connection(database_connection)
            database_connection.close()
            if (
                authority.database_digest != sha256_digest(authority.database_bytes)
                or database_projection.facts != authority.facts
                or database_projection.projection != authority.projection
                or database_projection.schema_fingerprint != authority.schema_fingerprint
            ):
                raise OperationsIntegrityError(
                    "valid operations database disagrees with owned JSON"
                )

        candidate = cls._replay_facts(authority.facts)
        rebuilt = cls._export_connection(candidate)
        if (
            rebuilt.facts != authority.facts
            or rebuilt.projection != authority.projection
            or rebuilt.schema_fingerprint != authority.schema_fingerprint
        ):
            candidate.close()
            raise OperationsIntegrityError(
                "rebuilt operations projection disagrees with owned JSON"
            )
        return candidate, authority

    def export_owned_state(self) -> OperationsOwnedStateV1:
        with self._thread_lock:
            if self._connection is None or self._poisoned:
                raise OperationsStateError("operations state is unavailable")
            return self._export_connection(self._connection)

    def _install_candidate(self, candidate: sqlite3.Connection) -> None:
        if self._parent is None:
            candidate.close()
            raise OperationsStateError("operations state is closed")
        self._verify_connection(candidate)
        payload = self._serialize(candidate)
        previous = self._parent.read_bytes(
            self._name,
            max_bytes=MAX_OPERATIONS_DB_BYTES,
            missing_ok=True,
        )
        try:
            if previous is None:
                self._parent.atomic_write(
                    self._name,
                    payload,
                    max_bytes=MAX_OPERATIONS_DB_BYTES,
                    seam_prefix="operations_state_",
                )
            else:
                self._parent.atomic_write(
                    self._name,
                    payload,
                    max_bytes=MAX_OPERATIONS_DB_BYTES,
                    restore_bytes=previous,
                    seam_prefix="operations_state_",
                )
        except (DurableWriteError, OSError):
            candidate.close()
            self._poisoned = True
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            raise OperationsStateError("operations state persistence is uncertain") from None
        current = self._connection
        self._connection = candidate
        self._durable_bytes = payload
        if current is not None:
            current.close()

    def restore_owned_state(self, exported: object) -> None:
        candidate, authority = self._candidate_from_export(exported)
        with self._thread_lock:
            self._install_candidate(candidate)
            restored = self.export_owned_state()
            if restored.facts != authority.facts or restored.projection != authority.projection:
                self._poisoned = True
                raise OperationsIntegrityError("restored operations projection mismatch")

    @classmethod
    def rebuild_owned_state(cls, path: Path, exported: object) -> None:
        candidate, authority = cls._candidate_from_export(exported)
        store = cls.__new__(cls)
        store.path = Path(os.path.abspath(os.fspath(path)))
        store._name = AnchoredDirectory.validate_child_name(store.path.name)
        store._lock_name = AnchoredDirectory.validate_child_name(f".{store._name}.lock")
        store._filesystem_seam = None
        store._parent = None
        store._lock_descriptor = -1
        store._connection = None
        store._durable_bytes = None
        store._poisoned = False
        store._thread_lock = threading.RLock()
        try:
            if (
                not isinstance(path, Path)
                or not path.name
                or path.name.startswith(".")
                or path.parent == path
            ):
                raise ValueError("operations state requires one private regular filename")
            store._parent = AnchoredDirectory.open(store.path.parent, create=True)
            store._acquire_lock()
            store._parent.recover_stale_temporary(store._name)
            store._install_candidate(candidate)
            rebuilt = store.export_owned_state()
            if rebuilt.facts != authority.facts or rebuilt.projection != authority.projection:
                raise OperationsIntegrityError("rebuilt operations projection mismatch")
        except Exception:
            if store._connection is not candidate:
                candidate.close()
            raise
        finally:
            store.close()

    def close(self) -> None:
        with self._thread_lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            if self._lock_descriptor >= 0:
                try:
                    fcntl.flock(self._lock_descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
                os.close(self._lock_descriptor)
                self._lock_descriptor = -1
            if self._parent is not None:
                self._parent.close()
                self._parent = None

    def __enter__(self) -> OperationsStateStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
