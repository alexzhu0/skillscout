---
phase: 05-automated-discovery-operations
plan: "08"
subsystem: operations
tags: [discovery, cli, sqlite, state-branch, publication, security]

requires:
  - phase: 05-07
    provides: Durable discovery facts, three-store state publication, and recovery primitives
provides:
  - Strict lazy discovery composition with no publication authority
  - Separate discover and protected publish-discovered CLI entry points
  - Exact workflow-level resume state and exact eligible-candidate handoff proof
  - Exact-commit three-store rebuild and local Phase 4 re-admission before token minting
affects: [05-09, 05-10, phase-6-adversarial-acceptance, operations, publication]

tech-stack:
  added: []
  patterns:
    - Late-bound credential factories after deterministic authority validation
    - Workflow-granular durable terminals with typed run snapshots
    - Exact-state handoff re-admission before protected authority acquisition

key-files:
  created: []
  modified:
    - src/skillscout/bootstrap.py
    - src/skillscout/cli.py
    - src/skillscout/application/discovery.py
    - src/skillscout/adapters/operations_state.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/domain/discovery.py
    - tests/test_discovery_application.py
    - tests/test_discovery_publication_handoff.py
    - tests/test_operations_state.py

key-decisions:
  - "Discovery and protected publication remain separate authority zones; discovery cannot resolve catalog credentials or construct publication objects."
  - "Operations run identity is distinct from semantic execution run identity and is carried explicitly through durability transitions."
  - "Protected publication accepts only the exact eligible set proven by workflow terminal facts from the named discovery run and exact state commit."
  - "Resume reconstructs typed pages, candidates, reservations, workflow terminals, candidate terminals, and summaries instead of replaying completed prefixes."

patterns-established:
  - "Validate deterministic configuration before any credential, database, or network factory is resolved."
  - "Persist each workflow terminal before the aggregate candidate terminal so partial sibling outcomes remain auditable and resumable."
  - "Mint protected credentials only after exact state reread, three-store verification, artifact verification, and complete local re-admission."

requirements-completed: [DISC-01, DISC-02, DISC-03, OPS-02, OPS-03]

coverage:
  - id: D1
    description: "Strict lazy discovery composition validates authority before credentials and exposes no publication capability."
    requirement: "OPS-03"
    verification:
      - kind: integration
        ref: "tests/test_discovery_security.py and tests/test_discovery_application.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "The installed CLI separates bounded discovery from protected publication."
    requirement: "DISC-01"
    verification:
      - kind: integration
        ref: "tests/test_cli_security.py and tests/test_discovery_publication_handoff.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Discovery resumes from exact typed operations facts and preserves workflow-level outcomes."
    requirement: "OPS-02"
    verification:
      - kind: integration
        ref: "tests/test_operations_state.py and tests/test_discovery_application.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Protected publication proves the exact persisted eligible set and re-admits artifacts before token minting."
    requirement: "DISC-03"
    verification:
      - kind: integration
        ref: "tests/test_discovery_publication_handoff.py and tests/test_publication_security.py"
        status: pass
    human_judgment: false

duration: 56min
completed: 2026-07-28
status: complete
---

# Phase 5 Plan 08: Strict Discovery Entrypoints Summary

**Closed discovery and exact-commit protected publication with workflow-granular recovery, local re-admission, and credentials resolved only after deterministic proof**

## Performance

- **Duration:** 56 min
- **Started:** 2026-07-27T16:06:00Z
- **Completed:** 2026-07-27T17:02:23Z
- **Tasks:** 2
- **Files modified:** 20

## Accomplishments

- Added strict, lazy discovery composition and a bounded `discover` command that ends after Phase 3 without catalog authority.
- Added a separate `publish-discovered` path that rebuilds the exact state commit, verifies the exact eligible set, locally re-derives every admission, and only then obtains the catalog token.
- Closed restart and partial-progress gaps with typed operations snapshots, workflow-level terminal facts, pre-extractor reservation durability, prefix resume, fatal-stop semantics, and sibling quarantine continuation.
- Verified the repository with `1735 passed, 2 skipped, 5 xfailed` and a clean Ruff run.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build strict lazy discovery composition**
   - `fa2c1bc` — RED strict discovery bootstrap contracts
   - `67e556b` — GREEN strict lazy discovery composition
   - `0357e05` — RED semantic workflow attempt identity
   - `d1343b2` — GREEN isolated semantic workflow attempts
   - `076306a` — RED durable pre-extractor reservation
   - `498b577` — GREEN pre-extractor reservation guard
2. **Task 2: Add closed discovery and protected publication entry points**
   - `9c541f2` — RED separated entrypoint contracts
   - `95eb3bb` — GREEN separate discovery and protected publication entrypoints
   - `badc21a` — concrete discovery operations composition
   - `4c24353` — RED audited integration failure coverage
   - `b4aff11` — GREEN restart and exact-handoff authority closure
   - `f8200a0` — strict rebuild projection fixture coverage

## Files Created/Modified

- `src/skillscout/bootstrap.py` — strict discovery composition, lazy Phase 2/3 dependencies, exact-state reader, protected admission derivation, and publication ordering.
- `src/skillscout/cli.py` — closed `discover` and `publish-discovered` commands with sanitized bounded output.
- `src/skillscout/application/discovery.py` — real coordinator, typed resume, workflow terminal persistence, bounded handoff, and fatal/degraded run handling.
- `src/skillscout/adapters/operations_state.py` — exact workflow facts, typed run snapshots, schema migration, and rebuild projection support.
- `src/skillscout/application/pipeline.py` — explicit operations run identity and durability hooks before extraction.
- `src/skillscout/application/ports.py` and `src/skillscout/application/processors.py` — narrow durability receipt and reservation contracts.
- `src/skillscout/domain/discovery.py` and `src/skillscout/adapters/state_branch.py` — workflow terminal projection identity and state verification.
- `tests/` discovery, operations, semantic durability, pipeline resume, CLI, state-branch, and publication suites — strict TDD and integration coverage.

## Decisions Made

- Kept the public discovery dependency carrier structurally incapable of receiving Phase 4 or catalog authority.
- Bound semantic attempt durability to both the semantic execution ID and the separate discovery operations run ID.
- Made workflow terminal facts the canonical source for eligible-set reconstruction; candidate aggregates alone are insufficient.
- Treated unknown sibling workflows as quarantined and continuable, while integrity/permanent failures stop the run after one fatal terminal.
- Persisted over-budget observations as explicit `budget_excluded` facts so resumed search pages remain exact and non-replayable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced the Phase 05-07 fake coordinator seam**
- **Found during:** Task 2
- **Issue:** The installed discovery composition could not complete a real Phase 2 → Phase 3 run because the inherited coordinator seam always failed.
- **Fix:** Composed the existing production extraction, qualification, generation, validation, review, and durability adapters behind lazy factories.
- **Files modified:** `src/skillscout/bootstrap.py`, `src/skillscout/application/discovery.py`
- **Verification:** Discovery application, pipeline resume, semantic durability, and full repository suites.
- **Committed in:** `badc21a`

**2. [Rule 2 - Critical functionality] Added pre-extractor semantic reservation durability**
- **Found during:** Task 1 integration
- **Issue:** A semantic attempt could reach extraction before its non-refundable attempt identity was durably reserved.
- **Fix:** Added an explicit reservation receipt/hook and required the concrete Phase 2 composition to invoke it before Extractor construction.
- **Files modified:** `src/skillscout/application/pipeline.py`, `src/skillscout/application/ports.py`, `src/skillscout/application/processors.py`, `src/skillscout/bootstrap.py`
- **Verification:** `tests/test_pipeline_resume.py`, `tests/test_semantic_durability.py`, and full suite.
- **Committed in:** `498b577`

**3. [Rule 1 - Bug] Separated operations and semantic execution run identities**
- **Found during:** Post-task integration audit
- **Issue:** The semantic durability guard queried operations reservations using the Phase 2/3 execution run ID, while reservations were keyed by discovery run ID.
- **Fix:** Added explicit `operations_run_id` propagation and narrowed the accepted durability barrier to the required confirmation protocol.
- **Files modified:** `src/skillscout/application/pipeline.py`, `src/skillscout/bootstrap.py`
- **Verification:** `tests/test_semantic_durability.py`, focused audit suite, and full suite.
- **Committed in:** `b4aff11`

**4. [Rule 2 - Critical functionality] Added exact workflow resume and eligible-set authority**
- **Found during:** Post-task integration audit
- **Issue:** Aggregate candidate terminals could not prove which workflow produced an artifact, and restart could replay completed search/candidate prefixes.
- **Fix:** Added workflow terminal facts, typed complete run snapshots, exact prefix resume, exact completed-run reconstruction, and protected handoff equality against the persisted workflow-level eligible set.
- **Files modified:** `src/skillscout/adapters/operations_state.py`, `src/skillscout/application/discovery.py`, `src/skillscout/bootstrap.py`, `src/skillscout/domain/discovery.py`
- **Verification:** `tests/test_operations_state.py`, `tests/test_discovery_application.py`, `tests/test_discovery_publication_handoff.py`, and full suite.
- **Committed in:** `b4aff11`

**5. [Rule 1 - Bug] Closed lazy dependency, fatal-stop, sibling-quarantine, and page-cap edge cases**
- **Found during:** Post-task integration audit
- **Issue:** Completed lookup could construct unnecessary protected dependencies, deterministic rejects could require semantic credentials, fatal outcomes could continue, unknown siblings could suppress later siblings, and a mid-page cap could leave an invalid replay boundary.
- **Fix:** Deferred all protected dependency construction, allowed deterministic upstream rejection without semantic factories, stopped on the first fatal aggregate, continued after isolated unknown siblings, and persisted excluded page items explicitly.
- **Files modified:** `src/skillscout/bootstrap.py`, `src/skillscout/application/discovery.py`, `src/skillscout/adapters/operations_state.py`
- **Verification:** Focused audit suite, full suite, and Ruff.
- **Committed in:** `b4aff11`

**6. [Rule 3 - Blocking] Updated strict state projection fixtures**
- **Found during:** Overall verification
- **Issue:** Existing strict fixture projections omitted the new workflow terminal digest vector.
- **Fix:** Added the field and recalculated canonical projection/root identities.
- **Files modified:** `tests/test_discovery_domain.py`, `tests/test_state_branch.py`, `tests/fixtures/state_branch/valid_state.json`
- **Verification:** Full suite.
- **Committed in:** `f8200a0`

---

**Total deviations:** 6 auto-fixed (2 Rule 1, 2 Rule 2, 2 Rule 3)
**Impact on plan:** All deviations were required to make the planned entrypoints correct, resumable, auditable, and authority-safe; no new product surface was added.

## Issues Encountered

- A test initially wrote its default operations SQLite state under the repository root. The generated `state/` directory was moved intact to `/tmp/skillscout-test-state-05-08-20260728`, and the test now changes into its isolated temporary directory.
- The first full-suite verification exposed stale strict projection fixtures; they were updated and the complete suite then passed.

## Known Stubs

None.

## User Setup Required

None - no external service configuration or credential inspection was performed.

## Next Phase Readiness

- Phase 05-09 and Phase 05-10 can consume a bounded exact discovery handoff and rely on workflow-level recovery facts.
- Phase 6 adversarial acceptance can probe the explicit discovery/publication authority boundary and exact-state mutation denials.
- No blocker remains for this plan.

## Self-Check: PASSED

All listed key files and all 12 task commits were verified, and the coverage metadata classified successfully with all four deliverables automatically covered.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-28*
