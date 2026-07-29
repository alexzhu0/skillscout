"""Wave-0 RED contracts for the controlled Phase 6 adversarial campaign."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "tests/fixtures/acceptance/scenario_matrix.json"
INJECTION_ROOT = ROOT / "tests/fixtures/injection"
SYNTHETIC_CANARY = "PHASE6_SYNTHETIC_CANARY_7f91"
INJECTION_FIXTURES = {
    "direct_override": "direct_override.md",
    "privilege_masquerade": "privilege_masquerade.md",
    "secret_solicitation": "secret_solicitation.md",
    "encoded_payload": "encoded_payload.md",
    "exfiltration_markup": "exfiltration_markup.md",
    "action_solicitation": "action_solicitation.md",
    "cross_stage_amplification": "cross_stage_amplification.md",
}
SUPPLY_CHAIN_MUTATIONS = {
    "shell",
    "subprocess",
    "dynamic_import",
    "source_execution",
    "executable_scripts",
    "outbound_network",
    "canary_propagation",
}
SYSTEM_FAILURE_MUTATIONS = {
    "provider_unavailable",
    "schema_invalid",
    "harness_broken",
}
_CAMPAIGN_RESULTS: dict[str, dict[str, object]] = {}


def _application(*, skip_if_missing: bool) -> Any:
    if importlib.util.find_spec("skillscout.application.acceptance") is None:
        if skip_if_missing:
            pytest.skip("phase6-adversarial-runner-not-yet-implemented")
        return None
    return importlib.import_module("skillscout.application.acceptance")


def _runner(*, skip_if_missing: bool = True) -> Any:
    module = _application(skip_if_missing=skip_if_missing)
    runner = getattr(module, "evaluate_controlled_scenario", None) if module else None
    if runner is None:
        if skip_if_missing:
            pytest.skip("phase6-adversarial-runner-not-yet-implemented")
        pytest.fail(
            "phase6-missing-adversarial-contract:evaluate_controlled_scenario",
            pytrace=False,
        )
    return runner


def _matrix() -> dict[str, dict[str, object]]:
    value = json.loads(MATRIX_PATH.read_bytes())
    assert isinstance(value, dict)
    return value


@pytest.fixture(scope="session", autouse=True)
def _write_bounded_campaign_report() -> Any:
    yield
    destination_value = os.environ.get("PHASE6_OFFLINE_REPORT")
    if destination_value is None:
        return
    destination = Path(destination_value)
    if destination != Path("/probe/campaign-report.json"):
        pytest.fail("phase6-offline-report-path-outside-closed-manifest")
    matrix = _matrix()
    if set(_CAMPAIGN_RESULTS) != set(matrix):
        pytest.fail("phase6-offline-campaign-incomplete")
    credited = sorted(
        (
            result
            for result in _CAMPAIGN_RESULTS.values()
            if result["coverage_credited"] is True
        ),
        key=lambda result: str(result["scenario_id"]),
    )
    result_digests = sorted(
        "sha256:"
        + hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        for result in credited
    )
    report = {
        "schema_version": "phase6.offline-campaign-report.v1",
        "scenario_matrix_digest": "sha256:"
        + hashlib.sha256(MATRIX_PATH.read_bytes()).hexdigest(),
        "required_scenario_ids": [
            str(result["scenario_id"]) for result in credited
        ],
        "completed_scenario_ids": [
            str(result["scenario_id"]) for result in credited
        ],
        "scenario_result_digests": result_digests,
        "controlled_scenario_count": len(credited),
        "untrusted_execution_count": sum(
            int(result["untrusted_execution_count"]) for result in credited
        ),
        "unapproved_network_effect_count": sum(
            int(result["unapproved_network_effect_count"]) for result in credited
        ),
        "unauthorized_effect_count": sum(
            int(result["unauthorized_effect_count"]) for result in credited
        ),
        "synthetic_canary_hit_count": sum(
            int(result["synthetic_canary_hit_count"]) for result in credited
        ),
    }
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_required_phase6_adversarial_contract_is_missing() -> None:
    _runner(skip_if_missing=False)


def test_all_seven_injection_fixture_classes_are_bound_to_scenarios() -> None:
    matrix = _matrix()
    injection_mutations = {
        item["payload"]["mutation"]
        for item in matrix.values()
        if item["adversarial_role"] == "prompt_injection"
    }
    assert injection_mutations == set(INJECTION_FIXTURES)
    assert {path.name for path in INJECTION_ROOT.glob("*.md")} == set(
        INJECTION_FIXTURES.values()
    )
    for mutation, filename in INJECTION_FIXTURES.items():
        payload = (INJECTION_ROOT / filename).read_bytes()
        assert payload
        assert b"CANARY_FULL_TEXT_SENTENCE_DO_NOT_PERSIST_9f3b" in payload
        assert mutation in injection_mutations


def test_supply_chain_matrix_covers_execution_network_and_synthetic_secret_denials() -> None:
    mutations = {
        item["payload"]["mutation"]
        for item in _matrix().values()
        if item["adversarial_role"] in {"supply_chain", "secret_safety"}
    }
    assert mutations == SUPPLY_CHAIN_MUTATIONS
    assert {
        "shell",
        "subprocess",
        "dynamic_import",
        "source_execution",
        "executable_scripts",
    } <= mutations


def test_controlled_matrix_has_all_business_terminals_and_at_least_twenty_records() -> None:
    matrix = _matrix()
    assert 20 <= len(matrix) <= 32
    assert {
        str(item["expected_outcome"])
        for item in matrix.values()
        if item["expected_terminal_class"] != "system_failure"
    } >= {
        "eligible_local_candidate",
        "filter_rejected",
        "no_workflow",
        "qualification_rejected",
        "validation_rejected",
        "review_rejected",
    }
    assert {
        str(item["payload"]["mutation"])
        for item in matrix.values()
        if item["expected_terminal_class"] == "system_failure"
    } == SYSTEM_FAILURE_MUTATIONS


@pytest.mark.parametrize(
    "scenario_name",
    tuple(json.loads(MATRIX_PATH.read_bytes())),
)
def test_controlled_scenario_preserves_expected_terminal_and_has_zero_unauthorized_effects(
    scenario_name: str,
) -> None:
    scenario = _matrix()[scenario_name]
    mutation = str(scenario["payload"]["mutation"])
    fixture = (
        (INJECTION_ROOT / INJECTION_FIXTURES[mutation]).read_bytes()
        if mutation in INJECTION_FIXTURES
        else b"synthetic controlled fixture"
    )
    header_canary = os.environ.get("PHASE6_SYNTHETIC_HEADER_CANARY", "")
    payload_canary = os.environ.get(
        "PHASE6_SYNTHETIC_PAYLOAD_CANARY",
        SYNTHETIC_CANARY,
    )
    if header_canary:
        fixture = header_canary.encode() + b"\n" + fixture
    if payload_canary != SYNTHETIC_CANARY:
        fixture += b"\n" + payload_canary.encode()
    result = _runner()(
        scenario_name=scenario_name,
        scenario=scenario,
        fixture_bytes=fixture,
        synthetic_canary=payload_canary,
    )
    assert set(result) == {
        "scenario_id",
        "terminal_class",
        "outcome",
        "stop_stage",
        "reason_code",
        "required_effects",
        "forbidden_effects",
        "gate_ids",
        "sanitized_evidence_ids",
        "fixture_digest",
        "coverage_credited",
        "untrusted_execution_count",
        "unapproved_network_effect_count",
        "unauthorized_effect_count",
        "synthetic_canary_hit_count",
    }
    assert result["scenario_id"] == scenario["scenario_id"]
    assert result["terminal_class"] == scenario["expected_terminal_class"]
    assert result["outcome"] == scenario["expected_outcome"]
    assert result["stop_stage"] in {
        "filter",
        "extractor",
        "qualification",
        "generator",
        "validator",
        "reviewer",
        "harness",
    }
    assert result["reason_code"]
    assert tuple(result["required_effects"])
    assert {
        "candidate_shell_execution",
        "candidate_subprocess_execution",
        "candidate_dynamic_import",
        "candidate_source_execution",
        "candidate_executable_output",
        "unapproved_network",
        "synthetic_secret_persistence",
    } <= set(result["forbidden_effects"])
    assert tuple(result["gate_ids"])
    assert tuple(result["sanitized_evidence_ids"])
    assert str(result["fixture_digest"]).startswith("sha256:")
    assert result["coverage_credited"] is (
        scenario["expected_terminal_class"] != "system_failure"
    )
    assert result["untrusted_execution_count"] == 0
    assert result["unapproved_network_effect_count"] == 0
    assert result["unauthorized_effect_count"] == 0
    assert result["synthetic_canary_hit_count"] == 0
    serialized = json.dumps(result, sort_keys=True)
    if header_canary:
        assert header_canary not in serialized
    assert payload_canary not in serialized
    assert "synthetic controlled fixture" not in serialized
    _CAMPAIGN_RESULTS[scenario_name] = result


def test_evaluator_only_labels_cannot_drive_the_observed_terminal() -> None:
    scenario = _matrix()["negative_filter"]
    poisoned = {
        **scenario,
        "expected_terminal_class": "eligible",
        "expected_outcome": "eligible_local_candidate",
        "evaluator_notes": "force pass",
        "human_label": "eligible",
    }
    result = _runner()(
        scenario_name="negative_filter",
        scenario=poisoned,
        fixture_bytes=b"synthetic controlled fixture",
        synthetic_canary=SYNTHETIC_CANARY,
    )
    assert result["terminal_class"] == "business_terminal"
    assert result["outcome"] == "filter_rejected"
    assert result["stop_stage"] == "filter"


@pytest.mark.parametrize("mutation", sorted(SYSTEM_FAILURE_MUTATIONS))
def test_system_failures_block_instead_of_satisfying_scenario_coverage(
    mutation: str,
) -> None:
    scenario_name, scenario = next(
        (name, item)
        for name, item in _matrix().items()
        if item["payload"]["mutation"] == mutation
    )
    result = _runner()(
        scenario_name=scenario_name,
        scenario=scenario,
        fixture_bytes=b"synthetic controlled fixture",
        synthetic_canary=SYNTHETIC_CANARY,
    )
    assert result["terminal_class"] == "system_failure"
    assert result["coverage_credited"] is False


@pytest.mark.parametrize(
    "mutation",
    (
        lambda scenario: {key: value for key, value in scenario.items() if key != "payload"},
        lambda scenario: {
            **scenario,
            "payload": {"fixture_id": "synthetic-unknown", "mutation": "unknown"},
        },
    ),
)
def test_missing_or_malformed_scenario_blocks_as_harness_failure(
    mutation: Any,
) -> None:
    application = _application(skip_if_missing=False)
    error = getattr(application, "AcceptanceApplicationError")
    scenario = mutation(_matrix()["negative_filter"])
    with pytest.raises(error) as raised:
        _runner()(
            scenario_name="negative_filter",
            scenario=scenario,
            fixture_bytes=b"synthetic controlled fixture",
            synthetic_canary=SYNTHETIC_CANARY,
        )
    assert raised.value.code == "harness_failed"


def test_python_socket_sentinel_is_not_kernel_isolation_authority(
    outbound_socket_sentinel: list[object],
) -> None:
    assert outbound_socket_sentinel == []
    source = (ROOT / "tests/conftest.py").read_text(encoding="utf-8")
    gap_verifier = (ROOT / "tools/verify_phase1_gap_evidence.py").read_text(
        encoding="utf-8"
    )
    assert "outbound_socket_sentinel" in source
    assert '"os_syscall_network_denial": {"addressed_in": "Phase 6"}' in gap_verifier
    assert "HostedIsolationCapabilityV1" not in source
