---
quick_id: 260727-mfm
title: Add a safe DeepSeek V4 Flash provider path
phase: quick-260727-mfm
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - src/skillscout/adapters/semantic_provider.py
  - src/skillscout/adapters/openai_extract.py
  - src/skillscout/adapters/openai_generate.py
  - src/skillscout/adapters/openai_review.py
  - src/skillscout/application/phase3.py
  - src/skillscout/bootstrap.py
  - src/skillscout/cli.py
  - tests/test_semantic_provider.py
  - tests/test_openai_extract.py
  - tests/test_openai_generate.py
  - tests/test_openai_review.py
  - .gitignore
  - skillscout-catalog-test.2026-07-24.private-key.pem
  - .planning/quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/260727-mfm-PEM-AUTH-EVIDENCE.json
must_haves:
  truths:
    - Explicitly selecting DeepSeek makes extraction, generation, and independent review use DeepSeek V4 Flash through the official HTTPS Chat Completions endpoint, while the default OpenAI provider continues to issue its existing Responses requests unchanged.
    - DeepSeek responses become existing SkillScout result contracts only after strict local Pydantic validation; empty, truncated, malformed, extra-field, and provider-error responses fail through the existing closed outcome and SafeFailure vocabulary.
    - Both provider paths make one tool-less request per attempt with SDK retries disabled, keep untrusted source text in the user-message boundary, and never emit or persist either provider key or base URL.
    - The local GitHub App PEM is ignored, reduced from mode 0644 to owner-only mode 0600, and bound to a fresh successful read-only GitHub App/installation authentication receipt before it is moved intact to macOS Trash; any failed or missing proof aborts the move without exposing credentials.
  artifacts:
    - path: src/skillscout/adapters/semantic_provider.py
      provides: Closed provider selection, official DeepSeek endpoint validation, environment-name mapping, and provider-specific structured request helpers
    - path: src/skillscout/adapters/openai_extract.py
      provides: Extraction result contract backed by either unchanged OpenAI Responses or guarded DeepSeek Chat Completions
    - path: src/skillscout/adapters/openai_generate.py
      provides: Generator result contract backed by either unchanged OpenAI Responses or guarded DeepSeek Chat Completions
    - path: src/skillscout/adapters/openai_review.py
      provides: Reviewer result contract backed by either unchanged OpenAI Responses or guarded DeepSeek Chat Completions
    - path: tests/test_semantic_provider.py
      provides: Provider, endpoint, credential-boundary, and strict Chat Completions contract tests
    - path: .gitignore
      provides: Ignore coverage for private-key file patterns before PEM removal
    - path: .planning/quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/260727-mfm-PEM-AUTH-EVIDENCE.json
      provides: Non-secret bounded receipt for the successful read-only GitHub App and installation identity confirmation performed before the PEM move
  key_links:
    - from: src/skillscout/cli.py
      to: src/skillscout/adapters/semantic_provider.py
      via: The composition root resolves one explicit provider selection and constructs all semantic clients from the matching nonsecret model profile and secret environment binding
      pattern: "semantic_provider|provider"
    - from: src/skillscout/adapters/semantic_provider.py
      to: https://api.deepseek.com/chat/completions
      via: Only the exact official HTTPS origin is admitted before the OpenAI SDK Chat Completions client is constructed with max_retries=0
      pattern: "https://api\\.deepseek\\.com"
    - from: src/skillscout/adapters/openai_extract.py
      to: skillscout.domain.extraction.ExtractorResponse
      via: DeepSeek message content is parsed locally with strict Pydantic validation before entering ExtractionResult
      pattern: "ExtractorResponse.*model_validate_json|model_validate_json.*ExtractorResponse"
    - from: src/skillscout/adapters/openai_generate.py
      to: skillscout.domain.skill_artifacts.GeneratedSkillDraft
      via: DeepSeek message content is parsed locally with strict Pydantic validation before entering GenerationResult
      pattern: "GeneratedSkillDraft.*model_validate_json|model_validate_json.*GeneratedSkillDraft"
    - from: src/skillscout/adapters/openai_review.py
      to: skillscout.domain.review.ReviewerJudgment
      via: DeepSeek message content is parsed locally with strict Pydantic validation before entering ReviewResult
      pattern: "ReviewerJudgment.*model_validate_json|model_validate_json.*ReviewerJudgment"
    - from: .gitignore
      to: skillscout-catalog-test.2026-07-24.private-key.pem
      via: git check-ignore, file identity/mode hardening, and read-only authentication evidence must all succeed before the exact untracked PEM is moved to the explicit macOS Trash destination
      pattern: "\\*\\.pem|private-key\\.pem"
    - from: .planning/quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/260727-mfm-PEM-AUTH-EVIDENCE.json
      to: /Users/alexzhu/.Trash/skillscout-catalog-test.2026-07-24.private-key.pem
      via: The receipt records only bounded non-secret App/installation identifiers, endpoint outcomes, timestamp, basename, and public-key fingerprint after successful JWT authentication and before the no-overwrite move
      pattern: "github-app-pem-auth-evidence-v1"
---

<objective>
Add a guarded DeepSeek V4 Flash execution path for all three semantic stages without weakening the existing OpenAI Responses, validation, injection, retry, telemetry, or secret-handling contracts.

Purpose: Allow a local operator to select the lower-cost DeepSeek provider safely while preserving the deterministic and auditable boundaries that make semantic provider output non-authoritative until validated.
Output: A closed provider configuration/transport seam, DeepSeek-aware semantic adapters and composition roots, mock-backed regression/security tests, and recoverable removal of the verified local GitHub App PEM.
</objective>

<execution_context>
@/Users/alexzhu/.codex/gsd-core/workflows/execute-plan.md
@/Users/alexzhu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/STATE.md
@.planning/PROJECT.md
@src/skillscout/adapters/openai_extract.py
@src/skillscout/adapters/openai_generate.py
@src/skillscout/adapters/openai_review.py
@src/skillscout/application/phase3.py
@src/skillscout/bootstrap.py
@src/skillscout/cli.py
@tests/test_openai_extract.py
@tests/test_openai_generate.py
@tests/test_openai_review.py
@.gitignore

DeepSeek's official OpenAI-format base URL is `https://api.deepseek.com`, its current Flash model ID is `deepseek-v4-flash`, and its supported structured route is Chat Completions JSON Output rather than Responses schema parsing. JSON Output guarantees JSON syntax, not conformance to SkillScout's Pydantic schema, so local `model_validate_json(..., strict=True)` remains mandatory.

The root `.env` is already ignored. Never read, print, diff, serialize, or persist `.env`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, private PEM bytes, JWTs, installation tokens, Authorization headers, or raw GitHub response bodies. The prior interactive PEM authentication succeeded but has no durable receipt; Task 3 must therefore perform a fresh bounded read-only JWT confirmation and persist only the allowed non-secret evidence before moving the file. Do not mint an installation token, request write permissions, or broaden GitHub authority.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Define the closed provider and official-endpoint boundary</name>
  <files>src/skillscout/adapters/semantic_provider.py, tests/test_semantic_provider.py</files>
  <behavior>
    - With no provider selection, configuration resolves to the existing OpenAI provider, existing default models, `OPENAI_API_KEY`, no custom base URL, and no change to Responses behavior.
    - An explicit DeepSeek selection resolves only `DEEPSEEK_API_KEY`, requires `DEEPSEEK_BASE_URL`, fixes the model to `deepseek-v4-flash`, and accepts only the canonical official `https://api.deepseek.com` origin (optionally normalize one trailing slash before exact comparison).
    - Missing/empty keys, unknown provider names, HTTP, userinfo, ports, subdomains, IP literals, query/fragment components, beta paths, and nonofficial hosts fail closed with `stage_permanent_failure` without echoing the rejected value.
    - DeepSeek Chat Completions requests use system and user messages, `response_format={"type":"json_object"}`, bounded `max_tokens`, `stream=False`, explicit non-thinking mode, no tools/tool choice, and an SDK client configured with `max_retries=0`.
    - Response decoding accepts exactly one nonempty assistant content value with a terminal stop finish reason and validates it strictly against the caller-supplied Pydantic model; length/empty/multiple-choice/invalid/extra-field results never cross the schema boundary.
  </behavior>
  <action>Create an immutable, narrowly typed provider settings/transport module with a closed provider literal such as `openai | deepseek`; keep provider selection explicit through a dedicated nonsecret environment variable such as `SKILLSCOUT_LLM_PROVIDER`, defaulting to `openai` for backward compatibility. Separate nonsecret provider/model resolution from secret lookup so publication projection can reconstruct the Phase 3 runtime profile without requiring an API key. Resolve keys once at client construction, never retain a raw environment mapping, and never include key/base URL/rejected configuration in exceptions, reprs, telemetry, prompts, persisted evidence, or logs. For DeepSeek, construct the already-locked `openai.OpenAI` SDK with the exact guarded base URL and `max_retries=0`; do not add packages or modify the lock. Build Chat Completions JSON mode around the same developer/system instructions and user payload used by each current adapter, including an explicit JSON requirement and the target schema in trusted instructions, but never promote repository text out of the user role. Omit tools entirely, disable thinking explicitly, and locally strict-validate returned content. Map provider HTTP/timeout/connection failures and invalid provider telemetry into the existing closed transient/permanent semantics; do not expose raw provider messages. Keep the helper generic only across the three known schema-bearing stages rather than creating a general arbitrary prompt or model gateway.</action>
  <verify>
    <automated>.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py</automated>
  </verify>
  <done>The provider resolver is fail-closed and secret-free, the DeepSeek request helper reaches only the official Chat Completions origin with one no-tools/no-retry JSON request, and only strict schema-valid content is returned to callers.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire DeepSeek through extraction, generation, review, and runtime identity</name>
  <files>src/skillscout/adapters/openai_extract.py, src/skillscout/adapters/openai_generate.py, src/skillscout/adapters/openai_review.py, src/skillscout/application/phase3.py, src/skillscout/bootstrap.py, src/skillscout/cli.py, tests/test_semantic_provider.py, tests/test_openai_extract.py, tests/test_openai_generate.py, tests/test_openai_review.py</files>
  <behavior>
    - Existing OpenAI tests continue to observe exactly one `/v1/responses` request with `store=false`, strict Pydantic schema format, no tools, unchanged prompts, bounded output, and unchanged closed outcomes/telemetry.
    - Explicit DeepSeek selection makes each stage issue exactly one `/chat/completions` request for `deepseek-v4-flash`, locally strict-validates the stage-specific model, and maps request ID/model/token usage into the existing result type.
    - DeepSeek keys appear only in the Authorization header and neither key nor configured base URL enters request content, CLI stdout/stderr, SQLite/manifests, generated artifacts, prompts, or result reprs.
    - Phase 3 candidate authority and later publication projection derive the same selected configured generator/reviewer model IDs without requiring the semantic-provider key during read-only projection.
  </behavior>
  <action>Refactor each existing `OpenAI*Client` behind the closed provider settings/helper while retaining the public class APIs and existing OpenAI Responses branch. Do not emulate Responses support against DeepSeek. The DeepSeek branch must preserve each stage's exact trusted instructions and user-message boundary, produce the existing `ExtractionResult`, `GenerationResult`, or `ReviewResult`, and handle incomplete/invalid content through the existing status vocabulary; provider retry remains zero and pipeline retry ownership remains unchanged. Update the CLI composition root to resolve provider selection once per command and pass one coherent provider/model choice to extraction or to both Phase 3 semantic clients. Construct `PhaseThreeRuntimeProfile` with the selected nonsecret model IDs so execution authority, resumability, provenance, attestation, and publication lookup bind to `deepseek-v4-flash` when selected; update the bootstrap publication projection to derive the identical nonsecret profile without looking up or requiring either API key. Do not store the provider base URL, provider key, or environment variable values in profile/evidence schemas. Extend the existing recorded-transport tests rather than using live network: add DeepSeek success, invalid schema, empty/truncated response, 429/5xx/400, one-request, telemetry, prompt-injection, and secret-canary cases for all three stages; retain the exact OpenAI request-shape assertions as regressions. Put provider-selection, coherent profile identity, missing-secret fail-closed, and provider-secret/base-URL non-disclosure assertions in `tests/test_semantic_provider.py` and the three existing adapter test modules; do not modify `tests/test_cli_security.py`. Preserve all unrelated working-tree changes.</action>
  <verify>
    <automated>.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_phase3_bootstrap.py tests/test_phase3_pipeline.py</automated>
  </verify>
  <done>All three stages run through either unchanged OpenAI Responses or guarded DeepSeek Chat Completions, runtime identity stays coherent across build and publication projection, strict schemas and injection boundaries hold, and mock-backed regressions prove no secret leakage or hidden retry.</done>
</task>

<task type="auto">
  <name>Task 3: Prove PEM usability, harden permissions, and move it to macOS Trash</name>
  <files>.gitignore, skillscout-catalog-test.2026-07-24.private-key.pem, .planning/quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/260727-mfm-PEM-AUTH-EVIDENCE.json</files>
  <action>Execute this task as three fail-closed boundaries, completing and verifying each boundary before entering the next.

Boundary A — ignore and identity hardening: add narrow repository ignore rules covering local PEM/private-key files while preserving the existing `.env` rule and all unrelated entries. Prove the exact root `skillscout-catalog-test.2026-07-24.private-key.pem` is untracked and ignored. Use `lstat`/descriptor metadata without displaying bytes to require one regular non-symlink file owned by the current user; capture its device/inode/owner identity, open it with no-follow semantics, require descriptor metadata to match, change the descriptor mode from the observed 0644 to exactly 0600, then revalidate the same device/inode/owner and exact 0600 mode through both descriptor and pathname before continuing. If any identity, type, ownership, or mode check fails, stop with the PEM retained at its current path; never replace it through a pathname-following chmod.

Boundary B — fresh read-only GitHub authentication proof: use the project-setup constants `EXPECTED_GITHUB_APP_ID = 4382801` and `EXPECTED_GITHUB_INSTALLATION_ID = 149272172`; these are non-secret identifiers. Define each literal exactly once inside one bounded verification routine and use those same resolved integer values to construct the JWT issuer, construct the exact installation URL, validate both GitHub response identities, and populate the receipt. The routine's only secret input is the already-open no-follow PEM descriptor from Boundary A; the exact source basename and the two literal expected IDs are fixed plan inputs, not environment variables or command-line arguments. Run non-verbosely with stdout/stderr suppressed except for one fixed success/failure code, so neither IDs nor any credential material are echoed.

Capture strict RFC3339 UTC `execution_started_at_utc` immediately before signing and `execution_finished_at_utc` immediately after the second validated response; require a nonnegative window no longer than 120 seconds. Perform one bounded JWT authentication confirmation using the now-0600 exact descriptor. Keep private bytes and the short-lived JWT in process memory only, disable tracing/verbose HTTP, never pass them in argv, and issue exactly `GET https://api.github.com/app` and `GET https://api.github.com/app/installations/149272172`, with bounded response bodies, explicit timeouts, and a fixed GitHub API version. Require exact HTTP 200 for both endpoints, require `/app` to return integer App ID `4382801`, and require the installation response to return integer installation ID `149272172` associated with that authenticated App. Do not mint an installation token and do not call any write endpoint. Collapse every failure to a fixed secret-free message.

Derive only the public SPKI SHA-256 fingerprint, then atomically write `.planning/quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/260727-mfm-PEM-AUTH-EVIDENCE.json` with exactly these top-level fields: `schema_version`, `execution_started_at_utc`, `confirmed_at_utc`, `execution_finished_at_utc`, `endpoints`, `app_id`, `installation_id`, `pem_basename`, `public_key_spki_sha256`, and `result`. `confirmed_at_utc` must be strict RFC3339 UTC and fall inclusively inside the recorded execution window. `endpoints` must contain exactly `app` and `installation`; each nested object must contain exactly `method`, `url`, and `status`, with method `GET`, the two exact URLs above, and integer status 200. Require exact IDs `4382801` and `149272172`, exact basename, schema `github-app-pem-auth-evidence-v1`, result `succeeded`, and a 64-character lowercase hexadecimal SPKI digest. Reject bool-as-int, unexpected top-level/nested fields, unexpected nested values, naive/non-UTC timestamps, inverted/overlong/future windows, and any credential/header/body field. If authentication, identity matching, timestamp/window validation, or durable receipt validation fails, abort before the move and leave the 0600 PEM in place.

Boundary C — exclusive Trash move and postconditions: recapture pathname metadata and require the same device/inode/owner identity and exact 0600 mode recorded after Boundary A. Require `/Users/alexzhu/.Trash` to be the current user's non-symlink directory and require `/Users/alexzhu/.Trash/skillscout-catalog-test.2026-07-24.private-key.pem` not to exist. Move only the exact source with no-overwrite semantics; do not use recursive deletion, empty Trash, touch another key-like file, or fall back to an unlink. After the move, require the repository source to be absent and the exact destination to be a regular non-symlink file owned by the current user with mode 0600 (and the same device/inode where the filesystem preserves rename identity). Confirm scoped Git status for `.gitignore` plus the former PEM path shows only the intended `.gitignore` modification, and independently confirm the acknowledged pre-existing `.planning/STATE.md` modification is still present and unchanged; do not claim the entire worktree is clean.</action>
  <verify>
    <automated>git check-ignore -q --no-index skillscout-catalog-test.2026-07-24.private-key.pem &amp;&amp; ! git ls-files --error-unmatch -- skillscout-catalog-test.2026-07-24.private-key.pem &amp;&amp; .tools/uv-0.11.29/bin/uv run --locked python -c 'import datetime,json,pathlib,re; p=pathlib.Path(".planning/quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/260727-mfm-PEM-AUTH-EVIDENCE.json"); d=json.loads(p.read_text()); assert set(d)=={"schema_version","execution_started_at_utc","confirmed_at_utc","execution_finished_at_utc","endpoints","app_id","installation_id","pem_basename","public_key_spki_sha256","result"}; assert d["schema_version"]=="github-app-pem-auth-evidence-v1" and d["result"]=="succeeded"; assert type(d["app_id"]) is int and d["app_id"]==4382801 and type(d["installation_id"]) is int and d["installation_id"]==149272172; assert d["pem_basename"]=="skillscout-catalog-test.2026-07-24.private-key.pem"; assert re.fullmatch(r"[0-9a-f]{64}",d["public_key_spki_sha256"]); e=d["endpoints"]; assert type(e) is dict and set(e)=={"app","installation"}; assert all(type(e[k]) is dict and set(e[k])=={"method","url","status"} for k in e); assert e["app"]=={"method":"GET","url":"https://api.github.com/app","status":200}; assert e["installation"]=={"method":"GET","url":"https://api.github.com/app/installations/149272172","status":200}; parse=lambda s: datetime.datetime.strptime(s,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc); a,c,z=map(parse,(d["execution_started_at_utc"],d["confirmed_at_utc"],d["execution_finished_at_utc"])); assert a&lt;=c&lt;=z and datetime.timedelta(0)&lt;=z-a&lt;=datetime.timedelta(seconds=120); assert z&lt;=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=1)' &amp;&amp; test ! -e skillscout-catalog-test.2026-07-24.private-key.pem &amp;&amp; test -f /Users/alexzhu/.Trash/skillscout-catalog-test.2026-07-24.private-key.pem &amp;&amp; test ! -L /Users/alexzhu/.Trash/skillscout-catalog-test.2026-07-24.private-key.pem &amp;&amp; test "$(stat -f '%u:%Lp' /Users/alexzhu/.Trash/skillscout-catalog-test.2026-07-24.private-key.pem)" = "$(id -u):600" &amp;&amp; test "$(git status --short -- .gitignore skillscout-catalog-test.2026-07-24.private-key.pem)" = " M .gitignore" &amp;&amp; test "$(git status --short -- .planning/STATE.md)" = " M .planning/STATE.md"</automated>
  </verify>
  <done>The key pattern was ignored first; the exact PEM retained its identity while changing from 0644 to 0600; a closed non-secret receipt proves fresh read-only App/installation authentication; the exact 0600 user-owned PEM is recoverable in macOS Trash; scoped status contains only the `.gitignore` change and the acknowledged `.planning/STATE.md` edit remains untouched.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Environment to provider composition | Provider selector, base URL, and credentials are local untrusted configuration; only a closed provider and official endpoint may construct a client. |
| Repository content to semantic provider | Candidate text is untrusted inert user-message data and must never become trusted instructions, tools, or execution authority. |
| Provider response to SkillScout contracts | Remote JSON and telemetry are untrusted until bounded, shape-checked, and strictly validated into existing Pydantic contracts. |
| Repository to GitHub read-only authentication and macOS Trash | The exact untracked PEM may authenticate only through an in-memory bounded JWT check and may leave the workspace only after ignore, identity-preserving 0600 hardening, durable non-secret evidence, and collision guards pass. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260727-mfm-01 | Spoofing | DeepSeek base URL selection | high | mitigate | Accept only the canonical official HTTPS origin and reject alternate schemes, hosts, ports, credentials, paths, query, and fragment before client construction. |
| T-260727-mfm-02 | Tampering | Chat Completions response content | high | mitigate | Require one terminal nonempty JSON response and strict stage-specific Pydantic validation before building any existing result contract. |
| T-260727-mfm-03 | Information Disclosure | API keys, endpoint configuration, PEM, JWT, and GitHub responses | critical | mitigate | Resolve provider keys once; keep all keys/JWTs/headers/bodies out of prompts/results/errors/evidence; use the PEM only through a 0600 descriptor for bounded authentication; persist only a closed non-secret receipt. |
| T-260727-mfm-04 | Denial of Service | Provider retries and unbounded output | high | mitigate | Keep SDK retries at zero, one call per attempt, existing pipeline-owned retry ceilings, bounded request/output sizes, and terminal handling for truncation/empty content. |
| T-260727-mfm-05 | Elevation of Privilege | Prompt injection or tool activation | critical | mitigate | Preserve trusted-instruction/user-data role separation, omit tools from both provider requests, disable DeepSeek thinking explicitly, and never execute source content. |
| T-260727-mfm-06 | Repudiation | Provider/model identity across Phase 3 resume and publication | high | mitigate | Bind the selected nonsecret configured model ID into the existing runtime profile/authority chain and reconstruct the same profile during publication lookup. |
| T-260727-mfm-07 | Tampering | PEM identity, mode, authentication receipt, and removal target | high | mitigate | Bind device/inode/owner across descriptor chmod and pre-move revalidation, require exact 0600 mode and validated read-only receipt, then no-overwrite move to the exact Trash path and verify destination owner/mode. |
</threat_model>

<source_audit>

| SOURCE | ID | Feature/Requirement | Plan | Status | Notes |
|--------|----|---------------------|------|--------|-------|
| GOAL | — | Safe DeepSeek V4 Flash provider path with existing OpenAI contracts preserved | 01 | COVERED | Tasks 1-2 |
| REQ | — | No roadmap requirement IDs are assigned to this quick task | 01 | COVERED | Quick-task description is the scoped requirement source |
| RESEARCH | — | Official base URL, `deepseek-v4-flash`, Chat Completions, and JSON Output semantics | 01 | COVERED | Tasks 1-2; no Responses support is assumed |
| CONTEXT | — | No tools/source execution, zero SDK retries, strict Pydantic boundary, secret non-disclosure | 01 | COVERED | Tasks 1-2 and threat model |
| CONTEXT | — | Establish durable non-secret PEM usability evidence, harden observed 0644 to 0600 without identity substitution, then ignore and move the exact local PEM to Trash | 01 | COVERED | Task 3; fresh bounded read-only authentication, receipt validation, and three fail-closed boundaries |
</source_audit>

<verification>
Run `.tools/uv-0.11.29/bin/uv run --locked pytest -q` with provider transports mocked and without enabling shell tracing. Confirm the OpenAI request-shape tests remain unchanged, every DeepSeek test reaches only `/chat/completions`, all key/base URL canaries are absent from stdout, stderr, test artifacts, SQLite/manifests, and prompts, and `git diff --check` passes. Separately validate the closed PEM authentication receipt, the Trash destination owner/mode, and scoped Git status; retain the user's pre-existing `.planning/STATE.md` modification untouched, do not show the PEM source path after the move, and show no `.env` entry.
</verification>

<success_criteria>
- The full locked pytest suite passes with no live provider call.
- Default configuration continues to use OpenAI Responses with its exact store-false, strict-schema, no-tools, one-request contract.
- Explicit DeepSeek configuration uses only `DEEPSEEK_API_KEY`, exact official `DEEPSEEK_BASE_URL`, model `deepseek-v4-flash`, and Chat Completions JSON mode followed by strict local schema validation.
- Extraction, generation, and review preserve their existing result/status/error/telemetry contracts and untrusted-input separation.
- Neither API key, the configured endpoint, `.env`, nor PEM content appears in prompts, logs, CLI output, durable state, generated artifacts, tests, or Git.
- The exact GitHub App PEM is ignored, identity-preservingly hardened from 0644 to 0600, freshly authenticated through read-only App/installation endpoints, represented by a validated non-secret receipt, and recoverably located in macOS Trash as a user-owned 0600 regular file, with no other key-like file touched.
</success_criteria>

<output>
Create `.planning/quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/260727-mfm-SUMMARY.md` after execution.
</output>
