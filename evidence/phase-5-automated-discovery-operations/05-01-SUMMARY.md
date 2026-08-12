---
phase: 05-automated-discovery-operations
plan: "01"
subsystem: discovery-domain
tags: [pydantic, github-search, content-addressing, sqlite, tdd]

requires:
  - phase: 04-controlled-draft-pr
    provides: strict candidate and publication authority patterns
provides:
  - exact ordered four-query GitHub Repository Search policy
  - literal 100-repository and 20-semantic-candidate ceilings
  - strict content-addressed discovery, audit, reservation, terminal and rebuild contracts
affects: [05-02, 05-03, 05-04, 05-05, 05-06, discovery-operations]

tech-stack:
  added: []
  patterns:
    - strict frozen Pydantic contracts with canonical self-digests
    - numeric repository-ID deduplication authority
    - exact owner-to-database path binding

key-files:
  created:
    - config/discovery-queries-v1.json
    - src/skillscout/domain/discovery.py
    - tests/test_discovery_domain.py
  modified: []

key-decisions:
  - "Keep query text, query ordering and the 100/20 ceilings as code-owned literal policy with no runtime widening seam."
  - "Use numeric repository ID as deduplication authority while retaining owner/name only as bounded provenance."
  - "Represent state as one prior-root-linked canonical root, digest-derived immutable objects and exactly three owner-bound SQLite paths, with no pruning contract."
  - "Quarantine outcome-unknown semantic attempts and make them structurally distinct from confirmed retryable outcomes."

patterns-established:
  - "Self-hash pattern: every durable aggregate excludes only its own digest field from the canonical preimage."
  - "Closed durable projection: external prose, raw headers, errors, credentials and unvalidated paths are absent from domain schemas."

requirements-completed: [DISC-01, DISC-02, DISC-03, OPS-02, OPS-03]

coverage:
  - id: D1
    description: "Exact ordered v1 GitHub Search query policy and stable run authority with immutable 100/20 limits."
    requirement: DISC-01
    verification:
      - kind: unit
        ref: "tests/test_discovery_domain.py#query, budget and authority contract tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Complete trimmed page, rate, repository-ID deduplication, reservation and terminal facts."
    requirement: DISC-03
    verification:
      - kind: unit
        ref: "tests/test_discovery_domain.py#observation, reservation and terminal mutation tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "Content-addressed rebuild projection with exact root/object locators and three owner-bound SQLite databases."
    requirement: OPS-02
    verification:
      - kind: unit
        ref: "tests/test_discovery_domain.py#state root and forbidden-field mutation tests"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-27
status: complete
---

# Phase 5 Plan 01: Discovery Contract and Policy Surface Summary

**Exact four-query discovery authority, literal 100/20 cost ceilings, trimmed audit facts and a prior-root-linked three-database rebuild contract**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-27T12:55:28Z
- **Completed:** 2026-07-27T13:04:21Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Froze the reviewed `github-repository-search-v1` policy as four exact, ordered queries with 25-item round-robin pages and stable canonical authority.
- Added strict numeric repo-ID discovery facts, non-refundable 100/20 reservations and closed business/retry/unknown/integrity terminal states.
- Added immutable digest-derived state objects, complete rebuild projections and exact ownership for pipeline, operations and publication SQLite databases.

## Task Commits

Each TDD task was committed atomically:

1. **Task 05-01-01 RED: discovery authority tests** - `766a4e0` (test)
2. **Task 05-01-01 GREEN: query and budget authority** - `64e681b` (feat)
3. **Task 05-01-02 RED: durability contract tests** - `14c6e44` (test)
4. **Task 05-01-02 GREEN: observations and rebuild facts** - `1d7cc7c` (feat)

## Files Created/Modified

- `config/discovery-queries-v1.json` - Exact reviewed query-set bytes.
- `src/skillscout/domain/discovery.py` - Strict discovery policy, fact, terminal and state contracts.
- `tests/test_discovery_domain.py` - 62 boundary, mutation, sanitization and self-hash tests.

## Decisions Made

- Query text, order, pagination and budgets are literals; runtime input cannot widen them.
- Numeric GitHub repository ID owns deduplication; mutable owner/name remains provenance only.
- Outcome-unknown semantic requests are quarantined and never represented as automatically retryable.
- State root reachability is retained through `prior_root_digest`, but Phase 5 exposes no pruning operation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Bug] Canonical test helper did not recursively project nested strict models**
- **Found during:** Task 05-01-02 GREEN
- **Issue:** The RED helper attempted to hash a nested Pydantic model directly, which standard JSON cannot encode.
- **Fix:** Projected nested models and tuples to their canonical JSON-compatible values before hashing.
- **Files modified:** `tests/test_discovery_domain.py`
- **Verification:** Complete 62-test domain suite passes.
- **Committed in:** `1d7cc7c`

**2. [Rule 1 - Validation Bug] State-object locator length constraint was off by one**
- **Found during:** Task 05-01-02 GREEN
- **Issue:** A redundant fixed string-length bound rejected the correct digest-derived locator before the authoritative equality validator ran.
- **Fix:** Retained a conservative general length cap and made exact digest-derived path equality the sole locator authority.
- **Files modified:** `src/skillscout/domain/discovery.py`
- **Verification:** Exact-path, traversal, swapped-hash and forbidden-field mutations all pass.
- **Committed in:** `1d7cc7c`

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs).
**Impact on plan:** Both fixes were confined to the planned contract/test surface and strengthened exact validation.

## Issues Encountered

None.

## Known Stubs

None. Optional digest defaults are construction-time sentinels that are populated before validation and rejected if absent or inconsistent after validation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The Search adapter, operations ledger and state-branch plans can now import one exact contract vocabulary without inventing query, budget, outcome, path or persistence fields.

## Self-Check: PASSED

- All three planned files exist.
- TDD commits `766a4e0`, `64e681b`, `14c6e44` and `1d7cc7c` exist.
- `tests/test_discovery_domain.py`: 62 passed.
- Ruff passes on the new domain and test files.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-27*
