"""Frozen extractor-response and workflow-spec contracts with boundary validation."""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Literal, Mapping

from pydantic import Field

from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel

EXTRACT_PROMPT_VERSION = "extract-prompt-v1"
FINGERPRINT_VERSION = "wf-fingerprint-v1"
WORKFLOW_SPEC_SCHEMA_VERSION = "workflow-spec-v1"
MAX_WORKFLOWS_PER_REPO = 3
MAX_EVIDENCE_EXCERPT_CHARS = 280

_ShortText = Annotated[str, Field(min_length=1, max_length=280)]
_BoundedText = Annotated[str, Field(min_length=1, max_length=4096)]
_TokenText = Annotated[str, Field(min_length=1, max_length=1024)]
_EvidencePath = Annotated[str, Field(min_length=1, max_length=512)]
_BlobSha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
_Excerpt = Annotated[str, Field(min_length=1, max_length=MAX_EVIDENCE_EXCERPT_CHARS)]
_TokenList = Annotated[tuple[_TokenText, ...], Field(max_length=64)]


class EvidenceRef(StrictFrozenModel):
    """One model-claimed verbatim excerpt locating a claim inside a fetched blob."""

    path: _EvidencePath
    blob_sha: _BlobSha
    excerpt: _Excerpt
    supports: _TokenText


class WorkflowStep(StrictFrozenModel):
    """One ordered model-claimed instruction with its supporting evidence."""

    instruction: _BoundedText
    evidence: Annotated[tuple[EvidenceRef, ...], Field(min_length=1, max_length=64)]


class ExtractorWorkflow(StrictFrozenModel):
    """The complete model-claimed workflow shape before boundary validation."""

    title: _ShortText
    goal: _BoundedText
    applicability: _TokenList
    non_goals: _TokenList
    preconditions: _TokenList
    inputs: _TokenList
    steps: Annotated[tuple[WorkflowStep, ...], Field(min_length=1, max_length=64)]
    outputs: _TokenList
    failure_modes: _TokenList
    prohibited_actions: _TokenList
    required_approvals: _TokenList
    assumptions: _TokenList
    evidence: Annotated[tuple[EvidenceRef, ...], Field(min_length=1, max_length=64)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]


class ExtractorResponse(StrictFrozenModel):
    """The complete structured extraction result returned by the model."""

    repository_summary: _BoundedText
    rejection_reason: _BoundedText | None
    workflows: Annotated[
        tuple[ExtractorWorkflow, ...], Field(max_length=MAX_WORKFLOWS_PER_REPO)
    ]


class WorkflowEvidence(StrictFrozenModel):
    """One persisted evidence reference bound to its recorded content hash."""

    path: _EvidencePath
    blob_sha: _BlobSha
    content_hash: Digest
    excerpt: _Excerpt
    supports: _TokenText


class WorkflowSpecStep(StrictFrozenModel):
    """One persisted ordered instruction bound to hashed evidence."""

    instruction: _BoundedText
    evidence: Annotated[tuple[WorkflowEvidence, ...], Field(min_length=1, max_length=64)]


class WorkflowSpec(StrictFrozenModel):
    """The persisted semantic boundary artifact built from a validated workflow."""

    schema_version: Literal["workflow-spec-v1"]
    workflow_id: Annotated[str, Field(min_length=1, max_length=128)]
    fingerprint: Digest
    fingerprint_version: Literal["wf-fingerprint-v1"]
    title: _ShortText
    goal: _BoundedText
    applicability: _TokenList
    non_goals: _TokenList
    preconditions: _TokenList
    inputs: _TokenList
    steps: Annotated[tuple[WorkflowSpecStep, ...], Field(min_length=1, max_length=64)]
    outputs: _TokenList
    failure_modes: _TokenList
    prohibited_actions: _TokenList
    required_approvals: _TokenList
    assumptions: _TokenList
    evidence: Annotated[tuple[WorkflowEvidence, ...], Field(min_length=1, max_length=64)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]


def normalize_for_fingerprint(text: str) -> str:
    """Normalize compatibility form, case, punctuation, and whitespace for hashing."""

    normalized = unicodedata.normalize("NFKC", text).casefold()
    without_punctuation = "".join(
        char for char in normalized if not unicodedata.category(char).startswith("P")
    )
    return " ".join(without_punctuation.split())


def workflow_fingerprint(*, repo_id: str, goal: str, steps: tuple[str, ...]) -> str:
    """Hash the versioned preimage of repo id, normalized goal, and ordered steps."""

    return sha256_digest(
        {
            "fingerprint_version": FINGERPRINT_VERSION,
            "repo_id": repo_id,
            "goal": normalize_for_fingerprint(goal),
            "steps": [normalize_for_fingerprint(step) for step in steps],
        }
    )


FORBIDDEN_TEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", re.compile(r"https?://", re.IGNORECASE)),
    ("shell_curl_pipe", re.compile(r"\bcurl\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b")),
    ("shell_bash_c", re.compile(r"\b(?:ba|z)?sh\s+-c\b")),
    ("shell_sudo", re.compile(r"\bsudo\b")),
    ("secret_github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{8,}")),
    ("secret_ghp", re.compile(r"ghp_[A-Za-z0-9]{8,}")),
    ("secret_sk", re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")),
    ("secret_akia", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("pem_header", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
)

BOUNDARY_DROP_REASONS = (
    "unknown_evidence_path",
    "blob_sha_mismatch",
    "excerpt_over_length",
    "excerpt_not_verbatim",
    "forbidden_text",
)


def find_forbidden_text(text: str) -> tuple[str, ...]:
    """Return the closed names of every forbidden pattern present in one text."""

    return tuple(name for name, pattern in FORBIDDEN_TEXT_PATTERNS if pattern.search(text))


def validate_workflow_boundaries(
    workflow: ExtractorWorkflow,
    *,
    bundle_texts: Mapping[str, str],
    recorded: Mapping[str, str],
) -> tuple[str, ...]:
    """Return the closed drop reasons one candidate workflow violates, if any."""

    reasons: list[str] = []

    def note(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    def check_evidence(ref: EvidenceRef) -> None:
        expected_sha = recorded.get(ref.path)
        bundle_text = bundle_texts.get(ref.path)
        if expected_sha is None or bundle_text is None:
            note("unknown_evidence_path")
            return
        if ref.blob_sha != expected_sha:
            note("blob_sha_mismatch")
        if len(ref.excerpt) > MAX_EVIDENCE_EXCERPT_CHARS:
            note("excerpt_over_length")
        if ref.excerpt not in bundle_text:
            note("excerpt_not_verbatim")

    texts: list[str] = [workflow.title, workflow.goal]
    for field_values in (
        workflow.applicability,
        workflow.non_goals,
        workflow.preconditions,
        workflow.inputs,
        workflow.outputs,
        workflow.failure_modes,
        workflow.prohibited_actions,
        workflow.required_approvals,
        workflow.assumptions,
    ):
        texts.extend(field_values)

    for ref in workflow.evidence:
        check_evidence(ref)
        texts.extend((ref.path, ref.excerpt, ref.supports))
    for step in workflow.steps:
        texts.append(step.instruction)
        for ref in step.evidence:
            check_evidence(ref)
            texts.extend((ref.path, ref.excerpt, ref.supports))

    if any(find_forbidden_text(text) for text in texts):
        note("forbidden_text")

    return tuple(reasons)
