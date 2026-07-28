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
) -> httpx.MockTransport:
    draft_branch = "skillscout/gate-b4-12345-1-draft"
    merge_branch = "skillscout/gate-b4-12345-1-merge-probe"

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if fail_at == (request.method, request.url.path):
            return httpx.Response(500, json={"message": "MUST_NOT_APPEAR"})
        routes: dict[tuple[str, str], object] = {
            ("GET", "/installation"): {"id": 4001},
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
                "object": {"sha": DEFAULT_SHA},
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
            },
            (
                "GET",
                "/repos/catalog-org/skills/pulls/78/requested_reviewers",
            ): {"users": [{"login": "skill-maintainer"}], "teams": []},
            (
                "PUT",
                "/repos/catalog-org/skills/contents/"
                ".skillscout-gate-b4/gate-b4-12345-1-merge-probe.md",
            ): {
                "content": {"sha": "2" * 40},
                "commit": {"sha": MERGE_COMMIT_SHA},
            },
            ("GET", "/repos/catalog-org/skills/pulls/79"): {
                "number": 79,
                "draft": False,
                "mergeable": True,
                "head": {"ref": merge_branch},
                "base": {"ref": "main"},
            },
        }
        key = (request.method, request.url.path)
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
        if key in routes:
            return httpx.Response(200, json=routes[key])
        denied = {
            ("PATCH", "/repos/catalog-org/skills/git/refs/heads/main"),
            ("PUT", "/repos/catalog-org/skills/pulls/79/merge"),
            ("GET", "/repos/catalog-org/skills/rulesets"),
            ("POST", "/repos/catalog-org/skills/rulesets"),
            ("GET", "/repos/other-org/private"),
            ("GET", "/repos/catalog-org/skills/actions/secrets"),
        }
        if key in denied:
            return httpx.Response(
                403,
                json={
                    "message": "denied",
                    "private_payload": "MUST_NOT_APPEAR",
                },
            )
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
    )
    methods_paths = [(method, path) for method, path, _ in requests]
    assert methods_paths == [
        ("GET", "/installation"),
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
    assert bodies[4] == {
        "ref": "refs/heads/skillscout/gate-b4-12345-1-draft",
        "sha": DEFAULT_SHA,
    }
    assert bodies[6] == {
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
    assert bodies[7] == {
        "reviewers": ["skill-maintainer"],
        "team_reviewers": [],
    }
    assert bodies[10] == {
        "ref": "refs/heads/skillscout/gate-b4-12345-1-merge-probe",
        "sha": DEFAULT_SHA,
    }
    assert bodies[12]["draft"] is False
    assert bodies[14] == {"sha": MERGE_COMMIT_SHA, "force": False}
    assert bodies[15] == {"merge_method": "squash"}
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
    assert set(result["negative_probes"].values()) == {"denied"}
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
    module.run_canary(module.load_run_config(_env()), transport=_transport(requests))
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
