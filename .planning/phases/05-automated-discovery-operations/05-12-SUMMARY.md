---
phase: 05-automated-discovery-operations
plan: "12"
subsystem: database
tags: [sqlite, content-addressing, state-branch, recovery, integrity]

requires:
  - phase: 05-05
    provides: discovery-only operations ledger with canonical owned facts
  - phase: 05-06
    provides: exact fixed-path state-branch bundle validation and CAS
provides:
  - pipeline-owned canonical Phase 1/3 export and validated rebuild
  - publication-owned canonical attempt/checkpoint/record export and rebuild
  - exact three-database bundle assembly with content-addressed JSON objects
  - pre-restore and post-rebuild cross-store projection equality gates
affects: [05-13, 05-14, state-branch, semantic-durability]

tech-stack:
  added: []
  patterns:
    - store-owned canonical fact replay
    - prospective bundle equality before local mutation
    - fresh owner re-export after rebuild

key-files:
  created: []
  modified:
    - src/skillscout/adapters/state.py
    - src/skillscout/adapters/operations_state.py
    - src/skillscout/adapters/publication_state.py
    - tests/test_state_integrity.py
    - tests/test_operations_state.py
    - tests/test_publication_recovery.py
    - tests/test_state_branch.py

key-decisions:
  - "Each existing store remains the sole owner of its schema, canonical facts, replay, and full-chain verification."
  - "The coordinator binds compact owner envelopes, digest-addressed fact objects, and exactly three fixed database snapshots without private SQL."
  - "Restore validates a prospectively reassembled byte-exact bundle before writes and requires fresh three-store projection equality afterward."

patterns-established:
  - "Owned rebuild: accept an exact valid snapshot only when it agrees with canonical JSON; otherwise rebuild from fully validated owned facts."
  - "Three-store root: bind owner export digests and projections in a content-addressed projection object under the fixed state tree."

requirements-completed: [OPS-02, OPS-03]

coverage:
  - id: D1
    description: "Pipeline and publication stores independently export complete canonical authority and rebuild corrupt snapshots through owner-side validators."
    requirement: OPS-02
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py and tests/test_publication_recovery.py#owned export/rebuild mutation matrix"
        status: pass
    human_judgment: false
  - id: D2
    description: "The remote state bundle contains exactly three fixed owner databases plus digest-derived JSON objects and rejects swapped, partial, or mismatched evidence."
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "tests/test_operations_state.py and tests/test_state_branch.py#three-store bundle and path mutations"
        status: pass
    human_judgment: false
  - id: D3
    description: "Restore grants reuse only after prospective root equality and fresh post-rebuild cross-store projection equality."
    requirement: OPS-02
    verification:
      - kind: integration
        ref: ".tools/uv-0.11.29/bin/uv run --locked pytest -q"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-27
status: complete
---

# Phase 5 Plan 12: Three-Store State Bundle Summary

**Store-owned Phase 1/3, discovery, and publication rebuild authority assembled into one exact content-addressed three-SQLite bundle with fail-closed projection equality**

## Performance

- **Duration:** 20 minutes
- **Started:** 2026-07-27T14:57:27Z
- **Completed:** 2026-07-27T15:17:28Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added strict canonical fact, projection, snapshot, export, restore, and rebuild contracts to `SQLiteStateStore` and `PublicationStateStore`.
- Kept the discovery coordinator schema-owner agnostic while assembling fixed pipeline, operations, and publication snapshots with digest-derived JSON facts and owner envelopes.
- Required byte-exact prospective root reconstruction before restore and fresh three-store export equality after rebuild.
- Proved the implementation with 228 plan tests and a full 1605-pass repository regression.

## Task Commits

Each task was committed atomically:

1. **Task 05-12-01 RED: owned store rebuild contracts** - `dbf347d` (test)
2. **Task 05-12-01 GREEN: canonical owner exports and rebuilds** - `7eacc6d` (feat)
3. **Task 05-12-02 RED: exact three-store bundle contracts** - `89ce9b0` (test)
4. **Task 05-12-02 GREEN: bundle assembly and projection equality** - `cefe52d` (feat)
5. **Task 05-12-02 regression fix: read-only verifier compatibility** - `d492781` (fix)

## Files Created/Modified

- `src/skillscout/adapters/state.py` - Pipeline-owned canonical Phase 1/3 facts, resource evidence, snapshot validation, replay, and rebuild.
- `src/skillscout/adapters/publication_state.py` - Publication attempt/checkpoint/record projection, exact schema verification, replay, and rebuild.
- `src/skillscout/adapters/operations_state.py` - Schema-agnostic three-store envelopes, fixed bundle assembly, validation, restore, and fresh equality checks.
- `tests/test_state_integrity.py` - Pipeline export/rebuild and canonical fact mutation coverage.
- `tests/test_publication_recovery.py` - Publication export/rebuild and mutation coverage.
- `tests/test_operations_state.py` - Three-store round-trip and swapped/partial/tampered bundle coverage.
- `tests/test_state_branch.py` - Fixed-path and coordinator schema-ownership enforcement.

## Decisions Made

- Existing owners expose typed projections rather than raw SQL or copied schemas; `operations_state.py` never replays pipeline or publication tables.
- Content-addressed fact payloads are stored individually, while compact owner envelopes bind their canonical order, store projection, schema fingerprint, database digest, and export digest.
- A structurally valid database that disagrees with its owned JSON is rejected; only invalid snapshot bytes may fall back to canonical fact replay.
- Restore parses and prospectively reconstructs the complete bundle before creating target directories, then reopens all three rebuilt stores and compares the fresh combined projection.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved read-only verifier shell cleanup compatibility**

- **Found during:** Overall full-suite verification
- **Issue:** Closing a descriptor-only Phase 2 verifier assumed the newly used Phase 3 artifact-anchor attribute existed, causing two read-only candidate-source regressions.
- **Fix:** Made cleanup tolerate verifier shells that intentionally expose only the legacy read-only state surface.
- **Files modified:** `src/skillscout/adapters/state.py`
- **Verification:** Two focused candidate-source tests, 281 combined plan/candidate tests, and the full 1605-test regression pass.
- **Committed in:** `d492781`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** The fix preserves the pre-existing read-only query contract without widening the new rebuild or bundle authority.

## Issues Encountered

- The first full regression exposed the read-only verifier cleanup incompatibility above. After the targeted fix, the complete suite passed with 1605 passed, 2 skipped, and 93 expected xfails.

## Known Stubs

None. All new export, rebuild, bundle, validation, and equality paths are wired to durable stores and exercised by tests.

## User Setup Required

None - no external service configuration required.

## Test Evidence

- Plan integration suites: `228 passed`
- Plan suites plus candidate-source regression: `281 passed`
- Full repository suite: `1605 passed, 2 skipped, 93 xfailed`
- Ruff on all modified adapters: passed
- No live network, provider calls, dependency installation, or secret access occurred.

## Next Phase Readiness

Plans 05-13 and 05-14 can consume `assemble_three_store_bundle` and `restore_three_store_bundle` as the owner-preserving durability payload and verification boundary. No blockers remain.

## Self-Check: PASSED

- All seven planned files exist.
- All five task commits are present.
- SUMMARY status is `complete`.
- OPS-02 and OPS-03 are covered by passing integration and full-suite evidence.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-27*
