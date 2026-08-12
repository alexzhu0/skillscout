---
phase: 03-validated-skill-candidate
plan: "05"
subsystem: domain
tags: [authority, canonical-json, lineage, pydantic, tdd]

requires:
  - phase: 03-04
    provides: Gate B3 dependency equality preflight and approved immutable lock authority
  - phase: 02-safe-single-repository-extraction
    provides: Strict WorkflowSpec semantic boundary, full fingerprints, canonical digest helpers, and verified Phase 2 anchors
provides:
  - Complete immutable WorkflowSpec and Phase 3 prelookup execution authorities
  - Strict one-digest candidate descriptor contract with no heuristic prior-binding search authority
  - Deterministic new lineage plus exact approved-binding retention and fail-closed rejection matrix
affects: [03-06, 03-07, 03-08, 03-09, 03-10, 03-11, 03-12, candidate-source, phase3-ledger]

tech-stack:
  added: []
  patterns:
    - Complete canonical source authority embeds every WorkflowSpec semantic/evidence field and verified upstream anchor
    - Prelookup reuse authority contains only configured identities and immutable policy/version inputs
    - Historical lineage is retained only through one exact binding plus independently verified prior evidence

key-files:
  created:
    - src/skillscout/domain/candidate_authority.py
    - tests/test_candidate_authority.py
    - tests/test_lineage.py
  modified: []

key-decisions:
  - "Embed the complete strict WorkflowSpec and both verified Phase 2 anchors in WorkflowSpecAuthorityV1; wf-fingerprint-v1 remains only the selected workflow discriminator."
  - "Keep configured Generator/Reviewer identities in CandidateExecutionAuthorityV1 and structurally exclude actual response model identities until later terminal evidence."
  - "Derive new lineage from numeric repository ID plus initial complete WorkflowSpec authority; retain it only when one canonical binding, durable approval target, and verified prior package/terminal/initial-authority evidence all agree."
  - "Derive a bounded Agent Skills slug from normalized title plus a lineage-digest suffix, but never use title, slug, path, or content similarity as matching authority."

patterns-established:
  - "Self-hashed authority records exclude only their own digest field and reject hand-authored digest mismatches."
  - "Descriptor absence of prior_lineage_binding_digest means new-lineage evaluation; it grants no state/catalog search authority."
  - "Lineage rejection reasons use a bounded closed vocabulary and never contain raw external content."

requirements-completed: [GEN-04, GEN-05]

coverage:
  - id: D1
    description: "Complete source and execution authority contracts bind every semantic, evidence, configured model, prompt, schema, policy, renderer, validator, profile, retry, distribution, and approved-lock input before Phase 3 lookup."
    requirement: GEN-04
    verification:
      - kind: unit
        ref: "tests/test_candidate_authority.py (58 complete-field sensitivity, strictness, canonicalization, and prelookup-boundary cases)"
        status: pass
      - kind: other
        ref: "Gate-B3-prefixed full pytest suite: 734 passed; ruff check .: clean"
        status: pass
    human_judgment: false
  - id: D2
    description: "New lineage is deterministic and prior identity is retained only through one exact canonical binding whose approval, prior package, terminal summary, repository, slug, and initial authority all reverify."
    requirement: GEN-05
    verification:
      - kind: unit
        ref: "tests/test_lineage.py (29 new, retained, tamper, collision, duplicate, ambiguity, and not-evaluated cases)"
        status: pass
      - kind: integration
        ref: "Gate-B3-prefixed protected regression set: 138 passed"
        status: pass
    human_judgment: false

duration: 14 min
completed: 2026-07-23
status: complete
---

# Phase 03 Plan 05: Immutable Candidate Authority and Lineage Summary

**Complete canonical prelookup identity now binds the entire verified WorkflowSpec and Phase 3 configuration, while local Skill lineage can persist only through one exact human-approved, independently reverified prior binding.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-07-23T09:41:19Z
- **Completed:** 2026-07-23T09:55:00Z
- **Tasks:** 2/2
- **Implementation/test files:** 3

## Accomplishments

- Added strict frozen `CandidateSubjectDescriptorV1`, `WorkflowSpecAuthorityV1`, and `CandidateExecutionAuthorityV1` contracts with exact tagged SHA-256 canonical identities.
- Bound every complete WorkflowSpec field, nested evidence record, Phase 2 Extractor output/chain anchor, configured model, prompt/schema/policy, renderer, validator distribution/hash, approved B3 lock, eligibility, producer/profile, and retry version before any Phase 3 state lookup.
- Added canonical prior-lineage binding, verified prior evidence, deterministic new lineage/slug, exact retained lineage, and a bounded fail-closed rejection matrix covering stale, tampered, duplicate, colliding, multiple, and ambiguous evidence.
- Preserved the distinction between configured prelookup model identity and actual response model evidence; no actual model field can enter the authority schema.

## Task Commits

Each TDD task was committed with RED before GREEN:

1. **Task 1 RED: Complete candidate authority contracts** - `ceb3f5b` (`test`)
2. **Task 1 GREEN: Complete source and execution authorities** - `230493d` (`feat`)
3. **Task 2 RED: Exact lineage resolution contracts** - `0ae39d6` (`test`)
4. **Task 2 GREEN: Exact binding and verified-evidence lineage resolution** - `f0e1554` (`feat`)

## Files Created/Modified

- `src/skillscout/domain/candidate_authority.py` - Versioned candidate descriptor, complete authorities, prior binding/evidence, lineage derivation, canonical digests, and closed resolution.
- `tests/test_candidate_authority.py` - Complete WorkflowSpec/evidence/source-anchor and prelookup-configuration sensitivity matrices plus strict/canonical boundary tests.
- `tests/test_lineage.py` - New/retained identity, heuristic exclusion, every binding/evidence mutation, initial-authority tamper, collision, duplicate, and ambiguity tests.

## Decisions Made

- The complete `WorkflowSpec` is embedded in its authority object instead of being represented only by a digest or the intentionally partial `wf-fingerprint-v1`; downstream reports can directly bind and cross-check the full authority.
- `CandidateExecutionAuthorityV1` has no implicit reuse-sensitive defaults. Every configured version and identity must be supplied, while actual response model IDs remain impossible as extra fields.
- A prior binding's `binding_id` is the canonical digest of its complete target, including the durable approval-record digest. The approval record independently binds the same repository, lineage, slug, prior artifacts, target authority, and binding policy.
- Verified prior evidence carries the complete prior initial WorkflowSpec authority so resolution can recompute the original lineage rather than trusting historical lineage labels.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Canonicalization] Converted nested authority models before hashing plain dictionaries**
- **Found during:** Task 1 GREEN
- **Issue:** The shared canonical helper converts a top-level Pydantic model, but a `WorkflowSpec` nested inside an ordinary dictionary was not JSON serializable.
- **Fix:** Constructed explicit JSON-compatible preimages with `model_dump(mode="json", exclude_none=False)` while passing the original strict model object into the Pydantic contract.
- **Files modified:** `src/skillscout/domain/candidate_authority.py`
- **Verification:** All 58 candidate-authority cases and the full 734-test suite pass.
- **Committed in:** `230493d`

**2. [Rule 1 - Test Harness] Preserved strict tuple types while mutating WorkflowSpec fixtures**
- **Found during:** Task 1 GREEN
- **Issue:** The sensitivity helper round-tripped through JSON-mode dumps, which correctly converted tuples to lists that the existing strict `WorkflowSpec` rejects before the intended one-field mutation could be measured.
- **Fix:** Used Python-mode dumps and tuple-valued collection mutations so each parameterized case changes exactly its intended semantic field.
- **Files modified:** `tests/test_candidate_authority.py`
- **Verification:** All 25 complete WorkflowSpec field/evidence mutation cases independently change authority.
- **Committed in:** `230493d`

---

**Total deviations:** 2 auto-fixed Rule 1 implementation/test-harness bugs.
**Impact on plan:** Both fixes preserve the repository's existing strict and canonical contracts; no authority, schema, dependency, network, filesystem, or remote-write scope was broadened.

## Issues Encountered

- The sandbox initially denied access to uv's existing cache. Every dependency-backed retry still began with the required Gate B3 preflight and used the approved repository-local uv executable.

## Authentication Gates

None.

## Known Stubs

None.

## Verification

- Task 1 exact command: **58 passed**.
- Task 2 exact command: **29 passed**.
- Protected focused regression (`candidate_authority`, `lineage`, `stage_contracts`, `extractor_boundary`): **138 passed**.
- Full Gate-B3-prefixed test suite: **734 passed**.
- Full Gate-B3-prefixed Ruff: **All checks passed**.
- Stub scan: empty.
- Threat-surface scan: no new endpoint, credential, network, filesystem, database/schema, authentication, or remote-write surface. The new trust boundary is the plan-authored canonical authority/lineage transform covered by T-03-09, T-03-10, and T-03-11.

## User Setup Required

None.

## Next Phase Readiness

- Plan 03-06 can safely derive/load one canonical candidate descriptor, reverify the referenced Phase 2 result, and compare the full `WorkflowSpecAuthorityV1` before Phase 3 state access.
- Later qualification, generation, validation, review, ledger, and terminal contracts can directly bind the complete WorkflowSpec and execution authority without reconstructing partial identity.
- A future state adapter must supply `VerifiedPriorLineageEvidenceV1` only after exact prior chain, terminal-summary, package, approval-record, and binding-byte verification; absence must remain a no-search new-lineage path.

## Self-Check: PASSED

- Found all three declared implementation/test files and this summary on disk.
- Confirmed all four TDD commits are commit objects in repository history.
- Reconfirmed the exact task suites, protected regression suite, full test suite, full Ruff gate, stub scan, and threat-surface scan recorded above.

---
*Phase: 03-validated-skill-candidate*
*Completed: 2026-07-23*
