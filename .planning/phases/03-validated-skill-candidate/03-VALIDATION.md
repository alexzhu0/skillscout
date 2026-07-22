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
| TBD-SC-A | TBD | 0/1 | VAL-01 | T-03-SC | Human approves `skills-ref` declaration and publisher/source provenance before any lock resolution, sync, import, or execution | human checkpoint | N/A — approval is a blocking human supply-chain decision | N/A | ⬜ pending |
| TBD-SC-B | TBD | 0/1 | VAL-01 | T-03-SC | Human approves every new registry-only node/artifact and exact `uv.lock` bytes before execution | human checkpoint | N/A — exact-lock approval is human-only | N/A | ⬜ pending |
| TBD-QUAL | TBD | TBD | QUAL-01, QUAL-02 | T-03-QUAL | Versioned 100-point qualification, stable checks, hard fails, and exact 74/75/76 plus confidence boundaries | unit/property matrix | `... pytest -q tests/test_qualification.py` | ❌ Wave 0 | ⬜ pending |
| TBD-GEN | TBD | TBD | GEN-01, GEN-02, GEN-03, GEN-04, GEN-05 | T-03-GEN, T-03-LINEAGE | Structured draft plus deterministic trusted rendering; closed paths/types/modes; no scripts, binaries, executable bits; exact provenance and identity reuse | unit + filesystem adversarial | `... pytest -q tests/test_skill_generation.py tests/test_phase3_pipeline.py` | ❌ Wave 0 | ⬜ pending |
| TBD-VAL | TBD | TBD | VAL-01, VAL-02, VAL-03 | T-03-VAL, T-03-TOCTOU | Pinned official validator signal plus closed custom structure, provenance, secret, injection, execution, reference, permission, and over-copy checks | integration + adversarial matrix | `... pytest -q tests/test_skill_validation.py` | ❌ Wave 0 | ⬜ pending |
| TBD-REVIEW | TBD | TBD | REV-01, REV-02, REV-03 | T-03-PI, T-03-REVIEW | Independent tool-less/store-false reviewer sees only four allowed artifacts, cannot emit edits, and gates exactly on clean validation + YES + confidence >= 0.80 | adapter + policy | `... pytest -q tests/test_openai_review.py tests/test_phase3_pipeline.py` | ❌ Wave 0 | ⬜ pending |
| TBD-E2E | TBD | TBD | QUAL-01..REV-03 | T-03-E2E | CLI happy path, every business rejection, retry/resume, exact reuse, zero unauthorized remote writes, and no raw repository text on durable surfaces | recorded-transport E2E | `... pytest -q tests/test_cli_validate_skill.py` | ❌ Wave 0 | ⬜ pending |

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
- [ ] Per-task map updated from TBD identifiers after plans are finalized
- [ ] `nyquist_compliant: true` set after validation audit

**Approval:** pending
