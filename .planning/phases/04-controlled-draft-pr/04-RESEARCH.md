# Phase 4: Controlled Draft PR - Research

**Researched:** 2026-07-24  
**Domain:** GitHub REST publishing, GitHub App least privilege, idempotent Draft PR recovery, and CI/ruleset enforcement  
**Confidence:** MEDIUM

## User Constraints

No `CONTEXT.md` exists for this phase; the user explicitly chose to continue without phase discussion. [VERIFIED: phase init and codebase grep]

The binding constraints are therefore the Phase 4 goal, requirements `PUB-01` through `PUB-05` and `SEC-02`, the roadmap success criteria, and `AGENTS.md`. [VERIFIED: `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, and `AGENTS.md`]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PUB-01 | Publisher 只向配置的受控中央 Skill catalog 仓库创建或更新确定性机器分支、提交已验证 artifact、创建 Draft Pull Request，并请求配置的人类 reviewer 或 team。 | Use a catalog-bound publish authority, deterministic branch identity, a manifest-gated Git Data transaction, `draft: true`, and the review-request endpoint. [VERIFIED: codebase grep] [CITED: https://docs.github.com/en/rest/git] [CITED: https://docs.github.com/en/rest/pulls/pulls] [CITED: https://docs.github.com/en/rest/pulls/review-requests] |
| PUB-02 | Draft PR 正文必须包含来源仓库、commit SHA、许可证、workflow fingerprint、证据摘要、资格结果、安全/格式检查、独立审核结论及明确的人类审核提示。 | Render a deterministic body only from strict Phase 3 artifacts and include a bounded machine marker used for recovery. [VERIFIED: `src/skillscout/domain/skill_artifacts.py`, `qualification.py`, `validation.py`, and `review.py`] |
| PUB-03 | Publisher 不得设置 auto-merge、调用 merge API、批准 PR、把 Draft 标记为 ready for review、修改规则集或直接向默认分支写入。 | Expose a closed method-and-path REST allowlist; omit GraphQL entirely; reject the default ref in domain policy; omit merge, review-submission, ready, auto-merge, ruleset, and administration routes. [VERIFIED: codebase adapter pattern] [CITED: https://docs.github.com/en/rest/pulls/pulls] |
| PUB-04 | 发布身份使用最小权限短期 GitHub App installation token；catalog 默认分支 ruleset 必须在平台层阻止该身份直接写入、绕过人工审批或 merge。 | Scope the installation token to one catalog with Contents write and Pull requests write only, exclude Administration, keep the App out of every bypass list, and run positive/negative live canaries. [CITED: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app] [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets] |
| PUB-05 | Publisher 根据目标仓库、稳定 slug、发布分支和机器可读 PR marker 实现幂等；重复运行更新已有 Draft PR，并能在本地状态丢失时从远端恢复 Publication Record。 | Reconcile remote ref and PR before writes, require exactly one matching Draft, cross-check head/base/marker/commit trailer, use only fast-forward ref updates, and persist each completed remote step. [CITED: https://docs.github.com/en/rest/pulls/pulls] [CITED: https://docs.github.com/en/rest/git/refs] |
| SEC-02 | CI 使用最小 GitHub Actions 权限、固定第三方 Action commit SHA、受保护发布环境和结构化日志字段 allowlist；候选仓库数据不得直接插值到 shell 命令。 | Set default-deny workflow permissions, gate the App secret in a protected environment, pin every action to a full SHA, pass only validated identifiers as process arguments/environment values, and log a closed schema. [CITED: https://docs.github.com/en/actions/reference/security/secure-use] [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments] |
</phase_requirements>

## Summary

Phase 4 should be planned as a new, narrowly authorized publication subsystem that consumes the exact durable Phase 3 result; it must not turn the existing dry-run publisher or read-only GitHub adapter into a generic remote client. The current code already supplies the essential trust root: `CandidateTerminalSummaryV1` proves `eligible_local_candidate`, `FrozenSkillPackageV1` binds exact bytes to a canonical manifest and package digest, `ValidationReportV1` binds zero errors to that package, and `ReviewAttestationV1` binds the independent review. [VERIFIED: codebase grep] The Phase 4 admission gate should re-parse canonical durable bytes and re-check every digest relationship before minting a token or making any remote call. [VERIFIED: existing Phase 3 recovery and canonicalization patterns]

The safe write protocol is a reconcile-first state machine. Resolve the configured catalog and its default-branch SHA, derive one deterministic machine branch from the stable slug, recover any matching open PR by the exact `owner:head` and `base` filters plus a machine-readable body marker, and reject ambiguous or human-modified states. [CITED: https://docs.github.com/en/rest/pulls/pulls] Publish all files as one Git commit through Git blobs, a tree based on the observed head tree, and a commit whose parent is the observed head; update the ref with `force: false`. [CITED: https://docs.github.com/en/rest/git/trees] [CITED: https://docs.github.com/en/rest/git/commits] [CITED: https://docs.github.com/en/rest/git/refs] Create the PR with `draft: true`, then request only the configured users/teams. [CITED: https://docs.github.com/en/rest/pulls/pulls] [CITED: https://docs.github.com/en/rest/pulls/review-requests]

GitHub permission granularity is not sufficient by itself. `Contents: write`, which is required for Git objects and refs, is also sufficient for GitHub's merge endpoint; therefore the plan must prove the boundary at three layers: a production adapter with no forbidden routes, a default-branch ruleset where the App has no bypass, and a live canary using the real installation identity. [CITED: https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps] [CITED: https://docs.github.com/en/rest/pulls/pulls] This distinction is central to planning: platform enforcement must prove default-branch updates and merge fail, while adapter-surface tests prove there is no approve, ready-for-review, auto-merge, GraphQL, or ruleset-management capability. [VERIFIED: requirement decomposition]

**Primary recommendation:** Build a separate, catalog-bound `GitHubPublishClient` and publication state machine that admits only a canonical eligible Phase 3 bundle, performs reconcile-first fast-forward writes, and treats every ambiguity as `manual_intervention_required`. [VERIFIED: codebase patterns] [CITED: https://docs.github.com/en/rest/git/refs]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Phase 3 publication admission | API / Backend domain | Database / Storage | Strict models and digest checks decide whether bytes are publishable; durable artifacts supply the authority. [VERIFIED: Phase 3 domain and state code] |
| Deterministic branch/PR identity | API / Backend domain | GitHub service boundary | Repository ID, base, slug, branch, marker schema, and package digest are policy facts, not transport behavior. [VERIFIED: existing authority-model pattern] |
| Git object and PR operations | API / Backend adapter | GitHub REST API | Only the adapter should serialize provider requests and parse bounded responses. [VERIFIED: `GitHubReadClient` architecture] |
| Idempotency and crash recovery | API / Backend application | Database / Storage plus GitHub remote state | The application reconciles local checkpoints with ref/PR state; neither side alone is authoritative after a crash. [VERIFIED: current recovery architecture] |
| Default-branch and merge prevention | GitHub ruleset / service boundary | Backend adapter allowlist | The platform blocks ref updates/merge; the adapter removes routes the application never needs. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets] |
| Token issuance and secret access | GitHub Actions protected environment | GitHub App installation | The environment gates secret release; the installation token limits repository and permission scope and expires after one hour. [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments] [CITED: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app] |
| Human review and merge | Human / GitHub UI | GitHub ruleset | Automation requests review but cannot complete the approval/merge decision. [VERIFIED: requirements] [CITED: https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews] |

## Project Constraints (from AGENTS.md)

- Treat all external repository content as untrusted data and never as instructions, tool calls, or execution permission. [VERIFIED: `AGENTS.md`]
- Never clone-and-run, install source-repository dependencies, call source scripts, generate executable scripts, or execute candidate code. [VERIFIED: `AGENTS.md`]
- Automation stops at a Draft PR and cannot approve, publish, or merge a Skill. [VERIFIED: `AGENTS.md`]
- Publish only artifacts whose permissive repository license and attribution were already deterministically verified and retained downstream. [VERIFIED: `AGENTS.md`]
- GitHub credentials must be minimally scoped, runtime-injected, and absent from logs, databases, prompts, and PR content. [VERIFIED: `AGENTS.md`]
- Deterministic logic owns validation, safety, idempotency, content limits, and publication authority; an LLM must not participate in Phase 4 decisions. [VERIFIED: `AGENTS.md`]
- Preserve explicit versioned stage contracts, isolated retry, and auditable structured input/output. [VERIFIED: `AGENTS.md`]
- Use Python 3.13, direct GitHub REST calls through `httpx`, Pydantic contracts, SQLite/JSON audit state, GitHub Actions, and a short-lived GitHub App installation token. [VERIFIED: `AGENTS.md`]
- Keep GitHub Actions single-purpose and least-privileged; pin external actions to full commit SHAs; do not use Actions cache as durable state. [VERIFIED: `AGENTS.md`]
- Do not broaden the MVP to other forges, tenants, SDKs, event buses, databases, or auto-generated scripts. [VERIFIED: `AGENTS.md`]

## Standard Stack

### Core

| Library / Service | Version | Purpose | Why Standard |
|-------------------|---------|---------|--------------|
| Python | 3.13.14 in `.venv`; project range `>=3.13,<3.14` | Runtime and deterministic domain logic | Matches the established project runtime and is locally available. [VERIFIED: environment probe and `pyproject.toml`] |
| `httpx` | 0.28.1 | Serial GitHub REST transport | Already pinned and used by the read-only adapter; no SDK is needed for the small closed endpoint set. [VERIFIED: `pyproject.toml`, `uv.lock`, and import probe] |
| Pydantic | 2.13.4 | Strict request/response, policy, marker, and publication-record contracts | Existing project contracts use strict frozen models and validators. [VERIFIED: `pyproject.toml`, `uv.lock`, and codebase grep] |
| SQLite (`sqlite3`) | Python standard library | Local publication attempts, checkpoints, and records | Existing state architecture already provides transactional, content-addressed recovery patterns. [VERIFIED: `src/skillscout/adapters/state.py`] |
| GitHub REST API | `2022-11-28` | Git objects, refs, PRs, and reviewer requests | The codebase already pins this header; GitHub lists it as supported until 2028-03-10. [VERIFIED: `src/skillscout/adapters/github.py`] [CITED: https://docs.github.com/en/rest/about-the-rest-api/api-versions] |
| GitHub App installation token | One-hour token | Catalog-scoped authentication | Tokens can be narrowed to selected repositories and permissions and expire after one hour. [CITED: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app] |

### Supporting

| Library / Service | Version | Purpose | When to Use |
|-------------------|---------|---------|-------------|
| pytest | 9.1.1 | Contract, state-machine, transport, crash, and security tests | Use recorded `httpx.MockTransport` fixtures for every REST branch; reserve a separate opt-in live canary for platform permissions. [VERIFIED: environment probe and existing tests] |
| `actions/create-github-app-token` | Exact full commit SHA to be approved in a supply-chain gate | Mint and revoke a repository-scoped installation token in Actions | GitHub's official workflow guidance uses this GitHub-owned action; do not use a mutable `@v3` tag in the committed workflow. [CITED: https://docs.github.com/en/enterprise-cloud@latest/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow] [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |
| GitHub repository ruleset | Active catalog configuration | Enforce pull-request-only default-branch updates, human approval, and no App bypass | Configure before enabling production publication; verify with a canary. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets] |
| GitHub Actions protected environment | Catalog-specific environment | Gate access to the App private key and production catalog variables | Use only for the real publish job, not unit or dry-run jobs. [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Git Data API transaction | Contents API one file at a time | Contents calls expose partial multi-file publication after crashes; blob/tree/commit/ref makes the visible branch update atomic. [CITED: https://docs.github.com/en/rest/git/trees] |
| Direct `httpx` adapter | PyGithub or Octokit | An SDK expands dependency and capability surface; the project already chose a small direct REST wrapper. [VERIFIED: `AGENTS.md` and codebase] |
| Installation token | PAT | PATs are longer-lived, person-bound, and usually broader; the project explicitly forbids this choice. [VERIFIED: `AGENTS.md`] |
| Remote reconciliation | Trust local SQLite only | Local state can disappear on ephemeral runners; `PUB-05` requires remote reconstruction. [VERIFIED: `.planning/REQUIREMENTS.md`] |
| Fast-forward machine branch | Force update deterministic branch | Force update can overwrite human/divergent changes and destroys the conflict signal required by the roadmap. [CITED: https://docs.github.com/en/rest/git/refs] |

**Installation:** No new Python package is required for the Publisher. [VERIFIED: codebase and stack analysis]

The only new workflow dependency should be the GitHub-owned App-token action after an explicit full-SHA supply-chain decision; do not add it by tag. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]

## Architecture Patterns

### System Architecture Diagram

```text
Phase 3 durable bundle
  terminal summary + frozen package + qualification + validation + review
                            |
                            v
                Strict Publication Admission
        canonical bytes, cross-digests, eligible=true,
          zero validation errors, exact file manifest
                            |
                 reject ----+---- admit
                   |                 |
                   v                 v
          Audited no-write       Publication Intent
                           catalog repo ID + base
                           slug + branch + marker
                                      |
                                      v
                         Remote Reconciliation (GET)
                    repo/default ref, machine ref, open PRs
                                      |
             ambiguous/non-draft/     | clean/new/recoverable
             human divergence         |
                    |                 v
                    v        Blob -> Tree -> Commit
             Manual handling          |
                                      v
                         create/update ref force=false
                                      |
                                      v
                     create Draft or update title/body
                                      |
                                      v
                         request configured reviewers
                                      |
                                      v
                      verify remote state and persist
                           PublicationRecordV1

Service boundary: every remote operation passes through a closed REST
method+path allowlist. Default-branch writes and merge are additionally
blocked by an active GitHub ruleset with no App bypass.
```

The diagram reflects the current project's separation of domain contracts, application orchestration, adapters, and durable state. [VERIFIED: codebase architecture]

### Recommended Project Structure

```text
src/skillscout/
├── domain/
│   └── publication.py          # intent, marker, admission, transitions, records
├── application/
│   └── publication.py          # reconcile-first orchestrator and recovery
├── adapters/
│   ├── github_publish.py       # closed REST write/read endpoint surface
│   └── publication_state.py    # durable attempts/checkpoints/records
├── bootstrap.py                # explicit production wiring; dry-run unchanged
└── cli.py                      # publish command and safe public result
tests/
├── fixtures/github_publish/    # bounded provider responses
├── test_publication_domain.py
├── test_github_publish_adapter.py
├── test_publication_recovery.py
├── test_publication_security.py
└── test_publication_live_canary.py
.github/workflows/
└── publish-candidate.yml       # protected environment, pinned actions, least privilege
```

This structure follows existing module boundaries and keeps `REMOTE_WRITE` authority out of `GitHubReadClient`, `PhaseThreeApplication`, and the Phase 1 dry-run runner. [VERIFIED: codebase grep]

### Pattern 1: Canonical Phase 3 Admission Before Token Access

**What:** Load the completed Phase 3 projection from durable state, require the exact terminal outcome `eligible_local_candidate`, parse every artifact strictly, require canonical bytes, re-derive the frozen manifest/package identity, and cross-check terminal, validation, and review digests. [VERIFIED: Phase 3 contracts]

**When to use:** Before constructing a publication intent and before entering the protected environment step that exposes credentials. [VERIFIED: security decomposition]

**Required checks:**

1. `CandidateTerminalSummaryV1.eligible is True` and `outcome == "eligible_local_candidate"`. [VERIFIED: `domain/review.py`]
2. `FrozenSkillPackageV1` canonical bytes and `package_identity` equal the terminal summary. [VERIFIED: `domain/skill_artifacts.py`]
3. Every `RenderedManifestEntryV1` is present exactly once, has mode `0o644`, matches content hash and size, and maps only below `skills/{stable_slug}/`. [VERIFIED: `domain/skill_artifacts.py`]
4. Validation digest matches and error count is zero; review attestation digest and artifact/package identities match. [VERIFIED: `domain/validation.py` and `domain/review.py`]
5. Repository URL/ID, source SHA, license, workflow fingerprint, qualification digest, and stable slug come from provenance/authority rather than CLI strings. [VERIFIED: `domain/skill_artifacts.py`]

### Pattern 2: Closed Publication Intent

**What:** Build one immutable `PublicationIntentV1` containing the configured catalog repository ID/full name, observed default branch, deterministic head ref, target root, package digest, manifest digest, terminal/validation/review digests, reviewers, marker version, and publisher policy version. [VERIFIED: existing authority-object pattern]

**When to use:** As the identity and retry key for every attempt. [VERIFIED: current stage identity pattern]

Recommended identities:

```text
target_root       = skills/{stable_slug}/
head_branch       = skillscout/{stable_slug}
publication_key   = sha256(catalog_repo_id, base_ref, stable_slug)
desired_revision  = sha256(publication_key, package_digest, policy_version)
PR marker         = bounded canonical JSON containing marker schema,
                    catalog repo ID, base, head, slug, publication key,
                    package digest, manifest digest, workflow fingerprint
```

These are project recommendations derived from `PUB-05`; they are not GitHub platform primitives. [VERIFIED: requirement-based design]

### Pattern 3: Reconcile Before Mutate

**What:** Read repository metadata/default ref, machine ref, and open pull requests filtered by `head={owner}:{branch}` and `base={default}` before any write. GitHub supports both filters. [CITED: https://docs.github.com/en/rest/pulls/pulls]

**Decision table:**

| Remote state | Action |
|--------------|--------|
| No branch, no PR | Create commit from observed default head, create machine ref, create Draft PR, request reviewers. [CITED: https://docs.github.com/en/rest/git/refs] |
| Branch at desired machine commit, no PR | Recover from crash by creating Draft PR and requesting reviewers. [VERIFIED: idempotent state-machine analysis] |
| Exactly one matching Draft PR and machine-owned head | Fast-forward new commit if package changed; update deterministic body; request only missing reviewers. [CITED: https://docs.github.com/en/rest/pulls/review-requests] |
| Exactly one matching Draft already at desired revision | Verify marker/reviewers and return reconstructed `PublicationRecordV1` with no content write. [VERIFIED: idempotent state-machine analysis] |
| Matching PR is not Draft | Stop with `manual_intervention_required`; the ordinary REST update endpoint does not expose a `draft` field. [CITED: https://docs.github.com/en/rest/pulls/pulls] |
| More than one matching PR or marker mismatch | Stop; never guess which PR owns the identity. [VERIFIED: fail-closed design] |
| Head commit lacks the expected machine trailer, has an unexpected parent/tree, or ref update conflicts | Stop; never force-push or absorb unreviewed human changes. [CITED: https://docs.github.com/en/rest/git/refs] |
| Base/default branch changed during reconciliation | Restart bounded reconciliation from the new observed base; do not silently retarget an existing PR. [VERIFIED: concurrency analysis] |

### Pattern 4: Atomic Visible Content Update Through Git Data

**What:** Create blobs for the admitted bytes, create a tree with `base_tree` set to the currently observed machine-head tree (or default-head tree for first publication), create one commit with the observed head commit as its sole parent, then create or update `refs/heads/{machine_branch}`. [CITED: https://docs.github.com/en/rest/git/trees] [CITED: https://docs.github.com/en/rest/git/commits]

Set `force: false` on ref updates. GitHub documents that false enforces fast-forward behavior and avoids overwriting work. [CITED: https://docs.github.com/en/rest/git/refs]

The tree diff must contain only the admitted package paths under `skills/{slug}/`; a changed source package must explicitly delete stale prior files from that same owned subtree, while paths outside it remain inherited through `base_tree`. [VERIFIED: manifest enforcement design] [CITED: https://docs.github.com/en/rest/git/trees]

### Pattern 5: Draft-Only PR Lifecycle

**What:** On create, always send `draft: true`, deterministic title/body, exact head/base, and `maintainer_can_modify: false`; on reuse, verify the returned PR remains open and Draft before updating title/body. [CITED: https://docs.github.com/en/rest/pulls/pulls]

Request reviewers through `POST /pulls/{number}/requested_reviewers`, then GET requested reviewers and record the actual accepted users/teams. [CITED: https://docs.github.com/en/rest/pulls/review-requests]

Do not expose GraphQL. The normal REST update endpoint changes title/body/state/base/maintainer behavior but not Draft readiness, so the Publisher has no need for ready-for-review or auto-merge mutations. [CITED: https://docs.github.com/en/rest/pulls/pulls]

### Pattern 6: Checkpoint Every Externally Observable Step

**What:** Persist attempt-start before the call and a verified checkpoint after each of: reconciliation, ref visible, Draft PR visible, reviewers verified, and terminal remote verification. [VERIFIED: existing state architecture]

**When to use:** Every live publish, because a process can stop between any two GitHub calls. [VERIFIED: crash analysis]

`PublicationRecordV1` should contain stable IDs and hashes, not secrets or raw source text: catalog repository ID/full name, base/head refs, observed base/head SHAs, PR number/node ID/URL, Draft state, marker digest, package/manifest/terminal/validation/review digests, requested reviewers, actual reviewers, request IDs, policy/API versions, and timestamps. [VERIFIED: requirements and structured-log constraint]

### Pattern 7: Two-Layer Negative Capability Proof

**What:** Separate what GitHub can enforce from what SkillScout refuses to expose. [VERIFIED: permission analysis]

| Forbidden behavior | Production adapter proof | Platform proof |
|--------------------|--------------------------|----------------|
| Direct default-branch write | Domain rejects default ref; route allowlist binds only derived machine ref. [VERIFIED: recommended design] | Same App token receives a ruleset rejection on a canary default-ref update. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets] |
| Merge | No `PUT /pulls/{n}/merge`. [CITED: https://docs.github.com/en/rest/pulls/pulls] | Same App token cannot merge through the protected default branch; canary records provider response and unchanged base SHA. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets] |
| Approve | No `POST /pulls/{n}/reviews`; App-authored PR also cannot approve itself. [CITED: https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews] | Required human approval remains unsatisfied. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets] |
| Ready for review / auto-merge | No GraphQL transport at all. [VERIFIED: recommended design] | Do not claim token scopes separately deny these; `Pull requests: write` is coarse. [VERIFIED: permission analysis] |
| Ruleset modification | No ruleset routes. [VERIFIED: recommended design] | App has no repository or organization Administration permission. [CITED: https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps] |

### Anti-Patterns to Avoid

- **Extending `GitHubReadClient` with a generic request method:** this destroys the current truthful read-only capability declaration; create a separate closed write adapter. [VERIFIED: codebase grep]
- **Publishing from a materialized directory walk:** local files can be added or changed after validation; publish only bytes enumerated by the frozen manifest recovered from durable state. [VERIFIED: Phase 3 manifest model]
- **One Contents API call per file:** a crash exposes a partial package on the branch. [CITED: https://docs.github.com/en/rest/git/trees]
- **Force-pushing deterministic branches:** it hides concurrent/human changes and defeats the required manual-conflict outcome. [CITED: https://docs.github.com/en/rest/git/refs]
- **Finding PRs by title or local PR number:** titles are mutable and local state can be lost; bind head/base plus a versioned marker. [CITED: https://docs.github.com/en/rest/pulls/pulls]
- **Creating a new branch per package digest:** this defeats stable-slug update semantics and creates duplicate PRs. [VERIFIED: `PUB-05`]
- **Treating a `422` as proof of ruleset enforcement:** GitHub uses `422` for validation and secondary-rate-limit conditions too; the canary must verify the exact remote state remained unchanged and capture a bounded provider classification. [CITED: https://docs.github.com/en/rest/pulls/pulls]
- **Using candidate text in branch names, shell, logs, or PR templates:** only strict stable slug and structured trusted Phase 3 fields may enter these sinks. [VERIFIED: `SEC-02` and codebase trust boundary]
- **Logging raw HTTP headers/bodies:** Authorization, private keys, and provider error echoes can leak; log a closed schema of request ID, route ID, status class, rate facts, and safe error code. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-file visible update | Sequential file PUT loop | Git blobs + base tree + commit + fast-forward ref | One ref move publishes one coherent snapshot. [CITED: https://docs.github.com/en/rest/git/trees] |
| Concurrency control | Last-write-wins or force push | Observed parent SHA plus `force: false` | Provider returns a conflict instead of overwriting divergent work. [CITED: https://docs.github.com/en/rest/git/refs] |
| Token lifetime | Stored installation token refresh database | Mint per protected job and let it expire/revoke | Installation tokens expire after one hour; the official action revokes on job completion by default. [CITED: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app] [CITED: https://github.com/actions/create-github-app-token] |
| Merge protection | Boolean in application config | Active ruleset plus no App bypass and canary | Application config cannot constrain a compromised token. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets] |
| Publication eligibility | Recompute or summarize Phase 3 informally | Strict Phase 3 terminal/package/validation/review contracts | Existing digests already bind the exact approved candidate. [VERIFIED: Phase 3 domain code] |
| Review notification | Custom comments or mentions | Requested-reviewers REST endpoint | GitHub delivers native review requests and returns accepted reviewers/teams. [CITED: https://docs.github.com/en/rest/pulls/review-requests] |
| Secret redaction | Regex-only sanitizer over arbitrary logs | Structured allowlist plus GitHub masking and post-run secret scan | GitHub states automatic redaction is not guaranteed. [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |

**Key insight:** The difficult part is not creating a PR; it is proving that the exact reviewed bytes are the only bytes committed, that retries cannot duplicate or overwrite human work, and that the credential cannot cross the default-branch/merge boundary. [VERIFIED: requirements synthesis]

## Common Pitfalls

### Pitfall 1: Contents Write Is Also Merge-Capable

**What goes wrong:** A plan calls `Contents: write` “least privilege” and assumes the token therefore cannot call merge. [CITED: https://docs.github.com/en/rest/pulls/pulls]

**Why it happens:** GitHub's merge endpoint requires Contents write, the same permission required for Git objects and refs. [CITED: https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps]

**How to avoid:** Omit the merge route in production, keep the App out of the ruleset bypass list, require human approval, restrict default-branch updates, and run a real negative merge canary. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets]

**Warning signs:** The plan relies only on an App permission screenshot or has a generic REST method capable of arbitrary paths. [VERIFIED: security review heuristic]

### Pitfall 2: Publishing a Directory Instead of the Frozen Manifest

**What goes wrong:** Extra, changed, executable, or symlinked files reach the catalog after Phase 3 validation. [VERIFIED: trust-boundary analysis]

**Why it happens:** A filesystem walk creates a new source of truth after the manifest was frozen. [VERIFIED: Phase 3 artifact architecture]

**How to avoid:** Recover canonical `FrozenSkillPackageV1` bytes, re-derive its manifest, map each entry to one fixed catalog prefix, and reject every unlisted path/mode. [VERIFIED: `domain/skill_artifacts.py`]

**Warning signs:** The Publisher accepts an output directory, glob, tarball, or arbitrary path from CLI input. [VERIFIED: security review heuristic]

### Pitfall 3: Remote Recovery Selects the Wrong PR

**What goes wrong:** Lost local state causes a duplicate PR or updates a human PR. [VERIFIED: `PUB-05` failure analysis]

**Why it happens:** Title/slug alone is not unique enough, or pagination is ignored. [CITED: https://docs.github.com/en/rest/pulls/pulls]

**How to avoid:** Fetch all pages for exact head/base, require exactly one marker match, cross-check repository ID/slug/branch/package lineage, and fail on ambiguity. [CITED: https://docs.github.com/en/rest/pulls/pulls]

**Warning signs:** Recovery uses the first search result, PR title, or a cached number without revalidation. [VERIFIED: security review heuristic]

### Pitfall 4: Human Edits Are Silently Overwritten

**What goes wrong:** A maintainer edits or commits to the machine branch and the next run replaces it. [VERIFIED: roadmap conflict criterion]

**Why it happens:** The Publisher force-updates the ref or treats branch ownership as permanent. [CITED: https://docs.github.com/en/rest/git/refs]

**How to avoid:** Set `maintainer_can_modify: false`, validate the current head's machine trailer and expected lineage, use the observed head as parent, and update with `force: false`; otherwise require manual handling. [CITED: https://docs.github.com/en/rest/pulls/pulls] [CITED: https://docs.github.com/en/rest/git/refs]

**Warning signs:** `force: true`, missing expected-head checks, or automatic rebase/merge of base into head. [VERIFIED: security review heuristic]

### Pitfall 5: Reviewer Requests Are Not Idempotent

**What goes wrong:** Every retry re-notifies reviewers and hits secondary rate limits. [CITED: https://docs.github.com/en/rest/pulls/review-requests]

**Why it happens:** The Publisher posts the configured list without first reading current requests and completed reviews. [CITED: https://docs.github.com/en/rest/pulls/review-requests]

**How to avoid:** Read requested reviewers, calculate the missing set, request once, and verify the response; preserve a bounded retry policy for transient/rate failures. [CITED: https://docs.github.com/en/rest/pulls/review-requests]

**Warning signs:** Reviewer POST is inside a blind generic retry loop. [VERIFIED: security review heuristic]

### Pitfall 6: Protected Environment Is Added Too Late

**What goes wrong:** The App private key is exposed to a job before policy/admission checks, or to unrelated steps/actions. [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments]

**Why it happens:** One monolithic job performs build, validation, and publish with the same secrets. [VERIFIED: workflow threat analysis]

**How to avoid:** Use an unprivileged admission job producing only bounded digests, then a small environment-protected publish job that re-verifies its inputs before minting the token. [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments]

**Warning signs:** Repository-wide secrets, job-level broad permissions, or third-party actions after the App token is minted. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]

### Pitfall 7: Candidate Data Becomes Shell Source

**What goes wrong:** A repository-controlled title/path/value injects workflow commands. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]

**Why it happens:** `${{ ... }}` expressions are interpolated directly inside `run:` scripts. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]

**How to avoid:** The publish workflow should invoke the Python CLI with fixed arguments; pass only strict trusted config as environment/input values, and never construct shell syntax from candidate fields. [VERIFIED: project-specific recommendation]

**Warning signs:** Candidate title, source URL, branch, or file path appears inside a shell command string. [VERIFIED: `SEC-02`]

### Pitfall 8: Canary Failure Is Not Causal

**What goes wrong:** A merge attempt fails because the PR is Draft, lacks checks, or has conflicts, and the test incorrectly credits the ruleset/App identity. [VERIFIED: canary design analysis]

**Why it happens:** Only the HTTP status is asserted. [VERIFIED: test-design analysis]

**How to avoid:** Define the exact protection being tested, inspect active rules and bypass actors with an independent administrative verifier, record pre/post default SHA, and make the canary fixture otherwise mergeable when testing merge authority. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository]

**Warning signs:** A negative test accepts any `403`/`405`/`409`/`422` without checking provider reason and unchanged remote state. [CITED: https://docs.github.com/en/rest/pulls/pulls]

## Code Examples

Verified patterns from official sources, adapted to the project's strict adapter style:

### Create One Tree Over the Observed Base

```python
# Source: https://docs.github.com/en/rest/git/trees
# `entries` is created only from FrozenSkillPackageV1.rendered_manifest.
tree_payload = {
    "base_tree": observed_head_tree_sha,
    "tree": [
        {
            "path": f"skills/{stable_slug}/{entry.path}",
            "mode": "100644",
            "type": "blob",
            "sha": uploaded_blob_sha_by_path[entry.path],
        }
        for entry in frozen_package.rendered_manifest.entries
    ],
}
```

The planner should add an explicit stale-file deletion list for prior machine-owned files that are absent from the new manifest. [CITED: https://docs.github.com/en/rest/git/trees]

### Fast-Forward Ref Update

```python
# Source: https://docs.github.com/en/rest/git/refs
publish_client.update_machine_ref(
    expected_ref=derived_machine_ref,
    new_commit_sha=created_commit_sha,
    force=False,
)
```

The adapter method should derive and validate the path internally rather than accepting an arbitrary endpoint. [VERIFIED: existing `GitHubReadClient` pattern]

### Create Draft and Request Reviewers

```python
# Sources:
# https://docs.github.com/en/rest/pulls/pulls
# https://docs.github.com/en/rest/pulls/review-requests
pull = publish_client.create_draft_pull(
    head=derived_machine_branch,
    base=observed_default_branch,
    title=trusted_title,
    body=deterministic_body,
    draft=True,
    maintainer_can_modify=False,
)
publish_client.request_reviewers(
    pull_number=pull.number,
    reviewers=configured_users,
    team_reviewers=configured_team_slugs,
)
```

`trusted_title` and `deterministic_body` must be rendered from strict Phase 3 fields and bounded templates, not raw candidate text. [VERIFIED: trust-boundary requirement]

### Workflow Permission and Environment Shape

```yaml
# Sources:
# https://docs.github.com/en/actions/reference/security/secure-use
# https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
permissions:
  contents: read

jobs:
  publish:
    environment: skillscout-catalog-publish
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@FULL_COMMIT_SHA
      - uses: actions/create-github-app-token@FULL_COMMIT_SHA
        id: app-token
        with:
          client-id: ${{ vars.SKILLSCOUT_APP_CLIENT_ID }}
          private-key: ${{ secrets.SKILLSCOUT_APP_PRIVATE_KEY }}
          owner: ${{ vars.SKILLSCOUT_CATALOG_OWNER }}
          repositories: ${{ vars.SKILLSCOUT_CATALOG_REPOSITORY }}
          permission-contents: write
          permission-pull-requests: write
      - name: Publish admitted candidate
        env:
          SKILLSCOUT_GITHUB_TOKEN: ${{ steps.app-token.outputs.token }}
        run: .venv/bin/skillscout publish-candidate --intent publication-intent.json
```

Exact action SHAs and the safe construction of `publication-intent.json` are Wave 0/gate work, not placeholders permitted in the final workflow. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Unversioned GitHub REST requests | Explicit date-based `X-GitHub-Api-Version`; `2022-11-28` remains supported until 2028-03-10 | GitHub introduced date-based versions with `2022-11-28`; `2026-03-10` is also current | Keep the project's pinned version for Phase 4 and add an upgrade test rather than mixing response contracts. [CITED: https://docs.github.com/en/rest/about-the-rest-api/api-versions] |
| Long-lived PAT automation | Repository-scoped, permission-scoped GitHub App installation token | Current GitHub App model | Token expires after one hour and can be narrowed when minted. [CITED: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app] |
| Mutable action tags | Full-length action commit SHA | Current GitHub Actions hardening guidance | A full SHA is the only immutable action reference GitHub identifies. [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |
| Classic branch protection alone | Layered repository/organization rulesets plus branch protections | Rulesets are the current policy surface | Multiple matching protections aggregate and the most restrictive rule applies. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets] |

**Deprecated/outdated:**

- Treating `2022-11-28` as indefinitely current is unsafe; it has a published end-of-support date of 2028-03-10. [CITED: https://docs.github.com/en/rest/about-the-rest-api/api-versions]
- Pinning `actions/*@vN` is insufficient for this project even when the action is GitHub-owned; use a reviewed full commit SHA. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|

All technical claims are verified from the codebase or cited to official GitHub/OWASP sources. Configuration values that do not yet exist are recorded as open questions rather than assumptions. [VERIFIED: research audit]

## Open Questions (RESOLVED)

1. **What is the exact controlled catalog repository ID/full name and default target directory?**
   - What we know: Publisher must bind one configured central catalog and stable slug. [VERIFIED: `PUB-01`]
   - Resolution: The repository identity is supplied only through protected `SKILLSCOUT_CATALOG_REPOSITORY_ID` and `SKILLSCOUT_CATALOG_FULL_NAME`; production cross-checks both against GitHub's repository response. The target directory is code-owned as `skills/{stable_slug}/` and is not configurable. Plan 10 checkpoint `04-10-01` records the numeric/full-name evidence before live enablement. Missing, mismatched, or unreviewed values block client construction/token release and leave live publication disabled. [VERIFIED: Plans 04-06 and 04-10]

2. **Which human users and/or team slugs must be requested?**
   - What we know: GitHub accepts user and team arrays and requires Pull requests write. [CITED: https://docs.github.com/en/rest/pulls/review-requests]
   - Resolution: Protected `SKILLSCOUT_CATALOG_REVIEWERS` and `SKILLSCOUT_CATALOG_TEAM_REVIEWERS` hold bounded lists; at least one combined target is mandatory. Plan 10 checkpoint `04-10-01` verifies the configured identities exist and are authorized, and records requested/completed-review evidence. Missing, malformed, unauthorized, or unreviewed targets block publication; reconciliation combines current requests with completed review history so local-state loss cannot repeat notification. [VERIFIED: Plans 04-04, 04-05, 04-06, and 04-10]

3. **Which exact ruleset ID/configuration and organization plan are available?**
   - What we know: Rulesets can restrict default-branch updates, require PR review, block force pushes, and define bypass actors; feature availability varies by plan/repository visibility. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets]
   - Resolution: Plan 10 checkpoint `04-10-01` requires an independent export of the exact active ruleset ID, target/default branch, restrict-update/required-review/force-push rules, bypass actors, repository plan/feature availability, and digest before the canary. The App must have no Administration permission and no bypass. Missing/inactive/unsupported/mismatched evidence or any permitted forbidden probe blocks Phase 4 acceptance and production enablement. [VERIFIED: Plans 04-09 and 04-10]

4. **What full commit SHA of `actions/create-github-app-token` is approved?**
   - What we know: GitHub officially recommends the action, while Actions security guidance requires full-SHA pinning for immutability. [CITED: https://docs.github.com/en/enterprise-cloud@latest/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow] [CITED: https://docs.github.com/en/actions/reference/security/secure-use]
   - Resolution: Plan 07 statically audits exact full commits for both `actions/checkout` and `actions/create-github-app-token`; Plan 08 checkpoint `04-08-01` is a non-auto-approvable human decision bound to repository IDs, full SHAs, trees/content hashes, behavior, and audit digest. Plan 09 may reference only the approved exact pair. Missing, rejected, stale, or mismatched approval blocks workflow creation. [VERIFIED: Plans 04-07, 04-08, and 04-09]

5. **How will the merge canary isolate ruleset denial from Draft/check/conflict denial?**
   - What we know: Many independent conditions can block merge and several HTTP statuses overlap. [CITED: https://docs.github.com/en/rest/pulls/pulls]
   - Resolution: Plan 09's isolated canary-only client requires an otherwise mergeable disposable PR, independently exported active rules/bypass evidence, same-installation attestation, bounded provider classification, and pre/post default SHA equality. It also probes approve, ready-for-review, ruleset access/mutation, unauthorized repository/resource access, and secret-resource access with before/after state. Plan 10 checkpoint `04-10-01` reviews causal prerequisites and all unchanged-state evidence. Ambiguous denial, unavailable causal setup, or any permitted forbidden operation blocks acceptance and requires an explicit architecture/roadmap-criterion revision; static production-surface absence cannot replace live evidence. [VERIFIED: Plans 04-09 and 04-10]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Project Python virtual environment | Unit/contract tests and CLI | ✓ | Python 3.13.14 | — [VERIFIED: environment probe] |
| pytest | Validation architecture | ✓ | 9.1.1 | — [VERIFIED: environment probe] |
| `httpx`, Pydantic, OpenAI SDK | Existing runtime | ✓ | 0.28.1 / 2.13.4 / 2.46.0 | — [VERIFIED: import probe] |
| `uv` command | Lock-synchronized environment operations | ✗ on current `PATH` | — | Existing `.venv` is runnable; locate the project-managed uv tool before dependency operations. [VERIFIED: environment probe] |
| GitHub App credentials | Live publish and canary | ✗ not available to this research session | — | Recorded transport tests and dry-run only; live acceptance remains blocked. [VERIFIED: environment boundary] |
| Controlled catalog/ruleset | Live publish and canary | ✗ not configured in project files | — | Mock contract tests only; human configuration checkpoint required. [VERIFIED: codebase grep] |
| Protected Actions environment | `SEC-02` live proof | ✗ not inspectable | — | Workflow static tests only; live evidence required later. [VERIFIED: environment boundary] |

**Missing dependencies with no fallback:**

- Real GitHub App installation, catalog repository, protected environment, reviewer identities, and active ruleset are required for the live Phase 4 canary and final production proof. [VERIFIED: requirements]

**Missing dependencies with fallback:**

- Local development can use `.venv/bin/python` and `.venv/bin/pytest`; recorded `httpx.MockTransport` fixtures cover all deterministic logic without credentials. [VERIFIED: existing test infrastructure]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 with `httpx.MockTransport`. [VERIFIED: environment and tests] |
| Config file | `pyproject.toml`. [VERIFIED: codebase] |
| Quick run command | `.venv/bin/pytest -q tests/test_publication_domain.py tests/test_github_publish_adapter.py tests/test_publication_recovery.py tests/test_publication_security.py` [VERIFIED: recommended Wave 0 layout] |
| Full suite command | `.venv/bin/pytest -q` [VERIFIED: existing project configuration] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PUB-01 | Only configured catalog/machine branch/manifest bytes; Draft PR; reviewer request | contract + transport integration | `.venv/bin/pytest -q tests/test_github_publish_adapter.py -x` | ❌ Wave 0 |
| PUB-02 | Deterministic complete PR body and marker from strict Phase 3 evidence | unit/golden | `.venv/bin/pytest -q tests/test_publication_domain.py -x` | ❌ Wave 0 |
| PUB-03 | No merge/approve/ready/auto-merge/ruleset/default-ref capability | static AST + negative transport | `.venv/bin/pytest -q tests/test_publication_security.py -x` | ❌ Wave 0 |
| PUB-04 | Scoped one-hour App token and ruleset canary blocks default push/merge | static workflow + opt-in live integration | `.venv/bin/pytest -q tests/test_publication_live_canary.py -x` | ❌ Wave 0 |
| PUB-05 | Same Draft updated/reused; local-state-loss recovery; human conflicts stop | crash matrix + recorded integration | `.venv/bin/pytest -q tests/test_publication_recovery.py -x` | ❌ Wave 0 |
| SEC-02 | Minimal Actions permissions, protected environment, pinned SHAs, safe shell/log fields | workflow parser + AST/security tests | `.venv/bin/pytest -q tests/test_publication_security.py -x` | ❌ Wave 0 |

### Required Test Matrices

1. **Admission:** eligible package succeeds; every single cross-digest, canonical-byte, path, mode, size, validation-error, verdict, confidence, and terminal-outcome mutation fails before network/token access. [VERIFIED: Phase 3 contract surface]
2. **Provider responses:** success plus 301/redirect, 401, 403, 404, 409, 422, 429/secondary rate limit, 5xx, oversized body, malformed JSON, wrong content type, missing request ID, pagination, and unknown fields. [VERIFIED: existing GitHub adapter test style]
3. **Crash points:** after blob/tree/commit creation, after ref creation/update, after PR creation/update, after reviewer request, after remote verification, and after remote success before local commit. [VERIFIED: recovery analysis]
4. **Remote ambiguity:** duplicate matching PRs, non-Draft PR, wrong base/head, marker mismatch, machine ref without marker commit, human commit, force-updated ref, deleted/reopened/closed PR, changed default branch, and stale reviewer state. [VERIFIED: roadmap and recovery analysis]
5. **Forbidden routes:** prove production code cannot issue `PUT`, `DELETE`, GraphQL, `/merge`, `/reviews`, `/update-branch`, `/rulesets`, `/branches/{default}`, arbitrary refs, or arbitrary repositories. [CITED: https://docs.github.com/en/rest/pulls/pulls] [VERIFIED: security design]
6. **Live canary:** positive machine-branch/Draft/reviewer flow and negative default-ref/merge/ruleset access using the same installation identity, with cleanup performed by a separately authorized human/admin process. [VERIFIED: two-layer proof design]

### Sampling Rate

- **Per task commit:** Run the narrow publication test file(s) touched by the task. [VERIFIED: Nyquist recommendation]
- **Per wave merge:** Run all four offline Phase 4 suites plus current Phase 1–3 regression tests. [VERIFIED: integration recommendation]
- **Phase gate:** Full offline suite green, workflow static security checks green, and one separately authorized live canary evidence bundle reviewed by a human. [VERIFIED: roadmap success criteria]

### Wave 0 Gaps

- [ ] `tests/fixtures/github_publish/` — bounded fixtures for Git objects, refs, pulls, review requests, pagination, conflicts, and rate limits. [VERIFIED: existing fixture pattern]
- [ ] `tests/test_publication_domain.py` — admission, identity, marker, body, transition, and record contracts. [VERIFIED: recommended layout]
- [ ] `tests/test_github_publish_adapter.py` — exact method/path/body allowlist and response parsing. [VERIFIED: recommended layout]
- [ ] `tests/test_publication_recovery.py` — crash and remote-reconstruction matrix. [VERIFIED: recommended layout]
- [ ] `tests/test_publication_security.py` — AST/import/route/workflow/logging forbidden-surface tests. [VERIFIED: existing security-test pattern]
- [ ] `tests/test_publication_live_canary.py` — opt-in marker and environment contract; skipped unless explicit canary variables are present. [VERIFIED: environment design]
- [ ] Supply-chain gate artifact for the exact App-token action SHA. [VERIFIED: project Gate A/B pattern]
- [ ] Independent ruleset configuration evidence and canary cleanup procedure. [VERIFIED: open environment gap]

## Security Domain

Security enforcement is enabled at ASVS Level 1 in `.planning/config.json`. [VERIFIED: project config]

OWASP ASVS 5.0.0 is the current stable version; its chapter numbering differs from the older V2–V6 labels in the GSD template, so controls below are expressed by security function and mapped to this phase rather than asserting obsolete identifiers. [CITED: https://github.com/OWASP/ASVS]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| Authentication | yes | GitHub App installation authentication; validate repository/installation binding and token expiry, never persist the token. [CITED: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app] |
| Session / token management | yes | One job-scoped token, protected environment secret release, revocation/expiry, and no token in logs/state/PR. [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments] |
| Access control | yes | Catalog/repository/ref allowlists, no Administration permission, ruleset with no App bypass, and human-only merge. [CITED: https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps] |
| Input validation / encoding | yes | Strict Pydantic contracts, closed branch/path/login/marker grammars, JSON request bodies, and no candidate-to-shell interpolation. [VERIFIED: project patterns] [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |
| Cryptography | yes, consume only | Use TLS/GitHub authentication and existing SHA-256 canonical digests; do not implement signing or token cryptography inside publication domain logic. [VERIFIED: codebase canonicalization and GitHub HTTPS boundary] |
| Error handling and logging | yes | Fixed safe error codes and structured field allowlist; never log headers, token, private key, arbitrary response body, or raw candidate content. [VERIFIED: existing `SafeFailure` pattern] [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |
| Files and resources | yes | Publish only exact manifest paths/modes/sizes/hashes under one slug-owned root; reject symlink/executable/path traversal. [VERIFIED: Phase 3 manifest contracts] |
| API and web service | yes | Fixed API version, exact endpoint allowlist, bounded bodies, serial client, bounded retry, rate-limit classification, and no GraphQL. [VERIFIED: existing adapter pattern] [CITED: https://docs.github.com/en/rest/about-the-rest-api/api-versions] |
| Configuration | yes | Protected environment, immutable action refs, minimal workflow/App permissions, active ruleset, explicit reviewers, and canary evidence. [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |

### Known Threat Patterns for GitHub Publisher

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Candidate-controlled branch/path/body injection | Tampering / Elevation | Derive branch/path from strict stable slug; render JSON/Markdown from bounded trusted fields; never generate shell source. [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |
| Token or private-key disclosure | Information Disclosure | Protected environment, per-job minting, secret masking, structured logs, no persisted headers, post-run secret scan. [CITED: https://docs.github.com/en/actions/reference/security/secure-use] |
| Publishing bytes not reviewed | Tampering | Canonical Phase 3 bundle revalidation and exact manifest-to-blob mapping. [VERIFIED: Phase 3 artifact contracts] |
| Force overwrite of human changes | Tampering / Repudiation | Machine commit marker, observed parent, `force: false`, manual intervention on mismatch. [CITED: https://docs.github.com/en/rest/git/refs] |
| Duplicate PR after state loss | Repudiation / Denial of Service | Exact head/base pagination plus versioned marker and one-match rule. [CITED: https://docs.github.com/en/rest/pulls/pulls] |
| Automation merges or changes rules | Elevation of Privilege | No routes/GraphQL/Admin permission; no ruleset bypass; platform canary. [CITED: https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps] |
| Reviewer notification storm | Denial of Service | Read-before-request, missing-set diff, bounded retry, secondary-rate-limit handling. [CITED: https://docs.github.com/en/rest/pulls/review-requests] |
| Confused deputy publishes to another repository | Spoofing / Elevation | Bind numeric catalog repository ID in configuration, intent, marker, adapter, and returned provider objects. [VERIFIED: security design] |
| Malicious provider/error response pollutes logs | Information Disclosure / Injection | Bounded strict response models and safe error-code projection; no arbitrary response echo. [VERIFIED: existing GitHub adapter/SafeFailure pattern] |

## Sources

### Primary (MEDIUM confidence from official sources)

- [GitHub REST Git database](https://docs.github.com/en/rest/git) — Git objects and references. [CITED: https://docs.github.com/en/rest/git]
- [Git trees](https://docs.github.com/en/rest/git/trees) — `base_tree`, path/mode/type entries, and tree-to-commit flow. [CITED: https://docs.github.com/en/rest/git/trees]
- [Git commits](https://docs.github.com/en/rest/git/commits) — tree, parents, permission, and response behavior. [CITED: https://docs.github.com/en/rest/git/commits]
- [Git references](https://docs.github.com/en/rest/git/refs) — create/update ref and `force: false` fast-forward semantics. [CITED: https://docs.github.com/en/rest/git/refs]
- [Pull requests](https://docs.github.com/en/rest/pulls/pulls) — list head/base filters, Draft create, update fields, and merge endpoint permissions. [CITED: https://docs.github.com/en/rest/pulls/pulls]
- [Review requests](https://docs.github.com/en/rest/pulls/review-requests) — requested users/teams and permissions. [CITED: https://docs.github.com/en/rest/pulls/review-requests]
- [GitHub App installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app) — repository/permission narrowing and one-hour expiry. [CITED: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app]
- [GitHub App endpoint permissions](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps) — Contents, Pull requests, and Administration capabilities. [CITED: https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps]
- [Rulesets overview](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) and [available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) — enforcement, layering, bypass actors, restrict updates, and required reviews. [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets]
- [GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use) — least privilege, script injection, secret handling, and immutable action SHAs. [CITED: https://docs.github.com/en/actions/reference/security/secure-use]
- [Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments) — required reviewers and gated environment secrets. [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments]
- [GitHub App in Actions](https://docs.github.com/en/enterprise-cloud@latest/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow) — GitHub-owned token action. [CITED: https://docs.github.com/en/enterprise-cloud@latest/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow]
- [GitHub REST API versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions) — current supported versions and sunset dates. [CITED: https://docs.github.com/en/rest/about-the-rest-api/api-versions]
- [OWASP ASVS](https://github.com/OWASP/ASVS) — current stable ASVS version and security verification framing. [CITED: https://github.com/OWASP/ASVS]

### Internal Authoritative Sources

- `AGENTS.md` — project constraints and approved technology stack. [VERIFIED: codebase]
- `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` — Phase 4 requirements and success criteria. [VERIFIED: codebase]
- `src/skillscout/domain/skill_artifacts.py`, `validation.py`, and `review.py` — exact Phase 3 trust artifacts. [VERIFIED: codebase]
- `src/skillscout/application/phase3.py` and `src/skillscout/adapters/state.py` — durable recovery and projection patterns. [VERIFIED: codebase]
- `src/skillscout/adapters/github.py` and `tests/recorded_transport.py` — closed serial REST adapter and recorded-fixture pattern. [VERIFIED: codebase]

### Tertiary

None. [VERIFIED: source audit]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — versions and architecture were verified from the lockfile, local environment, and codebase; GitHub API support dates are official. [VERIFIED: environment/codebase] [CITED: https://docs.github.com/en/rest/about-the-rest-api/api-versions]
- Architecture: HIGH for internal seams, MEDIUM for live GitHub configuration — code boundaries are directly verified, but the real catalog/App/ruleset were unavailable. [VERIFIED: codebase and environment audit]
- GitHub REST behavior: MEDIUM — all claims use official GitHub docs, and the research seam classifies verified websearch as MEDIUM. [VERIFIED: `classify-confidence` seam]
- Pitfalls and recovery: MEDIUM — endpoint facts are official; the exact state-machine design is a prescriptive synthesis requiring implementation tests. [CITED: official GitHub sources] [VERIFIED: requirements synthesis]
- Security controls: MEDIUM — official GitHub/OWASP guidance is current, but live ruleset and protected-environment proof remains outstanding. [CITED: official sources] [VERIFIED: environment audit]

**Research date:** 2026-07-24  
**Valid until:** 2026-08-23 for stable codebase architecture; re-check GitHub Actions action SHA, API docs, App permissions, and ruleset behavior immediately before live enablement. [VERIFIED: research freshness policy]
