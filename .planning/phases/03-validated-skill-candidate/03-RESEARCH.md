# Phase 03: Validated Skill Candidate - Research

**Researched:** 2026-07-22
**Domain:** Deterministic workflow qualification, documentation-only Agent Skill generation, artifact validation, and independent LLM review
**Confidence:** MEDIUM

## User Constraints

- No `CONTEXT.md` exists. Planning is intentionally based on the roadmap, requirements, Phase 2 verified contracts, project constraints, and current technical research. [VERIFIED: `init.phase-op 3` and phase directory inspection]
- Phase 3 must satisfy `QUAL-01`, `QUAL-02`, `GEN-01` through `GEN-05`, `VAL-01` through `VAL-03`, and `REV-01` through `REV-03`. [VERIFIED: `.planning/REQUIREMENTS.md`]
- The output is a local, documentation-only, source-traceable Agent Skill candidate. It may contain `SKILL.md` and, only when necessary, one-level `references/` or text-only `assets/`; it must never contain `scripts/`, binary files, or executable file modes. [VERIFIED: `.planning/ROADMAP.md` Phase 3 success criteria]
- Qualification is deterministic, versioned, passes at 75/100 by default, and is blocked by any hard failure. [VERIFIED: QUAL-01 and QUAL-02]
- `WorkflowSpec` is the only semantic boundary from source repository content into qualification, generation, validation, review, and publishing. Complete README, documentation, or source bytes must not re-enter Phase 3. [VERIFIED: EXTR-04 and Phase 2 verification]
- Generator and Reviewer calls are tool-less, `store=false`, bounded, independently prompted, and receive no credentials. The Reviewer receives only the `WorkflowSpec`, generated artifact, provenance, and Validation Report; it judges but cannot return replacement files. [VERIFIED: REV-01, REV-02, SEC-01, and AGENTS.md]
- Phase 3 preserves the Phase 2 authority ceiling: local state plus remote reads only. It introduces no branch, PR, merge, approval, release, package-install-at-runtime, or other remote-write capability. [VERIFIED: AGENTS.md, Phase 2 verification, and Phase 4 scope]
- Identical input and version identities must reuse a verified artifact; validator errors, Reviewer `NO`, or Reviewer confidence below `0.80` are auditable business rejections and cannot create a publication plan. [VERIFIED: Phase 3 success criterion 6 and REV-03]
- Deferred and out of scope: generated executable scripts, candidate-code execution, Draft PR publication, automatic revision loops, public marketplace publication, private repositories, and automatic merge/approval. [VERIFIED: `.planning/REQUIREMENTS.md` Out of Scope and v2 requirements]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUAL-01 | Versioned deterministic qualification of specificity, reusability, verifiability, evidence, and unauthorized execution | Closed scoring rubric, hard-fail rules, and typed Qualification Report below |
| QUAL-02 | Default pass at 75/100 with itemized checks and rejection reasons | Exact 100-point recommendation and `qualified = score >= 75 and not hard_fail` |
| GEN-01 | Generate an Agent Skills directory from a qualified `WorkflowSpec` | Structured semantic draft plus deterministic renderer/materializer |
| GEN-02 | Documentation-only; no scripts, binaries, or executable bits | Closed path/type/mode allowlist and validator checks |
| GEN-03 | Generalized rewrite; bounded, attributed excerpts only | Quote registry and deterministic over-copy policy |
| GEN-04 | Machine-readable complete provenance | `references/provenance.json` contract and package manifest |
| GEN-05 | Stable slug and versioned workflow fingerprint; update rather than duplicate | Separate lineage key, content artifact ID, package digest, and exact-run reuse |
| VAL-01 | Official Agent Skills validation plus format/reference/progressive-disclosure checks | Pinned `skills-ref` adapter plus SkillScout structural checks |
| VAL-02 | Secret, dangerous action, tool, download/execute, injection, URL, provenance, scripts, and over-copy checks | Versioned deterministic validation policy and adversarial fixtures |
| VAL-03 | Structured `error/warning/info`; every error blocks | Closed finding model, fail-closed validator runtime mapping, and gate matrix |
| REV-01 | Independent fresh LLM context with only four allowed inputs | Separate `OpenAIReviewClient` and serialized review envelope |
| REV-02 | Strict YES/NO judgment; no edits | Pydantic schema with no file/body replacement fields |
| REV-03 | Error-free validation + YES + confidence ≥0.80 | Deterministic publication-eligibility predicate |

</phase_requirements>

## Summary

Phase 3 should be implemented as an additive `phase3-v1` full pipeline profile through `REVIEWER`, using a new `PhaseThreeProcessor` that composes the verified Phase 2 processor for Scout through Extractor and owns four new downstream handlers. Do not change `phase2-v1`, its terminal state, or its seven-registration composition root. This preserves the current prefix-indexed ledger verifier and makes Phase 3 resume/idempotency work through the same content-addressed checkpoint chain. [VERIFIED: codebase inspection of `PIPELINE_PROFILES`, `verify_run_chain`, `PhaseTwoProcessor`, and `build_phase_two_runtime`]

Qualification and all artifact safety decisions must be deterministic. Use the LLM only to transform one qualified `WorkflowSpec` into a bounded semantic draft and to independently judge the rendered result. SkillScout, not either model, owns the slug, lineage key, filenames, frontmatter, provenance, file modes, package digest, validation findings, and final eligibility gate. [VERIFIED: project deterministic-first constraint; ASSUMED for the proposed ownership split]

Run the official `skills-ref` validator, but do not mistake it for the complete Phase 3 validator. The current official repository marks the reference library as demonstration-only, and its `validate(Path)` implementation checks `SKILL.md` frontmatter and naming conventions; it does not validate links, progressive disclosure, provenance, executable bits, secrets, dangerous commands, or copied-source limits. [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref] [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py]

**Primary recommendation:** add a closed `phase3-v1` local-candidate pipeline with deterministic qualification/rendering/validation, one isolated generator call and one isolated reviewer call per selected workflow, exact artifact reuse, and a final typed gate that is publishable only when qualification passed, validation has zero errors, Reviewer says `YES`, and Reviewer confidence is at least `0.80`. [ASSUMED]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Qualification scoring and hard fails | API / Backend domain | — | Pure deterministic policy over a validated `WorkflowSpec` and upstream facts; no filesystem or model needed. [VERIFIED: QUAL-01] |
| Semantic Skill drafting | API / Backend adapter | OpenAI Responses API | Model performs bounded rephrasing only; it does not choose identity, paths, modes, or gates. [ASSUMED] |
| Frontmatter, provenance, and package rendering | API / Backend domain | Local Storage | Deterministic rendering owns exact bytes; an anchored writer materializes only declared regular files. [ASSUMED] |
| Official and custom validation | API / Backend domain | Local Storage | Validators inspect a bounded local artifact and return data; they never execute artifact content. [VERIFIED: VAL-01 and VAL-02] |
| Independent review | API / Backend adapter | OpenAI Responses API | A fresh tool-less call judges the four allowed inputs and returns a closed decision schema. [VERIFIED: REV-01 and REV-02] |
| Artifact/checkpoint/reuse authority | Database / Storage | API / Backend | Existing SQLite plus canonical manifests verify every prefix before resume or completed-run reuse. [VERIFIED: Phase 2 verification] |
| Publication eligibility | API / Backend domain | — | A pure predicate combines qualification, validation, and review; Phase 3 has no publisher capability. [VERIFIED: REV-03 and Phase 4 boundary] |

## Project Constraints (from AGENTS.md)

- Treat every external byte as untrusted data, never as system instructions, tool calls, or execution permission. [VERIFIED: AGENTS.md]
- Never clone-and-run, install source-repository dependencies, invoke source scripts, build, import, or execute candidate code. [VERIFIED: AGENTS.md]
- End automation at a Draft PR in the overall system; Phase 3 is earlier and must remain local-only. Never merge, approve, or publish automatically. [VERIFIED: AGENTS.md]
- Process only an explicitly recognized permissive repository license and retain license and attribution in every downstream artifact. [VERIFIED: AGENTS.md]
- Inject GitHub/OpenAI credentials from the environment with minimum permissions; never write them to logs, SQLite, prompts, provenance, artifacts, or PRs. [VERIFIED: AGENTS.md]
- Deterministic logic owns filtering, limits, format/security checks, idempotency, and permission gates; LLMs own semantic work only. [VERIFIED: AGENTS.md]
- Every stage uses explicit versioned schemas and can retry independently without implicit shared state. [VERIFIED: AGENTS.md]
- Candidate and LLM call counts have hard ceilings. [VERIFIED: AGENTS.md]
- MVP supports public GitHub repositories and one central Agent Skills catalog only; do not generalize to providers or tenants. [VERIFIED: AGENTS.md]
- Use Python 3.13, `pyproject.toml` plus an exact lock, OpenAI Responses API, Pydantic, SQLite, and pytest. [VERIFIED: AGENTS.md]
- Do not introduce a multi-agent framework, event bus, PostgreSQL, vector database, full clone/index, generated scripts, PAT, or free-text LLM parsing. [VERIFIED: AGENTS.md]
- Project skill discovery found no `.codex/skills/` or `.agents/skills/` `SKILL.md` files, so there are no additional project-skill rules. [VERIFIED: filesystem inspection]

## Standard Stack

### Core

| Library | Version / publish date | Purpose | Why Standard |
|---------|------------------------|---------|--------------|
| Python | 3.13.14 available locally | Runtime and safe filesystem primitives | Locked project runtime; use existing descriptor-anchored and canonical JSON patterns. [VERIFIED: local environment and AGENTS.md] |
| Pydantic | 2.13.4, published 2026-05-06 | Qualification, generation, provenance, validation, and review contracts | Already pinned and used for strict frozen models and Structured Outputs. [VERIFIED: `pyproject.toml`, `uv.lock`, and https://pypi.org/pypi/pydantic/2.13.4/json] |
| OpenAI Python SDK | 2.46.0, published 2026-07-17 | Separate generator and reviewer Responses calls | Already pinned; the verified Extractor adapter supplies the exact request/error/telemetry pattern. [VERIFIED: `pyproject.toml`, Phase 2 verification, and https://pypi.org/pypi/openai/2.46.0/json] |
| `skills-ref` [WARNING: flagged as suspicious — verify before using.] | 0.1.1, published 2026-01-10 | Official reference validation signal | The Agent Skills specification directs users to `skills-ref`; use the Python `validate(Path)` API, not parsed CLI text. The package-legitimacy seam returned `SUS`, so installation requires a human checkpoint and fresh lock approval. [CITED: https://agentskills.io/specification] [CITED: https://pypi.org/project/skills-ref/] |
| Python standard library | 3.13 | Canonical JSON, SHA-256, regex, Unicode normalization, `stat`, descriptor I/O | Enough for deterministic rendering, manifests, content comparison, and safe local materialization; avoid another parser/scanner dependency. [ASSUMED] |

### Supporting

| Library | Version / publish date | Purpose | When to Use |
|---------|------------------------|---------|-------------|
| pytest | 9.1.1, published 2026-06-19 | Contract, policy, adversarial, recorded-response, resume, and CLI tests | Reuse the existing suite and `httpx.MockTransport` fixture style. [VERIFIED: `pyproject.toml`, tests, and https://pypi.org/pypi/pytest/9.1.1/json] |
| HTTPX | 0.28.1, published 2024-12-06 | Recorded OpenAI transport injection through the existing SDK | No new direct Phase 3 HTTP client; retain existing confinement. [VERIFIED: `pyproject.toml`, Phase 2 verification, and https://pypi.org/pypi/httpx/0.28.1/json] |
| StrictYAML / Click | Versions resolved and hash-pinned by the approved lock | Transitive dependencies of `skills-ref` | Do not import them in SkillScout code. Treat both as new supply-chain nodes reviewed with the `skills-ref` lock change. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/pyproject.toml] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-process `skills_ref.validate(Path)` | `skills-ref validate` subprocess | CLI proves the published executable, but subprocess adds process authority, output parsing, absolute-path leakage risk, and a command-name discrepancy between official repo and PyPI 0.1.1 docs. Use the Python API and add a single smoke test for the installed console entry point only if human supply-chain review requires it. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/cli.py] [CITED: https://pypi.org/project/skills-ref/] |
| Deterministic renderer | Model-generated arbitrary file map | Arbitrary paths/frontmatter/modes turn model output into authority. A structured semantic draft keeps filesystem and identity decisions in trusted code. [ASSUMED] |
| Closed regex/policy checks over bounded structured text | A new broad secret or Markdown-analysis package | Another package expands the approved dependency graph. The controlled renderer can reject arbitrary links/HTML and compare exact declared references without a general Markdown parser. [ASSUMED] |
| Full-prefix `phase3-v1` profile | Importing a completed Phase 2 suffix into a new run | Current ledger verification requires stages to start at Scout with their enum index. Cross-producer checkpoint import would require a new trust/migration design; a new full-prefix profile preserves existing authority. [VERIFIED: codebase inspection of `verify_run_chain`] |

**Installation (do not run before the human dependency gate):**

```bash
# Gate A: review exact direct/transitive nodes and official source provenance.
# Gate B: approve the resulting uv.lock bytes and new SHA-256 authority.
./.tools/uv-0.11.29/bin/uv add 'skills-ref==0.1.1'
./.tools/uv-0.11.29/bin/uv lock --check
```

The system Python is 3.9.6, so `pip index versions skills-ref` reported no compatible distribution; the project-managed Python is 3.13.14 and meets the package's `>=3.11` requirement. Use only the project-managed toolchain. [VERIFIED: local environment probe and https://pypi.org/project/skills-ref/]

At the dependency checkpoint, verify that the selected PyPI 0.1.1 wheel still has SHA-256 `d35db5bb8de71ae301daf5ca9cb71f8a555e8c6f83a6d40e46a5bc09f8f461b5`, then retain the exact resolved distribution hashes in `uv.lock`. PyPI reports that this release was not uploaded through Trusted Publishing, which is an additional review signal rather than an automatic rejection. [VERIFIED: https://pypi.org/pypi/skills-ref/0.1.1/json]

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `skills-ref` | PyPI | ~6 months; 0.1.1 uploaded 2026-01-10 | Registry API does not expose a useful count | `github.com/agentskills/agentskills`; PyPI metadata still names the older `anthropics/agentskills` URL | SUS | Flagged — planner must add `checkpoint:human-verify` before dependency/lock modification. [CITED: https://pypi.org/pypi/skills-ref/json] |
| `click` | PyPI | Established but not independently age-resolved by the seam | Unknown to seam | Pallets project | SUS | Transitive; approve exact resolved version and hashes at the same checkpoint. [VERIFIED: package-legitimacy seam] |
| `strictyaml` | PyPI | Established but not independently age-resolved by the seam | Unknown to seam | Resolve from package metadata during Gate A | SUS | Transitive; approve exact resolved version and hashes at the same checkpoint. [VERIFIED: package-legitimacy seam] |

**Packages removed due to SLOP verdict:** none. [VERIFIED: package-legitimacy seam]

**Packages flagged as suspicious [SUS]:** `skills-ref`, `click`, `strictyaml`. The seam could not resolve registry age/download/repository signals, and the official repository calls `skills-ref` demonstration-only. The planner must require human verification before any install or lock change. [VERIFIED: package-legitimacy seam] [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref]

## Architecture Patterns

### System Architecture Diagram

```text
RepositorySubject
      |
      v
Existing Phase 2 prefix (Scout -> Filter -> Reader -> Extractor)
      | accepted, 1-3 validated WorkflowSpecs
      v
Qualifier (pure, versioned 100-point policy)
      |                         |
      | qualified               +--> rejected_qualification -> audit summary
      v
Generator adapter (fresh tool-less Responses call, one selected workflow)
      | structured semantic draft / refusal / incomplete / schema failure
      v
Deterministic renderer + anchored content-addressed materializer
      | SKILL.md + optional one-level text resources + provenance.json
      v
Validators
  preflight regular-file/path/size/mode checks
      -> official skills_ref.validate(Path)
      -> custom structure/source/security/over-copy checks
      |                         |
      | zero errors             +--> validation_rejected -> Reviewer not called
      v
Independent Reviewer (fresh tool-less Responses call; four allowed inputs)
      | YES >= 0.80             | NO / low confidence / refusal / invalid
      v                         v
eligible local candidate      review_rejected
      |
      v
ValidatedCandidateSummary + exact package manifest

No Phase 3 edge reaches a Publisher or REMOTE_WRITE adapter.
```

This keeps entry, branching, processing, external service boundaries, and terminal rejection states explicit. [ASSUMED]

### Recommended Project Structure

```text
src/skillscout/
├── domain/
│   ├── qualification.py       # policy, rule decisions, scoring report
│   ├── skill_artifacts.py     # draft, provenance, manifest, identity, renderer
│   ├── validation.py          # finding schema and deterministic checks
│   └── review.py              # Reviewer response/decision contracts and gate
├── adapters/
│   ├── openai_generate.py     # one bounded structured generation call
│   ├── openai_review.py       # separate one-call independent reviewer
│   └── skills_ref.py          # narrow wrapper over skills_ref.validate(Path)
├── application/
│   ├── processors.py          # preserve PhaseTwoProcessor behavior
│   └── phase3.py              # PhaseThreeProcessor/composition helpers if size warrants
└── cli.py                     # additive local candidate command

tests/
├── fixtures/openai/generator/
├── fixtures/openai/reviewer/
├── fixtures/skills/
├── test_qualification.py
├── test_skill_generation.py
├── test_skill_validation.py
├── test_openai_generate.py
├── test_openai_review.py
├── test_phase3_pipeline.py
└── test_cli_validate_skill.py
```

Keep the existing Phase 2 modules and public behavior unchanged. Compose rather than subclass `PhaseTwoProcessor`, because production roots already use exact concrete-type admission. [VERIFIED: codebase inspection of `build_phase_two_runtime`]

### Pattern 1: Closed Qualification Policy

**What:** Re-parse every workflow payload as `WorkflowSpec`, recompute/bind upstream facts, run hard failures first, then emit one ordered list of itemized score decisions. Never let the LLM assign or revise a score. [VERIFIED: QUAL-01 and deterministic-first constraint]

**Recommended v1 rubric (policy version `qualification-policy-v1`):** [ASSUMED]

| Dimension | Points | Deterministic observations |
|-----------|-------:|----------------------------|
| Specificity | 25 | Goal present (5), at least 3 ordered steps (10), non-empty inputs (5), non-empty outputs (5) |
| Reusability | 20 | Applicability (5), preconditions (5), non-goals (5), no exact source owner/repo/evidence-path dependency in goal or steps (5) |
| Verifiability | 20 | Failure modes (5), every step evidence-bound (5), workflow-level evidence (5), every referenced content/blob hash has an upstream match (5) |
| Evidence sufficiency | 25 | At least one distinct evidence path (5), 100% step coverage (10), bounded non-empty support statements (5), exact commit/repository/license facts available for provenance (5) |
| Safety readiness | 10 | Prohibited actions present (5), and side-effect-shaped steps have a named approval or explicitly safe no-side-effect classification (5) |

**Hard failures:** invalid `WorkflowSpec`; fingerprint or repo binding mismatch; extraction confidence `<0.70`; fewer than 3 steps; empty inputs or outputs; missing/unknown/hash-mismatched evidence; source-repository execution/install/build/import dependence; credential access; destructive/download-and-execute/permission-bypass patterns; prompt-injection residue; or an approval-requiring side effect with no named approval. [ASSUMED]

**Pass predicate:** `score >= 75 and hard_failures == ()`. Keep score, pass boolean, policy version, every check's observed value/result/points/rationale, and ordered rejection codes. [VERIFIED: QUAL-02]

### Pattern 2: Structured Draft, Deterministic Package

**What:** The generator returns semantic fields, not a filesystem. A trusted renderer supplies the stable slug, fixed frontmatter keys, headings, relative links, provenance location, filenames, modes, and canonical bytes. [ASSUMED]

**Recommended generator response fields:** `description`, `overview`, `when_to_use`, `inputs`, ordered `steps`, `outputs`, `failure_handling`, `approvals`, `limitations`, and up to four named Markdown reference topics. Each collection and string needs explicit Pydantic size bounds. No schema field may represent a path outside the closed reference-name pattern, executable content, frontmatter, `allowed-tools`, a script, or a binary. [ASSUMED]

**Materialized package:** [ASSUMED]

```text
<stable-slug>/
├── SKILL.md                         # mode 0644, recommended <=500 lines/<5000 tokens
└── references/
    ├── provenance.json              # canonical JSON, mode 0644
    └── <optional-topic>.md           # mode 0644, one level only
```

Do not generate `allowed-tools`: the specification labels it experimental and it represents pre-approved tool authority, which conflicts with Phase 3's documentation-only, no-preapproval boundary. [CITED: https://agentskills.io/specification] [ASSUMED]

`assets/` may be added later in the phase only for bounded UTF-8 text templates (`.md`, `.txt`, `.json`) with the same path and mode checks. There is no requirement to emit it when a workflow does not need it. [VERIFIED: GEN-01 and GEN-02; ASSUMED for the text-only extension set]

### Pattern 3: Separate Lineage, Artifact, and Package Identities

Use three different identities; combining them causes duplicates or circular hashes. [ASSUMED]

| Identity | Recommended preimage | Stability purpose |
|----------|----------------------|-------------------|
| `lineage_id` | version + repo ID + normalized workflow title + sorted evidence paths | Stable update key across commits when the source workflow remains recognizably in the same location. Collision or ambiguous remap fails closed for human resolution. [ASSUMED] |
| `artifact_id` | version + lineage ID + workflow fingerprint + generation prompt/policy + configured/actual model + canonical semantic draft hash | Identifies one generated semantic candidate. [ASSUMED] |
| `package_digest` | canonical ordered map of relative path -> SHA-256 + mode + size | Binds the exact bytes that Validators reviewed and Phase 4 may publish. [ASSUMED] |

The current `workflow_id` is derived from `wf-fingerprint-v1`, so it changes when normalized goal or ordered steps change and cannot alone be the cross-commit update key. [VERIFIED: `src/skillscout/domain/extraction.py` and `_build_workflow_spec`]

Use slug `slugify(normalized title)` plus a short repo-ID-derived suffix, not a fingerprint suffix. Store the full lineage ID and full package digest in machine-readable records; never trust the short suffix as collision authority. [ASSUMED]

### Pattern 4: Provenance Without a Self-Hash Cycle

Write canonical `references/provenance.json` with at least: [VERIFIED: GEN-04; ASSUMED for layout]

- `schema_version`, `artifact_id`, `lineage_id`, stable slug;
- repository URL, numeric repo ID, exact commit SHA, SPDX license;
- workflow ID, full fingerprint, fingerprint version;
- every evidence path, blob SHA, content hash, and bounded excerpt/quote registration;
- WorkflowSpec schema, extraction prompt, qualification policy, generation prompt, artifact schema, and validation policy versions;
- configured and actual generation model plus bounded request ID/usage telemetry where policy permits.

Do not put `package_digest` inside the file whose bytes it hashes. Compute the package digest after provenance is finalized and store it in the Generator envelope, Validation Report, terminal summary, and later publication manifest. [ASSUMED]

### Pattern 5: Layered Validation and Fail-Closed Review

Run Validators in this order: [ASSUMED]

1. Admit only a trusted, content-addressed workspace: regular files, no symlinks/hard-link surprises, exact manifest path set, per-file and package size caps, UTF-8 text, modes exactly `0644`, no `scripts/`, no binary signatures.
2. Call `skills_ref.validate(Path)` through a narrow adapter and map every returned item to a bounded `error` finding. Any exception becomes `official_validator_runtime_failure` (`error`) without raw exception/path leakage.
3. Verify SkillScout structure: exact `SKILL.md`, name-directory equality, fixed frontmatter keys, declared one-level resources, no broken/orphan/nested links, main file line/token cap, and all files present in the package manifest.
4. Verify provenance/source bindings against Scout/Filter/Reader/Extractor payloads and recompute artifact/package hashes.
5. Scan normalized structured fields and rendered bytes for secrets, injection markers, dangerous commands, download/execute chains, forbidden tools/preapproval, URLs/HTML/Markdown images, and quote/over-copy violations.
6. Emit one sorted `ValidationReport`; do not call Reviewer when `error_count > 0`.

Use `error` for gate violations, `warning` only for human-quality risks that are safe to review, and `info` for version/size/count facts. Never downgrade an official validator error. [VERIFIED: VAL-03; ASSUMED for severity policy]

### Pattern 6: Independent Reviewer as Judge Only

Create `OpenAIReviewClient` separately from both extraction and generation clients. One `review()` invocation is exactly one Responses request (`max_retries=0`); pipeline retry policy owns transient retry. Set `store=False`, bounded output tokens, and omit `tools`. [VERIFIED: Phase 2 adapter pattern and OpenAI SDK retry documentation at https://pypi.org/pypi/openai/2.46.0/json]

The user-role payload must be a canonical envelope with exactly four sections: `WorkflowSpec`, rendered artifact files, provenance, and Validation Report. Each section is data inside fresh randomized/unambiguous delimiters; the developer message contains instructions and policy only, with zero payload bytes. [VERIFIED: REV-01 and Phase 2 injection-boundary pattern]

Reviewer schema: `verdict: Literal["YES", "NO"]`, `confidence: float[0,1]`, bounded `reasons`, bounded `missing_assumptions`, and bounded `minimal_modifications`. Do not include `files`, `replacement`, `patch`, `body`, or free-form additional properties. Schema invalidity, refusal, or incomplete response is a structured non-approval, not permission to ask for a different answer. [VERIFIED: REV-02; ASSUMED for closed failure mapping]

Final predicate:

```python
eligible_for_publication = (
    qualification.passed
    and validation.error_count == 0
    and review.status == "reviewed"
    and review.verdict == "YES"
    and review.confidence >= 0.80
)
```

This predicate is deterministic and belongs outside the Reviewer adapter. [VERIFIED: REV-03]

### Anti-Patterns to Avoid

- **Extending or mutating `phase2-v1`:** changes Phase 2's verified terminal behavior and exact composition root. Add `phase3-v1`. [VERIFIED: Phase 2 verification]
- **Treating `RunStatus.COMPLETED` as approved:** completed means the pipeline reached its terminal, including clean business rejection. Phase 4 must require the exact eligible candidate report and package digest. [ASSUMED]
- **Letting the generator output filenames/frontmatter/modes:** converts model text into filesystem authority. Render from trusted structured fields. [ASSUMED]
- **Calling Reviewer after a validation error:** spends cost and risks a model appearing to override deterministic safety. Emit `review_skipped_validation_errors`. [VERIFIED: VAL-03]
- **Using `skills-ref` alone:** it does not cover most VAL-01/02 requirements and is labeled demonstration-only. [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref]
- **Parsing validator CLI prose as a contract:** use the Python list-returning API and record the installed distribution version. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py]
- **Hashing provenance with its own package digest:** creates a self-reference cycle. Keep semantic artifact ID and external package digest separate. [ASSUMED]
- **Regenerating to seek a YES:** decided refusal/schema/NO/low-confidence outcomes are auditable business results; only transient infrastructure failures consume retry authority. [VERIFIED: Phase 2 retry pattern; ASSUMED for Phase 3 outcome mapping]
- **Persisting complete upstream repository text:** Phase 3 must operate only on bounded WorkflowSpec fields and evidence excerpts. [VERIFIED: EXTR-04]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Agent Skills frontmatter conformance | A second independent YAML/spec parser | Pinned `skills_ref.validate(Path)` plus deterministic renderer | Official signal prevents drift, while trusted rendering removes ambiguous model-produced YAML. [CITED: https://agentskills.io/specification] |
| LLM output parsing | Free-text JSON extraction or regex | Pydantic strict Structured Outputs through `responses.parse` | Refusal, incomplete, and schema-invalid outcomes stay explicit and typed. [CITED: https://developers.openai.com/api/docs/guides/structured-outputs] |
| Retry/backoff | SDK internal retries or a new retry library | Existing `RetryPolicy` with SDK `max_retries=0` | Preserves one HTTP request per attempt and ledger-owned retry authority. [VERIFIED: Phase 2 verification] |
| Artifact durability | Plain `Path.write_text`, mutable temp names, or following links | Existing anchored directory, retained flock, atomic replace, and fatal fsync patterns | Phase 1 already verified crash/ownership/link boundaries. [VERIFIED: STATE decisions and codebase inspection] |
| Artifact identity | Model-provided IDs or short-slug equality | Canonical JSON plus full SHA-256 identities | Models do not own identity; short names are presentation only. [VERIFIED: Phase 2 identity pattern] |
| Complete Markdown interpretation | A broad custom Markdown parser | Closed renderer plus rejection of model-authored links/HTML; validate only renderer-declared references | Controlled output makes exact reference checks simpler and safer. [ASSUMED] |

**Key insight:** Phase 3 is safest when the LLM produces meaning, while trusted code produces bytes, identities, authority, and decisions. [ASSUMED]

## Common Pitfalls

### Pitfall 1: Official Validator Coverage Is Overstated

**What goes wrong:** A Skill passes `skills-ref` but has broken references, deep resource chains, executable modes, secrets, or dangerous instructions. [VERIFIED: official validator source inspection]

**Why it happens:** The current reference validator checks existence of `SKILL.md`, YAML frontmatter, allowed fields, name, description, compatibility, and directory-name match only. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py]

**How to avoid:** Record official results as one named check family, then run the custom structural/source/security policy. [ASSUMED]

**Warning signs:** Tests assert only that `skills_ref.validate()` returns an empty list; no adversarial package fixtures exist. [ASSUMED]

### Pitfall 2: Validator Reads Unbounded or Link-Swapped Files

**What goes wrong:** The reference validator uses ordinary path existence and `read_text()`, so calling it on an attacker-controllable directory could follow links or read unexpectedly large content. [VERIFIED: official validator source inspection]

**Why it happens:** It is a demonstration reference implementation, not SkillScout's filesystem trust boundary. [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref]

**How to avoid:** Materialize only system-owned files, preflight exact regular-file identities/sizes/modes, retain the workspace lock, then call the validator. [ASSUMED]

**Warning signs:** Validator is invoked before manifest admission or against a caller-supplied path. [ASSUMED]

### Pitfall 3: Nondeterministic Generation Is Confused With Idempotency

**What goes wrong:** Re-running the model produces different bytes and a second candidate even though the semantic input/version identity is unchanged. [ASSUMED]

**Why it happens:** Model sampling is not a stable artifact cache key. [ASSUMED]

**How to avoid:** Verify and reuse the completed `phase3-v1` chain before any GitHub/OpenAI call. Bind the artifact to the first successful canonical draft and its versions. [VERIFIED: existing completed-run reuse pattern; ASSUMED for Phase 3]

**Warning signs:** A same-identity test records any generator/reviewer request or creates a new artifact directory. [ASSUMED]

### Pitfall 4: Cross-Commit Update Identity Uses the Fingerprint

**What goes wrong:** A legitimate source update changes goal/steps, therefore changes fingerprint/workflow ID, and creates a duplicate slug. [VERIFIED: current fingerprint preimage]

**Why it happens:** Content identity and lineage identity serve different purposes. [ASSUMED]

**How to avoid:** Add an explicit lineage key independent of commit/fingerprint, keep the stable slug attached to it, and fail closed on lineage collisions. [ASSUMED]

**Warning signs:** Slug contains the workflow fingerprint prefix or update lookup keys only on `workflow_id`. [ASSUMED]

### Pitfall 5: Over-Copy Detection Pretends to Be a Legal Rule

**What goes wrong:** A numeric match threshold is described as a copyright safe harbor. No universal character count establishes that. [ASSUMED]

**Why it happens:** A technical heuristic is confused with a legal conclusion. [ASSUMED]

**How to avoid:** Make the policy intentionally conservative and versioned: generator paraphrases by default; allow only registered quotes of at most 120 characters each and 240 characters total; reject any unregistered normalized source match of 80 or more characters. Treat those thresholds as project policy requiring user confirmation, not legal advice. [ASSUMED]

**Warning signs:** Validator compares only exact raw strings, ignores Unicode/whitespace normalization, or permits unattributed quotes. [ASSUMED]

### Pitfall 6: Reviewer Can Smuggle an Edit

**What goes wrong:** A reviewer returns a replacement `SKILL.md` inside a rationale or extra JSON field, collapsing judge and generator roles. [ASSUMED]

**Why it happens:** The review schema is permissive or the application treats prose as a patch. [ASSUMED]

**How to avoid:** Extra fields forbidden, strings bounded, no replacement/file fields, and application code never writes Reviewer text into artifact files. [VERIFIED: REV-02]

**Warning signs:** Reviewer output is passed to the renderer or a `suggested_skill` field appears. [ASSUMED]

### Pitfall 7: Rejection Is Recorded as Infrastructure Failure

**What goes wrong:** Low qualification, official validation errors, Reviewer `NO`, refusal, or low confidence consume retry budget and repeatedly call the LLM. [ASSUMED]

**Why it happens:** Business outcomes raise exceptions rather than return closed payloads. [VERIFIED: Phase 2 identified and solved the same class]

**How to avoid:** Return succeeded stage attempts with closed rejection outcomes; raise only mapped transient/permanent infrastructure failures. [VERIFIED: Phase 2 pattern]

**Warning signs:** `Reviewer NO` increments `attempt_no`, or a validation error prevents the terminal summary from being written. [ASSUMED]

## Code Examples

Verified and recommended patterns:

### Typed Qualification Decision

```python
# Source pattern: existing StrictFrozenModel contracts; policy fields are Phase 3 recommendation.
class QualificationCheck(StrictFrozenModel):
    check_id: str
    dimension: Literal["specificity", "reusability", "verifiability", "evidence", "safety"]
    result: Literal["pass", "fail", "not_applicable"]
    observed: str
    points_awarded: Annotated[int, Field(ge=0)]
    points_possible: Annotated[int, Field(ge=0)]
    hard_failure: bool
    rationale_code: str


class QualificationReport(StrictFrozenModel):
    schema_version: Literal["qualification-report-v1"]
    policy_version: Literal["qualification-policy-v1"]
    workflow_fingerprint: Digest
    threshold: Literal[75]
    score: Annotated[int, Field(ge=0, le=100)]
    passed: bool
    checks: tuple[QualificationCheck, ...]
    rejection_reasons: tuple[str, ...]
```

### Official Validator Adapter

```python
# Source: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py
from importlib.metadata import version
from pathlib import Path
from skills_ref import validate


def run_official_validator(admitted_skill_dir: Path) -> tuple[str, tuple[str, ...]]:
    # admitted_skill_dir has already passed SkillScout's descriptor/path/size/mode preflight.
    validator_version = version("skills-ref")
    problems = tuple(validate(admitted_skill_dir))
    return validator_version, problems
```

The adapter must catch all exceptions at its boundary and return one sanitized error finding; it must not persist raw absolute paths or exception representations. [VERIFIED: project diagnostic discipline]

### Independent Structured Reviewer

```python
# Source pattern: src/skillscout/adapters/openai_extract.py and
# https://developers.openai.com/api/docs/guides/structured-outputs
response = client.responses.parse(
    model=configured_model,
    input=[
        {"role": "developer", "content": REVIEW_INSTRUCTIONS_V1},
        {"role": "user", "content": canonical_review_envelope},
    ],
    text_format=ReviewerResponse,
    store=False,
    max_output_tokens=MAX_REVIEW_OUTPUT_TOKENS,
)
```

Construct the SDK client with `max_retries=0`, omit `tools`, and map refusal/incomplete/schema-invalid exactly as the existing Extractor adapter does. [VERIFIED: Phase 2 adapter and OpenAI official documentation]

## Deterministic Validation Policy

### File and Structure Checks

| Check family | Error conditions | Notes |
|--------------|------------------|-------|
| Manifest admission | undeclared/missing/duplicate path; absolute path; `..`; backslash; NUL/control; symlink; non-regular file; hard-link/identity swap; mode not `0644`; total >128 KiB; file >64 KiB | Recommended caps fit the existing 262,144-byte stage manifest ceiling. [VERIFIED: existing cap; ASSUMED for package caps] |
| Closed tree | anything other than `SKILL.md`, `references/*.md|json`, optional `assets/*.md|txt|json`; any `scripts` segment; nesting deeper than one resource directory | v1 documentation-only boundary. [VERIFIED: GEN-02] |
| Frontmatter | official validator issue; unexpected field; missing `name`/`description`/`license`/SkillScout metadata pointer; `allowed-tools` present; name != directory | The base spec requires only name/description, but project policy can be stricter. [CITED: https://agentskills.io/specification] [ASSUMED] |
| Progressive disclosure | `SKILL.md` >500 lines or estimated >5000 tokens; missing/broken/unreferenced resource; nested resource reference; references that themselves link to more files | Official recommendations elevated to project errors for predictable review cost. [CITED: https://agentskills.io/specification] [ASSUMED] |

### Security and Source Checks

| Check family | Error conditions | Detection approach |
|--------------|------------------|--------------------|
| Secrets | provider token/private-key/connection-string patterns; declared canary; high-entropy candidate with secret-shaped context | Reuse and extend the closed Phase 2 pattern names; normalize first and report only pattern ID/path, never matched secret bytes. GitHub distinguishes provider and generic regex-based patterns. [VERIFIED: current extraction patterns] [CITED: https://docs.github.com/en/code-security/reference/secret-security/supported-secret-scanning-patterns] |
| Dangerous execution | download-and-pipe shell, package install, source repo script invocation, `eval`/`exec`, `sudo`, permission escalation, destructive filesystem commands, automatic merge/approve/publish | Closed, versioned pattern set over structured fields and final rendered bytes. Safe-looking code fences remain warnings for Reviewer attention. [ASSUMED] |
| Tool authority | any `allowed-tools`; instructions to bypass approval, access credentials, enable network, or use tools absent from WorkflowSpec preconditions/approvals | Models never grant authority. [VERIFIED: project execution boundary; ASSUMED for matching] |
| Injection residue | role override, ignore-prior, fake system/developer/tool markup, source delimiters, exfiltration markup, encoded control payloads, bidi/zero-width controls | Reuse all Phase 2 injection fixtures and add generator/reviewer-specific variants. OWASP recommends role/data separation, structured outputs, output validation, and least privilege. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html] |
| URLs/markup | any non-provenance external URL, Markdown image, raw HTML network element, `data:` or protocol-relative URL | Permit only the exact source repository/commit attribution fields in canonical provenance; instructions must not create network authority. [ASSUMED] |
| Provenance | missing/mismatched repo ID/URL/commit/license/fingerprint/version/evidence path/blob/content hash; unknown quote registration | Recompute from prior verified payloads, never from generator claims. [VERIFIED: GEN-04] |
| Over-copy | registered quote >120 chars; total quotes >240; unattributed normalized evidence match >=80 chars; quote not verbatim in WorkflowSpec evidence | Conservative v1 policy; thresholds are assumptions requiring confirmation. [ASSUMED] |

### Rejection Flow Matrix

| Condition | Qualifier | Generator | Validators | Reviewer | Final outcome |
|-----------|-----------|-----------|------------|----------|---------------|
| Extractor did not yield selected workflow | skipped/rejected | zero calls | skipped | zero calls | `no_qualified_workflow` [ASSUMED] |
| Score <75 or hard fail | rejected | zero calls | skipped | zero calls | `qualification_rejected` [VERIFIED: QUAL-02] |
| Generator refusal/incomplete/schema-invalid | passed | one decided business outcome | skipped | zero calls | `generation_rejected` [ASSUMED] |
| Any validation error | passed | generated | error report | zero calls | `validation_rejected` [VERIFIED: VAL-03] |
| Reviewer `NO` | passed | generated | clean | one call | `review_rejected` [VERIFIED: REV-03] |
| Reviewer `YES`, confidence <0.80 | passed | generated | clean | one call | `review_low_confidence` [VERIFIED: REV-03] |
| Reviewer refusal/incomplete/schema-invalid | passed | generated | clean | one decided business outcome | `review_unavailable` [ASSUMED] |
| Reviewer `YES`, confidence ≥0.80 | passed | generated | clean | one call | `eligible_local_candidate` [VERIFIED: REV-03] |

All rows are succeeded pipeline attempts unless an infrastructure adapter raises a sanitized transient/permanent failure. [VERIFIED: established Phase 2 pattern; ASSUMED for Phase 3]

## State of the Art

| Old Approach | Current Approach | When Changed / Observed | Impact |
|--------------|------------------|-------------------------|--------|
| Private/ad hoc Skill layout | Open Agent Skills directory with `SKILL.md`, optional resources, and progressive disclosure | Current official spec inspected 2026-07-22 | Generate the standard directly and keep `SKILL.md` concise. [CITED: https://agentskills.io/specification] |
| Free-text model output then parsing | Strict JSON Schema / Pydantic Structured Outputs | Current OpenAI guidance inspected 2026-07-22 | Generator and Reviewer failures are typed, not parser heuristics. [CITED: https://developers.openai.com/api/docs/guides/structured-outputs] |
| Assuming an official validator is production-complete | Use official reference as one versioned signal plus project checks | Official repository currently labels `skills-ref` demonstration-only | VAL-01/02 need a layered validator. [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref] |
| CLI-only validator integration | Python `validate(Path) -> list[str]` API | Present in official main and PyPI docs | Avoid subprocess authority and brittle prose parsing. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py] |

**Deprecated/outdated:**

- The PyPI 0.1.1 description shows `agentskills validate`, while the current official repository and specification show `skills-ref validate`. Do not make either executable name the application contract; import the library and record the installed version. [CITED: https://pypi.org/project/skills-ref/] [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref]
- The official repository's `pyproject.toml` still declares 0.1.0 while PyPI has 0.1.1. Exact distribution and source provenance must be confirmed during the human gate. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/pyproject.toml] [CITED: https://pypi.org/project/skills-ref/]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact qualification weights, confidence hard floor `0.70`, and hard-fail vocabulary | Qualification | False positives/negatives or product-policy disagreement; lock in a versioned fixture evaluation before implementation |
| A2 | Quote caps of 120 characters each / 240 total and unregistered-match threshold of 80 | Validation | Too strict for useful attribution or too permissive for copying; these are policy, not legal safe harbors |
| A3 | `lineage_id` derived from repo ID, normalized title, and evidence paths is sufficiently stable for MVP | Identity | Title/path changes can require human remapping; collisions must fail closed |
| A4 | Use a full-prefix `phase3-v1` run rather than importing a completed Phase 2 suffix | Architecture | Repeats Phase 2 remote reads/Extractor once under a new producer version; avoids weakening ledger authority but increases cost during the phase transition |
| A5 | One selected workflow per generator/reviewer request is the correct isolation/cost unit | Architecture | CLI selection UX and multi-workflow orchestration may need an explicit subject contract |
| A6 | `references/provenance.json` is the best machine-readable location | Generation | Catalog conventions may prefer a root manifest; no catalog layout decision exists yet |
| A7 | `allowed-tools` must be omitted rather than left empty | Generation | A future client/catalog may require it, but current spec marks it experimental and omission is safer |

## Open Questions

1. **How is one workflow selected when a repository yields 2-3 `WorkflowSpec`s?**
   - What we know: Phase 2 emits up to three workflows in one Extractor payload and fingerprints each. [VERIFIED: Phase 2 contracts]
   - What's unclear: The current `RepositorySubject` does not carry a pre-extraction workflow selector, and Phase 3 should isolate generation/review per Skill. [VERIFIED: codebase inspection]
   - Recommendation: add a deterministic local selection contract after Extractor (iterate sorted full fingerprints, one candidate sub-record each) while keeping at most three generation and three review calls per repository; if the stage runner cannot checkpoint sub-items safely, plan one batch Structured Output call with independent per-workflow results and explicitly test cross-workflow isolation. [ASSUMED]

2. **What is the cross-commit lineage rule?**
   - What we know: current workflow ID changes with fingerprint, and GEN-05 needs update rather than duplicate behavior. [VERIFIED: codebase inspection and GEN-05]
   - What's unclear: no immutable source workflow identifier exists upstream. [VERIFIED: WorkflowSpec schema]
   - Recommendation: introduce `lineage_id` now, test title/path-stable updates, and fail ambiguous mappings to human review. Do not silently claim semantic identity across unrelated changed workflows. [ASSUMED]

3. **Which generator and reviewer model snapshot becomes production authority?**
   - What we know: model is configuration-driven; the current project default is `gpt-5.6-terra`, while actual production snapshot choice remains open. [VERIFIED: AGENTS.md and STATE]
   - What's unclear: fixture quality/cost results for generation and review do not yet exist. [VERIFIED: test fixture inventory]
   - Recommendation: implement configurable model IDs and record configured/actual IDs; lock the production snapshot only after valid/reject/injection fixture evaluation. [VERIFIED: project decision; ASSUMED for gate timing]

4. **Will the `skills-ref` dependency pass human supply-chain review?**
   - What we know: PyPI 0.1.1 exists, but the legitimacy seam says `SUS`, the repo declares 0.1.0, the PyPI CLI name differs, and the official repo calls it demonstration-only. [VERIFIED: package checks and cited official sources]
   - What's unclear: accepted exact wheel/source/maintainer provenance and transitive lock graph. [VERIFIED: no current lock entry]
   - Recommendation: make this an early blocking checkpoint. If rejected, Phase 3 cannot truthfully satisfy VAL-01 until an approved official distribution/commit is selected. [VERIFIED: VAL-01]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Project-managed Python | All Phase 3 code/tests | ✓ | 3.13.14 | None needed [VERIFIED: local probe] |
| Project-managed uv | Locked dependency and test commands | ✓ | 0.11.29 | Use explicit `.tools/uv-0.11.29/bin/uv`; shell `uv` is not on PATH. [VERIFIED: local probe] |
| OpenAI SDK | Generator/Reviewer adapters | ✓ | 2.46.0 | Recorded `httpx.MockTransport` fixtures for tests; live key only for later canary. [VERIFIED: local probe] |
| Pydantic | Contracts/Structured Outputs | ✓ | 2.13.4 | — [VERIFIED: local probe] |
| pytest | Validation architecture | ✓ | 9.1.1 | — [VERIFIED: local probe] |
| `skills-ref` | VAL-01 | ✗ | — | No truthful fallback for the official-validator requirement; dependency approval is blocking. [VERIFIED: local probe] |
| `OPENAI_API_KEY` | Live generation/review | ✗ | — | Recorded fixtures cover implementation; live model verification remains a later authenticated gate. [VERIFIED: presence-only environment probe] |
| `SKILLSCOUT_GITHUB_TOKEN` | Full Phase 3 live repo path | ✗ | — | Recorded GitHub fixtures cover planning/implementation tests. [VERIFIED: presence-only environment probe] |

**Missing dependencies with no fallback:** approved/pinned `skills-ref` for VAL-01. [VERIFIED: local probe and VAL-01]

**Missing dependencies with fallback:** OpenAI and GitHub credentials are absent, but recorded transports are the required default for Phase 3 automated tests. [VERIFIED: existing test architecture]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 [VERIFIED: local environment] |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`, strict config/markers) [VERIFIED: codebase inspection] |
| Quick run command | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_qualification.py tests/test_skill_generation.py tests/test_skill_validation.py tests/test_openai_review.py` [ASSUMED] |
| Full suite command | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` [VERIFIED: established project gate] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUAL-01/02 | 100-point rules, hard failures, stable ordering/version, 75 boundary | unit/property matrix | `... pytest -q tests/test_qualification.py` | ❌ Wave 0 |
| GEN-01/02 | deterministic standard package; closed paths/types/modes; no scripts/binaries | unit + filesystem adversarial | `... pytest -q tests/test_skill_generation.py` | ❌ Wave 0 |
| GEN-03/04 | paraphrase/quote limits and exact provenance bindings | unit + fixture | `... pytest -q tests/test_skill_generation.py tests/test_skill_validation.py` | ❌ Wave 0 |
| GEN-05 | slug/lineage/artifact/package identity and exact reuse | unit + integration | `... pytest -q tests/test_skill_generation.py tests/test_phase3_pipeline.py` | ❌ Wave 0 |
| VAL-01 | pinned official validator plus custom structure/progressive disclosure | integration | `... pytest -q tests/test_skill_validation.py -k 'official or structure'` | ❌ Wave 0 |
| VAL-02/03 | all security/source/over-copy checks; severity/count/gate coherence | adversarial parameter matrix | `... pytest -q tests/test_skill_validation.py` | ❌ Wave 0 |
| REV-01/02 | isolated request shape, four inputs only, no files in output schema | adapter contract | `... pytest -q tests/test_openai_review.py` | ❌ Wave 0 |
| REV-03 | clean+YES+0.80 boundary; NO/0.799/error skips | unit + integration | `... pytest -q tests/test_openai_review.py tests/test_phase3_pipeline.py` | ❌ Wave 0 |
| All | CLI happy path, every rejection, resume, zero-call same-identity reuse | E2E recorded transports | `... pytest -q tests/test_cli_validate_skill.py` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** run the narrow module(s) named in that task plus Ruff on touched source/tests. [ASSUMED]
- **Per wave merge:** `.tools/uv-0.11.29/bin/uv run --locked pytest -q` and `.tools/uv-0.11.29/bin/uv run --locked ruff check .`. [VERIFIED: project practice]
- **Phase gate:** `uv lock --check`, build without sources, Ruff, full pytest, source-wide forbidden-capability scan, artifact secret scan, and package-lock hash equality to the human-approved Phase 3 lock. [VERIFIED: existing gate pattern; ASSUMED for new lock authority]

### Wave 0 Gaps

- [ ] Human dependency checkpoint for `skills-ref==0.1.1` plus exact transitive lock approval. [VERIFIED: package audit]
- [ ] `tests/test_qualification.py` and score/hard-fail fixtures for 74/75/76, confidence 0.699/0.700, two-step hard fail, source-execution hard fail, and valid evidence. [ASSUMED]
- [ ] `tests/test_skill_generation.py` with deterministic render, slug collision, provenance, permissions, no scripts/binaries, and quote limits. [ASSUMED]
- [ ] `tests/test_skill_validation.py` with valid official fixture plus missing frontmatter, name mismatch, broken/deep/orphan reference, symlink, hard link/TOCTOU seam, mode `0755`, binary, secret, injection, URL, download-execute, missing provenance, hash mismatch, and over-copy cases. [ASSUMED]
- [ ] `tests/test_openai_generate.py` and recorded parsed/refusal/incomplete/schema-invalid/429/500 responses. [ASSUMED]
- [ ] `tests/test_openai_review.py` and recorded YES, NO, 0.799, 0.800, refusal, incomplete, schema-invalid, 429, and 500 responses. [ASSUMED]
- [ ] `tests/test_phase3_pipeline.py` for closed profile/root, REMOTE_READ ceiling, skip cascade, retry, resume, and completed-run reuse. [ASSUMED]
- [ ] `tests/test_cli_validate_skill.py` for happy path and every business rejection with exact GitHub/OpenAI call counts and zero remote writes. [ASSUMED]
- [ ] Reuse the seven Phase 2 injection fixtures and canaries; add generated-artifact/reviewer delimiter variants. [VERIFIED: existing fixtures; ASSUMED for additions]

## Security Domain

Security enforcement is enabled at ASVS Level 1. [VERIFIED: `.planning/config.json`]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| Authentication | no | No user/session authentication boundary is introduced in this local CLI phase. Credentials remain environment-injected adapter configuration. [VERIFIED: phase scope] |
| Session Management | no | Responses are independent and `store=false`; no conversational session is reused. [VERIFIED: requirements] |
| Access Control | yes, capability level | Closed composition root permits only `NONE`, `LOCAL_STATE`, and `REMOTE_READ`; no `REMOTE_WRITE`. [VERIFIED: Phase 2 architecture; ASSUMED for Phase 3 root] |
| Encoding, Sanitization, Injection Prevention | yes | Strict typed input, NFKC/control handling for scans, deterministic rendering, no shell interpolation, and tool-less Structured Outputs. [CITED: https://owasp.org/www-project-application-security-verification-standard/] |
| File Handling | yes | Exact path/type/size/mode allowlists, no links/binaries/scripts, descriptor identity checks, bounded reads. ASVS 5.0 file controls require size and content/type validation. [CITED: https://cornucopia.owasp.org/taxonomy/asvs-5.0/05-file-handling/02-file-upload-and-content] |
| Cryptography | yes, integrity only | Standard SHA-256 canonical digests; never hand-roll encryption or secret storage. [VERIFIED: existing project pattern] |
| Error Handling / Logging / Data Protection | yes | Closed codes and bounded summaries; no secrets, raw exceptions, absolute paths, or full source text. [VERIFIED: project constraints] |
| Malicious Code / Business Logic | yes | Documentation-only allowlist, deterministic gates, no model-owned authority, and no reviewer override of validation. [VERIFIED: GEN-02, VAL-03, REV-03] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Generated prompt injection manipulates Reviewer | Spoofing / Tampering | Four-section inert-data envelope, separate developer instructions, no tools, strict response schema, deterministic final gate, injection corpus. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html] |
| Path traversal, symlink swap, executable mode | Tampering / Elevation of Privilege | Closed relative paths, descriptor-anchored materialization, identity recheck, retained lock, exact `0644`, no scripts/binaries. [VERIFIED: existing localfs patterns; ASSUMED for artifact writer] |
| Secret-like model output reaches artifact/report | Information Disclosure | Pre-render and post-render scans; canaries; report pattern IDs only; credentials header-only. [CITED: https://docs.github.com/en/code-security/reference/secret-security/supported-secret-scanning-patterns] |
| Validator failure is treated as pass | Tampering | Exception -> structured `error`; every error blocks Reviewer/Publisher. [VERIFIED: VAL-03] |
| Artifact changes after validation | Tampering | Package digest over exact path/hash/mode/size manifest; Phase 4 must publish only those bytes. [ASSUMED] |
| Slug collision aliases another workflow | Spoofing | Full lineage identity comparison and collision fail-closed; short suffix never authorizes. [ASSUMED] |
| Oversized model/package output exhausts resources | Denial of Service | Pydantic collection/string caps, bounded output tokens, package/file/line/token caps, manifest ceiling. [VERIFIED: existing bounded contract pattern; ASSUMED for Phase 3 cap values] |
| Repeated calls seek a favorable review | Repudiation / Business Logic | Decided outcomes are recorded once; exact completed-run reuse; only infrastructure failures retry. [VERIFIED: established retry pattern] |

## Sources

### Primary (MEDIUM confidence from official sources)

- [Agent Skills specification](https://agentskills.io/specification) — directory, frontmatter, naming, progressive disclosure, references, and official validator direction.
- [Official Agent Skills repository](https://github.com/agentskills/agentskills) — current source authority and project ownership.
- [Official skills-ref README](https://github.com/agentskills/agentskills/tree/main/skills-ref) — demonstration-only warning, install, CLI, and Python API.
- [Official skills-ref validator source](https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py) — exact validation coverage and list-returning API.
- [Official skills-ref package metadata](https://github.com/agentskills/agentskills/blob/main/skills-ref/pyproject.toml) — source version, dependencies, and console entry point.
- [OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) — strict schemas and refusal/incomplete handling.
- [OpenAI Python 2.46.0 registry metadata](https://pypi.org/pypi/openai/2.46.0/json) — exact project-pinned distribution, retries, and release date.
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) and [ASVS 5 file controls](https://cornucopia.owasp.org/taxonomy/asvs-5.0/05-file-handling/02-file-upload-and-content) — validation/file security categories.
- [OWASP LLM Prompt Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) — role/data separation, least privilege, output validation, adversarial testing.
- [GitHub supported secret patterns](https://docs.github.com/en/code-security/reference/secret-security/supported-secret-scanning-patterns) — provider/generic secret pattern categories.
- Local codebase and Phase 2 verification — current schemas, fingerprint semantics, prefix-indexed ledger, retry/idempotency, capability ceiling, and recorded fixture architecture. [VERIFIED: codebase inspection]

### Secondary (MEDIUM confidence)

- [PyPI skills-ref 0.1.1](https://pypi.org/project/skills-ref/) — distribution version/date/hash and the CLI-name discrepancy; package remains `SUS` pending human provenance review.
- [PyPI Pydantic 2.13.4](https://pypi.org/pypi/pydantic/2.13.4/json) and [pytest 9.1.1](https://pypi.org/pypi/pytest/9.1.1/json) — exact current project pins and publish dates.

### Tertiary (LOW confidence)

- None used as factual authority. Project-specific thresholds and lineage heuristics are explicitly tagged `[ASSUMED]` and listed in the Assumptions Log.

## Metadata

**Confidence breakdown:**

- Standard stack: MEDIUM — existing pins are verified; new `skills-ref` is official-spec-linked but the legitimacy seam returned `SUS`, source/PyPI versions differ, and human lock approval is required.
- Architecture: HIGH — recommendations follow verified Phase 1/2 profiles, exact prefix ledger, typed contracts, retry model, and capability roots.
- Qualification policy: LOW — requirement dimensions and threshold are locked, but weights, confidence floor, and hard-fail vocabulary are project choices needing fixture evaluation.
- Validation patterns: MEDIUM — control families come from requirements and official security guidance; exact quote and size thresholds are policy assumptions.
- Reviewer integration: HIGH — it directly reuses the verified Extractor adapter shape and current official Structured Outputs behavior.
- Identity/lineage: LOW — exact-input artifact reuse is well supported, but cross-commit workflow lineage is not present in the Phase 2 schema and needs a deliberate contract.

**Research date:** 2026-07-22

**Valid until:** 2026-07-29 for `skills-ref`/OpenAI package details; 2026-08-21 for stable internal architecture and Agent Skills format findings.
