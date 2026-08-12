---
status: resolved
trigger: "Phase 6 run-benchmark is stopped by the credential-free Gate B3 distribution check before semantic work; the durable authority carrier also lacks the first campaign resume locator required by the current protocol."
created: 2026-07-31
updated: 2026-07-31
---

# Phase 6 live preflight blockers

## Symptoms

- Expected: the approved live benchmark reaches its bounded DeepSeek stages only after the immutable authority and campaign-resume preflight pass.
- Actual: GitHub Actions run `30614957077` stops in `live_authority_preflight` before any model request, source-repository execution, catalog write, or PR.
- Error: `PhaseThreeGateError: Phase 3 Gate B3 preflight failed` while importing `skillscout.cli` on the hosted runner.
- Additional evidence: the durable authority carrier `ab0ac3dd8b60c254dd20788ec936494996d76440` / `sha256:5c7a1097c0e6cee8b85150120078c434fe1a24ae908a1c91fa6b4b86df57cfd8` is valid, but has no `acceptance_campaign_resume_locator`; the resume resolver requires a locator for every successor edge after the original campaign state.
- Reproduction: dispatch `phase6-acceptance.yml` with `phase6_action=run-benchmark` at source `4c7baba3052765ce52993dbb129ac5fa126495df`, using the independently verified authority variables.

## Current Focus

- fault_tree:
  - "the hosted workflow does not materialize the exact Phase 3 validator distribution required at CLI import"
  - "the Gate B3 verifier incorrectly rejects a legitimate locked hosted layout"
  - "the authority-record transition is not modeled as an admissible zero-stage campaign resume anchor"
  - "a future protocol repair could accidentally weaken source, state, or human-approval binding"
- hypothesis: The workflow needs a deterministic, integrity-checked validator-distribution setup before any CLI import, and the resume protocol needs an explicit, narrowly verified authority-carrier anchor. Both changes require a new source commit and therefore a fresh human authority before another live benchmark.
- test: Identify the exact missing Gate B3 file/distribution condition on a clean hosted layout; add focused regression coverage for the intended hosted setup and for a carrier-only authority successor.
- expecting: Current code fails those focused tests; a repair passes only when it preserves fail-closed behavior for altered distributions, unrelated successor states, and any missing/changed authority fact.
- next_action: Diagnose source and workflow setup first, then propose the smallest verified repair. Do not use credentials, invoke providers, dispatch workflows, or publish artifacts during diagnosis.

## Evidence

- 2026-07-31: run `30614957077` failed in the credential-free `Verify the immutable original live authority` step; `live_benchmark` was skipped.
- 2026-07-31: its failed log shows `require_phase3_gate_b3()` rejected the validator distribution before `verify-live-authority` ran.
- 2026-07-31: no DeepSeek request, untrusted source-code execution, catalog write, PR, or merge occurred in that run.
- 2026-07-31: independent local verification confirmed authority digest `sha256:87f354fc931f67913d948c99a61ffbd8de35bf99b16f9f60386debe6582facd9` binds the exact source, original state, manifest, workflow digest, provider, and Flash/Flash/Pro model split.
- 2026-07-31: carrier `ab0ac3d...` is a direct successor of original campaign state `500b3d...` and contains exactly one matching authority fact, but no resume locator for that edge.

## Eliminated

- hypothesis: The live benchmark reached DeepSeek or publication. Evidence: the preflight import failed before those jobs/steps became eligible.
- hypothesis: The authority receipt is malformed. Evidence: local `verify-live-authority` passed against the immutable carrier and original bound state identities.

## Resolution

- Root causes: the hosted preflight job allowed a hard-linked validator distribution that Gate B3 correctly rejects, and the original authority carrier omitted the required first campaign resume locator.
- Fix: preflight now uses `UV_LINK_MODE: copy`; authority recording creates an `authority_carrier` locator in the same CAS child and the resolver admits only its unique matching live-authority fact.
- Follow-up: the old authority remains immutable historical evidence. A fresh nomination, fresh human-locked benchmark, and a newly approved exact authority are required before another live benchmark.
