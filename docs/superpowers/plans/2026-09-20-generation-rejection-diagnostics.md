# Local generation rejection diagnostics implementation plan

> Execute inline using `superpowers:executing-plans`; use TDD and one independent
> final review. The user requested a plan and implementation and previously
> delegated routine decisions; no additional routine approval handoff.

**Goal:** Identify the rejected boundary in a future local generation attempt
without retaining model text, changing acceptance, or triggering any live request.
**Architecture:** Add opt-in in-memory diagnostic metadata to the DeepSeek adapter;
the local source-faithful generation client also classifies its source checks.
Only the local CLI writes a terminal-bound, non-authoritative diagnostic sidecar.
**Tech Stack:** Existing Python, Pydantic, anchored local writer and pytest; no dependencies.
**Spec:** User request “制定优化方案并修改”, the short in-chat design, and
[observed diagnostic limit](../specs/2026-09-20-source-faithful-real-result.md#known-facts-and-diagnostic-limit).

## Global constraints

- No live requests, secrets, source execution, remote writes or publication.
- No prompt changes, relaxed validation, public authority/schema migration, new
  CLI option, database table, retry or recovery authority.
- Only `--source-faithful-generation --single-attempt` produces new diagnostics.
- Fixed reason codes; bounded, deduplicated top-level schema field/error categories.
  Unknown keys map to `document`; unknown error kinds to `invalid_value`.
- Never serialize exception messages, inputs, context, rejected text or arbitrary locations.
- Existing terminal/state/output meanings remain unchanged; older failures cannot
  be retroactively diagnosed. Preserve historical trial evidence byte-for-byte.

## Review focus

- Secrets in extra keys, nested fields, validation context and JSON decoder messages.
- Diagnostic state from a previous invocation contaminating a successful/unknown call.
- Default/hosted/reviewer behavior or prompt/schema byte drift.
- Sidecar writes following symlinks or changing immutable terminal evidence.
- Replaying completed work creates new requests or invents a missing diagnostic.

## Task 1: opt-in classification through local CLI

**Files:** create `src/skillscout/domain/generation_diagnostics.py` and
`tests/test_generation_diagnostics.py`; modify `semantic_provider.py`,
`openai_generate.py`, `cli.py`, `tests/test_cli_build_candidate.py`, README,
RELEASE and CONFIGURATION. No semantic/artifact authority model changes.

**Interfaces:** `rejection_diagnostic(reason, *, error=None, fields=()) -> dict`;
`DeepSeekJSONResult.diagnostic: dict | None`; internal
`request_deepseek_json(..., collect_diagnostics=False)`;
`OpenAIGenerationClient.last_diagnostic -> dict | None`.
Diagnostic dictionaries use `local-generation-diagnostic-v1`, a fixed `reason`,
`findings` with fixed `field`/`code`, and `truncated`.

- [x] Write recorded-transport tests for shape, empty, JSON, schema and source
  failures; assert precise literal reasons, no raw strings, one request, and
  `status == "schema_invalid"` / `draft is None` as before.

  ```python
  assert client.last_diagnostic["reason"] == "json_invalid"
  assert "PRIVATE_CANARY" not in json.dumps(client.last_diagnostic)
  assert result.status == "schema_invalid" and result.draft is None
  ```

- [x] Run `pytest -q tests/test_generation_diagnostics.py`; expected RED because
  the local client cannot expose a diagnostic yet. Keep actual SDK/validation;
  replace only remote HTTP with recorded responses.
- [x] Implement the bounded classifier with `error.errors(include_input=False,
  include_context=False, include_url=False)`; use only allowlisted type and first
  location component. Cap deduplicated findings at16; no raw messages.
- [x] Capture DeepSeek diagnostics only when explicitly requested by the local
  client; reset `last_diagnostic` before every generation. Distinguish missing
  parsed OpenAI output/parse failures without changing its result contract.
- [x] Classify local sentinel rejection as `source_contract` with fixed approval
  and/or failure-handling field codes; keep rejection and `draft=None` unchanged.
- [x] Add an integration test using real generator/recorded HTTP and real local
  state/projector. Assert `generation-diagnostic.json` is written, references the
  terminal digest, and never becomes a publication evidence kind.
- [x] Run that test before CLI implementation; expected RED: sidecar absent.
- [x] Write the sidecar only after a fresh local failed result, through
  `AnchoredDirectory`. Bind to terminal digest; do not reconstruct it on replay,
  trust it as authority, or overwrite an existing file with different bytes.
- [x] Cover clean success/unknown after failure, disabled/default path, hostile
  nested keys, finding cap, sidecar conflict/symlink and completed replay.
- [x] Run focused tests, full offline pytest, Ruff and historical hash checks.
  Expected all relevant tests green; explicitly report pre-existing skips/failures.
- [x] Update docs to distinguish diagnostic improvement from generation success.
  Commit locally and get one independent code review; no push or paid retest.

## Scope decisions

Keep the existing public schema and semantic output bytes unchanged. The sidecar
is local troubleshooting information bound to a terminal digest, not canonical
stage evidence. A crash before sidecar projection may leave it absent; recovery
must not regenerate model output merely to fill diagnostics.

## Verification result

Final frozen implementation: **3051 passed, 3 skipped in1225.05s**; expanded focused
suite **416 passed**; whole Ruff and whitespace checks passed. Existing skips are
the pending Phase 6 requirement map and two unconfigured live canaries. Independent
review's late-telemetry stale-diagnostic finding was reproduced RED for both
providers, fixed, and included in this final full run. The immutable-conflict test
was strengthened to reach the intended check. Historical artifact hashes match.
No paid call, prompt change, authority migration, remote update or Skill success
is claimed. Preserve the local ledger and interrupted old-code test log as failure
history; the latter is not counted as completed verification.
