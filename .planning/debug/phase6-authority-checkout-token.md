---
status: resolved
trigger: "Phase 6 live benchmark fails before any model call while checking out the exact authority-state commit."
created: "2026-08-10T06:31:14Z"
updated: "2026-08-10T06:38:00Z"
---

# Phase 6 authority checkout token

## Symptoms

- Expected behavior: `live_benchmark` checks out immutable state commit `4db72171eaf0e93009a71c45994820937b6a5ff6` before the semantic stage.
- Actual behavior: run `31362215710` stops at that checkout; no DeepSeek request, source execution, or PR is created.
- Error: `Input required and not supplied: token` from `actions/checkout`.
- Timeline: began on the first real benchmark after live authority persistence.
- Reproduction: dispatch `phase6-acceptance.yml` with `phase6_action=run-benchmark` at source `bfb9724e5ab7127292f5d4e7f3b407917615d5c6`.

## Root Cause

- The `live_benchmark` and `live_replay` jobs passed `token: ''` to their two immutable state checkouts. The current pinned `actions/checkout` requires a token input instead of treating that empty value as an anonymous public checkout.
- This failure occurs before the semantic stage, so no untrusted source was read and no DeepSeek request or publication side effect occurred.

## Fix and Verification

- Replaced each of the four empty checkout token inputs with the job-scoped read-only `${{ github.token }}` while retaining `persist-credentials: false`.
- Updated the closed-workflow verifier and added regression tests that reject a substituted secret token.
- Focused workflow and source-execution suites passed: `162 passed`.
- `python tools/verify_phase6_source_execution.py` and Ruff for the changed Python files passed.
- The full suite currently reports 21 failures outside this checkout-only change, including a superseded benchmark manifest with `prior_manifest_digest` set and prior Phase 1/3/6 fixture-contract failures. None of their files are modified by this fix.

## Evidence

- timestamp: 2026-08-10T06:31:14Z; run `31362215710`, job `93373350882` logged `Input required and not supplied: token` while `ref` was the persisted authority commit.

## Eliminated

- hypothesis: Authority state is missing or malformed; evidence: the prior `live_authority_preflight` job checked out and verified the same immutable authority state successfully.
