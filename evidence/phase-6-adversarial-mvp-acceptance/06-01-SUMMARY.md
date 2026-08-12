---
phase: 06-adversarial-mvp-acceptance
plan: "01"
subsystem: testing
tags: [pytest, expected-red, acceptance-contracts, nyquist, security]

requires:
  - phase: 05-automated-discovery-operations
    provides: Bounded discovery, canonical operations state, protected publication, and deterministic acceptance-verifier patterns
provides:
  - Collectable expected-RED contracts for the complete Phase 6 acceptance domain
  - Evaluator-blind capability and exact DeepSeek Flash/Flash/Pro provider contracts
  - Exact 38-task validation, checkpoint, requirement, ownership, and hard-gate registries
affects: [06-02, 06-03, 06-04, 06-05, phase6-verification]

tech-stack:
  added: []
  patterns:
    - Exact named missing-contract RED nodes with independent pytest-output verification
    - Standard-library-only task, ownership, and hard-gate registries

key-files:
  created:
    - tests/fixtures/acceptance/scenario_matrix.json
    - tests/test_acceptance_domain.py
    - tests/test_acceptance_application.py
    - tools/verify_phase6_red_contracts.py
    - tools/verify_phase6_validation_map.py
    - tools/verify_phase6_acceptance.py
  modified:
    - tests/test_semantic_provider.py
    - .planning/phases/06-adversarial-mvp-acceptance/06-VALIDATION.md

key-decisions:
  - "Represent Wave 0 RED as exact named missing-contract failures while detailed behavior tests remain dormant only until their production module exists."
  - "Keep all 19 release gates blocking and make absent hosted, live, human, or report facts an explicit incomplete result."
  - "Assign every Phase 6 production surface one reachable owner and reject producer/consumer inversions before Wave 1."

patterns-established:
  - "Expected-RED verification: successful collection plus an exact failure-node and failure-message set; no traceback or infrastructure failure is accepted."
  - "Evaluator blindness: scenario labels and notes remain outside the canonical semantic payload."
  - "Ownership reachability: consumers may use a surface only from its owner plan or a transitive dependent plan."

requirements-completed: [TEST-01, TEST-02, TEST-03, TEST-04]

coverage:
  - id: D1
    description: Strict domain, hosted/offline, replay/update, attestation, and release-verdict RED contracts
    requirement: TEST-02
    verification:
      - kind: integration
        ref: ".tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_red_contracts.py --suite domain"
        status: pass
    human_judgment: false
  - id: D2
    description: Evaluator-blind orchestration and exact closed semantic-provider policy RED contracts
    requirement: TEST-04
    verification:
      - kind: integration
        ref: ".tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_red_contracts.py --suite application-provider"
        status: pass
    human_judgment: false
  - id: D3
    description: Exact Phase 6 task, checkpoint, requirement, surface-ownership, and hard-gate registries
    requirement: TEST-01
    verification:
      - kind: other
        ref: ".tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py --plan-contract"
        status: pass
      - kind: other
        ref: ".tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py --registry-only"
        status: pass
    human_judgment: false

duration: 12 min
completed: 2026-07-29
status: complete
---

# Phase 6 Plan 1: Acceptance Contract and Validation Map Summary

**A collectable expected-RED acceptance suite now freezes 25 missing production contracts, evaluator-blind provider boundaries, and an independently verified 38-task ownership map before Phase 6 implementation begins.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-29T06:09:11Z
- **Completed:** 2026-07-29T06:20:56Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Added an 18-case bounded synthetic scenario matrix and strict future behavior contracts for benchmark, hosted isolation, offline adversarial execution, replay/update completion, human review, calibration, and release gates.
- Added capability-signature and provider-policy RED contracts that require separate orchestration surfaces, evaluator-blind semantic payloads, exact Flash/Flash/Pro routing, the official DeepSeek endpoint, no tools, and zero SDK retries.
- Finalized and independently verified all 38 Phase 6 tasks, TEST-01..TEST-04 forward/inverse coverage, nine checkpoint chains, 69 owned surfaces, 13 Wave 0 file owners, and 19 non-waivable hard gates.

## Task Commits

Each task was committed atomically:

1. **Task 06-01-01: Freeze strict benchmark, evidence, gate, and attestation contracts** - `d3187f4` (test)
2. **Task 06-01-02: Freeze evaluator-blind orchestration and closed provider policy** - `92cebf2` (test)
3. **Task 06-01-03: Finalize and independently verify the exact Phase 6 validation map** - `aab6865` (test)

## Files Created/Modified

- `tests/fixtures/acceptance/scenario_matrix.json` - Ordered bounded synthetic scenario and mutation instructions.
- `tests/test_acceptance_domain.py` - Deferred-import strict acceptance domain RED contracts and mutation matrix.
- `tests/test_acceptance_application.py` - Capability separation, terminal taxonomy, and evaluator-blind request contracts.
- `tests/test_semantic_provider.py` - Exact stage/model mapping and invalid-pair pre-transport contracts.
- `tools/verify_phase6_red_contracts.py` - Exact collectable expected-RED verifier for domain and application/provider suites.
- `tools/verify_phase6_validation_map.py` - Read-only parser for all plans, task rows, checkpoint links, inverse coverage, and ownership reachability.
- `tools/verify_phase6_acceptance.py` - Initial fixed hard-gate registry that fails all non-registry acceptance modes until evidence exists.
- `.planning/phases/06-adversarial-mvp-acceptance/06-VALIDATION.md` - Finalized task map, checkpoint chains, surface registry, and Wave 0 file ownership.

## Decisions Made

- Missing production contracts are explicit named failures, not collection errors or broad xfails; detailed contract tests activate when the owning production module exists.
- Expected outcome, coverage role, evaluator notes, and human labels remain evaluator-only metadata and cannot enter serialized semantic requests.
- Hosted/live/human facts remain absent and release-blocking; Wave 0 records no repository, SHA, approval, run, credential, or evidence value.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pytest 9's `--tb=no` summary omitted failure messages needed for exact RED auditing. The verifier was changed to `--tb=line`, missing imports were detected without raising import tracebacks, and node/message sets are now checked independently.
- The sandbox initially blocked the user-level uv cache and Git index lock. The same locked commands and normal Git hooks were rerun with the required filesystem authorization; no verification or hook was bypassed.

## Known Stubs

None. Missing Phase 6 production modules are the intentional, verifier-enforced RED state owned by Plans 06-03 through 06-05, not shipped stubs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 06-02 can add the remaining Wave 0 adversarial, workflow, source-execution, and independent-rebuild contracts against the exact map.
- `nyquist_compliant:false` and `wave_0_complete:false` intentionally remain unchanged until both Wave 0 plans have execution evidence.
- No live credential, hosted run, benchmark selection, publication, human verdict, or cleanup authority was exercised.

## Self-Check: PASSED

- All eight created/modified plan files exist.
- Task commits `d3187f4`, `92cebf2`, and `aab6865` exist in Git history.
- Both expected-RED suites, the plan-contract verifier, the hard-gate registry, 120-node collection, Ruff, and `git diff --check` passed.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-07-29*
