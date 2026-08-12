# Getting Started

This guide takes a maintained SkillScout checkout from locked dependency setup to its first safe, offline result. Live semantic-provider access and Draft PR publication are optional, separate steps with additional authority requirements. The automated operations path is implemented and Phase 5 is verified, but Phase 6 adversarial acceptance is still pending; do not treat this checkout as production-ready.

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

The default provider is OpenAI. `SKILLSCOUT_LLM_PROVIDER=deepseek` selects the closed DeepSeek profile: extraction and generation use `deepseek-v4-flash`, while independent review uses `deepseek-v4-pro`. DeepSeek also requires `DEEPSEEK_BASE_URL` to normalize exactly to `https://api.deepseek.com`; other endpoints fail closed.

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

## Local Extract, Build, and Inspect Flow

The single-repository commands expose the Phase 2 and Phase 3 boundaries for controlled development and diagnosis. They do not publish.

### Extract one reviewed repository

Use distinct state and output paths. Capture the bounded JSON result so its generated `run_id` can be inspected without querying the database directly:

```bash
mkdir -p .tmp
repo_run_dir="$(mktemp -d .tmp/repository-run.XXXXXX)"

.tools/uv-0.11.29/bin/uv run --locked skillscout extract-repo \
  --subject <reviewed-subject.json> \
  --state "$repo_run_dir/phase2.db" \
  --output "$repo_run_dir/phase2-output" \
  > "$repo_run_dir/extract-result.json"

phase2_run_id="$(
  .tools/uv-0.11.29/bin/uv run --locked python -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["run_id"])' \
    "$repo_run_dir/extract-result.json"
)"
```

On success, the result reports `status: "completed"`, `last_stage: "extractor"`, `remote_writes_attempted: 0`, and `publication_plan_path: "extraction-summary.json"`. The repository is read through bounded GitHub API calls and the selected semantic provider is called once per authorized attempt; source-repository code is never executed.

### Inspect the recorded Phase 2 run

`inspect-run` returns the durable JSON projection for an exact run ID:

```bash
.tools/uv-0.11.29/bin/uv run --locked skillscout inspect-run \
  "$phase2_run_id" \
  --state "$repo_run_dir/phase2.db" \
  --format json
```

The projection contains sanitized run, attempt, stage-result, and artifact metadata. It is intended for audit and recovery diagnosis, not as a source of publication authority.

### Build an admitted candidate

`build-candidate` requires a canonical candidate descriptor that binds one extracted workflow to the exact Phase 2 run and chain evidence. `extract-repo` writes the extraction summary but does not turn that summary into a trusted candidate descriptor for the shell. Use a descriptor produced by the reviewed coordinator or a controlled test harness; do not hand-edit an extraction result into one.

```bash
.tools/uv-0.11.29/bin/uv run --locked skillscout build-candidate \
  --candidate <canonical-candidate-descriptor.json> \
  --phase2-state "$repo_run_dir/phase2.db" \
  --state "$repo_run_dir/phase3.db" \
  --output "$repo_run_dir/phase3-output"
```

The candidate descriptor, Phase 2 database, Phase 3 database, and output directory must be four distinct filesystem objects. If the output directory already exists, it must be empty, owned by the current user, and not group- or world-writable. The command generates, validates, and independently reviews the candidate, but it has no publication authority.

## Automated Discovery Boundaries

The automated path deliberately separates two commands:

1. `skillscout discover` runs the unprotected discovery and Phase 2/3 graph. It uses the fixed query set, admits at most 100 deduplicated repositories, reserves at most 20 for semantic processing, persists the exact three-store state bundle to `refs/heads/skillscout-state`, and emits a bounded metadata handoff. It can read public source repositories, call the selected semantic provider, and update the dedicated state branch, but it cannot write to the Skill catalog.
2. `skillscout publish-discovered --handoff ...` is a protected-workflow command. In `.github/workflows/discover.yml`, an inline protected step first re-reads the exact state commit and derives every discovery publication admission before the catalog-scoped installation token is minted. After minting, `publish-discovered` independently re-reads that exact state commit and re-derives every candidate admission again before accessing the already-minted token. Only this boundary can create or reconcile Draft PRs.

Neither command is an offline dry run. Use the bundled `dry-run` fixture for local, no-network verification. Do not run `publish-discovered` from an ordinary developer shell or treat the handoff JSON as authority.

## Safe Manual GitHub Actions Run

The supported hosted entry point is [`.github/workflows/discover.yml`](../.github/workflows/discover.yml), named **Discover and publish eligible Skill drafts**. It runs daily at `03:17 UTC` and accepts `workflow_dispatch` without candidate-controlled inputs.

1. Confirm that the selected workflow revision is the exact reviewed revision and that the configuration in [Configuration](CONFIGURATION.md) is current. A workflow, App scope, catalog, ruleset, reviewer, protected-environment, or installation-identity change invalidates prior live evidence.
2. In the repository's **Actions** tab, select **Discover and publish eligible Skill drafts**, choose the reviewed revision, and select **Run workflow**. There are no repository, candidate, token, or key inputs to fill in.
3. Monitor the unprotected `discovery` job. It must finish and emit only the bounded state locators and digests before the protected job can proceed.
4. If GitHub requests approval for the `skillscout-catalog-publish` environment, approve it only under the project's operating policy. Do not copy a token, private key, PEM, or other credential into a workflow input, log, artifact, issue, or local file.
5. In `protected_publication`, verify that exact-state re-admission completes before the catalog-scoped GitHub App installation token step. Then review any resulting Draft PR manually.

Scheduled and manual runs share the `skillscout-production` concurrency group with `cancel-in-progress: false`. The workflow never approves, merges, enables auto-merge, or marks a PR ready for review.

## Protected Publication Prerequisites

Do not run `publish-candidate` or `publish-discovered` as a local getting-started step. The automated path above uses `.github/workflows/discover.yml`; `.github/workflows/publish-candidate.yml` remains the separately controlled single-candidate path. Both introduce catalog authority only inside the protected environment after exact evidence admission.

The protected path requires all of the following:

- Canonical candidate, Phase 2 state, Phase 3 state, and dedicated publication-state locators beneath the workflow's fixed `evidence/` and `state/` roots.
- For `.github/workflows/publish-candidate.yml`, successful unprivileged evidence admission followed by `verify-publication-admission --compare-env` inside the protected job; `.github/workflows/discover.yml` instead independently re-reads the exact state commit and derives discovery publication admissions before late token minting.
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

Check `.python-version` and `pyproject.toml`: this checkout pins CPython `3.13.14` and accepts only Python `>=3.13,<3.14`. Run `.tools/uv-0.11.29/bin/uv sync --locked`; do not remove `--locked` or regenerate `uv.lock` merely to bypass a mismatch.

### The offline run reports `state_operation_failed`

Use a fresh state file and output directory under an owner-controlled, non-symlink directory. Do not reuse one path for state and output, and do not use group- or world-writable output locations.

### A DeepSeek smoke fails before making a request

Confirm that `SKILLSCOUT_LLM_PROVIDER` is exactly `deepseek`, `DEEPSEEK_BASE_URL` is exactly `https://api.deepseek.com` with at most one trailing slash, and `DEEPSEEK_API_KEY` is present in the process environment. Rejected configuration values are intentionally not echoed.

## Next Steps

- Read [Architecture](ARCHITECTURE.md) for the stage boundaries and data flow.
- Read [Configuration](CONFIGURATION.md) before configuring any live provider or protected publication environment.
- Read [Development](DEVELOPMENT.md) for contributor setup and code-quality commands.
- Read [Testing](TESTING.md) for the offline test suites, fixtures, and live-canary boundary.
