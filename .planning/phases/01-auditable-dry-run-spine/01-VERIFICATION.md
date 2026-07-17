---
phase: 01-auditable-dry-run-spine
verified: 2026-07-17T07:28:23Z
status: gaps_found
score: 1/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Dry-run construction enforces an immutable Phase-1 maximum authority before any adapter can run."
    status: failed
    reason: "The composition root accepts a caller-supplied policy that can allow remote_read/remote_write and labels an arbitrary processor EffectScope.NONE; the verifier reproduced acceptance of a remote_write registration under a permissive policy."
    artifacts:
      - path: "src/skillscout/application/pipeline.py"
        issue: "build_dry_run_runtime accepts policy= and trusts caller-supplied registration scopes instead of enforcing the Phase-1 ceiling."
      - path: "src/skillscout/application/ports.py"
        issue: "AdapterRegistration binds a caller-provided label to an arbitrary object without proving the object's actual authority."
      - path: "tests/test_side_effect_policy.py"
        issue: "Tests cover only the default policy, not attempted policy widening or a processor that declares/carries remote authority."
    missing:
      - "Make {none, local_state} an immutable upper bound in the production composition root; remove or subset-check policy widening."
      - "Require a closed, truthful effect declaration from supported concrete adapters/processors and reject remote authority before runner construction."
      - "Add regression tests for permissive custom policies and mislabeled/remote-capable processors."
  - truth: "Every accepted stage output becomes bounded, self-consistent and durably readable evidence before its checkpoint or terminal plan commits."
    status: failed
    reason: "Writer and reader contracts diverge: fixture-v2 and cap-plus-one manifests can reach planned_not_published but inspect immediately rejects them; post-processor failures can leave running attempts; directory fsync errors are ignored and parent-path checks remain pathname-racy."
    artifacts:
      - path: "src/skillscout/application/pipeline.py"
        issue: "Only processor.process is inside the stage failure boundary; output conversion, hashing, manifest persistence and publication-plan durability are outside it."
      - path: "src/skillscout/adapters/state.py"
        issue: "The write path has no MAX_MANIFEST_BYTES check, producer acceptance is broader than _SUPPORTED_PRODUCERS, required directory sync failures are swallowed, and operations re-resolve checked parent paths."
      - path: "src/skillscout/domain/models.py"
        issue: "StageEnvelope.payload is an unbounded dict[str, Any] rather than a bounded JSON-only output contract."
    missing:
      - "Use one producer/schema registry on both write and read paths and reject unsupported versions before run creation."
      - "Validate JSON-only bounded stage output and canonical manifest bytes before creating a file or advancing an attempt."
      - "Cover the entire post-start_attempt lifecycle with closed failure transitions so attempt/run state is accurate at failure time."
      - "Anchor writes to verified directory descriptors and treat required file/directory fsync failure as fatal before DB checkpoint or terminal status."
  - truth: "The ledger verifier fully binds canonical run, attempt, result, checkpoint and manifest identity and exposes only validated diagnostics."
    status: failed
    reason: "A coherently rehashed manifest with a forged noncanonical result_id passed verify_completed_results; inspect_run returns unvalidated run/attempt rows and reproduced a credential canary verbatim; schema-v2 open validates only a small column subset."
    artifacts:
      - path: "src/skillscout/adapters/state.py"
        issue: "_verify_manifest_row does not recompute result_id or bind all duplicated attempt/envelope/checkpoint identity; inspect_run uses dict(row); _validate_current_schema is not an exact schema/integrity fingerprint."
      - path: "src/skillscout/domain/models.py"
        issue: "There are no strict persisted-row projection models enforcing status/error/telemetry coherence."
      - path: "src/skillscout/application/ports.py"
        issue: "The closed ERROR_SUMMARIES boundary is not applied to persisted diagnostics before inspect output."
    missing:
      - "Centralize one full-chain verifier that joins all four tables, recomputes StageInput/input/reuse/output/result/manifest identities, enforces exact stage order/cardinality and is used by migration, resume, inspect and completed-result checks."
      - "Parse persisted rows through strict models; require ErrorCode plus the exact fixed summary and reject any mismatch without echoing stored content."
      - "Validate the complete schema/index/constraint/foreign-key fingerprint and SQLite integrity before accepting user_version=2."
      - "Add one corruption regression per canonical duplicate field, including result_id, reusable digest, attempt number, stage relabel/order and diagnostic canaries."
  - truth: "Retry and resume select the exact matching identity and remain correct across valid input/producer/policy evolution without replay or collision."
    status: failed
    reason: "stage_results.result_id is globally unique while semantic result_id excludes run_id; changing a fixture after a Generator checkpoint reproduced state_operation_failed and left the new run running. Resume also considers only the newest unfinished run for a subject, so A/B/A revisions can miss the matching checkpoint."
    artifacts:
      - path: "src/skillscout/adapters/state.py"
        issue: "result_id is the global stage_results primary key and find_resumable_run returns only one subject-level candidate."
      - path: "src/skillscout/domain/canonical.py"
        issue: "make_result_id intentionally creates semantic identity but the database also uses it as row identity."
      - path: "src/skillscout/application/pipeline.py"
        issue: "One mismatching newest candidate causes creation of a new run without searching for an older exact identity match."
    missing:
      - "Separate run-scoped row identity from semantic result digest, or model reusable semantic results plus run/result associations."
      - "Persist/query complete run identity and select an exact resumable candidate rather than only the latest subject row."
      - "Add changed A' completion/dual-inspect and A-interrupt/B-interrupt/A-resume regressions."
deferred:
  - truth: "Prove zero outbound network at the OS/syscall boundary in addition to Python socket sentinels."
    addressed_in: "Phase 6"
    evidence: "Phase 6 is the explicit Adversarial MVP Acceptance phase with live canary evidence; extend that acceptance environment with OS-level network denial. This does not defer the Phase-1 immutable capability-ceiling gap above."
---

# Phase 1: Auditable Dry-Run Spine Verification Report

**Phase Goal:** 用户可以用冻结 fixture 运行一条从候选输入到“拟发布结果”的完整流水线；所有阶段都有版本化结构结果、可恢复 checkpoint，并且 dry-run 在架构层阻止远程写入。
**Verified:** 2026-07-17T07:28:23Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Roadmap success criterion | Status | Evidence |
|---|---|---|---|
| 1 | 冻结 fixture 依次经过九个阶段并产生完整 stage ledger。 | ✓ VERIFIED | The named installed-CLI and happy-path tests passed independently; actual code wires `cli.main` → `build_dry_run_runtime` → `PipelineRunner` → SQLite/manifests and the approved fixture creates nine ordered attempts/results/checkpoints. |
| 2 | 每个 stage result 都携带完整的版本、稳定身份、hash、时间、attempt 与适用版本/telemetry。 | ✗ FAILED | Fields exist in `StageEnvelope`, but persisted duplicate identity is not fully bound or recomputed, persisted diagnostics bypass the closed allowlist, and a forged noncanonical `result_id` passed completed-result verification. This is not auditable evidence. |
| 3 | 暂时性失败后从最近成功 checkpoint 恢复且不重复已完成副作用。 | ✗ FAILED | The nominal Generator-interrupt/resume and frozen-v1 Validators-first paths pass, but valid identity evolution collides with a prior global semantic result ID and leaves a new run `running`; candidate lookup also cannot select an older exact A identity after B. |
| 4 | dry-run 通过架构级无写入 adapter 只能生成 publication plan。 | ✗ FAILED | The default CLI reaches `planned_not_published`, but the composition root can be widened by its caller and accepts arbitrary processor authority labeled `NONE`; a verification probe accepted an explicit `remote_write` registration. |
| 5 | 稳定 hash、非法状态跃迁和 schema 不兼容由契约测试拒绝。 | ✗ FAILED | Unit tests cover nominal hashes/transitions, but the read verifier accepted a coherently rehashed noncanonical result identity, writer-accepted producer/manifest states can be reader-incompatible, and schema-v2 validation checks only a subset. |

**Score:** 1/5 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/skillscout/cli.py` | Packaged dry-run and inspect boundary | ✓ SUBSTANTIVE / WIRED | CLI is real, invokes fixture/state/runtime paths and returns closed top-level failures. |
| `src/skillscout/application/pipeline.py` | Ordered recovery pipeline and immutable no-remote composition | ✗ PARTIAL | Nine-stage behavior is substantive, but the composition ceiling is caller-widenable and post-processor persistence is outside the failure boundary. |
| `src/skillscout/adapters/fixtures.py` | Strict bounded single-descriptor fixture reader | ✓ VERIFIED | 65,536-byte bound, type/identity/change checks and strict schema are present and exercised by focused tests. |
| `src/skillscout/adapters/state.py` | Transactional, content-addressed, fully verified ledger | ✗ PARTIAL | Real schema/migration/manifests exist, but writer/read symmetry, full-chain canonical verification, schema fingerprint, diagnostic projection and durability/path anchoring are incomplete. |
| `src/skillscout/domain/models.py` / `canonical.py` | Strict immutable contracts and canonical identities | ⚠️ PARTIAL | Models/hash functions are substantive, but unbounded payload and semantic-result/row-identity conflation break the persisted contract. |
| `tests/fixtures/state/v1-cli.db` | Frozen real interrupted v1 evidence | ✓ VERIFIED | SHA-256 `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`; named migration/resume test passed. |
| `uv.lock` | Gate-B-authorized graph | ✓ VERIFIED | SHA-256 `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32` matches the approved value. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `pyproject.toml` | `skillscout.cli:main` | Packaged entry point | ✓ WIRED | Named packaged CLI tests execute the real entry point. |
| `cli.py` | `fixtures.py` | `load_fixture` before state construction | ✓ WIRED | Invalid fixture tests show rejection before DB creation. |
| `pipeline.py` | `state.py` | running attempt before processor | ✓ WIRED | Code and probe test show identity is persisted before `process`. |
| `state.py` | manifests/checkpoints | manifest before DB commit | ⚠️ PARTIAL | Ordering exists, but oversized/unsupported state is committed and directory durability failures are ignored. |
| persisted ledger | `inspect-run` | strict integrity + sanitized projection | ✗ NOT_WIRED | Manifest rows are partially checked; raw run/attempt rows are projected without strict validation. |
| dry-run composition | side-effect policy | immutable Phase-1 ceiling | ✗ NOT_WIRED | Default policy is safe, but a caller-supplied permissive policy widens it. |

### Data-Flow Trace (Level 4)

| Artifact | Data source | Sink | Status |
|---|---|---|---|
| Approved fixture | One bounded descriptor + strict `FixtureSubject` | `StageInput` chain | ✓ FLOWING |
| Stage output | `StageProcessor.process` | `StageEnvelope` → manifest → SQLite | ✗ HOLLOW-INTEGRITY: output is unbounded and writer/read support differs |
| Retry identity | Canonical five-field digest | attempt index/resume | ⚠️ PARTIAL: nominal same-identity path works; run/result identity evolution is broken |
| Durable diagnostics | SQLite run/attempt rows | `inspect-run` JSON | ✗ UNSAFE: persisted values flow verbatim without allowlist validation |
| Publication plan | Final local stage | `publication-plan.json` | ⚠️ PARTIAL: nominal local-only output works; directory durability and capability ceiling are incomplete |

### Behavioral Spot-Checks

All Python commands used the approved repository-local uv/managed-CPython/no-download prefix and `--locked`; no network, remote write, candidate code or secret access was used.

| Behavior | Result | Status |
|---|---|---|
| Happy nine-stage CLI, interrupt/resume/inspect, default remote-scope rejection and frozen-v1 migration | 5 parametrized named checks passed in 0.40s | ✓ PASS |
| Custom permissive policy with explicit `remote_write` registration | Registration accepted (`true`) | ✗ FAIL |
| `producer_version=fixture-v2` writer/read symmetry | Run returned `planned_not_published`; inspect returned `state_integrity_error` | ✗ FAIL |
| Manifest larger than `MAX_MANIFEST_BYTES` | Run returned `planned_not_published`; inspect returned `state_integrity_error` | ✗ FAIL |
| Tampered persisted attempt diagnostic | Credential canary appeared in `inspect_run` JSON | ✗ FAIL |
| Changed fixture after Generator checkpoint | New run returned `state_operation_failed`; statuses were old `interrupted`, new `running` | ✗ FAIL |
| Coherently rehashed forged `result_id` | `verify_completed_results` accepted `sha256:ffff…ffff` | ✗ FAIL |

### Probe Execution

No phase-declared `probe-*.sh` exists. The CLI/tooling behavior was instead checked through the named tests and isolated temporary-directory reproduction probes listed above.

### Requirements Coverage

| Requirement | Source plans | Status | Evidence |
|---|---|---|---|
| OPS-01 | 01-01 through 01-04 | ✗ BLOCKED | Structured fields exist, but canonical cross-record identity and public diagnostic integrity are not enforced; writer-created state can be immediately unreadable. |
| OPS-04 | 01-01 through 01-04 | ✗ BLOCKED | Nominal retry/resume and local publication planning work, but identity evolution collides, exact resume selection is incomplete, and the Phase-1 effect ceiling can be widened. |

No Phase-1 requirement is orphaned from plan frontmatter. REQUIREMENTS.md currently marks both complete, but code evidence does not support that status yet.

### Anti-Patterns and Review Finding Disposition

No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK` or placeholder marker was found in source/tests. The blockers are behavioral and architectural, not obvious stubs.

| Finding group | Disposition | Rationale |
|---|---|---|
| CR-01 | BLOCKER → Gap 1 | Directly defeats roadmap criterion 4's architecture-level remote-write boundary. |
| CR-02, CR-03, CR-04, CR-08 | BLOCKER → Gaps 2 and 4 | Writer/read inconsistency, global-ID collision and non-durable commits undermine criteria 1–3 and 5. |
| CR-05, CR-06 | BLOCKER → Gap 3 | Canonical audit verification and closed diagnostic output are Phase-1 requirements, not later hardening. |
| CR-07 | BLOCKER → Gap 2 | The plan explicitly claims fail-closed path boundaries; checked ancestors can still be swapped before pathname operations. |
| WR-01, WR-02, WR-03 | BLOCKER support → Gaps 2–4 | They materially break lifecycle accuracy, incompatible-schema rejection and exact checkpoint recovery. |
| WR-04 | DEFER to Phase 6 | Add OS/syscall-level network denial to adversarial acceptance. It is not a substitute for fixing the caller-widenable Phase-1 firewall now. |

### Human Verification Required

None. The blocking failures are deterministically observable in code and local reproduction probes. Gate A and Gate B were already explicitly approved and their authoritative hashes still match.

### Gaps Summary

Phase 1 has a genuine runnable vertical skeleton and strong nominal tests, but the goal is not yet achieved under its own audit/security claims. Four root concerns remain: immutable authority enforcement; bounded/symmetric/durable write semantics; full-chain canonical verification plus sanitized inspect output; and collision-free exact-identity resume. These are structured in frontmatter for `$gsd-plan-phase --gaps`.

---

_Verified: 2026-07-17T07:28:23Z_
_Verifier: the agent (gsd-verifier, generic-agent workaround)_
