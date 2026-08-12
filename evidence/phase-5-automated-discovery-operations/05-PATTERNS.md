# Phase 5: Automated Discovery Operations - Pattern Map

**Mapped:** 2026-07-27
**Files analyzed:** 22 likely new/modified files or fixture groups
**Analogs found:** 22 / 22
**Scope:** DISC-01, DISC-02, DISC-03, OPS-02, OPS-03

## Scope and Pattern Strategy

Phase 5 should add a durable operational control plane, not a second content-processing pipeline. The new discovery application should select repositories and persist discovery/budget facts, then compose the existing Phase 2 `PipelineRunner`, Phase 3 `PhaseThreeApplication`, and Phase 4 `PublicationApplication`. The strongest codebase analogs are:

1. Phase 1 `SQLiteStateStore` and `PipelineRunner` for exact identity, durable-before-effect checkpoints, snapshot transactions, resumption, chain verification, and sanitized failures.
2. Phase 2 `GitHubReadClient`, `PhaseTwoProcessor`, and `SQLitePhaseTwoCandidateSource` for bounded REST reads, lenient provider parsing followed by strict projection, pinned repository processing, and read-only verified state access.
3. Phase 3 `PhaseThreeRuntimeProfile`, semantic-attempt persistence, and completed-first application lookup for hard budgets, attempt accounting, interruption recovery, and exact-authority reuse.
4. Phase 4 `GitHubPublishClient`, `PublicationStateStore`, `PublicationApplication`, bootstrap, CLI, and workflow for narrow remote capabilities, remote reconciliation, non-force ref updates, late credentials, protected publication, and static workflow security tests.

## File Classification

| New/Modified File or Group | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `config/discovery-queries-v1.json` | config | batch | `PhaseThreeRuntimeProfile` in `application/phase3.py` | role-match |
| `src/skillscout/domain/discovery.py` | model | batch / event-driven | `domain/candidate_authority.py`; `domain/models.py` | exact |
| `src/skillscout/adapters/github.py` | service | request-response | existing `GitHubReadClient` methods; pagination in `github_publish.py` | exact |
| `src/skillscout/adapters/operations_state.py` | store | CRUD / event-driven | `adapters/state.py`; `adapters/publication_state.py` | exact |
| `src/skillscout/adapters/state_branch.py` | service | request-response / file-I/O | `adapters/github_publish.py` | exact |
| `src/skillscout/application/discovery.py` | service | batch / event-driven | `application/pipeline.py`; `application/phase3.py`; `application/publication.py` | exact |
| `src/skillscout/bootstrap.py` | provider / config | request-response | `build_publication_application` | role-match |
| `src/skillscout/cli.py` | controller | request-response | existing subcommand parser/dispatch and bounded public payloads | exact |
| `.github/workflows/discover.yml` | config | event-driven | `.github/workflows/publish-candidate.yml` | exact |
| `tests/fixtures/github_search/*` | test fixture | request-response | `tests/fixtures/github/*`; `tests/recorded_transport.py` | exact |
| `tests/fixtures/state_branch/*` | test fixture | request-response / file-I/O | `tests/fixtures/github_publish/*`; `tests/recorded_transport.py` | exact |
| `tests/test_discovery_domain.py` | test | transform | `tests/test_candidate_authority.py`; Phase 3 domain-chain tests | exact |
| `tests/test_github_search.py` | test | request-response | `tests/test_github_adapter.py` | exact |
| `tests/test_operations_state.py` | test | CRUD / event-driven | `tests/test_state_integrity.py`; Phase 3 ledger tests | exact |
| `tests/test_state_branch.py` | test | request-response / file-I/O | `tests/test_publication_recovery.py`; `tests/test_github_publish_adapter.py` | exact |
| `tests/test_discovery_application.py` | test | batch / event-driven | `tests/test_pipeline_resume.py`; `tests/test_phase3_pipeline.py` | exact |
| `tests/test_discovery_workflow.py` | test | event-driven | `tests/test_publication_security.py` | exact |
| `tests/test_discovery_security.py` | test | batch / request-response | `tests/test_cli_security.py`; `tests/test_publication_security.py` | exact |
| `tests/test_phase5_acceptance.py` | test | batch | `tests/test_phase4_acceptance_tool.py` | exact |
| `tools/verify_phase5_acceptance.py` | utility | batch / file-I/O | `tools/verify_phase4_acceptance.py` | exact |
| `tests/test_phase5_validation_map.py` | test | batch / file-I/O | `tests/test_phase4_validation_map.py` | exact |
| `tools/verify_phase5_validation_map.py` | utility | batch / file-I/O | `tools/verify_phase4_validation_map.py` | exact |

## Pattern Assignments

### `config/discovery-queries-v1.json` (config, batch)

**Analog:** `src/skillscout/application/phase3.py:113-157`

Copy the Phase 3 runtime-profile principle: all cost-sensitive policy is versioned, bounded by validation, and included in a stable digest before any reuse lookup. The JSON file should be static reviewed input, while `domain/discovery.py` strictly validates its exact schema and derives the digest with `canonical_json_bytes` / `sha256_digest`.

```python
class PhaseThreeRuntimeProfile(StrictFrozenModel):
    profile_version: str = PHASE_THREE_PROFILE_VERSION
    budget_policy_version: str = PHASE_THREE_BUDGET_POLICY_VERSION
    max_candidates: Annotated[int, Field(ge=1, le=3)] = 3
    max_generator_attempts: Annotated[int, Field(ge=1, le=3)] = 3

@property
def profile_digest(self) -> str:
    return sha256_digest(
        {"schema_version": "phase3-runtime-profile-v1", "profile": self.model_dump(...)}
    )
```

For Phase 5, validate the fixed query-set version, four ordered query IDs/texts, `per_page=25`, `max_pages_per_query=4`, `sort=updated`, `order=desc`, `max_candidates=100`, and `max_semantic_candidates=20`. Do not accept query text from `workflow_dispatch`.

### `src/skillscout/domain/discovery.py` (model, batch/event-driven)

**Analogs:** `src/skillscout/domain/models.py:13-43,129-183`; `src/skillscout/domain/candidate_authority.py:61-118,121-179`; `src/skillscout/domain/canonical.py:24-40`

Use `StrictFrozenModel` for every durable object, `Literal[...]` schema/status fields, bounded `Annotated` fields, and `@model_validator(mode="after")` for self-hash, sequence, and cross-field invariants.

```python
class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

class CandidateExecutionAuthorityV1(StrictFrozenModel):
    schema_version: Literal["candidate-execution-authority-v1"]
    ...
    authority_digest: Digest

    @model_validator(mode="after")
    def validate_complete_authority(self):
        expected = sha256_digest(
            self.model_dump(mode="json", exclude_none=False, exclude={"authority_digest"})
        )
        if self.authority_digest != expected:
            raise ValueError("candidate execution authority digest mismatch")
        return self
```

Define closed contracts rather than untyped dictionaries:

- `DiscoveryQueryV1`, `DiscoveryQuerySetV1`, and `DiscoveryBudgetPolicyV1`.
- `SearchRateLimitFactsV1` including `limit`, `remaining`, `used`, `reset`, and `resource`.
- `SearchPageObservationV1` binding query-set digest, query ID/text, page/per-page, `total_count`, `incomplete_results`, item count, next-page integer, request ID, and rate-limit facts.
- `SearchRepositoryObservationV1` containing only numeric repository ID, owner/name, public/fork/archive/disabled/default-branch facts.
- `DiscoveredCandidateV1` with first-seen query/page/item provenance and a closed dedup disposition.
- `DiscoveryRunAuthorityV1`, `DiscoveryReservationV1`, `DiscoveryCandidateTerminalV1`, `DiscoveryRunSummaryV1`, state object/root contracts, and a closed outcome taxonomy.

Use the canonical encoding exactly as established:

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

Do not include Search descriptions, topics, text matches, raw `Link`, provider bodies, source text, raw exceptions, headers, or secrets in any domain contract.

### `src/skillscout/adapters/github.py` (service, request-response)

**Analog:** the existing file, especially `github.py:35-59,90-111,162-235,311-385,396-425`; pagination analog `github_publish.py:418-459`

Extend the existing serial `GitHubReadClient`; do not introduce a second general GitHub client. Preserve the provider-to-domain projection boundary:

```python
class _LenientFrozenModel(BaseModel):
    """Provider-response parsing: validate consumed fields, ignore the rest."""
    model_config = ConfigDict(frozen=True, strict=True)

raw = _validate_json(_RawRepo, body)
return _validate(
    RepoMetadata,
    {
        "id": raw.id,
        "owner": raw.owner.login,
        "name": raw.name,
        ...
        "rate_limit": _rate_limit_facts(response_headers),
    },
)
```

Add raw Search envelope/item models that consume only the allowlisted fields. Return a strict Search page observation, never the raw provider item. Reuse the existing caps, exact API base/version, no automatic redirects, `EffectScope.REMOTE_READ`, bounded `Retry-After`, and closed `SafeFailure` classification.

For pagination, adapt Phase 4's validation instead of following an arbitrary URL:

```python
def _next_page(self, link: str | None) -> str | None:
    if link is None:
        return None
    if type(link) is not str or len(link) > 8_192:
        _fail()
    ...
    if not next_url.startswith("https://api.github.com/") or "#" in next_url:
        _fail()
```

Phase 5 should narrow this further: validate the Search endpoint, query-set-owned parameters, and the exact next page number; persist the integer cursor, not raw `Link`.

Keep response reads streaming and capped:

```python
for chunk in response.iter_bytes(65_536):
    consumed += len(chunk)
    if consumed > cap:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
```

Rate-limit telemetry should extend the current `_rate_limit_facts` projection without retaining arbitrary headers. Treat 429 and exhausted 403 as transient/rate-deferred, 5xx/transport failures through the existing closed taxonomy, and malformed/missing required Search facts as permanent.

### `src/skillscout/adapters/operations_state.py` (store, CRUD/event-driven)

**Analogs:** `src/skillscout/adapters/state.py:1169-1364,2254-2342,3405-3684,4231-4285`; `src/skillscout/adapters/publication_state.py:1-8,30-51,59-180`

Use a dedicated operations ledger rather than broadening publication state. Copy the Phase 1 serialized in-memory SQLite pattern: private anchored file, retained flock, exact schema fingerprint, `PRAGMA foreign_keys=ON`, mutation on a candidate connection, canonical serialization, atomic replacement, and poisoning after durability failure.

```python
def _snapshot_transaction(self, mutation):
    candidate = self._new_memory_connection()
    candidate.deserialize(self._durable_bytes)
    candidate.execute("PRAGMA foreign_keys = ON")
    candidate.execute("BEGIN IMMEDIATE")
    result = mutation(candidate)
    candidate.commit()
    payload = self._serialize(candidate)
    self._state_parent.atomic_write(
        self._state_name,
        payload,
        restore_bytes=previous,
        ...
    )
```

Copy completed/resumable exact-authority lookup:

```python
WHERE ... authority_digest = ?
  AND status IN ('running', 'interrupted')
```

Reject ambiguity instead of selecting an arbitrary unfinished run, matching `find_resumable_candidate()` in `state.py:3685-3704`.

Candidate discovery reservation and the count must happen in one `BEGIN IMMEDIATE` mutation. Required invariants:

- unique `(discovery_run_id, repository_id)` first-seen discovery selection;
- discovery ordinal contiguous and bounded at 100;
- unique `(discovery_run_id, repository_id)` semantic reservation;
- semantic ordinal contiguous and bounded at 20;
- reservations never deleted/refunded by rejection, transient failure, interruption, or resume;
- completed exact-authority reuse creates no new semantic reservation;
- candidate status and run health are separate closed fields.

Persist semantic reservation and a state-branch durability barrier before invoking the existing Extractor. Follow Phase 3's pre-call attempt pattern:

```python
chain = _record_semantic_attempt(..., status="running", ...)
self.state.persist_semantic_attempt(chain)
result = generator.generate(request=request)
```

Add exact export/import methods using canonical JSON facts. On restore, validate canonical bytes, object hashes, ordinal continuity, all Phase 1/3 chain verifiers, publication checkpoints, schema fingerprint, foreign keys, and `PRAGMA integrity_check == ("ok",)`. Rebuild through the same validated insertion paths; never trust a physically valid SQLite file that disagrees with the JSON root projection.

### `src/skillscout/adapters/state_branch.py` (service, request-response/file-I/O)

**Analog:** `src/skillscout/adapters/github_publish.py:98-145,172-181,277-328,355-394,493-499`

Create a narrower client fixed to the configured source/state repository and exactly `refs/heads/skillscout-state`. It should expose only read-ref/tree/blob plus create-blob/tree/commit and create-or-fast-forward-ref. Do not reuse catalog-root assumptions or expose PR/reviewer methods.

Copy Phase 4's exact authority binding, request-ID validation, body caps, redirect rejection, and closed failure mapping. Copy the mutation rules:

```python
raw = self._json(
    "PATCH",
    f"/repos/{self._repository}/git/refs/heads/{self._branch}",
    {"sha": expected, "force": False},
)
return self._ref_response(raw, expected_sha=expected)
```

The state commit must have exactly one parent equal to the previously observed state head. Build an exact allowlisted tree:

```text
state/root.json
state/objects/sha256/ab/<64-hex>.json
state/skillscout.sqlite3
state/publication.sqlite3
```

Require regular blob mode `100644`, bounded path/count/byte sizes, no symlinks, no WAL/journal/temp files, no unexpected paths, and no deletion/overwrite outside the allowlist. After ref mutation, re-read the ref and require the expected SHA. Classify 409/422, changed head, response mismatch, or reread mismatch as `state_branch_conflict`; never retry with force and never merge SQLite bytes.

### `src/skillscout/application/discovery.py` (service, batch/event-driven)

**Analogs:** `src/skillscout/application/pipeline.py:282-365,365-583`; `src/skillscout/application/phase3.py:1344-1462`; `src/skillscout/application/publication.py:83-143,498-620`

Model the application as constructor-injected dependencies/factories. Stable authority and completed/resumable lookup must occur before mutation or semantic-client construction.

Copy the completed-first pattern:

```python
completed = lookup(authority)
if completed is not None:
    return PhaseThreeApplicationResult(
        outcome=...,
        authority=authority,
        completed_projection=completed,
    )

mutable = self._dependencies.mutable_state_factory()
```

Discovery sequencing should be:

1. restore and verify the exact state branch;
2. select one matching verified unfinished discovery run, otherwise create one;
3. acquire Search pages in fixed round-robin order;
4. project and durably record every page and first-seen/duplicate observation;
5. stop after 100 durably selected numeric repository IDs;
6. re-run existing Phase 2 Scout → Filter → Reader;
7. if Phase 2 rejects, persist a business terminal and continue;
8. reserve the semantic candidate durably (maximum 20) immediately before the first Extractor request;
9. run the existing Phase 2 extraction and Phase 3 candidate application, preserving their attempt budgets;
10. persist business terminals separately from operational failures;
11. pass only eligible canonical evidence through existing Phase 4 admission/publication;
12. run a durability barrier after each page/dedup transaction, semantic reservation/attempt, candidate terminal, publication checkpoint, and publication terminal.

The loop should continue after business terminals but fail closed on state integrity, schema/config/permission failures, or state-branch conflict. At confirmed rate exhaustion, stop new remote calls until policy permits a bounded retry/resume. An outcome-unknown semantic request must be quarantined and must not be automatically replayed.

Copy Phase 1's exception collapse:

```python
except SafeFailure:
    raise
except Exception:
    raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED) from None
```

Never persist raw exception text. Keep per-candidate outcome and aggregate run health distinct.

### `src/skillscout/bootstrap.py` (provider/config, request-response)

**Analog:** `bootstrap.py:318-368`

Use late-bound factories and keep authority zones separate:

```python
def remote_factory() -> object:
    token = runtime.token_factory()
    if type(token) is not str or not token:
        _publication_config_fail()
    return GitHubPublishClient(...)
```

Add strict discovery/state configuration loaders and a `build_discovery_application` factory. Source/Search/state credentials may be resolved only in the discovery job's remote factories. Catalog App token construction must remain exclusively inside the existing protected publication factory/job and must happen after local re-admission.

Validate state repository ID/full name, fixed state branch, query-set locator/digest, database locators, model/provider identities, and policy versions before accessing state or tokens. Do not pass environment mappings or secrets into domain/application objects.

### `src/skillscout/cli.py` (controller, request-response)

**Analog:** `cli.py:72-127,534-583,586-649`

Add one production `discover` subcommand with path/config locators only. Do not expose free-form query text, budget overrides, state branch overrides, catalog admission digests, tokens, or unsafe retry switches as arguments.

Continue using `SafeArgumentParser`, which emits only the closed `INVALID_CLI_ARGUMENTS` diagnostic. Project one bounded JSON result like `_public_publication_payload`; include stable run/root/state-head IDs and counts/outcome codes, not provider bodies, source text, exceptions, environment, headers, or arbitrary URLs.

Dispatch through a dedicated `_run_discover()` helper and preserve the current top-level behavior:

```python
except SafeFailure as failure:
    print(json.dumps({"error": failure.as_dict()}, ...), file=sys.stderr)
    return 1
except Exception:
    failure = SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
    ...
```

Ensure all state/client handles close in `finally`.

### `.github/workflows/discover.yml` (config, event-driven)

**Analog:** `.github/workflows/publish-candidate.yml:1-31,31-161`

Copy immutable Action pins, `persist-credentials:false`, locked `uv`, explicit shell safety, minimum top-level permissions, and protected late token minting. Add:

```yaml
on:
  schedule:
    - cron: "17 3 * * *"
  workflow_dispatch:

concurrency:
  group: skillscout-production
  cancel-in-progress: false
```

Use one workflow with two authority zones:

- discovery/build job: read reviewed code, restore/verify state, run discovery through Review, fast-forward the state branch, and emit only a bounded run locator, root digest, and exact state-head SHA;
- protected publication job: check out the same code revision and exact state commit, re-derive all candidate admissions locally, then mint the catalog-scoped App token and call the existing publisher sequentially.

The discovery job must not receive catalog variables/secrets. No run block may contain `${{ ... }}` interpolation of candidate-controlled data; bridge values through validated environment fields. Do not use cache or artifacts as canonical recovery state. If `queue: max` is used, add syntax/audit coverage first; otherwise retain the fixed group and non-cancel behavior and document pending-run replacement behavior.

### `tests/fixtures/github_search/*` and `tests/fixtures/state_branch/*` (test fixtures)

**Analogs:** `tests/recorded_transport.py:18-41,64-112,147-174`; existing GitHub and publication fixture directories

Use recorded, deterministic JSON fixtures and `httpx.MockTransport`; every unrecorded request must fail:

```python
recorded = self._routes.get(key)
if recorded is None:
    raise AssertionError(f"unrecorded request: {key[0]} {key[1]}")
```

Search fixtures should cover one/multiple pages, cross-query duplicates, rename with same numeric ID, incomplete results, invalid public/fork facts, hostile discarded prose, hostile `Link`, malformed/oversized responses, 403/429/5xx, and missing/malformed rate headers.

State-branch fixtures should cover absent branch bootstrap, valid tree/root/objects, normal fast-forward, 409/422, changed head, lying mutation response, reread mismatch, unexpected path/mode/symlink, missing/swapped object, rollback root, and corrupt database bytes. Fixtures must never contain live credentials or copied full repository text.

### Test modules (test, mixed flows)

**Primary analogs:** `tests/test_github_adapter.py:75-162,269-474`; `tests/test_pipeline_resume.py:390-423,944-1015`; `tests/test_phase3_pipeline.py:2305-2460`; `tests/test_publication_recovery.py:292-380`; `tests/test_publication_security.py:257-308`

Use real adapters with recorded transports for boundary tests, tiny dependency fakes for orchestration tests, and real SQLite for durability/integrity tests.

`tests/test_discovery_domain.py` should mutation-test strict fields, extra-field rejection, self-hashes, exact query-set digest, closed status vocabulary, cursor/order invariants, and 100/20 ceilings.

`tests/test_github_search.py` should copy the existing adapter assertions: exact method/path/query/headers, one serial request per page, strict projected facts, rate telemetry, bounded sleep, redirect/Link rejection, body caps, error classification, and token confined to the Authorization header.

`tests/test_operations_state.py` should copy state integrity's mutation style and test exact schema fingerprint, transactional reservation, 100th/101st and 20th/21st behavior, non-refund after all terminal/failure classes, contiguous ordinals, duplicate repository IDs, tampered rows/counters, canonical export, SQLite corruption, JSON rebuild, projection equality, and killed-writer recovery.

`tests/test_discovery_application.py` should use interruption wrappers like:

```python
def persist_semantic_attempt(self, chain) -> None:
    self._store.persist_semantic_attempt(chain)
    ...
    raise SafeFailure(ErrorCode.PIPELINE_INTERRUPTED)
```

Verify crashes before/after discovery reservation and semantic reservation, completed reuse, no prefix replay, filter/reader/qualification/validation/reviewer business terminals continuing the run, outcome-unknown quarantine, bounded confirmed retry, and no duplicate Draft.

`tests/test_state_branch.py` should copy publication reconciliation tests: mutate remote state between read/write, require exact parent and final reread, prove no force route, prove conflicts have zero additional writes, and prove a valid remote state can reconstruct missing local state.

`tests/test_discovery_workflow.py` and `tests/test_discovery_security.py` should statically assert exact immutable Action SHAs, schedule plus manual dispatch, one fixed concurrency group, `cancel-in-progress:false`, minimum per-job permissions, no cache/artifact authority, no catalog secret in discovery, local re-admission before token minting, no candidate shell interpolation, and no full source/secret canaries in state/log/job outputs/prospective tree.

### `tools/verify_phase5_acceptance.py` and `tests/test_phase5_acceptance.py` (utility/test, batch/file-I/O)

**Analog:** `tools/verify_phase4_acceptance.py:1-81,96-240`

Make the verifier independent, standard-library-only, read-only, size-bounded, and based on AST/structured source inspection rather than importing project code:

```python
def _read(root: Path, relative: Path) -> str:
    payload = (root / relative).read_bytes()
    _require(len(payload) <= MAX_SOURCE_BYTES)
    return payload.decode("utf-8", errors="strict")

def imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_bytes(), filename=str(path))
    ...
```

The inspector should independently check all five requirements and their prohibitions: query versioning/triggers, 100/20 durable caps, complete page/source/rate/dedup facts, SQLite-plus-JSON rebuild and concurrency, and absence of source/secrets across durable/observable surfaces. Its test must mutation-test each claim, not merely test the success case.

### `tools/verify_phase5_validation_map.py` and `tests/test_phase5_validation_map.py` (utility/test, batch/file-I/O)

**Analog:** `tools/verify_phase4_validation_map.py:1-105,121-220`; `tests/test_phase4_validation_map.py`

Copy the exact plan/task bijection and requirement inverse-map approach. Pin the five Phase 5 requirements, exact task IDs, waves, dependencies, focused commands, local locked `uv` path, Action identities, and full release chain. Reject mutable Action references, missing prohibition evidence, nonlocal tools, plan drift, and requirement rows that are absent or multiply/incorrectly mapped.

## Shared Patterns

### Durable Before External Effect

**Sources:** `application/pipeline.py:397-424`; `application/phase3.py:1062-1078`; `adapters/state.py:4231-4285`

Apply to Search page acquisition bookkeeping, first-seen admission, semantic reservation, semantic attempt start, and publication checkpoints. The state mutation must be durably serialized and, where required, synchronized to the state branch before the external semantic or catalog effect.

### Exact Authority Before Reuse

**Sources:** `application/pipeline.py:305-358`; `application/phase3.py:1370-1387`; `adapters/state.py:3685-3704`

Every reuse lookup must bind the query-set digest, budget policy, pipeline/profile versions, provider/model identities, and initial state root. A changed authority is a clean miss; malformed or ambiguous persisted authority is an integrity failure, never a miss.

### Closed Provider Projection

**Source:** `adapters/github.py:35-59,90-111,213-235,410-425`

Parse only consumed provider fields into lenient raw models, then construct a strict domain object. Collapse provider-shape errors into `SafeFailure`; never serialize raw provider dictionaries.

### Business Outcome vs Operational Health

**Sources:** `application/phase3.py:1289-1341`; `application/publication.py:142-143`

Persist deterministic rejection/qualification/validation/review outcomes as candidate terminals and continue. Keep transient, outcome-unknown, conflict/integrity, and permanent operational states separate. Never express a business rejection by throwing a retryable exception.

### Remote Reconciliation and Compare-and-Swap

**Sources:** `application/publication.py:83-124,498-561`; `adapters/github_publish.py:320-328,493-499`

Observe remote authority, mutate narrowly, then independently re-read and verify the exact ref/tree/commit. A mutation response alone cannot authorize success. State-branch conflicts stop the attempt and require a later fetch/verify/resume.

### Sanitized Diagnostics

**Sources:** `cli.py:72-86,634-646`; `tests/test_pipeline_resume.py:985-1015`

Only closed error code/summary pairs may cross CLI/log/state boundaries. Raw exceptions, credentials, paths, headers, and provider bodies must be discarded.

### Read-Only Verification

**Source:** `adapters/phase2_state.py:53-135,239-341`

Verification readers should use stable private-file reads, shared retained locks, in-memory deserialize, `PRAGMA query_only=ON`, a SQLite authorizer, canonical revalidation, and guaranteed close. Rebuild authority must be verified without gaining an accidental writable capability.

## Planner Notes and Boundaries

- Do not modify the existing semantic provider contracts merely to count candidates. Reserve once per repository immediately before the first Extractor request in the discovery operations ledger.
- Do not count Generator/Reviewer retry attempts as new semantic candidates; retain Phase 3's separate attempt accounting.
- Do not refund discovery or semantic reservations.
- Do not deduplicate by mutable `owner/name`; use numeric repository ID and retain name only as provenance.
- Do not trust Search qualifiers as filter authority; re-run Phase 2 Scout/Filter and pin the commit.
- Do not copy an active SQLite file. Export via serialized/backup snapshot under the store's retained lock.
- Do not force-update or merge the state branch.
- Do not use Actions cache/artifacts as canonical state.
- Do not add a new package; Phase 5 fits the locked Python/httpx/Pydantic/sqlite3/pytest stack.
- Do not weaken or bypass the Phase 4 protected publication path. Phase 5 should call it and preserve its reconciliation and human-control boundary.
- Phase 6, not Phase 5, owns the five-real-repository adversarial acceptance campaign.

## No Analog Found

No likely Phase 5 file lacks a usable codebase analog. The new Search query policy and state-branch JSON root are new domain content, but their implementation patterns are already established by Phase 3 versioned profiles, Phase 1/3 canonical hash chains, Phase 1 snapshot state, and Phase 4 bounded Git-object/ref operations.

## Metadata

**Analog search scope:** `config/`, `src/skillscout/domain/`, `src/skillscout/application/`, `src/skillscout/adapters/`, `tests/`, `tools/`, `.github/workflows/`

**Primary analog files read:** 19

**Pattern extraction date:** 2026-07-27

**Source constraints:** `.planning/phases/05-automated-discovery-operations/05-RESEARCH.md`, `.planning/ROADMAP.md` Phase 5, `.planning/REQUIREMENTS.md` DISC-01..03 and OPS-02..03, and `AGENTS.md`
