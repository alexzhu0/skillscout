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


def _v2_benchmark_entries() -> tuple[Any, ...]:
    entry_model = _symbol("BenchmarkEntryV1", skip_if_missing=False)
    roles = (
        "positive",
        "positive_multi_workflow",
        "negative",
        "negative",
        "borderline",
    )
    return tuple(
        sorted(
            (
                entry_model(
                    schema_version="benchmark-entry-v1",
                    repository_full_name=f"octo-org/v2-workflow-{index}",
                    repository_id=920000 + index,
                    exact_commit_sha=f"{index:040x}",
                    license_spdx="MIT",
                    selection_source="search_derived",
                    coverage_role=role,
                    nomination_entry_digest=sha256_digest(
                        {"v2-nomination": index}
                    ),
                    selection_evidence_digests=(
                        sha256_digest({"v2-evidence": index}),
                    ),
                )
                for index, role in enumerate(roles, 1)
            ),
            key=lambda item: item.entry_digest,
        )
    )


def _v2_selection_manifest() -> Any:
    """Build the exact immutable V1 selection preimage carried by a V2 lock."""

    attestation_model = _symbol("BenchmarkLockAttestationV1", skip_if_missing=False)
    manifest_model = _symbol("LockedBenchmarkManifestV1", skip_if_missing=False)
    entries = _v2_benchmark_entries()
    preimage = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": DIGEST_C,
        "entries": [
            entry.model_dump(mode="json", exclude_none=False)
            for entry in entries
        ],
        "prior_manifest_digest": None,
    }
    manifest_digest = sha256_digest(preimage)
    return manifest_model(
        **preimage,
        lock_attestation=attestation_model(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=DIGEST_C,
            manifest_digest=manifest_digest,
            reviewer_id="v2-reviewer",
            locked_at=TIMESTAMP_A,
        ),
        manifest_digest=manifest_digest,
    )


def _v2_benchmark_lock_payload() -> dict[str, object]:
    receipt_model = _symbol("BenchmarkLockApprovalReceiptV2", skip_if_missing=False)
    source_state_binding_digest = _symbol(
        "fresh_benchmark_source_state_binding_digest",
        skip_if_missing=False,
    )
    receipt = receipt_model(
        schema_version="benchmark-lock-approval-receipt-v2",
        purpose="benchmark_lock",
        environment="phase6-human-benchmark-lock",
        source_repository_id=1_310_897_029,
        source_repository_full_name="alexzhu0/skillscout",
        reviewer_login="alexzhu0",
        reviewer_id=101,
        workflow_run_id=1001,
        workflow_run_attempt=1,
        source_commit_sha=SHA_A,
        workflow_sha256=DIGEST_A,
        trigger_identity="workflow_dispatch",
        approval_record_digest=DIGEST_B,
    )
    selection_manifest = _v2_selection_manifest()
    return {
        "schema_version": "locked-benchmark-manifest-v2",
        "purpose": "benchmark_lock",
        "source_repository_id": receipt.source_repository_id,
        "source_repository_full_name": receipt.source_repository_full_name,
        "state_repository_id": 9001,
        "state_repository_full_name": "octo-org/skillscout-state",
        "parent_state_commit_sha": SHA_B,
        "parent_state_root_digest": DIGEST_C,
        "source_commit_sha": SHA_A,
        "acceptance_workflow_sha256": DIGEST_A,
        "source_state_binding_digest": source_state_binding_digest(
            source_repository_id=receipt.source_repository_id,
            source_repository_full_name=receipt.source_repository_full_name,
            state_repository_id=9001,
            state_repository_full_name="octo-org/skillscout-state",
            parent_state_commit_sha=SHA_B,
            parent_state_root_digest=DIGEST_C,
            source_commit_sha=SHA_A,
            acceptance_workflow_sha256=DIGEST_A,
            selection_manifest_digest=selection_manifest.manifest_digest,
            nomination_set_digest=selection_manifest.nomination_set_digest,
        ),
        "selection_manifest_digest": selection_manifest.manifest_digest,
        "nomination_set_digest": selection_manifest.nomination_set_digest,
        "selection_manifest": selection_manifest,
        "entries": selection_manifest.entries,
        "environment": receipt.environment,
        "approved_reviewer_login": receipt.reviewer_login,
        "approved_reviewer_id": receipt.reviewer_id,
        "workflow_run_id": receipt.workflow_run_id,
        "workflow_run_attempt": receipt.workflow_run_attempt,
        "trigger_identity": receipt.trigger_identity,
        "approval_record_digest": receipt.approval_record_digest,
        "approval_receipt": receipt,
        "approval_receipt_digest": receipt.receipt_digest,
    }


def _benchmark_rebind_chain() -> tuple[Any, Any]:
    """Build a closed nomination-to-V2-lock chain for rebind contract tests."""

    nomination_entry_model = _symbol("NominationEntryV1", skip_if_missing=False)
    nomination_model = _symbol("NominationSetV1", skip_if_missing=False)
    entry_model = _symbol("BenchmarkEntryV1", skip_if_missing=False)
    attestation_model = _symbol("BenchmarkLockAttestationV1", skip_if_missing=False)
    selection_model = _symbol("LockedBenchmarkManifestV1", skip_if_missing=False)
    lock_model = _symbol("LockedBenchmarkManifestV2", skip_if_missing=False)
    source_binding = _symbol(
        "fresh_benchmark_source_state_binding_digest", skip_if_missing=False
    )
    roles = (
        "positive",
        "positive_multi_workflow",
        "negative",
        "negative",
        "borderline",
    )
    nominations = tuple(
        sorted(
            (
                nomination_entry_model(
                    schema_version="nomination-entry-v1",
                    repository_full_name=f"octo-org/rebind-workflow-{index}",
                    repository_id=930000 + index,
                    exact_commit_sha=f"{index + 10:040x}",
                    license_spdx="MIT",
                    selection_source="search_derived",
                    selection_evidence_digests=(
                        sha256_digest({"rebind-evidence": index}),
                    ),
                )
                for index in range(1, 6)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    nomination = nomination_model(
        schema_version="nomination-set-v1",
        nomination_set_id="phase6-approved-selection",
        query_set_digest=sha256_digest({"rebind-query": 1}),
        search_run_authority_digest=sha256_digest({"rebind-authority": 1}),
        search_derived_entries=nominations,
        user_nominated_entries=(),
        created_at=TIMESTAMP_A,
    )
    entries = tuple(
        sorted(
            (
                entry_model(
                    schema_version="benchmark-entry-v1",
                    repository_full_name=item.repository_full_name,
                    repository_id=item.repository_id,
                    exact_commit_sha=item.exact_commit_sha,
                    license_spdx=item.license_spdx,
                    selection_source="search_derived",
                    coverage_role=roles[index],
                    nomination_entry_digest=item.entry_digest,
                    selection_evidence_digests=item.selection_evidence_digests,
                )
                for index, item in enumerate(nominations)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    selection_preimage = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": nomination.nomination_set_digest,
        "entries": [
            entry.model_dump(mode="json", exclude_none=False) for entry in entries
        ],
        "prior_manifest_digest": None,
    }
    selection_digest = sha256_digest(selection_preimage)
    selection = selection_model(
        **selection_preimage,
        lock_attestation=attestation_model(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=nomination.nomination_set_digest,
            manifest_digest=selection_digest,
            reviewer_id="rebind-reviewer",
            locked_at=TIMESTAMP_A,
        ),
        manifest_digest=selection_digest,
    )
    payload = _v2_benchmark_lock_payload()
    payload.update(
        {
            "selection_manifest_digest": selection.manifest_digest,
            "nomination_set_digest": nomination.nomination_set_digest,
            "selection_manifest": selection,
            "entries": selection.entries,
        }
    )
    payload["source_state_binding_digest"] = source_binding(
        source_repository_id=int(payload["source_repository_id"]),
        source_repository_full_name=str(payload["source_repository_full_name"]),
        state_repository_id=int(payload["state_repository_id"]),
        state_repository_full_name=str(payload["state_repository_full_name"]),
        parent_state_commit_sha=str(payload["parent_state_commit_sha"]),
        parent_state_root_digest=str(payload["parent_state_root_digest"]),
        source_commit_sha=str(payload["source_commit_sha"]),
        acceptance_workflow_sha256=str(payload["acceptance_workflow_sha256"]),
        selection_manifest_digest=selection.manifest_digest,
        nomination_set_digest=nomination.nomination_set_digest,
    )
    return nomination, lock_model.model_validate(payload, strict=True)


def _benchmark_rebind_payload() -> dict[str, object]:
    model = _symbol("BenchmarkSelectionRebindV1", skip_if_missing=False)
    nomination, lock = _benchmark_rebind_chain()
    return model(
        schema_version="benchmark-selection-rebind-v1",
        acceptance_run_id="phase6-current-main",
        source_acceptance_run_id="phase6-approved-selection",
        source_nomination=nomination,
        source_lock=lock,
        selection_manifest_digest=lock.selection_manifest_digest,
    ).model_dump(mode="json", exclude_none=False)


def test_benchmark_rebind_preserves_exact_old_selection_chain() -> None:
    model = _symbol("BenchmarkSelectionRebindV1", skip_if_missing=False)
    old_nomination, old_lock = _benchmark_rebind_chain()

    fact = model(
        schema_version="benchmark-selection-rebind-v1",
        acceptance_run_id="phase6-current-main",
        source_acceptance_run_id="phase6-approved-selection",
        source_nomination=old_nomination,
        source_lock=old_lock,
        selection_manifest_digest=old_lock.selection_manifest_digest,
    )

    assert fact.source_lock.entries == old_lock.entries
    assert fact.source_nomination.nomination_set_digest == old_lock.nomination_set_digest
    assert fact.rebind_digest is not None
    assert fact.rebind_digest.startswith("sha256:")


def test_benchmark_rebind_rejects_redigested_selected_entry_projection_drift() -> None:
    """A valid inner digest chain cannot rewrite the nomination's selected fields."""

    rebind_model = _symbol("BenchmarkSelectionRebindV1", skip_if_missing=False)
    entry_model = _symbol("BenchmarkEntryV1", skip_if_missing=False)
    attestation_model = _symbol("BenchmarkLockAttestationV1", skip_if_missing=False)
    selection_model = _symbol("LockedBenchmarkManifestV1", skip_if_missing=False)
    lock_model = _symbol("LockedBenchmarkManifestV2", skip_if_missing=False)
    source_binding = _symbol(
        "fresh_benchmark_source_state_binding_digest",
        skip_if_missing=False,
    )
    nomination, lock = _benchmark_rebind_chain()
    selected = lock.entries[0]
    drifted = entry_model(
        schema_version="benchmark-entry-v1",
        repository_full_name="octo-org/selected-only-drift",
        repository_id=9_999_991,
        exact_commit_sha="f" * 40,
        license_spdx="Apache-2.0",
        selection_source="search_derived",
        coverage_role=selected.coverage_role,
        nomination_entry_digest=selected.nomination_entry_digest,
        selection_evidence_digests=(
            "sha256:" + ("9" * 64),
        ),
    )
    drifted_entries = tuple(
        sorted(
            (drifted, *lock.entries[1:]),
            key=lambda entry: entry.entry_digest,
        )
    )
    selection_preimage = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": nomination.nomination_set_digest,
        "entries": [
            entry.model_dump(mode="json", exclude_none=False)
            for entry in drifted_entries
        ],
        "prior_manifest_digest": None,
    }
    selection_digest = sha256_digest(selection_preimage)
    drifted_selection = selection_model(
        **selection_preimage,
        lock_attestation=attestation_model(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=nomination.nomination_set_digest,
            manifest_digest=selection_digest,
            reviewer_id="projection-drift-reviewer",
            locked_at="2026-08-14T12:00:00.000000Z",
        ),
        manifest_digest=selection_digest,
    )
    lock_payload = lock.model_dump(mode="python", exclude_none=False)
    lock_payload.update(
        {
            "selection_manifest_digest": drifted_selection.manifest_digest,
            "selection_manifest": drifted_selection,
            "entries": drifted_selection.entries,
            "source_state_binding_digest": source_binding(
                source_repository_id=lock.source_repository_id,
                source_repository_full_name=lock.source_repository_full_name,
                state_repository_id=lock.state_repository_id,
                state_repository_full_name=lock.state_repository_full_name,
                parent_state_commit_sha=lock.parent_state_commit_sha,
                parent_state_root_digest=lock.parent_state_root_digest,
                source_commit_sha=lock.source_commit_sha,
                acceptance_workflow_sha256=lock.acceptance_workflow_sha256,
                selection_manifest_digest=drifted_selection.manifest_digest,
                nomination_set_digest=nomination.nomination_set_digest,
            ),
            "lock_digest": None,
        }
    )
    drifted_lock = lock_model.model_validate(lock_payload, strict=True)

    assert drifted_lock.selection_manifest.manifest_digest == selection_digest
    assert drifted_lock.entries[0].nomination_entry_digest in {
        entry.entry_digest for entry in nomination.search_derived_entries
    }
    with pytest.raises(ValidationError, match="selected-entry projection mismatch"):
        rebind_model(
            schema_version="benchmark-selection-rebind-v1",
            acceptance_run_id="phase6-current-main",
            source_acceptance_run_id="phase6-approved-selection",
            source_nomination=nomination,
            source_lock=drifted_lock,
            selection_manifest_digest=drifted_lock.selection_manifest_digest,
        )


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("search_derived_entries", 0, "repository_id"), 999999),
        (("search_derived_entries", 0, "exact_commit_sha"), SHA_A),
        (("search_derived_entries", 0, "license_spdx"), "Apache-2.0"),
        (("search_derived_entries", 0, "selection_evidence_digests", 0), DIGEST_A),
        (("query_set_digest",), DIGEST_A),
        (("selection_manifest_digest",), DIGEST_A),
        (("source_acceptance_run_id",), "phase6-current-main"),
    ),
)
def test_benchmark_rebind_rejects_selection_chain_mutations(
    path: tuple[object, ...], value: object
) -> None:
    model = _symbol("BenchmarkSelectionRebindV1", skip_if_missing=False)
    nomination_model = _symbol("NominationSetV1", skip_if_missing=False)
    nomination_entry_model = _symbol("NominationEntryV1", skip_if_missing=False)
    nomination, lock = _benchmark_rebind_chain()
    nomination_payload = nomination.model_dump(mode="json", exclude_none=False)
    target: object = nomination_payload
    for key in path[:-1]:
        if isinstance(target, dict):
            target = target[key]
        else:
            assert isinstance(target, list)
            assert isinstance(key, int)
            target = target[key]
    if isinstance(target, dict):
        target[path[-1]] = value
    else:
        assert isinstance(target, list)
        assert isinstance(path[-1], int)
        target[path[-1]] = value
    if path[0] != "selection_manifest_digest" and path[0] != "source_acceptance_run_id":
        if len(path) > 1:
            entry = nomination_payload["search_derived_entries"][0]
            assert isinstance(entry, dict)
            entry.pop("entry_digest")
        entries = nomination_payload["search_derived_entries"]
        assert isinstance(entries, list)
        for item in entries:
            assert isinstance(item, dict)
            evidence = item["selection_evidence_digests"]
            assert isinstance(evidence, list)
            item["selection_evidence_digests"] = tuple(evidence)
        nomination_payload["search_derived_entries"] = tuple(
            sorted(
                (
                    nomination_entry_model.model_validate(item, strict=True)
                    for item in entries
                ),
                key=lambda item: item.entry_digest,
            )
        )
        nomination_payload["user_nominated_entries"] = ()
        nomination_payload.pop("nomination_set_digest")
        nomination = nomination_model.model_validate(nomination_payload, strict=True)
    values: dict[str, object] = {
        "schema_version": "benchmark-selection-rebind-v1",
        "acceptance_run_id": "phase6-current-main",
        "source_acceptance_run_id": "phase6-approved-selection",
        "source_nomination": nomination,
        "source_lock": lock,
        "selection_manifest_digest": lock.selection_manifest_digest,
    }
    if path == ("selection_manifest_digest",):
        values["selection_manifest_digest"] = value
    if path == ("source_acceptance_run_id",):
        values["source_acceptance_run_id"] = value

    with pytest.raises(ValidationError):
        model(**values)


def test_locked_benchmark_manifest_v2_binds_redacted_environment_approval() -> None:
    receipt_model = _symbol("BenchmarkLockApprovalReceiptV2", skip_if_missing=False)
    manifest_model = _symbol("LockedBenchmarkManifestV2", skip_if_missing=False)
    assert {
        "purpose",
        "environment",
        "source_repository_id",
        "source_repository_full_name",
        "reviewer_login",
        "reviewer_id",
        "workflow_run_id",
        "workflow_run_attempt",
        "source_commit_sha",
        "workflow_sha256",
        "trigger_identity",
        "approval_record_digest",
        "receipt_digest",
    } == set(receipt_model.model_fields) - {"schema_version"}
    assert {
        "purpose",
        "source_repository_id",
        "source_repository_full_name",
        "state_repository_id",
        "state_repository_full_name",
        "parent_state_commit_sha",
        "parent_state_root_digest",
        "source_commit_sha",
        "acceptance_workflow_sha256",
        "source_state_binding_digest",
        "selection_manifest_digest",
        "nomination_set_digest",
        "selection_manifest",
        "entries",
        "environment",
        "approved_reviewer_login",
        "approved_reviewer_id",
        "workflow_run_id",
        "workflow_run_attempt",
        "trigger_identity",
        "approval_record_digest",
        "approval_receipt",
        "approval_receipt_digest",
        "lock_digest",
    } == set(manifest_model.model_fields) - {"schema_version"}
    assert {"actor", "comment", "approval_comment", "endpoint", "raw_response"}.isdisjoint(
        receipt_model.model_fields
    )

    manifest = manifest_model.model_validate(_v2_benchmark_lock_payload(), strict=True)
    assert manifest.purpose == "benchmark_lock"
    assert manifest.approval_receipt_digest == manifest.approval_receipt.receipt_digest
    assert manifest_model.model_validate_json(
        canonical_json_bytes(manifest), strict=True
    ) == manifest


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("environment",), "other-environment"),
        (("approved_reviewer_login",), "automation-bot"),
        (("approval_receipt", "purpose"), "live_execution"),
        (("approval_receipt", "environment"), "other-environment"),
        (("approval_receipt", "comment"), "approve this"),
    ),
)
def test_locked_benchmark_manifest_v2_rejects_forged_or_unredacted_approval(
    path: tuple[str, ...], value: object
) -> None:
    manifest_model = _symbol("LockedBenchmarkManifestV2", skip_if_missing=False)
    payload = manifest_model.model_validate(
        _v2_benchmark_lock_payload(), strict=True
    ).model_dump(mode="json", exclude_none=False)
    target: dict[str, object] = payload
    for key in path[:-1]:
        nested = target[key]
        assert isinstance(nested, dict)
        target = nested
    target[path[-1]] = value
    payload.pop("lock_digest")
    with pytest.raises(ValidationError):
        manifest_model.model_validate(payload, strict=True)


def test_locked_benchmark_manifest_v2_rejects_duplicate_or_noncanonical_entries() -> None:
    manifest_model = _symbol("LockedBenchmarkManifestV2", skip_if_missing=False)
    payload = manifest_model.model_validate(
        _v2_benchmark_lock_payload(), strict=True
    ).model_dump(mode="json", exclude_none=False)
    entries = payload["entries"]
    assert isinstance(entries, list)
    payload["entries"] = [entries[0], *entries[:-1]]
    payload.pop("lock_digest")
    with pytest.raises(ValidationError):
        manifest_model.model_validate(payload, strict=True)


def test_locked_benchmark_manifest_v2_carries_an_exact_v1_selection_preimage() -> None:
    """A valid role distribution cannot reinterpret the V1-reviewed selection."""

    entry_model = _symbol("BenchmarkEntryV1", skip_if_missing=False)
    manifest_model = _symbol("LockedBenchmarkManifestV2", skip_if_missing=False)
    source_binding = _symbol(
        "fresh_benchmark_source_state_binding_digest",
        skip_if_missing=False,
    )
    payload = manifest_model.model_validate(
        _v2_benchmark_lock_payload(), strict=True
    ).model_dump(mode="json", exclude_none=False)
    entries = payload["entries"]
    assert isinstance(entries, list)
    positive = next(item for item in entries if item["coverage_role"] == "positive")
    negative = next(item for item in entries if item["coverage_role"] == "negative")
    rewritten: list[dict[str, object]] = []
    for entry in entries:
        altered = dict(entry)
        if entry is positive:
            altered["coverage_role"] = "negative"
        elif entry is negative:
            altered["coverage_role"] = "positive"
        altered.pop("entry_digest")
        rewritten.append(
            entry_model.model_validate(altered, strict=True).model_dump(
                mode="json", exclude_none=False
            )
        )
    payload["entries"] = sorted(rewritten, key=lambda item: str(item["entry_digest"]))
    payload.pop("lock_digest")
    with pytest.raises(ValidationError, match="V1 selection preimage"):
        manifest_model.model_validate(payload, strict=True)

    payload = manifest_model.model_validate(
        _v2_benchmark_lock_payload(), strict=True
    ).model_dump(mode="json", exclude_none=False)
    selection = payload["selection_manifest"]
    assert isinstance(selection, dict)
    selection_digest = str(selection["manifest_digest"])
    payload["selection_manifest_digest"] = DIGEST_B
    payload["source_state_binding_digest"] = source_binding(
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        source_repository_id=1_310_897_029,
        source_repository_full_name="alexzhu0/skillscout",
        parent_state_commit_sha=SHA_B,
        parent_state_root_digest=DIGEST_C,
        source_commit_sha=SHA_A,
        acceptance_workflow_sha256=DIGEST_A,
        selection_manifest_digest=DIGEST_B,
        nomination_set_digest=str(selection["nomination_set_digest"]),
    )
    assert selection_digest != DIGEST_B
    payload.pop("lock_digest")
    with pytest.raises(ValidationError, match="V1 selection preimage"):
        manifest_model.model_validate(payload, strict=True)


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


def test_live_authority_contract_binds_human_approval_and_every_effect_identity() -> None:
    """A consuming workflow cannot certify caller-supplied identities."""

    contract = getattr(_acceptance_module(skip_if_missing=False), "LiveAcceptanceAuthorityV1", None)
    assert contract is not None
    values = {
        "schema_version": "live-acceptance-authority-v1",
        "authority_version": 1,
        "source_commit_sha": SHA_A,
        "acceptance_workflow_sha256": DIGEST_A,
        "manifest_path": (
            "config/acceptance/phase6/benchmark-manifest.json"
        ),
        "manifest_digest": DIGEST_B,
        "nomination_set_digest": DIGEST_C,
        "lock_attestation_digest": "sha256:" + ("d" * 64),
        "state_commit_sha": SHA_B,
        "state_root_digest": "sha256:" + ("e" * 64),
        "state_repository_id": 123,
        "state_repository_full_name": "example/state",
        "query_set_digest": "sha256:" + ("f" * 64),
        "budget_policy_digest": "sha256:" + ("1" * 64),
        "semantic_provider": "deepseek",
        "provider_base_url": "https://api.deepseek.com",
        "stage_models": (
            "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ),
        "prompt_versions": (
            "extract-prompt-v1",
            "generator-prompt-v1",
            "reviewer-prompt-v1",
        ),
        "schema_versions": (
            "workflow-spec-v1",
            "generation-draft-v1",
            "reviewer-judgment-v1",
        ),
        "policy_versions": (
            "discovery-budget-policy-v1",
            "extract-policy-v1",
            "generator-policy-v1",
            "qualification-policy-v1",
            "reader-policy-v1",
            "reviewer-policy-v1",
        ),
        "max_candidates": 100,
        "max_semantic_candidates": 20,
        "max_semantic_requests": 20,
        "max_files_per_repository": 25,
        "max_source_files_per_repository": 5,
        "max_file_bytes": 131_072,
        "max_total_bytes_per_repository": 524_288,
        "max_tokens_per_repository": 40_000,
        "benchmark_scenario_write_count": 5,
        "replay_semantic_effect_count": 0,
        "replay_publication_effect_count": 0,
        "reviewer_id": "alexzhu0",
        "approved_at": TIMESTAMP_A,
    }
    authority = contract(**values)

    assert authority.authority_digest is not None
    with pytest.raises(ValueError):
        contract(**{**values, "semantic_provider": "openai"})
    with pytest.raises(ValueError):
        contract(**{**values, "max_semantic_requests": 21})


def test_legacy_live_authority_locator_is_historical_read_only() -> None:
    """The old locator can be decoded as archival evidence, never as a new authority."""

    module = _acceptance_module(skip_if_missing=False)
    active = module.LiveAcceptanceAuthorityV1
    values = {
        "schema_version": "live-acceptance-authority-v1",
        "authority_version": 1,
        "source_commit_sha": SHA_A,
        "acceptance_workflow_sha256": DIGEST_A,
        "manifest_path": (
            ".planning/phases/06-adversarial-mvp-acceptance/"
            "06-BENCHMARK-MANIFEST.json"
        ),
        "manifest_digest": DIGEST_B,
        "nomination_set_digest": DIGEST_C,
        "lock_attestation_digest": "sha256:" + ("d" * 64),
        "state_commit_sha": SHA_B,
        "state_root_digest": "sha256:" + ("e" * 64),
        "state_repository_id": 123,
        "state_repository_full_name": "example/state",
        "query_set_digest": "sha256:" + ("f" * 64),
        "budget_policy_digest": "sha256:" + ("1" * 64),
        "semantic_provider": "deepseek",
        "provider_base_url": "https://api.deepseek.com",
        "stage_models": (
            "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ),
        "prompt_versions": (
            "extract-prompt-v1",
            "generator-prompt-v1",
            "reviewer-prompt-v1",
        ),
        "schema_versions": (
            "workflow-spec-v1",
            "generation-draft-v1",
            "reviewer-judgment-v1",
        ),
        "policy_versions": (
            "discovery-budget-policy-v1",
            "extract-policy-v1",
            "generator-policy-v1",
            "qualification-policy-v1",
            "reader-policy-v1",
            "reviewer-policy-v1",
        ),
        "max_candidates": 100,
        "max_semantic_candidates": 20,
        "max_semantic_requests": 20,
        "max_files_per_repository": 25,
        "max_source_files_per_repository": 5,
        "max_file_bytes": 131_072,
        "max_total_bytes_per_repository": 524_288,
        "max_tokens_per_repository": 40_000,
        "benchmark_scenario_write_count": 5,
        "replay_semantic_effect_count": 0,
        "replay_publication_effect_count": 0,
        "reviewer_id": "alexzhu0",
        "approved_at": TIMESTAMP_A,
    }

    with pytest.raises(ValidationError):
        active(**values)

    historical = getattr(module, "HistoricalLiveAcceptanceAuthorityV1", None)
    assert historical is not None
    archived = historical(**values)
    assert type(archived) is historical
    with pytest.raises(ValidationError):
        historical(**{**values, "manifest_path": "config/acceptance/phase6/benchmark-manifest.json"})


def _v2_live_authority_payload() -> dict[str, object]:
    """Return one complete fresh authority without using caller approval prose."""

    lock_model = _symbol("LockedBenchmarkManifestV2", skip_if_missing=False)
    receipt_model = _symbol("LiveExecutionApprovalReceiptV2", skip_if_missing=False)
    lock = lock_model.model_validate(_v2_benchmark_lock_payload(), strict=True)
    receipt = receipt_model(
        schema_version="live-execution-approval-receipt-v2",
        purpose="live_execution",
        environment="skillscout-phase6-live-authority",
        source_repository_id=lock.source_repository_id,
        source_repository_full_name=lock.source_repository_full_name,
        reviewer_login="alexzhu0",
        reviewer_id=202,
        workflow_run_id=2001,
        workflow_run_attempt=1,
        source_commit_sha=lock.source_commit_sha,
        workflow_sha256=lock.acceptance_workflow_sha256,
        trigger_identity=lock.trigger_identity,
        approval_record_digest="sha256:" + ("4" * 64),
    )
    return {
        "schema_version": "live-acceptance-authority-v2",
        "authority_version": 2,
        "purpose": "live_execution",
        "benchmark_lock_digest": lock.lock_digest,
        "benchmark_lock": lock,
        "source_repository_id": lock.source_repository_id,
        "source_repository_full_name": lock.source_repository_full_name,
        "state_repository_id": lock.state_repository_id,
        "state_repository_full_name": lock.state_repository_full_name,
        "parent_state_commit_sha": lock.parent_state_commit_sha,
        "parent_state_root_digest": lock.parent_state_root_digest,
        "state_commit_sha": "c" * 40,
        "state_root_digest": "sha256:" + ("5" * 64),
        "source_commit_sha": lock.source_commit_sha,
        "acceptance_workflow_sha256": lock.acceptance_workflow_sha256,
        "source_state_binding_digest": lock.source_state_binding_digest,
        "manifest_path": (
            "config/acceptance/phase6/benchmark-manifest.json"
        ),
        "manifest_digest": lock.selection_manifest_digest,
        "selection_manifest_digest": lock.selection_manifest_digest,
        "nomination_set_digest": lock.nomination_set_digest,
        "lock_attestation_digest": lock.selection_manifest.lock_attestation.attestation_digest,
        "entries": lock.entries,
        "environment": "skillscout-phase6-live-authority",
        "approved_reviewer_login": receipt.reviewer_login,
        "approved_reviewer_id": receipt.reviewer_id,
        "workflow_run_id": receipt.workflow_run_id,
        "workflow_run_attempt": receipt.workflow_run_attempt,
        "trigger_identity": receipt.trigger_identity,
        "approval_record_digest": receipt.approval_record_digest,
        "approval_receipt": receipt,
        "approval_receipt_digest": receipt.receipt_digest,
        "query_set_digest": "sha256:" + ("6" * 64),
        "budget_policy_digest": "sha256:" + ("7" * 64),
        "semantic_provider": "deepseek",
        "provider_base_url": "https://api.deepseek.com",
        "stage_models": (
            "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ),
        "prompt_versions": (
            "extract-prompt-v1",
            "generator-prompt-v1",
            "reviewer-prompt-v1",
        ),
        "schema_versions": (
            "workflow-spec-v1",
            "generation-draft-v1",
            "reviewer-judgment-v1",
        ),
        "policy_versions": (
            "discovery-budget-policy-v1",
            "extract-policy-v1",
            "generator-policy-v1",
            "qualification-policy-v1",
            "reader-policy-v1",
            "reviewer-policy-v1",
        ),
        "max_candidates": 100,
        "max_semantic_candidates": 20,
        "max_semantic_requests": 20,
        "max_files_per_repository": 25,
        "max_source_files_per_repository": 5,
        "max_file_bytes": 131_072,
        "max_total_bytes_per_repository": 524_288,
        "max_tokens_per_repository": 40_000,
        "benchmark_scenario_write_count": 5,
        "replay_semantic_effect_count": 0,
        "replay_publication_effect_count": 0,
        "approved_at": TIMESTAMP_B,
    }


def test_live_authority_v2_binds_complete_fresh_lock_chain_and_distinct_receipt() -> None:
    model = _symbol("LiveAcceptanceAuthorityV2", skip_if_missing=False)
    receipt_model = _symbol("LiveExecutionApprovalReceiptV2", skip_if_missing=False)
    authority = model.model_validate(_v2_live_authority_payload(), strict=True)

    assert authority.authority_digest is not None
    assert authority.benchmark_lock_digest == authority.benchmark_lock.lock_digest
    assert authority.entries == authority.benchmark_lock.entries
    assert authority.manifest_digest == authority.benchmark_lock.selection_manifest_digest
    assert authority.nomination_set_digest == authority.benchmark_lock.nomination_set_digest
    assert authority.approval_receipt_digest == authority.approval_receipt.receipt_digest

    assert authority.approval_receipt.purpose == "live_execution"
    assert authority.approval_receipt.environment == "skillscout-phase6-live-authority"
    assert {
        "actor",
        "comment",
        "authority_json",
        "token",
        "authorization",
    }.isdisjoint(receipt_model.model_fields)

    payload = authority.model_dump(mode="json", exclude_none=False)
    payload["approval_receipt"] = _v2_benchmark_lock_payload()["approval_receipt"]
    payload["approval_receipt_digest"] = _v2_benchmark_lock_payload()[
        "approval_receipt_digest"
    ]
    payload.pop("authority_digest")
    with pytest.raises(ValidationError):
        model.model_validate(payload, strict=True)

    payload = authority.model_dump(mode="json", exclude_none=False)
    entries = payload["entries"]
    assert isinstance(entries, list)
    payload["entries"] = list(reversed(entries))
    payload.pop("authority_digest")
    with pytest.raises(ValueError, match="selected-entry"):
        model.model_validate(payload, strict=True)

    payload = authority.model_dump(mode="json", exclude_none=False)
    payload["benchmark_lock_digest"] = DIGEST_A
    payload.pop("authority_digest")
    with pytest.raises(ValueError, match="benchmark lock"):
        model.model_validate(payload, strict=True)

    for forbidden_key in ("actor", "comment", "authority_json"):
        payload = authority.model_dump(mode="json", exclude_none=False)
        payload[forbidden_key] = "caller-asserted"
        payload.pop("authority_digest")
        with pytest.raises(ValidationError):
            model.model_validate(payload, strict=True)


def test_fresh_live_authority_rejects_the_retired_manifest_locator() -> None:
    model = _symbol("LiveAcceptanceAuthorityV2", skip_if_missing=False)
    payload = _v2_live_authority_payload()
    payload["manifest_path"] = (
        ".planning/phases/06-adversarial-mvp-acceptance/"
        "06-BENCHMARK-MANIFEST.json"
    )

    with pytest.raises(ValidationError):
        model.model_validate(payload, strict=True)


def test_semantic_telemetry_is_bound_to_live_authority_and_exact_stage_matrix() -> None:
    module = _acceptance_module(skip_if_missing=False)
    telemetry = module.AcceptanceSemanticTelemetryV1(
        schema_version="acceptance-semantic-telemetry-v1",
        live_acceptance_authority_digest=DIGEST_A,
        stage="extractor",
        workflow_spec_authority_digest=DIGEST_B,
        attempt_no=1,
        request_id="request-extractor-1",
        actual_model="deepseek-v4-flash",
        prompt_version="extract-prompt-v1",
        output_schema_version="workflow-spec-v1",
        policy_version="extract-policy-v1",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        latency_ms=20,
    )

    assert telemetry.live_acceptance_authority_digest == DIGEST_A
    assert "live_acceptance_authority_digest" in (
        module.AcceptanceScenarioResultV1.model_fields
    )
    with pytest.raises(ValueError):
        telemetry.model_copy(
            update={"prompt_version": "extract-prompt-drift-v2"},
        ).model_validate(
            {
                **telemetry.model_dump(mode="json"),
                "prompt_version": "extract-prompt-drift-v2",
            }
        )


def test_eligible_scenario_requires_all_three_durable_semantic_stages() -> None:
    module = _acceptance_module(skip_if_missing=False)
    telemetry_type = module.AcceptanceSemanticTelemetryV1
    scenario_type = module.AcceptanceScenarioResultV1

    def telemetry(stage: str, attempt: int) -> object:
        return telemetry_type(
            schema_version="acceptance-semantic-telemetry-v1",
            live_acceptance_authority_digest=DIGEST_C,
            stage=stage,
            workflow_spec_authority_digest=DIGEST_A,
            attempt_no=attempt,
            request_id=f"request-{stage}-{attempt}",
            actual_model=(
                "deepseek-v4-pro"
                if stage == "reviewer"
                else "deepseek-v4-flash"
            ),
            prompt_version={
                "extractor": "extract-prompt-v1",
                "generator": "generator-prompt-v1",
                "reviewer": "reviewer-prompt-v1",
            }[stage],
            output_schema_version={
                "extractor": "workflow-spec-v1",
                "generator": "generation-draft-v1",
                "reviewer": "reviewer-judgment-v1",
            }[stage],
            policy_version={
                "extractor": "extract-policy-v1",
                "generator": "generator-policy-v1",
                "reviewer": "reviewer-policy-v1",
            }[stage],
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=20,
        )

    complete = tuple(
        telemetry(stage, ordinal)
        for ordinal, stage in enumerate(
            ("extractor", "generator", "reviewer"),
            start=1,
        )
    )
    base = {
        "schema_version": "acceptance-scenario-result-v1",
        "acceptance_run_id": "acceptance-live-five",
        "scenario_id": "locked-1-101",
        "repository_id": 101,
        "repository_full_name": "example/repository",
        "exact_commit_sha": SHA_A,
        "license_spdx": "MIT",
        "benchmark_manifest_digest": DIGEST_B,
        "benchmark_entry_digest": DIGEST_A,
        "live_acceptance_authority_digest": DIGEST_C,
        "discovery_run_id": "acceptance-live-five-semantic",
        "discovery_run_authority_digest": DIGEST_A,
        "budget_reservation_digest": DIGEST_A,
        "fixed_candidate_admission_digest": DIGEST_B,
        "semantic_candidate_reservation_digest": DIGEST_C,
        "terminal_class": "eligible",
        "outcome": "eligible_local_candidate",
        "reason_code": "eligible_candidate_completed",
        "evidence_digests": (DIGEST_A,),
        "candidate_funnel": (
            "fixed_identity",
            "deterministic_filter",
            "bounded_read",
            "extractor",
            "qualification",
            "generator",
            "validation",
            "reviewer",
        ),
        "reader_order": "readme_docs_examples_manifests_source",
        "reader_file_count": 2,
        "reader_source_file_count": 0,
        "reader_total_bytes": 100,
        "reader_estimated_tokens": 25,
        "semantic_request_count": 3,
        "semantic_request_reservation_digests": (
            DIGEST_A,
            DIGEST_B,
            DIGEST_C,
        ),
        "semantic_attempt_digests": (DIGEST_A, DIGEST_B, DIGEST_C),
        "semantic_telemetry": complete,
        "actual_models": tuple(item.actual_model for item in complete),
        "prompt_versions": tuple(item.prompt_version for item in complete),
        "schema_versions": tuple(item.output_schema_version for item in complete),
        "policy_versions": tuple(item.policy_version for item in complete),
        "workflow_fingerprint": DIGEST_A,
        "workflow_spec_authority_digest": DIGEST_A,
        "workflow_execution_authority_digests": (DIGEST_A,),
        "workflow_spec_authority_digests": (DIGEST_A,),
        "candidate_terminal_digest": DIGEST_A,
        "workflow_terminal_digests": (DIGEST_A,),
        "phase3_terminal_summary_digests": (DIGEST_B,),
        "skill_artifact_digests": (DIGEST_C,),
        "package_digests": (DIGEST_A,),
        "eligible_locator": "state/objects/eligible.json",
        "eligible_object_digest": DIGEST_B,
        "expected_coverage_role": "positive",
        "evaluator_matches_observed": True,
        "publication_decision": "eligible_for_later_publication",
        "warnings": (),
        "recorded_at": TIMESTAMP_A,
    }
    assert scenario_type(**base).terminal_class == "eligible"
    for field, forged in (
        ("workflow_spec_authority_digests", (DIGEST_B,)),
        ("phase3_terminal_summary_digests", ()),
        ("skill_artifact_digests", ()),
        ("package_digests", ()),
        ("eligible_object_digest", None),
    ):
        with pytest.raises(ValueError):
            scenario_type(**{**base, field: forged})
    for missing_stage in ("generator", "reviewer"):
        reduced = tuple(item for item in complete if item.stage != missing_stage)
        with pytest.raises(ValueError):
            scenario_type(
                **{
                    **base,
                    "semantic_request_count": len(reduced),
                    "semantic_request_reservation_digests": tuple(
                        (DIGEST_A, DIGEST_B, DIGEST_C)[: len(reduced)]
                    ),
                    "semantic_attempt_digests": tuple(
                        (DIGEST_A, DIGEST_B, DIGEST_C)[: len(reduced)]
                    ),
                    "semantic_telemetry": reduced,
                    "actual_models": tuple(item.actual_model for item in reduced),
                    "prompt_versions": tuple(item.prompt_version for item in reduced),
                    "schema_versions": tuple(
                        item.output_schema_version for item in reduced
                    ),
                    "policy_versions": tuple(item.policy_version for item in reduced),
                }
            )
    with pytest.raises(ValueError):
        scenario_type(
            **{
                **base,
                "semantic_request_count": 0,
                "semantic_request_reservation_digests": (),
                "semantic_attempt_digests": (),
                "semantic_telemetry": (),
                "actual_models": (),
                "prompt_versions": (),
                "schema_versions": (),
                "policy_versions": (),
            }
        )
