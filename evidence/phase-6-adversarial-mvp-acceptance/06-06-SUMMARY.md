---
phase: 06-adversarial-mvp-acceptance
plan: "06"
subsystem: acceptance-testing
tags: [github-actions, docker-network-none, adversarial, canonical-state, synthetic-canary]

requires:
  - phase: 06-02
    provides: Hosted isolation workflow contracts and fail-closed artifact policy
  - phase: 06-04
    provides: Strict hosted capability/offline run models and operations-owned persistence
  - phase: 06-15
    provides: Frozen source-only workflow boundary and hosted runtime corrections
provides:
  - Successful hosted kernel-isolated adversarial campaign over the exact seven-fixture corpus
  - Canonical hosted-isolation and offline-run facts bound to run 30519607061 attempt 1
  - Fresh three-store rebuild and exact two-fact acceptance snapshot
affects: [06-07, phase6-live-acceptance, acceptance-report]

tech-stack:
  added: []
  patterns:
    - One-shot exact-source hosted dispatch with fail-closed 422/no-run/main fallback
    - Noncanonical one-day artifact admission followed by typed canonical state promotion
    - Pre-Phase-6 operations facts replayed through the current owner before exact CAS

key-files:
  created:
    - .planning/phases/06-adversarial-mvp-acceptance/06-06-SUMMARY.md
  modified:
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Promote only the validated JSON evidence digest; retain the downloaded ZIP digest as transport metadata, not a third canonical fact."
  - "Replay the verified pre-Phase-6 operations fact objects through the current owner before CAS because the old projection predates acceptance digest tuples."
  - "Persist exactly the hosted capability and capability-bound offline run; no scenario, publication, credential, catalog, or cleanup fact was added."

patterns-established:
  - "Hosted campaign credit requires exact source/workflow/run/attempt binding, 0/97/97 control and denial statuses, exact corpus/scenario digests, and zero prohibited effects."
  - "A canonical acceptance promotion is complete only after non-force CAS, fresh ref fetch, full bundle equality, three-store rebuild, and per-kind projection equality."

requirements-completed: [TEST-02, TEST-03, TEST-04]

coverage:
  - id: D1
    description: Exact seven-fixture controlled campaign completed 22 credited scenarios under Docker network-none
    requirement: TEST-02
    verification:
      - kind: e2e
        ref: "GitHub Actions run 30519607061 attempt 1, offline_adversarial job 90796886351"
        status: pass
    human_judgment: false
  - id: D2
    description: Direct and child outbound probes were causally denied while untrusted execution, unauthorized effects, unapproved network effects, and synthetic canary hits remained zero
    requirement: TEST-04
    verification:
      - kind: integration
        ref: "independent bounded artifact validation: control/direct/child 0/97/97"
        status: pass
    human_judgment: false
  - id: D3
    description: Hosted capability and capability-bound offline run rebuild as exactly two operations-owned canonical facts
    requirement: TEST-03
    verification:
      - kind: integration
        ref: "canonical state commit 37f8dcbf74c85f2471670373fd03f71d9f155bae and root sha256:b4167cffc31969854260d4acd58b804f4823a4d25d078ef3b5dc88445b75c2e5"
        status: pass
    human_judgment: false

duration: 21min
completed: 2026-07-30
status: complete
---

# Phase 6 Plan 06: Hosted Offline Adversarial Campaign Summary

**A one-shot hosted Docker network-none campaign passed the exact seven-fixture/22-scenario corpus and promoted exactly two rebuilt canonical acceptance facts**

## Performance

- **Duration:** 21 min
- **Started:** 2026-07-30T06:23:56Z
- **Completed:** 2026-07-30T06:44:00Z
- **Tasks:** 3
- **Files modified:** 3 planning files; canonical state advanced by one non-force commit

## Accomplishments

- Dispatched exactly one authorized `offline-adversarial` run at source `a3c41cf8501bec435a646f140f52acedf1c5f312`. The exact-SHA ref returned HTTP 422 and created zero runs; a fresh `origin/main` equality proof then authorized the single `main` fallback.
- Validated the sole one-day evidence artifact against the frozen Phase 6 workflow, exact seven-fixture corpus aggregate `sha256:809fdb625fc9340ff6c4effa2dd5252311ea485bb4ec2c164aafb0835545d032`, 22 scenario IDs/result digests, the control/probe command digests, and all zero-effect counters.
- Persisted exactly `acceptance_hosted_isolation_capability` and `acceptance_offline_adversarial_run`, then fresh-fetched and rebuilt all three canonical stores with exact per-kind digest projections.

## Task Commits

1. **Task 06-06-01: Execute the complete controlled terminal and adversarial matrix** - `ca5c135` (RED), `8822d64` (GREEN), plus exact-corpus corrections `17fa07e`/`2625c27`
2. **Task 06-06-02: Enforce hosted kernel isolation and synthetic-secret scans** - `d05c70a` (RED), `27d7a41` (GREEN), with hosted-runtime corrections documented in `06-15-SUMMARY.md`
3. **Task 06-06-03: Dispatch and canonically attest the full hosted offline campaign** - canonical state commit `37f8dcbf74c85f2471670373fd03f71d9f155bae`; local plan metadata commit recorded after this summary

## Hosted Run and Artifact Evidence

- **Run:** `30519607061`, attempt `1`, event `workflow_dispatch`
- **Source:** `a3c41cf8501bec435a646f140f52acedf1c5f312`
- **Workflow SHA-256:** `7eca32de7c0468d18c180ebecf567d7239412e54c2776e43621930b894570f63`
- **Job:** `90796886351` / `offline_adversarial` / `success`
- **Artifact:** `8750213543` / `phase6-offline-adversarial-30519607061-1`
- **Artifact metadata:** 2,077 bytes, retention 1 day, expires `2026-07-31T06:27:13Z`
- **ZIP SHA-256:** `74a3c1df41c64c078ecb6be07975fe022faa026a7bcff8faaef8285126946bb9`
- **JSON:** exactly `offline-evidence.json`, 5,125 bytes, SHA-256 `1002f6398dbde5c98f5fb1f8ae1d08b297ce287c54e82dee12682f159adeec48`
- **Scenario matrix:** `sha256:d99f1d35adfc1c694d92afa511cefb23ab6c979e9020252157715b193dfaaaa5`
- **Synthetic scan manifest:** `sha256:e8f12071891362e3a4b3c99da892236b7b574ab2603263ef8750ea2153ac7771`
- **Control/direct/child statuses:** `0/97/97`
- **Credited scenarios:** `22`; required IDs, completed IDs, and result digests were exact, sorted, unique, and equal in cardinality
- **Forbidden effects:** untrusted execution `0`, unapproved network `0`, unauthorized effects `0`, synthetic canary hits `0`

Raw workflow logs were never opened. No diagnostic artifact existed or was accessed.

## Canonical State Evidence

- **Prior state head:** `eeea094ee0baf018a55071c536005e8467d4c3e4`
- **Prior state root:** `sha256:fbf4b1cd398fbdd5b6ceaa84d33119c38589693352db4e1dd036043761de2425`
- **New state commit:** `37f8dcbf74c85f2471670373fd03f71d9f155bae`
- **New state tree:** `671a6e94023aba83f1f60077142906dfae6ddd13`
- **New state root:** `sha256:b4167cffc31969854260d4acd58b804f4823a4d25d078ef3b5dc88445b75c2e5`
- **Hosted capability digest:** `sha256:cc6f4802e74ec07450958224235b8f0baa8748e74f64b5a1f67c3484998b500a`
- **Offline run digest:** `sha256:f37b81258d966c6683fb16d50aee537e35851dfd41f232490f89d7b0dc228e0b`
- **Three-store projection digest:** `sha256:c69f87f4fc213daa36faed3151f0ffe7f99da243363e197db8e59cfb2640b69c`

The fresh reread reproduced the exact candidate bundle, rebuilt pipeline/operations/publication stores, and returned a two-record acceptance snapshot with only the two required kinds and exact per-kind digest tuples.

## Decisions Made

- Used the evidence JSON digest as `probe_artifact_digest` because it is the validated bounded content; the ZIP digest remains non-authoritative transport metadata.
- Recorded reviewer identity `codex-phase6-executor` at `2026-07-30T06:40:15.000000Z`; no human approval token or credential value was fabricated or persisted.
- Kept the hosted job credential-free and performed the protected state CAS separately through configured gh/keyring transport without extracting or printing the credential.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Rebuilt the pre-Phase-6 operations projection through current owner facts**

- **Found during:** Task 06-06-03 canonical state admission
- **Issue:** The verified canonical parent predated the Phase 6 acceptance projection and therefore lacked the fifteen acceptance digest tuples. Its pipeline and publication exports remained valid, but direct current-code three-store parsing and raw operations DB opening correctly failed closed.
- **Fix:** Revalidated every old operations fact object and digest, replayed those facts through `OperationsStateStore`'s current closed registry, rebuilt all three owners from their canonical JSON exports, and proved the only new fact objects were the two plan-authorized kinds before CAS.
- **Files modified:** No repository source files; canonical state only
- **Verification:** Offline rehearsal, non-force CAS, fresh Git-object reread, exact bundle equality, three-store rebuild, and per-kind snapshot checks all passed.
- **Canonical commit:** `37f8dcbf74c85f2471670373fd03f71d9f155bae`

**Total deviations:** 1 auto-fixed blocking state-schema migration.

**Impact on plan:** The correction preserved every prior fact digest and introduced no third acceptance fact, dependency, workflow, publication, catalog, credential, or cleanup authority.

## Authentication Gates

- GitHub access used the already configured `alexzhu0` gh/keyring session.
- No token value was read, printed, logged, copied, staged, or persisted. An attempted direct token injection was rejected before execution and was replaced with gh-internal keyring transport.

## Verification

- Plan-scoped campaign/canonical tests: `8 passed, 92 deselected`
- Pre-dispatch domain/operations/workflow admission: `81 passed, 197 deselected`
- Closed four-workflow source verifier: `phase6 source execution valid`
- Independent artifact/canonical verifier: exact corpus, 22 scenarios, `0/97/97`, two facts, fresh rebuild all passed
- Full locked pytest: `2193 passed, 14 skipped, 1 failed`

The sole full-suite failure is the intentionally frozen future repository-level RED node `test_required_phase6_repository_verifier_is_missing`. It does not contradict this plan's hosted or canonical evidence.

## Known Stubs

- `tools/verify_phase6_acceptance.py --offline-only` remains the Wave 0 registry stub and deliberately returns `phase6 acceptance incomplete`; it does not consume remote canonical state. The exact remote-bound independent verification was performed directly in this task. Plan 06-07 must replace or route this stub before using that exact command as its authorization gate.
- The whole-repository `verify_repository` Phase 6 verifier remains an expected later-plan RED contract.

Neither stub prevents the Plan 06-06 hosted campaign or canonical two-fact goal from being achieved, but both remain blocking for their later owning plan.

## Issues Encountered

- The repository-local uv cache required sandbox authorization; the locked command and dependency graph were unchanged.
- One read-only gh blob request failed transiently. A metadata-only check confirmed the exact blob identity/size, and the full state restore was repeated without any state mutation.

## User Setup Required

None. The approved run and canonical write completed through the configured gh/keyring session; no new secret, package, or remote permission was introduced.

## Next Phase Readiness

- Plan 06-07 now has exact canonical hosted-isolation and offline-run facts at state commit `37f8dcbf74c85f2471670373fd03f71d9f155bae`.
- No live Search, DeepSeek, catalog, Draft PR, publication, Gate B4, cleanup, merge, approval, or ready-for-review action occurred.
- Before opening the Plan 06-07 credential checkpoint, its independent offline-only verifier path must consume and validate this exact state commit/root rather than the Wave 0 incomplete stub.

## Self-Check: PASSED

- `06-06-SUMMARY.md` exists and the hosted run, artifact, canonical commit, two fact digests, and rebuild projection are recorded.
- Task implementation commits exist in Git history.
- The canonical state ref fresh-rereads at `37f8dcbf74c85f2471670373fd03f71d9f155bae` and rebuilds to exactly two target facts.
- The local repository worktree contains only intended planning close-out changes before the final metadata commit.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-07-30*
