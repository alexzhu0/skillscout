"""Exact GitHub state-branch restore and fast-forward synchronization.

The client is deliberately smaller than the publication client: it is bound to
one repository and ``refs/heads/skillscout-state`` and exposes only Git object
and ref operations.  The store validates the complete prospective or observed
tree before granting state authority.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import re
import time
from typing import Any, Callable, Iterable, Literal, Mapping

import httpx
from pydantic import ValidationError

from skillscout.application.ports import (
    DurabilityReceipt,
    ErrorCode,
    SafeFailure,
    SemanticDurabilityTransition,
)
from skillscout.domain.canonical import canonical_json_bytes
from skillscout.domain.discovery import DiscoveryStateRootV1
from skillscout.domain.enums import EffectScope


GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
STATE_REF = "refs/heads/skillscout-state"

_MAX_RESPONSE_BYTES = 1_048_576
_MAX_ROOT_BYTES = 1_048_576
_MAX_OBJECT_BYTES = 1_048_576
_MAX_DATABASE_BYTES = 1_073_741_824
_MAX_TREE_ENTRIES = 4_100
_MAX_REQUEST_ID_CHARS = 128
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
_GITHUB_REQUEST_ID = re.compile(r"(?:[A-Za-z0-9._-]+|[0-9A-F]+(?::[0-9A-F]+)+)")
_OBJECT_PATH = re.compile(r"^state/objects/sha256/([0-9a-f]{2})/([0-9a-f]{64})\.json$")
_DATABASE_PATHS = (
    "state/databases/pipeline.sqlite3",
    "state/databases/operations.sqlite3",
    "state/databases/publication.sqlite3",
)
_SECRET_CANARIES = (
    b"github_pat_",
    b"ghp_",
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"authorization: bearer ",
    b"STATE_BRANCH_REPOSITORY_BODY_CANARY",
)
_RESOLVER_MAX_REQUESTS = 1_024
_RESOLVER_MAX_RESPONSE_BYTES = 268_435_456
_RESOLVER_MAX_ELAPSED_SECONDS = 45.0


class StateIntegrityFailure(Exception):
    """Closed failure for malformed, mismatched, or leaking state evidence."""


class StateBranchConflict(Exception):
    """Closed signal for a changed or unverifiable remote state head."""


class StateBranchPostCasUncertain(StateBranchConflict):
    """A fixed ref write may have landed but its immediate verification failed.

    This is deliberately narrower than a general state-branch conflict.  It is
    constructed only after the candidate commit exists and a create/update-ref
    request has been attempted, so a caller can perform one exact immutable
    recovery proof without treating unrelated errors as successful writes.
    """

    def __init__(
        self,
        *,
        candidate_commit_sha: str,
        candidate_tree_sha: str,
        previous_head: str | None,
        expected_root_digest: str,
    ) -> None:
        self.candidate_commit_sha = candidate_commit_sha
        self.candidate_tree_sha = candidate_tree_sha
        self.previous_head = previous_head
        self.expected_root_digest = expected_root_digest
        super().__init__("post-CAS state verification is uncertain")


class StateRefNotFound(Exception):
    """The exact fixed state ref does not exist."""


class ResolverReadBudget:
    """One hard resolver-wide budget shared by every immutable Git read."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_requests: int = _RESOLVER_MAX_REQUESTS,
        max_response_bytes: int = _RESOLVER_MAX_RESPONSE_BYTES,
        max_elapsed_seconds: float = _RESOLVER_MAX_ELAPSED_SECONDS,
    ) -> None:
        if (
            not callable(clock)
            or type(max_requests) is not int
            or not 1 <= max_requests <= _RESOLVER_MAX_REQUESTS
            or type(max_response_bytes) is not int
            or not 1 <= max_response_bytes <= _RESOLVER_MAX_RESPONSE_BYTES
            or type(max_elapsed_seconds) not in {int, float}
            or not 0 < float(max_elapsed_seconds) <= _RESOLVER_MAX_ELAPSED_SECONDS
        ):
            raise StateIntegrityFailure
        self._clock = clock
        self._max_requests = max_requests
        self._max_response_bytes = max_response_bytes
        self._deadline = clock() + float(max_elapsed_seconds)
        self.request_count = 0
        self.response_bytes = 0

    def begin_request(self) -> float:
        remaining = self._deadline - self._clock()
        if remaining <= 0 or self.request_count >= self._max_requests:
            raise StateIntegrityFailure
        self.request_count += 1
        return remaining

    def charge_response_bytes(self, count: int) -> None:
        if (
            type(count) is not int
            or count < 0
            or self._clock() >= self._deadline
            or self.response_bytes + count > self._max_response_bytes
        ):
            raise StateIntegrityFailure
        self.response_bytes += count

    @property
    def remaining_response_bytes(self) -> int:
        return self._max_response_bytes - self.response_bytes


@dataclass(frozen=True)
class StateRefObservation:
    ref: str
    sha: str


@dataclass(frozen=True)
class StateCommitObservation:
    sha: str
    tree_sha: str
    parents: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class StateTreeEntry:
    path: str
    sha: str
    mode: str
    size: int | None = None


@dataclass(frozen=True)
class StateOwnedFile:
    path: str
    content: bytes


@dataclass(frozen=True)
class VerifiedStateBundle:
    root: DiscoveryStateRootV1
    files: tuple[StateOwnedFile, ...] = ()

    def content_by_path(self) -> dict[str, bytes]:
        return {item.path: item.content for item in self.files}


@dataclass(frozen=True)
class StateRestoreObservation:
    status: Literal["absent", "verified"]
    observed_head: str | None
    bundle: VerifiedStateBundle | None


@dataclass(frozen=True)
class StateSyncObservation:
    status: Literal["verified"]
    previous_head: str | None
    commit_sha: str
    tree_sha: str
    root_digest: str


@dataclass(frozen=True)
class StateCommitRootObservation:
    """Bounded commit/tree/root proof without database or object restoration."""

    commit: StateCommitObservation
    root: DiscoveryStateRootV1
    object_digests: tuple[str, ...]
    declared_content_bytes: int


def _safe_failure(code: ErrorCode = ErrorCode.STAGE_PERMANENT_FAILURE) -> None:
    raise SafeFailure(code)


def _sha(value: object) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _safe_failure()
    return value


def _digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _require_digest(value: object) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise StateIntegrityFailure
    return value


def _git_blob_id(value: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(value)).encode("ascii") + b"\0" + value,
        usedforsecurity=False,
    ).hexdigest()


def _state_commit_message(root_digest: str) -> str:
    _require_digest(root_digest)
    return f"skillscout: persist state\n\nSkillScout-State: v1\nRoot-Digest: {root_digest}"


def _contains_canary(value: bytes) -> bool:
    lowered = value.lower()
    return any(canary.lower() in lowered for canary in _SECRET_CANARIES)


class _StateBranchReadClientBase:
    """Shared bounded GitHub Git-data reads for the fixed state ref."""

    effect_scope = EffectScope.REMOTE_READ

    def __init__(
        self,
        *,
        token: str,
        repository_id: int,
        repository_full_name: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if type(token) is not str or not token:
            _safe_failure()
        if type(repository_id) is not int or repository_id <= 0:
            _safe_failure()
        if (
            type(repository_full_name) is not str
            or repository_full_name.count("/") != 1
            or any(not part for part in repository_full_name.split("/"))
        ):
            _safe_failure()
        self._repository_id = repository_id
        self._repository = repository_full_name
        self._client = httpx.Client(
            base_url=GITHUB_API_BASE,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "Authorization": f"Bearer {token}",
                "User-Agent": "skillscout/0.1.0",
            },
            timeout=10.0,
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def get_state_ref(
        self,
        *,
        read_budget: ResolverReadBudget | None = None,
    ) -> StateRefObservation:
        raw = self._json(
            "GET",
            f"/repos/{self._repository}/git/ref/heads/skillscout-state",
            allow_not_found=True,
            read_budget=read_budget,
        )
        return self._ref(raw)

    def get_commit(
        self,
        sha: str,
        *,
        read_budget: ResolverReadBudget | None = None,
    ) -> StateCommitObservation:
        expected = _sha(sha)
        raw = self._json(
            "GET",
            f"/repos/{self._repository}/git/commits/{expected}",
            read_budget=read_budget,
        )
        if (
            not isinstance(raw, dict)
            or raw.get("sha") != expected
            or not isinstance(raw.get("tree"), dict)
            or not isinstance(raw.get("parents"), list)
            or len(raw["parents"]) > 1
            or any(not isinstance(parent, dict) for parent in raw["parents"])
        ):
            _safe_failure()
        message = raw.get("message")
        if type(message) is not str or not message or len(message) > 4_096:
            _safe_failure()
        return StateCommitObservation(
            sha=expected,
            tree_sha=_sha(raw["tree"].get("sha")),
            parents=tuple(_sha(parent.get("sha")) for parent in raw["parents"]),
            message=message,
        )

    def get_tree(
        self,
        sha: str,
        *,
        read_budget: ResolverReadBudget | None = None,
    ) -> tuple[StateTreeEntry, ...]:
        expected = _sha(sha)
        raw = self._json(
            "GET",
            f"/repos/{self._repository}/git/trees/{expected}?recursive=1",
            read_budget=read_budget,
        )
        if (
            not isinstance(raw, dict)
            or raw.get("sha") != expected
            or raw.get("truncated") is not False
            or not isinstance(raw.get("tree"), list)
            or len(raw["tree"]) > _MAX_TREE_ENTRIES
        ):
            _safe_failure()
        entries: list[StateTreeEntry] = []
        directories: set[str] = set()
        for item in raw["tree"]:
            if not isinstance(item, dict) or type(item.get("path")) is not str:
                _safe_failure()
            path = item["path"]
            if not path or "\\" in path or path.startswith("/") or ".." in path.split("/"):
                _safe_failure()
            if item.get("type") == "tree":
                if item.get("mode") != "040000" or not _allowed_tree_path(path):
                    _safe_failure()
                _sha(item.get("sha"))
                if path in directories:
                    _safe_failure()
                directories.add(path)
                continue
            if item.get("type") != "blob" or item.get("mode") != "100644":
                _safe_failure()
            size = item.get("size")
            if size is not None and (type(size) is not int or size < 0):
                _safe_failure()
            entries.append(
                StateTreeEntry(
                    path=path,
                    sha=_sha(item.get("sha")),
                    mode="100644",
                    size=size,
                )
            )
        if len({entry.path for entry in entries}) != len(entries):
            _safe_failure()
        if directories != _required_directory_paths(entries):
            _safe_failure()
        return tuple(sorted(entries, key=lambda entry: entry.path))

    def get_blob(
        self,
        sha: str,
        *,
        read_budget: ResolverReadBudget | None = None,
    ) -> bytes:
        raw = self._json(
            "GET",
            f"/repos/{self._repository}/git/blobs/{_sha(sha)}",
            cap=_MAX_DATABASE_BYTES + 1024,
            read_budget=read_budget,
        )
        if (
            not isinstance(raw, dict)
            or raw.get("encoding") != "base64"
            or type(raw.get("content")) is not str
            or type(raw.get("size")) is not int
            or raw["size"] < 0
            or raw["size"] > _MAX_DATABASE_BYTES
        ):
            _safe_failure()
        encoded = raw["content"].replace("\r", "").replace("\n", "")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            _safe_failure()
        if (
            base64.b64encode(content).decode("ascii") != encoded
            or len(content) != raw["size"]
            or _git_blob_id(content) != _sha(sha)
        ):
            _safe_failure()
        return content

    def _ref(self, raw: object, expected_sha: str | None = None) -> StateRefObservation:
        if (
            not isinstance(raw, dict)
            or raw.get("ref") != STATE_REF
            or not isinstance(raw.get("object"), dict)
        ):
            _safe_failure()
        sha = _sha(raw["object"].get("sha"))
        if expected_sha is not None and sha != expected_sha:
            raise StateBranchConflict
        return StateRefObservation(STATE_REF, sha)

    def _json(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        cap: int = _MAX_RESPONSE_BYTES,
        allow_not_found: bool = False,
        conflict_on_write: bool = False,
        read_budget: ResolverReadBudget | None = None,
    ) -> Any:
        request_arguments: dict[str, object] = {}
        if read_budget is not None:
            request_arguments["timeout"] = read_budget.begin_request()
        try:
            response = self._client.send(
                self._client.build_request(
                    method,
                    path,
                    json=payload,
                    **request_arguments,
                ),
                stream=True,
            )
        except httpx.TransportError:
            _safe_failure(ErrorCode.STAGE_TRANSIENT_FAILURE)
        except httpx.HTTPError:
            _safe_failure()
        try:
            request_id = response.headers.get("x-github-request-id")
            if (
                type(request_id) is not str
                or not request_id
                or len(request_id) > _MAX_REQUEST_ID_CHARS
                or _GITHUB_REQUEST_ID.fullmatch(request_id) is None
            ):
                _safe_failure()
            if response.status_code in {301, 302, 303, 307, 308}:
                _safe_failure()
            if conflict_on_write and response.status_code in {409, 422}:
                raise StateBranchConflict
            if response.status_code == 404 and allow_not_found:
                raise StateRefNotFound
            if response.status_code == 429 or response.status_code >= 500:
                _safe_failure(ErrorCode.STAGE_TRANSIENT_FAILURE)
            if (
                not 200 <= response.status_code < 300
                or "application/json" not in response.headers.get("content-type", "")
            ):
                _safe_failure()
            pieces: list[bytes] = []
            consumed = 0
            try:
                for piece in response.iter_bytes(65_536):
                    if read_budget is not None:
                        read_budget.charge_response_bytes(len(piece))
                    consumed += len(piece)
                    if consumed > cap:
                        _safe_failure()
                    pieces.append(piece)
            except httpx.TransportError:
                _safe_failure(ErrorCode.STAGE_TRANSIENT_FAILURE)
            try:
                return json.loads(b"".join(pieces))
            except (UnicodeDecodeError, json.JSONDecodeError):
                _safe_failure()
        finally:
            response.close()


class StateBranchReadClient(_StateBranchReadClientBase):
    """Read-only capability used to prove a resume lineage."""


class StateBranchClient(_StateBranchReadClientBase):
    """GitHub Git-data write capability bound to the fixed state ref."""

    effect_scope = EffectScope.REMOTE_WRITE

    def create_blob(self, content: bytes) -> str:
        if type(content) is not bytes or not content or len(content) > _MAX_DATABASE_BYTES:
            _safe_failure()
        raw = self._json(
            "POST",
            f"/repos/{self._repository}/git/blobs",
            {
                "content": base64.b64encode(content).decode("ascii"),
                "encoding": "base64",
            },
        )
        if not isinstance(raw, dict):
            _safe_failure()
        return _sha(raw.get("sha"))

    def create_tree(self, entries: Iterable[Mapping[str, object]]) -> str:
        normalized = _normalize_tree_entries(entries)
        raw = self._json(
            "POST",
            f"/repos/{self._repository}/git/trees",
            {"tree": normalized},
        )
        if not isinstance(raw, dict):
            _safe_failure()
        return _sha(raw.get("sha"))

    def create_commit(
        self,
        message: str,
        tree: str,
        parents: Iterable[str],
    ) -> str:
        parent_values = tuple(parents)
        if (
            type(message) is not str
            or not message
            or len(message) > 4_096
            or len(parent_values) > 1
            or "SkillScout-State: v1" not in message
        ):
            _safe_failure()
        raw = self._json(
            "POST",
            f"/repos/{self._repository}/git/commits",
            {
                "message": message,
                "tree": _sha(tree),
                "parents": [_sha(parent) for parent in parent_values],
            },
        )
        if not isinstance(raw, dict):
            _safe_failure()
        return _sha(raw.get("sha"))

    def create_state_ref(self, sha: str) -> StateRefObservation:
        expected = _sha(sha)
        raw = self._json(
            "POST",
            f"/repos/{self._repository}/git/refs",
            {"ref": STATE_REF, "sha": expected},
            conflict_on_write=True,
        )
        return self._ref(raw, expected)

    def update_state_ref(self, sha: str, *, force: bool) -> StateRefObservation:
        if force is not False:
            _safe_failure()
        expected = _sha(sha)
        raw = self._json(
            "PATCH",
            f"/repos/{self._repository}/git/refs/heads/skillscout-state",
            {"sha": expected, "force": False},
            conflict_on_write=True,
        )
        return self._ref(raw, expected)

    def _ref(self, raw: object, expected_sha: str | None = None) -> StateRefObservation:
        if (
            not isinstance(raw, dict)
            or raw.get("ref") != STATE_REF
            or not isinstance(raw.get("object"), dict)
        ):
            _safe_failure()
        sha = _sha(raw["object"].get("sha"))
        if expected_sha is not None and sha != expected_sha:
            raise StateBranchConflict
        return StateRefObservation(STATE_REF, sha)

    def _json(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        cap: int = _MAX_RESPONSE_BYTES,
        allow_not_found: bool = False,
        conflict_on_write: bool = False,
        read_budget: ResolverReadBudget | None = None,
    ) -> Any:
        request_arguments: dict[str, object] = {}
        if read_budget is not None:
            request_arguments["timeout"] = read_budget.begin_request()
        try:
            response = self._client.send(
                self._client.build_request(
                    method,
                    path,
                    json=payload,
                    **request_arguments,
                ),
                stream=True,
            )
        except httpx.TransportError:
            _safe_failure(ErrorCode.STAGE_TRANSIENT_FAILURE)
        except httpx.HTTPError:
            _safe_failure()
        try:
            request_id = response.headers.get("x-github-request-id")
            if (
                type(request_id) is not str
                or not request_id
                or len(request_id) > _MAX_REQUEST_ID_CHARS
                or _GITHUB_REQUEST_ID.fullmatch(request_id) is None
            ):
                _safe_failure()
            if response.status_code in {301, 302, 303, 307, 308}:
                _safe_failure()
            if conflict_on_write and response.status_code in {409, 422}:
                raise StateBranchConflict
            if response.status_code == 404 and allow_not_found:
                raise StateRefNotFound
            if response.status_code == 429 or response.status_code >= 500:
                _safe_failure(ErrorCode.STAGE_TRANSIENT_FAILURE)
            if (
                not 200 <= response.status_code < 300
                or "application/json" not in response.headers.get("content-type", "")
            ):
                _safe_failure()
            pieces: list[bytes] = []
            consumed = 0
            try:
                for piece in response.iter_bytes(65_536):
                    if read_budget is not None:
                        read_budget.charge_response_bytes(len(piece))
                    consumed += len(piece)
                    if consumed > cap:
                        _safe_failure()
                    pieces.append(piece)
            except httpx.TransportError:
                _safe_failure(ErrorCode.STAGE_TRANSIENT_FAILURE)
            try:
                return json.loads(b"".join(pieces))
            except (UnicodeDecodeError, json.JSONDecodeError):
                _safe_failure()
        finally:
            response.close()


class StateBranchStore:
    """Verify complete state bundles and advance only the exact fixed ref."""

    def __init__(self, remote: object) -> None:
        self._remote = remote
        self._commit_cache: dict[str, object] = {}
        self._tree_cache: dict[str, object] = {}
        self._blob_cache: dict[str, bytes] = {}

    def restore(
        self,
        *,
        read_budget: ResolverReadBudget | None = None,
    ) -> StateRestoreObservation:
        try:
            ref = (
                self._remote.get_state_ref(read_budget=read_budget)
                if read_budget is not None
                else self._remote.get_state_ref()
            )
        except StateRefNotFound:
            return StateRestoreObservation("absent", None, None)
        return StateRestoreObservation(
            "verified",
            ref.sha,
            self.restore_commit(ref.sha, read_budget=read_budget),
        )

    def restore_commit(
        self,
        commit_sha: str,
        *,
        read_budget: ResolverReadBudget | None = None,
    ) -> VerifiedStateBundle:
        expected_commit_sha = _sha(commit_sha)
        commit = self._cached_read(
            self._commit_cache,
            "get_commit",
            expected_commit_sha,
            read_budget=read_budget,
        )
        if commit.sha != expected_commit_sha or len(commit.parents) > 1:
            raise StateIntegrityFailure
        entries = self._cached_read(
            self._tree_cache,
            "get_tree",
            commit.tree_sha,
            read_budget=read_budget,
        )
        entry_map = _validate_tree_shape(entries)
        root_entry = entry_map.get("state/root.json")
        if root_entry is None:
            raise StateIntegrityFailure
        root_bytes = self._cached_read(
            self._blob_cache,
            "get_blob",
            root_entry.sha,
            read_budget=read_budget,
        )
        if root_entry.size is not None and root_entry.size != len(root_bytes):
            raise StateIntegrityFailure
        root = _parse_root(root_bytes)
        if commit.message != _state_commit_message(root.root_digest):
            raise StateIntegrityFailure
        if commit.parents and root.state_parent_commit_sha != commit.parents[0]:
            raise StateIntegrityFailure
        expected_paths = _expected_paths(root)
        if set(entry_map) != expected_paths:
            raise StateIntegrityFailure
        files: list[StateOwnedFile] = [StateOwnedFile("state/root.json", root_bytes)]
        object_digests = {item.locator: item.object_digest for item in root.objects}
        database_digests = {item.locator: item.content_digest for item in root.databases}
        for path in sorted(expected_paths - {"state/root.json"}):
            content = self._cached_read(
                self._blob_cache,
                "get_blob",
                entry_map[path].sha,
                read_budget=read_budget,
            )
            _validate_content(
                path,
                content,
                object_digests.get(path) or database_digests.get(path),
            )
            if entry_map[path].size is not None and entry_map[path].size != len(content):
                raise StateIntegrityFailure
            files.append(StateOwnedFile(path, content))
        bundle = VerifiedStateBundle(root, tuple(files))
        _validate_bundle(bundle, expected_parent=commit.parents[0] if commit.parents else None)
        return bundle

    def inspect_commit_root(
        self,
        commit_sha: str,
        *,
        read_budget: ResolverReadBudget | None = None,
    ) -> StateCommitRootObservation:
        """Verify one immutable commit manifest without reading owned payload blobs."""

        expected_commit_sha = _sha(commit_sha)
        commit = self._cached_read(
            self._commit_cache,
            "get_commit",
            expected_commit_sha,
            read_budget=read_budget,
        )
        if commit.sha != expected_commit_sha or len(commit.parents) > 1:
            raise StateIntegrityFailure
        entries = self._cached_read(
            self._tree_cache,
            "get_tree",
            commit.tree_sha,
            read_budget=read_budget,
        )
        entry_map = _validate_tree_shape(entries)
        root_entry = entry_map.get("state/root.json")
        if root_entry is None:
            raise StateIntegrityFailure
        root_bytes = self._cached_read(
            self._blob_cache,
            "get_blob",
            root_entry.sha,
            read_budget=read_budget,
        )
        if (
            root_entry.sha != _git_blob_id(root_bytes)
            or root_entry.size is not None
            and root_entry.size != len(root_bytes)
        ):
            raise StateIntegrityFailure
        root = _parse_root(root_bytes)
        if (
            commit.message != _state_commit_message(root.root_digest)
            or commit.parents
            and root.state_parent_commit_sha != commit.parents[0]
            or set(entry_map) != _expected_paths(root)
        ):
            raise StateIntegrityFailure
        declared_sizes = {
            item.locator: item.size_bytes for item in (*root.objects, *root.databases)
        }
        for path, size in declared_sizes.items():
            entry = entry_map[path]
            if entry.size is not None and entry.size != size:
                raise StateIntegrityFailure
        return StateCommitRootObservation(
            commit=commit,
            root=root,
            object_digests=tuple(item.object_digest for item in root.objects),
            declared_content_bytes=(len(root_bytes) + sum(declared_sizes.values())),
        )

    def _read(
        self,
        method_name: str,
        *arguments: object,
        read_budget: ResolverReadBudget | None,
    ) -> object:
        method = getattr(self._remote, method_name)
        if read_budget is None:
            return method(*arguments)
        return method(*arguments, read_budget=read_budget)

    def _cached_read(
        self,
        cache: dict[str, object] | dict[str, bytes],
        method_name: str,
        identity: str,
        *,
        read_budget: ResolverReadBudget | None,
    ) -> object:
        cached = cache.get(identity)
        if cached is not None:
            return cached
        value = self._read(
            method_name,
            identity,
            read_budget=read_budget,
        )
        cache[identity] = value  # type: ignore[assignment]
        return value

    @staticmethod
    def restore_from_fixture(
        fixture: object,
        *,
        state_ref: str | None,
        mutation: str | None = None,
    ) -> StateRestoreObservation:
        if mutation is not None:
            raise StateIntegrityFailure
        if not isinstance(fixture, dict) or fixture.get("schema_version") != (
            "state-branch-fixture-v1"
        ):
            raise StateIntegrityFailure
        if state_ref is None:
            return StateRestoreObservation("absent", None, None)
        try:
            observed = _sha(state_ref)
            root = DiscoveryStateRootV1.model_validate(fixture.get("root"), strict=True)
        except (SafeFailure, ValidationError):
            raise StateIntegrityFailure from None
        if root.state_parent_commit_sha != observed:
            raise StateIntegrityFailure
        raw_databases = fixture.get("databases")
        raw_objects = fixture.get("objects")
        if not isinstance(raw_databases, dict) or not isinstance(raw_objects, dict):
            raise StateIntegrityFailure
        expected_databases = {
            item.owner: {
                "content_digest": item.content_digest,
                "size_bytes": item.size_bytes,
            }
            for item in root.databases
        }
        expected_objects = {
            item.object_digest: {
                "locator": item.locator,
                "size_bytes": item.size_bytes,
            }
            for item in root.objects
        }
        if raw_databases != expected_databases or raw_objects != expected_objects:
            raise StateIntegrityFailure
        return StateRestoreObservation("verified", observed, VerifiedStateBundle(root))

    def sync(
        self,
        bundle: VerifiedStateBundle,
        observed_head: str | None,
        *,
        expected_prior_root_digest: str | None = None,
    ) -> StateSyncObservation:
        expected_parent = None if observed_head is None else _sha(observed_head)
        files = _validate_bundle(bundle, expected_parent=expected_parent)
        if (
            expected_prior_root_digest is not None
            and bundle.root.prior_root_digest != _require_digest(expected_prior_root_digest)
        ):
            raise StateIntegrityFailure
        try:
            current = self._remote.get_state_ref()
        except StateRefNotFound:
            current = None
        if (current is None) != (expected_parent is None):
            raise StateBranchConflict
        if current is not None and current.sha != expected_parent:
            raise StateBranchConflict

        parent_entries: dict[str, StateTreeEntry] = {}
        if current is not None:
            parent_commit = self._remote.get_commit(current.sha)
            if (
                parent_commit.sha != current.sha
                or len(parent_commit.parents) > 1
                or (
                    expected_prior_root_digest is not None
                    and parent_commit.message != _state_commit_message(expected_prior_root_digest)
                )
            ):
                raise StateBranchConflict
            try:
                parent_entries = _validate_tree_shape(self._remote.get_tree(parent_commit.tree_sha))
            except StateIntegrityFailure:
                raise StateBranchConflict from None

        blob_entries: list[dict[str, object]] = []
        for path, content in sorted(files.items()):
            expected_blob_sha = _git_blob_id(content)
            parent_entry = parent_entries.get(path)
            if parent_entry is not None and parent_entry.sha == expected_blob_sha:
                blob_sha = expected_blob_sha
            else:
                blob_sha = self._remote.create_blob(content)
                if blob_sha != expected_blob_sha:
                    raise StateBranchConflict
            blob_entries.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }
            )
        tree_sha = self._remote.create_tree(blob_entries)
        parents = () if expected_parent is None else (expected_parent,)
        commit_sha = self._remote.create_commit(
            _state_commit_message(bundle.root.root_digest),
            tree_sha,
            parents,
        )
        try:
            if expected_parent is None:
                response = self._remote.create_state_ref(commit_sha)
            else:
                response = self._remote.update_state_ref(commit_sha, force=False)
            if response.sha != commit_sha:
                raise StateBranchConflict
            return self._verify_sync(
                bundle,
                previous_head=expected_parent,
                commit_sha=commit_sha,
                tree_sha=tree_sha,
                expected_files=files,
            )
        except (
            SafeFailure,
            StateBranchConflict,
            StateIntegrityFailure,
            StateRefNotFound,
        ) as error:
            # No broad exception handling here: only the known ref-write or
            # immediate verification failures can be reconciled by proving the
            # exact candidate commit remotely.  Programming errors and any
            # other unexpected condition must propagate unchanged.
            raise StateBranchPostCasUncertain(
                candidate_commit_sha=commit_sha,
                candidate_tree_sha=tree_sha,
                previous_head=expected_parent,
                expected_root_digest=bundle.root.root_digest,
            ) from error

    def reconcile_post_cas_uncertainty(
        self,
        failure: StateBranchPostCasUncertain,
        bundle: VerifiedStateBundle,
        observed_head: str | None,
        *,
        expected_prior_root_digest: str | None = None,
    ) -> StateSyncObservation:
        """Recover only a fully proven exact child after a post-CAS read loss."""

        if type(failure) is not StateBranchPostCasUncertain:
            raise StateIntegrityFailure
        expected_parent = None if observed_head is None else _sha(observed_head)
        files = _validate_bundle(bundle, expected_parent=expected_parent)
        if (
            expected_prior_root_digest is not None
            and bundle.root.prior_root_digest
            != _require_digest(expected_prior_root_digest)
        ):
            raise StateIntegrityFailure
        if (
            failure.previous_head != expected_parent
            or failure.expected_root_digest != bundle.root.root_digest
            or _SHA.fullmatch(failure.candidate_commit_sha) is None
            or _SHA.fullmatch(failure.candidate_tree_sha) is None
        ):
            raise StateBranchConflict

        restored = self.restore()
        if (
            restored.status != "verified"
            or restored.observed_head != failure.candidate_commit_sha
            or restored.bundle is None
        ):
            raise StateBranchConflict
        proof = self.inspect_commit_root(failure.candidate_commit_sha)
        expected_parents = () if expected_parent is None else (expected_parent,)
        if (
            proof.commit.sha != failure.candidate_commit_sha
            or proof.commit.tree_sha != failure.candidate_tree_sha
            or proof.commit.parents != expected_parents
            or proof.commit.message != _state_commit_message(bundle.root.root_digest)
            or proof.root != bundle.root
            or proof.root.root_digest != bundle.root.root_digest
            or restored.bundle.root != bundle.root
            or restored.bundle.content_by_path() != files
            or len(restored.bundle.files) != len(bundle.files)
        ):
            raise StateBranchConflict
        return StateSyncObservation(
            "verified",
            expected_parent,
            failure.candidate_commit_sha,
            failure.candidate_tree_sha,
            bundle.root.root_digest,
        )

    def _verify_sync(
        self,
        bundle: VerifiedStateBundle,
        *,
        previous_head: str | None,
        commit_sha: str,
        tree_sha: str,
        expected_files: dict[str, bytes],
    ) -> StateSyncObservation:
        reread_ref = self._remote.get_state_ref()
        if reread_ref.sha != commit_sha:
            raise StateBranchConflict
        commit = self._remote.get_commit(commit_sha)
        expected_parents = () if previous_head is None else (previous_head,)
        if (
            commit.sha != commit_sha
            or commit.tree_sha != tree_sha
            or commit.parents != expected_parents
            or commit.message != _state_commit_message(bundle.root.root_digest)
        ):
            raise StateBranchConflict
        entries = self._remote.get_tree(tree_sha)
        try:
            observed = _validate_tree_shape(entries)
        except StateIntegrityFailure:
            raise StateBranchConflict from None
        if set(observed) != set(expected_files):
            raise StateBranchConflict
        for path, content in expected_files.items():
            entry = observed[path]
            if entry.sha != _git_blob_id(content):
                raise StateBranchConflict
        return StateSyncObservation(
            "verified",
            previous_head,
            commit_sha,
            tree_sha,
            bundle.root.root_digest,
        )

    def sync_fixture(
        self,
        fixture: object,
        *,
        observed_head: str,
    ) -> StateSyncObservation:
        observation = self.restore_from_fixture(
            fixture,
            state_ref=observed_head,
        )
        if observation.bundle is None:
            raise StateIntegrityFailure
        sync_fixture = getattr(self._remote, "sync_fixture", None)
        if callable(sync_fixture):
            return sync_fixture(observation.bundle, observed_head)
        return self.sync(observation.bundle, observed_head)


class StateBranchDurabilityBarrier:
    """Remote acknowledgement boundary for one exact semantic transition."""

    def __init__(
        self,
        *,
        state_store: StateBranchStore,
        query_set_digest: str,
        budget_policy_digest: str,
    ) -> None:
        if type(state_store) is not StateBranchStore:
            raise ValueError("invalid state-branch durability store")
        _require_digest(query_set_digest)
        _require_digest(budget_policy_digest)
        self._state_store = state_store
        self._query_set_digest = query_set_digest
        self._budget_policy_digest = budget_policy_digest

    def confirm(
        self,
        *,
        transition: SemanticDurabilityTransition,
        pipeline_store: object,
        operations_store: object,
        publication_store: object,
    ) -> DurabilityReceipt:
        """Export, CAS, fully reread, and acknowledge an exact owned transition."""

        try:
            return self._confirm(
                transition=transition,
                pipeline_store=pipeline_store,
                operations_store=operations_store,
                publication_store=publication_store,
            )
        except SafeFailure as failure:
            if failure.code is ErrorCode.STATE_OPERATION_FAILED:
                raise
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None
        except Exception:
            raise SafeFailure(ErrorCode.STATE_OPERATION_FAILED) from None

    def _confirm(
        self,
        *,
        transition: SemanticDurabilityTransition,
        pipeline_store: object,
        operations_store: object,
        publication_store: object,
    ) -> DurabilityReceipt:
        if type(transition) is not SemanticDurabilityTransition:
            raise ValueError("invalid semantic durability transition")

        pipeline = pipeline_store.export_owned_state()
        operations = operations_store.export_owned_state()
        publication = publication_store.export_owned_state()
        if (
            pipeline.export_digest != transition.pipeline_export_digest
            or operations.export_digest != transition.operations_export_digest
            or publication.export_digest != transition.publication_export_digest
        ):
            raise StateIntegrityFailure
        self._verify_transition_fact(operations, transition)

        # Import locally to keep operations_state's existing bundle coordinator
        # free to import the fixed state-branch value types without a cycle.
        from skillscout.adapters.operations_state import (
            _bundle_from_exports,
            _parse_bundle_exports,
        )

        bundle, _ = _bundle_from_exports(
            pipeline=pipeline,
            operations=operations,
            publication=publication,
            prior_root_digest=transition.expected_prior_root_digest,
            state_parent_commit_sha=transition.expected_prior_state_head,
            query_set_digest=self._query_set_digest,
            budget_policy_digest=self._budget_policy_digest,
            created_at=transition.recorded_at,
        )

        reread = None
        try:
            synchronized = self._state_store.sync(
                bundle,
                transition.expected_prior_state_head,
                expected_prior_root_digest=(transition.expected_prior_root_digest),
            )
            verified_head = synchronized.commit_sha
        except StateBranchPostCasUncertain:
            # This narrow uncertainty is recoverable only by the
            # authority-carrier path, which additionally proves its exact
            # authority and resume-locator fact delta before a full-bundle
            # reconciliation.  Semantic durability stays fail-closed here.
            raise
        except StateBranchConflict:
            reread = self._state_store.restore()
            if (
                reread.status != "verified"
                or reread.observed_head is None
                or reread.bundle is None
                or not self._bundles_equal(reread.bundle, bundle)
            ):
                raise StateBranchConflict from None
            # A restart or ambiguous post-CAS observation receives authority
            # only by fully restoring the already-present exact state.
            verified_head = reread.observed_head
        if reread is None:
            reread = self._state_store.restore()
        if (
            reread.status != "verified"
            or reread.observed_head != verified_head
            or reread.bundle is None
            or not self._bundles_equal(reread.bundle, bundle)
        ):
            raise StateIntegrityFailure
        (
            remote_pipeline,
            remote_operations,
            remote_publication,
            _remote_projection,
        ) = _parse_bundle_exports(reread.bundle)
        if (
            remote_pipeline != pipeline
            or remote_operations != operations
            or remote_publication != publication
        ):
            raise StateIntegrityFailure
        self._verify_transition_fact(remote_operations, transition)
        return DurabilityReceipt.from_remote_verification(
            transition=transition,
            verified_state_head=verified_head,
            state_root_digest=reread.bundle.root.root_digest,
            pipeline_database_digest=remote_pipeline.database_digest,
            operations_database_digest=remote_operations.database_digest,
            publication_database_digest=remote_publication.database_digest,
            pipeline_projection_digest=remote_pipeline.projection_digest,
            operations_projection_digest=remote_operations.projection_digest,
            publication_projection_digest=remote_publication.projection_digest,
        )

    @staticmethod
    def _bundles_equal(
        left: VerifiedStateBundle,
        right: VerifiedStateBundle,
    ) -> bool:
        return (
            left.root == right.root
            and left.content_by_path() == right.content_by_path()
            and len(left.files) == len(right.files)
        )

    @staticmethod
    def _verify_transition_fact(
        operations: object,
        transition: SemanticDurabilityTransition,
    ) -> None:
        expected_status = {
            "attempt_started": "started",
            "result_decided": "decided",
            "result_confirmed_retryable": "confirmed_retryable",
            "result_outcome_unknown": "semantic_outcome_unknown",
        }[transition.transition]
        matches = 0
        for fact in operations.facts:
            if fact.kind != "semantic_attempt":
                continue
            try:
                payload = json.loads(fact.payload_json)
            except (TypeError, ValueError):
                raise StateIntegrityFailure from None
            value = payload.get("value") if type(payload) is dict else None
            if type(value) is not dict:
                raise StateIntegrityFailure
            identity = (
                value.get("run_id"),
                value.get("repository_id"),
                value.get("workflow_authority_digest"),
                value.get("stage"),
                value.get("attempt_no"),
            )
            expected_identity = (
                transition.operations_run_id,
                transition.repository_id,
                transition.workflow_authority_digest,
                transition.stage,
                transition.attempt_no,
            )
            if identity == expected_identity:
                if (
                    value.get("status") != expected_status
                    or value.get("recorded_at") != transition.recorded_at
                ):
                    raise StateIntegrityFailure
                matches += 1
        if matches != 1:
            raise StateIntegrityFailure


class FixtureStateRemote:
    """Bounded in-memory conflict model used by the recorded fixture contract."""

    def __init__(self, *, case_name: str) -> None:
        self.case_name = case_name
        self.force_values: list[bool] = []
        self.followup_actions: list[str] = []
        self.commit_parents: list[tuple[str, ...]] = []

    def sync_fixture(
        self,
        bundle: VerifiedStateBundle,
        observed_head: str,
    ) -> StateSyncObservation:
        del bundle
        if self.case_name == "head_changed":
            raise StateBranchConflict
        self.commit_parents.append((observed_head,))
        self.force_values.append(False)
        if self.case_name in {
            "update_409",
            "update_422",
            "lying_mutation_response",
            "reread_mismatch",
        }:
            raise StateBranchConflict
        raise StateIntegrityFailure


def _parse_root(content: bytes) -> DiscoveryStateRootV1:
    if (
        type(content) is not bytes
        or not content
        or len(content) > _MAX_ROOT_BYTES
        or _contains_canary(content)
    ):
        raise StateIntegrityFailure
    try:
        raw = json.loads(content)
        root = DiscoveryStateRootV1.model_validate(raw, strict=True)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        raise StateIntegrityFailure from None
    if canonical_json_bytes(root.model_dump(mode="json", exclude_none=False)) != content:
        raise StateIntegrityFailure
    return root


def _expected_paths(root: DiscoveryStateRootV1) -> set[str]:
    return {
        "state/root.json",
        *(item.locator for item in root.objects),
        *(item.locator for item in root.databases),
    }


def _validate_content(path: str, content: bytes, expected_digest: str | None) -> None:
    if type(content) is not bytes or not content or expected_digest is None:
        raise StateIntegrityFailure
    limit = _MAX_OBJECT_BYTES if _OBJECT_PATH.fullmatch(path) else _MAX_DATABASE_BYTES
    if (
        len(content) > limit
        or _contains_canary(content)
        or _digest_bytes(content) != expected_digest
    ):
        raise StateIntegrityFailure
    if _OBJECT_PATH.fullmatch(path):
        try:
            parsed = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise StateIntegrityFailure from None
        if canonical_json_bytes(parsed) != content:
            raise StateIntegrityFailure


def _validate_bundle(
    bundle: VerifiedStateBundle,
    *,
    expected_parent: str | None,
) -> dict[str, bytes]:
    if type(bundle) is not VerifiedStateBundle:
        raise StateIntegrityFailure
    root = bundle.root
    if expected_parent is not None and root.state_parent_commit_sha != expected_parent:
        raise StateIntegrityFailure
    files = bundle.content_by_path()
    if len(files) != len(bundle.files) or set(files) != _expected_paths(root):
        raise StateIntegrityFailure
    root_bytes = files.get("state/root.json")
    if root_bytes is None or _parse_root(root_bytes) != root:
        raise StateIntegrityFailure
    object_digests = {item.locator: item.object_digest for item in root.objects}
    database_digests = {item.locator: item.content_digest for item in root.databases}
    for path, content in files.items():
        if path == "state/root.json":
            continue
        _validate_content(
            path,
            content,
            object_digests.get(path) or database_digests.get(path),
        )
    return files


def _validate_tree_shape(
    entries: Iterable[StateTreeEntry],
) -> dict[str, StateTreeEntry]:
    values = tuple(entries)
    if len(values) > _MAX_TREE_ENTRIES:
        raise StateIntegrityFailure
    output: dict[str, StateTreeEntry] = {}
    for entry in values:
        if (
            type(entry) is not StateTreeEntry
            or entry.mode != "100644"
            or entry.path in output
            or (
                entry.path != "state/root.json"
                and entry.path not in _DATABASE_PATHS
                and _OBJECT_PATH.fullmatch(entry.path) is None
            )
            or _SHA.fullmatch(entry.sha) is None
        ):
            raise StateIntegrityFailure
        object_match = _OBJECT_PATH.fullmatch(entry.path)
        if object_match is not None and object_match.group(1) != object_match.group(2)[:2]:
            raise StateIntegrityFailure
        if entry.size is not None:
            limit = (
                _MAX_ROOT_BYTES
                if entry.path == "state/root.json"
                else _MAX_OBJECT_BYTES
                if object_match is not None
                else _MAX_DATABASE_BYTES
            )
            if entry.size <= 0 or entry.size > limit:
                raise StateIntegrityFailure
        output[entry.path] = entry
    return output


def _normalize_tree_entries(
    entries: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    values = list(entries)
    if len(values) > _MAX_TREE_ENTRIES:
        _safe_failure()
    normalized: list[dict[str, object]] = []
    paths: set[str] = set()
    for entry in values:
        if not isinstance(entry, Mapping) or set(entry) != {
            "path",
            "mode",
            "type",
            "sha",
        }:
            _safe_failure()
        path = entry["path"]
        if (
            type(path) is not str
            or path in paths
            or entry["mode"] != "100644"
            or entry["type"] != "blob"
            or (
                path != "state/root.json"
                and path not in _DATABASE_PATHS
                and _OBJECT_PATH.fullmatch(path) is None
            )
        ):
            _safe_failure()
        paths.add(path)
        normalized.append(
            {
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": _sha(entry["sha"]),
            }
        )
    return sorted(normalized, key=lambda item: str(item["path"]))


def _allowed_tree_path(path: str) -> bool:
    if path in {
        "state",
        "state/databases",
        "state/objects",
        "state/objects/sha256",
    }:
        return True
    prefix = "state/objects/sha256/"
    suffix = path.removeprefix(prefix)
    return (
        path.startswith(prefix)
        and len(suffix) == 2
        and re.fullmatch(r"[0-9a-f]{2}", suffix) is not None
    )


def _required_directory_paths(
    entries: Iterable[StateTreeEntry],
) -> set[str]:
    required = {"state"}
    for entry in entries:
        parts = entry.path.split("/")
        required.update("/".join(parts[:index]) for index in range(2, len(parts)))
    return required
