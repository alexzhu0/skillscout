---
phase: 01-auditable-dry-run-spine
plan: "12"
subsystem: local-state
tags: [sqlite, atomic-replace, fsync, file-permissions, namespace-integrity]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: descriptor-anchored SQLite snapshots, manifests, and locked offline acceptance
provides:
  - Truthful durable snapshot outcomes after the target directory fsync commit point
  - Disjoint state and manifest namespaces rejected before filesystem mutation
  - Shared private single-link effective-owner admission for state, manifest, and lock files
affects: [state-integrity, pipeline-resume, audit-evidence, phase-01-gap-closure]

tech-stack:
  added: []
  patterns:
    - authoritative replacement commit point before best-effort backup retirement
    - one stat/fstat private-file predicate across every local evidence reader

key-files:
  created: []
  modified:
    - src/skillscout/adapters/localfs.py
    - src/skillscout/adapters/state.py
    - tests/test_state_integrity.py
    - tests/test_cli_security.py
    - tests/test_pipeline_resume.py

key-decisions:
  - "Treat successful target file fsync, rename, and containing-directory fsync as the authoritative snapshot commit point; later backup retirement is non-throwing housekeeping."
  - "Require regular type, one link, effective-user ownership, and no group/other permission bits at both stat and fstat before local evidence bytes are read."
  - "Reject state and derived manifest namespace equality before parent creation, lock acquisition, or snapshot creation."

patterns-established:
  - "Post-commit cleanup: backup unlink and cleanup sync failures cannot turn a durable success into a rollback-shaped result."
  - "Private evidence admission: state, manifest, and retained lock files share one fail-closed metadata policy."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Snapshot mutation results agree with the authoritative row set observed after reopen across pre- and post-commit fault seams."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_post_commit_backup_cleanup_failure_returns_success_and_reopen_observes_mutation"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_pre_commit_snapshot_failure_restores_prior_authority"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_stale_backup_never_supersedes_valid_state_target"
        status: pass
    human_judgment: false
  - id: D2
    description: "Only disjoint private single-link current-owner state and manifest files can become audit authority."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_state_integrity.py#test_state_manifest_namespace_collision_is_rejected_before_creation"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_existing_state_requires_private_permissions_before_deserialize"
        status: pass
      - kind: integration
        ref: "tests/test_state_integrity.py#test_existing_manifest_requires_private_single_owner_file_before_decode"
        status: pass
    human_judgment: false
  - id: D3
    description: "Colliding CLI state names fail without artifacts or disclosure of the operator-selected canary."
    requirement: OPS-01
    verification:
      - kind: e2e
        ref: "tests/test_cli_security.py#test_cli_rejects_colliding_state_namespace_without_disclosure"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 12: Local Persistence Authority Summary

**Commit-point-aware atomic replacement now returns the same outcome that reopen observes, while private-file and namespace admission prevent ambiguous local evidence from becoming audit authority.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-07-19T09:42:12Z
- **Completed:** 2026-07-19T09:55:48Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Defined target file fsync, rename, and containing-directory fsync as the authoritative replacement commit point; backup unlink or cleanup sync failures afterward return success and preserve the promoted live candidate.
- Rejected equal state/manifest namespaces before any filesystem creation and applied one effective-owner, single-link, private regular-file predicate to state, manifest, and retained-lock stat/fstat metadata.
- Added deterministic fault, stale-backup, chmod, hard-link, simulated-owner, private transient-file, and packaged CLI disclosure regressions.

## Task Commits

Each TDD task was committed with a failing test gate followed by its implementation:

1. **Task 01-12-01: Make snapshot replacement outcomes agree with reopened authority** - `33b1d1f` (test), `c2d4195` (feat)
2. **Task 01-12-02: Reject namespace collisions and non-private existing evidence** - `2ac1e2c` (test), `3735994` (feat)
3. **Rule-1 test harness compatibility: Prepare frozen migration copies as private runtime state** - `065cb48` (test)

## Files Created/Modified

- `src/skillscout/adapters/localfs.py` - Shared private-file admission and non-throwing post-commit backup retirement seams.
- `src/skillscout/adapters/state.py` - Early namespace equality rejection and shared lock metadata validation.
- `tests/test_state_integrity.py` - Commit-point fault matrix plus namespace, mode, link, owner, and private-file regressions.
- `tests/test_cli_security.py` - Sanitized packaged CLI namespace-collision regression and private legacy copy preparation.
- `tests/test_pipeline_resume.py` - Private mode preparation for temporary copies of the frozen migration fixture.

## Fault Matrix

| Fault seam | Returned outcome | Live/reopened authority |
|---|---|---|
| `before_state_file_fsync` | `state_operation_failed` | Prior snapshot restored; reopen has zero requested rows |
| `before_state_rename` | `state_operation_failed` | Prior snapshot restored; reopen has zero requested rows |
| `before_state_directory_fsync` | `state_operation_failed` | Prior snapshot restored; reopen has zero requested rows |
| `after_backup_unlink` | success | Promoted and reopened state each contain the requested row exactly once |
| `before_backup_cleanup_directory_fsync` | success | Promoted and reopened state each contain the requested row exactly once |
| stale valid backup beside valid target | target remains authoritative | Stale row is never selected; next write/reopen contains only the new authoritative row |

## Permission Matrix

| Evidence condition | Result |
|---|---|
| State mode `0640` or `0602` | Rejected before SQLite connection/deserialization |
| State hard link (`st_nlink = 2`) | Rejected as schema-incompatible local state |
| Manifest mode `0640` | Rejected before JSON decoding |
| Manifest hard link (`st_nlink = 2`) | Rejected before JSON decoding |
| Simulated foreign owner | Shared predicate fails closed |
| Missing effective-owner primitive | Shared predicate fails closed |
| Newly written state, lock, backup temporary, state temporary, and manifests | Effective-owner, one link, no group/other permission bits |

## Collision Evidence

- A state leaf ending in `.manifests` is rejected with the fixed `state_integrity_error` diagnostic before the parent anchor, lock, state file, or manifest directory is created.
- The packaged CLI regression uses a credential-shaped canary and proves stdout/stderr contain only the fixed allowlisted diagnostic while the selected temporary parent remains empty.

## Decisions Made

- Replacement durability, not backup retirement, determines the mutation outcome. Backup cleanup cannot report rollback after the replacement directory has synced.
- State, manifest, and lock metadata share one policy to avoid weaker parallel admission logic.
- Git-stored database fixtures remain byte-identical; tests explicitly make only their temporary operational copies private before opening them as state.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Prepared frozen migration test copies as private runtime state**
- **Found during:** Repository-wide verification after Task 01-12-02
- **Issue:** `shutil.copy2` preserved the repository fixture's ordinary `0644` checkout mode, so seven migration tests presented intentionally non-private files to the newly correct production admission boundary.
- **Fix:** Set only each temporary copied database to `0600` in the migration test helper; production admission and the source fixture were unchanged.
- **Files modified:** `tests/test_pipeline_resume.py`
- **Verification:** The seven focused migration tests and the complete locked offline suite pass.
- **Committed in:** `065cb48`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug).  
**Impact on plan:** Test setup now models valid private operational state without weakening the security boundary or changing protected fixture bytes.

## Issues Encountered

None - the one repository-wide test-harness mismatch was resolved under the deviation rule above.

## User Setup Required

None - no external service configuration required.

## Verification Evidence

- Exact Task 01 verification: `6 passed`, Ruff passed.
- Exact Task 02 verification: `11 passed`; frozen database hash matched.
- Complete state and CLI suites: `116 passed`.
- Previously failing migration subset after the helper fix: `7 passed`.
- Full locked offline suite: `215 passed`.
- Full Ruff scan across `src` and `tests`: all checks passed.
- `uv.lock` SHA-256: `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256: `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`.

## Known Stubs

None.

## Self-Check: PASSED

- Modified production and test files exist: `src/skillscout/adapters/localfs.py`, `src/skillscout/adapters/state.py`, `tests/test_state_integrity.py`, `tests/test_cli_security.py`, and `tests/test_pipeline_resume.py`.
- Task and deviation commits exist: `33b1d1f`, `c2d4195`, `2ac1e2c`, `3735994`, and `065cb48`.
- All task acceptance checks, protected hashes, the full locked offline suite, and Ruff passed after the final code commit.
- `.planning/config.json` remains byte-identical to its pre-execution user/orchestrator state and is not staged.

## Next Phase Readiness

- CR-01, WR-03, and WR-04 are closed with deterministic regression evidence.
- Plan 01-13 can build immutable resume-event authority on a truthful, private local snapshot boundary.
- No blockers remain from this plan.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*
