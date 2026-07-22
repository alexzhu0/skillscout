"""Closed read-only GitHub REST adapter over one serial httpx client."""

from __future__ import annotations

import base64
import binascii
import os
import re
import time
from typing import Annotated, Any, Callable, Literal, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.enums import EffectScope
from skillscout.domain.models import StrictFrozenModel

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
MAX_METADATA_BYTES = 1_048_576
MAX_TREE_BYTES = 8_388_608
MAX_LICENSE_BYTES = 1_048_576
MAX_BLOB_BYTES = 262_144
MAX_RETRY_AFTER_SECONDS = 60

_OWNER_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_HEX_PATTERN = re.compile(r"^[0-9a-f]{1,128}$")

_BoundedName = Annotated[str, Field(min_length=1, max_length=200)]
_HexSha = Annotated[str, Field(pattern=r"^[0-9a-f]{1,128}$")]


class _LenientFrozenModel(BaseModel):
    """Provider-response parsing: validate consumed fields, ignore the rest."""

    model_config = ConfigDict(frozen=True, strict=True)


class _RawOwner(_LenientFrozenModel):
    login: _BoundedName


class _RawLicenseRef(_LenientFrozenModel):
    spdx_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None


class _RawRepo(_LenientFrozenModel):
    id: Annotated[int, Field(ge=0)]
    name: _BoundedName
    owner: _RawOwner
    private: bool
    fork: bool
    archived: bool
    disabled: bool
    visibility: Annotated[str, Field(min_length=1, max_length=32)]
    default_branch: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    license: _RawLicenseRef | None = None


class _RawCommit(_LenientFrozenModel):
    sha: _HexSha


class _RawTreeEntry(_LenientFrozenModel):
    path: Annotated[str, Field(min_length=1, max_length=512)]
    mode: Annotated[str, Field(min_length=1, max_length=16)]
    type: Annotated[str, Field(min_length=1, max_length=16)]
    size: Annotated[int, Field(ge=0)] | None = None
    sha: _HexSha


class _RawTree(_LenientFrozenModel):
    tree: tuple[_RawTreeEntry, ...]
    truncated: bool


class _RawLicense(_LenientFrozenModel):
    sha: _HexSha
    license: _RawLicenseRef


class _RawBlob(_LenientFrozenModel):
    size: Annotated[int, Field(ge=0)]
    content: str
    encoding: str


class RateLimitFacts(StrictFrozenModel):
    """The rate-limit headers observed on one response, when present."""

    limit: Annotated[int, Field(ge=0)] | None = None
    remaining: Annotated[int, Field(ge=0)] | None = None
    reset: Annotated[int, Field(ge=0)] | None = None


class RepoMetadata(StrictFrozenModel):
    """The repository facts Scout and Filter are allowed to observe."""

    id: Annotated[int, Field(ge=0)]
    owner: _BoundedName
    name: _BoundedName
    default_branch: Annotated[str, Field(min_length=1, max_length=200)] | None
    private: bool
    fork: bool
    archived: bool
    disabled: bool
    visibility: Annotated[str, Field(min_length=1, max_length=32)]
    license_spdx: Annotated[str, Field(min_length=1, max_length=64)] | None
    rate_limit: RateLimitFacts


class TreeEntry(StrictFrozenModel):
    """One repository tree entry as observed from the provider."""

    path: Annotated[str, Field(min_length=1, max_length=512)]
    mode: Annotated[str, Field(min_length=1, max_length=16)]
    type: Annotated[str, Field(min_length=1, max_length=16)]
    size: Annotated[int, Field(ge=0)] | None
    sha: _HexSha


class TreeSnapshot(StrictFrozenModel):
    """The complete tree listing observed at one pinned commit."""

    entries: tuple[TreeEntry, ...]
    truncated: bool


class LicenseResponse(StrictFrozenModel):
    """The closed outcome of the license endpoint lookup at the pinned SHA."""

    status: Literal["confirmed", "not_found", "noassertion"]
    spdx_id: Annotated[str, Field(min_length=1, max_length=64)] | None
    license_blob_sha: _HexSha | None


class RedirectFacts(StrictFrozenModel):
    """One recorded same-host redirect followed by the adapter."""

    from_url: Annotated[str, Field(min_length=1, max_length=512)]
    to_url: Annotated[str, Field(min_length=1, max_length=512)]


def _require_segment(pattern: re.Pattern[str], value: str) -> str:
    if pattern.fullmatch(value) is None:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
    return value


def _parse_non_negative_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


class GitHubReadClient:
    """The only GitHub HTTP capability: serial, read-only, fail-closed."""

    def __init__(
        self,
        *,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        timeout: float = 10.0,
    ) -> None:
        resolved_token = token if token is not None else os.environ.get("SKILLSCOUT_GITHUB_TOKEN")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "skillscout/0.1.0",
        }
        if resolved_token:
            headers["Authorization"] = f"Bearer {resolved_token}"
        self._client = httpx.Client(
            base_url=GITHUB_API_BASE,
            headers=headers,
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
        )
        self._sleeper = sleeper
        self._redirects: list[RedirectFacts] = []
        self._last_request_id: str | None = None

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.REMOTE_READ

    @property
    def redirects(self) -> tuple[RedirectFacts, ...]:
        return tuple(self._redirects)

    @property
    def last_request_id(self) -> str | None:
        return self._last_request_id

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitHubReadClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def get_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
        path = (
            f"/repos/{_require_segment(_OWNER_REPO_PATTERN, owner)}"
            f"/{_require_segment(_OWNER_REPO_PATTERN, repo)}"
        )
        _status, response_headers, body = self._get(path, cap=MAX_METADATA_BYTES)
        raw = _validate_json(_RawRepo, body)
        return _validate(
            RepoMetadata,
            {
                "id": raw.id,
                "owner": raw.owner.login,
                "name": raw.name,
                "default_branch": raw.default_branch,
                "private": raw.private,
                "fork": raw.fork,
                "archived": raw.archived,
                "disabled": raw.disabled,
                "visibility": raw.visibility,
                "license_spdx": raw.license.spdx_id if raw.license else None,
                "rate_limit": _rate_limit_facts(response_headers),
            },
        )

    def resolve_commit(self, owner: str, repo: str, ref: str) -> str:
        path = (
            f"/repos/{_require_segment(_OWNER_REPO_PATTERN, owner)}"
            f"/{_require_segment(_OWNER_REPO_PATTERN, repo)}"
            f"/commits/{_require_segment(_REF_PATTERN, ref)}"
        )
        _status, _headers, body = self._get(path, cap=MAX_METADATA_BYTES)
        return _validate_json(_RawCommit, body).sha

    def get_tree(self, owner: str, repo: str, sha: str) -> TreeSnapshot:
        path = (
            f"/repos/{_require_segment(_OWNER_REPO_PATTERN, owner)}"
            f"/{_require_segment(_OWNER_REPO_PATTERN, repo)}"
            f"/git/trees/{_require_segment(_HEX_PATTERN, sha)}?recursive=1"
        )
        _status, _headers, body = self._get(path, cap=MAX_TREE_BYTES)
        raw = _validate_json(_RawTree, body)
        return _validate(
            TreeSnapshot,
            {
                "entries": tuple(
                    {
                        "path": entry.path,
                        "mode": entry.mode,
                        "type": entry.type,
                        "size": entry.size,
                        "sha": entry.sha,
                    }
                    for entry in raw.tree
                ),
                "truncated": raw.truncated,
            },
        )

    def get_license(self, owner: str, repo: str, sha: str) -> LicenseResponse:
        path = (
            f"/repos/{_require_segment(_OWNER_REPO_PATTERN, owner)}"
            f"/{_require_segment(_OWNER_REPO_PATTERN, repo)}"
            f"/license?ref={_require_segment(_HEX_PATTERN, sha)}"
        )
        status, _headers, body = self._get(path, cap=MAX_LICENSE_BYTES, not_found_ok=True)
        if status == 404:
            return LicenseResponse(status="not_found", spdx_id=None, license_blob_sha=None)
        raw = _validate_json(_RawLicense, body)
        spdx_id = raw.license.spdx_id
        if spdx_id == "NOASSERTION":
            return LicenseResponse(
                status="noassertion", spdx_id=None, license_blob_sha=None
            )
        return LicenseResponse(
            status="confirmed", spdx_id=spdx_id, license_blob_sha=raw.sha
        )

    def get_blob(self, owner: str, repo: str, blob_sha: str, expected_size: int) -> bytes:
        path = (
            f"/repos/{_require_segment(_OWNER_REPO_PATTERN, owner)}"
            f"/{_require_segment(_OWNER_REPO_PATTERN, repo)}"
            f"/git/blobs/{_require_segment(_HEX_PATTERN, blob_sha)}"
        )
        _status, _headers, body = self._get(path, cap=MAX_BLOB_BYTES)
        raw = _validate_json(_RawBlob, body)
        if raw.encoding != "base64":
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
        try:
            content = base64.b64decode(raw.content, validate=True)
        except (binascii.Error, ValueError):
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None
        if len(content) != raw.size or raw.size != expected_size:
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
        return content

    def _get(
        self,
        path: str,
        *,
        cap: int,
        not_found_ok: bool = False,
    ) -> tuple[int, httpx.Headers, bytes]:
        current = path
        followed = False
        while True:
            response = self._send(current)
            try:
                self._last_request_id = response.headers.get("x-github-request-id")
                status = response.status_code
                if status in (301, 307, 308):
                    if followed:
                        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
                    location = response.headers.get("location")
                    from_url = str(response.request.url)
                    if location is None or not _is_same_host(location):
                        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
                    self._redirects.append(
                        RedirectFacts(from_url=from_url, to_url=location)
                    )
                    current = location
                    followed = True
                    continue
                if 200 <= status < 300:
                    return status, response.headers, self._read_capped(response, cap)
                if status == 404 and not_found_ok:
                    return status, response.headers, b""
                if status == 429 or (
                    status == 403 and response.headers.get("x-ratelimit-remaining") == "0"
                ) or 500 <= status < 600:
                    retry_after = _parse_non_negative_int(
                        response.headers.get("retry-after")
                    )
                    self._sleeper(
                        float(min(retry_after or 0, MAX_RETRY_AFTER_SECONDS))
                    )
                    raise SafeFailure(ErrorCode.STAGE_TRANSIENT_FAILURE)
                raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
            finally:
                response.close()

    def _send(self, url: str) -> httpx.Response:
        try:
            return self._client.send(
                self._client.build_request("GET", url),
                stream=True,
            )
        except httpx.TransportError:
            raise SafeFailure(ErrorCode.STAGE_TRANSIENT_FAILURE) from None
        except httpx.HTTPError:
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None

    def _read_capped(self, response: httpx.Response, cap: int) -> bytes:
        chunks: list[bytes] = []
        consumed = 0
        try:
            for chunk in response.iter_bytes(65_536):
                consumed += len(chunk)
                if consumed > cap:
                    raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
                chunks.append(chunk)
        except SafeFailure:
            raise
        except httpx.TransportError:
            raise SafeFailure(ErrorCode.STAGE_TRANSIENT_FAILURE) from None
        except httpx.HTTPError:
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None
        return b"".join(chunks)


def _is_same_host(location: str) -> bool:
    try:
        target = httpx.URL(location)
    except httpx.InvalidURL:
        return False
    return target.scheme == "https" and target.host == "api.github.com"


def _rate_limit_facts(headers: httpx.Headers) -> RateLimitFacts:
    return _validate(
        RateLimitFacts,
        {
            "limit": _parse_non_negative_int(headers.get("x-ratelimit-limit")),
            "remaining": _parse_non_negative_int(headers.get("x-ratelimit-remaining")),
            "reset": _parse_non_negative_int(headers.get("x-ratelimit-reset")),
        },
    )


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _validate(model: type[_ModelT], value: Any) -> _ModelT:
    """Collapse provider-shape violations into the closed failure set."""

    try:
        return model.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None


def _validate_json(model: type[_ModelT], body: bytes) -> _ModelT:
    """Validate provider JSON bytes, accepting JSON arrays for tuple fields."""

    try:
        return model.model_validate_json(body)
    except (ValidationError, TypeError, ValueError, UnicodeDecodeError):
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None
