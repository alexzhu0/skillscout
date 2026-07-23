---
phase: 03-validated-skill-candidate
plan: "09"
subsystem: validation
tags: [skills-ref, workspace-admission, safety-policy, provenance, overcopy, canonical-report, tdd]

requires:
  - phase: 03-03
    provides: Gate B3 pinned dependency authority and offline verification
  - phase: 03-05
    provides: Complete WorkflowSpec and candidate execution authorities
  - phase: 03-08
    provides: Frozen semantic and rendered package identities with canonical provenance
provides:
  - Exact private workspace admission before isolated official skills-ref validation
  - Deterministic local structure, safety, provenance, attribution, and overcopy policies
  - Immutable authority-bound ValidationReport with canonical digest and strict revalidation
affects: [03-10, 03-11, 03-12, 03-14, reviewer, eligibility, phase3-ledger]

tech-stack:
  added: []
  patterns:
    - Exact package bytes are re-admitted through no-follow descriptor reads before and after official validation
    - Official validation and SkillScout-owned local policies remain separate capability families
    - Validation reports bind complete upstream authority and ordered findings under one canonical digest

key-files:
  created:
    - src/skillscout/domain/validation.py
    - src/skillscout/adapters/skills_ref.py
    - tests/test_skill_validation.py
    - tests/fixtures/skills/valid-skill/SKILL.md
    - tests/fixtures/skills/valid-skill/references/provenance.json
  modified:
    - tests/test_phase1_gap_closure.py

key-decisions:
  - "Re-admit the exact frozen manifest through descriptor identity, size, mode, type, UTF-8, hash, link-count, and before/after identity checks before trusting an official validation result."
  - "Keep skills-ref behind one capability-limited adapter; SkillScout deterministically owns local structure, safety, provenance, attribution, and overcopy findings."
  - "Embed complete WorkflowSpec, candidate execution, renderer, generated artifact, package, workspace, official-validator, and local-policy authorities directly in ValidationReportV1."

patterns-established:
  - "Validation never reopens raw repositories: it consumes only the frozen docs-only package and its already-authorized identities."
  - "All findings are bounded, stably ordered data; report pass/count fields and the report digest are recomputed and rejected on any mismatch."

requirements-completed: [GEN-02, GEN-03, GEN-04, VAL-01, VAL-02, VAL-03]

coverage:
  - id: V1
    description: "The exact frozen docs-only package is materialized in a private workspace, re-admitted without following links, and passed through the pinned official validator."
    requirement: VAL-01
    verification:
      - kind: unit
        ref: "tests/test_skill_validation.py official admission selection (25 passed)"
        status: pass
      - kind: static
        ref: "AST capability scan found skills_ref imports only in adapters/skills_ref.py"
        status: pass
    human_judgment: false
  - id: V2
    description: "Local deterministic checks reject malformed structure, unsafe instructions, missing provenance or attribution, and excessive copied source text at exact policy boundaries."
    requirement: VAL-02
    verification:
      - kind: unit
        ref: "tests/test_skill_validation.py local policy selection (35 passed)"
        status: pass
      - kind: integration
        ref: "Protected state, Phase 2, extraction, generation, and validation regressions (318 passed)"
        status: pass
    human_judgment: false
  - id: V3
    description: "ValidationReportV1 directly binds all upstream and validator authorities, ordered findings, counts, pass state, and a canonical tamper-evident digest."
    requirement: VAL-03
    verification:
      - kind: unit
        ref: "tests/test_skill_validation.py complete validation module (80 passed)"
        status: pass
      - kind: integration
        ref: "Gate-B3-prefixed full pytest suite (945 passed)"
        status: pass
    human_judgment: false
  - id: V4
    description: "Validation preserves the generated docs-only structure, generalized human-controlled instructions, and canonical provenance obligations."
    requirement: GEN-02
    verification:
      - kind: unit
        ref: "tests/test_skill_validation.py structure, scripts, mode, and link rejection cases"
        status: pass
    human_judgment: false
  - id: V5
    description: "Verbatim excerpts are admitted only within exact per-quote and aggregate limits and with verified commit-level source attribution."
    requirement: GEN-03
    verification:
      - kind: unit
        ref: "tests/test_skill_validation.py 119/120/121, 239/240/241, and unregistered-source boundary cases"
        status: pass
    human_judgment: false
  - id: V6
    description: "Machine-readable provenance remains complete, canonical, and consistent with the exact rendered manifest and package identity."
    requirement: GEN-04
    verification:
      - kind: unit
        ref: "tests/test_skill_validation.py provenance, manifest, attribution, and identity-tamper cases"
        status: pass
    human_judgment: false

duration: 24 min
completed: 2026-07-23
status: complete
---

# Phase 03 Plan 09: Layered Skill Validation Summary

**Frozen Skill packages now pass an exact no-follow workspace admission, isolated official `skills-ref` validation, deterministic local safety and provenance policies, and an immutable authority-bound report before any Reviewer or publishing stage can consume them.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-07-23T11:09:47Z
- **Completed:** 2026-07-23T11:33:29Z
- **Tasks:** 3/3
- **Implementation/test files:** 6

## Accomplishments

- Added private workspace materialization and exact manifest re-admission using descriptor-relative no-follow reads, fixed modes, link/type checks, UTF-8 validation, content hashes, and before/after file identity checks.
- Added a single isolated official-validator adapter that verifies the approved lock authority immediately before resolving and invoking the pinned installed `skills-ref` interface.
- Added deterministic local structure, progressive-disclosure, instruction-safety, provenance, attribution, URL, and overcopy policies with stable bounded findings and exact quote/source limits.
- Added `ValidationReportV1`, which directly embeds every complete upstream authority plus official/local policy authority, ordered findings, derived counts/pass state, and a canonical report digest.
- Proved fail-closed behavior for symlink, hard-link, FIFO, mode, manifest, hash, encoding, TOCTOU, validator-infrastructure, authority-swap, finding, count, pass-state, and digest tampering.

## Task Commits

Each TDD task was committed with RED before GREEN:

1. **Task 1 RED: Official validation admission tests** - `dcada69` (`test`)
2. **Task 1 GREEN: Exact workspace admission and official adapter** - `7d4900c` (`feat`)
3. **Task 2 RED: Local safety and provenance policy tests** - `d529cf9` (`test`)
4. **Task 2 GREEN: Deterministic local validation policies** - `89bae9f` (`feat`)
5. **Task 3 RED: Immutable validation report tests** - `f74886a` (`test`)
6. **Task 3 GREEN: Authority-bound validation report composition** - `c5d83cc` (`feat`)

Supporting deviation commit:

- **Static capability guard update** - `0ef1c71` (`fix`)

## Files Created/Modified

- `src/skillscout/domain/validation.py` - Workspace admission, stable findings, local policies, report contracts, canonical report identity, and strict revalidation.
- `src/skillscout/adapters/skills_ref.py` - Approved-lock verification and the sole isolated official `skills-ref` import/call boundary.
- `tests/test_skill_validation.py` - Admission attacks, official outcomes, local policy boundaries, authority completeness, determinism, and tamper coverage.
- `tests/fixtures/skills/valid-skill/SKILL.md` - Minimal valid Agent Skill fixture for official validation.
- `tests/fixtures/skills/valid-skill/references/provenance.json` - Matching machine-readable provenance fixture.
- `tests/test_phase1_gap_closure.py` - Exact static capability carve-out for the dedicated validator adapter's distribution metadata lookup.

## Decisions Made

- Official validation is meaningful only after the exact frozen package has been re-admitted. The same descriptor-backed identity is checked again after the official call so concurrent replacement cannot produce a trusted result.
- The official validator does not own SkillScout policy. Its normalized problems remain a separate family from local deterministic structure, safety, provenance, attribution, and overcopy findings.
- Report consumers receive complete authority objects rather than hashes standing in for omitted state. Strict model revalidation recomputes all derived fields and rejects reordered, duplicated, swapped, or otherwise inconsistent evidence.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Test Guard] Admitted the planned official validator metadata boundary**
- **Found during:** Overall full-suite verification
- **Issue:** The Phase 1 static capability test rejected `importlib.metadata` in the new plan-required `adapters/skills_ref.py` before it could evaluate the adapter's closed capability boundary.
- **Fix:** Added only `adapters/skills_ref.py: importlib` to the exact module carve-out. No network, subprocess, credential, execution, publication, or other import authority was widened.
- **Files modified:** `tests/test_phase1_gap_closure.py`
- **Verification:** The targeted static guard passed, followed by the protected 318-test set, full 945-test suite, and full Ruff.
- **Committed in:** `0ef1c71`

---

**Total deviations:** 1 auto-fixed Rule 3 blocking test-guard issue.
**Impact on plan:** The guard now recognizes exactly the planned installed-distribution metadata check while retaining all existing capability denials.

## Issues Encountered

- The first full-suite run exposed the static guard mismatch above; it was fixed narrowly and the entire suite was rerun from a fresh Gate B3 check.
- One intermediate protected-regression command referenced a nonexistent historical filename and collected no tests. It was immediately replaced with the current extraction test modules; the corrected set passed 318 tests.
- The current GSD `state.update-progress` handler reported 86% but wrote the completed-phase ratio (33%) into frontmatter. The value was corrected to the internally consistent 31/36 plan ratio after all SDK state handlers completed.

## Authentication Gates

None.

## Known Stubs

None.

## Verification

- Task 1 exact official-admission selection: **25 passed, 55 deselected**.
- Task 2 exact local-policy selection: **35 passed, 45 deselected**.
- Task 3 complete validation module: **80 passed**.
- Independent AST capability scan: `skills_ref` is imported only by `src/skillscout/adapters/skills_ref.py`.
- Targeted Phase 1 capability guard after the deviation: **1 passed**.
- Protected state integrity, Phase 2 pipeline, extraction, generation, and validation regressions: **318 passed**.
- Full Gate-B3-prefixed test suite: **945 passed**.
- Full Gate-B3-prefixed Ruff: **All checks passed**.
- Approved dependency lock remained unchanged; no dependency, network, credential, candidate-execution, or publication authority was added.
- Changed-file and stub scan found no goal-blocking placeholders, TODOs, FIXMEs, empty UI data, or unimplemented data sources.
- Threat-surface scan found no unplanned surface. The local filesystem admission and official static-validator adapter are the plan-authored boundaries covered by exact manifest, link, race, dependency-authority, and capability-isolation tests.

## User Setup Required

None.

## Next Phase Readiness

- Plan 03-10 can consume one immutable validation report without reopening package bytes or silently substituting upstream authority.
- Reviewer, eligibility, ledger, and Draft PR stages can distinguish official-validator infrastructure failures from stable local policy findings.
- No blocker remains for the next sequential plan; this executor did not start it.

## Self-Check: PASSED

- Found every declared implementation, test, fixture, and summary file on disk.
- Confirmed all six TDD commits and the one deviation commit exist in RED-before-GREEN order.
- Reconfirmed exact task selections, AST isolation, the protected 318-test set, full 945-test suite, full Ruff, unchanged dependency files, stub scan, and threat-surface scan.

---
*Phase: 03-validated-skill-candidate*
*Completed: 2026-07-23*
