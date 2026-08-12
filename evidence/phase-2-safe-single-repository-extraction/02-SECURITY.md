---
phase: 02
slug: safe-single-repository-extraction
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-22
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Package registry → approved lock → runtime | Only the human-approved, hash-bound dependency graph may execute. | Package metadata, artifacts, lock bytes |
| Subject descriptor → run authority | A hostile local descriptor must fail closed before state or network activity. | Repository identity, URL, ref |
| GitHub REST → Scout/Reader | Remote metadata, paths, and bytes remain adversary-controlled and bounded. | Repository metadata, tree entries, text blobs |
| Credentials → remote adapters | GitHub and OpenAI credentials are environment-injected and header-only. | Secrets, authorization headers |
| Phase profile → capability ceiling | Phase 2 may read remotely but may never gain remote-write authority. | Adapter registrations, side-effect scopes |
| Raw repository text → LLM request | Untrusted text remains inert user-role data in one tool-less request. | Bounded repository excerpts |
| Model output → WorkflowSpec | Model output is untrusted until deterministic evidence and identity validation succeeds. | Structured extraction response, evidence references |
| In-memory read bundle → durable state | Full repository text must not cross into manifests, SQLite, logs, stdout, or summaries. | Content hashes, blob SHAs, bounded excerpts |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01-SC | Tampering / Spoofing | httpx/openai supply chain | high | mitigate | Separate Gate A2/B2 approvals; exact pinned dependency set and approved `uv.lock` SHA-256 recorded in `02-01-SUMMARY.md`; lock integrity and 618-test suite verified in `02-VERIFICATION.md`. | closed |
| T-02-01-IN | Tampering | Subject input file | high | mitigate | Bounded single-descriptor read, strict frozen schema, identity/URL cross-check, ref denylist, and non-echoing `INVALID_SUBJECT`; covered by subject and CLI security tests. | closed |
| T-02-01-CT | Tampering / Elevation of Privilege | Phase 1 contracts and capability surface | high | mitigate | Additive-only vocabulary changes, closed capability sweep, sanctioned Phase 1 amendments, full regression suite green; human-confirmed in `02-UAT.md`. | closed |
| T-02-01-LIC | Information Disclosure (legal/attribution) | License determination | medium | mitigate | Exact permissive SPDX allowlist; missing, ambiguous, multiple, conflicting, or mismatched licenses fail deterministically before any LLM call. | closed |
| T-02-02-CR | Information Disclosure | GitHub credential handling | high | mitigate | Token read once at adapter construction and used only in Authorization header; canary sweeps cover requests and durable surfaces. | closed |
| T-02-02-SS | Tampering / SSRF | Request URLs and redirects | high | mitigate | Fixed `api.github.com` base, closed templated endpoints, no response-derived URLs, redirects disabled except recorded same-host handling, numeric repository identity. | closed |
| T-02-02-EOP | Elevation of Privilege | Phase 2 registry and policy ceiling | critical | mitigate | Closed composition root with concrete-type checks; `SideEffectPolicy.phase_two()` admits only NONE, LOCAL_STATE, and REMOTE_READ; REMOTE_WRITE rejected before invocation. | closed |
| T-02-02-DOS | Denial of Service | Rate limits and oversized responses | medium | mitigate | Serial client, endpoint byte caps, bounded Retry-After, and transient retry mapping limited to rate-limit/5xx/timeout infrastructure failures. | closed |
| T-02-02-ID | Tampering | Stage identity and telemetry | medium | mitigate | Profile spine guard, global stage indices, telemetry persisted before completion and included in output identity, completed chain verified before reuse. | closed |
| T-02-03-PT | Tampering | Repository paths | high | mitigate | Closed path predicate rejects traversal, separators, control/framing bytes, and records `PATH_VIOLATION`; rejected paths are never fetched. | closed |
| T-02-03-DOS | Denial of Service | Oversized or excessive files | high | mitigate | Size-before-fetch, five immutable budgets with boundary tests, endpoint caps, and explicit early-stop reasons. | closed |
| T-02-03-SM | Tampering | Binary/LFS/submodule/symlink smuggling | high | mitigate | Mode, extension, binary, and LFS rejection matrix with never-fetched or exactly-once fetch assertions. | closed |
| T-02-03-EX | Elevation of Privilege | Candidate code execution | critical | mitigate | Execution capability omitted; source sweep bans subprocess/importlib/socket/eval/exec/compile and runtime tests permit only recorded HTTP transports. | closed |
| T-02-03-ID | Information Disclosure | Raw bundle persistence | high | mitigate | Raw text exists only in process scratch; durable payloads contain bounded metadata, hashes, and excerpts; full-text canary sweeps pass. | closed |
| T-02-04-PI | Tampering / Elevation of Privilege | Prompt injection | critical | mitigate | Versioned developer-only instructions, repository text only in delimited user-role data, no tools, `store=false`, seven-class injection corpus, deterministic post-validation. | closed |
| T-02-04-SX | Information Disclosure | Secret exfiltration | high | mitigate | Header-only credentials, minimized request body, `store=false`, and canary sweeps across bodies, manifests, SQLite, stdout, and summaries. | closed |
| T-02-04-CM | Tampering / Spoofing | Compromised model output | high | mitigate | Verbatim evidence, recorded blob SHA/content-hash checks, forbidden intent patterns, SkillScout-owned fingerprints/IDs, and fail-closed all-dropped outcome. | closed |
| T-02-04-COST | Denial of Service | Runaway LLM/API cost | medium | mitigate | One request per extraction attempt, SDK retries disabled, bounded output tokens, maximum three workflows, zero-call skip cascades, transient-only pipeline retry budget. | closed |
| T-02-04-LK | Information Disclosure | Raw repository text crossing downstream | high | mitigate | `WorkflowSpec` is the sole semantic carrier; only bounded evidence excerpts leave memory; full-text canary durable-surface tests pass. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` count toward `threats_open`.*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party).*

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-22 | 19 | 19 | 0 | Codex (`gsd-secure-phase`, ASVS L1) |

Evidence baseline: `02-VERIFICATION.md` (14/14 truths, 618 tests), `02-UAT.md` (15/15 human confirmations), Plan 02-01 through 02-04 threat registers, and their execution summaries. No additional threats were scanned because the register was authored at plan time and ASVS L1 requires mitigation verification only.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-22
