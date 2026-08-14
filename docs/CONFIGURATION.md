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

### Phase 6 fresh-campaign preflight

The `preflight-fresh-campaign` choice in `.github/workflows/phase6-acceptance.yml` is a read-only diagnostic route for a failed or uncertain fresh nomination. It uses the protected `phase6-fresh-nomination` environment and only the source/state read credentials already required by that environment:

| Secret | Scope |
|---|---|
| `SKILLSCOUT_FRESH_NOMINATION_STATE_GITHUB_TOKEN` | Read the fixed `skillscout-state` repository and immutable state branch. |
| `github.token` (mapped to `SKILLSCOUT_SOURCE_GITHUB_TOKEN`) | Read the reviewed public GitHub Search endpoint. |

The command performs, in order, state-repository identity verification, a split bounded immutable restore (lineage proof and payload validation each retain a 45-second hard resolver cap), and exactly one Search page for each reviewed query. The subsequent state-only `prepare-fresh-campaign` path reuses the restore's compact lineage cache for its one CAS parent proof, so it does not repeat the full history walk; the cache contains no database or object payloads. It does not call candidate `get_repo_metadata`, resolve candidate commits, read candidate licenses, open a state store/CAS, call a semantic provider, run candidate code, or access catalog/publication credentials. Its JSON output contains only closed stage labels, durations, validated request identifiers and rate facts, counts, and immutable state digests. A failure is returned with a stage label, a safe restore subphase (`ref`, `lineage`, or `payload`) when known, and a non-sensitive error code; raw URLs, headers, response bodies, exception text, and credentials are never emitted.

Because this route reads current remote state, its result is diagnostic evidence only. It does not authorize a nomination, benchmark lock, live authority, model call, or publication. Any workflow-byte change invalidates previously recorded Phase 6 source/workflow approvals and requires a new exact approval before a fresh nomination.

### Phase 6 live-acceptance authority

The Phase 6 live path is ordered and single-use: `rebind-benchmark-lock → record-live-authority → run-benchmark → run-replay`. It runs only after the implementation is merged and the final `main` source, Phase 6 workflow bytes, manifest, and required control-plane names have been reverified. Any code or workflow change after that merge invalidates every approval in this sequence; stop and obtain a new exact approval packet rather than reusing a prior run or receipt.

The rebind has two distinct non-secret acceptance-run IDs. `SKILLSCOUT_PHASE6_SOURCE_ACCEPTANCE_RUN_ID` identifies the historical run that already owns the approved five-entry selection and V2 lock. `SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID` is a new, empty target run, chosen and set **before** dispatching `rebind-benchmark-lock`. The protected `phase6-human-benchmark-lock` job reads the fixed-host approval metadata with `github.token`, admits the canonical handoff before restoring state, then maps the environment secret `SKILLSCOUT_BENCHMARK_LOCK_STATE_GITHUB_TOKEN` to process-local `SKILLSCOUT_STATE_GITHUB_TOKEN` only for the final rebind persistence command. That command atomically records the target-run rebind reference and replacement V2 lock. It emits only the sanitized fields `source_acceptance_run_id`, `acceptance_run_id`, `rebind_digest`, `lock_digest`, `state_commit_sha`, `state_root_digest`, and `status=benchmark_lock_rebound`; failures are a closed diagnostic and do not authorize a retry. The rebind job has no DeepSeek/OpenAI, catalog, publication, candidate-source, or Pull Request credential or capability.

`record-live-authority` accepts only `--acceptance-run-id`; it does not accept caller-supplied authority JSON, actor, approval prose, receipt, or endpoint. In `skillscout-phase6-live-authority`, it records exactly one V2 `acceptance_live_authority` fact through the state-branch compare-and-swap boundary, then rebuilds and re-admits it. It cannot call a model, read source repositories, create a catalog branch, open a Pull Request, approve, merge, or mark a Pull Request ready. Its sanitized successful receipt contains `acceptance_run_id`, `authority_digest`, `authority_state_commit_sha`, `authority_state_root_digest`, the original bound `source_commit_sha`, `state_commit_sha`, `state_root_digest`, state repository identity, and `status=live_authority_persisted`.

Only after that receipt has persisted successfully, set these four non-secret repository variables from the exact receipt: `SKILLSCOUT_PHASE6_AUTHORITY_STATE_COMMIT_SHA`, `SKILLSCOUT_PHASE6_AUTHORITY_STATE_ROOT_DIGEST`, `SKILLSCOUT_PHASE6_AUTHORITY_DIGEST`, and the already chosen `SKILLSCOUT_PHASE6_ACCEPTANCE_RUN_ID`. A mismatch or an existing authority fact stops the campaign; neither is retry authority. `run-benchmark` and `run-replay` first check out and re-admit that exact immutable carrier before they can receive the DeepSeek credential. The resolver proves the authority predecessor-to-carrier edge, byte-compares the checked-out carrier, then permits at most 159 later transitions (160 total typed campaign transitions). The carrier is a recovery anchor, not a credential or a bypass for state verification.

The four human checkpoints for this slice are: approve the exact final-`main` rebind packet; approve the single `phase6-human-benchmark-lock` rebind dispatch; approve the single `skillscout-phase6-live-authority` recording dispatch; and inspect the completed benchmark/replay evidence before deciding whether to authorize the separate Gate B4 and Draft-publication slice. The fourth checkpoint does not itself create a catalog branch, request reviewers, or publish a Draft PR.

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
