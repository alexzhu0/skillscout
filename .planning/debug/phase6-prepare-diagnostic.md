---
status: patch_ready
trigger: "Phase 6 fresh campaign preparation fails with a sanitized stage_permanent_failure after read-only preflight passes."
created: 2026-08-07
updated: 2026-08-07
---

# Debug Session: Phase 6 Fresh Preparation Diagnostic

## Symptoms

- The read-only fresh-campaign preflight succeeds.
- The protected preparation step fails with only `stage_permanent_failure`.
- The state branch head remains unchanged after each failed run.

## Confirmed failure

The first fresh preparation run after the diagnostic patch reported:

```json
{"diagnostic":{"error_code":"stage_permanent_failure","stage":"resolve_commit"}}
```

Read-only preflight still passes. Search pagination and repository metadata complete before the failure. The failing boundary is the default-branch commit lookup for a Search candidate. A Search result can become stale between pagination and metadata/commit lookup (for example, a repository can disappear or its default branch can be renamed), so a `404` is a deterministic unavailable-candidate outcome rather than a campaign-wide failure. Other HTTP failures remain fail-closed.

## Implemented diagnostic

Added a fail-closed, allowlisted stage breadcrumb at each boundary. The breadcrumb contains only a stage identifier and a closed error code; it never contains repository identifiers, URLs, headers, response bodies, credentials, or exception text. Regression tests prove the breadcrumb is emitted without changing success output or state effects.

## Safety boundary

The planned fix only treats a commit endpoint `404` as an unavailable candidate and skips it. It does not broaden permissions, retry unknown failures, write state, call a model, execute candidate code, create a Draft PR, approve an environment, or merge anything. `403`, `429`, `5xx`, malformed responses, and all other permanent failures remain errors.

## Implemented repair

`GitHubReadClient.resolve_commit` now returns an explicit unavailable result only for a `404`. Fresh nomination validates the result before requesting the license endpoint, so the stale candidate is skipped deterministically. The Phase 2 scout records `ref_not_found` for the same condition; exact-authority publication still fails closed when its pinned commit cannot be resolved.

Regression coverage includes adapter-level `404`/non-`404` behavior and a five-of-six nomination fixture where one stale candidate is skipped.

## Verification

- Focused acceptance and CLI security tests: 85 passed.
- Diagnostic regression, nomination success, and CLI output tests: 3 passed.
- Ruff check, `git diff --check`, and the Phase 6 source-execution verifier passed.
- The focused repair suite passed: 146 passed with two pre-existing durable-nomination diagnostic failures.
- CLI/Search/security regression suites passed: 113 passed; source compilation passed.
- The broader Phase 6 suite retains the same 16 known baseline failures and one skip as before this repair; none are in the changed commit-resolution path.
- The broader Phase 6 suite retains known baseline failures unrelated to this patch: repository-contract fixtures, the historical V1 test seam, and the process-harness authority fixture.
