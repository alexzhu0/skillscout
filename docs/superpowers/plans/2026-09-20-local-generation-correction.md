# Local source-faithful generation correction implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the one integrated code task, then independent task and final review. The user explicitly requested a correction plan **and execution**, and previously delegated routine design/execution decisions. Do not insert another routine approval gate. Controller owns final full-suite verification and documentation.

**Goal:** Correct the observed local generation boundary and reference-link defects without changing historical evidence, public schema shapes, hosted defaults or safety thresholds.

**Architecture:** Add one explicit, single-attempt local generation variant to the existing build command. Existing profile/prompt identity fields bind the variant through authority, replay, generation and rendering. Keep the v1 schema and renderer family; a closed local profile branch renders trusted reference links. A post-response guard rejects unsupported values in source-absent approval/failure fields, preserving telemetry rather than repairing model output.

**Tech Stack:** Existing Python 3.13, Pydantic, SQLite, provider adapters, pytest and Ruff. No dependencies, database, framework, new command or external service.

**Spec:** User request “创建修正计划并执行”, the bounded design in this conversation, and the observed failures in [the September 20 report](../specs/2026-09-20-selected-markdown-result.md). Success here means offline-correct implementation, not a newly accepted real Skill.

## Global Constraints

- No live model request, credential read, GitHub/network operation, push, PR, merge or publication in this correction task.
- Do not edit the September 20 source, extracted JSON, canonical descriptor, failed package, state, frozen trial configuration or consumed launchers. Its remaining requests stay closed.
- Keep public JSON schema shapes and defaults unchanged, including `GeneratedSkillDraft`, `GenerationRequestV1`, `WorkflowSpec`, all authority/provenance/validation models, and the `skill-renderer-v1` Literal. Existing v1 prompt text and default renderer bytes remain unchanged.
- Keep license, source bindings, copy thresholds (80-character unregistered match; 120/240 registered-quote limits), safety rules, token limits, reviewer model and unknown-response/no-replay behavior unchanged.
- New local mode always caps generator and reviewer attempts at one. It has no publication authority, even if its underlying Phase 2 source is ordinary rather than a local preview.
- Never silently replace, delete or repair generated semantic fields. Invalid new-profile responses become `schema_invalid` with their original model/request/token/latency telemetry and no retained draft.
- The new guard proves only the two structured absent-field contracts; it does not prove arbitrary prose fidelity or model usefulness. Existing independent Reviewer and human checks remain necessary.
- Work only in the existing isolated `codex/first-useful-skill-loop` worktree. Preserve all historical failures. Final delivery is local commits plus documentation.

## Design and alternatives

The failure is not a missing source document. `approvals` and `failure_handling`
require nonempty output lists even when the source fields are empty; the generic
manual-publication instruction does not distinguish SkillScout policy from source
requirements. References are emitted as files without a trusted index. Unregistered
copy detection behaved as specified and must not be weakened.

Rejected alternatives: changing global v1 instructions/renderer behavior would
silently change hosted and replay semantics; allowing empty public-schema lists
or introducing renderer-v2 Literals would widen this task into a schema migration;
repairing the failed output by hand would invalidate the experiment.

Selected design: one closed local profile, opted into explicitly, keeping old
input/output shapes. The profile and prompt pair fully identify the variant in
existing authority digests. Renderer family v1 remains truthful as a dispatch
family: old profile has exactly its old behavior, new profile adds a reference
index. Do not relabel the old failed package as a new-profile result.

## Review Focus

1. An absent source field plus invented model text must fail with telemetry intact and zero review calls, rather than be rewritten to a sentinel.
2. Genuine nonempty source approvals/failure modes must remain eligible for semantic review; the absence guard must not erase them or require exact copying of long passages.
3. Empty references, four references and Markdown-like titles must produce only valid deterministic local paths; unknown/mixed local profile/prompt pairs fail closed.
4. Default profile output and exact completed replay remain unchanged; a local variant must never reuse a default terminal result or silently dispatch a different prompt than its authority.
5. New local-profile publication is rejected before any remote capability is constructed, independently of Phase 2 source scope. Single-attempt and unknown-outcome behavior cannot expand.

## Task 1: Implement the complete local generation variant

**Files:**
- Modify `src/skillscout/domain/skill_artifacts.py`: closed identity/sentinel constants, local profile/prompt pairing, deterministic reference index.
- Modify `src/skillscout/adapters/openai_generate.py`: new prompt branch, exact selected prompt identity, absent-field rejection while preserving response telemetry.
- Modify `src/skillscout/application/phase3.py`: derive generator prompt from existing profile identity, bind it before lookup, verify the constructed client identity before dispatch, and enforce local one-attempt bounds.
- Modify `src/skillscout/cli.py`: one explicit build option and preflight pairing with `--single-attempt`; no hosted wiring.
- Modify `src/skillscout/domain/publication.py`: explicit rejection of local profile/prompt authority during candidate publication admission.
- Test in `tests/test_local_generation_preview.py` (new), plus narrow existing `test_openai_generate.py`, `test_skill_generation.py`, `test_phase3_pipeline.py`, `test_cli_build_candidate.py`, `test_publication_admission.py` or the actual corresponding publication test if needed. Do not create a parallel test framework.

**Exact contracts:**

```python
# Constants in domain/skill_artifacts.py; no new serialized fields.
LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION = "phase3-local-source-faithful-v1"
LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION = "generator-local-source-faithful-v1"
SOURCE_APPROVALS_UNSPECIFIED = "The source does not specify approval requirements."
SOURCE_FAILURE_HANDLING_UNSPECIFIED = "The source does not specify failure handling."
```

`build-candidate --source-faithful-generation` requires `--single-attempt`.
Reject an invalid combination before provider/state/client construction. Construct
the existing runtime profile with the local `profile_version` and attempt caps
1/1, without adding serialized profile fields. Existing `profile_digest` must bind
the changed value. Expose the selected generator prompt through a read-only
property; use that same value in execution authority and client construction.
`OpenAIGenerationClient(prompt_version=GENERATOR_PROMPT_VERSION)` remains the
default and accepts only the default and the new closed prompt identity.
The local generator client must report the expected prompt identity before any
request. Legacy injected clients without that property retain their existing v1
contract; missing/wrong identity is never accepted for the new variant.

- [x] **RED: demonstrate the missing behavior with real components and recorded transports.** Use existing `_request`, `_draft`, `_authority`, recorded transport and composition fixtures as appropriate; rebuild authority hashes whenever changing source facts. Baseline v1 snapshots are literal bytes/digests captured before the implementation, not expectations computed by the modified renderer. At minimum exercise:

  ```python
  assert local_result.status == "schema_invalid"  # source approvals absent, invented draft
  assert local_result.draft is None
  assert local_result.usage.total_tokens == 42
  assert local_result.request_id == "chatcmpl-generator-1"
  assert recorded.call_count("POST", "/chat/completions") == 1
  assert "[formatting-constraints](references/formatting-constraints.md)" in skill_text
  assert not any(f.code == "structure_orphan_resource" for f in findings)
  ```

  Repeat absent-field rejection for failure handling, test both OpenAI and DeepSeek
  recorded paths, and test faithful sentinels plus genuine nonempty source fields.
  Use recorded payloads, not a test that merely searches prompt source text. No
  real API call and no claim that a fake response proves semantic model quality.

- [x] Run the new tests and save the expected pre-implementation failures in the task report. Distinguish assertion failures from fixture/setup errors.

- [x] **GREEN: add the minimal client/authority/rendering behavior.** Preserve the v1 prompt verbatim. Derive a separately named local prompt that clearly says: use only source-supported obligations; SkillScout's publication policy is not an approval requirement for user work products; source-absent fields use exactly the sentinels above; supplied source failure rules stay source rules, not invented exceptions; preserve exact counts, sections and limits while paraphrasing prose; avoid unregistered long source matches and retain existing quote constraints. Raw evidence stays only in the untrusted user payload, never in trusted instructions.

  At the actual client response boundary, for a parsed local response only:

  ```python
  workflow = request.workflow_spec_authority.workflow_spec
  unsupported = (
      not workflow.required_approvals
      and result.draft.approvals != (SOURCE_APPROVALS_UNSPECIFIED,)
  ) or (
      not workflow.failure_modes
      and result.draft.failure_handling != (SOURCE_FAILURE_HANDLING_UNSPECIFIED,)
  )
  if unsupported:
      return result.model_copy(update={"status": "schema_invalid", "draft": None})
  ```

  Preserve all telemetry and known refusal/incomplete handling. The two providers
  share this small guard. Nonempty source fields are not forced to match text
  byte-for-byte; those semantics remain Reviewer responsibilities. Default v1
  responses do not go through the new guard. The runner records the rejection as
  an ordinary closed generator outcome, not an ambiguous transport failure.

  For the exact local profile/prompt pair, append trusted relative reference links
  using validated `reference.name` for both label and path, not model-provided title:

  ```python
  f"- [{reference.name}](references/{reference.name}.md)"
  ```

  Preserve tuple order; render no index when there are no references. Do not add
  provenance as a semantic reading dependency. Unknown mixed local/default
  identity pairs fail before rendering. Keep existing `RENDERER_VERSION` and all
  schema Literals unchanged; the existing profile/prompt pair versions the local
  branch, and remains in provenance, artifact identities and replay authority.

- [x] **Exercise all Review Focus edges.** Cover default byte compatibility; new
  profile/prompt binding and stale-completion separation; zero/four refs and safe
  labels; unchanged overcopy rejection with an 80-character match; preserved
  request telemetry on rejected new-profile outputs; no reviewer after generation
  rejection; 1/1 caps including transient/unknown outcomes; direct publication
  admission denial for the local authority with an otherwise eligible ordinary
  source. No sentinel may be substituted by the renderer to turn a failure green.

- [x] Run focused tests and Ruff, inspect the entire diff for new schema fields,
  dependency or workflow changes, and write the implementation/TDD report. Tell the
  controller when product/test files are frozen. Controller runs the full suite
  once on that frozen code before final completion/commit; do not launch duplicate
  20-minute suites or edit modules during the controller's run.

- [x] Complete independent task review, address concrete findings with focused
  RED/GREEN evidence, and preserve the whole-task diff for final independent review.

## Task 2: Controller verification, docs and local handoff

- [x] Re-run the focused suite independently and perform final whole-change review
  with a fresh reviewer. If fixes are needed, return them to the implementer.
- [x] Run frozen full offline tests and Ruff:

  ```bash
  UV_CACHE_DIR=.tmp/uv-cache .tools/uv-0.11.29/bin/uv run --locked --offline --no-env-file pytest -q -ra
  UV_CACHE_DIR=.tmp/uv-cache .tools/uv-0.11.29/bin/uv run --locked --offline --no-env-file ruff check .
  git diff --check
  ```

- [x] Update `README.md`, `RELEASE.md`, `docs/CONFIGURATION.md` with the opt-in
  command, one-attempt/local-only bounds, unchanged defaults and precise offline
  evidence. Add a short result section to this plan; do not rewrite the closed
  September 20 trial as a success. Record remaining semantic/real-model uncertainty.
- [x] Commit only reviewed local code/tests/docs; preserve worktree and historical
  diagnostic files. No push/merge/PR. No new campaign, extraction, generation or
  usefulness calls in this task. A later trial needs fresh frozen configuration,
  new durable request reservations and its own outcome record, not old slots.

## Plan self-review

All observed failures are covered: missing links have deterministic correction;
source-absent obligations have explicit prompt guidance plus a reject-only guard;
overcopy remains enforced and has a regression, rather than a bypass. Exact counts
and instructions are preserved in test fixtures but real model fidelity remains
unproven. No public schema migration or hosted prompt promotion is required.
The schema-compatible local branch is a deliberate boundary, not a general plugin
or profile registry. All five Review Focus items map to Task 1 tests.

## Execution result — September 20, 2026

Implemented the explicit local variant in the existing build command. No public
schema shape, hosted default, dependency, workflow, reviewer model, copy threshold
or historical artifact was changed. The old stage-record profile Literal remains
the ledger schema family; each record's authority digest binds the exact runtime
profile/prompt. Both independent reviewers checked that separation and found no
replay or identity ambiguity.

Fresh verification on frozen code:

- Full offline suite: **3033 passed, 3 skipped in 1163.93s**, exit 0.
- Controller's expanded focused suite: **329 passed in 6.59s**.
- Whole-repository Ruff and `git diff --check`: passed.
- Nine public JSON schema hashes and legacy prompt hash: unchanged.
- Six preserved September 20 failure-artifact checksums: unchanged.
- Task review and final whole-change review: approved, no blocking findings.

The three skips are the still-pending Phase 6 release-requirement map and two live
canaries without explicit protected configuration. They are not newly claimed as
passing. An initial full run was deliberately stopped after it exposed a stale
CLI option-set assertion (1 failed, 1905 passed, 1 skipped); the newly authorized
option was added to that exact test and the entire suite rerun as recorded above.
The original RED evidence and intermediate failures remain in the local task log.

One non-blocking maintenance observation remains: the CLI repeats the existing
default attempt count `3`. Current behavior is correct; neither reviewer required
reopening the frozen change for it.

This correction made **zero live model requests** and incurred **zero provider
spend**. It does not turn the earlier failed package into an accepted Skill, prove
real-model source fidelity or usefulness, complete Phase 6, or grant publication
authority. A later real trial needs fresh configuration, state/output and durable
reservations; the closed trial is not resumed. Local commits only, no push/PR/merge.
