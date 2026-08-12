---
status: resolved
trigger: "After completed Plan 05-06, the full locked suite has three historical Phase 1/3 scanner failures because src/skillscout/adapters/state_branch.py imports httpx for fixed state-branch operations; 1,562 tests otherwise pass."
created: 2026-07-27
updated: 2026-07-27T15:25:00Z
---

# Debug Session: Phase 5 State-Branch HTTPX Scanner Drift

## Symptoms

- expected: Phase 5 state-branch support passes historical security boundary scanners without widening HTTP or publication authority.
- actual: Three historical Phase 1/3 scanner tests fail after Plan 05-06 while 1,562 other tests pass.
- errors: Exact pre-Phase-5 `httpx` importer baselines reject `src/skillscout/adapters/state_branch.py`.
- reproduction: Run the focused Phase 1/3 scanner tests with the repository-local locked toolchain.

## Current Focus

- hypothesis: RESOLVED — the historical scanners rejected the planned `state_branch.py:httpx` owner because their exact HTTP-owner baselines predated Plan 05-06, even though that adapter is structurally limited to fixed state-repository Git objects and `refs/heads/skillscout-state`.
- test: Human independently reran the full locked suite and repository checks at commit `f05247c`.
- expecting: Satisfied — the locked suite reports zero failures, the former Phase 1/3 scanner paths are green, and the repository contains only this resolution metadata beyond the isolated fix commit.
- next_action: Archive the resolved session, append the knowledge-base entry, and commit only those resolution metadata paths.
- reasoning_checkpoint:
    hypothesis: Historical Phase 1 and Phase 3 acceptance scanners reject the legitimate `adapters/state_branch.py:httpx` import because their exact owner baselines were established before Plan 05-06; the production adapter itself does not grant catalog/default-branch authority because it exposes only fixed Git object/state-ref methods and hard-codes `refs/heads/skillscout-state`.
    confirming_evidence:
      - The unchanged focused baseline is exactly 3 failed and 56 passed; Phase 1 identifies only `adapters/state_branch.py:httpx`, and both Phase 3 failures originate at the exact HTTP owner comparison.
      - Complete AST enumeration finds exactly three HTTP owners and zero forbidden imports; changing only the in-memory Phase 3 expected owner set makes the capability check pass.
      - The complete state adapter/source contract uses a configured repository plus only the fixed state ref, no arbitrary request/PR/reviewer/merge/delete methods, and its unchanged 24-test security/restore/CAS suite passes.
    falsification_test: This hypothesis would be false if another forbidden import/call remained after the in-memory owner-set change, if the state suite failed, or if a scanner implementation that admits this owner also admitted off-owner `httpx`, a `/pulls` catalog path, or a `refs/heads/main` mutation.
    fix_rationale: Adding only `state_branch.py:httpx` to the two exact owner policies reconciles the planned owner, while independently pinning the StateBranchClient public methods, fixed state ref/endpoints, non-force update, and prohibited catalog/default-branch tokens ensures the exception represents one reviewed capability rather than general HTTP authority.
    blind_spots: Static AST/source checks cannot prove dynamically constructed behavior outside scanned source, but the scanner already closes dynamic-import and execution surfaces, and the adapter's offline recorded transport/store tests directly exercise its intended request and mutation paths without network authority.

### Fault Tree

- observed symptom: historical Phase 1/3 scanners reject the Phase 5 state-branch adapter
  - OR H1: exact scanner baselines are stale and reject a legitimate, separately bounded HTTP owner
  - OR H2: `state_branch.py` actually widens HTTP authority beyond its intended state-branch capability
  - OR H3: the scanner failures hide another forbidden import/call or catalog/default-branch mutation path
  - OR H4: state-branch persistence should reuse an existing HTTP owner rather than introduce a new owner

## Evidence

- timestamp: 2026-07-27T15:01:00Z
  checked: `.planning/debug/knowledge-base.md`
  found: The prior resolved `phase5-scanner-drift` entry overlaps on Phase 1/3 scanners and three forbidden-capability failures; its root cause was an obsolete scanner capability model, fixed with an exact owner/module carve-out plus negative mutations.
  implication: This is a known-pattern candidate for H1, not a diagnosis; test the current `httpx` owner and its distinct mutation authority directly.
- timestamp: 2026-07-27T15:01:00Z
  checked: Project skill indexes and git worktree
  found: No project-defined skills exist. The only worktree change is this untracked debug session; HEAD is completed Plan 05-06 commit `6ba47b4`.
  implication: Focused failures can be reproduced against an otherwise clean, attributable baseline without overwriting user or peer changes.
- timestamp: 2026-07-27T15:03:00Z
  checked: Unchanged focused Phase 1/3 scanner baseline
  found: The locked command yields exactly 3 failed and 56 passed. Phase 1 reports only `adapters/state_branch.py:httpx`; Phase 3 fails only because its exact `EXPECTED_HTTPX_IMPORTERS` comparison is false, and its CLI wrapper then returns the same bounded invalid result.
  implication: The reported regression is reproduced. H1 remains viable, but the adapter's concrete mutation authority and the scanner's full finding set must be inspected before changing policy.
- timestamp: 2026-07-27T15:08:00Z
  checked: Complete `state_branch.py`, `test_state_branch.py`, both scanner implementations/tests, and Plan 05-06 plan/summary/patterns
  found: `StateBranchClient` is constructor-bound to one repository, has only named Git object/ref methods, hard-codes `refs/heads/skillscout-state` for ref reads/creates/updates, serializes `force=False`, and exposes no arbitrary request, PR, reviewer, merge, deletion, or catalog method. Plan 05-06 explicitly reviewed `httpx` as the existing stack for this fixed state capability, and its 24-test suite covers tree allowlisting, canary rejection, parent binding, non-force writes, and reread conflicts.
  implication: Source and executable contracts support a third HTTP owner with a distinct fixed-state capability. However, merely adding the filename to the expected set would not make the historical scanner independently preserve the new owner's no-catalog/default-branch boundary; the scanner fix needs an exact state-client surface check plus negative mutations.
- timestamp: 2026-07-27T15:08:00Z
  checked: Phase 1 and Phase 3 scanner predicates
  found: Phase 1 authorizes `httpx` only through the per-file `IMPORT_CARVE_OUTS` map; Phase 3 independently pins the exact `httpx` owner set to only `github.py` and `github_publish.py`. Neither current policy admits `state_branch.py`; Phase 3 currently checks publication capability text but has no state-branch capability assertion.
  implication: The direct mismatch is stale acceptance policy, while the safe change must pair exact owner admission with state-specific capability invariants instead of broadly permitting `httpx`.
- timestamp: 2026-07-27T15:10:00Z
  checked: In-memory single-variable Phase 3 counterfactual and complete import enumeration
  found: The scanner enumerates exactly `github.py`, `github_publish.py`, and `state_branch.py` as `httpx` owners; its forbidden list is empty. Replacing only the in-memory expected owner set with those three makes `_check_import_capability_isolation` pass.
  implication: H1 is causally confirmed and H3 is eliminated: the Phase 3 failure is solely the obsolete exact owner baseline, not another hidden forbidden capability. The fix can remain scanner/test-only.
- timestamp: 2026-07-27T15:11:00Z
  checked: Unchanged `tests/test_state_branch.py`
  found: All 24 offline state-branch tests pass.
  implication: H2 is eliminated: the reviewed adapter contract still enforces exact tree/path/digest validation, fixed-ref non-force mutation, parent binding, canary rejection, and conflict-closed reread behavior before any scanner change.
- timestamp: 2026-07-27T15:16:00Z
  checked: Focused post-fix Phase 1/3 scanners, negative mutations, and state-branch suite
  found: All 89 tests pass, including the three former failure paths, off-owner `httpx` denial, exact three-owner enforcement, catalog `/pulls` denial, default-branch ref denial, public method denial, and all 24 unchanged state-branch tests.
  implication: The minimal fix resolves the original regression while executable mutations preserve the intended HTTP and target-operation boundaries.
- timestamp: 2026-07-27T15:18:00Z
  checked: Ruff, scoped diff review, worktree status, and `git diff --check`
  found: Ruff passes all three changed Python files; `git diff --check` is clean. The code diff contains only the two independent scanner policies, their regression/mutation tests, and deletion of the sole resolved 05-06 deferred item; the only additional path is this debug session.
  implication: The fix is isolated, formatted, and ready for full regression verification.
- timestamp: 2026-07-27T15:20:00Z
  checked: Complete locked repository pytest suite
  found: 1,571 passed, 2 skipped, and 93 expected xfailed in 38.08 seconds with zero failures.
  implication: The original regressions are fixed without breaking historical, discovery, publication, operations, semantic-provider, or security behavior.
- timestamp: 2026-07-27T15:22:00Z
  checked: Atomic fix commit
  found: Commit `f05247c` contains exactly the two scanner policy changes, their regression/mutation tests, and removal of the resolved 05-06 deferred item; the active debug session was excluded.
  implication: The verified fix is durably isolated and ready for required human confirmation before session archival.
- timestamp: 2026-07-27T15:25:00Z
  checked: Independent human verification at commit `f05247c`
  found: The session manager independently reran the full locked suite with the repository-local UV cache and observed 1,571 passed, 2 skipped, and 93 expected xfailed in 39.26 seconds; Ruff passed all three changed Python files; `git diff --check` passed; the fix commit contains exactly four paths; the debug session was the only untracked path.
  implication: The original regression is independently confirmed fixed end-to-end, so the session can be resolved and archived.

## Eliminated

- hypothesis: H3 — another forbidden import/call or unrelated capability widening is hidden behind the first exact-set failure.
  evidence: Complete AST enumeration reports no forbidden imports, and the Phase 3 check passes after changing only its in-memory expected `httpx` owner set.
  timestamp: 2026-07-27T15:10:00Z
- hypothesis: H2 — `state_branch.py` widens HTTP authority beyond the intended state-repository/state-ref capability.
  evidence: Complete source inspection shows only named Git object and fixed state-ref operations, no arbitrary/catalog/default-branch surface, and all 24 unchanged state restore/CAS/security tests pass.
  timestamp: 2026-07-27T15:11:00Z
- hypothesis: H4 — the state persistence capability should reuse the publication HTTP owner instead of introducing its own owner.
  evidence: Plan 05-06 explicitly separates the state repository/ref from catalog-root publication assumptions, requires a narrower client without PR/reviewer methods, and the implemented adapter has a distinct fixed-ref contract that cannot be represented by the catalog publisher without widening that publisher.
  timestamp: 2026-07-27T15:11:00Z

## Resolution

- root_cause: Historical Phase 1 and Phase 3 import-capability scanners pin the pre-Plan-05-06 set of `httpx` owners. The planned fixed state-branch adapter is therefore rejected by filename even though its reviewed capability is limited to one configured repository's Git objects and `refs/heads/skillscout-state`.
- fix: Added only `adapters/state_branch.py:httpx` to the two independent exact-owner policies; extended Phase 3 acceptance to pin the StateBranchClient public methods, exact state ref/endpoints, non-force update, and denial of catalog/default-branch tokens; added negative mutations for off-owner `httpx`, catalog PR paths, default branches, and public catalog methods; removed only the resolved 05-06 deferred item.
- verification: Commit `f05247c`; focused Phase 1/3 scanner, negative-mutation, and state-branch suite 89 passed; Ruff passed on all changed Python files; full locked suite 1,571 passed, 2 skipped, 93 expected xfailed in 38.08s; independent human rerun confirmed 1,571 passed, 2 skipped, 93 expected xfailed in 39.26s; `git diff --check` passed; confirmed fixed end-to-end.
- files_changed:
    - tests/test_phase1_gap_closure.py
    - tools/verify_phase3_acceptance.py
    - tests/test_phase3_acceptance_tool.py
    - .planning/phases/05-automated-discovery-operations/deferred-items.md
- investigation_cycles: 0
- fix_cycles: 0
