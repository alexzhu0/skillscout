---
phase: 04-controlled-draft-pr
reviewed: 2026-07-27T10:34:41Z
depth: standard
files_reviewed: 29
files_reviewed_list:
  - .github/workflows/publish-candidate.yml
  - src/skillscout/adapters/github_publish.py
  - src/skillscout/adapters/publication_state.py
  - src/skillscout/application/publication.py
  - src/skillscout/bootstrap.py
  - src/skillscout/cli.py
  - src/skillscout/domain/publication.py
  - tests/fixtures/github_publish/blob.json
  - tests/fixtures/github_publish/commit.json
  - tests/fixtures/github_publish/error_matrix.json
  - tests/fixtures/github_publish/pull_draft.json
  - tests/fixtures/github_publish/pulls_page.json
  - tests/fixtures/github_publish/ref.json
  - tests/fixtures/github_publish/repository.json
  - tests/fixtures/github_publish/reviewers.json
  - tests/fixtures/github_publish/tree.json
  - tests/test_cli_security.py
  - tests/test_cli_validate_skill.py
  - tests/test_github_publish_adapter.py
  - tests/test_phase4_acceptance_tool.py
  - tests/test_phase4_action_audit.py
  - tests/test_phase4_validation_map.py
  - tests/test_publication_domain.py
  - tests/test_publication_live_canary.py
  - tests/test_publication_recovery.py
  - tests/test_publication_security.py
  - tools/verify_phase4_acceptance.py
  - tools/verify_phase4_action_audit.py
  - tools/verify_phase4_validation_map.py
findings:
  critical: 7
  warning: 6
  info: 0
  total: 13
status: fixes_applied_pending_gate_b4
---

# Phase 04: Code Review Report

**Reviewed:** 2026-07-27T10:34:41Z  
**Depth:** standard  
**Files Reviewed:** 29  
**Status:** fixes_applied_pending_gate_b4

**Fix verification:** All 13 Critical/Warning findings were fixed and passed the
full local suite (`1406 passed, 2 skipped`). The protected workflow changed as
part of the fixes, so the prior Gate B4 evidence is intentionally stale; a fresh
separately authorized live canary and human review remain required.

## Summary

The controlled-publication implementation is not safe to ship. The happy-path transport primitives are narrow, but the application layer does not create recoverable markers, cannot recognize an already-correct remote tree, does not verify final remote state before recording success, mishandles completed local attempts, and treats arbitrary ref-read failures as proof that a ref is absent. The workflow also passes an unvalidated operator-controlled publication-state path to a writer.

The focused locked suite passed (`107 passed`), but two central suites do not exercise the behaviors they claim: recovery assertions call canned fixture-result functions, and the provider error-matrix test never sends an error response.

## Critical Issues

### CR-01: Draft markers are permanently bound to zero SHAs

**Classification:** BLOCKER  
**Finding status:** FIXED (`0cc6e11`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/publication.py:284`  
**Issue:** `render_pull_request_body()` always builds the machine marker with forty zeroes for both `machine_commit_sha` and `machine_parent_sha`. Both create and update paths persist that body after the real commit exists. Recovery then requires the marker SHAs to equal the observed ref/base SHAs, so every Draft created by this implementation is rejected as `marker_lineage_inconsistent` on the next run. `_finalize()` compounds this by storing a different synthetic marker digest (`sha256({"publication_key", "commit"})`) rather than the digest of the marker actually written to the PR.

**Fix:** Make body rendering accept the observed commit SHA, parent SHA, and prior marker digest; construct one real `PublicationMarkerV1` after commit creation; write that marker into the PR; and persist exactly `marker.marker_digest`.

### CR-02: Remote Git blob SHA-1 values are compared with SHA-256 content digests

**Classification:** BLOCKER  
**Finding status:** FIXED (`039cee2`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/publication.py:118`  
**Issue:** `get_tree()` returns Git object IDs constrained to 40 hex characters, while `PublicationFileV1.content_hash` is a `sha256:` digest. The code strips the prefix and compares a 64-character SHA-256 value with a 40-character Git blob ID. `observed == desired` can therefore never be true, so an already-correct Draft is never reconstructed with zero writes.

**Fix:** Derive the expected Git blob object ID from each admitted byte string using Git's blob-object encoding (or add a bounded blob-content read and verify SHA-256), then compare like-for-like identifiers.

### CR-03: Publication is recorded successful without re-reading the remote result

**Classification:** BLOCKER  
**Finding status:** FIXED (`1602209`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/publication.py:170`  
**Issue:** `_finalize()` only reads reviewers/reviews before writing the terminal record. It never re-reads the default ref, machine ref, commit parent/tree, complete owned subtree, PR head/base/Draft/body marker, or actual ref SHA. Adapter mutation responses are not sufficient: `_ref_response()` does not require the returned SHA to equal the requested SHA, and PR mutation responses are discarded. A stale, inconsistent, or unexpected provider result can therefore be persisted as `published`.

**Fix:** After every mutation cascade, repeat the full bounded reconciliation and persist a terminal record only when catalog/default ref, machine ref/commit lineage, exact owned subtree, one Draft marker, and reviewer evidence all match the admission.

### CR-04: Re-running a completed intent crashes during remote reconstruction

**Classification:** BLOCKER  
**Finding status:** FIXED (`7cc44c5`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/publication.py:64`  
**Issue:** `begin_attempt()` returns an existing completed attempt, but `run()` proceeds into reconciliation. If remote state is valid, `_reconcile_existing()` calls `append_checkpoint()`, which requires `find_pending()` and raises because the attempt already has a terminal record. Thus an idempotent rerun of an already-completed intent fails instead of returning a remotely revalidated completion.

**Fix:** Add an explicit completed-attempt revalidation path that returns the existing record after exact remote verification without appending to the closed attempt, or create a new uniquely keyed verification attempt.

### CR-05: Any ref-read failure is treated as proof that the machine ref is absent

**Classification:** BLOCKER  
**Finding status:** FIXED (`e03e411`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/publication.py:91`  
**Issue:** `_maybe_ref()` catches every exception, including timeouts, 5xx responses, authorization failures, malformed responses, and integrity failures, and returns `None`. With no observed pull, the application then starts creating blobs/tree/commit and attempts ref creation without having established that the ref is absent. This violates the reconcile-before-mutate boundary and can leave orphaned remote objects during transient or ambiguous failures.

**Fix:** Give the adapter a distinct, closed `REF_NOT_FOUND` result for an exact 404. Only that result may map to `None`; propagate all transient, permission, malformed, and integrity failures with zero writes.

### CR-06: Workflow input permits an arbitrary local file write

**Classification:** BLOCKER  
**Finding status:** FIXED (`f02051b`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/.github/workflows/publish-candidate.yml:99`  
**Issue:** `publication_state_locator` is a raw `workflow_dispatch` string. Unlike the three evidence/state locators, it is never passed through `_closed_publication_locator(..., root="state")`. It reaches `PublicationStateStore`, which opens `path.parent` and atomically writes `path.name`. An authorized dispatcher can therefore select an absolute or traversal path outside `state/` and cause the protected job to replace a writable runner file.

**Fix:** Validate the publication-state argument before constructing any state or token capability, requiring the same ASCII canonical relative grammar and `state/` root used by the other state locator. Reject absolute paths, `..`, collisions, and non-private targets.

### CR-07: Lineage validation rejects every second package update

**Classification:** BLOCKER  
**Finding status:** FIXED (`ef5880e`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/publication.py:104`  
**Issue:** Existing machine commits are accepted only when their parent equals the current default-branch SHA. The first update creates a new commit whose parent is the prior machine commit, so the next run necessarily fails `machine_lineage_inconsistent`. `MachineLineageV1` and prior-marker fields exist but are not used to validate a chained machine history.

**Fix:** Validate a bounded machine-owned chain using the commit trailer and prior marker/revision linkage. Permit a verified previous machine head as the new parent while still rejecting force updates, default-branch drift, and human commits.

## Warnings

### WR-01: Pagination is rejected rather than consumed

**Classification:** WARNING  
**Finding status:** FIXED (`a1127eb`, compatibility follow-up `3225aff`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/github_publish.py:365`  
**Issue:** `_pages()` returns only when a page contains fewer than 100 rows; exactly 100 rows immediately fail instead of following GitHub's `Link` header. `list_reviews()` separately hardcodes page 1 and rejects 100 rows. This contradicts the required complete bounded pagination and makes valid busy repositories unrecoverable.

**Fix:** Parse and validate same-origin canonical `Link` headers, follow at most `_MAX_PAGES`, reject cycles/cross-origin links, and apply the same implementation to reviews.

### WR-02: Recovery tests assert canned answers instead of the production state machine

**Classification:** WARNING  
**Finding status:** FIXED (`2315f68`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/tests/test_publication_recovery.py:44`  
**Issue:** `_reconcile()` calls `reconcile_publication_fixture()`, which returns hard-coded `_FixtureResult` values based only on a case-name string. No test in this suite instantiates `PublicationApplication` with a fake remote/store. Consequently the suite passes while CR-01 through CR-05 and CR-07 remain in production.

**Fix:** Replace the canned seam with stateful fake `PublicationStateStore`/remote implementations and run every crash, replay, local-state-loss, marker, lineage, reviewer, and stale-tree case through `PublicationApplication.run()`.

### WR-03: The provider error-matrix test never exercises an error

**Classification:** WARNING  
**Finding status:** FIXED (`fca1321`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/tests/test_github_publish_adapter.py:156`  
**Issue:** The parameterized test only checks that each fixture key exists and that `GitHubPublishClient` is truthy. It never constructs a response for the status/body condition or calls the adapter, so redirects, 401/403/404/409/422, rate limits, 5xx, oversized/malformed bodies, pagination, and missing request IDs have no asserted behavior.

**Fix:** Convert every matrix entry into a `RecordedResponse`, call the relevant named operation, and assert the exact closed failure classification, request count, response closure, and absence of provider body/token leakage.

### WR-04: Publication state resources are never closed by the application

**Classification:** WARNING  
**Finding status:** FIXED (`67a194e`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/publication.py:64`  
**Issue:** `run()` creates a `PublicationStateStore` but its `finally` block closes only the remote. Every result and exception path leaks the SQLite connection and anchored directory descriptor, making repeated in-process publishing brittle.

**Fix:** Close both resources in a nested `try/finally` or use context-manager protocols for the state store and remote.

### WR-05: Public CLI results collapse all successful dispositions

**Classification:** WARNING  
**Finding status:** FIXED (`9c49451`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/cli.py:537`  
**Issue:** Every `published` result becomes `draft_updated`, including a newly created or remotely reused Draft. The payload also omits the promised commit SHA, PR number, and PR URL, so an operator cannot tell what happened or identify the Draft from the command's bounded output.

**Fix:** Carry an explicit `draft_created` / `draft_updated` / `draft_reused` disposition plus bounded commit/PR identifiers in `PublicationApplicationResult`, and project those fields verbatim.

### WR-06: Terminal records are not fully bound to their stored intent

**Classification:** WARNING  
**Finding status:** FIXED (`5705c0a`)  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/publication_state.py:166`  
**Issue:** `complete()` checks only `record.publication_key`; it does not require `record.desired_revision == intent.desired_revision`. `_attempt()` likewise returns a canonical terminal record without checking either field against the stored intent. A canonical but mismatched record can therefore be accepted as completed state.

**Fix:** Validate both publication key and desired revision in `complete()` and again while loading `_attempt()`, failing closed on any mismatch.

---

_Reviewed: 2026-07-27T10:34:41Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
