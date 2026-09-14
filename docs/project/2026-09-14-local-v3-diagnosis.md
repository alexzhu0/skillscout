# September 14: offline diagnosis of the v3 candidate

## Outcome and scope

The next bottleneck is **semantic workflow selection and usefulness**, not a
broken provider connection or loss of all core RAG evidence. The existing safety
qualification correctly stops the surviving demo-operation candidate. No product
code, prompt, schema, safety rule, workflow or historical state was changed.

This investigation used local recorded outputs, pure deterministic functions and
a read-only retrieval of the exact public README to reconstruct transient input.
It made zero provider calls, read no credentials, ran no source-repository code,
and did not generate, review, publish or merge a Skill. It is not a new Phase 6
campaign or a replay of the exhausted trial.

Baseline: `7640ee1daf2d6ced6af4bf0fc27b9e21b85cd830`, Draft developer PR #40.
The [September 11 report](2026-09-11-local-v3-extraction.md) remains the historical
record of the one real extraction and its authorization.

## Reconstruction: the core workflow was available

Source: [pinned README](https://github.com/restatedev/examples/blob/f339b97a8cd0e14bae51f242d9957e68a0f4ca14/python/end-to-end-applications/rag-ingestion/README.md).
The retrieved bytes matched the recorded 2,821-byte input and SHA-256
`0a64862343e1e28f51c62ca13f3a72d9aff37c41050e46f33bb257a19be31cd6`.
Rebuilding with the unchanged scope and `build_evidence_catalog` produced exactly
the recorded audit: 17 entries, not truncated, digest
`sha256:9eb5f3627f312230b8a0c0589a6c122f005880a96e7f59fc927d5a440b3607bf`.

| Evidence | Original README lines | Role in the available input |
| --- | --- | --- |
| `e0007`–`e0009` | 12–14 | Upload event, durable handling, document retrieval, snippet extraction, embedding computation and vector storage |
| `e0011` | 48 | Local environment/dependency setup |
| `e0012`, `e0016` | 56, 73 | Running-example heading and upload prompt |
| `e0017` | 81 | Teardown heading |

The survivor cited the latter three groups in its three steps, not the core
processing entries. This disproves the narrow hypothesis that filtering removed
all core workflow information. It does **not** prove the remaining short overview
supports every precondition, failure mode or detailed reusable procedure that a
good Skill needs. Code fences, links and other ineligible lines stayed excluded.

The other proposal was rejected for `step_evidence_not_declared`. Its title and
raw rejected content were not retained. We cannot claim the model failed to
propose the core workflow at all, nor claim that repairing this rejected proposal
would have produced a useful Skill.

## Why the current result is possible

1. **The local v3 prompt has a broad target.**
   `src/skillscout/adapters/openai_extract.py:47` asks for reusable agent workflows
   and carefully defines evidence and forbidden-string constraints. It does not
   explicitly distinguish an AI task's transformation from demo setup, launch and
   cleanup. This is a confirmed specification gap; its causal effect on future
   model behavior is still a hypothesis, not a measured prompt improvement.
2. **Exact evidence is not semantic adequacy.**
   Catalogue materialization establishes source identity, exact quotation and ID
   membership. A real heading can therefore be valid evidence mechanically while
   providing weak support for a detailed instruction. The deterministic checks
   do not establish that each claimed step follows from the quoted text.
3. **The 95 points are not a usefulness score.**
   `src/skillscout/domain/qualification.py:406` scores fields, step count, reference
   consistency and bounded safety predicates. Its reusability heuristic checks
   populated lists and limited source-specific phrasing; it does not judge task
   transfer. Evidence sufficiency checks references and nonempty support claims,
   plus the model's confidence floor, not semantic entailment. A full-looking
   demo workflow can receive most points without demonstrating AI task value.

No evidence here establishes that Flash is inherently unsuitable or that a
stronger model, larger input budget, more repository files or another live retry
would solve the problem. None was attempted.

## Qualification is behaving as written

Pure re-evaluation reproduced 25 + 20 + 20 + 25 + 5 = 95, with hard failure:

- `dependency_installation`: the candidate's first instruction asks to install
  dependencies. Removing shell syntax does not make this action admissible.
- `approval_required_without_named_step`: upload is a side-effect action and
  none of the steps names an approving human/operator.
- `safety_controls_incomplete`: the same missing approval control loses five
  safety points. This reason is not itself a hard-failure code; the preceding
  two reasons are. The high total cannot override them.

Adding a cosmetic approval sentence would not cure dependency installation or
turn demo operations into a useful AI workflow. The recorded candidate must not
be rewritten into a new apparently model-produced success.

## Recommended next bounded increment

Keep the existing source/evidence boundary and hard safety checks. Before any
new paid trial, define and offline-test the **selection target**:

- A candidate should explain an evidence-supported AI task: input, meaningful
  transformation, expected output and a way to check that output. Installation,
  starting services and teardown alone are not the target.
- Use a small human-labelled evaluation set covering a core workflow, demo-only
  instructions, mixed documentation, insufficient evidence and injected text.
  Include this real rejected candidate as a negative example. Curated expected
  outputs are fixtures, never live extraction evidence or publishable candidates.
- Keep deterministic schema/source/safety tests separate from semantic quality
  labels. Do not try to prove usefulness with a keyword score or inflate the
  current 95-point result. A recorded-response test can validate plumbing, not
  demonstrate that a changed prompt improves a real model.
- Any later prompt change must have its own version and immutable lineage; it
  must not silently alter historical v3 semantics or renew exhausted budgets.
  A new bounded live comparison is a separate decision after offline checks.

This is a recommended follow-up, not an implemented prompt change or an approved
new provider request. The product milestone remains one genuinely useful,
source-grounded Skill, followed by a bounded comparison against no Skill and the
original README. No new approval infrastructure is needed for this diagnosis.

## Verification

- Fresh scoped suite: **174 passed** (`test_evidence_selection.py`,
  `test_qualification.py`, `test_local_evidence_preview.py`). This is not a full
  suite rerun or live semantic quality evaluation.
- Read-only reconstruction matched the stored catalogue audit exactly and mapped
  every surviving step's selected evidence back to its original line.
- Pure qualification reproduced all five scores and the three reason codes.
- An independent read-only subtask replayed qualification from SQLite and checked
  the exact field predicates and tests. It agreed that the safety veto is correct
  and the numerical rubric does not establish semantic usefulness; it made no
  network/model requests or file edits. The controller separately verified the
  catalogue reconstruction and ran the scoped suite.
- The trial database SHA-256 remained
  `354592c416381f2b587e7255ce82cc32fda030a2826107f0ad16f4508d86b1f3`.
- The one-off diagnostic initially used the wrong strict Python-object parsing
  entry point for JSON arrays; switching to `model_validate_json` made the
  diagnostic complete. No product validator or recorded payload was changed.
- Old pilot 3/3 and separately approved v3 trial 1/1 remain exhausted.
