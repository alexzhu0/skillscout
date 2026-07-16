---
phase: 1
slug: auditable-dry-run-spine
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-16
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for the auditable dry-run Walking Skeleton.

## Test Infrastructure

| Property | Value |
|---|---|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` — created in Plan 01 |
| **Quick run command** | `uv run --locked pytest -q <task-specific-test>` |
| **Full suite command** | `uv run --locked pytest -q && uv run --locked ruff check . && uv lock --check && uv build --no-sources` |
| **Estimated runtime** | <15 seconds on local fixtures |

## Sampling Rate

- **After every task commit:** After Gate B, run the task's focused pytest command and Ruff on touched Python paths. Before Gate B, no build/import/test command is authorized.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite and both CLI demonstrations must be green.
- **Max feedback latency:** 15 seconds.
- Watch-mode flags are forbidden.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---|---:|---:|---|---|---|---|---|---|---|
| 01-01-01 | 01 | 1 | OPS-01, OPS-04 | T-01-SC-A | Gate A approves the exact uv archive/checksum/attestation, upstream CPython plus Astral redistributed runtime artifact, and direct declarations before bootstrap | human checkpoint | N/A — mandatory toolchain/direct provenance gate | N/A | ⬜ pending |
| 01-01-01B | 01 | 1 | OPS-01, OPS-04 | T-01-SC-B | Gate B approves every locked package/distribution/version/source/hash before project dependency sync/build/install | human checkpoint | N/A — mandatory complete-lock provenance gate | N/A | ⬜ pending |
| 01-01-02 | 01 | 1 | OPS-01, OPS-04 | T-01-01 | Packaged `skillscout` console entry point and bounded fixture contract are test-owned; the intended functional assertion is RED after successful build and test collection | e2e/red | `uv build --no-sources && ! uv run --locked pytest -q tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | OPS-01, OPS-04 | T-01-02 | Happy path writes v1 SQLite state and no remote output; fixture reads reject symlink/non-regular/oversize/change races using one descriptor | e2e/security | `uv run --locked pytest -q tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | OPS-01 | T-01-03 | Contracts reject extras; output and manifest hash preimages are non-circular and stable | unit | `uv run --locked pytest -q tests/test_stage_contracts.py` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | OPS-01, OPS-04 | T-01-04 | v1 state transactionally migrates to v2 or rolls back/fails closed; attempt identity, result and content-addressed manifest/checkpoint commit safely | integration | `uv run --locked pytest -q tests/test_pipeline_resume.py` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 2 | OPS-04 | T-01-05 | Failed run resumes, reports reused stages, refuses a fourth retry for one digest, and grants a distinct budget only after input/producer/retry-policy change | CLI/integration | `uv run --locked pytest -q tests/test_pipeline_resume.py tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 3 | OPS-04 | T-01-06 | Remote-read and remote-write capabilities cannot register in Phase 1 dry-run | security | `uv run --locked pytest -q tests/test_side_effect_policy.py` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 3 | OPS-01, OPS-04 | T-01-07 | Tampered state and the expanded adversarial path/size/change matrix beyond Plan 01 primitives fail closed | security/integration | `uv run --locked pytest -q tests/test_state_integrity.py tests/test_cli_security.py` | ❌ W0 | ⬜ pending |
| 01-03-03 | 03 | 3 | OPS-01, OPS-04 | T-01-06 | Full acceptance proves no network access and reports zero remote writes | e2e | `uv run --locked pytest -q` | ❌ W0 | ⬜ pending |

## Wave 0 Requirements

Plan 01 establishes all test infrastructure before implementing the happy path:

- [ ] `pyproject.toml` — Python 3.13, `[build-system]` with exact `uv_build==0.11.29`, `build-backend = "uv_build"`, `[project.scripts]` console entry point, pytest and Ruff config.
- [ ] `uv.lock` — generated only by the non-building/no-source/no-cache discovery command after Gate A and approved in full at Gate B before any sync/build/install.
- [ ] `tests/fixtures/pipeline/approved.json` — valid deterministic pipeline fixture.
- [ ] `tests/test_cli_dry_run.py` — failing happy-path acceptance test before implementation, plus Plan 01 minimum symlink, non-regular, size-before/during, `cap + 1`, single-descriptor, and pre/post-change-detection cases.
- [ ] `tests/conftest.py` — temporary state/output fixtures and deterministic clock/ID providers.

Plans 02 and 03 create their focused test files in the same task before implementing the behavior under test; no test path may be referenced after the task without being created first.

Plan 01's enforced order is Gate A → verified repo-local uv/managed CPython bootstrap → write only the static `pyproject.toml`/test scaffold → non-building lock discovery → Gate B → execute the exact `01-01-02` RED command → implement `01-01-03`. The Gate B row is a blocking checkpoint inside that sequence; its `01-01-01B` identifier preserves every existing implementation ID and does not authorize moving build/test ahead of lock review.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Gate A: toolchain/direct identity approval | OPS-01, OPS-04 | GSD legitimacy seam returned SUS; the current host lacks approved uv/Python | Before bootstrap, verify Darwin/aarch64; uv `0.11.29` commit `901092e…`, Apple-Silicon archive SHA `61c04acc…8930e3` and attestation; upstream CPython `3.13.14`; distinct Astral build `20260623`, `cpython-3.13.14+20260623-aarch64-apple-darwin-install_only_stripped.tar.gz`, SHA `795a5aee…087d7`; and `uv-build==0.11.29` (`uv_build` backend), `pydantic==2.13.4`, `pytest==9.1.1`, `ruff==0.15.21`. Match the full values in `01-RESEARCH.md`, record evidence, and approve or stop. After bootstrap, require the approved path and `uv --version` to report `0.11.29`, then pass the managed interpreter path/version checks before continuing. |
| Gate B: complete lock approval | OPS-01, OPS-04 | Transitive identities and executable artifacts are unknown until safe resolution | Run only `uv lock --no-build --no-sources --no-cache --managed-python --no-python-downloads --python 3.13.14`; it may download wheel/sdist bytes for metadata but must not build, sync or install. Review every locked package and every artifact's exact version, dependency/marker, source URL, SHA-256 and size; rerun legitimacy/provenance checks for all transitives; reject nonregistry/Git/path/editable/direct-URL sources, missing hashes, unexpected/yanked packages or required source builds. Approve exact lock bytes/hash or stop before `uv sync`, `uv build`, `uv run`, pytest or Ruff. |

All product behaviors after the two supply-chain approvals have automated verification.

The RED command for `01-01-02` must be executed exactly as listed. Its shell success is not sufficient evidence: retain pytest output and confirm the test module collected successfully and failed at the named intended functional assertion. Exit due to import/collection/usage/no-tests errors (pytest 2/4/5), build failure, missing interpreter, or dependency/bootstrap failure does not count as RED and must be attributed to setup instead.

## Final Phase Commands

Run these only from the Gate-A-verified shell where `command -v uv` resolves to the approved repo-local uv `0.11.29`, `UV_MANAGED_PYTHON=1`, `UV_PYTHON_DOWNLOADS=never`, the approved `UV_PYTHON_INSTALL_DIR` is set, and Gate B has approved the exact current `uv.lock`.

```text
uv lock --check
uv build --no-sources
uv run --locked ruff check .
uv run --locked pytest -q
uv run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/demo.db --output .tmp/demo-out
uv run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/resume.db --output .tmp/resume-out --fail-after generator
uv run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/resume.db --output .tmp/resume-out
```

The first dry-run exits `0` with `status=planned_not_published` and `remote_writes_attempted=0`. The fail-injected run exits `1`; its rerun exits `0`, reports a positive `reused_stage_count`, and preserves identical hashes for reused stage results. The full pytest suite additionally proves transactional v1→v2 migration/rollback, persisted precomputed attempt identity, retry exhaustion scoped to one reusable digest plus a distinct budget after identity change, complete nullable attempt telemetry, non-circular hashes, Plan 01 fixture-read primitives, and rejection of both remote-read and remote-write capabilities.

## Validation Sign-Off

- [x] All implementation tasks define an automated verification command or create their test first.
- [x] Sampling continuity has no three consecutive implementation tasks without automated verification.
- [x] Wave 0 paths are explicitly owned by Plan 01.
- [x] No watch-mode flags are used.
- [x] Target feedback latency is under 15 seconds.
- [x] `nyquist_compliant: true` is set.
- [ ] Execution evidence captured.

**Approval:** planning contract approved 2026-07-16; execution pending
