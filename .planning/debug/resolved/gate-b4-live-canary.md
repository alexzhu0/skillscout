---
status: resolved
trigger: "Gate B4 live canary failed after successful App-created PR setup."
created: 2026-07-27
updated: 2026-07-27
---

# Debug Session: Gate B4 live canary

## Symptoms

- Expected behavior: The opt-in live canary passes for the public catalog using the exact scoped GitHub App installation, while default-branch update, merge, ruleset mutation, private unauthorized repository access, and secret access remain blocked.
- Actual behavior: Setup created Draft PR #1 with reviewer and ready PR #2, but the canary failed.
- Errors:
  - Ruleset read returned HTTP 200 because the catalog is public; ruleset mutation returned HTTP 403.
  - `test_partial_environment_fails_closed_before_token_use` inherited the complete live environment and returned a valid config instead of `None`.
- Timeline: First real Gate B4 execution on 2026-07-27.
- Reproduction: Run `SKILLSCOUT_LIVE_CANARY=1 ... pytest -q tests/test_publication_live_canary.py -x` with all required live variables.

## Current Focus

hypothesis: The live canary fails because it conflates public ruleset visibility with ruleset administration by requiring every probe, including ruleset GET, to be non-success; independently, the partial-environment test inherits required variables because it does not clear REQUIRED_CANARY_ENV.
test: Re-run the separately authorized protected live canary and independently compare pre/post default SHA plus ruleset state without exposing credentials or protected logs.
expecting: ruleset_read may be success for the public catalog; ruleset_mutation and every other authority probe remain denied/not_found/conflict/validation/rate_limited; main SHA and ruleset state remain unchanged.
next_action: Complete.
reasoning_checkpoint:
  hypothesis: "A successful public ruleset GET causes the canary failure because CanaryGitHubClient.run applies the same denial-only assertion to ruleset observation and ruleset mutation, while the partial-environment test can return a full config because it never deletes inherited required variables."
  confirming_evidence:
    - "The live probe observed ruleset GET=200, ruleset POST=403, no Administration permission, and unchanged main SHA."
    - "NEGATIVE_PROBES contains ruleset_read and run() asserts every probe classification is in SAFE_CLASSIFICATIONS, which excludes success."
    - "test_partial_environment_fails_closed_before_token_use sets only LIVE_CANARY and APP_TOKEN but does not delete any of the other REQUIRED_CANARY_ENV names."
  falsification_test: "The hypothesis is false if a mock run with ruleset GET=200 and mutation=403 already succeeds under the current assertion, or if clearing all required variables before injecting the partial pair still produces a LiveCanaryConfig."
  fix_rationale: "Give ruleset observation its own bounded contract (success or the existing fail-closed classifications), keep mutation and every other negative probe denial-only, assert unchanged default SHA, and isolate the partial-env test by clearing the complete required set."
  blind_spots: "Offline mocks cannot independently attest the external ruleset digest/state or rerun the protected live environment; the parent orchestrator must review that remote evidence and cleanup separately."

## Evidence

- timestamp: 2026-07-27
  observation: App token created Draft PR #1, requested reviewer alexzhu0, and created otherwise-mergeable PR #2.
- timestamp: 2026-07-27
  observation: default ref update=422, merge=405, ruleset read=200, ruleset mutation=403, unauthorized private repo=404, secret access=403.
- timestamp: 2026-07-27
  observation: main SHA remained unchanged after probes.
- timestamp: 2026-07-27
  observation: CanaryGitHubClient.run classifies all probes uniformly through SAFE_CLASSIFICATIONS, whose values exclude success, even though ruleset_read is a public GET and ruleset_mutation is the administrative POST.
- timestamp: 2026-07-27
  observation: test_partial_environment_fails_closed_before_token_use does not clear REQUIRED_CANARY_ENV before setting its two partial values, so a complete inherited live environment defeats the intended isolation.
- timestamp: 2026-07-27
  observation: The new mock regression with ruleset GET=200 and every other probe=403 fails at CanaryGitHubClient.run's uniform SAFE_CLASSIFICATIONS assertion before the fix.
- timestamp: 2026-07-27
  observation: After the narrow classification fix and environment cleanup, the two targeted regressions pass (2 passed, 4 deselected).
- timestamp: 2026-07-27
  observation: With SKILLSCOUT_LIVE_CANARY forced to 0, the complete live-canary file plus adjacent publication security suite passes (14 passed, 2 skipped), so no remote canary client was constructed.
- timestamp: 2026-07-27
  observation: The bounded diff passes git diff --check and Ruff reports All checks passed for tests/test_publication_live_canary.py.
- timestamp: 2026-07-27
  observation: The full locked offline suite passes with SKILLSCOUT_LIVE_CANARY=0 (1384 passed, 2 skipped in 34.30s).
- timestamp: 2026-07-27
  observation: Final bounded contract scan finds public ruleset observation explicitly allowed while ruleset administration/mutation remains a required denial; no stale ruleset-read denial claim remains.
- timestamp: 2026-07-27
  observation: The first protected rerun exposed that `/installation` accepts an App JWT rather than an installation token; the canary now receives the independently reviewed positive installation ID as fail-closed configuration and never sends the installation token to that endpoint.
- timestamp: 2026-07-27
  observation: The corrected protected rerun passed (5 passed, 1 skipped). Default-ref update=422, merge=405, ruleset read=200, ruleset mutation=403, unauthorized private repo=404, and secret access=403.
- timestamp: 2026-07-27
  observation: Human/admin cleanup closed catalog PRs #1 and #2 and deleted both exact canary branches; the catalog then contained only main at bd96c4fcfed5e7b2c94c79be7ec1aa6e333b71bb.

## Eliminated

- hypothesis: App had Administration or ruleset mutation permission.
  reason: Ruleset mutation returned HTTP 403 and installation permissions contain only contents/write, pull_requests/write, metadata/read.

## Resolution

root_cause: The canary contract conflated public ruleset visibility with administrative mutation, the partial-environment test inherited live variables, and it tried to discover installation identity through an endpoint that requires an App JWT while holding an installation token.
fix: Allow success only for bounded ruleset observation, retain denial-only classifications for authority probes, clear the complete required environment in isolation tests, and accept the independently reviewed positive installation ID as explicit fail-closed canary configuration.
verification: Targeted and full offline suites passed before the rerun; the corrected protected live canary passed (5 passed, 1 skipped), remote default SHA and ruleset remained unchanged, and separate human/admin cleanup removed both PR branches without merging.
files_changed:
  - tests/test_publication_live_canary.py
  - .planning/phases/04-controlled-draft-pr/04-10-PLAN.md
  - .planning/phases/04-controlled-draft-pr/04-VALIDATION.md
