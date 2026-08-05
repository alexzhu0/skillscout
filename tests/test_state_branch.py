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
from skillscout.domain.enums import EffectScope


FIXTURES = Path(__file__).parent / "fixtures" / "state_branch"
SECRET_CANARIES = (
    "github_pat_STATE_BRANCH_CANARY",
    "-----BEGIN PRIVATE KEY-----",
    "STATE_BRANCH_REPOSITORY_BODY_CANARY",
)


def _state_module():
    return importlib.import_module("skillscout.adapters.state_branch")


def test_state_branch_read_client_exposes_no_remote_write_capability() -> None:
    module = _state_module()
    client = module.StateBranchReadClient(
        token="test-token",
        repository_id=101,
        repository_full_name="source-org/source",
        transport=httpx.MockTransport(
            lambda _request: pytest.fail("construction must not make a request")
        ),
    )
    try:
        assert client.effect_scope is EffectScope.REMOTE_READ
        assert {
            name
            for name, _value in inspect.getmembers(
                client, predicate=callable
            )
            if not name.startswith("_")
        } == {
            "close",
            "get_blob",
            "get_commit",
            "get_state_ref",
            "get_tree",
        }
    finally:
        client.close()


def test_resume_read_budget_enforces_requests_bytes_and_deadline() -> None:
    """The resolver budget charges actual reads rather than predicting them."""

    module = _state_module()
    now = [100.0]
    budget = module.ResolverReadBudget(clock=lambda: now[0])

    for _ in range(1_024):
        assert budget.begin_request() > 0
    with pytest.raises(module.StateIntegrityFailure):
        budget.begin_request()
    assert budget.request_count == 1_024

    byte_budget = module.ResolverReadBudget(clock=lambda: now[0])
    byte_budget.charge_response_bytes(268_435_456)
    with pytest.raises(module.StateIntegrityFailure):
        byte_budget.charge_response_bytes(1)
    assert byte_budget.response_bytes == 268_435_456

    deadline_budget = module.ResolverReadBudget(clock=lambda: now[0])
    now[0] += 45.0
    with pytest.raises(module.StateIntegrityFailure):
        deadline_budget.begin_request()


def test_resume_read_budget_sets_remaining_timeout_and_rejects_blocking_call() -> None:
    """A call that consumes the deadline fails even when transport returns a body."""

    module = _state_module()
    now = [10.0]
    observed_timeout: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_timeout.append(request.extensions["timeout"]["read"])
        now[0] += 45.0
        return httpx.Response(
            200,
            headers={
                "content-type": "application/json",
                "x-github-request-id": "REQ-budget",
            },
            json={
                "ref": module.STATE_REF,
                "object": {"sha": "a" * 40},
            },
        )

    budget = module.ResolverReadBudget(clock=lambda: now[0])
    client = module.StateBranchReadClient(
        token="test-token",
        repository_id=101,
        repository_full_name="source-org/source",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(Exception):
            client.get_state_ref(read_budget=budget)
    finally:
        client.close()

    assert observed_timeout == [45.0]
    assert budget.request_count == 1
    assert budget.response_bytes == 0


def test_resolver_read_budget_allows_90_seconds_only_for_payload_phase() -> None:
    module = _state_module()
    now = [100.0]

    lineage_budget = module.ResolverReadBudget(
        clock=lambda: now[0],
        phase="lineage",
    )
    assert lineage_budget.phase == "lineage"
    now[0] += 45.0
    with pytest.raises(module.StateIntegrityFailure):
        lineage_budget.begin_request()

    now[0] = 200.0
    payload_budget = module.ResolverReadBudget.payload_phase(clock=lambda: now[0])
    assert payload_budget.phase == "payload"
    now[0] += 89.0
    assert payload_budget.begin_request() > 0
    now[0] += 1.0
    with pytest.raises(module.StateIntegrityFailure):
        payload_budget.begin_request()

    for kwargs in (
        {"max_elapsed_seconds": 90.0},
        {"max_elapsed_seconds": 90.0, "phase": "ref"},
        {"max_elapsed_seconds": 45.0, "phase": "payload"},
    ):
        with pytest.raises(module.StateIntegrityFailure):
            module.ResolverReadBudget(**kwargs)


def test_payload_phase_budget_keeps_request_and_response_limits() -> None:
    module = _state_module()
    payload_budget = module.ResolverReadBudget.payload_phase(
        max_requests=1,
        max_response_bytes=2,
    )

    assert payload_budget.begin_request() > 0
    with pytest.raises(module.StateIntegrityFailure):
        payload_budget.begin_request()
    payload_budget.charge_response_bytes(2)
    with pytest.raises(module.StateIntegrityFailure):
        payload_budget.charge_response_bytes(1)


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
    object_count: int = 0,
    prior_root_digest: str | None = None,
) -> object:
    database_bytes = {
        "pipeline": pipeline_bytes,
        "operations": b"SQLite format 3\x00operations-state",
        "publication": b"SQLite format 3\x00publication-state",
    }
    object_bytes = {
        sha256_digest({"index": index}): canonical_json_bytes({"index": index})
        for index in range(object_count)
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
        "prior_root_digest": prior_root_digest,
        "state_parent_commit_sha": parent,
        "query_set_digest": "sha256:" + "1" * 64,
        "budget_policy_digest": "sha256:" + "2" * 64,
        "objects": [
            {
                "object_digest": digest,
                "locator": (
                    "state/objects/sha256/"
                    f"{digest.removeprefix('sha256:')[:2]}/"
                    f"{digest.removeprefix('sha256:')}.json"
                ),
                "size_bytes": len(content),
            }
            for digest, content in sorted(object_bytes.items())
        ],
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
        ),
        *(
            module.StateOwnedFile(
                (
                    "state/objects/sha256/"
                    f"{digest.removeprefix('sha256:')[:2]}/"
                    f"{digest.removeprefix('sha256:')}.json"
                ),
                content,
            )
            for digest, content in sorted(object_bytes.items())
        ),
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
        self.initial_root_digest: str | None = None
        if head is not None:
            seed = _bundle(module, parent="0" * 40)
            self.initial_root_digest = seed.root.root_digest
            contents = seed.content_by_path()
            for content in contents.values():
                self.blobs[self.module._git_blob_id(content)] = content
            tree_sha = self._sha()
            self.trees[tree_sha] = tuple(
                self.module.StateTreeEntry(
                    path=path,
                    sha=self.module._git_blob_id(content),
                    mode="100644",
                    size=len(content),
                )
                for path, content in sorted(contents.items())
            )
            self.commits[head] = self.module.StateCommitObservation(
                sha=head,
                tree_sha=tree_sha,
                parents=(),
                message=self.module._state_commit_message(seed.root.root_digest),
            )

    def _sha(self) -> str:
        self.counter += 1
        return f"{self.counter:040x}"

    def get_state_ref(self, *, read_budget: object | None = None) -> object:
        if read_budget is not None:
            read_budget.begin_request()
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

    def get_commit(self, sha: str, *, read_budget: object | None = None) -> object:
        if read_budget is not None:
            read_budget.begin_request()
        return self.commits[sha]

    def get_tree(
        self,
        sha: str,
        *,
        read_budget: object | None = None,
    ) -> tuple[object, ...]:
        if read_budget is not None:
            read_budget.begin_request()
        return self.trees[sha]

    def get_blob(self, sha: str, *, read_budget: object | None = None) -> bytes:
        if read_budget is not None:
            read_budget.begin_request()
        return self.blobs[sha]


def _initial_root(remote: _StateRemote) -> str:
    """Return the canonical root carried by a synthetic state-branch genesis."""

    assert remote.initial_root_digest is not None
    return remote.initial_root_digest


def _inject_state_bundle(
    remote: _StateRemote,
    bundle: object,
    *,
    parents: tuple[str, ...],
) -> str:
    """Install an adversarial immutable state commit without using the store."""

    files = bundle.content_by_path()
    entries = [
        {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": remote.create_blob(content),
        }
        for path, content in sorted(files.items())
    ]
    tree_sha = remote.create_tree(entries)
    return remote.create_commit(
        remote.module._state_commit_message(bundle.root.root_digest),
        tree_sha,
        parents,
    )


def test_sync_rejects_a_noncanonical_immediate_state_parent() -> None:
    """A foreign Git parent is not an empty state lineage."""

    module = _state_module()
    observed_head = "4" * 40
    remote = _StateRemote(module, observed_head)
    parent = remote.commits[observed_head]
    remote.commits[observed_head] = module.StateCommitObservation(
        sha=parent.sha,
        tree_sha=parent.tree_sha,
        parents=parent.parents,
        message="foreign parent",
    )

    with pytest.raises(module.StateBranchConflict):
        module.StateBranchStore(remote).sync(
            _bundle(module, parent=observed_head),
            observed_head=observed_head,
        )

    assert remote.writes == []


def test_restore_rejects_a_valid_child_above_a_broken_ancestor_link() -> None:
    """One valid child may not hide a malformed prior state transition."""

    module = _state_module()
    anchor = "4" * 40
    remote = _StateRemote(module, anchor)
    malformed_parent = _bundle(module, parent=anchor, prior_root_digest=None)
    parent_commit = _inject_state_bundle(
        remote,
        malformed_parent,
        parents=(anchor,),
    )
    valid_child = _bundle(
        module,
        parent=parent_commit,
        prior_root_digest=malformed_parent.root.root_digest,
    )
    child_commit = _inject_state_bundle(
        remote,
        valid_child,
        parents=(parent_commit,),
    )
    remote.update_state_ref(child_commit, force=False)

    with pytest.raises(module.StateIntegrityFailure):
        module.StateBranchStore(remote).restore()


def test_sync_refuses_to_extend_a_broken_older_state_ancestor() -> None:
    """CAS must not make a valid child durable above a malformed history edge."""

    module = _state_module()
    anchor = "4" * 40
    remote = _StateRemote(module, anchor)
    malformed_parent = _bundle(module, parent=anchor, prior_root_digest=None)
    parent_commit = _inject_state_bundle(
        remote,
        malformed_parent,
        parents=(anchor,),
    )
    remote.update_state_ref(parent_commit, force=False)
    remote.writes.clear()
    child = _bundle(
        module,
        parent=parent_commit,
        prior_root_digest=malformed_parent.root.root_digest,
    )

    with pytest.raises(module.StateBranchConflict):
        module.StateBranchStore(remote).sync(child, observed_head=parent_commit)

    assert remote.head == parent_commit
    assert remote.writes == []


@pytest.mark.parametrize(
    ("state_parent_commit_sha", "prior_root_digest"),
    (
        ("4" * 40, None),
        ("0" * 40, "sha256:" + ("a" * 64)),
    ),
    ids=("wrong-genesis-parent", "unexpected-prior-root"),
)
def test_restore_rejects_a_parentless_commit_that_is_not_canonical_genesis(
    state_parent_commit_sha: str,
    prior_root_digest: str | None,
) -> None:
    """Only the explicit zero-parent root may terminate a state lineage."""

    module = _state_module()
    remote = _StateRemote(module, None)
    malformed = _bundle(
        module,
        parent=state_parent_commit_sha,
        prior_root_digest=prior_root_digest,
    )
    commit_sha = _inject_state_bundle(remote, malformed, parents=())
    remote.create_state_ref(commit_sha)

    with pytest.raises(module.StateIntegrityFailure):
        module.StateBranchStore(remote).restore()


@pytest.mark.parametrize(
    ("state_parent_commit_sha", "prior_root_digest"),
    (
        ("4" * 40, None),
        ("0" * 40, "sha256:" + ("a" * 64)),
    ),
    ids=("wrong-genesis-parent", "unexpected-prior-root"),
)
def test_sync_rejects_a_noncanonical_genesis_bundle(
    state_parent_commit_sha: str,
    prior_root_digest: str | None,
) -> None:
    """The store must not create an invalid initial state ref itself."""

    module = _state_module()
    remote = _StateRemote(module, None)

    with pytest.raises(module.StateIntegrityFailure):
        module.StateBranchStore(remote).sync(
            _bundle(
                module,
                parent=state_parent_commit_sha,
                prior_root_digest=prior_root_digest,
            ),
            observed_head=None,
        )

    assert remote.writes == []


def test_restore_keeps_complete_state_history_reachable_beyond_256_links() -> None:
    """No hidden depth cap may turn the no-pruning state history into an outage."""

    module = _state_module()
    remote = _StateRemote(module, None)
    current_bundle = _bundle(module, parent="0" * 40)
    current_commit = _inject_state_bundle(remote, current_bundle, parents=())
    remote.create_state_ref(current_commit)
    for ordinal in range(257):
        current_bundle = _bundle(
            module,
            parent=current_commit,
            prior_root_digest=current_bundle.root.root_digest,
            pipeline_bytes=(
                b"SQLite format 3\x00state-history-" + str(ordinal).encode("ascii")
            ),
        )
        current_commit = _inject_state_bundle(
            remote,
            current_bundle,
            parents=(current_commit,),
        )
        remote.update_state_ref(current_commit, force=False)

    restored = module.StateBranchStore(remote).restore()

    assert restored.observed_head == current_commit
    assert restored.bundle is not None
    assert restored.bundle.root == current_bundle.root


def test_external_anchor_binds_and_bounds_a_state_restore() -> None:
    """A protected exact anchor may bound a descendant proof, never a bare root."""

    module = _state_module()
    genesis = "4" * 40
    remote = _StateRemote(module, genesis)
    store = module.StateBranchStore(remote)
    anchor_bundle = _bundle(
        module,
        parent=genesis,
        prior_root_digest=_initial_root(remote),
    )
    anchor_sync = store.sync(anchor_bundle, observed_head=genesis)
    child_bundle = _bundle(
        module,
        parent=anchor_sync.commit_sha,
        prior_root_digest=anchor_bundle.root.root_digest,
    )
    child_sync = store.sync(child_bundle, observed_head=anchor_sync.commit_sha)
    grandchild_bundle = _bundle(
        module,
        parent=child_sync.commit_sha,
        prior_root_digest=child_bundle.root.root_digest,
    )
    grandchild_sync = store.sync(
        grandchild_bundle,
        observed_head=child_sync.commit_sha,
    )

    original_genesis = remote.commits[genesis]
    remote.commits[genesis] = module.StateCommitObservation(
        sha=original_genesis.sha,
        tree_sha=original_genesis.tree_sha,
        parents=original_genesis.parents,
        message="foreign historical state",
    )
    anchor = module.StateLineageAnchor(
        commit_sha=anchor_sync.commit_sha,
        root_digest=anchor_bundle.root.root_digest,
        max_hops=3,
    )

    successor_bundle = _bundle(
        module,
        parent=grandchild_sync.commit_sha,
        prior_root_digest=grandchild_bundle.root.root_digest,
    )
    successor_sync = module.StateBranchStore(remote).sync(
        successor_bundle,
        observed_head=grandchild_sync.commit_sha,
        lineage_anchor=anchor,
    )

    with pytest.raises(module.StateIntegrityFailure):
        module.StateBranchStore(remote).restore_commit(successor_sync.commit_sha)
    restored = module.StateBranchStore(remote).restore_commit(
        successor_sync.commit_sha,
        lineage_anchor=anchor,
    )
    assert restored.root == successor_bundle.root
    with pytest.raises(module.StateIntegrityFailure):
        module.StateBranchStore(remote).restore_commit(
            successor_sync.commit_sha,
            lineage_anchor=module.StateLineageAnchor(
                commit_sha=anchor_sync.commit_sha,
                root_digest=anchor_bundle.root.root_digest,
                max_hops=2,
            ),
        )

    replacement_bundle = _bundle(module, parent="0" * 40)
    replacement = _inject_state_bundle(remote, replacement_bundle, parents=())
    remote.update_state_ref(replacement, force=False)
    with pytest.raises(module.StateIntegrityFailure):
        module.StateBranchStore(remote).restore(lineage_anchor=anchor)


def test_restore_commit_verifies_exact_immutable_commit_not_current_ref() -> None:
    module = _state_module()
    remote = _StateRemote(module, "4" * 40)
    store = module.StateBranchStore(remote)
    first_bundle = _bundle(
        module,
        parent="4" * 40,
        prior_root_digest=_initial_root(remote),
    )
    first = store.sync(first_bundle, observed_head="4" * 40)
    second_bundle = _bundle(
        module,
        parent=first.commit_sha,
        prior_root_digest=first_bundle.root.root_digest,
        object_count=2,
    )
    store.sync(second_bundle, observed_head=first.commit_sha)

    restored = store.restore_commit(first.commit_sha)

    assert restored.root.root_digest == first_bundle.root.root_digest
    assert restored.root.state_parent_commit_sha == "4" * 40
    assert remote.head != first.commit_sha


@pytest.mark.parametrize(
    "prior_root_digest",
    (None, "sha256:" + ("f" * 64)),
    ids=("missing", "wrong"),
)
def test_sync_rejects_child_whose_prior_root_does_not_bind_the_state_parent(
    prior_root_digest: str | None,
) -> None:
    """A non-genesis child cannot sever or forge the immutable root chain."""

    module = _state_module()
    remote = _StateRemote(module, "4" * 40)
    store = module.StateBranchStore(remote)
    parent_bundle = _bundle(
        module,
        parent="4" * 40,
        prior_root_digest=_initial_root(remote),
    )
    parent = store.sync(parent_bundle, observed_head="4" * 40)
    malformed_child = _bundle(
        module,
        parent=parent.commit_sha,
        prior_root_digest=prior_root_digest,
    )

    with pytest.raises(module.StateBranchConflict):
        store.sync(malformed_child, observed_head=parent.commit_sha)

    assert remote.head == parent.commit_sha


@pytest.mark.parametrize(
    "prior_root_digest",
    (None, "sha256:" + ("f" * 64)),
    ids=("missing", "wrong"),
)
def test_restore_rejects_injected_child_whose_prior_root_does_not_bind_parent(
    prior_root_digest: str | None,
) -> None:
    """A direct remote ref mutation cannot bypass the state-root lineage check."""

    module = _state_module()
    remote = _StateRemote(module, "4" * 40)
    store = module.StateBranchStore(remote)
    parent_bundle = _bundle(
        module,
        parent="4" * 40,
        prior_root_digest=_initial_root(remote),
    )
    parent = store.sync(parent_bundle, observed_head="4" * 40)
    malformed_child = _bundle(
        module,
        parent=parent.commit_sha,
        prior_root_digest=prior_root_digest,
    )
    entries = [
        {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": remote.create_blob(content),
        }
        for path, content in sorted(malformed_child.content_by_path().items())
    ]
    tree_sha = remote.create_tree(entries)
    child_sha = remote.create_commit(
        module._state_commit_message(malformed_child.root.root_digest),
        tree_sha,
        (parent.commit_sha,),
    )
    remote.update_state_ref(child_sha, force=False)

    with pytest.raises(module.StateIntegrityFailure):
        store.restore()


def test_inspect_commit_root_reads_only_bounded_lineage_metadata() -> None:
    """Lineage proof must not restore database or owned-object bodies per commit."""

    module = _state_module()

    class CountingRemote(_StateRemote):
        def __init__(self) -> None:
            super().__init__(module, "4" * 40)
            self.blob_gets: list[str] = []

        def get_blob(self, sha: str) -> bytes:
            self.blob_gets.append(sha)
            return super().get_blob(sha)

    remote = CountingRemote()
    store = module.StateBranchStore(remote)
    bundle = _bundle(
        module,
        parent="4" * 40,
        object_count=12,
        prior_root_digest=_initial_root(remote),
    )
    synchronized = store.sync(bundle, observed_head="4" * 40)
    remote.blob_gets.clear()

    observation = store.inspect_commit_root(synchronized.commit_sha)

    assert observation.commit.sha == synchronized.commit_sha
    assert observation.root == bundle.root
    assert observation.object_digests == tuple(
        item.object_digest for item in bundle.root.objects
    )
    assert remote.blob_gets == [
        module._git_blob_id(
            canonical_json_bytes(
                bundle.root.model_dump(mode="json", exclude_none=False)
            )
        )
    ]


def test_split_restore_uses_separate_budgets_for_lineage_and_payload() -> None:
    """The acceptance preflight keeps each immutable-read phase bounded."""

    module = _state_module()
    remote = _StateRemote(module, "4" * 40)
    store = module.StateBranchStore(remote)
    bundle = _bundle(
        module,
        parent="4" * 40,
        object_count=2,
        prior_root_digest=_initial_root(remote),
    )
    synchronized = store.sync(bundle, observed_head="4" * 40)
    lineage_budget = module.ResolverReadBudget()
    payload_budget = module.ResolverReadBudget.payload_phase()

    restored = store.restore_with_split_budgets(
        lineage_read_budget=lineage_budget,
        payload_read_budget=payload_budget,
    )

    assert restored.status == "verified"
    assert restored.observed_head == synchronized.commit_sha
    assert restored.bundle is not None
    assert restored.bundle.root == bundle.root
    assert lineage_budget.request_count > 0
    assert payload_budget.request_count > 0


def test_split_restore_rejects_budgets_in_the_wrong_phase_slot() -> None:
    module = _state_module()
    remote = _StateRemote(module, "4" * 40)
    store = module.StateBranchStore(remote)

    with pytest.raises(module.StateIntegrityFailure):
        store.restore_with_split_budgets(
            lineage_read_budget=module.ResolverReadBudget.payload_phase(),
            payload_read_budget=module.ResolverReadBudget.payload_phase(),
        )
    with pytest.raises(module.StateIntegrityFailure):
        store.restore_with_split_budgets(
            lineage_read_budget=module.ResolverReadBudget(phase="lineage"),
            payload_read_budget=module.ResolverReadBudget(),
        )


def test_ordinary_restore_rejects_the_payload_phase_budget() -> None:
    module = _state_module()
    remote = _StateRemote(module, "4" * 40)
    store = module.StateBranchStore(remote)

    with pytest.raises(module.StateIntegrityFailure):
        store.restore(read_budget=module.ResolverReadBudget.payload_phase())


def test_split_restore_labels_payload_budget_failure_without_details() -> None:
    """A bounded payload failure is classified without exposing remote text."""

    module = _state_module()
    remote = _StateRemote(module, "4" * 40)
    store = module.StateBranchStore(remote)
    bundle = _bundle(
        module,
        parent="4" * 40,
        object_count=2,
        prior_root_digest=_initial_root(remote),
    )
    store.sync(bundle, observed_head="4" * 40)

    with pytest.raises(module.StateRestorePhaseFailure) as caught:
        store.restore_with_split_budgets(
            lineage_read_budget=module.ResolverReadBudget(),
            payload_read_budget=module.ResolverReadBudget.payload_phase(max_requests=1),
        )

    assert caught.value.phase == "payload"
    assert caught.value.code == "state_integrity_failure"
    assert "payload" in str(caught.value)
    assert "github" not in repr(caught.value).lower()


@pytest.mark.parametrize(
    "mutation",
    (None, "missing", "extra", "wrong_sha", "duplicate", "wrong_mode"),
)
def test_sync_reads_only_the_parent_root_metadata_not_owned_payload_bodies(
    mutation: str | None,
) -> None:
    module = _state_module()

    class ExactTreeRemote(_StateRemote):
        def __init__(self) -> None:
            super().__init__(module, "4" * 40)
            self.body_gets = 0
            parent = self.commits["4" * 40]
            self.parent_root_blob = next(
                entry.sha
                for entry in self.trees[parent.tree_sha]
                if entry.path == "state/root.json"
            )
            self.root_gets = 0

        def update_state_ref(self, sha: str, *, force: bool) -> object:
            response = super().update_state_ref(sha, force=force)
            tree_sha = self.commits[sha].tree_sha
            entries = list(self.trees[tree_sha])
            if mutation == "missing":
                entries.pop()
            elif mutation == "extra":
                content = canonical_json_bytes({"extra": True})
                digest = sha256_digest({"extra": True}).removeprefix(
                    "sha256:"
                )
                blob_sha = module._git_blob_id(content)
                self.blobs[blob_sha] = content
                entries.append(
                    module.StateTreeEntry(
                        path=(
                            "state/objects/sha256/"
                            f"{digest[:2]}/{digest}.json"
                        ),
                        sha=blob_sha,
                        mode="100644",
                        size=len(content),
                    )
                )
            elif mutation == "wrong_sha":
                entries[0] = module.StateTreeEntry(
                    path=entries[0].path,
                    sha="9" * 40,
                    mode=entries[0].mode,
                    size=entries[0].size,
                )
            elif mutation == "duplicate":
                entries.append(entries[0])
            elif mutation == "wrong_mode":
                entries[0] = module.StateTreeEntry(
                    path=entries[0].path,
                    sha=entries[0].sha,
                    mode="100755",
                    size=entries[0].size,
                )
            self.trees[tree_sha] = tuple(entries)
            return response

        def get_blob(self, sha: str) -> bytes:
            if sha == self.parent_root_blob:
                self.root_gets += 1
                return super().get_blob(sha)
            self.body_gets += 1
            raise AssertionError(
                "sync may read only parent-root metadata, never owned payload bodies"
            )

    remote = ExactTreeRemote()
    store = module.StateBranchStore(remote)
    bundle = _bundle(
        module,
        parent="4" * 40,
        object_count=2,
        prior_root_digest=_initial_root(remote),
    )

    if mutation is None:
        synchronized = store.sync(bundle, observed_head="4" * 40)
        assert synchronized.status == "verified"
    else:
        with pytest.raises(module.StateBranchConflict):
            store.sync(bundle, observed_head="4" * 40)
    assert remote.root_gets == 1
    assert remote.body_gets == 0


def test_one_hundred_discovery_syncs_have_constant_metadata_request_cost() -> None:
    module = _state_module()

    class CountingRemote(_StateRemote):
        def __init__(self) -> None:
            super().__init__(module, "4" * 40)
            self.calls: dict[str, int] = {}

        def count(self, name: str) -> None:
            self.calls[name] = self.calls.get(name, 0) + 1

        def get_state_ref(self) -> object:
            self.count("get_state_ref")
            return super().get_state_ref()

        def get_commit(self, sha: str) -> object:
            self.count("get_commit")
            return super().get_commit(sha)

        def get_tree(self, sha: str) -> tuple[object, ...]:
            self.count("get_tree")
            return super().get_tree(sha)

        def get_blob(self, sha: str) -> bytes:
            self.count("get_blob")
            return super().get_blob(sha)

        def create_blob(self, content: bytes) -> str:
            self.count("create_blob")
            return super().create_blob(content)

        def create_tree(self, entries: list[dict[str, object]]) -> str:
            self.count("create_tree")
            return super().create_tree(entries)

        def create_commit(
            self,
            message: str,
            tree: str,
            parents: tuple[str, ...],
        ) -> str:
            self.count("create_commit")
            return super().create_commit(message, tree, parents)

        def update_state_ref(self, sha: str, *, force: bool) -> object:
            self.count("update_state_ref")
            return super().update_state_ref(sha, force=force)

    remote = CountingRemote()
    store = module.StateBranchStore(remote)
    bundle = _bundle(
        module,
        parent="4" * 40,
        prior_root_digest=_initial_root(remote),
    )
    synchronized = store.sync(bundle, observed_head="4" * 40)
    remote.calls.clear()

    for object_count in range(1, 101):
        bundle = _bundle(
            module,
            parent=synchronized.commit_sha,
            object_count=object_count,
            prior_root_digest=bundle.root.root_digest,
        )
        synchronized = store.sync(
            bundle,
            observed_head=synchronized.commit_sha,
        )

    assert remote.calls == {
        "get_state_ref": 200,
        "get_commit": 200,
        "get_tree": 200,
        "get_blob": 100,
        "create_blob": 200,
        "create_tree": 100,
        "create_commit": 100,
        "update_state_ref": 100,
    }
    assert sum(remote.calls.values()) == 1_200


def test_run_scoped_read_cache_survives_ephemeral_state_stores() -> None:
    """Production's per-checkpoint clients must not re-walk old state history."""

    module = _state_module()

    class CountingRemote(_StateRemote):
        def __init__(self) -> None:
            super().__init__(module, "4" * 40)
            self.calls: dict[str, int] = {}

        def count(self, name: str) -> None:
            self.calls[name] = self.calls.get(name, 0) + 1

        def get_state_ref(self) -> object:
            self.count("get_state_ref")
            return super().get_state_ref()

        def get_commit(self, sha: str) -> object:
            self.count("get_commit")
            return super().get_commit(sha)

        def get_tree(self, sha: str) -> tuple[object, ...]:
            self.count("get_tree")
            return super().get_tree(sha)

        def get_blob(self, sha: str) -> bytes:
            self.count("get_blob")
            return super().get_blob(sha)

        def create_blob(self, content: bytes) -> str:
            self.count("create_blob")
            return super().create_blob(content)

        def create_tree(self, entries: list[dict[str, object]]) -> str:
            self.count("create_tree")
            return super().create_tree(entries)

        def create_commit(
            self,
            message: str,
            tree: str,
            parents: tuple[str, ...],
        ) -> str:
            self.count("create_commit")
            return super().create_commit(message, tree, parents)

        def update_state_ref(self, sha: str, *, force: bool) -> object:
            self.count("update_state_ref")
            return super().update_state_ref(sha, force=force)

    remote = CountingRemote()
    cache = module.StateBranchReadCache()
    bundle = _bundle(
        module,
        parent="4" * 40,
        prior_root_digest=_initial_root(remote),
    )
    synchronized = module.StateBranchStore(remote, read_cache=cache).sync(
        bundle,
        observed_head="4" * 40,
    )
    remote.calls.clear()

    for object_count in range(1, 101):
        bundle = _bundle(
            module,
            parent=synchronized.commit_sha,
            object_count=object_count,
            prior_root_digest=bundle.root.root_digest,
        )
        synchronized = module.StateBranchStore(remote, read_cache=cache).sync(
            bundle,
            observed_head=synchronized.commit_sha,
        )

    assert remote.calls == {
        "get_state_ref": 200,
        "get_commit": 200,
        "get_tree": 200,
        "get_blob": 100,
        "create_blob": 200,
        "create_tree": 100,
        "create_commit": 100,
        "update_state_ref": 100,
    }
    assert sum(remote.calls.values()) == 1_200


def test_sync_reuses_unchanged_parent_blobs_below_content_creation_limit() -> None:
    module = _state_module()

    class ContentLimitedRemote(_StateRemote):
        def __init__(self, head: str) -> None:
            super().__init__(module, head)
            self.blob_creation_limit: int | None = None
            self.blob_creation_count = 0

        def create_blob(self, content: bytes) -> str:
            self.blob_creation_count += 1
            if (
                self.blob_creation_limit is not None
                and self.blob_creation_count > self.blob_creation_limit
            ):
                raise RuntimeError("synthetic content creation limit")
            return super().create_blob(content)

    remote = ContentLimitedRemote("4" * 40)
    parent_bundle = _bundle(
        module,
        parent="4" * 40,
        object_count=109,
        prior_root_digest=_initial_root(remote),
    )
    parent = module.StateBranchStore(remote).sync(
        parent_bundle,
        observed_head="4" * 40,
    )
    child_bundle = _bundle(
        module,
        parent=parent.commit_sha,
        object_count=135,
        prior_root_digest=parent_bundle.root.root_digest,
    )
    remote.blob_creation_count = 0
    remote.blob_creation_limit = 80
    remote.writes.clear()

    synchronized = module.StateBranchStore(remote).sync(
        child_bundle,
        observed_head=parent.commit_sha,
    )

    assert synchronized.status == "verified"
    assert remote.blob_creation_count == 27
    assert remote.writes.count("blob") == 27
    assert remote.writes[-1] == "update_ref"
    assert remote.force_values[-1] is False


def test_sync_rejects_invalid_parent_tree_before_blob_reuse() -> None:
    module = _state_module()
    observed_head = "4" * 40
    remote = _StateRemote(module, observed_head)
    parent = remote.commits[observed_head]
    remote.trees[parent.tree_sha] = (
        module.StateTreeEntry(
            path="state/unowned.json",
            sha="9" * 40,
            mode="100644",
            size=1,
        ),
    )

    with pytest.raises(module.StateBranchConflict):
        module.StateBranchStore(remote).sync(
            _bundle(
                module,
                parent=observed_head,
                prior_root_digest=_initial_root(remote),
            ),
            observed_head=observed_head,
        )

    assert remote.writes == []


@pytest.mark.parametrize("bootstrap", (False, True))
def test_sync_bootstrap_and_fast_forward_reread_exact_state(
    bootstrap: bool,
) -> None:
    module = _state_module()
    observed_head = None if bootstrap else "4" * 40
    remote = _StateRemote(module, observed_head)

    result = module.StateBranchStore(remote).sync(
        _bundle(
            module,
            parent=observed_head or "0" * 40,
            prior_root_digest=(None if observed_head is None else _initial_root(remote)),
        ),
        observed_head=observed_head,
    )

    assert result.status == "verified"
    assert result.previous_head == observed_head
    assert remote.commits[result.commit_sha].parents == (
        () if bootstrap else (observed_head,)
    )
    assert remote.force_values == ([] if bootstrap else [False])
    assert remote.writes[-1] == ("create_ref" if bootstrap else "update_ref")


def test_restore_records_whether_the_current_state_is_genesis() -> None:
    module = _state_module()
    remote = _StateRemote(module, None)
    store = module.StateBranchStore(remote)
    synchronized = store.sync(
        _bundle(module, parent="0" * 40),
        observed_head=None,
    )

    restored = store.restore()

    assert restored.observed_head == synchronized.commit_sha
    assert restored.is_genesis is True


def test_post_cas_uncertainty_reconciles_only_the_exact_successor() -> None:
    """A lost post-CAS read is recoverable only from the exact child commit."""

    module = _state_module()
    observed_head = "4" * 40

    class LostFirstPostCasReadRemote(_StateRemote):
        def __init__(self) -> None:
            super().__init__(module, observed_head)
            self._lose_next_post_cas_ref_read = False

        def update_state_ref(self, sha: str, *, force: bool) -> object:
            response = super().update_state_ref(sha, force=force)
            self._lose_next_post_cas_ref_read = True
            return response

        def get_state_ref(self) -> object:
            if self._lose_next_post_cas_ref_read:
                self._lose_next_post_cas_ref_read = False
                raise module.SafeFailure(module.ErrorCode.STAGE_TRANSIENT_FAILURE)
            return super().get_state_ref()

    remote = LostFirstPostCasReadRemote()
    bundle = _bundle(
        module,
        parent=observed_head,
        object_count=1,
        prior_root_digest=_initial_root(remote),
    )
    store = module.StateBranchStore(remote)

    with pytest.raises(module.StateBranchPostCasUncertain) as raised:
        store.sync(bundle, observed_head)

    recovered = store.reconcile_post_cas_uncertainty(
        raised.value,
        bundle,
        observed_head,
    )

    assert recovered.status == "verified"
    assert recovered.previous_head == observed_head
    assert recovered.commit_sha == raised.value.candidate_commit_sha
    assert recovered.tree_sha == raised.value.candidate_tree_sha
    assert recovered.root_digest == bundle.root.root_digest


@pytest.mark.parametrize("mutation", ("head", "parent", "bundle"))
def test_post_cas_reconciliation_rejects_every_nonexact_successor(
    mutation: str,
) -> None:
    """A post-CAS recovery never turns a nearby or altered child into success."""

    module = _state_module()
    observed_head = "4" * 40

    class LostFirstPostCasReadRemote(_StateRemote):
        def __init__(self) -> None:
            super().__init__(module, observed_head)
            self._lose_next_post_cas_ref_read = False

        def update_state_ref(self, sha: str, *, force: bool) -> object:
            response = super().update_state_ref(sha, force=force)
            self._lose_next_post_cas_ref_read = True
            return response

        def get_state_ref(self) -> object:
            if self._lose_next_post_cas_ref_read:
                self._lose_next_post_cas_ref_read = False
                raise module.SafeFailure(module.ErrorCode.STAGE_TRANSIENT_FAILURE)
            return super().get_state_ref()

    remote = LostFirstPostCasReadRemote()
    bundle = _bundle(
        module,
        parent=observed_head,
        object_count=1,
        prior_root_digest=_initial_root(remote),
    )
    store = module.StateBranchStore(remote)

    with pytest.raises(module.StateBranchPostCasUncertain) as raised:
        store.sync(bundle, observed_head)

    candidate = raised.value.candidate_commit_sha
    if mutation == "head":
        remote.head = observed_head
    elif mutation == "parent":
        commit = remote.commits[candidate]
        remote.commits[candidate] = module.StateCommitObservation(
            sha=commit.sha,
            tree_sha=commit.tree_sha,
            parents=("5" * 40,),
            message=commit.message,
        )
    else:
        alternate = _bundle(
            module,
            parent=observed_head,
            object_count=2,
            prior_root_digest=_initial_root(remote),
        )
        alternate_files = alternate.content_by_path()
        for content in alternate_files.values():
            remote.blobs[module._git_blob_id(content)] = content
        alternate_tree = remote._sha()
        remote.trees[alternate_tree] = tuple(
            module.StateTreeEntry(
                path=path,
                sha=module._git_blob_id(content),
                mode="100644",
                size=len(content),
            )
            for path, content in sorted(alternate_files.items())
        )
        remote.commits[candidate] = module.StateCommitObservation(
            sha=candidate,
            tree_sha=alternate_tree,
            parents=(observed_head,),
            message=module._state_commit_message(alternate.root.root_digest),
        )

    with pytest.raises((module.StateBranchConflict, module.StateIntegrityFailure)):
        store.reconcile_post_cas_uncertainty(
            raised.value,
            bundle,
            observed_head,
        )


def test_post_cas_reconciliation_does_not_wrap_unexpected_programming_errors() -> None:
    """Only known remote-verification failures may enter reconciliation."""

    module = _state_module()
    observed_head = "4" * 40

    class UnexpectedPostCasReadRemote(_StateRemote):
        def __init__(self) -> None:
            super().__init__(module, observed_head)
            self._raise_after_cas = False

        def update_state_ref(self, sha: str, *, force: bool) -> object:
            response = super().update_state_ref(sha, force=force)
            self._raise_after_cas = True
            return response

        def get_state_ref(self) -> object:
            if self._raise_after_cas:
                raise RuntimeError("synthetic unexpected post-CAS error")
            return super().get_state_ref()

    remote = UnexpectedPostCasReadRemote()
    with pytest.raises(RuntimeError, match="synthetic unexpected"):
        module.StateBranchStore(remote).sync(
            _bundle(
                module,
                parent=observed_head,
                prior_root_digest=_initial_root(remote),
            ),
            observed_head,
        )


def test_sync_secret_canary_fails_before_first_blob_creation() -> None:
    module = _state_module()
    observed_head = "4" * 40
    remote = _StateRemote(module, observed_head)
    bundle = _bundle(
        module,
        parent=observed_head,
        pipeline_bytes=b"SQLite format 3\x00github_pat_STATE_BRANCH_CANARY",
        prior_root_digest=_initial_root(remote),
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
