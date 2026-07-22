"""Recorded-fixture MockTransport loader with per-request recording."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "github"


@dataclass(frozen=True)
class RecordedResponse:
    """One frozen recorded HTTP response loaded from a fixture file."""

    status: int
    headers: dict[str, str]
    body: bytes


def recorded_fixture(name: str) -> RecordedResponse:
    """Load one recorded response fixture without any network access."""

    parsed = json.loads((FIXTURES / f"{name}.json").read_bytes())
    body = parsed["body"]
    payload = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
    return RecordedResponse(
        status=parsed["status"],
        headers={str(key): str(value) for key, value in parsed["headers"].items()},
        body=payload,
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
