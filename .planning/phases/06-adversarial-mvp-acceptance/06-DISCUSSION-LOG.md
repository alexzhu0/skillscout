# Phase 6: Adversarial MVP Acceptance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-28
**Phase:** 6-Adversarial MVP Acceptance
**Areas discussed:** real repository and model campaign, acceptance verdict, Draft PR lifecycle, live canary and evidence boundary

---

## Real repository and model campaign

### Benchmark selection

| Option | Description | Selected |
|--------|-------------|----------|
| Search then lock | Use real Search/filter results, then human-lock five repository identities, SHAs, licenses, and coverage roles | ✓ |
| Fully manual | Pick five well-known repositories without requiring Search provenance | |
| Dynamic top five | Use the current top five Search results on every run | |

**User's choice:** Search then lock.
**Notes:** The user asked whether humans may also provide repositories. Supplemental human nominations are allowed under the same safety and fixed-SHA rules, but cannot silently replace the formal benchmark.

### Benchmark outcome mix

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-labeled mixed sample | Two plausible positives including multi-workflow, two negatives, and one borderline sample; attacks remain controlled fixtures | ✓ |
| All positive | Focus only on successful generation | |
| No prior distribution | Interpret whatever outcomes occur after the run | |

**User's choice:** Pre-labeled mixed sample.
**Notes:** Expected labels are evaluator hypotheses and must not be supplied to the semantic model as desired answers.

### Live provider

| Option | Description | Selected |
|--------|-------------|----------|
| DeepSeek-only tiered models | Flash for extraction/generation and Pro for independent final review | ✓ |
| OpenAI primary | Require a live OpenAI acceptance run | |
| Dual-provider consensus | Require both providers to approve publication | |

**User's choice:** DeepSeek-only tiered models.
**Notes:** The user currently has only a DeepSeek credential and asked whether Pro and Flash can share the campaign. Live OpenAI is not necessary for v1 release credit; its provider path remains covered offline.

### Cross-model review

| Option | Description | Selected |
|--------|-------------|----------|
| Pro-only final review | Flash generates; one independent Pro request produces the final semantic review | ✓ |
| Flash and Pro both review | Require both reviewers to pass | |
| Escalation only | Flash reviews first and sends only disputes to Pro | |

**User's choice:** Pro-only final review.
**Notes:** Independence is enforced through stage/request/context and distinct model identity; the Reviewer still has no edit or publish authority.

---

## Acceptance verdict

### Overall decision rule

| Option | Description | Selected |
|--------|-------------|----------|
| Automated hard gates then human review | Blocking technical evidence must pass before a human judges the real Skill Draft | ✓ |
| Weighted aggregate score | Permit failures to be offset by high scores elsewhere | |
| Unconstrained human override | Let a human ignore failed automated gates | |

**User's choice:** Automated hard gates then human review.
**Notes:** The user asked what humans actually inspect. Skill reviewers judge usefulness, fidelity, attribution/license, instruction safety, and diff scope; milestone reviewers confirm the summarized evidence and release recommendation.

### Rejection versus system failure

| Option | Description | Selected |
|--------|-------------|----------|
| Classify by failure nature | Correct fail-closed business rejection is normal; invariant, authority, evidence, secret, or execution failure blocks release | ✓ |
| Every rejection fails | Require all five repositories to publish | |
| Only crashes fail | Treat duplicates or evidence gaps as successful operation | |

**User's choice:** Classify by failure nature.
**Notes:** Filtering, qualification rejection, validation rejection, and Reviewer rejection must still produce complete structured reasons at the correct terminal boundary.

### Warnings

| Option | Description | Selected |
|--------|-------------|----------|
| Non-security warnings only | Allow explicit quality/latency/cost/provider-coverage limits but never waive hard safety or evidence gates | ✓ |
| Zero warnings | Fail on any known limitation | |
| Human waiver | Permit safety or permission failures to be manually waived | |

**User's choice:** Non-security warnings only.
**Notes:** A successful report may describe DeepSeek-only live coverage without claiming universal provider validation.

### Human value proof

| Option | Description | Selected |
|--------|-------------|----------|
| Human marks at least one Draft worth publishing | Require `publishable` or `publishable_with_changes`; no merge required | ✓ |
| Creation only | Count a Draft without content review | |
| Merge required | Require the Skill to enter the catalog default branch | |

**User's choice:** Human marks at least one Draft worth publishing.
**Notes:** A rejected Draft remains useful negative evidence, but another candidate must satisfy the positive value gate.

---

## Draft PR lifecycle

| Decision | Recommended option selected | Alternatives rejected |
|----------|-----------------------------|-----------------------|
| Target catalog | Publish only to `alexzhu0/skillscout-catalog-test` | SkillScout source repository; arbitrary runtime target |
| Successful Draft | Keep open and Draft until explicit human judgment; never auto merge/approve/ready | Automatic close; automatic ready transition |
| Probe cleanup | Separate human administrator closes probe PRs, deletes probe branches, and attests cleanup | GitHub App cleanup; permanent probe branches |
| Changed source | Update the corresponding open Draft with old/new SHA lineage; create a new Draft only after prior closure/merge | New PR per SHA; never reevaluate |

**User's choice:** All recommended options.
**Notes:** The user requested the remaining questions in one batch and approved every recommended Draft lifecycle choice.

---

## Live canary and evidence boundary

| Decision | Recommended option selected | Alternatives rejected |
|----------|-----------------------------|-----------------------|
| Gate B4 freshness | Rerun immediately before release credit and bind exact workflows plus current App/catalog/ruleset/environment/reviewer/installation identity | Reuse Phase 5 historical evidence; inspect workflow text only |
| Adversarial scope | Existing injection corpus plus denied shell, subprocess, dynamic import, source execution, and non-adapter network paths | Text injection only; code review only |
| Secret evidence | Synthetic canaries scan sanitized logs/state/report/artifacts/PR diff; never read real secrets | Open `.env`/PEM for inspection; Git-only scan |
| Persistence | Concise report on main, redacted content-addressed evidence on state branch, bounded diagnostic artifacts | Commit raw evidence to main; logs only |

**User's choice:** All recommended options.
**Notes:** Any bound production-surface change invalidates the live canary. Phase 6 also closes the previously deferred OS/syscall network-denial evidence gap.

---

## the agent's Discretion

- Select exact repositories and SHAs during research, subject to the locked distribution and human-lock requirement.
- Choose internal schemas, command layout, test organization, presentation thresholds, and bounded artifact retention without weakening deterministic gates.

## Deferred Ideas

- Live OpenAI acceptance after a credential becomes available.
- Arbitrary providers/models, private repositories, generated scripts, automated rewriting, Web review UI, and public marketplace publication.
