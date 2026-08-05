---
status: resolved
trigger: "Authorized Phase 6 fresh nomination run 30974774249 failed with a sanitized stage_permanent_failure before any downstream job ran."
created: 2026-08-05
updated: 2026-08-05
---

# Debug Session: Phase 6 Fresh Nomination Preflight

## Symptoms

- expected: The protected fresh nomination route identifies whether failure occurs during state identity, immutable state restore, or Search.
- actual: Run `30974774249` exposed only `stage_permanent_failure`; the state bundle and reviewed Search query set were independently valid, but the failing remote read phase was not visible.
- safety boundary: No model call, candidate-code execution, state CAS, catalog write, Draft PR, approval, merge, or cleanup ran.

## Resolution

- Added a read-only `preflight-fresh-campaign` application and CLI command.
- The probe runs three closed stages: state metadata, bounded immutable state restore, and one Search page per reviewed query.
- It reports only stage names, durations, validated request/rate facts, counts, immutable state digests, and a closed error code. Exception text, raw response material, URLs, headers, and credentials are excluded.
- The preflight dependency graph has no operations store, durability barrier, semantic provider, candidate reader, or publication capability.
- The protected Phase 6 workflow exposes the route through the existing `phase6-fresh-nomination` environment with read-only permissions and the existing source/state credential split.

## Verification

- Focused acceptance, CLI-security, workflow, and source-execution tests pass.
- `tools/verify_phase6_source_execution.py` passes.
- Ruff passes on all changed Python files.
- The full suite remains subject to documented pre-existing failures in the Phase 1 capability import check, Phase 3 acceptance inspector, and Phase 6 process-harness fixtures.
