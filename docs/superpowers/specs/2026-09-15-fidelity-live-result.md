# Fidelity live comparison — 2026-09-15

## Outcome

The bounded comparison completed, but **r2 did not meet the required 6/6
semantic-fidelity threshold**. Do not promote r2 to the production prompt or
interpret this as useful-Skill acceptance. No Skill generation, publication,
GitHub write, merge, or source-code execution occurred.

The protocol and source hashes were frozen in commit `58fe109`; implementation
was `6034cff`. All twelve slots in `fidelity-check-20260915` are decided. There
were eleven mechanically admitted outputs and one `no_workflows` result
(`r2:h03`). No retry or additional request occurred. The old campaign remains
at 26 decided requests and was not changed.

## Mechanical verification and cost

- 57 launcher/shared-runner tests passed after the live comparison.
- All 71 emitted evidence excerpts exactly matched their corresponding source.
  Exact excerpts and admission do not establish semantic fidelity.
- Provider: DeepSeek; requested model `deepseek-flash`, thinking disabled,
  no tools, SDK retries disabled. This is a live API comparison on synthetic
  source texts, **not a fresh GitHub discovery run or an end-to-end Skill test**.
- Input: 21,554 tokens. Output: 8,258 tokens. Total: 29,812 tokens.
- Sum of measured request latency: 52,261 ms (not total task wall time).
- Conservative cost estimate: **CNY0.109172**, using peak uncached input
  CNY2/million and output CNY8/million from
  [official pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/).
  This is not a wallet debit measurement; caching/off-peak billing may be lower.
- Results digest: `sha256:d883376c71656d876384b07049e46d27df363cc32a4c63df34d2984340c856b4`.
  It hashes UTF-8 compact sorted-key JSON of `(slot,state,result_json)` rows
  in reservation rowid order, keeping `result_json` as its stored string.
- SQLite digest: `sha256:0353ffbddfed155118c4082384dd8754f566d907de9e35a424ea3723a7b48dd6`.
  Private ledger: `.tmp/fidelity-check-20260915/runtime/ledger.sqlite3`.

## Directly observed failures

Independent source-based review, reconciled with controller inspection, scored
**r1 3/6 and r2 2/6** under the frozen all-authored-fields criterion:

| Case | r1 | r2 |
| --- | --- | --- |
| Customer message / policy | Fail: policy-only claim mapping | Fail: assumes evidence sufficiency |
| Observations / hypotheses | Pass | Pass |
| Explicit eligibility evidence restriction | Pass | Fail: unsupported applicability expansion |
| Fresh h01: incident review | Fail: assumes evidence sufficiency | Fail: assumes evidence sufficiency |
| Fresh h02: vendor evidence | Fail: restricts follow-up without support | Pass |
| Fresh h03: product prioritization | Pass | Fail: no workflow returned |

These are assistant judgments on synthetic cases, not human-validated gold.
The r2 eligibility failure is a strict applicability judgment: the output adds
“or decision summary” to a source describing an eligibility reply. Even treating
that borderline expansion as acceptable would raise r2 only to 3/6, not 6/6.

The independent scorer initially passed r1:h02. Controller review identified
its assumption, “Follow-up requests are limited to targeted clarification rather
than new evidence generation.” The source does not exclude requesting missing
evidence. The scorer agreed to correct that row; the table includes this
correction rather than silently retaining the initial favorable score.

The original customer/policy mistake recurred in r1: its output mapped
“each revised claim to corresponding policy evidence,” although the source
only restricts promises to policy support. r2 removed that narrowing in its
steps, but added the unsupported assumption: “Grounding can be determined
solely from the policy, message and draft without additional sources.”

On fresh incident case h01, r2 assumed the records “are sufficient to
reconstruct the sequence and test causes.” The source explicitly asks to
identify missing evidence and does not guarantee sufficiency. An assumption
field does not authorize adding that guarantee.

On fresh product-prioritization case h03, r1 returned a workflow and r2
returned none. The frozen label expects selection. The saved result establishes
the omission, not the model's internal reason for omitting it.

These findings support neither another prompt promotion nor a claim that more
prompt instructions reliably solve fidelity. One output per profile/case is
too small to establish a stable win rate. Preserve these failures as development
evidence; no tuning, extra campaign, or automatic spending follows this run.

## Fresh sources retained for review

The independent curator created these after the prompt freeze, without reading
the prompts or earlier cases. Full source/checklist bytes are retained privately
at `.tmp/fidelity-check-20260915/fresh-cases.json`, bound by the protocol hash.
Source text only entered model requests, not the labels or checklists.

### h01

For each service incident, have the AI reconstruct a timestamped sequence from
alert records and operator notes, use dashboards to quantify customer impact,
and use ticket histories to test suspected causes. It should flag contradictions,
separate observed facts from hypotheses, assign confidence to each causal link,
identify missing evidence, and draft a review with corrective actions tied to
named owners and verification signals.

### h02

Review an AI vendor by mapping requirements to evidence roles: questionnaires
record vendor claims, audit reports support control design, penetration findings
expose tested weaknesses, and contracts establish commitments. Questionnaires
support only what the vendor claims, never control effectiveness. Mark conflicts,
freshness gaps, and unavailable evidence; rate each requirement with confidence
and request targeted follow-up.

### h03

To prioritize product problems, have the AI extract user pain from interviews,
count recurrence with support tags, and compare themes with telemetry showing
where workflows stall. Roadmap notes provide delivery constraints, not user
demand. Cluster only traceable observations, preserve dissenting examples, note
sampling and tagging uncertainty, and rank opportunities with evidence summaries
and reasons for low confidence.

## Follow-up: closed rejection diagnostics and two-call retest

After the user approved the diagnostic follow-up, the experimental runner gained
one optional `rejection_diagnostic` field for `no_workflows` results only. It
records `reason_present` and a bounded list of `untrusted_lexical_hints` from five
fixed English topic vocabularies. It does not retain rejection prose, summaries,
URLs, credentials, or arbitrary model strings. Unsupported language can produce
no hints. Negation is intentionally not interpreted: a mentioned topic is not
a semantic classification, causal conclusion, or instruction. The diagnostic
does not affect selection, retries, or admission. Existing output schemas,
prompts, production adapters, and historical records were not changed.

Six HTTP-fixture cases first failed on the missing diagnostic, then passed with
the implementation. The related selection suites passed **149 tests**; scoped
Ruff passed. Independent code review found no blockers. The implementation adds
19 lines to the experimental runner and introduces no dependencies.

A separate `rejection-check-20260915` ledger admitted exactly two requests on
the already-known h03 development case: r1 once, then r2 once. Same input digest
`sha256:404e5cd51699abb0c60f126bde146bba63efd87ad5a89dd2f7e2dd64039aa065`,
same frozen r1/r2 prompt digests, same `deepseek-flash` request configuration.
This is diagnostic reproduction, not a new held-out evaluation.

- r1: mechanically admitted one workflow; no rejection diagnostic.
- r2: `no_workflows`; reason present; hints `evidence`, `read_only_scope`,
  `execution`. No rejection prose was persisted.
- Both slots are decided; no retries. Total usage: 3,683 input + 1,010 output =
  4,693 tokens. At the same conservative pricing above, estimated CNY0.015446,
  not measured wallet spend.
- The old twelve-request ledger's SHA-256 was verified unchanged.
- New private ledger SHA-256:
  `307ff2ece86ea05c604fd105bc9d3c2f3a49739e621e7c2f97714c4c185b05b6`.

The repeated omission plus topic hints supports investigating whether r2
overrestricts a read-only analysis workflow as execution. It does **not** prove
that mechanism: the hints omit context, and r1 shares the read-only constraint.
No production prompt was promoted, no new fix was inferred successful, and no
additional comparison or publication automatically follows this retest.
