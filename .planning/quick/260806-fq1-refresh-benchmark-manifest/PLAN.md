---
quick_id: 260806-fq1
slug: refresh-benchmark-manifest
status: planned
---

# Refresh Phase 6 benchmark manifest

Update the checked-in five-repository benchmark manifest to the human-confirmed
selection from fresh nomination `fresh-nomination-45509fd3370d6d791c9473beb536433e`.
Preserve the exact role distribution (one positive, one positive multi-workflow,
one borderline, two negative), recompute all canonical entry/manifest/attestation
digests, and verify the locked manifest contract locally. Submit the change on a
PR branch; do not write `main` or the state branch directly.

## Tasks

1. Construct the canonical `locked-benchmark-manifest-v1` revision from the
   confirmed nomination entries and current prior manifest digest.
2. Run strict model validation, focused Phase 6 manifest tests, and Ruff on any
   touched Python helper (none expected).
3. Commit the manifest and GSD summary atomically, push a `codex/` branch, and
   open a Draft PR for human review.

## Verification

- `UV_CACHE_DIR=/private/tmp/skillscout-uv-cache .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k 'manifest or nomination or selection'`
- Parse the manifest with `LockedBenchmarkManifestV1` and confirm all five
  entries match the fresh nomination by repository ID, full name, SHA, license,
  provenance, and evidence digests.
- Confirm no model call, state write, catalog write, or merge occurs in this task.
