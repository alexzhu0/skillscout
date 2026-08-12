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

All commands run from the repository root. Every post-Gate-B uv invocation repeats this exact prefix; `PATH`, activated environments and previously exported variables are not validation evidence:

```text
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"
```

| Property | Value |
|---|---|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` — created statically in Plan 01 |
| **Quick run command** | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q <task-specific-test>` |
| **Full suite command** | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check . && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" build --no-sources` |
| **Estimated runtime** | <15 seconds on local fixtures |

## Sampling Rate

- **Wave 1:** Stop after verified static bootstrap, non-building lock discovery and Gate B. Only the non-importing static check in the map is required; no pytest, Ruff, `uv build`, `uv run` or full suite is authorized or sampled.
- **Wave 2:** Execute the exact attributed RED in Task `01-01-02`, then the focused Walking Skeleton GREEN suite. Only after GREEN, run the full suite for the first time.
- **Waves 3–4:** After every task, run its focused command and Ruff on touched Python paths. At the end of each wave, run the full suite.
- **Before `$gsd-verify-work`:** Run the final self-contained command block plus happy, interrupt/resume and inspect evidence.
- **Max feedback latency:** 15 seconds. Watch-mode flags are forbidden.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---|---:|---:|---|---|---|---|---|---|---|
| 01-01-01 | 01 | 1 | OPS-01, OPS-04 | T-01-SC-A | Gate A approves the exact uv archive/checksum/attestation, upstream CPython plus Astral redistributed runtime artifact, and direct declarations before bootstrap | human checkpoint | N/A — mandatory toolchain/direct provenance gate | N/A | ⬜ pending |
| 01-01-01A | 01 | 1 | OPS-01, OPS-04 | T-01-SC-C | Checksum-verified repo-local uv and managed CPython are selected without system fallback; lock discovery is non-building and performs no project/package execution | preflight/static | `test "$(cat .python-version)" = "3.13.14" && test -s uv.lock && test "$("$PWD/.tools/uv-0.11.29/bin/uv" --version)" = "uv 0.11.29" && test -x "$(cat "$PWD/.tools/approved-python-path")"` | ❌ W0 | ⬜ pending |
| 01-01-01B | 01 | 1 | OPS-01, OPS-04 | T-01-SC-B | Gate B approves the exact one-node first-party root exception plus every external locked package/artifact before project sync/build/install | human checkpoint | N/A — mandatory complete-lock provenance gate | N/A | ⬜ pending |
| 01-01-02 | 02 | 2 | OPS-01, OPS-04 | T-01-01 | Packaged `skillscout` entry point and bounded fixture/error/failure contract collect, then fail only at the named missing behavior | e2e/red | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" build --no-sources && ! UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-01-03 | 02 | 2 | OPS-01, OPS-04 | T-01-01, T-01-02, T-01-08 | Happy path writes v1 state; one-descriptor controls pass; fixed bounded diagnostics omit raw/Pydantic/exception/secret/path input; `--fail-after generator` freezes a real interrupted v1 DB | e2e/security | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_dry_run.py && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-02-01 | 03 | 3 | OPS-01 | T-01-03 | Contracts reject extras; output and manifest hash preimages are non-circular and stable | unit | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_stage_contracts.py && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout/domain tests/test_stage_contracts.py` | ❌ W0 | ⬜ pending |
| 01-02-02 | 03 | 3 | OPS-01, OPS-04 | T-01-04 | A frozen CLI-produced v1 DB interrupted after Generator migrates transactionally to v2 and resumes at Validators with no prior-stage replay; rollback remains fail closed | integration | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_pipeline_resume.py && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout tests/test_pipeline_resume.py` | ❌ W0 | ⬜ pending |
| 01-02-03 | 03 | 3 | OPS-04 | T-01-05 | Resume reports reused stages, refuses a fourth retry for one digest, and grants a distinct budget only after input/producer/retry-policy change | CLI/integration | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_pipeline_resume.py tests/test_cli_dry_run.py && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout tests/test_pipeline_resume.py tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-03-01 | 04 | 4 | OPS-04 | T-01-06 | Remote-read and remote-write capabilities cannot register in Phase 1 dry-run | security | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_side_effect_policy.py && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout tests/test_side_effect_policy.py` | ❌ W0 | ⬜ pending |
| 01-03-02 | 04 | 4 | OPS-01, OPS-04 | T-01-07, T-01-08 | Tampered state and the expanded path/size/change/error disclosure matrix beyond the Walking Skeleton baseline fail closed | security/integration | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_state_integrity.py tests/test_cli_security.py tests/test_cli_dry_run.py && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout tests/test_state_integrity.py tests/test_cli_security.py` | ❌ W0 | ⬜ pending |
| 01-03-03 | 04 | 4 | OPS-01, OPS-04 | T-01-06 | Full acceptance proves no network access and reports zero remote writes | e2e | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check .` | ❌ W0 | ⬜ pending |

## Wave 0 Requirements

Plan 01 creates static infrastructure but does not execute project or dependency code:

- [ ] `pyproject.toml` — static name `skillscout`, version `0.1.0`, Python 3.13, exact `uv_build==0.11.29`, `build-backend = "uv_build"`, console entry point, pytest and Ruff config.
- [ ] `uv.lock` — generated only by the non-building/no-source/no-cache discovery command after Gate A; Gate B allows exactly one canonical first-party root `skillscout==0.1.0` with `source = { editable = "." }`, then requires registry-only sources for every other node.
- [ ] `tests/fixtures/pipeline/approved.json` — valid deterministic pipeline fixture.
- [ ] `tests/test_cli_dry_run.py` — unexecuted failing happy-path contract; minimum single-descriptor safety cases; closed-code/fixed-summary hostile canaries; and schema-v1 `--fail-after generator` behavior.
- [ ] `tests/conftest.py` — temporary state/output fixtures and deterministic clock/ID providers.

Walking Skeleton Plan 02 owns the first execution. After its GREEN suite, it uses its actual packaged CLI—not hand-authored SQL—to create and freeze `tests/fixtures/state/v1-cli.db` with Generator as the durable last checkpoint and no Validators attempt, plus `v1-cli-provenance.json`. Plans 03 and 04 create their remaining focused test files in the same task before implementing the behavior under test.

The order is: Plan 01 Gate A → verified repo-local bootstrap → static scaffold → non-building lock discovery → Gate B → stop Wave 1; Plan 02 exact attributed RED → GREEN Walking Skeleton → freeze interrupted v1 DB → first full-suite sample. No Wave-1 full-suite requirement may pull build/import/test ahead of Gate B.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Gate A: toolchain/direct identity approval | OPS-01, OPS-04 | GSD legitimacy seam returned SUS; the current host lacks approved uv/Python | Before bootstrap, verify Darwin/aarch64; uv `0.11.29` commit `901092e…`, Apple-Silicon archive SHA `61c04acc…8930e3` and attestation; upstream CPython `3.13.14`; distinct Astral build `20260623`, managed-runtime asset SHA `795a5aee…087d7`; and `uv-build==0.11.29`, `pydantic==2.13.4`, `pytest==9.1.1`, `ruff==0.15.21`. Match the full values in `01-RESEARCH.md`, record evidence, and approve or stop. |
| Gate B: complete lock approval | OPS-01, OPS-04 | External transitive identities and executable artifacts are unknown until safe resolution | Run only `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --no-build --no-sources --no-cache --managed-python --no-python-downloads --python 3.13.14`. Permit exactly one first-party root node with name `skillscout`, version `0.1.0`, source exactly editable `.`, and dependency metadata matching reviewed `pyproject.toml`; reject a missing/duplicate/mismatched root. For every other node, require reviewed PyPI registry source and reject Git/path/editable/workspace/direct-URL/alternate-registry sources. Review every external version, edge/marker and artifact URL/hash/size; approve exact lock bytes/hash or stop before sync/build/import/test. |

All product behaviors after the two supply-chain approvals have automated verification.

The RED command for `01-01-02` must be executed exactly as listed in the map. Its shell success is not sufficient evidence: retain pytest output and confirm the module collected successfully and failed at the named intended functional assertion. Exit due to import/collection/usage/no-tests errors (pytest 2/4/5), build failure, missing interpreter, dependency/bootstrap failure, or a mismatched Gate-B lock does not count as RED.

## Walking Skeleton v1 Freeze Handoff

After Task `01-01-03` is GREEN and before any v2 adapter edit, execute the schema-v1 CLI once against fresh paths using the exact prefix:

```text
! UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state tests/fixtures/state/v1-cli.db --output .tmp/v1-cli-out --fail-after generator
```

The raw CLI status must be `1` for the intentional interruption, not setup failure. Record the exact command, fixture/database SHA-256, `PRAGMA user_version=1`, run ID, Generator checkpoint, run status `interrupted`, row counts and absence of any Validators attempt in `v1-cli-provenance.json`; freeze both files before Plan 03 changes the adapter. Plan 03 tests copy the DB, migrate the copy, and place invocation canaries on Scout through Generator so resumption proves Validators is the first processor called.

## Final Phase Commands

Run from a repository root with fresh `.tmp` demo paths after confirming the current lock SHA-256 still equals Gate B:

```text
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" build --no-sources
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check .
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/demo.db --output .tmp/demo-out
! UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/resume.db --output .tmp/resume-out --fail-after generator
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/resume.db --output .tmp/resume-out
```

The happy run exits `0` with `planned_not_published` and zero remote writes. The intentional interruption exits `1` after durable Generator; its rerun exits `0`, begins processing at Validators, reports positive reuse and preserves reused hashes. The full suite additionally proves v1→v2 migration/rollback, retry exhaustion per digest, complete nullable telemetry, non-circular hashes, Walking Skeleton error canaries and fixture primitives, expanded Plan-04 disclosure/integrity coverage, and rejection of remote-read/write capabilities.

## Validation Sign-Off

- [x] Wave 1 terminates after static lock approval and has no full-suite requirement.
- [x] The exact attributed RED remains in Plan 02.
- [x] Full-suite sampling begins only after Wave 2 GREEN and continues after Waves 3–4.
- [x] Every post-Gate-B command repeats the verified repo-local uv path and all three inline managed-Python/no-download values.
- [x] Walking Skeleton owns minimum error sanitization, hostile canaries and `--fail-after generator`; Plan 04 owns the expanded matrix.
- [x] Plan 03 migrates a frozen CLI-produced interrupted v1 DB and proves resume begins at Validators.
- [x] No watch-mode flags are used; `nyquist_compliant: true` is set.
- [ ] Execution evidence captured.

**Approval:** planning contract revised 2026-07-16; execution pending
