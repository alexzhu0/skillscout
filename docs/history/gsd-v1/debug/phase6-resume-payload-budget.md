# Phase 6 resume payload-budget diagnosis

## Status

Resolved on 2026-08-10.

## Symptom

The real Phase 6 benchmark preflight run `31367636630` stopped in
`Resolve the exact campaign resume descendant` before any semantic provider
credential, source-content read, Skill generation, or catalog operation.

## Evidence and root cause

The locked campaign and its environment-approved live authority were both
persisted and independently read back. The authority-carrier state snapshot
contained 272 verified files. The resume resolver used one ordinary
`ResolverReadBudget` for both the bounded lineage proof and full immutable
payload restoration. Its 45-second budget expired after 47 seconds.

## Repair boundary

The resolver now uses the existing split-budget policy: lineage/ref reads use
the 45-second `lineage` budget; complete immutable payload restoration uses
the already-defined 90-second `payload` budget. Request and response-byte caps
remain unchanged. A regression test asserts that the resolver never routes
payload restoration through the lineage budget.

## Verification

- Resume-focused tests: 20 passed.
- Phase 6 workflow/source tests: 162 passed.
- Ruff for changed Python files: passed.
- The unrelated static manifest-verifier baseline remains outside this change.
