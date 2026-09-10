"""Local Flash opt-in does not change hosted defaults or model identity checks."""

import json

import httpx
import pytest

from recorded_transport import RecordedTransport, recorded_openai_fixture
from test_cli_extract_repo import _argv, _attempts, _github_routes
from test_cli_validate_skill import (
    _argv as build_argv,
    _patch_phase3_ports,
)
from test_phase3_pipeline import _workflow, _write_composition_descriptor_for_workflow
from test_semantic_provider import CHAT_COMPLETIONS, _chat_response

from skillscout import cli
from skillscout.adapters.github import GitHubReadClient
from skillscout.adapters.openai_extract import OpenAIExtractionClient


@pytest.mark.parametrize(
    ("opt_in", "returned_model", "expected_status"),
    [(False, "deepseek-v4-flash", 0), (True, "deepseek-flash", 0),
     (True, "deepseek-v4-flash", 1)],
)
def test_extraction_opt_in_binds_requested_and_recorded_model(
    tmp_path, monkeypatch, capsys, outbound_socket_sentinel,
    opt_in, returned_model, expected_status,
):
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-current-flash-key")
    github = RecordedTransport(_github_routes())
    source = json.loads(recorded_openai_fixture("parsed_2_workflows").body)
    content = source["output"][0]["content"][0]["text"]
    semantic = RecordedTransport({CHAT_COMPLETIONS: _chat_response(
        content, model=returned_model,
    )})
    monkeypatch.setattr(cli, "GitHubReadClient", lambda: GitHubReadClient(
        token="", transport=github.transport(), sleeper=lambda _seconds: None,
    ))
    monkeypatch.setattr(cli, "OpenAIExtractionClient", lambda **kwargs: OpenAIExtractionClient(
        http_client=httpx.Client(transport=semantic.transport()), **kwargs,
    ))
    argv = _argv(tmp_path, *(["--deepseek-current-flash"] if opt_in else []))

    status = cli.main(argv)
    captured = capsys.readouterr()

    assert status == expected_status
    requested = "deepseek-flash" if opt_in else "deepseek-v4-flash"
    assert json.loads(semantic.requests[0].content)["model"] == requested
    assert semantic.call_count(*CHAT_COMPLETIONS) == 1
    assert outbound_socket_sentinel == []
    if expected_status == 0:
        assert captured.err == ""
        assert json.loads(captured.out)["status"] == "completed"
        assert _attempts(tmp_path)[-1]["model_id"] == requested
    else:
        # The public CLI currently closes provider exceptions into this generic
        # diagnostic; the durable attempt and no-second-request rule are decisive.
        assert json.loads(captured.err)["error"]["code"] == "state_operation_failed"
        assert _attempts(tmp_path)[-1]["status"] == "failed"
        assert not (tmp_path / "out" / "extraction-summary.json").exists()
        assert cli.main(argv) == 1
        capsys.readouterr()
        assert semantic.call_count(*CHAT_COMPLETIONS) == 1


def test_current_flash_rejects_openai_before_state_or_network(
    tmp_path, monkeypatch, capsys, outbound_socket_sentinel,
):
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "openai")
    assert cli.main(_argv(tmp_path, "--deepseek-current-flash")) == 1
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "stage_permanent_failure"
    assert not (tmp_path / "state.db").exists()
    assert outbound_socket_sentinel == []


def test_current_flash_build_keeps_separate_pro_reviewer(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.setenv("SKILLSCOUT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    workflow = _workflow()
    descriptor_dir = tmp_path / "descriptor"
    descriptor_dir.mkdir(mode=0o700)
    descriptor = _write_composition_descriptor_for_workflow(
        descriptor_dir, workflow=workflow,
    )
    calls = []
    _patch_phase3_ports(
        monkeypatch, workflow=workflow, outcome="eligible_local_candidate", calls=calls,
    )
    generator = cli.OpenAIGenerationClient
    reviewer = cli.OpenAIReviewClient
    configured = []

    def generator_factory(**kwargs):
        configured.append(("generator", kwargs["model"], kwargs["provider_settings"].provider.value))
        return generator(**kwargs)

    def reviewer_factory(**kwargs):
        configured.append(("reviewer", kwargs["model"], kwargs["provider_settings"].provider.value))
        return reviewer(**kwargs)

    monkeypatch.setattr(cli, "OpenAIGenerationClient", generator_factory)
    monkeypatch.setattr(cli, "OpenAIReviewClient", reviewer_factory)
    status = cli.main(build_argv(
        descriptor=descriptor, phase2_state=tmp_path / "phase2.db",
        state=tmp_path / "phase3.db", output=tmp_path / "out",
    ) + ["--deepseek-current-flash"])
    captured = capsys.readouterr()
    assert status == 0, captured.err
    assert json.loads(captured.out)["outcome"] == "eligible_local_candidate"
    assert configured == [
        ("generator", "deepseek-flash", "deepseek"),
        ("reviewer", "deepseek-v4-pro", "deepseek"),
    ]
    assert calls == ["generator", "validator", "reviewer"]


@pytest.mark.parametrize("argv", [
    ["discover", "--state-repository-id", "1", "--state-repository-full-name", "example/state",
     "--initial-state-root-digest", "sha256:" + "a" * 64],
    ["publish-discovered", "--handoff", "handoff.json"],
    ["publish-candidate", "--candidate", "candidate.json", "--phase2-state", "p2.db",
     "--phase3-state", "p3.db", "--publication-state", "pub.db"],
])
def test_current_flash_option_is_not_a_hosted_or_publication_override(argv, capsys):
    assert cli.build_parser().parse_args(argv).command == argv[0]
    with pytest.raises(SystemExit) as error:
        cli.build_parser().parse_args(argv + ["--deepseek-current-flash"])
    assert error.value.code == 2
    assert "invalid_cli_arguments" in capsys.readouterr().err
