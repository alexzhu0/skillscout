---
phase: 01-auditable-dry-run-spine
plan: "17"
subsystem: state-durability
tags: [crash-recovery, atomic-write, flock, sqlite, stale-temp, offline]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: AnchoredDirectory deterministic-temp atomic writes, retained state flock, private regular-file predicate, finite no-replay resume ledger
provides:
  - AnchoredDirectory.recover_stale_temporary owner-validated stale-temp recovery primitive with mandatory directory fsync
  - Under-lock startup recovery of state/backup temps and serialized manifest temp recovery in SQLiteStateStore
  - Publication-plan operation lock (retained .publication-plan.json.lock flock inode) with stale-temp recovery
  - Killed-writer SIGKILL regression proving pending-stage completion with zero prefix replay
affects: [phase-01-verification, plan-01-18, code-review, security-audit]

tech-stack:
  added: []
  patterns:
    - crash-left deterministic temps are admitted to deletion only under the corresponding retained lock after the private regular-file predicate passes
    - publication writers serialize on a retained kernel-flock inode that is never deleted (kernel-only ownership survives process death)
    - recovery fails closed on the existing sanitized SafeFailure codes; invalid temps are rejected and retained

key-files:
  created: []
  modified:
    - src/skillscout/adapters/localfs.py
    - src/skillscout/adapters/state.py
    - src/skillscout/application/pipeline.py
    - tests/test_state_integrity.py
    - tests/test_pipeline_resume.py
    - tests/test_cli_dry_run.py

key-decisions:
  - "Recovery reuses _require_private_regular and unlink(..., missing_ok=False, sync=True); a rejected temp is retained and the operation fails closed."
  - "State and manifest recovery run under the already-retained state flock, so a leftover temp can only belong to a dead former lock holder."
  - "Publication writes take a non-blocking LOCK_EX flock on a retained .{target}.lock inode (mode 0o600, anchored/opened stat identity check); a live holder makes concurrent writes fail closed with state_operation_failed."
  - "_atomic_write_once keeps the temporary_exists refusal unchanged so the primitive stays fail-closed whenever no recovery authority ran."

patterns-established:
  - "Lock-gated recovery: every deterministic-temp call site recovers crash-left temps only while holding the state lock (state/manifest) or the publication operation lock."
  - "Retained lock inode: flock ownership is kernel-only; the lock file is created once, validated by (st_dev, st_ino) identity, and never deleted."

requirements-completed: [OPS-04]

coverage:
  - id: D1
    description: "Owner-validated stale-temp recovery primitive removes private temps with a proven directory fsync, rejects and retains non-private temps, no-ops on absence, and keeps the fail-closed backstop."
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "tests/test_state_integrity.py#test_recover_stale_temporary_removes_private_temp_and_fsyncs_directory"
        status: pass
      - kind: unit
        ref: "tests/test_state_integrity.py#test_recover_stale_temporary_rejects_and_retains_non_private_temps"
        status: pass
      - kind: unit
        ref: "tests/test_state_integrity.py#test_recover_stale_temporary_missing_temp_is_a_noop"
        status: pass
      - kind: unit
        ref: "tests/test_state_integrity.py#test_atomic_write_still_refuses_preexisting_temp_without_recovery"
        status: pass
    human_judgment: false
  - id: D2
    description: "State, backup, and manifest crash-left temps recover under the retained state lock; non-private startup temps fail closed and are retained."
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "tests/test_state_integrity.py#test_startup_recovers_private_state_and_backup_temps"
        status: pass
      - kind: unit
        ref: "tests/test_state_integrity.py#test_startup_rejects_non_private_state_temp_without_touching_it"
        status: pass
      - kind: unit
        ref: "tests/test_state_integrity.py#test_write_manifest_recovers_crash_left_temp"
        status: pass
    human_judgment: false
  - id: D3
    description: "A SIGKILLed writer's stale state temp never blocks reopen: the pending stage completes with reused_stage_count == 6 and byte-identical verified-prefix rows (no replay)."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay"
        status: pass
    human_judgment: false
  - id: D4
    description: "Publication-plan writes recover stale temps under a retained operation lock; a concurrent live lock holder forces fail-closed state_operation_failed, and the lock inode is retained after success."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_publication_stale_temp_recovers_under_retained_operation_lock"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_concurrent_publication_write_fails_closed_until_lock_holder_exits"
        status: pass
    human_judgment: false

duration: 35min (interrupted once; closeout verified and committed)
completed: 2026-07-20
status: complete
---

# Plan 01-17: Stale-Temp Crash Recovery Wiring Summary

**Crash-left deterministic temps no longer block state, manifest, or publication-plan replacement: owner-validated recovery runs under the retained state lock and a new publication operation lock, proven by a SIGKILL killed-writer regression with zero prefix replay.**

## Performance

- **Duration:** ~35 min across two sessions (interrupted after implementation; closeout completed verification/commit)
- **Started:** 2026-07-20T08:58:38Z (first RED commit)
- **Completed:** 2026-07-20T09:29:13Z (GREEN commit)
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- `AnchoredDirectory.recover_stale_temporary` removes owner-valid stale temps with mandatory directory fsync, rejects/retains non-private temps, no-ops on absence, and leaves the `temporary_exists` backstop untouched.
- `SQLiteStateStore` recovers state and backup temps after `_acquire_lock` and before the state read, and recovers manifest temps in `_write_manifest` under the same retained lock.
- `PipelineRunner._write_publication_plan` serializes writers on a retained `.publication-plan.json.lock` kernel-flock inode and recovers plan/backup temps before writing; concurrent writers fail closed with `state_operation_failed`.
- Killed-writer regression proves SIGKILL residue recovers on reopen and the pending stage completes with `reused_stage_count == 6` and byte-identical prefix rows.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 01-17-01: Owner-validated stale-temp recovery primitive** — `f8e2e17` (test, RED), `81bf686` (feat, GREEN)
2. **Task 01-17-02: Under-lock recovery wiring and killed-writer crash regression** — `b48215d` (test, RED), `15463e7` (feat, GREEN)

## Files Created/Modified
- `src/skillscout/adapters/localfs.py` — `recover_stale_temporary(name)` beside `atomic_write`; reuses `validate_child_name`, `stat_child`, `_require_private_regular`, `unlink(..., missing_ok=False, sync=True)`.
- `src/skillscout/adapters/state.py` — startup recovery of `.{state}.tmp`/`..{state}.backup.tmp` after `_acquire_lock` before the `before_state_read` seam; manifest temp recovery immediately before `anchor.atomic_write`.
- `src/skillscout/application/pipeline.py` — `_acquire_publication_lock` (anchored open, private-regular + inode-identity checks, non-blocking flock, fail closed) plus under-lock plan/backup temp recovery; new `fcntl`/`os` imports.
- `tests/test_state_integrity.py` — primitive admission/rejection/no-op/backstop tests; startup recovery/rejection; manifest recovery.
- `tests/test_pipeline_resume.py` — killed-writer SIGKILL regression; publication stale-temp recovery; concurrent publication lock rejection.
- `tests/test_cli_dry_run.py` — output-directory listing expectation now includes the retained lock inode (see Deviations).

## Decisions Made
- Recovery reuses the existing private regular-file predicate and synchronized unlink; anything failing the predicate is retained and the operation fails closed on sanitized codes.
- State/manifest recovery runs under the already-retained state flock — a leftover temp can only belong to a dead former lock holder.
- The publication lock inode is created once at mode 0o600, validated by (st_dev, st_ino) identity between anchored and opened stats, flocked non-blockingly, closed after the write, and never deleted.
- No new dependency, CLI flag, schema version, or remote capability was introduced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Blocking] Pre-existing CLI dry-run test rejected the plan-mandated retained lock inode**
- **Found during:** Task 01-17-02 full-suite verification (`pytest -q tests`).
- **Issue:** `tests/test_cli_dry_run.py::test_approved_fixture_reaches_planned_not_published` asserted the output directory contains exactly `["publication-plan.json"]`, while the plan mandates a retained `.publication-plan.json.lock` inode beside the plan (never deleted; the plan's own new tests assert the lock inode is retained). The two statements conflict; the retained-lock artifact is the behavior-defining requirement.
- **Fix:** Updated the listing expectation to the sorted pair `[".publication-plan.json.lock", "publication-plan.json"]` and read the plan by name. No production behavior changed.
- **Files modified:** `tests/test_cli_dry_run.py`
- **Verification:** Full locked suite 312 passed; Ruff clean.
- **Committed in:** `15463e7` (part of the Task 01-17-02 GREEN commit)

### Interruption Recovery (orchestrator-verified)

The first executor was interrupted after all implementation landed: T01 fully committed, T02 RED committed (`b48215d`), T02 GREEN uncommitted. The orchestrator verified the state; this closeout reviewed the uncommitted diff against the plan (coherent — startup state/backup recovery, manifest recovery, publication lock + recovery exactly as specified), ran the plan's verify commands, applied the single auto-fix above, and committed GREEN. No re-implementation was needed.

---

**Total deviations:** 1 auto-fixed (blocking test-expectation conflict with a plan-mandated artifact)
**Impact on plan:** The auto-fix reflects the plan-mandated retained lock inode in one pre-existing listing assertion; no scope creep, no weakened expectations.

## Issues Encountered
- Executor interruption mid-plan — recovered as described above with no lost work.
- Full-suite failure in `test_cli_dry_run.py` (stale exact-listing expectation) — fixed per deviation 1.

## Self-Check Results

All commands ran offline through the repository-local pinned uv (`UV_OFFLINE=1 ... uv run --locked`):

- `pytest -q tests/test_pipeline_resume.py tests/test_state_integrity.py` — **190 passed**
- `pytest -q tests` — **312 passed**
- `ruff check src/skillscout tests` — **All checks passed**
- `grep -c "def recover_stale_temporary" src/skillscout/adapters/localfs.py` — **1**
- `grep -c "recover_stale_temporary" src/skillscout/adapters/state.py` — **3** (startup state, startup backup, manifest)
- `grep -c "flock" src/skillscout/application/pipeline.py` — **2**
- `tests/test_pipeline_resume.py::test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay` — **pass** (externally bound name for Plan 01-18; asserts `reused_stage_count == 6`, nine ordered checkpoints, byte-identical prefix tuples)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Verification gap 1 (BLOCKER) is ready for independent re-review with the named crash regression as evidence.
- Plan 01-18 may bind this plan's resulting bytes; the externally bound test name `test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay` exists and passes.
- Flagged assumption remains for manual review: SIGKILL via multiprocessing models the crash window; power-loss filesystem semantics stay covered by the existing mandatory fsync discipline.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-20*
