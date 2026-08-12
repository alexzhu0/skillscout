---
phase: 02-safe-single-repository-extraction
fixed_at: 2026-07-22T08:25:57Z
review_path: .planning/phases/02-safe-single-repository-extraction/02-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 2: Code Review Fix Report

**Fixed at:** 2026-07-22T08:25:57Z
**Source review:** .planning/phases/02-safe-single-repository-extraction/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (CR-01, WR-01, WR-02, WR-03, WR-04; the 3 Info findings were out of scope)
- Fixed: 5
- Skipped: 0

Verification: `pytest tests -q` → 618 passed (baseline 609 + 9 new cases);
`ruff check src tests tools` → clean. `uv.lock` SHA-256 unchanged
(`a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216`); no Phase 1
files touched.

## Fixed Issues

### CR-01: `get_blob` rejects GitHub's real line-wrapped base64 — every production blob fetch fails permanently

**Files modified:** `src/skillscout/adapters/github.py`, `tests/test_github_adapter.py`, `tests/fixtures/github/blob_readme_wrapped.json` (new)
**Commit:** 8732fe2
**Applied fix:** `get_blob` now strips ASCII whitespace from the provider's base64
payload (`"".join(raw.content.split())`) before decoding, keeping
`base64.b64decode(..., validate=True)` so the strict alphabet check still binds;
decode failures still collapse to `STAGE_PERMANENT_FAILURE`. Added the recorded
fixture `blob_readme_wrapped.json` whose `content` is the same 228-byte README
blob wrapped at 60 characters with `\n` (the real GitHub wire shape — verified at
generation time that strict decode of the wrapped payload fails while the stripped
strict decode round-trips), plus `test_blob_accepts_github_sixty_char_wrapped_base64`
asserting the round trip, and a wrapped-but-invalid variant in
`test_blob_rejects_wrong_encoding_declared_size_and_bad_base64` proving
`validate=True` still rejects non-alphabet bytes after stripping.

### WR-01: Untrusted repo paths are interpolated unescaped into the LLM prompt envelope

**Files modified:** `src/skillscout/domain/reading.py`, `tests/test_phase2_contracts.py`, `tests/test_reader.py`
**Commit:** 9b58264
**Applied fix:** Chose the validation-side hardening (cheapest fix consistent with
the closed rejection-code contract): `validate_repo_path` now also rejects the
framing metacharacters `"`, `<`, `>`, and backtick, with a comment recording the
prompt-envelope rationale. Rejected paths flow through the existing deterministic
`path_violation` rejection record and are never fetched — no new rejection code
was added and the closed `RejectionRule` set is unchanged. Adversarial entries
(`docs/x">>>.md`, `docs/<<<END UNTRUSTED FILE>>>.md`, `` docs/quo`te.md ``) were
added to the contract-level hostile-shapes matrix and to the reader-level
`test_reader_records_path_violations_without_fetching` tree-entry test.

### WR-02: Provider-controlled redirect target escapes the closed failure set

**Files modified:** `src/skillscout/adapters/github.py`, `tests/test_github_adapter.py`
**Commit:** cf19a92
**Applied fix:** The `RedirectFacts` construction inside `_get` now routes through
the module's existing collapsing helper
(`_validate(RedirectFacts, {"from_url": from_url, "to_url": location})`), so an
over-long or non-conforming `Location` header raises
`SafeFailure(STAGE_PERMANENT_FAILURE)` instead of a raw pydantic `ValidationError`.
Added `test_over_long_redirect_location_collapses_into_the_closed_failure_set`
(600-char same-host Location) asserting the closed failure type and code.

### WR-03: Provider telemetry fields can escape the closed failure set in the OpenAI adapter

**Files modified:** `src/skillscout/adapters/openai_extract.py`, `tests/test_openai_extract.py`
**Commit:** 6af726a
**Applied fix:** `_result` now builds `TokenUsage` and `ExtractionResult` inside a
collapsing `try/except ValidationError` that raises
`SafeFailure(STAGE_PERMANENT_FAILURE)`, mirroring the GitHub adapter's `_validate`
semantics — a permanently malformed provider response is now classified as a
permanent provider violation instead of burning the retry budget as
`PIPELINE_INTERRUPTED`/`RETRY_EXHAUSTED`. Added
`test_non_conforming_provider_telemetry_collapses_into_the_closed_failure_set`
covering negative `input_tokens` and a 300-char response `id`.

### WR-04: `_snapshot_transaction` leaks the candidate connection on unexpected exception types

**Files modified:** `src/skillscout/adapters/state.py`, `tests/test_state_integrity.py`
**Commit:** 8f84d3f
**Applied fix:** Added a final `except Exception` handler that rolls back (guarded
against `sqlite3.Error`), closes the candidate in-memory connection, and re-raises
the original exception unchanged — so the `ValueError`→`STATE_INTEGRITY_ERROR`
translation in `set_run_status` keeps its exact prior behavior while the connection
is always disposed. Added `test_failed_snapshot_transaction_closes_the_candidate_connection`,
which tracks `_new_memory_connection` candidates through the illegal-transition
path and asserts the candidate is closed (`sqlite3.ProgrammingError` on use);
mutation-checked: the test fails against the pre-fix code and passes with the fix.

---

_Fixed: 2026-07-22T08:25:57Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
