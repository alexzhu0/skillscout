---
phase: 01-auditable-dry-run-spine
plan: "01"
subsystem: infra
tags: [uv, cpython, supply-chain, lockfile, pytest, pydantic]

requires: []
provides:
  - "Checksum-verified repository-local uv 0.11.29 and managed CPython 3.13.14 toolchain"
  - "Human-approved exact uv.lock dependency graph and bytes"
  - "Static Python package, fixture, and unexecuted test scaffold for the dry-run walking skeleton"
affects: [01-02-walking-skeleton, 01-03-audit-ledger, 01-04-capability-firewall]

tech-stack:
  added: [uv 0.11.29, CPython 3.13.14, uv-build 0.11.29, Pydantic 2.13.4, pytest 9.1.1, Ruff 0.15.21]
  patterns: [repository-local verified toolchain, two-gate dependency approval, exact-lock execution authority]

key-files:
  created:
    - .python-version
    - pyproject.toml
    - uv.lock
    - src/skillscout/__init__.py
    - tests/conftest.py
    - tests/fixtures/pipeline/approved.json
    - tests/test_cli_dry_run.py
  modified:
    - .gitignore

key-decisions:
  - "Gate A approved only the Darwin/arm64 uv and managed-CPython artifacts with the recorded immutable versions and SHA-256 digests."
  - "Gate B approved uv.lock only at SHA-256 caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32."
  - "Wave 1 remains a static supply-chain boundary: locked project packages are not built, installed, imported, or tested until the following plan."

patterns-established:
  - "Every post-Gate-B command must use the verified repository-local uv and managed-Python/no-download prefix."
  - "Any byte change to uv.lock invalidates Gate B and requires a new complete-graph review."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Repository-local uv and managed CPython identities and bytes were independently approved before bootstrap."
    requirement: OPS-01
    verification:
      - kind: manual_procedural
        ref: "Gate A approval: host, release identities, asset names, owner evidence, and both approved SHA-256 digests"
        status: pass
      - kind: other
        ref: "shasum -a 256 on the retained uv and CPython archives; exact local uv/Python version checks"
        status: pass
    human_judgment: true
    rationale: "Toolchain ownership and provenance are mandatory human supply-chain decisions even when byte integrity is automated."
  - id: D2
    description: "The complete registry-only external dependency graph and exact uv.lock bytes were approved before package execution."
    requirement: OPS-04
    verification:
      - kind: manual_procedural
        ref: "Gate B approval of 12 external distributions, 54 artifact records, one canonical first-party root, and the exact lock hash"
        status: pass
      - kind: other
        ref: "shasum -a 256 uv.lock => caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32"
        status: pass
    human_judgment: true
    rationale: "Package legitimacy and the disposition of every resolved artifact require explicit human approval."
  - id: D3
    description: "Static project metadata and the unexecuted fixture/test scaffold are ready for the Walking Skeleton RED step."
    requirement: OPS-01
    verification:
      - kind: other
        ref: "git show --name-status 10ee77f; static pyproject.toml and uv.lock inspection"
        status: pass
    human_judgment: false

duration: 9 min
completed: 2026-07-17
status: complete
---

# Phase 1 Plan 01: Verified Toolchain and Exact Lock Approval Summary

**A checksum-bound repository-local Python toolchain and the complete 12-distribution external lock graph are approved for the Walking Skeleton execution boundary.**

## Performance

- **Duration:** 9 min of automated execution and verification, excluding human checkpoint wait time
- **Started:** 2026-07-17T05:28:56Z
- **Completed:** 2026-07-17T05:37:32Z
- **Tasks:** 3, including two blocking human gates
- **Files modified:** 8 tracked implementation/scaffold files

## Accomplishments

- Gate A approved `Darwin/arm64`, uv `0.11.29` at commit `901092ee11a89ba287f274e3c6e3a2e18ec2fba2`, and Astral's CPython `3.13.14` build `20260623` before their repository-local bootstrap.
- Gate B approved exactly 12 external PyPI distributions, 54 URL/hash/size artifact records, and one artifact-free first-party `skillscout==0.1.0` editable-root node at lock SHA-256 `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Static PEP 621 metadata, package marker, bounded fixture, and the intentionally unexecuted Walking Skeleton test scaffold are committed without creating a project environment or executing locked project code.

## Approval Record

### Gate A — explicit human approval

The user responded `批准 Gate A` after reviewing the complete Gate A record. The retained evidence still matches:

- uv archive: `61c04acc52a33ef0f331e494bdfbedcdb6c26c6970c022ed3699e5860f8930e3`
- Astral managed-CPython archive: `795a5aeeb050f00aa8a2214d779bad9f1b9113edb6923317a80c042a11a087d7`
- local uv: `uv 0.11.29 (901092ee1 2026-07-15 aarch64-apple-darwin)`
- local runtime identity: `cpython 3.13.14`
- direct declarations: `uv-build==0.11.29`, `pydantic==2.13.4`, `pytest==9.1.1`, and `ruff==0.15.21`

### Gate B — explicit human approval

The user responded `批准 Gate B` after reviewing the exact lock hash, all 12 external distributions, dependency markers, all 54 artifact records, and the sole first-party editable-root exception. The approved and current lock hash is:

```text
caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32  uv.lock
```

Every non-root source is `https://pypi.org/simple`; no non-root Git, path, editable, workspace, direct-URL, or alternate-registry source exists. The root metadata exactly matches `pyproject.toml` and has no artifact records.

## Task Commits

1. **Task 01-01-01: Gate A approval** — no commit; human security decision recorded above
2. **Task 01-01-01A: Bootstrap verified local tools and discover lock** — `10ee77f` (`chore`)
3. **Task 01-01-01B: Gate B exact-lock approval** — no production commit; human security decision recorded above

The plan metadata and this summary are committed atomically by the final `docs(01-01)` commit.

## Files Created/Modified

- `.gitignore` — excludes repository-local toolchain, environments, build outputs, and temporary files.
- `.python-version` — pins CPython `3.13.14`.
- `pyproject.toml` — declares static PEP 621 metadata, exact direct dependencies, build backend, and CLI entry point.
- `uv.lock` — records the human-approved exact dependency graph and artifacts.
- `src/skillscout/__init__.py` — creates the package marker without importing project dependencies.
- `tests/conftest.py` — defines deterministic fixture-path scaffolding for the next plan.
- `tests/fixtures/pipeline/approved.json` — supplies bounded repository-owned structured test input.
- `tests/test_cli_dry_run.py` — names the happy path and minimum fixture-safety contracts without being executed in Wave 1.

## Decisions Made

- Treat the exact `uv.lock` bytes—not merely the declared top-level versions—as execution authority.
- Permit only the reviewed first-party editable `.` root; every external node remains exact-version, registry-only, and artifact-hashed.
- Preserve the Wave 1 execution boundary: metadata resolution was allowed, but no project dependency build, sync, import, pytest, Ruff, or `uv run` occurred.

## Deviations from Plan

None. The optional GitHub attestation check was not applicable because no trusted `gh` executable was available; checksum verification and the mandatory human provenance gates were completed exactly as specified.

## Issues Encountered

None.

## Threat Status

- **T-01-SC / T-01-SC-B:** mitigated by the separate Gate A and Gate B decisions, exact-lock approval, and registry-only external-source rule.
- **T-01-SC-A:** mitigated by the two exact archive digests and repository-local tool paths.
- **T-01-SC-C:** mitigated by the managed CPython identity, local uv path, and disabled system fallback contract.
- No unresolved high- or critical-severity threat remains in Plan 01. Any later change to toolchain artifacts, root metadata, dependency graph, or lock bytes reopens the relevant gate.

## Boundary Verification

- No `.venv/`, `dist/`, or project build directory exists.
- No project dependency wheel was downloaded or installed. The managed CPython distribution contains its upstream-bundled `ensurepip` wheel; that file is part of the separately checksum-approved runtime archive, not a resolved SkillScout dependency artifact.
- The uv cache contains only lock-resolution metadata; no locked package archive was installed, built, or imported.
- No project/package import, `uv sync`, `uv build`, `uv run`, pytest, or Ruff command occurred in this plan.

## User Setup Required

None. No external service configuration or credentials are used in Phase 1 Plan 01.

## Next Plan Readiness

Gate B now authorizes Plan 02 to build and execute only the exact approved graph through the full repository-local uv/managed-Python/no-download command prefix. Plan 02 must first prove the named RED test failure, then implement the real SQLite-backed dry-run Walking Skeleton.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-17*

## Self-Check

- `uv.lock` current SHA-256 equals the exact Gate B approval: **PASS**.
- Host, uv archive, runtime archive, uv version/commit, and CPython identity match Gate A: **PASS**.
- Lock structure is 13 nodes total: one canonical artifact-free first-party root and 12 reviewed PyPI external nodes with 54 artifact records: **PASS**.
- Task 01A commit `10ee77f` exists and contains exactly the eight planned tracked files: **PASS**.
- Summary exists at `.planning/phases/01-auditable-dry-run-spine/01-01-SUMMARY.md`: **PASS**.
