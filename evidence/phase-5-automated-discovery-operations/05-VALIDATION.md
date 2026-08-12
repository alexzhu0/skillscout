---
phase: 05
slug: automated-discovery-operations
status: complete
nyquist_compliant: true
wave_0_complete: true
execution_status: complete
hosted_gate_b4_status: approved
created: 2026-07-27
updated: 2026-07-28
---

# Phase 05 — Validation Strategy

`nyquist_compliant: true` records complete planning coverage. Execution completion is established separately by the Plan 05-10 release chain and `05-VERIFICATION.md`; hosted approval is established by the exact Gate B4 evidence and approval records below. Phase 6 real-repository acceptance is not claimed.

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest 9.1.1 |
| Config file | `pyproject.toml` |
| Locked runner | `.tools/uv-0.11.29/bin/uv run --locked` |
| Full suite | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` |
| Static checks | `.tools/uv-0.11.29/bin/uv run --locked ruff check .` |

## Exact Per-Task Verification Map

| Task | Plan | Wave | Dependencies | Requirements | Automated verification | Artifacts | Evidence |
|---|---|---:|---|---|---|---|---|
| 05-01-01 | 05-01 | 1 | — | DISC-01, DISC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_domain.py -k "query or budget or authority" -x` | config/discovery-queries-v1.json, src/skillscout/domain/discovery.py, tests/test_discovery_domain.py | Query/budget authority contracts pass |
| 05-01-02 | 05-01 | 1 | — | DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_domain.py -x` | src/skillscout/domain/discovery.py, tests/test_discovery_domain.py | Observation/terminal/rebuild contracts pass |
| 05-02-01 | 05-02 | 1 | — | DISC-01, DISC-02, DISC-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_github_search.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q -rxX tests/test_github_search.py -k "page or duplicate or incomplete" -x` | tests/fixtures/github_search/page_one.json, tests/fixtures/github_search/page_duplicates.json, tests/fixtures/github_search/page_incomplete.json, tests/recorded_transport.py, tests/test_github_search.py | Named Search nodes strict-xfail; all other nodes pass |
| 05-02-02 | 05-02 | 1 | — | DISC-02, DISC-03, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_github_search.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q -rxX tests/test_github_search.py -k "hostile or oversized or rate or error" -x` | tests/fixtures/github_search/error_matrix.json, tests/test_github_search.py | Hostile/failure matrix is collected and bounded |
| 05-03-01 | 05-03 | 1 | — | DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_operations_state.py tests/test_state_branch.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q -rxX tests/test_operations_state.py tests/test_state_branch.py -x` | tests/fixtures/state_branch/valid_state.json, tests/fixtures/state_branch/conflict_matrix.json, tests/test_operations_state.py, tests/test_state_branch.py | Only named operations/store/state-branch capabilities strict-xfail |
| 05-03-02 | 05-03 | 1 | — | DISC-01, DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py tests/test_discovery_workflow.py tests/test_discovery_security.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q -rxX tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py tests/test_discovery_workflow.py tests/test_discovery_security.py -x` | tests/test_discovery_application.py, tests/test_discovery_publication_handoff.py, tests/test_semantic_durability.py, tests/test_discovery_workflow.py, tests/test_discovery_security.py | Only named discovery/barrier/handoff/workflow capabilities strict-xfail |
| 05-04-01 | 05-04 | 2 | 05-01, 05-02 | DISC-01, DISC-02, DISC-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_github_search.py -k "page or duplicate or incomplete" tests/test_github_adapter.py -x` | src/skillscout/adapters/github.py, tests/test_github_search.py | Search page projection passes |
| 05-04-02 | 05-04 | 2 | 05-01, 05-02 | DISC-02, DISC-03, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_github_search.py tests/test_github_adapter.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/github.py tests/test_github_search.py` | src/skillscout/adapters/github.py, tests/test_github_search.py | Search failure/resource/security matrix passes |
| 05-05-01 | 05-05 | 2 | 05-01, 05-03 | DISC-02, DISC-03, OPS-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_operations_state.py -k "reservation or budget or ordinal or refund" -x` | src/skillscout/adapters/operations_state.py, tests/test_operations_state.py | Non-refundable reservation ledger passes |
| 05-05-02 | 05-05 | 2 | 05-01, 05-03 | DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_operations_state.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/operations_state.py tests/test_operations_state.py` | src/skillscout/adapters/operations_state.py, tests/test_operations_state.py | Discovery-store export/integrity passes |
| 05-06-01 | 05-06 | 2 | 05-01, 05-03 | OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_branch.py -k "restore or tree or object or rollback or absent" -x` | src/skillscout/adapters/state_branch.py, tests/test_state_branch.py | Exact state restore validation passes |
| 05-06-02 | 05-06 | 2 | 05-01, 05-03 | OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_branch.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/state_branch.py tests/test_state_branch.py` | src/skillscout/adapters/state_branch.py, tests/test_state_branch.py | Parent-bound CAS/reread/conflict checks pass |
| 05-07-01 | 05-07 | 6 | 05-04, 05-12, 05-13, 05-14 | DISC-01, DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_application.py -k "search or reservation or resume or business" -x` | src/skillscout/application/discovery.py, src/skillscout/application/ports.py, tests/test_discovery_application.py | Unprotected discovery reaches independent Phase 3 outcomes |
| 05-07-02 | 05-07 | 6 | 05-04, 05-12, 05-13, 05-14 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_application.py tests/test_discovery_security.py -k "unknown or handoff or forbidden or publisher or eligible or health" -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/application/discovery.py tests/test_discovery_application.py tests/test_discovery_security.py` | src/skillscout/application/discovery.py, tests/test_discovery_application.py, tests/test_discovery_security.py | Discovery ends at closed handoff and cannot construct publication |
| 05-08-01 | 05-08 | 7 | 05-07 | DISC-01, DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_application.py tests/test_discovery_security.py -k "bootstrap or config or credential or factory" -x` | src/skillscout/bootstrap.py, tests/test_discovery_application.py, tests/test_discovery_security.py | Discovery bootstrap has no catalog/Phase 4 authority |
| 05-08-02 | 05-08 | 7 | 05-07 | DISC-01, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_discovery_security.py tests/test_cli_security.py tests/test_publication_security.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/bootstrap.py src/skillscout/cli.py` | src/skillscout/bootstrap.py, src/skillscout/cli.py, tests/test_discovery_application.py, tests/test_discovery_publication_handoff.py, tests/test_discovery_security.py | Exact-commit re-admission precedes token and publication construction |
| 05-09-01 | 05-09 | 8 | 05-08 | DISC-01, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_workflow.py tests/test_discovery_security.py -x` | .github/workflows/discover.yml, tests/test_discovery_workflow.py, tests/test_discovery_security.py | Separate workflow entry points and authority zones pass static audit |
| 05-09-02 | 05-09 | 8 | 05-08 | DISC-01, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_workflow.py tests/test_discovery_security.py -x` | .github/workflows/discover.yml, tests/test_discovery_workflow.py | Hosted concurrency and fresh exact Gate B4 are separately approved |
| 05-10-01 | 05-10 | 9 | 05-09 | DISC-01, DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase5_acceptance.py -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_acceptance.py` | tools/verify_phase5_acceptance.py, tests/test_phase5_acceptance.py | Independent acceptance inspector passes |
| 05-10-02 | 05-10 | 9 | 05-09 | DISC-01, DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase5_validation_map.py tests/test_phase5_acceptance.py tests/test_discovery_domain.py tests/test_github_search.py tests/test_operations_state.py tests/test_state_branch.py tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py tests/test_discovery_workflow.py tests/test_discovery_security.py tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_state_integrity.py tests/test_pipeline_resume.py tests/test_phase3_pipeline.py tests/test_publication_recovery.py tests/test_publication_security.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check . && .tools/uv-0.11.29/bin/uv run --locked pytest -q && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_acceptance.py` | tools/verify_phase5_validation_map.py, tests/test_phase5_validation_map.py, .planning/phases/05-automated-discovery-operations/05-VALIDATION.md | Full release chain and map audit pass |
| 05-11-01 | 05-11 | 2 | 05-01, 05-03 | DISC-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py -x` | src/skillscout/adapters/semantic_provider.py, tests/test_semantic_provider.py | Provider-neutral disposition contract passes |
| 05-11-02 | 05-11 | 2 | 05-01, 05-03 | DISC-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/semantic_provider.py src/skillscout/adapters/openai_extract.py src/skillscout/adapters/openai_generate.py src/skillscout/adapters/openai_review.py` | src/skillscout/adapters/openai_extract.py, src/skillscout/adapters/openai_generate.py, src/skillscout/adapters/openai_review.py, tests/test_openai_extract.py, tests/test_openai_generate.py, tests/test_openai_review.py | Both providers/all three stages classify closed outcomes |
| 05-12-01 | 05-12 | 3 | 05-05, 05-06 | OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_integrity.py tests/test_publication_recovery.py -k "export or import or rebuild or snapshot or integrity" -x` | src/skillscout/adapters/state.py, src/skillscout/adapters/publication_state.py, tests/test_state_integrity.py, tests/test_publication_recovery.py | Pipeline/publication store-owned seams pass |
| 05-12-02 | 05-12 | 3 | 05-05, 05-06 | OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_operations_state.py tests/test_state_branch.py tests/test_state_integrity.py tests/test_publication_recovery.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/state.py src/skillscout/adapters/operations_state.py src/skillscout/adapters/publication_state.py` | src/skillscout/adapters/operations_state.py, tests/test_operations_state.py, tests/test_state_branch.py | Exact three-DB bundle/rebuild/equality passes |
| 05-13-01 | 05-13 | 5 | 05-11, 05-14 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_pipeline_resume.py tests/test_openai_extract.py -k "semantic or extractor or retry or unknown or resume" -x` | src/skillscout/application/pipeline.py, tests/test_pipeline_resume.py | Extractor is barrier-gated with zero ambiguous replay |
| 05-13-02 | 05-13 | 5 | 05-11, 05-14 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase3_pipeline.py tests/test_openai_generate.py tests/test_openai_review.py -k "semantic or generator or reviewer or retry or unknown or resume" -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/application/pipeline.py src/skillscout/application/phase3.py` | src/skillscout/application/phase3.py, tests/test_phase3_pipeline.py | Generator/Reviewer are barrier-gated with zero ambiguous replay |
| 05-14-01 | 05-14 | 4 | 05-06, 05-11, 05-12 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_durability.py -k "contract or receipt or transition or sanitize" -x` | src/skillscout/application/ports.py, tests/test_semantic_durability.py | Barrier contract and receipt authority pass |
| 05-14-02 | 05-14 | 4 | 05-06, 05-11, 05-12 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_durability.py tests/test_state_branch.py tests/test_state_integrity.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/application/ports.py src/skillscout/adapters/state_branch.py tests/test_semantic_durability.py` | src/skillscout/adapters/state_branch.py, tests/test_semantic_durability.py | Three-store CAS/reread and crash matrix passes |

## Requirement Inverse Map

| Requirement | Positive task coverage | Prohibition evidence |
|---|---|---|
| DISC-01 | 05-01-01, 05-02-01, 05-03-02, 05-04-01, 05-07-01, 05-08-01, 05-08-02, 05-09-01, 05-09-02, 05-10-01, 05-10-02 | Prohibition: no runtime query widening, missing trigger, catalog authority in discovery, or mutable workflow identity |
| DISC-02 | 05-01-01, 05-02-01, 05-02-02, 05-03-01, 05-03-02, 05-04-01, 05-04-02, 05-05-01, 05-07-01, 05-07-02, 05-08-01, 05-10-01, 05-10-02, 05-11-01, 05-11-02, 05-13-01, 05-13-02, 05-14-01, 05-14-02 | Prohibition: no 101st repository, 21st semantic reservation, refund, or ambiguous replay |
| DISC-03 | 05-01-02, 05-02-01, 05-02-02, 05-03-01, 05-04-01, 05-04-02, 05-05-01, 05-05-02, 05-07-01, 05-08-01, 05-10-01, 05-10-02 | Prohibition: no incomplete, provider-prose, arbitrary-header, or unbound pagination facts |
| OPS-02 | 05-01-02, 05-03-01, 05-03-02, 05-05-01, 05-05-02, 05-06-01, 05-06-02, 05-07-01, 05-07-02, 05-08-01, 05-08-02, 05-09-01, 05-09-02, 05-10-01, 05-10-02, 05-12-01, 05-12-02, 05-13-01, 05-13-02, 05-14-01, 05-14-02 | Prohibition: no fourth store, force update, stale reread, cache authority, or state-object pruning |
| OPS-03 | 05-01-02, 05-02-02, 05-03-01, 05-03-02, 05-04-02, 05-05-02, 05-06-01, 05-06-02, 05-07-01, 05-07-02, 05-08-01, 05-08-02, 05-09-01, 05-09-02, 05-10-01, 05-10-02, 05-11-01, 05-11-02, 05-12-01, 05-12-02, 05-13-01, 05-13-02, 05-14-01, 05-14-02 | Prohibition: no raw source, provider body, secret, header, environment dump, or unallowlisted path |

## Locked Prohibition Evidence

| Decision | Independently checked boundary |
|---|---|
| D-01 | Fixed reviewed query set and daily/manual triggers only |
| D-02 | Numeric repository ID is deduplication authority |
| D-03 | Durable literal 100/20 reservations are non-refundable |
| D-04 | Unknown semantic outcomes quarantine without replay |
| D-05 | Exact three-store JSON/SQLite rebuild and equality |
| D-06 | Parent-bound non-force CAS with exact reread |
| D-07 | Fixed shared non-cancelling production concurrency |
| D-08 | Allowlisted state, handoff, logs and outputs only |
| D-09 | No state-object pruning |

Immutable Actions: `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` and `actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1`.

## Hosted Evidence Identity

- Gate B4 evidence SHA-256: `1ee162ea47cf86b7faec68bfba37b7a9b2af3b25472066312b43c4a5e4414cdd`
- Human approval SHA-256: `e1c6687d4c85c4881a433d03da8d66168915c8e316e4817e1415835b52e3ba72`
- Discover workflow SHA-256: `8157cb686b9bf18bfa800811b1fe1529ed9a15ec371fe36ec1708233052b7cfd`
- Publish workflow SHA-256: `96ce9f39db49ce647a88b83ec4db3cb0135e5cf51c1eb2f11961cfd243b23cf0`
- Canary workflow SHA-256: `9c59cd9822eecec913f82d24c7880a443ba9416795b8996c6201f33c4df5805d`

Concurrency runs `30324567231` and `30324568742` are scheduling evidence only. Gate B4 credit comes from canary run `30327184915`, the exact workflow/identity bindings above, causal denials, and separate human cleanup.

## Exact Release Chain

The release command is intentionally duplicated from Task 05-10-02 and is executed without partial credit:

`.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase5_validation_map.py tests/test_phase5_acceptance.py tests/test_discovery_domain.py tests/test_github_search.py tests/test_operations_state.py tests/test_state_branch.py tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py tests/test_discovery_workflow.py tests/test_discovery_security.py tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_state_integrity.py tests/test_pipeline_resume.py tests/test_phase3_pipeline.py tests/test_publication_recovery.py tests/test_publication_security.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check . && .tools/uv-0.11.29/bin/uv run --locked pytest -q && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_acceptance.py`

## Validation Sign-Off

- [x] All 14 plans, 28 tasks, waves, dependencies, commands and artifact sets are mapped exactly.
- [x] All five requirement inverse maps are complete and mutation-tested.
- [x] D-01 through D-09 and exact hosted evidence identities are pinned separately.
- [x] Wave 0 tests were executed and all named production capabilities are green.
- [x] Plan 05-10 release-chain execution is recorded in `05-10-SUMMARY.md`.

**Validation result:** Nyquist-compliant, exact release chain passed, hosted Gate B4 approved, and Phase 05 independently verified.
