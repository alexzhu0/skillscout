# Phase 03: Validated Skill Candidate - Research

**Researched:** 2026-07-23
**Domain:** Deterministic workflow qualification, documentation-only Agent Skill generation, artifact validation, and independent LLM review
**Confidence:** MEDIUM

## User Constraints

- No `CONTEXT.md` exists. Planning is intentionally based on the roadmap, requirements, Phase 2 verified contracts, project constraints, and current technical research. [VERIFIED: `init.phase-op 3` and phase directory inspection]
- Phase 3 must satisfy `QUAL-01`, `QUAL-02`, `GEN-01` through `GEN-05`, `VAL-01` through `VAL-03`, and `REV-01` through `REV-03`. [VERIFIED: `.planning/REQUIREMENTS.md`]
- The output is a local, documentation-only, source-traceable Agent Skill candidate. It may contain `SKILL.md` and, only when necessary, one-level `references/` or text-only `assets/`; it must never contain `scripts/`, binary files, or executable file modes. [VERIFIED: `.planning/ROADMAP.md` Phase 3 success criteria]
- Qualification is deterministic, versioned, passes at 75/100 by default, and is blocked by any hard failure. [VERIFIED: QUAL-01 and QUAL-02]
- `WorkflowSpec` is the only semantic boundary from source repository content into qualification, generation, validation, review, and publishing. Complete README, documentation, or source bytes must not re-enter Phase 3. [VERIFIED: EXTR-04 and Phase 2 verification]
- Phase 3 accepts only a strict `CandidateSubjectDescriptorV1` that points to an already verified, completed Phase 2 run and one selected full workflow fingerprint. Source resolution occurs before any Phase 3 run lookup or ledger creation; an unavailable/mismatched source is a sanitized pre-run result with zero downstream calls. Do not widen `RepositorySubject` or the existing `load_subject`. [VERIFIED: Phase 3 architecture reset]
- Generator and Reviewer calls are tool-less, `store=false`, bounded, independently prompted, and receive no credentials. The Reviewer receives only the `WorkflowSpec`, generated artifact, provenance, and Validation Report; it judges but cannot return replacement files. [VERIFIED: REV-01, REV-02, SEC-01, and AGENTS.md]
- Phase 3 preserves the Phase 2 authority ceiling: local state plus remote reads only. It introduces no branch, PR, merge, approval, release, package-install-at-runtime, or other remote-write capability. [VERIFIED: AGENTS.md, Phase 2 verification, and Phase 4 scope]
- An identical completed `CandidateExecutionAuthorityV1` must reproject the exact terminal summary and any optional frozen artifact/report/attestation bytes; rejection branches may have no artifact. Validator errors, Reviewer `NO`, or Reviewer confidence below `0.80` are auditable terminal business outcomes and cannot create a publication plan. [VERIFIED: Phase 3 architecture reset, success criterion 6, and REV-03]
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
| GEN-04 | Machine-readable complete provenance | Generation-time-only `references/provenance.json`, complete WorkflowSpec authority, and external frozen package manifest |
| GEN-05 | Stable slug and versioned workflow fingerprint; update rather than duplicate | Authority-bound lineage, pre-lookup execution identity, immutable artifact/package, external attestation/summary, and exact terminal reuse |
| VAL-01 | Official Agent Skills validation plus format/reference/progressive-disclosure checks | Pinned `skills-ref` adapter plus SkillScout structural checks |
| VAL-02 | Secret, dangerous action, tool, download/execute, injection, URL, provenance, scripts, and over-copy checks | Versioned deterministic validation policy and adversarial fixtures |
| VAL-03 | Structured `error/warning/info`; every error blocks | Closed finding model, fail-closed validator runtime mapping, and gate matrix |
| REV-01 | Independent fresh LLM context with only four allowed inputs | Separate `OpenAIReviewClient` and serialized review envelope |
| REV-02 | Strict YES/NO judgment; no edits | Pydantic schema with no file/body replacement fields |
| REV-03 | Error-free validation + YES + confidence ≥0.80 | Deterministic publication-eligibility predicate |

</phase_requirements>

## Summary

Phase 3 is a separate local pipeline over a verified Phase 2 result, not a full-prefix replay of Scout through Extractor. A new bounded `CandidateSubjectDescriptorV1` and safe loader identify one completed Phase 2 run, one selected full workflow fingerprint, the expected complete `WorkflowSpec` digest, a verified-chain/output-hash anchor, and an optional strict prior-lineage binding. A read-only Phase 2 state/query seam verifies the completed chain and reconstructs the exact `WorkflowSpec` before Phase 3 opens or looks up any run. This preserves Phase 2 without repeating its GitHub/OpenAI work or weakening its ledger. [VERIFIED: Phase 3 architecture reset]

Qualification and all artifact safety decisions must be deterministic. Use the LLM only to transform one qualified `WorkflowSpec` into a bounded semantic draft and to independently judge the rendered result. SkillScout, not either model, owns the slug, lineage key, filenames, frontmatter, provenance, file modes, package digest, validation findings, and final eligibility gate. [VERIFIED: project deterministic-first constraint; ASSUMED for the proposed ownership split]

Run the official `skills-ref` validator, but do not mistake it for the complete Phase 3 validator. The current official repository marks the reference library as demonstration-only, and its `validate(Path)` implementation checks `SKILL.md` frontmatter and naming conventions; it does not validate links, progressive disclosure, provenance, executable bits, secrets, dangerous commands, or copied-source limits. [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref] [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py]

**Primary recommendation:** resolve a strict candidate descriptor into `WorkflowSpecAuthorityV1` before run creation, compute a pre-lookup `CandidateExecutionAuthorityV1`, and make every Phase 3 terminal branch an immutable `CandidateTerminalSummaryV1`. Generation freezes a package before validation; review produces an external attestation and never mutates package bytes. Same-authority completed reuse reprojects the exact stored terminal bytes with zero new calls, rows, or events. [VERIFIED: Phase 3 architecture reset]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Qualification scoring and hard fails | API / Backend domain | — | Pure deterministic policy over a validated `WorkflowSpec` and upstream facts; no filesystem or model needed. [VERIFIED: QUAL-01] |
| Semantic Skill drafting | API / Backend adapter | OpenAI Responses API | Model performs bounded rephrasing only; it does not choose identity, paths, modes, or gates. [ASSUMED] |
| Frontmatter, provenance, and package rendering | API / Backend domain | Local Storage | Deterministic rendering owns exact bytes; an anchored writer materializes only declared regular files. [ASSUMED] |
| Official and custom validation | API / Backend domain | Local Storage | Validators inspect a bounded local artifact and return data; they never execute artifact content. [VERIFIED: VAL-01 and VAL-02] |
| Independent review | API / Backend adapter | OpenAI Responses API | A fresh tool-less call judges the four allowed inputs and returns a closed decision schema. [VERIFIED: REV-01 and REV-02] |
| Phase 2 source resolution | Database / Storage | API / Backend | A read-only query seam verifies the referenced completed Phase 2 chain and selected complete WorkflowSpec before Phase 3 ledger access. [VERIFIED: Phase 3 architecture reset] |
| Artifact/checkpoint/reuse authority | Database / Storage | API / Backend | Pre-lookup execution authority gates resume/reuse; immutable external summaries and attestations bind terminal facts without rewriting package bytes. [VERIFIED: Phase 3 architecture reset] |
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
| Separate Phase 3 pipeline over a verified Phase 2 query result | Full-prefix `phase3-v1` replay or checkpoint-prefix import | The safe query seam validates Phase 2 under its own profile and supplies a content-bound authority object; Phase 3 then owns a new ledger without replaying upstream API/model calls or pretending imported rows belong to its chain. [VERIFIED: Phase 3 architecture reset] |

**Installation (do not run before the human dependency gate):**

```bash
# Gate A3: review the exact distribution, source provenance, and wheel hash.
# Gate B3: approve the resulting transitive uv.lock graph and SHA-256 authority.
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
| `strictyaml` | PyPI | Established but not independently age-resolved by the seam | Unknown to seam | Resolve from package metadata during Gate A3 | SUS | Transitive; approve exact resolved version and hashes at Gate B3. [VERIFIED: package-legitimacy seam] |

**Packages removed due to SLOP verdict:** none. [VERIFIED: package-legitimacy seam]

**Packages flagged as suspicious [SUS]:** `skills-ref`, `click`, `strictyaml`. The seam could not resolve registry age/download/repository signals, and the official repository calls `skills-ref` demonstration-only. The planner must require human verification before any install or lock change. [VERIFIED: package-legitimacy seam] [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref]

## Architecture Patterns

### System Architecture Diagram

```text
CandidateSubjectDescriptorV1 (bounded local input; one selected fingerprint)
      |
      v
load_candidate_subject() [new safe loader; existing load_subject unchanged]
      |
      v
PhaseTwoCandidateSource query + verify completed Phase 2 chain/output anchor
      | unavailable/mismatch/rejection/no_workflow/refusal/incomplete/schema/missing fingerprint
      +--------------------------------------------------> candidate_source_unavailable
      |                                                    no Phase 3 ledger/calls
      v
WorkflowSpecAuthorityV1 (complete WorkflowSpec + verified Phase 2 anchor)
      |
      v
CandidateExecutionAuthorityV1 (configured/pre-lookup authority)
      |                         |
      | exact completed match   +--> reproject exact CandidateTerminalSummaryV1/package
      |                              zero calls/rows/events; no mutation
      v new/resumable Phase 3 run
Qualifier (pure, versioned 100-point policy)
      |                         |
      | qualified               +--> rejected_qualification -> terminal summary
      v
Lineage resolution (new lineage or exact PriorLineageBinding)
      |                         |
      | resolved                +--> ambiguity/rejection -> terminal summary
      v
Generator adapter (fresh tool-less Responses call, one selected workflow)
      | structured semantic draft / refusal / incomplete / schema failure
      v
Deterministic renderer + anchored content-addressed materializer
      | GeneratedArtifactIdentityV1 + frozen package bytes
      | SKILL.md + optional one-level text resources + provenance.json
      | external package_digest (never written back into package)
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
external ReviewAttestationV1
      |
      v
CandidateTerminalSummaryV1 + exact optional package/validation/review bindings

No Phase 3 edge reaches a Publisher or REMOTE_WRITE adapter.
```

The descriptor producer may derive at most three descriptors from a Phase 2 result by sorting full workflow fingerprints, but each descriptor crosses the Phase 3 boundary and runs independently. Generator/Reviewer requests, ledgers, retries, artifacts, attestations, and outcomes are never batched across workflows. [VERIFIED: Phase 3 architecture reset]

### Recommended Project Structure

```text
src/skillscout/
├── domain/
│   ├── candidate_authority.py  # descriptor, WorkflowSpec/execution/lineage authority
│   ├── qualification.py       # policy, rule decisions, scoring report
│   ├── skill_artifacts.py     # draft, provenance, manifest, identity, renderer
│   ├── validation.py          # finding schema and deterministic checks
│   └── review.py              # attestation, terminal summary, eligibility gate
├── adapters/
│   ├── phase2_state.py        # read-only verified-chain/query seam
│   ├── openai_generate.py     # one bounded structured generation call
│   ├── openai_review.py       # separate one-call independent reviewer
│   └── skills_ref.py          # narrow wrapper over skills_ref.validate(Path)
├── application/
│   ├── processors.py          # preserve PhaseTwoProcessor behavior
│   ├── candidate_source.py    # separate bounded loader + pre-run resolution
│   └── phase3.py              # Phase 3-only run/reuse/terminal orchestration
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
├── test_candidate_source.py
├── test_candidate_authority.py
├── test_phase3_pipeline.py
└── test_cli_validate_skill.py
```

Keep the existing Phase 2 modules, `RepositorySubject`, `load_subject`, profile, and public behavior unchanged. Phase 3 receives only the verified query result; it neither composes `PhaseTwoProcessor` nor imports Phase 2 rows into its ledger. [VERIFIED: Phase 3 architecture reset]

### Pattern 1: Strict Pre-Run Candidate Source Boundary

`CandidateSubjectDescriptorV1` is a separate bounded, strict JSON contract containing: descriptor schema version, completed Phase 2 run ID, expected Phase 2 profile/producer version, authoritative Extractor envelope output hash or verified-chain anchor, selected full workflow fingerprint, expected complete WorkflowSpec digest, and optional `PriorLineageBindingV1`. The new loader applies the existing local-file ownership/link/size/canonical-JSON discipline but does not widen `RepositorySubject` or `load_subject`. [VERIFIED: Phase 3 architecture reset]

The required state seam is a read-only `PhaseTwoCandidateSource.resolve(descriptor)` query. It must verify the referenced run is completed under the expected Phase 2 profile, re-verify the persisted Phase 2 chain under Phase 2 rules, verify the Extractor terminal envelope/output hash, locate exactly one selected fingerprint, strictly parse the complete `WorkflowSpec`, recompute its complete canonical digest, and return it with its verified-chain anchor. It must not execute Phase 2 handlers, create Phase 3 rows, or make GitHub/OpenAI calls. [VERIFIED: Phase 3 architecture reset]

Phase 2 rejection, `no_workflow`, refusal, incomplete/schema failure, chain/output mismatch, missing fingerprint, duplicate selected fingerprint, or descriptor mismatch maps to one sanitized pre-run `candidate_source_unavailable`. This result has no Phase 3 run/ledger, validator invocation, Generator/Reviewer call, or retry side effect. Upstream business branches therefore do not appear in the Phase 3 terminal matrix. [VERIFIED: Phase 3 architecture reset]

Because the existing verified ledger treats profiles as global prefixes beginning at Scout, the separate Phase 3 run needs an explicit profile-relative ordered-stage verifier for `(QUALIFIER, GENERATOR, VALIDATOR, REVIEWER)` rather than fake Scout/Extractor rows. Keep the Phase 2 prefix verifier unchanged; the new verifier applies the same attempt/event/output-hash continuity rules against the declared Phase 3 sequence and binds its first row to `CandidateExecutionAuthorityV1`. Do not relax stage-index checks globally or copy Phase 2 records into the Phase 3 chain. [VERIFIED: Phase 3 architecture reset and codebase inspection of `verify_run_chain`]

### Pattern 2: Closed Qualification Policy

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

Within the Phase 3 `QUALIFIER` stage, qualification runs first. A rejection records `LineageResolutionV1(status="not_evaluated_qualification_rejected")`; a pass invokes deterministic lineage resolution before the stage output is committed. Thus lineage ambiguity is a Phase 3 terminal outcome without inventing a fifth pipeline stage. [VERIFIED: Phase 3 architecture reset]

### Pattern 3: Structured Draft, Deterministic Package

**What:** The generator returns semantic fields, not a filesystem. A trusted renderer supplies the stable slug, fixed frontmatter keys, headings, relative links, provenance location, filenames, modes, and canonical bytes. [ASSUMED]

Define immutable code constants `RENDERER_VERSION = "skill-renderer-v1"` and `ELIGIBILITY_POLICY_VERSION = "candidate-eligibility-v1"`. They are producer authority, not mutable per-run flags; both enter `CandidateExecutionAuthorityV1` and every applicable report/summary. Any change requires a new value and invalidates completed reuse. [VERIFIED: Phase 3 architecture reset]

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

### Pattern 4: Layered Authority, Artifact, Review, and Terminal Identity

Never use the workflow fingerprint alone as Phase 3 input or reuse authority. It is only the selected-version discriminator inside a complete verified source authority. [VERIFIED: Phase 3 architecture reset]

| Contract / identity | Creation time and canonical authority | Purpose |
|---------------------|---------------------------------------|---------|
| `WorkflowSpecAuthorityV1` | Before Phase 3 lookup: digest the complete strictly parsed `WorkflowSpec`—every field, all workflow/step evidence bindings and bounded excerpts, schema and fingerprint versions—plus the authoritative Phase 2 Extractor envelope/output hash or verified-chain anchor. | Proves exactly which complete verified semantic payload crossed from Phase 2; fingerprint alone is insufficient. [VERIFIED: Phase 3 architecture reset] |
| `CandidateExecutionAuthorityV1` | Before Phase 3 lookup: WorkflowSpecAuthority digest, selected full fingerprint, optional PriorLineageBinding digest, qualification policy/report schema versions, configured Generator model and prompt/output schema, `RENDERER_VERSION` plus artifact/provenance schema versions, pinned official-validator distribution/hash and custom validation policy/report schema, configured Reviewer model and prompt/output/policy versions, `ELIGIBILITY_POLICY_VERSION`, Phase 3 producer/profile, and retry-policy versions. | Sole resume/completed-lookup key. All members are knowable before lookup. A configured model/version change invalidates reuse. [VERIFIED: Phase 3 architecture reset] |
| `GeneratedArtifactIdentityV1` | After generation: canonical structured draft plus a canonical generation-time authority projection containing WorkflowSpec authority, selected fingerprint, resolved lineage/slug, qualification-report digest and policy/schema, configured/actual Generator model, Generator prompt/output schema, `RENDERER_VERSION`, artifact/provenance schemas, and Phase 3 producer/retry versions. It excludes validator, Reviewer, eligibility, and other post-generation facts. | Identifies the generated meaning and complete authority that could affect its bytes without coupling package identity to later stages. [VERIFIED: Phase 3 architecture reset] |
| `package_digest` | After deterministic rendering/provenance: digest the canonical ordered path -> content hash/mode/size manifest outside the package bytes. | Freezes exactly the package Validators and Reviewer inspect; never write the digest back into its own package. [VERIFIED: Phase 3 architecture reset] |
| `ReviewAttestationV1` | Only after validation: bind immutable package digest, ValidationReport digest, configured/actual Reviewer model, review prompt/output/policy versions, outcome/verdict/confidence/reasons, and bounded telemetry. Store externally. | Proves the independent judgment over exact immutable bytes; it is never written into the reviewed package. [VERIFIED: Phase 3 architecture reset] |
| `CandidateTerminalSummaryV1` | On every Phase 3 terminal branch: bind execution authority, WorkflowSpec authority, lineage-resolution result (including `not_evaluated_qualification_rejected`), optional bounded Generator outcome/actual-model evidence, optional artifact/package, optional ValidationReport digest, optional ReviewAttestation digest, eligibility, and closed outcome code. Store canonical bytes externally. | Phase 4 consumes this summary/attestation, not mutable stage state. Same-authority completed reuse reprojects these exact bytes and any present package without mutation. [VERIFIED: Phase 3 architecture reset] |

Configured Generator/Reviewer model IDs and all version constants are pre-lookup authority. Actual model IDs cannot be required before a call; they are generation or review terminal evidence. A stable unchanged configured ID authorizes lookup of the already completed result, while changing that configured ID invalidates reuse. [VERIFIED: Phase 3 architecture reset]

The current `workflow_id` is derived from `wf-fingerprint-v1`, so it changes when normalized goal or ordered steps change and cannot be lineage authority. A new lineage is the full digest of `lineage-v1`, numeric repository ID, and the initial complete `WorkflowSpecAuthorityV1` digest. [VERIFIED: `src/skillscout/domain/extraction.py`, `_build_workflow_spec`, and Phase 3 architecture reset]

An update retains that lineage and its stable slug only through an exact approved `PriorLineageBindingV1` from the prior lineage/package to the new WorkflowSpec authority. Its canonical fields include repo ID, full lineage ID, stable slug, prior package digest and terminal-summary digest, new WorkflowSpecAuthority digest, binding schema/policy version, and the durable approval-record digest. No binding creates a new lineage. A stale binding, collision, multiple mappings, mismatched package/source, or ambiguous mapping stops for human review. Title and evidence path may change under an approved binding but are never lineage preimage or matching authority. [VERIFIED: Phase 3 architecture reset]

### Pattern 5: Package Provenance Without Future Facts or a Self-Hash Cycle

Write canonical `references/provenance.json` with at least: [VERIFIED: GEN-04; ASSUMED for layout]

- `schema_version`, `GeneratedArtifactIdentityV1` digest, its generation-time authority digest, `WorkflowSpecAuthorityV1` digest, lineage ID, and stable slug;
- repository URL, numeric repo ID, exact commit SHA, SPDX license;
- workflow ID, full fingerprint, fingerprint version;
- every evidence path, blob SHA, content hash, and bounded excerpt/quote registration;
- WorkflowSpec schema/fingerprint and verified Phase 2 anchor; qualification policy/report schema; configured and actual Generator model; Generator prompt/output schema; immutable `RENDERER_VERSION`; artifact/provenance schemas; Phase 3 producer/profile/retry-policy versions; and bounded Generator request ID/usage telemetry where policy permits.

Package provenance must never include the Reviewer model, review prompt/schema/policy, verdict, confidence, reasons, validation result, attestation, eligibility, or any other fact created after generation. Finalize provenance, render once, compute `package_digest` outside the package bytes, and freeze the admitted path/hash/mode/size manifest before validation or review. Later records may point to the digest; no later stage rewrites package bytes. [VERIFIED: Phase 3 architecture reset]

### Pattern 6: Layered Validation and Fail-Closed Review

Run Validators in this order: [ASSUMED]

1. Admit only a trusted, content-addressed workspace: regular files, no symlinks/hard-link surprises, exact manifest path set, per-file and package size caps, UTF-8 text, modes exactly `0644`, no `scripts/`, no binary signatures.
2. Call `skills_ref.validate(Path)` through a narrow adapter and map every returned item to a bounded `error` finding. Any exception becomes `official_validator_runtime_failure` (`error`) without raw exception/path leakage.
3. Verify SkillScout structure: exact `SKILL.md`, name-directory equality, fixed frontmatter keys, declared one-level resources, no broken/orphan/nested links, main file line/token cap, and all files present in the package manifest.
4. Verify provenance against `WorkflowSpecAuthorityV1` and the frozen manifest, reject future validation/review fields inside the package, and recompute the external artifact/package hashes.
5. Scan normalized structured fields and rendered bytes for secrets, injection markers, dangerous commands, download/execute chains, forbidden tools/preapproval, URLs/HTML/Markdown images, and quote/over-copy violations.
6. Emit one sorted `ValidationReport`; do not call Reviewer when `error_count > 0`.

Use `error` for gate violations, `warning` only for human-quality risks that are safe to review, and `info` for version/size/count facts. Never downgrade an official validator error. [VERIFIED: VAL-03; ASSUMED for severity policy]

Report headers must close the authority chain: `QualificationReport` binds WorkflowSpec and execution authority plus qualification versions; `ValidationReport` binds WorkflowSpec/execution/artifact identities, frozen package digest, `RENDERER_VERSION`, official-validator distribution/hash, and custom validation/report versions; `CandidateTerminalSummaryV1` additionally binds `ELIGIBILITY_POLICY_VERSION` and any ReviewAttestation. Validate these bindings before trusting report counts or eligibility. [VERIFIED: Phase 3 architecture reset]

The final source-wide OpenAI import scan has one exact allowlist relative to `src/skillscout/`: `adapters/openai_extract.py`, `adapters/openai_generate.py`, and `adapters/openai_review.py`. Any `openai` import outside those three files fails the gate. The first is the already verified Phase 2 adapter; the latter two are the only new Phase 3 model boundaries. [VERIFIED: Phase 3 architecture reset]

### Pattern 7: Independent Reviewer as Judge Only

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

This predicate is deterministic, versioned by immutable `ELIGIBILITY_POLICY_VERSION`, and belongs outside the Reviewer adapter. The resulting decision is recorded in `CandidateTerminalSummaryV1`; the package remains untouched. [VERIFIED: REV-03 and Phase 3 architecture reset]

### Anti-Patterns to Avoid

- **Replaying/importing Phase 2 as a Phase 3 prefix:** blurs producer authority and repeats upstream side effects. Verify Phase 2 through the read-only query seam before creating a separate Phase 3 run. [VERIFIED: Phase 3 architecture reset]
- **Relaxing the global ledger verifier so Phase 3 can start mid-enum:** weakens Phase 1/2 guarantees. Add an explicit profile-relative Phase 3 stage sequence and retain all hash/attempt/event checks. [VERIFIED: Phase 3 architecture reset]
- **Widening `RepositorySubject` or `load_subject`:** mixes public-repository discovery authority with a local verified-candidate descriptor. Add `CandidateSubjectDescriptorV1` and its own safe loader. [VERIFIED: Phase 3 architecture reset]
- **Treating any completed run as approved:** completed means one closed terminal outcome. Phase 4 must require an eligible `CandidateTerminalSummaryV1`, matching package digest, and matching `ReviewAttestationV1`. [VERIFIED: Phase 3 architecture reset]
- **Letting the generator output filenames/frontmatter/modes:** converts model text into filesystem authority. Render from trusted structured fields. [ASSUMED]
- **Calling Reviewer after a validation error:** spends cost and risks a model appearing to override deterministic safety. Emit `review_skipped_validation_errors`. [VERIFIED: VAL-03]
- **Using `skills-ref` alone:** it does not cover most VAL-01/02 requirements and is labeled demonstration-only. [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref]
- **Parsing validator CLI prose as a contract:** use the Python list-returning API and record the installed distribution version. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py]
- **Hashing provenance with its own package digest or future review facts:** creates a self-reference cycle or mutates reviewed bytes. Keep package provenance generation-time-only and store package digest, validation, review, and terminal facts externally. [VERIFIED: Phase 3 architecture reset]
- **Putting actual model IDs in the pre-lookup key:** those values do not exist before a call. Configured IDs gate lookup; actual Generator/Reviewer IDs are artifact/attestation terminal evidence. [VERIFIED: Phase 3 architecture reset]
- **Regenerating to seek a YES:** decided refusal/schema/NO/low-confidence outcomes are auditable business results; only transient infrastructure failures consume retry authority. [VERIFIED: Phase 2 retry pattern; ASSUMED for Phase 3 outcome mapping]
- **Persisting complete upstream repository text:** Phase 3 must operate only on bounded WorkflowSpec fields and evidence excerpts. [VERIFIED: EXTR-04]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Phase 2 candidate trust | A raw WorkflowSpec/fingerprint loader or copied Phase 2 verifier | `CandidateSubjectDescriptorV1` + read-only `PhaseTwoCandidateSource.resolve()` under Phase 2 chain rules | Prevents fingerprint-only admission and keeps upstream failures outside the Phase 3 ledger. [VERIFIED: Phase 3 architecture reset] |
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

**How to avoid:** First resolve the candidate against verified Phase 2 state without creating a Phase 3 ledger. Then compute `CandidateExecutionAuthorityV1`; an exact completed match reprojects the stored terminal summary and optional frozen package with zero calls, rows, or events. [VERIFIED: Phase 3 architecture reset]

**Warning signs:** An exact-authority completed test records any call, validator invocation, run/attempt/event/summary row, creates a new artifact directory, or serializes different terminal bytes. [VERIFIED: Phase 3 architecture reset]

### Pitfall 4: Cross-Commit Update Identity Uses the Fingerprint

**What goes wrong:** A legitimate source update changes goal/steps, therefore changes fingerprint/workflow ID, and creates a duplicate slug. [VERIFIED: current fingerprint preimage]

**Why it happens:** Content identity and lineage identity serve different purposes. [ASSUMED]

**How to avoid:** Create lineage from repository ID plus the initial complete WorkflowSpec authority. Retain it only through an exact approved binding from the prior lineage/package to the new WorkflowSpec authority; fail stale/colliding/multiple/ambiguous mappings to human review. [VERIFIED: Phase 3 architecture reset]

**Warning signs:** Slug contains the workflow fingerprint prefix or update lookup keys only on `workflow_id`. [ASSUMED]

### Pitfall 5: Fingerprint-Only Candidate Admission

**What goes wrong:** Two distinct complete `WorkflowSpec` payloads with the same selected fingerprint metadata, omitted evidence, or a mismatched Phase 2 envelope can reach the same reuse key. [VERIFIED: Phase 3 architecture reset threat model]

**Why it happens:** The fingerprint does not bind every WorkflowSpec field, evidence excerpt, schema version, or authoritative Phase 2 output. [VERIFIED: Phase 3 architecture reset]

**How to avoid:** Recompute `WorkflowSpecAuthorityV1` from the complete strict payload plus verified Phase 2 chain/output anchor before Phase 3 lookup; descriptor mismatch is pre-run `candidate_source_unavailable`. [VERIFIED: Phase 3 architecture reset]

**Warning signs:** A reuse query accepts only run ID and workflow fingerprint, or a source-resolution failure leaves Phase 3 ledger rows. [VERIFIED: Phase 3 architecture reset]

### Pitfall 6: Over-Copy Detection Pretends to Be a Legal Rule

**What goes wrong:** A numeric match threshold is described as a copyright safe harbor. No universal character count establishes that. [ASSUMED]

**Why it happens:** A technical heuristic is confused with a legal conclusion. [ASSUMED]

**How to avoid:** Make the policy intentionally conservative and versioned: generator paraphrases by default; allow only registered quotes of at most 120 characters each and 240 characters total; reject any unregistered normalized source match of 80 or more characters. Treat those thresholds as project policy requiring user confirmation, not legal advice. [ASSUMED]

**Warning signs:** Validator compares only exact raw strings, ignores Unicode/whitespace normalization, or permits unattributed quotes. [ASSUMED]

### Pitfall 7: Reviewer Can Smuggle an Edit

**What goes wrong:** A reviewer returns a replacement `SKILL.md` inside a rationale or extra JSON field, collapsing judge and generator roles. [ASSUMED]

**Why it happens:** The review schema is permissive or the application treats prose as a patch. [ASSUMED]

**How to avoid:** Extra fields forbidden, strings bounded, no replacement/file fields, and application code never writes Reviewer text into artifact files. [VERIFIED: REV-02]

**Warning signs:** Reviewer output is passed to the renderer or a `suggested_skill` field appears. [ASSUMED]

### Pitfall 8: Rejection Is Recorded as Infrastructure Failure

**What goes wrong:** Low qualification, official validation errors, Reviewer `NO`, refusal, or low confidence consume retry budget and repeatedly call the LLM. [ASSUMED]

**Why it happens:** Business outcomes raise exceptions rather than return closed payloads. [VERIFIED: Phase 2 identified and solved the same class]

**How to avoid:** Return succeeded stage attempts with closed rejection outcomes; raise only mapped transient/permanent infrastructure failures. [VERIFIED: Phase 2 pattern]

**Warning signs:** `Reviewer NO` increments `attempt_no`, or a validation error prevents the terminal summary from being written. [ASSUMED]

## Code Examples

Verified and recommended patterns:

### Immutable Producer Authority Versions

```python
# Source: Phase 3 architecture reset; values change only with a new producer contract.
from typing import Final

RENDERER_VERSION: Final = "skill-renderer-v1"
ELIGIBILITY_POLICY_VERSION: Final = "candidate-eligibility-v1"
```

Include both values in `CandidateExecutionAuthorityV1` and applicable reports/summaries. Do not permit runtime configuration to mutate their meaning under the same string. [VERIFIED: Phase 3 architecture reset]

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
    workflow_spec_authority: Digest
    candidate_execution_authority: Digest
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
| Provenance/authority | missing/mismatched `WorkflowSpecAuthorityV1`, Phase 2 anchor, repo/commit/license/fingerprint/schema/evidence binding, configured/actual Generator ID, `RENDERER_VERSION`, or unknown quote registration; any Reviewer/validation/eligibility fact inside package | Recompute against the pre-run verified authority and generation record, never generator claims; future facts are external. [VERIFIED: GEN-04 and Phase 3 architecture reset] |
| Over-copy | registered quote >120 chars; total quotes >240; unattributed normalized evidence match >=80 chars; quote not verbatim in WorkflowSpec evidence | Conservative v1 policy; thresholds are assumptions requiring confirmation. [ASSUMED] |
| OpenAI import capability | any `openai` import outside `adapters/openai_extract.py`, `adapters/openai_generate.py`, `adapters/openai_review.py` | Exact final-scan allowlist relative to `src/skillscout/`; no glob, directory-wide, or test exception. [VERIFIED: Phase 3 architecture reset] |

### Phase 3 Terminal and Reuse Matrix

`candidate_source_unavailable` is deliberately absent: it is a sanitized pre-run source-resolution result with no Phase 3 ledger. The table contains only terminal branches Phase 3 owns. [VERIFIED: Phase 3 architecture reset]

| Owned terminal branch | Package fields | Validation report | Review attestation | `CandidateTerminalSummaryV1` outcome |
|-----------------------|----------------|-------------------|--------------------|--------------------------------------|
| Qualification rejection (`score <75` or hard fail) | absent | absent | absent | `qualification_rejected` with lineage status `not_evaluated_qualification_rejected`. [VERIFIED: QUAL-02 and Phase 3 architecture reset] |
| Lineage ambiguity/rejection | absent | absent | absent | `lineage_rejected` with bound `LineageResolutionV1`; human review required. [VERIFIED: Phase 3 architecture reset] |
| Generator refusal | absent | absent | absent | `generator_refusal` [VERIFIED: Phase 3 architecture reset] |
| Generator incomplete | absent | absent | absent | `generator_incomplete` [VERIFIED: Phase 3 architecture reset] |
| Generator schema failure | absent | absent | absent | `generator_schema_failure` [VERIFIED: Phase 3 architecture reset] |
| Validation error | present and frozen | present/error | absent | `validation_rejected` [VERIFIED: VAL-03 and Phase 3 architecture reset] |
| Reviewer skipped (`review_skipped_validation_errors`) | present and frozen | present/error | absent | Required companion review-status branch inside the same `validation_rejected` terminal summary; v1 defines no clean-validation skip. [VERIFIED: Phase 3 architecture reset] |
| Reviewer refusal | present and frozen | present/clean | present with refusal outcome and response telemetry; verdict/confidence absent | `reviewer_refusal` [VERIFIED: Phase 3 architecture reset] |
| Reviewer incomplete | present and frozen | present/clean | present with incomplete outcome and response telemetry; verdict/confidence absent | `reviewer_incomplete` [VERIFIED: Phase 3 architecture reset] |
| Reviewer schema failure | present and frozen | present/clean | present with schema-failure outcome and sanitized telemetry; verdict/confidence absent | `reviewer_schema_failure` [VERIFIED: Phase 3 architecture reset] |
| Reviewer `NO` | present and frozen | present/clean | present with `NO`, confidence, reasons, and telemetry | `review_rejected` [VERIFIED: REV-03] |
| Reviewer `YES`, confidence `<0.80` | present and frozen | present/clean | present with `YES`, confidence, reasons, and telemetry | `review_low_confidence` [VERIFIED: REV-03] |
| Reviewer `YES`, confidence `>=0.80` | present and frozen | present/clean | present with `YES`, confidence, reasons, and telemetry | `eligible_local_candidate` [VERIFIED: REV-03] |

Every completed branch stores canonical terminal-summary bytes. An exact `CandidateExecutionAuthorityV1` completed lookup returns/reprojects those exact bytes and, only when present, the exact frozen package/validation/attestation bytes. Reuse performs zero Generator/Reviewer/validator calls and appends zero runs, attempts, events, or summary rows. Package, ValidationReport, and ReviewAttestation fields are optional by schema and materialized only for branches where the table marks them present. [VERIFIED: Phase 3 architecture reset]

## State of the Art

| Old Approach | Current Approach | When Changed / Observed | Impact |
|--------------|------------------|-------------------------|--------|
| Private/ad hoc Skill layout | Open Agent Skills directory with `SKILL.md`, optional resources, and progressive disclosure | Current official spec inspected 2026-07-22 | Generate the standard directly and keep `SKILL.md` concise. [CITED: https://agentskills.io/specification] |
| Free-text model output then parsing | Strict JSON Schema / Pydantic Structured Outputs | Current OpenAI guidance inspected 2026-07-22 | Generator and Reviewer failures are typed, not parser heuristics. [CITED: https://developers.openai.com/api/docs/guides/structured-outputs] |
| Assuming an official validator is production-complete | Use official reference as one versioned signal plus project checks | Official repository currently labels `skills-ref` demonstration-only | VAL-01/02 need a layered validator. [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref] |
| CLI-only validator integration | Python `validate(Path) -> list[str]` API | Present in official main and PyPI docs | Avoid subprocess authority and brittle prose parsing. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py] |
| Replaying an upstream pipeline as a downstream prefix | Strict descriptor + verified read-only upstream state/query seam | Phase 3 architecture reset, 2026-07-23 | Preserves producer boundaries, avoids repeat API/model work, and makes pre-run source failure distinct from Phase 3 terminal outcomes. [VERIFIED: Phase 3 architecture reset] |

**Deprecated/outdated:**

- The PyPI 0.1.1 description shows `agentskills validate`, while the current official repository and specification show `skills-ref validate`. Do not make either executable name the application contract; import the library and record the installed version. [CITED: https://pypi.org/project/skills-ref/] [CITED: https://github.com/agentskills/agentskills/tree/main/skills-ref]
- The official repository's `pyproject.toml` still declares 0.1.0 while PyPI has 0.1.1. Exact distribution and source provenance must be confirmed during the human gate. [CITED: https://github.com/agentskills/agentskills/blob/main/skills-ref/pyproject.toml] [CITED: https://pypi.org/project/skills-ref/]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact qualification weights, confidence hard floor `0.70`, and hard-fail vocabulary | Qualification | False positives/negatives or product-policy disagreement; lock in a versioned fixture evaluation before implementation |
| A2 | Quote caps of 120 characters each / 240 total and unregistered-match threshold of 80 | Validation | Too strict for useful attribution or too permissive for copying; these are policy, not legal safe harbors |
| A6 | `references/provenance.json` is the best machine-readable location | Generation | Catalog conventions may prefer a root manifest; no catalog layout decision exists yet |
| A7 | `allowed-tools` must be omitted rather than left empty | Generation | A future client/catalog may require it, but current spec marks it experimental and omission is safer |

**Resolved former assumptions:** A3 (title/path-derived lineage heuristic) is replaced by authority-bound lineage; A4 (full-prefix Phase 3 replay) is superseded by a separate descriptor/query boundary over verified Phase 2 state; and A5 (per-workflow request unit) is replaced by mandatory isolated descriptors with no cross-workflow batch authority. These are authoritative planning constraints, not remaining assumptions. [VERIFIED: Phase 3 architecture reset]

## Resolved Questions

1. **Multi-workflow selection and isolation**
   - Resolution: outside Phase 3 run creation, derive strict `CandidateSubjectDescriptorV1` values from an already completed Phase 2 run by sorting full workflow fingerprints and capping at three. Each descriptor selects one complete WorkflowSpec and creates an independent Phase 3 authority, ledger, Generator call, Reviewer call, retry history, terminal summary, and optional package. No cross-workflow batch authority exists. [VERIFIED: Phase 3 architecture reset]
   - Planning consequence: implement descriptor derivation/loading separately from Phase 3 orchestration and test ordering/cap, one-workflow boundaries, sibling isolation, and exact per-candidate calls/outcomes. [VERIFIED: Phase 3 architecture reset]

2. **Phase 3 input and Phase 2 state boundary**
   - Resolution: a separate bounded safe loader reads `CandidateSubjectDescriptorV1`; existing `RepositorySubject` and `load_subject` remain unchanged. Before Phase 3 lookup, a read-only state seam verifies the referenced completed Phase 2 chain/output anchor, finds exactly one selected fingerprint, parses the complete WorkflowSpec, and recomputes `WorkflowSpecAuthorityV1`. Any upstream rejection/no-workflow/refusal/incomplete/schema failure or any descriptor/chain/fingerprint/digest mismatch yields sanitized pre-run `candidate_source_unavailable`, with no Phase 3 ledger and zero Generator/Reviewer/validator calls. [VERIFIED: Phase 3 architecture reset]
   - Planning consequence: implement `PhaseTwoCandidateSource.resolve()` and pre-run error mapping before Phase 3 storage/orchestration tasks; test every unavailable source case and assert zero rows/events/calls. [VERIFIED: Phase 3 architecture reset]

3. **Cross-commit lineage and update binding**
   - Resolution: fingerprint is version identity, never lineage. New lineage is repository ID plus the initial complete WorkflowSpec authority. Retention requires one exact approved `PriorLineageBindingV1` from the prior lineage/package/terminal summary to the new WorkflowSpec authority; no binding creates a new lineage. Stale, colliding, multiple, mismatched, or ambiguous mappings stop for human review. Approved mappings retain lineage/slug despite title/evidence-path changes; title/path are never matching authority. [VERIFIED: Phase 3 architecture reset]
   - Planning consequence: persist the binding and approval digest, model `LineageResolutionV1` as terminal evidence, and test new/exact/stale/tampered/colliding/multiple/ambiguous cases without implementing Phase 4 publication. [VERIFIED: Phase 3 architecture reset]

4. **Layered execution, package, review, and reuse authority**
   - Resolution: `CandidateExecutionAuthorityV1` contains only knowable pre-lookup authority, including configured model IDs and immutable `RENDERER_VERSION`/`ELIGIBILITY_POLICY_VERSION`; actual model IDs are later terminal evidence. `GeneratedArtifactIdentityV1` and the external package digest are finalized after generation, package bytes freeze before validation, `ReviewAttestationV1` remains external, and `CandidateTerminalSummaryV1` binds every owned terminal branch. Exact completed reuse returns the exact terminal and optional artifact/report/attestation bytes with zero new calls/rows/events. [VERIFIED: Phase 3 architecture reset]
   - Planning consequence: define all five authority/identity contracts with canonical digest functions and optional fields by branch; test each configured/version invalidation, actual-model evidence placement, package immutability, forbidden future provenance fields, and exact byte-for-byte terminal reuse. [VERIFIED: Phase 3 architecture reset]

5. **Official `skills-ref` dependency authority**
   - Resolution: dependency Gate A3 (exact distribution/source provenance and wheel hash) and Gate B3 (exact transitive lock graph/hash approval) are blocking prerequisites. If either gate rejects `skills-ref`, its provenance, or its resolved lock graph, Phase 3 stops. No local parser, copied validator logic, CLI emulation, or custom checker may be presented as satisfying official-validator requirement VAL-01. [VERIFIED: Phase 3 planning resolution and VAL-01]
   - Planning consequence: put A3/B3 before implementation tasks that import or lock `skills-ref`; record the approved distribution and lock authority; test missing/unapproved/version-mismatched validator as a blocking error. SkillScout custom validators remain additional VAL-01/02 controls, never a substitute. [VERIFIED: Phase 3 planning resolution]

### Resolution Impact on Planning

Required contracts: `CandidateSubjectDescriptorV1`, `WorkflowSpecAuthorityV1`, `PriorLineageBindingV1`, `LineageResolutionV1`, pre-lookup `CandidateExecutionAuthorityV1`, `GeneratedArtifactIdentityV1`, frozen package manifest/digest, `ValidationReport`, external `ReviewAttestationV1`, and external `CandidateTerminalSummaryV1`. Required immutable constants: `RENDERER_VERSION` and `ELIGIBILITY_POLICY_VERSION`. Required seams: separate safe descriptor loader, read-only `PhaseTwoCandidateSource` verified-chain query, profile-relative Phase 3 ledger verification rooted in execution authority, Phase 3 authority lookup, exact terminal-byte projector, and exact OpenAI import allowlist of `adapters/openai_extract.py`, `adapters/openai_generate.py`, `adapters/openai_review.py`. [VERIFIED: Phase 3 architecture reset]

Required tests: descriptor limits and existing-loader non-regression; all `candidate_source_unavailable` cases with no ledger/calls; complete WorkflowSpec digest sensitivity for every field/evidence/anchor; deterministic descriptor ordering/cap and sibling isolation; lineage binding cases; pre-lookup authority invalidation for every configured/version field; actual model evidence placement; frozen-package and no-future-provenance invariants; every Phase 3 terminal branch; exact completed reprojection with zero calls/rows/events; package optionality; A3/B3 blocking; and exact OpenAI import allowlist enforcement. [VERIFIED: Phase 3 architecture reset]

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
| `SKILLSCOUT_GITHUB_TOKEN` | Phase 2 descriptor production only; not Phase 3 execution | ✗ | — | Phase 3 resolves already persisted verified Phase 2 state and must make zero GitHub calls. [VERIFIED: Phase 3 architecture reset and presence-only environment probe] |

**Missing dependencies with no fallback:** approved/pinned `skills-ref` for VAL-01. [VERIFIED: local probe and VAL-01]

**Missing dependencies with fallback:** OpenAI credentials are absent, but recorded transports are the required default for Generator/Reviewer tests. GitHub credentials are not a Phase 3 dependency because candidate-source resolution is local and read-only. [VERIFIED: existing test architecture and Phase 3 architecture reset]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 [VERIFIED: local environment] |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`, strict config/markers) [VERIFIED: codebase inspection] |
| Quick run command | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_candidate_source.py tests/test_candidate_authority.py tests/test_qualification.py tests/test_skill_generation.py tests/test_skill_validation.py tests/test_openai_review.py` [ASSUMED] |
| Full suite command | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` [VERIFIED: established project gate] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUAL-01/02 | 100-point rules, hard failures, stable ordering/version, 75 boundary | unit/property matrix | `... pytest -q tests/test_qualification.py` | ❌ Wave 0 |
| GEN-01/02 | deterministic standard package; closed paths/types/modes; no scripts/binaries | unit + filesystem adversarial | `... pytest -q tests/test_skill_generation.py` | ❌ Wave 0 |
| GEN-03/04 | paraphrase/quote limits and exact provenance bindings | unit + fixture | `... pytest -q tests/test_skill_generation.py tests/test_skill_validation.py` | ❌ Wave 0 |
| GEN-05 | complete WorkflowSpec authority, pre-lookup execution authority, durable lineage, frozen package identity, external attestation/summary, and exact reuse | unit + integration | `... pytest -q tests/test_candidate_authority.py tests/test_skill_generation.py tests/test_phase3_pipeline.py` | ❌ Wave 0 |
| VAL-01 | pinned official validator plus custom structure/progressive disclosure | integration | `... pytest -q tests/test_skill_validation.py -k 'official or structure'` | ❌ Wave 0 |
| VAL-02/03 | all security/source/over-copy checks; severity/count/gate coherence | adversarial parameter matrix | `... pytest -q tests/test_skill_validation.py` | ❌ Wave 0 |
| REV-01/02 | isolated request shape, four inputs only, no files in output schema | adapter contract | `... pytest -q tests/test_openai_review.py` | ❌ Wave 0 |
| REV-03 | clean+YES+0.80 boundary; NO/0.799/error skips | unit + integration | `... pytest -q tests/test_openai_review.py tests/test_phase3_pipeline.py` | ❌ Wave 0 |
| Input boundary | strict descriptor loader, verified Phase 2 query, every sanitized pre-run unavailable case, no ledger/calls | contract + integration | `... pytest -q tests/test_candidate_source.py` | ❌ Wave 0 |
| All | every owned terminal branch, resume, byte-exact zero-side-effect completed reuse, optional package/report/attestation fields | E2E recorded transports | `... pytest -q tests/test_cli_validate_skill.py tests/test_phase3_pipeline.py` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** run the narrow module(s) named in that task plus Ruff on touched source/tests. [ASSUMED]
- **Per wave merge:** `.tools/uv-0.11.29/bin/uv run --locked pytest -q` and `.tools/uv-0.11.29/bin/uv run --locked ruff check .`. [VERIFIED: project practice]
- **Phase gate:** `uv lock --check`, build without sources, Ruff, full pytest, source-wide forbidden-capability scan, artifact secret scan, and package-lock hash equality to the human-approved Phase 3 lock. [VERIFIED: existing gate pattern; ASSUMED for new lock authority]

### Wave 0 Gaps

- [ ] Blocking Gate A3 for exact `skills-ref==0.1.1` distribution/source/wheel provenance and Gate B3 for the exact transitive lock graph/hashes. [VERIFIED: Phase 3 planning resolution and package audit]
- [ ] `tests/test_candidate_source.py` for strict bounded descriptor loading, unchanged `RepositorySubject`/`load_subject`, completed Phase 2 chain/output verification, complete selected WorkflowSpec recovery, and every `candidate_source_unavailable` path with zero Phase 3 rows/calls. [VERIFIED: Phase 3 architecture reset]
- [ ] `tests/test_candidate_authority.py` for complete WorkflowSpec field/evidence/anchor digest sensitivity; all pre-lookup authority fields; immutable renderer/eligibility versions; configured-model invalidation; actual-model terminal placement; and canonical digest stability. [VERIFIED: Phase 3 architecture reset]
- [ ] `tests/test_qualification.py` and score/hard-fail fixtures for 74/75/76, confidence 0.699/0.700, two-step hard fail, source-execution hard fail, and valid evidence. [ASSUMED]
- [ ] `tests/test_skill_generation.py` with deterministic render, authority-bound provenance containing Generator but no future Reviewer/validation facts, byte freeze, external package digest, slug collision, permissions, no scripts/binaries, and quote limits. [VERIFIED: Phase 3 architecture reset; ASSUMED for quote thresholds]
- [ ] `tests/test_skill_validation.py` with valid official fixture plus missing frontmatter, name mismatch, broken/deep/orphan reference, symlink, hard link/TOCTOU seam, mode `0755`, binary, secret, injection, URL, download-execute, missing provenance, hash mismatch, and over-copy cases. [ASSUMED]
- [ ] `tests/test_openai_generate.py` and recorded parsed/refusal/incomplete/schema-invalid/429/500 responses. [ASSUMED]
- [ ] `tests/test_openai_review.py` and recorded YES, NO, 0.799, 0.800, refusal, incomplete, schema-invalid, 429, and 500 responses. [ASSUMED]
- [ ] `tests/test_phase3_pipeline.py` for a profile-relative `(QUALIFIER, GENERATOR, VALIDATOR, REVIEWER)` chain rooted in execution authority; unchanged Phase 2 prefix verification; no fake/imported upstream rows; isolated descriptors; lineage results; all terminal branches; retry; exact completed-summary/package/report/attestation reprojection; zero new calls/validators/rows/events; and reuse invalidation across every configured model and authority version. [VERIFIED: Phase 3 architecture reset]
- [ ] `tests/test_lineage.py` for new lineage, exact durable binding, title/evidence-path changes with approved binding, no-binding new lineage, stale/tampered binding, repository mismatch, collision, multiple matches, and ambiguous remap. [VERIFIED: Phase 3 planning resolution]
- [ ] `tests/test_cli_validate_skill.py` for pre-run source-unavailable diagnostics, every Phase 3 terminal branch, exact OpenAI call counts, zero GitHub calls, zero remote writes, and optional package materialization. [VERIFIED: Phase 3 architecture reset]
- [ ] Final capability-scan test accepting OpenAI imports only in `adapters/openai_extract.py`, `adapters/openai_generate.py`, and `adapters/openai_review.py`. [VERIFIED: Phase 3 architecture reset]
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
| Descriptor selects unverified/tampered Phase 2 output | Spoofing / Tampering | Separate bounded loader plus read-only completed-chain/output-anchor verification and complete WorkflowSpec authority digest before any Phase 3 ledger lookup. [VERIFIED: Phase 3 architecture reset] |
| Generated prompt injection manipulates Reviewer | Spoofing / Tampering | Four-section inert-data envelope, separate developer instructions, no tools, strict response schema, deterministic final gate, injection corpus. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html] |
| Path traversal, symlink swap, executable mode | Tampering / Elevation of Privilege | Closed relative paths, descriptor-anchored materialization, identity recheck, retained lock, exact `0644`, no scripts/binaries. [VERIFIED: existing localfs patterns; ASSUMED for artifact writer] |
| Secret-like model output reaches artifact/report | Information Disclosure | Pre-render and post-render scans; canaries; report pattern IDs only; credentials header-only. [CITED: https://docs.github.com/en/code-security/reference/secret-security/supported-secret-scanning-patterns] |
| Validator failure is treated as pass | Tampering | Exception -> structured `error`; every error blocks Reviewer/Publisher. [VERIFIED: VAL-03] |
| Artifact changes after validation/review | Tampering | Freeze generation-time package bytes, keep package digest external, bind validation and ReviewAttestation to that digest, and let Phase 4 consume only the matching terminal summary. [VERIFIED: Phase 3 architecture reset] |
| Slug collision or stale binding aliases another workflow | Spoofing | Lineage from repo ID + initial complete WorkflowSpec authority; exact approved prior package-to-new-authority binding; collision/multiple/stale/ambiguous mapping fails closed. [VERIFIED: Phase 3 architecture reset] |
| Oversized model/package output exhausts resources | Denial of Service | Pydantic collection/string caps, bounded output tokens, package/file/line/token caps, manifest ceiling. [VERIFIED: existing bounded contract pattern; ASSUMED for Phase 3 cap values] |
| Repeated calls seek a favorable review | Repudiation / Business Logic | Every branch has immutable terminal bytes; exact execution-authority reuse reprojects them with zero new calls/rows/events; only infrastructure failures retry. [VERIFIED: established retry pattern and Phase 3 architecture reset] |

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

- None used as factual authority. Remaining project-specific thresholds and layout choices are explicitly tagged `[ASSUMED]` and listed in the Assumptions Log.

## Metadata

**Confidence breakdown:**

- Standard stack: MEDIUM — existing pins are verified; new `skills-ref` is official-spec-linked but the legitimacy seam returned `SUS`, source/PyPI versions differ, and human lock approval is required.
- Architecture: HIGH — the authoritative reset preserves verified Phase 2 state behind a strict descriptor/read-only query seam and defines pre-run, pre-lookup, generation, review, terminal, and reuse authorities without replaying the upstream pipeline.
- Qualification policy: LOW — requirement dimensions and threshold are locked, but weights, confidence floor, and hard-fail vocabulary are project choices needing fixture evaluation.
- Validation patterns: MEDIUM — control families come from requirements and official security guidance; exact quote and size thresholds are policy assumptions.
- Reviewer integration: HIGH — it directly reuses the verified Extractor adapter shape and current official Structured Outputs behavior.
- Identity/lineage: HIGH — the planning authority now explicitly separates fingerprint version identity from durable lineage binding and defines every fail-closed mapping outcome; implementation and adversarial tests remain Wave 0 work.

**Research date:** 2026-07-23

**Valid until:** 2026-07-30 for `skills-ref`/OpenAI package details; 2026-08-22 for stable internal architecture and Agent Skills format findings.
