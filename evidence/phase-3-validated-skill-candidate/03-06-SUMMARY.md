---
phase: 03-validated-skill-candidate
plan: "06"
subsystem: application
tags: [candidate-source, sqlite, canonical-json, authority, filesystem-safety, tdd]

requires:
  - phase: 03-05
    provides: Strict candidate descriptor and complete WorkflowSpec authority contracts
  - phase: 03-04
    provides: Gate B3 dependency equality preflight
  - phase: 02-safe-single-repository-extraction
    provides: Canonical Phase 2 workflow results and verified run-chain authority
provides:
  - Private bounded canonical descriptor admission before any Phase 3 effect
  - Read-only completed-Phase-2 query with existing full-chain reverification
  - Stable full-fingerprint descriptor derivation capped at three independent candidates
affects: [03-07, 03-08, 03-09, 03-10, 03-11, 03-12, phase3-ledger, candidate-pipeline]

tech-stack:
  added: []
  patterns:
    - Descriptor-first pre-run barrier with effective-UID, private-file, stable-identity, and cap-plus-one checks
    - Immutable SQLite query adapter reusing the canonical run-chain verifier
    - Exact canonical bytes and complete authority equality before structured source release

key-files:
  created:
    - src/skillscout/application/candidate_source.py
    - src/skillscout/adapters/phase2_state.py
    - tests/test_candidate_source.py
  modified:
    - src/skillscout/application/ports.py

key-decisions:
  - "Represent the verified chain anchor as the SHA-256 digest of the complete strict VerifiedRunChain projection, not as a workflow fingerprint or partial row identity."
  - "Expose only resolve and resolve_all read methods; resolve_all verifies one completed Phase 2 chain once so deterministic sibling derivation does not repeat or bypass authority checks."
  - "Treat an absent prior-lineage binding mapping as no binding and no search; only an explicit exact full-fingerprint mapping may attach the opaque digest."

patterns-established:
  - "Candidate descriptor files are rejected before the source query unless lstat/fstat ownership, mode, link count, type, identity, size, and stability all pass."
  - "Every filesystem, parsing, upstream-state, chain, selection, and authority failure collapses to the fixed candidate_source_unavailable surface."
  - "Phase 2 state is opened through immutable read-only SQLite and its established verify_run_chain implementation remains the success gate."

requirements-completed: [GEN-04, GEN-05]

coverage:
  - id: D1
    description: "Only one exact canonical WorkflowSpec from a completed, reverified Phase 2 run crosses into the resolved Phase 3 source contract."
    requirement: GEN-04
    verification:
      - kind: unit
        ref: "tests/test_candidate_source.py (49 query, hostile-file, canonical-byte, authority-mutation, derivation, and sibling-isolation cases)"
        status: pass
      - kind: integration
        ref: "Gate-B3-prefixed protected Phase 2/state/authority/lineage regression set: 403 passed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Candidate selection is stable by complete fingerprint bytes, capped at three, and preserves exact source and optional approved-binding authority."
    requirement: GEN-05
    verification:
      - kind: unit
        ref: "tests/test_candidate_source.py (stable permutation, fourth-candidate exclusion, exact binding mapping, and sibling failure isolation)"
        status: pass
      - kind: other
        ref: "Gate-B3-prefixed full pytest suite: 783 passed; ruff check .: clean"
        status: pass
    human_judgment: false

duration: 20 min
completed: 2026-07-23
status: complete
---

# Phase 03 Plan 06: Strict Phase 2 Candidate Source Bridge Summary

**Private canonical descriptors now resolve only to one complete, chain-verified Phase 2 WorkflowSpec, with deterministic three-candidate derivation and a single sanitized pre-run failure surface.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-23T09:59:52Z
- **Completed:** 2026-07-23T10:19:21Z
- **Tasks:** 2/2
- **Implementation/test files:** 4

## Accomplishments

- Added a narrow read-only Phase 2 source protocol and immutable SQLite adapter that reuses the unchanged canonical `verify_run_chain` implementation, validates all Phase 2 terminal outcomes and source facts, and exposes no mutation method.
- Added private single-link effective-UID descriptor admission with no-follow/nonblocking/close-on-exec flags, path-to-fd identity, complete pre/post metadata stability, stat and stream size enforcement, strict UTF-8/JSON/Pydantic parsing, and exact canonical-byte equality.
- Reconstructed the exact canonical `WorkflowSpec`, recomputed complete authority from its Phase 2 output and chain anchors, and released only a strict structured resolved source when every equality holds.
- Added deterministic full-fingerprint descriptor derivation, exact optional binding attachment, fourth-candidate exclusion, and isolated sibling resolution so one invalid source cannot suppress or contaminate another.
- Preserved the existing subject loaders, `PhaseTwoProcessor`, pipeline, and canonical state verifier byte-for-byte.

## Task Commits

Each TDD task was committed with RED before GREEN:

1. **Task 1 RED: Read-only Phase 2 candidate query contracts** - `036b6b2` (`test`)
2. **Task 1 GREEN: Completed Phase 2 candidate query adapter** - `935d007` (`feat`)
3. **Task 2 RED: Strict descriptor and source-authority boundary contracts** - `c3ae706` (`test`)
4. **Task 2 GREEN: Private canonical loader and stable sibling derivation** - `b4d2bcf` (`feat`)

## Files Created/Modified

- `src/skillscout/application/candidate_source.py` - Safe descriptor loader, exact source-authority comparison, resolved source model, and stable capped derivation.
- `src/skillscout/adapters/phase2_state.py` - Immutable read-only Phase 2 adapter with full-chain reverification and exact canonical workflow projections.
- `src/skillscout/application/ports.py` - Sanitized source-unavailable contract, strict source projection, and read-only query protocol.
- `tests/test_candidate_source.py` - Query immutability, hostile-file, bounded-read, strict parsing, authority mutation, deterministic derivation, and sibling-isolation coverage.

## Decisions Made

- The verified chain anchor is computed from the complete canonical `VerifiedRunChain` projection so selection binds the run identity, all stage results, and their terminal authority rather than only the extractor fingerprint.
- `resolve_all` is a read-only enumeration seam used only for derivation. It opens one immutable query connection, invokes the existing verifier once, validates every stored workflow strictly, rejects duplicate fingerprints, and returns frozen projections.
- Repository identity, pinned commit, and permissive license remain verified Phase 2 projection facts bound through the complete chain anchor; callers cannot override them through descriptor text.
- Descriptor absence never authorizes Phase 3 lookup or binding inference. An optional prior binding is attached only from one explicit exact full-fingerprint mapping.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Harness] Kept hostile fstat simulation local and tested only descriptor-controlled authority mutations**
- **Found during:** Task 2 GREEN
- **Issue:** The initial `os.fstat` monkeypatch recursively called itself, and fake-port cases attempted to alter repository projection facts that are not descriptor-controlled inputs.
- **Fix:** Captured the real `fstat` before patching so post-read mutation is measured correctly, and retained source-mutation cases at the descriptor-controlled extractor-output and complete-chain anchors while repository facts remain covered by the read-only adapter's verified-chain tests.
- **Files modified:** `tests/test_candidate_source.py`
- **Verification:** All 49 candidate-source tests and 403 protected regressions pass.
- **Committed in:** `b4d2bcf`

**2. [Rule 2 - Missing Critical Functionality] Added one-shot completed-run enumeration for deterministic derivation**
- **Found during:** Task 2 GREEN
- **Issue:** The Task 1 single-descriptor `resolve` seam could not derive a stable capped sibling set while satisfying the requirement to reverify the completed Phase 2 result exactly once.
- **Fix:** Added `resolve_all` to the same read-only protocol and adapter, factored both methods through one immutable verified query, and kept the public adapter mutation-free.
- **Files modified:** `src/skillscout/application/ports.py`, `src/skillscout/adapters/phase2_state.py`
- **Verification:** Stable order permutations, exact cap-three/fourth exclusion, protocol surface, database immutability, and the full 783-test suite pass.
- **Committed in:** `b4d2bcf`

---

**Total deviations:** 2 auto-fixed issues (1 Rule 1 test-harness correction, 1 Rule 2 critical read-only seam).
**Impact on plan:** Both changes strengthen the planned safety and determinism boundaries without adding dependencies, mutation authority, Phase 3 state, model calls, validators, artifacts, or remote effects.

## Issues Encountered

- The sandbox required approval to access the repository-local uv cache. Every dependency-backed command still began with the mandatory Gate B3 preflight and used the exact locked repository uv executable.

## Authentication Gates

None.

## Known Stubs

None.

## Verification

- Task 1 exact `phase2_query` command: **15 passed**.
- Task 2 exact candidate-source command: **49 passed**.
- Protected Phase 2 contracts, state integrity, pipeline, candidate authority, and lineage regressions: **403 passed**.
- Full Gate-B3-prefixed test suite: **783 passed**.
- Full Gate-B3-prefixed Ruff: **All checks passed**.
- Protected source diff: empty; the four captured source hashes match their pre-plan values, and `SQLiteStateStore.verify_run_chain` is unchanged.
- Stub scan: no goal-blocking stubs.
- Threat-surface scan: no unplanned endpoint, credential, network, database/schema mutation, authentication, model/tool, or remote-write surface. The new local descriptor read and immutable Phase 2 query are the plan-authored boundaries covered by T-03-12 through T-03-15.

## User Setup Required

None.

## Next Phase Readiness

- Plan 03-07 can consume `ResolvedCandidateSourceV1` knowing its exact WorkflowSpec, repository facts, Phase 2 output anchor, complete chain anchor, and authority digest have all been reverified before Phase 3 exists.
- Later sibling orchestration can use the stable capped descriptors independently; one source failure already collapses locally without Phase 3 lookup, state, call, validator, or artifact effects.
- Prior-lineage resolution remains explicitly opt-in by exact approved binding digest and does not search or infer from absence.

## Self-Check: PASSED

- Found all four declared implementation/test files and this summary on disk.
- Confirmed all four TDD commits are commit objects in repository history.
- Reconfirmed the exact task suites, protected regression suite, full test suite, full Ruff gate, protected source hashes, stub scan, and threat-surface scan recorded above.

---
*Phase: 03-validated-skill-candidate*
*Completed: 2026-07-23*
