---
phase: 06-adversarial-mvp-acceptance
plan: "16"
subsystem: acceptance
tags: [github-actions, protected-environment, benchmark-lock, canonical-state, pydantic]

requires:
  - phase: 06-07
    provides: Human-selected fixed five-repository V1 selection manifest and fresh nomination
  - phase: 06-15
    provides: Checked-out-source and authority-zone baseline for Phase 6 workflows
provides:
  - Schema-discriminated V2 benchmark-lock facts that preserve V1 history
  - State-only fresh nomination and protected benchmark-lock routes
  - One environment-approved, persisted V2 five-repository benchmark lock
affects: [06-17-live-authority, 06-18-protected-route, 06-08-live-benchmark]

tech-stack:
  added: []
  patterns:
    - V1 history remains parseable while new authority is admitted only by exact schema version
    - GitHub protected-environment approval is persisted only as a redacted, canonical receipt

key-files:
  created: []
  modified:
    - src/skillscout/domain/acceptance.py
    - src/skillscout/adapters/operations_state.py
    - src/skillscout/application/acceptance.py
    - src/skillscout/bootstrap.py
    - src/skillscout/cli.py
    - .github/workflows/phase6-acceptance.yml
    - .planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json

key-decisions:
  - "A V2 benchmark lock proves only the human-selected benchmark; it cannot grant live-model or publication authority."
  - "The V1 selection manifest is preserved as immutable historical input while a V2 lock binds fresh nomination, source, workflow, state, and approval evidence."

patterns-established:
  - "Protected lock route: validate fixed source/state/manifest bindings before using an environment-scoped state credential, then perform one state-only CAS."
  - "Approval handling: parse only the fixed-host Actions approval response and retain no approval comment or credential value."

requirements-completed: [TEST-01, TEST-02]

coverage:
  - id: D1
    description: V2 benchmark-lock schema and state-only routes reject malformed or mismatched fresh-lock authority before any semantic or publication effect.
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "108 focused Phase 6 tests plus tools/verify_phase6_source_execution.py"
        status: pass
    human_judgment: false
  - id: D2
    description: The fixed five-repository selection was bound into a separately approved V2 benchmark lock.
    requirement: TEST-02
    verification:
      - kind: manual_procedural
        ref: "GitHub Actions run 30878463167; reviewer alexzhu0 approved the protected benchmark-lock environment"
        status: pass
    human_judgment: true
    rationale: The accountable five-repository selection and protected-environment approval require human judgment.

duration: historical execution reconciled on 2026-08-04
completed: 2026-08-04
status: complete
---

# Phase 6 Plan 16: Protected V2 Benchmark Lock Summary

**A protected, state-only V2 benchmark lock now binds the human-selected five repositories to exact source, workflow, nomination, selection, state, and approval evidence without granting live execution.**

## Performance

- **Duration:** Historical execution reconciled on 2026-08-04
- **Tasks:** 3
- **Files modified:** 13 implementation/test/workflow files, plus the fixed selection manifest

## Accomplishments

- Added `LockedBenchmarkManifestV2` and redacted approval-receipt handling while retaining `locked-benchmark-manifest-v1` as historical, byte-preserved evidence.
- Added closed `prepare-fresh-campaign` and `lock-fresh-campaign` routes; they are branch-restricted, protected-environment scoped, state-only, and exclude model, candidate-code, catalog, review, and publication capability.
- Persisted the V2 five-repository lock at source `7bab6abcb89b5287e8d32077333fd4383331d6e5` through [Actions run 30878463167](https://github.com/alexzhu0/skillscout/actions/runs/30878463167). It binds workflow SHA-256 `164cfd4eb25af493f4fad42ff25b6175d8f56a277e5539a121e021822fda1894`, selection digest `sha256:09aa2df9686f3094f361510fd2923edb6097df801c658d39e641f9207ffdb1f4`, nomination digest `sha256:46535e6ce499a710c2ecf5b9cd0db8134682dbac2429b8e3d7af4035130297ea`, and lock digest `sha256:3c1a9b2737ee79c58696e5e601b61e49b35549630f5826ac9fef3c694feaffa6`.
- Re-ran the Plan 06-16 focused offline checks during reconciliation: `108 passed, 207 deselected`; the independent source verifier reported `phase6 source execution valid`.

## Task Commits

1. **Task 1: Add schema-discriminated V2 benchmark-lock evidence** — `5aa54b1`, `e4cee19`
2. **Task 2: Implement the state-only protected benchmark-lock route and source proof** — `72e4d2f`, `2dfe690`, `879b95a`, `eca552e`, `636ea6a`
3. **Task 3: Configure and prove the protected V2 benchmark lock** — `a6f1d06`, followed by the environment-approved state-only run `30878463167`

## Files Created/Modified

- `src/skillscout/domain/acceptance.py` — Strict V2 benchmark-lock and redacted approval-receipt contracts.
- `src/skillscout/adapters/operations_state.py` — Schema-version-discriminated storage, restore, and rebuild for V1/V2 lock facts.
- `src/skillscout/application/acceptance.py` — Fresh nomination and exact selection-chain admission rules.
- `src/skillscout/bootstrap.py` and `src/skillscout/cli.py` — Closed state-only composition and command surface.
- `.github/workflows/phase6-acceptance.yml` — Branch-restricted protected benchmark-lock route.
- `.planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json` — Human-selected fixed V1 selection manifest bound by the V2 lock.

## Decisions Made

- The V2 lock is a benchmark-selection boundary only. It is not a live-authority grant and cannot call a model, read a candidate repository, publish a catalog change, or create a Pull Request.
- Approval comments and credential values remain hostile/sensitive transport data: neither enters canonical state, prompts, logs, or this summary.
- The bare workflow-path compatibility fix remains bounded to the exact Phase 6 workflow path, so Actions metadata cannot widen the verified source identity.

## Deviations from Plan

This summary was reconstructed after the implementation commits and protected checkpoint completed without a plan summary. Reconciliation added no production code and did not re-dispatch any remote action.

## Issues Encountered

- GitHub Actions reported the expected workflow path without an `@ref` suffix during the first V2 lock attempt. The narrowly scoped path compatibility fix was reviewed and merged before one fresh, separately approved lock run.

## User Setup Required

None. The two required environments and their environment-scoped state credentials were configured and used without inspecting any credential values.

## Next Phase Readiness

- Plan 06-17 must replace the historical V1 live-authority path with a V2, purpose-distinct live-execution authority before any benchmark or replay can receive credentials.
- No real benchmark, replay, Draft PR, review, merge, or publication result is credited by this plan.

## Self-Check: PASSED

- The Plan 06-16 commit chain and approved Actions run are recorded above.
- Focused Plan 06-16 offline tests passed: `108 passed, 207 deselected`.
- `tools/verify_phase6_source_execution.py` passed on the reconciled source.
- This summary records only public digests and identifiers; it contains no token, private key, approval comment, or raw state payload.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-08-04*
