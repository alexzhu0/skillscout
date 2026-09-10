# SkillScout v0.1.0 Preview Release Notes

SkillScout `0.1.0` is a public preview of an auditable Python pipeline that turns bounded, read-only evidence from public GitHub repositories into validated Agent Skill candidates and, through a separately controlled publication boundary, human-reviewable Draft Pull Requests.

This preview demonstrates the implemented pipeline and its verification evidence. It does **not** make a whole-product production-readiness claim. Phase 5 automated discovery operations completed independent verification on **2026-07-28** with **6/6 must-haves** and **5/5 requirements** satisfied, including an exact-byte **Gate B4** for the then-reviewed workflow, GitHub App installation, catalog ruleset, protected environment, and reviewer configuration. Those approvals are historical and do not grant authority to changed code or identities.

## September 9 status and extraction-terminal repair

The [September 3 live benchmark](https://github.com/alexzhu0/skillscout/actions/runs/33734530468), on source `bec2eeda2363d2fea639af5a68bca9d394cd16ec`, passed authority preflight and failed in the benchmark job. The recorded investigation found a Flash extraction response rejected by deterministic evidence validation. It did not produce a successful Skill acceptance result; replay was skipped.

The current repair preserves a verified extractor `schema_failure` through the coordinator as `schema_exhausted`, retaining request telemetry and the permanent candidate terminal. The CLI reports a closed `schema_exhausted` diagnostic rather than describing this known failure as local-state corruption. Offline regressions cover malformed provider JSON, non-verbatim evidence, and repeated invocation without another semantic request.

That terminal-only repair added no correction request, changed no validator, and granted no live execution authority. Its separately scoped correction follow-up is described below. Successful real extraction, controlled Skill-use comparison, five-repository acceptance, exact replay, and the separately authorized publication evidence remain open. See the [direction review](docs/project/2026-09-09-direction-review.md).

### September 9 bounded-correction offline milestone

DeepSeek extraction now has one durable correction opportunity for invalid structured output or zero surviving workflows where at least one rejected workflow has only non-verbatim excerpt errors. It uses the same pinned input, fixed trusted feedback, unchanged validators, and a distinct versioned prompt/policy. Every response keeps its own request ID and usage; each request consumes the existing limits of three extraction attempts and twenty acceptance-campaign semantic requests. A prior transport retry consumes a slot. No request is retried after correction, including a correction rejected with HTTP 429.

Explicit provider refusal markers are terminal for extraction, without interpreting free-text refusal claims or changing generation/review handling. Missing telemetry, stale/wrong predecessor model identity, changed correction policy, and fabricated decided predecessors cannot authorize correction. Recorded tests cover successful schema/excerpt correction, twice-invalid `schema_exhausted`, budget rejection, crash recovery, and replay without another request. Fresh V2 acceptance authority must bind `extract-correction-policy-v1`; historical V1 facts remain readable and grant no new authority.

Correction is application-scheduled, not an SDK retry: the fixed benchmark coordinator owns the bounded invocation loop, whereas `extract-repo` calls the runner once and requires a subsequent same-input/state invocation for a scheduled correction. This milestone does not change workflows, execute candidate code, call a live provider, or prove real Skill usefulness. The next product milestone remains one useful Skill and a controlled task-alone/README/Skill comparison, before wider campaign and publication acceptance.

## Implemented preview scope

### September 10 local candidate export

`export-candidates` now exposes the existing verified Phase 2-to-Phase 3 bridge
for local use. It writes up to three canonical descriptors into a fresh private
directory, retaining source provenance in its inventory. It needs no model key,
performs no network access, does not change source state, and grants no publication
authority. Invalid state and unsafe destinations fail closed. The
[single-Skill pilot](docs/project/2026-09-10-single-skill-pilot.md) has now reached
its extraction ceiling with zero admissible workflows; real generation and the
three-condition usefulness comparison have not run.

### September 10 local current-Flash compatibility

Local `extract-repo` and `build-candidate` now accept the explicit
`--deepseek-current-flash` option. It requests `deepseek-flash` for extraction and
generation, retains the independent Pro reviewer, and preserves strict response
model identity, local schema validation, zero SDK retries, and unknown-outcome
quarantine. Default and hosted model profiles are unchanged.

Read-only credential recovery passed. The subsequent current-Flash invocation
stopped in the GitHub scout stage with no semantic request: a diagnostic confirmed
the anonymous GitHub rate limit was exhausted. This is not a successful extraction
or generated Skill, and does not change Phase 6 release status. A separate offline
check confirmed that the intended nested RAG README is outside the current reader
path allowlist. That run and its state remain preserved. The separately approved
selected-input experiment below does not relabel it as a successful extraction.

### September 10 selected-README local trial

`extract-repo --readme-path` now accepts one explicitly selected repository-relative
README at an exact commit SHA. A versioned local subject binds the path through
all stage outputs and retry identities without changing ordinary subject bytes or
hosted reading policy. Existing content/license limits remain enforced. Local
export/build can consume the verified chain; publication and hosted candidate
sources reject it by default.

The controlled trial read the intended 2,821-byte RAG README, verified MIT at the
pinned SHA, and completed one real `deepseek-flash` request (4,308 total tokens).
The proposed workflow was dropped for `forbidden_text`; the extractor recorded
`schema_failure`, with no surviving workflows. Export failed closed. No correction,
generation, review, comparison, or publication followed. The CLI's run-level
`completed` status is not candidate success. Exact offending text is unavailable
because rejected model content was not retained; the diagnostic does not establish
which forbidden pattern matched. See the [pilot record](docs/project/2026-09-10-single-skill-pilot.md).

Offline verification: 2,725 passed, 3 skipped, Ruff and the three Phase 6 inspectors
passed. This milestone proves a bounded input path and records a real failure;
it does not complete the useful-Skill milestone or Phase 6 acceptance.

### September 10 local extraction-output alignment

The selected-README CLI now binds `local-readme-v2` and a separately versioned
safe-output prompt. HTTP links, unsafe shell forms, and credential-like values
remain forbidden; exact evidence must never be rewritten to pass validation.
Rejected workflows expose only bounded rule/field diagnostics (32 findings max),
not rejected titles or matching text. V2 also suppresses unvalidated model summary,
refusal, and incomplete prose. The underlying validator and legacy/hosted prompt
are unchanged.

V2 uses one attempt per stage, without correction or transport retry, while
preserving unknown-outcome no-replay handling. The distinct subject/retry identity
prevents reuse of historical v1 success or failure; v1 evidence remains readable
and usable by the existing local bridge. The repair checkpoint was offline;
the subsequently approved real trial is recorded separately below.
Final disjoint regression runs: 2,748 passed, 3 skipped. Full Ruff, the three
Phase 6 inspectors, and whitespace checks passed; independent review found no
remaining issue. Skips are not live acceptance evidence.

### September 10 local v2 live outcome — stopped

The separately approved v2 trial used software `e490f5a8238f17c1de3cffd5723cfaa9a2435427`
and the same exact source README. It made one real `deepseek-flash` request
(2,338 input + 2,300 output = 4,638 tokens). Both proposed workflows were dropped:
one for non-verbatim evidence, one for URLs in three evidence-excerpt fields.
The terminal remains `schema_failure`, zero workflows; offline export failed
closed. Rejected raw text was not retained, so diagnostics establish the rule
and field failures, not the exact offending text.

The original possible request plus the two confirmed selected-README requests
exhaust the three-extraction ceiling. No correction, generation, review,
comparison, or publication followed; historical failed facts were verified
unchanged. The prompt repair did not establish a useful Skill. Further work
starts with offline evidence-boundary investigation, not automatic retries or
weakened validation. PR #40 remains a development Draft, not a generated Skill
or release-acceptance result.

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

Persisting this historical lock is not a live-authority grant or an adversarial acceptance result. The controlled sequence is `rebind-benchmark-lock → record-live-authority → run-benchmark → run-replay`: a fresh target acceptance run can reuse unchanged entries while binding final source/workflow bytes. Rebind receives no model or catalog credential and produces only a sanitized state receipt. Each state-only approval and the subsequent authority carrier is single-use; changed bindings invalidate the old approval. Later live execution has occurred as noted above, but successful benchmark acceptance, exact replay, fresh applicable Gate B4 evidence, and Draft PR acceptance remain open.

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
- V2 benchmark locks and live authority have been persisted, and a real benchmark has been attempted. A successful five-repository benchmark, replay, and Draft PR acceptance remain pending.
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
