---
quick_id: 260806-fq1
slug: refresh-benchmark-manifest
status: complete
completed: 2026-08-06
---

# Quick Task Summary

Updated the Phase 6 static benchmark manifest to the human-confirmed fresh
nomination `fresh-nomination-45509fd3370d6d791c9473beb536433e`.

## Result

- Manifest version: `3`
- Manifest digest: `sha256:44fd573c20ecf6bce4a6e56e6a46743c4deacb35147db22c87fc327e8f3f6852`
- Attestation digest: `sha256:bbcea3d33f9a349831be799a8ac9f80fee8653b17398db0b1c551190da15b989`
- Role distribution: one positive, one positive multi-workflow, one borderline, two negative.
- All entries bind exact nomination entry digests, commit SHAs, licenses, and sorted selection evidence.

## Verification

- Strict `LockedBenchmarkManifestV1` validation passed.
- Focused Phase 6 manifest/nomination/selection tests: `5 passed, 144 deselected`.
- No model, repository-code execution, state write, catalog write, PR creation, or merge occurred during manifest generation.

## Follow-up

After this manifest PR is merged, dispatch `lock-fresh-campaign` and approve the
protected human benchmark-lock environment before recording the new live authority.
