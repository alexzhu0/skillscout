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

- [x] Write focused RED tests first. Examples of required behavior:

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

- [x] Implement the smallest ledger/runner. Group caps are fixed; validate slot
  identities against a frozen manifest of admitted case IDs/profiles so callers
  cannot create replacement slots. Init records development dataset hash and
  baseline prompt identity; held-out identity comes from the curator manifest,
  without printing/returning its contents. Each profile's prompt/input identity
  is immutable after its first reservation. Empty catalogue or over-limit
  payload means zero requests. No default automatic seven-case loop on errors.
- [x] Baseline must use the existing `EVIDENCE_SELECTION_INSTRUCTIONS_V1`,
  `EvidenceSelectionResponse`, `MAX_EXTRACT_OUTPUT_TOKENS`,
  `deepseek_json_instructions` and `request_deepseek_json` with the existing local
  provider configuration. Preserve full request byte cap 65,536 and no-tools,
  zero-retry behavior. Recorded-transport tests compare baseline request bytes
  to `OpenAIExtractionClient.extract(..., evidence_selection=True)` so this
  experiment cannot silently measure a different baseline.
- [x] Materialize via `materialize_workflow` and `validate_workflow_boundaries`;
  return only admitted workflow objects plus bounded outcome/usage/digests.
  Discard rejected model text. Results are experiment-only, never candidate
  descriptors or publication evidence. Judgment of substantive core coverage
  remains separate from mechanical admission; no `quality_passed` inference.
- [x] CLI defaults to offline preflight; explicit run requires injected key and
  one named development slot. Held-out dispatch remains disabled until a
  controller-recorded prompt-freeze marker binds the candidate and dataset.
  Do not implement real artifact/usefulness dispatch yet: reserve their quotas
  in the ledger for later guarded adapters; do not claim end-to-end completion.
- [x] Run focused tests, Ruff and diff checks; commit only named files. Write a
  report with RED/GREEN evidence and limitations. Controller arranges review.

## Controller execution after Task 1

- [x] Review runner and curate development rubric independently of model output.
- [x] Confirm held-out manifest and sample-label status; keep source/answers unread.
- [x] Resolve runtime credential delivery and initialize one ledger; record 0/49.
- [x] Run seven baseline cases once; independently score actual admitted outputs.
- [x] For each permitted round, record hypothesis then change only selection
  suffix and compare the same seven cases. Stop after two no-improvement rounds.
- [x] Freeze eligible prompt, then independently run and score held-out baseline
  and candidate once each. Stop on failure; no held-out tuning.
- [ ] If admitted, use one pinned real repo through existing local extraction,
  qualification, generation and independent review, accounting all three slots.
  Verify the extractor uses the frozen winning selection instructions; a
  candidate suffix in the experimental runner does not automatically change
  the existing CLI. Integrate and verify only if a non-baseline prompt wins.
- [ ] If a Skill exists, freeze three task rubrics and run six paired calls;
  anonymized review and final user judgment decide usefulness.

No later checklist grants extra budget, credential access or publication.

## Offline checkpoint — 2026-09-14

Implementation: `e2546b6`, campaign-stop fix `40b99a8`, hermetic preflight and
latency fix `955bddc`. Task review and final scoped re-review approved the
preparation only; no conclusion about model quality or Skill usefulness.

- Fresh final focused regression: **205 passed** at `955bddc`; Ruff lint and
  formatting passed. Tests use recorded HTTP responses, not live requests.
- Earlier broad run at `e2546b6`: **2,905 passed, 3 skipped**, with the 12 slow
  recovery cases excluded. All 12 unchanged recovery cases subsequently passed
  in three disjoint groups. This is not a claim that the full suite was rerun
  after the final test-fixture/latency edit.
- Exclusive runtime initialization succeeded. Read-only ledger check: **0
  reservations**, caps development 28 / heldout 12 / artifact 3 / usefulness 6.
- Runtime credentials remain unavailable. No secret file was read, no model
  request made, no Skill produced, and no branch pushed or PR created.
- Next: resolve credential injection, then run each of the seven baseline
  cases once. Stop on unknown outcomes; never reinitialize the campaign.

The experiment and branch remain in progress. Do not merge, delete its private
state, or mark the useful-Skill objective complete based on this checkpoint.

## Live baseline checkpoint — 2026-09-14

The user separately authorized a runtime-only read of DEEPSEEK_API_KEY from
the named root repository .env. No value was printed or copied. Seven baseline
slots completed once with DeepSeek Flash; **7/49 requests**, all decided.
Usage: 13,351 tokens; summed provider latency 20,779 ms; median 2,362 ms.

Independent source/rubric scoring: **5/7 pass**, positives 1/3, negatives 4/4.
d01 proposes processing authority instead of a non-executing review; d03 also
admits a demo lifecycle and unsupported approvals. Baseline is ineligible;
no held-out, real-artifact, usefulness or publication step has run.
Round 1 is preregistered in `../specs/2026-09-14-useful-skill-r1.md`.

## Candidate freeze — 2026-09-14

R1 independently passes 7/7 semantic cases (positives 3/3, negatives 4/4),
versus baseline 5/7. R1 uses 14,558 tokens and 18,622 ms summed latency.
All 14 cumulative requests are decided. Freeze r1 before opening held-out
sources; binding is `../specs/2026-09-14-useful-skill-frozen-candidate.json`.
No r2/r3 or held-out-based tuning is now permitted in this campaign.

Separate deterministic qualification still blocks synthetic r1:d01: only two
steps, confidence below the floor, safety-controls and named-approval checks.
Semantic promotion is not artifact admission. Keep all existing rules unchanged;
later real extraction must pass qualification before generation or review.

### Task 3: Minimal frozen held-out route

Modify only the existing experiment runner and its tests. Reuse its guarded
request/materialization path, adding explicit held-out dispatch after a strict
candidate-freeze binding. Existing ledger must not be reset or slots added.
Bind the checked-in freeze marker once into campaign_meta, validate identities
against existing metadata and decided development rows, reject outstanding
requests, and prohibit all new development reservations after freeze.
Held-out execution reads the bounded file only after binding, checks its exact
frozen dataset hash and h01..h06 IDs, selects by opaque ID, and sends source only.
Both baseline and candidate use the exact reviewed requests; candidate resolves
to r1's frozen instructions, never a free-form prompt. Preserve existing
global unknown-outcome halt and per-slot no-replay accounting. No real calls
by implementer, no artifact/usefulness adapter, no new dependencies or CLI.
Use synthetic temporary held-out files in TDD tests; never open real held-out
sources or credentials during implementation/review. Controller dispatches
only after task review and fresh regression checks.

Held-out dispatch order, fixed before reading sources or outputs: baseline
h01..h06, then candidate h01..h06. One call per invocation, identical private
transport settings, no retries. Stop immediately on unknown/transport/schema
failure; otherwise score after completing the frozen comparison. Report both
profiles under the existing source rubric, without changing labels or candidate.
An ineligible candidate ends this campaign, even when budget remains unused.

## Terminal checkpoint — 2026-09-14

The frozen candidate failed held-out h06; candidate5/6 vs baseline3/6. Stop rule
applied at26/49 actual requests. Artifact and usefulness steps are not executed
and are no longer authorized by this campaign. Goal remains unachieved.
See `../specs/2026-09-14-useful-skill-loop-result.md` for actual counts, failure
evidence, independent-score correction and the narrow proposed follow-up.
