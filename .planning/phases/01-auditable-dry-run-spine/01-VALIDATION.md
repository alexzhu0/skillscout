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
| **Full suite command** | `uv run --locked pytest -q && uv run --locked ruff check . && uv lock --check` |
| **Estimated runtime** | <15 seconds on local fixtures |

## Sampling Rate

- **After every task commit:** Run the task's focused pytest command and Ruff on touched Python paths.
- **After every plan wave:** Run the full suite command.
- **Before `$gsd-verify-work`:** Full suite and both CLI demonstrations must be green.
- **Max feedback latency:** 15 seconds.
- Watch-mode flags are forbidden.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---|---:|---:|---|---|---|---|---|---|---|
| 01-01-01 | 01 | 1 | OPS-01, OPS-04 | T-01-SC | Exact runtime and packages are approved before install | human checkpoint | N/A — mandatory runtime/package provenance checkpoint | N/A | ⬜ pending |
| 01-01-02 | 01 | 1 | OPS-01, OPS-04 | T-01-01 | CLI fixture is bounded and strict | e2e/red | `uv run --locked pytest -q tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | OPS-01, OPS-04 | T-01-02 | Happy path writes real SQLite state and no remote output | e2e | `uv run --locked pytest -q tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | OPS-01 | T-01-03 | Contracts reject extras; output and manifest hash preimages are non-circular and stable | unit | `uv run --locked pytest -q tests/test_stage_contracts.py` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | OPS-01, OPS-04 | T-01-04 | Attempt telemetry, result and content-addressed manifest/checkpoint commit safely | integration | `uv run --locked pytest -q tests/test_pipeline_resume.py` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 2 | OPS-04 | T-01-05 | Failed run resumes, reports reused stages, and refuses a fourth retry | CLI/integration | `uv run --locked pytest -q tests/test_pipeline_resume.py tests/test_cli_dry_run.py` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 3 | OPS-04 | T-01-06 | Remote-read and remote-write capabilities cannot register in Phase 1 dry-run | security | `uv run --locked pytest -q tests/test_side_effect_policy.py` | ❌ W0 | ⬜ pending |
| 01-03-02 | 03 | 3 | OPS-01, OPS-04 | T-01-07 | Tampered state, unsafe paths and oversized JSON fail closed | security/integration | `uv run --locked pytest -q tests/test_state_integrity.py tests/test_cli_security.py` | ❌ W0 | ⬜ pending |
| 01-03-03 | 03 | 3 | OPS-01, OPS-04 | T-01-06 | Full acceptance proves no network access and reports zero remote writes | e2e | `uv run --locked pytest -q` | ❌ W0 | ⬜ pending |

## Wave 0 Requirements

Plan 01 establishes all test infrastructure before implementing the happy path:

- [ ] `pyproject.toml` — Python 3.13, console entry point, pytest and Ruff config.
- [ ] `uv.lock` — exact dependency resolution after human package verification.
- [ ] `tests/fixtures/pipeline/approved.json` — valid deterministic pipeline fixture.
- [ ] `tests/test_cli_dry_run.py` — failing happy-path acceptance test before implementation.
- [ ] `tests/conftest.py` — temporary state/output fixtures and deterministic clock/ID providers.

Plans 02 and 03 create their focused test files in the same task before implementing the behavior under test; no test path may be referenced after the task without being created first.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Runtime/package identity approval | OPS-01, OPS-04 | GSD legitimacy seam returned SUS for current package releases; the runtime is also downloaded externally | Before any install, compare CPython `3.13.14` against Python.org and `uv==0.11.29`, `pydantic==2.13.4`, `pytest==9.1.1`, `ruff==0.15.21` against their official PyPI owners/source links; approve or stop. |

All product behaviors after dependency approval have automated verification.

## Final Phase Commands

```text
uv lock --check
uv run --locked ruff check .
uv run --locked pytest -q
uv run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/demo.db --output .tmp/demo-out
uv run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/resume.db --output .tmp/resume-out --fail-after generator
uv run --locked skillscout dry-run --fixture tests/fixtures/pipeline/approved.json --state .tmp/resume.db --output .tmp/resume-out
```

The first dry-run exits `0` with `status=planned_not_published` and `remote_writes_attempted=0`. The fail-injected run exits `1`; its rerun exits `0`, reports a positive `reused_stage_count`, and preserves identical hashes for reused stage results. The full pytest suite additionally proves retry exhaustion, complete nullable attempt telemetry, non-circular hashes, and rejection of both remote-read and remote-write capabilities.

## Validation Sign-Off

- [x] All implementation tasks define an automated verification command or create their test first.
- [x] Sampling continuity has no three consecutive implementation tasks without automated verification.
- [x] Wave 0 paths are explicitly owned by Plan 01.
- [x] No watch-mode flags are used.
- [x] Target feedback latency is under 15 seconds.
- [x] `nyquist_compliant: true` is set.
- [ ] Execution evidence captured.

**Approval:** planning contract approved 2026-07-16; execution pending
