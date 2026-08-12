---
phase: 03-validated-skill-candidate
plan: "07"
subsystem: domain
tags: [qualification, deterministic-policy, pydantic, canonical-json, authority, tdd]

requires:
  - phase: 03-05
    provides: Complete WorkflowSpec and CandidateExecutionAuthorityV1 contracts
  - phase: 03-06
    provides: Strict verified Phase 2 candidate source projection
  - phase: 03-04
    provides: Gate B3 dependency equality preflight
provides:
  - Versioned deterministic five-dimension qualification policy with a closed hard-failure matrix
  - Fixed 75/100 no-hard-failure eligibility predicate
  - Canonical strict QualificationReportV1 directly binding complete source and execution authorities
affects: [03-08, 03-09, 03-10, 03-11, 03-12, phase3-ledger, candidate-generation]

tech-stack:
  added: []
  patterns:
    - Code-owned immutable policy constants with no caller-supplied runtime override
    - Closed item and reason vocabularies validated by strict frozen Pydantic contracts
    - Direct complete authority embedding plus canonical report bytes and digest

key-files:
  created:
    - src/skillscout/domain/qualification.py
    - tests/test_qualification.py
  modified: []

key-decisions:
  - "Treat WorkflowSpec workflow-level evidence as the complete authoritative registry against which every step reference path, blob SHA, and content hash is reconciled."
  - "Keep qualification weights, the 0.70 confidence floor, the 75 threshold, and every schema/policy version as code-owned constants with no runtime or caller override."
  - "Embed the selected full fingerprint, complete WorkflowSpecAuthorityV1, and complete CandidateExecutionAuthorityV1 directly in the report header and reject any stale or cross-candidate combination."

patterns-established:
  - "Qualification runs as one pure deterministic transform over structured WorkflowSpec fields; it imports no model, filesystem, network, validator, or raw-source boundary."
  - "Report construction canonicalizes the exact five-item order, while strict validation recomputes totals, hard-failure state, pass status, and aggregate reasons."

requirements-completed: [QUAL-01, QUAL-02]

coverage:
  - id: D1
    description: "Every candidate receives independently itemized deterministic checks for specificity, reusability, verifiability, evidence sufficiency, and unauthorized execution risk under fixed versioned policy."
    requirement: QUAL-01
    verification:
      - kind: unit
        ref: "tests/test_qualification.py -k checks (23 policy, confidence-boundary, hard-failure, and determinism cases)"
        status: pass
      - kind: integration
        ref: "Gate-B3-prefixed full pytest suite (827 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "QualificationReportV1 enforces the exact 75/100 no-hard-failure rule and directly binds every complete source/execution authority with stable canonical bytes."
    requirement: QUAL-02
    verification:
      - kind: unit
        ref: "tests/test_qualification.py (44 total policy/report boundary and strictness cases)"
        status: pass
      - kind: integration
        ref: "Protected candidate authority, lineage, source, and extractor regression set (161 passed)"
        status: pass
    human_judgment: false

duration: 13 min
completed: 2026-07-23
status: complete
---

# Phase 03 Plan 07: Deterministic Qualification Policy and Report Summary

**Five fixed qualification dimensions now produce an authority-bound canonical report whose 75/100 decision can never override a closed hard failure.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-07-23T10:23:19Z
- **Completed:** 2026-07-23T10:35:47Z
- **Tasks:** 2/2
- **Implementation/test files:** 2

## Accomplishments

- Added a pure versioned policy with exact 25/20/20/25/10 weights, a 0.70 evidence-confidence floor, independent item scores, and a closed deterministic reason vocabulary.
- Added hard failures for short or empty contracts, incomplete or mismatched evidence authority, credential/destructive/bypass/injection behavior, unnamed approval side effects, source execution, dependency installation, repository script invocation, download-and-execute, and other closed unauthorized capabilities.
- Added strict frozen report/header contracts that directly embed the selected fingerprint and complete WorkflowSpec/execution authorities, recompute totals and pass state, canonicalize items and reasons, and provide stable persistence bytes/digests.
- Proved the 74/75 boundary, 100-with-hard-failure rejection, full header sensitivity, policy-version ownership, cross-candidate swap rejection, malformed-report rejection, and canonical permutation stability.

## Task Commits

Each TDD task was committed with RED before GREEN:

1. **Task 1 RED: Versioned qualification policy contracts** - `605c5a5` (`test`)
2. **Task 1 GREEN: Deterministic five-dimension checks** - `5a5c627` (`feat`)
3. **Task 2 RED: Strict authority-bound report contracts** - `6ddf26b` (`test`)
4. **Task 2 GREEN: Canonical threshold report and digest** - `8fa96ca` (`feat`)

## Files Created/Modified

- `src/skillscout/domain/qualification.py` - Policy constants, check/report models, evidence and safety evaluation, exact threshold constructor, and canonical bytes/digest.
- `tests/test_qualification.py` - Weight, confidence, every hard-failure, score boundary, direct authority, canonicalization, strictness, mutation, and swap coverage.

## Decisions Made

- Workflow-level `WorkflowSpec.evidence` is the closed evidence membership authority. Step references must resolve by path and match both blob SHA and content hash; model text cannot assert its own authority.
- Safety detection examines only positive semantic/action fields. `prohibited_actions` and `non_goals` remain controls rather than being misread as requested dangerous behavior.
- Side-effect-shaped workflow text is safe only when an ordered step explicitly names a human/reviewer/operator/owner/maintainer/security/team approval; a free-standing `required_approvals` claim cannot substitute for the named step.
- Qualification and threshold versions are immutable code authority. A policy change requires a version/code change and therefore changes the complete prelookup execution authority.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Harness] Matched the first applicable authority-rejection diagnostic**
- **Found during:** Task 2 GREEN
- **Issue:** The cross-candidate test required the later `workflow authority` diagnostic, but the stricter header validator correctly rejected the swapped execution authority earlier at the selected-fingerprint binding.
- **Fix:** Asserted the stable bounded `authority disagree` diagnostic family while retaining both forward and reverse cross-candidate swap cases.
- **Files modified:** `tests/test_qualification.py`
- **Verification:** All 44 qualification tests and 827 repository tests pass.
- **Committed in:** `8fa96ca`

---

**Total deviations:** 1 auto-fixed Rule 1 test-harness issue.
**Impact on plan:** The correction preserved and accurately tested the stricter fail-fast authority binding; no policy, schema, dependency, I/O, model, or remote capability was widened.

## Issues Encountered

- The managed sandbox initially denied uv's existing cache. Every retry still began with the required dependency-free Gate B3 equality preflight and used only `.tools/uv-0.11.29/bin/uv`.

## Authentication Gates

None.

## Known Stubs

None.

## Verification

- Task 1 exact command: **23 passed, 21 deselected**.
- Task 2 exact command: **44 passed**.
- Protected `candidate_authority`, `lineage`, `candidate_source`, and `extractor_boundary` regressions: **161 passed**.
- Full Gate-B3-prefixed test suite: **827 passed**.
- Full Gate-B3-prefixed Ruff: **All checks passed**.
- Changed-file and stub scan: only the planned module/test files changed; no goal-blocking stubs.
- Threat-surface scan: no unplanned endpoint, model/LLM, credential, network, filesystem, database/schema, authentication, validator, or remote-write surface. The new structured trust boundary is exactly the plan-authored qualification/report surface covered by T-03-16 through T-03-18.

## User Setup Required

None - qualification is local, deterministic, and requires no credential or external service.

## Next Phase Readiness

- Plan 03-08 can require one valid passing `QualificationReportV1` before any Generator call and persist its canonical digest as generation authority.
- Later Phase 3 ledger/orchestration work can reject forged totals, stale policy authority, hard-failure overrides, and cross-candidate report swaps before any downstream effect.
- No blocker remains for the next sequential plan; this executor did not start it.

## Self-Check: PASSED

- Found both declared implementation/test files and this summary on disk.
- Confirmed all four TDD commits are repository commit objects in RED-before-GREEN order.
- Reconfirmed both exact task commands, the protected regression set, the full 827-test suite, full Ruff, stub scan, and threat-surface scan recorded above.

---
*Phase: 03-validated-skill-candidate*
*Completed: 2026-07-23*
