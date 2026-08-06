---
quick_id: 260806-ggb
slug: canonicalize-benchmark-manifest
status: complete
completed: 2026-08-06
---

Repair task completed after the protected lock route correctly rejected
noncanonical pretty-printed manifest bytes. The manifest now uses the exact
canonical JSON serialization accepted by the workflow (with one permitted
trailing newline). No state write or model call occurred.

## Verification

- Raw bytes equal `canonical_json_bytes(model)` or that value plus one newline.
- Strict `LockedBenchmarkManifestV1` validation passed.
- Focused Phase 6 tests: `5 passed, 144 deselected`.
