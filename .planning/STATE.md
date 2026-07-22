---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 02
current_phase_name: safe-single-repository-extraction
status: executing
stopped_at: Completed 02-01-PLAN.md
last_updated: "2026-07-22T03:27:04.017Z"
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 22
  completed_plans: 19
---

# Project State: SkillScout

**Last updated:** 2026-07-20
**Milestone:** v1 — Safe discovery-to-Draft-PR MVP  
**Status:** Ready to execute

## Current Position

**Phase:** 02 (safe-single-repository-extraction) — EXECUTING
**Plan:** 2 of 4
**Verification:** Phase 1 passed — 5 of 5 must-haves verified; UAT 6/6 countersigned; security audit 83/83 threats closed
**Next command:** `/gsd:discuss-phase 2`

## Progress

```text
Project initialization  [██████████] 100%
MVP requirements        [██████████] 100%
Roadmap approval        [██████████] 100%
Phase 1 implementation  [██████████] 100%
Phase 1 verification    [██████████] 100%
```

| Metric | Value |
|---|---:|
| MVP requirements | 44 |
| Requirements mapped | 44 |
| Roadmap phases | 6 |
| Phases completed | 1 |
| Plans completed | 18/18 |

## Accumulated Context

### Product Decisions

- SkillScout discovers reusable AI workflows in public GitHub repositories and publishes only human-reviewable Draft PRs to a controlled Skill catalog.
- Discovery runs daily and manually, with hard per-run budgets of 100 candidates and 20 LLM analyses.
- All external repository content is untrusted; no candidate code is cloned, installed, imported, built, or executed.
- Reader order is README → docs → examples → package manifests → limited source, with explicit budgets and early stop.
- `WorkflowSpec` is the only semantic boundary allowed to cross from raw repository content into generation, review, and publishing.
- v1 generates documentation-only Agent Skills and forbids `scripts/`.
- Only MIT, Apache-2.0, BSD-2-Clause, and BSD-3-Clause are accepted automatically.
- Independent Reviewer only judges; it never edits or rewrites the Skill.
- Publisher can create/update branches and Draft PRs but cannot merge, approve, mark ready, modify rulesets, or write the default branch.
- Human review and merge are required for every generated Skill.

### Architecture Decisions

- Python 3.13 modular monolith with typed stage contracts and provider adapters.
- GitHub REST API via HTTPX; OpenAI Responses API with strict Structured Outputs and Pydantic.
- SQLite is operational query state; versioned JSON manifests are auditable/rebuildable facts.
- MVP persists state on a dedicated `skillscout-state` branch because GitHub-hosted runners are ephemeral; cache/artifact are not canonical state.
- Production schedule/manual runs share one non-cancelling concurrency group.
- Cross-repository publishing uses a least-privilege short-lived GitHub App installation token and protected catalog ruleset.
- The roadmap uses vertical slices: dry-run spine → single-repo extraction → validated Skill → Draft PR → automated discovery → adversarial acceptance.

### Scope Boundaries

- No automatic merge, code execution, unauthorized secrets, private repositories, vector database, multi-tenancy, Web admin, self-modification, public marketplace publishing, or generated scripts in v1.
- No fixed “8-Agent” deployment requirement; stage contracts, not agent count, define the architecture.

## Open Decisions

No product-scope blocker remains. Phase planning will choose implementation-level details such as:

- Concrete GitHub Search query set and organization-level Reader budget ceilings.
- Target controlled catalog repository and human reviewer/team identifiers for live canary.
- Qualification scoring weights, excerpt limit, similarity threshold, and policy versioning process.
- Exact OpenAI model snapshot after fixture evaluation.

These decisions must preserve the approved requirements and may not broaden remote permissions or execution authority.

## Blockers

None. Phase 1 closed all historical blockers: Plans 01-12 through 01-15 fixed snapshot truthfulness, event-derived reuse authority, closed CLI diagnostics, and finite no-replay recovery; Plan 01-17 wired owner-validated stale-temp crash recovery into state, manifest, and publication writes with a killed-writer regression; Plan 01-18 bound both reviewed JSON fixtures into the evidence authority. Independent re-review closed CR-01/WR-01, goal re-verification passed 5/5, UAT countersigned 6/6, and the security audit closed 83/83 register rows. Two Info-level code-quality known issues (IN-01 dead alias, IN-02 lock-helper duplication) are documented in 01-REVIEW.md and bound in evidence. The OS/syscall network-denial item remains explicitly deferred to Phase 6.

## Session Continuity

**Last session:** 2026-07-22T03:27:04.012Z
**Stopped at:** Completed 02-01-PLAN.md
**Resume file:** None

### Next

1. Discuss and plan Phase 2 — Safe Single-Repository Extraction (`/gsd:discuss-phase 2`).
2. Optional cleanup: IN-01/IN-02 Info findings via `/gsd:code-review 01 --fix` (requires evidence re-record afterward).

---
*State initialized: 2026-07-16*

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 01 P01 | 9 min | 3 tasks | 8 files |
| Phase 01 P02 | 15 min | 2 tasks | 9 files |
| Phase 01 P03 | 21 min | 3 tasks | 11 files |
| Phase 01 P04 | 21 min | 3 tasks | 11 files |
| Phase 01 P05 | 9min | 2 tasks | 5 files |
| Phase 01 P06 | 16min | 2 tasks | 6 files |
| Phase 01 P07 | 20min | 2 tasks | 5 files |
| Phase 01 P08 | 19min | 2 tasks | 9 files |
| Phase 01 P09 | 24min | 2 tasks | 5 files |
| Phase 01 P10 | 19min | 2 tasks | 7 files |
| Phase 01 P11 | 15min | 2 tasks | 3 files |
| Phase 01 P12 | 14min | 2 tasks | 5 files |
| Phase 01 P13 | 20min | 2 tasks | 8 files |
| Phase 01-auditable-dry-run-spine P14 | 13 min | 2 tasks | 4 files |
| Phase 01-auditable-dry-run-spine P15 | 9 min | 2 tasks | 5 files |
| Phase 01-auditable-dry-run-spine P16 | 16min | 2 tasks | 4 files |
| Phase 01-auditable-dry-run-spine P17 | 35min | 2 tasks | 6 files |
| Phase 01-auditable-dry-run-spine P18 | 19min | 2 tasks | 4 files |
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 02 P01 | 17 min | 4 tasks | 15 files |

## Decisions

- [Phase 01]: Approve exact Gate B lock bytes as execution authority — Any byte change to uv.lock invalidates the human-reviewed dependency graph.
- [Phase 01]: Keep Wave 1 static and uninstalled — Locked project code begins execution only in Plan 02 after both supply-chain gates.
- [Phase 01]: Load and strictly validate the bounded fixture before opening SQLite, so rejected input cannot create state. — Keep rejected untrusted input outside every durable run surface.
- [Phase 01]: Persist the five-field reusable identity on a running attempt before processor invocation. — Make migration, retry accounting and interruption evidence reconstructible from durable facts.
- [Phase 01]: Expose only four closed schema-v1 error codes and fixed ASCII summaries. — Prevent raw fixture, Pydantic, exception, credential and path disclosure.
- [Phase 01]: Validate current canonical identity before checkpoint reuse — Input, producer, or retry-policy mismatch starts a new run and preserves the interrupted audit record.
- [Phase 01]: Scope retry budget to persisted reusable_key_digest — Three transient or abandoned attempts exhaust one identity; permanent failures never receive a second invocation.
- [Phase 01]: Validate the complete immutable effect-scoped registry before constructing the dry-run runner — Remote authority is absent structurally, not hidden behind a flag.
- [Phase 01]: Persist only closed relative manifest locators — Filesystem roots derive from the configured state DB and operator paths never enter evidence.
- [Phase 01]: Keep every external diagnostic on a closed code and fixed bounded ASCII summary — Raw exceptions, payloads, credentials and paths never cross into durable or CLI surfaces.
- [Phase 01]: Derive registration authority only from adapter-owned effect declarations — Remove the parallel caller label that enabled capability misrepresentation.
- [Phase 01]: Seal build_dry_run_runtime to PHASE_ONE_MAX_SCOPES — Production construction has no policy or arbitrary-registration widening input.
- [Phase 01]: Keep PipelineRunner injectable while production composition requires supported concrete adapters — Deterministic tests retain protocol seams without widening the production authority boundary.
- [Phase 01]: Use one immutable producer/schema registry at runtime, migration, manifest write and manifest read boundaries. — Prevent successful evidence that the reader later rejects.
- [Phase 01]: Validate StagePayload and bound exact canonical manifest bytes before filesystem activity. — Keep untrusted outputs JSON-only, deterministic and resource bounded.
- [Phase 01]: Close known post-start failures immediately and reconcile indeterminate orphan attempts on next open. — Keep durable lifecycle evidence truthful after failures.
- [Phase 01]: Never give SQLite an operator pathname — Deserialize bounded descriptor-read bytes into private in-memory connections and serialize candidate snapshots only.
- [Phase 01]: Use a retained reusable lock inode with kernel-only flock ownership — Process death releases live ownership without lock-file deletion or recreation.
- [Phase 01]: Make every required local fsync fatal before state promotion — Manifest and publication bytes must be durable before checkpoint or terminal success.
- [Phase 01]: Separate semantic result identity from run-scoped row ownership — Stable semantic digests may repeat across runs, while deterministic result_row_id owns stage and checkpoint associations.
- [Phase 01]: Select resumable runs by complete exact RunIdentity — Schema, subject, fixture, producer, and retry-policy facts must all match before checkpoint reuse.
- [Phase 01]: Keep migrated v1 runs legacy_unbound until transactional canonical proof — Unbound evidence cannot authorize inspect or resume, and a wrong expected identity must leave state unchanged.
- [Phase 01]: Use one immutable schema-v2 descriptor set for creation, acceptance, and migration — A user_version value cannot establish structural or integrity compatibility.
- [Phase 01]: Treat persisted diagnostics as untrusted until exact closed validation — Public inspect output must never project corrupt, legacy, credential-bearing, or provider-controlled fields.
- [Phase 01]: Validate schema-v1 source rows before migration copy or manifest creation — Rejected legacy bytes stay unchanged evidence and cannot become new durable surfaces.
- [Phase 01]: Return VerifiedRunChain only for bound identity — Legacy-unbound evidence cannot authorize resume or full inspect before exact current identity proof.
- [Phase 01]: Keep legacy migration validation non-authorizing — The frozen v1 ledger lacks fixture_hash, so only reconstructible facts are validated before binding.
- [Phase 01]: Use one full-chain verifier for every bound trust path — Resume, latest checkpoint, completed verification, and inspect must reject identical corruption consistently.
- [Phase 01]: Preserve the historical schema-v1 semantic result preimage — Migrated and newly completed v1 stages must remain one canonical chain.
- [Phase 01]: Keep generated evidence outside standard pytest — Acyclic validation requires product and quality results to exist before the evidence document, followed by one standalone validation pass.
- [Phase 01]: Keep WR-04 deferred to Phase 6 — OS/syscall network denial is adversarial acceptance work and is not falsely claimed as a Phase-1 fix.
- [Phase 01]: Use the target directory fsync as the snapshot authority commit point — Post-commit backup retirement cannot truthfully report rollback
- [Phase 01]: Use one private regular-file predicate for state, manifest, and lock evidence — Every local evidence reader must enforce the same ownership, link, type, and mode boundary
- [Phase 01]: Reject equal state and derived manifest namespaces before filesystem creation — Operator-selected leaves cannot alias internal evidence directories
- [Phase 01]: Represent every invocation boundary as a content-addressed event; genesis alone is ordinal zero and every reopened run appends a later event.
- [Phase 01]: Treat the resume-event ledger as reuse authority and keep runs.reused_stage_count only as an atomically maintained projection of the current event head.
- [Phase 01]: Migrate pre-event runs only when historical reuse is absent or zero; reject nonzero schema-v2 claims because no independent event can attest them.
- [Phase 01]: Commit each resume event, run head, count, running status, and timestamp in one candidate snapshot before stale-attempt reconciliation or processor work.
- [Phase 01]: Make the final verified ResumeEvent the sole reuse-count authority — Mutable run count and head are accepted only as exact duplicates of the complete event proof.
- [Phase 01]: Verify migrated bound schema-v2 runs after conservative genesis installation — The exact schema-v3 candidate can use the same event-aware canonical verifier without inventing prior invocations.
- [Phase 01]: Route authoritative run reads through verify_run_chain — Every public reuse projection must reject the same tamper; no row-only public audit path remains.
- [Phase 01]: Discard every argparse-generated failure detail inside SafeArgumentParser — One fixed status-2 JSON diagnostic keeps rejected argv outside all output and durable surfaces.
- [Phase 01]: Treat sanitized pipeline interruptions as transient under the existing finite ceiling — Unexpected processor exceptions can recover without making explicit permanent failures retryable or widening the three-attempt budget.
- [Phase 01]: Keep the verified resume-event ledger as the sole retry prefix authority — Recovery starts at the failed stage and never replays already verified successful prefix effects.
- [Phase 01]: Keep evidence documents and verifier outcomes outside the authority they report — Eliminates self-hash and self-success cycles while exact source and fresh output remain independently checkable.
- [Phase 01]: Normalize only exact temporary roots and elapsed durations after the fixed timing marker — Makes reruns reproducible without removing failures, counts, node names, exit status, or arbitrary output.
- [Phase 01]: Recover crash-left deterministic temps only under the corresponding retained lock after the private regular-file predicate passes — Rejected temps are retained and the operation fails closed on sanitized codes.
- [Phase 01]: Serialize publication writers on a retained kernel-flock inode that is never deleted — A live lock holder makes concurrent publication writes fail closed with state_operation_failed.
- [Phase 01]: Bind both reviewed JSON fixtures as explicit literal paths in the closed evidence source set — Semantically neutral fixture byte changes now stale recorded evidence before command credit.
- [Phase 01]: Credit exactly the current review's CR-01/WR-01 findings through digest-bound nodes — The superseded seven-finding map survives only under the past-tense prior-review label.
- [Phase 02]: Admit exactly httpx==0.28.1 and openai==2.46.0 through the two-gate ceremony with no tiktoken, GitHub SDK, tenacity, or VCR library — Supply-chain inputs require separate declaration (Gate A2) and exact-lock-bytes (Gate B2) human approvals; Gate B2 binds all execution to uv.lock SHA-256 a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216
- [Phase 02]: Re-anchor the Phase 1 evidence verifier LOCK_HASH to the Gate-B2-approved uv.lock bytes — The verifier authority constant must track the human-approved graph; recorded Phase 1 evidence stales by design and awaits Phase 2 re-baselining
