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


def test_live_runner_persists_read_and_semantic_budget_before_remote_read() -> None:
    """Every fixed repository must consume its bounded slot before GitHub I/O."""

    import skillscout.bootstrap as bootstrap
    import skillscout.domain.acceptance as acceptance

    assert hasattr(acceptance, "AcceptanceBudgetReservationV1")
    source = inspect.getsource(bootstrap._FixedRepositoryAcceptanceRunner.run)
    reservation = source.index('"acceptance_budget_reservation"')
    remote_read = source.index("github = GitHubReadClient(")
    assert reservation < remote_read
