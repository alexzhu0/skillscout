<!-- generated-by: gsd-doc-writer -->
<!-- GSD:DOC generated -->

# SkillScout

SkillScout is an auditable Python pipeline for maintainers who turn reusable workflows from public GitHub repositories into human-reviewed Agent Skill Draft PRs.

SkillScout 面向中央 Agent Skills 仓库的维护者：它以只读、可追溯的方式发现和分析公开 GitHub 仓库，并把通过安全门禁的工作流生成为仅供人工审核的 Draft PR。

> **Preview:** The deterministic and semantic pipeline is implemented and tested locally. The separately authorized live-canary release gate is still pending, so this repository is not yet production-ready. See [RELEASE.md](RELEASE.md) for the current release scope and gates.

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

SkillScout also has an explicit DeepSeek provider path. Selecting `deepseek` fixes all three semantic stages to `deepseek-v4-flash` and uses the official DeepSeek Chat Completions endpoint with thinking disabled, no tools, one JSON response, and strict local schema validation. Provider selection and credentials are documented in [Configuration](docs/CONFIGURATION.md).

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

Run the parser help for the exact arguments:

```bash
.tools/uv-0.11.29/bin/uv run --locked skillscout --help
.tools/uv-0.11.29/bin/uv run --locked skillscout dry-run --help
```

Publication is intentionally separate from extraction and generation. Do not run `publish-candidate` until the protected environment and pending release gates described in [RELEASE.md](RELEASE.md) have been satisfied.

## Testing

Run the complete locked test suite from the repository root:

```bash
.tools/uv-0.11.29/bin/uv run --locked pytest -q
```

The ordinary suite is offline by default. The live canary is separately authorized and skips unless its complete protected configuration is present.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — components, boundaries, and data flow
- [Configuration](docs/CONFIGURATION.md) — provider and publication settings
- [Getting started](docs/GETTING-STARTED.md) — prerequisites, setup, and first run
- [Development](docs/DEVELOPMENT.md) — local development workflow and code style
- [Testing](docs/TESTING.md) — test suites, fixtures, and CI behavior
- [Release status](RELEASE.md) — preview scope, verification evidence, and remaining gates
