---
phase: 01-auditable-dry-run-spine
reviewed: 2026-07-19T07:59:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - src/skillscout/__init__.py
  - src/skillscout/adapters/fixtures.py
  - src/skillscout/adapters/localfs.py
  - src/skillscout/adapters/state.py
  - src/skillscout/application/pipeline.py
  - src/skillscout/application/ports.py
  - src/skillscout/cli.py
  - src/skillscout/domain/canonical.py
  - src/skillscout/domain/enums.py
  - src/skillscout/domain/models.py
  - tests/conftest.py
  - tests/fixtures/pipeline/approved.json
  - tests/fixtures/state/v1-cli-provenance.json
  - tests/fixtures/state/v1-cli.db
  - tests/test_cli_dry_run.py
  - tests/test_cli_security.py
  - tests/test_phase1_gap_closure.py
  - tests/test_pipeline_resume.py
  - tests/test_side_effect_policy.py
  - tests/test_stage_contracts.py
  - tests/test_state_integrity.py
  - tools/verify_phase1_gap_evidence.py
findings:
  critical: 3
  warning: 4
  info: 0
  total: 7
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-07-19T07:59:00Z
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Narrative Findings (AI reviewer)

The current post-gap implementation was reviewed across the fixture boundary, snapshot-backed SQLite ledger, content-addressed manifests, resume logic, CLI diagnostics, and standalone evidence verifier. The checked-in suite passes (`200 passed`), Ruff passes, and the gap-evidence document validates, but those checks miss three release-blocking integrity/disclosure failures and four robustness gaps. Two critical failures were reproduced directly: a state mutation that raises `state_operation_failed` is present after reopen, and a tampered `reused_stage_count` is accepted and emitted by the full-chain verifier.

## Critical Issues

### CR-01: Backup-cleanup failure reports rollback while the new state is durably committed

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/localfs.py:310-314`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:2016-2037`

**Issue:** `atomic_write()` first makes the replacement durable, then unlinks the backup with a directory fsync. If that cleanup fsync fails, `unlink()` has already removed the backup and line 314 raises `DurableWriteError("backup_cleanup", renamed=True)` without restoring the prior target. `_snapshot_transaction()` treats this as a failed transaction, poisons the live connection, and returns `state_operation_failed`, even though the replacement snapshot remains on disk. A focused reproduction made `create_run("failed-call", ...)` raise `state_operation_failed`; reopening the database returned the supposedly failed `failed-call` row. Callers can retry after an error and create duplicate or contradictory audit state, so the API's success/failure boundary is false.

**Fix:** Separate replacement durability from best-effort backup retirement. Once the target file and containing directory are durably synced, commit the in-memory candidate and treat backup cleanup as recoverable housekeeping; alternatively retain the backup and record a deterministic recovery state. Do not return failure after a mutation is already authoritative unless reopen can unambiguously select and restore the old generation. Add a regression that injects failure specifically after backup unlink and asserts that the returned outcome matches the state observed after reopen.

### CR-02: Full-chain verification trusts an unattested `reused_stage_count`

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:1549-1555`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:1567-1570`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:1960-1982`

**Issue:** `verify_run_chain()` recomputes stage inputs, reusable digests, result identities, output hashes, and manifest hashes, but returns the run row without proving `reused_stage_count`. That field is a standalone mutable column, is not covered by a manifest or immutable resume event, and is projected as verified audit data by `inspect_run()`. Changing a fresh completed run from `reused_stage_count=0` to `9` in the persisted database still makes both `verify_run_chain()` and `inspect_run()` return `9`. This breaks the phase's claim that inspected audit facts are full-chain verified.

**Fix:** Persist an immutable, content-addressed resume event that records the selected checkpoint and reused prefix, and bind its digest into the run ledger; derive `reused_stage_count` from that verified event instead of trusting the mutable summary column. If the field remains denormalized, compare it with the verified event during `_verify_run_chain()` and reject any mismatch. Add tamper cases for every publicly projected run-level audit fact, including `reused_stage_count`.

### CR-03: `argparse` echoes raw hostile arguments outside the sanitized diagnostic boundary

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/cli.py:19-35`

**Issue:** `parse_args()` executes before the CLI's `try` block, and the default `ArgumentParser.error()` writes the rejected argument verbatim to stderr. For example, `--fail-after github_pat_DO_NOT_DISCLOSE` exits 2 while printing that complete canary. Unknown options similarly echo their raw values. This bypasses the closed `SafeFailure` vocabulary and violates the requirement that credentials and untrusted values never enter logs or diagnostics.

**Fix:** Use a parser subclass whose `error()`/`exit()` emits only a fixed bounded diagnostic (for example, a new allowlisted `invalid_cli_arguments` code) without including the offending token, or pre-validate argv through a non-echoing parser boundary. Preserve exit code 2 if desired, but add subprocess tests with credential and path canaries for invalid choices, unknown options, and missing values.

## Warnings

### WR-01: An unexpected processor exception permanently disables retry for that stage identity

**Classification:** WARNING
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/pipeline.py:311-318`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/pipeline.py:262-273`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/pipeline.py:426-433`

**Issue:** An arbitrary processor exception is translated to `PIPELINE_INTERRUPTED`, but `_close_started_attempt()` marks only `STAGE_TRANSIENT_FAILURE` retryable. The next invocation sees a non-retryable failed attempt through `has_permanent_failure()` and raises `STAGE_PERMANENT_FAILURE` without calling the processor again. A one-time internal exception was reproduced as `pipeline_interrupted` on the first run and `stage_permanent_failure` on the second, with the processor call count still one. This contradicts resumable failure behavior and the meaning of an interruption.

**Fix:** Classify unexpected exceptions consistently: either store them as an explicit permanent failure on the first run, or treat sanitized `PIPELINE_INTERRUPTED` as retryable under the finite retry budget. Add a fail-once-then-succeed resume test.

### WR-02: The standalone evidence verifier accepts stale or self-asserted command success

**Classification:** WARNING
**File:** `/Users/alexzhu/Lenovo/skillscout/tools/verify_phase1_gap_evidence.py:158-189`
**Related:** `/Users/alexzhu/Lenovo/skillscout/tools/verify_phase1_gap_evidence.py:192-228`

**Issue:** The verifier checks that the document claims fixed exit codes/counts and that node strings look like pytest IDs; it does not bind those claims to command output, the reviewed source/test bytes, or even the existence and contents of the named test functions. Only `uv.lock` and the frozen database are hashed. Consequently the unchanged evidence document remains valid after arbitrary product/test edits and can be constructed with the expected success literals without running a command. This is a false-positive quality gate, not independent verification of the claimed full suite.

**Fix:** Bind evidence to an immutable repository tree or an explicit digest set covering production and test files, include digests of captured command outputs, and have the verifier resolve every named node against the bound test sources. Prefer generating and validating the evidence in the same CI job that executes the commands, with the commit/tree identity recorded.

### WR-03: A valid state filename can collide with its derived manifest directory

**Classification:** WARNING
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:456-459`

**Issue:** `self.manifest_root = self.path.with_suffix(".manifests")` equals `self.path` whenever the operator selects a state file already ending in `.manifests`. The database is created successfully, but the first stage then tries to open that regular file as the manifest directory and fails with `state_integrity_error`, leaving an interrupted run. The CLI accepts this filename and provides no early validation.

**Fix:** Derive a disjoint sibling name (for example, append `.manifests` to the complete database filename) or explicitly reject any path where `manifest_root == path` before creating state. Add a CLI regression for `.manifests`-suffixed state names.

### WR-04: Existing state snapshots are accepted without private ownership or mode checks

**Classification:** WARNING
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/localfs.py:227-241`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:479-484`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:92-98`

**Issue:** New snapshots and the lock use mode `0600`, and the lock is checked with `stat_is_private_regular()`, but `read_bytes()` validates only regular-file type, symlink status, and size. A pre-existing state database owned by another user or writable by group/other is accepted as authoritative when its parent is owner-controlled but traversable (for example, mode `0755`). This weakens the local tamper boundary and makes run-level metadata forgery materially easier.

**Fix:** Before deserializing state, require owner identity, link/type expectations, and no group/other permission bits, matching the lock policy. Apply an equivalent check to existing manifest files before treating them as immutable evidence. Reject violations with the fixed state-integrity diagnostic and add mode/ownership regression tests.

---

_Reviewed: 2026-07-19T07:59:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
