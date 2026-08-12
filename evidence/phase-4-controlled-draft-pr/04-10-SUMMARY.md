---
phase: 04-controlled-draft-pr
plan: 10
subsystem: controlled-publication-live-gate
tags: [github-app, draft-pr, ruleset, protected-environment, live-canary]
requires:
  - phase: 04-controlled-draft-pr
    provides: protected publishing workflow and opt-in causal canary
provides:
  - human-reviewed Gate B4 evidence for the exact production installation
  - causal denial evidence for protected and unauthorized surfaces
  - separate human/admin cleanup attestation
affects: [04-11, phase-04-acceptance]
key-files:
  created: [.planning/phases/04-controlled-draft-pr/04-10-SUMMARY.md]
  modified: [tests/test_publication_live_canary.py, .planning/phases/04-controlled-draft-pr/04-10-PLAN.md, .planning/phases/04-controlled-draft-pr/04-VALIDATION.md]
key-decisions:
  - "Public ruleset observation may succeed; ruleset mutation must remain denied and the reviewed digest must remain unchanged."
  - "Installation identity is independently reviewed configuration because the installation-token endpoint cannot attest itself."
  - "Ready-for-review remains a documented coarse-token residual risk and is absent from every SkillScout production surface."
requirements-completed: [PUB-01, PUB-03, PUB-04, PUB-05, SEC-02]
metrics:
  tasks: 1
  completed: 2026-07-27
status: complete
---

# Phase 04 Plan 10: Gate B4 Live Canary Summary

Gate B4 passed against the controlled public catalog. The exact GitHub App installation created the intended Draft PR and reviewer request, while protected mutations and unauthorized access failed. A separately authorized human account then removed only the canary artifacts.

## Reviewed governance evidence

- Catalog: `alexzhu0/skillscout-catalog-test`, repository ID `1310876019`, default branch `main`.
- GitHub App: App ID `4382801`, installation ID `149272172`, repository selection limited to the catalog.
- App permissions: `contents: write`, `pull_requests: write`, `metadata: read`; no Administration permission.
- Ruleset: ID `19790912`, active on the default branch, one approving review required, no bypass actors.
- Ruleset digest: `sha256:e58e74403d890296e44105cb60b42abffe522f11d169884d6d51f285b63948b5`.
- Protected environment: `skillscout-catalog-publish`; required individual reviewer `alexzhu0`; no team reviewer.
- Workflow action identities:
  - `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`
  - `actions/create-github-app-token@67018539274d69449ef7c8cde82c3ff073ffe3b5`
- Reviewed source HEAD: `3225afff21aa66ff6e03d53d67767d0139acffcd`.
- Workflow content SHA-256: `224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c`.

## Positive evidence

- Draft PR: catalog PR `#3`, created by `skillscout-catalog-test[bot]`.
- Head: `skillscout/gate-b4-canary-reviewfix-20260727` at `a81ee2052136abfaf11a26028c59338603388f05`.
- Base: `main`.
- Requested reviewers: exactly `alexzhu0`; teams empty.
- Otherwise-mergeable negative-control PR: `#4`, head `skillscout/gate-b4-mergeable-reviewfix-20260727` at `3fd820a8e624e5be80319c0b97be394e2093e27d`.
- Default SHA before and after all probes: `bd96c4fcfed5e7b2c94c79be7ec1aa6e333b71bb`.

## Causal probe evidence

| Probe | HTTP | Classification |
|---|---:|---|
| Default-ref update | 422 | validation |
| Merge otherwise-mergeable PR | 405 | denied |
| Public ruleset observation | 200 | success |
| Ruleset mutation | 403 | denied |
| Unauthorized private repository | 404 | not_found |
| Repository secret access | 403 | denied |

Ruleset identity, enforcement, rules, conditions, and empty bypass list were unchanged after the probes. The unauthorized private repository remained inaccessible.

The protected live command passed with `5 passed, 1 skipped`. Offline isolation tests additionally prove incomplete configuration never constructs the client or uses a token.

## Production-surface evidence

- Unprivileged workflow output is restricted to the three candidate locators and seven candidate digests.
- Protected catalog authority, reviewer configuration, `publication_intent_digest`, and `admission_digest` are not accepted from the unprivileged job.
- The protected job re-reads candidate evidence and derives intent/admission locally before token issuance.
- Production adapter, CLI, and workflow expose no approve/review-submission endpoint, GraphQL transport, ready-for-review transition, team request field, merge route, or cleanup route.
- Residual risk accepted: GitHub's coarse `pull_requests: write` token may support ready-for-review outside SkillScout if stolen or misused; SkillScout itself cannot express that operation.
- Secret scan: clean. No private key, installation token, JWT, authorization header, or protected secret was written to repository evidence.

## Separate-authority cleanup

- Actor: `alexzhu0`, authenticated human/admin account; not the GitHub App installation token.
- Attestation: `github-admin-cleanup-20260727-pr3-pr4`.
- PRs `#3` and `#4` are closed, not merged.
- Branches `skillscout/gate-b4-canary-reviewfix-20260727` and `skillscout/gate-b4-mergeable-reviewfix-20260727` were deleted.
- Post-cleanup branches: only `main`.
- Post-cleanup default SHA: `bd96c4fcfed5e7b2c94c79be7ec1aa6e333b71bb`.

## Deviations

The earlier PR `#1`/`#2` evidence was superseded after code-review remediation changed the protected workflow. The replacement canary bound the new workflow hash, passed without broadening privileges, and was separately cleaned as PR `#3`/`#4`.

## Self-check

PASSED. Positive Draft/reviewer behavior, causal denials, unchanged protected state, static forbidden-surface evidence, secret hygiene, and separate cleanup are all recorded with stable non-secret identifiers.
