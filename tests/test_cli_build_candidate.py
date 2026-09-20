"""Pilot request-budget coverage for the local ``build-candidate`` command."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import httpx
import pytest

from skillscout import cli
from skillscout.adapters.semantic_provider import (
    SemanticProviderFailure,
    SemanticTransportDisposition,
)
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.phase3 import PhaseThreeRuntimeProfile
from skillscout.domain.models import CandidateRunIdentityV1
from skillscout.domain.skill_artifacts import (
    LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION,
    LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION,
)

from test_cli_validate_skill import _argv
from test_phase3_pipeline import (
    _CascadeGenerator,
    _CascadeReviewer,
    _CascadeValidator,
    _CompositionSource,
    _workflow,
    _write_composition_descriptor_for_workflow,
)


def test_local_generation_diagnostic_sidecar_is_not_authority_or_replayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
) -> None:
    from recorded_transport import RecordedTransport
    from test_generation_diagnostics import PRIVATE, _response
    from test_openai_generate import CANARY_KEY, CHAT_COMPLETIONS

    descriptor, phase2_state, state, output = _candidate_paths(tmp_path)
    source = _CompositionSource(workflow=_workflow())
    monkeypatch.setattr(cli, "SQLitePhaseTwoCandidateSource", lambda *a, **k: source)
    monkeypatch.setenv("DEEPSEEK_API_KEY", CANARY_KEY)
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    recorded = RecordedTransport({CHAT_COMPLETIONS: _response("nested")})
    real_generator = cli.OpenAIGenerationClient
    monkeypatch.setattr(
        cli, "OpenAIGenerationClient",
        lambda **kwargs: real_generator(http_client=httpx.Client(transport=recorded.transport()), **kwargs),
    )
    monkeypatch.setattr(cli, "OpenAIReviewClient", lambda **k: pytest.fail("review reached"))
    arguments = _build_argv(descriptor, phase2_state, state, output,
                            single_attempt=True, source_faithful_generation=True)
    assert cli.main(arguments) == 0
    public = json.loads(capsys.readouterr().out)
    assert public["outcome"] == "generator_schema_failure"
    terminal_bytes = (output / "candidate-terminal-summary.json").read_bytes()
    terminal = json.loads(terminal_bytes)
    sidecar = output / "generation-diagnostic.json"
    diagnostic = json.loads(sidecar.read_bytes())
    assert diagnostic == {
        "schema_version": "local-generation-diagnostic-v1",
        "reason": "schema_invalid",
        "findings": [{"field": "references", "code": "extra_forbidden"}],
        "truncated": False,
        "terminal_summary_digest": terminal["terminal_summary_digest"],
    }
    assert PRIVATE not in sidecar.read_text() and CANARY_KEY not in sidecar.read_text()
    assert all(item["kind"] != "generation_diagnostic" for item in public["evidence"])
    with sqlite3.connect(state) as db:
        assert db.execute("select stage from phase3_attempts order by stage_index").fetchall() == [
            ("qualifier",), ("generator",),
        ]
        assert db.execute("select count(*) from phase3_artifacts where artifact_kind='generation_diagnostic'").fetchone() == (0,)
    assert len(recorded.requests) == 1

    # An old/missing sidecar is never reconstructed by replaying the model.
    sidecar.unlink()
    monkeypatch.setattr(cli, "OpenAIGenerationClient", lambda **k: pytest.fail("replayed model"))
    assert cli.main(arguments) == 0
    assert json.loads(capsys.readouterr().out) == public
    assert not sidecar.exists()
    assert (output / "candidate-terminal-summary.json").read_bytes() == terminal_bytes


@pytest.mark.parametrize("symlink", [False, True])
def test_generation_diagnostic_refuses_existing_conflict_or_symlink(tmp_path: Path, symlink):
    from types import SimpleNamespace
    from skillscout.application.ports import SafeFailure

    outside = tmp_path / "outside.json"
    outside.write_bytes(b"original")
    output = tmp_path / "output"
    output.mkdir()
    sidecar = output / "generation-diagnostic.json"
    if symlink:
        sidecar.symlink_to(outside)
    else:
        sidecar.write_bytes(b"original")
        sidecar.chmod(0o600)
    with pytest.raises(SafeFailure):
        cli._write_generation_diagnostic(
            output, SimpleNamespace(terminal_summary_digest="sha256:" + "a" * 64),
            {"schema_version": "local-generation-diagnostic-v1", "reason": "empty_content",
             "findings": [], "truncated": False},
        )
    assert outside.read_bytes() == b"original"
    assert sidecar.read_bytes() == b"original"

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
    source_faithful_generation: bool = False,
) -> list[str]:
    values = _argv(
        descriptor=descriptor,
        phase2_state=phase2_state,
        state=state,
        output=output,
    )
    if single_attempt:
        values.append("--single-attempt")
    if source_faithful_generation:
        values.append("--source-faithful-generation")
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
        lambda **kwargs: _generator_with_prompt(
            generator_type(
                "parsed",
                calls,
                model=kwargs["model"],
                max_output_tokens=kwargs["max_output_tokens"],
            ),
            kwargs.get("prompt_version"),
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


def _generator_with_prompt(generator: _CascadeGenerator, prompt_version: str | None):
    if prompt_version is not None:
        generator.prompt_version = prompt_version
    return generator


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


def test_source_faithful_generation_requires_single_attempt_before_provider_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    descriptor, phase2_state, state, output = _candidate_paths(tmp_path)
    provider_calls = 0

    def forbidden_provider():
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("invalid CLI combination constructed a provider")

    monkeypatch.setattr(cli, "resolve_semantic_provider", forbidden_provider)

    assert (
        cli.main(
            _build_argv(
                descriptor,
                phase2_state,
                state,
                output,
                single_attempt=False,
                source_faithful_generation=True,
            )
        )
        == 1
    )
    assert capsys.readouterr().out == ""
    assert provider_calls == 0
    assert not state.exists()


def test_source_faithful_generation_binds_closed_profile_prompt_and_one_attempt(
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
                single_attempt=True,
                source_faithful_generation=True,
            )
        )
        == 0
    )
    assert capsys.readouterr().err == ""

    authority = _persisted_identity(state).candidate_execution_authority
    assert authority.phase3_profile_version == LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION
    assert authority.generator_prompt_version == LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION
    assert authority.max_generator_attempts == 1
    assert authority.max_reviewer_attempts == 1
    assert calls == ["generator", "validator", "reviewer"]


@pytest.mark.parametrize(
    ("generator_type", "expected_calls"),
    (
        (_ConfirmedTransientGenerator, ["generator"]),
        (_UnknownGenerator, ["generator"]),
    ),
    ids=("confirmed-transient", "unknown"),
)
def test_source_faithful_generation_never_expands_one_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    generator_type: type[_CascadeGenerator],
    expected_calls: list[str],
) -> None:
    descriptor, phase2_state, state, output = _candidate_paths(tmp_path)
    calls: list[str] = []
    _patch_build_boundary(
        monkeypatch,
        calls=calls,
        generator_type=generator_type,
    )
    argv = _build_argv(
        descriptor,
        phase2_state,
        state,
        output,
        single_attempt=True,
        source_faithful_generation=True,
    )

    assert cli.main(argv) == 1
    capsys.readouterr()
    assert calls == expected_calls

    assert cli.main(argv) == 1
    capsys.readouterr()
    assert calls == expected_calls
