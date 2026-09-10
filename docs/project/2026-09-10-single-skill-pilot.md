# Single-Skill pilot — September 10, 2026

Status: local export implemented; real extraction, generation, and comparison
have not run. This is development validation, not Phase 6 release evidence.

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
deployed RAG service works. The bounded repository reader may not select this
nested example. If extraction produces no suitable workflow, record that outcome;
do not relabel an unrelated workflow or weaken retrieval/evidence validation.

## Execution boundary

1. Inject credentials only through the approved runtime mechanism. Never source
   or inspect repository `.env` files, copy tokens, or expose values in arguments.
   The current local session has no injected DeepSeek credential, so live work is
   blocked until that runtime prerequisite is supplied.
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

## Starting the first live extraction safely on macOS

Run the following in your own **zsh terminal**, from the checkout containing this
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
  .tools/uv-0.11.29/bin/uv run --locked skillscout extract-repo \
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
