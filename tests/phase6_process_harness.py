"""Two-process production CLI crash/recovery harness for Phase 6 acceptance."""

from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import NoReturn

import httpx

from recorded_transport import (
    RecordedResponse,
    RecordedTransport,
    make_tree_fixture,
    recorded_fixture,
    recorded_openai_fixture,
)
import skillscout.adapters.github as github_adapter
import skillscout.adapters.openai_extract as extract_adapter
import skillscout.adapters.openai_generate as generate_adapter
import skillscout.adapters.openai_review as review_adapter
from skillscout.adapters.operations_state import (
    AcceptanceFactRecord,
    AcceptanceRunSnapshot,
    OperationsStateStore,
    _bundle_from_exports,
    _parse_bundle_exports,
    restore_acceptance_state_bundle,
)
from skillscout.adapters.publication_state import PublicationStateStore
from skillscout.adapters.state import SQLiteStateStore
import skillscout.adapters.state_branch as state_branch
import skillscout.bootstrap as bootstrap
from skillscout.adapters.state_branch import (
    StateBranchStore,
    StateCommitObservation,
    StateRefObservation,
    StateTreeEntry,
    VerifiedStateBundle,
)
import skillscout.cli as cli
from skillscout.domain.acceptance import (
    AcceptanceBudgetReservationV1,
    AcceptanceCampaignResumeLocatorV1,
    BenchmarkEntryV1,
    BenchmarkLockApprovalReceiptV2,
    BenchmarkLockAttestationV1,
    LiveAcceptanceAuthorityV2,
    LiveExecutionApprovalReceiptV2,
    LockedBenchmarkManifestV1,
    LockedBenchmarkManifestV2,
    NominationEntryV1,
    NominationSetV1,
)
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.discovery import (
    DiscoveryBudgetPolicyV1,
    DiscoveryQuerySetV1,
)


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-07-30T12:00:00.000000Z"
RUN_ID = "phase6-process-v2-local"
LOCK_HEAD = "500b3de1b14d8c0d1e0a4d3a35bf027eb19db2eb"
LOCK_ROOT = "sha256:a9131fdfec479202f1f626834c805bece17f933e802ecb9877827a9525f94d85"
STATE_REPOSITORY_ID = 1_310_897_029
STATE_REPOSITORY = "alexzhu0/skillscout"
REQUEST_HEADERS = {
    "content-type": "application/json",
    "x-github-request-id": "LOCAL-CAS-1",
}


def _lock_anchor() -> state_branch.StateLineageAnchor:
    """The fixed live authority bounds this harness's synthetic remote history."""

    return state_branch.StateLineageAnchor(
        commit_sha=LOCK_HEAD,
        root_digest=LOCK_ROOT,
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path, default: object) -> object:
    return json.loads(path.read_bytes()) if path.exists() else default


def _copy_repository(workspace: Path) -> tuple[Path, str]:
    repository = workspace / "repository"
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
    subprocess.run(("git", "add", "."), cwd=repository, check=True)
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=SkillScout Test",
            "-c",
            "user.email=skillscout@example.invalid",
            "commit",
            "-q",
            "-m",
            "test fixture",
        ),
        cwd=repository,
        check=True,
    )
    source_commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repository, source_commit


def _load_phase6_verifier() -> object:
    path = ROOT / "tools/verify_phase6_acceptance.py"
    spec = importlib.util.spec_from_file_location("_phase6_process_verifier", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _locked_bundle() -> VerifiedStateBundle:
    verifier = _load_phase6_verifier()
    observation = StateBranchStore(verifier._local_state_remote(ROOT, LOCK_HEAD)).restore()
    if (
        observation.status != "verified"
        or observation.observed_head != LOCK_HEAD
        or observation.bundle is None
        or observation.bundle.root.root_digest != LOCK_ROOT
    ):
        raise AssertionError("locked benchmark state unavailable")
    return observation.bundle


class DurableStateRemote:
    """Filesystem-backed fake remote behind the production state-client seam."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.path = workspace / "remote-cas.json"
        self.data = _read_json(
            self.path,
            {"head": None, "blobs": {}, "trees": {}, "commits": {}},
        )

    def close(self) -> None:
        pass

    def _save(self) -> None:
        _write_json(self.path, self.data)

    def seed(self, commit_sha: str, bundle: VerifiedStateBundle) -> None:
        blobs: dict[str, str] = self.data["blobs"]
        entries: list[dict[str, object]] = []
        for item in bundle.files:
            sha = state_branch._git_blob_id(item.content)
            blobs[sha] = base64.b64encode(item.content).decode("ascii")
            entries.append(
                {
                    "path": item.path,
                    "sha": sha,
                    "mode": "100644",
                    "size": len(item.content),
                }
            )
        entries.sort(key=lambda item: str(item["path"]))
        tree_sha = hashlib.sha1(
            canonical_json_bytes(tuple(entries)), usedforsecurity=False
        ).hexdigest()
        self.data["trees"][tree_sha] = entries
        self.data["commits"][commit_sha] = {
            "tree": tree_sha,
            "parents": (
                []
                if bundle.root.state_parent_commit_sha is None
                else [bundle.root.state_parent_commit_sha]
            ),
            "message": state_branch._state_commit_message(bundle.root.root_digest),
        }
        self.data["head"] = commit_sha
        self._save()

    def get_state_ref(self, *, read_budget: object | None = None) -> StateRefObservation:
        del read_budget
        head = self.data["head"]
        if type(head) is not str:
            raise state_branch.StateRefNotFound
        return StateRefObservation(state_branch.STATE_REF, head)

    def get_commit(
        self,
        sha: str,
        *,
        read_budget: object | None = None,
    ) -> StateCommitObservation:
        del read_budget
        value = self.data["commits"][sha]
        return StateCommitObservation(
            sha=sha,
            tree_sha=value["tree"],
            parents=tuple(value["parents"]),
            message=value["message"],
        )

    def get_tree(
        self,
        sha: str,
        *,
        read_budget: object | None = None,
    ) -> tuple[StateTreeEntry, ...]:
        del read_budget
        return tuple(
            StateTreeEntry(
                path=item["path"],
                sha=item["sha"],
                mode=item["mode"],
                size=item["size"],
            )
            for item in self.data["trees"][sha]
        )

    def get_blob(
        self,
        sha: str,
        *,
        read_budget: object | None = None,
    ) -> bytes:
        del read_budget
        return base64.b64decode(self.data["blobs"][sha], validate=True)

    def create_blob(self, content: bytes) -> str:
        sha = state_branch._git_blob_id(content)
        self.data["blobs"][sha] = base64.b64encode(content).decode("ascii")
        self._save()
        return sha

    def create_tree(self, entries: object) -> str:
        normalized = tuple(
            sorted(
                (
                    {
                        "path": str(item["path"]),
                        "sha": str(item["sha"]),
                        "mode": str(item["mode"]),
                        "size": len(self.get_blob(str(item["sha"]))),
                    }
                    for item in entries
                ),
                key=lambda item: item["path"],
            )
        )
        sha = hashlib.sha1(canonical_json_bytes(normalized), usedforsecurity=False).hexdigest()
        self.data["trees"][sha] = list(normalized)
        self._save()
        return sha

    def create_commit(
        self,
        message: str,
        tree: str,
        parents: object,
    ) -> str:
        parent_values = tuple(parents)
        preimage = canonical_json_bytes(
            {"message": message, "tree": tree, "parents": parent_values}
        )
        sha = hashlib.sha1(preimage, usedforsecurity=False).hexdigest()
        self.data["commits"][sha] = {
            "tree": tree,
            "parents": list(parent_values),
            "message": message,
        }
        self._save()
        return sha

    def create_state_ref(self, sha: str) -> StateRefObservation:
        if self.data["head"] is not None:
            raise state_branch.StateBranchConflict
        self.data["head"] = sha
        self._save()
        return StateRefObservation(state_branch.STATE_REF, sha)

    def update_state_ref(self, sha: str, *, force: bool) -> StateRefObservation:
        if force is not False:
            raise state_branch.StateBranchConflict
        self.data["head"] = sha
        self._save()
        self._maybe_crash(sha)
        return StateRefObservation(state_branch.STATE_REF, sha)

    def _maybe_crash(self, sha: str) -> None:
        fault_path = self.workspace / "fault.json"
        if not fault_path.exists() or (self.workspace / "crash.json").exists():
            return
        fault = json.loads(fault_path.read_bytes())
        calls = _read_json(self.workspace / "provider-calls.json", [])
        target_calls = [item for item in calls if item["stage"] == fault["stage"]]
        if len(target_calls) != 3:
            return
        bundle = StateBranchStore(self).restore_commit(
            sha,
            lineage_anchor=_lock_anchor(),
        )
        with TemporaryDirectory(prefix="skillscout-process-inspect-") as temporary:
            temporary_root = Path(temporary).resolve()
            restore_acceptance_state_bundle(
                bundle,
                pipeline_path=temporary_root / "pipeline.sqlite3",
                operations_path=temporary_root / "operations.sqlite3",
            )
            with OperationsStateStore(temporary_root / "operations.sqlite3") as operations:
                snapshot = operations.snapshot_run(f"{RUN_ID}-semantic")
                acceptance = operations.acceptance_snapshot(RUN_ID)
        expected = "confirmed_retryable" if fault["status"] == "exhaustion" else fault["status"]
        matching = tuple(
            item
            for item in snapshot.semantic_attempts
            if item.stage == fault["stage"] and item.attempt_no == 3 and item.status == expected
        )
        if len(matching) != 1:
            return
        locators = tuple(
            record.fact
            for record in acceptance.facts
            if record.kind == "acceptance_campaign_resume_locator"
        )
        latest_locator = max(locators, key=lambda item: item.transition_index)
        if fault["status"] == "exhaustion":
            target_repository_id = _read_json(
                self.workspace / "setup.json",
                {},
            ).get("target_repository_id")
            exhausted = tuple(
                item
                for item in snapshot.candidate_terminals
                if item.repository_id == target_repository_id
                and item.outcome == "confirmed_retryable"
            )
            if len(exhausted) != 1 or latest_locator.transition_phase != "terminal":
                return
        elif latest_locator.transition_phase != "result_durable":
            return
        _write_json(
            self.workspace / "crash.json",
            {
                "pid": os.getpid(),
                "stage": fault["stage"],
                "status": fault["status"],
                "transition_phase": latest_locator.transition_phase,
            },
        )
        os._exit(86)


def _patch_state_clients(workspace: Path) -> None:
    def client(**_kwargs: object) -> DurableStateRemote:
        return DurableStateRemote(workspace)

    state_branch.StateBranchClient = client  # type: ignore[assignment]
    state_branch.StateBranchReadClient = client  # type: ignore[assignment]

    def local_temporary_directory(*args: object, **kwargs: object) -> object:
        kwargs.setdefault("dir", workspace)
        return TemporaryDirectory(*args, **kwargs)

    bootstrap.tempfile.TemporaryDirectory = local_temporary_directory  # type: ignore[assignment]
    cli.TemporaryDirectory = local_temporary_directory  # type: ignore[assignment]


def _response(base: RecordedResponse, value: object) -> RecordedResponse:
    return RecordedResponse(
        status=base.status,
        headers=base.headers,
        body=json.dumps(value).encode(),
    )


def _patch_github(
    workspace: Path,
    manifest: LockedBenchmarkManifestV1,
) -> None:
    routes: dict[tuple[str, str], RecordedResponse] = {}
    for entry in manifest.entries:
        owner, name = entry.repository_full_name.split("/")
        metadata = json.loads(recorded_fixture("repo_mit").body)
        metadata.update(
            {
                "id": entry.repository_id,
                "name": name,
                "full_name": entry.repository_full_name,
            }
        )
        metadata["owner"]["login"] = owner
        metadata["license"]["spdx_id"] = entry.license_spdx
        commit = json.loads(recorded_fixture("commits_pin").body)
        commit["sha"] = entry.exact_commit_sha
        license_payload = json.loads(recorded_fixture("license_mit").body)
        license_payload["license"]["spdx_id"] = entry.license_spdx
        license_payload["url"] = (
            f"https://api.github.com/repos/{owner}/{name}/contents/LICENSE"
            f"?ref={entry.exact_commit_sha}"
        )
        readme_sha = "aa01aa01aa01aa01aa01aa01aa01aa01aa01aa01"
        guide_sha = "bb02bb02bb02bb02bb02bb02bb02bb02bb02bb02"
        routes.update(
            {
                ("GET", f"/repos/{owner}/{name}"): _response(
                    recorded_fixture("repo_mit"), metadata
                ),
                (
                    "GET",
                    f"/repos/{owner}/{name}/commits/{entry.exact_commit_sha}",
                ): _response(recorded_fixture("commits_pin"), commit),
                (
                    "GET",
                    f"/repos/{owner}/{name}/license?ref={entry.exact_commit_sha}",
                ): _response(recorded_fixture("license_mit"), license_payload),
                (
                    "GET",
                    f"/repos/{owner}/{name}/git/trees/{entry.exact_commit_sha}?recursive=1",
                ): make_tree_fixture(
                    [
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
                ),
                (
                    "GET",
                    f"/repos/{owner}/{name}/git/blobs/{readme_sha}",
                ): recorded_fixture("blob_readme"),
                (
                    "GET",
                    f"/repos/{owner}/{name}/git/blobs/{guide_sha}",
                ): recorded_fixture("blob_doc"),
            }
        )
    recorded = RecordedTransport(routes)
    original = github_adapter.GitHubReadClient

    class GitHubProxy:
        def __init__(self, client: object) -> None:
            self._client = client

        def get_repo_metadata(self, owner: str, repo: str) -> object:
            metadata = self._client.get_repo_metadata(owner, repo)
            _write_json(
                workspace / "current-repository.json",
                {"repository_id": metadata.id},
            )
            return metadata

        def __getattr__(self, name: str) -> object:
            return getattr(self._client, name)

    def github(**kwargs: object) -> object:
        return GitHubProxy(
            original(
                **kwargs,
                transport=recorded.transport(),
                sleeper=lambda _delay: None,
            )
        )

    github_adapter.GitHubReadClient = github  # type: ignore[assignment]


def _fixture_text(path: Path, key: str | None = None) -> str:
    value = json.loads(path.read_bytes())
    if key is not None:
        value = value[key]
    return value["body"]["output"][0]["content"][0]["text"]


def _deepseek_response(
    content: str,
    *,
    stage: str,
    status: int,
) -> RecordedResponse:
    if status != 200:
        return recorded_openai_fixture("openai_429" if status == 429 else "openai_500")
    model = "deepseek-v4-pro" if stage == "reviewer" else "deepseek-v4-flash"
    return RecordedResponse(
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "id": f"chatcmpl-{stage}-local",
                "object": "chat.completion",
                "created": 1,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
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


def _patch_semantic(
    workspace: Path,
    *,
    stage: str,
    status: str,
    process: int,
) -> None:
    parsed = json.loads(_fixture_text(ROOT / "tests/fixtures/openai/parsed_2_workflows.json"))
    parsed["workflows"] = parsed["workflows"][:1]
    one_workflow = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    zero_workflow = _fixture_text(ROOT / "tests/fixtures/openai/parsed_zero_workflows.json")
    generation = _fixture_text(
        ROOT / "tests/fixtures/openai/generator/cases.json",
        "parsed_success",
    )
    review = _fixture_text(
        ROOT / "tests/fixtures/openai/reviewer/cases.json",
        "parsed_yes",
    )
    target_repository_id = _read_json(workspace / "setup.json", {})["target_repository_id"]
    originals = {
        "extractor": extract_adapter.OpenAIExtractionClient,
        "generator": generate_adapter.OpenAIGenerationClient,
        "reviewer": review_adapter.OpenAIReviewClient,
    }

    def build(kind: str, content: str) -> object:
        def factory(**kwargs: object) -> object:
            current_repository_id = _read_json(
                workspace / "current-repository.json",
                {},
            ).get("repository_id")
            is_target = current_repository_id == target_repository_id
            if process == 2:
                after = _read_json(workspace / "provider-clients-after-resume.json", [])
                after.append({"stage": kind})
                _write_json(workspace / "provider-clients-after-resume.json", after)
            response_content = (
                zero_workflow
                if kind == "extractor" and not is_target
                else one_workflow
                if kind == "extractor"
                else content
            )

            def respond(_request: httpx.Request) -> httpx.Response:
                response_status = 200
                if process == 2:
                    after = _read_json(
                        workspace / "provider-requests-after-resume.json",
                        [],
                    )
                    after.append({"stage": kind})
                    _write_json(
                        workspace / "provider-requests-after-resume.json",
                        after,
                    )
                if is_target:
                    calls = _read_json(workspace / "provider-calls.json", [])
                    target_attempt = sum(item["stage"] == kind for item in calls) + 1
                    calls.append({"attempt_no": target_attempt, "stage": kind})
                    _write_json(workspace / "provider-calls.json", calls)
                    if kind == stage:
                        if target_attempt < 3:
                            response_status = 429
                        elif status in {"confirmed_retryable", "exhaustion"}:
                            response_status = 429
                        elif status == "semantic_outcome_unknown":
                            response_status = 500
                response = _deepseek_response(
                    response_content,
                    stage=kind,
                    status=response_status,
                )
                return httpx.Response(
                    status_code=response.status,
                    headers=response.headers,
                    content=response.body,
                )

            return originals[kind](
                **kwargs,
                api_key="local-placeholder",
                http_client=httpx.Client(transport=httpx.MockTransport(respond)),
            )

        return factory

    extract_adapter.OpenAIExtractionClient = build(  # type: ignore[assignment]
        "extractor", one_workflow
    )
    generate_adapter.OpenAIGenerationClient = build(  # type: ignore[assignment]
        "generator", generation
    )
    review_adapter.OpenAIReviewClient = build(  # type: ignore[assignment]
        "reviewer", review
    )


def _materialize_checkout(
    path: Path,
    *,
    bundle: VerifiedStateBundle,
    commit_sha: str,
) -> None:
    if path.exists():
        shutil.rmtree(path)
    for item in bundle.files:
        destination = path / item.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item.content)
    git_directory = path / ".git"
    git_directory.mkdir(parents=True)
    (git_directory / "HEAD").write_text(f"{commit_sha}\n", encoding="ascii")


def _manifest(repository: Path) -> LockedBenchmarkManifestV1:
    return LockedBenchmarkManifestV1.model_validate_json(
        (
            repository / "config/acceptance/phase6/benchmark-manifest.json"
        ).read_bytes(),
        strict=True,
    )


def _fresh_selection(
    *,
    seed: LockedBenchmarkManifestV1,
    query_set: DiscoveryQuerySetV1,
) -> tuple[NominationSetV1, LockedBenchmarkManifestV1]:
    """Create the local V1 selection that the synthetic V2 chain re-admits."""

    nominations = tuple(
        NominationEntryV1(
            schema_version="nomination-entry-v1",
            repository_full_name=entry.repository_full_name,
            repository_id=entry.repository_id,
            exact_commit_sha=entry.exact_commit_sha,
            license_spdx=entry.license_spdx,
            selection_source="search_derived",
            selection_evidence_digests=entry.selection_evidence_digests,
        )
        for entry in seed.entries
    )
    nomination = NominationSetV1(
        schema_version="nomination-set-v1",
        nomination_set_id=RUN_ID,
        query_set_digest=query_set.query_set_digest,
        search_run_authority_digest=sha256_digest(
            {"phase6_process_harness": "local_search_authority"}
        ),
        search_derived_entries=tuple(sorted(nominations, key=lambda entry: entry.entry_digest)),
        user_nominated_entries=(),
        created_at=TIMESTAMP,
    )
    roles = {entry.repository_id: entry.coverage_role for entry in seed.entries}
    entries = tuple(
        sorted(
            (
                BenchmarkEntryV1(
                    schema_version="benchmark-entry-v1",
                    repository_full_name=entry.repository_full_name,
                    repository_id=entry.repository_id,
                    exact_commit_sha=entry.exact_commit_sha,
                    license_spdx=entry.license_spdx,
                    selection_source=entry.selection_source,
                    coverage_role=roles[entry.repository_id],
                    nomination_entry_digest=entry.entry_digest,
                    selection_evidence_digests=entry.selection_evidence_digests,
                )
                for entry in nomination.search_derived_entries
            ),
            key=lambda entry: entry.entry_digest,
        )
    )
    preimage = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": nomination.nomination_set_digest,
        "entries": [entry.model_dump(mode="json", exclude_none=False) for entry in entries],
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
            reviewer_id="local-harness",
            locked_at=TIMESTAMP,
        ),
        manifest_digest=manifest_digest,
    )
    return nomination, manifest


def _amend_selection_manifest(
    repository: Path,
    manifest: LockedBenchmarkManifestV1,
    query_set: DiscoveryQuerySetV1,
) -> str:
    """Bind the copied test repository's source commit to canonical V2 inputs."""

    manifest_path = repository / "config/acceptance/phase6/benchmark-manifest.json"
    query_path = repository / "config/discovery-queries-v1.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    query_path.write_bytes(canonical_json_bytes(query_set))
    subprocess.run(("git", "add", manifest_path, query_path), cwd=repository, check=True)
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=SkillScout Test",
            "-c",
            "user.email=skillscout@example.invalid",
            "commit",
            "--amend",
            "--no-edit",
            "-q",
        ),
        cwd=repository,
        check=True,
    )
    return subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _fresh_lock(
    *,
    nomination: NominationSetV1,
    manifest: LockedBenchmarkManifestV1,
    source_commit: str,
    workflow_digest: str,
    query_set: DiscoveryQuerySetV1,
    parent_commit: str,
    parent_root: str,
) -> LockedBenchmarkManifestV2:
    """Construct a V2 lock through the same domain binding as production."""

    from skillscout.application.acceptance import bind_fresh_benchmark_lock

    snapshot = AcceptanceRunSnapshot(
        acceptance_run_id=RUN_ID,
        facts=(
            AcceptanceFactRecord(
                acceptance_run_id=RUN_ID,
                kind="acceptance_nomination",
                fact_digest=nomination.nomination_set_digest,
                fact=nomination,
            ),
        ),
    )
    lock_receipt = BenchmarkLockApprovalReceiptV2(
        schema_version="benchmark-lock-approval-receipt-v2",
        purpose="benchmark_lock",
        environment="phase6-human-benchmark-lock",
        source_repository_id=STATE_REPOSITORY_ID,
        source_repository_full_name=STATE_REPOSITORY,
        reviewer_login="alexzhu0",
        reviewer_id=101,
        workflow_run_id=1001,
        workflow_run_attempt=1,
        source_commit_sha=source_commit,
        workflow_sha256=workflow_digest,
        trigger_identity="workflow_dispatch:local-lock",
        approval_record_digest=sha256_digest({"local": "lock-approval"}),
    )
    lock = bind_fresh_benchmark_lock(
        snapshot=snapshot,
        selection_manifest=manifest,
        state_repository_id=STATE_REPOSITORY_ID,
        state_repository_full_name=STATE_REPOSITORY,
        parent_state_commit_sha=parent_commit,
        parent_state_root_digest=parent_root,
        expected_nomination_authority_digest=nomination.search_run_authority_digest,
        approval_receipt=lock_receipt,
    )
    return lock


def _live_authority(
    *,
    lock: LockedBenchmarkManifestV2,
    source_commit: str,
    workflow_digest: str,
    query_set: DiscoveryQuerySetV1,
    state_commit: str,
    state_root: str,
) -> LiveAcceptanceAuthorityV2:
    """Construct the V2 authority only after the local V2 lock is durable."""

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
        trigger_identity="workflow_dispatch:local-authority",
        approval_record_digest=sha256_digest({"local": "live-approval"}),
    )
    return LiveAcceptanceAuthorityV2(
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
        state_commit_sha=state_commit,
        state_root_digest=state_root,
        source_commit_sha=source_commit,
        acceptance_workflow_sha256=workflow_digest,
        source_state_binding_digest=lock.source_state_binding_digest,
        manifest_path="config/acceptance/phase6/benchmark-manifest.json",
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
        query_set_digest=query_set.query_set_digest,
        budget_policy_digest=DiscoveryBudgetPolicyV1().budget_policy_digest,
        semantic_provider="deepseek",
        provider_base_url="https://api.deepseek.com",
        stage_models=("deepseek-v4-flash", "deepseek-v4-flash", "deepseek-v4-pro"),
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
        approved_at=TIMESTAMP,
    )


def _setup(workspace: Path) -> dict[str, object]:
    repository, _ = _copy_repository(workspace)
    os.chdir(repository)
    query = DiscoveryQuerySetV1.model_validate_json(
        (repository / "config/discovery-queries-v1.json").read_bytes(), strict=True
    )
    nomination, manifest = _fresh_selection(seed=_manifest(repository), query_set=query)
    source_commit = _amend_selection_manifest(repository, manifest, query)
    workflow_digest = "sha256:" + hashlib.sha256(
        (repository / ".github/workflows/phase6-acceptance.yml").read_bytes()
    ).hexdigest()
    remote = DurableStateRemote(workspace)
    locked = _locked_bundle()
    remote.seed(LOCK_HEAD, locked)
    state_root = repository / "state/databases"
    restore_acceptance_state_bundle(
        locked,
        pipeline_path=state_root / "pipeline.sqlite3",
        operations_path=state_root / "operations.sqlite3",
    )
    with OperationsStateStore(state_root / "operations.sqlite3") as operations:
        operations.upgrade_acceptance_schema()

    def export_bundle(*, parent_commit: str, parent_root: str) -> VerifiedStateBundle:
        with OperationsStateStore(state_root / "operations.sqlite3") as operations:
            pipeline = SQLiteStateStore(state_root / "pipeline.sqlite3")
            publication = PublicationStateStore(state_root / "publication.sqlite3")
            try:
                bundle, _ = _bundle_from_exports(
                    pipeline=pipeline.export_owned_state(),
                    operations=operations.export_owned_state(),
                    publication=publication.export_owned_state(),
                    prior_root_digest=parent_root,
                    state_parent_commit_sha=parent_commit,
                    query_set_digest=query.query_set_digest,
                    budget_policy_digest=DiscoveryBudgetPolicyV1().budget_policy_digest,
                    created_at=TIMESTAMP,
                )
            finally:
                pipeline.close()
                publication.close()
        return bundle

    with OperationsStateStore(state_root / "operations.sqlite3") as operations:
        operations.record_acceptance_fact(RUN_ID, "acceptance_nomination", nomination)
    nomination_synced = StateBranchStore(remote).sync(
        export_bundle(parent_commit=LOCK_HEAD, parent_root=LOCK_ROOT),
        LOCK_HEAD,
        expected_prior_root_digest=LOCK_ROOT,
        lineage_anchor=_lock_anchor(),
    )
    lock = _fresh_lock(
        nomination=nomination,
        manifest=manifest,
        source_commit=source_commit,
        workflow_digest=workflow_digest,
        query_set=query,
        parent_commit=nomination_synced.commit_sha,
        parent_root=nomination_synced.root_digest,
    )
    with OperationsStateStore(state_root / "operations.sqlite3") as operations:
        operations.record_acceptance_fact(RUN_ID, "acceptance_benchmark_lock", lock)
    lock_synced = StateBranchStore(remote).sync(
        export_bundle(
            parent_commit=nomination_synced.commit_sha,
            parent_root=nomination_synced.root_digest,
        ),
        nomination_synced.commit_sha,
        expected_prior_root_digest=nomination_synced.root_digest,
        lineage_anchor=_lock_anchor(),
    )
    authority = _live_authority(
        lock=lock,
        source_commit=source_commit,
        workflow_digest=workflow_digest,
        query_set=query,
        state_commit=lock_synced.commit_sha,
        state_root=lock_synced.root_digest,
    )
    authority_locator = AcceptanceCampaignResumeLocatorV1(
        schema_version="acceptance-campaign-resume-locator-v1",
        acceptance_run_id=RUN_ID,
        live_acceptance_authority_digest=authority.authority_digest,
        source_commit_sha=authority.source_commit_sha,
        manifest_digest=authority.manifest_digest,
        state_repository_id=authority.state_repository_id,
        state_repository_full_name=authority.state_repository_full_name,
        original_state_commit_sha=authority.state_commit_sha,
        original_state_root_digest=authority.state_root_digest,
        parent_state_commit_sha=lock_synced.commit_sha,
        parent_state_root_digest=lock_synced.root_digest,
        transition_index=1,
        previous_locator_digest=None,
        transition_phase="authority_carrier",
        semantic_stage=None,
        attempt_no=None,
        semantic_status=None,
        workflow_authority_digest=None,
        semantic_provider=authority.semantic_provider,
        stage_models=authority.stage_models,
        prompt_versions=authority.prompt_versions,
        schema_versions=authority.schema_versions,
        policy_versions=authority.policy_versions,
        recorded_at=TIMESTAMP,
    )
    with OperationsStateStore(state_root / "operations.sqlite3") as operations:
        operations.record_acceptance_fact(RUN_ID, "acceptance_live_authority", authority)
        operations.record_acceptance_fact(
            RUN_ID, "acceptance_campaign_resume_locator", authority_locator
        )
    authority_synced = StateBranchStore(remote).sync(
        export_bundle(
            parent_commit=lock_synced.commit_sha,
            parent_root=lock_synced.root_digest,
        ),
        lock_synced.commit_sha,
        expected_prior_root_digest=lock_synced.root_digest,
        lineage_anchor=_lock_anchor(),
    )
    authority_state_bundle = StateBranchStore(remote).restore_commit(
        authority_synced.commit_sha, lineage_anchor=_lock_anchor()
    )
    _materialize_checkout(
        workspace / "authority-checkout",
        bundle=authority_state_bundle,
        commit_sha=authority_synced.commit_sha,
    )
    first_entry = manifest.entries[0]
    with OperationsStateStore(state_root / "operations.sqlite3") as operations:
        operations.record_acceptance_fact(
            RUN_ID,
            "acceptance_budget_reservation",
            AcceptanceBudgetReservationV1(
                schema_version="acceptance-budget-reservation-v1",
                acceptance_run_id=RUN_ID,
                benchmark_manifest_digest=manifest.manifest_digest,
                nomination_entry_digest=first_entry.nomination_entry_digest,
                benchmark_entry_digest=first_entry.entry_digest,
                repository_id=first_entry.repository_id,
                repository_full_name=first_entry.repository_full_name,
                ordinal=1,
                max_files=25,
                max_source_files=5,
                max_file_bytes=131_072,
                max_total_bytes=524_288,
                max_estimated_tokens=40_000,
                semantic_candidate_slots=1,
                campaign_semantic_request_limit=20,
                reserved_at=TIMESTAMP,
            ),
        )
        operations.record_acceptance_fact(
            RUN_ID,
            "acceptance_campaign_resume_locator",
            AcceptanceCampaignResumeLocatorV1(
                schema_version="acceptance-campaign-resume-locator-v1",
                acceptance_run_id=RUN_ID,
                live_acceptance_authority_digest=authority.authority_digest,
                source_commit_sha=authority.source_commit_sha,
                manifest_digest=authority.manifest_digest,
                state_repository_id=authority.state_repository_id,
                state_repository_full_name=authority.state_repository_full_name,
                original_state_commit_sha=authority.state_commit_sha,
                original_state_root_digest=authority.state_root_digest,
                parent_state_commit_sha=authority_synced.commit_sha,
                parent_state_root_digest=authority_synced.root_digest,
                transition_index=2,
                previous_locator_digest=authority_locator.locator_digest,
                transition_phase="budget_reserved",
                semantic_stage=None,
                attempt_no=None,
                semantic_status=None,
                workflow_authority_digest=None,
                semantic_provider=authority.semantic_provider,
                stage_models=authority.stage_models,
                prompt_versions=authority.prompt_versions,
                schema_versions=authority.schema_versions,
                policy_versions=authority.policy_versions,
                recorded_at=TIMESTAMP,
            ),
        )
    StateBranchStore(remote).sync(
        export_bundle(
            parent_commit=authority_synced.commit_sha,
            parent_root=authority_synced.root_digest,
        ),
        authority_synced.commit_sha,
        expected_prior_root_digest=authority_synced.root_digest,
        lineage_anchor=_lock_anchor(),
    )
    setup = {
        "repository": str(repository),
        "source_commit_sha": source_commit,
        "authority_digest": authority.authority_digest,
        "authority_head": authority_synced.commit_sha,
        "authority_root": authority_synced.root_digest,
        "lock_head": lock_synced.commit_sha,
        "lock_root": lock_synced.root_digest,
        "target_repository_id": manifest.entries[-1].repository_id,
    }
    _write_json(workspace / "setup.json", setup)
    return setup


def _environment(setup: dict[str, object]) -> None:
    os.environ.update(
        {
            "PHASE6_AUTHORITY_DIGEST": str(setup["authority_digest"]),
            "PHASE6_AUTHORITY_STATE_COMMIT_SHA": str(setup["authority_head"]),
            "PHASE6_AUTHORITY_STATE_ROOT_DIGEST": str(setup["authority_root"]),
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "DEEPSEEK_API_KEY": "local-placeholder",
            "SKILLSCOUT_SOURCE_GITHUB_TOKEN": "local-placeholder",
            "SKILLSCOUT_STATE_GITHUB_TOKEN": "local-placeholder",
            "SKILLSCOUT_STATE_REPOSITORY_ID": str(STATE_REPOSITORY_ID),
            "SKILLSCOUT_STATE_REPOSITORY_FULL_NAME": STATE_REPOSITORY,
        }
    )


def _record_cli(workspace: Path, command: str, process: int) -> None:
    commands = _read_json(workspace / "cli-commands.json", [])
    commands.append({"command": command, "process": process})
    _write_json(workspace / "cli-commands.json", commands)


def _run_cli(arguments: list[str]) -> dict[str, object]:
    output = StringIO()
    with redirect_stdout(output):
        code = cli.main(arguments)
    if code != 0:
        raise AssertionError(output.getvalue())
    lines = tuple(line for line in output.getvalue().splitlines() if line)
    if len(lines) != 1:
        raise AssertionError(lines)
    return json.loads(lines[0])


def _invoke_cli(arguments: list[str]) -> tuple[int, dict[str, object]]:
    """Invoke a production CLI command while retaining an expected error payload."""

    standard_output = StringIO()
    standard_error = StringIO()
    with redirect_stdout(standard_output), redirect_stderr(standard_error):
        code = cli.main(arguments)
    selected = standard_output if code == 0 else standard_error
    lines = tuple(line for line in selected.getvalue().splitlines() if line)
    if len(lines) != 1:
        raise AssertionError(lines)
    return code, json.loads(lines[0])


def _resolve_resume_proof(
    workspace: Path,
    setup: dict[str, object],
    *,
    process: int,
    filename: str,
) -> tuple[dict[str, object], Path]:
    remote = DurableStateRemote(workspace)
    head = remote.get_state_ref().sha
    head_bundle = StateBranchStore(remote).restore_commit(
        head,
        lineage_anchor=_lock_anchor(),
    )
    campaign_checkout = workspace / f"campaign-checkout-{process}"
    _materialize_checkout(
        campaign_checkout,
        bundle=head_bundle,
        commit_sha=head,
    )
    _record_cli(workspace, "resolve-acceptance-resume", process)
    arguments = [
        "resolve-acceptance-resume",
        "--authority-state-root",
        str(workspace / "authority-checkout"),
        "--authority-state-commit-sha",
        str(setup["authority_head"]),
        "--authority-state-root-digest",
        str(setup["authority_root"]),
        "--campaign-state-root",
        str(campaign_checkout),
        "--acceptance-run-id",
        RUN_ID,
        "--authority-digest",
        str(setup["authority_digest"]),
        "--source-commit-sha",
        str(setup["source_commit_sha"]),
        "--state-repository-id",
        str(STATE_REPOSITORY_ID),
        "--state-repository-full-name",
        STATE_REPOSITORY,
    ]
    proof = _run_cli(arguments)
    if (
        proof.get("lineage_commit_shas", [])[:2]
        != [str(setup["lock_head"]), str(setup["authority_head"])]
        or proof.get("lineage_root_digests", [])[:2]
        != [str(setup["lock_root"]), str(setup["authority_root"])]
    ):
        raise AssertionError("resume proof omitted the verified authority carrier")
    proof_path = workspace / filename
    _write_json(proof_path, proof)
    return proof, proof_path


def _locator_first_appearances(
    workspace: Path,
    *,
    authority_head: str,
    locator_digests: tuple[str, ...],
) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Derive each locator's first presence by restoring the real CAS lineage."""

    remote = DurableStateRemote(workspace)
    commit_chain: list[str] = []
    current = remote.get_state_ref().sha
    while True:
        commit_chain.append(current)
        if current == authority_head:
            break
        parents = remote.get_commit(current).parents
        if len(parents) != 1:
            raise AssertionError("acceptance CAS lineage is not linear")
        current = parents[0]
    commit_chain.reverse()

    first_positions: dict[str, int] = {}
    first_commits: dict[str, str] = {}
    seen: set[str] = set()
    store = StateBranchStore(remote)
    for position, commit_sha in enumerate(commit_chain, start=1):
        bundle = store.restore_commit(
            commit_sha,
            lineage_anchor=_lock_anchor(),
        )
        _, operations, _, _ = _parse_bundle_exports(bundle)
        present: set[str] = set()
        for fact in operations.facts:
            if fact.kind != "acceptance_campaign_resume_locator":
                continue
            payload = json.loads(fact.payload_json)
            value = payload.get("value")
            locator_digest = value.get("locator_digest") if isinstance(value, dict) else None
            if type(locator_digest) is not str:
                raise AssertionError("CAS locator fact has no canonical locator digest")
            present.add(locator_digest)
        for locator_digest in present - seen:
            first_positions[locator_digest] = position
            first_commits[locator_digest] = commit_sha
        seen.update(present)
    if set(locator_digests) != set(first_positions):
        raise AssertionError("locator first-appearance set disagrees with final CAS")
    return (
        tuple(first_positions[digest] for digest in locator_digests),
        tuple(first_commits[digest] for digest in locator_digests),
    )


def crash(workspace: Path, stage: str, status: str) -> NoReturn:
    setup = _setup(workspace)
    repository = Path(str(setup["repository"]))
    os.chdir(repository)
    manifest = _manifest(repository)
    _environment(setup)
    _patch_state_clients(workspace)
    _patch_github(workspace, manifest)
    _patch_semantic(workspace, stage=stage, status=status, process=1)
    _write_json(workspace / "fault.json", {"stage": stage, "status": status})
    proof, proof_path = _resolve_resume_proof(
        workspace,
        setup,
        process=1,
        filename="initial-resume-proof.json",
    )
    _record_cli(workspace, "run-acceptance", 1)
    _run_cli(
        [
            "run-acceptance",
            "--action",
            "benchmark",
            "--manifest",
            str(
                repository / "config/acceptance/phase6/benchmark-manifest.json"
            ),
            "--acceptance-run-id",
            RUN_ID,
            "--resume-proof",
            str(proof_path),
            "--state-commit-sha",
            str(proof["state_commit_sha"]),
            "--state-root-digest",
            str(proof["state_root_digest"]),
            "--authority-state-root",
            str(workspace / "authority-checkout"),
            "--authority-state-commit-sha",
            str(setup["authority_head"]),
            "--authority-state-root-digest",
            str(setup["authority_root"]),
        ]
    )
    raise AssertionError("fault seam did not terminate after durable attempt three")


def resume(
    workspace: Path,
    stage: str,
    status: str,
    result_path: Path,
) -> None:
    setup = json.loads((workspace / "setup.json").read_bytes())
    repository = Path(setup["repository"])
    os.chdir(repository)
    manifest = _manifest(repository)
    _environment(setup)
    _patch_state_clients(workspace)
    _patch_github(workspace, manifest)
    _patch_semantic(workspace, stage=stage, status=status, process=2)
    proof, proof_path = _resolve_resume_proof(
        workspace,
        setup,
        process=2,
        filename="resume-proof.json",
    )
    _record_cli(workspace, "run-acceptance", 2)
    benchmark_code, completed = _invoke_cli(
        [
            "run-acceptance",
            "--action",
            "benchmark",
            "--manifest",
            str(
                repository / "config/acceptance/phase6/benchmark-manifest.json"
            ),
            "--acceptance-run-id",
            RUN_ID,
            "--resume-proof",
            str(proof_path),
            "--state-commit-sha",
            proof["state_commit_sha"],
            "--state-root-digest",
            proof["state_root_digest"],
            "--authority-state-root",
            str(workspace / "authority-checkout"),
            "--authority-state-commit-sha",
            str(setup["authority_head"]),
            "--authority-state-root-digest",
            str(setup["authority_root"]),
        ]
    )
    if status == "decided":
        if benchmark_code != 0 or completed.get("status") != "benchmark_complete":
            raise AssertionError(completed)
    elif benchmark_code != 1 or completed.get("error", {}).get("code") != "state_integrity_error":
        raise AssertionError(completed)
    latest = DurableStateRemote(workspace)
    bundle = StateBranchStore(latest).restore(lineage_anchor=_lock_anchor())
    assert bundle.bundle is not None
    state_root = repository / "state/databases"
    restore_acceptance_state_bundle(
        bundle.bundle,
        pipeline_path=state_root / "pipeline.sqlite3",
        operations_path=state_root / "operations.sqlite3",
    )
    with OperationsStateStore(state_root / "operations.sqlite3") as operations:
        discovery = operations.snapshot_run(f"{RUN_ID}-semantic")
        acceptance = operations.acceptance_snapshot(RUN_ID)
    target_id = setup["target_repository_id"]
    target_attempts = tuple(
        item for item in discovery.semantic_attempts if item.repository_id == target_id
    )
    target_terminals = tuple(
        item for item in discovery.candidate_terminals if item.repository_id == target_id
    )
    target_scenarios = tuple(
        record
        for record in acceptance.facts
        if record.kind == "acceptance_scenario" and record.fact.repository_id == target_id
    )
    locator_records = tuple(
        sorted(
            (
                record
                for record in acceptance.facts
                if record.kind == "acceptance_campaign_resume_locator"
            ),
            key=lambda item: item.fact.transition_index,
        )
    )
    locators = tuple(record.fact for record in locator_records)
    locator_first_indexes, locator_first_commits = _locator_first_appearances(
        workspace,
        authority_head=str(setup["authority_head"]),
        locator_digests=tuple(record.fact_digest for record in locator_records),
    )
    workflow_specs = tuple(
        digest
        for record in target_scenarios
        for digest in record.fact.workflow_spec_authority_digests
    )
    phase3_artifacts = tuple(
        digest
        for record in target_scenarios
        for digest in record.fact.phase3_terminal_summary_digests
    )
    skill_digests = tuple(
        digest for record in target_scenarios for digest in record.fact.skill_artifact_digests
    )
    package_digests = tuple(
        digest for record in target_scenarios for digest in record.fact.package_digests
    )
    crash_fact = json.loads((workspace / "crash.json").read_bytes())
    calls = _read_json(workspace / "provider-calls.json", [])
    provider_clients_after = _read_json(
        workspace / "provider-clients-after-resume.json",
        [],
    )
    provider_requests_after = _read_json(
        workspace / "provider-requests-after-resume.json",
        [],
    )
    _write_json(
        result_path,
        {
            "process_ids": [crash_fact["pid"], os.getpid()],
            "cli_commands": _read_json(workspace / "cli-commands.json", []),
            "provider_calls": calls,
            "third_status": status,
            "crash_stage": stage,
            "crash_transition_phase": crash_fact["transition_phase"],
            "semantic_attempts": [
                {
                    "attempt_no": item.attempt_no,
                    "stage": item.stage,
                    "status": item.status,
                }
                for item in target_attempts
            ],
            "locator_transition_indexes": [item.transition_index for item in locators],
            "locator_first_appearance_indexes": locator_first_indexes,
            "locator_first_appearance_commit_shas": locator_first_commits,
            "resume_lineage_commit_shas": proof["lineage_commit_shas"],
            "resume_lineage_root_digests": proof["lineage_root_digests"],
            "expected_resume_lineage_commit_prefix": [
                str(setup["lock_head"]),
                str(setup["authority_head"]),
            ],
            "expected_resume_lineage_root_prefix": [
                str(setup["lock_root"]),
                str(setup["authority_root"]),
            ],
            "candidate_terminal_count": len(target_terminals),
            "workflow_terminal_count": sum(
                item.repository_id == target_id for item in discovery.workflow_terminals
            ),
            "scenario_count": len(target_scenarios),
            "phase3_artifact_count": len(set(phase3_artifacts)),
            "workflow_spec_count": len(set(workflow_specs)),
            "skill_count": len(set(skill_digests)),
            "package_count": len(set(package_digests)),
            "duplicate_workflow_spec_count": sum(
                item.repository_id == target_id for item in discovery.workflow_terminals
            )
            - len(
                {
                    item.workflow_authority_digest
                    for item in discovery.workflow_terminals
                    if item.repository_id == target_id
                }
            ),
            "duplicate_skill_count": len(skill_digests) - len(set(skill_digests)),
            "duplicate_package_count": len(package_digests) - len(set(package_digests)),
            "provider_requests_after_resume": provider_requests_after,
            "provider_clients_after_resume": provider_clients_after,
            "resume_benchmark_exit_code": benchmark_code,
            "resume_benchmark_payload": completed,
            "semantic_telemetry_stages": [
                item.stage for record in target_scenarios for item in record.fact.semantic_telemetry
            ],
        },
    )


def main() -> int:
    if len(sys.argv) not in {5, 6}:
        return 2
    action = sys.argv[1]
    workspace = Path(sys.argv[2]).resolve()
    stage = sys.argv[3]
    status = sys.argv[4]
    if stage not in {"extractor", "generator", "reviewer"}:
        return 2
    if status not in {
        "decided",
        "confirmed_retryable",
        "semantic_outcome_unknown",
        "exhaustion",
    }:
        return 2
    if action == "crash" and len(sys.argv) == 5:
        crash(workspace, stage, status)
    if action == "resume" and len(sys.argv) == 6:
        resume(workspace, stage, status, Path(sys.argv[5]))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
