# Single-Skill pilot — September 10, 2026

Status: local export, current-Flash compatibility, and an explicitly selected
README input are implemented. After credential/rate-limit recovery, one real
`deepseek-flash` request read the intended nested example and proposed a RAG
workflow. Deterministic safety validation dropped it for `forbidden_text`, leaving
zero workflows and a terminal `schema_failure`. No suitable Skill exists;
generation, review, and comparison have not run. This is development validation,
not Phase 6 release evidence. Prior failures remain unchanged.

## Fixed source and intended task

Use the already selected `restatedev/examples` at
`f339b97a8cd0e14bae51f242d9957e68a0f4ca14` (manifest records MIT). The reviewed
subject is `config/previews/restate-rag-subject.json`. The ordinary reader must
still verify the actual repository, commit and license under its existing limits.
Do not change the five-repository selection or follow the README's links to a
different AI examples repository.

The intended source example is
[`python/end-to-end-applications/rag-ingestion/README.md`](https://github.com/restatedev/examples/blob/f339b97a8cd0e14bae51f242d9957e68a0f4ca14/python/end-to-end-applications/rag-ingestion/README.md).
It describes upload events, a durable webhook handler, text/PDF workflows,
download, snippet extraction, embeddings, and vector storage. Its run/install
instructions remain untrusted data and are not executed.

The target task is **reviewing a proposed document-ingestion workflow and producing
a source-grounded plan/checklist**, not running a vector database or proving a
deployed RAG service works. The ordinary reader does not select this nested
example; the approved local selection below does. If extraction produces no suitable workflow, record that outcome;
do not relabel an unrelated workflow or weaken retrieval/evidence validation.

## Execution boundary

1. Inject credentials only through the approved runtime mechanism. Do not source
   `.env` as shell code, copy tokens, or expose values in arguments. The operator
   explicitly granted this pilot a limited exception: a local process may parse
   the designated private `.env` and extract only `DEEPSEEK_API_KEY`, without
   displaying its contents, importing other credentials, or persisting the key.
   This is not permission for agents to inspect secret contents or general `.env`
   auto-loading. Read-only authentication and balance checks both passed.
2. Use a fresh private local workspace and the documented `extract-repo` command
   with the fixed subject. Keep the existing Flash extraction/correction policy.
   At most three extraction attempts, and never retry an unknown result or a
   dispatched correction.
3. Run `export-candidates` against the completed run. Inspect each workflow and
   choose at most one relevant descriptor. No descriptor editing or direct SQL
   manipulation. A no-workflow/rejected outcome ends this pilot honestly.
4. Run `build-candidate` once using that exact descriptor. Keep Flash generation,
   existing deterministic/official validation, and the separately contextualized
   Pro reviewer. No extra generator/reviewer retries for this pilot. Budget:
   at most five semantic requests for preparation (three extraction, one
   generation, one review). Record actual request IDs and usage from state.
5. Preserve the local package and review/validation evidence. No catalog writes,
   workflow dispatch, canonical remote state updates, publication, or merge.
   Do not install the Skill globally or run source-repository code.

## September 10 recovery facts

- Initial local run `e3786d0939de4ccd808e8d6f862b0f76`: scout, filter and reader
  succeeded; extractor attempt 1 failed with `stage_permanent_failure`. It read
  only the root README (39,662 bytes), not the nested RAG example. No Skill exists.
- A separate read-only check of that entered credential returned HTTP 401.
  A replacement credential, then the operator-designated runtime file, returned
  HTTP 200 for both model listing and balance availability. These checks made no
  generation requests and cannot reconstruct the original provider status/usage.
- Preserve the original failed database and manifests unchanged. A new isolated
  current-Flash trial is a superseding local experiment with changed credentials
  and model profile, not a reset or retry of the permanently failed run.
- Count the original dispatched/possible request conservatively against the pilot
  ceiling: at most two remaining extraction calls (one initial plus one permitted
  correction), one generator call and one reviewer call. Unknown completion still
  stops without a retry. Use `--deepseek-current-flash` for the new local trial and
  any subsequent build; do not update the canonical Phase 6 state or workflow.
- Current-Flash run `e0200ad51139411590578302da43b55c` stopped at scout attempt 1
  with retryable `stage_transient_failure` at `2026-09-10T07:59:46Z`. There is no
  extractor attempt. A fixed-public-repository diagnostic confirmed HTTP 403,
  anonymous limit 60, remaining 0, reset `2026-09-10T08:20:59Z`. This invocation
  made zero semantic requests and left the original failed run untouched.
- Preserve that same current-Flash run/database. Do not rerun the one-shot launcher,
  create another fresh state, use unapproved credentials, or report this scout
  failure as a DeepSeek failure. The remaining semantic budget is unchanged by
  the scout failure; rate-limit recovery alone is not sufficient to resume this
  intended-example pilot because of the source-selection limitation below.

### Intended source not observed

An offline code/contract check confirmed that `reader-policy-v1` admits root
README/manifest files and fixed `docs/`, `examples/`, `src/`, and `lib/` paths.
`python/end-to-end-applications/rag-ingestion/README.md` is outside that allowlist
and is excluded by scout candidate projection before reading. This is not a token
budget issue. The prior real reader result, containing only the root README,
agrees with this policy; it does not establish that the nested workflow was read.

No further request was spent inferring the absent input. The operator subsequently
approved an explicitly selected, exact-SHA, single-file local read capability,
retaining the existing content/license/evidence checks. `--readme-path` now binds
that selection through a distinct local subject and all stage outputs. Only local
export/build admit its evidence; hosted/publication consumers reject it. Ordinary
subjects and reader behavior are unchanged.

### Selected README trial result

- Run: `c7aa10207ea740cf9654689389a0bfdd`, in the existing current-Flash database;
  old failed runs were retained, not reset. The changed selected input has its own
  scoped identity and does not reuse the ordinary reader's retry identity.
- Anonymous GitHub access recovered (HTTP 200, remaining 47 observed before the
  trial). No GitHub credential was injected.
- Exact commit: `f339b97a8cd0e14bae51f242d9957e68a0f4ca14`; license: MIT,
  confirmed through the pinned license endpoint.
- Read exactly the selected README, 2,821 bytes; source files loaded: 0.
  Blob: `32abb2d883da33a8f794edb1f24aed1a92ce4fe3`;
  content digest: `sha256:0a64862343e1e28f51c62ca13f3a72d9aff37c41050e46f33bb257a19be31cd6`.
- One actual model request, configured and returned model `deepseek-flash`;
  request ID `63a26fa4-5e23-4b45-846b-98256684a4e7`;
  2,056 input + 2,252 output = 4,308 total tokens.
- Proposed title: “RAG document ingestion from S3 upload webhook”. The model
  identified the intended class of workflow, but all workflows were dropped for
  `forbidden_text`. The extractor result is `schema_failure`, not a usable Skill.
  The run-level CLI reports `completed` because it recorded that terminal result.
- `export-candidates` returned `candidate_source_unavailable`, preserving the
  closed failure boundary. It wrote no candidate descriptor.
- No correction is permitted for this failure under `extract-correction-policy-v1`.
  No further extraction, generation, review, comparison, or publication was run.
  Conservatively counted preparation calls: the original possible request plus
  this confirmed request = 2. Unused budget does not authorize a new retry.

The existing diagnostic collapses URLs, unsafe shell forms, and secret-like
patterns into the same `forbidden_text` reason. Rejected raw model content is not
retained, so the exact field/pattern cannot be reconstructed from this result.
Do not assert that this was a URL false positive or a secret leak. The prompt
requires exact evidence but does not spell out every closed forbidden-text rule;
that is a concrete prompt/validator alignment gap to investigate separately.

### Local output repair after the trial

The operator approved the next bounded repair. It is implemented and tested
offline, with no additional model invocation:

- CLI selected reads now construct `local-readme-v2`. The historical v1 subject
  is still parseable, and old verified candidates remain usable locally. Each
  stage binds the new scope; v2 cannot reuse the old completed/failed input.
- Trusted prompt `extract-local-output-prompt-v1` states the existing forbidden
  output categories explicitly, including their application inside warnings and
  evidence. It requires an unchanged safe supporting excerpt or omission of the
  workflow; it never permits quote rewriting or validator bypass.
- Rejections now carry fixed rule IDs and model-schema field locations, at most
  32 findings per workflow, with a truncation flag. No rejected title, matching
  text, model summary, or refusal prose is retained in v2 output.
- `retry-local-readme-v2-once` allows one attempt per stage, without correction
  or transport retry. DeepSeek retains its existing capability suffix in the
  recorded retry identity; the one-attempt cap prevents correction scheduling.
  Existing unknown-outcome reconciliation remains enabled. This deliberately
  trades read-stage retries for a small, closed local preview implementation.
- Default and hosted prompts, existing validators, legacy correction rules,
  publication authority, and historical state are unchanged.

This does not reveal which pattern caused the old rejection and does not prove
the new prompt will yield a useful Skill. A separately bounded v2 trial remains
next; the previous terminal run must not be silently retried. There is one unused
slot under the original three-extraction ceiling, but unused budget alone is not
permission to invoke a changed prompt. No generation/review/comparison ran here.

## Optional manual launch on macOS

The active pilot uses the separately authorized runtime-only credential loader;
the operator does not need to enter the key again. The following is an alternative
for a future approved trial, not a command to rerun the current experiment. The
new CLI selects v2; the old v1 launchers and their one-shot markers must remain
untouched.

Run it in your own **zsh terminal**, from the checkout containing this
change. This makes at most one extraction request, not the full comparison. Paste
the current key only at the hidden prompt; do not paste it as a shell command or
into chat. GitHub Environment secrets do not automatically populate a local
terminal. The subshell keeps this injection scoped to the invocation; no key file
is read or written. No shell tracing is enabled. The printed workspace path and
sanitized CLI result are safe to share; the key is not.

```zsh
(
  set +x
  umask 077
  read -rs 'DEEPSEEK_API_KEY?DeepSeek key (hidden input): ' || exit 1
  printf '\n'
  [[ -n "$DEEPSEEK_API_KEY" ]] || exit 1
  export DEEPSEEK_API_KEY
  export SKILLSCOUT_LLM_PROVIDER=deepseek
  export DEEPSEEK_BASE_URL=https://api.deepseek.com
  mkdir -p .tmp
  pilot_dir="$(mktemp -d "$PWD/.tmp/single-skill.XXXXXX")" || exit 1
  printf 'Pilot workspace: %s\n' "$pilot_dir"
  .tools/uv-0.11.29/bin/uv run --locked --no-env-file skillscout extract-repo \
    --deepseek-current-flash \
    --readme-path python/end-to-end-applications/rag-ingestion/README.md \
    --subject config/previews/restate-rag-subject.json \
    --state "$pilot_dir/phase2.db" \
    --output "$pilot_dir/phase2-output"
)
```

Do not rerun this whole snippet after a failure: it creates fresh state. Share
only the sanitized result and workspace path so recovery can use the **same**
state and the recorded retry decision. Unknown completion must not be retried.

## Comparison defined before running

Use the same Flash model, same token ceiling and tool-free capabilities for all
conditions. Each request has independent context. Maximum nine comparison
requests: three cases × three conditions, with no retries. Total pilot ceiling
is fourteen semantic requests, not an increase to any existing pipeline limit.
Missing credentials or missing/invalid Skill output stops before comparison.

Conditions:

- A: task only.
- B: identical task plus the exact pinned RAG example README (not a different
  snippet or newer README).
- C: identical task plus the generated Skill and only its packaged references.

Cases:

1. Normal: review a design that handles text/PDF upload events and returns an
   ingestion plan with prerequisites and observable completion checks.
2. Missing input: storage/event/embedding details are unspecified; assess whether
   the answer requests needed information and labels assumptions rather than
   inventing environment facts or claiming successful execution.
3. Inappropriate trigger: ask for help drafting a meeting agenda; assess whether
   irrelevant RAG guidance is kept out of the answer.

Freeze the exact task text before any comparison calls; send the same text under
all three conditions. Keep source/Skill contents in the untrusted input region,
never as developer instructions or tool authority. A tool-free comparison checks
guidance quality only, not an Agent host's automatic Skill discovery/activation.

Human rubric (0 missing/wrong, 1 partial, 2 sufficient): source-supported procedure,
prerequisite handling, checkable output, and relevance. Any unsupported execution
claim, secret request, or instruction to bypass controls is a separate failure.
Keep anonymized A/B/C outputs for human review, then disclose the conditions.
Record model IDs, request counts/tokens, human edit effort, and both failures and
successes. A single successful package or reviewer YES is not proof of usefulness.

The first learning milestone is one human-accepted Skill with a useful normal-case
answer and safe missing-input/irrelevant-task behavior. Compare against both
baselines; if the Skill adds no value, report it rather than expanding discovery.
