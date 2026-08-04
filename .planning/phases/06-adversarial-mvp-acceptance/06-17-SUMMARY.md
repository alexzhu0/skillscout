---
phase: 06-adversarial-mvp-acceptance
plan: "17"
subsystem: acceptance
tags: [live-authority-v2, state-only, github-actions, admission, fail-closed]

requires:
  - phase: 06-16
    provides: Rebuilt V2 benchmark-lock facts and redacted fixed-host approval evidence
provides:
  - Purpose-bound V2 live-execution authority facts, while V1 remains historical-only
  - Checked-out carrier re-admission before runtime/provider/state composition
  - Closed state-only recorder using only fixed-host Actions approval history
affects: [06-18-protected-route, phase6-live-benchmark, phase6-replay]

key-files:
  modified:
    - src/skillscout/domain/acceptance.py
    - src/skillscout/adapters/operations_state.py
    - src/skillscout/application/acceptance.py
    - src/skillscout/bootstrap.py
    - src/skillscout/cli.py
    - tests/test_acceptance_domain.py
    - tests/test_operations_state.py
    - tests/test_phase6_acceptance.py
    - tests/test_cli_security.py

key-decisions:
  - "Fresh live execution accepts only LiveAcceptanceAuthorityV2 bound to a rebuilt LockedBenchmarkManifestV2 and a purpose=live_execution receipt."
  - "The public record-live-authority surface accepts only acceptance-run-id; authority JSON, actor, comment, receipt, and endpoint inputs are absent."
  - "Benchmark/replay first rebuild a V2 authority from a checked-out authority carrier, before runtime configuration or any state/provider/source credential path."

verification:
  focused_contract_state: "8 passed, 133 deselected"
  focused_admission: "9 passed, 134 deselected"
  focused_recorder_cli: "22 passed, 173 deselected"
  ruff: "passed"
  plan_task3_full_filter: "blocked by pre-existing V1 process-harness setup missing its required V1 benchmark-lock fact; 9 passed before the first failure"

completed: 2026-08-04
status: complete
---

# Phase 6 Plan 17: V2 Live Authority Summary

**Fresh benchmark and replay admission now starts from a separately versioned V2 authority reconstructed from state, not from a caller-supplied authority document.**

## Accomplishments

- Added strict `LiveAcceptanceAuthorityV2` and `LiveExecutionApprovalReceiptV2` contracts while retaining the V1 parser and state schema as historical evidence.
- Added explicit schema-version state restore and V2 lock/nomination/selection re-admission.  Historical V1 facts remain parseable but cannot satisfy the fresh admission seam.
- Added `record_live_authority` V2 type enforcement and a closed bootstrap recorder.  It validates exact checked-out source bytes and the current rebuilt V2 lock before it creates the fixed-host Actions approvals client; it retains only redacted approval identity fields and performs the authority-carrier CAS followed by an exact rebuild check.
- Removed caller-controlled record flags.  `record-live-authority` takes only `--acceptance-run-id`; no actor, approval comment, authority JSON, endpoint, or free-form receipt channel exists.
- Added the V2 carrier-checkout gate to `run-acceptance` before runtime configuration and state restoration.  The execution builder re-runs the closed V2 admission against the restored local operations snapshot before it builds discovery/provider composition.
- Extended downstream scenario, budget, fixed-candidate, and resume validation to resolve a V2 lock through its immutable V1 selection preimage without reclassifying V1 history as fresh authority.
- Post-review hardening made V2 admission mandatory for both runtime configuration and public live-execution composition.  The fixed repository runner and application benchmark path now reject historical V1 authority facts before discovery, provider, source, or state capability composition.
- Rebuild validation now invokes V2 live-authority cardinality checks, so a self-consistent export containing two different V2 authority facts is rejected rather than allowing a caller-selected digest.

## Task Commits

1. **Task 1 — V2 contract/state registry:** `db745d8`, `381f0d7`
2. **Task 2 — V2 re-admission guard:** `e055262`, `2499039`, `4dc2900`
3. **Task 3 — closed recorder and CLI wiring:** `879e278`, `b3e6851`

## Verification

- Contract/state filter: `8 passed, 133 deselected`.
- V2 admission filter: `9 passed, 134 deselected`.
- Recorder/CLI/admission narrowed filter: `22 passed, 173 deselected`.
- Post-review V2 contract/state filter: `9 passed, 133 deselected`.
- Post-review V2 admission/production filter: `12 passed, 134 deselected`; full application suite: `28 passed`; full CLI security suite: `51 passed`.
- Ruff passed for all modified implementation and test files.

The plan's literal Task 3 keyword filter was also run. It reached ten passing tests and then encountered the pre-existing Phase 6 process-harness defect: the harness tries to persist a historical V1 live authority without its required V1 benchmark-lock fact. The same strict historical reference check existed before this plan; this work intentionally did not weaken it. No provider, source, state-branch, GitHub, or workflow action was performed during this implementation or verification.

## Deviations

- No workflow bytes were changed. The newly required immutable authority-carrier checkout inputs are intended for Plan 06-18's protected route to supply.
- No live approval lookup, credential inspection, provider call, source-repository operation, state-branch mutation, or publication action was performed.

## Next Phase Readiness

Plan 06-18 can wire the protected environment job to the closed `record-live-authority` command and pass the immutable authority-carrier checkout to benchmark/replay. Any V1 authority or caller-supplied authority representation remains unable to reach the fresh V2 execution admission path.
