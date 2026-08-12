---
phase: 06-adversarial-mvp-acceptance
plan: "05"
subsystem: acceptance-application
tags: [acceptance, capability-separation, cli, state-authority, tdd]
requires:
  - phase: 06-03
    provides: acceptance domain facts and hard-gate vocabulary
  - phase: 06-04
    provides: operations-owned acceptance persistence and rebuild projection
provides:
  - capability-separated acceptance application dependencies and transitions
  - evaluator-blind semantic payload projection and closed terminal classification
  - bounded acceptance CLI surface with pre-secret authority validation
  - canonical locked-manifest and attestation readers
affects: [06-07, 06-08, 06-10, 06-12, 06-13]
tech-stack:
  added: []
  patterns:
    - frozen capability-specific dependency dataclasses
    - exact immutable-state readmission before credential resolution
    - canonical typed file handoffs with fixed sanitized diagnostics
key-files:
  created:
    - src/skillscout/application/acceptance.py
  modified:
    - src/skillscout/bootstrap.py
    - src/skillscout/cli.py
    - tests/test_acceptance_application.py
    - tests/test_phase6_acceptance.py
    - tests/test_cli_security.py
key-decisions:
  - "Nomination, locked campaign, replay/update, attestations, and rebuild use distinct frozen dependency types."
  - "Acceptance CLI inputs cannot select models, endpoints, catalogs, refs, secrets, cleanup, approval, merge, or ready-for-review effects."
  - "The acceptance catalog is fixed to alexzhu0/skillscout-catalog-test and immutable facts are validated before any environment-backed credential boundary."
patterns-established:
  - "Acceptance facts are recorded only through OperationsStateStore and rebuilt through its typed snapshot."
  - "Evaluator-only fields are recursively rejected before semantic request projection."
metrics:
  duration: 12m
  completed: 2026-07-29
  tasks: 2
  files: 6
status: complete
---

# Phase 6 Plan 05: Capability-Separated Acceptance Orchestrator Summary

Capability-separated acceptance composition with evaluator-blind semantic inputs, exact state re-admission, and four closed CLI transitions whose authority is validated before credentials.

## Performance

- **Duration:** 12 minutes
- **Started:** 2026-07-29T07:49:46Z
- **Completed:** 2026-07-29T08:01:53Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added frozen dependency contracts for Search-only nomination, locked campaigns, replay/update, human review, probe cleanup, offline evaluation, and report rebuild.
- Added exact manifest-to-nomination re-admission, closed terminal classification, typed operations-state recording, and evaluator-field exclusion from semantic payloads.
- Added `nominate-benchmark`, `run-acceptance`, `record-acceptance-attestation`, and `rebuild-acceptance` with only bounded authority arguments and canonical JSON output.
- Added stable private-file validation for locked manifests and attestations, a fixed catalog target, closed provider revalidation, and exact state commit/root readmission before credential use.

## Task Commits

Each task was committed atomically:

1. **Task 06-05-01: Compose acceptance services** — `bcb669d` (`feat`)
2. **Task 06-05-02 RED: Freeze CLI authority boundary** — `444f22f` (`test`)
3. **Task 06-05-02 GREEN: Add closed acceptance CLI authority** — `41ed7fb` (`feat`)

## Files Created/Modified

- `src/skillscout/application/acceptance.py` — capability-specific dependencies, record/rebuild transitions, re-admission, and terminal mapping.
- `src/skillscout/bootstrap.py` — nomination and acceptance runtime configs, canonical file readers, fixed catalog, and pre-secret state validation.
- `src/skillscout/cli.py` — four bounded acceptance commands, exact-state restore, attestation persistence, and report-root rebuild projection.
- `tests/test_acceptance_application.py` — capability and evaluator-blindness contracts.
- `tests/test_phase6_acceptance.py` — closed parser and pre-secret bootstrap contracts.
- `tests/test_cli_security.py` — expanded exact command registry while retaining `SafeArgumentParser`.

## Decisions Made

- Kept live adapters outside offline/rebuild dependency signatures; only the transition that needs a capability can receive its lazy factory.
- Reused the existing discovery query policy and operations-state owner instead of introducing a second Search, persistence, or publication implementation.
- Treated business rejection as durable evidence while mapping provider/schema exhaustion, evidence mismatch, duplicate effects, unauthorized effects, and harness failure to closed system-failure outcomes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added the missing Task 2 RED selection**
- **Found during:** Task 06-05-02 RED
- **Issue:** The plan's required `-k 'cli or parser or bootstrap or credential or target'` command selected no tests, so the TDD gate could not prove a failing contract.
- **Fix:** Added exact parser, forbidden-option, fixed-catalog, pre-secret validation, and sanitized unknown-flag tests before implementation.
- **Files modified:** `tests/test_phase6_acceptance.py`
- **Commit:** `444f22f`

**2. [Rule 1 - Compatibility] Updated the exact CLI command registry**
- **Found during:** Task 06-05-02 GREEN
- **Issue:** The existing CLI security test intentionally enumerated the previous eight commands and would reject the four planned bounded commands.
- **Fix:** Extended only the exact approved command set while retaining the same safe parser assertion for every subparser.
- **Files modified:** `tests/test_cli_security.py`
- **Commit:** `41ed7fb`

## Verification

- `tests/test_acceptance_application.py`: 12 passed.
- Task 2 acceptance selector: 3 passed, 16 deselected.
- CLI and discovery security regression: 49 passed.
- Ruff on all changed production and test files: passed.
- Full locked suite: 2048 passed, 59 skipped, with three expected later-plan Wave-0 RED nodes still failing (`verify_repository`, `evaluate_controlled_scenario`, and `verify_source_execution`), already tracked in `deferred-items.md`.

## Known Stubs

None. Optional campaign/publication factories are deliberate absent capabilities until their protected transitions are authorized; they do not supply empty UI or fabricated acceptance evidence.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: cli_authority | `src/skillscout/cli.py` | Four new acceptance transitions restore exact state and keep secrets, arbitrary provider/catalog selection, and destructive GitHub actions outside the CLI grammar. |
| threat_flag: bounded_file_read | `src/skillscout/bootstrap.py` | Locked manifest and human attestation files cross a trust boundary through stable private-file checks, strict schemas, and canonical-byte validation. |

## Next Phase Readiness

- Plan 06-07 can bind real Search nomination evidence to the Search-only authority and operations-owned nomination fact.
- Plans 06-08 through 06-13 can use the locked campaign, attestation, replay/update, and offline rebuild capabilities without widening CLI authority.
- The three remaining full-suite RED nodes belong to later Phase 6 plans and are unchanged.

## Self-Check: PASSED

All six implementation/test files and this summary exist, and commits `bcb669d`, `444f22f`, and `41ed7fb` are present in repository history.
