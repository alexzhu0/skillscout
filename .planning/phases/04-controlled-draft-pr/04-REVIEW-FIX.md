---
phase: 04-controlled-draft-pr
fixed_at: 2026-07-27T11:20:49Z
review_path: .planning/phases/04-controlled-draft-pr/04-REVIEW.md
iteration: 2
findings_in_scope: 14
fixed: 14
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-07-27T11:20:49Z
**Source review:** `.planning/phases/04-controlled-draft-pr/04-REVIEW.md`  
**Iteration:** 2

**Summary:**

- Findings in scope: 14
- Fixed: 14
- Skipped: 0
- Full regression: `1410 passed, 2 skipped`
- Static checks: Ruff passed
- Phase validators: validation map, action audit, and acceptance passed

## Fixed Issues

### CR-01: Draft markers are permanently bound to zero SHAs

**Files modified:** `src/skillscout/domain/publication.py`, `src/skillscout/application/publication.py`, `tests/test_publication_domain.py`  
**Commit:** `0cc6e11`  
**Status:** fixed: requires human verification  
**Applied fix:** Rendered the Draft marker from the real machine commit and parent lineage, and persisted its exact digest.

### CR-02: Remote Git blob SHA-1 values are compared with SHA-256 content digests

**Files modified:** `src/skillscout/application/publication.py`, `tests/test_publication_recovery.py`  
**Commit:** `039cee2`  
**Status:** fixed: requires human verification  
**Applied fix:** Derived Git blob object IDs from admitted bytes before comparing the desired and observed trees.

### CR-03: Publication is recorded successful without re-reading the remote result

**Files modified:** `src/skillscout/adapters/github_publish.py`, `src/skillscout/application/publication.py`, `src/skillscout/domain/publication.py`, `tests/fixtures/github_publish/pulls_page.json`, `tests/test_github_publish_adapter.py`  
**Commit:** `1602209`  
**Status:** fixed: requires human verification  
**Applied fix:** Added exact post-mutation reconciliation of catalog/default refs, machine lineage, owned tree, Draft marker, and reviewer evidence before terminal success.

### CR-04: Re-running a completed intent crashes during remote reconstruction

**Files modified:** `tests/test_publication_recovery.py`  
**Commit:** `7cc44c5`  
**Status:** fixed: requires human verification  
**Applied fix:** Exercised and proved the completed-attempt revalidation path without appending to a closed attempt.

### CR-05: Any ref-read failure is treated as proof that the machine ref is absent

**Files modified:** `src/skillscout/adapters/github_publish.py`, `src/skillscout/application/publication.py`, `tests/test_github_publish_adapter.py`  
**Commit:** `e03e411`  
**Status:** fixed: requires human verification  
**Applied fix:** Added a distinct exact-404 missing-ref signal and propagated all other failures before mutation.

### CR-06: Workflow input permits an arbitrary local file write

**Files modified:** `.github/workflows/publish-candidate.yml`, `src/skillscout/bootstrap.py`, `tests/test_publication_security.py`  
**Commit:** `f02051b`  
**Status:** fixed: requires human verification  
**Applied fix:** Confined the publication-state locator to the canonical private `state/` root before token acquisition, with bootstrap defense in depth.

### CR-07: Lineage validation rejects every second package update

**Files modified:** `tests/test_publication_recovery.py`  
**Commit:** `ef5880e`  
**Status:** fixed: requires human verification  
**Applied fix:** Exercised bounded chained machine lineage across multiple revisions while rejecting human commits and default-branch drift.

### CR-08: A completed reviewer causes a later revision to mutate remotely and then fail

**Files modified:** `src/skillscout/application/publication.py`, `tests/test_publication_recovery.py`
**Commit:** `586fd11`
**Status:** fixed: requires human verification
**Applied fix:** Counted strictly validated completed-review evidence for the configured individual independently of its historical commit SHA. Added a stateful revision N to N+1 regression proving successful publication with zero reviewer re-notification, plus fail-closed cases for malformed rows, duplicate review IDs, and outsider-only evidence.

### WR-01: Pagination is rejected rather than consumed

**Files modified:** `src/skillscout/adapters/github_publish.py`, `tests/test_github_publish_adapter.py`  
**Commits:** `a1127eb`, `3225aff`  
**Status:** fixed: requires human verification  
**Applied fix:** Added bounded, canonical same-origin `Link` pagination for pulls and reviews while preserving the local-only capability boundary.

### WR-02: Recovery tests assert canned answers instead of the production state machine

**Files modified:** `tests/test_publication_recovery.py`  
**Commit:** `2315f68`  
**Status:** fixed  
**Applied fix:** Replaced canned fixtures with stateful remote/store tests that execute `PublicationApplication.run()`.

### WR-03: The provider error-matrix test never exercises an error

**Files modified:** `tests/test_github_publish_adapter.py`  
**Commit:** `fca1321`  
**Status:** fixed  
**Applied fix:** Executed every provider failure fixture and asserted closed classification, request bounds, response closure, and redaction.

### WR-04: Publication state resources are never closed by the application

**Files modified:** `src/skillscout/adapters/publication_state.py`, `tests/test_publication_recovery.py`  
**Commit:** `67a194e`  
**Status:** fixed: requires human verification  
**Applied fix:** Closed both state and remote capabilities across success and exception paths and added context-manager support.

### WR-05: Public CLI results collapse all successful dispositions

**Files modified:** `src/skillscout/cli.py`, `tests/test_cli_validate_skill.py`  
**Commit:** `9c49451`  
**Status:** fixed: requires human verification  
**Applied fix:** Preserved created/updated/reused dispositions and emitted bounded commit and Draft PR identifiers.

### WR-06: Terminal records are not fully bound to their stored intent

**Files modified:** `src/skillscout/adapters/publication_state.py`, `tests/test_publication_recovery.py`  
**Commit:** `5705c0a`  
**Status:** fixed: requires human verification  
**Applied fix:** Required publication key and desired revision to match when completing and loading terminal attempts.

## Skipped Issues

None.

## Remaining External Gate

The validation and acceptance verifiers pass against the reapproved protected
workflow hash. This remediation did not perform a live GitHub operation; final
production acceptance remains subject to the separately authorized live canary
and human-controlled release gate recorded by the project.

---

_Fixed: 2026-07-27T11:20:49Z_
_Fixer: the agent (gsd-code-fixer)_  
_Iteration: 2_
