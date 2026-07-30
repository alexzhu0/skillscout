"""Wave-0 RED contract for the discovery-owned operations ledger."""

from __future__ import annotations

import importlib
import inspect
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from skillscout.adapters.publication_state import PublicationStateStore
from skillscout.adapters.state import SQLiteStateStore
from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
    DiscoveredCandidateV1,
    DiscoveryBudgetPolicyV1,
    DiscoveryCandidateTerminalV1,
    DiscoveryQuerySetV1,
    DiscoveryRunAuthorityV1,
    DiscoveryRunSummaryV1,
    SearchPageObservationV1,
    SearchRateLimitFactsV1,
    SearchRepositoryObservationV1,
)
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.acceptance import (
    AcceptanceFixedCandidateAdmissionV1,
    BenchmarkEntryV1,
    BenchmarkLockAttestationV1,
    HostedIsolationCapabilityV1,
    LockedBenchmarkManifestV1,
    NominationEntryV1,
    NominationSetV1,
    OfflineAdversarialRunV1,
    PublicationReplayCompletionV1,
    ReplayIntentV1,
    ReplayEvidenceV1,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "state_branch" / "valid_state.json"
FORBIDDEN_SCHEMA_OWNERS = {
    "runs",
    "stage_attempts",
    "stage_results",
    "phase3_candidate_runs",
    "publication_attempts",
    "publication_checkpoints",
}
TIMESTAMP = "2026-07-27T12:00:00.000000Z"
DIGEST_A = "sha256:" + ("a" * 64)
DIGEST_B = "sha256:" + ("b" * 64)
DIGEST_C = "sha256:" + ("c" * 64)


def _digest_values(values: dict[str, object]) -> str:
    def json_value(value: object) -> object:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", exclude_none=False)
        if isinstance(value, tuple):
            return [json_value(item) for item in value]
        return value

    return sha256_digest({key: json_value(value) for key, value in values.items()})


def _authority() -> DiscoveryRunAuthorityV1:
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config" / "discovery-queries-v1.json").read_bytes(),
        strict=True,
    )
    budget = DiscoveryBudgetPolicyV1()
    values = {
        "schema_version": "discovery-run-authority-v1",
        "run_id": "discovery-operations",
        "query_set_digest": query_set.query_set_digest,
        "budget_policy_digest": budget.budget_policy_digest,
        "phase2_profile_version": "phase2-v1",
        "phase3_profile_version": "phase3-profile-v1",
        "semantic_provider": "openai",
        "extractor_model_id": "gpt-5.6-terra",
        "generator_model_id": "gpt-5.6-terra",
        "reviewer_model_id": "gpt-5.6-terra",
        "initial_state_root_digest": DIGEST_A,
    }
    return DiscoveryRunAuthorityV1(
        **values,
        authority_digest=_digest_values(values),
    )


def _page(authority: DiscoveryRunAuthorityV1) -> SearchPageObservationV1:
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config" / "discovery-queries-v1.json").read_bytes(),
        strict=True,
    )
    values = {
        "schema_version": "search-page-observation-v1",
        "discovery_run_authority_digest": authority.authority_digest,
        "query_set_version": query_set.query_set_version,
        "query_set_digest": query_set.query_set_digest,
        "query_id": query_set.queries[0].query_id,
        "query_ordinal": 1,
        "query_text": query_set.queries[0].query_text,
        "sort": "updated",
        "order": "desc",
        "page": 1,
        "per_page": 25,
        "next_page": None,
        "total_count": 1,
        "incomplete_results": False,
        "item_count": 1,
        "request_id": "request-operations",
        "rate_limit": SearchRateLimitFactsV1(
            limit=30,
            remaining=29,
            used=1,
            reset_epoch=1,
            resource="search",
        ),
    }
    return SearchPageObservationV1(
        **values,
        observation_digest=_digest_values(values),
    )


def _candidate(
    authority: DiscoveryRunAuthorityV1,
    page: SearchPageObservationV1,
) -> DiscoveredCandidateV1:
    repository_values = {
        "schema_version": "search-repository-observation-v1",
        "repository_id": 910001,
        "owner": "octo-org",
        "name": "workflow-kit",
        "full_name": "octo-org/workflow-kit",
        "private": False,
        "visibility": "public",
        "fork": False,
        "archived": False,
        "disabled": False,
        "default_branch": "main",
    }
    repository = SearchRepositoryObservationV1(
        **repository_values,
        observation_digest=sha256_digest(repository_values),
    )
    values = {
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
    return DiscoveredCandidateV1(
        **values,
        candidate_digest=_digest_values(values),
    )


def _operations_module():
    return importlib.import_module("skillscout.adapters.operations_state")


def _acceptance_replay() -> ReplayIntentV1:
    return ReplayIntentV1(
        schema_version="replay-intent-v1",
        acceptance_run_id="acceptance-operations",
        repository_id=101,
        source_commit_sha="a" * 40,
        workflow_fingerprint=DIGEST_A,
        workflow_spec_authority_digest=DIGEST_B,
        replay_policy_version="acceptance-replay-policy-v1",
        benchmark_manifest_digest=DIGEST_C,
        before_state_commit_sha="c" * 40,
        before_state_root_digest="sha256:" + ("d" * 64),
        before_projection_digest=DIGEST_A,
        before_object_digests=(DIGEST_B,),
        semantic_request_count=0,
        remote_effect_count=0,
        recorded_at=TIMESTAMP,
    )


def _acceptance_replay_completion(
    replay: ReplayIntentV1,
    *,
    recorded_at: str = "2026-07-27T12:01:00.000000Z",
) -> PublicationReplayCompletionV1:
    return PublicationReplayCompletionV1(
        schema_version="publication-replay-completion-v1",
        acceptance_run_id=replay.acceptance_run_id,
        replay_intent_digest=replay.replay_digest,
        repository_id=replay.repository_id,
        source_commit_sha=replay.source_commit_sha,
        workflow_fingerprint=replay.workflow_fingerprint,
        workflow_spec_authority_digest=replay.workflow_spec_authority_digest,
        publication_policy_version="publication-policy-v1",
        publication_key=DIGEST_A,
        publication_marker=DIGEST_B,
        target_repository_id=202,
        target_repository_full_name="catalog-org/skills",
        pull_request_number=17,
        head_branch="skillscout/bounded-workflow",
        head_commit_sha="b" * 40,
        draft=True,
        open=True,
        prior_publication_receipt_digest=DIGEST_C,
        before_remote_observation_digest=DIGEST_B,
        after_remote_observation_digest=DIGEST_B,
        branch_create_count=0,
        commit_create_count=0,
        pull_request_create_count=0,
        pull_request_update_count=0,
        reviewer_request_count=0,
        completion_recorded_at=recorded_at,
    )


def _acceptance_replay_evidence(replay: ReplayIntentV1) -> ReplayEvidenceV1:
    return ReplayEvidenceV1(
        schema_version="replay-evidence-v1",
        acceptance_run_id=replay.acceptance_run_id,
        repository_id=replay.repository_id,
        source_commit_sha=replay.source_commit_sha,
        workflow_fingerprint=replay.workflow_fingerprint,
        workflow_spec_authority_digest=replay.workflow_spec_authority_digest,
        replay_policy_version=replay.replay_policy_version,
        replay_fact_digest=replay.replay_digest,
        allowed_delta_fact_digests=(replay.replay_digest,),
        benchmark_manifest_digest=replay.benchmark_manifest_digest,
        before_state_commit_sha=replay.before_state_commit_sha,
        before_state_root_digest=replay.before_state_root_digest,
        after_state_commit_sha="e" * 40,
        after_state_root_digest="sha256:" + ("f" * 64),
        before_projection_digest=replay.before_projection_digest,
        after_projection_digest=replay.before_projection_digest,
        before_object_digests=replay.before_object_digests,
        after_object_digests=replay.before_object_digests,
        scenario_result_digests=tuple(
            "sha256:" + f"{index:064x}" for index in range(1, 6)
        ),
        eligible_locators=("state/objects/eligible.json",),
        semantic_attempt_count_before=3,
        semantic_attempt_count_after=3,
        semantic_request_count=0,
        duplicate_workflow_spec_count=0,
        duplicate_skill_count=0,
        duplicate_fact_count=0,
        remote_effect_count=0,
        recorded_at=TIMESTAMP,
    )


def _hosted_capability() -> HostedIsolationCapabilityV1:
    return HostedIsolationCapabilityV1(
        schema_version="hosted-isolation-capability-v1",
        workflow_sha256=DIGEST_A,
        source_commit_sha="a" * 40,
        hosted_run_id=1001,
        run_attempt=1,
        runner_image="github-actions-ubuntu-24.04",
        isolation_mechanism="docker_network_none",
        probe_artifact_locator="phase6/probes/1001/1",
        probe_artifact_digest=DIGEST_A,
        control_command_digest=DIGEST_A,
        direct_probe_command_digest=DIGEST_B,
        child_probe_command_digest=DIGEST_C,
        control_outcome="passed",
        direct_network_outcome="denied",
        child_network_outcome="denied",
        credential_count=0,
        state_write_capability=False,
        synthetic_scan_manifest_digest=DIGEST_B,
        synthetic_canary_hit_count=0,
        reviewer_id="security-reviewer",
        reviewed_at=TIMESTAMP,
    )


def _offline_run(
    capability: HostedIsolationCapabilityV1,
) -> OfflineAdversarialRunV1:
    scenario_ids = tuple(f"scenario-{index:02d}" for index in range(1, 16))
    return OfflineAdversarialRunV1(
        schema_version="offline-adversarial-run-v1",
        acceptance_run_id="acceptance-operations",
        hosted_capability_digest=capability.capability_digest,
        workflow_sha256=capability.workflow_sha256,
        source_commit_sha=capability.source_commit_sha,
        hosted_run_id=capability.hosted_run_id,
        run_attempt=capability.run_attempt,
        isolation_mechanism=capability.isolation_mechanism,
        scenario_matrix_digest=DIGEST_C,
        required_scenario_ids=scenario_ids,
        completed_scenario_ids=scenario_ids,
        scenario_result_digests=tuple("sha256:" + f"{index:064x}" for index in range(1, 16)),
        controlled_scenario_count=15,
        os_syscall_network_denied=True,
        direct_network_denied=True,
        child_network_denied=True,
        untrusted_execution_count=0,
        unapproved_network_effect_count=0,
        unauthorized_effect_count=0,
        synthetic_scan_manifest_digest=capability.synthetic_scan_manifest_digest,
        synthetic_canary_hit_count=0,
        started_at=TIMESTAMP,
        completed_at="2026-07-27T12:01:00.000000Z",
    )


def _nomination_set() -> NominationSetV1:
    entries = tuple(
        sorted(
            (
                NominationEntryV1(
                    schema_version="nomination-entry-v1",
                    repository_full_name=f"fixture/repository-{index}",
                    repository_id=index,
                    exact_commit_sha=f"{index:040x}",
                    license_spdx="MIT",
                    selection_source="search_derived",
                    selection_evidence_digests=(DIGEST_A, DIGEST_B),
                )
                for index in range(1, 6)
            ),
            key=lambda entry: entry.entry_digest,
        )
    )
    return NominationSetV1(
        schema_version="nomination-set-v1",
        nomination_set_id="nomination-operations",
        query_set_digest=DIGEST_A,
        search_run_authority_digest=DIGEST_B,
        search_derived_entries=entries,
        user_nominated_entries=(),
        created_at=TIMESTAMP,
    )


def _locked_manifest(
    nomination: NominationSetV1,
) -> LockedBenchmarkManifestV1:
    roles = ("positive", "positive_multi_workflow", "negative", "negative", "borderline")
    entries = tuple(
        sorted(
            (
                BenchmarkEntryV1(
                    schema_version="benchmark-entry-v1",
                    repository_full_name=entry.repository_full_name,
                    repository_id=entry.repository_id,
                    exact_commit_sha=entry.exact_commit_sha,
                    license_spdx=entry.license_spdx,
                    selection_source=entry.selection_source,
                    coverage_role=role,
                    nomination_entry_digest=entry.entry_digest,
                    selection_evidence_digests=entry.selection_evidence_digests,
                )
                for entry, role in zip(
                    nomination.search_derived_entries,
                    roles,
                    strict=True,
                )
            ),
            key=lambda entry: entry.entry_digest,
        )
    )
    preimage = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": nomination.nomination_set_digest,
        "entries": [
            entry.model_dump(mode="json", exclude_none=False)
            for entry in entries
        ],
        "prior_manifest_digest": None,
    }
    manifest_digest = sha256_digest(preimage)
    return LockedBenchmarkManifestV1(
        **preimage,
        lock_attestation=BenchmarkLockAttestationV1(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=nomination.nomination_set_digest,
            manifest_digest=manifest_digest,
            reviewer_id="reviewer",
            locked_at=TIMESTAMP,
        ),
        manifest_digest=manifest_digest,
    )


def test_acceptance_fact_registry_is_exact_and_immutable() -> None:
    module = _operations_module()
    assert tuple(module.ACCEPTANCE_FACT_MODELS) == (
        "acceptance_nomination",
        "acceptance_benchmark_lock",
        "acceptance_live_authority",
        "acceptance_budget_reservation",
        "acceptance_fixed_candidate_admission",
        "acceptance_semantic_request_reservation",
        "acceptance_scenario",
        "acceptance_hosted_isolation_capability",
        "acceptance_offline_adversarial_run",
        "acceptance_replay",
        "acceptance_replay_evidence",
        "acceptance_changed_source",
        "acceptance_publication_replay_completion",
        "acceptance_changed_source_draft_update_completion",
        "acceptance_gate_b4",
        "acceptance_human_review",
        "acceptance_cleanup",
        "acceptance_reviewer_calibration",
        "acceptance_gate",
        "acceptance_report_root",
    )
    with pytest.raises(TypeError):
        module.ACCEPTANCE_FACT_MODELS["acceptance_replay"] = object


def test_fixed_acceptance_candidate_never_fabricates_search_page_or_candidate(
    tmp_path: Path,
) -> None:
    """The acceptance-only graph has no operational Search-page foreign key."""

    module = _operations_module()
    authority = _authority()
    admission = AcceptanceFixedCandidateAdmissionV1(
        schema_version="acceptance-fixed-candidate-admission-v1",
        acceptance_run_id="acceptance-fixed",
        benchmark_manifest_digest=DIGEST_A,
        nomination_entry_digest=DIGEST_B,
        benchmark_entry_digest=DIGEST_C,
        repository_id=101,
        repository_full_name="example/workflow",
        exact_commit_sha="a" * 40,
        license_spdx="MIT",
        ordinal=1,
        admitted_at=TIMESTAMP,
    )
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        store.create_run(authority, TIMESTAMP)
        semantic = store.reserve_acceptance_semantic_candidate(
            authority.run_id,
            admission,
            DIGEST_A,
            TIMESTAMP,
        )
        snapshot = store.snapshot_run(authority.run_id)
        connection = store._connection
        assert connection is not None
        candidate_count = connection.execute(
            "SELECT COUNT(*) FROM operations_candidates"
        ).fetchone()[0]
        page_count = connection.execute(
            "SELECT COUNT(*) FROM operations_search_pages"
        ).fetchone()[0]

    assert semantic.discovery_reservation_digest == admission.admission_digest
    assert snapshot.candidates == ()
    assert snapshot.discovery_reservations == ()
    assert candidate_count == 0
    assert page_count == 0


def test_acceptance_semantic_request_budget_blocks_twenty_first_before_attempt(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    nomination = _nomination_set()
    manifest = _locked_manifest(nomination)
    entry = manifest.entries[0]
    admission = AcceptanceFixedCandidateAdmissionV1(
        schema_version="acceptance-fixed-candidate-admission-v1",
        acceptance_run_id="acceptance-fixed",
        benchmark_manifest_digest=manifest.manifest_digest,
        nomination_entry_digest=entry.nomination_entry_digest,
        benchmark_entry_digest=entry.entry_digest,
        repository_id=entry.repository_id,
        repository_full_name=entry.repository_full_name,
        exact_commit_sha=entry.exact_commit_sha,
        license_spdx=entry.license_spdx,
        ordinal=1,
        admitted_at=TIMESTAMP,
    )
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        store.record_acceptance_fact(
            admission.acceptance_run_id,
            "acceptance_nomination",
            nomination,
        )
        store.record_acceptance_fact(
            admission.acceptance_run_id,
            "acceptance_benchmark_lock",
            manifest,
        )
        store.record_acceptance_fact(
            admission.acceptance_run_id,
            "acceptance_fixed_candidate_admission",
            admission,
        )
        for ordinal in range(1, 21):
            store.reserve_acceptance_semantic_request(
                acceptance_run_id=admission.acceptance_run_id,
                fixed_candidate_admission_digest=admission.admission_digest,
                repository_id=admission.repository_id,
                workflow_spec_authority_digest=(
                    "sha256:" + f"{ordinal:064x}"
                ),
                stage="extractor",
                attempt_no=1,
                reserved_at=TIMESTAMP,
            )
        with pytest.raises(module.BudgetExhausted):
            store.reserve_acceptance_semantic_request(
                acceptance_run_id=admission.acceptance_run_id,
                fixed_candidate_admission_digest=admission.admission_digest,
                repository_id=admission.repository_id,
                workflow_spec_authority_digest="sha256:" + ("f" * 64),
                stage="reviewer",
                attempt_no=1,
                reserved_at=TIMESTAMP,
            )
        snapshot = store.acceptance_snapshot(admission.acceptance_run_id)

    assert (
        len(
            tuple(
                fact
                for fact in snapshot.facts
                if fact.kind == "acceptance_semantic_request_reservation"
            )
        )
        == 20
    )


def test_pre_budget_state_requires_explicit_acceptance_schema_upgrade(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    path = tmp_path / "operations.sqlite3"
    connection = sqlite3.connect(path)
    try:
        for statement in module._schema_statements(
            module._PRE_BUDGET_ACCEPTANCE_FACT_KINDS
        ):
            connection.execute(statement)
        connection.execute(f"PRAGMA user_version = {module.OPERATIONS_SCHEMA_VERSION}")
        connection.commit()
    finally:
        connection.close()
    path.chmod(0o600)

    with module.OperationsStateStore(path) as store:
        store.upgrade_acceptance_schema()
        exported = store.export_owned_state()

    assert exported.schema_fingerprint == module._schema_fingerprint()


def test_acceptance_intent_and_completion_coexist_idempotently(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    replay = _acceptance_replay()
    completion = _acceptance_replay_completion(replay)
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        first = store.record_acceptance_fact(
            replay.acceptance_run_id,
            "acceptance_replay",
            replay,
        )
        second = store.record_acceptance_fact(
            replay.acceptance_run_id,
            "acceptance_publication_replay_completion",
            completion,
        )
        assert (
            store.record_acceptance_fact(
                replay.acceptance_run_id,
                "acceptance_publication_replay_completion",
                completion,
            )
            == second
        )
        snapshot = store.acceptance_snapshot(replay.acceptance_run_id)
        assert tuple(item.kind for item in snapshot.facts) == (
            "acceptance_publication_replay_completion",
            "acceptance_replay",
        )
        assert {item.fact_digest for item in snapshot.facts} == {
            first.fact_digest,
            second.fact_digest,
        }
        with pytest.raises(module.OperationsIntegrityError):
            store.record_acceptance_fact(
                replay.acceptance_run_id,
                "acceptance_publication_replay_completion",
                _acceptance_replay_completion(
                    replay,
                    recorded_at="2026-07-27T12:02:00.000000Z",
                ),
            )


def test_acceptance_capability_reference_and_owned_rebuild_are_exact(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    capability = _hosted_capability()
    offline = _offline_run(capability)
    source = tmp_path / "operations.sqlite3"
    with module.OperationsStateStore(source) as store:
        with pytest.raises(module.OperationsIntegrityError):
            store.record_acceptance_fact(
                offline.acceptance_run_id,
                "acceptance_offline_adversarial_run",
                offline,
            )
        store.record_acceptance_fact(
            offline.acceptance_run_id,
            "acceptance_hosted_isolation_capability",
            capability,
        )
        store.record_acceptance_fact(
            offline.acceptance_run_id,
            "acceptance_offline_adversarial_run",
            offline,
        )
        exported = store.export_owned_state()

    rebuilt = tmp_path / "rebuilt.sqlite3"
    module.OperationsStateStore.rebuild_owned_state(rebuilt, exported)
    with module.OperationsStateStore(rebuilt) as store:
        fresh = store.export_owned_state()
    assert fresh.facts == exported.facts
    assert fresh.projection == exported.projection
    assert (
        fresh.database_bytes == exported.database_bytes
        and fresh.database_digest == exported.database_digest
    )


def test_replay_evidence_requires_intent_and_survives_owned_rebuild(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    replay = _acceptance_replay()
    evidence = _acceptance_replay_evidence(replay)
    source = tmp_path / "operations.sqlite3"
    with module.OperationsStateStore(source) as store:
        with pytest.raises(module.OperationsIntegrityError):
            store.record_acceptance_fact(
                replay.acceptance_run_id,
                "acceptance_replay_evidence",
                evidence,
            )
        store.record_acceptance_fact(
            replay.acceptance_run_id,
            "acceptance_replay",
            replay,
        )
        store.record_acceptance_fact(
            replay.acceptance_run_id,
            "acceptance_replay_evidence",
            evidence,
        )
        exported = store.export_owned_state()

    rebuilt = tmp_path / "rebuilt-replay.sqlite3"
    module.OperationsStateStore.rebuild_owned_state(rebuilt, exported)
    with module.OperationsStateStore(rebuilt) as fresh:
        snapshot = fresh.acceptance_snapshot(replay.acceptance_run_id)
        assert tuple(item.kind for item in snapshot.facts) == (
            "acceptance_replay",
            "acceptance_replay_evidence",
        )
        assert snapshot.facts[1].fact == evidence
        assert fresh.export_owned_state().projection == exported.projection


def test_nomination_entries_round_trip_through_owned_state(tmp_path: Path) -> None:
    module = _operations_module()
    nomination = _nomination_set()
    source = tmp_path / "nomination-source.sqlite3"
    with module.OperationsStateStore(source) as store:
        recorded = store.record_acceptance_fact(
            nomination.nomination_set_id,
            "acceptance_nomination",
            nomination,
        )
        assert recorded.fact_digest == nomination.nomination_set_digest
        exported = store.export_owned_state()

    rebuilt = tmp_path / "nomination-rebuilt.sqlite3"
    module.OperationsStateStore.rebuild_owned_state(rebuilt, exported)
    with module.OperationsStateStore(rebuilt) as store:
        snapshot = store.acceptance_snapshot(nomination.nomination_set_id)
        fresh = store.export_owned_state()

    assert snapshot.facts[0].fact == nomination
    assert fresh.facts == exported.facts
    assert fresh.projection == exported.projection
    assert (
        fresh.database_bytes == exported.database_bytes
        and fresh.database_digest == exported.database_digest
    )


def test_acceptance_kind_model_and_run_binding_fail_before_mutation(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    replay = _acceptance_replay()
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        with pytest.raises((TypeError, module.OperationsIntegrityError)):
            store.record_acceptance_fact(
                replay.acceptance_run_id,
                "acceptance_scenario",
                replay,
            )
        with pytest.raises(module.OperationsIntegrityError):
            store.record_acceptance_fact(
                "other-acceptance-run",
                "acceptance_replay",
                replay,
            )
        assert store.acceptance_snapshot(replay.acceptance_run_id).facts == ()


def test_state_fixture_is_bounded_canonical_and_database_owner_complete() -> None:
    payload = FIXTURE.read_bytes()
    assert len(payload) < 16_384
    assert (
        payload
        == json.dumps(
            json.loads(payload),
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n"
    )
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
    existing = (ROOT / "src" / "skillscout" / "adapters" / "state.py").read_text()
    publication = (ROOT / "src" / "skillscout" / "adapters" / "publication_state.py").read_text()
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
    assert not public.intersection({"refund", "delete_reservation", "reset_budget", "prune"})


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
        assert tuple(item.ordinal for item in reservations) == tuple(range(1, limit + 1))
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
        assert (
            store.reservation_count(
                "discovery-wave0",
                kind=kind,
            )
            == limit
        )
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
        assert (
            store.reservation_count(
                "discovery-concurrent",
                kind="discovery",
            )
            == 1
        )


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


def test_semantic_attempt_identity_isolated_per_workflow_authority(
    tmp_path: Path,
) -> None:
    """Sibling Phase 3 workflows must never share one attempt key."""

    module = _operations_module()
    workflow_a = sha256_digest({"workflow": "a"})
    workflow_b = sha256_digest({"workflow": "b"})
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        store.seed_test_reservations(
            run_id="discovery-siblings",
            repository_id=910001,
        )
        first = store.record_semantic_attempt(
            run_id="discovery-siblings",
            repository_id=910001,
            workflow_authority_digest=workflow_a,
            stage="generator",
            attempt_no=1,
            status="started",
            recorded_at="2026-07-27T12:00:00.000000Z",
        )
        second = store.record_semantic_attempt(
            run_id="discovery-siblings",
            repository_id=910001,
            workflow_authority_digest=workflow_b,
            stage="generator",
            attempt_no=1,
            status="started",
            recorded_at="2026-07-27T12:00:01.000000Z",
        )

        assert first.workflow_authority_digest == workflow_a
        assert second.workflow_authority_digest == workflow_b
        assert first.attempt_digest != second.attempt_digest


def test_workflow_terminals_and_run_snapshot_preserve_exact_eligible_set(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    authority = _authority()
    page = _page(authority)
    candidate = _candidate(authority, page)
    workflow_a = sha256_digest({"workflow": "eligible"})
    workflow_b = sha256_digest({"workflow": "rejected"})
    locator = "state/objects/sha256/aa/" + ("a" * 64) + ".json"
    with module.OperationsStateStore(tmp_path / "operations.sqlite3") as store:
        store.create_run(authority, TIMESTAMP)
        store.record_search_page(authority.run_id, page, (candidate,))
        store.reserve_discovery_candidate(authority.run_id, candidate, TIMESTAMP)
        store.record_workflow_terminal(
            run_id=authority.run_id,
            repository_id=candidate.repository.repository_id,
            workflow_authority_digest=workflow_a,
            outcome="eligible_local_candidate",
            eligible_locator=locator,
            eligible_object_digest="sha256:" + ("a" * 64),
            recorded_at=TIMESTAMP,
        )
        store.record_workflow_terminal(
            run_id=authority.run_id,
            repository_id=candidate.repository.repository_id,
            workflow_authority_digest=workflow_b,
            outcome="review_rejected",
            eligible_locator=None,
            eligible_object_digest=None,
            recorded_at=TIMESTAMP,
        )

        snapshot = store.snapshot_run(authority.run_id)

    assert snapshot.search_pages == (page,)
    assert snapshot.candidates == (candidate,)
    assert tuple(item.workflow_authority_digest for item in snapshot.workflow_terminals) == (
        workflow_a,
        workflow_b,
    )
    assert tuple(
        item.workflow_authority_digest
        for item in snapshot.workflow_terminals
        if item.outcome == "eligible_local_candidate"
    ) == (workflow_a,)


def test_operations_store_rejects_legacy_ambiguous_semantic_attempt_schema(
    tmp_path: Path,
) -> None:
    """A database without workflow-bound attempt identity fails closed."""

    module = _operations_module()
    database = tmp_path / "legacy-operations.sqlite3"
    with module.OperationsStateStore(database) as store:
        store.seed_test_reservations(
            run_id="discovery-legacy",
            repository_id=910001,
        )

    connection = sqlite3.connect(":memory:")
    connection.deserialize(database.read_bytes())
    connection.execute("ALTER TABLE operations_semantic_attempts RENAME TO legacy_attempts")
    connection.execute(
        """CREATE TABLE operations_semantic_attempts (
            attempt_digest TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            repository_id INTEGER NOT NULL,
            stage TEXT NOT NULL,
            attempt_no INTEGER NOT NULL,
            status TEXT NOT NULL,
            attempt_json TEXT NOT NULL,
            UNIQUE (run_id, repository_id, stage, attempt_no)
        )"""
    )
    connection.commit()
    database.write_bytes(connection.serialize())
    connection.close()

    with pytest.raises(module.OperationsIntegrityError):
        module.OperationsStateStore(database)


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

    tampered = exported.model_copy(update={"projection_digest": "sha256:" + ("f" * 64)})
    with pytest.raises(Exception):
        module.OperationsStateStore.rebuild_owned_state(
            tmp_path / "rejected.sqlite3",
            tampered,
        )


def test_complete_typed_discovery_chain_round_trips_through_owned_json(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    authority = _authority()
    page = _page(authority)
    candidate = _candidate(authority, page)
    source = tmp_path / "typed-source.sqlite3"
    with module.OperationsStateStore(source) as store:
        store.create_run(authority, TIMESTAMP)
        store.record_search_page(authority.run_id, page, (candidate,))
        discovery = store.reserve_discovery_candidate(
            authority.run_id,
            candidate,
            TIMESTAMP,
        )
        semantic = store.reserve_semantic_candidate(
            authority.run_id,
            candidate.repository.repository_id,
            DIGEST_B,
            TIMESTAMP,
        )
        store.record_semantic_attempt(
            run_id=authority.run_id,
            repository_id=candidate.repository.repository_id,
            stage="extractor",
            attempt_no=1,
            status="started",
            recorded_at=TIMESTAMP,
        )
        store.record_semantic_attempt(
            run_id=authority.run_id,
            repository_id=candidate.repository.repository_id,
            stage="extractor",
            attempt_no=1,
            status="semantic_outcome_unknown",
            recorded_at="2026-07-27T12:00:01.000000Z",
        )
        terminal_values = {
            "schema_version": "discovery-candidate-terminal-v1",
            "discovery_run_authority_digest": authority.authority_digest,
            "repository_id": candidate.repository.repository_id,
            "semantic_reservation_digest": semantic.reservation_digest,
            "outcome": "semantic_outcome_unknown",
            "workflow_authority_digests": (),
            "recorded_at": "2026-07-27T12:00:01.000000Z",
        }
        terminal = DiscoveryCandidateTerminalV1(
            **terminal_values,
            terminal_digest=sha256_digest(terminal_values),
        )
        store.record_candidate_terminal(authority.run_id, terminal)
        summary_values = {
            "schema_version": "discovery-run-summary-v1",
            "discovery_run_authority_digest": authority.authority_digest,
            "status": "completed_degraded",
            "selected_candidate_count": 1,
            "semantic_reservation_count": 1,
            "business_terminal_count": 0,
            "quarantined_candidate_count": 1,
            "confirmed_retryable_count": 0,
            "integrity_conflict_count": 0,
            "permanent_failure_count": 0,
            "terminal_digests": (terminal.terminal_digest,),
            "completed_at": "2026-07-27T12:00:02.000000Z",
        }
        summary = DiscoveryRunSummaryV1(
            **summary_values,
            summary_digest=sha256_digest(summary_values),
        )
        store.record_run_summary(authority.run_id, summary)
        exported = store.export_owned_state()

    assert discovery.ordinal == semantic.ordinal == 1
    assert len(exported.projection.search_page_digests) == 1
    assert len(exported.projection.candidate_digests) == 1
    assert len(exported.projection.run_summary_digests) == 1
    rebuilt = tmp_path / "typed-rebuilt.sqlite3"
    module.OperationsStateStore.rebuild_owned_state(rebuilt, exported)
    with module.OperationsStateStore(rebuilt) as store:
        assert store.export_owned_state().facts == exported.facts


def test_corrupt_database_bytes_rebuild_from_complete_owned_json(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    with module.OperationsStateStore(tmp_path / "source.sqlite3") as store:
        store.seed_test_reservations(
            run_id="discovery-rebuild",
            repository_id=910001,
        )
        store.record_test_terminal(
            run_id="discovery-rebuild",
            repository_id=910001,
            outcome="semantic_outcome_unknown",
        )
        exported = store.export_owned_state()

    corrupt = exported.model_copy(
        update={
            "database_bytes": b"not-a-sqlite-database",
            "database_digest": sha256_digest(b"not-a-sqlite-database"),
        }
    )
    rebuilt = tmp_path / "rebuilt.sqlite3"
    module.OperationsStateStore.rebuild_owned_state(rebuilt, corrupt)
    with module.OperationsStateStore(rebuilt) as store:
        restored = store.export_owned_state()
    assert restored.facts == exported.facts
    assert restored.projection == exported.projection


@pytest.mark.parametrize("damage", ("database_digest", "missing_fact", "reordered"))
def test_valid_database_with_wrong_owned_authority_fails_closed(
    tmp_path: Path,
    damage: str,
) -> None:
    module = _operations_module()
    with module.OperationsStateStore(tmp_path / "source.sqlite3") as store:
        store.seed_test_reservations(
            run_id="discovery-rebuild",
            repository_id=910001,
        )
        exported = store.export_owned_state()

    if damage == "database_digest":
        tampered = exported.model_copy(update={"database_digest": "sha256:" + ("f" * 64)})
    elif damage == "missing_fact":
        tampered = exported.model_copy(update={"facts": exported.facts[:-1]})
    else:
        tampered = exported.model_copy(update={"facts": tuple(reversed(exported.facts))})
    with pytest.raises(module.OperationsIntegrityError):
        module.OperationsStateStore.rebuild_owned_state(
            tmp_path / f"rejected-{damage}.sqlite3",
            tampered,
        )


def test_failed_owned_snapshot_exposes_previous_complete_database(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    active = False

    def fail_after_replace(operation: str) -> None:
        if active and operation == "before_operations_state_directory_fsync":
            raise OSError("simulated killed writer")

    database = tmp_path / "operations.sqlite3"
    store = module.OperationsStateStore(database, filesystem_seam=fail_after_replace)
    before = database.read_bytes()
    active = True
    with pytest.raises(module.OperationsStateError):
        store.seed_test_reservations(
            run_id="discovery-killed",
            repository_id=910001,
        )
    store.close()
    assert database.read_bytes() == before
    with module.OperationsStateStore(database) as reopened:
        assert (
            reopened.reservation_count(
                "discovery-killed",
                kind="discovery",
            )
            == 0
        )


def test_three_store_bundle_has_exact_paths_and_round_trips_owner_projections(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    pipeline = SQLiteStateStore(tmp_path / "pipeline.sqlite3")
    operations = module.OperationsStateStore(tmp_path / "operations.sqlite3")
    publication = PublicationStateStore(tmp_path / "publication.sqlite3")
    try:
        bundle = module.assemble_three_store_bundle(
            pipeline_store=pipeline,
            operations_store=operations,
            publication_store=publication,
            prior_root_digest=None,
            state_parent_commit_sha="0" * 40,
            query_set_digest=DIGEST_A,
            budget_policy_digest=DIGEST_B,
            created_at=TIMESTAMP,
        )
        original = (
            pipeline.export_owned_state().projection,
            operations.export_owned_state().projection,
            publication.export_owned_state().projection,
        )
    finally:
        publication.close()
        operations.close()
        pipeline.close()

    paths = {item.path for item in bundle.files}
    assert {
        "state/root.json",
        "state/databases/pipeline.sqlite3",
        "state/databases/operations.sqlite3",
        "state/databases/publication.sqlite3",
    } < paths
    assert all(
        path
        in {
            "state/root.json",
            "state/databases/pipeline.sqlite3",
            "state/databases/operations.sqlite3",
            "state/databases/publication.sqlite3",
        }
        or path.startswith("state/objects/sha256/")
        for path in paths
    )

    restored = tmp_path / "restored"
    restored.mkdir(mode=0o700)
    projection = module.restore_three_store_bundle(
        bundle,
        pipeline_path=restored / "pipeline.sqlite3",
        operations_path=restored / "operations.sqlite3",
        publication_path=restored / "publication.sqlite3",
    )
    assert (
        projection.pipeline,
        projection.operations,
        projection.publication,
    ) == original


def test_three_store_restore_accepts_state_branch_file_order(
    tmp_path: Path,
) -> None:
    module = _operations_module()
    pipeline = SQLiteStateStore(tmp_path / "pipeline.sqlite3")
    operations = module.OperationsStateStore(tmp_path / "operations.sqlite3")
    publication = PublicationStateStore(tmp_path / "publication.sqlite3")
    try:
        bundle = module.assemble_three_store_bundle(
            pipeline_store=pipeline,
            operations_store=operations,
            publication_store=publication,
            prior_root_digest=None,
            state_parent_commit_sha="0" * 40,
            query_set_digest=DIGEST_A,
            budget_policy_digest=DIGEST_B,
            created_at=TIMESTAMP,
        )
    finally:
        publication.close()
        operations.close()
        pipeline.close()

    root_file = next(item for item in bundle.files if item.path == "state/root.json")
    restored_files = (
        root_file,
        *sorted(
            (item for item in bundle.files if item.path != "state/root.json"),
            key=lambda item: item.path,
        ),
    )
    restored_bundle = type(bundle)(bundle.root, restored_files)
    assert restored_bundle != bundle
    assert restored_bundle.root == bundle.root
    assert restored_bundle.content_by_path() == bundle.content_by_path()

    restored = tmp_path / "restored"
    restored.mkdir(mode=0o700)
    module.restore_three_store_bundle(
        restored_bundle,
        pipeline_path=restored / "pipeline.sqlite3",
        operations_path=restored / "operations.sqlite3",
        publication_path=restored / "publication.sqlite3",
    )


@pytest.mark.parametrize("damage", ("swapped_database", "object", "partial"))
def test_three_store_restore_rejects_bundle_mismatch_before_reuse(
    tmp_path: Path,
    damage: str,
) -> None:
    module = _operations_module()
    pipeline = SQLiteStateStore(tmp_path / "pipeline.sqlite3")
    operations = module.OperationsStateStore(tmp_path / "operations.sqlite3")
    publication = PublicationStateStore(tmp_path / "publication.sqlite3")
    try:
        bundle = module.assemble_three_store_bundle(
            pipeline_store=pipeline,
            operations_store=operations,
            publication_store=publication,
            prior_root_digest=None,
            state_parent_commit_sha="0" * 40,
            query_set_digest=DIGEST_A,
            budget_policy_digest=DIGEST_B,
            created_at=TIMESTAMP,
        )
    finally:
        publication.close()
        operations.close()
        pipeline.close()

    files = list(bundle.files)
    if damage == "swapped_database":
        by_path = {item.path: item for item in files}
        first = by_path["state/databases/pipeline.sqlite3"]
        second = by_path["state/databases/publication.sqlite3"]
        files[files.index(first)] = type(first)(first.path, second.content)
        files[files.index(second)] = type(second)(second.path, first.content)
    elif damage == "object":
        index = next(
            index for index, item in enumerate(files) if item.path.startswith("state/objects/")
        )
        files[index] = type(files[index])(files[index].path, b"{}")
    else:
        files.pop(
            next(
                index
                for index, item in enumerate(files)
                if item.path == "state/databases/operations.sqlite3"
            )
        )
    damaged = type(bundle)(bundle.root, tuple(files))
    with pytest.raises(Exception):
        module.restore_three_store_bundle(
            damaged,
            pipeline_path=tmp_path / "rejected" / "pipeline.sqlite3",
            operations_path=tmp_path / "rejected" / "operations.sqlite3",
            publication_path=tmp_path / "rejected" / "publication.sqlite3",
        )
    assert not (tmp_path / "rejected").exists()
