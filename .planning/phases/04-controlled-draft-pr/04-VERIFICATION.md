---
phase: 04-controlled-draft-pr
verified: 2026-07-27T11:43:31Z
status: passed
score: 11/11 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 11/11
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 4: Controlled Draft PR Verification Report

**Phase Goal:** 对一个通过全部门禁的 Skill，系统只能在受控 catalog 中创建或更新机器分支和 Draft PR，并请求人类审核；平台权限实测禁止自动化身份写默认分支或 merge。
**Verified:** 2026-07-27T11:43:31Z
**Status:** passed
**Re-verification:** Yes — after final documentation/tracking synchronization; no production or workflow changes

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Only an exact, eligible Phase 3 candidate can cross publication admission, and candidate evidence remains free of catalog/reviewer authority. | ✓ VERIFIED | `admit_phase3_candidate` reconstructs the exact terminal artifact matrix and frozen files in `src/skillscout/domain/publication.py:232`; protected authority is added only by `derive_publication_intent`/`bind_publication_admission`. Domain mutation and zero-capability-call tests passed in the full locked suite. |
| 2 | The short-lived write path is confined to the configured catalog, deterministic machine branch, verified manifest files, Draft PR, and configured individual reviewers; team configuration fails before token/network access. | ✓ VERIFIED | Authority/team rejection is at `src/skillscout/bootstrap.py:70`; catalog/default/head/root binding and users-only requests are in `src/skillscout/adapters/github_publish.py:103` and `:346`; the protected token action is after admission at `.github/workflows/publish-candidate.yml:121-154`. Security and adapter behavior tests passed. |
| 3 | The Draft PR body contains the required source, exact SHA, license, fingerprint, qualification, validation, independent-review, and human-review evidence. | ✓ VERIFIED | Deterministic rendering exists at `src/skillscout/domain/publication.py:280`; `tests/test_publication_domain.py` exercises the complete body and marker contract and passed. |
| 4 | Repeating the same stable slug reuses or updates one Draft, and local publication-state loss can be reconstructed from exact remote state without duplicate PRs. | ✓ VERIFIED | Reconcile-first selection and reconstruction are implemented at `src/skillscout/application/publication.py:83` and `:145`. `test_completed_intent_is_remotely_revalidated_without_reopening_ledger` and `test_local_state_loss_reconstructs_exact_remote_completion_without_writes` passed. |
| 5 | Non-Draft, ambiguous, human-conflicted, malformed-lineage, reviewer-ambiguous, or non-manifest remote state stops with bounded manual intervention and no unsafe overwrite. | ✓ VERIFIED | Exact Draft/head/base/marker/lineage/reviewer/tree checks precede updates at `src/skillscout/application/publication.py:155-204`; non-force ref updates and owned-root-only tree writes are enforced at `src/skillscout/adapters/github_publish.py:284-328`. Stateful conflict and zero-write tests passed. |
| 6 | Stateful recovery verifies actual remote results, uses stable machine lineage, deletes stale owned files, and does not re-notify pending/completed reviewers. | ✓ VERIFIED | Remote terminal re-read is at `src/skillscout/application/publication.py:498`; hash-linked terminal persistence follows only at `:563`; stale deletion is derived in `_write_commit`; reviewer durability is validated at `:310`. Multi-revision, stale-file, crash, removed-reviewer, and completed-reviewer tests passed. |
| 7 | Production exposes no merge, approval, ready-for-review, auto-merge, GraphQL, ruleset/admin, cleanup, arbitrary request, PUT, DELETE, force push, or default-ref write surface; candidate values are not interpolated into workflow shell text. | ✓ VERIFIED | The adapter's public operations and HTTP literals are restricted to catalog-bound GET/POST/PATCH calls; machine updates serialize `force: false`. Static AST/workflow allowlist tests passed, and the manual source scan found no forbidden production route or method. |
| 8 | The workflow uses the exact Gate A4-approved Action identities, minimum top-level permissions, a protected environment, candidate-only cross-job handoff, and late catalog-scoped token minting. | ✓ VERIFIED | Current pins are checkout `11bd71901bbe5b1630ceea73d27597364c9af683` and token action `67018539274d69449ef7c8cde82c3ff073ffe3b5`; the current action-audit digest is `d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622`, exactly matching Gate A4. Workflow ordering and output allowlists are visible at `.github/workflows/publish-candidate.yml:28-161` and passed mutation tests. |
| 9 | Gate B4 proves the same production installation can create the intended Draft/reviewer flow but cannot write the default ref, merge, mutate rulesets, or access unauthorized repositories/secrets; ready-for-review residual risk is explicit. | ✓ VERIFIED | The non-auto-approvable Gate B4 record contains the production installation/catalog/ruleset identities, causal denial results, unchanged default SHA, clean secret scan, and separate-authority cleanup. Its approved workflow SHA-256 `224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c` exactly equals the current workflow. |
| 10 | All 14 prior code-review findings remain closed in current code and behavioral coverage. | ✓ VERIFIED | CR-01–CR-08 and WR-01–WR-06 map to current production logic and named regression tests; all those tests ran in the full suite. `04-REVIEW-FIX.md` records 14/14 fixed and the subsequent `04-REVIEW.md` is clean, but the verdict here is based on current code/test inspection rather than those claims. |
| 11 | The complete repository-local locked release chain is green. | ✓ VERIFIED | Fresh re-run: validation-map verifier valid; action-audit verifier valid; Ruff `All checks passed!`; pytest `1410 passed, 2 skipped in 33.59s`; acceptance verifier valid. The skips are the intentionally opt-in live-canary paths already covered by the completed Gate B4 evidence. |

**Score:** 11/11 truths verified (0 present but behavior-unverified)

### Re-verification Regression Check

- Final synchronization changed only `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, and `04-11-SUMMARY.md`; no Phase 4 production, workflow, test, fixture, or verifier file changed after the initial verification.
- The latest commit touching the scoped production/workflow files remains `586fd11d27262604fdccb4caba0672856bc3a813`.
- Current workflow SHA-256 remains `224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c`; current action-audit SHA-256 remains `d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622`.
- The exact locked release chain was rerun after the documentation synchronization and passed with no regressions.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/skillscout/domain/publication.py` | Closed admission, authority, identity, marker, body, record contracts | ✓ VERIFIED | 334 substantive lines; imported by bootstrap/application/tests; exact artifact and authority separation are exercised. |
| `src/skillscout/adapters/github_publish.py` | Catalog-bound finite GitHub REST capability | ✓ VERIFIED | 504 substantive lines; constructed only by the protected factory and consumed by the application; route/method allowlist tests pass. |
| `src/skillscout/adapters/publication_state.py` | Dedicated canonical checkpoint/terminal store | ✓ VERIFIED | 190 substantive lines; wired through `build_publication_application`; corruption, binding, persistence, and closure tests pass. |
| `src/skillscout/application/publication.py` | Reconcile-first, idempotent publication state machine | ✓ VERIFIED | 629 substantive lines; wired from CLI/bootstrap to the closed adapter/store and exercised statefully for create/update/reuse/recovery/conflict. |
| `src/skillscout/bootstrap.py` and `src/skillscout/cli.py` | Protected authority, late token, closed verifier/publisher entry points | ✓ VERIFIED | Fixed locator-only CLI contracts; exact candidate handoff and protected admission are wired before remote construction. |
| `.github/workflows/publish-candidate.yml` | Manual protected publication workflow | ✓ VERIFIED | Current SHA-256 matches Gate B4; exact Gate A4 action pins, `contents: read`, protected environment, and late token order verified. |
| `tests/fixtures/github_publish/` and Phase 4 test modules | Offline provider, recovery, security, CLI, gate, and mutation evidence | ✓ VERIFIED | Fixture corpus and all declared test modules exist and participated in the 1410-test run. |
| `tools/verify_phase4_action_audit.py` | Exact action-evidence verifier | ✓ VERIFIED | Fresh execution: `phase4 action audit valid`; mutation suite passed. |
| `tools/verify_phase4_validation_map.py` | Exact 25-task/requirement inverse-map verifier | ✓ VERIFIED | Fresh execution: `phase4 validation map valid`; mutation suite passed. |
| `tools/verify_phase4_acceptance.py` | Independent read-only phase acceptance inspector | ✓ VERIFIED | Fresh execution: `phase4 acceptance valid`; mutation suite passed. |
| `04-08-SUMMARY.md` and `04-10-SUMMARY.md` | Non-auto-approvable Gate A4/B4 decision evidence | ✓ VERIFIED | Both records are present; their approved audit/workflow identities match current bytes exactly. |

The generic `gsd-tools verify.artifacts` check passed every file artifact it could parse. It cannot consume Plan 02's directory artifact and treats component-name `key_links.from` values as file paths; those tool-level parse failures were not accepted as evidence and all affected artifacts/links were verified manually below.

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Completed Phase 3 projection | Candidate publication evidence | Exact canonical terminal/artifact reconstruction | ✓ WIRED | `verify_publication_admission_handoff` projects completed state and calls `admit_phase3_candidate` before protected authority. |
| Candidate evidence + protected catalog/reviewers | Publication admission | Protected-local deterministic derivation | ✓ WIRED | Handoff equality precedes `load_publication_authority_config`, intent derivation, and admission binding at `bootstrap.py:276-315`. |
| Publication admission | Token-backed GitHub client | State admission and delayed remote factory | ✓ WIRED | Application begins canonical attempt before calling the remote factory; token access exists only inside that factory at `bootstrap.py:347-361`. |
| Frozen publication files | Git blobs/tree/commit/ref | Exact bytes, Git blob IDs, null deletions, one non-force ref move | ✓ WIRED | `_write_commit` consumes `admission.evidence.files`; final verification compares the complete owned subtree with derived Git blob object IDs. |
| Remote catalog/ref/commit/tree/Draft/reviews | Publication record | Full post-mutation re-observation before terminal persistence | ✓ WIRED | `_verify_remote` re-reads every remote fact; `_persist_verified` checkpoints `remote_verified` and then completes the local record. |
| Gate A4 action audit | Production workflow | Exact immutable `uses:` references | ✓ WIRED | Current action audit digest and both workflow pins equal the human-approved identities. |
| Production workflow | Gate B4 evidence | Exact workflow content digest and installation identity | ✓ WIRED | Current workflow digest equals the post-review Gate B4 digest; the canary record binds the production installation and separately authorized cleanup. |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Produces Real Data | Status |
|---|---|---|---|---|
| Publication admission | Frozen package files and Phase 2/3 digests | Canonical completed Phase 3 projection | Yes — exact bytes/digests are re-parsed and cross-validated | ✓ FLOWING |
| Git publication state machine | Blobs, tree, commit, branch, Draft and reviewer observations | Closed GitHub adapter responses | Yes — mutation results are re-read from remote truth before success | ✓ FLOWING |
| Publication ledger | Intent, checkpoints, terminal record | Canonical state-machine transitions | Yes — hash-linked snapshots and remote IDs/SHAs, no raw provider data | ✓ FLOWING |
| Public CLI result | Disposition and bounded stable IDs/digests | Verified `PublicationApplicationResult` | Yes — created/updated/reused remain distinct | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command / evidence | Result | Status |
|---|---|---|---|
| All current behavior, including state transitions and recovery invariants | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` | `1410 passed, 2 skipped in 33.59s` | ✓ PASS |
| Static quality | `.tools/uv-0.11.29/bin/uv run --locked ruff check .` | `All checks passed!` | ✓ PASS |
| Exact validation/task map | `... python tools/verify_phase4_validation_map.py` | `phase4 validation map valid` | ✓ PASS |
| Exact action audit | `... python tools/verify_phase4_action_audit.py` | `phase4 action audit valid` | ✓ PASS |
| Independent acceptance | `... python tools/verify_phase4_acceptance.py` | `phase4 acceptance valid` | ✓ PASS |
| Gate B4 platform behavior | Existing separately authorized live canary and human review | `5 passed, 1 skipped`; causal denials and cleanup recorded | ✓ PASS |

### Probe Execution

No Phase 4 `scripts/**/tests/probe-*.sh` files or plan-declared shell probes exist. The three declared independent Python verifiers were executed directly and passed.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| PUB-01 | 04-01–06, 04-09–11 | Controlled catalog/machine branch/verified artifact/Draft/reviewer publication | ✓ SATISFIED | Exact admission, closed adapter, stateful application, protected workflow, Gate B4 positive flow. |
| PUB-02 | 04-01, 04-03, 04-06, 04-11 | Complete deterministic PR body and human warning | ✓ SATISFIED | Renderer and golden domain tests. |
| PUB-03 | 04-01, 04-03–04, 04-06, 04-09–11 | No merge/approve/ready/default/ruleset/admin capability | ✓ SATISFIED | Source/AST/workflow allowlists, transport tests, and Gate B4 scoped evidence. |
| PUB-04 | 04-02, 04-07–11 | Short-lived least-privilege App identity and platform controls | ✓ SATISFIED | Gate A4 exact pins, protected environment/token scope, Gate B4 catalog/ruleset/denial evidence. |
| PUB-05 | 04-02–06, 04-10–11 | Stable identity, Draft reuse/update, local-state-loss recovery | ✓ SATISFIED | Reconcile-first application and stateful create/update/reuse/recovery tests. |
| SEC-02 | 04-01, 04-04, 04-06–11 | Minimal Actions permissions, full-SHA pins, protected environment, structured output, no candidate shell interpolation | ✓ SATISFIED | Current workflow/source inspection, exact hashes, security tests, action and acceptance verifiers. |

No Phase 4 requirement is orphaned: all six IDs appear in Phase 4 plan frontmatter and map to implementation/test evidence. Their pending checkboxes in `REQUIREMENTS.md` and the unchecked Phase 4 roadmap entries are workflow tracking state for the orchestrator, not missing implementation; those files were intentionally not modified by this verifier.

### Review Finding Closure

| Findings | Current closure evidence | Status |
|---|---|---|
| CR-01–CR-03 | Actual-SHA marker persistence, Git blob object IDs, and mandatory remote re-observation before terminal success | ✓ CLOSED |
| CR-04–CR-06 | Completed-attempt remote revalidation, exact-404 ref absence, and publication-state confinement before token/state | ✓ CLOSED |
| CR-07–CR-08 | Bounded multi-revision machine lineage and durable completed-review evidence without re-notification | ✓ CLOSED |
| WR-01–WR-03 | Canonical same-origin pagination, stateful production-application recovery tests, and executed/redacted provider error matrix | ✓ CLOSED |
| WR-04–WR-06 | Store/remote closure, preserved CLI dispositions/IDs, and terminal record binding to publication key/revision | ✓ CLOSED |

**Closure total:** 14/14. No regression was observed in current source or the fresh re-verification test run.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| — | — | No unreferenced `TBD`, `FIXME`, or `XXX`; no production placeholder/stub; no forbidden publication route/method | — | None |

The scan's only merge/approve text in production is the human-review warning rendered into the Draft body, not executable capability.

### Gaps Summary

No blocking or warning gaps, no outstanding human-verification items, and no behavior-dependent truth remains unexercised. Gate A4 and Gate B4 are already completed and remain bound to the current action-audit/workflow bytes. The phase goal is achieved in the current codebase. The only documented residual is the already human-accepted possibility that a stolen coarse `pull_requests: write` token could express ready-for-review outside SkillScout; SkillScout's production adapter, CLI, and workflow have no such capability.

---

_Verified: 2026-07-27T11:43:31Z_
_Verifier: the agent (gsd-verifier)_
