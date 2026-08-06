---
status: resolved
trigger: "Phase 6 live benchmark preflight rejected a freshly persisted V2 authority before any provider call."
created: 2026-08-06
updated: 2026-08-06
---

# Debug Session: Phase 6 V2 Authority Preflight

## Symptoms

- expected: The approved V2 carrier is verified and the real benchmark reaches the bounded DeepSeek stage.
- actual: Run `31064734801` stopped in `live_authority_preflight` with the closed `state_integrity_error` result.
- safety boundary: No semantic request, candidate execution, state mutation, catalog write, Draft PR, or merge ran.

## Evidence

- The live-authority recording run succeeded and its carrier state was independently verified at commit `90672d4d00a1c06b5048015b5ecc98e8ffad9ea7` with root digest `sha256:2d00c35ceec27486394bd4834278ccc6d28f46cf817c28e6fd848194b1d400d1`.
- The preflight restored that carrier successfully, found exactly one V2 authority fact, and failed while validating the fact against source-owned files.
- Direct reproduction showed `_run_verify_live_authority` passed a `LiveAcceptanceAuthorityV2` document to `verify_live_acceptance_authority`, which only parsed the historical V1 schema. The V2 authority was rejected before provider or credential access.

## Resolution

- Added a V2-aware authority verifier that keeps the existing exact source, workflow, query, provider, schema, policy, and canonical-byte checks.
- Added explicit V2 selection-manifest and lock-entry binding checks.
- Routed the carrier preflight to the V2 verifier while preserving the historical V1 route.
- Added a regression proving a V2 fact cannot reach the V1 verifier.

## Verification

- The focused authority/preflight tests pass (`33 passed`).
- `tools/verify_phase6_source_execution.py` reports `phase6 source execution valid`.
- A local reproduction with the exact public carrier state and source SHA now returns `live_authority_verified`.
