---
status: complete
phase: 02-safe-single-repository-extraction
source: [02-VERIFICATION.md]
started: 2026-07-22T08:54:30Z
updated: 2026-07-22T09:51:33Z
---

## Current Test

[testing complete]

## Tests

### 1. - test: "Confirm prohibition (02-01): no dependency beyond httpx/openai entered the runtime graph, and neither package was synced, built, imported or executed before Gate B2 approved the exact new lock bytes.
expected: Held. NON-AUTHORITATIVE verdict: pyproject.toml [project].dependencies is exactly the sorted three-pin list (httpx==0.28.1, openai==2.46.0, pydantic==2.13.4 — verified by read); uv.lock SHA-256 recomputed this cycle equals the Gate-B2-approved a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216; `uv lock --check` exit 0 (24 packages); Gate A2/B2 approval records are in 02-01-SUMMARY.md (human gate signals, not agent-assertable).
result: pass

### 2. Confirm prohibition (02-01): the filter never passes a repository with a missing, unrecognized, NOASSERTION, multiple or conflicting license; license ambiguity is always a recorded deterministic rejection, never an LLM question.
expected: Held. NON-AUTHORITATIVE verdict: domain/filtering.py:170 (null/NOASSERTION/non-listed SPDX not in the exact four-member ALLOWED_LICENSE_SPDX → FAIL), :176 (multiple root license files → FAIL), :187-201 (unconfirmed/mismatched endpoint → FAIL, NOT_APPLICABLE gating); the license GET fires only when allowlist+single-file pass (processors.py:225-234) and no LLM exists on the filter path. Backed by tests/test_phase2_contracts.py license-boundary matrix and tests/test_scout_filter.py unconfirmed-outcome cases (inside this cycle's 618-test pass).
result: pass

### 3. Confirm prohibition (02-01): Phase 1 closed vocabularies were never narrowed, renamed or reordered; new members are additive-only and every pre-existing behavior assertion stays unchanged.
expected: Held. NON-AUTHORITATIVE verdict: git history since phase start shows Phase 1 file touches limited to the three sanctioned additive test amendments (b9f9971: test_stage_contracts.py + test_phase1_gap_closure.py; 91b0f83: test_cli_security.py subparser member), the disclosed LOCK_HASH re-anchor (ecb69aa, tool file), and the post-summary WR-04 review fix (8f84d3f: 37 insertions / 0 deletions — additive except-handler + new regression test). Full suite 618 passed.
result: pass

### 4. Confirm prohibition (02-02): the phase-two runtime never admits a REMOTE_WRITE registration, and neither build_dry_run_runtime nor PHASE_ONE_MAX_SCOPES was widened.
expected: Held. NON-AUTHORITATIVE verdict: PHASE_TWO_MAX_SCOPES = {NONE, LOCAL_STATE, REMOTE_READ} (pipeline.py:68-70); SideEffectPolicy.validate rejects any out-of-scope scope before invocation (pipeline.py:150-156); build_dry_run_runtime still uses phase_one() and its five-registration set (pipeline.py:784-829); backed by tests/test_phase2_pipeline.py#test_phase_two_policy_rejects_remote_write_before_invocation and test_phase_one_root_rejects_the_phase_two_processor (618-test pass).
result: pass

### 5. Confirm prohibition (02-02): GitHub credentials never appear in domain objects, stage payloads, manifests, SQLite rows, logs, stdout, request URLs or request bodies — the token exists only as an Authorization header read once from the environment at adapter construction.
expected: Held. NON-AUTHORITATIVE verdict: adapters/github.py:173 reads SKILLSCOUT_GITHUB_TOKEN once at construction; the Authorization header is the only use; backed by tests/test_github_adapter.py#test_canary_token_stays_in_the_authorization_header_only and tests/test_extractor_boundary.py#test_secret_canaries_stay_in_authorization_headers_only (rerun this cycle, pass).
result: pass

### 6. Confirm prohibition (02-02): the adapter never constructs a request URL from response-supplied fields, never follows a cross-host redirect, and never derives repository identity from names.
expected: Held. NON-AUTHORITATIVE verdict: fixed https://api.github.com base with templated paths (github.py:19, :218-296), follow_redirects=False with one same-host recorded redirect and cross-host → STAGE_PERMANENT_FAILURE; identity is the numeric metadata.id (processors.py:118-129, :409-411); backed by the tests/test_github_adapter.py redirect/closed-URL-set matrix (618-test pass).
result: pass

### 7. Confirm prohibition (02-02): a business rejection (filter failure, truncated tree, license 404, SHA-256 repository) is never represented as an infrastructure failure that consumes the three-attempt retry budget.
expected: Held. NON-AUTHORITATIVE verdict: Scout/Filter rejections return StageOutcome payloads (succeeded attempts; processors.py:170-190, :236-256) and downstream stages return deterministic skipped payloads (processors.py:756-765); only adapter-mapped infrastructure errors raise; backed by tests/test_scout_filter.py#test_rejected_run_completes_with_skips_and_consumes_no_retry_budget (attempt count 1 per stage; 618-test pass).
result: pass

### 8. Confirm prohibition (02-03): the raw read bundle is never persisted, logged or written to any durable, debug or diagnostic surface; only bounded metadata, blob SHAs, content hashes and policy-bounded excerpts leave process memory.
expected: Held. NON-AUTHORITATIVE verdict: the bundle lives only in context.scratch['read_bundle'] (processors.py:366); reader payload carries bounded files[]/rejections[] records only (processors.py:367-383); backed by tests/test_reader.py#test_reader_surfaces_carry_no_full_text_canary and tests/test_extractor_boundary.py#test_canary_disciplines_hold_on_the_extracted_happy_path (full-text canary absent from manifests, SQLite, stdout, extraction-summary.json; 618-test pass).
result: pass

### 9. Confirm prohibition (02-03): reading never silently truncates and claims completeness — every stop carries an explicit closed stop_reason and every skipped candidate a recorded rejection rule with its observed value.
expected: Held. NON-AUTHORITATIVE verdict: StopReason closed four-member set (reading.py:60-64) assigned on every exit path (processors.py:322-364); every skip appended as {path, rule, observed} (processors.py:585-586 and classification precedence :287-313); backed by the tests/test_reader.py order/budget/rejection matrix (618-test pass).
result: pass

### 10. Confirm prohibition (02-03): fetched content is never executed, imported, compiled or interpreted as instructions — repository text is inert data everywhere.
expected: Held. NON-AUTHORITATIVE verdict: source-wide grep shows no subprocess/importlib/socket/urllib/requests/aiohttp/eval/exec/compile usage; httpx is confined to adapters/github.py and openai to adapters/openai_extract.py (the sanctioned carve-outs); backed by tests/test_phase1_gap_closure.py#test_production_capability_surface_remains_local_only and tests/test_reader.py#test_reader_run_performs_only_recorded_mock_transport_http under the outbound socket sentinel (618-test pass).
result: pass

### 11. Confirm prohibition (02-04): untrusted repository text is never promoted into the developer or instruction role or interpreted as a tool call, even when it mimics system markup, fake tool invocations or earlier conversation turns.
expected: Held. NON-AUTHORITATIVE verdict: the developer message is EXTRACT_INSTRUCTIONS_V1 only (openai_extract.py:104-106 — zero repository bytes, standing inert-data rule); repository text enters only the user role inside <<<UNTRUSTED REPOSITORY FILE ...>>> delimiters (processors.py:675-689); the request has no tools key and store=False; backed by tests/test_openai_extract.py#test_request_shape_is_tool_less_store_false_with_strict_pydantic_schema and the seven-class tests/test_extractor_boundary.py#test_injection_corpus_never_gains_instruction_authority (rerun this cycle, pass).
result: pass

### 12. Confirm prohibition (02-04): a workflow whose evidence cannot be verified verbatim against recorded blobs never survives extraction to appear evidence-backed.
expected: Held. NON-AUTHORITATIVE verdict: validate_workflow_boundaries (extraction.py:164-217) drops unknown paths, blob_sha mismatches, non-verbatim or over-length excerpts and forbidden text; the extractor drops every violator with recorded reasons and all-dropped runs end schema_failure (processors.py:522-561); backed by the compromised-model fixtures (compromised_url_in_steps, compromised_fake_evidence) in tests/test_extractor_boundary.py (618-test pass).
result: pass

### 13. Confirm prohibition (02-04): a decided business outcome (filter rejection, refusal, incomplete, schema failure, no_workflow) is never retried by re-calling the LLM for a different answer.
expected: Held. NON-AUTHORITATIVE verdict: every decided outcome returns a StageOutcome payload without raising (processors.py:469-572); the SDK is constructed with max_retries=0 so one extract() is exactly one HTTP request (openai_extract.py:72-76); only transient infrastructure mappings raise; backed by recorded call-count assertions (exactly one OpenAI request per attempt, zero on filter-rejected/reader-empty paths) in tests/test_extractor_boundary.py and tests/test_cli_extract_repo.py (618-test pass).
result: pass

### 14. Confirm prohibition (02-04): model output never defines identity — fingerprints, workflow IDs, blob SHAs and content hashes are computed by skillscout and model-emitted identity is discarded.
expected: Held. NON-AUTHORITATIVE verdict: _build_workflow_spec computes the wf-fingerprint-v1 sha256 from repo id + normalized goal/steps and derives workflow_id = 'wf-' + fingerprint[7:23]; content_hash comes from the read record, never the model (processors.py:692-745; extraction.py:124-134); backed by the fingerprint stability/sensitivity/order tests in tests/test_phase2_contracts.py and tests/test_extractor_boundary.py (618-test pass).
result: pass

### 15. Confirm prohibition (02-04): GitHub/OpenAI credentials are never written to request bodies, logs, manifests, SQLite, stdout, extraction-summary.json or committed fixtures — including in tests, which use only declared canary values.
expected: Held. NON-AUTHORITATIVE verdict: both clients read keys once from the environment into Authorization headers only (github.py:173, openai_extract.py:69); backed by tests/test_extractor_boundary.py#test_secret_canaries_stay_in_authorization_headers_only and tests/test_openai_extract.py#test_api_key_canary_stays_in_the_authorization_header_only (rerun this cycle, pass) plus the full-text canary durable-surface sweeps.
result: pass

## Summary

total: 15
passed: 15
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
