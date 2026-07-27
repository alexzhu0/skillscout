"""Wave-0 RED audit for daily/manual two-zone production workflow."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-candidate.yml"
DISCOVER_WORKFLOW = ROOT / ".github" / "workflows" / "discover.yml"
PUBLISH_WORKFLOW_SHA256 = (
    "224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c"
)
CHECKOUT_SHA = "11bd71901bbe5b1630ceea73d27597364c9af683"
APP_TOKEN_SHA = "67018539274d69449ef7c8cde82c3ff073ffe3b5"


def _workflow() -> str:
    return DISCOVER_WORKFLOW.read_text()


def _job(text: str, name: str) -> str:
    match = re.search(
        rf"^  {name}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9_-]*:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match
    return match.group("body")


def test_phase4_gate_b4_baseline_workflow_bytes_remain_exact() -> None:
    assert hashlib.sha256(PUBLISH_WORKFLOW.read_bytes()).hexdigest() == (
        PUBLISH_WORKFLOW_SHA256
    )


def test_discovery_workflow_has_exact_triggers_and_shared_non_cancel_group() -> None:
    text = _workflow()
    assert re.search(r'^on:\n(?:.*\n)*?  schedule:\n    - cron: "17 3 \* \* \*"', text)
    assert re.search(r"^  workflow_dispatch:\s*$", text, re.MULTILINE)
    assert re.search(
        r"^concurrency:\n  group: skillscout-production\n  cancel-in-progress: false",
        text,
        re.MULTILINE,
    )
    assert "@v" not in text
    refs = re.findall(r"^\s*uses:\s*[^@\s]+@([^\s#]+)", text, re.MULTILINE)
    assert refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs)
    assert CHECKOUT_SHA in refs
    assert APP_TOKEN_SHA in refs
    assert re.search(r"^permissions:\n  contents: read$", text, re.MULTILINE)
    discovery = _job(text, "discovery")
    publication = _job(text, "protected_publication")
    assert re.search(r"^    permissions:\n      contents: write$", discovery, re.MULTILINE)
    assert re.search(r"^    permissions:\n      contents: read$", publication, re.MULTILINE)


def test_discovery_and_protected_jobs_are_separate_authority_zones() -> None:
    text = _workflow()
    discovery = _job(text, "discovery")
    publication = _job(text, "protected_publication")
    assert "environment:" not in discovery
    assert "SKILLSCOUT_GITHUB_APP_PRIVATE_KEY" not in discovery
    assert "SKILLSCOUT_CATALOG_" not in discovery
    assert "publish-candidate" not in discovery
    assert "skillscout.cli discover" in discovery
    assert "skillscout.cli publish-discovered" not in discovery
    assert "skillscout.cli publish-discovered" in publication
    assert "skillscout.cli discover" not in publication
    assert "environment: skillscout-catalog-publish" in publication
    admission_index = publication.index("read_exact_discovery_state")
    derivation_index = publication.index("derive_discovery_publication_admissions")
    token_index = publication.index("actions/create-github-app-token")
    invocation_index = publication.index("skillscout.cli publish-discovered")
    assert admission_index < derivation_index < token_index < invocation_index
    for forbidden in (
        "build_publication_application",
        "PublicationApplication",
        "GitHubPublishClient",
    ):
        assert forbidden not in discovery
        assert forbidden not in publication[:token_index]
    assert publication.count(
        "actions/create-github-app-token"
    ) == 1
    assert publication.count(
        "skillscout.cli publish-discovered"
    ) == 1
    assert re.search(
        r"needs:\s*discovery",
        publication,
    )
    assert "persist-credentials: false" in discovery
    assert "persist-credentials: false" in publication


def test_workflow_handoff_is_bounded_and_shell_never_interpolates_candidates() -> None:
    text = _workflow()
    discovery = _job(text, "discovery")
    expected = {
        "discovery_run_id",
        "state_root_digest",
        "state_commit_sha",
        "eligible_candidates_json",
        "eligible_candidates_digest",
    }
    output_block = re.search(
        r"^    outputs:\n(?P<body>.*?)(?=^    [a-z]|\Z)",
        discovery,
        re.MULTILINE | re.DOTALL,
    )
    assert output_block
    actual = set(
        re.findall(r"^      ([a-z][a-z0-9_]+):", output_block.group("body"), re.MULTILINE)
    )
    assert actual == expected
    assert 'set(payload) != {"run_id", "state_root_digest", "state_commit_sha", "eligible_count", "eligible_candidates"}' in discovery
    assert "len(candidates) > 60" in discovery
    assert "len(canonical) > 65_536" in discovery
    assert 'set(candidate) != {"locator", "authority_digest", "workflow_identity_digest"}' in discovery
    publication = _job(text, "protected_publication")
    for output in expected:
        assert f"${{{{ needs.discovery.outputs.{output} }}}}" in publication
    for block in re.findall(r"run:\s*\|\n((?:\s{8,}.*\n?)*)", text):
        assert "${{" not in block
    assert "actions/cache" not in text
    assert "upload-artifact" not in text
    assert "download-artifact" not in text


def test_queue_grammar_requires_recorded_hosted_validation_or_fixed_fallback() -> None:
    text = _workflow()
    evidence = ROOT / ".planning" / "phases" / "05-automated-discovery-operations" / "05-HOSTED-CONCURRENCY.json"
    if re.search(r"^  queue: max$", text, re.MULTILINE):
        assert evidence.is_file()
        assert '"queue_max_accepted": true' in evidence.read_text()
    else:
        assert "cancel-in-progress: false" in text
        assert "pending run replacement" in text
