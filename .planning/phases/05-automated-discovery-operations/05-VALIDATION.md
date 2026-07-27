---
phase: 05
slug: automated-discovery-operations
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-27
updated: 2026-07-27
---

# Phase 05 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest 9.1.1 |
| Config file | `pyproject.toml` |
| Locked runner | `.tools/uv-0.11.29/bin/uv run --locked` |
| Full suite | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` |
| Static checks | `.tools/uv-0.11.29/bin/uv run --locked ruff check .` |

Wave 0 uses collection-first strict expected failures. Syntax, imports, collection, fixture validity, dependency problems, unrelated failures and unexpected passes fail immediately. Production plans turn only the named missing-capability nodes green.

## Exact Per-Task Verification Map

| Task | Wave | Requirements | Automated verification | Expected state after task |
|---|---:|---|---|---|
| 05-01-01 | 1 | DISC-01, DISC-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_domain.py -k "query or budget or authority" -x` | Query/budget authority contracts pass |
| 05-01-02 | 1 | DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_domain.py -x` | Observation/terminal/rebuild contracts pass |
| 05-02-01 | 1 | DISC-01, DISC-02, DISC-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_github_search.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q -rxX tests/test_github_search.py -k "page or duplicate or incomplete" -x` | Named Search nodes strict-xfail; all other nodes pass |
| 05-02-02 | 1 | DISC-02, DISC-03, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_github_search.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q -rxX tests/test_github_search.py -k "hostile or oversized or rate or error" -x` | Hostile/failure matrix is collected and bounded |
| 05-03-01 | 1 | DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_operations_state.py tests/test_state_branch.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q -rxX tests/test_operations_state.py tests/test_state_branch.py -x` | Only named operations/store/state-branch capabilities strict-xfail |
| 05-03-02 | 1 | DISC-01, DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest --collect-only -q tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py tests/test_discovery_workflow.py tests/test_discovery_security.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q -rxX tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py tests/test_discovery_workflow.py tests/test_discovery_security.py -x` | Only named discovery/barrier/handoff/workflow capabilities strict-xfail |
| 05-04-01 | 2 | DISC-01, DISC-02, DISC-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_github_search.py -k "page or duplicate or incomplete" tests/test_github_adapter.py -x` | Search page projection passes |
| 05-04-02 | 2 | DISC-02, DISC-03, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_github_search.py tests/test_github_adapter.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/github.py tests/test_github_search.py` | Search failure/resource/security matrix passes |
| 05-05-01 | 2 | DISC-02, DISC-03, OPS-02 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_operations_state.py -k "reservation or budget or ordinal or refund" -x` | Non-refundable reservation ledger passes |
| 05-05-02 | 2 | DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_operations_state.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/operations_state.py tests/test_operations_state.py` | Discovery-store export/integrity passes |
| 05-06-01 | 2 | OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_branch.py -k "restore or tree or object or rollback or absent" -x` | Exact state restore validation passes |
| 05-06-02 | 2 | OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_branch.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/state_branch.py tests/test_state_branch.py` | Parent-bound CAS/reread/conflict checks pass |
| 05-11-01 | 2 | DISC-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py -x` | Provider-neutral disposition contract passes |
| 05-11-02 | 2 | DISC-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/semantic_provider.py src/skillscout/adapters/openai_extract.py src/skillscout/adapters/openai_generate.py src/skillscout/adapters/openai_review.py` | Both providers/all three stages classify closed outcomes |
| 05-12-01 | 3 | OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_state_integrity.py tests/test_publication_recovery.py -k "export or import or rebuild or snapshot or integrity" -x` | Pipeline/publication store-owned seams pass |
| 05-12-02 | 3 | OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_operations_state.py tests/test_state_branch.py tests/test_state_integrity.py tests/test_publication_recovery.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/adapters/state.py src/skillscout/adapters/operations_state.py src/skillscout/adapters/publication_state.py` | Exact three-DB bundle/rebuild/equality passes |
| 05-14-01 | 4 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_durability.py -k "contract or receipt or transition or sanitize" -x` | Barrier contract and receipt authority pass |
| 05-14-02 | 4 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_semantic_durability.py tests/test_state_branch.py tests/test_state_integrity.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/application/ports.py src/skillscout/adapters/state_branch.py tests/test_semantic_durability.py` | Three-store CAS/reread and crash matrix passes |
| 05-13-01 | 5 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_pipeline_resume.py tests/test_openai_extract.py -k "semantic or extractor or retry or unknown or resume" -x` | Extractor is barrier-gated with zero ambiguous replay |
| 05-13-02 | 5 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase3_pipeline.py tests/test_openai_generate.py tests/test_openai_review.py -k "semantic or generator or reviewer or retry or unknown or resume" -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/application/pipeline.py src/skillscout/application/phase3.py` | Generator/Reviewer are barrier-gated with zero ambiguous replay |
| 05-07-01 | 6 | DISC-01, DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_application.py -k "search or reservation or resume or business" -x` | Unprotected discovery reaches independent Phase 3 outcomes |
| 05-07-02 | 6 | DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_application.py tests/test_discovery_security.py -k "unknown or handoff or forbidden or publisher or eligible or health" -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/application/discovery.py tests/test_discovery_application.py tests/test_discovery_security.py` | Discovery ends at closed handoff and cannot construct publication |
| 05-08-01 | 7 | DISC-01, DISC-02, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_application.py tests/test_discovery_security.py -k "bootstrap or config or credential or factory" -x` | Discovery bootstrap has no catalog/Phase 4 authority |
| 05-08-02 | 7 | DISC-01, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_discovery_security.py tests/test_cli_security.py tests/test_publication_security.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/bootstrap.py src/skillscout/cli.py` | Exact-commit re-admission precedes token and publication construction |
| 05-09-01 | 8 | DISC-01, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_workflow.py tests/test_discovery_security.py -x` | Separate workflow entry points and authority zones pass static audit |
| 05-09-02 | 8 | DISC-01, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_workflow.py tests/test_discovery_security.py -x` plus blocking human check | Hosted concurrency and fresh exact Gate B4 are separately approved |
| 05-10-01 | 9 | DISC-01, DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase5_acceptance.py -x && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_acceptance.py` | Independent acceptance inspector passes |
| 05-10-02 | 9 | DISC-01, DISC-02, DISC-03, OPS-02, OPS-03 | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase5_validation_map.py tests/test_phase5_acceptance.py tests/test_discovery_domain.py tests/test_github_search.py tests/test_operations_state.py tests/test_state_branch.py tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py tests/test_discovery_workflow.py tests/test_discovery_security.py tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_state_integrity.py tests/test_pipeline_resume.py tests/test_phase3_pipeline.py tests/test_publication_recovery.py tests/test_publication_security.py -x && .tools/uv-0.11.29/bin/uv run --locked ruff check . && .tools/uv-0.11.29/bin/uv run --locked pytest -q && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_acceptance.py` | Full release chain and map audit pass |

## Mandatory Scenario Matrix

- Search: pagination, cross-query duplicates, rename by numeric ID, incomplete results, hostile metadata/links, rate limits and malformed/oversized responses.
- Budgets: exact 100/20 boundaries, non-refundable reservations, tampered counters, resume and completed reuse.
- Semantic durability: OpenAI and DeepSeek across Extractor, Generator and Reviewer; crash immediately before/after attempt-start and result barriers; decided, confirmed-retryable and outcome-unknown results; every sync failure blocks request/retry/terminal; restart produces zero ambiguous replay.
- Composition: one repository reservation supports 0–3 independent workflow authorities and mixed Phase 3 outcomes.
- Closed handoff: unprotected discovery ends after Phase 3, persists bounded eligible locators/authorities, and cannot construct Phase 4 or a publisher.
- Protected publication: exact state commit reread, three-store validation and canonical admission derivation precede token minting; minting precedes `PublicationApplication` construction/invocation.
- State: exact three-DB snapshot, integrity/schema/root verification, store-owned JSON rebuild, missing/swapped objects, rollback, path/mode rejection and killed writer.
- Workflow/security: separate entry points, fixed concurrency, minimum permissions, credential zones, fresh exact Gate B4, no candidate shell interpolation and no secret/raw-source persistence.

## Wave 0 Requirements

- [ ] Create all named Phase 5 test modules and bounded recorded fixtures.
- [ ] Add strict expected failures only for named missing production capabilities.
- [ ] Add interruption seams around both semantic barriers and the exact publication handoff.
- [ ] Confirm every Wave 0 module collects with no syntax/import/dependency error.

## Manual-Only Verification

Task 05-09-02 is the only blocking human verification. It separately records:

1. Hosted fixed-group/non-cancel concurrency and credential-zone behavior.
2. A fresh Gate B4 bound to exact `discover.yml` bytes and reviewed App/catalog/ruleset/environment/reviewer/installation identities.

The concurrency canary cannot satisfy Gate B4. The prior Phase 4 Gate B4 remains evidence only for its unchanged workflow and identities.

## Validation Sign-Off

- [x] Every implementation task has an exact automated verification row.
- [x] Every requirement appears in automated task coverage.
- [x] Wave 0 creates every missing Phase 5 test/fixture seam.
- [x] No three consecutive implementation tasks lack automated feedback.
- [x] Separate discovery/publication authority and three-store semantic barriers have dedicated negative/crash tests.
- [ ] Wave 0 tests executed and strict expected failures confirmed.
- [ ] Full release chain and hosted evidence pass during execution.

**Planning approval:** Nyquist-compliant; execution evidence pending.
