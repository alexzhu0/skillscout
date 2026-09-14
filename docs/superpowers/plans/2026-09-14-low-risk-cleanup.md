# Low-risk Cleanup Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this bounded cleanup; review the diff before integration.

**Goal:** Remove confirmed duplicate implementation and a retired write entry without changing active behavior.

**Architecture:** Keep existing stage adapters, schemas, read/write capability separation and V2 authority composition. Reuse the existing state base class and small pure response helpers; introduce no framework.

**Tech Stack:** Existing Python 3.13, Pydantic, pytest and locked uv toolchain.

**Spec:** The user-approved in-chat audit follow-up: low-risk cleanup first; SQLite metadata and historical GSD acceptance changes deferred.

## Global Constraints

- No credentials, live model calls, workflow dispatch, remote state changes or automatic merges.
- No changes to prompts, models, retry policies, schema identities or publication admission.
- Preserve historical V1 authority reading and all current V2 authority gates.
- Leave historical GSD evidence and current workflow files unchanged.
- Run `.tools/uv-0.11.29/bin/uv run --locked pytest -q` before and after changes.

## Tasks

- [x] Establish the clean offline baseline in the existing isolated worktree: 293 focused tests passed. The initial full run was interrupted for latency repartitioning; its partial count is excluded from final evidence.
- [x] In `src/skillscout/adapters/state_branch.py`, remove only the derived `_ref` and `_json` copies. Existing `tests/test_state_branch.py` exercises returned observations, bounded response failures and non-force CAS conflicts. All 94 tests passed after deletion; read-only client capability restrictions remain unchanged. An in-process mutation returning empty JSON was caught by the existing absent-ref test before refactoring.
- [x] In `src/skillscout/bootstrap.py`, remove only `record_live_acceptance_authority` (the V1 writer). Remove its two obsolete writer tests and port the rejection test to `verify_live_acceptance_authority_state` in `tests/test_phase6_acceptance.py`; retain V1 verifier and V2 writer tests. Caller tracing and independent review confirmed the boundary. All 30 authority/recording tests passed afterwards.
- [x] Add pure `response_token_usage(response)` and `first_response_refusal(response)` functions to existing `semantic_provider.py`, after 12 tests fail for the absent behavior entry points, then pass. Reuse them from extraction, generation and review; keep request/model/latency and stage-specific validation at their existing call sites.

The helper tests in `tests/test_semantic_provider.py` use `SimpleNamespace`
responses with literal OpenAI/DeepSeek counts, absent usage and negative counts:

```python
assert response_token_usage(None) is None
assert response_token_usage(response).model_dump() == {
    "prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14,
}
with pytest.raises(ValidationError):
    response_token_usage(negative_usage_response)
assert first_response_refusal(response_with_multiple_messages) == "first refusal"
```

Implementation copies only the common token-field normalization and refusal
scan into the two functions. The adapters retain their `ValidationError`
classification and bounded stage result models. Do not add telemetry classes.

- [x] Run `tests/test_semantic_provider.py`, `tests/test_openai_extract.py`, `tests/test_openai_generate.py`, and `tests/test_openai_review.py`; all 179 passed, including malformed-telemetry and refusal cases.
- [x] Run full pytest, Ruff, `git diff --check`, and an independent code review. Final disjoint runs: 2,890 passed / 3 skipped excluding the twelve cross-process recovery cases, plus four passed for each of extractor, generator and reviewer: **2,902 passed, 3 skipped** in total. Full Ruff and diff checks passed. Independent review approved the code and prompted preservation of the V1 read-boundary rejection test.

Production code decreased by 239 lines; test code decreased by 122 lines while
adding twelve response-normalization/refusal cases. Dependencies, workflows,
prompts, model profiles, retry policy and historical evidence are unchanged.

The source-execution, validation-map and `--registry-only` acceptance inspectors
passed. The acceptance inspector without flags still reports `phase6 acceptance
incomplete` by design: offline structural checks do not supply live/human facts.

Integration is a separate local cleanup commit on `codex/low-risk-cleanup`, based
on `3d85b44`, not a merge or remote dispatch. Historical GSD verifier retirement
and SQLite schema-metadata simplification remain deferred, separate work.
