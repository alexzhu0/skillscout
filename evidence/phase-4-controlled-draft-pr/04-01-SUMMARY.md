---
phase: 04-controlled-draft-pr
plan: 01
subsystem: publication-contracts
tags: [pytest, tdd, publication, security, draft-pr]
requires: [phase-03-candidate-contracts]
provides: [publication-admission-specification, publication-negative-capability-specification]
affects: [04-03, 04-04, 04-06, 04-09]
tech_stack:
  added: []
  patterns: [strict-frozen-contracts, deferred-import-wave-zero-tests, ast-allowlists]
key_files:
  created:
    - tests/test_publication_domain.py
    - tests/test_publication_security.py
  modified: []
decisions:
  - "Wave 0 tests defer publication imports until execution so collection stays valid before production modules exist."
  - "Publication safety is constrained with positive AST and route/method allowlists instead of broad negative text matching."
metrics:
  tests_collected: 24
status: complete
---

# Phase 04 Plan 01: Controlled Draft PR contract summary

Wave 0 establishes executable, offline contracts for Phase 3 candidate admission, deterministic Draft PR evidence, marker recovery, and the publisher's forbidden capability boundary.

## Completed Tasks

1. Added `tests/test_publication_domain.py` with 18 collectable cases covering candidate-only evidence, explicit catalog/reviewer authority, deterministic intent/body rendering, zero-call rejection seams, and stable-marker/revision recovery.
2. Added `tests/test_publication_security.py` with 6 collectable cases covering closed publisher operations, route/method allowlists, default-branch rejection, remote-write scope isolation, secret canaries, and workflow hardening.

## Verification

- `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_publication_domain.py tests/test_publication_security.py` — 24 tests collected.
- `git diff --check` — passed.

Ordinary test execution is intentionally red until the later Phase 4 plans provide the publication domain, publisher adapter, composition, and workflow modules named by these contracts.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. The missing publication modules are intentional Wave 0 red-state dependencies, not stubs in the test artifacts.

## Self-Check: PASSED

- `tests/test_publication_domain.py` and `tests/test_publication_security.py` exist.
- Task commits `45d4d4a` and `e9da71d` exist in git history.
- Shared tracking files were not modified by this plan; the pre-existing `.planning/STATE.md` worktree change remains unstaged.
