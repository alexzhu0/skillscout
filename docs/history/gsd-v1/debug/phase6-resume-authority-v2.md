---
status: resolved
trigger: "Phase 6 benchmark run 31090867258 failed closed while resolving the exact campaign resume descendant."
created: 2026-08-06
updated: 2026-08-06
---

# Debug Session: Phase 6 Resume Authority V2

## Symptoms

- expected: The approved V2 carrier is verified and the exact campaign descendant is resolved before the live benchmark.
- actual: The protected preflight returned `state_integrity_error` before any provider request or benchmark state write.
- safety boundary: No DeepSeek call, candidate execution, publication, Draft PR, or merge occurred.

## Current Focus

- hypothesis: The resume resolver still loads the V2 `acceptance_live_authority` fact with the historical V1 model and therefore rejects the otherwise valid carrier.
- test: Reproduce `_load_verified_live_authority` against carrier `52cfe1350fe77b937b0294385f366c9812b01533` and inspect the typed fact model.
- expecting: The carrier contains exactly one V2 authority fact, while the resolver filters for `LiveAcceptanceAuthorityV1`.
- next_action: Update the resolver to use the V2 verifier and add a regression test before rerunning the protected preflight.

## Evidence

- timestamp: 2026-08-06
  observation: Carrier operations state contains `acceptance_live_authority` with schema `live-acceptance-authority-v2` and digest `sha256:1d0867c0abca0d7727bb0d7b414d7b7fc9dcb41bede0d14b85a41892e6d3f883`.
- timestamp: 2026-08-06
  observation: `_load_verified_live_authority` imports and requires `LiveAcceptanceAuthorityV1`; local reproduction raises at the `len(records) != 1` guard.

## Resolution

- root_cause: The resume resolver was left on the historical V1 authority loader after the live route moved to the fresh V2 authority contract.
- fix: Load `LiveAcceptanceAuthorityV2`, invoke `verify_live_acceptance_authority_v2`, and remove the now-unused V1 verifier import from the CLI boundary.
- verification: The new V2 loader regression passes; the resume-focused suite (20 tests), authority/admission suite (24 tests), protected preflight/workflow subset (40 tests), Ruff, and the Phase 6 source-execution verifier pass.
- files_changed: `src/skillscout/cli.py`, `tests/test_phase6_acceptance.py`

## Eliminated

- hypothesis: The carrier checkout or root digest is malformed.
  evidence: `verify-acceptance-state` succeeds for commit `52cfe1350fe77b937b0294385f366c9812b01533` and root `sha256:a483a2d02a9babbd988397d89d824d24ec05e8f948128aaceacb42bf675bfd63`.
- hypothesis: The campaign resume locator is missing.
  evidence: The carrier contains one `acceptance_campaign_resume_locator` fact with transition index 1.
