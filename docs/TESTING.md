<!-- generated-by: gsd-doc-writer -->
<!-- GSD:DOC generated -->

# Testing SkillScout

## Test framework and setup

SkillScout uses Python `>=3.13,<3.14` and pytest `9.1.1`. The development dependencies and their exact versions are locked in `pyproject.toml` and `uv.lock`; use the repository-pinned uv executable so the environment is reproduced from that lock.

From the repository root, install or synchronize the locked development environment:

```bash
.tools/uv-0.11.29/bin/uv sync --locked
```

Pytest is configured in `pyproject.toml` to discover tests under `tests/` and reject unknown configuration or markers with `--strict-config` and `--strict-markers`.

The ordinary suite is offline by default. GitHub and OpenAI HTTP behavior is represented by frozen JSON fixtures and `httpx.MockTransport`; `tests/recorded_transport.py` rejects any request for which no response was recorded. Tests that exercise CLI dry runs can also use the `outbound_socket_sentinel` fixture from `tests/conftest.py`, which fails on attempted socket connections.

## Running tests

Run the complete locked suite:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q
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

## Suite categories

The tests are named `tests/test_*.py` and are grouped by behavior rather than by separate unit and integration directories:

| Area | Representative tests | What they cover |
|---|---|---|
| Stage contracts and authority | `test_stage_contracts.py`, `test_phase2_contracts.py`, `test_candidate_authority.py`, `test_candidate_source.py` | Versioned schemas, canonical lineage, immutable handoffs, and authority checks |
| Discovery, filtering, and bounded reading | `test_scout_filter.py`, `test_github_adapter.py`, `test_reader.py` | GitHub response handling, license and repository filters, content budgets, and rejection of unsafe input shapes |
| Semantic stages | `test_openai_extract.py`, `test_openai_generate.py`, `test_openai_review.py`, `test_semantic_provider.py` | Structured responses, provider selection, retry/failure behavior, prompt isolation, and redaction |
| Generation and validation | `test_skill_generation.py`, `test_skill_validation.py`, `test_qualification.py` | Artifact rendering, qualification policy, `skills-ref` validation, and deterministic safety rules |
| Pipeline and recovery | `test_phase2_pipeline.py`, `test_phase3_pipeline.py`, `test_pipeline_resume.py`, `test_state_integrity.py` | End-to-end offline flows, checkpoints, exact replay, tamper detection, SQLite integrity, and crash recovery |
| CLI boundaries | `test_cli_dry_run.py`, `test_cli_extract_repo.py`, `test_cli_validate_skill.py`, `test_cli_security.py` | Stable JSON contracts, dry-run no-write guarantees, sanitized failures, and credential non-disclosure |
| Publication | `test_publication_domain.py`, `test_github_publish_adapter.py`, `test_publication_recovery.py`, `test_publication_security.py` | Owned-branch reconciliation, Draft PR creation/update, reviewer requests, idempotency, and forbidden remote actions |
| Verification tools | `test_phase1_evidence_verifier.py`, `test_phase3_acceptance_tool.py`, `test_phase3_validation_map.py`, `test_phase4_action_audit.py` | Dependency-free evidence and release-gate verifiers |

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

`tests/test_publication_live_canary.py` is different: one test can construct a real GitHub client, but only when the complete protected canary configuration is supplied and the explicit opt-in flag is enabled. With ordinary local configuration, that test skips before client construction. Partial configuration fails closed before the token is used.

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

The following is an observation from 2026-07-27, not a permanent pass-count contract:

- The locked full suite completed with `1384 passed, 2 skipped`.
- `git diff --check` completed successfully.
- Ruff reported 12 existing violations: ten `E702` multiple-statements-on-one-line findings in publication tests and two unused imports in `tools/verify_phase4_action_audit.py`. Until those findings are corrected, the repository-wide Ruff command is expected to return nonzero.

Test counts change as coverage grows. Treat the commands and security properties above as the contract, and refresh this dated baseline when the repository changes materially.

## CI integration

The only workflow currently present is `.github/workflows/publish-candidate.yml`, named “Publish admitted candidate as Draft PR.” It is manually triggered with `workflow_dispatch` and runs locked admission and publication CLI commands; it does not run pytest or Ruff.

There is therefore no automated push or pull-request test job in the repository today. Before relying on CI as a merge gate, add a workflow that runs the locked pytest and Ruff commands above and retains `git diff --check` as a repository hygiene check.
