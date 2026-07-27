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
