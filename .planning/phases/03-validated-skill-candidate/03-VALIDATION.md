---
phase: 3
slug: validated-skill-candidate
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `03-RESEARCH.md`; exact task identifiers are finalized with the Phase 3 plans.

---

## Test Infrastructure

All commands run from the repository root with the repository-local uv binary. `uv` on `PATH`, activated environments, floating dependencies, and downloaded Python interpreters are not validation evidence:

```text
UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"
```

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` (`testpaths = ["tests"]`, strict config/markers) |
| **Quick run command** | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q <task-specific-test>` |
| **Full suite command** | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check . && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check` |
| **Estimated runtime** | ~30 seconds on local fixtures; GitHub/OpenAI transports mocked and network forbidden |

---

## Sampling Rate

- **After every task commit:** Run the task's focused pytest module(s) and Ruff on touched Python paths.
- **After every plan wave:** Run the full suite command above.
- **Before `$gsd-verify-work`:** Full suite, lock check, capability sweep, artifact secret scan, and package permission scan must be green.
- **Max feedback latency:** 30 seconds. Watch-mode flags are forbidden.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 03-01 | 1 | VAL-01 | T-03-SC | Gate A3 approves exact direct declaration, wheel digest, provenance discrepancies and non-additions before lock discovery | human checkpoint | N/A — approval is a blocking human supply-chain decision | N/A | ⬜ pending |
| 03-01-02 | 03-01 | 1 | VAL-01 | T-03-SC | Registry-only non-building lock discovery produces the complete Gate B3 inventory without sync/import/test | lock integrity | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check` | ✅ existing config | ⬜ pending |
| 03-01-03 | 03-01 | 1 | VAL-01 | T-03-SC | Gate B3 approves every new node/artifact and exact `uv.lock` SHA-256 before execution | human checkpoint | N/A — exact-lock approval is human-only | N/A | ⬜ pending |
| 03-02-01 | 03-02 | 2 | QUAL-01, QUAL-02 | T-03-QUAL | Frozen 100-point ordered rubric/report and exact 74/75/76 threshold behavior | unit/property matrix | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_qualification.py -k 'rubric or threshold or order or contract'` | ❌ Wave 0 | ⬜ pending |
| 03-02-02 | 03-02 | 2 | QUAL-01, QUAL-02 | T-03-QUAL | WorkflowSpec/upstream binding and complete confidence/unauthorized-execution hard-failure matrix | unit/property matrix | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_qualification.py` | ❌ Wave 0 | ⬜ pending |
| 03-03-01 | 03-03 | 2 | GEN-04, GEN-05 | T-03-LINEAGE | Strict semantic/provenance contracts and separate lineage/artifact/package identities without self-hash | unit | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_generation.py -k 'contract or lineage or artifact_id or package_digest or provenance'` | ❌ Wave 0 | ⬜ pending |
| 03-03-02 | 03-03 | 2 | GEN-01, GEN-02, GEN-03, GEN-04, GEN-05 | T-03-GEN | Deterministic trusted rendering/materialization, closed paths/types/modes and exact quote/copy boundaries | filesystem adversarial | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_generation.py` | ❌ Wave 0 | ⬜ pending |
| 03-03-03 | 03-03 | 2 | GEN-01, GEN-03 | T-03-GEN | One-call tool-less/store-false Generator with strict schema, closed outcomes and header-only key | adapter contract | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_generate.py` | ❌ Wave 0 | ⬜ pending |
| 03-04-01 | 03-04 | 3 | GEN-02, VAL-01, VAL-03 | T-03-VAL, T-03-TOCTOU | Exact descriptor/manifest admission precedes pinned official validator; exceptions fail closed | integration/filesystem | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py -k 'admission or official or runtime_failure'` | ❌ Wave 0 | ⬜ pending |
| 03-04-02 | 03-04 | 3 | GEN-04, VAL-01, VAL-02 | T-03-VAL | Structure, progressive disclosure, references, provenance and exact source-binding checks | integration/fixture | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py -k 'structure or reference or progressive or provenance or binding'` | ❌ Wave 0 | ⬜ pending |
| 03-04-03 | 03-04 | 3 | GEN-02, GEN-03, VAL-02, VAL-03 | T-03-VAL | Secret/injection/execution/tool/URL/copy policy and deterministic error/warning/info report invariants | adversarial matrix | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py` | ❌ Wave 0 | ⬜ pending |
| 03-05-01 | 03-05 | 4 | REV-02, REV-03 | T-03-REVIEW | Judge-only schema and exact clean+YES+0.799/0.800 deterministic eligibility matrix | unit/schema | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_review.py -k 'schema or gate or confidence or decision'` | ❌ Wave 0 | ⬜ pending |
| 03-05-02 | 03-05 | 4 | REV-01, REV-02, REV-03 | T-03-PI, T-03-REVIEW | Fresh one-call Reviewer sees exactly four inert inputs, cannot emit files and returns closed outcomes | adapter/injection | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_review.py` | ❌ Wave 0 | ⬜ pending |
| 03-06-01 | 03-06 | 5 | GEN-05 | T-03-06-SEL | Full workflow-fingerprint selector, additive phase3-v1 profile and bounded terminal contract | integration | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k 'subject or profile or summary or producer'` | ❌ Wave 0 | ⬜ pending |
| 03-06-02 | 03-06 | 5 | QUAL-01..REV-03 | T-03-06-AUTH | Closed stage cascade, WorkflowSpec-only boundary, exact business-rejection call counts and telemetry | integration | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k 'processor or selector or cascade or call_count or telemetry'` | ❌ Wave 0 | ⬜ pending |
| 03-06-03 | 03-06 | 5 | QUAL-01..REV-03 | T-03-06-AUTH, T-03-06-LEDGER | Closed root, retry/resume, corruption refusal and exact zero-call completed reuse | integration/security | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py tests/test_phase2_pipeline.py tests/test_pipeline_resume.py` | ❌ Wave 0 | ⬜ pending |
| 03-07-01 | 03-07 | 6 | QUAL-01..REV-03 | T-03-E2E | Safe build-candidate command, input-before-state and non-echo boundary | CLI/security | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_validate_skill.py -k 'parser or subject or non_echo or summary' tests/test_cli_security.py` | ❌ Wave 0 | ⬜ pending |
| 03-07-02 | 03-07 | 6 | QUAL-01..REV-03 | T-03-E2E | Happy path, all business rejections, resume, exact reuse, zero remote writes and durable canary sweeps | recorded-transport E2E | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_validate_skill.py` | ❌ Wave 0 | ⬜ pending |
| 03-07-03 | 03-07 | 6 | QUAL-01..REV-03 | T-03-E2E | Exact-lock full suite, Ruff, lock/capability/package scans and truthful validation closeout | full phase gate | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && ... run --locked ruff check . && ... lock --check` | ✅ infrastructure | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Human Gate A3 for the exact `skills-ref` declaration and package legitimacy; no dependency resolution or execution before approval.
- [ ] Non-building registry-only lock discovery followed by human Gate B3 approval of every new node/artifact and exact lock hash; no sync/import/test before approval.
- [ ] `tests/test_qualification.py` with score, hard-fail, stable-order/version, 74/75/76, 0.699/0.700, two-step, source-execution, and evidence fixtures.
- [ ] `tests/test_skill_generation.py` with deterministic rendering, slug collisions, provenance, permissions, no scripts/binaries, and quote-limit fixtures.
- [ ] `tests/test_skill_validation.py` with valid official fixture plus missing/mismatched frontmatter, broken/deep/orphan references, symlink/hard-link/TOCTOU, executable mode, binary, secret, injection, URL/download-execute, missing/hash-mismatched provenance, and over-copy cases.
- [ ] `tests/test_openai_generate.py` with parsed/refusal/incomplete/schema-invalid/429/500 recorded responses.
- [ ] `tests/test_openai_review.py` with YES, NO, 0.799, 0.800, refusal, incomplete, schema-invalid, 429, and 500 responses.
- [ ] `tests/test_phase3_pipeline.py` with closed profile/root, REMOTE_READ ceiling, skip cascade, retry, resume, and completed-run reuse.
- [ ] `tests/test_cli_validate_skill.py` with happy path and every business rejection, exact GitHub/OpenAI call counts, and zero remote writes.
- [ ] Reuse the seven Phase 2 injection fixtures and canaries; add generated-artifact and Reviewer delimiter variants.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Gate A3 package legitimacy approval | VAL-01 | The `skills-ref` distribution/source/version discrepancy and publisher trust are human supply-chain decisions | Review official repository, PyPI metadata, exact declared version, direct dependency rationale, and explicit non-additions; approve or reject before lock discovery. |
| Gate B3 exact lock approval | VAL-01 | Transitive packages and artifact hashes define the executable graph | Review every new registry-only node/source/artifact hash and approve the exact `uv.lock` SHA-256 before any sync, import, test, or validator execution. |

---

## Validation Sign-Off

- [ ] All finalized tasks have `<automated>` verification or an explicit human checkpoint
- [ ] Sampling continuity: no three consecutive implementation tasks without automated verification
- [ ] Wave 0 covers every missing fixture/test and the two supply-chain approvals
- [ ] No watch-mode flags or real network in automated tests
- [ ] Feedback latency < 30 seconds
- [x] Per-task map updated from TBD identifiers after plans are finalized
- [ ] `nyquist_compliant: true` set after validation audit

**Approval:** pending
