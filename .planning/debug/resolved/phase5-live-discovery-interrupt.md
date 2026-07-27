---
status: resolved
trigger: "Real Phase 5 discovery reports sanitized pipeline_interrupted after live state bootstrap in both hosted GitHub-token and local OAuth plus DeepSeek runs; durable state remains at the initial root."
created: 2026-07-28
updated: 2026-07-28T16:30:00+08:00
---

## Symptoms

- expected: A bounded live discovery run proceeds past bootstrap and persists a durable terminal outcome.
- actual: Both hosted run 30291358672 and a local OAuth plus DeepSeek run terminate as sanitized `pipeline_interrupted`.
- errors: Only the sanitized public outcome is available; secrets and raw external/provider content must not be inspected or logged.
- timeline: Reproduced after live state bootstrap; Gate B3 and the locked toolchain pass.
- reproduction: Live rerun is intentionally delegated to the parent; this investigation must reproduce offline with spies or fixtures.

## Current Focus

- known_pattern_candidate: resolved
- hypothesis: The live failure was a chain of restart-only integrity and terminal-accounting defects: restore mutated an orphan before byte verification; candidate-source failure escaped classification; fatal summaries omitted durable reservation counts; and crash-persisted fatal state accumulated or stopped later restoration.
- test: Hosted discovery workflow run `30314354246` at exact SHA `3f034dac9c6ecb074b69b5d34c694acb5c3617c8`.
- expecting: Discovery restores the exact remote state, classifies and persists restart outcomes without provider replay, reconciles fatal state coherently, and returns successfully.
- next_action: None for this debug session. The hosted discovery job succeeded in 53 seconds; archive as resolved.

reasoning_checkpoint:
  hypothesis: "The actual-wire failure is caused by startup orphan reconciliation changing the pipeline export during restore verification, not by GitHub transport, state-tree validation or provider behavior."
  confirming_evidence:
    - "The write- and provider-blocked actual-wire tracer reports public `pipeline_interrupted` with deepest ordinary exception `OperationsIntegrityError` at `operations_state.py:2734`."
    - "The sanitized projection comparison differs only in `pipeline_export_digest`; pipeline, operations and publication business projections plus the other two export digests are identical."
    - "Strict RED `test_three_store_restore_verifies_orphan_before_startup_reconciliation` at `e9ca792` reproduces the same line-2734 rejection."
    - "With reconciliation disabled only for the final restore integrity pass, focused, adjacent and full locked suites pass while normal later `SQLiteStateStore` opens retain `reconcile_orphans=True`."
  falsification_test: "The hypothesis is disproved if a hosted run at exact commit `299e29b` or later still fails at the unchanged parent with the same sanitized restore-integrity location and digest-difference shape."
  fix_rationale: "Restore must first prove that downloaded bytes exactly match the remote three-store bundle. Orphan recovery is a startup mutation and must occur only after that proof; making the internal restore-verification open non-mutating preserves byte binding without disabling normal recovery."
  blind_spots: "Hosted causal confirmation is still required. The separately measured state-transport request budget remains a production blocker even if this restore failure is confirmed fixed."

reasoning_checkpoint:
  hypothesis: "State throughput is exhausted because every sync verification downloads all tree bodies, while semantic confirmation additionally performs a full pre-restore and full post-restore."
  confirming_evidence:
    - "The valid no-body spy fails exactly at `_verify_sync` calling `get_blob`."
    - "One hundred incremental discovery syncs perform 5,450 blob GETs beyond the exact 1,100 metadata/write requests."
    - "One active semantic confirmation reads 35 bodies for a 12-file committed tree."
    - "Missing, extra, duplicate and wrong-mode tree mutations already fail before authority; wrong SHA is detected after earlier redundant body reads."
  falsification_test: "The hypothesis is disproved if exact path-to-local-Git-SHA verification plus one full semantic restore cannot reject every hostile tree mutation, preserve non-force CAS, or reduce the counters to zero sync-body reads and one restore-body read."
  fix_rationale: "The locally validated bundle binds every byte string to its Git blob SHA; create responses must return that SHA; the post-CAS ref→commit→tree Merkle chain can therefore verify the exact complete path-to-SHA map without downloading bodies. Semantic authority still requires one full restore, which revalidates Git SHA, sizes, SHA-256 root digests, canonical JSON and canaries."
  blind_spots: "Even the reduced approximately 4,260-request simplified envelope exceeds the Actions token budget, and actual reservation plus terminal orchestration can exceed 100 discovery transitions. Deterministic batching or another persistent transport remains required."

reasoning_checkpoint:
  hypothesis: "Restart loses durable reservation context in two places: it redundantly syncs the restored discovery reservation, then initializes the default factory's semantic reservation to `None`, producing a recovered terminal inconsistent with the restored semantic count."
  confirming_evidence:
    - "Live restart at dbf99a9 leaves HEAD exactly 984 with no idempotent reservation child commit, no semantic unknown transition, and no candidate terminal."
    - "The candidate loop always reserves then syncs before invoking Phase 2, even when the restored snapshot already contains the exact discovery reservation."
    - "The exact real-store 984 RED first fails at the redundant pre-factory sync; after skipping it, provider construction remains zero and `result_outcome_unknown` plus candidate-terminal sync execute."
    - "The unwrapped next failure is `run summary projection mismatch`: recovered terminal semantic count is 0 while restored operations state contains exactly one semantic reservation."
  falsification_test: "The hypothesis is disproved if exact restored reservation binding still replays the provider or if the recovered terminal/summary cannot pass operations projection verification."
  fix_rationale: "Both reservations came from the verified remote snapshot. Reusing them only after exact authority/repository/candidate/Phase-2 linkage checks preserves first-time barriers and supplies the terminal digest needed for coherent quarantine accounting."
  blind_spots: "The offline barrier is deterministic rather than GitHub-backed; live verification remains necessary to confirm request-budget behavior after recovery advances."

reasoning_checkpoint:
  hypothesis: "An ordinary exception from any unguarded close in the default Phase-2 factory replaces the factory's classified result or primary exception, so candidate-terminal persistence is never reached and remote state remains at Extractor `started`."
  confirming_evidence:
    - "Live typed state ends exactly at candidate-1 Extractor attempt 1 `started`, with no semantic result or candidate terminal."
    - "The factory converts runner `SafeFailure` into a typed terminal return inside `except`, but Python executes its four unguarded close calls before delivering that return."
    - "The strict injected-close test fails at every close position and directly shows the constructed terminal is lost."
  falsification_test: "The hypothesis is disproved if a close exception can occur in each position while the classified terminal/primary exception is preserved and all remaining resources are still closed."
  fix_rationale: "Cleanup has no authority to change the already-classified pipeline outcome. A private helper that attempts every close and suppresses cleanup-only exceptions removes the masking mechanism without changing provider, state, durability, or terminal classification behavior."
  blind_spots: "Sanitized live evidence cannot identify which concrete close raised; the fix is authorized as direct containment of the only reproduced ordinary escape after the handled factory outcome, not as proof of a specific SDK defect."

reasoning_checkpoint:
  hypothesis: "`SQLitePhaseTwoCandidateSource._resolve_all` rejects a verified completed filter-rejection chain because it admits only the all-success vector, so the default factory's empty-descriptor terminal branch is unreachable and ordinary `CandidateSourceUnavailable` escapes as `pipeline_interrupted`."
  confirming_evidence:
    - "cab3 durably contains discovery reservation ordinal 1 and zero semantic reservations or candidate terminals, exactly bounding the failure to the nonsemantic Phase 2 path after reservation."
    - "A real completed filter-rejection run verifies with outcomes `[accepted, rejected, skipped, skipped]`, then the strict RED raises `CandidateSourceUnavailable` at `phase2_state.py:336` during `resolve_all`."
    - "The default factory calls descriptor derivation outside its Phase 2 exception boundary and explicitly contains an `if not descriptors` branch that would otherwise persist `filter_rejected`."
  falsification_test: "The hypothesis is disproved if exact verified rejection vectors resolve to an empty tuple but the default factory still cannot build a filter-rejected terminal, or if the live rerun persists no candidate terminal for another ordinary exception."
  fix_rationale: "A read-only multi-projection query has a valid empty result for an exact verified completed rejection chain. Returning `()` only for the two deterministic Scout/Filter rejection vectors activates the existing terminal branch without admitting malformed, incomplete, or semantically ambiguous chains."
  blind_spots: "The sanitized live state does not disclose the ordinal-1 filter outcome. A parent-owned live rerun remains necessary; semantic `no_workflow`, refusal and schema outcomes are intentionally outside this minimal fix."

tdd_checkpoint:
  test_file: "tests/test_operations_state.py"
  test_name: "test_three_store_restore_verifies_orphan_before_startup_reconciliation"
  status: "green"
  failure_output: "Before the fix, final three-store restore verification raises `OperationsIntegrityError` at `operations_state.py:2734` because startup orphan reconciliation changes only `pipeline_export_digest` before byte-exact comparison."

## Evidence

- timestamp: 2026-07-28T00:00:00+08:00
  checked: Active debug session, project rules, Phase 5 plan index, common bug patterns
  found: Both live executions reached state bootstrap and then collapsed to sanitized pipeline_interrupted; the production controller catches broad exceptions at DiscoveryApplication.run.
  implication: The raw public error cannot distinguish restore/config/data-shape/semantic failures; offline stage isolation is required before any fix.

- timestamp: 2026-07-28T02:00:29+08:00
  checked: Debug knowledge base, prior live fixes, `_run_discover`, bootstrap composition, DiscoveryApplication and its integration tests
  found: Two prior live state failures were caused by synthetic fixtures omitting valid GitHub request-ID and folded-base64 wire forms. Discovery's real empty-run test stubs `_LateStateDurabilityBarrier.sync_discovery`, so it never exercises the post-Search HTTP CAS/reread path that the live runs reached.
  implication: A remaining state-client wire mismatch is a high-priority known-pattern hypothesis, but must be causally reproduced at the HTTP boundary before changing code.

- timestamp: 2026-07-28T02:00:29+08:00
  checked: Fault tree for sanitized interruption after verified bootstrap
  found: "OR branches: (H1) Search response contract mismatch; (H2) local restored three-store/projection mismatch; (H3) first state sync HTTP wire mismatch or CAS conflict; (H4) later Phase 2/semantic stage failure. Provider-independent repetition and unchanged initial root place H1-H3 before H4; existing integration stubs leave H3 substantially uncovered."
  implication: Test H3 first with a real adapter round trip, then H1/H2 if eliminated.

- timestamp: 2026-07-28T02:08:00+08:00
  checked: Complete GitHub Search adapter and response-contract tests versus the already-confirmed live GitHub request-ID form
  found: `StateBranchClient` was fixed to accept bounded colon-delimited uppercase hexadecimal GitHub IDs, but `GitHubReadClient._search_request_id` still uses `^[A-Za-z0-9._-]{1,128}$`; every successful Search fixture uses synthetic IDs such as `REQ-SEARCH-P1`, and no test supplies the confirmed live form.
  implication: The earliest post-bootstrap external effect has the same stale wire grammar as the previous confirmed state-client bug. A single-field recorded-response counterfactual can directly confirm or eliminate this candidate.

- timestamp: 2026-07-28T02:04:35+08:00
  checked: Strict RED Search adapter test with one response-header mutation
  found: The successful recorded page fails at `src/skillscout/adapters/github.py:556` when its request ID is the live colon-delimited form; the independent hostile matrix passes 11/11.
  implication: The single-token Search request-ID grammar is causally responsible for rejecting this valid wire form, and the safe fix surface is exactly one compiled pattern.

- timestamp: 2026-07-28T02:04:35+08:00
  checked: Focused post-fix request-ID counterfactual and hostile mutation matrix
  found: All 12 cases pass: the exact live colon-delimited Search ID is preserved in the typed page, while missing, empty, whitespace/control, malformed group, non-hex and oversized values remain `stage_permanent_failure`.
  implication: Changing only the request-ID grammar removes the reproduced failure and preserves the established fail-closed boundary.

- timestamp: 2026-07-28T02:07:41+08:00
  checked: Adjacent locked Search, state-branch, discovery application and discovery security suites
  found: 128 tests passed.
  implication: The fix preserves Search projections, state durability and discovery orchestration/security contracts.

- timestamp: 2026-07-28T02:07:41+08:00
  checked: Complete locked repository pytest suite
  found: 1785 tests passed and 2 tests skipped in 40.89 seconds.
  implication: No offline regression is detected across the repository.

- timestamp: 2026-07-28T02:07:41+08:00
  checked: Configured Ruff, git diff whitespace and scoped diff review
  found: Ruff reports all checks passed; `git diff --check` passes; tracked changes are limited to the Search adapter and its request-ID tests, with the active debug file untracked.
  implication: The implementation is minimal, formatted and ready for the parent-owned live verification.

- timestamp: 2026-07-28T02:20:00+08:00
  checked: Hosted run 30292555545 at exact source SHA 13b271dc29f7e5c2de4395c5ee9ae47b21bad2f9
  found: Toolchain and Gate B3 passed, but discover returned sanitized `pipeline_interrupted` in approximately five seconds, the protected job was skipped, and `skillscout-state` HEAD remained at the initial root `449aed6599f3487e34a34751a893be2d984fa95c`.
  implication: The Search request-ID defect was real but not the complete live root cause. The failure still occurs before the first durable state sync; resume at the next pre-persistence boundary and do not archive the session.

- timestamp: 2026-07-28T02:18:00+08:00
  checked: Fresh real owner stores, typed operations run/page/candidate, exact bundle assembly and real StateBranchStore over an in-memory parent-bound remote
  found: The first checkpoint verified successfully, used the expected prior head, performed a non-force ref update, and produced an 11-file exact bundle.
  implication: Fresh local owner export, bundle construction and StateBranchStore logic are not sufficient to reproduce the live interruption; restored-state reuse and production page shape remain.

- timestamp: 2026-07-28T02:21:00+08:00
  checked: Real GitHubReadClient over a live-form request ID and production-shaped three-item Search page, real DiscoveryApplication and OperationsStateStore
  found: The typed page and all three candidate observations were durably recorded; only an intentionally injected barrier exception became `pipeline_interrupted`.
  implication: Production Search projection and multi-item page persistence reach the first durability barrier correctly offline; exact restored-state reuse or live state mutation remains.

- timestamp: 2026-07-28T02:25:00+08:00
  checked: Bundle construction and restore ordering code
  found: `_bundle_from_exports` stores root, then objects, then databases in owner order; StateBranchStore.restore stores root then all remaining paths in lexical order. `restore_three_store_bundle` rejects when `prospective != bundle`, so dataclass tuple order is treated as state identity even though other barrier code already compares root plus `content_by_path`.
  implication: This predicts the observed plain exception before Search, unchanged remote head, short runtime, and absence from tests that pass an assembler-originated bundle directly.

- timestamp: 2026-07-28T02:26:00+08:00
  checked: Exact assemble→StateBranchStore sync/restore→three-store restore reproduction with real empty owner stores and an in-memory remote
  found: The assembled and restored bundles have equal roots and identical path-to-bytes maps but different file tuple order; `restore_three_store_bundle` raises `OperationsIntegrityError("bundle projection equality failed")`.
  implication: The order-sensitive comparison is the directly reproduced pre-Search root cause; the regression test can isolate it without network access.

- timestamp: 2026-07-28T02:28:00+08:00
  checked: Strict RED regression test with only StateBranchStore-style lexical file ordering
  found: The bundle root and exact path-to-bytes map remain equal, but `restore_three_store_bundle` fails at the direct dataclass comparison with `OperationsIntegrityError("bundle projection equality failed")`.
  implication: Tuple order alone is sufficient to reproduce the production bootstrap interruption, and the proposed equality change has a precise falsification test.

- timestamp: 2026-07-28T02:30:00+08:00
  checked: Minimal content-aware comparison against the RED regression and existing three-case mismatch matrix
  found: The StateBranchStore-order regression passes, and swapped database bytes, damaged object bytes and missing database files remain rejected; 4 tests passed.
  implication: The fix removes only the non-semantic ordering mismatch while preserving fail-closed bundle integrity.

- timestamp: 2026-07-28T02:32:00+08:00
  checked: Adjacent locked operations-state, state-branch, discovery-application and discovery-security suites
  found: All 122 tests passed.
  implication: Restored-state durability, discovery orchestration and security behavior remain intact around the fix.

- timestamp: 2026-07-28T02:35:00+08:00
  checked: Complete locked repository pytest suite
  found: 1786 tests passed and 2 tests skipped in 43.60 seconds.
  implication: No offline regression is detected across the repository.

- timestamp: 2026-07-28T02:35:00+08:00
  checked: Untracked `state/` directory after offline reproduction
  found: It contained only the experiment-generated operations SQLite database and zero-byte lock, both timestamped during the reproduction; only those files and empty directories were removed.
  implication: No pre-existing or user-owned state artifact was deleted, and commit scope remains clean.

- timestamp: 2026-07-28T02:37:00+08:00
  checked: Configured Ruff, git diff whitespace and exact scoped diff review
  found: Ruff and `git diff --check` pass; tracked changes are limited to the four-condition content-aware comparison and one 46-line regression test, while the active debug session remains untracked.
  implication: The fix is minimal, formatted and ready for an atomic code-and-test commit.

- timestamp: 2026-07-28T02:39:00+08:00
  checked: Atomic code-and-test commit and post-commit worktree scope
  found: Commit `c888c38e96ad9c790954a94d0bedf3be2c080203` contains exactly `operations_state.py` and `test_operations_state.py`; only the active debug session remains untracked.
  implication: The exact implementation is ready for the parent-owned hosted rerun without archiving or conflating planning state.

- timestamp: 2026-07-28T03:00:00+08:00
  checked: Hosted run 30294010488 at exact source SHA `c888c38e96ad9c790954a94d0bedf3be2c080203`
  found: After installation the run lasted approximately 20 seconds and terminal output changed from `pipeline_interrupted` to sanitized `stage_permanent_failure`; protected publication was skipped and `skillscout-state` HEAD remained at initial root `449aed6599f3487e34a34751a893be2d984fa95c`.
  implication: The restored-bundle ordering fix is live-confirmed. The next failure is an intentional fail-closed stage boundary before first state persistence, most likely the production Search response contract.

- timestamp: 2026-07-28T03:08:00+08:00
  checked: Complete Search response admission path, discovery checkpoint placement and candidate field grammars
  found: A Search `SafeFailure` propagates unchanged and occurs before the first page checkpoint. `_RawSearchRepo.default_branch` accepts a bounded string up to 200 characters, but `SearchRepositoryObservationV1.default_branch` reuses `_GitHubSegment` (max 100, no slash); the same adapter's ref path validator accepts slash-bearing refs.
  implication: One valid slash-bearing default branch can explain the exact live `stage_permanent_failure` with unchanged state HEAD; test this single field before considering broader Link/header changes.

- timestamp: 2026-07-28T03:12:00+08:00
  checked: Strict one-field RED Search counterfactual and six-case malformed/oversized default-branch matrix
  found: Replacing only `main` with `release/v1` raises `SafeFailure(stage_permanent_failure)` at strict repository projection; all six hostile variants remain rejected. Result was 1 failed and 6 passed.
  implication: The adapter has a directly reproduced valid-public-shape incompatibility at exactly the pre-persistence boundary, with a narrowly falsifiable schema fix.

- timestamp: 2026-07-28T03:15:00+08:00
  checked: Dedicated bounded ref grammar against the strict RED and hostile matrix
  found: `release/v1` is preserved in the typed Search projection, while leading slash, whitespace, backslash, colon, caret and over-200-character variants remain permanent failures; all 7 tests passed.
  implication: The minimal schema correction removes only the repository-name/ref type mismatch and retains the intended fail-closed boundary.

- timestamp: 2026-07-28T03:17:00+08:00
  checked: Adjacent locked Search, GitHub adapter, discovery-domain, discovery-application and discovery-security suites
  found: All 170 tests passed.
  implication: Query/page authority, domain digests, orchestration and security behavior remain intact around the ref schema change.

- timestamp: 2026-07-28T03:20:00+08:00
  checked: Complete locked repository pytest suite
  found: 1793 tests passed and 2 tests skipped in 43.04 seconds.
  implication: No offline regression is detected across the repository.

- timestamp: 2026-07-28T03:22:00+08:00
  checked: Configured Ruff, whitespace validation and exact scoped diff/worktree review
  found: Ruff and `git diff --check` pass; tracked changes are limited to one bounded ref type, one field assignment, the single-field RED/GREEN case and six hostile cases; only the active debug session is untracked.
  implication: The correction is minimal, fail-closed and ready for an atomic code-and-test commit.

- timestamp: 2026-07-28T03:24:00+08:00
  checked: Atomic code-and-test commit and post-commit worktree scope
  found: Commit `65e50078e95f41d0c825fd72418191bccfc9d931` contains exactly `src/skillscout/domain/discovery.py` and `tests/test_github_search.py`; only the active debug session remains untracked.
  implication: The exact correction is ready for parent-owned hosted verification without archiving or broadening authority.

- timestamp: 2026-07-28T03:40:00+08:00
  checked: Hosted run 30294877997 at exact source SHA `65e50078e95f41d0c825fd72418191bccfc9d931`
  found: The run returned sanitized `pipeline_interrupted` after approximately 13 seconds, protected publication was skipped, and `skillscout-state` advanced from initial `449aed6599f3487e34a34751a893be2d984fa95c` to `91c02447740d14023dc466184a8830f02dfe2306`. The new commit has the initial commit as parent, a sanitized root message beginning `sha256:a636c418`, and a tree containing three SQLite databases, 31 content-addressed JSON objects, and `root.json`.
  implication: The slash-bearing default-ref fix and first durable Search sync are live-confirmed with a non-empty candidate set. The next failure is strictly after that checkpoint; exact typed canonical metadata can identify the last completed deterministic boundary without raw content.

- timestamp: 2026-07-28T03:46:00+08:00
  checked: Post-page discovery sync control flow against the bounded live facts
  found: `_LateStateDurabilityBarrier.sync_discovery` calls `StateBranchStore.sync` first, then rereads the new commit and compares `reread.bundle != bundle` directly. Remote restore emits root plus lexically sorted files while assembly emits root, objects, then owner-ordered databases; the subsequent order-only mismatch raises a plain ValueError after the ref has advanced.
  implication: This exactly predicts one new child commit, advanced HEAD and sanitized `pipeline_interrupted`; no raw remote metadata is required to isolate the post-checkpoint failure.

- timestamp: 2026-07-28T03:50:00+08:00
  checked: Strict real-barrier RED with real owner stores, successful fake sync and order-only remote reread
  found: Sync returned a new commit/root and the reread had the same root and exact path-to-bytes map, but lexical file order alone caused `ValueError("discovery state synchronization rejected")` at `bootstrap.py:363`.
  implication: The post-first-checkpoint root cause is directly reproduced and the fix surface is the single reread equality predicate.

- timestamp: 2026-07-28T03:54:00+08:00
  checked: Content-aware late-barrier reread comparison against order-only success and six fail-closed mutations
  found: The barrier returns the verified sync for equal root/count/path-to-bytes content in lexical order, while wrong status, wrong head, missing bundle, changed root, missing file and changed bytes all remain rejected; all 7 tests passed.
  implication: The fix removes only the non-semantic ordering mismatch and preserves complete post-commit reread integrity.

- timestamp: 2026-07-28T03:56:00+08:00
  checked: Adjacent locked discovery-application, discovery-security, state-branch and operations-state suites
  found: All 129 tests passed.
  implication: State synchronization, restore integrity and discovery authority remain intact around the late-barrier change.

- timestamp: 2026-07-28T03:59:00+08:00
  checked: Complete locked repository pytest suite
  found: 1800 tests passed and 2 tests skipped in 42.68 seconds.
  implication: No offline regression is detected across the repository.

- timestamp: 2026-07-28T04:01:00+08:00
  checked: Configured Ruff, whitespace validation and exact scoped diff/worktree review
  found: Ruff and `git diff --check` pass; tracked changes are limited to the four content-aware reread predicates and the seven-case real-barrier regression matrix; only the active debug session is untracked.
  implication: The post-checkpoint fix is minimal, fail-closed and ready for an atomic code-and-test commit.

- timestamp: 2026-07-28T04:03:00+08:00
  checked: Atomic code-and-test commit and post-commit worktree scope
  found: Commit `0a66c5466a7c2b8d78d593abbcdfe3a041fc4e31` contains exactly `src/skillscout/bootstrap.py` and `tests/test_discovery_application.py`; only the active debug session remains untracked.
  implication: The exact post-first-checkpoint correction is ready for parent-owned hosted verification without archiving the session.

- timestamp: 2026-07-28T04:20:00+08:00
  checked: Hosted run 30295585425 at exact source SHA `0a66c5466a7c2b8d78d593abbcdfe3a041fc4e31`
  found: The run returned sanitized `pipeline_interrupted` after approximately 62 seconds and advanced state twice: `91c02447740d14023dc466184a8830f02dfe2306` to `ded8d36c...` at 18:51:18Z with root prefix `1c6c3b`, then to `b545f980...` at 18:51:55Z with root prefix `4795a686`; protected publication was skipped. Canonical tree blob counts were 35 → 61 → 87, exactly 26 new files per successful checkpoint.
  implication: The late post-write reread fix is live-confirmed. Each new checkpoint strongly matches one page manifest plus 25 candidate observations; the next failure occurs while continuing round-robin queries/pages or enforcing Link, duplicate reservation, or rate-limit boundaries after three successful pages.

- timestamp: 2026-07-28T04:40:00+08:00
  checked: Bounded live q1/p3 aggregate probe using one Search request and typed canary booleans only
  found: The adapter outcome was `ok`, `page_canary` was false, and every item ordinal 1 through 25 had `canary=false`; no identifier, name, content, request ID, token or exception was emitted.
  implication: Current q1/p3 Search projection and the canonical state canary detector both pass. The pre-sync canary hypothesis is falsified; investigate non-canary state-bundle validation or resume-specific query scheduling next.

- timestamp: 2026-07-28T04:25:00+08:00
  checked: Sanitized canonical root, page manifests and candidate disposition aggregate at current state
  found: The durable prefix is exactly q1/p1 with 25 first-seen observations, q1/p2 with 24 first-seen plus 1 duplicate, and q2/p1 with 25 first-seen observations; there are 75 observations, 74 selected candidates, zero discovery or semantic reservations, zero candidate/workflow terminals, and zero run summaries.
  implication: Resume next attempts q1/p3. Even 25 new items can raise selected count only to 99, so the 100-candidate budget cannot terminate or fail on that page; an exact typed replay can isolate candidate/operations logic without reading source content.

- timestamp: 2026-07-28T04:32:00+08:00
  checked: Exact offline real-store resume replay through q1/p3
  found: The real OperationsStateStore accepted q1/p1 with 25 first-seen, q1/p2 with 24 first-seen plus 1 duplicate, and q2/p1 with 25 first-seen; the real DiscoveryApplication then restored that prefix, persisted 25 new q1/p3 observations, produced 99 total selected candidates, and invoked the durability barrier once before the intentionally injected next-page stop.
  implication: The exact persisted prefix does not cause a candidate deduplication, provenance, ordinal or SQLite transaction exception. The live failure is now bounded to q1/p3 Search transformation or state-bundle construction/validation before the fourth ref update.

- timestamp: 2026-07-28T04:38:00+08:00
  checked: Complete Search success/error path and pre-sync state bundle validation
  found: JSON/model, request-ID, rate-limit, Link URL/query and repository-field validation all collapse to SafeFailure and would surface as stage_permanent or stage_transient, not pipeline_interrupted. StateBranchStore instead scans every canonical object and database for any case-insensitive occurrence of `github_pat_`, `ghp_`, private-key banners, bearer headers or the state canary, raising plain StateIntegrityFailure before remote writes.
  implication: A legitimate public repository name/default ref containing a canary prefix is a specific single-point mechanism matching successful Search, local page recording, absent fourth commit and sanitized pipeline_interrupted.

- timestamp: 2026-07-28T04:38:00+08:00
  checked: Bounded live diagnostic design
  found: A syntax-checked temporary probe performs exactly one q1/p3 Search request and emits only adapter outcome, page canary boolean, and item ordinal/canary booleans; it never emits identifiers, names, content, request IDs, credentials or exception text and performs no writes.
  implication: The parent can confirm or eliminate the canary hypothesis with one bounded sanitized aggregate and no expansion of content authority.

- timestamp: 2026-07-28T04:42:00+08:00
  checked: One-field offline public-metadata canary counterfactual
  found: With all other typed facts equal, a normal repository name assembled successfully while a valid bounded `ghp_`-prefixed repository name caused StateIntegrityFailure before sync.
  implication: The proposed mechanism is real, but the sanitized live probe found no canary on q1/p3, so it does not explain the current live interruption.

- timestamp: 2026-07-28T04:48:00+08:00
  checked: Exact 100-observation offline three-store bundle assembly
  found: After correcting a probe-only configuration setup error, real pipeline, operations and publication stores assembled q1/p1, q1/p2, q2/p1 and q1/p3 into a verified bundle with 100 observations, 99 selected candidates, 109 canonical objects and 113 total files.
  implication: Local owner export, object canonicalization, database serialization, root construction, canary scanning and complete bundle validation all pass at the exact fourth-checkpoint size. The remaining boundary begins inside remote StateBranchStore sync.

- timestamp: 2026-07-28T04:52:00+08:00
  checked: Complete StateBranchStore sync with the verified 113-file bundle over a parent-bound in-memory remote
  found: Sync completed with verified status after 113 blob creations plus tree, commit and non-force ref update, for 116 content-generating writes total.
  implication: Deterministic sync/CAS/reread logic accepts the fourth-checkpoint bundle, but its live request strategy generates more content writes than GitHub's general per-minute secondary content-creation boundary.

- timestamp: 2026-07-28T04:55:00+08:00
  checked: GitHub official REST secondary-rate-limit and best-practice documentation
  found: GitHub documents a general limit of no more than 80 content-generating requests per minute, notes lower undisclosed endpoint limits may apply, and recommends at least a one-second pause between mutative requests. The current fourth checkpoint performs 116 mutative writes and prior checkpoints retransmit all unchanged blobs.
  implication: The exact live 35→61→87 success then pre-ref 113-file failure aligns with a documented remote content-generation boundary. Reusing unchanged parent-tree blob SHAs reduces the fourth checkpoint to approximately 30 mutative writes without adding retry authority or weakening verification.

- timestamp: 2026-07-28T05:02:00+08:00
  checked: Strict 87-file parent to 113-file child content-creation-limit RED
  found: Although the child shares all 83 parent objects and all three database bytes, current StateBranchStore called create_blob for every child file and raised the synthetic content limit exactly on call 81.
  implication: Unconditional retransmission is causally sufficient to reproduce the pre-ref failure at the exact live boundary; same-path/same-SHA parent reuse is the minimal counterfactual.

- timestamp: 2026-07-28T05:08:00+08:00
  checked: Minimal validated parent-tree blob reuse against the strict RED and adjacent CAS/security checks
  found: The child sync now creates exactly 27 blobs, constructs and rereads the complete 113-file tree, performs a non-force update, and passes bootstrap, changed-head and secret-before-write checks; 5 focused tests passed.
  implication: The fix removes 86 redundant content-generating requests from the controlled fourth checkpoint without weakening full-state verification or ref authority.

- timestamp: 2026-07-28T05:08:00+08:00
  checked: Complete StateBranch suite after parent-tree reuse
  found: All 55 tests passed.
  implication: Existing client wire validation, restore integrity, mutation rejection, conflict handling and exact reread behavior remain intact.

- timestamp: 2026-07-28T05:12:00+08:00
  checked: Final consolidated StateBranch fixture and malformed-parent regression
  found: All 56 StateBranch tests passed; a parent tree with an unowned path is rejected as StateBranchConflict before any blob write.
  implication: Blob reuse grants no authority to malformed parent trees and remains fully covered at the exact 87-to-113-file boundary.

- timestamp: 2026-07-28T05:14:00+08:00
  checked: Adjacent locked state, operations, discovery application and discovery security suites
  found: All 131 tests passed.
  implication: Discovery checkpointing, restored operations state and security boundaries remain intact around the StateBranch optimization.

- timestamp: 2026-07-28T05:14:00+08:00
  checked: Complete locked repository pytest suite after final fixture consolidation
  found: 1802 tests passed and 2 tests skipped in 42.69 seconds.
  implication: No offline regression is detected across the repository.

- timestamp: 2026-07-28T05:15:00+08:00
  checked: Configured Ruff, whitespace check, scoped diff and worktree review
  found: Ruff and git diff --check pass; tracked changes are limited to StateBranch parent-blob reuse and its exact limit/security regressions, while the active debug file remains untracked.
  implication: The implementation is minimal, fail-closed and ready for an atomic code-and-test commit followed by parent-owned live verification.

- timestamp: 2026-07-28T05:18:00+08:00
  checked: Atomic implementation-and-test commit and post-commit worktree scope
  found: Commit `e1c643e` contains exactly `src/skillscout/adapters/state_branch.py` and `tests/test_state_branch.py`; only the active debug session remains untracked.
  implication: The verified fix is ready for a parent-owned hosted rerun without archiving the session or conflating planning state.

- timestamp: 2026-07-28T05:35:00+08:00
  checked: Hosted run 30298360131 at exact source SHA `e1c643e4806a86b29a0a04b8676b4d26b4ce0e3c`
  found: The run returned sanitized `pipeline_interrupted` after approximately 25 seconds and advanced state once from `b545f98...` to `d1ac0ec...` at 19:28:43Z with root prefix `110bcab`; no second commit was created and protected publication was skipped.
  implication: Incremental parent-blob reuse is live-confirmed and q1/p3 now persists successfully. The next failure is after a durable 99-selected prefix, making the 100-selected budget boundary the highest-priority exact replay.

- timestamp: 2026-07-28T05:50:00+08:00
  checked: Fully decoded d1ac typed aggregate and exact 95-to-100 real application/store replay
  found: d1ac contains 100 observations and 95 selected candidates: q1/p1 25 first-seen; q1/p2 24 first-seen plus 1 duplicate; q1/p3 21 first-seen plus 4 duplicates; q2/p1 25 first-seen. The generic next-page replay persisted exactly 5 first-seen plus 20 budget-excluded observations, stopped at 100 selected, and reached the durability barrier.
  implication: Budget-cap disposition, ordinal and OperationsStateStore logic are correct. In the same live run, the next active coordinate after q1/p3 is q2/p2, so investigate that exact page's wire/content and pre-sync bundle.

- timestamp: 2026-07-28T05:55:00+08:00
  checked: Bounded live q2/p2 aggregate probe with one Search request
  found: Adapter outcome was `ok`, page_canary was false, and item ordinals 1 through 25 all had `canary=false`; no raw metadata or secret material was emitted.
  implication: The exact q2/p2 adapter call and canary scan pass. The live interruption lies after typed Search projection, within exact-page persistence/bundle/sync behavior at the 100-selected transition.

- timestamp: 2026-07-28T05:45:00+08:00
  checked: Fully decoded bounded d1ac canonical operations aggregates
  found: d1ac contains one run, four Search pages and 100 candidate observations. Pages are q1/p1, q1/p2, q1/p3 and q2/p1, each with 25 items; q1/p3 points to page 4 and q2/p1 points to page 2. Dispositions are 95 first_seen, 5 duplicate and 0 budget_excluded: q1/p1 25 first, q1/p2 24 first plus 1 duplicate, q1/p3 21 first plus 4 duplicates, and q2/p1 25 first.
  implication: The previous 99-selected assumption was wrong. Resume attempts q1/p4 from exactly 95 selected candidates, so a 25-new-item page produces five first_seen followed by twenty budget_excluded observations and is the precise boundary to replay.

- timestamp: 2026-07-28T05:52:00+08:00
  checked: Exact 95-selected prefix to q1/p4 real DiscoveryApplication and OperationsStateStore replay
  found: After correcting a fixture-only initial-root mismatch, q1/p4 recorded 25 observations as exactly five first_seen and twenty budget_excluded, selected count stopped at 100, and the durability barrier was reached once.
  implication: Candidate-budget enforcement, budget-excluded provenance, discovery ordinal 100, page transaction and exact-stop control flow are correct. The live pre-commit failure depends on the actual q1/p4 response or canonical content, not the deterministic budget transition.

- timestamp: 2026-07-28T05:56:00+08:00
  checked: Discovery loop scheduling after the live q1/p3 checkpoint
  found: The active-page loop snapshots sorted query ordinals before processing. After q1/p3 persists, the same run continues to q2/p2; it does not restart at q1/p4. A fresh later resume would try q1/p4 first.
  implication: The live no-second-commit boundary is q2/p2. The earlier q1/p4 budget replay was coordinate-independent but not the exact same-run call.

- timestamp: 2026-07-28T05:57:00+08:00
  checked: Bounded live q1/p4 adapter probe
  found: The q1/p4 adapter returned sanitized stage_permanent_failure.
  implication: This is unrelated to run 30298360131's same-run q2/p2 failure, but it identifies a future max-page Search Link/wire boundary that must be closed before a fresh resume can complete.

- timestamp: 2026-07-28T05:58:00+08:00
  checked: Corrected same-run q1/p3 then q2/p2 real application/store budget replay
  found: Starting from the exact 74-selected prefix, q1/p3 reached 95 selected and synchronized, then q2/p2 persisted five first_seen plus twenty budget_excluded observations, stopped at exactly 100 selected, and reached the second durability barrier.
  implication: Query-loop scheduling plus the actual 95-to-100 q2/p2 budget transition is correct with typed synthetic repositories. Only q2/p2 live response/content remains.

- timestamp: 2026-07-28T06:02:00+08:00
  checked: Bounded live q2/p2 adapter and canary aggregate
  found: The adapter outcome was ok, page_canary was false, and all item ordinals 1 through 25 had canary=false.
  implication: The exact live next-page Search wire and canonical-content canary boundary are eliminated. Test operations export/rebuild and the full 139-file sync after budget exclusion.

- timestamp: 2026-07-28T06:10:00+08:00
  checked: Exact same-run q1/p3 then q2/p2 export through real three-store bundle assembly
  found: The real OperationsStateStore persisted 125 observations as 100 first_seen, 5 duplicate and 20 budget_excluded facts; assembly produced a valid 135-object, 139-file bundle.
  implication: Budget-excluded export, canonicalization, owner-database serialization and root validation all pass at the exact live boundary.

- timestamp: 2026-07-28T06:11:00+08:00
  checked: Exact 109-object parent to 135-object child StateBranchStore sync with parent blob reuse
  found: The complete 139-file child synchronized and reread successfully while creating only 27 new blobs.
  implication: Deterministic StateBranch mutation, CAS and byte-verification logic passes the exact post-q2/p2 boundary.

- timestamp: 2026-07-28T06:14:00+08:00
  checked: Remote request count across restore, q1/p3 sync verification and late durability barrier
  found: Restoring the 87-file prefix costs approximately 90 GETs. The 113-file q1/p3 sync costs 3 parent reads, about 31 mutations and 116 verification GETs. The barrier then immediately performs another 116-GET restore of the identical state, for approximately 356 REST requests before q1/p3 returns.
  implication: The second restore is redundant with `_verify_sync` and materially pressures the shared hosted token budget. The minimal safe boundary is to retain the complete `_verify_sync` reread and accept only its strictly bound verified receipt.

- timestamp: 2026-07-28T06:18:00+08:00
  checked: Strict valid-receipt no-second-restore RED
  found: A real `StateSyncObservation` bound to the observed head and assembled root failed at `bootstrap.py:357` because the barrier called `store.restore()`; the spy raised exactly `verified sync receipt must not trigger a second restore`.
  implication: The redundant second read is directly reproduced as the sole failing action, so the minimal fix can be isolated to receipt validation inside `_LateStateDurabilityBarrier`.

- timestamp: 2026-07-28T06:22:00+08:00
  checked: Strict receipt matrix after minimal barrier change
  found: The correctly bound concrete receipt returns without invoking restore, while wrong type, status, previous head, root digest, commit SHA and tree SHA are all rejected; all 7 cases passed.
  implication: The barrier now accepts only the receipt produced by complete `_verify_sync` semantics and removes exactly one redundant full remote reread.

- timestamp: 2026-07-28T06:24:00+08:00
  checked: Adjacent discovery application, StateBranch, operations state and discovery security suites
  found: All 132 tests passed.
  implication: Complete StateBranch reread/CAS/security behavior and the exact 139-file budget-boundary regressions remain green around the barrier change.

- timestamp: 2026-07-28T06:27:00+08:00
  checked: Complete locked repository pytest suite
  found: 1803 tests passed and 2 tests skipped in 42.90 seconds.
  implication: No offline regression is detected across the repository.

- timestamp: 2026-07-28T06:30:00+08:00
  checked: Configured Ruff, whitespace validation and exact scoped diff/worktree review
  found: Ruff and `git diff --check` pass. Tracked changes are limited to the barrier receipt check, the strict no-second-restore matrix, the exact q1/p3-to-q2/p2 139-file replay, and scaling the parent-reuse regression to 109-to-135 objects; the active debug session remains untracked.
  implication: The change is scoped, fail-closed and ready for an atomic code-and-test commit.

- timestamp: 2026-07-28T06:33:00+08:00
  checked: Atomic implementation-and-regression commit and post-commit worktree scope
  found: Commit `f2b5ef6` contains exactly `src/skillscout/bootstrap.py`, `tests/test_discovery_application.py` and `tests/test_state_branch.py`; only the active debug session remains untracked.
  implication: The optimized single-verification boundary is ready for parent-owned hosted verification without archiving the session.

- timestamp: 2026-07-28T06:50:00+08:00
  checked: Hosted run 30300437045 at exact source SHA `f2b5ef6dc47cfb6f284ab67d535ff690b87f9225`
  found: The run returned sanitized `stage_permanent_failure` after approximately 26 seconds, state remained at `d1ac0ec...`, and protected publication was skipped. Restart ordering begins at q1/p4; the prior bounded q1/p4 probe independently returned the same `stage_permanent_failure`.
  implication: The duplicate-verification optimization is live-confirmed by the changed terminal boundary. The exact current failure is q1/p4 adapter admission, with a valid provider page-5 continuation crossing the local max-page-4 policy as the strongest single-variable cause.

- timestamp: 2026-07-28T07:00:00+08:00
  checked: Strict page-4 valid-next-page-5 Link RED with three hostile controls
  found: The exact same-authority/path/query `rel="next"` page-5 URL raised `stage_permanent_failure` at `github.py:648`, while hostile authority, malformed query and duplicate-next mutations were all rejected as expected.
  implication: The local max-page policy predicate alone rejects the valid provider continuation; terminalization can safely occur after, and only after, the existing exact Link validation.

- timestamp: 2026-07-28T07:04:00+08:00
  checked: Post-validation local terminalization against the exact four-case matrix
  found: The valid page-5 continuation now produces `next_page=None`; hostile authority, malformed query and duplicate-next cases remain permanent failures; all four cases passed.
  implication: The minimal change separates trusted provider pagination facts from local acquisition policy without broadening Link authority.

- timestamp: 2026-07-28T07:06:00+08:00
  checked: Adjacent GitHub Search, discovery domain, discovery application and discovery security suites
  found: All 155 tests passed.
  implication: Existing pagination, schema, orchestration and hostile-input contracts remain intact around local max-page terminalization.

- timestamp: 2026-07-28T07:09:00+08:00
  checked: Complete locked repository pytest suite
  found: 1807 tests passed and 2 tests skipped in 43.72 seconds.
  implication: No offline regression is detected across the repository.

- timestamp: 2026-07-28T07:12:00+08:00
  checked: Configured Ruff, whitespace validation and exact scoped diff/worktree review
  found: Ruff and `git diff --check` pass; tracked changes are limited to seven adapter lines and one 51-line valid/hostile Link boundary matrix, while the active debug session remains untracked.
  implication: The fix is minimal, fail-closed and ready for an atomic implementation-and-test commit.

- timestamp: 2026-07-28T07:15:00+08:00
  checked: Atomic max-page implementation-and-test commit and post-commit worktree scope
  found: Commit `aa28a7a` contains exactly `src/skillscout/adapters/github.py` and `tests/test_github_search.py`; only the active debug session remains untracked.
  implication: The exact provider-pagination/local-policy correction is ready for parent-owned hosted verification without archiving the session.

- timestamp: 2026-07-28T07:35:00+08:00
  checked: Hosted run 30301002850 at exact source SHA `aa28a7acf7c344bfebb8b8846e87932835547732`
  found: The run returned sanitized `pipeline_interrupted` after approximately 47 seconds and advanced state twice: `d1ac...` to `56a8466...` at 20:04:57 with root prefix `c7affb`, then to `cab3afa...` at 20:05:17 with root prefix `bc83af`; protected publication was skipped.
  implication: Max-page terminalization is live-confirmed. The first commit is consistent with q1/p4 completion and the second with discovery reservation ordinal 1; the next failure is inside Phase 2 composition/admission before its next durable transition.

- timestamp: 2026-07-28T07:42:00+08:00
  checked: cab3 typed aggregate counts/kinds and added operations row
  found: cab3 has 136 objects and three databases. Its projection contains 125 candidates, five Search pages, one discovery reservation, zero semantic reservations, zero candidate/workflow terminals and zero run summaries. The durable added row is `discovery-reservation-v1` ordinal 1.
  implication: The failure occurs after the first discovery reservation is remotely durable and before semantic reservation or terminal persistence.

- timestamp: 2026-07-28T07:45:00+08:00
  checked: Ordinal-1 candidate derived subject length and current validator outcome
  found: The typed candidate has full-name length 10, derived subject-ID length 15, and the current RepositorySubject validator accepts it; no identifier value was emitted.
  implication: The legal-long-name/max-128 SubjectId mismatch is real in general but does not cause this live ordinal-1 failure. Continue through factory/runtime composition.

- timestamp: 2026-07-28T08:22:00+08:00
  checked: Default Phase 2 factory, candidate-source admission and real completed filter-rejection pipeline
  found: The real run completes and verifies with `[accepted, rejected, skipped, skipped]`, but `SQLitePhaseTwoCandidateSource.resolve_all` raises ordinary `CandidateSourceUnavailable` before the factory can enter its explicit empty-descriptor `filter_rejected` branch.
  implication: The first deterministic failing post-run marker is `descriptors_derived`; the exception escapes the factory and exactly explains `pipeline_interrupted` after discovery reservation with no semantic reservation or candidate terminal.

- timestamp: 2026-07-28T08:28:00+08:00
  checked: Minimal exact rejection-vector admission and focused candidate-source regressions
  found: Both verified Scout- and Filter-rejection chains now resolve to an empty multi-projection tuple; all 55 focused rejection and candidate-source tests pass, including existing non-success descriptor fail-closed cases.
  implication: The existing default-factory empty-descriptor terminal branch is reachable without broadening single-descriptor or malformed-chain authority.

- timestamp: 2026-07-28T08:36:00+08:00
  checked: Adjacent locked suites, complete locked suite, Ruff lint, formatter baseline and scoped diff
  found: Adjacent Phase 2/discovery/security tests passed 397/397; the complete suite passed 1808 with 2 skipped; Ruff lint and `git diff --check` pass. Ruff format check reports an existing repository-wide 86-file baseline, including untouched files, so no broad formatter rewrite was applied.
  implication: The targeted fix has no detected regression and the exact three-file code/test diff is ready for an atomic commit.

- timestamp: 2026-07-28T08:40:00+08:00
  checked: Atomic implementation-and-regression commit and post-commit scope
  found: Commit `848d46c` contains exactly `phase2_state.py`, `test_candidate_source.py` and `test_scout_filter.py`; only the active debug session remains untracked.
  implication: The confirmed fix is ready for parent-owned hosted verification without archiving the session.

- timestamp: 2026-07-28T09:00:00+08:00
  checked: Hosted run 30303195568 at exact source SHA `848d46cf17ae0459d6e00fe9497a85318465d779`
  found: The run returned sanitized `pipeline_interrupted` after approximately 85 seconds and advanced state three times: `cab3afa...` to `072d0cd...` at 20:35:26, then `0aeda16...` at 20:35:50, then `984e353...` at 20:36:25; protected publication was skipped.
  implication: Verified rejection terminalization is live-confirmed. Decode only typed kind/count deltas to locate the next post-checkpoint failure.

- timestamp: 2026-07-28T09:12:00+08:00
  checked: Sanitized typed root/object deltas across cab3, 072d, 0aeda and 984e
  found: cab3 to 072d replaces only the operations envelope with no fact-count change; 072d to 0aeda adds candidate-1 semantic reservation ordinal 1 plus Phase 2 Scout/Filter/Reader facts; 0aeda to 984e adds candidate-1 Extractor semantic attempt 1 with status `started` plus its local running-attempt fact. No candidate/workflow terminal or result-status transition is durable.
  implication: All transitions remain candidate ordinal 1. The provider request boundary was authorized after the exact started receipt, but no decided, confirmed-retryable or outcome-unknown result receipt completed.

- timestamp: 2026-07-28T09:18:00+08:00
  checked: Plan 05-14 durability contract and semantic barrier read path
  found: The contract requires one full post-CAS reread of the exact remote commit/tree/root/objects. Current active confirmation performs three full reads: a pre-sync restore, per-blob sync verification and a second full restore; an idempotent confirmation performs two.
  implication: Duplicate full reads are not required authority. A semantic-only lightweight sync check followed by the existing full byte-equal restore preserves the locked receipt contract while removing the hosted request amplification.

- timestamp: 2026-07-28T09:30:00+08:00
  checked: Strict semantic confirmation read-count RED on a real three-store bundle and in-memory Git remote
  found: One active Extractor `attempt_started` confirmation issued 35 blob reads for a 12-file child bundle; the one-full-reread contract expected 12.
  implication: Request amplification is directly reproduced, but it remains an adjacent performance defect until a bounded request budget proves it changes the exact post-result/terminal outcome.

- timestamp: 2026-07-28T09:40:00+08:00
  checked: Request-budget algebra for the exact post-result semantic confirmation
  found: Let `P` be sync requests through CAS and `V` its mandatory full post-CAS reread. A fixed direct sync needs `P+V`; current code reaches CAS after its pre-restore at `R+P`, and `R=V` because both read the same ref/commit/tree/blob set. Therefore any budget sufficient for the proposed fix also lets current code advance the ref before failing.
  implication: Since live HEAD contains only `started` and no `decided` transition, triple-read amplification cannot be the causal explanation under a synthetic request-count budget. The adjacent read-count RED was removed and no barrier optimization is authorized by this symptom.

- timestamp: 2026-07-28T09:46:00+08:00
  checked: Exact default Phase-2 handled-terminal path with injected cleanup failures
  found: All four strict cases fail: an ordinary close exception from the resolved Extractor, GitHub reader, lazy publication store, or Phase-2 state store escapes the unguarded `finally` after the factory has constructed a `permanent_failure` terminal, masks that return, and stops subsequent cleanup.
  implication: Cleanup masking exactly reproduces durable `started` with no candidate terminal and public `pipeline_interrupted`; however sanitized live evidence does not identify which concrete close raised.

- timestamp: 2026-07-28T10:00:00+08:00
  checked: Minimal cleanup containment against handled-terminal and primary-exception matrices
  found: A private no-output helper attempts every close and suppresses cleanup-only exceptions. All eight cases pass across four resource categories and two primary outcomes.
  implication: Classified terminal returns and primary exceptions now survive cleanup, while every remaining resource still receives a close attempt.

- timestamp: 2026-07-28T10:08:00+08:00
  checked: Adjacent locked regressions, complete locked suite, Ruff lint, formatter baseline and scoped diff
  found: Adjacent discovery/semantic/recovery/state tests pass 270/270; the complete suite passes 1816 with 2 skipped; Ruff lint and `git diff --check` pass. Targeted Ruff format check reports the existing repository formatting baseline for both changed files, so no broad rewrite was applied.
  implication: The containment introduces no detected regression and the exact two-file diff is ready for an atomic commit.

- timestamp: 2026-07-28T10:12:00+08:00
  checked: Atomic implementation-and-regression commit and post-commit worktree scope
  found: Commit `dbf99a9` contains exactly `src/skillscout/bootstrap.py` and `tests/test_discovery_application.py`; only the active debug session remains untracked.
  implication: The cleanup containment is ready for parent-owned live verification without archiving the session.

- timestamp: 2026-07-28T10:30:00+08:00
  checked: Hosted run 30305186275 at exact source SHA `dbf99a93719eb8135cb8b4f6a96ac556ecf3b81d`
  found: The run returned sanitized `pipeline_interrupted` after approximately 20 seconds and state remained unchanged at `984e353...`, whose exact durable boundary is candidate-1 Extractor attempt 1 `started` with no result.
  implication: This restart cannot causally verify the same-run cleanup containment. The precise current bug is orphan semantic-attempt recovery: the provider request must never be replayed, and the unknown outcome must become a durable quarantine/terminal transition rather than an ordinary escape.

- timestamp: 2026-07-28T10:42:00+08:00
  checked: Discovery restart ordering before default Phase-2 recovery
  found: The restored snapshot already contains candidate-1's discovery reservation, but the candidate loop calls the idempotent reservation API and unconditionally synchronizes the unchanged three-store bundle before invoking Phase 2. PipelineRunner's later `running|abandoned` branch already performs zero-replay unknown-outcome confirmation.
  implication: State remaining exactly at 984 bounds the restart failure to the redundant pre-factory reservation sync. Skipping only a reservation proven present in the restored snapshot lets the existing semantic recovery execute without weakening first-time reservation durability.

- timestamp: 2026-07-28T10:50:00+08:00
  checked: Exact real-store orphan-started restart RED with forbidden provider constructor
  found: The fixture contains four terminal Search coordinates, one discovery reservation, one semantic reservation, completed Scout/Filter/Reader results, and Extractor attempt1 `running`; current restart collapses to `pipeline_interrupted` at the barrier's forbidden pre-terminal discovery sync.
  implication: The RED reproduces the live unchanged-984 boundary before any provider construction and differentiates it from the existing semantic recovery and terminal persistence paths.

- timestamp: 2026-07-28T11:00:00+08:00
  checked: Unwrapped exact restart after snapshot-bound discovery-reservation reuse
  found: Provider construction remains zero; `result_outcome_unknown` confirms and the candidate terminal synchronizes. Final summary then fails with `OperationsIntegrityError("run summary projection mismatch")` because the factory-local semantic reservation is reset to `None`, yielding terminal semantic count 0 against restored store count 1.
  implication: Restart must rebind the exact restored semantic reservation so the quarantine terminal preserves its non-refundable reservation lineage.

- timestamp: 2026-07-28T11:12:00+08:00
  checked: Exact restart GREEN with outer sanitizer restored and mismatched semantic-authority negative control
  found: The provider constructor is called zero times; the barrier receives exactly `result_outcome_unknown`; discovery syncs only the candidate terminal and degraded summary; operations persists semantic attempt and terminal as `semantic_outcome_unknown`. A mismatched restored Phase-2 authority fails closed before provider construction or remote transition.
  implication: The minimal two-part recovery preserves no-replay and non-refundable reservation lineage while rejecting incoherent restored authority.

- timestamp: 2026-07-28T05:20:00+08:00
  checked: Five adjacent locked suites after the exact restart GREEN
  found: 263 tests passed and all eight failures are the existing direct-factory cleanup parametrizations; their synthetic operations store contains no discovery run, so the new restored-reservation snapshot rejects the invalid fixture before its intended cleanup path.
  implication: Preserve the production fail-closed precondition and make the cleanup fixture establish the run that DiscoveryApplication always creates before invoking Phase 2.

- timestamp: 2026-07-28T05:25:00+08:00
  checked: Corrected eight-case cleanup fixture matrix
  found: All 8 parametrizations pass after creating the discovery run required by the default factory contract.
  implication: Cleanup containment remains intact without weakening the restored semantic-reservation validation.

- timestamp: 2026-07-28T05:28:00+08:00
  checked: Adjacent discovery, pipeline-resume, semantic-durability, operations-state and state-branch suites
  found: All 271 tests passed.
  implication: Orphan recovery, cleanup containment, semantic durability, projection integrity and state synchronization remain green together.

- timestamp: 2026-07-28T05:31:00+08:00
  checked: Complete locked repository pytest suite
  found: 1817 tests passed and 2 tests skipped in 43.78 seconds.
  implication: No repository-wide offline regression is detected.

- timestamp: 2026-07-28T05:34:00+08:00
  checked: Configured Ruff lint, whitespace validation and complete scoped diff review
  found: Ruff reports all checks passed and `git diff --check` passes; tracked changes are exactly `discovery.py`, `bootstrap.py` and `test_discovery_application.py`, while the active debug session remains untracked.
  implication: The no-replay recovery is statically clean and ready for one atomic implementation-and-regression commit.

- timestamp: 2026-07-28T05:37:00+08:00
  checked: Atomic implementation-and-regression commit and post-commit worktree scope
  found: Commit `e8d4b85fca9970676bd28f665428a62831647237` contains exactly `src/skillscout/application/discovery.py`, `src/skillscout/bootstrap.py` and `tests/test_discovery_application.py`; only the active debug session remains untracked.
  implication: Offline verification is complete and the exact source is ready for parent-owned live causal verification without archiving the session.

- timestamp: 2026-07-28T05:40:00+08:00
  checked: Hosted run 30306497938 at exact source SHA `e8d4b85fca9970676bd28f665428a62831647237`
  found: The run returned sanitized `pipeline_interrupted` after approximately twenty seconds and state remained at `984e353...`; earlier runs shared the GitHub token's hourly request budget, so failure may have occurred during initial full restore before orphan recovery.
  implication: This live result neither confirms nor disproves the offline orphan fix. Request throughput is now a Phase 5 blocker; audit the full bounded transition envelope and remove redundant blob-body reads without weakening CAS or byte binding.

- timestamp: 2026-07-28T05:48:00+08:00
  checked: Structural request graph for StateBranch sync and semantic confirmation
  found: Existing-branch sync costs `C + 9 + F_new` requests and active semantic confirmation costs `C + 15 + F_prev + 2*F_new`, where `C` is changed blobs and `F` is complete tree files. Exact-tree sync plus one post-CAS restore reduces these to `C + 9` and `C + 12 + F_new`. At a 140-file live baseline, the requested 100-discovery/20-semantic envelope drops from approximately 23,960 to 4,260 requests.
  implication: The optimization is structurally material but residual throughput remains above the approximately 1,000 requests per repository per hour Actions-token budget; real reservation-plus-terminal orchestration can exceed the simplified 100-transition envelope. Deterministic batching or another persistent transport remains a production blocker after this fix.

- timestamp: 2026-07-28T05:53:00+08:00
  checked: Strict exact-tree, 100-transition and semantic one-restore RED contracts
  found: Four cases fail as predicted. Valid sync invokes the forbidden body getter; 100 incremental discovery syncs add exactly 5,450 body GETs beyond the matching 1,100 metadata/write calls; one active semantic confirmation reads 35 bodies for a 12-file target. Four hostile tree-shape mutations already fail closed.
  implication: The counters isolate the amplification to `_verify_sync` plus semantic pre-restore, and provide exact post-fix targets without changing CAS or restore validation.

- timestamp: 2026-07-28T05:57:00+08:00
  checked: Direct semantic sync prior-root mutation control
  found: Supplying the correct prior head with a wrong expected prior root initially advanced CAS instead of failing.
  implication: Removing the full pre-restore requires an explicit metadata-only prior-root binding; validate the exact Root-Digest trailer of the parent commit before any write.

- timestamp: 2026-07-28T06:02:00+08:00
  checked: Exact-tree hostile matrix, 100-transition counter, one-restore counter and prior-root binding after the minimal fix
  found: All 9 contracts pass. Valid sync and five hostile variants issue zero body GETs; 100 discovery syncs cost exactly 1,100 calls; active and idempotent semantic confirmations each restore one complete body set; wrong prior root fails before CAS.
  implication: Complete path-to-Git-SHA, parent Root-Digest, non-force CAS and one full byte restore preserve the locked integrity chain while removing the measured amplification.

- timestamp: 2026-07-28T06:05:00+08:00
  checked: Complete StateBranch and semantic durability test files
  found: All 142 tests passed.
  implication: Wire validation, CAS conflicts, crash recovery, provider matrices and guarded-effect boundaries remain intact.

- timestamp: 2026-07-28T06:08:00+08:00
  checked: Adjacent StateBranch, semantic durability, discovery application, pipeline resume, operations state and discovery security suites
  found: All 285 tests passed.
  implication: The optimization remains compatible with orphan recovery, operations projections and security boundaries.

- timestamp: 2026-07-28T06:12:00+08:00
  checked: Complete locked repository pytest suite
  found: 1826 tests passed and 2 tests skipped in 43.61 seconds.
  implication: No repository-wide offline regression is detected.

- timestamp: 2026-07-28T06:16:00+08:00
  checked: Ambiguous post-CAS commit-message mutation
  found: A wrong Root-Digest commit message was rejected by sync verification but then accepted by the conflict fallback's full restore because restore had not bound the commit message to the parsed root.
  implication: Full restore must compare the exact deterministic commit message to the root digest before it can authorize idempotent or ambiguous post-CAS recovery.

- timestamp: 2026-07-28T06:20:00+08:00
  checked: Final hostile matrix and complete locked repository suite
  found: The 16-case focused matrix passes after binding restore to the exact commit Root-Digest; the complete suite passes 1827 tests with 2 skipped in 43.75 seconds.
  implication: The final exact-tree, CAS, prior-root, commit-message and byte-restore chain has no detected repository-wide regression.

- timestamp: 2026-07-28T06:23:00+08:00
  checked: Final configured Ruff, whitespace and scoped worktree checks
  found: Ruff reports all checks passed and `git diff --check` passes; tracked changes are exactly the StateBranch implementation plus StateBranch and semantic durability regressions.
  implication: The implementation is statically clean and scoped for one atomic commit.

- timestamp: 2026-07-28T06:25:00+08:00
  checked: Atomic implementation-and-regression commit and post-commit worktree
  found: Commit `1f65fd04f4c0cc9bf36dced6bb83cfc763baf6dc` contains exactly `src/skillscout/adapters/state_branch.py`, `tests/test_state_branch.py` and `tests/test_semantic_durability.py`; only this active debug session remains untracked.
  implication: The request-amplification fix is ready, but the explicitly recorded residual request-budget blocker prevents production readiness or debug archival.

- timestamp: 2026-07-28T05:49:46+08:00
  checked: Hosted run 30307999057 at exact source SHA `1f65fd04f4c0cc9bf36dced6bb83cfc763baf6dc`
  found: The run returned sanitized `pipeline_interrupted` after approximately 34 seconds; durable state remained at the restored 984 parent and no unknown child commit appeared.
  implication: The optimized code still raises before the recovery transition's non-force CAS; provider replay remains forbidden and the exact prospective transition must be reproduced offline.

- timestamp: 2026-07-28T05:49:46+08:00
  checked: Sanitized live parent commit metadata and typed root binding
  found: The 984 parent has the canonical four-line state commit-message shape, exactly one Root-Digest trailer, and that trailer equals the typed `state/root.json` root digest.
  implication: The new expected-prior-root check is compatible with the live parent; the investigation moves to prospective bundle construction and other pre-CAS invariants.

- timestamp: 2026-07-28T05:55:00+08:00
  checked: Exact post-crash orphan fixture with assembled parent bundle, canonical parent commit, instrumented in-memory remote and real StateBranchDurabilityBarrier
  found: The single locked test passed. Provider construction remained zero, non-force `update_state_ref` was reached, no exception was raised, and the final remote operation was `get_blob` during the mandatory post-CAS full restore.
  implication: Exact three-store prospective bundle assembly and local StateBranch pre-CAS validation do not reproduce the live unchanged-984 interruption; the remaining cause requires a live-client transport/runtime difference.

- timestamp: 2026-07-28T06:05:00+08:00
  checked: Complete exact offline DiscoveryApplication restart from real in-memory restore through unknown result, quarantine terminal and degraded summary
  found: The focused test passed with zero recovery provider constructions or calls, 119 total remote operations, exactly three non-force ref updates, a final `get_tree` verification operation, one semantic-outcome-unknown attempt and terminal, and a completed_degraded summary.
  implication: The complete local restart/orchestration/state-domain chain is valid; the unchanged live parent requires a GitHub client, request-budget, or environment-specific divergence before the first CAS.

- timestamp: 2026-07-28T06:15:00+08:00
  checked: Focused, adjacent and complete locked validation for the test-only exact-restart regression
  found: The focused test passed; six adjacent discovery/state/recovery suites passed 286 tests; the complete repository suite passed 1827 tests with 2 skipped in 43.71 seconds.
  implication: Preserving the complete exact-restart diagnostic introduces no detected functional regression.

- timestamp: 2026-07-28T06:15:00+08:00
  checked: Ruff lint, formatter baseline, whitespace and scoped diff
  found: Ruff lint passes and `git diff --check` passes. Ruff format check still reports the existing full-file formatting baseline; no broad rewrite was applied. The tracked diff is test-only.
  implication: The diagnostic evidence is lint-clean, whitespace-clean and isolated from production code.

- timestamp: 2026-07-28T06:18:00+08:00
  checked: Atomic test-only evidence commit and post-commit worktree
  found: Commit `4083a54c5b1811837234ee18a49d83efa3a5a52c` contains only `tests/test_discovery_application.py`; only this active debug session remains untracked.
  implication: The complete exact-restart regression is preserved without production changes, and the session remains active for live-only boundary diagnosis.

- timestamp: 2026-07-28T06:30:00+08:00
  checked: Fresh hosted run 30309241563 after the quota-reset window
  found: The run still returned sanitized pipeline_interrupted in approximately 26 seconds and durable state remained at the same parent.
  implication: Shared hourly quota is disproven as the immediate cause; an actual-wire read-only prewrite trace is authorized for later execution.

- timestamp: 2026-07-28T15:15:00+08:00
  checked: Safe actual-wire prewrite tracer at source commit `4083a54`
  found: Every remote state mutation and semantic provider boundary was hard-blocked, and output excluded messages, content and identifiers. The public result was `pipeline_interrupted`; the deepest ordinary exception was `OperationsIntegrityError` at `operations_state.py:2734` inside `restore_three_store_bundle`.
  implication: The unchanged remote parent is explained by a deterministic local restore-integrity failure before any permitted write or provider call.

- timestamp: 2026-07-28T15:18:00+08:00
  checked: Sanitized three-store restore projection comparison
  found: Only `pipeline_export_digest` differed. The pipeline, operations and publication business projections and the operations/publication export digests were equal.
  implication: The restored pipeline database is being mutated locally during verification; remote bytes and the other two stores are not the source of the mismatch.

- timestamp: 2026-07-28T15:21:00+08:00
  checked: Strict restore-order RED at commit `e9ca792`
  found: `test_three_store_restore_verifies_orphan_before_startup_reconciliation` reproduces the same `OperationsIntegrityError` at line 2734 when an orphan semantic attempt exists.
  implication: Opening `SQLiteStateStore` with normal startup reconciliation before final bundle verification causally changes the pipeline export digest and rejects the exact restored bundle.

- timestamp: 2026-07-28T15:25:00+08:00
  checked: Minimal restore-order fix at commit `299e29b`
  found: `SQLiteStateStore` now has internal `reconcile_orphans: bool = True`; only the final integrity-verification open in `restore_three_store_bundle` passes `False`, while normal subsequent opens retain default orphan recovery.
  implication: Remote bytes are verified before startup mutation without weakening ordinary recovery or enabling provider replay.

- timestamp: 2026-07-28T15:28:00+08:00
  checked: Focused, adjacent and complete locked verification for `299e29b`
  found: Focused restore-order tests pass 3/3; adjacent suites pass 207/207; the full locked suite passes 1828 with 2 skipped; Ruff and `git diff --check` pass.
  implication: The minimal restore-order correction is ready for parent-owned hosted causal verification; the session must remain active and unarchived.

- timestamp: 2026-07-28T15:45:00+08:00
  checked: Restart continuation after restore-order fix
  found: A `candidate_source_unavailable` ordinary exception escaped the typed fatal classification boundary; commit `b8cb282` contains the bounded correction.
  implication: Successful byte-exact restore exposed the next restart-only escape instead of reaching durable terminal accounting.

- timestamp: 2026-07-28T15:55:00+08:00
  checked: Fatal summary projection after candidate-source classification
  found: The fatal summary omitted the already-durable reservation count and failed projection integrity; commit `b1ecb11` preserves the durable reservation accounting.
  implication: Fatal completion must summarize durable facts already present in restored state, even when no new semantic work is permitted.

- timestamp: 2026-07-28T16:05:00+08:00
  checked: Crash-persisted fatal accumulation and later restore behavior
  found: Repeated restart handling accumulated persisted fatal state and prevented a normal restored return; commit `3f034da` makes fatal persistence idempotent and allows the recovered terminal state to stop cleanly.
  implication: Restart reconciliation must not append duplicate fatal facts or re-enter work after the exact terminal state has been restored.

- timestamp: 2026-07-28T16:15:00+08:00
  checked: Safe latest-state shadow execution at exact final code
  found: The shadow returned normally with one in-memory summary sync and no semantic provider construction or call.
  implication: The complete restored-state control flow is coherent and no-replay before live verification.

- timestamp: 2026-07-28T16:25:00+08:00
  checked: Hosted workflow run `30314354246` at exact SHA `3f034dac9c6ecb074b69b5d34c694acb5c3617c8`
  found: The discovery job succeeded in 53 seconds.
  implication: The complete restart root-cause chain and fixes are causally confirmed in the hosted environment; the debug session is resolved.

- timestamp: 2026-07-28T16:28:00+08:00
  checked: Final local verification at exact resolved code
  found: The complete locked suite passes 1838 tests with 2 skipped; Ruff and `git diff --check` pass.
  implication: Hosted success and the final local regression suite agree; the session can be archived.

## Eliminated

- hypothesis: Fresh local three-store bundle assembly or deterministic StateBranchStore sync always fails on the first discovery page.
  evidence: A real typed run/page/candidate exported all three owner stores and completed parent-bound non-force StateBranchStore sync with exact reread.
  timestamp: 2026-07-28T02:18:00+08:00

- hypothesis: A production-shaped GitHub Search page or multi-candidate operations transaction raises before the first barrier.
  evidence: The real Search adapter with the live request-ID form recorded one page and three candidates; the only interruption was the injected barrier stop.
  timestamp: 2026-07-28T02:21:00+08:00

- hypothesis: The exact 75-observation/74-selected restored prefix raises while deduplicating, assigning ordinals, or recording q1/p3.
  evidence: A bounded typed replay persisted q1/p3 with 25 new candidates, reached 99 selected candidates and called the barrier; the probe then stopped only on the deliberately injected following Search call.
  timestamp: 2026-07-28T04:32:00+08:00

- hypothesis: A legitimate q1/p3 repository metadata field contains a configured secret-canary prefix and is rejected during bundle validation.
  evidence: The mechanism reproduces offline, but the bounded live q1/p3 adapter probe reported page_canary=false and canary=false for every item ordinal 1 through 25.
  timestamp: 2026-07-28T04:42:00+08:00

- hypothesis: A non-canary local bundle-validation boundary rejects the exact 100-observation fourth checkpoint before StateBranchStore sync.
  evidence: Real three-store assembly produced the expected verified 113-file/109-object bundle with 100 observations and 99 selected candidates.
  timestamp: 2026-07-28T04:48:00+08:00

- hypothesis: The exact 95-selected prefix raises while crossing the 100-candidate budget on q1/p4.
  evidence: Real application/store replay persisted five first_seen and twenty budget_excluded observations, stopped at exactly 100 selected, and reached the durability barrier.
  timestamp: 2026-07-28T05:52:00+08:00

- hypothesis: The exact live q2/p2 Search response fails adapter validation or contains a configured state canary.
  evidence: The bounded adapter returned ok and every page/item canary boolean was false.
  timestamp: 2026-07-28T06:02:00+08:00

- hypothesis: Exporting the q2/p2 budget-excluded observations or synchronizing the resulting exact 139-file child deterministically fails.
  evidence: Real three-store assembly produced 135 objects and 139 files, and a 109-to-135 parent-reuse StateBranch sync completed with exact byte reread and 27 new blobs.
  timestamp: 2026-07-28T06:11:00+08:00

- hypothesis: Ordinal-1 Phase 2 admission fails because its valid GitHub full name exceeds RepositorySubject's 128-character subject-ID bound.
  evidence: The bounded typed probe found full-name length 10, derived subject-ID length 15, and current validator acceptance.
  timestamp: 2026-07-28T07:45:00+08:00

- hypothesis: Semantic barrier triple-read amplification can be fixed under the same request budget while explaining why live state remains at Extractor `started`.
  evidence: Direct sync requires `P+V` requests; current reaches CAS at `R+P`, and the pre-restore `R` equals the mandatory verification reread `V`. A budget that allows fixed completion also allows current CAS, which would have durably advanced beyond `started`.
  timestamp: 2026-07-28T09:40:00+08:00

- hypothesis: The restored 984 parent uses legacy commit metadata incompatible with the new pre-CAS expected-prior-root binding.
  evidence: The sanitized live parent has the canonical commit-message shape, exactly one Root-Digest trailer, and the trailer equals the typed restored root digest.
  timestamp: 2026-07-28T05:49:46+08:00

- hypothesis: The exact prospective orphan `result_outcome_unknown` bundle raises during three-store assembly or local StateBranch pre-CAS validation.
  evidence: The exact instrumented orphan fixture passed through real StateBranchDurabilityBarrier confirmation, reached non-force `update_state_ref`, fully restored the child, and constructed no provider.
  timestamp: 2026-07-28T05:55:00+08:00

- hypothesis: A local failure after restore but before the completed_degraded summary prevents the exact orphan restart from advancing durable state.
  evidence: The full exact DiscoveryApplication restart performed real restore, unknown semantic confirmation, candidate terminal sync and summary sync with three non-force CAS operations and zero recovery provider construction.
  timestamp: 2026-07-28T06:05:00+08:00

- hypothesis: The fresh hosted restart fails immediately because earlier runs exhausted the shared hourly request quota.
  evidence: A new run after the quota-reset window still returned pipeline_interrupted with unchanged durable state.
  timestamp: 2026-07-28T06:30:00+08:00

## Resolution

- root_cause: The hosted restart failed through a chain of restart-only defects. Three-store verification opened the pipeline database with orphan reconciliation enabled, changing `pipeline_export_digest` before byte-exact comparison. After that was fixed, `candidate_source_unavailable` escaped typed fatal classification, fatal summaries omitted already-durable reservation counts, and crash-persisted fatal state accumulated or prevented a clean restored return. Earlier in the same investigation, restored discovery/semantic reservations were also lost or redundantly synchronized, and state verification amplified GitHub requests by rereading every blob body.
- fix: Verify restored three-store bytes before startup orphan reconciliation; classify candidate-source failure through the typed fatal boundary; include durable reservation facts in fatal summaries; make crash-persisted fatal recovery idempotent and terminal. Retain the earlier no-replay restored-reservation recovery and exact path-to-Git-blob-SHA state verification with non-force CAS and one authoritative restore.
- verification: Safe actual-wire tracing localized the restore failure without remote writes, provider calls or sensitive output. Strict RED tests reproduced each boundary. A safe latest-state shadow returned normally with one in-memory summary sync and no provider. Final local verification passed 1838 tests with 2 skipped plus Ruff and `git diff --check`. Hosted run `30314354246` at exact SHA `3f034dac9c6ecb074b69b5d34c694acb5c3617c8` completed the discovery job successfully in 53 seconds.
- files_changed:
  - src/skillscout/adapters/github.py
  - tests/test_github_search.py
  - src/skillscout/adapters/operations_state.py
  - tests/test_operations_state.py
  - src/skillscout/domain/discovery.py
  - src/skillscout/bootstrap.py
  - tests/test_discovery_application.py
  - src/skillscout/adapters/state_branch.py
  - tests/test_state_branch.py
  - src/skillscout/adapters/phase2_state.py
  - tests/test_candidate_source.py
  - tests/test_scout_filter.py
