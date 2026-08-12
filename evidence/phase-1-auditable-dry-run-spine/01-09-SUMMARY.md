---
phase: 01-auditable-dry-run-spine
plan: "09"
subsystem: local-state
tags: [sqlite, schema-fingerprint, integrity, diagnostics, migration, tdd]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: run-scoped result ownership, exact run identity, canonical manifests, and transactional schema-v1 migration
provides:
  - Exact immutable schema-v2 table, column, constraint, foreign-key, and index fingerprint validation
  - SQLite quick-check and foreign-key integrity gates before existing state is accepted
  - Strict sanitized persisted run, attempt, and checkpoint projections
  - Transactional rejection of unsafe legacy diagnostics before copy or manifest creation
affects: [state-integrity, inspect-run, migration, pipeline-resume, phase-01-verification]

tech-stack:
  added: []
  patterns:
    - immutable versioned SQLite schema descriptors checked before state reads or writes
    - exact closed diagnostic projection from untrusted persisted rows
    - validate-before-copy legacy migration boundary

key-files:
  created: []
  modified:
    - src/skillscout/domain/models.py
    - src/skillscout/adapters/state.py
    - tests/test_state_integrity.py
    - tests/test_cli_security.py
    - tests/test_pipeline_resume.py

key-decisions:
  - "Use one immutable schema-v2 descriptor set for fresh creation, existing-state acceptance, and the final canonical migration rebuild."
  - "Treat every persisted diagnostic as untrusted until its closed ErrorCode, exact fixed summary, lifecycle, timestamp, retry, and telemetry facts validate."
  - "Validate schema-v1 source rows before creating copy tables or manifests so rejected legacy bytes remain unchanged evidence."

patterns-established:
  - "Schema acceptance: user_version is necessary but never sufficient; every trusted structural and integrity fact must match."
  - "Persisted projection: public JSON is emitted only from strict extra-forbid Pydantic row models."
  - "Legacy diagnostics: fixture-v1 telemetry is explicitly null and migration cannot bless raw provider fields."

requirements-completed: [OPS-01]

coverage:
  - id: D1
    description: "Schema-v2 databases are accepted only when their exact tables, columns, SQL constraints, foreign keys, indexes, and SQLite integrity match the immutable fingerprint."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_malformed_schema_v2_fingerprint_is_rejected_without_mutation"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_schema_v2_integrity_failures_are_fixed_and_sanitized"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_fresh_and_migrated_v2_use_identical_schema_fingerprint"
        status: pass
    human_judgment: false
  - id: D2
    description: "Run, attempt, and checkpoint rows pass strict closed diagnostic, lifecycle, identifier, timestamp, retry, and telemetry validation before inspect projection."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_cli_security.py#test_persisted_diagnostic_and_telemetry_tampering_is_never_projected"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_running_failed_and_abandoned_records_project_explicit_nulls"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_supported_writer_state_is_immediately_verifiable_and_inspectable"
        status: pass
    human_judgment: false
  - id: D3
    description: "Credential and path canaries in schema-v1 diagnostics fail migration before new schema or manifest evidence is written, without changing the source bytes."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_cli_security.py#test_legacy_diagnostic_canary_rejects_migration_without_new_evidence"
        status: pass
      - kind: other
        ref: "shasum -a 256 tests/fixtures/state/v1-cli.db"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 09: Exact Schema and Sanitized Persisted Projection Summary

**Exact SQLite fingerprinting and strict closed persisted-row models now reject incompatible or secret-bearing state before it can authorize reads, writes, migration, or inspect output.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-07-19T06:27:11Z
- **Completed:** 2026-07-19T06:51:24Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Replaced subset schema checks with immutable descriptors covering every table column, declaration, nullability, default, primary-key position, normalized trusted SQL constraint, foreign key, and index definition.
- Added exact `quick_check` and `foreign_key_check` acceptance gates, then made schema-v1 migration rebuild the same canonical schema used by fresh databases before commit.
- Added strict `PersistedRunRecord`, `PersistedAttemptRecord`, and `PersistedCheckpointRecord` models with fixed diagnostic, lifecycle, timestamp, identifier, retryability, token, and fixture-v1 telemetry validation.
- Added direct tamper and legacy credential/path canary matrices proving inspect and migration return only fixed failures without copying or emitting hostile persisted bytes.

## Task Commits

Each TDD task was committed with a failing test gate followed by its implementation:

1. **Task 01-09-01: Validate the exact schema-v2 fingerprint and database integrity** - `5b684f0` (test), `d71becd` (feat)
2. **Task 01-09-02: Parse persisted rows through strict sanitized projections** - `6f36acc` (test), `1b97b93` (feat)

**Plan metadata:** committed with this summary and tracking update.

## Files Created/Modified

- `src/skillscout/domain/models.py` - Strict persisted run, flattened attempt, and checkpoint projection contracts with coherent lifecycle and telemetry rules.
- `src/skillscout/adapters/state.py` - Immutable schema descriptors, exact SQLite integrity checks, canonical migration rebuild, closed diagnostics, and validated public projection.
- `tests/test_state_integrity.py` - Malformed schema-v2 matrix plus sanitized quick-check and foreign-key failure evidence.
- `tests/test_cli_security.py` - Persisted diagnostic/telemetry tamper matrix and legacy credential/path canary migration evidence.
- `tests/test_pipeline_resume.py` - Fresh-versus-migrated schema identity, complete checkpoint fields, and valid running/failed/abandoned projection evidence.

## Decisions Made

- The canonical schema descriptor is shared by creation, acceptance, and migration. Migration copies through temporary tables, rebuilds the final canonical names and SQL, validates them, and only then commits schema version 2.
- Error code and summary are one closed persisted fact. Both must be null or the code must be a real `ErrorCode` paired with its exact `ERROR_SUMMARIES` value before any model dump.
- Producer telemetry remains a provider-specific contract. The only supported fixture-v1 producer must persist every provider-only telemetry field as explicit null.
- Invalid schema-v1 rows fail before migration starts writing manifests; the copied hostile source stays byte-identical for audit evidence.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The managed sandbox could not read the existing user-level uv cache. Verification was rerun through narrowly approved repository-local `uv run --locked` commands with `UV_PYTHON_DOWNLOADS=never`; no dependency install or network access occurred.
- An optional repository-wide `ruff format --check` found seven pre-existing files outside this plan that are not formatter-clean. The plan-required Ruff lint checks pass; the unrelated formatting drift was left untouched and recorded in `deferred-items.md`.

## User Setup Required

None - no external service configuration required.

## Verification Evidence

- Task 1 exact schema/integrity command: `43 passed, 26 deselected`.
- Task 2 exact diagnostic/canary/inspect command: `24 passed, 73 deselected`.
- Full locked offline regression: `152 passed`.
- Repository-wide Ruff lint: all checks passed.
- `uv.lock` SHA-256 remained `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256 remained `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`.
- `.planning/config.json` remained byte-identical with SHA-256 `5c5acc837fef244afd431f542223618d8abd043eb77b0ef9e08b98267d9d3219` and was never staged.

## TDD Gate Compliance

- Task 1 RED `5b684f0` failed 14 new fingerprint cases before GREEN `d71becd` passed the full focused schema suite.
- Task 2 RED `6f36acc` failed 15 new projection/canary cases before GREEN `1b97b93` passed those cases and the full regression.

## Known Stubs

None.

## Self-Check: PASSED

- All five modified production/test files exist.
- Task commits `5b684f0`, `d71becd`, `6f36acc`, and `1b97b93` exist in order.
- Every task acceptance criterion, both plan-level verification commands, the full suite, and Ruff passed after the final implementation commit.
- Stub scan found only intentional empty test collections/outputs and internal accumulator initialization; no goal-blocking placeholder exists.
- No new endpoint, authentication path, remote capability, executable external content, or unplanned schema trust boundary was introduced.

## Next Phase Readiness

- WR-02 exact-schema and CR-06 persisted-diagnostic gaps now have deterministic local evidence and sanitized failure behavior.
- Plan 01-10 can build on a schema and inspect boundary that fails closed before public reads, writes, or migration authority.
- No blockers remain from this plan.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*
