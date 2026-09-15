# First real useful Skill pilot: stopped on source fidelity

## Conclusion

The approved pilot ran once against a real public Microsoft README. Extraction
returned one schema-valid, source-bound workflow. Independent field-level review
rejected it for unsupported output and approval obligations. No Skill was built,
no semantic Reviewer was called, and none of the nine usefulness comparisons ran.
This is a completed failed trial, not proof of usefulness or Phase 6 acceptance.

## Frozen scope and evidence

- Plan: [approved implementation plan](../plans/2026-09-15-real-useful-skill.md).
- Frozen inputs: [manifest](../../../config/previews/real-useful-skill-20260915.json).
- Implementation baseline: `58aa4219dee6c6858ed7601304ddeb89ebfefcd8`.
- Invocation checkout: `e2ababa18d931264c8ebe82fe155e427ece3d216`.
- Three repositories screened, one eligible; no replacement sources added.
- Microsoft `generative-ai-for-beginners`, commit
  `c9657f3fdb6e4f50a168b1d026eadf4cda2f0d07`, MIT,
  `04-prompt-engineering-fundamentals/README.md`, 44,273 bytes.
- Source SHA-256: `cb859f174d8a08f99b3d0b29b71f0ff5746f20648592bf1d60ecb38991da1f5b`.
- brexhq/prompt-engineering was excluded because the retained 128-entry catalogue
  ends before a usable procedure. anthropics/courses was excluded for its
  noncommercial license. Neither received a model request.
- The Microsoft catalogue also truncates at 128 entries. Independent preflight
  admitted only the retained prompt-design/refinement workflow, not the truncated
  primary-content procedure.

## Actual execution

The private one-shot launcher used the already authorized runtime-only key loader,
an allowlisted child environment, an exclusive fsynced reservation before dispatch,
and fresh local state. It did not expose credentials or invoke source code. It
selected existing local v3, not experimental r1/r2 prompts.

| Fact | Value |
|---|---|
| Phase 2 run | `0da563f8a29a4cc691c36351956911e8` |
| Outcome | scout/filter/reader accepted; extractor `extracted`, one workflow |
| Model | configured and actual `deepseek-flash` |
| Prompt | `extract-local-evidence-select-v1` |
| Request ID | `80944828-3319-4a0e-8ff3-932110496bca` |
| Input / output / total tokens | 18,251 / 1,903 / 20,154 |
| Provider latency | 9,207 ms |
| Workflow fingerprint | `sha256:96b02e1acd688de05e92ef17e2cd8a64d8e71f9ed08a118908e9afd64d9ca210` |
| Extractor output hash | `sha256:f4c595d151a4c5890d49c78ec5ec9c93b61077ae5ae5cd2b8e527809ab225730` |
| Remote writes | 0 |

Estimated model cost is **CNY 0.051726**, using uncached peak Flash rates of
CNY 2/million input tokens and CNY 8/million output tokens. This is a conservative
token-based estimate, not a verified account charge. Rates checked on
[DeepSeek's official pricing page](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/).

Budget used: extraction **1/3**, generation **0/1**, Pro review **0/1**, comparison
**0/9**. There is no second eligible frozen source. Unused slots do not authorize
retries, replacement sources or a new campaign. This pilot is closed.

## Why the candidate is not admissible

The core objective, inputs, iterative prompting steps and stochastic/fabrication
limitations substantially match the source. Exact excerpt restoration worked.
However, exact excerpts do not establish every authored field's truth:

| Field | Finding |
|---|---|
| `outputs` | Adds a required record of iterations/response variations; source describes iteration, not a record-keeping deliverable. |
| `required_approvals` | Adds human review for high-stakes/factual use and responsible-owner authorization for endpoints/API keys; neither obligation is stated in the retained source. |
| `prohibited_actions` | Adds secret-exposure and safety-bypass prohibitions without identifying them as separate operator policy. Sensible safety advice is not a source fact. |
| `non_goals` | Repeats the unsupported high-stakes human-review obligation. |

Existing pure deterministic qualification returned **100/100, no hard failures**.
That diagnostic is not semantic fidelity approval, generation authority or a
persisted Phase 3 decision. It demonstrates why source review is a separate gate.
No fields were manually removed, repaired or re-labelled to obtain success.

One descriptor was exported unchanged for offline diagnostic re-admission while
fidelity review was pending. This is a sequencing deviation from the plan's
fidelity-before-export order, not successful candidate acceptance. The export
made no provider call or remote write and was never supplied to build-candidate.
Its SHA-256 is `c0aac39f9eca023dd883a791f8da70d997e262902972ade6fe5b836e6e9c46cf`.

## Inspect and reproduce the command shape

The preserved local evidence directory is
`.tmp/real-useful-skill-20260915/` in the experimental worktree. It contains
`phase2.db`, `started.json`, `invocation-result.json`, `output/extraction-summary.json`
and `exported/`. Do not rerun its consumed launcher or edit its state.

Read this exact run without credentials or network:

```bash
.venv/bin/python -I -m skillscout.cli inspect-run \
  0da563f8a29a4cc691c36351956911e8 \
  --state .tmp/real-useful-skill-20260915/phase2.db --format json
```

For a separately authorized future trial, the shortest pipeline remains:

```text
extract-repo --subject SUBJECT --readme-path PATH --evidence-selection
  --deepseek-current-flash --state PHASE2_DB --output PHASE2_OUTPUT
export-candidates --phase2-state PHASE2_DB --run-id RUN_ID --output FRESH_EXPORT
build-candidate --candidate ORIGINAL_DESCRIPTOR --phase2-state PHASE2_DB
  --state PHASE3_DB --output PHASE3_OUTPUT --deepseek-current-flash
inspect-run RUN_ID --state STATE_DB --format json
```

Invoke these through the installed `python -I -m skillscout.cli`; inject secrets
only through the approved runtime mechanism. Source-fidelity acceptance must
precede export/build in that future trial. An extraction `completed` status or
an `exported` descriptor is not a generated Skill. The current rejected descriptor
must not be used for the build step. See also [the CLI guide](../../GETTING-STARTED.md#local-extract-build-and-inspect-flow).

## Verification and limits

- Private launcher TDD: missing-module RED, then **10 passing tests**; main
  controller independently reran all ten. Exact CLI/env, reservation-before-key,
  stale artifacts, source/checkout binding and terminal no-replay are covered.
- Independent launcher code review: no blocking findings.
- Independent source suitability review: allowed one narrowly scoped extraction.
- Independent post-extraction fidelity review: rejected unsupported obligations.
- Full repository and private-launcher Ruff: passed; `git diff --check`: passed.
- Full locked offline pytest: **2,962 passed, 3 skipped, 0 failed**, 1,275.66 s.
  Existing skips: the unfinished Phase 6 release-requirement map, and two live
  publication-canary cases gated on explicit protected configuration. They are
  not useful-Skill acceptance evidence. The first two reasons were independently
  confirmed with a focused `pytest -rs` invocation.
- Additional export/Phase 3 acceptance-tool regression run: **62 passed**.
- Final result/README/RELEASE accuracy review: no blocking findings.
- No comparison inputs, scores, Skill-format results or Pro-review approval exist;
  these downstream checks were not applicable after the fidelity failure.
- No production code, schema, permission, provider strategy or dependency changed.
  Private launcher/test code remains ignored local tooling, not a new public CLI.

## Next falsifiable hypothesis, not executed

The present evidence supports a narrower hypothesis: selected evidence IDs preserve
quoted provenance, but the extractor still conflates source-derived workflow fields
with sensible operator policy. A separate offline proposal should test whether
source-absent approvals/deliverables remain absent, while genuinely source-required
approvals survive. That proposal must not relax runtime safety, alter this trial's
outputs, promote experimental prompts or spend another live request automatically.
No human editing of this candidate is requested; any future acceptable candidate
must be generated by the system and independently verified. Human confirmation is
still required for usefulness claims and any publication decision.
