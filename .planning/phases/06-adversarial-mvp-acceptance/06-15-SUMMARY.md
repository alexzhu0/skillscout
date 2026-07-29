---
phase: 06-adversarial-mvp-acceptance
plan: "15"
subsystem: workflow-security
tags: [github-actions, source-execution, uv, fail-closed, publication]

requires:
  - phase: 06-02
    provides: Wave 0 source-execution mutation contracts and the retained isolation-probe job
  - phase: 06-03
    provides: Closed Flash/Flash/Pro semantic-provider authority
  - phase: 06-04
    provides: Typed acceptance facts and canonical operations-owned persistence
provides:
  - Four-workflow same-job full-SHA checked-out-source execution contract
  - Closed Phase 6 action grammar with separated credential and effect zones
  - Standard-library-only fail-closed verifier plus launcher mutation coverage
affects: [06-06, 06-07, 06-08, 06-09, 06-10, gate-b4, publication]

tech-stack:
  added: []
  patterns:
    - Same-job full-SHA checkout, exact setup-uv, repository-local materialization, and direct run --locked
    - Constrained ordered workflow parser with closed authoritative-entry grammar

key-files:
  created:
    - tools/verify_phase6_source_execution.py
  modified:
    - .github/workflows/phase6-acceptance.yml
    - .github/workflows/discover.yml
    - .github/workflows/publish-candidate.yml
    - .github/workflows/gate-b4-canary.yml
    - tests/test_phase5_acceptance.py
    - tests/test_publication_security.py
    - tests/test_phase6_workflow.py
    - tests/test_discovery_workflow.py

key-decisions:
  - "Recognize only direct python -m skillscout, inline skillscout imports, and python tools/*.py as authoritative workflow entry forms; every unknown form fails closed."
  - "Keep catalog credentials exclusively in value_publication after fresh_gate_b4, while nomination, semantic, attestation, rebuild, and isolation jobs retain separate minimum authority."
  - "Preserve isolation_probe as the Plan 06-02 contract while widening only the closed phase6_action grammar and exact job registry."

patterns-established:
  - "Authoritative workflow execution: checkout current github.sha with credentials disabled, pin setup-uv 0.11.29, copy and verify local uv, then invoke checked-out source directly with run --locked."
  - "Workflow mutation defense: reject package/artifact acquisition, PATH-only launchers, external cwd, variables, aliases, functions, sourced/delegated wrappers, indirect scripts, and empty scans."

requirements-completed: [TEST-01, TEST-03, TEST-04]

coverage:
  - id: D1
    description: All four authoritative workflows execute SkillScout and repository tools only from the same-job checked-out locked source.
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "tests/test_phase6_source_execution.py (29 passed)"
        status: pass
      - kind: other
        ref: ".tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py"
        status: pass
    human_judgment: false
  - id: D2
    description: Phase 6 actions isolate nomination, offline, semantic, publication, attestation, cleanup, and rebuild authority with catalog access only after the fresh gate.
    requirement: TEST-03
    verification:
      - kind: integration
        ref: "tests/test_phase6_workflow.py#test_phase6_actions_and_jobs_have_closed_authority_zones"
        status: pass
      - kind: integration
        ref: "affected workflow regression (86 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: Publication and discovery launchers require full-SHA checkout, exact local uv materialization, and direct locked-source invocation.
    requirement: TEST-04
    verification:
      - kind: integration
        ref: "tests/test_publication_security.py and tests/test_discovery_workflow.py"
        status: pass
      - kind: other
        ref: "ruff check and ruff format --check over changed Python files"
        status: pass
    human_judgment: false
  - id: D4
    description: Historical Phase 5 acceptance is tested against its exact Gate-B4-bound workflow bytes while the current Phase 6 tree fails closed pending fresh evidence.
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "tests/test_phase5_acceptance.py (25 passed)"
        status: pass
      - kind: integration
        ref: "full locked pytest (2080 passed, 32 skipped, 2 planned future Phase 6 RED failures)"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-29
status: complete
---

# Phase 6 Plan 15: Pre-Gate-B4 Workflow Authority Summary

**Four authoritative GitHub workflows now execute only same-job checked-out source through verified repository-local uv 0.11.29, with closed Phase 6 authority zones and mutation-tested fail-closed admission**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-29T08:06:42Z
- **Completed:** 2026-07-29T08:15:48Z
- **Tasks:** 1
- **Files modified:** 8

## Accomplishments

- Expanded `phase6-acceptance.yml` to the exact ten-action grammar and ten isolated jobs while preserving the existing credential-free `isolation_probe`.
- Converted discover, controlled publish, Gate B4 canary, and Phase 6 authoritative entry points to same-job full-SHA checkout plus verified repository-local locked uv execution.
- Added a network-free, project-import-free verifier that parses ordered job steps and rejects alternate acquisition, wrapper, external-directory, mutable, indirect, unknown, and empty-scan routes.
- Extended publication, discovery, and Phase 6 workflow tests so older security contracts continue to validate the stricter local-source baseline.

## Task Commits

The task was committed atomically:

1. **Task 06-15-01 GREEN: protected workflow zones and locked source execution** - `bd8f749` (feat; RED inherited from the 06-02 Wave 0 contract)

Post-merge regression repair was committed separately under strict TDD:

2. **RED: expose the mixed Phase 5 workflow/evidence lifecycle** - `279c7f0` (test; observed failing exact-digest contract)
3. **GREEN: separate historical and current workflow lifecycles** - `1fa3f49` (fix; test-harness-only)

## Files Created/Modified

- `.github/workflows/phase6-acceptance.yml` - Defines the closed action grammar and separated nomination, offline, semantic, publication, attestation, cleanup, and rebuild jobs.
- `.github/workflows/discover.yml` - Materializes and verifies local uv in both jobs and directly runs checked-out discovery/publication source.
- `.github/workflows/publish-candidate.yml` - Adds current-SHA checkout, pinned uv setup, local materialization, and direct locked admission/publication launchers.
- `.github/workflows/gate-b4-canary.yml` - Runs both canary phases through verified repository-local locked source.
- `tools/verify_phase6_source_execution.py` - Independently validates the exact four-workflow set and returns typed invocation evidence.
- `tests/test_publication_security.py` - Owns the updated protected publication launcher and action-pin contract.
- `tests/test_phase6_workflow.py` - Preserves isolation assertions while freezing the expanded action/job authority zones.
- `tests/test_discovery_workflow.py` - Updates the historical discovery security audit for the stricter local uv source path.

## Decisions Made

- The verifier does not trust general YAML or shell interpretation. It accepts one constrained ordered workflow shape and three explicit authoritative entry classes, then fails closed on every other form.
- `value_publication` is the only Phase 6 acceptance job that can mint the fixed-catalog App token, and it is ordered after `fresh_gate_b4`.
- Candidate, evaluator, attestation, and state identities enter shell commands only through fixed files and bounded environment variables; workflow-dispatch input is used only in job-level closed equality conditions.
- Existing Phase 5 Gate B4 hashes are historical after these planned pre-Gate workflow changes. A fresh Gate B4 must bind the final bytes after Plan 06-06's one permitted offline-job change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced dynamically imported dataclasses with immutable NamedTuple contracts**
- **Found during:** Task 06-15-01 GREEN
- **Issue:** The Wave 0 loader uses `module_from_spec` without inserting the module into `sys.modules`; Python 3.13 dataclass annotation processing therefore failed before verification.
- **Fix:** Kept the same immutable fields and attribute API using `NamedTuple`, which is safe under the existing dynamic loader.
- **Files modified:** `tools/verify_phase6_source_execution.py`
- **Verification:** All 29 source-execution tests, including every mutation, passed.
- **Committed in:** `bd8f749`

**2. [Rule 3 - Blocking] Updated superseded workflow-owner tests for the stricter source contract**
- **Found during:** Task 06-15-01 GREEN regression
- **Issue:** Plan 06-02 still asserted that the Phase 6 workflow contained only `isolation_probe`, and the Phase 5 discovery test explicitly forbade repository-local uv.
- **Fix:** Scoped isolation secrecy assertions to the preserved job, froze the exact expanded job set, and replaced the obsolete PATH-only uv expectation with same-job local materialization assertions.
- **Files modified:** `tests/test_phase6_workflow.py`, `tests/test_discovery_workflow.py`
- **Verification:** The affected workflow regression passed with 86 tests; the plan command passed with 52 tests and 12 unrelated deselections.
- **Committed in:** `bd8f749`

**3. [Rule 1 - Bug] Restored the historical Phase 5 acceptance fixture lifecycle**
- **Found during:** Wave 3 post-merge full-suite verification
- **Issue:** `tests/test_phase5_acceptance.py` copied the current Phase 6-modified workflow bytes while retaining Phase 5 Gate B4 evidence bound to the prior discover, publish, and canary digests, so the positive fixture mixed two valid but incompatible lifecycles.
- **Fix:** Added a RED exact-digest fixture contract, restored only the three historical Gate-B4-bound workflow byte sequences inside the positive fixture, and added a separate current-tree test that fails closed until fresh Gate B4 evidence exists.
- **Files modified:** `tests/test_phase5_acceptance.py`
- **Verification:** The RED test failed with all three current digests, then passed after the fix; all 25 Phase 5 acceptance tests and all 29 Phase 6 source-execution tests passed; the independent Phase 6 verifier reported `phase6 source execution valid`; full locked pytest reported 2,080 passed, 32 skipped, and only the two planned future Phase 6 RED failures.
- **Committed in:** `279c7f0` (RED), `1fa3f49` (GREEN)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking issue)
**Impact on plan:** The original two fixes were necessary to execute the pre-existing RED contract and preserve prior security ownership under the stricter planned baseline. The post-merge fix restores historical Phase 5 fixture correctness without changing the verifier, evidence, approval, or current workflow bytes. No dependency, remote effect, credential scope, or candidate execution authority was added.

## Issues Encountered

- The sandbox initially denied uv cache and Git index-lock access. The exact locked commands and normal commit hooks were rerun with approved filesystem access; no dependency was installed or changed.
- Workflow byte changes intentionally stale historical Phase 5 Gate B4 digests. No Gate B4, publication, remote dispatch, candidate repository execution, or credential inspection occurred in this plan.
- Wave 3 post-merge verification exposed a test-harness lifecycle mismatch: historical Phase 5 evidence had been paired with current Phase 6 workflow bytes. The verifier correctly failed closed; no production verifier, evidence, approval, or workflow byte was changed.

## Authentication Gates

None.

## Known Stubs

None. The scan found no placeholder, TODO, FIXME, empty UI data source, or unimplemented authoritative workflow route.

## User Setup Required

None - no new dependency or external service configuration is required by this plan.

## Next Phase Readiness

- Plan 06-06 may make only its already planned final source-only `offline_adversarial` job change, then must rerun the four-workflow verifier and freeze all four files.
- Plans 06-07 through 06-09 can execute or read the frozen workflow without changing its bytes.
- Fresh Gate B4 and value publication remain unauthorized until later checkpoints bind the exact post-06-06 workflows and fixed catalog identity.

## Self-Check: PASSED

- All eight created/modified task files exist.
- Task commit `bd8f749` exists in Git history and contains no file deletions.
- The exact plan verification passed with 52 tests and 12 unrelated deselections.
- The wider affected workflow regression passed with 86 tests.
- The independent source-execution verifier reported `phase6 source execution valid`.
- Ruff check, Ruff format check, and `git diff --check` passed.
- Stub and threat-surface scans found no untracked placeholder or threat outside the plan's T-06-47, T-06-48, T-06-49, and T-06-SC register.
- Post-merge RED commit `279c7f0` and GREEN commit `1fa3f49` exist and modify only `tests/test_phase5_acceptance.py`.
- The targeted lifecycle test and all 25 Phase 5 acceptance tests passed while preserving the external-cwd and read-only metadata assertions.
- All 29 Phase 6 source-execution tests passed, and the independent verifier reported `phase6 source execution valid`.
- Full locked pytest completed with 2,080 passed, 32 skipped, and only the two planned future Phase 6 RED nodes failing; no Phase 5 regression remains.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-07-29*
