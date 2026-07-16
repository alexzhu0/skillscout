# Project State: SkillScout

**Last updated:** 2026-07-16  
**Milestone:** v1 — Safe discovery-to-Draft-PR MVP  
**Status:** Phase 1 planned and independently verified; ready for execution

## Current Position

**Phase:** 1 of 6 — Auditable Dry-Run Spine  
**Plan:** 4 plans across 4 sequential waves
**Execution:** Not started  
**Next command:** `$gsd-execute-phase 1`

## Progress

```text
Project initialization  [██████████] 100%
MVP requirements        [██████████] 100%
Roadmap approval        [██████████] 100%
Implementation          [░░░░░░░░░░]   0%
```

| Metric | Value |
|---|---:|
| MVP requirements | 44 |
| Requirements mapped | 44 |
| Roadmap phases | 6 |
| Phases completed | 0 |
| Plans completed | 0 |

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

None. Phase 1 execution begins with two mandatory, non-auto-approvable supply-chain checkpoints before any project dependency is built, installed, imported, or tested.

## Session Continuity

### Completed

- Initialized Git repository and GSD project configuration.
- Created and committed `PROJECT.md`.
- Researched stack, features, architecture, risks, Agent Skills specification, GitHub and OpenAI safety constraints.
- Created and committed all research documents.
- Confirmed and committed 44 MVP requirements.
- Drafted a six-phase vertical MVP roadmap and mapped every requirement exactly once.
- Skipped Phase 1 discussion by explicit user request and completed research, Nyquist validation, pattern mapping, Walking Skeleton design, and four executable plans.
- Passed two bounded plan-checker revision rounds; the final independent review returned `VERIFICATION PASSED` with no blockers or warnings.

### Next

1. Execute Phase 1 with `$gsd-execute-phase 1`.
2. Stop at Gate A for exact toolchain/direct-declaration approval, then at Gate B for complete lock-graph approval.
3. Continue through the Walking Skeleton, auditable resume ledger, and fail-closed zero-network acceptance waves.

---
*State initialized: 2026-07-16*
