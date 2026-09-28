# September 28 observed real generation — closed failure

## Outcome

One real DeepSeek generation request completed in 4.273 seconds. Requested and
returned model IDs were both `deepseek-flash`. Qualification passed; generation
failed strict schema validation. The content-free diagnostic reports
`quotes / string_too_long`. No accepted Skill, rendered package, format/safety
result, Reviewer request, usefulness request, or publication resulted.

This is the first retained field-level evidence for this failure family. The
diagnostic deliberately collapses nested paths: it does not establish whether
the overlong string was quote text (120-character limit) or its source path
(512-character limit). Rejected text was not retained or repaired. The prior
September 20 and September 25 outcomes must not be retroactively assigned this
cause.

CLI exit 0 means the pipeline recorded a terminal result, not that the candidate
passed: terminal `outcome=generator_schema_failure`, `eligible=false`,
`package_digest=null`, and `review_not_reached_generation_unsuccessful`.

## Frozen trial and execution

- Trial: `source-faithful-observed-20260928`; implementation `43dde11` (full
  checkout commit bound in the local frozen manifest).
- Source: `danielmiessler/fabric`, commit
  `b682dad740f24e85ce9a48d23babc6780dd476ac`, MIT,
  `data/patterns/summarize/system.md`.
- Source SHA256: `29d393bf16f9a89464ef1f734cfd523e5949c01e5e580039540fd65823bc4a06`.
- Reused immutable Phase 2 evidence and the original exported descriptor; no new
  extraction, manual semantic editing, production-code change or schema relaxation.
- Existing CLI: `build-candidate --deepseek-current-flash --single-attempt
  --source-faithful-generation`, fresh state/output. Existing 240-second child
  deadline and SDK zero-retry policy retained.
- Reserved maximum: generation 1, independent-context Reviewer 1, conditional
  comparison 9. Invoked: **1 / 0 / 0**. Trial closed; unused slots are not reusable.
- Reviewer alias routing is accepted by the user. Separate requests and contexts
  provide workflow independence; they do not establish cross-model independence.
- Only the existing hash-bound authorized runtime loader accessed
  `DEEPSEEK_API_KEY`. No credential, original error body or rejected model content
  was printed or saved.

Request ID: `bcdd9f47-c6ec-4668-a736-d21c30e7561c`.
Usage: **5,316 input + 887 output = 6,203 tokens**.
Estimated cost: **CNY0.017728**, using peak uncached input2/output8 per million
from the [official Chinese pricing page](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)
(search index checked September 28; direct fetch timed out). Not a provider bill.
Known cumulative estimate is **CNY0.265724**, plus the unresolved September 25
charge. Before dispatch, its entire CNY20 reservation was retained and another
CNY20 reserved: conservative allocation **CNY40.247996**, below CNY100.

## Investigation and verification

The September 25 child exited1 rather than being killed at its outer deadline.
Its stdout/stderr were discarded. SDK timeout/connection errors and model-ID
mismatch share the same durable unknown-outcome classification, so its original
cause cannot be reconstructed from retained evidence. The SDK defaults here are
connect5/read600 seconds; the launcher deadline is240 seconds. That mismatch is
a future observability risk, not proof of the historical cause. No timeout change
was made speculatively.

The new local observer wraps exactly the existing SDK call, passes its response
or exception through unchanged, and writes only closed outcome/model categories,
bounded token counts and elapsed time. Independent review found sink-failure and
malformed-model interference; failing tests reproduced both and minimal fixes
passed. The initial pre-dispatch manifest is preserved separately; the corrected
observer was frozen again before any request.

- Private observer/controller checks: **6 passed**.
- Combined provider, generation-diagnostic and private checks: **90 passed**.
- Private Ruff: passed. No production source/dependency change in this trial.
- Previous full product suite remains historical: **3053 passed,3 skipped** at
  `43dde11`; a fresh whole-product run was not performed for local instrumentation.
- No retry, altered quote, relaxed length limit, changed prompt, or success-picked
  replacement trial was performed.

## Evidence hashes

Local root: `.tmp/source-faithful-observed-20260928/`. SHA256 values:

| File | SHA256 |
| --- | --- |
| config.json | `200920fbdfc4be104d172e5b34326d15389634227e5823640385208e1dc241cc` |
| run-once.py | `adf2ea68e40e90880337890144da4d09ba867b3f5497a49233554922be3a62cb` |
| observer.py | `bd5beae5769931ab5bb0b0bfaae82b2a92be7758be8fa8dfe27802203ec17bd9` |
| runtime/frozen-manifest.json | `838c17557dcb1483da15acd2cc7a5ee3b1290aea246f8ffcaf018a9f450491e7` |
| runtime/started.json | `565cb9cf004094ab19c4adfded4251d8692c7c02348364b94bcccea916e90328` |
| runtime/provider-event-1.json | `3b50ce8c9d8f56b3a2aff4e86f0e606c97728d790da71690b6d2e204daab80cc` |
| runtime/invocation-result.json | `06dfd7923146b332608598f5fec0539e11761f5e56e7b1a6208bd4c5f0596eac` |
| runtime/output/generation-diagnostic.json | `2dcae52ad47cadecdb0133e3aa56c3883b853397728a2a3c2141233e21b963d0` |
| runtime/output/candidate-terminal-summary.json | `60055ea7450638817e4622137210e3a450c30c2eb087651a36fddf426f5dd87e` |
| runtime/phase3.db | `deb14266e84d55ca8e9ae2a74144bc47d86de74a25ee67ee72d4a058809c3516` |

## Next falsifiable hypothesis

Optional quotations add avoidable generation constraints to a documentation-only
summary Skill. A separately frozen local experiment could ask for `quotes=[]`
and paraphrased guidance, while retaining provenance, source checks and every
existing validator. This is a proposal, not an implemented correction or a claim
that quote text was the specific failing nested field. Do not truncate or remove
fields from this failed response. First obtain one fully accepted package; only
then spend the nine requests on usefulness. Broad discovery and Phase6 remain out
of scope.

Ruling: reused immutable extraction as regression input, not a new-source test;
cost is limited generalization. Kept observer local and best-effort; if metadata
cannot be written, evidence remains unknown rather than altering the model result.
Deferred: generic CLI error projection and timeout-policy redesign; neither was
needed to establish this completed response's schema rejection.
