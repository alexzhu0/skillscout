---
phase: 01-auditable-dry-run-spine
reviewed: 2026-07-20T10:42:13Z
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
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-07-20T10:42:13Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

This re-review verified the two plans that target the previous report's only findings. Both are resolved at their cited boundaries, each with a passing, independently identifiable regression node. The crash-window recovery contract is now closed for all three deterministic-temperature writers, and the evidence authority set now binds every reviewed fixture byte. The locked offline suite passes (`314 passed`), Ruff passes, and the recorded schema-v2 evidence document reproduced its full six-command registry result (`verify --rerun`: valid) against the source bytes in place before this report was written.

No new Critical or Warning defect was found. Two Info items remain (one dead alias, one duplicated lock helper). No production network client, remote-write adapter, candidate-code execution path, dependency installation, source-repository script invocation, secret/environment read, automatic approval, merge, or publication capability was introduced; publication remains a local `planned_not_published` artifact with `remote_writes_attempted = 0`, and the composition root still admits only the exact fixture processor, SQLite/local-manifest store, local clock/ID providers, and local publication planner.

Follow-up for the next re-baselining plan (not a finding): `tools/verify_phase1_gap_evidence.py` `CURRENT_FINDING_NODES` and `tests/test_phase1_gap_closure.py::test_current_review_finding_node_definitions_exist` hardcode the now-closed two-finding shape `("CR-01", "WR-01")`, and the recorded evidence binds this report's bytes. As designed, `verify --rerun` will fail closed once this replacement lands, until the finding map and evidence are freshly recorded against the current (zero-finding) review state.

## Previous Finding Re-evaluation

| Previous finding | Status | Re-evaluation |
|---|---|---|
| CR-01 (crash-left deterministic temp blocks recovery) | **CLOSED** | `AnchoredDirectory.recover_stale_temporary()` (`localfs.py:331-346`) admits a stale temp only through the existing private-owner/single-link/regular-file predicate, then unlinks and directory-fsyncs it; anything failing the predicate is retained with the unchanged fail-closed error. State recovery runs at `state.py:599-600` (state temp and backup temp) immediately after the exclusive flock is taken; manifest recovery runs at `state.py:2219` under the same store lock; publication recovery runs at `pipeline.py:487-491` under the new per-operation kernel flock (`pipeline.py:441-466`), so a live writer's temp can never be scavenged. Regression `tests/test_pipeline_resume.py::test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay` (spawned writer SIGKILLed after `O_EXCL` temp creation, before rename) passes: reopen discards the temp, resume completes with `reused_stage_count == 6`, and the verified prefix rows are byte-identical (no replay). Publication stale-temp recovery and lock-contention fail-closed tests also pass. |
| WR-01 (evidence source authority excludes reviewed JSON fixtures) | **CLOSED** | `_source_paths()` (`verify_phase1_gap_evidence.py:261-268`) now explicitly binds `tests/fixtures/pipeline/approved.json` and `tests/fixtures/state/v1-cli-provenance.json`; the frozen database remains separately hash-pinned (`FROZEN_DB_HASH`). Directory inventory confirms these are the only fixture files besides the database, so the authority set is closed. Regression `tests/test_phase1_evidence_verifier.py::test_stale_json_fixture_bytes_are_rejected_before_command_credit` passes: whitespace-only and key-order-only fixture edits are rejected on the source digest check before any registry command is credited (`calls == []`), and dropped or renamed fixture claims are likewise rejected. `_resolve_nodes()` binds the finding-to-node map structurally. |

## Narrative Findings (AI reviewer)

No Critical issues.

No Warnings.

## Info

### IN-01: Unused `LocalStateStore` alias

**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/ports.py:200`
**Issue:** `LocalStateStore = StateStore` has no references anywhere in `src/`, `tests/`, or `tools/` (verified by repository-wide search). It is a dead export left from an earlier naming.
**Fix:** Delete the alias, or reference it from the composition layer if it is meant as the public local-store name.

### IN-02: Lock-acquisition logic duplicated across state and publication writers

**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:682-711`
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/pipeline.py:441-466`
**Issue:** `_acquire_lock` and `_acquire_publication_lock` are near-verbatim copies (~25 lines: open with `O_NOFOLLOW|O_CLOEXEC`, dual private-regular admission, dev/ino identity check, non-blocking exclusive flock, fail-closed cleanup). The copies are semantically identical today; a future hardening edit applied to only one copy would silently diverge the two serialization boundaries.
**Fix:** Extract one shared helper (e.g. `AnchoredDirectory.acquire_exclusive_lock(name) -> int` in `localfs.py`) and call it from both sites.

## Verification Notes

- Locked offline targeted regressions: `4 passed` (`test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay`, `test_stale_json_fixture_bytes_are_rejected_before_command_credit`, `test_publication_stale_temp_recovers_under_retained_operation_lock`, `test_concurrent_publication_write_fails_closed_until_lock_holder_exits`).
- Locked offline full pytest: `314 passed in 6.02s`.
- Locked offline Ruff over `src`, `tests`, and the verifier: `All checks passed!`.
- Recorded evidence document passed `verify --rerun` (`phase1 gap evidence valid`) against the pre-review-write source bytes; this report's replacement deliberately invalidates it until evidence is freshly recorded, matching the established fail-closed design. No evidence artifact was modified during this review.
- Fixture inventory: `tests/fixtures/` contains exactly `pipeline/approved.json`, `state/v1-cli-provenance.json`, and `state/v1-cli.db`; all three are bound (source digests or pinned immutable hash). `tests/fixtures/state/v1-cli.db` is the frozen schema-v1 SQLite provenance fixture (user version 1); its bytes are evidence-pinned, not parsed as text.
- Anti-pattern scan of `src/`: no `eval`/`exec`, `os.system`, `shell=True`, `pickle`, unsafe YAML, network clients, or hardcoded secrets. Test scan: no bare `except:`, sleeps, skips, or xfails.
- `.planning/config.json` remained at SHA-256 `5c5acc837fef244afd431f542223618d8abd043eb77b0ef9e08b98267d9d3219` before the report write (unchanged since the previous review; its pre-existing working-tree delta is GSD workflow bookkeeping outside the evidence authority set).

---

_Reviewed: 2026-07-20T10:42:13Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
