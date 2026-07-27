---
status: resolved
trigger: "Live Phase 5 StateBranchClient rejects a valid GitHub X-GitHub-Request-Id containing colon-delimited hexadecimal groups before a missing-ref 404 can become StateRefNotFound."
created: 2026-07-28
updated: 2026-07-28T01:40:00Z
---

# Resolved Debug Session: Phase 5 State Request ID

## Symptoms

- expected: A missing state ref response with a valid GitHub request ID such as `753C:748B6:2CB2070:2EA615C:6A679381` reaches the `allow_not_found` path and raises `StateRefNotFound`.
- actual: `StateBranchClient._json` rejects the response header with `SafeFailure` because its request-ID allowlist excludes colons.
- errors: Safe failure occurs before missing-ref classification; no remote changes occurred.
- timeline: Reproduced during the live Phase 5 state-branch path on 2026-07-28.
- reproduction: Return a GitHub 404 for the fixed state ref with `X-GitHub-Request-Id: 753C:748B6:2CB2070:2EA615C:6A679381`.

## Current Focus

reasoning_checkpoint:
  hypothesis: StateBranchClient rejects the valid missing-ref response because its request-ID validator permits only one `[A-Za-z0-9._-]+` token, so the first colon raises SafeFailure before the subsequent 404 allow_not_found branch.
  confirming_evidence:
    - The unchanged adapter's focused live-ID test raises SafeFailure at state_branch.py:429, the request-ID rejection line, instead of StateRefNotFound.
    - The same 404 transport with all 11 missing, whitespace/control, malformed/empty-colon, non-hex, and oversized mutations fails closed as expected.
    - `_json` performs no other work between reading the request-ID header and the failing validator.
  falsification_test: If replacing only the request-ID pattern with the bounded two-alternative grammar does not make the recorded live-ID 404 raise StateRefNotFound, or if any mutation stops raising SafeFailure, the hypothesis is wrong.
  fix_rationale: A compiled pattern that preserves the existing safe single-token form and separately accepts two or more non-empty uppercase-hex groups joined by single colons changes only the rejected live wire form; the independent 128-character check retains the established bound.
  blind_spots: Only the recorded live uppercase-hex form and repository fixtures are observable offline; no network probe will be made, and sibling adapters with similar validators are outside this scoped state-branch fix.
next_action: RESOLVED — archive the session after independent offline verification of the exact recorded live header/404 pair.

## Evidence

- timestamp: 2026-07-28T00:20:00Z
  checked: StateBranchClient._json response handling
  found: The request ID is validated with `[A-Za-z0-9._-]+` and a 128-character limit before redirect, conflict, 404, transient, status, content-type, and body handling.
  implication: The recorded colon-delimited request ID deterministically raises SafeFailure before the permitted absent-ref classification.

- timestamp: 2026-07-28T00:20:00Z
  checked: Knowledge base and repository request-ID validators
  found: No knowledge-base entry overlaps this request-ID grammar bug. Existing GitHub adapters use the same 128-character single-token bound; the semantic-provider validator permits colon but is provider-generic and has a broader 256-character bound.
  implication: The fix should remain local and GitHub-specific, preserve the established 128-character cap, and avoid copying the broader semantic-provider policy.

- timestamp: 2026-07-28T00:32:00Z
  checked: Phase 5 plan/patterns and Phase 4/Phase 2 GitHub adapter tests
  found: The state client intentionally copied Phase 4's 128-character request-ID validation and sanitized-failure pattern. Existing successful fixtures use safe single-token IDs, while the only observed live colon form is uppercase hexadecimal groups.
  implication: Preserve the safe single-token alternative for existing/recorded traffic, add a separate uppercase-hex colon alternative requiring non-empty groups, and keep the total 128-character cap.

- timestamp: 2026-07-28T00:40:00Z
  checked: Focused pre-fix regression and request-ID mutation matrix
  found: The live `753C:748B6:2CB2070:2EA615C:6A679381` case failed at the request-ID validator with SafeFailure, while all 11 absent, whitespace/control, malformed/empty group, non-hex group, and 129-character mutations raised SafeFailure as required.
  implication: The root cause is confirmed and the fix can be limited to the accepted request-ID grammar.

- timestamp: 2026-07-28T00:47:00Z
  checked: Focused post-fix regression and request-ID mutation matrix
  found: All 12 cases pass. The live uppercase-hex colon ID reaches the exact 404 StateRefNotFound path and is absent from exception/log capture; every hostile mutation still raises SafeFailure.
  implication: The counterfactual confirms the grammar caused the bug and the minimal fix restores only the intended behavior.

- timestamp: 2026-07-28T00:58:00Z
  checked: Complete state-branch and repository regression verification
  found: `tests/test_state_branch.py` passed 37 tests; the full locked suite passed 1756 tests with 2 skips; scoped Ruff lint and `git diff --check` passed. Ruff format-check reports existing whole-file drift on both current and HEAD versions, so no unrelated bulk reformat was applied.
  implication: The fix is regression-safe in the offline test environment and the remaining end-to-end check is the live missing-ref workflow.

- timestamp: 2026-07-28T01:03:00Z
  checked: Atomic commit scope
  found: Commit `4929cb9` contains only `src/skillscout/adapters/state_branch.py` and `tests/test_state_branch.py`; the active debug record remains untracked for the human-verification continuation.
  implication: The implementation and its regression protection are isolated from unrelated worktree state.

- timestamp: 2026-07-28T01:40:00Z
  checked: Independent offline post-commit verification
  found: The exact recorded live request-ID/404 reproduction and all state-branch mutations passed in the 37-test state suite; scoped Ruff and diff checks passed. The requested workflow requires no new network call, and no remote changes or secrets were used.
  implication: The fix is verified against the original failure boundary and can be archived without expanding authority to a live GitHub mutation or secret-bearing workflow.

## Eliminated

## Resolution

- root_cause: StateBranchClient._json copied the synthetic single-token `[A-Za-z0-9._-]+` request-ID grammar and validates it before `allow_not_found`, so a valid live uppercase-hex colon-delimited GitHub request ID is rejected before the exact missing state ref can raise StateRefNotFound.
- fix: Added a local compiled GitHub request-ID validator with the existing safe single-token alternative plus a separate two-or-more non-empty uppercase-hex colon-group alternative, retained the 128-character cap, and added live 404/log-redaction plus hostile mutation coverage.
- verification: Focused live-ID and hostile mutation checks passed 12/12; complete state-branch suite passed 37/37 independently; full locked repository suite passed 1756 with 2 skips; scoped Ruff lint and diff whitespace checks passed; committed atomically as 4929cb9; no network, remote mutation, or secret inspection was used.
- files_changed:
  - src/skillscout/adapters/state_branch.py
  - tests/test_state_branch.py
