---
phase: 04-controlled-draft-pr
plan: 02
subsystem: publication-contract-tests
tags: [pytest, httpx, mocktransport, github-rest, recovery, live-canary]
requires:
  - phase: 03-candidate-pipeline
    provides: frozen candidate and reviewer evidence contracts
provides:
  - bounded GitHub publish response corpus and exact offline transport contract
  - crash/recovery ambiguity specification with individual-reviewer-only evidence
  - explicit all-or-nothing live-canary admission and cleanup-manifest boundary
affects: [04-03, 04-04, 04-05, 04-06, 04-09]
tech_stack:
  added: []
  patterns: [deferred-import-wave-zero-tests, recorded-mocktransport, reconcile-first-recovery, opt-in-canary]
key_files:
  created:
    - tests/fixtures/github_publish/error_matrix.json
    - tests/test_github_publish_adapter.py
    - tests/test_publication_recovery.py
    - tests/test_publication_live_canary.py
  modified: []
key-decisions:
  - "All publish-provider routes use RecordedTransport fixtures and reject unrecorded requests."
  - "Recovery accepts only sorted unique individual reviewers; provider team state and removed reviewer evidence fail closed."
  - "Live canary remains inert without all explicit environment values and yields a human cleanup manifest instead of cleanup calls."
requirements-completed: [PUB-01, PUB-04, PUB-05]
coverage:
  - id: D1
    description: Bounded GitHub publish transport protocol and failure matrix.
    requirement: PUB-01
    verification:
      - kind: integration
        ref: .tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_github_publish_adapter.py
        status: pass
    human_judgment: false
  - id: D2
    description: Crash recovery, local-state-loss, remote ambiguity, and individual reviewer evidence contract.
    requirement: PUB-05
    verification:
      - kind: integration
        ref: .tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_publication_recovery.py
        status: pass
    human_judgment: false
  - id: D3
    description: Explicit live-canary admission boundary and separate cleanup authority.
    requirement: PUB-04
    verification:
      - kind: integration
        ref: .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py
        status: pass
    human_judgment: true
    rationale: A later separately authorized GitHub App and ruleset canary must be reviewed by a human/admin.
metrics:
  tests_collected: 57
  live_canary_tests: 3 passed, 2 skipped
status: complete
---

# Phase 04 Plan 02: Controlled Draft PR transport and recovery contract summary

Bounded MockTransport fixtures now freeze the closed publisher protocol, while recovery and opt-in live-canary contracts define fail-closed behavior before write-capable production code exists.

## Completed Tasks

1. Added nine credential-free `github_publish` JSON fixtures and 21 collectable transport cases for exact Git REST paths, bodies, pagination, tree bounds, team ambiguity, and provider failures.
2. Added 36 collectable crash/recovery cases covering every visible crash seam, state loss, remote conflicts, reviewer completion/removal, and stale owned-subtree cleanup.
3. Added five offline live-canary admission tests; default execution has no client construction or network activity and reports a bounded human cleanup manifest only.

## Verification

- `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_github_publish_adapter.py tests/test_publication_recovery.py` — 57 tests collected.
- `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py` — 3 passed, 2 safely skipped without complete opt-in configuration.
- `git diff --check` — passed.

## Task Commits

1. `da0135a` — `test(04-02): freeze GitHub publish transport contract`
2. `d946080` — `test(04-02): specify publication crash recovery`
3. `72ce68b` — `test(04-02): specify opt-in publication canary`

## Decisions Made

- The fixture corpus contains only bounded synthetic provider IDs and is isolated behind `RecordedTransport`; unexpected routes raise immediately.
- Team reviewer configuration and non-empty provider team observations are manual ambiguity, never reviewer authority.
- Approval and ready-for-review remain static/transport absence proofs rather than falsely claimed platform denials; live negative probes retain only safe classifications and unchanged default-ref evidence.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

The test modules defer imports of the planned publisher adapter and application seams. This is intentional Wave 0 red-state specification: collection and default canary execution work before later plans introduce production modules.

## Self-Check: PASSED

- All nine GitHub publish fixtures and all three plan test modules exist.
- Task commits `da0135a`, `d946080`, and `72ce68b` exist in git history.
- No shared tracking files were modified by this plan; the pre-existing `.planning/STATE.md` worktree change remains unstaged.
