---
phase: 01-auditable-dry-run-spine
plan: "03"
subsystem: persistence
tags: [pydantic, sqlite, migration, manifests, retry, resume, inspect]

requires:
  - phase: 01-auditable-dry-run-spine/01-02
    provides: "Safe schema-v1 Walking Skeleton and frozen real Generator-interrupted database"
provides:
  - "Strict frozen stage, attempt, run, checkpoint and publication contracts"
  - "Transactional v1-to-v2 migration with rollback and Validators-first resume"
  - "Content-addressed manifests durable before result/checkpoint transactions"
  - "Digest-scoped finite retry, stale-attempt abandonment and persisted inspect JSON"
affects: [01-04-capability-firewall, phase-2-stage-contracts, operational-recovery]

tech-stack:
  added: []
  patterns: [strict frozen contracts, version-last transactional migration, manifest-before-database, digest-scoped retry]

key-files:
  created:
    - src/skillscout/domain/enums.py
    - src/skillscout/domain/models.py
    - src/skillscout/domain/canonical.py
    - tests/test_stage_contracts.py
    - tests/test_pipeline_resume.py
  modified:
    - src/skillscout/application/ports.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/adapters/fixtures.py
    - src/skillscout/adapters/state.py
    - src/skillscout/cli.py
    - tests/test_cli_dry_run.py

key-decisions:
  - "Preserve schema-v1 input, output and result identities byte-for-byte while using explicit schema-v2 preimages for new facts."
  - "Treat any input, producer or retry-policy mismatch as a new run rather than reusing an incompatible checkpoint."
  - "Count transient failures and abandoned attempts only through the canonical reusable-key index; permanent failures never receive a second invocation."

patterns-established:
  - "Every running attempt persists input_hash, producer_version, retry_policy_version and reusable_key_digest before processor invocation."
  - "Manifest bytes are fsynced and atomically replaced before one transaction inserts the result, succeeds the attempt and advances the checkpoint."
  - "Inspect output is reconstructed from SQLite and verified manifests, never process memory."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Strict immutable stage contracts and exact non-circular canonical identities are enforced."
    requirement: OPS-01
    verification:
      - kind: unit
        ref: "tests/test_stage_contracts.py (12 contract tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The real frozen v1 run migrates transactionally, preserves six identities and resumes first at Validators with full rollback evidence."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py migration, rollback and no-replay cases"
        status: pass
      - kind: other
        ref: "frozen database SHA-256 49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251"
        status: pass
    human_judgment: false
  - id: D3
    description: "Retry, resume and inspect are finite, digest-scoped and fully persisted."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py digest budget and identity-change cases"
        status: pass
      - kind: e2e
        ref: "tests/test_cli_dry_run.py#test_fresh_interruption_rerun_and_inspect_are_persisted"
        status: pass
    human_judgment: false

duration: 21 min
completed: 2026-07-17
status: complete
---

# Phase 1 Plan 03: Immutable Ledger, Migration and Recovery Summary

**Strict stage identities now survive a transactional real-v1 migration, back content-addressed manifests, and bound every retry and resume decision to persisted canonical evidence.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-17T06:02:04Z
- **Completed:** 2026-07-17T06:23:06Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- Added strict frozen Pydantic contracts, closed stage/status transitions and exact canonical input/output/manifest/retry identities.
- Migrated a temporary copy of the real Generator-interrupted schema-v1 CLI database under `BEGIN IMMEDIATE`, preserving its run ID, Generator checkpoint and six result hashes before resuming first at Validators.
- Made manifest durability precede the atomic result/attempt/checkpoint transaction and verified processor execution occurs outside database transactions.
- Added digest-indexed three-attempt retry exhaustion, permanent-error refusal, stale-running abandonment, identity-change isolation and persisted `inspect-run` JSON.

## Task Commits

Each TDD task has a RED commit followed by its GREEN implementation commit:

1. **Immutable envelopes and precomputed identity** — `0759b29` (RED), `8fce0b5` (GREEN)
2. **Transactional v1 migration and atomic manifests** — `4df1bc6` (RED), `ddfc8f4` (GREEN)
3. **Digest-scoped retry, resume and inspect** — `1b8ee2d` (RED), `e86cbec` (GREEN)

The plan metadata and this summary are committed separately by `docs(01-03)`.

## Files Created/Modified

- `src/skillscout/domain/enums.py` — fixed pipeline stages and legal lifecycle transitions.
- `src/skillscout/domain/models.py` — strict frozen inputs, envelopes, attempts, runs, checkpoints and summaries.
- `src/skillscout/domain/canonical.py` — sole canonical JSON encoder and exact SHA-256 preimages.
- `src/skillscout/adapters/state.py` — schema-v2 creation, v1 migration/rollback, manifests, retry index and inspect projection.
- `src/skillscout/application/pipeline.py` — verified resume, finite retry policy and identity-change isolation.
- `src/skillscout/cli.py` — `inspect-run RUN_ID --state PATH --format json`.
- `tests/test_stage_contracts.py` — immutable-model, transition and hash-preimage evidence.
- `tests/test_pipeline_resume.py` — real migration, rollback, durability, retry and no-reuse evidence.
- `tests/test_cli_dry_run.py` — fresh interruption/rerun/inspect end-to-end evidence.

## Migration and Rollback Evidence

- Frozen schema-v1 database SHA-256: `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251` before and after execution.
- Frozen facts: run `884039fcafca4757a194a9a69ca0e306`, status `interrupted`, Generator checkpoint index `5`, six attempts/results/checkpoints and zero Validators attempts.
- Successful copy migration reached `PRAGMA user_version = 2`, retained the original run and six output hashes, and invoked Validators, Reviewer and PublicationPlanner only.
- Forced failures after schema creation, row copy and validation each rolled back to `user_version = 1`, the four original tables, six readable results and no v2 manifest tree.
- Version `0`, malformed and future-version files failed `state_schema_incompatible` without byte replacement.

## Digest Budget Evidence

- Three transient Scout failures shared one `reusable_key_digest`; a fourth call returned `retry_exhausted` with processor invocation count still three.
- A stale running attempt became `abandoned` before monotonically increasing attempt `2` succeeded.
- A permanent failure was invoked once and refused on the next unchanged-digest call.
- Independent input, producer-version and retry-policy-version changes each created a distinct digest, received a fresh budget and refused incompatible checkpoint reuse.
- `EXPLAIN QUERY PLAN` confirmed retry counting uses `idx_attempts_reusable`.

## Decisions Made

- Schema-v1 canonical output and result preimages remain available solely for migration verification; new schema-v2 results include retry-policy identity in their deterministic result ID so distinct policy runs cannot collide in SQLite.
- Resume first validates every manifest plus the current canonical input/producer/retry identity. A mismatch creates a new run and leaves the interrupted audit record intact.
- `inspect-run` verifies manifest and embedded output hashes before emitting persisted rows with every nullable telemetry field explicit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Recreated the canonical retry index after table rename**
- **Found during:** Task 2/3 migration resume verification
- **Issue:** SQLite retained the temporary `idx_attempts_reusable_v2` name after table rename, so fail-closed retry queries using the canonical index name could not run on migrated state.
- **Fix:** Drop the temporary-name index after transactional table promotion and recreate `idx_attempts_reusable` on the final table before setting schema version 2.
- **Files modified:** `src/skillscout/adapters/state.py`
- **Verification:** Migrated Validators-first resume and indexed retry tests pass.
- **Committed in:** `e86cbec`

**2. [Rule 1 - Bug] Prevented schema-v2 result-ID collisions across retry policies**
- **Found during:** Task 3 retry-policy identity-change verification
- **Issue:** Two runs with identical semantic output but different retry-policy identity produced the same globally unique result ID.
- **Fix:** Persist retry-policy version on every envelope and include it in schema-v2 result identity while preserving the exact legacy schema-v1 preimage.
- **Files modified:** `src/skillscout/domain/models.py`, `src/skillscout/domain/canonical.py`, `src/skillscout/application/pipeline.py`, `src/skillscout/adapters/state.py`
- **Verification:** Retry-policy fresh-budget and no-reuse tests pass; frozen v1 result IDs remain unchanged.
- **Committed in:** `e86cbec`

---

**Total deviations:** 2 auto-fixed bugs. **Impact:** Both fixes preserve the planned audit and identity guarantees without broadening scope or capabilities.

## Issues Encountered

- The sandbox blocks uv's default user cache path; every verification was rerun with scoped permission using the unchanged repository-local uv, managed Python and `--locked` command contract.

## TDD Gate Compliance

- Task 1: RED `0759b29` → GREEN `8fce0b5`.
- Task 2: RED `4df1bc6` → GREEN `ddfc8f4`.
- Task 3: RED `1b8ee2d` → GREEN `e86cbec`.

## Verification

- Focused contract/migration/resume/CLI suite: **42 passed**.
- Ruff on all touched source and test files: **passed**.
- Full pytest suite: **42 passed**.
- Gate-B `uv.lock` SHA-256: `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32` — unchanged.
- Stub scan: no TODO, FIXME, placeholder, coming-soon or unavailable implementation marker.
- Capability scan: no HTTP, OpenAI, GitHub, socket, subprocess, merge or remote-publication client in `src/skillscout`.

## User Setup Required

None. This plan adds no service, credential or external runtime configuration.

## Next Phase Readiness

Plan 04 can now harden capability construction, malformed state/manifest handling and the final zero-network acceptance test on top of a strict, migrated and inspectable ledger.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-17*

## Self-Check: PASSED

- All five created files exist and all six plan commits are present.
- Both authoritative hashes match their approved/frozen values.
- The exact plan verification command and full suite pass with 42 tests.
- No tracked file was deleted and `.planning/config.json` remains excluded from task commits.
