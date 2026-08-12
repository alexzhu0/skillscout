---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 06
current_phase_name: adversarial-mvp-acceptance
status: executing
stopped_at: Completed hardened 06-17-PLAN.md V2 live-authority admission
last_updated: "2026-08-05T10:20:00Z"
last_activity: 2026-08-05
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 79
  completed_plans: 71
  percent: 90
---

# Project State: SkillScout

**Last updated:** 2026-08-04
**Milestone:** v1 — Safe discovery-to-Draft-PR MVP  
**Status:** Ready for Plan 06-18 protected-workflow checkpoint

## Current Position

**Phase:** 06 (adversarial-mvp-acceptance) — EXECUTING
**Plan:** 10 of 18
**Verification:** V2 live authority is now independently rebuilt and re-admitted before any live capability boundary. Plan 06-18 must wire that closed route into the protected workflow and preserve its exact environment and workflow-byte gates before 06-08 can begin.
**Next command:** `$gsd-execute-phase 6`

## Progress

```text
Project initialization  [██████████] 100%
MVP requirements        [██████████] 100%
Roadmap approval        [██████████] 100%
Phase 1 implementation  [██████████] 100%
Phase 1 verification    [██████████] 100%
Phase 2 extraction      [██████████] 100%
Phase 3 implementation  [██████████] 100%
Phase 3 verification    [██████████] 100%
Phase 4 publication     [██████████] 100%
Phase 5 operations      [██████████] 100%
Phase 6 acceptance      [██████░░░░]  56%
```

| Metric | Value |
|---|---:|
| MVP requirements | 44 |
| Requirements mapped | 44 |
| Roadmap phases | 6 |
| Phases completed | 5/6 |
| Plans completed | 71/79 authored plans |

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-22)

**Core value:** 安全、可追溯地把公开仓库中的可复用 AI 工作流转化为值得人类审核的标准 Agent Skill Draft PR。
**Current focus:** Phase 06 — adversarial-mvp-acceptance

## Accumulated Context

### Product Decisions

- SkillScout discovers reusable AI workflows in public GitHub repositories and publishes only human-reviewable Draft PRs to a controlled Skill catalog.
- Discovery runs daily and manually, with hard per-run budgets of 100 candidates and 20 LLM analyses.
- All external repository content is untrusted; no candidate code is cloned, installed, imported, built, or executed.
- Reader order is README → docs → examples → package manifests → limited source, with explicit budgets and early stop.
- `WorkflowSpec` is the only semantic boundary allowed to cross from raw repository content into generation, review, and publishing.
- v1 generates documentation-only Agent Skills and forbids `scripts/`.
- Only MIT, Apache-2.0, BSD-2-Clause, and BSD-3-Clause are accepted automatically.
- Independent Reviewer only judges; it never edits or rewrites the Skill.
- Publisher can create/update branches and Draft PRs but cannot merge, approve, mark ready, modify rulesets, or write the default branch.
- Human review and merge are required for every generated Skill.

### Architecture Decisions

- Python 3.13 modular monolith with typed stage contracts and provider adapters.
- GitHub REST API via HTTPX; OpenAI Responses API with strict Structured Outputs and Pydantic.
- SQLite is operational query state; versioned JSON manifests are auditable/rebuildable facts.
- MVP persists state on a dedicated `skillscout-state` branch because GitHub-hosted runners are ephemeral; cache/artifact are not canonical state.
- Production schedule/manual runs share one non-cancelling concurrency group.
- Cross-repository publishing uses a least-privilege short-lived GitHub App installation token and protected catalog ruleset.
- The roadmap uses vertical slices: dry-run spine → single-repo extraction → validated Skill → Draft PR → automated discovery → adversarial acceptance.
- Phase 2 reads only fixed commits through closed GitHub REST endpoints; tree-derived blob SHAs provide content authority after pinning.
- Phase 2 runtime authority is capped at REMOTE_READ; candidate text stays memory-only and crosses the semantic boundary only as validated `WorkflowSpec` evidence.
- OpenAI SDK retries are disabled; the pipeline owns the finite retry budget and decided business outcomes are never re-asked.
- Completed Phase 2 runs are reused only after full-chain verification, producing zero GitHub/OpenAI calls for the same identity.

### Scope Boundaries

- No automatic merge, code execution, unauthorized secrets, private repositories, vector database, multi-tenancy, Web admin, self-modification, public marketplace publishing, or generated scripts in v1.
- No fixed “8-Agent” deployment requirement; stage contracts, not agent count, define the architecture.

## Open Decisions

No product-scope blocker remains. Phase 6 execution retains explicit human checkpoints for:

- Selecting and locking the five Search-derived public repositories and fixed commit SHAs.
- Accepting only a fail-closed hosted kernel/network isolation mechanism proven by the capability probe.
- Authorizing the exact DeepSeek/GitHub live runs, changed-source lineage, fresh Gate B4, exact-head Skill review, and separate human/admin cleanup.

Live acceptance uses DeepSeek Flash for extraction/generation and Pro for independent review. A live OpenAI credential is not required. The target catalog remains fixed to `alexzhu0/skillscout-catalog-test`, and no checkpoint may broaden remote permissions or execution authority.

## Blockers

Phase 5 independently passed 6/6 roadmap criteria and all five mapped requirements. The final locked release chain passed 1,920 tests with 2 expected live-only skips. The 2026-07-28 Gate B4 evidence remains historical, but its workflow-byte bindings are stale after the 06-15 toolchain and hosted-runtime corrections and grant no current authority. Whole-product production readiness remains pending Phase 6 real-repository and adversarial acceptance.

- Plan 06-06 hosted isolation ingestion is blocked: run 30430010273 failed before the network probe, upload was skipped, and artifact count is zero.
- Plan 06-06 Task 3 blocked: exact offline-adversarial run 30441596331 attempt 1 at source 27d7a41f0e7c7ffeb2991110f44eab6a977c78ca failed during repository-local locked-toolchain verification; campaign and upload were skipped, artifact count is zero, and no hosted-isolation or offline-run canonical fact was persisted. No retry is authorized.
- Proven common cause for runs 30430010273 and 30441596331 was the exact-full-output guard rejecting the official pinned output `uv 0.11.29 (901092ee1 2026-07-15 aarch64-apple-darwin)`. Strict-TDD correction commits are RED `49a548261c84f81628d301f5bf4eba603c0c18ee` and GREEN `3b6b189cc848ab083cf83bf4489a5c91945f5aed`.
- The current authoritative workflow SHA-256 values are discover `71c174175b03355f432348bda9fca47ee72bee20a939d87720b7c32d4fe370e4`, publish `0bb486d9f06cc93d97a953bc1f40b6b2f206c9fdccdc914a90af1c9388faac19`, canary `ad06ccec08cf1df76a395b14574957e69aebe3ce78b2892c22c23912ed672ccc`, and Phase 6 acceptance `7eca32de7c0468d18c180ebecf567d7239412e54c2776e43621930b894570f63`.
- Every earlier workflow digest, dispatch approval, Gate B4 approval, and exact-source authorization is stale after the current workflow-byte changes. A new human checkpoint must bind the final local HEAD and current Phase 6 workflow digest before any retry; no push, dispatch, artifact access, canonical fact write, or approval inference has occurred.
- Plan 06-06 Task 3 remains blocked: authorized one-shot offline-adversarial run 30443794922 attempt 1 at source 5997ceaac5fc137971d031750be98323b5745591 passed checkout, pinned uv materialization, and locked-toolchain verification, then failed in the fresh kernel-isolated adversarial campaign; bounded evidence upload was skipped, artifact count is zero, and no acceptance_hosted_isolation_capability or acceptance_offline_adversarial_run canonical fact was persisted. No retry is authorized.
- Proven cause for run 30443794922 was the repository-visible `.venv/bin/python` resolving to a hosted Python base prefix outside the repository while the empty-rootfs Docker invocations did not mount that prefix. Strict-TDD correction commits RED `e86c8091279757fb43ffdb2dcac7afe364e79f91` and GREEN `b48e1fddc058e44a355ebc09086ec6a2aa65ee8d` attempted an exact `${RUNNER_TOOL_CACHE}/Python/` mount; that approach is historical and superseded by the repository-managed correction below.
- Plan 06-06 Task 3 remains blocked: authorized one-shot offline-adversarial run `30446151495` attempt 1 at exact source `f40d559244a68e3e7746fcd3a45c250685551b0f` and Phase 6 workflow SHA-256 `6a25a68d98cb8d796b8619bdb6e4922c28d575a4d0955aa80f8eb28dbc78981f` passed checkout, pinned uv materialization, and locked-toolchain verification, then failed in the fresh kernel-isolated adversarial campaign. The bounded evidence upload was skipped, artifact metadata reported `total_count: 0`, and neither `acceptance_hosted_isolation_capability` nor `acceptance_offline_adversarial_run` was persisted. Raw logs were not opened; no retry is authorized.
- Strict-TDD diagnostic instrumentation commits are RED `1a6d668` and GREEN `7d94188`. The campaign step now initializes one path-free closed diagnostic before runtime preflight, preserves its original nonzero exit, and uploads exactly one pinned one-day noncanonical diagnostic only on campaign failure. The independent verifier rejects stage/schema/status broadening, logs/paths/free text, retention or pin drift, and evidence/canonical promotion.
- This instrumentation is diagnostic-only: it changes no mount, temporary-directory policy, pytest command, probe, network mode, scenario, persistence, credential, catalog, publication, lock, or dependency behavior. It does not diagnose or fix run `30446151495`, grant campaign credit, or authorize artifact access.
- Run `30447435387` deterministically failed during runtime preflight before any container launched because the hosted toolcache-root assumption was unavailable. No artifact was accessed, no canonical fact was written, and no retry, push, or dispatch was authorized or performed.
- The user-approved correction materializes exact CPython `3.13.14` under canonical `${GITHUB_WORKSPACE}/.tools/python` in all 15 authoritative jobs. Six network-none invocations receive no external Python mount; the same-path read-only repository mount carries both `.venv` and its managed runtime, with downloads disabled. Strict-TDD commits are RED `80eaa3a68d945867b338e71262d12cb0abf87a61` and GREEN `a8f42d1baa50118fb9dffd5a797adb4ead13ecb0`.
- Run `30508458266` is a blocking failure fact: the kernel-isolated control returned 1 because the freshly recreated venv did not contain the current SkillScout project, while the direct and child network-denial probes both returned 97. The ordinary baseline, synthetic-canary environment, and read-only-repository checks each passed 36 tests; removing the project installation record reproduced the first-test failure, and restoring it produced 1 passed.
- The confirmed root cause was all 15 authoritative initializers running `uv sync --locked --no-install-project` after deleting `.venv`. Strict-TDD commits are RED `5aa3aa28eed11adefe3ccaa0bb294bdb22e6426e` and GREEN `e425de3acf9ccb6c8ebeabd3a4bb90ea80403070`; the correction installs only the current locked project and changes no lock, dependency, mount, network, probe, scenario, credential, publication, retention, or diagnostic authority.
- Every prior Phase 6 workflow digest, exact-source authorization, dispatch approval, and Gate B4 binding was stale after the fresh-project workflow-byte change. At that checkpoint, a new human authorization had to bind exact Phase 6 workflow SHA-256 `1e938070e70aabcf84a5d6d8fce5c674b36d19d7d6fe8771adffdd0f0ecd6fe5`; that consumed authorization is now historical and grants no retry, artifact-read, canonical-state, Gate B4, or publication authority.
- The fresh authorization was consumed by exactly one hosted run after fail-closed preflight: exact-SHA ref dispatch returned HTTP 422 and created no run; a fresh `origin/main == b1425f7f72407f08463578db387e84d79d72e2df` proof authorized the `main` fallback, which created run `30510875649` attempt 1 at that exact source and Phase 6 workflow SHA-256 `1e938070e70aabcf84a5d6d8fce5c674b36d19d7d6fe8771adffdd0f0ecd6fe5`.
- Run `30510875649` failed at the closed `campaign-report` stage with overall/control/direct/child statuses `1/1/97/97`. Its artifact inventory contained exactly the one-day diagnostic `8747046558`; the strict 378-byte JSON SHA-256 was `112b9c040433f10524b08a62d6e11764146b6e08f64e17a1fa3ed316641142ff` and the ZIP SHA-256 was `26faa56b695126a6d65cea55209787911973570b072f2e39251ba976b1306755`.
- This failure grants no hosted-isolation or campaign credit. No raw logs or other artifacts were opened, no canonical `acceptance_hosted_isolation_capability` or `acceptance_offline_adversarial_run` fact was written, and no retry is authorized. Plan 06-06 remains blocked and no `06-06-SUMMARY.md` exists.
- The old pytest-owned diagnostic from run `30510875649` is ambiguous by construction: control status 1 plus a missing session-teardown report cannot distinguish scenario/assertion failure from final report-write failure. It is retained only as a bounded failure fact, not a root-cause claim.
- The user-approved strict-TDD correction is RED `f32fa2d` and GREEN `e5ab102`. Hosted campaign control now invokes the installed `skillscout.application.phase6_adversarial_runner` with an exact closed 25-node registry, fixed validated bindings, no network/tools/subprocess/untrusted-code/path authority, canonical atomic output, synthetic scans, and distinct bounded scenario/report-write diagnostics. Pytest remains a development consumer only.
- The correction changes only `.github/workflows/phase6-acceptance.yml`; the other three workflow digests remain unchanged. Every prior Phase 6 workflow authorization, dispatch approval, and Gate B4 binding is stale. No push, dispatch, remote read, artifact read, canonical write, credential access, or publication action occurred.
- Blocking code review then proved the deterministic runner synthesized fixture bytes from canaries and registry names and returned static policy zeros without loading the seven committed injection fixtures. Strict-TDD RED `17fa07e` and GREEN `2625c27` embed and independently bind the exact 1,945-byte corpus, fail closed on omission/replacement/identity-swap/acquisition-bypass mutations, and pass actual inert bytes through ordered in-memory filter/read/extract/qualification/generate/validate/review/publication-barrier seams.
- Local evidence is limited to corpus digest `sha256:809fdb625fc9340ff6c4effa2dd5252311ea485bb4ec2c164aafb0835545d032`, 264 focused passes with 12 skips and the future verifier node deselected, and full locked pytest `2181 passed, 14 skipped, 1` planned RED failure. This grants no hosted-isolation/campaign credit, retry, dispatch, artifact read, canonical fact, Gate B4, credential, or publication authority. No workflow, `pyproject.toml`, or `uv.lock` byte changed.
- The fresh user authorization bound exact source/local/remote `main` `aacd2f2efb5db8e32728fba002f2d2f23dbed2d4`, Phase 6 workflow SHA-256 `9c62787e9a061ef061957b4c57b2635145d1c35df7063acc49ad668d2ff352ef`, unchanged discover/publish/canary digests, and corpus aggregate `sha256:809fdb625fc9340ff6c4effa2dd5252311ea485bb4ec2c164aafb0835545d032`. The exact-SHA dispatch returned HTTP 422 and created no run; fresh remote equality then authorized the one `main` fallback, which created run `30517690161` attempt 1 at that exact source.
- Run `30517690161` failed at the closed `synthetic-scan` stage with overall/control/direct/child statuses `1/0/97/97`. Its inventory contained exactly the one-day diagnostic artifact `8749511557`, named `phase6-offline-adversarial-diagnostic-30517690161-1`, with metadata size 416 bytes and expiry `2026-07-31T05:49:11Z`; the strict 377-byte JSON SHA-256 is `cffaf349b538c8dfcd4a8dfbf2125d6a38c1e6666050e7102a8ffc1b66f54370` and ZIP SHA-256 is `dc70b3523520f7aa6ed17bfd551266357a4c10e02eda21bb915b90dec1711792`.
- The sole artifact was the workflow-owned bounded schema `phase6.offline-diagnostic.v1`, not runner diagnostic v2 or success evidence. It proves the control and both denial probes reached their required statuses but grants no synthetic-scan, hosted-isolation, or completed-campaign credit. No raw logs or other artifact were opened, no canonical acceptance fact was written, no retry is authorized, and no `06-06-SUMMARY.md` exists.
- Confirmed root cause for run `30517690161`: `AtomicCampaignSink` created `campaign-report.json` with required mode `0600` inside the root-default control container, so the bind-mounted report was root-owned. Host `test -s` could stat it, but the non-root host synthetic scanner's `read_bytes()` raised `PermissionError`; an exact readable copy scanned with zero canary hits, and making only the report unreadable reproduced the failure.
- Strict-TDD ownership correction commits are RED `d4d7b5dd4858fc88c38f8d0db561cc28c62c3430` and GREEN `1c8aaf8359a3ff1eeea56b2cf10d151db71767db`. Only the report-writing control invocation receives exactly one validated numeric `--user "${host_uid}:${host_gid}"`; mode `0600`, direct/child probes, `--network none`, read-only repository mount, scan manifest, one-day artifacts, and no-retry policy remain unchanged.
- Local verification passed 124 focused tests and a 276-pass/12-skip wider Phase 6 matrix; all 35 workflow blocks passed `bash -n`; the independent source verifier passed; full locked pytest reported 2,193 passed, 14 skipped, and only the planned repository-verifier RED failure. The offline verifier remains correctly incomplete. `pyproject.toml` and `uv.lock` are unchanged.
- Every prior exact-source/workflow authorization, dispatch approval, and Gate B4 binding is stale after this workflow-byte correction. No push, dispatch, remote or artifact access, canonical write, credential inspection, publication, or cleanup occurred; Task 06-06-03 remains incomplete pending separately authorized hosted success.
- Plan 06-06 Task 3 is resolved by authorized run `30519607061` attempt 1 at source `a3c41cf8501bec435a646f140f52acedf1c5f312`: the exact seven-fixture/22-scenario campaign passed with control/direct/child statuses `0/97/97`, the sole one-day evidence artifact passed strict validation, and canonical state commit `37f8dcbf74c85f2471670373fd03f71d9f155bae` / root `sha256:b4167cffc31969854260d4acd58b804f4823a4d25d078ef3b5dc88445b75c2e5` fresh-rebuilt exactly `acceptance_hosted_isolation_capability` and `acceptance_offline_adversarial_run`. No raw logs, retry, third fact, credential disclosure, catalog/default-branch/PR/publication mutation, or follow-up push occurred.

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260727-mfm | Add a safe DeepSeek V4 Flash provider path and retire the verified local App PEM | 2026-07-27 | ab4a34d | Verified | [260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa](./quick/260727-mfm-add-a-safe-deepseek-v4-flash-provider-pa/) |
| 260805-orr | Fix Phase 6 preflight payload read budget | 2026-08-05 | e875ab0 | Complete | [260805-orr-fix-phase-6-preflight-payload-read-budge](./quick/260805-orr-fix-phase-6-preflight-payload-read-budge/) |
| 260806-fq1 | Refresh Phase 6 benchmark manifest from fresh nomination | 2026-08-06 | c21674c | Complete | [260806-fq1-refresh-benchmark-manifest](./quick/260806-fq1-refresh-benchmark-manifest/) |
| 260806-ggb | Canonicalize Phase 6 benchmark manifest bytes | 2026-08-06 | f3e97c0 | Complete | [260806-ggb-canonicalize-benchmark-manifest](./quick/260806-ggb-canonicalize-benchmark-manifest/) |
| 260806-rbm | Refresh Phase 6 benchmark manifest from fresh nomination a496 | 2026-08-06 | a9631e5 | Complete | [260806-rbm-refresh-phase6-manifest-a496](./quick/260806-rbm-refresh-phase6-manifest-a496/) |

## Session Continuity

**Last activity:** 2026-08-05
**Last session:** 2026-08-05T10:20:00Z
**Stopped at:** Completed quick fix 260805-orr: payload-only 90-second preflight budget
**Resume file:** None

### Next

1. Execute Plan 06-18 only after reviewing/merging the V2 authority Draft PR; it changes the protected workflow and requires a human environment checkpoint.
2. Follow the remaining fixed benchmark, hosted isolation, live credentials, Gate B4, human Skill verdict, and separate cleanup checkpoints without widening verified publication authority.

---
*State initialized: 2026-07-16*

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 01 P01 | 9 min | 3 tasks | 8 files |
| Phase 01 P02 | 15 min | 2 tasks | 9 files |
| Phase 01 P03 | 21 min | 3 tasks | 11 files |
| Phase 01 P04 | 21 min | 3 tasks | 11 files |
| Phase 01 P05 | 9min | 2 tasks | 5 files |
| Phase 01 P06 | 16min | 2 tasks | 6 files |
| Phase 01 P07 | 20min | 2 tasks | 5 files |
| Phase 01 P08 | 19min | 2 tasks | 9 files |
| Phase 01 P09 | 24min | 2 tasks | 5 files |
| Phase 01 P10 | 19min | 2 tasks | 7 files |
| Phase 01 P11 | 15min | 2 tasks | 3 files |
| Phase 01 P12 | 14min | 2 tasks | 5 files |
| Phase 01 P13 | 20min | 2 tasks | 8 files |
| Phase 01-auditable-dry-run-spine P14 | 13 min | 2 tasks | 4 files |
| Phase 01-auditable-dry-run-spine P15 | 9 min | 2 tasks | 5 files |
| Phase 01-auditable-dry-run-spine P16 | 16min | 2 tasks | 4 files |
| Phase 01-auditable-dry-run-spine P17 | 35min | 2 tasks | 6 files |
| Phase 01-auditable-dry-run-spine P18 | 19min | 2 tasks | 4 files |
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 02 P01 | 17 min | 4 tasks | 15 files |
| Phase 02 P02 | 64min | 3 tasks | 27 files |
| Phase 02 P03 | 43min | 2 tasks | 10 files |
| Phase 02 P04 | 56min | 3 tasks | 33 files |
| Phase 03 P01 | 1 min | 1 tasks | 4 files |
| Phase 03 P02 | 5min | 1 tasks | 6 files |
| Phase 03 P03 | 4 min | 1 tasks | 4 files |
| Phase 03 P04 | 9 min | 1 tasks | 3 files |
| Phase 03 P05 | 14 min | 2 tasks | 3 files |
| Phase 03 P06 | 20 min | 2 tasks | 4 files |
| Phase 03 P07 | 13 min | 2 tasks | 2 files |
| Phase 03 P08 | 24 min | 3 tasks | 7 files |
| Phase 03 P09 | 24 min | 3 tasks | 6 files |
| Phase 03 P10 | 23min | 3 tasks | 5 files |
| Phase 03 P11 | 35min | 3 tasks | 3 files |
| Phase 03 P12 | 29min | 3 tasks | 4 files |
| Phase 03 P13 | 16min | 2 tasks | 3 files |
| Phase 03 P14 | 17min | 2 tasks | 5 files |
| Phase 05 P01 | 9min | 2 tasks | 3 files |
| Phase 05 P02 | 6min | 2 tasks | 6 files |
| Phase 05 P03 | 9min | 2 tasks | 9 files |
| Phase 05 P04 | 5min | 2 tasks | 2 files |
| Phase 05 P05 | 16min | 2 tasks | 3 files |
| Phase 05 P06 | 9min | 2 tasks | 2 files |
| Phase 05 P11 | 8min | 2 tasks | 8 files |
| Phase 05 P12 | 20min | 2 tasks | 7 files |
| Phase 05 P14 | 10min | 2 tasks | 3 files |
| Phase 05 P13 | 15min | 2 tasks | 4 files |
| Phase 05 P07 | 8min | 2 tasks | 3 files |
| Phase 05 P08 | 56min | 2 tasks | 20 files |
| Phase 06 P01 | 12 min | 3 tasks | 8 files |
| Phase 06 P02 | 32 min | 3 tasks | 5 files |
| Phase 06 P03 | 10min | 2 tasks | 8 files |
| Phase 06 P04 | 18min | 2 tasks | 4 files |
| Phase 06 P05 | 12min | 2 tasks | 6 files |
| Phase 06 P15 | 9min | 1 tasks | 8 files |
| Phase 06 P06 | 21min | 3 tasks | 3 files |
| Phase 06 P07 | 95min | 3 tasks | 12 files |

## Decisions

- [Phase 01]: Approve exact Gate B lock bytes as execution authority — Any byte change to uv.lock invalidates the human-reviewed dependency graph.
- [Phase 01]: Keep Wave 1 static and uninstalled — Locked project code begins execution only in Plan 02 after both supply-chain gates.
- [Phase 01]: Load and strictly validate the bounded fixture before opening SQLite, so rejected input cannot create state. — Keep rejected untrusted input outside every durable run surface.
- [Phase 01]: Persist the five-field reusable identity on a running attempt before processor invocation. — Make migration, retry accounting and interruption evidence reconstructible from durable facts.
- [Phase 01]: Expose only four closed schema-v1 error codes and fixed ASCII summaries. — Prevent raw fixture, Pydantic, exception, credential and path disclosure.
- [Phase 01]: Validate current canonical identity before checkpoint reuse — Input, producer, or retry-policy mismatch starts a new run and preserves the interrupted audit record.
- [Phase 01]: Scope retry budget to persisted reusable_key_digest — Three transient or abandoned attempts exhaust one identity; permanent failures never receive a second invocation.
- [Phase 01]: Validate the complete immutable effect-scoped registry before constructing the dry-run runner — Remote authority is absent structurally, not hidden behind a flag.
- [Phase 01]: Persist only closed relative manifest locators — Filesystem roots derive from the configured state DB and operator paths never enter evidence.
- [Phase 01]: Keep every external diagnostic on a closed code and fixed bounded ASCII summary — Raw exceptions, payloads, credentials and paths never cross into durable or CLI surfaces.
- [Phase 01]: Derive registration authority only from adapter-owned effect declarations — Remove the parallel caller label that enabled capability misrepresentation.
- [Phase 01]: Seal build_dry_run_runtime to PHASE_ONE_MAX_SCOPES — Production construction has no policy or arbitrary-registration widening input.
- [Phase 01]: Keep PipelineRunner injectable while production composition requires supported concrete adapters — Deterministic tests retain protocol seams without widening the production authority boundary.
- [Phase 01]: Use one immutable producer/schema registry at runtime, migration, manifest write and manifest read boundaries. — Prevent successful evidence that the reader later rejects.
- [Phase 01]: Validate StagePayload and bound exact canonical manifest bytes before filesystem activity. — Keep untrusted outputs JSON-only, deterministic and resource bounded.
- [Phase 01]: Close known post-start failures immediately and reconcile indeterminate orphan attempts on next open. — Keep durable lifecycle evidence truthful after failures.
- [Phase 01]: Never give SQLite an operator pathname — Deserialize bounded descriptor-read bytes into private in-memory connections and serialize candidate snapshots only.
- [Phase 01]: Use a retained reusable lock inode with kernel-only flock ownership — Process death releases live ownership without lock-file deletion or recreation.
- [Phase 01]: Make every required local fsync fatal before state promotion — Manifest and publication bytes must be durable before checkpoint or terminal success.
- [Phase 01]: Separate semantic result identity from run-scoped row ownership — Stable semantic digests may repeat across runs, while deterministic result_row_id owns stage and checkpoint associations.
- [Phase 01]: Select resumable runs by complete exact RunIdentity — Schema, subject, fixture, producer, and retry-policy facts must all match before checkpoint reuse.
- [Phase 01]: Keep migrated v1 runs legacy_unbound until transactional canonical proof — Unbound evidence cannot authorize inspect or resume, and a wrong expected identity must leave state unchanged.
- [Phase 01]: Use one immutable schema-v2 descriptor set for creation, acceptance, and migration — A user_version value cannot establish structural or integrity compatibility.
- [Phase 01]: Treat persisted diagnostics as untrusted until exact closed validation — Public inspect output must never project corrupt, legacy, credential-bearing, or provider-controlled fields.
- [Phase 01]: Validate schema-v1 source rows before migration copy or manifest creation — Rejected legacy bytes stay unchanged evidence and cannot become new durable surfaces.
- [Phase 01]: Return VerifiedRunChain only for bound identity — Legacy-unbound evidence cannot authorize resume or full inspect before exact current identity proof.
- [Phase 01]: Keep legacy migration validation non-authorizing — The frozen v1 ledger lacks fixture_hash, so only reconstructible facts are validated before binding.
- [Phase 01]: Use one full-chain verifier for every bound trust path — Resume, latest checkpoint, completed verification, and inspect must reject identical corruption consistently.
- [Phase 01]: Preserve the historical schema-v1 semantic result preimage — Migrated and newly completed v1 stages must remain one canonical chain.
- [Phase 01]: Keep generated evidence outside standard pytest — Acyclic validation requires product and quality results to exist before the evidence document, followed by one standalone validation pass.
- [Phase 01]: Keep WR-04 deferred to Phase 6 — OS/syscall network denial is adversarial acceptance work and is not falsely claimed as a Phase-1 fix.
- [Phase 01]: Use the target directory fsync as the snapshot authority commit point — Post-commit backup retirement cannot truthfully report rollback
- [Phase 01]: Use one private regular-file predicate for state, manifest, and lock evidence — Every local evidence reader must enforce the same ownership, link, type, and mode boundary
- [Phase 01]: Reject equal state and derived manifest namespaces before filesystem creation — Operator-selected leaves cannot alias internal evidence directories
- [Phase 01]: Represent every invocation boundary as a content-addressed event; genesis alone is ordinal zero and every reopened run appends a later event.
- [Phase 01]: Treat the resume-event ledger as reuse authority and keep runs.reused_stage_count only as an atomically maintained projection of the current event head.
- [Phase 01]: Migrate pre-event runs only when historical reuse is absent or zero; reject nonzero schema-v2 claims because no independent event can attest them.
- [Phase 01]: Commit each resume event, run head, count, running status, and timestamp in one candidate snapshot before stale-attempt reconciliation or processor work.
- [Phase 01]: Make the final verified ResumeEvent the sole reuse-count authority — Mutable run count and head are accepted only as exact duplicates of the complete event proof.
- [Phase 01]: Verify migrated bound schema-v2 runs after conservative genesis installation — The exact schema-v3 candidate can use the same event-aware canonical verifier without inventing prior invocations.
- [Phase 01]: Route authoritative run reads through verify_run_chain — Every public reuse projection must reject the same tamper; no row-only public audit path remains.
- [Phase 01]: Discard every argparse-generated failure detail inside SafeArgumentParser — One fixed status-2 JSON diagnostic keeps rejected argv outside all output and durable surfaces.
- [Phase 01]: Treat sanitized pipeline interruptions as transient under the existing finite ceiling — Unexpected processor exceptions can recover without making explicit permanent failures retryable or widening the three-attempt budget.
- [Phase 01]: Keep the verified resume-event ledger as the sole retry prefix authority — Recovery starts at the failed stage and never replays already verified successful prefix effects.
- [Phase 01]: Keep evidence documents and verifier outcomes outside the authority they report — Eliminates self-hash and self-success cycles while exact source and fresh output remain independently checkable.
- [Phase 01]: Normalize only exact temporary roots and elapsed durations after the fixed timing marker — Makes reruns reproducible without removing failures, counts, node names, exit status, or arbitrary output.
- [Phase 01]: Recover crash-left deterministic temps only under the corresponding retained lock after the private regular-file predicate passes — Rejected temps are retained and the operation fails closed on sanitized codes.
- [Phase 01]: Serialize publication writers on a retained kernel-flock inode that is never deleted — A live lock holder makes concurrent publication writes fail closed with state_operation_failed.
- [Phase 01]: Bind both reviewed JSON fixtures as explicit literal paths in the closed evidence source set — Semantically neutral fixture byte changes now stale recorded evidence before command credit.
- [Phase 01]: Credit exactly the current review's CR-01/WR-01 findings through digest-bound nodes — The superseded seven-finding map survives only under the past-tense prior-review label.
- [Phase 02]: Admit exactly httpx==0.28.1 and openai==2.46.0 through the two-gate ceremony with no tiktoken, GitHub SDK, tenacity, or VCR library — Supply-chain inputs require separate declaration (Gate A2) and exact-lock-bytes (Gate B2) human approvals; Gate B2 binds all execution to uv.lock SHA-256 a23c47119a50650dd08d45209e2741cf2c5053031bbaef0bde95ca837ec59216
- [Phase 02]: Re-anchor the Phase 1 evidence verifier LOCK_HASH to the Gate-B2-approved uv.lock bytes — The verifier authority constant must track the human-approved graph; recorded Phase 1 evidence stales by design and awaits Phase 2 re-baselining
- [Phase 02]: Deliver context and telemetry through additive carriers (StageOutcome/StageContext/ContextStageProcessor) with producer-profile dispatch instead of bumping the StageProcessor signature — Every Phase 1 process(self, stage_input) override subclass and test stays byte-for-byte green; the runner selects the calling convention from the closed PIPELINE_PROFILES map.
- [Phase 02]: Build one StageContext per stage invocation as a snapshot (subject, copied prior payloads, fresh scratch); resume hydration comes only from the verified chain — A shared mutable context would leak later stage payloads into contexts recorded by earlier invocations; per-invocation scratch forbids cross-stage reuse.
- [Phase 02]: Blob URLs embed the tree-derived blob SHA (content addressing at the pinned commit); the SHA-in-URL invariant binds tree/license URLs to the pinned commit SHA and forbids any floating ref after resolve_commit — The GitHub blobs API is addressed by blob SHA, so the READ-01 pin-before-read guarantee binds tree/license URLs to the commit SHA and treats the tree-declared blob SHA as transitively pinned content addressing.
- [Phase 02]: Prove the max_total_bytes ±1 boundary on the pure _read_budget_stop predicate with a lowered ReaderPolicy while handler tests prove the four reachable gates at the real defaults — Under the organization ceilings the 40000-token estimate gate (160000 bytes at ceil(bytes/4)) always binds before the 524288-byte total gate, so the total gate is unreachable through the handler; lowering budgets is ceiling-legal and keeps the defaults-only production construction untouched
- [Phase 02]: Populate reader telemetry request_id only when the stage fetched at least one blob — A zero-fetch run would otherwise inherit a stale X-GitHub-Request-Id from the filter stage's license response, misattributing telemetry across stages
- [Phase 02]: Bind SDK retry to zero and let the runner RetryPolicy own re-attempts — one extract() is exactly one recorded HTTP request, so the one-call-per-attempt discipline is structural rather than configurational — A single responses.parse call site with max_retries=0; business outcomes are succeeded attempts and only 429/5xx/timeout/connection map to stage_transient_failure
- [Phase 02]: Reuse a completed phase-two run only through an additive find_completed_run seam and a runner short-circuit gated on the COMPLETED terminal — no new run rows, events or status transitions, and the fixture-v1 terminal path stays byte-identical — The plan-mandated zero-call idempotent rerun had no existing seam (find_resumable_run matches running/interrupted only and completed-to-completed transitions are illegal); the gated short-circuit rewrites the summary artifact through the durable core without touching Phase 1 semantics
- [Phase 02]: Prefer the per-invocation scratch bundle and rebuild it through hash-verified hydrate_read_bundle on fresh contexts — the runner shape always hydrates, so resume re-issues blob GETs only for byte-verified hydration — Per-invocation StageContext scratch never crosses stages in the runner; hydration against recorded content hashes preserves the no-raw-text-persistence boundary without weakening resume integrity
- [Phase 03]: Approved Gate A3 for exactly skills-ref==0.1.1 and wheel SHA-256 d35db5bb8de71ae301daf5ca9cb71f8a555e8c6f83a6d40e46a5bc09f8f461b5 — Human approval is limited to registry-only dependency declaration and graph resolution for separate Gate B3 review; it does not authorize installation, import, tests, validator execution, or a substitute validator.
- [Phase 03]: Gate B3 must approve the exact skills-ref registry lock digest and artifact graph before any installation, import, test, or validator invocation. — The A3 approval permits only registry-only resolution; it does not authorize dependency use.
- [Phase 03]: Approved Gate B3 for exact uv.lock SHA-256 b87e7f1035d452ef1c5e66ca19e03e980398303fa8d3f99aec1822de75d85004. — Every later dependency-backed command requires a fresh dependency-free equality preflight; B3 does not authorize merge, publishing, source-repository execution, a substitute validator, or unapproved credentials.
- [Phase 03]: Use fixed OS secure-descriptor primitives inside the Gate B3 shell preflight — O_NOFOLLOW, FD_CLOEXEC, bounded retained-stream hashing, and high-resolution identity stability are exact without importing project or third-party code.
- [Phase 03]: Keep the Gate B3 authority registry closed to exactly the committed digest and uv.lock — No caller-supplied path, consumer, environment, or recomputed digest can substitute for the human-approved bytes.
- [Phase 03]: Reject every authority admission or identity failure before dependency execution — Missing, malformed, linked, unsafe, oversized, swapped, mutated, or byte-different inputs cannot reach the downstream command.
- [Phase 03]: Embed the complete strict WorkflowSpec and both verified Phase 2 anchors in WorkflowSpecAuthorityV1; wf-fingerprint-v1 remains only the selected workflow discriminator. — Prevent partial fingerprints from authorizing Phase 3 reuse.
- [Phase 03]: Keep configured Generator and Reviewer identities in CandidateExecutionAuthorityV1 and structurally exclude actual response model identities until later terminal evidence. — Only configured identities exist before lookup; actual identities are later evidence.
- [Phase 03]: Derive new lineage from numeric repository ID plus initial complete WorkflowSpec authority; retain it only when one canonical binding and verified prior evidence agree. — Prevent stale or heuristic remapping from aliasing unrelated Skills.
- [Phase 03]: Derive a bounded Agent Skills slug from normalized title plus a lineage-digest suffix, but never use title, slug, path, or content similarity as matching authority. — Provide readable stable names without turning presentation text into ownership authority.
- [Phase 03]: Bind candidate selection to the SHA-256 digest of the complete strict VerifiedRunChain projection, not a partial fingerprint or row identity.
- [Phase 03]: Use a mutation-free resolve_all seam to verify one completed Phase 2 chain once before deterministic max-three sibling derivation.
- [Phase 03]: Attach prior lineage only from an explicit exact full-fingerprint mapping; absence authorizes neither search nor inference.
- [Phase 03]: Treat WorkflowSpec workflow-level evidence as the complete authoritative registry against which every step reference path, blob SHA, and content hash is reconciled.
- [Phase 03]: Keep qualification weights, the 0.70 confidence floor, the 75 threshold, and every schema/policy version as code-owned constants with no runtime or caller override.
- [Phase 03]: Embed the selected full fingerprint, complete WorkflowSpecAuthorityV1, and complete CandidateExecutionAuthorityV1 directly in the report header and reject any stale or cross-candidate combination.
- [Phase 03]: Separate semantic artifact identity from rendered package identity — Request telemetry and exact rendered layout can change package evidence without rewriting semantic generation authority.
- [Phase 03]: Admit only one strict bounded Generator request — Generation uses one no-tools store-false Responses parse with SDK retries disabled and only verified structured authority.
- [Phase 03]: Promote complete Skill trees under one retained lock — Descriptor-relative private staging and whole-tree rename preserve the exact prior package on every pre-commit failure.
- [Phase 03]: Re-admit exact frozen package bytes with descriptor identity checks before and after official validation. — An official result is trustworthy only for the unchanged frozen package identity.
- [Phase 03]: Keep official skills-ref findings separate from SkillScout-owned deterministic local policies. — Capability isolation and policy versioning must remain independently auditable.
- [Phase 03]: Bind complete upstream and validator authorities directly into a canonically digested ValidationReportV1. — Later stages must detect omitted, swapped, reordered, or tampered validation evidence.
- [Phase 03]: Reviewer dynamic payload is confined to four freshly delimited user-role sections; the developer role is static policy only.
- [Phase 03]: ReviewAttestation records raw review evidence without eligibility; CandidateTerminalSummary alone owns the versioned derived decision.
- [Phase 03]: Every semantic Reviewer outcome is terminal; SDK retries remain disabled and each adapter invocation owns exactly one raw request.
- [Phase 03]: Keep Phase 3 in seven additive phase3_* tables without changing PIPELINE_PROFILES or the Phase 1/2 verify_run_chain trust path. — Preserve shipped verifier behavior while adding independently auditable candidate state.
- [Phase 03]: Completed exact-authority lookup uses only an existing retained lock, read-only descriptors, and query-only private :memory: SQLite. — Make exact reuse structurally incapable of filesystem or SQLite side effects.
- [Phase 03]: Resume accepts only a strict verified extension of an interrupted or running Phase 3 prefix. — Append auditable progress without accepting reordered, substituted, or cross-authority history.
- [Phase 03]: Completed projection precedes mutable state; only a verified clean miss may open mutable state. — Preserves zero-side-effect exact reuse and fail-closed projector integrity.
- [Phase 03]: Durable stage recovery payloads reuse phase3_artifacts and leave the seven-table schema unchanged. — Adds restart payloads without weakening Plan 11 completed projection.
- [Phase 03]: Recovery validates payload digest, result/checkpoint continuity, authority, and typed evidence before downstream calls. — Prevents missing, tampered, or cross-run payloads from triggering semantic work.
- [Phase 03]: Completed CLI reuse returns exact stored projections and never constructs mutable state or output writers.
- [Phase 03]: After a verified completed miss, mutable execution requires an absent or empty private output directory.
- [Phase 03]: Keep Phase 3 acceptance and validation-map gates standard-library-only, read-only, and independent of project imports. — These gates must fail closed before application or dependency imports.
- [Phase 03]: Bind release credit to checker-owned task commands, exact requirement inverse coverage, and a terminal Gate B3 postflight. — Agreement between mutable plans and the map alone is not independent evidence.
- [Phase 05]: Keep query text, ordering, pagination and 100/20 ceilings as code-owned literal policy. — Runtime input cannot widen discovery or semantic cost authority.
- [Phase 05]: Use numeric repository ID as discovery deduplication authority. — Owner and repository names are mutable provenance, not stable identity.
- [Phase 05]: Quarantine outcome-unknown semantic attempts separately from confirmed retryable outcomes. — Automatic replay cannot be proven duplicate-free after an indeterminate provider request.
- [Phase 05]: Bind one prior-root-linked state root to digest-derived objects and exactly three owner-specific SQLite paths with no pruning surface. — Audit and rebuild authority stays complete, path-closed and retention-preserving.
- [Phase 05]: Freeze Search results as one strict page observation plus a tuple of strict repository observations. — Raw provider dictionaries and discarded prose never cross the adapter boundary.
- [Phase 05]: Keep fixture, recorder, parser, and numeric-ID tests ordinary green while only named adapter behavior nodes strict-xfail. — Collection and unrelated defects remain hard failures, and unexpected adapter passes XPASS-fail.
- [Phase 05]: Synthesize malformed and oversized responses from bounded fixture instructions. — The repository retains a compact deterministic corpus instead of megabyte-scale provider bodies.
- [Phase 05]: Keep fixture, schema ownership, baseline workflow hash and canary checks ordinary green while only named missing production behavior is strict-xfail. — Collection, import, fixture and unrelated failures must remain hard failures in Wave 0.
- [Phase 05]: Use compact digest-only state fixtures and explicit provider-stage-transition crash matrices. — Avoid active databases, raw provider bodies and secrets while retaining complete deterministic acceptance coverage.
- [Phase 05]: Extend the existing GitHubReadClient and keep one serial REMOTE_READ capability rather than introduce a second GitHub client. — Preserves the verified fixed-host, capped-body, sanitized read boundary.
- [Phase 05]: Revalidate the complete reviewed query-set authority before constructing the exact Search request. — Prevents runtime query text or bypass-constructed models from widening discovery authority.
- [Phase 05]: Persist only strict self-hashed Search observations and discard provider prose, raw Link values, provider bodies and arbitrary headers. — Keeps untrusted content outside durable and diagnostic surfaces.
- [Phase 05]: Make unique contiguous reservation rows, not mutable counters, the sole 100/20 budget authority.
- [Phase 05]: Treat outcome-unknown semantic attempts as consumed and terminally non-replayable; only confirmed-retryable attempts may advance automatically.
- [Phase 05]: Keep complete canonical operations-owned facts authoritative and treat the SQLite snapshot as a verified disposable query index.
- [Phase 05]: Reject a valid SQLite snapshot that disagrees with its digest or JSON projection, while allowing corrupt or absent bytes to rebuild only from fully validated owned facts.
- [Phase 05]: Bind the state client to exactly refs/heads/skillscout-state with no general request, PR, reviewer, merge, deletion or arbitrary-ref capability. — Keep state persistence narrower than catalog publication authority.
- [Phase 05]: Admit recursive Git directory entries only when they are the exact structural prefixes required by the allowlisted state blobs. — Support valid Git recursive trees without hiding empty or unexpected subtrees.
- [Phase 05]: Accept state synchronization only after observed-parent force-false mutation and exact ref, commit, tree and blob reread. — Prevent lost updates and mutation-response lies from authorizing durable state.
- [Phase 05]: Only exact 429 provider rejection grants confirmed semantic retry authority; timeout, connection loss, 408, 5xx and unrecognized failures are outcome-unknown. — Ambiguous replay could duplicate a paid semantic effect.
- [Phase 05]: Keep refusal, incomplete and strict-schema failures as decided semantic results while treating post-send telemetry projection failures as outcome-unknown. — Business outcomes do not retry, and ambiguous local completion cannot safely replay.
- [Phase 05]: Each existing store remains the sole owner of its schema, canonical facts, replay, and full-chain verification. — Prevents the discovery coordinator from bypassing private transition and integrity validators.
- [Phase 05]: Bind compact owner envelopes, digest-addressed facts, and exactly three fixed database snapshots without private SQL duplication. — Keeps the state tree path-closed, content-addressed, and ownership preserving.
- [Phase 05]: Validate prospective bundle equality before writes and fresh three-store projection equality after rebuild. — No partial, swapped, stale, or cross-store-mismatched bundle can grant reuse authority.
- [Phase 05]: Bind semantic request, retry and terminal authority to exact self-hashed transition identity plus all three owner export digests. — A caller-provided label cannot prove the recorded attempt or remote three-store state.
- [Phase 05]: Grant restart idempotence only after a fresh full remote reread equals the deterministic prospective three-store bundle. — This closes crash windows without accepting local-only durability or ambiguous replay.
- [Phase 05]: Only confirmed-retryable semantic failures enter bounded automatic retry; outcome-unknown attempts are consumed and quarantined. — This prevents ambiguous OpenAI or DeepSeek effects from being replayed after a crash or transport uncertainty.
- [Phase 05]: Retain attempt_interrupted in the Phase 3 local compatibility ledger while operations state owns the semantic_outcome_unknown quarantine fact. — This preserves the verified Phase 3 chain schema without weakening the explicit remote quarantine authority.
- [Phase 05]: Require the exact three-store receipt before provider requests, retries, downstream stages, or terminal projection. — Local durability alone cannot authorize a semantic effect when the canonical operational state lives on the protected state branch.
- [Phase 05]: Keep unprotected discovery structurally incapable of receiving Phase 4, catalog credential, or remote publisher authority. — Preserve the authority-zone split before protected re-admission.
- [Phase 05]: Consume one semantic repository reservation across zero-to-three independently identified workflow paths. — Repository-level semantic cost remains non-refundable while sibling workflows retain separate authorities.
- [Phase 05]: Persist eligible output only as bounded exact-state locators and authorities requiring later protected re-admission. — Eligibility alone must not grant publication authority.
- [Phase 05]: Discovery and protected publication remain separate authority zones — Discovery cannot resolve catalog credentials or construct publication objects.
- [Phase 05]: Operations run identity is explicit and distinct from semantic execution identity — Durability checks must address the discovery reservation namespace exactly.
- [Phase 05]: Workflow terminal facts are authoritative for exact eligible-set reconstruction — Candidate aggregates cannot prove which workflow emitted each artifact.
- [Phase 05]: Discovery resumes from typed persisted prefixes — Search pages, candidates, reservations, workflow terminals and summaries must not replay after durable completion.
- [Phase 06]: Represent Wave 0 RED as exact named missing-contract failures — Collection and infrastructure failures must never satisfy the RED contract.
- [Phase 06]: Keep all Phase 6 release gates blocking when evidence is absent — Wave 0 cannot fabricate hosted, live, human, or report authority.
- [Phase 06]: Require transitive ownership reachability for every Phase 6 surface — Prevents missing owners and producer-consumer inversions before execution.
- [Phase 06]: Treat hosted run 30430010273 as a blocking failure because locked-toolchain verification failed before the network probe and artifact upload. — No bounded artifact exists, so D-24 kernel/OS denial remains unproven.
- [Phase 06]: Record exact run, source, workflow, job, and empty-artifact locators without inventing an artifact digest or inspecting raw logs. — Preserve a tamper-evident failure boundary without widening the approved evidence surface.
- [Phase 06]: Deny Plan 06-06 campaign credit until an authorized exact run produces bounded evidence revalidated into canonical operations state. — A skipped probe and zero artifacts cannot authorize campaign evidence.
- [Phase 06]: Preserve the historical DEEPSEEK_MODEL Flash alias — New live authority comes only from immutable DEEPSEEK_MODEL_BY_STAGE, so historical all-Flash evidence is not rewritten.
- [Phase 06]: Validate provider settings before credential lookup and stage-model pairs before HTTP — Invalid endpoint, key variable, or model identity must produce zero secret lookup and zero transport calls.
- [Phase 06]: Quarantine wrong actual DeepSeek model telemetry as semantic_outcome_unknown — Mismatched provider identity is ambiguous evidence and cannot authorize a business result or blind replay.
- [Phase 06]: Fix DeepSeek stage output caps at 8000, 6000, and 2000 tokens — Exact extraction, generation, and review budgets are part of the closed Phase 6 semantic policy while recorded OpenAI behavior stays unchanged.
- [Phase 06]: Persist every Phase 6 acceptance fact in one bounded operations_acceptance_facts table; do not create a fourth state owner.
- [Phase 06]: Project replay and changed-source intent separately from their post-publication completion facts so both immutable scopes coexist.
- [Phase 06]: Revalidate canonical JSON through the exact model registry and require post-parse byte equality before any fact receives authority.
- [Phase 06]: Restore a valid owned SQLite image byte-for-byte after JSON/projection agreement; rebuild corrupt database bytes only from canonical facts.
- [Phase 06]: Phase 6 acceptance uses distinct frozen capability types for nomination, locked campaigns, replay/update, attestations, and rebuild.
- [Phase 06]: Acceptance CLI authority excludes runtime model, endpoint, catalog, ref, secret, cleanup, merge, approval, and ready-for-review selection.
- [Phase 06]: Acceptance fixes the catalog to alexzhu0/skillscout-catalog-test and validates immutable facts before environment-backed credentials.
- [Phase 06]: Recognize only direct python -m skillscout, inline SkillScout imports, and python tools/*.py as authoritative workflow entry forms — Every unknown acquisition or invocation source must fail closed before Gate B4.
- [Phase 06]: No current Phase 6 workflow job holds fixed-catalog credentials: the nonfunctional `fresh_gate_b4`/`value_publication` scaffold was removed pending a separately reviewed implementation. Nomination, semantic, attestation, rebuild, and isolation jobs retain separate minimum authority zones.
- [Phase 06]: Admit the pinned tool only when its program token is exactly `uv` and version token is exactly `0.11.29`, with an optional non-empty parenthesized build-metadata suffix. — Official build metadata must not be rejected, and metadata cannot replace either authoritative token.
- [Phase 06]: Materialize exact CPython 3.13.14 under canonical `${GITHUB_WORKSPACE}/.tools/python` in every authoritative job. — The locked venv and managed runtime cross into network-none containers only through the same-path read-only repository mount; hosted toolcache paths and external Python mounts are no longer runtime authority.
- [Phase 06]: Install the current locked SkillScout project in all 15 freshly recreated authoritative venvs. — A dependency-only venv cannot import the src-layout application, and the `--no-install-project` mutation must make both isolated import and the adversarial control return 1.
- [Phase 06]: Hosted adversarial evidence is produced only by an installed-package deterministic runner with a closed 25-node registry; pytest is a development consumer and cannot own report lifecycle. — This separates scenario/assertion failure from final report-write failure without widening network, path, credential, publication, or canonical-state authority.
- [Phase 06]: Bind the deterministic runner to seven exact production-embedded injection payloads and independent SHA-256 identities, then derive observed results through ordered in-memory application seams. — Static policy projection or synthetic-name bytes alone cannot prove the committed inert corpus crossed its intended barriers.
- [Phase 06]: Promote only the validated offline evidence JSON digest — Retain the ZIP digest as non-authoritative transport metadata and avoid promoting archive packaging as fact authority.
- [Phase 06]: Replay verified pre-Phase-6 operations facts through the current owner before CAS — Preserve every prior fact digest while adding the acceptance projection schema required by the current owner.
- [Phase 06]: Persist exactly two offline acceptance facts — Only acceptance_hosted_isolation_capability and acceptance_offline_adversarial_run are authorized; no third acceptance fact is admitted.
- [Phase 06]: Search nominations remain role-neutral; evaluator roles enter only through the human-locked manifest.
- [Phase 06]: Historical acceptance evidence rebuilds from its immutable exact commit object rather than the mutable current state head.
- [Phase 06]: Strict canonical manifest JSON normalizes arrays to tuple contracts before validation without relaxing digests or fields.
