---
phase: 06-adversarial-mvp-acceptance
plan: "07"
subsystem: acceptance
tags: [github-search, canonical-state, benchmark-lock, pydantic, sqlite]

requires:
  - phase: 06-04
    provides: Typed Phase 6 acceptance fact registry and benchmark contracts
  - phase: 06-06
    provides: Rebuildable hosted-isolation and offline-adversarial canonical facts
provides:
  - Real bounded GitHub Search nomination with 31 role-neutral fixed-SHA candidates
  - Canonical acceptance_nomination fact and independently rebuilt three-store state
  - Human-approved five-repository benchmark manifest and acceptance_benchmark_lock fact
affects: [06-08-live-benchmark, acceptance-campaign, canonical-state]

tech-stack:
  added: []
  patterns:
    - Role-neutral Search nomination followed by separate accountable human role assignment
    - Exact-parent non-force state CAS with fresh three-store reconstruction

key-files:
  created:
    - .planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json
  modified:
    - src/skillscout/domain/acceptance.py
    - src/skillscout/application/acceptance.py
    - src/skillscout/bootstrap.py
    - src/skillscout/cli.py
    - tools/verify_phase6_acceptance.py
    - .github/workflows/phase6-acceptance.yml
    - tests/test_acceptance_domain.py
    - tests/test_acceptance_application.py
    - tests/test_operations_state.py
    - tests/test_phase6_acceptance.py
    - tests/test_phase6_workflow.py

key-decisions:
  - "Search nominations contain immutable repository identity, SHA, license, and evidence only; evaluator roles exist only in the human-locked benchmark entries."
  - "Historical Plan 06-06 verification resolves its exact commit object instead of equating historical evidence with the mutable current state-branch head."
  - "The strict manifest remains canonical JSON; deterministic JSON-array normalization preserves strict tuple contracts at the file boundary."

patterns-established:
  - "Nomination authority: restore exact state, acquire at most 100 public candidates, pin commit and permissive license, persist, then verify state CAS."
  - "Human lock authority: re-admit every selected entry by nomination-entry digest before recording a versioned self-digested manifest."

requirements-completed: [TEST-01, TEST-02]

coverage:
  - id: D1
    description: Real bounded Search produced 31 role-neutral, permissively licensed, fixed-SHA nomination entries.
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "GitHub Actions run 30526079398 and tests/test_phase6_acceptance.py nomination tests"
        status: pass
    human_judgment: false
  - id: D2
    description: Exactly five nominated repositories carry the approved 1 positive, 1 multi-workflow positive, 2 negative, and 1 borderline distribution.
    requirement: TEST-02
    verification:
      - kind: manual_procedural
        ref: "Reviewer alexzhu0 approval bound by BenchmarkLockAttestationV1 sha256:19fa84cb98a6a545199cb35d11079a1583044c9d933d5b9bf0edd0fd03a7a746"
        status: pass
      - kind: unit
        ref: "tests/test_acceptance_domain.py#test_locked_manifest_strict_json_round_trip_preserves_tuple_contracts"
        status: pass
    human_judgment: true
    rationale: Repository-role hypotheses require accountable human selection even though identity, distribution, and digest binding are automated.
  - id: D3
    description: Nomination and benchmark-lock facts rebuild exactly from canonical three-store state.
    requirement: TEST-01
    verification:
      - kind: integration
        ref: "Fresh rebuild of state commits f2cbe1db96185df4880c732bfd73cbc3b32d2ad3 and 500b3de1b14d8c0d1e0a4d3a35bf027eb19db2eb"
        status: pass
    human_judgment: false

duration: 1h 35m
completed: 2026-07-30
status: complete
---

# Phase 6 Plan 07: Search Nomination and Benchmark Lock Summary

**Real GitHub Search produced a canonical 31-entry fixed-SHA nomination set, followed by an accountable five-repository human lock rebuilt exactly from three-store state.**

## Performance

- **Duration:** 1h 35m
- **Started:** 2026-07-30T07:13:33Z
- **Completed:** 2026-07-30T08:47:53Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Ran one fresh authorized production nomination at source `7fed160bc10c7ad85f027939b3f79884bb6e691f`; run `30526079398` produced 31 unique public candidates under the 100-candidate ceiling with only MIT or Apache-2.0 licenses.
- Persisted `acceptance_nomination` digest `sha256:84db903b9a75a0fc413c89c16abc5c596a1b9501dea16e871686c405084cf477` at state commit `f2cbe1db96185df4880c732bfd73cbc3b32d2ad3`, root `sha256:cecec575e415334593d0e5163af3baf07b4a0982539d78767f77df6f4c0a5926`.
- Human reviewer `alexzhu0` locked the exact five approved identities in manifest `sha256:3d7f16e60c3336c5c73d174273a01740daa39ab1b506a437be753d94aa387185`; the byte/field-equivalent `acceptance_benchmark_lock` fact rebuilds from state commit `500b3de1b14d8c0d1e0a4d3a35bf027eb19db2eb`, root `sha256:a9131fdfec479202f1f626834c805bece17f933e802ecb9877827a9525f94d85`.
- Kept nomination structurally incapable of semantic, publication, catalog, PR, merge, approval, Gate B4, or cleanup effects; the final run executed only the `nominate` job.

## Locked Benchmark

| Role | Repository | Numeric ID | Fixed SHA | SPDX |
|---|---|---:|---|---|
| positive_multi_workflow | `DevExpress/agent-skills` | 1256973124 | `baa2e1c79b9d46420f4c0b2fe166a12cff20cae9` | MIT |
| positive | `Growth-Today/claude-skills` | 1295183605 | `468d5458f8b9d97bff9c03500fb8fe26e5137c79` | MIT |
| negative | `root-signals/scorable-sdk` | 790539692 | `a8b8c5eba796a63c61efd8eeddb03398e96d0133` | Apache-2.0 |
| negative | `adobe/spacecat-api-service` | 700271527 | `45b7b95f8daf102a6e86e86aa0e8700dbf59dcae` | Apache-2.0 |
| borderline | `TencentCloudBase/CloudBase-AI-Toolkit` | 988892963 | `730c03aef0c0cbaa3ab535ed905eede58cd43492` | MIT |

The manifest stores full name plus exact SHA, so every reproducibility locator is deterministically `https://github.com/{full_name}/tree/{exact_commit_sha}` without adding an unversioned schema field.

## Task Commits

1. **Task 1: Authorize exact Search nomination credential use** — `c77b8bb`, `b7d08ef`
2. **Task 2: Run Search-derived nomination and persist canonical facts** — `7fed160`
3. **Task 3: Lock the exact five-repository benchmark** — `2980379`

## Files Created/Modified

- `.planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json` — Canonical version-1 human lock with five exact identities and complete nomination evidence.
- `src/skillscout/domain/acceptance.py` — Role-neutral nomination entries, exact nomination linkage, and strict canonical manifest JSON normalization.
- `src/skillscout/application/acceptance.py` — Bounded Search nomination, exact manifest re-admission, and state-persisted lock behavior.
- `src/skillscout/bootstrap.py` — Late-bound nomination Search/state capabilities and verified three-store CAS.
- `src/skillscout/cli.py` — Production `nominate-benchmark` result and state identities.
- `tools/verify_phase6_acceptance.py` — Immutable historical Plan 06-06 commit-object reconstruction.
- `.github/workflows/phase6-acceptance.yml` — Exact state-root copy and nomination runtime prerequisites.
- `tests/test_acceptance_domain.py` — Role separation and strict manifest JSON round-trip coverage.
- `tests/test_acceptance_application.py` — Search filtering/pinning and persist-before-CAS coverage.
- `tests/test_operations_state.py` — Nomination owned-state export/rebuild equality.
- `tests/test_phase6_acceptance.py` — Sanitized persisted CLI result and offline gate coverage.
- `tests/test_phase6_workflow.py` — Workflow authority and state-root runtime coverage.

## Decisions Made

- Search is allowed to nominate but not label. Human-assigned evaluator hypotheses are introduced only after the exact nomination digest and entry digests are visible.
- A formal candidate is accepted only after public/non-fork/non-archived filtering, metadata identity equality, permissive-license confirmation at a pinned commit, and five deterministic evidence digests.
- State updates use an exact-parent, non-force CAS and are credited only after complete bundle equality plus a fresh three-store projection rebuild.
- Historical prerequisite verification remains tied to the immutable Plan 06-06 commit object; the mutable state head may legitimately advance after later accepted facts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Repaired nomination workflow preflight state-root materialization**
- **Found during:** Task 1
- **Issue:** The first authorized nomination run `30522590713` failed Gate B3 before Search because the exact state-root prerequisite was not materialized correctly.
- **Fix:** Bound the workflow to the exact offline-verified state root and corrected the state copy/preflight path.
- **Files modified:** `.github/workflows/phase6-acceptance.yml`, `tests/test_phase6_workflow.py`, `tools/verify_phase6_acceptance.py`
- **Verification:** Offline verifier and workflow tests passed before a fresh authorization packet was presented.
- **Committed in:** `c77b8bb`, `b7d08ef`

**2. [Rule 1 - Bug] Replaced the Search-authority stub with the real bounded nomination path**
- **Found during:** Task 2
- **Issue:** Run `30523180235` completed with `search_authority_validated` but produced zero candidates and no state change.
- **Fix:** Added actual round-robin Search acquisition, deterministic filtering, commit/license pinning, role-neutral contracts, operations persistence, and verified three-store CAS.
- **Files modified:** `src/skillscout/domain/acceptance.py`, `src/skillscout/application/acceptance.py`, `src/skillscout/bootstrap.py`, `src/skillscout/cli.py`, related tests
- **Verification:** Final run `30526079398` produced 31 candidates and a rebuilt canonical nomination fact.
- **Committed in:** `7fed160`

**3. [Rule 1 - Bug] Canonicalized nested self-digested model inputs**
- **Found during:** Task 2 persistence round-trip testing
- **Issue:** A `NominationSetV1` constructed from validated nested entries could pass Pydantic objects directly to JSON hashing and fail serialization.
- **Fix:** Canonicalized nested strict models and sequences before binding self-digests.
- **Files modified:** `src/skillscout/domain/acceptance.py`, `tests/test_operations_state.py`
- **Verification:** Owned-state export → rebuild → fresh export equality passed.
- **Committed in:** `7fed160`

**4. [Rule 1 - Bug] Made canonical locked manifests loadable through the production strict JSON boundary**
- **Found during:** Task 3 manifest re-admission
- **Issue:** JSON arrays could not satisfy tuple-typed benchmark fields under the required `strict=True` loader.
- **Fix:** Added deterministic list-to-tuple normalization before validation without relaxing field or digest checks.
- **Files modified:** `src/skillscout/domain/acceptance.py`, `tests/test_acceptance_domain.py`
- **Verification:** Strict canonical JSON round-trip regression and actual manifest re-admission passed.
- **Committed in:** `2980379`

**5. [Rule 1 - Bug] Decoupled historical evidence verification from the mutable current state head**
- **Found during:** Task 3 broader verification after the legitimate benchmark-lock CAS
- **Issue:** The historical Plan 06-06 verifier incorrectly required `origin/skillscout-state` still to equal the old evidence commit.
- **Fix:** Resolve and rebuild the exact immutable historical commit object while retaining exact expected-commit validation.
- **Files modified:** `tools/verify_phase6_acceptance.py`
- **Verification:** Historical valid/stale tests passed and the broader suite reached 181 passed.
- **Committed in:** `2980379`

---

**Total deviations:** 5 auto-fixed (5 Rule 1 bugs)
**Impact on plan:** All fixes were required for real Search execution, strict manifest loading, or immutable evidence verification; no semantic or publication scope was added.

## Authentication Gates

- Task 1 received explicit authorization for the exact source/workflow/query/state identities and one bounded nomination run; no credential value was read or displayed.
- After the source SHA changed to implement the missing real path, a fresh authorization was obtained for exact SHA `7fed160bc10c7ad85f027939b3f79884bb6e691f`.
- Task 3 received explicit human approval for the five exact repository identities, role distribution, reviewer `alexzhu0`, manifest lock, and one state-only CAS.

## Issues Encountered

- macOS `/tmp` is a symlink alias and is correctly rejected by anchored state paths. Independent rebuild destinations used canonical `/private/tmp` paths.
- macOS `date` does not support GNU `%6N`; the lock timestamp was generated with Python UTC microsecond precision.
- The repository does not configure or install mypy, so no package was installed merely to add an unowned type-check command.
- The broader suite intentionally excludes the separate future whole-repository acceptance-verifier RED; the final scoped result was `181 passed, 12 skipped, 1 deselected`.

## Known Stubs

None. Empty lists and optional `None` fields found by the scan are bounded runtime accumulators or explicitly optional digest inputs, not UI/data-source placeholders.

## User Setup Required

None. Protected workflow variables already supplied the authorized runtime credentials; values were never inspected or persisted.

## Next Phase Readiness

- Plan 06-08 may re-admit state commit `500b3de1b14d8c0d1e0a4d3a35bf027eb19db2eb`, root `sha256:a9131fdfec479202f1f626834c805bece17f933e802ecb9877827a9525f94d85`, and manifest `sha256:3d7f16e60c3336c5c73d174273a01740daa39ab1b506a437be753d94aa387185`.
- No live semantic, DeepSeek, publication, catalog, PR, Gate B4, cleanup, merge, approval, or default-branch authority was granted by this plan.
- Expected benchmark roles remain evaluator hypotheses and must not be copied into semantic requests.

## Self-Check: PASSED

- Summary and locked benchmark manifest exist at their canonical paths.
- All four task commits resolve as commit objects.
- The production strict loader re-admitted the five-entry manifest with the exact nomination, manifest, and attestation digests.
- Exact canonical state commit `500b3de1b14d8c0d1e0a4d3a35bf027eb19db2eb` resolves locally after the independent remote-state rebuild.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-07-30*
