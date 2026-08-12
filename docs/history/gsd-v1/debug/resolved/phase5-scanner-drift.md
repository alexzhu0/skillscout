---
status: resolved
trigger: "Phase 5 full-suite baseline regression: three failures because Phase 1 gap-closure and Phase 3 acceptance security scanners reject urllib.parse imported by Plan 05-04 in src/skillscout/adapters/github.py."
created: 2026-07-27
updated: 2026-07-27T14:14:15Z
---

# Debug Session: Phase 5 Scanner Drift

## Symptoms

- expected: Phase 5 GitHub adapter change passes historical security boundary scanners without weakening execution capability restrictions.
- actual: Full locked suite reports three failures in tests/test_phase1_gap_closure.py and the Phase 3 acceptance scanner after urllib.parse was imported in src/skillscout/adapters/github.py.
- errors: Security scanner rejects urllib.parse as a forbidden capability.
- timeline: Regression introduced by Phase 5 Plan 05-04.
- reproduction: Run the focused scanner tests or the full locked pytest suite with repository-local uv and UV_CACHE_DIR.

## Current Focus

- hypothesis: RESOLVED — exact parsing carve-outs remove the false positive while denial mutations preserve the capability boundary.
- test: Human independently reran the full locked suite, Ruff, and diff integrity checks.
- expecting: MET — 1,544 passed, 2 skipped, 108 expected xfailed; Ruff and `git diff --check` passed.
- next_action: Archive this session, append the knowledge-base entry, and commit resolution metadata.
- reasoning_checkpoint:
    hypothesis: Both scanners classify `urllib.parse` as forbidden because they use `imported == "urllib" or imported.startswith("urllib.")`; the reviewed adapter therefore fails despite adding only pure URL parsing and no new transport.
    confirming_evidence:
      - The Phase 1 failure reports exactly `adapters/github.py:urllib.parse` and no forbidden call.
      - The Phase 3 scanner fails specifically at its nonempty forbidden-import assertion, and direct enumeration reports the same sole identity.
      - `GitHubReadClient` still performs every request through its existing serial `httpx.Client`, and the exact Phase 3 `httpx` importer set remains `adapters/github.py` plus `adapters/github_publish.py`.
    falsification_test: The hypothesis would be false if enumeration found another forbidden identity, if the adapter called any urllib network API, or if exact-carve-out mutation tests allowed `urllib.request` or allowed `urllib.parse` outside the reviewed adapter.
    fix_rationale: An exact file-and-module exception represents the reviewed pure parsing use while leaving bare `urllib`, every other `urllib.*` module, and the same pure parser in every other production file forbidden; negative mutations prove the capability boundary remains closed.
    blind_spots: Static AST scanners cannot prove runtime behavior of dynamically loaded code, but existing policy independently forbids `importlib` outside its fixed owners; no live network verification is needed or authorized for this scanner-only regression.
- tdd_checkpoint:

### Fault Tree

- observed symptom: historical acceptance scanners reject the Phase 5 GitHub Search adapter
  - OR H1: scanner policy is overbroad and confuses pure URL parsing with network authority
  - OR H2: `urllib.parse` supplies a capability that violates the original local-only/import boundary
  - OR H3: the adapter change widened HTTP authority elsewhere and `urllib.parse` is only the first visible failure
  - OR H4: scanner and adapter policies intentionally conflict, requiring the adapter to use an already-approved parser instead

## Evidence

- timestamp: 2026-07-27T14:02:35Z
  checked: `.planning/debug/knowledge-base.md`
  found: No debug knowledge base exists, so there is no prior known-pattern candidate.
  implication: Diagnose from current source and tests without assuming a previous fix.
- timestamp: 2026-07-27T14:02:35Z
  checked: Phase 5 Plan 05-04, summary, research, and deferred item
  found: The reviewed design requires fixed-host/fixed-path Search pagination, explicitly keeps one serial `httpx` capability, and uses URL parsing only to reduce a hostile Link header to a bounded integer cursor. The deferred item records 1,538 passed and exactly three scanner failures after this import.
  implication: The intended authority boundary distinguishes HTTP transport from deterministic parsing; any scanner change must preserve rejection of actual network and execution surfaces.
- timestamp: 2026-07-27T14:02:35Z
  checked: `tests/test_phase1_gap_closure.py`, `tools/verify_phase3_acceptance.py`, and `tests/test_phase3_acceptance_tool.py`
  found: Both scanners reject an import when it equals `urllib` or starts with `urllib.`. Neither distinguishes `urllib.parse` from network-capable modules. Both independently enforce exact `httpx` importer sets and forbidden execution calls.
  implication: Prefix matching can cause the reported false positive, but focused reproduction is still required before confirming H1.
- timestamp: 2026-07-27T14:02:35Z
  checked: `src/skillscout/adapters/github.py`
  found: The only urllib import is `from urllib.parse import parse_qsl, urlsplit`; those functions validate the fixed HTTPS GitHub Search link and exact ordered query before returning the next integer page. All requests remain in `GitHubReadClient._send` through its serial `httpx.Client`.
  implication: Source inspection supports H1 and contradicts a direct new transport capability, pending executable reproduction and mutation tests.
- timestamp: 2026-07-27T14:03:08Z
  checked: Focused Phase 1 capability test on the unchanged tree
  found: The test fails with exactly one forbidden import, `adapters/github.py:urllib.parse`; the collected forbidden-call list contributes no failure.
  implication: H1's Phase 1 prediction is confirmed and H3 has no support from this scanner result; reproduce the independent Phase 3 result next.
- timestamp: 2026-07-27T14:05:16Z
  checked: Focused Phase 3 acceptance current-tree test on the unchanged tree
  found: The inspector fails inside `_check_import_capability_isolation` at `_require(not forbidden)`; all earlier authority checks pass.
  implication: The independent scanner reaches the same import-policy boundary, matching H1 and ruling out supply-chain authority admission as the cause.
- timestamp: 2026-07-27T14:06:32Z
  checked: Complete focused scanner baseline
  found: The exact command produces 3 failed and 39 passed; failures are the Phase 1 capability assertion plus the Phase 3 direct-current-tree and CLI-success wrappers.
  implication: The three reported full-suite regressions are all reproduced and reduce to one predicate mismatch.
- timestamp: 2026-07-27T14:06:32Z
  checked: Direct Phase 3 scanner import enumeration
  found: `forbidden` is exactly `["adapters/github.py:urllib.parse"]`; `httpx_importers` remains exactly `["adapters/github.py", "adapters/github_publish.py"]`.
  implication: H1 is confirmed. H2 and H3 are eliminated, and the narrow fix can target only the scanner predicates.
- timestamp: 2026-07-27T14:08:12Z
  checked: Focused post-fix scanner, mutation, and GitHub Search suites
  found: 76 tests passed, including all three former failure paths, both new exact-carve-out policies, negative mutations, and the unchanged Search behavior.
  implication: The minimal scanner fix removes the false positive while executable negative evidence preserves the capability boundary.
- timestamp: 2026-07-27T14:08:42Z
  checked: Ruff on all changed Python files
  found: All checks passed.
  implication: The targeted implementation and tests meet the repository's static quality gate.
- timestamp: 2026-07-27T14:09:04Z
  checked: Scoped diff, worktree status, and `git diff --check`
  found: Only the two scanners, their regression tests, the resolved deferred-item deletion, and this debug session are changed; `git diff --check` reports no errors.
  implication: The change is isolated and ready for full regression verification.
- timestamp: 2026-07-27T14:10:08Z
  checked: Complete locked repository pytest suite
  found: 1,544 passed, 2 skipped, and 108 expected xfailed in 34.64 seconds with zero failures.
  implication: The original three regressions are fixed and adjacent historical, Search, publication, operations, and security behavior remains green.
- timestamp: 2026-07-27T14:11:22Z
  checked: Atomic fix commit
  found: Commit `7f98b0a` contains only the two scanner changes, their regression tests, and deletion of the resolved deferred item.
  implication: The verified code fix is durably isolated; the debug session remains active until required human confirmation.
- timestamp: 2026-07-27T14:14:15Z
  checked: Human verification checkpoint
  found: Human confirmed fixed after an independent rerun reported 1,544 passed, 2 skipped, 108 expected xfailed; Ruff and `git diff --check` passed.
  implication: End-to-end verification is complete and the session may be archived as resolved.

## Eliminated

- hypothesis: H2 — `urllib.parse` adds a production network or execution capability.
  evidence: The adapter imports only `parse_qsl` and `urlsplit`, calls them only while validating a Link value, and all request construction/sending remains in the existing `httpx` client.
  timestamp: 2026-07-27T14:06:32Z
- hypothesis: H3 — another Phase 5 capability widening is hidden behind the first scanner failure.
  evidence: Both scanners enumerate only `adapters/github.py:urllib.parse`; exact `httpx` importers and forbidden-call results remain unchanged.
  timestamp: 2026-07-27T14:06:32Z

## Resolution

- root_cause: Historical import scanners model the entire `urllib` namespace as a forbidden transport capability through prefix matching. Phase 5 legitimately imported the pure `urllib.parse` submodule for deterministic Link validation, so the scanners report a false capability widening even though network authority remains exclusively in the reviewed serial `httpx` adapter.
- fix: Added the sole exact carve-out `adapters/github.py:urllib.parse` to both scanner predicates; added positive policy locking and negative mutations proving bare `urllib`, `urllib.request`, and off-owner `urllib.parse` remain forbidden; removed the now-resolved sole deferred item.
- verification: Commit `7f98b0a`; focused scanner/Search regression 76 passed; Ruff passed on every changed Python file; full locked suite 1,544 passed, 2 skipped, 108 expected xfailed in 34.64s; `git diff --check` passed; human independently confirmed the same full-suite/Ruff/diff result.
- files_changed:
    - tests/test_phase1_gap_closure.py
    - tools/verify_phase3_acceptance.py
    - tests/test_phase3_acceptance_tool.py
    - .planning/phases/05-automated-discovery-operations/deferred-items.md
- investigation_cycles: 1
- fix_cycles: 1
