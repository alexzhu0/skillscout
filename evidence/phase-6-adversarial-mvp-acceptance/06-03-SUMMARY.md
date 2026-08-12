---
phase: 06-adversarial-mvp-acceptance
plan: "03"
subsystem: semantic-provider
tags: [deepseek, openai, structured-output, reviewer-isolation, tdd]

requires:
  - phase: 06-01
    provides: Wave 0 provider contracts and validation ownership map
  - phase: 06-02
    provides: Adversarial acceptance and hosted-isolation contract surfaces
provides:
  - Immutable extraction/generation/review DeepSeek model policy
  - Pre-credential exact provider-profile admission
  - Stage-bound Flash/Flash/Pro adapter requests and output caps
  - Wrong actual-model quarantine and Reviewer context-isolation evidence
affects: [06-04, 06-05, 06-07, 06-08, 06-13, live-acceptance]

tech-stack:
  added: []
  patterns:
    - Immutable MappingProxyType stage-to-model policy
    - Typed semantic-stage admission before transport
    - Exact actual-model verification before durable telemetry

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
  - "Keep DEEPSEEK_MODEL as the historical Flash alias while new authority comes only from immutable DEEPSEEK_MODEL_BY_STAGE."
  - "Validate the complete provider settings profile before environment credential lookup, then validate the typed stage/model pair before HTTP."
  - "Treat a DeepSeek response whose actual model differs from the admitted stage model as semantic_outcome_unknown."
  - "Fix DeepSeek output caps at 8000 extraction, 6000 generation, and 2000 review tokens while preserving recorded OpenAI behavior."

patterns-established:
  - "Closed semantic policy: extraction and generation use deepseek-v4-flash; review uses deepseek-v4-pro."
  - "Reviewer isolation: only WorkflowSpec, rendered files, provenance, and a zero-error ValidationReport enter a fresh judge-only request."

requirements-completed: [TEST-01, TEST-04]

coverage:
  - id: D1
    description: Exact official-DeepSeek Flash/Flash/Pro policy rejects every invalid profile or stage/model pair before credential lookup or transport.
    requirement: TEST-01
    verification:
      - kind: unit
        ref: "tests/test_semantic_provider.py (44 passed)"
        status: pass
      - kind: other
        ref: ".tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py --wave-zero-complete"
        status: pass
    human_judgment: false
  - id: D2
    description: Extraction, generation, and isolated Pro review use exact stage identities, token caps, no tools, one request, and sanitized telemetry.
    requirement: TEST-04
    verification:
      - kind: integration
        ref: "tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_semantic_provider.py (150 passed)"
        status: pass
      - kind: integration
        ref: "full regression excluding 26 explicitly named future-plan Wave 0 RED nodes (1962 passed, 115 skipped)"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-07-29
status: complete
---

# Phase 6 Plan 03: Closed Flash/Flash/Pro Provider Policy Summary

**Typed DeepSeek stage admission now binds extraction/generation to Flash and independent review to Pro, with exact caps, pre-key validation, and no-tools one-request transport**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-29T07:10:46Z
- **Completed:** 2026-07-29T07:20:46Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Replaced the historical all-Flash live profile with an immutable `SemanticStage` to `DEEPSEEK_MODEL_BY_STAGE` mapping while retaining the old Flash alias only for historical compatibility.
- Moved exact endpoint, credential-variable, and stage-model profile admission ahead of environment key lookup; invalid stage/model pairs cannot reach the transport.
- Wired extraction, generation, and review to typed stages with exact 8,000/6,000/2,000 token caps, JSON mode, non-thinking mode, no tools, and one SDK request.
- Preserved the four-section Reviewer envelope and proved raw repository, expected label, human notes, Generator history, edit authority, and publication authority cannot enter the request.
- Quarantined wrong actual DeepSeek model telemetry as `semantic_outcome_unknown` instead of accepting mismatched evidence.

## Task Commits

Each TDD task was committed atomically:

1. **Task 06-03-01 RED: stage-aware provider contracts** - `245d551` (test)
2. **Task 06-03-01 GREEN: exact provider admission** - `55563ba` (feat)
3. **Task 06-03-02 RED: stage-specific adapter contracts** - `3af03c3` (test)
4. **Task 06-03-02 GREEN: Flash/Flash/Pro adapter wiring** - `717a393` (feat)
5. **Plan refactor: locked Ruff formatting** - `db3d00d` (style)

## Files Created/Modified

- `src/skillscout/adapters/semantic_provider.py` - Defines the immutable stage map, validates complete settings before key lookup, admits exact stage/model pairs, and rejects mismatched actual-model telemetry.
- `src/skillscout/adapters/openai_extract.py` - Sends DeepSeek extraction through `SemanticStage.EXTRACTION` with the exact Flash model and 8,000-token cap.
- `src/skillscout/adapters/openai_generate.py` - Sends generation through `SemanticStage.GENERATION` with the exact Flash model and 6,000-token cap.
- `src/skillscout/adapters/openai_review.py` - Sends fresh independent review through `SemanticStage.REVIEW` with the exact Pro model and 2,000-token cap.
- `tests/test_semantic_provider.py` - Covers immutable mapping, pre-key rejection, valid/invalid stage pairs, strict JSON outcomes, request accounting, and telemetry.
- `tests/test_openai_extract.py` - Records the exact Flash extraction body and cap.
- `tests/test_openai_generate.py` - Records the exact Flash generation body and cap.
- `tests/test_openai_review.py` - Records the exact Pro review body, forbidden-context mutations, and wrong actual-model rejection.

## Decisions Made

- Historical all-Flash evidence remains immutable: `DEEPSEEK_MODEL` continues to name Flash for compatibility, but all new live admission uses `DEEPSEEK_MODEL_BY_STAGE`.
- The settings factory validates every non-secret identity before resolving an environment credential, so a manually forged `SemanticProviderSettings` cannot redirect a key or endpoint.
- Actual DeepSeek model mismatch is an ambiguous provider outcome, not a business rejection or repairable schema error; the attempt is quarantined without automatic replay.
- Existing deterministic OpenAI request bodies and fixture coverage remain unchanged and require no live OpenAI credential.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Applied the locked Ruff formatter to all eight plan files**
- **Found during:** Final plan verification
- **Issue:** `ruff format --check` reported the eight files touched by this plan were not in the locked formatter's canonical form.
- **Fix:** Ran the repository-locked Ruff formatter over exactly those files and reran Ruff plus the affected and broad regression suites.
- **Files modified:** The four semantic adapters and their four test modules.
- **Verification:** `ruff check` passed, `ruff format --check` reported all eight files already formatted, and 150 focused tests passed.
- **Committed in:** `db3d00d`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Pure formatting only; no authority, behavior, dependency, endpoint, or schema changes beyond the planned implementation.

## Issues Encountered

- The unfiltered full suite ended with `1962 passed, 115 skipped, 26 failed`. All 26 failures are the exact Wave 0 RED nodes intentionally reserved for later Phase 6 plans: acceptance domain contracts, application dependencies, repository/adversarial/source-execution verifiers. They were not fixed or reclassified. Rerunning the broad suite with only those five explicitly named future-contract tests deselected produced `1962 passed, 115 skipped, 26 deselected`.
- The Phase 6 validation-map completeness gate remained green before and after implementation. The 06-02 hosted-isolation blocker remains unchanged and still blocks only Plan 06-06 credit.

## Authentication Gates

None.

## Known Stubs

None. The scan found only intentional optional/default `None` values and empty local accumulator collections; no placeholder or unwired runtime output was introduced.

## User Setup Required

None - no external service configuration required and no live credential was read.

## Next Phase Readiness

- Plans 06-04 and later can bind new acceptance evidence to the exact Flash/Flash/Pro semantic policy.
- Live acceptance needs only the official DeepSeek credential at the late client-construction boundary; recorded OpenAI tests remain credential-free.
- Plan 06-06 remains blocked by the explicit failed hosted-isolation probe recorded in 06-02; this plan does not alter that evidence.

## Self-Check: PASSED

- All eight created/modified plan files exist.
- Task and formatting commits `245d551`, `55563ba`, `3af03c3`, `717a393`, and `db3d00d` exist in Git history.
- Wave 0 validation-map verification passed.
- The 150 focused provider/adapter tests passed after formatting.
- Ruff check and Ruff format check passed for all eight plan files.
- Broad regression excluding only the 26 explicitly named future-plan RED nodes passed with 1,962 tests and 115 expected skips.
- No new dependency, endpoint, schema trust boundary, credential read, source execution, or publication capability was introduced.

---
*Phase: 06-adversarial-mvp-acceptance*
*Completed: 2026-07-29*
