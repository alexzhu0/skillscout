# Bounded extraction correction implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow exactly one application-owned correction of eligible DeepSeek extraction output without increasing request limits or weakening evidence validation.

**Spec:** `docs/superpowers/specs/2026-09-09-extraction-correction-design.md` (approved).

**Architecture:** Closed correction reasons and a versioned prompt feed the existing PhaseTwoProcessor. The pipeline records the first response as a telemetry-bearing failed attempt and schedules a separately reserved correction through its existing retry loop. State validation binds eligibility, prompt identity, and predecessor semantics. The coordinator includes both responses in request accounting.

**Stack:** Existing Python 3.13, Pydantic, sqlite3, OpenAI SDK compatibility transport, pytest. No new dependency or service.

## Global Constraints

- At most one correction HTTP request for a repository extraction identity.
- The correction consumes an existing attempt slot: the current three-attempt extraction ceiling and twenty-request campaign ceiling do not increase.
- After a correction is dispatched, do not retry it, including on a confirmed transport rejection.
- The policy applies only to the explicit DeepSeek extraction profile. OpenAI, generation, and independent review behavior remain unchanged.
- Keep each provider response's request ID, actual model, usage, latency, prompt version, and policy version in its own attempt record.
- Never allow another request after an arbitrary `decided` predecessor.
- No real provider calls, live workflows, credential reads, candidate execution, merge, or release are authorized by this plan.
- Worktree: `/Users/alexzhu/Lenovo/skillscout/.worktrees/codex/extraction-correction`; branch `codex/extraction-correction`. Read no `.env`, PEM, or secret material.
- Use `.tools/uv-0.11.29/bin/uv run --locked pytest -q`; use apply_patch for file edits. Commit only owned files.

## Task 1: Closed correction policy and single-call prompt boundary

Files:
- Create `src/skillscout/domain/extraction_correction.py` for closed reasons, versions, and pure eligibility validation.
- Modify `src/skillscout/adapters/openai_extract.py` for a provider property and an optional closed correction argument.
- Modify `src/skillscout/application/processors.py` to consume application-owned scratch context and report correct prompt/policy telemetry.
- Modify `src/skillscout/application/ports.py` only if a typed correction interface/error code belongs there.
- Create `tests/test_extraction_correction.py`; extend `tests/test_openai_extract.py`, `tests/test_extractor_boundary.py` as appropriate.

Interfaces:
- `ExtractionCorrectionReason` is a string enum with `SCHEMA = "extraction_correction_schema"` and `EXCERPT = "extraction_correction_excerpt"`.
- `EXTRACTION_CORRECTION_POLICY_VERSION = "extract-correction-policy-v1"` and `EXTRACTION_CORRECTION_PROMPT_VERSION = "extract-correction-prompt-v1"`.
- A pure eligibility function accepts an extractor payload and returns a reason or None. It requires `outcome == "schema_failure"`, no workflows, and either exact schema-validation diagnostic or all-dropped with at least one dropped entry whose nonempty reason set is only `excerpt_not_verbatim`. It never interprets free text.
- Telemetry completeness and provider/policy eligibility are checked at the application boundary, not inferred by this pure payload predicate.
- `OpenAIExtractionClient.extract(*, user_payload: str, correction: ExtractionCorrectionReason | None = None)` still sends exactly one request. Reject invalid/non-DeepSeek correction before network I/O. Fixed code-owned instructions carry the reason; rejected model output is never supplied.
- PhaseTwoProcessor consumes scratch key `extraction_correction` only when it is the enum, with explicit DeepSeek provider. Absent key keeps ordinary call signature compatible with existing fakes. Its correction request reports correction prompt/policy versions. Expose a safe, non-secret correction-policy capability for runner identity selection without eagerly constructing lazy semantic clients.

- [ ] Add failing eligibility cases (schema, excerpt, mixed, unsafe-only, negative, partial, incomplete, refusal) and transport tests before implementing.
- [ ] Implement the pure predicate and adapter support without changing schema or validators.
- [ ] Test that request user content remains identical, correction instructions are fixed, tools are absent, one invocation creates one request, and OpenAI correction produces zero calls.
- [ ] Run focused tests and Ruff; record RED/GREEN commands and output in report; commit.

Example assertion contract (use local fixture builders for valid complete payloads):

```python
assert extraction_correction_reason(schema_failure) is ExtractionCorrectionReason.SCHEMA
assert extraction_correction_reason(unsafe_only) is None
assert extraction_correction_reason(partial_success) is None
assert correction_request["messages"][-1] == initial_request["messages"][-1]
assert len(transport.requests) == 2  # two explicit calls, no SDK retry
```

## Task 2: Durable bounded correction attempts and coordinator accounting

Files:
- Modify `src/skillscout/application/pipeline.py`, `src/skillscout/application/ports.py`.
- Modify `src/skillscout/adapters/state.py`, `src/skillscout/adapters/operations_state.py` only where verification/ledger semantics need to change.
- Modify `src/skillscout/bootstrap.py` for lazy policy selection, reusable identity, retry classification, and telemetry gathering/linkage.
- Modify `src/skillscout/domain/acceptance.py` and existing authority construction/verification call sites as required to bind the new correction policy and admit exactly its prompt/policy telemetry pair; preserve historical authority readability and existing schema shape.
- Add focused tests in `tests/test_extraction_correction.py`, `tests/test_semantic_durability.py`, `tests/test_pipeline_resume.py`, `tests/test_state_integrity.py` as needed.

Consume Task 1's enum/versions/predicate and processor context. Preserve the old one-shot policy for OpenAI and historical state. Do not broaden generic retry authority to any failed/decided result.

- [ ] Add failing pipeline tests for invalid→valid, invalid→invalid, invalid on third attempt, and correction transport rejection. Inspect exact attempts/telemetry, not only invocation counts.
- [ ] Bind enabled correction policy into reusable identity before run selection; preserve acceptance-specific identity salt. New-policy failed attempts cannot be reused under old policy.
- [ ] Persist validated initial telemetry and one closed eligibility error before reserving correction; do not complete or overwrite a stage envelope for this interim result.
- [ ] Revalidate latest failed attempt, policy, explicit error, telemetry, previous corrections, and remaining slots before issuing a correction. Started correction attempts must already identify correction prompt/policy in durable state before provider dispatch.
- [ ] Reuse operations `confirmed_retryable` only for a verified eligible attempt, without fabricating provider transport disposition. Map scheduling to the existing application loop. A correction transport rejection closes permanently with truthful terminal classification and no subsequent request.
- [ ] Update state/operations cross-checks to reject tampered eligibility, missing telemetry, stale policy, wrong predecessor, and unexpected correction identity. Preserve old readable state without table migration.
- [ ] Gather complete telemetry from eligible failed attempts plus final successful attempts, preserving independent request IDs and token usage; campaign request reservations remain unchanged.
- [ ] Run focused durability/resume/state suites and the existing production five-repo regression; record RED/GREEN and commit.

Test assertions must include:

```python
assert [a["attempt_no"] for a in extractor_attempts] == [1, 2]
assert extractor_attempts[0]["status"] == "failed"
assert extractor_attempts[0]["request_id"] != extractor_attempts[1]["request_id"]
assert extractor_attempts[1]["prompt_version"] == EXTRACTION_CORRECTION_PROMPT_VERSION
assert len(requests_after_resume) == len(requests_before_resume)
```

## Task 3: Production composition, recovery acceptance, and documentation

Files:
- Modify `tests/test_phase6_acceptance.py` using its existing recorded DeepSeek production composition.
- Modify `tests/phase6_process_harness.py` or create a focused correction crash harness only if required to prove process recovery (reuse fixtures, no new framework).
- Modify `src/skillscout/adapters/semantic_provider.py` and extraction adapter only for explicit extraction refusal exclusion if recorded negative tests confirm the existing helper misclassifies it; generation/review behavior remains unchanged.
- Update `README.md`, `RELEASE.md`, `docs/TESTING.md`, `docs/project/v1-status.md`, and `docs/project/2026-09-09-direction-review.md` only for delivered behavior and remaining real-use validation.

- [ ] Add recorded production cases for schema→valid and nonverbatim→valid with independently traceable response usage, plus twice invalid terminal `schema_exhausted`.
- [ ] Cover prior transport retry consuming a slot, correction transport rejection final, budget exhaustion before correction, no duplicate calls on replay, and disabled profiles.
- [ ] Exercise reservation, started, response-persisted, and terminal recovery boundaries, including a fabricated `decided` predecessor and mismatched eligibility/policy. Use focused fault injection, not sleeps; existing process harness runs once at final validation.
- [ ] Run complete tests in bounded partitions (the 12 existing process tests are slow; run them once, not after every edit), full Ruff, diff check, and the three existing Phase 6 inspectors.
- [ ] Update documentation without claiming useful real Skill generation or Phase 6 completion. Preserve historical facts.
- [ ] Commit code/tests/docs, obtain whole-branch independent review, address findings and rerun covering tests.
- [ ] Prepare a Draft PR after verification. Do not merge or launch a live campaign. Report tests, any remaining limits, and the next product-validation step.
