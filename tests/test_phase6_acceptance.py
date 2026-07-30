"""Wave-0 RED mutation contracts for the independent Phase 6 rebuild verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "tools/verify_phase6_acceptance.py"
VALIDATION_PATH = (
    ROOT / ".planning/phases/06-adversarial-mvp-acceptance/06-VALIDATION.md"
)
REQUIREMENTS_PATH = ROOT / ".planning/REQUIREMENTS.md"


def _verifier() -> Any:
    spec = importlib.util.spec_from_file_location("phase6_acceptance_verifier", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _repository_verifier(*, skip_if_missing: bool = True) -> Any:
    verifier = getattr(_verifier(), "verify_repository", None)
    if verifier is None:
        if skip_if_missing:
            pytest.skip("phase6-rebuild-verifier-not-yet-implemented")
        pytest.fail(
            "phase6-missing-acceptance-verifier:verify_repository",
            pytrace=False,
        )
    return verifier


def test_required_phase6_repository_verifier_is_missing() -> None:
    _repository_verifier(skip_if_missing=False)


def test_hard_gate_registry_is_exact_blocking_and_current() -> None:
    module = _verifier()
    assert module.registry_is_exact()
    gates = tuple(module.HARD_GATE_REGISTRY)
    assert len(gates) == 19
    assert all(gate.blocking is True for gate in gates)
    assert tuple(gate.identifier for gate in gates)[3] == "hosted_kernel_isolation"
    assert tuple(gate.identifier for gate in gates)[-1] == "all_44_requirements"


@pytest.fixture
def acceptance_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    for relative in (
        Path("tools/verify_phase6_acceptance.py"),
        Path("tools/verify_phase6_validation_map.py"),
        Path(".planning/REQUIREMENTS.md"),
    ):
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    phase_source = ROOT / ".planning/phases/06-adversarial-mvp-acceptance"
    phase_target = repository / ".planning/phases/06-adversarial-mvp-acceptance"
    phase_target.mkdir(parents=True, exist_ok=True)
    for path in phase_source.glob("06-??-PLAN.md"):
        shutil.copy2(path, phase_target / path.name)
    shutil.copy2(VALIDATION_PATH, phase_target / VALIDATION_PATH.name)
    return repository


@pytest.mark.parametrize(
    "mutation",
    (
        "missing_evidence",
        "swapped_evidence",
        "duplicate_evidence",
        "stale_evidence",
        "self_referential_evidence",
        "identical_replay_effect",
        "changed_lineage_alias",
        "stale_gate_b4",
        "stale_draft_head",
        "hard_gate_deleted",
        "all_44_inverse_drift",
    ),
)
def test_independent_verifier_rejects_whole_phase_evidence_mutation(
    acceptance_repository: Path,
    mutation: str,
) -> None:
    verifier = _repository_verifier()
    with pytest.raises(verifier.AcceptanceError):
        verifier(acceptance_repository, mutation=mutation)


def test_all_44_requirement_ids_are_unique_before_report_rebuild() -> None:
    source = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    requirement_ids = tuple(
        re.findall(
            r"^- \[[ x]\] \*\*([A-Z]+-\d{2})\*\*:",
            source.split("## v2 Requirements", 1)[0],
            re.MULTILINE,
        )
    )
    assert len(requirement_ids) == 44
    assert len(set(requirement_ids)) == 44


def test_wave_zero_never_fabricates_a_positive_release_verdict() -> None:
    module = _verifier()
    assert module.main([]) == 1
    assert module.main(["--registry-only"]) == 0
    assert not (ROOT / ".planning/phases/06-adversarial-mvp-acceptance/06-ACCEPTANCE-REPORT.md").exists()
    assert not (ROOT / ".planning/phases/06-adversarial-mvp-acceptance/06-RELEASE-REQUIREMENTS.json").exists()


def test_search_credential_gate_rebuilds_exact_plan_06_06_offline_state() -> None:
    module = _verifier()

    report = module.verify_offline_state(ROOT)

    assert report.state_commit_sha == ("37f8dcbf74c85f2471670373fd03f71d9f155bae")
    assert report.state_root_digest == (
        "sha256:b4167cffc31969854260d4acd58b804f4823a4d25d078ef3b5dc88445b75c2e5"
    )
    assert report.workflow_sha256 == (
        "sha256:7eca32de7c0468d18c180ebecf567d7239412e54c2776e43621930b894570f63"
    )
    assert report.source_commit_sha == ("a3c41cf8501bec435a646f140f52acedf1c5f312")
    assert report.hosted_run_id == 30519607061
    assert report.run_attempt == 1
    assert report.isolation_mechanism == "docker_network_none"


def test_search_credential_gate_rejects_a_stale_canonical_state_identity() -> None:
    module = _verifier()

    with pytest.raises(module.OfflineStateError):
        module.verify_offline_state(
            ROOT,
            expected_state_commit="0" * 40,
        )


def test_future_requirement_map_must_be_canonical_and_exactly_all_44() -> None:
    path = (
        ROOT
        / ".planning/phases/06-adversarial-mvp-acceptance"
        / "06-RELEASE-REQUIREMENTS.json"
    )
    if not path.exists():
        pytest.skip("phase6-release-requirement-map-not-yet-built")
    raw = path.read_bytes()
    payload = json.loads(raw)
    assert raw == (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")
    assert len(payload["requirements"]) == 44
    assert set(payload["requirements"]) == set(payload["inverse_requirement_map"])


def _cli_subcommands() -> dict[str, Any]:
    from skillscout.cli import build_parser

    parser = build_parser()
    action = next(
        item
        for item in parser._actions
        if item.__class__.__name__ == "_SubParsersAction"
    )
    return dict(action.choices)


def test_acceptance_cli_parser_has_only_closed_authority_options() -> None:
    commands = _cli_subcommands()
    expected = {
        "nominate-benchmark": {
            "--state-repository-id",
            "--state-repository-full-name",
            "--initial-state-root-digest",
        },
        "run-acceptance": {
            "--manifest",
            "--acceptance-run-id",
            "--state-commit-sha",
            "--state-root-digest",
        },
        "record-acceptance-attestation": {
            "--attestation",
            "--kind",
            "--state-commit-sha",
            "--state-root-digest",
        },
        "rebuild-acceptance": {
            "--acceptance-run-id",
            "--evidence-root-digest",
            "--state-commit-sha",
            "--state-root-digest",
        },
    }
    forbidden = {
        "--model",
        "--endpoint",
        "--catalog",
        "--token",
        "--secret",
        "--ref",
        "--merge",
        "--approve",
        "--ready",
        "--delete",
        "--cleanup",
    }
    for name, required in expected.items():
        options = {
            option
            for action in commands[name]._actions
            for option in action.option_strings
        }
        assert required <= options
        assert forbidden.isdisjoint(options)
    kind = next(
        action
        for action in commands["record-acceptance-attestation"]._actions
        if "--kind" in action.option_strings
    )
    assert tuple(kind.choices) == ("human-review", "probe-cleanup")


def test_acceptance_bootstrap_target_is_fixed_and_fact_validation_is_pre_secret() -> None:
    import skillscout.bootstrap as bootstrap

    assert bootstrap.ACCEPTANCE_CATALOG_FULL_NAME == (
        "alexzhu0/skillscout-catalog-test"
    )
    signature = inspect.signature(bootstrap.load_acceptance_runtime_config)
    assert "environ" in signature.parameters
    assert {
        "model",
        "endpoint",
        "catalog",
        "token",
        "credential",
    }.isdisjoint(signature.parameters)

    class ForbiddenEnvironment(dict[str, str]):
        def __getitem__(self, key: str) -> str:
            pytest.fail(f"invalid authority read credential:{key}")

        def get(self, key: str, default: Any = None) -> Any:
            pytest.fail(f"invalid authority read credential:{key}")

    with pytest.raises(ValueError, match="acceptance runtime configuration rejected"):
        bootstrap.load_acceptance_runtime_config(
            manifest_path=Path("not-the-locked-manifest.json"),
            state_commit_sha="not-a-sha",
            state_root_digest="not-a-digest",
            environ=ForbiddenEnvironment(),
        )


def test_acceptance_cli_unknown_flag_uses_existing_fixed_parser_diagnostic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from skillscout.cli import build_parser

    with pytest.raises(SystemExit) as failure:
        build_parser().parse_args(
            ["run-acceptance", "--unknown", "SECRET_DO_NOT_ECHO"]
        )
    captured = capsys.readouterr()
    assert failure.value.code == 2
    assert captured.out == ""
    assert captured.err == (
        '{"error":{"code":"invalid_cli_arguments",'
        '"summary":"Command-line arguments were rejected."}}\n'
    )
    assert "SECRET_DO_NOT_ECHO" not in captured.err


def test_nomination_cli_emits_persisted_role_neutral_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import skillscout.cli as cli
    from skillscout.domain.acceptance import NominationEntryV1, NominationSetV1
    from skillscout.domain.canonical import sha256_digest

    entries = tuple(
        NominationEntryV1(
            schema_version="nomination-entry-v1",
            repository_full_name=f"octo-org/workflow-{index}",
            repository_id=910000 + index,
            exact_commit_sha=f"{index:040x}",
            license_spdx="MIT",
            selection_source="search_derived",
            selection_evidence_digests=(sha256_digest({"index": index}),),
        )
        for index in range(1, 6)
    )
    nomination = NominationSetV1.model_validate(
        {
            "schema_version": "nomination-set-v1",
            "nomination_set_id": "nomination-cli",
            "query_set_digest": "sha256:" + ("a" * 64),
            "search_run_authority_digest": "sha256:" + ("b" * 64),
            "search_derived_entries": tuple(
                entry.model_dump(mode="python", exclude_none=False)
                for entry in sorted(entries, key=lambda entry: entry.entry_digest or "")
            ),
            "user_nominated_entries": (),
            "created_at": "2026-07-30T00:00:00.000000Z",
        },
        strict=True,
    )
    config = SimpleNamespace(
        state_repository_id=1310897029,
        state_repository_full_name="alexzhu0/skillscout",
        query_set_digest=nomination.query_set_digest,
        initial_state_root_digest="sha256:" + ("c" * 64),
    )
    monkeypatch.setattr(cli, "load_nomination_runtime_config", lambda **_kwargs: config)
    monkeypatch.setattr(
        cli,
        "build_nomination_application",
        lambda _config: SimpleNamespace(
            run=lambda **_kwargs: SimpleNamespace(
                nomination=nomination,
                state_commit_sha="d" * 40,
                state_root_digest="sha256:" + ("e" * 64),
            )
        ),
        raising=False,
    )

    payload = cli._run_nominate_benchmark(
        SimpleNamespace(
            state_repository_id="1310897029",
            state_repository_full_name="alexzhu0/skillscout",
            initial_state_root_digest=config.initial_state_root_digest,
        )
    )

    assert payload["status"] == "nomination_persisted"
    assert payload["state_commit_sha"] == "d" * 40
    assert payload["nomination_set_digest"] == nomination.nomination_set_digest
    assert len(payload["search_derived_entries"]) == 5
    assert all(
        "coverage_role" not in entry for entry in payload["search_derived_entries"]
    )


def test_exact_manifest_live_authority_is_validated_without_secret_lookup() -> None:
    """Catches a preflight that opens credentials before all immutable identities."""

    import skillscout.bootstrap as bootstrap

    class ForbiddenCredentials(dict[str, str]):
        def __getitem__(self, key: str) -> str:
            pytest.fail(f"credential read during non-secret preflight:{key}")

        def get(self, key: str, default: Any = None) -> Any:
            if key in {
                "DEEPSEEK_API_KEY",
                "SKILLSCOUT_SOURCE_GITHUB_TOKEN",
                "SKILLSCOUT_STATE_GITHUB_TOKEN",
                "OPENAI_API_KEY",
            }:
                pytest.fail(f"credential read during non-secret preflight:{key}")
            return super().get(key, default)

    with pytest.raises(ValueError):
        bootstrap.verify_live_acceptance_authority(
            repository_root=ROOT,
            authority_bytes=b"{}",
            observed_source_commit_sha="c" * 40,
            observed_state_commit_sha="d" * 40,
            observed_state_root_digest="sha256:" + ("e" * 64),
            observed_state_repository_id=123,
            observed_state_repository_full_name="example/state",
            environ=ForbiddenCredentials(
                {
                    "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                    "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                }
            ),
        )


def test_live_authority_verifier_requires_approved_state_fact_and_trusted_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Self-hashed workflow inputs cannot replace a human-approved authority file."""

    import shutil

    import skillscout.bootstrap as bootstrap
    from skillscout.domain.acceptance import (
        LiveAcceptanceAuthorityV1,
        LockedBenchmarkManifestV1,
    )
    from skillscout.domain.canonical import canonical_json_bytes
    from skillscout.domain.discovery import DiscoveryBudgetPolicyV1, DiscoveryQuerySetV1

    manifest_relative = Path(
        ".planning/phases/06-adversarial-mvp-acceptance/"
        "06-BENCHMARK-MANIFEST.json"
    )
    workflow_relative = Path(".github/workflows/phase6-acceptance.yml")
    query_relative = Path("config/discovery-queries-v1.json")
    for relative in (manifest_relative, workflow_relative, query_relative):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    manifest = LockedBenchmarkManifestV1.model_validate_json(
        (tmp_path / manifest_relative).read_bytes(),
        strict=True,
    )
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (tmp_path / query_relative).read_bytes(),
        strict=True,
    )
    workflow_digest = "sha256:" + hashlib.sha256(
        (tmp_path / workflow_relative).read_bytes()
    ).hexdigest()
    authority = LiveAcceptanceAuthorityV1(
        schema_version="live-acceptance-authority-v1",
        authority_version=1,
        source_commit_sha="c" * 40,
        acceptance_workflow_sha256=workflow_digest,
        manifest_path=manifest_relative.as_posix(),
        manifest_digest=manifest.manifest_digest,
        nomination_set_digest=manifest.nomination_set_digest,
        lock_attestation_digest=manifest.lock_attestation.attestation_digest,
        state_commit_sha="e" * 40,
        state_root_digest="sha256:" + ("f" * 64),
        state_repository_id=123,
        state_repository_full_name="example/state",
        query_set_digest=query_set.query_set_digest,
        budget_policy_digest=DiscoveryBudgetPolicyV1().budget_policy_digest,
        semantic_provider="deepseek",
        provider_base_url="https://api.deepseek.com",
        stage_models=(
            "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ),
        prompt_versions=(
            "extract-prompt-v1",
            "generator-prompt-v1",
            "reviewer-prompt-v1",
        ),
        schema_versions=(
            "workflow-spec-v1",
            "generation-draft-v1",
            "reviewer-judgment-v1",
        ),
        policy_versions=(
            "discovery-budget-policy-v1",
            "extract-policy-v1",
            "generator-policy-v1",
            "qualification-policy-v1",
            "reader-policy-v1",
            "reviewer-policy-v1",
        ),
        max_candidates=100,
        max_semantic_candidates=20,
        max_semantic_requests=20,
        max_files_per_repository=25,
        max_source_files_per_repository=5,
        max_file_bytes=131_072,
        max_total_bytes_per_repository=524_288,
        max_tokens_per_repository=40_000,
        benchmark_scenario_write_count=5,
        replay_semantic_effect_count=0,
        replay_publication_effect_count=0,
        reviewer_id="alexzhu0",
        approved_at="2026-07-30T00:00:00.000000Z",
    )
    authority_bytes = canonical_json_bytes(authority) + b"\n"

    verified = bootstrap.verify_live_acceptance_authority(
        repository_root=tmp_path,
        authority_bytes=authority_bytes,
        observed_source_commit_sha="c" * 40,
        observed_state_commit_sha="e" * 40,
        observed_state_root_digest="sha256:" + ("f" * 64),
        observed_state_repository_id=123,
        observed_state_repository_full_name="example/state",
        environ={
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        },
    )

    assert verified == authority
    import skillscout.domain.extraction as extraction

    monkeypatch.setattr(
        extraction,
        "EXTRACT_PROMPT_VERSION",
        "extract-prompt-drift-v2",
    )
    with pytest.raises(ValueError):
        bootstrap.verify_live_acceptance_authority(
            repository_root=tmp_path,
            authority_bytes=authority_bytes,
            observed_source_commit_sha="c" * 40,
            observed_state_commit_sha="e" * 40,
            observed_state_root_digest="sha256:" + ("f" * 64),
            observed_state_repository_id=123,
            observed_state_repository_full_name="example/state",
            environ={
                "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            },
        )
    monkeypatch.undo()
    with pytest.raises(ValueError):
        bootstrap.verify_live_acceptance_authority(
            repository_root=tmp_path,
            authority_bytes=authority_bytes,
            observed_source_commit_sha="d" * 40,
            observed_state_commit_sha="e" * 40,
            observed_state_root_digest="sha256:" + ("f" * 64),
            observed_state_repository_id=123,
            observed_state_repository_full_name="example/state",
            environ={
                "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            },
        )
    with pytest.raises(ValueError):
        bootstrap.verify_live_acceptance_authority(
            repository_root=tmp_path,
            authority_bytes=authority_bytes,
            observed_source_commit_sha="c" * 40,
            observed_state_commit_sha="d" * 40,
            observed_state_root_digest="sha256:" + ("f" * 64),
            observed_state_repository_id=123,
            observed_state_repository_full_name="example/state",
            environ={
                "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            },
        )
    assert "06-LIVE-AUTHORITY.json" not in inspect.getsource(
        bootstrap.verify_live_acceptance_authority
    )


def test_live_authority_cli_accepts_only_a_complete_state_bundle_root() -> None:
    """A raw operations database cannot establish the checked-out state root."""

    commands = _cli_subcommands()
    parser = commands["verify-live-authority"]
    options = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--authority-state-root" in options
    assert "--authority-operations-state" not in options


@pytest.mark.parametrize(
    ("action", "expected_handler"),
    (("benchmark", "benchmark"), ("replay", "replay")),
)
def test_run_acceptance_dispatches_exact_action_without_publication_authority(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    expected_handler: str,
) -> None:
    """The protected commands must execute, not merely revalidate authority."""

    import skillscout.cli as cli

    config = SimpleNamespace(
        manifest=object(),
        manifest_path=Path("06-BENCHMARK-MANIFEST.json"),
        state_commit_sha="a" * 40,
        state_root_digest="sha256:" + ("b" * 64),
    )
    restored = object()
    calls: list[str] = []
    monkeypatch.setattr(cli, "load_acceptance_runtime_config", lambda **_: config)
    monkeypatch.setattr(cli, "_restore_acceptance_state", lambda **_: restored)
    monkeypatch.setattr(
        cli,
        "load_publication_authority_config",
        lambda: pytest.fail("benchmark/replay cannot load publication authority"),
    )
    monkeypatch.setattr(
        cli,
        "_run_live_benchmark",
        lambda **_: calls.append("benchmark") or {"status": "benchmark_complete"},
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "_run_live_replay",
        lambda **_: calls.append("replay") or {"status": "replay_complete"},
        raising=False,
    )

    result = cli._run_acceptance(
        SimpleNamespace(
            action=action,
            manifest=config.manifest_path,
            acceptance_run_id="acceptance-live-five",
            state_commit_sha=config.state_commit_sha,
            state_root_digest=config.state_root_digest,
        )
    )

    assert calls == [expected_handler]
    assert result["status"] == f"{expected_handler}_complete"


def test_live_execution_builder_has_no_publication_state_or_configuration() -> None:
    """The benchmark/replay composition cannot construct publication authority."""

    import dataclasses
    import skillscout.bootstrap as bootstrap

    fields = {
        field.name for field in dataclasses.fields(bootstrap.AcceptanceRuntimeConfig)
    }
    assert "catalog_full_name" not in fields
    source = inspect.getsource(bootstrap.build_live_acceptance_execution)
    for forbidden in (
        "PublicationStateStore",
        "publication_factory",
        "load_publication_authority_config",
        "SKILLSCOUT_CATALOG",
    ):
        assert forbidden not in source


def test_acceptance_restore_never_opens_mutable_publication_owner() -> None:
    """Benchmark, replay, and their preflight only validate immutable owner bytes."""

    import skillscout.bootstrap as bootstrap
    import skillscout.cli as cli

    assert hasattr(bootstrap, "read_exact_acceptance_state")
    for target in (
        cli._restore_acceptance_state,
        cli._run_verify_live_authority,
        bootstrap.read_exact_acceptance_state,
    ):
        source = inspect.getsource(target)
        assert "restore_three_store_bundle" not in source
        assert "PublicationStateStore" not in source
    discovery_source = inspect.getsource(bootstrap.build_discovery_application)
    assert "restore_acceptance_state_bundle" in discovery_source


def test_live_replay_builder_dispatches_state_only_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the production builder without opening live or publication adapters."""

    import skillscout.adapters.operations_state as operations_state
    import skillscout.application.acceptance as acceptance
    import skillscout.bootstrap as bootstrap

    manifest_path = (
        ROOT
        / ".planning/phases/06-adversarial-mvp-acceptance"
        / "06-BENCHMARK-MANIFEST.json"
    )
    manifest = acceptance.load_locked_benchmark_manifest(manifest_path)
    config = bootstrap.AcceptanceRuntimeConfig(
        manifest_path=manifest_path,
        manifest=manifest,
        state_commit_sha="a" * 40,
        state_root_digest="sha256:" + ("b" * 64),
        semantic_provider="deepseek",
        extractor_model_id="deepseek-v4-flash",
        generator_model_id="deepseek-v4-flash",
        reviewer_model_id="deepseek-v4-pro",
        live_acceptance_authority_digest="sha256:" + ("9" * 64),
    )
    discovery_config = SimpleNamespace(
        operations_state=Path("state/databases/operations.sqlite3"),
        pipeline_state=Path("state/databases/pipeline.sqlite3"),
    )
    restored = SimpleNamespace(
        status="verified",
        observed_head=config.state_commit_sha,
        bundle=SimpleNamespace(
            root=SimpleNamespace(root_digest=config.state_root_digest)
        ),
    )
    calls: list[str] = []
    monkeypatch.setattr(
        bootstrap,
        "_acceptance_discovery_config",
        lambda *_args, **_kwargs: discovery_config,
    )
    monkeypatch.setattr(
        operations_state,
        "_parse_bundle_exports",
        lambda _bundle: (object(), object(), object(), object()),
    )
    monkeypatch.setattr(
        bootstrap,
        "_LateStateDurabilityBarrier",
        lambda *_args, **_kwargs: SimpleNamespace(
            sync_discovery=lambda **_arguments: None
        ),
    )
    monkeypatch.setattr(
        acceptance,
        "run_exact_replay",
        lambda *_args, **_kwargs: (
            calls.append("replay")
            or SimpleNamespace(replay_digest="sha256:" + ("c" * 64))
        ),
    )

    execution = bootstrap.build_live_acceptance_execution(
        config=config,
        restored=restored,
        action="replay",
        acceptance_run_id="acceptance-live-five",
        environ={},
    )

    assert execution.run() == {
        "acceptance_run_id": "acceptance-live-five",
        "replay_digest": "sha256:" + ("c" * 64),
        "status": "replay_complete",
    }
    assert calls == ["replay"]


def test_production_replay_uses_restored_bundle_and_zero_live_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the real replay builder/projector/stores with only remote CAS faked."""

    import skillscout.adapters.github as github_adapter
    import skillscout.adapters.openai_extract as extract_adapter
    import skillscout.adapters.openai_generate as generate_adapter
    import skillscout.adapters.openai_review as review_adapter
    import skillscout.adapters.operations_state as operations_state
    import skillscout.adapters.publication_state as publication_state
    import skillscout.adapters.state as pipeline_state
    import skillscout.bootstrap as bootstrap
    import skillscout.domain.acceptance as acceptance_domain
    from skillscout.domain.canonical import sha256_digest

    timestamp = "2026-07-30T12:00:00.000000Z"
    nomination_entries = tuple(
        sorted(
            (
                acceptance_domain.NominationEntryV1(
                    schema_version="nomination-entry-v1",
                    repository_full_name=f"example/repository-{index}",
                    repository_id=100 + index,
                    exact_commit_sha=f"{index:040x}",
                    license_spdx="MIT",
                    selection_source="search_derived",
                    selection_evidence_digests=(
                        "sha256:" + f"{index:064x}",
                    ),
                )
                for index in range(1, 6)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    nomination = acceptance_domain.NominationSetV1(
        schema_version="nomination-set-v1",
        nomination_set_id="acceptance-production-replay",
        query_set_digest="sha256:" + ("a" * 64),
        search_run_authority_digest="sha256:" + ("b" * 64),
        search_derived_entries=nomination_entries,
        user_nominated_entries=(),
        created_at=timestamp,
    )
    roles = ("positive", "positive_multi_workflow", "negative", "negative", "borderline")
    benchmark_entries = tuple(
        sorted(
            (
                acceptance_domain.BenchmarkEntryV1(
                    schema_version="benchmark-entry-v1",
                    repository_full_name=entry.repository_full_name,
                    repository_id=entry.repository_id,
                    exact_commit_sha=entry.exact_commit_sha,
                    license_spdx=entry.license_spdx,
                    selection_source=entry.selection_source,
                    coverage_role=role,
                    nomination_entry_digest=entry.entry_digest,
                    selection_evidence_digests=entry.selection_evidence_digests,
                )
                for entry, role in zip(nomination_entries, roles, strict=True)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    manifest_values = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": nomination.nomination_set_digest,
        "entries": benchmark_entries,
        "prior_manifest_digest": None,
    }
    manifest_digest = sha256_digest(
        {
            **manifest_values,
            "entries": tuple(
                item.model_dump(mode="json", exclude_none=False)
                for item in benchmark_entries
            ),
        }
    )
    manifest = acceptance_domain.LockedBenchmarkManifestV1(
        **manifest_values,
        manifest_digest=manifest_digest,
        lock_attestation=acceptance_domain.BenchmarkLockAttestationV1(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=nomination.nomination_set_digest,
            manifest_digest=manifest_digest,
            reviewer_id="acceptance-reviewer",
            locked_at=timestamp,
        ),
    )

    def telemetry(
        stage: str,
        authority_digest: str,
        request_suffix: str,
    ) -> object:
        return acceptance_domain.AcceptanceSemanticTelemetryV1(
            schema_version="acceptance-semantic-telemetry-v1",
            live_acceptance_authority_digest=manifest.manifest_digest,
            stage=stage,
            workflow_spec_authority_digest=authority_digest,
            attempt_no=1,
            request_id=f"request-{request_suffix}-{stage}",
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

    run_id = "acceptance-production-replay"
    state_root = tmp_path / "state" / "databases"
    state_root.mkdir(parents=True)
    operations_path = state_root / "operations.sqlite3"
    pipeline_path = state_root / "pipeline.sqlite3"
    publication_path = state_root / "publication.sqlite3"
    with operations_state.OperationsStateStore(operations_path) as operations:
        operations.record_acceptance_fact(
            run_id, "acceptance_nomination", nomination
        )
        operations.record_acceptance_fact(
            run_id, "acceptance_benchmark_lock", manifest
        )
        request_ordinal = 0
        for ordinal, entry in enumerate(manifest.entries, start=1):
            eligible = ordinal == 1
            stages = (
                ("extractor", "generator", "reviewer")
                if eligible
                else ("extractor",)
            )
            stage_telemetry = tuple(
                telemetry(stage, entry.entry_digest, str(ordinal))
                for stage in stages
            )
            operations.record_acceptance_fact(
                run_id,
                "acceptance_budget_reservation",
                acceptance_domain.AcceptanceBudgetReservationV1(
                    schema_version="acceptance-budget-reservation-v1",
                    acceptance_run_id=run_id,
                    benchmark_manifest_digest=manifest.manifest_digest,
                    nomination_entry_digest=entry.nomination_entry_digest,
                    benchmark_entry_digest=entry.entry_digest,
                    repository_id=entry.repository_id,
                    repository_full_name=entry.repository_full_name,
                    ordinal=ordinal,
                    max_files=25,
                    max_source_files=5,
                    max_file_bytes=131_072,
                    max_total_bytes=524_288,
                    max_estimated_tokens=40_000,
                    semantic_candidate_slots=1,
                    campaign_semantic_request_limit=20,
                    reserved_at=timestamp,
                ),
            )
            admission = acceptance_domain.AcceptanceFixedCandidateAdmissionV1(
                schema_version="acceptance-fixed-candidate-admission-v1",
                acceptance_run_id=run_id,
                benchmark_manifest_digest=manifest.manifest_digest,
                nomination_entry_digest=entry.nomination_entry_digest,
                benchmark_entry_digest=entry.entry_digest,
                repository_id=entry.repository_id,
                repository_full_name=entry.repository_full_name,
                exact_commit_sha=entry.exact_commit_sha,
                license_spdx=entry.license_spdx,
                ordinal=ordinal,
                admitted_at=timestamp,
            )
            operations.record_acceptance_fact(
                run_id,
                "acceptance_fixed_candidate_admission",
                admission,
            )
            for item in stage_telemetry:
                request_ordinal += 1
                operations.record_acceptance_fact(
                    run_id,
                    "acceptance_semantic_request_reservation",
                    acceptance_domain.AcceptanceSemanticRequestReservationV1(
                        schema_version=(
                            "acceptance-semantic-request-reservation-v1"
                        ),
                        acceptance_run_id=run_id,
                        fixed_candidate_admission_digest=(
                            admission.admission_digest
                        ),
                        repository_id=entry.repository_id,
                        workflow_spec_authority_digest=(
                            item.workflow_spec_authority_digest
                        ),
                        stage=item.stage,
                        attempt_no=item.attempt_no,
                        request_ordinal=request_ordinal,
                        reserved_at=timestamp,
                    ),
                )
            attempt_digests = tuple(
                sorted(
                    "sha256:" + f"{ordinal * 10 + index:064x}"
                    for index in range(1, len(stages) + 1)
                )
            )
            operations.record_acceptance_fact(
                run_id,
                "acceptance_scenario",
                acceptance_domain.AcceptanceScenarioResultV1(
                    schema_version="acceptance-scenario-result-v1",
                    acceptance_run_id=run_id,
                    scenario_id=f"locked-{ordinal}-{entry.repository_id}",
                    repository_id=entry.repository_id,
                    repository_full_name=entry.repository_full_name,
                    exact_commit_sha=entry.exact_commit_sha,
                    license_spdx=entry.license_spdx,
                    benchmark_manifest_digest=manifest.manifest_digest,
                    live_acceptance_authority_digest=manifest.manifest_digest,
                    terminal_class=(
                        "eligible" if eligible else "business_terminal"
                    ),
                    outcome=(
                        "eligible_local_candidate" if eligible else "no_workflow"
                    ),
                    reason_code=(
                        "eligible_candidate_completed"
                        if eligible
                        else "no_reusable_workflow"
                    ),
                    evidence_digests=(entry.entry_digest,),
                    candidate_funnel=(
                        (
                            "fixed_identity",
                            "deterministic_filter",
                            "bounded_read",
                            "extractor",
                            "qualification",
                            "generator",
                            "validation",
                            "reviewer",
                        )
                        if eligible
                        else (
                            "fixed_identity",
                            "deterministic_filter",
                            "bounded_read",
                            "extractor",
                        )
                    ),
                    reader_order="readme_docs_examples_manifests_source",
                    reader_file_count=2,
                    reader_source_file_count=0,
                    reader_total_bytes=100,
                    reader_estimated_tokens=25,
                    semantic_request_count=len(stage_telemetry),
                    semantic_attempt_digests=attempt_digests,
                    semantic_telemetry=stage_telemetry,
                    actual_models=tuple(
                        item.actual_model for item in stage_telemetry
                    ),
                    prompt_versions=tuple(
                        item.prompt_version for item in stage_telemetry
                    ),
                    schema_versions=tuple(
                        item.output_schema_version for item in stage_telemetry
                    ),
                    policy_versions=tuple(
                        item.policy_version for item in stage_telemetry
                    ),
                    workflow_fingerprint=(
                        entry.entry_digest if eligible else None
                    ),
                    workflow_spec_authority_digest=(
                        entry.entry_digest if eligible else None
                    ),
                    eligible_locator=(
                        "state/objects/eligible.json" if eligible else None
                    ),
                    expected_coverage_role=entry.coverage_role,
                    evaluator_matches_observed=True,
                    publication_decision=(
                        "eligible_for_later_publication"
                        if eligible
                        else "not_eligible"
                    ),
                    warnings=(),
                    recorded_at=timestamp,
                ),
            )
        pipeline = pipeline_state.SQLiteStateStore(pipeline_path)
        publication = publication_state.PublicationStateStore(
            publication_path
        )
        try:
            bundle = operations_state.assemble_three_store_bundle(
                pipeline_store=pipeline,
                operations_store=operations,
                publication_store=publication,
                prior_root_digest="sha256:" + ("c" * 64),
                state_parent_commit_sha="d" * 40,
                query_set_digest="sha256:" + ("a" * 64),
                budget_policy_digest="sha256:" + ("b" * 64),
                created_at=timestamp,
            )
        finally:
            publication.close()
            pipeline.close()

    query_target = tmp_path / "config" / "discovery-queries-v1.json"
    query_target.parent.mkdir()
    shutil.copy2(ROOT / "config/discovery-queries-v1.json", query_target)
    monkeypatch.chdir(tmp_path)
    operations_state.restore_acceptance_state_bundle(
        bundle,
        pipeline_path=Path("state/databases/pipeline.sqlite3"),
        operations_path=Path("state/databases/operations.sqlite3"),
    )
    config = bootstrap.AcceptanceRuntimeConfig(
        manifest_path=(
            ROOT
            / ".planning/phases/06-adversarial-mvp-acceptance"
            / "06-BENCHMARK-MANIFEST.json"
        ),
        manifest=manifest,
        state_commit_sha="d" * 40,
        state_root_digest=bundle.root.root_digest,
        semantic_provider="deepseek",
        extractor_model_id="deepseek-v4-flash",
        generator_model_id="deepseek-v4-flash",
        reviewer_model_id="deepseek-v4-pro",
        live_acceptance_authority_digest=manifest.manifest_digest,
    )
    commits = iter(("e" * 40, "f" * 40))
    roots = iter(
        ("sha256:" + ("1" * 64), "sha256:" + ("2" * 64))
    )

    class LocalCAS:
        def sync_discovery(self, *, observed_head: str, **_: object) -> object:
            return SimpleNamespace(
                status="verified",
                previous_head=observed_head,
                commit_sha=next(commits),
                root_digest=next(roots),
            )

    monkeypatch.setattr(
        bootstrap,
        "_LateStateDurabilityBarrier",
        lambda *_args, **_kwargs: LocalCAS(),
    )

    def forbidden(*_args: object, **_kwargs: object) -> object:
        pytest.fail("replay constructed a live provider/GitHub/publication capability")

    monkeypatch.setattr(github_adapter, "GitHubReadClient", forbidden)
    monkeypatch.setattr(extract_adapter, "OpenAIExtractionClient", forbidden)
    monkeypatch.setattr(generate_adapter, "OpenAIGenerationClient", forbidden)
    monkeypatch.setattr(review_adapter, "OpenAIReviewClient", forbidden)
    monkeypatch.setattr(publication_state, "PublicationStateStore", forbidden)
    monkeypatch.setattr(operations_state, "PublicationStateStore", forbidden)

    execution = bootstrap.build_live_acceptance_execution(
        config=config,
        restored=SimpleNamespace(
            status="verified",
            observed_head=config.state_commit_sha,
            bundle=bundle,
        ),
        action="replay",
        acceptance_run_id=run_id,
        environ={
            "SKILLSCOUT_STATE_REPOSITORY_ID": "123",
            "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME": "example/state",
        },
    )
    result = execution.run()
    assert result["status"] == "replay_complete"
    with operations_state.OperationsStateStore(operations_path) as operations:
        snapshot = operations.acceptance_snapshot(run_id)
        assert tuple(
            item.kind
            for item in snapshot.facts
            if item.kind.startswith("acceptance_replay")
        ) == ("acceptance_replay", "acceptance_replay_evidence")
        evidence = next(
            item.fact
            for item in snapshot.facts
            if item.kind == "acceptance_replay_evidence"
        )
        assert isinstance(evidence, acceptance_domain.ReplayEvidenceV1)
        assert evidence.before_projection_digest == evidence.after_projection_digest
        assert evidence.before_object_digests == evidence.after_object_digests


def test_live_runner_persists_read_and_semantic_budget_before_remote_read() -> None:
    """Every fixed repository must consume its bounded slot before GitHub I/O."""

    import skillscout.bootstrap as bootstrap
    import skillscout.domain.acceptance as acceptance

    assert hasattr(acceptance, "AcceptanceBudgetReservationV1")
    source = inspect.getsource(bootstrap._FixedRepositoryAcceptanceRunner.run)
    reservation = source.index('"acceptance_budget_reservation"')
    remote_read = source.index("github = GitHubReadClient(")
    assert reservation < remote_read


def test_production_fixed_runner_reaches_eligible_with_only_outer_effects_faked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the real fixed runner, Phase 2/3, SQLite, and local validator."""

    import httpx

    from recorded_transport import (
        RecordedResponse,
        RecordedTransport,
        make_tree_fixture,
        recorded_fixture,
        recorded_openai_fixture,
        recorded_openai_generator_fixture,
    )
    import skillscout.adapters.github as github_adapter
    import skillscout.adapters.openai_extract as extract_adapter
    import skillscout.adapters.openai_generate as generate_adapter
    import skillscout.adapters.openai_review as review_adapter
    import skillscout.adapters.operations_state as operations_state
    import skillscout.adapters.publication_state as publication_state
    import skillscout.adapters.state as pipeline_state
    import skillscout.application.acceptance as acceptance_application
    import skillscout.bootstrap as bootstrap
    import skillscout.domain.acceptance as acceptance_domain
    from skillscout.domain.canonical import sha256_digest
    from skillscout.domain.discovery import DiscoveryQuerySetV1
    from skillscout.application.ports import DurabilityReceipt

    timestamp = "2026-07-30T12:00:00.000000Z"
    pinned = "0123456789abcdef0123456789abcdef01234567"
    nomination_entries = tuple(
        sorted(
            (
                acceptance_domain.NominationEntryV1(
                    schema_version="nomination-entry-v1",
                    repository_full_name=(
                        "example/approved-repo"
                        if index == 1
                        else f"example/repository-{index}"
                    ),
                    repository_id=840001 if index == 1 else 840000 + index,
                    exact_commit_sha=pinned if index == 1 else f"{index:040x}",
                    license_spdx="MIT",
                    selection_source="search_derived",
                    selection_evidence_digests=(
                        "sha256:" + f"{index:064x}",
                    ),
                )
                for index in range(1, 6)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    nomination = acceptance_domain.NominationSetV1(
        schema_version="nomination-set-v1",
        nomination_set_id="acceptance-production-fixed-runner",
        query_set_digest="sha256:" + ("a" * 64),
        search_run_authority_digest="sha256:" + ("b" * 64),
        search_derived_entries=nomination_entries,
        user_nominated_entries=(),
        created_at=timestamp,
    )
    roles = (
        "positive",
        "positive_multi_workflow",
        "negative",
        "negative",
        "borderline",
    )
    benchmark_entries = tuple(
        sorted(
            (
                acceptance_domain.BenchmarkEntryV1(
                    schema_version="benchmark-entry-v1",
                    repository_full_name=entry.repository_full_name,
                    repository_id=entry.repository_id,
                    exact_commit_sha=entry.exact_commit_sha,
                    license_spdx=entry.license_spdx,
                    selection_source=entry.selection_source,
                    coverage_role=role,
                    nomination_entry_digest=entry.entry_digest,
                    selection_evidence_digests=entry.selection_evidence_digests,
                )
                for entry, role in zip(
                    nomination_entries,
                    roles,
                    strict=True,
                )
            ),
            key=lambda item: item.entry_digest,
        )
    )
    manifest_values = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": nomination.nomination_set_digest,
        "entries": benchmark_entries,
        "prior_manifest_digest": None,
    }
    manifest_digest = sha256_digest(
        {
            **manifest_values,
            "entries": tuple(
                item.model_dump(mode="json", exclude_none=False)
                for item in benchmark_entries
            ),
        }
    )
    manifest = acceptance_domain.LockedBenchmarkManifestV1(
        **manifest_values,
        manifest_digest=manifest_digest,
        lock_attestation=acceptance_domain.BenchmarkLockAttestationV1(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=nomination.nomination_set_digest,
            manifest_digest=manifest_digest,
            reviewer_id="acceptance-reviewer",
            locked_at=timestamp,
        ),
    )
    query_path = tmp_path / "config" / "discovery-queries-v1.json"
    query_path.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "config/discovery-queries-v1.json", query_path)
    query_set = DiscoveryQuerySetV1.model_validate_json(
        query_path.read_bytes(),
        strict=True,
    )
    state_dir = tmp_path / "state" / "databases"
    state_dir.mkdir(parents=True)
    pipeline_path = state_dir / "pipeline.sqlite3"
    operations_path = state_dir / "operations.sqlite3"
    publication_path = state_dir / "publication.sqlite3"
    pipeline = pipeline_state.SQLiteStateStore(pipeline_path)
    publication = publication_state.PublicationStateStore(publication_path)
    try:
        frozen_publication = publication.export_owned_state()
    finally:
        publication.close()
        pipeline.close()

    authority = acceptance_domain.LiveAcceptanceAuthorityV1(
        schema_version="live-acceptance-authority-v1",
        authority_version=1,
        source_commit_sha="c" * 40,
        acceptance_workflow_sha256="sha256:" + ("d" * 64),
        manifest_path=(
            ".planning/phases/06-adversarial-mvp-acceptance/"
            "06-BENCHMARK-MANIFEST.json"
        ),
        manifest_digest=manifest.manifest_digest,
        nomination_set_digest=manifest.nomination_set_digest,
        lock_attestation_digest=manifest.lock_attestation.attestation_digest,
        state_commit_sha="e" * 40,
        state_root_digest="sha256:" + ("f" * 64),
        state_repository_id=123,
        state_repository_full_name="example/state",
        query_set_digest=query_set.query_set_digest,
        budget_policy_digest=(
            __import__(
                "skillscout.domain.discovery",
                fromlist=["DiscoveryBudgetPolicyV1"],
            )
            .DiscoveryBudgetPolicyV1()
            .budget_policy_digest
        ),
        semantic_provider="deepseek",
        provider_base_url="https://api.deepseek.com",
        stage_models=(
            "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ),
        prompt_versions=(
            "extract-prompt-v1",
            "generator-prompt-v1",
            "reviewer-prompt-v1",
        ),
        schema_versions=(
            "workflow-spec-v1",
            "generation-draft-v1",
            "reviewer-judgment-v1",
        ),
        policy_versions=(
            "discovery-budget-policy-v1",
            "extract-policy-v1",
            "generator-policy-v1",
            "qualification-policy-v1",
            "reader-policy-v1",
            "reviewer-policy-v1",
        ),
        max_candidates=100,
        max_semantic_candidates=20,
        max_semantic_requests=20,
        max_files_per_repository=25,
        max_source_files_per_repository=5,
        max_file_bytes=131_072,
        max_total_bytes_per_repository=524_288,
        max_tokens_per_repository=40_000,
        benchmark_scenario_write_count=5,
        replay_semantic_effect_count=0,
        replay_publication_effect_count=0,
        reviewer_id="acceptance-reviewer",
        approved_at=timestamp,
    )
    run_id = "acceptance-production-fixed-runner"
    with operations_state.OperationsStateStore(operations_path) as operations:
        operations.record_acceptance_fact(
            run_id, "acceptance_nomination", nomination
        )
        operations.record_acceptance_fact(
            run_id, "acceptance_benchmark_lock", manifest
        )
        operations.record_acceptance_fact(
            run_id, "acceptance_live_authority", authority
        )

    readme_sha = "aa01aa01aa01aa01aa01aa01aa01aa01aa01aa01"
    guide_sha = "bb02bb02bb02bb02bb02bb02bb02bb02bb02bb02"
    github_routes = {
        ("GET", "/repos/example/approved-repo"): recorded_fixture("repo_mit"),
        (
            "GET",
            f"/repos/example/approved-repo/commits/{pinned}",
        ): recorded_fixture("commits_pin"),
        (
            "GET",
            f"/repos/example/approved-repo/license?ref={pinned}",
        ): recorded_fixture("license_mit"),
        (
            "GET",
            f"/repos/example/approved-repo/git/trees/{pinned}?recursive=1",
        ): make_tree_fixture(
            [
                {
                    "path": "LICENSE",
                    "mode": "100644",
                    "type": "blob",
                    "sha": "bb12bb12bb12bb12bb12bb12bb12bb12bb12bb12",
                    "size": 1100,
                },
                {
                    "path": "README.md",
                    "mode": "100644",
                    "type": "blob",
                    "sha": readme_sha,
                    "size": 228,
                },
                {
                    "path": "docs/guide.md",
                    "mode": "100644",
                    "type": "blob",
                    "sha": guide_sha,
                    "size": 800,
                },
            ]
        ),
        (
            "GET",
            f"/repos/example/approved-repo/git/blobs/{readme_sha}",
        ): recorded_fixture("blob_readme"),
        (
            "GET",
            f"/repos/example/approved-repo/git/blobs/{guide_sha}",
        ): recorded_fixture("blob_doc"),
    }
    github_recording = RecordedTransport(github_routes)
    original_github = github_adapter.GitHubReadClient
    monkeypatch.setattr(
        github_adapter,
        "GitHubReadClient",
        lambda **kwargs: original_github(
            **kwargs,
            transport=github_recording.transport(),
            sleeper=lambda _delay: None,
        ),
    )

    def deepseek_response(
        content: str,
        *,
        model: str,
        request_id: str,
    ) -> RecordedResponse:
        return RecordedResponse(
            status=200,
            headers={"content-type": "application/json"},
            body=json.dumps(
                {
                    "id": request_id,
                    "object": "chat.completion",
                    "created": 1,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": content,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 40,
                        "completion_tokens": 20,
                        "total_tokens": 60,
                    },
                }
            ).encode(),
        )

    extractor_payload = json.loads(
        recorded_openai_fixture("parsed_2_workflows").body
    )["output"][0]["content"][0]["text"]
    generator_payload = json.loads(
        recorded_openai_generator_fixture("parsed_success").body
    )["output"][0]["content"][0]["text"]
    reviewer_cases = json.loads(
        (
            ROOT / "tests/fixtures/openai/reviewer/cases.json"
        ).read_bytes()
    )
    reviewer_payload = reviewer_cases["parsed_yes"]["body"]["output"][0][
        "content"
    ][0]["text"]
    original_extract = extract_adapter.OpenAIExtractionClient
    original_generate = generate_adapter.OpenAIGenerationClient
    original_review = review_adapter.OpenAIReviewClient
    semantic_recordings: list[RecordedTransport] = []

    def semantic_client(
        original: object,
        payload: str,
        response_model: str,
        request_id: str,
        **kwargs: object,
    ) -> object:
        recording = RecordedTransport(
            {
                ("POST", "/chat/completions"): deepseek_response(
                    payload,
                    model=response_model,
                    request_id=request_id,
                )
            }
        )
        semantic_recordings.append(recording)
        return original(  # type: ignore[operator]
            **kwargs,
            api_key="bounded-test-key",
            http_client=httpx.Client(transport=recording.transport()),
        )

    monkeypatch.setattr(
        extract_adapter,
        "OpenAIExtractionClient",
        lambda **kwargs: semantic_client(
            original_extract,
            extractor_payload,
            "deepseek-v4-flash",
            "chatcmpl-extractor-1",
            **kwargs,
        ),
    )
    monkeypatch.setattr(
        generate_adapter,
        "OpenAIGenerationClient",
        lambda **kwargs: semantic_client(
            original_generate,
            generator_payload,
            "deepseek-v4-flash",
            "chatcmpl-generator-1",
            **kwargs,
        ),
    )
    monkeypatch.setattr(
        review_adapter,
        "OpenAIReviewClient",
        lambda **kwargs: semantic_client(
            original_review,
            reviewer_payload,
            "deepseek-v4-pro",
            "chatcmpl-reviewer-1",
            **kwargs,
        ),
    )

    config = bootstrap.AcceptanceRuntimeConfig(
        manifest_path=(
            ROOT
            / ".planning/phases/06-adversarial-mvp-acceptance/"
            "06-BENCHMARK-MANIFEST.json"
        ),
        manifest=manifest,
        state_commit_sha=authority.state_commit_sha,
        state_root_digest=authority.state_root_digest,
        semantic_provider="deepseek",
        extractor_model_id="deepseek-v4-flash",
        generator_model_id="deepseek-v4-flash",
        reviewer_model_id="deepseek-v4-pro",
        live_acceptance_authority_digest=authority.authority_digest,
    )
    discovery_config = bootstrap.DiscoveryRuntimeConfig(
        state_repository_id=123,
        state_repository_full_name="example/state",
        state_ref="refs/heads/skillscout-state",
        query_set_path=query_path,
        query_set=query_set,
        query_set_digest=query_set.query_set_digest,
        pipeline_state=Path("state/databases/pipeline.sqlite3"),
        operations_state=Path("state/databases/operations.sqlite3"),
        publication_state=Path("state/databases/publication.sqlite3"),
        semantic_provider="deepseek",
        extractor_model_id="deepseek-v4-flash",
        generator_model_id="deepseek-v4-flash",
        reviewer_model_id="deepseek-v4-pro",
        initial_state_root_digest=authority.state_root_digest,
    )

    class LocalCAS:
        def __init__(self) -> None:
            self.ordinal = 0

        def sync_discovery(
            self,
            *,
            observed_head: str,
            **_kwargs: object,
        ) -> object:
            self.ordinal += 1
            return SimpleNamespace(
                status="verified",
                previous_head=observed_head,
                commit_sha=f"{self.ordinal:040x}",
                root_digest="sha256:" + f"{self.ordinal:064x}",
            )

        def confirm(self, *, transition: object, **_kwargs: object) -> object:
            self.ordinal += 1
            return DurabilityReceipt.from_remote_verification(
                transition=transition,
                verified_state_head=f"{self.ordinal:040x}",
                state_root_digest="sha256:" + f"{self.ordinal:064x}",
                pipeline_database_digest=sha256_digest(
                    {"pipeline": self.ordinal}
                ),
                operations_database_digest=sha256_digest(
                    {"operations": self.ordinal}
                ),
                publication_database_digest=sha256_digest(
                    {"publication": self.ordinal}
                ),
                pipeline_projection_digest=sha256_digest(
                    {"pipeline_projection": self.ordinal}
                ),
                operations_projection_digest=sha256_digest(
                    {"operations_projection": self.ordinal}
                ),
                publication_projection_digest=sha256_digest(
                    {"publication_projection": self.ordinal}
                ),
            )

    monkeypatch.chdir(tmp_path)
    cas = LocalCAS()
    runner = bootstrap._FixedRepositoryAcceptanceRunner(
        config=config,
        discovery_config=discovery_config,
        barrier=cas,
        source={
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "SKILLSCOUT_SOURCE_GITHUB_TOKEN": "bounded-test-token",
        },
        frozen_owner_export=frozen_publication,
        acceptance_run_id=run_id,
    )
    entry = next(
        item
        for item in manifest.entries
        if item.repository_full_name == "example/approved-repo"
    )
    try:
        observation = runner.run(
            acceptance_application.LiveRepositoryAuthority(
                repository_full_name=entry.repository_full_name,
                repository_id=entry.repository_id,
                exact_commit_sha=entry.exact_commit_sha,
                license_spdx=entry.license_spdx,
                nomination_entry_digest=entry.nomination_entry_digest,
                entry_digest=entry.entry_digest,
                selection_evidence_digests=entry.selection_evidence_digests,
            )
        )
    finally:
        runner.close()

    assert observation.outcome == "eligible_local_candidate"
    assert observation.live_acceptance_authority_digest == authority.authority_digest
    with operations_state.OperationsStateStore(operations_path) as operations:
        snapshot = operations.snapshot_run(f"{run_id}-semantic")
    assert tuple(item.stage for item in snapshot.semantic_attempts) == (
        "extractor",
        "generator",
        "reviewer",
    )
    assert tuple(item.outcome for item in snapshot.workflow_terminals) == (
        "eligible_local_candidate",
        "eligible_local_candidate",
    )
