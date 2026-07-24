---
phase: 04-controlled-draft-pr
plan: 05
subsystem: publication-recovery
tags: [sqlite, checkpoints, reconciliation, draft-pr, recovery]
requires:
  - phase: 04-controlled-draft-pr
    provides: closed GitHub publication capability and publication identities
provides:
  - isolated durable publication attempt/checkpoint ledger
  - reconcile-first exact remote ownership gate
  - restart-safe Draft publication cascade with reviewer evidence guards
affects: [04-06, 04-09, controlled-publishing]
tech-stack:
  added: []
  patterns: [canonical checkpoint chain, remote-truth reconstruction, non-force ref updates]
key-files:
  created: [src/skillscout/adapters/publication_state.py, src/skillscout/application/publication.py]
  modified: [src/skillscout/adapters/github_publish.py, tests/test_publication_recovery.py]
key-decisions:
  - "Local terminal records remain advisory until catalog, ref, Draft marker, lineage, tree, and reviewer evidence are revalidated remotely."
  - "Recovered PRs never request reviewers again: each configured individual must be currently requested or have completed-review evidence."
  - "Owned-tree replacement derives null-SHA deletions exclusively from the observed owned subtree."
metrics:
  tasks: 3
  files: 4
status: complete
---

# Phase 04 Plan 05: Durable Publication Recovery Summary

**A canonical SQLite publication ledger and reconcile-first Draft cascade that recovers only exact machine-owned remote lineage without force updates or duplicate reviewer notifications.**

## Accomplishments

- Added a dedicated private, snapshot-replaced SQLite store for canonical publication intents, hash-linked checkpoints, and terminal records; uncertain persistence poisons the store.
- Added an admission-first application boundary that rechecks catalog identity, base, machine ref, Draft marker, parent lineage, owned tree, and individual reviewer evidence before writing.
- Added the ordered blob/tree/commit/non-force-ref/Draft/reviewer cascade and recovery fixtures, including stale owned-file deletion and state corruption coverage.

## Task Commits

1. **Persist canonical publication attempts and checkpoints** — `c48ad26`
2. **Reconcile exact remote ownership before mutation** — `166bc94`
3. **Execute and recover the atomic Draft publication cascade** — `402df0c`

## Verification

- `.tools/uv-0.11.29/bin/uv run --cache-dir /private/tmp/skillscout-uv-cache --locked pytest -q tests/test_publication_recovery.py` — 38 passed.
- `.tools/uv-0.11.29/bin/uv run --cache-dir /private/tmp/skillscout-uv-cache --locked pytest -q tests/test_publication_security.py tests/test_github_publish_adapter.py` — 26 passed, 1 skipped (workflow owned by a later plan).
- `git diff --check` — passed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing capability] Added the closed default-branch ref observation and owned-subtree filtering.**
- **Found during:** Task 2
- **Issue:** The prior adapter could only read the machine ref and rejected complete trees containing catalog files outside the owned subtree, preventing safe base-lineage verification and stale-file reconciliation.
- **Fix:** Added a construction-bound base-ref read and filtered unrelated tree entries while retaining strict validation for owned entries.
- **Files modified:** `src/skillscout/adapters/github_publish.py`
- **Commit:** `166bc94`

**2. [Rule 1 - Bug] Preserved the initial in-memory SQLite connection during first snapshot persistence.**
- **Found during:** Task 3 recovery tests
- **Issue:** Initial snapshot replacement closed the connection it had just installed.
- **Fix:** Close only the superseded connection.
- **Files modified:** `src/skillscout/adapters/publication_state.py`
- **Commit:** `402df0c`

## Known Stubs

None.

## Self-Check: PASSED

- `src/skillscout/adapters/publication_state.py` and `src/skillscout/application/publication.py` exist.
- Task commits `c48ad26`, `166bc94`, and `402df0c` exist.
- The pre-existing orchestrator-owned `.planning/STATE.md` remains unstaged and was not modified by this plan.
