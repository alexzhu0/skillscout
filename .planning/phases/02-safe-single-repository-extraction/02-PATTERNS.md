# Phase 2: Safe Single-Repository Extraction — Pattern Map

**Mapped:** 2026-07-21  
**Files analyzed:** 23 planned new/modified files from `02-RESEARCH.md` §Planning Recommendations  
**Analogs found:** 23 / 23 (every planned file has at least one concrete in-repo analog; HTTP/LLM transport mocking is the only genuinely new mechanic)  
**Repository status:** Phase 1 complete and green — full spine implementation exists under `src/skillscout/` with a 9-module test suite

## Mapping Result

Unlike Phase 1 (greenfield), Phase 2 extends a working spine. `02-RESEARCH.md` §Phase 1 Integration Map verifies every extension point against current code; this document adds the concrete excerpts the planner should lift into plan `<read_first>` lists. The dominant pattern: **Phase 2 adds new closed vocabularies, producers, and adapters beside Phase 1 mechanisms — it does not generalize or weaken them.** `build_dry_run_runtime`, schema `"1"`/`"2"` preimages, the 9-stage `PipelineStage` vocabulary, and every Phase 1 test stay byte-for-byte intact.

One deliberate discrepancy to note: `02-RESEARCH.md` cites identity `schema_version` `"2"` (`src/skillscout/domain/models.py:248`), while the SQLite store itself is at `PRAGMA user_version = 3` (`tests/test_cli_dry_run.py:76`; the pipeline docstring says "schema-v3 contracts"). These are two different version axes — identity/producer schema vs. DB physical schema. Phase 2 touches only the identity axis; no DB migration is needed.

## File Classification

| Planned File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `pyproject.toml` / `uv.lock` (modify) | config | dependency declaration | `pyproject.toml:10-12` exact pin + Phase 1 two-gate ceremony | exact |
| `src/skillscout/domain/subjects.py` (new) | domain contract | file-I/O → strict model | `src/skillscout/adapters/fixtures.py:36-57, 70-123` (`FixtureSubject`, `load_fixture`) | strong |
| `src/skillscout/domain/filtering.py` (new) | domain contract | pure transform | `domain/models.py:123-132` + `domain/enums.py:8-17` closed vocabulary + versioned-policy constant (`pipeline.py:54`) | strong |
| `src/skillscout/domain/reading.py` (new) | domain contract | pure transform | `domain/models.py:27-33` bounded constants + `StrictFrozenModel` | strong |
| `src/skillscout/domain/extraction.py` (new) | domain contract | pure transform, hashing | `domain/models.py` (`StrictFrozenModel`, `Digest`) + `domain/canonical.py:36-46` preimage hashing | strong |
| `src/skillscout/domain/enums.py` (modify) | domain contract | closed lifecycle | `domain/enums.py:33-58` (`RunStatus` + `_RUN_TRANSITIONS`) | exact |
| `src/skillscout/domain/models.py` (modify) | domain contract | registration | `domain/models.py:35-37` (`SUPPORTED_PRODUCER_SCHEMAS`) | exact |
| `src/skillscout/application/ports.py` (modify) | provider contract | request-response | `ports.py:22-59` (`ErrorCode`/`ERROR_SUMMARIES`), `ports.py:104-112` (`StageProcessor`) | exact |
| `src/skillscout/application/pipeline.py` (modify) | application runner | batch, orchestration | itself: `pipeline.py:243-253` (stage loop), `277-301` (attempt), `529-574` (composition root) | exact |
| `src/skillscout/adapters/github.py` (new) | provider adapter | network read → mapped payload | `adapters/fixtures.py:126-149` (scope-declaring processor) + `ports.py:73-101` (`ScopedAdapter`/`AdapterRegistration`) | structural (no HTTP analog exists) |
| `src/skillscout/adapters/openai_extract.py` (new) | provider adapter | network read → structured parse | same as `github.py` + telemetry fields `domain/models.py:186-191` | structural |
| Scout/Filter/Reader/Extractor processors (new module, name fixed at plan time) | application stage processors | transform via adapter | `adapters/fixtures.py:126-149` (`FixtureProcessor`) + `ports.py:104-112` (`StageProcessor`) | strong |
| `src/skillscout/adapters/fixtures.py` (modify) | provider adapter | signature bump only | itself: `FixtureProcessor.process` ignores the new context | exact |
| `src/skillscout/cli.py` (modify) | controller | request-response, file-I/O | `cli.py:36-50` (`build_parser`), `cli.py:53-86` (`main`) | exact |
| extraction-summary writer (in `pipeline.py`) | application durability | atomic file-I/O | `pipeline.py:440-526` (`_acquire_publication_lock` + `_write_publication_plan`) | exact |
| `tests/fixtures/subject/approved.json` (new) | test fixture | file-I/O | `tests/fixtures/pipeline/approved.json` | exact |
| `tests/fixtures/github/` (new) | test fixture | recorded transport | `tests/fixtures/state/v1-cli.db` + `v1-cli-provenance.json` (frozen artifact + provenance pattern) | structural |
| `tests/fixtures/openai/` (new) | test fixture | recorded transport | same as above | structural |
| `tests/fixtures/injection/` (new) | test fixture | adversarial corpus | hostile-canary pattern `tests/test_cli_dry_run.py:303-344` | strong |
| Contract unit tests (new, e.g. `tests/test_phase2_contracts.py`) | test | transform | `tests/test_stage_contracts.py:47-154` builder helpers | exact |
| GitHub/Reader/Extractor adapter tests (new) | test | request-response at MockTransport seam | `tests/test_side_effect_policy.py:74-100` (rejection-before-invocation) + `tests/conftest.py:22-38` (socket sentinel) | structural |
| Pipeline/CLI/security tests (new) | test | batch, CRUD, file-I/O | `tests/test_pipeline_resume.py:115-129` (canary processor), `tests/test_cli_dry_run.py`, `tests/test_cli_security.py` | exact |

## Pattern Assignments

### Plan 1 — Dependency gate and frozen domain contracts

#### `pyproject.toml` / `uv.lock` — dependency declaration

**Analog:** `pyproject.toml:1-21`

```toml
[build-system]
requires = ["uv_build==0.11.29"]
build-backend = "uv_build"

[project]
name = "skillscout"
version = "0.1.0"
requires-python = ">=3.13,<3.14"
dependencies = [
    "pydantic==2.13.4",
]
```

Replicate: exact `==` pins only, no extras/URL sources; `httpx` and `openai` enter `dependencies` the same way. The lock update must repeat the Phase 1 two-gate ceremony (non-building discovery `uv lock --no-build --no-sources --no-cache --managed-python --no-python-downloads --python 3.13.14`, human review of every new node's artifacts, then build/test) with the full inline prefix `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"`. Dev tooling stays in `[dependency-groups] dev` — httpx's `MockTransport` is first-party, so no test-only HTTP dependency is added.

#### `src/skillscout/domain/subjects.py` — `RepositorySubject` + `load_subject`

**Analog A (contract shape):** `src/skillscout/adapters/fixtures.py:36-57`

```python
class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FixtureSource(_StrictModel):
    repository: RepositoryUrl
    commit_sha: CommitSha
    license: Literal["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"]


class FixtureSubject(_StrictModel):
    schema_version: Literal["1"]
    subject_id: FixtureId
    source: FixtureSource
    workflow: FixtureWorkflow
```

Reusable bounded types already exist in the same file: `RepositoryUrl` (`^https://github\.com/...`, fixtures.py:22-29), `CommitSha` (40-hex, fixtures.py:30). `RepositorySubject` reuses the `RepositoryUrl` pattern; `subject_id` follows the namespaced-ID convention (`fixture:` prefix at fixtures.py:18-21 → `repo:owner/name`).

**Analog B (bounded single-descriptor read):** `src/skillscout/adapters/fixtures.py:70-113` — `lstat` → reject symlink/non-regular → open once with `O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC` → `fstat` the same descriptor → size cap (`MAX_FIXTURE_BYTES = 65_536`, fixtures.py:17) → chunked read with `cap + 1` overflow probe → post-read identity recheck → strict decode/parse, with every failure mapped:

```python
        after_fd = os.fstat(descriptor)
        if _identity(before_fd) != _identity(after_fd):
            raise SafeFailure(ErrorCode.FIXTURE_CHANGED)

        raw = b"".join(chunks)
        try:
            decoded = raw.decode("utf-8")
            parsed: Any = json.loads(decoded)
            return FixtureSubject.model_validate(parsed, strict=True)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            raise SafeFailure(ErrorCode.INVALID_FIXTURE) from None
```

`load_subject` copies this shape, mapping failures to the new `INVALID_SUBJECT` code. Note the layering choice: `FixtureSubject`/`load_fixture` live in `adapters/`, but RESEARCH places `RepositorySubject` in `domain/` because it is the phase-two run authority; the file-I/O loader half still follows the adapter pattern. Runner identity needs no model change — `fixture_hash = sha256_digest(subject.model_dump(mode="json", exclude_none=False))` (`pipeline.py:209`) works for any Pydantic subject.

#### `src/skillscout/domain/filtering.py` — `FilterPolicy` and rule results

**Analog (closed, versioned, pure):** `src/skillscout/domain/enums.py:8-17` for the closed rule vocabulary plus the versioned-constant convention:

```python
class PipelineStage(StrEnum):
    SCOUT = "scout"
    FILTER = "filter"
    READER = "reader"
    EXTRACTOR = "extractor"
    QUALIFIER = "qualifier"
```

and `src/skillscout/application/pipeline.py:54` (`RETRY_POLICY_VERSION = "retry-v1"`) for the `filter-policy-v1` version string. Rule result records are `StrictFrozenModel`s (`domain/models.py:123-126`):

```python
class StrictFrozenModel(BaseModel):
    """One fail-closed configuration for every persisted domain object."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
```

Filter is a **pure function** over Scout's payload — no I/O except the one Filter-owned license GET, which RESEARCH assigns to the adapter, not the policy. The `pass|fail|not_applicable` closed result set and `outcome: "accepted" | "rejected"` payload mirror the existing outcome convention in `FixtureProcessor` (`"outcome": "accepted"`, fixtures.py:144-148).

#### `src/skillscout/domain/reading.py` — `ReaderPolicy`, tiers, classification

**Analog:** the bounded-constant block `src/skillscout/domain/models.py:27-33`

```python
MAX_MANIFEST_BYTES = 262_144
MAX_STAGE_PAYLOAD_DEPTH = 16
MAX_STAGE_PAYLOAD_NODES = 4_096
MAX_STAGE_COLLECTION_ITEMS = 1_024
MAX_STAGE_KEY_BYTES = 256
MAX_STAGE_STRING_BYTES = 65_536
MAX_STAGE_INTEGER_ABS = 9_007_199_254_740_991
```

Budget knobs (`max_files=25`, `max_source_files=5`, `max_file_bytes=131_072`, `max_total_bytes=524_288`, `max_estimated_input_tokens=40_000`) are module constants on a frozen `ReaderPolicy` model with version `reader-policy-v1` — org ceilings, never per-run operator input (same reason `--fail-after` choices come from the closed `STAGE_SEQUENCE`, cli.py:45). Tier order and the closed extension allowlist are frozen tuples/sets; `stop_reason` is a closed `StrEnum` or `Literal` set, matching the enum-first convention. The existing payload bounds above are also the structural proof that full text can never persist: Reader's persisted payload carries metadata + bounded excerpts only.

#### `src/skillscout/domain/extraction.py` — `ExtractorResponse`, `WorkflowSpec`, fingerprint, boundary validation

**Analog A (hashing):** `src/skillscout/domain/canonical.py:24-40`

```python
def canonical_json_bytes(value: object) -> bytes:
    """Encode the sole canonical JSON form, retaining explicit null fields."""

    return json.dumps(
        _json_compatible(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_digest(value: object) -> str:
    """Return a tagged lowercase SHA-256 over canonical bytes or supplied bytes."""
```

Fingerprint = keyword-only preimage function over `sha256_digest`, exactly like `reusable_key_digest` (canonical.py:93-111) and `make_result_id` (canonical.py:114-134), with the version string (`wf-fingerprint-v1`) inside the preimage. **Analog B (identity type):** `Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]` (models.py:12) for `blob_sha`/`content_hash` fields. `ExtractorResponse`/`WorkflowSpec` are `StrictFrozenModel`s; Structured-Outputs constraints (all-required fields, null-unions, `workflows` maxItems 3) are expressed with `Field(max_length=3)` and `str | None` — the single Pydantic source from which the LLM schema is generated, per RESEARCH §Don't Hand-Roll.

#### `src/skillscout/domain/enums.py` (modify) — `RunStatus.COMPLETED`

**Analog:** `src/skillscout/domain/enums.py:33-58`

```python
class RunStatus(StrEnum):
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    PLANNED_NOT_PUBLISHED = "planned_not_published"

...
_RUN_TRANSITIONS = {
    RunStatus.RUNNING: frozenset(
        {RunStatus.INTERRUPTED, RunStatus.FAILED, RunStatus.PLANNED_NOT_PUBLISHED}
    ),
    RunStatus.INTERRUPTED: frozenset({RunStatus.RUNNING, RunStatus.FAILED}),
    RunStatus.FAILED: frozenset(),
    RunStatus.PLANNED_NOT_PUBLISHED: frozenset(),
}
```

Add `COMPLETED = "completed"` to the enum and to the `RUNNING` successor frozenset, plus `RunStatus.COMPLETED: frozenset()`. `validate_run_transition` (enums.py:77-82) and the persisted-record validators need no change: `PersistedRunRecord` only requires diagnostics for INTERRUPTED/FAILED (models.py:264-266), and run status is stored as TEXT.

#### `src/skillscout/domain/models.py` (modify) — producer registration

**Analog:** `src/skillscout/domain/models.py:35-37`

```python
SUPPORTED_PRODUCER_SCHEMAS: frozenset[tuple[str, str]] = frozenset(
    {("1", "fixture-v1"), ("2", "fixture-v1")}
)
```

Add `("2", "phase2-v1")`. This one tuple is read by the runner's producer gate (`pipeline.py:199-207`) and by `_write_manifest` (`state.py:2200-2204`), so registration alone enables both. `PersistedRunRecord.schema_version: Literal["1", "2"]` (models.py:248) already admits `"2"` — no migration machinery is touched.

#### `src/skillscout/application/ports.py` (modify) — `INVALID_SUBJECT` + processor protocol

**Analog A (error vocabulary):** `src/skillscout/application/ports.py:22-59`

```python
class ErrorCode(StrEnum):
    """The complete schema-v1 diagnostic vocabulary."""

    INVALID_CLI_ARGUMENTS = "invalid_cli_arguments"
    INVALID_FIXTURE = "invalid_fixture"
    ...

ERROR_SUMMARIES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_CLI_ARGUMENTS: "Command-line arguments were rejected.",
    ErrorCode.INVALID_FIXTURE: "Fixture input was rejected.",
    ...
}

if not all(summary.isascii() and len(summary) <= 160 for summary in ERROR_SUMMARIES.values()):
    raise RuntimeError("unsafe diagnostic summary configuration")
```

Add `INVALID_SUBJECT = "invalid_subject"` + fixed summary `"Subject input was rejected."`; the import-time ASCII/≤160 guard and the closed-vocabulary test (`tests/test_cli_security.py:519`) enforce the rest. All GitHub/OpenAI raw exceptions collapse into existing `STAGE_TRANSIENT_FAILURE`/`STAGE_PERMANENT_FAILURE`/`STAGE_OUTPUT_INVALID` — no new remote-error codes.

**Analog B (protocol):** `src/skillscout/application/ports.py:104-112`

```python
class StageProcessor(Protocol):
    """Provider-independent deterministic stage processor."""

    producer_version: str

    def process(
        self,
        stage_input: StageInput,
    ) -> Mapping[str, Any]: ...
```

Phase 2 extends to `process(stage_input, context) -> StageOutcome` (RESEARCH §Integration Map row 4). `StageOutcome` is a new frozen carrier: `payload: Mapping` + optional `StageTelemetry(prompt_version, policy_version, model_id, request_id, latency_ms, token_usage)` — field-for-field the nullable telemetry already on `StageAttempt` (models.py:186-191) and `StageEnvelope` (models.py:158-161). The context carrier is **runtime-only**: it must not subclass any persisted model and must never be canonicalized — the existing `StagePayload`/`MAX_MANIFEST_BYTES` bounds (models.py:27-33, 109-120) structurally enforce that only bounded JSON reaches the ledger.

### Plan 2 — Runner generalization, GitHub adapter, Scout/Filter

#### `src/skillscout/application/pipeline.py` (modify) — profile slice, telemetry, phase-two root

**Analog A (stage loop to slice):** `src/skillscout/application/pipeline.py:243-253`

```python
        for stage_index, stage in enumerate(PipelineStage):
            if stage_index < start_index:
                continue
            stage_input = StageInput(
                schema_version=schema_version,
                execution_mode=ExecutionMode.DRY_RUN,
                subject_id=subject.subject_id,
                stage=stage,
                previous_output_hash=previous_output_hash,
                fixture_hash=fixture_hash if stage_index == 0 else None,
            )
```

Replace `enumerate(PipelineStage)` with `enumerate(profile_stages)` where the profile is a **closed constant** resolved from `producer_version` (`{"fixture-v1": tuple(PipelineStage), "phase2-v1": (SCOUT, FILTER, READER, EXTRACTOR)}`), keeping **global** stage indices — `PersistedAttemptRecord` validates `stage_index == tuple(PipelineStage).index(stage)` (models.py:302-303) and `_commit_success` requires contiguous indices from checkpoint state (state.py:2239-2254), so a sliced profile must yield stages in spine order starting at index 0. Terminal status becomes `COMPLETED` for `phase2-v1` at the analog of pipeline.py:403-404; `PLANNED_NOT_PUBLISHED` + the publication writer stay fixture-only.

**Analog B (telemetry hardcoded None — the exact seams to populate):** `pipeline.py:290-296` (attempt) and `pipeline.py:321-332, 343-364` (envelope/output hash):

```python
                started_at=self.clock.now(),
                finished_at=None,
                prompt_version=None,
                policy_version=None,
                model_id=None,
                request_id=None,
                latency_ms=None,
                token_usage=None,
```

```python
                payload = StagePayload.model_validate(output).root
                output_hash = stage_output_hash(
                    schema_version=schema_version,
                    subject_id=subject.subject_id,
                    stage=stage,
                    producer_version=producer_version,
                    prompt_version=None,
                    policy_version=None,
                    model_id=None,
                    payload=payload,
                )
```

Copy `StageOutcome.telemetry` into all three places. `stage_output_hash` schema `"2"` already mixes these fields (canonical.py:72-83), so the hash preimage is unchanged. Business rejections (filter rejected, refusal, schema failure) flow through as **succeeded attempts with outcome payloads** — they must not raise, or they would consume the 3-attempt `RetryPolicy` budget (pipeline.py:61-73, 269-274).

**Analog C (composition root):** `src/skillscout/application/pipeline.py:529-574`

```python
def build_dry_run_runtime(
    state: SQLiteStateStore,
    processor: FixtureProcessor,
    *,
    retry_policy: RetryPolicy | None = None,
) -> DryRunRuntime:
    """Construct the closed Phase 1 runtime under its immutable authority ceiling."""

    resolved_clock = SystemClock()
    ...
    try:
        complete_registry = (
            AdapterRegistration("fixture_processor", processor),
            AdapterRegistration("sqlite_and_manifests", state),
            AdapterRegistration("clock", resolved_clock),
            AdapterRegistration("run_ids", resolved_ids),
            AdapterRegistration("local_publication_planner", publication_writer),
        )
    except ValueError:
        raise SafeFailure(ErrorCode.FORBIDDEN_EFFECT_SCOPE) from None

    resolved_policy = SideEffectPolicy.phase_one()
    validated = resolved_policy.validate(complete_registry)
    expected_types = (
        FixtureProcessor,
        SQLiteStateStore,
        SystemClock,
        UUIDIdProvider,
        _LocalPublicationPlanner,
    )
```

`build_phase_two_runtime` mirrors this exactly: closed registry (`phase2_processor`, `sqlite_and_manifests`, `github_read`, `openai_extract`, `clock`, `run_ids`, `extraction_summary_writer`), concrete `type(...) is not expected` checks, and a new `SideEffectPolicy.phase_two()` over `PHASE_TWO_MAX_SCOPES = {NONE, LOCAL_STATE, REMOTE_READ}` beside `PHASE_ONE_MAX_SCOPES` (pipeline.py:55-57) and `SideEffectPolicy.phase_one()` (pipeline.py:119-121). No caller-selected policy or registrations — Phase 1 tests assert those raise `TypeError` (`test_side_effect_policy.py:136-162`); add the phase-two equivalents. `build_dry_run_runtime` itself stays untouched.

#### `src/skillscout/adapters/github.py` — `GitHubReadClient`

**Analog (capability declaration):** `src/skillscout/adapters/fixtures.py:126-134` and `src/skillscout/adapters/state.py:562-564`

```python
class FixtureProcessor:
    """Deterministic local processor with no provider or execution capability."""

    producer_version = "fixture-v1"

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.NONE
```

```python
    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.LOCAL_STATE
```

`GitHubReadClient.effect_scope = EffectScope.REMOTE_READ` — declared as a property on the adapter, never caller-supplied (`AdapterRegistration.__post_init__` derives scope from the adapter and rejects non-`ScopedAdapter`s, ports.py:81-101). Additional conventions to replicate:

- **Closed endpoint set:** module-level templated paths (`/repos/{owner}/{repo}` etc.) against a fixed `https://api.github.com` base — no caller-supplied URLs, mirroring how the CLI only accepts closed `choices` (cli.py:45).
- **Error mapping:** every `httpx` exception and non-2xx status collapses to `SafeFailure` with an existing code, `raise ... from None` (fixtures.py:112-117 is the canonical mapping block). 429/5xx/timeout → `STAGE_TRANSIENT_FAILURE` (retryable under the existing digest-scoped `RetryPolicy`); business facts (license 404, `truncated=true`) are payload data, not failures.
- **Credentials:** token read once at construction from the environment, held only as a client header — never a field on any domain object (canary-test target).
- **Timeouts + serial requests** on one `httpx.Client`; construction accepts a transport so tests inject `httpx.MockTransport` without monkeypatching.

There is no HTTP analog in the codebase — this is Phase 2's one genuinely new mechanic. The boundary discipline analog is `tests/conftest.py:22-38` (below): the socket sentinel stays on for all non-adapter tests, so only adapter test modules may construct a real (MockTransport-backed) client.

#### Scout/Filter processors + `src/skillscout/adapters/fixtures.py` (modify)

**Analog:** `src/skillscout/adapters/fixtures.py:135-149`

```python
    def process(
        self,
        stage_input: StageInput,
    ) -> dict[str, object]:
        return {
            "schema_version": stage_input.schema_version,
            "stage": stage_input.stage.value,
            "subject_id": stage_input.subject_id,
            "previous_output_hash": stage_input.previous_output_hash,
            "outcome": (
                "accepted"
                if stage_input.stage.value != "publication_planner"
                else "planned_not_published"
            ),
        }
```

Scout/Filter/Reader/Extractor processors (one new module, `producer_version = "phase2-v1"`) follow this shape: read `stage_input.stage`, dispatch internally, return a bounded JSON payload dict. `FixtureProcessor` gets the signature bump to `process(stage_input, context) -> StageOutcome` and simply ignores `context` — one protocol serves both producers. Downstream-skip is structural: Reader/Extractor return `{"outcome": "skipped", ...}` deterministically when the context's filter verdict is `"rejected"`, with zero adapter calls (call-count assertion is the FILT-03 proof).

### Plan 3 — Budgeted Reader

Covered by the `domain/reading.py` and processor patterns above. Reader-specific mechanical analogs:

- **Size-before-fetch:** the tree entry's `size` gates the blob GET, the same discipline as `load_fixture` checking `before_fd.st_size > MAX_FIXTURE_BYTES` before reading (fixtures.py:89-90) and `read_bytes` re-checking with a `cap + 1` probe (localfs.py:267-276).
- **Path validation:** tree paths are validated like `AnchoredDirectory.validate_child_name` (localfs.py:174-185) — reject absolute, `..`, empty segments, separators-in-name — extended to full relative paths (RESEARCH §Pattern 4: backslash, NUL/control, >512 chars).
- **Deterministic order:** path-sorted within tier; fixed tier tuple — same "closed ordered vocabulary" style as `PipelineStage`.

### Plan 4 — Extractor, CLI, acceptance

#### `src/skillscout/adapters/openai_extract.py` — `OpenAIExtractionClient`

Same adapter conventions as `github.py` plus:

- `effect_scope = EffectScope.REMOTE_READ` (a structured extraction call mutates no remote state).
- Constructed with a custom `http_client` so tests reuse `httpx.MockTransport`; exactly one `responses.parse(..., text_format=ExtractorResponse, store=False)` call site, no `tools` key — request shape asserted in tests.
- Telemetry extraction (`response.id`, `response.model`, `response.usage`, measured latency) returned to the processor for `StageOutcome.telemetry`; refusal/incomplete/schema-invalid are **outcome data**, not exceptions.
- `OPENAI_API_KEY` read once at construction; header-only.

#### `src/skillscout/cli.py` (modify) — `extract-repo` subcommand

**Analog:** `src/skillscout/cli.py:36-50, 53-86`

```python
def build_parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(prog="skillscout")
    commands = parser.add_subparsers(
        dest="command", required=True, parser_class=SafeArgumentParser
    )
    dry_run = commands.add_parser("dry-run")
    dry_run.add_argument("--fixture", required=True, type=Path)
    dry_run.add_argument("--state", required=True, type=Path)
    dry_run.add_argument("--output", required=True, type=Path)
    dry_run.add_argument("--fail-after", choices=STAGE_SEQUENCE)
```

```python
        else:
            subject = load_fixture(arguments.fixture)
            state = SQLiteStateStore(arguments.state)
            runtime = build_dry_run_runtime(state, FixtureProcessor())
            payload = runtime.runner.run(
                subject,
                arguments.output,
                fail_after=arguments.fail_after,
            ).as_dict()
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 0
    except SafeFailure as failure:
        print(
            json.dumps({"error": failure.as_dict()}, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 1
```

`extract-repo --subject <path> --state <db> --output <dir> [--fail-after {scout,filter,reader,extractor}]` slots in as a sibling branch: `load_subject` → `SQLiteStateStore` → `build_phase_two_runtime` → `runner.run(...)`. `--fail-after` choices come from the phase-two stage subset constant, never free text. All output stays compact sorted-key JSON on stdout; errors stay `SafeFailure`-only on stderr with exit 1; argparse rejection stays exit 2 through `SafeArgumentParser` (cli.py:19-33), which discards the rejected input. Credentials are never CLI flags — environment only.

#### Extraction-summary writer (in `pipeline.py`)

**Analog:** `src/skillscout/application/pipeline.py:468-526` (`_write_publication_plan`) — canonical JSON + `\n`, byte cap (`MAX_PUBLICATION_PLAN_BYTES = 65_536`, pipeline.py:58), `AnchoredDirectory.open(create=True)`, kernel-flock sidecar lock (`.<name>.lock`, pipeline.py:440-466), stale-temp recovery, read-previous-then-`atomic_write` with `restore_bytes` backup, `filesystem_seam` trip points, and `(DurableWriteError, OSError)` → `SafeFailure(STATE_OPERATION_FAILED) from None`. `extraction-summary.json` reuses this verbatim with its own byte cap; the summary contains run identity, per-stage outcomes, workflow fingerprints and counts — never excerpts beyond policy bounds (the durable-surface sweep tests enforce this).

### Test fixtures and test modules

#### `tests/fixtures/subject/approved.json`

**Analog:** `tests/fixtures/pipeline/approved.json` (full file)

```json
{
  "schema_version": "1",
  "subject_id": "fixture:approved-workflow",
  "source": {
    "repository": "https://github.com/example/approved-workflow",
    "commit_sha": "0123456789abcdef0123456789abcdef01234567",
    "license": "MIT"
  },
  "workflow": { "goal": "Transform a bounded structured request ...", ... }
}
```

Same shape discipline: hand-authored, minimal, non-executable, one happy-path subject (`repo:owner/name` ID, repository URL, optional `ref`). Negative subjects are built inline in tests by mutation (the `_stage_input(**changes)` builder convention below), not as fixture files.

#### `tests/fixtures/github/`, `tests/fixtures/openai/` — recorded transport responses

**Analog:** the frozen-artifact + provenance pair `tests/fixtures/state/v1-cli.db` + `v1-cli-provenance.json`, and its consumer `tests/test_cli_dry_run.py:439` (`test_frozen_v1_cli_fixture_matches_provenance`). Recorded JSON bodies live in the repo (reviewable, deterministic); a small loader in `tests/conftest.py` maps `(method, path)` → recorded `httpx.Response` inside an `httpx.MockTransport` handler. Variant sets (`archived`, `fork`, `private`, `no_readme`, `license_noassertion`, `license_multiple_files`, `tree_truncated`, `rate_limited`, `renamed`; OpenAI: `parsed_2_workflows`, `parsed_zero_workflows`, `refusal`, `incomplete_max_tokens`, `schema_invalid`, `compromised_*`) follow the RESEARCH §Required fixtures list. Recorded-transport call counts double as resume/no-replay evidence — the same assertion style as `CanaryProcessor.calls` in `test_pipeline_resume.py`.

#### `tests/fixtures/injection/` — adversarial corpus + canaries

**Analog:** `tests/test_cli_dry_run.py:303-344`

```python
    credential = "github_pat_DO_NOT_DISCLOSE_123456789"
    attacker_path = "/attacker/selected/private/path"
    raw = (
        json.dumps(
            {
                "schema_version": "1",
                "subject_id": credential,
                ...
            }
        ).encode()
        if pydantic_invalid
        else (b'{"hostile":"' + credential.encode() + b'","path":"' + attacker_path.encode())
    )
    ...
    _assert_sanitized_error(result, ErrorCode.INVALID_FIXTURE)
    surfaces = (
        result.stdout.encode()
        + result.stderr.encode()
        + _all_file_bytes(tmp_path, exclude={fixture})
    )
    assert credential.encode() not in surfaces
    assert attacker_path.encode() not in surfaces
    assert not (tmp_path / "state.db").exists()
```

The injection corpus (RESEARCH's 8 attack classes) becomes markdown files with two sentinel strings: `CANARY_FULL_TEXT_SENTENCE` (asserted absent from every durable surface via `_all_file_bytes`, test_cli_dry_run.py:30-36) and `CANARY_EVIDENCE_SENTENCE` (asserted present only as a bounded excerpt). Secret canaries for `SKILLSCOUT_GITHUB_TOKEN`/`OPENAI_API_KEY` follow the exact credential-shape convention above. Note the parametrized `pydantic_invalid` style — one test body, two hostile encodings.

#### New test modules — contract, adapter, pipeline, CLI, security

- **Contract unit tests** — analog `tests/test_stage_contracts.py:58-104`: module-level builder helpers with `values.update(changes)` then `Model.model_validate(values)`; strictness/extras rejection via `pytest.raises(ValidationError)`; independent recomputation (`_digest` at test_stage_contracts.py:47-55) to prove hash stability rather than trusting the implementation.
- **Capability/registration tests** — analog `tests/test_side_effect_policy.py:74-88`: `pytest.raises(SafeFailure)` + `failure.value.code is ErrorCode.FORBIDDEN_EFFECT_SCOPE` + `canary.calls == 0` (rejection **before** invocation); registry-order/type assertions at test_side_effect_policy.py:202-232.
- **Pipeline tests** — analog `tests/test_pipeline_resume.py:115-129`: inner-class `CanaryProcessor(FixtureProcessor)` that records `calls` and raises `AssertionError` if a durable stage is replayed; direct SQLite verification through `_connect` (test_cli_dry_run.py:45-48); four-stage slice asserted with **global** indices; `COMPLETED` terminal; LLM call count 0 after filter rejection.
- **CLI tests** — analog `tests/conftest.py:41-64` (`run_cli` subprocess, `parse_cli_json`/`parse_cli_error`) and `test_cli_dry_run.py:51-128` (happy path + durable-state assertions). Both subprocess and in-process `cli.main([...])` styles exist (test_cli_dry_run.py:359-370); use subprocess for the new happy path, in-process + `monkeypatch` for hostile injection.
- **Socket sentinel** — `tests/conftest.py:22-38` stays autouse-by-explicit-request for every non-adapter test module; adapter tests use MockTransport only, so no test ever dials out (RESEARCH §Sampling policy: no live network in pytest, ever).

## Shared Patterns

### Closed vocabularies and versioned producers

**Source:** `domain/enums.py`, `domain/models.py:35-37`, `pipeline.py:53-58`  
**Apply to:** all new Phase 2 modules

Every enumerated fact is a `StrEnum` or `Literal` set with a transition/successor validator; every behavior-changing rule set carries a version string (`fixture-v1`, `retry-v1`, schema `"1"`/`"2"` → `filter-policy-v1`, `reader-policy-v1`, `extract-prompt-v1`, `wf-fingerprint-v1`, `phase2-v1`). New versions are additive members of existing closed sets; nothing is renamed or removed.

### Structured fail-closed errors

**Source:** `ports.py:22-70`, all adapters' `except ... raise SafeFailure(...) from None` blocks  
**Apply to:** `github.py`, `openai_extract.py`, `subjects.py` loader, CLI, processors

Raw `httpx`/SDK/`OSError` exceptions never cross a boundary. Public failures are `SafeFailure` with a code from the closed `ErrorCode` enum; summaries are fixed ASCII ≤160 chars enforced at import time; `raise ... from None` suppresses internal chains. Remote infrastructure failures map to `STAGE_TRANSIENT_FAILURE` (retryable) or `STAGE_PERMANENT_FAILURE`; contract violations to `STAGE_OUTPUT_INVALID`; business rejections are **not errors** — they are succeeded attempts with `outcome` payloads.

### Deterministic content identity

**Source:** `domain/canonical.py` (whole module)  
**Apply to:** fingerprint, subject identity, any new hash

One canonical JSON path (`sort_keys`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False`); tagged `sha256:` digests; keyword-only explicit preimages that name every hashed field; hash fields excluded from their own preimage. Telemetry (request IDs, latency, timestamps) never enters semantic identity — `stage_output_hash` schema `"2"` is the template.

### Capability omission and declared scopes

**Source:** `ports.py:73-101`, `pipeline.py:113-129, 529-574`, `AGENTS.md` constraints  
**Apply to:** both new adapters, both composition roots

Adapters declare `effect_scope` as a property; `AdapterRegistration` derives scope from the adapter; the policy validates the closed registry before any invocation; concrete `type(...) is` checks reject subclasses/mocks at the root; callers cannot inject policies or extra registrations (TypeError). Phase 2 admits `REMOTE_READ` only through `SideEffectPolicy.phase_two()` in the new root; `REMOTE_WRITE` remains rejected everywhere, and the Phase 1 root keeps its ceiling unchanged.

### Runtime-only context; bounded durable surfaces

**Source:** `domain/models.py:27-33, 109-120`, `state.py:2191-2231`, `pipeline.py:303-332`  
**Apply to:** the context carrier, Reader/Extractor payloads, extraction summary

Everything persisted passes through `StagePayload` validation (JSON-only, depth/node/collection/string bounds) and `validate_manifest_bytes` (≤256 KiB) before `atomic_write`. The raw read bundle lives only in the runtime context object and is never canonicalized, logged, or persisted — the bounds make full-text persistence structurally impossible, and the canary sweep proves it behaviorally.

### Module and comment conventions

Observed across all of `src/skillscout/`:

- One-line module docstring stating the module's closed scope (`"""Strict immutable contracts crossing SkillScout pipeline boundaries."""`); test modules name the contract they pin (`"""Composition-time authority checks for the Phase 1 dry-run runtime."""`).
- `from __future__ import annotations` first; stdlib → third-party → `skillscout.*` import groups; `typing.Final` for module constants.
- Docstrings are single-sentence behavioral contracts (`"""Return the successor only when it is the next closed pipeline stage."""`), not narrative; comments are sparse and explain invariants, not mechanics.
- Names: `UPPER_SNAKE` constants with explicit units (`MAX_STAGE_STRING_BYTES`), `snake_case` functions prefixed by role (`validate_*`, `make_*`, `stage_*_hash`, `build_*_runtime`, `load_*`), `_leading_underscore` for module-private helpers.
- Line length 100 (`pyproject.toml:29`); Ruff clean is a plan-end gate.

### Self-contained uv invocation

**Source:** `02-VALIDATION.md` §Test Infrastructure (carried over from Phase 1)  
**Apply to:** every command in every Phase 2 task `<automated>` verification

```text
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv"
```

`--locked` wherever supported; never ambient `PATH`, activated environments, or system Python. Full plan-end gate: `pytest -q && ruff check . && uv lock --check && uv build --no-sources` (all under the prefix), plus the two CLI demonstrations RESEARCH §Sampling policy requires before phase verification.

## Generated and Runtime Artifacts (Not Implementation Analogs)

| Artifact | Producer | Pattern |
|---|---|---|
| `uv.lock` (updated) | Plan 1 non-building lock discovery + human gate | Same ceremony as Phase 1 Gate B: every new node registry-only, all artifact URLs/hashes/sizes reviewed before any sync/build/import/test. |
| `tests/fixtures/github/*.json`, `tests/fixtures/openai/*.json` | Plan 2/4 fixture authoring | Hand-reviewed recorded responses treated as frozen test artifacts; transport call counts are the replay evidence. |
| `<db-stem>.manifests/<stage>/<manifest-hash>.json` | `SQLiteStateStore` | Reused as-is; Reader/Extractor manifests contain metadata + bounded excerpts only. |
| `extraction-summary.json` + `.<name>.lock` | phase-two summary writer | Same locked/atomic/fsync pattern as `publication-plan.json`; `tests/test_cli_dry_run.py:118-128` shows the expected on-disk file set assertion style. |
| Working SQLite state (`user_version=3`) | state adapter | No migration; identity `schema_version` stays `"2"` for `phase2-v1`. |

## Planner Guardrails

1. **Do not touch Phase 1 mechanics:** `build_dry_run_runtime`, `PHASE_ONE_MAX_SCOPES`, the 9-stage `PipelineStage` vocabulary, schema `"1"`/`"2"` hash preimages, SQLite physical schema (`user_version=3`), the resume-event ledger, and every existing test stay unchanged. Phase 2 adds beside, never edits within — the one sanctioned exception is the additive set members (`COMPLETED`, `INVALID_SUBJECT`, `("2","phase2-v1")`) and the `StageProcessor` signature bump, whose `FixtureProcessor` update keeps Phase 1 green.
2. **Keep global stage indices in the profile slice.** `PersistedAttemptRecord` (models.py:302) and `_commit_success` (state.py:2247-2253) both bind `stage_index` to `tuple(PipelineStage).index(stage)`; the `phase2-v1` profile must be a spine-ordered prefix starting at index 0, derived from `producer_version`, never from operator input.
3. **Business rejections are succeeded attempts.** Filter rejection, `no_workflow`, refusal, incomplete, and schema failure return outcome payloads; only infrastructure errors raise `SafeFailure`. This is what keeps resume from re-calling the LLM and what makes the "hard gates never reach the LLM" skip-outcome test meaningful.
4. **No new dependencies beyond `httpx` and `openai`, admitted only through the two-gate lock ceremony.** Explicitly not: `tiktoken`, any GitHub SDK, tenacity/retry libraries, VCR/cassette libraries (RESEARCH §Don't Hand-Roll). The existing `RetryPolicy` owns retry; `httpx.MockTransport` is the only HTTP seam.
5. **Credentials are environment-read once at adapter construction and exist only as client headers.** No credential in domain objects, payloads, manifests, logs, stdout, or CLI flags; the canary-secret sweep (`_all_file_bytes` pattern) covers every emitted byte, including request bodies captured by the mock transport.
6. **The raw read bundle never persists.** Reader/Extractor payloads carry paths, blob SHAs, content hashes, sizes, and bounded excerpts; the context carrier is runtime-only. Do not add a "debug bundle" artifact.
7. **Request shape is a tested contract:** no `tools` key, `store=False`, strict `text.format` generated from the Pydantic model (not hand-written), repo text only in the user role inside untrusted delimiters, versioned developer instructions.
8. **Every URL after pinning embeds the 40-hex SHA** — a recorded-transport contract test asserts no floating branch ref reappears (READ-01); the adapter never interpolates URLs from response fields.
9. **Assign every planned file above to an explicit task** with its analog path in `<read_first>`; keep 2–3 tasks per plan per the Phase 1 convention, with the focused-test-plus-Ruff sampling after each task and the full gate at each plan end.

## Metadata

**Analog search scope:** `src/skillscout/`, `tests/`, `pyproject.toml`, `tools/`  
**Planned files mapped:** 23 (13 new source/fixture files, 7 modifications, 3+ new test modules)  
**Existing implementation files scanned:** 10 source modules (2,644-line `state.py` sampled at cited seams), 9 test modules (4 sampled in full/part)  
**Generated tracked artifacts identified:** 2 classes (lock update, recorded fixtures)  
**Project skills found:** 0  
**Pattern extraction date:** 2026-07-21
