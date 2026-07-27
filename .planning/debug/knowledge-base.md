# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## phase5-scanner-drift — Historical scanners rejected reviewed urllib.parse parsing
- **Date:** 2026-07-27
- **Error patterns:** security scanner, urllib.parse, forbidden capability, Phase 1 gap closure, Phase 3 acceptance, three failures
- **Root cause:** Historical import scanners modeled the entire `urllib` namespace as a forbidden transport capability through prefix matching, so the pure `urllib.parse` submodule used for deterministic Link validation produced a false capability-widening failure.
- **Fix:** Added the sole exact carve-out `adapters/github.py:urllib.parse` to both scanner predicates; added positive policy locking and negative mutations proving bare `urllib`, `urllib.request`, and off-owner `urllib.parse` remain forbidden; removed the resolved deferred item.
- **Files changed:** tests/test_phase1_gap_closure.py, tools/verify_phase3_acceptance.py, tests/test_phase3_acceptance_tool.py, .planning/phases/05-automated-discovery-operations/deferred-items.md
---

## phase5-state-httpx-scanner-drift — Historical scanners rejected the fixed state-branch HTTP owner
- **Date:** 2026-07-27
- **Error patterns:** security scanner, httpx importer, exact HTTP owner, state_branch.py, Phase 1 gap closure, Phase 3 acceptance, three failures
- **Root cause:** Historical Phase 1 and Phase 3 import-capability scanners pinned the pre-Plan-05-06 set of `httpx` owners, so they rejected the planned fixed state-branch adapter by filename even though its reviewed capability is limited to one configured repository's Git objects and `refs/heads/skillscout-state`.
- **Fix:** Added only `adapters/state_branch.py:httpx` to both exact-owner policies; pinned the StateBranchClient method, endpoint, fixed-ref, and non-force boundaries; added negative mutations for off-owner HTTP, catalog PR paths, default branches, and public catalog methods; removed the resolved deferred item.
- **Files changed:** tests/test_phase1_gap_closure.py, tools/verify_phase3_acceptance.py, tests/test_phase3_acceptance_tool.py, .planning/phases/05-automated-discovery-operations/deferred-items.md
---

## phase5-state-request-id — Live GitHub colon request ID blocked missing-ref classification
- **Date:** 2026-07-28
- **Error patterns:** StateBranchClient, X-GitHub-Request-Id, colon-delimited request ID, 404, StateRefNotFound, SafeFailure
- **Root cause:** The state adapter validated request IDs with a synthetic single-token grammar before classifying allowed 404 responses, so a valid live uppercase-hex colon-delimited GitHub ID raised SafeFailure before the missing state ref could become StateRefNotFound.
- **Fix:** Preserved the 128-character bound and legacy safe-token alternative, added an exact two-or-more non-empty uppercase-hex colon-group alternative, and locked the boundary with the recorded live 404 plus missing, whitespace/control, malformed-group, non-hex, and oversized mutations without logging the value.
- **Files changed:** src/skillscout/adapters/state_branch.py, tests/test_state_branch.py
---

## github-blob-base64 — CR/LF-folded GitHub blob base64 failed strict decode
- **Date:** 2026-07-28
- **Error patterns:** StateBranchClient, GitHub blob content, CR/LF, base64, write-after-read, strict decoder, SafeFailure
- **Root cause:** `StateBranchClient.get_blob` applied Python's strict base64 decoder directly to GitHub's CR/LF-folded wire value, so valid live blobs failed before integrity verification; the decoder alone also accepts noncanonical pad-bit spellings.
- **Fix:** Removed only CR and LF before strict decoding, required exact canonical re-encoding equality, retained decoded-size and requested git-blob-ID verification, and added adapter-level positive and negative mutations for the complete boundary.
- **Files changed:** src/skillscout/adapters/state_branch.py, tests/test_state_branch.py
---
