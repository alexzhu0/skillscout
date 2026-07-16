# Phase 1: Auditable Dry-Run Spine — Research

**Researched:** 2026-07-16
**Domain:** Python CLI walking skeleton, typed stage contracts, SQLite checkpoints, content-addressed JSON audit, dry-run side-effect isolation
**Confidence:** HIGH for official-library behavior; MEDIUM for the proposed project-specific decomposition

## User Constraints

No Phase 1 `CONTEXT.md` exists because the user explicitly chose to skip discuss-phase and plan directly from the approved project artifacts.

The following approved constraints are locked for this phase:

- Phase 1 delivers an auditable dry-run spine using deterministic fixtures; it does not connect to live GitHub or OpenAI services.
- The pipeline contains the named stage sequence Scout → Filter → Reader → Extractor → Qualifier → Generator → Validators → Reviewer → Publisher plan.
- Every stage emits versioned structured data with stable IDs, timestamps, input/output hashes, attempts, and applicable prompt/policy/model versions (`OPS-01`).
- A failed run can resume from its latest successful checkpoint; dry-run can produce a publication plan but cannot create a branch, commit, PR, or other remote side effect (`OPS-04`).
- Phase 1 is a vertical MVP Walking Skeleton: one CLI interaction must exercise the complete stage path, one real SQLite write/read must occur, and a documented local command must prove the slice end-to-end.
- Candidate repository content is not part of Phase 1. The fixture represents already-bounded structured stage payloads and must not be mistaken for permission to execute external code.
- Human control, no automatic merge, no candidate code execution, no unauthorized secrets, deterministic-first design, and stage isolation from `AGENTS.md` remain mandatory.

## Summary

Phase 1 should build the smallest real operational spine rather than all future domain models. The recommended happy path is a `skillscout dry-run` CLI command that loads a size-bounded, repository-owned JSON fixture, creates a run in a real local SQLite database, moves a typed envelope through all nine stage names, persists one content-addressed manifest per stage, and writes a final `publication-plan.json`. The final observable state is `planned_not_published`; no GitHub or OpenAI adapter exists in the runtime registry for this phase.

Use a `src/` layout, Python 3.13, Pydantic models, stdlib `sqlite3`, canonical JSON plus SHA-256, pytest, Ruff, and a uv lockfile. Pytest recommends a `src` layout for new projects and uv uses `pyproject.toml` plus a checked-in cross-platform `uv.lock`. [CITED: https://docs.pytest.org/en/stable/explanation/goodpractices.html] [CITED: https://docs.astral.sh/uv/guides/projects/]

The highest-risk implementation mistake is making `--dry-run` a boolean checked only inside a future Publisher. The dry-run boundary must be structural: Phase 1's composition root only constructs no-effect fixture processors, local-state ports and a `PublicationPlanner`; it does not construct or expose a remote adapter. A `SideEffectPolicy` permits only `none` and `local_state`, and an end-to-end test patches outbound socket connection attempts to fail. [ASSUMED: project-specific defense-in-depth design]

**Primary recommendation:** implement three vertical refinements—happy-path walking skeleton, checkpoint/resume ledger, and fail-closed side-effect/state-integrity handling—while keeping live GitHub, OpenAI, state-branch persistence, and real Draft PRs outside Phase 1.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| CLI parsing and user-facing run summary | `skillscout.cli` | `skillscout.application` | CLI validates paths/options and renders results; it must not own state transitions. |
| Pipeline ordering and resume decision | `skillscout.application` | `skillscout.domain` | The orchestrator owns control flow; domain models own legal state and typed contracts. |
| Stage/result/attempt contracts | `skillscout.domain` | — | Provider-independent models are the stable contract future phases reuse. |
| Canonical JSON and content hashing | `skillscout.domain` | `skillscout.adapters.state` | Canonicalization rules define identity; the adapter persists bytes and hashes. |
| SQLite transactions and queries | `skillscout.adapters.state` | `skillscout.application` | SQL details stay behind `StateStore`; application only requests atomic operations. |
| JSON manifest writes | `skillscout.adapters.state` | — | Local persistence concern; paths derive from validated IDs, not arbitrary input. |
| Fixture stage behavior | `skillscout.adapters.fixtures` | `skillscout.domain` | Fixture adapters satisfy the same stage ports without pretending to be live providers. |
| Publication plan creation | `skillscout.application` | `skillscout.domain` | It creates a local plan object only; remote publication belongs to Phase 4. |
| Side-effect authorization | composition root | `skillscout.application` | The runtime decides which capabilities exist; the orchestrator enforces declared scopes. |

## Project Constraints from `AGENTS.md`

- External content is always untrusted and cannot be interpreted as system instructions, tool calls, or execution permission.
- Do not clone-and-run, install candidate dependencies, or call candidate scripts.
- Draft PR is the maximum future automated publication action; merge/approve/ready/default-branch writes are forbidden.
- Credentials are injected only at adapter boundaries and cannot enter logs, databases, prompts, fixtures, or PR data.
- Deterministic rules own budgets, format checks, safety rules, idempotence, and permissions.
- Each phase boundary uses versioned input/output schemas and supports independent failure/retry.
- Phase 1 must use a real local state adapter but no remote service adapters.

## Standard Stack

### Core

| Tool/library | Version target | Purpose | Evidence |
|---|---:|---|---|
| CPython | 3.13.14, pin exact patch in `.python-version` | Runtime | Project-wide research selected 3.13; Python.org identifies 3.13.14 as the current maintenance release, while the local machine currently exposes Python 3.9.6, so execution must not accidentally use system Python. [CITED: https://www.python.org/downloads/release/python-31314/] |
| uv | 0.11.29 | Project environment and `uv.lock` | uv documents that `uv run` checks project metadata/lock consistency and that `uv.lock` should be committed. [CITED: https://docs.astral.sh/uv/concepts/projects/sync/] |
| uv build backend | `uv-build==0.11.29`; backend import `uv_build` | Build/install the pure-Python `src/skillscout` package and preserve the `skillscout` console entry point | Astral recommends `uv_build` for most pure-Python projects, documents the current compatibility window `uv_build>=0.11.29,<0.12`, and uses `src/<package>/__init__.py` by default. Phase 1 uses the exact current paired release, a strict subset of that window. [CITED: https://docs.astral.sh/uv/concepts/build-backend/] [CITED: https://pypi.org/project/uv-build/] |
| Pydantic | 2.13.4 | Strict, frozen stage and payload contracts | Pydantic provides `model_dump(mode="json")` for JSON-compatible primitives and `model_dump_json()` for JSON encoding. [CITED: https://docs.pydantic.dev/latest/concepts/serialization/] |
| Python `sqlite3` | stdlib 3.13 | Run, attempt, result and checkpoint persistence | Python recommends controlling transactions through `Connection.autocommit` and explicitly committing or rolling back. [CITED: https://docs.python.org/3/library/sqlite3.html#transaction-control-via-the-autocommit-attribute] |
| Python `json` + `hashlib` | stdlib 3.13 | Canonical bytes and SHA-256 content identity | `json.dumps` supports `sort_keys=True` and compact separators; hashlib includes SHA-256. [CITED: https://docs.python.org/3/library/json.html] [CITED: https://docs.python.org/3/library/hashlib.html] |

### Development

| Tool/library | Version target | Purpose | Evidence |
|---|---:|---|---|
| pytest | 9.1.1 | Unit, contract, CLI and recovery tests | PyPI shows 9.1.1 with Trusted Publishing provenance and Python ≥3.10. [CITED: https://pypi.org/project/pytest/] |
| Ruff | 0.15.21 | Formatting and linting | Official PyPI/docs identify Ruff as a production-stable Python linter/formatter with `pyproject.toml` configuration. [CITED: https://pypi.org/project/ruff/] |

Do not add HTTPX, OpenAI, PyYAML, GitHub clients, a migration framework, a DI framework, a workflow engine, or a logging vendor in Phase 1. Those packages do not contribute to the approved Phase 1 user story.

### Installation and lock strategy

The intended execution setup is:

```text
uv 0.11.29 available
→ uv python pin 3.13.14
→ pyproject.toml declares `[build-system] requires = ["uv_build==0.11.29"]`, `build-backend = "uv_build"`
→ `[project.scripts] skillscout = "skillscout.cli:main"`, pydantic, and dev group pytest/ruff
→ uv lock
→ all task/test commands use uv run --locked ...
```

Do not use a floating `uv run` in verification because it may update the lockfile automatically; `--locked` causes an error when project metadata and `uv.lock` disagree. [CITED: https://docs.astral.sh/uv/concepts/projects/sync/]

The PyPI distribution name is canonically displayed as `uv-build`; the PEP 518 requirement and backend import use `uv_build`, as shown by Astral's official configuration. The official range is `>=0.11.29,<0.12`, but Phase 1 narrows it to `==0.11.29` so the build dependency is exactly the release reviewed at the mandatory checkpoint. The `uv 0.11.29` executable bundles a compatible copy and may use it for uv-driven builds; declaring the requirement remains necessary for standard package metadata and non-uv build frontends. `uv_build` is appropriate because this phase is pure Python and uses the backend's default `src/skillscout` layout. [CITED: https://docs.astral.sh/uv/concepts/build-backend/]

## Package Legitimacy Audit

The GSD package-legitimacy seam returned `SUS` for every checked Python package because PyPI weekly-download data was unavailable and several current releases were recent. Official PyPI pages independently show verified project ownership/source links; nevertheless, the plan must include a blocking `checkpoint:human-verify` before installation because GSD policy does not permit overriding a `SUS` verdict automatically.

| Package | Registry evidence | Seam verdict/reason | Official provenance | Disposition |
|---|---|---|---|---|
| `uv==0.11.29` | Exists; released 2026-07-15 | SUS: too-new, unknown-downloads | PyPI verified project links and Astral maintainers [CITED: https://pypi.org/project/uv/] | Retain; human verifies name/version/source before install |
| `uv-build==0.11.29` (`uv_build` in `[build-system]`) | Exists; released 2026-07-15; Python >=3.8 including 3.13 | SUS: too-new, unknown-downloads | Astral's official docs recommend the backend and its PyPI project has verified repository links plus Trusted Publishing [CITED: https://docs.astral.sh/uv/concepts/build-backend/] [CITED: https://pypi.org/project/uv-build/] | Retain; human verifies distribution/backend names, exact version and Astral source before build/install |
| `pydantic==2.13.4` | Exists; released 2026-05-06 | SUS: unknown-downloads | PyPI verified Pydantic owner/source [CITED: https://pypi.org/project/pydantic/] | Retain; human verifies name/version/source before install |
| `pytest==9.1.1` | Exists; released 2026-06-19 | SUS: too-new, unknown-downloads | PyPI Trusted Publishing provenance from `pytest-dev/pytest` [CITED: https://pypi.org/project/pytest/] | Retain; human verifies name/version/source before install |
| `ruff==0.15.21` | Exists; released 2026-07-09 | SUS: too-new, unknown-downloads | PyPI verified Astral repository/maintainers [CITED: https://pypi.org/project/ruff/] | Retain; human verifies name/version/source before install |

**Packages removed due to SLOP:** none.
**Packages flagged SUS:** uv, uv-build, pydantic, pytest, ruff.
**Planning consequence:** the first plan is non-autonomous until a human approves the exact table above; installation and lock generation occur only afterward.

**Runtime provenance:** the same checkpoint must also confirm the official CPython `3.13.14` release before uv downloads that interpreter. Python is not a PyPI package and therefore was not part of the package-legitimacy seam, but the exact runtime pin is still an external supply-chain input. [CITED: https://www.python.org/downloads/release/python-31314/]

## Architecture Patterns

### System Architecture Diagram

```text
CLI: skillscout dry-run --fixture ... --state ... --output ...
        │ validate fixture type/size + construct internal paths + execution_mode=dry_run
        ▼
PipelineRunner
        │ creates Run + first StageAttempt in SQLite
        ▼
Fixture processors, one typed hop at a time
Scout → Filter → Reader → Extractor → Qualifier → Generator → Validators → Reviewer
        │ each hop: canonical result core → output SHA-256; full envelope → manifest SHA-256
        │           → SQLite result + content-addressed JSON manifest
        │ failure: mark attempt failed; preserve last successful checkpoint
        ▼
PublicationPlanner
        │ SideEffectPolicy permits none + local_state only
        ▼
publication-plan.json + RunSummary(status=planned_not_published)

No GitHub client · No OpenAI client · No subprocess of candidate code · No remote adapter
```

### Recommended Project Structure

```text
pyproject.toml
uv.lock
.python-version
src/skillscout/
├── __init__.py
├── cli.py
├── application/
│   ├── pipeline.py
│   └── ports.py
├── domain/
│   ├── enums.py
│   ├── models.py
│   └── canonical.py
└── adapters/
    ├── fixtures.py
    └── state.py
tests/
├── fixtures/pipeline/approved.json
├── test_cli_dry_run.py
├── test_pipeline_resume.py
├── test_stage_contracts.py
└── test_side_effect_policy.py
```

Keep the first slice compact. If a module remains under roughly one screen and has a single responsibility, do not split it merely to mirror every future stage.

### Pattern 1: Immutable versioned envelopes

Use strict, frozen Pydantic models with `extra="forbid"`. Separate stable result identity from volatile attempt metadata. Pydantic's current `ConfigDict` exposes `extra`, `frozen`, and `strict` explicitly. [CITED: https://docs.pydantic.dev/latest/api/config/]

- `StageEnvelope`: stable `result_id`, `schema_version`, `run_id`, `stage`, `subject_id`, `produced_by_attempt_id`, `attempt_no`, `created_at`, typed `payload`, `input_hash`, `output_hash`, `manifest_hash`, `producer_version`, and explicit nullable `prompt_version`, `policy_version`, `model_id`.
- `StageAttempt`: `attempt_id`, `run_id`, `subject_id`, `stage`, `attempt_no`, `status`, `started_at`, `finished_at`, `request_id`, `latency_ms`, nullable structured `token_usage`, sanitized `error_code`/`error_summary`, and `retryable`.
- `Run`: `run_id`, `execution_mode`, `status`, `config_hash`, timestamps.
- `PublicationPlan`: local target paths and artifact hashes only; no token, API route, branch write method, or merge field.

`result_id` is deterministically derived from stage, subject, input hash, producer version and output hash. The envelope's attempt reference must match the `StageAttempt.artifact_ref` back to that result. All timestamps use UTC RFC 3339. Timestamps, attempt numbers, request IDs and run-local IDs do not participate in `output_hash`; otherwise identical domain results would never hash identically. For deterministic fixture stages, non-applicable model/prompt fields remain explicit `null` values rather than invented provenance.

### Pattern 2: One canonicalization function

`canonical_json_bytes(value)` should be the only JSON-to-bytes path, but callers must use three explicit, non-self-referential preimages:

1. Validate with Pydantic.
2. Call `model_dump(mode="json", exclude_none=False)`.
3. Encode with `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`.
4. UTF-8 encode.
5. Hash with SHA-256 and prefix stored values with `sha256:`.

The preimages are:

- `input_hash`: a canonical typed `StageInput` containing the predecessor `output_hash` (or normalized initial fixture subject for Scout), execution mode, effective config hash, and every stage-relevant policy/prompt/model version. This prevents stale reuse when behavior changes without payload changes.
- `output_hash`: `{schema_version, stage, subject_id, producer_version, prompt_version, policy_version, model_id, payload}` only. It explicitly excludes `result_id`, all timestamps, attempts, and every hash field.
- `manifest_hash`: the complete immutable `StageEnvelope` except `manifest_hash` itself. It therefore covers the run/attempt link, `created_at`, `input_hash`, `output_hash`, and `result_id` without circularity.

Manifest paths use `manifest_hash`, not `output_hash`. Store `sha256:<hex>` in the envelope/DB, but use only validated lowercase `<hex>` as the filename so the path is portable. Derive the manifest root from the state DB path (for example `<db-stem>.manifests/<stage>/<hex>.json`), never from fixture-supplied IDs. Two independent executions may have the same semantic `output_hash` but different run/attempt/timestamp metadata and thus different manifest hashes; they must never overwrite different bytes under one content address.

Python documents sorted keys, compact separators, strict NaN control, and warnings about resource exhaustion from untrusted JSON; fixture input therefore also needs a byte cap before parsing. [CITED: https://docs.python.org/3/library/json.html]

### Pattern 3: Transactional result/checkpoint write

Use explicit SQLite transaction semantics with `autocommit=False`. For each stage attempt:

1. Insert/transition attempt to `running`; commit.
2. Execute the deterministic processor outside the DB transaction.
3. Begin a transaction that inserts the immutable stage result, marks attempt `succeeded`, and advances the run checkpoint together.
4. On processor error, record a sanitized structured failure in a separate transaction; never advance the checkpoint.

The JSON manifest should be written to a temporary sibling on the same filesystem, flushed and `fsync`ed, then atomically replaced before the DB transaction stores its final path/hash. On POSIX, sync the parent directory after replacement where supported. At resume, verify the full manifest hash and the embedded output hash before trusting the checkpoint. Python exposes `os.fsync`; `os.replace` performs replacement and is atomic when successful on the same filesystem. [CITED: https://docs.python.org/3.13/library/os.html#os.fsync] [CITED: https://docs.python.org/3.13/library/os.html#os.replace]

SQLite must enforce foreign keys plus uniqueness for `(run_id, subject_id, stage, attempt_no)`, the reusable stage key, and `manifest_hash`. A crash between manifest replacement and DB commit can leave an unreferenced manifest, which is safe and may be garbage-collected later; the reverse ordering is forbidden because it can leave a committed checkpoint pointing at absent bytes.

### Pattern 4: Resume by deterministic stage key

The reusable stage key is:

```text
(subject_id, stage_name, input_hash, producer_version)
```

On resume:

- Re-read the last `succeeded` result in stage order.
- Recompute and verify its manifest hash.
- If the next stage has a matching successful key, reuse it.
- If an attempt is left `running` from interruption, mark it `abandoned` and create a new attempt number.
- Apply a versioned retry policy with a default maximum of three attempts for the same reusable stage key; only allowlisted transient error codes may be retried, and exhaustion becomes the structured terminal error `retry_exhausted`.
- If a manifest is missing/corrupt or a stage transition is illegal, fail closed with `state_integrity_error`; do not silently restart from raw input.

### Pattern 5: Capability-based dry-run composition

Do not implement dry-run as “call the real publisher with a flag.” Define:

- `EffectScope`: `none`, `local_state`, `remote_read`, `remote_write`.
- `SideEffectPolicy.allowed_scopes` for Phase 1: `none`, `local_state`.
- Every adapter declares an effect scope at registration.
- `build_dry_run_runtime()` only receives fixture processors, SQLite/manifest state, clock, and publication planner.
- The application refuses startup if any `remote_read` or `remote_write` adapter is present. This is stricter than the eventual production dry-run requirement and preserves Phase 1's approved no-live-provider scope.

The end-to-end test patches `socket.socket.connect` to raise and verifies the approved fixture still completes. This is defense in depth; the stronger proof is that the composition root contains no GitHub/OpenAI/remote publisher implementation.

### Pattern 6: CLI as the Walking Skeleton interaction

The CLI is Phase 1's user interface. Define two commands:

- `skillscout dry-run --fixture PATH --state PATH --output DIR [--fail-after STAGE]`
- `skillscout inspect-run RUN_ID --state PATH --format json`

Observable happy-path output contains `run_id`, `status`, `last_stage`, `reused_stage_count`, `publication_plan_path`, and `remote_writes_attempted: 0`. Use exit code `0` for completed dry-run, `1` for pipeline/integrity failure, and argparse's `2` for invalid CLI input.

`--fail-after` is a fixture-only interruption seam and must be rejected unless execution mode is dry-run. It exits after the named stage has succeeded and its checkpoint is durable, marks the run `interrupted`, and does not invoke the next processor; rerunning without the flag proves checkpoint resume without killing a process nondeterministically. Separate adapter tests exercise failed `StageAttempt` records, allowlisted transient failures, the three-attempt ceiling, and `retry_exhausted`.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Runtime data validation | Ad hoc nested-dict checks | Pydantic strict/frozen models | One schema source for validation and serialization. |
| Dependency resolution | Custom requirements scripts | uv + checked-in `uv.lock` | Reproducible environment and locked commands. |
| Persistence framework | ORM/migration dependency | stdlib `sqlite3` with a small explicit schema | Only three/four tables; SQL is part of the audit contract. |
| Workflow engine | Generic DAG or Agent framework | Ordered `PipelineStage` enum + runner | Stage order is fixed and small in Phase 1. |
| Hash encoding | Model-specific serializers | One canonical JSON function | Avoid inconsistent identities across stages. |
| Remote-capability mocking | Fake GitHub/OpenAI clients with live capability-shaped methods | Omit every remote adapter entirely | Absence is stronger than a flag on a dangerous adapter. |
| Crash recovery | Pickle or in-memory retry | SQLite attempts + JSON manifests | Pickle is opaque and unsafe for untrusted data; manifests are inspectable. |

## Common Pitfalls

1. **Using timestamps inside payload hashes.** Same fixture produces different hashes, breaking idempotence tests.
2. **Hashing the envelope including `output_hash` itself, or storing timestamp-varying envelopes under `output_hash`.** Use the three explicit preimages and address manifests by `manifest_hash`.
3. **Writing DB checkpoint before manifest durability.** A crash leaves the DB pointing to a missing result.
4. **Long SQLite transactions around stage processing.** Locks remain open while code runs; keep processor execution outside state transactions.
5. **Treating `running` as resumable success.** An interrupted attempt must become `abandoned` and be retried with a new attempt.
6. **Calling future provider adapters in the walking skeleton.** Phase 1 fixtures are local; no network API belongs in this slice.
7. **A dry-run boolean in the Publisher.** The dangerous capability still exists and can ignore the flag.
8. **Persisting arbitrary exception strings.** They can contain paths or secrets; map to allowlisted error codes and sanitized summaries.
9. **Unbounded JSON fixtures.** Python warns that malicious JSON can consume CPU/memory; enforce a small fixture byte cap before parsing. [CITED: https://docs.python.org/3/library/json.html]
10. **Running tests against the repository root instead of the installed package.** Use `src/` layout and `uv run --locked pytest`; pytest recommends src layout for new projects. [CITED: https://docs.pytest.org/en/stable/explanation/goodpractices.html]

## Security Threat Model Inputs

Security enforcement is active at OWASP ASVS Level 1 and blocks unresolved high-severity threats. Each plan must include a `<threat_model>` register.

| Threat | STRIDE | Severity | Required mitigation |
|---|---|---:|---|
| Fixture is a symlink/non-regular file, changes during read, or JSON is oversized | Tampering / DoS | high | Treat the operator-selected fixture as untrusted data: reject symlinks/non-regular files, enforce a byte cap before parse, read from one opened descriptor, then apply strict schema. |
| Manifest path derived from attacker-controlled IDs | Tampering | high | Validate IDs/enum names and construct paths internally. |
| Tampered/missing manifest is accepted during resume | Tampering / Repudiation | high | Recompute hash, compare DB metadata, fail closed. |
| Exception or payload leaks secrets into state/output | Information Disclosure | high | Allowlists for persisted fields; sanitized `error_code`/summary only. |
| Dry-run runtime obtains remote read/write or network capability | Elevation of Privilege | critical | Capability omission plus `SideEffectPolicy` startup rejection and socket sentinel test. |
| Package name/version substitution | Tampering | high | Human verification checkpoint, exact versions, lockfile, `uv run --locked`. |
| Replayed stage with incompatible producer/schema version | Tampering | medium | Stage key includes producer version; schema version validated before reuse. |

## Validation Architecture

### Test layers

| Layer | Purpose | Target runtime |
|---|---|---:|
| Contract unit tests | Strict schemas, non-self-referential hash preimages, stable output hashes, legal transitions | <1 s |
| State adapter tests | SQLite constraints/transaction outcomes, manifest/output hash integrity, abandoned attempts | <2 s |
| Application tests | Ordered stages, checkpoint reuse, retry allowlist/exhaustion, fail-closed corruption | <3 s |
| CLI walking-skeleton test | Subprocess-like CLI invocation from fixture to publication plan and inspect output | <5 s |
| Security tests | Path/size limits, sanitized errors, remote-read/write registration and socket sentinel | <3 s |

### Required fixtures

- `approved.json`: one subject traverses all stages to `planned_not_published`.
- `fail-after-generator.json` or the `--fail-after generator` seam: first run fails after a known successful checkpoint; second run resumes and reuses prior results.
- `invalid-extra-field.json`: strict schema rejects unknown data.
- generated oversized JSON in test temp directory: size gate rejects before parse.
- tampered manifest copy: resume detects content hash mismatch.
- persisted transient failures at the retry ceiling: the next attempt is rejected as `retry_exhausted` without invoking the processor.

### Sampling policy

- After every task: run the narrow test file named in the task's `<automated>` verification plus Ruff on touched Python paths.
- After every plan: run `uv run --locked pytest -q` and `uv run --locked ruff check .`.
- Before Phase 1 verification: run full pytest, Ruff, `uv lock --check`, and two CLI demonstrations (happy path; fail then resume).
- No watch mode. Target full feedback latency is under 15 seconds on local fixture data.

### Nyquist mapping guidance

- `OPS-01` needs automated coverage for schema rejection, stable/non-circular hashes, all required nullable provenance and attempt telemetry fields, persisted attempts/results, and inspectable ledger output.
- `OPS-04` needs automated coverage for failure injection, allowlisted finite retry plus exhaustion, checkpoint reuse, publication-plan-only output, zero remote reads/writes, and fail-closed state corruption.
- No behavior should remain manual-only except the initial package legitimacy checkpoint required by the GSD seam.

## Planning Recommendations

Use three sequential plans:

1. **Walking Skeleton:** human package verification checkpoint, project scaffold, failing CLI test, then the thinnest real fixture→SQLite→publication-plan path.
2. **Checkpoint/Resume Ledger:** immutable envelopes, explicit non-circular hashes, transactional manifests/SQLite attempts, bounded retry, inspect command, failure injection and resume tests.
3. **Fail-Closed Dry-Run Hardening:** capability registry/policy, remote-read/write rejection, path/size/error sanitization, manifest corruption detection, full acceptance commands.

Each plan should contain 2–3 tasks and a complete vertical refinement. Plans are sequential because Plan 2 refines the skeleton's contracts/state and Plan 3 hardens the composed runtime.

## Deferred to Later Phases

- Live GitHub Search, Repository Contents, Licenses, rate limits, and source reading (Phases 2/5).
- OpenAI requests and real semantic extraction/generation/review (Phases 2/3).
- Agent Skills validation and actual Skill directories (Phase 3).
- GitHub App, branches and Draft PR API (Phase 4).
- `skillscout-state` branch persistence and GitHub Actions schedules (Phase 5).
- Multi-repository real-world acceptance (Phase 6).

## Sources

- [uv project workflow](https://docs.astral.sh/uv/guides/projects/)
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [uv build backend](https://docs.astral.sh/uv/concepts/build-backend/)
- [Pydantic serialization](https://docs.pydantic.dev/latest/concepts/serialization/)
- [Pydantic model configuration](https://docs.pydantic.dev/latest/api/config/)
- [Python sqlite3 transaction control](https://docs.python.org/3/library/sqlite3.html#transaction-control-via-the-autocommit-attribute)
- [Python JSON](https://docs.python.org/3/library/json.html)
- [Python hashlib](https://docs.python.org/3/library/hashlib.html)
- [Python `os.replace`](https://docs.python.org/3/library/os.html#os.replace)
- [Python `os.fsync`](https://docs.python.org/3.13/library/os.html#os.fsync)
- [Python 3.13.14 release](https://www.python.org/downloads/release/python-31314/)
- [pytest good integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [Python Packaging: src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [uv on PyPI](https://pypi.org/project/uv/)
- [uv-build on PyPI](https://pypi.org/project/uv-build/)
- [Pydantic on PyPI](https://pypi.org/project/pydantic/)
- [pytest on PyPI](https://pypi.org/project/pytest/)
- [Ruff on PyPI](https://pypi.org/project/ruff/)

## RESEARCH COMPLETE

Phase 1 can be planned without further product decisions. The only execution-time human checkpoint is verification of the exact CPython runtime plus five external package identities/versions—including the `uv-build` distribution / `uv_build` backend-name mapping—before build or installation.
