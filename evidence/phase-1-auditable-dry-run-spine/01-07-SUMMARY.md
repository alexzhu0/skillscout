---
phase: 01-auditable-dry-run-spine
plan: "07"
subsystem: local-state
tags: [sqlite, dir-fd, flock, fsync, durability, race-resistance]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: schema-v2 lifecycle ledger, bounded manifests, and local-only runtime composition
provides:
  - Descriptor-anchored state, manifest, and publication-plan filesystem operations
  - Bounded private in-memory SQLite snapshots with reusable exclusive flock ownership
  - Fail-stop file and directory durability ordering before checkpoints and terminal status
affects: [state-integrity, pipeline-resume, publication-planning, phase-01-verification]

tech-stack:
  added: []
  patterns:
    - retained dir_fd operations with closed child names
    - serialized SQLite copy-on-write snapshots
    - mandatory file and directory fsync before state promotion

key-files:
  created:
    - src/skillscout/adapters/localfs.py
  modified:
    - src/skillscout/adapters/state.py
    - src/skillscout/application/pipeline.py
    - tests/test_state_integrity.py
    - tests/test_pipeline_resume.py

key-decisions:
  - "Never give SQLite an operator pathname: deserialize bounded anchored bytes into a private :memory: connection and durably serialize each candidate mutation."
  - "Use one retained 0600 lock inode with nonblocking kernel flock ownership; close releases ownership and the inert inode is reused."
  - "Treat every required file, leaf-directory, and new-ancestor fsync failure as fatal before checkpoint or terminal-state promotion."

patterns-established:
  - "Anchored local I/O: validate each path component, retain the directory descriptor, and resolve every child relative to dir_fd."
  - "Fail-stop snapshot promotion: publish and sync candidate bytes before replacing the active in-memory SQLite connection."
  - "Durability ordering: manifest before checkpoint; publication-plan bytes before planned_not_published."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "State and manifest writes remain bound to verified directory descriptors across parent-path swaps and process crashes."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_parent_swap_after_state_anchor_cannot_redirect_state_or_manifests"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_killed_lock_owner_releases_flock_without_recreating_lock_inode"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every SQLite mutation is a bounded serialized copy-on-write snapshot that restores prior bytes and requires reopen after durability failure."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_state_snapshot_sync_failure_restores_prior_bytes_and_requires_reopen"
        status: pass
      - kind: unit
        ref: "tests/test_state_integrity.py#test_state_uses_private_memory_sqlite_and_one_reusable_live_lock"
        status: pass
    human_judgment: false
  - id: D3
    description: "Manifest and publication-plan file and directory durability precede checkpoint and planned_not_published transitions."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_manifest_sync_failure_never_advances_checkpoint"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_publication_sync_failure_prevents_terminal_transition"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_publication_is_directory_durable_before_terminal_state_transaction"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 07: Descriptor-Anchored Durable State Summary

**Descriptor-anchored manifests and publication plans with exclusive serialized SQLite snapshots whose file and directory durability always precedes state success.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-19T05:36:10Z
- **Completed:** 2026-07-19T05:56:12Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added retained, verified directory descriptors with closed child-name validation, relative create/open/rename/unlink operations, durable ancestor creation, and parent-swap resistance.
- Replaced pathname SQLite with a 64 MiB-bounded private `:memory:` connection, serialized copy-on-write snapshots, and a reusable nonblocking exclusive flock held for the store lifetime.
- Made file fsync, rename, containing-directory fsync, and new-ancestor sync mandatory before manifest checkpoints or terminal publication status; failures restore prior state when possible and poison the active store.
- Added deterministic parent-swap, second-writer, SIGKILL lock recovery, oversize/deserialize, fsync failure, restoration, and publication-order regressions.

## Task Commits

Each TDD task was committed with a failing test gate followed by its implementation:

1. **Task 01-07-01: Anchor state and manifest operations to verified directories** - `a8073cf` (test), `8e08868` (feat)
2. **Task 01-07-02: Make manifest and publication durability a prerequisite for DB success** - `f292a24` (test), `f0db8c9` (feat)

## Files Created/Modified

- `src/skillscout/adapters/localfs.py` - Descriptor-retained directory traversal, bounded reads, durable atomic replace, restoration, and anchored cleanup.
- `src/skillscout/adapters/state.py` - Exclusive flock lifetime, bounded anchored state reads, private SQLite deserialize/serialize, copy-on-write persistence, and anchored manifests.
- `src/skillscout/application/pipeline.py` - Durable anchored publication-plan writer that completes before the terminal run transition.
- `tests/test_state_integrity.py` - Parent-swap, lock contention, killed-owner recovery, oversize, and failure-cleanup evidence.
- `tests/test_pipeline_resume.py` - File/directory/ancestor fsync failures, exact snapshot restoration, and publication ordering evidence.

## Decisions Made

- SQLite receives only `":memory:"`; operator-selected state paths are never passed to the SQLite VFS or `/dev/fd`.
- The ordinary `.<state>.lock` file is retained and reused. Live ownership is exclusively `flock(LOCK_EX | LOCK_NB)`, so process death releases ownership without inode deletion or recreation.
- Candidate state becomes active only after bounded serialization, anchored atomic replacement, and required directory sync. Any persistence ambiguity closes the connection and requires reopen/validation.
- Phase 1 intentionally remains single-process and exclusive, with no live cross-process reader promise, WAL, journal, or sidecar files.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- A legacy test monkeypatched the process-global `os.open` to prove manifests were not touched. That instrumentation invalidated the new fail-closed dir-fd capability check, so it was replaced with the plan's explicit filesystem seam and now proves no manifest event occurs without weakening secure-open validation.

## User Setup Required

None - no external service configuration required.

## Verification Evidence

- Full locked offline suite: `113 passed`.
- Plan-targeted durability suite: `59 passed`.
- Ruff: all checks passed across `src/skillscout` and `tests`.
- `uv.lock` SHA-256 remained `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database and provenance fixture git object hashes remained unchanged.
- Static scan found only `sqlite3.connect(":memory:")`; no state pathname, `/dev/fd`, WAL, or journal open exists.

## Known Stubs

None.

## Self-Check: PASSED

- Created file exists: `src/skillscout/adapters/localfs.py`.
- Modified production files exist: `src/skillscout/adapters/state.py`, `src/skillscout/application/pipeline.py`.
- Task commits exist: `a8073cf`, `8e08868`, `f292a24`, `f0db8c9`.
- All acceptance and plan-level verification commands passed after the final task commit.

## Next Phase Readiness

- CR-07 and CR-08 are closed with deterministic race and durability evidence.
- Phase 1 plan 01-08 can build on a descriptor-anchored, fail-stop local evidence substrate.
- No blockers remain from this plan.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*
