"""Closed filter-policy-v1 rule set and the pure repository verdict function."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from skillscout.domain.models import StrictFrozenModel

FILTER_POLICY_VERSION = "filter-policy-v1"

ALLOWED_LICENSE_SPDX = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"})


class FilterRuleId(StrEnum):
    REPO_PUBLIC = "repo.public"
    REPO_NOT_ARCHIVED = "repo.not_archived"
    REPO_NOT_FORK = "repo.not_fork"
    REPO_HAS_DEFAULT_BRANCH = "repo.has_default_branch"
    REPO_HAS_README = "repo.has_readme"
    LICENSE_ALLOWLISTED = "license.allowlisted"
    LICENSE_SINGLE_FILE = "license.single_file"
    LICENSE_CONFIRMED_AT_SHA = "license.confirmed_at_sha"


class FilterResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


_RULE_RATIONALES: dict[FilterRuleId, str] = {
    FilterRuleId.REPO_PUBLIC: "The repository must be enabled and publicly visible.",
    FilterRuleId.REPO_NOT_ARCHIVED: "The repository must not be archived.",
    FilterRuleId.REPO_NOT_FORK: "The repository must not be a fork.",
    FilterRuleId.REPO_HAS_DEFAULT_BRANCH: "The repository must declare a default branch.",
    FilterRuleId.REPO_HAS_README: "The repository tree must contain a root README.",
    FilterRuleId.LICENSE_ALLOWLISTED: "The metadata license must be on the closed allowlist.",
    FilterRuleId.LICENSE_SINGLE_FILE: "The tree must not contain multiple root license files.",
    FilterRuleId.LICENSE_CONFIRMED_AT_SHA: (
        "The license endpoint must confirm the metadata license at the pinned SHA."
    ),
}


class RuleDecision(StrictFrozenModel):
    """One auditable closed outcome for exactly one filter rule."""

    rule_id: FilterRuleId
    rule_version: Literal["filter-policy-v1"]
    observed: Annotated[str, Field(max_length=256)]
    result: FilterResult
    rationale: str

    @model_validator(mode="after")
    def validate_closed_rationale(self) -> RuleDecision:
        if self.rationale != _RULE_RATIONALES[self.rule_id]:
            raise ValueError("rule rationale is not the closed per-rule rationale")
        return self


class RepoFacts(StrictFrozenModel):
    """The exact repository metadata facts the filter is allowed to observe."""

    private: bool
    archived: bool
    fork: bool
    disabled: bool
    visibility: Annotated[str, Field(min_length=1, max_length=32)]
    default_branch: Annotated[str, Field(min_length=1, max_length=200)] | None
    license_spdx: Annotated[str, Field(min_length=1, max_length=64)] | None


class TreeCandidate(StrictFrozenModel):
    """One repository tree entry as observed from the provider."""

    path: Annotated[str, Field(min_length=1, max_length=512)]
    mode: Annotated[str, Field(min_length=1, max_length=16)]
    type: Annotated[str, Field(min_length=1, max_length=16)]
    size: Annotated[int, Field(ge=0)]
    sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


class TreeFacts(StrictFrozenModel):
    """The exact tree-derived facts the filter is allowed to observe."""

    has_root_readme: bool
    root_license_files: tuple[Annotated[str, Field(min_length=1, max_length=512)], ...]


class LicenseConfirmation(StrictFrozenModel):
    """The closed outcome of the license endpoint lookup at the pinned SHA."""

    status: Literal["confirmed", "not_found", "mismatch", "noassertion"]
    observed_spdx: Annotated[str, Field(min_length=1, max_length=64)] | None


class FilterVerdict(StrictFrozenModel):
    """The complete ordered decision record and acceptance of one candidate."""

    policy_version: Literal["filter-policy-v1"]
    accepted: bool
    decisions: tuple[RuleDecision, ...]

    @model_validator(mode="after")
    def validate_closed_rule_order(self) -> FilterVerdict:
        if tuple(decision.rule_id for decision in self.decisions) != tuple(FilterRuleId):
            raise ValueError("verdict decisions must cover the closed ordered rule set")
        rejected = any(decision.result is FilterResult.FAIL for decision in self.decisions)
        if self.accepted == rejected:
            raise ValueError("verdict acceptance disagrees with rule decisions")
        return self


def evaluate_filter(
    repo_facts: RepoFacts,
    tree_facts: TreeFacts,
    license_confirmation: LicenseConfirmation,
) -> FilterVerdict:
    """Evaluate the closed ordered rules and accept only when no rule fails."""

    decisions: list[RuleDecision] = []

    def record(rule_id: FilterRuleId, observed: str, result: FilterResult) -> None:
        decisions.append(
            RuleDecision(
                rule_id=rule_id,
                rule_version=FILTER_POLICY_VERSION,
                observed=observed,
                result=result,
                rationale=_RULE_RATIONALES[rule_id],
            )
        )

    repo_public = (
        not repo_facts.private
        and not repo_facts.disabled
        and repo_facts.visibility == "public"
    )
    record(
        FilterRuleId.REPO_PUBLIC,
        (
            f"private={repo_facts.private},disabled={repo_facts.disabled},"
            f"visibility={repo_facts.visibility}"
        ),
        FilterResult.PASS if repo_public else FilterResult.FAIL,
    )
    record(
        FilterRuleId.REPO_NOT_ARCHIVED,
        f"archived={repo_facts.archived}",
        FilterResult.PASS if not repo_facts.archived else FilterResult.FAIL,
    )
    record(
        FilterRuleId.REPO_NOT_FORK,
        f"fork={repo_facts.fork}",
        FilterResult.PASS if not repo_facts.fork else FilterResult.FAIL,
    )
    record(
        FilterRuleId.REPO_HAS_DEFAULT_BRANCH,
        f"default_branch={repo_facts.default_branch}",
        FilterResult.PASS if repo_facts.default_branch is not None else FilterResult.FAIL,
    )
    record(
        FilterRuleId.REPO_HAS_README,
        f"has_root_readme={tree_facts.has_root_readme}",
        FilterResult.PASS if tree_facts.has_root_readme else FilterResult.FAIL,
    )
    license_allowlisted = repo_facts.license_spdx in ALLOWED_LICENSE_SPDX
    record(
        FilterRuleId.LICENSE_ALLOWLISTED,
        f"license_spdx={repo_facts.license_spdx}",
        FilterResult.PASS if license_allowlisted else FilterResult.FAIL,
    )
    single_license_file = len(tree_facts.root_license_files) <= 1
    record(
        FilterRuleId.LICENSE_SINGLE_FILE,
        f"root_license_files={len(tree_facts.root_license_files)}",
        FilterResult.PASS if single_license_file else FilterResult.FAIL,
    )

    confirmation_observed = (
        f"status={license_confirmation.status},"
        f"observed_spdx={license_confirmation.observed_spdx}"
    )
    if not license_allowlisted or not single_license_file:
        record(
            FilterRuleId.LICENSE_CONFIRMED_AT_SHA,
            confirmation_observed,
            FilterResult.NOT_APPLICABLE,
        )
    else:
        confirmed = (
            license_confirmation.status == "confirmed"
            and license_confirmation.observed_spdx == repo_facts.license_spdx
        )
        record(
            FilterRuleId.LICENSE_CONFIRMED_AT_SHA,
            confirmation_observed,
            FilterResult.PASS if confirmed else FilterResult.FAIL,
        )

    return FilterVerdict(
        policy_version=FILTER_POLICY_VERSION,
        accepted=all(decision.result is not FilterResult.FAIL for decision in decisions),
        decisions=tuple(decisions),
    )
