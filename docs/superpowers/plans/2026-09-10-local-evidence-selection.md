# Local Evidence Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove model-authored evidence copying from the local preview while preserving exact source binding and all existing safety checks.

**Architecture:** A pure bounded catalogue supplies inert, exact source snippets. A separate strict response selects identifiers; deterministic materialization creates the unchanged extractor/workflow contracts before the existing validator. Explicit v3 CLI activation isolates new semantics from historical v1/v2 and hosted publication.

**Tech Stack:** Existing locked Python 3.13, Pydantic, httpx/OpenAI SDK, SQLite, pytest and Ruff; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-10-local-evidence-selection-design.md` (confirmed by user).

## Global Constraints

- New identities: `local-readme-v3`, `evidence-catalog-v1`, `extract-local-evidence-select-v1`, `extractor-evidence-selection-v1`, `retry-local-readme-v3-once`.
- Maximum 128 snippets; exact contiguous original substrings of at most 280 characters; identifiers start at `e0001`; offsets are original character offsets, half-open.
- Exclude whole original lines matching existing forbidden-text rules before slicing. Exclude fenced code, including unclosed fences through EOF. Recheck every snippet. Never rewrite, normalize, splice, follow links or execute source text.
- Only selected safe catalogue entries reach the new semantic input; no duplicate full README. Full instructions + user payload + response schema <=65,536 UTF-8 bytes before dispatch.
- Unknown evidence ID or step evidence absent from top-level evidence rejects that workflow. No fuzzy recovery, evidence repair or inserted model claims.
- Existing WorkflowSpec, validators, default/hosted profiles, v1/v2 state and publication restrictions remain unchanged. V3 only enters explicitly local export/build.
- One request maximum per invocation/identity, SDK retries zero, no correction or unknown-response replay. The previous pilot is terminal at 3/3; zero live model calls in implementation.
- Never inspect secret files or runtime loaders; do not read `.env`, PEM or credentials. No network experiments, workflow dispatch, canonical state changes, publication or merge. Use synthetic credentials only in transport tests.
- Test command prefix: `.tools/uv-0.11.29/bin/uv run --locked --no-env-file`.
- Work only in `/Users/alexzhu/Lenovo/skillscout/.worktrees/codex/local-candidate-preview` on `codex/local-candidate-preview`. No unrelated refactor, no subagents spawned by implementers/reviewers.

---

### Task 1: Pure catalogue and evidence-selection contracts

**Files:**
- Create: `src/skillscout/domain/evidence_selection.py`
- Create: `tests/test_evidence_selection.py`

**Interfaces:**
- Consume existing `ExtractorWorkflow`, `ExtractorResponse`, `EvidenceRef`, `find_forbidden_text`, `StrictFrozenModel`, canonical SHA-256 utility, and their current bounds without modifying them.
- Produce `EvidenceCatalog`, immutable entries with `evidence_id,path,blob_sha,content_hash,start,end,excerpt`, `entries`, `digest`, `truncated`, `audit()` (policy/digest/count/truncated only), and `user_payload()` (canonical JSON of inert entries and necessary source metadata).
- Produce `build_evidence_catalog(*, scope: Mapping[str, object], path: str, blob_sha: str, content_hash: str, text: str) -> EvidenceCatalog`. Verify SHA-256 of UTF-8 text equals supplied content hash, source path matches scope, and valid blob/hash syntax; reject inconsistent trusted inputs without echoing values.
- Produce strict `SelectedEvidence(evidence_id,supports)`, `SelectedStep(instruction,evidence)`, `SelectedWorkflow` (same semantic fields/limits as ExtractorWorkflow, but selected evidence), `EvidenceSelectionResponse` (same summary/rejection/workflow limits as ExtractorResponse).
- Produce `materialize_workflow(workflow: SelectedWorkflow, catalog: EvidenceCatalog) -> ExtractorWorkflow`; raise `EvidenceSelectionError` with closed `.code` (`unknown_evidence_id` or `step_evidence_not_declared`) for reference failures. No strings from rejected output in error messages.
- Produce `EVIDENCE_CATALOG_POLICY_VERSION` and `EVIDENCE_SELECTION_SCHEMA_VERSION` with global constraint values.

- [ ] Write focused tests with independently derived expected excerpts and offsets. Required example:

```python
text = "Alpha\r\nhttps://blocked.invalid\r\n  第二段  \r\n"
catalog = build_evidence_catalog(
    scope={"readme_path": "README.md"}, path="README.md", blob_sha="a" * 40,
    content_hash="sha256:" + hashlib.sha256(text.encode()).hexdigest(), text=text,
)
assert catalog.entries[0].excerpt == "Alpha\r\n"
assert catalog.entries[0].start == 0
assert catalog.entries[0].end == 7
assert catalog.entries[1].excerpt == "  第二段  \r\n"
assert catalog.entries[1].evidence_id == "e0002"
```

Add tests for mixed backtick/tilde fences, unclosed/mismatched fences, long lines, full-line forbidden patterns crossing a 280-character boundary, blank chunks, Unicode, exactly 128 and >128 eligible pieces, digest changes on changed scope/source/position, strict extra-field rejection, exact materialization, unknown IDs and undeclared step IDs. Confirm safety of original whole line is checked before segmentation. Do not assert product helper output against itself.

- [ ] Run `pytest -q tests/test_evidence_selection.py` via the locked prefix; record expected RED from the missing feature before production implementation.
- [ ] Implement frozen domain values and pure functions. The catalogue algorithm is:

```text
for each original line, preserving line endings and absolute character offset:
    detect fence opener/valid matching closer conservatively
    skip fenced or blank lines
    skip whole line if existing forbidden-text rules match
    for consecutive <=280-character slices without rewriting:
        ignore whitespace-only slices; recheck forbidden rules
        append exact source-bound item with next eNNNN ID
        on the 129th eligible item mark truncated and stop
digest canonical scope + catalogue policy + ordered entries (+ truncation fact)
```

Only the valid matching fence character and sufficient closing length end a fence; a different fence marker inside it is not a closer. Materialization derives every mechanical field from the entry map, never from model fields. Semantic limits must match the legacy workflow and evidence support contracts.

- [ ] Run the focused file plus `tests/test_extraction_diagnostics.py`; run scoped Ruff; self-review source equality, boundedness and no raw error propagation.
- [ ] Commit only these domain/test files and write the implementation report with RED/GREEN outputs and exact public interfaces.

### Task 2: V3 adapter, pipeline, state admission, CLI and documentation

**Files:**
- Modify: `src/skillscout/adapters/openai_extract.py`
- Modify: `src/skillscout/application/processors.py`
- Modify: `src/skillscout/adapters/phase2_state.py`
- Modify: `src/skillscout/domain/local_preview.py`
- Modify: `src/skillscout/cli.py`
- Create: `tests/test_local_evidence_preview.py`
- Modify only if required for new coverage: `tests/test_local_readme_preview.py`, `tests/test_local_extraction_output.py`
- Update: `README.md`, `AGENTS.md`, `RELEASE.md`, `docs/CONFIGURATION.md`, `docs/TESTING.md`, `docs/GETTING-STARTED.md`, `docs/project/2026-09-10-single-skill-pilot.md`.

**Interfaces:**
- Consume all Task 1 public interfaces exactly as reported.
- Add explicit `extract-repo --evidence-selection`, requiring `--readme-path`; without it preserve existing v2 CLI behavior. This avoids silently changing old launch commands. V3 subject/retry/prompt identities must differ from v1/v2.
- Add `OpenAIExtractionClient.extract(..., evidence_selection: bool = False)` as a mutually exclusive mode with `local_preview=True` or any correction. Reject non-booleans before request. Use `EvidenceSelectionResponse` only for this mode, keeping legacy response schemas unchanged.
- Result parsing may carry a strictly typed selection response until the processor resolves it; do not weaken existing response validation or coerce arbitrary mappings into a valid workflow. Keep telemetry identical to existing handling.

- [ ] Write recorded-transport production-composition tests first. Reuse the existing selected-reader Github fixtures and synthetic semantic response helper; transform evidence refs into IDs in the synthetic response, then assert actual output source values:

```python
argv = _argv(tmp_path) + ["--deepseek-current-flash", "--evidence-selection"]
assert cli.main(argv) == 0
output = _results(tmp_path)["extractor"]
assert output["local_readme_scope"]["scope_version"] == "local-readme-v3"
assert output["prompt_version"] == "extract-local-evidence-select-v1"
assert output["outcome"] == "extracted"
assert output["workflows"][0]["evidence"][0]["path"] == SELECTED
assert semantic.call_count(*CHAT_COMPLETIONS) == 1
```

Use a hand-checked source line/ID; never compute the expected materialized excerpt with the new catalogue helper. Cover empty catalogue, byte budget boundary, forbidden authored output, unknown/extra model fields, undeclared step references, model refusal/incomplete/unknown/429, lost response and second invocation, stage scope/identity tampering, unchanged old state, export/build and publication denial. Verify ignored source text and fake instructions never enter trusted messages. In the empty/preflight branches assert zero semantic transport requests and a distinct fixed diagnostic, not a model no-workflow result.

- [ ] Run the new file for RED and record specific missing CLI/mode behavior.
- [ ] Wire v3 explicitly through the existing flow:

```text
CLI selection flag + selected README -> v3 subject + one-attempt retry policy
existing scout/filter/reader -> immutable verified file text
build catalogue; empty -> skipped/no_eligible_evidence (zero model calls)
adapter measures trusted prompt + catalogue JSON + actual response JSON schema
over 65,536 bytes -> fixed preflight failure, zero model calls
one strict selection request -> per-workflow resolve -> unchanged boundary validator
surviving WorkflowSpec objects -> existing local export/build
```

The empty catalogue is a local skip with `skip_reason` and `diagnostics` containing `no_eligible_evidence`, not `no_workflow`. Byte-cap preflight uses a closed local code/diagnostic and retains no raw inputs. Preserve the existing one-shot runner/reconciliation mechanism; do not modify pipeline/state core tables or disable unknown-outcome handling. V3 inherits v2 summary/refusal suppression and bounded diagnostic shapes. Persist audit metadata only, not the whole catalogue or rejected selected workflow text.

- [ ] Extend candidate-chain admission to recognize v3 only for explicit local consumers. Require the exact v3 prompt/response/catalogue/retry policy markers and one attempt; check fixed audit types/bounds and source scope across stages. A digest alone grants no authority. Required local preflight skip shapes must not be mistaken for valid candidate evidence. Retain all existing path/hash/budget/fixed-SHA checks. Default hosted/publication must reject v3.
- [ ] Verify actual local build from the exported descriptor with recorded generator/reviewer transports and the real format/safety validators. Do not hand-edit WorkflowSpec or descriptor fields to obtain acceptance.
- [ ] Run locked focused tests including all local preview files, provider, extraction and candidate-source/build tests. Fix regressions without changing legacy v1/v2/default meaning. Run Ruff, three existing Phase 6 inspection scripts and a final complete offline suite in disjoint partitions (slow Phase 6 recovery tests separately if needed).
- [ ] Update docs with exact new command, local-only constraints, offline result and the still-exhausted real pilot budget. Mark this as an offline mechanical repair, not a real successful extraction or useful Skill. Do not reset historical facts.
- [ ] Commit scoped code, tests and docs; report RED/GREEN, complete final evidence, remaining issues and no live calls. Controller performs independent review, then updates the existing Draft PR only after verification; no merge.
