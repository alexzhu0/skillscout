---
phase: 04-controlled-draft-pr
plan: 09
subsystem: controlled-publication-security
tags: [github-actions, github-app, draft-pr, canary, least-privilege]
requires:
  - phase: 04-controlled-draft-pr
    provides: candidate-only admission verifier, protected authority loading, and Gate A4-approved action identities
provides:
  - immutable protected Actions workflow with late catalog-scoped token minting
  - opt-in test-only causal platform canary with cleanup-manifest-only output
affects: [04-10, 04-11, controlled-publishing]
tech-stack:
  added: []
  patterns: [candidate-only-cross-job-handoff, protected-local-admission, test-only-live-probe]
key-files:
  created: [.github/workflows/publish-candidate.yml]
  modified: [tests/test_publication_security.py, tests/test_publication_live_canary.py]
key-decisions:
  - "Only the approved checkout and GitHub App token commits may run in the production workflow."
  - "Intent and admission digests remain protected-job-local and are rederived before token minting."
  - "Ready-for-review is a residual coarse-token platform risk proven absent from SkillScout's production surface, not claimed as a live denial."
patterns-established:
  - "Unprivileged jobs export only fixed candidate locators and candidate digests; protected authority never crosses backward."
  - "Live platform probes are explicit test-only clients with an isolated transport and no remote cleanup method."
requirements-completed: [PUB-01, PUB-03, PUB-04, SEC-02]
coverage:
  - id: D1
    description: Protected candidate-publication workflow uses exact approved action commits, candidate-only admission output, and environment-gated late token minting.
    requirement: SEC-02
    verification:
      - kind: integration
        ref: ".tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_security.py -k workflow"
        status: pass
    human_judgment: false
  - id: D2
    description: Opt-in causal canary records a same-installation positive Draft/reviewer observation and bounded platform-denial probes without cleanup authority.
    requirement: PUB-04
    verification:
      - kind: integration
        ref: ".tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py tests/test_publication_security.py -x"
        status: pass
    human_judgment: true
    rationale: "Real catalog ruleset and protected-environment behavior require separately authorized live evidence."
metrics:
  tasks: 2
  files: 3
  completed: 2026-07-24
status: complete
---

# Phase 04 Plan 09: Protected Workflow and Live Canary Summary

**Immutable, environment-gated Draft publication with a candidate-only handoff and an opt-in causal GitHub platform canary.**

## Accomplishments

- Added a `workflow_dispatch`-only publication workflow with `contents: read`, the two Gate A4-approved immutable action SHAs, and no mutable action tags.
- Split unprivileged candidate admission from the protected `skillscout-catalog-publish` job; the protected job revalidates all ten candidate fields, rejects team reviewers, and derives authority-bound admission before minting the catalog-scoped token.
- Added a test-only, fully opt-in canary runner that proves the positive Draft/reviewer observation and bounded default-ref, merge, ruleset, unauthorized-resource, and secret-resource negative probes through one installation identity.

## Task Commits

1. **Task 1: Create exact protected publication workflow** — `808923a` (test), `f9e4207` (feat)
2. **Task 2: Implement causal positive and negative live probes** — `aec7910` (test), `c82bcb4` (feat)

## Verification

- `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_security.py -k workflow` — 3 passed.
- `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py tests/test_publication_security.py -x` — 14 passed, 2 skipped (the live path remains opt-in).
- Parsed `.github/workflows/publish-candidate.yml` with the local Ruby YAML parser and confirmed only `admit` and `publish` jobs exist.

## Files Created/Modified

- `.github/workflows/publish-candidate.yml` — protected candidate-only Draft publication workflow.
- `tests/test_publication_security.py` — immutable action, job-boundary, and forbidden-surface workflow contract.
- `tests/test_publication_live_canary.py` — opt-in causal canary transport and production-surface negative checks.

## Decisions Made

- Keep App credentials and protected catalog variables exclusively in the protected publish job after candidate revalidation.
- Preserve the derived `publication_intent_digest` and `admission_digest` as job-local protected values; they are never unprivileged outputs or equality inputs.
- Do not treat ready-for-review as a platform denial: the Pull requests write token may be capable outside SkillScout, so the code, CLI, and workflow surface remains closed and human-only.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. The live runner intentionally skips unless every protected opt-in variable is supplied; this is its security boundary, not a stub.

## Threat Flags

None. The workflow's GitHub App token and the test-only canary transport are the planned trust-boundary surfaces and are covered by the plan threat model.

## Self-Check: PASSED

- Verified `.github/workflows/publish-candidate.yml`, `tests/test_publication_security.py`, and `tests/test_publication_live_canary.py` exist.
- Verified task commits `808923a`, `f9e4207`, `aec7910`, and `c82bcb4` exist.
- Verified the orchestrator-owned `.planning/STATE.md` remains unstaged and was not modified by this plan.
