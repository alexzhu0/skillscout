---
phase: quick-260727-mfm
plan: 01
subsystem: semantic-providers
tags: [openai, deepseek, chat-completions, pydantic, security]
requires:
  - phase: 02
    provides: Existing OpenAI Responses extraction and Phase 3 semantic contracts
provides:
  - Closed OpenAI/DeepSeek provider selection and official endpoint validation
  - Strict local DeepSeek Chat Completions decoding for extraction, generation, and review
  - Provider-coherent Phase 3 runtime and publication model identity
  - Non-secret GitHub App authentication evidence and recoverable local PEM retirement
affects: [phase3, publication, semantic-extraction]
tech-stack:
  added: []
  patterns:
    - Provider configuration is resolved separately from secret binding
    - DeepSeek JSON output remains untrusted until strict local Pydantic validation
key-files:
  created:
    - src/skillscout/adapters/semantic_provider.py
    - tests/test_semantic_provider.py
    - .planning/quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/260727-mfm-PEM-AUTH-EVIDENCE.json
  modified:
    - src/skillscout/adapters/openai_extract.py
    - src/skillscout/adapters/openai_generate.py
    - src/skillscout/adapters/openai_review.py
    - src/skillscout/application/phase3.py
    - src/skillscout/bootstrap.py
    - src/skillscout/cli.py
    - tests/test_openai_extract.py
    - tests/test_openai_generate.py
    - tests/test_openai_review.py
    - .gitignore
key-decisions:
  - "Keep OpenAI SDK authority in the three existing adapter carve-outs and pass it into the provider helper."
  - "Require the exact official DeepSeek origin and fixed deepseek-v4-flash model before client construction."
  - "Retire the local GitHub App PEM only after exact read-only App/installation verification, owner-only permission hardening, and durable non-secret evidence."
patterns-established:
  - "Semantic provider profile: resolve non-secret provider/model identity once, then bind only its matching credential."
  - "DeepSeek response boundary: one terminal assistant choice followed by model_validate_json(strict=True)."
requirements-completed: []
coverage:
  - id: D1
    description: Closed DeepSeek provider and official endpoint boundary
    verification:
      - kind: unit
        ref: tests/test_semantic_provider.py
        status: pass
    human_judgment: false
  - id: D2
    description: DeepSeek execution across extraction, generation, review, and Phase 3 identity
    verification:
      - kind: integration
        ref: tests/test_openai_extract.py, tests/test_openai_generate.py, tests/test_openai_review.py
        status: pass
      - kind: integration
        ref: tests/test_phase3_bootstrap.py, tests/test_phase3_pipeline.py
        status: pass
    human_judgment: false
  - id: D3
    description: Fresh GitHub App proof, 0600 hardening, receipt, and exclusive Trash move
    verification:
      - kind: integration
        ref: 260727-mfm-PEM-AUTH-EVIDENCE.json and post-move filesystem checks
        status: pass
    human_judgment: false
duration: 14min
completed: 2026-07-27
status: complete
---

# Quick Task 260727-mfm: Safe DeepSeek V4 Flash Provider Path Summary

**Guarded DeepSeek V4 Flash Chat Completions now backs all semantic stages while OpenAI Responses remains unchanged; the verified local GitHub App PEM is recoverably retired.**

## Performance

- **Started:** 2026-07-27T08:25:12Z
- **Stopped:** 2026-07-27T08:46:36Z
- **Tasks:** 3 of 3 complete
- **Full locked suite:** passed (1,386 tests collected)
- **Focused verification:** 260 passed

## Accomplishments

- Added closed provider resolution with exact official DeepSeek endpoint admission, fixed `deepseek-v4-flash`, matching credential selection, zero SDK retries, no tools, disabled thinking, and strict local schema validation.
- Preserved the existing OpenAI Responses request path and result contracts while wiring DeepSeek through extraction, generation, and independent review.
- Bound the selected non-secret generator/reviewer model IDs into Phase 3 execution authority and publication projection without requiring an API key for projection.
- Added explicit `.env`, PEM, and private-key ignore coverage.
- Verified the exact GitHub App and installation through read-only endpoints, persisted only closed non-secret evidence, hardened the PEM to 0600, and moved it without overwrite to macOS Trash.

## Task Commits

1. **Task 1 RED:** `951d3f9` — failing provider boundary tests
2. **Task 1 GREEN:** `d5cbaa2` — guarded provider boundary
3. **Task 2 RED:** `9317098` — failing semantic-stage integration tests
4. **Task 2 GREEN:** `6e67f46` — DeepSeek semantic stages and runtime identity
5. **Task 2 compatibility fix:** `58f38e8` — preserve established capability and CLI seams
6. **Task 3:** `ab4a34d` — verified local App key retirement

## Verification

- `pytest -q tests/test_semantic_provider.py tests/test_openai_extract.py tests/test_openai_generate.py tests/test_openai_review.py tests/test_phase3_bootstrap.py tests/test_phase3_pipeline.py tests/test_cli_extract_repo.py tests/test_phase1_gap_closure.py` — 260 passed.
- `.tools/uv-0.11.29/bin/uv run --locked pytest -q` — passed; 1,386 tests collected.
- Ruff checks for all modified Python files — passed.
- `git diff --check` — passed before the Task 3 checkpoint.
- Closed receipt schema, exact App/installation identity, timestamp window, source absence, Trash destination owner/mode, and scoped Git status checks — passed.
- Post-verification live smoke against the official DeepSeek endpoint with `deepseek-v4-flash` and a fixed minimal JSON schema — passed; no repository content or credential value was emitted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test bug] Corrected the empty rejected-endpoint non-disclosure assertion**

- An empty string is contained in every exception string, so the assertion now checks non-disclosure only for nonempty rejected values.
- Included in `d5cbaa2`.

**2. [Rule 1 - Compatibility] Preserved existing CLI constructor test seams**

- Default OpenAI composition continues to invoke the established constructors without new provider arguments; only the explicit DeepSeek branch supplies provider settings.
- Included in `58f38e8`.

**3. [Rule 2 - Security] Kept OpenAI SDK authority inside existing audited adapter carve-outs**

- The new provider helper accepts the SDK capability from the three existing adapters instead of importing `openai` as a new production capability surface.
- Included in `58f38e8`.

## Credential Retirement

- The exact App ID `4382801` and installation ID `149272172` were confirmed through bounded read-only GitHub endpoints.
- The durable receipt contains only the closed schema, non-secret identifiers, endpoint outcomes, timestamps, basename, and public-key fingerprint.
- The source PEM is absent from the repository and the recoverable Trash copy is a current-user-owned, non-symlink regular file with mode 0600.
- The PEM was never staged or committed; `.env`, `*.pem`, and `*.private-key` are ignored.

## Known Stubs

None in completed Tasks 1-2.

## Self-Check: PASSED

- All source, tests, and non-secret evidence claimed for Tasks 1-3 exist.
- Commits `951d3f9`, `d5cbaa2`, `9317098`, `6e67f46`, `58f38e8`, and `ab4a34d` exist.
- Focused and full locked test suites passed; PEM retirement postconditions passed.
