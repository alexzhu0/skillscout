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

## Working hypothesis

The failure occurs in a preparation-only remote read or state transition after the preflight boundary. The current public diagnostic vocabulary is too coarse to distinguish state restore, Search pagination, repository metadata, commit, license, local fact recording, or state synchronization.

## Implemented diagnostic

Added a fail-closed, allowlisted stage breadcrumb at each boundary. The breadcrumb contains only a stage identifier and a closed error code; it never contains repository identifiers, URLs, headers, response bodies, credentials, or exception text. Regression tests prove the breadcrumb is emitted without changing success output or state effects.

## Safety boundary

This change does not retry, write state, call a model, execute candidate code, create a Draft PR, approve an environment, or merge anything.

## Verification

- Focused acceptance and CLI security tests: 85 passed.
- Diagnostic regression, nomination success, and CLI output tests: 3 passed.
- Ruff check, `git diff --check`, and the Phase 6 source-execution verifier passed.
- The broader Phase 6 suite retains known baseline failures unrelated to this patch: repository-contract fixtures, the historical V1 test seam, and the process-harness authority fixture.
