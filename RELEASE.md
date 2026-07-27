<!-- generated-by: gsd-doc-writer -->
<!-- GSD:DOC generated -->

# SkillScout v0.1.0 Preview Release Notes

SkillScout `0.1.0` is a public preview of an auditable Python pipeline that turns bounded, read-only evidence from public GitHub repositories into validated Agent Skill candidates and, through a separately controlled publication boundary, human-reviewable Draft Pull Requests.

This preview demonstrates the implemented pipeline and its offline verification evidence. It does **not** make a production-readiness claim. Phase 4 live canary **Gate B4 is pending**, so the production GitHub App, catalog ruleset, protected environment, and real Draft PR path have not yet been accepted as a complete live control set.

## Implemented preview scope

### Auditable dry-run

The `skillscout dry-run` command exercises the versioned pipeline spine against a frozen local fixture. It records durable SQLite state, canonical manifests, stage checkpoints, lineage, and a local publication plan. The terminal result is `planned_not_published`, and the dry-run runtime admits no remote-write adapter.

### Public-repository extraction

The `skillscout extract-repo` command processes one explicitly described public GitHub repository at an exact commit SHA. It uses bounded GitHub REST reads instead of cloning the repository. Deterministic filtering and reading enforce repository, license, path, file-type, symlink, binary, Git LFS, and byte-budget rules before semantic extraction.

Repository content remains untrusted data. SkillScout does not install source-repository dependencies, import source modules, build the project, invoke repository scripts, or execute repository code.

### Validated Skill candidate

The `skillscout build-candidate` command consumes verified extraction evidence and runs isolated qualification, generation, structural and safety validation, and independent semantic review stages. A publishable local candidate must preserve source attribution and lineage, pass the official `skills-ref` validator and local deterministic checks, receive a positive independent review at the required confidence, and materialize as a frozen package with canonical evidence.

Within each generated Skill package, the preview writes the required `SKILL.md` instruction document and supporting reference/provenance files. It does not generate executable `scripts/` content from an external repository.

### DeepSeek V4 Flash provider

OpenAI remains the default semantic provider. The explicit `deepseek` provider path fixes extraction, generation, and review to `deepseek-v4-flash` at the official configured endpoint. Requests disable thinking, do not expose tools, request one JSON object, use zero SDK retries, and cross the provider boundary only after strict local Pydantic validation.

The DeepSeek path is covered by recorded-transport and boundary tests. This preview does not claim live-provider availability, latency, output quality, or service-level guarantees.

### Controlled Draft PR implementation

The `verify-publication-admission` and `publish-candidate` commands implement a separate, late-authority publication boundary. The publisher revalidates candidate evidence, confines writes to the configured catalog and derived machine branch, reconciles existing remote state, creates or updates one Draft PR, and requests configured individual human reviewers.

The committed workflow is manually dispatched, separates unprivileged admission from the protected publication job, pins its approved third-party Actions to full commit SHAs, and mints a catalog-scoped installation token only after protected revalidation.

The automated terminal state is always a **Draft PR**. SkillScout has no merge, approve, review-submission, auto-merge, ready-for-review, ruleset-administration, default-branch-write, or automated cleanup operation. A human must review and decide what happens next.

## Verification evidence

The current observed baseline, recorded on **2026-07-27**, is:

- Locked full test suite: `1384 passed, 2 skipped`.
- The two skipped cases are the separately authorized live-canary paths under ordinary offline configuration.
- Offline tests cover stage contracts, public-repository filtering and bounded reads, semantic-provider boundaries, candidate generation and validation, resumability and tamper detection, publication reconciliation, Draft-only transport, forbidden production surfaces, and protected-workflow structure.

This count is a dated observation, not a permanent compatibility or pass-count contract. Test counts will change as coverage and release gates evolve. See [Testing](docs/TESTING.md) for the commands, suite organization, and current quality-check caveats.

## Security posture

- Public GitHub repositories are the only supported source. Private-repository ingestion is outside the preview scope.
- All external repository bytes are untrusted and are processed as inert data under deterministic size, path, schema, and evidence constraints.
- Source repositories are never cloned or executed, and their dependencies are never installed.
- Semantic requests have no tool or code-execution capability. Raw repository bundles do not cross into candidate generation and review.
- Credentials are injected only by the runtime, introduced as late as possible, excluded from durable models and public diagnostics, and must never be committed or copied into evidence.
- Publication authority is isolated from extraction and generation. Candidate-only evidence does not confer catalog authority.
- The production adapter and workflow expose Draft creation/update and individual reviewer requests only. Merge, approve, ready-for-review, administration, and default-branch mutation are absent from the SkillScout surface.
- GitHub's coarse Pull Requests permission may retain capabilities outside SkillScout if a token is stolen or misused. The closed application surface reduces that risk but does not replace the pending live platform controls.

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

- Phase 4 live canary Gate B4 is pending; no production-readiness claim is made.
- Automated GitHub Search discovery, scheduled operation, candidate budgets, and durable multi-run state-branch operations are not part of this preview.
- The adversarial MVP acceptance run across five pinned real repositories has not been completed.
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

1. **Phase 4 live canary Gate B4:** an independently authorized human must review the real catalog identity, GitHub App installation permissions, protected environment, reviewer configuration, active default-branch ruleset, lack of App bypass, and exact pinned workflow identities. The protected canary must use the production installation identity to create the intended machine-branch commit, Draft PR, and reviewer request while causally demonstrating denial of default-branch writes, merge, ruleset or administration access, unauthorized repository/resource access, and secret-resource access. Approve and ready-for-review must remain proven absent from SkillScout's production surface, without falsely claiming that GitHub denies every out-of-process use of the coarse token. Cleanup must be attested under separate human or administrator authority.
2. **Phase 4 final release chain:** after Gate B4, the validation map, Action audit, offline publication suites, acceptance mutation tests and inspectors, repository-wide Ruff check, locked full pytest suite, and terminal acceptance inspection must all pass from the same reviewed revision.
3. **Automated discovery operations:** bounded Search queries, daily/manual scheduling, hard candidate and semantic-call budgets, durable auditable state, concurrency control, and interruption/rate-limit recovery must be implemented and verified.
4. **Adversarial MVP acceptance:** five public repositories pinned to exact commits must exercise successful and rejected paths, prompt-injection samples, end-to-end idempotency, at least one real human-reviewed Draft PR, repeated platform canary evidence, secret scanning, and evidence for every release requirement.

## Production-ready release checklist

- [ ] Phase 4 live canary Gate B4 is approved with non-secret evidence and separate-authority cleanup attestation.
- [ ] The production identity cannot write the protected default branch, merge, administer rulesets, or access unauthorized repositories or secret resources.
- [ ] SkillScout's production code, CLI, transport, and workflow still expose no merge, approve, auto-merge, ready-for-review, or automated cleanup path.
- [ ] The exact final locked validation chain passes, including Ruff, pytest, validation-map checks, Action audit, and acceptance inspectors.
- [ ] A push/pull-request CI quality gate runs the locked offline checks on the reviewed revision.
- [ ] Automated discovery and operational state persistence meet the documented hard budgets and recovery requirements.
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
