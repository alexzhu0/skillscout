"""Wave-0 RED mutation contracts for the independent Phase 6 rebuild verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
import shutil
import subprocess
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
            "--resume-proof",
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


def test_acceptance_runtime_loads_only_exact_resolver_proof(
    tmp_path: Path,
) -> None:
    import skillscout.bootstrap as bootstrap

    commit = "a" * 40
    root = "sha256:" + ("b" * 64)
    authority = "sha256:" + ("c" * 64)
    proof_path = tmp_path / "resume.json"
    proof = {
        "acceptance_run_id": "acceptance-proof",
        "authority_digest": authority,
        "lineage_commit_shas": [commit],
        "lineage_root_digests": [root],
        "locator_digest": None,
        "state_commit_sha": commit,
        "state_root_digest": root,
        "status": "acceptance_resume_verified",
    }
    proof_path.write_text(
        json.dumps(proof, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    environment = {
        "PHASE6_AUTHORITY_DIGEST": authority,
        "SKILLSCOUT_LLM_PROVIDER": "deepseek",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    }

    config = bootstrap.load_acceptance_runtime_config(
        manifest_path=(
            ROOT
            / ".planning/phases/06-adversarial-mvp-acceptance"
            / "06-BENCHMARK-MANIFEST.json"
        ),
        state_commit_sha=commit,
        state_root_digest=root,
        acceptance_run_id="acceptance-proof",
        resume_proof_path=proof_path,
        environ=environment,
    )

    assert config.resume_lineage_commit_shas == (commit,)
    assert config.resume_lineage_root_digests == (root,)
    proof["state_commit_sha"] = "d" * 40
    proof_path.write_text(
        json.dumps(proof, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="runtime configuration"):
        bootstrap.load_acceptance_runtime_config(
            manifest_path=config.manifest_path,
            state_commit_sha=commit,
            state_root_digest=root,
            acceptance_run_id="acceptance-proof",
            resume_proof_path=proof_path,
            environ=environment,
        )


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


def test_campaign_resume_locator_binds_exact_authority_and_descendant_lineage() -> None:
    """A resume pointer is a typed parent-state fact, not a mutable branch label."""

    from pydantic import ValidationError

    from skillscout.domain.canonical import sha256_digest
    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    values = {
        "schema_version": "acceptance-campaign-resume-locator-v1",
        "acceptance_run_id": "acceptance-resume",
        "live_acceptance_authority_digest": "sha256:" + ("1" * 64),
        "source_commit_sha": "2" * 40,
        "manifest_digest": "sha256:" + ("3" * 64),
        "state_repository_id": 123,
        "state_repository_full_name": "example/state",
        "original_state_commit_sha": "4" * 40,
        "original_state_root_digest": "sha256:" + ("5" * 64),
        "current_state_commit_sha": "6" * 40,
        "current_state_root_digest": "sha256:" + ("7" * 64),
        "semantic_provider": "deepseek",
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
        "lineage_commit_shas": ("4" * 40, "6" * 40),
        "lineage_root_digests": (
            "sha256:" + ("5" * 64),
            "sha256:" + ("7" * 64),
        ),
        "recorded_at": "2026-07-30T12:00:00.000000Z",
    }
    locator = AcceptanceCampaignResumeLocatorV1(**values)

    assert locator.locator_digest == sha256_digest(values)
    assert locator.current_state_commit_sha == locator.lineage_commit_shas[-1]
    assert locator.current_state_root_digest == locator.lineage_root_digests[-1]
    with pytest.raises(ValidationError):
        AcceptanceCampaignResumeLocatorV1(
            **{
                **values,
                "current_state_commit_sha": "8" * 40,
            }
        )
    with pytest.raises(ValidationError):
        AcceptanceCampaignResumeLocatorV1(
            **{
                **values,
                "live_acceptance_authority_digest": "sha256:" + ("9" * 64),
                "locator_digest": locator.locator_digest,
            }
        )


def test_acceptance_cli_exposes_only_exact_resume_lineage_inputs() -> None:
    """Workflow preflight resolves a descendant checkout without a mutable SHA var."""

    parser = _cli_subcommands()["resolve-acceptance-resume"]
    options = {
        option
        for action in parser._actions
        for option in action.option_strings
    }

    assert options == {
        "-h",
        "--help",
        "--authority-state-root",
        "--authority-state-root-digest",
        "--campaign-state-root",
        "--acceptance-run-id",
        "--authority-digest",
        "--source-commit-sha",
        "--state-repository-id",
        "--state-repository-full-name",
    }


def test_resolve_acceptance_resume_cli_dispatches_verified_locator(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    import skillscout.cli as cli

    expected = {
        "state_commit_sha": "a" * 40,
        "state_root_digest": "sha256:" + ("b" * 64),
        "locator_digest": "sha256:" + ("c" * 64),
        "status": "acceptance_resume_verified",
    }
    monkeypatch.setattr(
        cli,
        "_run_resolve_acceptance_resume",
        lambda _arguments: expected,
        raising=False,
    )

    assert (
        cli.main(
            [
                "resolve-acceptance-resume",
                "--authority-state-root",
                str(tmp_path),
                "--authority-state-root-digest",
                "sha256:" + ("d" * 64),
                "--campaign-state-root",
                str(tmp_path),
                "--acceptance-run-id",
                "acceptance-resume",
                "--authority-digest",
                "sha256:" + ("e" * 64),
                "--source-commit-sha",
                "f" * 40,
                "--state-repository-id",
                "123",
                "--state-repository-full-name",
                "example/state",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == expected


def test_resume_resolver_verifies_authority_before_reading_exact_branch_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import skillscout.adapters.state_branch as state_branch
    import skillscout.cli as cli
    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    original_commit = "4" * 40
    anchor_commit = "8" * 40
    original_root = "sha256:" + ("5" * 64)
    anchor_root = "sha256:" + ("9" * 64)
    authority_digest = "sha256:" + ("1" * 64)
    events: list[str] = []
    locator = AcceptanceCampaignResumeLocatorV1.model_construct(
        acceptance_run_id="acceptance-resume",
        live_acceptance_authority_digest=authority_digest,
        original_state_commit_sha=original_commit,
        original_state_root_digest=original_root,
        current_state_commit_sha=original_commit,
        lineage_commit_shas=(original_commit,),
        lineage_root_digests=(original_root,),
        locator_digest="sha256:" + ("a" * 64),
    )
    bundles = {
        original_commit: SimpleNamespace(
            root=SimpleNamespace(
                root_digest=original_root,
                state_parent_commit_sha="0" * 40,
                prior_root_digest="sha256:" + ("0" * 64),
            )
        ),
        anchor_commit: SimpleNamespace(
            root=SimpleNamespace(
                root_digest=anchor_root,
                state_parent_commit_sha=original_commit,
                prior_root_digest=original_root,
            )
        ),
    }

    class Reader:
        def __init__(self, **_kwargs: object) -> None:
            assert events == ["authority"]
            events.append("reader")

        def close(self) -> None:
            events.append("closed")

        def get_state_ref(self) -> object:
            return SimpleNamespace(sha=anchor_commit)

        def get_commit(self, sha: str) -> object:
            parent = (
                ("0" * 40,) if sha == original_commit else (original_commit,)
            )
            return SimpleNamespace(sha=sha, parents=parent)

    class Store:
        def __init__(self, _reader: object) -> None:
            pass

        def restore_commit(self, sha: str) -> object:
            return bundles[sha]

    monkeypatch.setattr(
        cli,
        "_load_verified_live_authority",
        lambda _arguments: events.append("authority")
        or SimpleNamespace(
            authority_digest=authority_digest,
            source_commit_sha="2" * 40,
            state_commit_sha=original_commit,
            state_root_digest=original_root,
            state_repository_id=123,
            state_repository_full_name="example/state",
        ),
        raising=False,
    )
    monkeypatch.setattr(state_branch, "StateBranchReadClient", Reader)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        cli,
        "_acceptance_resume_locators_from_bundle",
        lambda bundle, _run_id: (
            (locator,) if bundle is bundles[anchor_commit] else ()
        ),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "_checked_out_git_commit",
        lambda _path: anchor_commit,
    )
    monkeypatch.setattr(
        cli,
        "load_verified_state_checkout",
        lambda **_kwargs: bundles[anchor_commit],
    )
    monkeypatch.setenv("SKILLSCOUT_STATE_GITHUB_TOKEN", "fixture-token")

    result = cli._run_resolve_acceptance_resume(
        SimpleNamespace(
            authority_state_root=tmp_path,
            authority_state_root_digest=original_root,
            campaign_state_root=tmp_path,
            acceptance_run_id="acceptance-resume",
            authority_digest=authority_digest,
            source_commit_sha="2" * 40,
            state_repository_id=123,
            state_repository_full_name="example/state",
        )
    )

    assert result == {
        "authority_digest": authority_digest,
        "acceptance_run_id": "acceptance-resume",
        "lineage_commit_shas": [original_commit, anchor_commit],
        "lineage_root_digests": [original_root, anchor_root],
        "locator_digest": locator.locator_digest,
        "state_commit_sha": anchor_commit,
        "state_root_digest": anchor_root,
        "status": "acceptance_resume_verified",
    }
    assert events == ["authority", "reader", "closed"]


def test_resume_locator_is_recorded_before_cas_and_advances_exact_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import skillscout.bootstrap as bootstrap
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

    original_commit = "4" * 40
    anchor_commit = "8" * 40
    second_commit = "a" * 40
    original_root = "sha256:" + ("5" * 64)
    anchor_root = "sha256:" + ("9" * 64)
    second_root = "sha256:" + ("b" * 64)
    authority = LiveAcceptanceAuthorityV1.model_construct(
        authority_digest="sha256:" + ("1" * 64),
        source_commit_sha="2" * 40,
        manifest_digest="sha256:" + ("3" * 64),
        state_commit_sha=original_commit,
        state_root_digest=original_root,
        state_repository_id=123,
        state_repository_full_name="example/state",
        semantic_provider="deepseek",
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
    )
    recorded: list[object] = []
    synchronized = iter(
        (
            SimpleNamespace(
                status="verified",
                previous_head=original_commit,
                commit_sha=anchor_commit,
                root_digest=anchor_root,
            ),
            SimpleNamespace(
                status="verified",
                previous_head=anchor_commit,
                commit_sha=second_commit,
                root_digest=second_root,
            ),
        )
    )

    class Operations:
        def record_acceptance_fact(
            self, run_id: str, kind: str, fact: object
        ) -> object:
            assert run_id == "acceptance-resume"
            assert kind == "acceptance_campaign_resume_locator"
            recorded.append(fact)
            return object()

    barrier = object.__new__(bootstrap._LateStateDurabilityBarrier)
    monkeypatch.setattr(
        barrier,
        "sync_discovery",
        lambda **_kwargs: next(synchronized),
    )
    barrier.configure_acceptance_resume(
        authority=authority,
        acceptance_run_id="acceptance-resume",
        lineage_commit_shas=(original_commit,),
        lineage_root_digests=(original_root,),
    )

    first = barrier.anchor_acceptance_resume(
        operations_store=Operations(),
        observed_head=original_commit,
        prior_root_digest=original_root,
        created_at="2026-07-30T12:00:00.000000Z",
        pipeline_store=object(),
    )
    second = barrier.anchor_acceptance_resume(
        operations_store=Operations(),
        observed_head=anchor_commit,
        prior_root_digest=anchor_root,
        created_at="2026-07-30T12:01:00.000000Z",
        pipeline_store=object(),
    )

    assert first.commit_sha == anchor_commit
    assert second.commit_sha == second_commit
    assert [
        (
            item.current_state_commit_sha,
            item.current_state_root_digest,
            item.lineage_commit_shas,
            item.lineage_root_digests,
        )
        for item in recorded
    ] == [
        (
            original_commit,
            original_root,
            (original_commit,),
            (original_root,),
        ),
        (
            anchor_commit,
            anchor_root,
            (original_commit, anchor_commit),
            (original_root, anchor_root),
        ),
    ]


def test_resume_lineage_accepts_locator_anchor_and_bounded_crash_successor() -> None:
    """A locator anchor admits its verified commit or one verified crash suffix."""

    from dataclasses import replace

    from skillscout.application.acceptance import (
        CampaignStateLineageObservation,
        resolve_campaign_resume_lineage,
    )
    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    original_commit = "4" * 40
    current_commit = "6" * 40
    anchor_commit = "8" * 40
    crash_commit = "a" * 40
    original_root = "sha256:" + ("5" * 64)
    current_root = "sha256:" + ("7" * 64)
    anchor_root = "sha256:" + ("9" * 64)
    crash_root = "sha256:" + ("b" * 64)
    locator = AcceptanceCampaignResumeLocatorV1(
        schema_version="acceptance-campaign-resume-locator-v1",
        acceptance_run_id="acceptance-resume",
        live_acceptance_authority_digest="sha256:" + ("1" * 64),
        source_commit_sha="2" * 40,
        manifest_digest="sha256:" + ("3" * 64),
        state_repository_id=123,
        state_repository_full_name="example/state",
        original_state_commit_sha=original_commit,
        original_state_root_digest=original_root,
        current_state_commit_sha=current_commit,
        current_state_root_digest=current_root,
        semantic_provider="deepseek",
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
        lineage_commit_shas=(original_commit, current_commit),
        lineage_root_digests=(original_root, current_root),
        recorded_at="2026-07-30T12:00:00.000000Z",
    )
    observations = (
        CampaignStateLineageObservation(
            commit_sha=original_commit,
            root_digest=original_root,
            parent_commit_sha="0" * 40,
            prior_root_digest="sha256:" + ("0" * 64),
            resume_locators=(),
        ),
        CampaignStateLineageObservation(
            commit_sha=current_commit,
            root_digest=current_root,
            parent_commit_sha=original_commit,
            prior_root_digest=original_root,
            resume_locators=(),
        ),
        CampaignStateLineageObservation(
            commit_sha=anchor_commit,
            root_digest=anchor_root,
            parent_commit_sha=current_commit,
            prior_root_digest=current_root,
            resume_locators=(locator,),
        ),
    )

    anchored = resolve_campaign_resume_lineage(
        authority_digest=locator.live_acceptance_authority_digest,
        acceptance_run_id=locator.acceptance_run_id,
        original_state_commit_sha=original_commit,
        original_state_root_digest=original_root,
        campaign_head_commit_sha=anchor_commit,
        observations=observations,
    )
    crashed = resolve_campaign_resume_lineage(
        authority_digest=locator.live_acceptance_authority_digest,
        acceptance_run_id=locator.acceptance_run_id,
        original_state_commit_sha=original_commit,
        original_state_root_digest=original_root,
        campaign_head_commit_sha=crash_commit,
        observations=(
            *observations,
            CampaignStateLineageObservation(
                commit_sha=crash_commit,
                root_digest=crash_root,
                parent_commit_sha=anchor_commit,
                prior_root_digest=anchor_root,
                resume_locators=(locator,),
            ),
        ),
    )

    assert (anchored.state_commit_sha, anchored.state_root_digest) == (
        anchor_commit,
        anchor_root,
    )
    assert (crashed.state_commit_sha, crashed.state_root_digest) == (
        crash_commit,
        crash_root,
    )
    with pytest.raises(ValueError):
        resolve_campaign_resume_lineage(
            authority_digest="sha256:" + ("c" * 64),
            acceptance_run_id=locator.acceptance_run_id,
            original_state_commit_sha=original_commit,
            original_state_root_digest=original_root,
            campaign_head_commit_sha=anchor_commit,
            observations=observations,
        )
    with pytest.raises(ValueError):
        resolve_campaign_resume_lineage(
            authority_digest=locator.live_acceptance_authority_digest,
            acceptance_run_id=locator.acceptance_run_id,
            original_state_commit_sha=original_commit,
            original_state_root_digest=original_root,
            campaign_head_commit_sha=anchor_commit,
            observations=(
                *observations[:-1],
                replace(
                    observations[-1],
                    parent_commit_sha="d" * 40,
                ),
            ),
        )


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


def test_completed_projector_rejects_unverified_state_locator(
    tmp_path: Path,
) -> None:
    import skillscout.bootstrap as bootstrap
    from skillscout.application.acceptance import load_locked_benchmark_manifest

    manifest = load_locked_benchmark_manifest(
        ROOT
        / ".planning/phases/06-adversarial-mvp-acceptance"
        / "06-BENCHMARK-MANIFEST.json"
    )
    verified = {
        ("a" * 40, "sha256:" + ("b" * 64)),
    }
    projector = bootstrap._CompletedBenchmarkStateProjector(
        operations_path=tmp_path / "operations.sqlite3",
        pipeline_path=tmp_path / "pipeline.sqlite3",
        acceptance_run_id="acceptance-projector-locator",
        expected_live_authority_digest="sha256:" + ("9" * 64),
        verified_state_locators=verified,
    )

    with pytest.raises(ValueError, match="state locator"):
        projector.project(
            manifest=manifest,
            state_commit_sha="c" * 40,
            state_root_digest="sha256:" + ("d" * 64),
        )


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


def test_production_replay_rejects_synthetic_scenarios_without_terminal_graph(
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
        state_commit_sha="d" * 40,
        state_root_digest="sha256:" + ("c" * 64),
        state_repository_id=123,
        state_repository_full_name="example/state",
        query_set_digest=nomination.query_set_digest,
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

    def telemetry(
        stage: str,
        authority_digest: str,
        request_suffix: str,
    ) -> object:
        return acceptance_domain.AcceptanceSemanticTelemetryV1(
            schema_version="acceptance-semantic-telemetry-v1",
            live_acceptance_authority_digest=authority.authority_digest,
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
        operations.record_acceptance_fact(
            run_id, "acceptance_live_authority", authority
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
            scenario = acceptance_domain.AcceptanceScenarioResultV1(
                    schema_version="acceptance-scenario-result-v1",
                    acceptance_run_id=run_id,
                    scenario_id=f"locked-{ordinal}-{entry.repository_id}",
                    repository_id=entry.repository_id,
                    repository_full_name=entry.repository_full_name,
                    exact_commit_sha=entry.exact_commit_sha,
                    license_spdx=entry.license_spdx,
                    benchmark_manifest_digest=manifest.manifest_digest,
                    benchmark_entry_digest=entry.entry_digest,
                    live_acceptance_authority_digest=authority.authority_digest,
                    discovery_run_id=f"{run_id}-semantic",
                    discovery_run_authority_digest=entry.entry_digest,
                    budget_reservation_digest=entry.entry_digest,
                    fixed_candidate_admission_digest=admission.admission_digest,
                    semantic_candidate_reservation_digest=entry.entry_digest,
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
                    semantic_request_reservation_digests=attempt_digests,
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
                    workflow_execution_authority_digests=(
                        (entry.entry_digest,) if eligible else ()
                    ),
                    workflow_spec_authority_digests=(
                        (entry.entry_digest,) if eligible else ()
                    ),
                    candidate_terminal_digest=entry.entry_digest,
                    workflow_terminal_digests=(
                        (entry.entry_digest,) if eligible else ()
                    ),
                    phase3_terminal_summary_digests=(
                        (entry.entry_digest,) if eligible else ()
                    ),
                    skill_artifact_digests=(
                        (entry.entry_digest,) if eligible else ()
                    ),
                    package_digests=(
                        (entry.entry_digest,) if eligible else ()
                    ),
                    eligible_locator=(
                        "state/objects/eligible.json" if eligible else None
                    ),
                    eligible_object_digest=(
                        entry.entry_digest if eligible else None
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
            )
            with pytest.raises(
                operations_state.OperationsIntegrityError,
                match="scenario budget or admission binding",
            ):
                operations.record_acceptance_fact(
                    run_id,
                    "acceptance_scenario",
                    scenario,
                )
            return
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
        live_acceptance_authority_digest=authority.authority_digest,
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
    with pytest.raises(ValueError, match="typed Phase 3"):
        execution.run()


def test_live_runner_persists_read_and_semantic_budget_before_remote_read() -> None:
    """Every fixed repository must consume its bounded slot before GitHub I/O."""

    import skillscout.bootstrap as bootstrap
    import skillscout.domain.acceptance as acceptance

    assert hasattr(acceptance, "AcceptanceBudgetReservationV1")
    source = inspect.getsource(bootstrap._FixedRepositoryAcceptanceRunner.run)
    reservation = source.index('"acceptance_budget_reservation"')
    remote_read = source.index("github = GitHubReadClient(")
    assert reservation < remote_read


def test_fixed_runner_exhausts_only_after_three_same_authority_retries() -> None:
    """Confirmed retries consume the exact policy budget without a fourth call."""

    import skillscout.bootstrap as bootstrap

    calls: list[dict[str, object]] = []
    retryable = SimpleNamespace(
        terminal=SimpleNamespace(outcome="confirmed_retryable"),
        state_commit_sha="b" * 40,
        state_root_digest="sha256:" + ("c" * 64),
    )
    runner = object.__new__(bootstrap._FixedRepositoryAcceptanceRunner)
    runner._state_head = "a" * 40
    runner._state_root = "sha256:" + ("b" * 64)
    runner._authority = SimpleNamespace(run_id="acceptance-retry-semantic")
    runner._operations = SimpleNamespace(
        snapshot_run=lambda _run_id: SimpleNamespace(
            semantic_attempts=(),
            semantic_reservations=(),
            candidate_terminals=(),
        )
    )
    runner._barrier = object()
    runner._phase3_factory = object()

    def factory(**kwargs: object) -> object:
        calls.append(kwargs)
        return retryable

    runner._phase2_factory = factory
    result = runner._run_phase2_with_retries(
        candidate=SimpleNamespace(
            repository=SimpleNamespace(repository_id=101)
        ),
        pinned_commit_sha="d" * 40,
    )

    assert result is retryable
    assert len(calls) == 3
    assert all(call["candidate"] is calls[0]["candidate"] for call in calls)
    assert tuple(call["observed_head"] for call in calls) == (
        "a" * 40,
        "b" * 40,
        "b" * 40,
    )


@pytest.mark.parametrize(
    ("durable_attempts", "remaining_calls"),
    ((1, 2), (2, 1)),
)
def test_fixed_runner_resumes_only_remaining_same_authority_attempts(
    durable_attempts: int,
    remaining_calls: int,
) -> None:
    """A restarted process cannot receive a fresh three-call retry budget."""

    import skillscout.bootstrap as bootstrap

    phase2_authority = "sha256:" + ("a" * 64)
    attempts = tuple(
        SimpleNamespace(
            repository_id=101,
            workflow_authority_digest=phase2_authority,
            stage="extractor",
            attempt_no=attempt_no,
            status="confirmed_retryable",
        )
        for attempt_no in range(1, durable_attempts + 1)
    )
    runner = object.__new__(bootstrap._FixedRepositoryAcceptanceRunner)
    runner._state_head = "a" * 40
    runner._state_root = "sha256:" + ("b" * 64)
    runner._authority = SimpleNamespace(run_id="acceptance-resume-semantic")
    runner._operations = SimpleNamespace(
        snapshot_run=lambda _run_id: SimpleNamespace(
            semantic_attempts=attempts,
            semantic_reservations=(
                SimpleNamespace(
                    repository_id=101,
                    phase2_run_authority_digest=phase2_authority,
                ),
            ),
            candidate_terminals=(),
        )
    )
    runner._barrier = object()
    runner._phase3_factory = object()
    calls = 0
    retryable = SimpleNamespace(
        terminal=SimpleNamespace(outcome="confirmed_retryable"),
        state_commit_sha="b" * 40,
        state_root_digest="sha256:" + ("c" * 64),
    )

    def factory(**_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return retryable

    runner._phase2_factory = factory
    candidate = SimpleNamespace(
        repository=SimpleNamespace(repository_id=101)
    )
    result = runner._run_phase2_with_retries(
        candidate=candidate,
        pinned_commit_sha="d" * 40,
    )

    assert result is retryable
    assert calls == remaining_calls


def test_fixed_runner_does_not_issue_fourth_request_after_durable_exhaustion() -> None:
    """Three durable retry attempts are terminal across process restarts."""

    import skillscout.bootstrap as bootstrap
    from skillscout.domain.discovery import DiscoveryCandidateTerminalV1

    phase2_authority = "sha256:" + ("a" * 64)
    terminal = DiscoveryCandidateTerminalV1.model_construct(
        schema_version="discovery-candidate-terminal-v1",
        discovery_run_authority_digest="sha256:" + ("b" * 64),
        repository_id=101,
        semantic_reservation_digest="sha256:" + ("c" * 64),
        outcome="confirmed_retryable",
        workflow_authority_digests=(),
        recorded_at="2026-07-27T12:00:00.000000Z",
        terminal_digest="sha256:" + ("d" * 64),
    )
    runner = object.__new__(bootstrap._FixedRepositoryAcceptanceRunner)
    runner._state_head = "a" * 40
    runner._state_root = "sha256:" + ("b" * 64)
    runner._authority = SimpleNamespace(run_id="acceptance-exhausted-semantic")
    runner._operations = SimpleNamespace(
        snapshot_run=lambda _run_id: SimpleNamespace(
            semantic_attempts=tuple(
                SimpleNamespace(
                    repository_id=101,
                    workflow_authority_digest=phase2_authority,
                    stage="extractor",
                    attempt_no=attempt_no,
                )
                for attempt_no in range(1, 4)
            ),
            semantic_reservations=(
                SimpleNamespace(
                    repository_id=101,
                    phase2_run_authority_digest=phase2_authority,
                ),
            ),
            candidate_terminals=(terminal,),
        )
    )
    runner._barrier = object()
    runner._phase3_factory = object()

    recovery_calls = 0

    def recovery_factory(**kwargs: object) -> object:
        nonlocal recovery_calls
        recovery_calls += 1
        assert kwargs["recovery_only"] is True
        return SimpleNamespace(
            terminal=terminal,
            eligible_candidates=(),
            state_commit_sha=runner._state_head,
            state_root_digest=runner._state_root,
            acceptance_system_outcome="provider_exhausted",
        )

    runner._phase2_factory = recovery_factory
    result = runner._run_phase2_with_retries(
        candidate=SimpleNamespace(
            repository=SimpleNamespace(repository_id=101)
        ),
        pinned_commit_sha="e" * 40,
    )

    assert result.terminal is terminal
    assert result.acceptance_system_outcome == "provider_exhausted"
    assert recovery_calls == 1


@pytest.mark.parametrize(
    ("attempt_status", "has_preexisting_terminal"),
    (
        ("decided", False),
        ("confirmed_retryable", False),
        ("semantic_outcome_unknown", False),
        ("confirmed_retryable", True),
    ),
)
def test_fixed_runner_reconstructs_three_attempt_crash_without_provider_replay(
    attempt_status: str,
    has_preexisting_terminal: bool,
) -> None:
    """A durable third result must be projected, never granted a fourth request."""

    import skillscout.bootstrap as bootstrap

    phase2_authority = "sha256:" + ("a" * 64)
    preexisting = SimpleNamespace(
        repository_id=101,
        outcome="confirmed_retryable",
    )
    recovered = SimpleNamespace(
        terminal=SimpleNamespace(outcome=attempt_status),
        state_commit_sha="c" * 40,
        state_root_digest="sha256:" + ("d" * 64),
    )
    runner = object.__new__(bootstrap._FixedRepositoryAcceptanceRunner)
    runner._state_head = "b" * 40
    runner._state_root = "sha256:" + ("c" * 64)
    runner._authority = SimpleNamespace(run_id="acceptance-crash-recovery-semantic")
    runner._operations = SimpleNamespace(
        snapshot_run=lambda _run_id: SimpleNamespace(
            semantic_attempts=tuple(
                SimpleNamespace(
                    repository_id=101,
                    workflow_authority_digest=phase2_authority,
                    stage="extractor",
                    attempt_no=attempt_no,
                    status=attempt_status if attempt_no == 3 else "confirmed_retryable",
                )
                for attempt_no in range(1, 4)
            ),
            semantic_reservations=(
                SimpleNamespace(
                    repository_id=101,
                    phase2_run_authority_digest=phase2_authority,
                ),
            ),
            candidate_terminals=(preexisting,) if has_preexisting_terminal else (),
        )
    )
    runner._barrier = object()
    runner._phase3_factory = object()
    calls: list[dict[str, object]] = []

    def recover_factory(**kwargs: object) -> object:
        calls.append(kwargs)
        if kwargs.get("recovery_only") is not True:
            raise AssertionError("third-attempt recovery was allowed provider authority")
        return recovered

    runner._phase2_factory = recover_factory
    result = runner._run_phase2_with_retries(
        candidate=SimpleNamespace(
            repository=SimpleNamespace(repository_id=101)
        ),
        pinned_commit_sha="e" * 40,
    )

    assert result is recovered
    assert len(calls) == 1


@pytest.mark.parametrize(
    "third_status",
    ("decided", "confirmed_retryable", "semantic_outcome_unknown"),
)
def test_third_attempt_crash_recovers_across_real_sqlite_process_restart(
    tmp_path: Path,
    third_status: str,
) -> None:
    """A new process reopens exact stores and cannot issue request four."""

    operations_path = tmp_path / "operations.sqlite3"
    pipeline_path = tmp_path / "pipeline.sqlite3"
    request_count_path = tmp_path / "provider-request-count"
    recovery_path = tmp_path / "recovery-result.json"
    setup = r"""
import sqlite3
import sys
from pathlib import Path

from skillscout.adapters.operations_state import OperationsStateStore
from skillscout.adapters.state import SQLiteStateStore
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.discovery import DiscoveryRunAuthorityV1, SemanticReservationV1

operations_path = Path(sys.argv[1])
pipeline_path = Path(sys.argv[2])
request_count_path = Path(sys.argv[3])
third_status = sys.argv[4]
run_id = "acceptance-process-restart-semantic"
repository_id = 101
phase2_authority = "sha256:" + ("a" * 64)
timestamp = "2026-07-30T12:00:00.000000Z"
values = {
    "schema_version": "discovery-run-authority-v1",
    "run_id": run_id,
    "query_set_digest": "sha256:" + ("1" * 64),
    "budget_policy_digest": "sha256:" + ("2" * 64),
    "phase2_profile_version": "phase2-v1",
    "phase3_profile_version": "phase3-profile-v1",
    "semantic_provider": "deepseek",
    "extractor_model_id": "deepseek-v4-flash",
    "generator_model_id": "deepseek-v4-flash",
    "reviewer_model_id": "deepseek-v4-pro",
    "initial_state_root_digest": "sha256:" + ("3" * 64),
}
authority = DiscoveryRunAuthorityV1(
    **values,
    authority_digest=sha256_digest(values),
)
store = OperationsStateStore(operations_path)
store.create_run(authority, timestamp)
store.close()
reservation_values = {
    "schema_version": "semantic-reservation-v1",
    "discovery_run_authority_digest": authority.authority_digest,
    "repository_id": repository_id,
    "ordinal": 1,
    "discovery_reservation_digest": "sha256:" + ("4" * 64),
    "phase2_run_authority_digest": phase2_authority,
    "reserved_at": timestamp,
}
reservation = SemanticReservationV1(
    **reservation_values,
    reservation_digest=sha256_digest(reservation_values),
)
with sqlite3.connect(operations_path) as connection:
    connection.execute(
        "INSERT INTO operations_semantic_reservations "
        "(reservation_digest, run_id, repository_id, ordinal, "
        "discovery_reservation_digest, phase2_run_authority_digest, "
        "reservation_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            reservation.reservation_digest,
            run_id,
            repository_id,
            reservation.ordinal,
            reservation.discovery_reservation_digest,
            reservation.phase2_run_authority_digest,
            canonical_json_bytes(reservation).decode("utf-8"),
        ),
    )
pipeline = SQLiteStateStore(pipeline_path)
pipeline.close()
store = OperationsStateStore(operations_path)
for attempt_no in range(1, 4):
    store.record_semantic_attempt(
        run_id=run_id,
        repository_id=repository_id,
        workflow_authority_digest=phase2_authority,
        stage="extractor",
        attempt_no=attempt_no,
        status="started",
        recorded_at=timestamp,
    )
    store.record_semantic_attempt(
        run_id=run_id,
        repository_id=repository_id,
        workflow_authority_digest=phase2_authority,
        stage="extractor",
        attempt_no=attempt_no,
        status=third_status if attempt_no == 3 else "confirmed_retryable",
        recorded_at=timestamp,
    )
store.close()
request_count_path.write_text("3", encoding="ascii")
"""
    recover = r"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from skillscout.adapters.operations_state import OperationsStateStore
from skillscout.adapters.state import SQLiteStateStore
from skillscout.bootstrap import _FixedRepositoryAcceptanceRunner

operations_path = Path(sys.argv[1])
pipeline_path = Path(sys.argv[2])
request_count_path = Path(sys.argv[3])
recovery_path = Path(sys.argv[4])
store = OperationsStateStore(operations_path)
pipeline = SQLiteStateStore(pipeline_path)
runner = object.__new__(_FixedRepositoryAcceptanceRunner)
runner._state_head = "b" * 40
runner._state_root = "sha256:" + ("c" * 64)
runner._authority = SimpleNamespace(run_id="acceptance-process-restart-semantic")
runner._operations = store
runner._barrier = object()
runner._phase3_factory = object()
calls = []
def recovery_factory(**kwargs):
    calls.append(kwargs)
    if kwargs.get("recovery_only") is not True:
        raise AssertionError("provider replay was granted after durable attempt three")
    return SimpleNamespace(
        terminal=SimpleNamespace(outcome="recovered"),
        state_commit_sha=runner._state_head,
        state_root_digest=runner._state_root,
    )
runner._phase2_factory = recovery_factory
result = runner._run_phase2_with_retries(
    candidate=SimpleNamespace(repository=SimpleNamespace(repository_id=101)),
    pinned_commit_sha="e" * 40,
)
snapshot = store.snapshot_run(runner._authority.run_id)
recovery_path.write_text(
    json.dumps(
        {
            "attempt_count": len(snapshot.semantic_attempts),
            "provider_request_count": int(request_count_path.read_text(encoding="ascii")),
            "recovery_only_calls": len(calls),
            "result": result.terminal.outcome,
        },
        sort_keys=True,
    ),
    encoding="utf-8",
)
pipeline.close()
store.close()
"""
    first = subprocess.run(
        [
            sys.executable,
            "-c",
            setup,
            str(operations_path),
            str(pipeline_path),
            str(request_count_path),
            third_status,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    second = subprocess.run(
        [
            sys.executable,
            "-c",
            recover,
            str(operations_path),
            str(pipeline_path),
            str(request_count_path),
            str(recovery_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, second.stderr
    assert json.loads(recovery_path.read_text(encoding="utf-8")) == {
        "attempt_count": 3,
        "provider_request_count": 3,
        "recovery_only_calls": 1,
        "result": "recovered",
    }


@pytest.mark.parametrize(
    "terminal_outcome",
    ("semantic_outcome_unknown", "completed_reuse"),
)
def test_fixed_runner_never_replays_unknown_or_completed_phase2(
    terminal_outcome: str,
) -> None:
    """Unknown transport and completed lookup are both terminal for the caller."""

    import skillscout.bootstrap as bootstrap

    calls = 0
    terminal = SimpleNamespace(
        terminal=SimpleNamespace(outcome=terminal_outcome),
        state_commit_sha="b" * 40,
        state_root_digest="sha256:" + ("c" * 64),
    )
    runner = object.__new__(bootstrap._FixedRepositoryAcceptanceRunner)
    runner._state_head = "a" * 40
    runner._state_root = "sha256:" + ("b" * 64)
    runner._authority = SimpleNamespace(run_id="acceptance-terminal-semantic")
    runner._operations = SimpleNamespace(
        snapshot_run=lambda _run_id: SimpleNamespace(
            semantic_attempts=(),
            semantic_reservations=(),
            candidate_terminals=(),
        )
    )
    runner._barrier = object()
    runner._phase3_factory = object()

    def factory(**_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return terminal

    runner._phase2_factory = factory
    assert (
        runner._run_phase2_with_retries(
            candidate=SimpleNamespace(
                repository=SimpleNamespace(repository_id=101)
            ),
            pinned_commit_sha="d" * 40,
        )
        is terminal
    )
    assert calls == 1


def test_production_five_repo_benchmark_restores_and_replays_without_live_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run five real local Phase 2/3 chains, restore the bundle, then replay."""

    from dataclasses import replace

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
    def response_with_json(
        response: RecordedResponse,
        values: dict[str, object],
    ) -> RecordedResponse:
        return RecordedResponse(
            status=response.status,
            headers=response.headers,
            body=json.dumps(values).encode(),
        )

    github_routes: dict[tuple[str, str], RecordedResponse] = {}
    for benchmark_entry in manifest.entries:
        owner, repository_name = (
            benchmark_entry.repository_full_name.split("/")
        )
        metadata = json.loads(recorded_fixture("repo_mit").body)
        metadata.update(
            {
                "id": benchmark_entry.repository_id,
                "name": repository_name,
                "full_name": benchmark_entry.repository_full_name,
            }
        )
        commit = json.loads(recorded_fixture("commits_pin").body)
        commit["sha"] = benchmark_entry.exact_commit_sha
        license_payload = json.loads(recorded_fixture("license_mit").body)
        license_payload["url"] = (
            f"https://api.github.com/repos/{owner}/{repository_name}/"
            f"contents/LICENSE?ref={benchmark_entry.exact_commit_sha}"
        )
        github_routes[
            ("GET", f"/repos/{owner}/{repository_name}")
        ] = response_with_json(recorded_fixture("repo_mit"), metadata)
        github_routes[
            (
                "GET",
                f"/repos/{owner}/{repository_name}/commits/"
                f"{benchmark_entry.exact_commit_sha}",
            )
        ] = response_with_json(recorded_fixture("commits_pin"), commit)
        github_routes[
            (
                "GET",
                f"/repos/{owner}/{repository_name}/license?"
                f"ref={benchmark_entry.exact_commit_sha}",
            )
        ] = response_with_json(recorded_fixture("license_mit"), license_payload)
        github_routes[
            (
                "GET",
                f"/repos/{owner}/{repository_name}/git/trees/"
                f"{benchmark_entry.exact_commit_sha}?recursive=1",
            )
        ] = make_tree_fixture(
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
        )
        github_routes[
            (
                "GET",
                f"/repos/{owner}/{repository_name}/git/blobs/{readme_sha}",
            )
        ] = recorded_fixture("blob_readme")
        github_routes[
            (
                "GET",
                f"/repos/{owner}/{repository_name}/git/blobs/{guide_sha}",
            )
        ] = recorded_fixture("blob_doc")
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
    extractor_constructions = 0

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

    def extractor_client(**kwargs: object) -> object:
        nonlocal extractor_constructions
        extractor_constructions += 1
        if extractor_constructions == 1:
            recording = RecordedTransport(
                {
                    ("POST", "/chat/completions"): recorded_openai_fixture(
                        "openai_429"
                    )
                }
            )
            semantic_recordings.append(recording)
            return original_extract(
                **kwargs,
                api_key="bounded-test-key",
                http_client=httpx.Client(transport=recording.transport()),
            )
        return semantic_client(
            original_extract,
            extractor_payload,
            "deepseek-v4-flash",
            "chatcmpl-extractor-2",
            **kwargs,
        )

    monkeypatch.setattr(
        extract_adapter,
        "OpenAIExtractionClient",
        extractor_client,
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
    def discovery_factory(
        state_commit_sha: str,
        state_root_digest: str,
    ) -> object:
        return bootstrap._FixedRepositoryAcceptanceRunner(
            config=replace(
                config,
                state_commit_sha=state_commit_sha,
                state_root_digest=state_root_digest,
            ),
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

    benchmark = acceptance_application.run_locked_benchmark(
        acceptance_application.LockedCampaignDependencies(
            discovery_factory=discovery_factory,
            operations_store_factory=lambda: (
                operations_state.OperationsStateStore(operations_path)
            ),
            state_sync=cas.sync_discovery,
        ),
        manifest=manifest,
        acceptance_run_id=run_id,
        observed_head=authority.state_commit_sha,
        prior_root_digest=authority.state_root_digest,
        recorded_at=timestamp,
    )
    entry = next(
        item
        for item in manifest.entries
        if item.repository_full_name == "example/approved-repo"
    )
    observation = next(
        item
        for item in benchmark.scenario_results
        if item.repository_id == entry.repository_id
    )

    assert observation.outcome == "eligible_local_candidate"
    assert observation.live_acceptance_authority_digest == authority.authority_digest
    assert len(benchmark.scenario_results) == 5
    assert extractor_constructions == 6
    with operations_state.OperationsStateStore(operations_path) as operations:
        snapshot = operations.snapshot_run(f"{run_id}-semantic")
        acceptance_snapshot = operations.acceptance_snapshot(run_id)
    assert {item.stage for item in snapshot.semantic_attempts} == {
        "extractor",
        "generator",
        "reviewer",
    }
    assert {item.outcome for item in snapshot.workflow_terminals} == {
        "eligible_local_candidate",
        "qualification_rejected",
    }
    extractor_attempts = tuple(
        item
        for item in snapshot.semantic_attempts
        if item.stage == "extractor"
    )
    assert sum(
        item.status == "confirmed_retryable"
        for item in extractor_attempts
    ) == 1
    assert sum(item.status == "decided" for item in extractor_attempts) == 5
    assert {
        item.repository_id for item in extractor_attempts
    } == {item.repository_id for item in manifest.entries}
    linked_digests = {
        authority.authority_digest,
        manifest.manifest_digest,
        entry.nomination_entry_digest,
        entry.entry_digest,
        *(
            item.reservation_digest
            for item in snapshot.semantic_reservations
            if item.repository_id == entry.repository_id
        ),
        *(
            item.attempt_digest
            for item in snapshot.semantic_attempts
            if item.repository_id == entry.repository_id
        ),
        *(
            item.terminal_digest
            for item in snapshot.workflow_terminals
            if item.repository_id == entry.repository_id
        ),
        *(
            item.terminal_digest
            for item in snapshot.candidate_terminals
            if item.repository_id == entry.repository_id
        ),
        *(
            record.fact_digest
            for record in acceptance_snapshot.facts
            if record.kind
            in {
                "acceptance_budget_reservation",
                "acceptance_fixed_candidate_admission",
                "acceptance_semantic_request_reservation",
            }
            and getattr(record.fact, "repository_id", None) == entry.repository_id
        ),
    }
    assert linked_digests.issubset(observation.evidence_digests)

    pipeline = pipeline_state.SQLiteStateStore(pipeline_path)
    operations = operations_state.OperationsStateStore(operations_path)
    publication = publication_state.PublicationStateStore(publication_path)
    try:
        bundle = operations_state.assemble_three_store_bundle(
            pipeline_store=pipeline,
            operations_store=operations,
            publication_store=publication,
            prior_root_digest=benchmark.state_root_digest,
            state_parent_commit_sha=benchmark.state_commit_sha,
            query_set_digest=query_set.query_set_digest,
            budget_policy_digest=authority.budget_policy_digest,
            created_at=timestamp,
        )
    finally:
        publication.close()
        operations.close()
        pipeline.close()
    restored_dir = tmp_path / "restored" / "state" / "databases"
    restored_dir.mkdir(parents=True)
    restored_pipeline_path = restored_dir / "pipeline.sqlite3"
    restored_operations_path = restored_dir / "operations.sqlite3"
    operations_state.restore_acceptance_state_bundle(
        bundle,
        pipeline_path=restored_pipeline_path,
        operations_path=restored_operations_path,
    )

    def forbidden_live_capability(
        *_args: object,
        **_kwargs: object,
    ) -> object:
        pytest.fail("replay constructed a live or publication capability")

    monkeypatch.setattr(github_adapter, "GitHubReadClient", forbidden_live_capability)
    monkeypatch.setattr(
        extract_adapter,
        "OpenAIExtractionClient",
        forbidden_live_capability,
    )
    monkeypatch.setattr(
        generate_adapter,
        "OpenAIGenerationClient",
        forbidden_live_capability,
    )
    monkeypatch.setattr(
        review_adapter,
        "OpenAIReviewClient",
        forbidden_live_capability,
    )
    monkeypatch.setattr(
        publication_state,
        "PublicationStateStore",
        forbidden_live_capability,
    )
    monkeypatch.setattr(
        operations_state,
        "PublicationStateStore",
        forbidden_live_capability,
    )

    replay_initial_head = "a" * 40
    replay_initial_root = bundle.root.root_digest
    verified_state_locators = {
        (replay_initial_head, replay_initial_root),
    }
    replay_sync_ordinal = 0

    def replay_sync(*, observed_head: str, **_kwargs: object) -> object:
        nonlocal replay_sync_ordinal
        replay_sync_ordinal += 1
        commit_sha = f"{900 + replay_sync_ordinal:040x}"
        root_digest = "sha256:" + f"{900 + replay_sync_ordinal:064x}"
        verified_state_locators.add((commit_sha, root_digest))
        return SimpleNamespace(
            status="verified",
            previous_head=observed_head,
            commit_sha=commit_sha,
            root_digest=root_digest,
        )

    def projector_factory() -> object:
        return bootstrap._CompletedBenchmarkStateProjector(
            operations_path=restored_operations_path,
            pipeline_path=restored_pipeline_path,
            acceptance_run_id=run_id,
            expected_live_authority_digest=authority.authority_digest,
            verified_state_locators=verified_state_locators,
        )

    replay = acceptance_application.run_exact_replay(
        acceptance_application.ReplayUpdateDependencies(
            completed_projector_factory=projector_factory,
            operations_store_factory=lambda: (
                operations_state.OperationsStateStore(
                    restored_operations_path
                )
            ),
            state_sync=replay_sync,
        ),
        manifest=manifest,
        acceptance_run_id=run_id,
        state_commit_sha=replay_initial_head,
        state_root_digest=replay_initial_root,
        recorded_at="2026-07-30T12:00:01.000000Z",
    )

    assert replay.semantic_request_count == 0
    assert replay.remote_effect_count == 0
    assert replay.duplicate_workflow_spec_count == 0
    assert replay.duplicate_skill_count == 0
    assert replay.duplicate_fact_count == 0


@pytest.mark.parametrize(
    ("outcome", "reason"),
    (
        ("schema_exhausted", "provider_schema_exhausted"),
        ("provider_exhausted", "provider_attempts_exhausted"),
        ("evidence_missing", "state_integrity_conflict"),
        ("harness_failed", "pipeline_permanent_failure"),
    ),
)
def test_acceptance_system_reason_is_derived_from_normalized_outcome(
    outcome: str,
    reason: str,
) -> None:
    import skillscout.bootstrap as bootstrap

    assert bootstrap._acceptance_reason_code(outcome) == reason
