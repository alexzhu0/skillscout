---
status: resolved
trigger: "Phase 6 protected benchmark-lock run 30877163816 failed after a valid environment approval because the live GitHub attempt metadata reported the exact workflow path without an @ref suffix."
created: 2026-08-04
updated: 2026-08-04
---

# Debug Session: Phase 6 Lock Workflow Path Compatibility

## Symptoms

- expected: A `lock-fresh-campaign` run approved by `alexzhu0` in `phase6-human-benchmark-lock` produces its read-only handoff and reaches the state-only persistence step.
- actual: Run `30877163816` completed the approval wait, then failed in `prepare-fresh-lock-handoff`; persistence was skipped.
- errors: The workflow intentionally emitted only a closed failure result; raw logs were not retrieved because they may contain credentials.
- timeline: The first live V2 benchmark-lock attempt after merging the exact five-repository selection manifest.
- reproduction: GitHub's attempt metadata for the exact run returns `.github/workflows/phase6-acceptance.yml`; the current matcher requires `.github/workflows/phase6-acceptance.yml@<ref>`.

## Current Focus

- hypothesis: `_is_fresh_campaign_workflow_path` rejects the documented exact path form despite all independent source, actor, approval, and repository bindings matching.
- test: Add a regression test for the bare exact workflow path, while retaining rejection of every other path.
- expecting: The current test fails before the matcher change and passes only after an exact optional suffix change.
- next_action: RESOLVED — use the exact bare path accepted by GitHub attempt metadata or the already-supported bounded `@ref` form; do not retry the failed run without a new human-approved operation.

## Evidence

- timestamp: 2026-08-04; run 30877163816 had one approved `phase6-human-benchmark-lock` review by `alexzhu0`; its source SHA, workflow event, actor, and triggering actor matched the fixed policy.
- timestamp: 2026-08-04; run-attempt metadata exposed the exact bare workflow path; no lock-state persistence job ran.
- timestamp: 2026-08-04; the new bare-path regression failed before the production change while all legacy and rejection cases remained green, then passed after making only the existing bounded `@ref` segment optional.
- timestamp: 2026-08-04; the independent closed-workflow source verifier reported `phase6 source execution valid`; it performs no live GitHub action or candidate execution.

## Eliminated

- hypothesis: user approval or source identity was missing; evidence: exact environment, reviewer, source SHA, actor, and repository identity all matched.

## Resolution

- root_cause: `_is_fresh_campaign_workflow_path` required an `@ref` suffix even though GitHub attempt metadata can report the same exact approved workflow path without one.
- fix: Make only the pre-existing bounded `@ref` segment optional while retaining the exact workflow filename, suffix character policy, and 200-character suffix limit.
- verification: The initial regression was RED (1 bare-path failure, 7 existing cases passed); final matcher coverage passed 11/11; the remaining Phase 6 acceptance coverage passed 119 with 1 skipped after excluding 12 unrelated `test_third_attempt_crash_recovers_through_two_production_processes` process-harness variants that fail in acceptance-fact setup before the matcher is reached; `tools/verify_phase6_source_execution.py` reported `phase6 source execution valid`; scoped Ruff passed. A fresh full-suite run on 2026-08-04 had 15 baseline failures: those same 12 process-harness variants plus three pre-existing Phase 1/3 scanner failures caused by the unchanged `bootstrap.py:subprocess` import. Ruff format-check reports existing whole-file drift in both changed Python files, so no unrelated reformat was applied.
- files_changed:
  - src/skillscout/bootstrap.py
  - tests/test_phase6_acceptance.py
  - .planning/debug/phase6-lock-workflow-path.md
