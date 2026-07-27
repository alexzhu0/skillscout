"""Wave-0 RED contract for the discovery-owned operations ledger."""

from __future__ import annotations

import importlib
import inspect
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
    DiscoveryBudgetPolicyV1,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "state_branch" / "valid_state.json"
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
def test_reservation_limits_are_literal_and_transactional(
    tmp_path: Path,
    limit: int,
    denied: int,
) -> None:
    module = _operations_module()
    store = module.OperationsStateStore(tmp_path / "operations.sqlite3")
    try:
        policy = DiscoveryBudgetPolicyV1()
        kind = "discovery" if limit == 100 else "semantic"
        reservations = tuple(
            store.reserve_test_slot(
                kind=kind,
                run_id="discovery-wave0",
                repository_id=900_000 + ordinal,
                requested_ordinal=ordinal,
                policy=policy,
            )
            for ordinal in range(1, limit + 1)
        )
        reservation = reservations[-1]
        assert tuple(item.ordinal for item in reservations) == tuple(
            range(1, limit + 1)
        )
        assert reservation.ordinal == limit
        assert (
            store.reserve_test_slot(
                kind=kind,
                run_id="discovery-wave0",
                repository_id=900_000 + limit,
                requested_ordinal=limit,
                policy=policy,
            )
            == reservation
        )
        with pytest.raises(module.BudgetExhausted):
            store.reserve_test_slot(
                kind=kind,
                run_id="discovery-wave0",
                repository_id=900_000 + denied,
                requested_ordinal=denied,
                policy=policy,
            )
        assert store.reservation_count(
            "discovery-wave0",
            kind=kind,
        ) == limit
    finally:
        store.close()


def test_reservation_is_unique_under_repeated_concurrent_callers(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        policy = DiscoveryBudgetPolicyV1()

        def reserve() -> object:
            return store.reserve_test_slot(
                kind="discovery",
                run_id="discovery-concurrent",
                repository_id=910000,
                requested_ordinal=1,
                policy=policy,
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            reservations = tuple(executor.map(lambda _index: reserve(), range(32)))

        assert len(set(reservations)) == 1
        assert store.reservation_count(
            "discovery-concurrent",
            kind="discovery",
        ) == 1


def test_reservation_ordinal_must_be_the_next_contiguous_value(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        with pytest.raises(module.OperationsIntegrityError):
            store.reserve_test_slot(
                kind="discovery",
                run_id="discovery-gap",
                repository_id=910000,
                requested_ordinal=2,
                policy=DiscoveryBudgetPolicyV1(),
            )
        assert store.reservation_count("discovery-gap", kind="discovery") == 0


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


def test_tampered_reservation_ordinal_is_rejected_before_reuse(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    database = tmp_path / "operations.sqlite3"
    with module.OperationsStateStore(database) as store:
        store.seed_test_reservations(
            run_id="discovery-tampered",
            repository_id=910001,
        )

    connection = sqlite3.connect(":memory:")
    connection.deserialize(database.read_bytes())
    connection.execute(
        """UPDATE operations_discovery_reservations
           SET ordinal = 2 WHERE run_id = 'discovery-tampered'"""
    )
    connection.commit()
    database.write_bytes(connection.serialize())
    connection.close()

    with pytest.raises(module.OperationsIntegrityError):
        module.OperationsStateStore(database)


@pytest.mark.parametrize("damage", ("authority", "status"))
def test_tampered_run_authority_or_status_is_rejected_before_reuse(
    tmp_path: Path,
    damage: str,
) -> None:
    module = _operations_module()
    database = tmp_path / f"operations-{damage}.sqlite3"
    with module.OperationsStateStore(database) as store:
        store.seed_test_reservations(
            run_id="discovery-tampered",
            repository_id=910001,
        )

    connection = sqlite3.connect(":memory:")
    connection.deserialize(database.read_bytes())
    if damage == "authority":
        connection.execute(
            """UPDATE operations_runs SET authority_digest = ?
               WHERE run_id = 'discovery-tampered'""",
            ("sha256:" + ("f" * 64),),
        )
    else:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            """UPDATE operations_runs SET status = 'refundable'
               WHERE run_id = 'discovery-tampered'"""
        )
    connection.commit()
    database.write_bytes(connection.serialize())
    connection.close()

    with pytest.raises(module.OperationsIntegrityError):
        module.OperationsStateStore(database)


def test_outcome_unknown_attempt_is_consumed_and_blocks_automatic_reentry(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        store.seed_test_reservations(
            run_id="discovery-unknown",
            repository_id=910001,
        )
        started = store.record_semantic_attempt(
            run_id="discovery-unknown",
            repository_id=910001,
            stage="extractor",
            attempt_no=1,
            status="started",
            recorded_at="2026-07-27T12:00:00.000000Z",
        )
        unknown = store.record_semantic_attempt(
            run_id="discovery-unknown",
            repository_id=910001,
            stage="extractor",
            attempt_no=1,
            status="semantic_outcome_unknown",
            recorded_at="2026-07-27T12:00:01.000000Z",
        )
        assert unknown.attempt_digest != started.attempt_digest
        with pytest.raises(module.OperationsIntegrityError):
            store.record_semantic_attempt(
                run_id="discovery-unknown",
                repository_id=910001,
                stage="extractor",
                attempt_no=2,
                status="started",
                recorded_at="2026-07-27T12:00:02.000000Z",
            )


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
