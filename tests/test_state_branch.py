"""Wave-0 RED contract for exact state-branch restore and non-force CAS."""

from __future__ import annotations

import base64
import importlib
import inspect
import json
from pathlib import Path

import httpx
import pytest

from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
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


def test_three_store_bundle_coordinator_is_schema_owner_agnostic() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "skillscout"
        / "adapters"
        / "operations_state.py"
    ).read_text()
    for private_table in (
        "CREATE TABLE runs",
        "CREATE TABLE phase3_runs",
        "CREATE TABLE publication_attempts",
        "CREATE TABLE publication_checkpoints",
    ):
        assert private_table not in source
    assert "state/databases/pipeline.sqlite3" in source
    assert "state/databases/operations.sqlite3" in source
    assert "state/databases/publication.sqlite3" in source


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


def _missing_state_ref_client(module: object, request_id: str | None) -> object:
    def handler(_request: httpx.Request) -> httpx.Response:
        headers = {"content-type": "application/json"}
        if request_id is not None:
            headers["x-github-request-id"] = request_id
        return httpx.Response(
            404,
            headers=headers,
            json={"message": "provider text must stay closed"},
        )

    return module.StateBranchClient(
        token="test-token",
        repository_id=101,
        repository_full_name="source-org/source",
        transport=httpx.MockTransport(handler),
    )


def test_state_client_classifies_absent_ref_with_live_colon_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = _state_module()
    request_id = "753C:748B6:2CB2070:2EA615C:6A679381"
    client = _missing_state_ref_client(module, request_id)
    try:
        with pytest.raises(module.StateRefNotFound) as caught:
            client.get_state_ref()
    finally:
        client.close()

    assert request_id not in repr(caught.value)
    assert request_id not in caplog.text


@pytest.mark.parametrize(
    "request_id",
    (
        None,
        "",
        "753C 748B6",
        "753C:\t748B6",
        "753C:\x00748B6",
        ":753C",
        "753C:",
        "753C::748B6",
        "753C:GG",
        "753C:-748B6",
        ("A" * 64) + ":" + ("B" * 64),
    ),
)
def test_state_client_rejects_malformed_or_oversized_request_id(
    request_id: str | None,
) -> None:
    module = _state_module()
    client = _missing_state_ref_client(module, request_id)
    try:
        with pytest.raises(module.SafeFailure):
            client.get_state_ref()
    finally:
        client.close()


def _state_blob_client(
    module: object,
    *,
    encoded: str,
    declared_size: int,
    requested_sha: str,
) -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == (
            f"/repos/source-org/source/git/blobs/{requested_sha}"
        )
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "x-github-request-id": "STATE-BLOB-1",
            },
            json={
                "encoding": "base64",
                "content": encoded,
                "size": declared_size,
            },
        )

    return module.StateBranchClient(
        token="test-token",
        repository_id=101,
        repository_full_name="source-org/source",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.parametrize("separator", ("", "\n", "\r", "\r\n"))
def test_state_client_accepts_only_cr_lf_folded_canonical_blob_content(
    separator: str,
) -> None:
    module = _state_module()
    content = bytes(range(97))
    canonical = base64.b64encode(content).decode("ascii")
    encoded = separator.join(
        canonical[index : index + 60]
        for index in range(0, len(canonical), 60)
    )
    requested_sha = module._git_blob_id(content)
    client = _state_blob_client(
        module,
        encoded=encoded,
        declared_size=len(content),
        requested_sha=requested_sha,
    )
    try:
        assert client.get_blob(requested_sha) == content
    finally:
        client.close()


@pytest.mark.parametrize(
    "encoded",
    (
        pytest.param("/w ==", id="space"),
        pytest.param("/w==\t", id="tab"),
        pytest.param("/w==\x00", id="nul"),
        pytest.param("/w==\x0b", id="vertical-tab"),
        pytest.param("/w==\x7f", id="delete-control"),
        pytest.param("/w=", id="missing-padding"),
        pytest.param("/w===", id="excess-padding"),
        pytest.param("/=w=", id="interior-padding"),
        pytest.param("/x==", id="noncanonical-pad-bits-x"),
        pytest.param("/y==", id="noncanonical-pad-bits-y"),
        pytest.param("/z==", id="noncanonical-pad-bits-z"),
    ),
)
def test_state_client_rejects_noncanonical_blob_wire_mutations(
    encoded: str,
) -> None:
    module = _state_module()
    content = b"\xff"
    requested_sha = module._git_blob_id(content)
    client = _state_blob_client(
        module,
        encoded=encoded,
        declared_size=len(content),
        requested_sha=requested_sha,
    )
    try:
        with pytest.raises(module.SafeFailure):
            client.get_blob(requested_sha)
    finally:
        client.close()


@pytest.mark.parametrize("mutation", ("declared_size", "git_blob_id"))
def test_state_client_retains_blob_size_and_identity_verification(
    mutation: str,
) -> None:
    module = _state_module()
    content = b"state-branch-integrity"
    requested_sha = module._git_blob_id(content)
    declared_size = len(content)
    if mutation == "declared_size":
        declared_size += 1
    else:
        requested_sha = "0" * 40
    client = _state_blob_client(
        module,
        encoded=base64.b64encode(content).decode("ascii"),
        declared_size=declared_size,
        requested_sha=requested_sha,
    )
    try:
        with pytest.raises(module.SafeFailure):
            client.get_blob(requested_sha)
    finally:
        client.close()


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
    database_sha = "e" * 40

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
                        "path": "state/databases/pipeline.sqlite3",
                        "mode": "100644",
                        "type": "blob",
                        "sha": database_sha,
                        "size": 200,
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
                path="state/databases/pipeline.sqlite3",
                sha=database_sha,
                mode="100644",
                size=200,
            ),
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


def _bundle(
    module: object,
    *,
    parent: str,
    pipeline_bytes: bytes = b"SQLite format 3\x00pipeline-state",
) -> object:
    database_bytes = {
        "pipeline": pipeline_bytes,
        "operations": b"SQLite format 3\x00operations-state",
        "publication": b"SQLite format 3\x00publication-state",
    }
    projection = {
        "schema_version": "discovery-state-rebuild-projection-v1",
        "search_page_digests": [],
        "candidate_digests": [],
        "discovery_reservation_digests": [],
        "semantic_reservation_digests": [],
        "workflow_terminal_digests": [],
        "candidate_terminal_digests": [],
        "run_summary_digests": [],
    }
    projection["projection_digest"] = sha256_digest(projection)
    root_payload = {
        "schema_version": "discovery-state-root-v1",
        "root_locator": "state/root.json",
        "prior_root_digest": None,
        "state_parent_commit_sha": parent,
        "query_set_digest": "sha256:" + "1" * 64,
        "budget_policy_digest": "sha256:" + "2" * 64,
        "objects": [],
        "databases": [
            {
                "owner": owner,
                "locator": f"state/databases/{owner}.sqlite3",
                "content_digest": sha256_digest(content),
                "size_bytes": len(content),
                "schema_fingerprint": "sha256:" + digit * 64,
            }
            for owner, content, digit in (
                ("pipeline", database_bytes["pipeline"], "a"),
                ("operations", database_bytes["operations"], "b"),
                ("publication", database_bytes["publication"], "c"),
            )
        ],
        "rebuild_projection": projection,
        "created_at": "2026-07-27T12:00:00.000000Z",
    }
    root_payload["root_digest"] = sha256_digest(root_payload)
    root = DiscoveryStateRootV1.model_validate(root_payload, strict=True)
    files = [
        module.StateOwnedFile(
            "state/root.json",
            canonical_json_bytes(root.model_dump(mode="json", exclude_none=False)),
        )
    ]
    files.extend(
        module.StateOwnedFile(f"state/databases/{owner}.sqlite3", content)
        for owner, content in database_bytes.items()
    )
    return module.VerifiedStateBundle(root, tuple(files))


class _StateRemote:
    def __init__(self, module: object, head: str | None) -> None:
        self.module = module
        self.head = head
        self.blobs: dict[str, bytes] = {}
        self.trees: dict[str, tuple[object, ...]] = {}
        self.commits: dict[str, object] = {}
        self.writes: list[str] = []
        self.force_values: list[bool] = []
        self.counter = 10

    def _sha(self) -> str:
        self.counter += 1
        return f"{self.counter:040x}"

    def get_state_ref(self) -> object:
        if self.head is None:
            raise self.module.StateRefNotFound
        return self.module.StateRefObservation(
            self.module.STATE_REF,
            self.head,
        )

    def create_blob(self, content: bytes) -> str:
        sha = self.module._git_blob_id(content)
        self.blobs[sha] = content
        self.writes.append("blob")
        return sha

    def create_tree(self, entries: list[dict[str, object]]) -> str:
        sha = self._sha()
        self.trees[sha] = tuple(
            self.module.StateTreeEntry(
                path=str(entry["path"]),
                sha=str(entry["sha"]),
                mode="100644",
                size=len(self.blobs[str(entry["sha"])]),
            )
            for entry in entries
        )
        self.writes.append("tree")
        return sha

    def create_commit(
        self,
        message: str,
        tree: str,
        parents: tuple[str, ...],
    ) -> str:
        sha = self._sha()
        self.commits[sha] = self.module.StateCommitObservation(
            sha=sha,
            tree_sha=tree,
            parents=tuple(parents),
            message=message,
        )
        self.writes.append("commit")
        return sha

    def create_state_ref(self, sha: str) -> object:
        self.head = sha
        self.writes.append("create_ref")
        return self.module.StateRefObservation(self.module.STATE_REF, sha)

    def update_state_ref(self, sha: str, *, force: bool) -> object:
        self.force_values.append(force)
        self.head = sha
        self.writes.append("update_ref")
        return self.module.StateRefObservation(self.module.STATE_REF, sha)

    def get_commit(self, sha: str) -> object:
        return self.commits[sha]

    def get_tree(self, sha: str) -> tuple[object, ...]:
        return self.trees[sha]

    def get_blob(self, sha: str) -> bytes:
        return self.blobs[sha]


@pytest.mark.parametrize("bootstrap", (False, True))
def test_sync_bootstrap_and_fast_forward_reread_exact_state(
    bootstrap: bool,
) -> None:
    module = _state_module()
    observed_head = None if bootstrap else "4" * 40
    root_parent = observed_head or "0" * 40
    remote = _StateRemote(module, observed_head)

    result = module.StateBranchStore(remote).sync(
        _bundle(module, parent=root_parent),
        observed_head=observed_head,
    )

    assert result.status == "verified"
    assert result.previous_head == observed_head
    assert remote.commits[result.commit_sha].parents == (
        () if bootstrap else (observed_head,)
    )
    assert remote.force_values == ([] if bootstrap else [False])
    assert remote.writes[-1] == ("create_ref" if bootstrap else "update_ref")


def test_sync_secret_canary_fails_before_first_blob_creation() -> None:
    module = _state_module()
    observed_head = "4" * 40
    remote = _StateRemote(module, observed_head)
    bundle = _bundle(
        module,
        parent=observed_head,
        pipeline_bytes=b"SQLite format 3\x00github_pat_STATE_BRANCH_CANARY",
    )

    with pytest.raises(module.StateIntegrityFailure):
        module.StateBranchStore(remote).sync(bundle, observed_head)

    assert remote.writes == []


def test_sync_changed_observed_head_fails_before_first_blob_creation() -> None:
    module = _state_module()
    observed_head = "4" * 40
    remote = _StateRemote(module, "5" * 40)

    with pytest.raises(module.StateBranchConflict):
        module.StateBranchStore(remote).sync(
            _bundle(module, parent=observed_head),
            observed_head,
        )

    assert remote.writes == []
