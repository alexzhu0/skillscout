---
phase: 01-auditable-dry-run-spine
plan: "06"
subsystem: persistence
tags: [stage-contracts, bounded-json, manifests, sqlite, lifecycle, tdd]

requires:
  - phase: 01-auditable-dry-run-spine/01-05
    provides: "Sealed Phase-1 composition authority with supported local fixture and SQLite adapters"
provides:
  - "One immutable producer/schema registry shared by runtime acceptance, migration, manifest writes and manifest reads"
  - "Strict JSON-only StagePayload with deterministic structural and canonical manifest byte bounds"
  - "Whole-stage post-start failure closure plus deterministic next-open orphan reconciliation"
affects: [phase-1-ledger-integrity, phase-2-provider-adapters, phase-6-adversarial-acceptance]

tech-stack:
  added: []
  patterns: [bounded untrusted output, writer-reader symmetry, pre-I/O canonicalization, durable lifecycle reconciliation]

key-files:
  created: []
  modified:
    - src/skillscout/domain/models.py
    - src/skillscout/application/ports.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/adapters/state.py
    - tests/test_stage_contracts.py
    - tests/test_pipeline_resume.py

key-decisions:
  - "Represent supported persisted evidence as immutable (schema_version, producer_version) pairs and apply the same set at every write/read boundary."
  - "Reject processor output through StagePayload before hashing, then bound the exact canonical envelope bytes before any manifest path or temporary file is created."
  - "Close every known post-start failure immediately; if durable closure is indeterminate, reconcile only orphan running attempts from persisted facts on the next successful store open."

patterns-established:
  - "Untrusted stage output: validate exact JSON types, finite numbers, UTF-8 sizes, collection sizes, depth and total nodes before canonicalization."
  - "Manifest preflight: canonicalize once, enforce MAX_MANIFEST_BYTES, then reuse those exact bytes for the atomic writer."
  - "Lifecycle boundary: processor, output contract, identity construction, manifest persistence and DB completion each map to closed diagnostics and terminal attempt/run evidence."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Stage outputs accept only bounded JSON primitives and finite deterministic structures."
    requirement: OPS-01
    verification:
      - kind: unit
        ref: "tests/test_stage_contracts.py#StagePayload structural and byte-bound regressions"
        status: pass
    human_judgment: false
  - id: D2
    description: "Writer, migration and reader accept exactly the same supported producer/schema identities and manifest size."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#writer-reader and migration preflight regressions"
        status: pass
    human_judgment: false
  - id: D3
    description: "Known post-start failures close immediately and indeterminate closures reconcile before resume decisions."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#failure closure and orphan reconciliation regressions"
        status: pass
    human_judgment: false

duration: 16min
completed: 2026-07-19
status: complete
---

# Phase 1 Plan 06: Bounded Symmetric Stage Lifecycle Summary

**Strict bounded JSON output, one producer/schema registry and complete post-start lifecycle closure now prevent SkillScout from producing successful evidence that its own reader rejects.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-07-19T05:14:09Z
- **Completed:** 2026-07-19T05:30:37Z
- **Tasks:** 2 TDD tasks
- **Files modified:** 6

## Accomplishments

- Added frozen `StagePayload` validation for exact JSON types, finite numbers, UTF-8 key/string limits, collection size, nesting depth, node count and bounded integers while preserving explicit nulls and canonical JSON.
- Centralized `MAX_MANIFEST_BYTES` and immutable `(schema, producer)` support pairs in the domain contract; runtime, migration, writer and reader now share them without duplicated allowlists.
- Rejected unsupported producer identities before resumable lookup or run creation and captured one immutable producer value for the complete run.
- Moved output conversion, validation, hashing, envelope construction, manifest persistence and DB completion behind sanitized post-start failure handling.
- Computed exact canonical envelope bytes once and rejected oversized manifests before resolving or creating manifest paths.
- Added deterministic SQLite-open reconciliation that converts only orphan `running` attempts/runs into fixed interrupted evidence without result or checkpoint creation.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: Bounded stage-output contract regressions** — `3bf0144` (test)
2. **Task 1 GREEN: Bounded JSON and producer/schema contract** — `d4c2266` (feat)
3. **Task 2 RED: Writer-reader and lifecycle regressions** — `dc6a12f` (test)
4. **Task 2 GREEN: Symmetric durable stage lifecycle** — `831e3a0` (feat)

## Files Created/Modified

- `src/skillscout/domain/models.py` — shared resource limits, immutable producer/schema registry, strict `StagePayload` and manifest-byte preflight.
- `src/skillscout/application/ports.py` — closed `STAGE_OUTPUT_INVALID` code and fixed bounded ASCII summary.
- `src/skillscout/application/pipeline.py` — pre-run producer support gate and complete post-start failure classifier.
- `src/skillscout/adapters/state.py` — symmetric registry enforcement, exact manifest-byte writing, migration bounds and orphan reconciliation.
- `tests/test_stage_contracts.py` — JSON primitive, invalid type, finite number, depth, node, collection, UTF-8 and exact byte-cap coverage.
- `tests/test_pipeline_resume.py` — unsupported producer, oversized output, migration, persistence failure, writer-reader and next-open reconciliation coverage.

## Verification Evidence

- Focused locked offline suite: `47 passed`.
- Focused Ruff check: all checks passed.
- Diff whitespace check: clean.
- Gate-B `uv.lock` SHA-256 remains `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256 remains `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`.
- No tracked file was deleted, and `.planning/config.json` remained outside every plan commit.

## Decisions Made

- Producer support is a pair contract rather than independent schema and producer allowlists; this prevents a valid value from one schema being accidentally accepted in another.
- `StageEnvelope` retains strict direct-construction validation, while the runner validates `StagePayload` before any identity or persistence work so non-JSON objects never reach hashing.
- Orphan reconciliation uses durable `started_at` facts for terminal timestamps and the fixed `PIPELINE_INTERRUPTED` diagnostic; it never persists raw exceptions or reconstructs unavailable failure content.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test instrumentation] Narrowed the manifest-I/O observer**
- **Found during:** Task 2 GREEN verification.
- **Issue:** The RED observer was installed before the approved fixture read, so it counted `approved.json` as manifest I/O even though no manifest path was touched.
- **Fix:** Loaded the already-approved bounded fixture before installing the `os.open` observer; all lifecycle and zero-manifest-I/O assertions remain unchanged.
- **Files modified:** `tests/test_pipeline_resume.py`
- **Verification:** The exact focused suite passed all 47 tests.
- **Committed in:** `831e3a0`

**2. [Rule 3 - Blocking] Recovered exact verification and commits through the orchestrator**
- **Found during:** Task 2 RED/GREEN execution.
- **Issue:** The command approval layer repeatedly misclassified required parent-agent status messages and denied exact repository-local locked verification and atomic git commits.
- **Fix:** Stopped after each denial without workarounds; the orchestrator reran only the exact locked offline commands, confirmed intended RED/GREEN results, and committed only the plan-scoped files.
- **Files modified:** None beyond the plan-scoped task files.
- **Verification:** RED produced six intended failures; GREEN produced 47 passes and a clean Ruff result; commit contents were independently scoped.
- **Committed in:** `dc6a12f`, `831e3a0`

---

**Total deviations:** 2 auto-fixed (1 test instrumentation, 1 execution-environment blocker). **Impact:** No product scope, authority, dependency or security boundary changed.

## Issues Encountered

- The approval-layer recovery was an execution-environment issue, not a product failure. No network access, dependency installation, source-repository execution or broad git staging occurred.

## TDD Gate Compliance

- Task 1: RED `3bf0144` → GREEN `d4c2266`.
- Task 2: RED `dc6a12f` → GREEN `831e3a0`.
- Both RED gates failed on the intended missing behavior, and both GREEN gates passed their exact focused suites.

## Threat and Stub Scan

- T-01-G2-01 is mitigated by the one immutable producer/schema registry at runtime, migration, write and read boundaries.
- T-01-G2-02 is mitigated by pre-recursion structural caps and exact canonical-byte preflight before manifest filesystem activity.
- T-01-G2-03 is mitigated by whole-stage failure closure and deterministic next-open orphan reconciliation.
- T-01-SC remains satisfied: neither `uv.lock` nor the frozen schema-v1 fixture changed.
- No new network, authentication, remote-write, executable-source, schema or credential surface was introduced.
- No TODO, FIXME, placeholder, coming-soon, unavailable or UI-flowing empty stub was found in the changed files.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CR-03, CR-04 and WR-01 are closed with bounded writer/read symmetry and durable lifecycle evidence.
- Plan 01-07 can strengthen the full canonical ledger verifier on top of evidence that is now guaranteed write-readable and resource-bounded.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*

## Self-Check: PASSED

- All six modified source/test files exist.
- All four TDD task commits are present in git history.
- Both authoritative SHA-256 values match the approved frozen bytes.
- The exact focused suite passed 47 tests, Ruff passed, and diff whitespace validation was clean.
- No tracked file was deleted, and `.planning/config.json` remains the sole uncommitted orchestrator-owned change.
