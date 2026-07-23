"""Recorded-fixture MockTransport loader with per-request recording."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "github"
OPENAI_FIXTURES = Path(__file__).parent / "fixtures" / "openai"
OPENAI_GENERATOR_FIXTURES = OPENAI_FIXTURES / "generator" / "cases.json"


@dataclass(frozen=True)
class RecordedResponse:
    """One frozen recorded HTTP response loaded from a fixture file."""

    status: int
    headers: dict[str, str]
    body: bytes


def _load_fixture(directory: Path, name: str) -> RecordedResponse:
    parsed = json.loads((directory / f"{name}.json").read_bytes())
    body = parsed["body"]
    payload = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
    return RecordedResponse(
        status=parsed["status"],
        headers={str(key): str(value) for key, value in parsed["headers"].items()},
        body=payload,
    )


def recorded_fixture(name: str) -> RecordedResponse:
    """Load one recorded GitHub response fixture without any network access."""

    return _load_fixture(FIXTURES, name)


def recorded_openai_fixture(name: str) -> RecordedResponse:
    """Load one recorded OpenAI response fixture without any network access."""

    return _load_fixture(OPENAI_FIXTURES, name)


def recorded_openai_generator_fixture(name: str) -> RecordedResponse:
    """Load one named Generator response from the shared recorded case set."""

    cases = json.loads(OPENAI_GENERATOR_FIXTURES.read_bytes())
    parsed = cases[name]
    body = parsed["body"]
    payload = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
    return RecordedResponse(
        status=parsed["status"],
        headers={str(key): str(value) for key, value in parsed["headers"].items()},
        body=payload,
    )


def git_blob_id(content: bytes) -> str:
    """Derive the deterministic git blob identifier for exact content bytes."""

    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def make_blob_entry(
    path: str,
    content: bytes,
    *,
    sha: str | None = None,
    mode: str = "100644",
) -> dict[str, object]:
    """Build one deterministic tree entry for a blob with exact content bytes."""

    return {
        "path": path,
        "mode": mode,
        "type": "blob",
        "size": len(content),
        "sha": sha or git_blob_id(content),
    }


def make_tree_fixture(
    entries: list[dict[str, object]],
    *,
    truncated: bool = False,
    request_id: str = "REQ-TREE-SYNTH",
) -> RecordedResponse:
    """Synthesize a recorded tree response from explicit entries."""

    body = json.dumps(
        {
            "sha": "aa00aa00aa00aa00aa00aa00aa00aa00aa00aa00",
            "url": "https://api.github.com/repos/example/approved-repo/git/trees/aa00",
            "tree": entries,
            "truncated": truncated,
        },
        separators=(",", ":"),
    ).encode()
    return RecordedResponse(
        status=200,
        headers={
            "content-type": "application/json; charset=utf-8",
            "x-github-request-id": request_id,
        },
        body=body,
    )


def make_blob_fixture(
    content: bytes,
    *,
    sha: str | None = None,
    request_id: str = "REQ-BLOB-SYNTH",
) -> RecordedResponse:
    """Synthesize a recorded base64 blob response for exact content bytes."""

    resolved_sha = sha or git_blob_id(content)
    body = json.dumps(
        {
            "sha": resolved_sha,
            "size": len(content),
            "url": (
                "https://api.github.com/repos/example/approved-repo"
                f"/git/blobs/{resolved_sha}"
            ),
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        },
        separators=(",", ":"),
    ).encode()
    return RecordedResponse(
        status=200,
        headers={
            "content-type": "application/json; charset=utf-8",
            "x-github-request-id": request_id,
        },
        body=body,
    )


class RecordedTransport:
    """Map (method, path) to recorded responses; reject anything unrecorded."""

    def __init__(self, routes: dict[tuple[str, str], RecordedResponse]) -> None:
        self._routes = dict(routes)
        self.requests: list[httpx.Request] = []
        self.calls: dict[tuple[str, str], int] = {}

    def call_count(self, method: str, path: str) -> int:
        return self.calls.get((method, path), 0)

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            query = request.url.query.decode()
            key = (request.method, request.url.path + (f"?{query}" if query else ""))
            self.calls[key] = self.calls.get(key, 0) + 1
            recorded = self._routes.get(key)
            if recorded is None:
                raise AssertionError(f"unrecorded request: {key[0]} {key[1]}")
            return httpx.Response(
                recorded.status,
                headers=recorded.headers,
                content=recorded.body,
                request=request,
            )

        return httpx.MockTransport(handler)
