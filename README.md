<!-- generated-by: gsd-doc-writer -->
<!-- GSD:DOC generated -->

# SkillScout

SkillScout is an auditable Python pipeline for maintainers who turn reusable workflows from public GitHub repositories into human-reviewed Agent Skill Draft PRs.

SkillScout 面向中央 Agent Skills 仓库的维护者：它以只读、可追溯的方式发现和分析公开 GitHub 仓库，并把通过安全门禁的工作流生成为仅供人工审核的 Draft PR。

> **Preview:** The bounded daily/manual discovery path, deterministic and semantic pipeline, durable state recovery, and controlled Draft publication boundary are implemented and independently verified. A fresh Gate B4 canary approved the exact reviewed workflow and hosted identities. The V2 five-repository benchmark lock was successfully persisted for source commit `7bab6abcb89b5287e8d32077333fd4383331d6e5`, but persistence is not acceptance: live authority, a real benchmark, replay, and Draft PR acceptance remain pending. SkillScout is therefore not yet production-ready. Any workflow, GitHub App scope, catalog, ruleset, reviewer, protected-environment, or installation-identity change invalidates that live evidence and requires a new Gate B4 run. See [RELEASE.md](RELEASE.md) for the current release scope and gates.

## Safety model

- SkillScout supports public GitHub repositories only. It reads bounded repository content through the GitHub API; it does not clone repositories, install their dependencies, run their scripts, or execute their code.
- Deterministic stages own filtering, content limits, schemas, validation, state, and publication authority. The LLM is limited to semantic extraction, skill generation, and an independent review request.
- External repository text is always untrusted input. Semantic calls are tool-free and their results must pass strict schemas and deterministic safety checks.
- The publication boundary can create or update an owned machine branch, open a Draft PR, and request configured human reviewers. SkillScout never merges, approves, or marks a PR ready for review automatically.

## How it works

```text
public GitHub repository
        │
        ▼
deterministic filtering and bounded static reading
        │
        ▼
semantic extraction ──► deterministic qualification
        │
        ▼
skill generation ──► structural and safety validation
        │
        ▼
independent semantic review
        │
        ▼
controlled Draft PR for human review
```

Every stage exchanges versioned, validated data and records auditable evidence so failures can be retried without relying on hidden shared state.

## Requirements

- Python `3.13.14` (the package accepts Python `>=3.13,<3.14`)
- The pinned `uv 0.11.29` executable at `.tools/uv-0.11.29/bin/uv`
- Git

## Installation

```bash
git clone https://github.com/alexzhu0/skillscout.git
cd skillscout
.tools/uv-0.11.29/bin/uv sync --locked
```

The lock file is authoritative; keep `--locked` enabled so dependency resolution cannot drift.

## Quick start

1. Create an isolated working directory:

   ```bash
   demo_dir="$(mktemp -d)"
   ```

2. Run the bundled approved fixture through the offline pipeline:

   ```bash
   .tools/uv-0.11.29/bin/uv run --locked skillscout dry-run \
     --fixture tests/fixtures/pipeline/approved.json \
     --state "$demo_dir/state.db" \
     --output "$demo_dir/output"
   ```

3. Confirm that the JSON result contains:

   ```json
   {
     "status": "planned_not_published",
     "last_stage": "publication_planner",
     "remote_writes_attempted": 0
   }
   ```

The exact output also includes a generated `run_id`, reuse count, and publication-plan path.

## Semantic providers

OpenAI is the default provider. Extraction, generation, and review use the OpenAI Responses API with the configured `gpt-5.6-terra` model.

SkillScout also has an explicit DeepSeek provider path. Selecting `deepseek` fixes extraction and generation to `deepseek-v4-flash`, and independent review to `deepseek-v4-pro`. It uses the official DeepSeek Chat Completions endpoint with thinking disabled, no tools, one JSON response, and strict local schema validation. Provider selection and credentials are documented in [Configuration](docs/CONFIGURATION.md).

## CLI usage

The installed `skillscout` command exposes these bounded workflows:

| Command | Purpose |
|---|---|
| `dry-run` | Run the deterministic local fixture pipeline with no network writes. |
| `extract-repo` | Read one admitted public repository and extract workflow evidence. |
| `build-candidate` | Generate, validate, and independently review one admitted candidate. |
| `inspect-run` | Inspect the durable JSON projection of a recorded run. |
| `verify-publication-admission` | Revalidate the exact evidence handoff before publication authority is used. |
| `publish-candidate` | Reconcile one admitted candidate into its controlled Draft PR. |
| `discover` | Run the bounded, unprotected discovery graph and emit a non-authorizing metadata handoff. |
| `publish-discovered` | Re-read exact persisted state, re-admit the discovery handoff, and publish eligible candidates as Draft PRs from the protected boundary. |
| `preflight-fresh-campaign` | Read-only, bounded diagnosis of state identity, state restore, and one Search page per reviewed query. |

Run the parser help for the exact arguments:

```bash
.tools/uv-0.11.29/bin/uv run --locked skillscout --help
.tools/uv-0.11.29/bin/uv run --locked skillscout dry-run --help
.tools/uv-0.11.29/bin/uv run --locked skillscout discover --help
```

Publication is intentionally separate from extraction and generation. Do not run `publish-candidate` or `publish-discovered` from an ordinary developer shell; the reviewed production path introduces catalog authority only inside the protected environment.

`preflight-fresh-campaign` is a diagnostic command for the protected Phase 6 workflow. It never writes the state branch, calls a model, reads candidate metadata or licenses, executes repository code, or creates a Pull Request. It prints only stage names, durations, immutable state digests, Search counts/rate facts, and a closed error code; state restore keeps separate hard-bounded lineage and payload phases and may report the safe subphase (`ref`, `lineage`, or `payload`). A failed probe exits non-zero after printing that report.

## Daily and manual discovery

The production entry point is [`.github/workflows/discover.yml`](.github/workflows/discover.yml). It starts automatically every day at `03:17 UTC` and also supports an authorized manual run through GitHub Actions:

1. Open the repository's **Actions** tab and select **Discover and publish eligible Skill drafts**.
2. Choose **Run workflow** and dispatch the exact reviewed revision.
3. Monitor the unprotected `discovery` job, which runs the fixed query set through independent review and persists the exact three-store state bundle on `skillscout-state`.
4. When GitHub requests access to the separately governed `skillscout-catalog-publish` environment, approve it only according to the operating policy. The protected job re-reads the exact state commit and re-derives every admission before a catalog-scoped token is minted.
5. Review any resulting Draft PR manually. The workflow cannot approve, merge, or mark it ready for review.

Scheduled and manual runs share the non-cancelling `skillscout-production` concurrency group. Each run is capped at 100 deduplicated repositories and 20 semantic reservations; retry and recovery do not expand those budgets. Configure the repository variables, protected secrets, and environment policy described in [Configuration](docs/CONFIGURATION.md) before dispatching this workflow. Never paste credentials into CLI arguments, workflow inputs, logs, or state.

## Testing

Run the complete locked test suite from the repository root:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q
```

The ordinary suite is offline by default. The live canary is separately authorized and skips unless its complete protected configuration is present.

The independently verified 2026-07-28 baseline is `1916 passed, 2 skipped`; the two skips are the expected live-only publication canaries. This is a dated observation, not a fixed test-count contract.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — components, boundaries, and data flow
- [Configuration](docs/CONFIGURATION.md) — provider and publication settings
- [Getting started](docs/GETTING-STARTED.md) — prerequisites, setup, and first run
- [Development](docs/DEVELOPMENT.md) — local development workflow and code style
- [Testing](docs/TESTING.md) — test suites, fixtures, and CI behavior
- [Release status](RELEASE.md) — preview scope, verification evidence, and remaining gates
