"""Wave-0 RED contracts for the Phase 6 acceptance authority vocabulary.

Imports of the future production module are deliberately deferred until test
execution.  Collection must remain green; each absent production symbol is one
explicit, stable RED node owned by Plan 06-04.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from skillscout.domain.canonical import canonical_json_bytes, sha256_digest


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_MATRIX_PATH = ROOT / "tests" / "fixtures" / "acceptance" / "scenario_matrix.json"
DIGEST_A = "sha256:" + ("a" * 64)
DIGEST_B = "sha256:" + ("b" * 64)
DIGEST_C = "sha256:" + ("c" * 64)
SHA_A = "a" * 40
SHA_B = "b" * 40
TIMESTAMP_A = "2026-07-29T00:00:00.000000Z"
TIMESTAMP_B = "2026-07-29T00:30:00.000000Z"

REQUIRED_DOMAIN_CONTRACTS = (
    "NominationEntryV1",
    "NominationSetV1",
    "BenchmarkEntryV1",
    "BenchmarkLockAttestationV1",
    "LockedBenchmarkManifestV1",
    "AcceptanceScenarioResultV1",
    "HostedIsolationCapabilityV1",
    "OfflineAdversarialRunV1",
    "ReplayEvidenceV1",
    "ChangedSourceEvidenceV1",
    "PublicationReplayCompletionV1",
    "ChangedSourceDraftUpdateCompletionV1",
    "GateB4BindingV1",
    "HumanSkillReviewAttestationV1",
    "ProbeCleanupAttestationV1",
    "ReviewerCalibrationV1",
    "AcceptanceEvidenceRootV1",
    "AcceptanceReleaseVerdictV1",
)

EXACT_FIELDS = {
    "NominationEntryV1": (
        "repository_full_name",
        "repository_id",
        "exact_commit_sha",
        "license_spdx",
        "selection_source",
        "selection_evidence_digests",
        "entry_digest",
    ),
    "BenchmarkEntryV1": (
        "repository_full_name",
        "repository_id",
        "exact_commit_sha",
        "license_spdx",
        "selection_source",
        "coverage_role",
        "nomination_entry_digest",
        "selection_evidence_digests",
        "entry_digest",
    ),
    "NominationSetV1": (
        "nomination_set_id",
        "query_set_digest",
        "search_run_authority_digest",
        "search_derived_entries",
        "user_nominated_entries",
        "created_at",
        "nomination_set_digest",
    ),
    "BenchmarkLockAttestationV1": (
        "manifest_version",
        "nomination_set_digest",
        "manifest_digest",
        "reviewer_id",
        "locked_at",
        "attestation_digest",
    ),
    "LockedBenchmarkManifestV1": (
        "manifest_version",
        "nomination_set_digest",
        "entries",
        "lock_attestation",
        "prior_manifest_digest",
        "manifest_digest",
    ),
    "HostedIsolationCapabilityV1": (
        "workflow_sha256",
        "source_commit_sha",
        "hosted_run_id",
        "run_attempt",
        "runner_image",
        "isolation_mechanism",
        "probe_artifact_locator",
        "probe_artifact_digest",
        "control_command_digest",
        "direct_probe_command_digest",
        "child_probe_command_digest",
        "control_outcome",
        "direct_network_outcome",
        "child_network_outcome",
        "credential_count",
        "state_write_capability",
        "synthetic_scan_manifest_digest",
        "synthetic_canary_hit_count",
        "reviewer_id",
        "reviewed_at",
        "capability_digest",
    ),
    "OfflineAdversarialRunV1": (
        "acceptance_run_id",
        "hosted_capability_digest",
        "workflow_sha256",
        "source_commit_sha",
        "hosted_run_id",
        "run_attempt",
        "isolation_mechanism",
        "scenario_matrix_digest",
        "required_scenario_ids",
        "completed_scenario_ids",
        "scenario_result_digests",
        "controlled_scenario_count",
        "os_syscall_network_denied",
        "direct_network_denied",
        "child_network_denied",
        "untrusted_execution_count",
        "unapproved_network_effect_count",
        "unauthorized_effect_count",
        "synthetic_scan_manifest_digest",
        "synthetic_canary_hit_count",
        "started_at",
        "completed_at",
        "run_digest",
    ),
    "PublicationReplayCompletionV1": (
        "acceptance_run_id",
        "replay_intent_digest",
        "repository_id",
        "source_commit_sha",
        "workflow_fingerprint",
        "workflow_spec_authority_digest",
        "publication_policy_version",
        "publication_key",
        "publication_marker",
        "target_repository_id",
        "target_repository_full_name",
        "pull_request_number",
        "head_branch",
        "head_commit_sha",
        "draft",
        "open",
        "prior_publication_receipt_digest",
        "before_remote_observation_digest",
        "after_remote_observation_digest",
        "branch_create_count",
        "commit_create_count",
        "pull_request_create_count",
        "pull_request_update_count",
        "reviewer_request_count",
        "completion_recorded_at",
        "completion_digest",
    ),
    "ChangedSourceDraftUpdateCompletionV1": (
        "acceptance_run_id",
        "changed_source_intent_digest",
        "repository_id",
        "prior_source_commit_sha",
        "new_source_commit_sha",
        "prior_workflow_fingerprint",
        "new_workflow_fingerprint",
        "prior_workflow_spec_authority_digest",
        "new_workflow_spec_authority_digest",
        "publication_policy_version",
        "publication_key",
        "publication_marker",
        "target_repository_id",
        "target_repository_full_name",
        "pull_request_number",
        "head_branch",
        "previous_head_commit_sha",
        "new_head_commit_sha",
        "previous_desired_revision_digest",
        "new_desired_revision_digest",
        "previous_lineage_id",
        "new_lineage_id",
        "prior_lineage_binding_digest",
        "lineage_approval_record_digest",
        "remote_reconciliation_digest",
        "new_branch_count",
        "new_pull_request_count",
        "new_reviewer_request_count",
        "head_update_count",
        "remote_commit_count",
        "draft",
        "open",
        "completion_recorded_at",
        "completion_digest",
    ),
}


def _acceptance_module(*, skip_if_missing: bool) -> Any:
    if importlib.util.find_spec("skillscout.domain.acceptance") is None:
        if skip_if_missing:
            pytest.skip("phase6-domain-contracts-not-yet-implemented")
        return None
    return importlib.import_module("skillscout.domain.acceptance")


def _symbol(name: str, *, skip_if_missing: bool = True) -> type[Any]:
    module = _acceptance_module(skip_if_missing=skip_if_missing)
    if module is None:
        pytest.fail(f"phase6-missing-domain-contract:{name}", pytrace=False)
    value = getattr(module, name, None)
    if value is None:
        if skip_if_missing:
            pytest.skip("phase6-domain-contracts-not-yet-implemented")
        pytest.fail(f"phase6-missing-domain-contract:{name}", pytrace=False)
    return value


@pytest.mark.parametrize("contract", REQUIRED_DOMAIN_CONTRACTS, ids=REQUIRED_DOMAIN_CONTRACTS)
def test_required_phase6_domain_contract_is_missing(contract: str) -> None:
    _symbol(contract, skip_if_missing=False)


def test_scenario_matrix_is_bounded_canonical_and_evaluator_only() -> None:
    raw = SCENARIO_MATRIX_PATH.read_bytes()
    matrix = json.loads(raw)
    assert 15 <= len(matrix) <= 32
    assert len(raw) <= 32_768
    assert tuple(matrix) == (
        "positive_single_workflow",
        "positive_multi_workflow",
        "negative_filter",
        "negative_no_workflow",
        "borderline_qualification",
        "negative_format_validation",
        "negative_security_validation",
        "negative_reviewer",
        "injection_direct_override",
        "injection_privilege_masquerade",
        "injection_secret_solicitation",
        "injection_encoded_payload",
        "injection_exfiltration_markup",
        "injection_action_solicitation",
        "injection_cross_stage",
        "supply_chain_shell",
        "supply_chain_subprocess",
        "supply_chain_dynamic_import",
        "supply_chain_source_execution",
        "supply_chain_executable_scripts",
        "supply_chain_network",
        "supply_chain_synthetic_canary",
        "system_provider_exhausted",
        "system_schema_exhausted",
        "system_harness_failed",
    )
    scenario_ids = tuple(item["scenario_id"] for item in matrix.values())
    assert scenario_ids == tuple(sorted(scenario_ids, key=scenario_ids.index))
    assert len(scenario_ids) == len(set(scenario_ids))
    assert sum(item["adversarial_role"] == "business_positive" for item in matrix.values()) == 1
    assert sum(item["adversarial_role"] == "business_positive_multi_workflow" for item in matrix.values()) == 1
    assert sum(item["adversarial_role"] == "business_negative" for item in matrix.values()) == 2
    assert sum(item["adversarial_role"] == "business_borderline" for item in matrix.values()) == 1
    for item in matrix.values():
        assert tuple(item) == (
            "scenario_id",
            "adversarial_role",
            "expected_terminal_class",
            "expected_outcome",
            "evaluator_notes",
            "human_label",
            "payload",
        )
        assert set(item["payload"]) == {"fixture_id", "mutation"}
        serialized_request = canonical_json_bytes(item["payload"])
        for evaluator_only in (
            item["expected_terminal_class"],
            item["expected_outcome"],
            item["evaluator_notes"],
            item["human_label"],
        ):
            assert evaluator_only.encode("utf-8") not in serialized_request
        system_failures = {
            "provider_exhausted",
            "schema_exhausted",
            "evidence_missing",
            "harness_failed",
        }
        if item["expected_terminal_class"] == "system_failure":
            assert item["expected_outcome"] in system_failures
        else:
            assert item["expected_outcome"] not in system_failures
    forbidden_keys = {
        "repository_body",
        "raw_log",
        "response_body",
        "authorization",
        "token",
        "api_key",
        "private_key",
        "credential",
    }
    assert forbidden_keys.isdisjoint(raw.decode("utf-8").casefold().replace("-", "_").split('"'))


@pytest.mark.parametrize("contract", tuple(EXACT_FIELDS), ids=tuple(EXACT_FIELDS))
def test_exact_high_risk_contract_field_sets(contract: str) -> None:
    model = _symbol(contract)
    assert tuple(model.model_fields) == ("schema_version", *EXACT_FIELDS[contract])
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["frozen"] is True


def _hosted_payload() -> dict[str, object]:
    return {
        "schema_version": "hosted-isolation-capability-v1",
        "workflow_sha256": DIGEST_A,
        "source_commit_sha": SHA_A,
        "hosted_run_id": 1001,
        "run_attempt": 1,
        "runner_image": "github-actions-ubuntu-24.04",
        "isolation_mechanism": "docker_network_none",
        "probe_artifact_locator": "phase6/probes/1001/1",
        "probe_artifact_digest": DIGEST_A,
        "control_command_digest": DIGEST_A,
        "direct_probe_command_digest": DIGEST_B,
        "child_probe_command_digest": DIGEST_C,
        "control_outcome": "passed",
        "direct_network_outcome": "denied",
        "child_network_outcome": "denied",
        "credential_count": 0,
        "state_write_capability": False,
        "synthetic_scan_manifest_digest": DIGEST_B,
        "synthetic_canary_hit_count": 0,
        "reviewer_id": "security-reviewer",
        "reviewed_at": TIMESTAMP_B,
    }


def _offline_payload(capability_digest: str) -> dict[str, object]:
    scenario_ids = tuple(f"scenario-{index:02d}" for index in range(1, 16))
    result_digests = tuple(
        "sha256:" + f"{index:064x}" for index in range(1, 16)
    )
    return {
        "schema_version": "offline-adversarial-run-v1",
        "acceptance_run_id": "acceptance-run-001",
        "hosted_capability_digest": capability_digest,
        "workflow_sha256": DIGEST_A,
        "source_commit_sha": SHA_A,
        "hosted_run_id": 1001,
        "run_attempt": 1,
        "isolation_mechanism": "docker_network_none",
        "scenario_matrix_digest": DIGEST_C,
        "required_scenario_ids": scenario_ids,
        "completed_scenario_ids": scenario_ids,
        "scenario_result_digests": result_digests,
        "controlled_scenario_count": 15,
        "os_syscall_network_denied": True,
        "direct_network_denied": True,
        "child_network_denied": True,
        "untrusted_execution_count": 0,
        "unapproved_network_effect_count": 0,
        "unauthorized_effect_count": 0,
        "synthetic_scan_manifest_digest": DIGEST_B,
        "synthetic_canary_hit_count": 0,
        "started_at": TIMESTAMP_A,
        "completed_at": TIMESTAMP_B,
    }


def test_hosted_capability_and_offline_run_bind_exact_reviewed_denials() -> None:
    hosted_type = _symbol("HostedIsolationCapabilityV1")
    offline_type = _symbol("OfflineAdversarialRunV1")
    hosted = hosted_type.model_validate(_hosted_payload(), strict=True)
    offline = offline_type.model_validate(
        _offline_payload(hosted.capability_digest), strict=True
    )
    assert offline.hosted_capability_digest == hosted.capability_digest
    assert (
        offline.workflow_sha256,
        offline.source_commit_sha,
        offline.hosted_run_id,
        offline.run_attempt,
        offline.isolation_mechanism,
    ) == (
        hosted.workflow_sha256,
        hosted.source_commit_sha,
        hosted.hosted_run_id,
        hosted.run_attempt,
        hosted.isolation_mechanism,
    )
    assert offline.completed_scenario_ids == offline.required_scenario_ids


@pytest.mark.parametrize(
    ("target", "field", "value"),
    (
        ("hosted", "isolation_mechanism", "best_effort_firewall"),
        ("hosted", "control_outcome", "failed"),
        ("hosted", "direct_network_outcome", "allowed"),
        ("hosted", "child_network_outcome", "allowed"),
        ("hosted", "credential_count", 1),
        ("hosted", "state_write_capability", True),
        ("hosted", "synthetic_canary_hit_count", 1),
        ("offline", "hosted_capability_digest", DIGEST_C),
        ("offline", "completed_scenario_ids", ("scenario-01",)),
        ("offline", "os_syscall_network_denied", False),
        ("offline", "direct_network_denied", False),
        ("offline", "child_network_denied", False),
        ("offline", "untrusted_execution_count", 1),
        ("offline", "unapproved_network_effect_count", 1),
        ("offline", "unauthorized_effect_count", 1),
        ("offline", "synthetic_canary_hit_count", 1),
        ("offline", "completed_at", "2026-07-28T23:59:59.000000Z"),
    ),
)
def test_hosted_and_offline_contracts_reject_every_authority_drift(
    target: str, field: str, value: object
) -> None:
    hosted_type = _symbol("HostedIsolationCapabilityV1")
    offline_type = _symbol("OfflineAdversarialRunV1")
    hosted = hosted_type.model_validate(_hosted_payload(), strict=True)
    payload = (
        hosted.model_dump(mode="json")
        if target == "hosted"
        else _offline_payload(hosted.capability_digest)
    )
    payload[field] = value
    digest_field = "capability_digest" if target == "hosted" else "run_digest"
    payload.pop(digest_field, None)
    with pytest.raises(ValidationError):
        (hosted_type if target == "hosted" else offline_type).model_validate(
            payload, strict=True
        )


@pytest.mark.parametrize(
    "forbidden",
    (
        "raw_log",
        "fixture_prose",
        "response_body",
        "authorization",
        "token",
        "api_key",
        "private_key",
        "credential",
        "repository_path",
        "home_path",
    ),
)
def test_acceptance_authorities_reject_raw_secret_or_unrestricted_fields(
    forbidden: str,
) -> None:
    model = _symbol("HostedIsolationCapabilityV1")
    with pytest.raises(ValidationError):
        model.model_validate(
            {**_hosted_payload(), forbidden: "synthetic-forbidden-value"},
            strict=True,
        )


def _replay_completion_payload() -> dict[str, object]:
    return {
        "schema_version": "publication-replay-completion-v1",
        "acceptance_run_id": "acceptance-run-001",
        "replay_intent_digest": DIGEST_A,
        "repository_id": 101,
        "source_commit_sha": SHA_A,
        "workflow_fingerprint": DIGEST_A,
        "workflow_spec_authority_digest": DIGEST_B,
        "publication_policy_version": "publication-policy-v1",
        "publication_key": DIGEST_A,
        "publication_marker": DIGEST_B,
        "target_repository_id": 202,
        "target_repository_full_name": "catalog-org/skills",
        "pull_request_number": 17,
        "head_branch": "skillscout/bounded-workflow",
        "head_commit_sha": SHA_A,
        "draft": True,
        "open": True,
        "prior_publication_receipt_digest": DIGEST_C,
        "before_remote_observation_digest": DIGEST_B,
        "after_remote_observation_digest": DIGEST_B,
        "branch_create_count": 0,
        "commit_create_count": 0,
        "pull_request_create_count": 0,
        "pull_request_update_count": 0,
        "reviewer_request_count": 0,
        "completion_recorded_at": TIMESTAMP_B,
    }


def _changed_completion_payload() -> dict[str, object]:
    return {
        "schema_version": "changed-source-draft-update-completion-v1",
        "acceptance_run_id": "acceptance-run-001",
        "changed_source_intent_digest": DIGEST_A,
        "repository_id": 101,
        "prior_source_commit_sha": SHA_A,
        "new_source_commit_sha": SHA_B,
        "prior_workflow_fingerprint": DIGEST_A,
        "new_workflow_fingerprint": DIGEST_B,
        "prior_workflow_spec_authority_digest": DIGEST_A,
        "new_workflow_spec_authority_digest": DIGEST_B,
        "publication_policy_version": "publication-policy-v1",
        "publication_key": DIGEST_A,
        "publication_marker": DIGEST_B,
        "target_repository_id": 202,
        "target_repository_full_name": "catalog-org/skills",
        "pull_request_number": 17,
        "head_branch": "skillscout/bounded-workflow",
        "previous_head_commit_sha": SHA_A,
        "new_head_commit_sha": SHA_B,
        "previous_desired_revision_digest": DIGEST_A,
        "new_desired_revision_digest": DIGEST_B,
        "previous_lineage_id": DIGEST_C,
        "new_lineage_id": DIGEST_C,
        "prior_lineage_binding_digest": DIGEST_A,
        "lineage_approval_record_digest": DIGEST_B,
        "remote_reconciliation_digest": DIGEST_C,
        "new_branch_count": 0,
        "new_pull_request_count": 0,
        "new_reviewer_request_count": 0,
        "head_update_count": 1,
        "remote_commit_count": 1,
        "draft": True,
        "open": True,
        "completion_recorded_at": TIMESTAMP_B,
    }


@pytest.mark.parametrize(
    ("contract", "payload_factory", "field", "value"),
    (
        ("PublicationReplayCompletionV1", _replay_completion_payload, "after_remote_observation_digest", DIGEST_C),
        ("PublicationReplayCompletionV1", _replay_completion_payload, "commit_create_count", 1),
        ("PublicationReplayCompletionV1", _replay_completion_payload, "draft", False),
        ("PublicationReplayCompletionV1", _replay_completion_payload, "open", False),
        ("ChangedSourceDraftUpdateCompletionV1", _changed_completion_payload, "new_source_commit_sha", SHA_A),
        ("ChangedSourceDraftUpdateCompletionV1", _changed_completion_payload, "new_lineage_id", DIGEST_B),
        ("ChangedSourceDraftUpdateCompletionV1", _changed_completion_payload, "new_pull_request_count", 1),
        ("ChangedSourceDraftUpdateCompletionV1", _changed_completion_payload, "head_update_count", 0),
        ("ChangedSourceDraftUpdateCompletionV1", _changed_completion_payload, "remote_commit_count", 0),
        ("ChangedSourceDraftUpdateCompletionV1", _changed_completion_payload, "draft", False),
    ),
)
def test_publication_completion_contracts_reject_stale_or_duplicate_effects(
    contract: str, payload_factory: Any, field: str, value: object
) -> None:
    model = _symbol(contract)
    payload = payload_factory()
    payload[field] = value
    with pytest.raises(ValidationError):
        model.model_validate(payload, strict=True)


def test_reviewer_calibration_is_redacted_self_digested_and_advice_only() -> None:
    model = _symbol("ReviewerCalibrationV1")
    fields = set(model.model_fields)
    assert {
        "schema_version",
        "acceptance_run_id",
        "label_digests",
        "review_result_digests",
        "case_count",
        "agreement_count",
        "agreement_rate",
        "cohen_kappa",
        "disagreement_case_digests",
        "advice_only",
        "calibration_digest",
    } <= fields
    assert {
        "label_text",
        "reviewer_response",
        "publication_authority",
        "override",
    }.isdisjoint(fields)


def test_benchmark_contracts_freeze_fixed_identity_distribution_and_human_lock() -> None:
    nomination_entry = _symbol("NominationEntryV1")
    entry = _symbol("BenchmarkEntryV1")
    nomination = _symbol("NominationSetV1")
    lock = _symbol("BenchmarkLockAttestationV1")
    manifest = _symbol("LockedBenchmarkManifestV1")
    assert {
        "repository_id",
        "repository_full_name",
        "exact_commit_sha",
        "license_spdx",
        "selection_source",
        "coverage_role",
        "nomination_entry_digest",
        "selection_evidence_digests",
        "entry_digest",
    } <= set(entry.model_fields)
    assert "coverage_role" not in nomination_entry.model_fields
    with pytest.raises(ValidationError):
        nomination_entry.model_validate(
            {
                "schema_version": "nomination-entry-v1",
                "repository_full_name": "octo-org/workflow-kit",
                "repository_id": 910001,
                "exact_commit_sha": SHA_A,
                "license_spdx": "MIT",
                "selection_source": "search_derived",
                "selection_evidence_digests": [DIGEST_A],
                "coverage_role": "positive",
            },
            strict=True,
        )
    assert {
        "default_branch",
        "branch",
        "ref",
        "expected_outcome",
        "evaluator_notes",
    }.isdisjoint(entry.model_fields)
    assert {
        "search_derived_entries",
        "user_nominated_entries",
        "nomination_set_digest",
    } <= set(nomination.model_fields)
    assert {"reviewer_id", "locked_at", "attestation_digest"} <= set(
        lock.model_fields
    )
    assert {
        "manifest_version",
        "nomination_set_digest",
        "entries",
        "lock_attestation",
        "prior_manifest_digest",
        "manifest_digest",
    } <= set(manifest.model_fields)


def test_locked_manifest_strict_json_round_trip_preserves_tuple_contracts() -> None:
    entry_model = _symbol("BenchmarkEntryV1")
    attestation_model = _symbol("BenchmarkLockAttestationV1")
    manifest_model = _symbol("LockedBenchmarkManifestV1")
    roles = (
        "positive",
        "positive_multi_workflow",
        "negative",
        "negative",
        "borderline",
    )
    entries = tuple(
        sorted(
            (
                entry_model(
                    schema_version="benchmark-entry-v1",
                    repository_full_name=f"octo-org/workflow-{index}",
                    repository_id=910000 + index,
                    exact_commit_sha=f"{index:040x}",
                    license_spdx="MIT",
                    selection_source="search_derived",
                    coverage_role=role,
                    nomination_entry_digest=sha256_digest(
                        {"nomination": index}
                    ),
                    selection_evidence_digests=(
                        sha256_digest({"evidence": index}),
                    ),
                )
                for index, role in enumerate(roles, 1)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    preimage = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": DIGEST_A,
        "entries": [
            item.model_dump(mode="json", exclude_none=False)
            for item in entries
        ],
        "prior_manifest_digest": None,
    }
    manifest_digest = sha256_digest(preimage)
    attestation = attestation_model(
        schema_version="benchmark-lock-attestation-v1",
        manifest_version=1,
        nomination_set_digest=DIGEST_A,
        manifest_digest=manifest_digest,
        reviewer_id="reviewer",
        locked_at=TIMESTAMP_A,
    )
    manifest = manifest_model(
        schema_version="locked-benchmark-manifest-v1",
        manifest_version=1,
        nomination_set_digest=DIGEST_A,
        entries=entries,
        lock_attestation=attestation,
        prior_manifest_digest=None,
        manifest_digest=manifest_digest,
    )

    assert manifest_model.model_validate_json(
        canonical_json_bytes(manifest),
        strict=True,
    ) == manifest


def test_human_review_contract_requires_exact_head_and_complete_d17_checklist() -> None:
    model = _symbol("HumanSkillReviewAttestationV1")
    assert {
        "target_repository_id",
        "pull_request_number",
        "pr_head_sha",
        "source_commit_sha",
        "package_digest",
        "publication_marker_digest",
        "verdict",
        "usefulness_checked",
        "fidelity_checked",
        "provenance_license_checked",
        "instruction_safety_checked",
        "diff_scope_checked",
        "reviewer_id",
        "reviewed_at",
        "attestation_digest",
    } <= set(model.model_fields)
    assert {
        "requested_reviewer",
        "aggregate_score",
        "waiver",
        "override",
    }.isdisjoint(model.model_fields)


def test_terminal_taxonomy_and_release_verdict_are_closed_non_waivable_gates() -> None:
    module = _acceptance_module(skip_if_missing=True)
    assert tuple(item.value for item in module.AcceptanceTerminalClass) == (
        "eligible",
        "business_terminal",
        "system_failure",
    )
    verdict = _symbol("AcceptanceReleaseVerdictV1")
    assert {
        "aggregate_score",
        "waive_security",
        "waive_permission",
        "waive_idempotency",
        "waive_provenance",
        "waive_license",
    }.isdisjoint(verdict.model_fields)
