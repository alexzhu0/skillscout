# Phase 6: Adversarial MVP Acceptance - Research

**Researched:** 2026-07-28
**Domain:** Evidence-backed adversarial acceptance, closed semantic-provider policy, least-privilege Draft publication, and deterministic release reporting
**Confidence:** HIGH for repository architecture and deterministic verification; MEDIUM for live campaign outcomes pending benchmark lock and authorized hosted runs

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Fixed real-repository benchmark and nominations
- **D-01:** Build the formal five-repository benchmark from candidates produced by SkillScout's real GitHub Search and deterministic filtering path, then require a human to lock the benchmark manifest before the acceptance run.
- **D-02:** Each locked benchmark entry must include the full repository name, immutable GitHub repository identity, commit SHA, detected/confirmed permissive license, selection source, intended coverage role, and the evidence needed to reproduce the selection.
- **D-03:** Use a deliberately mixed benchmark: two plausible positive repositories, including at least one multi-workflow repository; two expected negative repositories; and one borderline repository. Pre-run labels are evaluator hypotheses, not instructions that force a semantic result.
- **D-04:** Prompt Injection and supply-chain attacks use controlled adversarial fixtures in addition to the five real repositories; acceptance must not depend on a public repository coincidentally containing a suitable attack.
- **D-05:** Human-nominated public repositories are allowed as supplemental candidates when they pass the same license, fixed-SHA, read-only, budget, and safety rules. Record them as `selection_source=user_nominated`; they do not silently replace the formal benchmark.
- **D-06:** Promoting a nominated repository into the formal benchmark requires an explicit benchmark-manifest revision and rerunning every affected evidence item.

### DeepSeek-only live semantic campaign
- **D-07:** Phase 6 live acceptance requires only the existing DeepSeek credential. A live OpenAI credential and live OpenAI run are not release blockers; the OpenAI provider path remains covered by deterministic recorded/mocked tests and is disclosed as a non-blocking limitation.
- **D-08:** Use `deepseek-v4-flash` for extraction and Skill generation, and `deepseek-v4-pro` for the independent final Reviewer. The Reviewer remains a separate request and context, receives no raw repository corpus, and has no editing or publication authority.
- **D-09:** The model policy is closed and stage-specific: only the exact approved DeepSeek model identifiers and official base URL are admitted. Arbitrary model names and arbitrary OpenAI-compatible endpoints remain forbidden.
- **D-10:** The current all-Flash DeepSeek profile must be revised through a bounded, tested provider-policy change so the final Reviewer can use Pro without turning model selection into an unrestricted runtime escape hatch.

### Hard-gated acceptance verdict
- **D-11:** Overall `PASS` requires every blocking safety, permission, idempotency, provenance, license, scenario-coverage, evidence-integrity, and report-rebuild gate to pass, plus at least one real Draft PR that completes human content review.
- **D-12:** Deterministic filtering, no reusable workflow, qualification low score, deterministic format/security rejection, and independent Reviewer rejection are valid fail-closed business outcomes when they terminate at the correct boundary with a complete structured reason.
- **D-13:** Provider/schema exhaustion, missing or broken evidence, duplicate WorkflowSpecs/Skills/branches/PRs, unauthorized effects, secret exposure, untrusted code execution, acceptance-harness failure, or an unrebuildable report are system failures and block release credit.
- **D-14:** Non-security warnings may accompany `PASS` only when their impact and follow-up are explicit. Examples include model-quality variability, latency, cost, and the absence of a live OpenAI-provider run.
- **D-15:** Security, permission, idempotency, license, provenance, human-review, or real-Draft evidence cannot be waived by an aggregate score or an unstructured human override.
- **D-16:** At least one real Draft PR must receive an explicit human verdict of `publishable` or `publishable_with_changes`. Creation alone is insufficient; a rejected PR is useful negative evidence but does not satisfy the positive value gate.
- **D-17:** The human Skill review checks usefulness, fidelity to cited source material, repository/SHA/license/attribution, instruction safety, and the PR diff's scope. The human may merge, request changes, or close later; Phase 6 never requires or performs a merge.

### Controlled Draft PR lifecycle
- **D-18:** Publish Phase 6 real Skill Drafts only to `alexzhu0/skillscout-catalog-test` using the already bounded GitHub App installation and protected catalog controls. Runtime selection of arbitrary publication repositories is forbidden.
- **D-19:** Keep a successful Skill PR open and in Draft state until a human records `publishable`, `publishable_with_changes`, or `rejected`. SkillScout must never approve, merge, or mark it ready for review.
- **D-20:** Keep value-bearing Skill PRs separate from canary/probe PRs. A separate human administrator closes probe PRs, deletes probe branches, and signs the cleanup attestation; the automation identity receives no cleanup authority that weakens the tested boundary.
- **D-21:** For the same repository/workflow/policy lineage, a changed source SHA updates the corresponding open Draft rather than creating a duplicate. Preserve old-to-new SHA lineage and the reevaluation evidence. If the previous PR is already closed or merged, a new Draft may be created with an explicit link to the prior lineage.

### Fresh canary and durable evidence
- **D-22:** Run a fresh Gate B4 canary immediately before granting Phase 6 live-publication credit. Bind it to the exact discover, publish, and canary workflow bytes plus the current App installation, catalog, ruleset, protected environment, reviewer configuration, and installation identity.
- **D-23:** Any change to a bound workflow byte, App scope/installation, catalog, ruleset, environment, reviewer configuration, or installation identity invalidates the canary evidence and requires a new run.
- **D-24:** The adversarial campaign covers every existing Prompt Injection fixture and adds deterministic denial evidence for shell, subprocess, dynamic import, source-code execution, and outbound network paths outside explicitly approved GitHub and DeepSeek adapters. Close the previously deferred Phase 1 `os_syscall_network_denial` evidence gap here.
- **D-25:** Secret-leakage evidence uses synthetic canary values and scans sanitized logs, durable state, reports, Actions artifacts, and PR diffs. Tests and reports must never open, copy, print, or persist real `.env`, PEM, JWT, token, private-key, or credential values.
- **D-26:** Keep the concise Phase 6 acceptance and 44-requirement release report on the main project branch. Store durable, redacted, content-addressed structured evidence on the canonical state branch. Raw diagnostic output may exist only as a bounded-retention Actions artifact and is never canonical state.
- **D-27:** The final report must identify benchmark manifest/version, fixed SHAs, funnel counts, reader budgets, token/latency telemetry, per-stage outcomes, expected-vs-observed labels, idempotency/update results, canary bindings, human review result, warnings, known limitations, and a deterministic release recommendation.

### the agent's Discretion
- Research and planning may choose the exact five repository names and SHAs, provided they satisfy the locked benchmark distribution and are human-locked before release evidence is collected.
- Research and planning may choose the internal acceptance-report schema decomposition, file names, command surface, and test organization while preserving structured outputs, deterministic verdict rules, redaction, rebuildability, and the persistence boundary above.
- Research and planning may set bounded latency/cost presentation thresholds and artifact-retention duration; these cannot weaken hard safety, authority, or evidence-integrity gates.

### Deferred Ideas (OUT OF SCOPE)
- A live OpenAI-provider acceptance campaign is optional follow-up work and does not block the DeepSeek-backed v1 acceptance.
- Arbitrary provider/model configuration, private repositories, generated scripts, automated Reviewer-driven rewriting, a Web review queue, and publication to a public Skill marketplace remain outside Phase 6 and the v1 boundary.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEST-01 | 系统使用至少 5 个固定到 commit SHA 的真实公共仓库完成 Search 到发布决策的端到端验收。 | Use a two-step real-search nomination and human-lock flow, then re-admit the immutable manifest through the production discovery coordinator and verify its canonical evidence graph. [VERIFIED: `.planning/REQUIREMENTS.md`, codebase grep] |
| TEST-02 | 验收集至少覆盖成功生成、确定性过滤、资格低分、格式/安全失败、Reviewer 拒绝和多种 Prompt Injection 输入。 | Combine the mixed five-repository live benchmark with controlled adversarial/rejection fixtures, preserving structured business-terminal reasons and keeping evaluator hypotheses outside model requests. [VERIFIED: `.planning/REQUIREMENTS.md`, codebase grep] |
| TEST-03 | 相同 repo、commit SHA、workflow fingerprint 和政策版本重复运行时，不得重复生成 WorkflowSpec、Skill、发布分支或 Draft PR；相关来源变化必须触发重新评估并更新既有 Draft。 | Compare canonical authority, package, publication, and remote-effect evidence across an identical replay, then exercise the existing explicit prior-lineage binding path for a changed-SHA update to the same open Draft. [VERIFIED: `src/skillscout/application/publication.py`, codebase grep] |
| TEST-04 | MVP 必须至少创建一个需要人类审核的真实 Draft PR，并实测自动化身份无法 push 默认分支、merge、批准或读取未授权密钥。 | Reuse the fresh Gate B4 canary for causal permission denials, publish only after its bindings validate, and add an exact-head human content-review attestation whose positive verdict is required for release credit. [VERIFIED: `tools/gate_b4_canary.py`, codebase grep] |
</phase_requirements>

## Summary

Phase 6 should be planned as an evidence campaign built on the production pipeline, not as a parallel demonstration script. The existing system already has the essential deterministic boundaries: fixed-SHA GitHub reads, strict versioned stage facts, content-addressed persistence, structured terminal outcomes, independent semantic requests, idempotent Draft creation/update, and a causal least-privilege canary. The missing work is orchestration and proof: a real-search nomination lane with a human-locked benchmark manifest, a closed Flash/Flash/Pro DeepSeek policy, whole-product acceptance facts and hard gates, explicit human Skill-review evidence, process-level network denial, and a deterministic report/rebuilder. [VERIFIED: `src/skillscout/application/discovery.py`, `src/skillscout/application/publication.py`, `tools/gate_b4_canary.py`, codebase grep]

The acceptance verdict must be a conjunction of named gates. Valid fail-closed business outcomes count toward scenario coverage, whereas provider/schema exhaustion, missing evidence, duplicate side effects, secret exposure, untrusted execution, stale canary authority, or report mismatch are release-blocking system failures. Expected benchmark labels belong only to the evaluator and must never be added to extraction, generation, or review input. The five real repositories establish product realism; controlled fixtures establish deterministic adversarial and rejection coverage. [VERIFIED: `06-CONTEXT.md`, codebase grep]

The live sequence is necessarily checkpointed: nominate through real Search, lock the five-entry manifest, run and replay the campaign, explicitly authorize one changed-lineage update, run a fresh Gate B4 canary, publish a value-bearing Draft, obtain an exact-head human verdict, and rebuild the report independently. The current repository tests relevant to this surface are healthy: a focused locked run of semantic-provider, Phase 5 acceptance, Gate B4, and live-canary contract tests completed with `192 passed, 2 skipped`; the skips are live-only paths. [VERIFIED: locked pytest run, 2026-07-28]

**Primary recommendation:** Add a strict acceptance domain and two-step `nominate-benchmark` / `run-acceptance` command surface that composes existing production coordinators, persists redacted canonical facts in the existing state boundary, and emits a hard-gated, independently rebuildable Phase 6 report.

### Final planning contract clarification

TEST-03 needs two immutable evidence scopes rather than one mutable replay/update record. `ReplayEvidenceV1` and `ChangedSourceEvidenceV1` remain pre-publication semantic intent/evidence. Post-effect authority is recorded separately as strict `PublicationReplayCompletionV1` (`publication-replay-completion-v1`, kind `acceptance_publication_replay_completion`) and `ChangedSourceDraftUpdateCompletionV1` (`changed-source-draft-update-completion-v1`, kind `acceptance_changed_source_draft_update_completion`). The completion facts bind their exact intent digests, fixed source/policy/fingerprint authorities, publication key/marker/target/PR/head, remote observations/effect counts, and—on update—previous/new source, authority, revision, head, and lineage. Their model-specific natural identities allow intent and completion to coexist while still rejecting changed bytes for one completion identity. Report credit requires independent typed export/rebuild of both completion facts; planned lineage or mutable publication state is insufficient.

Fresh Gate B4 must also be preceded by one closed source-execution proof over exactly four workflows: `.github/workflows/discover.yml`, `.github/workflows/publish-candidate.yml`, `.github/workflows/gate-b4-canary.yml`, and `.github/workflows/phase6-acceptance.yml`. Every authoritative SkillScout import/entry point must follow same-job full-SHA checkout, pinned uv 0.11.29 setup/materialization, and direct repository-local `.tools/uv-0.11.29/bin/uv run --locked` execution from checkout root. Wheel/dist/registry/pip/uvx/uv-tool/uv-with/bare/preinstalled/artifact/download/wrapper/alias/function/variable/indirect/external-working-directory/unknown routes, empty scans, and an execution-source selector fail closed. The verifier and mutation contract are implemented before Plan 06-10; Plan 06-10 binds all four corrected workflow hashes, and later work only reads those bytes. The Phase 6 wheel remains later release-document evidence and is never an authoritative workflow execution input.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Benchmark nomination and immutable manifest | API / Backend | Database / Storage | The application owns real Search admission and human-lock state; the canonical manifest and digest belong in durable state. [VERIFIED: `src/skillscout/application/discovery.py`, codebase grep] |
| Fixed-SHA repository reads and license evidence | API / Backend | External GitHub REST | The existing GitHub adapter performs bounded read-only Contents/Search/License access without cloning or executing source code. [VERIFIED: `src/skillscout/adapters/github.py`, codebase grep] |
| Flash extraction and generation | API / Backend | External DeepSeek API | Semantic calls are backend adapters with strict local output validation and no tool authority. [VERIFIED: `src/skillscout/adapters/semantic_provider.py`, codebase grep] |
| Pro independent review | API / Backend | External DeepSeek API | Reviewer isolation is a separate request and authority; it consumes generated evidence rather than raw corpus and cannot edit or publish. [VERIFIED: `src/skillscout/adapters/openai_review.py`, codebase grep] |
| Scenario verdicts and release gates | API / Backend | Database / Storage | Deterministic policy must classify terminal business outcomes, system failures, and the all-gates verdict from canonical facts. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| Acceptance evidence persistence | Database / Storage | Git state branch | Existing pipeline, operations, and publication stores are the canonical three-store boundary; evidence exports are content-addressed facts rather than logs. [VERIFIED: `src/skillscout/adapters/operations_state.py`, codebase grep] |
| Gate B4 permission proof | API / Backend | GitHub platform controls | The canary performs positive Draft/reviewer actions and causal negative probes against external App, ruleset, environment, and installation authority. [VERIFIED: `tools/gate_b4_canary.py`, codebase grep] |
| Value Draft publication and update | API / Backend | External GitHub REST | Publication owns stable keys, desired revisions, create/reuse/update behavior, and forbidden-action limits. [VERIFIED: `src/skillscout/application/publication.py`, codebase grep] |
| Human Skill content verdict | Human / GitHub UI boundary | API / Backend | A human inspects the exact Draft head; SkillScout only ingests and verifies an attestation and does not approve, merge, or mark ready. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| Concise acceptance/release report | CDN / Static repository artifact | API / Backend | The report is reviewable on the main branch but must be generated and independently rebuilt from verified structured evidence. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| OS/syscall outbound-network denial | CI runner / Kernel | API / Backend tests | Kernel or network-namespace enforcement must prove denial below Python socket monkeypatching while application tests verify the only approved live adapters. [VERIFIED: `tools/verify_phase1_gap_evidence.py`, codebase grep] |

## Project Constraints (from AGENTS.md)

- Treat every external repository byte as untrusted data; it cannot become an instruction, tool call, or execution authorization. [VERIFIED: `AGENTS.md`, codebase grep]
- Do not clone and run repositories, install their dependencies, invoke their scripts, generate executable `scripts/`, or execute source content. [VERIFIED: `AGENTS.md`, codebase grep]
- Automation stops at Draft PR creation/update and may never merge, approve, publish, mark ready, or write the protected default branch. [VERIFIED: `AGENTS.md`, codebase grep]
- Process only clearly identified permissive licenses and preserve source, commit SHA, license, and attribution through every downstream artifact. [VERIFIED: `AGENTS.md`, codebase grep]
- Inject GitHub and DeepSeek credentials only at the latest runtime boundary with minimum permission; never place secret values in logs, state, prompts, fixtures, reports, artifacts, or PRs. Do not read repository `.env`, PEM, JWT, token, private-key, or credential material. [VERIFIED: `AGENTS.md`, codebase grep]
- Keep Search filtering, budgets, content limits, validation, security rules, idempotency, and publication permissions deterministic; the LLM performs semantic extraction, generation, and review only. [VERIFIED: `AGENTS.md`, codebase grep]
- Keep stages isolated by strict versioned schemas and persistent structured facts; no implicit shared state. [VERIFIED: `AGENTS.md`, codebase grep]
- Preserve hard caps on candidates and semantic calls, and retain the public-GitHub plus central catalog v1 boundary. [VERIFIED: `AGENTS.md`, codebase grep]
- Use Python 3.13, locked `pyproject.toml` dependencies, GitHub REST through `httpx`, strict Pydantic contracts, SQLite plus versioned JSON facts, safe YAML, and official `skills-ref validate`. [VERIFIED: `AGENTS.md`, codebase grep]
- Keep DeepSeek opt-in at the exact official base URL, validate its JSON locally against the same strict Pydantic schemas, keep SDK retries disabled, and leave retry authority in deterministic pipeline policy. [VERIFIED: `AGENTS.md`, codebase grep]
- Run repository tests through `.tools/uv-0.11.29/bin/uv run --locked pytest -q`; use Ruff and mypy boundaries already established by the project. [VERIFIED: `AGENTS.md`, codebase grep]
- Work remains inside the active GSD Phase 6 planning workflow; do not make unrelated direct repository changes. [VERIFIED: `AGENTS.md`, codebase grep]

## Standard Stack

### Core

| Library / Surface | Version | Purpose | Why Standard |
|-------------------|---------|---------|--------------|
| Python | `>=3.13,<3.14`; local locked runtime `3.13.14` | Acceptance models, orchestration, inspectors, and CLI | This is the project runtime and is already installed through the locked toolchain. [VERIFIED: `pyproject.toml`, local version probe] |
| Pydantic | `2.13.4` | Frozen, extra-forbidden, versioned manifests, evidence facts, attestations, and verdicts | Reusing the cross-stage contract pattern keeps canonical JSON and validation behavior consistent. [VERIFIED: `pyproject.toml`, PyPI registry] |
| httpx | `0.28.1` | Existing bounded GitHub REST and provider HTTP boundary | The project already centralizes audited network access here; Phase 6 should not add another HTTP client. [VERIFIED: `pyproject.toml`, codebase grep] |
| DeepSeek Chat Completions compatibility path | exact official base URL; models `deepseek-v4-flash` and `deepseek-v4-pro` | Live extraction/generation and isolated final review | DeepSeek documents both exact model IDs and JSON-output support; the project must still perform strict local schema validation. [CITED: https://api-docs.deepseek.com/quick_start/pricing/?article_id=article_1779470751466_8] |
| SQLite `sqlite3` + content-addressed JSON | Python stdlib / schema-versioned | Transaction state plus rebuildable audit facts | Existing adapters already use three explicit state owners; acceptance should extend their facts rather than introduce a fourth competing database. [VERIFIED: `src/skillscout/adapters/operations_state.py`, codebase grep] |
| GitHub REST API | `X-GitHub-Api-Version: 2022-11-28` through existing adapters | Search, fixed-SHA Contents/License reads, Draft PRs, requested reviewers, and review reconciliation | GitHub documents Draft creation and fine-grained Pull Requests write permission; the existing adapter adds the project’s stricter allowlist. [CITED: https://docs.github.com/en/rest/pulls/pulls] |
| pytest | `9.1.1` | Unit, contract, mutation, adversarial, replay, and deterministic report tests | Existing suite and fixtures already exercise all phase boundaries and live-only separation. [VERIFIED: `pyproject.toml`, codebase grep] |

### Supporting

| Library / Surface | Version | Purpose | When to Use |
|-------------------|---------|---------|-------------|
| `skills-ref` | `0.1.1` | Official generated-Skill validation | Run before reviewer admission and again on exact PR bytes. [VERIFIED: `pyproject.toml`, codebase grep] |
| PyYAML | locked transitively/current project lock | Safe frontmatter serialization/validation | Use only the existing safe API or project serializer; never construct arbitrary Python objects. [VERIFIED: `AGENTS.md`, codebase grep] |
| Ruff | `0.15.21` | Static forbidden-import and style enforcement | Include in every Wave 0 and phase gate after acceptance code changes. [VERIFIED: `pyproject.toml`, local lock] |
| Existing Gate B4 canary | repository tool + protected workflow | Least-privilege live publication evidence | Run after all bound workflow/provider changes and immediately before publication credit. [VERIFIED: `tools/gate_b4_canary.py`, codebase grep] |
| Docker `--network none` on an ephemeral hosted Linux runner | hosted capability to verify in Wave 0 | Kernel-enforced offline adversarial test segment | Use only after the locked environment/image is prepared; the none driver isolates a container from networks except loopback. [CITED: https://docs.docker.com/engine/network/drivers/none/] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extend existing operations-owned canonical facts | Add a fourth acceptance SQLite database | A fourth database would widen recovery and reconciliation invariants without a new operational owner; preserve the established three-store boundary. [VERIFIED: codebase grep] |
| Typed stage-to-model policy | Runtime-configurable arbitrary model strings | Arbitrary strings violate D-09 and make an OpenAI-compatible endpoint/model escape possible; the stage policy must reject before HTTP. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| Controlled rejection fixtures plus real repositories | Rely only on five public repositories | Real repositories cannot deterministically guarantee prompt-injection, security-format, or reviewer-rejection coverage. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| Exact-head human attestation | Treat Draft creation or requested reviewer as human approval | Requested-reviewer state proves routing, not content judgment; GitHub removes a requested reviewer after review submission, so evidence must reconcile requests, reviews, and the exact PR head. [CITED: https://docs.github.com/en/rest/pulls/review-requests] |
| Kernel-enforced offline job plus application sentinels | Python socket monkeypatch alone | The existing sentinel cannot prove denial of non-Python syscalls or child-process network access, which is the explicit deferred Phase 1 gap. [VERIFIED: `tests/conftest.py`, `tools/verify_phase1_gap_evidence.py`, codebase grep] |

**Installation:** No new runtime package is required. Use the existing locked environment:

```bash
.tools/uv-0.11.29/bin/uv sync --locked
```

The phase should not install packages from candidate repositories or add a provider/agent framework. [VERIFIED: `AGENTS.md`, codebase grep]

**Version verification:** Core versions above were checked against `pyproject.toml`, the locked local environment, and the correct Python package registry on 2026-07-28. No external package is introduced by this phase, so the Package Legitimacy Gate and audit table are not applicable. [VERIFIED: `pyproject.toml`, local version probes, PyPI registry]

## Architecture Patterns

### System Architecture Diagram

```text
GitHub Search API
      |
      v
deterministic search/filter/pin -------- human nomination lane
      |                                         |
      +------------> nomination facts <---------+
                           |
                           v
                 human locks manifest digest
                           |
                  [manifest valid and ≥5?]
                     /                 \
                   no                   yes
                   |                     |
           blocking harness result       v
                               production discovery coordinator
                                         |
                +------------------------+------------------------+
                |                         |                       |
          structured negative      fixed-SHA bounded read    system failure
          terminal outcome                |                       |
                |                         v                       |
                |             Flash extract -> Flash generate     |
                |                         |                       |
                |                         v                       |
                |                   Pro reviewer                  |
                |                    /       \                    |
                |             reject         eligible             |
                +----------------+---------------+----------------+
                                 |
                                 v
                    canonical acceptance evidence
                    (existing state ownership)
                                 |
                +----------------+------------------+
                |                                   |
         offline adversarial gates           live publication lane
      fixtures + kernel network denial               |
                |                            fresh Gate B4 canary
                |                                   |
                |                         [bindings current?]
                |                            /            \
                |                          no              yes
                |                          |                |
                |                     block credit    value Draft PR
                |                                           |
                |                                  human exact-head review
                +---------------------+---------------------+
                                      |
                                      v
                           deterministic gate evaluator
                              [all hard gates pass?]
                                /               \
                              no                 yes
                              |                   |
                         FAIL / INCOMPLETE       PASS
                                \               /
                                 v             v
                       concise report + 44-requirement map
                                      |
                                      v
                           independent byte rebuild/check
```

This flow keeps expected labels and human authority outside semantic prompts, separates offline attacks from live adapters, and admits publication credit only after current canary evidence. [VERIFIED: `06-CONTEXT.md`, codebase grep]

### Recommended Project Structure

```text
src/skillscout/
├── domain/
│   └── acceptance.py              # Manifest, scenario, attestation, gate, and report facts
├── application/
│   └── acceptance.py              # Nomination, lock admission, campaign, and gate orchestration
├── adapters/
│   ├── semantic_provider.py       # Closed Flash/Flash/Pro policy
│   └── operations_state.py        # Acceptance projections/rebuild under existing owner
└── cli.py                         # nominate-benchmark / run-acceptance / rebuild-report
tools/
├── verify_phase6_acceptance.py    # Stdlib-only independent registry + mutation verifier
└── verify_phase6_validation_map.py
tests/
├── fixtures/acceptance/           # Controlled rejection/supply-chain facts; no executable source
├── test_acceptance_domain.py
├── test_acceptance_application.py
├── test_phase6_adversarial.py
├── test_phase6_acceptance.py
└── test_phase6_workflow.py
.planning/phases/06-adversarial-mvp-acceptance/
├── 06-BENCHMARK-MANIFEST.json     # Human-locked public identity/SHA hypotheses
├── 06-ACCEPTANCE-REPORT.md        # Concise reconstructed verdict
└── 06-RELEASE-REQUIREMENTS.json   # Exact 44-requirement evidence map
```

The exact filenames are discretionary, but canonical live evidence must stay redacted and content-addressed on `skillscout-state`; the main branch retains only the concise report, requirement map, and human-reviewable benchmark definition. [VERIFIED: `06-CONTEXT.md`, codebase grep]

### Pattern 1: Two-Step Nominate → Human Lock → Run

**What:** Search and deterministic filtering create nomination facts without semantic execution or publication. A human chooses the formal distribution and signs a manifest digest. The run command accepts only a strict locked manifest whose repository IDs, SHAs, licenses, selection evidence, roles, and source facts revalidate.

**When to use:** Always for the formal five-repository campaign and every promoted supplemental nomination.

**Example:**

```python
class LockedBenchmarkManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["locked_benchmark_manifest.v1"]
    manifest_version: PositiveInt
    entries: tuple[BenchmarkEntryV1, ...]
    locked_by: str
    locked_at: AwareDatetime
    nomination_set_digest: Sha256Digest
    manifest_digest: Sha256Digest

    @model_validator(mode="after")
    def require_distribution(self) -> Self:
        require_exact_benchmark_distribution(self.entries)
        return self
```

This follows the repository’s strict frozen Pydantic contract pattern; `manifest_digest` must be recomputed over canonical fields and cannot trust a supplied digest. [VERIFIED: domain model codebase grep]

### Pattern 2: Closed Stage-Specific Semantic Policy

**What:** Map each semantic stage to exactly one admitted DeepSeek model and reject a mismatched stage/model or non-official endpoint before constructing the HTTP request.

**When to use:** Every DeepSeek extraction, generation, and reviewer call.

**Example:**

```python
class SemanticStage(StrEnum):
    EXTRACTION = "extraction"
    GENERATION = "generation"
    REVIEW = "review"


DEEPSEEK_MODEL_BY_STAGE: Final = {
    SemanticStage.EXTRACTION: "deepseek-v4-flash",
    SemanticStage.GENERATION: "deepseek-v4-flash",
    SemanticStage.REVIEW: "deepseek-v4-pro",
}


def admitted_deepseek_model(stage: SemanticStage, configured: str) -> str:
    expected = DEEPSEEK_MODEL_BY_STAGE[stage]
    if configured != expected:
        raise SemanticProviderConfigurationError("closed stage/model policy mismatch")
    return expected
```

DeepSeek’s JSON mode requires `response_format={"type":"json_object"}`, a prompt mentioning JSON, and sufficient output budget; it can still return empty content, so the existing strict local decode/Pydantic failure path remains mandatory. [CITED: https://api-docs.deepseek.com/guides/json_mode/]

### Pattern 3: Evidence First, Report as Projection

**What:** Persist immutable facts for manifest admission, each terminal outcome, stage attempts, replay comparison, update lineage, canary bindings, human attestation, and every gate. Build human-facing Markdown and the 44-requirement map only from those facts.

**When to use:** Every acceptance run and rerun.

**Example:**

```python
def evaluate_release(evidence: AcceptanceEvidenceV1) -> ReleaseVerdictV1:
    gates = tuple(evaluate_gate(rule, evidence) for rule in HARD_GATE_REGISTRY)
    return ReleaseVerdictV1(
        gates=gates,
        verdict="PASS" if all(g.status == "PASS" for g in gates) else "FAIL",
        evidence_root_digest=evidence.root_digest,
    )
```

The independent verifier must rebuild the report bytes from the evidence root, compare the result with the checked-in report, and mutation-test missing, swapped, duplicated, stale, and self-referential evidence. [VERIFIED: `tools/verify_phase5_acceptance.py`, codebase grep]

### Pattern 4: Evaluator-Blind Expected Labels

**What:** Store the intended role and expected outcome in manifest/evaluator facts, but construct all semantic request payloads solely from the admitted source facts and prior stage output. Compare expected to observed only after a terminal outcome exists.

**When to use:** Every formal or supplemental repository scenario.

**Example:**

```python
semantic_input = build_extraction_input(
    source_bundle=admitted_source_bundle,
    policy=extraction_policy,
)
# benchmark_entry.expected_outcome is deliberately unavailable here.
observed = extraction_client.extract(semantic_input)
comparison = compare_hypothesis(benchmark_entry.expected_outcome, observed)
```

Tests should inspect serialized requests and fail if benchmark role, hypothesis, expected label, or human notes appear in any semantic message. [VERIFIED: `06-CONTEXT.md`, codebase grep]

### Pattern 5: Explicit Changed-Lineage Update

**What:** An identical replay proves no new semantic authority, package, branch, PR, commit, or reviewer request. A changed-SHA test creates a new workflow authority and desired revision only after an explicit prior-lineage binding and human approval; publication must update the same eligible open Draft and preserve the old-to-new chain.

**When to use:** TEST-03’s update scenario.

**Example:**

```python
persist_prior_lineage_binding(binding, approval)
updated = run_changed_source(candidate_at_new_sha)
assert updated.publication.outcome == "draft_updated"
assert updated.publication.pr_number == original.publication.pr_number
assert updated.lineage.previous_source_sha == original.source_sha
assert updated.lineage.current_source_sha == new_source_sha
```

The existing phase-three binding and publication desired-revision mechanisms should be exercised directly; Phase 6 must not invent a filename/title heuristic that silently equates two workflow authorities. [VERIFIED: phase-three lineage and publication codebase grep]

### Pattern 6: Exact-Head Human Content Attestation

**What:** Record a strict human attestation containing reviewer identity, target repository/PR, exact head SHA, source SHA, package and marker digests, verdict enum, each D-17 checklist result, notes, review timestamp, and attestation digest. Reconcile it with the live Draft and submitted GitHub review/comment evidence without granting automation review authority.

**When to use:** Before a real Draft can satisfy the positive value gate.

**Example:**

```python
class HumanSkillReviewAttestationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    verdict: Literal["publishable", "publishable_with_changes", "rejected"]
    pr_head_sha: GitObjectId
    usefulness_checked: bool
    fidelity_checked: bool
    provenance_license_checked: bool
    instruction_safety_checked: bool
    diff_scope_checked: bool
```

A GitHub requested reviewer is not sufficient evidence of a completed human judgment; requested reviewers and submitted reviews must be reconciled because a user is removed from requested reviewers after submitting a review. [CITED: https://docs.github.com/en/rest/pulls/review-requests]

### Anti-Patterns to Avoid

- **One command searches and silently selects the benchmark:** it removes the required human lock and makes the evidence set unstable; split nomination from formal execution.
- **Putting expected outcomes in prompts:** it contaminates the semantic result and makes expected-vs-observed evidence circular.
- **Treating every negative outcome as an outage:** deterministic rejection is valid product behavior; distinguish business terminals from system failure using a closed enum.
- **Treating provider/schema exhaustion as a negative example:** it is missing product evidence and must block release.
- **Adding an `ACCEPTANCE_MODEL` environment variable:** it creates precisely the arbitrary model escape D-09 forbids; keep exact stage models in closed typed code policy.
- **Rewriting historical all-Flash facts:** model identity is part of prior authority; keep history immutable and emit new Flash/Flash/Pro facts.
- **Inferring update lineage from repository/path/title:** require the existing explicit prior-lineage binding and approval.
- **Counting Draft creation or reviewer request as human review:** require an exact-head D-17 attestation with an explicit content verdict.
- **Running the value Draft before Gate B4 or after a bound change:** publication evidence would lack current authority.
- **Using Python socket monkeypatching as OS-level denial:** it cannot close the deferred syscall/process gap.
- **Scanning actual secret files:** use synthetic canary values only and scan sanitized surfaces.
- **Building the report from console logs or temporary artifacts:** logs are diagnostics; canonical structured state is the source of truth.
- **Letting the report certify its own digest:** keep an external evidence-root registry and independent rebuilder to avoid a self-validation cycle.
- **Using an aggregate score:** a high total can never waive a failed security, permission, provenance, idempotency, human-review, or rebuild gate.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GitHub reads and Draft writes | New generic GitHub SDK wrapper or raw ad hoc requests | Existing `github.py` and `github_publish.py` adapters | They already enforce fixed-SHA reads, repository allowlists, bounded mutations, redaction, and forbidden actions. [VERIFIED: codebase grep] |
| Semantic retry policy | SDK automatic retries or an agent framework | Existing deterministic pipeline retry authority with `max_retries=0` clients | One stage attempt must correspond to exactly one provider request for auditable cost and failure evidence. [VERIFIED: `AGENTS.md`, codebase grep] |
| Structured model output parsing | Free-text parsing/repair | Existing strict local JSON decode plus Pydantic validation | DeepSeek JSON mode does not guarantee application-schema validity or non-empty output. [CITED: https://api-docs.deepseek.com/guides/json_mode/] |
| Skill validation | Custom specification approximation | Official locked `skills-ref validate` plus existing deterministic security checks | The official validator covers format while project rules enforce the narrower no-scripts safety policy. [VERIFIED: `pyproject.toml`, codebase grep] |
| Publication idempotency | PR-title search or branch guessing | Existing publication key, desired revision, marker, remote reconciliation, and state adapter | These mechanisms already distinguish create, reuse, update, and recovery while bounding writes. [VERIFIED: `src/skillscout/application/publication.py`, codebase grep] |
| Changed-workflow identity | Automatic similarity matching | Existing prior-lineage binding plus explicit approval | Semantic authority changes at the new SHA and must not be silently collapsed. [VERIFIED: phase-three codebase grep] |
| Permission proof | A successful PR creation alone | Existing Gate B4 positive and causal negative probes | Least privilege requires proving both permitted and forbidden actions against current platform configuration. [VERIFIED: `tools/gate_b4_canary.py`, codebase grep] |
| Cryptography or attestation signing | Custom encryption, key storage, or signature scheme | Canonical SHA-256 content addressing plus GitHub identity/review evidence | The phase needs tamper-evident linkage, not new secret-bearing cryptographic infrastructure. [VERIFIED: codebase grep] |
| OS network isolation | A custom syscall filter in Python | Hosted kernel/network-namespace enforcement such as Docker `--network none`, verified in Wave 0 | Isolation must sit below Python and child processes. [CITED: https://docs.docker.com/engine/network/drivers/none/] |
| Release-report rendering | Hand-edited evidence prose | Deterministic renderer plus independent byte comparison | Manual prose cannot prove complete, reproducible mapping of all gates and 44 requirements. [VERIFIED: `tools/verify_phase5_acceptance.py`, codebase grep] |

**Key insight:** Phase 6 is primarily composition and evidence closure. Reuse each production authority boundary, then add strict acceptance contracts and independent verification around them; duplicating discovery, provider, publication, or validation logic would test the harness rather than the product.

## Runtime State Inventory

This phase includes a bounded semantic-provider policy refactor and a source-lineage update scenario, so runtime state must be treated explicitly.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Pipeline, operations, and publication stores persist prompt/policy/model identities, workflow authorities, attempts, publication markers, and desired revisions. Historical DeepSeek facts identify all-Flash policy. [VERIFIED: state adapter codebase grep] | Do not migrate or rewrite historical facts. Emit a new stage-specific Flash/Flash/Pro policy identity. For the changed-SHA test, write a new workflow authority and explicit prior-lineage binding/approval, then preserve both old and new facts. |
| Live service config | GitHub App installation, catalog, ruleset, protected environment, required reviewer configuration, installation identity, and repository secrets/variables live partly outside git. [VERIFIED: `tools/gate_b4_canary.py`, codebase grep] | Capture identifiers and hashes in fresh Gate B4 evidence. Any bound change invalidates evidence. Verify the protected environment immediately before publication credit. |
| OS-registered state | No launchd, systemd, Task Scheduler, pm2, or other durable OS registration is used by the repository. GitHub-hosted runner capabilities are external ephemeral state; local `sandbox-exec` exists, but Docker, `unshare`, and `strace` were not available in the research environment. [VERIFIED: codebase grep and local command probes] | Add a Wave 0 hosted-runner capability probe and record the exact kernel-enforced offline mechanism. Do not claim local socket tests close the syscall gap. |
| Secrets/env vars | The existing DeepSeek key, GitHub App identity/private-key injection, provider selector, and official base URL are runtime boundaries. The Flash/Pro split does not require a new credential or secret-name migration. [VERIFIED: configuration codebase grep] | Keep values unread and unlogged. Test only presence/absence, closed identifiers, redaction, and synthetic canaries. No data migration. |
| Build artifacts | `dist/skillscout-0.1.0-py3-none-any.whl` predates Phase 6 changes and will not update automatically. [VERIFIED: filesystem inventory] | Rebuild from the locked source after implementation, record its SHA-256, and ensure live workflows/test installation use the rebuilt exact bytes. Never treat the existing wheel as release evidence. |

**Canonical question answer:** Updating repository files does not update historical semantic authorities, live GitHub protection configuration, an already-built wheel, or an open Draft’s remote head. The plan must separately preserve history, re-run Gate B4, rebuild release bytes, and reconcile the remote Draft. [VERIFIED: codebase and runtime inventory]

## Common Pitfalls

### Pitfall 1: Benchmark Selection Is Not Reproducible
**What goes wrong:** The campaign names five repositories without evidence that real Search and filtering produced them, or silently replaces a weak candidate.
**Why it happens:** Selection, nomination, and execution are combined in one command.
**How to avoid:** Persist nomination facts, require immutable repository ID/SHA/license/provenance, then require a human-signed manifest revision before formal execution.
**Warning signs:** Repository names appear only in a test constant or report; no search page/candidate digest; a nomination changes without a manifest version bump. [VERIFIED: `06-CONTEXT.md`, codebase grep]

### Pitfall 2: Evaluator Hypotheses Leak into Semantic Requests
**What goes wrong:** The model is told that a repository should pass or fail, making scenario evidence circular.
**Why it happens:** The benchmark entry is passed wholesale to prompt construction.
**How to avoid:** Use separate evaluator and semantic-input types and mutation-test serialized request bodies for forbidden benchmark fields.
**Warning signs:** `expected`, `role`, `positive`, `negative`, or human notes occur in provider messages. [VERIFIED: `06-CONTEXT.md`, codebase grep]

### Pitfall 3: Business Rejection and System Failure Are Collapsed
**What goes wrong:** A valid fail-closed filter/reviewer result is marked as harness failure, or a provider/schema outage is counted as negative coverage.
**Why it happens:** A boolean `success` field lacks a closed terminal taxonomy.
**How to avoid:** Map existing discovery terminal outcomes into explicit `business_terminal`, `eligible`, and `system_failure` acceptance classes with complete structured reasons.
**Warning signs:** Retry exhaustion contributes to coverage; a structured reject blocks report generation; terminal reasons are free text. [VERIFIED: discovery domain codebase grep]

### Pitfall 4: The Provider Split Creates an Escape Hatch
**What goes wrong:** Pro review is enabled through arbitrary environment model/URL settings.
**Why it happens:** The existing single Flash constant is replaced with unrestricted configuration.
**How to avoid:** Add exact stage-specific constants/typed policy, preserve the official URL guard, and fail before HTTP for every mismatched model or endpoint.
**Warning signs:** Caller passes any string to `request_deepseek_json`; tests only check happy-path response parsing. [VERIFIED: `src/skillscout/adapters/semantic_provider.py`, codebase grep]

### Pitfall 5: “Same Lineage” Is Assumed from Path or Repository
**What goes wrong:** A changed SHA creates a duplicate Draft or updates the wrong workflow.
**Why it happens:** The acceptance harness bypasses existing explicit lineage binding.
**How to avoid:** Exercise `persist_prior_lineage_binding(binding, approval)` and prove new authority plus stable publication identity.
**Warning signs:** Update works without human approval; old/new authority digests are absent; title search determines the target PR. [VERIFIED: phase-three and publication codebase grep]

### Pitfall 6: Human Review Evidence Is Only a Reviewer Request
**What goes wrong:** The report says “human reviewed” because a reviewer was requested or a Draft was created.
**Why it happens:** Routing evidence is confused with content verdict evidence.
**How to avoid:** Add an exact-head D-17 attestation and reconcile GitHub requests/reviews plus current Draft state.
**Warning signs:** No `publishable` enum; checklist fields absent; PR head changed after the attestation. [CITED: https://docs.github.com/en/rest/pulls/review-requests]

### Pitfall 7: Gate B4 Evidence Is Stale
**What goes wrong:** A provider/workflow change occurs after the canary, but old permission evidence is reused.
**Why it happens:** The report binds a run ID without recomputing workflow and platform bindings.
**How to avoid:** Finalize all bound files, run the fresh canary immediately before value publication, and make every binding mismatch a hard gate failure.
**Warning signs:** Canary predates the release commit; workflow hashes differ; reviewer/environment/App identifiers are missing. [VERIFIED: `tools/gate_b4_canary.py`, codebase grep]

### Pitfall 8: Socket Monkeypatch Is Claimed as Syscall Denial
**What goes wrong:** Python-level tests pass while a subprocess or native code could still reach the network.
**Why it happens:** The existing test sentinel is mistaken for an OS boundary.
**How to avoid:** Run the offline adversarial suite under a verified hosted kernel/network isolation layer and retain a denial probe as evidence.
**Warning signs:** Evidence names only `socket.connect`; child-process or raw syscall probe never runs; Docker/namespace setup is unverified. [VERIFIED: `tests/conftest.py`, `tools/verify_phase1_gap_evidence.py`, codebase grep]

### Pitfall 9: Secret Scanning Reads Real Secrets
**What goes wrong:** The acceptance procedure itself exposes credentials while trying to prove redaction.
**Why it happens:** A broad recursive scanner opens `.env` or key material.
**How to avoid:** Seed synthetic canaries only into controlled inputs, maintain an allowlisted sanitized-output inventory, and scan those exact outputs and PR diffs.
**Warning signs:** Scanner walks the repository or runner home; output contains secret-value prefixes; artifacts are downloaded without a bounded manifest. [VERIFIED: `AGENTS.md`, codebase grep]

### Pitfall 10: Report Is Non-Rebuildable or Self-Certifying
**What goes wrong:** A polished Markdown document has no reproducible link to state, or its own digest is used to prove itself.
**Why it happens:** The report is manually edited or reads logs.
**How to avoid:** Render from a canonical evidence-root registry, keep report digest outside its own payload, and mutation-test byte-for-byte rebuilding.
**Warning signs:** Timestamps/order vary; missing evidence is a warning; a report checkbox is the only evidence for a requirement. [VERIFIED: `tools/verify_phase5_acceptance.py`, codebase grep]

## Code Examples

Verified patterns from official sources and repository code:

### DeepSeek Strict JSON Request with Local Validation

```python
response = client.chat.completions.create(
    model=admitted_deepseek_model(stage, configured_model),
    messages=messages_that_explicitly_request_json,
    response_format={"type": "json_object"},
    max_tokens=bounded_output_tokens,
)
payload = json.loads(require_nonempty_content(response))
result = response_model.model_validate(payload)
```

DeepSeek documents the JSON response-format flag and warns that prompts must mention JSON, output limits must be sufficient, and empty content can occur; local strict validation therefore remains part of the security boundary. [CITED: https://api-docs.deepseek.com/guides/json_mode/]

### GitHub Draft PR Creation

```python
payload = {
    "title": bounded_title,
    "head": admitted_head_branch,
    "base": protected_default_branch,
    "body": marker_bound_body,
    "draft": True,
}
```

The GitHub REST create-PR endpoint accepts `draft` and requires Pull Requests write permission for fine-grained credentials; SkillScout’s adapter must remain narrower than the generic API. [CITED: https://docs.github.com/en/rest/pulls/pulls]

### Full-SHA Action Pin

```yaml
steps:
  - uses: actions/checkout@<full-40-character-commit-sha>
```

GitHub states that pinning an action to a full-length commit SHA is the only immutable release reference; every new acceptance workflow must follow the existing full-SHA pin policy. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]

### Protected Environment and Serialized Live Runs

```yaml
concurrency:
  group: skillscout-phase6-live
  cancel-in-progress: false

jobs:
  publish:
    environment: skillscout-publication
```

GitHub environments can require approval and restrict deployment branches, and Actions concurrency can ensure only one workflow/job in a group runs at a time. [CITED: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments] [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax]

### Independent Acceptance Registry

```python
REQUIRED_GATES = {
    "benchmark_locked",
    "scenario_coverage",
    "prompt_injection_denied",
    "supply_chain_denied",
    "os_syscall_network_denied",
    "secret_canaries_absent",
    "identical_replay_idempotent",
    "changed_source_updates_existing_draft",
    "gate_b4_current",
    "human_publishable_verdict",
    "all_44_requirements_mapped",
    "report_rebuild_exact",
}
```

Keep this registry in the independent verifier and cross-check it against the production renderer so removing a production gate cannot make both sides silently agree. [VERIFIED: `tools/verify_phase5_acceptance.py`, codebase grep]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DeepSeek all-Flash semantic profile | Flash extraction/generation plus Pro isolated reviewer | Phase 6 locked decision | Requires bounded stage-specific model admission and new policy identity; historical facts remain valid history. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| JSON mode treated as structured output | JSON mode plus strict local application-schema validation | Existing SkillScout DeepSeek boundary | Malformed, extra-field, truncated, or empty responses fail closed rather than being repaired. [CITED: https://api-docs.deepseek.com/guides/json_mode/] |
| Python socket sentinel | Python sentinel plus hosted kernel/network isolation evidence | Phase 6 closure of deferred gap | Closes the non-Python syscall and subprocess portion of `os_syscall_network_denial`. [VERIFIED: `tools/verify_phase1_gap_evidence.py`, codebase grep] |
| Requested reviewer / Draft existence evidence | Exact-head human Skill-review attestation | Phase 6 acceptance | Separates publication routing from actual content judgment and satisfies D-16/D-17. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| Per-phase verification reports | Whole-MVP evidence root plus exact 44-requirement map and deterministic rebuild | Phase 6 milestone gate | Release recommendation becomes reproducible from cross-phase canonical evidence. [VERIFIED: roadmap and existing verifier codebase grep] |

**Deprecated/outdated:**

- **All-Flash reviewer setting:** Retain only for historical evidence; new Phase 6 live facts must identify Pro for the review stage. [VERIFIED: `src/skillscout/adapters/semantic_provider.py`, codebase grep]
- **Historical Gate B4 authority as Phase 6 credit:** Existing evidence remains historical but must not satisfy the fresh post-change Phase 6 gate. [VERIFIED: `AGENTS.md`, codebase grep]
- **Socket sentinel as complete network proof:** Keep it as a fast unit-test detector, not as the OS/syscall acceptance artifact. [VERIFIED: `tools/verify_phase1_gap_evidence.py`, codebase grep]
- **Draft creation as human acceptance:** A real content verdict is now mandatory. [VERIFIED: `06-CONTEXT.md`, codebase grep]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | None. Recommendations are derived from locked decisions, repository inspection, executed tests, registries, or official documentation. | — | — |

No assumed package, compliance target, retention duration, benchmark repository, or live outcome is treated as decided. Human selection and hosted capability checks remain explicit open questions/checkpoints.

## Open Questions (RESOLVED)

1. **RESOLVED — Which exact five repository names and commit SHAs will be locked?**
   - What we know: The distribution, identity fields, license rule, real-Search provenance, and human-lock requirement are fixed. [VERIFIED: `06-CONTEXT.md`, codebase grep]
   - What's unclear: The actual candidates cannot be selected by research without running the product nomination lane and obtaining human approval.
   - Disposition: Resolve the values at runtime from the real Search nomination output, then require the benchmark-lock human checkpoint to select and attest the exact five identities before any live semantic run. The planner must not hard-code internet-search picks as release evidence.

2. **RESOLVED — Which hosted kernel-enforced network-denial mechanism is available in the exact Actions runner?**
   - What we know: Local research found `sandbox-exec` but not Docker, `unshare`, or `strace`; GitHub-hosted Ubuntu images document Docker tooling, and Docker’s none network provides container isolation except loopback. [CITED: https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md] [CITED: https://docs.docker.com/engine/network/drivers/none/]
   - What's unclear: The exact permissions and pinned base image/runtime path in the project’s protected workflow have not been exercised.
   - Disposition: Run the Wave 0 hosted probe and prefer an ephemeral, dependency-prepared container with `--network none`; fail closed and block the adversarial campaign if the exact runner cannot demonstrate both direct-process and child-process denial. No Python-only fallback receives release credit.

3. **RESOLVED — What bounded raw-artifact retention duration should be selected?**
   - What we know: Raw diagnostic artifacts are non-canonical and must have bounded retention; GitHub allows repository/org/enterprise retention configuration and per-artifact limits. [CITED: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/remove-workflow-artifacts]
   - What's unclear: The project has not locked a Phase 6 duration.
   - Disposition: Set every Phase 6 raw diagnostic Actions artifact to `retention-days: 1`. Raw artifacts remain non-canonical; release reconstruction depends only on redacted content-addressed state-branch facts.

4. **RESOLVED — What human attestation transport will be used?**
   - What we know: The evidence must bind the exact Draft head and D-17 checklist, while automation cannot approve or merge. [VERIFIED: `06-CONTEXT.md`, codebase grep]
   - What's unclear: Whether the human will provide a structured PR comment, a separately reviewed JSON file, or a protected workflow input.
   - Disposition: Use a strict exact-head JSON attestation ingested by the pre-finalized protected read-only verification workflow. Corroborate reviewer identity against GitHub review/comment observations and reject any stale Draft head, marker, package, source, or lineage binding.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Repository-local uv | Locked tests/build | ✓ | `0.11.29` | — [VERIFIED: local command probe] |
| Python | Runtime/tests | ✓ | `3.13.14` through locked environment | — [VERIFIED: local command probe] |
| git | Diff/hash/report evidence | ✓ | `2.50.1` | — [VERIFIED: local command probe] |
| DeepSeek API credential | Live semantic campaign | Unknown by design; value not inspected | — | No live fallback; protected workflow checkpoint required. [VERIFIED: secret-handling policy] |
| GitHub App protected publication configuration | Gate B4 and real Draft | Historical evidence exists; freshness required | bound platform identity, not a local version | Fresh canary must validate before credit. [VERIFIED: `AGENTS.md`, codebase grep] |
| `sandbox-exec` | Local process isolation experiments | ✓ | OS-provided | Not canonical Phase 6 evidence. [VERIFIED: local command probe] |
| Docker | Hosted OS/network denial | ✗ locally; expected on GitHub Ubuntu runner but unverified in project job | — | Hosted Wave 0 capability probe. [CITED: https://github.com/actions/runner-images] |
| `unshare` / `strace` | Alternative Linux syscall evidence | ✗ locally | — | Use the verified hosted container/network mechanism. [VERIFIED: local command probe] |
| Existing injection corpus | Prompt-injection campaign | ✓ | 7 named fixture classes | — [VERIFIED: `tests/fixtures/injection`, filesystem inventory] |
| Existing built wheel | Release byte evidence | ✓ but stale | `skillscout-0.1.0` artifact | Rebuild and re-hash from locked source. [VERIFIED: filesystem inventory] |

**Missing dependencies with no fallback:**

- A live DeepSeek credential and current protected GitHub publication authority are intentionally unavailable to offline research; the planner must place explicit human-authorized live checkpoints rather than probe credentials locally. [VERIFIED: `AGENTS.md`, codebase grep]

**Missing dependencies with fallback:**

- Local Docker/namespace tooling is absent; execute the kernel-denial proof in a verified GitHub-hosted Linux job, while retaining fast local socket/forbidden-import tests. [VERIFIED: local command probes]

## Validation Architecture

`workflow.nyquist_validation` is enabled, so Phase 6 requires task-level automated feedback and a live/manual evidence boundary. [VERIFIED: `.planning/config.json`, codebase grep]

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `9.1.1` plus stdlib-only independent acceptance verifiers [VERIFIED: `pyproject.toml`, codebase grep] |
| Config file | `pyproject.toml` [VERIFIED: filesystem inventory] |
| Quick run command | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_acceptance_domain.py tests/test_acceptance_application.py tests/test_semantic_provider.py -x` |
| Full suite command | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` |
| Static gate | `.tools/uv-0.11.29/bin/uv run --locked ruff check .` |
| Independent phase gate | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py` |

The currently relevant focused baseline completed `192 passed, 2 skipped in 2.27s`; the new tests above are Wave 0 gaps and therefore do not exist yet. [VERIFIED: locked pytest run, 2026-07-28]

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-01 | At least five fixed-SHA real public repositories flow from real Search to structured publication decisions | integration + authorized live | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -x` plus protected `run-acceptance` campaign | ❌ Wave 0 |
| TEST-02 | Positive generation, all required negative boundaries, multi-workflow, all injection fixtures, and supply-chain denials have complete structured outcomes | adversarial + contract | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_adversarial.py -x` | ❌ Wave 0 |
| TEST-03 | Identical replay produces no duplicate facts/remote effects; explicitly bound changed source updates the same open Draft with lineage | integration + recovery | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'idempotent or changed_source' -x` | ❌ Wave 0 |
| TEST-04 | Fresh causal authority denials, one real Draft, and exact-head human content verdict | deterministic verifier + authorized live/manual | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_gate_b4_canary.py tests/test_phase6_acceptance.py -k 'gate_b4 or human_review' -x` plus protected canary/publication workflows | ⚠️ Existing canary tests; Phase 6 attestation tests are Wave 0 |

### Sampling Rate

- **Per task commit:** Run the focused test file for the edited contract/application/adapter plus `ruff check` on changed Python files.
- **Per wave merge:** Run the full locked pytest suite, Ruff, and both Phase 6 independent verifiers.
- **Phase gate:** Full suite green; protected offline adversarial job green; locked live campaign complete; fresh Gate B4 current; real value Draft still Draft/open; human exact-head verdict positive; report and all 44 requirement mappings rebuild byte-for-byte before `$gsd-verify-work`.

### Wave 0 Gaps

- [ ] `src/skillscout/domain/acceptance.py` contract tests for strict manifest, evidence, attestation, gates, and digests.
- [ ] `tests/test_acceptance_application.py` for nomination/lock/run separation and evaluator-blind requests.
- [ ] `tests/test_phase6_adversarial.py` for seven existing injection classes plus shell, subprocess, dynamic import, source execution, synthetic-secret, and outbound-network denials.
- [ ] `tests/test_phase6_acceptance.py` for complete scenario taxonomy, identical replay, explicit changed-lineage update, fresh-canary binding, human attestation, and report rebuilding.
- [ ] `tests/test_phase6_workflow.py` for environment protection, serial concurrency, full-SHA Actions, artifact retention, no unsafe interpolation, and separation of offline/live jobs.
- [ ] `tools/verify_phase6_acceptance.py` with an independent required-gate registry, exact evidence roots, source-surface coverage, and mutation tests.
- [ ] `tools/verify_phase6_validation_map.py` with exact TEST-01..TEST-04 and all-44-requirement inverse maps.
- [ ] Hosted OS/network isolation capability probe before the plan commits to a specific runner mechanism.
- [ ] Deterministic report fixtures that contain only synthetic credentials and sanitized canonical facts.

## Security Domain

`security_enforcement` is enabled; Phase 6 is itself the milestone’s adversarial and least-privilege security gate. [VERIFIED: `.planning/config.json`, codebase grep]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | GitHub App short-lived installation credentials and DeepSeek credential injected only by protected runtime; no credential persistence or prompt exposure. [VERIFIED: `AGENTS.md`, codebase grep] |
| V3 Session Management | no | SkillScout has no end-user login/session layer in v1; GitHub/DeepSeek client credentials are request authority, not application sessions. [VERIFIED: architecture codebase grep] |
| V4 Access Control | yes | Closed catalog allowlist, protected environments, current Gate B4 causal denials, separate admin cleanup, and no merge/approve/ready/default-branch methods. [VERIFIED: `tools/gate_b4_canary.py`, codebase grep] |
| V5 Input Validation | yes | Frozen extra-forbidden Pydantic models, canonical JSON/digests, exact repository/SHA/license/model/endpoint admission, bounded text, and official Skill validation. [VERIFIED: domain model codebase grep] |
| V6 Cryptography | yes | Standard TLS through providers and `hashlib.sha256` content addressing; never hand-roll encryption/signature/key storage. [VERIFIED: codebase grep] |

### Known Threat Patterns for Python / GitHub Actions / LLM Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Repository prompt injection crossing into system authority | Elevation of Privilege / Spoofing | Untrusted-input envelope, no tools, evaluator-blind prompts, strict stage schemas, independent reviewer, and controlled injection corpus. [VERIFIED: `AGENTS.md`, codebase grep] |
| Source repository code, shell, dynamic import, or subprocess execution | Elevation of Privilege | Read-only REST, no clone/install/scripts, forbidden-import/static surface checks, controlled denial fixtures, and kernel-isolated offline job. [VERIFIED: `AGENTS.md`, codebase grep] |
| Arbitrary OpenAI-compatible endpoint or model | Spoofing / Information Disclosure | Exact official DeepSeek base URL and typed stage-to-model allowlist that rejects before HTTP. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| Outbound exfiltration outside GitHub/DeepSeek adapters | Information Disclosure | Closed network adapters, fast socket sentinel, AST/static checks, synthetic probes, and OS/network namespace denial evidence. [VERIFIED: `tools/verify_phase1_gap_evidence.py`, codebase grep] |
| Secret leakage through logs/state/report/artifact/PR | Information Disclosure | Never read real secrets; seed synthetic canaries; scan allowlisted sanitized outputs and exact PR diff; hard-fail on any hit. [VERIFIED: `06-CONTEXT.md`, codebase grep] |
| Evidence substitution, deletion, or stale binding | Tampering | Canonical digests, immutable facts, independent registry/rebuilder, mutation tests, and exact workflow/platform Gate B4 bindings. [VERIFIED: verifier and canary codebase grep] |
| Duplicate WorkflowSpec, Skill, branch, commit, PR, or reviewer request | Tampering / Repudiation | Stable authorities/publication keys, desired revisions, remote reconciliation, replay comparison, and zero-write proof. [VERIFIED: publication codebase grep] |
| Unauthorized default-branch push, merge, approval, ready transition, or cleanup | Elevation of Privilege | Adapter method absence, protected catalog/ruleset/environment, causal Gate B4 denial probes, and separate human admin cleanup. [VERIFIED: `tools/gate_b4_canary.py`, codebase grep] |
| Workflow expression/script injection | Elevation of Privilege | No direct untrusted `${{ }}` interpolation into shell, fixed action SHAs, bounded structured files, and workflow contract tests. [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |

## Recommended Planning Sequence

1. **Wave 0 — Contracts and failing tests:** Define manifest, nomination, scenario, attestation, evidence-root, gate, and report schemas; add the independent registry and hosted isolation capability probe. No live effects.
2. **Wave 1 — Closed provider policy:** Implement Flash extraction, Flash generation, Pro review as exact stage bindings; add request-body, endpoint/model denial, empty/malformed/extra-field, retry, telemetry, and historical-authority tests.
3. **Wave 2 — Acceptance orchestration and persistence:** Add nomination/lock/run/rebuild commands that compose the real discovery coordinator; persist under existing state ownership and prohibit evaluator-field prompt leakage.
4. **Wave 3 — Offline adversarial campaign:** Run every injection fixture and deterministic filter/qualification/format/security/reviewer/supply-chain scenario under kernel-enforced network denial; scan synthetic canaries across sanitized outputs.
5. **Wave 4 — Locked live benchmark:** Human locks the manifest; run five fixed-SHA repositories, identical replay, and explicitly approved changed-SHA lineage update. Capture funnel, budgets, telemetry, outcomes, and zero/updated effects.
6. **Wave 5 — Fresh authority and human value proof:** Freeze bound workflow bytes, run fresh Gate B4, publish one separate value Draft to the fixed test catalog, and ingest a positive exact-head human attestation. Keep the Draft open and Draft.
7. **Wave 6 — Release reconstruction:** Render the concise report and exact 44-requirement map; independently rebuild them, run mutation tests, bind the rebuilt wheel/workflow hashes, and run the full release chain.

Human checkpoints are mandatory before benchmark lock, prior-lineage approval, live credential use, Gate B4/publication, human content attestation, and later probe cleanup. [VERIFIED: `06-CONTEXT.md`, codebase grep]

## Sources

### Primary (HIGH confidence)

- Repository source and tests: `src/skillscout/application/discovery.py`, `publication.py`, semantic adapters, state adapters, canary tools, Phase 5 verifiers, injection fixtures, workflows, and locked focused test run — current implementation and behavior.
- `.planning/phases/06-adversarial-mvp-acceptance/06-CONTEXT.md` — locked Phase 6 decisions and acceptance boundaries.
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `AGENTS.md` — requirement, milestone, runtime, security, and workflow constraints.

### Secondary (MEDIUM confidence)

- [DeepSeek Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/?article_id=article_1779470751466_8) — exact Flash/Pro model identifiers.
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/) — JSON-mode request requirements and failure caveats.
- [DeepSeek List Models](https://api-docs.deepseek.com/api/list-models) — official model enumeration endpoint.
- [GitHub Pull Requests REST](https://docs.github.com/en/rest/pulls/pulls) — Draft creation and fine-grained permission.
- [GitHub Review Requests REST](https://docs.github.com/en/rest/pulls/review-requests) — reviewer-request and submitted-review lifecycle.
- [GitHub Actions Secure Use](https://docs.github.com/en/actions/reference/security/secure-use) — full-SHA action pinning and workflow security.
- [GitHub Deployment Environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments) — protection rules and deployment branch controls.
- [GitHub Workflow Syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) — serialized concurrency behavior.
- [GitHub Artifact Retention](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/remove-workflow-artifacts) — bounded artifact retention.
- [Docker none network driver](https://docs.docker.com/engine/network/drivers/none/) — container network isolation except loopback.
- [GitHub Actions Runner Images](https://github.com/actions/runner-images) — hosted runner image/tooling reference; exact project capability still requires a Wave 0 probe.

### Tertiary (LOW confidence)

- None used as implementation authority.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new package is needed; exact project versions and official provider/API documentation were checked.
- Architecture: HIGH — recommendations compose current production coordinators, state ownership, lineage, publication, and canary boundaries inspected in the repository.
- Pitfalls: HIGH — most are direct mismatches between locked decisions and current implementation surfaces; external hosted isolation remains a verified-before-use item.
- Live outcome readiness: MEDIUM — exact benchmark repositories, current protected credentials/platform identities, hosted kernel isolation, and the human verdict necessarily remain future authorized evidence.

**Research date:** 2026-07-28
**Valid until:** 2026-08-04 — re-check DeepSeek model documentation, GitHub hosted-runner capability, workflow hashes, and all Gate B4 platform bindings immediately before live execution.
