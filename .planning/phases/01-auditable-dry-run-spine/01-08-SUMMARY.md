---
phase: 01-auditable-dry-run-spine
plan: "08"
subsystem: local-state
tags: [sqlite, run-identity, migration, checkpoint, resume, tdd]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: descriptor-anchored serialized SQLite snapshots, bounded manifests, and symmetric stage lifecycle handling
provides:
  - Run-scoped result row identities separated from reusable semantic result digests
  - Complete five-field run identities persisted before work and queried through an exact resume index
  - Transactional canonical binding for migrated legacy_unbound v1 runs
  - Changed-input and A/B/A recovery evidence without replay or cross-run mutation
affects: [state-integrity, pipeline-resume, migration, inspect-run, phase-01-verification]

tech-stack:
  added: []
  patterns:
    - semantic content digest separated from run-owned association identity
    - exact five-field run identity lookup before checkpoint reuse
    - proof-before-authority binding for incomplete legacy evidence

key-files:
  created: []
  modified:
    - src/skillscout/domain/models.py
    - src/skillscout/domain/canonical.py
    - src/skillscout/application/ports.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/adapters/state.py
    - tests/test_stage_contracts.py
    - tests/test_pipeline_resume.py
    - tests/test_state_integrity.py
    - tests/test_cli_dry_run.py

key-decisions:
  - "Keep result_id as a reusable semantic digest and use deterministic result_row_id for each run/stage association and checkpoint foreign key."
  - "Persist and query schema, subject, fixture, producer, and retry-policy identity as one strict RunIdentity before any attempt begins."
  - "Keep migrated v1 runs legacy_unbound until the current fixture proves every reconstructible canonical fact inside the binding transaction."

patterns-established:
  - "Association ownership: result_row_id is the primary and foreign-key identity; result_id remains a non-unique indexed audit fact."
  - "Exact recovery: resumable candidates are selected by the complete persisted RunIdentity, never subject recency alone."
  - "Legacy authority: unbound evidence cannot authorize inspect or resume; a wrong expected identity is read-only and non-mutating."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Semantically identical stage outputs can belong to distinct runs without row collisions or checkpoint ambiguity."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_semantic_result_twins_use_distinct_run_scoped_rows"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_result_row_constraints_reject_cross_run_checkpoint_and_duplicates"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_v1_migration_preserves_semantic_results_and_adds_row_identity"
        status: pass
    human_judgment: false
  - id: D2
    description: "Fresh runs persist complete identities before work and exact lookup resumes A even when a newer mismatching B exists."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_complete_run_identity_is_persisted_before_first_attempt"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_exact_identity_lookup_uses_index_and_skips_newer_subject_mismatch"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_a_interrupt_b_interrupt_a_rerun_resumes_exact_a_without_touching_b"
        status: pass
    human_judgment: false
  - id: D3
    description: "Migrated v1 evidence stays legacy_unbound until exact canonical proof binds it transactionally for inspect and Validators-first resume."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_migrated_frozen_run_resumes_at_validators_without_replay"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_changed_a_prime_completes_without_reuse_and_both_runs_inspect"
        status: pass
    human_judgment: false

duration: 19min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 08: Exact Run Identity and Collision-Free Resume Summary

**Run-scoped result ownership, exact five-field recovery, and proof-gated legacy binding now preserve convergent audit data without collisions or cross-run replay.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-07-19T06:02:05Z
- **Completed:** 2026-07-19T06:21:18Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Split persisted association ownership from semantic identity: `result_row_id` keys stage rows and checkpoints while repeatable `result_id` values remain indexed audit facts.
- Persisted strict five-field `RunIdentity` records before the first attempt and made resume selection use the complete exact identity index, including producer and retry-policy isolation.
- Migrated frozen v1 evidence to explicit `legacy_unbound`, denied inspect and checkpoint authority before binding, and added non-mutating wrong-bind plus transactional exact-bind behavior.
- Added changed A-prime and A-interrupt/B-interrupt/A-rerun regressions proving zero unintended reuse, exact A recovery, byte-identical reused hashes, and untouched B evidence.

## Task Commits

Each TDD task was committed with a failing test gate followed by its implementation:

1. **Task 01-08-01: Separate semantic result digest from run-scoped row identity** - `f34ba4e` (test), `15eabbe` (feat)
2. **Task 01-08-02: Persist complete run identity and resume the exact A/B/A candidate** - `c430c8e` (test), `37dde5c` (feat)

## Files Created/Modified

- `src/skillscout/domain/models.py` - Strict `RunIdentity`, bound/unbound `RunRecord`, and result-row-aware envelope/checkpoint contracts.
- `src/skillscout/domain/canonical.py` - Canonical run/stage `make_result_row_id` distinct from semantic `make_result_id`.
- `src/skillscout/application/ports.py` - Provider-independent typed state lookup, binding, checkpoint, reconciliation, and run projection operations.
- `src/skillscout/application/pipeline.py` - Complete identity construction before mutation, exact current/legacy selection, typed checkpoint recovery, and row identity emission.
- `src/skillscout/adapters/state.py` - Identity-aware schema/migration/indexes, collision-free associations, canonical chain proof, legacy binding, and typed projections.
- `tests/test_stage_contracts.py` - Canonical semantic-versus-association identity contract.
- `tests/test_state_integrity.py` - Semantic twins, cross-run checkpoint rejection, uniqueness, and frozen migration evidence.
- `tests/test_pipeline_resume.py` - Complete identity timing, exact index, A-prime, A/B/A, and legacy binding/resume regressions.
- `tests/test_cli_dry_run.py` - Updated inspect projection evidence for complete bound run identity.

## Decisions Made

- Semantic convergence is legitimate audit data, so `result_id` remains stable and non-unique; ownership is expressed only by `result_row_id = sha256({run_id, stage})`.
- Run identity is one strict value object. The adapter stores and queries all five fields together, and a mismatching newer subject row cannot hide an older exact candidate.
- Migrated v1 rows retain only facts proven by their attempt history and remain `legacy_unbound`. They expose only `STATE_IDENTITY_UNBOUND` until current fixture bytes prove the chain and the same serialized snapshot binds it.
- Historical schema-v1 binding stays within the immutable supported producer/schema registry; no new producer capability or remote authority was added.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Strict Pydantic persisted projections require domain enum instances rather than raw SQLite strings. The adapter now converts `execution_mode`, run status, and checkpoint stage at the boundary before validation.
- An extra mypy probe was unavailable in the locked environment; it was not installed or substituted. The plan-required pytest and Ruff checks all passed.

## User Setup Required

None - no external service configuration required.

## Verification Evidence

- Full locked offline suite: `121 passed`.
- Result association and migration suite: `19 passed`, `59 deselected`.
- Exact identity, changed-input, migration, and resume suite: `34 passed`.
- Ruff: all checks passed across `src/skillscout` and `tests/test_pipeline_resume.py`.
- `uv.lock` SHA-256 remained `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256 remained `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`; all six migrated semantic result IDs were preserved.

## Known Stubs

None.

## Self-Check: PASSED

- Modified production files exist: `models.py`, `canonical.py`, `ports.py`, `pipeline.py`, and `state.py`.
- Task commits exist: `f34ba4e`, `15eabbe`, `c430c8e`, and `37dde5c`.
- Every task acceptance criterion and both plan-level verification commands passed after the final implementation commit.
- No new network endpoint, authentication path, executable external content, or unplanned trust boundary was introduced.

## Next Phase Readiness

- Verification root gap 4 and its CR-02/WR-03 causes now have deterministic collision and exact-recovery evidence.
- Plan 01-09 can build on exact run identity and association ownership while hardening schema fingerprint and persisted projections.
- No blockers remain from this plan.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*
