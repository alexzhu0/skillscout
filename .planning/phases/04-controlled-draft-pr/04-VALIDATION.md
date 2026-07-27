---
phase: 4
slug: controlled-draft-pr
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-24
completed: 2026-07-27
---

# Phase 4 — Exact Validation Contract

All commands run from the repository root. Offline commands use the repository-local locked uv binary. The live command in task `04-10-01` is historical Gate B4 evidence and is not part of the repeatable offline release chain.

| Property | Value |
|---|---|
| **Framework** | pytest 9.1.x with injected transports and bounded fixtures |
| **Full suite command** | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` |
| **Static quality command** | `.tools/uv-0.11.29/bin/uv run --locked ruff check .` |
| **Network policy** | Offline except the separately authorized and completed Gate B4 canary |
| **Human gates** | Gate A4 exact action identity; Gate B4 live governance/canary evidence |

## Exact Per-Task Verification Map

| Task ID | Plan | Wave | Depends On | Requirement | Automated Command | Evidence Path | Human Gate | Status | Result |
|---|---|---:|---|---|---|---|---|---|---|
| 04-01-01 | 04-01 | 1 | — | PUB-01, PUB-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_publication_domain.py` | tests/test_publication_domain.py | — | green | collected |
| 04-01-02 | 04-01 | 1 | — | PUB-03, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_publication_security.py` | tests/test_publication_security.py | — | green | collected |
| 04-02-01 | 04-02 | 1 | — | PUB-01 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_github_publish_adapter.py` | tests/fixtures/github_publish/, tests/test_github_publish_adapter.py | — | green | collected |
| 04-02-02 | 04-02 | 1 | — | PUB-05 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_publication_recovery.py` | tests/test_publication_recovery.py | — | green | collected |
| 04-02-03 | 04-02 | 1 | — | PUB-04 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py` | tests/test_publication_live_canary.py | — | green | offline skip boundary |
| 04-03-01 | 04-03 | 2 | 04-01 | PUB-01, PUB-02, PUB-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_domain.py -k 'identity or grammar or marker'` | src/skillscout/domain/publication.py, tests/test_publication_domain.py | — | green | focused |
| 04-03-02 | 04-03 | 2 | 04-01 | PUB-01, PUB-05 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_domain.py -k admission` | src/skillscout/domain/publication.py, tests/test_publication_domain.py | — | green | focused |
| 04-03-03 | 04-03 | 2 | 04-01 | PUB-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_domain.py` | src/skillscout/domain/publication.py, tests/test_publication_domain.py | — | green | focused |
| 04-04-01 | 04-04 | 3 | 04-02, 04-03 | PUB-01, PUB-05 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_github_publish_adapter.py -k 'catalog or reconcile or provider'` | src/skillscout/adapters/github_publish.py | — | green | focused |
| 04-04-02 | 04-04 | 3 | 04-02, 04-03 | PUB-03, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_github_publish_adapter.py tests/test_publication_security.py -x` | src/skillscout/adapters/github_publish.py, tests/test_publication_security.py | — | green | focused |
| 04-05-01 | 04-05 | 4 | 04-03, 04-04 | PUB-01 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_recovery.py -k state` | src/skillscout/adapters/publication_state.py | — | green | focused |
| 04-05-02 | 04-05 | 4 | 04-03, 04-04 | PUB-05 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_recovery.py -k reconcile` | src/skillscout/application/publication.py | — | green | focused |
| 04-05-03 | 04-05 | 4 | 04-03, 04-04 | PUB-01, PUB-05 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_recovery.py` | src/skillscout/application/publication.py, tests/test_publication_recovery.py | — | green | focused |
| 04-06-01 | 04-06 | 5 | 04-05 | PUB-01, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_security.py -k 'config or token_order or secret'` | src/skillscout/application/publication.py | — | green | focused |
| 04-06-02 | 04-06 | 5 | 04-05 | PUB-01, PUB-02, PUB-05 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_cli_validate_skill.py -k 'publish or admission_handoff'` | src/skillscout/cli.py | — | green | focused |
| 04-06-03 | 04-06 | 5 | 04-05 | PUB-03, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_cli_security.py tests/test_publication_security.py tests/test_cli_validate_skill.py -x` | src/skillscout/cli.py | — | green | focused |
| 04-07-01 | 04-07 | 1 | — | PUB-04 | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py` | config/supply-chain/phase4-actions-audit.json | — | green | exact audit |
| 04-07-02 | 04-07 | 1 | — | SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase4_action_audit.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py` | tools/verify_phase4_action_audit.py, tests/test_phase4_action_audit.py | — | green | mutation tested |
| 04-08-01 | 04-08 | 2 | 04-07 | PUB-04, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py` | .planning/phases/04-controlled-draft-pr/04-08-SUMMARY.md | Gate A4 | green | human approved |
| 04-09-01 | 04-09 | 6 | 04-06, 04-08 | PUB-01, PUB-04, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_security.py -k workflow` | .github/workflows/publish-candidate.yml | Gate A4 | green | focused |
| 04-09-02 | 04-09 | 6 | 04-06, 04-08 | PUB-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py tests/test_publication_security.py -x` | tests/test_publication_live_canary.py | — | green | offline boundary |
| 04-10-01 | 04-10 | 7 | 04-09 | PUB-01, PUB-03, PUB-04, PUB-05, SEC-02 | `SKILLSCOUT_LIVE_CANARY=1 .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py -x` | .planning/phases/04-controlled-draft-pr/04-10-SUMMARY.md | Gate B4 | green | human reviewed and cleaned |
| 04-11-01 | 04-11 | 8 | 04-10 | PUB-01, PUB-02, PUB-03, PUB-04, PUB-05, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase4_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_validation_map.py` | tools/verify_phase4_validation_map.py, tests/test_phase4_validation_map.py | — | green | mutation tested |
| 04-11-02 | 04-11 | 8 | 04-10 | PUB-01, PUB-02, PUB-03, PUB-04, PUB-05, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase4_acceptance_tool.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_acceptance.py` | tools/verify_phase4_acceptance.py, tests/test_phase4_acceptance_tool.py | — | green | mutation tested |
| 04-11-03 | 04-11 | 8 | 04-10 | PUB-01, PUB-02, PUB-03, PUB-04, PUB-05, SEC-02 | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py && .tools/uv-0.11.29/bin/uv run --locked ruff check . && .tools/uv-0.11.29/bin/uv run --locked pytest -q && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_acceptance.py` | 04-11-SUMMARY.md | — | green | final chain |

## Requirement Inverse Map

| Requirement | Validation evidence | Prohibition evidence |
|---|---|---|
| PUB-01 | Positive: 04-01-01, 04-02-01, 04-03-01, 04-03-02, 04-04-01, 04-05-01, 04-05-03, 04-06-01, 04-06-02, 04-09-01, 04-10-01, 04-11-01, 04-11-02, 04-11-03 | Prohibition: closed catalog/ref/path operations; exact manifest bytes and deletions; team configuration rejected |
| PUB-02 | Positive: 04-01-01, 04-03-01, 04-03-03, 04-06-02, 04-11-01, 04-11-02, 04-11-03 | Prohibition: deterministic body and marker cannot accept caller-supplied text or protected authority from an unprivileged job |
| PUB-03 | Positive: 04-01-02, 04-03-01, 04-04-02, 04-06-03, 04-09-02, 04-10-01, 04-11-01, 04-11-02, 04-11-03 | Prohibition: no merge, approval, ready, GraphQL, ruleset mutation, default-ref mutation, timeline, or generic request surface |
| PUB-04 | Positive: 04-02-03, 04-07-01, 04-08-01, 04-09-01, 04-10-01, 04-11-01, 04-11-02, 04-11-03 | Prohibition: candidate-only cross-job output; protected-local intent/admission derivation; scoped live platform denials |
| PUB-05 | Positive: 04-02-02, 04-03-02, 04-04-01, 04-05-02, 04-05-03, 04-06-02, 04-10-01, 04-11-01, 04-11-02, 04-11-03 | Prohibition: human/malformed lineage and removed reviewer ambiguity fail closed; no repeated notification or force update |
| SEC-02 | Positive: 04-01-02, 04-04-02, 04-06-01, 04-06-03, 04-07-02, 04-08-01, 04-09-01, 04-10-01, 04-11-01, 04-11-02, 04-11-03 | Prohibition: no secret persistence/logging, mutable action reference, candidate shell interpolation, or authority-dependent cross-job digest |

## Human Gate Evidence

- Gate A4 is non-auto-approvable. It approved `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` and `actions/create-github-app-token@67018539274d69449ef7c8cde82c3ff073ffe3b5` at audit digest `d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622`.
- Gate B4 is non-auto-approvable. The human-reviewed evidence records workflow SHA-256 `99fded78508bd4f20303cb201942f7b22b2be10c6b65042909835789853c2a09`, ruleset digest `sha256:e58e74403d890296e44105cb60b42abffe522f11d169884d6d51f285b63948b5`, stable Draft/reviewer identities, scoped denials, unchanged default SHA, and separate-authority cleanup.

## Exact Final Locked Release Chain

`.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py && .tools/uv-0.11.29/bin/uv run --locked ruff check . && .tools/uv-0.11.29/bin/uv run --locked pytest -q && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_acceptance.py`

The locked project does not contain mypy, so no mypy gate is claimed. The chain performs no live canary, cleanup, approval, ready transition, merge, or other remote mutation.

## Actual Results

Task 04-11 records the measured 2026-07-27 results in `04-11-SUMMARY.md`; no fabricated historical count is used here.

## Validation Sign-Off

- [x] Every one of 25 planned tasks appears exactly once with its plan, wave, dependency, requirements, exact command, evidence path, and human gate.
- [x] Every requirement has positive and prohibition evidence.
- [x] Wave 0 files and fixtures exist.
- [x] Gate A4 and Gate B4 evidence is immutable and human-reviewed.
- [x] The final release chain is repository-local, locked, offline, and failure-preserving.
- [x] `nyquist_compliant: true` follows independent validation and completed live human-gate evidence.

**Approval:** green
