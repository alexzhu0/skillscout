# Task 1 report: closed extraction correction boundary

## Changes

- Added `ExtractionCorrectionReason`, the exact policy/prompt versions, and a pure fail-closed payload eligibility predicate.
- Added an optional typed correction argument to `OpenAIExtractionClient.extract`; correction is DeepSeek-only, rejected before I/O otherwise, and each invocation still issues exactly one request.
- Kept the repository user payload byte-identical and added only fixed, code-owned correction instructions containing the closed reason; no rejected response is accepted by the interface.
- Exposed the adapter's non-secret provider identity.
- Added explicit `semantic_provider` composition metadata to `PhaseTwoProcessor` and the lazy-safe `extraction_correction_provider` capability property. A mismatch with an already exposed concrete provider fails closed.
- Made the processor consume only an enum-valued `scratch["extraction_correction"]` under explicit DeepSeek composition. Ordinary calls retain the legacy fake-compatible signature. Correction attempts report `extract-correction-prompt-v1` and `extract-correction-policy-v1` while preserving result telemetry.

## Runner interface for Task 2

Construct `PhaseTwoProcessor(..., semantic_provider=provider.provider)` at composition. The runner can inspect `processor.extraction_correction_provider` without resolving `_LazyDiscoveryCapability`; only the exact enum value `SemanticProvider.DEEPSEEK` advertises correction authority.

## TDD evidence

RED command:

`.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_extraction_correction.py tests/test_openai_extract.py tests/test_extractor_boundary.py`

After adding only the importable interface skeleton, output was `5 failed, 60 passed in 2.70s`. Failures were the two missing eligibility branches, missing adapter correction parameter/validation behavior, missing DeepSeek correction transport behavior, and missing processor capability/composition behavior. The immediately preceding collection run failed with three expected `ModuleNotFoundError` errors before the skeleton made behavioral RED possible.

GREEN command:

`.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_extraction_correction.py tests/test_openai_extract.py tests/test_extractor_boundary.py`

Initial output: `65 passed in 2.05s`. After review corrected mixed-drop semantics and added an unhashable-reason case, the policy-only RED was `2 failed, 12 passed in 0.02s`; final focused output was `67 passed in 1.31s`.

Ruff command:

`.tools/uv-0.11.29/bin/uv run --locked ruff check src/skillscout/domain/extraction_correction.py src/skillscout/adapters/openai_extract.py src/skillscout/application/processors.py tests/test_extraction_correction.py tests/test_openai_extract.py tests/test_extractor_boundary.py`

Output: `All checks passed!`.

## Self-review and concerns

- `git diff --check` passed.
- No schema or validator was changed; no provider, workflow, secret, candidate, merge, or release action was used.
- Task 2 must pass the explicit provider identity at both CLI and discovery/bootstrap composition sites; until then the safe property intentionally advertises no correction authority.
- The pure predicate accepts mixed dropped entries only when at least one entry has the exact nonempty reason set `{excerpt_not_verbatim}`. It rejects malformed containers, an entry that mixes excerpt and unsafe reasons without another excerpt-only entry, unsafe-only drops, partial success, incomplete/refused outcomes, and any diagnostic list other than the two exact admitted forms.

## Review fix round 1

- Removed duck-typed `provider` probing from `PhaseTwoProcessor` construction. Provider agreement is checked only for the known concrete `OpenAIExtractionClient`, so a lazy wrapper is not resolved before skip/durability boundaries; explicit composition metadata remains the runner-facing authority.
- Corrected the excerpt reminder for mixed drops: no workflows survived, at least one had nonverbatim evidence, and the model must re-evaluate the fresh original snapshot under all existing rules.
- RED: the two new regressions produced `2 failed in 0.65s`, one from lazy `__getattr__` resolution and one from inaccurate fixed instructions.
- GREEN: `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_extraction_correction.py tests/test_extractor_boundary.py tests/test_openai_extract.py tests/test_discovery_application.py::test_lazy_discovery_capability_does_not_resolve_extractor_on_skip` produced `69 passed in 1.02s`.
- Ruff on all owned source/test files produced `All checks passed!`.
