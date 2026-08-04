---
status: resolved
trigger: "Fresh Phase 6 preparation run 30791252494 persisted an exact nomination state child but exited with state_integrity_error after post-CAS verification."
created: 2026-08-03
updated: 2026-08-04
---

# Debug Session: Phase 6 Nomination Post-CAS Recovery

## Symptoms

- expected: A state-only fresh nomination that wins its exact state-branch CAS returns the verified child state and does not need another Search nomination.
- actual: Run `30791252494` wrote state child `c13c8b21b8aaf69d15d2115f9a42aaba2f755cd2` from parent `ab0ac3dd8b60c254dd20788ec936494996d76440`, then emitted the closed `state_integrity_error` result.
- errors: The CLI intentionally redacts the causal exception. No candidate code, semantic provider, lock, catalog, Draft PR, or merge job ran.
- timeline: The state child was committed immediately before the failed command completed; its root metadata binds the expected prior root and one fresh `acceptance_nomination` fact.
- reproduction: Make the first post-CAS state-ref reread fail after the update succeeds. `StateBranchStore.sync` raises `StateBranchPostCasUncertain`; the prior `sync_nomination` path rethrew it even though exact reconciliation can prove the immutable child.

## Resolution

reasoning_checkpoint:
  hypothesis: The state write succeeded, but the immediate read verification encountered an allowed uncertainty. Nomination is non-semantic and has no candidate-code/provider/publication effect, so it may safely use the existing exact full-bundle reconciliation proof; the current authority-carrier-only condition is too narrow.
  confirming_evidence:
    - The remote child has the exact observed parent and a coherent root digest.
    - The child contains the expected state-only nomination fact; pipeline and publication snapshots are unchanged.
    - The adapter constructs `StateBranchPostCasUncertain` only after create/update-ref is attempted, and its reconciliation validates the exact ref, commit, tree, root, and all bundle files.
  falsification_test: A nomination post-CAS uncertainty must return `StateSyncObservation(status='verified')` only when the existing exact reconciliation succeeds. A semantic transition must retain the existing fail-closed behavior.
  blind_spots: The hosted log intentionally does not identify which immediate verification read was unavailable. The fix must not add a state write, generic retry, semantic recovery, or diagnostic disclosure.
resolution:
  - `sync_nomination` now permits post-CAS reconciliation only after proving one exact Search-only `NominationSetV1` fact bound to the configured parent, query set, authority, and original timestamp.
  - State-branch synchronization and restore now require a state child to name its actual immediate parent root; a direct ref mutation with a missing or forged prior-root link is rejected.
  - `FreshCampaignPreparationApplication` first recognizes an already durable, exact fresh nomination in the restored current child and returns it without Search, fact recording, or state synchronization. It also binds the recovered fact to the child root's query set and timestamp.
  - Every raw state write now proves the complete existing parent/root chain before it creates a blob, tree, commit, or ref update. A true genesis has no Git parent and the explicit zero parent sentinel; malformed, ambiguous, or unlinked records fail closed.
  - Fresh Phase 6 preparation is bounded by the independently recorded public checkpoint commit/root. Live benchmark and replay carry the separately verified authority-carrier commit/root through resolver proof, exact restore, non-semantic CAS, and semantic durability confirmation; a replacement genesis or an invalid predecessor-to-carrier bridge is rejected.
  - The resolver verifies the one-edge signed-authority predecessor → configured carrier bridge before state-token access, byte-compares the remote carrier with the exact local checkout, and then visits the carrier plus at most 159 later transitions. This preserves the existing 160-transition locator contract without an off-by-one metadata cap.
  - Ordinary hosted discovery, Search-only nomination, and protected discovery-publication readback now use the code-reviewed central baseline with a 4,096-edge horizon. Their run-scoped cache retains only compact immutable commit/root-edge metadata, never SQLite snapshots or owned payload blobs; rolling that anchor needs a reviewed code change.
  - Every Phase 6 acceptance-state read now requires the independently recorded authority-carrier commit/root and explicitly enforces the narrower 160-edge limit. Benchmark, replay, human-review attestation, probe-cleanup attestation, and report rebuild fail before state access if that carrier is absent or malformed.
  - The unfinished changed-source and publication scaffolds were removed from the workflow rather than merely hard-disabled. They remain a future separately reviewed implementation task, with no residual credential-bearing job to re-enable accidentally.
  - Semantic transitions and benchmark-lock transitions retain their no-recovery behavior.

## Evidence

- timestamp: 2026-08-03
  checked: Run 30791252494 and public state commit metadata
  found: The sole active job failed after one bounded preparation; all downstream jobs were skipped. State head advanced exactly once to the child of the pre-run head.
  implication: The failure occurred after state CAS, not during model use, candidate execution, benchmark locking, or publication.

- timestamp: 2026-08-03
  checked: State-branch synchronization contract
  found: Exact reconciliation is already implemented for post-CAS uncertainty, but the durability barrier permits it only for `authority_carrier` and rethrows for `nomination`.
  implication: A narrow, exact-proof reuse is available without broadening semantic recovery.

## Eliminated

- hypothesis: The GitHub Search Link-order defect caused the current failure.
  evidence: The error changed from the prior `stage_permanent_failure` to a post-CAS `state_integrity_error`, and the fresh nomination state child exists.

## Verification

- complete Phase 6 acceptance suite: `120 passed, 1 skipped` in 13m47s, including all 12 two-process crash/recovery combinations.
- adjacent state/discovery/acceptance/semantic regression: `258 passed`.
- workflow, source-execution, and validation-map regression: `146 passed`.
- deterministic checks: `ruff check .`, `git diff --check`, `verify_phase6_source_execution.py`, `verify_phase6_validation_map.py --plan-contract`, and `verify_phase6_acceptance.py --registry-only` all passed.
- the fresh-campaign restore now explicitly uses the ordinary discovery horizon of 4,096 edges; this does not alter the independently enforced 160-transition live-campaign limit.
- full repository baseline: `854 passed`; the only failure is the pre-existing Phase 1 static-policy test `test_production_capability_surface_remains_local_only`, which flags `bootstrap.py:subprocess`. The same import exists in `HEAD` and this change does not modify it.

## Files Changed

- `src/skillscout/application/acceptance.py`
- `src/skillscout/bootstrap.py`
- `src/skillscout/adapters/state_branch.py`
- `tests/test_acceptance_application.py`
- `tests/test_phase6_acceptance.py`
- `tests/test_phase6_validation_map.py`
- `tests/test_semantic_durability.py`
- `tests/test_state_branch.py`
- `tests/test_discovery_application.py`
- `tools/verify_phase6_acceptance.py`
- `tools/verify_phase6_source_execution.py`
- `tools/verify_phase6_validation_map.py`
- `.github/workflows/phase6-acceptance.yml`
- `.planning/phases/06-adversarial-mvp-acceptance/06-VALIDATION.md`
- `docs/ARCHITECTURE.md`
- `docs/CONFIGURATION.md`
