---
phase: 01-auditable-dry-run-spine
reviewed: 2026-07-17T07:15:23Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - src/skillscout/__init__.py
  - src/skillscout/adapters/fixtures.py
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
  - tests/test_pipeline_resume.py
  - tests/test_side_effect_policy.py
  - tests/test_stage_contracts.py
  - tests/test_state_integrity.py
findings:
  critical: 8
  warning: 4
  info: 0
  total: 12
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-07-17T07:15:23Z  
**Depth:** standard (with cross-module trust-chain tracing requested by the orchestrator)  
**Files Reviewed:** 19  
**Status:** issues_found

## Narrative Findings (AI reviewer)

The complete fixture-to-SQLite-to-manifest-to-resume/inspect path was reviewed under an adversarial FORCE stance. The current suite is green (`72 passed`) and Ruff reports no lint errors, but those checks miss several correctness and security failures at the exact boundaries this phase claims to close. Three failures were reproduced directly: changing a fixture after a Generator checkpoint makes the new run fail with `state_operation_failed`; a run produced with `producer_version="fixture-v2"` reports success and is then rejected by `inspect-run`; and an oversized manifest likewise reaches `planned_not_published` before `inspect-run` reports `state_integrity_error`. A tampered attempt diagnostic is also emitted verbatim by `inspect-run`.

## Critical Issues

### CR-01: The capability firewall can be widened by its caller and mislabels every processor as effect-free

**File:** `src/skillscout/application/pipeline.py:397-424`  
**Related:** `src/skillscout/application/pipeline.py:409-415`, `src/skillscout/application/ports.py:58-79`  
**Issue:** `build_dry_run_runtime` accepts a caller-supplied `SideEffectPolicy` and uses it verbatim at line 423. A caller can therefore pass a policy allowing `remote_read`/`remote_write`, after which the same registrations rejected by the Phase 1 default are accepted. Independently, the processor is wrapped in `AdapterRegistration(..., EffectScope.NONE, processor)` without consulting or constraining the processor's actual authority. The policy validates caller-provided labels, not capabilities. This defeats the claimed composition-time critical boundary: an arbitrary processor with socket, subprocess, or filesystem behavior is blessed as `none`, and a permissive policy can authorize explicitly remote registrations.

**Fix:** Make the Phase 1 maximum authority immutable. Remove the public policy-widening parameter, or require `requested_policy.allowed_scopes <= SideEffectPolicy.phase_one().allowed_scopes`. Accept only concrete, known local adapter types at the production composition root; do not infer `NONE` for an arbitrary `StageProcessor`. If extensibility is required, make adapters expose a closed `effect_scope` and validate that value, while still keeping an immutable Phase 1 upper bound. Add tests proving a permissive custom policy cannot widen authority and a processor declaring or carrying remote authority is rejected before construction.

### CR-02: Globally unique semantic result IDs make valid identity changes crash a later stage

**File:** `src/skillscout/adapters/state.py:86-101`  
**Related:** `src/skillscout/domain/canonical.py:114-134`, `src/skillscout/application/pipeline.py:150-164`, `src/skillscout/application/pipeline.py:264-307`  
**Issue:** `stage_results.result_id` is a global primary key, while `make_result_id` deliberately excludes `run_id`. When a fixture changes but retains the same `subject_id`, the runner correctly creates a fresh run. The deterministic fixture processor does not include fixture contents in its output, so downstream stages can converge on the same input/output identity as the old run. Their semantic `result_id` then collides with the old run's row. Reproduction: interrupt fixture A after Generator, change only its workflow goal, and run again in the same state store. The new run writes Scout, then fails at Filter with `state_operation_failed`; the new run remains `running`. This violates the changed-identity/fresh-run contract and turns valid input evolution into a database error.

**Fix:** Separate semantic content identity from row identity. Use a run-scoped row key such as `(run_id, stage)` or a distinct generated `stage_result_row_id`, while storing `result_id` as a non-unique semantic digest. If global semantic deduplication is intended, model a reusable result table plus a run/result association table rather than making one result row belong to exactly one run and attempt. Add a regression test that interrupts A after multiple stages, runs changed A' with the same subject, completes, and inspects both runs.

### CR-03: The writer accepts producer versions that the reader later declares corrupt

**File:** `src/skillscout/adapters/state.py:35-36`  
**Related:** `src/skillscout/adapters/state.py:787-826`, `src/skillscout/application/pipeline.py:126-140`, `src/skillscout/application/pipeline.py:193-200`  
**Issue:** The runner accepts any non-empty `processor.producer_version` and can persist a complete successful run, but `_verify_manifest_row` only accepts `fixture-v1`. A processor with `producer_version="fixture-v2"` reaches `planned_not_published`; immediately inspecting that same run raises `state_integrity_error`. The existing retry tests explicitly exercise producer-version changes but never inspect the resulting successful run. The system can therefore create state that its own read path treats as corruption.

**Fix:** Establish one producer-version registry used by both write and read paths. Either reject unsupported versions at runtime construction before creating a run, or persist and support the configured version for verification. Never allow a writer version that the verifier rejects. Add a test that every accepted producer version completes, verifies, resumes, and inspects successfully, and a separate test that an unsupported version is rejected before state creation.

### CR-04: Oversized manifests are committed successfully and become immediately unreadable

**File:** `src/skillscout/adapters/state.py:624-663`  
**Related:** `src/skillscout/adapters/state.py:1007-1047`, `src/skillscout/domain/models.py:37-56`, `src/skillscout/application/pipeline.py:242-307`  
**Issue:** `MAX_MANIFEST_BYTES` is enforced only while reading. `_write_manifest` canonicalizes and writes an unbounded `StageEnvelope.payload` without checking `len(payload)`. A processor returning a string just over the cap produced a 262,940-byte manifest, completed all stages, and returned `planned_not_published`; `inspect_run` then rejected the run as `state_integrity_error`. This is both an integrity failure and an unbounded local-storage path reachable through processor output.

**Fix:** Validate each stage output with a bounded, JSON-only Pydantic contract before hashing. Compute canonical bytes once and reject `len(payload) > MAX_MANIFEST_BYTES` before opening a temporary file or advancing an attempt. Apply the same bound during migration before writing any manifest. Add cap, cap-plus-one, deeply nested, non-JSON, and non-finite output tests that assert the attempt/run are closed with a sanitized failure and no result/checkpoint is committed.

### CR-05: Resume verification does not prove the persisted canonical stage identity

**File:** `src/skillscout/adapters/state.py:787-826`  
**Related:** `src/skillscout/adapters/state.py:464-513`, `src/skillscout/adapters/state.py:770-785`, `src/skillscout/domain/canonical.py:93-134`  
**Issue:** `_verify_manifest_row` verifies selected row/envelope fields plus output and manifest hashes, but it never recomputes or checks the canonical `result_id`; never compares `envelope.input_hash`, `retry_policy_version`, or `attempt_no` with the attempt row; and never verifies the persisted `reusable_key_digest`. `resume_identity_matches` checks the attempt row's input/digest but does not bind those values back to the envelope. It also requires contiguous `stage_index` values without requiring `tuple(PipelineStage)[stage_index]` to equal the stored stage. A coherent but relabeled/rehashed persisted chain can therefore pass resume and skip or substitute a mandatory stage. `verify_completed_results` is weaker still because it reads no attempt identity at all.

**Fix:** Centralize one full verifier over a join of run, attempt, result, and checkpoint. For each position, require the exact closed stage, recompute `StageInput`, `input_hash`, `reusable_key_digest`, `output_hash`, schema-specific `result_id` (v1 excludes retry policy; v2 includes it), and `manifest_hash`; compare every duplicate field across all four records. Require checkpoint/result cardinality and order to match. Use this verifier for migration validation, resume, completed-result verification, and inspect. Add one corruption test per omitted field and a stage-relabel/order test.

### CR-06: `inspect-run` emits untrusted persisted diagnostics without the closed error allowlist

**File:** `src/skillscout/adapters/state.py:926-972`  
**Related:** `src/skillscout/adapters/state.py:238-251`, `src/skillscout/domain/models.py:59-81`, `src/skillscout/application/ports.py:29-55`  
**Issue:** Run and attempt rows are converted with `dict(row)` and returned verbatim. Their `error_code`, `error_summary`, request/model fields, timestamps, and identifiers are not validated against strict domain models or the fixed `ERROR_SUMMARIES` map. Migration also copies v1 attempt diagnostics wholesale. Writing `OPENAI_API_KEY_DO_NOT_DISCLOSE` into an attempt's `error_summary` causes `inspect_run` to print it even though all manifests still verify. Thus the advertised fixed diagnostic boundary does not cover persisted state, and a legacy, corrupted, or accidentally raw provider error can leak secrets to CLI output.

**Fix:** Parse run and attempt rows into strict persisted-record models before projection. Model `error_code` as `ErrorCode | None`, require the exact mapped summary for that code, enforce status/error coherence and length/ASCII bounds, and reject any mismatch with `STATE_INTEGRITY_ERROR` without echoing the value. Sanitize or omit request/provider metadata from public inspect output unless it has an explicit bounded contract. Validate these invariants during v1 migration as well. Add DB-tampering and migrated-v1 credential-canary tests that byte-search stdout/stderr and durable outputs.

### CR-07: Path checks are vulnerable to parent-directory symlink races

**File:** `src/skillscout/adapters/state.py:120-147`  
**Related:** `src/skillscout/adapters/state.py:624-663`, `src/skillscout/application/pipeline.py:329-366`  
**Issue:** State, manifest, and publication output paths are checked with `lstat`/`_path_contains_symlink`, then later opened or replaced by pathname. Another local actor can rename a checked parent and replace it with a symlink between the check and `sqlite3.connect`, `os.open`, or `os.replace`. `O_NOFOLLOW` protects only the final path component; it does not prevent following a swapped ancestor. The static symlink tests cannot exercise this TOCTOU window. A race can therefore redirect supposedly local writes outside the selected directory or connect to a different database.

**Fix:** Anchor filesystem operations to opened directory descriptors. Open each trusted parent with `O_DIRECTORY|O_NOFOLLOW`, verify it with `fstat`, create/open children relative to `dir_fd`, and use dir-fd-relative rename/unlink operations so ancestors cannot be re-resolved. For SQLite, either place the database in an application-owned, non-writable-by-others directory and verify the connected file identity with a supported secure-open/VFS strategy, or fail closed when that guarantee cannot be established. Add adversarial tests that swap parents at instrumented seams, not only pre-existing symlink tests.

### CR-08: Manifest durability errors are ignored before the checkpoint commits

**File:** `src/skillscout/adapters/state.py:647-673`  
**Related:** `src/skillscout/adapters/state.py:618-623`, `src/skillscout/adapters/state.py:690-768`, `src/skillscout/application/pipeline.py:348-366`  
**Issue:** After replacing a manifest, directory `fsync` errors are silently swallowed, and newly created parent directory entries are not durably synced through the hierarchy. `_commit_success` then commits the result/checkpoint. The publication plan similarly renames its file without syncing the directory before the run becomes terminal. A filesystem error or power loss can therefore leave SQLite claiming a durable result or terminal plan while the referenced file is absent. This contradicts the phase's manifest-before-database durability invariant and is a data-loss risk.

**Fix:** Treat every required file and directory sync failure as `STATE_OPERATION_FAILED`; do not commit the result/checkpoint or terminal run status afterward. Sync the file, the containing directory after rename, and any newly created parent directory entries up to an already durable root. If a platform cannot provide this guarantee, explicitly fail or use a single transactional storage mechanism instead of silently weakening durability. Add injected file-fsync and directory-fsync failure tests that assert zero checkpoint advance and a resumable, non-terminal run.

## Warnings

### WR-01: Failures after processor invocation leave a durable running attempt

**File:** `src/skillscout/application/pipeline.py:242-307`  
**Issue:** The exception boundary covers only `processor.process`. Conversion with `dict(output)`, canonical serialization, model construction, manifest writing, and database completion happen outside it. Type errors, non-JSON values, oversized output rejection after CR-04 is fixed, or state/manifest failures can exit while the attempt and run remain `running`; they are only rewritten as abandoned/interrupted on a later invocation. This makes the persisted lifecycle inaccurate at the moment of failure and maps some processor contract violations to the generic CLI state error.

**Fix:** Put the entire post-`start_attempt` stage lifecycle behind one explicit failure boundary. Validate output before persistence, classify processor-contract and state failures into closed codes, and atomically mark the attempt/run whenever the state store remains writable. For an indeterminate database failure, record a recovery marker or make the next-open reconciliation explicit and tested.

### WR-02: Schema-v2 validation accepts only a small column subset rather than the actual schema

**File:** `src/skillscout/adapters/state.py:196-228`  
**Issue:** `_validate_current_schema` checks a handful of column names and foreign-key violations. It does not verify the remaining required columns, types, nullability, primary/unique keys, check constraints, foreign-key definitions, retry index, or database integrity. A `user_version=2` database with the checked column names but an incompatible layout can open successfully and fail later as an operation error, bypass uniqueness/transition assumptions, or emit malformed inspect data.

**Fix:** Validate an exact versioned schema fingerprint: full `table_info`/`foreign_key_list`/`index_list` expectations, required SQL constraints, and `PRAGMA quick_check` or `integrity_check`. Reject any mismatch during open as `STATE_SCHEMA_INCOMPATIBLE` before reads or writes. Add malformed-v2 fixtures for missing non-subset columns, constraints, and index definitions.

### WR-03: Resume selection checks only the newest run for a subject

**File:** `src/skillscout/adapters/state.py:432-439`  
**Related:** `src/skillscout/application/pipeline.py:150-164`  
**Issue:** `find_resumable_run` returns one latest `running`/`interrupted` row by subject. If that row belongs to fixture identity B while an older interrupted run matches identity A, rerunning A discards the candidate after one mismatch and creates a third run instead of resuming the matching A run. Alternating revisions of the same subject therefore defeats idempotent recovery and compounds the result-ID collision in CR-02.

**Fix:** Persist the complete run identity (fixture/input root, producer version, retry-policy version, schema) on `runs` and query by it, or return ordered candidates and verify until an exact match is found. Add an A-interrupt, B-interrupt, A-resume regression test.

### WR-04: The socket sentinel does not prove zero outbound network behavior

**File:** `tests/conftest.py:22-38`  
**Related:** `tests/test_cli_dry_run.py:156-182`  
**Issue:** The sentinel patches `socket.socket.connect` and `socket.create_connection` only. Outbound UDP via `sendto`/`sendmsg`, `connect_ex`, and other OS/network paths remain available. The subprocess CLI tests also execute outside this monkeypatch. Consequently the green test is evidence for two Python call sites, not the claimed zero-network capability.

**Fix:** Run the acceptance command in an OS-level network-denied sandbox/namespace and fail on any attempted network syscall. As a secondary unit-test layer, patch `connect_ex`, `sendto`, `sendmsg`, and DNS-resolution entry points and exercise the packaged subprocess under the same restriction. Keep source/dependency capability omission checks, because monkeypatching alone is not a security boundary.

---

_Reviewed: 2026-07-17T07:15:23Z_  
_Reviewer: the agent (gsd-code-reviewer, generic-agent workaround)_  
_Depth: standard_
