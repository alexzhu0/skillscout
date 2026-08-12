---
phase: 05-automated-discovery-operations
plan: "04"
subsystem: github-search
tags: [github-rest, httpx, pydantic, pagination, rate-limits, tdd]

requires:
  - phase: 05-automated-discovery-operations
    plan: "01"
    provides: strict reviewed Search policy and page/repository/rate observation contracts
  - phase: 05-automated-discovery-operations
    plan: "02"
    provides: bounded Search fixtures and named strict RED behavior nodes
provides:
  - bounded exact GitHub Repository Search on the existing serial read client
  - strict allowlisted page, repository and complete rate-limit projections
  - fixed-host integer pagination with closed redirect, body, rate and transport failures
affects: [05-07, discovery-application, github-read-client, operations-state]

tech-stack:
  added: []
  patterns:
    - lenient consumed provider models followed by strict self-hashed domain projections
    - exact query-authority revalidation before one fixed Search request
    - raw Link reduction to a validated bounded integer cursor

key-files:
  created: []
  modified:
    - src/skillscout/adapters/github.py
    - tests/test_github_search.py

key-decisions:
  - "Extend the existing GitHubReadClient and keep one serial REMOTE_READ capability rather than introduce a second GitHub client."
  - "Revalidate the complete reviewed query-set authority before constructing the exact q/sort/order/per_page/page request."
  - "Persist only strict self-hashed page, repository and numeric rate observations; discard descriptions, topics, text matches, raw Link values, provider bodies and arbitrary headers."

patterns-established:
  - "Search pagination: validate one next relation against the exact HTTPS host, endpoint, reviewed parameters and next bounded page, then retain only the integer cursor."
  - "Search failures: reject redirects and malformed successful-response facts permanently; classify only 429, exhausted 403 and 5xx/transport failures as closed transient outcomes."

requirements-completed: [DISC-01, DISC-02, DISC-03, OPS-03]

coverage:
  - id: D1
    description: "Exact reviewed Search requests return strict page and repository observations through the existing serial GitHub read client."
    requirement: DISC-01
    verification:
      - kind: integration
        ref: "tests/test_github_search.py#page, duplicate and incomplete projection tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Numeric repository IDs remain stable across duplicates and renames while mutable names stay bounded provenance."
    requirement: DISC-02
    verification:
      - kind: integration
        ref: "tests/test_github_search.py#test_duplicate_and_rename_projection_preserves_stable_numeric_identity"
        status: pass
    human_judgment: false
  - id: D3
    description: "Pagination, request IDs, complete rate facts, body caps, redirects and transport/provider failures are bounded and fail closed."
    requirement: DISC-03
    verification:
      - kind: integration
        ref: "tests/test_github_search.py#hostile, rate, oversized and error matrix"
        status: pass
    human_judgment: false
  - id: D4
    description: "Provider prose, raw error bodies and token canaries never cross the strict Search result or closed diagnostic boundary."
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "tests/test_github_search.py#allowlisted projection and token/provider-body confinement tests"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-07-27
status: complete
---

# Phase 5 Plan 04: Bounded GitHub Repository Search Summary

**Exact reviewed Search requests now produce strict metadata-only observations with fixed-host pagination, complete rate facts and sanitized bounded failures**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-27T13:31:22Z
- **Completed:** 2026-07-27T13:36:39Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Extended the existing serial `GitHubReadClient` with one exact reviewed repository Search operation and no new remote capability or dependency.
- Projected provider responses into strict self-hashed page and repository observations containing only allowlisted metadata, numeric repository IDs, bounded provenance and complete Search rate facts.
- Rejected hostile Link targets, redirects, malformed/oversized responses, incomplete mandatory headers and raw provider failures without an extra request or diagnostic leakage.

## Task Commits

Each task was committed atomically against the RED contract established by Plan 05-02:

1. **Task 05-04-01: Project exact Search pages and candidates** - `8cd7bff` (feat)
2. **Task 05-04-02: Close pagination, rate and resource failures** - `1406211` (feat)

## Files Created/Modified

- `src/skillscout/adapters/github.py` - Exact Search request, lenient raw envelope, strict projection, rate validation, bounded cursor and closed failure handling.
- `tests/test_github_search.py` - Removed only the Plan 05-04 named strict xfails after their production behavior became green.

## Decisions Made

- The caller must supply the strict reviewed `DiscoveryQuerySetV1`; the adapter reconstructs and compares its canonical authority before using any query text.
- Search redirects are always rejected, preserving the exact request endpoint even though legacy repository metadata reads retain their existing bounded same-host redirect behavior.
- A successful Search response must contain one bounded request ID plus all five reconciled Search rate facts; missing, malformed or wrong-resource facts fail permanently.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Canonicalized nested Search rate facts before hashing the page observation**
- **Found during:** Task 05-04-01
- **Issue:** The first GREEN implementation passed a Pydantic rate model directly inside a dictionary to the canonical JSON encoder, which cannot encode nested model values in mappings.
- **Fix:** Projected `SearchRateLimitFactsV1` to its canonical JSON-compatible dictionary for the digest preimage while retaining the strict model in the returned page observation.
- **Files modified:** `src/skillscout/adapters/github.py`
- **Verification:** Happy, multi-page, duplicate, rename, incomplete and legacy adapter tests pass.
- **Committed in:** `8cd7bff`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** The fix was confined to the planned Search projection and aligned the adapter with the already-established domain hashing contract.

## Issues Encountered

- The default `uv` cache path was outside the writable sandbox. All locked commands used the repository-approved `UV_CACHE_DIR=.tools/uv-cache`; no dependency installation or network access occurred.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Verification

- Search plus legacy GitHub adapter: 58 passed.
- Search, legacy adapter and discovery domain regression: 120 passed.
- Ruff: passed for `src/skillscout/adapters/github.py` and `tests/test_github_search.py`.
- No `phase5-wave0-search-adapter-missing` marker remains in `tests/test_github_search.py`.
- No live network, candidate execution, dependency change, secret read or raw provider persistence occurred.

## Next Phase Readiness

The discovery application can now acquire reviewed Search pages through the verified read client and persist only strict metadata observations. Phase 5 budget/state and application plans can consume these facts without gaining arbitrary URL, query or provider-body authority.

## Self-Check: PASSED

- Both planned modified files exist.
- Task commits `8cd7bff` and `1406211` exist.
- All plan-focused tests and Ruff checks pass.
- No tracked file deletion or generated untracked output was introduced.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-27*
