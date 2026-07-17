---
phase: 01-auditable-dry-run-spine
plan: "04"
subsystem: security
tags: [capability-firewall, sqlite, manifests, prompt-injection, zero-network, fail-closed]

requires:
  - phase: 01-auditable-dry-run-spine/01-03
    provides: "Strict schema-v2 ledger, frozen v1 migration, content-addressed manifests and resumable inspect flow"
provides:
  - "Closed effect-scoped adapter registry that structurally rejects remote authority"
  - "Fail-closed state, manifest, fixture and local-output integrity boundaries"
  - "Sanitized relative evidence locators with no operator path disclosure"
  - "Locked zero-network nine-stage acceptance with interruption, reuse and inspect evidence"
affects: [phase-2-provider-adapters, phase-4-draft-pr-publisher, security-regression-suite]

tech-stack:
  added: []
  patterns: [capability omission, composition-time policy, descriptor-bounded reads, derived evidence locators, socket sentinel]

key-files:
  created:
    - tests/test_side_effect_policy.py
    - tests/test_state_integrity.py
    - tests/test_cli_security.py
  modified:
    - src/skillscout/domain/enums.py
    - src/skillscout/application/ports.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/adapters/fixtures.py
    - src/skillscout/adapters/state.py
    - src/skillscout/cli.py
    - tests/conftest.py
    - tests/test_cli_dry_run.py

key-decisions:
  - "Represent dry-run authority as immutable effect-scoped registrations and validate the complete registry before constructing PipelineRunner."
  - "Persist only stage/hash relative manifest locators; derive actual paths from the operator-selected database and never trust a stored filesystem override."
  - "Expose a fixed publication-plan filename instead of echoing operator paths, while retaining real filesystem writes behind strict symlink and regular-file checks."

patterns-established:
  - "Phase 1 production composition permits exactly none and local_state; remote_read or remote_write fails before any adapter invocation."
  - "Manifest reads use a single no-follow descriptor, enforce regular-file and byte bounds, and verify row, envelope, output and manifest identities."
  - "Every public failure uses a closed code and fixed ASCII summary of at most 160 characters; no exception, payload, credential or selected path is interpolated."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Dry-run composition structurally omits remote authority and rejects remote-read/write registrations before invocation."
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "tests/test_side_effect_policy.py (5 capability-policy tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Hostile fixture, state, manifest, symlink, transition and diagnostic inputs fail closed without checkpoint advance or disclosure."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py and tests/test_cli_security.py"
        status: pass
      - kind: other
        ref: "full locked pytest suite: 72 passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "The full installed CLI completes all nine stages with socket connects disabled, zero remote writes and verified interrupt/resume/inspect recovery."
    requirement: OPS-04
    verification:
      - kind: e2e
        ref: "tests/test_cli_dry_run.py#test_installed_main_completes_all_stages_with_socket_connects_disabled"
        status: pass
      - kind: other
        ref: "uv lock --check; uv build --no-sources; ruff check .; pytest -q"
        status: pass
    human_judgment: false

duration: 21 min
completed: 2026-07-17
status: complete
---

# Phase 1 Plan 04: Fail-Closed Local Runtime Summary

**A closed local-only composition root, derived content-addressed evidence paths and a socket-blocked acceptance run now make Phase 1's no-remote and no-disclosure promises executable.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-17T06:28:32Z
- **Completed:** 2026-07-17T06:49:20Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- Added immutable `EffectScope`, `AdapterRegistration`, `SideEffectPolicy`, `DryRunRuntime` and `build_dry_run_runtime`; the complete production registry permits only `none` and `local_state` and rejects either remote scope before invocation.
- Expanded strict fixture validation plus fail-closed SQLite, manifest and publication-output handling for malformed bytes, schema coercion, hostile IDs, symlinks, missing/tampered/redirected manifests, unsupported identities and illegal terminal transitions.
- Replaced stored filesystem paths with validated `stage/<lowercase-hash>.json` locators and made success JSON expose only the fixed `publication-plan.json` name, preventing operator-selected paths from reaching durable or CLI content.
- Proved a full nine-stage CLI with real SQLite/filesystem I/O completes under a socket sentinel with zero connection attempts, `remote_writes_attempted=0` and `planned_not_published`.

## Task Commits

1. **Task 1: Reject remote capability at composition time** — `122ac2d` (RED), `f0e0799` (GREEN)
2. **Task 2: Expand fail-closed state, input and disclosure coverage** — `4a6488e` (RED), `851db45` (GREEN), `468c95d` (disclosure correction)
3. **Task 3: Prove final locked no-network acceptance** — `89132d` (socket sentinel and acceptance test)

The plan metadata and this summary are committed separately by `docs(01-04)`.

## Files Created/Modified

- `src/skillscout/domain/enums.py` — closed local and remote effect scopes.
- `src/skillscout/application/ports.py` — immutable scoped registrations and bounded `forbidden_effect_scope` diagnostic.
- `src/skillscout/application/pipeline.py` — validated composition root, legal resume transitions, path-safe publication planning and fixed public plan locator.
- `src/skillscout/adapters/fixtures.py` — strict bounded schema, source/license/commit and safe subject identifier constraints.
- `src/skillscout/adapters/state.py` — no-follow bounded manifests, derived locators, row/envelope verification, transition enforcement and symlink rejection.
- `src/skillscout/cli.py` — sole dry-run construction path through `build_dry_run_runtime`.
- `tests/test_side_effect_policy.py` — composition-time remote authority rejection.
- `tests/test_state_integrity.py` — corruption, redirect, schema, transition and symlink evidence.
- `tests/test_cli_security.py` — invalid input and multi-surface disclosure canaries.
- `tests/conftest.py` — outbound socket sentinel.
- `tests/test_cli_dry_run.py` — installed in-process zero-network end-to-end acceptance.

## Final Acceptance Evidence

- Gate-B `uv.lock` SHA-256: `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32` — unchanged.
- Frozen v1 database SHA-256: `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251` — unchanged.
- `uv lock --check`: 13 packages resolved from the approved graph without lock mutation.
- `uv build --no-sources`: source distribution and wheel built successfully.
- `ruff check .`: passed.
- `pytest -q`: 72 passed in 1.07 seconds.
- Fresh happy run: exit 0, `planned_not_published`, last stage `publication_planner`, zero remote writes.
- Fresh intentional interruption: raw exit 1, run status `interrupted`, Generator checkpoint, zero Validators attempts.
- Fresh rerun: same run ID, exit 0, six reused stages, nine attempts/results/checkpoints, no replacement attempts.
- `inspect-run`: exit 0, all identity and nullable telemetry fields present, relative manifest locator only, reused count 6 and zero remote writes.
- Socket-sentinel E2E: all nine stages and real local I/O completed with zero `socket.connect` or `socket.create_connection` attempts.

## Decisions Made

- Authority validation belongs at composition time, not behind a dry-run boolean in a future publisher.
- A database may persist a closed relative manifest locator but never an operator-selected absolute path; the state adapter reconstructs the actual path from its own configured root.
- Existing regular publication-plan files may be atomically replaced, but symlinked directories/targets and pre-existing temporary paths are rejected before writes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved legal recovery of a stale running attempt**
- **Found during:** Task 2 full regression suite.
- **Issue:** Strict lifecycle validation correctly rejects `running → running`, but the runner was redundantly requesting that transition when recovering an already-running stale attempt.
- **Fix:** Only interrupted runs transition back to running; an already-running resumable run continues without a no-op state mutation.
- **Files modified:** `src/skillscout/application/pipeline.py`
- **Verification:** Stale-attempt abandonment plus all 72 tests pass.
- **Committed in:** `851db45`

**2. [Rule 2 - Missing Critical] Removed operator state paths from persisted and inspectable evidence**
- **Found during:** Task 3 final disclosure review.
- **Issue:** Although manifest paths were derived safely, persisting their complete filesystem path could echo an operator-selected state-directory canary through SQLite and `inspect-run`.
- **Fix:** Persist only the closed stage and lowercase digest locator, derive the filesystem root from the configured database at read/write time, and add a durable/CLI canary test.
- **Files modified:** `src/skillscout/adapters/state.py`, `tests/test_state_integrity.py`, `tests/test_cli_security.py`
- **Verification:** State-path canary is absent from SQLite/manifests/CLI output; full locked suite passes.
- **Committed in:** `468c95d`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical security control). **Impact:** Both enforce the planned transition and disclosure guarantees without adding remote authority or changing dependencies.

## Issues Encountered

- The sandbox blocks uv's default user cache path. Verification used scoped approval while retaining the exact approved repository-local uv binary, managed Python, `UV_PYTHON_DOWNLOADS=never` and `--locked` contract.

## TDD Gate Compliance

- Task 1: RED `122ac2d` → GREEN `f0e0799`.
- Task 2: RED `4a6488e` → GREEN `851db45`; final disclosure correction `468c95d` retained the complete GREEN suite.
- Task 3 was the plan's non-TDD acceptance task and committed its automated sentinel evidence in `89132d`.

## Threat and Stub Scan

- No HTTP, GitHub, OpenAI, shell, candidate-code execution, merge or remote-publication implementation exists in `src/skillscout`.
- No TODO, FIXME, placeholder, coming-soon or unavailable implementation marker was found in the changed source/tests.
- The new filesystem and registry surfaces are the exact T-01-06/T-01-07/T-01-08 mitigations already registered in the plan; no unplanned threat surface was introduced.

## User Setup Required

None. The completed Phase 1 runtime uses no external service, credential or remote configuration.

## Next Phase Readiness

Phase 1 is ready for independent code review and goal verification. Phase 2 can add the first provider-facing stage behind the established effect-scoped composition, strict contract, untrusted-input and sanitized-evidence boundaries.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-17*

## Self-Check: PASSED

- All three created security test files exist and all six execution commits are present.
- Both authoritative SHA-256 values match the approved/frozen bytes.
- The final locked build, lint, 72-test suite, happy run, raw interruption, resume and inspect commands passed.
- No tracked file was deleted and `.planning/config.json` remains excluded from task and metadata staging.
