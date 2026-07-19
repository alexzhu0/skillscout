---
phase: 01-auditable-dry-run-spine
plan: "10"
subsystem: local-state
tags: [sqlite, canonical-identity, verification, migration, resume, inspect, tdd]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: exact schema-v2 fingerprint, sanitized persisted projections, run-scoped result rows, exact RunIdentity, and transactional migration
provides:
  - One typed full-chain verifier for bound run, attempt, result, checkpoint, and manifest evidence
  - Exact closed PipelineStage prefix and one-to-one result/checkpoint cardinality enforcement
  - Schema-specific semantic result identity recomputation for historical v1 and retry-aware v2 evidence
  - Transactional legacy identity binding that grants authority only after complete current-identity proof
  - Shared verifier routing for resume, latest checkpoint, completed-result verification, and inspect
affects: [state-integrity, pipeline-resume, inspect-run, schema-v1-migration, phase-01-verification]

tech-stack:
  added: []
  patterns:
    - verified domain chain as the sole authority-bearing persisted projection
    - candidate-transaction verification before legacy identity promotion
    - schema-version-specific canonical preimages preserved across migration and resume

key-files:
  created: []
  modified:
    - src/skillscout/domain/models.py
    - src/skillscout/application/ports.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/adapters/state.py
    - tests/test_state_integrity.py
    - tests/test_pipeline_resume.py
    - tests/test_cli_dry_run.py

key-decisions:
  - "Return VerifiedRunChain only for identity_state=bound and reject legacy_unbound before any authority-bearing stage projection."
  - "Keep pre-promotion legacy validation separate and non-authorizing because fixture_hash is unavailable until a caller supplies the exact current RunIdentity."
  - "Make resume selection, latest checkpoint, completed verification, and inspect consume the same full-chain proof rather than maintaining weaker record-specific loops."
  - "Preserve the historical schema-v1 semantic result preimage for both migrated evidence and stages completed after migration."

patterns-established:
  - "Trust-path convergence: every bound-state authority decision delegates to verify_run_chain."
  - "Legacy promotion: bind in a private serialized candidate, prove the complete chain, then durably commit."
  - "Canonical chain: rebuild StageInput from exact RunIdentity plus the preceding verified output before comparing every persisted duplicate."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "A single typed verifier recomputes and cross-binds every canonical run, attempt, result, checkpoint, and manifest field across valid complete and interrupted chains."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_verify_run_chain_returns_one_typed_closed_prefix"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_full_chain_rejects_each_duplicated_persisted_field_tamper"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_full_chain_rejects_result_checkpoint_order_and_cardinality_damage"
        status: pass
    human_judgment: false
  - id: D2
    description: "Resume, latest checkpoint, completed-result verification, and inspect reject the same coherent forgery through one verifier without state mutation or partial projection."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_every_bound_trust_entry_point_delegates_to_one_full_chain_verifier"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_forged_semantic_result_is_rejected_consistently_by_every_trust_path"
        status: pass
      - kind: e2e
        ref: "tests/test_cli_dry_run.py#test_corrupt_chain_blocks_inspect_and_resume_without_output_or_mutation"
        status: pass
    human_judgment: false
  - id: D3
    description: "Legacy evidence remains non-authorizing until exact transactional binding, then resumes at Validators under historical schema-v1 canonical identity."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_legacy_binding_verifies_a_private_candidate_before_durable_promotion"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_migrated_frozen_run_resumes_at_validators_without_replay"
        status: pass
      - kind: other
        ref: "shasum -a 256 tests/fixtures/state/v1-cli.db"
        status: pass
    human_judgment: false

duration: 19min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 10: Complete Canonical Run-Chain Verification Summary

**One bound-only `VerifiedRunChain` now recomputes the complete canonical ledger and is the sole proof used by recovery, completed verification, legacy promotion, and inspect.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-07-19T06:58:39Z
- **Completed:** 2026-07-19T07:17:15Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added strict `VerifiedRunChain` output containing validated run identity, all persisted attempts, ordered result envelopes, and one-to-one checkpoints without exposing SQLite rows.
- Added a central verifier that rebuilds every `StageInput`, input hash, reusable digest, output hash, schema-specific semantic result ID, run-scoped row ID, manifest hash, locator, stage prefix, and duplicated association.
- Added 29 persisted-field tamper cases plus coherent manifest rehash, prior-output chain, order, missing/extra result, and missing/extra checkpoint regressions.
- Routed exact resumable lookup, latest checkpoint, completed-result verification, and inspect through the same proof and removed the weaker bound-state identity loop.
- Split non-authorizing legacy migration validation from transactional exact-identity binding; wrong fixture identity rolls back unchanged, while exact binding enables full inspect and Validators-first resume.

## Task Commits

Each TDD task was committed with a failing test gate followed by its implementation:

1. **Task 01-10-01: Build one full run-attempt-result-checkpoint-manifest verifier** - `39948ac` (test), `a31c3e2` (feat)
2. **Task 01-10-02: Route every trust decision through the full-chain verifier** - `0e73941` (test), `d3ab3a6` (feat)

**Plan metadata:** committed with this summary and tracking update.

## Files Created/Modified

- `src/skillscout/domain/models.py` - Bound-only typed `VerifiedRunChain` contract.
- `src/skillscout/application/ports.py` - Provider-independent full-chain verifier method on `StateStore`.
- `src/skillscout/application/pipeline.py` - Historical schema-v1 result preimage preserved for post-migration stages.
- `src/skillscout/adapters/state.py` - Central canonical verifier, non-authorizing legacy-copy validator, transactional binding, and converged trust paths.
- `tests/test_state_integrity.py` - Field-by-field, coherent-rehash, prior-chain, order/cardinality, and trust-entry consistency matrix.
- `tests/test_pipeline_resume.py` - Candidate-transaction binding, typed port, frozen migration, and canonical lifecycle evidence.
- `tests/test_cli_dry_run.py` - Sanitized, non-mutating corruption rejection across inspect and resume.

## Decisions Made

- `legacy_unbound` may be structurally migrated and validated, but it can never produce `VerifiedRunChain`, authorize resume, or expose full inspect data.
- Exact expected identity is applied only inside a private serialized candidate. The full verifier must pass before candidate bytes replace durable state.
- Attempts without results remain valid only at the next prefix position and must still carry the exact canonical input and reusable identity; each completed position has exactly one succeeded associated attempt.
- A planned-not-published run must have all nine exact stages. Non-terminal runs may carry only a contiguous closed prefix.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved historical schema-v1 result identity after migration**
- **Found during:** Task 2 frozen Validators-first recovery verification
- **Issue:** Newly completed stages on a migrated schema-v1 run used the schema-v2 retry-aware semantic result preimage, so the central verifier correctly rejected the mixed chain at final checkpoint verification.
- **Fix:** `PipelineRunner` now passes no retry-policy field to `make_result_id` for schema version 1 while retaining the current retry-aware preimage for schema version 2.
- **Files modified:** `src/skillscout/application/pipeline.py`
- **Verification:** Frozen v1 migration binds, resumes first at Validators, completes, and passes full-chain verification; all 195 tests pass.
- **Committed in:** `d3ab3a6`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).
**Impact on plan:** The fix is required for the plan's explicit schema-v1 historical-preimage guarantee and introduces no new scope or authority.

## Issues Encountered

- The managed sandbox could not read the existing user-level uv cache. Locked offline verification was run through narrowly approved repository-local `uv run --locked` commands with `UV_PYTHON_DOWNLOADS=never`; no dependency installation or network access occurred.

## User Setup Required

None - no external service configuration required.

## Verification Evidence

- Task 1 RED: 38 new cases failed specifically because `verify_run_chain` did not exist.
- Task 1 GREEN: 38 new cases passed; the plan keyword gate reported `42 passed, 29 deselected`.
- Task 2 focused trust-path gate: 6 passed after shared routing and schema-v1 correction.
- Exact integrity/recovery/CLI suites: `126 passed`.
- Full locked offline regression: `195 passed`.
- Repository-wide Ruff lint: all checks passed.
- `uv.lock` SHA-256 remained `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256 remained `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`.
- `.planning/config.json` remained byte-identical with SHA-256 `5c5acc837fef244afd431f542223618d8abd043eb77b0ef9e08b98267d9d3219` and was never staged.

## TDD Gate Compliance

- Task 1 RED `39948ac` preceded GREEN `a31c3e2`; all 38 new verifier cases moved from the missing-contract failure to green.
- Task 2 RED `0e73941` preceded GREEN `d3ab3a6`; all bound trust paths, candidate binding, typed-port, and CLI non-mutation checks pass.

## Known Stubs

None.

## Self-Check: PASSED

- All seven modified production/test files exist.
- Task commits `39948ac`, `a31c3e2`, `0e73941`, and `d3ab3a6` exist in RED/GREEN order.
- Every task acceptance criterion, both plan-level verification commands, the full suite, Ruff, frozen fixture hash, lock hash, and config-preservation check passed.
- Stub scan found only intentional empty test collections, nullable initialization, and explicit no-output assertions; no goal-blocking placeholder exists.
- No new endpoint, authentication path, remote capability, executable external content, schema change, or unplanned trust boundary was introduced.

## Next Phase Readiness

- CR-05 and verification root gap 3 now have one deterministic, bound-only canonical proof across all trust paths.
- Plan 01-11 can build final adversarial acceptance on consistent corruption failures, exact migration binding, and closed inspect/resume behavior.
- No blockers remain from this plan.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*
