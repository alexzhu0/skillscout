# Phase 5: Automated Discovery Operations - Research

**Researched:** 2026-07-27  
**Domain:** Bounded GitHub discovery, resumable multi-candidate orchestration, and durable state-branch operations  
**Confidence:** HIGH for codebase integration; MEDIUM for current hosted-platform behavior

## User Constraints

- Implement only DISC-01, DISC-02, DISC-03, OPS-02, and OPS-03 for this phase. Phase 6 owns the five-real-repository adversarial acceptance campaign. [VERIFIED: `.planning/ROADMAP.md` and `.planning/REQUIREMENTS.md`]
- Discovery must support a daily schedule and a manual trigger, accept no more than 100 deduplicated repositories per run, and allow no more than 20 repositories to enter semantic analysis. Neither retry nor resume may reset either limit. [VERIFIED: `.planning/REQUIREMENTS.md` DISC-01..03]
- Compose the already verified Filter → Reader → Extractor → Qualifier → Generator → Validator → Reviewer → Draft path; do not replace it with a second pipeline or a multi-agent framework. [VERIFIED: `.planning/ROADMAP.md` Phase 5 and `AGENTS.md`]
- Public, non-fork GitHub repositories are the only discovery source. Candidate repositories are read through REST at a pinned commit and are never cloned, installed, imported, built, or executed. [VERIFIED: `AGENTS.md`; `.planning/REQUIREMENTS.md` FILT-01 and READ-01..06]
- SQLite remains the queryable transactional index. Versioned, trimmed, content-addressed JSON on a dedicated `skillscout-state` branch is the rebuild/audit authority. Actions cache and artifacts are not canonical state. [VERIFIED: `AGENTS.md`; `.planning/REQUIREMENTS.md` OPS-02]
- Full third-party text, authorization headers, tokens, credentials, private keys, and raw exception text must not enter state, manifests, logs, artifacts, prompts other than the existing bounded untrusted-input envelope, or Draft PRs. [VERIFIED: `AGENTS.md`; `.planning/REQUIREMENTS.md` OPS-03]
- Production automation may create or update only machine branches and Draft PRs through the Phase 4 admission boundary. It may never merge, approve, mark ready, write the catalog default branch, administer rulesets, or weaken the protected environment. [VERIFIED: `AGENTS.md`; Phase 4 verification]
- Preserve the repository-local locked Python 3.13 toolchain and run tests with `.tools/uv-0.11.29/bin/uv run --locked pytest -q`. Do not read `.env`, PEM, JWT, token, or private-key contents. [VERIFIED: `AGENTS.md`]

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| DISC-01 | Versioned GitHub Search queries with daily and manual execution | Strict query-set contract, fixed query policy, Search adapter, and one scheduled/manual workflow |
| DISC-02 | At most 100 deduplicated candidates and 20 semantic candidates per run | Durable first-seen repository-ID ledger and pre-Extractor semantic reservation |
| DISC-03 | Query version/text, pagination, source, rate-limit, and dedup records | `SearchPageObservationV1`, `DiscoveredCandidateV1`, and content-addressed run manifests |
| OPS-02 | SQLite plus state-branch JSON rebuild authority and serialized production runs | Safe state bundle, CAS-like fast-forward update, rebuild verifier, and workflow concurrency |
| OPS-03 | No full source text or secrets in durable/observable surfaces | Closed schemas, field allowlists, secret canaries, and negative surface tests |

[VERIFIED: `.planning/REQUIREMENTS.md`]

</phase_requirements>

## Project Constraints (from AGENTS.md)

- Use Python 3.13, `pyproject.toml` plus the locked graph, REST through `httpx`, strict Pydantic contracts, stdlib `sqlite3`, and pytest. [VERIFIED: `AGENTS.md`; `pyproject.toml`; `uv.lock`]
- OpenAI remains the default semantic provider and DeepSeek remains explicit opt-in; both keep SDK retries at zero. Retry authority belongs to deterministic pipeline policy. [VERIFIED: `AGENTS.md`; `src/skillscout/adapters/semantic_provider.py`]
- Semantic requests keep no tools, no code execution, strict local validation, and `store=false`; model names remain configuration, not business-logic constants. [VERIFIED: `AGENTS.md`; existing semantic adapters]
- GitHub credentials are injected only at the latest boundary and have minimum scope. Source/state-repository authority and protected catalog-publication authority must remain separate. [VERIFIED: `AGENTS.md`; `.github/workflows/publish-candidate.yml`]
- Third-party Actions must remain pinned to full reviewed commit SHAs. Candidate-controlled values must not be interpolated into shell. [VERIFIED: `AGENTS.md`; Phase 4 verification]
- Phase 4 Gate B4 passed on 2026-07-27 only for protected publication workflow SHA-256 `224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c` and its reviewed App scope, catalog, ruleset, protected environment, reviewer configuration, and installation identity. Any byte or identity change requires a fresh Gate B4 run. Phase 5 concurrency evidence cannot substitute for Gate B4, and Phases 5–6 remain pending for whole-product readiness. [VERIFIED: `AGENTS.md`; `RELEASE.md`; `04-10-SUMMARY.md`; `04-VERIFICATION.md`]
- No project-local skills exist, so there are no additional `rules/*.md` conventions to incorporate. [VERIFIED: project skill discovery]

## Summary

Phase 5 should be a thin operational control plane around the verified single-repository applications. A code-owned, versioned query set feeds a hardened Search method on the existing serial read-only GitHub client. Search results are metadata locators only: keep numeric repository ID, validated owner/name, visibility/fork/archive facts, query/page/item provenance, and rate-limit telemetry; discard description, topics, text matches, and every other provider field. Deduplicate by numeric repository ID with first-seen authority, then re-fetch repository metadata through the existing Phase 2 Scout before any trust decision. [VERIFIED: `src/skillscout/adapters/github.py`, `application/processors.py`; CITED: https://docs.github.com/en/rest/search/search]

The 100-candidate and 20-semantic limits need durable ledgers, not loop counters. A candidate consumes one discovery slot when its first-seen record is committed. It consumes one semantic-candidate slot immediately before its first actual Extractor request. That one repository reservation covers all 0–3 independently identified workflows returned by Extractor; each workflow then receives its own complete Phase 3/4 authority, stable identity, business terminal, and Draft reconciliation path. Mixed workflow outcomes continue independently without consuming additional repository semantic reservations. The repository reservation is never refunded after rejection, transient failure, interruption, resume, or any mixture of downstream workflow terminals. Completed exact-authority reuse performs no new semantic request and consumes no new semantic slot. Generator and Reviewer attempts remain separately bounded and recorded, but are not additional “semantic candidates.” [VERIFIED: Phase 1 reusable-digest retry pattern; `PhaseThreeRuntimeProfile`; `.planning/REQUIREMENTS.md` DISC-02]

Persist a consistent SQLite snapshot and the complete trimmed rebuild facts in the same commit on `skillscout-state`. Build the commit from the remotely observed state head and update the ref with `force=false`; any non-fast-forward, changed head, malformed tree, or hash mismatch is a conflict, never a reason to force or merge SQLite bytes. On startup, validate the root manifest, every reachable object digest, SQLite `integrity_check`, exact schema fingerprint, and existing chain verifiers. If SQLite is missing or corrupt but the JSON authority is valid, replay into a fresh private database, verify it, and atomically replace it. [CITED: https://docs.github.com/en/rest/git/refs; CITED: https://www.sqlite.org/pragma.html#pragma_integrity_check; VERIFIED: `SQLiteStateStore` snapshot/chain patterns]

**Primary recommendation:** Add an unprotected `DiscoveryApplication` with durable budget reservations and one `StateBranchStore`; compose only the existing Phase 2 and Phase 3 applications, end after Review, and persist bounded eligible locators/authorities at an exact state commit. It must have no Phase 4 factory or remote publisher access. Add a separate protected publication entry point that re-reads that exact commit, re-derives canonical admission, and only then mints the catalog token, constructs `PublicationApplication`, and invokes it. Add a closed semantic transport classification shared by OpenAI Extractor/Generator/Reviewer and the DeepSeek compatibility path: only responses proven not to have produced a semantic result are confirmed-retryable, while timeout, connection loss, ambiguous 5xx, or any post-send indeterminate failure is outcome-unknown and quarantined without automatic replay. Wire an explicit three-store remote durability barrier into all three semantic runners immediately after attempt-start and before every request, then after every result and before retry or terminal.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Query-set versioning and budget policy | API / Backend | — | Code-owned deterministic policy, never workflow input |
| GitHub Search and pagination | API / Backend | External GitHub REST | Serial bounded REST reads with strict response projection |
| Candidate/semantic reservations | Database / Storage | API / Backend | Transactional uniqueness and non-refundable counters |
| Existing filter-to-review composition | API / Backend | External GitHub/OpenAI | Application orchestration over verified ports |
| State restore/rebuild | Database / Storage | External GitHub Git database | JSON authority reconstructs the disposable SQLite index |
| State-branch compare-and-swap | API / Backend | External GitHub Git database | Create immutable objects, then fast-forward only |
| Daily/manual production trigger | GitHub Actions | API / Backend | Triggering and serialization only; business policy stays in Python |
| Draft publication | API / Backend | External protected catalog | Existing Phase 4 admission, recovery, and human-control boundary |

[VERIFIED: current codebase boundaries and Phase 1–4 verification]

## Standard Stack

### Core

| Library / facility | Version | Purpose | Why Standard Here |
|---|---:|---|---|
| Python | 3.13.14 locally | Runtime and stdlib `sqlite3`, hashing, JSON, filesystem primitives | Required and already installed [VERIFIED: local locked-toolchain probe] |
| `httpx` | 0.28.1 | Search, source reads, state Git objects, publication REST | Already locked; preserves one auditable HTTP abstraction [VERIFIED: `pyproject.toml`, `uv.lock`, runtime import] |
| Pydantic | 2.13.4 | Strict versioned query, page, budget, manifest, and restore contracts | Existing contract pattern [VERIFIED: `pyproject.toml`, runtime import] |
| SQLite through `sqlite3` | Python module / SQLite 3.53.1 in locked Python | Queryable transaction and reservation ledger | Existing state technology; `integrity_check` is officially defined [VERIFIED: local probe; CITED: https://www.sqlite.org/pragma.html#pragma_integrity_check] |
| GitHub Actions | hosted service | Daily/manual orchestration, protected publication job, concurrency | Approved operations platform [VERIFIED: `AGENTS.md`; CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax] |

### Supporting

| Library / facility | Version | Purpose | When to Use |
|---|---:|---|---|
| OpenAI SDK | 2.46.0, uploaded 2026-07-17 in lock metadata | Existing Extractor/Generator/Reviewer calls | Only after durable semantic admission [VERIFIED: `uv.lock`; semantic adapters] |
| pytest | 9.1.1 | Contract, transport, crash, rebuild, workflow, and acceptance tests | Every task and phase gate [VERIFIED: `pyproject.toml`, runtime import] |
| Ruff | 0.15.21, uploaded 2026-07-09 in lock metadata | Static quality gate | Full phase release chain [VERIFIED: `uv.lock`] |
| Existing official `skills-ref` | 0.1.1 | Candidate validation | Continue through Phase 3 unchanged [VERIFIED: `pyproject.toml`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| Existing REST + `httpx` | PyGithub or another SDK | Adds a broad dependency and hides route/retry/body limits; reject for MVP [VERIFIED: `AGENTS.md` stack decision] |
| SQLite + JSON state branch | PostgreSQL/object storage | Better concurrent scale but contradicts approved MVP scope [VERIFIED: `AGENTS.md`] |
| Fast-forward Git-data update | `git push --force` | Can overwrite human/other-run state and defeats conflict evidence; forbidden [CITED: https://docs.github.com/en/rest/git/refs] |
| One application orchestrator | Event bus/multi-agent framework | Adds implicit state and recovery complexity; rejected for MVP [VERIFIED: `AGENTS.md`] |

**Installation:** no new package is required. Keep `pyproject.toml` and `uv.lock` unchanged. [VERIFIED: codebase and environment audit]

## Recommended Defaults

Use a committed `github-repository-search-v1` query set with four ordered entries, `per_page=25`, `max_pages_per_query=4`, round-robin page acquisition, `sort=updated`, and `order=desc`. Stop as soon as 100 unique numeric repository IDs are durably selected. [ASSUMED]

| Query ID | Exact query text |
|---|---|
| `agent-workflow-readme` | `"agent workflow" in:name,description,readme is:public archived:false` |
| `ai-workflow-readme` | `"AI workflow" in:name,description,readme is:public archived:false` |
| `llm-automation-readme` | `"LLM automation" in:name,description,readme is:public archived:false` |
| `agent-skills-topic` | `topic:agent-skills is:public archived:false` |

GitHub excludes forks unless `fork:true` or `fork:only` is present, and `is:public` and `archived:false` are documented qualifiers. Still require each returned item and the later Scout observation to say `private=false`, `visibility=public`, `fork=false`, and `archived=false`; query semantics are not admission authority. [CITED: https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories]

The exact terms are discovery hypotheses, not security policy. Measure their yield in Phase 6 before changing them; any edit creates a new query-set version and digest rather than mutating v1. [ASSUMED]

## Architecture Patterns

### System Architecture Diagram

```text
schedule / workflow_dispatch
            |
            v
  load exact code + observed state-head SHA
            |
            v
 validate root index -> objects -> SQLite
       | valid                 | DB corrupt, JSON valid
       |                       v
       |                 rebuild fresh SQLite
       +-----------+-----------+
                   v
       versioned query set (code-owned)
                   |
         GitHub Search pages (serial)
                   |
        strict metadata projection
                   |
       repo-ID first-seen dedup ----duplicate----> terminal duplicate record
                   |
          100-slot durable gate ----full--------> stop discovery
                   |
      existing Scout + Filter + Reader
             | business reject ----------> terminal rejection; continue
             v
      20-slot durable semantic gate ------> full: deferred/not admitted
             |
      existing Extractor -> Qualifier -> Generator -> Validator -> Reviewer
             | business reject ----------> terminal rejection; continue
             v
        Phase 4 admission + protected job
             |
      remote reconcile -> create/update Draft
             |
             v
  export trimmed facts + consistent SQLite snapshot
             |
 create blobs/tree/commit(parent = observed state head)
             |
 update skillscout-state ref, force=false
       | success + reread match     | 409/422/head mismatch
       v                            v
    next candidate              conflict; stop/fetch/rebuild
```

[VERIFIED: existing Phase 1–4 applications; CITED: GitHub refs and Actions docs]

### Recommended Project Structure

```text
config/
└── discovery-queries-v1.json        # reviewed, strict, code-owned query set
src/skillscout/
├── domain/discovery.py              # immutable contracts, policy constants, hashes
├── application/discovery.py         # multi-candidate orchestration and outcome taxonomy
├── adapters/github.py               # add bounded repository-search method/models
├── adapters/operations_state.py     # discovery/budget ledger and safe export/import
├── adapters/state_branch.py         # exact branch/tree/blob/ref capability
├── bootstrap.py                     # late-bound factories and authority separation
└── cli.py                           # one production `discover` command
.github/workflows/
└── discover.yml                     # schedule + dispatch + fixed concurrency group
tests/
├── fixtures/github_search/          # pages, duplicates, incomplete, 403/429/5xx
├── fixtures/state_branch/           # ref/tree/blob/conflict observations
├── test_discovery_domain.py
├── test_discovery_application.py
├── test_github_search.py
├── test_operations_state.py
├── test_state_branch.py
├── test_discovery_workflow.py
└── test_phase5_acceptance.py
```

### Component Responsibilities and Existing Analogs

| New responsibility | Existing analog to reuse | Required seam |
|---|---|---|
| Strict Search response projection | `_RawRepo`, `RepoMetadata`, `_get`, `_rate_limit_facts` in `adapters/github.py` | Add Search envelope/item models, `Link` parsing, response cap, and `search_repositories` |
| Stable dedup and policy hashes | `domain/canonical.py`; Phase 3 authority digests | Numeric repo ID key; query/budget/profile digest in every run |
| Non-refundable semantic reservation | `SQLiteStateStore.start_attempt`, `retry_attempt_count`; Phase 3 running semantic attempts | Unique `(discovery_run_id, repository_id)` reservation before first Extractor call |
| Resume without completed replay | `PipelineRunner.find_completed_run`; `PhaseThreeApplication` completed-first lookup | Discovery startup selects one exact unfinished run, then reuses completed authorities |
| Business-vs-operational status | Phase 2 `outcome=rejected`; Phase 3 terminal summaries; `SafeFailure` codes | Closed candidate status enum and separate run health aggregate |
| Content-addressed safe state | Phase 1 stage manifests; Phase 3 artifact digests | Root snapshot index must include all rebuild facts, not only successful stage envelopes |
| Consistent SQLite snapshot | `SQLiteStateStore._snapshot_transaction`; `PublicationStateStore.serialize` replacement | Export under store lock or SQLite backup API; never copy an active DB blindly |
| Remote recovery | `PublicationApplication._reconcile_existing` and `_verify_remote` | State ref/head/tree revalidation around every push |
| Fast-forward state update | `GitHubPublishClient.create_blob/create_tree/create_commit/update_ref` | A narrower state-branch client fixed to one branch and allowlisted paths |
| Workflow authority split | `.github/workflows/publish-candidate.yml` admit/publish jobs | Discovery job uses source/state token; protected publish job mints catalog token late |

[VERIFIED: codebase grep and Phase 1–4 summaries]

### Pattern 1: Durable Budget Reservation

The counter and reservation must be one SQLite transaction. Do not `COUNT` and later `INSERT` in separate transactions. Persist the state-branch snapshot before invoking Extractor so a killed runner cannot forget the slot. [VERIFIED: Phase 1 transactional state pattern]

```python
# Project pattern; exact schema names are planning guidance.
def reserve_semantic_candidate(run_id: str, repository_id: int) -> Reservation:
    with begin_immediate():
        existing = find_reservation(run_id, repository_id)
        if existing is not None:
            return existing
        used = count_reservations(run_id)
        if used >= 20:
            raise SemanticBudgetExhausted
        return insert_reservation(run_id, repository_id, ordinal=used + 1)
```

Use a unique constraint on `(run_id, repository_id)`, validate `ordinal` continuity during restore, and bind the reservation to query-set digest, budget-policy digest, and exact Phase 2 run authority. [VERIFIED: existing identity/chain verification patterns]

Define `DiscoveryRunAuthorityV1` from a generated run ID plus the exact query-set digest, discovery-budget policy, pipeline/profile versions, semantic-provider identities, and initial state-root digest. The changing current state-head SHA is checkpoint evidence, not part of this stable identity. At workflow start, resume exactly one verified unfinished run with matching authority before creating a new run; ambiguity or an incompatible unfinished run fails closed. [VERIFIED: `RunIdentity`, candidate execution authority, and completed-first lookup patterns]

Place a `ThreeStoreDurabilityBarrier` immediately after every Search page/dedup transaction, semantic reservation, candidate terminal, and—inside the existing Phase 2 Extractor and Phase 3 Generator/Reviewer runners—after semantic attempt-start and before each provider request, then after every decided/confirmed-retryable/outcome-unknown result and before retry authorization or terminal projection. Every call exports the complete `SQLiteStateStore`, `OperationsStateStore`, and `PublicationStateStore` projections through their owning APIs, advances the fixed state branch with parent-bound CAS, rereads the exact remote commit/tree/root/objects, and returns a verified receipt. Sync failure grants no request/retry/terminal authority. Crashes immediately before or after either semantic barrier resume the same pending transition and must produce zero ambiguous replay across both providers and all three stages. Protected publication retains its own Phase 4 checkpoint/reconciliation behavior behind the separate protected entry point. [VERIFIED: Phase 1 pre-effect checkpoint and Phase 4 remote-recovery patterns; APPROVED]

### Pattern 2: Search Page as an Observation, Not a Snapshot

Repository Search can return at most 100 items per page and exposes only up to 1,000 results per query. `incomplete_results=true` means a timed-out query returned a partial observation. Persist the flag and continue only according to a code-owned policy; recommended v1 behavior is to accept the returned page as partial, mark the run degraded, and never claim exhaustive coverage. [CITED: https://docs.github.com/en/rest/search/search]

Persist:

- query-set version/digest, query ID/ordinal, exact query text, sort/order;
- requested page/per-page and validated next-page integer;
- response `total_count`, `incomplete_results`, item count, request ID;
- `x-ratelimit-limit`, `remaining`, `used`, `reset`, and `resource`;
- each selected/duplicate item’s numeric repository ID, validated owner/name, public/non-fork facts, page/item ordinal, and first-seen source.

Do not persist description, topics, text-match fragments, provider error bodies, raw `Link`, authorization headers, or the complete provider item. [VERIFIED: OPS-03 and existing lenient-provider/strict-domain projection pattern]

### Pattern 3: Safe State-Branch Update

Create all immutable Git objects first, with the new commit’s sole parent equal to the observed state-head commit. Update `refs/heads/skillscout-state` with `force=false`, then re-read the exact ref and verify it equals the new commit. GitHub documents that `force=false` enforces a fast-forward and avoids overwriting work. [CITED: https://docs.github.com/en/rest/git/refs]

```python
observed = state_remote.get_exact_ref()
tree = state_remote.create_state_tree(validated_files)
commit = state_remote.create_state_commit(tree=tree, parents=(observed.sha,))
visible = state_remote.update_state_ref(commit, force=False)
if visible.sha != commit or state_remote.get_exact_ref().sha != commit:
    raise StateBranchConflict
```

A 409, 422, non-fast-forward, unexpected tree entry/mode, or changed reread is terminal for that workflow attempt. Fetch the new head, validate/rebuild, and resume through the same application on a later bounded attempt. Never force, merge SQLite, delete an unexpected file, or treat workflow concurrency as proof that conflicts cannot occur. [CITED: https://docs.github.com/en/rest/git/refs; VERIFIED: Phase 4 conflict policy]

### Pattern 4: JSON Authority and SQLite Rebuild

Use immutable content-addressed objects plus one canonical root:

```text
state/root.json
state/objects/sha256/ab/<64-hex>.json
state/databases/pipeline.sqlite3
state/databases/operations.sqlite3
state/databases/publication.sqlite3
```

`root.json` binds schema/version, prior root digest, state-head parent SHA, all three database digests, query/budget profiles, ordered run/candidate/search-page/reservation records, verified Phase 1/2/3 chain projections, safe artifact objects, publication intents/checkpoints/records, and object locators. Ownership is exact: `pipeline.sqlite3` is exported/imported by the existing `SQLiteStateStore` and owns Phase 1 plus Phase 3 tables/projections; `operations.sqlite3` is owned only by `OperationsStateStore` and contains Phase 5 discovery/page/reservation/run-health facts; `publication.sqlite3` is exported/imported by the existing `PublicationStateStore` and owns Phase 4 attempts/checkpoints/records. `operations_state.py` must not duplicate either existing store's private schema. Generated Skill content may be retained because it is a SkillScout artifact; raw third-party repository text may not. [VERIFIED: existing stage/Phase 3/publication contracts and OPS-03]

Restore order:

1. Validate branch/ref, tree allowlist, file modes, sizes, locators, canonical JSON, root self-hash, prior-root link, and every object hash.
2. For each owned database, call its explicit canonical export/validated import seam: `SQLiteStateStore` verifies/replays Phase 1 and Phase 3 facts through its existing schema, insertion and chain-validation paths; `OperationsStateStore` verifies/replays discovery facts through its own insertion validators; `PublicationStateStore` verifies/replays Phase 4 facts through its existing transition and record validators. Require `PRAGMA integrity_check` exactly `ok`, exact `user_version`/schema fingerprint, foreign-key check, and every store-owned chain verifier.
3. If one database is missing/corrupt but the complete JSON authority is valid, rebuild only that store into a fresh private database through its existing validated insertion paths, fully verify it, create a consistent snapshot, and atomically replace its local database.
4. Export all three rebuilt projections and require exact cross-store equality with the root projection, including shared run/candidate/publication keys and digests, before granting reuse authority.

[CITED: https://www.sqlite.org/pragma.html#pragma_integrity_check; CITED: https://www.sqlite.org/backup.html; VERIFIED: `SQLiteStateStore.verify_run_chain` and `verify_candidate_run_chain`]

### Pattern 5: One Workflow, Two Authority Zones

Use one workflow containing two separate application entry points and authority zones. The discovery job checks out exact code, restores the exact state head, invokes only unprotected `DiscoveryApplication`, runs Search through Review, persists bounded eligible run/candidate/workflow locators plus their complete authorities, and pushes a state snapshot. Discovery has no Phase 4 factory, remote publisher or catalog credential resolver. Its only job output is the bounded locator/authority set, root digest, and exact state-head SHA. The protected job checks out the same code revision, invokes only the protected publication entry point, re-reads and verifies the exact named state commit and all three stores, resolves the bounded locators, and re-derives every candidate admission locally. Only after all admission checks pass may it mint the catalog-scoped App token; only after minting may it construct and call the existing `PublicationApplication` sequentially. Eligibility or a handoff value alone never grants publication authority. [VERIFIED: Phase 4 candidate-only handoff pattern; APPROVED]

The existing Phase 4 Gate B4 remains valid only for `publish-candidate.yml` SHA-256 `224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c` and its reviewed identities. Because `discover.yml` introduces a distinct protected workflow surface, it needs a fresh, separately authorized Gate B4 bound to its exact bytes and App/catalog/ruleset/environment/reviewer/installation identities before its publication job receives production credit. The Phase 5 concurrency canary is separate evidence and cannot substitute for that gate. [APPROVED]

```yaml
# Source: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
on:
  schedule:
    - cron: "17 3 * * *"
  workflow_dispatch:

concurrency:
  group: skillscout-production
  cancel-in-progress: false
  queue: max
```

Current GitHub documentation says `queue: max` retains multiple pending runs; if repository validation rejects this newer syntax, omit it but retain `cancel-in-progress: false` and explicitly document that GitHub may replace an older pending run while never canceling the running run. [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax]

### Outcome Taxonomy

| Class | Examples | Candidate behavior | Run behavior |
|---|---|---|---|
| Business terminal | deterministic filter reject, no workflow, qualification reject, validation reject, Reviewer NO | Persist terminal evidence; continue | May complete normally |
| Completed/reused | exact Phase 2/3 completion or revalidated Draft | No replay and no new semantic reservation | Continue |
| Confirmed retryable | GitHub 429/rate exhaustion with reset; semantic request rejected before semantic processing with deterministic provider evidence | Persist attempt/defer time; bounded retry owned by pipeline | Stop remote calls at rate exhaustion or continue after policy delay |
| Outcome-unknown | connection loss, timeout, ambiguous 5xx, or post-send failure across OpenAI or DeepSeek may have reached provider | Consume attempt and repository reservation; never auto-repeat | Quarantine candidate/manual retry; continue safe candidates |
| Conflict/integrity | state-head change, malformed state object, SQLite/chain mismatch | No candidate work | Fail closed |
| Permanent operational | auth/config/schema/permission failure | No retry | Fail closed |

The current OpenAI Extractor/Generator/Reviewer adapters and DeepSeek compatibility path collapse rate limits, 5xx, timeout, and connection failures into one transient class. With `store=false`, neither provider boundary has an idempotency/retrieval contract proving replay is duplicate-free. Phase 5 therefore introduces a closed `confirmed_retryable` versus `semantic_outcome_unknown` classification through every semantic adapter and both Phase 2/3 retry orchestrators. A timeout, connection loss, ambiguous 5xx, or any post-send indeterminate failure is always unknown: exactly one request, durable consumed attempt, quarantine/manual retry, no automatic replay. Only deterministic evidence that no semantic result was produced may enter the existing bounded retry loop. [APPROVED]

### Anti-Patterns to Avoid

- **Budget as a local integer:** a crash resets it. Use durable unique reservations.
- **Count provider calls as semantic candidates:** DISC-02 limits candidate repositories; attempt counts are separate and still bounded.
- **Reserve after the LLM call:** the crash window permits an uncounted duplicate.
- **Deduplicate by `full_name`:** repositories can be renamed. Numeric repository ID is the stable first key; name remains provenance.
- **Trust Search qualifiers as Filter evidence:** always re-run existing Scout/Filter at a pinned commit.
- **Persist Search descriptions or raw errors:** they are untrusted source text and can contain injection or credential-shaped strings.
- **Follow raw `Link` URLs:** validate the fixed HTTPS GitHub host/endpoint and derive only a bounded next-page integer.
- **Copy a live SQLite file:** use a locked snapshot/backup; journals and WAL make blind copies unsafe.
- **Merge or force-push state:** binary merges and forced refs destroy replay authority.
- **Use Actions artifacts/cache as recovery state:** they are short-lived and non-canonical.
- **Expose query text as `workflow_dispatch` free-form input:** query policy would become an unaudited runtime decision.
- **Run all work in the catalog-protected job:** it unnecessarily exposes catalog credentials to discovery/semantic processing.
- **Assume Actions concurrency eliminates conflicts:** humans, reruns, or another workflow can still move the state ref.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| HTTP transport/retry hiding | Ad hoc `urllib`, shell `curl`, implicit SDK retries | Existing serial `httpx` client and deterministic retry policy | Existing caps, same-host checks, request IDs, and sanitized failures |
| JSON validation | Dictionary shape checks spread across orchestration | Strict frozen Pydantic models + canonical JSON | Rejects extra/malformed/oversized state consistently |
| Database consistency check | Custom page/file inspection | `PRAGMA integrity_check`, foreign-key check, schema fingerprint, chain verifiers | SQLite owns physical consistency; SkillScout owns semantic consistency |
| Active DB copy | Raw `cp` during writes | SQLite backup/serialize under lock | Officially consistent snapshot behavior |
| Git CAS protocol | Force push or last-writer-wins upload | Git objects + parent-bound commit + `force=false` ref update + reread | Preserves other work and produces explicit conflicts |
| Workflow engine | Event bus or multi-agent scheduler | One application loop over existing stage applications | Requirements are small and stages already have contracts |
| Publication dedup | Local PR-number cache | Existing Phase 4 remote marker/head/PR reconciliation | Remote truth survives state loss |
| Secret redaction after logging | Regex cleanup of arbitrary logs | Closed structured log schemas and never ingest secret/raw fields | Prevention is stronger than best-effort scrubbing |

**Key insight:** the difficult part is durable authority, not looping over Search results. Reuse the verified business stages and invest new code in reservations, state export/import, remote-head reconciliation, and negative tests.

## Common Pitfalls

### Pitfall 1: Query Starvation and Moving Pagination

**What goes wrong:** the first query fills all 100 slots, later queries never contribute, or updates between pages shift results.  
**Why it happens:** Search is a live ranked view, not a snapshot. [CITED: https://docs.github.com/en/rest/search/search]  
**How to avoid:** fixed round-robin queries, small fixed pages, first-seen repo-ID dedup, page observations, and a truthful `partial/incomplete` run flag.  
**Warning signs:** one query owns nearly every source record; duplicate rates spike between adjacent pages.

### Pitfall 2: Budget Expansion on Resume

**What goes wrong:** an interrupted candidate is selected again and consumes a second semantic slot, or failed candidates are “refunded.”  
**Why it happens:** selection is derived from current successful rows rather than immutable reservations.  
**How to avoid:** unique durable reservation rows and manifest events; verify ordinals and count on every restore.  
**Warning signs:** reservation count differs between SQLite and root projection, gaps in ordinals, or more than 20 distinct repository IDs.

### Pitfall 3: Outcome-Unknown Semantic Replay

**What goes wrong:** a timeout occurs after the provider accepted the request; automatic retry pays twice and may produce different output.  
**Why it happens:** request completion and local durable result are not one transaction, and `store=false` prevents later retrieval by response ID. [VERIFIED: current provider boundary]  
**How to avoid:** remote-durable pre-call attempt record, split confirmed rejection from unknown outcome, quarantine unknown attempts, and require explicit human retry if duplicate-free semantics are mandatory.  
**Warning signs:** an abandoned/running attempt followed automatically by a new provider request without a terminal response classification.

### Pitfall 4: SQLite Appears Valid but Disagrees with JSON

**What goes wrong:** `integrity_check` passes physical structure while a chain, object locator, or budget projection was tampered.  
**Why it happens:** physical consistency is not application authenticity.  
**How to avoid:** require physical check, exact schema fingerprint, canonical bytes, digest graph, all chain verifiers, and projection equality.  
**Warning signs:** clean `integrity_check` with a root/database digest mismatch.

### Pitfall 5: State Commit Conflict Is Hidden

**What goes wrong:** a later writer overwrites the state used by an in-progress run.  
**Why it happens:** forced ref update, incorrect parent, or no post-update reread.  
**How to avoid:** observed-head parent, `force=false`, conflict classification, and exact ref reread.  
**Warning signs:** commit parent is not the recorded prior state head or a 409/422 is retried with force.

### Pitfall 6: Rate-Limit Hammering

**What goes wrong:** retries continue before reset or secondary-limit guidance and risk integration bans.  
**Why it happens:** only `Retry-After` is honored, or each candidate creates a parallel client.  
**How to avoid:** keep one serial client, record `resource/remaining/reset`, stop new requests when remaining is zero, honor `Retry-After`/reset, and bound exponential retry. GitHub explicitly advises waiting and eventually failing. [CITED: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api]  
**Warning signs:** requests while `remaining=0`, missing rate resource, or concurrency greater than one.

### Pitfall 7: State Branch Becomes a Data Leak

**What goes wrong:** Reader scratch text, provider bodies, authorization headers, or environment dumps are committed.  
**Why it happens:** serializing application objects wholesale or uploading the runner directory.  
**How to avoid:** build the tree from an exact allowlist of canonical objects and database snapshots; scan the prospective tree before blob creation.  
**Warning signs:** README/source paths outside provenance metadata, arbitrary `.json`, logs, `.env`, `*-wal`, `*-journal`, or unexpected files.

### Pitfall 8: Protected Publication Boundary Is Bypassed

**What goes wrong:** the discovery job receives the catalog App key/token or can supply an admission digest.  
**Why it happens:** one broad job or dynamic output carries protected authority backward.  
**How to avoid:** candidate-only run/root/state-head handoff; protected job re-reads exact state and derives intent/admission before token minting.  
**Warning signs:** catalog variables in discovery environment, App token before admission, team reviewers, or caller-supplied intent.

## Code Examples

### Strict Search Projection

```python
# Pattern source: src/skillscout/adapters/github.py
class SearchRepositoryObservationV1(StrictFrozenModel):
    repository_id: int
    owner: str
    name: str
    private: bool
    visibility: str
    fork: bool
    archived: bool
    disabled: bool
    default_branch: str | None

class AdmittedDiscoveredCandidateV1(StrictFrozenModel):
    observation: SearchRepositoryObservationV1
    private: Literal[False]
    visibility: Literal["public"]
    fork: Literal[False]
    archived: Literal[False]
```

Provider parsing may ignore unconsumed fields. Persist a closed observation and a deterministic admission/rejection decision so a provider/query mismatch remains auditable; only the admitted projection may require the public/non-fork literals. Neither durable model includes description/topics/text-match content. [VERIFIED: existing `_LenientFrozenModel` → strict domain projection and Filter decision records]

### SQLite Restore Gate

```python
# Source: https://www.sqlite.org/pragma.html#pragma_integrity_check
rows = tuple(row[0] for row in connection.execute("PRAGMA integrity_check"))
if rows != ("ok",):
    rebuild_from_verified_manifests()
verify_exact_schema(connection)
verify_all_run_chains(connection)
verify_budget_projection(connection, root_manifest)
```

### Business Rejection Is Not an Exception Retry

```python
result = run_existing_candidate_path(candidate)
if result.outcome in BUSINESS_TERMINALS:
    state.record_candidate_terminal(result)
    durability.sync("candidate_terminal")
    continue
```

This preserves Phase 2/3 terminal evidence and lets one bad repository avoid aborting the remaining candidate funnel. [VERIFIED: existing structured rejection/terminal-summary patterns]

## State of the Art

| Old / unsafe approach | Current recommended approach | Evidence | Impact |
|---|---|---|---|
| Copy an active SQLite file | Online backup/serialized locked snapshot; retain journal/WAL awareness | [CITED: https://www.sqlite.org/backup.html] | Consistent state-branch database |
| Force-update a shared state branch | Parent-bound commit and `force=false` fast-forward update | [CITED: https://docs.github.com/en/rest/git/refs] | Conflict instead of lost work |
| One running + one replaceable pending Actions run | Current hosted syntax offers `queue: max` | [CITED: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax] | Scheduled and manual runs can queue without canceling |
| Treat Search total as exhaustive | Record `incomplete_results`, cap, cursor, and observed candidates | [CITED: https://docs.github.com/en/rest/search/search] | Honest audit semantics |
| Retry all SDK “transient” exceptions identically | Separate confirmed rejection from outcome-unknown requests | [VERIFIED: current adapter grouping; CITED: official OpenAI Python SDK] | Prevent unprovable duplicate-free claims |

**Deprecated/outdated for this project:**

- Using the Actions cache/artifact as state is explicitly out of scope. [VERIFIED: `.planning/REQUIREMENTS.md`]
- Mutating a state ref with force or merging SQLite bytes must not be introduced. [CITED: GitHub refs behavior; VERIFIED: project integrity constraints]
- The codebase pins GitHub API version `2022-11-28`; do not silently change it merely because current examples show a newer version. A version upgrade needs its own recorded compatibility evidence. [VERIFIED: `GITHUB_API_VERSION` in both GitHub adapters]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | The four recommended v1 search terms yield a useful, sufficiently diverse funnel. | Recommended Defaults | Low yield or biased candidates; Phase 6 must measure and version a replacement |
| A2 | `sort=updated`, 25-item round-robin pages, and four pages/query provide an acceptable discovery/cost balance. | Recommended Defaults | Too many misses or duplicates; telemetry supports a later versioned adjustment |
| A3 | The repository’s hosted Actions environment accepts current `queue: max` syntax. | Workflow Pattern | If rejected, omit it and accept replacement of older pending runs while keeping the running run non-cancelled |

No security, compliance, secret-retention, or authorization decision rests on these assumptions.

## Open Questions (RESOLVED)

1. **Outcome-unknown semantic attempts**
   - **Approved:** classify as `semantic_outcome_unknown`, consume the attempt and repository reservation, quarantine that candidate, continue safe candidates, and require a separately authorized manual retry. No OpenAI or DeepSeek adapter/runner may automatically replay it.

2. **Hosted queue grammar**
   - **Approved:** gate `queue: max` behind repository parsing/audit plus bounded hosted evidence. If unsupported, omit it and retain the fixed shared group with `cancel-in-progress:false`; document that GitHub may replace an older pending run while never cancelling the active run.

3. **Immutable state-object retention**
   - **Approved:** perform no object pruning in Phase 5. Record reachability and bounded size telemetry only; any later pruning policy requires explicit human approval.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---:|---:|---|
| Repository-local `uv` | locked tests/runtime | ✓ | 0.11.29 | none |
| Managed Python | application | ✓ | 3.13.14 | none |
| Python SQLite | state/rebuild | ✓ | 3.53.1 | none |
| System `sqlite3` | diagnostics only | ✓ | 3.51.0 | Python module |
| Git | local development | ✓ | 2.50.1 | GitHub REST for production state |
| `httpx` | GitHub REST | ✓ | 0.28.1 | none |
| OpenAI SDK | semantic stages | ✓ | 2.46.0 | DeepSeek remains explicit opt-in, not an outage fallback |
| pytest | validation | ✓ | 9.1.1 | none |

[VERIFIED: local probes using repository-local cache and locked environment]

**Missing dependencies with no fallback:** none.  
**Missing dependencies with fallback:** none.  
**Focused baseline:** 248 existing GitHub, resume, state-integrity, publication-recovery, and action-audit tests passed in 4.12 seconds. [VERIFIED: local test run]

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest 9.1.1 |
| Config file | `pyproject.toml` |
| Quick run command | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_discovery_domain.py tests/test_discovery_application.py tests/test_github_search.py -x` |
| Full suite command | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` |

[VERIFIED: `pyproject.toml` and environment]

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| DISC-01 | exact versioned query set; schedule + manual trigger | unit + workflow audit | `pytest -q tests/test_discovery_domain.py tests/test_discovery_workflow.py -x` | ❌ Wave 0 |
| DISC-02 | 100 repo-ID cap and 20 non-refundable semantic reservations across crash/resume/retry | unit + crash integration | `pytest -q tests/test_discovery_application.py -k "budget or resume or crash" -x` | ❌ Wave 0 |
| DISC-03 | query/page/rate/dedup records including incomplete results | adapter + contract | `pytest -q tests/test_github_search.py tests/test_operations_state.py -x` | ❌ Wave 0 |
| OPS-02 | state restore, integrity check, JSON rebuild, fast-forward push/conflict, single concurrency group | integration + mutation | `pytest -q tests/test_operations_state.py tests/test_state_branch.py tests/test_discovery_workflow.py -x` | ❌ Wave 0 |
| OPS-03 | no raw source/secrets in database, JSON, logs, artifacts, job outputs, or prospective Git tree | adversarial + static audit | `pytest -q tests/test_discovery_security.py tests/test_phase5_acceptance.py -x` | ❌ Wave 0 |

### Mandatory Scenario Matrix

| Area | Required fixtures / mutation |
|---|---|
| Search | one page; multiple pages; duplicate within/across queries; rename same repo ID; public/non-fork mismatch; `incomplete_results`; malformed JSON; oversized body; hostile description; hostile `Link`; 403/429/500; missing rate headers |
| Budgets | exactly 100/20; 101st/21st denied; crash before reservation; crash after reservation/before call; completed reuse; business rejection not refunded; transient retry not a new candidate; tampered counter/ordinal |
| Composition | Filter reject continues; Reader reject/stop; zero workflows; multi-workflow; qualification/validation/review rejects; one eligible Draft; exact completed Phase 2/3 reuse |
| Semantic interruption | explicit 429 retry; outcome-unknown timeout quarantined; running attempt restored; request/usage telemetry bounded; no SDK hidden retry |
| State | clean restore; DB byte corruption; schema tamper; valid DB/wrong root digest; missing DB rebuild; missing object; object hash swap; rollback root; unexpected path/mode/symlink; killed writer |
| Remote state | absent branch bootstrap; normal fast-forward; 409/422; head changes between read/update; response lies; reread mismatch; no force route |
| Publication | local state missing/remote Draft exists; remote head conflict; non-Draft PR; human-modified owned tree; interruption after commit/ref/PR/reviewer; no duplicate Draft |
| Security | injection canaries in every discarded Search text field; credential/header/PEM/JWT canaries; log/state/artifact/tree scan; no catalog token in discovery; no candidate shell interpolation |
| Workflow | exact immutable Action SHAs; default-branch schedule/dispatch; fixed shared concurrency; non-cancel; queue behavior; minimum per-job permissions; protected late token minting |

### Sampling Rate

- **Per task commit:** the focused command for the touched module.
- **Per wave merge:** discovery/state/workflow focused suites plus existing `test_pipeline_resume.py`, `test_state_integrity.py`, `test_phase3_pipeline.py`, and publication recovery/security suites.
- **Phase gate:** Ruff, full locked pytest, an independent stdlib-only Phase 5 acceptance inspector, and a workflow/static secret-surface audit all green before `$gsd-verify-work`.

### Wave 0 Gaps

- [ ] Add all Phase 5 test modules listed in Recommended Project Structure.
- [ ] Add recorded Search and state-branch fixtures; they must contain no live credentials or copied full repository text.
- [ ] Add a test-only interruption seam at each durability barrier.
- [ ] Add an independent read-only acceptance tool that imports no project code, performs no network/write, and mutation-tests all five requirement inverse maps.
- [ ] Add workflow parsing/audit coverage for `queue: max` and the exact pinned Action identities.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | yes | GitHub runtime token and protected GitHub App installation token, injected late |
| V3 Session Management | no | No user sessions |
| V4 Access Control | yes | Per-job minimum permissions, distinct state/source and catalog authorities, protected environment |
| V5 Input Validation | yes | Strict Pydantic contracts, bounded JSON/bytes, fixed hosts/routes/paths, deterministic filters |
| V6 Cryptography | yes | TLS through `httpx`; stdlib SHA-256 content addressing; never custom cryptography |

[VERIFIED: project stack and Phase 4 authority model]

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Search-description prompt injection | Elevation / Information Disclosure | Discard all prose at Search boundary; only existing Reader envelope reaches Extractor |
| Malicious owner/name/query shell injection | Tampering / Elevation | No free-form query input; HTTP parameters; strict segments; no candidate interpolation into shell |
| Pagination SSRF/open redirect | Spoofing / Information Disclosure | Fixed HTTPS API host/endpoint; parse bounded next-page integer, not arbitrary URL |
| Repo rename aliases duplicate work | Spoofing | Numeric repository ID dedup; re-observe metadata in Scout |
| Budget reset/tamper | Tampering / Repudiation | Transactional unique reservations, content-addressed events, full projection verification |
| State rollback | Tampering | Root prior-digest chain, observed remote head, exact commit parent, workflow run metadata |
| State overwrite race | Tampering / Denial of Service | `force=false`, reread, conflict stop, fixed concurrency group |
| Corrupt/partial SQLite upload | Tampering / Denial of Service | Consistent snapshot, DB digest, integrity/schema/chain checks, JSON rebuild |
| Secret copied into state/tree/log | Information Disclosure | Closed field allowlists, prospective-tree scan, no environment dump/raw errors/provider bodies |
| GitHub secondary-rate abuse | Denial of Service | One serial client, header telemetry, reset-aware bounded backoff and stop |
| Outcome-unknown LLM duplicate | Repudiation / Cost abuse | Pre-call durable attempt, quarantine ambiguous outcome, human-authorized retry |
| Duplicate or hijacked Draft | Spoofing / Tampering | Existing publication key, machine marker, remote head/tree/PR reconciliation |
| Catalog token exposed to discovery | Elevation | Separate protected job, local re-admission, late App token minting |
| State-branch artifact executes code | Elevation | Exact JSON/SQLite path allowlist; never execute files from state; code always from reviewed default-branch SHA |

### Logging and Persistence Allowlist

Allow only stable IDs/digests, schema/policy/query/model versions, candidate repository ID/full name/URL, exact commit SHA, license SPDX, query/page/item ordinals, rate-limit numeric facts/resource, closed outcome/error codes, bounded request IDs, latency/token counts, state/catalog non-secret IDs, Draft number/URL, and byte/count metrics. [VERIFIED: existing safe telemetry pattern]

Forbid source descriptions, README/docs/source bodies, Reader scratch bundles, authorization headers, tokens, keys, JWT/PEM material, environment dumps, raw exceptions, arbitrary provider error bodies, raw response headers, and unvalidated URLs/paths. [VERIFIED: OPS-03 and `AGENTS.md`]

## Sources

### Primary (HIGH confidence code/project authority)

- `AGENTS.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, and `.planning/STATE.md` — locked project and phase constraints.
- Phase 1–4 summaries and verification — verified retry, state, extraction, candidate, and publication patterns.
- `src/skillscout/adapters/state.py`, `application/pipeline.py`, `application/phase3.py`, `application/publication.py`, GitHub adapters, CLI/bootstrap, tests, workflow, `pyproject.toml`, and `uv.lock` — existing integration seams and exact versions.

### Secondary (MEDIUM confidence official hosted/current documentation)

- https://docs.github.com/en/rest/search/search — Search endpoint, pagination parameters, limits, response envelope, incomplete results.
- https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories — public/archive/fork query semantics.
- https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api — Link pagination.
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api — headers, primary/secondary exhaustion, retry guidance.
- https://docs.github.com/en/rest/git/refs — create/update refs, required permissions, fast-forward behavior.
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax — schedule, workflow dispatch, permissions, concurrency, queueing.
- https://www.sqlite.org/pragma.html#pragma_integrity_check — database physical integrity.
- https://www.sqlite.org/backup.html and https://www.sqlite.org/howtocorrupt.html — consistent backup and unsafe copy pitfalls.
- https://github.com/openai/openai-python — official SDK error/request-ID behavior; no duplicate-free Responses replay guarantee was found.

### Tertiary (LOW confidence)

- The proposed initial query terms and page distribution are marked `[ASSUMED]` and require Phase 6 yield evaluation.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new dependency; exact locked/runtime versions verified.
- Architecture: HIGH — composes verified codebase seams; state-branch hosted behavior is supported by official docs.
- Search defaults: LOW — terms/yield are product hypotheses.
- GitHub Actions queue behavior: MEDIUM — current official documentation, not yet repository-tested.
- Pitfalls/security: HIGH for codebase/state boundaries; MEDIUM for hosted transient edge behavior.

**Research date:** 2026-07-27  
**Valid until:** 2026-08-03 for GitHub/OpenAI hosted behavior; 2026-08-26 for stable codebase/SQLite patterns.
