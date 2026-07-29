"""Wave-0 RED mutation contracts for the independent Phase 6 rebuild verifier."""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import shutil
import sys
from pathlib import Path
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
