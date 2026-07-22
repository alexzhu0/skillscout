---
phase: 3
slug: validated-skill-candidate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-22
---

# Phase 3 — Validation Strategy

Every post-Gate-B3 dependency command starts with `sh tools/verify_phase3_gate_b3.sh`. The preflight reads the committed `config/supply-chain/phase3-gate-b3.lock.sha256`, compares it with exact `uv.lock` bytes, and exits before uv or package code can run on any mismatch.

## Test Infrastructure

All uv commands use the repository-local binary and managed Python with downloads disabled:

```text
UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"
```

| Property | Value |
|---|---|
| Framework | pytest 9.1.1 |
| Config | `pyproject.toml` strict pytest configuration |
| Lock preflight | `sh tools/verify_phase3_gate_b3.sh` |
| Quick run | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q <test-path>` |
| Full phase gate | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check . && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked python tools/verify_phase3_acceptance.py --package-root tests/fixtures/skills/valid-skill --discover-runtime-packages .tmp/phase3-acceptance` |
| Network policy | Recorded transports only; every unrecorded socket fails |

## Sampling Rate

- After each implementation task, run its exact focused command below.
- After each wave, run the full phase gate.
- Never use PATH uv, a floating lock, downloadable Python, watch mode, live GitHub, or live OpenAI.
- Mark a row green only from fresh command output after Gate B3.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement IDs | Threat Ref | Automated Command | File Exists | Status |
|---|---|---:|---|---|---|---|---|
| 03-01-01 | 03-01 | 1 | VAL-01 | T-03-SC | `N/A — blocking human Gate A3 package legitimacy decision` | N/A | ⬜ pending |
| 03-01-02 | 03-01 | 1 | VAL-01 | T-03-SC | `UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && grep -q '"skills-ref==0.1.1"' pyproject.toml && grep -q 'name = "skills-ref"' uv.lock` | ✅ existing config | ⬜ pending |
| 03-01-03 | 03-01 | 1 | VAL-01 | T-03-SC, T-03-01-DG | `N/A — blocking human Gate B3 exact graph and lock-byte decision` | N/A | ⬜ pending |
| 03-01-04 | 03-01 | 1 | VAL-01 | T-03-01-DG | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_lock_preflight.py && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check tests/test_phase3_lock_preflight.py` | ❌ Wave 0 | ⬜ pending |
| 03-02-01 | 03-02 | 2 | QUAL-01, QUAL-02 | T-03-QUAL | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_qualification.py -k 'rubric or threshold or order or contract'` | ❌ Wave 0 | ⬜ pending |
| 03-02-02 | 03-02 | 2 | QUAL-01, QUAL-02 | T-03-QUAL | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_qualification.py && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout/domain/qualification.py tests/test_qualification.py` | ❌ Wave 0 | ⬜ pending |
| 03-03-01 | 03-03 | 2 | GEN-04, GEN-05 | T-03-LINEAGE | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_generation.py tests/test_lineage.py -k 'contract or lineage or artifact_id or package_digest or provenance'` | ❌ Wave 0 | ⬜ pending |
| 03-03-02 | 03-03 | 2 | GEN-01, GEN-02, GEN-03, GEN-04, GEN-05 | T-03-GEN | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_generation.py tests/test_lineage.py` | ❌ Wave 0 | ⬜ pending |
| 03-03-03 | 03-03 | 2 | GEN-01, GEN-03 | T-03-GEN | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_generate.py && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout/domain/skill_artifacts.py src/skillscout/adapters/skill_packages.py src/skillscout/adapters/openai_generate.py tests/test_skill_generation.py tests/test_lineage.py tests/test_openai_generate.py` | ❌ Wave 0 | ⬜ pending |
| 03-04-01 | 03-04 | 3 | GEN-02, VAL-01, VAL-03 | T-03-VAL, T-03-TOCTOU | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py -k 'admission or official or runtime_failure'` | ❌ Wave 0 | ⬜ pending |
| 03-04-02 | 03-04 | 3 | GEN-04, VAL-01, VAL-02 | T-03-VAL | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py -k 'structure or reference or progressive or provenance or binding'` | ❌ Wave 0 | ⬜ pending |
| 03-04-03 | 03-04 | 3 | GEN-02, GEN-03, VAL-02, VAL-03 | T-03-VAL | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout/domain/validation.py src/skillscout/adapters/skills_ref.py tests/test_skill_validation.py` | ❌ Wave 0 | ⬜ pending |
| 03-05-01 | 03-05 | 4 | REV-02, REV-03 | T-03-REVIEW | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_review.py -k 'schema or gate or confidence or decision'` | ❌ Wave 0 | ⬜ pending |
| 03-05-02 | 03-05 | 4 | REV-01, REV-02, REV-03 | T-03-PI, T-03-REVIEW | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_review.py && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout/domain/review.py src/skillscout/adapters/openai_review.py tests/test_openai_review.py` | ❌ Wave 0 | ⬜ pending |
| 03-06-01 | 03-06 | 5 | GEN-05 | T-03-06-SEL, T-03-06-LEDGER | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k 'subject or profile or summary or producer or execution_authority' tests/test_phase2_pipeline.py` | ❌ Wave 0 | ⬜ pending |
| 03-06-02 | 03-06 | 5 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-06-AUTH | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k 'processor or selector or cascade or call_count or telemetry'` | ❌ Wave 0 | ⬜ pending |
| 03-06-03 | 03-06 | 5 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-06-AUTH, T-03-06-LEDGER | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py tests/test_phase2_pipeline.py tests/test_pipeline_resume.py && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check src/skillscout/domain/subjects.py src/skillscout/domain/models.py src/skillscout/application/phase3.py src/skillscout/application/pipeline.py src/skillscout/adapters/state.py tests/test_phase3_pipeline.py` | ❌ Wave 0 | ⬜ pending |
| 03-07-01 | 03-07 | 6 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-E2E | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_validate_skill.py -k 'parser or subject or lineage or execution_authority or non_echo or summary' tests/test_cli_security.py` | ❌ Wave 0 | ⬜ pending |
| 03-07-02 | 03-07 | 6 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-E2E, T-03-07-R | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_validate_skill.py` | ❌ Wave 0 | ⬜ pending |
| 03-07-03 | 03-07 | 6 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-E2E, T-03-07-ID, T-03-07-NET | `sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check . && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && sh tools/verify_phase3_gate_b3.sh && UV_CACHE_DIR="$PWD/.tools/uv-cache" UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked python tools/verify_phase3_acceptance.py --package-root tests/fixtures/skills/valid-skill --discover-runtime-packages .tmp/phase3-acceptance` | ❌ Wave 0 | ⬜ pending |

## Wave 0 Requirements

- [ ] Gate A3 approval of exact `skills-ref==0.1.1` provenance and non-additions.
- [ ] Gate B3 approval of every transitive artifact and exact lock bytes.
- [ ] Committed Gate-B3 digest, dependency-free preflight, and its mismatch-before-execution tests.
- [ ] Qualification, lineage, generation, validation, Reviewer, pipeline, CLI, and acceptance-tool test modules named in the map.
- [ ] Same-identity rerun fixtures for every qualification, generation, validation, review, and success terminal branch.
- [ ] Independent mutation fixtures for every configured execution-authority dimension and actual-model/finalized-branch mismatch.
- [ ] Approved title/evidence-path lineage remap plus stale, tampered, collision, multiple-match, repository-mismatch, and ambiguous mapping fixtures.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Exact evidence |
|---|---|---|---|
| Gate A3 package legitimacy | VAL-01 | Distribution/source/version/publisher trust is a human supply-chain decision | Task 03-01-01 approval record |
| Gate B3 executable graph | VAL-01 | Every transitive artifact and exact lock bytes require human disposition | Task 03-01-03 approval plus committed digest used by Task 03-01-04 |

## Validation Sign-Off

- [ ] Every post-Gate-B3 uv/import/test/validator command is immediately preceded by the committed lock preflight.
- [ ] All 20 final task IDs have exact automated commands or explicit human-only rationale.
- [ ] Requirement cells use only explicit IDs and cover all 13 Phase 3 requirements.
- [ ] Full phase gate includes approved-lock equality, full pytest, Ruff, lock check, capability scan, package tree/mode scan, secret scan, and provenance/self-hash checks.
- [ ] `wave_0_complete: true`, `nyquist_compliant: true`, and `status: validated` are set only after fresh evidence.

**Approval:** pending
