---
phase: 03-validated-skill-candidate
plan: 13
subsystem: cli
tags: [argparse, phase3, completed-reuse, local-artifacts, security, tdd]

requires:
  - phase: 02-safe-single-repository-extraction
    provides: Descriptor-anchored read-only Phase 2 candidate source
  - phase: 03-validated-skill-candidate
    provides: Complete Phase 3 authority, runner, durable resume, exact projector, and anchored materializer
provides:
  - Strict local-only `skillscout build-candidate` argparse command
  - Completed-first exact projection with no mutable state or output construction
  - Anchored immutable local evidence and documentation-only Skill materialization
  - Public 12-branch, checkpoint-resume, path, credential, capability, and zero-write reuse evidence
affects: [phase-3-verification, draft-pr-publishing, cli-security, candidate-operations]

tech-stack:
  added: []
  patterns:
    - Resolve and reverify Phase 2 source before constructing any Phase 3 path
    - Project exact completed evidence before a clean-miss-only mutable factory
    - Emit only canonical bounded relative evidence locators and digests

key-files:
  created:
    - tests/test_cli_validate_skill.py
  modified:
    - src/skillscout/cli.py
    - tests/test_cli_security.py

key-decisions:
  - "Keep argparse as the sole CLI framework and expose exactly candidate, Phase 2 state, Phase 3 state, output, and the closed fail-after vocabulary."
  - "Treat a non-empty output as admissible only for completed projection; after a verified clean miss, mutable execution requires an absent or empty private output directory."
  - "Return completed stored projections directly and leave even an alternate caller-selected output path absent."
  - "Use only the existing frozen package materializer plus descriptor-anchored canonical evidence writes for new or resumed results."

patterns-established:
  - "Public completed reuse: source reverify, O_RDONLY retained-lock projector, private-memory SQLite, bounded stdout projection, return."
  - "Public mutable path: verified clean miss, empty-output admission, mutable ledger, semantic ports, anchored local projection."

requirements-completed:
  - QUAL-01
  - QUAL-02
  - GEN-01
  - GEN-02
  - GEN-03
  - GEN-04
  - GEN-05
  - VAL-01
  - VAL-02
  - VAL-03
  - REV-01
  - REV-02
  - REV-03

coverage:
  - id: D1
    description: The additive build-candidate command exposes only the approved strict local argparse contract and resolves source before Phase 3 effects.
    requirement: QUAL-01
    verification:
      - kind: integration
        ref: "tests/test_cli_validate_skill.py#test_build_candidate_parser_exposes_only_the_closed_local_contract"
        status: pass
      - kind: integration
        ref: "tests/test_cli_validate_skill.py#test_candidate_source_failure_precedes_phase3_state_and_output"
        status: pass
    human_judgment: false
  - id: D2
    description: All 12 terminal outcomes emit bounded branch-appropriate evidence and completed invocations preserve exact recursive bytes and full lstat metadata.
    requirement: REV-03
    verification:
      - kind: integration
        ref: "tests/test_cli_validate_skill.py#test_build_candidate_all_terminal_branches_and_completed_reuse_are_exact"
        status: pass
    human_judgment: false
  - id: D3
    description: Qualifier, generator, validator, and reviewer failure injection resumes from the next verified durable checkpoint.
    requirement: VAL-03
    verification:
      - kind: integration
        ref: "tests/test_cli_validate_skill.py#test_build_candidate_failure_injection_resumes_from_verified_checkpoint"
        status: pass
    human_judgment: false
  - id: D4
    description: Completed CLI reuse permits no writable filesystem operation, mutable state, artifact writer, or file-backed SQLite connection.
    requirement: GEN-05
    verification:
      - kind: integration
        ref: "tests/test_cli_security.py#test_completed_candidate_cli_uses_only_read_opens_and_private_memory_sqlite"
        status: pass
    human_judgment: false
  - id: D5
    description: Unsafe namespaces, prohibited capabilities, Click imports, credential disclosure, and non-empty mutable outputs fail closed.
    requirement: GEN-02
    verification:
      - kind: integration
        ref: "tests/test_cli_security.py#test_build_candidate_rejects_unsafe_output_before_state_or_semantic_calls"
        status: pass
      - kind: unit
        ref: "tests/test_cli_security.py#test_skillscout_source_uses_argparse_and_never_imports_click"
        status: pass
      - kind: integration
        ref: "tests/test_cli_security.py#test_build_candidate_environment_secret_is_absent_from_every_surface"
        status: pass
    human_judgment: false

duration: 16min
completed: 2026-07-23
status: complete
---

# Phase 03 Plan 13: Safe Local Candidate CLI Summary

**A strict argparse command now drives verified Phase 2 input through completed-first Phase 3 reuse or anchored local materialization without publishing, candidate execution, credential exposure, or completed-state mutation.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-07-23T13:21:22Z
- **Completed:** 2026-07-23T13:37:30Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `skillscout build-candidate` with only the required descriptor, Phase 2 state, separate Phase 3 state, local output, and closed stage-interruption inputs.
- Wired source-before-state resolution, complete authority construction, read-only completed projection, clean-miss-only mutable resume, official-plus-local validation, independent generation/review, and anchored local evidence.
- Proved every terminal branch and resume boundary publicly, including exact completed DB/WAL/SHM/lock/artifact/output tree preservation and an alternate output path that remains absent.
- Closed CLI namespace, capability, Click, secret, and mutation channels with full filesystem snapshots and low-level open/SQLite/mutation sentinels.

## Task Commits

Each TDD boundary was committed atomically:

1. **Task 1: Add the strict local build-candidate command**
   - `4b29d32` — initial RED parser and pre-run source barrier
   - `12e2e35` — expanded RED 12-branch reuse and checkpoint-resume matrix
   - `0cc9ad9` — GREEN safe local command and anchored evidence projection
2. **Task 2: Close CLI capability, path, and credential leaks**
   - `44b69ce` — RED adversarial path, capability, secret, and low-level reuse gates
   - `7bd9e0e` — GREEN namespace admission and exact zero-write security boundary

## Files Created/Modified

- `src/skillscout/cli.py` — Strict command parser, production Phase 3 composition, local validator, anchored evidence projector, closed public summary, path admission, and durable failure-injection seam.
- `tests/test_cli_validate_skill.py` — Public parser, pre-run barrier, all 12 outcomes, exact completed reuse, alternate-output preservation, and four checkpoint resumes.
- `tests/test_cli_security.py` — No-Click AST gate, capability/help inspection, unsafe namespace rejection, credential scan, and low-level completed-reuse mutation sentinels.

## Decisions Made

- Existing completed output is never rewritten: the exact stored terminal/artifact projections determine stdout, and the supplied output argument is ignored for the completed hit.
- A verified clean miss may enter mutable execution only when output is absent or an empty private directory; this prevents state/output containment and unsafe overwrite ambiguity.
- Relative evidence names and canonical SHA-256 digests are the only public locators; absolute operator paths, raw source, prompts, responses, and exceptions never enter stdout.
- Real Generator and Reviewer construction remains lazy and consumes `OPENAI_API_KEY` only through the existing SDK adapters; tests replace both transports and require no real credential.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first low-level `os.open` sentinel replaced the function identity checked by `os.supports_dir_fd`, causing an instrumentation-only false failure before projection. The test now registers each wrapper in a copied supported-function set while retaining the zero-write assertions.

## Known Stubs

None.

## Threat Model Verification

- **T-03-39:** Descriptor, Phase 2 state, Phase 3 state, and output aliases/links are rejected; mutable execution additionally rejects state-under-output and non-empty output.
- **T-03-40:** Environment credential canaries are absent from stdout, stderr, state, package, reports, attestations, and all local evidence.
- **T-03-41:** Parser/help and source AST scans expose no publish, PR, merge, approval, shell, install, candidate execution, arbitrary tool, Click, renderer, eligibility, or separate fingerprint route.
- **T-03-42:** Completed reuse constructs no normal state or output writer, uses only read opens and `:memory:` SQLite, preserves exact recursive bytes/full lstat metadata, and leaves alternate output absent; the mutable resume control still persists and materializes.

No unmodeled network endpoint, publishing authority, candidate-code execution path, dependency change, schema change, or credential surface was introduced.

## TDD Gate Compliance

- Task 1 has RED commits `4b29d32` and `12e2e35` before GREEN commit `0cc9ad9`.
- Task 2 has RED commit `44b69ce` before GREEN commit `7bd9e0e`.

## Self-Check: PASSED

- All three created/modified implementation and test files exist.
- All five TDD task commits are present in order.
- Plan CLI suites: 60 passed.
- Full repository suite: 1,116 passed.
- Full repository Ruff checks pass.
- `build-candidate --help` exposes only the exact approved options.
- Dependency Gate B3 passed before every dependency-backed verification command.

## User Setup Required

Real generation and review require `OPENAI_API_KEY` to be injected by the runtime with minimum project access. Do not place it in files, command arguments, logs, state, prompts, or output. Automated tests use injected transports and require no real key.

## Next Phase Readiness

- Phase 3 now has one auditable local command from verified Phase 2 descriptor through exact terminal evidence.
- Plan 03-14 can run end-to-end verification over the public command and the full candidate pipeline.
- No blockers.

---
*Phase: 03-validated-skill-candidate*
*Completed: 2026-07-23*
