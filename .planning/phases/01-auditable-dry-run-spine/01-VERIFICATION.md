---
phase: 01-auditable-dry-run-spine
verified: 2026-07-19T11:55:07Z
status: gaps_found
score: 4/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  gaps_closed:
    - "Post-commit backup-retirement failures no longer report rollback after the replacement snapshot is authoritative."
    - "The public reused-stage count is now derived from a verified immutable resume-event chain."
    - "Invalid CLI arguments now emit one fixed non-echoing diagnostic."
  gaps_remaining:
    - "A crash-left deterministic temporary file permanently blocks later state, manifest, or publication-plan replacement."
    - "The current gap-evidence document is stale and does not bind the two reviewed JSON fixtures or the semantics of the replacement review's findings."
  regressions:
    - "Replacing 01-REVIEW.md changed a claimed source digest; replacing this report also changes the claimed 01-VERIFICATION.md digest, so the existing evidence is not current."
gaps:
  - truth: "A run interrupted by process or host loss can reopen and continue from its last verified checkpoint without manual filesystem repair."
    status: failed
    reason: "AnchoredDirectory uses one deterministic .<target>.tmp name, rejects an existing temp before write, and has no under-lock stale-temp recovery. A crash after O_EXCL creation but before rename leaves a permanent blocker."
    artifacts:
      - path: "src/skillscout/adapters/localfs.py"
        issue: "_atomic_write_once raises temporary_exists at lines 358-360 and only cleans a temp when the current process reaches finally; no crash-recovery path exists."
      - path: "src/skillscout/adapters/state.py"
        issue: "Startup and _snapshot_transaction call the shared atomic writer under the state lock without recovering .state.db.tmp, ..state.db.backup.tmp, or manifest temps."
      - path: "src/skillscout/application/pipeline.py"
        issue: "Publication-plan replacement uses the same deterministic temp primitive without an operation-specific recovery/coordination policy."
    missing:
      - "Recover owner-validated stale state and backup temps under the retained state lock before mutation, with directory fsync after removal."
      - "Apply serialized stale-temp recovery to manifest writes and a concurrency-safe unique-temp or locked scavenger design to publication-plan writes."
      - "Add a subprocess crash regression that kills a writer after temp creation, reopens, completes the pending stage, and proves the verified prefix is not replayed."
  - truth: "Phase-1 acceptance evidence is current, independently rerunnable, and bound to every reviewed source and fixture that determines the credited results."
    status: partial
    reason: "The standalone verifier correctly fails closed today, but 01-GAP-VALIDATION.md is stale: its 01-REVIEW.md digest is c319e423... while the current file is 5d038ccd.... The source set includes only tests/**/*.py and omits approved.json plus v1-cli-provenance.json. Its hard-coded CR/WR mapping also still assigns the replacement review's CR-01/WR-01 identifiers to the prior findings."
    artifacts:
      - path: "tools/verify_phase1_gap_evidence.py"
        issue: "_source_paths accepts only .py files below tests, and CURRENT_FINDING_NODES is the superseded seven-finding mapping."
      - path: "tests/fixtures/pipeline/approved.json"
        issue: "Authoritative packaged-CLI input is reviewed and executed but absent from source_digests."
      - path: "tests/fixtures/state/v1-cli-provenance.json"
        issue: "Authoritative migration/provenance fixture is reviewed and asserted but absent from source_digests."
      - path: ".planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md"
        issue: "verify --rerun exits 1 with phase1 gap evidence invalid against the current review; this report replacement also invalidates its recorded verification digest."
    missing:
      - "Bind an explicit closed set containing both reviewed JSON fixtures and reject stale fixture bytes before command credit."
      - "Replace the superseded seven-finding constants with mappings for the current review findings, including a crash-left temp regression and the JSON-fixture authority regression."
      - "After code, review, and this verification report are stable, record fresh evidence and run read-only verify --rerun from an external working directory without subsequently changing bound files."
deferred:
  - truth: "Prove zero outbound network at the OS/syscall boundary in addition to the Python socket sentinel."
    addressed_in: "Phase 6"
    evidence: "01-GAP-VALIDATION.md and Plan 01-16 explicitly keep os_syscall_network_denial assigned to adversarial MVP acceptance; it is unrelated to the current crash-recovery and evidence-authority findings."
---

# Phase 1: Auditable Dry-Run Spine Verification Report

**Phase Goal:** 用户可以用冻结 fixture 运行一条从候选输入到“拟发布结果”的完整流水线；所有阶段都有版本化结构结果、可恢复 checkpoint，并且 dry-run 在架构层阻止远程写入。
**Verified:** 2026-07-19T11:55:07Z
**Status:** gaps_found
**Re-verification:** Yes — after Plans 01-12 through 01-16

## Goal Achievement

### Observable Truths

| # | Roadmap success criterion | Status | Evidence |
|---|---|---|---|
| 1 | 冻结 fixture 依次经过九个阶段并产生完整 stage ledger。 | ✓ VERIFIED | `PipelineStage` defines the exact nine-stage order; `PipelineRunner.run()` iterates it and persists each success. The fresh locked selection including the packaged happy path passed (`42 passed` total across six named nodes/parameter sets). |
| 2 | 每个 stage result 包含版本、稳定 ID、hash、时间、attempt 和适用版本/telemetry。 | ✓ VERIFIED | `StageEnvelope`, `StageAttempt`, schema descriptors, `_commit_success`, and `_verify_run_chain` carry and cross-check the required fields. The duplicated-field tamper matrix passed in the fresh 42-test selection. |
| 3 | 暂时性失败后从最近成功 checkpoint 恢复且不重复已完成副作用。 | ✗ FAILED | Nominal fail-once and exact-prefix recovery pass, but crash-left deterministic temp files make later writes fail permanently. A direct two-reopen-equivalent primitive check returned `temporary_exists` twice, left the valid target at `v1`, and left the temp present. |
| 4 | dry-run 通过架构级无写入 adapter，只生成 publication plan。 | ✓ VERIFIED | Production construction seals `PHASE_ONE_MAX_SCOPES` to `none/local_state`, accepts only supported local adapters, and returns `planned_not_published` with `remote_writes_attempted=0`; the remote-declaring-adapter regression passed. |
| 5 | 相同 fixture/version hash 稳定，非法跃迁或不兼容 schema 被拒绝。 | ✓ VERIFIED | Canonical hash preimages, strict frozen models, exact schema fingerprints, central chain verification, and closed transitions are substantive and wired; transition and persisted-field tamper checks passed. |

**Score:** 4/5 roadmap must-haves verified

The reported 300-test suite and the independently rerun 23-test prior-finding matrix are useful regression evidence, but neither contains the crash-left temp case. A green suite therefore does not establish the recovery criterion.

### Plan Must-Have Reconciliation

The three blockers from the previous verification are closed in production code and named tests:

- Plan 01-12: post-commit backup cleanup is non-throwing and returned outcomes agree with reopened state.
- Plans 01-13/01-14: immutable resume events bind reuse count, head, order, checkpoint association, and public projections.
- Plan 01-15: parser rejection is fixed/non-echoing, and unexpected processor interruption retries finitely without prefix replay.

The exact eight-node review-regression command passed `23 passed in 0.60s`. However:

- Plans 01-07 and the phase recovery goal are contradicted by the uncovered crash-left deterministic-temp path.
- Plan 01-16's current-evidence truths are not met: the evidence document is stale, omits two reviewed JSON inputs, and its CR/WR mapping refers to the superseded review findings.

No verification overrides exist.

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/skillscout/cli.py` | Packaged dry-run/inspect boundary and fixed diagnostics | ✓ VERIFIED | Substantive and wired from `pyproject.toml`; parser and runtime failures are sanitized. |
| `src/skillscout/adapters/fixtures.py` | Bounded one-descriptor frozen-fixture reader | ✓ VERIFIED | Strict fixture contract, bounded read, change detection, and deterministic processor feed the real runner. |
| `src/skillscout/application/pipeline.py` | Ordered recovery runner and sealed local composition | ⚠️ PARTIAL | Nine-stage, finite retry, exact-prefix and local-only logic work; publication output inherits the unrecovered deterministic-temp primitive. |
| `src/skillscout/adapters/localfs.py` | Descriptor-anchored durable atomic replacement | ✗ PARTIAL | Substantive anchoring and commit-point logic exist, but crash-left deterministic temps permanently block replacement. |
| `src/skillscout/adapters/state.py` | Transactional, content-addressed, verified state/checkpoints | ⚠️ PARTIAL | Schema, event ledger, manifests and full-chain proof are substantive; state/manifest writes have no stale-temp recovery. |
| `src/skillscout/domain/models.py` / `canonical.py` | Strict versioned contracts and canonical identities | ✓ VERIFIED | Required fields, bounded payloads, resume events, and non-circular hashes are present and used. |
| `tests/fixtures/pipeline/approved.json` | Frozen approved pipeline input | ✓ VERIFIED | Real nine-stage fixture; current byte content was inspected. |
| `tests/fixtures/state/v1-cli.db` | Frozen interrupted v1 migration evidence | ✓ VERIFIED | SHA-256 is `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`. |
| `tests/fixtures/state/v1-cli-provenance.json` | Frozen database provenance | ⚠️ PARTIAL | Substantive and used by tests, but omitted from Plan-16 source-digest authority. |
| `tools/verify_phase1_gap_evidence.py` | Current independently rerunnable evidence authority | ⚠️ PARTIAL | Rerun and source checks are real, but the authority set excludes reviewed JSON fixtures and the finding map is stale. |
| `01-GAP-VALIDATION.md` | Current source/output-bound acceptance evidence | ✗ STALE | Current `01-REVIEW.md` digest differs; standalone verification fails before command credit. |
| `uv.lock` | Gate-B-approved dependency graph | ✓ VERIFIED | SHA-256 is `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `pyproject.toml` | `skillscout.cli:main` | Packaged entry point | ✓ WIRED | The named packaged happy-path test passes. |
| `cli.py` | fixture/state/runtime | `load_fixture` → `SQLiteStateStore` → `build_dry_run_runtime` | ✓ WIRED | Frozen input reaches the real local pipeline. |
| `pipeline.py` | `state.py` | run identity, event, attempt, result, checkpoint and resume operations | ✓ WIRED | Nominal transient recovery and no-replay behavior pass. |
| `state.py` | `localfs.py` | `atomic_write` for startup/state snapshots and manifests | ⚠️ PARTIAL | Connection is real, but no caller recovers a crash-left deterministic temp under the state lock. |
| `pipeline.py` | `localfs.py` | local `publication-plan.json` atomic replacement | ⚠️ PARTIAL | Correct local-only sink, but it shares the unrecovered temp-name failure. |
| persisted rows/manifests/events | `inspect-run` | `verify_run_chain` before projection | ✓ WIRED | Canonical stage and resume-event facts are recomputed; tamper tests pass. |
| evidence `source_digests` | reviewed production/tests/fixtures | `_source_paths` exact-set recomputation | ✗ PARTIAL | Production and Python tests are bound, but both reviewed JSON fixtures are absent. |
| evidence `current_findings` | replacement `01-REVIEW.md` | hard-coded CR/WR node map | ✗ NOT CURRENT | CR-01 and WR-01 now mean different findings than the nodes recorded by the tool/document. |

## Data-Flow Trace (Level 4)

| Artifact | Data source | Sink | Status |
|---|---|---|---|
| Stage ledger | Frozen approved JSON → `FixtureSubject` → `StageInput` → `FixtureProcessor` | content-addressed manifests + SQLite results/checkpoints | ✓ FLOWING |
| Resume authority | Verified result/checkpoint prefix → hash-linked `ResumeEvent` | runner start index + inspect reuse projection | ✓ FLOWING |
| Publication plan | Verified completed chain | local `publication-plan.json` only | ✓ FLOWING; no remote publisher exists |
| Crash recovery | prior authoritative target + crash-left `.<name>.tmp` | next atomic replacement | ✗ BLOCKED by `temporary_exists` before candidate creation |
| Evidence authority | current code/review/verification + command outputs | `01-GAP-VALIDATION.md` verifier | ✗ STALE / INCOMPLETE for JSON fixtures and replacement findings |

## Behavioral Spot-Checks

| Behavior | Command/result | Status |
|---|---|---|
| Happy nine-stage flow, closed transitions, finite no-replay recovery, remote-adapter rejection, duplicated-field tamper, and resume-event tamper | Locked offline named pytest selection: `42 passed in 0.74s` | ✓ PASS |
| All eight historical finding nodes from Plans 01-12..01-16 | Locked offline named pytest selection: `23 passed in 0.60s` | ✓ PASS |
| Crash-left state temp permits later progress | Created a valid target plus private `.state.db.tmp`; two atomic replacement attempts both returned `temporary_exists`, target remained `v1`, temp survived | ✗ FAIL |
| Current evidence independently reruns | External-cwd locked offline `verify --rerun` | ✗ FAIL — exit 1, `phase1 gap evidence invalid` |
| Protected inputs remain exact | `shasum -a 256 uv.lock tests/fixtures/state/v1-cli.db` | ✓ PASS |

## Probe / Evidence Execution

No `probe-*.sh` file is declared or present. The phase-declared standalone evidence executable was run from `/private/tmp` through the repository-local managed Python, locked graph, and offline/no-download settings. It exited 1 with the fixed diagnostic `phase1 gap evidence invalid`; the current review digest mismatch alone is sufficient, and this report replacement changes the additionally bound verification digest.

## Requirements Coverage

| Requirement | Source plans | Description | Status | Evidence |
|---|---|---|---|---|
| OPS-01 | 01-01..01-04, 01-06..01-16 | Versioned structured stage data and complete attempt telemetry/audit fields | ✓ SATISFIED | Contracts, SQLite columns, writes, central verification, and fresh tamper tests establish the product requirement. Plan-16 evidence-document completeness remains a separate current gap. |
| OPS-04 | 01-01..01-08, 01-10..01-16 | Finite retry, latest-checkpoint recovery, publication-plan-only dry-run | ✗ BLOCKED | Nominal retry/resume and architectural no-remote behavior pass, but process/host loss can leave a temp that prevents any later checkpoint mutation without manual repair. |

No Phase-1 requirement is orphaned: every plan declares OPS-01 and/or OPS-04, and REQUIREMENTS.md maps exactly those two IDs to Phase 1. The checked boxes in REQUIREMENTS.md are not accepted as evidence.

## Anti-Patterns and Finding Classification

The changed production/test/tool files contain no unreferenced `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, placeholder, or not-implemented marker. The defects are substantive edge-path and evidence-authority failures, not stubs.

| Classification | Count | Findings |
|---|---:|---|
| 🛑 BLOCKER | 1 | Crash-left deterministic temp permanently prevents recovery progress. |
| ⚠️ WARNING / partial must-have | 1 | Current evidence is stale, excludes reviewed JSON fixtures, and maps superseded finding semantics. |
| Deferred | 1 | OS/syscall-level outbound-network denial remains Phase 6 only. |

## Human Verification Required

None. Both current gaps are deterministic local failures demonstrated through code inspection and repository-local execution. No visual, external-service, performance, or subjective judgment is required.

## Gaps Summary

Phase 1 has a real nine-stage local-only pipeline, strict stage envelopes, immutable resume-event authority, exact-prefix retry, fixed diagnostics, and canonical corruption rejection. The previous three blockers are closed.

The phase goal is still not achieved because recovery fails after a realistic process/host-loss window: a deterministic temp created before rename survives the dead process and blocks every later mutation. The acceptance evidence also cannot currently certify the tree: it is stale after the new review, excludes two authoritative JSON fixtures, and still labels old tests as the new review's findings.

### Next Action

Run `$gsd-plan-phase 1 --gaps` with two focused concerns:

1. Add coordinated stale-temp recovery across state, backup, manifest, and publication-plan writes, with a real killed-writer/no-prefix-replay regression.
2. Update evidence authority for both reviewed JSON fixtures and current finding semantics, then regenerate and independently rerun evidence only after all bound code/review/verification bytes are stable.

Do not advance to Phase 2 while the crash-recovery blocker remains.

---

_Verified: 2026-07-19T11:55:07Z_
_Verifier: the agent (gsd-verifier)_
