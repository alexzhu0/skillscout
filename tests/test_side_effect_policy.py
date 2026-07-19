"""Composition-time authority checks for the Phase 1 dry-run runtime."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import (
    DryRunRuntime,
    SideEffectPolicy,
    build_dry_run_runtime,
)
from skillscout.application.ports import AdapterRegistration, ErrorCode, SafeFailure
from skillscout.domain.enums import EffectScope

APPROVED_FIXTURE = Path(__file__).parent / "fixtures" / "pipeline" / "approved.json"


class InvocationCanary:
    def __init__(self, effect_scope: object | None = None) -> None:
        self.calls = 0
        if effect_scope is not None:
            self.effect_scope = effect_scope

    def invoke(self) -> None:
        self.calls += 1


@pytest.mark.parametrize(
    "scope", (EffectScope.REMOTE_READ, EffectScope.REMOTE_WRITE)
)
def test_remote_scope_is_rejected_before_adapter_invocation(
    tmp_path: Path, scope: EffectScope
) -> None:
    del tmp_path
    canary = InvocationCanary(scope)
    registration = AdapterRegistration("canary", canary)

    with pytest.raises(SafeFailure) as failure:
        SideEffectPolicy.phase_one().validate((registration,))

    assert failure.value.code is ErrorCode.FORBIDDEN_EFFECT_SCOPE
    assert canary.calls == 0


@pytest.mark.parametrize("declared_scope", (None, "none", object()))
def test_missing_or_malformed_scope_is_rejected_before_adapter_invocation(
    declared_scope: object | None,
) -> None:
    canary = InvocationCanary(declared_scope)

    with pytest.raises(ValueError, match="invalid adapter registration"):
        AdapterRegistration("canary", canary)

    assert canary.calls == 0


def test_registration_cannot_accept_a_caller_selected_scope() -> None:
    with pytest.raises(TypeError):
        AdapterRegistration(
            "processor",
            EffectScope.REMOTE_WRITE,
            FixtureProcessor(),
        )


def test_supported_adapters_declare_exact_local_authority(tmp_path: Path) -> None:
    state = SQLiteStateStore(tmp_path / "state.db")
    try:
        assert FixtureProcessor().effect_scope is EffectScope.NONE
        assert state.effect_scope is EffectScope.LOCAL_STATE
    finally:
        state.close()


def test_closed_scope_vocabulary_and_phase_one_policy() -> None:
    assert tuple(scope.value for scope in EffectScope) == (
        "none",
        "local_state",
        "remote_read",
        "remote_write",
    )
    assert SideEffectPolicy.phase_one().allowed_scopes == frozenset(
        {EffectScope.NONE, EffectScope.LOCAL_STATE}
    )


def test_local_registry_constructs_and_completes(tmp_path: Path) -> None:
    state = SQLiteStateStore(tmp_path / "state.db")
    runtime = build_dry_run_runtime(state, FixtureProcessor())
    try:
        assert isinstance(runtime, DryRunRuntime)
        assert runtime.registrations
        assert {registration.scope for registration in runtime.registrations} == {
            EffectScope.NONE,
            EffectScope.LOCAL_STATE,
        }
        assert all(
            registration.scope in runtime.policy.allowed_scopes
            for registration in runtime.registrations
        )
        summary = runtime.runner.run(load_fixture(APPROVED_FIXTURE), tmp_path / "out")
        assert summary.status.value == "planned_not_published"
        assert summary.remote_writes_attempted == 0
    finally:
        state.close()


def test_registration_is_immutable() -> None:
    registration = AdapterRegistration("processor", FixtureProcessor())
    with pytest.raises((AttributeError, TypeError)):
        registration.scope = EffectScope.REMOTE_WRITE
