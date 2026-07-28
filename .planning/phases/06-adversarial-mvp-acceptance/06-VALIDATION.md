---
phase: 6
slug: adversarial-mvp-acceptance
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-28
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 plus stdlib-only independent acceptance verifiers |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_domain.py tests/test_acceptance_application.py tests/test_semantic_provider.py -x` |
| **Full suite command** | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` |
| **Static gate** | `.tools/uv-0.11.29/bin/uv run --locked ruff check .` |
| **Independent phase gate** | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py` |
| **Estimated runtime** | Quick feedback under 10 seconds; full offline release chain under 120 seconds; protected live/manual gates excluded |

---

## Sampling Rate

- **After every task commit:** Run the focused test file for the contract, application, adapter, workflow, or verifier edited by that task, plus Ruff on changed Python files.
- **After every plan wave:** Run the full locked pytest suite, Ruff, and both Phase 6 independent verifiers once those verifiers exist.
- **Before `$gsd-verify-work`:** The full offline release chain must be green; the protected offline adversarial job, locked live campaign, fresh Gate B4 evidence, and human exact-head review attestation must all be current.
- **Max feedback latency:** 10 seconds for the quick loop, 120 seconds for the offline phase gate.

---

## Per-Task Verification Map

Plan and task identifiers are finalized by `gsd-planner`; every produced task must map back to at least one row below and replace the provisional `TBD` identifier without changing the required behavior.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD-contracts | TBD | 0 | TEST-01..04 | T6-02 / T6-06 | Strict benchmark, evidence, attestation, gate, and report models reject unknown or inconsistent fields | unit/contract | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_domain.py -x` | ❌ W0 | ⬜ pending |
| TBD-provider | TBD | 1 | TEST-01, TEST-04 | T6-03 | DeepSeek uses exact Flash/Flash/Pro stage bindings and the official endpoint; arbitrary models/endpoints fail before HTTP | unit/contract | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py -x` | ⚠️ extend | ⬜ pending |
| TBD-orchestration | TBD | 2 | TEST-01, TEST-03 | T6-01 / T6-06 | Nomination, human lock, execution, persistence, replay, changed-source update, and rebuild are separate structured transitions | integration | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_application.py tests/test_phase6_acceptance.py -x` | ❌ W0 | ⬜ pending |
| TBD-adversarial | TBD | 3 | TEST-02 | T6-01 / T6-04 / T6-05 | All injection and supply-chain scenarios stop at the intended boundary under kernel-enforced offline execution and synthetic-secret scans | adversarial/contract | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_adversarial.py -x` | ❌ W0 | ⬜ pending |
| TBD-live-benchmark | TBD | 4 | TEST-01, TEST-03 | T6-02 / T6-06 | Five fixed-SHA repositories produce complete facts; identical replay has zero duplicate effects; approved changed source updates the same open Draft lineage | protected integration/live | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'benchmark or idempotent or changed_source' -x` plus protected `run-acceptance` | ❌ W0 | ⬜ pending |
| TBD-authority | TBD | 5 | TEST-04 | T6-04 / T6-07 / T6-08 | Fresh causal denials, one separate real value Draft, exact-head human verdict, and human-only probe cleanup are bound without widening App authority | protected integration/live/manual | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_gate_b4_canary.py tests/test_gate_b4_canary_workflow.py tests/test_phase6_acceptance.py -k 'gate_b4 or human_review' -x` | ⚠️ extend | ⬜ pending |
| TBD-report | TBD | 6 | TEST-01..04 | T6-05 / T6-06 | Concise report and all-44 inverse requirement map rebuild byte-for-byte from canonical redacted evidence and fail under mutation | independent verifier | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `src/skillscout/domain/acceptance.py` contract tests for strict benchmark, evidence, attestation, gate, and report schemas and digests.
- [ ] `tests/test_acceptance_domain.py` for contract strictness, canonical identity, evaluator/semantic separation, and invalid combinations.
- [ ] `tests/test_acceptance_application.py` for nomination/lock/run separation and evaluator-blind semantic requests.
- [ ] `tests/test_phase6_adversarial.py` for all seven existing injection classes plus shell, subprocess, dynamic import, source execution, synthetic-secret, and outbound-network denials.
- [ ] `tests/test_phase6_acceptance.py` for complete scenario taxonomy, identical replay, explicit changed-lineage update, fresh-canary binding, human attestation, and report rebuilding.
- [ ] `tests/test_phase6_workflow.py` for protected environments, serial concurrency, full-SHA Actions, artifact retention, unsafe-interpolation denial, and offline/live job separation.
- [ ] `tools/verify_phase6_acceptance.py` with an independent required-gate registry, exact evidence roots, source-surface coverage, and mutation tests.
- [ ] `tools/verify_phase6_validation_map.py` with exact TEST-01..TEST-04 and all-44-requirement inverse maps.
- [ ] A hosted OS/network-isolation capability probe before choosing the exact runner mechanism for the protected offline adversarial job.
- [ ] Deterministic report fixtures containing only synthetic credentials and sanitized canonical facts.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Lock the five-repository benchmark | TEST-01 | Repository identity, license, outcome-role mix, and suitability require accountable human selection before credentials or LLM calls | Review the Search-derived nomination manifest; confirm two plausible positives including a multi-workflow repository, two negatives, one borderline repository, fixed repository IDs/SHAs/licenses, then record a content-addressed human lock attestation |
| Approve the changed-source lineage test | TEST-03 | Mutating live source authority or choosing the replacement SHA is an external-effect checkpoint | Confirm the exact old/new repository IDs and SHAs, expected open Draft identity, and bounded update operation before the changed-source run |
| Authorize live credentials and publication | TEST-01, TEST-04 | GitHub App and DeepSeek credentials may be injected only by the protected runtime at the latest required boundary | Verify the protected environment and current bindings without opening secret values; approve the exact benchmark run and later Gate B4/value-Draft run separately |
| Human content verdict on the real value Draft | TEST-04 | Usefulness, fidelity, attribution/license, instruction safety, and diff scope require human judgment | Review the exact open Draft head; record `publishable` or `publishable_with_changes` with repository/SHA/license/diff-scope checklist and an exact-head attestation; do not merge or mark ready |
| Probe cleanup | TEST-04 | Cleanup authority intentionally belongs to a separate human administrator | After all denial evidence is durable, close only probe PRs, delete only probe branches, leave the value Draft open, and record a separate cleanup attestation |

---

## Validation Sign-Off

- [ ] Every finalized task replaces a provisional `TBD` row with an exact plan/task ID and has an automated verify or explicit manual checkpoint dependency.
- [ ] Sampling continuity: no three consecutive implementation tasks lack automated feedback.
- [ ] Wave 0 creates every missing test, verifier, fixture, and hosted capability probe before dependent implementation/live tasks.
- [ ] No watch-mode flags or unlocked dependency commands are used.
- [ ] Quick feedback latency remains below 10 seconds and the offline phase gate below 120 seconds.
- [ ] Real credentials are never opened, copied into fixtures, logged, or scanned as values; only synthetic canaries are used.
- [ ] Protected live/manual evidence is current and bound to exact identities, heads, workflows, policies, and human attestations.
- [ ] `nyquist_compliant: true` and `wave_0_complete: true` are set only after the finalized task map and Wave 0 evidence are complete.

**Approval:** pending
