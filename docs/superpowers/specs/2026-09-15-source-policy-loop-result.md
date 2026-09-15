# Source-policy experiment: no general improvement established

The autonomous goal is one faithful real Skill and an honest usefulness result,
not a larger evaluation framework. User authorization covers ordinary local work
and cumulative model spend below CNY100; it does not authorize remote changes,
publication, source execution, new credentials or weaker validation.

## Frozen eight-request comparison

Code/fixture commit: `f460888dba16e8fd0c6ff88212340333540a5645`.
Dataset: [four synthetic cases](../../../tests/fixtures/workflow_selection/source_policy_cases.json),
SHA-256 `d15e80edb00ccdd06767d64f86a815cc164ee4e4676b65887c69a59ed7d1f1a5`.
The baseline and independent `source_only` suffix used the same guarded Flash
client, schema, source catalogue and output cap. Source-only did not inherit r1/r2.

- Baseline rendered prompt: `sha256:067e4da3b7f45718a73aa1fec52e038222e7447bb13dae7cff76975888b5b1ac`.
- Source-only rendered prompt: `sha256:1d0dd63b7620ab5556995ffe18f6e5e5dc0ab19afbdc93ccc9b5fb93d43d0edc`.
- Order: baseline/candidate, candidate/baseline, baseline/candidate,
  candidate/baseline in dataset case order. All eight reservations decided.
- Source catalogues retained 7/10/8/8 entries without truncation.
- Private immutable evidence: `.tmp/source-policy-check-20260915/runtime/`.
- No grading fields entered requests. No prompt/fixture edits or retries occurred
  during the run. Old campaigns and production/hosted prompts were unchanged.

## Preliminary independent field-level review

| Case | Baseline | Source-only | Main reason |
|---|---|---|---|
| No source policy | Fail | Pass | Baseline adds policy and an unsupported second workflow; candidate preserves empty policy fields and exact outputs. |
| Explicit approval and decision record | Fail | Fail | Both preserve real approval/record steps, but convert the non-goal “does not publish” into a prohibited-action rule. |
| Conditional approval | Fail | Fail | Baseline moves approval before analysis; candidate preserves the condition/exception in metadata but omits the ordered conditional approval action. |
| Hostile quoted requirement | Pass | Fail | Candidate is mechanically rejected with no surviving workflow; rejected raw output is not retained, so its cause is unknown. |

Both score **1/4** under the frozen all-field criteria. The planned 4/4 acceptance
condition was **not met**. This is not a general extraction improvement and does
not authorize default prompt promotion. The independent review is agent-only,
not human validation or the production Pro Reviewer. No Skill was generated.

Additional nuances retained in the review: the candidate correctly keeps the
source-required reviewer decision record (it does not blindly delete all records),
and correctly keeps the external-distribution condition plus internal-analysis
exception. Its unresolved-outcome description is also classified as a failure
mode, although the source requires retaining unresolved issues. These observations
do not change the failed case grades.

## Requests and costs

| Slot | Input tokens | Output tokens | Mechanical outcome |
|---|---:|---:|---|
| baseline:policy-absent | 2086 | 1457 | 2 admitted workflows |
| source_only:policy-absent | 2256 | 702 | 1 admitted workflow |
| source_only:policy-explicit | 2617 | 811 | 1 admitted workflow |
| baseline:policy-explicit | 2447 | 1290 | 1 admitted workflow |
| baseline:policy-conditional | 2136 | 1021 | 1 admitted workflow |
| source_only:policy-conditional | 2306 | 638 | 1 admitted workflow |
| source_only:policy-injection | 2273 | 568 | mechanically rejected |
| baseline:policy-injection | 2103 | 965 | 1 admitted workflow |

Total: **18,224 input + 7,452 output = 25,676 tokens**, eight requests, no unknown
outcomes. Estimated cost **CNY0.096064**, using uncached peak Flash input/output
rates 2/8 per million tokens from [official pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/).
Together with the immediately preceding real-source pilot, the known estimate is
CNY0.147790. These are token-based estimates, not verified billing charges.

## Verification

- Related tracked tests: 133 passed; repository Ruff passed.
- Private launcher: 12 passed; scoped Ruff passed; independent review green.
- The first launcher implementation reused an HTTP client that the SDK closed
  after each request. This was found before live execution and fixed with a real
  guarded-SDK/MockTransport regression exercising eight distinct clients.
- Full offline suite is still running; its terminal result will be recorded.
- Runtime credentials were selected only by the previously authorized loader.
  No credential contents or raw rejected provider prose entered the report/state.

## Next bounded hypothesis — not retroactive acceptance

The original product plan explicitly avoided making a general extraction benchmark
a prerequisite for the first real artifact. Therefore the next hypothesis is
narrower: can the source-only candidate avoid invented policy on the already
identified real Microsoft prompt-refinement source, which has no stated approval
policy? This does **not** turn 1/4 into a passing experiment.

A separately identified opt-in local preview may test that hypothesis, provided
legacy v3/default/hosted prompts stay unchanged and old state remains readable.
This is a deliberate sequencing change from the local experiment plan's 4/4-before-
integration step: no default/hosted promotion is allowed, and every real candidate
still requires full field-level source review, deterministic qualification, format/
safety checks and independent Pro review before the usefulness comparison.
The known false-negative and claim-type failures remain open. No source text,
WorkflowSpec, descriptor or generated Skill may be manually repaired to pass.

The local v4 implementation received independent code review. Fresh focused
tests covering v4, v3, the frozen trial and export passed (133 tests); repository
Ruff passed. Tests include exact 65,536-byte / plus-one boundaries for both
providers and the historical source-only prompt digest. A read-only check also
re-admitted the preserved real v3 descriptor under the changed code. These checks
establish local compatibility and guards, not model fidelity or usefulness.
