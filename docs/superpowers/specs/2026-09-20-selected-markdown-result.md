# Selected Markdown preview and source screening — 2026-09-20

## Status

The local preview can select one ordinary Markdown file at an immutable GitHub
commit using `--markdown-path`, with both `--evidence-selection` and
`--source-only-fields`. Commit `7c0c446` contains the bounded extension and tests.
The existing v4 prompt, evidence catalogue, source validation, qualification,
generation, security and publication boundaries are unchanged. This input-format
extension is not evidence of a useful Skill or completed Phase 6 acceptance.

The real pilot is now closed at `validation_rejected`: extraction was faithful,
but the generated package failed three local checks and independent read-only
inspection found invented approval requirements. It is a diagnostic artifact,
not an accepted or useful Skill. No Pro request or usefulness comparison ran.

Controller verification: 210 product-focused tests, 29 private extraction
launcher tests and 17 private build launcher tests passed; full Ruff and whitespace
checks passed. Independent implementation and integration reviews found no
blocking code issue. A private-launcher path mismatch was fixed and re-reviewed.
The final frozen full suite passed: **3,011 passed, 3 skipped in 1,046.83s**, exit 0,
against implementation commit `7f02248`. No product source, test or dependency
changed during that run. Subsequent edits are documentation only.

The three explicit skips are `phase6-release-requirement-map-not-yet-built`
(`test_phase6_acceptance.py:453`), incomplete protected live-canary configuration
(`test_publication_live_canary.py:266`) and no explicit live-canary opt-in
(`test_publication_live_canary.py:336`). They do not prove live acceptance. The
initial full run was intentionally interrupted before a confirmed integration
fix: 1,878 passed, 1 skipped in 588.20s, exit 2; it remains partial evidence, not
the successful final run above.

## Source screening before model use

The first repository was public MIT `microsoft/prompts-for-edu`, pinned to
`508567d4008b17dc1df98cbb89f88708c250f666`, with license blob
`9e841e7a26e4eb057b24511e7b92d42b257a80e5`.

| Selected path | Content SHA-256 | Result under unchanged catalogue |
| --- | --- | --- |
| `Administration/Prompts/Meeting Summary.MD` | `2b6e19285ec2aeff27c5c7ac506df97d6093bea3285d739a95d02979d08d787c` | Fenced normative prompt excluded; retained example loses mandatory summary length and heading constraints. |
| `Students/Prompts/Team Pre-mortem Coach.MD` | `ed04e2d2af1020a007c436f675647b9f7848da3b2cc3f3748d8768e5c172a8bb` | Fenced procedure/output contract excluded; original also requires outside research. |
| `Students/Prompts/Team Reflection Coach.MD` | `d92f88ff573a50edf5caf06bb544bfe94649be86f4cbce09830d6a6d89d100e8` | Fenced adaptive procedure excluded; retained synopsis cannot support its interaction rules. |

All three were excluded before any model request. An untruncated catalogue means
the retained entries fit the limit, not that every essential source fact survived
filtering. No fence or safety rule was relaxed to make a source eligible.

The second repository selected for bounded screening was `danielmiessler/fabric`,
only `data/patterns/summarize/system.md` (the historical
`patterns/summarize/system.md` only if the current path is absent). Two bounded
metadata attempts failed before any source content was obtained. A credential-free
connectivity check established GitHub anonymous API exhaustion: HTTP403,
remaining0, reset `2026-09-20T07:13:47Z`. A post-reset metadata attempt also failed.
No GitHub credential was accessed, and no web-page substitute was admitted as
source provenance. The three failed metadata attempts are preserved in the
private screen report. A third repository has not been screened.

At `07:15:18Z`, a credential-free header diagnostic confirmed actual recovery
(HTTP200, remaining58). One subsequent bounded adapter pass succeeded using five
reads. The source is public MIT, with no privileged action, execution, installation
or external research in the selected workflow. Its exact source identity and fixed
attempt order are frozen in
[`local-markdown-20260920.json`](../../../config/previews/local-markdown-20260920.json).
The sole eligible source meets all three ranking criteria (complete input/steps/
output, explicit constraints, standalone use); no model result influenced selection.

Fabric commit: `b682dad740f24e85ce9a48d23babc6780dd476ac`; selected blob:
`b655b620b895c71593ea578fb4ea5e975cfdd3a0`; license blob:
`fb06a6f8c497f15063059ff224965d9e60e98a01`; content SHA-256:
`29d393bf16f9a89464ef1f734cfd523e5949c01e5e580039540fd65823bc4a06`.
The unchanged catalogue retains all nonblank characters in 16 untruncated entries.
The contract specifies a 20-word summary, ten main points of at most 16 words each,
five takeaways, and numbered Markdown lists without notes, duplicate items or
repeated item openings. No author is inferred from the repository owner.

## Request and authority accounting

No new campaign was initialized and no new model call was made at this pre-call checkpoint.
The private launcher reserves one extraction slot durably before loading the
runtime credential or starting the real CLI, with no unknown-outcome replay.
Its new configuration must first freeze the eligible source, model and committed
code. The sole eligible source above is admitted for exactly one fresh extraction;
the configuration reserves CNY20 conservatively, without borrowing prior budgets.

Known historical model-cost estimate remains CNY0.196462, not a billing statement.
The cumulative ceiling is CNY100. Prior failed campaigns remain closed and their
budgets cannot be reused. New generation/review/comparison calls remain contingent
on actual extraction fidelity and deterministic qualification, not CLI exit status.

One later integration concern is explicitly recorded: the ordinary
`build-candidate` runtime profile permits up to three application-level generation
and review attempts. Before a real pilot build, it must be constrained to the
pilot's one-request-per-stage ceiling through a reviewed minimal implementation;
SDK retries being disabled does not establish that application-level bound.

No push, PR, merge, remote state mutation, Skill publication, source-code execution
or human repair of generated semantic data occurred.

## Real extraction and independent fidelity result

On committed source `153b8a2932c06691ee1eeb37af40c790bf667fc8`, the fresh one-shot
launcher made exactly one real `deepseek-flash` extraction request. Run
`686a3ed1ed3b4c399ce66b0f13f4d18f` completed with one WorkflowSpec and no dropped
workflow. Fingerprint:
`sha256:a6ef7f7a24de05defe57f7f121c6b53192b392909e353fc3f89c86a341209de1`.
The returned model identity and evidence catalogue matched the frozen settings.

Telemetry: request `f5ef0b40-4bd2-4ef1-9a1f-2db6dfeea922`, 3,373 input tokens,
1,118 output tokens, 4,491 total. Conservative peak uncached estimate:
CNY0.015690; cumulative known estimate CNY0.212152, not a provider bill.

Independent field-by-field review passed source fidelity: all three output
sections, exact 20/10/16/5 count/word constraints, numbered Markdown, absence of
extra notes, duplicate items and repeated openings survived. All16 evidence
records exactly match the frozen source; all11 step references are declared.
No invented approval, setup prerequisite, scenario fact or authorship was added.
Empty preconditions, assumptions and approval fields accurately reflect the source.
Section-label punctuation remains exact in evidence even where semantic fields
omit the trailing colon; downstream generation must preserve the required format.

Pure deterministic qualification evaluates to 85/100 with no hard failure (25
specificity, 10 reusability, 15 verifiability, 25 evidence, 10 safety). Missing explicit
preconditions/non-goals/failure modes were not invented to inflate this score.
This diagnostic score does not by itself establish end-to-end candidate admission.

The first unchanged CLI export attempt failed closed with
`candidate_source_unavailable`. Read-only isolation verified the complete four-stage
chain and selected-file scope; the remaining rejection was `_source_facts`
comparing `repo:danielmiessler/fabric` with GitHub metadata spelling
`danielmiessler/Fabric`. GitHub's
[repository API contract](https://docs.github.com/en/rest/repos/repos#get-a-repository)
defines owner/repository names as case-insensitive. A minimal ASCII comparison
fix preserves metadata spelling and all other identity/integrity checks. The same
unmodified source state then exported exactly one canonical descriptor locally,
with no model request. A new opt-in `build-candidate --single-attempt` binds existing
generator/reviewer attempt fields to1/1; defaults remain3/3. Both fixes are covered
by regressions under the
[local integration plan](../plans/2026-09-20-local-pilot-integration-fixes.md).
No original semantic JSON or state was edited, and extraction will not be retried.

| Evidence layer | Current result |
| --- | --- |
| Structured extraction | Passed, one real workflow |
| Source fidelity | Passed independent field-level review |
| Pure qualification | 85/100, no hard failure |
| Canonical export/admission | Passed after minimal case-only comparison fix; original state unchanged |
| Generated package | Produced once; preserved unchanged, not accepted |
| Official format | Passed pinned `skills-ref 0.1.1`; no official findings |
| Local structure / policy | Failed: two orphan resources and one unregistered source match |
| Generated-package source fidelity | Rejected by independent read-only inspection: invented approvals; inconsistent failure guidance |
| Independent Pro Reviewer | Skipped by validation gate; zero requests |
| Nine usefulness comparisons | Not started; tasks/scoring not frozen and no value claim |

## One real build and exact stop

Build code was frozen at `7f022486c882e62b3c7eeb61c6ffdcbb44a788ca` after the two
reviewed integration repairs. The canonical descriptor was passed unchanged;
its SHA-256 before and after build is
`87a59998718012085be9f23e4b7e64a5fed86fd6d6b15975fc6339e52aef91db`.
Build run: `phase3-2eebaf7357c64643875bedea08e98aef`. Both model-attempt ceilings
were bound to one by `--single-attempt`; the reviewer remained `deepseek-v4-pro`.
The private launcher durably reserved the stage ceilings before loading the
previously authorized runtime credential. No fallback or retry occurred.

The generator returned one parsed `deepseek-flash` response, request
`893fed21-40ef-48da-a31a-2e046dd64387`, with 5,190 input and 973 output tokens
(6,163 total). The CLI exited zero because it recorded a known terminal outcome;
the terminal summary explicitly says `eligible=false`,
`outcome=validation_rejected`, and `review_skipped_validation_errors`.
The stage ledger contains one qualifier, one generator and one validator attempt,
and no reviewer attempt. An unused reviewer reservation is not a model call and
cannot be moved to another stage.

The frozen package has four files (36,587 bytes): `SKILL.md`, two Markdown
references and `references/provenance.json`. Package digest:
`sha256:3741b1c6e334038558ee7301175fbf9c3e2541a486cf0f69ec20316f8157dfb3`.

### What failed, without changing the artifact

1. `structure_orphan_resource`: neither `references/formatting-constraints.md` nor
   `references/summarization-pattern-details.md` is linked from `SKILL.md`.
   The renderer writes reference files but does not automatically render a
   reference index. The generated semantic text supplies no links either.
   This is a generator/renderer contract gap, not a missing repository document.
2. `overcopy_unregistered_source_match`: the unchanged policy reports one error
   at the first matching normalized 80-character window. A separate read-only
   reproduction located matches from source evidence entries 5 and 6 (zero-based)
   in `SKILL.md` procedure steps 3 and 4. The one registered quotation does not cover
   these matches. This is the project's mechanical copying rule, not a finding
   that the MIT source is legally unusable. The threshold was not relaxed.
3. Independent package inspection rejects the new approval obligations in
   `SKILL.md` lines 45–46: external distribution of a summary and adoption of
   pattern changes now require human approval. The original source states no
   such obligations and the verified WorkflowSpec has `required_approvals=[]`.
   The generation schema requires at least one `approvals` item, and the trusted
   generator instructions both prohibit invented authority and require manual
   publication/approval. This is observable contract pressure: it does not force
   the particular fabricated requirements, but plausibly contributed to the
   conflation. This single sample cannot establish the model's internal cause.
4. The new failure instruction at line 41 asks for a limitation statement without
   resolving the source's fixed-section/no-notes rule. Avoiding invented content
   at line 40 is reasonable general safety guidance; the defect is an unlabelled,
   ambiguous exception, not the principle of refusing to invent facts.
   `failure_handling` also requires a nonempty list even when the source has no
   explicit failure modes.

Core source constraints survived generation: a 20-word single sentence, ten main
points of at most 16 words, five takeaways, numbered Markdown lists, no extra notes,
no repeated items and no repeated opening words. Preserving these facts does not
cancel the additional obligations or the failed package checks. No generated file,
WorkflowSpec, descriptor or historical state was manually repaired.

### Request and cost totals

| Stage | Requests used / frozen cap | Input tokens | Output tokens | Estimated CNY |
| --- | ---: | ---: | ---: | ---: |
| Extraction | 1 / 1 | 3,373 | 1,118 | 0.015690 |
| Generation | 1 / 1 | 5,190 | 973 | 0.018164 |
| Pro review | 0 / 1 | 0 | 0 | 0 |
| A/B/C comparison | 0 / 9 | 0 | 0 | 0 |
| This trial | 2 / 12 | 8,563 | 2,091 | 0.033854 |

Conservative estimates use the peak uncached Flash rates observed on September 20
(CNY 2/million input, CNY 8/million output) from
[DeepSeek's pricing page](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/).
Including the prior known CNY 0.196462, the known cumulative estimate is
**CNY 0.230316**, not a provider bill. Remaining slots are unused and closed,
not permission for a second generation or a new campaign. Repository screening
exclusions and the three failed GitHub metadata reads above remain recorded.

## Inspect and reproduce the route

All trial files below are local, ignored diagnostics under
`.tmp/local-markdown-20260920/runtime/`, relative to this worktree:

- Original state: `phase2.db`; canonical input: `export/candidate-a6ef7f7a24de05defe57f7f121c6b53192b392909e353fc3f89c86a341209de1.json`.
- Build state: `build-runtime/phase3.db`; terminal and validation reports:
  `build-runtime/output/candidate-terminal-summary.json` and `validation-report.json`.
- Rejected package: `build-runtime/output/content-summarization-pattern-eb4e5a36/`.
- `SKILL.md` SHA-256: `7298c95c426dc3800ab4a55658440b4aec66f974e75d34217172ad4a8397975b`.
- Validation report SHA-256: `62035049b70a288a9f6f5aab5a27c714f31f36a8046bcce19b5f84d47e08743c`.
- Terminal summary SHA-256: `1fc57cca0d652d4adbb759385358dbbb7fd44fd2a192bfe00119e6fafba3ff14`.

For read-only inspection, from the worktree root:

```bash
trial=.tmp/local-markdown-20260920/runtime
.tools/uv-0.11.29/bin/uv run --locked --offline --no-env-file skillscout inspect-run \
  686a3ed1ed3b4c399ce66b0f13f4d18f --state "$trial/phase2.db" --format json
jq '{outcome,eligible,validation_error_count,review_disposition}' \
  "$trial/build-runtime/output/candidate-terminal-summary.json"
```

The shortest future live route remains the existing commands, not a new runtime:
`extract-repo --markdown-path … --evidence-selection --source-only-fields
--deepseek-current-flash` → source-fidelity review → `export-candidates` →
`build-candidate --deepseek-current-flash --single-attempt` → inspect terminal,
validation and review reports. Follow the [command guide](../../GETTING-STARTED.md#local-extract-build-and-inspect-flow)
with fresh distinct paths, frozen source/configuration and pre-reserved request
limits. Use the approved runtime credential mechanism; do not source or display
`.env`. **Do not rerun either consumed launcher or reuse this trial's state/budget.**

## Conclusion and next testable hypothesis

The bounded Markdown input and case-only export repairs are implemented. A real
faithful extraction and a real generated package are demonstrated. A validated,
independently Pro-reviewed or useful Skill is **not** demonstrated; there are no
nine comparison outputs or usefulness scores to report. Host loading, Phase 6,
remote publishing and the overall product goal remain unverified.

The next narrow hypothesis is that generation can accurately state that the
source specifies no approvals, without inventing a requirement to fill the
nonempty output field, while keeping SkillScout's publication policy separate.
Trusted rendering should also link the references it creates. First test those
contracts offline against this preserved failure, including the unchanged copying
rule, before allocating another frozen one-shot trial. This report does not change
the generator prompt, public schema, safety thresholds or model policy. A public
schema change is outside this pilot's authority. No human editing of this failed
Skill is requested as a shortcut to acceptance.
