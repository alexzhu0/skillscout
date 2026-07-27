---
phase: 05-automated-discovery-operations
plan: "05"
subsystem: operations-state
tags: [sqlite, canonical-json, content-addressing, recovery, budgets, tdd]

requires:
  - phase: 05-automated-discovery-operations
    plan: "01"
    provides: strict discovery authority, reservation, terminal and rebuild contracts
  - phase: 05-automated-discovery-operations
    plan: "03"
    provides: named Wave-0 operations-state RED contracts and bounded state fixtures
provides:
  - descriptor-anchored exact-schema discovery operations ledger
  - atomic non-refundable 100-candidate and 20-semantic reservations
  - canonical discovery-owned JSON export and validated SQLite rebuild authority
  - outcome-unknown semantic attempt quarantine with no automatic re-entry
affects: [05-06, 05-07, 05-12, 05-14, state-branch, discovery-application]

tech-stack:
  added: []
  patterns:
    - retained flock plus private in-memory SQLite serialization
    - complete content-addressed owned facts with exact projection equality
    - rebuild through the owning store's schema and semantic validators

key-files:
  created:
    - src/skillscout/adapters/operations_state.py
    - .planning/phases/05-automated-discovery-operations/deferred-items.md
  modified:
    - tests/test_operations_state.py

key-decisions:
  - "Make unique contiguous reservation rows, not mutable counters, the sole 100/20 budget authority."
  - "Treat outcome-unknown semantic attempts as consumed and terminally non-replayable; only confirmed-retryable attempts may advance automatically."
  - "Keep complete canonical operations-owned facts authoritative and treat the SQLite snapshot as a verified disposable query index."
  - "Reject a valid SQLite snapshot that disagrees with its digest or JSON projection, while allowing corrupt or absent bytes to rebuild only from fully validated owned facts."

patterns-established:
  - "Operations snapshot transaction: clone durable bytes into private memory, BEGIN IMMEDIATE, validate the complete candidate, serialize, fsync/rename/fsync, then promote."
  - "Owned rebuild: validate canonical fact order/digests/projection, replay exact allowlisted rows into the sole operations schema, fully re-export, then atomically replace."

requirements-completed: [DISC-02, DISC-03, OPS-02, OPS-03]

coverage:
  - id: D1
    description: "Discovery and semantic candidate reservations are unique, contiguous, atomic, durable and never refunded."
    requirement: DISC-02
    verification:
      - kind: integration
        ref: "tests/test_operations_state.py#reservation, budget, ordinal and refund tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Ordered Search pages, candidate observations, attempts, terminals and run health remain exact discovery-owned query state."
    requirement: DISC-03
    verification:
      - kind: integration
        ref: "tests/test_operations_state.py#test_complete_typed_discovery_chain_round_trips_through_owned_json"
        status: pass
    human_judgment: false
  - id: D3
    description: "Complete canonical JSON facts rebuild missing or corrupt operations SQLite and reject ambiguity, disagreement or tampering."
    requirement: OPS-02
    verification:
      - kind: integration
        ref: "tests/test_operations_state.py#owned export, corrupt rebuild and mutation tests"
        status: pass
    human_judgment: false
  - id: D4
    description: "Operations persistence retains only closed authority, digest, bounded telemetry and locator facts with no raw provider/source or secret surface."
    requirement: OPS-03
    verification:
      - kind: unit
        ref: "tests/test_operations_state.py#schema ownership and canonical fact tests"
        status: pass
    human_judgment: false

duration: 16min
completed: 2026-07-27
status: complete
---

# Phase 5 Plan 05: Durable Operations Ledger and Rebuild Summary

**A private exact-schema SQLite ledger now owns non-refundable discovery budgets and can be reconstructed only from complete canonical discovery JSON facts**

## Performance

- **Duration:** 16 min
- **Started:** 2026-07-27T13:39:57Z
- **Completed:** 2026-07-27T13:56:01Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added a dedicated descriptor-anchored `OperationsStateStore` with a retained exclusive lock, exact schema fingerprint, foreign keys, full integrity checks and snapshot-replaced in-memory SQLite.
- Made unique contiguous reservation rows the sole 100/20 budget authority, retained them across every terminal class, and prevented outcome-unknown semantic attempts from entering another automatic request.
- Added complete content-addressed owned-fact export, strict projection equality, valid-database disagreement rejection, and fresh private rebuild from canonical JSON when SQLite bytes are missing or corrupt.

## Task Commits

Each TDD task was committed with separate RED and GREEN gates:

1. **Task 05-05-01 RED: reservation ledger contracts** - `19bbbf2` (test)
2. **Task 05-05-01 GREEN: exact schema and non-refundable reservations** - `52f36bc` (feat)
3. **Task 05-05-02 RED: owned export and rebuild contracts** - `8a76831` (test)
4. **Task 05-05-02 GREEN: canonical export, integrity and rebuild** - `0b7248f` (feat)

## Files Created/Modified

- `src/skillscout/adapters/operations_state.py` - Discovery-only schema, durable snapshot transactions, reservations, semantic transitions, terminals, summaries, canonical export, restore and JSON rebuild.
- `tests/test_operations_state.py` - Ordinary GREEN budget, concurrency, non-refund, tamper, killed-writer, complete typed-chain and rebuild tests.
- `.planning/phases/05-automated-discovery-operations/deferred-items.md` - Out-of-scope older acceptance-scanner drift found by the full regression run.

## Decisions Made

- Reservation allocation uses a unique `(run_id, repository_id)` row plus a unique contiguous `(run_id, ordinal)` in the same `BEGIN IMMEDIATE`; no stored counter or refund surface exists.
- The operations database is never opened by operator pathname. SQLite receives only `:memory:` and descriptor-admitted bytes are serialized under the retained store lock.
- A valid SQLite image must match its declared digest and exact JSON facts/projection. Only bytes that are absent or structurally invalid may be ignored in favor of the independently valid complete JSON authority.
- Owned facts contain only allowlisted row columns plus already-validated canonical domain JSON. They exclude raw source, provider bodies, headers, environment values, credentials, arbitrary errors and operator paths.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Made the Wave-0 boundary test prove contiguous allocation**
- **Found during:** Task 05-05-01
- **Issue:** The original strict-xfail inserted only ordinal 100 or 20 into an empty run, which could not prove contiguous ledger allocation and conflicted with the plan's no-gap requirement.
- **Fix:** Allocated every ordinal from 1 through the exact ceiling, asserted the complete sequence, then denied 101/21 without changing the durable count.
- **Files modified:** `tests/test_operations_state.py`
- **Verification:** The focused reservation gate passes 17 tests, including both exact ceilings.
- **Committed in:** `19bbbf2`, completed by `52f36bc`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 test bug).
**Impact on plan:** The correction strengthened the planned acceptance evidence without changing product scope or policy.

## Issues Encountered

- The repository-approved `UV_CACHE_DIR=.tools/uv-cache` was required because the default cache is outside the writable sandbox. No dependency installation or network access occurred.
- The full regression suite found three out-of-scope failures in older Phase 1/3 capability scanners that reject Plan 05-04's committed `urllib.parse` import in `adapters/github.py`. The result was 1,538 passed, 2 skipped, 108 expected xfailed and 3 failed. This is recorded in `deferred-items.md`; no prior-plan file was changed.

## Known Stubs

None.

## Authentication Gates

None.

## Threat Flags

None. The new local SQLite/filesystem trust surface and rebuild authority are the explicit T-05-14 through T-05-17 scope of this plan; no new network, authentication, schema-owner or external execution surface was introduced.

## User Setup Required

None - no external service configuration required.

## Verification

- Task 1 reservation gate: 17 passed, 12 deselected.
- Complete operations-state suite: 29 passed with no operations-store xfails.
- Ruff: passed for `src/skillscout/adapters/operations_state.py` and `tests/test_operations_state.py`.
- Full repository regression: 1,538 passed, 2 skipped, 108 expected xfailed; three pre-existing scanner-drift failures deferred as out of scope.
- No live network, secret read, dependency change, candidate execution, active SQLite copy, WAL/journal authority or foreign store schema duplication occurred.

## Next Phase Readiness

Plans 05-06, 05-07, 05-12 and 05-14 can consume the operations store's owned export/rebuild and reservation seams. The older Phase 1/3 import-capability scanners should be reconciled with Plan 05-04 before the final Phase 5 release chain is expected to pass.

## Self-Check: PASSED

- Both planned task files, the summary and the deferred-item record exist.
- TDD commits `19bbbf2`, `52f36bc`, `8a76831` and `0b7248f` exist.
- The complete 29-test operations suite and Ruff verification pass after the final task commit.
- No tracked file deletion or generated untracked runtime output was introduced.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-27*
