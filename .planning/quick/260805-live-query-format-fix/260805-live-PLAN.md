---
quick_id: 260805-live
title: Fix live-authority query JSON formatting compatibility
phase: quick-260805-live
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - src/skillscout/bootstrap.py
  - tests/test_phase6_acceptance.py
must_haves:
  truths:
    - Live-authority configuration accepts the repository's valid formatted query JSON when its checked-out commit, strict model, and query digest all match.
    - Source-file binding, strict schema validation, query-set digest binding, and fail-closed handling remain unchanged.
    - The regression test reproduces the formatted query-file case and prevents a return to the unnecessary byte-layout rejection.
  artifacts:
    - path: src/skillscout/bootstrap.py
      provides: Live-authority runtime configuration validation without a formatting-only rejection.
    - path: tests/test_phase6_acceptance.py
      provides: Regression coverage for formatted query JSON in the live-authority loader.
  key_links:
    - from: src/skillscout/bootstrap.py
      to: src/skillscout/domain/discovery.py
      via: Exact checked-out query bytes are still parsed into DiscoveryQuerySetV1 and bound by query_set_digest.

<objective>
Remove the formatting-only incompatibility that prevents Phase 6 live-authority recording from loading the repository's valid query JSON. Keep the exact checked-out commit, strict Pydantic model, and digest bindings as the authority boundary.
</objective>

<context>
The failed live-authority run rejected config before remote state restore because `config/discovery-queries-v1.json` is valid formatted JSON rather than canonical one-line JSON. Manifest and workflow checks already permit canonical bytes with an optional trailing newline. The query file must receive the same semantic treatment while remaining bound to the exact checked-out source commit and model digest.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Align live query validation with the repository format contract</name>
  <files>src/skillscout/bootstrap.py</files>
  <action>Remove only the query_bytes canonical-byte membership requirement from load_live_authority_recording_runtime_config. Retain exact checked-out source verification, strict DiscoveryQuerySetV1 validation, and the non-null query_set_digest requirement. Do not change workflow, manifest, state, credential, or endpoint binding.</action>
  <verify>
    <automated>.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k live_authority</automated>
  </verify>
  <done>Formatted repository query JSON reaches the typed digest-bound configuration while malformed or mismatched source content still fails closed.</done>
</task>

<task type="auto">
  <name>Task 2: Add a focused formatted-query regression</name>
  <files>tests/test_phase6_acceptance.py</files>
  <action>Add a deterministic loader test using the checked-out repository fixture and a formatted query payload, asserting configuration succeeds only with the exact source commit and strict query digest. Keep assertions structural and avoid secrets or raw diagnostic text.</action>
  <verify>
    <automated>.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_acceptance.py -k live_authority</automated>
  </verify>
  <done>The test fails if the formatting-only byte check returns and passes when semantic validation plus digest binding is preserved.</done>
</task>

</tasks>

<verification>
Run focused Phase 6 acceptance tests, then the full locked suite. Confirm the diff is limited to the loader and regression test; no workflow, dependency, credential, endpoint, or publication authority changes are present.
</verification>

<success_criteria>
- The current main query file format loads in live-authority config.
- Exact commit/source binding and strict typed digest validation remain enforced.
- Focused and full locked tests pass.
</success_criteria>
