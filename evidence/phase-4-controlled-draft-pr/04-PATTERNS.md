# Phase 4: Controlled Draft PR - Pattern Map

**Mapped:** 2026-07-24
**Files analyzed:** 13 new/modified files or file groups
**Analogs found:** 12 / 13

No `CONTEXT.md` exists. Scope comes from `04-RESEARCH.md`, `ROADMAP.md`, and requirements `PUB-01`–`PUB-05` plus `SEC-02`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/skillscout/domain/publication.py` | model + policy utility | transform / event-driven state machine | `src/skillscout/domain/skill_artifacts.py` | exact role and trust-boundary match |
| `src/skillscout/application/publication.py` | service/orchestrator | request-response + event-driven recovery | `src/skillscout/application/phase3.py` | exact orchestration/recovery match |
| `src/skillscout/adapters/github_publish.py` | service adapter | request-response | `src/skillscout/adapters/github.py` | exact transport match; different effect scope |
| `src/skillscout/adapters/publication_state.py` | state adapter | CRUD + event-driven checkpointing + file-I/O | `src/skillscout/adapters/state.py` | exact durability/recovery match |
| `src/skillscout/bootstrap.py` | composition/config | request-response | `src/skillscout/application/phase3.py` dependency factories | role match |
| `src/skillscout/cli.py` | controller | request-response | `src/skillscout/cli.py` `build-candidate` boundary | exact in-file match |
| `tests/fixtures/github_publish/` | test fixtures | request-response | `tests/recorded_transport.py` + `tests/fixtures/github/` | exact fixture pattern |
| `tests/test_publication_domain.py` | unit/contract test | transform | `tests/test_phase3_pipeline.py` terminal artifact tests | role/data-flow match |
| `tests/test_github_publish_adapter.py` | transport integration test | request-response | `tests/test_github_adapter.py` | exact role/data-flow match |
| `tests/test_publication_recovery.py` | state/crash test | event-driven recovery | `tests/test_phase3_pipeline.py` reuse/resume tests | exact behavior match |
| `tests/test_publication_security.py` | security/static test | transform + negative capability | `tests/test_cli_security.py`, `tests/test_side_effect_policy.py` | role match |
| `tests/test_publication_live_canary.py` | opt-in integration test | request-response | `tests/test_github_adapter.py` recorded boundary tests | partial; no existing live-write test |
| `.github/workflows/publish-candidate.yml` | workflow/config | event-driven request-response | none | no workflow exists |

## Pattern Assignments

### `src/skillscout/domain/publication.py` (model/policy, transform + state machine)

**Analog:** `src/skillscout/domain/skill_artifacts.py`

Copy the strict frozen-contract style, closed field grammars, canonical ordering, cross-object validators, and digest derivation. Publication domain models should include `PublicationIntentV1`, a versioned PR marker, remote observations/transitions, `PublicationRecordV1`, and a bounded public/manual-intervention result.

**Closed grammar pattern** (`skill_artifacts.py:39-57, 60-105`):

```python
_StableSlug = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]

def _rendered_path(value: str) -> str:
    ...
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix() or ...:
        raise ValueError("rendered path is outside the closed grammar")
```

Derive `skills/{stable_slug}/`, `skillscout/{stable_slug}`, reviewer logins/team slugs, repository full name, ref names, and marker fields inside the domain. Do not accept arbitrary REST paths, catalog paths, refs, titles, or PR bodies from CLI input.

**Canonical manifest and cross-binding pattern** (`skill_artifacts.py:404-425, 489-511`):

```python
class RenderedPackageManifestV1(StrictFrozenModel):
    ...
    @model_validator(mode="after")
    def validate_manifest(self) -> RenderedPackageManifestV1:
        paths = tuple(entry.path for entry in self.entries)
        if paths != tuple(sorted(paths)):
            raise ValueError("rendered manifest is not canonically ordered")
        ...
        return self

class FrozenSkillPackageV1(StrictFrozenModel):
    ...
    @model_validator(mode="after")
    def validate_frozen_package(self) -> FrozenSkillPackageV1:
        ...
        manifest = RenderedPackageManifestV1.from_files(self.files)
        if manifest != self.rendered_manifest:
            raise ValueError("frozen package manifest mismatch")
        if package_digest(manifest) != self.package_identity:
            raise ValueError("frozen package identity mismatch")
        return self
```

Publication admission should reconstruct and compare the manifest rather than walk an output directory. Require mode `0o644`, exact byte size/hash, zero unlisted files, `eligible_local_candidate`, validation error count zero, reviewer `YES`/confidence threshold, and all terminal/package/validation/review digests.

**Digest pattern** (`skill_artifacts.py:453-486`):

```python
manifest_digest = sha256_digest(canonical_json_bytes(manifest))
preimage = {
    "schema_version": PACKAGE_IDENTITY_SCHEMA_VERSION,
    "rendered_manifest_digest": manifest_digest,
}
return PackageIdentityV1(
    **preimage,
    package_digest=sha256_digest(preimage),
)
```

Use the same canonical preimage approach for `publication_key`, `desired_revision`, marker digest, intent digest, and record digest. Domain validation errors should be deterministic `ValueError`/strict validation failures; application boundaries collapse them into `SafeFailure`.

**Deterministic rendering pattern** (`skill_artifacts.py:619-679`): render the PR title/body from strict Phase 3 facts in a fixed section order. The body must contain the PUB-02 facts plus an explicit human-review warning and one bounded canonical marker. Never include raw candidate prose or provider error bodies.

---

### `src/skillscout/application/publication.py` (orchestrator, reconcile-first recovery)

**Analog:** `src/skillscout/application/phase3.py`

Copy the lazy dependency factories and completed-first ordering. The Phase 4 equivalent must validate/recover the durable Phase 3 projection and reconcile GitHub before constructing the token-backed mutable client.

**Lazy capability pattern** (`phase3.py:150-160`):

```python
@dataclass(frozen=True)
class PhaseThreeDependencies:
    completed_projector_factory: Callable[[], object]
    mutable_state_factory: Callable[[], object]
    generator_factory: Callable[[], object]
    validator_factory: Callable[[], object]
    reviewer_factory: Callable[[], object]
    artifact_projector_factory: Callable[[], object]
```

Define separate factories for Phase 3 projection/admission, publication state, read-only reconciliation, and live publisher/token access. A completed or rejected admission path must not invoke the live client factory.

**Completed-first composition pattern** (`phase3.py:1350-1375`):

```python
authority = _execution_authority(source=resolved, profile=self._profile)
projector = self._dependencies.completed_projector_factory()
try:
    completed = projector.find_completed_candidate(authority)
finally:
    close = getattr(projector, "close", None)
    if callable(close):
        close()
if completed is not None:
    return PhaseThreeApplicationResult(..., completed_projection=completed)
mutable = self._dependencies.mutable_state_factory()
```

For Phase 4, the analogous order is:

1. recover and canonically revalidate the eligible Phase 3 projection;
2. derive a closed `PublicationIntentV1`;
3. check completed local publication record;
4. reconcile repository/default ref/machine ref/open PR/reviewers remotely;
5. return no-write recovered completion when the remote desired revision already exists;
6. only then create blobs → tree → commit → ref (`force=False`) → Draft PR/update body → missing reviewer requests;
7. verify remote state and persist terminal record.

**Checkpoint-before/after side effect pattern** (`phase3.py:1053-1064, 1120-1135`):

```python
chain = _record_semantic_attempt(..., status="running", ...)
self.state.persist_semantic_attempt(chain)
result = generator.generate(request=request)
...
self.state.persist_candidate_stage(
    chain,
    stage_payload=canonical_json_bytes(evidence),
    recovery_artifacts=recovery_artifacts,
    status="running",
)
```

Apply this around every externally observable publication step: reconciliation, Git commit/ref visible, Draft PR visible, reviewer set verified, final verification. Persist intent/observed IDs before proceeding; after a crash, re-read remote state instead of blindly replaying.

**Fail-closed exception pattern** (`phase3.py:1407-1418`):

```python
try:
    terminal, artifacts = PhaseThreeRunner(...).run()
except SafeFailure:
    raise
except (AttributeError, TypeError, ValueError):
    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR) from None
```

Ambiguous PRs, non-Draft PRs, marker mismatch, unexpected parents/trees, human commits, changed base, or ref conflicts must return a bounded `manual_intervention_required`; they must not choose a PR, force-push, retarget, or merge.

---

### `src/skillscout/adapters/github_publish.py` (closed REST adapter)

**Analog:** `src/skillscout/adapters/github.py`

Create a separate class; do not add writes or a generic request method to `GitHubReadClient`.

**Imports/provider model pattern** (`github.py:12-17, 35-38`):

```python
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

class _LenientFrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
```

Provider models may ignore unknown GitHub fields, but all fields consumed by domain logic must be bounded and strictly parsed. Return project-owned frozen observations, not raw dictionaries or `httpx.Response`.

**Client/header/effect pattern** (`github.py:162-195`):

```python
class GitHubReadClient:
    def __init__(..., transport: httpx.BaseTransport | None = None, ...):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "skillscout/0.1.0",
        }
        ...
        self._client = httpx.Client(..., follow_redirects=False, transport=transport)

    @property
    def effect_scope(self) -> EffectScope:
        return EffectScope.REMOTE_READ
```

The new class declares `EffectScope.REMOTE_WRITE`, binds one numeric catalog repository ID/full name at construction, and exposes only named operations. Internally derive exact routes for repository/ref/commit/tree/blob/pulls/requested-reviewers. There must be no public `request(method, path)` and no GraphQL, merge, reviews/approval, update-branch, ready, auto-merge, ruleset, administration, arbitrary repository, arbitrary ref, `PUT`, or `DELETE` capability.

**Derived endpoint pattern** (`github.py:213-244`):

```python
path = (
    f"/repos/{_require_segment(_OWNER_REPO_PATTERN, owner)}"
    f"/{_require_segment(_OWNER_REPO_PATTERN, repo)}"
)
_status, response_headers, body = self._get(path, cap=MAX_METADATA_BYTES)
raw = _validate_json(_RawRepo, body)
```

Every publish method should derive the path internally from bound catalog identity and validated identifiers. `update_machine_ref` must always send `force: false` and reject the observed default ref.

**Transport/error/cap pattern** (`github.py:311-385`):

```python
if 200 <= status < 300:
    return status, response.headers, self._read_capped(response, cap)
if status == 429 or (...) or 500 <= status < 600:
    ...
    raise SafeFailure(ErrorCode.STAGE_TRANSIENT_FAILURE)
raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
```

Preserve bounded streaming reads, same-host/no-redirect policy as appropriate, request-ID capture, finite retry classification, and closed safe failures. Add publication-specific conflict/manual classifications for 409/422 only after verifying remote state; never log or persist headers/body/token.

---

### `src/skillscout/adapters/publication_state.py` (durable state)

**Analog:** `src/skillscout/adapters/state.py`

Prefer a focused Phase 4 store rather than expanding the 4,369-line general store. Reuse its strict canonical artifact recovery and snapshot transaction semantics.

**Canonical durable projection pattern** (`state.py:771-817`):

```python
report = ValidationReportV1.model_validate_json(payload, strict=True)
if canonical_json_bytes(report) != payload:
    raise ValueError("noncanonical validation report")
return report.report_digest
```

Admission/recovery must parse canonical bytes for the terminal, frozen package, manifest, qualification, validation, and review attestation, then cross-check the exact terminal artifact matrix. The existing matrix implementation at `state.py:832-897` is the direct source for Phase 4 admission.

**Atomic checkpoint pattern** (`state.py:3445-3503`):

```python
if sha256_digest(stage_payload) != chain.results[-1].payload_digest:
    raise SafeFailure(ErrorCode.STATE_INTEGRITY_ERROR)
...
anchor.atomic_write(locator, payload, max_bytes=..., seam_prefix=...)
...
def mutate(database: sqlite3.Connection) -> None:
    chain_mutation(database)
    database.execute("INSERT INTO ...", ...)
```

Store bounded canonical checkpoint payloads by digest, then atomically index them. Publication state should contain only stable repository/ref/commit/PR IDs, marker/package/manifest/terminal/validation/review digests, reviewer identities, safe route/request IDs, policy/API versions, and timestamps—never tokens, headers, private keys, raw provider bodies, or candidate text.

**Crash-safe transaction pattern** (`state.py:4231-4285`):

```python
candidate.execute("BEGIN IMMEDIATE")
result = mutation(candidate)
candidate.commit()
payload = self._serialize(candidate)
...
self._state_parent.atomic_write(
    self._state_name,
    payload,
    restore_bytes=previous,
    seam_prefix="state_",
)
```

Use one transaction per verified state transition. A filesystem persistence failure poisons the store; it must never continue with memory state that is newer than durable bytes.

**Projection visibility pattern** (`state.py:3715-3815, 3829-3931`): persist the remote terminal as a non-reusable/projecting state first, reconstruct and verify exact artifacts, and expose `completed` only after final remote verification. Require exactly one pending record for an intent; ambiguity is integrity failure.

---

### `src/skillscout/bootstrap.py` and `src/skillscout/cli.py` (composition/controller)

**Analogs:** `phase3.py:150-160, 1330-1448`; `cli.py:66-111, 358-431, 434-481`

Bootstrap should explicitly wire the publication admission projector, publication store, closed publish client, and protected configuration. Keep dry-run and Phase 1–3 graphs unchanged. Configuration must fail closed until catalog numeric ID/full name, target root policy, at least one reviewer/team, policy versions, and token source are present.

**Safe CLI parser pattern** (`cli.py:66-80`):

```python
class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> NoReturn:
        self.exit(2)
    ...
    failure = SafeFailure(ErrorCode.INVALID_CLI_ARGUMENTS)
```

Add `publish-candidate` with fixed descriptor/state/intent paths only. Do not accept repository, branch, package directory/glob, PR title/body, REST path, or reviewer values from candidate-controlled CLI strings.

**Late client construction/cleanup pattern** (`cli.py:358-431`):

```python
clients: list[object] = []
...
try:
    result = PhaseThreeApplication(...).run(...)
finally:
    for client in clients:
        close = getattr(client, "close", None)
        if callable(close):
            close()
```

The publish client/token factory must be invoked only after canonical admission. Always close clients/stores. Public output follows `cli.py:464-477`: sorted compact JSON with a bounded success/manual/error schema, no arbitrary exception text.

## Test Pattern Assignments

### `tests/fixtures/github_publish/` and `tests/test_github_publish_adapter.py`

**Analogs:** `tests/recorded_transport.py`, `tests/test_github_adapter.py`

Use frozen JSON responses and a route map keyed by exact `(method, path)`:

```python
class RecordedTransport:
    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            key = (request.method, request.url.path + ...)
            recorded = self._routes.get(key)
            if recorded is None:
                raise AssertionError(f"unrecorded request: {key[0]} {key[1]}")
```

Source: `recorded_transport.py:147-174`. Extend fixture coverage for blobs, trees, commits, refs, pulls, reviewer pagination, 301, 401, 403, 404, 409, 422, 429, 5xx, malformed/oversized bodies, and missing request IDs.

Copy exact request assertions from `test_github_adapter.py:75-101` and closed route assertions from `test_github_adapter.py:146-162`. For every publish operation assert method, path, JSON body, bound catalog, API header, `draft is True`, `maintainer_can_modify is False`, and `force is False`.

### `tests/test_publication_domain.py`

**Analog:** `tests/test_phase3_pipeline.py:1010-1078`

Test successful exact artifact binding plus one-at-a-time mutation of canonical bytes, digests, eligibility, validation errors, review verdict/confidence, paths, modes, sizes, catalog ID, refs, marker fields, and reviewer grammar. Follow the existing “row count unchanged after rejection” assertion so failed admission has zero token/network/state mutation.

### `tests/test_publication_recovery.py`

**Analogs:** `tests/test_phase3_pipeline.py:1154-1232, 1620-1695, 2345-2460`

Copy three proof styles:

- completed reuse forbids every mutation and uses only read-only projection (`1154-1232`);
- completed lookup happens before mutable factories (`1620-1651`);
- interruption consumes/preserves durable attempt history across restart (`2345-2460`).

Build a crash matrix after commit creation, ref visibility, PR creation/update, reviewer request, remote verification, and remote success before local commit. Add local-state-loss reconstruction and every ambiguous/human-modified state from research. Assert no duplicate PR, no repeated reviewer notification, no force update, and `manual_intervention_required` on ambiguity.

### `tests/test_publication_security.py`

**Analogs:** `tests/test_cli_security.py:598-639, 642-765`; `tests/test_side_effect_policy.py:75-139`

Use “snapshot all surfaces before/after” and canary-secret absence assertions. Static/AST tests must prove:

- no generic arbitrary-path request API;
- no GraphQL, merge, reviews/approval, ready, auto-merge, ruleset/admin, update-branch, `PUT`, or `DELETE`;
- default ref cannot be selected;
- only manifest bytes enter blobs/trees;
- structured log keys are allowlisted;
- candidate data never appears in workflow `run:` interpolation;
- all action refs are full 40-hex SHAs;
- workflow permissions and protected environment are exact.

### `tests/test_publication_live_canary.py`

**Partial analog:** `tests/test_github_adapter.py:269-346, 366-421`

Mark opt-in and skip unless the complete explicit canary configuration exists. Record safe classified outcomes and pre/post SHAs only. Positive proof: machine ref, Draft PR, and reviewer request. Negative proof using the same installation identity: default-ref update and merge fail with unchanged base SHA; adapter/static proof covers approve/ready/auto-merge/ruleset absence. Cleanup must be performed by a separately authorized human/admin process.

## Shared Patterns

### Canonical Admission

**Sources:** `skill_artifacts.py:404-511`; `state.py:771-897`

Apply to domain, application, state, CLI, and tests. Parse strict bytes, compare reserialization byte-for-byte, recompute manifests/digests, and cross-bind all Phase 3 authority before token/client construction.

### Capability Separation

**Sources:** `github.py:162-195`; `phase3.py:150-160`

Keep read and publish adapters separate and truthful about `EffectScope`. Dependency factories are the auditable point proving live write capability is unavailable on rejected, recovered, and dry-run paths.

### Safe Error Handling and Logging

**Sources:** `github.py:311-385`; `cli.py:434-481`

Collapse provider/validation failures into closed codes. Public JSON is deterministic. Persist/log only route ID, request ID, status class, bounded rate facts, safe error code, stable IDs, and digests. Never echo exception messages, response bodies, headers, candidate text, or secrets.

### Reconcile-First Idempotency

**Sources:** `phase3.py:1350-1448`; `state.py:3829-3931`

Lookup exact completed state before mutation; if local state is absent, reconstruct from exact remote head/base plus versioned marker. Exactly one match is required. Treat divergence as manual work, not an overwrite opportunity.

### GitHub Actions Security

No local workflow analog exists. Implement directly from the researched contract:

- top-level default-deny/read-only permissions;
- separate unprivileged admission and environment-protected publish jobs;
- mint the installation token only in the protected job;
- catalog repository and permissions narrowed in token creation;
- every `uses:` pinned to an approved full commit SHA;
- fixed Python CLI invocation; no candidate `${{ ... }}` inside shell;
- no third-party action after token minting;
- no durable state in Actions cache/artifact.

Do not commit `FULL_COMMIT_SHA` placeholders: exact action SHAs require the Phase 3-style supply-chain gate.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `.github/workflows/publish-candidate.yml` | workflow/config | event-driven request-response | Repository currently has no GitHub Actions workflow; use `04-RESEARCH.md` and static security tests as the contract. |

## Planning Constraints and Open Gates

- The catalog numeric repository ID/full name, target root, reviewer users/team slugs, ruleset evidence, protected environment, and approved `actions/create-github-app-token` SHA are not configured. Plans must add explicit human/configuration gates and fail closed until supplied.
- Offline unit/transport/recovery/security tests can be implemented now. Live publication and causal ruleset canary evidence remain blocked on the real GitHub App/catalog environment.
- `Contents: write` is also merge-capable. Safety requires all three layers: closed adapter surface, no App ruleset bypass/default-branch restriction, and a causal live canary.
- Publishing uses Git Data blobs/tree/commit plus one fast-forward ref move. Never use one Contents API call per file and never use `force: true`.

## Metadata

**Primary analog search scope:** `src/skillscout/domain`, `src/skillscout/application`, `src/skillscout/adapters`, `src/skillscout/cli.py`, `tests`, `.github`
**Files scanned:** 183 paths enumerated
**Primary implementation analogs:** 5 (`skill_artifacts.py`, `phase3.py`, `github.py`, `state.py`, `cli.py`)
**Companion test analogs:** 4 (`recorded_transport.py`, `test_github_adapter.py`, `test_phase3_pipeline.py`, `test_cli_security.py`/`test_side_effect_policy.py`)
**Pattern extraction date:** 2026-07-24
