# Phase 05 Deferred Items

## Pre-existing acceptance scanner drift

- **Found during:** Plan 05-05 overall regression verification
- **Scope:** Out of scope for Plan 05-05; no owned file is involved.
- **Observed:** The full suite reports three failures because
  `tests/test_phase1_gap_closure.py` and the Phase 3 acceptance inspector reject
  the `urllib.parse` import added to `src/skillscout/adapters/github.py` by
  completed Plan 05-04.
- **Evidence:** 1,538 passed, 2 skipped, 108 expected xfailed, 3 failed.
- **Required follow-up:** Reconcile the older capability scanners with the
  reviewed bounded GitHub Search URL parsing boundary, or replace that import
  within the owning plan. Do not weaken the scanners without a fresh authority
  review.
