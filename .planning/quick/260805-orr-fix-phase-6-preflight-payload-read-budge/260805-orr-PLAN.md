---
quick_id: 260805-orr
title: Fix Phase 6 preflight payload read budget
phase: quick-260805-orr
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - src/skillscout/adapters/state_branch.py
  - src/skillscout/bootstrap.py
  - tests/test_state_branch.py
  - tests/test_phase6_acceptance.py
must_haves:
  truths:
    - The Phase 6 fresh-campaign preflight grants a 90-second hard elapsed cap only to owned-payload restoration reads.
    - Lineage and ref reads retain their existing 45-second elapsed, request-count, response-byte, and hop limits.
    - Any request, response-byte, elapsed-time, integrity, or capability-boundary violation fails closed without writes or unbounded fallback.
  artifacts:
    - path: src/skillscout/adapters/state_branch.py
      provides: Phase-scoped resolver budget enforcement and split restore behavior.
    - path: src/skillscout/bootstrap.py
      provides: Fresh preflight construction of distinct lineage and payload budgets.
    - path: tests/test_state_branch.py
      provides: Budget and split-restore regression coverage.
    - path: tests/test_phase6_acceptance.py
      provides: Preflight wiring and lineage-horizon regression coverage.
  key_links:
    - from: src/skillscout/bootstrap.py
      to: src/skillscout/adapters/state_branch.py
      via: restore_with_split_budgets receives a restricted payload-phase elapsed allowance while lineage receives the default allowance.
    - from: ResolverReadBudget
      to: StateBranchReadClient._json
      via: begin_request and charge_response_bytes continue enforcing timeout, request, and byte ceilings on every remote read.
---

<objective>
Correct the Phase 6 fresh-campaign preflight payload read budget so only the payload phase can use a 90-second hard elapsed cap, while retaining all existing deterministic safety limits and read-only authority.

Purpose: Permit bounded verification of larger owned state payloads without weakening the immutable lineage proof or any remote-read safety boundary.
Output: Phase-scoped budget enforcement, preflight wiring, and focused regression tests.
</objective>

<context>
@AGENTS.md
@.planning/STATE.md
@src/skillscout/adapters/state_branch.py
@src/skillscout/bootstrap.py
@tests/test_state_branch.py
@tests/test_phase6_acceptance.py

The existing `restore_with_split_budgets` path already separates lineage and payload budgets and reports bounded `StateRestorePhaseFailure` labels. Preserve the ordinary restore budget behavior and the fixed state-ref/read-only capability. Do not alter GitHub endpoints, credentials, caches, lineage-anchor semantics, request-count ceiling, response-byte ceiling, hop ceiling, response validation, or fail-closed error mapping.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Restrict the elapsed-cap override to payload restoration</name>
  <files>src/skillscout/adapters/state_branch.py, src/skillscout/bootstrap.py</files>
  <action>Extend the resolver-budget implementation with an explicit, narrowly typed payload-phase allowance for a 90-second hard elapsed deadline while keeping the default/ref/lineage budget capped at the current 45 seconds. Reject invalid phase/elapsed combinations and preserve request-count, response-byte, per-request timeout, immutable-cache, lineage-anchor, and hop enforcement. In the fresh preflight bootstrap, construct the lineage budget with the unchanged default and the payload budget through the restricted payload-only path; keep `restore_with_split_budgets` read-only and fail closed for all budget or state-integrity failures. Do not make the general constructor or ordinary restore path accept an unrestricted 90-second setting.</action>
  <verify>
    <automated>.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_branch.py tests/test_phase6_acceptance.py</automated>
  </verify>
  <done>Only the payload phase can receive the 90-second hard elapsed cap; ref/lineage and ordinary restores remain at 45 seconds with all existing count, byte, hop, read-only, and fail-closed constraints intact.</done>
</task>

<task type="auto">
  <name>Task 2: Add regression coverage for phase-scoped elapsed budgets</name>
  <files>tests/test_state_branch.py, tests/test_phase6_acceptance.py</files>
  <action>Add deterministic clock/transport tests proving the default resolver and lineage budget reject elapsed time at 45 seconds, the payload-only budget permits reads through 90 seconds but rejects at its deadline, and request-count or response-byte exhaustion still fails closed in either phase. Exercise split restore to assert the two budgets are independent, the 90-second allowance is not passed to lineage, and the preflight path never opens a write capability or bypasses the fixed lineage anchor/horizon. Keep assertions limited to closed phase labels/statuses and counters; do not assert raw provider, token, path, or exception text.</action>
  <verify>
    <automated>.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_branch.py tests/test_phase6_acceptance.py</automated>
  </verify>
  <done>Focused tests fail on a phase-wide 90-second regression or any lost safety limit and pass with the payload-only elapsed-cap fix.</done>
</task>

</tasks>

<verification>
Run the focused state-branch and Phase 6 acceptance tests, then run the repository's locked full suite. Confirm the diff contains only the budget implementation, preflight wiring, and regression tests; no workflow, dependency, credential, endpoint, or publication authority changes are present.
</verification>

<success_criteria>
- Payload restoration alone has a hard 90-second elapsed ceiling.
- Ref and lineage reads, plus ordinary restore callers, retain the 45-second ceiling and existing request/byte/hop limits.
- All focused and full locked tests pass, with read-only and fail-closed behavior preserved.
</success_criteria>

<output>
Create `.planning/quick/260805-orr-fix-phase-6-preflight-payload-read-budge/260805-orr-SUMMARY.md` after execution.
</output>
