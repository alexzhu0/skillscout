"""Durable, deliberately small checkpoint ledger for controlled publication.

The publication ledger is intentionally not part of the Phase 1--3 ledger: a
publication attempt is an authority-bearing remote-write transaction and must
not be able to alter candidate processing state.  Only canonical contracts and
closed telemetry are admitted here; callers cannot persist provider payloads,
tokens, headers, exception text, or candidate prose.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel
from skillscout.domain.publication import PublicationIntentV1, PublicationRecordV1

_MAX_BYTES = 8_388_608
_GENESIS = "sha256:" + "0" * 64
_SAFE_STATUS = frozenset({"read", "success", "transient", "permanent", "conflict"})
_SAFE_STEP = frozenset({"begun", "reconciled", "blobs_created", "tree_created", "commit_created", "ref_visible", "draft_visible", "reviewers_verified", "remote_verified"})
_DATABASE_LOCATOR = "state/databases/publication.sqlite3"
_SCHEMA_STATEMENTS = (
    """CREATE TABLE publication_attempts (
      intent_digest TEXT PRIMARY KEY, intent_json TEXT NOT NULL, terminal_json TEXT
    )""",
    """CREATE TABLE publication_checkpoints (
      intent_digest TEXT NOT NULL REFERENCES publication_attempts(intent_digest),
      event_index INTEGER NOT NULL, checkpoint_json TEXT NOT NULL,
      PRIMARY KEY(intent_digest, event_index)
    )""",
)


def _normalize_schema(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _schema_fingerprint() -> str:
    return sha256_digest(
        {
            "schema_version": "publication-state-schema-v1",
            "statements": tuple(_normalize_schema(item) for item in _SCHEMA_STATEMENTS),
        }
    )


class PublicationOwnedFactV1(StrictFrozenModel):
    schema_version: Literal["publication-owned-fact-v1"]
    kind: Literal["attempt", "checkpoint"]
    sequence: Annotated[int, Field(ge=0, le=16_384)]
    payload_json: Annotated[str, Field(min_length=2, max_length=1_048_576)]
    object_digest: Digest

    @model_validator(mode="after")
    def validate_fact(self) -> "PublicationOwnedFactV1":
        try:
            import json

            decoded = json.loads(self.payload_json)
        except (UnicodeDecodeError, ValueError):
            raise ValueError("publication fact payload is invalid") from None
        if (
            type(decoded) is not dict
            or canonical_json_bytes(decoded).decode("utf-8") != self.payload_json
            or self.object_digest != sha256_digest(self.payload_json.encode("utf-8"))
        ):
            raise ValueError("publication fact payload is not canonical")
        return self


class PublicationStateProjectionV1(StrictFrozenModel):
    schema_version: Literal["publication-state-projection-v1"]
    intent_digests: tuple[Digest, ...]
    publication_keys: tuple[Digest, ...]
    desired_revisions: tuple[Digest, ...]
    terminal_record_digests: tuple[Digest, ...]
    projection_digest: Digest

    @model_validator(mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> object:
        if isinstance(value, dict):
            payload = dict(value)
            for field in (
                "intent_digests",
                "publication_keys",
                "desired_revisions",
                "terminal_record_digests",
            ):
                if isinstance(payload.get(field), list):
                    payload[field] = tuple(payload[field])
            return payload
        return value

    @model_validator(mode="after")
    def validate_projection(self) -> "PublicationStateProjectionV1":
        sequences = (
            self.intent_digests,
            self.publication_keys,
            self.desired_revisions,
            self.terminal_record_digests,
        )
        if any(sequence != tuple(sorted(set(sequence))) for sequence in sequences):
            raise ValueError("publication projection is not canonical")
        values = self.model_dump(mode="json", exclude={"projection_digest"})
        if self.projection_digest != sha256_digest(values):
            raise ValueError("publication projection digest mismatch")
        return self


class PublicationOwnedStateV1(StrictFrozenModel):
    schema_version: Literal["publication-owned-state-v1"]
    owner: Literal["publication"]
    database_locator: Literal["state/databases/publication.sqlite3"]
    schema_fingerprint: Digest
    database_bytes: Annotated[bytes, Field(max_length=_MAX_BYTES)]
    database_digest: Digest
    facts: Annotated[tuple[PublicationOwnedFactV1, ...], Field(max_length=16_384)]
    projection: PublicationStateProjectionV1
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
    def validate_owned_state(self) -> "PublicationOwnedStateV1":
        if self.schema_fingerprint != _schema_fingerprint():
            raise ValueError("publication schema fingerprint mismatch")
        if tuple(fact.sequence for fact in self.facts) != tuple(
            range(len(self.facts))
        ):
            raise ValueError("publication facts are not canonically sequenced")
        if len({fact.object_digest for fact in self.facts}) != len(self.facts):
            raise ValueError("publication facts are not unique")
        positions = {"attempt": 0, "checkpoint": 1}
        ordering = tuple(
            (positions[fact.kind], fact.payload_json) for fact in self.facts
        )
        if ordering != tuple(sorted(ordering)):
            raise ValueError("publication facts are reordered")
        projection = _projection_from_facts(self.facts)
        if (
            self.projection != projection
            or self.projection_digest != projection.projection_digest
        ):
            raise ValueError("publication projection disagrees with facts")
        expected_export = sha256_digest(
            {
                "schema_version": "publication-owned-state-v1",
                "owner": "publication",
                "database_locator": _DATABASE_LOCATOR,
                "schema_fingerprint": self.schema_fingerprint,
                "facts": tuple(
                    fact.model_dump(mode="json", exclude_none=False)
                    for fact in self.facts
                ),
                "projection": projection.model_dump(
                    mode="json", exclude_none=False
                ),
            }
        )
        if self.export_digest != expected_export:
            raise ValueError("publication export digest mismatch")
        return self


class PublicationCheckpointV1(StrictFrozenModel):
    schema_version: Literal["publication-checkpoint-v1"]
    intent_digest: Digest
    event_index: int = Field(ge=0, le=128)
    prior_checkpoint_hash: Digest
    step: str
    status_class: str
    request_id: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    remote_id: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9._/-]+$")
    remote_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    checkpoint_hash: Digest

    @model_validator(mode="after")
    def verify_hash(self) -> "PublicationCheckpointV1":
        if self.step not in _SAFE_STEP or self.status_class not in _SAFE_STATUS:
            raise ValueError("publication checkpoint is outside the closed vocabulary")
        values = self.model_dump(mode="json", exclude={"checkpoint_hash"})
        if self.checkpoint_hash != sha256_digest(values):
            raise ValueError("publication checkpoint hash mismatch")
        return self


@dataclass(frozen=True)
class PublicationAttempt:
    intent: PublicationIntentV1
    checkpoints: tuple[PublicationCheckpointV1, ...]
    record: PublicationRecordV1 | None


def _fact_payload(fact: PublicationOwnedFactV1) -> dict[str, object]:
    import json

    try:
        decoded = json.loads(fact.payload_json)
    except json.JSONDecodeError:
        raise RuntimeError("publication fact payload is invalid") from None
    if type(decoded) is not dict:
        raise RuntimeError("publication fact payload is invalid")
    return decoded


def _projection_from_facts(
    facts: tuple[PublicationOwnedFactV1, ...],
) -> PublicationStateProjectionV1:
    intents: set[str] = set()
    publication_keys: set[str] = set()
    revisions: set[str] = set()
    terminals: set[str] = set()
    for fact in facts:
        if fact.kind != "attempt":
            continue
        payload = _fact_payload(fact)
        if (
            payload.get("schema_version") != "publication-rebuild-attempt-v1"
            or type(payload.get("intent_json")) is not str
            or payload.get("terminal_json") is not None
            and type(payload.get("terminal_json")) is not str
        ):
            raise ValueError("publication attempt fact is malformed")
        intent = PublicationIntentV1.model_validate_json(
            payload["intent_json"], strict=True
        )
        if canonical_json_bytes(intent).decode("utf-8") != payload["intent_json"]:
            raise ValueError("publication intent is not canonical")
        intents.add(intent.intent_digest)
        publication_keys.add(intent.publication_key)
        revisions.add(intent.desired_revision)
        terminal_json = payload.get("terminal_json")
        if terminal_json is not None:
            record = PublicationRecordV1.model_validate_json(
                terminal_json, strict=True
            )
            if (
                canonical_json_bytes(record).decode("utf-8") != terminal_json
                or record.publication_key != intent.publication_key
                or record.desired_revision != intent.desired_revision
            ):
                raise ValueError("publication terminal record disagrees with intent")
            terminals.add(sha256_digest(terminal_json.encode("utf-8")))
    values: dict[str, object] = {
        "schema_version": "publication-state-projection-v1",
        "intent_digests": tuple(sorted(intents)),
        "publication_keys": tuple(sorted(publication_keys)),
        "desired_revisions": tuple(sorted(revisions)),
        "terminal_record_digests": tuple(sorted(terminals)),
    }
    return PublicationStateProjectionV1(
        **values,
        projection_digest=sha256_digest(values),
    )


class PublicationStateStore:
    """Snapshot-replaced SQLite store, poisoned after an uncertain write."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path) or not path.name or path.name.startswith("."):
            raise ValueError("publication state requires one private regular filename")
        self._parent = AnchoredDirectory.open(path.parent, create=True)
        self._name = path.name
        self._poisoned = False
        raw = self._parent.read_bytes(self._name, max_bytes=_MAX_BYTES, missing_ok=True)
        self._bytes = raw
        self._conn = sqlite3.connect(":memory:")
        if raw:
            self._conn.deserialize(raw)
        self._conn.execute("PRAGMA foreign_keys = ON")
        if raw:
            self._verify_connection(self._conn)
        else:
            for statement in _SCHEMA_STATEMENTS:
                self._conn.execute(statement)
            self._verify_connection(self._conn)
        self._persist_initial()

    @staticmethod
    def _verify_connection(connection: sqlite3.Connection) -> None:
        try:
            expected = {
                statement.split()[2]: _normalize_schema(statement)
                for statement in _SCHEMA_STATEMENTS
            }
            rows = connection.execute(
                """SELECT name, sql FROM sqlite_master
                   WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                   ORDER BY name"""
            ).fetchall()
            actual = {str(row[0]): _normalize_schema(str(row[1])) for row in rows}
            if actual != expected:
                raise RuntimeError("publication schema mismatch")
            integrity = tuple(
                str(row[0])
                for row in connection.execute("PRAGMA integrity_check").fetchall()
            )
            if integrity != ("ok",) or connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall():
                raise RuntimeError("publication database integrity failure")
        except sqlite3.Error:
            raise RuntimeError("publication database integrity failure") from None

    def _persist_initial(self) -> None:
        if self._bytes is None:
            self._replace(self._conn)

    def _replace(self, candidate: sqlite3.Connection) -> None:
        payload = candidate.serialize()
        try:
            self._parent.atomic_write(self._name, payload, max_bytes=_MAX_BYTES, restore_bytes=self._bytes if self._bytes is not None else b"", seam_prefix="publication_state_")
        except (DurableWriteError, OSError):
            self._poisoned = True
            candidate.close()
            raise RuntimeError("publication state persistence is uncertain") from None
        old = self._conn
        self._conn = candidate
        self._bytes = payload
        if old is not candidate:
            old.close()

    def _transaction(self, mutate: object) -> object:
        if self._poisoned:
            raise RuntimeError("publication state store is poisoned")
        candidate = sqlite3.connect(":memory:")
        candidate.deserialize(self._bytes or self._conn.serialize())
        candidate.execute("PRAGMA foreign_keys = ON")
        try:
            candidate.execute("BEGIN IMMEDIATE")
            result = mutate(candidate)  # type: ignore[operator]
            candidate.commit()
        except Exception:
            candidate.close()
            raise
        self._replace(candidate)
        return result

    def _attempt(self, intent_digest: str) -> PublicationAttempt | None:
        return self._attempt_from_connection(self._conn, intent_digest)

    @staticmethod
    def _attempt_from_connection(
        connection: sqlite3.Connection,
        intent_digest: str,
    ) -> PublicationAttempt | None:
        row = connection.execute("SELECT intent_json, terminal_json FROM publication_attempts WHERE intent_digest = ?", (intent_digest,)).fetchone()
        if row is None:
            return None
        intent = PublicationIntentV1.model_validate_json(row[0], strict=True)
        if (
            intent.intent_digest != intent_digest
            or canonical_json_bytes(intent).decode("utf-8") != row[0]
        ):
            raise RuntimeError("publication intent corruption")
        checkpoints = tuple(PublicationCheckpointV1.model_validate_json(item[0], strict=True) for item in connection.execute("SELECT checkpoint_json FROM publication_checkpoints WHERE intent_digest = ? ORDER BY event_index", (intent_digest,)))
        prior = _GENESIS
        for index, checkpoint in enumerate(checkpoints):
            if (
                checkpoint.intent_digest != intent_digest
                or checkpoint.event_index != index
                or checkpoint.prior_checkpoint_hash != prior
                or canonical_json_bytes(checkpoint).decode("utf-8")
                != connection.execute(
                    """SELECT checkpoint_json FROM publication_checkpoints
                       WHERE intent_digest = ? AND event_index = ?""",
                    (intent_digest, index),
                ).fetchone()[0]
            ):
                raise RuntimeError("publication checkpoint continuity failure")
            prior = checkpoint.checkpoint_hash
        record = PublicationRecordV1.model_validate_json(row[1], strict=True) if row[1] else None
        if record is not None and (
            record.publication_key != intent.publication_key
            or record.desired_revision != intent.desired_revision
            or canonical_json_bytes(record).decode("utf-8") != row[1]
        ):
            raise RuntimeError("publication terminal record disagrees with stored intent")
        return PublicationAttempt(intent, checkpoints, record)

    def find_completed(self, intent: PublicationIntentV1) -> PublicationRecordV1 | None:
        attempt = self._attempt(intent.intent_digest)
        return None if attempt is None else attempt.record

    def find_pending(self, intent: PublicationIntentV1) -> PublicationAttempt | None:
        attempt = self._attempt(intent.intent_digest)
        return attempt if attempt is not None and attempt.record is None else None

    def begin_attempt(self, intent: PublicationIntentV1) -> PublicationAttempt:
        if type(intent) is not PublicationIntentV1:
            raise TypeError("publication intent must be canonical")
        found = self._attempt(intent.intent_digest)
        if found:
            return found
        data = canonical_json_bytes(intent).decode("utf-8")
        self._transaction(lambda conn: conn.execute("INSERT INTO publication_attempts(intent_digest, intent_json) VALUES (?, ?)", (intent.intent_digest, data)))
        attempt = self._attempt(intent.intent_digest)
        assert attempt is not None
        return attempt

    def append_checkpoint(self, intent: PublicationIntentV1, *, step: str, status_class: str, request_id: str | None = None, remote_id: str | None = None, remote_sha: str | None = None) -> PublicationCheckpointV1:
        attempt = self.find_pending(intent)
        if attempt is None:
            raise RuntimeError("publication attempt is not pending")
        values = {"schema_version": "publication-checkpoint-v1", "intent_digest": intent.intent_digest, "event_index": len(attempt.checkpoints), "prior_checkpoint_hash": attempt.checkpoints[-1].checkpoint_hash if attempt.checkpoints else _GENESIS, "step": step, "status_class": status_class, "request_id": request_id, "remote_id": remote_id, "remote_sha": remote_sha}
        checkpoint = PublicationCheckpointV1(**values, checkpoint_hash=sha256_digest(values))
        payload = canonical_json_bytes(checkpoint).decode("utf-8")
        self._transaction(lambda conn: conn.execute("INSERT INTO publication_checkpoints(intent_digest, event_index, checkpoint_json) VALUES (?, ?, ?)", (intent.intent_digest, checkpoint.event_index, payload)))
        return checkpoint

    def complete(self, intent: PublicationIntentV1, record: PublicationRecordV1) -> None:
        if type(record) is not PublicationRecordV1 or (
            record.publication_key != intent.publication_key
            or record.desired_revision != intent.desired_revision
        ):
            raise ValueError("publication terminal record disagrees with intent")
        if self.find_pending(intent) is None:
            raise RuntimeError("publication attempt is not pending")
        payload = canonical_json_bytes(record).decode("utf-8")
        self._transaction(lambda conn: conn.execute("UPDATE publication_attempts SET terminal_json = ? WHERE intent_digest = ? AND terminal_json IS NULL", (payload, intent.intent_digest)))

    @classmethod
    def _facts_from_connection(
        cls,
        connection: sqlite3.Connection,
    ) -> tuple[PublicationOwnedFactV1, ...]:
        payloads: list[tuple[str, str]] = []
        for row in connection.execute(
            """SELECT intent_digest, intent_json, terminal_json
               FROM publication_attempts ORDER BY intent_digest"""
        ):
            payloads.append(
                (
                    "attempt",
                    canonical_json_bytes(
                        {
                            "schema_version": "publication-rebuild-attempt-v1",
                            "intent_digest": row[0],
                            "intent_json": row[1],
                            "terminal_json": row[2],
                        }
                    ).decode("utf-8"),
                )
            )
        for row in connection.execute(
            """SELECT intent_digest, event_index, checkpoint_json
               FROM publication_checkpoints
               ORDER BY intent_digest, event_index"""
        ):
            payloads.append(
                (
                    "checkpoint",
                    canonical_json_bytes(
                        {
                            "schema_version": "publication-rebuild-checkpoint-v1",
                            "intent_digest": row[0],
                            "event_index": row[1],
                            "checkpoint_json": row[2],
                        }
                    ).decode("utf-8"),
                )
            )
        return tuple(
            PublicationOwnedFactV1(
                schema_version="publication-owned-fact-v1",
                kind=kind,
                sequence=index,
                payload_json=payload,
                object_digest=sha256_digest(payload.encode("utf-8")),
            )
            for index, (kind, payload) in enumerate(payloads)
        )

    @staticmethod
    def _validated_export(exported: object) -> PublicationOwnedStateV1:
        try:
            if isinstance(exported, PublicationOwnedStateV1):
                raw = exported.model_dump(mode="python", exclude_none=False)
            elif isinstance(exported, dict):
                raw = exported
            else:
                raise TypeError("invalid publication export")
            return PublicationOwnedStateV1.model_validate(raw, strict=True)
        except (TypeError, ValueError, ValidationError):
            raise RuntimeError("invalid publication owned export") from None

    @classmethod
    def _replay_facts(
        cls,
        facts: tuple[PublicationOwnedFactV1, ...],
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            for statement in _SCHEMA_STATEMENTS:
                connection.execute(statement)
            attempt_payloads: dict[str, dict[str, object]] = {}
            checkpoint_payloads: list[dict[str, object]] = []
            for fact in facts:
                payload = _fact_payload(fact)
                if fact.kind == "attempt":
                    if (
                        payload.get("schema_version")
                        != "publication-rebuild-attempt-v1"
                        or type(payload.get("intent_digest")) is not str
                        or type(payload.get("intent_json")) is not str
                        or (
                            payload.get("terminal_json") is not None
                            and type(payload.get("terminal_json")) is not str
                        )
                        or payload["intent_digest"] in attempt_payloads
                    ):
                        raise RuntimeError("publication attempt fact is malformed")
                    attempt_payloads[str(payload["intent_digest"])] = payload
                else:
                    if (
                        payload.get("schema_version")
                        != "publication-rebuild-checkpoint-v1"
                        or type(payload.get("intent_digest")) is not str
                        or type(payload.get("event_index")) is not int
                        or type(payload.get("checkpoint_json")) is not str
                    ):
                        raise RuntimeError("publication checkpoint fact is malformed")
                    checkpoint_payloads.append(payload)

            connection.execute("BEGIN IMMEDIATE")
            for intent_digest, payload in attempt_payloads.items():
                intent = PublicationIntentV1.model_validate_json(
                    payload["intent_json"], strict=True
                )
                if (
                    intent.intent_digest != intent_digest
                    or canonical_json_bytes(intent).decode("utf-8")
                    != payload["intent_json"]
                ):
                    raise RuntimeError("publication intent fact is invalid")
                terminal_json = payload["terminal_json"]
                if terminal_json is not None:
                    record = PublicationRecordV1.model_validate_json(
                        terminal_json, strict=True
                    )
                    if (
                        canonical_json_bytes(record).decode("utf-8") != terminal_json
                        or record.publication_key != intent.publication_key
                        or record.desired_revision != intent.desired_revision
                    ):
                        raise RuntimeError(
                            "publication terminal fact disagrees with intent"
                        )
                connection.execute(
                    """INSERT INTO publication_attempts
                       (intent_digest, intent_json, terminal_json)
                       VALUES (?, ?, ?)""",
                    (intent_digest, payload["intent_json"], terminal_json),
                )
            for payload in checkpoint_payloads:
                checkpoint = PublicationCheckpointV1.model_validate_json(
                    payload["checkpoint_json"], strict=True
                )
                if (
                    checkpoint.intent_digest != payload["intent_digest"]
                    or checkpoint.event_index != payload["event_index"]
                    or canonical_json_bytes(checkpoint).decode("utf-8")
                    != payload["checkpoint_json"]
                ):
                    raise RuntimeError("publication checkpoint fact is invalid")
                connection.execute(
                    """INSERT INTO publication_checkpoints
                       (intent_digest, event_index, checkpoint_json)
                       VALUES (?, ?, ?)""",
                    (
                        payload["intent_digest"],
                        payload["event_index"],
                        payload["checkpoint_json"],
                    ),
                )
            connection.commit()
            cls._verify_connection(connection)
            for intent_digest in attempt_payloads:
                cls._attempt_from_connection(connection, intent_digest)
            return connection
        except Exception:
            connection.rollback()
            connection.close()
            raise

    @classmethod
    def _candidate_from_export(
        cls,
        exported: object,
    ) -> tuple[sqlite3.Connection, PublicationOwnedStateV1]:
        authority = cls._validated_export(exported)
        connection: sqlite3.Connection | None = None
        if authority.database_bytes:
            try:
                connection = sqlite3.connect(":memory:")
                connection.deserialize(authority.database_bytes)
                connection.execute("PRAGMA foreign_keys = ON")
                cls._verify_connection(connection)
            except (MemoryError, OverflowError, RuntimeError, sqlite3.Error):
                if connection is not None:
                    connection.close()
                connection = None
            if connection is not None:
                facts = cls._facts_from_connection(connection)
                if (
                    authority.database_digest
                    != sha256_digest(authority.database_bytes)
                    or facts != authority.facts
                ):
                    raise RuntimeError(
                        "valid publication database disagrees with owned JSON"
                    )
                for intent_digest in authority.projection.intent_digests:
                    cls._attempt_from_connection(connection, intent_digest)
                return connection, authority
        candidate = cls._replay_facts(authority.facts)
        if cls._facts_from_connection(candidate) != authority.facts:
            candidate.close()
            raise RuntimeError("rebuilt publication facts disagree with authority")
        return candidate, authority

    def export_owned_state(self) -> PublicationOwnedStateV1:
        self._verify_connection(self._conn)
        facts = self._facts_from_connection(self._conn)
        projection = _projection_from_facts(facts)
        database_bytes = self._conn.serialize()
        fingerprint = _schema_fingerprint()
        export_digest = sha256_digest(
            {
                "schema_version": "publication-owned-state-v1",
                "owner": "publication",
                "database_locator": _DATABASE_LOCATOR,
                "schema_fingerprint": fingerprint,
                "facts": tuple(
                    fact.model_dump(mode="json", exclude_none=False)
                    for fact in facts
                ),
                "projection": projection.model_dump(
                    mode="json", exclude_none=False
                ),
            }
        )
        return PublicationOwnedStateV1(
            schema_version="publication-owned-state-v1",
            owner="publication",
            database_locator=_DATABASE_LOCATOR,
            schema_fingerprint=fingerprint,
            database_bytes=database_bytes,
            database_digest=sha256_digest(database_bytes),
            facts=facts,
            projection=projection,
            projection_digest=projection.projection_digest,
            export_digest=export_digest,
        )

    def restore_owned_state(self, exported: object) -> None:
        candidate, authority = self._candidate_from_export(exported)
        self._replace(candidate)
        restored = self.export_owned_state()
        if (
            restored.facts != authority.facts
            or restored.projection != authority.projection
        ):
            self._poisoned = True
            raise RuntimeError("restored publication projection mismatch")

    @classmethod
    def rebuild_owned_state(cls, path: Path, exported: object) -> None:
        candidate, authority = cls._candidate_from_export(exported)
        if not isinstance(path, Path) or not path.name or path.name.startswith("."):
            candidate.close()
            raise ValueError("publication state requires one private regular filename")
        store = cls.__new__(cls)
        store._parent = AnchoredDirectory.open(path.parent, create=True)
        store._name = path.name
        store._poisoned = False
        store._bytes = store._parent.read_bytes(
            store._name,
            max_bytes=_MAX_BYTES,
            missing_ok=True,
        )
        store._conn = sqlite3.connect(":memory:")
        try:
            store._replace(candidate)
            restored = store.export_owned_state()
            if (
                restored.facts != authority.facts
                or restored.projection != authority.projection
            ):
                raise RuntimeError("rebuilt publication projection mismatch")
        finally:
            store.close()

    def close(self) -> None:
        self._conn.close()
        self._parent.close()

    def __enter__(self) -> "PublicationStateStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
