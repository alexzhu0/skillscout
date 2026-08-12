# Phase 6: Adversarial MVP Acceptance - Pattern Map

**Mapped:** 2026-07-28
**Files analyzed:** 25 new/modified files or file families
**Primary analogs:** 5
**Supporting references:** 8
**Analog coverage:** 25 / 25

## Scope Notes

- The file names proposed by `06-RESEARCH.md` are used where explicit. The new workflow name and the exact acceptance-fixture file split remain planner discretion.
- Canonical live evidence stays on `skillscout-state`; checked-in Phase 6 artifacts are the human-locked benchmark definition, concise reconstructed report, and exact requirement map.
- Existing injection fixtures are reused in place. Do not rewrite them into trusted instructions or execute any fixture content.
- No implementation file was modified while producing this map.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/skillscout/domain/acceptance.py` | model | transform | `src/skillscout/domain/discovery.py` | exact |
| `src/skillscout/application/acceptance.py` | service/orchestrator | batch + request-response | `src/skillscout/application/discovery.py` | exact |
| `src/skillscout/adapters/semantic_provider.py` | provider/config | request-response | same file | exact modification |
| `src/skillscout/adapters/operations_state.py` | store | CRUD + file-I/O + batch | same file | exact modification |
| `src/skillscout/bootstrap.py` | provider/bootstrap | request-response + file-I/O | `build_discovery_application`, `run_protected_discovery_publication` in same file | exact modification |
| `src/skillscout/cli.py` | controller | request-response | `discover` / `publish-discovered` paths in same file | exact modification |
| `.github/workflows/phase6-acceptance.yml` (name discretionary) | config/workflow | event-driven + batch | `.github/workflows/discover.yml` and `.github/workflows/gate-b4-canary.yml` | role-match |
| `tools/verify_phase6_acceptance.py` | independent verifier | file-I/O + transform | `tools/verify_phase5_acceptance.py` | exact |
| `tools/verify_phase6_validation_map.py` | independent verifier | file-I/O + transform | `tools/verify_phase5_validation_map.py` | exact |
| `tests/test_acceptance_domain.py` | test | transform | `tests/test_discovery_domain.py` | exact |
| `tests/test_acceptance_application.py` | test | batch + request-response | `tests/test_discovery_application.py` | exact |
| `tests/test_phase6_adversarial.py` | test | batch + transform | `tests/test_extractor_boundary.py`, `tests/conftest.py`, `tests/fixtures/injection/` | role-match |
| `tests/test_phase6_acceptance.py` | test | file-I/O + batch | `tests/test_phase5_acceptance.py` | exact |
| `tests/test_phase6_workflow.py` | test | transform | `tests/test_discovery_workflow.py`, `tests/test_gate_b4_canary_workflow.py` | exact |
| `tests/test_semantic_provider.py` | test | request-response | same file | exact modification |
| `tests/test_openai_extract.py` | test | request-response | same file | exact modification |
| `tests/test_openai_generate.py` | test | request-response | same file | exact modification |
| `tests/test_openai_review.py` | test | request-response | same file | exact modification |
| `tests/fixtures/acceptance/*.json` | fixture | batch + transform | `tests/fixtures/openai/generator/cases.json`, `tests/fixtures/openai/reviewer/cases.json` | role-match |
| `.planning/phases/06-adversarial-mvp-acceptance/06-BENCHMARK-MANIFEST.json` | config/evidence | transform | `config/discovery-queries-v1.json` plus `DiscoveryQuerySetV1` | role-match |
| `.planning/phases/06-adversarial-mvp-acceptance/06-ACCEPTANCE-REPORT.md` | report | transform | Phase 5 independent acceptance projection | role-match |
| `.planning/phases/06-adversarial-mvp-acceptance/06-RELEASE-REQUIREMENTS.json` | validation map | transform | Phase 5 validation-map verifier contract | exact role |
| `README.md`, `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md` | docs | transform | existing Phase 5 provider/operations sections in each file | exact modification |
| `docs/DEVELOPMENT.md`, `docs/TESTING.md` | docs | transform | existing provider-change and release-chain sections | exact modification |
| `RELEASE.md` | docs/release report | transform | current Phase 5 preview evidence and limitation sections | exact modification |

## Primary Analog Set

The planner should treat these as the five anchor analogs. Supporting files below refine tests, workflow security, CLI wiring, and documentation without introducing a second architecture.

1. `src/skillscout/domain/discovery.py` — strict versioned contracts, literal policy, self-digests, terminal taxonomy, root validation.
2. `src/skillscout/application/discovery.py` — capability-limited orchestration, business/system outcome separation, sanitized failures.
3. `src/skillscout/adapters/semantic_provider.py` — closed provider profile, pre-I/O admission, zero SDK retries, strict local JSON validation.
4. `src/skillscout/adapters/operations_state.py` — canonical facts, disposable SQLite index, content-addressed three-store projection/rebuild.
5. `tools/verify_phase5_acceptance.py` — read-only stdlib inspector, explicit registry, exact-byte checks, deterministic one-line result.

## Pattern Assignments

### `src/skillscout/domain/acceptance.py` (model, transform)

**Analog:** `src/skillscout/domain/discovery.py`

**Imports and strict base pattern** (`src/skillscout/domain/discovery.py:3`, `src/skillscout/domain/models.py:129`):

```python
from __future__ import annotations

from typing import Annotated, Final, Literal
from pydantic import Field, model_validator

from skillscout.domain.canonical import sha256_digest
from skillscout.domain.models import Digest, StrictFrozenModel

class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
```

Copy this for benchmark entries, nomination sets, locked manifests, scenario terminals, replay/update evidence, Gate B4 bindings, human attestations, hard-gate results, evidence roots, and report facts. Use closed `Literal` values and bounded tuples/strings, not open prose fields or booleans that collapse the terminal taxonomy.

**Self-digest pattern** (`src/skillscout/domain/discovery.py:76`):

```python
def _self_digest(model: StrictFrozenModel, field: str) -> str:
    return sha256_digest(
        model.model_dump(
            mode="json",
            exclude_none=False,
            exclude={field},
        )
    )
```

Use a `before` validator only to normalize JSON lists to tuples or bind an omitted computed digest. Use an `after` validator to recompute and reject stale supplied digests. Do not accept a caller-asserted manifest, attestation, evidence-root, or report digest without recomputation.

**Exact policy and distribution pattern** (`src/skillscout/domain/discovery.py:93`):

```python
class DiscoveryQuerySetV1(StrictFrozenModel):
    schema_version: Literal["discovery-query-set-v1"]
    query_set_version: Literal["github-repository-search-v1"]
    queries: Annotated[tuple[DiscoveryQueryV1, ...], Field(min_length=4, max_length=4)]
    per_page: Literal[25]
    max_pages_per_query: Literal[4]
    query_set_digest: Digest | None = None

    @model_validator(mode="after")
    def validate_exact_policy(self) -> DiscoveryQuerySetV1:
        actual = tuple((item.query_id, item.query_text) for item in self.queries)
        if actual != _APPROVED_QUERIES:
            raise ValueError("discovery query order or text is not the reviewed v1 policy")
        if self.query_set_digest != _self_digest(self, "query_set_digest"):
            raise ValueError("discovery query-set digest mismatch")
        return self
```

Adapt this to enforce at least five locked entries and the exact role distribution: two plausible positives (one multi-workflow), two negatives, one borderline. `selection_source` must be closed (`search_derived`, `user_nominated`), while evaluator hypotheses stay in evaluator-only fields.

**Business terminal versus system-health pattern** (`src/skillscout/domain/discovery.py:383`, `src/skillscout/domain/discovery.py:428`):

```python
class DiscoveryCandidateTerminalV1(StrictFrozenModel):
    outcome: _CandidateOutcome
    workflow_authority_digests: Annotated[tuple[Digest, ...], Field(max_length=3)]
    terminal_digest: Digest

class DiscoveryRunSummaryV1(StrictFrozenModel):
    status: Literal[
        "completed",
        "completed_degraded",
        "confirmed_retryable",
        "integrity_conflict",
        "permanent_failure",
    ]
```

Phase 6 should similarly separate valid fail-closed business outcomes from release-blocking harness/provider/schema/evidence failures. Never let provider exhaustion satisfy a negative scenario.

**Canonical evidence-root pattern** (`src/skillscout/domain/discovery.py:579`):

```python
class DiscoveryStateRootV1(StrictFrozenModel):
    schema_version: Literal["discovery-state-root-v1"]
    prior_root_digest: Digest | None
    objects: Annotated[tuple[DiscoveryStateObjectV1, ...], Field(max_length=4_096)]
    databases: Annotated[
        tuple[DiscoveryStateDatabaseV1, ...], Field(min_length=3, max_length=3)
    ]
    root_digest: Digest
```

Acceptance evidence should bind sorted unique object digests, explicit owners/locators, prior-root reachability, exact workflow/provider/policy identities, and one externally verifiable root. The report digest must not certify itself.

---

### `src/skillscout/application/acceptance.py` (service/orchestrator, batch)

**Analog:** `src/skillscout/application/discovery.py`

**Capability-limited dependency surface** (`src/skillscout/application/discovery.py:85`):

```python
class _SearchPort(Protocol):
    """Reviewed Search client; concrete construction is supplied by bootstrap."""

class _OperationsPort(Protocol):
    """Owner of durable discovery facts and non-refundable reservations."""

@dataclass(frozen=True)
class DiscoveryDependencies:
    search_factory: Callable[[], _SearchPort]
    operations_store_factory: Callable[[], _OperationsPort]
    state_restore: _StateRestorePort
    durability_barrier: _DurabilityPort
    phase2_factory: Callable[..., PipelineRunner]
    phase3_factory: Callable[..., PhaseThreeApplication]
```

Create distinct dependency types for nomination, locked campaign execution, report rebuild, and protected publication/human-attestation reconciliation. Nomination must not represent semantic or publication capability. Offline adversarial execution must not represent any live adapter or credential.

**Thin composition and sanitized error boundary** (`src/skillscout/application/discovery.py:228`):

```python
def run(self, authority: object | None = None) -> DiscoveryApplicationResult:
    operations: object | None = None
    try:
        restored = self._dependencies.state_restore()
        operations = self._dependencies.operations_store_factory()
        result = operations.run_discovery(...)
        if type(result) is not DiscoveryApplicationResult:
            raise TypeError("invalid discovery result")
        return result
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED) from None
    finally:
        close = getattr(operations, "close", None)
        if callable(close):
            close()
```

Compose the existing discovery and publication coordinators; do not duplicate GitHub reads, extraction/generation/review, lineage, or Draft reconciliation. Collapse unexpected exceptions to a closed safe code without retaining raw provider/repository content.

**Deterministic scenario evaluator** (`src/skillscout/application/discovery.py:771`):

```python
def evaluate_discovery_scenario(
    scenario: DiscoveryScenario,
) -> DiscoveryScenarioResult:
    workflow_outcomes = tuple(
        _WORKFLOW_RESULT[workflow.outcome] for workflow in scenario.workflows
    )
    fatal = scenario.terminal in _FATAL_OUTCOMES
    processed = (scenario.repository_id,)
    if scenario.later_repository_id is not None and not fatal:
        processed += (scenario.later_repository_id,)
    return DiscoveryScenarioResult(
        ...,
        automatic_replay_count=0,
        run_status=run_status,
    )
```

Use a closed hard-gate registry and deterministic evaluator. Expected labels are compared only after the production terminal fact exists; they must never be passed wholesale into extraction, generation, or review inputs.

**Late-authority protected transition** (`src/skillscout/bootstrap.py:1198`):

```python
normalized = _normalize_discovery_handoff(handoff)
state = state_reader(normalized.state_commit_sha)
admissions = admission_deriver(state, normalized)
if type(admissions) not in {list, tuple} or any(item is None for item in admissions):
    raise ValueError("protected discovery admission rejected")

token = catalog_token_factory()
for admission in admissions:
    application = publication_factory(admission=admission, token=token)
    results.append(application.run(admission))
```

Apply the same order to Phase 6: validate exact benchmark/evidence/canary/Draft-head authority first; only then obtain the relevant live credential. Human lock, changed-lineage approval, live campaign authorization, Gate B4 authorization, value-Draft publication, and human verdict are separate transitions.

---

### `src/skillscout/adapters/semantic_provider.py` and semantic adapter tests

**Analog:** existing `src/skillscout/adapters/semantic_provider.py`

**Closed, non-secret settings pattern** (`src/skillscout/adapters/semantic_provider.py:136`):

```python
class SemanticProvider(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"

@dataclass(frozen=True, repr=False)
class SemanticProviderSettings:
    provider: SemanticProvider
    api_key_env: str
    extract_model: str
    generator_model: str
    reviewer_model: str
    base_url: str | None = field(default=None, repr=False)
```

Replace the single `DEEPSEEK_MODEL` guard with a typed stage-specific closed map: Flash extraction, Flash generation, Pro review. Preserve OpenAI behavior and historical all-Flash facts. Do not add a general model or endpoint environment variable.

**Endpoint admission and zero-retry client** (`src/skillscout/adapters/semantic_provider.py:175`, `src/skillscout/adapters/semantic_provider.py:207`):

```python
normalized = candidate[:-1] if candidate and candidate.endswith("/") else candidate
if normalized != DEEPSEEK_OFFICIAL_BASE_URL:
    raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)

arguments = {
    "api_key": resolved_key,
    "http_client": http_client,
    "max_retries": 0,
}
```

Model/stage/endpoint admission must happen before credential resolution and before HTTP. Tests should prove arbitrary endpoints and wrong stage/model pairs produce zero transport calls.

**No-tools JSON and strict local validation** (`src/skillscout/adapters/semantic_provider.py:235`):

```python
response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": trusted},
        {"role": "user", "content": user_payload},
    ],
    response_format={"type": "json_object"},
    max_tokens=max_tokens,
    stream=False,
    extra_body={"thinking": {"type": "disabled"}},
)
...
if choice.finish_reason != "stop":
    return _closed_deepseek_result("incomplete", response)
try:
    parsed = response_model.model_validate_json(content, strict=True)
except ValidationError:
    return _closed_deepseek_result("schema_invalid", response)
```

Update `tests/test_semantic_provider.py`, `tests/test_openai_extract.py`, `tests/test_openai_generate.py`, and `tests/test_openai_review.py` to assert exact request bodies, Flash/Flash/Pro identities, absent tools, one request per durable attempt, sanitized telemetry, malformed/empty/extra-field failure, and Reviewer isolation from raw corpus/evaluator fields.

**Sanitized transport failure pattern** (`src/skillscout/adapters/semantic_provider.py:33`, `src/skillscout/adapters/semantic_provider.py:86`):

```python
class SemanticProviderFailure(Exception):
    __slots__ = ("code", "disposition", "request_id")

def classify_semantic_provider_failure(error: BaseException, *, sdk: Any):
    if isinstance(error, sdk.RateLimitError):
        return SemanticProviderFailure(
            disposition=SemanticTransportDisposition.CONFIRMED_RETRYABLE,
            code="semantic_rate_limited",
            request_id=_safe_provider_request_id(error),
        )
```

Never retain the originating exception, response body, credential, or untrusted returned content in acceptance evidence.

---

### `src/skillscout/adapters/operations_state.py` (store, CRUD/file-I-O)

**Analog:** existing `src/skillscout/adapters/operations_state.py`

**Owned fact and disposable-index pattern** (`src/skillscout/adapters/operations_state.py:171`):

```python
class OperationsOwnedFactV1(StrictFrozenModel):
    schema_version: Literal["operations-owned-fact-v1"]
    kind: _FactKind
    sequence: Annotated[int, Field(ge=0, le=8_192)]
    payload_json: Annotated[str, Field(min_length=2, max_length=1_048_576)]
    object_digest: Digest

    @model_validator(mode="after")
    def validate_canonical_payload(self) -> OperationsOwnedFactV1:
        decoded = _decoded_json(self.payload_json)
        if self.object_digest != sha256_digest(self.payload_json.encode("utf-8")):
            raise ValueError("operations fact digest mismatch")
        return self
```

Extend the operations owner with acceptance fact kinds rather than creating a fourth canonical store. Persist nominations, lock attestations, campaign/scenario terminals, replay comparisons, update lineage, canary bindings, human review, gate results, and report roots as bounded canonical JSON facts. SQLite remains a rebuildable index.

**Canonical JSON failure behavior** (`src/skillscout/adapters/operations_state.py:529`):

```python
def _decoded_json(value: object) -> object:
    if type(value) is not str:
        raise OperationsIntegrityError("invalid canonical operations JSON")
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        raise OperationsIntegrityError("invalid canonical operations JSON") from None
    if _json_text(decoded) != value:
        raise OperationsIntegrityError("noncanonical operations JSON")
    return decoded
```

Reject non-canonical, stale, duplicate, swapped, or malformed evidence. Never repair it for report generation.

**Projection-from-facts pattern** (`src/skillscout/adapters/operations_state.py:561`):

```python
for fact in facts:
    target = mapping.get(fact.kind)
    if target is None:
        continue
    payload = _fact_payload(fact)
    fields[target[0]].append(str(payload["value"][target[1]]))
values = {
    "schema_version": "discovery-state-rebuild-projection-v1",
    **{name: tuple(digests) for name, digests in fields.items()},
}
```

The report and 44-requirement map are projections over verified facts, never log scrapes. Preserve canonical order and explicit inverse mappings from every requirement to evidence and every evidence item back to requirements.

**Content-addressed bundle pattern** (`src/skillscout/adapters/operations_state.py:2427`):

```python
for exported in (pipeline, operations, publication):
    for fact in exported.facts:
        payload = fact.payload_json.encode("utf-8")
        if sha256_digest(payload) != fact.object_digest:
            raise OperationsIntegrityError("owned fact digest mismatch")
        object_bytes.setdefault(fact.object_digest, payload)
...
StateOwnedFile(
    "state/root.json",
    canonical_json_bytes(root.model_dump(mode="json", exclude_none=False)),
)
```

Acceptance evidence must remain redacted, bounded, immutable, and content-addressed on the state branch. Do not persist raw repository corpora, provider output, logs, secrets, or Actions diagnostics.

---

### `src/skillscout/bootstrap.py` and `src/skillscout/cli.py`

**Analogs:** `build_discovery_application`, `read_exact_discovery_state`, `discover`, `publish-discovered`

**Lazy credential factories** (`src/skillscout/bootstrap.py:425`):

```python
def search_factory() -> object:
    return GitHubReadClient(
        token=_required_credential(source, "SKILLSCOUT_SOURCE_GITHUB_TOKEN")
    )

def state_restore() -> object:
    client = StateBranchClient(
        token=_required_credential(source, "SKILLSCOUT_STATE_GITHUB_TOKEN"),
        repository_id=config.state_repository_id,
        repository_full_name=config.state_repository_full_name,
    )
```

Acceptance bootstrap should construct nomination, offline verification, live semantic, state, Gate B4, and publication capabilities separately. A command that only locks or rebuilds evidence must not resolve any live credential.

**Provider identity recheck** (`src/skillscout/bootstrap.py:570`):

```python
provider = resolve_semantic_provider(source)
if (
    provider.provider.value != config.semantic_provider
    or provider.extract_model != config.extractor_model_id
    or provider.generator_model != config.generator_model_id
    or provider.reviewer_model != config.reviewer_model_id
):
    raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
```

Bind exact stage/model policy identity into campaign authority and compare again at the late boundary.

**Safe parser and dispatch** (`src/skillscout/cli.py:78`, `src/skillscout/cli.py:744`):

```python
class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> NoReturn:
        self.exit(2)

arguments = build_parser().parse_args(argv)
try:
    if arguments.command == "discover":
        payload = _run_discover(arguments)
    ...
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
except SafeFailure as failure:
    print(json.dumps({"error": failure.as_dict()}, ...), file=sys.stderr)
    return 1
```

Add separate `nominate-benchmark`, `run-acceptance`, and report-rebuild/attestation commands only as needed by the finalized plan. Keep machine output canonical JSON and errors sanitized. Never accept a secret, arbitrary model, arbitrary endpoint, arbitrary catalog, or expected semantic result as a CLI argument.

**Exact state reread** (`src/skillscout/bootstrap.py:1308`):

```python
observation = StateBranchStore(
    _PinnedStateRemote(client, state_commit_sha)
).restore()
if (
    observation.status != "verified"
    or observation.observed_head != state_commit_sha
    or observation.bundle is None
):
    raise ValueError("protected discovery state rejected")
restore_three_store_bundle(...)
```

Use this before granting replay/update, canary, publication, human-attestation, or report credit.

---

### `.github/workflows/phase6-acceptance.yml` (workflow, event-driven/batch)

**Analogs:** `.github/workflows/discover.yml`, `.github/workflows/gate-b4-canary.yml`

**Serialized production and minimum top-level permission** (`.github/workflows/discover.yml:11`):

```yaml
concurrency:
  group: skillscout-production
  cancel-in-progress: false

permissions:
  contents: read
```

Use a Phase 6-specific non-cancelling concurrency group. Manual live checkpoints must not overlap with the production discovery group in a way that permits duplicate effects.

**Separate authority zones** (`.github/workflows/discover.yml:23`, `.github/workflows/discover.yml:115`):

```yaml
jobs:
  discovery:
    permissions:
      contents: write
    env:
      SKILLSCOUT_LLM_PROVIDER: deepseek
      DEEPSEEK_BASE_URL: https://api.deepseek.com

  protected_publication:
    needs: discovery
    environment: skillscout-catalog-publish
    permissions:
      contents: read
```

Phase 6 should have distinct jobs for offline adversarial verification (no credentials/network), nomination/lock evidence, authorized live DeepSeek benchmark, fresh Gate B4, value Draft publication, and report reconstruction. Never expose publication credentials to discovery or offline jobs.

**Validate before token minting** (`.github/workflows/gate-b4-canary.yml:32`, `.github/workflows/gate-b4-canary.yml:49`):

```yaml
- name: Admit fixed identities before catalog credentials exist
  run: |
    set -euo pipefail
    uv run --locked python tools/gate_b4_canary.py preflight

- name: Mint one catalog-repository installation token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1
```

Copy the ordering, protected environment, full-SHA Action pins, `persist-credentials: false`, explicit timeouts, and bounded artifact retention. No candidate-controlled `${{ }}` value may be interpolated directly into shell.

**No direct copy for OS isolation:** there is no existing kernel/network-isolation workflow analog. The planner must place a Wave 0 hosted capability probe and only then select the exact offline runner mechanism. Python socket monkeypatching is supporting fast feedback, not Phase 6 syscall-denial evidence.

---

### `tools/verify_phase6_acceptance.py` and `tools/verify_phase6_validation_map.py`

**Analog:** `tools/verify_phase5_acceptance.py`

**Dependency-free and bounded reads** (`tools/verify_phase5_acceptance.py:1`):

```python
#!/usr/bin/env python3
"""Independent standard-library-only, read-only Phase 5 acceptance inspector."""

import argparse
import ast
import hashlib
import json
import os
import sys

MAX_SOURCE_BYTES = 2_000_000

def _bytes(root: Path, relative: Path) -> bytes:
    payload = (root / relative).read_bytes()
    _require(len(payload) <= MAX_SOURCE_BYTES)
    return payload
```

Keep the Phase 6 verifiers standard-library-only, network-free, project-import-free, and write-free. Read only exact allowlisted evidence/report/source paths; never recursively scan `.env`, key, token, artifact, or runner-home paths.

**Explicit registry and exact coverage** (`tools/verify_phase5_acceptance.py:351`):

```python
CHECK_REGISTRY = (
    CheckSpec("query_and_budgets", inspect_query_and_budgets),
    CheckSpec("discovery_boundary", inspect_discovery_boundary),
    CheckSpec("semantic_barriers", inspect_semantic_barriers),
    CheckSpec("three_store_state", inspect_three_store_state),
    CheckSpec("protected_publication", inspect_protected_publication),
    CheckSpec("workflows", inspect_workflows),
    CheckSpec("hosted_evidence", inspect_hosted_evidence),
)

_require(tuple(spec.identifier for spec in CHECK_REGISTRY) == expected)
results = tuple((spec.identifier, spec.check(root)) for spec in CHECK_REGISTRY)
_require(all(evidence for _, evidence in results))
```

Phase 6’s registry should enumerate every hard gate independently. The validation-map verifier should assert exact TEST-01..TEST-04 and all 44 requirements in both directions, plus the exact offline/live release command.

**Deterministic diagnostics** (`tools/verify_phase5_acceptance.py:386`):

```python
try:
    verify_phase5_acceptance(root)
except (AcceptanceError, OSError, UnicodeError, SyntaxError, ValueError, ...):
    print(FAILURE_DIAGNOSTIC, file=sys.stderr)
    return 1
print(SUCCESS_DIAGNOSTIC)
return 0
```

Do not print evidence values or mutation detail. One stable success line and one stable failure line are sufficient.

---

### Test Modules

#### `tests/test_acceptance_domain.py`

**Analog:** `tests/test_discovery_domain.py:100`

```python
assert query_set.query_set_digest == sha256_digest(EXPECTED_QUERY_POLICY)
assert canonical_json_bytes(query_set) == canonical_json_bytes(
    {**EXPECTED_QUERY_POLICY, "query_set_digest": query_set.query_set_digest}
)

with pytest.raises(ValidationError):
    DiscoveryQuerySetV1.model_validate(invalid, strict=True)
```

Test exact canonical bytes, self-digests, extra-field rejection, evaluator/semantic separation, manifest distribution, immutable repository ID/SHA/license, attestation exact-head identity, gate conjunction, and all invalid field combinations.

#### `tests/test_acceptance_application.py`

**Analog:** `tests/test_discovery_application.py:77`

```python
fields = set(getattr(dependencies, "__annotations__", {}))
forbidden = {
    "publication",
    "publisher",
    "catalog",
    "catalog_token",
    "publication_factory",
}
assert fields.isdisjoint(forbidden)
```

Use AST/signature checks to prove nomination has no semantic/publication authority, offline tests have no live adapter, semantic payloads omit expected labels/human notes, and credential factories remain lazy. Add scenario tests for valid business rejection versus system failure and for zero-call exact replay.

#### `tests/test_phase6_acceptance.py`

**Analog:** `tests/test_phase5_acceptance.py:18`

```python
@pytest.fixture
def acceptance_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    for directory in ("src", "config", ".github"):
        shutil.copytree(PROJECT_ROOT / directory, repository / directory)
    return repository

def test_requirement_and_prohibition_mutations_fail_closed(...):
    _replace(acceptance_repository, relative, old, new)
    completed = _run(acceptance_repository)
    assert completed.returncode == 1
    assert completed.stderr == "phase5 acceptance invalid\n"
```

Copy the isolated-tree mutation style. Mutate or remove every required gate, requirement link, benchmark identity, replay/update fact, canary binding, exact Draft head, human verdict, workflow digest, and report byte. Assert the verifier is read-only by comparing file metadata before/after and by AST-checking forbidden imports/write calls (`tests/test_phase5_acceptance.py:213`).

#### `tests/test_phase6_adversarial.py`

**Analogs:** `tests/fixtures/injection/`, `tests/conftest.py`, `tests/test_extractor_boundary.py`

Run all seven existing fixture files as inert data and add controlled facts for shell, subprocess, dynamic import, source execution, executable/`scripts/`, synthetic-secret propagation, and unapproved outbound network. Use the existing socket sentinel for fast local detection, but require separate hosted kernel-denial evidence. Assert terminal boundary, forbidden effects, and sanitized evidence for every scenario.

#### `tests/test_phase6_workflow.py`

**Analog:** `tests/test_discovery_workflow.py:106`

Use anchored regex/AST-like YAML text checks for exact triggers, non-cancelling concurrency, protected environments, full 40-character Action SHAs, no candidate interpolation, credential-zone separation, explicit timeouts, bounded artifact retention, and offline/live job separation. Mutation-test each guarantee.

#### Provider tests

Use existing request-recording patterns in `tests/test_semantic_provider.py` and the three semantic adapter test modules. Assert the extracted actual model is Flash for extract/generate and Pro for review; arbitrary strings fail before the recorded transport sees a request.

---

### `tests/fixtures/acceptance/*.json` (fixture family)

**Analogs:** `tests/fixtures/openai/generator/cases.json:1`, `tests/fixtures/openai/reviewer/cases.json:1`

The existing fixtures use a named-case object:

```json
{
  "parsed_success": {"status": 200, "headers": {}, "body": {}},
  "refusal": {"status": 200, "headers": {}, "body": {}},
  "incomplete": {"status": 200, "headers": {}, "body": {}},
  "schema_invalid": {"status": 200, "headers": {}, "body": {}},
  "openai_429": {"status": 429, "headers": {}, "body": {}}
}
```

Acceptance fixtures should be deterministic canonical JSON containing only synthetic identities/credentials and sanitized facts. Include complete, missing, swapped, duplicate, stale, self-referential, replay, changed-lineage, stale-canary, stale-head-attestation, and requirement-map mutations. Do not copy real repository bodies, real tokens, `.env` contents, PEM/JWT/private-key material, raw logs, or live provider responses into fixtures.

Reuse `tests/fixtures/injection/*.md` as the seven authoritative injection classes; do not merge expected labels into those files.

---

### Checked-In Phase 6 Artifacts

#### `06-BENCHMARK-MANIFEST.json`

Copy the exact-byte config-plus-domain-validation relationship used by `config/discovery-queries-v1.json` and `DiscoveryQuerySetV1`. The checked-in definition must contain only public fixed identities, immutable SHAs, confirmed license/provenance, selection source, intended evaluator role, and lock/revision identity. Execution revalidates it against canonical nomination facts.

#### `06-ACCEPTANCE-REPORT.md`

Render deterministically from the canonical evidence root. Include manifest version/digest, five fixed repositories, funnel/budget/telemetry outcomes, expected-versus-observed results, replay/update evidence, exact current canary bindings, exact-head human verdict, warnings/limitations, and release recommendation. Do not hand-edit evidence conclusions.

#### `06-RELEASE-REQUIREMENTS.json`

Follow the independent validation-map pattern: exact 44 requirement IDs, each with one or more evidence identifiers and gate consequences, plus an inverse evidence-to-requirement map. Missing or unmapped entries fail closed.

---

### Documentation Updates

Use the existing Phase 5 sections as exact placement analogs:

- `README.md:87` and `docs/CONFIGURATION.md:59` — update provider text from all-Flash DeepSeek to closed Flash extraction / Flash generation / Pro review. Document no arbitrary model/endpoint input.
- `README.md:93` and `docs/CONFIGURATION.md:48` — add only finalized bounded acceptance commands and clearly label protected/manual checkpoints.
- `docs/ARCHITECTURE.md:43`, `docs/ARCHITECTURE.md:84`, `docs/ARCHITECTURE.md:97` — document nomination → human lock → production campaign → fresh Gate B4 → value Draft → exact-head human verdict → deterministic report, while preserving three-store ownership and Reviewer isolation.
- `docs/DEVELOPMENT.md` — document the stage-specific provider-policy change process and evidence invalidation rules.
- `docs/TESTING.md:19`, `docs/TESTING.md:60`, `docs/TESTING.md:75`, `docs/TESTING.md:114`, `docs/TESTING.md:175` — replace/extend the Phase 5 inspector and release-chain sections with Phase 6 offline, protected live, manual, adversarial, and independent-rebuild boundaries.
- `RELEASE.md:28`, `RELEASE.md:42`, `RELEASE.md:78` — record the actual campaign outcome only after evidence exists. Keep a live OpenAI campaign as a disclosed non-blocking limitation; do not claim universal provider validation.

## Shared Patterns

### Authentication and Credential Timing

**Sources:** `src/skillscout/bootstrap.py:439`, `src/skillscout/bootstrap.py:1198`, `.github/workflows/gate-b4-canary.yml:32`

Apply to every live adapter/workflow:

1. Validate non-secret identity and exact evidence first.
2. Re-read immutable state/workflow/Draft authority.
3. Resolve only the credential required for the next bounded action.
4. Never persist or print the value.
5. Keep GitHub read, DeepSeek semantic, state-branch, and catalog publication credentials in separate capability zones.

### Error Handling

**Sources:** `src/skillscout/application/discovery.py:242`, `src/skillscout/adapters/semantic_provider.py:33`, `tools/verify_phase5_acceptance.py:386`

- Domain validation raises closed `ValueError`/Pydantic failures without untrusted payloads.
- Application boundaries preserve `SafeFailure` and collapse unknown exceptions with `raise ... from None`.
- Provider errors retain only closed disposition/code and a regex-admitted request ID.
- Independent verifiers emit one deterministic success or failure diagnostic.

### Validation and Canonical Identity

**Sources:** `src/skillscout/domain/models.py:129`, `src/skillscout/domain/discovery.py:76`, `src/skillscout/adapters/operations_state.py:529`

- `extra="forbid"`, `frozen=True`, `strict=True`.
- Closed literals/enums and explicit field bounds.
- Canonical JSON, sorted unique sequences, SHA-256 self-digests.
- Recompute every supplied identity at ingress and again at protected/rebuild boundaries.

### State and Idempotency

**Sources:** `src/skillscout/adapters/operations_state.py:171`, `src/skillscout/adapters/operations_state.py:2427`, `src/skillscout/bootstrap.py:1308`

- Canonical JSON facts are authority; SQLite is a disposable query/recovery index.
- Exact replay reuses the same decided authority with zero new provider or remote effects.
- Changed source creates new semantic authority but may update the same eligible open Draft only through explicit prior-lineage binding/approval.
- Historical all-Flash facts are immutable.

### Independent Verification

**Sources:** `tools/verify_phase5_acceptance.py:1`, `tests/test_phase5_acceptance.py:77`

- Standard library only.
- Read-only and network-free.
- Explicit fixed registry rather than discovered checks.
- Exact-byte and inverse-map verification.
- Mutation suite proves each hard gate is causally required.

### Workflow Security

**Sources:** `.github/workflows/discover.yml:11`, `.github/workflows/discover.yml:115`, `.github/workflows/gate-b4-canary.yml:22`

- Full-SHA Actions, fixed checkout revision, `persist-credentials: false`.
- Minimum permissions and protected live environments.
- Non-cancelling concurrency.
- No untrusted `${{ }}` interpolation into shell.
- Validate before token minting.
- Raw diagnostics are short-retention artifacts only; canonical evidence is redacted state.

## No Exact Analog Found

These Phase 6 behaviors have strong surrounding patterns but no completed implementation analog:

| File/Behavior | Role | Data Flow | Planner Direction |
|---|---|---|---|
| Hosted OS/syscall network-denial job | workflow/security test | event-driven | Run a Wave 0 hosted capability probe before selecting Docker/network-namespace mechanics. Do not claim the socket sentinel as sufficient. |
| Exact-head human Skill review attestation | model + protected verifier | request-response | Build from strict self-digesting domain models and exact-state reread; reconcile current open Draft/head without granting review/merge authority. |
| Whole-MVP all-hard-gates report renderer | utility/report | batch transform | Build from canonical acceptance facts and verify independently byte-for-byte; do not scrape logs or self-certify. |
| Human-locked five-repository benchmark | config/evidence | transform | Build from `DiscoveryQuerySetV1` exact-policy pattern plus a strict human lock attestation; actual repositories remain a checkpoint, not planner-selected evidence. |

## Planner Guardrails

- Do not create a parallel discovery/publishing implementation for the campaign.
- Do not add a fourth canonical state store.
- Do not add an arbitrary model, endpoint, catalog, or expected-result runtime option.
- Do not pass benchmark roles, expected labels, or human notes into semantic requests.
- Do not count Draft creation or reviewer request as completed human review.
- Do not grant value-Draft credit before a fresh exact-byte Gate B4.
- Do not open or scan real secret-bearing files; use synthetic canaries and allowlisted sanitized surfaces only.
- Do not make the acceptance report or requirement map their own evidence authority.

## Metadata

**Search scope:** `src/skillscout/domain`, `src/skillscout/application`, `src/skillscout/adapters`, `src/skillscout/bootstrap.py`, `src/skillscout/cli.py`, `tools`, `tests`, `tests/fixtures`, `.github/workflows`, `README.md`, `docs`, `RELEASE.md`

**Primary analogs inspected:** 5

**Supporting references inspected:** `src/skillscout/bootstrap.py`, `src/skillscout/cli.py`, `.github/workflows/discover.yml`, `.github/workflows/gate-b4-canary.yml`, `tests/test_discovery_domain.py`, `tests/test_discovery_application.py`, `tests/test_phase5_acceptance.py`, `tests/fixtures/openai/{generator,reviewer}/cases.json`

**Pattern extraction date:** 2026-07-28
