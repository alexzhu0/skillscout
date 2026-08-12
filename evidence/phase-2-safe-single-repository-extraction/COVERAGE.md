# Phase 2 — External API Coverage Matrix

**Produced:** 2026-07-21 (plan-phase deterministic detector: `detected=true`, signal `rest` in Phase 2 scope)
**Scope:** every external API capability surface touched by Phase 2 plans 02-01..02-04. INTEGRATE is the default; every OPT-OUT carries its reason.

## GitHub REST API

Consumed only through `src/skillscout/adapters/github.py` (`GitHubReadClient`, `EffectScope.REMOTE_READ`) behind a fixed `https://api.github.com` base, templated closed endpoints and pinned `X-GitHub-Api-Version: 2022-11-28`.

| Capability | Endpoint / surface | Decision | Reason |
|---|---|---|---|
| Repository metadata | `GET /repos/{owner}/{repo}` | INTEGRATE | FILT-01 observed values, numeric repo id, default branch, `license.spdx_id` (Plan 02-02). |
| Commit resolution (pin) | `GET /repos/{owner}/{repo}/commits/{ref}` | INTEGRATE | READ-01: ref → exact 40-hex commit SHA before any content read (Plan 02-02). |
| Git tree (recursive snapshot) | `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1` | INTEGRATE | Scout snapshot: paths, modes (submodule/symlink), sizes for size-before-fetch (Plan 02-02). |
| License confirmation | `GET /repos/{owner}/{repo}/license?ref={sha}` | INTEGRATE | FILT-02: the one Filter-owned GET; 404/NOASSERTION/mismatch are deterministic rejections (Plan 02-02). |
| Git blob content | `GET /repos/{owner}/{repo}/git/blobs/{blob_sha}` | INTEGRATE | Reader bounded content fetch, pre-sized by tree metadata (Plans 02-02/02-03). |
| Rate-limit headers | `x-ratelimit-limit/remaining/reset` | INTEGRATE | Parsed into Scout payload for audit; 403-with-remaining-0 maps to transient (Plan 02-02). |
| Redirects (renames) | 301/307/308 same-host | INTEGRATE | Followed once, recorded; identity stays the numeric repo id; cross-host fails closed (Plan 02-02). |
| Retry-After signaling | `Retry-After` header on 429/limited 403 | INTEGRATE | Bounded sleeper (≤60 s) before the existing RetryPolicy's next attempt (Plan 02-02). |
| Search API | `GET /search/repositories` | OPT-OUT | Phase 5 discovery scope; Phase 2 input is one manually specified repository. |
| Contents API | `GET /repos/{owner}/{repo}/contents/{path}` | OPT-OUT | Trees+blobs already give mode/size pre-visibility; Contents adds no needed capability. |
| Conditional requests | ETag / If-None-Match (304) | OPT-OUT | Pinned-SHA content is immutable; caching matters only at Phase 5's 100-candidate scale. |
| GraphQL API | `/graphql` | OPT-OUT | The five needed calls have stable REST forms; one transport discipline keeps the adapter closed. |
| GitHub App installation tokens | `POST /app/installations/{id}/access_tokens` | OPT-OUT | Phase 4 publishing identity; Phase 2 reads are unauthenticated or minimal read-only token. |
| Write endpoints | refs/contents PUT, PRs, merges, reviews | OPT-OUT | REMOTE_WRITE is rejected everywhere until Phase 4; the capability is structurally absent. |
| Releases / assets download | `GET /repos/{owner}/{repo}/releases*` | OPT-OUT | READ-06 forbids artifact download; supply-chain execution boundary. |
| Archive (zipball/tarball) | `GET /repos/{owner}/{repo}/zipball` | OPT-OUT | Equivalent of cloning; forbidden by READ-06 and the no-archive allowlist rule. |
| Webhooks / Events | `/repos/{owner}/{repo}/hooks`, `/events` | OPT-OUT | No push-driven flows in v1; runs are schedule/manual CLI invocations. |
| Actions API | `/repos/{owner}/{repo}/actions/*` | OPT-OUT | Candidate CI introspection is out of scope and untrusted. |
| Commit compare / diffs | `GET /repos/{owner}/{repo}/compare/{base}...{head}` | OPT-OUT | Source-change re-evaluation is a fresh pinned run, not diff consumption (Phase 5 concern). |

## OpenAI API

Consumed only through `src/skillscout/adapters/openai_extract.py` (`OpenAIExtractionClient`, `EffectScope.REMOTE_READ`) with one `responses.parse` call per extraction attempt.

| Capability | Surface | Decision | Reason |
|---|---|---|---|
| Structured extraction | `responses.parse` + `text_format=ExtractorResponse` | INTEGRATE | EXTR-01: strict Structured Outputs generated from the Pydantic model (Plan 02-04). |
| Stateless data control | `store=false` | INTEGRATE | SEC-01: no application-side retention of repository content (Plan 02-04). |
| Usage telemetry | `response.usage` (input/output/total tokens) | INTEGRATE | OPS-01 attempt ledger token accounting (Plan 02-04). |
| Response identity | `response.id`, actual `response.model` | INTEGRATE | Audit identity; actual-model recording guards alias drift (Plan 02-04). |
| Output budget | `max_output_tokens` (8,000) | INTEGRATE | Structural cost bound beside the one-call-per-attempt discipline (Plan 02-04). |
| Tool calling | `tools` / function calling | OPT-OUT | SEC-01 forbids tools; the request never carries a `tools` key (tested contract). |
| Hosted tools | web search, code interpreter, computer use, MCP | OPT-OUT | SEC-01 forbids any remote action capability inside the model call. |
| Streaming | `stream=true` | OPT-OUT | One deterministic response simplifies outcome mapping and telemetry; no UX need. |
| Conversation state | `previous_response_id`, conversation objects | OPT-OUT | Requests are stateless; Phase 2 never chains model turns. |
| Embeddings | `/embeddings` | OPT-OUT | v2 FUT-02 semantic dedup; no vector need in MVP. |
| Batch API | `/batches` | OPT-OUT | One call per run; batching is a Phase 5 scale decision. |
| Files / Assistants / vector stores | `/files`, `/assistants`, `/vector_stores` | OPT-OUT | Stateful surfaces conflict with `store=false` minimization and stage isolation. |
| Fine-tuning | `/fine_tuning` | OPT-OUT | Out of MVP scope; configured base model only. |
| Zero Data Retention enrollment | org-level ZDR | OPT-OUT | Operations decision deferred per 02-RESEARCH.md; `store=false` is the Phase 2 control. |
| Other modalities | images, audio, realtime | OPT-OUT | Extraction is text-only over bounded repository text. |

## Notes

- The entire suite runs credential-free over `httpx.MockTransport`; no VCR library is used and no live network occurs in pytest. A live smoke run is manual-only (see 02-VALIDATION.md §Manual-Only Verifications).
- Every INTEGRATE row maps to a concrete plan task in 02-VALIDATION.md §Per-Task Verification Map; no detector-surfaced capability is unplanned.
