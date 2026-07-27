"""Wave-0 RED contract for the discovery-owned operations ledger."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

import pytest

from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
    DiscoveryBudgetPolicyV1,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "state_branch" / "valid_state.json"
OPERATIONS_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-operations-store-missing",
)
EXPORT_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-store-export-missing",
)

FORBIDDEN_SCHEMA_OWNERS = {
    "runs",
    "stage_attempts",
    "stage_results",
    "phase3_candidate_runs",
    "publication_attempts",
    "publication_checkpoints",
}


def _operations_module():
    return importlib.import_module("skillscout.adapters.operations_state")


def test_state_fixture_is_bounded_canonical_and_database_owner_complete() -> None:
    payload = FIXTURE.read_bytes()
    assert len(payload) < 16_384
    assert payload == json.dumps(
        json.loads(payload),
        indent=2,
        sort_keys=True,
    ).encode() + b"\n"
    parsed = json.loads(payload)
    assert tuple(parsed["databases"]) == (
        "operations",
        "pipeline",
        "publication",
    )
    assert [item["owner"] for item in parsed["root"]["databases"]] == [
        "pipeline",
        "operations",
        "publication",
    ]
    assert [item["locator"] for item in parsed["root"]["databases"]] == [
        "state/databases/pipeline.sqlite3",
        "state/databases/operations.sqlite3",
        "state/databases/publication.sqlite3",
    ]


def test_operations_schema_ownership_is_disjoint_from_existing_stores() -> None:
    existing = (
        ROOT / "src" / "skillscout" / "adapters" / "state.py"
    ).read_text()
    publication = (
        ROOT / "src" / "skillscout" / "adapters" / "publication_state.py"
    ).read_text()
    assert "CREATE TABLE IF NOT EXISTS publication_attempts" not in existing
    assert "CREATE TABLE IF NOT EXISTS phase3_candidate_runs" not in publication

    future = ROOT / "src" / "skillscout" / "adapters" / "operations_state.py"
    if future.exists():
        source = future.read_text()
        for table in FORBIDDEN_SCHEMA_OWNERS:
            assert f"CREATE TABLE {table}" not in source
            assert f"CREATE TABLE IF NOT EXISTS {table}" not in source


@OPERATIONS_XFAIL
def test_operations_store_has_closed_non_refundable_surface() -> None:
    store_type = getattr(_operations_module(), "OperationsStateStore")
    public = {
        name
        for name, member in inspect.getmembers(store_type)
        if not name.startswith("_") and callable(member)
    }
    assert {
        "create_run",
        "record_search_page",
        "reserve_discovery_candidate",
        "reserve_semantic_candidate",
        "record_candidate_terminal",
        "record_run_summary",
        "export_owned_state",
        "restore_owned_state",
        "close",
    } <= public
    assert not public.intersection(
        {"refund", "delete_reservation", "reset_budget", "prune"}
    )


@pytest.mark.parametrize(
    ("limit", "denied"),
    (
        (DISCOVERY_MAX_CANDIDATES, DISCOVERY_MAX_CANDIDATES + 1),
        (DISCOVERY_MAX_SEMANTIC_CANDIDATES, DISCOVERY_MAX_SEMANTIC_CANDIDATES + 1),
    ),
)
@OPERATIONS_XFAIL
def test_reservation_limits_are_literal_and_transactional(
    tmp_path: Path,
    limit: int,
    denied: int,
) -> None:
    module = _operations_module()
    store = module.OperationsStateStore(tmp_path / "operations.sqlite3")
    try:
        policy = DiscoveryBudgetPolicyV1()
        reservation = store.reserve_test_slot(
            kind="discovery" if limit == 100 else "semantic",
            run_id="discovery-wave0",
            repository_id=900_000 + limit,
            requested_ordinal=limit,
            policy=policy,
        )
        assert reservation.ordinal == limit
        assert (
            store.reserve_test_slot(
                kind="discovery" if limit == 100 else "semantic",
                run_id="discovery-wave0",
                repository_id=900_000 + limit,
                requested_ordinal=limit,
                policy=policy,
            )
            == reservation
        )
        with pytest.raises(module.BudgetExhausted):
            store.reserve_test_slot(
                kind="discovery" if limit == 100 else "semantic",
                run_id="discovery-wave0",
                repository_id=900_000 + denied,
                requested_ordinal=denied,
                policy=policy,
            )
        assert store.reservation_count(
            "discovery-wave0",
            kind="discovery" if limit == 100 else "semantic",
        ) == 1
    finally:
        store.close()


@pytest.mark.parametrize(
    "terminal",
    (
        "filter_rejected",
        "no_workflow",
        "qualification_rejected",
        "validation_rejected",
        "review_rejected",
        "completed_reuse",
        "eligible_local_candidate",
        "confirmed_retryable",
        "semantic_outcome_unknown",
        "state_integrity_conflict",
        "permanent_failure",
    ),
)
@OPERATIONS_XFAIL
def test_every_terminal_retains_consumed_reservations(
    tmp_path: Path,
    terminal: str,
) -> None:
    module = _operations_module()
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        store.seed_test_reservations(
            run_id="discovery-wave0",
            repository_id=910001,
        )
        before = store.reservation_projection("discovery-wave0")
        store.record_test_terminal(
            run_id="discovery-wave0",
            repository_id=910001,
            outcome=terminal,
        )
        assert store.reservation_projection("discovery-wave0") == before


@EXPORT_XFAIL
def test_owned_export_rebuild_and_projection_equality_fail_closed(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    original = tmp_path / "operations.sqlite3"
    rebuilt = tmp_path / "rebuilt.sqlite3"
    with module.OperationsStateStore(original) as store:
        store.seed_test_reservations(
            run_id="discovery-wave0",
            repository_id=910001,
        )
        exported = store.export_owned_state()
    assert exported.owner == "operations"
    assert exported.database_locator == "state/databases/operations.sqlite3"
    assert b"-wal" not in exported.database_bytes
    assert b"-journal" not in exported.database_bytes

    module.OperationsStateStore.rebuild_owned_state(rebuilt, exported)
    with module.OperationsStateStore(rebuilt) as store:
        assert store.export_owned_state().projection == exported.projection

    tampered = exported.model_copy(
        update={"projection_digest": "sha256:" + ("f" * 64)}
    )
    with pytest.raises(Exception):
        module.OperationsStateStore.rebuild_owned_state(
            tmp_path / "rejected.sqlite3",
            tampered,
        )
