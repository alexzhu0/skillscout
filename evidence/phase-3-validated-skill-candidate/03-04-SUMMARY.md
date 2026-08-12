---
phase: 03-validated-skill-candidate
plan: "04"
subsystem: supply-chain
tags: [supply-chain, gate-b3, lock-authority, no-follow, tdd]

requires:
  - phase: 03-03
    provides: Human Gate B3 approval for one exact uv.lock byte sequence
provides:
  - Committed literal Gate B3-approved SHA-256 authority
  - Dependency-free fail-closed preflight over retained no-follow descriptors
  - Adversarial proof that every failed admission blocks the downstream consumer
affects: [03-05, phase3-validation, dependency-backed-commands, skills-ref]

tech-stack:
  added: []
  patterns:
    - Dependency-backed commands begin only after fresh equality proof against committed human authority
    - Security-sensitive local authorities are hashed from retained no-follow descriptors after bounded stable-identity admission

key-files:
  created:
    - config/supply-chain/phase3-gate-b3.lock.sha256
    - tools/verify_phase3_gate_b3.sh
  modified:
    - tests/test_phase3_lock_preflight.py

key-decisions:
  - "Use the fixed operating-system /usr/bin/perl runtime and core Fcntl, Time::HiRes, and Digest::SHA primitives inside the sh gate so O_NOFOLLOW, FD_CLOEXEC, retained-descriptor hashing, and high-resolution identity stability are exact without project or third-party imports."
  - "Admit exactly two fixed repository-relative authorities with no caller-supplied registry or consumer arguments; sanitize the helper environment to PATH=/usr/bin:/bin and LC_ALL=C."
  - "Reject missing secure primitives, malformed authority, non-private writable modes, hard links, identity swaps, read-time mutation, and digest mismatch before downstream execution."

patterns-established:
  - "Gate B3 preflight: fixed authority paths, bounded descriptor reads, exact digest grammar, stable metadata, then consumer."
  - "Supply-chain tests use a stopped-process descriptor seam to deterministically exercise path/fd and post-read races without weakening success conditions."

requirements-completed: [VAL-01]

coverage:
  - id: D1
    description: "Exact Gate B3 lock authority and dependency-free fail-closed preflight for every later Phase 3 package-backed command."
    requirement: VAL-01
    verification:
      - kind: unit
        ref: "tests/test_phase3_lock_preflight.py (29 adversarial and success cases)"
        status: pass
      - kind: other
        ref: "sh tools/verify_phase3_gate_b3.sh && repository-local uv run --locked pytest -q tests/test_phase3_lock_preflight.py"
        status: pass
      - kind: other
        ref: "sh tools/verify_phase3_gate_b3.sh && repository-local uv lock --check"
        status: pass
    human_judgment: false

duration: 9 min
completed: 2026-07-23
status: complete
---

# Phase 03 Plan 04: Gate B3 Lock Equality Control Summary

**The exact human-approved `uv.lock` SHA-256 now gates all later Phase 3 dependency use through bounded no-follow descriptor reads, retained-stream hashing, stable identity checks, and 29 adversarial tests.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-23T09:29:21Z
- **Completed:** 2026-07-23T09:37:50Z
- **Tasks:** 1/1
- **Files modified:** 3 implementation/test files

## Accomplishments

- Committed only the approved lowercase digest `b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004` plus its required newline.
- Added an executable `sh` preflight that resolves its repository root independently of caller cwd, clears inherited helper configuration, rejects arguments, and invokes neither project code nor the repository-local package runner.
- Ported the repository's local authority discipline: regular non-link single-owner admission, safe permissions, `O_NOFOLLOW`, `FD_CLOEXEC`, path/fd identity equality, cap-plus-one retained-descriptor reads, high-resolution pre/post size/mtime/ctime checks, and SHA-256 over the admitted stream.
- Proved failure-before-consumer behavior for byte mutation, missing/malformed/linked/non-regular/oversized authorities, unsafe modes, hard links, forged hash utilities, identity swaps, and post-read mutation.

## Task Commits

TDD was committed with the required RED then GREEN gates:

1. **RED: Add failing Gate B3 preflight tests** - `1b7c4a1` (`test`)
2. **GREEN: Enforce approved Gate B3 lock identity** - `fd5d7ec` (`feat`)

## Files Created/Modified

- `config/supply-chain/phase3-gate-b3.lock.sha256` - Literal one-line human-approved lock authority.
- `tools/verify_phase3_gate_b3.sh` - Dependency-free, fail-closed retained-descriptor equality gate.
- `tests/test_phase3_lock_preflight.py` - 29 success, mutation, authority-admission, race, and sentinel cases.

## Verification

- PASS — TDD RED: all 29 tests failed before the digest and preflight existed.
- PASS — exact planned task command: `29 passed`.
- PASS — exact planned lock check: `Resolved 29 packages`; `uv.lock` remained byte-identical.
- PASS — targeted Ruff check: `All checks passed!`.
- PASS — `sh -n tools/verify_phase3_gate_b3.sh`.
- PASS — fresh preflight and independent `shasum -a 256 uv.lock` both confirmed the approved digest.
- PASS — digest file is exactly 65 bytes and the preflight is committed executable.

## Decisions Made

- The secure descriptor requirements are implemented through the operating-system Perl runtime and core modules rather than approximated with pathname-reopening shell pipelines. Platforms missing those primitives fail closed before dependency execution.
- The script accepts no authority or consumer arguments. Later commands compose it with `&&`, preserving one fixed local authority registry and making success the only route to the downstream executable.
- A narrowly closed test seam may only stop the process at the two descriptor race boundaries; it cannot change inputs, results, authority paths, or turn a failure into success.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Harness] Kept the forged-PATH case runnable without trusting PATH**
- **Found during:** Task 1 GREEN verification
- **Issue:** The forged-success test replaced `PATH` with only fake hash utilities, so the test harness could not locate its own `sh` executable and failed before exercising the preflight.
- **Fix:** Invoked the harness shell by fixed `/bin/sh`; the preflight still clears its helper environment and rejected the forged hash result.
- **Files modified:** `tests/test_phase3_lock_preflight.py`
- **Verification:** The exact planned command passed all 29 cases.
- **Committed in:** `fd5d7ec`

---

**Total deviations:** 1 auto-fixed Rule 1 test-harness bug.
**Impact on plan:** No scope or authority expansion; the correction makes the forged-success case test the intended boundary.

## Issues Encountered

- The first RED invocation could not access uv's default cache under the filesystem sandbox. The RED gate was rerun offline with the existing repository-local cache after the same approved hash check; the exact plan command was later run successfully with its original environment after the preflight.

## Authentication Gates

None.

## Known Stubs

None.

## User Setup Required

None - no external service, credential, or source-repository execution is required.

## Next Phase Readiness

- Plan 03-05 and every later Phase 3 dependency-backed command can uniformly start with `sh tools/verify_phase3_gate_b3.sh && ...`.
- Any future `uv.lock` byte change invalidates the committed B3 authority and must return to a new human review decision; the preflight cannot recompute or substitute approval.

## Self-Check: PASSED

- Found all three declared task files and both TDD commits.
- Reconfirmed the committed digest bytes, current `uv.lock` SHA-256, executable mode, targeted tests, lock check, syntax check, and lint result.
- Stub scan was empty.
- The only new file-read trust boundary is the plan-authored Gate B3 control and is covered by threats T-03-SC, T-03-07, and T-03-08; no additional network, auth, schema, or remote-write surface was introduced.

---
*Phase: 03-validated-skill-candidate*
*Completed: 2026-07-23*
