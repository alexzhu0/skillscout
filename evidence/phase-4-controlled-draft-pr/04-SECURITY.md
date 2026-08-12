---
phase: 04
slug: controlled-draft-pr
status: verified
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: 2026-07-27
verified: 2026-07-27
---

# Phase 04 — Controlled Draft PR Security

> ASVS L1 verification of every mitigation declared in the Phase 04 plan-time
> threat models. This is a mitigation-presence audit, not a new-vulnerability
> scan. Repeated threat IDs across plans are consolidated below; every declared
> abuse vector for each consolidated ID was checked.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Phase 3 durable evidence → publication admission | Candidate bytes remain untrusted until strict canonical reconstruction and cross-validation. | Candidate descriptor, Phase 2/3 state, terminal summary, package, manifest, validation, and review evidence |
| Candidate handoff → protected publish job | Only three canonical locators and seven candidate-bound digests may cross; catalog/reviewer authority and authority-dependent digests must not. | Non-secret locators and SHA-256 digests |
| Protected authority → token factory | Catalog/reviewer authority and candidate equality must be established before token minting. | Protected catalog identity, base branch, individual reviewers, policy version |
| Publication intent → GitHub REST | A catalog-bound adapter is the only remote-write serialization boundary. | Exact blobs/tree/commit, machine ref, Draft PR, individual reviewer request |
| GitHub observations ↔ local recovery state | Neither local checkpoints nor remote state alone establish ownership or success. | Catalog/ref/commit/tree/Draft/reviewer observations and hash-linked checkpoints |
| GitHub control plane → live security claim | App permissions, ruleset, protected environment, denial probes, and cleanup require independent human evidence. | Stable non-secret IDs, digests, denial classifications, cleanup attestation |
| External Action bytes → workflow authority | Static audit evidence cannot authorize execution; exact human-approved identities are required. | Repository/commit/tree/content hashes, runtime, permissions, dependency evidence |

## Threat Register

| Threat ID | Category | Component / declared abuse vectors | Severity | Disposition | Mitigation and implementation evidence | Status |
|-----------|----------|------------------------------------|----------|-------------|----------------------------------------|--------|
| T-04-01 | Elevation / Tampering | Admission and composition: token/network factory invoked before exact candidate admission | high | mitigate | Pure candidate admission validates the exact terminal artifact matrix before returning evidence (`src/skillscout/domain/publication.py:232`); protected comparison validates the ten-field handoff and derives authority locally (`src/skillscout/bootstrap.py:227`); token access exists only in the delayed remote factory (`src/skillscout/bootstrap.py:318`); protected workflow order is compare-env → token (`.github/workflows/publish-candidate.yml:121`). Zero-call/order tests are present at `tests/test_publication_domain.py:187` and `tests/test_publication_security.py:160`. | closed |
| T-04-02 | Spoofing / Confused deputy | Arbitrary repository, ref, path, response, or reviewer authority | high | mitigate | Catalog/ref/login grammars and code-derived target root/head are enforced in `src/skillscout/domain/publication.py:112` and `src/skillscout/domain/publication.py:208`; the client is constructor-bound and cross-checks repository/default branch in `src/skillscout/adapters/github_publish.py:98` and `src/skillscout/adapters/github_publish.py:160`; CLI publication flags are locator-only at `src/skillscout/cli.py:117`. Gate B4 independently records the exact catalog, default branch, installation, and reviewer in `04-10-SUMMARY.md`. | closed |
| T-04-03 | Tampering | Manifest substitution, unlisted bytes, or regression of the manifest/admission link | high | mitigate | Admission requires an exact artifact-key set, canonical bytes, matching cross-digests, zero validation errors, eligible review, and exact frozen files (`src/skillscout/domain/publication.py:247`); desired Git tree identities derive from admitted bytes (`src/skillscout/application/publication.py:218`), with stale owned paths emitted as null-SHA deletions (`src/skillscout/application/publication.py:358`). Mutation coverage is present at `tests/test_publication_domain.py:171`; the independent acceptance inspector checks the link at `tools/verify_phase4_acceptance.py:96` and `tools/verify_phase4_acceptance.py:210`. | closed |
| T-04-04 | Elevation | Arbitrary method/path; merge, approve, ready, GraphQL, ruleset/admin, auto-merge, or default-ref mutation; non-causal platform denial | high | mitigate | The production adapter exposes catalog-bound GET/POST/PATCH operations only, forces non-force machine-ref updates, and creates Draft PRs (`src/skillscout/adapters/github_publish.py:277`); positive AST/route allowlists reject forbidden surfaces (`tests/test_publication_security.py:61`). Gate B4 records causal default-ref, merge, and ruleset-mutation probes plus production approve/ready absence in `04-10-SUMMARY.md`. The independently verified residual that a stolen coarse token may support ready-for-review outside SkillScout is retained below. | closed |
| T-04-05 | Elevation | Token minted before admission, with broad repository scope/permissions, or with App/ruleset bypass | high | mitigate | The workflow is manual-only with top-level `contents: read`, a protected publish environment, protected pre-token revalidation, repository narrowing, and only Contents/Pull requests write on the installation token (`.github/workflows/publish-candidate.yml:3`, `.github/workflows/publish-candidate.yml:28`, `.github/workflows/publish-candidate.yml:91`, `.github/workflows/publish-candidate.yml:121`, `.github/workflows/publish-candidate.yml:145`). Gate B4 records catalog-only installation, no Administration permission, active ruleset, and no bypass actors in `04-10-SUMMARY.md`. | closed |
| T-04-06 | Elevation / Repudiation | Publishing identity performs cleanup, or cleanup is unaudited | high | mitigate | The test-only canary returns a bounded cleanup manifest and closes only its HTTP client (`tests/test_publication_live_canary.py:228`); its transport test proves no DELETE request (`tests/test_publication_live_canary.py:344`). Production adapter/CLI/workflow have no cleanup route. Gate B4 records distinct human/admin cleanup, closed-unmerged PRs, deleted canary branches, and unchanged default SHA in `04-10-SUMMARY.md`. | closed |
| T-04-07 | Tampering / Repudiation | Human or force-rewritten machine head is overwritten after a crash | high | mitigate | Reconciliation requires exact Draft/head/base/ref agreement, marker ownership, bounded machine trailers/ancestry, and durable reviewer evidence before update (`src/skillscout/application/publication.py:145`, `src/skillscout/application/publication.py:266`); the adapter accepts only the derived machine ref and serializes `force: false` (`src/skillscout/adapters/github_publish.py:310`). Stateful regression coverage rejects human/force-rewritten lineage before further writes at `tests/test_publication_recovery.py:461`. | closed |
| T-04-08 | Spoofing / DoS | Duplicate PR, marker spoof, or ambiguous remote object selects the wrong Draft | high | mitigate | All matching open pulls are fully paginated and more than one closes to manual intervention (`src/skillscout/application/publication.py:103`); an existing Draft must match ref/head/base, one canonical marker, catalog identity, publication identity, and machine lineage (`src/skillscout/application/publication.py:145`). Marker parsing/digest checks are in `src/skillscout/domain/publication.py:176` and `src/skillscout/domain/publication.py:299`; malformed/duplicate marker tests are at `tests/test_publication_domain.py:234`. | closed |
| T-04-09 | Injection / Disclosure | Candidate content becomes shell/config interpolation, logs, or secret output | high | mitigate | Workflow shell blocks contain fixed commands and consume candidate values only through quoted environment variables (`.github/workflows/publish-candidate.yml:45`, `.github/workflows/publish-candidate.yml:57`, `.github/workflows/publish-candidate.yml:155`); static tests reject `${{ }}` inside run blocks and forbidden publication syntax (`tests/test_publication_security.py:297`). CLI output is a fixed bounded projection (`src/skillscout/cli.py:534`). Secret/candidate canaries passed in the offline suite. | closed |
| T-04-10 | Disclosure | Token, private key, provider error/body, arbitrary exception, or secret-bearing evidence leaks | high | mitigate | Authority loading is token-blind (`src/skillscout/bootstrap.py:70`); provider responses are bounded and converted to closed failures without raw body/exception projection (`src/skillscout/adapters/github_publish.py:355`); the publication ledger admits only closed checkpoint fields (`src/skillscout/adapters/publication_state.py:24`); CLI catches arbitrary exceptions and emits closed diagnostics/projections (`src/skillscout/cli.py:534`, `src/skillscout/cli.py:567`). Gate B4 records a clean secret scan and no secret material in evidence (`04-10-SUMMARY.md`). | closed |
| T-04-11 | Repudiation | Local state claims success after an uncertain remote write | high | mitigate | Checkpoints are hash-linked, canonically validated, atomically snapshot-replaced, and poison on uncertain persistence (`src/skillscout/adapters/publication_state.py:30`, `src/skillscout/adapters/publication_state.py:90`, `src/skillscout/adapters/publication_state.py:120`). Terminal completion occurs only after a full remote re-read of catalog/base/ref/commit/tree/Draft/marker/reviewer evidence (`src/skillscout/application/publication.py:498`) and then appends `remote_verified` before `complete` (`src/skillscout/application/publication.py:612`). Stateful revalidation and local-state-loss tests are at `tests/test_publication_recovery.py:292` and `tests/test_publication_recovery.py:345`. | closed |
| T-04-12 | DoS / Repudiation | Reviewer notification storm, removed reviewer, malformed evidence, or team state is treated as durable receipt | high | mitigate | Existing/recovered Drafts require every configured individual in fully validated current-request or completed-review evidence (`src/skillscout/application/publication.py:309`); only the newly created Draft path issues the first request (`src/skillscout/application/publication.py:389`); non-empty provider teams fail closed (`src/skillscout/adapters/github_publish.py:238`). Later-revision and malformed/outsider/duplicate-review evidence regressions are at `tests/test_publication_recovery.py:398` and `tests/test_publication_recovery.py:430`. | closed |
| T-04-13 | Confused deputy / Repudiation | Team reviewer configuration bypasses individual-only evidence; task/requirement evidence is missing or self-claimed | high | mitigate | Protected config rejects any non-empty team setting before token/client construction (`src/skillscout/bootstrap.py:70`), and the application independently rejects teams (`src/skillscout/application/publication.py:57`). The exact task/requirement inverse map is checked by `tools/verify_phase4_validation_map.py`; the independent read-only acceptance inspector verifies implementation and both human gates rather than trusting success fields (`tools/verify_phase4_acceptance.py:378`). Both verifiers and their mutation suites passed. | closed |
| T-04-14 | Tampering | Unprivileged intent/admission digest is fabricated or trusted as protected authority proof | high | mitigate | The unprivileged handoff constant and workflow outputs contain exactly three locators plus seven candidate digests (`src/skillscout/bootstrap.py:144`, `.github/workflows/publish-candidate.yml:32`). Intent/admission digests are derived only after exact expected-handoff equality and protected authority loading (`src/skillscout/bootstrap.py:276`), remain protected-job-local (`.github/workflows/publish-candidate.yml:121`), and are explicitly absent from the admit job (`tests/test_publication_security.py:271`). | closed |
| T-04-SC | Tampering / Spoofing | Workflow Action substitution or stale/inferred approval | high | mitigate | The static audit binds exact repository IDs, commits, trees, content hashes, runtimes, permissions, empty nested actions/hooks, and no unresolved claims in `04-ACTION-AUDIT.md`; Gate A4 explicitly approves both exact commits and audit digest in `04-08-SUMMARY.md`; workflow pins those commits (`.github/workflows/publish-candidate.yml:50`, `.github/workflows/publish-candidate.yml:145`). Current SHA-256 values match the gate records: audit `d3d5f8a3480d55b7cf7278505f92e8f96ccd6622683f95401dd739f916aae622`, workflow `224c843ad1211bd3fa250e055e4040417d58bb5ecd837ed0fd8f148af6c0ca8c`. | closed |
| T-04-SC2 | Elevation | Action audit accidentally installs, imports, executes, or delegates to external code | high | mitigate | The audit verifier imports only Python standard-library modules and performs one bounded local read (`tools/verify_phase4_action_audit.py:1`, `tools/verify_phase4_action_audit.py:55`); it requires no executable hooks, resolved nested actions, and no unresolved claims (`tools/verify_phase4_action_audit.py:77`). Mutation tests reject substitutions, status promotion, unresolved nested actions, and unresolved claims (`tests/test_phase4_action_audit.py:29`). The action audit records that no checkout/install/import/build/action execution occurred. | closed |

*Status: open · closed · open — below high threshold (non-blocking).*

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-04-01 | T-04-04 | GitHub's coarse `pull_requests: write` installation token may technically support ready-for-review if stolen or used outside SkillScout. The production adapter, CLI, and workflow cannot express that transition; Gate B4 separately reviewed this residual and the closed production surface. Any production route for the operation reopens T-04-04. | Gate B4 human reviewer | 2026-07-27 |

No plan-time threat has disposition `accept` or `transfer`; R-04-01 records the explicitly reviewed residual of a mitigated threat.

## Threat Flags

No unregistered flags. `04-09-SUMMARY.md` explicitly reports that the GitHub
App token and test-only canary transport are planned trust-boundary surfaces
covered by the authored threat model; the other Phase 04 summaries contain no
`## Threat Flags` entries.

## Verification Evidence

- Config: `asvs_level: 1`; `block_on: high`; security enforcement enabled.
- Register: authored at plan time across `04-01-PLAN.md` through `04-11-PLAN.md`; 16 unique threat IDs, all severity `high`, all disposition `mitigate`.
- Current scoped implementation/workflow files had no uncommitted diff. The pre-existing dirty `.planning/STATE.md` was not modified. A concurrent audit edit appeared in `04-VALIDATION.md` during this run; it was left untouched and the validation-map verifier was rerun successfully against that current artifact.
- Locked explicitly offline focused audit: `197 passed, 2 skipped`.
- Independent local verifiers: `phase4 validation map valid`; `phase4 action audit valid`; `phase4 acceptance valid`.
- The two skips are the deliberately opt-in live-canary paths. This audit did not access credentials, network, or secret material and did not rerun Gate B4; it verified the recorded human-reviewed Gate B4 evidence and exact current workflow digest.
- Final code re-review `04-REVIEW.md` is clean after all 14 entries in `04-REVIEW-FIX.md` were fixed; the current workflow digest remains the Gate B4-approved digest.

## Security Audit Trail

| Audit Date | Threat IDs | Closed | Blocking Open | Non-blocking Open | Run By |
|------------|------------|--------|---------------|-------------------|--------|
| 2026-07-27 | 16 | 16 | 0 | 0 | gsd-security-auditor |

## Sign-Off

- [x] All declared threats have a disposition.
- [x] Every declared mitigation is present in implementation, workflow, tests, or required human-gate evidence.
- [x] Reviewed residual risk is documented.
- [x] Threat flags are incorporated.
- [x] `threats_open: 0` confirmed at `block_on: high`.
- [x] `status: verified` set in frontmatter.

**Approval:** verified 2026-07-27
