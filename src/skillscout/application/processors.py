"""phase2-v1 stage processor with Scout/Filter dispatch and deterministic skips."""

from __future__ import annotations

import re
import time
from typing import Iterable, Mapping

from pydantic import ValidationError

from skillscout.adapters.github import GitHubReadClient, LicenseResponse, TreeEntry
from skillscout.application.ports import (
    ErrorCode,
    SafeFailure,
    StageContext,
    StageOutcome,
    StageTelemetry,
)
from skillscout.domain.canonical import sha256_digest
from skillscout.domain.enums import EffectScope, PipelineStage
from skillscout.domain.filtering import (
    ALLOWED_LICENSE_SPDX,
    FILTER_POLICY_VERSION,
    LicenseConfirmation,
    RepoFacts,
    TreeFacts,
    evaluate_filter,
)
from skillscout.domain.models import StageInput
from skillscout.domain.reading import (
    LFS_POINTER_PREFIX,
    READER_POLICY_VERSION,
    ReaderPolicy,
    ReadTier,
    RejectionRule,
    StopReason,
    TIER_ORDER,
    assign_tier,
    estimate_tokens,
    is_allowlisted_for_tier,
    validate_repo_path,
)
from skillscout.domain.subjects import RepositorySubject

SCOUT_MAX_CANDIDATE_ENTRIES = 512

_REPOSITORY_PREFIX = "https://github.com/"
_COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_CANDIDATE_ROOTS = frozenset({"docs", "examples", "src", "lib"})
_SPECIAL_MODES = frozenset({"160000", "120000"})


class PhaseTwoProcessor:
    """Deterministic Scout/Filter/Reader stages; the Extractor arrives in 02-04."""

    producer_version = "phase2-v1"

    def __init__(self, github: GitHubReadClient) -> None:
        self._github = github

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.REMOTE_READ

    @property
    def github(self) -> GitHubReadClient:
        return self._github

    def process(self, stage_input: StageInput, context: StageContext) -> StageOutcome:
        if stage_input.stage is PipelineStage.SCOUT:
            return self._scout(stage_input, context)
        if stage_input.stage in (
            PipelineStage.FILTER,
            PipelineStage.READER,
            PipelineStage.EXTRACTOR,
        ):
            skipped = _upstream_skip(context)
            if skipped is not None:
                return StageOutcome(payload=skipped, telemetry=None)
            if stage_input.stage is PipelineStage.FILTER:
                return self._filter(stage_input, context)
            if stage_input.stage is PipelineStage.READER:
                return self._reader(stage_input, context)
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)

    def _scout(self, stage_input: StageInput, context: StageContext) -> StageOutcome:
        started = time.monotonic()
        subject = context.subject
        if not isinstance(subject, RepositorySubject):
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
        owner, repo = _owner_repo(subject)
        metadata = self._github.get_repo_metadata(owner, repo)
        repository = {
            "id": metadata.id,
            "owner": metadata.owner,
            "name": metadata.name,
            "default_branch": metadata.default_branch,
            "private": metadata.private,
            "fork": metadata.fork,
            "archived": metadata.archived,
            "disabled": metadata.disabled,
            "visibility": metadata.visibility,
            "license_spdx": metadata.license_spdx,
        }

        ref = subject.ref if subject.ref is not None else metadata.default_branch
        rejection: str | None = None
        pinned: str | None = None
        tree_section: dict[str, object] | None = None
        if ref is None:
            rejection = "no_ref_resolvable"
        else:
            candidate_sha = self._github.resolve_commit(owner, repo, ref)
            if _COMMIT_SHA_PATTERN.fullmatch(candidate_sha) is None:
                rejection = "sha256_repository_unsupported"
            else:
                pinned = candidate_sha
                snapshot = self._github.get_tree(owner, repo, pinned)
                if snapshot.truncated:
                    rejection = "repository_too_large"
                    tree_section = {
                        "entry_count": len(snapshot.entries),
                        "truncated": True,
                        "candidate_count": 0,
                        "candidates": [],
                    }
                else:
                    candidates = _project_candidates(snapshot.entries)
                    if len(candidates) > SCOUT_MAX_CANDIDATE_ENTRIES:
                        rejection = "repository_too_large"
                        tree_section = {
                            "entry_count": len(snapshot.entries),
                            "truncated": False,
                            "candidate_count": len(candidates),
                            "candidates": [],
                        }
                    else:
                        tree_section = {
                            "entry_count": len(snapshot.entries),
                            "truncated": False,
                            "candidate_count": len(candidates),
                            "candidates": candidates,
                        }

        payload: dict[str, object] = {
            "schema_version": stage_input.schema_version,
            "stage": stage_input.stage.value,
            "subject_id": stage_input.subject_id,
            "outcome": "rejected" if rejection else "accepted",
            "rejection_reason": rejection,
            "repository": repository,
            "ref_requested": subject.ref,
            "pinned_commit_sha": pinned,
            "redirect": [
                {"from_url": item.from_url, "to_url": item.to_url}
                for item in self._github.redirects
            ],
            "rate_limit": {
                "limit": metadata.rate_limit.limit,
                "remaining": metadata.rate_limit.remaining,
                "reset": metadata.rate_limit.reset,
            },
            "tree": tree_section,
        }
        return StageOutcome(payload=payload, telemetry=self._telemetry(started))

    def _filter(self, stage_input: StageInput, context: StageContext) -> StageOutcome:
        started = time.monotonic()
        scout = context.prior_payloads.get("scout")
        subject = context.subject
        if not isinstance(scout, Mapping) or not isinstance(subject, RepositorySubject):
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
        repository = scout.get("repository")
        tree = scout.get("tree")
        pinned = scout.get("pinned_commit_sha")
        candidates = tree.get("candidates") if isinstance(tree, Mapping) else None
        if (
            not isinstance(repository, Mapping)
            or not isinstance(pinned, str)
            or not isinstance(candidates, list)
        ):
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)

        try:
            repo_facts = RepoFacts(
                private=repository["private"],
                archived=repository["archived"],
                fork=repository["fork"],
                disabled=repository["disabled"],
                visibility=repository["visibility"],
                default_branch=repository["default_branch"],
                license_spdx=repository["license_spdx"],
            )
            tree_facts = _tree_facts(candidates)
        except (KeyError, TypeError, ValidationError, ValueError):
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None

        license_confirmation = LicenseConfirmation(status="not_found", observed_spdx=None)
        license_requested = False
        if (
            repo_facts.license_spdx in ALLOWED_LICENSE_SPDX
            and len(tree_facts.root_license_files) <= 1
        ):
            owner, repo = _owner_repo(subject)
            response = self._github.get_license(owner, repo, pinned)
            license_requested = True
            license_confirmation = _license_confirmation(
                response, repo_facts.license_spdx
            )

        verdict = evaluate_filter(repo_facts, tree_facts, license_confirmation)
        payload: dict[str, object] = {
            "schema_version": stage_input.schema_version,
            "stage": stage_input.stage.value,
            "subject_id": stage_input.subject_id,
            "outcome": "accepted" if verdict.accepted else "rejected",
            "policy_version": FILTER_POLICY_VERSION,
            "decisions": [
                decision.model_dump(mode="json", exclude_none=False)
                for decision in verdict.decisions
            ],
            "license_spdx": repo_facts.license_spdx if verdict.accepted else None,
        }
        return StageOutcome(
            payload=payload,
            telemetry=StageTelemetry(
                policy_version=FILTER_POLICY_VERSION,
                request_id=self._github.last_request_id if license_requested else None,
                latency_ms=_elapsed_ms(started),
            ),
        )

    def _reader(self, stage_input: StageInput, context: StageContext) -> StageOutcome:
        started = time.monotonic()
        scout = context.prior_payloads.get("scout")
        subject = context.subject
        if not isinstance(scout, Mapping) or not isinstance(subject, RepositorySubject):
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
        tree = scout.get("tree")
        candidates = tree.get("candidates") if isinstance(tree, Mapping) else None
        if not isinstance(candidates, list):
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
        owner, repo = _owner_repo(subject)
        policy = ReaderPolicy()

        survivors: list[tuple[int, str, ReadTier, str, int]] = []
        rejections: list[dict[str, object]] = []
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
            path = candidate.get("path")
            mode = candidate.get("mode")
            sha = candidate.get("sha")
            size = candidate.get("size")
            if (
                not isinstance(path, str)
                or not isinstance(mode, str)
                or not isinstance(sha, str)
                or not (size is None or type(size) is int)
            ):
                raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
            if not validate_repo_path(path):
                rejections.append(_rejection(path, RejectionRule.PATH_VIOLATION, path))
                continue
            if mode == "160000":
                rejections.append(_rejection(path, RejectionRule.SUBMODULE, mode))
                continue
            if mode == "120000":
                rejections.append(_rejection(path, RejectionRule.SYMLINK, mode))
                continue
            tier = assign_tier(path)
            if tier is None or not is_allowlisted_for_tier(tier, path):
                rejections.append(
                    _rejection(
                        path,
                        RejectionRule.NON_ALLOWLISTED_EXTENSION,
                        path.rsplit("/", 1)[-1],
                    )
                )
                continue
            if type(size) is not int:
                raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
            if size > policy.max_file_bytes:
                rejections.append(
                    _rejection(path, RejectionRule.OVER_BUDGET_SIZE, str(size))
                )
                continue
            survivors.append((TIER_ORDER.index(tier), path, tier, sha, size))
        survivors.sort(key=lambda item: (item[0], item[1]))

        files: list[dict[str, object]] = []
        bundle: dict[str, str] = {}
        files_read = 0
        source_files_read = 0
        total_bytes = 0
        fetched = False
        stop_reason = StopReason.CANDIDATES_EXHAUSTED
        for tier_index, path, tier, sha, size in survivors:
            if _read_budget_stop(
                policy,
                files_read=files_read,
                source_files_read=source_files_read,
                total_bytes=total_bytes,
                tier=tier,
                size=size,
            ):
                stop_reason = StopReason.BUDGET_EXHAUSTED
                break
            raw = self._github.get_blob(owner, repo, sha, expected_size=size)
            fetched = True
            text, content_rejection = _classify_blob_content(raw)
            if content_rejection is not None:
                rule, observed = content_rejection
                rejections.append(_rejection(path, rule, observed))
                continue
            files_read += 1
            if tier is ReadTier.SOURCE:
                source_files_read += 1
            total_bytes += len(raw)
            bundle[path] = text
            files.append(
                {
                    "path": path,
                    "tier": tier.value,
                    "blob_sha": sha,
                    "size": size,
                    "content_hash": sha256_digest(raw),
                    "read_order": files_read,
                }
            )
            if (
                tier_index >= TIER_ORDER.index(ReadTier.EXAMPLES)
                and estimate_tokens(total_bytes) >= policy.early_stop_soft_tokens
            ):
                stop_reason = StopReason.SOFT_TARGET_REACHED
                break
        else:
            if files_read == 0:
                stop_reason = StopReason.NO_ALLOWLISTED_FILES

        context.scratch["read_bundle"] = bundle
        payload: dict[str, object] = {
            "schema_version": stage_input.schema_version,
            "stage": stage_input.stage.value,
            "subject_id": stage_input.subject_id,
            "outcome": "accepted",
            "policy_version": READER_POLICY_VERSION,
            "files": files,
            "rejections": rejections,
            "budgets": {
                "files_read": files_read,
                "source_files_read": source_files_read,
                "total_bytes": total_bytes,
                "estimated_input_tokens": estimate_tokens(total_bytes),
            },
            "source_code_loaded": source_files_read > 0,
            "stop_reason": stop_reason.value,
        }
        return StageOutcome(
            payload=payload,
            telemetry=StageTelemetry(
                policy_version=READER_POLICY_VERSION,
                request_id=self._github.last_request_id if fetched else None,
                latency_ms=_elapsed_ms(started),
            ),
        )

    def _telemetry(self, started: float) -> StageTelemetry:
        return StageTelemetry(
            request_id=self._github.last_request_id,
            latency_ms=_elapsed_ms(started),
        )


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _rejection(path: str, rule: RejectionRule, observed: str) -> dict[str, object]:
    return {"path": path, "rule": rule.value, "observed": observed}


def _read_budget_stop(
    policy: ReaderPolicy,
    *,
    files_read: int,
    source_files_read: int,
    total_bytes: int,
    tier: ReadTier,
    size: int,
) -> bool:
    """Return whether fetching the next candidate would cross a closed budget."""

    if files_read >= policy.max_files:
        return True
    if tier is ReadTier.SOURCE and source_files_read >= policy.max_source_files:
        return True
    if total_bytes + size > policy.max_total_bytes:
        return True
    return estimate_tokens(total_bytes + size) > policy.max_estimated_input_tokens


def _classify_blob_content(raw: bytes) -> tuple[str | None, tuple[RejectionRule, str] | None]:
    """Decode fetched bytes as inert text or return the closed rejection."""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, (RejectionRule.BINARY_CONTENT, "utf8_decode_failed")
    if b"\x00" in raw[:8192]:
        return None, (RejectionRule.BINARY_CONTENT, "nul_byte_detected")
    if text.startswith(LFS_POINTER_PREFIX):
        return None, (RejectionRule.LFS_POINTER, "lfs_pointer_prefix")
    return text, None


def hydrate_read_bundle(
    github_client: GitHubReadClient,
    owner: str,
    repo: str,
    files: Iterable[Mapping[str, object]],
) -> dict[str, str]:
    """Rebuild the in-memory read bundle from the persisted read plan.

    Every recorded file is re-fetched at its recorded blob SHA, re-checked
    against the binary/LFS rejections, and required to match its recorded
    sha256 content hash exactly; any deviation fails closed.
    """

    entries: list[tuple[int, str, str, int, str]] = []
    try:
        for entry in files:
            path = entry["path"]
            blob_sha = entry["blob_sha"]
            size = entry["size"]
            content_hash = entry["content_hash"]
            read_order = entry["read_order"]
            if (
                not isinstance(path, str)
                or not isinstance(blob_sha, str)
                or type(size) is not int
                or not isinstance(content_hash, str)
                or type(read_order) is not int
            ):
                raise TypeError("invalid recorded read-plan entry")
            entries.append((read_order, path, blob_sha, size, content_hash))
    except (KeyError, TypeError):
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None
    entries.sort()

    bundle: dict[str, str] = {}
    for _read_order, path, blob_sha, size, content_hash in entries:
        raw = github_client.get_blob(owner, repo, blob_sha, expected_size=size)
        text, content_rejection = _classify_blob_content(raw)
        if content_rejection is not None or text is None:
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None
        if sha256_digest(raw) != content_hash:
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None
        bundle[path] = text
    return bundle


def _owner_repo(subject: RepositorySubject) -> tuple[str, str]:
    path = subject.repository.removeprefix(_REPOSITORY_PREFIX).removesuffix(".git")
    owner, separator, repo = path.partition("/")
    if not owner or not separator or not repo or "/" in repo:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
    return owner, repo


def _upstream_skip(context: StageContext) -> dict[str, object] | None:
    scout = context.prior_payloads.get("scout")
    if not isinstance(scout, Mapping) or scout.get("outcome") != "accepted":
        return {"outcome": "skipped", "skip_reason": "scout_rejected"}
    filter_payload = context.prior_payloads.get("filter")
    if filter_payload is None:
        return None
    if not isinstance(filter_payload, Mapping) or filter_payload.get("outcome") != "accepted":
        return {"outcome": "skipped", "skip_reason": "filter_rejected"}
    return None


def _is_candidate(entry: TreeEntry) -> bool:
    if assign_tier(entry.path) is not None:
        return True
    segments = entry.path.split("/")
    if len(segments) == 1:
        return segments[0].lower().startswith(("license", "copying", "readme"))
    return entry.mode in _SPECIAL_MODES and segments[0] in _CANDIDATE_ROOTS


def _project_candidates(entries: tuple[TreeEntry, ...]) -> list[dict[str, object]]:
    candidates = [
        {
            "path": entry.path,
            "mode": entry.mode,
            "type": entry.type,
            "size": entry.size,
            "sha": entry.sha,
        }
        for entry in entries
        if _is_candidate(entry)
    ]
    candidates.sort(key=lambda item: str(item["path"]))
    return candidates


def _tree_facts(candidates: list[object]) -> TreeFacts:
    root_names = [
        item["path"]
        for item in candidates
        if isinstance(item, Mapping)
        and isinstance(item.get("path"), str)
        and "/" not in item["path"]
    ]
    lowered = [(name, name.lower()) for name in root_names]
    has_readme = any(lower.startswith("readme") for _name, lower in lowered)
    license_files = tuple(
        sorted(
            name
            for name, lower in lowered
            if lower.startswith(("license", "copying"))
        )
    )
    return TreeFacts(has_root_readme=has_readme, root_license_files=license_files)


def _license_confirmation(
    response: LicenseResponse, metadata_spdx: str | None
) -> LicenseConfirmation:
    if response.status == "not_found":
        return LicenseConfirmation(status="not_found", observed_spdx=None)
    if response.status == "noassertion":
        return LicenseConfirmation(status="noassertion", observed_spdx=None)
    if response.spdx_id != metadata_spdx:
        return LicenseConfirmation(status="mismatch", observed_spdx=response.spdx_id)
    return LicenseConfirmation(status="confirmed", observed_spdx=response.spdx_id)
