# September 11: one real v3 extraction, qualification blocked

## Result

The operator separately approved **one** new DeepSeek Flash extraction request,
then explicitly authorized a runtime-only read of the designated local credential
file's `DEEPSEEK_API_KEY`. No other file variables were loaded into the child.
Credential values were not displayed, logged, put in state, or committed.
The invocation used a fresh private trial directory and an exclusive start marker;
it was not a replay or replacement of a historical failed run.

On source `4be61ed76ba53505f49377360a59825f5516fd7d`, run
`cadb2de7fbaf47cf8f5588034f3ad784` made one real `deepseek-flash`
request and finished with extractor outcome **`extracted`**. Two workflows were
proposed: index 0 was dropped for `step_evidence_not_declared`; the remaining
workflow passed extraction boundaries and was canonically exported locally.
No rejected workflow title or raw rejected response was retained.

This is a successful extraction/source-export milestone, **not** a generated,
qualified, reviewed or useful Skill. A subsequent read-only invocation of the
existing pure qualification checks rejected the surviving workflow.

## Bound source and request evidence

| Fact | Observed value |
| --- | --- |
| Repository | `restatedev/examples` |
| Commit | `f339b97a8cd0e14bae51f242d9957e68a0f4ca14` |
| README | `python/end-to-end-applications/rag-ingestion/README.md` |
| License | MIT, confirmed at the pinned SHA |
| Read budget | One README, 2,821 bytes; zero source-code files |
| Blob SHA | `32abb2d883da33a8f794edb1f24aed1a92ce4fe3` |
| Content SHA-256 | `0a64862343e1e28f51c62ca13f3a72d9aff37c41050e46f33bb257a19be31cd6` |
| Prompt | `extract-local-evidence-select-v1` |
| Scope | `local-readme-v3` |
| Retry identity | `retry-local-readme-v3-once+extract-correction-policy-v1` |
| Actual / configured model | `deepseek-flash` / `deepseek-flash` |
| Provider request ID | `86747feb-707a-44dc-b7bd-6e69ec792be7` |
| Token usage | 3,581 input + 1,710 output = 5,291 total |
| Semantic latency | 7,967 ms |
| Extractor attempts | One, no retry or correction |
| Catalogue | 17 entries; not truncated |
| Exported descriptors | One; zero remote writes |
| Phase 3 runs | Zero |

The capability suffix in the retry identity does not authorize a correction:
the v3 policy still has one attempt and the durable record contains exactly one
extractor attempt. No generator, semantic Reviewer, comparison, or publication
request was made. No source-repository code or dependencies were executed.

## Candidate and offline qualification

The surviving workflow is **Run and tear down the local RAG ingestion example**,
fingerprint `sha256:7f8e7b844d19072335d8b1032151a8066428d08485acbf4ebb2c409c728e753f`.
It describes preparing dependencies, running the demo and uploading a file, then
tearing the demo down. This is a summary of model-produced data, not execution
permission or an instruction for this project to perform those actions.

The existing `qualification-policy-v1` checks gave 95 points against a threshold
of 75, but **hard-failure rules override the numerical score**. Reasons:

- `dependency_installation`
- `approval_required_without_named_step`
- `safety_controls_incomplete`

This was a pure read-only inspection of a re-admitted local WorkflowSpec, not a
persisted Phase 3 qualification run or a fabricated authority/report. The default
hosted/publication source also rejected the local descriptor, as required.

Controller assessment: the candidate is mostly demo setup/run/teardown guidance,
not yet a sufficiently useful description of the core reusable AI workflow.
Source binding and exact quotation do not prove semantic usefulness. Do not spend
generation/review budget on this candidate or weaken safety checks to pass it.
The rejected index 0 was not retained, so its intended workflow cannot be inferred.

## Verification and immutable local records

- Preflight on the same source: 149 tests passed (v3, catalogue and legacy local
  output tests); isolated installed CLI import passed.
- Synthetic launcher checks verified the environment allowlist, exact arguments,
  one-shot refusal and absence of synthetic credentials from output/result data.
- The actual child finished with exit 0; success was established from the stored
  extractor outcome and verified export, not from that exit code alone.
- The source bridge successfully re-admitted the exported local descriptor.
- Read-only SQL confirmed one extractor attempt and zero Phase 3 runs.
- State directory: `.tmp/single-skill-v3.moFKdR/` (private and Git-ignored).
- Database SHA-256 after inspection/export:
  `354592c416381f2b587e7255ce82cc32fda030a2826107f0ad16f4508d86b1f3`.
- Descriptor SHA-256:
  `dc9317bc163d48c80489a5526c5519164ce6a147b9ee409b8fb17790c85a9e55`.
- Extractor output digest:
  `sha256:f182397e85f1817f2ec1a13ec139ffa4c99ee2657b974fa8dc4666378d09c056`.

An independent read-only audit reproduced the source/attempt/token facts, hashes,
local admission, pure qualification failure and default-source rejection, with no
blocking documentation discrepancy. It did not inspect credentials or launchers,
rerun the preflight suite, or make a semantic Reviewer request.

The old pilot stays terminal at **3/3**. This separately approved v3 trial is now
terminal at **1/1**. Do not rerun either launcher, clear state, or borrow unused
generation/reviewer slots for extraction. The next decision is how to improve
workflow selection using this failure evidence; no further live request or
implementation change is authorized by this report. PR #40 remains a developer
Draft, not a generated Skill PR or Phase 6 acceptance result.
