#!/usr/bin/env python3
"""Independent standard-library-only, read-only Phase 4 acceptance inspector."""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple

MAX_SOURCE_BYTES = 2_000_000
SUCCESS_DIAGNOSTIC = "phase4 acceptance valid"
FAILURE_DIAGNOSTIC = "phase4 acceptance invalid"
PHASE = Path(".planning/phases/04-controlled-draft-pr")
DOMAIN = Path("src/skillscout/domain/publication.py")
ADAPTER = Path("src/skillscout/adapters/github_publish.py")
RECOVERY = Path("src/skillscout/application/publication.py")
STATE = Path("src/skillscout/adapters/publication_state.py")
CLI = Path("src/skillscout/cli.py")
BOOTSTRAP = Path("src/skillscout/bootstrap.py")
WORKFLOW = Path(".github/workflows/publish-candidate.yml")
ACTION_AUDIT_DIGEST = "d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622"
WORKFLOW_SHA256 = "99fded78508bd4f20303cb201942f7b22b2be10c6b65042909835789853c2a09"
RULESET_DIGEST = "sha256:e58e74403d890296e44105cb60b42abffe522f11d169884d6d51f285b63948b5"
ACTION_PINS = (
    "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
    "actions/create-github-app-token@67018539274d69449ef7c8cde82c3ff073ffe3b5",
)
CANDIDATE_OUTPUTS = (
    "candidate_descriptor_locator",
    "phase2_state_locator",
    "phase3_state_locator",
    "candidate_descriptor_digest",
    "phase2_chain_digest",
    "terminal_summary_digest",
    "package_digest",
    "manifest_digest",
    "validation_report_digest",
    "review_attestation_digest",
)


class AcceptanceError(Exception):
    """Closed failure for missing or weakened Phase 4 acceptance evidence."""


class CheckSpec(NamedTuple):
    identifier: str
    check: Callable[[Path], tuple[str, ...]]


def _require(condition: bool) -> None:
    if not condition:
        raise AcceptanceError


def _read(root: Path, relative: Path) -> str:
    path = root / relative
    payload = path.read_bytes()
    _require(len(payload) <= MAX_SOURCE_BYTES)
    return payload.decode("utf-8", errors="strict")


def _tokens(source: str, values: tuple[str, ...]) -> None:
    _require(all(source.count(value) >= 1 for value in values))


def imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_bytes(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".", 1)[0])
    return modules


def _class_fields(tree: ast.Module, name: str) -> tuple[str, ...]:
    classes = [
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name
    ]
    _require(len(classes) == 1)
    return tuple(
        target.id
        for node in classes[0].body
        if isinstance(node, ast.AnnAssign) and isinstance((target := node.target), ast.Name)
    )


def inspect_domain(root: Path) -> tuple[str, ...]:
    source = _read(root, DOMAIN)
    tree = ast.parse(source)
    candidate = _class_fields(tree, "CandidatePublicationEvidenceV1")
    intent = _class_fields(tree, "PublicationIntentV1")
    admission = _class_fields(tree, "PublicationAdmissionV1")
    reviewers = _class_fields(tree, "ReviewerTargetsV1")
    lineage = _class_fields(tree, "MachineLineageV1")
    _require(
        not set(candidate)
        & {
            "catalog_repository_id",
            "catalog_full_name",
            "reviewers",
            "intent_digest",
            "admission_digest",
        }
    )
    _require(
        {"catalog_repository_id", "catalog_full_name", "reviewers", "intent_digest"}
        <= set(intent)
        and {"evidence", "intent", "admission_digest"} <= set(admission)
        and reviewers == ("schema_version", "reviewers")
        and "teams" not in candidate + intent + admission + reviewers
    )
    _require(
        lineage
        == (
            "schema_version",
            "publication_key",
            "machine_commit_sha",
            "parent_commit_sha",
            "tree_sha",
            "previous_marker_digest",
            "previous_desired_revision",
            "lineage_digest",
        )
    )
    _tokens(
        source,
        (
            "reviewers must be sorted and unique individual logins",
            "intent requires candidate evidence and protected authority",
            "admission requires strict candidate evidence, intent, and catalog authority",
            '"publication_key": publication_key, "package_digest": evidence.package_digest',
            "if head_branch == catalog_authority.base_branch:",
        ),
    )
    return ("authority-free candidate", "protected intent/admission", "stable revision lineage")


def inspect_adapter(root: Path) -> tuple[str, ...]:
    source = _read(root, ADAPTER)
    tree = ast.parse(source)
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "GitHubPublishClient"
    ]
    _require(len(classes) == 1)
    methods = {
        node.name for node in classes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    _require(
        {
            "get_catalog",
            "get_ref",
            "get_base_ref",
            "get_commit",
            "get_tree",
            "list_open_pulls",
            "get_requested_reviewers",
            "list_reviews",
            "create_blob",
            "create_tree",
            "create_commit",
            "create_ref",
            "update_ref",
            "create_pull",
            "update_pull",
            "request_reviewers",
        }
        <= methods
    )
    _require(
        not methods
        & {
            "request",
            "graphql",
            "merge",
            "approve",
            "submit_review",
            "ready_for_review",
            "timeline",
            "delete",
        }
    )
    _tokens(
        source,
        (
            'raw.get("truncated") is not False',
            "_MAX_TREE_ENTRIES = 2_000",
            "_MAX_PAGES = 20",
            'users, teams = raw.get("users"), raw.get("teams")',
            "or teams:",
            '{"sha": _sha(sha), "force": False}',
            '{"reviewers": list(value)}',
            "if ref != f\"heads/{self._branch}\" or force is not False:",
            "draft is not True or maintainer_can_modify is not False",
        ),
    )
    return ("bounded owned tree", "individual-review recovery reads", "closed mutations")


def inspect_recovery(root: Path) -> tuple[str, ...]:
    application = _read(root, RECOVERY)
    state = _read(root, STATE)
    _tokens(
        application,
        (
            "def validate_reviewer_targets(",
            "if teams or not reviewers",
            '"sha": None',
            '"removed_after_request"',
            '"malformed_review_evidence"',
            "remote.get_requested_reviewers(number).users",
            "remote.list_reviews(number)",
            "store.append_checkpoint(",
            "store.complete(admission.intent, record)",
        ),
    )
    _tokens(
        state,
        (
            "class PublicationCheckpointV1",
            "prior_checkpoint_hash: Digest",
            "checkpoint_hash: Digest",
            "def find_completed(",
            "def find_pending(",
            "def append_checkpoint(",
            "def complete(",
            'sqlite3.connect(":memory:")',
        ),
    )
    return ("checkpoint continuity", "pending/completed recovery", "reviewer ambiguity")


def inspect_cli(root: Path) -> tuple[str, ...]:
    cli = _read(root, CLI)
    bootstrap = _read(root, BOOTSTRAP)
    _tokens(
        cli,
        (
            "verify_publication_admission_handoff(",
            "compare_env=True",
            "load_publication_authority_config()",
            "derive_publication_intent(",
            "bind_publication_admission(",
            "build_publication_application(",
            "SKILLSCOUT_GITHUB_TOKEN",
            "verify-publication-admission",
            "publish-candidate",
            "--compare-env",
            "--publication-state",
        ),
    )
    _require(cli.count("verify_publication_admission_handoff(") == 2)
    _tokens(
        bootstrap,
        (
            "class PublicationEvidenceLocatorV1:",
            "def verify_publication_admission_handoff(",
            "candidate_descriptor_locator",
            "phase2_state_locator",
            "phase3_state_locator",
            "candidate_descriptor_digest",
            "phase2_chain_digest",
            "terminal_summary_digest",
            "package_digest",
            "manifest_digest",
            "validation_report_digest",
            "review_attestation_digest",
        ),
    )
    return ("late token", "exact locator grammar", "protected-local derivation")


def _workflow_outputs(source: str) -> tuple[str, ...]:
    match = re.search(r"(?ms)^  admit:\n.*?^    outputs:\n(.*?)^    env:", source)
    _require(match is not None)
    return tuple(
        found.group(1)
        for line in match.group(1).splitlines()
        if (found := re.match(r"^      ([a-z0-9_]+):", line)) is not None
    )


def inspect_workflow(root: Path) -> tuple[str, ...]:
    source = _read(root, WORKFLOW)
    _require(hashlib.sha256(source.encode("utf-8")).hexdigest() == WORKFLOW_SHA256)
    _require(_workflow_outputs(source) == CANDIDATE_OUTPUTS)
    _require(
        source.count(ACTION_PINS[0]) == 2
        and source.count(ACTION_PINS[1]) == 1
    )
    _tokens(
        source,
        (
            "permissions:\n  contents: read",
            "environment: skillscout-catalog-publish",
            "Revalidate candidate and derive protected-local admission",
            "verify-publication-admission --candidate \"$CANDIDATE_LOCATOR\" --phase2-state \"$PHASE2_STATE_LOCATOR\" --phase3-state \"$PHASE3_STATE_LOCATOR\" --compare-env",
            "value = protected.get(field)",
            "Mint catalog-scoped installation token after protected admission",
            "permission-contents: write",
            "permission-pull-requests: write",
            "fields = (",
            '"candidate_descriptor_locator", "phase2_state_locator", "phase3_state_locator",',
        ),
    )
    admit = source.split("\n  publish:", 1)[0]
    _require(
        "SKILLSCOUT_CATALOG_" not in admit
        and "publication_intent_digest" not in admit
        and "admission_digest" not in admit
        and "secrets." not in admit
    )
    return ("candidate-only ten fields", "protected environment", "token after admission")


def inspect_human_gates(root: Path) -> tuple[str, ...]:
    gate_a = _read(root, PHASE / "04-08-SUMMARY.md")
    gate_b = _read(root, PHASE / "04-10-SUMMARY.md")
    _require(
        gate_a.count(ACTION_AUDIT_DIGEST) == 4
        and all(pin in gate_a for pin in ACTION_PINS)
    )
    _tokens(
        gate_b,
        (
            f"Workflow content SHA-256: `{WORKFLOW_SHA256}`",
            f"Ruleset digest: `{RULESET_DIGEST}`",
            "Default-ref update | 422 | validation",
            "Merge otherwise-mergeable PR | 405 | denied",
            "Ruleset mutation | 403 | denied",
            "Unauthorized private repository | 404 | not_found",
            "Repository secret access | 403 | denied",
            "Default SHA before and after all probes: `bd96c4fcfed5e7b2c94c79be7ec1aa6e333b71bb`",
            "PRs `#1` and `#2` are closed, not merged.",
            "Post-cleanup branches: only `main`.",
            "coarse `pull_requests: write` token may support ready-for-review outside SkillScout",
        ),
    )
    return ("Gate A4 immutable pins", "Gate B4 scoped denial", "separate cleanup")


def inspect_forbidden_surfaces(root: Path) -> tuple[str, ...]:
    checked = (DOMAIN, ADAPTER, RECOVERY, STATE, CLI, BOOTSTRAP)
    forbidden_imports = {"requests", "subprocess", "socket", "urllib"}
    for relative in checked:
        _require(not imported_top_level_modules(root / relative) & forbidden_imports)
    adapter = _read(root, ADAPTER)
    workflow = _read(root, WORKFLOW)
    cli = _read(root, CLI)
    for value in ("--merge", "--approve", "--mark-ready", "--ready-for-review"):
        _require(value not in cli)
    for value in ("/graphql", "/merge", "/reviews", "/ready-for-review", "/rulesets"):
        _require(value not in adapter and value not in workflow)
    return ("no forbidden imports", "no approve/ready/merge CLI", "no generic remote routes")


CHECK_REGISTRY = (
    CheckSpec("domain", inspect_domain),
    CheckSpec("adapter", inspect_adapter),
    CheckSpec("recovery", inspect_recovery),
    CheckSpec("cli", inspect_cli),
    CheckSpec("workflow", inspect_workflow),
    CheckSpec("human_gates", inspect_human_gates),
    CheckSpec("forbidden_surfaces", inspect_forbidden_surfaces),
)


def verify_phase4_acceptance(repository_root: Path) -> None:
    root = Path(os.path.abspath(os.fspath(repository_root)))
    _require(root.is_dir())
    expected = (
        "domain",
        "adapter",
        "recovery",
        "cli",
        "workflow",
        "human_gates",
        "forbidden_surfaces",
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
        verify_phase4_acceptance(root)
    except (
        AcceptanceError,
        OSError,
        UnicodeError,
        SyntaxError,
        ValueError,
        TypeError,
        SystemExit,
    ):
        print(FAILURE_DIAGNOSTIC, file=sys.stderr)
        return 1
    print(SUCCESS_DIAGNOSTIC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
