"""Recorded-transport evidence for the closed read-only GitHub adapter."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from recorded_transport import RecordedResponse, RecordedTransport, recorded_fixture

from skillscout.adapters.github import (
    GITHUB_API_VERSION,
    MAX_METADATA_BYTES,
    MAX_RETRY_AFTER_SECONDS,
    GitHubReadClient,
    LicenseResponse,
    RedirectFacts,
    RepoMetadata,
    TreeSnapshot,
)
from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.enums import EffectScope

PINNED = "0123456789abcdef0123456789abcdef01234567"
PINNED_SHA256 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
README_BLOB = "aa01aa01aa01aa01aa01aa01aa01aa01aa01aa01"
README_TEXT = (
    b"# Approved Repo\n\nA small reusable workflow repository used by SkillScout "
    b"recorded tests.\n\n## Workflow\n\n1. Read the guide.\n2. Run the example.\n\n"
    b"CANARY_FULL_TEXT_SENTENCE_DO_NOT_PERSIST_9f3b\n"
    b"CANARY_EVIDENCE_SENTENCE_VERBATIM_7a21\n"
)
CANARY = "github_pat_CANARY_DO_NOT_DISCLOSE_0123456789"

META = ("GET", "/repos/example/approved-repo")
PIN = ("GET", "/repos/example/approved-repo/commits/main")
TREE = ("GET", f"/repos/example/approved-repo/git/trees/{PINNED}?recursive=1")
LICENSE = ("GET", f"/repos/example/approved-repo/license?ref={PINNED}")
BLOB = ("GET", f"/repos/example/approved-repo/git/blobs/{README_BLOB}")


@pytest.fixture(autouse=True)
def _clear_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLSCOUT_GITHUB_TOKEN", raising=False)


def _routes(**overrides: RecordedResponse) -> dict[tuple[str, str], RecordedResponse]:
    routes = {
        META: recorded_fixture("repo_mit"),
        PIN: recorded_fixture("commits_pin"),
        TREE: recorded_fixture("tree_full"),
        LICENSE: recorded_fixture("license_mit"),
        BLOB: recorded_fixture("blob_readme"),
    }
    routes.update(overrides)
    return routes


def _client(
    recorded: RecordedTransport,
    *,
    token: str | None = None,
    sleeps: list[float] | None = None,
) -> GitHubReadClient:
    return GitHubReadClient(
        token=token,
        transport=recorded.transport(),
        sleeper=(sleeps.append if sleeps is not None else (lambda _seconds: None)),
    )


def test_metadata_maps_to_frozen_facts_with_rate_limit() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded) as client:
        metadata = client.get_repo_metadata("example", "approved-repo")
        assert isinstance(metadata, RepoMetadata)
        assert client.last_request_id == "REQ-META-0001"

    assert metadata.id == 840001
    assert metadata.owner == "example"
    assert metadata.name == "approved-repo"
    assert metadata.default_branch == "main"
    assert metadata.private is False
    assert metadata.fork is False
    assert metadata.archived is False
    assert metadata.disabled is False
    assert metadata.visibility == "public"
    assert metadata.license_spdx == "MIT"
    assert metadata.rate_limit.limit == 5000
    assert metadata.rate_limit.remaining == 4999
    assert metadata.rate_limit.reset == 1800000000
    request = recorded.requests[0]
    assert request.method == "GET"
    assert request.url.path == "/repos/example/approved-repo"
    assert request.headers["accept"] == "application/vnd.github+json"
    assert request.headers["x-github-api-version"] == GITHUB_API_VERSION
    assert request.headers["user-agent"] == "skillscout/0.1.0"
    assert "authorization" not in request.headers


def test_effect_scope_is_remote_read() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded) as client:
        assert client.effect_scope is EffectScope.REMOTE_READ


def test_resolve_commit_returns_the_pinned_sha() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded) as client:
        assert client.resolve_commit("example", "approved-repo", "main") == PINNED
        assert recorded.call_count(*PIN) == 1


def test_sha256_pin_is_returned_for_scout_level_rejection() -> None:
    routes = _routes()
    routes[PIN] = recorded_fixture("commits_pin_sha256")
    recorded = RecordedTransport(routes)
    with _client(recorded) as client:
        assert client.resolve_commit("example", "approved-repo", "main") == PINNED_SHA256


def test_every_content_url_embeds_the_pinned_sha_after_resolution() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded) as client:
        client.get_repo_metadata("example", "approved-repo")
        sha = client.resolve_commit("example", "approved-repo", "main")
        client.get_tree("example", "approved-repo", sha)
        client.get_license("example", "approved-repo", sha)
        client.get_blob("example", "approved-repo", README_BLOB, expected_size=228)

    urls = [str(request.url) for request in recorded.requests]
    assert urls[1].endswith("/commits/main")
    assert PINNED in urls[2]
    assert PINNED in urls[3]
    assert README_BLOB in urls[4]
    for url in urls[2:]:
        assert "main" not in url
    assert recorded.call_count(*TREE) == 1
    assert recorded.call_count(*LICENSE) == 1
    assert recorded.call_count(*BLOB) == 1


def test_recorded_urls_stay_inside_the_closed_endpoint_set() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded) as client:
        client.get_repo_metadata("example", "approved-repo")
        sha = client.resolve_commit("example", "approved-repo", "main")
        client.get_tree("example", "approved-repo", sha)
        client.get_license("example", "approved-repo", sha)
        client.get_blob("example", "approved-repo", README_BLOB, expected_size=228)

    allowed = (
        f"https://api.github.com{META[1]}",
        f"https://api.github.com{PIN[1]}",
        f"https://api.github.com{TREE[1]}",
        f"https://api.github.com{LICENSE[1]}",
        f"https://api.github.com{BLOB[1]}",
    )
    assert [str(request.url) for request in recorded.requests] == list(allowed)


def test_tree_snapshot_parses_modes_sizes_and_truncation() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded) as client:
        snapshot = client.get_tree("example", "approved-repo", PINNED)

    assert isinstance(snapshot, TreeSnapshot)
    assert snapshot.truncated is False
    entries = {entry.path: entry for entry in snapshot.entries}
    assert len(entries) == 12
    submodule = entries["docs/external"]
    assert submodule.mode == "160000"
    assert submodule.type == "commit"
    assert submodule.size is None
    symlink = entries["docs/link.md"]
    assert symlink.mode == "120000"
    assert symlink.size == 31
    assert entries["docs/big.md"].size == 200000
    assert entries["README.md"].sha == README_BLOB

    truncated_routes = _routes()
    truncated_routes[TREE] = recorded_fixture("tree_truncated")
    with _client(RecordedTransport(truncated_routes)) as client:
        assert client.get_tree("example", "approved-repo", PINNED).truncated is True


def test_license_confirmed_noassertion_and_not_found() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded) as client:
        confirmed = client.get_license("example", "approved-repo", PINNED)
    assert isinstance(confirmed, LicenseResponse)
    assert confirmed.status == "confirmed"
    assert confirmed.spdx_id == "MIT"
    assert confirmed.license_blob_sha == "bb12bb12bb12bb12bb12bb12bb12bb12bb12bb12"

    for name, expected in (
        ("license_noassertion", "noassertion"),
        ("license_404", "not_found"),
    ):
        routes = _routes()
        routes[LICENSE] = recorded_fixture(name)
        with _client(RecordedTransport(routes)) as client:
            outcome = client.get_license("example", "approved-repo", PINNED)
        assert outcome.status == expected
        assert outcome.spdx_id is None
        assert outcome.license_blob_sha is None


def test_license_endpoint_spdx_is_reported_verbatim_for_filter_comparison() -> None:
    routes = _routes()
    routes[LICENSE] = recorded_fixture("license_mismatch")
    with _client(RecordedTransport(routes)) as client:
        outcome = client.get_license("example", "approved-repo", PINNED)
    assert outcome.status == "confirmed"
    assert outcome.spdx_id == "Apache-2.0"


def test_blob_round_trip_and_tree_declared_size_recheck() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded) as client:
        content = client.get_blob("example", "approved-repo", README_BLOB, expected_size=228)
    assert content == README_TEXT

    with _client(RecordedTransport(_routes())) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_blob("example", "approved-repo", README_BLOB, expected_size=141)
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_blob_accepts_github_sixty_char_wrapped_base64() -> None:
    routes = _routes()
    routes[BLOB] = recorded_fixture("blob_readme_wrapped")
    recorded = RecordedTransport(routes)
    with _client(recorded) as client:
        content = client.get_blob("example", "approved-repo", README_BLOB, expected_size=228)
    assert content == README_TEXT


def test_blob_rejects_wrong_encoding_declared_size_and_bad_base64() -> None:
    base = recorded_fixture("blob_readme")
    parsed = json.loads(base.body)
    variants = []
    wrong_size = dict(parsed)
    wrong_size["size"] = 999
    variants.append(wrong_size)
    wrong_encoding = dict(parsed)
    wrong_encoding["encoding"] = "utf-8"
    variants.append(wrong_encoding)
    bad_base64 = dict(parsed)
    bad_base64["content"] = "!!!not-base64!!!"
    variants.append(bad_base64)
    wrapped_bad_base64 = dict(parsed)
    wrapped_bad_base64["content"] = "!!!not-base64!!!\n" + parsed["content"][:60]
    variants.append(wrapped_bad_base64)

    for variant in variants:
        body = json.dumps(variant).encode()
        routes = _routes()
        routes[BLOB] = RecordedResponse(status=200, headers=base.headers, body=body)
        with _client(RecordedTransport(routes)) as client:
            with pytest.raises(SafeFailure) as failure:
                client.get_blob("example", "approved-repo", README_BLOB, expected_size=228)
        assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_rate_limit_429_is_transient_with_bounded_retry_after() -> None:
    sleeps: list[float] = []
    routes = _routes()
    routes[META] = recorded_fixture("rate_limit_429")
    with _client(RecordedTransport(routes), sleeps=sleeps) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_repo_metadata("example", "approved-repo")
    assert failure.value.code is ErrorCode.STAGE_TRANSIENT_FAILURE
    assert sleeps == [1.0]


def test_retry_after_is_capped_at_sixty_seconds() -> None:
    sleeps: list[float] = []
    limited = recorded_fixture("rate_limit_429")
    routes = _routes()
    routes[META] = replace(limited, headers={**limited.headers, "retry-after": "3600"})
    with _client(RecordedTransport(routes), sleeps=sleeps) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_repo_metadata("example", "approved-repo")
    assert failure.value.code is ErrorCode.STAGE_TRANSIENT_FAILURE
    assert sleeps == [float(MAX_RETRY_AFTER_SECONDS)]


def test_limited_403_is_transient() -> None:
    sleeps: list[float] = []
    body = b'{"message":"API rate limit exceeded"}'
    routes = _routes()
    routes[META] = RecordedResponse(
        status=403,
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1800003600"},
        body=body,
    )
    with _client(RecordedTransport(routes), sleeps=sleeps) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_repo_metadata("example", "approved-repo")
    assert failure.value.code is ErrorCode.STAGE_TRANSIENT_FAILURE
    assert len(sleeps) == 1


def test_unlimited_403_is_permanent() -> None:
    routes = _routes()
    routes[META] = RecordedResponse(
        status=403,
        headers={"x-ratelimit-remaining": "120"},
        body=b'{"message":"Forbidden"}',
    )
    with _client(RecordedTransport(routes)) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_repo_metadata("example", "approved-repo")
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_server_errors_are_transient_with_bounded_sleep() -> None:
    for status in (500, 503):
        sleeps: list[float] = []
        routes = _routes()
        routes[META] = RecordedResponse(status=status, headers={}, body=b'{"message":"boom"}')
        with _client(RecordedTransport(routes), sleeps=sleeps) as client:
            with pytest.raises(SafeFailure) as failure:
                client.get_repo_metadata("example", "approved-repo")
        assert failure.value.code is ErrorCode.STAGE_TRANSIENT_FAILURE
        assert sleeps == [0.0]


def test_timeouts_and_network_errors_are_transient_without_httpx_leakage() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("recorded timeout", request=request)

    def network_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("recorded network error", request=request)

    for handler in (timeout_handler, network_handler):
        with GitHubReadClient(
            transport=httpx.MockTransport(handler), sleeper=lambda _seconds: None
        ) as client:
            with pytest.raises(SafeFailure) as failure:
                client.get_repo_metadata("example", "approved-repo")
        assert failure.value.code is ErrorCode.STAGE_TRANSIENT_FAILURE


def test_metadata_and_pin_404_are_permanent() -> None:
    not_found = RecordedResponse(status=404, headers={}, body=b'{"message":"Not Found"}')
    routes = _routes()
    routes[META] = not_found
    with _client(RecordedTransport(routes)) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_repo_metadata("example", "approved-repo")
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE

    routes = _routes()
    routes[PIN] = not_found
    with _client(RecordedTransport(routes)) as client:
        with pytest.raises(SafeFailure) as failure:
            client.resolve_commit("example", "approved-repo", "main")
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_same_host_redirect_is_followed_once_and_recorded() -> None:
    routes = _routes()
    routes[META] = recorded_fixture("redirect_301")
    routes[("GET", "/repos/example/renamed-repo")] = recorded_fixture("repo_mit")
    recorded = RecordedTransport(routes)
    with _client(recorded) as client:
        metadata = client.get_repo_metadata("example", "approved-repo")

    assert metadata.id == 840001
    assert client.redirects == (
        RedirectFacts(
            from_url="https://api.github.com/repos/example/approved-repo",
            to_url="https://api.github.com/repos/example/renamed-repo",
        ),
    )
    assert recorded.call_count("GET", "/repos/example/renamed-repo") == 1


def test_cross_host_redirect_is_permanent() -> None:
    redirect = recorded_fixture("redirect_301")
    routes = _routes()
    routes[META] = replace(
        redirect,
        headers={**redirect.headers, "location": "https://evil.example.com/collect"},
    )
    with _client(RecordedTransport(routes)) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_repo_metadata("example", "approved-repo")
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_second_redirect_is_permanent() -> None:
    redirect = recorded_fixture("redirect_301")
    routes = _routes()
    routes[META] = redirect
    routes[("GET", "/repos/example/renamed-repo")] = replace(
        redirect,
        headers={**redirect.headers, "location": "https://api.github.com/repos/example/third"},
    )
    with _client(RecordedTransport(routes)) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_repo_metadata("example", "approved-repo")
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_over_cap_response_is_permanent() -> None:
    routes = _routes()
    routes[META] = RecordedResponse(
        status=200,
        headers={"content-type": "application/json"},
        body=b" " * (MAX_METADATA_BYTES + 1),
    )
    with _client(RecordedTransport(routes)) as client:
        with pytest.raises(SafeFailure) as failure:
            client.get_repo_metadata("example", "approved-repo")
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_malformed_and_schema_invalid_bodies_are_permanent() -> None:
    for body in (b"{not json", b'{"name":"approved-repo"}'):
        routes = _routes()
        routes[META] = RecordedResponse(
            status=200, headers={"content-type": "application/json"}, body=body
        )
        with _client(RecordedTransport(routes)) as client:
            with pytest.raises(SafeFailure) as failure:
                client.get_repo_metadata("example", "approved-repo")
        assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_canary_token_stays_in_the_authorization_header_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = RecordedTransport(_routes())
    monkeypatch.setenv("SKILLSCOUT_GITHUB_TOKEN", CANARY)
    with GitHubReadClient(
        transport=recorded.transport(), sleeper=lambda _seconds: None
    ) as client:
        monkeypatch.setenv("SKILLSCOUT_GITHUB_TOKEN", "github_pat_ROTATED_AFTER_CONSTRUCTION")
        client.get_repo_metadata("example", "approved-repo")
        sha = client.resolve_commit("example", "approved-repo", "main")
        client.get_tree("example", "approved-repo", sha)
        client.get_license("example", "approved-repo", sha)
        client.get_blob("example", "approved-repo", README_BLOB, expected_size=228)

    for request in recorded.requests:
        assert request.headers["authorization"] == f"Bearer {CANARY}"
        assert CANARY not in str(request.url)
        assert CANARY.encode() not in request.read()

    fixtures_dir = Path(__file__).parent / "fixtures" / "github"
    for fixture_file in fixtures_dir.glob("*.json"):
        assert CANARY.encode() not in fixture_file.read_bytes()


def test_explicit_token_constructs_without_environment_read() -> None:
    recorded = RecordedTransport(_routes())
    with _client(recorded, token=CANARY) as client:
        client.get_repo_metadata("example", "approved-repo")
    assert recorded.requests[0].headers["authorization"] == f"Bearer {CANARY}"
