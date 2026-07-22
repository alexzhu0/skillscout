---
phase: 02-safe-single-repository-extraction
plan: "03"
subsystem: security
tags: [reader, budgets, rejection-matrix, hydration, mock-transport, recorded-fixtures, no-execution, content-hash]

# Dependency graph
requires:
  - phase: 02-safe-single-repository-extraction plan 02-02
    provides: PhaseTwoProcessor with reader slot behind the fail-closed guard, GitHubReadClient.get_blob with tree-declared size re-check, recorded-transport harness, skip cascade
provides:
  - _reader stage handler: fixed README → docs → examples → manifests → source order with in-tier path sorting, five reader-policy-v1 budgets gated before fetch, early stop, complete structured read record, runtime-only scratch read_bundle
  - Full READ-05 rejection matrix with recorded {path, rule, observed} entries and never-fetched/exactly-one-fetch discipline
  - hydrate_read_bundle: read_order re-fetch with binary/LFS re-checks and exact sha256 content-hash equality, failing closed on any deviation
  - Programmatic fixture builders (make_tree_fixture, make_blob_fixture, make_blob_entry, git_blob_id) beside the reviewed JSON recordings
affects: [02-safe-single-repository-extraction plan 02-04, phase 3+]

# Tech tracking
tech-stack:
  added: []
  patterns: [size-before-fetch under validated policy defaults with a pure budget-gate predicate, fetched-then-rejected content classification (UTF-8 decode, NUL sniff, LFS prefix), memory-only raw bundle with hash-verified hydration, observed-value rejection records in filter key=value style]

key-files:
  created: [tests/test_reader.py, tests/fixtures/github/blob_doc.json, tests/fixtures/github/blob_example.json, tests/fixtures/github/blob_pyproject.json, tests/fixtures/github/blob_source.json, tests/fixtures/github/blob_lfs.json, tests/fixtures/github/blob_binary.json]
  modified: [src/skillscout/application/processors.py, tests/recorded_transport.py, tests/test_scout_filter.py]

key-decisions:
  - "The max_total_bytes gate is arithmetically shadowed by the 40000-token estimate gate under the organization ceilings (40000 tokens ≡ 160000 bytes < 524288 bytes); its ±1 boundary is proven on the pure _read_budget_stop predicate with a lowered ReaderPolicy while handler-level tests prove the four reachable gates at the real defaults."
  - "Reader telemetry request_id is populated only when the stage fetched at least one blob, so a zero-fetch run never inherits a stale X-GitHub-Request-Id from a prior stage's last response."

patterns-established:
  - "Size-before-fetch: the tree-declared size gates every blob GET, and get_blob re-checks the fetched byte length before any decode."
  - "Fetched-then-rejected classification: UTF-8 decode failure or NUL sniff → binary_content, LFS pointer prefix → lfs_pointer, each recorded with exactly one fetch."
  - "Memory-only bundle with hash-verified hydration: raw text lives only in context.scratch['read_bundle']; resume rebuilds it byte-for-byte or fails closed."

requirements-completed: [READ-02, READ-03, READ-04, READ-05, READ-06]

coverage:
  - id: D1
    description: "Deterministic tiered reading: exact README → docs → examples → manifests → source read_order with path-sorted entries inside each tier, proven across the recorded tree_full and synthetic budget trees; complete read record (schema facts, policy_version, ordered files with blob_sha/size/content_hash/read_order, rejections, budgets, source_code_loaded, closed stop_reason)"
    requirement: READ-02
    verification:
      - kind: unit
        ref: "tests/test_reader.py#test_reader_reads_in_exact_tier_order_with_sorted_paths"
        status: pass
    human_judgment: false
  - id: D2
    description: "Five reader-policy-v1 budgets hold at ±1 boundaries with defaults-only policy construction: 25th file read / 26th stopped, 5th source file read / 6th stopped, 131072-byte file read / 131073-byte skipped unfetched, token gate read at exactly 40000 / stopped at 40001, and the total-bytes gate proven on the pure predicate; recorded transport call counts prove count-overflow and over-size candidates were never fetched"
    requirement: READ-03
    verification:
      - kind: unit
        ref: "tests/test_reader.py#test_budget_gate_boundaries_are_exact_with_a_lowered_policy, test_default_policy_gate_reflects_the_organization_ceilings, test_reader_stops_at_max_files_before_the_26th_fetch, test_reader_stops_at_max_source_files_before_the_6th_fetch, test_reader_reads_max_file_bytes_exactly_and_never_fetches_one_byte_over, test_reader_stops_before_estimated_tokens_exceed_the_budget"
        status: pass
    human_judgment: false
  - id: D3
    description: "Early stop fires SOFT_TARGET_REACHED only after the examples tier; draining yields CANDIDATES_EXHAUSTED; an all-rejected set yields NO_ALLOWLISTED_FILES with zero blob GETs; the raw bundle lives only in scratch and the README canary appears in no payload, manifest or SQLite bytes while MAX_STAGE_STRING_BYTES/MAX_MANIFEST_BYTES bounds hold"
    requirement: READ-04
    verification:
      - kind: unit
        ref: "tests/test_reader.py#test_reader_early_stop_fires_only_after_the_examples_tier, test_reader_no_allowlisted_files_stops_without_any_fetch, test_reader_surfaces_carry_no_full_text_canary"
        status: pass
    human_judgment: false
  - id: D4
    description: "Complete READ-05 rejection matrix with {path, rule, observed} records: submodule 160000, symlink 120000, six path-violation shapes (.., empty segment, backslash, NUL, 513 chars, depth 9), non-allowlisted extensions including archives, and over-size files are never fetched; binary and LFS-pointer content are rejected after exactly one fetch each"
    requirement: READ-05
    verification:
      - kind: unit
        ref: "tests/test_reader.py#test_reader_records_submodule_and_symlink_without_fetching, test_reader_records_path_violations_without_fetching, test_reader_records_non_allowlisted_extensions_without_fetching, test_reader_rejects_binary_content_after_exactly_one_fetch, test_reader_rejects_lfs_pointer_after_exactly_one_fetch"
        status: pass
    human_judgment: false
  - id: D5
    description: "No candidate code is cloned, installed, imported, built or executed: the amended Phase 1 capability sweep keeps subprocess/importlib/socket/urllib/requests/aiohttp/github/http/eval/exec/os.popen/os.system banned in every source module, and a complete reader run under the outbound socket sentinel performs only recorded MockTransport HTTP"
    requirement: READ-06
    verification:
      - kind: unit
        ref: "tests/test_reader.py#test_reader_run_performs_only_recorded_mock_transport_http; tests/test_phase1_gap_closure.py#test_production_capability_surface_remains_local_only"
        status: pass
    human_judgment: false
  - id: D6
    description: "Resume hydration is byte-verified: hydrate_read_bundle reproduces the scratch bundle exactly, issues exactly one blob GET per recorded file and zero metadata/commits/tree/license calls, and fails closed with stage_permanent_failure on tampered bytes or new binary/LFS rejections"
    verification:
      - kind: unit
        ref: "tests/test_reader.py#test_hydrate_read_bundle_reproduces_the_scratch_bundle_byte_for_byte, test_hydrate_read_bundle_fails_closed_on_tampered_bytes, test_hydrate_read_bundle_fails_closed_on_a_new_content_rejection"
        status: pass
    human_judgment: false

# Metrics
duration: 43min
completed: 2026-07-22
status: complete
---

# Phase 02 Plan 03: Safe Single-Repository Extraction — Budgeted Tiered Reader Summary

**Budgeted tiered Reader with the complete READ-05 rejection matrix, early stop, a fully structured read record, a memory-only raw bundle, and hash-verified resume hydration — proven by 24 new tests over recorded fixtures with the full 560-test suite green and no Phase 1 file touched.**

## Performance

- **Duration:** 43 min
- **Started:** 2026-07-22T04:57:36Z
- **Completed:** 2026-07-22T05:40:19Z
- **Tasks:** 2
- **Files modified:** 10 (1 source module, 2 test modules amended, 1 test module created, 6 recorded fixture files)

## Accomplishments

- `_reader` handler in `src/skillscout/application/processors.py`: reads the Scout candidate projection from `context.prior_payloads`, constructs the default `ReaderPolicy()` (reader-policy-v1, ceiling-validated, never per-run input), classifies every candidate in the exact precedence path → submodule → symlink → extension → size, sorts survivors by (tier order, path), and fetches only under all five budgets with `BUDGET_EXHAUSTED`, `SOFT_TARGET_REACHED` (examples tier or later at 24000 estimated tokens), `CANDIDATES_EXHAUSTED` or `NO_ALLOWLISTED_FILES` closed stop reasons.
- Structured read record: ordered `files[]` (path, tier, blob_sha, size, sha256 content_hash, read_order), `rejections[]` (path, rule, observed), budget consumption (files_read, source_files_read, total_bytes, estimated_input_tokens), `source_code_loaded`, `stop_reason`; telemetry carries policy_version, the last blob `X-GitHub-Request-Id` (only when the stage actually fetched) and measured latency. Raw text lives only in `context.scratch["read_bundle"]`.
- Full READ-05 matrix with fetch discipline: metadata-sufficient rejections (submodule 160000, symlink 120000, six hostile path shapes, non-allowlisted extensions including `assets/pack.zip`, 131073-byte and 200000-byte over-size) issue zero blob GETs; binary (UTF-8 decode failure / NUL sniff) and LFS-pointer content are rejected after exactly one fetch each.
- `hydrate_read_bundle(github_client, owner, repo, files)`: re-fetches the recorded plan in read_order, re-runs the binary/LFS checks, requires exact sha256 content-hash equality, and maps any mismatch, decode failure or new rejection to `SafeFailure(STAGE_PERMANENT_FAILURE) from None`; proven byte-identical to the scratch bundle with blob-only traffic.
- Test infrastructure: `make_tree_fixture`/`make_blob_fixture`/`make_blob_entry`/`git_blob_id` builders in `tests/recorded_transport.py`; six recorded blobs (`blob_doc`, `blob_example`, `blob_pyproject`, `blob_source` consistent with tree_full sizes/SHAs; `blob_lfs`, `blob_binary` rejection content); `tests/test_reader.py` with 18 test functions / 24 cases covering order, budgets, early stop, the matrix, hydration, canary non-persistence and the socket-sentinel runtime proof.

## Task Commits

Each task was committed atomically (TDD: failing test, then implementation):

1. **Task 02-03-01: Tiered budgeted read loop with early stop and the structured read record** — `148e6ef` (test), `c4a2566` (feat)
2. **Task 02-03-02: Full rejection matrix, hash-verified resume hydration and no-execution proof** — `d081f98` (test), `4fd818f` (feat)

**Plan metadata:** recorded below (docs: complete plan)

## Files Created/Modified

- `src/skillscout/application/processors.py` — `_reader` handler, `_read_budget_stop` pure gate predicate, `_classify_blob_content`, `_rejection`, `hydrate_read_bundle`; READER dispatch added behind the existing skip cascade
- `tests/recorded_transport.py` — programmatic `make_tree_fixture`/`make_blob_fixture`/`make_blob_entry`/`git_blob_id` builders
- `tests/test_reader.py` — 24 reader cases (order/record, five budgets ±1, early stop, rejection matrix, hydration, canary sweep, socket sentinel)
- `tests/test_scout_filter.py` — two guard tests amended for the now-implemented reader (see Deviations)
- `tests/fixtures/github/blob_doc.json` — recorded 800-byte `docs/guide.md` blob
- `tests/fixtures/github/blob_example.json` — recorded 400-byte `examples/basic.md` blob
- `tests/fixtures/github/blob_pyproject.json` — recorded 600-byte `pyproject.toml` blob
- `tests/fixtures/github/blob_source.json` — recorded 2000-byte `src/core.py` blob
- `tests/fixtures/github/blob_lfs.json` — recorded LFS-pointer rejection blob
- `tests/fixtures/github/blob_binary.json` — recorded binary (NUL + invalid UTF-8) rejection blob

## Decisions Made

- **Total-bytes gate proof strategy.** Under the organization ceilings the 40000-token estimate gate (≡ 160000 bytes at ceil(bytes/4)) always binds before the 524288-byte total gate, so the total gate is unreachable through the handler with any valid policy. The continuation decision is factored into the pure module-level `_read_budget_stop` predicate: its ±1 boundaries are proven directly with a lowered `ReaderPolicy` (lowering is ceiling-legal), while handler-level tests prove the four reachable gates at the real defaults and a defaults-policy predicate test documents the shadowing explicitly.
- **Telemetry request_id gating.** The reader records `X-GitHub-Request-Id` in telemetry only when it fetched at least one blob; a zero-fetch run (e.g., `no_allowlisted_files`) would otherwise inherit a stale id from the filter stage's license response, misattributing telemetry across stages.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] Plan's `files_modified` omitted `tests/test_scout_filter.py`, whose guard tests the reader implementation necessarily breaks**
- **Found during:** Task 02-03-01 (GREEN run preparation)
- **Issue:** `test_unhandled_stages_fail_closed` asserted READER fails closed, and `test_accepted_run_fails_closed_at_the_not_yet_implemented_reader` asserted the reader stage attempt FAILED; an implemented reader invalidates both, while the plan's own verification requires the full suite green.
- **Fix:** Amended the two tests minimally: the fail-closed guard now targets the not-yet-implemented EXTRACTOR (QUALIFIER unchanged), and the runner test was renamed to `..._extractor` with the seven reader blob routes added and the reader attempt asserted SUCCEEDED. No assertion about Scout/Filter behavior was weakened.
- **Files modified:** `tests/test_scout_filter.py`
- **Verification:** Full suite 560 passed.
- **Committed in:** `c4a2566` (part of the Task 02-03-01 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocker)
**Impact on plan:** Test-amendment only, forced by the plan's verification block; no production behavior changed beyond what the plan specifies. No scope creep.

## Issues Encountered

- RED commits fail at collection with ImportError on the new names (`_read_budget_stop`, `hydrate_read_bundle`) — the documented RED shape for brand-new APIs (same as Plan 02-02); GREEN commits resolve them and the test→feat gate order is preserved per task.
- Two test-authoring corrections during the Task 02-03-01 GREEN loop (normal TDD iteration, fixed before the GREEN commit): the path-sorted source order is `lib/helper.py, script.py, src/core.py` (initial expectation had the last two swapped), and the lowered-policy gate test needed the token budget isolated in a second policy so it could not shadow the 1000-byte total boundary.

## Authentication Gates

None — the suite runs entirely on `httpx.MockTransport` with zero network access and zero credentials.

## User Setup Required

None - no external service configuration required.

## Verification Evidence (canonical `<verify>` chain, single clean pass)

- `uv run --locked pytest -q tests/test_reader.py tests/test_phase1_gap_closure.py` — **35 passed**
- `uv run --locked ruff check src/skillscout/application/processors.py tests/test_reader.py` — **All checks passed!**
- `uv run --locked pytest -q` — **560 passed** (536 plan-02-02 baseline + 24 new reader cases)
- `git diff --stat 054beab..HEAD -- <all Phase 1 source and test files>` — **0 lines changed**
- Pre- and post-run `shasum -a 256 uv.lock` — **`a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216`** (Gate-B2-approved bytes, unchanged; no dependency changes in this plan)
- Recorded-transport evidence: rejected candidates with metadata-sufficient rules show zero blob GETs; binary/LFS rejections show exactly one; hydration traffic is blob-only with one GET per recorded file.

## Next Phase Readiness

- Plan 02-04 (Extractor + CLI) builds directly on: the reader payload's bounded `files[]`/`rejections[]` record, the `context.scratch["read_bundle"]` runtime handoff (and `hydrate_read_bundle` for resume re-execution), the telemetry seam (`policy_version` already flowing for reader), and the fail-closed EXTRACTOR guard slot in `PhaseTwoProcessor`.
- The LLM-call-count-0 proof after filter rejection can now be demonstrated end-to-end: rejected runs skip READER/EXTRACTOR with zero adapter calls (Plan 02-02 cascade) and accepted runs reach the extractor with a bounded, hash-recorded bundle.

## Self-Check: PASSED

- Key files exist on disk (all `key-files.created` verified during execution; fixtures validated for exact size/SHA consistency with `tree_full.json`).
- `git log --oneline --grep="02-03"` returns four commits (`148e6ef`, `c4a2566`, `d081f98`, `4fd818f`) — RED before GREEN per TDD task.
- Task acceptance criteria re-run and passing: exact read_order across all five tiers with in-tier path sorting; all five ±1 budget cases with never-fetched proofs for the 131073-byte and count-overflow candidates; early stop only after the examples tier; `CANDIDATES_EXHAUSTED` on drain and `NO_ALLOWLISTED_FILES` with zero GETs on all-rejected input; complete read-record fields; the README canary absent from payload, manifests and SQLite bytes with the raw bundle only in scratch; every READ-05 class with rule/observed and fetch discipline; hydration byte-equality, tamper fail-closed and blob-only traffic; capability sweep and socket-sentinel proofs green.
- Plan-level `<verification>` commands re-run — results logged above.

---
*Phase: 02-safe-single-repository-extraction*
*Completed: 2026-07-22*
