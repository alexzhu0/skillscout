---
phase: 06-adversarial-mvp-acceptance
plan: "15"
subsystem: workflow-security
tags: [github-actions, source-execution, uv, fail-closed, publication]

requires:
  - phase: 06-02
    provides: Wave 0 source-execution mutation contracts and the retained isolation-probe job
  - phase: 06-03
    provides: Closed Flash/Flash/Pro semantic-provider authority
  - phase: 06-04
    provides: Typed acceptance facts and canonical operations-owned persistence
provides:
  - Four-workflow same-job full-SHA checked-out-source execution contract
  - Closed Phase 6 action grammar with separated credential and effect zones
  - Standard-library-only fail-closed verifier plus launcher mutation coverage
affects: [06-06, 06-07, 06-08, 06-09, 06-10, gate-b4, publication]

tech-stack:
  added: []
  patterns:
    - Same-job full-SHA checkout, exact setup-uv, repository-managed CPython 3.13.14, and direct run --locked
    - Fresh authoritative venvs install the locked current SkillScout project before any source entry executes
    - Constrained ordered workflow parser with closed authoritative-entry grammar
    - Failure-only bounded diagnostic artifact with closed stage/status schema and no evidence authority

key-files:
  created:
    - tools/verify_phase6_source_execution.py
    - src/skillscout/application/phase6_adversarial_runner.py
    - tests/test_phase6_campaign_runner.py
  modified:
    - .github/workflows/phase6-acceptance.yml
    - .github/workflows/discover.yml
    - .github/workflows/publish-candidate.yml
    - .github/workflows/gate-b4-canary.yml
    - tests/test_phase5_acceptance.py
    - tests/test_phase6_source_execution.py
    - tests/test_publication_security.py
    - tests/test_phase6_workflow.py
    - tests/test_discovery_workflow.py

key-decisions:
  - "Recognize only direct python -m skillscout, inline skillscout imports, and python tools/*.py as authoritative workflow entry forms; every unknown form fails closed."
  - "Keep catalog credentials exclusively in value_publication after fresh_gate_b4, while nomination, semantic, attestation, rebuild, and isolation jobs retain separate minimum authority."
  - "Preserve isolation_probe as the Plan 06-02 contract while widening only the closed phase6_action grammar and exact job registry."
  - "Admit uv only when the program token is exactly uv and the version token is exactly 0.11.29; allow only an optional non-empty parenthesized build-metadata suffix."
  - "Materialize exact CPython 3.13.14 under ${GITHUB_WORKSPACE}/.tools/python in every authoritative job; network-none containers receive only the read-only repository mount and closed uv managed-runtime environment."
  - "Install the current locked SkillScout project in all 15 fresh authoritative venvs; --no-install-project is a fail-closed mutation because the src-layout control runtime otherwise cannot import SkillScout."
  - "Run the hosted adversarial campaign through an installed-package deterministic runner with a closed 25-node registry; pytest remains only a development test consumer and cannot produce hosted evidence."

patterns-established:
  - "Authoritative workflow execution: checkout current github.sha with credentials disabled, pin setup-uv 0.11.29, copy and verify local uv, then invoke checked-out source directly with run --locked."
  - "Workflow mutation defense: reject package/artifact acquisition, PATH-only launchers, external cwd, variables, aliases, functions, sourced/delegated wrappers, indirect scripts, and empty scans."

requirements-completed: [TEST-01, TEST-03, TEST-04]

coverage:
  - id: D1
    description: All four authoritative workflows execute SkillScout and repository tools only from the same-job checked-out locked source.
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "tests/test_phase6_source_execution.py (61 passed)"
        status: pass
      - kind: other
        ref: ".tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py"
        status: pass
    human_judgment: false
  - id: D2
    description: Phase 6 actions isolate nomination, offline, semantic, publication, attestation, cleanup, and rebuild authority with catalog access only after the fresh gate.
    requirement: TEST-03
    verification:
      - kind: integration
        ref: "tests/test_phase6_workflow.py#test_phase6_actions_and_jobs_have_closed_authority_zones"
        status: pass
      - kind: integration
        ref: "affected workflow regression (180 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: Publication and discovery launchers require full-SHA checkout, exact local uv materialization, and direct locked-source invocation.
    requirement: TEST-04
    verification:
      - kind: integration
        ref: "tests/test_publication_security.py and tests/test_discovery_workflow.py"
        status: pass
      - kind: other
        ref: "ruff check and ruff format --check over changed Python files"
        status: pass
    human_judgment: false
  - id: D4
    description: Historical Phase 5 acceptance is tested against its exact Gate-B4-bound workflow bytes while the current Phase 6 tree fails closed pending fresh evidence.
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "tests/test_phase5_acceptance.py (25 passed)"
        status: pass
      - kind: integration
        ref: "full locked pytest (2080 passed, 32 skipped, 2 planned future Phase 6 RED failures)"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-30
status: complete
---

# Phase 6 Plan 15: Pre-Gate-B4 Workflow Authority Summary

**Four authoritative GitHub workflows now execute only same-job checked-out source through verified repository-local uv 0.11.29 and exact repository-managed CPython 3.13.14, with closed Phase 6 authority zones and mutation-tested fail-closed admission**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-29T08:06:42Z
- **Completed:** 2026-07-29T08:15:48Z
- **Tasks:** 1
- **Files modified:** 8

## Accomplishments

- Expanded `phase6-acceptance.yml` to the exact ten-action grammar and ten isolated jobs while preserving the existing credential-free `isolation_probe`.
- Converted discover, controlled publish, Gate B4 canary, and Phase 6 authoritative entry points to same-job full-SHA checkout plus verified repository-local locked uv execution.
- Added a network-free, project-import-free verifier that parses ordered job steps and rejects alternate acquisition, wrapper, external-directory, mutable, indirect, unknown, and empty-scan routes.
- Extended publication, discovery, and Phase 6 workflow tests so older security contracts continue to validate the stricter local-source baseline.
- Corrected all 15 authoritative toolchain guards to accept the pinned uv binary's official trailing build metadata while still rejecting wrong, missing, malformed, or spoofed program/version tokens.
- Historically attempted to close the hosted empty-rootfs runtime gap with a `${RUNNER_TOOL_CACHE}/Python/` base-prefix mount; hosted run `30447435387` proved that assumption unavailable at runtime preflight, so the approach is superseded.
- Added failure-only campaign observability: a closed seven-stage diagnostic initialized before runtime preflight, updated without raw output, and uploaded as exactly one pinned one-day artifact only when the campaign step fails.
- Extended the independent four-workflow verifier to reject diagnostic enum/schema/status widening, extra free-text/path/log fields, retention or Action-pin drift, broadened upload conditions, and any evidence/canonical naming.
- Replaced runner-toolcache dependence in all 15 authoritative jobs with exact CPython `3.13.14` materialized under `${GITHUB_WORKSPACE}/.tools/python`; all six network-none containers now rely only on the read-only repository mount plus closed managed-runtime environment variables.
- Corrected all 15 fresh authoritative sync jobs to install the locked current SkillScout project after removing the old venv; a real offline control test now proves baseline import/execution succeeds and the `--no-install-project` mutation returns 1.

## Task Commits

The task was committed atomically:

1. **Task 06-15-01 GREEN: protected workflow zones and locked source execution** - `bd8f749` (feat; RED inherited from the 06-02 Wave 0 contract)

Post-merge regression repair was committed separately under strict TDD:

2. **RED: expose the mixed Phase 5 workflow/evidence lifecycle** - `279c7f0` (test; observed failing exact-digest contract)
3. **GREEN: separate historical and current workflow lifecycles** - `1fa3f49` (fix; test-harness-only)

The second post-merge correction was also committed under strict TDD:

4. **RED: execute the real workflow guard against pinned uv** - `49a5482` (test; official build metadata was rejected)
5. **GREEN: admit exact uv 0.11.29 with optional official metadata** - `3b6b189` (fix; uniform 15-guard workflow and verifier correction)

The third post-merge correction was committed under strict TDD:

6. **RED: expose the absent hosted Python runtime mount** - `e86c809` (test; the current workflow failed the exact mount contract)
7. **GREEN: mount the validated hosted Python base prefix** - `b48e1fd` (fix; six exact read-only same-path mounts plus independent verifier enforcement)

The fourth post-merge correction was committed under strict TDD:

8. **RED: freeze bounded campaign diagnostic contracts** - `1a6d668` (test; stable step ID, closed state machine, failure upload, and independent mutations were absent)
9. **GREEN: retain bounded campaign failure diagnostics** - `7d94188` (fix; original nonzero status preserved, exact failure-only artifact, and independent verifier enforcement)

The fifth post-merge correction followed the user-approved repository-managed Python architecture under strict TDD:

10. **RED: require exact repository-managed CPython runtime** - `80eaa3a` (test; runner-toolcache paths, external runtime mounts, non-exact versions, and writable/remapped repository mounts remained admissible)
11. **GREEN: materialize CPython 3.13.14 inside the repository** - `a8f42d1` (fix; 15 exact managed-runtime jobs, six repository-only network-none containers, and independent mutation enforcement)

The sixth post-merge correction followed hosted run `30508458266` under strict TDD:

12. **RED: reproduce the missing project in a fresh authoritative venv** - `5aa3aa2` (test; real locked initialization completed but isolated SkillScout import returned 1)
13. **GREEN: install the current project in all fresh authoritative venvs** - `e425de3` (fix; all 15 jobs, the independent verifier, and workflow-owner contracts now require project installation)

The seventh post-checkpoint correction followed the user-approved deterministic-runner architecture under strict TDD:

14. **RED: require production-owned campaign execution and distinct failure classes** - `f32fa2d` (test; missing runner, pytest teardown evidence, and collapsed control failure diagnostics all failed)
15. **GREEN: execute the closed campaign through the installed package** - `e5ab102` (fix; exact 25-node registry, canonical atomic report, bounded scenario/report-write diagnostics, and direct `python -I -m` workflow execution)

## Files Created/Modified

- `.github/workflows/phase6-acceptance.yml` - Defines the closed action grammar and separated nomination, offline, semantic, publication, attestation, cleanup, and rebuild jobs.
- `.github/workflows/discover.yml` - Materializes and verifies local uv in both jobs and directly runs checked-out discovery/publication source.
- `.github/workflows/publish-candidate.yml` - Adds current-SHA checkout, pinned uv setup, local materialization, and direct locked admission/publication launchers.
- `.github/workflows/gate-b4-canary.yml` - Runs both canary phases through verified repository-local locked source.
- `tools/verify_phase6_source_execution.py` - Independently validates the exact four-workflow set and returns typed invocation evidence.
- `tests/test_publication_security.py` - Owns the updated protected publication launcher and action-pin contract.
- `tests/test_phase6_workflow.py` - Preserves isolation assertions while freezing the expanded action/job authority zones.
- `tests/test_phase6_source_execution.py` - Mutation-tests exact Python runtime preflight and rejects broad, writable, redirected, arbitrary, and unvalidated mounts.
- `tests/test_discovery_workflow.py` - Updates the historical discovery security audit for the stricter local uv source path.

## Decisions Made

- The verifier does not trust general YAML or shell interpretation. It accepts one constrained ordered workflow shape and three explicit authoritative entry classes, then fails closed on every other form.
- `value_publication` is the only Phase 6 acceptance job that can mint the fixed-catalog App token, and it is ordered after `fresh_gate_b4`.
- Candidate, evaluator, attestation, and state identities enter shell commands only through fixed files and bounded environment variables; workflow-dispatch input is used only in job-level closed equality conditions.
- Existing Phase 5 Gate B4 hashes are historical after these planned pre-Gate workflow changes. A fresh Gate B4 must bind the final bytes after Plan 06-06's one permitted offline-job change.
- The version guard treats the first two output tokens as authority (`uv`, `0.11.29`) and permits only an optional non-empty parenthesized suffix; build metadata is not allowed to weaken or replace either authoritative token.
- Both failed hosted runs `30430010273` and `30441596331` stopped at the same locked-toolchain verification boundary before campaign execution or artifact upload. Their locators remain failure facts only.
- This correction changes all four authoritative workflow byte sequences. Every prior workflow digest, approval, dispatch authorization, and Gate B4 binding is stale and grants no authority to retry, publish, or record canonical acceptance facts.
- The previous `${RUNNER_TOOL_CACHE}` base-prefix assumption is historical and superseded. Every authoritative job now materializes exact CPython `3.13.14` under canonical `${GITHUB_WORKSPACE}/.tools/python`; empty-rootfs containers receive no external Python mount and resolve the locked venv through the same-path read-only repository mount with `UV_PYTHON_INSTALL_DIR`, `UV_MANAGED_PYTHON=1`, and `UV_PYTHON_DOWNLOADS=never`.
- Failure diagnostics are never campaign evidence: they contain only the fixed schema, source/workflow identities, hosted run identity, one closed stage, four integer statuses, and retention value `1`; the existing offline-evidence upload remains success-only and canonical state admission remains unchanged.
- Fresh authoritative venv creation must install the current locked project. Dependency-only initialization is insufficient for a src-layout checkout: `uv run --locked --offline --no-sync` cannot resolve `skillscout.application.acceptance` unless sync records the project installation.
- Hosted run `30508458266` is a failure fact only. Its control returned 1 while direct and child network-denial probes remained 97; it grants no hosted campaign, canonical state, Gate B4, dispatch, or publication authority.
- Hosted run `30510875649` proves only that the old pytest control process returned 1 before its session teardown produced a report. The `campaign-report` stage label and statuses `1/1/97/97` cannot distinguish a scenario/assertion failure from a final report-write failure, so they are deliberately treated as ambiguous diagnostics rather than root-cause evidence.
- The approved correction moves campaign ownership into `skillscout.application.phase6_adversarial_runner`: a closed 25-node committed registry runs the existing controlled evaluator without network, tools, subprocesses, caller-supplied paths, or arbitrary scenario authority. It emits canonical bounded success bytes atomically and distinguishes `scenario_assertion_failure`, `scenario_evaluation_failure`, and `report_write_failure` without raw exceptions, paths, canary values, or free text.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced dynamically imported dataclasses with immutable NamedTuple contracts**
- **Found during:** Task 06-15-01 GREEN
- **Issue:** The Wave 0 loader uses `module_from_spec` without inserting the module into `sys.modules`; Python 3.13 dataclass annotation processing therefore failed before verification.
- **Fix:** Kept the same immutable fields and attribute API using `NamedTuple`, which is safe under the existing dynamic loader.
- **Files modified:** `tools/verify_phase6_source_execution.py`
- **Verification:** All 29 source-execution tests, including every mutation, passed.
- **Committed in:** `bd8f749`

**2. [Rule 3 - Blocking] Updated superseded workflow-owner tests for the stricter source contract**
- **Found during:** Task 06-15-01 GREEN regression
- **Issue:** Plan 06-02 still asserted that the Phase 6 workflow contained only `isolation_probe`, and the Phase 5 discovery test explicitly forbade repository-local uv.
- **Fix:** Scoped isolation secrecy assertions to the preserved job, froze the exact expanded job set, and replaced the obsolete PATH-only uv expectation with same-job local materialization assertions.
- **Files modified:** `tests/test_phase6_workflow.py`, `tests/test_discovery_workflow.py`
- **Verification:** The affected workflow regression passed with 86 tests; the plan command passed with 52 tests and 12 unrelated deselections.
- **Committed in:** `bd8f749`

**3. [Rule 1 - Bug] Restored the historical Phase 5 acceptance fixture lifecycle**
- **Found during:** Wave 3 post-merge full-suite verification
- **Issue:** `tests/test_phase5_acceptance.py` copied the current Phase 6-modified workflow bytes while retaining Phase 5 Gate B4 evidence bound to the prior discover, publish, and canary digests, so the positive fixture mixed two valid but incompatible lifecycles.
- **Fix:** Added a RED exact-digest fixture contract, restored only the three historical Gate-B4-bound workflow byte sequences inside the positive fixture, and added a separate current-tree test that fails closed until fresh Gate B4 evidence exists.
- **Files modified:** `tests/test_phase5_acceptance.py`
- **Verification:** The RED test failed with all three current digests, then passed after the fix; all 25 Phase 5 acceptance tests and all 29 Phase 6 source-execution tests passed; the independent Phase 6 verifier reported `phase6 source execution valid`; full locked pytest reported 2,080 passed, 32 skipped, and only the two planned future Phase 6 RED failures.
- **Committed in:** `279c7f0` (RED), `1fa3f49` (GREEN)

**4. [Rule 1 - Bug] Accepted official pinned-uv build metadata without weakening exact version admission**
- **Found during:** Plan 06-06 hosted execution review after runs `30430010273` and `30441596331`
- **Issue:** Every authoritative workflow required the complete `uv --version` output to equal `uv 0.11.29`, but the actual pinned official binary reports `uv 0.11.29 (901092ee1 2026-07-15 aarch64-apple-darwin)`. Both authorized hosted runs therefore failed before the campaign and artifact steps.
- **Fix:** Replaced all 15 exact-full-output comparisons with one uniform Bash guard requiring program token `uv`, version token `0.11.29`, and either no suffix or a non-empty parenthesized metadata suffix. Updated the independent structural verifier and historical Phase 5 fixture reconstruction without changing uv, the lock, checkout, runner, synchronization, or locked source invocation.
- **Files modified:** `.github/workflows/discover.yml`, `.github/workflows/publish-candidate.yml`, `.github/workflows/gate-b4-canary.yml`, `.github/workflows/phase6-acceptance.yml`, `tools/verify_phase6_source_execution.py`, `tests/test_phase6_source_execution.py`, `tests/test_publication_security.py`, `tests/test_discovery_workflow.py`, `tests/test_phase5_acceptance.py`
- **Verification:** The RED behavior test failed against the real repository-local pinned uv, then all 30 source-execution tests, the independent verifier, 59 four-workflow tests, 25 Phase 5 lifecycle tests, and full Ruff passed. Full locked pytest classified `2121 passed, 14 skipped, 1` pre-existing planned RED failure for the still-missing Phase 6 repository verifier.
- **Committed in:** `49a5482` (RED), `3b6b189` (GREEN)

**5. [Rule 1 - Bug] Mounted the missing hosted Python runtime into empty-rootfs containers**
- **Found during:** Plan 06-06 hosted run `30443794922`
- **Issue:** The locked `.venv/bin/python` resolves into the GitHub-hosted Python tool cache outside the repository, while each empty-rootfs Docker invocation mounted only system roots, the repository, and `/probe`. The venv was visible but its base interpreter/runtime was absent, so the campaign failed before producing a report or artifact.
- **Fix:** Resolve `sys.base_prefix` with the locked venv interpreter in the same shell that launches Docker; reject missing, multiline, noncanonical, nonabsolute, cache-root-equal, or non-`${RUNNER_TOOL_CACHE}/Python/` descendants; require the resolved interpreter and Python 3.13 runtime files; then mount only the exact base prefix read-only at the identical container path in every isolation-probe and offline-adversarial Docker run. The independent verifier now admits exactly six such invocations and rejects every broadened mount mutation.
- **Files modified:** `.github/workflows/phase6-acceptance.yml`, `tools/verify_phase6_source_execution.py`, `tests/test_phase6_workflow.py`, `tests/test_phase6_source_execution.py`
- **Verification:** The RED suite failed on the missing mount; after GREEN, 70 focused workflow/source-execution tests and the independent verifier passed. Full locked pytest classified 2,138 passed, 14 skipped, and the one pre-existing planned `verify_repository` RED failure. Ruff check and changed-file format checks passed.
- **Committed in:** `e86c809` (RED), `b48e1fd` (GREEN)
- **Superseded by:** The approved repository-managed Python correction below after run `30447435387` proved the hosted toolcache root was unavailable during runtime preflight.

**6. [Rule 2 - Missing critical functionality] Added bounded failure diagnostics before any third hosted hypothesis**
- **Found during:** Plan 06-06 hosted run `30446151495`
- **Issue:** The campaign step failed after locked-toolchain verification, but its success-only evidence upload was skipped and raw logs were prohibited, leaving no bounded way to distinguish the internal campaign substage.
- **Fix:** Initialize a strict diagnostic JSON before runtime preflight; advance only through seven closed stages; retain integer overall/control/direct/child statuses with `-1` as the only not-run sentinel; preserve the original nonzero exit in the EXIT trap; and upload only that exact file for one day when the stable campaign step reports failure. The independent verifier rejects every tested widening and the diagnostic cannot enter evidence or canonical state.
- **Files modified:** `.github/workflows/phase6-acceptance.yml`, `tools/verify_phase6_source_execution.py`, `tests/test_phase6_workflow.py`, `tests/test_phase6_source_execution.py`
- **Verification:** RED failed on the absent stable campaign ID and absent verifier result. GREEN passed 124 affected tests plus the independent verifier; full locked pytest classified 2,156 passed, 14 skipped, and only the unchanged planned Phase 6 repository-verifier RED failure. Full Ruff lint passed and all changed Python files passed Ruff format.
- **Committed in:** `1a6d668` (RED), `7d94188` (GREEN)

### Approved Architectural Correction

**7. [Rule 4 - User approved] Replaced hosted toolcache dependence with exact repository-managed CPython**
- **Found during:** Plan 06-06 hosted run `30447435387`
- **Issue:** Runtime preflight deterministically failed before any container because the workflow required `.venv` base authority under `${RUNNER_TOOL_CACHE}/Python`, but the locked runtime did not satisfy that hosted-path assumption. Repeating the same dispatch could not create new evidence.
- **Approved change:** Materialize exact CPython `3.13.14` under canonical `${GITHUB_WORKSPACE}/.tools/python` in all 15 authoritative jobs, bind locked sync to the discovered managed interpreter with downloads disabled, and let all six network-none containers use that runtime only through the same-path read-only repository mount.
- **Security boundary:** Reject alternate versions, default/home/system install roots, traversal or symlink escapes, missing managed-only flags, interpreter drift, writable/remapped repository mounts, external Python mounts, and absent container-side managed-runtime environment.
- **Files modified:** `.github/workflows/discover.yml`, `.github/workflows/publish-candidate.yml`, `.github/workflows/gate-b4-canary.yml`, `.github/workflows/phase6-acceptance.yml`, `tools/verify_phase6_source_execution.py`, `tests/test_phase6_source_execution.py`, `tests/test_phase6_workflow.py`, `tests/test_publication_security.py`, `tests/test_phase5_acceptance.py`
- **Verification:** The RED contract failed on the absent managed-runtime result and workflow markers. GREEN passed 180 affected tests, the independent source-execution verifier, Ruff lint/format, `git diff --check`, and Bash syntax validation for all 35 workflow run blocks. Full locked pytest classified 2,168 passed, 14 skipped, and only the unchanged planned Phase 6 `verify_repository` RED failure.
- **Committed in:** `80eaa3a` (RED), `a8f42d1` (GREEN)

### Post-Checkpoint Auto-Fixed Issue

**8. [Rule 1 - Bug] Installed SkillScout in every fresh authoritative venv**
- **Found during:** Plan 06-06 Task 3 hosted run `30508458266`
- **Issue:** Each authoritative job deleted `.venv` and then ran `uv sync --locked --no-install-project`. The fresh venv therefore contained locked dependencies but no SkillScout installation, so the offline control could not import `skillscout.application.acceptance` and returned 1 even though direct and child denial probes still returned 97.
- **Fix:** Removed only `--no-install-project` from all 15 authoritative fresh sync commands across the four frozen workflow paths, then updated the dependency-free source verifier and owner contracts. Locking, managed CPython, offline/no-sync container execution, read-only mounts, probes, scenarios, credentials, publication, retention, and diagnostic schema are unchanged.
- **Behavior proof:** The RED test executes the parsed production init against a project-free locked environment after deleting a pre-existing venv. GREEN imports `skillscout.application.acceptance` and runs the target adversarial control node successfully; mutating the exact sync back to `--no-install-project` makes both return 1.
- **Files modified:** `.github/workflows/discover.yml`, `.github/workflows/publish-candidate.yml`, `.github/workflows/gate-b4-canary.yml`, `.github/workflows/phase6-acceptance.yml`, `tools/verify_phase6_source_execution.py`, `tests/test_phase6_source_execution.py`, `tests/test_phase6_workflow.py`, `tests/test_publication_security.py`, `tests/test_discovery_workflow.py`
- **Verification:** 130 four-workflow owner tests and 137 Phase 6 workflow/adversarial/source tests passed; the independent verifier reported `phase6 source execution valid`; all 35 workflow run blocks passed `bash -n`; full locked pytest classified 2,169 passed, 14 skipped, and only the unchanged planned repository-verifier RED failure.
- **Committed in:** `5aa3aa2` (RED), `e425de3` (GREEN)

**9. [Rule 4 - User approved] Replaced pytest teardown evidence with an independent deterministic runner**
- **Found during:** Review of the bounded diagnostic from hosted run `30510875649`
- **Issue:** The workflow executed the entire development pytest module and relied on a session teardown to write campaign evidence. A control status of 1 stopped the teardown report but could not safely distinguish scenario/assertion failure from report-write failure.
- **Approved change:** Add an installed-package Phase 6 runner with an exact ordered 25-node registry, closed binding inputs, synthetic-canary scans, canonical bounded atomic output, and distinct closed diagnostics; keep pytest only as a consumer that executes and mutation-tests real runner behavior.
- **Security boundary:** The runner has no network, tool, subprocess, untrusted-code, arbitrary path, caller-supplied scenario, credential, catalog, publication, or canonical-state authority. Empty-rootfs, read-only same-path repository mount, `--network none`, direct/child denial probes, one-day failure-only artifact, and exact exit status remain unchanged.
- **Files modified:** `src/skillscout/application/phase6_adversarial_runner.py`, `.github/workflows/phase6-acceptance.yml`, `tools/verify_phase6_source_execution.py`, `tests/test_phase6_campaign_runner.py`, `tests/test_phase6_adversarial.py`, `tests/test_phase6_workflow.py`
- **Verification:** RED produced exactly five expected failures. GREEN passed 270 affected tests with 12 skips and only the future repository-verifier node deselected; the independent source verifier passed; all 35 workflow run blocks passed `bash -n`; full Ruff passed; full locked pytest classified 2,175 passed, 14 skipped, and only `test_required_phase6_repository_verifier_is_missing` failed.
- **Committed in:** `f32fa2d` (RED), `e5ab102` (GREEN)

---

**Total deviations:** 7 auto-fixed (5 bugs, 1 blocking issue, 1 missing critical diagnostic boundary) plus 2 user-approved architectural corrections
**Impact on plan:** The original two fixes were necessary to execute the pre-existing RED contract and preserve prior security ownership under the stricter planned baseline. The first post-merge fix restored historical Phase 5 fixture correctness. The second made the pinned official uv executable admissible without widening its authority. The third attempted to expose the hosted Python runtime but was superseded when the toolcache assumption failed deterministically. The fourth added bounded diagnostic observability. The approved fifth correction now owns the exact Python runtime inside the repository without widening container mounts or provider/publication authority. The sixth post-checkpoint correction restores the project installation required by every authoritative source entry without changing the lock or execution boundary. The seventh correction removes pytest lifecycle ownership from hosted evidence and makes the two previously ambiguous internal failure classes independently observable. Every workflow-byte authorization remains stale.

## Issues Encountered

- The sandbox initially denied uv cache and Git index-lock access. The exact locked commands and normal commit hooks were rerun with approved filesystem access; no dependency was installed or changed.
- Workflow byte changes intentionally stale historical Phase 5 Gate B4 digests. No Gate B4, publication, remote dispatch, candidate repository execution, or credential inspection occurred in this plan.
- Wave 3 post-merge verification exposed a test-harness lifecycle mismatch: historical Phase 5 evidence had been paired with current Phase 6 workflow bytes. The verifier correctly failed closed; no production verifier, evidence, approval, or workflow byte was changed.
- Hosted runs `30430010273` and `30441596331` both failed at repository-local locked-toolchain verification and produced zero artifacts. No raw logs or artifact content were opened, and no canonical hosted-isolation or offline-campaign fact exists.
- Hosted run `30443794922` passed checkout, pinned uv materialization, and locked sync, then failed inside the kernel-isolated campaign because the repository-visible venv referenced an unmounted hosted Python base prefix. It produced zero artifacts and no canonical facts; no retry is authorized.
- Hosted run `30446151495` passed checkout, pinned uv materialization, and locked-toolchain verification, then failed in the campaign step. Its success-only evidence upload was skipped, artifact count was zero, raw logs were not opened, and no canonical facts were written. This correction adds diagnostics only; it does not explain or fix that failure.
- Hosted run `30447435387` deterministically failed during runtime preflight before any container launched because the hosted toolcache path assumption was not satisfied. No artifact was accessed, no canonical fact was written, and no retry, push, or dispatch was authorized or performed.
- Hosted run `30508458266` reached the kernel-isolated campaign but the control returned 1 because the fresh venv could not import `skillscout.application.acceptance`; direct and child probes both retained the required denial status 97. The ordinary baseline was 36 passed, the synthetic-canary environment was 36 passed, and the read-only-repository case was 36 passed. Removing the project installation record reproduced the first-test failure consistently; restoring the record produced 1 passed.
- The confirmed root cause was the static contract requiring `uv sync --locked --no-install-project` after deleting `.venv`. This correction used only local locked tests and the user-supplied bounded failure facts; it did not read artifacts or raw logs, push, dispatch, write canonical state, execute candidate source, or access any remote system.
- After explicit fresh authorization, remote `main` and local `main`/`HEAD` were revalidated at `b1425f7f72407f08463578db387e84d79d72e2df`, with Phase 6 workflow SHA-256 `1e938070e70aabcf84a5d6d8fce5c674b36d19d7d6fe8771adffdd0f0ecd6fe5`. GitHub rejected the exact-SHA dispatch ref with HTTP 422 and created no run; after a fresh remote-main equality check, the authorized `main` fallback created exactly run `30510875649` attempt 1.
- Run `30510875649` failed in `offline_adversarial`. Its only artifact was the one-day bounded diagnostic `8747046558`, named `phase6-offline-adversarial-diagnostic-30510875649-1`, with metadata size 416 bytes, ZIP SHA-256 `26faa56b695126a6d65cea55209787911973570b072f2e39251ba976b1306755`, and exact JSON SHA-256 `112b9c040433f10524b08a62d6e11764146b6e08f64e17a1fa3ed316641142ff` over 378 bytes. The strict diagnostic was bound to the exact source/workflow/run/attempt, stopped at `campaign-report`, and recorded overall/control/direct/child statuses `1/1/97/97`.
- The failed run grants no campaign or hosted-isolation credit. No raw logs or other artifacts were opened, no retry occurred, and neither `acceptance_hosted_isolation_capability` nor `acceptance_offline_adversarial_run` was written to canonical state.
- The bounded run `30510875649` diagnostic is now explicitly classified as ambiguous: its old pytest-owned control status does not identify whether scenario evaluation/assertion or final report writing failed. No root cause is fabricated from that artifact.
- The current workflow SHA-256 values are `71c174175b03355f432348bda9fca47ee72bee20a939d87720b7c32d4fe370e4` (discover), `0bb486d9f06cc93d97a953bc1f40b6b2f206c9fdccdc914a90af1c9388faac19` (publish), `ad06ccec08cf1df76a395b14574957e69aebe3ce78b2892c22c23912ed672ccc` (canary), and `9c62787e9a061ef061957b4c57b2635145d1c35df7063acc49ad668d2ff352ef` (Phase 6 acceptance). All earlier workflow digests, workflow approvals, exact-source authorizations, dispatch approvals, and Gate B4 bindings are stale.

## Authentication Gates

None.

## Known Stubs

None. The scan found no placeholder, TODO, FIXME, empty UI data source, or unimplemented authoritative workflow route.

## User Setup Required

None - no new dependency or external service configuration is required by this plan.

## Next Phase Readiness

- Plan 06-06 Task 3 remains incomplete. Do not create `06-06-SUMMARY.md` or grant campaign credit from any failed run.
- Any retry requires a new human authorization bound to the then-exact local/remote HEAD and Phase 6 workflow SHA-256 `9c62787e9a061ef061957b4c57b2635145d1c35df7063acc49ad668d2ff352ef`; it cannot inherit the authorization consumed by run `30510875649` and grants no Gate B4, publication, artifact-read, or canonical-state authority.
- Plans 06-07 through 06-14 remain blocked from treating the workflow as hosted evidence until an authorized exact run succeeds and its bounded facts rebuild canonically.
- Fresh Gate B4 and value publication remain unauthorized until later checkpoints bind the corrected exact workflow bytes and fixed catalog identity.

## Self-Check: PASSED

- All eight created/modified task files exist.
- Task commit `bd8f749` exists in Git history and contains no file deletions.
- The exact plan verification passed with 52 tests and 12 unrelated deselections.
- The wider affected workflow regression passed with 86 tests.
- The independent source-execution verifier reported `phase6 source execution valid`.
- Ruff check, Ruff format check, and `git diff --check` passed.
- Stub and threat-surface scans found no untracked placeholder or threat outside the plan's T-06-47, T-06-48, T-06-49, and T-06-SC register.
- Post-merge RED commit `279c7f0` and GREEN commit `1fa3f49` exist and modify only `tests/test_phase5_acceptance.py`.
- The targeted lifecycle test and all 25 Phase 5 acceptance tests passed while preserving the external-cwd and read-only metadata assertions.
- Second post-merge RED commit `49a5482` and GREEN commit `3b6b189` exist.
- All 30 Phase 6 source-execution tests passed, including real execution of every version guard against the pinned uv and invalid-output mutations; the independent verifier reported `phase6 source execution valid`.
- The four affected workflow test modules passed 59 tests, all 25 Phase 5 acceptance lifecycle tests passed without warnings, full Ruff passed, and `git diff --check` passed.
- Full locked pytest completed with 2,121 passed and 14 skipped; its only failure is the pre-existing planned `verify_repository` RED node owned by the incomplete later Phase 6 acceptance verifier work.
- Full locked pytest completed with 2,080 passed, 32 skipped, and only the two planned future Phase 6 RED nodes failing; no Phase 5 regression remains.
- Hosted-runtime RED commit `e86c809` and GREEN commit `b48e1fd` exist and contain no file deletions.
- All 70 focused Phase 6 workflow/source-execution tests passed, and the independent verifier reported `phase6 source execution valid`.
- Full locked pytest completed with 2,138 passed and 14 skipped; its only failure is the unchanged pre-existing planned `verify_repository` RED node.
- Full Ruff check, changed-file Ruff format check, and `git diff --check` passed; the repository-wide format check reports only the pre-existing 87-file formatting baseline outside this correction.
- Diagnostic RED commit `1a6d668` and GREEN commit `7d94188` exist and contain no file deletions.
- All 124 affected workflow/source-execution/adversarial tests passed, the independent verifier reported `phase6 source execution valid`, and the extracted campaign shell passed `bash -n`.
- Full locked pytest classified 2,156 passed, 14 skipped, and only the unchanged planned `test_required_phase6_repository_verifier_is_missing` RED failure.
- Full Ruff lint passed; the three changed Python files passed Ruff format, while the repository-wide format check retained the same pre-existing 87-file baseline.
- Repository-managed-runtime RED commit `80eaa3a` and GREEN commit `a8f42d1` exist and contain no file deletions.
- Exact managed CPython `3.13.14` install, discovery, locked no-download sync, and runtime validation completed locally.
- All 180 affected tests passed, the independent verifier reported `phase6 source execution valid`, all 35 workflow run blocks passed `bash -n`, and Ruff lint/changed-file format plus `git diff --check` passed.
- Full locked pytest classified 2,168 passed, 14 skipped, and only the unchanged planned `test_required_phase6_repository_verifier_is_missing` RED failure.
- Fresh-project RED commit `5aa3aa28eed11adefe3ccaa0bb294bdb22e6426e` and GREEN commit `e425de3acf9ccb6c8ebeabd3a4bb90ea80403070` exist and contain no file deletions.
- The real fresh-control behavior test passed and proved the `--no-install-project` production mutation makes both isolated import and the target control test return 1.
- The four workflow owner suites passed 130 tests; the Phase 6 workflow/adversarial/source suites passed 137 tests; the independent verifier reported `phase6 source execution valid`; and all 35 workflow run blocks passed `bash -n`.
- Full locked pytest classified 2,169 passed, 14 skipped, and only the unchanged planned `tests/test_phase6_acceptance.py::test_required_phase6_repository_verifier_is_missing` RED failure.
- Full Ruff lint, changed-file Ruff format, and `git diff --check` passed. Neither `pyproject.toml` nor `uv.lock` changed.
- Deterministic-runner RED commit `f32fa2d` and GREEN commit `e5ab102` exist and contain no file deletions.
- The runner registry exactly matches all 25 committed matrix nodes; its real module/CLI behavior separately classifies scenario assertion and final report-write failures, and restoring pytest teardown ownership fails the behavior suite.
- The affected regression passed with 270 tests, 12 skips, and only the future repository-verifier node deselected; the independent source verifier reported `phase6 source execution valid`; all 35 workflow run blocks passed `bash -n`; and full Ruff lint plus changed-file formatting passed.
- Full locked pytest classified 2,175 passed, 14 skipped, and only the unchanged planned `tests/test_phase6_acceptance.py::test_required_phase6_repository_verifier_is_missing` RED failure.
- The independent offline acceptance verifier correctly remains `phase6 acceptance incomplete`; no hosted success or canonical fact was fabricated.
- Final workflow SHA-256 values are discover `71c174175b03355f432348bda9fca47ee72bee20a939d87720b7c32d4fe370e4`, publish `0bb486d9f06cc93d97a953bc1f40b6b2f206c9fdccdc914a90af1c9388faac19`, canary `ad06ccec08cf1df76a395b14574957e69aebe3ce78b2892c22c23912ed672ccc`, and Phase 6 acceptance `9c62787e9a061ef061957b4c57b2635145d1c35df7063acc49ad668d2ff352ef`.
- Before the deterministic-runner correction, the workflow SHA-256 values bound to the failed dispatch were discover `71c174175b03355f432348bda9fca47ee72bee20a939d87720b7c32d4fe370e4`, publish `0bb486d9f06cc93d97a953bc1f40b6b2f206c9fdccdc914a90af1c9388faac19`, canary `ad06ccec08cf1df76a395b14574957e69aebe3ce78b2892c22c23912ed672ccc`, and Phase 6 acceptance `1e938070e70aabcf84a5d6d8fce5c674b36d19d7d6fe8771adffdd0f0ecd6fe5`; those bindings are historical only.
- The fresh local/remote preflight matched `b1425f7f72407f08463578db387e84d79d72e2df`; the four frozen workflow SHA-256 values matched the approved bindings; 109 acceptance-domain/operations tests, 8 exact offline/canonical selector tests, the independent source verifier, and the fixed registry verifier passed before dispatch.
- Exact-SHA ref dispatch was rejected with HTTP 422 and created no run; the authorized `main` fallback created only run `30510875649` attempt 1.
- Artifact metadata contained exactly one one-day failure diagnostic. Its strict source/workflow/run/attempt/schema/status/digest checks passed; no raw logs or other artifact were read.
- No `06-06-SUMMARY.md` was created, no canonical acceptance fact was written, and no retry, credential inspection, Gate B4, catalog/default-branch/PR/publication mutation, cleanup, merge, approval, ready transition, or post-evidence push occurred.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-07-30*
