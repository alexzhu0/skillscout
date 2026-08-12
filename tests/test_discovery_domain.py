from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
    DiscoveredCandidateV1,
    DiscoveryBudgetPolicyV1,
    DiscoveryCandidateTerminalV1,
    DiscoveryQuerySetV1,
    DiscoveryReservationV1,
    DiscoveryRunAuthorityV1,
    DiscoveryRunSummaryV1,
    DiscoveryStateDatabaseV1,
    DiscoveryStateObjectV1,
    DiscoveryStateRebuildProjectionV1,
    DiscoveryStateRootV1,
    SearchPageObservationV1,
    SearchRateLimitFactsV1,
    SearchRepositoryObservationV1,
    SemanticReservationV1,
)


ROOT = Path(__file__).resolve().parents[1]
QUERY_POLICY_PATH = ROOT / "config" / "discovery-queries-v1.json"
DIGEST_A = "sha256:" + ("a" * 64)
DIGEST_B = "sha256:" + ("b" * 64)
DIGEST_C = "sha256:" + ("c" * 64)
DIGEST_D = "sha256:" + ("d" * 64)
TIMESTAMP = "2026-07-27T12:00:00.000000Z"

EXPECTED_QUERY_POLICY = {
    "schema_version": "discovery-query-set-v1",
    "query_set_version": "github-repository-search-v1",
    "queries": [
        {
            "query_id": "agent-workflow-readme",
            "query_text": '"agent workflow" in:name,description,readme is:public archived:false',
        },
        {
            "query_id": "ai-workflow-readme",
            "query_text": '"AI workflow" in:name,description,readme is:public archived:false',
        },
        {
            "query_id": "llm-automation-readme",
            "query_text": '"LLM automation" in:name,description,readme is:public archived:false',
        },
        {
            "query_id": "agent-skills-topic",
            "query_text": "topic:agent-skills is:public archived:false",
        },
    ],
    "per_page": 25,
    "max_pages_per_query": 4,
    "acquisition_order": "round_robin",
    "sort": "updated",
    "order": "desc",
}


def _query_set() -> DiscoveryQuerySetV1:
    return DiscoveryQuerySetV1.model_validate_json(
        QUERY_POLICY_PATH.read_bytes(), strict=True
    )


def _budget() -> DiscoveryBudgetPolicyV1:
    return DiscoveryBudgetPolicyV1()


def _authority() -> DiscoveryRunAuthorityV1:
    query_set = _query_set()
    budget = _budget()
    values = {
        "schema_version": "discovery-run-authority-v1",
        "run_id": "discovery-0123456789abcdef",
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
        authority_digest=sha256_digest(values),
    )


def test_query_policy_exact_bytes_parse_and_bind_stable_digest() -> None:
    assert json.loads(QUERY_POLICY_PATH.read_bytes()) == EXPECTED_QUERY_POLICY
    query_set = _query_set()
    assert query_set.model_dump(mode="json", exclude={"query_set_digest"}) == (
        EXPECTED_QUERY_POLICY
    )
    assert query_set.query_set_digest == sha256_digest(EXPECTED_QUERY_POLICY)
    assert canonical_json_bytes(query_set) == canonical_json_bytes(
        {**EXPECTED_QUERY_POLICY, "query_set_digest": query_set.query_set_digest}
    )


def test_query_policy_strictly_parses_canonical_json_with_bound_digest() -> None:
    query_set = _query_set()
    canonical = canonical_json_bytes(query_set)

    assert DiscoveryQuerySetV1.model_validate_json(canonical, strict=True) == query_set

    wrong_digest = json.loads(canonical)
    wrong_digest["query_set_digest"] = DIGEST_B
    with pytest.raises(ValidationError):
        DiscoveryQuerySetV1.model_validate_json(
            canonical_json_bytes(wrong_digest),
            strict=True,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("query_set_version", "github-repository-search-v2"),
        ("per_page", 24),
        ("max_pages_per_query", 5),
        ("acquisition_order", "sequential"),
        ("sort", "stars"),
        ("order", "asc"),
    ),
)
def test_query_policy_rejects_any_fixed_policy_mutation(
    field: str, value: object
) -> None:
    changed = {**EXPECTED_QUERY_POLICY, field: value}
    with pytest.raises(ValidationError):
        DiscoveryQuerySetV1.model_validate(changed, strict=True)


def test_query_policy_rejects_query_order_text_digest_and_extra_mutations() -> None:
    query_set = _query_set()
    swapped = {
        **EXPECTED_QUERY_POLICY,
        "queries": [
            EXPECTED_QUERY_POLICY["queries"][1],
            EXPECTED_QUERY_POLICY["queries"][0],
            *EXPECTED_QUERY_POLICY["queries"][2:],
        ],
    }
    changed_text = json.loads(json.dumps(EXPECTED_QUERY_POLICY))
    changed_text["queries"][0]["query_text"] += " fork:false"
    for invalid in (
        swapped,
        changed_text,
        {**EXPECTED_QUERY_POLICY, "unexpected": True},
        {
            **query_set.model_dump(mode="json"),
            "query_set_digest": DIGEST_B,
        },
    ):
        with pytest.raises(ValidationError):
            DiscoveryQuerySetV1.model_validate(invalid, strict=True)


def test_budget_policy_has_literal_non_widenable_100_and_20_ceilings() -> None:
    budget = _budget()
    assert DISCOVERY_MAX_CANDIDATES == 100
    assert DISCOVERY_MAX_SEMANTIC_CANDIDATES == 20
    assert budget.max_candidates == 100
    assert budget.max_semantic_candidates == 20
    assert budget.admit_discovery_ordinal(99) == 99
    assert budget.admit_discovery_ordinal(100) == 100
    assert budget.admit_semantic_ordinal(19) == 19
    assert budget.admit_semantic_ordinal(20) == 20
    for ordinal in (0, 101):
        with pytest.raises(ValueError):
            budget.admit_discovery_ordinal(ordinal)
    for ordinal in (0, 21):
        with pytest.raises(ValueError):
            budget.admit_semantic_ordinal(ordinal)
    for invalid in (
        {"max_candidates": 101},
        {"max_semantic_candidates": 21},
        {"unexpected": True},
        {"budget_policy_digest": DIGEST_B},
    ):
        with pytest.raises(ValidationError):
            DiscoveryBudgetPolicyV1.model_validate(invalid, strict=True)


def test_run_authority_is_complete_self_hashed_and_stable() -> None:
    authority = _authority()
    assert authority.authority_digest == sha256_digest(
        authority.model_dump(
            mode="json", exclude_none=False, exclude={"authority_digest"}
        )
    )
    assert authority == DiscoveryRunAuthorityV1.model_validate(
        authority.model_dump(mode="json"), strict=True
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("run_id", "discovery-fedcba9876543210"),
        ("query_set_digest", DIGEST_B),
        ("budget_policy_digest", DIGEST_B),
        ("phase2_profile_version", "phase2-v2"),
        ("phase3_profile_version", "phase3-profile-v2"),
        ("semantic_provider", "deepseek"),
        ("extractor_model_id", "other"),
        ("generator_model_id", "other"),
        ("reviewer_model_id", "other"),
        ("initial_state_root_digest", DIGEST_C),
    ),
)
def test_run_authority_mutation_is_a_clean_mismatch(
    field: str, value: object
) -> None:
    authority = _authority()
    changed = {**authority.model_dump(mode="json"), field: value}
    changed["authority_digest"] = sha256_digest(
        {key: item for key, item in changed.items() if key != "authority_digest"}
    )
    mutated = DiscoveryRunAuthorityV1.model_validate(changed, strict=True)
    assert mutated.authority_digest != authority.authority_digest
    assert mutated != authority


def test_run_authority_rejects_stale_digest_extra_and_checkpoint_head() -> None:
    authority = _authority()
    raw = authority.model_dump(mode="json")
    for invalid in (
        {**raw, "authority_digest": DIGEST_B},
        {**raw, "unexpected": True},
        {**raw, "checkpoint_head": DIGEST_C},
    ):
        with pytest.raises(ValidationError):
            DiscoveryRunAuthorityV1.model_validate(invalid, strict=True)


def _self_hashed(model: type, field: str, **values: object) -> object:
    def json_value(value: object) -> object:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", exclude_none=False)
        if isinstance(value, tuple):
            return [json_value(item) for item in value]
        return value

    preimage = {key: json_value(value) for key, value in values.items()}
    return model(**values, **{field: sha256_digest(preimage)})


def _rate() -> SearchRateLimitFactsV1:
    return SearchRateLimitFactsV1(
        limit=30,
        remaining=29,
        used=1,
        reset_epoch=1_785_156_000,
        resource="search",
    )


def _page() -> SearchPageObservationV1:
    query_set = _query_set()
    values = {
        "schema_version": "search-page-observation-v1",
        "discovery_run_authority_digest": _authority().authority_digest,
        "query_set_version": query_set.query_set_version,
        "query_set_digest": query_set.query_set_digest,
        "query_id": query_set.queries[0].query_id,
        "query_ordinal": 1,
        "query_text": query_set.queries[0].query_text,
        "sort": "updated",
        "order": "desc",
        "page": 1,
        "per_page": 25,
        "next_page": 2,
        "total_count": 50,
        "incomplete_results": False,
        "item_count": 25,
        "request_id": "github-request-001",
        "rate_limit": _rate(),
    }
    return _self_hashed(
        SearchPageObservationV1, "observation_digest", **values
    )


def _repository() -> SearchRepositoryObservationV1:
    values = {
        "schema_version": "search-repository-observation-v1",
        "repository_id": 123456,
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
    return _self_hashed(
        SearchRepositoryObservationV1, "observation_digest", **values
    )


def _candidate(
    *,
    disposition: str = "first_seen",
    owner: str = "octo-org",
    discovery_ordinal: int | None = 1,
) -> DiscoveredCandidateV1:
    repository = _repository()
    if owner != repository.owner:
        values = repository.model_dump(
            mode="json", exclude={"observation_digest"}
        )
        values["owner"] = owner
        values["full_name"] = f"{owner}/{repository.name}"
        repository = _self_hashed(
            SearchRepositoryObservationV1, "observation_digest", **values
        )
    values = {
        "schema_version": "discovered-candidate-v1",
        "discovery_run_authority_digest": _authority().authority_digest,
        "repository": repository,
        "source_page_digest": _page().observation_digest,
        "query_ordinal": 1 if disposition == "first_seen" else 2,
        "page": 1,
        "item_ordinal": 1 if disposition == "first_seen" else 4,
        "dedup_disposition": disposition,
        "discovery_ordinal": discovery_ordinal,
        "first_seen_query_ordinal": 1,
        "first_seen_page": 1,
        "first_seen_item_ordinal": 1,
    }
    return _self_hashed(DiscoveredCandidateV1, "candidate_digest", **values)


def _discovery_reservation() -> DiscoveryReservationV1:
    candidate = _candidate()
    values = {
        "schema_version": "discovery-reservation-v1",
        "discovery_run_authority_digest": _authority().authority_digest,
        "repository_id": candidate.repository.repository_id,
        "ordinal": 1,
        "candidate_digest": candidate.candidate_digest,
        "reserved_at": TIMESTAMP,
    }
    return _self_hashed(
        DiscoveryReservationV1, "reservation_digest", **values
    )


def _semantic_reservation() -> SemanticReservationV1:
    reservation = _discovery_reservation()
    values = {
        "schema_version": "semantic-reservation-v1",
        "discovery_run_authority_digest": _authority().authority_digest,
        "repository_id": reservation.repository_id,
        "ordinal": 1,
        "discovery_reservation_digest": reservation.reservation_digest,
        "phase2_run_authority_digest": DIGEST_B,
        "reserved_at": TIMESTAMP,
    }
    return _self_hashed(SemanticReservationV1, "reservation_digest", **values)


def test_page_observation_binds_complete_query_cursor_rate_and_counts() -> None:
    page = _page()
    assert page.rate_limit.resource == "search"
    assert page.item_count == 25
    assert page.observation_digest == sha256_digest(
        page.model_dump(
            mode="json", exclude_none=False, exclude={"observation_digest"}
        )
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("query_text", "runtime supplied query"),
        ("query_ordinal", 0),
        ("page", 0),
        ("per_page", 24),
        ("next_page", 1),
        ("item_count", 26),
        ("request_id", ""),
        ("observation_digest", DIGEST_D),
    ),
)
def test_page_observation_rejects_each_cursor_or_authority_mutation(
    field: str, value: object
) -> None:
    raw = _page().model_dump(mode="json")
    raw[field] = value
    with pytest.raises(ValidationError):
        SearchPageObservationV1.model_validate(raw, strict=True)


def test_rate_limit_facts_are_numeric_bounded_and_closed() -> None:
    for invalid in (
        {"limit": 30, "remaining": 31, "used": 1, "reset_epoch": 1, "resource": "search"},
        {"limit": 30, "remaining": 29, "used": 2, "reset_epoch": 1, "resource": "search"},
        {"limit": 30, "remaining": 29, "used": 1, "reset_epoch": 1, "resource": "core"},
        {**_rate().model_dump(mode="json"), "authorization": "secret"},
    ):
        with pytest.raises(ValidationError):
            SearchRateLimitFactsV1.model_validate(invalid, strict=True)


def test_repository_projection_keeps_only_validated_non_prose_facts() -> None:
    repository = _repository()
    assert repository.full_name == f"{repository.owner}/{repository.name}"
    assert repository.repository_id == 123456
    for forbidden in (
        "description",
        "topics",
        "text_matches",
        "readme",
        "source_body",
        "authorization",
        "provider_error",
    ):
        with pytest.raises(ValidationError):
            SearchRepositoryObservationV1.model_validate(
                {**repository.model_dump(mode="json"), forbidden: "hostile prose"},
                strict=True,
            )


def test_candidate_deduplicates_by_numeric_repository_id_not_mutable_name() -> None:
    first = _candidate()
    renamed_duplicate = _candidate(
        disposition="duplicate", owner="renamed-org", discovery_ordinal=None
    )
    assert first.repository.repository_id == renamed_duplicate.repository.repository_id
    assert first.repository.full_name != renamed_duplicate.repository.full_name
    assert renamed_duplicate.first_seen_query_ordinal == first.query_ordinal
    assert renamed_duplicate.discovery_ordinal is None


def test_candidate_rejects_incoherent_first_seen_or_duplicate_provenance() -> None:
    first = _candidate().model_dump(mode="json")
    duplicate = _candidate(
        disposition="duplicate", discovery_ordinal=None
    ).model_dump(mode="json")
    invalids = (
        {**first, "discovery_ordinal": None},
        {**duplicate, "discovery_ordinal": 2},
        {**duplicate, "first_seen_query_ordinal": 3},
        {**first, "candidate_digest": DIGEST_D},
        {**first, "raw_search_item": {"description": "untrusted"}},
    )
    for invalid in invalids:
        with pytest.raises(ValidationError):
            DiscoveredCandidateV1.model_validate(invalid, strict=True)


def test_discovery_and_semantic_reservations_are_self_hashed_and_bounded() -> None:
    discovery = _discovery_reservation()
    semantic = _semantic_reservation()
    assert discovery.ordinal == 1
    assert semantic.ordinal == 1
    for model, raw, field, value in (
        (
            DiscoveryReservationV1,
            discovery.model_dump(mode="json"),
            "ordinal",
            101,
        ),
        (
            SemanticReservationV1,
            semantic.model_dump(mode="json"),
            "ordinal",
            21,
        ),
        (
            DiscoveryReservationV1,
            discovery.model_dump(mode="json"),
            "reservation_digest",
            DIGEST_D,
        ),
        (
            SemanticReservationV1,
            semantic.model_dump(mode="json"),
            "reservation_digest",
            DIGEST_D,
        ),
    ):
        raw[field] = value
        with pytest.raises(ValidationError):
            model.model_validate(raw, strict=True)


def _terminal(outcome: str) -> DiscoveryCandidateTerminalV1:
    semantic = _semantic_reservation()
    values = {
        "schema_version": "discovery-candidate-terminal-v1",
        "discovery_run_authority_digest": _authority().authority_digest,
        "repository_id": semantic.repository_id,
        "semantic_reservation_digest": semantic.reservation_digest,
        "outcome": outcome,
        "workflow_authority_digests": (),
        "recorded_at": TIMESTAMP,
    }
    return _self_hashed(
        DiscoveryCandidateTerminalV1, "terminal_digest", **values
    )


@pytest.mark.parametrize(
    "outcome",
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
def test_candidate_terminal_has_closed_distinct_outcome_taxonomy(
    outcome: str,
) -> None:
    assert _terminal(outcome).outcome == outcome


def test_unknown_semantic_outcome_is_quarantined_not_retryable() -> None:
    terminal = _terminal("semantic_outcome_unknown")
    assert terminal.quarantined is True
    assert terminal.automatic_retry_allowed is False
    retryable = _terminal("confirmed_retryable")
    assert retryable.quarantined is False
    assert retryable.automatic_retry_allowed is True


def _run_summary() -> DiscoveryRunSummaryV1:
    terminal = _terminal("semantic_outcome_unknown")
    values = {
        "schema_version": "discovery-run-summary-v1",
        "discovery_run_authority_digest": _authority().authority_digest,
        "status": "completed_degraded",
        "selected_candidate_count": 1,
        "semantic_reservation_count": 1,
        "business_terminal_count": 0,
        "quarantined_candidate_count": 1,
        "confirmed_retryable_count": 0,
        "integrity_conflict_count": 0,
        "permanent_failure_count": 0,
        "terminal_digests": (terminal.terminal_digest,),
        "completed_at": TIMESTAMP,
    }
    return _self_hashed(DiscoveryRunSummaryV1, "summary_digest", **values)


def _state_objects() -> tuple[DiscoveryStateObjectV1, ...]:
    return tuple(
        DiscoveryStateObjectV1(
            object_digest=digest,
            locator=(
                f"state/objects/sha256/{digest[7:9]}/{digest[7:]}.json"
            ),
            size_bytes=index + 1,
        )
        for index, digest in enumerate((DIGEST_A, DIGEST_B, DIGEST_C))
    )


def _state_databases() -> tuple[DiscoveryStateDatabaseV1, ...]:
    return (
        DiscoveryStateDatabaseV1(
            owner="pipeline",
            locator="state/databases/pipeline.sqlite3",
            content_digest=DIGEST_A,
            size_bytes=1,
            schema_fingerprint=DIGEST_A,
        ),
        DiscoveryStateDatabaseV1(
            owner="operations",
            locator="state/databases/operations.sqlite3",
            content_digest=DIGEST_B,
            size_bytes=2,
            schema_fingerprint=DIGEST_B,
        ),
        DiscoveryStateDatabaseV1(
            owner="publication",
            locator="state/databases/publication.sqlite3",
            content_digest=DIGEST_C,
            size_bytes=3,
            schema_fingerprint=DIGEST_C,
        ),
    )


def _projection() -> DiscoveryStateRebuildProjectionV1:
    values = {
        "schema_version": "discovery-state-rebuild-projection-v1",
        "search_page_digests": (_page().observation_digest,),
        "candidate_digests": (_candidate().candidate_digest,),
        "discovery_reservation_digests": (
            _discovery_reservation().reservation_digest,
        ),
        "semantic_reservation_digests": (
            _semantic_reservation().reservation_digest,
        ),
        "workflow_terminal_digests": (),
        "candidate_terminal_digests": (
            _terminal("semantic_outcome_unknown").terminal_digest,
        ),
        "run_summary_digests": (_run_summary().summary_digest,),
    }
    return _self_hashed(
        DiscoveryStateRebuildProjectionV1, "projection_digest", **values
    )


def _state_root() -> DiscoveryStateRootV1:
    values = {
        "schema_version": "discovery-state-root-v1",
        "root_locator": "state/root.json",
        "prior_root_digest": DIGEST_D,
        "state_parent_commit_sha": "1" * 40,
        "query_set_digest": _query_set().query_set_digest,
        "budget_policy_digest": _budget().budget_policy_digest,
        "objects": _state_objects(),
        "databases": _state_databases(),
        "rebuild_projection": _projection(),
        "created_at": TIMESTAMP,
    }
    return _self_hashed(DiscoveryStateRootV1, "root_digest", **values)


def test_state_root_has_exact_root_object_and_three_database_ownership() -> None:
    root = _state_root()
    assert root.root_locator == "state/root.json"
    assert tuple(database.owner for database in root.databases) == (
        "pipeline",
        "operations",
        "publication",
    )
    assert root.root_digest == sha256_digest(
        root.model_dump(mode="json", exclude_none=False, exclude={"root_digest"})
    )
    assert root.prior_root_digest == DIGEST_D


def test_state_object_locator_is_derived_from_exact_content_digest() -> None:
    item = _state_objects()[0]
    for invalid in (
        {**item.model_dump(mode="json"), "locator": "state/objects/sha256/ff/" + ("a" * 64) + ".json"},
        {**item.model_dump(mode="json"), "locator": "../object.json"},
        {**item.model_dump(mode="json"), "object_digest": DIGEST_B},
        {**item.model_dump(mode="json"), "raw_body": "forbidden"},
    ):
        with pytest.raises(ValidationError):
            DiscoveryStateObjectV1.model_validate(invalid, strict=True)


def test_state_root_rejects_swapped_owner_path_fourth_database_and_mutations() -> None:
    root = _state_root()
    raw = root.model_dump(mode="json")
    swapped = json.loads(json.dumps(raw))
    swapped["databases"][0]["owner"] = "operations"
    fourth = json.loads(json.dumps(raw))
    fourth["databases"].append(
        {
            "owner": "operations",
            "locator": "state/databases/fourth.sqlite3",
            "content_digest": DIGEST_D,
            "size_bytes": 4,
            "schema_fingerprint": DIGEST_D,
        }
    )
    object_reordered = json.loads(json.dumps(raw))
    object_reordered["objects"][0], object_reordered["objects"][1] = (
        object_reordered["objects"][1],
        object_reordered["objects"][0],
    )
    projection_mutated = json.loads(json.dumps(raw))
    projection_mutated["rebuild_projection"]["projection_digest"] = DIGEST_D
    for invalid in (
        swapped,
        fourth,
        object_reordered,
        projection_mutated,
        {**raw, "root_digest": DIGEST_D},
        {**raw, "prune_before": TIMESTAMP},
        {**raw, "authorization": "secret"},
    ):
        with pytest.raises(ValidationError):
            DiscoveryStateRootV1.model_validate(invalid, strict=True)


@pytest.mark.parametrize(
    "forbidden",
    (
        "description",
        "topics",
        "text_matches",
        "link",
        "headers",
        "provider_body",
        "raw_error",
        "source_body",
        "authorization",
        "api_key",
        "private_key",
        "prune_policy",
    ),
)
def test_durable_models_reject_forbidden_untrusted_or_secret_fields(
    forbidden: str,
) -> None:
    root = _state_root().model_dump(mode="json")
    root[forbidden] = "forbidden"
    with pytest.raises(ValidationError):
        DiscoveryStateRootV1.model_validate(root, strict=True)
