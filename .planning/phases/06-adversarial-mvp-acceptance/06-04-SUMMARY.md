---
phase: 06-adversarial-mvp-acceptance
plan: "04"
subsystem: acceptance-evidence
tags: [pydantic, sqlite, canonical-json, content-addressing, tdd]

requires:
  - phase: 06-01
    provides: Frozen Phase 6 domain, state, mutation, and rebuild RED contracts
  - phase: 06-03
    provides: Closed semantic-provider identities consumed by later acceptance evidence
provides:
  - Strict self-digested benchmark, scenario, isolation, replay/update, attestation, gate, and verdict models
  - Immutable fifteen-kind acceptance fact registry in the existing operations owner
  - Distinct pre-effect intent and post-effect completion projections
  - Canonical acceptance export, rebuild, and three-store restore validation
affects: [06-05, 06-06, 06-07, 06-10, 06-11, 06-12, 06-13, live-acceptance]

tech-stack:
  added: []
  patterns:
    - StrictFrozenModel canonical self-digest contracts
    - One discriminator table with immutable fact-kind to model registry
    - Canonical post-parse equality for strict JSON tuple reconstruction

key-files:
  created:
    - src/skillscout/domain/acceptance.py
  modified:
    - src/skillscout/adapters/operations_state.py
    - tests/test_acceptance_domain.py
    - tests/test_operations_state.py

key-decisions:
  - "Persist every Phase 6 acceptance fact in one bounded operations_acceptance_facts table; do not create a fourth state owner."
  - "Project replay and changed-source intent separately from their post-publication completion facts so both immutable scopes coexist."
  - "Revalidate canonical JSON through the exact model registry and require post-parse byte equality before any fact receives authority."
  - "Restore a valid owned SQLite image byte-for-byte after JSON/projection agreement; rebuild corrupt database bytes only from canonical facts."

patterns-established:
  - "Acceptance fact admission: exact kind, exact model type, exact schema, canonical bytes, self-digest, run binding, natural identity, then one snapshot transaction."
  - "Acceptance dependency binding: benchmark requires nomination, offline run requires hosted capability, completions require their exact intent, cleanup requires Gate B4, and report root requires the exact gate set."

requirements-completed: [TEST-01, TEST-02, TEST-03, TEST-04]

coverage:
  - id: D1
    description: Strict immutable acceptance vocabulary enforces benchmark distribution, terminal taxonomy, hard gates, isolation, replay/update, human review, cleanup, and advice-only calibration.
    requirement: TEST-01
    verification:
      - kind: unit
        ref: "tests/test_acceptance_domain.py (68 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: Hosted-isolation capability and offline adversarial run bind the exact workflow, source, hosted run attempt, denial mechanism, scenario set, and zero-effect counters.
    requirement: TEST-02
    verification:
      - kind: integration
        ref: "tests/test_acceptance_domain.py tests/test_operations_state.py (109 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: Replay/update intent and completion facts coexist under distinct natural identities with exact prior-intent and lineage bindings.
    requirement: TEST-03
    verification:
      - kind: integration
        ref: "tests/test_operations_state.py#test_acceptance_intent_and_completion_coexist_idempotently"
        status: pass
    human_judgment: false
  - id: D4
    description: All fifteen redacted acceptance fact kinds export, revalidate, rebuild, and restore through the existing operations owner and three-store bundle.
    requirement: TEST-04
    verification:
      - kind: integration
        ref: "tests/test_operations_state.py (41 passed)"
        status: pass
      - kind: other
        ref: "ruff check src/skillscout/domain/acceptance.py src/skillscout/adapters/operations_state.py"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-07-29
status: complete
---

# Phase 6 Plan 04: Canonical Acceptance Evidence Domain Summary

**Strict self-digested acceptance contracts now persist through one redacted operations-owned fact table with exact intent/completion separation and content-addressed rebuild**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-29T07:26:26Z
- **Completed:** 2026-07-29T07:44:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented the complete strict Phase 6 vocabulary for fixed benchmark nomination and human lock, scenario outcomes, hosted isolation, offline adversarial execution, replay/update intent and completion, Gate B4, human review, cleanup, reviewer calibration, hard gates, evidence roots, and release verdicts.
- Added one closed `operations_acceptance_facts` table and immutable fifteen-kind model registry without duplicating pipeline/publication schemas or creating a fourth durable owner.
- Preserved pre-publication intent separately from post-effect completion, with exact natural identities, idempotent exact duplicates, conflicting duplicate rejection, and prior-intent/capability/cleanup/root dependency checks.
- Extended operations-owned projections, state objects, export envelopes, JSON rebuild, valid-database restore, and three-store restore so acceptance facts regain authority only after typed canonical revalidation.
- Kept all durable facts redacted: raw corpus, response body, logs, fixture prose, authorization, token, credential, private-key, home/repository scan, and unrestricted-path keys are rejected recursively.

## Task Commits

Each TDD task was committed atomically:

1. **Task 06-04-01 GREEN: strict acceptance evidence domain** - `17c7a24` (feat; RED inherited from 06-01)
2. **Task 06-04-02 RED: acceptance state contracts** - `1857c75` (test)
3. **Task 06-04-02 GREEN: canonical operations persistence** - `4e6f88d` (feat)

## Files Created/Modified

- `src/skillscout/domain/acceptance.py` - Defines strict acceptance models, enums, self-digests, closed terminal taxonomy, exact hard gates, and non-waivable release verdict semantics.
- `src/skillscout/adapters/operations_state.py` - Owns the shared acceptance table, immutable registry, typed APIs, dependency validation, projections, export, rebuild, and three-store restore.
- `tests/test_acceptance_domain.py` - Freezes exact fields, invalid combinations, redaction boundary, hard-gate semantics, and verdict behavior.
- `tests/test_operations_state.py` - Covers registry immutability, intent/completion coexistence, natural-identity conflicts, capability references, and exact owned rebuild.

## Decisions Made

- Acceptance persistence remains inside `OperationsStateStore`; the single shared table is represented once in `_FACT_TABLES` and uses its row discriminator for canonical ordering.
- `OperationsStateProjectionV1` retains the existing discovery digest surface while adding separate tuples for replay intent, changed-source intent, replay completion, changed-source Draft-update completion, and all other acceptance kinds.
- JSON reconstruction permits only JSON-native tuple arrays and then demands exact canonical equality after typed parsing; coercive drift cannot survive the equality check.
- Reviewer calibration is persisted as advice-only evidence and is absent from the hard-gate registry, so it cannot grant release authority.
- The failed hosted run `30430010273` remains a blocker; this plan defines and persists the required isolation contracts but does not claim hosted isolation evidence.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The unfiltered repository suite completed with `2033 passed, 65 skipped, 9 failed`. The nine failures are the exact later-wave Phase 6 RED contracts for six application dependency types plus repository, adversarial, and source-execution verifiers. They are recorded in `deferred-items.md` and were not implemented or reclassified by this plan.
- During GREEN iteration, strict Pydantic parsing exposed JSON arrays as the wire representation of frozen tuple fields. The operations boundary now permits that JSON-native representation only when typed post-parse canonical bytes remain exact.

## Authentication Gates

None.

## Known Stubs

None. The scan found only intentional self-digest defaults, optional prior-root values, and local accumulator collections; no placeholder or unwired runtime data source was introduced.

## User Setup Required

None - no dependency, credential, endpoint, or external service configuration was added.

## Next Phase Readiness

- Plans 06-05 onward can emit every named acceptance fact through `record_acceptance_fact` and recover it through `acceptance_snapshot` or canonical state rebuild.
- Plan 06-06 can consume the exact hosted-capability/offline-run kinds, but must not credit isolation until a new successful reviewed hosted run replaces the failed `30430010273` evidence.
- Plans 06-10/12 can bind cleanup and report roots to the exact Gate B4 and gate-result facts without inventing free-form evidence.

## Self-Check: PASSED

- All four plan code/test files and `06-04-SUMMARY.md` exist.
- Task commits `17c7a24`, `1857c75`, and `4e6f88d` exist in Git history.
- The complete plan-scoped domain and operations suites passed with 109 tests.
- The full operations regression passed with 41 tests, including existing discovery and three-store behavior.
- Ruff check passed for the acceptance domain and operations adapter.
- Stub and threat-surface scans found no untracked placeholder or unmodeled security surface.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-07-29*
