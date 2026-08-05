"""Wave-0 RED contracts for capability-separated acceptance orchestration."""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from skillscout.adapters.github import LicenseResponse, RateLimitFacts, RepoMetadata
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.acceptance import (
    LiveAcceptanceAuthorityV1,
    LiveAcceptanceAuthorityV2,
    LockedBenchmarkManifestV2,
    NominationEntryV1,
    NominationSetV1,
)
from skillscout.domain.discovery import (
    DiscoveryQuerySetV1,
    SearchPageObservationV1,
    SearchRateLimitFactsV1,
    SearchRepositoryObservationV1,
)


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-07-30T00:00:00.000000Z"
DIGEST = "sha256:" + ("a" * 64)


REQUIRED_APPLICATION_CONTRACTS = (
    "NominationDependencies",
    "LockedCampaignDependencies",
    "ReplayUpdateDependencies",
    "HumanAttestationDependencies",
    "CleanupAttestationDependencies",
    "LiveAuthorityDependencies",
    "AcceptanceRebuildDependencies",
)

EVALUATOR_ONLY_FIELDS = {
    "expected_role",
    "expected_outcome",
    "evaluator_notes",
    "human_label",
}
LIVE_CAPABILITY_FIELDS = {
    "semantic_client_factory",
    "extractor_factory",
    "generator_factory",
    "reviewer_factory",
    "publication_factory",
    "publisher_factory",
    "catalog_token_factory",
    "credential_factory",
}


def _application_module(*, skip_if_missing: bool) -> Any:
    if importlib.util.find_spec("skillscout.application.acceptance") is None:
        if skip_if_missing:
            pytest.skip("phase6-application-contracts-not-yet-implemented")
        return None
    return importlib.import_module("skillscout.application.acceptance")


def _fresh_live_evidence_for_manifest(manifest: Any) -> tuple[Any, Any]:
    """Minimal typed V2 evidence for application-only benchmark behavior tests."""

    lock_digest = sha256_digest({"fresh-lock": manifest.manifest_digest})
    lock = LockedBenchmarkManifestV2.model_construct(
        schema_version="locked-benchmark-manifest-v2",
        selection_manifest=manifest,
        entries=manifest.entries,
        lock_digest=lock_digest,
    )
    authority = LiveAcceptanceAuthorityV2.model_construct(
        schema_version="live-acceptance-authority-v2",
        manifest_digest=manifest.manifest_digest,
        benchmark_lock_digest=lock_digest,
        benchmark_lock=lock,
        authority_digest=sha256_digest({"fresh-authority": lock_digest}),
    )
    return lock, authority


def _symbol(name: str, *, skip_if_missing: bool = True) -> type[Any]:
    module = _application_module(skip_if_missing=skip_if_missing)
    if module is None:
        pytest.fail(f"phase6-missing-application-contract:{name}", pytrace=False)
    value = getattr(module, name, None)
    if value is None:
        if skip_if_missing:
            pytest.skip("phase6-application-contracts-not-yet-implemented")
        pytest.fail(f"phase6-missing-application-contract:{name}", pytrace=False)
    return value


@pytest.mark.parametrize(
    "contract",
    REQUIRED_APPLICATION_CONTRACTS,
    ids=REQUIRED_APPLICATION_CONTRACTS,
)
def test_required_phase6_application_contract_is_missing(contract: str) -> None:
    _symbol(contract, skip_if_missing=False)


def _field_names(contract: str) -> set[str]:
    model = _symbol(contract)
    assert dataclasses.is_dataclass(model)
    return {field.name for field in dataclasses.fields(model)}


def test_nomination_signature_has_search_state_only_and_no_hypothesis_channel() -> None:
    fields = _field_names("NominationDependencies")
    assert {"search_factory", "operations_store_factory"} <= fields
    assert fields.isdisjoint(LIVE_CAPABILITY_FIELDS)
    assert fields.isdisjoint(EVALUATOR_ONLY_FIELDS)
    assert fields.isdisjoint(
        {
            "phase2_factory",
            "phase3_factory",
            "model",
            "endpoint",
            "catalog",
            "reviewer_targets",
        }
    )


def test_nomination_search_filters_and_pins_role_neutral_entries() -> None:
    module = _application_module(skip_if_missing=False)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )
    repositories = []
    for index in range(1, 7):
        values = {
            "schema_version": "search-repository-observation-v1",
            "repository_id": 910000 + index,
            "owner": "octo-org",
            "name": f"workflow-{index}",
            "full_name": f"octo-org/workflow-{index}",
            "private": False,
            "visibility": "public",
            "fork": False,
            "archived": False,
            "disabled": False,
            "default_branch": "main",
        }
        repositories.append(
            SearchRepositoryObservationV1(
                **values,
                observation_digest=sha256_digest(values),
            )
        )

    class Search:
        def search_repositories(
            self,
            *,
            query_set: DiscoveryQuerySetV1,
            discovery_run_authority_digest: str,
            query_ordinal: int,
            page: int,
        ) -> tuple[SearchPageObservationV1, tuple[SearchRepositoryObservationV1, ...]]:
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
                "total_count": len(repositories),
                "incomplete_results": False,
                "item_count": len(repositories),
                "request_id": f"request-{query_ordinal}-{page}",
                "rate_limit": SearchRateLimitFactsV1(
                    limit=30,
                    remaining=29,
                    used=1,
                    reset_epoch=1,
                    resource="search",
                ),
            }
            return (
                SearchPageObservationV1(
                    **values,
                    observation_digest=sha256_digest(
                        {
                            **values,
                            "rate_limit": values["rate_limit"].model_dump(
                                mode="json", exclude_none=False
                            ),
                        }
                    ),
                ),
                tuple(repositories),
            )

        def get_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
            index = int(repo.rpartition("-")[2])
            return RepoMetadata(
                id=910000 + index,
                owner=owner,
                name=repo,
                default_branch="main",
                private=False,
                fork=False,
                archived=False,
                disabled=False,
                visibility="public",
                license_spdx="GPL-3.0" if index == 6 else "MIT",
                rate_limit=RateLimitFacts(limit=5000, remaining=4999, reset=1),
            )

        def resolve_commit(self, owner: str, repo: str, ref: str) -> str:
            return f"{int(repo.rpartition('-')[2]):040x}"

        def get_license(self, owner: str, repo: str, sha: str) -> LicenseResponse:
            index = int(repo.rpartition("-")[2])
            return LicenseResponse(
                status="confirmed",
                spdx_id="GPL-3.0" if index == 6 else "MIT",
                license_blob_sha=f"{index + 100:040x}",
            )

        def close(self) -> None:
            pass

    nomination = module.nominate_search_candidates(
        search=Search(),
        query_set=query_set,
        search_run_authority_digest=DIGEST,
        nomination_set_id="nomination-search",
        created_at=TIMESTAMP,
    )

    assert len(nomination.search_derived_entries) == 5
    assert {entry.repository_id for entry in nomination.search_derived_entries} == {
        910001,
        910002,
        910003,
        910004,
        910005,
    }
    assert all(
        "coverage_role" not in entry.model_dump(mode="json")
        for entry in nomination.search_derived_entries
    )


def _preflight_page(
    query_set: DiscoveryQuerySetV1,
    authority_digest: str,
    query_ordinal: int,
) -> SearchPageObservationV1:
    query = query_set.queries[query_ordinal - 1]
    values = {
        "schema_version": "search-page-observation-v1",
        "discovery_run_authority_digest": authority_digest,
        "query_set_version": query_set.query_set_version,
        "query_set_digest": query_set.query_set_digest,
        "query_id": query.query_id,
        "query_ordinal": query_ordinal,
        "query_text": query.query_text,
        "sort": query_set.sort,
        "order": query_set.order,
        "page": 1,
        "per_page": query_set.per_page,
        "next_page": None,
        "total_count": 0,
        "incomplete_results": False,
        "item_count": 0,
        "request_id": f"preflight-{query_ordinal}",
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
        observation_digest=sha256_digest(
            {
                **values,
                "rate_limit": values["rate_limit"].model_dump(
                    mode="json", exclude_none=False
                ),
            }
        ),
    )


def test_fresh_preflight_is_read_only_and_reports_bounded_stage_facts() -> None:
    module = _application_module(skip_if_missing=False)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )
    calls: list[str] = []

    class Search:
        def search_repositories(
            self,
            *,
            query_set: DiscoveryQuerySetV1,
            discovery_run_authority_digest: str,
            query_ordinal: int,
            page: int,
        ) -> tuple[SearchPageObservationV1, tuple[SearchRepositoryObservationV1, ...]]:
            calls.append(f"search:{query_ordinal}:{page}")
            assert page == 1
            return (
                _preflight_page(query_set, discovery_run_authority_digest, query_ordinal),
                (),
            )

        def get_repo_metadata(self, *_args: object, **_kwargs: object) -> object:
            pytest.fail("preflight must not read candidate metadata")

        def resolve_commit(self, *_args: object, **_kwargs: object) -> object:
            pytest.fail("preflight must not resolve candidate commits")

        def get_license(self, *_args: object, **_kwargs: object) -> object:
            pytest.fail("preflight must not read candidate licenses")

        def close(self) -> None:
            calls.append("search:close")

    application = module.FreshCampaignPreflightApplication(
        module.FreshCampaignPreflightDependencies(
            state_metadata_factory=lambda: calls.append("state:metadata")
            or SimpleNamespace(id=9001, owner="octo-org", name="skillscout-state"),
            state_restore_factory=lambda: calls.append("state:restore")
            or SimpleNamespace(
                status="verified",
                observed_head="a" * 40,
                bundle=SimpleNamespace(
                    root=SimpleNamespace(root_digest="sha256:" + ("b" * 64))
                ),
            ),
            search_factory=Search,
        ),
        query_set=query_set,
        clock=iter(range(100)).__next__,
    )

    result = application.run()

    assert result.status == "verified"
    assert result.failed_stage is None
    assert tuple(stage.stage for stage in result.stages) == (
        "state_metadata",
        "state_restore",
        *("search_page",) * len(query_set.queries),
    )
    assert all(stage.status == "passed" for stage in result.stages)
    assert calls[:2] == ["state:metadata", "state:restore"]
    assert calls[-1] == "search:close"
    assert len([call for call in calls if call.startswith("search:") and call != "search:close"]) == len(query_set.queries)


def test_fresh_preflight_failure_is_stage_labeled_and_does_not_echo_exception() -> None:
    module = _application_module(skip_if_missing=False)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )
    secret = "GITHUB_TOKEN_PRELIGHT_SECRET_DO_NOT_DISCLOSE"
    private_path = "/private/selected/preflight/path"

    application = module.FreshCampaignPreflightApplication(
        module.FreshCampaignPreflightDependencies(
            state_metadata_factory=lambda: SimpleNamespace(
                id=9001, owner="octo-org", name="skillscout-state"
            ),
            state_restore_factory=lambda: (_ for _ in ()).throw(
                RuntimeError(secret, private_path)
            ),
            search_factory=lambda: pytest.fail("Search must not run after restore failure"),
        ),
        query_set=query_set,
    )

    result = application.run()

    assert result.status == "failed"
    assert result.failed_stage == "state_restore"
    assert result.error_code == "unexpected_failure"
    serialized = json.dumps(result.to_json(), sort_keys=True)
    assert secret not in serialized
    assert private_path not in serialized


def test_nomination_application_persists_fact_before_exact_state_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _application_module(skip_if_missing=False)
    entries = tuple(
        NominationEntryV1(
            schema_version="nomination-entry-v1",
            repository_full_name=f"octo-org/workflow-{index}",
            repository_id=910000 + index,
            exact_commit_sha=f"{index:040x}",
            license_spdx="MIT",
            selection_source="search_derived",
            selection_evidence_digests=(sha256_digest({"index": index}),),
        )
        for index in range(1, 6)
    )
    nomination = NominationSetV1.model_validate(
        {
            "schema_version": "nomination-set-v1",
            "nomination_set_id": "nomination-cas",
            "query_set_digest": DIGEST,
            "search_run_authority_digest": DIGEST,
            "search_derived_entries": tuple(
                entry.model_dump(mode="python", exclude_none=False)
                for entry in sorted(entries, key=lambda entry: entry.entry_digest or "")
            ),
            "user_nominated_entries": (),
            "created_at": TIMESTAMP,
        },
        strict=True,
    )
    monkeypatch.setattr(
        module,
        "nominate_search_candidates",
        lambda **_arguments: nomination,
    )
    recorded = []

    class Store:
        def record_acceptance_fact(self, acceptance_run_id: str, kind: str, fact: object) -> object:
            from skillscout.adapters.operations_state import AcceptanceFactRecord

            recorded.append((acceptance_run_id, kind, fact))
            return AcceptanceFactRecord(
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact_digest=nomination.nomination_set_digest,
                fact=nomination,
            )

        def close(self) -> None:
            pass

    class Barrier:
        def sync_nomination(self, **arguments: object) -> object:
            assert recorded
            assert arguments["prior_root_digest"] == DIGEST
            return SimpleNamespace(
                status="verified",
                previous_head="a" * 40,
                commit_sha="b" * 40,
                root_digest="sha256:" + ("b" * 64),
            )

    dependencies = module.NominationDependencies(
        search_factory=lambda: SimpleNamespace(close=lambda: None),
        operations_store_factory=Store,
        state_restore=lambda: SimpleNamespace(
            status="verified",
            observed_head="a" * 40,
            bundle=SimpleNamespace(root=SimpleNamespace(root_digest=DIGEST)),
        ),
        durability_barrier=Barrier(),
    )
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )

    result = module.NominationApplication(
        dependencies,
        query_set=query_set,
        initial_state_root_digest=DIGEST,
    ).run(
        search_run_authority_digest=DIGEST,
        nomination_set_id="nomination-cas",
        created_at=TIMESTAMP,
    )

    assert result.nomination == nomination
    assert result.state_commit_sha == "b" * 40
    assert result.state_root_digest == "sha256:" + ("b" * 64)
    assert recorded == [("nomination-cas", "acceptance_nomination", nomination)]


@pytest.mark.parametrize(
    "root_mutation",
    (None, "query_set", "created_at"),
    ids=("exact", "wrong-query-set", "wrong-created-at"),
)
def test_fresh_campaign_preparation_reuses_only_exact_durable_nomination_without_search_or_sync(
    root_mutation: str | None,
) -> None:
    """A post-CAS child must bind its fact to the exact root metadata."""

    from skillscout.adapters.operations_state import (
        AcceptanceFactRecord,
        AcceptanceRunSnapshot,
    )

    module = _application_module(skip_if_missing=False)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )
    parent_commit = "a" * 40
    parent_root = "sha256:" + ("b" * 64)
    child_commit = "c" * 40
    child_root = "sha256:" + ("d" * 64)
    authority = module._fresh_nomination_authority_digest(
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        state_commit_sha=parent_commit,
        state_root_digest=parent_root,
        query_set_digest=query_set.query_set_digest,
    )
    nomination_set_id = "fresh-nomination-" + authority.removeprefix("sha256:")[:32]
    entries = tuple(
        NominationEntryV1(
            schema_version="nomination-entry-v1",
            repository_full_name=f"octo-org/recovered-{index}",
            repository_id=940000 + index,
            exact_commit_sha=f"{index:040x}",
            license_spdx="MIT",
            selection_source="search_derived",
            selection_evidence_digests=(sha256_digest({"recovered": index}),),
        )
        for index in range(1, 6)
    )
    nomination = NominationSetV1(
        schema_version="nomination-set-v1",
        nomination_set_id=nomination_set_id,
        query_set_digest=query_set.query_set_digest,
        search_run_authority_digest=authority,
        search_derived_entries=tuple(sorted(entries, key=lambda entry: entry.entry_digest or "")),
        user_nominated_entries=(),
        created_at=TIMESTAMP,
    )
    root_query_set_digest = (
        query_set.query_set_digest if root_mutation != "query_set" else "sha256:" + ("e" * 64)
    )
    root_created_at = TIMESTAMP if root_mutation != "created_at" else "2026-07-31T00:00:00.000000Z"
    snapshot = AcceptanceRunSnapshot(
        acceptance_run_id=nomination_set_id,
        facts=(
            AcceptanceFactRecord(
                acceptance_run_id=nomination_set_id,
                kind="acceptance_nomination",
                fact_digest=nomination.nomination_set_digest or "",
                fact=nomination,
            ),
        ),
    )
    calls: list[str] = []

    class Store:
        def acceptance_snapshot(self, acceptance_run_id: str) -> AcceptanceRunSnapshot:
            calls.append(acceptance_run_id)
            assert acceptance_run_id == nomination_set_id
            return snapshot

        def close(self) -> None:
            calls.append("close")

    dependencies = module.FreshCampaignPreparationDependencies(
        search_factory=lambda: pytest.fail("recovered nomination must not re-run Search"),
        operations_store_factory=Store,
        state_restore=lambda: SimpleNamespace(
            status="verified",
            observed_head=child_commit,
            bundle=SimpleNamespace(
                root=SimpleNamespace(
                    root_digest=child_root,
                    state_parent_commit_sha=parent_commit,
                    prior_root_digest=parent_root,
                    query_set_digest=root_query_set_digest,
                    created_at=root_created_at,
                )
            ),
        ),
        durability_barrier=SimpleNamespace(
            sync_nomination=lambda **_arguments: pytest.fail(
                "recovered nomination must not write state"
            )
        ),
    )

    application = module.FreshCampaignPreparationApplication(
        dependencies,
        query_set=query_set,
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
    )
    if root_mutation is None:
        result = application.run(created_at=TIMESTAMP)
        assert result == module.FreshCampaignPreparationResult(
            nomination=nomination,
            state_commit_sha=child_commit,
            state_root_digest=child_root,
        )
    else:
        with pytest.raises(module.AcceptanceApplicationError, match="evidence_missing"):
            application.run(created_at=TIMESTAMP)
    assert calls == [nomination_set_id, "close"]


def test_fresh_nomination_recovery_ignores_genesis_state_without_prior_root() -> None:
    """A valid genesis root has no predecessor nomination to recover."""

    module = _application_module(skip_if_missing=False)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )

    result = module._recover_exact_fresh_nomination(
        restored=SimpleNamespace(
            is_genesis=True,
            bundle=SimpleNamespace(
                root=SimpleNamespace(
                    prior_root_digest=None,
                    state_parent_commit_sha="0" * 40,
                )
            )
        ),
        operations_store_factory=lambda: pytest.fail(
            "genesis state must not open operations state for recovery"
        ),
        query_set_digest=query_set.query_set_digest,
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        observed_head="b" * 40,
        state_root_digest="sha256:" + ("c" * 64),
    )

    assert result is None


def test_fresh_nomination_recovery_rejects_missing_prior_root_from_non_genesis() -> None:
    """A child with no prior root may never fall through to a new Search."""

    module = _application_module(skip_if_missing=False)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )

    with pytest.raises(module.AcceptanceApplicationError, match="evidence_missing"):
        module._recover_exact_fresh_nomination(
            restored=SimpleNamespace(
                is_genesis=False,
                bundle=SimpleNamespace(
                    root=SimpleNamespace(
                        prior_root_digest=None,
                        state_parent_commit_sha="a" * 40,
                    )
                ),
            ),
            operations_store_factory=lambda: pytest.fail(
                "unlinked child must not open operations state for recovery"
            ),
            query_set_digest=query_set.query_set_digest,
            state_repository_id=9001,
            state_repository_full_name="octo-org/skillscout-state",
            observed_head="b" * 40,
            state_root_digest="sha256:" + ("c" * 64),
        )


def test_fresh_nomination_recovery_rejects_ambiguous_persisted_fact() -> None:
    """An apparent recovered run must contain exactly one nomination fact."""

    from skillscout.adapters.operations_state import (
        AcceptanceFactRecord,
        AcceptanceRunSnapshot,
    )

    module = _application_module(skip_if_missing=False)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (ROOT / "config/discovery-queries-v1.json").read_bytes(),
        strict=True,
    )
    parent_commit = "a" * 40
    parent_root = "sha256:" + ("b" * 64)
    authority = module._fresh_nomination_authority_digest(
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        state_commit_sha=parent_commit,
        state_root_digest=parent_root,
        query_set_digest=query_set.query_set_digest,
    )
    nomination_set_id = "fresh-nomination-" + authority.removeprefix("sha256:")[:32]
    record = AcceptanceFactRecord(
        acceptance_run_id=nomination_set_id,
        kind="acceptance_nomination",
        fact_digest="sha256:" + ("d" * 64),
        fact=object(),  # type: ignore[arg-type]
    )

    class Store:
        def acceptance_snapshot(self, acceptance_run_id: str) -> AcceptanceRunSnapshot:
            assert acceptance_run_id == nomination_set_id
            return AcceptanceRunSnapshot(nomination_set_id, (record, record))

        def close(self) -> None:
            pass

    with pytest.raises(module.AcceptanceApplicationError, match="evidence_missing"):
        module._recover_exact_fresh_nomination(
            restored=SimpleNamespace(
                bundle=SimpleNamespace(
                    root=SimpleNamespace(
                        prior_root_digest=parent_root,
                        state_parent_commit_sha=parent_commit,
                    )
                )
            ),
            operations_store_factory=Store,
            query_set_digest=query_set.query_set_digest,
            state_repository_id=9001,
            state_repository_full_name="octo-org/skillscout-state",
            observed_head="c" * 40,
            state_root_digest="sha256:" + ("e" * 64),
        )


def test_locked_campaign_signature_cannot_receive_evaluator_answers() -> None:
    fields = _field_names("LockedCampaignDependencies")
    assert {
        "discovery_factory",
        "operations_store_factory",
    } <= fields
    assert fields.isdisjoint(EVALUATOR_ONLY_FIELDS)
    assert fields.isdisjoint(
        {
            "benchmark_role",
            "selection_notes",
            "expected_terminal",
            "human_verdict",
        }
    )


def test_rebuild_and_attestation_signatures_have_no_live_semantic_or_edit_authority() -> None:
    for contract in (
        "HumanAttestationDependencies",
        "CleanupAttestationDependencies",
        "AcceptanceRebuildDependencies",
    ):
        fields = _field_names(contract)
        assert fields.isdisjoint(LIVE_CAPABILITY_FIELDS)
        assert fields.isdisjoint(EVALUATOR_ONLY_FIELDS)
        assert fields.isdisjoint(
            {
                "edit_candidate",
                "rewrite_skill",
                "approve_pull_request",
                "merge_pull_request",
                "mark_ready",
            }
        )


def test_offline_and_rebuild_application_surfaces_cannot_construct_live_adapters() -> None:
    module = _application_module(skip_if_missing=True)
    offline = getattr(module, "OfflineEvaluationDependencies", None)
    if offline is not None:
        assert {field.name for field in dataclasses.fields(offline)}.isdisjoint(
            LIVE_CAPABILITY_FIELDS | EVALUATOR_ONLY_FIELDS
        )
    rebuild = _field_names("AcceptanceRebuildDependencies")
    assert rebuild.isdisjoint(
        {
            "github_factory",
            "http_client_factory",
            "semantic_client_factory",
            "publication_factory",
        }
    )


def test_terminal_mapper_keeps_business_rejections_distinct_from_system_failures() -> None:
    module = _application_module(skip_if_missing=True)
    mapper = getattr(module, "classify_acceptance_terminal")
    for business in (
        "filter_rejected",
        "no_workflow",
        "qualification_rejected",
        "validation_rejected",
        "review_rejected",
    ):
        assert mapper(business) == "business_terminal"
    for failure in (
        "provider_exhausted",
        "schema_exhausted",
        "evidence_missing",
        "duplicate_effect",
        "unauthorized_effect",
        "harness_failed",
    ):
        assert mapper(failure) == "system_failure"


def test_semantic_request_projection_excludes_all_evaluator_only_metadata() -> None:
    module = _application_module(skip_if_missing=True)
    builder = getattr(module, "build_acceptance_semantic_payload")
    payload = builder(
        workflow_spec={"schema_version": "workflow-spec-v1"},
        provenance={"repository_id": 101, "source_commit_sha": "a" * 40},
    )
    assert type(payload) is dict
    assert set(payload).isdisjoint(EVALUATOR_ONLY_FIELDS)
    serialized = repr(payload)
    for canary in (
        "expected_role",
        "expected_outcome",
        "evaluator_notes",
        "human_label",
    ):
        assert canary not in serialized


def test_live_authority_runs_exact_five_without_exposing_evaluator_roles() -> None:
    """Catches widened, relabelled, or evaluator-aware benchmark execution."""

    module = _application_module(skip_if_missing=False)
    manifest = module.load_locked_benchmark_manifest(
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
    )
    fresh_lock, live_authority = _fresh_live_evidence_for_manifest(manifest)
    observed: list[object] = []
    persisted: list[object] = []

    class Runner:
        def run(self, authority: object) -> object:
            observed.append(authority)
            return module.LiveScenarioObservation(
                repository_id=authority.repository_id,
                repository_full_name=authority.repository_full_name,
                exact_commit_sha=authority.exact_commit_sha,
                license_spdx=authority.license_spdx,
                outcome="no_workflow",
                reason_code="no_reusable_workflow",
                evidence_digests=(authority.entry_digest,),
                live_acceptance_authority_digest=live_authority.authority_digest,
                discovery_run_id="acceptance-live-five-semantic",
                discovery_run_authority_digest=authority.entry_digest,
                benchmark_entry_digest=authority.entry_digest,
                budget_reservation_digest=authority.entry_digest,
                fixed_candidate_admission_digest=authority.entry_digest,
                semantic_candidate_reservation_digest=authority.entry_digest,
                semantic_request_reservation_digests=(authority.entry_digest,),
                candidate_terminal_digest=authority.entry_digest,
                workflow_terminal_digests=(),
                workflow_execution_authority_digests=(),
                workflow_spec_authority_digests=(),
                phase3_terminal_summary_digests=(),
                skill_artifact_digests=(),
                package_digests=(),
                eligible_object_digest=None,
                workflow_fingerprint=None,
                workflow_spec_authority_digest=None,
                eligible_locator=None,
                semantic_request_count=1,
                semantic_attempt_digests=(authority.entry_digest,),
                semantic_telemetry=(
                    module.AcceptanceSemanticTelemetryV1(
                        schema_version="acceptance-semantic-telemetry-v1",
                        live_acceptance_authority_digest=(live_authority.authority_digest),
                        stage="extractor",
                        workflow_spec_authority_digest=authority.entry_digest,
                        attempt_no=1,
                        request_id=f"request-{authority.repository_id}",
                        actual_model="deepseek-v4-flash",
                        prompt_version="extract-prompt-v1",
                        output_schema_version="workflow-spec-v1",
                        policy_version="extract-policy-v1",
                        prompt_tokens=10,
                        completion_tokens=5,
                        total_tokens=15,
                        latency_ms=20,
                    ),
                ),
                actual_models=("deepseek-v4-flash",),
            )

        def close(self) -> None:
            return None

    class Store:
        def acceptance_snapshot(self, acceptance_run_id: str) -> object:
            return module.AcceptanceRunSnapshot(
                acceptance_run_id=acceptance_run_id,
                facts=(
                    module.AcceptanceFactRecord(
                        acceptance_run_id=acceptance_run_id,
                        kind="acceptance_benchmark_lock",
                        fact_digest=fresh_lock.lock_digest,
                        fact=fresh_lock,
                    ),
                    module.AcceptanceFactRecord(
                        acceptance_run_id=acceptance_run_id,
                        kind="acceptance_live_authority",
                        fact_digest=live_authority.authority_digest,
                        fact=live_authority,
                    ),
                    *(
                        module.AcceptanceFactRecord(
                            acceptance_run_id=acceptance_run_id,
                            kind="acceptance_scenario",
                            fact_digest=fact.result_digest,
                            fact=fact,
                        )
                        for fact in persisted
                    ),
                ),
            )

        def record_acceptance_fact(self, acceptance_run_id: str, kind: str, fact: object) -> object:
            persisted.append(fact)
            return module.AcceptanceFactRecord(
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact_digest=fact.result_digest,
                fact=fact,
            )

        def close(self) -> None:
            return None

    sync_calls: list[tuple[str, str]] = []

    def sync(*, observed_head: str, prior_root_digest: str, **_: object) -> object:
        sync_calls.append((observed_head, prior_root_digest))
        index = len(sync_calls)
        return SimpleNamespace(
            status="verified",
            previous_head=observed_head,
            commit_sha=f"{index:040x}",
            root_digest="sha256:" + f"{index:064x}",
        )

    dependencies = module.LockedCampaignDependencies(
        discovery_factory=lambda _head, _root: Runner(),
        operations_store_factory=Store,
        state_sync=sync,
    )
    result = module.run_locked_benchmark(
        dependencies,
        manifest=manifest,
        acceptance_run_id="acceptance-live-five",
        observed_head="a" * 40,
        prior_root_digest="sha256:" + ("b" * 64),
        recorded_at=TIMESTAMP,
    )

    assert len(observed) == len(persisted) == len(sync_calls) == 5
    assert tuple(item.repository_id for item in observed) == tuple(
        entry.repository_id for entry in manifest.entries
    )
    assert all(
        not hasattr(item, "coverage_role") and not hasattr(item, "expected_outcome")
        for item in observed
    )
    assert all(item.terminal_class == "business_terminal" for item in persisted)
    assert all(
        item.candidate_funnel
        == (
            "fixed_identity",
            "deterministic_filter",
            "bounded_read",
            "extractor",
        )
        for item in persisted
    )
    assert all(item.prompt_versions == ("extract-prompt-v1",) for item in persisted)
    assert all(item.schema_versions == ("workflow-spec-v1",) for item in persisted)
    assert all(item.policy_versions == ("extract-policy-v1",) for item in persisted)
    assert result.state_commit_sha == f"{5:040x}"
    assert result.state_root_digest == "sha256:" + f"{5:064x}"

    resumed = module.run_locked_benchmark(
        dependencies,
        manifest=manifest,
        acceptance_run_id="acceptance-live-five",
        observed_head=result.state_commit_sha,
        prior_root_digest=result.state_root_digest,
        recorded_at="2026-07-27T12:00:01.000000Z",
    )

    assert resumed.scenario_results == result.scenario_results
    assert len(observed) == len(persisted) == len(sync_calls) == 5
    assert resumed.state_commit_sha == result.state_commit_sha
    assert resumed.state_root_digest == result.state_root_digest


def test_locked_benchmark_rejects_historical_v1_before_discovery_factory() -> None:
    """Historical facts stay inspectable but cannot start semantic benchmark work."""

    module = _application_module(skip_if_missing=False)
    manifest = module.load_locked_benchmark_manifest(
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
    )
    historical = LiveAcceptanceAuthorityV1.model_construct(
        schema_version="live-acceptance-authority-v1",
        authority_version=1,
        manifest_digest=manifest.manifest_digest,
        authority_digest="sha256:" + ("f" * 64),
    )
    calls: list[str] = []

    class Store:
        def acceptance_snapshot(self, acceptance_run_id: str) -> Any:
            return module.AcceptanceRunSnapshot(
                acceptance_run_id=acceptance_run_id,
                facts=(
                    module.AcceptanceFactRecord(
                        acceptance_run_id=acceptance_run_id,
                        kind="acceptance_benchmark_lock",
                        fact_digest=manifest.manifest_digest,
                        fact=manifest,
                    ),
                    module.AcceptanceFactRecord(
                        acceptance_run_id=acceptance_run_id,
                        kind="acceptance_live_authority",
                        fact_digest=historical.authority_digest,
                        fact=historical,
                    ),
                ),
            )

        def close(self) -> None:
            return None

    dependencies = module.LockedCampaignDependencies(
        discovery_factory=lambda *_args: calls.append("discovery") or object(),
        operations_store_factory=Store,
        state_sync=lambda **_kwargs: object(),
    )

    with pytest.raises(module.AcceptanceApplicationError, match="evidence_missing"):
        module.run_locked_benchmark(
            dependencies,
            manifest=manifest,
            acceptance_run_id="historical-v1-rejected",
            observed_head="a" * 40,
            prior_root_digest="sha256:" + ("b" * 64),
            recorded_at=TIMESTAMP,
        )

    assert calls == []


def _live_authority_for_manifest(manifest: Any) -> LiveAcceptanceAuthorityV2:
    return _fresh_live_evidence_for_manifest(manifest)[1]


def test_live_authority_recorder_allows_one_exact_authority_only() -> None:
    """A later dispatch cannot replace the human-approved authority in-place."""

    module = _application_module(skip_if_missing=False)
    manifest = module.load_locked_benchmark_manifest(
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
    )
    authority = _live_authority_for_manifest(manifest)
    persisted: list[Any] = []

    class Store:
        def acceptance_snapshot(self, acceptance_run_id: str) -> Any:
            assert acceptance_run_id == "acceptance-live-five"
            return module.AcceptanceRunSnapshot(
                acceptance_run_id=acceptance_run_id,
                facts=tuple(persisted),
            )

        def record_acceptance_fact(
            self,
            acceptance_run_id: str,
            kind: str,
            fact: Any,
        ) -> Any:
            record = module.AcceptanceFactRecord(
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact_digest=fact.authority_digest,
                fact=fact,
            )
            if not persisted:
                persisted.append(record)
            return record

        def close(self) -> None:
            return None

    dependencies = module.LiveAuthorityDependencies(operations_store_factory=Store)
    first = module.record_live_authority(
        dependencies,
        acceptance_run_id="acceptance-live-five",
        fact=authority,
    )
    assert first.fact_digest == authority.authority_digest
    assert len(persisted) == 1
    repeated = module.record_live_authority(
        dependencies,
        acceptance_run_id="acceptance-live-five",
        fact=authority,
    )
    assert repeated.fact_digest == authority.authority_digest
    persisted[0] = module.AcceptanceFactRecord(
        acceptance_run_id="acceptance-live-five",
        kind="acceptance_live_authority",
        fact_digest="sha256:" + ("f" * 64),
        fact=authority,
    )
    with pytest.raises(module.AcceptanceApplicationError, match="unauthorized_effect"):
        module.record_live_authority(
            dependencies,
            acceptance_run_id="acceptance-live-five",
            fact=authority,
        )


def _run_attempt_boundary_benchmark(
    *,
    outcome: str,
    reason_code: str,
    attempt_count: int,
    telemetry_attempt: int | None,
    expected_error: str | None = None,
) -> tuple[Any | None, list[Any]]:
    module = _application_module(skip_if_missing=False)
    manifest = module.load_locked_benchmark_manifest(
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
    )
    live_authority = _live_authority_for_manifest(manifest)
    fresh_lock = live_authority.benchmark_lock
    persisted: list[Any] = []

    class Runner:
        def run(self, authority: Any) -> Any:
            attempts = tuple(
                sha256_digest(
                    {
                        "repository_id": authority.repository_id,
                        "attempt_no": attempt_no,
                    }
                )
                for attempt_no in range(1, attempt_count + 1)
            )
            telemetry = (
                (
                    module.AcceptanceSemanticTelemetryV1(
                        schema_version="acceptance-semantic-telemetry-v1",
                        live_acceptance_authority_digest=(live_authority.authority_digest),
                        stage="extractor",
                        workflow_spec_authority_digest=authority.entry_digest,
                        attempt_no=telemetry_attempt,
                        request_id=f"request-{authority.repository_id}",
                        actual_model="deepseek-v4-flash",
                        prompt_version="extract-prompt-v1",
                        output_schema_version="workflow-spec-v1",
                        policy_version="extract-policy-v1",
                        prompt_tokens=10,
                        completion_tokens=5,
                        total_tokens=15,
                        latency_ms=20,
                    ),
                )
                if telemetry_attempt is not None
                else ()
            )
            return module.LiveScenarioObservation(
                repository_id=authority.repository_id,
                repository_full_name=authority.repository_full_name,
                exact_commit_sha=authority.exact_commit_sha,
                license_spdx=authority.license_spdx,
                outcome=outcome,
                reason_code=reason_code,
                evidence_digests=(
                    authority.entry_digest,
                    *attempts,
                ),
                live_acceptance_authority_digest=live_authority.authority_digest,
                discovery_run_id="acceptance-attempt-boundary-semantic",
                discovery_run_authority_digest=authority.entry_digest,
                benchmark_entry_digest=authority.entry_digest,
                budget_reservation_digest=authority.entry_digest,
                fixed_candidate_admission_digest=authority.entry_digest,
                semantic_candidate_reservation_digest=authority.entry_digest,
                semantic_request_reservation_digests=tuple(sorted(attempts)),
                candidate_terminal_digest=authority.entry_digest,
                workflow_terminal_digests=(),
                workflow_execution_authority_digests=(),
                workflow_spec_authority_digests=(),
                phase3_terminal_summary_digests=(),
                skill_artifact_digests=(),
                package_digests=(),
                eligible_object_digest=None,
                workflow_fingerprint=None,
                workflow_spec_authority_digest=None,
                eligible_locator=None,
                semantic_request_count=attempt_count,
                semantic_attempt_digests=tuple(sorted(attempts)),
                semantic_telemetry=telemetry,
                actual_models=tuple(item.actual_model for item in telemetry),
            )

        def close(self) -> None:
            return None

    class Store:
        def acceptance_snapshot(self, acceptance_run_id: str) -> Any:
            return module.AcceptanceRunSnapshot(
                acceptance_run_id=acceptance_run_id,
                facts=(
                    module.AcceptanceFactRecord(
                        acceptance_run_id=acceptance_run_id,
                        kind="acceptance_benchmark_lock",
                        fact_digest=fresh_lock.lock_digest,
                        fact=fresh_lock,
                    ),
                    module.AcceptanceFactRecord(
                        acceptance_run_id=acceptance_run_id,
                        kind="acceptance_live_authority",
                        fact_digest=live_authority.authority_digest,
                        fact=live_authority,
                    ),
                ),
            )

        def record_acceptance_fact(self, acceptance_run_id: str, kind: str, fact: Any) -> Any:
            persisted.append(fact)
            return module.AcceptanceFactRecord(
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact_digest=fact.result_digest,
                fact=fact,
            )

        def close(self) -> None:
            return None

    sync_count = 0

    def sync(*, observed_head: str, **_: Any) -> Any:
        nonlocal sync_count
        sync_count += 1
        return SimpleNamespace(
            status="verified",
            previous_head=observed_head,
            commit_sha=f"{sync_count:040x}",
            root_digest="sha256:" + f"{sync_count:064x}",
        )

    dependencies = module.LockedCampaignDependencies(
        discovery_factory=lambda _head, _root: Runner(),
        operations_store_factory=Store,
        state_sync=sync,
    )
    try:
        result = module.run_locked_benchmark(
            dependencies,
            manifest=manifest,
            acceptance_run_id="acceptance-attempt-boundary",
            observed_head="a" * 40,
            prior_root_digest="sha256:" + ("b" * 64),
            recorded_at=TIMESTAMP,
        )
    except module.AcceptanceApplicationError as error:
        if str(error) != expected_error:
            raise
        result = None
    return result, persisted


def test_locked_benchmark_counts_transient_then_success_without_fake_telemetry() -> None:
    """A response-less first request remains an attempt, not invented telemetry."""

    result, persisted = _run_attempt_boundary_benchmark(
        outcome="no_workflow",
        reason_code="no_reusable_workflow",
        attempt_count=2,
        telemetry_attempt=2,
    )

    assert len(result.scenario_results) == len(persisted) == 5
    assert all(item.semantic_request_count == 2 for item in persisted)
    assert all(len(item.semantic_attempt_digests) == 2 for item in persisted)
    assert all(
        tuple(item.attempt_no for item in scenario.semantic_telemetry) == (2,)
        for scenario in persisted
    )
    assert all(item.actual_models == ("deepseek-v4-flash",) for item in persisted)


def test_locked_benchmark_persists_true_exhaustion_without_fake_telemetry() -> None:
    """Three response-less durable attempts exhaust exactly once."""

    result, persisted = _run_attempt_boundary_benchmark(
        outcome="provider_exhausted",
        reason_code="provider_attempts_exhausted",
        attempt_count=3,
        telemetry_attempt=None,
        expected_error="provider_exhausted",
    )
    assert result is None
    assert len(persisted) == 1
    assert persisted[0].semantic_request_count == 3
    assert len(persisted[0].semantic_attempt_digests) == 3
    assert persisted[0].semantic_telemetry == ()
    assert persisted[0].actual_models == ()


def test_exact_replay_reuses_completed_projection_with_zero_live_effects() -> None:
    """Catches replay claiming zero effects without a measured post-write reread."""

    module = _application_module(skip_if_missing=False)
    manifest = module.load_locked_benchmark_manifest(
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
    )
    events: list[str] = []

    projections = 0
    persisted: list[tuple[str, object]] = []

    class Projector:
        def project(self, **_: object) -> object:
            nonlocal projections
            projections += 1
            events.append("project")
            return module.CompletedBenchmarkProjection(
                manifest_digest=manifest.manifest_digest,
                scenario_result_digests=tuple("sha256:" + f"{index:064x}" for index in range(1, 6)),
                repository_id=manifest.entries[0].repository_id,
                source_commit_sha=manifest.entries[0].exact_commit_sha,
                workflow_fingerprint="sha256:" + ("a" * 64),
                workflow_spec_authority_digest="sha256:" + ("b" * 64),
                eligible_locators=("state/objects/eligible.json",),
                semantic_attempt_count=5,
                semantic_attempt_digests=tuple(
                    "sha256:" + f"{index:064x}" for index in range(11, 16)
                ),
                workflow_spec_authority_digests=("sha256:" + ("b" * 64),),
                skill_identity_digests=("sha256:" + ("c" * 64),),
                candidate_fact_digests=tuple(
                    "sha256:" + f"{index:064x}" for index in range(21, 26)
                ),
                acceptance_business_fact_digests=tuple(
                    "sha256:" + f"{index:064x}" for index in range(31, 36)
                ),
                operations_fact_digests=tuple(
                    "sha256:" + f"{index:064x}" for index in range(41, 46)
                ),
                semantic_request_count=5,
            )

        def close(self) -> None:
            return None

    class Store:
        def record_acceptance_fact(self, acceptance_run_id: str, kind: str, fact: object) -> object:
            events.append("record")
            persisted.append((kind, fact))
            return module.AcceptanceFactRecord(
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact_digest=fact.replay_digest,
                fact=fact,
            )

        def close(self) -> None:
            return None

    sync_count = 0

    def sync(*, observed_head: str, **_: object) -> object:
        nonlocal sync_count
        sync_count += 1
        events.append("sync")
        return SimpleNamespace(
            status="verified",
            previous_head=observed_head,
            commit_sha=("e" if sync_count == 1 else "1") * 40,
            root_digest="sha256:" + (("f" if sync_count == 1 else "2") * 64),
        )

    dependencies = module.ReplayUpdateDependencies(
        completed_projector_factory=Projector,
        operations_store_factory=Store,
        state_sync=sync,
    )
    replay = module.run_exact_replay(
        dependencies,
        manifest=manifest,
        acceptance_run_id="acceptance-live-five",
        state_commit_sha="c" * 40,
        state_root_digest="sha256:" + ("d" * 64),
        recorded_at=TIMESTAMP,
    )

    assert events == [
        "project",
        "record",
        "sync",
        "project",
        "record",
        "sync",
        "project",
    ]
    assert projections == 3
    assert tuple(kind for kind, _ in persisted) == (
        "acceptance_replay",
        "acceptance_replay_evidence",
    )
    assert persisted[1][1] == replay
    assert replay.semantic_request_count == 0
    assert replay.duplicate_workflow_spec_count == 0
    assert replay.duplicate_skill_count == 0
    assert replay.duplicate_fact_count == 0
    assert replay.remote_effect_count == 0
    assert replay.before_state_root_digest == "sha256:" + ("d" * 64)
    assert replay.after_state_root_digest == "sha256:" + ("f" * 64)
    assert replay.before_state_commit_sha == "c" * 40
    assert replay.after_state_commit_sha == "e" * 40
    assert replay.before_projection_digest == replay.after_projection_digest
    assert replay.before_object_digests == replay.after_object_digests
    assert replay.replay_fact_digest.startswith("sha256:")
    assert replay.allowed_delta_fact_digests == (replay.replay_fact_digest,)


def test_exact_replay_blocks_when_post_write_campaign_projection_changes() -> None:
    """The replay fact write is allowed; any campaign-effect drift is not."""

    module = _application_module(skip_if_missing=False)
    manifest = module.load_locked_benchmark_manifest(
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
    )
    calls = 0

    class Projector:
        def project(self, **_: object) -> object:
            nonlocal calls
            calls += 1
            return module.CompletedBenchmarkProjection(
                manifest_digest=manifest.manifest_digest,
                scenario_result_digests=tuple("sha256:" + f"{index:064x}" for index in range(1, 6)),
                repository_id=manifest.entries[0].repository_id,
                source_commit_sha=manifest.entries[0].exact_commit_sha,
                workflow_fingerprint="sha256:" + ("a" * 64),
                workflow_spec_authority_digest="sha256:" + ("b" * 64),
                eligible_locators=("state/objects/eligible.json",),
                semantic_attempt_count=5 + (calls - 1),
                semantic_attempt_digests=tuple(
                    "sha256:" + f"{index:064x}" for index in range(11, 16 + (calls - 1))
                ),
                workflow_spec_authority_digests=("sha256:" + ("b" * 64),),
                skill_identity_digests=("sha256:" + ("c" * 64),),
                candidate_fact_digests=tuple(
                    "sha256:" + f"{index:064x}" for index in range(21, 26)
                ),
                acceptance_business_fact_digests=tuple(
                    "sha256:" + f"{index:064x}" for index in range(31, 36)
                ),
                operations_fact_digests=tuple(
                    "sha256:" + f"{index:064x}" for index in range(41, 46)
                ),
                semantic_request_count=5 + (calls - 1),
            )

        def close(self) -> None:
            return None

    class Store:
        def record_acceptance_fact(self, acceptance_run_id: str, kind: str, fact: object) -> object:
            return module.AcceptanceFactRecord(
                acceptance_run_id=acceptance_run_id,
                kind=kind,
                fact_digest=fact.replay_digest,
                fact=fact,
            )

        def close(self) -> None:
            return None

    dependencies = module.ReplayUpdateDependencies(
        completed_projector_factory=Projector,
        operations_store_factory=Store,
        state_sync=lambda **_: SimpleNamespace(
            status="verified",
            previous_head="c" * 40,
            commit_sha="e" * 40,
            root_digest="sha256:" + ("f" * 64),
        ),
    )
    with pytest.raises(module.AcceptanceApplicationError, match="duplicate_effect"):
        module.run_exact_replay(
            dependencies,
            manifest=manifest,
            acceptance_run_id="acceptance-live-five",
            state_commit_sha="c" * 40,
            state_root_digest="sha256:" + ("d" * 64),
            recorded_at=TIMESTAMP,
        )
