---
phase: 05-automated-discovery-operations
plan: "02"
subsystem: testing
tags: [github-search, httpx, recorded-fixtures, security, tdd]

requires:
  - phase: 05-automated-discovery-operations
    plan: "01"
    provides: strict Search query, page, rate and repository observation contracts
provides:
  - bounded deterministic GitHub repository Search fixture corpus
  - exact request, pagination, numeric-ID deduplication and projection RED contract
  - hostile Link, body, rate, transport and secret-confinement RED matrix
affects: [05-04, github-read-client, discovery-operations]

tech-stack:
  added: []
  patterns:
    - collection-first Wave 0 tests with one strict named xfail reason
    - recorded query-string routes that reject every unrecorded request
    - synthetic error cases layered over bounded base response fixtures

key-files:
  created:
    - tests/fixtures/github_search/page_one.json
    - tests/fixtures/github_search/page_duplicates.json
    - tests/fixtures/github_search/page_incomplete.json
    - tests/fixtures/github_search/error_matrix.json
    - tests/test_github_search.py
  modified:
    - tests/recorded_transport.py

key-decisions:
  - "Represent the future Search result as one strict page observation plus a tuple of strict repository observations; raw provider dictionaries never cross the adapter boundary."
  - "Use one exact strict Wave 0 xfail marker only on production-adapter behavior nodes; fixture, recorder, parsing and numeric-ID decision tests remain ordinary green tests."
  - "Synthesize malformed and oversized bodies from bounded fixture instructions instead of committing megabyte-scale or complete provider payloads."

patterns-established:
  - "Wave 0 RED: collection and local fixture behavior stay green while only the named missing production method strict-xfails."
  - "Pagination authority: route fixtures bind the complete query string while returned evidence retains only a bounded integer cursor."

requirements-completed: [DISC-01, DISC-02, DISC-03, OPS-03]

coverage:
  - id: D1
    description: "Bounded deterministic Search pages freeze exact page, incomplete-result and numeric repository-ID observations."
    requirement: DISC-03
    verification:
      - kind: integration
        ref: "tests/test_github_search.py#page, duplicate and incomplete focused Wave 0 command"
        status: pass
    human_judgment: false
  - id: D2
    description: "Recorded transport enforces the exact fixed-host Search query and rejects every unrecorded page."
    requirement: DISC-01
    verification:
      - kind: unit
        ref: "tests/test_github_search.py#test_page_recorded_transport_requires_exact_query_and_rejects_unrecorded"
        status: pass
    human_judgment: false
  - id: D3
    description: "Hostile pagination, malformed/oversized bodies, rate failures, transport failure and token/prose leakage are frozen as closed adapter behavior."
    requirement: OPS-03
    verification:
      - kind: integration
        ref: "tests/test_github_search.py#hostile, oversized, rate and error focused Wave 0 command"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-07-27
status: complete
---

# Phase 5 Plan 02: Recorded GitHub Search Boundary Summary

**A bounded synthetic Search corpus and 31-node strict Wave 0 contract for exact requests, numeric-ID deduplication, hostile pagination, rate handling and secret-safe failures**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-27T13:08:48Z
- **Completed:** 2026-07-27T13:14:31Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added four compact metadata-only fixture files covering happy pages, within/across-query duplicates, repository rename under one numeric ID, incomplete results, qualifier mismatches and a complete hostile/error matrix.
- Extended the recorded transport loader with deterministic Search cases while preserving exact unrecorded-request assertion failures.
- Added 31 collected Search contract nodes: 5 ordinary fixture/recorder/decision checks pass and 26 named adapter behaviors strict-xfail until Plan 05-04 implements `search_repositories`.

## Task Commits

Each task was committed atomically:

1. **Task 05-02-01: Record bounded Search happy and dedup observations** - `672056e` (test)
2. **Task 05-02-02: Record hostile pagination, caps and rate failures** - `95d6a20` (test)

## Files Created/Modified

- `tests/fixtures/github_search/page_one.json` - Exact first page with a bounded next Link and discarded prose canaries.
- `tests/fixtures/github_search/page_duplicates.json` - Across-page/query duplicate and rename observations keyed by stable numeric IDs.
- `tests/fixtures/github_search/page_incomplete.json` - Partial results plus public/fork/archive qualifier mismatches retained for later filtering.
- `tests/fixtures/github_search/error_matrix.json` - Hostile Link, redirect, body, rate-header and provider-error cases.
- `tests/recorded_transport.py` - Dedicated bounded Search fixture/error-case loader.
- `tests/test_github_search.py` - Collection-safe strict Wave 0 Search adapter specification.

## Decisions Made

- The Search call contract accepts the reviewed query set, stable run-authority digest, query ordinal and page; it returns a strict page observation and strict repository-observation tuple.
- Duplicates and renames are decided solely by numeric repository ID; owner/name remains bounded provenance and first-seen presentation data.
- Raw Link values, descriptions, topics, text matches, provider bodies and authorization data are never part of returned or durable expected objects.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

- `GitHubReadClient.search_repositories` is intentionally absent. The 26 adapter behavior nodes strict-xfail with `phase5-wave0-search-adapter-missing`; Plan 05-04 is the explicit GREEN implementation owner.

## TDD Gate Compliance

- RED gates exist as `672056e` and `95d6a20`.
- No GREEN commit is expected in this Wave 0 plan; Plan 05-04 owns the production implementation and removal of the strict expected failures.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 05-04 can implement the existing serial GitHub client against exact offline request, projection, pagination, rate, resource-cap and sanitization behavior without discovering a new provider boundary.

## Verification

- Collection: 31 tests collected without syntax, import, dependency or fixture errors.
- Task 05-02-01 focus: 4 passed, 4 strict xfailed.
- Task 05-02-02 focus: 1 passed, 23 strict xfailed.
- Complete Search plus legacy adapter regression: 32 passed, 26 strict xfailed.
- Ruff passed for `tests/recorded_transport.py` and `tests/test_github_search.py`.

## Self-Check: PASSED

- All six planned files exist.
- Task commits `672056e` and `95d6a20` exist.
- Every expected failure uses the exact reason `phase5-wave0-search-adapter-missing`.
- No unexpected deletion, untracked generated output, new dependency, network call, secret read or production authority change occurred.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-27*
