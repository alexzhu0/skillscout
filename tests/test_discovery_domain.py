from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.discovery import (
    DISCOVERY_MAX_CANDIDATES,
    DISCOVERY_MAX_SEMANTIC_CANDIDATES,
    DiscoveryBudgetPolicyV1,
    DiscoveryQuerySetV1,
    DiscoveryRunAuthorityV1,
)


ROOT = Path(__file__).resolve().parents[1]
QUERY_POLICY_PATH = ROOT / "config" / "discovery-queries-v1.json"
DIGEST_A = "sha256:" + ("a" * 64)
DIGEST_B = "sha256:" + ("b" * 64)
DIGEST_C = "sha256:" + ("c" * 64)

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
