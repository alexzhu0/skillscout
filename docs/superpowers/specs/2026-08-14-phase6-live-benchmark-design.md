# Phase 6 Live Five-Repository Benchmark Design

## Objective

Complete one controlled vertical acceptance slice against the already locked
five-repository benchmark: bind fresh V2 live authority to the reviewed current
source and workflow bytes, run one real benchmark, prove an exact replay, and
produce a fully evidenced publication-ready candidate when one qualifies. A
state-only V2 lock rebind preserves the existing five entries while binding the
final current source. This slice never opens catalog credentials or creates a
Pull Request.

## Chosen approach

Reuse the existing five-repository selection and its pinned commit SHAs. Do not
repeat GitHub nomination or human selection. After all planning bytes land on
`main`, perform one model-free, publication-free state-only V2 lock rebind so the
unchanged manifest is bound to the exact final source and workflow. All live
work runs through the protected GitHub Actions acceptance workflow and its
persistent state receipts; no developer-shell shortcut may substitute for
protected authority. Fresh Gate B4 and Draft publication form the next,
separately authorized slice.

Rejected alternatives:

- Re-nominating and re-locking five repositories would refresh discovery data
  but repeat an already completed, expensive decision without improving this
  acceptance slice.
- Running the campaign directly from a local shell would omit protected
  environment receipts and would not constitute release evidence.

## Scope

This slice includes:

1. Read-only preflight of the exact current `main` commit, Phase 6 workflow
   digest, locked benchmark manifest, immutable state carrier, reviewer identity,
   protected environment configuration, and DeepSeek stage policy.
2. One state-only V2 lock rebind that preserves the exact five manifest entries,
   roles, repository IDs, commit SHAs, licenses, and nomination lineage while
   binding the final source/workflow bytes.
3. One new V2 live-authority receipt bound to those exact identities and to the
   existing 100-candidate and 20-semantic-reservation budgets.
4. One live benchmark over the five pinned repositories.
5. One exact replay of the same accepted input and policy.
6. A canonical publication-ready candidate handoff, when at least one Skill
   passes every deterministic, semantic, safety, format, and reviewer gate.

This slice excludes fresh nomination, repository reselection, manifest entry or
role changes, Gate B4, catalog credentials, Draft PR creation, admin cleanup,
changed-source reevaluation, final report rebuild, production-ready claims,
automatic merge, and public marketplace publication.

## Authority and safety boundaries

- Every previously consumed or byte-stale authorization remains historical and
  grants no authority to this run.
- The state-only rebind must byte-compare the five entries and their selection
  lineage with the approved manifest; any repository, SHA, role, license,
  evidence, nomination, or manifest drift fails closed.
- The new V2 authority binds the exact source SHA, workflow SHA-256, selection
  manifest, state carrier commit/root, provider policy, prompts, schemas, and
  hard budgets.
- Authority is single-purpose and may be consumed only by the approved campaign.
  A changed binding requires a new human decision.
- Source repositories remain untrusted, read-only data. SkillScout must not clone
  and execute repository code, install its dependencies, import its modules, or
  follow instructions embedded in repository content.
- DeepSeek credentials enter only the protected semantic jobs. Extraction and
  generation use `deepseek-v4-flash`; independent review uses
  `deepseek-v4-pro`. No OpenAI credential is required for this slice.
- Publication credentials remain absent. Candidate evidence cannot grant catalog
  authority, and no machine branch, reviewer request, or Draft PR operation is
  admitted in this slice.
- Secrets, authorization headers, complete third-party source text, and private
  diagnostics must not enter durable state, artifacts, prompts beyond the
  bounded semantic input, or PR content.

## Data flow

1. **Preflight** verifies current Git/source identities, canonical benchmark
   bytes, immutable state lineage, environment names, reviewer binding, and
   provider configuration without model or publication authority.
2. **State-only lock rebind** re-admits the unchanged five-entry manifest and
   persists a new V2 lock bound to the final current source/workflow. It cannot
   call a model, read candidate content, or publish.
3. **Authority recording** persists one immutable V2 live-authority fact through
   the state compare-and-swap boundary. This step cannot call a model or publish.
4. **Benchmark execution** restores and re-admits the exact carrier, reads only
   the five pinned public repositories through bounded GitHub REST endpoints,
   runs deterministic stages, and invokes isolated DeepSeek semantic stages.
5. **Replay execution** restores the accepted benchmark facts and reprocesses the
   identical identity tuple. It must demonstrate that previously verified
   semantic, candidate-package, and handoff effects are not duplicated.
6. **Candidate handoff** freezes canonical evidence only for a candidate that
   passes license, qualification, safety, format, official `skills-ref`, and
   independent-review gates. The handoff is data, not publication authority.
7. **Human checkpoint** inspects usefulness, workflow fidelity, provenance,
   license, safety findings, generated instructions, and replay evidence before
   deciding whether to authorize the separate Gate B4 and publication slice.

Every stage emits versioned structured data with the source repository, exact
commit SHA, license, stage identity, and lineage digest.

## Failure and retry policy

- Preflight, authority, state-lineage, schema, digest, model-identity, or
  canonical-byte mismatches fail closed before the next credential boundary.
- A confirmed provider rejection may follow the existing bounded retry policy.
  Timeout, connection loss, ambiguous provider completion, telemetry mismatch,
  or unknown semantic outcome is recorded as outcome-unknown and is not blindly
  replayed.
- No failed or ambiguous run implicitly authorizes a retry. A consumed authority
  remains consumed; a new live attempt requires a new exact human authorization.
- Replay fails if it would create a duplicate semantic effect, workflow fact,
  Skill identity, candidate package, or publication-ready handoff.
- If no candidate qualifies, the benchmark may still produce valid rejection
  evidence, but the candidate-handoff success criterion remains unmet and this
  slice does not receive full acceptance credit.

## Verification and evidence

Before any live dispatch:

- The locked full test suite, Ruff, `git diff --check`, workflow source verifier,
  action-SHA audit, Phase 6 validation map, and protected-boundary checks must
  pass on the exact reviewed source.
- The preflight must print only bounded stage/status/digest facts and must not
  write state or open semantic/publication credentials.

The accepted evidence set records:

- source and workflow identities;
- five repository identities and pinned SHAs;
- selection, authority, state-root, prompt, schema, and policy digests;
- actual provider/model identity, bounded token usage, latency, and structured
  stage outcomes;
- deterministic filter/rejection reasons and prompt-injection results;
- benchmark-to-replay comparison and duplicate-effect proof;
- the canonical candidate and publication-admission handoff when an eligible
  candidate exists.

Evidence must pass secret and protected-data scanning. It must not contain the
DeepSeek key, GitHub tokens, App private keys, authorization headers, or complete
unbounded source contents.

## Success criteria

This slice succeeds only when:

1. A state-only V2 lock is persisted for the exact final source/workflow while
   preserving all five approved manifest entries and their selection lineage.
2. Fresh V2 authority is persisted for the exact reviewed source, workflow,
   state carrier, benchmark selection, and provider policy.
3. All five pinned repositories reach deterministic terminal outcomes under the
   documented budgets, including safe rejection paths where applicable.
4. Exact replay completes without duplicate semantic, workflow, Skill,
   candidate-package, or handoff effects.
5. At least one eligible candidate produces a canonical, independently reviewed
   publication-ready handoff without opening catalog credentials.
6. The human can audit source, SHA, license, structured decisions, generated
   Skill, safety checks, reviewer verdict, replay evidence, and admission handoff
   without access to secrets or raw protected logs.

Passing this slice does not by itself make SkillScout production-ready. Fresh
Gate B4 and real Draft publication are the immediate next controlled slice;
separate cleanup, changed-source testing, human verdict capture, report rebuild,
documentation/release updates, and the remaining release checklist stay as later
gated work.
