"""Pure, bounded catalogues and deterministic materialization of selected evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Annotated, Literal, Mapping

from pydantic import Field, ValidationError

from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.extraction import (
    MAX_EVIDENCE_EXCERPT_CHARS,
    MAX_WORKFLOWS_PER_REPO,
    EvidenceRef,
    ExtractorWorkflow,
    WorkflowStep,
    _BlobSha,
    _BoundedText,
    _EvidencePath,
    _Excerpt,
    _ShortText,
    _TokenList,
    _TokenText,
    find_forbidden_text,
)
from skillscout.domain.models import Digest, StrictFrozenModel

EVIDENCE_CATALOG_POLICY_VERSION = "evidence-catalog-v1"
EVIDENCE_SELECTION_SCHEMA_VERSION = "extractor-evidence-selection-v1"
MAX_EVIDENCE_CATALOG_ENTRIES = 128

_EvidenceId = Annotated[str, Field(pattern=r"^e[0-9]{4}$")]
_Fence = re.compile(r"^[ \t]*(`{3,}|~{3,})([^\r\n]*)")
_SelectionErrorCode = Literal["unknown_evidence_id", "step_evidence_not_declared"]


class EvidenceCatalogEntry(StrictFrozenModel):
    """An exact inert substring bound to one source and character range."""

    evidence_id: _EvidenceId
    path: _EvidencePath
    blob_sha: _BlobSha
    content_hash: Digest
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    excerpt: _Excerpt


@dataclass(frozen=True)
class EvidenceCatalog:
    """In-memory catalogue; only audit() is suitable for content-free persistence."""

    entries: tuple[EvidenceCatalogEntry, ...]
    digest: str
    truncated: bool
    _payload: bytes

    def audit(self) -> dict[str, object]:
        """Return only policy identity, digest, count and truncation fact."""

        return {
            "policy_version": EVIDENCE_CATALOG_POLICY_VERSION,
            "digest": self.digest,
            "entry_count": len(self.entries),
            "truncated": self.truncated,
        }

    def user_payload(self) -> str:
        """Return canonical JSON exclusively for the untrusted user-input boundary."""

        return self._payload.decode("utf-8")


class SelectedEvidence(StrictFrozenModel):
    """Model-selected catalogue ID and semantic claim, never mechanical source data."""

    evidence_id: _EvidenceId
    supports: _TokenText


class SelectedStep(StrictFrozenModel):
    """An ordered semantic instruction with at least one selected evidence ID."""

    instruction: _BoundedText
    evidence: Annotated[tuple[SelectedEvidence, ...], Field(min_length=1, max_length=64)]


class SelectedWorkflow(StrictFrozenModel):
    """Legacy workflow semantic bounds with source copying removed from the model."""

    title: _ShortText
    goal: _BoundedText
    applicability: _TokenList
    non_goals: _TokenList
    preconditions: _TokenList
    inputs: _TokenList
    steps: Annotated[tuple[SelectedStep, ...], Field(min_length=1, max_length=64)]
    outputs: _TokenList
    failure_modes: _TokenList
    prohibited_actions: _TokenList
    required_approvals: _TokenList
    assumptions: _TokenList
    evidence: Annotated[tuple[SelectedEvidence, ...], Field(min_length=1, max_length=64)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]


class EvidenceSelectionResponse(StrictFrozenModel):
    """Strict local selection response, bounded identically to legacy extraction."""

    repository_summary: _BoundedText
    rejection_reason: _BoundedText | None
    workflows: Annotated[tuple[SelectedWorkflow, ...], Field(max_length=MAX_WORKFLOWS_PER_REPO)]


class EvidenceSelectionError(ValueError):
    """A closed reference failure carrying no rejected model text."""

    def __init__(self, code: _SelectionErrorCode) -> None:
        if code not in ("unknown_evidence_id", "step_evidence_not_declared"):
            raise ValueError("invalid evidence selection error code")
        self.code = code
        super().__init__(code)


def build_evidence_catalog(
    *,
    scope: Mapping[str, object],
    path: str,
    blob_sha: str,
    content_hash: str,
    text: str,
) -> EvidenceCatalog:
    """Select safe original-line slices without executing or rewriting source text."""

    try:
        if scope.get("readme_path") != path or sha256_digest(text.encode("utf-8")) != content_hash:
            raise ValueError
        # Validate trusted mechanical inputs even when no source text is eligible.
        EvidenceCatalogEntry(
            evidence_id="e0001",
            path=path,
            blob_sha=blob_sha,
            content_hash=content_hash,
            start=0,
            end=1,
            excerpt="x",
        )
        # Freeze nested caller-owned mappings through a canonical JSON snapshot.
        source_scope = json.loads(canonical_json_bytes(dict(scope)))
    except (ValueError, TypeError, AttributeError, ValidationError):
        raise ValueError("invalid evidence catalogue source") from None

    entries: list[EvidenceCatalogEntry] = []
    offset = 0
    fence_character: str | None = None
    fence_length = 0
    truncated = False
    for line in text.splitlines(keepends=True):
        start = offset
        offset += len(line)
        fence = _Fence.match(line)
        if fence_character is not None:
            if (
                fence is not None
                and fence.group(1)[0] == fence_character
                and len(fence.group(1)) >= fence_length
                and not fence.group(2).strip()
            ):
                fence_character = None
            continue
        if fence is not None:
            fence_character = fence.group(1)[0]
            fence_length = len(fence.group(1))
            continue
        # Whole-line filtering MUST precede segmentation: slicing cannot wash a pattern.
        if not line.strip() or find_forbidden_text(line):
            continue
        for position in range(0, len(line), MAX_EVIDENCE_EXCERPT_CHARS):
            excerpt = line[position : position + MAX_EVIDENCE_EXCERPT_CHARS]
            if not excerpt.strip() or find_forbidden_text(excerpt):
                continue
            if len(entries) == MAX_EVIDENCE_CATALOG_ENTRIES:
                truncated = True
                break
            entries.append(
                EvidenceCatalogEntry(
                    evidence_id=f"e{len(entries) + 1:04d}",
                    path=path,
                    blob_sha=blob_sha,
                    content_hash=content_hash,
                    start=start + position,
                    end=start + position + len(excerpt),
                    excerpt=excerpt,
                )
            )
        if truncated:
            break
    payload = canonical_json_bytes(
        {
            "scope": source_scope,
            "policy_version": EVIDENCE_CATALOG_POLICY_VERSION,
            "source": {"path": path, "blob_sha": blob_sha, "content_hash": content_hash},
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "truncated": truncated,
        }
    )
    return EvidenceCatalog(tuple(entries), sha256_digest(payload), truncated, payload)


def materialize_workflow(workflow: SelectedWorkflow, catalog: EvidenceCatalog) -> ExtractorWorkflow:
    """Resolve IDs in this catalogue only, preserving all semantic model fields."""

    entries = {entry.evidence_id: entry for entry in catalog.entries}
    declared = {evidence.evidence_id for evidence in workflow.evidence}

    def resolve(selected: SelectedEvidence) -> EvidenceRef:
        entry = entries.get(selected.evidence_id)
        if entry is None:
            raise EvidenceSelectionError("unknown_evidence_id")
        return EvidenceRef(
            path=entry.path,
            blob_sha=entry.blob_sha,
            excerpt=entry.excerpt,
            supports=selected.supports,
        )

    evidence = tuple(resolve(selected) for selected in workflow.evidence)
    steps: list[WorkflowStep] = []
    for step in workflow.steps:
        step_evidence = tuple(resolve(selected) for selected in step.evidence)
        if any(selected.evidence_id not in declared for selected in step.evidence):
            raise EvidenceSelectionError("step_evidence_not_declared")
        steps.append(WorkflowStep(instruction=step.instruction, evidence=step_evidence))
    return ExtractorWorkflow.model_validate(
        {
            **workflow.model_dump(exclude={"evidence", "steps"}),
            "evidence": evidence,
            "steps": tuple(steps),
        }
    )
