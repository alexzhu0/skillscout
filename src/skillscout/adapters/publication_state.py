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
from typing import Literal

from pydantic import Field, model_validator

from skillscout.adapters.localfs import AnchoredDirectory, DurableWriteError
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel
from skillscout.domain.publication import PublicationIntentV1, PublicationRecordV1

_MAX_BYTES = 8_388_608
_GENESIS = "sha256:" + "0" * 64
_SAFE_STATUS = frozenset({"read", "success", "transient", "permanent", "conflict"})
_SAFE_STEP = frozenset({"begun", "reconciled", "blobs_created", "tree_created", "commit_created", "ref_visible", "draft_visible", "reviewers_verified", "remote_verified"})


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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS publication_attempts (
              intent_digest TEXT PRIMARY KEY, intent_json TEXT NOT NULL, terminal_json TEXT
            );
            CREATE TABLE IF NOT EXISTS publication_checkpoints (
              intent_digest TEXT NOT NULL REFERENCES publication_attempts(intent_digest),
              event_index INTEGER NOT NULL, checkpoint_json TEXT NOT NULL,
              PRIMARY KEY(intent_digest, event_index)
            );
        """)
        self._persist_initial()

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
        row = self._conn.execute("SELECT intent_json, terminal_json FROM publication_attempts WHERE intent_digest = ?", (intent_digest,)).fetchone()
        if row is None:
            return None
        intent = PublicationIntentV1.model_validate_json(row[0], strict=True)
        if intent.intent_digest != intent_digest:
            raise RuntimeError("publication intent corruption")
        checkpoints = tuple(PublicationCheckpointV1.model_validate_json(item[0], strict=True) for item in self._conn.execute("SELECT checkpoint_json FROM publication_checkpoints WHERE intent_digest = ? ORDER BY event_index", (intent_digest,)))
        prior = _GENESIS
        for index, checkpoint in enumerate(checkpoints):
            if checkpoint.intent_digest != intent_digest or checkpoint.event_index != index or checkpoint.prior_checkpoint_hash != prior:
                raise RuntimeError("publication checkpoint continuity failure")
            prior = checkpoint.checkpoint_hash
        record = PublicationRecordV1.model_validate_json(row[1], strict=True) if row[1] else None
        if record is not None and (
            record.publication_key != intent.publication_key
            or record.desired_revision != intent.desired_revision
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

    def close(self) -> None:
        self._conn.close()
        self._parent.close()

    def __enter__(self) -> "PublicationStateStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
