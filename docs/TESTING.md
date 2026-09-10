# Testing SkillScout

## Test framework and setup

SkillScout uses Python `>=3.13,<3.14` and pytest `9.1.1`. The development dependencies and their exact versions are locked in `pyproject.toml` and `uv.lock`; use the repository-pinned uv executable so the environment is reproduced from that lock.

From the repository root, install or synchronize the locked development environment:

```bash
.tools/uv-0.11.29/bin/uv sync --locked
```

Pytest is configured in `pyproject.toml` to discover tests under `tests/` and reject unknown configuration or markers with `--strict-config` and `--strict-markers`.

The ordinary suite is offline by default. GitHub and OpenAI HTTP behavior is represented by frozen JSON fixtures and `httpx.MockTransport`; `tests/recorded_transport.py` rejects any request for which no response was recorded. Tests that exercise CLI dry runs can also use the `outbound_socket_sentinel` fixture from `tests/conftest.py`, which fails on attempted socket connections.

The repository also includes independent, read-only release inspectors:

- `tools/verify_phase5_validation_map.py` checks the exact validation map, release command, requirement coverage, pinned Action identities, and hosted-evidence identities.
- `tools/verify_phase5_acceptance.py` checks the implemented discovery limits, semantic durability barriers, three-store recovery boundary, protected publication handoff, workflow bytes, and hosted Gate B4 evidence.
- `tools/verify_phase6_source_execution.py`, `tools/verify_phase6_validation_map.py`, and `tools/verify_phase6_acceptance.py` check the closed Phase 6 source-execution boundary, requirement ownership, and acceptance registry. They do not dispatch Actions, read credentials, call a model, or publish.

All of these inspectors use only the Python standard library. Their mutation suites assert that they do not import the project package, network clients, pytest, or subprocess-based execution authority.

## Running tests

The local export boundary is covered by `tests/test_cli_export_candidates.py`:
canonical descriptors round-trip through the real read-only candidate source;
source bytes remain unchanged; invalid/incomplete state and unsafe output paths
fail closed; the command works without provider configuration or network access.

The local current-Flash option is covered by `tests/test_cli_current_flash.py`
and `tests/test_semantic_provider.py`: unchanged legacy/hosted defaults, exact
current-Flash request/response identity, separate Pro review, rejection of mixed
or arbitrary models, and no second request after an unknown model mismatch.
These are recorded-transport tests, not evidence of live model quality.

The selected-README boundary is covered by `tests/test_local_readme_preview.py`:
single-file reads and exact evidence identity, unsafe/missing/indirect input
denials, path-bound retry isolation, completed replay without another request,
tampered scoped-chain rejection, zero-candidate export for a missing commit,
and actual local build composition followed by publication-source denial.

September 10 local output-profile verification observed `2748 passed, 3 skipped`
across disjoint final runs: 2568 non-Phase-6 cases; 160 ordinary Phase 6 cases;
8 production five-repository cases; and 12 cross-process recovery cases. The three
skips are not live acceptance evidence. Ruff, the Phase 6 source-execution check,
validation map, hard-gate registry, and `git diff --check` also passed. This is a
dated observation of the local preview tree, not a permanent pass-count contract.

The first live selected-README trial made one `deepseek-flash` request and
recorded a terminal `schema_failure` / `forbidden_text`, not a usable candidate.
See the [pilot evidence](project/2026-09-10-single-skill-pilot.md#selected-readme-trial-result).

The follow-up local output profile is covered by `tests/test_local_extraction_output.py`
and `tests/test_extraction_diagnostics.py`: v1/v2 success/failure identity isolation,
historical candidate export, no second request after schema/excerpt/429/unknown
failures or lost responses, strict local/correction exclusion, mismatched prompt
and retry evidence rejection, all nine forbidden patterns, every schema text field,
bounded diagnostic order, and no rejected text in durable state. These are offline
recorded-transport checks; they do not establish that the revised prompt improves
real model output.

The subsequently approved v2 live trial made one `deepseek-flash` request (4,638
tokens) and also ended in `schema_failure`, with non-verbatim evidence and URL
matches in evidence excerpts. There were zero workflows and no generated Skill;
export failed closed. This exhausts the pilot's conservative three-extraction
ceiling. The 50 focused local-output/diagnostic/selected-reader tests passed before
dispatch; passing those tests did not predict real extraction quality. See the
[v2 result](project/2026-09-10-single-skill-pilot.md#selected-readme-v2-trial-result).

Local v3 is covered by `tests/test_local_evidence_preview.py` and the pure
`tests/test_evidence_selection.py` tests. Recorded production composition verifies
literal source materialization, catalogue-only untrusted input, zero-request
empty/over-budget preflight, the actual request's 65,536-byte boundary for both
providers, strict selected-output rejection, one-shot terminal/lost-response
handling, v2 state isolation, scoped audit admission, canonical export and build
with real official/local validators followed by publication denial. These are
offline mechanics, not real extraction or useful-Skill acceptance. The exhausted
3/3 live pilot budget is unchanged.

The v3 integration's final disjoint offline runs observed **2,854 passed,
3 skipped**: 2,674 non-Phase-6 tests, 160 ordinary Phase 6 tests, 8 five-repository
replay cases, and 12 cross-process recovery cases (four per semantic stage).
The recovery run was repartitioned for latency; its interrupted partial result
was excluded from totals. Full Ruff and the three Phase 6 inspectors passed.
These are dated offline results, not live acceptance or a permanent test count.

```bash
.tools/uv-0.11.29/bin/uv run --locked --no-env-file pytest -q \
  tests/test_evidence_selection.py tests/test_local_evidence_preview.py \
  tests/test_local_readme_preview.py tests/test_local_extraction_output.py
```

Run the complete locked suite:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q
```

If the default uv cache is outside the writable environment, use the repository-local cache without changing dependency resolution:

```bash
UV_CACHE_DIR="$PWD/.tools/uv-cache" .tools/uv-0.11.29/bin/uv run --locked pytest -q
```

Run one test module:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_reader.py
```

Run one test by node ID:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_reader.py::test_reader_rejects_binary_content_after_exactly_one_fetch
```

Run tests whose collected names match an expression:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q -k publication
```

There is no configured watch-mode command. During development, rerun a focused module or node ID and then run the complete suite before submitting changes.

### Automated discovery operations release chain

The exact locked release chain first validates the release map, then runs the focused operations and cross-stage regression set with fail-fast behavior, Ruff, the complete pytest suite, and a final independent acceptance inspection:

```bash
export UV_CACHE_DIR="$PWD/.tools/uv-cache"
.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_validation_map.py && \
.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase5_validation_map.py tests/test_phase5_acceptance.py tests/test_discovery_domain.py tests/test_github_search.py tests/test_operations_state.py tests/test_state_branch.py tests/test_discovery_application.py tests/test_discovery_publication_handoff.py tests/test_semantic_durability.py tests/test_discovery_workflow.py tests/test_discovery_security.py tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_state_integrity.py tests/test_pipeline_resume.py tests/test_phase3_pipeline.py tests/test_publication_recovery.py tests/test_publication_security.py -x && \
.tools/uv-0.11.29/bin/uv run --locked ruff check . && \
.tools/uv-0.11.29/bin/uv run --locked pytest -q && \
.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_acceptance.py
```

The repository-local cache setting is optional; it is useful in sandboxes where uv's default cache is not writable. It does not permit dependency updates because every uv invocation still uses `--locked`.

### Phase 6 rebind offline chain

Before the protected Phase 6 route is approved on final `main`, run the focused rebind boundary suite and then the complete offline chain:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q \
  tests/test_acceptance_domain.py \
  tests/test_acceptance_application.py \
  tests/test_operations_state.py \
  tests/test_phase6_acceptance.py \
  tests/test_cli_security.py \
  tests/test_phase6_workflow.py \
  tests/test_phase6_source_execution.py \
  tests/test_phase6_validation_map.py
.tools/uv-0.11.29/bin/uv run --locked pytest -q
.tools/uv-0.11.29/bin/uv run --locked ruff check .
.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py
.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py --plan-contract
.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_acceptance.py --registry-only
git diff --check
```

These checks prove only the offline contracts for the ordered `rebind-benchmark-lock → record-live-authority → run-benchmark → run-replay` route. They do not consume the one-shot human approvals, write canonical state, call DeepSeek, or create a candidate, catalog branch, or Draft PR. Live-only tests may skip when their complete protected configuration is absent; a skip is not live acceptance evidence.

The Phase 6 fixed-candidate integration tests also inspect the persisted pipeline runs. They require acceptance executions to use authority-derived retry-policy namespaces, correction-disabled Phase 2 execution to retain `retry-v1`, same-identity permanent failures to remain non-replayed, and a changed retry identity to start with a fresh deterministic budget. Correction-enabled DeepSeek extraction adds `+extract-correction-policy-v1` to its retry identity, including the acceptance-specific namespace. These are offline recorded-transport checks; they do not call a live model.

### Bounded extraction correction

The recorded five-repository production composition covers schema-invalid and non-verbatim responses followed by either a valid correction or terminal `schema_exhausted`, plus `429 → schema-invalid → valid` within three extraction requests. It asserts original user-message preservation, distinct response IDs/usage, fixed correction instructions, and no new request on replay. The pipeline suite injects interruption at reservation, started, response-persisted, and final-result durability boundaries; it also rejects tampered policy, missing telemetry, stale/wrong model identity, and fabricated decided predecessors before another dispatch. Operations-state tests separately enforce the hard twenty-request campaign ledger ceiling. Adapter and domain tests retain refusal, incomplete, partial-success, legitimate-negative, and unsafe-workflow exclusions and unchanged OpenAI/generation/review behavior.

Focused offline commands (use the pinned repository toolchain):

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_pipeline_resume.py tests/test_extraction_correction.py tests/test_openai_extract.py tests/test_semantic_provider.py tests/test_extractor_boundary.py tests/test_operations_state.py tests/test_state_integrity.py tests/test_semantic_durability.py
.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k production_five_repo
```

Run the existing twelve cross-process recovery cases once in final full-suite validation, not after each local edit. The correction-specific crash tests are deterministic in-process fault injections, not a claim of additional cross-process/live evidence. `extract-repo` invokes the runner once; only the fixed benchmark coordinator owns an in-call correction/resume loop. Passing these tests proves bounded offline behavior, not useful real Skill generation or Phase 6 completion.

The same production-composition tests now cover malformed extraction JSON and
non-verbatim evidence. Both must persist `schema_exhausted`, retain the completed
request's model and token telemetry, produce no candidate workflow, and make no
additional semantic request when the failed campaign is invoked again. A CLI
regression checks the closed public diagnostic. These checks validate failure
handling; they do not demonstrate improved live extraction quality.

## Suite categories

The tests are named `tests/test_*.py` and are grouped by behavior rather than by separate unit and integration directories:

| Area | Representative tests | What they cover |
|---|---|---|
| Stage contracts and authority | `test_stage_contracts.py`, `test_phase2_contracts.py`, `test_candidate_authority.py`, `test_candidate_source.py` | Versioned schemas, canonical lineage, immutable handoffs, and authority checks |
| Discovery, filtering, and bounded reading | `test_scout_filter.py`, `test_github_adapter.py`, `test_reader.py` | GitHub response handling, license and repository filters, content budgets, and rejection of unsafe input shapes |
| Semantic stages | `test_openai_extract.py`, `test_openai_generate.py`, `test_openai_review.py`, `test_semantic_provider.py` | Structured responses, provider selection, retry/failure behavior, prompt isolation, and redaction |
| Generation and validation | `test_skill_generation.py`, `test_skill_validation.py`, `test_qualification.py` | Artifact rendering, qualification policy, `skills-ref` validation, and deterministic safety rules |
| Pipeline and recovery | `test_phase2_pipeline.py`, `test_phase3_pipeline.py`, `test_pipeline_resume.py`, `test_state_integrity.py` | End-to-end offline flows, checkpoints, exact replay, tamper detection, SQLite integrity, and crash recovery |
| Automated discovery operations | `test_discovery_domain.py`, `test_github_search.py`, `test_operations_state.py`, `test_discovery_application.py`, `test_discovery_workflow.py` | Fixed search policy, numeric-ID deduplication, literal candidate budgets, durable reservations, workflow handoff, and daily/manual orchestration |
| Semantic durability and protected handoff | `test_semantic_durability.py`, `test_discovery_publication_handoff.py`, `test_semantic_provider.py` | Attempt/result barriers, unknown-outcome quarantine, exact-state re-admission, and late credential construction |
| CLI boundaries | `test_cli_dry_run.py`, `test_cli_extract_repo.py`, `test_cli_validate_skill.py`, `test_cli_security.py` | Stable JSON contracts, dry-run no-write guarantees, sanitized failures, and credential non-disclosure |
| Publication | `test_publication_domain.py`, `test_github_publish_adapter.py`, `test_publication_recovery.py`, `test_publication_security.py` | Owned-branch reconciliation, Draft PR creation/update, reviewer requests, idempotency, and forbidden remote actions |
| Gate B4 canary | `test_gate_b4_canary.py`, `test_gate_b4_canary_workflow.py`, `test_publication_live_canary.py` | Bounded canary behavior, workflow identity and authority-zone mutations, causal denials, unchanged default branch, and explicit live opt-in |
| Verification tools | `test_phase1_evidence_verifier.py`, `test_phase3_acceptance_tool.py`, `test_phase3_validation_map.py`, `test_phase4_action_audit.py`, `test_phase5_acceptance.py`, `test_phase5_validation_map.py`, `test_phase6_acceptance.py`, `test_phase6_source_execution.py`, `test_phase6_validation_map.py` | Dependency-free evidence inspectors plus mutation checks for release-map drift, state-only rebind, and weakened acceptance boundaries |

## Fixtures and recorded transports

Reusable fixtures live under `tests/fixtures/`:

- `github/` contains recorded GitHub read responses, including rate limits, redirects, license states, trees, blobs, binary content, and Git LFS pointers.
- `github_publish/` contains recorded repository, ref, tree, commit, pull, and reviewer responses for the write adapter.
- `openai/` contains successful structured responses, refusals, schema failures, incomplete responses, rate limits, server failures, and generator/reviewer case sets.
- `injection/` contains direct overrides, privilege masquerading, secret solicitation, encoded payloads, exfiltration markup, action solicitation, and cross-stage amplification samples.
- `pipeline/`, `state/`, `subject/`, and `skills/` provide approved candidate input, persisted state, subject metadata, and valid generated-skill packages.

Use the helpers in `tests/recorded_transport.py` when adding an HTTP-facing test. Register every expected method and path explicitly. An unregistered request must fail the test; do not add a fallback that reaches the network.

## Writing new tests

1. Add tests as `tests/test_<area>.py` and name cases `test_<expected_behavior>`.
2. Prefer deterministic domain-level inputs and temporary paths supplied by pytest's `tmp_path`.
3. For HTTP integrations, add a bounded recorded fixture or synthesize a response with the helpers in `tests/recorded_transport.py`, then inject `httpx.MockTransport`.
4. For CLI paths that must remain offline, request `outbound_socket_sentinel` and assert its attempts list remains empty.
5. Assert the security boundary as well as the successful result: no secret in output or representation, no unapproved path, no unexpected remote call, and no mutation beyond the declared side-effect scope.
6. Keep source-repository material as untrusted test data. Tests must not clone a fixture repository, install its dependencies, or execute its scripts.

## Prompt-injection and security checks

Security regressions should use the adversarial samples under `tests/fixtures/injection/` and the existing boundary tests as patterns. In particular:

- `test_extractor_boundary.py` and the OpenAI adapter tests verify that untrusted repository text stays in delimited user-input sections and cannot become developer instructions.
- `test_cli_security.py`, `test_side_effect_policy.py`, and `test_state_integrity.py` cover path confinement, side-effect declarations, tamper detection, permissions, and sanitized failures.
- `test_publication_security.py` and `test_publication_live_canary.py` verify that production surfaces omit merge, approval, ready-for-review, default-branch mutation, arbitrary endpoint, and cleanup capabilities.

Use unmistakably synthetic canary strings in tests. Never put a real credential, token, private key, or secret-bearing local file into a fixture, assertion, snapshot, command, or failure message.

## Publication tests and live canary

Normal publication tests are offline and use recorded transports. They exercise create, update, reconcile, recovery, reviewer, and denial behavior without contacting GitHub.

`tests/test_gate_b4_canary.py` exercises the bounded canary runner with synthetic transports, including the positive Draft path, unauthorized-repository denial, ruleset denial, default-branch protection, malformed-success handling, and cleanup-manifest behavior. `tests/test_gate_b4_canary_workflow.py` statically and mutation-tests the workflow-dispatch-only protected workflow, pinned Actions, credential timing, and fixed authority zones.

`tests/test_publication_live_canary.py` is different: one test can construct a real GitHub client, but only when the complete protected canary configuration is supplied and the explicit opt-in flag is enabled. With ordinary local configuration, the configuration guard test and the actual live execution test are the two expected skips. The skips mean that separately authorized live network actions were not requested; they do not represent missing offline assertions. Partial configuration fails closed before the token is used.

Run the canary module in its default, offline state with:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py
```

Do not enable the live path from an ordinary developer shell. It requires separately authorized, protected configuration and pre-existing bounded canary resources. The test intentionally performs no cleanup and emits only a cleanup manifest for a separately authorized human or administrator.

## Coverage requirements

No coverage plugin, collection command, or minimum line, branch, function, or statement threshold is configured in `pyproject.toml` or the repository workflows. A passing test run is therefore not a coverage-percentage guarantee.

## Quality checks

Run Ruff across source, tests, and tools:

```bash
.tools/uv-0.11.29/bin/uv run --locked ruff check .
```

Check the current diff for whitespace errors:

```bash
git diff --check
```

These checks do not replace pytest; run all three before submitting a change.

## Current observed baseline

The following is an independently verified observation from 2026-07-28, not a permanent pass-count contract:

- The focused automated-discovery release set completed with `920 passed` and no skipped local behavior.
- The locked full suite completed with `1916 passed, 2 skipped`.
- The two skips were the expected live-only publication canary paths described above.
- Ruff completed successfully.
- The final standalone inspector reported `phase5 acceptance valid`.
- `git diff --check` completed successfully.

Test counts change as coverage grows. Treat the commands and security properties above as the contract, and refresh this dated baseline when the repository changes materially.

This baseline verifies the implemented local and hosted-bound operations release chain. It does not claim that the separate real-repository adversarial acceptance campaign is complete.

## CI integration

Three GitHub Actions workflows are present:

| Workflow | Trigger | Test behavior |
|---|---|---|
| `.github/workflows/discover.yml` — “Discover and publish eligible Skill drafts” | Daily schedule and `workflow_dispatch` | Runs the locked production discovery and protected publication path; it does not run pytest or Ruff |
| `.github/workflows/gate-b4-canary.yml` — “Controlled Gate B4 catalog publication canary” | `workflow_dispatch` | Runs the separately protected, bounded canary; it does not run the offline test suite |
| `.github/workflows/publish-candidate.yml` — “Publish admitted candidate as Draft PR” | `workflow_dispatch` | Runs locked admission and Draft publication commands; it does not run pytest or Ruff |

There is therefore no automated push or pull-request test job in the repository today. Before relying on CI as a merge gate, add a workflow that runs the locked pytest and Ruff commands above and retains `git diff --check` as a repository hygiene check.
