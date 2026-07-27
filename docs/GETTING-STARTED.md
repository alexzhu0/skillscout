<!-- generated-by: gsd-doc-writer -->
<!-- GSD:DOC generated -->

# Getting Started

This guide takes a maintained SkillScout checkout from locked dependency setup to its first safe, offline result. Live semantic-provider access and Draft PR publication are optional, separate steps with additional authority requirements.

## Prerequisites

- Git, for cloning the repository.
- CPython `3.13.14`. The package accepts Python `>=3.13,<3.14`, and `.python-version` pins `3.13.14` for this checkout.
- The approved repository-local `uv 0.11.29` executable at `.tools/uv-0.11.29/bin/uv`.

The `.tools/` directory is intentionally ignored by Git. A fresh clone therefore needs the approved `uv` artifact to be provisioned through the project maintainer's trusted, checksum-verifying process before installation. This repository does not contain a bootstrap script for that step. Do not silently substitute a system `uv`, pipe a remote installer into a shell, or run `uv self update`.

Before continuing, verify the provisioned executable:

```bash
.tools/uv-0.11.29/bin/uv --version
```

The output must begin with `uv 0.11.29`.

## Installation

1. Clone the public repository and enter it:

   ```bash
   git clone https://github.com/alexzhu0/skillscout.git
   cd skillscout
   ```

2. Confirm that the approved repository-local `uv` executable described above has been provisioned.

3. Create or update the project environment strictly from `uv.lock`:

   ```bash
   .tools/uv-0.11.29/bin/uv sync --locked
   ```

Keep `--locked` on every documented `uv sync` and `uv run` command. If `pyproject.toml` and `uv.lock` disagree, the command must fail instead of resolving a different dependency set.

## First Run: Safe Offline Fixture

The bundled fixture is local, deterministic input. This command does not contact GitHub or a semantic provider and cannot publish anything.

1. Create a fresh ignored workspace:

   ```bash
   mkdir -p .tmp
   demo_dir="$(mktemp -d .tmp/getting-started.XXXXXX)"
   ```

2. Run the complete fixture profile:

   ```bash
   .tools/uv-0.11.29/bin/uv run --locked skillscout dry-run \
     --fixture tests/fixtures/pipeline/approved.json \
     --state "$demo_dir/state.db" \
     --output "$demo_dir/output"
   ```

3. Confirm the compact JSON output contains these stable fields:

   ```json
   {
     "last_stage": "publication_planner",
     "remote_writes_attempted": 0,
     "status": "planned_not_published"
   }
   ```

The result also contains a generated `run_id`, `reused_stage_count`, and `publication_plan_path`. The local plan is not a Draft PR and grants no publication authority.

Never clone a candidate repository for SkillScout, install its dependencies, import its modules, or run its scripts. The live repository path uses bounded GitHub REST reads and treats all returned content as untrusted data.

## Optional Semantic-Provider Smoke

This step is not offline: it reads a public GitHub repository and makes a billed semantic-provider request. Use only a subject JSON file that you created or reviewed yourself. The `extract-repo` command reads repository content as data; it does not execute source-repository code.

The default provider is OpenAI. `SKILLSCOUT_LLM_PROVIDER=deepseek` selects the closed DeepSeek profile, which fixes extraction, generation, and review to `deepseek-v4-flash`. DeepSeek also requires `DEEPSEEK_BASE_URL` to normalize exactly to `https://api.deepseek.com`; other endpoints fail closed.

Inject the selected provider credential through your approved secret mechanism before running the command:

- OpenAI reads `OPENAI_API_KEY`.
- DeepSeek reads `DEEPSEEK_API_KEY`.

Do not put a credential in the subject JSON, source tree, command arguments, state database, prompt, or documentation. For a DeepSeek smoke, keep the secret out of the command itself:

```bash
export SKILLSCOUT_LLM_PROVIDER='deepseek'
export DEEPSEEK_BASE_URL='https://api.deepseek.com'

mkdir -p .tmp
smoke_dir="$(mktemp -d .tmp/semantic-smoke.XXXXXX)"
.tools/uv-0.11.29/bin/uv run --locked skillscout extract-repo \
  --subject <reviewed-subject.json> \
  --state "$smoke_dir/phase2.db" \
  --output "$smoke_dir/output"
```

The reviewed subject must match the strict repository-subject shape:

```json
{
  "schema_version": "1",
  "subject_id": "repo:owner/repository",
  "repository": "https://github.com/owner/repository"
}
```

For public GitHub reads, `SKILLSCOUT_GITHUB_TOKEN` is optional. If your environment supplies one for rate limits, keep it read-scoped and inject it without writing it to disk.

## Protected Publication Prerequisites

Do not run `publish-candidate` as a local getting-started step. Live publication is admitted only through the manually dispatched `.github/workflows/publish-candidate.yml` workflow after Phase 2 and Phase 3 have produced the exact durable evidence expected by the gate.

The protected path requires all of the following:

- Canonical candidate, Phase 2 state, Phase 3 state, and dedicated publication-state locators beneath the workflow's fixed `evidence/` and `state/` roots.
- Successful unprivileged evidence admission followed by `verify-publication-admission --compare-env` inside the protected job.
- The protected GitHub environment `skillscout-catalog-publish`.
- Catalog-bound authority variables and `SKILLSCOUT_PUBLICATION_POLICY_VERSION=publication-policy-v1`.
- A repository-scoped GitHub App whose installation token is minted only after protected admission, with only the required Contents and Pull Requests permissions.
- Configured individual human reviewers. The automated endpoint is a Draft PR; SkillScout does not approve, merge, enable auto-merge, or mark it ready for review.

<!-- VERIFY: Confirm in GitHub settings that the skillscout-catalog-publish environment has the intended required reviewers and deployment protections, and that the GitHub App installation cannot bypass default-branch or merge protections. -->

See [Configuration](CONFIGURATION.md) for the complete protected variable and secret inventory.

## Common Setup Issues

### `.tools/uv-0.11.29/bin/uv` is missing

Because `.tools/` is ignored, Git does not restore this executable. Stop and obtain the approved, checksum-verified `uv 0.11.29` artifact through the maintainer's trusted provisioning process. Do not replace it with an arbitrary system installation.

### Python or dependency resolution is rejected

Check `.python-version` and `pyproject.toml`: this checkout pins CPython `3.13.14` and accepts only Python `>=3.13,<3.14`. Run `uv sync --locked`; do not remove `--locked` or regenerate `uv.lock` merely to bypass a mismatch.

### The offline run reports `state_operation_failed`

Use a fresh state file and output directory under an owner-controlled, non-symlink directory. Do not reuse one path for state and output, and do not use group- or world-writable output locations.

### A DeepSeek smoke fails before making a request

Confirm that `SKILLSCOUT_LLM_PROVIDER` is exactly `deepseek`, `DEEPSEEK_BASE_URL` is exactly `https://api.deepseek.com` with at most one trailing slash, and `DEEPSEEK_API_KEY` is present in the process environment. Rejected configuration values are intentionally not echoed.

## Next Steps

- Read [Architecture](ARCHITECTURE.md) for the stage boundaries and data flow.
- Read [Configuration](CONFIGURATION.md) before configuring any live provider or protected publication environment.
- Read [Development](DEVELOPMENT.md) for contributor setup and code-quality commands.
- Read [Testing](TESTING.md) for the offline test suites, fixtures, and live-canary boundary.
