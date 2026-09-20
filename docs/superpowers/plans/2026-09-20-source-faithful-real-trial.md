# Source-faithful real trial implementation plan

> Execute continuously using the existing local workflow and an independently
> reviewed private one-shot launcher. The user requested completion of the real
> test and already delegated routine choices; no extra routine approval gate.

**Goal:** Determine whether the corrected local generator yields a faithful,
validated, independently reviewed Skill from the fixed Fabric summary workflow.
**Architecture:** Read the previously verified Phase 2 snapshot and original
descriptor without mutation. Use fresh Phase 3 state/output, new durable request
reservations and the explicit source-faithful profile. Only a fully accepted
package may enter the existing nine-call usefulness experiment.
**Tech Stack:** Existing Python CLI, bounded DeepSeek client, SQLite and pytest.
**Spec:** User's first-useful-Skill plan and latest request “完成独立真实测试”.

## Frozen decisions and constraints

- Trial `source-faithful-real-20260920`; implementation `291f74638f0a825f5b96e055c9b47b845500128c`.
- Same immutable Fabric source and faithful extraction as the September 20
  diagnostic. This is a regression trial, not unseen-source generalization.
- Reusing immutable input evidence does not reopen the previous campaign or its
  budget. Original database, descriptor, packages and consumed launchers stay intact.
- New maximum calls: extraction 0, generation 1, review 1, comparison 9. No borrowing,
  retry, model fallback, edited semantic result, relaxed check or publication.
- Generation uses `deepseek-flash`; independent review remains `deepseek-v4-pro`.
  This is the existing explicit current-Flash configuration, not a silent alias change.
- Reserve CNY20 for this entire trial before credentials or dispatch. Prior known
  cumulative estimate CNY0.230316; stop before conservative total reaches CNY100.
  Official indexed pricing was verified after direct-page timeouts: peak uncached
  CNY/million input/output Flash2/8, Pro9/27. Estimates are not provider bills.
- Only the existing hash-pinned runtime loader may select `DEEPSEEK_API_KEY` from
  the already authorized file. No secret is displayed, persisted or sent to models.
- Unknown transport/outcome, model drift, schema rejection, safety/format rejection,
  source-fidelity rejection or Reviewer rejection closes the trial. No new trial
  or prompt tuning inside this test to select for success.

## Review focus

1. Source/descriptor/checkout/prompt/loader drift blocks before credential access.
2. Reservation must be exclusive and durable before the subprocess; rerun denied.
3. Exact CLI flags and fresh paths enforce one request per semantic stage.
4. Failure or unknown outcome cannot trigger Pro/comparison/replacement requests.
5. Source limitations and missing fields remain honest; a good format is not usefulness.

## Task 1: freeze and validate the one-shot harness

Files: new `config/previews/source-faithful-real-20260920.json`, private
`.tmp/source-faithful-real-20260920/run.py` and `test_run.py`; project state at
`docs/project/BENCHMARK_STATE.md`. No production source or dependency changes.

- [x] Independently re-admit the original descriptor and inspect source fidelity.
- [x] Write failing launcher tests for reservation-before-key, duplicate launch,
  drift, exact flags, fresh paths, unknown-result no-retry and secret-free outputs.
  Exercise real reservation files and fake only credential/network subprocesses.
- [x] Implement the smallest wrapper using existing hash-pinned private helpers:
  `_identity() -> dict`, `initialize() -> dict`, `run(key_loader=...) -> int`.
  Freeze config/launcher/loader/candidate/source-state/prompt hashes in the manifest.
  Use `os.O_EXCL` plus fsync through the existing `_write_exclusive_json` helper.
  Run the real CLI with `--deepseek-current-flash --single-attempt
  --source-faithful-generation`, fresh state/output, hidden stdout/stderr, timeout240s.
- [x] Run private tests and focused product regressions; independently review the
  launcher and freeze documents in a local commit before initializing the manifest.

## Task 2: one real build, inspect, and stop-or-continue

- [x] Initialize the fresh manifest without credentials, then consume exactly one
  build reservation through the existing approved runtime loader.
- [x] Inspect terminal, validation, request/model/token evidence, package and
  independent Pro decision. Do not interpret exit0 alone as accepted.
- [x] Independently compare the generated package with the full source and verified
  WorkflowSpec; preserve all output bytes and report every failure.
  Not applicable: no package was produced. Independent post-run review instead
  verified the generation rejection and absence of downstream artifacts.
- [x] On any failed prerequisite, close the trial and leave comparison calls unused.

## Task 3: conditional usefulness test

**Not reached:** generation returned `schema_invalid`; no tasks, comparison harness
or scores were created, and all nine requests remain unused and closed.

Only if Task 2 fully passes: freeze three synthetic, newly authored tasks and a
0–2 rubric for procedure correctness, missing-information handling, verifiability
and relevance. Expected outcomes: normal completed, missing information escalated,
unrelated abstained. These are candidate tasks, not a representative production sample.

Run independent contexts in order ABC/BCA/CAB: A task/materials only, B same plus
fixed source document, C same plus unchanged Skill/references. Same Flash model,
same token cap, no tools, untrusted user data only. Exactly nine calls, each reserved
durably first. Freeze task/rubric hashes and request shapes before dispatch; keep
rubric/answers outside requests. Blind-label responses before independent scoring.

Pass requires each C≥7/8 with zero invention/guarantee/authority/execution violation,
C>A on at least two tasks, C≥B on all, C>B on at least one. Full ties only establish
README-level performance. Preserve unknown/missing/failure and cost evidence.
Model/agent scores are preliminary and require human confirmation, never publication.

## Task 4: evidence and local handoff

- [x] Write actual request/token/cost/outcome evidence and update README, RELEASE,
  and BENCHMARK_STATE. Keep original failure reports unchanged.
- [x] Verify unchanged implementation/historical inputs, run relevant offline checks,
  and commit documentation locally. No remote write, PR, merge or publication.

Ruling: Reuse the faithful historical extraction as immutable test input, not a
fresh extraction — isolates the corrected generation boundary and avoids spending
on an unchanged step — cost if wrong is limited generalization; report regression
scope explicitly and make no end-to-end-new-source claim.

## Execution outcome

Closed failed real regression: one Flash request, 6,197 tokens, estimated
CNY0.017680. Terminal `generator_schema_failure`; no package, validator, Pro or
comparison result. No retry, semantic edit or publication. The precise rejected
field/check is not retained by the current content-free diagnostic. See the
[result and independent verification](../specs/2026-09-20-source-faithful-real-result.md).
