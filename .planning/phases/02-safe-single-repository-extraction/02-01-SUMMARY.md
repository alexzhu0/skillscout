---
phase: 02-safe-single-repository-extraction
plan: "01"
subsystem: security
tags: [supply-chain, uv-lock, pydantic, contracts, filtering, reading, extraction, fingerprint]

# Dependency graph
requires:
  - phase: 01-auditable-dry-run-spine
    provides: two-gate lock-approval ceremony, StrictFrozenModel idiom, closed error codes, producer schema registry, authority-bound evidence verifier
provides:
  - Gate-A2/Gate-B2 human-approved httpx==0.28.1 and openai==2.46.0 runtime graph at uv.lock SHA-256 a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216
  - Frozen Phase 2 domain contracts: RepositorySubject/load_subject, filter-policy-v1, reader-policy-v1, extractor-response-v1/workflow-spec-v1, wf-fingerprint-v1, deterministic boundary validation
  - Additive Phase 1 members RunStatus.COMPLETED, ErrorCode.INVALID_SUBJECT, ("2","phase2-v1") producer registration
affects: [02-safe-single-repository-extraction plans 02-02..02-04, phase 3+]

# Tech tracking
tech-stack:
  added: [httpx==0.28.1, openai==2.46.0]
  patterns: [closed ordered rule-set verdicts with per-rule versioned decisions, budget-ceiling-validated policy models, skillscout-owned versioned fingerprint preimages, deterministic drop-not-repair boundary validation]

key-files:
  created: [src/skillscout/domain/subjects.py, src/skillscout/domain/filtering.py, src/skillscout/domain/reading.py, src/skillscout/domain/extraction.py, src/skillscout/adapters/subjects.py, tests/test_phase2_contracts.py, tests/fixtures/subject/approved.json]
  modified: [pyproject.toml, uv.lock, src/skillscout/domain/enums.py, src/skillscout/domain/models.py, src/skillscout/application/ports.py, tests/test_stage_contracts.py, tests/test_phase1_gap_closure.py, tools/verify_phase1_gap_evidence.py]

key-decisions:
  - "Admit exactly httpx==0.28.1 and openai==2.46.0 through the Phase 1 two-gate ceremony; no tiktoken, GitHub SDK, tenacity, or VCR library."
  - "Re-anchor the Phase 1 evidence verifier LOCK_HASH to the Gate-B2-approved uv.lock bytes so the authority constant tracks the human-approved graph; recorded Phase 1 evidence stales by design and awaits Phase 2 re-baselining."

patterns-established:
  - "Two-gate supply-chain ceremony: declaration approval (A) and exact-lock-bytes approval (B) are separate blocking human gates; execution only after both."
  - "Closed rule-set evaluation: every filter decision records rule id, rule version, observed value, pass|fail|not_applicable and a closed rationale."
  - "Organization-ceiling validation: policy defaults double as ceilings; any above-ceiling value is rejected at model validation."

requirements-completed: [FILT-01, FILT-02, FILT-03, READ-03, READ-05, EXTR-02, EXTR-03]

coverage:
  - id: D1
    description: "Exactly two runtime dependencies (httpx==0.28.1, openai==2.46.0) admitted through Gate A2 and Gate B2; execution bound to exact approved lock bytes a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216"
    verification:
      - kind: other
        ref: "shasum -a 256 uv.lock => a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216 (pre-execution gate check)"
        status: pass
      - kind: other
        ref: "uv lock --check => Resolved 24 packages, exit 0"
        status: pass
    human_judgment: true
    rationale: "Gate A2 and Gate B2 are inherently human supply-chain approval decisions; both were explicitly approved by the human reviewer before any execution."
  - id: D2
    description: "RepositorySubject strict contract and bounded single-descriptor load_subject with closed INVALID_SUBJECT mapping"
    verification:
      - kind: unit
        ref: "tests/test_phase2_contracts.py#test_subject_strictness_matrix_rejects, test_load_subject_rejects_* (symlink, non-regular, missing, oversized, malformed, schema-invalid, mid-read)"
        status: pass
    human_judgment: false
  - id: D3
    description: "filter-policy-v1 closed ordered eight-rule set with exact four-SPDX license allowlist and deterministic license boundary failures"
    requirement: FILT-01
    verification:
      - kind: unit
        ref: "tests/test_phase2_contracts.py#test_filter_repo_rule_matrix_fails_deterministically, test_filter_fails_null_noassertion_and_non_listed_licenses, test_filter_fails_multiple_root_license_files, test_filter_fails_unconfirmed_license_endpoint_outcomes, test_verdict_requires_the_closed_ordered_rule_set"
        status: pass
    human_judgment: false
  - id: D4
    description: "reader-policy-v1 five budgets plus soft target, fixed tier order, path/tier/allowlist predicates and ceiling rejection"
    requirement: READ-03
    verification:
      - kind: unit
        ref: "tests/test_phase2_contracts.py#test_reader_policy_defaults_equal_the_five_budgets_and_soft_target, test_reader_policy_rejects_above_ceiling_values, test_validate_repo_path_rejects_hostile_shapes, test_assign_tier_matrix, test_estimate_tokens_is_ceil_bytes_over_four"
        status: pass
    human_judgment: false
  - id: D5
    description: "extractor-response-v1 Structured-Outputs shape (additionalProperties false, all-required, maxItems 3, no tools), workflow-spec-v1 field list, wf-fingerprint-v1 stability/sensitivity/order properties, deterministic boundary-validation drop matrix"
    requirement: EXTR-03
    verification:
      - kind: unit
        ref: "tests/test_phase2_contracts.py#test_extractor_response_schema_is_structured_outputs_shaped, test_extractor_response_caps_workflows_at_three, test_fingerprint_is_stable_under_case_whitespace_punctuation_variation, test_fingerprint_is_sensitive_to_step_order, test_boundary_validation_drops_* (unknown path, blob mismatch, non-verbatim, over-length, forbidden text)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Additive Phase 1 members RunStatus.COMPLETED, ErrorCode.INVALID_SUBJECT, (\"2\",\"phase2-v1\") with exactly three sanctioned Phase 1 test amendments; full Phase 1 suite green"
    verification:
      - kind: unit
        ref: "tests/test_phase2_contracts.py#test_completed_run_status_is_additive_and_terminal, test_invalid_subject_error_code_is_closed_and_bounded, test_phase_two_producer_registration_is_additive; tests/test_stage_contracts.py registry test; tests/test_phase1_gap_closure.py dependency + capability sweep"
        status: pass
    human_judgment: false

# Metrics
duration: 17min
completed: 2026-07-22
status: complete
---

# Phase 02 Plan 01: Safe Single-Repository Extraction — Approved Dependencies and Frozen Contracts Summary

**httpx/openai admitted through the two-gate human ceremony and every Phase 2 semantic contract (subject, filter, reader, extraction, fingerprint, boundary validation) frozen and proven by 473 green tests under the exact Gate-B2-approved lock bytes.**

## Performance

- **Duration:** 17 min (this execution segment; excludes human gate review time)
- **Started:** 2026-07-22T03:02:15Z
- **Completed:** 2026-07-22T03:18:52Z
- **Tasks:** 4
- **Files modified:** 15

## Gate Signals

- **Gate A2 (Task 02-01-01):** Human approved exactly two new direct declarations — `httpx==0.28.1` (encode org) and `openai==2.46.0` (OpenAI official, superseding the STACK.md 2.45.x baseline by one minor line) — plus four explicit non-additions (no tiktoken, no GitHub SDK, no tenacity, no VCR). No lock resolution, download, or execution occurred before approval.
- **Gate B2 (Task 02-01-03):** Human approved all 11 new locked registry-only nodes/artifacts (httpx 0.28.1, openai 2.46.0, anyio 4.14.2, certifi 2026.6.17, distro 1.9.0, h11 0.16.0, httpcore 1.0.9, idna 3.18, jiter 0.16.0, sniffio 1.3.1, tqdm 4.69.0 — all from https://pypi.org/simple, hash-pinned) and the exact `uv.lock` bytes at **SHA-256 `a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216`**. Task 02-01-04 re-verified this hash before the first command ran; it matched, and the post-approval `uv run --locked` sync was the only installation event.

## Accomplishments

- Approved supply chain: exactly three sorted exact pins in `pyproject.toml` (`httpx==0.28.1`, `openai==2.46.0`, `pydantic==2.13.4`); lock graph contains only approved registry-only nodes; `uv lock --check` exit 0; lock hash unchanged after the full run.
- Frozen `domain/subjects.py` + `adapters/subjects.py`: strict subject_id/URL/ref validation with owner-name cross-check and a bounded single-descriptor loader mapping symlink, non-regular, missing, oversized, malformed, schema-invalid and mid-read-changed inputs to the single closed non-echoing `INVALID_SUBJECT` code.
- Frozen `domain/filtering.py` (filter-policy-v1): closed ordered eight-rule set, exact `{MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause}` allowlist, per-rule versioned `RuleDecision` records with closed rationales, deterministic failure on null/NOASSERTION/non-listed/multiple/mismatched licenses.
- Frozen `domain/reading.py` (reader-policy-v1): five READ-03 budgets plus 24k soft target, organization-ceiling rejection, fixed README → docs/ → examples/ → manifests → source tier order, hostile-path rejection predicates, ceil(bytes/4) token estimation.
- Frozen `domain/extraction.py`: extractor-response-v1 satisfying Structured Outputs shape (object root, `additionalProperties: false`, all-required with null-unions, workflows maxItems 3, no tools field), full EXTR-03 workflow-spec-v1 field list, skillscout-owned `wf-fingerprint-v1` (stable under case/whitespace/punctuation, sensitive to semantic and step-order change), and deterministic boundary validation dropping unknown paths, blob mismatches, non-verbatim/over-length excerpts and URL/shell/secret-shaped text.
- Additive Phase 1 members (`RunStatus.COMPLETED`, `ErrorCode.INVALID_SUBJECT`, `("2","phase2-v1")`) with exactly the three sanctioned Phase 1 test amendments; every other Phase 1 test byte-for-byte unchanged and green.

## Task Commits

Each task was committed atomically:

1. **Task 02-01-01: Gate A2 — approve exactly two new direct dependency declarations** — human-approved, no commit (gate record)
2. **Task 02-01-02: Apply the two pins, rediscover the lock non-building, land frozen contracts** — `b9f9971` (feat)
3. **Task 02-01-03: Gate B2 — approve every new locked distribution and exact lock bytes** — human-approved, no commit (gate record)
4. **Task 02-01-04: Execute contract suite and full regression under the approved graph** — `829f0ee`, `ecb69aa` (fix; see Deviations)

**Plan metadata:** recorded below (docs: complete plan)

## Files Created/Modified

- `pyproject.toml` — exactly three sorted exact runtime pins admitted through the two-gate ceremony
- `uv.lock` — non-building/no-source/no-cache discovered graph; Gate-B2-approved exact bytes
- `src/skillscout/domain/subjects.py` — `RepositorySubject` run-authority contract (`SubjectId`, `RepositoryUrl`, `SubjectRef`)
- `src/skillscout/adapters/subjects.py` — bounded single-descriptor `load_subject` (`MAX_SUBJECT_BYTES = 65_536`)
- `src/skillscout/domain/filtering.py` — filter-policy-v1 closed rules and pure `evaluate_filter`
- `src/skillscout/domain/reading.py` — reader-policy-v1 budgets, tiers, allowlists and path predicates
- `src/skillscout/domain/extraction.py` — extractor-response-v1, workflow-spec-v1, fingerprint and boundary validation
- `src/skillscout/domain/enums.py` — additive `RunStatus.COMPLETED` (terminal)
- `src/skillscout/domain/models.py` — additive `("2","phase2-v1")` registry member
- `src/skillscout/application/ports.py` — additive `ErrorCode.INVALID_SUBJECT` with fixed bounded summary
- `tests/test_phase2_contracts.py` — 52-test pure contract suite (this plan's evidence authority)
- `tests/fixtures/subject/approved.json` — one approved subject fixture
- `tests/test_stage_contracts.py`, `tests/test_phase1_gap_closure.py` — the three sanctioned additive amendments
- `tools/verify_phase1_gap_evidence.py` — `LOCK_HASH` re-anchored to the Gate-B2-approved bytes (deviation 2)

## Decisions Made

- Gate A2 approved exactly `httpx==0.28.1` and `openai==2.46.0` with both publishers reviewed and four explicit non-additions; Gate B2 approved every new registry-only node/artifact and the exact lock hash. Any later `uv.lock` byte change invalidates Gate B2.
- Re-anchored the Phase 1 evidence verifier's `LOCK_HASH` constant to the Gate-B2-approved hash (deviation 2): the constant exists to bind evidence authority to the human-approved lock bytes, so after Gate B2 the approved value is the only correct anchor. The verifier still fails closed on any unapproved byte change; the previously recorded Phase 1 evidence is stale by design (see Issues).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Contract cap assertion used list inputs against the strict tuple contract**
- **Found during:** Task 02-01-04 (focused suite first run: 1 failed, 228 passed)
- **Issue:** `test_extractor_response_caps_workflows_at_three` passed Python lists for `workflows`, but `StrictFrozenModel` sets `strict=True`, under which Pydantic rejects list input for tuple fields (`model_validate_json` accepts JSON arrays; the test file's own `_workflow_values` helper uses tuples everywhere else).
- **Fix:** Changed the three list inputs to tuples (`()`, `tuple(...)`), preserving the test's intent — the 0/3-accept and 4-reject cap boundary. The reviewed strict model was left untouched; real JSON output validates via `model_validate_json`.
- **Files modified:** `tests/test_phase2_contracts.py`
- **Verification:** Focused suite 229 passed; full suite 473 passed.
- **Committed in:** `829f0ee`

**2. [Rule 3 - Blocker] Phase 1 evidence verifier rejected the Gate-B2-approved lock bytes**
- **Found during:** Task 02-01-04 (full suite first run: 19 failed, all in `tests/test_phase1_evidence_verifier.py`)
- **Issue:** `tools/verify_phase1_gap_evidence.py:27` hardcoded the Phase 1 Gate B lock hash (`caeeddcf…`). The verifier test harness copies the real `uv.lock` into its temporary repository, so `_immutable_hashes` failed closed on the new — human-approved — bytes. The plan requires both the full suite green and Phase 1 tests byte-for-byte unchanged; the plan did not own this tool file, so this is a planning gap, not a contract failure.
- **Fix:** Re-anchored `LOCK_HASH` to exactly the Gate-B2-approved SHA-256 `a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216`. The value is uniquely determined by the human's approval record — no judgment call and no loosening: any deviation from the approved bytes still fails closed. No test file, no `src/skillscout` Phase 1 file, and no recorded evidence document was modified.
- **Files modified:** `tools/verify_phase1_gap_evidence.py`
- **Verification:** `tests/test_phase1_evidence_verifier.py` 24 passed; full suite 473 passed; Ruff clean on the tool; lock hash rechecked unchanged after the run.
- **Committed in:** `ecb69aa`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocker)
**Impact on plan:** Both fixes were forced by the plan's own verification block and stay inside the human-approved authority decisions. No scope creep; no Phase 1 behavior assertion weakened; no test loosened.

## Issues Encountered

- The recorded Phase 1 evidence document `.planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md` binds the superseded lock hash (`caeeddcf…`) in its immutable pre/post inputs, so `verify --rerun` against it now fails closed. This is the designed stale-by-design behavior for any bound-byte change (anticipated in `01-REVIEW.md` as the "next re-baselining plan" follow-up). Fresh evidence re-recording belongs to Phase 2 validation work and was not performed here; no evidence bytes were edited.

## User Setup Required

None - no external service configuration required.

## Verification Evidence (canonical `<verify>` chain, single clean pass)

- `uv run --locked pytest -q tests/test_phase2_contracts.py tests/test_stage_contracts.py tests/test_phase1_gap_closure.py tests/test_cli_security.py` — **229 passed** (includes the three-member registry test, the three-pin dependency assertion, and the two named-module capability carve-outs)
- `uv run --locked ruff check src/skillscout tests/test_phase2_contracts.py` — **All checks passed!**
- `uv run --locked pytest -q` — **473 passed**
- `uv lock --check` — **Resolved 24 packages, exit 0**
- Pre- and post-run `shasum -a 256 uv.lock` — **`a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216`** (Gate-B2-approved bytes, unchanged)

## Next Phase Readiness

- Plan 02-02 can build the live Scout/Filter adapters on the approved httpx graph and the frozen filter contract; Plans 02-03/02-04 inherit the reader/extraction contracts and the openai Structured Outputs shape.
- Follow-up for Phase 2 validation: re-record/re-baseline the authority-bound evidence against the Gate-B2 graph (the Phase 1 document is stale by design after the approved lock change).

## Self-Check: PASSED

- Key files exist on disk (all `key-files.created` verified during execution).
- `git log --oneline --grep="02-01"` returns the task commits (`b9f9971`, `829f0ee`, `ecb69aa`).
- Task 02-01-04 acceptance criteria re-run and passing: lock hash matched Gate B2 before the first command; focused suites, Ruff, full suite and `uv lock --check` all exit 0; registry/dependency/capability-sweep assertions pass; contract suite proves the subject/loader, filter, reading, extraction-schema, fingerprint and boundary matrices; no Phase 1 source or test changed beyond the sanctioned additive members and amendments (plus the disclosed verifier-anchor deviation).
- Plan-level `<verification>` commands re-run — results logged above.

---
*Phase: 02-safe-single-repository-extraction*
*Completed: 2026-07-22*
