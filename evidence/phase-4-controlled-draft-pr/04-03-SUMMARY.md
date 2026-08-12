---
phase: 04-controlled-draft-pr
plan: 03
subsystem: publication-domain
tags: [pydantic, canonical-digest, draft-pr, authority-boundary]
requires:
  - phase: 03
    provides: canonical eligible candidate terminal artifacts
provides:
  - authority-free candidate publication evidence
  - catalog and reviewer-bound publication admission identities
  - deterministic Draft PR metadata and recovery marker
affects: [04-04, 04-05, 04-06, controlled-publishing]
tech-stack:
  added: []
  patterns: [strict frozen contracts, canonical SHA-256 identities, protected authority composition]
key-files:
  created: [src/skillscout/domain/publication.py]
  modified: []
key-decisions:
  - "Candidate evidence remains catalog- and reviewer-free; protected authority is required for intent and admission."
  - "Machine markers bind stable ownership separately from revision-specific package evidence."
patterns-established:
  - "Publication inputs are closed Pydantic contracts with code-derived paths and branches."
requirements-completed: [PUB-01, PUB-02, PUB-03, PUB-05]
coverage:
  - id: D1
    description: Authority-free candidate evidence and protected catalog/reviewer publication intent.
    requirement: PUB-01
    verification:
      - kind: unit
        ref: tests/test_publication_domain.py
        status: pass
    human_judgment: false
  - id: D2
    description: Deterministic Draft metadata and recoverable machine marker.
    requirement: PUB-02
    verification:
      - kind: unit
        ref: tests/test_publication_domain.py
        status: pass
    human_judgment: false
duration: 18min
completed: 2026-07-24
status: complete
---

# Phase 04 Plan 03: Controlled Publication Domain Summary

**Strict candidate-only publication evidence, protected catalog/reviewer admission, and deterministic Draft PR metadata without any remote capability.**

## Accomplishments

- Added closed, immutable publication identities, catalog authority, individual reviewer targets, admission, marker, record, and result contracts.
- Revalidated eligible Phase 3 terminal artifacts into exact frozen file evidence before protected authority is composed.
- Rendered stable Draft titles, human-review metadata, and a bounded catalog-bound machine marker.

## Task Commits

1. **Task 1: Define closed catalog and publication identities** — `28075f9`
2. **Task 2: Admit the exact eligible Phase 3 bundle** — `9af2020`
3. **Task 3: Render deterministic Draft metadata and machine marker** — `1bc3e0c`

## Verification

- `mkdir -p /private/tmp/skillscout-uv-cache && .tools/uv-0.11.29/bin/uv run --cache-dir /private/tmp/skillscout-uv-cache --locked pytest -q tests/test_publication_domain.py` — 18 passed.

## Decisions Made

- Candidate handoff data excludes catalog, reviewer, branch, intent, and authority-bound admission fields.
- Catalog root and machine branch are code-derived and the default branch is rejected as a machine branch.
- Marker recovery validates stable catalog identity without requiring its previous desired revision to equal a new candidate revision.

## Deviations from Plan

None - plan executed within the pure publication-domain boundary. The full publication-security suite is intentionally deferred because it asserts adapters and workflow files owned by later Phase 04 plans.

## Known Stubs

None.

## Self-Check: PASSED

- `src/skillscout/domain/publication.py` exists.
- Task commits `28075f9`, `9af2020`, and `1bc3e0c` exist.
