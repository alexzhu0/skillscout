---
phase: 02-safe-single-repository-extraction
plan: "02"
subsystem: security
tags: [httpx, mock-transport, github-rest, pipeline-profile, telemetry, scout, filter, composition-root, recorded-fixtures]

# Dependency graph
requires:
  - phase: 02-safe-single-repository-extraction plan 02-01
    provides: Gate-B2-approved httpx==0.28.1 graph, RepositorySubject/load_subject, filter-policy-v1 closed rules, reader tier predicates, ("2","phase2-v1") producer registration, RunStatus.COMPLETED
provides:
  - Profile-driven runner (PIPELINE_PROFILES with import-time spine-prefix guard), runtime-only per-invocation StageContext, and processor-returned StageTelemetry plumbed into attempts, envelopes and stage_output_hash
  - COMPLETED terminal with durable bounded extraction-summary.json via the shared locked/atomic/fsync durable-artifact core
  - Closed read-only GitHubReadClient (REMOTE_READ) with templated endpoints, pinned API version, per-endpoint byte caps, same-host recorded redirects, total error mapping and bounded Retry-After
  - PhaseTwoProcessor Scout (pin + bounded snapshot) and Filter (filter-policy-v1 verdicts) with deterministic skip cascade
  - build_phase_two_runtime: closed six-registration registry under SideEffectPolicy.phase_two() admitting at most REMOTE_READ
  - Recorded-transport harness (tests/recorded_transport.py + tests/fixtures/github/*.json) whose call counts double as no-replay evidence
affects: [02-safe-single-repository-extraction plans 02-03/02-04, phase 3+]

# Tech tracking
tech-stack:
  added: []
  patterns: [producer-resolved closed pipeline profiles with global stage indices, additive attempt-telemetry seam before complete_stage, recorded-transport fixtures with call-count replay evidence, business rejections as succeeded attempts with deterministic skip cascades]

key-files:
  created: [src/skillscout/adapters/github.py, src/skillscout/application/processors.py, tests/recorded_transport.py, tests/test_github_adapter.py, tests/test_phase2_pipeline.py, tests/test_scout_filter.py, tests/fixtures/github/ (17 recorded responses)]
  modified: [src/skillscout/application/ports.py, src/skillscout/application/pipeline.py, src/skillscout/adapters/state.py, src/skillscout/domain/models.py]

key-decisions:
  - "Deliver context and telemetry through additive carriers (StageOutcome/StageContext/ContextStageProcessor) with producer-profile dispatch instead of bumping the StageProcessor signature — every Phase 1 process(self, stage_input) override subclass stays byte-for-byte green."
  - "Build one StageContext per stage invocation as a snapshot (subject, copied prior payloads, fresh scratch); resume hydration comes only from the verified chain, never from processor memory."
  - "Blob URLs embed the tree-derived blob SHA (content addressing at the pinned commit); the SHA-in-URL invariant binds tree/license URLs to the pinned commit SHA and forbids any floating ref after resolve_commit."

patterns-established:
  - "Profile-driven stage slices: a closed PIPELINE_PROFILES map resolves producer → spine-prefix stage tuple + context flag + terminal status, validated at import time, with global stage indices preserved."
  - "Additive attempt-telemetry seam: processor-returned StageTelemetry is written onto the running attempt before complete_stage, so envelope and attempt agree under verify_run_chain."
  - "Recorded-transport fixtures: repository-owned JSON (status/headers/body) mapped by (method, path) through httpx.MockTransport; unrecorded requests raise and call counts double as no-replay evidence."
  - "Business rejections are succeeded attempts: Scout/Filter rejections and downstream skipped outcomes return payloads and consume zero retry budget; only infrastructure errors raise."

requirements-completed: [FILT-01, FILT-02, FILT-03, READ-01]

coverage:
  - id: D1
    description: "Profile-driven runner: phase2-v1 runs (SCOUT, FILTER, READER, EXTRACTOR) at global indices 0..3 with per-invocation context, resume hydration from the verified chain, real telemetry on attempt+envelope, telemetry-sensitive output hash, COMPLETED terminal and durable bounded extraction-summary.json; fixture-v1 behavior byte-for-byte unchanged"
    verification:
      - kind: unit
        ref: "tests/test_phase2_pipeline.py#test_phase_two_slice_completes_with_context_telemetry_and_summary, test_resume_hydrates_prior_payloads_without_replaying_succeeded_stages, test_telemetry_variation_changes_the_stage_output_hash, test_fixture_profile_stays_one_argument_telemetry_free_and_publication_bound, test_run_signature_covers_repository_subjects, test_profiles_are_closed_prefix_slices_with_declared_terminals"
        status: pass
    human_judgment: false
  - id: D2
    description: "Closed read-only GitHubReadClient: templated endpoints, pinned API version, serial client, per-endpoint byte caps, same-host recorded redirects, total 429/limited-403/5xx/timeout/404/malformed/over-cap mapping with bounded Retry-After, canary token confined to the Authorization header"
    requirement: READ-01
    verification:
      - kind: unit
        ref: "tests/test_github_adapter.py (25 tests incl. test_every_content_url_embeds_the_pinned_sha_after_resolution, test_canary_token_stays_in_the_authorization_header_only, error/redirect/cap matrix)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Scout pins the exact commit before any content read and emits a bounded snapshot; no_ref_resolvable, sha256_repository_unsupported, truncated and over-cap projections are recorded deterministic rejections"
    requirement: READ-01
    verification:
      - kind: unit
        ref: "tests/test_scout_filter.py#test_scout_happy_path_pins_and_projects_the_bounded_snapshot, test_scout_rejects_when_no_ref_is_resolvable, test_scout_rejects_a_sha256_repository_without_fetching_content, test_scout_rejects_a_truncated_tree, test_scout_rejects_an_over_cap_candidate_projection"
        status: pass
    human_judgment: false
  - id: D4
    description: "Filter evaluates filter-policy-v1 over the Scout snapshot with complete versioned decision records; every FILT-01 variant fails its named rule with observed values; every FILT-02 license boundary (null, NOASSERTION, non-listed, multiple files, endpoint 404, metadata/endpoint mismatch) rejects deterministically with at most one gated license GET; no LLM is involved"
    requirement: FILT-01
    verification:
      - kind: unit
        ref: "tests/test_scout_filter.py#test_filter_happy_path_accepts_with_complete_versioned_decisions, test_filter_repo_rule_variants_fail_with_observed_values, test_filter_fails_missing_default_branch_with_observed_value, test_filter_fails_missing_readme_with_observed_value, test_filter_fails_unallowlisted_metadata_licenses_without_an_endpoint_call, test_filter_fails_multiple_root_license_files_without_an_endpoint_call, test_filter_fails_unconfirmed_license_endpoint_outcomes"
        status: pass
    human_judgment: false
  - id: D5
    description: "Rejected Scout/Filter outcomes make every downstream stage return deterministic skipped payloads with zero adapter calls and zero retry-budget consumption (attempt count 1 per stage), proven at runner level with recorded transport counts; unimplemented stages fail closed"
    requirement: FILT-03
    verification:
      - kind: integration
        ref: "tests/test_scout_filter.py#test_downstream_stages_skip_deterministically_after_rejections, test_rejected_run_completes_with_skips_and_consumes_no_retry_budget, test_scout_rejected_run_skips_everything_without_content_fetches, test_accepted_run_fails_closed_at_the_not_yet_implemented_reader, test_unhandled_stages_fail_closed"
        status: pass
    human_judgment: false
  - id: D6
    description: "build_phase_two_runtime admits exactly the six-registration closed set under SideEffectPolicy.phase_two() ({none, local_state, remote_read}); REMOTE_WRITE, caller policies, extra registrations, wrong concrete types and subclasses are rejected before any adapter invocation; build_dry_run_runtime and PHASE_ONE_MAX_SCOPES untouched"
    verification:
      - kind: unit
        ref: "tests/test_phase2_pipeline.py#test_phase_two_root_constructs_the_closed_six_registration_registry, test_phase_two_policy_rejects_remote_write_before_invocation, test_phase_two_root_has_no_policy_or_registration_inputs, test_phase_two_root_rejects_wrong_concrete_types, test_phase_one_root_rejects_the_phase_two_processor; tests/test_side_effect_policy.py unchanged and green"
        status: pass
    human_judgment: false

# Metrics
duration: 64min
completed: 2026-07-22
status: complete
---

# Phase 02 Plan 02: Safe Single-Repository Extraction — Runner Generalization, GitHub Adapter, Scout/Filter Summary

**Profile-driven runner with real telemetry and a COMPLETED terminal, a closed recorded-fixture-proven read-only GitHub adapter, and Scout/Filter stages whose deterministic rejections cascade downstream — all behind a REMOTE_READ-capped composition root with every Phase 1 test byte-for-byte green.**

## Performance

- **Duration:** 64 min
- **Started:** 2026-07-22T03:42:05Z
- **Completed:** 2026-07-22T04:46:31Z
- **Tasks:** 3
- **Files modified:** 27 (6 created source/test modules, 17 recorded fixture files, 4 modified source modules)

## Accomplishments

- `PIPELINE_PROFILES` resolves the closed stage slice from `producer_version` with an import-time spine-prefix guard: `fixture-v1` keeps all nine stages, one-argument dispatch, None telemetry and PLANNED_NOT_PUBLISHED; `phase2-v1` runs (SCOUT, FILTER, READER, EXTRACTOR) at global indices 0..3 with per-invocation `StageContext` (subject, prior payloads hydrated from the verified chain on resume, fresh scratch) and terminates COMPLETED with a durable bounded `extraction-summary.json` written through the shared locked/atomic/fsync durable-artifact core (`_ExtractionSummaryWriter`, seam prefix `extraction_`, marker `after_extraction_durable`, cap 65 536 bytes).
- Telemetry plumbing: `StageOutcome.telemetry` is validated, mixed into `stage_output_hash` and the envelope, and copied onto the running attempt via the additive `StateStore.record_attempt_telemetry` seam before `complete_stage`; attempt row and envelope agree under `verify_run_chain`, and a telemetry change alters the stage output hash while fixture-v1 hashes stay None everywhere.
- `GitHubReadClient` (REMOTE_READ): fixed `https://api.github.com` base with five templated endpoints, pinned `X-GitHub-Api-Version: 2022-11-28`, serial streamed reads with per-endpoint byte caps (1 MiB metadata/license, 8 MiB tree, 256 KiB blob), same-host-only recorded redirects, total error mapping (`raise ... from None`: timeout/network→transient, 429/limited-403/5xx→bounded `min(retry_after, 60)` sleeper then transient, metadata/pin 404→permanent, license 404→`not_found` business data, over-cap/malformed/cross-host→permanent), and the token read once from the environment into the Authorization header only.
- `PhaseTwoProcessor`: Scout parses owner/repo from the subject, pins the exact 40-hex commit before any content read (64-hex → recorded `sha256_repository_unsupported` rejection with zero tree/license fetches), snapshots the tree with a ≤512 path-sorted candidate projection (tier predicate + root LICENSE*/COPYING*/README* + submodule/symlink entries under candidate roots), and records repo facts, ref, redirects and rate-limit facts; Filter rebuilds `RepoFacts`/`TreeFacts`, performs at most one license GET (only when allowlist and single-file rules pass), and emits the complete eight-record versioned decision list — never delegating any license question to an LLM.
- Skip cascade: rejected Scout/Filter outcomes make FILTER/READER/EXTRACTOR return deterministic `{"outcome": "skipped", "skip_reason": ...}` payloads with zero adapter calls and zero retry-budget consumption (attempt count 1 per stage); not-yet-implemented stages fall through to a fail-closed `STAGE_PERMANENT_FAILURE` guard.
- `build_phase_two_runtime`: closed six-registration registry (`phase2_processor`, `sqlite_and_manifests`, `github_read` — the exact client held by the processor, `clock`, `run_ids`, `extraction_summary_writer`) under `SideEffectPolicy.phase_two()` admitting at most REMOTE_READ; concrete `type(...) is` checks reject subclasses/mocks; caller policies/registrations raise TypeError; `build_dry_run_runtime` and `PHASE_ONE_MAX_SCOPES` are untouched and the Phase 1 root rejects the REMOTE_READ-declaring phase-two processor before invocation.

## Task Commits

Each task was committed atomically (TDD: failing test, then implementation):

1. **Task 02-02-01: Profile-driven runner, telemetry seam and COMPLETED terminal** — `e7f0e17` (test), `763e939` (feat)
2. **Task 02-02-02: Closed read-only GitHub adapter over recorded MockTransport fixtures** — `61810f2` (test), `c6e7284` (feat)
3. **Task 02-02-03: Scout/Filter processors with skip cascade and the phase-two composition root** — `044a993` (test), `f0a0471` (feat)

**Plan metadata:** recorded below (docs: complete plan)

## Files Created/Modified

- `src/skillscout/application/ports.py` — additive frozen carriers `StageTelemetry`/`StageOutcome`/`StageContext`, `ContextStageProcessor` protocol, `StateStore.record_attempt_telemetry` (existing `StageProcessor` untouched)
- `src/skillscout/application/pipeline.py` — `PipelineProfile`/`PIPELINE_PROFILES` with import-time prefix guard, `PHASE_TWO_STAGE_SEQUENCE`, `PHASE_TWO_MAX_SCOPES`, `SideEffectPolicy.phase_two()`, `PhaseTwoRuntime`, `_ExtractionSummaryWriter`, shared `_write_durable_artifact` core (Phase 1 publication behavior preserved, `_acquire_publication_lock` body untouched), `_build_extraction_summary`, `build_phase_two_runtime`
- `src/skillscout/adapters/state.py` — additive `record_attempt_telemetry` (single running-row UPDATE inside the snapshot transaction, rowcount-1 required)
- `src/skillscout/domain/models.py` — `StageOutcomeEntry`, `ExtractionSummary` (bounded, workflow fingerprints ≤ 3, count coherence validator)
- `src/skillscout/adapters/github.py` — `GitHubReadClient` + frozen `RepoMetadata`/`TreeEntry`/`TreeSnapshot`/`LicenseResponse`/`RateLimitFacts`/`RedirectFacts`, byte-cap and `MAX_RETRY_AFTER_SECONDS` constants
- `src/skillscout/application/processors.py` — `PhaseTwoProcessor` (Scout/Filter dispatch, skip cascade, fail-closed guard), `SCOUT_MAX_CANDIDATE_ENTRIES = 512`
- `tests/recorded_transport.py` — recorded-fixture loader + `RecordedTransport` (request recording, call counts, unrecorded-request assertion)
- `tests/fixtures/github/*.json` — 17 recorded responses (4 metadata variants, 2 pins, 4 trees, 4 license outcomes, 429, 301, 1 blob)
- `tests/test_github_adapter.py` — 25 adapter tests (mappings, closed URL set, SHA-in-URL invariant, redirect recording, sleeper bounds, canary confinement)
- `tests/test_phase2_pipeline.py` — 14 profile/context/telemetry/terminal/composition-root tests
- `tests/test_scout_filter.py` — 24 Scout/Filter tests (rule matrix with observed values, license boundaries, skip cascades, runner-level retry-budget evidence)

## Decisions Made

- Profile dispatch over a protocol signature bump: the RESEARCH integration map proposed extending `StageProcessor.process` to `(stage_input, context) -> StageOutcome`; the plan's additive `ContextStageProcessor` + `PIPELINE_PROFILES` resolution delivers the same behavior while keeping the ~20 Phase 1 `process(self, stage_input)` override subclasses and every Phase 1 test byte-for-byte unchanged (this resolves the plan's flagged research-level deviation note).
- One `StageContext` per stage invocation: each dispatch receives a fresh carrier (subject, a copy of accumulated prior payloads, fresh scratch). A single shared mutable context would let later stage payloads leak into contexts recorded by earlier invocations, and "per-invocation scratch" forbids cross-stage scratch reuse.
- Blob addressing interpretation of the SHA-in-URL acceptance criterion — see Deviation 1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Acceptance assertion for the SHA-in-URL invariant could not hold literally for blob URLs**
- **Found during:** Task 02-02-02 (GREEN run of `test_every_content_url_embeds_the_pinned_sha_after_resolution`)
- **Issue:** The task's acceptance text asks that "after `resolve_commit` every tree/license/blob URL contains the pinned SHA". The GitHub blobs API is addressed by **blob SHA**, not commit SHA (`GET /repos/{o}/{r}/git/blobs/{blob_sha}`), so a literal reading is unsatisfiable for real API shapes; the blob SHA is itself content addressing derived from the tree at the pinned commit.
- **Fix:** Expressed the security invariant precisely in the test: tree and license URLs contain the pinned 40-hex commit SHA, the blob URL contains the tree-declared blob SHA, and the floating ref (`main`) never reappears in any post-pin URL. This is the READ-01 guarantee (pin before read; no floating refs) in its strongest API-correct form; no production code was weakened.
- **Files modified:** `tests/test_github_adapter.py`
- **Verification:** 25 adapter tests pass; the closed-endpoint-set test independently pins every recorded URL to the five templates.
- **Committed in:** `c6e7284`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test-assertion correction only; the pinned-before-read guarantee is enforced more precisely, not relaxed. No scope creep.

## Issues Encountered

- RED commits fail at collection with ImportError on the new module names — the expected RED shape for brand-new APIs (no behavioral stub exists yet to fail against). GREEN commits resolve them; the gate sequence test→feat is preserved per task.
- Strict-mode Pydantic rejects Python lists for tuple fields (lesson carried from Plan 02-01): provider JSON is therefore validated with `model_validate_json` (JSON arrays accepted) and test-side JSON artifacts with `model_validate_json` as well.

## Authentication Gates

None — no credentials were required; the suite runs entirely on `httpx.MockTransport` with zero network access.

## User Setup Required

None - no external service configuration required.

## Verification Evidence (canonical `<verify>` chain, single clean pass)

- `uv run --locked pytest -q tests/test_github_adapter.py tests/test_scout_filter.py tests/test_phase2_pipeline.py` — **63 passed**
- `uv run --locked ruff check src/skillscout tests` — **All checks passed!**
- `uv run --locked pytest -q` — **536 passed** (473 Phase 1/plan-02-01 baseline + 63 new)
- `git diff --stat 33eba2f -- <all Phase 1 source and test files>` — **0 lines changed** (`build_dry_run_runtime`, `PHASE_ONE_MAX_SCOPES`, `adapters/fixtures.py`, every Phase 1 test byte-for-byte intact)
- Pre- and post-run `shasum -a 256 uv.lock` — **`a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216`** (Gate-B2-approved bytes, unchanged; no dependency changes in this plan)

## Next Phase Readiness

- Plan 02-03 (budgeted Reader) builds directly on `PhaseTwoProcessor` (Reader handler slot behind the fail-closed guard), `GitHubReadClient.get_blob` with tree-declared size re-check, and the reader-policy-v1 contracts from Plan 02-01.
- Plan 02-04 (Extractor + CLI) inherits the telemetry seam (`extract-prompt-v1` prompt/policy/model fields already flowing), the `ExtractionSummary` workflow/fingerprint projection, and the phase-two composition root where the OpenAI adapter registers.
- The LLM-call-count-0 proof after filter rejection completes in 02-04 when the OpenAI adapter exists; the structural skip cascade and zero-adapter-call evidence landed here.

## Self-Check: PASSED

- Key files exist on disk (all `key-files.created` verified with `[ -f ]` after the final commit).
- `git log --oneline --grep="02-02"` returns six commits (three test → three feat, one per TDD task).
- Acceptance criteria re-run and passing: four-stage slice at global indices with COMPLETED + parseable bounded `ExtractionSummary`; telemetry identical on attempt and envelope with `verify_run_chain` green and telemetry-sensitive hashes; reader-interruption resume re-invokes only the extractor with chain-hydrated payloads; `run()` annotates `subject: FixtureSubject | RepositorySubject`; zero `git diff` under Phase 1 files; every FILT-01/FILT-02 fixture fails its named rule with observed values; happy path accepted with eight decision records; skip cascades with recorded call counts prove zero downstream adapter calls and attempt count 1 per stage; the phase-two root admits the closed six-registration set and rejects REMOTE_WRITE/caller policies/wrong types before invocation; the full suite passes under the canonical prefix.
- Plan-level `<verification>` commands re-run — results logged above.
- TDD gates: each of the three tasks has a `test(02-02)` RED commit preceding its `feat(02-02)` GREEN commit; no REFACTOR commit was needed.

---
*Phase: 02-safe-single-repository-extraction*
*Completed: 2026-07-22*
