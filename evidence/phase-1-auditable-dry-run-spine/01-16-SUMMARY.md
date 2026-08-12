---
phase: 01-auditable-dry-run-spine
plan: "16"
subsystem: audit-evidence
tags: [sha256, ast, pytest, offline, reproducible-evidence]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: truthful private snapshots, immutable resume events, verified reuse projections, closed CLI diagnostics, and finite no-replay recovery
provides:
  - Exact sorted source authority over production, tests, verifier, review, verification, and project metadata
  - Closed six-command offline registry with normalized captured-output digests and parsed results
  - Independently rerunnable current authority for all three blockers and four warnings
affects: [phase-01-verification, code-review, security-audit, phase-02-planning]

tech-stack:
  added: []
  patterns:
    - evidence documents remain outside the source and output claims they report
    - symbolic command tokens materialize only through repository-local absolute paths and temporary roots
    - exact digest verification precedes AST node resolution and command credit

key-files:
  created:
    - tests/test_phase1_evidence_verifier.py
  modified:
    - tools/verify_phase1_gap_evidence.py
    - tests/test_phase1_gap_closure.py
    - .planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md

key-decisions:
  - "Keep the evidence document and record/verify outcomes outside every source/output claim, eliminating self-hash and self-success cycles."
  - "Normalize only the exact per-command temporary root and elapsed ns/us/ms/s duration following the fixed ' in ' marker; preserve all other bytes."
  - "Credit current review findings only after their nodes resolve as top-level test functions in digest-verified source and the closed registry reruns them."
  - "Keep current WR-04 ownership/mode enforcement as PASS while deferring only the older OS/syscall network-denial item to Phase 6."

patterns-established:
  - "Authority-first evidence: exact file set and immutable hashes are checked before any claimed command result is accepted."
  - "Rerun equivalence: argv, exit, parsed kind/count, normalized stdout digest, and normalized stderr digest must all match fresh execution."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Schema-v2 evidence fails closed on stale source/test/tool bytes, unsafe files, missing AST nodes, duplicate or extra claims, forged exits/counts/digests, and self-asserted success."
    requirement: OPS-01
    verification:
      - kind: unit
        ref: "tests/test_phase1_evidence_verifier.py (23 adversarial cases)"
        status: pass
    human_judgment: false
  - id: D2
    description: "All three current blockers and four current warnings map to digest-bound top-level tests and pass together in one composed local smoke."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_phase1_gap_closure.py#test_current_review_composed_packaged_smoke"
        status: pass
      - kind: integration
        ref: "01-GAP-VALIDATION.md#Current Seven-Finding Matrix"
        status: pass
    human_judgment: false
  - id: D3
    description: "An external-cwd verifier independently reruns packaged smoke, focused findings, full pytest, Ruff, lock check, and isolated build without rewriting evidence or changing protected inputs."
    requirement: OPS-01
    verification:
      - kind: e2e
        ref: "absolute repository-local uv verify --rerun acceptance from mktemp cwd"
        status: pass
    human_judgment: false

duration: 16min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 16: Independently Rerunnable Evidence Authority Summary

**Exact source-byte, AST-node, and normalized command-output authority now makes every current Phase-1 gap claim independently rerunnable from outside the repository.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-07-19T11:11:05Z
- **Completed:** 2026-07-19T11:27:05Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Replaced the literal-only schema-v1 checker with explicit `record DOCUMENT` and read-only `verify --rerun DOCUMENT` modes backed by one fixed six-command registry.
- Bound an exact sorted 23-file authority set, resolved every current finding node through the bound AST bytes, and rejected stale, extra, duplicate, unsafe, oversized, self-hashed, or self-asserted claims.
- Captured and independently reproduced exits, parsed counts, canonical argv tokens, and normalized stdout/stderr SHA-256 values for packaged smoke, current findings, all 300 tests, Ruff, lock consistency, and two build artifacts.
- Proved CR-01..CR-03 and WR-01..WR-04 together while retaining the older OS/syscall network-denial item as a distinct Phase-6 deferral.

## Task Commits

1. **Task 01-16-01 RED: Authority-bound verifier adversarial contract** - `fc68ebf` (test)
2. **Task 01-16-01 GREEN: Exact source/node/output rerun verifier** - `2770854` (feat)
3. **Task 01-16-02: Current seven-finding map and composed smoke** - `0b88a4c` (test)
4. **Rule-1 rerun stability: Narrow elapsed-unit normalization** - `1e07b85` (fix)
5. **Task 01-16-02: Generated schema-v2 current evidence** - `a8a84d0` (docs)

## Source Authority Set

| Category | Exact coverage | Count |
|---|---|---:|
| Project metadata | `pyproject.toml` | 1 |
| Production | every `src/skillscout/**/*.py` regular non-symlink file | 10 |
| Tests | every `tests/**/*.py` regular non-symlink file | 9 |
| Tool | `tools/verify_phase1_gap_evidence.py` | 1 |
| Review authority | `01-REVIEW.md`, `01-VERIFICATION.md` | 2 |
| **Total** | exact sorted path/SHA-256 records | **23** |

The evidence document, `.planning/config.json`, `uv.lock`, and the frozen database are not members of this source set. The lock and database are instead separately fixed pre/post authorities; the document and verifier outcome cannot certify themselves.

## Captured Command Authority

| Command ID | Parsed result | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|
| `packaged_smoke` | 1 passed | `b580f90a30ad73dec6c80e46370ae0103707bc11fb880eeeeb887b89af8aea30` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `current_findings` | 23 passed | `30680ad42c517116e16588f4201f8570353ed6e0540514f69890c0bbf0ab7d12` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `full_pytest` | 300 passed | `4c4030b820fe1724781c76e8fd58eeb1834205021c1389f21327905337860142` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `ruff` | 1 check | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `lock_check` | 1 check | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `46b458b2c297a651ae7e60f895ee59b5f17410bde066563700eacd186c8b6444` |
| `build` | 2 artifacts | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `c1ec4635509470b06b572f64e46bdf7e2d13e643c0d6b709b3038c334a00b598` |

Normalization replaces only the exact per-command temporary workspace and decimal elapsed `ns`, `us`, `ms`, or `s` values immediately following the literal ` in `. Exit status, counts, node names, arbitrary output lines, and failure text remain digest-significant.

## Current Seven-Finding Matrix

| Finding | Status | Bound regression authority |
|---|---|---|
| CR-01 | PASS | Post-commit snapshot cleanup outcome equals reopened authority |
| CR-02 | PASS | Resume-event tamper is rejected by every bound public path |
| CR-03 | PASS | Invalid argv emits one fixed non-echoing diagnostic |
| WR-01 | PASS | Fail-once unexpected interruption resumes without prefix replay |
| WR-02 | PASS | Stale/self-asserted evidence and rerun mismatch fail closed |
| WR-03 | PASS | State/manifest namespace collision is rejected before creation |
| WR-04 | PASS | Existing state and manifests enforce private owner/mode/link policy |

The older OS/syscall-boundary outbound-network denial is not this WR-04. It remains explicitly deferred as `deferred.os_syscall_network_denial.addressed_in = Phase 6`.

## Temporary-Root Acceptance

The final gate ran from a newly created caller directory outside the repository and invoked only the approved repository-local toolchain:

```sh
UV_CACHE_DIR="$repo_root/.tools/uv-cache" \
UV_PYTHON_INSTALL_DIR="$repo_root/.tools/python" \
UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never UV_OFFLINE=1 \
"$repo_root/.tools/uv-0.11.29/bin/uv" run \
  --project "$repo_root" --locked --offline python \
  "$repo_root/tools/verify_phase1_gap_evidence.py" verify --rerun \
  "$repo_root/.planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md"
```

The verifier recomputed the exact source set and immutable inputs, resolved every current node, independently reran all six commands in per-command temporary roots, compared every captured result, and confirmed that the evidence document remained byte-identical.

## Immutable Input Hashes

| Authority | Before record | After record | After independent rerun |
|---|---|---|---|
| `uv.lock` | `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32` | same | same |
| `tests/fixtures/state/v1-cli.db` | `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251` | same | same |

## Decisions Made

- Symbolic argv tokens are stored as evidence, then reconstructed only from the verifier-file repository root and a newly allocated command workspace; caller cwd and ambient executable lookup do not establish authority.
- Source digests are verified before node resolution, and each node must be a top-level `test_*` function in those exact bytes before a passing command can credit it.
- Read-only verification compares fresh complete result records and checks the document bytes again afterward; record mode is the only writer.
- Current WR-04 remains a passing ownership/mode boundary. Only the separately named OS/syscall network-denial acceptance is deferred.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Normalized uv's elapsed millisecond output without weakening captured facts**
- **Found during:** Task 01-16-02 independent rerun
- **Issue:** `uv lock --check` alternated between elapsed outputs such as `1ms` and `0.76ms`; the initial seconds-only normalization correctly rejected the resulting stderr digest mismatch.
- **Fix:** Extended the same fixed ` in ` timing marker to the bounded `ns/us/ms/s` unit set and added a regression proving failure text, counts, nodes, and arbitrary lines remain unchanged.
- **Files modified:** `tools/verify_phase1_gap_evidence.py`, `tests/test_phase1_evidence_verifier.py`
- **Verification:** 23 adversarial tests and Ruff pass; a fresh record followed by two external-cwd independent reruns matched exactly.
- **Committed in:** `1e07b85`

**2. [Rule 1 - Tracking integrity] Repaired legacy STATE and ROADMAP projections after registered handler drift**
- **Found during:** Sequential plan tracking closeout
- **Issue:** The required handlers correctly counted 16/16 summaries but rewrote the nested STATE plan percentage as the six-phase milestone share (17%) and replaced the legacy ROADMAP `Requirements/Completed` row with incompatible plan-count columns.
- **Fix:** Preserved the handler's 16/16 completion, date, metric, decisions, and session updates while restoring the established 100% plan projection and four-column requirement row.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** STATE reports Plan 16 of 16 and 100%; ROADMAP marks 01-16 complete and retains the `Phase/Status/Requirements/Completed` contract.
- **Committed in:** plan tracking metadata commit

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs).
**Impact on plan:** Both fixes preserve the intended evidence and tracking contracts without expanding product scope; no failure or semantic evidence is removed.

## Issues Encountered

- The sandbox denied the first `.git/index.lock` write for the RED commit. The exact scoped commit was retried through the approved Git path with normal hooks; no hook was bypassed and no unrelated file was staged.

## Known Stubs

None.

## Threat and Safety Scan

- T-01-16-01 is mitigated by fresh full-record comparison over exit, parsed result, canonical argv, and both normalized stream digests.
- T-01-16-02 is mitigated by the exact sorted allowlist and pre/post immutable authority checks.
- T-01-16-03 is mitigated by top-level AST resolution after digest verification and execution of the resolved fixed nodes.
- T-01-16-04 is mitigated by storing only digests and fixed structured facts; captured raw streams and temporary runtime data are discarded.
- T-01-16-05 and T-01-16-SC are mitigated by absolute local uv, managed Python, no downloads, offline/locked execution, temporary output/state/build roots, and unchanged protected hashes.
- No new network endpoint, authentication path, schema object, dependency, remote-write authority, candidate-code execution path, or unmodeled trust boundary was introduced.

## User Setup Required

None - no dependency, credential, network, remote-write, or external-service setup is required.

## Self-Check: PASSED

- All four plan-owned artifacts and this summary exist.
- RED/GREEN, finding-map, rerun-stability, and generated-evidence commits exist: `fc68ebf`, `2770854`, `0b88a4c`, `1e07b85`, and `a8a84d0`.
- The 23 adversarial verifier tests, composed smoke, current findings, full 300-test suite, Ruff, lock check, build, and final external-cwd `verify --rerun` all pass.
- Evidence bytes remained unchanged during rerun; both protected hashes and user-owned `.planning/config.json` retained their pre-execution SHA-256 values.
- No tracked file was deleted, no generated file remains untracked, and `.planning/config.json` remains the sole unstaged user-owned change.

## Next Phase Readiness

- WR-02 is closed under current independent authority, and all seven 2026-07-19 review findings have named, digest-bound, freshly passing evidence.
- OPS-01 and OPS-04 are ready for a new independent Phase-1 code review, goal verification, Nyquist validation, and security audit.
- The Phase-6 OS/syscall network-denial item remains explicitly deferred and does not weaken current WR-04 closure.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*
