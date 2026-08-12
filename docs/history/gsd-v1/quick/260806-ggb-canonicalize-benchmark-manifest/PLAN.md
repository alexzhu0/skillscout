---
quick_id: 260806-ggb
slug: canonicalize-benchmark-manifest
status: planned
---

# Canonicalize the Phase 6 benchmark manifest

The protected `lock-fresh-campaign` handoff requires the checked-in manifest to
be byte-for-byte canonical JSON. Convert the already human-confirmed manifest
to the repository's canonical serialization without changing any semantic
field, digest, repository, SHA, role, or license.

## Tasks

1. Replace the pretty-printed manifest bytes with the exact canonical JSON
   serialization while preserving the validated manifest digest.
2. Verify canonical-byte equality and focused manifest/selection tests.
3. Commit and push a repair PR; do not write state or rerun the lock until it is
   merged.

## Verification

- `LockedBenchmarkManifestV1` strict validation passes.
- Raw file bytes equal `canonical_json_bytes(model)` exactly (optionally with one newline only if the contract allows it).
- Focused Phase 6 manifest tests pass.
