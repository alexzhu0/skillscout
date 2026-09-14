# SkillScout

SkillScout is an auditable Python pipeline for maintainers who turn reusable workflows from public GitHub repositories into human-reviewed Agent Skill Draft PRs.

SkillScout 面向中央 Agent Skills 仓库的维护者：它以只读、可追溯的方式发现和分析公开 GitHub 仓库，并把通过安全门禁的工作流生成为仅供人工审核的 Draft PR。

> **Preview — September 2026:** The discovery, extraction, candidate-generation, durable-state, and controlled Draft-publication paths are implemented. The [September 3 real benchmark](https://github.com/alexzhu0/skillscout/actions/runs/33734530468) passed authority preflight but failed during extraction; replay and successful real-Skill acceptance remain pending. SkillScout is not yet production-ready. Historical Gate B4 approvals apply only to their exact reviewed workflows and identities. See [RELEASE.md](RELEASE.md) for release evidence and the [direction review](docs/project/2026-09-09-direction-review.md) for the next priority: demonstrate one useful Skill with a controlled task comparison.

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

For the real single-repository route, see the [extract → export → build guide](docs/GETTING-STARTED.md#local-extract-build-and-inspect-flow).
`export-candidates` bridges verified extraction state into canonical local build
inputs without network access or credentials. The [single-Skill pilot](docs/project/2026-09-10-single-skill-pilot.md)
defines the intended real-use comparison; it is not completed live acceptance.
The September 10 trial produced zero admissible workflows. A separately approved
[September 11 v3 trial](docs/project/2026-09-11-local-v3-extraction.md) extracted and
exported one real workflow, but offline qualification rejected it for dependency
installation and missing approval controls. No Skill was generated. Both trial
budgets are exhausted; there is no automatic retry.
The [September 14 offline diagnosis](docs/project/2026-09-14-local-v3-diagnosis.md)
reconstructed the exact evidence catalogue: core RAG information was retained,
but the surviving candidate selected demo operations. The next focus is semantic
workflow selection and usefulness evaluation, not relaxing safety rules.
The [offline selection examples](docs/WORKFLOW-SELECTION-EVAL.md) now provide
seven assistant-proposed positive/negative cases and an explicit-label comparison
tool. They are not a human-validated benchmark or proof of model improvement.

For a nested example, local `extract-repo --readme-path path/to/README.md`
reads only that selected file at the subject's exact 40-character commit SHA.
It retains the normal license/content limits and never follows links or executes
code. Its candidates can be exported and built locally, but publication rejects
this preview-only source. See [configuration](docs/CONFIGURATION.md#selected-readme-local-preview).
This command now uses a separately identified v2 local output profile: one attempt
per stage, explicit safe-output instructions, and content-free rejection diagnostics.
Historical v1 runs remain readable; reissuing an old command is not a v1 resume.

Explicit `--evidence-selection` (requires `--readme-path`) selects local v3:
the model chooses bounded evidence IDs and deterministic code restores the exact
source excerpts before the unchanged safety validator. Empty catalogues and
semantic inputs over 65,536 UTF-8 bytes stop before a model request. Without the
flag, selected-README commands remain v2. The mechanical repair has now produced
one real extracted workflow, but not a qualified or useful Skill. The old pilot
remains terminal at 3/3; the separate v3 trial is terminal at 1/1. Another live
trial needs a separately approved budget. See the
[v3 command](docs/CONFIGURATION.md#local-v3-evidence-selection).

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

SkillScout also has an explicit DeepSeek provider path. By default, selecting `deepseek` fixes extraction and generation to `deepseek-v4-flash`, and independent review to `deepseek-v4-pro`. Local `extract-repo` and `build-candidate` runs may explicitly select current `deepseek-flash` with `--deepseek-current-flash`; hosted defaults and historical acceptance bindings are unchanged. It uses the official DeepSeek Chat Completions endpoint with thinking disabled, no tools, one JSON response per adapter invocation, and strict local schema validation. Provider selection and credentials are documented in [Configuration](docs/CONFIGURATION.md).

DeepSeek extraction can schedule one application-level correction for invalid structured output or zero surviving workflows with at least one excerpt-only rejection. The correction keeps the original pinned source input and validators, adds only fixed trusted guidance, and consumes the existing three-attempt extraction limit and twenty-request acceptance-campaign limit. Refusals, incomplete responses, legitimate no-workflow results, partial success, unsafe-only rejections, and ambiguous provider outcomes are not correction opportunities. There is no retry after a correction. The fixed benchmark coordinator runs the bounded scheduling loop; `extract-repo` invokes the runner once, so a scheduled correction requires a subsequent invocation with the same inputs and state. This offline-verified behavior is not evidence of a useful real Skill or completed Phase 6 acceptance.

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
| `rebind-benchmark-lock` | Protected state-only rebind of an approved Phase 6 five-repository lock from a source acceptance run to a new target run. |
| `record-live-authority` | Protected state-only V2 authority receipt for one rebound acceptance run. |
| `preflight-fresh-campaign` | Read-only, bounded diagnosis of state identity, state restore, and one Search page per reviewed query. |

Run the parser help for the exact arguments:

```bash
.tools/uv-0.11.29/bin/uv run --locked skillscout --help
.tools/uv-0.11.29/bin/uv run --locked skillscout dry-run --help
.tools/uv-0.11.29/bin/uv run --locked skillscout discover --help
```

Publication is intentionally separate from extraction and generation. Do not run `publish-candidate` or `publish-discovered` from an ordinary developer shell; the reviewed production path introduces catalog authority only inside the protected environment.

`preflight-fresh-campaign` is a diagnostic command for the protected Phase 6 workflow. It never writes the state branch, calls a model, reads candidate metadata or licenses, executes repository code, or creates a Pull Request. It prints only stage names, durations, immutable state digests, Search counts/rate facts, and a closed error code; state restore keeps separate hard-bounded lineage and payload phases and may report the safe subphase (`ref`, `lineage`, or `payload`). A failed probe exits non-zero after printing that report.

### Phase 6 benchmark rebind

The pending live-acceptance sequence is `rebind-benchmark-lock → record-live-authority → run-benchmark → run-replay`. It is an operator workflow, not a developer-shell shortcut. Before rebind, set a fresh target `SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID`; keep the historical `SKILLSCOUT_PHASE6_SOURCE_ACCEPTANCE_RUN_ID` distinct. The protected rebind uses Actions approval metadata to write and admit a fixed-locator canonical self-digested handoff before state restore, then exposes its state token solely for final persistence. That persistence performs exactly one state CAS to atomically write the rebind reference and replacement lock. It has no model, catalog, candidate-source, publication, or Pull Request capability.

After `record-live-authority` succeeds, retain and verify the preselected `SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID`, then set `SKILLSCOUT_PHASE6_AUTHORITY_STATE_COMMIT_SHA`, `SKILLSCOUT_PHASE6_AUTHORITY_STATE_ROOT_DIGEST`, and `SKILLSCOUT_PHASE6_AUTHORITY_DIGEST` from its sanitized receipt before a benchmark or replay may begin. Together, those four variables must exactly match that receipt. Each approval and carrier is single-use: ambiguity, a failed attempt, or any source/workflow change after merge stops the sequence and requires a new exact human approval. A completed replay can at most yield a publication-ready handoff; Gate B4 and any Draft PR remain separate, unstarted work.

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
