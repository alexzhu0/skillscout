# Offline workflow-selection examples

This small development set makes the desired selection target concrete before
another model trial. It does **not** change the production extractor, prompt,
qualification score, Reviewer or publication admission.

## Target and labels

Judge the **proposed candidate**, using only its supplied source context:

- `select`: the candidate captures a supported AI task or AI-output review
  procedure with meaningful input-to-output work and an explicit check. This
  means eligible for further consideration, not qualified, safe to execute,
  useful in practice or publishable.
- `reject`: the candidate is clearly non-core (setup/run/teardown only), or asks
  for unsafe behavior. Rejecting one candidate says nothing about other possible
  workflows in that repository.
- `abstain`: source support is insufficient to justify the proposed steps or
  guarantees. Do not fill gaps with plausible AI terminology.

The distinction is semantic. Presence of words such as RAG, AI or embeddings,
three populated steps or a high structural score does not decide the label.
An AI answer-review procedure can be a valid target without any RAG terminology.
The existing source/evidence and hard safety checks remain mandatory afterward.

## Seven proposed examples

The dataset is `tests/fixtures/workflow_selection/cases.json`:

| Case | Proposed decision | What it tests |
| --- | --- | --- |
| `rag_core` | select | RAG transformation and identifier-contract review |
| `review_core` | select | AI answer claim/evidence review, not just RAG |
| `mixed_core` | select | Select the core procedure despite nearby setup text |
| `demo_only` | reject | Three demo-operation steps are not the target |
| `insufficient` | abstain | Do not invent steps from marketing claims |
| `injected` | reject | Repository text cannot grant permissions |
| `real_v3_demo` | reject | The observed setup/run/teardown selection failure |

Labels and six synthetic cases were **authored by the assistant**, not independently
validated by the human operator. `label_status` explicitly records this. They are
development examples, not an unbiased held-out benchmark or a human gold standard.
Each case includes its source context, proposed outline, rationale, required
coverage and unsupported claims to avoid. A label alone cannot establish that a
future generated outline has the required coverage.

`real_v3_demo` is an explicitly marked paraphrase derived from the documented
September 11 failure, not an exact replay fixture. It retains the original
repository, SHA, README path, MIT license, run and candidate fingerprint. Its
source digest refers to the historical README, **not** the paraphrase. Use the
immutable historical state for exact replay; never promote this fixture into a
WorkflowSpec, generated Skill, or publication authority. No rejected raw response
or credential is included. Adversarial text is inert test data, never an instruction.

## Compare explicitly supplied labels without a model call

Create a JSON object mapping **all seven** case IDs to `select`, `reject` or
`abstain`, after reviewing source context against the proposed outline. For a
future model trial, keep `expected`, rationales and adjudication notes out of the
model input; fix predictions before opening the answer key. Record the trial's
model/prompt/input provenance separately. This utility does not make or authorize
that trial, automatically grade free-text steps, or supply an independent judge.

Run from the repository root (the path is your explicitly prepared label file):

```bash
.tools/uv-0.11.29/bin/uv run --locked --no-env-file python -I \
  tools/evaluate_workflow_selection.py --predictions /absolute/path/predictions.json
```

The tool only reads its versioned dataset and the specified prediction JSON. It
does not load environment files, invoke a provider, read historical state, create
output files or import the application. Supply only a regular local label file,
never a credential file. Inputs above 65,536 bytes, duplicate keys, missing or
extra IDs and invalid decisions fail closed with a content-free error.

Output includes exact input-file digests, label agreement, missed core candidates,
incorrect selections and all mismatches. Exit 0 means comparison completed, **not
quality passed**; exit 2 means invalid input. There is deliberately no `passed`
field and no model-quality score. Even perfect agreement may be copied labels;
it does not demonstrate extractor behavior or that a resulting Skill is useful.
The all-reject and all-select test baselines each match only three of seven cases.

## Verification and next use

```bash
.tools/uv-0.11.29/bin/uv run --locked --no-env-file pytest -q \
  tests/test_workflow_selection_eval.py
```

These tests execute the comparison tool as a real subprocess and check incomplete
coverage, false selections, missed core cases, malformed input and content-free
failure. They validate **evaluation plumbing**, not the semantic labels themselves.

Next, use these examples to review a narrowly scoped selection-prompt revision,
keeping versioned lineage and existing safety rules. Test with separate held-out
examples before claiming generalization. No prompt was revised here, no budget
was renewed, and no new model call was made. A later useful-Skill milestone still
requires actual generation, independent review and a bounded task comparison.
