# Phase 6 Plan 18: User Setup Required

**Generated:** 2026-08-04
**Phase:** adversarial-mvp-acceptance
**Status:** Incomplete

These are the only remaining browser-only steps before the protected, state-only
V2 live-authority receipt can be recorded. Do not send any credential value to
Codex or place one in the repository.

## Environment Secret

| Status | Secret name | Create it from | Add to |
|---|---|---|---|
| [ ] | `SKILLSCOUT_LIVE_AUTHORITY_STATE_GITHUB_TOKEN` | A fresh fine-grained GitHub token owned by `alexzhu0`, limited to `alexzhu0/skillscout`, with repository `Contents: Read and write` and the shortest practical expiry | Environment `skillscout-phase6-live-authority` only |

The workflow maps this secret only to the final state-persistence step. It is
not a model, source-repository, catalog, or pull-request credential.

## GitHub Environment Configuration

- [ ] Create or open `skillscout-phase6-live-authority`.
  - Location: `alexzhu0/skillscout` → **Settings** → **Environments**.
  - Deployment branches and tags: allow `main` only.
- [ ] Add required reviewer `alexzhu0`.
  - Leave **Prevent self-review** disabled: the sole required reviewer may be
    the person who dispatched this state-only route.
- [ ] Do not add a custom deployment protection rule, signing/key scheme, or
  any environment variable.
- [ ] Add the environment secret from the table above. Paste it once in GitHub;
  do not copy it into chat, logs, test fixtures, project files, or state.

## What This Enables

After this setup and the PR are merged, the `record-live-authority` workflow
job may do exactly one thing after environment approval: persist and rebuild a
V2 `live_execution` authority receipt bound to the current V2 benchmark lock.
It cannot call DeepSeek, read a source candidate, execute candidate code,
access the catalog, create a pull request, review, publication, merge, cleanup,
or Gate B4 effect.

## Verification

When the setup is complete, report only that it is complete. Do not provide the
secret value. I will then verify the non-secret environment configuration and
prepare the human approval checkpoint without dispatching a benchmark, replay,
or publication action.

**Once all items are complete:** change **Status** above to `Complete`.
