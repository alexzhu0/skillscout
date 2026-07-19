---
phase: 01-auditable-dry-run-spine
plan: "14"
subsystem: resume-integrity
tags: [sqlite, resume-events, hash-chain, audit-projection, tamper-detection]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: schema-v3 immutable resume-event ledger and exact checkpoint-bound invocation decisions
provides:
  - Complete canonical verification of genesis, zero-prefix, and positive-prefix resume-event chains
  - Event-derived reuse authority with exact run head and denormalized count comparison
  - One fail-closed verifier for inspect, recovery, checkpoint, completed-result, run-read, and resume-decision paths
affects: [state-integrity, pipeline-resume, audit-inspection, phase-01-gap-closure]

tech-stack:
  added: []
  patterns:
    - typed event authority crosses persistence only after full hash, order, association, and timing verification
    - public reuse projections derive from the final verified event rather than mutable run summaries

key-files:
  created: []
  modified:
    - src/skillscout/domain/models.py
    - src/skillscout/adapters/state.py
    - tests/test_state_integrity.py
    - tests/test_pipeline_resume.py

key-decisions:
  - "Make the final verified ResumeEvent the sole reuse-count authority; runs.reused_stage_count and latest_resume_event_hash are accepted only as exact duplicates of that proof."
  - "Verify migrated bound schema-v2 runs after their conservative genesis event is installed in the exact schema-v3 candidate, so migration uses the same canonical verifier without inventing prior invocations."
  - "Treat read_run as an authoritative public projection and route it through verify_run_chain instead of preserving a weaker row-only read path."

patterns-established:
  - "Event-chain closure: canonical hashes, contiguous ordinals, prior heads, timestamps, checkpoint identities, run head, and projected count are one indivisible proof."
  - "Projection closure: inspect fills both nested and top-level reuse counts from VerifiedRunChain.reused_stage_count only after complete verification."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Full-chain verification recomputes every resume event and rejects field, order, linkage, association, timing, head, and count tamper."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_full_chain_rejects_resume_event_order_shape_head_and_count_tamper"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_full_chain_rejects_positive_event_checkpoint_and_timing_tamper"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every bound trust path and public inspect projection consumes the same event-derived reuse authority and returns no partial payload on corruption."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_resume_event_tamper_is_rejected_by_every_bound_trust_path"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_completed_resumed_inspection_uses_one_verified_count_after_reopen"
        status: pass
    human_judgment: false
  - id: D3
    description: "Genesis-only, consecutive zero-prefix, positive-prefix, repeated-positive, and v1/v2 migrated-genesis chains retain valid audited recovery semantics."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_full_chain_accepts_genesis_only_and_consecutive_zero_prefix_events"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_zero_reuse_migration_verifies_with_exactly_one_genesis_event"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 14: Full Resume-Event Chain Authority Summary

**The canonical run proof now verifies every invocation event through its checkpoint provenance and derives all public reuse counts from the final verified event, closing CR-02 without a weaker audit path.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-07-19T10:30:28Z
- **Completed:** 2026-07-19T10:43:06Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Extended `VerifiedRunChain` with immutable typed resume events and an event-head-derived `reused_stage_count` property.
- Recomputed canonical event hashes, contiguous ordinals, prior heads, genesis binding, zero-prefix shape, positive checkpoint association, timestamp bounds, run head, and denormalized count in one verifier.
- Converged exact-identity recovery, latest checkpoint, completed-result verification, authoritative run reads, inspect, and resume decisions on the same full-chain proof.
- Proved valid genesis-only, consecutive zero-prefix, repeated positive-prefix, migrated v1/v2 genesis-only, and resumed terminal chains while rejecting the complete event/count tamper matrix with one sanitized error.

## Task Commits

Each TDD task was committed with a failing test gate followed by its implementation:

1. **Task 01-14-01: Extend the canonical run-chain proof through every resume event** - `29f5c18` (test), `0680d18` (feat)
2. **Task 01-14-02: Converge all public reuse projections on the verified event count** - `63b3913` (test), `64f772b` (feat)
3. **Rule-3 suite compatibility: Align prior mutable-count expectation with fail-closed authority** - `8d5b171` (test)

## Event Tamper Matrix

| Authority dimension | Direct corruption covered | Verified result |
|---|---|---|
| Cardinality and order | missing event, unheaded extra/duplicate event, wrong ordinal, reordered genesis | fixed `state_integrity_error` |
| Hash linkage | unrehashed payload, coherently rehashed broken prior, incorrect run head | fixed `state_integrity_error` |
| Genesis and zero-prefix shape | relabelled genesis, creation-time mismatch, later null prior, non-null zero checkpoint tuple | fixed `state_integrity_error` |
| Positive-prefix shape | partial tuple, count/stage mismatch, wrong result row, wrong manifest | fixed `state_integrity_error` |
| Timing | decreasing event time, zero event before creation, positive event before checkpoint completion | fixed `state_integrity_error` |
| Mutable projections | raw run count edit, coherent event/count/hash/head edit with false association | fixed `state_integrity_error` |

Exact duplicate event hashes and duplicate `(run_id, event_index)` ordinals are additionally blocked by the schema uniqueness constraints. A valid later zero-prefix event remains accepted because it has a new ordinal, prior head, canonical hash, all-null checkpoint tuple, and nondecreasing time.

## Derived-Count Proof

1. Every event row is strictly parsed into `ResumeEvent`, which independently recomputes its canonical hash.
2. The verifier requires exactly one ordinal-zero genesis at `run.created_at`, then contiguous later ordinals whose prior hash equals the preceding recomputed head.
3. A positive event references the already verified checkpoint at `reused_stage_count - 1` with exact stage, result-row identity, manifest identity, and a non-earlier timestamp. Zero events perform no checkpoint lookup.
4. The final verified event defines `VerifiedRunChain.reused_stage_count`.
5. `runs.latest_resume_event_hash` and `runs.reused_stage_count` must exactly equal that final event before any run model is returned.
6. Inspect writes the verified property into both `payload.run.reused_stage_count` and top-level `payload.reused_stage_count`; no raw SQLite count is projected first.

## Trust-Entry Consistency

The parameterized matrix applies raw count, event count, head, event hash, checkpoint reference, order, missing, extra/duplicate, and malformed zero-prefix damage to all bound entries:

- `find_resumable_run`
- `latest_checkpoint`
- `verify_completed_results`
- authoritative `read_run`
- `inspect_run`
- `record_resume_decision`

Every entry returns the same fixed `state_integrity_error`. The inspect capture remains `None`, and serialized current/durable state bytes remain unchanged after every rejected operation, proving no attempt, result, checkpoint, event, count, or partial JSON projection escapes.

## Migration and Crash-Window Semantics

- A schema-v1 zero-reuse run migrates through the exact v2/v3 rebuild, binds only after current fixture identity proof, and verifies with one genesis event.
- A schema-v2 bound zero-reuse run receives one conservative genesis event and is verified in the final schema-v3 candidate before commit.
- A pre-event nonzero schema-v2 claim remains rejected without source mutation.
- Genesis-only and any number of later canonical zero-prefix decisions are complete audited states even when no attempt follows; the verifier does not invent or require an unobserved attempt.
- Positive and repeated-positive events remain valid when they bind the exact completed prefix, including after close and reopen of a completed resumed run.

## Files Created/Modified

- `src/skillscout/domain/models.py` - Typed event tuple and derived reuse authority on `VerifiedRunChain`.
- `src/skillscout/adapters/state.py` - Canonical full event-chain verification, migration validation, verified reads, and inspect projection.
- `tests/test_state_integrity.py` - Event/count/head/order/association/timing tamper matrix, migration controls, and cross-entry consistency proof.
- `tests/test_pipeline_resume.py` - Fail-closed regression for direct denormalized count tamper.

## Decisions Made

- Event provenance is complete only when both immutable event facts and mutable run duplicates agree; neither content addressing nor a matching run count is sufficient by itself.
- Later zero-prefix events preserve the 01-13 crash-window invariant: they are independently hash-linked invocation facts and never trigger a checkpoint lookup.
- Pre-event migration performs its bound-run proof after conservative genesis installation in the exact candidate schema, keeping public trust paths on one event-aware verifier.
- `read_run` is authority-bearing and therefore verifies the full chain; no row-only method remains with a public audit-shaped name.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated the prior mutable-count self-repair expectation**
- **Found during:** Repository-wide verification after Task 01-14-02
- **Issue:** A Plan 01-13 lifecycle test expected a direct `runs.reused_stage_count` edit to be ignored and overwritten during resume, contradicting Plan 01-14's explicit requirement that every mutable duplicate mismatch fail closed.
- **Fix:** Changed the regression to require the fixed integrity failure and prove that rejection adds no attempt or resume event.
- **Files modified:** `tests/test_pipeline_resume.py`
- **Verification:** The focused regression and the complete 266-test locked offline suite pass.
- **Committed in:** `8d5b171`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking test-contract mismatch).  
**Impact on plan:** The historical assertion now matches CR-02's approved fail-closed contract; no production scope or architecture changed.

## Issues Encountered

None - the one stale cross-suite expectation was resolved under the documented deviation rule.

## User Setup Required

None - no dependencies, credentials, network access, remote writes, or external configuration were introduced.

## Verification Evidence

- Task 01 focused event/count/head/full-chain/migration selection: `65 passed` before the public-projection additions; all cases remain covered by the final file run.
- Final `tests/test_state_integrity.py`: `131 passed`.
- Full locked offline suite: `266 passed`.
- Full Ruff scan across `src` and `tests`: all checks passed.
- `uv.lock` SHA-256: `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256: `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`.
- `.planning/config.json` SHA-256 remains `5c5acc837fef244afd431f542223618d8abd043eb77b0ef9e08b98267d9d3219` and the file remains unstaged.

## Known Stubs

None.

## Self-Check: PASSED

- All four modified production/test files exist.
- RED/GREEN and deviation commits exist: `29f5c18`, `0680d18`, `63b3913`, `64f772b`, and `8d5b171`.
- Both task acceptance gates, the complete locked offline suite, Ruff, and all three protected byte hashes passed after the final code commit.
- No raw event row, unattested count, partial inspect payload, new endpoint, new authentication path, file-access pattern, schema object, dependency, or external trust surface was introduced.
- `.planning/config.json` is byte-identical to its pre-execution user/orchestrator state and is not staged.

## Next Phase Readiness

- CR-02 is completely closed with direct tamper and public-projection evidence.
- Plan 01-15 can address non-echoing CLI rejection and unexpected processor failure recovery without relying on mutable reuse summaries.
- No blockers remain from this plan.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*
