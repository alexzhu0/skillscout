"""Strict, content-addressed contracts for bounded discovery operations."""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel

DISCOVERY_QUERY_SET_VERSION: Final = "github-repository-search-v1"
DISCOVERY_BUDGET_POLICY_VERSION: Final = "discovery-budget-policy-v1"
DISCOVERY_MAX_CANDIDATES: Final = 100
DISCOVERY_MAX_SEMANTIC_CANDIDATES: Final = 20

_Version = Annotated[str, Field(min_length=1, max_length=128)]
_Identifier = Annotated[
    str,
    Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"),
]
_ModelIdentity = Annotated[str, Field(min_length=1, max_length=256)]

_APPROVED_QUERIES: Final[tuple[tuple[str, str], ...]] = (
    (
        "agent-workflow-readme",
        '"agent workflow" in:name,description,readme is:public archived:false',
    ),
    (
        "ai-workflow-readme",
        '"AI workflow" in:name,description,readme is:public archived:false',
    ),
    (
        "llm-automation-readme",
        '"LLM automation" in:name,description,readme is:public archived:false',
    ),
    (
        "agent-skills-topic",
        "topic:agent-skills is:public archived:false",
    ),
)


def _self_digest(model: StrictFrozenModel, field: str) -> str:
    return sha256_digest(
        model.model_dump(
            mode="json",
            exclude_none=False,
            exclude={field},
        )
    )


class DiscoveryQueryV1(StrictFrozenModel):
    """One reviewed query entry; runtime text cannot satisfy this contract."""

    query_id: Annotated[str, Field(min_length=1, max_length=64)]
    query_text: Annotated[str, Field(min_length=1, max_length=256)]


class DiscoveryQuerySetV1(StrictFrozenModel):
    """The exact ordered v1 GitHub Repository Search policy."""

    schema_version: Literal["discovery-query-set-v1"]
    query_set_version: Literal["github-repository-search-v1"]
    queries: Annotated[tuple[DiscoveryQueryV1, ...], Field(min_length=4, max_length=4)]
    per_page: Literal[25]
    max_pages_per_query: Literal[4]
    acquisition_order: Literal["round_robin"]
    sort: Literal["updated"]
    order: Literal["desc"]
    query_set_digest: Digest | None = None

    @model_validator(mode="before")
    @classmethod
    def bind_query_set_digest(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("query_set_digest") is None:
            payload = dict(value)
            payload.pop("query_set_digest", None)
            digest_payload = dict(payload)
            payload["queries"] = tuple(payload.get("queries", ()))
            payload["query_set_digest"] = sha256_digest(digest_payload)
            return payload
        return value

    @model_validator(mode="after")
    def validate_exact_policy(self) -> DiscoveryQuerySetV1:
        actual = tuple((item.query_id, item.query_text) for item in self.queries)
        if actual != _APPROVED_QUERIES:
            raise ValueError("discovery query order or text is not the reviewed v1 policy")
        if (
            self.query_set_digest is None
            or self.query_set_digest != _self_digest(self, "query_set_digest")
        ):
            raise ValueError("discovery query-set digest mismatch")
        return self


class DiscoveryBudgetPolicyV1(StrictFrozenModel):
    """Literal, non-widenable repository and semantic-candidate ceilings."""

    schema_version: Literal["discovery-budget-policy-v1"] = (
        "discovery-budget-policy-v1"
    )
    budget_policy_version: Literal["discovery-budget-policy-v1"] = (
        DISCOVERY_BUDGET_POLICY_VERSION
    )
    max_candidates: Literal[100] = DISCOVERY_MAX_CANDIDATES
    max_semantic_candidates: Literal[20] = DISCOVERY_MAX_SEMANTIC_CANDIDATES
    budget_policy_digest: Digest | None = None

    @model_validator(mode="before")
    @classmethod
    def bind_budget_digest(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("budget_policy_digest") is None:
            payload = dict(value)
            payload.pop("budget_policy_digest", None)
            payload.setdefault("schema_version", "discovery-budget-policy-v1")
            payload.setdefault(
                "budget_policy_version", DISCOVERY_BUDGET_POLICY_VERSION
            )
            payload.setdefault("max_candidates", DISCOVERY_MAX_CANDIDATES)
            payload.setdefault(
                "max_semantic_candidates",
                DISCOVERY_MAX_SEMANTIC_CANDIDATES,
            )
            payload["budget_policy_digest"] = sha256_digest(payload)
            return payload
        return value

    @model_validator(mode="after")
    def validate_budget_digest(self) -> DiscoveryBudgetPolicyV1:
        if (
            self.budget_policy_digest is None
            or self.budget_policy_digest != _self_digest(self, "budget_policy_digest")
        ):
            raise ValueError("discovery budget-policy digest mismatch")
        return self

    def admit_discovery_ordinal(self, ordinal: int) -> int:
        if type(ordinal) is not int or not 1 <= ordinal <= DISCOVERY_MAX_CANDIDATES:
            raise ValueError("discovery ordinal exceeds the hard candidate ceiling")
        return ordinal

    def admit_semantic_ordinal(self, ordinal: int) -> int:
        if (
            type(ordinal) is not int
            or not 1 <= ordinal <= DISCOVERY_MAX_SEMANTIC_CANDIDATES
        ):
            raise ValueError("semantic ordinal exceeds the hard candidate ceiling")
        return ordinal


class DiscoveryRunAuthorityV1(StrictFrozenModel):
    """Stable discovery-run identity, excluding changing checkpoint heads."""

    schema_version: Literal["discovery-run-authority-v1"]
    run_id: _Identifier
    query_set_digest: Digest
    budget_policy_digest: Digest
    phase2_profile_version: _Version
    phase3_profile_version: _Version
    semantic_provider: Literal["openai", "deepseek"]
    extractor_model_id: _ModelIdentity
    generator_model_id: _ModelIdentity
    reviewer_model_id: _ModelIdentity
    initial_state_root_digest: Digest
    authority_digest: Digest

    @model_validator(mode="after")
    def validate_authority_digest(self) -> DiscoveryRunAuthorityV1:
        if self.authority_digest != _self_digest(self, "authority_digest"):
            raise ValueError("discovery run authority digest mismatch")
        return self
