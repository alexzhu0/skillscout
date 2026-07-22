---
phase: 02-safe-single-repository-extraction
verified: 2026-07-22T08:45:35Z
status: passed
score: 14/14 must-haves verified
behavior_unverified: 0
overrides_applied: 0
unverified_prohibitions: 15 # judgment-tier must_haves.prohibitions across plans 02-01..02-04 — human review recommended; each carries a NON-AUTHORITATIVE verdict backed by named code/test evidence below
human_verification:

  - test: "Confirm prohibition (02-01): no dependency beyond httpx/openai entered the runtime graph, and neither package was synced, built, imported or executed before Gate B2 approved the exact new lock bytes."
    expected: "Held. NON-AUTHORITATIVE verdict: pyproject.toml [project].dependencies is exactly the sorted three-pin list (httpx==0.28.1, openai==2.46.0, pydantic==2.13.4 — verified by read); uv.lock SHA-256 recomputed this cycle equals the Gate-B2-approved a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216; `uv lock --check` exit 0 (24 packages); Gate A2/B2 approval records are in 02-01-SUMMARY.md (human gate signals, not agent-assertable)."
    why_human: "Judgment-tier prohibition; the two-gate ceremony is a human supply-chain decision autonomous verify may not silently pass."

  - test: "Confirm prohibition (02-01): the filter never passes a repository with a missing, unrecognized, NOASSERTION, multiple or conflicting license; license ambiguity is always a recorded deterministic rejection, never an LLM question."
    expected: "Held. NON-AUTHORITATIVE verdict: domain/filtering.py:170 (null/NOASSERTION/non-listed SPDX not in the exact four-member ALLOWED_LICENSE_SPDX → FAIL), :176 (multiple root license files → FAIL), :187-201 (unconfirmed/mismatched endpoint → FAIL, NOT_APPLICABLE gating); the license GET fires only when allowlist+single-file pass (processors.py:225-234) and no LLM exists on the filter path. Backed by tests/test_phase2_contracts.py license-boundary matrix and tests/test_scout_filter.py unconfirmed-outcome cases (inside this cycle's 618-test pass)."
    why_human: "Judgment-tier prohibition; test-evidenced but declared without a verification tier."

  - test: "Confirm prohibition (02-01): Phase 1 closed vocabularies were never narrowed, renamed or reordered; new members are additive-only and every pre-existing behavior assertion stays unchanged."
    expected: "Held. NON-AUTHORITATIVE verdict: git history since phase start shows Phase 1 file touches limited to the three sanctioned additive test amendments (b9f9971: test_stage_contracts.py + test_phase1_gap_closure.py; 91b0f83: test_cli_security.py subparser member), the disclosed LOCK_HASH re-anchor (ecb69aa, tool file), and the post-summary WR-04 review fix (8f84d3f: 37 insertions / 0 deletions — additive except-handler + new regression test). Full suite 618 passed."
    why_human: "Judgment-tier prohibition; the byte-for-byte claim is git-evidenced but the item is undeclared-tier."

  - test: "Confirm prohibition (02-02): the phase-two runtime never admits a REMOTE_WRITE registration, and neither build_dry_run_runtime nor PHASE_ONE_MAX_SCOPES was widened."
    expected: "Held. NON-AUTHORITATIVE verdict: PHASE_TWO_MAX_SCOPES = {NONE, LOCAL_STATE, REMOTE_READ} (pipeline.py:68-70); SideEffectPolicy.validate rejects any out-of-scope scope before invocation (pipeline.py:150-156); build_dry_run_runtime still uses phase_one() and its five-registration set (pipeline.py:784-829); backed by tests/test_phase2_pipeline.py#test_phase_two_policy_rejects_remote_write_before_invocation and test_phase_one_root_rejects_the_phase_two_processor (618-test pass)."
    why_human: "Judgment-tier prohibition; test-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-02): GitHub credentials never appear in domain objects, stage payloads, manifests, SQLite rows, logs, stdout, request URLs or request bodies — the token exists only as an Authorization header read once from the environment at adapter construction."
    expected: "Held. NON-AUTHORITATIVE verdict: adapters/github.py:173 reads SKILLSCOUT_GITHUB_TOKEN once at construction; the Authorization header is the only use; backed by tests/test_github_adapter.py#test_canary_token_stays_in_the_authorization_header_only and tests/test_extractor_boundary.py#test_secret_canaries_stay_in_authorization_headers_only (rerun this cycle, pass)."
    why_human: "Judgment-tier prohibition; canary-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-02): the adapter never constructs a request URL from response-supplied fields, never follows a cross-host redirect, and never derives repository identity from names."
    expected: "Held. NON-AUTHORITATIVE verdict: fixed https://api.github.com base with templated paths (github.py:19, :218-296), follow_redirects=False with one same-host recorded redirect and cross-host → STAGE_PERMANENT_FAILURE; identity is the numeric metadata.id (processors.py:118-129, :409-411); backed by the tests/test_github_adapter.py redirect/closed-URL-set matrix (618-test pass)."
    why_human: "Judgment-tier prohibition; test-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-02): a business rejection (filter failure, truncated tree, license 404, SHA-256 repository) is never represented as an infrastructure failure that consumes the three-attempt retry budget."
    expected: "Held. NON-AUTHORITATIVE verdict: Scout/Filter rejections return StageOutcome payloads (succeeded attempts; processors.py:170-190, :236-256) and downstream stages return deterministic skipped payloads (processors.py:756-765); only adapter-mapped infrastructure errors raise; backed by tests/test_scout_filter.py#test_rejected_run_completes_with_skips_and_consumes_no_retry_budget (attempt count 1 per stage; 618-test pass)."
    why_human: "Judgment-tier prohibition; test-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-03): the raw read bundle is never persisted, logged or written to any durable, debug or diagnostic surface; only bounded metadata, blob SHAs, content hashes and policy-bounded excerpts leave process memory."
    expected: "Held. NON-AUTHORITATIVE verdict: the bundle lives only in context.scratch['read_bundle'] (processors.py:366); reader payload carries bounded files[]/rejections[] records only (processors.py:367-383); backed by tests/test_reader.py#test_reader_surfaces_carry_no_full_text_canary and tests/test_extractor_boundary.py#test_canary_disciplines_hold_on_the_extracted_happy_path (full-text canary absent from manifests, SQLite, stdout, extraction-summary.json; 618-test pass)."
    why_human: "Judgment-tier prohibition; canary-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-03): reading never silently truncates and claims completeness — every stop carries an explicit closed stop_reason and every skipped candidate a recorded rejection rule with its observed value."
    expected: "Held. NON-AUTHORITATIVE verdict: StopReason closed four-member set (reading.py:60-64) assigned on every exit path (processors.py:322-364); every skip appended as {path, rule, observed} (processors.py:585-586 and classification precedence :287-313); backed by the tests/test_reader.py order/budget/rejection matrix (618-test pass)."
    why_human: "Judgment-tier prohibition; test-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-03): fetched content is never executed, imported, compiled or interpreted as instructions — repository text is inert data everywhere."
    expected: "Held. NON-AUTHORITATIVE verdict: source-wide grep shows no subprocess/importlib/socket/urllib/requests/aiohttp/eval/exec/compile usage; httpx is confined to adapters/github.py and openai to adapters/openai_extract.py (the sanctioned carve-outs); backed by tests/test_phase1_gap_closure.py#test_production_capability_surface_remains_local_only and tests/test_reader.py#test_reader_run_performs_only_recorded_mock_transport_http under the outbound socket sentinel (618-test pass)."
    why_human: "Judgment-tier prohibition; sweep-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-04): untrusted repository text is never promoted into the developer or instruction role or interpreted as a tool call, even when it mimics system markup, fake tool invocations or earlier conversation turns."
    expected: "Held. NON-AUTHORITATIVE verdict: the developer message is EXTRACT_INSTRUCTIONS_V1 only (openai_extract.py:104-106 — zero repository bytes, standing inert-data rule); repository text enters only the user role inside <<<UNTRUSTED REPOSITORY FILE ...>>> delimiters (processors.py:675-689); the request has no tools key and store=False; backed by tests/test_openai_extract.py#test_request_shape_is_tool_less_store_false_with_strict_pydantic_schema and the seven-class tests/test_extractor_boundary.py#test_injection_corpus_never_gains_instruction_authority (rerun this cycle, pass)."
    why_human: "Judgment-tier prohibition; the injection-resistance claim is corpus-evidenced but warrants human countersign."

  - test: "Confirm prohibition (02-04): a workflow whose evidence cannot be verified verbatim against recorded blobs never survives extraction to appear evidence-backed."
    expected: "Held. NON-AUTHORITATIVE verdict: validate_workflow_boundaries (extraction.py:164-217) drops unknown paths, blob_sha mismatches, non-verbatim or over-length excerpts and forbidden text; the extractor drops every violator with recorded reasons and all-dropped runs end schema_failure (processors.py:522-561); backed by the compromised-model fixtures (compromised_url_in_steps, compromised_fake_evidence) in tests/test_extractor_boundary.py (618-test pass)."
    why_human: "Judgment-tier prohibition; test-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-04): a decided business outcome (filter rejection, refusal, incomplete, schema failure, no_workflow) is never retried by re-calling the LLM for a different answer."
    expected: "Held. NON-AUTHORITATIVE verdict: every decided outcome returns a StageOutcome payload without raising (processors.py:469-572); the SDK is constructed with max_retries=0 so one extract() is exactly one HTTP request (openai_extract.py:72-76); only transient infrastructure mappings raise; backed by recorded call-count assertions (exactly one OpenAI request per attempt, zero on filter-rejected/reader-empty paths) in tests/test_extractor_boundary.py and tests/test_cli_extract_repo.py (618-test pass)."
    why_human: "Judgment-tier prohibition; test-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-04): model output never defines identity — fingerprints, workflow IDs, blob SHAs and content hashes are computed by skillscout and model-emitted identity is discarded."
    expected: "Held. NON-AUTHORITATIVE verdict: _build_workflow_spec computes the wf-fingerprint-v1 sha256 from repo id + normalized goal/steps and derives workflow_id = 'wf-' + fingerprint[7:23]; content_hash comes from the read record, never the model (processors.py:692-745; extraction.py:124-134); backed by the fingerprint stability/sensitivity/order tests in tests/test_phase2_contracts.py and tests/test_extractor_boundary.py (618-test pass)."
    why_human: "Judgment-tier prohibition; test-evidenced but undeclared-tier."

  - test: "Confirm prohibition (02-04): GitHub/OpenAI credentials are never written to request bodies, logs, manifests, SQLite, stdout, extraction-summary.json or committed fixtures — including in tests, which use only declared canary values."
    expected: "Held. NON-AUTHORITATIVE verdict: both clients read keys once from the environment into Authorization headers only (github.py:173, openai_extract.py:69); backed by tests/test_extractor_boundary.py#test_secret_canaries_stay_in_authorization_headers_only and tests/test_openai_extract.py#test_api_key_canary_stays_in_the_authorization_header_only (rerun this cycle, pass) plus the full-text canary durable-surface sweeps."
    why_human: "Judgment-tier prohibition; canary-evidenced but undeclared-tier."
---

# Phase 2: Safe Single-Repository Extraction Verification Report

**Phase Goal:** 用户提供一个公开 GitHub 仓库，系统固定 commit、执行确定性过滤和有预算阅读，并返回最多三个有证据的 `WorkflowSpec` 或清晰的过滤/无工作流结论；任何候选内容都不会被执行或传入下游。
**Verified:** 2026-07-22T08:45:35Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Roadmap success criteria (rows 1–6, the contract) merged with plan-frontmatter must-haves that add plan-specific detail (rows 7–14).

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | SC1: 对人工指定仓库，系统只通过 GitHub REST 读取固定 SHA 的允许文本，按 README → docs → examples → 包清单 → 源码顺序及默认预算 early stop | ✓ VERIFIED | Scout pins 40-hex before any content read and rejects 64-hex repos (`processors.py:131-168`; `test_every_content_url_embeds_the_pinned_sha_after_resolution` rerun, pass); `TIER_ORDER` fixed five-tier (`reading.py:51-57`); reader sorts (tier, path) and gates five budgets before fetch (`processors.py:258-391`); early stop only after examples tier at 24000 soft tokens (`processors.py:356-361`); `test_reader_stops_at_max_files_before_the_26th_fetch` rerun, pass; only templated api.github.com endpoints (`github.py:19-25, 218-296`). |
| 2 | SC2: 每个确定性过滤决定包含规则、观察值和理由；不明确许可证或其他硬门槛不会调用 LLM | ✓ VERIFIED | `RuleDecision` carries rule_id, `filter-policy-v1` version, observed, pass/fail/not_applicable, closed rationale enforced by validator (`filtering.py:48-61`); all eight rules in fixed order with license boundaries failing closed (`filtering.py:117-208`); license GET only when allowlist+single-file pass (`processors.py:225-234`); filter stage is pure deterministic code — no LLM exists on the path; rule-matrix tests in `test_phase2_contracts.py`/`test_scout_filter.py` inside the 618-test pass. |
| 3 | SC3: Extractor 使用无工具、store=false 的严格结构化请求，输出 0–3 个符合契约的 WorkflowSpec，并把拒绝/schema 失败保存为可诊断结果 | ✓ VERIFIED | Single `responses.parse` call site (grep count 1) with `text_format=ExtractorResponse`, `store=False`, bounded `max_output_tokens=8000`, no `tools` argument, `max_retries=0` (`openai_extract.py:97-122`); developer role is `EXTRACT_INSTRUCTIONS_V1` only, repository text user-role-only inside untrusted delimiters; outcomes extracted/no_workflow/refused/incomplete/schema_failure as succeeded-attempt payloads (`processors.py:469-572`); `ExtractorResponse.workflows` schema-capped at 3 (`extraction.py:64-71`); request-shape test inside 618-test pass. |
| 4 | SC4: 每个工作流的关键目标和步骤都有来源路径、blob/content hash 和必要短证据；fingerprint 对相同规范化语义稳定 | ✓ VERIFIED | Every evidence ref carries path + blob_sha + ≤280-char excerpt + skillscout-bound content_hash (`extraction.py:74-88`, `processors.py:736-745`); workflow- and step-level evidence require ≥1 entry by schema and must verify verbatim against recorded blobs or the workflow drops (`extraction.py:178-189`); `workflow_fingerprint` hashes the versioned wf-fingerprint-v1 preimage over NFKC/casefold/punctuation-stripped goal+steps (`extraction.py:114-134`); fingerprint stability/sensitivity/order tests inside 618-test pass. |
| 5 | SC5: Prompt Injection fixture 无法触发工具、网络动作、密钥访问或跨越 WorkflowSpec；Phase 2 输出可证明没有完整原始仓库内容 | ✓ VERIFIED | Seven injection classes run the full Scout→Filter→Reader→Extractor path with injected text only inside user-role delimiters and zero effect beyond one recorded call — `test_injection_corpus_never_gains_instruction_authority[7 classes]` rerun, pass; full-text canary absent from manifests/SQLite/stdout/extraction-summary.json while the evidence canary appears only as a bounded excerpt; secret canaries confined to Authorization headers — `test_secret_canaries_stay_in_authorization_headers_only` rerun, pass; WorkflowSpec is the only semantic artifact (`_build_workflow_spec` emits bounded fields only). |
| 6 | SC6: 测试证明流程不会 clone、安装、构建、import、运行示例，且会拒绝二进制、超预算、子模块、LFS 和路径异常 | ✓ VERIFIED | Source-wide grep: no subprocess/importlib/socket/urllib/requests/aiohttp/eval/exec/compile; httpx only in `adapters/github.py`, openai only in `adapters/openai_extract.py` (sanctioned carve-outs); capability sweep `test_production_capability_surface_remains_local_only` and `test_reader_run_performs_only_recorded_mock_transport_http` inside 618-test pass; full rejection matrix: path violations (incl. framing metacharacters — WR-01 fix `reading.py:120-123`), submodule 160000, symlink 120000, non-allowlisted extensions, over-size never fetched; binary/LFS rejected after exactly one fetch (`processors.py:287-340, 609-620`). |
| 7 | Plan 02-01: exactly httpx==0.28.1 + openai==2.46.0 admitted through the two-gate ceremony; execution bound to exact approved lock bytes | ✓ VERIFIED | `pyproject.toml` dependencies are exactly the three sorted pins (read directly); `uv.lock` SHA-256 recomputed = Gate-B2-approved `a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216`; `uv lock --check` exit 0 (24 packages); gate approval records in 02-01-SUMMARY.md (human signals — see prohibition 1). |
| 8 | Plan 02-01: RepositorySubject strictness and load_subject closed non-echoing INVALID_SUBJECT mapping | ✓ VERIFIED | SubjectId/URL/ref patterns with `..`/slash/backslash/`@{` rejection and subject_id↔URL owner-name validator (`subjects.py:11-65`); loader is bounded single-descriptor: lstat, O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC, fstat identity recheck, cap-plus-one probe, mid-read identity recheck, strict decode, every failure `raise SafeFailure(INVALID_SUBJECT) from None` (`adapters/subjects.py:29-82`); strictness matrix inside 618-test pass. |
| 9 | Plan 02-02: profile-driven runner, telemetry on attempt+envelope+output hash, COMPLETED terminal, skip cascade with zero retry-budget consumption | ✓ VERIFIED | `PIPELINE_PROFILES` with import-time spine-prefix guard (`pipeline.py:168-188`); `record_attempt_telemetry` on the running attempt before `complete_stage` (`pipeline.py:532`); `ExtractionSummary` durable artifact via `_ExtractionSummaryWriter` (65 536-byte cap); rejected Scout/Filter → deterministic skipped payloads downstream with attempt count 1 (`processors.py:92-109, 756-765`; skip-cascade/retry tests inside 618-test pass). |
| 10 | Plan 02-02/02-04: phase-two composition root admits at most REMOTE_READ under a closed seven-registration registry with concrete-type checks | ✓ VERIFIED | `build_phase_two_runtime` registry: phase2_processor, sqlite_and_manifests, github_read, openai_extract, clock, run_ids, extraction_summary_writer with `type(...) is` checks and `SideEffectPolicy.phase_two()` = {NONE, LOCAL_STATE, REMOTE_READ} (`pipeline.py:832-874`); no policy/registration parameters; `build_dry_run_runtime` and `PHASE_ONE_MAX_SCOPES` untouched (`pipeline.py:65-67, 784-829`); root-policy tests inside 618-test pass. |
| 11 | Plan 02-03: hash-verified resume hydration; raw bundle memory-only | ✓ VERIFIED | `hydrate_read_bundle` re-fetches at recorded blob SHAs in read_order, re-runs binary/LFS checks, requires exact sha256 content-hash equality, else `STAGE_PERMANENT_FAILURE from None` (`processors.py:623-666`); `test_hydrate_read_bundle_fails_closed_on_tampered_bytes` rerun, pass; bundle only in `context.scratch` (`processors.py:366`); canary sweeps inside 618-test pass. |
| 12 | Plan 02-04: extract-repo CLI happy path, filter-rejection zero-LLM, resume/idempotency, hostile-subject closure | ✓ VERIFIED | CLI branch builds only via `build_phase_two_runtime` with environment-only credentials and closed `--fail-after` choices (`cli.py:55-59, 74-85`); `test_extract_repo_resume_and_idempotent_rerun` and the full `test_cli_extract_repo.py` (5 cases) rerun, pass — Scout/Filter call counts stay 1, exactly one total LLM call, zero-call third run via the COMPLETED-gated `find_completed_run` short-circuit (`pipeline.py:319-339`); malformed/oversized/symlinked subjects fail closed as `invalid_subject` without state or echo. |
| 13 | Plan 02-04: at most one extraction call per attempt and at most three workflows per repository as structural limits | ✓ VERIFIED | SDK `max_retries=0` makes one `extract()` exactly one HTTP request (`openai_extract.py:72-76`); `ExtractorResponse.workflows` capped at `max_length=3` (`extraction.py:69-71`) and the handler's over-cap branch returns schema_failure (`processors.py:508-520`); 0/1/2/3/4-workflow fixtures inside 618-test pass. |
| 14 | All plans: Phase 1 authority intact — additive-only members, sanctioned test amendments only, full suite green | ✓ VERIFIED | `RunStatus.COMPLETED` additive terminal (`enums.py:38, 58, 64`), `("2","phase2-v1")` registry member (`models.py:36`), `ErrorCode.INVALID_SUBJECT` with fixed summary (`ports.py:40, 58`); git history shows Phase 1 touches limited to the three sanctioned additive test amendments, the disclosed LOCK_HASH re-anchor (ecb69aa), and the post-summary WR-04 review fix (8f84d3f — 37 insertions/0 deletions, additive except-handler + regression test); full suite 618 passed, ruff clean. |

**Score:** 14/14 truths verified (0 present, behavior-unverified)

Behavior-dependent truths (9, 11, 12 — telemetry-before-completion, hash-verified hydration, resume/zero-call reuse) are VERIFIED on rerun named behavioral tests, not symbol presence: `test_completed_phase_two_run_is_fully_reused_without_reexecution`, `test_hydrate_read_bundle_fails_closed_on_tampered_bytes`, `test_extract_repo_resume_and_idempotent_rerun` all passed this cycle.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/skillscout/domain/subjects.py` (65 lines) | RepositorySubject run-authority contract | ✓ VERIFIED | All four exported types present; strict frozen, extra-field rejection via StrictFrozenModel; owner-name cross-validator at :60-65. |
| `src/skillscout/adapters/subjects.py` (82 lines) | Bounded single-descriptor loader | ✓ VERIFIED | `MAX_SUBJECT_BYTES = 65_536`; full descriptor discipline; closed INVALID_SUBJECT mapping. |
| `src/skillscout/domain/filtering.py` (208 lines) | filter-policy-v1 closed rules + pure verdict | ✓ VERIFIED | Eight-rule ordered set, exact four-SPDX allowlist, closed rationales, verdict coherence validator. |
| `src/skillscout/domain/reading.py` (173 lines) | reader-policy-v1 budgets/tiers/predicates | ✓ VERIFIED | Five budgets = org ceilings with above-ceiling rejection; fixed TIER_ORDER; path predicate incl. WR-01 metacharacter rejection; ceil(bytes/4). |
| `src/skillscout/domain/extraction.py` (217 lines) | extractor-response/workflow-spec contracts, fingerprint, boundary validation | ✓ VERIFIED | Structured-Outputs shape (all-required, maxItems 3); full EXTR-03 field list; skillscout-owned fingerprint; five closed drop reasons. |
| `src/skillscout/adapters/github.py` (425 lines) | Closed read-only GitHub REST adapter | ✓ VERIFIED | Fixed base/version, per-endpoint caps, bounded Retry-After, same-host redirects, total error mapping, CR-01 whitespace-stripped strict base64 (:302), WR-02 collapsed RedirectFacts. |
| `src/skillscout/adapters/openai_extract.py` (186 lines) | Closed no-tools store=false extraction adapter | ✓ VERIFIED | One `responses.parse` site; `store=False`; no tools; `max_retries=0`; versioned developer-only instructions; WR-03 collapsed telemetry validation (:174-176). |
| `src/skillscout/application/processors.py` (822 lines) | PhaseTwoProcessor Scout/Filter/Reader/Extractor + hydration | ✓ VERIFIED | All four handlers + skip cascade + `_read_budget_stop` + `_classify_blob_content` + `hydrate_read_bundle` read and matched to contracts. |
| `src/skillscout/application/pipeline.py` (883 lines) | Profiles, phase-two root, telemetry seam, terminal, reuse seam | ✓ VERIFIED | Import-time prefix guard; seven-registration root; COMPLETED-gated `find_completed_run` short-circuit with verify_run_chain first. |
| `src/skillscout/application/ports.py` (252 lines) | Additive carriers + INVALID_SUBJECT | ✓ VERIFIED | StageTelemetry/StageOutcome/StageContext/ContextStageProcessor; `find_completed_run`/`record_attempt_telemetry` protocol members. |
| `src/skillscout/cli.py` (116 lines) | extract-repo subcommand | ✓ VERIFIED | Sibling of dry-run; closed fail-after choices; sanitized SafeFailure/exception handlers only. |
| Test modules (4 872 lines across 9 files) | Contract/adapter/pipeline/scout-filter/reader/openai/boundary/CLI evidence | ✓ VERIFIED | All present, substantive, and green (618 total with the rest of the suite). |
| Fixture sets | Recorded GitHub (24), OpenAI (9), injection (7), subject (1) | ✓ VERIFIED | All present incl. post-review `blob_readme_wrapped.json`; both canary sentences confirmed inside the decoded 228-byte README blob; full-text canary in all 7 injection files. |
| `pyproject.toml` / `uv.lock` | Three sorted pins / Gate-B2 bytes | ✓ VERIFIED | Exact pins read; SHA-256 recomputed equal to approved hash; `lock --check` exit 0. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `pyproject.toml` | `uv.lock` | non-building discovery under managed CPython; approved bytes | ✓ WIRED | `httpx==0.28.1` declared; lock contains httpx/openai nodes; hash matches Gate B2. |
| `domain/extraction.py` | `domain/canonical.py` | keyword-only versioned fingerprint preimage over `sha256_digest` | ✓ WIRED | `workflow_fingerprint` embeds `wf-fingerprint-v1` in the preimage (:124-134). |
| `domain/models.py` | `application/pipeline.py` | additive ("2","phase2-v1") registration read by the producer gate | ✓ WIRED | `SUPPORTED_PRODUCER_SCHEMAS` checked at pipeline.py:295 before profile resolution. |
| `application/pipeline.py` | `adapters/state.py` | telemetry onto the running attempt before complete_stage | ✓ WIRED | `record_attempt_telemetry` called at pipeline.py:532; implemented at state.py:2223. |
| `application/processors.py` | `adapters/github.py` | content URLs embed the pinned SHA after resolve_commit | ✓ WIRED | tree/license paths take `pinned`; blob paths take tree-declared blob SHA; `test_every_content_url_embeds_the_pinned_sha_after_resolution` rerun, pass. |
| `application/processors.py` | `adapters/openai_extract.py` | exactly one responses.parse per attempt | ✓ WIRED | Single call site (grep count 1); one extract() per `_extractor` invocation (:450-452). |
| `application/processors.py` | `domain/extraction.py` | deterministic boundary validation + fingerprint after every parse | ✓ WIRED | `validate_workflow_boundaries` at :525; `_build_workflow_spec` at :532. |
| `cli.py` | `application/pipeline.py` | extract-repo builds only through build_phase_two_runtime | ✓ WIRED | cli.py:77-80 constructs processor + root; no other composition path. |
| `tests/recorded_transport.py` | `tests/fixtures/{github,openai}` | recorded (method, path) responses; call counts as no-replay evidence | ✓ WIRED | Loader present (159 lines); CLI resume/idempotency case asserts on retained recorders (rerun, pass). |

### Data-Flow Trace (Level 4)

| Artifact | Data source | Sink | Status |
|---|---|---|---|
| Scout payload | Recorded/real GitHub metadata+tree via `GitHubReadClient` | stage envelope + manifests (bounded facts only) | ✓ FLOWING — numeric repo id, pinned SHA, ≤512 candidate projection |
| Reader payload | Scout candidates + `get_blob` bytes under budgets | bounded files[]/rejections[] record; raw text to scratch only | ✓ FLOWING — full-text canary absent from every durable surface |
| Extractor payload | scratch/hydrated bundle → one user-role request | WorkflowSpec survivors with skillscout-owned identity | ✓ FLOWING — model output never defines identity; drops recorded |
| ExtractionSummary | verified run chain envelopes | `extraction-summary.json` via locked/atomic/fsync core | ✓ FLOWING — parses as ExtractionSummary in CLI happy-path test (rerun, pass) |
| Credentials | environment, read once at construction | Authorization headers only | ✓ FLOWING + CONFINEMENT PROVEN — canary tests rerun, pass |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full locked suite (run once) | `uv run --locked pytest -q` | `618 passed in 19.83s` | ✓ PASS |
| Ruff | `uv run --locked ruff check .` | `All checks passed!` | ✓ PASS |
| Lock integrity | `uv lock --check` + `shasum -a 256 uv.lock` | Resolved 24 packages; hash = approved `a23c4711…` | ✓ PASS |
| Pinned-SHA URL invariant; secret-canary confinement; 7-class injection corpus; CLI resume/idempotency; completed-run full reuse; 26th-file budget stop; tampered-hydration closure; all 5 CLI E2E cases (17 named tests) | `uv run --locked pytest -q <17 named nodes>` | `17 passed in 2.14s` | ✓ PASS |
| httpx/openai confinement | `grep -rn "^import httpx\|^from httpx\|^import openai\|^from openai" src/skillscout/` | only `adapters/github.py` + `adapters/openai_extract.py` | ✓ PASS |
| Canary presence in decoded README blob | python3 decode of `blob_readme.json` | both canary sentences present; size 228 consistent | ✓ PASS |

### Probe Execution

No `probe-*.sh` is declared in any plan or present in the repository (`find scripts -path '*/tests/probe-*.sh'` — no matches; no `scripts/` tree). Step 7c: SKIPPED (no declared or conventional probes).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| FILT-01 | 02-01, 02-02 | Deterministic rejection of non-public/archived/fork/no-default-branch/no-README repos | ✓ SATISFIED | `evaluate_filter` rules 1–5 with observed values (`filtering.py:137-169`); variant fixtures each fail their named rule (`test_scout_filter.py`, 618-test pass). |
| FILT-02 | 02-01, 02-02 | Exact {MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause} single repo-level license; null/NOASSERTION/non-listed/multiple/conflicting rejected | ✓ SATISFIED | `ALLOWED_LICENSE_SPDX` exact (`filtering.py:14`); endpoint confirmation gated at :187-201; all boundary fixtures reject deterministically. |
| FILT-03 | 02-01, 02-02 | Versioned rule/observed/result/rationale records; hard gates never reach the LLM | ✓ SATISFIED | `RuleDecision` closed-rationale validator; skip cascade keeps rejected runs at zero LLM calls (CLI filter-rejection case, rerun pass). |
| READ-01 | 02-02 | Pin exact commit before reads; no floating refs | ✓ SATISFIED | `resolve_commit` + 40-hex requirement + sha256 rejection (`processors.py:131-142`); pinned-SHA URL invariant test rerun, pass. |
| READ-02 | 02-03 | Fixed README → docs → examples → manifests → source order | ✓ SATISFIED | `TIER_ORDER` + (tier, path) sort; read_order sequence proof in `test_reader.py`. |
| READ-03 | 02-01, 02-03 | Five default budgets (25/5/128KiB/512KiB/40k tokens); run cannot exceed org ceilings | ✓ SATISFIED | `ReaderPolicy` defaults = ceilings with above-ceiling rejection (`reading.py:77-108`); ±1 boundary tests (`test_reader_stops_at_max_files_before_the_26th_fetch` rerun, pass). |
| READ-04 | 02-03 | Early stop + structured read record (files, SHAs, hashes, order, budgets, source flag, stop reason) | ✓ SATISFIED | Soft-target rule at `processors.py:356-361`; complete payload record :367-383. |
| READ-05 | 02-01, 02-03 | Reject binary, archives, submodules, LFS, over-budget, path traversal, non-allowlisted content | ✓ SATISFIED | Full matrix with never-fetched/exactly-one-fetch discipline (`processors.py:287-340, 609-620`); hostile path shapes incl. WR-01 metacharacters. |
| READ-06 | 02-03 | No clone/install/build/import/execute of candidate code | ✓ SATISFIED | Capability sweep + socket-sentinel runtime proof; source grep clean. |
| EXTR-01 | 02-04 | Tool-less strict structured request; diagnosable refusal/schema failure | ✓ SATISFIED | Request-shape contract (store=false, no tools, Pydantic-generated schema); four closed outcome classes with sanitized diagnostics. |
| EXTR-02 | 02-01, 02-04 | ≤3 independent workflows with independent evidence and stable fingerprints | ✓ SATISFIED | Schema cap 3 + over-cap schema_failure; fingerprint stability/sensitivity/order tests. |
| EXTR-03 | 02-01, 02-04 | Full WorkflowSpec field list | ✓ SATISFIED | All 13 content fields plus identity/fingerprint/evidence on `WorkflowSpec` (`extraction.py:91-111`); emitted by `_build_workflow_spec`. |
| EXTR-04 | 02-04 | WorkflowSpec as the sole semantic trust boundary downstream | ✓ SATISFIED | Bounded excerpts only; full-text canary sweeps across manifests/SQLite/stdout/summary. |
| SEC-01 | 02-04 | store=false, no tools, no keys in requests, untrusted-input handling | ✓ SATISFIED | Request-shape proof; injection corpus; secret-canary confinement (rerun, pass). |

**Orphan check:** REQUIREMENTS.md maps exactly these 14 IDs to Phase 2; the union of plan-declared IDs (02-01: FILT-01/02/03, READ-03/05, EXTR-02/03; 02-02: FILT-01/02/03, READ-01; 02-03: READ-02/03/04/05/06; 02-04: EXTR-01/02/03/04, SEC-01) covers all 14. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | Debt markers (TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER) | none | grep across all phase-modified source/test/tool files: zero matches. |
| `adapters/state.py` | 584-585 | IN-01: `validate_child_name` raises non-SafeFailure before constructor try | ℹ️ Info (documented) | 02-REVIEW info finding, out of fix scope; CLI generic handler still closes it (exit 1, state_operation_failed). |
| `application/processors.py` | 508-520 | IN-02: unreachable workflow-count overflow branch | ℹ️ Info (documented) | Deliberate defense-in-depth; strict schema rejects first. |
| `application/pipeline.py` | 319-339 | IN-03: reuse-path `reused_stage_count` is invocation-scoped, not ledger-derived | ℹ️ Info (documented) | Reporting inconsistency only; `verify_run_chain` still gates reuse. |

No stubs, hollow wiring, or blockers found. The 02-REVIEW CR-01 + WR-01..04 fixes (post-summary) were independently re-verified in code: whitespace-stripped strict base64 (`github.py:302`), metacharacter path rejection (`reading.py:120-123`), collapsed RedirectFacts, collapsed OpenAI telemetry validation (`openai_extract.py:174-176`), and the candidate-connection disposal (`state.py` final except handler — 37-insertion/0-deletion additive diff).

### Human Verification Required

Fifteen judgment-tier `must_haves.prohibitions` from the four plans' frontmatter (structured in frontmatter `human_verification`). Each already carries a NON-AUTHORITATIVE verdict backed by named code locations and tests that passed this cycle — the checkpoint is a countersign formality, not new testing. Headline items: the Gate A2/B2 supply-chain approvals (inherently human), license fail-closed filtering, Phase 1 vocabulary immutability, REMOTE_READ ceiling, credential confinement, no business-outcome retries, memory-only raw bundle, no candidate execution, untrusted-text non-promotion, evidence-verbatim survival, and skillscout-owned identity.

### Gaps Summary

None. All six roadmap success criteria and all eight merged plan-level must-have groups verify against the actual code: artifacts exist, are substantive, wired, and behaviorally exercised by a suite I ran myself (618 passed; 17 named behavior tests rerun; ruff clean; lock check pass; approved lock hash recomputed equal). All 14 requirement IDs are satisfied with no orphans. The only outstanding items are the 15 judgment-tier prohibition confirmations routed to the end-of-phase human checkpoint, plus three documented info-level review findings (IN-01..03) deliberately left out of the fix scope.

**Follow-up (not a phase-2 gap):** the Phase 1 authority-bound evidence document (01-GAP-VALIDATION.md) binds the superseded Phase 1 lock hash and is stale by design after Gate B2; re-recording against the Gate-B2 graph is tracked as Phase 2 validation follow-up in 02-01-SUMMARY.md. Phase 1's own verification remains `passed` against its own baseline.

---

_Verified: 2026-07-22T08:45:35Z_
_Verifier: the agent (gsd-verifier)_
