<!-- generated-by: gsd-doc-writer -->
<!-- GSD:DOC generated -->

# Configuration

SkillScout is configured through command-line paths, a versioned discovery-query file, and a small, closed set of environment variables. It does not load a repository `.env` file or a general application config file. Keep local development settings, discovery/state credentials, semantic-provider credentials, and protected publication authority separate.

## Local development

Install the locked Python 3.13 environment before running commands:

```bash
.tools/uv-0.11.29/bin/uv sync --locked
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
| `skillscout discover` | `--state-repository-id`, `--state-repository-full-name`, `--initial-state-root-digest` |
| `skillscout publish-discovered` | `--handoff` |

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

For a local discovery run, first inject the source-read, state-branch, and selected semantic-provider credentials into the process environment. Then run the locked command with non-secret identity arguments:

```bash
.tools/uv-0.11.29/bin/uv run --locked skillscout discover \
  --state-repository-id <state-repository-id> \
  --state-repository-full-name <state-owner>/<state-repository> \
  --initial-state-root-digest sha256:<64-lowercase-hex-characters>
```

`publish-discovered` is the protected workflow handoff command, not an ordinary local-development command. It requires an exact persisted-state handoff and catalog authority that are introduced only after protected re-admission.

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

DeepSeek is enabled only with all three settings below. Extraction and generation use `deepseek-v4-flash`; the independent review stage uses `deepseek-v4-pro`.

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
| Discovery repositories admitted per run | 100 |
| Discovery repositories reserved for semantic processing per run | 20 |
| Protected discovery handoff candidates | 60 |
| Protected discovery handoff bytes | 65,536 |

Changing these values requires a code change and corresponding contract/test updates.

## Automated discovery operations

The hosted entry point is `.github/workflows/discover.yml`. It runs every day at `03:17 UTC` from cron expression `17 3 * * *` and also accepts `workflow_dispatch` with no candidate-controlled inputs. Scheduled and manual runs share concurrency group `skillscout-production` with `cancel-in-progress: false`; GitHub may replace a pending run, but it does not cancel the active production run.

The workflow executes the reviewed query set in `config/discovery-queries-v1.json`: four fixed public, non-archived repository searches, 25 results per page, at most four pages per query, acquired round-robin and ordered by most recently updated. Runtime input cannot replace or extend these queries. Deterministic reservations cap each run at 100 deduplicated repositories and 20 repositories admitted to semantic processing; resume and confirmed retry reuse the recorded reservations and do not widen either budget.

The hosted discovery job selects `deepseek`, fixes `DEEPSEEK_BASE_URL` to `https://api.deepseek.com`, and runs:

```bash
uv run --locked python -m skillscout.cli discover \
  --state-repository-id "$STATE_REPOSITORY_ID" \
  --state-repository-full-name "$STATE_REPOSITORY_FULL_NAME" \
  --initial-state-root-digest "$INITIAL_STATE_ROOT_DIGEST"
```

The protected job accepts only a bounded metadata handoff, re-reads the exact state commit, re-derives every candidate admission, and then runs:

```bash
uv run --locked python -m skillscout.cli publish-discovered \
  --handoff /tmp/skillscout-discovery-handoff.json
```

Do not treat the temporary handoff as publication authority. It contains canonical locators and digests only; the protected job independently reconstructs authority from the exact persisted state.

### Discovery and state variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SKILLSCOUT_STATE_REPOSITORY_ID` | Required for hosted state readback and protected publication | None | Positive decimal identity of the repository that owns the state branch. |
| `SKILLSCOUT_STATE_REPOSITORY_FULL_NAME` | Required for hosted state readback and protected publication | None | State repository in `owner/repository` form. |
| `SKILLSCOUT_INITIAL_STATE_ROOT_DIGEST` | Required by the hosted discovery job | None | Trusted `sha256:` root digest used to bind the initial or expected state lineage. |
| `SKILLSCOUT_SOURCE_GITHUB_TOKEN` | Required by `discover` | None | Source-zone credential used only for bounded public GitHub Search and repository reads. |
| `SKILLSCOUT_STATE_GITHUB_TOKEN` | Required by `discover` and `publish-discovered` | None | State-zone credential used only for the fixed state repository and state ref. |

The workflow maps the three non-secret repository settings to the shorter process-local names `STATE_REPOSITORY_ID`, `STATE_REPOSITORY_FULL_NAME`, and `INITIAL_STATE_ROOT_DIGEST` only for the `discover` command. The application-facing state names remain `SKILLSCOUT_STATE_REPOSITORY_ID` and `SKILLSCOUT_STATE_REPOSITORY_FULL_NAME` in the protected job.

For this MVP, the scheduled `discover` and `nominate-benchmark` commands accept only the reviewed `alexzhu0/skillscout` state repository (numeric identity `1310897029`). This is intentional: their code-reviewed state-lineage baseline is meaningful only for that repository. They do not accept an environment or CLI override for the anchor. The baseline covers at most 4,096 state edges; if it is reached, the run fails closed and a human must land a reviewed anchor-roll change. The workflow never rolls that trust point by itself.

<!-- VERIFY: Confirm the actual state repository ID, full name, initial root digest, and repository-variable scoping in GitHub Actions settings. -->

### Phase 6 live-acceptance authority

The `record-live-authority` Phase 6 dispatch action accepts only a canonical, non-secret `LiveAcceptanceAuthorityV1` JSON object. It is restricted to the configured reviewer identity and verifies the exact source commit, workflow bytes, locked five-repository manifest, state root, provider policy, prompt/schema versions, and 100/20 budgets before it opens the state credential. It writes one immutable `acceptance_live_authority` fact through the state-branch compare-and-swap boundary; it cannot call a model, read source repositories, create a catalog branch, open a Pull Request, approve, merge, or mark a Pull Request ready.

The authority object is not a secret. Still, do not edit its JSON after approval or substitute its `acceptance_run_id`. Record the resulting immutable authority-state commit, root digest, authority digest, and acceptance-run ID in the four `SKILLSCOUT_PHASE6_AUTHORITY_*` / `SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID` repository variables before dispatching `run-benchmark` or `run-replay`. Those later jobs check out the configured state repository at that exact authority-carrier commit, re-check both the checkout HEAD and root digest, and require the resolver proof to begin with the immutable authority predecessor followed immediately by that same carrier commit/root before they receive `DEEPSEEK_API_KEY`. The resolver proves that one predecessor-to-carrier edge separately, byte-compares the remote carrier with the checked-out bundle, then permits at most 159 later transitions (160 total typed campaign transitions). Human-review attestation, probe-cleanup attestation, and report rebuild use the same non-secret carrier pair; if it is absent or malformed, they fail before opening the state credential. Ordinary acceptance-state reads remain limited to 160 lineage edges from that carrier. The carrier is a bounded recovery anchor, not a credential or a bypass for state verification.

### Durable state branch

Discovery state is fixed to `refs/heads/skillscout-state`; it is not a CLI-selectable ref. The branch contains:

```text
state/root.json
state/databases/pipeline.sqlite3
state/databases/operations.sqlite3
state/databases/publication.sqlite3
state/objects/sha256/<prefix>/<digest>.json
```

The three databases have separate owners: pipeline execution, operations/reservations, and publication reconciliation. Canonical JSON evidence is content-addressed under `state/objects/sha256/`, and `state/root.json` binds the database/object projection to its parent commit and policy digests. Synchronization uses non-force fast-forward updates and exact post-write readback; state conflicts fail closed.

### Two credential zones

1. The unprotected `discovery` job has repository `contents: write` so its workflow-scoped `github.token` can serve as both `SKILLSCOUT_SOURCE_GITHUB_TOKEN` and `SKILLSCOUT_STATE_GITHUB_TOKEN`. The DeepSeek credential is available only to this job's semantic stages. This zone can read public sources and advance the fixed state branch, but it receives no catalog GitHub App private key or catalog installation token.
2. The `protected_publication` job uses the protected environment `skillscout-catalog-publish`, has repository `contents: read`, and uses `github.token` only as `SKILLSCOUT_STATE_GITHUB_TOKEN` to re-read the exact state commit. Only after re-admission does the pinned token action receive `SKILLSCOUT_GITHUB_APP_ID` and `SKILLSCOUT_GITHUB_APP_PRIVATE_KEY` and mint a catalog-repository installation token for `contents: write` and `pull-requests: write`. That short-lived token is exposed as `SKILLSCOUT_GITHUB_TOKEN` only to the final Draft-publication step.

<!-- VERIFY: Confirm that the workflow token's repository identity matches the configured state repository and that job/environment secret scoping enforces the two documented credential zones. -->

### Hosted identity and Gate B4 binding

The current repository bytes have these SHA-256 identities:

| Surface | SHA-256 |
|---|---|
| Automated discovery workflow | `8157cb686b9bf18bfa800811b1fe1529ed9a15ec371fe36ec1708233052b7cfd` |
| Manual publication workflow | `96ce9f39db49ce647a88b83ec4db3cb0135e5cf51c1eb2f11961cfd243b23cf0` |
| Controlled Gate B4 canary workflow | `9c59cd9822eecec913f82d24c7880a443ba9416795b8996c6201f33c4df5805d` |

The fresh hosted Gate B4 approval is bound to the exact workflow bytes plus the reviewed GitHub App scope, catalog, ruleset, protected environment, reviewer configuration, installation identity, causal denial results, and separate human/admin cleanup.

Any change to the workflow, App scope, catalog, ruleset, protected-environment configuration, required-reviewer configuration, or installation identity invalidates that evidence and requires a fresh Gate B4 run.

## Protected publication configuration

Manual single-candidate publication is isolated in `.github/workflows/publish-candidate.yml`. Its `publish` job uses the protected GitHub environment named `skillscout-catalog-publish`; the earlier `admit` job has only repository read permission and does not receive publication credentials. Automated discovery uses the same protected environment in `.github/workflows/discover.yml`, but independently re-reads the exact persisted state before token minting.

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
- `discover` needs `SKILLSCOUT_SOURCE_GITHUB_TOKEN`, `SKILLSCOUT_STATE_GITHUB_TOKEN`, the three state identity arguments, and the selected provider credential.
- Selecting DeepSeek additionally requires the exact official `DEEPSEEK_BASE_URL`.
- `verify-publication-admission` without `--compare-env` does not load publication authority or a publication token.
- `verify-publication-admission --compare-env` requires the canonical `SKILLSCOUT_EXPECTED_*` handoff and catalog authority variables.
- `publish-candidate` requires the protected authority variables and a non-empty `SKILLSCOUT_GITHUB_TOKEN`.
- `publish-discovered` requires the exact protected handoff, state repository variables, `SKILLSCOUT_STATE_GITHUB_TOKEN`, protected catalog authority, and the late-minted `SKILLSCOUT_GITHUB_TOKEN`.

Missing or malformed semantic and protected-publication configuration is intentionally converted to a sanitized failure rather than echoing the rejected value.

## Config files and per-environment overrides

`pyproject.toml` pins the supported Python range and dependencies; `uv.lock` supplies reproducible dependency resolution. `config/discovery-queries-v1.json` is the only runtime policy JSON and must validate as the exact reviewed query set. `.github/workflows/discover.yml` defines daily/manual discovery, state persistence, and protected discovered-candidate publication; `.github/workflows/publish-candidate.yml` defines the manual single-candidate protected publication path. There is no general application YAML/JSON/TOML configuration schema and no checked-in development, test, staging, or production `.env` override mechanism.

Use the host process environment for local semantic/discovery work and GitHub Actions repository variables, secrets, and protected-environment settings for hosted operation. Do not commit local credential files. If a local shell setup is needed, keep it outside the repository and use only placeholder documentation.
