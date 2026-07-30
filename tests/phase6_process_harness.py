"""Two-process production-graph crash/recovery harness for Phase 6 acceptance."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
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
    OperationsStateStore,
    _bundle_from_exports,
    _parse_bundle_exports,
    restore_acceptance_state_bundle,
)
from skillscout.adapters.publication_state import PublicationStateStore
from skillscout.adapters.state import SQLiteStateStore
from skillscout.adapters.state_branch import (
    StateOwnedFile,
    StateSyncObservation,
    VerifiedStateBundle,
)
from skillscout.application.acceptance import LiveRepositoryAuthority
from skillscout.application.ports import DurabilityReceipt
import skillscout.bootstrap as bootstrap
from skillscout.domain.acceptance import (
    AcceptanceScenarioResultV1,
    AcceptanceWarningV1,
    BenchmarkEntryV1,
    BenchmarkLockAttestationV1,
    LiveAcceptanceAuthorityV1,
    LockedBenchmarkManifestV1,
    NominationEntryV1,
    NominationSetV1,
)
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.discovery import (
    DiscoveryBudgetPolicyV1,
    DiscoveryQuerySetV1,
    DiscoveryStateRootV1,
)


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-07-30T12:00:00.000000Z"
RUN_ID = "acceptance-production-process-restart"
TARGET_NAME = "example/repository-1"
TARGET_ID = 840001
TARGET_SHA = "1" * 40
INITIAL_HEAD = "e" * 40
INITIAL_ROOT = "sha256:" + ("f" * 64)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _manifest() -> tuple[
    NominationSetV1,
    LockedBenchmarkManifestV1,
]:
    nominations = tuple(
        sorted(
            (
                NominationEntryV1(
                    schema_version="nomination-entry-v1",
                    repository_full_name=f"example/repository-{index}",
                    repository_id=840000 + index,
                    exact_commit_sha=f"{index:x}" * 40,
                    license_spdx="MIT",
                    selection_source="search_derived",
                    selection_evidence_digests=(
                        "sha256:" + f"{index:064x}",
                    ),
                )
                for index in range(1, 6)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    nomination = NominationSetV1(
        schema_version="nomination-set-v1",
        nomination_set_id=RUN_ID,
        query_set_digest="sha256:" + ("a" * 64),
        search_run_authority_digest="sha256:" + ("b" * 64),
        search_derived_entries=nominations,
        user_nominated_entries=(),
        created_at=TIMESTAMP,
    )
    roles = (
        "positive",
        "positive_multi_workflow",
        "negative",
        "negative",
        "borderline",
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
                    selection_source=entry.selection_source,
                    coverage_role=role,
                    nomination_entry_digest=entry.entry_digest,
                    selection_evidence_digests=entry.selection_evidence_digests,
                )
                for entry, role in zip(nominations, roles, strict=True)
            ),
            key=lambda item: item.entry_digest,
        )
    )
    values = {
        "schema_version": "locked-benchmark-manifest-v1",
        "manifest_version": 1,
        "nomination_set_digest": nomination.nomination_set_digest,
        "entries": entries,
        "prior_manifest_digest": None,
    }
    digest = sha256_digest(
        {
            **values,
            "entries": tuple(
                item.model_dump(mode="json", exclude_none=False)
                for item in entries
            ),
        }
    )
    return nomination, LockedBenchmarkManifestV1(
        **values,
        manifest_digest=digest,
        lock_attestation=BenchmarkLockAttestationV1(
            schema_version="benchmark-lock-attestation-v1",
            manifest_version=1,
            nomination_set_digest=nomination.nomination_set_digest,
            manifest_digest=digest,
            reviewer_id="acceptance-reviewer",
            locked_at=TIMESTAMP,
        ),
    )


def _query_set(workspace: Path) -> tuple[Path, DiscoveryQuerySetV1]:
    path = workspace / "config" / "discovery-queries-v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config/discovery-queries-v1.json", path)
    return path, DiscoveryQuerySetV1.model_validate_json(
        path.read_bytes(),
        strict=True,
    )


def _authority(
    manifest: LockedBenchmarkManifestV1,
    query_set: DiscoveryQuerySetV1,
) -> LiveAcceptanceAuthorityV1:
    return LiveAcceptanceAuthorityV1(
        schema_version="live-acceptance-authority-v1",
        authority_version=1,
        source_commit_sha="c" * 40,
        acceptance_workflow_sha256="sha256:" + ("d" * 64),
        manifest_path=(
            ".planning/phases/06-adversarial-mvp-acceptance/"
            "06-BENCHMARK-MANIFEST.json"
        ),
        manifest_digest=manifest.manifest_digest,
        nomination_set_digest=manifest.nomination_set_digest,
        lock_attestation_digest=manifest.lock_attestation.attestation_digest,
        state_commit_sha=INITIAL_HEAD,
        state_root_digest=INITIAL_ROOT,
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
        reviewer_id="acceptance-reviewer",
        approved_at=TIMESTAMP,
    )


def _paths(workspace: Path) -> tuple[Path, Path, Path]:
    state_dir = workspace / "state" / "databases"
    state_dir.mkdir(parents=True, exist_ok=True)
    return (
        state_dir / "pipeline.sqlite3",
        state_dir / "operations.sqlite3",
        state_dir / "publication.sqlite3",
    )


def _persist_bundle(workspace: Path, bundle: VerifiedStateBundle) -> None:
    bundle_dir = workspace / "remote-bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for item in bundle.files:
        destination = bundle_dir / item.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item.content)
        paths.append(item.path)
    _write_json(
        bundle_dir / "bundle.json",
        {
            "root": bundle.root.model_dump(mode="json", exclude_none=False),
            "paths": sorted(paths),
        },
    )


def _load_bundle(workspace: Path) -> VerifiedStateBundle:
    bundle_dir = workspace / "remote-bundle"
    value = json.loads((bundle_dir / "bundle.json").read_bytes())
    root = DiscoveryStateRootV1.model_validate(value["root"], strict=True)
    return VerifiedStateBundle(
        root=root,
        files=tuple(
            StateOwnedFile(path=path, content=(bundle_dir / path).read_bytes())
            for path in value["paths"]
        ),
    )


class LocalPersistentCAS:
    """Fake only the remote CAS while preserving real exports and bundles."""

    def __init__(
        self,
        *,
        workspace: Path,
        query_set_digest: str,
        budget_policy_digest: str,
        pipeline_path: Path,
        publication_path: Path,
        crash_status: str | None,
    ) -> None:
        self.workspace = workspace
        self.query_set_digest = query_set_digest
        self.budget_policy_digest = budget_policy_digest
        self.pipeline_path = pipeline_path
        self.publication_path = publication_path
        self.crash_status = crash_status
        history_path = workspace / "lineage.json"
        if history_path.exists():
            self.history = json.loads(history_path.read_bytes())
        else:
            self.history = [
                {"commit_sha": INITIAL_HEAD, "root_digest": INITIAL_ROOT}
            ]
        self._resume_lineage = (
            tuple(item["commit_sha"] for item in self.history),
            tuple(item["root_digest"] for item in self.history),
        )

    def configure_acceptance_resume(self, **arguments: object) -> None:
        commits = arguments["lineage_commit_shas"]
        roots = arguments["lineage_root_digests"]
        if type(commits) is not tuple or type(roots) is not tuple:
            raise ValueError("invalid local CAS resume lineage")
        self._resume_lineage = (commits, roots)

    def acceptance_resume_lineage(
        self,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return self._resume_lineage

    def acceptance_resume_locator(self) -> tuple[str | None, int]:
        return None, 0

    def prepare_acceptance_transition(self, **arguments: object) -> None:
        del arguments

    def _save(
        self,
        *,
        bundle: VerifiedStateBundle,
        previous_head: str,
    ) -> StateSyncObservation:
        ordinal = len(self.history)
        commit_sha = f"{ordinal:040x}"
        _persist_bundle(self.workspace, bundle)
        observation = StateSyncObservation(
            status="verified",
            previous_head=previous_head,
            commit_sha=commit_sha,
            tree_sha=f"{ordinal + 1000:040x}",
            root_digest=bundle.root.root_digest,
        )
        self.history.append(
            {
                "commit_sha": commit_sha,
                "root_digest": bundle.root.root_digest,
            }
        )
        _write_json(self.workspace / "lineage.json", self.history)
        return observation

    def sync_discovery(
        self,
        *,
        operations_store: OperationsStateStore,
        observed_head: str,
        prior_root_digest: str,
        created_at: str,
        pipeline_store: SQLiteStateStore | None = None,
        transition_phase: str = "scenario",
        semantic_stage: str | None = None,
        attempt_no: int | None = None,
        semantic_status: str | None = None,
        workflow_authority_digest: str | None = None,
    ) -> StateSyncObservation:
        del (
            transition_phase,
            semantic_stage,
            attempt_no,
            semantic_status,
            workflow_authority_digest,
        )
        owns_pipeline = pipeline_store is None
        pipeline = pipeline_store or SQLiteStateStore(self.pipeline_path)
        publication = PublicationStateStore(self.publication_path)
        try:
            bundle = _bundle_from_exports(
                pipeline=pipeline.export_owned_state(),
                operations=operations_store.export_owned_state(),
                publication=publication.export_owned_state(),
                prior_root_digest=prior_root_digest,
                state_parent_commit_sha=observed_head,
                query_set_digest=self.query_set_digest,
                budget_policy_digest=self.budget_policy_digest,
                created_at=created_at,
            )[0]
            observation = self._save(
                bundle=bundle,
                previous_head=observed_head,
            )
            self._resume_lineage = (
                (*self._resume_lineage[0], observation.commit_sha),
                (*self._resume_lineage[1], observation.root_digest),
            )
            return observation
        finally:
            publication.close()
            if owns_pipeline:
                pipeline.close()

    def confirm(
        self,
        *,
        transition: object,
        pipeline_store: SQLiteStateStore,
        operations_store: OperationsStateStore,
        publication_store: PublicationStateStore,
    ) -> DurabilityReceipt:
        bundle, _projection = _bundle_from_exports(
            pipeline=pipeline_store.export_owned_state(),
            operations=operations_store.export_owned_state(),
            publication=publication_store.export_owned_state(),
            prior_root_digest=transition.expected_prior_root_digest,
            state_parent_commit_sha=transition.expected_prior_state_head,
            query_set_digest=self.query_set_digest,
            budget_policy_digest=self.budget_policy_digest,
            created_at=transition.recorded_at,
        )
        observation = self._save(
            bundle=bundle,
            previous_head=transition.expected_prior_state_head,
        )
        pipeline, operations, publication, _ = _parse_bundle_exports(bundle)
        receipt = DurabilityReceipt.from_remote_verification(
            transition=transition,
            verified_state_head=observation.commit_sha,
            state_root_digest=bundle.root.root_digest,
            pipeline_database_digest=pipeline.database_digest,
            operations_database_digest=operations.database_digest,
            publication_database_digest=publication.database_digest,
            pipeline_projection_digest=pipeline.projection_digest,
            operations_projection_digest=operations.projection_digest,
            publication_projection_digest=publication.projection_digest,
        )
        if (
            self.crash_status is not None
            and transition.stage == "extractor"
            and transition.attempt_no == 3
            and transition.transition
            == {
                "decided": "result_decided",
                "confirmed_retryable": "result_confirmed_retryable",
                "semantic_outcome_unknown": "result_outcome_unknown",
            }[self.crash_status]
        ):
            _write_json(
                self.workspace / "crash.json",
                {
                    "pid": os.getpid(),
                    "third_status": self.crash_status,
                },
            )
            os._exit(86)
        self._resume_lineage = (
            (*self._resume_lineage[0], observation.commit_sha),
            (*self._resume_lineage[1], observation.root_digest),
        )
        return receipt


def _patch_github(entry: BenchmarkEntryV1) -> None:
    owner, name = entry.repository_full_name.split("/")
    metadata = json.loads(recorded_fixture("repo_mit").body)
    metadata.update(
        {
            "id": entry.repository_id,
            "name": name,
            "full_name": entry.repository_full_name,
        }
    )
    commit = json.loads(recorded_fixture("commits_pin").body)
    commit["sha"] = entry.exact_commit_sha
    license_payload = json.loads(recorded_fixture("license_mit").body)
    license_payload["url"] = (
        f"https://api.github.com/repos/{owner}/{name}/contents/LICENSE"
        f"?ref={entry.exact_commit_sha}"
    )

    def response(base: RecordedResponse, value: object) -> RecordedResponse:
        return RecordedResponse(
            status=base.status,
            headers=base.headers,
            body=json.dumps(value).encode(),
        )

    readme_sha = "aa01aa01aa01aa01aa01aa01aa01aa01aa01aa01"
    guide_sha = "bb02bb02bb02bb02bb02bb02bb02bb02bb02bb02"
    recording = RecordedTransport(
        {
            ("GET", f"/repos/{owner}/{name}"): response(
                recorded_fixture("repo_mit"), metadata
            ),
            (
                "GET",
                f"/repos/{owner}/{name}/commits/{entry.exact_commit_sha}",
            ): response(recorded_fixture("commits_pin"), commit),
            (
                "GET",
                f"/repos/{owner}/{name}/license?ref={entry.exact_commit_sha}",
            ): response(recorded_fixture("license_mit"), license_payload),
            (
                "GET",
                f"/repos/{owner}/{name}/git/trees/"
                f"{entry.exact_commit_sha}?recursive=1",
            ): make_tree_fixture(
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
    original = github_adapter.GitHubReadClient
    github_adapter.GitHubReadClient = lambda **kwargs: original(  # type: ignore[misc]
        **kwargs,
        transport=recording.transport(),
        sleeper=lambda _delay: None,
    )


def _deepseek_response(
    content: str,
    *,
    status: int,
) -> RecordedResponse:
    if status != 200:
        fixture = "openai_429" if status == 429 else "openai_500"
        return recorded_openai_fixture(fixture)
    return RecordedResponse(
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "id": "chatcmpl-extractor-3",
                "object": "chat.completion",
                "created": 1,
                "model": "deepseek-v4-flash",
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


def _patch_semantic_for_crash(workspace: Path, third_status: str) -> None:
    original = extract_adapter.OpenAIExtractionClient
    successful = json.loads(
        recorded_openai_fixture("parsed_zero_workflows").body
    )["output"][0]["content"][0]["text"]
    constructions = 0

    def extractor(**kwargs: object) -> object:
        nonlocal constructions
        constructions += 1
        calls_path = workspace / "provider-calls.json"
        calls = (
            json.loads(calls_path.read_bytes())
            if calls_path.exists()
            else []
        )
        calls.append({"attempt_no": constructions, "stage": "extractor"})
        _write_json(calls_path, calls)
        status = (
            429
            if constructions < 3 or third_status == "confirmed_retryable"
            else 500
            if third_status == "semantic_outcome_unknown"
            else 200
        )
        recording = RecordedTransport(
            {
                ("POST", "/chat/completions"): _deepseek_response(
                    successful,
                    status=status,
                )
            }
        )
        return original(
            **kwargs,
            api_key="local-placeholder",
            http_client=httpx.Client(transport=recording.transport()),
        )

    extract_adapter.OpenAIExtractionClient = extractor  # type: ignore[assignment]

    def forbidden(**_kwargs: object) -> NoReturn:
        raise AssertionError("Phase 3 provider constructed in extractor recovery")

    generate_adapter.OpenAIGenerationClient = forbidden  # type: ignore[assignment]
    review_adapter.OpenAIReviewClient = forbidden  # type: ignore[assignment]


def _patch_semantic_for_resume(workspace: Path) -> None:
    def forbidden(**_kwargs: object) -> NoReturn:
        path = workspace / "provider-calls-after-resume"
        path.write_text("1", encoding="ascii")
        raise AssertionError("provider authority reopened after durable attempt three")

    extract_adapter.OpenAIExtractionClient = forbidden  # type: ignore[assignment]
    generate_adapter.OpenAIGenerationClient = forbidden  # type: ignore[assignment]
    review_adapter.OpenAIReviewClient = forbidden  # type: ignore[assignment]


def _configs(
    *,
    workspace: Path,
    manifest: LockedBenchmarkManifestV1,
    authority: LiveAcceptanceAuthorityV1,
    query_path: Path,
    query_set: DiscoveryQuerySetV1,
    state_head: str,
    state_root: str,
    operations_path: Path,
    pipeline_path: Path,
    publication_path: Path,
    resume: bool,
) -> tuple[bootstrap.AcceptanceRuntimeConfig, bootstrap.DiscoveryRuntimeConfig]:
    lineage = json.loads((workspace / "lineage.json").read_bytes()) if resume else []
    acceptance = bootstrap.AcceptanceRuntimeConfig(
        manifest_path=(
            ROOT
            / ".planning/phases/06-adversarial-mvp-acceptance/"
            "06-BENCHMARK-MANIFEST.json"
        ),
        manifest=manifest,
        state_commit_sha=state_head,
        state_root_digest=state_root,
        semantic_provider="deepseek",
        extractor_model_id="deepseek-v4-flash",
        generator_model_id="deepseek-v4-flash",
        reviewer_model_id="deepseek-v4-pro",
        live_acceptance_authority_digest=authority.authority_digest,
        acceptance_run_id=RUN_ID if resume else None,
        resume_locator_digest=None,
        resume_transition_index=0,
        resume_lineage_commit_shas=tuple(
            item["commit_sha"] for item in lineage
        ),
        resume_lineage_root_digests=tuple(
            item["root_digest"] for item in lineage
        ),
    )
    discovery = bootstrap.DiscoveryRuntimeConfig(
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
    return acceptance, discovery


def _target(
    manifest: LockedBenchmarkManifestV1,
) -> tuple[BenchmarkEntryV1, LiveRepositoryAuthority]:
    entry = next(
        item for item in manifest.entries if item.repository_id == TARGET_ID
    )
    return entry, LiveRepositoryAuthority(
        repository_full_name=entry.repository_full_name,
        repository_id=entry.repository_id,
        exact_commit_sha=entry.exact_commit_sha,
        license_spdx=entry.license_spdx,
        nomination_entry_digest=entry.nomination_entry_digest,
        entry_digest=entry.entry_digest,
        selection_evidence_digests=entry.selection_evidence_digests,
    )


def crash(workspace: Path, third_status: str) -> NoReturn:
    nomination, manifest = _manifest()
    query_path, query_set = _query_set(workspace)
    authority = _authority(manifest, query_set)
    pipeline_path, operations_path, publication_path = _paths(workspace)
    pipeline = SQLiteStateStore(pipeline_path)
    publication = PublicationStateStore(publication_path)
    try:
        frozen_publication = publication.export_owned_state()
    finally:
        publication.close()
        pipeline.close()
    with OperationsStateStore(operations_path) as operations:
        operations.record_acceptance_fact(
            RUN_ID, "acceptance_nomination", nomination
        )
        operations.record_acceptance_fact(
            RUN_ID, "acceptance_benchmark_lock", manifest
        )
        operations.record_acceptance_fact(
            RUN_ID, "acceptance_live_authority", authority
        )
    acceptance, discovery = _configs(
        workspace=workspace,
        manifest=manifest,
        authority=authority,
        query_path=query_path,
        query_set=query_set,
        state_head=INITIAL_HEAD,
        state_root=INITIAL_ROOT,
        operations_path=operations_path,
        pipeline_path=pipeline_path,
        publication_path=publication_path,
        resume=False,
    )
    barrier = LocalPersistentCAS(
        workspace=workspace,
        query_set_digest=query_set.query_set_digest,
        budget_policy_digest=authority.budget_policy_digest,
        pipeline_path=pipeline_path,
        publication_path=publication_path,
        crash_status=third_status,
    )
    entry, repository_authority = _target(manifest)
    _patch_github(entry)
    _patch_semantic_for_crash(workspace, third_status)
    runner = bootstrap._FixedRepositoryAcceptanceRunner(
        config=acceptance,
        discovery_config=discovery,
        barrier=barrier,
        source={
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "DEEPSEEK_API_KEY": "local-placeholder",
            "SKILLSCOUT_SOURCE_GITHUB_TOKEN": "local-placeholder",
        },
        frozen_owner_export=frozen_publication,
        acceptance_run_id=RUN_ID,
    )
    runner.run(repository_authority)
    raise AssertionError("fault seam did not terminate after durable attempt three")


def resume(
    workspace: Path,
    third_status: str,
    result_path: Path,
) -> None:
    nomination, manifest = _manifest()
    del nomination
    query_path, query_set = _query_set(workspace)
    authority = _authority(manifest, query_set)
    pipeline_path, operations_path, publication_path = _paths(workspace)
    bundle = _load_bundle(workspace)
    restore_acceptance_state_bundle(
        bundle,
        pipeline_path=pipeline_path,
        operations_path=operations_path,
    )
    acceptance, discovery = _configs(
        workspace=workspace,
        manifest=manifest,
        authority=authority,
        query_path=query_path,
        query_set=query_set,
        state_head=json.loads((workspace / "lineage.json").read_bytes())[-1][
            "commit_sha"
        ],
        state_root=bundle.root.root_digest,
        operations_path=operations_path,
        pipeline_path=pipeline_path,
        publication_path=publication_path,
        resume=True,
    )
    barrier = LocalPersistentCAS(
        workspace=workspace,
        query_set_digest=query_set.query_set_digest,
        budget_policy_digest=authority.budget_policy_digest,
        pipeline_path=pipeline_path,
        publication_path=publication_path,
        crash_status=None,
    )
    entry, repository_authority = _target(manifest)
    _patch_github(entry)
    _patch_semantic_for_resume(workspace)
    frozen_publication = _parse_bundle_exports(bundle)[2]
    factory = bootstrap._fixed_acceptance_runner_factory(
        config=acceptance,
        discovery_config=discovery,
        restored=object(),
        barrier=barrier,
        source={
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "DEEPSEEK_API_KEY": "local-placeholder",
            "SKILLSCOUT_SOURCE_GITHUB_TOKEN": "local-placeholder",
        },
        frozen_owner_export=frozen_publication,
        acceptance_run_id=RUN_ID,
    )
    runner = factory(acceptance.state_commit_sha, acceptance.state_root_digest)
    observation = runner.run(repository_authority)
    runner.close()
    from skillscout.application.acceptance import (
        _candidate_funnel_for_observation,
        classify_acceptance_terminal,
    )

    terminal_class = classify_acceptance_terminal(observation.outcome)
    scenario = AcceptanceScenarioResultV1(
        schema_version="acceptance-scenario-result-v1",
        acceptance_run_id=RUN_ID,
        scenario_id=f"locked-1-{entry.repository_id}",
        repository_id=entry.repository_id,
        repository_full_name=entry.repository_full_name,
        exact_commit_sha=entry.exact_commit_sha,
        license_spdx=entry.license_spdx,
        benchmark_manifest_digest=manifest.manifest_digest,
        benchmark_entry_digest=observation.benchmark_entry_digest,
        live_acceptance_authority_digest=(
            observation.live_acceptance_authority_digest
        ),
        discovery_run_id=observation.discovery_run_id,
        discovery_run_authority_digest=(
            observation.discovery_run_authority_digest
        ),
        budget_reservation_digest=observation.budget_reservation_digest,
        fixed_candidate_admission_digest=(
            observation.fixed_candidate_admission_digest
        ),
        semantic_candidate_reservation_digest=(
            observation.semantic_candidate_reservation_digest
        ),
        terminal_class=terminal_class,
        outcome=observation.outcome,
        reason_code=observation.reason_code,
        evidence_digests=tuple(sorted(set(observation.evidence_digests))),
        candidate_funnel=_candidate_funnel_for_observation(
            observation.outcome,
            observation.semantic_telemetry,
        ),
        reader_order="readme_docs_examples_manifests_source",
        reader_file_count=observation.reader_file_count,
        reader_source_file_count=observation.reader_source_file_count,
        reader_total_bytes=observation.reader_total_bytes,
        reader_estimated_tokens=observation.reader_estimated_tokens,
        semantic_request_count=observation.semantic_request_count,
        semantic_request_reservation_digests=tuple(
            sorted(observation.semantic_request_reservation_digests)
        ),
        semantic_attempt_digests=tuple(
            sorted(observation.semantic_attempt_digests)
        ),
        semantic_telemetry=observation.semantic_telemetry,
        actual_models=observation.actual_models,
        prompt_versions=tuple(
            item.prompt_version for item in observation.semantic_telemetry
        ),
        schema_versions=tuple(
            item.output_schema_version for item in observation.semantic_telemetry
        ),
        policy_versions=tuple(
            item.policy_version for item in observation.semantic_telemetry
        ),
        workflow_fingerprint=observation.workflow_fingerprint,
        workflow_spec_authority_digest=(
            observation.workflow_spec_authority_digest
        ),
        workflow_execution_authority_digests=tuple(
            sorted(observation.workflow_execution_authority_digests)
        ),
        workflow_spec_authority_digests=tuple(
            sorted(observation.workflow_spec_authority_digests)
        ),
        candidate_terminal_digest=observation.candidate_terminal_digest,
        workflow_terminal_digests=tuple(
            sorted(observation.workflow_terminal_digests)
        ),
        phase3_terminal_summary_digests=tuple(
            sorted(observation.phase3_terminal_summary_digests)
        ),
        skill_artifact_digests=tuple(
            sorted(observation.skill_artifact_digests)
        ),
        package_digests=tuple(sorted(observation.package_digests)),
        eligible_locator=observation.eligible_locator,
        eligible_object_digest=observation.eligible_object_digest,
        expected_coverage_role=entry.coverage_role,
        evaluator_matches_observed=False,
        publication_decision="not_eligible",
        warnings=(
            AcceptanceWarningV1(
                warning_code="openai_live_absent",
                impact="Local process recovery covers the DeepSeek provider path.",
                follow_up="No live provider authority is granted by this test.",
                security_relevant=False,
            ),
        ),
        recorded_at=TIMESTAMP,
    )
    with OperationsStateStore(operations_path) as operations:
        operations.record_acceptance_fact(
            RUN_ID,
            "acceptance_scenario",
            scenario,
        )
        synchronized = barrier.sync_discovery(
            operations_store=operations,
            observed_head=observation.state_commit_sha,
            prior_root_digest=observation.state_root_digest,
            created_at=TIMESTAMP,
        )
        del synchronized
        discovery_snapshot = operations.snapshot_run(f"{RUN_ID}-semantic")
        acceptance_snapshot = operations.acceptance_snapshot(RUN_ID)
    scenario_count = sum(
        record.kind == "acceptance_scenario"
        for record in acceptance_snapshot.facts
    )
    workflow_specs = {
        item.workflow_spec_authority_digest
        for item in discovery_snapshot.workflow_terminals
        if item.workflow_spec_authority_digest is not None
    }
    skill_digests = {
        item.skill_artifact_digest
        for item in discovery_snapshot.workflow_terminals
        if item.skill_artifact_digest is not None
    }
    package_digests = {
        item.package_digest
        for item in discovery_snapshot.workflow_terminals
        if item.package_digest is not None
    }
    crash_fact = json.loads((workspace / "crash.json").read_bytes())
    _write_json(
        result_path,
        {
            "process_ids": [crash_fact["pid"], os.getpid()],
            "provider_calls": json.loads(
                (workspace / "provider-calls.json").read_bytes()
            ),
            "third_status": third_status,
            "candidate_terminal_count": len(
                discovery_snapshot.candidate_terminals
            ),
            "workflow_terminal_count": len(
                discovery_snapshot.workflow_terminals
            ),
            "semantic_attempts": [
                {
                    "attempt_no": item.attempt_no,
                    "stage": item.stage,
                    "status": item.status,
                }
                for item in discovery_snapshot.semantic_attempts
            ],
            "scenario_count": scenario_count,
            "workflow_spec_count": len(workflow_specs),
            "duplicate_workflow_spec_count": (
                len(discovery_snapshot.workflow_terminals)
                - len(
                    {
                        item.workflow_authority_digest
                        for item in discovery_snapshot.workflow_terminals
                    }
                )
            ),
            "duplicate_skill_count": len(skill_digests) - len(set(skill_digests)),
            "duplicate_package_count": (
                len(package_digests) - len(set(package_digests))
            ),
            "provider_calls_after_resume": int(
                (workspace / "provider-calls-after-resume").read_text(
                    encoding="ascii"
                )
            )
            if (workspace / "provider-calls-after-resume").exists()
            else 0,
        },
    )


def main() -> int:
    if len(sys.argv) not in {4, 5}:
        return 2
    action = sys.argv[1]
    workspace = Path(sys.argv[2]).resolve()
    third_status = sys.argv[3]
    if third_status not in {
        "decided",
        "confirmed_retryable",
        "semantic_outcome_unknown",
    }:
        return 2
    os.chdir(workspace)
    if action == "crash" and len(sys.argv) == 4:
        crash(workspace, third_status)
    if action == "resume" and len(sys.argv) == 5:
        resume(workspace, third_status, Path(sys.argv[4]))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
