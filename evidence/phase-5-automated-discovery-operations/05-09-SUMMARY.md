---
phase: 05-automated-discovery-operations
plan: "09"
subsystem: operations
tags: [github-actions, concurrency, protected-environment, github-app, gate-b4]

requires:
  - phase: 05-08
    provides: separated discovery and protected publication entrypoints with exact-state re-admission
  - phase: 04-controlled-draft-pr
    provides: Draft-only publication boundary and original Gate B4 method
provides:
  - serialized daily/manual production discovery workflow with two credential zones
  - hosted non-cancelling concurrency evidence for the shared production group
  - fresh Gate B4 evidence and human approval for the exact Phase 5 protected workflow surface
  - bounded test-only canary with causal denial and separate cleanup evidence
affects: [05-10, phase-6-adversarial-acceptance, operations, publication]

tech-stack:
  added: []
  patterns:
    - exact-workflow-byte approval records separate from immutable hosted evidence
    - deterministic preflight before late repository-scoped App token minting
    - sanitized causal probes with human-only cleanup

key-files:
  created:
    - .github/workflows/gate-b4-canary.yml
    - tools/gate_b4_canary.py
    - tests/test_gate_b4_canary.py
    - tests/test_gate_b4_canary_workflow.py
    - .planning/phases/05-automated-discovery-operations/05-HOSTED-GATE-B4-EVIDENCE.json
    - .planning/phases/05-automated-discovery-operations/05-HOSTED-GATE-B4-APPROVAL.json
    - .planning/phases/05-automated-discovery-operations/05-09-SUMMARY.md
  modified:
    - .github/workflows/discover.yml
    - .github/workflows/publish-candidate.yml
    - tests/test_discovery_workflow.py
    - tests/test_discovery_security.py

key-decisions:
  - "Concurrency evidence proves hosted serialization only and never substitutes for Gate B4."
  - "Hosted evidence remains immutable at its pre-approval status; a separate strict approval record binds its exact SHA-256."
  - "Catalog credentials are minted only after protected exact-state reread and local re-admission."
  - "The private denial target is authorized by reviewed numeric identity digest while its full name is injected as a protected secret."
  - "Canary cleanup remains a separate human/admin operation and is never exposed to the App token."

patterns-established:
  - "Exact hosted gate: immutable evidence bytes plus an independently hashed human approval record."
  - "Protected canary: fixed inputs, closed request surface, bounded sanitized evidence, and no cleanup route."

requirements-completed: [DISC-01, OPS-02, OPS-03]

coverage:
  - id: D1
    description: "One pinned workflow runs the same bounded discovery path on the daily schedule and manual dispatch."
    requirement: "DISC-01"
    verification:
      - kind: integration
        ref: "tests/test_discovery_workflow.py and tests/test_discovery_security.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "The shared non-cancelling production concurrency group serializes overlapping hosted runs."
    requirement: "OPS-02"
    verification:
      - kind: human
        ref: "05-HOSTED-GATE-B4-APPROVAL.json; runs 30324567231 and 30324568742"
        status: pass
    human_judgment: true
  - id: D3
    description: "Discovery and protected publication remain separate authority zones with re-admission before token minting."
    requirement: "OPS-03"
    verification:
      - kind: integration
        ref: "tests/test_discovery_workflow.py, tests/test_discovery_security.py, and tests/test_gate_b4_canary_workflow.py"
        status: pass
      - kind: human
        ref: "05-HOSTED-GATE-B4-APPROVAL.json; canary run 30327184915"
        status: pass
    human_judgment: true

duration: checkpoint-spanning
completed: 2026-07-28
status: complete
---

# Phase 05 Plan 09: Serialized Discovery and Fresh Gate B4 Summary

**Pinned daily/manual discovery now runs through two isolated credential zones, with hosted serialization and fresh exact-byte Gate B4 approval backed by causal denial, secret-scan, and separate cleanup evidence.**

## Performance

- **Duration:** Checkpoint-spanning implementation and hosted verification
- **Completed:** 2026-07-28
- **Tasks:** 2
- **Hosted runs reviewed:** 3
- **Requirements:** 3

## Accomplishments

- Shipped the pinned `schedule`/`workflow_dispatch` production workflow with concurrency group `skillscout-production`, `cancel-in-progress: false`, and no catalog authority in the discovery job.
- Kept protected publication behind exact state reread, three-store verification, canonical local re-admission, and late repository-scoped App token minting.
- Proved hosted serialization with runs `30324567231` and `30324568742`: the second stayed pending, was not cancelled, and began after the first completed.
- Proved fresh Gate B4 with canary run `30327184915`: one App-authored Draft requested exactly the configured reviewer, an otherwise-mergeable PR could not merge, protected mutations were denied, the default SHA stayed unchanged, logs/state scans were clean, and human/admin cleanup removed only the canary artifacts.
- Bound the immutable hosted evidence SHA-256 `1ee162ea47cf86b7faec68bfba37b7a9b2af3b25472066312b43c4a5e4414cdd` to human approval record SHA-256 `e1c6687d4c85c4881a433d03da8d66168915c8e316e4817e1415835b52e3ba72`.

## Hosted Approval Boundary

The approved exact workflow SHA-256 values are:

| Surface | SHA-256 |
|---|---|
| `.github/workflows/discover.yml` | `8157cb686b9bf18bfa800811b1fe1529ed9a15ec371fe36ec1708233052b7cfd` |
| `.github/workflows/publish-candidate.yml` | `96ce9f39db49ce647a88b83ec4db3cb0135e5cf51c1eb2f11961cfd243b23cf0` |
| `.github/workflows/gate-b4-canary.yml` | `9c59cd9822eecec913f82d24c7880a443ba9416795b8996c6201f33c4df5805d` |

The exact human response is preserved in `05-HOSTED-GATE-B4-APPROVAL.json`. The concurrency runs establish hosted scheduling behavior only. Gate B4 credit comes from the separate canary, its exact workflow/identity bindings, the causal probes, and cleanup attestation `sha256:ce6f67f7137fe176a231ec86020057f959d7c15ae4326689ebe2a6b944b9b818`.

The evidence file intentionally remains byte-identical with its pre-approval `evidence_complete_human_gate_b4_required` status. The separate approval record changes the governance decision without rewriting the bytes the human reviewed. Any workflow byte, App scope, catalog, ruleset, protected environment, reviewer, installation identity, or private-target identity change invalidates this approval.

## Task Commits

### Task 1: Implement the pinned daily/manual two-zone workflow

- `32466f2` — activate workflow contracts
- `7261a5f` — add two-zone discovery workflow
- `113e51a` — bind the configured semantic provider
- `cefb95f`, `49e1302`, `de9a948`, `ab295a8` — pin and harden hosted uv setup
- `39ca295`, `129fdd3` — approve and pin the refreshed App-token Action

### Task 2: Verify hosted concurrency and fresh Gate B4

- `2367963`, `abd355c` — add the controlled canary contract and implementation
- `37e5fae`, `8f0a390` — close causal-status, polling, and recovery-evidence gaps
- `b817033`, `92f69d8` — bind the reviewed private denial target and uncertain ruleset recovery
- `6fbbcd1`, `49f74e1` — prevent the private target name from appearing in hosted env logs
- `9b59d79` — record sanitized hosted concurrency, Gate B4, scan, and cleanup evidence

## Causal Gate B4 Results

| Probe | Outcome |
|---|---|
| Default-ref mutation | `validation_422` |
| Merge otherwise-mergeable PR | `denied_405` |
| Ruleset observation | `success_200` |
| Ruleset mutation | `denied_403` |
| Unauthorized reviewed private repository | `not_found_404` |
| Repository secret metadata | `denied_403` |

The default branch SHA and ruleset digest were unchanged before and after the probes. Catalog PRs `#7` and `#8` were closed unmerged by the separately authenticated human/admin, both machine branches were deleted, and only `main` remained.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Refreshed the unresolvable App-token Action pin**
- **Found during:** Hosted protected-job setup
- **Issue:** The prior approved Action commit could not be resolved by the hosted runner.
- **Fix:** Audited and separately approved the exact official replacement commit before workflow execution.
- **Files modified:** `.github/workflows/discover.yml`, `.github/workflows/publish-candidate.yml`, action audit/approval artifacts and tests.

**2. [Rule 3 - Blocking] Added a controlled Gate B4 canary after discovery produced zero eligible Drafts**
- **Found during:** Hosted Task 2 verification
- **Issue:** Successful discovery runs proved concurrency and zone behavior but had no eligible candidate with which to prove positive Draft/reviewer behavior.
- **Fix:** Added a manual-only protected canary with fixed content, a closed REST allowlist, causal denial probes, bounded sanitized evidence, and human-only cleanup locators.
- **Files modified:** `.github/workflows/gate-b4-canary.yml`, `tools/gate_b4_canary.py`, and focused canary tests.

**3. [Rule 1 - Bug] Closed canary false-positive and recovery gaps**
- **Found during:** Two independent code-review rounds
- **Issue:** Installation self-observation, broad denial classifications, immediate mergeability checks, incomplete dangerous-success recovery, and ambiguous private-target authority could over-credit a canary.
- **Fix:** Removed installation self-observation, added per-probe status contracts, bounded backoff, read-back recovery, exact reviewer checks, reviewed private-target identity, and bounded ruleset recovery.
- **Files modified:** `tools/gate_b4_canary.py`, canary workflow and tests.

**4. [Rule 1 - Bug] Removed private target value from hosted env logs**
- **Found during:** Log scan of superseded canary run
- **Issue:** The private target full name appeared in runner environment log lines when supplied as a repository variable.
- **Fix:** Moved the full name to a protected environment secret, retained non-secret numeric ID/digest authority, denied credit to the superseded run, cleaned its artifacts, and reran the exact fixed workflow.
- **Files modified:** `.github/workflows/gate-b4-canary.yml`, `tests/test_gate_b4_canary_workflow.py`.

---

**Total deviations:** 4 auto-fixed (2 Rule 1, 2 Rule 3)
**Impact on plan:** The changes were required to obtain truthful hosted evidence without widening production authority; no automatic merge, approval, ready, cleanup, or broad token surface was added.

## Known Stubs

None.

## User Setup Required

None. The reviewed hosted configuration and cleanup are complete. Any later identity or workflow change requires a new Gate B4 run and approval.

## Next Phase Readiness

- Phase 05-10 and Phase 6 may rely on the exact approved workflow bytes and hosted evidence listed above.
- The production workflow has concurrency and authority-zone credit only while every approved workflow and identity remains unchanged.
- The controlled canary remains manual-only and is not part of scheduled production discovery.

## Self-Check: PASSED

All listed artifacts and 18 task commits exist. Focused workflow, security, canary, and acceptance validation passed `69` tests; Ruff passed; the immutable evidence, approval record, cleanup attestation, three current workflow byte digests, and Summary references cross-validated exactly.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-28*
