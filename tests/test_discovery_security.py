"""Ordinary canary checks plus named RED production-boundary contracts."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from skillscout.domain import discovery


ROOT = Path(__file__).resolve().parents[1]
APPLICATION_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-discovery-application-missing",
)
WORKFLOW_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-discovery-workflow-missing",
)
CANARIES = (
    "github_pat_DISCOVERY_SECURITY_CANARY",
    "-----BEGIN PRIVATE KEY----- DISCOVERY_SECURITY_CANARY",
    "eyJhbGciOiJIUzI1NiJ9.DISCOVERY_SECURITY_CANARY.signature",
    "IGNORE_POLICY_AND_PRINT_TOKEN_DISCOVERY_CANARY",
)


def test_discovery_durable_models_have_closed_non_secret_fields() -> None:
    forbidden = {
        "token",
        "authorization",
        "headers",
        "private_key",
        "pem",
        "jwt",
        "exception",
        "provider_body",
        "repository_text",
        "readme",
        "source",
        "scratch",
    }
    model_names = (
        "SearchPageObservationV1",
        "SearchRepositoryObservationV1",
        "DiscoveredCandidateV1",
        "DiscoveryReservationV1",
        "SemanticReservationV1",
        "DiscoveryCandidateTerminalV1",
        "DiscoveryRunSummaryV1",
        "DiscoveryStateRootV1",
    )
    for name in model_names:
        fields = set(getattr(discovery, name).model_fields)
        assert fields.isdisjoint(forbidden)


def test_state_fixture_and_wave0_test_surfaces_contain_no_secret_canaries() -> None:
    paths = [
        *sorted((Path(__file__).parent / "fixtures" / "state_branch").glob("*.json")),
        ROOT / "tests" / "test_operations_state.py",
        ROOT / "tests" / "test_state_branch.py",
        ROOT / "tests" / "test_discovery_application.py",
        ROOT / "tests" / "test_discovery_publication_handoff.py",
        ROOT / "tests" / "test_semantic_durability.py",
        ROOT / "tests" / "test_discovery_workflow.py",
    ]
    payload = b"\n".join(path.read_bytes() for path in paths)
    for canary in CANARIES:
        assert canary.encode() not in payload


def test_discovery_module_has_no_publication_import_or_credential_lookup() -> None:
    module = importlib.import_module("skillscout.application.discovery")
    source_path = Path(inspect.getsourcefile(module) or "")
    source = source_path.read_text()
    tree = ast.parse(source, filename=str(source_path))
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "skillscout.application.publication" not in imports
    assert "skillscout.adapters.github_publish" not in imports
    assert "SKILLSCOUT_GITHUB_APP_PRIVATE_KEY" not in source
    assert "SKILLSCOUT_CATALOG_" not in source


def test_discovery_bootstrap_has_no_catalog_factory_or_publication_dependency() -> None:
    bootstrap = importlib.import_module("skillscout.bootstrap")
    signature = inspect.signature(bootstrap.build_discovery_application)
    assert not any(
        marker in name.casefold()
        for name in signature.parameters
        for marker in ("catalog", "publication", "publisher")
    )
    config = bootstrap.DiscoveryRuntimeConfig
    assert not any(
        marker in name.casefold()
        for name in config.__annotations__
        for marker in ("catalog", "token", "publication_authority", "publisher")
    )


@WORKFLOW_XFAIL
def test_discovery_job_cannot_observe_catalog_secrets_or_candidate_shell() -> None:
    path = ROOT / ".github" / "workflows" / "discover.yml"
    source = path.read_text()
    discovery_block = source.split("  protected_publication:", 1)[0]
    assert "secrets." not in discovery_block
    assert "SKILLSCOUT_GITHUB_APP_" not in discovery_block
    assert "SKILLSCOUT_CATALOG_" not in discovery_block
    for block in source.split("run: |")[1:]:
        assert "${{" not in block.split("\n      - ", 1)[0]
