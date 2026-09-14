# First useful Skill Loop Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the bounded runner task; the controller owns experiment decisions and budget dispatch.

**Goal:** Run a small, honest source-to-workflow experiment inside the approved 49-request limit, then pursue one useful Skill only if the evidence admits it.

**Architecture:** One local experiment runner plus focused tests, reusing existing guarded DeepSeek transport and pure evidence checks. A small SQLite slot ledger is not connected to production state. No new production CLI command or platform.

**Tech Stack:** Existing Python 3.13, sqlite3, httpx, Pydantic and locked pytest.

**Spec:** `docs/superpowers/specs/2026-09-14-first-useful-skill-loop.md` (approved in chat; numerical decision rules preregistered before any provider call).

## Global Constraints

- At most 49 external requests: 28 development, 12 held-out, 3 artifact, 6 usefulness; no borrowing or retries.
- No source execution, credentials in files/logs/prompts, live calls by implementers, hosted workflow changes, safety relaxation, automatic publication or merge.
- Keep controller blind to held-out sources/labels until prompt freeze.
- Development extraction uses `tests/fixtures/workflow_selection/extraction_cases.json`,
  not the original candidate-label fixture. The seven-case source-only rubric
  was corrected before any model request; historical fixtures remain unchanged.
- Main agent handles docs and fixtures; implementer touches only the two named code/test files. No subagents from workers.
- Runtime missing credentials is a stop, not permission to read `.env`.

### Task 1: Minimal experiment runner and durable slots

**Files:** Create `tools/run_workflow_selection_trial.py` and `tests/test_workflow_selection_trial.py` only.

**Interfaces:** expose pure `prepare_case(case)` (only source text enters catalogue), `initialize_campaign(root)` (exclusive runtime dir and SQLite ledger), `reserve_slot(root, group, slot, input_digest, prompt_digest, model)` (durable before dispatch), and `run_case(root, case, profile, *, http_client=None, api_key=None)` (one guarded extraction request maximum). The root parameter is injectable for tests; production CLI uses the one fixed campaign root. Profiles baseline/r1/r2/r3 map to trusted baseline instructions plus optional versioned selection-only suffix; never send case ID, expected, rationale, outline or scoring notes in provider payload.

- [ ] Write focused RED tests first. Examples of required behavior:

```python
assert 'ANSWER-KEY-CANARY' not in prepare_case(case).user_payload()
reserve_slot(root, 'development', 'baseline:case1', digest, digest, 'deepseek-flash')
with pytest.raises(ValueError):
    reserve_slot(root, 'development', 'baseline:case1', digest, digest, 'deepseek-flash')
```

Also test across reopened processes/ledger handles: allocation exhaustion,
in-flight reservation cannot be reclaimed, duplicate slots with changed hashes
are rejected, normal runs cannot recreate missing state. Strict bounded JSON
dataset reads reject duplicate IDs/keys, excessive size and symlink/non-regular
inputs. No dotenv, subprocess, source code execution or remote publishing.

- [ ] Implement the smallest ledger/runner. Group caps are fixed; validate slot
  identities against a frozen manifest of admitted case IDs/profiles so callers
  cannot create replacement slots. Init records development dataset hash and
  baseline prompt identity; held-out identity comes from the curator manifest,
  without printing/returning its contents. Each profile's prompt/input identity
  is immutable after its first reservation. Empty catalogue or over-limit
  payload means zero requests. No default automatic seven-case loop on errors.
- [ ] Baseline must use the existing `EVIDENCE_SELECTION_INSTRUCTIONS_V1`,
  `EvidenceSelectionResponse`, `MAX_EXTRACT_OUTPUT_TOKENS`,
  `deepseek_json_instructions` and `request_deepseek_json` with the existing local
  provider configuration. Preserve full request byte cap 65,536 and no-tools,
  zero-retry behavior. Recorded-transport tests compare baseline request bytes
  to `OpenAIExtractionClient.extract(..., evidence_selection=True)` so this
  experiment cannot silently measure a different baseline.
- [ ] Materialize via `materialize_workflow` and `validate_workflow_boundaries`;
  return only admitted workflow objects plus bounded outcome/usage/digests.
  Discard rejected model text. Results are experiment-only, never candidate
  descriptors or publication evidence. Judgment of substantive core coverage
  remains separate from mechanical admission; no `quality_passed` inference.
- [ ] CLI defaults to offline preflight; explicit run requires injected key and
  one named development slot. Held-out dispatch remains disabled until a
  controller-recorded prompt-freeze marker binds the candidate and dataset.
  Do not implement real artifact/usefulness dispatch yet: reserve their quotas
  in the ledger for later guarded adapters; do not claim end-to-end completion.
- [ ] Run focused tests, Ruff and diff checks; commit only named files. Write a
  report with RED/GREEN evidence and limitations. Controller arranges review.

## Controller execution after Task 1

- [ ] Review runner and curate development rubric independently of model output.
- [ ] Confirm held-out manifest and sample-label status; keep source/answers unread.
- [ ] Resolve runtime credential delivery and initialize one ledger; record 0/49.
- [ ] Run seven baseline cases once; independently score actual admitted outputs.
- [ ] For each permitted round, record hypothesis then change only selection
  suffix and compare the same seven cases. Stop after two no-improvement rounds.
- [ ] Freeze eligible prompt, then independently run and score held-out baseline
  and candidate once each. Stop on failure; no held-out tuning.
- [ ] If admitted, use one pinned real repo through existing local extraction,
  qualification, generation and independent review, accounting all three slots.
  Verify the extractor uses the frozen winning selection instructions; a
  candidate suffix in the experimental runner does not automatically change
  the existing CLI. Integrate and verify only if a non-baseline prompt wins.
- [ ] If a Skill exists, freeze three task rubrics and run six paired calls;
  anonymized review and final user judgment decide usefulness.

No later checklist grants extra budget, credential access or publication.
