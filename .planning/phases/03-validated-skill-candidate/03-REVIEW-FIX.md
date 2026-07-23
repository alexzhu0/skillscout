---
phase: 03-validated-skill-candidate
fixed_at: 2026-07-23T15:13:50Z
review_path: .planning/phases/03-validated-skill-candidate/03-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-07-23T15:13:50Z  
**Source review:** `.planning/phases/03-validated-skill-candidate/03-REVIEW.md`  
**Iteration:** 1

**Summary:**

- Findings in scope: 7
- Fixed: 7
- Skipped: 0
- Release verification: validation map, lock check, local build, acceptance, Ruff, 1235 tests, and terminal Gate B3 all passed

## Fixed Issues

### CR-01: Approved prior lineage can never be retained

**Status:** fixed: requires human verification  
**Files modified:** `src/skillscout/domain/candidate_authority.py`, `src/skillscout/application/phase3.py`, `src/skillscout/application/ports.py`, `src/skillscout/adapters/state.py`, `tests/test_phase3_pipeline.py`  
**Commit:** e52ed6e  
**Applied fix:** Added typed, content-addressed binding and approval evidence; exact prior terminal/package/owner re-verification; and real retained-lineage resolution through the state adapter.

### CR-02: Phase 2 authority state is opened through a raceable, followable pathname

**Files modified:** `src/skillscout/adapters/phase2_state.py`  
**Commit:** c46bd35  
**Applied fix:** Replaced pathname SQLite admission with a retained shared lock, private no-follow stable descriptor read, in-memory deserialization, query-only mode, and read-only authorization.

### CR-03: Runtime budgets change behavior without changing execution authority

**Status:** fixed: requires human verification  
**Files modified:** `src/skillscout/adapters/openai_generate.py`, `src/skillscout/adapters/openai_review.py`, `src/skillscout/application/phase3.py`, `src/skillscout/cli.py`, `src/skillscout/domain/candidate_authority.py`, `tests/test_candidate_authority.py`, `tests/test_cli_validate_skill.py`, `tests/test_openai_review.py`, `tests/test_phase3_pipeline.py`, `tests/test_qualification.py`, `tests/test_skill_validation.py`  
**Commit:** fc9547c  
**Applied fix:** Bound every runtime-profile field into execution identity and enforced exact batch, input-envelope, model, and output-token budgets before semantic calls.

### CR-04: A projection failure leaves completed state with missing or partial output forever

**Status:** fixed: requires human verification  
**Files modified:** `src/skillscout/adapters/state.py`, `src/skillscout/application/phase3.py`, `src/skillscout/application/ports.py`, `src/skillscout/cli.py`, `tests/test_cli_validate_skill.py`  
**Commit:** 1e0d15a  
**Applied fix:** Added the recoverable `projecting` ledger state, exact pending projection retrieval, idempotent repair, and completion only after durable output projection.

### CR-05: Completed reuse accepts a rendered package unrelated to terminal identity

**Status:** fixed: requires human verification  
**Files modified:** `src/skillscout/adapters/state.py`, `tests/test_phase3_pipeline.py`  
**Commit:** 3042d95  
**Applied fix:** Enforced a closed terminal artifact set and canonical cross-validation of frozen package, manifest, generated identity, validation report, provenance, lineage, and terminal package identity.

### CR-06: Gate B3 is checked only after dependency code has already executed

**Files modified:** `.planning/phases/03-validated-skill-candidate/03-14-PLAN.md`, `.planning/phases/03-validated-skill-candidate/03-VALIDATION.md`, `pyproject.toml`, `src/skillscout/bootstrap.py`, `src/skillscout/adapters/skills_ref.py`, `src/skillscout/cli.py`, `src/skillscout/domain/validation.py`, `tests/test_phase1_gap_closure.py`, `tests/test_phase3_acceptance_tool.py`, `tests/test_phase3_pipeline.py`, `tests/test_skill_validation.py`, `tools/verify_phase3_acceptance.py`, `tools/verify_phase3_validation_map.py`  
**Commit:** 4e27a30  
**Applied fix:** Added a standard-library bootstrap that admits the lock and installed validator bytes before dependency import, made validator loading lazy, separated approved wheel and observed runtime digests, and registered the boundary in acceptance.

### WR-01: Reviewer attestation says “no retry” even when the runner retries three times

**Status:** fixed: requires human verification  
**Files modified:** `.planning/phases/03-validated-skill-candidate/03-VALIDATION.md`, `src/skillscout/adapters/state.py`, `src/skillscout/application/phase3.py`, `src/skillscout/domain/candidate_authority.py`, `src/skillscout/domain/review.py`, `tests/test_candidate_authority.py`, `tests/test_openai_review.py`, `tests/test_phase3_acceptance_tool.py`, `tests/test_phase3_pipeline.py`, `tests/test_qualification.py`, `tests/test_skill_validation.py`, `tools/verify_phase3_acceptance.py`  
**Commit:** e42f671  
**Applied fix:** Bound reviewer-specific retry policy and maximum attempts into execution authority and attestation, persisted bounded transient-failure facts, and verified attestation attempt count against the reviewer ledger attempt.

---

_Fixed: 2026-07-23T15:13:50Z_  
_Fixer: the agent (gsd-code-fixer)_  
_Iteration: 1_
