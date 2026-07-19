# Phase 1 Gap Closure Validation

This index records only completed, local, pre-document facts from the authoritative
offline Phase-1 verification sequence. All commands used the repository-local uv,
managed Python, `--locked` where applicable, and `UV_PYTHON_DOWNLOADS=never`. No
external service, credential, remote write, or candidate repository code was accessed
or executed.

## Immutable Inputs

| Input | Pre-command SHA-256 | Post-command SHA-256 | Result |
|---|---|---|---|
| `uv.lock` | `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32` | `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32` | PASS |
| `tests/fixtures/state/v1-cli.db` | `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251` | `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251` | PASS |

## Completed Command Evidence

| ID | Command summary | Exit | Actual count |
|---|---|---:|---:|
| `packaged_cli` | Three named packaged-CLI gap-acceptance nodes | 0 | 3 passed |
| `mapping_capability` | AST finding-map and parsed production-capability nodes | 0 | 2 passed |
| `focused_findings` | Six focused CR/WR test modules | 0 | 195 passed |
| `phase1_collect` | Explicit non-recursive collection of seven Phase-1 modules | 0 | 200 collected |
| `full_pytest` | Full locked pytest suite | 0 | 200 passed |
| `ruff` | Repository-wide Ruff lint | 0 | 1 successful check |
| `lock_check` | Frozen lock consistency | 0 | 1 successful check |
| `build` | Source distribution and wheel with `--no-sources` | 0 | 2 artifacts |

## Root Gap Matrix

| Root | Closed behavior | Named evidence |
|---:|---|---|
| 1 | Immutable, truthful local-only production authority | `test_production_capability_surface_remains_local_only`; CR-01 nodes |
| 2 | Bounded, symmetric, descriptor-anchored and durable evidence lifecycle | CR-03, CR-04, CR-07, CR-08 and WR-01 nodes |
| 3 | Exact schema, sanitized projection and one canonical full-chain proof | CR-05, CR-06 and WR-02 nodes |
| 4 | Collision-free exact identity, changed A-prime, and A/B/A resume | CR-02, WR-03 and packaged A-prime/A-B-A nodes |

## Review Finding Matrix

| Finding | Status | Named regression evidence |
|---|---|---|
| CR-01 | PASS | `test_prior_permissive_policy_path_is_not_a_public_runtime_input`; `test_remote_declaring_processor_is_rejected_before_invocation` |
| CR-02 | PASS | `test_changed_a_prime_completes_without_reuse_and_both_runs_inspect`; `test_semantic_result_twins_use_distinct_run_scoped_rows` |
| CR-03 | PASS | `test_unsupported_producer_is_rejected_before_run_creation` |
| CR-04 | PASS | `test_invalid_or_oversized_output_closes_lifecycle_before_manifest_io` |
| CR-05 | PASS | `test_full_chain_recomputes_result_id_after_coherent_manifest_rehash`; `test_every_bound_trust_entry_point_delegates_to_one_full_chain_verifier` |
| CR-06 | PASS | `test_persisted_diagnostic_and_telemetry_tampering_is_never_projected` |
| CR-07 | PASS | `test_parent_swap_after_state_anchor_cannot_redirect_state_or_manifests`; `test_parent_swap_during_failed_snapshot_cleanup_never_touches_attacker` |
| CR-08 | PASS | `test_manifest_sync_failure_never_advances_checkpoint`; `test_publication_sync_failure_prevents_terminal_transition` |
| WR-01 | PASS | `test_database_failure_after_manifest_never_advances_checkpoint`; `test_indeterminate_failure_closure_is_reconciled_on_next_open` |
| WR-02 | PASS | `test_malformed_schema_v2_fingerprint_is_rejected_without_mutation`; `test_schema_v2_integrity_failures_are_fixed_and_sanitized` |
| WR-03 | PASS | `test_a_interrupt_b_interrupt_a_rerun_resumes_exact_a_without_touching_b` |
| WR-04 | DEFERRED | Exact OS/syscall network denial remains assigned to **Phase 6**; it is not claimed as a Phase-1 fix. |

## Packaged CLI Facts

- Fresh happy and interruption/resume/inspect outputs were structured and full-chain
  verified, all nine stages completed after resume, six persisted prefix stages were
  reused unchanged, zero remote writes were reported, and the disclosure canary was
  absent from emitted and durable bytes.
- Changed A-prime created a distinct zero-reuse run; both the original interrupted run
  and the completed A-prime run passed strict inspect verification.
- A/B/A selected and resumed exact A with six reused stages while B's persisted rows
  and manifest bytes remained unchanged; the completed local publication plan reported
  zero remote writes.

## Canonical Machine Evidence

<!-- phase1-gap-evidence-json:start -->
{"cli_facts":{"a_b_a":{"b_manifest_bytes_unchanged":true,"b_rows_unchanged":true,"exact_a_resumed":true,"remote_writes_attempted":0,"reused_stage_count":6},"changed_a_prime":{"distinct_runs":true,"dual_inspect_verified":true,"new_run_reused_stage_count":0,"remote_writes_attempted":0},"happy_resume_inspect":{"disclosure_canary_present":false,"remote_writes_attempted":0,"reused_stage_count":6,"stage_count":9,"structured":true,"verified":true}},"commands":[{"argv_summary":"uv run --locked pytest -q <3 packaged CLI gap-acceptance nodes>","count":{"kind":"passed","value":3},"exit_code":0,"id":"packaged_cli"},{"argv_summary":"uv run --locked pytest -q <AST finding-map and production-capability nodes>","count":{"kind":"passed","value":2},"exit_code":0,"id":"mapping_capability"},{"argv_summary":"uv run --locked pytest -q <6 focused CR and WR modules>","count":{"kind":"passed","value":195},"exit_code":0,"id":"focused_findings"},{"argv_summary":"uv run --locked pytest --collect-only -q <7 explicit Phase-1 modules>","count":{"kind":"collected","value":200},"exit_code":0,"id":"phase1_collect"},{"argv_summary":"uv run --locked pytest -q","count":{"kind":"passed","value":200},"exit_code":0,"id":"full_pytest"},{"argv_summary":"uv run --locked ruff check .","count":{"kind":"checks","value":1},"exit_code":0,"id":"ruff"},{"argv_summary":"uv lock --check","count":{"kind":"checks","value":1},"exit_code":0,"id":"lock_check"},{"argv_summary":"uv build --no-sources","count":{"kind":"artifacts","value":2},"exit_code":0,"id":"build"}],"findings":{"CR-01":{"nodes":["tests/test_side_effect_policy.py::test_prior_permissive_policy_path_is_not_a_public_runtime_input","tests/test_side_effect_policy.py::test_remote_declaring_processor_is_rejected_before_invocation"],"status":"pass"},"CR-02":{"nodes":["tests/test_pipeline_resume.py::test_changed_a_prime_completes_without_reuse_and_both_runs_inspect","tests/test_state_integrity.py::test_semantic_result_twins_use_distinct_run_scoped_rows"],"status":"pass"},"CR-03":{"nodes":["tests/test_pipeline_resume.py::test_unsupported_producer_is_rejected_before_run_creation"],"status":"pass"},"CR-04":{"nodes":["tests/test_pipeline_resume.py::test_invalid_or_oversized_output_closes_lifecycle_before_manifest_io"],"status":"pass"},"CR-05":{"nodes":["tests/test_state_integrity.py::test_full_chain_recomputes_result_id_after_coherent_manifest_rehash","tests/test_state_integrity.py::test_every_bound_trust_entry_point_delegates_to_one_full_chain_verifier"],"status":"pass"},"CR-06":{"nodes":["tests/test_cli_security.py::test_persisted_diagnostic_and_telemetry_tampering_is_never_projected"],"status":"pass"},"CR-07":{"nodes":["tests/test_state_integrity.py::test_parent_swap_after_state_anchor_cannot_redirect_state_or_manifests","tests/test_state_integrity.py::test_parent_swap_during_failed_snapshot_cleanup_never_touches_attacker"],"status":"pass"},"CR-08":{"nodes":["tests/test_pipeline_resume.py::test_manifest_sync_failure_never_advances_checkpoint","tests/test_pipeline_resume.py::test_publication_sync_failure_prevents_terminal_transition"],"status":"pass"},"WR-01":{"nodes":["tests/test_pipeline_resume.py::test_database_failure_after_manifest_never_advances_checkpoint","tests/test_pipeline_resume.py::test_indeterminate_failure_closure_is_reconciled_on_next_open"],"status":"pass"},"WR-02":{"nodes":["tests/test_state_integrity.py::test_malformed_schema_v2_fingerprint_is_rejected_without_mutation","tests/test_state_integrity.py::test_schema_v2_integrity_failures_are_fixed_and_sanitized"],"status":"pass"},"WR-03":{"nodes":["tests/test_pipeline_resume.py::test_a_interrupt_b_interrupt_a_rerun_resumes_exact_a_without_touching_b"],"status":"pass"}},"hashes":{"frozen_v1_db":{"expected":"49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251","path":"tests/fixtures/state/v1-cli.db","post":"49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251","pre":"49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251"},"uv_lock":{"expected":"caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32","path":"uv.lock","post":"caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32","pre":"caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32"}},"roots":{"1":{"nodes":["tests/test_phase1_gap_closure.py::test_production_capability_surface_remains_local_only","tests/test_side_effect_policy.py::test_prior_permissive_policy_path_is_not_a_public_runtime_input","tests/test_side_effect_policy.py::test_remote_declaring_processor_is_rejected_before_invocation"],"status":"pass"},"2":{"nodes":["tests/test_pipeline_resume.py::test_unsupported_producer_is_rejected_before_run_creation","tests/test_pipeline_resume.py::test_invalid_or_oversized_output_closes_lifecycle_before_manifest_io","tests/test_state_integrity.py::test_parent_swap_after_state_anchor_cannot_redirect_state_or_manifests","tests/test_state_integrity.py::test_parent_swap_during_failed_snapshot_cleanup_never_touches_attacker","tests/test_pipeline_resume.py::test_manifest_sync_failure_never_advances_checkpoint","tests/test_pipeline_resume.py::test_publication_sync_failure_prevents_terminal_transition","tests/test_pipeline_resume.py::test_database_failure_after_manifest_never_advances_checkpoint","tests/test_pipeline_resume.py::test_indeterminate_failure_closure_is_reconciled_on_next_open"],"status":"pass"},"3":{"nodes":["tests/test_state_integrity.py::test_full_chain_recomputes_result_id_after_coherent_manifest_rehash","tests/test_state_integrity.py::test_every_bound_trust_entry_point_delegates_to_one_full_chain_verifier","tests/test_cli_security.py::test_persisted_diagnostic_and_telemetry_tampering_is_never_projected","tests/test_state_integrity.py::test_malformed_schema_v2_fingerprint_is_rejected_without_mutation","tests/test_state_integrity.py::test_schema_v2_integrity_failures_are_fixed_and_sanitized"],"status":"pass"},"4":{"nodes":["tests/test_pipeline_resume.py::test_changed_a_prime_completes_without_reuse_and_both_runs_inspect","tests/test_state_integrity.py::test_semantic_result_twins_use_distinct_run_scoped_rows","tests/test_pipeline_resume.py::test_a_interrupt_b_interrupt_a_rerun_resumes_exact_a_without_touching_b","tests/test_phase1_gap_closure.py::test_packaged_cli_changed_a_prime_dual_inspect_gap_acceptance","tests/test_phase1_gap_closure.py::test_packaged_cli_a_b_a_exact_resume_gap_acceptance"],"status":"pass"}},"schema_version":"1","wr_04":{"addressed_in":"Phase 6","status":"deferred"}}
<!-- phase1-gap-evidence-json:end -->
