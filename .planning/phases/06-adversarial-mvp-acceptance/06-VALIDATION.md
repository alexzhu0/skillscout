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
| **Independent phase gate** | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py` |
| **Estimated runtime** | Quick feedback under 10 seconds; full offline release chain under 120 seconds; protected live/manual gates excluded |

---

## Sampling Rate

- **After every task commit:** Run the focused test file for the contract, application, adapter, workflow, or verifier edited by that task, plus Ruff on changed Python files.
- **After every plan wave:** Run the full locked pytest suite, Ruff, and both Phase 6 independent verifiers once those verifiers exist.
- **Before `$gsd-verify-work`:** The full offline release chain must be green; the protected offline adversarial job, locked live campaign, fresh Gate B4 evidence, and human exact-head review attestation must all be current.
- **Max feedback latency:** 10 seconds for the quick loop, 120 seconds for the offline phase gate.

---

## Per-Task Verification Map

All 38 Phase 6 tasks appear exactly once below as primary rows. Checkpoint dependencies are explicit, and every row has an automated command even when human or hosted evidence is also required.

| Task ID | Plan | Wave | Requirement | Feedback / checkpoint dependency | Automated command | Status |
|---------|------|------|-------------|----------------------------------|-------------------|--------|
| 06-01-01 | 06-01 | 0 | TEST-01..04 | Expected-RED domain contracts; rejects collection/infrastructure failure | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_red_contracts.py --suite domain` | ⬜ pending |
| 06-01-02 | 06-01 | 0 | TEST-01, TEST-04 | Expected-RED application/provider contracts; rejects unexpected failures | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_red_contracts.py --suite application-provider` | ⬜ pending |
| 06-01-03 | 06-01 | 0 | TEST-01..04 | Exact 38-task, checkpoint, inverse-requirement, command, and Wave 0 ownership map | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py --plan-contract && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py --registry-only` | ⬜ pending |
| 06-02-01 | 06-02 | 0 | TEST-01..04 | Collectable adversarial/report/workflow contracts | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_phase6_adversarial.py tests/test_phase6_acceptance.py tests/test_phase6_workflow.py` | ⬜ pending |
| 06-02-02 | 06-02 | 0 | TEST-02, TEST-04 | Static probe workflow admission before dispatch | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py -k 'isolation or workflow or permission or secret' -x` | ⬜ pending |
| 06-02-03 | 06-02 | 0 | TEST-02, TEST-04 | Blocking human review after 06-02-02; non-authoritative one-day locator only | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py -k 'hosted_isolation_locator or isolation' -x` | ⬜ pending |
| 06-03-01 | 06-03 | 1 | TEST-01, TEST-04 | Hard precondition on both Wave 0 plans, then exact stage/model/endpoint admission | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py --wave-zero-complete && .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py -x` | ⬜ pending |
| 06-03-02 | 06-03 | 1 | TEST-01, TEST-04 | Production extraction/generation/review stage wiring | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_semantic_provider.py -x` | ⬜ pending |
| 06-04-01 | 06-04 | 2 | TEST-01..04 | Strict acceptance vocabulary and gate semantics | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_domain.py -x` | ⬜ pending |
| 06-04-02 | 06-04 | 2 | TEST-01..04 | OperationsStateStore acceptance facts and rebuild | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_operations_state.py -k 'acceptance or export or rebuild or canonical' -x` | ⬜ pending |
| 06-05-01 | 06-05 | 3 | TEST-01, TEST-03, TEST-04 | Capability-separated orchestration | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_application.py -x` | ⬜ pending |
| 06-05-02 | 06-05 | 3 | TEST-01, TEST-03, TEST-04 | Closed CLI and late credentials | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'cli or parser or bootstrap or credential or target' -x` | ⬜ pending |
| 06-05-03 | 06-05 | 3 | TEST-01, TEST-03, TEST-04 | Finalizes every Phase 6 workflow action/authority zone before live execution | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py tests/test_phase6_acceptance.py -k 'workflow or zone or action or retention' -x` | ⬜ pending |
| 06-06-01 | 06-06 | 4 | TEST-02, TEST-03, TEST-04 | Complete controlled terminal/adversarial matrix | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_adversarial.py -x` | ⬜ pending |
| 06-06-02 | 06-06 | 4 | TEST-02, TEST-03, TEST-04 | Frozen credential-free hosted offline job and canary scans | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py tests/test_phase6_adversarial.py -k 'network or kernel or isolation or secret or canary or artifact' -x` | ⬜ pending |
| 06-06-03 | 06-06 | 4 | TEST-02, TEST-03, TEST-04 | Blocking hosted dispatch after 06-06-02; canonical state persistence/rebuild required | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py tests/test_phase6_adversarial.py tests/test_phase6_acceptance.py -k 'offline_adversarial or hosted_campaign or canonical_state or rebuild' -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py --offline-only` | ⬜ pending |
| 06-07-01 | 06-07 | 5 | TEST-01, TEST-02 | Blocking nomination credential authorization after canonical 06-06-03 pass | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py tests/test_phase6_acceptance.py -k 'nominate or search_credential or no_semantic or no_publication' -x` | ⬜ pending |
| 06-07-02 | 06-07 | 5 | TEST-01, TEST-02 | Search-derived canonical nomination facts | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_phase6_workflow.py -k 'nomination or search_derived or user_nominated or state_fact' -x` | ⬜ pending |
| 06-07-03 | 06-07 | 5 | TEST-01, TEST-02 | Blocking human benchmark lock after 06-07-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_domain.py tests/test_phase6_acceptance.py -k 'locked_manifest or distribution or search_provenance' -x` | ⬜ pending |
| 06-08-01 | 06-08 | 6 | TEST-01, TEST-02, TEST-03 | Blocking live credential authorization after 06-07-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_phase6_workflow.py -k 'live_authority or exact_manifest or deepseek_only or no_catalog' -x` | ⬜ pending |
| 06-08-02 | 06-08 | 6 | TEST-01, TEST-02, TEST-03 | Five fixed-SHA live terminal facts | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'benchmark or five_repositories or evaluator_blind or terminal or telemetry' -x` | ⬜ pending |
| 06-08-03 | 06-08 | 6 | TEST-01, TEST-02, TEST-03 | Exact semantic replay zero effects | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'replay or idempotent or zero_effect' -x` | ⬜ pending |
| 06-09-01 | 06-09 | 7 | TEST-03 | Blocking exact changed-lineage approval after 06-08-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_phase3_pipeline.py -k 'prior_lineage or changed_source or approval' -x` | ⬜ pending |
| 06-09-02 | 06-09 | 7 | TEST-03 | Changed source creates new authority and no publication effect | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_phase3_pipeline.py -k 'changed_source or prior_lineage or new_authority or no_publication' -x` | ⬜ pending |
| 06-10-01 | 06-10 | 8 | TEST-03, TEST-04 | Blocking fresh canary/publication authorization after final workflow bytes from 06-09 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_gate_b4_canary.py tests/test_gate_b4_canary_workflow.py tests/test_phase6_acceptance.py -k 'preflight or binding or publication_authority' -x` | ⬜ pending |
| 06-10-02 | 06-10 | 8 | TEST-03, TEST-04 | Fresh causal denials persisted/rebuilt on state branch | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_gate_b4_canary.py tests/test_gate_b4_canary_workflow.py tests/test_phase6_acceptance.py -k 'gate_b4 or causal or stale or cleanup_manifest' -x` | ⬜ pending |
| 06-10-03 | 06-10 | 8 | TEST-03, TEST-04 | One Draft, zero-effect replay, same-Draft update | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_publication_recovery.py tests/test_publication_security.py -k 'value_draft or publication_replay or changed_source or same_draft or forbidden' -x` | ⬜ pending |
| 06-11-01 | 06-11 | 9 | TEST-02, TEST-04 | Blocking exact-head human content verdict after 06-10-03; no workflow edit | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'human_review or exact_head or checklist or draft_state' -x` | ⬜ pending |
| 06-11-02 | 06-11 | 9 | TEST-02, TEST-04 | Pre-finalized read-only attestation job; canonical reconciliation | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'attestation or reconcile or submitted_review or stale_head or no_publication' -x` | ⬜ pending |
| 06-11-03 | 06-11 | 9 | TEST-02, TEST-04 | Advice-only Pro/human calibration | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'calibration or agreement or kappa or reviewer_advisory or label_leakage' -x` | ⬜ pending |
| 06-12-01 | 06-12 | 10 | TEST-04 | Blocking separate human/admin cleanup after 06-11-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_gate_b4_canary.py tests/test_phase6_acceptance.py -k 'cleanup or probe_only or value_draft_untouched' -x` | ⬜ pending |
| 06-12-02 | 06-12 | 10 | TEST-04 | Pre-finalized read-only cleanup-attestation job; no workflow edit | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_gate_b4_canary_workflow.py -k 'cleanup_attestation or exact_targets or no_cleanup_route or value_draft' -x` | ⬜ pending |
| 06-13-01 | 06-13 | 11 | TEST-01..04 | Final hard-gate and exact-map mutation coverage | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'verifier or validation_map or mutation or read_only or all_44' -x` | ⬜ pending |
| 06-13-02 | 06-13 | 11 | TEST-01..04 | Deterministic report/all-44 rebuild | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'report or requirement_map or rebuild or warning or recommendation' -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py` | ⬜ pending |
| 06-13-03 | 06-13 | 11 | TEST-01..04 | Final Nyquist statuses from executed evidence | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py` | ⬜ pending |
| 06-14-01 | 06-14 | 12 | TEST-01..04 | Provider/architecture/operator docs | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py tests/test_phase6_workflow.py tests/test_phase6_acceptance.py -k 'docs or provider or command or boundary' -x && git diff --check` | ⬜ pending |
| 06-14-02 | 06-14 | 12 | TEST-01..04 | Testing/release posture matches report | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py && git diff --check` | ⬜ pending |
| 06-14-03 | 06-14 | 12 | TEST-01..04 | Structural source-execution verifier plus mutation suite; fresh offline wheel equals sole installed/documented SHA-256; workflows remain separately Gate B4-bound | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_source_execution.py -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py && git diff --quiet -- .github/workflows/discover.yml .github/workflows/publish-candidate.yml .github/workflows/gate-b4-canary.yml .github/workflows/phase6-acceptance.yml && git diff --cached --quiet -- .github/workflows/discover.yml .github/workflows/publish-candidate.yml .github/workflows/gate-b4-canary.yml .github/workflows/phase6-acceptance.yml && .tools/uv-0.11.29/bin/uv --no-cache --offline lock --check && build_stage="$(mktemp -d)" && trap 'rm -rf "$build_stage"' EXIT && .tools/uv-0.11.29/bin/uv --no-cache build --offline --no-sources --wheel --out-dir "$build_stage" . && .tools/uv-0.11.29/bin/uv run --locked python -c 'import hashlib,re,sys; from pathlib import Path; stage=Path(sys.argv[1]); expected="skillscout-0.1.0-py3-none-any.whl"; built=list(stage.iterdir()); published=list(Path("dist").glob("skillscout-*.whl")); assert len(built)==1 and built[0].is_file() and built[0].name==expected, built; assert len(published)==1 and published[0].is_file() and published[0].name==expected, published; release=Path("RELEASE.md").read_text(encoding="utf-8"); documented=re.findall(r"Release wheel SHA-256: `([0-9a-f]{64})`", release); assert len(documented)==1, documented; digest=lambda path: hashlib.sha256(path.read_bytes()).hexdigest(); assert digest(built[0])==digest(published[0])==documented[0]; assert "release-document evidence only" in release and "Gate B4 independently binds" in release' "$build_stage" && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q && .tools/uv-0.11.29/bin/uv run --locked ruff check . && git diff --check && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

## Requirement Inverse Coverage

The Wave 0 map verifier requires every primary task row above to appear in the appropriate inverse set and rejects any missing, duplicate, or extra task ID.

| Requirement | Exact task coverage |
|-------------|---------------------|
| TEST-01 | 06-01-01, 06-01-02, 06-01-03, 06-02-01, 06-03-01, 06-03-02, 06-04-01, 06-04-02, 06-05-01, 06-05-02, 06-05-03, 06-07-01, 06-07-02, 06-07-03, 06-08-01, 06-08-02, 06-08-03, 06-13-01, 06-13-02, 06-13-03, 06-14-01, 06-14-02, 06-14-03 |
| TEST-02 | 06-01-01, 06-01-03, 06-02-01, 06-02-02, 06-02-03, 06-04-01, 06-04-02, 06-06-01, 06-06-02, 06-06-03, 06-07-01, 06-07-02, 06-07-03, 06-08-01, 06-08-02, 06-08-03, 06-11-01, 06-11-02, 06-11-03, 06-13-01, 06-13-02, 06-13-03, 06-14-01, 06-14-02, 06-14-03 |
| TEST-03 | 06-01-01, 06-01-03, 06-02-01, 06-04-01, 06-04-02, 06-05-01, 06-05-02, 06-05-03, 06-06-01, 06-06-02, 06-06-03, 06-08-01, 06-08-02, 06-08-03, 06-09-01, 06-09-02, 06-10-01, 06-10-02, 06-10-03, 06-13-01, 06-13-02, 06-13-03, 06-14-01, 06-14-02, 06-14-03 |
| TEST-04 | 06-01-01, 06-01-02, 06-01-03, 06-02-01, 06-02-02, 06-02-03, 06-03-01, 06-03-02, 06-04-01, 06-04-02, 06-05-01, 06-05-02, 06-05-03, 06-06-01, 06-06-02, 06-06-03, 06-10-01, 06-10-02, 06-10-03, 06-11-01, 06-11-02, 06-11-03, 06-12-01, 06-12-02, 06-13-01, 06-13-02, 06-13-03, 06-14-01, 06-14-02, 06-14-03 |

---

## Wave 0 Requirements

- [ ] `tests/fixtures/acceptance/scenario_matrix.json` contains only bounded synthetic scenario instructions and mutation identities.
- [ ] `tests/test_acceptance_domain.py` for contract strictness, canonical identity, evaluator/semantic separation, and invalid combinations.
- [ ] `tests/test_acceptance_application.py` for nomination/lock/run separation and evaluator-blind semantic requests.
- [ ] `tests/test_semantic_provider.py` contains the exact stage/model/endpoint expected-RED policy.
- [ ] `tests/test_phase6_adversarial.py` for all seven existing injection classes plus shell, subprocess, dynamic import, source execution, synthetic-secret, and outbound-network denials.
- [ ] `tests/test_phase6_acceptance.py` for complete scenario taxonomy, identical replay, explicit changed-lineage update, fresh-canary binding, human attestation, and report rebuilding.
- [ ] `tests/test_phase6_workflow.py` for protected environments, serial concurrency, full-SHA Actions, artifact retention, unsafe-interpolation denial, and offline/live job separation.
- [ ] `tools/verify_phase6_red_contracts.py` exits zero only for the exact expected missing-contract failures and rejects collection/infrastructure/unexpected failures.
- [ ] `tools/verify_phase6_acceptance.py` exists with the fixed hard-gate registry; future facts remain explicit failures.
- [ ] `tools/verify_phase6_validation_map.py` parses all 14 plans and proves 38 unique primary task rows, checkpoint dependencies, TEST-01..TEST-04 forward/inverse coverage, commands, and this complete Wave 0 file set.
- [ ] `.github/workflows/phase6-acceptance.yml` contains the no-credential hosted capability probe with one-day raw artifact retention.
- [ ] The hosted OS/network-isolation probe is explicitly reviewed before choosing the exact mechanism for `offline_adversarial`; only its immutable artifact locator/digest is projected, and canonical ingestion is deferred to Plan 06-06 after OperationsStateStore acceptance facts exist.
- [ ] `.planning/phases/06-adversarial-mvp-acceptance/06-VALIDATION.md` contains this exact non-provisional map before Wave 1.

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

- [ ] All 38 finalized tasks appear exactly once as primary rows and each has an automated command; all checkpoint prerequisites and post-ingest checks are explicit.
- [ ] Sampling continuity: no three consecutive implementation tasks lack automated feedback.
- [ ] Wave 0 creates every listed test, verifier, fixture, map, and hosted capability probe before Wave 1; `verify_phase6_validation_map.py --wave-zero-complete` passes.
- [ ] No watch-mode flags or unlocked dependency commands are used.
- [ ] Quick feedback latency remains below 10 seconds and the offline phase gate below 120 seconds.
- [ ] Real credentials are never opened, copied into fixtures, logged, or scanned as values; only synthetic canaries are used.
- [ ] Protected live/manual evidence is current and bound to exact identities, heads, workflows, policies, and human attestations.
- [ ] The dedicated source-execution verifier parses the exact protected discover/publish/canary workflows, finds every authoritative SkillScout step, and mutation tests reject every non-checkout, non-locked, registry, artifact, preinstalled-command, alias/wrapper, and unknown invocation route.
- [ ] `nyquist_compliant: true` and `wave_0_complete: true` are set only after the finalized task map and Wave 0 evidence are complete.

**Approval:** pending
