# First useful Skill loop: stopped at held-out evaluation

Date: 2026-09-14. Campaign: `useful-skill-loop-20260914`.
Outcome: **heldout_failed**. The useful-Skill goal is not achieved.

## Actual result

| Evaluation | Baseline | Frozen r1 |
| --- | ---: | ---: |
| Development semantic cases | 5/7 | 7/7 |
| Held-out semantic cases | 3/6 | 5/6 |
| Held-out positive cases | 1/3 | 2/3 |
| Held-out negative outcomes | 2/3 | 3/3 |

All 26 DeepSeek Flash requests completed with decided ledger records; none is
in flight. Actual reported usage totals 51,599 tokens. No retry or replacement
slot was used. Development used 14 requests; held-out used 12. The remaining
23 allocated slots are unused and do not authorize another attempt after this
terminal stop. There were no real-repository artifact, generation, semantic
Reviewer, usefulness-comparison, publication, push or merge operations.

Inputs are independently curated synthetic source-only cases, not real
repository extracts and not human gold truth. These small samples do not
establish general accuracy, statistical significance or production readiness.
Negative empty outputs show non-admission, not a general proof of resistance
to prompt injection. All evidence snippets checked against the frozen source.

## Why the candidate failed

Held-out h06 describes auditing an AI-drafted support reply with **both the
customer message and current policy**, preserving confirmed facts and mapping
each revised claim to evidence. The candidate's third step and second output
narrowed that mapping to **policy-only evidence**. Customer-specific facts need
customer-message evidence; silently excluding that source changes the workflow.
Its assumption also treats the customer message as containing facts that must
remain unchanged, whereas the source protects only **confirmed** facts.

The independent scorer's preliminary 6/6 was challenged by controller review
of those exact fields. Source-based adjudication corrected it to 5/6 before
admission. The preliminary verdict is superseded; this record does not conceal
that review correction or treat mechanical validation as substantive proof.

This is a semantic fidelity failure, not a connection, credential or JSON error.
R1 improved demo-lifecycle exclusion, but does not reliably preserve evidence
scope and uncertainty. Existing qualification checks did not detect h06:
candidate h02/h06 scored 100 with no hard failure; h05 scored 95 with no hard
failure and a verifiability-incomplete reason. Those checks are not a substitute
for faithful content or independent human review. No validator was relaxed.

## Stop and implementation evidence

R1 was frozen in commit `2c99dd6`, before controller access to held-out sources.
The bounded held-out route was implemented in `91f8bf5` and independently
approved. Fresh related regression: **239 passed**; scoped Ruff passed.
No dependencies, production CLI or hosted workflows were added or changed.

Private state and detailed scores remain under
`.tmp/useful-skill-loop-20260914/`; STOP.json records this terminal result.
The private launcher now rejects before reading credentials; a local denial
check made no provider request and the ledger remained at 26 decided rows.
Preserve the frozen prompt, original datasets and ledger; do not reset, rerun,
reselect a prompt or tune on this held-out set in the same campaign.

## Narrow next step

Treat h06 as a newly observed development regression in any separately approved
future experiment. Investigate preserving all evidence sources and the distinction
between asserted and confirmed facts. Keep the same safety and publication
boundaries. A new live experiment needs fresh held-out cases and an explicit new
budget; no new runtime platform or production feature is justified by this result.

## Offline repair preparation — 2026-09-15

With separate user approval, prepared an additive r2 prompt in the existing
experiment runner. It preserves source-specific evidence roles and uncertainty
across every authored field; it also forbids broadening an explicitly restricted
source. R1 and baseline request instructions remain unchanged. This is not a
change to production extraction defaults or a new live-campaign authorization.

Added `tests/fixtures/workflow_selection/fidelity_regressions.json`: the observed
h06 failure, a log/interview hypothesis case, and an explicit policy-only
counterexample. These are development checklists, not fresh held-out evidence
or automated semantic grades. The old held-out dataset remains unchanged.

Two new tests first failed while r2 was unavailable, then passed: recorded HTTP
requests carry the added instructions without changing other request fields;
the frozen campaign rejects r2 before any request. Related regression: 241
passed; scoped Ruff passed. These tests verify wiring and isolation, not whether
DeepSeek follows the instructions. No new provider request was made, no secret
was read, and the historical ledger remains at 26 decided requests with its
terminal stop intact. Model-level fidelity still requires a separately approved
fresh evaluation; do not count the remaining old slots as available budget.
