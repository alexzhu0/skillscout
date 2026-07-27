"""Mutation tests for the read-only independent Phase 4 acceptance inspector."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
INSPECTOR_PATH = PROJECT_ROOT / "tools/verify_phase4_acceptance.py"
SPEC = importlib.util.spec_from_file_location("phase4_acceptance", INSPECTOR_PATH)
assert SPEC is not None and SPEC.loader is not None
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)


@pytest.fixture
def acceptance_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(PROJECT_ROOT / "src", repository / "src")
    shutil.copytree(PROJECT_ROOT / ".github", repository / ".github")
    phase = repository / ".planning/phases/04-controlled-draft-pr"
    phase.mkdir(parents=True)
    for name in ("04-08-SUMMARY.md", "04-10-SUMMARY.md"):
        shutil.copy2(
            PROJECT_ROOT / ".planning/phases/04-controlled-draft-pr" / name,
            phase / name,
        )
    return repository


def _replace(repository: Path, relative: str, old: str, new: str) -> None:
    path = repository / relative
    source = path.read_text(encoding="utf-8")
    assert source.count(old) >= 1
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def test_current_tree_passes_with_closed_independent_registry() -> None:
    assert inspector.verify_phase4_acceptance(PROJECT_ROOT) is None
    assert tuple(spec.identifier for spec in inspector.CHECK_REGISTRY) == (
        "domain",
        "adapter",
        "recovery",
        "cli",
        "workflow",
        "human_gates",
        "forbidden_surfaces",
    )
    assert inspector.imported_top_level_modules(INSPECTOR_PATH).isdisjoint(
        {"httpx", "openai", "pydantic", "pytest", "requests", "skillscout", "subprocess"}
    )


@pytest.mark.parametrize(
    ("relative", "old", "new"),
    [
        (
            "src/skillscout/domain/publication.py",
            "class CandidatePublicationEvidenceV1(StrictFrozenModel):",
            "class CandidatePublicationEvidenceWithAuthorityV1(StrictFrozenModel):",
        ),
        (
            "src/skillscout/domain/publication.py",
            "class PublicationIntentV1(StrictFrozenModel):",
            "class OptionalPublicationIntentV1(StrictFrozenModel):",
        ),
        (
            "src/skillscout/domain/publication.py",
            "class MachineLineageV1(StrictFrozenModel):",
            "class WeakLineageV1(StrictFrozenModel):",
        ),
        (
            "src/skillscout/domain/publication.py",
            "reviewers: Annotated[tuple[_LOGIN, ...], Field(min_length=1, max_length=16)]",
            "teams: tuple[str, ...]",
        ),
        (
            "src/skillscout/adapters/github_publish.py",
            '"force": False',
            '"force": True',
        ),
        (
            "src/skillscout/application/publication.py",
            '"sha": None',
            '"sha": stale_sha',
        ),
        (
            "src/skillscout/application/publication.py",
            '"removed_after_request"',
            '"request_again"',
        ),
        (
            "src/skillscout/cli.py",
            "verify_publication_admission_handoff(",
            "trust_publication_admission_handoff(",
        ),
        (
            ".github/workflows/publish-candidate.yml",
            "environment: skillscout-catalog-publish",
            "environment: unprotected",
        ),
        (
            ".planning/phases/04-controlled-draft-pr/04-08-SUMMARY.md",
            "d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622",
            "0" * 64,
        ),
        (
            ".planning/phases/04-controlled-draft-pr/04-10-SUMMARY.md",
            "Default-ref update | 422 | validation",
            "Default-ref update | 200 | success",
        ),
        (
            ".planning/phases/04-controlled-draft-pr/04-10-SUMMARY.md",
            "PRs `#1` and `#2` are closed, not merged.",
            "cleanup pending",
        ),
    ],
)
def test_required_artifact_link_and_evidence_mutations_fail(
    acceptance_repository: Path, relative: str, old: str, new: str
) -> None:
    _replace(acceptance_repository, relative, old, new)
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase4_acceptance(acceptance_repository)


@pytest.mark.parametrize(
    "addition",
    [
        "      publication_intent_digest: ${{ steps.admission.outputs.publication_intent_digest }}\n",
        "      admission_digest: ${{ steps.admission.outputs.admission_digest }}\n",
    ],
)
def test_authority_dependent_digest_cannot_cross_job(
    acceptance_repository: Path, addition: str
) -> None:
    path = acceptance_repository / ".github/workflows/publish-candidate.yml"
    source = path.read_text(encoding="utf-8")
    marker = "      review_attestation_digest: ${{ steps.admission.outputs.review_attestation_digest }}\n"
    assert source.count(marker) == 1
    path.write_text(source.replace(marker, marker + addition), encoding="utf-8")
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase4_acceptance(acceptance_repository)


def test_unprivileged_value_cannot_authorize_protected_digest(
    acceptance_repository: Path,
) -> None:
    _replace(
        acceptance_repository,
        ".github/workflows/publish-candidate.yml",
        "value = protected.get(field)",
        'value = "${{ needs.admit.outputs.admission_digest }}"',
    )
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase4_acceptance(acceptance_repository)


@pytest.mark.parametrize(
    ("relative", "addition"),
    [
        ("src/skillscout/adapters/github_publish.py", "\nimport requests\n"),
        ("src/skillscout/application/publication.py", "\nimport subprocess\n"),
        ("src/skillscout/cli.py", '\nFORBIDDEN = "--merge --approve --mark-ready"\n'),
    ],
)
def test_forbidden_imports_and_production_surfaces_fail(
    acceptance_repository: Path, relative: str, addition: str
) -> None:
    path = acceptance_repository / relative
    path.write_text(path.read_text(encoding="utf-8") + addition, encoding="utf-8")
    with pytest.raises(inspector.AcceptanceError):
        inspector.verify_phase4_acceptance(acceptance_repository)


def test_cli_diagnostics_are_fixed(capsys: pytest.CaptureFixture[str]) -> None:
    assert inspector.main([]) == 0
    assert capsys.readouterr().out == "phase4 acceptance valid\n"
    assert inspector.main(["--repository-root", "/missing"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "phase4 acceptance invalid\n"
