---
phase: 01-auditable-dry-run-spine
plan: "13"
subsystem: resume-authority
tags: [sqlite, content-addressing, resume-events, migration, checkpoint-recovery]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: private atomic SQLite snapshots, exact identity recovery, and full-chain checkpoint verification
provides:
  - Immutable content-addressed invocation events for genesis, empty-prefix resume, and checkpoint-bound resume decisions
  - Schema-version-3 run heads whose reuse count, event head, status, and timestamp update atomically
  - Fail-closed migration that never converts an unattested historical nonzero reuse count into authority
affects: [state-integrity, pipeline-resume, audit-evidence, phase-01-gap-closure]

tech-stack:
  added: []
  patterns:
    - hash-linked invocation-event ledger with a non-self-referential canonical preimage
    - verified checkpoint selection persisted before resumed stage work
    - exact schema descriptors shared by fresh creation and migration rebuilds

key-files:
  created: []
  modified:
    - src/skillscout/domain/canonical.py
    - src/skillscout/domain/models.py
    - src/skillscout/application/ports.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/adapters/state.py
    - tests/test_state_integrity.py
    - tests/test_pipeline_resume.py
    - tests/test_cli_dry_run.py

key-decisions:
  - "Represent every invocation boundary as a content-addressed event: genesis alone is ordinal zero, while every reopened run appends a later event even when its verified prefix is empty."
  - "Treat the event ledger as reuse authority and keep runs.reused_stage_count only as an atomically maintained denormalized projection of the current event head."
  - "Migrate pre-event runs only when their historical reuse count is absent or zero; reject nonzero schema-v2 claims unchanged because no independent event can attest them."
  - "Commit the resume event, run head, count, running status, and timestamp in one candidate snapshot before stale-attempt reconciliation or processor invocation."

patterns-established:
  - "Empty-prefix provenance: a non-genesis count-zero event must have a prior event hash and an all-null checkpoint tuple."
  - "Checkpoint-bound provenance: positive counts equal checkpoint stage index plus one and carry exact stage, result-row, and manifest identities."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Every fresh or resumed invocation has canonical, contiguous, hash-linked reuse provenance, including explicit empty-prefix events."
    requirement: OPS-01
    verification:
      - kind: contract
        ref: "tests/test_state_integrity.py#test_resume_event_contract_accepts_only_three_canonical_shapes"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_crash_after_zero_prefix_decision_appends_another_zero_before_work"
        status: pass
    human_judgment: false
  - id: D2
    description: "Resume decisions are durably bound to the exact verified checkpoint before any new processor call and never replay a successful prefix."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_positive_resume_event_is_durable_before_first_new_processor_call"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_a_interrupt_b_interrupt_a_rerun_resumes_exact_a_without_touching_b"
        status: pass
    human_judgment: false
  - id: D3
    description: "Migration preserves zero-reuse history as genesis only and rejects unattested nonzero reuse without mutating source authority."
    requirement: OPS-01
    verification:
      - kind: migration
        ref: "tests/test_state_integrity.py"
        status: pass
      - kind: migration
        ref: "tests/test_pipeline_resume.py#test_migrated_frozen_run_resumes_at_validators_without_replay"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 13: Immutable Resume-Event Authority Summary

**A schema-v3 hash-linked invocation ledger now records the exact verified prefix before resumed work, so mutable run counters can no longer self-authorize checkpoint reuse.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-19T10:03:04Z
- **Completed:** 2026-07-19T10:22:58Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added strict frozen `ResumeEvent` shapes and a canonical non-self-referential hash for genesis, later empty-prefix, and positive checkpoint-bound invocation facts.
- Advanced SQLite to an exact schema-version-3 fingerprint with immutable event rows, a run head, safe v1/v2 rebuilds, and rejection of unattested nonzero historical reuse.
- Replaced the independent count setter with one atomic resume-decision mutation and wired the runner to persist its decision before stale-attempt handling, stage-attempt creation, or processor execution.
- Covered fresh genesis, crash-before-first-attempt, crash-after-zero-event, repeated positive resumes, mutable-count tampering, and A/B/A checkpoint association.

## Task Commits

Each TDD task was committed with a failing test gate followed by its implementation:

1. **Task 01-13-01: Add a canonical resume-event ledger and safe schema migration** - `46f6ba3` (test), `8b9e820` (feat)
2. **Task 01-13-02: Record each exact resume decision before new stage work** - `889415b` (test), `451994e` (feat)
3. **Rule-3 suite compatibility: Align CLI schema assertions with version 3** - `3a40760` (test)

## Schema Version 3 Fingerprint

- The exact named-object set is the existing three named indexes and four state tables plus the new `resume_events` table; additive or altered objects remain invalid.
- `runs` adds non-null `latest_resume_event_hash`, a deferred foreign key to `resume_events.event_hash`; `reused_stage_count` remains non-null with default zero as a projection, not authority.
- `resume_events` has the exact columns `event_hash`, `run_id`, `event_index`, `prior_event_hash`, `reused_stage_count`, `checkpoint_stage`, `checkpoint_result_row_id`, `checkpoint_manifest_hash`, and `recorded_at`.
- Primary-key and uniqueness identity are `event_hash` and `(run_id, event_index)`; foreign keys bind events to their run, prior event, and optional checkpoint result row.
- Fresh creation and v1/v2 rebuilds use the same descriptor set, with exact SQL, column, foreign-key, and index validation before promotion.

## Event Hash Preimage

The canonical JSON preimage includes every persisted semantic field except the self-referential hash:

| Field | Authority carried |
|---|---|
| `run_id` | Exact run identity |
| `event_index` | Contiguous invocation ordinal |
| `prior_event_hash` | Previous ledger head, null only for genesis |
| `reused_stage_count` | Verified prefix length |
| `checkpoint_stage` | Exact checkpoint stage or null for an empty prefix |
| `checkpoint_result_row_id` | Exact persisted result identity or null |
| `checkpoint_manifest_hash` | Exact manifest identity or null |
| `recorded_at` | Invocation decision timestamp |

`event_hash` is excluded only from its own preimage; canonical JSON ordering and SHA-256 make repeated calculation stable.

## Migration Matrix

| Source state | Historical reuse claim | Schema-v3 result |
|---|---:|---|
| Fresh database | 0 | Run and one genesis event/head/count created in one snapshot transaction |
| Schema v1 | absent/normalized to 0 | Rebuilt through exact v2 then v3 descriptors; one genesis event at `created_at` |
| Schema v2 | 0 | Rebuilt to exact v3; one genesis event only, with no invented prior resume boundary |
| Schema v2 | nonzero | Rejected fail-closed; source bytes and manifests remain unchanged |
| Unsupported or malformed schema | any | Rejected without durable mutation |

## Invocation Ordering Evidence

1. Select the exact resumable run and verify its complete persisted chain.
2. Select the verified latest checkpoint, or verified absence of any checkpoint.
3. In one candidate snapshot, append the next event and update the run head, projected count, status, timestamp, and cleared error fields.
4. Use the returned persisted event count as the pipeline start index and summary value.
5. Only then reconcile stale attempts, create a new stage attempt, and invoke the processor.

The crash-after-zero regression faults before `start_attempt`: the first later zero-prefix event remains durable, the following invocation appends another contiguous zero-prefix event, and stage zero then executes successfully. The positive-prefix probe observes its checkpoint-bound event from inside the first resumed processor call, proving event durability precedes work.

## Files Created/Modified

- `src/skillscout/domain/canonical.py` - Canonical resume-event hash preimage.
- `src/skillscout/domain/models.py` - Strict frozen `ResumeEvent` contract and shape validation.
- `src/skillscout/application/ports.py` - Atomic `record_resume_decision` port; independent count setter removed.
- `src/skillscout/application/pipeline.py` - Event-first fresh/resume orchestration and persisted-count summary authority.
- `src/skillscout/adapters/state.py` - Exact schema-v3 descriptors, safe migrations, ledger verification, genesis creation, and atomic resume decisions.
- `tests/test_state_integrity.py` - Event/hash/schema/migration integrity coverage.
- `tests/test_pipeline_resume.py` - Empty/positive prefix lifecycle, crash windows, repeated resumes, count tampering, and A/B/A coverage.
- `tests/test_cli_dry_run.py` - Schema-version-3 assertions for fresh and interrupted CLI state.

## Decisions Made

- Genesis is the sole ordinal-zero event. Reopening a genesis-only run records a distinct later zero-prefix decision instead of reusing genesis as evidence of a later invocation.
- The run-row count has no independent authority; pipeline control flow uses the event returned by the atomic decision mutation.
- Migration conservatively records only knowable history. A zero historical count supports genesis creation, while a nonzero count without an existing event cannot be trusted.
- Event creation occurs inside the existing private candidate-snapshot transaction so an event insert cannot become visible without its matching run head/count/status transition.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated stale CLI schema-version assertions**
- **Found during:** Repository-wide verification after Task 01-13-02
- **Issue:** Two CLI tests still asserted SQLite `user_version = 2`, so the full suite rejected the intentionally advanced exact schema version 3.
- **Fix:** Updated only the fresh and interrupted CLI expectations to version 3; runtime behavior and CLI output were unchanged.
- **Files modified:** `tests/test_cli_dry_run.py`
- **Verification:** The complete locked offline suite passes with 232 tests.
- **Committed in:** `3a40760`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking test-contract mismatch).  
**Impact on plan:** Repository-wide CLI coverage now recognizes the planned schema advancement without broadening production behavior.

## Issues Encountered

None - the repository-wide schema assertion mismatch was resolved under the deviation rule above.

## User Setup Required

None - no dependencies, network access, credentials, remote writes, or external configuration were introduced.

## Verification Evidence

- Task 01 focused integrity/resume suites: `135 passed` after the schema-ledger implementation.
- Task 02 focused resume lifecycle suite: `45 passed`.
- Combined integrity and recovery suites: `142 passed`.
- Full locked offline suite: `232 passed`.
- Full Ruff scan across `src` and `tests`: all checks passed.
- `uv.lock` SHA-256: `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256: `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`.

## Known Stubs

None.

## Self-Check: PASSED

- All eight modified production/test files exist.
- Task and deviation commits exist: `46f6ba3`, `8b9e820`, `889415b`, `451994e`, and `3a40760`.
- Task acceptance checks, the complete locked offline suite, Ruff, and both protected hashes passed after the final code commit.
- No unplanned network, authentication, executable-source, or schema trust surface was introduced; the new schema trust boundary is covered by the plan threat model and exact fingerprint checks.
- `.planning/config.json` remains byte-identical to its pre-execution user/orchestrator state and is not staged.

## Next Phase Readiness

- CR-02 is closed: every reuse count now has independent, immutable, verified-prefix provenance recorded before new work.
- Later verification can reconstruct invocation history from the event chain and compare the denormalized run head/count without trusting either in isolation.
- No blockers remain from this plan.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*
