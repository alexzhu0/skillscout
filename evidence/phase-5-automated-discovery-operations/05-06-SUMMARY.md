---
phase: 05-automated-discovery-operations
plan: "06"
subsystem: state-persistence
tags: [github-rest, git-objects, state-branch, cas, content-addressing, tdd]

requires:
  - phase: 05-01
    provides: strict prior-root-linked state root, object and three-database contracts
  - phase: 05-03
    provides: recorded state-branch restore and conflict fixtures
provides:
  - fixed-repository, fixed-ref GitHub state-branch capability
  - canonical state-root/object/database restore verification
  - parent-bound non-force state synchronization with exact post-write reread
affects: [05-07, 05-12, 05-14, discovery-operations, semantic-durability]

tech-stack:
  added: []
  patterns:
    - exact allowlisted Git tree projection before restore authority
    - prospective bundle validation and canary scan before immutable blob writes
    - observed-head commit parent plus force-false ref mutation and full reread

key-files:
  created:
    - src/skillscout/adapters/state_branch.py
  modified:
    - tests/test_state_branch.py

key-decisions:
  - "Bind the client to exactly refs/heads/skillscout-state and expose no general request, PR, reviewer, merge, deletion or arbitrary-ref method."
  - "Treat recursive Git directory entries as valid only when they are the exact structural prefixes required by allowlisted blobs."
  - "Stop on every head, mutation-response, commit, tree or blob reread disagreement; never force, merge, prune or retry as last-writer-wins."

patterns-established:
  - "Remote state authority: canonical root bytes, digest-derived objects and exactly three owner-bound database snapshots must all agree before restore."
  - "State CAS: prevalidate locally, observe the fixed head, create immutable objects, write force=false, then independently reread every committed byte."

requirements-completed: [OPS-02, OPS-03]

coverage:
  - id: D1
    description: "Exact state-branch restore admits only canonical root/object/three-database evidence and distinguishes an absent branch."
    requirement: OPS-02
    verification:
      - kind: integration
        ref: "tests/test_state_branch.py#restore/tree/object/rollback/absent focused suite"
        status: pass
    human_judgment: false
  - id: D2
    description: "State synchronization is parent-bound, non-force, conflict-closed and accepted only after a complete reread."
    requirement: OPS-02
    verification:
      - kind: integration
        ref: "tests/test_state_branch.py#bootstrap/fast-forward/conflict/reread suite"
        status: pass
    human_judgment: false
  - id: D3
    description: "Unexpected paths, modes, directory structure and secret canaries fail before state authority or the first blob write."
    requirement: OPS-03
    verification:
      - kind: unit
        ref: "tests/test_state_branch.py#mutation and prospective-secret matrix"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-27
status: complete
---

# Phase 5 Plan 06: Exact Remote State Restore and Fast-Forward Sync Summary

**Canonical state restore and observed-head Git CAS with force-false mutation, prospective leak rejection and byte-exact independent reread**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-27T14:17:31Z
- **Completed:** 2026-07-27T14:26:26Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added a narrow GitHub Git-data client fixed to one configured repository and `refs/heads/skillscout-state`, preserving the pinned API version, bounded streaming responses, redirect denial, request-ID validation and closed failures.
- Added exact restore verification for canonical root bytes, digest-derived immutable JSON objects, three owner-bound SQLite snapshots, Git modes/paths/sizes and prior-parent facts.
- Added bootstrap and fast-forward synchronization that scans the complete prospective bundle before writes, commits against the observed head, uses `force=False`, and grants success only after rereading the exact ref, commit, tree and blob bytes.

## Task Commits

Each TDD task was committed atomically:

1. **Task 05-06-01 RED: activate exact state restore contract** - `44e871a` (test)
2. **Task 05-06-01 GREEN: verify exact remote state restore** - `6b93266` (feat)
3. **Task 05-06-02 RED: recursive state tree contract** - `e69705e` (test)
4. **Task 05-06-02 GREEN: fast-forward exact state branch** - `78caedf` (feat)

## Files Created/Modified

- `src/skillscout/adapters/state_branch.py` - Fixed state-ref client, strict restore verifier, complete prospective scanner and parent-bound CAS store.
- `tests/test_state_branch.py` - Offline recorded restore, tree, bootstrap, fast-forward, conflict, reread and leak tests.

## Decisions Made

- The state client has named Git object/ref methods only; catalog, PR, reviewer, merge, deletion and general-request capabilities are structurally absent.
- Recursive Git tree directories are checked as exact required structure instead of being silently discarded, preventing unexpected empty subtrees from escaping the allowlist.
- Immutable objects are retained by omission of every delete/prune route; synchronization constructs only the currently authoritative exact tree and never merges SQLite bytes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Admitted required recursive Git directory entries without allowing hidden subtrees**
- **Found during:** Task 05-06-02
- **Issue:** GitHub recursive trees include `040000` directory entries, while rejecting every non-blob would reject valid state trees; blindly ignoring directories would hide unexpected empty subtrees.
- **Fix:** Admit only the exact structural directory prefixes required by the returned allowlisted blobs and reject missing, duplicate or unexpected directories.
- **Files modified:** `src/skillscout/adapters/state_branch.py`, `tests/test_state_branch.py`
- **Verification:** Complete 24-test state-branch suite and Ruff pass.
- **Committed in:** `78caedf`

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** The fix is required for correct GitHub tree handling and strengthens the plan's exact-tree prohibition without broadening scope.

## Issues Encountered

- The historical Phase 1/3 independent acceptance scanners pin the exact pre-Phase-5 set of production `httpx` importers. The planned new adapter therefore produces three broader-suite scanner failures while 1,562 tests pass, 2 skip and 93 remain expected xfails. This cross-plan baseline update is recorded in `deferred-items.md` for the Phase 5 acceptance/map work; Plan 05-06 did not weaken historical guards.

## Known Stubs

None. Optional fields represent closed absent/bootstrap observations or optional Git-reported sizes; no empty/mock data flows into production authority.

## User Setup Required

None - all verification used offline recorded transports and synthetic digest-only state; no live network or credential was used.

## Next Phase Readiness

Plans 05-07, 05-12 and 05-14 can compose the fixed state branch with store-owned exports, rebuild validation and semantic durability receipts. The independent acceptance scanners must add this planned importer in their own acceptance-owned update before the full historical release chain can become green.

## Self-Check: PASSED

- Both planned implementation/test files and this summary exist.
- TDD commits `44e871a`, `6b93266`, `e69705e` and `78caedf` exist.
- `tests/test_state_branch.py`: 24 passed.
- Ruff passes on the adapter and its tests.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-27*
