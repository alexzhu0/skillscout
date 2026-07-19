---
phase: 01-auditable-dry-run-spine
verified: 2026-07-19T08:30:00Z
status: gaps_found
score: 3/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 1/5
  gaps_closed:
    - "The production composition root now enforces a fixed Phase-1 none/local_state authority ceiling."
    - "Run-scoped result ownership and exact-identity A/B/A resume replace the former global result collision and subject-recency lookup."
  gaps_remaining:
    - "Durable snapshot operations can report failure after the replacement state has become authoritative."
    - "Full-chain validation does not bind the publicly projected reused_stage_count."
  regressions:
    - "Invalid CLI argument handling remains outside the fixed diagnostic boundary and can echo the rejected value."
gaps:
  - truth: "A state mutation's returned outcome agrees with the authoritative state observed after reopen."
    status: failed
    reason: "Backup retirement can fail after replacement durability and backup removal; the state transaction then returns state_operation_failed even though reopening observes the new mutation."
    artifacts:
      - path: "src/skillscout/adapters/localfs.py"
        issue: "atomic_write raises backup_cleanup after the replacement has completed and the backup may already be gone."
      - path: "src/skillscout/adapters/state.py"
        issue: "_snapshot_transaction treats that cleanup error as a failed mutation and poisons the store without reconciling the authoritative snapshot."
    missing:
      - "Define a single authoritative commit point: after replacement durability, treat backup retirement as recoverable housekeeping or retain deterministic recovery evidence."
      - "Add a regression that fails after backup unlink and asserts the API outcome matches the row set visible after reopen."
  - truth: "Full-chain validation binds every run-level audit fact returned by inspect-run."
    status: failed
    reason: "reused_stage_count is accepted from the mutable runs row, returned by VerifiedRunChain, and projected by inspect_run without derivation from an immutable resume event or comparison with the verified checkpoint prefix."
    artifacts:
      - path: "src/skillscout/adapters/state.py"
        issue: "_verify_run_chain verifies stage identities but does not attest reused_stage_count before returning the run record."
      - path: "src/skillscout/domain/models.py"
        issue: "PersistedRunRecord only range-checks reused_stage_count; it cannot establish provenance or correctness."
    missing:
      - "Persist a content-addressed resume decision or derive the count from verified resume/checkpoint evidence."
      - "Reject any denormalized count that differs from the verified event/prefix and add public-projection tamper coverage."
  - truth: "Invalid CLI arguments emit only a fixed bounded diagnostic and never echo rejected operator input."
    status: failed
    reason: "Argument parsing runs before the CLI try/SafeFailure boundary, and argparse's default error path includes rejected values in stderr."
    artifacts:
      - path: "src/skillscout/cli.py"
        issue: "build_parser().parse_args(argv) executes before the sanitized exception boundary and uses default ArgumentParser.error/exit behavior."
    missing:
      - "Use a non-echoing parser error boundary with one fixed allowlisted invalid-arguments diagnostic."
      - "Add subprocess coverage for invalid choices, unknown options, and missing values using credential/path canaries."
deferred:
  - truth: "Prove zero outbound network at the OS/syscall boundary in addition to the Python socket sentinel."
    addressed_in: "Phase 6"
    evidence: "The legacy WR-04 item in 01-GAP-VALIDATION.md remains assigned to the Adversarial MVP Acceptance phase; it is distinct from the current review's existing-state permission warning."
---

# Phase 1: Auditable Dry-Run Spine Verification Report

**Phase Goal:** 用户可以用冻结 fixture 运行一条从候选输入到“拟发布结果”的完整流水线；所有阶段都有版本化结构结果、可恢复 checkpoint，并且 dry-run 在架构层阻止远程写入。
**Verified:** 2026-07-19T08:30:00Z
**Status:** gaps_found
**Re-verification:** Yes — after the original four-gap closure sequence

## Goal Achievement

### Observable Truths

| # | Roadmap success criterion | Status | Evidence |
|---|---|---|---|
| 1 | 冻结 fixture 依次经过九个阶段并产生完整 stage ledger。 | ✓ VERIFIED | `STAGE_SEQUENCE` is the closed nine-stage enum order; the three packaged-CLI acceptance flows and related focused checks passed (35 selected tests total, 1.60s). |
| 2 | 每个 stage result 携带完整版本、身份、hash、时间、attempt 和适用版本/telemetry，并形成可信审计结果。 | ✗ FAILED | Stage-envelope fields and canonical checks exist, but a public run-level audit fact, `reused_stage_count`, is not bound by the full-chain proof and can be altered while verification and inspect still accept it. |
| 3 | 暂时性失败后从最近成功 checkpoint 恢复且不重复已完成副作用。 | ✗ FAILED | Nominal transient retry and exact A/B/A recovery work, but a durability-cleanup failure can return failure after the mutation is authoritative; an unexpected one-time processor interruption is also persisted as non-retryable. |
| 4 | dry-run 通过架构级无写入 adapter，只生成 publication plan。 | ✓ VERIFIED | The composition root accepts only supported concrete local adapters under `PHASE_ONE_MAX_SCOPES`; the remote-declaring adapter regression and packaged flows pass with `remote_writes_attempted=0`. |
| 5 | 相同 fixture/version 的 hash 稳定，非法状态跃迁或不兼容 schema 被拒绝。 | ✓ VERIFIED | Canonical hashing, strict models, exact schema fingerprinting and the parameterized duplicated-field tamper checks are substantive and wired; the selected canonical tamper matrix passed. |

**Score:** 3/5 roadmap must-haves verified

The repository's reported full suite is green (`200 passed`), but that result does not cover the three blocker paths above or the four warning paths below. Test count is therefore not evidence that the phase goal is fully achieved.

### Plan Must-Have Reconciliation

All PLAN frontmatter truths from `01-01` through `01-11` were rechecked against the current implementation. The supply-chain gates, bounded fixture reader, strict contracts, schema migration, exact identity lookup, sealed authority, descriptor-anchored I/O, canonical stage-chain verification and local publication plan are present and wired. The following PLAN-level claims remain contradicted:

- `01-07`: every durability failure has a truthful resumable outcome — contradicted by post-commit backup-cleanup failure.
- `01-10`: one verifier binds every publicly trusted ledger fact — contradicted by unattested `reused_stage_count`.
- `01-02` / `01-04`: every CLI diagnostic is closed and canary-free — contradicted by default argparse error output.
- `01-06`: every interruption has consistent retry semantics — incomplete for unexpected processor exceptions.
- `01-11`: the evidence index is independently bound to current product/test execution — incomplete because its verifier accepts asserted command results without source/output binding.

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/skillscout/cli.py` | Packaged dry-run/inspect and closed diagnostics | ⚠️ PARTIAL | Runtime commands are substantive and wired; parser failures bypass the closed diagnostic boundary. |
| `src/skillscout/application/pipeline.py` | Ordered recovery pipeline and sealed local composition | ⚠️ PARTIAL | Nine-stage, exact-identity and local-only behavior are real; unexpected exceptions become non-retryable interruptions. |
| `src/skillscout/adapters/fixtures.py` | Bounded one-descriptor fixture reader | ✓ VERIFIED | Strict fixture parsing and deterministic fixture processor are substantive and exercised. |
| `src/skillscout/adapters/localfs.py` | Descriptor-anchored durable atomic writes | ✗ PARTIAL | Anchoring and mandatory sync logic exist, but backup cleanup can make the reported transaction outcome disagree with reopened state. |
| `src/skillscout/adapters/state.py` | Transactional, content-addressed, fully verified ledger | ✗ PARTIAL | The schema, migration, manifests and chain verifier are substantive; run-level reuse provenance is unbound, path collision is possible, and existing file permissions are not checked. |
| `src/skillscout/domain/models.py` / `canonical.py` | Strict immutable contracts and canonical identities | ✓ VERIFIED | Bounded JSON, strict persisted projections and canonical stage/result identities are present and used. |
| `tests/fixtures/state/v1-cli.db` | Frozen interrupted v1 migration evidence | ✓ VERIFIED | Current SHA-256 remains `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`. |
| `uv.lock` | Gate-B-approved dependency graph | ✓ VERIFIED | Current SHA-256 remains `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`. |
| `tools/verify_phase1_gap_evidence.py` | Independent evidence validation | ⚠️ PARTIAL | It validates canonical document shape and two immutable hashes, but not current source/test bytes, captured command output, or named-node definitions. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `pyproject.toml` | `skillscout.cli:main` | Packaged entry point | ✓ WIRED | The real packaged command path is exercised by acceptance tests. |
| `cli.py` | fixture/state/runtime | `load_fixture` → `SQLiteStateStore` → `build_dry_run_runtime` | ✓ WIRED | Approved fixture reaches the real local pipeline. |
| `pipeline.py` | `state.py` | attempt identity, manifest, checkpoint and resume operations | ✓ WIRED | Stage lifecycle is connected; failure truthfulness/retry semantics have uncovered edge-path defects. |
| `state.py` | `localfs.py` | anchored read/atomic replace | ⚠️ PARTIAL | The connection is real, but post-commit backup cleanup is treated as rollback/failure. |
| persisted ledger | `inspect-run` | `verify_run_chain` then model projection | ✗ PARTIAL | Stage facts are recomputed; `reused_stage_count` reaches output without equivalent provenance proof. |
| CLI argv | fixed diagnostic vocabulary | parser error path | ✗ NOT_WIRED | Default argparse output is outside `SafeFailure` handling. |
| gap evidence JSON | standalone verifier | canonical parsing and literal checks | ⚠️ PARTIAL | Command success assertions are not bound to the product/test tree or captured output. |

## Data-Flow Trace (Level 4)

| Artifact | Data source | Sink | Status |
|---|---|---|---|
| Stage ledger | Frozen fixture → `StageInput` → processor payload | manifest + SQLite result/checkpoint | ✓ FLOWING |
| Publication plan | Verified nine-stage chain | local `publication-plan.json` | ✓ FLOWING; no remote publisher exists |
| Snapshot mutation result | candidate serialized DB + backup lifecycle | caller outcome and reopened state | ✗ INCONSISTENT after backup-cleanup failure |
| Reuse audit fact | mutable `runs.reused_stage_count` | `VerifiedRunChain` and inspect JSON | ✗ UNATTESTED |
| Invalid CLI value | raw argv | argparse stderr | ✗ UNSANITIZED |
| Evidence command result | literals in `01-GAP-VALIDATION.md` | standalone validity result | ⚠️ SELF-ASSERTED / STALE-RISK |

## Behavioral Spot-Checks

| Behavior | Result | Status |
|---|---|---|
| Packaged happy/resume/inspect, changed A-prime, exact A/B/A, frozen-v1 Validators-first resume, finite transient budget, remote-declaring adapter rejection and canonical tamper matrix | 35 selected tests passed in 1.60s | ✓ PASS |
| Snapshot failure outcome matches reopened state | Post-gap review reproduced `state_operation_failed` while the requested row was present after reopen; current control flow confirms the replacement precedes failing backup retirement | ✗ FAIL |
| Tampered `reused_stage_count` is rejected | Post-gap review changed a completed run's count and both full-chain verification and inspect accepted the value; current verifier has no count derivation/comparison | ✗ FAIL |
| Hostile invalid option value stays out of diagnostics | Default argparse choice handling echoes the rejected value before the CLI try block | ✗ FAIL |
| One-time unexpected processor interruption can retry | First call becomes `pipeline_interrupted`; subsequent unchanged identity is treated as permanent without a second processor invocation | ⚠️ WARNING |

## Probe / Evidence Execution

No conventional `probe-*.sh` is declared. The Phase-1 standalone evidence validator is not accepted as proof of current product execution: it validates document literals and only recomputes the lock/frozen-DB hashes. The green 200-test record remains useful regression context, but it cannot close uncovered paths.

## Requirements Coverage

| Requirement | Source plans | Status | Evidence |
|---|---|---|---|
| OPS-01 | `01-01` through `01-11` | ✗ BLOCKED | Structured envelopes and canonical stage facts exist, but a public audit count is not chain-bound, parser diagnostics can disclose rejected input, and existing state/manifest trust lacks permission checks. |
| OPS-04 | `01-01` through `01-11` | ✗ BLOCKED | Architectural no-remote dry-run and nominal retry/resume work, but the returned persistence outcome can disagree with reopened state and an interruption class is permanently non-retryable. |

No Phase-1 requirement is orphaned from PLAN frontmatter. `REQUIREMENTS.md` marks OPS-01 and OPS-04 complete, but current code evidence does not support completion.

## Current Review Warnings

| Finding | File(s) | Status | Impact and required remediation |
|---|---|---|---|
| WR-01: unexpected processor exception disables retry | `application/pipeline.py` | ⚠️ WARNING | Classify the first outcome consistently as permanent, or make `PIPELINE_INTERRUPTED` retryable within the finite budget; add fail-once-then-succeed recovery coverage. |
| WR-02: evidence verifier accepts stale/self-asserted success | `tools/verify_phase1_gap_evidence.py` | ⚠️ WARNING | Bind evidence to a repository tree or explicit source/test/output digests, resolve named nodes, and generate/validate evidence in the same execution job. |
| WR-03: state filename can collide with manifest directory | `adapters/state.py` | ⚠️ WARNING | Append a disjoint manifest suffix to the complete filename or reject `manifest_root == path` before state creation; add a CLI regression for `.manifests` state names. |
| WR-04: existing state/manifests lack owner/mode validation | `adapters/localfs.py`, `adapters/state.py` | ⚠️ WARNING | Apply the private regular-file owner/mode check before deserializing state and before trusting existing manifests; reject violations with the fixed integrity diagnostic. |

The current WR-04 permission warning is not the same item as the legacy `01-GAP-VALIDATION.md` WR-04 deferral. Only the legacy OS/syscall-level network-denial check is deferred to Phase 6.

## Anti-Patterns and Finding Classification

No placeholder implementation explains the result; the affected files are substantive. The failures are edge-path integrity and privacy defects:

| Classification | Count | Findings |
|---|---:|---|
| 🛑 BLOCKER | 3 | Snapshot outcome/reopen inconsistency; unattested reused count; raw invalid CLI value outside the diagnostic boundary |
| ⚠️ WARNING | 4 | Retry classification; stale evidence gate; manifest path collision; existing-file ownership/mode checks |
| Deferred | 1 | OS/syscall-level outbound-network denial in Phase 6 |

## Human Verification Required

None. The blocking conditions and warnings are observable in deterministic local code paths and do not require visual, external-service or performance judgment.

## Gaps Summary

Phase 1 now has a real, sealed, local-only nine-stage pipeline with strict stage contracts, exact-identity resume and substantial canonical ledger verification. It is not yet a truthful audit/recovery boundary under all supported failure and input paths. Three blockers remain: persistence can report the wrong durable outcome, a projected reuse fact is not attested, and invalid CLI arguments can bypass fixed diagnostics. The four warnings should be addressed in the same closure pass because they affect retry reliability, evidence freshness and local-state integrity.

### Next Action

Run `$gsd-plan-phase 1 --gaps` and plan one focused closure covering the three frontmatter gaps, with the four warnings as required regression work. Re-run independent verification afterward; do not advance to Phase 2 while the blocker list is non-empty.

---

_Verified: 2026-07-19T08:30:00Z_
_Verifier: the agent (gsd-verifier)_
