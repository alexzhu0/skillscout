---
phase: 04-controlled-draft-pr
plan: 06
subsystem: controlled-publication-cli
tags: [publication, admission, cli, github, security]
requires:
  - phase: 04-controlled-draft-pr
    provides: exact Phase 3 candidate projections and recovery-first Draft publication
provides:
  - protected catalog authority configuration with deferred token access
  - authority-blind candidate evidence handoff and protected comparison binding
  - fixed admission verifier and publisher CLI surfaces
affects: [04-09, controlled-publishing, GitHub Actions]
tech-stack:
  added: []
  patterns: [admission-before-token, fixed-cli-contract, bounded-public-projection]
key-files:
  created: []
  modified: [src/skillscout/bootstrap.py, src/skillscout/cli.py, tests/test_publication_security.py, tests/test_cli_security.py, tests/test_cli_validate_skill.py]
key-decisions:
  - "Catalog identity and individual reviewer authority are read only from strict protected configuration."
  - "The unprivileged handoff contains exactly candidate locators and candidate digests; intent and admission digests are protected-job-local."
requirements-completed: [PUB-01, PUB-02, PUB-03, PUB-05, SEC-02]
coverage:
  - id: D1
    description: Strict protected catalog/reviewer configuration defers token use until publication admission.
    requirement: SEC-02
    verification:
      - kind: unit
        ref: tests/test_publication_security.py
        status: pass
    human_judgment: false
  - id: D2
    description: Fixed verifier and publisher CLI contracts prevent caller-selected remote authority and mutation options.
    requirement: PUB-01
    verification:
      - kind: integration
        ref: tests/test_cli_security.py tests/test_cli_validate_skill.py
        status: pass
    human_judgment: false
metrics:
  tasks: 3
  files: 5
  completed: 2026-07-24
status: complete
---

# Phase 04 Plan 06: Admission-First Publisher and Safe CLI Summary

**Protected catalog authority, exact completed-candidate admission, and fixed CLI contracts for controlled Draft publication.**

## Accomplishments

- Added frozen protected authority/runtime configuration that rejects team reviewers and malformed catalog input before token or network construction.
- Reprojects completed Phase 2/3 evidence into the exact ten-field authority-blind handoff; protected comparison derives intent and admission only after equality.
- Added closed `verify-publication-admission` and `publish-candidate` command surfaces with bounded JSON projection and no mutation/authority flags.

## Task Commits

1. **Task 1: Build strict protected publication configuration** — `f20cd09`
2. **Task 2: Wire completed Phase 3 projection to publication application** — `270baf3`
3. **Task 3: Expose closed admission-verifier and publish CLIs** — `0642c9a`

## Verification

- `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_cli_security.py tests/test_publication_security.py tests/test_cli_validate_skill.py -x` — 76 passed, 1 skipped.
- `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_cli_dry_run.py tests/test_cli_extract_repo.py tests/test_cli_validate_skill.py` — 46 passed.

## Decisions Made

- Keep the Phase 1/2/3 graphs free of direct publication-adapter imports; the publication client is resolved only by the protected write factory.
- Treat all configuration/comparison failures as closed diagnostics, without persisting candidate prose, token values, or provider error bodies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Preserved pre-existing dry-run isolation assertion.**
- **Found during:** Task 3 verification.
- **Issue:** Directly importing the publisher adapter from bootstrap would make the dry-run isolation test fail despite lazy construction.
- **Fix:** Deferred the fixed publisher-adapter resolution to the protected remote factory.
- **Files modified:** `src/skillscout/bootstrap.py`
- **Verification:** Full CLI/publication security suite passed.
- **Commit:** `0642c9a`

## Known Stubs

None.

## Self-Check: PASSED

- `src/skillscout/bootstrap.py`, `src/skillscout/cli.py`, and this summary exist.
- Task commits `f20cd09`, `270baf3`, and `0642c9a` exist.
- The pre-existing orchestrator-owned `.planning/STATE.md` remains unstaged and was not modified.
