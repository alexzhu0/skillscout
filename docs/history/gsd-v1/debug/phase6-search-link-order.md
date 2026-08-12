---
status: resolved
trigger: "Phase 6 fresh-campaign preparation run 30788478745 ended with the safe stage_permanent_failure result."
created: 2026-08-03
updated: 2026-08-03T10:30:00Z
---

# Debug Session: Phase 6 Search Link Order

## Symptoms

- expected: The bounded public GitHub Search nomination accepts a GitHub `Link: rel=next` URL when it has the exact configured query parameters, regardless of their order.
- actual: The hosted preparation run ended with `stage_permanent_failure` before state synchronization, model use, benchmark locking, or PR creation.
- errors: The public CLI intentionally reports only the closed error code; no secret or provider body is logged.
- timeline: First fresh-campaign preparation attempt on 2026-08-03 after protected-environment setup.
- reproduction: A live GitHub Search response for the configured query supplies `order`, `page`, `per_page`, `q`, `sort`; `_search_next_page` compares that ordered list against `q`, `sort`, `order`, `per_page`, `page` and raises `SafeFailure`.

## Current Focus

reasoning_checkpoint:
  hypothesis: The GitHub Search adapter treats query-parameter serialization order as a security invariant, although URL query ordering is semantically irrelevant; an equivalent live `next` URL therefore triggers a permanent safe failure if the run reaches Search.
  confirming_evidence:
    - A read-only live Search header has the same five key/value pairs in a different order.
    - The adapter uses ordered-list comparison after `parse_qsl`.
    - The fixture uses the older order, so existing tests do not cover the live response form.
  falsification_test: A public-client regression test that supplies the live-equivalent reordered `next` Link must fail before the production fix and pass after a multiset-equivalence check. Existing hostile URL, malformed query, duplicate-key, and bound checks must remain closed.
  blind_spots: The hosted redacted error does not identify the exact endpoint. State restoration has another possible permanent-failure path, so a passing Link-order fix proves the blocking adapter bug but does not by itself prove that no later state issue exists.
next_action: RESOLVED — merge the isolated adapter correction, then begin a new fresh-campaign preparation attempt; do not retry the failed run.

## Evidence

- timestamp: 2026-08-03
  checked: Hosted run 30788478745 and state head
  found: Only the fresh preparation job ran and it returned the closed `stage_permanent_failure` result; no new state child was created.
  implication: No model, benchmark lock, candidate code execution, or Draft PR occurred.

- timestamp: 2026-08-03
  checked: Live public GitHub Search Link response and adapter comparison
  found: GitHub ordered the valid next-query parameters differently from the test fixture; `_search_next_page` compares their ordered lists exactly.
  implication: A valid live response deterministically fails at the adapter boundary.

- timestamp: 2026-08-03
  checked: Test-first public-client regression
  found: The reordered live-equivalent Link test failed before the production change with `SafeFailure(stage_permanent_failure)` at the ordered-list comparison, then passed after an exact multiset comparison.
  implication: The change accepts only reordering; it still requires the same keys, values, and parameter cardinality.

- timestamp: 2026-08-03
  checked: Scoped verification
  found: GitHub Search tests passed 55/55; the remaining Phase 6 acceptance tests passed 98 with 1 skipped and 12 known process-harness baseline cases excluded; acceptance and discovery application tests passed 78/78; scoped Ruff lint passed.
  implication: The adapter correction is isolated and surrounding fresh-campaign application behavior remains covered.

## Eliminated

- hypothesis: Environment secret names, repository identity variables, or `main` branch policy caused the observed setup failure.
  evidence: Both environment secret names exist without reading values, state repository ID/name match the live repository, and the job reached its preparation command.

## Resolution

- root_cause: `_search_next_page` compared `parse_qsl` output to an ordered expected list, despite query-parameter order not being semantic. Live GitHub Search reordered the same five bounded key/value pairs.
- fix: Compare sorted key/value pairs, retaining exact values and multiplicity while ignoring only serialization order.
- verification: The new regression failed before the fix and passed after it; Search adapter tests passed 55/55; surrounding application tests passed 78/78; remaining Phase 6 acceptance tests passed 98 with 1 skipped and 12 unrelated pre-existing process-harness baseline failures excluded; scoped Ruff lint passed. Ruff format-check reports existing whole-file drift on both changed files, so no unrelated formatting rewrite was applied.
- files_changed:
  - src/skillscout/adapters/github.py
  - tests/test_github_search.py
