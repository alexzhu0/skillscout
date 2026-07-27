<!-- generated-by: gsd-doc-writer -->
<!-- GSD:DOC generated -->

# Configuration

SkillScout is configured through command-line paths and a small, closed set of environment variables. It does not load a repository `.env` file or a general application config file. Keep local development settings, semantic-provider credentials, and protected publication authority separate.

## Local development

Install the locked Python 3.13 environment before running commands:

```bash
uv sync --locked
```

Pass state, evidence, and output locations explicitly. The CLI does not define default paths.

| Command | Path arguments |
|---|---|
| `skillscout dry-run` | `--fixture`, `--state`, `--output` |
| `skillscout extract-repo` | `--subject`, `--state`, `--output` |
| `skillscout build-candidate` | `--candidate`, `--phase2-state`, `--state`, `--output` |
| `skillscout inspect-run` | `--state` |
| `skillscout verify-publication-admission` | `--candidate`, `--phase2-state`, `--phase3-state` |
| `skillscout publish-candidate` | `--candidate`, `--phase2-state`, `--phase3-state`, `--publication-state` |

Example with placeholders:

```bash
uv run skillscout extract-repo \
  --subject <path-to-subject-json> \
  --state <path-to-phase2-state-db> \
  --output <empty-output-directory>
```

For `build-candidate`, the candidate descriptor, Phase 2 database, Phase 3 database, and output directory must not resolve to the same existing filesystem object. An existing output path must be an empty directory owned by the current user and must not be group- or world-writable.

`SKILLSCOUT_GITHUB_TOKEN` is optional for public-repository reads: `GitHubReadClient` omits the authorization header when it is absent. If supplied locally, inject it through the process environment and use a placeholder in examples:

```bash
export SKILLSCOUT_GITHUB_TOKEN='<github-read-credential>'
```

Do not store the value in source files, command output, state databases, prompts, or documentation.

## Semantic provider

`SKILLSCOUT_LLM_PROVIDER` selects one of exactly two providers. The default is `openai`; any value other than `openai` or `deepseek` fails closed.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SKILLSCOUT_LLM_PROVIDER` | Optional | `openai` | Closed provider selector: `openai` or `deepseek`. |
| `OPENAI_API_KEY` | Required when provider is `openai` | None | Credential read when the semantic client is created. |
| `DEEPSEEK_API_KEY` | Required when provider is `deepseek` | None | Credential read when the DeepSeek-compatible client is created. |
| `DEEPSEEK_BASE_URL` | Required when provider is `deepseek` | None | Must normalize exactly to `https://api.deepseek.com`; one trailing slash is accepted and removed. Other or missing values fail closed. |

### OpenAI default

With `SKILLSCOUT_LLM_PROVIDER` unset or set to `openai`, extraction, generation, and review use `gpt-5.6-terra` and read `OPENAI_API_KEY`.

```bash
export SKILLSCOUT_LLM_PROVIDER='openai'
export OPENAI_API_KEY='<openai-credential>'
```

### DeepSeek

DeepSeek is enabled only with all three settings below. Extraction, generation, and review then use `deepseek-v4-flash`.

```bash
export SKILLSCOUT_LLM_PROVIDER='deepseek'
export DEEPSEEK_API_KEY='<deepseek-credential>'
export DEEPSEEK_BASE_URL='https://api.deepseek.com'
```

The implementation pins the official base URL instead of accepting arbitrary compatible endpoints. Semantic SDK clients use zero SDK retries. Provider identity and model names may be persisted for audit, but credential values are deliberately excluded from the settings representation.

## Limits and fixed defaults

These limits are defined in source and are not environment-variable overrides.

| Area | Fixed value |
|---|---:|
| Repository files read per candidate | 25 |
| Source files read per candidate | 5 |
| Bytes per repository file | 131,072 |
| Total repository bytes | 524,288 |
| Estimated semantic input tokens | 40,000 |
| Early-stop soft token target | 24,000 |
| Extracted workflows per repository | 3 |
| Extraction output tokens | 8,000 |
| Phase 3 candidates | 3 |
| Generator attempts per candidate | 3 |
| Reviewer attempts per candidate | 3 |
| Generator input bytes | 65,536 |
| Generator output tokens | 6,000 |
| Reviewer input bytes | 262,144 |
| Reviewer output tokens | 2,000 |

Changing these values requires a code change and corresponding contract/test updates.

## Protected publication configuration

Live publication is isolated in `.github/workflows/publish-candidate.yml`. The `publish` job uses the protected GitHub environment named `skillscout-catalog-publish`; the earlier `admit` job has only repository read permission and does not receive publication credentials.

<!-- VERIFY: Confirm that the skillscout-catalog-publish GitHub environment has the intended required reviewers, deployment protections, and restricted variable/secret access in repository settings. -->

### GitHub environment variables

Configure these as GitHub Actions variables for the protected publication environment or repository, according to the repository's administration policy:

| Variable | Required | Default | Validation and purpose |
|---|---|---|---|
| `SKILLSCOUT_CATALOG_REPOSITORY_ID` | Required | None | Positive decimal repository ID; leading zero is rejected. |
| `SKILLSCOUT_CATALOG_FULL_NAME` | Required | None | Target catalog in `owner/repository` form. |
| `SKILLSCOUT_CATALOG_BASE_BRANCH` | Required | None | Catalog branch name; a full `refs/heads/...` value is rejected by the domain grammar. |
| `SKILLSCOUT_CATALOG_REVIEWERS` | Required | None | Comma-separated individual GitHub logins. Entries are trimmed, deduplicated, sorted, and limited to 16. Empty entries are rejected. |
| `SKILLSCOUT_CATALOG_TEAM_REVIEWERS` | Optional compatibility setting | Empty | Must be absent or blank. Any non-blank value fails closed. |
| `SKILLSCOUT_PUBLICATION_POLICY_VERSION` | Required | None | Must equal `publication-policy-v1`. |
| `SKILLSCOUT_CATALOG_OWNER` | Required by workflow | None | Owner passed to the GitHub App token action. |
| `SKILLSCOUT_CATALOG_REPOSITORY` | Required by workflow | None | Repository selection passed to the GitHub App token action. |

Use deployment-specific placeholders when provisioning these values:

```text
SKILLSCOUT_CATALOG_REPOSITORY_ID=<catalog-repository-id>
SKILLSCOUT_CATALOG_FULL_NAME=<catalog-owner>/<catalog-repository>
SKILLSCOUT_CATALOG_BASE_BRANCH=<catalog-base-branch>
SKILLSCOUT_CATALOG_REVIEWERS=<reviewer-login>
SKILLSCOUT_CATALOG_TEAM_REVIEWERS=
SKILLSCOUT_PUBLICATION_POLICY_VERSION=publication-policy-v1
SKILLSCOUT_CATALOG_OWNER=<catalog-owner>
SKILLSCOUT_CATALOG_REPOSITORY=<catalog-repository>
```

<!-- VERIFY: Confirm the actual catalog repository ID, owner, repository name, base branch, and authorized individual reviewers in the protected GitHub environment. -->

### GitHub App secrets and runtime token

| Name | Source | Behavior |
|---|---|---|
| `SKILLSCOUT_GITHUB_APP_ID` | GitHub Actions secret | Passed to the pinned GitHub App token action after protected admission succeeds. |
| `SKILLSCOUT_GITHUB_APP_PRIVATE_KEY` | GitHub Actions secret | Passed directly to the token action; it must never be copied into files or logs. |
| `SKILLSCOUT_GITHUB_TOKEN` | Workflow-generated environment variable | Receives the short-lived installation token only for the final publication step. The application reads it lazily after local admission and publication-ledger checks. |

The token action requests `contents: write` and `pull-requests: write` for the selected catalog repository. The workflow checks out source with `persist-credentials: false` and ends publication at a Draft Pull Request.

<!-- VERIFY: Confirm in GitHub App and target-repository settings that the installation is restricted to the intended catalog repository and cannot bypass default-branch or merge protections. -->

### Publication workflow inputs and handoff

The manually dispatched workflow requires four relative locators:

| Input | Required shape |
|---|---|
| `candidate_descriptor` | Candidate descriptor beneath `evidence/` |
| `phase2_state_locator` | Phase 2 state beneath `state/` |
| `phase3_state_locator` | Phase 3 state beneath `state/` |
| `publication_state_locator` | Dedicated publication state beneath `state/` |

Admission validates candidate, Phase 2, and Phase 3 locators as ASCII, relative, canonical POSIX-style paths with no traversal components. The application-side locator validator limits them to 255 ASCII bytes and requires the expected `evidence/` or `state/` root.

The `admit` job emits canonical locators and SHA-256 evidence digests. The protected job maps them to `SKILLSCOUT_EXPECTED_*` variables and runs `verify-publication-admission --compare-env`; operators should not set or edit these handoff variables manually. The workflow also derives `SKILLSCOUT_PROTECTED_PUBLICATION_INTENT_DIGEST` and `SKILLSCOUT_PROTECTED_ADMISSION_DIGEST` inside the protected job.

The complete workflow-generated comparison set is:

- `SKILLSCOUT_EXPECTED_CANDIDATE_DESCRIPTOR_LOCATOR`
- `SKILLSCOUT_EXPECTED_PHASE2_STATE_LOCATOR`
- `SKILLSCOUT_EXPECTED_PHASE3_STATE_LOCATOR`
- `SKILLSCOUT_EXPECTED_CANDIDATE_DESCRIPTOR_DIGEST`
- `SKILLSCOUT_EXPECTED_PHASE2_CHAIN_DIGEST`
- `SKILLSCOUT_EXPECTED_TERMINAL_SUMMARY_DIGEST`
- `SKILLSCOUT_EXPECTED_PACKAGE_DIGEST`
- `SKILLSCOUT_EXPECTED_MANIFEST_DIGEST`
- `SKILLSCOUT_EXPECTED_VALIDATION_REPORT_DIGEST`
- `SKILLSCOUT_EXPECTED_REVIEW_ATTESTATION_DIGEST`

## Required versus optional settings

- Local `dry-run` needs no remote credential.
- `extract-repo` needs semantic-provider credentials and may use `SKILLSCOUT_GITHUB_TOKEN` for authenticated public GitHub reads.
- `build-candidate` needs the selected provider credential.
- Selecting DeepSeek additionally requires the exact official `DEEPSEEK_BASE_URL`.
- `verify-publication-admission` without `--compare-env` does not load publication authority or a publication token.
- `verify-publication-admission --compare-env` requires the canonical `SKILLSCOUT_EXPECTED_*` handoff and catalog authority variables.
- `publish-candidate` requires the protected authority variables and a non-empty `SKILLSCOUT_GITHUB_TOKEN`.

Missing or malformed semantic and protected-publication configuration is intentionally converted to a sanitized failure rather than echoing the rejected value.

## Config files and per-environment overrides

`pyproject.toml` pins the supported Python range and dependencies; `uv.lock` supplies reproducible dependency resolution. `.github/workflows/publish-candidate.yml` defines the protected publication job and its variable/secret bindings. There is no application YAML/JSON/TOML configuration schema beyond project metadata, and no checked-in development, test, staging, or production `.env` override mechanism.

Use the host process environment for local semantic work and GitHub Actions environment/repository settings for publication. Do not commit local credential files. If a local shell setup is needed, keep it outside the repository and use only placeholder documentation.
