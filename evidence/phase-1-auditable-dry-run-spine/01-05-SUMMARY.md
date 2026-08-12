---
phase: 01-auditable-dry-run-spine
plan: "05"
subsystem: security
tags: [capability-firewall, effect-scopes, composition-root, dry-run, tdd]

requires:
  - phase: 01-auditable-dry-run-spine/01-04
    provides: "Local-only capability registry, fail-closed state boundaries and nine-stage dry-run acceptance"
provides:
  - "Adapter-owned immutable effect declarations that cannot be paired with caller-forged scope labels"
  - "Fixed Phase-1 authority ceiling limited to none and local_state"
  - "Closed production composition root that rejects remote and unsupported adapters before runner construction"
affects: [phase-2-provider-adapters, phase-4-publication-boundary, security-regression-suite]

tech-stack:
  added: []
  patterns: [adapter-owned authority, immutable capability ceiling, concrete production registry, lower-level dependency injection]

key-files:
  created: []
  modified:
    - src/skillscout/application/ports.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/adapters/fixtures.py
    - src/skillscout/adapters/state.py
    - tests/test_side_effect_policy.py

key-decisions:
  - "Derive every AdapterRegistration scope from the adapter and remove the independent caller-supplied label."
  - "Expose PHASE_ONE_MAX_SCOPES as the immutable production ceiling and remove policy/extra-registration inputs from build_dry_run_runtime."
  - "Keep PipelineRunner dependency-injected for focused tests while requiring exact supported concrete types at the production composition root."

patterns-established:
  - "Authority declaration: supported adapters expose a read-only EffectScope property; registration copies and freezes that declaration."
  - "Production composition: validate the complete fixed registry and concrete types before creating PipelineRunner."

requirements-completed: [OPS-04]

coverage:
  - id: D1
    description: "Registration authority is adapter-owned, immutable and rejects missing, malformed or remote declarations before invocation."
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "tests/test_side_effect_policy.py#adapter-owned declaration regressions"
        status: pass
    human_judgment: false
  - id: D2
    description: "The Phase-1 production builder has a fixed none/local_state ceiling and no policy or arbitrary-registration widening path."
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "tests/test_side_effect_policy.py#sealed composition regressions"
        status: pass
    human_judgment: false
  - id: D3
    description: "The supported concrete fixture and SQLite registry still completes all nine local stages with zero remote writes."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_cli_dry_run.py#test_installed_main_completes_all_stages_with_socket_connects_disabled"
        status: pass
      - kind: other
        ref: "locked pytest -q: 82 passed"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-19
status: complete
---

# Phase 1 Plan 05: Immutable Authority Ceiling Summary

**Adapter-owned effect declarations and a sealed concrete composition root now make Phase 1's none/local_state ceiling non-forgeable and non-widenable.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-19T04:59:46Z
- **Completed:** 2026-07-19T05:08:20Z
- **Tasks:** 2 TDD tasks
- **Files modified:** 5

## Accomplishments

- Removed the independent scope parameter from `AdapterRegistration`; registrations now validate and freeze the adapter's own closed `EffectScope` declaration.
- Added read-only `none` and `local_state` declarations to the supported fixture and SQLite adapters and proved malformed, missing and remote declarations fail before invocation.
- Added immutable `PHASE_ONE_MAX_SCOPES`, removed caller policy and arbitrary-registration inputs, and restricted production construction to the fixed supported fixture, SQLite, clock, ID and local publication objects.
- Preserved provider-independent `PipelineRunner` injection and the complete nine-stage local dry-run, with zero remote writes.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: Adapter-owned declaration regressions** — `d7181e1` (test)
2. **Task 1 GREEN: Adapter-owned immutable scopes** — `65a6e3e` (feat)
3. **Task 2 RED: Sealed composition regressions** — `1ea498f` (test)
4. **Task 2 GREEN: Immutable production ceiling** — `c24c5a6` (feat)

## Files Created/Modified

- `src/skillscout/application/ports.py` — adapter-owned registration contract with a frozen derived scope.
- `src/skillscout/application/pipeline.py` — immutable Phase-1 maximum, closed concrete registry and actual local publication-writer registration.
- `src/skillscout/adapters/fixtures.py` — read-only effect-free fixture processor declaration.
- `src/skillscout/adapters/state.py` — read-only local-state SQLite declaration.
- `tests/test_side_effect_policy.py` — CR-01 mislabel, widening, unsupported-adapter and fixed-registry regressions.

## Verification Evidence

- Gate-B `uv.lock` SHA-256 remained `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256 remained `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`.
- Task 1 focused gate: `10 passed`.
- Task 2 authority plus CLI gate: `29 passed`; focused Ruff passed.
- Full locked regression suite: `82 passed in 1.20s`.
- Full `ruff check .`: passed.
- `.planning/config.json` retained its orchestrator-owned bytes and remained outside every task commit.

## Decisions Made

- A registration records authority; it does not grant authority. Its effect scope therefore comes only from the adapter and cannot be supplied in parallel by a caller.
- `SideEffectPolicy` remains useful for lower-level policy tests, but production `build_dry_run_runtime` always constructs and applies `SideEffectPolicy.phase_one()` with the fixed maximum.
- Exact concrete-type checks are intentionally confined to the Phase-1 production builder; `PipelineRunner` remains protocol-oriented for deterministic unit tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated composition registrations during Task 1**
- **Found during:** Task 1 GREEN implementation.
- **Issue:** Removing the caller-supplied registration scope changed the constructor used by the existing production composition root; leaving that caller unchanged would break the task's required local happy path before Task 2 began.
- **Fix:** Converted the existing fixed registrations to adapter-owned construction and added truthful clock, ID and local publication declarations while leaving policy sealing for Task 2.
- **Files modified:** `src/skillscout/application/pipeline.py`
- **Verification:** Task 1's complete focused suite passed with the nine-stage local happy path green.
- **Committed in:** `65a6e3e`

---

**Total deviations:** 1 auto-fixed (1 blocking integration update). **Impact:** The adjustment was required by the planned registration API change and introduced no new capability or scope.

## Issues Encountered

- The sandbox could not access uv's existing user cache or write Git metadata. The exact approved local uv/managed-Python/no-download commands and normal verified git commits were run through the required approval boundary; no dependency, lock or fixture bytes changed.

## TDD Gate Compliance

- Task 1: RED `d7181e1` → GREEN `65a6e3e`.
- Task 2: RED `1ea498f` → GREEN `c24c5a6`.
- Both RED runs failed on the intended missing authority guarantees, and both GREEN runs passed their focused acceptance suites.

## Threat and Stub Scan

- T-01-G1-01 and T-01-G1-02 are mitigated by removal of widening inputs, adapter-owned declarations, the immutable maximum and pre-run concrete registry validation.
- No HTTP, GitHub, OpenAI, socket, subprocess, credential, remote-publication, merge or candidate-code execution surface was added.
- No TODO, FIXME, placeholder, coming-soon, unavailable or UI-flowing empty stub was found in the changed files.
- No unplanned trust boundary was introduced; the only changed boundary is the composition authority surface registered in this plan's threat model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CR-01 and verification root gap 1 are closed by construction with adversarial regression evidence.
- Plan 01-06 can build bounded symmetric durable contracts on top of the now-sealed production authority boundary.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*

## Self-Check: PASSED

- All five modified files exist and the four TDD task commits are present in git history.
- Both authoritative SHA-256 values match the approved frozen bytes.
- All task acceptance checks, the 82-test full suite and full Ruff suite passed.
- No tracked file was deleted, and `.planning/config.json` remains uncommitted with its pre-existing orchestrator-owned change intact.
