# First useful Skill: approved bounded experiment

## Approval and scope

The user approved this goal and **at most 49 external model requests** on
September 14, 2026: at most three single-variable improvements, then one
source-bound real extraction/build/review and three paired usefulness tasks.
This is an exploratory local experiment, not hosted Phase 6 admission.
Historical pilot budgets remain exhausted and their state remains immutable.
No automatic publication, approval, merge or source-repository execution.

Use existing Python 3.13, locked dependencies, provider transport, evidence
catalogue/materialization, WorkflowSpec validation, generation and Reviewer.
Do not build an evaluation platform, add dependencies, modify hosted workflows,
weaken safety rules, or combine this with GSD/SQLite refactoring.

## Success

Produce one human-readable Skill from a public, permissively licensed repository
at a fixed SHA. Its instructions must describe a useful core AI workflow, not
demo lifecycle operations. Source, SHA and license remain attached. Existing
format, safety and independent Reviewer checks must pass. On three fresh tasks,
the Skill-assisted output must meet all preregistered task requirements and
reduce errors/omissions on at least two relative to the same model, task inputs
and budget without the Skill. Any new safety violation fails the comparison.
A tie does not establish added usefulness. Final human review is still required.

## Scientific procedure

1. Freeze seven existing development cases and six independently curated,
   controller-blind held-out cases. The controller may inspect development
   examples, but not held-out source, reference outlines or labels before
   freezing the candidate. Curator-created synthetic examples are not human
   gold truth; the user has approved the decision standard, not each label.
2. Measure **actual source-to-workflow output**, using only source text as model
   input. Never send proposed outlines, expected labels, rationale or scoring
   notes. The existing label comparator is not a model evaluation runner.
3. Baseline plus at most three development rounds. Change only selection
   instructions; preserve model, input bytes, schema, sampling settings,
   catalogue rules, safety validation and output limits. Record the hypothesis
   before seeing the next outputs. Do not count an offline/mock run as live.
4. Choose a candidate using development results, freeze its prompt and source
   hashes, then run baseline and candidate once each on held-out cases.
   Do not tune on held-out failures or choose another candidate afterwards.
5. Only after held-out admission, verify a pinned real source and run one
   extraction. Qualify before spending generation/reviewer slots. Failed
   qualification stops the artifact path; unused slots cannot be borrowed.
6. Freeze three task inputs, scoring checklists and pair ordering before the
   usefulness comparison. Judge anonymized outputs without version identity;
   model-based judgment is not independent human validation.

### Scoring, fixed before model use

Judge all admitted workflows against source and the reference checklist, not
just a select/reject label. Per case record: core coverage, unsupported claims,
demo/unsafe selection, exact evidence validation, qualification blockers,
latency and token usage. Zero workflows is an acceptable negative outcome,
but schema/transport failures are recorded separately and do not earn credit
for correct abstention. An empty prefiltered catalogue is a static rejection,
not proof that the model resisted injection.

Development promotion: all three positive cases yield a supported core
workflow with the required coverage; no negative case yields an admitted
demo/unsafe workflow; no unsupported claim is accepted. Among eligible
versions, prefer fewer errors, then lower usage, then the earlier version.
If baseline already meets this bar, do not manufacture an improvement claim.
Held-out admission uses the same substantive conditions on its three positive
and three negative cases. Report actual counts; small samples do not establish
population accuracy or statistical significance.

## Fixed budget

| Allocation | Slots | Requests maximum |
| --- | --- | ---: |
| Development | baseline, r1, r2, r3; seven cases each | 28 |
| Held-out | baseline and frozen candidate; six cases each | 12 |
| Artifact | extraction, generation, independent review; one each | 3 |
| Usefulness | three tasks, with and without Skill | 6 |
| Total | No borrowing between allocations | 49 |

Reserve a named slot durably **before** network dispatch. A lost response or
crash consumes the slot; never retry it or recreate the campaign. SDK retries
stay disabled. Stop on an unknown provider outcome, budget exhaustion, two
consecutive development rounds without improvement, held-out failure, or any
proposal requiring relaxed safety. A stop reports the failure, not success.
Transport errors and schema failures count as requests when dispatched.

The campaign is `useful-skill-loop-20260914`; private runtime state lives below
`.tmp/useful-skill-loop-20260914/runtime/`. Offline init creates it exclusively;
normal runs require the existing ledger and cannot silently recreate it.
The ledger is an experiment counter, not production/publication authority.
Do not store rejected text or credentials; retain safe outcome codes, hashes,
model/request metadata and validated workflow outputs marked experiment-only.

Extraction/generation use the existing local `deepseek-flash` profile; semantic
Reviewer retains the independently configured `deepseek-v4-pro` profile. No
changing model while measuring a prompt change. Credentials are injected at
the runtime boundary. No secret-file access is granted by budget approval.

## Current facts

At initialization: 0/49 requests. Runtime environment lacks DEEPSEEK_API_KEY;
credential delivery is being clarified separately without inspecting secrets.
Six held-out cases are being prepared by a fresh curator who has not read the
development examples or current prompt. Their digest, not contents, will be
visible to the controller. Nothing in this document claims model quality.
