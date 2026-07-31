# Phase 6: Adversarial MVP Acceptance - Context

**Gathered:** 2026-07-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a repeatable, evidence-backed MVP acceptance campaign over at least five real public repositories pinned to commit SHAs. The campaign must cover positive and negative business outcomes, adversarial inputs, end-to-end idempotency and update behavior, a fresh least-privilege publication canary, and at least one real human-reviewed Draft PR. It concludes with a release report mapping all 44 v1 requirements. It does not widen the v1 product boundary: no automatic merge, approval, ready-for-review transition, untrusted code execution, unauthorized secret access, private-repository support, generated scripts, self-modification, or public-marketplace publication.

</domain>

<decisions>
## Implementation Decisions

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

### Fresh campaign recovery addendum
- A stale Phase 6 authority must never be revived. A replacement campaign begins with a read-verified current canonical state head/root, then uses a source/workflow binding that contains that exact root; mutable environment input must not select the nomination parent.
- Add a narrowly scoped state-only path for a fresh Search-derived nomination and its subsequent benchmark lock. It may persist only the strict nomination and `acceptance_benchmark_lock` facts, and may not invoke a semantic provider, execute candidate code, access catalog/PR authority, or create live authority.
- The five repository choices remain an accountable human decision. Automation may prepare and display a proposed manifest, but it must not fabricate a human attestation or silently reuse the historical five-entry lock. A later exact live-authority approval is separate and remains required before DeepSeek benchmark/replay use.

### the agent's Discretion
- Research and planning may choose the exact five repository names and SHAs, provided they satisfy the locked benchmark distribution and are human-locked before release evidence is collected.
- Research and planning may choose the internal acceptance-report schema decomposition, file names, command surface, and test organization while preserving structured outputs, deterministic verdict rules, redaction, rebuildability, and the persistence boundary above.
- Research and planning may set bounded latency/cost presentation thresholds and artifact-retention duration; these cannot weaken hard safety, authority, or evidence-integrity gates.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product scope and Phase 6 acceptance
- `.planning/PROJECT.md` — Core value, v1 boundaries, untrusted-input rules, credential constraints, and phase-isolation requirements.
- `.planning/ROADMAP.md` §Phase 6: Adversarial MVP Acceptance — Fixed phase goal, six success criteria, milestone exit criteria, and 44-requirement reporting obligation.
- `.planning/REQUIREMENTS.md` §MVP Verification — Locked TEST-01 through TEST-04 requirements and explicit v1 out-of-scope boundaries.
- `.planning/STATE.md` — Current milestone status, completed Phase 1–5 capabilities, verified Gate B4 bindings, and remaining Phase 6 release blocker.
- `RELEASE.md` — Current preview/release posture and gates that Phase 6 must close.

### Architecture, provider, and operating policy
- `docs/ARCHITECTURE.md` — Stage isolation, WorkflowSpec trust boundary, semantic-provider constraints, state persistence, and publication boundary.
- `docs/CONFIGURATION.md` — Closed provider selection, official DeepSeek endpoint, credentials, hosted discovery settings, and protected publication configuration.
- `docs/DEVELOPMENT.md` — Secret-handling rules and the required process for adding a bounded semantic-provider/model policy.
- `docs/TESTING.md` — Existing suites, locked local test command, live-only test boundaries, and CI evidence conventions.
- `src/skillscout/adapters/semantic_provider.py` — Current closed OpenAI/DeepSeek provider profile and all-Flash DeepSeek model binding that Phase 6 must revise safely.
- `src/skillscout/adapters/openai_extract.py` — Extraction client boundary shared by the DeepSeek compatibility path.
- `src/skillscout/adapters/openai_generate.py` — Generation client boundary and strict local DeepSeek response validation.
- `src/skillscout/adapters/openai_review.py` — Independent Reviewer client boundary and reviewer model identity.

### Real discovery, state, and publication surfaces
- `src/skillscout/application/discovery.py` — Search-to-candidate orchestration, budgets, stage outcomes, persistence, and recovery entry point for the five-repository campaign.
- `src/skillscout/application/publication.py` — Strict publication admission and idempotent create/update behavior.
- `src/skillscout/adapters/github.py` — Fixed-SHA, read-only GitHub REST access boundary.
- `src/skillscout/adapters/github_publish.py` — Bounded branch/Draft PR GitHub write adapter and forbidden-action surface.
- `src/skillscout/adapters/operations_state.py` — Canonical discovery/checkpoint state projection and rebuild path.
- `src/skillscout/adapters/publication_state.py` — Publication markers, recovery, and duplicate-prevention state.
- `.github/workflows/discover.yml` — Current scheduled/manual discovery workflow whose exact bytes participate in live-canary authority.
- `.github/workflows/publish-candidate.yml` — Current protected publication workflow whose exact bytes participate in live-canary authority.
- `.github/workflows/gate-b4-canary.yml` — Existing live permission-canary workflow and human-cleanup separation.

### Existing acceptance and adversarial assets
- `tools/verify_phase5_acceptance.py` — Existing deterministic phase-level acceptance report pattern to extend, not bypass.
- `tests/test_phase5_acceptance.py` — Acceptance-tool mutation tests, forbidden-import checks, and production-surface coverage patterns.
- `tools/gate_b4_canary.py` — Existing positive Draft/reviewer and negative authority probe implementation.
- `tests/test_gate_b4_canary.py` — Canary contract, probe causality, redaction, and cleanup-attestation tests.
- `tests/test_gate_b4_canary_workflow.py` — Workflow binding and least-privilege checks for Gate B4.
- `tests/test_publication_live_canary.py` — Existing live publication-canary evidence patterns.
- `tests/fixtures/injection/` — Controlled prompt-injection corpus covering override, secret solicitation, exfiltration, encoding, privilege masquerade, action solicitation, and cross-stage amplification.
- `tools/verify_phase1_gap_evidence.py` — Records `os_syscall_network_denial` as specifically deferred to Phase 6.
- `tests/conftest.py` — Existing outbound socket sentinel that rejects and records attempted network connections in offline tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/verify_phase5_acceptance.py` already demonstrates a deterministic, structured, mutation-tested acceptance-report pattern suitable as the base for the Phase 6 whole-MVP report.
- `tools/gate_b4_canary.py` and `.github/workflows/gate-b4-canary.yml` already implement positive Draft/reviewer evidence, negative default-branch/merge/ruleset/unauthorized-resource probes, secret redaction, and separate human cleanup.
- `tests/fixtures/injection/` provides seven named adversarial classes; Phase 6 should aggregate their existing stage-boundary results rather than invent an unrelated corpus.
- Discovery and publication state adapters already provide persistent content-addressed facts, recovery, and idempotency markers needed for same-input reruns and changed-source updates.
- The installed CLI already exposes `discover`, `publish-discovered`, `inspect-run`, admission verification, and candidate publication commands that can be composed into an acceptance campaign.

### Established Patterns
- Every cross-stage fact is a strict, frozen, versioned Pydantic model with unknown fields rejected and canonical digests.
- LLM calls are tool-free and independently requested; DeepSeek JSON is locally decoded and strictly validated, with SDK retries disabled.
- Semantic business rejection is a terminal structured outcome, while transient provider failure follows the pipeline-owned finite retry policy.
- Durable state belongs on `skillscout-state`; Actions artifacts are short-lived diagnostics only.
- Publication is Draft-only, marker-bound, recoverable, and denied any merge/approve/ready/default-branch authority.
- Tests use the repository-local locked command `.tools/uv-0.11.29/bin/uv run --locked pytest -q`.

### Integration Points
- Extend the closed stage-specific provider settings so Flash remains the extractor/generator model and Pro becomes the Reviewer model without allowing arbitrary endpoints or identifiers.
- Feed the locked benchmark manifest through the real Search/discovery coordinator and record expected-vs-observed outcomes without contaminating model prompts with expected labels.
- Build the Phase 6 report from verified stage/state/publication evidence rather than scraping logs.
- Exercise publication only after fresh Gate B4 evidence is bound to the exact current production surface, then keep the successful Skill PR open for human judgment.
- Add Phase 6 denial evidence at the process/network boundary while preserving the GitHub and DeepSeek adapters' explicitly authorized outbound access.

</code_context>

<specifics>
## Specific Ideas

- The user may hand SkillScout additional repositories at any time; these should enter a visible nomination lane rather than silently changing the formal benchmark.
- The formal live model arrangement should make the independent review easy to explain: “Flash finds and drafts; Pro makes the final semantic publication recommendation.”
- Human reviewers should not inspect credentials or run source repositories. Their Skill PR checklist is usefulness, fidelity, attribution/license, instruction safety, and diff scope.
- A successful Phase 6 proves “controlled pilot readiness on the DeepSeek path,” not universal validation of every provider or future repository class.

</specifics>

<deferred>
## Deferred Ideas

- A live OpenAI-provider acceptance campaign is optional follow-up work and does not block the DeepSeek-backed v1 acceptance.
- Arbitrary provider/model configuration, private repositories, generated scripts, automated Reviewer-driven rewriting, a Web review queue, and publication to a public Skill marketplace remain outside Phase 6 and the v1 boundary.

</deferred>

---

*Phase: 6-Adversarial MVP Acceptance*
*Context gathered: 2026-07-28*
