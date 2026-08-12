---
phase: 01-auditable-dry-run-spine
plan: "18"
subsystem: audit-evidence
tags: [sha256, evidence-authority, fixture-binding, finding-map, offline, rerun]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: Plan 01-17 killed-writer crash-recovery regression and stabilized 2026-07-19 review/verification bytes
provides:
  - Fixture-complete closed evidence source authority (25 exact paths including both reviewed JSON fixtures)
  - Stale-fixture rejection regressions proving zero runner calls before command credit
  - Current two-finding CR-01/WR-01 authority map with AST-resolved digest-bound nodes
  - Fresh schema-version-2 evidence proven by an independent external-cwd verify --rerun
affects: [phase-01-verification, code-review, security-audit, nyquist-validation, phase-02-planning]

tech-stack:
  added: []
  patterns:
    - reviewed JSON fixture bytes are first-class authority members entered only as explicit literal paths, never globbed
    - a finding identifier is creditable only after AST resolution inside digest-bound source and execution by the closed registry
    - evidence is recorded only after every bound byte stabilizes; any later bound change stales it by design

key-files:
  created: []
  modified:
    - tools/verify_phase1_gap_evidence.py
    - tests/test_phase1_evidence_verifier.py
    - tests/test_phase1_gap_closure.py
    - .planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md

key-decisions:
  - "Bind both reviewed JSON fixtures as explicit literal paths in the closed source set — semantically neutral fixture byte changes now stale recorded evidence at the digest check before any command is credited."
  - "Credit exactly the current review's CR-01/WR-01 findings through digest-bound top-level nodes; the superseded seven-finding map survives only under the past-tense PRIOR_REVIEW_FINDING_NODES label."

patterns-established:
  - "Fixture-authority regression: record, flip only whitespace/key order in a bound fixture, and require verification failure with zero runner calls before command credit."
  - "Past-tense preservation: superseded finding maps keep a labeled definitions-existence assertion instead of deletion, matching the LEGACY_GAP_FINDING_NODES precedent."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "The closed evidence source set binds tests/fixtures/pipeline/approved.json and tests/fixtures/state/v1-cli-provenance.json; whitespace-only and key-order-only fixture byte changes fail the source-digest check with zero runner calls, and the claim set fails closed on dropped or substituted fixture paths."
    requirement: OPS-01
    verification:
      - kind: unit
        ref: "tests/test_phase1_evidence_verifier.py#test_stale_json_fixture_bytes_are_rejected_before_command_credit"
        status: pass
    human_judgment: false
  - id: D2
    description: "The finding map credits exactly the current review's CR-01 (killed-writer crash recovery) and WR-01 (stale fixture rejection) through AST-resolved top-level nodes; the superseded seven-finding map remains resolvable under PRIOR_REVIEW_FINDING_NODES."
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "tests/test_phase1_gap_closure.py#test_current_review_finding_node_definitions_exist"
        status: pass
      - kind: unit
        ref: "tests/test_phase1_gap_closure.py#test_prior_review_finding_node_definitions_exist"
        status: pass
      - kind: integration
        ref: "tests/test_phase1_gap_closure.py#test_current_review_composed_packaged_smoke"
        status: pass
    human_judgment: false
  - id: D3
    description: "Fresh schema-v2 evidence recorded only after all bound bytes stabilized, then independently rerun read-only from an external working directory with exit 0, byte-identical document, and unchanged immutable hashes at all three checkpoints."
    requirement: OPS-01
    verification:
      - kind: e2e
        ref: "absolute repository-local uv record from mktemp cwd + verify --rerun from a distinct mktemp cwd (phase1 gap evidence valid)"
        status: pass
    human_judgment: false

duration: 19min
completed: 2026-07-20
status: complete
---

# Phase 1 Plan 18: Evidence Authority Gap Closure Summary

**Both reviewed JSON fixtures are now digest-bound members of the closed evidence source set, the finding map credits exactly the current review's CR-01/WR-01 regressions, and fresh schema-v2 evidence passed an independent read-only rerun from an external working directory.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-07-20T09:43:06Z
- **Completed:** 2026-07-20T10:02:32Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `_source_paths` now binds `tests/fixtures/pipeline/approved.json` and `tests/fixtures/state/v1-cli-provenance.json` as explicit literals beside the existing exact set; the sorted, duplicate-free authority is 25 paths and `.planning/config.json` remains outside it.
- `test_stale_json_fixture_bytes_are_rejected_before_command_credit` proves whitespace-only (approved.json) and key-order-only (v1-cli-provenance.json) byte changes fail at the source-digest check with zero runner calls, and that dropping either claim or substituting a non-bound path fails closed.
- `CURRENT_FINDING_NODES` credits exactly CR-01 → `test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay` (Plan 01-17) and WR-01 → the new stale-fixture regression; the superseded seven-finding map is preserved as `PRIOR_REVIEW_FINDING_NODES` with its own definitions-existence assertion.
- Fresh evidence was recorded only after all bound bytes stabilized; read-only `verify --rerun` from a distinct external cwd exited 0 (`phase1 gap evidence valid`) with the document byte-identical and both immutable hashes unchanged at all three checkpoints.

## Task Commits

Each task was committed atomically (Task 01 TDD: RED then GREEN; Task 02 evidence separate):

1. **Task 01-18-01 RED: stale-fixture rejection regression + harness fixture copies** - `72faafe` (test)
2. **Task 01-18-01 GREEN: fixture-complete source set and two-finding authority map** - `8ed93ad` (feat)
3. **Task 01-18-02: fresh fixture-complete two-finding evidence** - `b857e45` (docs)

## Files Created/Modified

- `tools/verify_phase1_gap_evidence.py` — two explicit fixture `Path` literals in `_source_paths`; `CURRENT_FINDING_NODES` replaced with exactly CR-01/WR-01; rendered `## Current Two-Finding Matrix`; deferred prose keeps OS/syscall network denial assigned only to Phase 6 without the retired WR-04 reference. `SCHEMA_VERSION`, `EXPECTED_TOP_LEVEL`, `CLI_FACTS`, `COMMAND_REGISTRY`, and normalization unchanged.
- `tests/test_phase1_evidence_verifier.py` — harness repository now carries bounded copies of both reviewed JSON fixtures at exact relative paths; new bound-name regression `test_stale_json_fixture_bytes_are_rejected_before_command_credit`; `_drop_source_claim`/`_rename_source_claim` claim-mutation helpers.
- `tests/test_phase1_gap_closure.py` — superseded map relabeled `PRIOR_REVIEW_FINDING_NODES` with `test_prior_review_finding_node_definitions_exist`; `CURRENT_REVIEW_FINDING_NODES` redefined as exactly `("CR-01", "WR-01")`; current-map test asserts the two-key tuple.
- `.planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md` — regenerated schema-version-2 evidence (25 source digests, two-finding matrix, 314-test full suite) recorded after byte stabilization.

## Source Authority Set

| Category | Exact coverage | Count |
|---|---|---:|
| Project metadata | `pyproject.toml` | 1 |
| Production | every `src/skillscout/**/*.py` regular non-symlink file | 10 |
| Tests | every `tests/**/*.py` regular non-symlink file | 9 |
| Reviewed JSON fixtures | `tests/fixtures/pipeline/approved.json`, `tests/fixtures/state/v1-cli-provenance.json` | 2 |
| Tool | `tools/verify_phase1_gap_evidence.py` | 1 |
| Review authority | `01-REVIEW.md`, `01-VERIFICATION.md` | 2 |
| **Total** | exact sorted path/SHA-256 records | **25** |

Fixture digests bound by the record: `approved.json` = `1664549ffc5154d2a10827deaddba4e030b574b4bfb3e9b53475af4ca049bf3c`, `v1-cli-provenance.json` = `4c57e883fad30d03a1cd10420d8e82c75c6873389044e68fe1135bbf218a960a`. The frozen `v1-cli.db` remains a separately pinned immutable input, never a source claim; the evidence document, verifier outcome, and `.planning/config.json` stay outside the authority set.

## Current Two-Finding Matrix

| Finding | Status | Digest-bound top-level test node |
|---|---|---|
| CR-01 | PASS | `tests/test_pipeline_resume.py::test_killed_writer_stale_state_temp_recovers_and_resumes_without_prefix_replay` |
| WR-01 | PASS | `tests/test_phase1_evidence_verifier.py::test_stale_json_fixture_bytes_are_rejected_before_command_credit` |

## Record / Independent Rerun Authority

Record ran from a newly created external working directory `/var/folders/5d/5jv9m53555qd21yd7qntlfsh0000gn/T/tmp.EQDwhhEtwT`:

```sh
UV_PYTHON_INSTALL_DIR="$repo_root/.tools/python" UV_MANAGED_PYTHON=1 \
UV_PYTHON_DOWNLOADS=never UV_OFFLINE=1 \
"$repo_root/.tools/uv-0.11.29/bin/uv" run --project "$repo_root" --locked python \
  "$repo_root/tools/verify_phase1_gap_evidence.py" record \
  "$repo_root/.planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md"
# -> "phase1 gap evidence recorded", exit 0
```

The independent read-only rerun ran from a distinct new external working directory `/var/folders/5d/5jv9m53555qd21yd7qntlfsh0000gn/T/tmp.FeviV0tAPb`:

```sh
UV_PYTHON_INSTALL_DIR="$repo_root/.tools/python" UV_MANAGED_PYTHON=1 \
UV_PYTHON_DOWNLOADS=never UV_OFFLINE=1 \
"$repo_root/.tools/uv-0.11.29/bin/uv" run --project "$repo_root" --locked python \
  "$repo_root/tools/verify_phase1_gap_evidence.py" verify --rerun \
  "$repo_root/.planning/phases/01-auditable-dry-run-spine/01-GAP-VALIDATION.md"
# -> "phase1 gap evidence valid", exit 0
```

The document stayed byte-identical across the rerun: SHA-256 `008752516cd22af6814a80d046561084cc989fe8bf4d383d64edc8c31544faad` before and after.

## Immutable Input Hashes

| Authority | Before record | After record | After independent rerun |
|---|---|---|---|
| `uv.lock` | `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32` | same | same |
| `tests/fixtures/state/v1-cli.db` | `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251` | same | same |

## Byte-Stability Declaration

The record executed only after Plan 01-17 and Task 01-18-01 commits landed, the full locked suite (314 passed) and Ruff passed, and `01-REVIEW.md` / `01-VERIFICATION.md` were already stable. No bound file (`src/skillscout/**/*.py`, `tests/**/*.py`, both JSON fixtures, `pyproject.toml`, `tools/verify_phase1_gap_evidence.py`, `01-REVIEW.md`, `01-VERIFICATION.md`) was modified during or after the record; any later bound-byte change stales this evidence by design and forces a fresh record. `.planning/config.json` was never read into evidence, staged, or modified.

## Decisions Made

- Both reviewed JSON fixtures entered the closed source set only as explicit literal paths — no globbed extensions or directories — so the authority can never widen implicitly.
- The current map credits exactly CR-01/WR-01; the superseded seven-finding semantics survive only under the past-tense `PRIOR_REVIEW_FINDING_NODES` label with its own resolvability assertion.
- Evidence recording was sequenced strictly after byte stabilization, and the rerun was read-only from a distinct external cwd, keeping the document and verifier outcome outside the authority they report.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None.

## Threat and Safety Scan

- T-01-18-01 mitigated: both JSON fixtures are digest-bound; the new regression proves stale fixture bytes fail before any command credit (zero runner calls).
- T-01-18-02 mitigated: superseded constants replaced; CR-01/WR-01 nodes AST-resolve from digest-bound bytes and were executed by the closed registry (`current_findings`: 2 passed).
- T-01-18-03 mitigated: record ran only after stabilization; the rerun was read-only; document bytes were identical before/after.
- T-01-18-04 / T-01-18-SC mitigated: only bounded normalized digests and allowlisted facts recorded; `--locked`, offline, no-download execution with unchanged protected hashes.
- No new file, CLI flag, schema version, dependency, network path, or trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

All commands ran offline through the repository-local pinned uv (`UV_OFFLINE=1 ... uv run --locked`):

- `pytest -q tests/test_phase1_evidence_verifier.py tests/test_phase1_gap_closure.py` — **32 passed**
- `pytest -q tests` — **314 passed**
- `ruff check tools/verify_phase1_gap_evidence.py tests/test_phase1_evidence_verifier.py tests/test_phase1_gap_closure.py` — **All checks passed**
- RED gate: `test_stale_json_fixture_bytes_are_rejected_before_command_credit` failed before GREEN with `DID NOT RAISE EvidenceError` (old verifier accepted stale fixture bytes)
- Commits exist: `72faafe` (test, RED), `8ed93ad` (feat, GREEN), `b857e45` (docs, evidence)
- `grep -c "approved.json" tools/verify_phase1_gap_evidence.py` — **1**; `grep -c "v1-cli-provenance.json" ...` — **1**; `grep -c "WR-04" ...` — **0**
- Recorded `current_findings` keys exactly `("CR-01", "WR-01")`, both `pass`; `source_digests` 25 sorted duplicate-free paths including both JSON fixtures; `.planning/config.json` absent
- `verify --rerun` from an external cwd exited 0 with `phase1 gap evidence valid`; document SHA-256 identical across the rerun; both immutable hashes matched at all three checkpoints
- All four plan-owned artifacts exist; no tracked file was deleted; `.planning/config.json` remains the sole unstaged user-owned change

## Next Phase Readiness

- Verification gap 2 (WARNING) is ready for independent re-review: the evidence authority is current, fixture-complete, and independently rerunnable against the stabilized tree.
- Both 2026-07-19 review findings now have named, digest-bound, freshly passing regression authority; OPS-01 and OPS-04 evidence is current.
- Standing property: replacing `01-REVIEW.md` or `01-VERIFICATION.md` (or any bound byte) deliberately stales this evidence and requires a fresh record before the next acceptance claim.
- The Phase-6 OS/syscall network-denial item remains explicitly deferred and untouched.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-20*
