---
phase: 03-validated-skill-candidate
plan: "08"
subsystem: generation
tags: [openai-responses, structured-outputs, provenance, agent-skills, canonical-identity, durable-filesystem, tdd]

requires:
  - phase: 03-05
    provides: Complete WorkflowSpec authority, candidate execution authority, and lineage identity
  - phase: 03-07
    provides: Passing canonical QualificationReport authority
  - phase: 03-04
    provides: Gate B3 dependency equality preflight
provides:
  - Strict frozen semantic draft, generation authority, provenance, manifest, and two-layer identity contracts
  - One-call no-tools store-false OpenAI Generator adapter with bounded outcomes and telemetry
  - Deterministic docs-only Agent Skill renderer and descriptor-anchored durable package materializer
affects: [03-09, 03-10, 03-11, 03-12, phase3-ledger, reviewer, draft-pr-publisher]

tech-stack:
  added: []
  patterns:
    - Semantic artifact identity is finalized from canonical draft plus generation-only authority before rendering
    - Exact rendered path/hash/mode/size facts form a separate package identity after provenance bytes are final
    - OpenAI Responses adapters perform exactly one strict no-tools request with SDK retries disabled
    - Package replacement uses retained flock authority, descriptor-relative staging, fsync, atomic rename, and rollback

key-files:
  created:
    - src/skillscout/domain/skill_artifacts.py
    - src/skillscout/adapters/openai_generate.py
    - tests/test_skill_generation.py
    - tests/test_openai_generate.py
    - tests/fixtures/openai/generator/cases.json
  modified:
    - tests/recorded_transport.py
    - tests/test_phase1_gap_closure.py

key-decisions:
  - "Keep GeneratedArtifactIdentityV1 independent from request telemetry and rendered layout; derive PackageIdentityV1 only after complete provenance bytes and the exact rendered manifest are frozen."
  - "Admit only a strict verified GenerationRequestV1 to the Generator and make one responses.parse call with max_retries=0, no tools, and store=false."
  - "Materialize an entire private staged slug tree under one retained 0600 lock and atomically promote or restore the prior tree, leaving post-commit backup retirement best-effort."

patterns-established:
  - "Model output owns semantic draft fields only; deterministic code owns paths, modes, frontmatter, provenance, identity, and durable writes."
  - "Generated packages contain only 0644 UTF-8 documentation leaves under 0700 directories, with scripts, binary content, executable modes, copied code blocks, and download-and-execute instructions rejected."

requirements-completed: [GEN-01, GEN-02, GEN-03, GEN-04, GEN-05]

coverage:
  - id: G1
    description: "A qualified verified WorkflowSpec enters exactly one strict tool-free Generator call and produces a bounded semantic draft without raw-source execution authority."
    requirement: GEN-01
    verification:
      - kind: unit
        ref: "tests/test_openai_generate.py (10 request, outcome, injection, telemetry, and one-call cases)"
        status: pass
      - kind: integration
        ref: "Gate-B3-prefixed full pytest suite (865 passed)"
        status: pass
    human_judgment: false
  - id: G2
    description: "The deterministic renderer emits only SKILL.md and justified reference documentation with no scripts, binaries, executable modes, copied executable blocks, or allowed-tools grant."
    requirement: GEN-02
    verification:
      - kind: unit
        ref: "tests/test_skill_generation.py (28 contract, renderer, identity, safety, and durability cases)"
        status: pass
    human_judgment: false
  - id: G3
    description: "Generalized instructions retain human control; optional verbatim excerpts are capped and require verified source path plus exact commit attribution."
    requirement: GEN-03
    verification:
      - kind: unit
        ref: "tests/test_skill_generation.py quote-boundary and executable/supply-chain rejection cases"
        status: pass
    human_judgment: false
  - id: G4
    description: "Canonical machine-readable provenance binds complete source, WorkflowSpec, lineage, qualification, model, version, request, usage, and latency evidence before external package identity."
    requirement: GEN-04
    verification:
      - kind: unit
        ref: "tests/test_skill_generation.py provenance completeness, future-fact exclusion, and package sensitivity cases"
        status: pass
    human_judgment: false
  - id: G5
    description: "Stable lineage slug selects one replaceable package directory while semantic and rendered identities remain distinct, deterministic, and non-circular."
    requirement: GEN-05
    verification:
      - kind: unit
        ref: "tests/test_skill_generation.py deterministic identity, retained-lock update, rollback, and attack cases"
        status: pass
      - kind: integration
        ref: "Protected Phase 1/2 and generation regression set (213 passed)"
        status: pass
    human_judgment: false

duration: 24 min
completed: 2026-07-23
status: complete
---

# Phase 03 Plan 08: Frozen Skill Generation and Materialization Summary

**A one-call tool-free Generator now yields a canonical semantic draft that deterministic code freezes into an attributed, provenance-complete, docs-only Skill package with atomic replace-or-restore durability.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-07-23T10:41:25Z
- **Completed:** 2026-07-23T11:05:14Z
- **Tasks:** 3/3
- **Implementation/test files:** 7

## Accomplishments

- Added strict frozen contracts for semantic drafts, bounded attributed quotes, generation-only authority, complete provenance, rendered files/manifests, and separate semantic/package identities.
- Added an isolated OpenAI Responses Generator with a strict canonical request projection, `max_retries=0`, exactly one request, no tools, `store=false`, bounded context/output, sanitized typed failures, and external model/request/usage telemetry.
- Added deterministic Agent Skill rendering with stable slug frontmatter, generalized reusable instructions, optional generated references, complete canonical provenance, fixed documentation-only paths/modes, and explicit executable/supply-chain rejection.
- Added a descriptor-anchored materializer with retained 0600 lock inode, private staging, no-follow opens, fixed 0700/0644 modes, leaf/directory fsync, atomic whole-tree promotion, exact prior-tree rollback, secure stale-temp recovery, and best-effort post-commit cleanup.
- Proved deterministic bytes, quote limits and attribution, dual-identity sensitivity, one-call provider behavior, injection resistance, retained-lock reuse, rollback at every pre-commit seam, cleanup semantics, and symlink/hard-link/temp attack rejection.

## Task Commits

Each TDD task was committed with RED before GREEN:

1. **Task 1 RED: Generation and package contract tests** - `a0d6052` (`test`)
2. **Task 1 GREEN: Frozen generation contracts and identities** - `41ff55c` (`feat`)
3. **Task 2 RED: Recorded Generator adapter fixtures/tests** - `5a162a2` (`test`)
4. **Task 2 GREEN: One-call bounded OpenAI Generator** - `a5596e3` (`feat`)
5. **Task 3 RED: Renderer and materializer durability tests** - `b1fdeac` (`test`)
6. **Task 3 GREEN: Deterministic renderer and durable materializer** - `4e04796` (`feat`)

Supporting deviation commit:

- **Static capability guard update** - `3eeb488` (`fix`)

## Files Created/Modified

- `src/skillscout/domain/skill_artifacts.py` - Strict draft/provenance/package contracts, canonical dual identities, deterministic renderer, and descriptor-anchored materializer.
- `src/skillscout/adapters/openai_generate.py` - One-call strict Structured Outputs Generator adapter and closed telemetry outcomes.
- `tests/test_skill_generation.py` - Contract, identity, rendering, safety, mode, durability, rollback, and attack coverage.
- `tests/test_openai_generate.py` - Exact request, one-call, result, failure, telemetry, credential, and prompt-injection coverage.
- `tests/fixtures/openai/generator/cases.json` - Recorded success, injection, refusal, incomplete, schema-invalid, 429, and 500 cases.
- `tests/recorded_transport.py` - Named Generator case loader using the existing recorded transport.
- `tests/test_phase1_gap_closure.py` - Static capability guard carve-out for the dedicated Generator adapter.

## Decisions Made

- Semantic identity includes only the canonical `GeneratedSkillDraft` and an explicit generation-time authority projection. Request ID, usage, latency, rendered paths/modes, validation, Reviewer, eligibility, and terminal facts cannot enter that identity.
- Provenance deliberately includes request/model/usage/latency evidence, so telemetry changes the external package identity without changing semantic identity.
- The Generator receives a strict bounded canonical `GenerationRequestV1`, not raw repository files, previous model transcripts, tools, or execution permissions.
- The materializer replaces a complete slug directory from a private staged tree. Its retained lock file is never deleted or recreated, and any failure before the root-directory durability point restores the exact prior tree.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Test Guard] Admitted the planned isolated Generator adapter**
- **Found during:** Task 3 overall verification
- **Issue:** The Phase 1 static capability test allowed the existing OpenAI extraction adapter but rejected the new plan-required `openai_generate.py` import before evaluating its isolation guarantees.
- **Fix:** Added only `adapters/openai_generate.py: openai` to the closed import carve-out; all other forbidden imports and direct calls remain rejected.
- **Files modified:** `tests/test_phase1_gap_closure.py`
- **Verification:** The targeted static guard passed, then the full 865-test suite and full Ruff passed.
- **Committed in:** `3eeb488`

---

**Total deviations:** 1 auto-fixed Rule 3 blocking test-guard issue.
**Impact on plan:** The update recognizes exactly the plan-authored isolated OpenAI capability and does not widen network, tool, execution, credential, or publication authority.

## Issues Encountered

- Context7 MCP and its `ctx7` CLI fallback were unavailable. Implementation therefore mirrored the repository's installed, already-tested OpenAI Responses adapter pattern and verified exact serialized requests through the pinned SDK's recorded HTTP transport.

## Authentication Gates

None.

## Known Stubs

None.

## Verification

- Task 1 exact contract selection: **13 passed**.
- Task 2 exact Generator adapter suite: **10 passed**.
- Task 3 exact renderer/materializer suite: **28 passed**.
- Protected state integrity, Phase 2 pipeline, extraction, Generator, and Skill package regressions: **213 passed**.
- Full Gate-B3-prefixed test suite: **865 passed**.
- Full Gate-B3-prefixed Ruff: **All checks passed**.
- Changed-file and stub scan: no goal-blocking placeholders, empty UI data, TODOs, or FIXMEs.
- Threat-surface scan: no unplanned surface. The new OpenAI semantic boundary and local descriptor-anchored package writer are exactly the plan-authored surfaces covered by its Generator, provenance, source-attribution, filesystem, and supply-chain mitigations.

## User Setup Required

None for this plan. Runtime composition will inject the existing least-privilege OpenAI credential; no credential was read, logged, persisted, or sent in package bytes during verification.

## Next Phase Readiness

- Plan 03-09 can validate the frozen package without reopening model semantics or changing package bytes.
- Later Reviewer, eligibility, ledger, and Draft PR plans can consume the two distinct identities and complete provenance without becoming part of generation authority.
- No blocker remains for the next sequential plan; this executor did not start it.

## Self-Check: PASSED

- Found every declared implementation/test/fixture file and this summary on disk.
- Confirmed all six TDD commits and the one deviation commit exist in RED-before-GREEN order.
- Reconfirmed all exact task commands, the protected 213-test set, full 865-test suite, full Ruff, stub scan, and threat-surface scan recorded above.

---
*Phase: 03-validated-skill-candidate*
*Completed: 2026-07-23*
