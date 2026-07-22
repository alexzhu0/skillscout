"""Scout pinning/snapshot and filter rule-matrix evidence over recorded fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pytest

from recorded_transport import (
    RecordedResponse,
    RecordedTransport,
    make_blob_fixture,
    recorded_fixture,
)

from skillscout.adapters.github import GitHubReadClient
from skillscout.adapters.state import SQLiteStateStore
from skillscout.adapters.subjects import load_subject
from skillscout.application.pipeline import PipelineRunner
from skillscout.application.ports import (
    ErrorCode,
    SafeFailure,
    StageContext,
    StageOutcome,
)
from skillscout.application.processors import (
    SCOUT_MAX_CANDIDATE_ENTRIES,
    PhaseTwoProcessor,
)
from skillscout.domain.enums import (
    AttemptStatus,
    ExecutionMode,
    PipelineStage,
    RunStatus,
)
from skillscout.domain.filtering import FILTER_POLICY_VERSION, FilterRuleId
from skillscout.domain.models import ExtractionSummary, StageInput
from skillscout.domain.subjects import RepositorySubject

APPROVED_SUBJECT = Path(__file__).parent / "fixtures" / "subject" / "approved.json"
PINNED = "0123456789abcdef0123456789abcdef01234567"
SUBJECT = RepositorySubject(
    schema_version="1",
    subject_id="repo:example/approved-repo",
    repository="https://github.com/example/approved-repo",
)

META = ("GET", "/repos/example/approved-repo")
PIN = ("GET", "/repos/example/approved-repo/commits/main")
TREE = ("GET", f"/repos/example/approved-repo/git/trees/{PINNED}?recursive=1")
LICENSE = ("GET", f"/repos/example/approved-repo/license?ref={PINNED}")


def _routes(
    *,
    repo: str = "repo_mit",
    pin: str = "commits_pin",
    tree: str = "tree_full",
    license: str = "license_mit",
) -> dict[tuple[str, str], RecordedResponse]:
    return {
        META: recorded_fixture(repo),
        PIN: recorded_fixture(pin),
        TREE: recorded_fixture(tree),
        LICENSE: recorded_fixture(license),
    }


def _metadata_variant(**changes: object) -> RecordedResponse:
    base = recorded_fixture("repo_mit")
    body = json.loads(base.body)
    body.update(changes)
    return RecordedResponse(
        status=base.status, headers=base.headers, body=json.dumps(body).encode()
    )


def _processor(
    routes: dict[tuple[str, str], RecordedResponse],
) -> tuple[PhaseTwoProcessor, RecordedTransport]:
    recorded = RecordedTransport(routes)
    client = GitHubReadClient(
        transport=recorded.transport(), sleeper=lambda _seconds: None
    )
    return PhaseTwoProcessor(client), recorded


def _stage_input(stage: PipelineStage) -> StageInput:
    return StageInput(
        schema_version="2",
        execution_mode=ExecutionMode.DRY_RUN,
        subject_id=SUBJECT.subject_id,
        stage=stage,
        previous_output_hash=None,
        fixture_hash="sha256:" + "0" * 64,
    )


def _context(
    subject: RepositorySubject = SUBJECT,
    prior: dict[str, Mapping[str, object]] | None = None,
) -> StageContext:
    return StageContext(subject=subject, prior_payloads=prior or {}, scratch={})


def _scout(
    processor: PhaseTwoProcessor,
    subject: RepositorySubject = SUBJECT,
) -> StageOutcome:
    return processor.process(_stage_input(PipelineStage.SCOUT), _context(subject))


def _filter(
    processor: PhaseTwoProcessor,
    scout_payload: Mapping[str, object],
    subject: RepositorySubject = SUBJECT,
) -> StageOutcome:
    return processor.process(
        _stage_input(PipelineStage.FILTER),
        _context(subject, {"scout": scout_payload}),
    )


def _decision(payload: Mapping[str, object], rule_id: FilterRuleId) -> Mapping[str, object]:
    decisions = payload["decisions"]
    assert isinstance(decisions, list)
    for decision in decisions:
        assert isinstance(decision, Mapping)
        if decision["rule_id"] == rule_id.value:
            return decision
    raise AssertionError(f"missing decision {rule_id.value}")


def test_scout_happy_path_pins_and_projects_the_bounded_snapshot() -> None:
    processor, recorded = _processor(_routes())
    outcome = _scout(processor)

    payload = outcome.payload
    assert payload["outcome"] == "accepted"
    assert payload["rejection_reason"] is None
    assert payload["schema_version"] == "2"
    assert payload["stage"] == "scout"
    assert payload["subject_id"] == SUBJECT.subject_id
    assert payload["ref_requested"] is None
    assert payload["pinned_commit_sha"] == PINNED
    assert payload["redirect"] == []
    assert payload["rate_limit"] == {"limit": 5000, "remaining": 4999, "reset": 1800000000}
    repository = payload["repository"]
    assert repository["id"] == 840001
    assert repository["owner"] == "example"
    assert repository["name"] == "approved-repo"
    assert repository["default_branch"] == "main"
    assert repository["private"] is False
    assert repository["fork"] is False
    assert repository["archived"] is False
    assert repository["disabled"] is False
    assert repository["visibility"] == "public"
    assert repository["license_spdx"] == "MIT"

    tree = payload["tree"]
    assert tree["entry_count"] == 12
    assert tree["truncated"] is False
    assert tree["candidate_count"] == 12
    candidates = tree["candidates"]
    paths = [entry["path"] for entry in candidates]
    assert paths == sorted(paths)
    assert paths == [
        "LICENSE",
        "README.md",
        "docs/big.md",
        "docs/external",
        "docs/guide.md",
        "docs/link.md",
        "examples/basic.md",
        "examples/data.bin",
        "lib/helper.py",
        "pyproject.toml",
        "script.py",
        "src/core.py",
    ]
    submodule = candidates[paths.index("docs/external")]
    assert submodule["mode"] == "160000"
    assert submodule["size"] is None
    symlink = candidates[paths.index("docs/link.md")]
    assert symlink["mode"] == "120000"

    assert outcome.telemetry is not None
    assert outcome.telemetry.request_id == "REQ-TREE-0001"
    assert isinstance(outcome.telemetry.latency_ms, int)
    assert outcome.telemetry.latency_ms >= 0

    urls = [str(request.url) for request in recorded.requests]
    assert urls[0].endswith("/repos/example/approved-repo")
    assert urls[1].endswith("/commits/main")
    assert PINNED in urls[2]
    assert "main" not in urls[2]


def test_scout_records_the_followed_same_host_redirect() -> None:
    routes = _routes()
    routes[META] = recorded_fixture("redirect_301")
    routes[("GET", "/repos/example/renamed-repo")] = recorded_fixture("repo_mit")
    routes[("GET", "/repos/example/renamed-repo/commits/main")] = recorded_fixture(
        "commits_pin"
    )
    routes[("GET", f"/repos/example/renamed-repo/git/trees/{PINNED}?recursive=1")] = (
        recorded_fixture("tree_full")
    )
    processor, _recorded = _processor(routes)
    outcome = _scout(processor)

    assert outcome.payload["redirect"] == [
        {
            "from_url": "https://api.github.com/repos/example/approved-repo",
            "to_url": "https://api.github.com/repos/example/renamed-repo",
        }
    ]
    assert outcome.payload["outcome"] == "accepted"


def test_scout_rejects_when_no_ref_is_resolvable() -> None:
    routes = _routes()
    routes[META] = _metadata_variant(default_branch=None)
    processor, recorded = _processor(routes)
    outcome = _scout(processor)

    payload = outcome.payload
    assert payload["outcome"] == "rejected"
    assert payload["rejection_reason"] == "no_ref_resolvable"
    assert payload["repository"]["default_branch"] is None
    assert payload["pinned_commit_sha"] is None
    assert payload["tree"] is None
    assert recorded.call_count(*PIN) == 0
    assert recorded.call_count(*TREE) == 0


def test_scout_rejects_a_sha256_repository_without_fetching_content() -> None:
    routes = _routes(pin="commits_pin_sha256")
    processor, recorded = _processor(routes)
    outcome = _scout(processor)

    payload = outcome.payload
    assert payload["outcome"] == "rejected"
    assert payload["rejection_reason"] == "sha256_repository_unsupported"
    assert payload["pinned_commit_sha"] is None
    assert payload["tree"] is None
    assert recorded.call_count(*PIN) == 1
    assert recorded.call_count(*TREE) == 0
    assert recorded.call_count(*LICENSE) == 0


def test_scout_rejects_a_truncated_tree() -> None:
    processor, _recorded = _processor(_routes(tree="tree_truncated"))
    outcome = _scout(processor)

    payload = outcome.payload
    assert payload["outcome"] == "rejected"
    assert payload["rejection_reason"] == "repository_too_large"
    assert payload["tree"]["truncated"] is True
    assert payload["tree"]["candidates"] == []


def test_scout_rejects_an_over_cap_candidate_projection() -> None:
    base = recorded_fixture("tree_full")
    body = json.loads(base.body)
    body["tree"] = [
        {
            "path": f"src/module_{index:04d}.py",
            "mode": "100644",
            "type": "blob",
            "size": 10,
            "sha": "dd09dd09dd09dd09dd09dd09dd09dd09dd09dd09",
        }
        for index in range(SCOUT_MAX_CANDIDATE_ENTRIES + 1)
    ]
    routes = _routes()
    routes[TREE] = RecordedResponse(
        status=base.status, headers=base.headers, body=json.dumps(body).encode()
    )
    processor, _recorded = _processor(routes)
    outcome = _scout(processor)

    payload = outcome.payload
    assert payload["outcome"] == "rejected"
    assert payload["rejection_reason"] == "repository_too_large"
    assert payload["tree"]["candidate_count"] == SCOUT_MAX_CANDIDATE_ENTRIES + 1
    assert payload["tree"]["candidates"] == []


def test_filter_happy_path_accepts_with_complete_versioned_decisions() -> None:
    processor, recorded = _processor(_routes())
    scout = _scout(processor)
    outcome = _filter(processor, scout.payload)

    payload = outcome.payload
    assert payload["outcome"] == "accepted"
    assert payload["policy_version"] == FILTER_POLICY_VERSION
    assert payload["license_spdx"] == "MIT"
    decisions = payload["decisions"]
    assert len(decisions) == 8
    assert [decision["rule_id"] for decision in decisions] == [
        rule.value for rule in FilterRuleId
    ]
    for decision in decisions:
        assert set(decision) == {
            "rule_id",
            "rule_version",
            "observed",
            "result",
            "rationale",
        }
        assert decision["rule_version"] == FILTER_POLICY_VERSION
        assert decision["result"] == "pass"
        assert isinstance(decision["observed"], str)
        assert isinstance(decision["rationale"], str) and decision["rationale"]
    assert outcome.telemetry is not None
    assert outcome.telemetry.policy_version == FILTER_POLICY_VERSION
    assert outcome.telemetry.request_id == "REQ-LIC-0001"
    assert recorded.call_count(*LICENSE) == 1


@pytest.mark.parametrize(
    ("repo_fixture", "rule_id", "observed"),
    [
        (
            "repo_private",
            FilterRuleId.REPO_PUBLIC,
            "private=True,disabled=False,visibility=private",
        ),
        ("repo_archived", FilterRuleId.REPO_NOT_ARCHIVED, "archived=True"),
        ("repo_fork", FilterRuleId.REPO_NOT_FORK, "fork=True"),
    ],
)
def test_filter_repo_rule_variants_fail_with_observed_values(
    repo_fixture: str, rule_id: FilterRuleId, observed: str
) -> None:
    processor, _recorded = _processor(_routes(repo=repo_fixture))
    scout = _scout(processor)
    outcome = _filter(processor, scout.payload)

    payload = outcome.payload
    assert payload["outcome"] == "rejected"
    assert payload["license_spdx"] is None
    decision = _decision(payload, rule_id)
    assert decision["result"] == "fail"
    assert decision["observed"] == observed


def test_filter_fails_missing_default_branch_with_observed_value() -> None:
    routes = _routes()
    routes[META] = _metadata_variant(default_branch=None)
    processor, _recorded = _processor(routes)
    subject = SUBJECT.model_copy(update={"ref": "main"})
    scout = _scout(processor, subject)
    assert scout.payload["outcome"] == "accepted"

    outcome = _filter(processor, scout.payload, subject)
    decision = _decision(outcome.payload, FilterRuleId.REPO_HAS_DEFAULT_BRANCH)
    assert outcome.payload["outcome"] == "rejected"
    assert decision["result"] == "fail"
    assert decision["observed"] == "default_branch=None"


def test_filter_fails_missing_readme_with_observed_value() -> None:
    processor, _recorded = _processor(_routes(tree="tree_no_readme"))
    scout = _scout(processor)
    outcome = _filter(processor, scout.payload)

    decision = _decision(outcome.payload, FilterRuleId.REPO_HAS_README)
    assert outcome.payload["outcome"] == "rejected"
    assert decision["result"] == "fail"
    assert decision["observed"] == "has_root_readme=False"


@pytest.mark.parametrize(
    ("license_field", "observed"),
    [
        (None, "license_spdx=None"),
        (
            {
                "key": "other",
                "name": "Other",
                "spdx_id": "NOASSERTION",
                "url": None,
                "node_id": "MDc6TGljZW5zZTA=",
            },
            "license_spdx=NOASSERTION",
        ),
        (
            {
                "key": "gpl-3.0",
                "name": "GNU General Public License v3.0",
                "spdx_id": "GPL-3.0",
                "url": "https://api.github.com/licenses/gpl-3.0",
                "node_id": "MDc6TGljZW5zZTk=",
            },
            "license_spdx=GPL-3.0",
        ),
    ],
)
def test_filter_fails_unallowlisted_metadata_licenses_without_an_endpoint_call(
    license_field: object, observed: str
) -> None:
    routes = _routes()
    routes[META] = _metadata_variant(license=license_field)
    processor, recorded = _processor(routes)
    scout = _scout(processor)
    outcome = _filter(processor, scout.payload)

    payload = outcome.payload
    assert payload["outcome"] == "rejected"
    decision = _decision(payload, FilterRuleId.LICENSE_ALLOWLISTED)
    assert decision["result"] == "fail"
    assert decision["observed"] == observed
    confirmation = _decision(payload, FilterRuleId.LICENSE_CONFIRMED_AT_SHA)
    assert confirmation["result"] == "not_applicable"
    assert recorded.call_count(*LICENSE) == 0


def test_filter_fails_multiple_root_license_files_without_an_endpoint_call() -> None:
    processor, recorded = _processor(_routes(tree="tree_license_multiple"))
    scout = _scout(processor)
    outcome = _filter(processor, scout.payload)

    payload = outcome.payload
    assert payload["outcome"] == "rejected"
    decision = _decision(payload, FilterRuleId.LICENSE_SINGLE_FILE)
    assert decision["result"] == "fail"
    assert decision["observed"] == "root_license_files=2"
    confirmation = _decision(payload, FilterRuleId.LICENSE_CONFIRMED_AT_SHA)
    assert confirmation["result"] == "not_applicable"
    assert recorded.call_count(*LICENSE) == 0


@pytest.mark.parametrize(
    ("license_fixture", "observed"),
    [
        ("license_404", "status=not_found,observed_spdx=None"),
        ("license_noassertion", "status=noassertion,observed_spdx=None"),
        ("license_mismatch", "status=mismatch,observed_spdx=Apache-2.0"),
    ],
)
def test_filter_fails_unconfirmed_license_endpoint_outcomes(
    license_fixture: str, observed: str
) -> None:
    processor, recorded = _processor(_routes(license=license_fixture))
    scout = _scout(processor)
    outcome = _filter(processor, scout.payload)

    payload = outcome.payload
    assert payload["outcome"] == "rejected"
    decision = _decision(payload, FilterRuleId.LICENSE_CONFIRMED_AT_SHA)
    assert decision["result"] == "fail"
    assert decision["observed"] == observed
    assert recorded.call_count(*LICENSE) == 1


def test_downstream_stages_skip_deterministically_after_rejections() -> None:
    processor, recorded = _processor(_routes())
    rejected_scout: Mapping[str, object] = {
        "outcome": "rejected",
        "rejection_reason": "repository_too_large",
    }
    accepted_scout: Mapping[str, object] = {"outcome": "accepted"}
    rejected_filter: Mapping[str, object] = {"outcome": "rejected"}

    for stage in (PipelineStage.FILTER, PipelineStage.READER, PipelineStage.EXTRACTOR):
        outcome = processor.process(
            _stage_input(stage), _context(prior={"scout": rejected_scout})
        )
        assert outcome.payload == {
            "outcome": "skipped",
            "skip_reason": "scout_rejected",
        }
        assert outcome.telemetry is None

    for stage in (PipelineStage.READER, PipelineStage.EXTRACTOR):
        outcome = processor.process(
            _stage_input(stage),
            _context(prior={"scout": accepted_scout, "filter": rejected_filter}),
        )
        assert outcome.payload == {
            "outcome": "skipped",
            "skip_reason": "filter_rejected",
        }

    assert recorded.requests == []


def test_unhandled_stages_fail_closed() -> None:
    processor, _recorded = _processor(_routes())
    scout = _scout(processor)
    filter_outcome = _filter(processor, scout.payload)
    accepted_prior = {"scout": scout.payload, "filter": filter_outcome.payload}

    with pytest.raises(SafeFailure) as failure:
        processor.process(
            _stage_input(PipelineStage.EXTRACTOR), _context(prior=accepted_prior)
        )
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE

    with pytest.raises(SafeFailure) as failure:
        processor.process(
            _stage_input(PipelineStage.QUALIFIER), _context(prior=accepted_prior)
        )
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_rejected_run_completes_with_skips_and_consumes_no_retry_budget(
    tmp_path: Path,
) -> None:
    processor, recorded = _processor(_routes(repo="repo_archived"))
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        summary = PipelineRunner(store, processor).run(
            load_subject(APPROVED_SUBJECT), tmp_path / "output"
        )
        chain = store.verify_run_chain(summary.run_id)
        attempts = store.connection.execute(
            """SELECT stage, attempt_no, status, retryable FROM stage_attempts
               ORDER BY stage_index"""
        ).fetchall()
    finally:
        store.close()

    assert summary.status is RunStatus.COMPLETED
    assert [envelope.payload["outcome"] for envelope in chain.results] == [
        "accepted",
        "rejected",
        "skipped",
        "skipped",
    ]
    assert [
        (row["stage"], row["attempt_no"], row["status"], row["retryable"])
        for row in attempts
    ] == [
        ("scout", 1, AttemptStatus.SUCCEEDED.value, 0),
        ("filter", 1, AttemptStatus.SUCCEEDED.value, 0),
        ("reader", 1, AttemptStatus.SUCCEEDED.value, 0),
        ("extractor", 1, AttemptStatus.SUCCEEDED.value, 0),
    ]
    assert recorded.call_count(*META) == 1
    assert recorded.call_count(*PIN) == 1
    assert recorded.call_count(*TREE) == 1
    assert recorded.call_count(*LICENSE) == 1

    artifact = ExtractionSummary.model_validate_json(
        (tmp_path / "output" / "extraction-summary.json").read_bytes()
    )
    assert artifact.pinned_commit_sha == PINNED
    assert [entry.outcome for entry in artifact.stage_outcomes] == [
        "accepted",
        "rejected",
        "skipped",
        "skipped",
    ]
    assert artifact.extractor_outcome == "skipped"
    assert artifact.workflow_count == 0
    assert artifact.workflow_fingerprints == ()


def test_scout_rejected_run_skips_everything_without_content_fetches(
    tmp_path: Path,
) -> None:
    processor, recorded = _processor(_routes(pin="commits_pin_sha256"))
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        summary = PipelineRunner(store, processor).run(
            load_subject(APPROVED_SUBJECT), tmp_path / "output"
        )
        chain = store.verify_run_chain(summary.run_id)
    finally:
        store.close()

    assert summary.status is RunStatus.COMPLETED
    assert [envelope.payload["outcome"] for envelope in chain.results] == [
        "rejected",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert recorded.call_count(*META) == 1
    assert recorded.call_count(*PIN) == 1
    assert recorded.call_count(*TREE) == 0
    assert recorded.call_count(*LICENSE) == 0

    artifact = ExtractionSummary.model_validate_json(
        (tmp_path / "output" / "extraction-summary.json").read_bytes()
    )
    assert artifact.pinned_commit_sha is None
    assert artifact.extractor_outcome == "skipped"


def _reader_blob_routes() -> dict[tuple[str, str], RecordedResponse]:
    def blob(sha: str) -> tuple[str, str]:
        return ("GET", f"/repos/example/approved-repo/git/blobs/{sha}")

    return {
        blob("aa01" * 10): recorded_fixture("blob_readme"),
        blob("bb02" * 10): recorded_fixture("blob_doc"),
        blob("aa06" * 10): recorded_fixture("blob_example"),
        blob("cc08" * 10): recorded_fixture("blob_pyproject"),
        blob("ee10" * 10): make_blob_fixture(
            b"# lib helper\n" + b"h" * (1500 - 14) + b"\n", sha="ee10" * 10
        ),
        blob("dd09" * 10): recorded_fixture("blob_source"),
        blob("aa11" * 10): make_blob_fixture(
            b"# script\n" + b"s" * (700 - 10) + b"\n", sha="aa11" * 10
        ),
    }


def test_accepted_run_fails_closed_at_the_not_yet_implemented_extractor(
    tmp_path: Path,
) -> None:
    routes = _routes()
    routes.update(_reader_blob_routes())
    processor, recorded = _processor(routes)
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, processor).run(
                load_subject(APPROVED_SUBJECT), tmp_path / "output"
            )
        assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE
        attempts = store.connection.execute(
            """SELECT stage, status, retryable, error_code FROM stage_attempts
               ORDER BY stage_index"""
        ).fetchall()
    finally:
        store.close()

    assert [
        (row["stage"], row["status"], row["retryable"], row["error_code"])
        for row in attempts
    ] == [
        ("scout", AttemptStatus.SUCCEEDED.value, 0, None),
        ("filter", AttemptStatus.SUCCEEDED.value, 0, None),
        ("reader", AttemptStatus.SUCCEEDED.value, 0, None),
        (
            "extractor",
            AttemptStatus.FAILED.value,
            0,
            ErrorCode.STAGE_PERMANENT_FAILURE.value,
        ),
    ]
    assert recorded.call_count(*META) == 1
    assert recorded.call_count(*PIN) == 1
    assert recorded.call_count(*TREE) == 1
    assert recorded.call_count(*LICENSE) == 1
