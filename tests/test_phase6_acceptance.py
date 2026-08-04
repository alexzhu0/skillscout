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
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "tools/verify_phase6_acceptance.py"
VALIDATION_PATH = ROOT / ".planning/phases/06-adversarial-mvp-acceptance/06-VALIDATION.md"
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
    tracked = subprocess.run(
        ("git", "ls-files", "-z"),
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    for encoded in tracked:
        if not encoded:
            continue
        relative = Path(encoded.decode("utf-8"))
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    subprocess.run(("git", "init", "-q"), cwd=repository, check=True)
    return repository


def _replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    assert source.count(old) == 1, (path, old)
    path.write_text(source.replace(old, new), encoding="utf-8")


def _mutate_acceptance_repository(repository: Path, mutation: str) -> None:
    phase = repository / ".planning/phases/06-adversarial-mvp-acceptance"
    if mutation == "missing_evidence":
        (phase / "06-BENCHMARK-MANIFEST.json").unlink()
    elif mutation == "swapped_evidence":
        discover = repository / ".github/workflows/discover.yml"
        publish = repository / ".github/workflows/publish-candidate.yml"
        discover_bytes = discover.read_bytes()
        discover.write_bytes(publish.read_bytes())
        publish.write_bytes(discover_bytes)
    elif mutation == "duplicate_evidence":
        validation = phase / "06-VALIDATION.md"
        source = validation.read_text(encoding="utf-8")
        row = next(line for line in source.splitlines() if line.startswith("| 06-01-01 |"))
        marker = "\n## Requirement Inverse Coverage"
        assert source.count(marker) == 1
        validation.write_text(
            source.replace(marker, f"\n{row}{marker}"),
            encoding="utf-8",
        )
    elif mutation == "stale_evidence":
        state = repository / ".planning/STATE.md"
        _replace_once(
            state,
            "7eca32de7c0468d18c180ebecf567d7239412e54c2776e43621930b894570f63",
            "0" * 64,
        )
    elif mutation == "self_referential_evidence":
        manifest = phase / "06-BENCHMARK-MANIFEST.json"
        payload = json.loads(manifest.read_bytes())
        payload["prior_manifest_digest"] = payload["manifest_digest"]
        manifest.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="ascii",
        )
    elif mutation == "identical_replay_effect":
        _replace_once(
            repository / "src/skillscout/domain/acceptance.py",
            "replay_semantic_effect_count: Literal[0]",
            "replay_semantic_effect_count: Literal[1]",
        )
    elif mutation == "changed_lineage_alias":
        _replace_once(
            repository / "src/skillscout/adapters/operations_state.py",
            '"acceptance_changed_source_draft_update_completion": {\n'
            '        "changed-source-draft-update-completion-v1": '
            "ChangedSourceDraftUpdateCompletionV1,\n"
            "    },",
            '"acceptance_changed_source": {\n'
            '        "changed-source-draft-update-completion-v1": '
            "ChangedSourceDraftUpdateCompletionV1,\n"
            "    },",
        )
    elif mutation == "stale_gate_b4":
        _replace_once(
            repository / ".planning/STATE.md",
            "Gate B4 evidence remains historical",
            "Gate B4 evidence is current",
        )
    elif mutation == "stale_draft_head":
        path = repository / "src/skillscout/domain/acceptance.py"
        source = path.read_text(encoding="utf-8")
        before, marker, after = source.partition("class HumanSkillReviewAttestationV1")
        assert marker and "pr_head_sha: _Sha" in after
        path.write_text(
            before + marker + after.replace("pr_head_sha: _Sha", "pr_head_sha: str", 1),
            encoding="utf-8",
        )
    elif mutation == "hard_gate_deleted":
        _replace_once(
            repository / "src/skillscout/domain/acceptance.py",
            '    "fresh_gate_b4_binding",\n',
            "",
        )
    elif mutation == "all_44_inverse_drift":
        validation = phase / "06-VALIDATION.md"
        source = validation.read_text(encoding="utf-8")
        _replace_once(
            validation,
            next(line for line in source.splitlines() if line.startswith("| TEST-01 |")),
            "| TEST-01 | 06-01-01 |",
        )
    elif mutation == "benchmark_lock_mismatch":
        manifest = phase / "06-BENCHMARK-MANIFEST.json"
        payload = bytearray(manifest.read_bytes())
        index = payload.index(b'"entry_digest":"sha256:') + len(b'"entry_digest":"sha256:')
        payload[index] = ord("0") if payload[index] != ord("0") else ord("1")
        manifest.write_bytes(payload)
    elif mutation == "benchmark_lock_environment_branch_policy_missing":
        _replace_once(
            phase / "06-16-PLAN.md",
            "require reviewer `alexzhu0`, restrict deployment branches to the protected "
            "default branch `main` only, leave Prevent self-review disabled",
            "require reviewer `alexzhu0`, leave Prevent self-review disabled",
        )
    elif mutation == "benchmark_lock_validation_branch_policy_missing":
        _replace_once(
            phase / "06-VALIDATION.md",
            "configure `phase6-human-benchmark-lock` with required reviewer "
            "`alexzhu0`, selected deployment branch `main` only, Prevent self-review "
            "disabled for the sole reviewer",
            "configure `phase6-human-benchmark-lock` with required reviewer "
            "`alexzhu0`, Prevent self-review disabled for the sole reviewer",
        )
    else:
        raise AssertionError(mutation)


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
        "benchmark_lock_mismatch",
        "benchmark_lock_environment_branch_policy_missing",
        "benchmark_lock_validation_branch_policy_missing",
    ),
)
def test_independent_verifier_rejects_whole_phase_evidence_mutation(
    acceptance_repository: Path,
    mutation: str,
) -> None:
    verifier = _repository_verifier()
    _mutate_acceptance_repository(acceptance_repository, mutation)
    error = sys.modules[verifier.__module__].AcceptanceError
    with pytest.raises(error):
        verifier(acceptance_repository)


def test_independent_verifier_accepts_complete_current_repository_contract(
    acceptance_repository: Path,
) -> None:
    verifier = _repository_verifier()
    assert tuple(inspect.signature(verifier).parameters) == ("repository_root",)
    result = verifier(acceptance_repository)

    assert result.status == "repository_contract_valid_acceptance_incomplete"
    assert result.structural_valid is True
    assert result.acceptance_complete is False
    assert result.plan_count == 18
    assert result.task_count == 47
    assert result.requirement_count == 44


@pytest.mark.parametrize(
    "relative",
    (
        "src/skillscout/application/pipeline.py",
        "src/skillscout/application/phase3.py",
        "src/skillscout/adapters/openai_extract.py",
        "src/skillscout/adapters/openai_generate.py",
        "src/skillscout/adapters/openai_review.py",
        "src/skillscout/adapters/semantic_provider.py",
    ),
)
def test_independent_verifier_requires_complete_semantic_execution_surface(
    acceptance_repository: Path,
    relative: str,
) -> None:
    """Dropping any semantic execution owner must invalidate the repository."""

    verifier = _repository_verifier()
    error = sys.modules[verifier.__module__].AcceptanceError
    (acceptance_repository / relative).unlink()

    with pytest.raises(error):
        verifier(acceptance_repository)


@pytest.mark.parametrize(
    "relative",
    (
        "tools/verify_phase6_validation_map.py",
        "tools/verify_phase6_source_execution.py",
    ),
)
def test_independent_verifier_parses_but_never_executes_repository_helpers(
    acceptance_repository: Path,
    relative: str,
) -> None:
    """Repository-owned helper top-level code must receive no verifier authority."""

    verifier = _repository_verifier()
    helper = acceptance_repository / relative
    helper.write_text(
        helper.read_text(encoding="utf-8")
        + '\nraise RuntimeError("repository helper was executed")\n',
        encoding="utf-8",
    )

    result = verifier(acceptance_repository)

    assert result.structural_valid is True
    assert result.acceptance_complete is False


def test_independent_verifier_rejects_symlinked_parent_and_root_escape(
    acceptance_repository: Path,
    tmp_path: Path,
) -> None:
    verifier = _repository_verifier()
    error = sys.modules[verifier.__module__].AcceptanceError
    real_planning = acceptance_repository / ".planning"
    moved_planning = tmp_path / "moved-planning"
    real_planning.rename(moved_planning)
    real_planning.symlink_to(moved_planning, target_is_directory=True)
    with pytest.raises(error):
        verifier(acceptance_repository)

    escaped = tmp_path / "escaped"
    escaped.symlink_to(acceptance_repository, target_is_directory=True)
    with pytest.raises(error):
        verifier(escaped)


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
    assert not (
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance/06-ACCEPTANCE-REPORT.md"
    ).exists()
    assert not (
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance/06-RELEASE-REQUIREMENTS.json"
    ).exists()


def test_default_verifier_cli_runs_repository_verification_before_incomplete(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The default command must run the independent repository contract."""

    module = _verifier()
    observed: list[Path] = []

    def verify_repository(repository_root: Path) -> Any:
        observed.append(repository_root)
        return module.RepositoryVerification(
            status="repository_contract_valid_acceptance_incomplete",
            structural_valid=True,
            acceptance_complete=False,
            plan_count=18,
            task_count=47,
            requirement_count=44,
            source_execution_step_count=1,
            missing_live_artifacts=(
                "06-ACCEPTANCE-REPORT.md",
                "06-RELEASE-REQUIREMENTS.json",
            ),
        )

    monkeypatch.setattr(module, "verify_repository", verify_repository)

    assert module.main([]) == 1
    assert observed == [Path.cwd()]
    assert capsys.readouterr().err == module.INCOMPLETE + "\n"


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
    path = ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-RELEASE-REQUIREMENTS.json"
    if not path.exists():
        pytest.skip("phase6-release-requirement-map-not-yet-built")
    raw = path.read_bytes()
    payload = json.loads(raw)
    assert raw == (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("ascii")
    assert len(payload["requirements"]) == 44
    assert set(payload["requirements"]) == set(payload["inverse_requirement_map"])


def _cli_subcommands() -> dict[str, Any]:
    from skillscout.cli import build_parser

    parser = build_parser()
    action = next(
        item for item in parser._actions if item.__class__.__name__ == "_SubParsersAction"
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
        "verify-live-authority-state": {
            "--authority",
            "--source-commit-sha",
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
        options = {option for action in commands[name]._actions for option in action.option_strings}
        assert required <= options
        assert forbidden.isdisjoint(options)
    kind = next(
        action
        for action in commands["record-acceptance-attestation"]._actions
        if "--kind" in action.option_strings
    )
    assert tuple(kind.choices) == ("human-review", "probe-cleanup")
    acceptance_action = next(
        action
        for action in commands["run-acceptance"]._actions
        if "--action" in action.option_strings
    )
    assert tuple(acceptance_action.choices) == ("benchmark", "replay")


def _fresh_lock_inputs() -> tuple[object, object, object]:
    """Return one fresh Search-only nomination, its static V1 selection, and a snapshot."""

    from skillscout.adapters.operations_state import AcceptanceFactRecord, AcceptanceRunSnapshot
    from skillscout.domain.acceptance import (
        BenchmarkEntryV1,
        BenchmarkLockAttestationV1,
        LockedBenchmarkManifestV1,
        NominationEntryV1,
        NominationSetV1,
    )
    from skillscout.domain.canonical import sha256_digest

    roles = ("positive", "positive_multi_workflow", "negative", "negative", "borderline")
    nominations = tuple(
        NominationEntryV1(
            schema_version="nomination-entry-v1",
            repository_full_name=f"octo-org/fresh-{index}",
            repository_id=930000 + index,
            exact_commit_sha=f"{index:040x}",
            license_spdx="MIT",
            selection_source="search_derived",
            selection_evidence_digests=(sha256_digest({"fresh-evidence": index}),),
        )
        for index in range(1, 6)
    )
    nomination = NominationSetV1(
        schema_version="nomination-set-v1",
        nomination_set_id="fresh-campaign",
        query_set_digest=sha256_digest({"query": "fresh"}),
        search_run_authority_digest=sha256_digest({"authority": "fresh"}),
        search_derived_entries=tuple(sorted(nominations, key=lambda item: item.entry_digest)),
        user_nominated_entries=(),
        created_at="2026-08-02T00:00:00.000000Z",
    )
    entries = tuple(
        sorted(
            (
                BenchmarkEntryV1(
                    schema_version="benchmark-entry-v1",
                    repository_full_name=entry.repository_full_name,
                    repository_id=entry.repository_id,
                    exact_commit_sha=entry.exact_commit_sha,
                    license_spdx=entry.license_spdx,
                    selection_source="search_derived",
                    coverage_role=role,
                    nomination_entry_digest=entry.entry_digest,
                    selection_evidence_digests=entry.selection_evidence_digests,
                )
                for entry, role in zip(nomination.search_derived_entries, roles, strict=True)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    preimage = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": nomination.nomination_set_digest,
        "entries": [item.model_dump(mode="json", exclude_none=False) for item in entries],
        "prior_manifest_digest": None,
    }
    manifest_digest = sha256_digest(preimage)
    manifest = LockedBenchmarkManifestV1(
        **preimage,
        lock_attestation=BenchmarkLockAttestationV1(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=nomination.nomination_set_digest,
            manifest_digest=manifest_digest,
            reviewer_id="historical-selection",
            locked_at="2026-08-02T00:00:00.000000Z",
        ),
        manifest_digest=manifest_digest,
    )
    snapshot = AcceptanceRunSnapshot(
        acceptance_run_id=nomination.nomination_set_id,
        facts=(
            AcceptanceFactRecord(
                acceptance_run_id=nomination.nomination_set_id,
                kind="acceptance_nomination",
                fact_digest=nomination.nomination_set_digest,
                fact=nomination,
            ),
        ),
    )
    return nomination, manifest, snapshot


def _fresh_lock_receipt() -> object:
    from skillscout.domain.acceptance import BenchmarkLockApprovalReceiptV2
    from skillscout.domain.canonical import sha256_digest

    return BenchmarkLockApprovalReceiptV2(
        schema_version="benchmark-lock-approval-receipt-v2",
        purpose="benchmark_lock",
        environment="phase6-human-benchmark-lock",
        source_repository_id=1_310_897_029,
        source_repository_full_name="alexzhu0/skillscout",
        reviewer_login="alexzhu0",
        reviewer_id=101,
        workflow_run_id=1001,
        workflow_run_attempt=1,
        source_commit_sha="a" * 40,
        workflow_sha256=sha256_digest({"workflow": "fresh-lock"}),
        trigger_identity="workflow_dispatch:42:alexzhu0",
        approval_record_digest=sha256_digest({"approval": "redacted"}),
    )


def _fresh_lock_handoff(*, manifest: object, receipt: object) -> object:
    from skillscout.domain.acceptance import FreshBenchmarkLockHandoffV1

    return FreshBenchmarkLockHandoffV1(
        schema_version="fresh-benchmark-lock-handoff-v1",
        source_repository_id=1310897029,
        source_repository_full_name="alexzhu0/skillscout",
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        source_commit_sha=getattr(receipt, "source_commit_sha"),
        acceptance_workflow_sha256=getattr(receipt, "workflow_sha256"),
        workflow_run_id=getattr(receipt, "workflow_run_id"),
        workflow_run_attempt=getattr(receipt, "workflow_run_attempt"),
        trigger_identity=getattr(receipt, "trigger_identity"),
        selection_manifest=manifest,
        approval_receipt=receipt,
    )


def _fresh_live_authority_admission_inputs() -> tuple[object, object, object]:
    """Build a rebuilt V2 lock/authority snapshot and its exact carrier lineage."""

    from skillscout.adapters.operations_state import AcceptanceFactRecord, AcceptanceRunSnapshot
    from skillscout.application import acceptance as application
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV2, LiveExecutionApprovalReceiptV2

    nomination, manifest, snapshot = _fresh_lock_inputs()
    receipt = _fresh_lock_receipt()
    lock = application.bind_fresh_benchmark_lock(
        snapshot=snapshot,
        selection_manifest=manifest,
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        parent_state_commit_sha="b" * 40,
        parent_state_root_digest="sha256:" + ("c" * 64),
        expected_nomination_authority_digest=nomination.search_run_authority_digest,
        approval_receipt=receipt,
    )
    approval = LiveExecutionApprovalReceiptV2(
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
    authority = LiveAcceptanceAuthorityV2(
        schema_version="live-acceptance-authority-v2",
        authority_version=2,
        purpose="live_execution",
        benchmark_lock_digest=lock.lock_digest,
        benchmark_lock=lock,
        source_repository_id=lock.source_repository_id,
        source_repository_full_name=lock.source_repository_full_name,
        state_repository_id=lock.state_repository_id,
        state_repository_full_name=lock.state_repository_full_name,
        parent_state_commit_sha=lock.parent_state_commit_sha,
        parent_state_root_digest=lock.parent_state_root_digest,
        state_commit_sha="c" * 40,
        state_root_digest="sha256:" + ("d" * 64),
        source_commit_sha=lock.source_commit_sha,
        acceptance_workflow_sha256=lock.acceptance_workflow_sha256,
        source_state_binding_digest=lock.source_state_binding_digest,
        manifest_path=(
            ".planning/phases/06-adversarial-mvp-acceptance/"
            "06-BENCHMARK-MANIFEST.json"
        ),
        manifest_digest=lock.selection_manifest_digest,
        selection_manifest_digest=lock.selection_manifest_digest,
        nomination_set_digest=lock.nomination_set_digest,
        lock_attestation_digest=lock.selection_manifest.lock_attestation.attestation_digest,
        entries=lock.entries,
        environment="skillscout-phase6-live-authority",
        approved_reviewer_login=approval.reviewer_login,
        approved_reviewer_id=approval.reviewer_id,
        workflow_run_id=approval.workflow_run_id,
        workflow_run_attempt=approval.workflow_run_attempt,
        trigger_identity=approval.trigger_identity,
        approval_record_digest=approval.approval_record_digest,
        approval_receipt=approval,
        approval_receipt_digest=approval.receipt_digest,
        query_set_digest="sha256:" + ("6" * 64),
        budget_policy_digest="sha256:" + ("7" * 64),
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
        approved_at="2026-08-02T00:30:00.000000Z",
    )
    rebuilt = AcceptanceRunSnapshot(
        acceptance_run_id=nomination.nomination_set_id,
        facts=(
            *snapshot.facts,
            AcceptanceFactRecord(
                acceptance_run_id=nomination.nomination_set_id,
                kind="acceptance_benchmark_lock",
                fact_digest=lock.lock_digest,
                fact=lock,
            ),
            AcceptanceFactRecord(
                acceptance_run_id=nomination.nomination_set_id,
                kind="acceptance_live_authority",
                fact_digest=authority.authority_digest,
                fact=authority,
            ),
        ),
    )
    observation = application.LiveAuthorityStateObservation(
        state_repository_id=lock.state_repository_id,
        state_repository_full_name=lock.state_repository_full_name,
        authority_carrier_commit_sha="d" * 40,
        authority_carrier_root_digest="sha256:" + ("e" * 64),
        authority_carrier_parent_commit_sha=authority.state_commit_sha,
        authority_carrier_prior_root_digest=authority.state_root_digest,
        lock_state_parent_commit_sha=lock.parent_state_commit_sha,
        lock_state_prior_root_digest=lock.parent_state_root_digest,
    )
    return rebuilt, authority, observation


def test_live_admission_v2_rebuilds_complete_chain_before_capability_factory() -> None:
    from skillscout.application import acceptance as application

    snapshot, authority, observation = _fresh_live_authority_admission_inputs()
    constructed: list[object] = []

    admission = application.admit_live_execution_v2(
        snapshot=snapshot,
        authority_digest=authority.authority_digest,
        state_observation=observation,
        capability_factory=lambda value: constructed.append(value) or value,
    )

    assert admission.authority == authority
    assert admission.lock == authority.benchmark_lock
    assert admission.nomination.nomination_set_digest == authority.nomination_set_digest
    assert constructed == [admission]


@pytest.mark.parametrize(
    "mutation",
    (
        "legacy_authority",
        "stale_carrier_parent",
        "stale_lock_parent",
        "selection_chain",
        "receipt_reuse",
    ),
)
def test_live_admission_v2_rejects_invalid_chain_with_zero_credential_effect(
    mutation: str,
) -> None:
    from skillscout.adapters.operations_state import AcceptanceFactRecord, AcceptanceRunSnapshot
    from skillscout.application import acceptance as application
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

    snapshot, authority, observation = _fresh_live_authority_admission_inputs()
    if mutation == "legacy_authority":
        legacy = LiveAcceptanceAuthorityV1.model_construct(
            schema_version="live-acceptance-authority-v1",
            authority_digest=authority.authority_digest,
        )
        snapshot = AcceptanceRunSnapshot(
            acceptance_run_id=snapshot.acceptance_run_id,
            facts=tuple(
                AcceptanceFactRecord(
                    acceptance_run_id=record.acceptance_run_id,
                    kind=record.kind,
                    fact_digest=record.fact_digest,
                    fact=(legacy if record.kind == "acceptance_live_authority" else record.fact),
                )
                for record in snapshot.facts
            ),
        )
    elif mutation == "stale_carrier_parent":
        observation = replace(observation, authority_carrier_parent_commit_sha="f" * 40)
    elif mutation == "stale_lock_parent":
        observation = replace(observation, lock_state_parent_commit_sha="f" * 40)
    elif mutation == "selection_chain":
        forged = authority.model_copy(update={"entries": tuple(reversed(authority.entries))})
        snapshot = AcceptanceRunSnapshot(
            acceptance_run_id=snapshot.acceptance_run_id,
            facts=tuple(
                AcceptanceFactRecord(
                    acceptance_run_id=record.acceptance_run_id,
                    kind=record.kind,
                    fact_digest=record.fact_digest,
                    fact=(forged if record.kind == "acceptance_live_authority" else record.fact),
                )
                for record in snapshot.facts
            ),
        )
    elif mutation == "receipt_reuse":
        forged = authority.model_copy(
            update={"approval_receipt": authority.benchmark_lock.approval_receipt}
        )
        snapshot = AcceptanceRunSnapshot(
            acceptance_run_id=snapshot.acceptance_run_id,
            facts=tuple(
                AcceptanceFactRecord(
                    acceptance_run_id=record.acceptance_run_id,
                    kind=record.kind,
                    fact_digest=record.fact_digest,
                    fact=(forged if record.kind == "acceptance_live_authority" else record.fact),
                )
                for record in snapshot.facts
            ),
        )
    else:
        raise AssertionError(mutation)

    effects: list[object] = []
    with pytest.raises(application.AcceptanceApplicationError, match="evidence_missing"):
        application.admit_live_execution_v2(
            snapshot=snapshot,
            authority_digest=authority.authority_digest,
            state_observation=observation,
            capability_factory=lambda value: effects.append(value),
        )
    assert effects == []


def test_live_admission_v2_has_no_actor_comment_or_caller_authority_channel() -> None:
    from skillscout.application import acceptance as application

    signature = inspect.signature(application.admit_live_execution_v2)
    assert {"actor", "comment", "authority_json", "approval_receipt"}.isdisjoint(
        signature.parameters
    )


def test_prepare_and_lock_fresh_campaign_cli_routes_have_no_caller_authority() -> None:
    commands = _cli_subcommands()
    forbidden = {
        "--state-repository-id",
        "--state-repository-full-name",
        "--initial-state-root-digest",
        "--manifest",
        "--reviewer",
        "--approval",
        "--token",
        "--endpoint",
        "--source",
        "--workflow",
    }
    for name in (
        "prepare-fresh-campaign",
        "prepare-fresh-lock-handoff",
        "lock-fresh-campaign",
    ):
        options = {
            option
            for action in commands[name]._actions
            for option in action.option_strings
            if option not in {"-h", "--help"}
        }
        assert options == set()
        assert forbidden.isdisjoint(options)


def test_fresh_campaign_lock_source_context_requires_repository_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The protected source handoff starts with Actions' numeric repository identity."""

    from skillscout import cli

    environment = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY_ID": "1310897029",
        "GITHUB_REPOSITORY": "alexzhu0/skillscout",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "1001",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR_ID": "42",
        "GITHUB_ACTOR": "alexzhu0",
        "GITHUB_TRIGGERING_ACTOR": "alexzhu0",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    assert cli._fresh_campaign_lock_source_context() == (
        1_310_897_029,
        "alexzhu0/skillscout",
        "a" * 40,
        1001,
        1,
        "workflow_dispatch:42:alexzhu0",
    )

    monkeypatch.setenv("GITHUB_REPOSITORY_ID", "0")
    with pytest.raises(ValueError, match="fresh campaign source context rejected"):
        cli._fresh_campaign_lock_source_context()


def test_fresh_benchmark_lock_rebinds_static_v1_manifest_to_current_nomination() -> None:
    from skillscout.application import acceptance as application
    from skillscout.domain.acceptance import BenchmarkEntryV1

    nomination, manifest, snapshot = _fresh_lock_inputs()
    receipt = _fresh_lock_receipt()
    lock = application.bind_fresh_benchmark_lock(
        snapshot=snapshot,
        selection_manifest=manifest,
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        parent_state_commit_sha="b" * 40,
        parent_state_root_digest="sha256:" + ("c" * 64),
        expected_nomination_authority_digest=nomination.search_run_authority_digest,
        approval_receipt=receipt,
    )
    assert lock.selection_manifest_digest == manifest.manifest_digest
    assert lock.nomination_set_digest == nomination.nomination_set_digest
    assert lock.entries == manifest.entries

    changed = BenchmarkEntryV1(
        schema_version="benchmark-entry-v1",
        repository_full_name=manifest.entries[0].repository_full_name,
        repository_id=manifest.entries[0].repository_id,
        exact_commit_sha="f" * 40,
        license_spdx=manifest.entries[0].license_spdx,
        selection_source=manifest.entries[0].selection_source,
        coverage_role=manifest.entries[0].coverage_role,
        nomination_entry_digest=manifest.entries[0].nomination_entry_digest,
        selection_evidence_digests=manifest.entries[0].selection_evidence_digests,
    )
    altered_entries = tuple(
        sorted((changed, *manifest.entries[1:]), key=lambda item: item.entry_digest)
    )
    from skillscout.domain.acceptance import BenchmarkLockAttestationV1, LockedBenchmarkManifestV1
    from skillscout.domain.canonical import sha256_digest

    altered_preimage = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": manifest.nomination_set_digest,
        "entries": [item.model_dump(mode="json", exclude_none=False) for item in altered_entries],
        "prior_manifest_digest": None,
    }
    altered_digest = sha256_digest(altered_preimage)
    altered = LockedBenchmarkManifestV1(
        **altered_preimage,
        lock_attestation=BenchmarkLockAttestationV1(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=manifest.nomination_set_digest,
            manifest_digest=altered_digest,
            reviewer_id="historical-selection",
            locked_at="2026-08-02T00:00:00.000000Z",
        ),
        manifest_digest=altered_digest,
    )
    with pytest.raises(application.AcceptanceApplicationError, match="evidence_missing"):
        application.bind_fresh_benchmark_lock(
            snapshot=snapshot,
            selection_manifest=altered,
            state_repository_id=9001,
            state_repository_full_name="octo-org/skillscout-state",
            parent_state_commit_sha="b" * 40,
            parent_state_root_digest="sha256:" + ("c" * 64),
            expected_nomination_authority_digest=nomination.search_run_authority_digest,
            approval_receipt=receipt,
        )


def test_fresh_lock_rejects_invalid_handoff_before_opening_late_state_capability() -> None:
    from skillscout.application import acceptance as application

    nomination, _manifest, _snapshot = _fresh_lock_inputs()
    calls: list[str] = []

    def malformed_handoff() -> object:
        calls.append("handoff")
        return object()

    dependencies = application.FreshCampaignLockDependencies(
        handoff_factory=malformed_handoff,
        state_restore=lambda: pytest.fail("state capability opened before approval"),
        operations_store_factory=lambda: pytest.fail("operations store opened before approval"),
        durability_barrier=object(),
    )
    application_instance = application.FreshCampaignLockApplication(
        dependencies,
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        source_repository_id=1_310_897_029,
        source_repository_full_name="alexzhu0/skillscout",
        query_set_digest=nomination.query_set_digest,
    )
    with pytest.raises(application.AcceptanceApplicationError, match="evidence_missing"):
        application_instance.run(created_at="2026-08-02T00:00:00.000000Z")
    assert calls == ["handoff"]


def test_fresh_lock_rejects_mismatched_source_identity_before_opening_state() -> None:
    """The state-only side must re-admit both source repository identity fields."""

    from skillscout.application import acceptance as application

    nomination, manifest, _snapshot = _fresh_lock_inputs()
    handoff = _fresh_lock_handoff(manifest=manifest, receipt=_fresh_lock_receipt())
    dependencies = application.FreshCampaignLockDependencies(
        handoff_factory=lambda: handoff,
        state_restore=lambda: pytest.fail("state capability opened for wrong source"),
        operations_store_factory=lambda: pytest.fail("store opened for wrong source"),
        durability_barrier=object(),
    )
    application_instance = application.FreshCampaignLockApplication(
        dependencies,
        state_repository_id=9001,
        state_repository_full_name="octo-org/skillscout-state",
        source_repository_id=1_310_897_030,
        source_repository_full_name="alexzhu0/skillscout",
        query_set_digest=nomination.query_set_digest,
    )

    with pytest.raises(application.AcceptanceApplicationError, match="evidence_missing"):
        application_instance.run(created_at="2026-08-02T00:00:00.000000Z")


def test_fixed_host_approval_reader_redacts_documented_top_level_array() -> None:
    from skillscout.adapters.github import GitHubReadClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == httpx.URL(
            "https://api.github.com/repos/octo-org/skillscout/actions/runs/1001/approvals"
        )
        return httpx.Response(
            200,
            json=[
                {
                    "user": {"login": "alexzhu0", "id": 101},
                    "state": "approved",
                    "environments": [{"id": 1, "name": "phase6-human-benchmark-lock"}],
                    "comment": "untrusted comment that must not persist",
                }
            ],
            request=request,
        )

    client = GitHubReadClient(transport=httpx.MockTransport(handler), sleeper=lambda _delay: None)
    try:
        approvals = client.get_workflow_run_approvals(
            "octo-org",
            "skillscout",
            1001,
        )
    finally:
        client.close()
    assert len(approvals) == 1
    approval = approvals[0]
    assert approval.environment == "phase6-human-benchmark-lock"
    assert approval.reviewer_login == "alexzhu0"
    assert approval.reviewer_id == 101
    assert {"comment", "raw_response", "endpoint"}.isdisjoint(
        type(approval).model_fields
    )


@pytest.mark.parametrize(
    "payload_patch",
    (
        {},
        {"run_attempt": 2},
    ),
)
def test_fixed_host_run_attempt_reader_requires_exact_attempt_metadata(
    payload_patch: dict[str, object],
) -> None:
    from skillscout.adapters.github import GitHubReadClient
    from skillscout.application.ports import SafeFailure

    payload: dict[str, object] = {
        "id": 1001,
        "run_attempt": 1,
        "head_sha": "a" * 40,
        "event": "workflow_dispatch",
        "path": ".github/workflows/phase6-acceptance.yml@main",
        "actor": {"login": "alexzhu0", "id": 42},
        "triggering_actor": {"login": "alexzhu0", "id": 42},
    }
    payload.update(payload_patch)
    if not payload_patch:
        payload.pop("triggering_actor")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(
            "https://api.github.com/repos/octo-org/skillscout/actions/runs/1001/attempts/1"
        )
        return httpx.Response(200, json=payload, request=request)

    client = GitHubReadClient(transport=httpx.MockTransport(handler), sleeper=lambda _delay: None)
    try:
        with pytest.raises(SafeFailure):
            client.get_workflow_run_attempt("octo-org", "skillscout", 1001, 1)
    finally:
        client.close()


def test_fixed_host_run_attempt_reader_retains_only_needed_identity_facts() -> None:
    from skillscout.adapters.github import GitHubReadClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 1001,
                "run_attempt": 1,
                "head_sha": "a" * 40,
                "event": "workflow_dispatch",
                "path": ".github/workflows/phase6-acceptance.yml@main",
                "actor": {"login": "alexzhu0", "id": 42},
                "triggering_actor": {"login": "alexzhu0", "id": 42},
                "display_title": "untrusted title",
            },
            request=request,
        )

    client = GitHubReadClient(transport=httpx.MockTransport(handler), sleeper=lambda _delay: None)
    try:
        metadata = client.get_workflow_run_attempt("octo-org", "skillscout", 1001, 1)
    finally:
        client.close()
    assert metadata.workflow_path == ".github/workflows/phase6-acceptance.yml@main"
    assert metadata.actor_id == metadata.triggering_actor_id == 42
    assert metadata.actor_login == metadata.triggering_actor_login == "alexzhu0"
    assert {"display_title", "raw_response", "endpoint"}.isdisjoint(type(metadata).model_fields)


@pytest.mark.parametrize(
    ("workflow_path", "expected"),
    (
        (".github/workflows/phase6-acceptance.yml", True),
        (".github/workflows/phase6-acceptance.yml@main", True),
        (".github/workflows/phase6-acceptance.yml@refs/heads/main", True),
        (".github/workflows/phase6-acceptance.yml@" + ("a" * 200), True),
        (".github/workflows/phase6-acceptance.yml@", False),
        (".github/workflows/phase6-acceptance.yml@" + ("a" * 201), False),
        (".github/workflows/phase6-acceptance.yml@main?override", False),
        (".github/workflows/phase6-acceptance.yml/other", False),
        (".github/workflows/other.yml", False),
        ("phase6-acceptance.yml", False),
        (None, False),
    ),
)
def test_fresh_campaign_workflow_path_allows_only_exact_path_with_optional_ref(
    workflow_path: object,
    expected: bool,
) -> None:
    from skillscout.bootstrap import _is_fresh_campaign_workflow_path

    assert _is_fresh_campaign_workflow_path(workflow_path) is expected


def test_acceptance_runtime_loads_only_exact_resolver_proof(
    tmp_path: Path,
) -> None:
    import skillscout.bootstrap as bootstrap

    original_commit = "d" * 40
    original_root = "sha256:" + ("e" * 64)
    carrier_commit = "c" * 40
    carrier_root = "sha256:" + ("d" * 64)
    commit = "a" * 40
    root = "sha256:" + ("b" * 64)
    authority = "sha256:" + ("c" * 64)
    proof_path = tmp_path / "resume.json"
    proof = {
        "acceptance_run_id": "acceptance-proof",
        "authority_digest": authority,
        "lineage_commit_shas": [original_commit, carrier_commit, commit],
        "lineage_root_digests": [original_root, carrier_root, root],
        "locator_digest": "sha256:" + ("f" * 64),
        "transition_index": 2,
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
        "PHASE6_AUTHORITY_STATE_COMMIT_SHA": carrier_commit,
        "PHASE6_AUTHORITY_STATE_ROOT_DIGEST": carrier_root,
        "SKILLSCOUT_LLM_PROVIDER": "deepseek",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    }

    config = bootstrap.load_acceptance_runtime_config(
        manifest_path=(
            ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
        ),
        state_commit_sha=commit,
        state_root_digest=root,
        acceptance_run_id="acceptance-proof",
        resume_proof_path=proof_path,
        environ=environment,
    )

    assert config.resume_lineage_commit_shas == (
        original_commit,
        carrier_commit,
        commit,
    )
    assert config.resume_lineage_root_digests == (
        original_root,
        carrier_root,
        root,
    )
    assert config.resume_transition_index == 2
    assert config.state_lineage_anchor_commit_sha == carrier_commit
    assert config.state_lineage_anchor_root_digest == carrier_root
    discovery_config = bootstrap._acceptance_discovery_config(
        config,
        {
            "SKILLSCOUT_STATE_REPOSITORY_ID": "123",
            "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME": "example/state",
        },
    )
    assert discovery_config.state_lineage_anchor_commit_sha == carrier_commit
    assert discovery_config.state_lineage_anchor_root_digest == carrier_root
    with pytest.raises(ValueError, match="runtime configuration"):
        bootstrap.load_acceptance_runtime_config(
            manifest_path=config.manifest_path,
            state_commit_sha=commit,
            state_root_digest=root,
            acceptance_run_id="acceptance-proof",
            resume_proof_path=proof_path,
            environ={
                **environment,
                "PHASE6_AUTHORITY_STATE_COMMIT_SHA": "f" * 40,
            },
        )
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

    assert bootstrap.ACCEPTANCE_CATALOG_FULL_NAME == ("alexzhu0/skillscout-catalog-test")
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
        build_parser().parse_args(["run-acceptance", "--unknown", "SECRET_DO_NOT_ECHO"])
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
    assert all("coverage_role" not in entry for entry in payload["search_derived_entries"])


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


def test_live_authority_recording_rejects_before_opening_state_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed approval input never reaches the state reader or writer."""

    import skillscout.bootstrap as bootstrap

    authority_path = tmp_path / "live-authority.json"
    authority_path.write_bytes(b"{}")
    authority_path.chmod(0o600)

    def forbidden_state_read(**_kwargs: object) -> object:
        pytest.fail("state client opened before live authority validation")

    monkeypatch.setattr(bootstrap, "read_exact_discovery_state", forbidden_state_read)
    with pytest.raises(ValueError, match="live acceptance authority rejected"):
        bootstrap.record_live_acceptance_authority(
            authority_path=authority_path,
            acceptance_run_id="acceptance-live-five",
            source_commit_sha="c" * 40,
            state_commit_sha="d" * 40,
            state_root_digest="sha256:" + ("e" * 64),
            state_repository_id=123,
            state_repository_full_name="example/state",
            environ={
                "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            },
        )


def test_live_authority_recording_upgrades_legacy_state_before_authority_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A state-only authority record upgrades an accepted legacy ledger first.

    This catches removal or reordering of the compatibility migration: the
    recorder sees the current operations schema before it is allowed to make
    its first authority-fact write.  The dependency passed to the recorder is
    operations-only, so this transition cannot acquire semantic or publication
    capability as part of the migration.
    """

    import sqlite3

    import skillscout.adapters.operations_state as operations_state
    import skillscout.application.acceptance as acceptance
    import skillscout.bootstrap as bootstrap
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

    database = tmp_path / "state" / "databases" / "operations.sqlite3"
    database.parent.mkdir(parents=True)
    connection = sqlite3.connect(database)
    try:
        for statement in operations_state._schema_statements(
            operations_state._LEGACY_ACCEPTANCE_FACT_KINDS
        ):
            connection.execute(statement)
        connection.execute(
            f"PRAGMA user_version = {operations_state.OPERATIONS_SCHEMA_VERSION}"
        )
        connection.commit()
    finally:
        connection.close()
    database.chmod(0o600)

    authority = LiveAcceptanceAuthorityV1.model_construct(
        authority_digest="sha256:" + ("1" * 64),
        source_commit_sha="2" * 40,
        state_commit_sha="3" * 40,
        state_root_digest="sha256:" + ("4" * 64),
        state_repository_id=123,
        state_repository_full_name="example/state",
        query_set_digest="sha256:" + ("7" * 64),
        semantic_provider="deepseek",
        stage_models=(
            "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ),
    )
    recorded_schema_fingerprints: list[str] = []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        bootstrap,
        "verify_live_acceptance_authority_state",
        lambda **_kwargs: authority,
    )
    monkeypatch.setattr(
        bootstrap,
        "load_discovery_runtime_config",
        lambda **_kwargs: SimpleNamespace(),
    )

    def record_without_external_capability(
        dependencies: object,
        *,
        acceptance_run_id: str,
        fact: object,
    ) -> object:
        assert type(dependencies) is acceptance.LiveAuthorityDependencies
        assert set(dependencies.__dataclass_fields__) == {"operations_store_factory"}
        assert acceptance_run_id == "acceptance-legacy-authority"
        assert fact is authority
        store = dependencies.operations_store_factory()
        try:
            recorded_schema_fingerprints.append(store.export_owned_state().schema_fingerprint)
        finally:
            store.close()
        return SimpleNamespace(fact_digest=authority.authority_digest)

    class VerifiedBarrier:
        def __init__(self, _config: object, _environ: object) -> None:
            pass

        def configure_acceptance_resume(self, **arguments: object) -> None:
            configured.append(arguments)

        def sync_discovery(self, **arguments: object) -> object:
            assert arguments["transition_phase"] == "authority_carrier"
            return SimpleNamespace(
                status="verified",
                commit_sha="5" * 40,
                root_digest="sha256:" + ("6" * 64),
            )

    configured: list[dict[str, object]] = []
    monkeypatch.setattr(acceptance, "record_live_authority", record_without_external_capability)
    monkeypatch.setattr(bootstrap, "_LateStateDurabilityBarrier", VerifiedBarrier)

    result = bootstrap.record_live_acceptance_authority(
        authority_path=tmp_path / "approved-authority.json",
        acceptance_run_id="acceptance-legacy-authority",
        source_commit_sha="2" * 40,
        state_commit_sha="3" * 40,
        state_root_digest="sha256:" + ("4" * 64),
        state_repository_id=123,
        state_repository_full_name="example/state",
        environ={},
    )

    assert result["status"] == "live_authority_persisted"
    assert recorded_schema_fingerprints == [operations_state._schema_fingerprint()]
    assert configured == [
        {
            "authority": authority,
            "acceptance_run_id": "acceptance-legacy-authority",
            "lineage_commit_shas": ("3" * 40,),
            "lineage_root_digests": ("sha256:" + ("4" * 64),),
        }
    ]


def test_live_authority_recording_rejects_parent_authority_without_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parent authority is a conflict, not a successful retry receipt."""

    import skillscout.adapters.operations_state as operations_state
    import skillscout.application.acceptance as acceptance
    import skillscout.bootstrap as bootstrap
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

    authority = LiveAcceptanceAuthorityV1.model_construct(
        authority_digest="sha256:" + ("1" * 64),
        source_commit_sha="2" * 40,
        state_commit_sha="3" * 40,
        state_root_digest="sha256:" + ("4" * 64),
        state_repository_id=123,
        state_repository_full_name="example/state",
        query_set_digest="sha256:" + ("7" * 64),
        semantic_provider="deepseek",
        stage_models=(
            "deepseek-v4-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ),
    )

    class ExistingAuthorityStore:
        def __init__(self, _path: Path) -> None:
            pass

        def __enter__(self) -> ExistingAuthorityStore:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def acceptance_snapshot(self, _run_id: str) -> object:
            return SimpleNamespace(
                facts=(
                    SimpleNamespace(
                        kind="acceptance_live_authority",
                        fact_digest=authority.authority_digest,
                    ),
                )
            )

        def upgrade_acceptance_schema(self) -> None:
            pytest.fail("existing parent authority triggered a local migration")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        bootstrap,
        "verify_live_acceptance_authority_state",
        lambda **_kwargs: authority,
    )
    monkeypatch.setattr(
        bootstrap,
        "load_discovery_runtime_config",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(operations_state, "OperationsStateStore", ExistingAuthorityStore)
    monkeypatch.setattr(
        acceptance,
        "record_live_authority",
        lambda *_args, **_kwargs: pytest.fail("parent authority reached a writer"),
    )

    with pytest.raises(ValueError, match="live acceptance authority"):
        bootstrap.record_live_acceptance_authority(
            authority_path=tmp_path / "approved-authority.json",
            acceptance_run_id="acceptance-existing-authority",
            source_commit_sha="2" * 40,
            state_commit_sha="3" * 40,
            state_root_digest="sha256:" + ("4" * 64),
            state_repository_id=123,
            state_repository_full_name="example/state",
            environ={},
        )


def test_fixed_runner_rejects_legacy_schema_without_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark construction never repairs legacy state before semantic work."""

    import skillscout.adapters.operations_state as operations_state
    import skillscout.bootstrap as bootstrap

    closed: list[bool] = []

    class LegacyOperationsStore:
        def __init__(self, _path: Path) -> None:
            pass

        def export_owned_state(self) -> object:
            return SimpleNamespace(
                schema_fingerprint=operations_state._fingerprint_for_schema(
                    operations_state._LEGACY_EXPECTED_SCHEMA
                )
            )

        def upgrade_acceptance_schema(self) -> None:
            pytest.fail("benchmark construction triggered a legacy migration")

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(operations_state, "OperationsStateStore", LegacyOperationsStore)

    with pytest.raises(ValueError, match="acceptance operations schema is not current"):
        bootstrap._FixedRepositoryAcceptanceRunner(
            config=SimpleNamespace(),
            discovery_config=SimpleNamespace(operations_state=tmp_path / "operations.sqlite3"),
            barrier=object(),
            source={},
            frozen_owner_export=object(),
            acceptance_run_id="acceptance-legacy-runner",
        )

    assert closed == [True]


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
        ".planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json"
    )
    workflow_relative = Path(".github/workflows/phase6-acceptance.yml")
    query_relative = Path("config/discovery-queries-v1.json")
    for relative in (manifest_relative, workflow_relative, query_relative):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    subprocess.run(("git", "init", "-q"), cwd=tmp_path, check=True)
    subprocess.run(("git", "config", "user.email", "tests@example.invalid"), cwd=tmp_path, check=True)
    subprocess.run(("git", "config", "user.name", "SkillScout tests"), cwd=tmp_path, check=True)
    subprocess.run(("git", "add", "."), cwd=tmp_path, check=True)
    subprocess.run(("git", "commit", "-qm", "authority source"), cwd=tmp_path, check=True)
    source_commit_sha = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = LockedBenchmarkManifestV1.model_validate_json(
        (tmp_path / manifest_relative).read_bytes(),
        strict=True,
    )
    query_set = DiscoveryQuerySetV1.model_validate_json(
        (tmp_path / query_relative).read_bytes(),
        strict=True,
    )
    workflow_digest = (
        "sha256:" + hashlib.sha256((tmp_path / workflow_relative).read_bytes()).hexdigest()
    )
    authority = LiveAcceptanceAuthorityV1(
        schema_version="live-acceptance-authority-v1",
        authority_version=1,
        source_commit_sha=source_commit_sha,
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
        observed_source_commit_sha=source_commit_sha,
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

    # A parseable working-tree query file must still be the exact blob from the
    # approved source commit, not merely an unchecked local input.
    original_query_bytes = (tmp_path / query_relative).read_bytes()
    (tmp_path / query_relative).write_bytes(original_query_bytes + b"\n")
    with pytest.raises(ValueError):
        bootstrap.verify_live_acceptance_authority(
            repository_root=tmp_path,
            authority_bytes=authority_bytes,
            observed_source_commit_sha=source_commit_sha,
            observed_state_commit_sha="e" * 40,
            observed_state_root_digest="sha256:" + ("f" * 64),
            observed_state_repository_id=123,
            observed_state_repository_full_name="example/state",
            environ={
                "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            },
        )
    (tmp_path / query_relative).write_bytes(original_query_bytes)

    # A matching collection of files cannot be evaluated from a different
    # checkout HEAD than the immutable authority source commit.
    subprocess.run(
        ("git", "commit", "--allow-empty", "-qm", "different checkout head"),
        cwd=tmp_path,
        check=True,
    )
    with pytest.raises(ValueError):
        bootstrap.verify_live_acceptance_authority(
            repository_root=tmp_path,
            authority_bytes=authority_bytes,
            observed_source_commit_sha=source_commit_sha,
            observed_state_commit_sha="e" * 40,
            observed_state_root_digest="sha256:" + ("f" * 64),
            observed_state_repository_id=123,
            observed_state_repository_full_name="example/state",
            environ={
                "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            },
        )

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
            observed_source_commit_sha=source_commit_sha,
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
            observed_source_commit_sha=source_commit_sha,
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
    options = {option for action in parser._actions for option in action.option_strings}
    assert "--authority-state-root" in options
    assert "--authority-operations-state" not in options


def test_live_authority_recording_is_a_closed_state_only_cli_transition() -> None:
    """The only authority-recording command has no model or catalog surface."""

    commands = _cli_subcommands()
    parser = commands["record-live-authority"]
    options = {option for action in parser._actions for option in action.option_strings}
    assert {
        "--authority",
        "--acceptance-run-id",
        "--source-commit-sha",
    } <= options
    assert (
        not {
            "--state-commit-sha",
            "--state-root-digest",
            "--state-repository-id",
            "--state-repository-full-name",
            "--deepseek-api-key",
            "--openai-api-key",
            "--catalog-token",
            "--publish",
        }
        & options
    )
    preflight_options = {
        option
        for action in commands["verify-live-authority-state"]._actions
        for option in action.option_strings
    }
    assert {"--authority", "--source-commit-sha"} <= preflight_options
    assert not {"--token", "--secret", "--publish", "--catalog"} & preflight_options


def test_live_authority_state_preflight_is_read_only() -> None:
    """The diagnostic preflight cannot persist an authority or invoke a model."""

    import skillscout.cli as cli

    source = inspect.getsource(cli._run_verify_live_authority_state)
    assert "record_live_acceptance_authority" not in source
    assert "resolve_semantic_provider" not in source
    assert "SKILLSCOUT_GITHUB_TOKEN" not in source


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
        "parent_state_commit_sha": "6" * 40,
        "parent_state_root_digest": "sha256:" + ("7" * 64),
        "transition_index": 1,
        "previous_locator_digest": None,
        "transition_phase": "scenario",
        "semantic_stage": None,
        "attempt_no": None,
        "semantic_status": None,
        "workflow_authority_digest": None,
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
        "recorded_at": "2026-07-30T12:00:00.000000Z",
    }
    locator = AcceptanceCampaignResumeLocatorV1(**values)

    assert locator.locator_digest == sha256_digest(values)
    assert locator.parent_state_commit_sha == "6" * 40
    assert locator.parent_state_root_digest == "sha256:" + ("7" * 64)
    authority_carrier = AcceptanceCampaignResumeLocatorV1(
        **{
            **values,
            "transition_phase": "authority_carrier",
        }
    )
    assert authority_carrier.semantic_stage is None
    with pytest.raises(ValidationError):
        AcceptanceCampaignResumeLocatorV1(
            **{
                **values,
                "transition_phase": "authority_carrier",
                "semantic_stage": "extractor",
                "attempt_no": 1,
                "workflow_authority_digest": "sha256:" + ("9" * 64),
            }
        )
    with pytest.raises(ValidationError):
        AcceptanceCampaignResumeLocatorV1(
            **{
                **values,
                "transition_index": 2,
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


@pytest.mark.parametrize(
    ("transition_phase", "semantic_status"),
    (
        ("request_reserved", None),
        ("started", "started"),
        ("result_durable", "decided"),
        ("result_durable", "confirmed_retryable"),
        ("result_durable", "semantic_outcome_unknown"),
    ),
)
def test_campaign_resume_locator_binds_explicit_semantic_transition_edge(
    transition_phase: str,
    semantic_status: str | None,
) -> None:
    """A child is authorized by a named protocol edge, never a commit-count suffix."""

    from pydantic import ValidationError

    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    values = {
        "schema_version": "acceptance-campaign-resume-locator-v1",
        "acceptance_run_id": "acceptance-transition",
        "live_acceptance_authority_digest": "sha256:" + ("1" * 64),
        "source_commit_sha": "2" * 40,
        "manifest_digest": "sha256:" + ("3" * 64),
        "state_repository_id": 123,
        "state_repository_full_name": "example/state",
        "original_state_commit_sha": "4" * 40,
        "original_state_root_digest": "sha256:" + ("5" * 64),
        "parent_state_commit_sha": "6" * 40,
        "parent_state_root_digest": "sha256:" + ("7" * 64),
        "transition_index": 3,
        "previous_locator_digest": "sha256:" + ("8" * 64),
        "transition_phase": transition_phase,
        "semantic_stage": "generator",
        "attempt_no": 2,
        "semantic_status": semantic_status,
        "workflow_authority_digest": "sha256:" + ("9" * 64),
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
        "recorded_at": "2026-07-30T12:00:00.000000Z",
    }
    locator = AcceptanceCampaignResumeLocatorV1(**values)

    assert locator.transition_phase == transition_phase
    assert locator.parent_state_commit_sha == "6" * 40
    assert locator.transition_index == 3
    with pytest.raises(ValidationError):
        AcceptanceCampaignResumeLocatorV1(
            **{
                **values,
                "transition_phase": "result_durable",
                "semantic_status": None,
            }
        )
    with pytest.raises(ValidationError):
        AcceptanceCampaignResumeLocatorV1(
            **{
                **values,
                "transition_index": 1,
                "previous_locator_digest": values["previous_locator_digest"],
            }
        )


def test_phase3_retry_exhaustion_is_a_provider_system_outcome() -> None:
    """Generator/reviewer exhaustion must not be mislabeled as harness failure."""

    import skillscout.bootstrap as bootstrap
    from skillscout.application.ports import ErrorCode

    assert bootstrap._phase3_safe_failure_outcome(ErrorCode.RETRY_EXHAUSTED) == (
        "provider_exhausted",
        "provider_attempts_exhausted",
    )


def test_acceptance_cli_exposes_only_exact_resume_lineage_inputs() -> None:
    """Workflow preflight resolves a descendant checkout without a mutable SHA var."""

    parser = _cli_subcommands()["resolve-acceptance-resume"]
    options = {option for action in parser._actions for option in action.option_strings}

    assert options == {
        "-h",
        "--help",
        "--authority-state-root",
        "--authority-state-commit-sha",
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
                "--authority-state-commit-sha",
                "c" * 40,
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
    from skillscout.application.acceptance import (
        CampaignOwnedFactObservation,
        CampaignResumeLocatorObservation,
    )
    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    original_commit = "4" * 40
    carrier_commit = "8" * 40
    original_root = "sha256:" + ("5" * 64)
    carrier_root = "sha256:" + ("9" * 64)
    authority_digest = "sha256:" + ("1" * 64)
    events: list[str] = []
    locator = AcceptanceCampaignResumeLocatorV1.model_construct(
        acceptance_run_id="acceptance-resume",
        live_acceptance_authority_digest=authority_digest,
        original_state_commit_sha=original_commit,
        original_state_root_digest=original_root,
        parent_state_commit_sha=original_commit,
        parent_state_root_digest=original_root,
        transition_index=1,
        previous_locator_digest=None,
        transition_phase="authority_carrier",
        locator_digest="sha256:" + ("a" * 64),
    )
    locator_object_digest = "sha256:" + ("b" * 64)
    carrier_fact = CampaignOwnedFactObservation(
        kind="acceptance_live_authority",
        object_digest="sha256:" + ("c" * 64),
    )

    def bundle(root: object) -> object:
        return SimpleNamespace(
            root=root,
            content_by_path=lambda: {"state/root.json": b"canonical"},
        )

    bundles = {
        original_commit: bundle(
            SimpleNamespace(
                root_digest=original_root,
                state_parent_commit_sha="0" * 40,
                prior_root_digest="sha256:" + ("0" * 64),
            )
        ),
        carrier_commit: bundle(
            SimpleNamespace(
                root_digest=carrier_root,
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

        def get_state_ref(self, *, read_budget: object) -> object:
            assert read_budget is not None
            return SimpleNamespace(sha=carrier_commit)

    class Store:
        def __init__(self, _reader: object) -> None:
            pass

        def verify_lineage_anchor(
            self,
            *,
            commit_sha: str,
            root_digest: str,
            anchor: object,
            read_budget: object,
        ) -> None:
            assert read_budget is not None
            assert commit_sha == carrier_commit
            assert root_digest == carrier_root
            assert getattr(anchor, "commit_sha", None) == original_commit
            assert getattr(anchor, "root_digest", None) == original_root
            assert getattr(anchor, "max_hops", None) == 1

        def inspect_commit_root(
            self,
            sha: str,
            *,
            read_budget: object,
        ) -> object:
            assert read_budget is not None
            parent = ("0" * 40,) if sha == original_commit else (original_commit,)
            root = bundles[sha].root
            return SimpleNamespace(
                commit=SimpleNamespace(sha=sha, parents=parent),
                root=root,
                object_digests=(locator_object_digest,) if sha == carrier_commit else (),
                declared_content_bytes=1_024,
            )

        def restore_commit(
            self,
            sha: str,
            *,
            lineage_anchor: object,
            read_budget: object,
        ) -> object:
            assert read_budget is not None
            if sha == original_commit:
                assert getattr(lineage_anchor, "commit_sha", None) == original_commit
                assert getattr(lineage_anchor, "root_digest", None) == original_root
                assert getattr(lineage_anchor, "max_hops", None) == 1
            else:
                assert getattr(lineage_anchor, "commit_sha", None) == carrier_commit
                assert getattr(lineage_anchor, "root_digest", None) == carrier_root
                assert getattr(lineage_anchor, "max_hops", None) == 159
            return bundles[sha]

    monkeypatch.setattr(
        cli,
        "_load_verified_live_authority",
        lambda _arguments: (
            events.append("authority")
            or (
                SimpleNamespace(
                    authority_digest=authority_digest,
                    source_commit_sha="2" * 40,
                    state_commit_sha=original_commit,
                    state_root_digest=original_root,
                    state_repository_id=123,
                    state_repository_full_name="example/state",
                ),
                bundles[carrier_commit],
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(state_branch, "StateBranchReadClient", Reader)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        cli,
        "_acceptance_resume_projection_from_bundle",
        lambda bundle, _run_id: (
            (
                (
                    CampaignResumeLocatorObservation(
                        locator=locator,
                        object_digest=locator_object_digest,
                    ),
                ),
                (carrier_fact,),
            )
            if bundle is bundles[carrier_commit]
            else ((), ())
        ),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "_checked_out_git_commit",
        lambda _path: carrier_commit,
    )
    monkeypatch.setattr(
        cli,
        "load_verified_state_checkout",
        lambda **_kwargs: bundles[carrier_commit],
    )
    monkeypatch.setenv("SKILLSCOUT_STATE_GITHUB_TOKEN", "fixture-token")

    result = cli._run_resolve_acceptance_resume(
        SimpleNamespace(
            authority_state_root=tmp_path,
            authority_state_commit_sha=carrier_commit,
            authority_state_root_digest=carrier_root,
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
        "lineage_commit_shas": [original_commit, carrier_commit],
        "lineage_root_digests": [original_root, carrier_root],
        "locator_digest": locator.locator_digest,
        "transition_index": 1,
        "state_commit_sha": carrier_commit,
        "state_root_digest": carrier_root,
        "status": "acceptance_resume_verified",
    }
    assert events == ["authority", "reader", "closed"]


def test_resume_resolver_rejects_wrong_carrier_checkout_before_state_token_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The local immutable carrier identity is checked before remote capability use."""

    import skillscout.adapters.state_branch as state_branch
    import skillscout.cli as cli
    from skillscout.application.ports import SafeFailure

    class Reader:
        def __init__(self, **_kwargs: object) -> None:
            pytest.fail("resolver read state before its authority carrier was verified")

    monkeypatch.setattr(state_branch, "StateBranchReadClient", Reader)
    monkeypatch.setattr(cli, "_checked_out_git_commit", lambda _path: "f" * 40)
    monkeypatch.delenv("SKILLSCOUT_STATE_GITHUB_TOKEN", raising=False)

    with pytest.raises(SafeFailure):
        cli._run_resolve_acceptance_resume(
            SimpleNamespace(
                authority_state_root=tmp_path,
                authority_state_commit_sha="c" * 40,
                authority_state_root_digest="sha256:" + ("d" * 64),
                campaign_state_root=tmp_path,
                acceptance_run_id="acceptance-resume",
                authority_digest="sha256:" + ("a" * 64),
                source_commit_sha="b" * 40,
                state_repository_id=123,
                state_repository_full_name="example/state",
            )
        )


def test_resume_resolver_rejects_a_branch_that_reaches_predecessor_without_carrier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A valid old authority state cannot substitute for the required carrier checkpoint."""

    import skillscout.adapters.state_branch as state_branch
    import skillscout.cli as cli
    from skillscout.application.ports import SafeFailure

    predecessor_commit = "4" * 40
    predecessor_root = "sha256:" + ("5" * 64)
    carrier_commit = "8" * 40
    carrier_root = "sha256:" + ("9" * 64)
    head_commit = "7" * 40
    head_root = "sha256:" + ("6" * 64)
    inspected: list[str] = []

    def bundle(root: object) -> object:
        return SimpleNamespace(root=root, content_by_path=lambda: {})

    bundles = {
        predecessor_commit: bundle(
            SimpleNamespace(
                root_digest=predecessor_root,
                prior_root_digest="sha256:" + ("0" * 64),
            )
        ),
        carrier_commit: bundle(
            SimpleNamespace(
                root_digest=carrier_root,
                prior_root_digest=predecessor_root,
            )
        ),
    }

    class Reader:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

        def get_state_ref(self, *, read_budget: object) -> object:
            assert read_budget is not None
            return SimpleNamespace(sha=head_commit)

    class Store:
        def __init__(self, _reader: object) -> None:
            pass

        def verify_lineage_anchor(self, **_kwargs: object) -> None:
            pass

        def inspect_commit_root(
            self,
            sha: str,
            *,
            read_budget: object,
        ) -> object:
            assert read_budget is not None
            inspected.append(sha)
            if sha == head_commit:
                return SimpleNamespace(
                    commit=SimpleNamespace(sha=sha, parents=(predecessor_commit,)),
                    root=SimpleNamespace(
                        root_digest=head_root,
                        prior_root_digest=predecessor_root,
                    ),
                    object_digests=(),
                    declared_content_bytes=1_024,
                )
            if sha == predecessor_commit:
                return SimpleNamespace(
                    commit=SimpleNamespace(sha=sha, parents=()),
                    root=bundles[sha].root,
                    object_digests=(),
                    declared_content_bytes=1_024,
                )
            raise AssertionError("resolver followed an unexpected parent")

        def restore_commit(
            self,
            sha: str,
            *,
            lineage_anchor: object,
            read_budget: object,
        ) -> object:
            assert read_budget is not None
            if sha == carrier_commit:
                assert getattr(lineage_anchor, "commit_sha", None) == carrier_commit
            elif sha == predecessor_commit:
                assert getattr(lineage_anchor, "commit_sha", None) == predecessor_commit
            else:
                pytest.fail("resolver restored a campaign branch before carrier membership")
            return bundles[sha]

    authority = SimpleNamespace(
        authority_digest="sha256:" + ("1" * 64),
        source_commit_sha="2" * 40,
        state_commit_sha=predecessor_commit,
        state_root_digest=predecessor_root,
        state_repository_id=123,
        state_repository_full_name="example/state",
    )
    monkeypatch.setattr(
        cli,
        "_load_verified_live_authority",
        lambda _arguments: (authority, bundles[carrier_commit]),
    )
    monkeypatch.setattr(state_branch, "StateBranchReadClient", Reader)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        cli,
        "_acceptance_resume_projection_from_bundle",
        lambda _bundle, _run_id: ((), ()),
    )
    monkeypatch.setenv("SKILLSCOUT_STATE_GITHUB_TOKEN", "fixture-token")

    with pytest.raises(SafeFailure):
        cli._run_resolve_acceptance_resume(
            SimpleNamespace(
                authority_state_root=tmp_path,
                authority_state_commit_sha=carrier_commit,
                authority_state_root_digest=carrier_root,
                campaign_state_root=tmp_path,
                acceptance_run_id="acceptance-resume",
                authority_digest=authority.authority_digest,
                source_commit_sha=authority.source_commit_sha,
                state_repository_id=123,
                state_repository_full_name="example/state",
            )
        )

    assert carrier_commit not in inspected
    assert inspected[-1] == predecessor_commit


def test_resume_resolver_counts_and_rejects_overlong_metadata_lineage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Carrier plus 160 descendants fails before any descendant bundle read."""

    import skillscout.adapters.state_branch as state_branch
    import skillscout.cli as cli
    from skillscout.application.ports import ErrorCode, SafeFailure

    predecessor_commit = "f" * 40
    predecessor_root = "sha256:" + ("e" * 64)
    carrier_commit = "e" * 40
    carrier_root = "sha256:" + ("d" * 64)
    descendants = tuple(f"{index:040x}" for index in range(1, 161))
    commits = (predecessor_commit, carrier_commit, *descendants)
    inspected: list[str] = []
    restored: list[str] = []

    def bundle(root: object) -> object:
        return SimpleNamespace(root=root, content_by_path=lambda: {})

    def root_for(index: int) -> object:
        root_digest = (
            predecessor_root
            if index == 0
            else carrier_root if index == 1 else "sha256:" + f"{index:064x}"
        )
        prior_root = (
            "sha256:" + ("0" * 64)
            if index == 0
            else predecessor_root
            if index == 1
            else "sha256:" + f"{index - 1:064x}"
        )
        return SimpleNamespace(root_digest=root_digest, prior_root_digest=prior_root)

    bundles = {sha: bundle(root_for(index)) for index, sha in enumerate(commits[:2])}

    class Reader:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

        def get_state_ref(self, *, read_budget: object) -> object:
            assert read_budget is not None
            return SimpleNamespace(sha=commits[-1])

    class Store:
        def __init__(self, _reader: object) -> None:
            pass

        def verify_lineage_anchor(
            self,
            *,
            commit_sha: str,
            root_digest: str,
            anchor: object,
            read_budget: object,
        ) -> None:
            assert read_budget is not None
            assert (commit_sha, root_digest) == (carrier_commit, carrier_root)
            assert (
                getattr(anchor, "commit_sha", None),
                getattr(anchor, "root_digest", None),
                getattr(anchor, "max_hops", None),
            ) == (predecessor_commit, predecessor_root, 1)

        def inspect_commit_root(
            self,
            sha: str,
            *,
            read_budget: object,
        ) -> object:
            assert read_budget is not None
            inspected.append(sha)
            index = commits.index(sha)
            parent = commits[index - 1] if index > 0 else "0" * 40
            root = root_for(index)
            return SimpleNamespace(
                commit=SimpleNamespace(sha=sha, parents=(parent,)),
                root=root,
                object_digests=(),
                declared_content_bytes=1_024,
            )

        def restore_commit(
            self,
            sha: str,
            *,
            lineage_anchor: object,
            read_budget: object,
        ) -> object:
            assert read_budget is not None
            if sha == carrier_commit:
                assert (
                    getattr(lineage_anchor, "commit_sha", None),
                    getattr(lineage_anchor, "root_digest", None),
                    getattr(lineage_anchor, "max_hops", None),
                ) == (carrier_commit, carrier_root, 159)
                restored.append(sha)
                return bundles[sha]
            if sha == predecessor_commit:
                assert (
                    getattr(lineage_anchor, "commit_sha", None),
                    getattr(lineage_anchor, "root_digest", None),
                    getattr(lineage_anchor, "max_hops", None),
                ) == (predecessor_commit, predecessor_root, 1)
                restored.append(sha)
                return bundles[sha]
            raise AssertionError("overlong lineage restored a descendant bundle")

    monkeypatch.setattr(
        cli,
        "_load_verified_live_authority",
        lambda _arguments: (
            SimpleNamespace(
                authority_digest="sha256:" + ("1" * 64),
                source_commit_sha="2" * 40,
                state_commit_sha=predecessor_commit,
                state_root_digest=predecessor_root,
                state_repository_id=123,
                state_repository_full_name="example/state",
            ),
            bundles[carrier_commit],
        ),
    )
    monkeypatch.setattr(state_branch, "StateBranchReadClient", Reader)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        cli,
        "_acceptance_resume_projection_from_bundle",
        lambda _bundle, _run_id: ((), ()),
    )
    monkeypatch.setenv("SKILLSCOUT_STATE_GITHUB_TOKEN", "fixture-token")

    with pytest.raises(SafeFailure) as rejected:
        cli._run_resolve_acceptance_resume(
            SimpleNamespace(
                authority_state_root=tmp_path,
                authority_state_commit_sha=carrier_commit,
                authority_state_root_digest=carrier_root,
                campaign_state_root=tmp_path,
                acceptance_run_id="acceptance-resume",
                authority_digest="sha256:" + ("1" * 64),
                source_commit_sha="2" * 40,
                state_repository_id=123,
                state_repository_full_name="example/state",
            )
        )

    assert rejected.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    assert inspected[0] == predecessor_commit
    assert len(inspected[1:]) == 160
    assert carrier_commit not in inspected
    assert restored == [carrier_commit, predecessor_commit]


def test_resume_resolver_visits_authority_at_exact_descendant_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Carrier plus 159 descendants reaches carrier in the exact 160-state cap."""

    import skillscout.adapters.state_branch as state_branch
    import skillscout.cli as cli
    from skillscout.application.ports import ErrorCode, SafeFailure

    predecessor_commit = "f" * 40
    predecessor_root = "sha256:" + ("e" * 64)
    carrier_commit = "e" * 40
    carrier_root = "sha256:" + ("d" * 64)
    descendants = tuple(f"{index:040x}" for index in range(1, 160))
    commits = (predecessor_commit, carrier_commit, *descendants)
    inspected: list[str] = []
    restored: list[str] = []

    def bundle(root: object) -> object:
        return SimpleNamespace(root=root, content_by_path=lambda: {})

    def root_for(index: int) -> object:
        root_digest = (
            predecessor_root
            if index == 0
            else carrier_root if index == 1 else "sha256:" + f"{index:064x}"
        )
        prior_root = (
            "sha256:" + ("0" * 64)
            if index == 0
            else predecessor_root
            if index == 1
            else "sha256:" + f"{index - 1:064x}"
        )
        return SimpleNamespace(root_digest=root_digest, prior_root_digest=prior_root)

    bundles = {sha: bundle(root_for(index)) for index, sha in enumerate(commits[:2])}

    class Reader:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

        def get_state_ref(self, *, read_budget: object) -> object:
            assert read_budget is not None
            return SimpleNamespace(sha=commits[-1])

    class Store:
        def __init__(self, _reader: object) -> None:
            pass

        def verify_lineage_anchor(
            self,
            *,
            commit_sha: str,
            root_digest: str,
            anchor: object,
            read_budget: object,
        ) -> None:
            assert read_budget is not None
            assert (commit_sha, root_digest) == (carrier_commit, carrier_root)
            assert (
                getattr(anchor, "commit_sha", None),
                getattr(anchor, "root_digest", None),
                getattr(anchor, "max_hops", None),
            ) == (predecessor_commit, predecessor_root, 1)

        def inspect_commit_root(
            self,
            sha: str,
            *,
            read_budget: object,
        ) -> object:
            assert read_budget is not None
            inspected.append(sha)
            index = commits.index(sha)
            parent = commits[index - 1] if index else "0" * 40
            root = root_for(index)
            return SimpleNamespace(
                commit=SimpleNamespace(sha=sha, parents=(parent,)),
                root=root,
                object_digests=(),
                declared_content_bytes=1_024,
            )

        def restore_commit(
            self,
            sha: str,
            *,
            lineage_anchor: object,
            read_budget: object,
        ) -> object:
            assert read_budget is not None
            if sha == carrier_commit:
                assert (
                    getattr(lineage_anchor, "commit_sha", None),
                    getattr(lineage_anchor, "root_digest", None),
                    getattr(lineage_anchor, "max_hops", None),
                ) == (carrier_commit, carrier_root, 159)
                return bundles[sha]
            if sha == predecessor_commit:
                assert (
                    getattr(lineage_anchor, "commit_sha", None),
                    getattr(lineage_anchor, "root_digest", None),
                    getattr(lineage_anchor, "max_hops", None),
                ) == (predecessor_commit, predecessor_root, 1)
                return bundles[sha]
            assert (
                getattr(lineage_anchor, "commit_sha", None),
                getattr(lineage_anchor, "root_digest", None),
                getattr(lineage_anchor, "max_hops", None),
            ) == (carrier_commit, carrier_root, 159)
            restored.append(sha)
            raise AssertionError("boundary test stops after carrier-anchored metadata traversal")

    monkeypatch.setattr(
        cli,
        "_load_verified_live_authority",
        lambda _arguments: (
            SimpleNamespace(
                authority_digest="sha256:" + ("1" * 64),
                source_commit_sha="2" * 40,
                state_commit_sha=predecessor_commit,
                state_root_digest=predecessor_root,
                state_repository_id=123,
                state_repository_full_name="example/state",
            ),
            bundles[carrier_commit],
        ),
    )
    monkeypatch.setattr(state_branch, "StateBranchReadClient", Reader)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        cli,
        "_acceptance_resume_projection_from_bundle",
        lambda _bundle, _run_id: ((), ()),
    )
    monkeypatch.setenv("SKILLSCOUT_STATE_GITHUB_TOKEN", "fixture-token")

    with pytest.raises(SafeFailure) as rejected:
        cli._run_resolve_acceptance_resume(
            SimpleNamespace(
                authority_state_root=tmp_path,
                authority_state_commit_sha=carrier_commit,
                authority_state_root_digest=carrier_root,
                campaign_state_root=tmp_path,
                acceptance_run_id="acceptance-resume",
                authority_digest="sha256:" + ("1" * 64),
                source_commit_sha="2" * 40,
                state_repository_id=123,
                state_repository_full_name="example/state",
            )
        )

    assert rejected.value.code is ErrorCode.STATE_INTEGRITY_ERROR
    assert inspected[0] == predecessor_commit
    assert len(inspected[1:]) == 160
    assert inspected[-1] == carrier_commit
    assert restored == [commits[-1]]


def test_fresh_campaign_state_restore_uses_the_discovery_lineage_horizon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh nomination cannot treat a replacement zero-parent state as trusted."""

    import skillscout.bootstrap as bootstrap
    import skillscout.adapters.github as github
    import skillscout.adapters.operations_state as operations_state
    import skillscout.adapters.state_branch as state_branch
    from skillscout.domain.discovery import DiscoveryQuerySetV1

    query_path = ROOT / "config" / "discovery-queries-v1.json"
    query_set = DiscoveryQuerySetV1.model_validate_json(
        query_path.read_bytes(),
        strict=True,
    )
    config = bootstrap.FreshCampaignPreparationRuntimeConfig(
        state_repository_id=123,
        state_repository_full_name="example/state",
        query_set_path=query_path,
        query_set=query_set,
        query_set_digest=query_set.query_set_digest or "",
        operations_state=Path("state/databases/operations.sqlite3"),
        state_lineage_anchor_commit_sha="a" * 40,
        state_lineage_anchor_root_digest="sha256:" + ("b" * 64),
    )
    anchors: list[object] = []
    restored: list[dict[str, object]] = []

    class MetadataClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def get_repo_metadata(self, _owner: str, _repository: str) -> object:
            return SimpleNamespace(id=123, owner="example", name="state")

        def close(self) -> None:
            pass

    class StateClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    observation = SimpleNamespace(
        observed_head="c" * 40,
        bundle=SimpleNamespace(
            root=SimpleNamespace(root_digest="sha256:" + ("d" * 64))
        ),
    )

    class Store:
        def __init__(self, _client: object) -> None:
            pass

        def restore(self, *, lineage_anchor: object) -> object:
            anchors.append(lineage_anchor)
            return observation

    monkeypatch.setattr(github, "GitHubReadClient", MetadataClient)
    monkeypatch.setattr(state_branch, "StateBranchClient", StateClient)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        operations_state,
        "restore_three_store_bundle",
        lambda bundle, **kwargs: restored.append({"bundle": bundle, **kwargs}),
    )

    assert bootstrap._restore_verified_fresh_campaign_state(
        config=config,
        source={"SKILLSCOUT_STATE_GITHUB_TOKEN": "fixture-token"},
        pipeline_path=Path("state/databases/pipeline.sqlite3"),
        publication_path=Path("state/databases/publication.sqlite3"),
    ) is observation
    assert len(anchors) == 1
    anchor = anchors[0]
    assert getattr(anchor, "commit_sha", None) == config.state_lineage_anchor_commit_sha
    assert getattr(anchor, "root_digest", None) == config.state_lineage_anchor_root_digest
    assert getattr(anchor, "max_hops", None) == 4096
    assert len(restored) == 1


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
        def record_acceptance_fact(self, run_id: str, kind: str, fact: object) -> object:
            assert run_id == "acceptance-resume"
            assert kind == "acceptance_campaign_resume_locator"
            recorded.append(fact)
            return object()

    barrier = object.__new__(bootstrap._LateStateDurabilityBarrier)

    def synchronize(**arguments: object) -> object:
        synchronized_result = next(synchronized)
        barrier._record_acceptance_transition(
            operations_store=arguments["operations_store"],
            observed_head=str(arguments["observed_head"]),
            prior_root_digest=str(arguments["prior_root_digest"]),
            created_at=str(arguments["created_at"]),
            transition_phase=str(arguments["transition_phase"]),
            semantic_stage=arguments.get("semantic_stage"),
            attempt_no=arguments.get("attempt_no"),
            semantic_status=arguments.get("semantic_status"),
            workflow_authority_digest=arguments.get("workflow_authority_digest"),
        )
        barrier._advance_acceptance_transition(synchronized_result)
        return synchronized_result

    monkeypatch.setattr(
        barrier,
        "sync_discovery",
        synchronize,
    )
    barrier.configure_acceptance_resume(
        authority=authority,
        acceptance_run_id="acceptance-resume",
        lineage_commit_shas=(original_commit,),
        lineage_root_digests=(original_root,),
    )

    first = barrier.sync_discovery(
        operations_store=Operations(),
        observed_head=original_commit,
        prior_root_digest=original_root,
        created_at="2026-07-30T12:00:00.000000Z",
        pipeline_store=object(),
        transition_phase="terminal",
    )
    second = barrier.sync_discovery(
        operations_store=Operations(),
        observed_head=anchor_commit,
        prior_root_digest=anchor_root,
        created_at="2026-07-30T12:01:00.000000Z",
        pipeline_store=object(),
        transition_phase="scenario",
    )

    assert first.commit_sha == anchor_commit
    assert second.commit_sha == second_commit
    assert [
        (
            item.parent_state_commit_sha,
            item.parent_state_root_digest,
            item.transition_index,
            item.previous_locator_digest,
            item.transition_phase,
        )
        for item in recorded
    ] == [
        (
            original_commit,
            original_root,
            1,
            None,
            "terminal",
        ),
        (
            anchor_commit,
            anchor_root,
            2,
            recorded[0].locator_digest,
            "scenario",
        ),
    ]


@pytest.mark.parametrize(
    "mutation",
    ("exact", "missing_authority", "missing_locator", "wrong_locator"),
)
def test_authority_carrier_post_cas_recovery_requires_exact_authority_and_locator(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    """A live-authority recovery needs its exact local fact carrier before CAS proof."""

    import skillscout.adapters.operations_state as operations_state
    import skillscout.adapters.state_branch as state_branch
    import skillscout.bootstrap as bootstrap
    from skillscout.adapters.operations_state import (
        AcceptanceFactRecord,
        AcceptanceRunSnapshot,
    )
    from skillscout.domain.acceptance import LiveAcceptanceAuthorityV1

    parent_commit = "4" * 40
    parent_root = "sha256:" + ("5" * 64)
    child_commit = "6" * 40
    child_tree = "7" * 40
    child_root = "sha256:" + ("8" * 64)
    authority = LiveAcceptanceAuthorityV1.model_construct(
        authority_digest="sha256:" + ("1" * 64),
        source_commit_sha="2" * 40,
        manifest_digest="sha256:" + ("3" * 64),
        state_commit_sha=parent_commit,
        state_root_digest=parent_root,
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

    class Operations:
        def __init__(self) -> None:
            authority_fact = authority
            if mutation == "missing_authority":
                authority_fact = authority.model_copy(
                    update={"authority_digest": "sha256:" + ("9" * 64)}
                )
            self.facts = (
                ()
                if mutation == "missing_authority"
                else (
                    AcceptanceFactRecord(
                        acceptance_run_id="acceptance-recovery",
                        kind="acceptance_live_authority",
                        fact_digest=authority_fact.authority_digest or "",
                        fact=authority_fact,
                    ),
                )
            )

        def record_acceptance_fact(
            self,
            run_id: str,
            kind: str,
            fact: object,
        ) -> object:
            assert run_id == "acceptance-recovery"
            assert kind == "acceptance_campaign_resume_locator"
            if mutation != "missing_locator":
                persisted = fact
                if mutation == "wrong_locator":
                    persisted = fact.model_copy(
                        update={"locator_digest": "sha256:" + ("a" * 64)}
                    )
                self.facts = (*self.facts, AcceptanceFactRecord(
                    acceptance_run_id=run_id,
                    kind="acceptance_campaign_resume_locator",
                    fact_digest=persisted.locator_digest,
                    fact=persisted,
                ))
            return object()

        def acceptance_snapshot(self, run_id: str) -> AcceptanceRunSnapshot:
            assert run_id == "acceptance-recovery"
            return AcceptanceRunSnapshot(run_id, self.facts)

    reconciliations: list[tuple[object, object, object, object]] = []

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    class Store:
        def __init__(self, _client: object, *, read_cache: object) -> None:
            pass

        def sync(self, _bundle: object, _head: str) -> object:
            raise state_branch.StateBranchPostCasUncertain(
                candidate_commit_sha=child_commit,
                candidate_tree_sha=child_tree,
                previous_head=parent_commit,
                expected_root_digest=child_root,
            )

        def reconcile_post_cas_uncertainty(
            self,
            failure: object,
            bundle: object,
            observed_head: object,
            *,
            expected_prior_root_digest: object,
        ) -> object:
            reconciliations.append(
                (failure, bundle, observed_head, expected_prior_root_digest)
            )
            return state_branch.StateSyncObservation(
                "verified",
                parent_commit,
                child_commit,
                child_tree,
                child_root,
            )

    monkeypatch.setattr(state_branch, "StateBranchClient", Client)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        operations_state,
        "assemble_three_store_bundle",
        lambda **_kwargs: SimpleNamespace(root=SimpleNamespace(root_digest=child_root)),
    )
    barrier = bootstrap._LateStateDurabilityBarrier(
        SimpleNamespace(
            state_repository_id=123,
            state_repository_full_name="example/state",
            query_set_digest="sha256:" + ("b" * 64),
        ),
        {"SKILLSCOUT_STATE_GITHUB_TOKEN": "fixture-token"},
        frozen_publication_export=SimpleNamespace(
            export_digest="sha256:" + ("c" * 64)
        ),
    )
    barrier.configure_acceptance_resume(
        authority=authority,
        acceptance_run_id="acceptance-recovery",
        lineage_commit_shas=(parent_commit,),
        lineage_root_digests=(parent_root,),
    )

    if mutation == "exact":
        synchronized = barrier.sync_discovery(
            operations_store=Operations(),
            observed_head=parent_commit,
            prior_root_digest=parent_root,
            created_at="2026-07-31T12:00:00.000000Z",
            pipeline_store=object(),
            transition_phase="authority_carrier",
        )
        assert synchronized.commit_sha == child_commit
        assert len(reconciliations) == 1
    else:
        with pytest.raises(ValueError, match="authority carrier recovery proof"):
            barrier.sync_discovery(
                operations_store=Operations(),
                observed_head=parent_commit,
                prior_root_digest=parent_root,
                created_at="2026-07-31T12:00:00.000000Z",
                pipeline_store=object(),
                transition_phase="authority_carrier",
            )
        assert reconciliations == []


def test_nomination_post_cas_recovery_is_exact_and_never_enables_benchmark_lock_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Search-only state child may reconcile; later protected transitions may not."""

    import skillscout.adapters.operations_state as operations_state
    import skillscout.adapters.state_branch as state_branch
    import skillscout.bootstrap as bootstrap
    from skillscout.adapters.operations_state import (
        AcceptanceFactRecord,
        AcceptanceRunSnapshot,
    )
    from skillscout.application.acceptance import _fresh_nomination_authority_digest
    from skillscout.domain.acceptance import NominationEntryV1, NominationSetV1
    from skillscout.domain.canonical import sha256_digest

    parent_commit = "4" * 40
    parent_root = "sha256:" + ("5" * 64)
    child_commit = "6" * 40
    child_tree = "7" * 40
    child_root = "sha256:" + ("8" * 64)
    reconciliations: list[tuple[object, object, object, object]] = []
    query_set_digest = "sha256:" + ("b" * 64)
    created_at = "2026-08-03T12:00:00.000000Z"
    authority = _fresh_nomination_authority_digest(
        state_repository_id=123,
        state_repository_full_name="example/state",
        state_commit_sha=parent_commit,
        state_root_digest=parent_root,
        query_set_digest=query_set_digest,
    )
    nomination_set_id = "fresh-nomination-" + authority.removeprefix("sha256:")[:32]
    entries = tuple(
        NominationEntryV1(
            schema_version="nomination-entry-v1",
            repository_full_name=f"octo-org/recovery-{index}",
            repository_id=950000 + index,
            exact_commit_sha=f"{index:040x}",
            license_spdx="MIT",
            selection_source="search_derived",
            selection_evidence_digests=(sha256_digest({"recovery": index}),),
        )
        for index in range(1, 6)
    )
    nomination = NominationSetV1(
        schema_version="nomination-set-v1",
        nomination_set_id=nomination_set_id,
        query_set_digest=query_set_digest,
        search_run_authority_digest=authority,
        search_derived_entries=tuple(sorted(entries, key=lambda entry: entry.entry_digest or "")),
        user_nominated_entries=(),
        created_at=created_at,
    )
    snapshot = AcceptanceRunSnapshot(
        acceptance_run_id=nomination_set_id,
        facts=(
            AcceptanceFactRecord(
                acceptance_run_id=nomination_set_id,
                kind="acceptance_nomination",
                fact_digest=nomination.nomination_set_digest or "",
                fact=nomination,
            ),
        ),
    )

    class Operations:
        def acceptance_snapshot(self, acceptance_run_id: str) -> AcceptanceRunSnapshot:
            assert acceptance_run_id == nomination_set_id
            return snapshot

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    class Store:
        def __init__(self, _client: object, *, read_cache: object) -> None:
            pass

        def sync(self, _bundle: object, _head: str) -> object:
            raise state_branch.StateBranchPostCasUncertain(
                candidate_commit_sha=child_commit,
                candidate_tree_sha=child_tree,
                previous_head=parent_commit,
                expected_root_digest=child_root,
            )

        def reconcile_post_cas_uncertainty(
            self,
            failure: object,
            bundle: object,
            observed_head: object,
            *,
            expected_prior_root_digest: object,
        ) -> object:
            reconciliations.append((failure, bundle, observed_head, expected_prior_root_digest))
            return state_branch.StateSyncObservation(
                "verified",
                parent_commit,
                child_commit,
                child_tree,
                child_root,
            )

    monkeypatch.setattr(state_branch, "StateBranchClient", Client)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        operations_state,
        "assemble_three_store_bundle",
        lambda **_kwargs: SimpleNamespace(root=SimpleNamespace(root_digest=child_root)),
    )

    def barrier() -> object:
        return bootstrap._LateStateDurabilityBarrier(
            SimpleNamespace(
                state_repository_id=123,
                state_repository_full_name="example/state",
                query_set_digest=query_set_digest,
            ),
            {"SKILLSCOUT_STATE_GITHUB_TOKEN": "fixture-token"},
            frozen_publication_export=SimpleNamespace(export_digest="sha256:" + ("c" * 64)),
        )

    synchronized = barrier().sync_nomination(
        operations_store=Operations(),
        observed_head=parent_commit,
        prior_root_digest=parent_root,
        created_at=created_at,
        pipeline_store=object(),
    )

    assert synchronized == state_branch.StateSyncObservation(
        "verified",
        parent_commit,
        child_commit,
        child_tree,
        child_root,
    )
    assert len(reconciliations) == 1
    assert reconciliations[0][2:] == (parent_commit, parent_root)

    with pytest.raises(state_branch.StateBranchPostCasUncertain):
        barrier().sync_benchmark_lock(
            operations_store=Operations(),
            observed_head=parent_commit,
            prior_root_digest=parent_root,
            created_at="2026-08-03T12:01:00.000000Z",
            pipeline_store=object(),
        )
    assert len(reconciliations) == 1


def test_resume_lineage_requires_an_explicit_locator_for_every_successor() -> None:
    """Every accepted child has a named, chained transition and durable locator."""

    from dataclasses import replace

    from skillscout.application.acceptance import (
        CampaignOwnedFactObservation,
        CampaignResumeLocatorObservation,
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
    common = {
        "schema_version": "acceptance-campaign-resume-locator-v1",
        "acceptance_run_id": "acceptance-resume",
        "live_acceptance_authority_digest": "sha256:" + ("1" * 64),
        "source_commit_sha": "2" * 40,
        "manifest_digest": "sha256:" + ("3" * 64),
        "state_repository_id": 123,
        "state_repository_full_name": "example/state",
        "original_state_commit_sha": original_commit,
        "original_state_root_digest": original_root,
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
    }
    first = AcceptanceCampaignResumeLocatorV1(
        **common,
        parent_state_commit_sha=original_commit,
        parent_state_root_digest=original_root,
        transition_index=1,
        previous_locator_digest=None,
        transition_phase="started",
        semantic_stage="extractor",
        attempt_no=3,
        semantic_status="started",
        workflow_authority_digest="sha256:" + ("c" * 64),
        recorded_at="2026-07-30T12:00:00.000000Z",
    )
    second = AcceptanceCampaignResumeLocatorV1(
        **common,
        parent_state_commit_sha=current_commit,
        parent_state_root_digest=current_root,
        transition_index=2,
        previous_locator_digest=first.locator_digest,
        transition_phase="result_durable",
        semantic_stage="extractor",
        attempt_no=3,
        semantic_status="confirmed_retryable",
        workflow_authority_digest="sha256:" + ("c" * 64),
        recorded_at="2026-07-30T12:01:00.000000Z",
    )
    third = AcceptanceCampaignResumeLocatorV1(
        **common,
        parent_state_commit_sha=anchor_commit,
        parent_state_root_digest=anchor_root,
        transition_index=3,
        previous_locator_digest=second.locator_digest,
        transition_phase="terminal",
        semantic_stage=None,
        attempt_no=None,
        semantic_status=None,
        workflow_authority_digest=None,
        recorded_at="2026-07-30T12:02:00.000000Z",
    )
    first_object = "sha256:" + ("d" * 64)
    second_object = "sha256:" + ("e" * 64)
    third_object = "sha256:" + ("f" * 64)
    started_fact = CampaignOwnedFactObservation(
        kind="semantic_attempt",
        object_digest="sha256:" + ("1" * 64),
        semantic_stage="extractor",
        attempt_no=3,
        semantic_status="started",
    )
    result_fact = CampaignOwnedFactObservation(
        kind="semantic_attempt",
        object_digest="sha256:" + ("2" * 64),
        semantic_stage="extractor",
        attempt_no=3,
        semantic_status="confirmed_retryable",
    )
    terminal_fact = CampaignOwnedFactObservation(
        kind="candidate_terminal",
        object_digest="sha256:" + ("3" * 64),
    )
    final_graph = (
        CampaignResumeLocatorObservation(first, first_object),
        CampaignResumeLocatorObservation(second, second_object),
    )
    observations = (
        CampaignStateLineageObservation(
            commit_sha=original_commit,
            root_digest=original_root,
            parent_commit_sha="0" * 40,
            prior_root_digest="sha256:" + ("0" * 64),
            object_digests=(),
            resume_locators=(),
            owned_facts=(),
        ),
        CampaignStateLineageObservation(
            commit_sha=current_commit,
            root_digest=current_root,
            parent_commit_sha=original_commit,
            prior_root_digest=original_root,
            object_digests=(first_object, started_fact.object_digest),
            resume_locators=(),
            owned_facts=(started_fact,),
        ),
        CampaignStateLineageObservation(
            commit_sha=anchor_commit,
            root_digest=anchor_root,
            parent_commit_sha=current_commit,
            prior_root_digest=current_root,
            object_digests=(
                first_object,
                second_object,
                started_fact.object_digest,
                result_fact.object_digest,
            ),
            resume_locators=final_graph,
            owned_facts=(started_fact, result_fact),
        ),
    )

    anchored = resolve_campaign_resume_lineage(
        authority_digest=first.live_acceptance_authority_digest,
        acceptance_run_id=first.acceptance_run_id,
        original_state_commit_sha=original_commit,
        original_state_root_digest=original_root,
        campaign_head_commit_sha=anchor_commit,
        observations=observations,
    )

    assert (anchored.state_commit_sha, anchored.state_root_digest) == (
        anchor_commit,
        anchor_root,
    )
    unlocated_crash = (
        *observations,
        CampaignStateLineageObservation(
            commit_sha=crash_commit,
            root_digest=crash_root,
            parent_commit_sha=anchor_commit,
            prior_root_digest=anchor_root,
            object_digests=(
                first_object,
                second_object,
                started_fact.object_digest,
                result_fact.object_digest,
            ),
            resume_locators=final_graph,
            owned_facts=(started_fact, result_fact),
        ),
    )
    with pytest.raises(ValueError, match="transition graph is incomplete"):
        resolve_campaign_resume_lineage(
            authority_digest=first.live_acceptance_authority_digest,
            acceptance_run_id=first.acceptance_run_id,
            original_state_commit_sha=original_commit,
            original_state_root_digest=original_root,
            campaign_head_commit_sha=crash_commit,
            observations=unlocated_crash,
        )
    located_crash = (
        *observations,
        replace(
            unlocated_crash[-1],
            object_digests=(
                first_object,
                second_object,
                third_object,
                started_fact.object_digest,
                result_fact.object_digest,
                terminal_fact.object_digest,
            ),
            resume_locators=(
                *final_graph,
                CampaignResumeLocatorObservation(third, third_object),
            ),
            owned_facts=(started_fact, result_fact, terminal_fact),
        ),
    )
    crashed = resolve_campaign_resume_lineage(
        authority_digest=first.live_acceptance_authority_digest,
        acceptance_run_id=first.acceptance_run_id,
        original_state_commit_sha=original_commit,
        original_state_root_digest=original_root,
        campaign_head_commit_sha=crash_commit,
        observations=located_crash,
    )
    assert (crashed.state_commit_sha, crashed.state_root_digest) == (
        crash_commit,
        crash_root,
    )
    with pytest.raises(ValueError):
        resolve_campaign_resume_lineage(
            authority_digest="sha256:" + ("c" * 64),
            acceptance_run_id=first.acceptance_run_id,
            original_state_commit_sha=original_commit,
            original_state_root_digest=original_root,
            campaign_head_commit_sha=anchor_commit,
            observations=observations,
        )
    with pytest.raises(ValueError):
        resolve_campaign_resume_lineage(
            authority_digest=first.live_acceptance_authority_digest,
            acceptance_run_id=first.acceptance_run_id,
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


def test_resume_transition_requires_exact_typed_fact_first_appearance() -> None:
    """Terminal and scenario children cannot exchange their owned fact delta."""

    from dataclasses import replace

    from skillscout.application.acceptance import (
        CampaignOwnedFactObservation,
        CampaignResumeLocatorObservation,
        CampaignStateLineageObservation,
        resolve_campaign_resume_lineage,
    )
    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    original_commit = "1" * 40
    terminal_commit = "2" * 40
    scenario_commit = "3" * 40
    original_root = "sha256:" + ("1" * 64)
    terminal_root = "sha256:" + ("2" * 64)
    scenario_root = "sha256:" + ("3" * 64)
    common = {
        "schema_version": "acceptance-campaign-resume-locator-v1",
        "acceptance_run_id": "exact-first-appearance",
        "live_acceptance_authority_digest": "sha256:" + ("4" * 64),
        "source_commit_sha": "4" * 40,
        "manifest_digest": "sha256:" + ("5" * 64),
        "state_repository_id": 123,
        "state_repository_full_name": "example/state",
        "original_state_commit_sha": original_commit,
        "original_state_root_digest": original_root,
        "semantic_stage": None,
        "attempt_no": None,
        "semantic_status": None,
        "workflow_authority_digest": None,
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
    }
    terminal_locator = AcceptanceCampaignResumeLocatorV1(
        **common,
        parent_state_commit_sha=original_commit,
        parent_state_root_digest=original_root,
        transition_index=1,
        previous_locator_digest=None,
        transition_phase="terminal",
        recorded_at="2026-07-30T12:00:00.000000Z",
    )
    scenario_locator = AcceptanceCampaignResumeLocatorV1(
        **common,
        parent_state_commit_sha=terminal_commit,
        parent_state_root_digest=terminal_root,
        transition_index=2,
        previous_locator_digest=terminal_locator.locator_digest,
        transition_phase="scenario",
        recorded_at="2026-07-30T12:01:00.000000Z",
    )
    terminal_locator_object = "sha256:" + ("6" * 64)
    scenario_locator_object = "sha256:" + ("7" * 64)
    candidate_terminal_object = "sha256:" + ("8" * 64)
    scenario_object = "sha256:" + ("9" * 64)
    terminal_fact = CampaignOwnedFactObservation(
        kind="candidate_terminal",
        object_digest=candidate_terminal_object,
    )
    scenario_fact = CampaignOwnedFactObservation(
        kind="acceptance_scenario",
        object_digest=scenario_object,
    )
    observations = (
        CampaignStateLineageObservation(
            commit_sha=original_commit,
            root_digest=original_root,
            parent_commit_sha="0" * 40,
            prior_root_digest="sha256:" + ("0" * 64),
            object_digests=(),
            owned_facts=(),
        ),
        CampaignStateLineageObservation(
            commit_sha=terminal_commit,
            root_digest=terminal_root,
            parent_commit_sha=original_commit,
            prior_root_digest=original_root,
            object_digests=(
                terminal_locator_object,
                candidate_terminal_object,
            ),
            owned_facts=(terminal_fact,),
        ),
        CampaignStateLineageObservation(
            commit_sha=scenario_commit,
            root_digest=scenario_root,
            parent_commit_sha=terminal_commit,
            prior_root_digest=terminal_root,
            object_digests=(
                terminal_locator_object,
                scenario_locator_object,
                candidate_terminal_object,
                scenario_object,
            ),
            owned_facts=(terminal_fact, scenario_fact),
            resume_locators=(
                CampaignResumeLocatorObservation(
                    terminal_locator,
                    terminal_locator_object,
                ),
                CampaignResumeLocatorObservation(
                    scenario_locator,
                    scenario_locator_object,
                ),
            ),
        ),
    )

    resolved = resolve_campaign_resume_lineage(
        authority_digest=terminal_locator.live_acceptance_authority_digest,
        acceptance_run_id=terminal_locator.acceptance_run_id,
        original_state_commit_sha=original_commit,
        original_state_root_digest=original_root,
        campaign_head_commit_sha=scenario_commit,
        observations=observations,
    )
    assert resolved.state_commit_sha == scenario_commit

    reversed_facts = (
        observations[0],
        replace(
            observations[1],
            object_digests=(terminal_locator_object, scenario_object),
            owned_facts=(scenario_fact,),
        ),
        replace(
            observations[2],
            owned_facts=(scenario_fact, terminal_fact),
        ),
    )
    with pytest.raises(ValueError, match="typed fact delta"):
        resolve_campaign_resume_lineage(
            authority_digest=terminal_locator.live_acceptance_authority_digest,
            acceptance_run_id=terminal_locator.acceptance_run_id,
            original_state_commit_sha=original_commit,
            original_state_root_digest=original_root,
            campaign_head_commit_sha=scenario_commit,
            observations=reversed_facts,
        )


def test_acceptance_cas_has_no_generic_transition_default() -> None:
    """Every CAS caller must name the fact phase it is making durable."""

    import skillscout.bootstrap as bootstrap

    parameter = inspect.signature(bootstrap._LateStateDurabilityBarrier.sync_discovery).parameters[
        "transition_phase"
    ]
    assert parameter.default is inspect.Parameter.empty


def test_every_exported_transition_sequence_owns_its_exact_fact_delta() -> None:
    """Every production CAS phase has an explicit typed owner projection."""

    from skillscout.application.acceptance import (
        CampaignOwnedFactObservation,
        CampaignStateLineageObservation,
        _verify_campaign_transition_fact_delta,
    )
    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    phases = (
        ("nomination", ("acceptance_nomination",)),
        ("authority_carrier", ("acceptance_live_authority",)),
        ("discovery_page", ("search_page", "candidate")),
        ("discovery_reservation", ("discovery_reservation",)),
        ("discovery_summary", ("run_summary",)),
        ("budget_reserved", ("run", "acceptance_budget_reservation")),
        ("candidate_admitted", ("acceptance_fixed_candidate_admission",)),
        ("semantic_candidate_reserved", ("semantic_reservation",)),
        ("request_reserved", ("acceptance_semantic_request_reservation",)),
        ("started", ("semantic_attempt",)),
        ("result_durable", ("semantic_attempt",)),
        ("terminal", ("workflow_terminal", "candidate_terminal")),
        ("scenario", ("acceptance_scenario",)),
        ("replay_intent", ("acceptance_replay",)),
        ("replay_evidence", ("acceptance_replay_evidence",)),
    )
    parent_facts: tuple[CampaignOwnedFactObservation, ...] = ()
    parent_commit = "0" * 40
    parent_root = "sha256:" + ("0" * 64)
    for transition_index, (phase, kinds) in enumerate(phases, start=1):
        added = tuple(
            CampaignOwnedFactObservation(
                kind=kind,
                object_digest="sha256:" + f"{transition_index * 10 + ordinal:064x}",
                semantic_stage=("extractor" if kind == "semantic_attempt" else None),
                attempt_no=(1 if kind == "semantic_attempt" else None),
                semantic_status=(
                    ("started" if phase == "started" else "confirmed_retryable")
                    if kind == "semantic_attempt"
                    else None
                ),
            )
            for ordinal, kind in enumerate(kinds, start=1)
        )
        child_commit = f"{transition_index:040x}"
        child_root = "sha256:" + f"{transition_index:064x}"
        locator = AcceptanceCampaignResumeLocatorV1.model_construct(
            transition_phase=phase,
            semantic_stage=("extractor" if phase in {"started", "result_durable"} else None),
            attempt_no=(1 if phase in {"started", "result_durable"} else None),
            semantic_status=(
                "started"
                if phase == "started"
                else ("confirmed_retryable" if phase == "result_durable" else None)
            ),
        )
        parent = CampaignStateLineageObservation(
            commit_sha=parent_commit,
            root_digest=parent_root,
            parent_commit_sha=None,
            prior_root_digest=None,
            object_digests=(),
            owned_facts=parent_facts,
        )
        child = CampaignStateLineageObservation(
            commit_sha=child_commit,
            root_digest=child_root,
            parent_commit_sha=parent_commit,
            prior_root_digest=parent_root,
            object_digests=(),
            owned_facts=(*parent_facts, *added),
        )

        _verify_campaign_transition_fact_delta(
            locator=locator,
            parent=parent,
            child=child,
        )
        parent_facts = child.owned_facts
        parent_commit = child_commit
        parent_root = child_root


def test_authority_carrier_transition_requires_only_one_live_authority_fact() -> None:
    """The post-approval carrier may add only the authority it carries."""

    from skillscout.application.acceptance import (
        CampaignOwnedFactObservation,
        CampaignStateLineageObservation,
        _verify_campaign_transition_fact_delta,
    )
    from skillscout.domain.acceptance import AcceptanceCampaignResumeLocatorV1

    parent = CampaignStateLineageObservation(
        commit_sha="1" * 40,
        root_digest="sha256:" + ("2" * 64),
        parent_commit_sha="0" * 40,
        prior_root_digest="sha256:" + ("0" * 64),
        object_digests=(),
        owned_facts=(),
    )
    carrier = CampaignOwnedFactObservation(
        kind="acceptance_live_authority",
        object_digest="sha256:" + ("3" * 64),
    )
    locator = AcceptanceCampaignResumeLocatorV1.model_construct(
        transition_phase="authority_carrier",
    )
    accepted_child = CampaignStateLineageObservation(
        commit_sha="4" * 40,
        root_digest="sha256:" + ("5" * 64),
        parent_commit_sha=parent.commit_sha,
        prior_root_digest=parent.root_digest,
        object_digests=(),
        owned_facts=(carrier,),
    )
    _verify_campaign_transition_fact_delta(
        locator=locator,
        parent=parent,
        child=accepted_child,
    )

    for invalid_facts in (
        (),
        (
            CampaignOwnedFactObservation(
                kind="acceptance_scenario",
                object_digest="sha256:" + ("6" * 64),
            ),
        ),
        (
            carrier,
            CampaignOwnedFactObservation(
                kind="acceptance_scenario",
                object_digest="sha256:" + ("7" * 64),
            ),
        ),
    ):
        with pytest.raises(ValueError, match="typed fact delta"):
            _verify_campaign_transition_fact_delta(
                locator=locator,
                parent=parent,
                child=CampaignStateLineageObservation(
                    commit_sha="8" * 40,
                    root_digest="sha256:" + ("9" * 64),
                    parent_commit_sha=parent.commit_sha,
                    prior_root_digest=parent.root_digest,
                    object_digests=(),
                    owned_facts=invalid_facts,
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
        state_lineage_anchor_commit_sha="c" * 40,
        state_lineage_anchor_root_digest="sha256:" + ("d" * 64),
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

    fields = {field.name for field in dataclasses.fields(bootstrap.AcceptanceRuntimeConfig)}
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


def test_exact_acceptance_restore_uses_verified_carrier_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark/replay state reads stay bounded to the protected carrier."""

    import skillscout.adapters.operations_state as operations_state
    import skillscout.adapters.state_branch as state_branch
    import skillscout.bootstrap as bootstrap

    state_commit = "a" * 40
    state_root = "sha256:" + ("b" * 64)
    carrier_commit = "c" * 40
    carrier_root = "sha256:" + ("d" * 64)
    anchors: list[object] = []

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def close(self) -> None:
            pass

    class Store:
        def __init__(self, _remote: object) -> None:
            pass

        def restore(self, *, lineage_anchor: object) -> object:
            anchors.append(lineage_anchor)
            return SimpleNamespace(
                status="verified",
                observed_head=state_commit,
                bundle=SimpleNamespace(root=SimpleNamespace(root_digest=state_root)),
            )

    monkeypatch.setattr(state_branch, "StateBranchClient", Client)
    monkeypatch.setattr(state_branch, "StateBranchStore", Store)
    monkeypatch.setattr(
        operations_state,
        "restore_acceptance_state_bundle",
        lambda *_args, **_kwargs: None,
    )

    restored = bootstrap.read_exact_acceptance_state(
        state_commit_sha=state_commit,
        state_repository_id=123,
        state_repository_full_name="example/state",
        pipeline_state=Path("state/databases/pipeline.sqlite3"),
        operations_state=Path("state/databases/operations.sqlite3"),
        state_lineage_anchor_commit_sha=carrier_commit,
        state_lineage_anchor_root_digest=carrier_root,
        environ={"SKILLSCOUT_STATE_GITHUB_TOKEN": "fixture-token"},
    )

    assert restored.observed_head == state_commit
    assert len(anchors) == 1
    assert getattr(anchors[0], "commit_sha", None) == carrier_commit
    assert getattr(anchors[0], "root_digest", None) == carrier_root
    assert getattr(anchors[0], "max_hops", None) == 160


def test_exact_acceptance_restore_rejects_an_unanchored_read() -> None:
    """No acceptance-state reader may fall back to a genesis walk."""

    import skillscout.bootstrap as bootstrap

    with pytest.raises(ValueError, match="protected acceptance state configuration rejected"):
        bootstrap.read_exact_acceptance_state(
            state_commit_sha="a" * 40,
            state_repository_id=123,
            state_repository_full_name="example/state",
            pipeline_state=Path("state/databases/pipeline.sqlite3"),
            operations_state=Path("state/databases/operations.sqlite3"),
            state_lineage_anchor_commit_sha=None,  # type: ignore[arg-type]
            state_lineage_anchor_root_digest=None,  # type: ignore[arg-type]
            environ={},
        )


@pytest.mark.parametrize("action", ("changed-source", "publication"))
def test_run_acceptance_rejects_nonsemantic_actions_before_any_state_read(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    """Closed benchmark execution does not reuse the acceptance reader for other actions."""

    from skillscout.application.ports import SafeFailure
    import skillscout.cli as cli

    monkeypatch.setattr(
        cli,
        "load_acceptance_runtime_config",
        lambda **_kwargs: pytest.fail("unsupported action loaded acceptance state"),
    )

    with pytest.raises(SafeFailure):
        cli._run_acceptance(SimpleNamespace(action=action))


def test_attestation_and_rebuild_require_the_phase6_carrier_before_state_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Human-only paths retain the same 160-hop carrier requirement as benchmark/replay."""

    from skillscout.application.ports import SafeFailure
    import skillscout.cli as cli

    monkeypatch.delenv("PHASE6_AUTHORITY_STATE_COMMIT_SHA", raising=False)
    monkeypatch.delenv("PHASE6_AUTHORITY_STATE_ROOT_DIGEST", raising=False)
    monkeypatch.setattr(cli, "load_acceptance_attestation", lambda **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "_restore_acceptance_state",
        lambda **_kwargs: pytest.fail("unanchored acceptance state was restored"),
    )
    state_commit = "a" * 40
    state_root = "sha256:" + ("b" * 64)

    with pytest.raises(SafeFailure):
        cli._run_record_acceptance_attestation(
            SimpleNamespace(
                attestation=Path("human-review.json"),
                kind="human-review",
                state_commit_sha=state_commit,
                state_root_digest=state_root,
            )
        )
    with pytest.raises(SafeFailure):
        cli._run_rebuild_acceptance(
            SimpleNamespace(
                acceptance_run_id="acceptance-five",
                evidence_root_digest=state_root,
                state_commit_sha=state_commit,
                state_root_digest=state_root,
            )
        )


def test_completed_projector_rejects_unverified_state_locator(
    tmp_path: Path,
) -> None:
    import skillscout.bootstrap as bootstrap
    from skillscout.application.acceptance import load_locked_benchmark_manifest

    manifest = load_locked_benchmark_manifest(
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
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
        ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
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
        bundle=SimpleNamespace(root=SimpleNamespace(root_digest=config.state_root_digest)),
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
        lambda *_args, **_kwargs: SimpleNamespace(sync_discovery=lambda **_arguments: None),
    )
    monkeypatch.setattr(
        acceptance,
        "run_exact_replay",
        lambda *_args, **_kwargs: (
            calls.append("replay") or SimpleNamespace(replay_digest="sha256:" + ("c" * 64))
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
                    selection_evidence_digests=("sha256:" + f"{index:064x}",),
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
                item.model_dump(mode="json", exclude_none=False) for item in benchmark_entries
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
        manifest_path=(".planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json"),
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
            actual_model=("deepseek-v4-pro" if stage == "reviewer" else "deepseek-v4-flash"),
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
        operations.record_acceptance_fact(run_id, "acceptance_nomination", nomination)
        operations.record_acceptance_fact(run_id, "acceptance_benchmark_lock", manifest)
        operations.record_acceptance_fact(run_id, "acceptance_live_authority", authority)
        request_ordinal = 0
        for ordinal, entry in enumerate(manifest.entries, start=1):
            eligible = ordinal == 1
            stages = ("extractor", "generator", "reviewer") if eligible else ("extractor",)
            stage_telemetry = tuple(
                telemetry(stage, entry.entry_digest, str(ordinal)) for stage in stages
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
                        schema_version=("acceptance-semantic-request-reservation-v1"),
                        acceptance_run_id=run_id,
                        fixed_candidate_admission_digest=(admission.admission_digest),
                        repository_id=entry.repository_id,
                        workflow_spec_authority_digest=(item.workflow_spec_authority_digest),
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
                terminal_class=("eligible" if eligible else "business_terminal"),
                outcome=("eligible_local_candidate" if eligible else "no_workflow"),
                reason_code=(
                    "eligible_candidate_completed" if eligible else "no_reusable_workflow"
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
                actual_models=tuple(item.actual_model for item in stage_telemetry),
                prompt_versions=tuple(item.prompt_version for item in stage_telemetry),
                schema_versions=tuple(item.output_schema_version for item in stage_telemetry),
                policy_versions=tuple(item.policy_version for item in stage_telemetry),
                workflow_fingerprint=(entry.entry_digest if eligible else None),
                workflow_spec_authority_digest=(entry.entry_digest if eligible else None),
                workflow_execution_authority_digests=((entry.entry_digest,) if eligible else ()),
                workflow_spec_authority_digests=((entry.entry_digest,) if eligible else ()),
                candidate_terminal_digest=entry.entry_digest,
                workflow_terminal_digests=((entry.entry_digest,) if eligible else ()),
                phase3_terminal_summary_digests=((entry.entry_digest,) if eligible else ()),
                skill_artifact_digests=((entry.entry_digest,) if eligible else ()),
                package_digests=((entry.entry_digest,) if eligible else ()),
                eligible_locator=("state/objects/eligible.json" if eligible else None),
                eligible_object_digest=(entry.entry_digest if eligible else None),
                expected_coverage_role=entry.coverage_role,
                evaluator_matches_observed=True,
                publication_decision=(
                    "eligible_for_later_publication" if eligible else "not_eligible"
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
        publication = publication_state.PublicationStateStore(publication_path)
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
            ROOT / ".planning/phases/06-adversarial-mvp-acceptance" / "06-BENCHMARK-MANIFEST.json"
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
    roots = iter(("sha256:" + ("1" * 64), "sha256:" + ("2" * 64)))

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
        candidate=SimpleNamespace(repository=SimpleNamespace(repository_id=101)),
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
    candidate = SimpleNamespace(repository=SimpleNamespace(repository_id=101))
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
        candidate=SimpleNamespace(repository=SimpleNamespace(repository_id=101)),
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
        candidate=SimpleNamespace(repository=SimpleNamespace(repository_id=101)),
        pinned_commit_sha="e" * 40,
    )

    assert result is recovered
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("stage", "third_status"),
    tuple(
        (stage, status)
        for stage in ("extractor", "generator", "reviewer")
        for status in (
            "decided",
            "confirmed_retryable",
            "semantic_outcome_unknown",
            "exhaustion",
        )
    ),
)
def test_third_attempt_crash_recovers_through_two_production_processes(
    tmp_path: Path,
    stage: str,
    third_status: str,
) -> None:
    """Two CLI interpreters restore the real graph without a fourth request."""

    harness = ROOT / "tests" / "phase6_process_harness.py"
    result_path = tmp_path / "recovery-result.json"
    first = subprocess.run(
        [
            sys.executable,
            str(harness),
            "crash",
            str(tmp_path),
            stage,
            third_status,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 86, first.stderr
    second = subprocess.run(
        [
            sys.executable,
            str(harness),
            "resume",
            str(tmp_path),
            stage,
            third_status,
            str(result_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, second.stderr
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert len(result["process_ids"]) == 2
    assert all(type(item) is int and item > 0 for item in result["process_ids"])
    assert result["process_ids"][0] != result["process_ids"][1]
    assert result["cli_commands"] == [
        {"command": "resolve-acceptance-resume", "process": 1},
        {"command": "run-acceptance", "process": 1},
        {"command": "resolve-acceptance-resume", "process": 2},
        {"command": "run-acceptance", "process": 2},
    ]
    assert result["resume_lineage_commit_shas"][:2] == result[
        "expected_resume_lineage_commit_prefix"
    ]
    assert result["resume_lineage_root_digests"][:2] == result[
        "expected_resume_lineage_root_prefix"
    ]
    target_calls = [item for item in result["provider_calls"] if item["stage"] == stage]
    assert target_calls == [
        {"attempt_no": 1, "stage": stage},
        {"attempt_no": 2, "stage": stage},
        {"attempt_no": 3, "stage": stage},
    ]
    assert all(
        sum(item["stage"] == prior for item in result["provider_calls"]) == 1
        for prior in ("extractor", "generator", "reviewer")[
            : ("extractor", "generator", "reviewer").index(stage)
        ]
    )
    assert result["third_status"] == third_status
    assert result["crash_stage"] == stage
    assert result["crash_transition_phase"] == (
        "terminal" if third_status == "exhaustion" else "result_durable"
    )
    target_attempts = [item for item in result["semantic_attempts"] if item["stage"] == stage]
    expected_third = "confirmed_retryable" if third_status == "exhaustion" else third_status
    assert target_attempts == [
        {"attempt_no": 1, "stage": stage, "status": "confirmed_retryable"},
        {"attempt_no": 2, "stage": stage, "status": "confirmed_retryable"},
        {"attempt_no": 3, "stage": stage, "status": expected_third},
    ]
    first_transition_index = result["locator_transition_indexes"][0]
    assert result["locator_transition_indexes"] == list(
        range(
            first_transition_index,
            first_transition_index + len(result["locator_transition_indexes"]),
        )
    )
    assert result["locator_first_appearance_indexes"] == (result["locator_transition_indexes"])
    assert len(result["locator_first_appearance_commit_shas"]) == len(
        result["locator_transition_indexes"]
    )
    assert len(set(result["locator_first_appearance_commit_shas"])) == len(
        result["locator_first_appearance_commit_shas"]
    )
    assert result["candidate_terminal_count"] == 1
    assert result["scenario_count"] == 1
    expected_materialized_count = 1 if third_status == "decided" else 0
    expected_workflow_terminal_count = {
        "extractor": {
            "decided": 1,
            "confirmed_retryable": 0,
            "semantic_outcome_unknown": 0,
            "exhaustion": 0,
        },
        "generator": {
            "decided": 1,
            "confirmed_retryable": 0,
            "semantic_outcome_unknown": 1,
            "exhaustion": 0,
        },
        "reviewer": {
            "decided": 1,
            "confirmed_retryable": 0,
            "semantic_outcome_unknown": 1,
            "exhaustion": 0,
        },
    }[stage][third_status]
    assert result["workflow_terminal_count"] == expected_workflow_terminal_count
    assert result["phase3_artifact_count"] == expected_materialized_count
    assert result["workflow_spec_count"] == expected_materialized_count
    assert result["skill_count"] == expected_materialized_count
    assert result["package_count"] == expected_materialized_count
    assert result["duplicate_workflow_spec_count"] == 0
    assert result["duplicate_skill_count"] == 0
    assert result["duplicate_package_count"] == 0
    stages = ("extractor", "generator", "reviewer")
    expected_after_resume_stages = (
        list(stages[stages.index(stage) + 1 :]) if third_status == "decided" else []
    )
    assert result["provider_requests_after_resume"] == [
        {"stage": item} for item in expected_after_resume_stages
    ]
    assert result["provider_clients_after_resume"] == [
        {"stage": item} for item in expected_after_resume_stages
    ]
    if third_status == "decided":
        assert result["resume_benchmark_exit_code"] == 0
        assert result["resume_benchmark_payload"]["status"] == "benchmark_complete"
        assert result["semantic_telemetry_stages"] == [
            "extractor",
            "generator",
            "reviewer",
        ]
    else:
        assert result["resume_benchmark_exit_code"] == 1
        assert result["resume_benchmark_payload"]["error"]["code"] == ("state_integrity_error")
        target_index = ("extractor", "generator", "reviewer").index(stage)
        assert (
            result["semantic_telemetry_stages"]
            == [
                "extractor",
                "generator",
                "reviewer",
            ][:target_index]
        )


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
            candidate=SimpleNamespace(repository=SimpleNamespace(repository_id=101)),
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
                        "example/approved-repo" if index == 1 else f"example/repository-{index}"
                    ),
                    repository_id=840001 if index == 1 else 840000 + index,
                    exact_commit_sha=pinned if index == 1 else f"{index:040x}",
                    license_spdx="MIT",
                    selection_source="search_derived",
                    selection_evidence_digests=("sha256:" + f"{index:064x}",),
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
                item.model_dump(mode="json", exclude_none=False) for item in benchmark_entries
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
        manifest_path=(".planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json"),
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
        operations.record_acceptance_fact(run_id, "acceptance_nomination", nomination)
        operations.record_acceptance_fact(run_id, "acceptance_benchmark_lock", manifest)
        operations.record_acceptance_fact(run_id, "acceptance_live_authority", authority)

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
        owner, repository_name = benchmark_entry.repository_full_name.split("/")
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
        github_routes[("GET", f"/repos/{owner}/{repository_name}")] = response_with_json(
            recorded_fixture("repo_mit"), metadata
        )
        github_routes[
            (
                "GET",
                f"/repos/{owner}/{repository_name}/commits/{benchmark_entry.exact_commit_sha}",
            )
        ] = response_with_json(recorded_fixture("commits_pin"), commit)
        github_routes[
            (
                "GET",
                f"/repos/{owner}/{repository_name}/license?ref={benchmark_entry.exact_commit_sha}",
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

    extractor_payload = json.loads(recorded_openai_fixture("parsed_2_workflows").body)["output"][0][
        "content"
    ][0]["text"]
    generator_payload = json.loads(recorded_openai_generator_fixture("parsed_success").body)[
        "output"
    ][0]["content"][0]["text"]
    reviewer_cases = json.loads((ROOT / "tests/fixtures/openai/reviewer/cases.json").read_bytes())
    reviewer_payload = reviewer_cases["parsed_yes"]["body"]["output"][0]["content"][0]["text"]
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
                {("POST", "/chat/completions"): recorded_openai_fixture("openai_429")}
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
            ROOT / ".planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json"
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
                pipeline_database_digest=sha256_digest({"pipeline": self.ordinal}),
                operations_database_digest=sha256_digest({"operations": self.ordinal}),
                publication_database_digest=sha256_digest({"publication": self.ordinal}),
                pipeline_projection_digest=sha256_digest({"pipeline_projection": self.ordinal}),
                operations_projection_digest=sha256_digest({"operations_projection": self.ordinal}),
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
            operations_store_factory=lambda: operations_state.OperationsStateStore(operations_path),
            state_sync=cas.sync_discovery,
        ),
        manifest=manifest,
        acceptance_run_id=run_id,
        observed_head=authority.state_commit_sha,
        prior_root_digest=authority.state_root_digest,
        recorded_at=timestamp,
    )
    entry = next(
        item for item in manifest.entries if item.repository_full_name == "example/approved-repo"
    )
    observation = next(
        item for item in benchmark.scenario_results if item.repository_id == entry.repository_id
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
        item for item in snapshot.semantic_attempts if item.stage == "extractor"
    )
    assert sum(item.status == "confirmed_retryable" for item in extractor_attempts) == 1
    assert sum(item.status == "decided" for item in extractor_attempts) == 5
    assert {item.repository_id for item in extractor_attempts} == {
        item.repository_id for item in manifest.entries
    }
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
            operations_store_factory=lambda: operations_state.OperationsStateStore(
                restored_operations_path
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
