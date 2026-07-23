---
phase: 03-validated-skill-candidate
reviewed: 2026-07-23T15:29:37Z
resolved: 2026-07-23T15:50:10Z
round: 2
depth: deep
files_reviewed: 19
files_reviewed_list:
  - pyproject.toml
  - src/skillscout/bootstrap.py
  - src/skillscout/adapters/phase2_state.py
  - src/skillscout/adapters/skills_ref.py
  - src/skillscout/adapters/state.py
  - src/skillscout/application/phase3.py
  - src/skillscout/application/ports.py
  - src/skillscout/cli.py
  - src/skillscout/domain/candidate_authority.py
  - src/skillscout/domain/models.py
  - src/skillscout/domain/review.py
  - tests/test_candidate_source.py
  - tests/test_lineage.py
  - tests/test_openai_review.py
  - tests/test_phase3_bootstrap.py
  - tests/test_phase3_pipeline.py
  - tests/test_skill_validation.py
  - tests/test_phase3_acceptance_tool.py
  - tools/verify_phase3_acceptance.py
findings:
  critical: 4
  warning: 0
  info: 0
  total: 4
resolved_findings: 4
status: clean
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-23T15:29:37Z
**Round:** 2
**Depth:** deep
**Files Reviewed:** 19
**Status:** clean after Round-2 fixes

## Summary

Round 2 identified four residual correctness and trust-boundary blockers:

- lineage approval is derived from the binding instead of supplied as independent human-review evidence;
- the Phase 2 shared-lock and state path identities are not reverified across the locked snapshot;
- Gate B3 hashes one installed `skills-ref` distribution but the adapter can import a different `skills_ref` module selected earlier on `sys.path`;
- Reviewer transient-attempt history is held only in memory until a later success, so interruption resets the attempt budget and loses audit facts.

All four findings were fixed in isolated commits and the expanded release suite now covers the missing invariants. The original findings remain below as the audit source; their applied fixes and commit evidence are recorded in `03-REVIEW-FIX.md`.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-07: Lineage “approval” is synthesized from the binding being approved

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:3976-3994`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/candidate_authority.py:436-461`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/candidate_authority.py:490-535`, `/Users/alexzhu/Lenovo/skillscout/tests/test_phase3_pipeline.py:2124-2139`
**Issue:** `prior_lineage_binding()` computes its own `approval_record_digest`, and `persist_prior_lineage_binding()` then calls `prior_lineage_approval_record(binding)` to reconstruct the alleged approval from the same binding. The approval record contains no independently supplied decision, reviewer identity, or other evidence that a human approved the update. The end-to-end test seeds state by constructing a binding and calling this method directly, so it proves retention without any independent approval input. Any code path able to construct a binding can therefore manufacture the evidence needed to retain lineage, violating the human-control boundary.

**Fix:** Accept the binding and approval as two independently obtained inputs. The approval artifact must carry an affirmative human-review decision and stable reviewer/audit identity, bind the exact binding digest and new WorkflowSpec authority, and be admitted through a separate trusted input path. Persistence must validate the supplied approval against the binding without deriving it. Add negative tests proving a binding alone, a synthesized approval, a mismatched approval, and a missing approval all fail closed; add a positive integration test that supplies an independently created approval artifact.

### CR-08: Phase 2 lock and state authority can change after the shared lock is acquired

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/phase2_state.py:90-116`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:699-737`, `/Users/alexzhu/Lenovo/skillscout/tests/test_candidate_source.py:256-285`
**Issue:** `_open_read_only_verifier()` compares the lock path to the opened lock descriptor before `flock()`, but never re-stats the lock pathname after acquiring the shared lock. It also records `state_metadata` before locking but does not require `_read_stable_private_file()` to read that same state identity. The helper starts a new admission at read time and only compares descriptor metadata; it does not compare the state pathname again after the read. Replacing the lock or state pathname during these gaps can detach the retained lock from the pathname other processes use and can make the accepted snapshot differ from the authority observed before locking.

**Fix:** After `flock()`, re-stat the lock child through the retained parent descriptor and require complete equality with the locked descriptor. Read the state through a retained no-follow descriptor whose opened metadata equals the pre-lock `state_metadata`, then require opened, post-read descriptor, and post-read pathname metadata to remain identical before deserializing. Add deterministic seam tests for lock replacement immediately after `flock()`, state replacement between lock acquisition and open, and state pathname replacement after descriptor open/read.

### CR-09: The validated `skills-ref` distribution is not bound to the imported module

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/skills_ref.py:46-50`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/bootstrap.py:152-223`, `/Users/alexzhu/Lenovo/skillscout/tests/test_phase3_bootstrap.py:89-118`
**Issue:** `_verify_validator_distribution()` validates one distribution returned by `importlib.metadata.distribution("skills-ref")` and returns only its aggregate digest. Later, `_official_validator()` executes `from skills_ref import validate`, which uses normal import-path precedence and is not required to resolve inside the distribution root that was just validated. A different earlier `skills_ref` package or module can therefore be loaded while the authority continues to report the digest of the validated distribution. The current modified-distribution test changes the same distribution copy that metadata discovers; it does not prove that the imported module is the validated one.

**Fix:** Return a typed admission containing the validated distribution root and exact recorded module path/digest. Before import, resolve the `skills_ref` spec without executing it and require its origin/package search paths to equal the admitted RECORD paths; after import, reverify the loaded module origin and bytes against that admission. Fail closed on duplicate distributions or any earlier shadow module. Add a subprocess test with a valid admitted distribution plus a distinct earlier import-path module and prove the earlier module is never executed.

### CR-10: Reviewer retry budget and audit history reset after interruption

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:1001-1030`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:930-967`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/models.py:346-355`, `/Users/alexzhu/Lenovo/skillscout/tests/test_phase3_pipeline.py:2206-2273`
**Issue:** `_retry_review()` accumulates transient failures only in a local list. No Reviewer attempt or failure is persisted until a later successful result produces the attestation and `persist_candidate_stage()` call. If the process is interrupted after a failed remote call, resume starts again at attempt 1 with an empty history, allowing more than `max_reviewer_attempts` total calls and omitting the pre-interruption failures from the audit record. The current ledger model also requires one attempt per successful result, so it cannot represent failed Reviewer attempts. The test exercises three attempts in one uninterrupted invocation and therefore misses the reset.

**Fix:** Persist a Reviewer attempt record before every remote call and persist its sanitized transient failure before starting the next attempt. On resume, reconstruct the exact attempt history from state, count interrupted/in-flight attempts conservatively against the configured maximum, continue only from the next legal attempt number, and build the final attestation from the persisted history. Extend the chain/schema so failed or abandoned Reviewer attempts are verified without requiring a successful result for each one. Add interruption/resume tests after attempts 1 and 2, plus exhaustion across restarts, proving total calls never exceed the configured maximum and the final attestation exactly matches durable history.

## Verification

- Round-2 fix commits: `f62b8c6`, `2f57439`, `f79650b`, `79e573a`
- Test cleanup commit: `2a80975`
- Dependency-free validation-map checker: passed
- Validation-map mutation suite: **41 passed**
- Locked graph check and repository-local build: passed
- Phase 3 acceptance checker: passed
- Ruff: passed
- `sh tools/verify_phase3_gate_b3.sh`
- Repository-local locked unit suite with `UV_CACHE_DIR="$PWD/.tools/uv-cache"` and `.tools/uv-0.11.29/bin/uv`
- Result: **1241 passed in 32.61s**
- Terminal Gate B3 postflight: passed
- Resolution status: all four Round-2 blockers fixed

---

_Reviewed: 2026-07-23T15:29:37Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
