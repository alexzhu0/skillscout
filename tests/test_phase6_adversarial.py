"""Wave-0 RED contracts for the controlled Phase 6 adversarial campaign."""

from __future__ import annotations

import importlib
import importlib.util
import json
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
    "outbound_network",
    "canary_propagation",
}


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
    } <= mutations


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
    result = _runner()(
        scenario_name=scenario_name,
        scenario=scenario,
        fixture_bytes=fixture,
        synthetic_canary=SYNTHETIC_CANARY,
    )
    assert set(result) == {
        "scenario_id",
        "terminal_class",
        "outcome",
        "untrusted_execution_count",
        "unapproved_network_effect_count",
        "unauthorized_effect_count",
        "synthetic_canary_hit_count",
    }
    assert result["scenario_id"] == scenario["scenario_id"]
    assert result["terminal_class"] == scenario["expected_terminal_class"]
    assert result["outcome"] == scenario["expected_outcome"]
    assert result["untrusted_execution_count"] == 0
    assert result["unapproved_network_effect_count"] == 0
    assert result["unauthorized_effect_count"] == 0
    assert result["synthetic_canary_hit_count"] == 0


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

