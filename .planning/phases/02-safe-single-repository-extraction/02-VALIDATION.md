---
phase: 2
slug: safe-single-repository-extraction
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-21
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded by plan-phase; the Per-Task Verification Map is populated once Phase 2 plans exist.

---

## Test Infrastructure

All commands run from the repository root with the Phase 1 canonical uv prefix; `PATH`, activated environments and previously exported variables are not validation evidence:

```text
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"
```

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q <task-specific-test>` |
| **Full suite command** | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check . && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" build --no-sources` |
| **Estimated runtime** | ~15 seconds on local fixtures (GitHub/OpenAI calls mocked — no network) |

---

## Sampling Rate

- **After every task commit:** Run the task's focused pytest command plus Ruff on touched Python paths.
- **After every plan wave:** Run the full suite command above.
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** 15 seconds. Watch-mode flags are forbidden.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 02-01 | 1 | — (supply chain) | T-02-01-SC | Gate A2: human approves exactly `httpx==0.28.1` + `openai==2.46.0` before any resolution | human checkpoint | N/A — human-only provenance decision blocking before new dependency bytes | N/A | ⬜ pending |
| 02-01-02 | 02-01 | 1 | FILT-01..03, READ-03, READ-05, EXTR-02, EXTR-03 | T-02-01-IN, T-02-01-CT | Two pins applied; non-building lock discovery; all frozen contracts landed unexecuted; three sanctioned Phase 1 test amendments | static source assertions | `grep -q '"httpx==0.28.1"' pyproject.toml && grep -q '"openai==2.46.0"' pyproject.toml && test -s uv.lock && grep -q 'name = "httpx"' uv.lock && grep -q 'name = "openai"' uv.lock && ! grep -rn "^import httpx\|^from httpx\|^import openai\|^from openai" src/skillscout/` | ➕ created by task | ⬜ pending |
| 02-01-03 | 02-01 | 1 | — (supply chain) | T-02-01-SC | Gate B2: human approves every new registry-only node/artifact and the exact new lock SHA-256 before execution | human checkpoint | N/A — human-only transitive-graph and exact-lock approval | N/A | ⬜ pending |
| 02-01-04 | 02-01 | 1 | FILT-01..03, READ-03, READ-05, EXTR-02, EXTR-03 | T-02-01-CT | Contract suite (subjects, filter matrix, reading predicates, extraction schema, fingerprint, boundary validation) plus full Phase 1 regression green | contract unit | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase2_contracts.py tests/test_stage_contracts.py tests/test_phase1_gap_closure.py tests/test_cli_security.py` | ➕ created by task | ⬜ pending |
| 02-02-01 | 02-02 | 2 | FILT-03 (mechanism), READ-01 (mechanism) | T-02-02-ID | Profile slice with global indices, runtime-only context, telemetry into attempt/envelope/hash, COMPLETED terminal with durable summary | pipeline integration | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase2_pipeline.py tests/test_pipeline_resume.py tests/test_side_effect_policy.py tests/test_state_integrity.py` | ➕ created by task | ⬜ pending |
| 02-02-02 | 02-02 | 2 | READ-01 | T-02-02-CR, T-02-02-SS, T-02-02-DOS | Closed GitHub adapter: SHA-in-URL invariant, total error mapping, bounded Retry-After, canary-token header confinement | adapter (MockTransport) | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_github_adapter.py` | ➕ created by task | ⬜ pending |
| 02-02-03 | 02-02 | 2 | FILT-01, FILT-02, FILT-03 | T-02-02-EOP | Scout pin/snapshot, filter rule matrix with license boundaries, skip cascade with zero downstream calls, REMOTE_READ-capped composition root | processor + policy | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_scout_filter.py tests/test_phase2_pipeline.py tests/test_github_adapter.py` | ➕ created by task | ⬜ pending |
| 02-03-01 | 02-03 | 3 | READ-02, READ-03, READ-04 | T-02-03-DOS | Fixed tier order, five budgets at ±1, early stop, complete read record, memory-only bundle | unit + integration | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_reader.py` | ➕ created by task | ⬜ pending |
| 02-03-02 | 02-03 | 3 | READ-05, READ-06 | T-02-03-PT, T-02-03-SM, T-02-03-EX, T-02-03-ID | Full rejection matrix with never-fetched proofs, hash-verified hydration, no-execution sweep and runtime proof | matrix + sweep + runtime | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_reader.py tests/test_phase1_gap_closure.py` | ➕ created by task | ⬜ pending |
| 02-04-01 | 02-04 | 4 | EXTR-01, SEC-01 | T-02-04-PI, T-02-04-SX | Tool-less store=false request with Pydantic-generated strict schema; four outcome classes; telemetry | adapter (MockTransport) | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_extract.py` | ➕ created by task | ⬜ pending |
| 02-04-02 | 02-04 | 4 | EXTR-01, EXTR-02, EXTR-03, EXTR-04, SEC-01 | T-02-04-PI, T-02-04-CM, T-02-04-COST | Boundary validation drops fabricated/tainted workflows; seven-class injection corpus; full-text and secret canary disciplines | security | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_extractor_boundary.py tests/test_openai_extract.py tests/test_reader.py` | ➕ created by task | ⬜ pending |
| 02-04-03 | 02-04 | 4 | EXTR-02, EXTR-04, SEC-01 | T-02-04-LK | extract-repo E2E: happy path COMPLETED, resume with unchanged Scout/Filter call counts and one total LLM call, zero-call idempotent rerun, INVALID_SUBJECT closure | CLI end-to-end | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_extract_repo.py tests/test_cli_security.py tests/test_extractor_boundary.py` | ➕ created by task | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New dependency pins (`httpx==0.28.1`, `openai==2.46.0`) admitted only through the Phase 1 two-gate lock-approval ceremony before any import — Plan 02-01 Tasks 02-01-01/02-01-02/02-01-03 (Gate A2 → non-building discovery → Gate B2); see 02-RESEARCH.md finding 3.
- [ ] `tests/fixtures/` GitHub/OpenAI transport stubs (httpx `MockTransport`; no VCR library) for deterministic pinned-SHA reads and extraction responses — `tests/recorded_transport.py` plus `tests/fixtures/github/` (Plan 02-02 Tasks 02-02-02, Plan 02-03) and `tests/fixtures/openai/` + `tests/fixtures/injection/` (Plan 02-04 Tasks 02-04-01/02-04-02).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Optional live smoke run against one real public repo | READ-01 | Requires network + credentials; the automated suite is fully credential-free | Run the documented CLI against a chosen public repo and inspect the stage ledger output. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
