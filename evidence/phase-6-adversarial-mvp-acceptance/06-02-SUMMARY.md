---
phase: 06-adversarial-mvp-acceptance
plan: "02"
subsystem: testing
tags: [pytest, github-actions, docker-network-none, hosted-isolation, fail-closed]

requires:
  - phase: 06-adversarial-mvp-acceptance
    provides: Plan 06-01 acceptance contracts, hard-gate registry, and Wave 0 ownership map
provides:
  - Collectable adversarial, acceptance-mutation, workflow, and source-execution RED contracts
  - Secretless least-privilege hosted isolation probe workflow bound to exact checked-out source
  - Reviewed fail-closed hosted run locator proving that no isolation artifact or capability credit was produced
affects: [06-03, 06-06, phase6-offline-campaign, phase6-verification]

tech-stack:
  added: []
  patterns:
    - Exact named expected-RED contracts for adversarial and evidence mutations
    - Full-SHA checkout followed by repository-local locked uv execution
    - Non-authoritative one-day hosted diagnostics with fail-closed absence handling

key-files:
  created:
    - tests/test_phase6_adversarial.py
    - tests/test_phase6_acceptance.py
    - tests/test_phase6_workflow.py
    - tests/test_phase6_source_execution.py
    - .github/workflows/phase6-acceptance.yml
  modified: []

key-decisions:
  - "Treat hosted run 30430010273 as a blocking failure because the locked-toolchain verification failed before the network probe and artifact upload."
  - "Record the exact run, source, workflow, job, and empty-artifact locators without inventing an artifact digest or inspecting raw logs."
  - "Deny Plan 06-06 campaign credit until a separately authorized exact workflow run produces bounded evidence that is revalidated into canonical operations state."

patterns-established:
  - "Hosted isolation credit requires all three outcomes: offline control passed, direct Python network denied, and subprocess network denied."
  - "A skipped probe or upload yields no artifact authority; an immutable run locator documents the failure but cannot substitute for canonical evidence."

requirements-completed: [TEST-01, TEST-02, TEST-03, TEST-04]

coverage:
  - id: D1
    description: Complete collectable Wave 0 adversarial, mutation, workflow, and source-execution contract surface
    requirement: TEST-02
    verification:
      - kind: integration
        ref: ".tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_phase6_adversarial.py tests/test_phase6_acceptance.py tests/test_phase6_workflow.py tests/test_phase6_source_execution.py"
        status: pass
    human_judgment: false
  - id: D2
    description: Secretless least-privilege hosted isolation workflow with one-day non-canonical artifact policy
    requirement: TEST-04
    verification:
      - kind: integration
        ref: ".tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py -k 'isolation or workflow or permission or secret' -x"
        status: pass
    human_judgment: false
  - id: D3
    description: Hosted Docker network-none capability evidence for the ordinary control and both process-level denial probes
    requirement: TEST-04
    verification:
      - kind: manual_procedural
        ref: "GitHub Actions run 30430010273 attempt 1"
        status: fail
    human_judgment: true
    rationale: "The run failed before the isolation probe; no bounded artifact exists and kernel/OS denial capability remains unproven."

duration: 32 min
completed: 2026-07-29
status: complete
---

# Phase 6 Plan 2: Adversarial Contracts and Hosted Isolation Probe Summary

**Wave 0 now freezes 82 adversarial and source-execution contract nodes and a secretless Docker network-none probe, while the exact first hosted run remains a fail-closed blocking locator because it produced no isolation artifact.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-07-29T06:28:58Z
- **Completed:** 2026-07-29T07:01:11Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added collectable contracts for all injection classes, supply-chain execution paths, whole-phase evidence mutations, the exact four-workflow source-only execution boundary, and empty/indirect execution mutations.
- Added a single-job `workflow_dispatch` probe with `contents: read`, full-SHA Actions, `persist-credentials: false`, pinned uv 0.11.29, Docker `--network none`, synthetic-only scanning, and one-day non-canonical artifact policy.
- Dispatched only the explicitly approved `isolation-probe` against exact commit and workflow bytes, then retained its precise failure locator without reading raw logs, secret values, or unapproved artifact content.

## Task Commits

Each repository-changing task was committed atomically:

1. **Task 06-02-01: Freeze adversarial, workflow, and independent-rebuild contracts** - `b57f4cd` (test)
2. **Task 06-02-02: Implement the no-credential hosted isolation capability probe** - `27e6446` (feat)
3. **Task 06-02-03: Authorize and review hosted isolation capability evidence locator** - recorded by this summary commit because the task's only durable output is the non-authoritative locator and blocking result

## Files Created/Modified

- `tests/test_phase6_adversarial.py` - Injection, supply-chain, network, and synthetic-canary RED contracts.
- `tests/test_phase6_acceptance.py` - Whole-phase evidence mutation and 44-requirement rebuild contracts.
- `tests/test_phase6_workflow.py` - Secretless hosted workflow, mutation, and locator contracts.
- `tests/test_phase6_source_execution.py` - Exact four-workflow checked-out-source execution contract.
- `.github/workflows/phase6-acceptance.yml` - Single-job hosted Docker network-none capability probe.

## Non-Authoritative Hosted Probe Locator

This projection is intentionally non-authoritative. It records a failed diagnostic run only; Plan 06-06 must not grant campaign credit from it.

- **Repository:** `alexzhu0/skillscout`
- **Workflow path:** `.github/workflows/phase6-acceptance.yml`
- **Workflow ID:** `322759872`
- **Workflow SHA-256:** `b1232499a5b5caba8a073fc0880973d4b1711f0ef807b1ff001b54992d932703`
- **Source commit SHA:** `27e644657a24c554eb73a03394cb9bc92e84b116`
- **Source tree:** `35e6a2f7b693d4ab85e8ca7519cdfe0fcbabdc11`
- **Run ID / attempt:** `30430010273` / `1`
- **Run locator:** `https://github.com/alexzhu0/skillscout/actions/runs/30430010273`
- **Job ID / name:** `90504839033` / `isolation_probe`
- **Job locator:** `https://github.com/alexzhu0/skillscout/actions/runs/30430010273/job/90504839033`
- **Artifact metadata locator:** `https://api.github.com/repos/alexzhu0/skillscout/actions/runs/30430010273/artifacts`
- **Intended artifact retention:** `1 day`
- **Observed artifact count:** `0`
- **Artifact locator/digest:** absent; the upload step was skipped, so no value is guessed or recorded
- **Run conclusion:** `failure`
- **Observed boundary:** checkout and pinned setup-uv completed; repository-local locked-toolchain verification failed; the offline control, direct-process denial, child-process denial, synthetic-canary result, and upload steps did not run

Because no artifact exists, this run proves neither `docker_network_none` availability nor D-24 kernel/OS network denial. It is an immutable failure locator only.

## Decisions Made

- The exact approved dispatch remained bound to remote `main` and local `HEAD` at `27e644657a24c554eb73a03394cb9bc92e84b116`; both matched the approved workflow digest before dispatch.
- The failed toolchain step is not reclassified as an isolation success. No alternate workflow, SHA, input, job, retry, mechanism, or Python-only substitute was used.
- Raw job logs were not opened. Artifact metadata reported zero artifacts, so no artifact content or secret-bearing environment surface was inspected.

## Deviations from Plan

None - the authorized workflow was dispatched exactly once and its failure was handled through the plan's fail-closed path.

## Issues Encountered

- GitHub Actions run `30430010273` failed during repository-local locked-toolchain verification. The network-isolation probe and artifact upload were skipped, leaving no bounded evidence artifact.
- The local sandbox initially blocked uv cache initialization. The same locked pytest command was rerun with filesystem authorization; no dependency, source, or test command changed.

## Known Stubs

None. Missing Phase 6 production/evidence modules are intentional named Wave 0 RED contracts, not shipped runtime placeholders.

## User Setup Required

None - no external service configuration or secret inspection is required by this plan.

## Next Phase Readiness

- Plans that implement the frozen Phase 6 contracts may continue against the 82-node Wave 0 surface.
- Plan 06-06 and all `os_syscall_network_denial` campaign credit remain blocked until an explicitly authorized exact hosted run produces the bounded one-day artifact and Plan 06-06 revalidates it into `OperationsStateStore`/state-branch evidence.
- No publication, state write, GitHub App/catalog/DeepSeek credential, cleanup, merge, approval, ready transition, or secret inspection occurred.

## Self-Check: PASSED

- All five created/modified plan files exist.
- Task commits `b57f4cd` and `27e6446` exist in Git history.
- All four Wave 0 modules collect 82 tests; the 15 isolation/workflow/permission/secret contract tests pass.
- Remote `main`, local `HEAD`, source commit, source tree, and workflow SHA-256 were checked before dispatch.
- The hosted result is represented as a failure with zero artifacts; no positive isolation claim or guessed digest appears.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-07-29*
