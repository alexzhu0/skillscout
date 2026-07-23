---
phase: 03-validated-skill-candidate
reviewed: 2026-07-23T14:18:30Z
resolved: 2026-07-23T15:13:50Z
depth: deep
files_reviewed: 42
files_reviewed_list:
  - config/supply-chain/phase3-gate-b3.lock.sha256
  - pyproject.toml
  - src/skillscout/adapters/openai_generate.py
  - src/skillscout/adapters/openai_review.py
  - src/skillscout/adapters/phase2_state.py
  - src/skillscout/adapters/skills_ref.py
  - src/skillscout/adapters/state.py
  - src/skillscout/application/candidate_source.py
  - src/skillscout/application/phase3.py
  - src/skillscout/application/ports.py
  - src/skillscout/cli.py
  - src/skillscout/domain/candidate_authority.py
  - src/skillscout/domain/models.py
  - src/skillscout/domain/qualification.py
  - src/skillscout/domain/review.py
  - src/skillscout/domain/skill_artifacts.py
  - src/skillscout/domain/validation.py
  - tests/fixtures/openai/generator/cases.json
  - tests/fixtures/openai/reviewer/cases.json
  - tests/fixtures/skills/valid-skill/SKILL.md
  - tests/fixtures/skills/valid-skill/references/provenance.json
  - tests/recorded_transport.py
  - tests/test_candidate_authority.py
  - tests/test_candidate_source.py
  - tests/test_cli_security.py
  - tests/test_cli_validate_skill.py
  - tests/test_lineage.py
  - tests/test_openai_generate.py
  - tests/test_openai_review.py
  - tests/test_phase1_gap_closure.py
  - tests/test_phase3_acceptance_tool.py
  - tests/test_phase3_lock_preflight.py
  - tests/test_phase3_pipeline.py
  - tests/test_phase3_validation_map.py
  - tests/test_qualification.py
  - tests/test_skill_generation.py
  - tests/test_skill_validation.py
  - tools/verify_phase1_gap_evidence.py
  - tools/verify_phase3_acceptance.py
  - tools/verify_phase3_gate_b3.sh
  - tools/verify_phase3_validation_map.py
  - uv.lock
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
resolved_findings:
  critical: 6
  warning: 1
  info: 0
  total: 7
status: resolved
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-23T14:18:30Z  
**Depth:** deep  
**Files Reviewed:** 42  
**Status:** resolved

## Summary

All six blockers and the Reviewer retry warning are resolved in isolated RED/GREEN commits. The release chain passed the validation-map self-check, lock check, local wheel/sdist build, dependency-free acceptance inspector, Ruff, **1235 tests**, and the terminal Gate B3 preflight.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Approved prior lineage can never be retained

**Classification:** BLOCKER  
**Resolution:** RESOLVED in `e52ed6e` — typed binding/approval artifacts, exact prior-terminal verification, and real retained-lineage orchestration.  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:480-498`  
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:3650-3657`, `/Users/alexzhu/Lenovo/skillscout/tests/test_phase3_pipeline.py:1043-1048`  
**Issue:** Every non-null `prior_lineage_binding_digest` is unconditionally closed as `lineage_rejected`; the runner never asks state for the exact binding or calls `resolve_lineage`. The advertised state API is a stub that validates only digest syntax and returns `None`. The test suite enshrines that stub instead of exercising the required approved-update path. Consequently SKIL-04 and the Plan 03-11 exact prior-chain/package/approval verification contract are absent from production.

**Fix:** Persist the canonical binding and approval records as typed artifacts. Implement exact-digest lookup that verifies the prior Phase 3 chain, terminal summary, package manifest/digest, repository, initial WorkflowSpec authority, and approval digest before constructing `VerifiedPriorLineageEvidenceV1`. In the runner, call `resolve_lineage` with exactly that verified projection and reject only missing, invalid, or ambiguous evidence. Add an end-to-end retained-lineage test through the real state adapter.

### CR-02: Phase 2 authority state is opened through a raceable, followable pathname

**Classification:** BLOCKER  
**Resolution:** RESOLVED in `c46bd35` — retained shared lock, private no-follow descriptor admission, stable byte snapshot, and query-only in-memory SQLite.  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/phase2_state.py:57-86`  
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/cli.py:288-318`  
**Issue:** `_open_read_only_verifier` anchors only the parent directory and then gives `sqlite3.connect()` an ordinary file URI. It does not admit the database as an owned private regular single-link file, use `O_NOFOLLOW`, retain a descriptor, compare pre/open/post identity, or acquire the state lock. The CLI's earlier `lstat` is not retained, so a path can be replaced with a symlink or different database between validation and SQLite open. `immutable=1` further tells SQLite to assume the file cannot change. A substituted but internally coherent Phase 2 database can therefore become the source of Phase 3 authority.

**Fix:** Mirror the completed-projector design: acquire the verified shared state lock, descriptor-read the database through the anchored parent with `O_RDONLY|O_NOFOLLOW|O_CLOEXEC`, enforce owner/mode/type/link/size and complete metadata stability, deserialize the admitted bytes into `:memory:`, then set `query_only` and the read-only authorizer. Never pass this trust-boundary pathname to SQLite.

### CR-03: Runtime budgets change behavior without changing execution authority

**Classification:** BLOCKER  
**Resolution:** RESOLVED in `fc9547c` — full runtime-profile digest plus exact candidate, request-envelope, model, input, and output budget enforcement.  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:109-132`  
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:159-192`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/candidate_authority.py:121-157`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:844-863`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:1075-1090`  
**Issue:** The profile exposes candidate, retry, input-byte, and output-token limits, but execution authority binds only the profile's version string. Two profiles with the same `profile_version` and different limits produce the same authority digest and can exact-reuse each other's result. Enforcement is also inconsistent: `run_phase_three_batch` ignores `max_candidates` and hardcodes three; Reviewer input sizing omits JSON metadata and delimiter overhead; output-token ceilings are checked only after the remote call; and dependency factories are not required to use the configured model or token cap. These are material execution/cost-policy changes hidden behind one reuse identity.

**Fix:** Give the complete immutable runtime profile a self-digest and include that digest (or every limit) in `CandidateExecutionAuthorityV1`. Enforce the profile at the call boundary: build and size the exact Reviewer envelope, construct clients with the exact configured token ceilings, verify each adapter's configured model/capability identity before invocation, and make batch execution consume the applicable `max_candidates`. Add sensitivity tests for every profile field and prove each policy mutation causes a clean completed miss.

### CR-04: A projection failure leaves completed state with missing or partial output forever

**Classification:** BLOCKER  
**Resolution:** RESOLVED in `1e0d15a` — recoverable `projecting` state and idempotent exact projection repair before completed reuse exposure.  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:946-993`  
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:1024-1062`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/cli.py:186-239`  
**Issue:** `_terminal` marks the run completed before `PhaseThreeApplication` projects local output. The projector commits the package first and evidence files one by one afterward. If an evidence write, fsync, or directory check fails, state remains completed and output may contain only the package or a prefix of evidence. A retry takes the completed-reuse branch, which deliberately performs no output mutation, so it reports success and evidence paths without repairing the absent files. The candidate is permanently split between terminal state and local artifacts.

**Fix:** Add a recoverable projection state to the ledger and stage the entire package-plus-evidence tree before terminal exposure. Resume must verify and finish an exact staged/partial projection idempotently; only after the output set is durable should the run enter externally reusable `completed` state. Test failures after package promotion and after each evidence write, then prove one retry yields the exact complete tree without semantic replay.

### CR-05: Completed reuse accepts a rendered package unrelated to terminal identity

**Classification:** BLOCKER  
**Resolution:** RESOLVED in `3042d95` — exact artifact-kind closure and canonical package/manifest/identity/provenance cross-validation.  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/state.py:743-856`  
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/cli.py:150-183`  
**Issue:** The completed projector parses and binds `package_identity`, but `rendered_package` and `package_manifest` fall through to a generic raw SHA-256 and are never compared with that identity. The terminal artifact matrix permits these extra artifacts without validating their schema, canonical bytes, manifest, provenance, generated-artifact identity, or package digest. An attacker who updates the local artifact row and content-addressed file can substitute any canonical rendered package while leaving the verified terminal/authority unchanged; the CLI then parses and advertises the substituted package's own digest.

**Fix:** Require an exact closed artifact-kind set for every terminal branch. Parse `rendered_package` as canonical `FrozenSkillPackageV1`, recompute its manifest and `PackageIdentityV1`, and require equality with the terminal, validation report, generated-artifact identity, and provenance authority. Parse `package_manifest` canonically and require equality with the package manifest. Reject any unknown or uncited artifact kind.

### CR-06: Gate B3 is checked only after dependency code has already executed

**Classification:** BLOCKER  
**Resolution:** RESOLVED in `4e27a30` — dependency-free bootstrap, pre-import lock/runtime-distribution admission, lazy validator import, and separate approved/observed hashes.  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/skills_ref.py:5-8`  
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/skills_ref.py:35-48`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/adapters/skills_ref.py:82-96`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/cli.py:13-20`, `/Users/alexzhu/Lenovo/skillscout/pyproject.toml:17-18`  
**Issue:** Importing the CLI immediately imports `skills_ref`, OpenAI, and other locked dependencies. `_verify_approved_lock_authority()` runs only later when validation is called, after `skills_ref` module code has executed. The adapter checks only the installed version and then reports the audited wheel hash from a constant; it never verifies that the executing installed files came from or still match that artifact. Direct console-script/library use therefore bypasses the claimed pre-execution dependency gate, and a modified same-version package can execute and be attested with the approved hash.

**Fix:** Point the console script at a dependency-free bootstrap that performs the no-follow Gate-B3 lock check before importing `skillscout.cli` or any third-party package. Move the `skills_ref` import behind that verified boundary and validate the installed distribution/file record against the approved environment authority. Distinguish an approved wheel hash from an observed runtime distribution digest; do not emit the former as if it verified the latter. Add a subprocess test with an import-time canary proving no dependency module executes when preflight fails.

## Warnings

### WR-01: Reviewer attestation says “no retry” even when the runner retries three times

**Classification:** WARNING  
**Resolution:** RESOLVED in `e42f671` — reviewer-specific retry authority, bounded failed-attempt facts, and attestation/ledger attempt agreement.  
**File:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/review.py:27-31`  
**Related:** `/Users/alexzhu/Lenovo/skillscout/src/skillscout/domain/review.py:403-415`, `/Users/alexzhu/Lenovo/skillscout/src/skillscout/application/phase3.py:922-944`  
**Issue:** `ReviewAttestationV1.reviewer_retry_policy_version` is always `reviewer-no-retry-v1`, while `_retry_review` performs up to `max_reviewer_attempts` (default three) and persists the successful attempt number. The attestation's audit claim is false whenever a transient failure precedes success.

**Fix:** Bind the runner-owned Reviewer retry policy and maximum attempts into execution authority and attestation, or truly enforce one attempt. Persist bounded failed-attempt facts so the successful attestation and ledger agree on how many remote calls occurred.

---

_Reviewed: 2026-07-23T14:18:30Z_  
_Resolved: 2026-07-23T15:13:50Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: deep_
