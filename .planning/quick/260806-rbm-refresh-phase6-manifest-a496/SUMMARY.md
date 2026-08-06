---
quick_id: 260806-rbm
slug: refresh-phase6-manifest-a496
status: complete
completed: 2026-08-06
---

# Quick Task Summary

Refreshed the Phase 6 static benchmark manifest from successful fresh
nomination `fresh-nomination-a496381638792609e09688c4bec24e23`.

## Result

- Nomination set digest: `sha256:812bda0e609c0b18d1b8d87d3a184acd21cfa6d058f7ab32da8f8485dadffe35`
- Manifest version: `4`
- Manifest digest: `sha256:b98dd7e563eae4dfcb7aa6064420bf600ec037eba6538299e0d0a4fdb5c967ea`
- Lock attestation digest: `sha256:9db3c4a9cac37ff82ec667a36a11535946863cf5e2195bc7b686f75978f4aeed`
- Prior manifest digest: `sha256:44fd573c20ecf6bce4a6e56e6a46743c4deacb35147db22c87fc327e8f3f6852`
- Role distribution: one positive, one positive multi-workflow, one borderline, two negative.
- All five entries bind exact nomination entry digests, commit SHAs, SPDX licenses, and sorted selection evidence.

## Verification

- Strict `LockedBenchmarkManifestV1` validation passed.
- Canonical-byte equality passed (with one permitted trailing newline).
- Fresh nomination field-by-field comparison passed.
- Focused Phase 6 tests: `5 passed, 145 deselected`.
- No model call, campaign-state write, catalog write, lock, PR merge, or publication occurred during generation.

## Follow-up

After this Draft PR is merged, dispatch `lock-fresh-campaign` for a new
protected human approval bound to the new manifest and nomination.
