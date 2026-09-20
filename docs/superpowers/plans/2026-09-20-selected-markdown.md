# Selected Markdown local preview implementation

> **For agentic workers:** Use superpowers:subagent-driven-development; one bounded implementation task, followed by independent review. The user approved this input-contract extension and autonomous ordinary work on September 20. Do not ask for routine step approvals.

**Goal:** Let the existing local extraction/export/build flow read one explicitly selected ordinary Markdown document without changing its execution or publication authority.

**Architecture:** Reuse the existing versioned local subject and selected-file reader. Add a distinct `local-markdown-v1` scope, reader/retry identities, and `--markdown-path`; preserve all historical README identities and payloads. Keep the existing v4 source-only extraction prompt byte-identical.

**Tech Stack:** Existing Python/Pydantic/SQLite/CLI and recorded pytest transports. No new dependency.

**Spec:** User-approved in-chat bounded design: one `.md` file at an exact SHA, existing safety/limits, no links/code execution, local export/build only. Prior useful-Skill experiment requirements remain binding.

## Global Constraints

- No remote writes, push, PR, merge, publication or source-code execution.
- Never read secrets or `.env` contents; live calls remain controller-only through the separately authorized runtime loader.
- Preserve old state and defaults. Do not alter WorkflowSpec, qualification/security rules, provider/model settings or prompt text.
- One selected regular UTF-8 `.md` blob, case-insensitive extension; exact 40-lowercase-hex SHA. Existing path/size/content/catalogue and semantic request caps remain unchanged.
- Full local model attempt limit remains one; no correction, transport retry, unknown-outcome replay or authority inferred from a prior campaign.
- This is not hosted/default promotion. Publication must reject new local scope, even if scope markers are removed but the new reader policy remains.

## Review Focus

1. Spaces and uppercase `.MD` paths must work without normalization changing the selected object.
2. Unsafe paths, non-Markdown, multiple path flags and missing selection flags fail before clients/state are constructed.
3. New scope on an old reader/retry identity, changed selected path, or extra files cannot re-enter export/build.
4. Non-regular tree entries, invalid UTF-8 and oversize blobs cannot cause a model request or fallback read.
5. Historical README v1–v4 and unscoped subjects keep their identities; new Markdown remains local-only.

### Task 1: Extend the existing selected-file route

**Files:** `src/skillscout/domain/local_preview.py`, `src/skillscout/application/processors.py`, `src/skillscout/adapters/phase2_state.py`, `src/skillscout/cli.py`; create `tests/test_local_markdown_preview.py`. Controller owns documentation updates. Avoid unrelated formatting/refactors.

**Interfaces and decisions:**
- Add scope literal `local-markdown-v1` to `LocalReadmeSubject`. Retain the legacy `readme_path` field and `local_readme_scope` envelope for compatibility; document these internal names instead of introducing parallel subject hierarchies.
- New constants: `LOCAL_MARKDOWN_POLICY_VERSION = "reader-selected-markdown-v1"`, `LOCAL_MARKDOWN_RETRY_VERSION = "retry-local-markdown-v1-once"`.
- New scope permits a safe repository-relative path ending `.md` case-insensitively; all old scopes still require basename `README.md` case-insensitively.
- CLI `--markdown-path PATH` mutually exclusive with `--readme-path`; require both `--evidence-selection` and `--source-only-fields` explicitly. Preserve old option combinations. Validate combinations and subject before state/client construction.
- New scope uses existing `LOCAL_SOURCE_ONLY_PROMPT_VERSION`, source-only suffix, evidence catalogue/materializer, redaction, one-shot retry settings. No prompt adaptation for document type.
- Reader selects exactly the chosen path as today; use `docs` tier and new reader policy for new scope, `readme` tier and old reader policy for README scopes. No other document is fetched on missing/invalid selection.
- Exact scope/prompt/retry/reader policy/tier binding in local-chain validation; local evidence is detected through either scope envelope or either selected-file policy, before ordinary-chain admission. Only `allow_local_readme=True` consumers admit both scoped modes.

- [x] Write failing behavioral tests first. Begin with the existing recorded selected-README fixture moved to `notes/Workflow.MD`; assert one exact blob fetched, new scope/policy/retry, unchanged v4 prompt, and successful local descriptor export/re-admission.
  ```python
  assert cli.main(base_args + ["--markdown-path", "notes/Workflow.MD",
      "--evidence-selection", "--source-only-fields", "--deepseek-current-flash"]) == 0
  # Inspect actual persisted manifests, actual transport requests and exported bytes.
  ```
- [x] Run the new tests before implementation and retain the expected missing-option/scope failures.
- [x] Implement the minimal changes above, reusing current source selection and verifier code.
- [x] Add negative cases for the five Review Focus items, plus empty catalogue and consumed/unknown outcome replay. Assert no model/network request for deterministic preflight failures; mock only external transports.
- [x] Run new tests plus README/evidence/source-only/export tests and Ruff. The controller runs the final full frozen-code suite once after review, avoiding code edits while it is running.
  ```bash
  UV_CACHE_DIR=.tmp/uv-cache .tools/uv-0.11.29/bin/uv run --locked --offline --no-env-file pytest -q tests/test_local_markdown_preview.py tests/test_local_source_only_preview.py tests/test_local_evidence_preview.py tests/test_local_readme_preview.py tests/test_cli_export_candidates.py
  UV_CACHE_DIR=.tmp/uv-cache .tools/uv-0.11.29/bin/uv run --locked --offline --no-env-file ruff check .
  ```
- [x] Independently review, fix material findings, and commit only this local change. No live requests by implementer/reviewer.

## Follow-through (controller, no new product subsystem)

Start with three selected Markdown candidates from the already pinned public MIT `microsoft/prompts-for-edu` repository, without following links. If their essential workflow is excluded by the unchanged evidence filter, preserve that exclusion and screen at most two additional public repositories, within the user's original three-repository screening limit; do not relax the filter. Freeze eligible order and a fresh local budget before calls: at most three extraction requests, one generation, one Pro review and nine comparison requests, no slot borrowing; cumulative model cost ceiling stays CNY100. First faithful qualified candidate may advance. Never hand-edit generated semantic data. Freeze usefulness tasks/rubric only after a validated package exists. Failures remain recorded.

## Execution outcome

Implemented at `7c0c446`; source/config frozen at `153b8a2`; two bounded real-source
integration repairs at `7f02248`. Final offline suite: 3,011 passed, 3 skipped;
Ruff and independent code review passed. One faithful real extraction then one
real generation produced a package rejected by unchanged checks. No Pro request,
comparison, remote change or publication followed. See the
[complete result](../specs/2026-09-20-selected-markdown-result.md). The input-format
implementation is complete; the useful-Skill goal is not achieved.
