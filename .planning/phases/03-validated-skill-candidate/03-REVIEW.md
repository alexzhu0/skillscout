---
phase: 03-validated-skill-candidate
reviewed: 2026-07-23T16:24:24Z
round: 4
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
  critical: 0
  warning: 0
  info: 0
  total: 0
resolved_findings:
  critical: 12
  warning: 1
  info: 0
  total: 13
status: clean
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-23T16:24:24Z
**Round:** 4
**Depth:** deep
**Files Reviewed:** 19
**Status:** clean

## Summary

Round 4 independently reviewed the complete CR-01 through CR-12 / WR-01 fix
chain, including the Round-3 red/green commits `1d83d02` and `279b61d`. No new
blocker or warning was found, and every prior finding remains closed.

Generator and Reviewer now satisfy the same durable-attempt invariants. A
`running` record is committed before every remote call; interruption consumes
that authority-bound attempt; transient histories and exhaustion survive
restart; sanitized permanent or invalid post-call outcomes are finalized and
replayed without another call; and a successful result, checkpoint, and exact
recovery payload are persisted before control returns to the cascade.

The earlier trust and recovery fixes also remain intact: lineage approval is an
independent typed input, the Phase 2 lock/state snapshot is identity-stable, the
official validator import is bound to its admitted distribution, runtime policy
changes alter execution authority, completed package identities are
cross-checked, output projection is recoverable, and dependency admission still
precedes dependency import.

## Narrative Findings (AI reviewer)

No Round-4 blocker, warning, or information finding.

## Resolved Round-3 Findings

### CR-11: Generator retry budget resets on every restart of the same run

**Classification:** BLOCKER
**Round-3 fix status:** RESOLVED — `279b61d`, regression tests in `1d83d02`.
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
**Round-3 fix status:** RESOLVED — `279b61d`, regression tests in `1d83d02`.
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

- Reviewed every CR-01 through CR-12 / WR-01 fix commit from `e52ed6e` through
  `279b61d`, including the separate Round-3 regression commit `1d83d02`.
- B3-prefixed focused semantic-attempt restart/exhaustion/in-flight/post-call
  matrix: **10 passed**.
- B3-prefixed independent Round-4 probes outside the production tree:
  Generator post-call token-budget rejection and Reviewer post-call invalid
  output both replayed durably with exactly one remote call; **2 passed**.
- B3-prefixed CR-01 through CR-10 / WR-01 closure matrix: **95 passed**.
- B3-prefixed full repository suite: **1,247 passed in 32.48s**.
- Terminal `sh tools/verify_phase3_gate_b3.sh` postflight: passed after every
  successful dependency-backed run.
- `git diff 1d83d02^..279b61d --check`: passed.

## Prior-Finding Reverification

| Finding | Round-4 result | Evidence |
|---|---|---|
| CR-01 / CR-07 | closed | Real-state retained-lineage path requires separately supplied typed approval; binding-only and mismatched approval paths reject. |
| CR-02 / CR-08 | closed | Shared-lock admission and all three lock/state replacement seams pass. |
| CR-03 / CR-11 | closed | Generator attempts are authority-capped, durable across interruption/restart, and retain exact sanitized running/failed/abandoned/succeeded history. |
| CR-04 | closed | Pending projection remains recoverable and completed reuse is exposed only after projection completion. |
| CR-05 | closed | Rendered-package/manifest substitution and uncited artifact tests reject. |
| CR-06 / CR-09 | closed | Import-before-gate, modified-distribution, duplicate-distribution, and shadow-module canaries pass. |
| WR-01 / CR-10 / CR-12 | closed | Reviewer transient, in-flight, exhaustion, and post-call permanent failure paths are durable; deterministic rejection replays without another call. |

---

_Reviewed: 2026-07-23T16:24:24Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
