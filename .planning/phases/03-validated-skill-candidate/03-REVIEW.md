---
phase: 03-validated-skill-candidate
reviewed: 2026-07-23T15:58:16Z
round: 3
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
  critical: 2
  warning: 0
  info: 0
  total: 2
resolved_findings:
  critical: 10
  warning: 1
  info: 0
  total: 11
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-23T15:58:16Z
**Round:** 3
**Depth:** deep
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Round 3 independently reverified the five Round-2 fix commits (`f62b8c6`,
`2f57439`, `f79650b`, `79e573a`, and `2a80975`) and the earlier CR-01 through
CR-06 / WR-01 fixes. The exact previously reported defects remain closed:
independent lineage approval is required, the Phase 2 lock/state snapshot is
identity-stable, the imported validator is bound to its admitted distribution,
transient Reviewer history survives interruption, completed packages remain
identity-bound, projection is recoverable, and the dependency gate still
precedes imports.

The phase is not clean. Two normal restart/failure paths still violate the
configured semantic-call limits and durable audit contract:

- Generator attempts are never persisted before or after failed calls, so the
  same resumable run gets a fresh three-call budget on every invocation.
- A Reviewer result rejected by the caller's post-call token-ceiling check is
  left `running`; resume records the completed call as `abandoned` and calls the
  Reviewer again.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-11: Generator retry budget resets on every restart of the same run

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:1086-1102`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:756-768`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:832-847`
**Issue:** `_retry_generate()` keeps all failed Generator attempts in a local
loop and writes nothing until a successful Generator result is converted to a
stage result. After three transient failures, the run remains resumable at the
qualifier checkpoint. Calling the application again starts Generator attempt 1
and permits three more remote calls under the same execution authority. A
B3-prefixed Round-3 regression invoked the same run twice and observed six
Generator calls despite `max_generator_attempts == 3`. If a later invocation
succeeds, the ledger records only that invocation's attempt number and omits all
earlier calls. This violates the project's hard per-run LLM-call cap and makes
the execution audit false.

**Fix:** Persist a typed Generator attempt before every remote call and finalize
every success, transient failure, permanent failure, invalid result, and
post-call budget rejection. Reconstruct the Generator attempt history on resume,
count an in-flight attempt conservatively, and refuse further calls when the
authority-bound total is exhausted. Extend `VerifiedCandidateRunChain` and the
state mutation path to validate multiple failed/abandoned Generator attempts
before one optional success. Add interruption and exhaustion-across-restart
tests equivalent to the Reviewer tests.

### CR-12: Post-call Reviewer rejection is recorded as interruption and retried

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:1026-1042`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:1175-1191`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:1124-1137`
**Issue:** `_retry_review()` returns while the durable Reviewer attempt is still
`running`. The completion-token ceiling is checked only afterward. When a valid
Reviewer response exceeds that ceiling, the caller raises
`stage_permanent_failure` without finalizing the attempt. On resume, the runner
rewrites that genuinely completed remote call as `attempt_interrupted`, then
issues another call. A B3-prefixed Round-3 regression observed two Reviewer
calls across two invocations and a ledger of `[abandoned, running]`; the correct
history was one completed call rejected for a permanent budget violation.
Repeated invocations eventually replace the original permanent failure with
`retry_exhausted`, corrupting both behavior and audit evidence.

**Fix:** Keep all validation of the returned `ReviewResult`, including output
token limits and disposition/attestation construction needed to accept it,
inside the durable attempt lifecycle. Finalize the attempt with the exact
sanitized permanent failure before propagating it, and make resume reproduce
that failure without another remote call. Add a restart test for over-budget
Reviewer output that asserts one total call and one durable failed attempt.

## Reverified Round-2 Findings

### CR-07: Lineage “approval” is synthesized from the binding being approved

**Classification:** BLOCKER
**Round-3 status:** RESOLVED — `f62b8c6`, with test cleanup in `2a80975`.
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:3976-3994`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/candidate_authority.py:436-461`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/candidate_authority.py:490-535`, `/Users/alexzhu/Lenovo/skillscout/tests/test_phase3_pipeline.py:2124-2139`
**Issue:** `prior_lineage_binding()` computes its own `approval_record_digest`, and `persist_prior_lineage_binding()` then calls `prior_lineage_approval_record(binding)` to reconstruct the alleged approval from the same binding. The approval record contains no independently supplied decision, reviewer identity, or other evidence that a human approved the update. The end-to-end test seeds state by constructing a binding and calling this method directly, so it proves retention without any independent approval input. Any code path able to construct a binding can therefore manufacture the evidence needed to retain lineage, violating the human-control boundary.

**Fix:** Accept the binding and approval as two independently obtained inputs. The approval artifact must carry an affirmative human-review decision and stable reviewer/audit identity, bind the exact binding digest and new WorkflowSpec authority, and be admitted through a separate trusted input path. Persistence must validate the supplied approval against the binding without deriving it. Add negative tests proving a binding alone, a synthesized approval, a mismatched approval, and a missing approval all fail closed; add a positive integration test that supplies an independently created approval artifact.

### CR-08: Phase 2 lock and state authority can change after the shared lock is acquired

**Classification:** BLOCKER
**Round-3 status:** RESOLVED — `2f57439`.
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/phase2_state.py:90-116`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:699-737`, `/Users/alexzhu/Lenovo/skillscout/tests/test_candidate_source.py:256-285`
**Issue:** `_open_read_only_verifier()` compares the lock path to the opened lock descriptor before `flock()`, but never re-stats the lock pathname after acquiring the shared lock. It also records `state_metadata` before locking but does not require `_read_stable_private_file()` to read that same state identity. The helper starts a new admission at read time and only compares descriptor metadata; it does not compare the state pathname again after the read. Replacing the lock or state pathname during these gaps can detach the retained lock from the pathname other processes use and can make the accepted snapshot differ from the authority observed before locking.

**Fix:** After `flock()`, re-stat the lock child through the retained parent descriptor and require complete equality with the locked descriptor. Read the state through a retained no-follow descriptor whose opened metadata equals the pre-lock `state_metadata`, then require opened, post-read descriptor, and post-read pathname metadata to remain identical before deserializing. Add deterministic seam tests for lock replacement immediately after `flock()`, state replacement between lock acquisition and open, and state pathname replacement after descriptor open/read.

### CR-09: The validated `skills-ref` distribution is not bound to the imported module

**Classification:** BLOCKER
**Round-3 status:** RESOLVED — `f79650b`.
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/skills_ref.py:46-50`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/bootstrap.py:152-223`, `/Users/alexzhu/Lenovo/skillscout/tests/test_phase3_bootstrap.py:89-118`
**Issue:** `_verify_validator_distribution()` validates one distribution returned by `importlib.metadata.distribution("skills-ref")` and returns only its aggregate digest. Later, `_official_validator()` executes `from skills_ref import validate`, which uses normal import-path precedence and is not required to resolve inside the distribution root that was just validated. A different earlier `skills_ref` package or module can therefore be loaded while the authority continues to report the digest of the validated distribution. The current modified-distribution test changes the same distribution copy that metadata discovers; it does not prove that the imported module is the validated one.

**Fix:** Return a typed admission containing the validated distribution root and exact recorded module path/digest. Before import, resolve the `skills_ref` spec without executing it and require its origin/package search paths to equal the admitted RECORD paths; after import, reverify the loaded module origin and bytes against that admission. Fail closed on duplicate distributions or any earlier shadow module. Add a subprocess test with a valid admitted distribution plus a distinct earlier import-path module and prove the earlier module is never executed.

### CR-10: Reviewer retry budget and audit history reset after interruption

**Classification:** BLOCKER
**Round-3 status:** RESOLVED for pre-call, in-flight, and transient-failure
interruption paths — `79e573a`. CR-12 covers the distinct post-call failure gap.
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:1001-1030`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:930-967`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/models.py:346-355`, `/Users/alexzhu/Lenovo/skillscout/tests/test_phase3_pipeline.py:2206-2273`
**Issue:** `_retry_review()` accumulates transient failures only in a local list. No Reviewer attempt or failure is persisted until a later successful result produces the attestation and `persist_candidate_stage()` call. If the process is interrupted after a failed remote call, resume starts again at attempt 1 with an empty history, allowing more than `max_reviewer_attempts` total calls and omitting the pre-interruption failures from the audit record. The current ledger model also requires one attempt per successful result, so it cannot represent failed Reviewer attempts. The test exercises three attempts in one uninterrupted invocation and therefore misses the reset.

**Fix:** Persist a Reviewer attempt record before every remote call and persist its sanitized transient failure before starting the next attempt. On resume, reconstruct the exact attempt history from state, count interrupted/in-flight attempts conservatively against the configured maximum, continue only from the next legal attempt number, and build the final attestation from the persisted history. Extend the chain/schema so failed or abandoned Reviewer attempts are verified without requiring a successful result for each one. Add interruption/resume tests after attempts 1 and 2, plus exhaustion across restarts, proving total calls never exceed the configured maximum and the final attestation exactly matches durable history.

## Verification

- Commit inspection: `f62b8c6`, `2f57439`, `f79650b`, `79e573a`,
  `2a80975`, plus the earlier CR-01..06 / WR-01 fixes.
- Repository-local locked suite, prefixed by Gate B3: **1241 passed in
  36.20s**.
- Terminal `sh tools/verify_phase3_gate_b3.sh` postflight: passed.
- Round-3 temporary regression suite, prefixed by Gate B3: **2 failed as
  expected**, exposing CR-11 and CR-12.
- CR-11 observed: **6 Generator calls** across two resumptions under a configured
  total of 3.
- CR-12 observed: the second invocation made a second Reviewer call; durable
  statuses were `abandoned, running` instead of one permanent `failed` attempt.

## Prior-Finding Reverification

| Finding | Round-3 result | Evidence |
|---|---|---|
| CR-01 / CR-07 | closed | Real-state retained-lineage path requires separately supplied typed approval; binding-only and mismatched approval paths reject. |
| CR-02 / CR-08 | closed | Shared-lock admission and all three lock/state replacement seams pass. |
| CR-03 | original authority-binding and call-boundary checks closed | Runtime-profile sensitivity and token-ceiling tests pass; CR-11 is a newly isolated cross-restart Generator-budget defect. |
| CR-04 | closed | Pending projection remains recoverable and completed reuse is exposed only after projection completion. |
| CR-05 | closed | Rendered-package/manifest substitution and uncited artifact tests reject. |
| CR-06 / CR-09 | closed | Import-before-gate, modified-distribution, duplicate-distribution, and shadow-module canaries pass. |
| WR-01 / CR-10 | original retry-history paths closed | Transient failures, in-flight abandonment, and exhaustion across restarts pass; CR-12 is a distinct returned-result failure path. |

---

_Reviewed: 2026-07-23T15:58:16Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
