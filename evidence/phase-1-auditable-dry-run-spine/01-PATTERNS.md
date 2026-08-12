# Phase 1: Auditable Dry-Run Spine — Pattern Map

**Mapped:** 2026-07-16  
**Files analyzed:** 20 anticipated hand-authored repository files  
**Analogs found:** 0 / 20  
**Generated tracked artifacts:** 3 (`uv.lock`, `tests/fixtures/state/v1-cli.db`, `tests/fixtures/state/v1-cli-provenance.json`)  
**Repository status:** Greenfield; the repository contains planning documents only

## Mapping Result

There are no source, test, packaging, CLI, persistence, or adapter files in the current repository. The repository contains planning documents only; none is a code analog. The 20-file count below covers files authored as implementation, configuration or test content. The lockfile and two frozen schema-v1 fixtures are generated, reviewed, tracked artifacts with explicit producers, so they are mapped separately rather than misclassified as hand-authored analogs.

The planner must therefore use `01-RESEARCH.md` as the implementation-pattern authority and `01-VALIDATION.md` as the test ownership authority. `AGENTS.md` remains the non-negotiable security and workflow constraint. Planning documents are specification anchors, not code to copy.

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `.gitignore` | config | workspace hygiene | None — no ignore file exists | no analog |
| `.python-version` | config | environment selection | None — no runtime config exists | no analog |
| `pyproject.toml` | config | build/test configuration | None — `.planning/config.json` is unrelated GSD state | no analog |
| `src/skillscout/__init__.py` | package | import surface | None — no Python package exists | no analog |
| `src/skillscout/cli.py` | controller | request-response, file-I/O | None — no CLI exists | no analog |
| `src/skillscout/application/pipeline.py` | service | batch, transform | None — no application service exists | no analog |
| `src/skillscout/application/ports.py` | provider contract | request-response | None — no ports exist | no analog |
| `src/skillscout/domain/enums.py` | model | transform | None — no domain model exists | no analog |
| `src/skillscout/domain/models.py` | model | transform | None — no domain model exists | no analog |
| `src/skillscout/domain/canonical.py` | utility | transform | None — no serialization utility exists | no analog |
| `src/skillscout/adapters/fixtures.py` | provider | file-I/O, transform | None — no adapter exists | no analog |
| `src/skillscout/adapters/state.py` | store | CRUD, file-I/O | None — no persistence code exists | no analog |
| `tests/conftest.py` | test support | request-response | None — no test suite exists | no analog |
| `tests/fixtures/pipeline/approved.json` | test fixture | file-I/O, batch | None — no product fixture exists | no analog |
| `tests/test_cli_dry_run.py` | test | request-response, file-I/O | None — no CLI tests exist | no analog |
| `tests/test_stage_contracts.py` | test | transform | None — no contract tests exist | no analog |
| `tests/test_pipeline_resume.py` | test | batch, CRUD, file-I/O | None — no recovery tests exist | no analog |
| `tests/test_side_effect_policy.py` | test | request-response | None — no capability tests exist | no analog |
| `tests/test_state_integrity.py` | test | CRUD, file-I/O | None — no integrity tests exist | no analog |
| `tests/test_cli_security.py` | test | request-response, file-I/O | None — no input-boundary tests exist | no analog |

### Generated tracked artifacts (not part of the 20-file hand-authored map)

| Generated File | Producer | Consumer / Gate | Analog Status |
|---|---|---|---|
| `uv.lock` | Plan 01's exact non-building/no-source/no-cache discovery command after Gate A | Gate B reviews exact bytes, the one first-party root exception, and every external artifact before any build/import/test | no analog |
| `tests/fixtures/state/v1-cli.db` | Plan 02's real packaged schema-v1 CLI run with `--fail-after generator`, after Walking Skeleton GREEN and before v2 edits | Plan 03 copies, migrates and resumes the frozen database at Validators | no analog |
| `tests/fixtures/state/v1-cli-provenance.json` | Plan 02's freeze handoff beside the CLI-produced database | Plan 03 verifies command/hash/version/run/checkpoint/row-count provenance before migration | no analog |

## Pattern Assignments

Because no code analog exists, each file is assigned to an exact upstream specification anchor. The planner should cite these anchors in task actions instead of claiming an existing implementation convention.

### Runtime and project configuration

| File | Specification Anchor | Required Pattern |
|---|---|---|
| `.gitignore` | `01-RESEARCH.md` → Installation and lock strategy | Exclude `.tools/`, `.venv/`, `dist/` and `.tmp/` so verified local executables/runtimes and ephemeral build/demo state cannot enter source commits. |
| `.python-version` | `01-RESEARCH.md` → Installation and lock strategy | Contain exactly `3.13.14` after Gate A installs the approved managed runtime. Every uv command must retain `UV_MANAGED_PYTHON=1`, `UV_PYTHON_DOWNLOADS=never`, the approved repository-local `UV_PYTHON_INSTALL_DIR`, and must never fall back to system Python. |
| `pyproject.toml` | `01-RESEARCH.md` → Standard Stack, Installation and lock strategy; `01-VALIDATION.md` → Wave 0 Requirements | Create only static PEP 621 metadata: pure-Python `src/` layout, `[build-system] requires = ["uv_build==0.11.29"]`, `build-backend = "uv_build"`, `[project.scripts] skillscout = "skillscout.cli:main"`, exact Pydantic plus pytest/Ruff declarations and central test/lint configuration. Declare no Git/path/editable/direct-URL dependency source or dynamic build metadata; uv's single canonical root-project record is reviewed later as a lock-format exception, not declared as an external source here. |

No existing repository metadata should be copied: `.planning/config.json` configures GSD, not the product runtime.

### Package and CLI boundary

| File | Specification Anchor | Required Pattern |
|---|---|---|
| `src/skillscout/__init__.py` | `01-RESEARCH.md` → Standard Stack, Recommended Project Structure | Keep the public package surface minimal and compatible with `uv_build`'s default `src/skillscout` package discovery; do not expose future provider capabilities. |
| `src/skillscout/cli.py` | `01-RESEARCH.md` → Installation and lock strategy, Patterns 6–7 | Export `main` for the exact console mapping `skillscout.cli:main`; Walking Skeleton Plan 02 implements `dry-run` plus deterministic `--fail-after`, while Plan 03 adds `inspect-run`. Validate options, emit only the closed fixed-summary error contract, and render structured summaries while delegating transitions to the application layer. Preserve exit codes `0`, `1`, and argparse `2`. |

The CLI is the Walking Skeleton interaction. Its happy path must reach a real SQLite write/read and a local `publication-plan.json`, not an in-memory demonstration.

### Domain contracts and canonical identity

| File | Specification Anchor | Required Pattern |
|---|---|---|
| `src/skillscout/domain/enums.py` | `01-RESEARCH.md` → Patterns 4–6 | Define the fixed ordered stage sequence, run/attempt states, execution mode, and `EffectScope`; reject illegal or unknown states. |
| `src/skillscout/domain/models.py` | `01-RESEARCH.md` → Pattern 1 | Use strict, frozen Pydantic models with `extra="forbid"`; keep stable result identity separate from volatile telemetry. `StageAttempt` structurally persists precomputed `input_hash`, `producer_version`, `retry_policy_version`, `reusable_key_digest`, attempt number/status and explicit nullable prompt/model/request/token fields. |
| `src/skillscout/domain/canonical.py` | `01-RESEARCH.md` → Pattern 2 | Provide the single canonical JSON byte path and three explicit non-self-referential preimages for input, output, and manifest hashes. |

`OPS-01` is owned at this boundary: schemas, IDs, timestamps, hashes, attempt telemetry, and applicable versions must be structural fields, not ad hoc log strings.

### Application orchestration and ports

| File | Specification Anchor | Required Pattern |
|---|---|---|
| `src/skillscout/application/ports.py` | `01-RESEARCH.md` → Architectural Responsibility Map; Pattern 5 | Define provider-independent stage/state contracts and declared effect scopes. Do not add GitHub, OpenAI, shell, or remote-publisher methods. |
| `src/skillscout/application/pipeline.py` | `01-RESEARCH.md` → System Architecture Diagram; Patterns 3–6 | Before invoking a processor, canonicalize/freeze the input, producer and retry-policy versions, compute `input_hash` plus `reusable_key_digest`, and persist the running attempt. Own ordered execution, digest-scoped finite retry, checkpoint reuse, failure injection, publication planning and structured summaries; processors run outside DB transactions. |

The composition root must be capability-based. Phase 1 allows only `none` and `local_state`; a dry-run boolean around a dangerous adapter is not an acceptable pattern.

### Local adapters

| File | Specification Anchor | Required Pattern |
|---|---|---|
| `src/skillscout/adapters/fixtures.py` | `01-RESEARCH.md` → Security Threat Model Inputs, Common Pitfalls | Walking Skeleton Plan 02 must `lstat`, reject symlink/non-regular input, open once with `O_NOFOLLOW`/`O_NONBLOCK`/`O_CLOEXEC` where available, `fstat` the same descriptor, validate device/inode and declared size, read bounded chunks with a `cap + 1` overflow probe, then compare post-read device/inode/size/`mtime_ns`/`ctime_ns` before decode/strict parse. Never check then reopen. |
| `src/skillscout/adapters/state.py` | `01-RESEARCH.md` → Patterns 3, 3A and 4 | Walking Skeleton Plan 02 creates real schema v1 with `PRAGMA user_version = 1` and persists stage/retry identity before processing. In ledger Plan 03, an absent DB is created directly at current schema v2, existing v2 proceeds idempotently, and v1 migrates under `BEGIN IMMEDIATE`; validate copies/digests/FKs/non-null fields, set version 2 last, and roll back/fail closed on error. Existing version 0, malformed or future-version DBs are rejected. Manifest bytes remain durable before the result/attempt/checkpoint DB commit. |

The adapters must not import or instantiate HTTP, OpenAI, GitHub, subprocess, candidate-code, or remote publication clients.

### Test infrastructure and acceptance coverage

| File | Specification Anchor | Required Pattern |
|---|---|---|
| `tests/conftest.py` | `01-VALIDATION.md` → Wave 0 Requirements | Supply temporary state/output paths and deterministic clock/ID providers without masking real SQLite I/O. |
| `tests/fixtures/pipeline/approved.json` | `01-RESEARCH.md` → Required fixtures | Represent one bounded structured subject that reaches `planned_not_published`; contain no executable repository content. |
| `tests/test_cli_dry_run.py` | `01-VALIDATION.md` → tasks 01-01-02, 01-01-03, 01-02-03 | After Gate B, run the attributed RED only through the exact repository-local uv prefix below; retain output and require successful collection plus the intended named functional assertion failure, never import/collection/usage/no-test failure. Walking Skeleton GREEN coverage includes the complete CLI, schema-v1 state, publication-plan-only output, same-descriptor symlink/non-regular/size/`cap + 1`/change-race cases, the closed fixed-summary error contract and hostile secret/path/raw-input/exception canaries. It also owns `--fail-after generator` and the real interrupted-v1 freeze handoff consumed by Plan 03. |
| `tests/test_stage_contracts.py` | `01-VALIDATION.md` → task 01-02-01 | Prove strict extras rejection, legal transitions, stable/non-circular hashes and complete precomputed attempt identity including retry-policy version and reusable digest. |
| `tests/test_pipeline_resume.py` | `01-VALIDATION.md` → tasks 01-02-02, 01-02-03 | Copy the frozen v1 state produced by Plan 02's real Walking Skeleton CLI, migrate it to v2, and prove the same run/Generator checkpoint resumes first at Validators without replay; forced migration rollback leaves readable v1 state. Also prove abandoned attempts, three-attempt exhaustion scoped to one digest, and a distinct budget only after canonical input/producer/retry-policy identity changes. |
| `tests/test_side_effect_policy.py` | `01-VALIDATION.md` → task 01-03-01 | Prove both remote-read and remote-write adapters are rejected at runtime construction. |
| `tests/test_state_integrity.py` | `01-VALIDATION.md` → task 01-03-02 | Prove missing/tampered manifests and incompatible/corrupt state fail closed; version `0`, malformed and future-version DBs are never silently recreated. |
| `tests/test_cli_security.py` | `01-VALIDATION.md` → task 01-03-02 | Expand the adversarial path/size/change/error matrix beyond the single-descriptor primitives already required and green in Walking Skeleton Plan 02; do not defer those minimum controls to Hardening Plan 04. |

Tests should exercise public CLI/application boundaries and inspect durable outputs. They must not introduce mock remote clients merely to prove those clients are unused; the stronger Phase 1 pattern is that such capabilities do not exist.

## Plan and Task Ownership

| Task | Owned Pattern/File Boundary |
|---|---|
| `01-01-01` | Gate A evidence and verified repository-local uv/managed-CPython bootstrap; `.python-version`; static `pyproject.toml`/Wave-0 scaffold; exact non-building/no-source/no-cache lock discovery. No project package may be imported, built, synced or tested. |
| `01-01-01B` | Gate B allows exactly one first-party lock node: normalized `skillscout==0.1.0` with canonical `source = { editable = "." }` and no artifacts. Every non-root node must be registry-only and has its dependency edge, marker, artifact URL/hash/size and exact lock bytes reviewed before any build/import/test. |
| `01-01-02` | Packaged CLI/test scaffold and the exact RED command, with evidence that pytest collected and failed only at the intended functional assertion. |
| `01-01-03` | Green Walking Skeleton: `cli.py`, fixture adapter's minimum single-descriptor safeguards, schema-v1 closed error enum plus fixed generic ASCII summaries ≤160 characters, hostile disclosure canaries, deterministic local stages, and SQLite v1 retry identity/checkpoint fields. It implements `--fail-after generator`, then the actual packaged CLI freezes an interrupted v1 DB/provenance with Generator durable and no Validators attempt before Plan 03 edits v2 state code. |
| `01-02-01` | Strict/frozen domain envelopes, canonical preimages, precomputed attempt identity and contract tests. |
| `01-02-02` | `StateStore.open()` v1→v2 transactional migration/rollback, durable manifests and attempt/result/checkpoint persistence, exercised from a copy of Plan 02's frozen CLI-created interrupted DB; first resumed processor is Validators and Scout through Generator are canary-protected from replay. |
| `01-02-03` | Resume/inspect behavior, abandoned attempts, digest-scoped retry ceiling and fresh budget only after identity change. |
| `01-03-01` | Side-effect capability registry/policy and remote read/write rejection. |
| `01-03-02` | Manifest/state integrity plus the broader CLI adversarial matrix beyond the Walking Skeleton's mandatory primitives. |
| `01-03-03` | Full no-network/zero-remote-write acceptance and final locked build/test commands. |

## Shared Patterns

### Layer ownership

**Source:** `01-RESEARCH.md` → Architectural Responsibility Map  
**Apply to:** all `src/skillscout/**` files

- Domain owns typed, provider-independent facts and legal states.
- Application owns orchestration and capability enforcement.
- Adapters own fixture and local persistence mechanics.
- CLI owns input/options and user-facing structured output only.

### Structured fail-closed errors

**Source:** `01-RESEARCH.md` → Patterns 3–4, Common Pitfalls, Security Threat Model Inputs  
**Apply to:** CLI, pipeline, fixture adapter, state adapter

The first runnable schema-v1 Walking Skeleton defines a closed error-code enum with a static code-to-summary table. At minimum it owns `invalid_fixture`, `fixture_changed`, `state_operation_failed`, and `pipeline_interrupted`; every summary is fixed generic ASCII text of at most 160 characters. CLI JSON, SQLite text, manifests, publication plans and test-visible logs may persist or emit only an allowlisted code plus its fixed summary. They never interpolate exception `str`/`repr`/`args`, Pydantic error input/context/URL, raw JSON, credential-shaped values, attacker-selected paths or identifiers.

`tests/test_cli_dry_run.py` establishes this contract in Plan 02 with hostile credential, absolute-path, raw-JSON/Pydantic and exception-argument canaries searched across stdout/stderr and every durable surface. Plan 04 may expand codes and malformed-state cases, but it cannot establish or weaken this baseline. A missing/corrupt manifest, illegal transition, incompatible schema, unsafe fixture, or forbidden capability stops the run; none silently restarts from raw input or advances the checkpoint.

### Deterministic content identity

**Source:** `01-RESEARCH.md` → Patterns 1–2  
**Apply to:** domain contracts, pipeline, state adapter, contract/resume tests

Use one canonical JSON implementation. Exclude timestamps, attempts, request IDs, run-local IDs, and hash fields from semantic output identity. Address full immutable manifests by `manifest_hash`, not `output_hash`.

Before the processor runs, freeze the canonical input, producer version and retry-policy version, derive `input_hash` and `reusable_key_digest`, and persist those fields on the running attempt. Retry accounting and reusable results are scoped to that digest; changed input/producer/retry-policy identity creates a new budget and never consumes or reuses the old digest's attempts.

### Durable local state

**Source:** `01-RESEARCH.md` → Patterns 3 and 3A  
**Apply to:** pipeline and state adapter

Write and sync a same-filesystem temporary manifest, atomically replace it, then commit immutable result, succeeded attempt, and checkpoint together. Stage processing must occur outside the database transaction.

Schema v1 is a durable contract, not disposable scaffolding. It records `PRAGMA user_version = 1` plus the complete persisted retry identity required for Ledger Plan 03. Migration to v2 obtains `BEGIN IMMEDIATE`, copies and validates state, updates `user_version` last, and rolls back entirely to readable v1 on failure. Version `0`, malformed, and future schemas fail closed rather than being deleted or recreated.

### Capability omission

**Source:** `AGENTS.md` constraints; `01-RESEARCH.md` → Pattern 5  
**Apply to:** ports, pipeline composition, adapters, security tests

Phase 1 has no remote service adapter. The runtime rejects `remote_read` and `remote_write` scopes at startup, and the end-to-end test uses a socket-connect sentinel as defense in depth.

### Test-first vertical refinement

**Source:** `01-VALIDATION.md` → Per-Task Verification Map and Wave 0 Requirements  
**Apply to:** all four Phase 1 plans

Plan 01 follows Gate A → verified bootstrap → static metadata/test scaffold → non-building lock discovery → Gate B. **Wave 1 is an intentional sampling exception:** it ends at static Gate-B evidence and runs no pytest, Ruff, `uv build`, `uv run` or full suite. Its only automated evidence is non-importing static verification of files and approved repository-local tool/interpreter identity.

Walking Skeleton Plan 02 then runs the exact fully prefixed RED shown below before green implementation. Shell success alone is insufficient: pytest must collect and fail at the named intended assertion, not exit for setup/import/collection/usage/no-test reasons. Full-suite sampling starts only after Plan 02 is GREEN, then runs at the ends of Waves 2, 3 and 4. Plans 03 and 04 create focused tests in the same task before the behavior they verify.

### Self-contained post-Gate-B uv invocation

**Source:** `01-RESEARCH.md` → Installation and lock strategy; `01-VALIDATION.md` → Test Infrastructure  
**Apply to:** every command after Gate B in Plans 02–04, including `<verify>` commands, RED/GREEN tests, Ruff, build, lock checks, CLI demos and fixture generation

Never rely on ambient `PATH`, an activated environment or prior shell exports. Every uv command must begin with this complete inline managed-Python/no-download prefix:

```text
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"
```

For example, the attributed RED expands to:

```text
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" build --no-sources && ! UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked pytest -q tests/test_cli_dry_run.py
```

Commands use `--locked` wherever supported and fail rather than relock, download Python, use system Python or execute an unreviewed source.

### Two-gate supply-chain and build boundary

**Source:** `01-RESEARCH.md` → Standard Stack, Installation and lock strategy, Package Legitimacy Audit; `01-VALIDATION.md` → Test Infrastructure and Final Phase Commands  
**Apply to:** `.python-version`, `pyproject.toml`, `uv.lock`, `src/skillscout/__init__.py`, `src/skillscout/cli.py`, Plan 01 Gate A/Gate B checkpoints and build verification

Gate A verifies the Darwin/aarch64 host; uv `0.11.29` commit `901092ee11a89ba287f274e3c6e3a2e18ec2fba2`, asset `uv-aarch64-apple-darwin.tar.gz`, SHA-256 `61c04acc52a33ef0f331e494bdfbedcdb6c26c6970c022ed3699e5860f8930e3` and attestation; upstream CPython `3.13.14`; distinct Astral `python-build-standalone` build `20260623`, asset `cpython-3.13.14+20260623-aarch64-apple-darwin-install_only_stripped.tar.gz`, SHA-256 `795a5aeeb050f00aa8a2214d779bad9f1b9113edb6923317a80c042a11a087d7`; and the four direct declarations. Bootstrap uses only verified, repository-local ignored uv and managed-Python directories, a local runtime mirror, `UV_PYTHON_CPYTHON_BUILD=20260623`, and disabled automatic downloads/system-Python fallback.

After static metadata exists, the only authorized resolution command is `uv lock --no-build --no-sources --no-cache --managed-python --no-python-downloads --python 3.13.14`. Gate B permits exactly one non-registry record: the first-party root with normalized name `skillscout`, version `0.1.0`, canonical `source = { editable = "." }`, dependency metadata matching `pyproject.toml`, and no `sdist`/`wheels` artifacts. Every other node is external and must be registry-only; Git/path/editable/workspace/direct-URL/alternate-registry sources are rejected for all non-root nodes. Gate B reviews every external edge/marker and artifact URL/hash/size plus exact lock bytes. No `uv sync`, `uv build`, `uv run`, import, pytest or Ruff is authorized before Gate B. After approval, the self-contained prefix plus `build --no-sources` proves the pure-Python `src/skillscout` package and `[project.scripts] skillscout = "skillscout.cli:main"` entry point are valid without workspace/source overrides.

## Generated and Runtime Artifacts (Not Implementation Analogs)

The following are produced during execution and must not be mistaken for pre-existing source analogs. Rows explicitly marked tracked are committed only after their named producer and review/freeze gate.

| Artifact | Producer | Pattern |
|---|---|---|
| `.tools/uv-0.11.29/` | Gate-A bootstrap | Ignored repository-local uv extracted only after archive checksum/optional trusted-base attestation verification; `command -v uv` must resolve here. |
| Repository-local managed CPython directory | Gate-A bootstrap | Contains only the approved Astral `python-build-standalone` asset for CPython `3.13.14`; resolved interpreter path/version is asserted and automatic downloads are disabled. |
| `uv.lock` plus approval record/hash | Plan 01 discovery + Gate B | **Tracked generated configuration.** It contains exactly one canonical first-party editable root; every non-root source is registry-only. The human-reviewed exact bytes cover every external artifact URL/hash/size; no unseen future graph is covered by Gate A. |
| `tests/fixtures/state/v1-cli.db` | Plan 02 packaged CLI after GREEN | **Tracked generated test fixture.** `--fail-after generator` produces `user_version=1`, an interrupted run, durable Generator checkpoint and no Validators attempt before any v2 edit. |
| `tests/fixtures/state/v1-cli-provenance.json` | Plan 02 freeze handoff | **Tracked generated test evidence.** Records the exact prefixed CLI command, fixture/database SHA-256, schema version, run/checkpoint and row counts. |
| Working SQLite state database (`user_version=1` then `2`) | state adapter | Plan 02 creates real v1 state. Plan 03 copies the frozen v1 fixture, migrates the copy transactionally to v2 without changing run/checkpoint identity, and resumes first at Validators. |
| `<db-stem>.manifests/<stage>/<manifest-hash>.json` | state adapter | Internally derived, content-addressed, immutable audit record. |
| `publication-plan.json` | publication planner | Local plan only, ending in `planned_not_published`; contains no branch/PR/merge method or credential. |
| CLI run/inspect JSON | CLI | Structured projection of persisted state with `remote_writes_attempted: 0`. |
| `dist/*.whl` and `dist/*.tar.gz` | `uv_build` via the exact post-Gate-B prefix plus `build --no-sources` | Ephemeral build-verification outputs proving package discovery and console metadata; not source files or canonical operational state. |

## No Analog Found

All 20 anticipated hand-authored files have no close match because the repository contains no implementation files. Specifically:

- **Runtime/config (3):** `.gitignore`, `.python-version`, `pyproject.toml`.
- **Package/application/domain/adapters (9):** every proposed file under `src/skillscout/`.
- **Tests/fixtures (8):** `tests/conftest.py`, the hand-authored approved fixture, and six test modules.

The three generated tracked artifacts also have no analog, but are excluded from the 20-file authored count so their producer/gate provenance remains explicit.

The planner should not use `.planning/config.json` as a Python configuration analog, planning Markdown as a source-code style analog, or future Phase 2–5 architecture as permission to add live integrations.

## Planner Guardrails

1. Keep the exact stage path Scout → Filter → Reader → Extractor → Qualifier → Generator → Validators → Reviewer → publication plan.
2. Preserve the CLI as a true vertical slice with real SQLite write/read and inspectable local artifacts.
3. Preserve both blocking supply-chain gates. Gate A precedes any external executable bootstrap; Gate B follows exact non-building/no-source/no-cache lock discovery and precedes every sync/build/import/test. Gate B allows exactly the canonical `skillscout==0.1.0` editable `.` root and requires registry-only sources for every non-root node. Never let one approval cover an unseen transitive graph.
4. Do not add HTTPX, OpenAI, PyYAML, GitHub clients, migration/DI/workflow frameworks, remote adapters, GitHub Actions, or Skill-generation dependencies in Phase 1.
5. Do not create `scripts/`, clone/install/import/execute candidate content, or introduce any merge/default-branch capability.
6. Walking Skeleton Plan 02 must ship minimum single-descriptor fixture safeguards, the schema-v1 closed fixed-summary (≤160 ASCII characters) error contract and hostile disclosure canaries, plus a real SQLite v1 with persisted retry identity; hardening Plan 04 may expand their adversarial coverage but cannot own or defer these baselines.
7. Walking Skeleton Plan 02 owns `--fail-after generator` and, after GREEN, freezes the actual packaged CLI-produced interrupted v1 DB/provenance before v2 edits. Ledger Plan 03 copies that fixture, preserves run/Generator identity, resumes first at Validators with prior-stage canaries, and proves forced rollback leaves `user_version == 1` with no partial v2 state.
8. Assign all 20 hand-authored repository files and all three generated tracked artifacts above to explicit tasks, and list every new symbol, CLI option, runtime artifact, schema version/migration, `uv_build` backend, `skillscout.cli:main` entry point and build output in the owning plan's artifact inventory.
9. Wave 1 stops after static Gate-B evidence and is exempt from pytest/Ruff/build/full-suite sampling. After Gate B, repeat the complete inline repository-local uv/managed-Python/no-download prefix on every command; use the corrected RED exactly and inspect raw pytest evidence so logical negation cannot convert setup/import/collection/usage/no-test failure into false RED success.

## Metadata

**Analog search scope:** entire repository excluding `.git`  
**Anticipated hand-authored files mapped:** 20  
**Generated tracked artifacts mapped:** 3  
**Existing implementation files scanned:** 0  
**Source files found:** 0  
**Test files found:** 0  
**Project skills found:** 0  
**Pattern extraction date:** 2026-07-16
