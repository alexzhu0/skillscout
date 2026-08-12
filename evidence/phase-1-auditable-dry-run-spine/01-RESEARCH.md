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

**Primary recommendation:** implement four sequential waves—verified toolchain/two supply-chain gates, happy-path walking skeleton, checkpoint/resume ledger, and fail-closed side-effect/state-integrity hardening—while keeping live GitHub, OpenAI, state-branch persistence, and real Draft PRs outside Phase 1. The toolchain split preserves the 2–3-task plan limit without collapsing either human gate into automation.

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

The local audit found no `uv` executable and only system Python `3.9.6`; neither is an acceptable fallback. Bootstrap is therefore a supply-chain workflow with two blocking human gates, not an implicit prerequisite.

**Gate A — approve the toolchain and direct declarations.** Before an external executable is installed or run, the reviewer records and approves:

- host tuple `Darwin/aarch64` (a different host must stop for its own artifact review);
- immutable Astral uv release `0.11.29`, release commit `901092ee11a89ba287f274e3c6e3a2e18ec2fba2`, asset `uv-aarch64-apple-darwin.tar.gz`, official SHA-256 `61c04acc52a33ef0f331e494bdfbedcdb6c26c6970c022ed3699e5860f8930e3`, and the GitHub artifact-attestation result;
- upstream language identity `CPython 3.13.14`, released by the Python project on 2026-06-10;
- **distributed runtime identity**, separately: immutable Astral `python-build-standalone` release/build `20260623`, asset `cpython-3.13.14+20260623-aarch64-apple-darwin-install_only_stripped.tar.gz`, exact URL `https://github.com/astral-sh/python-build-standalone/releases/download/20260623/cpython-3.13.14%2B20260623-aarch64-apple-darwin-install_only_stripped.tar.gz`, and SHA-256 `795a5aeeb050f00aa8a2214d779bad9f1b9113edb6923317a80c042a11a087d7`, as selected by uv `0.11.29`'s bundled download metadata for `cpython@3.13.14` on Darwin/aarch64;
- direct declarations `uv-build==0.11.29`, `pydantic==2.13.4`, `pytest==9.1.1`, and `ruff==0.15.21`, including owner/repository checks from the package-legitimacy table.

These values come from the uv release's fixed official download metadata and matching immutable `python-build-standalone` release; Gate A re-verifies them rather than resolving a floating runtime. [CITED: https://raw.githubusercontent.com/astral-sh/uv/901092ee11a89ba287f274e3c6e3a2e18ec2fba2/crates/uv-python/download-metadata.json] [CITED: https://github.com/astral-sh/python-build-standalone/releases/tag/20260623]

Python.org establishes the upstream CPython release but is **not** the provenance of the managed binary: Python does not publish the distributable binaries used by uv; `uv python install` obtains CPython distributions from Astral's `python-build-standalone`, and available download records are bundled in each uv release. The Gate A record must include both identities and may not substitute the Python.org macOS installer's checksum for the Astral asset checksum. [CITED: https://www.python.org/downloads/release/python-31314/] [CITED: https://docs.astral.sh/uv/guides/install-python/] [CITED: https://docs.astral.sh/uv/reference/cli/#uv-python-install]

Only after Gate A approval may the deterministic bootstrap proceed:

1. Download the fixed uv archive and `.sha256` from `https://releases.astral.sh/github/uv/releases/download/0.11.29/`, require `shasum -a 256 -c uv-aarch64-apple-darwin.tar.gz.sha256` to pass, and verify the release attestation with `gh attestation verify <archive> --repo astral-sh/uv` only if that `gh` executable is already part of the operator's trusted base; the official checksum remains the mandatory integrity check. Then extract to a repository-local ignored `.tools/uv-0.11.29/`. Never pipe an installer to a shell, invoke `uv self update`, modify a shell profile, or fall back to a package-manager/system uv. The immutable release publishes the platform archive, checksum and attestation instructions. [CITED: https://github.com/astral-sh/uv/releases/tag/0.11.29]
2. Put only that verified uv directory at the front of the current task shell's `PATH`; assert `command -v uv` resolves inside `.tools/uv-0.11.29/` and `uv --version` reports release `0.11.29` (and commit prefix `901092e` when the build emits commit metadata). Any other version/path stops execution.
3. Stage the Gate-A-approved `python-build-standalone` asset under a local `file://` mirror, require SHA-256 `795a5aeeb050f00aa8a2214d779bad9f1b9113edb6923317a80c042a11a087d7` before extraction, and set `UV_PYTHON_CPYTHON_BUILD=20260623`. Run exact `uv python install cpython@3.13.14` with the local mirror, a repository-local `UV_PYTHON_INSTALL_DIR`, and `--no-bin`; uv officially supports a local directory mirror. [CITED: https://docs.astral.sh/uv/reference/cli/#uv-python-install] [CITED: https://docs.astral.sh/uv/reference/environment/#uv_python_cpython_build]
4. Resolve the interpreter with `uv python find --managed-python --no-python-downloads cpython@3.13.14`, require the resolved path to be below the approved install directory, and run that path with an assertion for `sys.implementation.name == "cpython"` and `sys.version_info[:3] == (3, 13, 14)`. Thereafter every uv command runs with `UV_MANAGED_PYTHON=1`, `UV_PYTHON_DOWNLOADS=never`, the repository-local `UV_PYTHON_INSTALL_DIR`, and `.python-version` containing exactly `3.13.14`; this forbids automatic downloads and system Python fallback. [CITED: https://docs.astral.sh/uv/concepts/python-versions/] [CITED: https://docs.astral.sh/uv/reference/settings/#python-downloads]

After the reviewed `pyproject.toml` exists, resolution is a non-installing discovery step. The static project identity is fixed as normalized name `skillscout`, version `0.1.0`; changing either value invalidates the lock review:

```text
uv lock --no-build --no-sources --no-cache --managed-python --no-python-downloads --python 3.13.14
```

This command is deliberately not described as “metadata-only network traffic.” To generate a universal lock, uv may download a wheel to inspect its metadata or inspect static metadata from an sdist; without `--no-build`, it can build a package when neither source is sufficient. `--no-build` makes such a case fail, `--no-sources` excludes workspace/Git/URL/path source overrides, `--no-cache` prevents reuse of a previously built wheel and discards downloaded inspection bytes after the command, and the project must use only static PEP 621 metadata with no editable/path/Git dependency. The command does not sync or install distributions. [CITED: https://docs.astral.sh/uv/reference/troubleshooting/build-failures/#why-does-uv-build-a-package] [CITED: https://docs.astral.sh/uv/reference/cli/#uv-lock]

**Gate B — approve the complete locked graph.** Before `uv sync`, `uv build`, `uv run`, pytest, Ruff, or import of any locked package, classify every `[[package]]` record and inspect every `sdist`/`wheels` distribution entry in `uv.lock`:

1. Allow **exactly one first-party root project node**. It must have normalized name `skillscout`, version `0.1.0`, and source exactly `source = { editable = "." }`, where `.` is the canonical repository root. It must not name another path, escape through a symlink, identify another workspace member, or carry `sdist`/`wheels` artifacts. Its dependency edges, markers, `requires-dist` and dependency-group metadata must exactly match the human-reviewed static `pyproject.toml` declarations; a missing, duplicate or mismatched root node stops the gate. uv documents that it installs the current project/workspace members in editable mode by default, so this single root record is expected first-party metadata rather than an external dependency source. [CITED: https://docs.astral.sh/uv/concepts/projects/config/#editable-mode] [CITED: https://docs.astral.sh/uv/concepts/projects/sync/]
2. Treat **every other node as external**. Each must use the reviewed PyPI registry source, have an exact version and expected dependency edge/marker, and expose the artifact URL, SHA-256 and size required for install review. Reject Git, path, editable, workspace, direct-URL or alternate-registry sources on every non-root node; also reject missing hashes, yanked/adverse releases, dependency-confusion lookalikes, unexpected packages, or any package that would require a source build on Darwin/aarch64. `--no-sources` ignores `tool.uv.sources` overrides, but it does not remove uv's expected editable representation of the current project. [CITED: https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-sources] [CITED: https://docs.astral.sh/uv/reference/cli/#uv-lock]

Re-run the GSD legitimacy seam and official-owner/source review for every newly introduced external transitive distribution. Approve the exact lock bytes/hash or stop. `uv.lock` is a human-readable universal lock with exact resolved versions; its artifact records are the reviewed install authority. [CITED: https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile]

Only after Gate B may the approved graph be installed and project code built. From the repository root, every post-Gate-B uv command must repeat this exact self-contained prefix rather than depend on ambient `PATH` or prior shell exports:

```text
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"
```

All later commands use `--locked` where supported, retain that inline managed-Python/no-download environment, and must fail rather than re-lock, auto-download Python, use system Python, or build an unreviewed dependency. Do not use a floating `uv run`: `--locked` causes an error when project metadata and `uv.lock` disagree. uv documents that `UV_PYTHON_INSTALL_DIR` controls managed-Python discovery, `UV_MANAGED_PYTHON` forbids system-Python fallback, and disabling Python downloads prevents implicit acquisition. [CITED: https://docs.astral.sh/uv/reference/environment/#uv_python_install_dir] [CITED: https://docs.astral.sh/uv/reference/environment/#uv_managed_python] [CITED: https://docs.astral.sh/uv/reference/environment/#uv_python_downloads] [CITED: https://docs.astral.sh/uv/concepts/projects/sync/]

The PyPI distribution name is canonically displayed as `uv-build`; the PEP 518 requirement and backend import use `uv_build`, as shown by Astral's official configuration. The official range is `>=0.11.29,<0.12`, but Phase 1 narrows it to `==0.11.29` so the build dependency is exactly the release reviewed at the mandatory checkpoint. The `uv 0.11.29` executable bundles a compatible copy and may use it for uv-driven builds; declaring the requirement remains necessary for standard package metadata and non-uv build frontends. `uv_build` is appropriate because this phase is pure Python and uses the backend's default `src/skillscout` layout. [CITED: https://docs.astral.sh/uv/concepts/build-backend/]

## Package Legitimacy Audit

The GSD package-legitimacy seam returned `SUS` for every checked Python package because PyPI weekly-download data was unavailable and several current releases were recent. Official PyPI pages independently show verified project ownership/source links; nevertheless, the plan must include blocking `checkpoint:human-verify` gates before bootstrap and installation because GSD policy does not permit overriding a `SUS` verdict automatically.

| Package | Registry evidence | Seam verdict/reason | Official provenance | Disposition |
|---|---|---|---|---|
| `uv==0.11.29` | Exists; released 2026-07-15 | SUS: too-new, unknown-downloads | PyPI verified project links and Astral maintainers [CITED: https://pypi.org/project/uv/] | Retain; human verifies name/version/source before install |
| `uv-build==0.11.29` (`uv_build` in `[build-system]`) | Exists; released 2026-07-15; Python >=3.8 including 3.13 | SUS: too-new, unknown-downloads | Astral's official docs recommend the backend and its PyPI project has verified repository links plus Trusted Publishing [CITED: https://docs.astral.sh/uv/concepts/build-backend/] [CITED: https://pypi.org/project/uv-build/] | Retain; human verifies distribution/backend names, exact version and Astral source before build/install |
| `pydantic==2.13.4` | Exists; released 2026-05-06 | SUS: unknown-downloads | PyPI verified Pydantic owner/source [CITED: https://pypi.org/project/pydantic/] | Retain; human verifies name/version/source before install |
| `pytest==9.1.1` | Exists; released 2026-06-19 | SUS: too-new, unknown-downloads | PyPI Trusted Publishing provenance from `pytest-dev/pytest` [CITED: https://pypi.org/project/pytest/] | Retain; human verifies name/version/source before install |
| `ruff==0.15.21` | Exists; released 2026-07-09 | SUS: too-new, unknown-downloads | PyPI verified Astral repository/maintainers [CITED: https://pypi.org/project/ruff/] | Retain; human verifies name/version/source before install |

**Packages removed due to SLOP:** none.
**Packages flagged SUS:** uv, uv-build, pydantic, pytest, ruff.
**Planning consequence:** the first plan is non-autonomous at two points. Gate A approves the exact toolchain artifacts and direct declarations before bootstrap. Safe lock discovery then runs without build/install, and Gate B approves every transitive package and artifact record before any sync/build/test. No single approval may cover an unseen future lock graph.

**Runtime provenance:** Gate A must distinguish the upstream CPython `3.13.14` release from the exact Astral `python-build-standalone` binary distribution selected for this host. Python is not a PyPI package and therefore was not part of the package-legitimacy seam, but both the upstream version and redistributed artifact/build/hash are external supply-chain inputs. [CITED: https://www.python.org/downloads/release/python-31314/] [CITED: https://docs.astral.sh/uv/guides/install-python/]

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
- `StageAttempt`: `attempt_id`, `run_id`, `subject_id`, `stage`, precomputed `input_hash`, `producer_version`, `retry_policy_version`, `reusable_key_digest`, `attempt_no`, `status`, `started_at`, `finished_at`, `request_id`, `latency_ms`, nullable structured `token_usage`, sanitized `error_code`/`error_summary`, and `retryable`.
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

Use explicit SQLite transaction semantics with `autocommit=False`. Before a processor is invoked, canonicalize the stage input, compute `input_hash`, freeze the `producer_version` and `retry_policy_version`, derive `reusable_key_digest`, and persist all four on the `running` attempt. For each stage attempt:

1. Insert/transition attempt to `running` with the precomputed identity/budget fields; commit.
2. Execute the deterministic processor outside the DB transaction.
3. Begin a transaction that inserts the immutable stage result, marks attempt `succeeded`, and advances the run checkpoint together.
4. On processor error, record a sanitized structured failure in a separate transaction; never advance the checkpoint.

The JSON manifest should be written to a temporary sibling on the same filesystem, flushed and `fsync`ed, then atomically replaced before the DB transaction stores its final path/hash. On POSIX, sync the parent directory after replacement where supported. At resume, verify the full manifest hash and the embedded output hash before trusting the checkpoint. Python exposes `os.fsync`; `os.replace` performs replacement and is atomic when successful on the same filesystem. [CITED: https://docs.python.org/3.13/library/os.html#os.fsync] [CITED: https://docs.python.org/3.13/library/os.html#os.replace]

SQLite must enforce foreign keys plus uniqueness for `(run_id, subject_id, stage, attempt_no)`, the reusable stage key, and `manifest_hash`. A crash between manifest replacement and DB commit can leave an unreferenced manifest, which is safe and may be garbage-collected later; the reverse ordering is forbidden because it can leave a committed checkpoint pointing at absent bytes.

### Pattern 3A: Explicit Walking Skeleton Plan 02 → Ledger Plan 03 schema migration

Walking Skeleton Plan 02's thin SQLite database is a real public-on-disk state version, not a disposable prototype. It must create its thin tables with `PRAGMA user_version = 1`, and even the v1 attempt/checkpoint row must retain `subject_id`, `stage`, precomputed `input_hash`, `producer_version`, the fixed `retry_policy_version`, `reusable_key_digest`, attempt number/status and successful output hash. Ledger Plan 03's `StateStore.open()` supports exactly versions 1 and 2:

1. If the DB path does not exist, the current implementation creates its current schema transactionally. For an existing file, read `PRAGMA user_version` before normal queries. Version `2` proceeds; version `1` enters a `BEGIN IMMEDIATE` migration; existing version `0`, malformed databases, and versions greater than `2` fail closed as `state_schema_incompatible` rather than deleting or recreating state.
2. Inside the transaction, create the v2 result/checkpoint tables or columns, copy Walking Skeleton happy-path rows using their persisted run/stage/input/producer/retry identity and hashes, validate row counts, foreign keys, digest recomputation and required non-null fields, then set `PRAGMA user_version = 2` as the final mutation and commit. Missing identity is corruption and fails migration; do not invent a default after processing.
3. Any exception rolls the whole transaction back and reports `state_schema_migration_error`; it must leave the v1 database readable by Walking Skeleton semantics. Opening an already-v2 DB is idempotent.
4. Walking Skeleton Plan 02 must already expose deterministic `--fail-after generator`. After its GREEN tests, run the actual packaged CLI with that flag to create `tests/fixtures/state/v1-cli.db`: Generator is the durable last successful checkpoint, the run is `interrupted`, Validators has no attempt, and the companion provenance JSON records the generating command, fixture/database hashes, `user_version=1`, run ID, checkpoint and row counts. Freeze those bytes before changing the v1 adapter. Ledger Plan 03 copies that CLI-produced database, opens the copy under the v2 adapter, proves the same `run_id` and Generator checkpoint survive migration, and resumes **at Validators** with call canaries proving Scout through Generator were not replayed. A forced mid-migration error must prove rollback leaves `user_version == 1` and no partial v2 state.

SQLite reserves `user_version` for application use, and `BEGIN IMMEDIATE` obtains the write transaction before migration work; this makes the format transition explicit and testable without adding a migration dependency. [CITED: https://sqlite.org/pragma.html#pragma_user_version] [CITED: https://sqlite.org/lang_transaction.html]

### Pattern 4: Resume by deterministic stage key

The reusable stage key is:

```text
sha256(canonical(subject_id, stage_name, input_hash, producer_version, retry_policy_version))
```

On resume:

- Re-read the last `succeeded` result in stage order.
- Recompute and verify its manifest hash.
- If the next stage has a matching successful key, reuse it.
- If an attempt is left `running` from interruption, mark it `abandoned` and create a new attempt number.
- Apply a versioned retry policy with a default maximum of three attempts for the same `reusable_key_digest`; only allowlisted transient error codes may be retried, and exhaustion becomes the structured terminal error `retry_exhausted`. A changed canonical input, producer version, or retry-policy version produces a distinct digest and therefore a distinct retry budget; attempts from the old digest must never consume the new budget or be reused as its result.
- If a manifest is missing/corrupt or a stage transition is illegal, fail closed with `state_integrity_error`; do not silently restart from raw input.

The digest and its preimage fields are persisted before processing so a crash cannot create an identity-free `running` attempt or allow retry accounting to be reconstructed from mutable current configuration.

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

`--fail-after` is part of the first runnable schema-v1 CLI in Walking Skeleton Plan 02, not a later ledger feature. It is a fixture-only interruption seam and must be rejected unless execution mode is dry-run. It exits `1` after the named stage has succeeded and its checkpoint is durable, marks the run `interrupted`, and does not invoke the next processor. The required v1 migration fixture is generated with `--fail-after generator`; Ledger Plan 03 migrates a frozen copy and resumes at Validators without replaying the six completed stages. Separate adapter tests exercise failed `StageAttempt` records, allowlisted transient failures, the three-attempt ceiling, and `retry_exhausted`.

### Pattern 7: Minimum sanitized error contract starts in the Walking Skeleton

The first runnable CLI already crosses untrusted fixture and filesystem boundaries, so diagnostic sanitization cannot wait for Hardening Plan 04. Walking Skeleton Plan 02 defines a closed schema-v1 error-code enum and a static code-to-summary table. The minimum codes are `invalid_fixture`, `fixture_changed`, `state_operation_failed`, and `pipeline_interrupted`; summaries are fixed generic ASCII text of at most 160 characters and never interpolate an exception, path, identifier or input value.

All CLI JSON, SQLite rows, manifests and publication-plan data must be constructed from that allowlist. Do not serialize or emit `ValidationError.errors()` input/context/URL data, Pydantic `input`, exception `str`/`repr`/`args`, raw JSON bytes/text, environment values, credential-shaped strings, or operator/attacker-selected absolute paths. Internal logs used by tests obey the same boundary. `test_cli_dry_run.py` must inject a credential canary, an attacker-chosen absolute-path canary, hostile raw JSON and an exception containing those values, then search CLI stdout/stderr, SQLite text fields, manifests and any publication plan to prove every canary is absent while only an allowed code plus its fixed bounded summary remains. Hardening Plan 04 expands the code/malformed-state matrix and all durable surfaces; it does not establish this baseline for the first time. [CITED: https://docs.pydantic.dev/latest/errors/errors/]

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
8. **Deferring error sanitization to the hardening wave.** The first runnable CLI already accepts untrusted paths/JSON. Map to the schema-v1 closed code/fixed-summary table before any persistence or output; Pydantic input and exception `str`/`repr`/`args` are never diagnostics.
9. **Unbounded JSON fixtures.** Python warns that malicious JSON can consume CPU/memory; enforce a small fixture byte cap before parsing. [CITED: https://docs.python.org/3/library/json.html]
10. **Running tests against the repository root instead of the installed package.** Use `src/` layout and `uv run --locked pytest`; pytest recommends src layout for new projects. [CITED: https://docs.pytest.org/en/stable/explanation/goodpractices.html]
11. **Treating `uv lock` as a no-download/no-execution guarantee.** Resolution may fetch wheel/sdist bytes and may build when static metadata is unavailable. Use the Gate-B discovery command with `--no-build --no-sources --no-cache`; a required build is a stop condition, not permission to continue. [CITED: https://docs.astral.sh/uv/reference/troubleshooting/build-failures/#why-does-uv-build-a-package]
12. **Allowing lock review to cover only direct packages.** Every transitive distribution, version, source URL and artifact hash is executable supply-chain input at sync time and must pass Gate B.
13. **Opening a fixture twice.** A check-then-open or size-check-then-reopen sequence permits symlink/file replacement. Inspect and consume one descriptor, then compare its metadata before/after the bounded read.
14. **Rejecting every editable node in `uv.lock`.** uv normally represents the current project as editable. Gate B allows exactly one canonical `skillscout==0.1.0` root at `.`, then rejects editable/path/workspace/Git/URL sources for every external node.
15. **Assuming a previously exported uv environment remains active.** Each post-Gate-B command repeats the verified repo-local uv path and all three managed-Python/no-download environment values inline.

## Security Threat Model Inputs

Security enforcement is active at OWASP ASVS Level 1 and blocks unresolved high-severity threats. Each plan must include a `<threat_model>` register.

| Threat | STRIDE | Severity | Required mitigation |
|---|---|---:|---|
| Fixture is a symlink/non-regular file, changes during read, or JSON is oversized | Tampering / DoS | high | **Walking Skeleton Plan 02 minimum:** `lstat` and reject symlink/non-regular inputs; open once with `O_NOFOLLOW`, `O_NONBLOCK` and `O_CLOEXEC` where available so a swap to a FIFO cannot block; `fstat` the same descriptor, require regular mode and compare device/inode; reject declared size over the cap; read in bounded chunks and reject as soon as accumulated bytes exceed the cap (`cap + 1` probe); `fstat` again and reject changed device/inode/size/`mtime_ns`/`ctime_ns`; only then decode/parse and apply the strict schema. Platforms without `O_NOFOLLOW` still require the lstat/fstat identity comparison. Hardening Plan 04 expands the adversarial matrix but may not defer these primitives. |
| Manifest path derived from attacker-controlled IDs | Tampering | high | Validate IDs/enum names and construct paths internally. |
| Tampered/missing manifest is accepted during resume | Tampering / Repudiation | high | Recompute hash, compare DB metadata, fail closed. |
| Exception or payload leaks secrets into state/output | Information Disclosure | high | **Walking Skeleton Plan 02 minimum:** closed error-code enum plus fixed generic summaries ≤160 ASCII characters; never persist/emit Pydantic input, validation context/URL, exception `str`/`repr`/`args`, raw JSON, credential canaries or attacker-selected absolute paths; hostile canary coverage lives in `test_cli_dry_run.py`. Hardening Plan 04 expands the matrix. |
| Dry-run runtime obtains remote read/write or network capability | Elevation of Privilege | critical | Capability omission plus `SideEffectPolicy` startup rejection and socket sentinel test. |
| Package name/version substitution | Tampering | high | Gate A verified toolchain/direct identities and artifacts; non-building lock discovery; Gate B allows exactly one canonical first-party root `skillscout==0.1.0` editable `.` and requires registry-only sources for every external node; all post-gate commands repeat the self-contained verified-uv prefix. |
| Replayed stage with incompatible producer/schema/retry version | Tampering | medium | Precomputed attempt identity persists input/producer/retry-policy versions; reusable digest and schema version are validated before reuse. |
| Walking Skeleton database is silently reinitialized by Ledger Plan 03 | Tampering / Repudiation | high | Version 1/2 format contract, transactional `BEGIN IMMEDIATE` migration, rollback on error, fail-closed unknown versions, migration/resume tests. |

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
- Walking Skeleton fixture-safety cases in `test_cli_dry_run.py`: symlink, directory or other non-regular input, over-limit declared size, `cap + 1` streaming overflow, and a same-descriptor file-change simulation that proves pre/post metadata comparison. These are minimum acceptance, not Hardening Plan 04 deferrals.
- Walking Skeleton error-disclosure cases in `test_cli_dry_run.py`: raw/Pydantic-invalid JSON containing a credential canary and attacker absolute path plus an exception whose args contain those values; all emitted/persisted surfaces contain only the closed code and its fixed bounded summary.
- `--fail-after generator` in the schema-v1 Walking Skeleton CLI: generate and freeze a real interrupted v1 DB whose last checkpoint is Generator and which has no Validators attempt; Ledger Plan 03 migrates a copy and proves the first resumed invocation is Validators.
- `invalid-extra-field.json`: strict schema rejects unknown data.
- generated oversized JSON in test temp directory: size gate rejects before parse.
- tampered manifest copy: resume detects content hash mismatch.
- persisted transient failures at the retry ceiling: the next attempt is rejected as `retry_exhausted` without invoking the processor.
- the real Walking Skeleton CLI-produced, Generator-interrupted v1 database plus a forced migration-failure seam: Ledger Plan 03 migrates/resumes the former at Validators and rolls the latter back without partial v2 state.

### Sampling policy

- Wave 1 ends at static bootstrap/lock evidence and Gate B. Run only non-importing static assertions there; do **not** require pytest, Ruff, `uv build`, `uv run` or a full suite in Wave 1.
- Wave 2 first executes the exact attributed RED after Gate B, then its focused GREEN tests. Full-suite sampling begins only after Wave 2 is GREEN and runs at the ends of Waves 2, 3 and 4.
- After every post-Gate-B task, run the narrow test file named in the task's `<automated>` verification plus Ruff on touched Python paths. Every command repeats the exact self-contained uv prefix from the installation strategy; ambient `PATH`/exports are not evidence.
- Before Phase 1 verification: run full pytest, Ruff, `uv lock --check`, and two CLI demonstrations (happy path; fail then resume), again with the exact inline prefix.
- No watch mode. Target full feedback latency is under 15 seconds on local fixture data.

### Nyquist mapping guidance

- `OPS-01` needs automated coverage for schema rejection, stable/non-circular hashes, precomputed attempt input/producer/retry-policy identity, all required nullable provenance and attempt telemetry fields, persisted attempts/results, explicit v1→v2 migration, and inspectable ledger output.
- `OPS-04` needs automated coverage for failure injection, digest-scoped finite retry plus exhaustion, a fresh retry budget after input/producer/retry-policy change, checkpoint reuse, publication-plan-only output, zero remote reads/writes, and fail-closed state corruption.
- No product behavior should remain manual-only. The only manual work is the two supply-chain approvals mandated before bootstrap and installation.

## Planning Recommendations

Use four sequential plans:

1. **Verified Toolchain and Lock Approval:** Gate A, deterministic repository-local uv/managed-Python bootstrap, static scaffold, non-building lock discovery, then blocking Gate B before any build/import/test.
2. **Walking Skeleton:** exact attributed RED followed by the thinnest real fixture→SQLite-v1→publication-plan path, including the high-severity single-descriptor fixture reader, minimum sanitized-error contract, deterministic `--fail-after generator`, and a frozen CLI-produced v1 DB interrupted after Generator.
3. **Checkpoint/Resume Ledger:** transactional migration of a copy of that frozen v1 DB, resume at Validators without replay, immutable envelopes, explicit non-circular hashes, precomputed attempt/retry identity, transactional manifests/SQLite attempts, digest-scoped bounded retry and inspect command.
4. **Fail-Closed Dry-Run Hardening:** capability registry/policy, remote-read/write rejection, the broader adversarial path/size/change/error matrix beyond Walking Skeleton primitives, manifest corruption detection, full acceptance commands.

Each plan should contain 2–3 tasks and a complete vertical refinement. Plans are sequential because Plan 03 migrates/refines the Walking Skeleton's contracts and state, while Plan 04 hardens the composed runtime.

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
- [uv editable project configuration](https://docs.astral.sh/uv/concepts/projects/config/#editable-mode)
- [uv dependency-source semantics](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-sources)
- [uv environment variables](https://docs.astral.sh/uv/reference/environment/)
- [uv 0.11.29 immutable release, platform checksums and attestations](https://github.com/astral-sh/uv/releases/tag/0.11.29)
- [uv 0.11.29 fixed managed-Python download metadata](https://raw.githubusercontent.com/astral-sh/uv/901092ee11a89ba287f274e3c6e3a2e18ec2fba2/crates/uv-python/download-metadata.json)
- [Astral python-build-standalone immutable 20260623 release](https://github.com/astral-sh/python-build-standalone/releases/tag/20260623)
- [uv CLI: managed Python, `python install`, and `uv lock`](https://docs.astral.sh/uv/reference/cli/)
- [uv Python versions and Astral distributions](https://docs.astral.sh/uv/concepts/python-versions/)
- [uv environment: pinned CPython build metadata](https://docs.astral.sh/uv/reference/environment/#uv_python_cpython_build)
- [uv build behavior during resolution](https://docs.astral.sh/uv/reference/troubleshooting/build-failures/#why-does-uv-build-a-package)
- [uv build backend](https://docs.astral.sh/uv/concepts/build-backend/)
- [Pydantic serialization](https://docs.pydantic.dev/latest/concepts/serialization/)
- [Pydantic model configuration](https://docs.pydantic.dev/latest/api/config/)
- [Pydantic validation-error details and input controls](https://docs.pydantic.dev/latest/errors/errors/)
- [Python sqlite3 transaction control](https://docs.python.org/3/library/sqlite3.html#transaction-control-via-the-autocommit-attribute)
- [Python JSON](https://docs.python.org/3/library/json.html)
- [Python hashlib](https://docs.python.org/3/library/hashlib.html)
- [Python `os.replace`](https://docs.python.org/3/library/os.html#os.replace)
- [Python `os.fsync`](https://docs.python.org/3.13/library/os.html#os.fsync)
- [Python 3.13.14 release](https://www.python.org/downloads/release/python-31314/)
- [SQLite application `user_version`](https://sqlite.org/pragma.html#pragma_user_version)
- [SQLite transactions and `BEGIN IMMEDIATE`](https://sqlite.org/lang_transaction.html)
- [pytest good integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [Python Packaging: src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [uv on PyPI](https://pypi.org/project/uv/)
- [uv-build on PyPI](https://pypi.org/project/uv-build/)
- [Pydantic on PyPI](https://pypi.org/project/pydantic/)
- [pytest on PyPI](https://pypi.org/project/pytest/)
- [Ruff on PyPI](https://pypi.org/project/ruff/)

## RESEARCH COMPLETE

Phase 1 can be planned without further product decisions. Gate B recognizes exactly one canonical first-party `skillscout==0.1.0` editable root and rejects non-registry sources for every external node. Wave 1 ends after static lock approval; every later command repeats the verified local uv/managed-Python prefix. Walking Skeleton Plan 02 owns minimum error sanitization, hostile disclosure canaries and the Generator-interrupted schema-v1 CLI fixture; Ledger Plan 03 migrates a frozen copy and resumes at Validators without replay; Hardening Plan 04 expands the security matrix.
