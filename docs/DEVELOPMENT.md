# SkillScout Development

This guide is for maintainers changing SkillScout's pipeline, contracts, adapters, and controlled publication path. Read [Architecture](ARCHITECTURE.md) before changing a stage boundary and [Configuration](CONFIGURATION.md) before adding runtime settings or credentials.

## Local setup

SkillScout requires Python `>=3.13,<3.14`. The repository pins `uv 0.11.29` at `.tools/uv-0.11.29/bin/uv`, declares dependencies in `pyproject.toml`, and locks them in `uv.lock`.

1. Fork the repository on GitHub, then clone your fork:

   ```bash
   git clone https://github.com/<your-github-login>/skillscout.git
   cd skillscout
   git remote add upstream https://github.com/alexzhu0/skillscout.git
   ```

2. Install the locked runtime and development dependencies:

   ```bash
   .tools/uv-0.11.29/bin/uv sync --locked
   ```

3. Confirm the packaged CLI and test environment:

   ```bash
   .tools/uv-0.11.29/bin/uv run --locked skillscout --help
   .tools/uv-0.11.29/bin/uv run --locked pytest --version
   .tools/uv-0.11.29/bin/uv run --locked ruff --version
   ```

No `.env` file is loaded by the application. Inject local provider credentials through the process environment only, never through committed files, fixtures, logs, prompts, state databases, or command examples. See [Configuration](CONFIGURATION.md) for the closed variable set.

For a credential-free smoke run, use the approved local fixture:

```bash
work_dir="$(mktemp -d)"
.tools/uv-0.11.29/bin/uv run --locked skillscout dry-run \
  --fixture tests/fixtures/pipeline/approved.json \
  --state "$work_dir/state.db" \
  --output "$work_dir/output"
```

The expected terminal status is `planned_not_published`, with `remote_writes_attempted` equal to `0`.

## Commands

`pyproject.toml` does not define a Makefile-style command collection. Use the pinned `uv` executable so the lock file remains authoritative.

| Command | Description |
|---|---|
| `.tools/uv-0.11.29/bin/uv sync --locked` | Synchronize runtime and development dependencies without changing resolution. |
| `.tools/uv-0.11.29/bin/uv run --locked skillscout --help` | Run the installed `skillscout` entry point and list CLI commands. |
| `.tools/uv-0.11.29/bin/uv run --locked pytest -q` | Run the complete pytest suite. |
| `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_reader.py` | Run one test module. |
| `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_reader.py::test_name` | Run one test node; replace `test_name` with an existing node. |
| `.tools/uv-0.11.29/bin/uv run --locked ruff check src tests tools` | Run Ruff's configured lint checks. |
| `.tools/uv-0.11.29/bin/uv run --locked ruff format --check src tests tools` | Check formatting without modifying files. |
| `.tools/uv-0.11.29/bin/uv run --locked ruff format src tests tools` | Format Python source, tests, and verification tools. |
| `sh tools/verify_phase3_gate_b3.sh` | Verify the locked Phase 3 validator dependency authority before importing it. |
| `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase3_acceptance.py` | Run the read-only Phase 3 architecture and supply-chain acceptance checks. |
| `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py` | Verify the pinned GitHub Action audit evidence. |
| `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_acceptance.py` | Run the independent, read-only Phase 5 operations acceptance inspector. |
| `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py` | Verify the Phase 6 workflow has no unapproved source-execution or credential zone. |

The repository currently configures Ruff with Python 3.13 syntax and a 100-character line length. It does not configure mypy or another static type-check command in `pyproject.toml`.

## Source layout and ownership

```text
src/skillscout/
├── domain/       # Frozen contracts, canonical identities, discovery budgets, and pure policy
├── application/  # Stage orchestration, discovery, ports, retries, and authority sequencing
├── adapters/     # GitHub/provider I/O plus pipeline, operations, publication, and state-ref stores
├── bootstrap.py  # Composition roots and late credential/capability construction
└── cli.py        # Packaged command boundary and sanitized user-facing failures

config/supply-chain/ # Validator lock authority
config/discovery-queries-v1.json # Reviewed, versioned GitHub Search query set
tools/               # Read-only or preflight verification tools
tests/               # Unit, contract, fixture, security, recovery, and workflow tests
```

Keep dependencies pointing inward: domain modules must not acquire network, filesystem, provider, or credential imports; application code depends on domain contracts and protocols; adapters implement effectful seams; bootstrap and CLI compose them. Publication-specific domain, application, adapter, and state modules must remain separate from the ordinary read pipeline.

The automated discovery path has additional ownership boundaries:

- `domain/discovery.py` owns the strict query, budget, reservation, terminal, and state-root contracts.
- `application/discovery.py` coordinates bounded Search and the existing Phase 2 and Phase 3 applications. Its dependency type cannot represent catalog or publication capabilities, and its result is a non-authorizing content-addressed handoff.
- `adapters/operations_state.py` owns discovery runs, reservations, semantic attempts, workflow terminals, and three-store bundle assembly.
- `adapters/state.py`, `adapters/operations_state.py`, and `adapters/publication_state.py` each export and rebuild only their own canonical facts and disposable SQLite projection.
- `adapters/state_branch.py` owns the fixed-ref restore, parent-bound non-force update, exact remote reread, and semantic durability receipt.
- Protected publication must re-read the exact state commit and independently re-derive admission before bootstrap constructs the catalog client or reads its token.

## Stage-contract rules

Every cross-stage value is a strict, versioned contract. When changing a contract:

- Use frozen Pydantic models with unknown fields rejected, bounded strings and collections, and a literal `schema_version`.
- Update canonical serialization and digest derivation together. Never add an unhashed field to persisted authority or evidence.
- Preserve explicit stage ordering and predecessor hashes. A successful row is reusable only after the complete chain and its canonical bytes are reverified.
- Add or migrate durable state deliberately; never treat a new field as an implicit shared value between stages.
- Update fixtures and contract, resume, tamper, and invalid-input tests for both the accepted path and fail-closed path.
- Keep public diagnostics sanitized and selected from the closed error vocabulary. Do not echo external text, rejected configuration, provider bodies, paths containing sensitive data, or exception text.

`WorkflowSpec` is the semantic reduction boundary. Raw repository text may enter only the bounded reader and extractor input. Phase 3 receives verified structured evidence, not a repository checkout or arbitrary source bundle.

## Deterministic and semantic boundary

Deterministic code owns repository admission, license checks, read budgets, path and content rules, evidence verification, qualification thresholds, artifact validation, state integrity, retry authority, publication admission, and remote-write scope. Semantic adapters are limited to extraction, generation, and independent review.

Do not move a safety or authority decision into a prompt. Semantic requests must remain:

- tool-free and unable to execute code;
- strictly schema-bound;
- size- and output-token-bounded;
- explicit that external text is inert, untrusted data;
- isolated by stage, with a fresh Reviewer request rather than Generator conversation reuse; and
- subject to deterministic validation before their output crosses the next boundary.

External repository code is never cloned and run, installed as a dependency, imported into the SkillScout process, or invoked as a script. Tests may execute SkillScout's own CLI and repository-owned verification tools; they must not turn third-party source fixtures into executable inputs.

Do not read repository `.env` files or PEM, JWT, token, private-key, or other secret material while developing or debugging. Credentials may enter only through the runtime environment at the latest required boundary. If a test needs a credential-shaped value, use a clearly synthetic sentinel and assert that it cannot cross logs, prompts, durable models, SQLite, state objects, CLI output, or workflow handoffs.

## Discovery durability and store ownership

Automated discovery persists one exact bundle with three independently owned SQLite stores:

| Store | Fixed state-branch path | Owner |
|---|---|---|
| Pipeline | `state/databases/pipeline.sqlite3` | Stage attempts, checkpoints, lineage, and completed candidate evidence |
| Operations | `state/databases/operations.sqlite3` | Search observations, non-refundable 100/20 reservations, semantic attempts, and run/workflow terminals |
| Publication | `state/databases/publication.sqlite3` | Publication attempts, reconciliation checkpoints, and Draft PR records |

Canonical JSON facts under `state/objects/sha256/` are the rebuild authority; SQLite is the queryable projection. `state/root.json` binds the three owner exports, their projections, the prior root, the exact parent commit, and the query/budget policy digests. Do not add a fourth store, read another owner's private schema, or make a database snapshot authoritative by itself.

A durability change must preserve all of these properties:

- each store validates and exports its own closed fact set;
- damaged or missing SQLite may rebuild only from owner-validated canonical JSON;
- prospective and restored cross-store projections must be exactly equal before reuse;
- state-ref updates use the sole observed parent with `force=False`;
- conflicts are neither merged nor overwritten; and
- success is granted only after ref, commit, tree, root, objects, and all three databases are reread and match the prospective bundle byte for byte.

Semantic transitions use the same barrier. The operations store must contain exactly one matching `attempt_started`, `result_decided`, `result_confirmed_retryable`, or `result_outcome_unknown` fact. The returned receipt binds that transition, prior and verified state heads and roots, all three owner exports, databases, and projections. Missing, stale, malformed, or mismatched receipts grant no provider-request, retry, or terminal authority.

## Extending semantic providers

Provider selection is intentionally closed in `src/skillscout/adapters/semantic_provider.py`. A provider change is incomplete unless it preserves all three semantic stages and their common security behavior.

1. Add the provider to `SemanticProvider` and resolve it through `resolve_semantic_provider()` using a fixed provider identity, explicit credential variable, approved model identifiers, and an allowlisted base URL where applicable.
2. Keep credential lookup in `create_semantic_client()` or an equivalently late factory. Settings representations, Pydantic results, logs, state, and prompts must never retain the credential.
3. Wire extraction, generation, and review through `OpenAIExtractionClient`, `OpenAIGenerationClient`, and `OpenAIReviewClient`, or rename/refactor the stage adapters without widening their `REMOTE_READ` effect scope.
4. Preserve strict local response validation, single bounded responses, no tools, and `max_retries=0` on the provider SDK client. Retry authority belongs only to deterministic application policy: a confirmed rate-limit response may consume the next bounded attempt after its durable transition is remotely acknowledged; timeouts, connection failures, request timeout status, ambiguous server failures, and unclassified transport errors become `semantic_outcome_unknown` and are quarantined without replay.
5. Do not reuse the Generator request or raw repository snapshot for review. Reviewer input remains the canonical four-section envelope.
6. Update `tests/test_semantic_provider.py`, `tests/test_semantic_durability.py`, the three stage-adapter test modules, failure fixtures, and provider-boundary security tests.
7. If imports or dependencies change, update `pyproject.toml`, regenerate `uv.lock`, re-authorize the Phase 3 lock digest, and update the import-capability allowlist in `tools/verify_phase3_acceptance.py`.

Avoid a generic “OpenAI-compatible” escape hatch. Each admitted provider needs an explicit endpoint policy, model policy, response contract, failure mapping, and tests.

## Publication isolation

Publication has remote-write authority and must never become a convenience method on the read or semantic adapters.

- `src/skillscout/domain/publication.py` stays pure and authority-free until candidate evidence is combined with protected catalog and reviewer configuration.
- `src/skillscout/application/publication.py` must continue to reconcile remote state before mutation and return `manual_intervention_required` for ambiguous or human-modified state.
- `src/skillscout/bootstrap.py` must construct the publication state and GitHub client only after evidence and protected admission are verified. Token lookup remains lazy.
- `src/skillscout/adapters/github_publish.py` stays bound to one catalog and stable slug with a finite route surface. Do not add merge, approval, ready-for-review, force-push, default-branch mutation, arbitrary path, or arbitrary HTTP capabilities.
- Publication state remains separate from Phase 2 and Phase 3 state. Candidate handoff data must not carry catalog authority, reviewer authority, tokens, or headers.
- The automated endpoint remains a Draft PR plus reviewer request. Human reviewers retain merge and approval control.

Changes in this area should run the publication domain, adapter, recovery, security, action-audit, and live-canary tests. The live canary is separately authorized and must remain skipped unless its complete protected opt-in configuration is present.

## Workflow and evidence change control

The hosted discovery, protected publication, and controlled canary evidence are byte-bound security surfaces. A change to `.github/workflows/discover.yml`, `.github/workflows/publish-candidate.yml`, `.github/workflows/gate-b4-canary.yml`, an Action pin, GitHub App scope or installation, catalog identity, ruleset, protected environment, or reviewer configuration invalidates the prior hosted approval.

Treat such a change as a new control surface:

1. Start with a failing workflow-security or acceptance mutation that proves the old invariant rejects the proposed drift.
2. Keep checkout and third-party Actions pinned to full commit SHAs, preserve `persist-credentials: false`, and keep discovery and protected publication in separate credential zones.
3. Run the locked unit, workflow, security, recovery, and independent acceptance suites.
4. Re-run the separately authorized hosted canary and causal denial probes against the exact new bytes and control-plane configuration.
5. Record fresh evidence only after confirming the default branch is unchanged, automated output remains Draft-only, and cleanup used separate human or administrative authority.

Never edit an accepted evidence record to make new workflow bytes appear approved. Preserve historical evidence and produce a new, independently bound record. Concurrency observations prove scheduling behavior only; they do not substitute for publication denial, ruleset, or Draft-only evidence.

## Safe file editing

Treat state databases, manifests, frozen candidate packages, validation reports, review attestations, and publication records as evidence, not hand-edited source:

- Never repair evidence in place. Fix the producer or migration, then create or resume through the verified application path.
- Use private, anchored directories for state and candidate output. Existing output directories must satisfy the ownership and permission checks enforced by the adapters.
- Do not follow symlinks or accept path traversal when adding filesystem behavior.
- Do not weaken stable-read checks, byte caps, file-type gates, canonical JSON, digest comparison, or fail-closed overwrite behavior.
- Never commit credentials or copy real secret values into fixtures. Security fixtures should use unmistakably synthetic sentinels.

Before changing repository files, first invoke `superpowers:using-superpowers`
and then follow every applicable Superpowers skill. Use
`superpowers:brainstorming` before creative work,
`superpowers:writing-plans` before multi-step implementation,
`superpowers:test-driven-development` for features and bug fixes,
`superpowers:systematic-debugging` for unexpected behavior, and
`superpowers:verification-before-completion` before claiming completion. See
[AGENTS.md](../AGENTS.md) for the complete repository rules and secret boundary.

## Test-driven and mutation expectations

For trust-boundary work, add the failing test before changing production code. Keep the red case narrow, implement the smallest deterministic behavior that makes it pass, then run the focused suite before the full locked regression. Tests should cover both successful flow and the refusal or recovery behavior that protects the boundary.

Mutation resistance is required for security and authority invariants. Add a test that changes the protected value or structure and proves the checker fails closed, especially for:

- the 100-candidate and 20-semantic-reservation ceilings;
- query-set versions and canonical digests;
- retry dispositions and semantic transition names;
- three-store ownership, export, projection, CAS, and exact-reread checks;
- workflow triggers, concurrency, permissions, environment boundaries, and full-SHA Action pins;
- bounded handoff fields, locators, byte limits, and digest comparisons; and
- forbidden publication capabilities such as merge, approval, ready-for-review, force update, or default-branch mutation.

Run the directly affected tests during red/green development, then use the repository-local locked toolchain:

```bash
.tools/uv-0.11.29/bin/uv run --locked ruff check src tests tools
.tools/uv-0.11.29/bin/uv run --locked ruff format --check src tests tools
.tools/uv-0.11.29/bin/uv run --locked pytest -q
.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase5_acceptance.py
.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py
```

The independent acceptance inspector is read-only and mutation-tested. A green full suite without the applicable independent acceptance check is insufficient for workflow, budget, retry, state-ownership, or hosted-evidence changes.

## Code style

Ruff `0.15.21` is the configured linter and formatter. Configuration lives in `pyproject.toml` under `[tool.ruff]`.

- Target Python 3.13.
- Keep lines within 100 characters after formatting.
- Prefer explicit typed contracts and small pure functions at trust boundaries.
- Keep effect scopes and capability construction visible; do not hide I/O behind domain helpers.
- Preserve sanitized exception boundaries and avoid logging external or secret-bearing values.

Run before requesting review:

```bash
.tools/uv-0.11.29/bin/uv run --locked ruff check src tests tools
.tools/uv-0.11.29/bin/uv run --locked ruff format --check src tests tools
.tools/uv-0.11.29/bin/uv run --locked pytest -q
```

## Branch conventions

The default branch is `main`. No branch-name convention is documented in the repository, and there is no pull-request template. Recent commits commonly use a Conventional Commits-like `type(scope): summary` form, but this is an observed history pattern rather than an enforced specification.

Use a short-lived branch that describes one bounded change, avoid mixing generated evidence with unrelated source edits, and keep security or contract changes reviewable as a coherent unit.

## Pull request process

- Rebase or merge the current `main` into the working branch and review the final diff for secrets, generated state, and unrelated files.
- Explain which stage, contract, effect scope, or authority boundary changes and why.
- Include tests for the success path and relevant refusal, tamper, retry, or ambiguous-state paths.
- Run the locked pytest suite and applicable Ruff and verification commands; report any known pre-existing failure separately.
- Update [Architecture](ARCHITECTURE.md), [Configuration](CONFIGURATION.md), [Testing](TESTING.md), or [release notes](../RELEASE.md) when behavior, settings, verification evidence, or release gates change.
- Do not merge or approve generated Skill candidates automatically. Candidate publication ends at a Draft PR for human review.

Automated discovery operations are implemented and independently verified. Adversarial acceptance remains pending, so changes must not describe the whole product as production-ready. For the current preview status and protected release gates, see [release notes](../RELEASE.md).
