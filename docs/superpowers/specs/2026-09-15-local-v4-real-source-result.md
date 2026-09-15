# Local v4 real-source trial

One new extraction was frozen and invoked from local commit
`67648a1ca36eac6f10cc58757ee10706b889959b`. No remote changes, source-code
execution, publication or automatic retries occurred.

## Exact inputs and invocation

- Configuration: [local-v4-microsoft-20260915](../../../config/previews/local-v4-microsoft-20260915.json).
- Source: `microsoft/generative-ai-for-beginners` at
  `c9657f3fdb6e4f50a168b1d026eadf4cda2f0d07`,
  `04-prompt-engineering-fundamentals/README.md`, MIT.
- README blob: `90cb596676fd2198da4bfdfeb1702707864a5bf3`;
  content SHA-256: `cb859f174d8a08f99b3d0b29b71f0ff5746f20648592bf1d60ecb38991da1f5b`.
- Scope: `local-readme-v4`; prompt:
  `extract-local-evidence-source-only-fields-v1`.
- Rendered prompt SHA-256:
  `0f06e8830e83b3e217818cf396e4195e3512e966d1f85264ea409cd8dd40160b`.
- Run: `08e1fb7e39bf4a5eb24aa848e43d31fd`.
- Private evidence: `.tmp/local-v4-microsoft-20260915/runtime/`.

The separately reviewed private launcher binds the committed checkout, config,
its own bytes, the exact previously authorized credential-loader bytes, and the
actual rendered v4 prompt. It durably consumes its one extraction slot before
loading the runtime key. Only the CLI child receives that key; stdout/stderr are
suppressed and an unknown outcome cannot be replayed.

## Mechanical result versus source fidelity

The CLI finished successfully and produced one schema-valid workflow:
`sha256:55f4cc340b0e32b28de7b384ce19963a45e5482b3b89cdc7487b2d810fdcc9ff`.
The reader fetched one 44,273-byte README without source-code loading. The existing
catalogue retained 128 entries and was marked truncated; its digest is
`sha256:0442b56bd49ef82777bc050610b7acff87dcb96142f38f27187924eca4de3565`.

Unlike the previous real v3 result, this workflow has no invented approval,
prohibited-action or non-goal fields and no extra iteration report deliverable.
However, its broad prompt-refinement procedure includes Python/local-environment
preconditions for the lesson's notebook and a mandatory notebook-practice step.
The source explicitly scopes those requirements to the accompanying exercises
(lines 35–41), whereas its general interaction and design/refinement procedure
is described separately (lines 10 and 69–76). This is a source-role/scope issue,
not fabrication of the notebook's existence. No fields were manually removed.

The phrase about refining until expectations are met is present in the full
source at line 10; it must not be reported as invented merely because one selected
evidence excerpt ends before that phrase. Fidelity review must distinguish the
full-source claim from the narrower evidence-support claim.

Independent field-level review also **rejected** this candidate. The precise
blocking fields are `preconditions[1]`, `preconditions[2]` and `steps[5]`
(zero-based indexes). The deployment/endpoint precondition is not independently
fatal; the Python/environment requirements and mandatory notebook step are.
The other substantive fields were judged materially source-supported. This is
preliminary agent review, not the production Pro Reviewer or human approval.

This one-source trial is closed. No export, generation, Pro Reviewer,
format-validation-of-a-generated-package or nine-way usefulness test has run.
Successful extraction is not a successful Skill.

## Usage and verification

One `deepseek-flash` request, request ID
`2299b0c6-2274-4cb4-abfa-80321d7071df`: 18,424 input and 1,478 output tokens,
19,902 total. At the already recorded conservative 2/8 CNY-per-million rates,
estimated cost is CNY0.048672; known cumulative estimate for the immediately
preceding pilot, eight-case comparison and this trial is CNY0.196462.
These are estimates, not verified charges. Other request categories were unused.

- Focused tracked tests: 133 passed; repository Ruff passed.
- Private v4 launcher: 19 passed; independent review passed after adding the
  exact credential-loader identity guard.
- A full test process started before the v4 edits ended with 2,902 passed,
  63 failed and 3 skipped in 1,707.71 seconds. The 63 failures were dynamic
  trial-tool imports of the new suffix while the process retained the old
  extraction module. It is a mixed-code test run, not a valid final-tree check;
  its failure is retained rather than called a pass.
- The fresh full offline run on the frozen v4 implementation completed:
  **2,981 passed, 3 skipped in 1,214.71 seconds**, exit code 0. Command:
  `.tools/uv-0.11.29/bin/uv run --locked --no-env-file pytest -q -rs --tb=short`.
  Source/test code remained unchanged from `67648a1` throughout this run;
  subsequent changes were documentation only. The skips were the unfinished
  Phase 6 release requirement map and two explicitly unconfigured live publication
  canary checks. They do not prove Phase 6 or live publication acceptance.

## Next hypothesis

Do not add another prompt suffix or edit this workflow to remove the failing
fields. First inspect at most three shorter, single-task sources under the
existing read/filename/license limits, before allocating any new model calls.
The goal is to test whether a clean source yields a faithful candidate, not to
hide this mixed-tutorial failure. If no source meets those unchanged limits,
report that limitation rather than expanding reader scope silently.
