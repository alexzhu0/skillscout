---
phase: quick-260805-live
plan: 01
subsystem: phase6-live-authority
tags: [phase6, live-authority, query-config, regression]
requires:
  - phase: Phase 6 fresh benchmark lock
    provides: Exact manifest, nomination, and state bindings for live-authority recording
provides:
  - Live-authority loader compatibility with the repository's formatted query JSON
  - Regression coverage for semantic query validation and digest binding
affects: [phase6-live-authority]
tech-stack:
  added: []
  patterns:
    - Exact checked-out source binding plus strict typed digest validation independent of JSON whitespace
key-files:
  created:
    - .planning/quick/260805-live-query-format-fix/260805-live-PLAN.md
    - .planning/quick/260805-live-query-format-fix/260805-live-SUMMARY.md
  modified:
    - src/skillscout/bootstrap.py
    - tests/test_phase6_acceptance.py
key-decisions:
  - "Keep strict manifest byte canonicalization; relax only the query file's unnecessary formatting check because the tracked query is valid formatted JSON."
  - "Retain exact checked-out commit verification, strict DiscoveryQuerySetV1 parsing, and query_set_digest binding as the authority boundary."
requirements-completed: []
coverage:
  - id: LQ1
    description: "The current formatted query file reaches live-authority configuration when its exact source commit and typed digest match."
    verification:
      - kind: unit
        ref: "tests/test_phase6_acceptance.py::test_live_authority_config_accepts_formatted_query_json_without_secret_lookup"
        status: pass
    human_judgment: false
duration: 20 min
completed: 2026-08-05
status: complete
---

# Quick 260805-live Summary

Live-authority recording now accepts the repository's valid formatted query JSON. The loader still binds the exact checked-out source commit, strictly validates `DiscoveryQuerySetV1`, and requires the model-derived query digest.

## Verification

- Focused live-authority tests: 12 passed.
- Full `tests/test_phase6_acceptance.py`: 135 passed, 1 skipped, 12 known baseline process-harness failures caused by missing prior acceptance facts during fixture setup.
- Ruff and `git diff --check`: passed.

## Root cause

Run 31010953545 failed before remote state restore because the loader required `config/discovery-queries-v1.json` to be canonical one-line JSON. The tracked file is valid formatted JSON, so the formatting-only predicate rejected it. The failure did not indicate a bad token, approval, or state branch.

## Task commit

- `58c5538 fix(phase6): accept formatted query config`

## Next step

After human merge of PR #13, rerun the protected fresh live-authority workflow once. The previous failed run did not mutate the state branch.

---
*Plan: quick-260805-live-01*
