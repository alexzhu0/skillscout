"""Wave-0 recovery specification for a reconcile-first Draft publisher.

No production publication imports occur during collection.  These tests become
red only when run, which protects the Wave-0 contract from implementation
coupling while documenting every crash and ambiguity disposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


PUBLICATION_CRASH_POINTS = (
    "after_blob_creation",
    "after_tree_creation",
    "after_commit_creation",
    "after_ref_visible",
    "after_pr_create_or_update",
    "after_reviewer_request",
    "after_remote_verification",
    "after_remote_success_before_local_commit",
)


@dataclass(frozen=True)
class RemoteRecoveryCase:
    name: str
    disposition: str
    content_writes: int = 0
    reviewer_requests: int = 0


def _publication() -> Any:
    from skillscout.application import publication

    return publication


def _reconcile(case: RemoteRecoveryCase) -> Any:
    """Call the eventual test-only recovery seam with bounded fake facts."""
    return _publication().reconcile_publication_fixture(
        case.name,
        configured_reviewers=("alpha-reviewer", "zeta-reviewer"),
    )


@pytest.mark.parametrize("crash_point", PUBLICATION_CRASH_POINTS)
def test_every_visible_crash_point_recovers_to_one_draft_without_force_or_renotify(
    crash_point: str,
) -> None:
    result = _publication().recover_crashed_publication_fixture(
        crash_point,
        configured_reviewers=("alpha-reviewer", "zeta-reviewer"),
    )
    assert result.draft_count == 1
    assert result.force_updates == 0
    assert result.duplicate_reviewer_notifications == 0
    assert result.final_remote_verification is True


@pytest.mark.parametrize(
    "case",
    (
        RemoteRecoveryCase("local_state_loss_desired_revision", "recovered", 0),
        RemoteRecoveryCase("duplicate_matching_pulls", "manual_intervention_required"),
        RemoteRecoveryCase("non_draft_pull", "manual_intervention_required"),
        RemoteRecoveryCase("wrong_base", "manual_intervention_required"),
        RemoteRecoveryCase("wrong_head", "manual_intervention_required"),
        RemoteRecoveryCase("malformed_marker", "manual_intervention_required"),
        RemoteRecoveryCase("cross_catalog_marker", "manual_intervention_required"),
        RemoteRecoveryCase("markerless_machine_commit", "manual_intervention_required"),
        RemoteRecoveryCase("inconsistent_lineage", "manual_intervention_required"),
        RemoteRecoveryCase("legitimate_later_package_revision", "update_draft", 1),
        RemoteRecoveryCase("human_commit", "manual_intervention_required"),
        RemoteRecoveryCase("force_updated_ref", "manual_intervention_required"),
        RemoteRecoveryCase("closed_pull", "manual_intervention_required"),
        RemoteRecoveryCase("reopened_pull", "manual_intervention_required"),
        RemoteRecoveryCase("deleted_pull", "manual_intervention_required"),
        RemoteRecoveryCase("default_branch_changed", "restart_reconciliation"),
        RemoteRecoveryCase("ref_conflict", "manual_intervention_required"),
    ),
    ids=lambda case: case.name,
)
def test_recovery_never_guesses_or_overwrites_ambiguous_remote_objects(
    case: RemoteRecoveryCase,
) -> None:
    result = _reconcile(case)
    assert result.disposition == case.disposition
    assert result.content_writes == case.content_writes
    assert result.force_updates == 0
    if case.disposition == "manual_intervention_required":
        assert result.selected_remote_object is None


def test_repeated_desired_revision_performs_zero_content_writes_after_local_state_loss() -> None:
    result = _reconcile(RemoteRecoveryCase("local_state_loss_desired_revision", "recovered"))
    assert result.content_writes == 0
    assert result.ref_updates == 0
    assert result.draft_count == 1


@pytest.mark.parametrize(
    "case",
    (
        RemoteRecoveryCase("pending_current_reviewer", "recovered", reviewer_requests=0),
        RemoteRecoveryCase("completed_reviewer", "recovered", reviewer_requests=0),
        RemoteRecoveryCase("removed_after_request", "manual_intervention_required", reviewer_requests=0),
        RemoteRecoveryCase("malformed_review_evidence", "manual_intervention_required", reviewer_requests=0),
        RemoteRecoveryCase("paginated_review_evidence", "recovered", reviewer_requests=0),
    ),
    ids=lambda case: case.name,
)
def test_recovery_uses_complete_individual_reviewer_evidence_without_renotification(
    case: RemoteRecoveryCase,
) -> None:
    result = _reconcile(case)
    assert result.disposition == case.disposition
    assert result.reviewer_requests == case.reviewer_requests
    assert result.observed_reviewers == tuple(sorted(set(result.observed_reviewers)))
    assert result.provider_teams == ()


def test_only_newly_created_pull_may_request_a_previously_unseen_individual() -> None:
    result = _reconcile(RemoteRecoveryCase("new_draft_no_prior_reviewer_opportunity", "created", reviewer_requests=1))
    assert result.reviewer_requests == 1
    recovered = _reconcile(RemoteRecoveryCase("removed_after_request", "manual_intervention_required"))
    assert recovered.reviewer_requests == 0
    assert recovered.disposition == "manual_intervention_required"


@pytest.mark.parametrize(
    "reviewers",
    (("zeta-reviewer", "alpha-reviewer"), ("alpha-reviewer", "alpha-reviewer")),
    ids=("unsorted", "duplicate"),
)
def test_reviewer_targets_must_be_sorted_unique_individual_logins(reviewers: tuple[str, ...]) -> None:
    with pytest.raises((ValueError, TypeError)):
        _publication().validate_reviewer_targets(reviewers=reviewers, teams=())


def test_team_configuration_is_rejected_before_token_or_network_access() -> None:
    guard = _publication().RejectingPublicationDependencies()
    with pytest.raises((ValueError, TypeError)):
        _publication().validate_reviewer_targets(
            reviewers=("alpha-reviewer",), teams=("maintainers",), dependencies=guard
        )
    assert guard.token_calls == 0
    assert guard.network_calls == 0


def test_stale_owned_catalog_files_are_deleted_only_inside_the_owned_subtree() -> None:
    result = _reconcile(RemoteRecoveryCase("stale_owned_catalog_files", "update_draft", 1))
    assert result.deleted_paths == ("skills/bounded-workflow/references/obsolete.md",)
    assert all(path.startswith("skills/bounded-workflow/") for path in result.deleted_paths)
    assert result.outside_owned_subtree_writes == 0
