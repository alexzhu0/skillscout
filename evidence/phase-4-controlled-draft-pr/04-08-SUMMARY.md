---
phase: 04-controlled-draft-pr
plan: 08
subsystem: supply-chain-approval
tags: [github-actions, supply-chain, human-gate, immutable-sha]
requires:
  - phase: 04-controlled-draft-pr
    provides: immutable, non-authorizing action evidence for Gate A4
provides:
  - human Gate A4 approval bound to the exact audited action identities
affects: [04-09, publish-candidate-workflow]
tech-stack:
  added: []
  patterns: [blocking-human-exact-sha-approval, audit-digest-binding]
key-files:
  created:
    - .planning/phases/04-controlled-draft-pr/04-08-SUMMARY.md
  modified: []
key-decisions:
  - "Human Gate A4 approved only actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 and actions/create-github-app-token@67018539274d69449ef7c8cde82c3ff073ffe3b5, bound to audit digest d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622."
patterns-established:
  - "Workflow action authority requires an explicit human approval of the exact audited commit set and audit-file digest."
requirements-completed: [PUB-04, SEC-02]
coverage:
  - id: D1
    description: Human Gate A4 approval for the exact audited GitHub Action commits.
    requirement: PUB-04
    verification:
      - kind: manual_procedural
        ref: "Human response: approve-exact-shas audit_digest=d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622 actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 actions/create-github-app-token@67018539274d69449ef7c8cde82c3ff073ffe3b5"
        status: pass
      - kind: unit
        ref: ".tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py"
        status: pass
    human_judgment: true
    rationale: "The non-auto-approvable Gate A4 decision must come from a human reviewer."
duration: 3min
completed: 2026-07-24
status: complete
---

# Phase 04 Plan 08: Gate A4 Action Identity Approval Summary

**Human approval binds the audited checkout and GitHub App token actions to their exact immutable commits and audit digest.**

## Gate A4 Decision Record

- **decision:** `approve-exact-shas`
- **approved_actions:**
  - **repository_id:** `197814629`; **repository_full_name:** `actions/checkout`; **commit_sha:** `11bd71901bbe5b1630ceea73d27597364c9af683`; **tree_sha:** `d0af3a2e48f72b25f2c8a4ce85f9a86058d7eaa7`; **runtime:** `node20`; **required permissions:** `contents:read`; **requested permissions:** none; **nested actions:** none.
  - **repository_id:** `595047935`; **repository_full_name:** `actions/create-github-app-token`; **commit_sha:** `67018539274d69449ef7c8cde82c3ff073ffe3b5`; **tree_sha:** `eb5e5fc0e85f5c1c4d03aa0c0c51e6fb3e8e6ff8`; **runtime:** `node20`; **required permissions:** `contents:read`; **requested permissions:** `contents:write`, `pull-requests:write`; **nested actions:** none.
- **audit_digest:** `d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622`
- **reviewer:** human requester in this conversation
- **decided_at:** `2026-07-24T07:12:30Z`
- **human-authored response:** `approve-exact-shas audit_digest=d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622 actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 actions/create-github-app-token@67018539274d69449ef7c8cde82c3ff073ffe3b5`

The approval applies only while the exact audit bytes, audit digest, repositories, numeric IDs, candidate commits, tree SHAs, content-evidence digests, Node 20 runtimes, input/output behaviour, permissions, empty nested-action sets, empty executable-hook sets, and unresolved-claim sets remain unchanged. Release tags are not authority. Any change invalidates this decision and requires a fresh Gate A4 decision before a workflow can consume an action identity.

## Performance

- **Duration:** 3 min
- **Completed:** 2026-07-24T07:12:30Z
- **Tasks:** 1/1
- **Files modified:** 1

## Accomplishments

- Verified the exact approval grammar, 64-hex audit digest, and both 40-hex action commit SHAs against the immutable audit evidence.
- Ran the prescribed local, locked audit verifier; it reported `phase4 action audit valid`.
- Recorded the sole human Gate A4 decision without downloading, installing, or executing either action.

## Task Commits

1. **Task 1: Approve or reject exact action identity** — recorded in the commit below.

## Files Created/Modified

- `.planning/phases/04-controlled-draft-pr/04-08-SUMMARY.md` — human Gate A4 decision bound to the fixed audit identity.

## Decisions Made

- Human Gate A4 approved the two exact audited action commits and no mutable tag or substituted identity.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The prescribed local verifier required read access to the existing locked uv cache outside the workspace; it was rerun with that filesystem permission. No network activity, dependency installation, or action code execution occurred.

## User Setup Required

None.

## Next Phase Readiness

Plan 09 may consume only the approved immutable action identities above while the audit digest and all bound evidence remain unchanged. Any mismatch re-blocks publication at Gate A4.

## Self-Check: PASSED

- Verified this summary exists and records the exact human response, audit digest, repository identities, and both full commit SHAs.
- Verified the local offline audit command returned `phase4 action audit valid`.
- Verified the task commit for this summary exists and contains only this decision artifact.
