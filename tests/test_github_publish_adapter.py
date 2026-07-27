"""Wave-0 exact transport contract for the future closed GitHub publisher.

The adapter is intentionally absent in Wave 0.  Import it only inside test
bodies: collection stays useful, while execution is red until Plan 04-04.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from recorded_transport import RecordedResponse, RecordedTransport


FIXTURES = Path(__file__).parent / "fixtures" / "github_publish"
REPOSITORY = "/repos/catalog-org/skills"
HEAD = "skillscout/bounded-workflow"
BASE = "main"
COMMIT = "1111111111111111111111111111111111111111"
TREE = "2222222222222222222222222222222222222222"


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _response(name: str) -> RecordedResponse:
    return RecordedResponse(
        status=200,
        headers={"content-type": "application/json", "x-github-request-id": "REQ-PUBLISH-1"},
        body=json.dumps(_fixture(name), separators=(",", ":")).encode(),
    )


def github_publish_routes() -> dict[tuple[str, str], RecordedResponse]:
    """All normal publisher routes, deliberately closed and serial."""
    return {
        ("GET", REPOSITORY): _response("repository"),
        ("GET", f"{REPOSITORY}/git/ref/heads/{HEAD}"): _response("ref"),
        ("GET", f"{REPOSITORY}/git/commits/{COMMIT}"): _response("commit"),
        ("GET", f"{REPOSITORY}/git/trees/{TREE}?recursive=1"): _response("tree"),
        ("POST", f"{REPOSITORY}/git/blobs"): _response("blob"),
        ("POST", f"{REPOSITORY}/git/trees"): _response("tree"),
        ("POST", f"{REPOSITORY}/git/commits"): _response("commit"),
        ("POST", f"{REPOSITORY}/git/refs"): _response("ref"),
        ("PATCH", f"{REPOSITORY}/git/refs/heads/{HEAD}"): _response("ref"),
        ("GET", f"{REPOSITORY}/pulls?state=open&head=catalog-org%3A{HEAD}&base={BASE}&per_page=100&page=1"): _response("pulls_page"),
        ("POST", f"{REPOSITORY}/pulls"): _response("pull_draft"),
        ("PATCH", f"{REPOSITORY}/pulls/42"): _response("pull_draft"),
        ("GET", f"{REPOSITORY}/pulls/42/requested_reviewers?per_page=100&page=1"): _response("reviewers"),
        ("GET", f"{REPOSITORY}/pulls/42/reviews?per_page=100&page=1"): _response("reviewers"),
        ("POST", f"{REPOSITORY}/pulls/42/requested_reviewers"): _response("reviewers"),
    }


def _adapter(recorded: RecordedTransport) -> Any:
    from skillscout.adapters.github_publish import GitHubPublishClient

    return GitHubPublishClient(
        token="fixture-token-only",
        catalog_repository_id=910001,
        catalog_full_name="catalog-org/skills",
        transport=recorded.transport(),
    )


def test_fixture_corpus_is_bounded_and_contains_the_complete_provider_matrix() -> None:
    assert {path.name for path in FIXTURES.glob("*.json")} == {
        "repository.json", "ref.json", "commit.json", "blob.json", "tree.json",
        "pull_draft.json", "pulls_page.json", "reviewers.json", "error_matrix.json",
    }
    errors = _fixture("error_matrix")
    assert set(errors) == {
        "redirect", "unauthorized", "forbidden", "missing", "conflict", "unprocessable",
        "rate_limited", "server_error", "oversized", "malformed", "wrong_content_type",
        "missing_request_id", "pagination", "unknown_field", "truncated_tree",
    }
    assert all("token" not in path.read_text(encoding="utf-8").casefold() for path in FIXTURES.glob("*.json"))


def test_unrecorded_requests_raise_and_routes_are_exact() -> None:
    recorded = RecordedTransport({})
    with pytest.raises(AssertionError, match="unrecorded request: GET /repos/catalog-org/skills"):
        recorded.transport().handle_request  # type: ignore[attr-defined]
        import httpx
        httpx.Client(transport=recorded.transport()).get("https://api.github.com" + REPOSITORY)


def test_closed_adapter_has_only_named_publish_operations() -> None:
    client = _adapter(RecordedTransport(github_publish_routes()))
    public = {name for name in dir(client) if not name.startswith("_")}
    forbidden = {"request", "graphql", "merge", "submit_review", "approve", "ready_for_review", "timeline"}
    assert public.isdisjoint(forbidden)
    assert {"get_repository", "get_ref", "get_commit", "get_tree", "create_blob", "create_tree", "create_commit", "create_ref", "update_ref", "list_pulls", "create_pull", "update_pull", "get_requested_reviewers", "list_reviews", "request_reviewers"} <= public


def test_named_operations_use_exact_paths_bodies_and_serial_calls() -> None:
    recorded = RecordedTransport(github_publish_routes())
    with _adapter(recorded) as client:
        client.get_repository()
        client.get_ref(HEAD)
        client.get_commit(COMMIT)
        client.get_tree(TREE, recursive=True)
        client.create_blob(content=b"fixture")
        client.create_tree(base_tree=TREE, entries=[])
        client.create_commit(message="fixture\n\nSkillScout-Publication: v1", tree=TREE, parents=[COMMIT])
        client.create_ref(ref=f"refs/heads/{HEAD}", sha=COMMIT)
        client.update_ref(ref=f"heads/{HEAD}", sha=COMMIT, force=False)
        client.list_pulls(head=HEAD, base=BASE)
        client.create_pull(title="Draft: fixture", body="body", head=HEAD, base=BASE, draft=True, maintainer_can_modify=False)
        client.update_pull(number=42, title="Draft: fixture", body="body")
        client.get_requested_reviewers(number=42)
        client.list_reviews(number=42)
        client.request_reviewers(number=42, reviewers=["skill-maintainer"])
    assert [request.url.path for request in recorded.requests][:4] == [REPOSITORY, f"{REPOSITORY}/git/ref/heads/{HEAD}", f"{REPOSITORY}/git/commits/{COMMIT}", f"{REPOSITORY}/git/trees/{TREE}"]
    bodies = [json.loads(request.content) for request in recorded.requests if request.method in {"POST", "PATCH"}]
    assert {"draft": True, "maintainer_can_modify": False}.items() <= bodies[5].items()
    assert bodies[4]["force"] is False
    assert bodies[-1] == {"reviewers": ["skill-maintainer"]}
    assert len(recorded.requests) == len(github_publish_routes())


def test_tree_enumerates_only_owned_catalog_subtree_and_rejects_truncation() -> None:
    recorded = RecordedTransport(github_publish_routes())
    with _adapter(recorded) as client:
        entries = client.get_tree(TREE, recursive=True)
    assert {entry.path for entry in entries} == {"skills/bounded-workflow/SKILL.md", "skills/bounded-workflow/references/provenance.json"}
    assert all(entry.path.startswith("skills/bounded-workflow/") for entry in entries)
    routes = github_publish_routes()
    bad = _fixture("tree")
    bad["truncated"] = True
    routes[("GET", f"{REPOSITORY}/git/trees/{TREE}?recursive=1")] = RecordedResponse(200, {"content-type": "application/json", "x-github-request-id": "REQ"}, json.dumps(bad).encode())
    with _adapter(RecordedTransport(routes)) as client:
        with pytest.raises(Exception):
            client.get_tree(TREE, recursive=True)


def test_only_exact_machine_ref_404_has_a_closed_not_found_result() -> None:
    from skillscout.adapters.github_publish import RefNotFound
    from skillscout.application.ports import SafeFailure

    path = f"{REPOSITORY}/git/ref/heads/{HEAD}"
    for status, expected in ((404, RefNotFound), (403, SafeFailure), (500, SafeFailure)):
        routes = github_publish_routes()
        routes[("GET", path)] = RecordedResponse(
            status,
            {"content-type": "application/json", "x-github-request-id": "REQ-REF"},
            b'{"message":"provider text must stay closed"}',
        )
        recorded = RecordedTransport(routes)
        with _adapter(recorded) as client, pytest.raises(expected):
            client.get_ref()
        assert [request.method for request in recorded.requests] == ["GET"]


def test_review_observations_are_bounded_users_only_and_team_state_is_ambiguous() -> None:
    with _adapter(RecordedTransport(github_publish_routes())) as client:
        requested = client.get_requested_reviewers(number=42)
        reviews = client.list_reviews(number=42)
    assert requested.users == ("skill-maintainer",)
    assert reviews == (("completed-maintainer", 7001, COMMIT, "APPROVED"),)
    routes = github_publish_routes()
    team = _fixture("reviewers")
    team["teams"] = [{"slug": "maintainers"}]
    routes[("GET", f"{REPOSITORY}/pulls/42/requested_reviewers?per_page=100&page=1")] = RecordedResponse(200, {"content-type": "application/json", "x-github-request-id": "REQ"}, json.dumps(team).encode())
    with _adapter(RecordedTransport(routes)) as client:
        with pytest.raises(Exception):
            client.get_requested_reviewers(number=42)


def test_paginated_pulls_and_reviews_follow_only_canonical_same_origin_links() -> None:
    pull = _fixture("pull_draft")
    pulls_page_one = [
        {
            **pull,
            "number": number,
            "html_url": f"https://github.com/catalog-org/skills/pull/{number}",
        }
        for number in range(1, 101)
    ]
    pulls_page_two = [
        {
            **pull,
            "number": 101,
            "html_url": "https://github.com/catalog-org/skills/pull/101",
        }
    ]
    review = _fixture("reviewers")["reviews"][0]
    reviews_page_one = [{**review, "id": number} for number in range(1, 101)]
    reviews_page_two = [{**review, "id": 101}]
    pull_prefix = (
        f"{REPOSITORY}/pulls?state=open&head=catalog-org%3A{HEAD}"
        f"&base={BASE}&per_page=100&page="
    )
    review_prefix = f"{REPOSITORY}/pulls/42/reviews?per_page=100&page="
    routes = github_publish_routes()
    routes[("GET", pull_prefix + "1")] = RecordedResponse(
        200,
        {
            "content-type": "application/json",
            "x-github-request-id": "REQ-PULLS-1",
            "link": (
                "<https://api.github.com"
                + pull_prefix
                + '2>; rel="next"'
            ),
        },
        json.dumps(pulls_page_one).encode(),
    )
    routes[("GET", pull_prefix + "2")] = RecordedResponse(
        200,
        {"content-type": "application/json", "x-github-request-id": "REQ-PULLS-2"},
        json.dumps(pulls_page_two).encode(),
    )
    routes[("GET", review_prefix + "1")] = RecordedResponse(
        200,
        {
            "content-type": "application/json",
            "x-github-request-id": "REQ-REVIEWS-1",
            "link": (
                "<https://api.github.com"
                + review_prefix
                + '2>; rel="next"'
            ),
        },
        json.dumps(reviews_page_one).encode(),
    )
    routes[("GET", review_prefix + "2")] = RecordedResponse(
        200,
        {"content-type": "application/json", "x-github-request-id": "REQ-REVIEWS-2"},
        json.dumps(reviews_page_two).encode(),
    )
    with _adapter(RecordedTransport(routes)) as client:
        assert len(client.list_open_pulls()) == 101
        assert len(client.list_reviews(42)) == 101

    hostile = dict(routes)
    hostile[("GET", pull_prefix + "1")] = RecordedResponse(
        200,
        {
            "content-type": "application/json",
            "x-github-request-id": "REQ-PULLS-1",
            "link": '<https://attacker.example/pulls?page=2>; rel="next"',
        },
        json.dumps(pulls_page_one).encode(),
    )
    with _adapter(RecordedTransport(hostile)) as client, pytest.raises(Exception):
        client.list_open_pulls()


@pytest.mark.parametrize("field", tuple(_fixture("error_matrix")), ids=lambda value: value)
def test_provider_error_matrix_is_closed_and_safe(field: str) -> None:
    from skillscout.application.ports import ErrorCode, SafeFailure

    matrix = _fixture("error_matrix")
    assert field in matrix
    if field == "pagination":
        pull = _fixture("pull_draft")
        prefix = (
            f"{REPOSITORY}/pulls?state=open&head=catalog-org%3A{HEAD}"
            f"&base={BASE}&per_page=100&page="
        )
        routes = github_publish_routes()
        routes[("GET", prefix + "1")] = RecordedResponse(
            200,
            {
                "content-type": "application/json",
                "x-github-request-id": "REQ-MATRIX-1",
                "link": (
                    "<https://api.github.com" + prefix + '2>; rel="next"'
                ),
            },
                json.dumps(
                    [
                        {
                            **pull,
                            "number": number,
                            "html_url": (
                                "https://github.com/catalog-org/skills/pull/"
                                f"{number}"
                            ),
                        }
                        for number in range(1, 101)
                    ]
                ).encode(),
        )
        routes[("GET", prefix + "2")] = RecordedResponse(
            200,
            {
                "content-type": "application/json",
                "x-github-request-id": "REQ-MATRIX-2",
            },
                json.dumps(
                    [
                        {
                            **pull,
                            "number": 101,
                            "html_url": (
                                "https://github.com/catalog-org/skills/pull/101"
                            ),
                        }
                    ]
                ).encode(),
        )
        recorded = RecordedTransport(routes)
        with _adapter(recorded) as client:
            assert len(client.list_open_pulls()) == 101
        assert len(recorded.requests) == 2
        return

    operation = "catalog"
    status = matrix[field] if isinstance(matrix[field], int) else 200
    headers = {
        "content-type": "application/json",
        "x-github-request-id": "REQ-MATRIX",
    }
    body = json.dumps(_fixture("repository")).encode()
    if field == "oversized":
        body = b"{" + b" " * 1_048_576 + b"}"
    elif field == "malformed":
        body = b"{"
    elif field == "wrong_content_type":
        headers["content-type"] = "text/html"
    elif field == "missing_request_id":
        headers.pop("x-github-request-id")
    elif field == "unknown_field":
        body = json.dumps({**_fixture("repository"), "provider_extra": "ignored"}).encode()
    elif field == "truncated_tree":
        operation = "tree"
        tree = {**_fixture("tree"), "truncated": True}
        body = json.dumps(tree).encode()
    elif status >= 300:
        body = b'{"message":"provider-secret-canary"}'

    recorded_response = RecordedResponse(status, headers, body)

    class TrackingStream(httpx.SyncByteStream):
        def __init__(self, payload: bytes) -> None:
            self.payload = payload
            self.closed = False

        def __iter__(self) -> Any:
            yield self.payload

        def close(self) -> None:
            self.closed = True

    stream = TrackingStream(recorded_response.body)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            recorded_response.status,
            headers=recorded_response.headers,
            stream=stream,
            request=request,
        )

    from skillscout.adapters.github_publish import GitHubPublishClient

    client = GitHubPublishClient(
        token="fixture-token-only",
        catalog_repository_id=910001,
        catalog_full_name="catalog-org/skills",
        transport=httpx.MockTransport(handler),
    )
    should_succeed = field == "unknown_field"
    if should_succeed:
        assert client.get_catalog().repository_id == 910001
    else:
        with pytest.raises(SafeFailure) as captured:
            if operation == "tree":
                client.get_tree(TREE)
            else:
                client.get_catalog()
        expected_code = (
            ErrorCode.STAGE_TRANSIENT_FAILURE
            if field in {"rate_limited", "server_error"}
            else ErrorCode.STAGE_PERMANENT_FAILURE
        )
        assert captured.value.code is expected_code
        assert "provider-secret-canary" not in str(captured.value)
    client.close()
    assert len(requests) == 1
    assert stream.closed is True
