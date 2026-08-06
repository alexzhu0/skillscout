---
quick_id: 260806-rbm
slug: refresh-phase6-manifest-a496
status: planned
---

# Refresh the Phase 6 benchmark manifest

Update the checked-in five-repository benchmark manifest to the human-selected
entries from fresh nomination `fresh-nomination-a496381638792609e09688c4bec24e23`.
Preserve the exact coverage distribution (one positive, one positive
multi-workflow, one borderline, two negative), bind every entry to its exact
commit/license/evidence, and submit the revision through a PR. Do not write
the default branch, campaign state, catalog, or publication state in this task.

## Tasks

1. Construct the canonical manifest revision with the current manifest digest
   as its prior revision and recompute entry, manifest, and lock-attestation
   digests.
2. Validate strict model/canonical-byte behavior and compare all selected
   fields against the successful nomination run.
3. Commit and push the manifest plus this GSD record on a `codex/` branch and
   open a Draft PR for human review.

## Verification

- `LockedBenchmarkManifestV1` strict validation passes.
- Manifest bytes equal canonical JSON (allowing one trailing newline).
- Focused Phase 6 manifest/nomination/selection tests pass.
- No model call, state write, catalog write, campaign lock, or merge occurs.
