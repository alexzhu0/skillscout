# SkillScout v0.1.0 Preview Release Notes

SkillScout `0.1.0` is a public preview of an auditable Python pipeline that turns bounded, read-only evidence from public GitHub repositories into validated Agent Skill candidates and, through a separately controlled publication boundary, human-reviewable Draft Pull Requests.

This preview demonstrates the implemented pipeline and its verification evidence. It does **not** make a whole-product production-readiness claim. Phase 5 automated discovery operations completed independent verification on **2026-07-28** with **6/6 must-haves** and **5/5 requirements** satisfied, including a fresh exact-byte **Gate B4** for the reviewed workflow, GitHub App installation, catalog ruleset, protected environment, and reviewer configuration. The historical V2 five-repository benchmark lock is being rebound through a new state-only target run, but this implementation has not yet been merged or used live. Fresh authority, a real benchmark, replay, fresh Gate B4, and Draft PR acceptance remain pending before whole-product production readiness.

## Implemented preview scope

### Auditable dry-run

The `skillscout dry-run` command exercises the versioned pipeline spine against a frozen local fixture. It records durable SQLite state, canonical manifests, stage checkpoints, lineage, and a local publication plan. The terminal result is `planned_not_published`, and the dry-run runtime admits no remote-write adapter.

### Public-repository extraction

The `skillscout extract-repo` command processes one explicitly described public GitHub repository at an exact commit SHA. It uses bounded GitHub REST reads instead of cloning the repository. Deterministic filtering and reading enforce repository, license, path, file-type, symlink, binary, Git LFS, and byte-budget rules before semantic extraction.

Repository content remains untrusted data. SkillScout does not install source-repository dependencies, import source modules, build the project, invoke repository scripts, or execute repository code.

### Validated Skill candidate

The `skillscout build-candidate` command consumes verified extraction evidence and runs isolated qualification, generation, structural and safety validation, and independent semantic review stages. A publishable local candidate must preserve source attribution and lineage, pass the official `skills-ref` validator and local deterministic checks, receive a positive independent review at the required confidence, and materialize as a frozen package with canonical evidence.

Within each generated Skill package, the preview writes the required `SKILL.md` instruction document and supporting reference/provenance files. It does not generate executable `scripts/` content from an external repository.

### DeepSeek V4 provider profile

OpenAI remains the default semantic provider. The explicit `deepseek` provider path fixes extraction and generation to `deepseek-v4-flash`, while independent review uses `deepseek-v4-pro`, at the official configured endpoint. Requests disable thinking, do not expose tools, request one JSON object, use zero SDK retries, and cross the provider boundary only after strict local Pydantic validation.

The DeepSeek path is covered by recorded-transport and boundary tests. This preview does not claim live-provider availability, latency, output quality, or service-level guarantees.

### Controlled Draft PR implementation

The `verify-publication-admission` and `publish-candidate` commands implement a separate, late-authority publication boundary. The publisher revalidates candidate evidence, confines writes to the configured catalog and derived machine branch, reconciles existing remote state, creates or updates one Draft PR, and requests configured individual human reviewers.

The committed workflow is manually dispatched, separates unprivileged admission from the protected publication job, pins its approved third-party Actions to full commit SHAs, and mints a catalog-scoped installation token only after protected revalidation.

Successful automated publication ends with a **Draft PR**; failures and ambiguous states fail closed or require manual intervention. SkillScout has no merge, approve, review-submission, auto-merge, ready-for-review, ruleset-administration, default-branch-write, or automated cleanup operation. A human must review and decide what happens next.

## Verification evidence

The current observed baseline, recorded on **2026-07-28**, includes a focused Phase 5 and cross-phase release suite of `920 passed`:

- Locked full test suite: `1916 passed, 2 skipped`.
- The two skipped cases are the separately authorized live-canary paths under ordinary offline configuration.
- Offline tests cover stage contracts, public-repository filtering and bounded reads, semantic-provider boundaries, candidate generation and validation, resumability and tamper detection, publication reconciliation, Draft-only transport, forbidden production surfaces, and protected-workflow structure.

This count is a dated observation, not a permanent compatibility or pass-count contract. Test counts will change as coverage and release gates evolve. See [Testing](docs/TESTING.md) for the commands, suite organization, and current quality-check caveats.

### V2 five-repository benchmark lock

The V2 five-repository benchmark lock was successfully persisted for source commit `7bab6abcb89b5287e8d32077333fd4383331d6e5` by the [acceptance workflow run](https://github.com/alexzhu0/skillscout/actions/runs/30878463167).

- Acceptance workflow SHA-256: `164cfd4eb25af493f4fad42ff25b6175d8f56a277e5539a121e021822fda1894`
- Selection digest: `sha256:09aa2df9686f3094f361510fd2923edb6097df801c658d39e641f9207ffdb1f4`
- Nomination digest: `sha256:46535e6ce499a710c2ecf5b9cd0db8134682dbac2429b8e3d7af4035130297ea`
- Lock digest: `sha256:3c1a9b2737ee79c58696e5e601b61e49b35549630f5826ac9fef3c694feaffa6`

Persisting this historical lock is not a live-authority grant or an adversarial acceptance result. The next, still-unperformed sequence is `rebind-benchmark-lock → record-live-authority → run-benchmark → run-replay`: a fresh target acceptance run reuses the five unchanged entries but binds final source/workflow bytes. Rebind receives no model or catalog credential and produces only a sanitized state receipt. Each state-only approval and the subsequent authority carrier is single-use; any code or workflow change after merge invalidates every approval in the sequence. A real benchmark execution, exact replay, fresh Gate B4, and Draft PR acceptance are still pending; SkillScout remains not production-ready.

## Security posture

- Public GitHub repositories are the only supported source. Private-repository ingestion is outside the preview scope.
- All external repository bytes are untrusted and are processed as inert data under deterministic size, path, schema, and evidence constraints.
- Source repositories are never cloned or executed, and their dependencies are never installed.
- Semantic requests have no tool or code-execution capability. Raw repository bundles do not cross into candidate generation and review.
- Credentials are injected only by the runtime, introduced as late as possible, excluded from durable models and public diagnostics, and must never be committed or copied into evidence.
- Publication authority is isolated from extraction and generation. Candidate-only evidence does not confer catalog authority.
- The production adapter and workflow expose Draft creation/update and individual reviewer requests only. Merge, approve, ready-for-review, administration, and default-branch mutation are absent from the SkillScout surface.
- GitHub's coarse Pull Requests permission may retain capabilities outside SkillScout if a token is stolen or misused. Gate B4 verified the scoped live controls and causal denials for the reviewed identity, while the closed application surface prevents SkillScout from expressing approve, ready, merge, or administration operations.

## Operational prerequisites

Local preview use requires:

- Python `3.13.14` within the supported package range `>=3.13,<3.14`;
- the repository-pinned `uv 0.11.29` executable;
- an installation synchronized from `uv.lock`;
- writable private locations for SQLite state and generated evidence;
- a selected semantic provider and its runtime-injected credential for live semantic commands; and
- a GitHub read credential with only the access needed for public-repository API reads.

Controlled publication additionally requires a separately governed protected environment, the approved GitHub App installed only on the controlled catalog, exact catalog identity and protected base-branch configuration, an active ruleset with no App bypass, a non-empty list of authorized individual reviewers, empty team-reviewer configuration, and a distinct human or administrator authority for canary cleanup.

Do not enable `publish-candidate` from an ordinary developer shell. Follow [Configuration](docs/CONFIGURATION.md) and complete the release gates below before introducing publication credentials.

## Known limitations

- Gate B4 evidence is identity- and byte-bound; any workflow, App scope, catalog, ruleset, reviewer, or installation change requires a fresh canary before publication is credited.
- Phase 5 implements and verifies versioned GitHub Search, daily and manual triggers, hard limits of 100 candidates and 20 semantic reservations per run, three-store state-branch recovery with non-force CAS, and credential-zone isolation. The fresh Gate B4 evidence is bound to the current workflow SHA-256 digests: discover `8157cb686b9bf18bfa800811b1fe1529ed9a15ec371fe36ec1708233052b7cfd`, publish `96ce9f39db49ce647a88b83ec4db3cb0135e5cf51c1eb2f11961cfd243b23cf0`, and canary `9c59cd9822eecec913f82d24c7880a443ba9416795b8996c6201f33c4df5805d`; changing any bound workflow or control-plane identity invalidates that evidence.
- The V2 five-repository benchmark lock is persisted, but the adversarial MVP acceptance run across those pinned real repositories has not been completed. Live authority, a real benchmark execution, replay, and Draft PR acceptance remain pending.
- Publication supports configured individual reviewers only. Team reviewer targets fail closed to manual handling.
- Live canary cleanup is intentionally not automated and must use separate human or administrator authority.
- The normal test suite is offline. Passing recorded-transport tests does not prove current third-party service availability or real catalog control-plane configuration.
- No push or pull-request CI workflow currently runs pytest or Ruff. The publication workflow is manual and publication-specific.
- No coverage threshold is configured, and the dated test baseline is not a coverage guarantee.
- The current release format is prerelease-quality; database, evidence-schema, CLI, and configuration compatibility are not yet promised across preview revisions.

## Upgrade guidance

1. Stop active SkillScout runs and record the exact current source revision, wheel, `uv.lock`, configuration version, and state locations.
2. Back up SQLite state and canonical evidence without copying credentials or protected logs.
3. Review the new release notes, schema changes, lock-file diff, pinned Action identities, and configuration changes.
4. Install or synchronize from the new release's exact lock file; do not allow dependency resolution to float.
5. Run the locked full test suite and an offline `dry-run` into new temporary state and output locations.
6. Validate existing candidate evidence before reusing it. If the new version rejects old state or schemas, preserve the old data for audit and start a new state store instead of rewriting evidence in place.
7. Re-run every affected human approval or live canary whenever an approved byte identity, GitHub App scope, catalog ruleset, protected environment, or publication policy changes.

## Rollback guidance

1. Disable or withhold the protected publication environment and stop invoking the manual publication workflow.
2. Return to the previously recorded source revision, wheel, and exact lock file, then restore the matching private state backup if needed.
3. Run the prior version's locked offline tests and `dry-run` before resuming local processing.
4. Do not force-rewrite publication branches or automatically close, delete, merge, approve, or mark an existing PR ready. Inspect the catalog state and let an authorized human decide whether to retain, close, or clean up a Draft PR.
5. If remote publication state is ambiguous or differs from the recorded lineage, leave it unchanged and require manual intervention.

## Remaining release gates

The following gates remain before SkillScout can make a production-ready release claim:

1. **Phase 6 operational acceptance:** the historical V2 five-repository benchmark lock must first be rebound to final `main`, then receive fresh V2 live authority before the pinned-repository MVP matrix can adversarially exercise discovery budgets, serialized three-store recovery, credential isolation, and exact Gate B4 binding.
2. **Adversarial MVP acceptance:** five public repositories pinned to exact commits must exercise successful and rejected paths, prompt-injection samples, end-to-end idempotency, at least one real human-reviewed Draft PR, repeated platform canary evidence, secret scanning, and evidence for every release requirement.

## Production-ready release checklist

- [x] Phase 4 live canary Gate B4 is approved with non-secret evidence and separate-authority cleanup attestation.
- [x] The reviewed production identity cannot write the protected default branch, merge, administer rulesets, or access unauthorized repositories or secret resources.
- [x] SkillScout's production code, CLI, transport, and workflow expose no merge, approve, auto-merge, ready-for-review, or automated cleanup path.
- [x] The exact final locked Phase 4 validation chain passes, including Ruff, pytest, validation-map checks, Action audit, and acceptance inspectors.
- [ ] A push/pull-request CI quality gate runs the locked offline checks on the reviewed revision.
- [x] Automated discovery and operational state persistence meet the documented 100-candidate and 20-semantic-reservation hard budgets, three-store rebuild and non-force CAS requirements, serialized hosted-run behavior, and bounded recovery requirements.
- [ ] Five pinned public repositories and the adversarial corpus complete the MVP acceptance matrix.
- [ ] Repeated identical inputs produce no duplicate workflow, Skill, branch, reviewer notification, or Draft PR.
- [ ] At least one real eligible candidate reaches a Draft PR and is reviewed by a human; automation does not merge it.
- [ ] Logs, evidence, artifacts, state, prompts, and PR content pass secret and protected-data review.
- [ ] All release requirements have traceable verification evidence, and every residual risk and known limitation is documented.
- [ ] Upgrade, rollback, and incident procedures are rehearsed against the release candidate.

## Documentation

- [README](README.md) — project overview, quick start, CLI surface, and safety model
- [Architecture](docs/ARCHITECTURE.md) — system components, trust boundaries, state, and publication isolation
- [Configuration](docs/CONFIGURATION.md) — provider and protected publication settings
- [Getting started](docs/GETTING-STARTED.md) — prerequisites, installation, and first run
- [Development](docs/DEVELOPMENT.md) — local development and contribution workflow
- [Testing](docs/TESTING.md) — test commands, fixtures, security checks, and dated baseline
