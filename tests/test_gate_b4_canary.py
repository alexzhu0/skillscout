"""Behavior contract for the test-only controlled Gate B4 hosted canary."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "gate_b4_canary.py"
TOKEN = "github_pat_NEVER_RENDER_GATE_B4"
DEFAULT_SHA = "a" * 40
DRAFT_COMMIT_SHA = "b" * 40
MERGE_COMMIT_SHA = "c" * 40


def _module() -> ModuleType:
    assert RUNNER.is_file(), "the dependency-locked test-only canary runner is missing"
    spec = importlib.util.spec_from_file_location("gate_b4_canary", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _env() -> dict[str, str]:
    return {
        "GITHUB_RUN_ID": "12345",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "d" * 40,
        "SKILLSCOUT_CANARY_CATALOG_REPOSITORY_ID": "910001",
        "SKILLSCOUT_CANARY_CATALOG_FULL_NAME": "catalog-org/skills",
        "SKILLSCOUT_CANARY_CATALOG_OWNER": "catalog-org",
        "SKILLSCOUT_CANARY_CATALOG_REPOSITORY": "skills",
        "SKILLSCOUT_CANARY_EXPECTED_INSTALLATION_ID": "4001",
        "SKILLSCOUT_CANARY_ACTUAL_INSTALLATION_ID": "4001",
        "SKILLSCOUT_CANARY_REVIEWER": "skill-maintainer",
        "SKILLSCOUT_CANARY_UNAUTHORIZED_PRIVATE_REPOSITORY": "other-org/private",
        "SKILLSCOUT_CANARY_APP_TOKEN": TOKEN,
    }


def _transport(
    requests: list[tuple[str, str, object | None]],
    *,
    fail_at: tuple[str, str] | None = None,
    transport_error_at: tuple[str, str] | None = None,
    mergeable: tuple[bool | None, ...] = (True,),
    status_overrides: dict[tuple[str, str], int] | None = None,
    reviewer_users: tuple[str, ...] = ("skill-maintainer",),
    reviewer_teams: tuple[str, ...] = (),
) -> httpx.MockTransport:
    draft_branch = "skillscout/gate-b4-12345-1-draft"
    merge_branch = "skillscout/gate-b4-12345-1-merge-probe"
    statuses = {
        ("PATCH", "/repos/catalog-org/skills/git/refs/heads/main"): 403,
        ("PUT", "/repos/catalog-org/skills/pulls/79/merge"): 405,
        ("GET", "/repos/catalog-org/skills/rulesets"): 200,
        ("POST", "/repos/catalog-org/skills/rulesets"): 403,
        ("GET", "/repos/other-org/private"): 404,
        ("GET", "/repos/catalog-org/skills/actions/secrets"): 403,
    }
    statuses.update(status_overrides or {})
    merge_poll_index = 0
    default_sha = DEFAULT_SHA
    merge_succeeded = False

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal default_sha, merge_poll_index, merge_succeeded
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        key = (request.method, request.url.path)
        if transport_error_at == key:
            raise httpx.ConnectError("MUST_NOT_APPEAR", request=request)
        if fail_at == (request.method, request.url.path):
            return httpx.Response(500, json={"message": "MUST_NOT_APPEAR"})
        routes: dict[tuple[str, str], object] = {
            ("GET", "/installation/repositories"): {
                "total_count": 1,
                "repositories": [{"id": 910001, "full_name": "catalog-org/skills"}],
            },
            ("GET", "/repos/catalog-org/skills"): {
                "id": 910001,
                "full_name": "catalog-org/skills",
                "default_branch": "main",
            },
            ("GET", "/repos/catalog-org/skills/git/ref/heads/main"): {
                "ref": "refs/heads/main",
                "object": {"sha": default_sha},
            },
            ("POST", "/repos/catalog-org/skills/git/refs"): {
                "ref": f"refs/heads/{draft_branch}",
                "object": {"sha": DEFAULT_SHA},
            },
            (
                "PUT",
                "/repos/catalog-org/skills/contents/.skillscout-gate-b4/gate-b4-12345-1-draft.md",
            ): {
                "content": {"sha": "1" * 40},
                "commit": {"sha": DRAFT_COMMIT_SHA},
            },
            ("POST", "/repos/catalog-org/skills/pulls"): {
                "number": 78,
                "draft": True,
                "head": {"ref": draft_branch},
                "base": {"ref": "main"},
            },
            (
                "POST",
                "/repos/catalog-org/skills/pulls/78/requested_reviewers",
            ): {"users": [{"login": "skill-maintainer"}]},
            ("GET", "/repos/catalog-org/skills/pulls/78"): {
                "number": 78,
                "draft": True,
                "head": {"ref": draft_branch},
                "base": {"ref": "main"},
                "state": "open",
                "merged": False,
                "merged_at": None,
            },
            (
                "GET",
                "/repos/catalog-org/skills/pulls/78/requested_reviewers",
            ): {
                "users": [{"login": login} for login in reviewer_users],
                "teams": [{"slug": slug} for slug in reviewer_teams],
            },
            (
                "PUT",
                "/repos/catalog-org/skills/contents/"
                ".skillscout-gate-b4/gate-b4-12345-1-merge-probe.md",
            ): {
                "content": {"sha": "2" * 40},
                "commit": {"sha": MERGE_COMMIT_SHA},
            },
        }
        if key == ("GET", "/repos/catalog-org/skills/git/ref/heads/main"):
            routes[key] = {
                "ref": "refs/heads/main",
                "object": {"sha": default_sha},
            }
        if key == ("GET", "/repos/catalog-org/skills/pulls/79"):
            observed = mergeable[min(merge_poll_index, len(mergeable) - 1)]
            merge_poll_index += 1
            return httpx.Response(
                200,
                json={
                    "number": 79,
                    "draft": False,
                    "mergeable": observed,
                    "head": {"ref": merge_branch},
                    "base": {"ref": "main"},
                    "state": "closed" if merge_succeeded else "open",
                    "merged": merge_succeeded,
                    "merged_at": "2026-07-28T00:00:00Z" if merge_succeeded else None,
                },
            )
        if key == ("POST", "/repos/catalog-org/skills/git/refs"):
            ref = body["ref"]
            return httpx.Response(201, json={"ref": ref, "object": {"sha": DEFAULT_SHA}})
        if key == ("POST", "/repos/catalog-org/skills/pulls"):
            is_draft = body["draft"]
            branch = draft_branch if is_draft else merge_branch
            number = 78 if is_draft else 79
            return httpx.Response(
                201,
                json={
                    "number": number,
                    "draft": is_draft,
                    "head": {"ref": branch},
                    "base": {"ref": "main"},
                },
            )
        if key in statuses:
            status = statuses[key]
            if 200 <= status < 300:
                if key == ("PATCH", "/repos/catalog-org/skills/git/refs/heads/main"):
                    default_sha = body["sha"]
                    return httpx.Response(
                        status,
                        json={"ref": "refs/heads/main", "object": {"sha": default_sha}},
                    )
                if key == ("PUT", "/repos/catalog-org/skills/pulls/79/merge"):
                    merge_succeeded = True
                    return httpx.Response(status, json={"merged": True, "sha": MERGE_COMMIT_SHA})
                if key == ("POST", "/repos/catalog-org/skills/rulesets"):
                    return httpx.Response(status, json={"id": 555})
                return httpx.Response(status, json=[])
            return httpx.Response(
                status,
                json={"message": "denied", "private_payload": "MUST_NOT_APPEAR"},
            )
        if key in routes:
            return httpx.Response(200, json=routes[key])
        raise AssertionError(f"unexpected route: {key}")

    return httpx.MockTransport(respond)


def test_preflight_is_all_or_nothing_and_never_requires_a_token() -> None:
    module = _module()
    env = _env()
    env.pop("SKILLSCOUT_CANARY_APP_TOKEN")
    env.pop("SKILLSCOUT_CANARY_ACTUAL_INSTALLATION_ID")
    config = module.load_preflight_config(env)
    assert config.catalog_full_name == "catalog-org/skills"
    assert config.branch_prefix == "skillscout/gate-b4-12345-1"
    for name in tuple(env):
        partial = dict(env)
        partial.pop(name)
        with pytest.raises(module.CanaryAdmissionError):
            module.load_preflight_config(partial)


def test_canary_uses_exact_fixed_route_allowlist_and_emits_bounded_evidence() -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    result = module.run_canary(
        module.load_run_config(_env()),
        transport=_transport(requests),
        sleeper=lambda _: None,
    )
    methods_paths = [(method, path) for method, path, _ in requests]
    assert methods_paths == [
        ("GET", "/installation/repositories"),
        ("GET", "/repos/catalog-org/skills"),
        ("GET", "/repos/catalog-org/skills/git/ref/heads/main"),
        ("POST", "/repos/catalog-org/skills/git/refs"),
        (
            "PUT",
            "/repos/catalog-org/skills/contents/.skillscout-gate-b4/gate-b4-12345-1-draft.md",
        ),
        ("POST", "/repos/catalog-org/skills/pulls"),
        ("POST", "/repos/catalog-org/skills/pulls/78/requested_reviewers"),
        ("GET", "/repos/catalog-org/skills/pulls/78"),
        ("GET", "/repos/catalog-org/skills/pulls/78/requested_reviewers"),
        ("POST", "/repos/catalog-org/skills/git/refs"),
        (
            "PUT",
            "/repos/catalog-org/skills/contents/.skillscout-gate-b4/gate-b4-12345-1-merge-probe.md",
        ),
        ("POST", "/repos/catalog-org/skills/pulls"),
        ("GET", "/repos/catalog-org/skills/pulls/79"),
        ("PATCH", "/repos/catalog-org/skills/git/refs/heads/main"),
        ("PUT", "/repos/catalog-org/skills/pulls/79/merge"),
        ("GET", "/repos/catalog-org/skills/rulesets"),
        ("POST", "/repos/catalog-org/skills/rulesets"),
        ("GET", "/repos/other-org/private"),
        ("GET", "/repos/catalog-org/skills/actions/secrets"),
        ("GET", "/repos/catalog-org/skills/git/ref/heads/main"),
    ]
    bodies = [body for _, _, body in requests]
    assert bodies[3] == {
        "ref": "refs/heads/skillscout/gate-b4-12345-1-draft",
        "sha": DEFAULT_SHA,
    }
    assert bodies[5] == {
        "title": "SkillScout controlled Gate B4 draft canary",
        "body": (
            "Fixed, non-production Gate B4 evidence. "
            "Human/admin cleanup is required; automation will not merge."
        ),
        "head": "skillscout/gate-b4-12345-1-draft",
        "base": "main",
        "draft": True,
        "maintainer_can_modify": False,
    }
    assert bodies[6] == {
        "reviewers": ["skill-maintainer"],
        "team_reviewers": [],
    }
    assert bodies[9] == {
        "ref": "refs/heads/skillscout/gate-b4-12345-1-merge-probe",
        "sha": DEFAULT_SHA,
    }
    assert bodies[11]["draft"] is False
    assert bodies[13] == {"sha": MERGE_COMMIT_SHA, "force": False}
    assert bodies[14] == {"merge_method": "squash"}
    assert result["positive_draft"] == {
        "branch": "skillscout/gate-b4-12345-1-draft",
        "pull_number": 78,
        "draft": True,
        "requested_reviewers": ["skill-maintainer"],
    }
    assert result["merge_probe"]["otherwise_mergeable"] is True
    assert result["default_ref"] == {
        "before": DEFAULT_SHA,
        "after": DEFAULT_SHA,
        "unchanged": True,
    }
    assert set(result["negative_probes"]) == {
        "default_ref_mutation",
        "merge",
        "ruleset_read",
        "ruleset_mutation",
        "secret_metadata_read",
        "unauthorized_private_repository",
    }
    assert result["negative_probes"] == {
        "default_ref_mutation": "denied_403",
        "merge": "denied_405",
        "ruleset_read": "success_200",
        "ruleset_mutation": "denied_403",
        "secret_metadata_read": "denied_403",
        "unauthorized_private_repository": "not_found_404",
    }
    assert result["cleanup_manifest"] == {
        "repository": "catalog-org/skills",
        "branches": [
            "skillscout/gate-b4-12345-1-draft",
            "skillscout/gate-b4-12345-1-merge-probe",
        ],
        "pulls": [78, 79],
    }
    encoded = module.canonical_evidence(result)
    assert len(encoded) <= 8_192
    assert encoded.endswith("\n")
    for forbidden in (
        TOKEN,
        "authorization",
        "MUST_NOT_APPEAR",
        "private_payload",
        "denied",
    ):
        if forbidden == "denied":
            continue
        assert forbidden not in encoded.casefold()


def test_canary_request_surface_has_no_cleanup_approve_review_or_ready_routes() -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    module.run_canary(
        module.load_run_config(_env()),
        transport=_transport(requests),
        sleeper=lambda _: None,
    )
    assert not any(method == "DELETE" for method, _, _ in requests)
    forbidden = (
        "/reviews",
        "/ready-for-review",
        "/graphql",
        "/update-branch",
        "/auto-merge",
    )
    assert not any(marker in path for _, path, _ in requests for marker in forbidden)
    assert not any(
        isinstance(body, dict) and body.get("event") in {"APPROVE", "REQUEST_CHANGES", "COMMENT"}
        for _, _, body in requests
    )


def test_mid_run_failure_exposes_only_created_locators_for_human_cleanup() -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    failing_path = (
        "PUT",
        "/repos/catalog-org/skills/contents/.skillscout-gate-b4/gate-b4-12345-1-merge-probe.md",
    )
    with pytest.raises(module.CanaryRunError) as raised:
        module.run_canary(
            module.load_run_config(_env()),
            transport=_transport(requests, fail_at=failing_path),
            sleeper=lambda _: None,
        )
    assert raised.value.cleanup_manifest == {
        "repository": "catalog-org/skills",
        "branches": [
            "skillscout/gate-b4-12345-1-draft",
            "skillscout/gate-b4-12345-1-merge-probe",
        ],
        "pulls": [78],
    }
    assert TOKEN not in repr(raised.value)
    assert "MUST_NOT_APPEAR" not in repr(raised.value)
    assert not any(method == "DELETE" for method, _, _ in requests)


def test_mergeable_poll_is_bounded_and_accepts_only_eventual_true() -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    sleeps: list[float] = []
    result = module.run_canary(
        module.load_run_config(_env()),
        transport=_transport(requests, mergeable=(None, None, True)),
        sleeper=sleeps.append,
    )
    assert result["merge_probe"]["otherwise_mergeable"] is True
    assert sleeps == [module.MERGE_POLL_DELAY_SECONDS] * 2
    assert sum(sleeps) <= module.MAX_MERGE_POLL_SLEEP_SECONDS
    assert [
        path for method, path, _ in requests
        if method == "GET" and path == "/repos/catalog-org/skills/pulls/79"
    ] == ["/repos/catalog-org/skills/pulls/79"] * 3
    assert len(requests) <= module.MAX_REQUESTS


def test_mergeable_poll_exhaustion_fails_closed_with_recovery_observations() -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    sleeps: list[float] = []
    with pytest.raises(module.CanaryRunError) as raised:
        module.run_canary(
            module.load_run_config(_env()),
            transport=_transport(requests, mergeable=(None, None, None, None)),
            sleeper=sleeps.append,
        )
    assert sleeps == [module.MERGE_POLL_DELAY_SECONDS] * 2
    evidence = raised.value.evidence
    assert evidence["status"] == "failed_closed"
    assert evidence["default_ref"] == {
        "before": DEFAULT_SHA,
        "after": DEFAULT_SHA,
        "unchanged": True,
    }
    assert [pull["number"] for pull in evidence["remote_recovery"]["pulls"]] == [78, 79]
    assert len(requests) <= module.MAX_REQUESTS


@pytest.mark.parametrize(
    ("status_overrides", "unexpected_probe"),
    [
        ({("PATCH", "/repos/catalog-org/skills/git/refs/heads/main"): 409},
         "default_ref_mutation"),
        ({("PUT", "/repos/catalog-org/skills/pulls/79/merge"): 422}, "merge"),
        ({("GET", "/repos/catalog-org/skills/rulesets"): 422}, "ruleset_read"),
        ({("POST", "/repos/catalog-org/skills/rulesets"): 404}, "ruleset_mutation"),
        ({("GET", "/repos/other-org/private"): 403}, "unauthorized_private_repository"),
        ({("GET", "/repos/catalog-org/skills/actions/secrets"): 422},
         "secret_metadata_read"),
    ],
)
def test_each_probe_rejects_false_positive_statuses_and_recovers(
    status_overrides: dict[tuple[str, str], int],
    unexpected_probe: str,
) -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    with pytest.raises(module.CanaryRunError) as raised:
        module.run_canary(
            module.load_run_config(_env()),
            transport=_transport(requests, status_overrides=status_overrides),
            sleeper=lambda _: None,
        )
    assert raised.value.evidence["unexpected_probe"] == unexpected_probe
    assert raised.value.evidence["remote_recovery"]["pulls"]
    assert len(requests) <= module.MAX_REQUESTS


def test_unexpected_default_mutation_success_stops_and_reads_back_remote_state() -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    with pytest.raises(module.CanaryRunError) as raised:
        module.run_canary(
            module.load_run_config(_env()),
            transport=_transport(
                requests,
                status_overrides={
                    ("PATCH", "/repos/catalog-org/skills/git/refs/heads/main"): 200,
                },
            ),
            sleeper=lambda _: None,
        )
    evidence = raised.value.evidence
    assert evidence["unexpected_probe"] == "default_ref_mutation"
    assert evidence["default_ref"] == {
        "before": DEFAULT_SHA,
        "after": MERGE_COMMIT_SHA,
        "unchanged": False,
    }
    assert [pull["number"] for pull in evidence["remote_recovery"]["pulls"]] == [78, 79]
    patch_index = next(
        index
        for index, request in enumerate(requests)
        if request[:2] == ("PATCH", "/repos/catalog-org/skills/git/refs/heads/main")
    )
    assert [(method, path) for method, path, _ in requests[patch_index + 1:]] == [
        ("GET", "/repos/catalog-org/skills/git/ref/heads/main"),
        ("GET", "/repos/catalog-org/skills/pulls/78"),
        ("GET", "/repos/catalog-org/skills/pulls/79"),
    ]


def test_unexpected_ruleset_creation_records_run_specific_id_then_recovers() -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    with pytest.raises(module.CanaryRunError) as raised:
        module.run_canary(
            module.load_run_config(_env()),
            transport=_transport(
                requests,
                status_overrides={
                    ("POST", "/repos/catalog-org/skills/rulesets"): 201,
                },
            ),
            sleeper=lambda _: None,
        )
    assert raised.value.evidence["ruleset_mutation"] == {
        "name": "skillscout-gate-b4-12345-1-denial-probe",
        "id": 555,
    }
    assert raised.value.evidence["remote_recovery"]["pulls"]


@pytest.mark.parametrize(
    ("users", "teams"),
    [
        (("skill-maintainer", "extra-reviewer"), ()),
        (("skill-maintainer",), ("catalog-admins",)),
    ],
)
def test_positive_reviewer_observation_must_be_exact_user_and_zero_teams(
    users: tuple[str, ...],
    teams: tuple[str, ...],
) -> None:
    module = _module()
    with pytest.raises(module.CanaryRunError):
        module.run_canary(
            module.load_run_config(_env()),
            transport=_transport([], reviewer_users=users, reviewer_teams=teams),
            sleeper=lambda _: None,
        )


def test_transport_failure_is_sanitized_and_keeps_both_branch_locators() -> None:
    module = _module()
    requests: list[tuple[str, str, object | None]] = []
    with pytest.raises(module.CanaryRunError) as raised:
        module.run_canary(
            module.load_run_config(_env()),
            transport=_transport(
                requests,
                transport_error_at=("POST", "/repos/catalog-org/skills/pulls"),
            ),
            sleeper=lambda _: None,
        )
    assert raised.value.cleanup_manifest == {
        "repository": "catalog-org/skills",
        "branches": [
            "skillscout/gate-b4-12345-1-draft",
            "skillscout/gate-b4-12345-1-merge-probe",
        ],
        "pulls": [],
    }
    encoded = module.canonical_evidence(raised.value.evidence)
    assert "MUST_NOT_APPEAR" not in encoded
    assert TOKEN not in encoded
    assert len(encoded) <= 8_192


@pytest.mark.parametrize(
    "mutate",
    [
        lambda env: env | {"SKILLSCOUT_CANARY_ACTUAL_INSTALLATION_ID": "4002"},
        lambda env: env | {"SKILLSCOUT_CANARY_CATALOG_OWNER": "other-org"},
        lambda env: (
            env | {"SKILLSCOUT_CANARY_UNAUTHORIZED_PRIVATE_REPOSITORY": "catalog-org/skills"}
        ),
        lambda env: env | {"GITHUB_RUN_ID": "../../unsafe"},
    ],
)
def test_canary_rejects_identity_or_path_widening_before_http(
    mutate: Callable[[dict[str, str]], dict[str, str]],
) -> None:
    module = _module()
    with pytest.raises(module.CanaryAdmissionError):
        module.load_run_config(mutate(_env()))
