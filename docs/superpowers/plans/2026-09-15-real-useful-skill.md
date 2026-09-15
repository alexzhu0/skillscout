# First real useful Skill — approved implementation plan

User approved execution on September 15, 2026. Baseline: `58aa421` on
`codex/first-useful-skill-loop`. Local work only; no push, merge, publication,
hosted-state update, source execution, dependency installation, or prompt promotion.

## Global constraints

- Reuse extract-repo → export-candidates → build-candidate; selected-README v3
  with --evidence-selection and --deepseek-current-flash. No r1/r2 substitution.
- Runtime-only existing authorized loader may select DEEPSEEK_API_KEY from the
  designated root .env. Never display or persist credentials or read other secrets.
- Maximum 14 provider requests: 3 extraction, 1 generation, 1 independent Pro
  review, 9 task comparisons. No borrowing. Reserve before dispatch; unknown
  outcomes stop without retry or replacement state. Stop before projected task
  costs reach CNY100; lower costs need no further spending approval.
- Preserve all historical failed campaigns and original output bytes.
- No manual JSON/Skill repairs or relaxed validators to obtain a passing result.

## Task 1: freeze sources and conditions

- [ ] Screen at most three public repository sources read-only. Require an allowed
  permissive license and explicit input/steps/output, not setup-only guidance.
- [ ] Rank eligible sources by complete input/steps/output, explicit limitations,
  standalone usability (one point each), then repository/path lexical order.
  Freeze order, SHA, license, file path/hash before any model request.
- [ ] Verify useful source text survives existing catalogue rules. Do not expand
  boundaries to rescue an unsuitable source. Create a fresh local pilot record.

## Task 2: real extraction and build

- [ ] Attempt each eligible frozen source once in order. Inspect all authored
  fields for fidelity, evidence roles, assumptions, approvals and source support.
- [ ] Export unmodified verified descriptors. First faithful candidate passing
  existing deterministic qualification may enter build, once only.
- [ ] Retain Flash generation and separately contextualized configured Pro review.
  Require existing official format/local safety validators and Reviewer approval.
- [ ] Normal no-workflow/qualification rejection may advance to the next frozen
  source; schema/unknown/transport failure or generation/review failure stops.
  If no candidate survives, later paid stages are not run; report failure.

## Task 3: usefulness comparison, only if Task 2 succeeds

- [ ] Freeze three fresh tasks (normal, missing information, irrelevant trigger),
  exact inputs and grading checklists after generation, before comparison calls.
- [ ] Run A task-only, B task+exact source README, C task+Skill/references on the
  same Flash model, independent contexts, same output cap and no tools. Data is
  untrusted, never system authority. Order: ABC, BCA, CAB. Nine calls, no retries.
- [ ] Blind-grade procedure correctness, missing-input handling, verifiable output,
  relevance, each 0–2. Record disagreements before revealing conditions.
- [ ] Pass requires every C ≥7/8, no invented facts/guarantees/authority/execution,
  C>A on at least two cases, C≥B on every case and C>B on at least one. Ties with
  README do not prove added value. Agent judgments still require human confirmation.

## Task 4: verification and handoff

- [ ] TDD any deterministic integration fix, independent review of changed code;
  no extra public interface, schema, dependency or framework by default.
- [ ] Verify source binding, descriptor identity, failed-stage gating, caps,
  unknown-outcome denial, equal comparison inputs and non-disclosing diagnostics.
- [ ] Run relevant and full locked offline pytest, Ruff; list baseline failures
  and skips separately. Use .tools/uv-0.11.29/bin/uv run --locked --no-env-file.
- [ ] Update README, RELEASE and result record with actual source/request/token/
  cost/outcome facts and minimal CLI guide. Commit locally, never push/merge.

## Execution record

- Source screening began with microsoft/generative-ai-for-beginners,
  brexhq/prompt-engineering and anthropics/courses. No other repository is screened.
- brexhq/prompt-engineering README at 50871be17eb86d70ce066462f4328a6f62a7208e:
  MIT; 65,747 bytes; catalogue cap128 ends in language-model history before useful
  citation/structured-output instructions. Excluded before paid extraction.
- anthropics/courses: API license NOASSERTION, LICENSE begins
  Attribution-NonCommercial 4.0 International. Excluded by permissive-license rule.
- Only the Microsoft source remains eligible. Fewer than three eligible sources
  does not authorize screening additional repositories or additional calls.
