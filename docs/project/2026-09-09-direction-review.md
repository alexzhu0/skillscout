# SkillScout direction review — 2026-09-09

Status: assessment and proposed priorities, not a replacement release policy or
authorization for remote execution. Reviewed local source: `bec2eed`.

## Judgment

Keep the product objective: help a Skill catalog maintainer turn procedural
knowledge in public GitHub repositories into useful, attributable Skill drafts.
The objective is plausible; its usefulness and cost advantage have not yet been
demonstrated by the reviewed live acceptance evidence. Existing engineering is
substantial, but implementation progress is not evidence of product value.

The present imbalance is between elaborate acceptance/publication machinery and
limited feedback from people actually using generated Skills. Correct the order
of validation before expanding that machinery or scaling discovery.

A repository is a source, not the unit of value. The unit of value is a specific
repeatable task with inputs, steps, outputs, limitations, and evidence. A popular
repository may contain no transferable workflow. A small example may contain a
valuable one. Search rank and stars are discovery signals, not quality verdicts.

## Evidence inspected

- `docs/project/product.md` identifies catalog maintainers as the initial user.
  Its July status mixes implemented and still-active requirements; it is not a
  reliable current product-completion score.
- `docs/GETTING-STARTED.md` documents a working fixture route and a live
  extraction command. Moving from extraction to generation requires a canonical
  descriptor from the reviewed coordinator; a newcomer does not yet have a
  documented single-repository, real-Skill preview journey.
- GitHub run [33734530468](https://github.com/alexzhu0/skillscout/actions/runs/33734530468),
  created September 3, was checked read-only during this review: authority
  preflight succeeded, live benchmark failed, replay was skipped. This check did
  not repeat the run or retrieve credential values.
- The earlier investigation of that run recorded one Flash extraction request
  followed by boundary rejection. Those observations support an extraction
  failure diagnosis, not a broad comparison of model quality.
- `src/skillscout/domain/extraction.py` requires model-supplied path, blob SHA,
  and exact excerpt. `validate_workflow_boundaries` checks membership and exact
  substring presence. It also applies the forbidden-pattern list to evidence
  and workflow prose; an ordinary HTTP(S) URL matches that list. This establishes
  a possible false-positive mechanism, not the specific reason every rejected
  workflow in the live run was unsafe or safe.
- `src/skillscout/application/processors.py` converts zero surviving proposed
  workflows into `schema_failure`. `src/skillscout/application/discovery.py`
  already maps that result to `schema_exhausted`. Other paths can lose that
  classification, and `src/skillscout/cli.py` maps unexpected acceptance
  exceptions to `state_integrity_error`; the exact failing path still needs a
  reproducing regression test before a fix is claimed.
- At the reviewed source, `bootstrap.py` has 7,240 lines, `operations_state.py`
  5,053, and the Phase 6 workflow 2,194. Size alone does not establish a defect,
  but these large coupled surfaces increase the cost of changing retry and
  acceptance behavior.
- The current [Agent Skills specification](https://agentskills.io/specification)
  permits instruction-only packages. Its reference validator checks frontmatter
  and naming conventions; passing it does not establish task usefulness.

## Keep these boundaries

Retain bounded read-only retrieval, fixed source commits, license/provenance
checks, strict stage contracts, isolated semantic requests, cost limits,
independent review, and human-only merge. Preserve the existing publication
controls until any proposed change has its own reviewed scope.

Separate provenance correctness from semantic correctness. A quote occurring in
the source proves that it exists, not that it supports the proposed procedure.
Likewise, valid JSON does not make content trustworthy, and two separate model
requests do not establish independent empirical evidence of usefulness.

## Recommended order

1. **Make failures understandable.** Reproduce the extraction-terminal failure
   locally with synthetic or already-authorized test data. Preserve the precise
   stage and closed reason codes through durable state and reporting. Keep
   schema exhaustion distinct from verified state corruption and business
   rejection. This is the first part of the already-approved repair.
2. **Test the proposed one-correction policy before integrating it.** A correction
   may use only bounded deterministic feedback, retain the original validation,
   and consume the same durable request budget. No rejected text should become
   trusted instructions. A confirmed refusal, a legitimate no-workflow result,
   or an ambiguous provider completion must not be re-asked as a formatting
   correction. Validate with offline fixtures first; a second billed request is
   useful only if it measurably improves valid evidence. Do not add a hidden
   adapter retry that breaks one-request-per-attempt accounting.
3. **Demonstrate one useful Skill before expanding operations.** Select one
   approved task-rich repository from the existing benchmark inputs. Produce a
   local reviewable Skill package and concise evidence report through reviewed
   composition. Preserve release authority requirements; a development preview
   cannot substitute for protected release evidence. If a new preview entry
   point is needed, design that narrow interface rather than another campaign
   subsystem.
4. **Evaluate actual use.** Use an existing Agent host with controlled inputs and
   explicitly limited capabilities. Compare the same task and model under three
   conditions: task alone, task plus source README, task plus generated Skill.
   Have a human evaluate the outputs against a rubric defined before testing.
   Source repository code is not installed or executed. Start with ordinary
   success, missing-input/failure handling, and inappropriate-trigger cases.
5. **Return to five repositories and Draft publication.** Once a concrete Skill
   shows value, complete the existing five-repository acceptance and exact replay,
   then the separately authorized publication boundary. Update current docs at
   meaningful milestones. Do not manufacture new nominations just to refresh
   expired code bindings when the source-input selection remains suitable.

The suggested usage comparison is a new validation deliverable, not a claim that
it has already been implemented or run. A custom Agent runtime, new database,
multi-agent framework, web console, and public marketplace remain unnecessary.

## What to measure

For each repository, record a terminal explanation, valid workflow count,
candidate count, model calls/tokens, and any human edits required. For each Skill,
record whether it activates appropriately, completes the target task, handles
missing prerequisites, preserves the source procedure, and improves on both
baselines. Record reviewer time and useful output, not simply files or PRs made.

Initial learning milestone: one human-accepted Skill with source-grounded
instructions and a successful controlled use case. A stronger pilot milestone
requires the five repository outcomes and repeatable comparison evidence; a
single successful example does not prove generalization or production readiness.

If successful Skills merely restate README material without improving outcomes
or saving curator effort, narrow the source domain or task definition before
automating more discovery. If a small number of examples is useful but most
repositories are noise, prioritize curator-supplied URLs and treat Search as a
candidate feed. Neither observation justifies silently weakening safety rules.

## Longer-term option, not part of the current repair

If verbatim-copy failures remain frequent, evaluate a versioned extraction
interface in which deterministic code assigns evidence IDs to bounded source
segments and the model selects IDs. Code would supply the exact text, path, and
SHA. This can remove mechanical copying from the LLM, but it changes the input
contract and needs separate evaluation of segmentation, semantic support,
compatibility, and policy identity. It is not an automatic replacement for the
already-approved bounded correction.

## Actions taken during this review

Created the approved isolated branch/worktree
`codex/fix-phase6-flash-correction`. Added this assessment only. No production
code, workflow, protection rule, remote state, or live authority was changed.
No tests, model calls, publication, or benchmark dispatch were performed in this
review. The Flash correction and precise-terminal repair remain implementation
work; this document is not a completion claim for those fixes.

Subsequent implementation in this branch addresses precise schema-failure
classification and telemetry only; see `RELEASE.md` for that repair. Automatic
correction and controlled Skill-use evaluation remain follow-ups. Review also
identified pre-existing loss of classification for refused/incomplete extraction
and generic CLI mapping of other acceptance failures; those are not fixed by
the schema-only change and must not be described as resolved.

## Subsequent bounded-correction offline milestone — September 9

The separately scoped implementation now supplies the one-correction policy
proposed above for DeepSeek extraction only. Recorded production composition
covers schema/non-verbatim failure followed by valid correction and twice-invalid
terminal failure. Each response retains independent telemetry; correction uses
the unchanged pinned user input and deterministic validators, fixed trusted
feedback, and the existing three-attempt extraction/twenty-request campaign
limits. It never retries after the correction. Explicit provider refusal markers
are excluded without interpreting prose as provider authority. Refused/incomplete
acceptance classification beyond that narrow exclusion remains outside this work.

Offline recovery tests cover reservation, started, response-persisted, and terminal
boundaries, plus altered policy/model identity and fabricated decided predecessor
rejection. Scheduling belongs to the application: the fixed benchmark coordinator
loops within its budget, while `extract-repo` requires a subsequent same-input/state
invocation after a scheduled correction. Historical authority stays readable;
fresh V2 live authority must bind the correction policy. No live run, candidate
execution, workflow change, publication, or human-use comparison was performed.

This is an implementation milestone, not a revised assessment of the inspected
live failure or proof of product value. The next milestone remains one useful
Skill and the controlled task-alone/source-README/generated-Skill comparison,
before broader five-repository and publication acceptance. Phase 6 remains open.
