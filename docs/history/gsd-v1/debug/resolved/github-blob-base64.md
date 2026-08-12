---
status: resolved
trigger: "Live GitHub blob content uses CR/LF-folded base64, but StateBranchClient.get_blob passes it directly to strict base64 decoding."
created: 2026-07-28
updated: 2026-07-27T17:40:43Z
---

# Debug Session: GitHub Blob Base64

## Symptoms

- expected: StateBranchClient accepts GitHub REST blob `content` encoded as canonical base64 with CR/LF line folding, then retains decoded-size and git-blob-ID verification.
- actual: `base64.b64decode(..., validate=True)` rejects live GitHub blob content containing line breaks, so write-after-read verification fails.
- errors: State branch bootstrap created remote commit `449aed6599f3487e34a34751a893be2d984fa95c`, but no success receipt was produced because read-back blob decoding failed.
- timeline: Reproduced during live state-branch bootstrap on 2026-07-28.
- reproduction: Feed a GitHub REST blob response whose canonical base64 `content` is folded with CR/LF into `StateBranchClient.get_blob`.

## Current Focus

hypothesis: `StateBranchClient.get_blob` rejects the live response solely because it passes CR/LF-folded canonical base64 directly to `b64decode(validate=True)`; accepting only after CR/LF removal plus canonical re-encoding will preserve every existing integrity check without widening the wire grammar.
test: Focused and full locked verification plus configured Ruff checks completed successfully.
expecting: Canonical and CR/LF-folded canonical payloads decode; spaces, tabs, controls, invalid padding, noncanonical pad bits, size mismatch, and git-blob-ID mismatch remain closed failures.
next_action: Archive this resolved session and append the confirmed pattern to the debug knowledge base.

reasoning_checkpoint:
  hypothesis: "`StateBranchClient.get_blob` fails because strict decoding sees GitHub's CR/LF fold characters before normalization; removing only CR/LF and requiring decode/re-encode equality accepts the one valid wire variant while rejecting broader whitespace and noncanonical pad-bit encodings."
  confirming_evidence:
    - "The exact adapter returns the byte for `/w==` but raises `SafeFailure(stage_permanent_failure)` for `/w==\\r\\n` with identical declared size and requested git blob ID."
    - "Python 3.13 `b64decode(validate=True)` rejects CR/LF, spaces, tabs, NUL, missing padding, and excess padding, but accepts `/x==` and `Zm9=` even though both re-encode differently."
  falsification_test: "The hypothesis is false if CR/LF-only normalization plus canonical re-encoding equality either still rejects a folded canonical payload or accepts any whitespace/control, padding, pad-bit, size, or blob-ID mutation."
  fix_rationale: "Normalization removes exactly the provider's permitted transport folding; strict decoding constrains the residual alphabet/padding; re-encoding equality enforces canonical pad bits; the existing size and git-blob-ID checks remain unchanged."
  blind_spots: "The local suite cannot prove every live GitHub line-wrap position, so tests include folds at multiple positions and both CR and LF while the implementation position-independently removes only those two characters."

## Evidence

- timestamp: 2026-07-27T17:34:51Z
  checked: `.planning/debug/knowledge-base.md`
  found: No prior entry overlaps the blob-content/base64-folding symptom by two or more error-pattern keywords.
  implication: No known-pattern shortcut applies; test the persisted encoding-contract hypothesis directly.

- timestamp: 2026-07-27T17:34:51Z
  checked: `StateBranchClient.get_blob` and existing state-branch tests
  found: The adapter calls `base64.b64decode(raw["content"], validate=True)` without normalization, then verifies decoded size and the requested git blob ID; `tests/test_state_branch.py` has no HTTP blob-content grammar tests.
  implication: CR/LF fails before the strong size/blob-ID checks, and the missing mutation contract allowed the live representation mismatch.

- timestamp: 2026-07-27T17:36:30Z
  checked: Direct `StateBranchClient.get_blob` reproduction with one-byte content, exact declared size, and exact git blob ID
  found: Canonical `/w==` returned `b'\\xff'`; the sole mutation `/w==\\r\\n` raised closed `stage_permanent_failure`.
  implication: The CR/LF handling order is the causal divergence point, independent of size or blob identity.

- timestamp: 2026-07-27T17:36:30Z
  checked: Python 3.13 strict base64 behavior across single-variable wire mutations
  found: `validate=True` rejected CR/LF, space, tab, NUL, missing padding, and excess padding, but decoded noncanonical `/x==` to the same byte as canonical `/w==` and `Zm9=` to the same bytes as canonical `Zm8=`.
  implication: The minimal safe fix requires both CR/LF-only normalization and canonical encode-after-decode equality; strict decoding alone does not enforce canonical pad bits.

- timestamp: 2026-07-27T17:38:01Z
  checked: Locked focused command `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_branch.py`
  found: 54 tests passed, including canonical and CR/LF-folded acceptance plus whitespace, control, padding, noncanonical pad-bit, size, and git-blob-ID mutations.
  implication: The original adapter path now accepts the live wire representation and the adjacent fail-closed boundary remains intact.

- timestamp: 2026-07-27T17:39:12Z
  checked: Locked full command `.tools/uv-0.11.29/bin/uv run --locked pytest -q`
  found: 1773 tests passed and 2 tests skipped in 39.88 seconds.
  implication: The minimal decoder change introduces no detected regression across the complete repository suite.

- timestamp: 2026-07-27T17:39:30Z
  checked: Scoped source/test diff, complete working-tree status, and `git diff --check`
  found: The implementation is a five-line bounded decoder change; tests are isolated to `tests/test_state_branch.py`; no unrelated tracked worktree changes exist; whitespace validation passed.
  implication: The requested implementation and mutation contract can be committed atomically without absorbing unrelated files or the debug artifact.

- timestamp: 2026-07-27T17:39:57Z
  checked: Locked configured command `.tools/uv-0.11.29/bin/uv run --locked ruff check src tests tools`
  found: All Ruff checks passed.
  implication: The decoder and test additions satisfy the repository's configured static style and lint policy.

- timestamp: 2026-07-27T17:40:43Z
  checked: Atomic implementation commit `535e5d33cd8438eb86d2277f57ff8335e7a94ad5`
  found: The commit contains exactly `src/skillscout/adapters/state_branch.py` and `tests/test_state_branch.py` with 125 insertions and 2 deletions.
  implication: The verified fix and its mutation contract are recorded together without the debug artifact or unrelated worktree content.

## Eliminated

## Resolution

- root_cause: `StateBranchClient.get_blob` applied Python's strict base64 decoder directly to GitHub's CR/LF-folded wire value, so valid live blobs failed before integrity verification; additionally, the decoder alone does not reject noncanonical pad-bit spellings, requiring explicit canonical re-encoding equality after narrow normalization.
- fix: Remove only `\r` and `\n` from the GitHub wire value before `b64decode(validate=True)`, require the decoded bytes to re-encode exactly to the normalized value, and retain decoded-size and requested git-blob-ID verification. Add adapter-level acceptance and negative mutation tests for the complete boundary.
- verification: Focused locked state-branch suite passed 54/54; full locked suite passed 1773 tests with 2 expected skips. The accepted cases cover canonical, LF-, CR-, and CRLF-folded wire values; rejection cases cover broader whitespace, other controls, malformed padding, noncanonical pad bits, size mismatch, and git-blob-ID mismatch.
- files_changed:
  - src/skillscout/adapters/state_branch.py
  - tests/test_state_branch.py
