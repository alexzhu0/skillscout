---
status: resolved
trigger: "Phase 6 record-live-authority fails with state_integrity_error after exact preflight on the approved source and state identities."
created: 2026-07-31
updated: 2026-07-31
---

# Phase 6 live authority integrity

## Symptoms

- Expected: the state-only authority transition upgrades the accepted legacy operations schema, records one authority fact, and persists one successor state receipt.
- Actual: GitHub Actions run `30613685381` preflight succeeds, then `record-live-authority` fails with `state_integrity_error` before any DeepSeek request or publication effect.
- Error: `Local state integrity verification failed.`
- Timeline: the first approved authority attempt failed before the compatibility change; the second attempt at source `4c7baba3052765ce52993dbb129ac5fa126495df` fails at the same boundary.
- Reproduction: restore the approved state commit `500b3de1b14d8c0d1e0a4d3a35bf027eb19db2eb` and invoke the state-only record path with authority digest `sha256:87f354fc931f67913d948c99a61ffbd8de35bf99b16f9f60386debe6582facd9`.

## Current Focus

- fault_tree:
  - "legacy-operations migration creates a state object that violates the current digest/receipt schema"
  - "authority-fact insertion produces an invalid source/root/digest relationship"
  - "the trusted state bundle is rejected before migration because its declared content digest does not match its files"
  - "local reproduction selects an incorrect state root or checkout"
- hypothesis: The initial state CAS durably succeeded, but post-CAS observation raised before the recorder returned its receipt; retrying from the immutable parent cannot recognize that exact successor and instead fails generically. A bounded reconciliation read can safely return only the direct verified successor that contains the exact expected authority fact.
- test: Read the synchronization verification and existing state-reader seams, then add a focused red regression test for a post-CAS exception followed by a verified direct successor containing the exact authority fact.
- expecting: The new test fails under current code because `record_live_acceptance_authority()` immediately propagates the synchronization exception. It will pass only when recovery proves the successor's parent, root, run ID, and complete authority fact all match.
- next_action: Add and run a focused red regression test in `tests/test_phase6_acceptance.py` that simulates a post-CAS synchronization exception and asserts recovery returns an independently verified successor receipt instead of retrying the authority mutation.

## Evidence

- 2026-07-31: workflow preflight emitted `live_authority_state_read_verified` for the approved source, state commit, root, and authority digest.
- 2026-07-31: the workflow's only active job was `human_attestation`; all semantic and publication jobs were skipped.
- 2026-07-31: trusted state commit `500b3de1b14d8c0d1e0a4d3a35bf027eb19db2eb` contains a legacy `operations_acceptance_facts` table whose constrained fact kinds omit `acceptance_live_authority`; it contains four valid legacy acceptance facts (nomination, benchmark lock, offline run, and hosted-isolation capability).
- 2026-07-31: the initial disposable-copy reproduction was rejected by `AnchoredDirectory` with `DurableWriteError("file_permissions")` before `OperationsStateStore` opened the database; this is a copy-mode artifact, not evidence about the trusted restored state or schema migration.
- 2026-07-31: after only correcting the disposable copy's mode, the exact legacy ledger migrated successfully (`upgrade_acceptance_schema() == True`) from schema fingerprint `sha256:afc759…` to the current fingerprint `sha256:ab08dd…`, retaining all 150 operations facts. The migration itself is eliminated as the failure boundary.
- 2026-07-31: the authority writer requires an `acceptance_benchmark_lock` with the authority manifest digest in the same `acceptance_run_id`; the trusted lock is owned by `nomination-80878c1a9a0f28e8fe8c5c63be8932ae`.
- 2026-07-31: paired offline writer reproduction after migration: a valid authority bound to the trusted manifest successfully recorded under `nomination-80878c1a9a0f28e8fe8c5c63be8932ae`, producing one additional live-authority fact. The same authority under `distinct-live-run` failed deterministically with `AcceptanceApplicationError("evidence_missing")`. The coordinator confirmed the live run used the matching nomination ID, so the run-identity guard is not the reported failure.
- 2026-07-31: the authority writer snapshot remained readable after the successful write (three facts under the nomination run: nomination, benchmark lock, and live authority). This eliminates the migration and local authority-fact persistence paths for the reported run.
- 2026-07-31: the first in-memory-CAS command did not execute because the one-line Python harness declared classes after semicolon-separated statements, producing a `SyntaxError`; no state code was reached and the scenario remains untested.
- 2026-07-31: trusted successor evidence supplied by the coordinator: despite the workflow error, the state ref advanced to `ab0ac3dd8b60c254dd20788ec936494996d76440`; root `sha256:5c7a1097c0e6cee8b85150120078c434fe1a24ae908a1c91fa6b4b86df57cfd8` verifies locally and its operations SQLite contains exactly one `acceptance_live_authority` fact with digest `sha256:87f354fc931f67913d948c99a61ffbd8de35bf99b16f9f60386debe6582facd9`. This directly proves a durable successor was written before the reported generic error.

## Eliminated

- hypothesis: DeepSeek request or catalog publication caused the failure. Evidence: neither job was eligible in the dispatched workflow.
- hypothesis: The legacy schema migration itself rejects the trusted state. Evidence: a private-mode disposable copy of the exact operations database migrated successfully and verified as current.

## Resolution

- Root cause: the fixed state-ref CAS could succeed and then lose its immediate verification read; the recorder collapsed that narrow post-CAS uncertainty into a generic integrity failure.
- Fix: `StateBranchStore` now marks only known post-ref-write verification failures as uncertain. The authority-carrier path may recover solely after proving the exact candidate commit, parent, tree, root, full bundle bytes, authority fact, and first resume locator.
- Verification: state-branch, semantic-durability, Phase 6 acceptance/workflow, discovery/operations, source-execution, compile, and Ruff checks passed. No live model, publication, or credential action occurred during the repair.
