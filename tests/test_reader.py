"""Budgeted tiered reader evidence over recorded fixtures and synthetic matrices."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Mapping

import pytest

from recorded_transport import (
    RecordedResponse,
    RecordedTransport,
    make_blob_entry,
    make_blob_fixture,
    make_tree_fixture,
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
    PhaseTwoProcessor,
    _read_budget_stop,
    hydrate_read_bundle,
)
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.enums import ExecutionMode, PipelineStage
from skillscout.domain.models import (
    MAX_MANIFEST_BYTES,
    MAX_STAGE_STRING_BYTES,
    StageInput,
)
from skillscout.domain.reading import (
    READER_POLICY_VERSION,
    ReaderPolicy,
    ReadTier,
    StopReason,
)
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

README_SHA = "aa01aa01aa01aa01aa01aa01aa01aa01aa01aa01"
GUIDE_SHA = "bb02bb02bb02bb02bb02bb02bb02bb02bb02bb02"
EXTERNAL_SHA = "cc03cc03cc03cc03cc03cc03cc03cc03cc03cc03"
LINK_SHA = "dd04dd04dd04dd04dd04dd04dd04dd04dd04dd04"
BIG_SHA = "ee05ee05ee05ee05ee05ee05ee05ee05ee05ee05"
BASIC_SHA = "aa06aa06aa06aa06aa06aa06aa06aa06aa06aa06"
DATA_SHA = "bb07bb07bb07bb07bb07bb07bb07bb07bb07bb07"
LICENSE_SHA = "bb12bb12bb12bb12bb12bb12bb12bb12bb12bb12"
HELPER_SHA = "ee10ee10ee10ee10ee10ee10ee10ee10ee10ee10"
PYPROJECT_SHA = "cc08cc08cc08cc08cc08cc08cc08cc08cc08cc08"
SCRIPT_SHA = "aa11aa11aa11aa11aa11aa11aa11aa11aa11aa11"
CORE_SHA = "dd09dd09dd09dd09dd09dd09dd09dd09dd09dd09"
LFS_SHA = "fa01fa01fa01fa01fa01fa01fa01fa01fa01fa01"
BINARY_SHA = "fb02fb02fb02fb02fb02fb02fb02fb02fb02fb02"

README_CANARY = "A small reusable workflow repository used by SkillScout recorded tests."
HELPER_CONTENT = b"# lib helper\n" + b"h" * (1500 - 14) + b"\n"
SCRIPT_CONTENT = b"# script\n" + b"s" * (700 - 10) + b"\n"


def _sized(prefix: str, size: int) -> bytes:
    raw = prefix.encode()
    need = size - len(raw)
    assert need >= 2
    return raw + b"p" * (need - 1) + b"\n"


def _fixture_bytes(name: str) -> bytes:
    body = json.loads(recorded_fixture(name).body)
    return base64.b64decode(body["content"])


def _fixture_text(name: str) -> str:
    return _fixture_bytes(name).decode("utf-8")


def _blob(sha: str) -> tuple[str, str]:
    return ("GET", f"/repos/example/approved-repo/git/blobs/{sha}")


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


def _context(prior: dict[str, Mapping[str, object]] | None = None) -> StageContext:
    return StageContext(subject=SUBJECT, prior_payloads=prior or {}, scratch={})


def _reader(
    processor: PhaseTwoProcessor, candidates: list[dict[str, object]]
) -> tuple[StageOutcome, StageContext]:
    context = _context(
        {
            "scout": {"outcome": "accepted", "tree": {"candidates": candidates}},
            "filter": {"outcome": "accepted"},
        }
    )
    outcome = processor.process(_stage_input(PipelineStage.READER), context)
    return outcome, context


def _reader_setup(
    specs: list[tuple[str, bytes]],
) -> tuple[list[dict[str, object]], dict[tuple[str, str], RecordedResponse]]:
    candidates: list[dict[str, object]] = []
    routes: dict[tuple[str, str], RecordedResponse] = {}
    for path, content in specs:
        entry = make_blob_entry(path, content)
        candidates.append(entry)
        routes[_blob(str(entry["sha"]))] = make_blob_fixture(
            content, sha=str(entry["sha"])
        )
    return candidates, routes


def _sha_by_path(candidates: list[dict[str, object]]) -> dict[str, str]:
    return {str(entry["path"]): str(entry["sha"]) for entry in candidates}


def _happy_blob_routes() -> dict[tuple[str, str], RecordedResponse]:
    return {
        _blob(README_SHA): recorded_fixture("blob_readme"),
        _blob(GUIDE_SHA): recorded_fixture("blob_doc"),
        _blob(BASIC_SHA): recorded_fixture("blob_example"),
        _blob(PYPROJECT_SHA): recorded_fixture("blob_pyproject"),
        _blob(HELPER_SHA): make_blob_fixture(HELPER_CONTENT, sha=HELPER_SHA),
        _blob(CORE_SHA): recorded_fixture("blob_source"),
        _blob(SCRIPT_SHA): make_blob_fixture(SCRIPT_CONTENT, sha=SCRIPT_SHA),
    }


def _happy_routes() -> dict[tuple[str, str], RecordedResponse]:
    routes = {
        META: recorded_fixture("repo_mit"),
        PIN: recorded_fixture("commits_pin"),
        TREE: recorded_fixture("tree_full"),
        LICENSE: recorded_fixture("license_mit"),
    }
    routes.update(_happy_blob_routes())
    return routes


def _happy_reader_run(
    processor: PhaseTwoProcessor,
) -> tuple[StageOutcome, StageContext]:
    scout = processor.process(_stage_input(PipelineStage.SCOUT), _context())
    filter_outcome = processor.process(
        _stage_input(PipelineStage.FILTER), _context({"scout": scout.payload})
    )
    context = _context({"scout": scout.payload, "filter": filter_outcome.payload})
    outcome = processor.process(_stage_input(PipelineStage.READER), context)
    return outcome, context


def _strings(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, Mapping):
        return [text for key, value in node.items() for text in _strings(key) + _strings(value)]
    if isinstance(node, list):
        return [text for item in node for text in _strings(item)]
    return []


EXPECTED_TEXTS = {
    "README.md": _fixture_text("blob_readme"),
    "docs/guide.md": _fixture_text("blob_doc"),
    "examples/basic.md": _fixture_text("blob_example"),
    "pyproject.toml": _fixture_text("blob_pyproject"),
    "lib/helper.py": HELPER_CONTENT.decode(),
    "src/core.py": _fixture_text("blob_source"),
    "script.py": SCRIPT_CONTENT.decode(),
}
EXPECTED_SHAS = {
    "README.md": README_SHA,
    "docs/guide.md": GUIDE_SHA,
    "examples/basic.md": BASIC_SHA,
    "pyproject.toml": PYPROJECT_SHA,
    "lib/helper.py": HELPER_SHA,
    "src/core.py": CORE_SHA,
    "script.py": SCRIPT_SHA,
}
EXPECTED_TIERS = {
    "README.md": "readme",
    "docs/guide.md": "docs",
    "examples/basic.md": "examples",
    "pyproject.toml": "manifests",
    "lib/helper.py": "source",
    "src/core.py": "source",
    "script.py": "source",
}
EXPECTED_ORDER = [
    "README.md",
    "docs/guide.md",
    "examples/basic.md",
    "pyproject.toml",
    "lib/helper.py",
    "script.py",
    "src/core.py",
]

LFS_CONTENT = _fixture_bytes("blob_lfs")
BINARY_CONTENT = _fixture_bytes("blob_binary")


def test_reader_reads_in_exact_tier_order_with_sorted_paths() -> None:
    processor, recorded = _processor(_happy_routes())
    outcome, context = _happy_reader_run(processor)
    payload = outcome.payload

    assert set(payload) == {
        "schema_version",
        "stage",
        "subject_id",
        "outcome",
        "policy_version",
        "files",
        "rejections",
        "budgets",
        "source_code_loaded",
        "stop_reason",
    }
    assert payload["schema_version"] == "2"
    assert payload["stage"] == "reader"
    assert payload["subject_id"] == SUBJECT.subject_id
    assert payload["outcome"] == "accepted"
    assert payload["policy_version"] == READER_POLICY_VERSION
    assert payload["stop_reason"] == StopReason.CANDIDATES_EXHAUSTED.value
    assert payload["source_code_loaded"] is True

    files = payload["files"]
    assert [entry["path"] for entry in files] == EXPECTED_ORDER
    assert [entry["read_order"] for entry in files] == [1, 2, 3, 4, 5, 6, 7]
    for entry in files:
        assert set(entry) == {
            "path",
            "tier",
            "blob_sha",
            "size",
            "content_hash",
            "read_order",
        }
        path = str(entry["path"])
        assert entry["tier"] == EXPECTED_TIERS[path]
        assert entry["blob_sha"] == EXPECTED_SHAS[path]
        assert entry["size"] == len(EXPECTED_TEXTS[path].encode())
        assert entry["content_hash"] == sha256_digest(EXPECTED_TEXTS[path].encode())
    assert payload["budgets"] == {
        "files_read": 7,
        "source_files_read": 3,
        "total_bytes": 6142,
        "estimated_input_tokens": 1536,
    }

    assert payload["rejections"] == [
        {"path": "LICENSE", "rule": "non_allowlisted_extension", "observed": "LICENSE"},
        {"path": "docs/big.md", "rule": "over_budget_size", "observed": "200000"},
        {"path": "docs/external", "rule": "submodule", "observed": "160000"},
        {"path": "docs/link.md", "rule": "symlink", "observed": "120000"},
        {
            "path": "examples/data.bin",
            "rule": "non_allowlisted_extension",
            "observed": "data.bin",
        },
    ]
    for sha in (LICENSE_SHA, BIG_SHA, EXTERNAL_SHA, LINK_SHA, DATA_SHA):
        assert recorded.call_count(*_blob(sha)) == 0

    assert context.scratch["read_bundle"] == EXPECTED_TEXTS
    assert README_CANARY not in json.dumps(payload)
    assert all(
        len(text.encode()) <= MAX_STAGE_STRING_BYTES for text in _strings(payload)
    )

    telemetry = outcome.telemetry
    assert telemetry is not None
    assert telemetry.policy_version == READER_POLICY_VERSION
    assert telemetry.request_id == "REQ-BLOB-SRC1"
    assert telemetry.latency_ms is not None and telemetry.latency_ms >= 0


def test_budget_gate_boundaries_are_exact_with_a_lowered_policy() -> None:
    policy = ReaderPolicy(max_files=2, max_source_files=1, max_total_bytes=1000)
    gate = _read_budget_stop

    assert (
        gate(
            policy,
            files_read=1,
            source_files_read=0,
            total_bytes=0,
            tier=ReadTier.DOCS,
            size=0,
        )
        is False
    )
    assert (
        gate(
            policy,
            files_read=2,
            source_files_read=0,
            total_bytes=0,
            tier=ReadTier.DOCS,
            size=0,
        )
        is True
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=0,
            total_bytes=0,
            tier=ReadTier.SOURCE,
            size=0,
        )
        is False
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=1,
            total_bytes=0,
            tier=ReadTier.SOURCE,
            size=0,
        )
        is True
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=1,
            total_bytes=0,
            tier=ReadTier.DOCS,
            size=0,
        )
        is False
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=0,
            total_bytes=1000,
            tier=ReadTier.DOCS,
            size=0,
        )
        is False
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=0,
            total_bytes=1000,
            tier=ReadTier.DOCS,
            size=1,
        )
        is True
    )

    token_policy = ReaderPolicy(max_estimated_input_tokens=100)
    assert (
        gate(
            token_policy,
            files_read=0,
            source_files_read=0,
            total_bytes=396,
            tier=ReadTier.DOCS,
            size=4,
        )
        is False
    )
    assert (
        gate(
            token_policy,
            files_read=0,
            source_files_read=0,
            total_bytes=396,
            tier=ReadTier.DOCS,
            size=5,
        )
        is True
    )


def test_default_policy_gate_reflects_the_organization_ceilings() -> None:
    policy = ReaderPolicy()
    gate = _read_budget_stop

    assert (
        gate(
            policy,
            files_read=24,
            source_files_read=0,
            total_bytes=0,
            tier=ReadTier.DOCS,
            size=1,
        )
        is False
    )
    assert (
        gate(
            policy,
            files_read=25,
            source_files_read=0,
            total_bytes=0,
            tier=ReadTier.DOCS,
            size=1,
        )
        is True
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=4,
            total_bytes=0,
            tier=ReadTier.SOURCE,
            size=1,
        )
        is False
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=5,
            total_bytes=0,
            tier=ReadTier.SOURCE,
            size=1,
        )
        is True
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=0,
            total_bytes=159_999,
            tier=ReadTier.DOCS,
            size=1,
        )
        is False
    )
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=0,
            total_bytes=160_000,
            tier=ReadTier.DOCS,
            size=1,
        )
        is True
    )
    # Under the org ceilings the 40000-token estimate (160000 bytes) always binds
    # before the 524288-byte total, so the total gate can never be crossed.
    assert (
        gate(
            policy,
            files_read=0,
            source_files_read=0,
            total_bytes=524_288,
            tier=ReadTier.DOCS,
            size=0,
        )
        is True
    )


def test_reader_stops_at_max_files_before_the_26th_fetch() -> None:
    specs = [(f"docs/f{index:02d}.md", f"# doc {index}\n".encode()) for index in range(26)]
    candidates, routes = _reader_setup(specs)
    sha_by_path = _sha_by_path(candidates)
    processor, recorded = _processor(routes)
    outcome, _context = _reader(processor, candidates)
    payload = outcome.payload

    assert payload["stop_reason"] == StopReason.BUDGET_EXHAUSTED.value
    assert payload["budgets"]["files_read"] == 25
    assert [entry["path"] for entry in payload["files"]] == [
        f"docs/f{index:02d}.md" for index in range(25)
    ]
    assert [entry["read_order"] for entry in payload["files"]] == list(range(1, 26))
    assert recorded.call_count(*_blob(sha_by_path["docs/f25.md"])) == 0
    assert sum(recorded.calls.values()) == 25


def test_reader_stops_at_max_source_files_before_the_6th_fetch() -> None:
    specs = [(f"src/s{index}.py", f"# source {index}\n".encode()) for index in range(6)]
    candidates, routes = _reader_setup(specs)
    sha_by_path = _sha_by_path(candidates)
    processor, recorded = _processor(routes)
    outcome, _context = _reader(processor, candidates)
    payload = outcome.payload

    assert payload["stop_reason"] == StopReason.BUDGET_EXHAUSTED.value
    assert payload["source_code_loaded"] is True
    assert payload["budgets"]["files_read"] == 5
    assert payload["budgets"]["source_files_read"] == 5
    assert payload["budgets"]["total_bytes"] == sum(
        len(content) for _path, content in specs[:5]
    )
    assert [entry["path"] for entry in payload["files"]] == [
        f"src/s{index}.py" for index in range(5)
    ]
    assert recorded.call_count(*_blob(sha_by_path["src/s5.py"])) == 0
    assert sum(recorded.calls.values()) == 5


def test_reader_reads_max_file_bytes_exactly_and_never_fetches_one_byte_over() -> None:
    specs = [
        ("docs/exact.md", _sized("# exact\n", 131_072)),
        ("docs/over.md", _sized("# over\n", 131_073)),
    ]
    candidates, routes = _reader_setup(specs)
    sha_by_path = _sha_by_path(candidates)
    processor, recorded = _processor(routes)
    outcome, _context = _reader(processor, candidates)
    payload = outcome.payload

    assert [entry["path"] for entry in payload["files"]] == ["docs/exact.md"]
    assert payload["rejections"] == [
        {"path": "docs/over.md", "rule": "over_budget_size", "observed": "131073"}
    ]
    assert payload["stop_reason"] == StopReason.CANDIDATES_EXHAUSTED.value
    assert recorded.call_count(*_blob(sha_by_path["docs/over.md"])) == 0
    assert sum(recorded.calls.values()) == 1


def test_reader_stops_before_estimated_tokens_exceed_the_budget() -> None:
    specs = [
        ("docs/a.md", _sized("# a\n", 100_000)),
        ("docs/b.md", _sized("# b\n", 60_000)),
        ("docs/c.md", b"# c\n"),
    ]
    candidates, routes = _reader_setup(specs)
    sha_by_path = _sha_by_path(candidates)
    processor, recorded = _processor(routes)
    outcome, _context = _reader(processor, candidates)
    payload = outcome.payload

    assert [entry["path"] for entry in payload["files"]] == ["docs/a.md", "docs/b.md"]
    assert payload["budgets"]["total_bytes"] == 160_000
    assert payload["budgets"]["estimated_input_tokens"] == 40_000
    assert payload["stop_reason"] == StopReason.BUDGET_EXHAUSTED.value
    assert recorded.call_count(*_blob(sha_by_path["docs/c.md"])) == 0
    assert sum(recorded.calls.values()) == 2


def test_reader_early_stop_fires_only_after_the_examples_tier() -> None:
    specs = [
        ("README.md", _sized("# readme\n", 100_000)),
        ("docs/d.md", _sized("# d\n", 100)),
        ("examples/e.md", _sized("# e\n", 100)),
        ("pyproject.toml", _sized("[project]\n", 100)),
        ("src/x.py", _sized("# x\n", 100)),
    ]
    candidates, routes = _reader_setup(specs)
    sha_by_path = _sha_by_path(candidates)
    processor, recorded = _processor(routes)
    outcome, _context = _reader(processor, candidates)
    payload = outcome.payload

    assert [entry["path"] for entry in payload["files"]] == [
        "README.md",
        "docs/d.md",
        "examples/e.md",
    ]
    assert payload["stop_reason"] == StopReason.SOFT_TARGET_REACHED.value
    assert payload["budgets"]["estimated_input_tokens"] == 25_050
    assert recorded.call_count(*_blob(sha_by_path["docs/d.md"])) == 1
    assert recorded.call_count(*_blob(sha_by_path["pyproject.toml"])) == 0
    assert recorded.call_count(*_blob(sha_by_path["src/x.py"])) == 0
    assert sum(recorded.calls.values()) == 3


def test_reader_no_allowlisted_files_stops_without_any_fetch() -> None:
    candidates = [
        {
            "path": "LICENSE",
            "mode": "100644",
            "type": "blob",
            "size": 1100,
            "sha": LICENSE_SHA,
        },
        {
            "path": "docs/external",
            "mode": "160000",
            "type": "commit",
            "size": None,
            "sha": EXTERNAL_SHA,
        },
        {
            "path": "examples/data.bin",
            "mode": "100644",
            "type": "blob",
            "size": 9000,
            "sha": DATA_SHA,
        },
    ]
    processor, recorded = _processor({})
    outcome, context = _reader(processor, candidates)
    payload = outcome.payload

    assert payload["stop_reason"] == StopReason.NO_ALLOWLISTED_FILES.value
    assert payload["files"] == []
    assert payload["budgets"] == {
        "files_read": 0,
        "source_files_read": 0,
        "total_bytes": 0,
        "estimated_input_tokens": 0,
    }
    assert payload["source_code_loaded"] is False
    assert [entry["rule"] for entry in payload["rejections"]] == [
        "non_allowlisted_extension",
        "submodule",
        "non_allowlisted_extension",
    ]
    assert recorded.requests == []
    assert context.scratch["read_bundle"] == {}
    assert outcome.telemetry is not None
    assert outcome.telemetry.policy_version == READER_POLICY_VERSION
    assert outcome.telemetry.request_id is None


def test_reader_surfaces_carry_no_full_text_canary(tmp_path: Path) -> None:
    processor, _recorded = _processor(_happy_routes())
    store = SQLiteStateStore(tmp_path / "state.db")
    try:
        with pytest.raises(SafeFailure) as failure:
            PipelineRunner(store, processor).run(
                load_subject(APPROVED_SUBJECT), tmp_path / "output"
            )
        assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE
        rows = store.connection.execute(
            "SELECT stage, manifest_path FROM stage_results ORDER BY stage_index"
        ).fetchall()
    finally:
        store.close()

    assert [str(row["stage"]) for row in rows] == ["scout", "filter", "reader"]
    manifest_root = (tmp_path / "state.db").with_suffix(".manifests")
    manifests = {
        str(row["stage"]): (manifest_root / str(row["manifest_path"])).read_bytes()
        for row in rows
    }
    for manifest in manifests.values():
        assert len(manifest) <= MAX_MANIFEST_BYTES
        assert README_CANARY.encode() not in manifest
    reader_manifest = manifests["reader"]
    for text in EXPECTED_TEXTS.values():
        assert text.encode() not in reader_manifest
    assert README_CANARY.encode() not in (tmp_path / "state.db").read_bytes()


def test_reader_records_submodule_and_symlink_without_fetching() -> None:
    candidates = [
        {
            "path": "docs/external",
            "mode": "160000",
            "type": "commit",
            "size": None,
            "sha": EXTERNAL_SHA,
        },
        {
            "path": "docs/link.md",
            "mode": "120000",
            "type": "blob",
            "size": 31,
            "sha": LINK_SHA,
        },
    ]
    routes = {
        _blob(EXTERNAL_SHA): make_blob_fixture(b"submodule", sha=EXTERNAL_SHA),
        _blob(LINK_SHA): make_blob_fixture(b"docs/guide.md\n", sha=LINK_SHA),
    }
    processor, recorded = _processor(routes)
    outcome, _context = _reader(processor, candidates)
    payload = outcome.payload

    assert payload["rejections"] == [
        {"path": "docs/external", "rule": "submodule", "observed": "160000"},
        {"path": "docs/link.md", "rule": "symlink", "observed": "120000"},
    ]
    assert payload["files"] == []
    assert payload["stop_reason"] == StopReason.NO_ALLOWLISTED_FILES.value
    assert recorded.requests == []


@pytest.mark.parametrize(
    "path",
    [
        "docs/../evil.md",
        "docs//gap.md",
        "docs\\evil.md",
        "docs/evil\x00.md",
        "docs/" + "a" * 505 + ".md",
        "docs/a/b/c/d/e/f/g/h.md",
    ],
)
def test_reader_records_path_violations_without_fetching(path: str) -> None:
    sha = "f0" * 20
    candidates = [{"path": path, "mode": "100644", "type": "blob", "size": 10, "sha": sha}]
    routes = {_blob(sha): make_blob_fixture(b"0123456789", sha=sha)}
    processor, recorded = _processor(routes)
    outcome, _context = _reader(processor, candidates)
    payload = outcome.payload

    assert payload["rejections"] == [
        {"path": path, "rule": "path_violation", "observed": path}
    ]
    assert payload["files"] == []
    assert payload["stop_reason"] == StopReason.NO_ALLOWLISTED_FILES.value
    assert recorded.requests == []


def test_reader_records_non_allowlisted_extensions_without_fetching() -> None:
    candidates, routes = _reader_setup(
        [
            ("examples/data.bin", b"\x00" * 32),
            ("assets/pack.zip", b"PK\x03\x04" * 8),
        ]
    )
    processor, recorded = _processor(routes)
    outcome, _context = _reader(processor, candidates)
    payload = outcome.payload

    assert payload["rejections"] == [
        {
            "path": "examples/data.bin",
            "rule": "non_allowlisted_extension",
            "observed": "data.bin",
        },
        {
            "path": "assets/pack.zip",
            "rule": "non_allowlisted_extension",
            "observed": "pack.zip",
        },
    ]
    assert payload["files"] == []
    assert payload["stop_reason"] == StopReason.NO_ALLOWLISTED_FILES.value
    assert recorded.requests == []


def _rejection_chain(
    extra_entries: list[dict[str, object]],
    extra_routes: dict[tuple[str, str], RecordedResponse],
) -> tuple[StageOutcome, RecordedTransport]:
    license_entry = make_blob_entry("LICENSE", b"MIT License\n")
    readme_entry = make_blob_entry("README.md", b"# readme\n")
    routes = {
        META: recorded_fixture("repo_mit"),
        PIN: recorded_fixture("commits_pin"),
        TREE: make_tree_fixture([license_entry, readme_entry, *extra_entries]),
        LICENSE: recorded_fixture("license_mit"),
        _blob(str(readme_entry["sha"])): make_blob_fixture(
            b"# readme\n", sha=str(readme_entry["sha"])
        ),
    }
    routes.update(extra_routes)
    processor, recorded = _processor(routes)
    outcome, _context = _happy_reader_run(processor)
    return outcome, recorded


def test_reader_rejects_binary_content_after_exactly_one_fetch() -> None:
    binary_entry = make_blob_entry("docs/diagram.md", BINARY_CONTENT, sha=BINARY_SHA)
    outcome, recorded = _rejection_chain(
        [binary_entry], {_blob(BINARY_SHA): recorded_fixture("blob_binary")}
    )
    payload = outcome.payload

    assert payload["rejections"] == [
        {"path": "LICENSE", "rule": "non_allowlisted_extension", "observed": "LICENSE"},
        {
            "path": "docs/diagram.md",
            "rule": "binary_content",
            "observed": "utf8_decode_failed",
        },
    ]
    assert [entry["path"] for entry in payload["files"]] == ["README.md"]
    assert payload["stop_reason"] == StopReason.CANDIDATES_EXHAUSTED.value
    assert recorded.call_count(*_blob(BINARY_SHA)) == 1


def test_reader_rejects_lfs_pointer_after_exactly_one_fetch() -> None:
    lfs_entry = make_blob_entry("docs/weights.md", LFS_CONTENT, sha=LFS_SHA)
    outcome, recorded = _rejection_chain(
        [lfs_entry], {_blob(LFS_SHA): recorded_fixture("blob_lfs")}
    )
    payload = outcome.payload

    assert payload["rejections"] == [
        {"path": "LICENSE", "rule": "non_allowlisted_extension", "observed": "LICENSE"},
        {
            "path": "docs/weights.md",
            "rule": "lfs_pointer",
            "observed": "lfs_pointer_prefix",
        },
    ]
    assert [entry["path"] for entry in payload["files"]] == ["README.md"]
    assert payload["stop_reason"] == StopReason.CANDIDATES_EXHAUSTED.value
    assert recorded.call_count(*_blob(LFS_SHA)) == 1


def _hydration_client(
    routes: dict[tuple[str, str], RecordedResponse],
) -> tuple[GitHubReadClient, RecordedTransport]:
    recorded = RecordedTransport(routes)
    client = GitHubReadClient(
        transport=recorded.transport(), sleeper=lambda _seconds: None
    )
    return client, recorded


def test_hydrate_read_bundle_reproduces_the_scratch_bundle_byte_for_byte() -> None:
    processor, _recorded = _processor(_happy_routes())
    outcome, context = _happy_reader_run(processor)
    files = outcome.payload["files"]

    client, hydration = _hydration_client(_happy_blob_routes())
    bundle = hydrate_read_bundle(client, "example", "approved-repo", files)

    assert bundle == context.scratch["read_bundle"]
    assert sum(hydration.calls.values()) == len(files)
    for entry in files:
        assert hydration.call_count(*_blob(str(entry["blob_sha"]))) == 1


def test_hydrate_read_bundle_fails_closed_on_tampered_bytes() -> None:
    processor, _recorded = _processor(_happy_routes())
    outcome, _context = _happy_reader_run(processor)
    files = outcome.payload["files"]

    tampered_routes = _happy_blob_routes()
    tampered_routes[_blob(GUIDE_SHA)] = make_blob_fixture(
        _sized("# tampered guide\n", 800), sha=GUIDE_SHA
    )
    client, _hydration = _hydration_client(tampered_routes)
    with pytest.raises(SafeFailure) as failure:
        hydrate_read_bundle(client, "example", "approved-repo", files)
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_hydrate_read_bundle_fails_closed_on_a_new_content_rejection() -> None:
    files = [
        {
            "path": "docs/diagram.md",
            "tier": "docs",
            "blob_sha": BINARY_SHA,
            "size": len(BINARY_CONTENT),
            "content_hash": sha256_digest(BINARY_CONTENT),
            "read_order": 1,
        }
    ]
    client, _hydration = _hydration_client(
        {_blob(BINARY_SHA): recorded_fixture("blob_binary")}
    )
    with pytest.raises(SafeFailure) as failure:
        hydrate_read_bundle(client, "example", "approved-repo", files)
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE


def test_reader_run_performs_only_recorded_mock_transport_http(
    outbound_socket_sentinel: list[object],
) -> None:
    processor, recorded = _processor(_happy_routes())
    outcome, _context = _happy_reader_run(processor)

    assert outcome.payload["outcome"] == "accepted"
    assert outbound_socket_sentinel == []
    allowed_paths = {
        META[1],
        PIN[1],
        f"/repos/example/approved-repo/git/trees/{PINNED}",
        "/repos/example/approved-repo/license",
    } | {route[1] for route in _happy_blob_routes()}
    assert {request.url.path for request in recorded.requests} <= allowed_paths
