---
phase: 3
slug: validated-skill-candidate
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 3 — Validation Strategy

> Per-task validation contract for the validated local Skill candidate phase.
> Gate A3 and Gate B3 are non-auto-approvable. After Gate B3, every command that can import or execute project/dependency code starts with the dependency-free exact-lock preflight.

---

## Test Infrastructure

All commands run from the repository root. The approved Phase 3 lock is checked before every post-B3 dependency-backed command. The canonical uv invocation is repeated literally; `PATH`, an activated environment, and previously exported variables are not evidence.

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x |
| **Config file** | `pyproject.toml` |
| **Gate B3 preflight** | `sh tools/verify_phase3_gate_b3.sh` |
| **Quick run command** | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_candidate_source.py tests/test_candidate_authority.py tests/test_qualification.py tests/test_skill_generation.py tests/test_skill_validation.py tests/test_openai_review.py tests/test_phase3_pipeline.py` |
| **Full suite command** | `PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_phase3_validation_map.py && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_validation_map.py && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" build --no-sources && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked python tools/verify_phase3_acceptance.py && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check . && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && sh tools/verify_phase3_gate_b3.sh` |
| **Network policy** | Tests use deterministic injected transports and local fixtures; no live GitHub/OpenAI/PyPI calls |
| **Estimated runtime** | Focused task checks under 60 seconds; final suite measured during execution |

---

## Command Admission and Closed Grammar

`tools/verify_phase3_validation_map.py` is a read-only, standard-library-only release gate. Before parsing, it must admit `03-01-PLAN.md` through `03-14-PLAN.md` and this file with bounded strict UTF-8 no-follow regular-file reads: `lstat`, `O_RDONLY | O_NOFOLLOW | O_CLOEXEC`, path/descriptor identity comparison, cap-plus-one descriptor read, and post-read path/descriptor stability. Symlinked, non-regular, oversized, swapped, malformed, or duplicate-table planning inputs fail closed.

The checker owns a finite `EXPECTED_TASK_COMMANDS` mapping and an `EXPECTED_RELEASE_COMMAND`; agreement between mutable PLAN and map text is insufficient. Every decoded command is a single physical line made only of its approved literal segments joined by the exact ` && ` delimiter. It rejects `||`, `;`, `|`, `|&`, any `&` outside that delimiter, CR/LF and other controls, backticks, `$(`, parameter substitution, redirection, process substitution, heredoc forms, comments, escape sequences, and unapproved quoting or expansion. The only non-B3 task-command exceptions are fixed and exact:

| Task ID | Exact allowed command |
|---------|-----------------------|
| 03-01-01 | `N/A — this is a non-auto-approvable human supply-chain decision.` |
| 03-02-01 | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --no-build --no-sources --no-cache --managed-python --no-python-downloads --python 3.13.14 && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" tree --locked --package skills-ref` |
| 03-03-01 | `git diff --check -- pyproject.toml uv.lock` |

The dependency-free map self-check is allowed only as the initial segment of the canonical 03-14-02/Full suite release command. Every dependency-backed segment immediately follows the exact Gate B3 preflight, and full pytest is immediately followed by the terminal Gate B3 postflight.

---

## Sampling Rate

- **After every task commit:** Run that task's literal command from the table.
- **After every plan wave:** Run the Quick run command when the referenced files exist.
- **Before `/gsd:verify-work`:** Run the Full suite command exactly.
- **Supply-chain invariant:** Gate A3 precedes lock resolution. Gate B3 precedes every dependency-backed test/import/validator command. Any `uv.lock` byte change invalidates B3.
- **Max feedback latency:** Focused task checks target under 60 seconds; no watch-mode flags.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 03-01 | 1 | VAL-01 | T-03-SC, T-03-01, T-03-02 | Gate A3 reviews exact `skills-ref==0.1.1` identity, audited wheel hash, and anomalies before resolution | human checkpoint | N/A — this is a non-auto-approvable human supply-chain decision. | N/A | ⬜ pending |
| 03-02-01 | 03-02 | 2 | VAL-01 | T-03-SC, T-03-03, T-03-04 | Exact managed-Python no-build/no-source/no-cache lock discovery plus complete Gate B3 command/diff/digest/tree/artifact evidence; no install/import/test/entrypoint | lock metadata | `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --no-build --no-sources --no-cache --managed-python --no-python-downloads --python 3.13.14 && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" tree --locked --package skills-ref` | `pyproject.toml`, `uv.lock` | ⬜ pending |
| 03-03-01 | 03-03 | 3 | VAL-01 | T-03-SC, T-03-05, T-03-06 | Gate B3 reviews every transitive artifact and binds one exact `uv.lock` digest | human checkpoint | `git diff --check -- pyproject.toml uv.lock` | N/A | ⬜ pending |
| 03-04-01 | 03-04 | 4 | VAL-01 | T-03-SC, T-03-07, T-03-08 | Exact lowercase hash parsing plus bounded no-follow stable descriptor reads block missing/symlink/non-regular/oversized/malformed/byte-different lock before a downstream sentinel executes | preflight unit | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_lock_preflight.py` | `tests/test_phase3_lock_preflight.py` | ⬜ pending |
| 03-05-01 | 03-05 | 5 | GEN-04, GEN-05 | T-03-09, T-03-11 | Complete source/execution authority; every reuse-sensitive field changes identity | authority unit | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_candidate_authority.py` | `tests/test_candidate_authority.py` | ⬜ pending |
| 03-05-02 | 03-05 | 5 | GEN-05 | T-03-10 | Only one exact approved prior binding retains lineage; all ambiguity closes | lineage unit | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_lineage.py` | `tests/test_lineage.py` | ⬜ pending |
| 03-06-01 | 03-06 | 6 | GEN-04, GEN-05 | T-03-13, T-03-15 | Read-only Phase 2 query reverifies canonical chain and never mutates upstream state | adapter integration | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_candidate_source.py -k phase2_query` | `tests/test_candidate_source.py` | ⬜ pending |
| 03-06-02 | 03-06 | 6 | GEN-04, GEN-05 | T-03-12, T-03-14 | Descriptor effective-UID/private-mode/single-link admission, O_NOFOLLOW/O_NONBLOCK/O_CLOEXEC, complete lstat/fstat identity, cap-plus-one read, post-read stability, exact canonical JSON, hostile-owner/permission/hard-link/swap/FIFO/symlink/oversize/malformed/no-echo matrix, plus deterministic sibling isolation | boundary security | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_candidate_source.py` | `tests/test_candidate_source.py` | ⬜ pending |
| 03-07-01 | 03-07 | 6 | QUAL-01 | T-03-17 | Five deterministic checks plus the closed steps/I-O/evidence/credential/destructive/bypass/injection/approval/execution hard-failure matrix | policy unit | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_qualification.py -k checks` | `tests/test_qualification.py` | ⬜ pending |
| 03-07-02 | 03-07 | 6 | QUAL-02 | T-03-16, T-03-18 | Exact 75/no-hard-failure rule and report directly bound to fingerprint, WorkflowSpec authority, execution authority, and schema/policy | report unit | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_qualification.py` | `tests/test_qualification.py` | ⬜ pending |
| 03-08-01 | 03-08 | 7 | GEN-01, GEN-02, GEN-04, GEN-05 | T-03-20, T-03-21 | domain/canonical.py owns distinct draft/generation-authority identity and post-provenance rendered path/hash/mode/size package identity; sole anchored materializer contract is reserved | contract unit | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_generation.py -k contracts` | `tests/test_skill_generation.py` | ⬜ pending |
| 03-08-02 | 03-08 | 7 | GEN-01, GEN-03, GEN-04 | T-03-19, T-03-22 | Tool-free store=false strict Generator with OpenAI max_retries=0 and exactly one raw Responses request per parsed/failure/429/500 adapter invocation | adapter transport | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_generate.py` | `tests/test_openai_generate.py` | ⬜ pending |
| 03-08-03 | 03-08 | 7 | GEN-01, GEN-02, GEN-03, GEN-04, GEN-05 | T-03-20, T-03-21 | Deterministic docs-only renderer plus sole retained-lock/fixed-mode/create-new-temp/atomic-restore/leaf-and-directory-fsync materializer; completed reuse bypasses it | renderer + durability | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_generation.py` | `tests/test_skill_generation.py` | ⬜ pending |
| 03-09-01 | 03-09 | 8 | VAL-01 | T-03-23, T-03-26 | Exact regular-file workspace admission and sole approved official-validator adapter without candidate execution | admission + adapter integration | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py -k "official or admission"` | `tests/test_skill_validation.py` | ⬜ pending |
| 03-09-02 | 03-09 | 8 | GEN-02, GEN-03, GEN-04, VAL-01, VAL-02 | T-03-23, T-03-24 | Local broken/orphan/deep/progressive structure plus secrets, execution, tools, injection, URLs, provenance, modes, and over-copying checks | structural + security matrix | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py -k "local_structure or local_policy"` | `tests/test_skill_validation.py` | ⬜ pending |
| 03-09-03 | 03-09 | 8 | VAL-03 | T-03-25 | Immutable report directly binds fingerprint, WorkflowSpec/execution authority, renderer/report schema, both identity layers, admission, validator, and policies | report integration | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_skill_validation.py` | `tests/test_skill_validation.py` | ⬜ pending |
| 03-10-01 | 03-10 | 9 | REV-02, REV-03 | T-03-28, T-03-29 | Judge-only schema and exact zero-errors plus YES plus confidence-at-least-0.80 rule | domain unit | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_review.py -k domain` | `tests/test_openai_review.py` | ⬜ pending |
| 03-10-02 | 03-10 | 9 | REV-01, REV-02 | T-03-27, T-03-28 | Canonical four-section user-role-only Reviewer envelope in exact order with fresh non-colliding delimiters, zero developer payload bytes, OpenAI max_retries=0, and one raw request per invocation | adapter transport | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_review.py -k adapter` | `tests/test_openai_review.py` | ⬜ pending |
| 03-10-03 | 03-10 | 9 | GEN-04, GEN-05, VAL-03, REV-03 | T-03-29, T-03-30 | Attestation owns raw review evidence; terminal owns eligibility policy, lineage/review statuses, Generator evidence, and exact branch matrix | attestation unit | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_openai_review.py` | `tests/test_openai_review.py` | ⬜ pending |
| 03-11-01 | 03-11 | 10 | GEN-05, VAL-03, REV-03 | T-03-31, T-03-34 | Closed Phase 3 stage/result/checkpoint chain with strict CandidateStageCheckpointV1 output-hash and previous/next continuity, isolated from global profiles | domain chain | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k domain_chain` | `tests/test_phase3_pipeline.py` | ⬜ pending |
| 03-11-02 | 03-11 | 10 | GEN-05, VAL-03, REV-03 | T-03-31, T-03-32, T-03-34 | Additive isolated phase3_checkpoints ledger recomputes result output/checkpoint hashes, detects checkpoint tampering, and atomically binds external evidence | state integration | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k state_ledger` | `tests/test_phase3_pipeline.py` | ⬜ pending |
| 03-11-03 | 03-11 | 10 | GEN-05, VAL-03, REV-03 | T-03-32, T-03-33 | DescriptorAnchoredCompletedCandidateProjector uses existing lock + bounded O_RDONLY/O_NOFOLLOW DB snapshot + query-only :memory: SQLite + descriptor artifacts; all 12 branches preserve full DB/WAL/SHM/lock/artifact/output path-byte-lstat snapshots under zero-write sentinels, while mutable resume still writes | reuse integration | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k exact_reuse` | `tests/test_phase3_pipeline.py` | ⬜ pending |
| 03-12-01 | 03-12 | 11 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-35, T-03-37 | Source/complete authority precede separate CompletedCandidateProjector; completed hit bypasses normal state/output, only clean miss may open MutableCandidateStateFactory, integrity failure never falls back; owner constants remain non-overridable | composition integration | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k composition_boundary` | `tests/test_phase3_pipeline.py` | ⬜ pending |
| 03-12-02 | 03-12 | 11 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-36 | Exact cascade, checkpoint output-hash continuity, runner-owned retries, one raw request per adapter attempt, 12 terminal branches, and terminal-owned evidence | pipeline matrix | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py -k terminal_cascade` | `tests/test_phase3_pipeline.py` | ⬜ pending |
| 03-12-03 | 03-12 | 11 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-35, T-03-37, T-03-38 | Resume verifies checkpoints and retains mutable writes; all-branch completed reuse uses descriptor projector with zero file-SQLite/WAL/SHM/mutation/materialization calls and identical complete path-byte-lstat snapshots; 429/500 raw counts equal runner attempts | pipeline integration | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_pipeline.py` | `tests/test_phase3_pipeline.py` | ⬜ pending |
| 03-13-01 | 03-13 | 12 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-39, T-03-42 | argparse CLI covers pre-run failure, mutable checkpoint resume through anchored materialization, and completed-first descriptor projection with alternate output absent plus identical DB/WAL/SHM/lock/artifact/output full snapshots | CLI end-to-end | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_validate_skill.py` | `tests/test_cli_validate_skill.py` | ⬜ pending |
| 03-13-02 | 03-13 | 12 | GEN-02, GEN-04, VAL-02, REV-01 | T-03-39, T-03-40, T-03-41, T-03-42 | Unsafe paths/secrets/execution capabilities remain unreachable; completed CLI reuse has zero low-level filesystem/SQLite mutation calls and identical full snapshots, while verified miss/resume still writes through the sole anchored materializer | CLI security | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_security.py` | `tests/test_cli_security.py` | ⬜ pending |
| 03-14-01 | 03-14 | 13 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-43, T-03-44, T-03-46 | Acceptance reuses Phase 1 bounded no-follow hash/immutable/fixed-registry patterns, exact import/capability/provenance gates, canonical anchored materializer durability, separate descriptor-read completed projector with all-branch zero-write snapshots, and protected Phase 1/2 seams | acceptance + mutation | `sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_acceptance_tool.py tests/test_phase1_gap_closure.py && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked python tools/verify_phase3_acceptance.py` | `tools/verify_phase3_acceptance.py`, `tests/test_phase3_acceptance_tool.py`, `tests/test_phase1_gap_closure.py` | ⬜ pending |
| 03-14-02 | 03-14 | 13 | QUAL-01, QUAL-02, GEN-01, GEN-02, GEN-03, GEN-04, GEN-05, VAL-01, VAL-02, VAL-03, REV-01, REV-02, REV-03 | T-03-45 | Read-only source-plan/map conformance, exact requirement-coverage inverse, literal command equality, and final Gate-B3-prefixed lock, repository-local build, acceptance, Ruff, and full-test release gates | final phase gate | `PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_phase3_validation_map.py && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_phase3_validation_map.py && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --check && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" build --no-sources && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked python tools/verify_phase3_acceptance.py && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked ruff check . && sh tools/verify_phase3_gate_b3.sh && UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q && sh tools/verify_phase3_gate_b3.sh` | `tools/verify_phase3_validation_map.py`, `tests/test_phase3_validation_map.py`, `.planning/phases/03-validated-skill-candidate/03-VALIDATION.md` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Gate A3 explicitly approves `skills-ref==0.1.1` and audited wheel SHA-256 `d35db5bb8de71ae301daf5ca9cb71f8a555e8c6f83a6d40e46a5bc09f8f461b5` before Plan 03-02 changes dependency metadata.
- [ ] Plan 03-02 uses `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" lock --no-build --no-sources --no-cache --managed-python --no-python-downloads --python 3.13.14` and captures the complete Gate B3 command/diff/digest/tree/artifact evidence without installing/importing/executing it.
- [ ] Gate B3 explicitly approves every exact transitive artifact and one exact `uv.lock` SHA-256 before Plan 03-04 or any dependency-backed command.
- [ ] Plan 03-04 commits the approved digest and dependency-free preflight; every later task uses it first.
- [ ] Generator and Reviewer fixtures use injected recorded transports in `tests/fixtures/openai/generator/cases.json` and `tests/fixtures/openai/reviewer/cases.json`; no live network is validation evidence.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Gate A3 package identity decision | VAL-01 | `[SUS]` package legitimacy cannot be auto-approved | Review exact PyPI/source evidence and respond `approved A3` or `rejected A3: reason`. |
| Gate B3 exact graph/lock decision | VAL-01 | Every executable transitive artifact and exact lock bytes require human approval | Review all resolved artifacts, compute the exact 64-character lock SHA-256, and respond with `approved B3` followed by that digest, or `rejected B3: reason`. |

No live GitHub/OpenAI run is required for automated acceptance; networked smoke tests are optional operational checks and cannot replace the fixture-backed suite.

---

## Requirement Coverage

The following inverse is regenerated from the Requirement cells in the Per-Task Verification Map; each of the 13 rows must match that map exactly.

| Requirement | Validation evidence |
|-------------|---------------------|
| QUAL-01 | 03-07-01, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |
| QUAL-02 | 03-07-02, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |
| GEN-01 | 03-08-01, 03-08-02, 03-08-03, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |
| GEN-02 | 03-08-01, 03-08-03, 03-09-02, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-13-02, 03-14-01, 03-14-02 |
| GEN-03 | 03-08-02, 03-08-03, 03-09-02, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |
| GEN-04 | 03-05-01, 03-06-01, 03-06-02, 03-08-01, 03-08-02, 03-08-03, 03-09-02, 03-10-03, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-13-02, 03-14-01, 03-14-02 |
| GEN-05 | 03-05-01, 03-05-02, 03-06-01, 03-06-02, 03-08-01, 03-08-03, 03-10-03, 03-11-01, 03-11-02, 03-11-03, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |
| VAL-01 | 03-01-01, 03-02-01, 03-03-01, 03-04-01, 03-09-01, 03-09-02, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |
| VAL-02 | 03-09-02, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-13-02, 03-14-01, 03-14-02 |
| VAL-03 | 03-09-03, 03-10-03, 03-11-01, 03-11-02, 03-11-03, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |
| REV-01 | 03-10-02, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-13-02, 03-14-01, 03-14-02 |
| REV-02 | 03-10-01, 03-10-02, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |
| REV-03 | 03-10-01, 03-10-03, 03-11-01, 03-11-02, 03-11-03, 03-12-01, 03-12-02, 03-12-03, 03-13-01, 03-14-01, 03-14-02 |

---

## Validation Sign-Off

- [ ] All 29 tasks have an automated verification command or non-auto-approvable checkpoint.
- [ ] All 13 Phase 3 requirement IDs appear explicitly in plan frontmatter and this map.
- [ ] No unresolved symbolic path tokens, ellipses, requirement ranges, or shorthand commands remain.
- [ ] Every post-B3 uv/import/test/Ruff/validator command starts with `sh tools/verify_phase3_gate_b3.sh &&`.
- [ ] Gate A3 and Gate B3 are recorded as blocking-human and cannot auto-advance.
- [ ] Sampling continuity has no unvalidated implementation task.
- [ ] No watch-mode flags or live-network dependency.
- [ ] Dependency-free validation-map checker and its temporary-copy mutation suite pass before release credit.
- [ ] The validation-map rows and Requirement Coverage inverse exactly match all source PLAN verification contracts.
- [ ] The checker safely admits all 14 PLAN files and this map, rejects malformed or duplicate tables, and allows only its hard-coded canonical command sequences.
- [ ] Parity-preserving logical-OR, separator, pipe, newline/control, substitution, redirection, process-substitution, heredoc, comment, and escape mutations fail before any mapped command could run.
- [ ] Full suite command passes without changing `uv.lock`, as proven by the terminal Gate B3 postflight after pytest.
- [ ] The full suite includes a fresh Gate B3 preflight immediately before repository-local `uv build --no-sources`.
- [ ] `nyquist_compliant: true` is set only after `/gsd-validate-phase` confirms execution.

**Approval:** pending
