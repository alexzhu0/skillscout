"""Wave-0 RED contract for exact state-branch restore and non-force CAS."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

import httpx
import pytest

from skillscout.domain.discovery import DiscoveryStateRootV1


FIXTURES = Path(__file__).parent / "fixtures" / "state_branch"
SECRET_CANARIES = (
    "github_pat_STATE_BRANCH_CANARY",
    "-----BEGIN PRIVATE KEY-----",
    "STATE_BRANCH_REPOSITORY_BODY_CANARY",
)


def _state_module():
    return importlib.import_module("skillscout.adapters.state_branch")


def test_valid_state_fixture_parses_strict_root_and_exact_paths() -> None:
    fixture = json.loads((FIXTURES / "valid_state.json").read_bytes())
    root = DiscoveryStateRootV1.model_validate(fixture["root"], strict=True)
    assert root.root_locator == "state/root.json"
    assert tuple(item.locator for item in root.objects) == ()
    assert tuple(item.locator for item in root.databases) == (
        "state/databases/pipeline.sqlite3",
        "state/databases/operations.sqlite3",
        "state/databases/publication.sqlite3",
    )
    assert root.state_parent_commit_sha == fixture["observed_head"]


def test_conflict_fixture_is_closed_and_forbids_followup_writes() -> None:
    matrix = json.loads((FIXTURES / "conflict_matrix.json").read_bytes())
    assert matrix["schema_version"] == "state-branch-conflict-matrix-v1"
    assert {case["name"] for case in matrix["cases"]} == {
        "update_409",
        "update_422",
        "head_changed",
        "lying_mutation_response",
        "reread_mismatch",
    }
    assert matrix["prohibited_followups"] == [
        "force",
        "merge",
        "prune",
        "retry",
    ]


def test_state_fixtures_are_bounded_and_contain_no_prose_or_secret_canary() -> None:
    for path in sorted(FIXTURES.glob("*.json")):
        payload = path.read_bytes()
        assert len(payload) < 16_384
        assert b"-wal" not in payload
        assert b"-journal" not in payload
        for canary in SECRET_CANARIES:
            assert canary.encode() not in payload


def test_state_client_exposes_only_fixed_git_object_capabilities() -> None:
    client_type = getattr(_state_module(), "StateBranchClient")
    public = {
        name
        for name, member in inspect.getmembers(client_type)
        if not name.startswith("_") and callable(member)
    }
    assert {
        "get_state_ref",
        "get_commit",
        "get_tree",
        "get_blob",
        "create_blob",
        "create_tree",
        "create_commit",
        "create_state_ref",
        "update_state_ref",
        "close",
    } <= public
    assert not public.intersection(
        {
            "create_pull",
            "request_reviewers",
            "merge",
            "approve",
            "ready_for_review",
            "delete_ref",
            "request",
        }
    )


def test_absent_branch_bootstrap_and_valid_restore_are_distinct() -> None:
    module = _state_module()
    fixture = json.loads((FIXTURES / "valid_state.json").read_bytes())
    absent = module.StateBranchStore.restore_from_fixture(
        fixture,
        state_ref=None,
    )
    assert absent.status == "absent"
    assert absent.bundle is None

    restored = module.StateBranchStore.restore_from_fixture(
        fixture,
        state_ref=fixture["observed_head"],
    )
    assert restored.status == "verified"
    assert restored.observed_head == fixture["observed_head"]
    assert restored.bundle.root.root_digest == fixture["root"]["root_digest"]


@pytest.mark.parametrize(
    "mutation",
    (
        "unexpected_path",
        "wrong_mode",
        "symlink",
        "missing_database",
        "database_swap",
        "object_swap",
        "rollback_root",
        "prospective_secret",
    ),
)
def test_restore_and_prospective_tree_mutations_fail_before_authority(
    mutation: str,
) -> None:
    module = _state_module()
    fixture = json.loads((FIXTURES / "valid_state.json").read_bytes())
    with pytest.raises(module.StateIntegrityFailure):
        module.StateBranchStore.restore_from_fixture(
            fixture,
            state_ref=fixture["observed_head"],
            mutation=mutation,
        )


@pytest.mark.parametrize(
    "case_name",
    (
        "update_409",
        "update_422",
        "head_changed",
        "lying_mutation_response",
        "reread_mismatch",
    ),
)
def test_parent_bound_non_force_conflict_stops_without_followup(
    case_name: str,
) -> None:
    module = _state_module()
    fixture = json.loads((FIXTURES / "valid_state.json").read_bytes())
    remote = module.FixtureStateRemote(case_name=case_name)
    store = module.StateBranchStore(remote)
    with pytest.raises(module.StateBranchConflict):
        store.sync_fixture(
            fixture,
            observed_head=fixture["observed_head"],
        )
    assert remote.force_values in ([], [False])
    assert remote.followup_actions == []
    assert remote.commit_parents in (
        [],
        [(fixture["observed_head"],)],
    )


def test_state_client_accepts_only_expected_recursive_tree_directories() -> None:
    module = _state_module()
    tree_sha = "a" * 40
    root_sha = "b" * 40

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/repos/source-org/source/git/trees/{tree_sha}"
        assert request.url.params.get("recursive") == "1"
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "x-github-request-id": "STATE-TREE-1",
            },
            json={
                "sha": tree_sha,
                "truncated": False,
                "tree": [
                    {
                        "path": "state",
                        "mode": "040000",
                        "type": "tree",
                        "sha": "c" * 40,
                    },
                    {
                        "path": "state/databases",
                        "mode": "040000",
                        "type": "tree",
                        "sha": "d" * 40,
                    },
                    {
                        "path": "state/root.json",
                        "mode": "100644",
                        "type": "blob",
                        "sha": root_sha,
                        "size": 100,
                    },
                ],
            },
        )

    client = module.StateBranchClient(
        token="test-token",
        repository_id=101,
        repository_full_name="source-org/source",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.get_tree(tree_sha) == (
            module.StateTreeEntry(
                path="state/root.json",
                sha=root_sha,
                mode="100644",
                size=100,
            ),
        )
    finally:
        client.close()


def test_state_client_rejects_unexpected_recursive_tree_directory() -> None:
    module = _state_module()
    tree_sha = "a" * 40

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "x-github-request-id": "STATE-TREE-2",
            },
            json={
                "sha": tree_sha,
                "truncated": False,
                "tree": [
                    {
                        "path": "state/logs",
                        "mode": "040000",
                        "type": "tree",
                        "sha": "c" * 40,
                    }
                ],
            },
        )

    client = module.StateBranchClient(
        token="test-token",
        repository_id=101,
        repository_full_name="source-org/source",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(Exception):
            client.get_tree(tree_sha)
    finally:
        client.close()
