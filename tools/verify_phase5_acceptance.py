#!/usr/bin/env python3
"""Independent standard-library-only, read-only Phase 5 acceptance inspector."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple

MAX_SOURCE_BYTES = 2_000_000
SUCCESS_DIAGNOSTIC = "phase5 acceptance valid"
FAILURE_DIAGNOSTIC = "phase5 acceptance invalid"
PACKAGE = Path("src") / ("skill" + "scout")
DOMAIN = PACKAGE / "domain/discovery.py"
DISCOVERY = PACKAGE / "application/discovery.py"
PORTS = PACKAGE / "application/ports.py"
PIPELINE = PACKAGE / "application/pipeline.py"
PHASE3 = PACKAGE / "application/phase3.py"
SEMANTIC_PROVIDER = PACKAGE / "adapters/semantic_provider.py"
OPERATIONS_STATE = PACKAGE / "adapters/operations_state.py"
PIPELINE_STATE = PACKAGE / "adapters/state.py"
PUBLICATION_STATE = PACKAGE / "adapters/publication_state.py"
STATE_BRANCH = PACKAGE / "adapters/state_branch.py"
BOOTSTRAP = PACKAGE / "bootstrap.py"
CLI = PACKAGE / "cli.py"
QUERY_CONFIG = Path("config/discovery-queries-v1.json")
DISCOVER_WORKFLOW = Path(".github/workflows/discover.yml")
PUBLISH_WORKFLOW = Path(".github/workflows/publish-candidate.yml")
CANARY_WORKFLOW = Path(".github/workflows/gate-b4-canary.yml")
PHASE = Path(".planning/phases/05-automated-discovery-operations")
EVIDENCE = PHASE / "05-HOSTED-GATE-B4-EVIDENCE.json"
APPROVAL = PHASE / "05-HOSTED-GATE-B4-APPROVAL.json"

EXPECTED_DIGESTS = {
    DISCOVER_WORKFLOW: "8157cb686b9bf18bfa800811b1fe1529ed9a15ec371fe36ec1708233052b7cfd",
    PUBLISH_WORKFLOW: "96ce9f39db49ce647a88b83ec4db3cb0135e5cf51c1eb2f11961cfd243b23cf0",
    CANARY_WORKFLOW: "9c59cd9822eecec913f82d24c7880a443ba9416795b8996c6201f33c4df5805d",
    EVIDENCE: "1ee162ea47cf86b7faec68bfba37b7a9b2af3b25472066312b43c4a5e4414cdd",
    APPROVAL: "e1c6687d4c85c4881a433d03da8d66168915c8e316e4817e1415835b52e3ba72",
}
APP_TOKEN_PIN = "bcd2ba49218906704ab6c1aa796996da409d3eb1"
CHECKOUT_PIN = "11bd71901bbe5b1630ceea73d27597364c9af683"
DATABASE_LOCATORS = (
    "state/databases/pipeline.sqlite3",
    "state/databases/operations.sqlite3",
    "state/databases/publication.sqlite3",
)


class AcceptanceError(Exception):
    """Closed failure for missing or weakened Phase 5 acceptance evidence."""


class CheckSpec(NamedTuple):
    identifier: str
    check: Callable[[Path], tuple[str, ...]]


def _require(condition: bool) -> None:
    if not condition:
        raise AcceptanceError


def _bytes(root: Path, relative: Path) -> bytes:
    path = root / relative
    payload = path.read_bytes()
    _require(len(payload) <= MAX_SOURCE_BYTES)
    return payload


def _read(root: Path, relative: Path) -> str:
    return _bytes(root, relative).decode("utf-8", errors="strict")


def _json(root: Path, relative: Path) -> object:
    return json.loads(_read(root, relative))


def _tokens(source: str, values: tuple[str, ...]) -> None:
    _require(all(source.count(value) >= 1 for value in values))


def _ordered(source: str, values: tuple[str, ...]) -> None:
    positions = tuple(source.index(value) for value in values)
    _require(positions == tuple(sorted(positions)))


def imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_bytes(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".", 1)[0])
    return modules


def inspect_query_and_budgets(root: Path) -> tuple[str, ...]:
    domain = _read(root, DOMAIN)
    config = _json(root, QUERY_CONFIG)
    _require(isinstance(config, dict))
    _require(
        config
        == {
            "schema_version": "discovery-query-set-v1",
            "query_set_version": "github-repository-search-v1",
            "queries": [
                {
                    "query_id": "agent-workflow-readme",
                    "query_text": '"agent workflow" in:name,description,readme is:public archived:false',
                },
                {
                    "query_id": "ai-workflow-readme",
                    "query_text": '"AI workflow" in:name,description,readme is:public archived:false',
                },
                {
                    "query_id": "llm-automation-readme",
                    "query_text": '"LLM automation" in:name,description,readme is:public archived:false',
                },
                {
                    "query_id": "agent-skills-topic",
                    "query_text": "topic:agent-skills is:public archived:false",
                },
            ],
            "per_page": 25,
            "max_pages_per_query": 4,
            "acquisition_order": "round_robin",
            "sort": "updated",
            "order": "desc",
        }
    )
    _tokens(
        domain,
        (
            'DISCOVERY_QUERY_SET_VERSION: Final = "github-repository-search-v1"',
            "DISCOVERY_MAX_CANDIDATES: Final = 100",
            "DISCOVERY_MAX_SEMANTIC_CANDIDATES: Final = 20",
            "max_candidates: Literal[100]",
            "max_semantic_candidates: Literal[20]",
            "admit_discovery_ordinal",
            "admit_semantic_ordinal",
            "SearchPageObservationV1",
            "DiscoveredCandidateV1",
            "SearchRateLimitFactsV1",
        ),
    )
    return ("DISC-01 exact queries", "DISC-02 literal 100/20", "DISC-03 complete facts")


def inspect_discovery_boundary(root: Path) -> tuple[str, ...]:
    source = _read(root, DISCOVERY)
    _tokens(
        source,
        (
            "reserve_discovery_candidate",
            "terminal.semantic_reservation_digest",
            "summary.semantic_reservation_count * 3",
            '"semantic_outcome_unknown"',
            "eligible_candidate_locator",
            "state_root_digest",
            "state_commit_sha",
            "class DiscoveryDependencies:",
        ),
    )
    _require(source.count("reserve_discovery_candidate") >= 2)
    _require("build_publication_application" not in source)
    _require("PublicationApplication" not in source)
    return ("non-refundable ledgers", "0-3 workflow fan-out", "closed unprotected handoff")


def inspect_semantic_barriers(root: Path) -> tuple[str, ...]:
    ports = _read(root, PORTS)
    pipeline = _read(root, PIPELINE)
    phase3 = _read(root, PHASE3)
    provider = _read(root, SEMANTIC_PROVIDER)
    _tokens(
        ports,
        (
            '"attempt_started"',
            '"result_decided"',
            '"result_confirmed_retryable"',
            '"result_outcome_unknown"',
            "class DurabilityReceipt",
            "def require_durability_receipt(",
        ),
    )
    _tokens(
        pipeline,
        (
            "reserve_before_extractor(",
            "require_durability_receipt(",
            "SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN",
            '"confirmed_retryable"',
        ),
    )
    _tokens(
        phase3,
        (
            "def _confirm_semantic(",
            'stage=PhaseThreeStageV1.GENERATOR',
            'stage=PhaseThreeStageV1.REVIEWER',
            'status="started"',
            'status="decided"',
            "SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN",
        ),
    )
    _tokens(
        provider,
        (
            "CONFIRMED_RETRYABLE",
            "SEMANTIC_OUTCOME_UNKNOWN",
            '"max_retries": 0',
            'OPENAI = "openai"',
            'DEEPSEEK = "deepseek"',
        ),
    )
    return ("extractor barriers", "generator/reviewer barriers", "provider-wide quarantine")


def inspect_three_store_state(root: Path) -> tuple[str, ...]:
    operations = _read(root, OPERATIONS_STATE)
    state_branch = _read(root, STATE_BRANCH)
    pipeline = _read(root, PIPELINE_STATE)
    publication = _read(root, PUBLICATION_STATE)
    for locator in DATABASE_LOCATORS:
        _require(locator in operations and locator in state_branch)
    _tokens(
        operations,
        (
            "def export_owned_state(",
            "def restore_three_store_bundle(",
            "SQLiteStateStore.rebuild_owned_state",
            "OperationsStateStore.rebuild_owned_state",
            "PublicationStateStore.rebuild_owned_state",
        ),
    )
    _tokens(pipeline, ("def rebuild_owned_state(", "pipeline-rebuild-row-v1"))
    _tokens(publication, ("def rebuild_owned_state(", "publication-rebuild-attempt-v1"))
    _tokens(
        state_branch,
        (
            '{"sha": expected, "force": False}',
            "update_state_ref(commit_sha, force=False)",
            "reread_ref = self._remote.get_state_ref()",
            "if reread_ref.sha != commit_sha:",
            "not self._bundles_equal(reread.bundle, bundle)",
        ),
    )
    _require("force=True" not in state_branch)
    return ("three owned stores", "JSON rebuild authority", "parent-bound CAS and reread")


def inspect_protected_publication(root: Path) -> tuple[str, ...]:
    bootstrap = _read(root, BOOTSTRAP)
    cli = _read(root, CLI)
    _tokens(
        bootstrap,
        (
            "def read_exact_discovery_state(",
            "def derive_discovery_publication_admissions(",
            "def run_protected_discovery_publication(",
            "catalog_token_factory",
            "publication_factory",
        ),
    )
    _ordered(
        bootstrap,
        (
            "state = state_reader(normalized.state_commit_sha)",
            "admissions = admission_deriver(state, normalized)",
            "token = catalog_token_factory()",
            "application = publication_factory(admission=admission, token=token)",
        ),
    )
    _tokens(
        cli,
        (
            "read_exact_discovery_state(",
            "derive_discovery_publication_admissions(",
            "catalog_token_factory=lambda: os.environ",
            "return build_publication_application(",
            "SKILLSCOUT_GITHUB_TOKEN",
            '_DISCOVERY_PIPELINE_STATE = Path("state/databases/pipeline.sqlite3")',
            '_DISCOVERY_OPERATIONS_STATE = Path("state/databases/operations.sqlite3")',
            '_DISCOVERY_PUBLICATION_STATE = Path("state/databases/publication.sqlite3")',
        ),
    )
    return ("exact-state reread", "canonical admission", "late catalog credential")


def inspect_workflows(root: Path) -> tuple[str, ...]:
    for relative, expected in EXPECTED_DIGESTS.items():
        _require(hashlib.sha256(_bytes(root, relative)).hexdigest() == expected)
    discover = _read(root, DISCOVER_WORKFLOW)
    _tokens(
        discover,
        (
            "schedule:",
            'cron: "17 3 * * *"',
            "workflow_dispatch:",
            "group: skillscout-production",
            "cancel-in-progress: false",
            "environment: skillscout-catalog-publish",
            f"actions/checkout@{CHECKOUT_PIN}",
            f"actions/create-github-app-token@{APP_TOKEN_PIN}",
            "Re-read exact state commit and re-derive every admission",
            "Mint catalog-scoped installation token after exact re-admission",
        ),
    )
    discovery_job, protected_job = discover.split("\n  protected_publication:", 1)
    _require("SKILLSCOUT_CATALOG_" not in discovery_job)
    _require("SKILLSCOUT_GITHUB_APP_PRIVATE_KEY" not in discovery_job)
    _require("secrets.SKILLSCOUT_GITHUB_APP_PRIVATE_KEY" in protected_job)
    return ("daily/manual trigger", "serialized production", "separate credential zones")


def inspect_hosted_evidence(root: Path) -> tuple[str, ...]:
    evidence = _json(root, EVIDENCE)
    approval = _json(root, APPROVAL)
    _require(isinstance(evidence, dict) and isinstance(approval, dict))
    _require(approval.get("decision") == "approved-gate-b4")
    _require(approval.get("evidence", {}).get("sha256") == EXPECTED_DIGESTS[EVIDENCE])
    _require(approval.get("scope", {}).get("concurrency_evidence_is_not_gate_b4") is True)
    _require(approval.get("scope", {}).get("automatic_merge_or_approval") is False)
    _require(evidence.get("gate_b4_approval", {}).get("approved") is False)
    expected_workflows = {
        "discover_sha256": EXPECTED_DIGESTS[DISCOVER_WORKFLOW],
        "publish_candidate_sha256": EXPECTED_DIGESTS[PUBLISH_WORKFLOW],
        "gate_b4_canary_sha256": EXPECTED_DIGESTS[CANARY_WORKFLOW],
    }
    _require(evidence.get("workflow_digests") == expected_workflows)
    _require(approval.get("approved_workflow_digests") == expected_workflows)
    _require(
        approval.get("approved_hosted_runs")
        == {
            "concurrency": ["30324567231", "30324568742"],
            "gate_b4_canary": "30327184915",
        }
    )
    _require(evidence.get("cleanup", {}).get("remaining_branches") == ["main"])
    return ("immutable Gate B4 bytes", "separate concurrency evidence", "human cleanup")


CHECK_REGISTRY = (
    CheckSpec("query_and_budgets", inspect_query_and_budgets),
    CheckSpec("discovery_boundary", inspect_discovery_boundary),
    CheckSpec("semantic_barriers", inspect_semantic_barriers),
    CheckSpec("three_store_state", inspect_three_store_state),
    CheckSpec("protected_publication", inspect_protected_publication),
    CheckSpec("workflows", inspect_workflows),
    CheckSpec("hosted_evidence", inspect_hosted_evidence),
)


def verify_phase5_acceptance(repository_root: Path) -> None:
    root = Path(os.path.abspath(os.fspath(repository_root)))
    _require(root.is_dir())
    expected = (
        "query_and_budgets",
        "discovery_boundary",
        "semantic_barriers",
        "three_store_state",
        "protected_publication",
        "workflows",
        "hosted_evidence",
    )
    _require(tuple(spec.identifier for spec in CHECK_REGISTRY) == expected)
    results = tuple((spec.identifier, spec.check(root)) for spec in CHECK_REGISTRY)
    _require(tuple(identifier for identifier, _ in results) == expected)
    _require(all(evidence for _, evidence in results))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repository-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        root = Path(__file__).resolve().parents[1]
        if arguments:
            namespace = _parser().parse_args(arguments)
            _require(namespace.repository_root is not None)
            root = namespace.repository_root
        verify_phase5_acceptance(root)
    except (
        AcceptanceError,
        OSError,
        UnicodeError,
        SyntaxError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        SystemExit,
    ):
        print(FAILURE_DIAGNOSTIC, file=sys.stderr)
        return 1
    print(SUCCESS_DIAGNOSTIC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
