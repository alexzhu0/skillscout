---
phase: 01-auditable-dry-run-spine
reviewed: 2026-07-19T11:44:44Z
depth: standard
files_reviewed: 23
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
  - tests/test_phase1_evidence_verifier.py
  - tests/test_phase1_gap_closure.py
  - tests/test_pipeline_resume.py
  - tests/test_side_effect_policy.py
  - tests/test_stage_contracts.py
  - tests/test_state_integrity.py
  - tools/verify_phase1_gap_evidence.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-07-19T11:44:44Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

The original persistence-commit, resume-event, parser-disclosure, unexpected-retry, namespace-collision, and private-file admission defects are fixed at their cited boundaries. The locked offline suite passes (`300 passed`), Ruff passes, and the schema-v2 evidence verifier reproduced its recorded six-command result before this report was replaced.

The re-review found one new release-blocking recovery defect and one remaining evidence-authority gap. A crash-left deterministic temporary file permanently prevents later snapshot mutations, and the evidence source set still omits both reviewed JSON fixtures. The latter means previous WR-02 is improved but not fully closed: semantically neutral fixture-byte changes can leave every recorded command result unchanged while the verifier continues to accept the stale evidence.

No production network client, remote-write adapter, candidate-code execution path, dependency installation, source-repository script invocation, secret/environment read, automatic approval, merge, or publication capability was introduced. The production composition root still admits only the exact fixture processor, SQLite/local-manifest store, local clock/ID providers, and local publication planner; publication remains a local `planned_not_published` artifact with `remote_writes_attempted = 0`. The separately deferred Phase-6 OS/syscall network-denial item is not the current WR-04 file ownership/mode admission finding and is not reclassified here.

## Previous Finding Re-evaluation

| Previous finding | Status | Re-evaluation |
|---|---|---|
| CR-01 | **CLOSED** | `AnchoredDirectory._retire_backup_after_commit()` is non-throwing after the authoritative target/directory sync, and post-commit cleanup fault tests prove the returned result matches reopened state. |
| CR-02 | **CLOSED** | Schema v3 persists hash-linked resume events; `_verify_run_chain()` recomputes their hashes, order, checkpoint association, head, timing, and denormalized count before any public projection. |
| CR-03 | **CLOSED** | Root and child parsers use `SafeArgumentParser`; every nonzero parser exit discards generated detail and emits one fixed byte-exact diagnostic. |
| WR-01 | **CLOSED** | `PIPELINE_INTERRUPTED` now uses the finite three-attempt transient budget, and fail-once recovery resumes at the failed stage without prefix replay. |
| WR-02 | **NOT CLOSED** | Source binding and command reruns were added, but `_source_paths()` includes only `*.py` under `tests`; the reviewed approved/provenance JSON fixtures remain outside the digest authority. See current WR-01. |
| WR-03 | **CLOSED** | State/manifest namespace equality is rejected in `SQLiteStateStore.__init__` before parent creation or state mutation. |
| WR-04 | **CLOSED** | Existing state and manifest bytes must pass the shared private regular-file predicate: effective owner, one link, and no group/other permission bits. |

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Crash-left temporary files permanently disable recovery

**Classification:** BLOCKER
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/localfs.py:358-360`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/localfs.py:394-401`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:2538-2550`

**Issue:** Every atomic replacement uses a deterministic `.{name}.tmp` path and immediately fails if that path exists. The `finally` cleanup only runs when the current Python process unwinds; `SIGKILL`, host loss, or power loss after `O_EXCL` creation but before rename leaves the temporary inode behind. No startup or under-lock recovery removes or validates it. A direct local reproduction created a valid state database, placed a private `.state.db.tmp` beside it to model that crash window, then attempted the same state mutation across two independent reopen cycles. Both returned `state_operation_failed`, and the temporary file survived both attempts. The same naming primitive is used for manifests and the publication plan, so a crash can turn a resumable checkpoint into a persistent manual-repair requirement.

This violates the phase's crash/retry contract: the authoritative target still contains the prior valid snapshot, but the next invocation cannot promote any candidate and cannot make progress.

**Fix:** Add deterministic stale-temporary recovery under the state lock before mutation. Admit a stale temp only with the existing private-owner/single-link/regular-file checks, then discard and directory-fsync it when the live target is still the authoritative pre-rename generation. Cover both `.state.db.tmp` and the backup writer's `..state.db.backup.tmp`; apply equivalent state-serialized recovery to manifest temps. For publication output, use an operation-specific lock or unique temp names plus a safe owner-validated scavenger so one live writer cannot delete another writer's temp. Add a subprocess crash regression that kills the writer after temp creation, reopens, completes the pending stage, and proves the verified prefix is not replayed.

## Warnings

### WR-01: Evidence source authority excludes reviewed JSON fixtures

**Classification:** WARNING
**File:** `/Users/alexzhu/Lenovo/skillscout/tools/verify_phase1_gap_evidence.py:282-300`
**Related:** `/Users/alexzhu/Lenovo/skillscout/tools/verify_phase1_gap_evidence.py:305-312`, `/Users/alexzhu/Lenovo/skillscout/tools/verify_phase1_gap_evidence.py:509-522`

**Issue:** `_source_paths()` recursively binds only filenames ending in `.py` under `tests`. It separately fixes the database hash, but it does not bind `tests/fixtures/pipeline/approved.json` or `tests/fixtures/state/v1-cli-provenance.json`, even though both are in this review scope and are authoritative inputs to the migration, resume, provenance, and packaged-CLI tests. The current source set reports 23 paths while direct inspection confirms both JSON paths are absent.

Rerunning commands does not close this gap. A whitespace/key-order-only edit changes `approved.json` bytes without changing its parsed model, tests, pass counts, normalized output digests, build artifacts, or any bound source hash. A similarly non-semantic provenance edit can do the same. `verify_evidence()` can therefore accept evidence whose reviewed fixture bytes differ from the recorded run, contradicting the claimed exact source-byte authority and leaving previous WR-02 partially open.

**Fix:** Make the evidence source set an explicit closed list of every reviewed source/fixture artifact, including both JSON files, or safely enumerate all relevant regular non-symlink test fixtures by approved extension while retaining the database's separately pinned hash. Add a regression that records evidence, changes only JSON whitespace or key order, supplies otherwise identical fresh command captures, and requires verification to fail on the source digest check before command credit.

## Verification Notes

- Locked offline pytest: `300 passed in 5.54s`.
- Locked offline Ruff: `All checks passed!`.
- The existing evidence document passed `verify --rerun` against the pre-review source bytes. After this replacement changed a deliberately bound source file, the same read-only command was confirmed to fail closed until evidence is freshly recorded; no evidence artifact was modified during this review.
- Direct stale-temp reproduction: two reopen/mutation attempts both returned `state_operation_failed`; `.state.db.tmp` remained present.
- Direct source-set inspection: `approved_json_bound=False`, `provenance_json_bound=False`, `source_count=23`.
- `.planning/config.json` remained at SHA-256 `5c5acc837fef244afd431f542223618d8abd043eb77b0ef9e08b98267d9d3219` before the report write.

---

_Reviewed: 2026-07-19T11:44:44Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
