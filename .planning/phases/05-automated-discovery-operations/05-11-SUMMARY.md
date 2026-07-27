---
phase: 05-automated-discovery-operations
plan: "11"
subsystem: semantic-provider
tags: [openai, deepseek, retry-safety, structured-outputs, security]

requires:
  - phase: 05-01
    provides: Closed discovery terminal vocabulary and outcome-unknown quarantine decision
  - phase: 05-03
    provides: Two-provider semantic durability acceptance matrix
provides:
  - Provider-neutral four-way semantic transport disposition
  - Sanitized SemanticProviderFailure carrier with bounded request telemetry
  - Classified OpenAI and DeepSeek Extractor, Generator and Reviewer boundaries
affects: [05-07, 05-13, 05-14, semantic-durability, discovery-operations]

tech-stack:
  added: []
  patterns:
    - Confirmed-only semantic retry authority
    - Default-unknown provider transport classification
    - Decided semantic outcomes remain successful closed results

key-files:
  created: []
  modified:
    - src/skillscout/adapters/semantic_provider.py
    - src/skillscout/adapters/openai_extract.py
    - src/skillscout/adapters/openai_generate.py
    - src/skillscout/adapters/openai_review.py
    - tests/test_semantic_provider.py
    - tests/test_openai_extract.py
    - tests/test_openai_generate.py
    - tests/test_openai_review.py

key-decisions:
  - "Only an exact provider 429 rejection grants confirmed retry authority; timeout, connection loss, 408, 5xx and unrecognized failures default to semantic_outcome_unknown."
  - "Post-send telemetry validation failures are outcome-unknown because replay could duplicate a semantic effect, while refusal, incomplete and schema-invalid responses remain decided outcomes."

patterns-established:
  - "Semantic failure projection: discard the originating exception and retain only disposition, closed code and a validated request ID."
  - "One request per adapter invocation: SDK retries stay disabled and no stage retries inside the adapter."

requirements-completed: [DISC-02, OPS-03]

coverage:
  - id: D1
    description: Provider-neutral semantic disposition classifies confirmed retryable, outcome-unknown, permanent and decided outcomes without raw provider details.
    requirement: OPS-03
    verification:
      - kind: unit
        ref: tests/test_semantic_provider.py
        status: pass
    human_judgment: false
  - id: D2
    description: OpenAI and DeepSeek Extractor, Generator and Reviewer preserve closed dispositions with exactly one request per invocation.
    requirement: DISC-02
    verification:
      - kind: integration
        ref: tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py
        status: pass
      - kind: integration
        ref: full pytest suite (1590 passed, 2 skipped, 93 xfailed)
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-07-27
status: complete
---

# Phase 5 Plan 11: Semantic Transport Disposition Summary

**Confirmed-only semantic retry authority across OpenAI and DeepSeek, with ambiguous transport and post-send failures quarantined as outcome-unknown in all three semantic stages**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-27T14:46:20Z
- **Completed:** 2026-07-27T14:53:44Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added one provider-neutral, closed four-way disposition and sanitized failure carrier.
- Classified both configured providers without using raw messages, bodies, headers or credentials as retry evidence.
- Applied the same one-request boundary to Extractor, Generator and Reviewer while preserving tool-less requests, OpenAI `store=false`, and strict local DeepSeek validation.

## Task Commits

Each TDD task was committed atomically:

1. **Task 05-11-01 RED: Define semantic transport contract** - `66ce34e` (test)
2. **Task 05-11-01 GREEN: Implement shared classifier** - `9e4c7c6` (feat)
3. **Task 05-11-02 RED: Require all-stage provider matrix** - `650daab` (test)
4. **Task 05-11-02 GREEN: Apply classifications to adapters** - `7ac760d` (feat)

## Files Created/Modified

- `src/skillscout/adapters/semantic_provider.py` - Closed dispositions, sanitized failures and shared typed classifier.
- `src/skillscout/adapters/openai_extract.py` - Classified OpenAI Extractor failures and ambiguous post-send telemetry.
- `src/skillscout/adapters/openai_generate.py` - Classified OpenAI Generator failures and ambiguous post-send telemetry.
- `src/skillscout/adapters/openai_review.py` - Classified OpenAI Reviewer failures and ambiguous post-send telemetry.
- `tests/test_semantic_provider.py` - Provider-neutral transport, sanitization and DeepSeek boundary evidence.
- `tests/test_openai_extract.py` - OpenAI/DeepSeek Extractor classification matrix.
- `tests/test_openai_generate.py` - OpenAI/DeepSeek Generator classification matrix.
- `tests/test_openai_review.py` - OpenAI/DeepSeek Reviewer classification matrix.

## Decisions Made

- Exact 429 response evidence is the only current confirmed-retryable transport case.
- Ambiguous delivery, provider processing, or post-send local projection defaults to outcome-unknown and cannot authorize automatic replay.
- Deterministic refusal, incomplete and strict-schema outcomes remain decided semantic results rather than transport failures.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The plan-required pytest and Ruff gates passed. The locked environment does not include a `mypy` executable, but mypy was not part of this plan's verification contract and no dependency was added.

## User Setup Required

None - all verification used recorded transports with no live network or credentials.

## Next Phase Readiness

- Plans 05-13 and 05-14 can map the closed disposition directly into durable pre-request/post-result barriers and quarantine behavior.
- No blocker remains for downstream semantic durability integration.

## Self-Check: PASSED

All eight modified implementation/test files and all four TDD commits were verified present.

---
*Phase: 05-automated-discovery-operations*
*Completed: 2026-07-27*
