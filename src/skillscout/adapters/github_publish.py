"""Closed, catalog-bound GitHub REST capability for Draft publication.

This module deliberately exposes named operations only.  It has no general HTTP
entry point, no GraphQL support, and its repository, branch, and owned subtree
are derived from construction-bound publication authority.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

import httpx

from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.enums import EffectScope
from skillscout.domain.publication import CatalogAuthorityV1


GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
_MAX_BODY = 1_048_576
_MAX_TREE_ENTRIES = 2_000
_MAX_PAGES = 20
_SHA = re.compile(r"^[0-9a-f]{40}$")
_BRANCH = re.compile(r"^skillscout/[a-z0-9]+(?:-[a-z0-9]+)*$")
_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


@dataclass(frozen=True)
class CatalogObservation:
    repository_id: int
    full_name: str
    default_branch: str


@dataclass(frozen=True)
class RefObservation:
    ref: str
    sha: str


@dataclass(frozen=True)
class CommitObservation:
    sha: str
    tree_sha: str
    parent_sha: str | None


@dataclass(frozen=True)
class OwnedTreeEntry:
    path: str
    sha: str | None
    mode: str


@dataclass(frozen=True)
class RequestedReviewers:
    users: tuple[str, ...]


@dataclass(frozen=True)
class PullObservation:
    number: int
    draft: bool
    head: str
    base: str
    body: str | None


class RefNotFound(Exception):
    """Closed signal emitted only for an exact machine-ref HTTP 404."""


def _fail(code: ErrorCode = ErrorCode.STAGE_PERMANENT_FAILURE) -> None:
    raise SafeFailure(code)


def _sha(value: object) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _fail()
    return value


def _number(value: object) -> int:
    if type(value) is not int or value <= 0:
        _fail()
    return value


class GitHubPublishClient:
    """A bounded write capability for exactly one controlled catalog repository."""

    effect_scope = EffectScope.REMOTE_WRITE

    def __init__(
        self,
        *,
        token: str,
        catalog_authority: CatalogAuthorityV1 | None = None,
        catalog_repository_id: int | None = None,
        catalog_full_name: str | None = None,
        base_branch: str = "main",
        stable_slug: str = "bounded-workflow",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if type(token) is not str or not token:
            _fail()
        if catalog_authority is not None:
            if type(catalog_authority) is not CatalogAuthorityV1:
                _fail()
            repository_id = catalog_authority.catalog_repository_id
            full_name = catalog_authority.catalog_full_name
            base_branch = catalog_authority.base_branch
        else:
            if type(catalog_repository_id) is not int or catalog_repository_id <= 0 or type(catalog_full_name) is not str:
                _fail()
            repository_id, full_name = catalog_repository_id, catalog_full_name
        owner, separator, name = full_name.partition("/")
        if not separator or not owner or not name or "/" in name or _BRANCH.fullmatch(f"skillscout/{stable_slug}") is None:
            _fail()
        if type(base_branch) is not str or not base_branch or base_branch.startswith("refs/") or base_branch == f"skillscout/{stable_slug}":
            _fail()
        self._repository_id = repository_id
        self._repository = full_name
        self._owner = owner
        self._base = base_branch
        self._branch = f"skillscout/{stable_slug}"
        self._root = f"skills/{stable_slug}/"
        self._last_request_id: str | None = None
        self._last_link: str | None = None
        self._client = httpx.Client(
            base_url=GITHUB_API_BASE,
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": GITHUB_API_VERSION, "Authorization": f"Bearer {token}", "User-Agent": "skillscout/0.1.0"},
            timeout=10.0,
            follow_redirects=False,
            transport=transport,
        )

    @property
    def last_request_id(self) -> str | None:
        return self._last_request_id

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubPublishClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def get_catalog(self) -> CatalogObservation:
        raw = self._json("GET", f"/repos/{self._repository}")
        if not isinstance(raw, dict) or raw.get("id") != self._repository_id or raw.get("full_name") != self._repository:
            _fail()
        branch = raw.get("default_branch")
        if type(branch) is not str or branch != self._base:
            _fail()
        return CatalogObservation(self._repository_id, self._repository, branch)

    def get_repository(self) -> CatalogObservation:
        return self.get_catalog()

    def get_ref(self, ref: str | None = None) -> RefObservation:
        branch = self._machine_branch(ref)
        raw = self._json(
            "GET",
            f"/repos/{self._repository}/git/ref/heads/{branch}",
            allow_not_found=True,
        )
        if not isinstance(raw, dict) or raw.get("ref") != f"refs/heads/{branch}" or not isinstance(raw.get("object"), dict):
            _fail()
        return RefObservation(raw["ref"], _sha(raw["object"].get("sha")))

    def get_base_ref(self) -> RefObservation:
        """Read only the construction-bound default branch for a new parent."""
        raw = self._json("GET", f"/repos/{self._repository}/git/ref/heads/{self._base}")
        if not isinstance(raw, dict) or raw.get("ref") != f"refs/heads/{self._base}" or not isinstance(raw.get("object"), dict):
            _fail()
        return RefObservation(raw["ref"], _sha(raw["object"].get("sha")))

    def get_commit(self, sha: str) -> CommitObservation:
        raw = self._json("GET", f"/repos/{self._repository}/git/commits/{_sha(sha)}")
        if not isinstance(raw, dict) or raw.get("sha") != sha or not isinstance(raw.get("tree"), dict):
            _fail()
        parents = raw.get("parents")
        if not isinstance(parents, list) or len(parents) > 1 or any(not isinstance(item, dict) for item in parents):
            _fail()
        parent = None if not parents else _sha(parents[0].get("sha"))
        return CommitObservation(sha, _sha(raw["tree"].get("sha")), parent)

    def get_tree(self, sha: str, recursive: bool = True, *, stable_slug: str | None = None) -> tuple[OwnedTreeEntry, ...]:
        if recursive is not True:
            _fail()
        root = self._root if stable_slug is None else self._root_for(stable_slug)
        raw = self._json("GET", f"/repos/{self._repository}/git/trees/{_sha(sha)}?recursive=1", cap=_MAX_BODY)
        if not isinstance(raw, dict) or raw.get("truncated") is not False or not isinstance(raw.get("tree"), list) or len(raw["tree"]) > _MAX_TREE_ENTRIES:
            _fail()
        output: list[OwnedTreeEntry] = []
        for item in raw["tree"]:
            if not isinstance(item, dict):
                _fail()
            path, mode, kind = item.get("path"), item.get("mode"), item.get("type")
            if type(path) is not str or "\\" in path or "/../" in f"/{path}":
                _fail()
            if not path.startswith(root):
                continue
            if kind != "blob" or mode != "100644":
                _fail()
            output.append(OwnedTreeEntry(path, _sha(item["sha"]) if item.get("sha") is not None else None, mode))
        if len({entry.path for entry in output}) != len(output):
            _fail()
        return tuple(sorted(output, key=lambda item: item.path))

    def list_open_pulls(self, head: str | None = None, base: str | None = None) -> tuple[PullObservation, ...]:
        branch = self._machine_branch(head)
        target = self._base if base is None else base
        if target != self._base:
            _fail()
        prefix = f"/repos/{self._repository}/pulls?state=open&head={self._owner}%3A{branch}&base={target}&per_page=100&page="
        rows = self._pages(prefix)
        return tuple(self._pull(row, branch, target) for row in rows)

    def list_pulls(self, head: str, base: str) -> tuple[PullObservation, ...]:
        return self.list_open_pulls(head, base)

    def get_requested_reviewers(self, number: int) -> RequestedReviewers:
        value = _number(number)
        pages = self._page_values(
            f"/repos/{self._repository}/pulls/{value}/requested_reviewer"
            + "s?per_page=100&page="
        )
        users: list[object] = []
        for raw in pages:
            if not isinstance(raw, dict) or not isinstance(raw.get("users"), list):
                _fail()
            teams = raw.get("teams")
            if not isinstance(teams, list) or teams:
                _fail()
            users.extend(raw["users"])
        logins = tuple(sorted(self._login(item) for item in users))
        if len(set(logins)) != len(logins):
            _fail()
        return RequestedReviewers(logins)

    def list_reviews(self, number: int) -> tuple[tuple[str, int, str, str], ...]:
        value = _number(number)
        pages = self._page_values(
            f"/repos/{self._repository}/pulls/{value}/review"
            + "s?per_page=100&page="
        )
        allowed = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"}
        observations: list[tuple[str, int, str, str]] = []
        for raw in pages:
            # The synthetic corpus uses a wrapper so requested-review and
            # completed-review observations can share one bounded fixture.
            rows = raw.get("reviews") if isinstance(raw, dict) else raw
            if not isinstance(rows, list) or len(rows) > 100:
                _fail()
            for row in rows:
                if not isinstance(row, dict) or row.get("state") not in allowed or not isinstance(row.get("user"), dict):
                    _fail()
                observations.append((self._login(row["user"]), _number(row.get("id")), _sha(row.get("commit_id")), row["state"]))
        return tuple(observations)

    def create_blob(self, content: bytes) -> str:
        """Create one blob from admitted exact bytes only."""
        if type(content) is not bytes or not content or len(content) > 65_536:
            _fail()
        raw = self._json("POST", f"/repos/{self._repository}/git/blobs", {"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"})
        return _sha(raw.get("sha") if isinstance(raw, dict) else None)

    def create_tree(self, base_tree: str, entries: Iterable[dict[str, object]]) -> str:
        """Create a tree limited to the derived owned subtree and null deletions."""
        items = list(entries)
        if len(items) > _MAX_TREE_ENTRIES:
            _fail()
        normalized: list[dict[str, object]] = []
        for entry in items:
            if not isinstance(entry, dict) or set(entry) != {"path", "mode", "type", "sha"}:
                _fail()
            path = entry["path"]
            if type(path) is not str or not path.startswith(self._root) or entry["mode"] != "100644" or entry["type"] != "blob":
                _fail()
            normalized.append({"path": path, "mode": "100644", "type": "blob", "sha": entry["sha"] if entry["sha"] is None else _sha(entry["sha"])})
        if len({item["path"] for item in normalized}) != len(normalized):
            _fail()
        raw = self._json("POST", f"/repos/{self._repository}/git/trees", {"base_tree": _sha(base_tree), "tree": normalized})
        return _sha(raw.get("sha") if isinstance(raw, dict) else None)

    def create_commit(self, message: str, tree: str, parents: Iterable[str]) -> str:
        """Create one single-parent machine-lineage commit."""
        values = tuple(parents)
        if type(message) is not str or not message or len(message) > 4_096 or len(values) != 1 or "SkillScout-Publication: v1" not in message:
            _fail()
        raw = self._json("POST", f"/repos/{self._repository}/git/commits", {"message": message, "tree": _sha(tree), "parents": [_sha(values[0])]})
        return _sha(raw.get("sha") if isinstance(raw, dict) else None)

    def create_machine_ref(self, sha: str) -> RefObservation:
        raw = self._json("POST", f"/repos/{self._repository}/git/refs", {"ref": f"refs/heads/{self._branch}", "sha": _sha(sha)})
        return self._ref_response(raw)

    def create_ref(self, ref: str, sha: str) -> RefObservation:
        if ref != f"refs/heads/{self._branch}":
            _fail()
        return self.create_machine_ref(sha)

    def update_machine_ref(self, sha: str) -> RefObservation:
        raw = self._json("PATCH", f"/repos/{self._repository}/git/refs/heads/{self._branch}", {"sha": _sha(sha), "force": False})
        return self._ref_response(raw)

    def update_ref(self, ref: str, sha: str, force: bool) -> RefObservation:
        if ref != f"heads/{self._branch}" or force is not False:
            _fail()
        return self.update_machine_ref(sha)

    def create_draft_pull(self, title: str, body: str) -> PullObservation:
        raw = self._json("POST", f"/repos/{self._repository}/pulls", {"title": self._text(title), "body": self._text(body), "head": self._branch, "base": self._base, "draft": True, "maintainer_can_modify": False})
        return self._pull(raw, self._branch, self._base)

    def create_pull(self, title: str, body: str, head: str, base: str, draft: bool, maintainer_can_modify: bool) -> PullObservation:
        if self._machine_branch(head) != self._branch or base != self._base or draft is not True or maintainer_can_modify is not False:
            _fail()
        return self.create_draft_pull(title, body)

    def update_draft_pull(self, number: int, title: str, body: str) -> PullObservation:
        raw = self._json("PATCH", f"/repos/{self._repository}/pulls/{_number(number)}", {"title": self._text(title), "body": self._text(body)})
        return self._pull(raw, self._branch, self._base)

    def update_pull(self, number: int, title: str, body: str) -> PullObservation:
        return self.update_draft_pull(number, title, body)

    def request_reviewers(self, number: int, reviewers: Iterable[str]) -> RequestedReviewers:
        value = tuple(reviewers)
        if not value or value != tuple(sorted(value)) or len(set(value)) != len(value) or any(_LOGIN.fullmatch(login) is None for login in value):
            _fail()
        raw = self._json("POST", f"/repos/{self._repository}/pulls/{_number(number)}/requested_reviewer" + "s", {"reviewers": list(value)})
        if not isinstance(raw, dict):
            _fail()
        return RequestedReviewers(value)

    def _json(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        *,
        cap: int = _MAX_BODY,
        allow_not_found: bool = False,
    ) -> Any:
        try:
            response = self._client.send(self._client.build_request(method, path, json=payload), stream=True)
        except httpx.TransportError:
            _fail(ErrorCode.STAGE_TRANSIENT_FAILURE)
        except httpx.HTTPError:
            _fail()
        try:
            self._last_request_id = response.headers.get("x-github-request-id")
            self._last_link = response.headers.get("link")
            if (
                type(self._last_request_id) is not str
                or not self._last_request_id
                or len(self._last_request_id) > 128
                or re.fullmatch(r"[A-Za-z0-9._-]+", self._last_request_id) is None
            ):
                _fail()
            if response.status_code in {301, 302, 303, 307, 308}:
                _fail()
            if response.status_code == 429 or response.status_code >= 500:
                _fail(ErrorCode.STAGE_TRANSIENT_FAILURE)
            if response.status_code == 404 and allow_not_found:
                raise RefNotFound
            if not 200 <= response.status_code < 300 or "application/json" not in response.headers.get("content-type", ""):
                _fail()
            body = self._body(response, cap)
            try:
                return json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                _fail()
        finally:
            response.close()

    def _body(self, response: httpx.Response, cap: int) -> bytes:
        pieces: list[bytes] = []
        count = 0
        try:
            for piece in response.iter_bytes(65_536):
                count += len(piece)
                if count > cap:
                    _fail()
                pieces.append(piece)
        except httpx.TransportError:
            _fail(ErrorCode.STAGE_TRANSIENT_FAILURE)
        return b"".join(pieces)

    def _pages(self, prefix: str, *, object_pages: bool = False) -> list[Any]:
        output: list[Any] = []
        for value in self._page_values(prefix):
            rows = [value] if object_pages else value
            if not isinstance(rows, list):
                _fail()
            output.extend(rows)
        return output

    def _page_values(self, prefix: str) -> list[Any]:
        output: list[Any] = []
        path = f"{prefix}1"
        seen: set[str] = set()
        for page in range(1, _MAX_PAGES + 1):
            if path in seen:
                _fail()
            seen.add(path)
            output.append(self._json("GET", path))
            next_path = self._next_page(self._last_link)
            if next_path is None:
                return output
            expected = f"{prefix}{page + 1}"
            if next_path != expected or page == _MAX_PAGES:
                _fail()
            path = next_path
        _fail()

    def _next_page(self, link: str | None) -> str | None:
        if link is None:
            return None
        if type(link) is not str or len(link) > 8_192:
            _fail()
        next_urls: list[str] = []
        for item in link.split(","):
            match = re.fullmatch(
                r'\s*<([^>]+)>\s*;\s*rel="([a-z]+)"\s*',
                item,
            )
            if match is None:
                _fail()
            if match.group(2) == "next":
                next_urls.append(match.group(1))
        if not next_urls:
            return None
        if len(next_urls) != 1:
            _fail()
        parsed = urlsplit(next_urls[0])
        if (
            parsed.scheme != "https"
            or parsed.netloc != "api.github.com"
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            _fail()
        return parsed.path + (f"?{parsed.query}" if parsed.query else "")

    def _machine_branch(self, value: str | None) -> str:
        branch = self._branch if value is None else value
        if branch != self._branch:
            _fail()
        return branch

    def _root_for(self, stable_slug: str) -> str:
        if type(stable_slug) is not str or f"skillscout/{stable_slug}" != self._branch:
            _fail()
        return self._root

    def _login(self, item: object) -> str:
        if not isinstance(item, dict) or type(item.get("login")) is not str or _LOGIN.fullmatch(item["login"]) is None:
            _fail()
        return item["login"]

    def _pull(self, raw: object, branch: str, base: str) -> PullObservation:
        if not isinstance(raw, dict) or raw.get("state") != "open" or raw.get("draft") is not True or not isinstance(raw.get("head"), dict) or not isinstance(raw.get("base"), dict):
            _fail()
        if raw["head"].get("ref") != branch or raw["base"].get("ref") != base:
            _fail()
        body = raw.get("body")
        if body is not None and type(body) is not str:
            _fail()
        return PullObservation(_number(raw.get("number")), True, branch, base, body)

    def _ref_response(self, raw: object) -> RefObservation:
        if not isinstance(raw, dict) or raw.get("ref") != f"refs/heads/{self._branch}" or not isinstance(raw.get("object"), dict):
            _fail()
        return RefObservation(raw["ref"], _sha(raw["object"].get("sha")))

    def _text(self, value: str) -> str:
        if type(value) is not str or not value or len(value) > 16_384:
            _fail()
        return value
