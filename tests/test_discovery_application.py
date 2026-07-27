"""Wave-0 RED contract for the unprotected multi-candidate controller."""

from __future__ import annotations

import ast
import importlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillscout.application.ports import (
    CandidateSourceUnavailable,
    ErrorCode,
    SafeFailure,
)
from skillscout.domain.canonical import sha256_digest


ROOT = Path(__file__).resolve().parents[1]
APPLICATION_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-discovery-application-missing",
)

BUSINESS_OUTCOMES = (
    "filter_rejected",
    "no_workflow",
    "qualification_rejected",
    "validation_rejected",
    "review_rejected",
    "completed_reuse",
    "eligible_local_candidate",
)
CONTINUABLE_OUTCOMES = BUSINESS_OUTCOMES + ("semantic_outcome_unknown",)
FATAL_OUTCOMES = (
    "state_integrity_conflict",
    "permanent_failure",
)


def _module():
    return importlib.import_module("skillscout.application.discovery")


def test_outcome_matrix_keeps_business_quarantine_and_fatal_classes_distinct() -> None:
    assert len(set(BUSINESS_OUTCOMES)) == len(BUSINESS_OUTCOMES)
    assert set(CONTINUABLE_OUTCOMES).isdisjoint(FATAL_OUTCOMES)
    assert "confirmed_retryable" not in CONTINUABLE_OUTCOMES
    assert "semantic_outcome_unknown" in CONTINUABLE_OUTCOMES


def test_crash_matrix_names_every_non_refundable_durability_seam() -> None:
    seams = (
        "before_page_dedup",
        "after_page_dedup",
        "before_discovery_reservation",
        "after_discovery_reservation",
        "before_semantic_attempt_start",
        "after_semantic_attempt_start",
        "before_semantic_result",
        "after_semantic_result",
        "before_candidate_terminal",
        "after_candidate_terminal",
        "before_final_handoff_sync",
        "after_final_handoff_sync",
    )
    assert len(seams) == len(set(seams))
    assert all(
        seam.startswith(("before_", "after_"))
        for seam in seams
    )


def test_discovery_dependency_surface_has_no_publication_authority() -> None:
    module = _module()
    dependencies = getattr(module, "DiscoveryDependencies")
    fields = set(getattr(dependencies, "__annotations__", {}))
    assert {
        "search_factory",
        "operations_store_factory",
        "state_restore",
        "durability_barrier",
        "phase2_factory",
        "phase3_factory",
    } <= fields
    forbidden = {
        "publication",
        "publisher",
        "catalog",
        "catalog_token",
        "publication_factory",
        "remote_publisher",
    }
    assert fields.isdisjoint(forbidden)


def test_discovery_source_imports_phase2_phase3_but_never_phase4() -> None:
    module = _module()
    source_path = Path(inspect.getsourcefile(module) or "")
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "skillscout.application.pipeline" in imported
    assert "skillscout.application.phase3" in imported
    assert "skillscout.application.publication" not in imported
    literals = {
        node.value.casefold()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any(
        marker in literal
        for marker in ("github_publish", "catalog token", "publicationapplication")
        for literal in literals
    )


def test_application_contract_exposes_bounded_result_and_run_only() -> None:
    module = _module()
    application = getattr(module, "DiscoveryApplication")
    result = getattr(module, "DiscoveryApplicationResult")
    assert tuple(inspect.signature(application.run).parameters) in (
        ("self",),
        ("self", "authority"),
    )
    fields = set(getattr(result, "model_fields", {})) | set(
        getattr(result, "__annotations__", {})
    )
    assert {
        "run_id",
        "state_root_digest",
        "state_commit_sha",
        "eligible_candidates",
    } <= fields
    assert fields.isdisjoint(
        {
            "publication_admission",
            "publication_intent",
            "catalog_token",
            "repository_text",
            "provider_response",
        }
    )


def test_three_workflow_repository_uses_one_semantic_reservation() -> None:
    module = _module()
    scenario = module.DiscoveryScenario(
        repository_id=910001,
        workflows=(
            module.WorkflowScenario("eligible"),
            module.WorkflowScenario("qualification_rejected"),
            module.WorkflowScenario("review_rejected"),
        ),
    )
    result = module.evaluate_discovery_scenario(scenario)
    assert result.semantic_reservation_count == 1
    assert result.workflow_outcomes == (
        "eligible_local_candidate",
        "qualification_rejected",
        "review_rejected",
    )
    assert len(set(result.workflow_authority_digests)) == 3


@pytest.mark.parametrize(
    "outcome",
    CONTINUABLE_OUTCOMES,
)
def test_business_and_quarantine_outcomes_continue_later_candidates(
    outcome: str,
) -> None:
    module = _module()
    result = module.evaluate_discovery_scenario(
        module.DiscoveryScenario(
            repository_id=910001,
            terminal=outcome,
            later_repository_id=910002,
        )
    )
    assert result.processed_repository_ids == (910001, 910002)
    if outcome == "semantic_outcome_unknown":
        assert result.provider_request_count == 1
        assert result.automatic_replay_count == 0


@pytest.mark.parametrize("outcome", FATAL_OUTCOMES)
def test_integrity_and_permanent_failures_stop_the_run(outcome: str) -> None:
    module = _module()
    result = module.evaluate_discovery_scenario(
        module.DiscoveryScenario(
            repository_id=910001,
            terminal=outcome,
            later_repository_id=910002,
        )
    )
    assert result.processed_repository_ids == (910001,)
    assert result.run_status in {"integrity_conflict", "permanent_failure"}


def test_fatal_summary_counts_only_durably_reserved_candidates() -> None:
    source = inspect.getsource(
        _module().DiscoveryApplication._run_operations_store
    )
    assert (
        'summary_values["selected_candidate_count"] = '
        "len(durable_discovery_reservations)"
    ) in source
    assert (
        "durable_discovery_reservations[\n"
        "                candidate.repository.repository_id\n"
        "            ] = reservation"
    ) in source


def test_unknown_outcome_consumes_once_without_automatic_replay() -> None:
    module = _module()
    result = module.evaluate_discovery_scenario(
        module.DiscoveryScenario(
            repository_id=910001,
            workflows=(module.WorkflowScenario("semantic_outcome_unknown"),),
            later_repository_id=910002,
        )
    )
    assert result.semantic_reservation_count == 1
    assert result.provider_request_count == 1
    assert result.automatic_replay_count == 0
    assert result.processed_repository_ids == (910001, 910002)
    assert result.run_status == "completed_degraded"


def test_eligible_handoff_locator_is_bounded_and_non_authorizing() -> None:
    module = _module()
    authority = "sha256:" + ("a" * 64)
    identity = "sha256:" + ("b" * 64)
    locator = module.eligible_candidate_locator(
        authority_digest=authority,
        workflow_identity_digest=identity,
    )
    assert locator.locator == (
        "state/objects/sha256/aa/" + ("a" * 64) + ".json"
    )
    assert set(locator.__annotations__) == {
        "locator",
        "authority_digest",
        "workflow_identity_digest",
    }


def test_forbidden_publication_factory_cannot_be_offered_to_dependencies() -> None:
    module = _module()
    calls: list[str] = []

    def forbidden() -> object:
        calls.append("publication_construct")
        return object()

    with pytest.raises(TypeError):
        module.DiscoveryDependencies(  # type: ignore[call-arg]
            search_factory=lambda: object(),
            operations_store_factory=lambda: object(),
            state_restore=lambda: object(),
            durability_barrier=object(),
            phase2_factory=lambda: object(),
            phase3_factory=lambda: object(),
            publication_factory=forbidden,
        )
    assert calls == []


def test_unexpected_health_failure_collapses_without_raw_exception() -> None:
    module = _module()

    class Operations:
        def run_discovery(self, **_kwargs: object) -> object:
            raise RuntimeError("SECRET_EXCEPTION_CANARY")

    dependencies = module.DiscoveryDependencies(
        search_factory=lambda: object(),
        operations_store_factory=Operations,
        state_restore=lambda: object(),
        durability_barrier=object(),
        phase2_factory=lambda: object(),
        phase3_factory=lambda: object(),
    )
    with pytest.raises(SafeFailure) as failure:
        module.DiscoveryApplication(dependencies).run()
    assert failure.value.code is ErrorCode.PIPELINE_INTERRUPTED
    assert "SECRET_EXCEPTION_CANARY" not in str(failure.value)


def _runtime_config(module, tmp_path: Path):
    query_path = tmp_path / "discovery-queries-v1.json"
    query_path.write_bytes(
        (ROOT / "config" / "discovery-queries-v1.json").read_bytes()
    )
    return module.load_discovery_runtime_config(
        state_repository_id="910001",
        state_repository_full_name="skillscout/state",
        state_ref="refs/heads/skillscout-state",
        query_set_path=query_path,
        pipeline_state=Path("state/databases/pipeline.sqlite3"),
        operations_state=Path("state/databases/operations.sqlite3"),
        publication_state=Path("state/databases/publication.sqlite3"),
        semantic_provider="openai",
        extractor_model_id="gpt-5.6-terra",
        generator_model_id="gpt-5.6-terra",
        reviewer_model_id="gpt-5.6-terra",
        initial_state_root_digest="sha256:" + ("1" * 64),
    )


def test_bootstrap_rejects_invalid_config_before_credentials_or_state(
    tmp_path: Path,
) -> None:
    module = importlib.import_module("skillscout.bootstrap")
    effects: list[str] = []

    class Environ(dict[str, str]):
        def __getitem__(self, key: str) -> str:
            effects.append(f"credential:{key}")
            return super().__getitem__(key)

    query_path = tmp_path / "queries.json"
    query_path.write_text(json.dumps({"schema_version": "wrong"}))
    with pytest.raises(ValueError):
        module.load_discovery_runtime_config(
            state_repository_id="not-an-id",
            state_repository_full_name="skillscout/state",
            state_ref="refs/heads/skillscout-state",
            query_set_path=query_path,
            pipeline_state=Path("state/databases/pipeline.sqlite3"),
            operations_state=Path("state/databases/operations.sqlite3"),
            publication_state=Path("state/databases/publication.sqlite3"),
            semantic_provider="openai",
            extractor_model_id="gpt-5.6-terra",
            generator_model_id="gpt-5.6-terra",
            reviewer_model_id="gpt-5.6-terra",
            initial_state_root_digest="sha256:" + ("1" * 64),
            environ=Environ(),
        )
    assert effects == []
    assert not (tmp_path / "state.sqlite3").exists()


def test_bootstrap_keeps_source_and_state_credentials_lazy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("skillscout.bootstrap")
    config = _runtime_config(module, tmp_path)
    events: list[str] = []

    class Environ(dict[str, str]):
        def __getitem__(self, key: str) -> str:
            events.append(f"credential:{key}")
            return "late-bound"

        def get(self, key: str, default=None):
            if key.startswith("SKILLSCOUT_CATALOG_"):
                events.append(f"catalog:{key}")
            return super().get(key, default)

    class Search:
        def __init__(self, *, token: str) -> None:
            events.append(f"search:{token}")

        def close(self) -> None:
            events.append("search:close")

    class StateClient:
        def __init__(self, **kwargs: object) -> None:
            events.append(f"state:{kwargs['token']}")

        def close(self) -> None:
            events.append("state:close")

    class StateStore:
        def __init__(self, remote: object) -> None:
            self.remote = remote

        def restore(self) -> object:
            events.append("state:restore")
            return object()

    monkeypatch.setattr("skillscout.adapters.github.GitHubReadClient", Search)
    monkeypatch.setattr(
        "skillscout.adapters.state_branch.StateBranchClient", StateClient
    )
    monkeypatch.setattr(
        "skillscout.adapters.state_branch.StateBranchStore", StateStore
    )

    application = module.build_discovery_application(
        config,
        environ=Environ(),
        operations_store_factory=lambda: object(),
        phase2_factory=lambda **_kwargs: object(),
        phase3_factory=lambda **_kwargs: object(),
    )
    assert events == []
    dependencies = application._dependencies
    search = dependencies.search_factory()
    search.close()
    dependencies.state_restore()
    assert events == [
        "credential:SKILLSCOUT_SOURCE_GITHUB_TOKEN",
        "search:late-bound",
        "search:close",
        "credential:SKILLSCOUT_STATE_GITHUB_TOKEN",
        "state:late-bound",
        "state:restore",
        "state:close",
    ]


def test_real_bootstrap_and_operations_store_complete_empty_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    discovery = importlib.import_module("skillscout.domain.discovery")
    monkeypatch.chdir(tmp_path)
    config = _runtime_config(bootstrap, tmp_path)
    calls: list[str] = []

    class Search:
        def __init__(self, *, token: str) -> None:
            assert token == "source-token"

        def search_repositories(
            self,
            *,
            query_set,
            discovery_run_authority_digest: str,
            query_ordinal: int,
            page: int,
        ):
            calls.append(f"search:{query_ordinal}:{page}")
            query = query_set.queries[query_ordinal - 1]
            values = {
                "schema_version": "search-page-observation-v1",
                "discovery_run_authority_digest": discovery_run_authority_digest,
                "query_set_version": query_set.query_set_version,
                "query_set_digest": query_set.query_set_digest,
                "query_id": query.query_id,
                "query_ordinal": query_ordinal,
                "query_text": query.query_text,
                "sort": query_set.sort,
                "order": query_set.order,
                "page": page,
                "per_page": query_set.per_page,
                "next_page": None,
                "total_count": 0,
                "incomplete_results": False,
                "item_count": 0,
                "request_id": f"request-{query_ordinal}",
                "rate_limit": {
                    "limit": 10,
                    "remaining": 9,
                    "used": 1,
                    "reset_epoch": 1,
                    "resource": "search",
                },
            }
            return (
                discovery.SearchPageObservationV1(
                    **values,
                    observation_digest=sha256_digest(values),
                ),
                (),
            )

        def close(self) -> None:
            calls.append("search:close")

    class StateClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    class StateStore:
        def __init__(self, _remote: object) -> None:
            pass

        def restore(self):
            return SimpleNamespace(
                status="verified",
                observed_head="b" * 40,
                bundle=SimpleNamespace(
                    root=SimpleNamespace(
                        root_digest=config.initial_state_root_digest
                    )
                ),
            )

    monkeypatch.setattr("skillscout.adapters.github.GitHubReadClient", Search)
    monkeypatch.setattr(
        "skillscout.adapters.state_branch.StateBranchClient", StateClient
    )
    monkeypatch.setattr(
        "skillscout.adapters.state_branch.StateBranchStore", StateStore
    )

    def sync_discovery(self, **_kwargs: object):
        calls.append("state:sync")
        return SimpleNamespace(
            commit_sha="c" * 40,
            root_digest="sha256:" + ("d" * 64),
        )

    monkeypatch.setattr(
        bootstrap._LateStateDurabilityBarrier,
        "sync_discovery",
        sync_discovery,
        raising=False,
    )
    application = bootstrap.build_discovery_application(
        config,
        environ={
            "SKILLSCOUT_SOURCE_GITHUB_TOKEN": "source-token",
            "SKILLSCOUT_STATE_GITHUB_TOKEN": "state-token",
        },
    )
    result = application.run(bootstrap.discovery_run_authority(config))

    assert result.eligible_candidates == ()
    assert result.state_commit_sha == "c" * 40
    assert result.state_root_digest == "sha256:" + ("d" * 64)
    assert calls == [
        "search:1:1",
        "state:sync",
        "search:2:1",
        "state:sync",
        "search:3:1",
        "state:sync",
        "search:4:1",
        "state:sync",
        "search:close",
        "state:sync",
    ]
    assert Path("state/databases/operations.sqlite3").is_file()


@pytest.mark.parametrize(
    "mutation",
    (
        "valid",
        "type",
        "status",
        "previous_head",
        "commit",
        "tree",
        "root",
    ),
)
def test_late_discovery_barrier_accepts_strict_sync_receipt_without_second_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    operations_module = importlib.import_module(
        "skillscout.adapters.operations_state"
    )
    state_branch = importlib.import_module(
        "skillscout.adapters.state_branch"
    )
    monkeypatch.chdir(tmp_path)
    config = _runtime_config(bootstrap, tmp_path)
    sync_calls = 0
    restore_calls = 0

    class StateClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    class StateStore:
        def __init__(self, _remote: object) -> None:
            self.bundle = None

        def sync(self, bundle, observed_head: str):
            nonlocal sync_calls
            sync_calls += 1
            assert observed_head == "a" * 40
            self.bundle = bundle
            receipt = state_branch.StateSyncObservation(
                status="absent" if mutation == "status" else "verified",
                previous_head=(
                    "c" * 40
                    if mutation == "previous_head"
                    else observed_head
                ),
                commit_sha=("z" if mutation == "commit" else "b") * 40,
                tree_sha=("z" if mutation == "tree" else "c") * 40,
                root_digest=(
                    "sha256:" + ("f" * 64)
                    if mutation == "root"
                    else bundle.root.root_digest
                ),
            )
            if mutation == "type":
                return SimpleNamespace(**receipt.__dict__)
            return receipt

        def restore(self):
            nonlocal restore_calls
            restore_calls += 1
            pytest.fail("verified sync receipt must not trigger a second restore")

    monkeypatch.setattr(
        "skillscout.adapters.state_branch.StateBranchClient",
        StateClient,
    )
    monkeypatch.setattr(
        "skillscout.adapters.state_branch.StateBranchStore",
        StateStore,
    )
    operations = operations_module.OperationsStateStore(config.operations_state)
    try:
        barrier = bootstrap._LateStateDurabilityBarrier(
            config,
            {"SKILLSCOUT_STATE_GITHUB_TOKEN": "state-token"},
        )
        arguments = {
            "operations_store": operations,
            "observed_head": "a" * 40,
            "prior_root_digest": config.initial_state_root_digest,
            "created_at": "2026-07-28T03:40:00.000000Z",
        }
        if mutation == "valid":
            synchronized = barrier.sync_discovery(**arguments)
            assert synchronized.commit_sha == "b" * 40
        else:
            with pytest.raises(
                ValueError,
                match=r"^discovery state synchronization rejected$",
            ):
                barrier.sync_discovery(**arguments)
    finally:
        operations.close()

    assert sync_calls == 1
    assert restore_calls == 0


def test_real_operations_resume_advances_from_persisted_search_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    application = _module()
    operations_module = importlib.import_module(
        "skillscout.adapters.operations_state"
    )
    discovery = importlib.import_module("skillscout.domain.discovery")
    monkeypatch.chdir(tmp_path)
    config = _runtime_config(bootstrap, tmp_path)
    authority = bootstrap.discovery_run_authority(config)
    query = config.query_set.queries[0]
    page_values = {
        "schema_version": "search-page-observation-v1",
        "discovery_run_authority_digest": authority.authority_digest,
        "query_set_version": config.query_set.query_set_version,
        "query_set_digest": config.query_set.query_set_digest,
        "query_id": query.query_id,
        "query_ordinal": 1,
        "query_text": query.query_text,
        "sort": config.query_set.sort,
        "order": config.query_set.order,
        "page": 1,
        "per_page": config.query_set.per_page,
        "next_page": None,
        "total_count": 0,
        "incomplete_results": False,
        "item_count": 0,
        "request_id": "persisted-page",
        "rate_limit": {
            "limit": 10,
            "remaining": 9,
            "used": 1,
            "reset_epoch": 1,
            "resource": "search",
        },
    }
    persisted_page = discovery.SearchPageObservationV1(
        **page_values,
        observation_digest=sha256_digest(page_values),
    )
    with operations_module.OperationsStateStore(
        config.operations_state
    ) as store:
        store.create_run(authority, "2026-07-27T12:00:00.000000Z")
        store.record_search_page(authority.run_id, persisted_page, ())

    calls: list[int] = []

    class Search:
        def search_repositories(
            self,
            *,
            query_set,
            discovery_run_authority_digest: str,
            query_ordinal: int,
            page: int,
        ):
            calls.append(query_ordinal)
            selected_query = query_set.queries[query_ordinal - 1]
            values = {
                **page_values,
                "query_id": selected_query.query_id,
                "query_ordinal": query_ordinal,
                "query_text": selected_query.query_text,
                "page": page,
                "request_id": f"resume-{query_ordinal}",
            }
            return (
                discovery.SearchPageObservationV1(
                    **values,
                    observation_digest=sha256_digest(values),
                ),
                (),
            )

        def close(self) -> None:
            pass

    class Barrier:
        def sync_discovery(self, **_kwargs):
            return SimpleNamespace(
                commit_sha="c" * 40,
                root_digest="sha256:" + ("d" * 64),
            )

    result = application.DiscoveryApplication(
        application.DiscoveryDependencies(
            search_factory=Search,
            operations_store_factory=lambda: (
                operations_module.OperationsStateStore(
                    config.operations_state
                )
            ),
            state_restore=lambda: SimpleNamespace(
                status="verified",
                observed_head="b" * 40,
                bundle=SimpleNamespace(
                    root=SimpleNamespace(
                        root_digest="sha256:" + ("e" * 64)
                    )
                ),
            ),
            durability_barrier=Barrier(),
            phase2_factory=lambda **_kwargs: pytest.fail(
                "empty resume must not enter Phase 2"
            ),
            phase3_factory=lambda **_kwargs: pytest.fail(
                "empty resume must not enter Phase 3"
            ),
            query_set=config.query_set,
            initial_state_root_digest=config.initial_state_root_digest,
        )
    ).run(authority)

    assert calls == [2, 3, 4]
    assert result.run_id == authority.run_id


def test_real_operations_crosses_candidate_budget_on_next_query_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    application = _module()
    operations_module = importlib.import_module(
        "skillscout.adapters.operations_state"
    )
    discovery = importlib.import_module("skillscout.domain.discovery")
    monkeypatch.chdir(tmp_path)
    config = _runtime_config(bootstrap, tmp_path)
    authority = bootstrap.discovery_run_authority(config)

    def repository(repository_id: int):
        values = {
            "schema_version": "search-repository-observation-v1",
            "repository_id": repository_id,
            "owner": "typed",
            "name": f"repo-{repository_id}",
            "full_name": f"typed/repo-{repository_id}",
            "private": False,
            "visibility": "public",
            "fork": False,
            "archived": False,
            "disabled": False,
            "default_branch": "main",
        }
        return discovery.SearchRepositoryObservationV1(
            **values,
            observation_digest=sha256_digest(values),
        )

    planned_repositories = {
        (1, 1): tuple(repository(item) for item in range(1, 26)),
        (1, 2): (
            repository(1),
            *(repository(item) for item in range(26, 50)),
        ),
        (2, 1): tuple(repository(item) for item in range(71, 96)),
        (1, 3): (
            *(repository(item) for item in range(2, 6)),
            *(repository(item) for item in range(50, 71)),
        ),
        (2, 2): tuple(repository(item) for item in range(96, 121)),
    }
    next_pages = {
        (1, 1): 2,
        (1, 2): 3,
        (2, 1): 2,
        (1, 3): 4,
        (2, 2): 3,
    }

    class Search:
        def __init__(self, expected: tuple[tuple[int, int], ...]) -> None:
            self.expected = list(expected)
            self.calls: list[tuple[int, int]] = []

        def search_repositories(
            self,
            *,
            query_set,
            discovery_run_authority_digest: str,
            query_ordinal: int,
            page: int,
        ):
            coordinate = (query_ordinal, page)
            self.calls.append(coordinate)
            assert self.expected.pop(0) == coordinate
            repositories = planned_repositories[coordinate]
            query = query_set.queries[query_ordinal - 1]
            values = {
                "schema_version": "search-page-observation-v1",
                "discovery_run_authority_digest": (
                    discovery_run_authority_digest
                ),
                "query_set_version": query_set.query_set_version,
                "query_set_digest": query_set.query_set_digest,
                "query_id": query.query_id,
                "query_ordinal": query_ordinal,
                "query_text": query.query_text,
                "sort": query_set.sort,
                "order": query_set.order,
                "page": page,
                "per_page": query_set.per_page,
                "next_page": next_pages[coordinate],
                "total_count": 200,
                "incomplete_results": False,
                "item_count": len(repositories),
                "request_id": f"budget-{query_ordinal}-{page}",
                "rate_limit": {
                    "limit": 30,
                    "remaining": 29,
                    "used": 1,
                    "reset_epoch": 1,
                    "resource": "search",
                },
            }
            return (
                discovery.SearchPageObservationV1(
                    **values,
                    observation_digest=sha256_digest(values),
                ),
                repositories,
            )

        def close(self) -> None:
            pass

    class ProbeStop(Exception):
        pass

    class Barrier:
        def __init__(self, stop_after: int) -> None:
            self.stop_after = stop_after
            self.calls = 0

        def sync_discovery(self, **_kwargs):
            self.calls += 1
            if self.calls == self.stop_after:
                raise ProbeStop
            return SimpleNamespace(
                commit_sha=f"{self.calls:040x}",
                root_digest="sha256:" + f"{self.calls:064x}",
            )

    def run_until_barrier(
        coordinates: tuple[tuple[int, int], ...],
        *,
        stop_after: int,
    ) -> tuple[Search, Barrier]:
        search = Search(coordinates)
        barrier = Barrier(stop_after)
        with pytest.raises(SafeFailure) as failure:
            application.DiscoveryApplication(
                application.DiscoveryDependencies(
                    search_factory=lambda: search,
                    operations_store_factory=lambda: (
                        operations_module.OperationsStateStore(
                            config.operations_state
                        )
                    ),
                    state_restore=lambda: SimpleNamespace(
                        status="verified",
                        observed_head="b" * 40,
                        bundle=SimpleNamespace(
                            root=SimpleNamespace(
                                root_digest=(
                                    config.initial_state_root_digest
                                )
                            )
                        ),
                    ),
                    durability_barrier=barrier,
                    phase2_factory=lambda **_kwargs: pytest.fail(
                        "probe must stop before Phase 2"
                    ),
                    phase3_factory=lambda **_kwargs: pytest.fail(
                        "probe must stop before Phase 3"
                    ),
                    query_set=config.query_set,
                    initial_state_root_digest=(
                        config.initial_state_root_digest
                    ),
                )
            ).run(authority)
        assert failure.value.code is ErrorCode.PIPELINE_INTERRUPTED
        assert not search.expected
        return search, barrier

    first_search, first_barrier = run_until_barrier(
        ((1, 1),),
        stop_after=1,
    )
    assert first_search.calls == [(1, 1)]
    assert first_barrier.calls == 1
    second_search, second_barrier = run_until_barrier(
        ((1, 2), (2, 1)),
        stop_after=2,
    )
    assert second_search.calls == [(1, 2), (2, 1)]
    assert second_barrier.calls == 2
    with operations_module.OperationsStateStore(
        config.operations_state
    ) as store:
        prefix = store.snapshot_run(authority.run_id)
    assert len(prefix.candidates) == 75
    assert sum(
        item.dedup_disposition == "first_seen"
        for item in prefix.candidates
    ) == 74

    final_search, final_barrier = run_until_barrier(
        ((1, 3), (2, 2)),
        stop_after=2,
    )
    assert final_search.calls == [(1, 3), (2, 2)]
    assert final_barrier.calls == 2
    with operations_module.OperationsStateStore(
        config.operations_state
    ) as store:
        snapshot = store.snapshot_run(authority.run_id)
    final_page = tuple(
        item
        for item in snapshot.candidates
        if (item.query_ordinal, item.page) == (2, 2)
    )
    assert len(snapshot.search_pages) == 5
    assert len(snapshot.candidates) == 125
    assert sum(
        item.dedup_disposition == "first_seen"
        for item in snapshot.candidates
    ) == 100
    assert sum(
        item.dedup_disposition == "budget_excluded"
        for item in snapshot.candidates
    ) == 20
    assert tuple(
        item.dedup_disposition for item in final_page
    ) == ("first_seen",) * 5 + ("budget_excluded",) * 20

    state_module = importlib.import_module("skillscout.adapters.state")
    publication_module = importlib.import_module(
        "skillscout.adapters.publication_state"
    )
    pipeline = state_module.SQLiteStateStore(config.pipeline_state)
    operations = operations_module.OperationsStateStore(
        config.operations_state
    )
    publication = publication_module.PublicationStateStore(
        config.publication_state
    )
    try:
        bundle = operations_module.assemble_three_store_bundle(
            pipeline_store=pipeline,
            operations_store=operations,
            publication_store=publication,
            prior_root_digest=config.initial_state_root_digest,
            state_parent_commit_sha="b" * 40,
            query_set_digest=config.query_set_digest,
            budget_policy_digest=(
                discovery.DiscoveryBudgetPolicyV1().budget_policy_digest
                or ""
            ),
            created_at="2026-07-27T12:00:00.000000Z",
        )
    finally:
        publication.close()
        operations.close()
        pipeline.close()
    assert len(bundle.root.objects) == 135
    assert len(bundle.files) == 139


def test_lazy_discovery_capability_does_not_resolve_extractor_on_skip() -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    processors = importlib.import_module("skillscout.application.processors")
    ports = importlib.import_module("skillscout.application.ports")
    enums = importlib.import_module("skillscout.domain.enums")
    subjects = importlib.import_module("skillscout.domain.subjects")
    effects: list[str] = []

    lazy = bootstrap._LazyDiscoveryCapability(
        lambda: effects.append("extractor") or object(),
        enums.EffectScope.REMOTE_READ,
    )
    processor = processors.PhaseTwoProcessor(object(), lazy)
    outcome = processor.process(
        importlib.import_module("skillscout.domain.models").StageInput(
            schema_version="2",
            execution_mode=enums.ExecutionMode.DRY_RUN,
            subject_id="repo:example/rejected",
            stage=enums.PipelineStage.EXTRACTOR,
            previous_output_hash=None,
            fixture_hash=None,
        ),
        ports.StageContext(
            subject=subjects.RepositorySubject(
                schema_version="1",
                subject_id="repo:example/rejected",
                repository="https://github.com/example/rejected",
            ),
            prior_payloads={
                "scout": {"outcome": "accepted"},
                "filter": {
                    "outcome": "rejected",
                    "rejection_reason": "license_not_allowed",
                },
            },
            scratch={},
        ),
    )

    assert outcome.payload["outcome"] == "skipped"
    assert effects == []


def test_mixed_workflow_outcomes_persist_exact_handoff_and_degrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    module = _module()
    operations_module = importlib.import_module(
        "skillscout.adapters.operations_state"
    )
    discovery = importlib.import_module("skillscout.domain.discovery")
    monkeypatch.chdir(tmp_path)
    config = _runtime_config(bootstrap, tmp_path)
    authority = bootstrap.discovery_run_authority(config)
    repository_values = {
        "schema_version": "search-repository-observation-v1",
        "repository_id": 910001,
        "owner": "example",
        "name": "mixed",
        "full_name": "example/mixed",
        "private": False,
        "visibility": "public",
        "fork": False,
        "archived": False,
        "disabled": False,
        "default_branch": "main",
    }
    repository = discovery.SearchRepositoryObservationV1(
        **repository_values,
        observation_digest=sha256_digest(repository_values),
    )

    class Search:
        def search_repositories(
            self,
            *,
            query_set,
            discovery_run_authority_digest: str,
            query_ordinal: int,
            page: int,
        ):
            query = query_set.queries[query_ordinal - 1]
            repositories = (repository,) if query_ordinal == 1 else ()
            values = {
                "schema_version": "search-page-observation-v1",
                "discovery_run_authority_digest": discovery_run_authority_digest,
                "query_set_version": query_set.query_set_version,
                "query_set_digest": query_set.query_set_digest,
                "query_id": query.query_id,
                "query_ordinal": query_ordinal,
                "query_text": query.query_text,
                "sort": query_set.sort,
                "order": query_set.order,
                "page": page,
                "per_page": query_set.per_page,
                "next_page": None,
                "total_count": len(repositories),
                "incomplete_results": False,
                "item_count": len(repositories),
                "request_id": f"mixed-{query_ordinal}",
                "rate_limit": {
                    "limit": 10,
                    "remaining": 9,
                    "used": 1,
                    "reset_epoch": 1,
                    "resource": "search",
                },
            }
            return (
                discovery.SearchPageObservationV1(
                    **values,
                    observation_digest=sha256_digest(values),
                ),
                repositories,
            )

        def close(self) -> None:
            pass

    eligible_authority = "sha256:" + ("a" * 64)
    unknown_authority = "sha256:" + ("b" * 64)
    locator = module.eligible_candidate_locator(
        authority_digest="sha256:" + ("c" * 64),
        workflow_identity_digest=eligible_authority,
    )

    def phase2_factory(**arguments):
        candidate = arguments["candidate"]
        terminal_values = {
            "schema_version": "discovery-candidate-terminal-v1",
            "discovery_run_authority_digest": authority.authority_digest,
            "repository_id": candidate.repository.repository_id,
            "semantic_reservation_digest": None,
            "outcome": "semantic_outcome_unknown",
            "workflow_authority_digests": (
                eligible_authority,
                unknown_authority,
            ),
            "recorded_at": "2026-07-27T12:00:00.000000Z",
        }
        return module.DiscoveryCandidateExecution(
            terminal=discovery.DiscoveryCandidateTerminalV1(
                **terminal_values,
                terminal_digest=sha256_digest(terminal_values),
            ),
            eligible_candidates=(locator,),
            state_commit_sha=arguments["observed_head"],
            state_root_digest=arguments["prior_root_digest"],
            workflows=(
                module.DiscoveryWorkflowExecution(
                    workflow_authority_digest=eligible_authority,
                    outcome="eligible",
                    locator=locator,
                ),
                module.DiscoveryWorkflowExecution(
                    workflow_authority_digest=unknown_authority,
                    outcome="semantic_outcome_unknown",
                ),
            ),
        )

    class Barrier:
        def sync_discovery(self, **_kwargs):
            return SimpleNamespace(
                commit_sha="c" * 40,
                root_digest="sha256:" + ("d" * 64),
            )

    result = module.DiscoveryApplication(
        module.DiscoveryDependencies(
            search_factory=Search,
            operations_store_factory=lambda: (
                operations_module.OperationsStateStore(
                    config.operations_state
                )
            ),
            state_restore=lambda: SimpleNamespace(
                status="verified",
                observed_head="b" * 40,
                bundle=SimpleNamespace(
                    root=SimpleNamespace(
                        root_digest=config.initial_state_root_digest
                    )
                ),
            ),
            durability_barrier=Barrier(),
            phase2_factory=phase2_factory,
            phase3_factory=lambda **_kwargs: object(),
            query_set=config.query_set,
            initial_state_root_digest=config.initial_state_root_digest,
        )
    ).run(authority)

    with operations_module.OperationsStateStore(
        config.operations_state
    ) as store:
        snapshot = store.snapshot_run(authority.run_id)
    assert result.eligible_candidates == (locator,)
    assert tuple(
        item.outcome for item in snapshot.workflow_terminals
    ) == ("eligible_local_candidate", "semantic_outcome_unknown")
    assert snapshot.summary.status == "completed_degraded"


@pytest.mark.parametrize(
    "failing_close",
    ("extractor", "github", "publication", "phase2_state"),
)
@pytest.mark.parametrize(
    "primary_outcome",
    (
        "handled_terminal",
        "exception",
        "candidate_source_unavailable",
        "descriptor_source_unavailable",
    ),
)
def test_default_phase2_factory_cleanup_cannot_mask_classified_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failing_close: str,
    primary_outcome: str,
) -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    discovery = importlib.import_module("skillscout.domain.discovery")
    operations_module = importlib.import_module(
        "skillscout.adapters.operations_state"
    )
    monkeypatch.chdir(tmp_path)
    config = _runtime_config(bootstrap, tmp_path)
    authority = bootstrap.discovery_run_authority(config)
    closed: list[str] = []

    class Resource:
        def __init__(self, label: str) -> None:
            self.label = label
            self.marker = True

        @property
        def effect_scope(self):
            return importlib.import_module(
                "skillscout.domain.enums"
            ).EffectScope.REMOTE_READ

        def export_owned_state(self) -> object:
            return object()

        def close(self) -> None:
            closed.append(self.label)
            if self.label == failing_close:
                raise RuntimeError("SECRET cleanup failure")

    class FakePhaseTwoState(Resource):
        def __init__(self, _path: Path) -> None:
            super().__init__("phase2_state")

        def verify_run_chain(self, _run_id: str) -> object:
            return SimpleNamespace(results=())

    class Barrier:
        def confirm(self, **_kwargs: object) -> object:
            raise AssertionError(
                "handled failure does not confirm another transition"
            )

    class PrimaryFailure(RuntimeError):
        pass

    def build_runtime(_state, processor, *, semantic_durability, **_kwargs):
        assert processor.github.marker
        assert processor.openai.marker
        semantic_durability._publication_store.export_owned_state()

        class Runner:
            def run(self, _subject, _output):
                if primary_outcome == "exception":
                    raise PrimaryFailure("SECRET primary failure")
                if primary_outcome == "handled_terminal":
                    raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
                return SimpleNamespace(run_id="completed-phase2")

        return SimpleNamespace(runner=Runner())

    monkeypatch.setattr(
        "skillscout.adapters.github.GitHubReadClient",
        lambda **_kwargs: Resource("github"),
    )
    monkeypatch.setattr(
        "skillscout.adapters.openai_extract.OpenAIExtractionClient",
        lambda **_kwargs: Resource("extractor"),
    )
    monkeypatch.setattr(
        "skillscout.adapters.publication_state.PublicationStateStore",
        lambda _path: Resource("publication"),
    )
    monkeypatch.setattr(
        "skillscout.adapters.state.SQLiteStateStore",
        FakePhaseTwoState,
    )
    monkeypatch.setattr(
        "skillscout.application.pipeline.build_phase_two_runtime",
        build_runtime,
    )
    if primary_outcome == "candidate_source_unavailable":
        monkeypatch.setattr(
            "skillscout.application.candidate_source."
            "derive_candidate_subject_descriptors",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                CandidateSourceUnavailable()
            ),
        )
    elif primary_outcome == "descriptor_source_unavailable":
        monkeypatch.setattr(
            "skillscout.application.candidate_source."
            "derive_candidate_subject_descriptors",
            lambda *_args, **_kwargs: ({"bounded": "descriptor"},),
        )
        monkeypatch.setattr(
            "skillscout.application.candidate_source.load_candidate_subject",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                CandidateSourceUnavailable()
            ),
        )

    application = bootstrap.build_discovery_application(
        config,
        environ={"SKILLSCOUT_SOURCE_GITHUB_TOKEN": "bounded-test-token"},
    )
    factory = application._dependencies.phase2_factory
    repository_values = {
        "schema_version": "search-repository-observation-v1",
        "repository_id": 101,
        "owner": "example",
        "name": "workflow",
        "full_name": "example/workflow",
        "private": False,
        "visibility": "public",
        "fork": False,
        "archived": False,
        "disabled": False,
        "default_branch": "main",
    }
    repository = discovery.SearchRepositoryObservationV1(
        **repository_values,
        observation_digest=sha256_digest(repository_values),
    )
    candidate_values = {
        "schema_version": "discovered-candidate-v1",
        "discovery_run_authority_digest": authority.authority_digest,
        "repository": repository,
        "source_page_digest": "sha256:" + ("2" * 64),
        "query_ordinal": 1,
        "page": 1,
        "item_ordinal": 1,
        "dedup_disposition": "first_seen",
        "discovery_ordinal": 1,
        "first_seen_query_ordinal": 1,
        "first_seen_page": 1,
        "first_seen_item_ordinal": 1,
    }
    candidate = discovery.DiscoveredCandidateV1(
        **candidate_values,
        candidate_digest=sha256_digest(
            {
                key: (
                    value.model_dump(mode="json", exclude_none=False)
                    if hasattr(value, "model_dump")
                    else value
                )
                for key, value in candidate_values.items()
            }
        ),
    )
    operations = operations_module.OperationsStateStore(
        config.operations_state
    )
    operations.create_run(authority, "2026-07-28T00:00:00.000000Z")
    try:
        arguments = {
            "candidate": candidate,
            "discovery_authority": authority,
            "operations_store": operations,
            "durability_barrier": Barrier(),
            "observed_head": "b" * 40,
            "prior_root_digest": config.initial_state_root_digest,
            "phase3_factory": lambda **_kwargs: object(),
        }
        if primary_outcome == "exception":
            with pytest.raises(PrimaryFailure, match="primary failure"):
                factory(**arguments)
            execution = None
        else:
            execution = factory(**arguments)
    finally:
        operations.close()

    if execution is not None:
        assert execution.terminal.outcome == "permanent_failure"
        assert execution.state_commit_sha == "b" * 40
    assert set(closed) == {
        "extractor",
        "github",
        "publication",
        "phase2_state",
    }


def test_restart_quarantines_orphan_started_extractor_without_provider_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    discovery_domain = importlib.import_module(
        "skillscout.domain.discovery"
    )
    discovery_application = importlib.import_module(
        "skillscout.application.discovery"
    )
    operations_module = importlib.import_module(
        "skillscout.adapters.operations_state"
    )
    pipeline_module = importlib.import_module(
        "skillscout.application.pipeline"
    )
    ports = importlib.import_module("skillscout.application.ports")
    enums = importlib.import_module("skillscout.domain.enums")
    state_module = importlib.import_module("skillscout.adapters.state")
    publication_module = importlib.import_module(
        "skillscout.adapters.publication_state"
    )
    state_branch_module = importlib.import_module(
        "skillscout.adapters.state_branch"
    )
    subjects = importlib.import_module("skillscout.domain.subjects")
    monkeypatch.chdir(tmp_path)
    config = _runtime_config(bootstrap, tmp_path)
    authority = bootstrap.discovery_run_authority(config)
    timestamp = "2026-07-28T00:00:00.000000Z"

    repository_values = {
        "schema_version": "search-repository-observation-v1",
        "repository_id": 101,
        "owner": "example",
        "name": "orphan",
        "full_name": "example/orphan",
        "private": False,
        "visibility": "public",
        "fork": False,
        "archived": False,
        "disabled": False,
        "default_branch": "main",
    }
    repository = discovery_domain.SearchRepositoryObservationV1(
        **repository_values,
        observation_digest=sha256_digest(repository_values),
    )
    operations = operations_module.OperationsStateStore(
        config.operations_state
    )
    operations.create_run(authority, timestamp)
    candidate = None
    for query_ordinal, query in enumerate(config.query_set.queries, start=1):
        page_values = {
            "schema_version": "search-page-observation-v1",
            "discovery_run_authority_digest": authority.authority_digest,
            "query_set_version": config.query_set.query_set_version,
            "query_set_digest": config.query_set.query_set_digest,
            "query_id": query.query_id,
            "query_ordinal": query_ordinal,
            "query_text": query.query_text,
            "sort": config.query_set.sort,
            "order": config.query_set.order,
            "page": 1,
            "per_page": config.query_set.per_page,
            "next_page": None,
            "total_count": 1 if query_ordinal == 1 else 0,
            "incomplete_results": False,
            "item_count": 1 if query_ordinal == 1 else 0,
            "request_id": f"restart-{query_ordinal}",
            "rate_limit": {
                "limit": 10,
                "remaining": 9,
                "used": 1,
                "reset_epoch": 1,
                "resource": "search",
            },
        }
        page = discovery_domain.SearchPageObservationV1(
            **page_values,
            observation_digest=sha256_digest(page_values),
        )
        candidates = ()
        if query_ordinal == 1:
            candidate_values = {
                "schema_version": "discovered-candidate-v1",
                "discovery_run_authority_digest": authority.authority_digest,
                "repository": repository,
                "source_page_digest": page.observation_digest,
                "query_ordinal": 1,
                "page": 1,
                "item_ordinal": 1,
                "dedup_disposition": "first_seen",
                "discovery_ordinal": 1,
                "first_seen_query_ordinal": 1,
                "first_seen_page": 1,
                "first_seen_item_ordinal": 1,
            }
            candidate = discovery_domain.DiscoveredCandidateV1(
                **candidate_values,
                candidate_digest=sha256_digest(
                    {
                        key: (
                            value.model_dump(mode="json", exclude_none=False)
                            if hasattr(value, "model_dump")
                            else value
                        )
                        for key, value in candidate_values.items()
                    }
                ),
            )
            candidates = (candidate,)
        operations.record_search_page(authority.run_id, page, candidates)
    assert candidate is not None
    operations.reserve_discovery_candidate(
        authority.run_id,
        candidate,
        timestamp,
    )

    phase2_authority_digest = sha256_digest(
        {
            "schema_version": "discovery-phase2-run-authority-v1",
            "discovery_run_authority_digest": authority.authority_digest,
            "candidate_digest": candidate.candidate_digest,
            "phase2_profile_version": config.phase2_profile_version,
            "extractor_model_id": config.extractor_model_id,
        }
    )
    reserved_head = "d" * 40
    started_head = "e" * 40
    reserved_root = "sha256:" + ("3" * 64)
    started_root = "sha256:" + ("4" * 64)

    def reserve_before_extractor(*, pipeline_store, run_id: str):
        del pipeline_store, run_id
        reservation = operations.reserve_semantic_candidate(
            authority.run_id,
            candidate.repository.repository_id,
            phase2_authority_digest,
            timestamp,
        )
        return pipeline_module.SemanticReservationReceipt(
            reservation_digest=reservation.reservation_digest,
            verified_state_head=reserved_head,
            state_root_digest=reserved_root,
        )

    class SetupBarrier:
        def confirm(self, *, transition, **_kwargs):
            return ports.DurabilityReceipt.from_remote_verification(
                transition=transition,
                verified_state_head=started_head,
                state_root_digest=started_root,
                pipeline_database_digest="sha256:" + ("5" * 64),
                operations_database_digest="sha256:" + ("6" * 64),
                publication_database_digest="sha256:" + ("7" * 64),
                pipeline_projection_digest="sha256:" + ("8" * 64),
                operations_projection_digest="sha256:" + ("9" * 64),
                publication_projection_digest="sha256:" + ("a" * 64),
            )

    class SimulatedProcessCrash(BaseException):
        pass

    original_provider_calls = 0

    class CrashAfterStarted:
        producer_version = "phase2-v1"

        def semantic_request_required(self, _context) -> bool:
            return True

        def process(self, stage_input, _context):
            nonlocal original_provider_calls
            if stage_input.stage is enums.PipelineStage.EXTRACTOR:
                original_provider_calls += 1
                raise SimulatedProcessCrash
            return pipeline_module.StageOutcome(
                payload={"outcome": "accepted"},
                telemetry=None,
            )

    publication = publication_module.PublicationStateStore(
        config.publication_state
    )
    phase2_state = state_module.SQLiteStateStore(config.pipeline_state)
    try:
        guard = pipeline_module.SemanticDurabilityGuard(
            barrier=SetupBarrier(),
            operations_store=operations,
            publication_store=publication,
            repository_id=candidate.repository.repository_id,
            workflow_authority_digest=phase2_authority_digest,
            provider="openai",
            expected_prior_state_head="c" * 40,
            expected_prior_root_digest=config.initial_state_root_digest,
            reservation_hook=reserve_before_extractor,
            operations_run_id=authority.run_id,
        )
        with pytest.raises(SimulatedProcessCrash):
            pipeline_module.PipelineRunner(
                phase2_state,
                CrashAfterStarted(),
                semantic_durability=guard,
            ).run(
                subjects.RepositorySubject(
                    schema_version="1",
                    subject_id=f"repo:{candidate.repository.full_name}",
                    repository=(
                        f"https://github.com/{candidate.repository.full_name}"
                    ),
                ),
                tmp_path / "crashed-output",
            )
    finally:
        phase2_state.close()
        publication.close()
    assert original_provider_calls == 1

    phase2_state = state_module.SQLiteStateStore(config.pipeline_state)
    publication = publication_module.PublicationStateStore(
        config.publication_state
    )
    try:
        parent_bundle = operations_module.assemble_three_store_bundle(
            pipeline_store=phase2_state,
            operations_store=operations,
            publication_store=publication,
            prior_root_digest=reserved_root,
            state_parent_commit_sha=reserved_head,
            query_set_digest=config.query_set_digest,
            budget_policy_digest=(
                discovery_domain.DiscoveryBudgetPolicyV1().budget_policy_digest
                or ""
            ),
            created_at=timestamp,
        )
    finally:
        phase2_state.close()
        publication.close()
    started_root = parent_bundle.root.root_digest

    class InstrumentedRemote:
        def __init__(self) -> None:
            self.head = started_head
            self.operations: list[str] = []
            self.force_values: list[bool] = []
            self.blobs = {
                state_branch_module._git_blob_id(item.content): item.content
                for item in parent_bundle.files
            }
            parent_tree_sha = "1" * 40
            self.trees = {
                parent_tree_sha: tuple(
                    state_branch_module.StateTreeEntry(
                        path=item.path,
                        sha=state_branch_module._git_blob_id(item.content),
                        mode="100644",
                        size=len(item.content),
                    )
                    for item in parent_bundle.files
                )
            }
            self.commits = {
                started_head: state_branch_module.StateCommitObservation(
                    sha=started_head,
                    tree_sha=parent_tree_sha,
                    parents=(reserved_head,),
                    message=state_branch_module._state_commit_message(
                        started_root
                    ),
                )
            }
            self.counter = 20

        def _sha(self) -> str:
            self.counter += 1
            return f"{self.counter:040x}"

        def get_state_ref(self):
            self.operations.append("get_state_ref")
            return state_branch_module.StateRefObservation(
                state_branch_module.STATE_REF,
                self.head,
            )

        def get_commit(self, sha: str):
            self.operations.append("get_commit")
            return self.commits[sha]

        def get_tree(self, sha: str):
            self.operations.append("get_tree")
            return self.trees[sha]

        def get_blob(self, sha: str) -> bytes:
            self.operations.append("get_blob")
            return self.blobs[sha]

        def create_blob(self, content: bytes) -> str:
            self.operations.append("create_blob")
            sha = state_branch_module._git_blob_id(content)
            self.blobs[sha] = content
            return sha

        def create_tree(self, entries) -> str:
            self.operations.append("create_tree")
            sha = self._sha()
            self.trees[sha] = tuple(
                state_branch_module.StateTreeEntry(
                    path=str(entry["path"]),
                    sha=str(entry["sha"]),
                    mode="100644",
                    size=len(self.blobs[str(entry["sha"])]),
                )
                for entry in entries
            )
            return sha

        def create_commit(
            self,
            message: str,
            tree: str,
            parents,
        ) -> str:
            self.operations.append("create_commit")
            sha = self._sha()
            self.commits[sha] = state_branch_module.StateCommitObservation(
                sha=sha,
                tree_sha=tree,
                parents=tuple(parents),
                message=message,
            )
            return sha

        def update_state_ref(self, sha: str, *, force: bool):
            self.operations.append("update_state_ref")
            self.force_values.append(force)
            assert force is False
            self.head = sha
            return state_branch_module.StateRefObservation(
                state_branch_module.STATE_REF,
                sha,
            )

    remote = InstrumentedRemote()
    state_branch_store = state_branch_module.StateBranchStore(remote)
    real_recovery_barrier = state_branch_module.StateBranchDurabilityBarrier(
        state_store=state_branch_store,
        query_set_digest=config.query_set_digest,
        budget_policy_digest=(
            discovery_domain.DiscoveryBudgetPolicyV1().budget_policy_digest
            or ""
        ),
    )

    provider_constructions = 0

    class ForbiddenProvider:
        def __init__(self, **_kwargs) -> None:
            nonlocal provider_constructions
            provider_constructions += 1
            raise AssertionError("orphan semantic request must not be replayed")

    monkeypatch.setattr(
        "skillscout.adapters.openai_extract.OpenAIExtractionClient",
        ForbiddenProvider,
    )

    transitions: list[str] = []
    discovery_syncs: list[str] = []

    class RecoveryBarrier:
        def confirm(self, *, transition, **kwargs):
            transitions.append(transition.transition)
            assert transition.transition == "result_outcome_unknown"
            return real_recovery_barrier.confirm(
                transition=transition,
                **kwargs,
            )

        def sync_discovery(
            self,
            *,
            operations_store,
            observed_head,
            prior_root_digest,
            created_at,
            pipeline_store=None,
        ):
            snapshot = operations_store.snapshot_run(authority.run_id)
            if not snapshot.candidate_terminals:
                raise AssertionError(
                    "durable discovery reservation must not be resynchronized"
                )
            kind = "summary" if snapshot.summary is not None else "terminal"
            discovery_syncs.append(kind)
            pipeline = (
                pipeline_store
                if pipeline_store is not None
                else state_module.SQLiteStateStore(config.pipeline_state)
            )
            owns_pipeline = pipeline_store is None
            publication_store = publication_module.PublicationStateStore(
                config.publication_state
            )
            try:
                bundle = operations_module.assemble_three_store_bundle(
                    pipeline_store=pipeline,
                    operations_store=operations_store,
                    publication_store=publication_store,
                    prior_root_digest=prior_root_digest,
                    state_parent_commit_sha=observed_head,
                    query_set_digest=config.query_set_digest,
                    budget_policy_digest=(
                        discovery_domain.DiscoveryBudgetPolicyV1()
                        .budget_policy_digest
                        or ""
                    ),
                    created_at=created_at,
                )
                return state_branch_store.sync(bundle, observed_head)
            finally:
                publication_store.close()
                if owns_pipeline:
                    pipeline.close()

    class Search:
        def search_repositories(self, **_kwargs):
            raise AssertionError("restored terminal pages must not be replayed")

        def close(self) -> None:
            pass

    built = bootstrap.build_discovery_application(config, environ={})
    real_snapshot_run = operations_module.OperationsStateStore.snapshot_run

    def mismatched_snapshot(store, run_id):
        snapshot = real_snapshot_run(store, run_id)
        semantic = snapshot.semantic_reservations[0].model_copy(
            update={
                "phase2_run_authority_digest": "sha256:" + ("2" * 64)
            }
        )
        return type(snapshot)(
            search_pages=snapshot.search_pages,
            candidates=snapshot.candidates,
            discovery_reservations=snapshot.discovery_reservations,
            semantic_reservations=(semantic,),
            semantic_attempts=snapshot.semantic_attempts,
            workflow_terminals=snapshot.workflow_terminals,
            candidate_terminals=snapshot.candidate_terminals,
            summary=snapshot.summary,
        )

    monkeypatch.setattr(
        operations_module.OperationsStateStore,
        "snapshot_run",
        mismatched_snapshot,
    )
    operations.close()
    mismatched_operations = operations_module.OperationsStateStore(
        config.operations_state
    )
    try:
        with pytest.raises(SafeFailure) as mismatch:
            built._dependencies.phase2_factory(
                candidate=candidate,
                discovery_authority=authority,
                operations_store=mismatched_operations,
                durability_barrier=RecoveryBarrier(),
                observed_head=started_head,
                prior_root_digest=started_root,
                phase3_factory=built._dependencies.phase3_factory,
            )
        assert mismatch.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    finally:
        mismatched_operations.close()
    assert provider_constructions == 0
    assert transitions == []
    assert discovery_syncs == []
    monkeypatch.setattr(
        operations_module.OperationsStateStore,
        "snapshot_run",
        real_snapshot_run,
    )

    def restore_state():
        restored = state_branch_store.restore()
        assert restored.bundle is not None
        operations_module.restore_three_store_bundle(
            restored.bundle,
            pipeline_path=config.pipeline_state,
            operations_path=config.operations_state,
            publication_path=config.publication_state,
        )
        return restored

    application = discovery_application.DiscoveryApplication(
        discovery_application.DiscoveryDependencies(
            search_factory=Search,
            operations_store_factory=lambda: (
                operations_module.OperationsStateStore(
                    config.operations_state
                )
            ),
            state_restore=restore_state,
            durability_barrier=RecoveryBarrier(),
            phase2_factory=built._dependencies.phase2_factory,
            phase3_factory=built._dependencies.phase3_factory,
            query_set=config.query_set,
            initial_state_root_digest=config.initial_state_root_digest,
        )
    )
    try:
        result = application.run(authority)
    except Exception as failure:
        pytest.fail(
            "real recovery probe failed: "
            f"type={type(failure).__name__} "
            f"code={getattr(failure, 'code', None)} "
            f"last_remote_operation="
            f"{remote.operations[-1] if remote.operations else None} "
            f"update_state_ref_reached="
            f"{'update_state_ref' in remote.operations} "
            f"provider_constructions={provider_constructions}"
        )

    with operations_module.OperationsStateStore(
        config.operations_state
    ) as restored_operations:
        snapshot = restored_operations.snapshot_run(authority.run_id)
    assert provider_constructions == 0
    assert transitions == ["result_outcome_unknown"]
    assert discovery_syncs == ["terminal", "summary"]
    assert tuple(item.status for item in snapshot.semantic_attempts) == (
        "semantic_outcome_unknown",
    )
    assert tuple(item.outcome for item in snapshot.candidate_terminals) == (
        "semantic_outcome_unknown",
    )
    assert snapshot.summary.status == "completed_degraded"
    assert result.eligible_candidates == ()
    assert remote.force_values == [False, False, False]
    assert remote.operations.count("update_state_ref") == 3
    assert len(remote.operations) == 119
    assert remote.operations[-1] == "get_tree"
