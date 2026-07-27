"""Wave-0 contract for bounded GitHub repository Search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from recorded_transport import RecordedTransport, recorded_search_fixture

from skillscout.adapters.github import GITHUB_API_VERSION, GitHubReadClient
from skillscout.domain.discovery import (
    DiscoveryQuerySetV1,
    SearchPageObservationV1,
    SearchRepositoryObservationV1,
)


ROOT = Path(__file__).resolve().parents[1]
QUERY_POLICY_PATH = ROOT / "config" / "discovery-queries-v1.json"
SEARCH_FIXTURES = Path(__file__).parent / "fixtures" / "github_search"
RUN_AUTHORITY_DIGEST = "sha256:" + ("d" * 64)
TOKEN_CANARY = "github_pat_SEARCH_CANARY_DO_NOT_DISCLOSE"
DISCARDED_CANARIES = (
    "SEARCH_DESCRIPTION_INJECTION_CANARY",
    "SEARCH_TOPIC_INJECTION_CANARY",
    "SEARCH_TEXT_MATCH_INJECTION_CANARY",
    "WITHIN_PAGE_DUPLICATE_CANARY",
    "CROSS_QUERY_RENAME_CANARY",
    "DISCARDED_TOPIC_CANARY",
)
WAVE0_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-search-adapter-missing",
)


@pytest.fixture(autouse=True)
def _clear_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLSCOUT_GITHUB_TOKEN", raising=False)


def _query_set() -> DiscoveryQuerySetV1:
    return DiscoveryQuerySetV1.model_validate_json(
        QUERY_POLICY_PATH.read_bytes(),
        strict=True,
    )


def _search_path(query_ordinal: int, page: int) -> str:
    policy = _query_set()
    query = policy.queries[query_ordinal - 1]
    params = httpx.QueryParams(
        [
            ("q", query.query_text),
            ("sort", policy.sort),
            ("order", policy.order),
            ("per_page", str(policy.per_page)),
            ("page", str(page)),
        ]
    )
    return f"/search/repositories?{params}"


def _invoke_search(
    client: GitHubReadClient,
    *,
    query_ordinal: int,
    page: int,
) -> tuple[SearchPageObservationV1, tuple[SearchRepositoryObservationV1, ...]]:
    method = getattr(client, "search_repositories")
    result = method(
        query_set=_query_set(),
        discovery_run_authority_digest=RUN_AUTHORITY_DIGEST,
        query_ordinal=query_ordinal,
        page=page,
    )
    assert type(result) is tuple and len(result) == 2
    page_observation, repositories = result
    assert isinstance(page_observation, SearchPageObservationV1)
    assert type(repositories) is tuple
    assert all(
        isinstance(item, SearchRepositoryObservationV1) for item in repositories
    )
    return page_observation, repositories


def _fixture_body(name: str) -> dict[str, Any]:
    response = recorded_search_fixture(name)
    parsed = json.loads(response.body)
    assert isinstance(parsed, dict)
    return parsed


def test_page_fixture_loader_corpus_is_bounded_metadata_only() -> None:
    fixture_names = ("page_one", "page_duplicates", "page_incomplete")
    for name in fixture_names:
        path = SEARCH_FIXTURES / f"{name}.json"
        assert path.stat().st_size < 16_384
        response = recorded_search_fixture(name)
        assert response.status == 200
        assert len(response.body) < 16_384
        parsed = _fixture_body(name)
        assert set(parsed) == {"total_count", "incomplete_results", "items"}
        assert len(parsed["items"]) <= 25
        for item in parsed["items"]:
            assert "readme" not in item
            assert "source" not in item
            assert "authorization" not in item


def test_page_recorded_transport_requires_exact_query_and_rejects_unrecorded() -> None:
    path = _search_path(1, 1)
    recorded = RecordedTransport(
        {("GET", path): recorded_search_fixture("page_one")}
    )
    request = httpx.Request("GET", f"https://api.github.com{path}")
    response = recorded.transport().handle_request(request)
    assert response.status_code == 200
    assert recorded.call_count("GET", path) == 1

    wrong_page = httpx.Request(
        "GET",
        f"https://api.github.com{_search_path(1, 2)}",
    )
    with pytest.raises(AssertionError, match=r"^unrecorded request: GET "):
        recorded.transport().handle_request(wrong_page)


def test_duplicate_fixture_identity_is_numeric_repository_id_only() -> None:
    observations = [
        *_fixture_body("page_one")["items"],
        *_fixture_body("page_duplicates")["items"],
    ]
    first_seen: dict[int, tuple[str, str]] = {}
    dispositions: list[tuple[int, str]] = []
    for item in observations:
        repository_id = item["id"]
        disposition = "duplicate" if repository_id in first_seen else "first_seen"
        dispositions.append((repository_id, disposition))
        first_seen.setdefault(
            repository_id,
            (item["owner"]["login"], item["name"]),
        )

    assert dispositions == [
        (910001, "first_seen"),
        (910002, "first_seen"),
        (910001, "duplicate"),
        (910002, "duplicate"),
        (910003, "first_seen"),
    ]
    assert first_seen[910002] == ("fixture-org", "workflow-beta")


def test_incomplete_fixture_retains_query_mismatch_facts_for_later_filtering() -> None:
    body = _fixture_body("page_incomplete")
    assert body["incomplete_results"] is True
    assert [item["id"] for item in body["items"]] == [910004, 910005, 910006]
    assert body["items"][0]["private"] is True
    assert body["items"][1]["fork"] is True
    assert body["items"][2]["archived"] is True


@WAVE0_XFAIL
def test_page_one_projects_exact_request_page_rate_and_allowlisted_items() -> None:
    path = _search_path(1, 1)
    recorded = RecordedTransport(
        {("GET", path): recorded_search_fixture("page_one")}
    )
    with GitHubReadClient(
        token=TOKEN_CANARY,
        transport=recorded.transport(),
        sleeper=lambda _seconds: None,
    ) as client:
        page, repositories = _invoke_search(client, query_ordinal=1, page=1)

    assert page.query_ordinal == 1
    assert page.query_text == _query_set().queries[0].query_text
    assert page.page == 1
    assert page.per_page == 25
    assert page.next_page == 2
    assert page.total_count == 5
    assert page.item_count == 3
    assert page.incomplete_results is False
    assert page.request_id == "REQ-SEARCH-P1"
    assert page.rate_limit.model_dump(mode="json") == {
        "limit": 30,
        "remaining": 29,
        "used": 1,
        "reset_epoch": 1785160800,
        "resource": "search",
    }
    assert [item.repository_id for item in repositories] == [
        910001,
        910002,
        910001,
    ]
    request = recorded.requests[0]
    assert request.method == "GET"
    assert request.url.host == "api.github.com"
    assert request.url.path == "/search/repositories"
    assert request.url.query.decode() == path.partition("?")[2]
    assert request.headers["accept"] == "application/vnd.github+json"
    assert request.headers["x-github-api-version"] == GITHUB_API_VERSION
    assert request.headers["authorization"] == f"Bearer {TOKEN_CANARY}"
    assert TOKEN_CANARY not in str(request.url)
    assert TOKEN_CANARY.encode() not in request.read()

    projected = page.model_dump_json() + "".join(
        item.model_dump_json() for item in repositories
    )
    recorder_summary = repr((recorded.calls, recorded.requests))
    for canary in DISCARDED_CANARIES:
        assert canary not in projected
        assert canary not in recorder_summary


@WAVE0_XFAIL
def test_page_multiple_requests_are_serial_and_follow_integer_cursor_only() -> None:
    first = _search_path(1, 1)
    second = _search_path(1, 2)
    recorded = RecordedTransport(
        {
            ("GET", first): recorded_search_fixture("page_one"),
            ("GET", second): recorded_search_fixture("page_duplicates"),
        }
    )
    with GitHubReadClient(
        transport=recorded.transport(),
        sleeper=lambda _seconds: None,
    ) as client:
        page_one, _ = _invoke_search(client, query_ordinal=1, page=1)
        assert page_one.next_page == 2
        page_two, _ = _invoke_search(
            client,
            query_ordinal=1,
            page=page_one.next_page,
        )

    assert page_two.page == 2
    assert page_two.next_page is None
    assert [str(request.url) for request in recorded.requests] == [
        f"https://api.github.com{first}",
        f"https://api.github.com{second}",
    ]
    assert recorded.call_count("GET", first) == 1
    assert recorded.call_count("GET", second) == 1


@WAVE0_XFAIL
def test_duplicate_and_rename_projection_preserves_stable_numeric_identity() -> None:
    first = _search_path(1, 1)
    cross_query = _search_path(2, 1)
    recorded = RecordedTransport(
        {
            ("GET", first): recorded_search_fixture("page_one"),
            ("GET", cross_query): recorded_search_fixture("page_duplicates"),
        }
    )
    with GitHubReadClient(
        transport=recorded.transport(),
        sleeper=lambda _seconds: None,
    ) as client:
        _, first_items = _invoke_search(client, query_ordinal=1, page=1)
        _, duplicate_items = _invoke_search(client, query_ordinal=2, page=1)

    first_by_id: dict[int, SearchRepositoryObservationV1] = {}
    dispositions: list[tuple[int, str]] = []
    for item in (*first_items, *duplicate_items):
        disposition = (
            "duplicate" if item.repository_id in first_by_id else "first_seen"
        )
        dispositions.append((item.repository_id, disposition))
        first_by_id.setdefault(item.repository_id, item)
    assert dispositions == [
        (910001, "first_seen"),
        (910002, "first_seen"),
        (910001, "duplicate"),
        (910002, "duplicate"),
        (910003, "first_seen"),
    ]
    assert first_by_id[910002].full_name == "fixture-org/workflow-beta"
    assert duplicate_items[0].full_name == "new-owner/workflow-beta-renamed"


@WAVE0_XFAIL
def test_incomplete_page_is_truthful_and_does_not_treat_query_as_admission() -> None:
    path = _search_path(3, 1)
    recorded = RecordedTransport(
        {("GET", path): recorded_search_fixture("page_incomplete")}
    )
    with GitHubReadClient(
        transport=recorded.transport(),
        sleeper=lambda _seconds: None,
    ) as client:
        page, repositories = _invoke_search(client, query_ordinal=3, page=1)

    assert page.incomplete_results is True
    assert page.total_count == 9
    assert page.item_count == 3
    assert repositories[0].private is True
    assert repositories[0].visibility == "private"
    assert repositories[1].fork is True
    assert repositories[2].archived is True
