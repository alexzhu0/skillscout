"""Pilot request-budget coverage for the local ``build-candidate`` command."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from skillscout import cli
from skillscout.adapters.semantic_provider import (
    SemanticProviderFailure,
    SemanticTransportDisposition,
)
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.phase3 import PhaseThreeRuntimeProfile
from skillscout.domain.models import CandidateRunIdentityV1

from test_cli_validate_skill import _argv
from test_phase3_pipeline import (
    _CascadeGenerator,
    _CascadeReviewer,
    _CascadeValidator,
    _CompositionSource,
    _workflow,
    _write_composition_descriptor_for_workflow,
)


def _candidate_paths(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    descriptor_root = tmp_path / "descriptor"
    descriptor_root.mkdir(mode=0o700)
    descriptor = _write_composition_descriptor_for_workflow(
        descriptor_root,
        workflow=_workflow(),
    )
    return (
        descriptor,
        tmp_path / "phase2.db",
        tmp_path / "phase3.db",
        tmp_path / "output",
    )


def _build_argv(
    descriptor: Path,
    phase2_state: Path,
    state: Path,
    output: Path,
    *,
    single_attempt: bool,
) -> list[str]:
    values = _argv(
        descriptor=descriptor,
        phase2_state=phase2_state,
        state=state,
        output=output,
    )
    if single_attempt:
        values.append("--single-attempt")
    return values


def _persisted_identity(state: Path) -> CandidateRunIdentityV1:
    with sqlite3.connect(state) as connection:
        row = connection.execute("SELECT run_id FROM phase3_runs").fetchone()
    assert row is not None
    store = SQLiteStateStore(state)
    try:
        return store.verify_candidate_run_chain(str(row[0])).identity
    finally:
        store.close()


def _patch_build_boundary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    calls: list[str],
    generator_type: type[_CascadeGenerator] = _CascadeGenerator,
    reviewer_type: type[_CascadeReviewer] = _CascadeReviewer,
) -> _CompositionSource:
    source = _CompositionSource(workflow=_workflow())
    monkeypatch.setattr(
        cli,
        "SQLitePhaseTwoCandidateSource",
        lambda _path, *, allow_local_readme: source,
    )
    monkeypatch.setattr(
        cli,
        "OpenAIGenerationClient",
        lambda **kwargs: generator_type(
            "parsed",
            calls,
            model=kwargs["model"],
            max_output_tokens=kwargs["max_output_tokens"],
        ),
    )
    monkeypatch.setattr(
        cli,
        "CandidateValidationAdapter",
        lambda: _CascadeValidator(False, calls),
    )
    monkeypatch.setattr(
        cli,
        "OpenAIReviewClient",
        lambda **kwargs: reviewer_type(
            "eligible_local_candidate",
            calls,
            model=kwargs["model"],
            max_output_tokens=kwargs["max_output_tokens"],
        ),
    )
    return source


class _ConfirmedTransientGenerator(_CascadeGenerator):
    def generate(self, *, request):
        del request
        self.calls.append("generator")
        raise SemanticProviderFailure(
            disposition=SemanticTransportDisposition.CONFIRMED_RETRYABLE,
            code="semantic_rate_limited",
        )


class _ConfirmedTransientReviewer(_CascadeReviewer):
    def review(self, **kwargs):
        del kwargs
        self.calls.append("reviewer")
        raise SemanticProviderFailure(
            disposition=SemanticTransportDisposition.CONFIRMED_RETRYABLE,
            code="semantic_rate_limited",
        )


class _UnknownGenerator(_CascadeGenerator):
    def generate(self, *, request):
        del request
        self.calls.append("generator")
        raise SemanticProviderFailure(
            disposition=SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN,
            code="semantic_provider_outcome_unknown",
        )


class _UnknownReviewer(_CascadeReviewer):
    def review(self, **kwargs):
        del kwargs
        self.calls.append("reviewer")
        raise SemanticProviderFailure(
            disposition=SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN,
            code="semantic_provider_outcome_unknown",
        )


def test_build_candidate_default_authority_retains_three_attempt_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    descriptor, phase2_state, state, output = _candidate_paths(tmp_path)
    calls: list[str] = []
    _patch_build_boundary(monkeypatch, calls=calls)

    assert (
        cli.main(
            _build_argv(
                descriptor,
                phase2_state,
                state,
                output,
                single_attempt=False,
            )
        )
        == 0
    )
    assert capsys.readouterr().err == ""

    authority = _persisted_identity(state).candidate_execution_authority
    assert authority.max_generator_attempts == 3
    assert authority.max_reviewer_attempts == 3
    assert calls == ["generator", "validator", "reviewer"]


def test_single_attempt_binds_limits_before_authority_and_keeps_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    descriptor, phase2_state, state, output = _candidate_paths(tmp_path)
    calls: list[str] = []
    source = _patch_build_boundary(monkeypatch, calls=calls)

    assert (
        cli.main(
            _build_argv(
                descriptor,
                phase2_state,
                state,
                output,
                single_attempt=True,
            )
        )
        == 0
    )
    assert capsys.readouterr().err == ""

    authority = _persisted_identity(state).candidate_execution_authority
    default_profile = PhaseThreeRuntimeProfile.from_configured_models(
        generator_model_id=authority.configured_generator_model_id,
        reviewer_model_id=authority.configured_reviewer_model_id,
    )
    assert authority.max_generator_attempts == 1
    assert authority.max_reviewer_attempts == 1
    assert authority.runtime_profile_digest != default_profile.profile_digest
    assert source.calls == ["source"]
    assert calls == ["generator", "validator", "reviewer"]


def test_single_attempt_confirmed_transient_generator_makes_one_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    descriptor, phase2_state, state, output = _candidate_paths(tmp_path)
    calls: list[str] = []
    _patch_build_boundary(
        monkeypatch,
        calls=calls,
        generator_type=_ConfirmedTransientGenerator,
    )

    assert (
        cli.main(
            _build_argv(
                descriptor,
                phase2_state,
                state,
                output,
                single_attempt=True,
            )
        )
        == 1
    )
    assert capsys.readouterr().out == ""
    assert calls == ["generator"]


def test_single_attempt_confirmed_transient_reviewer_makes_one_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    descriptor, phase2_state, state, output = _candidate_paths(tmp_path)
    calls: list[str] = []
    _patch_build_boundary(
        monkeypatch,
        calls=calls,
        reviewer_type=_ConfirmedTransientReviewer,
    )

    assert (
        cli.main(
            _build_argv(
                descriptor,
                phase2_state,
                state,
                output,
                single_attempt=True,
            )
        )
        == 1
    )
    assert capsys.readouterr().out == ""
    assert calls == ["generator", "validator", "reviewer"]


@pytest.mark.parametrize(
    ("generator_type", "reviewer_type", "expected_calls"),
    (
        pytest.param(
            _UnknownGenerator,
            _CascadeReviewer,
            ["generator"],
            id="generator",
        ),
        pytest.param(
            _CascadeGenerator,
            _UnknownReviewer,
            ["generator", "validator", "reviewer"],
            id="reviewer",
        ),
    ),
)
def test_single_attempt_unknown_response_is_terminal_across_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    generator_type: type[_CascadeGenerator],
    reviewer_type: type[_CascadeReviewer],
    expected_calls: list[str],
) -> None:
    descriptor, phase2_state, state, output = _candidate_paths(tmp_path)
    calls: list[str] = []
    _patch_build_boundary(
        monkeypatch,
        calls=calls,
        generator_type=generator_type,
        reviewer_type=reviewer_type,
    )
    argv = _build_argv(
        descriptor,
        phase2_state,
        state,
        output,
        single_attempt=True,
    )

    assert cli.main(argv) == 1
    capsys.readouterr()
    assert calls == expected_calls

    assert cli.main(argv) == 1
    capsys.readouterr()
    assert calls == expected_calls
