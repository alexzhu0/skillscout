# Phase 03: Validated Skill Candidate - Pattern Map

**Mapped:** 2026-07-22
**Scope source:** `03-RESEARCH.md`, `03-VALIDATION.md`, roadmap, requirements, state, and Phase 2 Plan 04 handoff (no `CONTEXT.md` exists)
**Files classified:** 25 logical new/modified paths or fixture groups
**Analogs found:** 23 / 25

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/skillscout/domain/qualification.py` | model + utility | transform | `src/skillscout/domain/extraction.py` | role/data-flow match |
| `src/skillscout/domain/skill_artifacts.py` | model + utility | transform + file-I/O manifest | `src/skillscout/domain/extraction.py`; identity core in `domain/canonical.py` | role/data-flow match |
| `src/skillscout/domain/validation.py` | model + service | batch + file-I/O | `src/skillscout/domain/extraction.py` boundary checks | role-match |
| `src/skillscout/domain/review.py` | model + utility | transform | `src/skillscout/domain/extraction.py` | role/data-flow match |
| `src/skillscout/adapters/openai_generate.py` | service adapter | request-response | `src/skillscout/adapters/openai_extract.py` | exact |
| `src/skillscout/adapters/openai_review.py` | service adapter | request-response | `src/skillscout/adapters/openai_extract.py` | exact |
| `src/skillscout/adapters/skills_ref.py` | service adapter | file-I/O request-response | no internal official-validator adapter | external API only |
| `src/skillscout/application/phase3.py` | service/orchestrator | event-driven + transform | `src/skillscout/application/processors.py` | exact role, extended flow |
| `src/skillscout/application/pipeline.py` | config/orchestrator | batch + event-driven | existing `phase2-v1` profile/root in same file | exact modification |
| `src/skillscout/domain/models.py` | model | transform + persistence | existing producer registry and terminal summaries in same file | exact modification |
| `src/skillscout/cli.py` | controller | request-response + file-I/O | existing `extract-repo` command in same file | exact modification |
| `pyproject.toml` | config | batch | existing exact-pin dependency declarations | exact modification, human-gated |
| `uv.lock` | config | batch | current Gate-B2 lock | exact modification, human-gated |
| `tests/recorded_transport.py` | test utility | request-response | `recorded_openai_fixture()` / `RecordedTransport` | exact modification |
| `tests/fixtures/openai/generator/*.json` | test fixture | request-response | `tests/fixtures/openai/*.json` | exact |
| `tests/fixtures/openai/reviewer/*.json` | test fixture | request-response | `tests/fixtures/openai/*.json` | exact |
| `tests/fixtures/skills/**` | test fixture | file-I/O | no existing Skill package fixture tree | no analog |
| `tests/test_qualification.py` | test | transform | contract/boundary matrices in `tests/test_openai_extract.py` | role-match |
| `tests/test_skill_generation.py` | test | transform + file-I/O | `tests/test_phase2_pipeline.py` terminal-artifact and identity tests | partial composite |
| `tests/test_skill_validation.py` | test | batch + file-I/O adversarial | `tests/test_phase2_pipeline.py` integrity/authority tests | partial composite |
| `tests/test_openai_generate.py` | test | request-response | `tests/test_openai_extract.py` | exact |
| `tests/test_openai_review.py` | test | request-response | `tests/test_openai_extract.py` | exact |
| `tests/test_phase3_pipeline.py` | test | batch + event-driven | `tests/test_phase2_pipeline.py` | exact |
| `tests/test_cli_validate_skill.py` | test | request-response + file-I/O | `tests/test_cli_extract_repo.py` | exact |
| `tests/test_cli_security.py` | test | request-response | existing subparser/non-echo assertions in same file | exact modification |

## Pattern Assignments

### `src/skillscout/domain/qualification.py` (model + deterministic policy, transform)

**Primary analog:** `src/skillscout/domain/extraction.py`

Use strict, frozen, size-bounded Pydantic contracts. Constants identify every policy/schema version; no free-form or mutable contract is persisted.

**Imports and bounded contract pattern** (`domain/extraction.py` lines 5-25, 29-42):

```python
import re
import unicodedata
from typing import Annotated, Literal, Mapping

from pydantic import Field

from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel

EXTRACT_PROMPT_VERSION = "extract-prompt-v1"
FINGERPRINT_VERSION = "wf-fingerprint-v1"
WORKFLOW_SPEC_SCHEMA_VERSION = "workflow-spec-v1"

class EvidenceRef(StrictFrozenModel):
    path: _EvidencePath
    blob_sha: _BlobSha
    excerpt: _Excerpt
    supports: _TokenText
```

**Deterministic ordered decision pattern:** copy the closed-vocabulary approach of `validate_workflow_boundaries()` (`domain/extraction.py` lines 164-217): accumulate each reason at most once, inspect all inputs, and return a tuple in stable policy order. Qualification should similarly emit every `QualificationCheck` in declared rubric order, run hard failures deterministically, and derive `passed` from `score >= 75 and not hard_failures`; never ask an LLM for points.

**Input admission:** re-parse the Extractor payload as `WorkflowSpec` before scoring. Bind repo/license/commit/evidence hashes to prior verified Scout/Filter/Reader/Extractor payloads, as `_build_workflow_spec()` binds trusted hashes at `application/processors.py` lines 692-745.

**Test analog:** use table-driven boundaries like the closed filter-policy tests; Phase 3 fixtures must pin 74/75/76, confidence 0.699/0.700, fewer than three steps, missing/hash-mismatched evidence, source execution, credential access, and unapproved side effects.

---

### `src/skillscout/domain/skill_artifacts.py` (models, deterministic rendering, identity)

**Primary analogs:** `src/skillscout/domain/extraction.py` and `src/skillscout/domain/canonical.py`

The generator may return semantic fields only. This module owns slug, frontmatter, headings, declared resource names, provenance bytes, file modes, manifests, and all identities.

**Canonical bytes and digest pattern** (`domain/canonical.py` lines 24-40):

```python
def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        _json_compatible(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

def sha256_digest(value: object) -> str:
    payload = value if isinstance(value, bytes) else canonical_json_bytes(value)
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
```

**SkillScout-owned identity pattern** (`application/processors.py` lines 692-733):

```python
fingerprint = workflow_fingerprint(
    repo_id=repo_id,
    goal=workflow.goal,
    steps=tuple(step.instruction for step in workflow.steps),
)
spec = WorkflowSpec(
    schema_version=WORKFLOW_SPEC_SCHEMA_VERSION,
    workflow_id="wf-" + fingerprint[7:23],
    fingerprint=fingerprint,
    fingerprint_version=FINGERPRINT_VERSION,
    ...
)
return spec.model_dump(mode="json", exclude_none=False)
```

Create three distinct identities:

- `lineage_id`: stable update identity from version + repo ID + normalized title + sorted evidence paths; collision or ambiguous mapping rejects.
- `artifact_id`: lineage + workflow fingerprint + generation prompt/policy/model identity + canonical semantic-draft hash.
- `package_digest`: canonical ordered `relative path -> sha256/mode/size` map over final bytes.

Do not place `package_digest` inside `references/provenance.json`; that would hash a file containing its own hash. Follow `stage_manifest_hash()` (`domain/canonical.py` lines 86-90): exclude the hash field from its own preimage.

**Renderer closed tree:** emit only `<slug>/SKILL.md`, `<slug>/references/provenance.json`, optional one-level `references/*.md`, and only if justified, text-only one-level `assets/*.md|txt|json`. Every file is regular UTF-8 mode `0644`; never emit `scripts/`, binaries, `allowed-tools`, model-selected paths, or copied executable code.

**Filesystem ownership seam:** materialization must use `AnchoredDirectory`, not `Path.write_text()`. Use child-name rejection (`adapters/localfs.py` lines 175-185), descriptor-relative child directory opens with identity checks (`197-235`), and atomic fsync/rename (`288-329`, `360-418`). If artifact package needs nested one-level directories, open each through `open_child_directory()` and validate each leaf independently.

---

### `src/skillscout/domain/validation.py` (finding schema + layered validators)

**Closest internal analog:** `src/skillscout/domain/extraction.py` boundary policy.

Copy its closed named-pattern and reason vocabulary, rather than exposing matched bytes:

**Pattern registry and bounded reason output** (`domain/extraction.py` lines 137-161):

```python
FORBIDDEN_TEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", re.compile(r"https?://", re.IGNORECASE)),
    ("shell_curl_pipe", re.compile(r"\bcurl\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b")),
    ...
)

def find_forbidden_text(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in FORBIDDEN_TEXT_PATTERNS if pattern.search(text))
```

Define strict `ValidationFinding` and `ValidationReport` models with closed severity `error|warning|info`, bounded `code`, sanitized relative `path`, bounded message/observed code, validator/policy versions, deterministic counts, and package digest. Sort findings by a fixed tuple such as `(severity rank, check family, path, code)`.

Run checks in this order:

1. Descriptor/path/type/link/mode/size/UTF-8/manifest admission.
2. Official `skills_ref.validate()` through the narrow adapter.
3. SkillScout frontmatter, name-directory, exact resource links, and progressive disclosure checks.
4. Provenance and upstream hash binding.
5. Normalized secret, injection, dangerous execution, tool authority, URL, quote registry, and over-copy checks.

Any validator exception maps to one sanitized `error` finding. Any `error` blocks Reviewer. Warnings never erase or downgrade official errors.

**Safe file-read analog** (`adapters/localfs.py` lines 247-286): `read_bytes()` performs no-follow regular-file admission, size bound, descriptor identity checks, bounded reads, and post-read stable-identity verification. Validation must inspect only a SkillScout-owned, locked package already admitted by this pattern; do not point `skills-ref` at arbitrary caller paths.

---

### `src/skillscout/domain/review.py` (review contract and pure gate)

**Analog:** `domain/extraction.py` strict structured contracts (`lines 45-71`) and `domain/models.py` strict base (`lines 123-126`).

Use `StrictFrozenModel` with `extra="forbid"`, bounded strings/tuples, `verdict: Literal["YES", "NO"]`, confidence `[0,1]`, reasons, missing assumptions, and minimal modifications. There must be no `files`, `body`, `replacement`, or patch field.

The final gate is a pure function outside the adapter:

```python
eligible_for_publication = (
    qualification.passed
    and validation.error_count == 0
    and review.status == "reviewed"
    and review.verdict == "YES"
    and review.confidence >= 0.80
)
```

Return a typed local-candidate decision only. Phase 3 must not produce `PublicationPlan`, invoke Publisher, or expose a remote-write adapter.

---

### `src/skillscout/adapters/openai_generate.py` and `openai_review.py` (service adapters, request-response)

**Exact analog:** `src/skillscout/adapters/openai_extract.py`

Keep two separate concrete clients and two separate versioned developer prompts. Do not share conversation state or client request envelopes between Generator and Reviewer.

**Construction and authority** (`openai_extract.py` lines 58-89):

```python
resolved_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
if not resolved_key or not model or max_output_tokens < 1:
    raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
self._client = openai.OpenAI(
    api_key=resolved_key,
    http_client=http_client,
    max_retries=0,
)

@property
def effect_scope(self) -> EffectScope:
    return EffectScope.REMOTE_READ
```

**One tool-less request** (`openai_extract.py` lines 97-122):

```python
response = self._client.responses.parse(
    model=self._model,
    input=[
        {"role": "developer", "content": INSTRUCTIONS_V1},
        {"role": "user", "content": user_payload},
    ],
    text_format=ResponseContract,
    store=False,
    max_output_tokens=self._max_output_tokens,
)
```

Omit `tools`; never pass credentials in the payload. Set SDK `max_retries=0`; map rate-limit/server/timeout/connection to `STAGE_TRANSIENT_FAILURE`, all other SDK errors to permanent failure (`lines 112-122`). Map refusal, incomplete, missing parsed output, and schema-invalid responses to closed returned business outcomes (`124-176`), not exceptions and not retries.

Generator input is one qualified `WorkflowSpec` plus trusted versions/facts needed by its semantic schema. Reviewer input is exactly four canonical sections: `WorkflowSpec`, rendered artifact files, provenance, and `ValidationReport`, each delimited as inert data. Developer instructions contain zero payload bytes. Reviewer output is judgment only and is never passed to the renderer.

---

### `src/skillscout/adapters/skills_ref.py` (official validator adapter)

**Internal analog:** none; this is the only new third-party adapter.

Keep the wrapper narrow and deterministic:

```python
from importlib.metadata import version
from pathlib import Path
from skills_ref import validate

def run_official_validator(admitted_skill_dir: Path) -> tuple[str, tuple[str, ...]]:
    return version("skills-ref"), tuple(validate(admitted_skill_dir))
```

The caller must pre-admit and retain control of the directory. Catch all adapter-boundary exceptions and return/map one bounded `official_validator_runtime_failure` error without raw exception text or absolute paths. Do not shell out, parse CLI prose, or treat this adapter as the full VAL-01/02 policy.

Dependency installation is blocked on human Gate A3 (distribution legitimacy) and Gate B3 (exact registry graph, artifact hashes, and `uv.lock` bytes). No `skills-ref` import or execution is authorized before those gates.

---

### `src/skillscout/application/phase3.py` (PhaseThreeProcessor, event-driven stage handlers)

**Exact analog:** `src/skillscout/application/processors.py`

Compose an exact `PhaseTwoProcessor` instance for Scout through Extractor; do not subclass it. Dispatch Qualifier/Generator/Validators/Reviewer in the Phase 3 processor and use `StageContext.prior_payloads` as the only persisted cross-stage source.

**Dispatch and skip shape** (`processors.py` lines 92-109):

```python
def process(self, stage_input: StageInput, context: StageContext) -> StageOutcome:
    if stage_input.stage is PipelineStage.SCOUT:
        return self._scout(stage_input, context)
    if stage_input.stage in (...):
        skipped = _upstream_skip(context)
        if skipped is not None:
            return StageOutcome(payload=skipped, telemetry=None)
        ...
    raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
```

Extend the skip cascade with closed business outcomes:

- no extracted selected workflow -> qualifier/generator/validators/reviewer skipped;
- qualification reject -> zero Generator and Reviewer calls;
- generation refusal/incomplete/schema failure -> validators/reviewer skipped;
- validation errors -> zero Reviewer calls;
- review NO/low confidence/refusal/incomplete/schema invalid -> terminal audited rejection.

**Business result pattern** (`processors.py` lines 469-572): refusal, incomplete, schema failure, no workflow, all-dropped, and success all return `StageOutcome` and telemetry. Only sanitized infrastructure failures raise `SafeFailure`.

**Telemetry pattern** (`processors.py` lines 450-467): copy prompt/policy/model/request/latency/token data to `StageTelemetry`; the runner persists it. Qualification and validation should set `policy_version`; generation/review should set `prompt_version`, actual model, request ID, latency, and usage.

**Semantic boundary:** Phase 3 may parse only the persisted `WorkflowSpec` and its bounded evidence. Never call `hydrate_read_bundle()` and never re-fetch or reintroduce complete repository text.

---

### `src/skillscout/application/pipeline.py` (additive `phase3-v1` profile/root)

**Exact analog:** current `phase2-v1` profile, completed-run reuse, and composition root in this file.

Add `PHASE_THREE_STAGE_SEQUENCE` through `REVIEWER` and a `phase3-v1` `PipelineProfile`. Preserve the prefix invariant (`pipeline.py` lines 168-188):

```python
"phase2-v1": PipelineProfile(
    (SCOUT, FILTER, READER, EXTRACTOR),
    True,
    RunStatus.COMPLETED,
),

if any(
    profile.stages != tuple(PipelineStage)[: len(profile.stages)]
    for profile in PIPELINE_PROFILES.values()
):
    raise RuntimeError("pipeline profile stages must be a spine prefix")
```

Do not change the `phase2-v1` tuple, terminal, seven registrations, or builder. Add a separate `PhaseThreeRuntime`, local candidate summary/package writer, and `build_phase_three_runtime()`.

**Authority ceiling:** reuse exactly `PHASE_TWO_MAX_SCOPES` (`pipeline.py` lines 68-70) and the same `SideEffectPolicy` validation (`150-156`). The Phase 3 closed root should register exact concrete instances for processor, state, GitHub read, OpenAI extraction, OpenAI generation, official validator, OpenAI review, clock, IDs, and the local candidate writer; reject subclasses/wrong types before invocation, following `build_phase_two_runtime()` lines 832-883. No `REMOTE_WRITE` registration is permitted.

**Ledger/retry seam:** the runner already starts a persisted attempt, invokes the context processor, validates bounded JSON, derives output/result/manifest hashes, records telemetry, and commits the stage (`pipeline.py` lines 365-552). Extend producer/schema/profile support; do not add per-stage retry loops in handlers or adapters.

**Completed reuse seam** (`pipeline.py` lines 313-339): exact same identity must call `find_completed_run()`, verify the full chain, rewrite the local terminal summary/package projection, and return without processor/GitHub/OpenAI calls. Generalize the completed artifact writer selection for Phase 2 and Phase 3 without altering the fixture terminal behavior.

**Durable writer seam** (`pipeline.py` lines 635-695): preserve retained flock, stale-temp recovery, bounded previous read, atomic replacement/restore, fsync, closed errors, and no operator absolute paths in output.

---

### `src/skillscout/domain/models.py` (producer registry and terminal artifact contracts)

**Exact analog:** producer registry and `ExtractionSummary`.

Add `("2", "phase3-v1")` to `SUPPORTED_PRODUCER_SCHEMAS` without changing existing members (`models.py` lines 35-37). Define a strict bounded Phase 3 terminal summary analogous to `ExtractionSummary` (`487-507`) but containing only identifiers, stage outcomes, qualification/validation/review decisions, lineage/artifact/package digests, relative artifact locator, and `remote_writes_attempted=0`. Do not persist generated file bodies twice, raw source, secrets, absolute output paths, or reviewer replacement text.

All new persisted contracts inherit:

```python
class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
```

(`models.py` lines 123-126). Stage payloads continue through the JSON type/depth/node/string/collection bounds in `StagePayload` (`lines 27-120`).

---

### `src/skillscout/cli.py` (additive local candidate command)

**Exact analog:** `extract-repo` (`cli.py` lines 45-64, 67-112).

Add a sibling command such as `validate-skill`/`build-candidate` with `--subject`, `--state`, `--output`, a deterministic workflow selector if required, and `--fail-after` choices restricted to `PHASE_THREE_STAGE_SEQUENCE`. Construct only through `build_phase_three_runtime()` with environment-injected clients.

Preserve `SafeArgumentParser.error()/exit()` byte-exact non-echo behavior (`cli.py` lines 28-42). Load and validate the subject before opening SQLite, emit canonical compact JSON, catch only `SafeFailure` publicly, collapse unexpected exceptions to a closed code, and always close state (`lines 67-112`). Never print operator paths, payload excerpts, credentials, raw validator prose, or exception representations.

Update `tests/test_cli_security.py` subparser assertion in the same additive style as lines 123-133; do not weaken any existing non-echo or no-durable-state assertion.

---

### `pyproject.toml` and `uv.lock` (human-gated configuration)

**Analog:** the Phase 2 two-gate exact-lock ceremony recorded in `STATE.md` and `02-04-SUMMARY.md`.

The plan must put dependency work behind two explicit blocking checkpoints:

1. Gate A3 reviews `skills-ref==0.1.1`, source/publisher/version mismatch, wheel hash, and the intended direct/transitive nodes.
2. Registry-only, non-building lock discovery produces candidate bytes; Gate B3 approves every new node/artifact/hash and the exact new `uv.lock` SHA-256 before sync, import, tests, or validator execution.

Do not add/import transitive `click` or `strictyaml` directly. Do not silently change the Gate-B2 lock before the new authority is approved.

---

### Test and fixture files

#### `tests/test_openai_generate.py`, `tests/test_openai_review.py`, and OpenAI fixtures

**Exact analog:** `tests/test_openai_extract.py`.

Copy the request-shape proof (`lines 62-85`): exactly one POST, `store=false`, no `tools`, bounded tokens, exact strict Pydantic schema, developer-only versioned instructions, and user-only payload. Copy key confinement (`102-109`), result/telemetry mapping (`142-210`), and transient/permanent one-request matrices (`213-262`). Reviewer tests must assert exactly four input sections and prove its schema has no file/replacement fields. Pin 0.799 reject and 0.800 pass in the pure gate tests.

Extend `tests/recorded_transport.py` through its existing loader seam (`lines 26-46`) or add bounded generator/reviewer directory loaders. Retain `RecordedTransport`'s reject-unrecorded behavior (`132-159`).

#### `tests/test_qualification.py`, `test_skill_generation.py`, `test_skill_validation.py`, and `tests/fixtures/skills/**`

Use strict fixture matrices rather than broad snapshots:

- Qualification: stable version/order/reasons, exact score/confidence boundaries, every hard fail, binding mismatch.
- Generation: deterministic bytes, stable slug/lineage, ambiguous collision fail-closed, exact provenance, package digest outside provenance, quote caps, file tree/modes, no scripts/binaries.
- Validation: official-valid package, frontmatter/name mismatch, broken/deep/orphan refs, symlink/hard-link/identity swap, mode `0755`, binary, secret, injection, URL, download-execute, provenance omission/hash mismatch, and over-copy.

Reuse the seven `tests/fixtures/injection/*.md` cases, but ensure Phase 3 receives only their bounded WorkflowSpec residue/canaries, never the raw full files. Add generator/reviewer delimiter variants.

#### `tests/test_phase3_pipeline.py`

**Exact analog:** `tests/test_phase2_pipeline.py`.

Copy these proof groups:

- closed prefix/profile/terminal and REMOTE_READ ceiling (`lines 99-120`);
- full context chain, telemetry, terminal artifact, zero remote writes (`128-195`);
- completed exact-identity reuse with zero processor calls (`198-225`);
- interrupted resume hydrating verified prior payloads without prefix replay (`246-279`);
- exact closed root registrations and adapter identity (`366-404`);
- remote-write canary rejected before invocation (`407-424`);
- no caller-supplied policy/registration widening and wrong concrete/subclass rejection (`427-504`).

Also pin business rejection call counts: qualification reject = zero generator/reviewer; generation reject = one generator/zero reviewer; validation error = one generator/zero reviewer; review outcomes = one generator/one reviewer; same completed identity = zero GitHub/generator/reviewer calls.

#### `tests/test_cli_validate_skill.py` and `tests/test_cli_security.py`

**Exact analog:** `tests/test_cli_extract_repo.py`.

Copy the happy-path evidence sweep (`lines 139-200`): parse terminal JSON, validate all stage outcomes/telemetry, assert `remote_writes_attempted == 0`, scan every durable/stdout/stderr byte for credentials and raw-text canaries, and keep the outbound socket sentinel empty except recorded HTTP transports.

Copy rejection/no-call assertions (`202-229`), resume and third-run idempotency call counts (`232-289`), hostile subject non-echo/no-state behavior (`292-327`), and the byte-exact parser rejection proof from `tests/test_cli_security.py` lines 100-133.

## Shared Patterns

### Phase 1/2 Authority Is the Ceiling

**Source:** `application/pipeline.py` lines 68-70, 150-156, 832-883

Apply to the Phase 3 root and every adapter. Allowed scopes remain `{NONE, LOCAL_STATE, REMOTE_READ}`. Exact concrete adapter admission happens before any invocation. Phase 3 has no Publisher, branch, PR, merge, approval, install-at-runtime, subprocess, or remote-write capability.

### WorkflowSpec Is the Sole Semantic Boundary

**Source:** `domain/extraction.py` lines 74-111; `application/processors.py` lines 692-745

Qualification, generation, validation, and review consume a revalidated `WorkflowSpec` plus trusted upstream facts. They do not hydrate Reader bundles, fetch source text, or persist full repository bytes. Evidence excerpts remain bounded and hash-bound.

### Closed Business Outcomes, Exceptions Only for Infrastructure

**Source:** `application/processors.py` lines 469-572; `adapters/openai_extract.py` lines 112-176

Qualification fail, generator refusal/incomplete/schema invalid, validator findings, Reviewer NO/low confidence/refusal/incomplete/schema invalid are succeeded stage attempts with closed outcome payloads. Only mapped transient/permanent infrastructure failures raise; only transient failures consume the runner retry budget.

### One Request per LLM Attempt

**Source:** `adapters/openai_extract.py` lines 58-122

Generator and Reviewer each have one `responses.parse` call, `max_retries=0`, `store=False`, no tools, strict response schema, bounded tokens, and fresh context. The pipeline, not SDK or handler, owns retry.

### Content-Addressed Durable Identity

**Source:** `domain/canonical.py` lines 24-40, 49-90, 93-140

Use canonical JSON and full SHA-256 identities; keep semantic IDs separate from run-row ownership and package manifests. Short slug suffixes are presentation only. Exclude self-hash fields from their own preimages.

### Verified Resume and Exact Completed Reuse

**Source:** `application/pipeline.py` lines 313-363, 365-552

Resume only from `verify_run_chain()`-authorized prior payloads. Exact completed identity verifies the full chain and performs zero processor/remote calls. Changed workflow/version/prompt/policy/model identity starts fresh work and retains prior audit evidence.

### Descriptor-Anchored File Admission and Durability

**Source:** `adapters/localfs.py` lines 75-143, 154-185, 197-286, 288-329, 360-418; `application/pipeline.py` lines 607-695

All package reads/writes are no-follow, descriptor-relative, identity-checked, bounded, lock-serialized, atomic, and fsynced. Validation runs only after package admission and while ownership is retained. Failures expose closed codes only.

### Sanitized CLI and Diagnostics

**Source:** `application/ports.py` lines 23-73; `cli.py` lines 28-42, 67-112

Public errors come only from the closed ASCII bounded vocabulary. Discard argparse details, provider exceptions, absolute paths, secret matches, and candidate bytes. Reports identify pattern codes and relative package paths, never matched secret content.

## Extension Seams and Non-Negotiable Pins

| Seam | Extend Here | Preserve Exactly |
|---|---|---|
| Producer/profile | `SUPPORTED_PRODUCER_SCHEMAS`, `PIPELINE_PROFILES` | Existing fixture/Phase 2 members, prefix-indexed stages, terminals |
| Processor | new composition-based `PhaseThreeProcessor` | Exact `PhaseTwoProcessor` behavior; no subclass override |
| Authority root | additive `build_phase_three_runtime()` | `PHASE_TWO_MAX_SCOPES`; exact concrete types; no caller widening |
| Stage persistence | existing `PipelineRunner` ledger | attempt lifecycle, bounded `StagePayload`, hashes, telemetry, retry ownership |
| Completed reuse | existing `find_completed_run` + `verify_run_chain` | zero remote/model calls; same run identity; no new status transition |
| Artifact writing | `AnchoredDirectory` / durable writer | no-follow, link/owner/mode checks, lock, atomic replace, fsync |
| Generator/Reviewer | separate clients modeled on Extractor | one call/attempt, `store=false`, no tools, no credentials, fresh contexts |
| CLI | sibling safe subcommand | parser non-echo, subject-before-state, compact JSON, closed errors |
| Dependency graph | Gate A3/B3 only | no lock/import/test before human approvals |

## No Analog Found

| File | Role | Data Flow | Reason / Planner Direction |
|---|---|---|---|
| `src/skillscout/adapters/skills_ref.py` | service adapter | file-I/O request-response | First third-party validator adapter. Use the research's tiny in-process API wrapper, but put dependency and lock changes behind human Gate A3/B3. |
| `tests/fixtures/skills/**` | test fixture | file-I/O | No existing Agent Skill package fixture tree. Build minimal explicit valid/invalid trees; never execute or import their contents. |

## Metadata

**Analog search scope:** `src/skillscout/domain`, `src/skillscout/adapters`, `src/skillscout/application`, `src/skillscout/cli.py`, and Phase 2 tests/recorded fixtures
**Primary analog files read:** 10 source/support files and 5 focused test files
**Pattern extraction date:** 2026-07-22
**Source edits:** none; this pattern map is the only file written
