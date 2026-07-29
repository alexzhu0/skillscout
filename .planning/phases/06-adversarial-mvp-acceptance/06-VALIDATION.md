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
| 06-01-01 | 06-01 | 0 | TEST-01..04 | Expected-RED domain contracts include exact hosted/offline/calibration schemas plus distinct publication replay/update completion models, intent links, natural identities, effect counts, redaction, and invalid combinations | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_red_contracts.py --suite domain` | ⬜ pending |
| 06-01-02 | 06-01 | 0 | TEST-01, TEST-04 | Expected-RED application/provider contracts; rejects unexpected failures | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_red_contracts.py --suite application-provider` | ⬜ pending |
| 06-01-03 | 06-01 | 0 | TEST-01..04 | Exact 38-task, checkpoint, inverse-requirement, command, Wave 0 file, and cross-plan symbol/fact-kind ownership map | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py --plan-contract && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py --registry-only` | ⬜ pending |
| 06-02-01 | 06-02 | 0 | TEST-01..04 | Collectable adversarial/report/workflow contracts plus all-four-workflow source-execution mutation contract | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_phase6_adversarial.py tests/test_phase6_acceptance.py tests/test_phase6_workflow.py tests/test_phase6_source_execution.py` | ⬜ pending |
| 06-02-02 | 06-02 | 0 | TEST-02, TEST-04 | Static probe workflow admission with checked-out locked source only and no execution-source selector | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py -k 'isolation or workflow or permission or secret' -x` | ⬜ pending |
| 06-02-03 | 06-02 | 0 | TEST-02, TEST-04 | checkpoint:human-verify; predecessor 06-02-02; post-ingest verifier 06-03-01; non-authoritative one-day locator only | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py -k 'hosted_isolation_locator or isolation' -x` | ⬜ pending |
| 06-03-01 | 06-03 | 1 | TEST-01, TEST-04 | Hard precondition on both Wave 0 plans, then exact stage/model/endpoint admission | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py --wave-zero-complete && .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py -x` | ⬜ pending |
| 06-03-02 | 06-03 | 1 | TEST-01, TEST-04 | Production extraction/generation/review stage wiring | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_semantic_provider.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/semantic_provider.py src/skillscout/adapters/openai_extract.py src/skillscout/adapters/openai_generate.py src/skillscout/adapters/openai_review.py` | ⬜ pending |
| 06-04-01 | 06-04 | 2 | TEST-01..04 | Strict acceptance vocabulary includes exact hosted/offline/calibration models and `PublicationReplayCompletionV1`/`ChangedSourceDraftUpdateCompletionV1` schemas, links, counters, lineage/PR/head rules, redaction, and gate semantics | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_domain.py -x` | ⬜ pending |
| 06-04-02 | 06-04 | 2 | TEST-01..04 | Exact intent/completion fact-kind/model registry, distinct natural identities, typed persistence/projection, duplicate/idempotency, export, state-bundle parse, and rebuild mutation coverage | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_operations_state.py -k 'acceptance or export or rebuild or canonical' -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/domain/acceptance.py src/skillscout/adapters/operations_state.py` | ⬜ pending |
| 06-05-01 | 06-05 | 3 | TEST-01, TEST-03, TEST-04 | Capability-separated orchestration | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_application.py -x` | ⬜ pending |
| 06-05-02 | 06-05 | 3 | TEST-01, TEST-03, TEST-04 | Closed CLI and late credentials | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'cli or parser or bootstrap or credential or target' -x` | ⬜ pending |
| 06-15-01 | 06-15 | 3 | TEST-01, TEST-03, TEST-04 | Creates the closed source-execution verifier, owns publication-security corrections, and establishes discover/publish/canary/Phase6 full-SHA repository-local locked-source bytes before the Plan 06-06 final freeze | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_source_execution.py tests/test_publication_security.py tests/test_phase6_workflow.py -k 'source_execution or publish_workflow or locked_source_execution or workflow or zone or action or retention' -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py` | ⬜ pending |
| 06-06-01 | 06-06 | 4 | TEST-02, TEST-03, TEST-04 | Complete controlled terminal/adversarial matrix | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_adversarial.py -x` | ⬜ pending |
| 06-06-02 | 06-06 | 4 | TEST-02, TEST-03, TEST-04 | Final credential-free hosted offline job, canary scans, and all-four-workflow source-only verification before workflow freeze | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py tests/test_phase6_adversarial.py tests/test_phase6_source_execution.py -k 'network or kernel or isolation or secret or canary or artifact or source_execution' -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py` | ⬜ pending |
| 06-06-03 | 06-06 | 4 | TEST-02, TEST-03, TEST-04 | checkpoint:human-verify; predecessor 06-06-02; post-ingest verifier 06-07-01; exact hosted/offline typed persistence/export/rebuild required | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py tests/test_phase6_adversarial.py tests/test_phase6_acceptance.py -k 'offline_adversarial or hosted_campaign or canonical_state or rebuild' -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py --offline-only` | ⬜ pending |
| 06-07-01 | 06-07 | 5 | TEST-01, TEST-02 | checkpoint:decision; predecessor 06-06-03; post-ingest verifier 06-07-02; exact canonical hosted/offline pair required | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py --offline-only && .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py tests/test_phase6_acceptance.py -k 'nominate or search_credential or no_semantic or no_publication' -x` | ⬜ pending |
| 06-07-02 | 06-07 | 5 | TEST-01, TEST-02 | Search-derived canonical nomination facts | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_phase6_workflow.py -k 'nomination or search_derived or user_nominated or state_fact' -x` | ⬜ pending |
| 06-07-03 | 06-07 | 5 | TEST-01, TEST-02 | checkpoint:human-verify; predecessor 06-07-02; post-ingest verifier 06-08-01; exact human benchmark lock | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_domain.py tests/test_phase6_acceptance.py -k 'locked_manifest or distribution or search_provenance' -x` | ⬜ pending |
| 06-08-01 | 06-08 | 6 | TEST-01, TEST-02, TEST-03 | checkpoint:decision; predecessor 06-07-03; post-ingest verifier 06-08-02; exact live credential authorization | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_phase6_workflow.py -k 'live_authority or exact_manifest or deepseek_only or no_catalog' -x` | ⬜ pending |
| 06-08-02 | 06-08 | 6 | TEST-01, TEST-02, TEST-03 | Five fixed-SHA live terminal facts | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'benchmark or five_repositories or evaluator_blind or terminal or telemetry' -x` | ⬜ pending |
| 06-08-03 | 06-08 | 6 | TEST-01, TEST-02, TEST-03 | Exact semantic replay zero effects persisted as immutable pre-publication intent; post-publication completion remains separate | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'replay or idempotent or zero_effect' -x` | ⬜ pending |
| 06-09-01 | 06-09 | 7 | TEST-03 | checkpoint:decision; predecessor 06-08-03; post-ingest verifier 06-09-02; exact changed-lineage approval | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_phase3_pipeline.py -k 'prior_lineage or changed_source or approval' -x` | ⬜ pending |
| 06-09-02 | 06-09 | 7 | TEST-03 | Changed source creates new authority and immutable pre-publication intent with no publication effect; workflow bytes remain frozen | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_phase3_pipeline.py -k 'changed_source or prior_lineage or new_authority or no_publication' -x` | ⬜ pending |
| 06-10-01 | 06-10 | 8 | TEST-03, TEST-04 | checkpoint:decision; predecessor 06-09-02; post-ingest verifier 06-10-02; frozen-workflow source verifier required | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_source_execution.py tests/test_publication_security.py tests/test_gate_b4_canary.py tests/test_gate_b4_canary_workflow.py tests/test_phase6_acceptance.py -k 'source_execution or publish_workflow or locked_source_execution or preflight or binding or publication_authority' -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py` | ⬜ pending |
| 06-10-02 | 06-10 | 8 | TEST-03, TEST-04 | Fresh causal denials persisted/rebuilt on state branch | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_gate_b4_canary.py tests/test_gate_b4_canary_workflow.py tests/test_phase6_acceptance.py -k 'gate_b4 or causal or stale or cleanup_manifest' -x` | ⬜ pending |
| 06-10-03 | 06-10 | 8 | TEST-03, TEST-04 | One Draft, zero-effect replay, same-Draft update, then distinct typed completion persistence/projection/export/rebuild | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_publication_recovery.py tests/test_publication_security.py -k 'value_draft or publication_replay or changed_source or same_draft or forbidden' -x` | ⬜ pending |
| 06-11-01 | 06-11 | 9 | TEST-02, TEST-04 | checkpoint:human-verify; predecessor 06-10-03; post-ingest verifier 06-11-02; exact-head content verdict and no workflow edit | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'human_review or exact_head or checklist or draft_state' -x` | ⬜ pending |
| 06-11-02 | 06-11 | 9 | TEST-02, TEST-04 | Pre-finalized read-only attestation job; canonical reconciliation | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'attestation or reconcile or submitted_review or stale_head or no_publication' -x` | ⬜ pending |
| 06-11-03 | 06-11 | 9 | TEST-02, TEST-04 | Advice-only strict `ReviewerCalibrationV1` persisted/rebuilt through `acceptance_reviewer_calibration` | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'calibration or agreement or kappa or reviewer_advisory or label_leakage' -x` | ⬜ pending |
| 06-12-01 | 06-12 | 10 | TEST-04 | checkpoint:human-action; predecessor 06-11-03; post-ingest verifier 06-12-02; separate probe-only cleanup | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_gate_b4_canary.py tests/test_phase6_acceptance.py -k 'cleanup or probe_only or value_draft_untouched' -x` | ⬜ pending |
| 06-12-02 | 06-12 | 10 | TEST-04 | Pre-finalized read-only cleanup-attestation job; no workflow edit | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py tests/test_gate_b4_canary_workflow.py -k 'cleanup_attestation or exact_targets or no_cleanup_route or value_draft' -x` | ⬜ pending |
| 06-13-01 | 06-13 | 11 | TEST-01..04 | Final hard-gate/map mutation coverage independently requires both typed post-publication completion facts and rejects intent-only credit | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'verifier or validation_map or mutation or read_only or all_44' -x` | ⬜ pending |
| 06-13-02 | 06-13 | 11 | TEST-01..04 | Deterministic report/all-44 rebuild consumes independently rebuilt publication completion identities/effects/lineage/PR-head facts | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'report or requirement_map or rebuild or warning or recommendation' -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py` | ⬜ pending |
| 06-13-03 | 06-13 | 11 | TEST-01..04 | Final Nyquist statuses from executed evidence | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py` | ⬜ pending |
| 06-14-01 | 06-14 | 12 | TEST-01..04 | Provider/architecture/operator docs | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py tests/test_phase6_workflow.py tests/test_phase6_acceptance.py -k 'docs or provider or command or boundary' -x && git diff --check` | ⬜ pending |
| 06-14-02 | 06-14 | 12 | TEST-01..04 | Testing/release posture matches report | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py && git diff --check` | ⬜ pending |
| 06-14-03 | 06-14 | 12 | TEST-01..04 | Read-only structural source-execution verifier over the exact corrected Plan 06-10 workflow binding plus mutation suite; fresh offline wheel equals sole installed/documented SHA-256 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_source_execution.py -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py && git diff --quiet -- .github/workflows/discover.yml .github/workflows/publish-candidate.yml .github/workflows/gate-b4-canary.yml .github/workflows/phase6-acceptance.yml && git diff --cached --quiet -- .github/workflows/discover.yml .github/workflows/publish-candidate.yml .github/workflows/gate-b4-canary.yml .github/workflows/phase6-acceptance.yml && .tools/uv-0.11.29/bin/uv --no-cache --offline lock --check && build_stage="$(mktemp -d)" && trap 'rm -rf "$build_stage"' EXIT && .tools/uv-0.11.29/bin/uv --no-cache build --offline --no-sources --wheel --out-dir "$build_stage" . && .tools/uv-0.11.29/bin/uv run --locked python -c 'import hashlib,re,sys; from pathlib import Path; stage=Path(sys.argv[1]); expected="skillscout-0.1.0-py3-none-any.whl"; built=list(stage.iterdir()); published=list(Path("dist").glob("skillscout-*.whl")); assert len(built)==1 and built[0].is_file() and built[0].name==expected, built; assert len(published)==1 and published[0].is_file() and published[0].name==expected, published; release=Path("RELEASE.md").read_text(encoding="utf-8"); documented=re.findall(r"Release wheel SHA-256: `([0-9a-f]{64})`", release); assert len(documented)==1, documented; digest=lambda path: hashlib.sha256(path.read_bytes()).hexdigest(); assert digest(built[0])==digest(published[0])==documented[0]; assert "release-document evidence only" in release and "Gate B4 independently binds" in release' "$build_stage" && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q && .tools/uv-0.11.29/bin/uv run --locked ruff check . && git diff --check && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

## Requirement Inverse Coverage

The Wave 0 map verifier requires every primary task row above to appear in the appropriate inverse set and rejects any missing, duplicate, or extra task ID.

| Requirement | Exact task coverage |
|-------------|---------------------|
| TEST-01 | 06-01-01, 06-01-02, 06-01-03, 06-02-01, 06-03-01, 06-03-02, 06-04-01, 06-04-02, 06-05-01, 06-05-02, 06-07-01, 06-07-02, 06-07-03, 06-08-01, 06-08-02, 06-08-03, 06-13-01, 06-13-02, 06-13-03, 06-14-01, 06-14-02, 06-14-03, 06-15-01 |
| TEST-02 | 06-01-01, 06-01-03, 06-02-01, 06-02-02, 06-02-03, 06-04-01, 06-04-02, 06-06-01, 06-06-02, 06-06-03, 06-07-01, 06-07-02, 06-07-03, 06-08-01, 06-08-02, 06-08-03, 06-11-01, 06-11-02, 06-11-03, 06-13-01, 06-13-02, 06-13-03, 06-14-01, 06-14-02, 06-14-03 |
| TEST-03 | 06-01-01, 06-01-03, 06-02-01, 06-04-01, 06-04-02, 06-05-01, 06-05-02, 06-06-01, 06-06-02, 06-06-03, 06-08-01, 06-08-02, 06-08-03, 06-09-01, 06-09-02, 06-10-01, 06-10-02, 06-10-03, 06-13-01, 06-13-02, 06-13-03, 06-14-01, 06-14-02, 06-14-03, 06-15-01 |
| TEST-04 | 06-01-01, 06-01-02, 06-01-03, 06-02-01, 06-02-02, 06-02-03, 06-03-01, 06-03-02, 06-04-01, 06-04-02, 06-05-01, 06-05-02, 06-06-01, 06-06-02, 06-06-03, 06-10-01, 06-10-02, 06-10-03, 06-11-01, 06-11-02, 06-11-03, 06-12-01, 06-12-02, 06-13-01, 06-13-02, 06-13-03, 06-14-01, 06-14-02, 06-14-03, 06-15-01 |

---

## Exact Cross-Plan Ownership Registry

Each surface has one production owner. A consumer may use it only in the same
task/plan or from a plan that transitively depends on the owner plan.

| Surface | Kind / mapping | Owner task | Earliest consumers |
|---------|----------------|------------|--------------------|
| `BenchmarkSelectionSource` | enum | 06-04-01 | 06-05-01, 06-07-02 |
| `BenchmarkCoverageRole` | enum | 06-04-01 | 06-05-01, 06-07-03 |
| `AcceptanceTerminalClass` | enum | 06-04-01 | 06-05-01, 06-08-02 |
| `BenchmarkEntryV1` | strict model | 06-04-01 | 06-07-02, 06-07-03 |
| `NominationSetV1` | strict model | 06-04-01 | 06-07-02 |
| `BenchmarkLockAttestationV1` | strict attestation | 06-04-01 | 06-07-03 |
| `LockedBenchmarkManifestV1` | strict model | 06-04-01 | 06-07-03, 06-08-01 |
| `AcceptanceScenarioResultV1` | strict result | 06-04-01 | 06-06-01, 06-08-02 |
| `HostedIsolationCapabilityV1` | strict attestation | 06-04-01 | 06-06-03, 06-07-01 |
| `OfflineAdversarialRunV1` | strict result | 06-04-01 | 06-06-03, 06-07-01 |
| `ReplayEvidenceV1` | pre-publication intent | 06-04-01 | 06-08-03, 06-10-03 |
| `ChangedSourceEvidenceV1` | pre-publication intent | 06-04-01 | 06-09-02, 06-10-03 |
| `PublicationReplayCompletionV1` | post-effect completion | 06-04-01 | 06-10-03, 06-13-02 |
| `ChangedSourceDraftUpdateCompletionV1` | post-effect completion | 06-04-01 | 06-10-03, 06-13-02 |
| `GateB4BindingV1` | strict attestation and cleanup target tuple | 06-04-01 | 06-10-02, 06-12-01 |
| `HumanSkillReviewAttestationV1` | strict attestation | 06-04-01 | 06-11-02, 06-13-02 |
| `ProbeCleanupAttestationV1` | strict attestation | 06-04-01 | 06-12-02, 06-13-02 |
| `ReviewerCalibrationV1` | advice-only strict result | 06-04-01 | 06-11-03, 06-13-02 |
| `AcceptanceGateResultV1` | hard-gate result | 06-04-01 | 06-13-01, 06-13-02 |
| `AcceptanceEvidenceRootV1` | report authority root | 06-04-01 | 06-13-02 |
| `AcceptanceReleaseVerdictV1` | deterministic report projection | 06-04-01 | 06-13-02 |
| `acceptance_nomination` | `NominationSetV1` fact mapping | 06-04-02 | 06-07-02 |
| `acceptance_benchmark_lock` | `LockedBenchmarkManifestV1` fact mapping | 06-04-02 | 06-07-03 |
| `acceptance_scenario` | `AcceptanceScenarioResultV1` fact mapping | 06-04-02 | 06-06-01, 06-08-02 |
| `acceptance_hosted_isolation_capability` | `HostedIsolationCapabilityV1` fact mapping | 06-04-02 | 06-06-03, 06-07-01 |
| `acceptance_offline_adversarial_run` | `OfflineAdversarialRunV1` fact mapping | 06-04-02 | 06-06-03, 06-07-01 |
| `acceptance_replay` | `ReplayEvidenceV1` fact mapping | 06-04-02 | 06-08-03 |
| `acceptance_changed_source` | `ChangedSourceEvidenceV1` fact mapping | 06-04-02 | 06-09-02 |
| `acceptance_publication_replay_completion` | `PublicationReplayCompletionV1` fact mapping | 06-04-02 | 06-10-03, 06-13-02 |
| `acceptance_changed_source_draft_update_completion` | `ChangedSourceDraftUpdateCompletionV1` fact mapping | 06-04-02 | 06-10-03, 06-13-02 |
| `acceptance_gate_b4` | `GateB4BindingV1` fact mapping | 06-04-02 | 06-10-02 |
| `acceptance_human_review` | `HumanSkillReviewAttestationV1` fact mapping | 06-04-02 | 06-11-02 |
| `acceptance_cleanup` | `ProbeCleanupAttestationV1` fact mapping | 06-04-02 | 06-12-02 |
| `acceptance_reviewer_calibration` | `ReviewerCalibrationV1` fact mapping | 06-04-02 | 06-11-03 |
| `acceptance_gate` | `AcceptanceGateResultV1` fact mapping | 06-04-02 | 06-13-01 |
| `acceptance_report_root` | `AcceptanceEvidenceRootV1` fact mapping | 06-04-02 | 06-13-02 |
| `OperationsStateStore.record_acceptance_fact` | typed persistence | 06-04-02 | 06-06-03, 06-07-02 |
| `OperationsStateStore.acceptance_snapshot` | typed projection | 06-04-02 | 06-06-03, 06-13-02 |
| `export_owned_state` | canonical acceptance export extension | 06-04-02 | 06-06-03, 06-13-02 |
| `rebuild_owned_state` | typed acceptance rebuild extension | 06-04-02 | 06-06-03, 06-13-02 |
| `SemanticStage` | enum | 06-03-01 | 06-03-02, 06-08-02 |
| `DEEPSEEK_MODEL_BY_STAGE` | exact Flash/Flash/Pro mapping | 06-03-01 | 06-03-02, 06-08-02 |
| `NominationDependencies` | capability dataclass | 06-05-01 | 06-07-02 |
| `LockedCampaignDependencies` | capability dataclass | 06-05-01 | 06-08-02 |
| `ReplayUpdateDependencies` | capability dataclass | 06-05-01 | 06-08-03, 06-09-02 |
| `HumanAttestationDependencies` | capability dataclass | 06-05-01 | 06-11-02 |
| `CleanupAttestationDependencies` | capability dataclass | 06-05-01 | 06-12-02 |
| `AcceptanceRebuildDependencies` | capability dataclass | 06-05-01 | 06-13-02 |
| `nominate-benchmark` | CLI command | 06-05-02 | 06-07-02 |
| `run-acceptance` | CLI command | 06-05-02 | 06-08-02 |
| `record-acceptance-attestation` | CLI command | 06-05-02 | 06-11-02, 06-12-02 |
| `rebuild-acceptance` | CLI command | 06-05-02 | 06-13-02 |
| `phase6_action` | closed workflow input | 06-15-01 | 06-06-02, 06-07-02 |
| `isolation-probe` | workflow action | 06-02-02 | 06-02-03 |
| `nominate` | workflow job/action | 06-15-01 | 06-07-02 |
| `offline_adversarial` | workflow job/action | 06-06-02 | 06-06-03 |
| `live_benchmark` | workflow job/action | 06-15-01 | 06-08-02 |
| `changed_source` | workflow job/action | 06-15-01 | 06-09-02 |
| `fresh_gate_b4` | workflow job/action | 06-15-01 | 06-10-02 |
| `value_publication` | workflow job/action | 06-15-01 | 06-10-03 |
| `human_attestation` | workflow job/action | 06-15-01 | 06-11-02 |
| `cleanup_attestation` | workflow job/action | 06-15-01 | 06-12-02 |
| `rebuild_report` | workflow job/action | 06-15-01 | 06-13-02 |
| `verify_phase6_red_contracts.py` | expected-RED verifier | 06-01-01 | 06-01-02 |
| `verify_phase6_validation_map.py` | task/ownership verifier | 06-01-03 | 06-03-01, 06-13-01 |
| `verify_phase6_acceptance.py` | hard-gate/report verifier | 06-01-03 | 06-06-03, 06-13-01 |
| `verify_phase6_source_execution.py` | four-workflow source verifier | 06-15-01 | 06-10-01, 06-14-03 |
| `06-ACCEPTANCE-REPORT.md` | deterministic report | 06-13-02 | 06-14-02 |
| `06-RELEASE-REQUIREMENTS.json` | all-44 inverse report | 06-13-02 | 06-14-02 |

### Wave 0 File Ownership

| File | Primary owner task |
|------|--------------------|
| `tests/fixtures/acceptance/scenario_matrix.json` | 06-01-01 |
| `tests/test_acceptance_domain.py` | 06-01-01 |
| `tools/verify_phase6_red_contracts.py` | 06-01-01 |
| `tests/test_acceptance_application.py` | 06-01-02 |
| `tests/test_semantic_provider.py` | 06-01-02 |
| `.planning/phases/06-adversarial-mvp-acceptance/06-VALIDATION.md` | 06-01-03 |
| `tools/verify_phase6_validation_map.py` | 06-01-03 |
| `tools/verify_phase6_acceptance.py` | 06-01-03 |
| `tests/test_phase6_adversarial.py` | 06-02-01 |
| `tests/test_phase6_acceptance.py` | 06-02-01 |
| `tests/test_phase6_workflow.py` | 06-02-01 |
| `tests/test_phase6_source_execution.py` | 06-02-01 |
| `.github/workflows/phase6-acceptance.yml` | 06-02-02 |

---

## Wave 0 Requirements

- [ ] `tests/fixtures/acceptance/scenario_matrix.json` contains only bounded synthetic scenario instructions and mutation identities.
- [ ] `tests/test_acceptance_domain.py` for contract strictness, canonical identity, evaluator/semantic separation, and invalid combinations.
- [ ] `tests/test_acceptance_domain.py` includes exact `HostedIsolationCapabilityV1`, `OfflineAdversarialRunV1`, and `ReviewerCalibrationV1` schema-version/field/binding/redaction mutations.
- [ ] `tests/test_acceptance_domain.py` includes exact `PublicationReplayCompletionV1` and `ChangedSourceDraftUpdateCompletionV1` schema versions, intent links, natural identities, publication marker/PR/head/lineage/effect-count constraints, and stale-digest mutations.
- [ ] `tests/test_acceptance_application.py` for nomination/lock/run separation and evaluator-blind semantic requests.
- [ ] `tests/test_semantic_provider.py` contains the exact stage/model/endpoint expected-RED policy.
- [ ] `tests/test_phase6_adversarial.py` for all seven existing injection classes plus shell, subprocess, dynamic import, source execution, synthetic-secret, and outbound-network denials.
- [ ] `tests/test_phase6_acceptance.py` for complete scenario taxonomy, identical replay, explicit changed-lineage update, fresh-canary binding, human attestation, and report rebuilding.
- [ ] `tests/test_phase6_workflow.py` for protected environments, serial concurrency, full-SHA Actions, artifact retention, unsafe-interpolation denial, and offline/live job separation.
- [ ] `tests/test_phase6_source_execution.py` freezes the exact four-workflow source-only grammar and every forbidden acquisition/invocation/order mutation before the Plan 06-15 verifier turns it green.
- [ ] `tools/verify_phase6_red_contracts.py` exits zero only for the exact expected missing-contract failures and rejects collection/infrastructure/unexpected failures.
- [ ] `tools/verify_phase6_acceptance.py` exists with the fixed hard-gate registry; future facts remain explicit failures.
- [ ] `tools/verify_phase6_validation_map.py` parses all 15 plans and proves 38 unique primary task rows, checkpoint dependencies, TEST-01..TEST-04 forward/inverse coverage, commands, and this complete Wave 0 file set.
- [ ] `tools/verify_phase6_validation_map.py` also proves every named model, enum, fact-kind/model mapping, attestation, report type, CLI/workflow surface, verifier, and persistence seam has an existing or reachable earlier/same-plan owner.
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
- [ ] Exact cross-plan ownership is complete, including `HostedIsolationCapabilityV1` → `acceptance_hosted_isolation_capability`, `OfflineAdversarialRunV1` → `acceptance_offline_adversarial_run`, `PublicationReplayCompletionV1` → `acceptance_publication_replay_completion`, `ChangedSourceDraftUpdateCompletionV1` → `acceptance_changed_source_draft_update_completion`, and `ReviewerCalibrationV1` → `acceptance_reviewer_calibration` before their consumer plans.
- [ ] Sampling continuity: no three consecutive implementation tasks lack automated feedback.
- [ ] Wave 0 creates every listed test, verifier, fixture, map, and hosted capability probe before Wave 1; `verify_phase6_validation_map.py --wave-zero-complete` passes.
- [ ] No watch-mode flags or unlocked dependency commands are used.
- [ ] Quick feedback latency remains below 10 seconds and the offline phase gate below 120 seconds.
- [ ] Real credentials are never opened, copied into fixtures, logged, or scanned as values; only synthetic canaries are used.
- [ ] Protected live/manual evidence is current and bound to exact identities, heads, workflows, policies, and human attestations.
- [ ] The dedicated source-execution verifier parses exact discover/publish/canary/Phase6 workflows, finds every authoritative SkillScout step, proves checkout/setup/materialization/invocation order, and mutation tests reject every non-checkout, non-locked, registry, wheel/dist, artifact, preinstalled-command, alias/function/variable/wrapper, indirect, external-working-directory, empty-scan, and unknown route.
- [ ] `nyquist_compliant: true` and `wave_0_complete: true` are set only after the finalized task map and Wave 0 evidence are complete.

**Approval:** pending
