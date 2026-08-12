# Phase 3: Validated Skill Candidate - Pattern Map

**Mapped:** 2026-07-23
**Authoritative input:** `03-RESEARCH.md` (architecture reset)
**Files classified:** 38 new or modified logical paths/groups
**Analogs found:** 36 / 38

## Authoritative Architecture Lock

Phase 3 is a **separate local pipeline over one verified Phase 2 result**. It is not a Scout-to-Reviewer prefix, does not replay or import Scout/Reader/Extractor rows, and must not extend the global-prefix `PIPELINE_PROFILES` rules in `src/skillscout/application/pipeline.py:168-188`.

The fixed Phase 3-relative sequence is `(QUALIFIER, GENERATOR, VALIDATOR, REVIEWER)`. Its first row is rooted in `CandidateExecutionAuthorityV1`. Keep the existing Phase 1/2 verifier and its global enum-index checks unchanged; implement a dedicated Phase 3-relative ledger/verifier.

Before any Phase 3 lookup or ledger creation:

1. Load a strict, bounded `CandidateSubjectDescriptorV1` using a new loader.
2. Resolve it through a read-only Phase 2 query seam.
3. Reverify the referenced completed Phase 2 chain and Extractor output anchor.
4. Recover exactly one complete `WorkflowSpec`, recompute `WorkflowSpecAuthorityV1`, and compare all descriptor authority.
5. Construct the complete pre-lookup `CandidateExecutionAuthorityV1`.

Any unavailable/rejected/incomplete/malformed/mismatched Phase 2 source yields sanitized `candidate_source_unavailable` with **zero Phase 3 rows, calls, validator executions, or retry effects**. It is not a Phase 3 terminal branch.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/skillscout/domain/candidate_authority.py` | model + utility | transform | `domain/models.py`; `domain/canonical.py`; `domain/extraction.py` | composite role/data-flow |
| `src/skillscout/domain/qualification.py` | model + policy utility | transform | `domain/extraction.py` | role/data-flow |
| `src/skillscout/domain/skill_artifacts.py` | model + renderer | transform + file-I/O manifest | `domain/canonical.py`; terminal writer in `application/pipeline.py` | composite |
| `src/skillscout/domain/validation.py` | model + policy service | batch + file-I/O | `domain/extraction.py` boundary validation | role-match |
| `src/skillscout/domain/review.py` | model + policy utility | transform | `domain/extraction.py`; `domain/models.py` summaries | composite |
| `src/skillscout/adapters/phase2_state.py` | query adapter | CRUD/read-only | `application/ports.py`; `adapters/state.py` verified-chain query | exact role, narrower flow |
| `src/skillscout/adapters/openai_generate.py` | service adapter | request-response | `adapters/openai_extract.py` | exact |
| `src/skillscout/adapters/openai_review.py` | service adapter | request-response | `adapters/openai_extract.py` | exact |
| `src/skillscout/adapters/skills_ref.py` | service adapter | bounded file-I/O | no internal official-validator adapter | no internal analog |
| `src/skillscout/application/ports.py` | port/protocol | request-response + persistence | existing closed ports in same file | exact modification |
| `src/skillscout/application/candidate_source.py` | loader + service | bounded file-I/O + query | `adapters/subjects.py`; `cli.py`; `adapters/state.py` | composite |
| `src/skillscout/application/phase3.py` | orchestrator | event-driven + transform | `application/pipeline.py`, excluding its global-prefix model | partial composite |
| `src/skillscout/adapters/state.py` | persistence adapter | CRUD + event-driven | existing ledger/manifest/lock implementation | exact concepts, separate profile required |
| `src/skillscout/domain/models.py` | persistence model | transform | `RunIdentity`, `StageEnvelope`, `VerifiedRunChain` | exact concepts, separate contracts required |
| `src/skillscout/cli.py` | controller | request-response + file-I/O | existing `extract-repo` command | exact |
| `pyproject.toml` | config | batch | existing exact dependency pins | exact modification after Gate A3 |
| `uv.lock` | config | batch | current exact lock workflow | exact modification after Gate B3 |
| `config/supply-chain/phase3-gate-b3.lock.sha256` | config/authority | file-I/O | immutable hashes in `tools/verify_phase1_gap_evidence.py` | partial |
| `tools/verify_phase3_gate_b3.sh` | preflight utility | file-I/O + process gate | `tools/verify_phase1_gap_evidence.py` | partial; new fail-before-exec guarantee |
| `tools/verify_phase3_acceptance.py` | verification utility | batch + file-I/O | `tools/verify_phase1_gap_evidence.py` | role/data-flow |
| `tests/recorded_transport.py` | test utility | request-response | existing `RecordedTransport` helpers | exact modification |
| `tests/fixtures/openai/generator/*.json` | test fixture | request-response | existing recorded OpenAI fixtures | exact |
| `tests/fixtures/openai/reviewer/*.json` | test fixture | request-response | existing recorded OpenAI fixtures | exact |
| `tests/fixtures/skills/**` | test fixture | file-I/O | no existing Skill package fixture tree | no analog |
| `tests/test_candidate_source.py` | contract/integration test | file-I/O + query | `test_phase2_contracts.py`; `test_state_integrity.py` | composite |
| `tests/test_candidate_authority.py` | contract test | transform | `test_stage_contracts.py`; `test_extractor_boundary.py` | composite |
| `tests/test_qualification.py` | policy test | transform | extraction boundary matrices | role-match |
| `tests/test_skill_generation.py` | unit/integration test | transform + file-I/O | terminal-artifact tests in `test_phase2_pipeline.py` | partial composite |
| `tests/test_lineage.py` | contract/policy test | transform + query | identity sensitivity tests in `test_stage_contracts.py` | partial |
| `tests/test_openai_generate.py` | adapter test | request-response | `tests/test_openai_extract.py` | exact |
| `tests/test_skill_validation.py` | adversarial integration test | batch + file-I/O | extraction boundary and state-integrity matrices | composite |
| `tests/test_openai_review.py` | adapter test | request-response | `tests/test_openai_extract.py` | exact |
| `tests/test_phase3_pipeline.py` | integration test | event-driven + persistence | `tests/test_phase2_pipeline.py`; `tests/test_state_integrity.py` | partial composite |
| `tests/test_cli_validate_skill.py` | CLI integration test | request-response + file-I/O | `tests/test_cli_extract_repo.py` | exact |
| `tests/test_cli_security.py` | security test | request-response | existing parser/non-echo assertions | exact modification |
| `tests/test_phase3_lock_preflight.py` | process-gate test | file-I/O + process | `tests/test_phase1_evidence_verifier.py` | partial |
| `tests/test_phase3_acceptance_tool.py` | verification-tool test | batch + file-I/O | `tests/test_phase1_evidence_verifier.py` | role-match |
| `tests/test_phase1_gap_closure.py` | source-policy test | static AST scan | existing import-confinement test in same file | exact modification |

## Pattern Assignments

### Candidate ingress: `candidate_authority.py`, `candidate_source.py`, `phase2_state.py`, and their tests

**Strict model analog:** `src/skillscout/domain/subjects.py:52-65`

```python
class RepositorySubject(StrictFrozenModel):
    schema_version: Literal["1"]
    subject_id: SubjectId
    repository: RepositoryUrl
    ref: SubjectRef | None = None

    @model_validator(mode="after")
    def validate_subject_matches_url(self) -> RepositorySubject:
        path = self.repository.removeprefix(_URL_PREFIX).removesuffix(".git")
        if self.subject_id != f"repo:{path}":
            raise ValueError("subject_id and repository URL disagree")
        return self
```

Define a separate frozen, `extra="forbid"` `CandidateSubjectDescriptorV1` containing exactly the descriptor schema, completed Phase 2 run ID, expected Phase 2 profile/producer, authoritative Extractor output/verified-chain anchor, selected full workflow fingerprint, expected complete WorkflowSpec-authority digest, and optional `PriorLineageBindingV1`. Do not add fields to `RepositorySubject` and do not change `load_subject()`.

**Safe loader analog:** `src/skillscout/adapters/subjects.py:34-70`

```python
before_path = os.lstat(path)
if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(before_path.st_mode):
    raise SafeFailure(ErrorCode.INVALID_SUBJECT)

flags = os.O_RDONLY
for flag_name in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
    flags |= getattr(os, flag_name, 0)
descriptor = os.open(path, flags)
before_fd = os.fstat(descriptor)
if before_fd.st_size > MAX_SUBJECT_BYTES:
    raise SafeFailure(ErrorCode.INVALID_SUBJECT)
...
after_fd = os.fstat(descriptor)
if _identity(before_fd) != _identity(after_fd):
    raise SafeFailure(ErrorCode.INVALID_SUBJECT)
```

Copy the ownership, non-link regular-file, `O_NOFOLLOW`, byte-cap, stable-identity, UTF-8/JSON, strict-Pydantic, and no-echo failure pattern into a separately named candidate-descriptor loader. Tests copy the full matrix from `tests/test_phase2_contracts.py:85-218` and CLI no-state/no-canary assertions from `tests/test_cli_extract_repo.py:292-327`.

**Verified query analog:** `src/skillscout/application/ports.py:171-190` and `src/skillscout/adapters/state.py:1734-2041`

```python
class StateStore(Protocol):
    def verify_run_chain(
        self,
        run_id: str,
        expected_identity: RunIdentity | None = None,
    ) -> VerifiedRunChain: ...
```

`PhaseTwoCandidateSource.resolve(descriptor)` must call the unchanged Phase 2 chain verifier and then independently require the expected Phase 2 producer/profile, completed status, exact Scout-to-Extractor chain, successful candidate outcome, exact Extractor output anchor, and exactly one selected full fingerprint. Strictly parse the selected complete `WorkflowSpec`, recompute its complete authority, and return only verified repository ID/URL, commit, license, workflow, and Phase 2 anchor facts.

Do not trust `ExtractionSummary`: `src/skillscout/domain/models.py:487-507` contains only outcome/count/fingerprints. Recover the complete workflow from the verified Extractor `StageEnvelope` (`domain/models.py:144-169`). The read-only resolver must never create a Phase 3 row, call a Phase 2 processor, call GitHub/OpenAI, or reinterpret an upstream business branch as Phase 3 state.

### Complete authorities and lineage: `candidate_authority.py`, `models.py`, `test_candidate_authority.py`, `test_lineage.py`

**Canonical digest analog:** `src/skillscout/domain/canonical.py:24-40,86-90`

```python
def stage_manifest_hash(envelope: StageEnvelope) -> str:
    preimage = envelope.model_dump(
        mode="json",
        exclude_none=False,
        exclude={"manifest_hash"},
    )
    return sha256_digest(preimage)
```

Use compact, sorted canonical JSON and a full tagged SHA-256. Self-hashed structures exclude only their own digest field.

**Complete workflow versus fingerprint analog:** `src/skillscout/domain/extraction.py:91-134`

```python
return sha256_digest(
    {
        "fingerprint_version": FINGERPRINT_VERSION,
        "repo_id": repo_id,
        "goal": normalize_for_fingerprint(goal),
        "steps": [normalize_for_fingerprint(step) for step in steps],
    }
)
```

That existing `wf-fingerprint-v1` intentionally omits title, applicability, inputs/outputs, confidence, evidence, excerpts, and content hashes. Treat it only as the selected workflow-version discriminator.

`WorkflowSpecAuthorityV1` must digest the **entire strictly parsed `WorkflowSpec`**, including every schema/fingerprint version, nested workflow/step evidence item, path, excerpt, and content hash, plus the authoritative verified Phase 2 Extractor envelope/output anchor. Test mutation sensitivity for every field and anchor.

`CandidateExecutionAuthorityV1` is created before Phase 3 lookup and is the sole resume/completed lookup key. Its canonical preimage contains:

- `WorkflowSpecAuthorityV1` digest and selected full fingerprint;
- optional canonical `PriorLineageBindingV1` digest;
- qualification policy and report schema versions;
- configured Generator model plus generator prompt/output schema versions;
- immutable `RENDERER_VERSION`, artifact schema, and provenance schema;
- exact official-validator distribution/version/hash and approved lock authority, custom validation policy, and report schema;
- configured Reviewer model plus reviewer prompt/output/policy versions;
- immutable `ELIGIBILITY_POLICY_VERSION`;
- Phase 3 producer/profile and retry-policy versions.

Only configured model IDs belong here. Actual returned model IDs, resolved lineage, generated bytes, validation, review, and eligibility are later facts and must not enter pre-lookup authority.

**Lineage target contract:** a new lineage is the full digest of `lineage-v1`, numeric repository ID, and the **initial** complete WorkflowSpec-authority digest. Never shorten it for authority.

```python
sha256_digest(
    {
        "lineage_version": "lineage-v1",
        "repository_id": repository_id,
        "initial_workflow_spec_authority_digest": initial_authority_digest,
    }
)
```

Retain an existing lineage and stable slug only through one exact approved `PriorLineageBindingV1`: repository ID, full lineage ID, stable slug, prior package digest, prior terminal-summary digest, new WorkflowSpec-authority digest, binding schema/policy version, and durable approval-record digest. Reverify that the referenced terminal proves the repository and initial authority, then recompute the lineage. No binding creates a new lineage. Stale, colliding, multiple, mismatched, or ambiguous bindings produce `lineage_rejected`; never fall back heuristically.

Title and evidence paths remain inside the complete WorkflowSpec/version authority, but they are **never** lineage preimage fields or remap/matching heuristics. An exact approved binding may survive changes to either.

### Qualification: `qualification.py` and `test_qualification.py`

**Closed-boundary analog:** `src/skillscout/domain/extraction.py:164-217`

Copy the pattern of immutable typed reports, named/versioned deterministic rules, bounded reasons, and explicit cross-field validation. A low score and any hard fail both map to `qualification_rejected`; the report binds WorkflowSpec authority, execution authority, policy version, and report schema.

Use table-driven boundary tests for score 74/75/76, confidence 0.699/0.700, two-step hard fail, source-execution hard fail, and valid evidence. Do not ask the Generator or Reviewer to make the qualification decision.

### Frozen generation: `skill_artifacts.py`, `test_skill_generation.py`, and Skill fixtures

**Owner module:** `src/skillscout/domain/skill_artifacts.py`

```python
RENDERER_VERSION: Final = "skill-renderer-v1"
```

This constant is code-owned producer authority, not a CLI/config flag.

The Generator returns a strict bounded semantic draft. SkillScout validates it and deterministically renders the allowed package. `GeneratedArtifactIdentityV1` is then computed from the canonical draft plus a generation-time authority projection containing WorkflowSpec authority, selected fingerprint, resolved lineage/slug, qualification-report digest/policy/schema, configured and actual Generator IDs, generator prompt/output schema, `RENDERER_VERSION`, artifact/provenance schemas, and Phase 3 producer/retry versions. It excludes validator, Reviewer, eligibility, and all other post-generation facts.

Provenance is generation-time-only. It may contain verified repository URL/ID/commit/license, full workflow/evidence, WorkflowSpec authority, qualification versions, configured/actual Generator, renderer/artifact/provenance versions, and bounded Generator telemetry. It must not contain the package digest, validation facts, Reviewer facts, attestation, eligibility, or any future fact.

After provenance is finalized, freeze package bytes and compute an **external** `package_digest` from a canonical ordered manifest of path to content hash, mode, and size. Never write the digest back into the package.

**Anchored file-I/O analogs:** `src/skillscout/adapters/localfs.py:75-143,175-185,197-346` and `src/skillscout/application/pipeline.py:607-695`

Copy descriptor-anchored directory admission, child-name validation, no-follow stable reads, private regular files, retained `flock`, stale-temp recovery, atomic replacement/restore, and directory fsync. Package paths must be closed, modes must be fixed, and no scripts/binaries are generated.

### Validation and independent review: `validation.py`, `skills_ref.py`, `review.py`, and tests

`skills_ref.validate(Path)` receives only an already-admitted exact package root through a narrow adapter. Catch exceptions and return a closed sanitized validator result. It is one validation family, not the sole validator and not authority to read arbitrary paths.

Run custom deterministic checks for structure, closed paths/depth, links and TOCTOU, hard links, mode, binary content, secrets, prompt injection, URLs/download-execute patterns, provenance bindings, hashes, and bounded-copy policy. `ValidationReport` binds WorkflowSpec/execution/artifact identities, frozen package digest, `RENDERER_VERSION`, exact official-validator distribution/hash, custom policy version, and report schema. Package bytes are immutable before validation starts.

**Owner module:** `src/skillscout/domain/review.py`

```python
ELIGIBILITY_POLICY_VERSION: Final = "candidate-eligibility-v1"
```

The Reviewer judges the frozen package and clean validation report; it never edits them. `ReviewAttestationV1` is external and binds package digest, validation-report digest, configured/actual Reviewer IDs, review prompt/output/policy versions, outcome, verdict, confidence, bounded reasons, and bounded telemetry. Never place it in the package.

Eligibility is local deterministic policy: Reviewer `YES` and confidence at least `0.80`, under `ELIGIBILITY_POLICY_VERSION`. A Reviewer claim cannot override validation or mutate the package.

### OpenAI boundaries: `openai_generate.py`, `openai_review.py`, recorded fixtures, and adapter tests

**Exact adapter analog:** `src/skillscout/adapters/openai_extract.py:58-82,97-176`

```python
self._client = OpenAI(
    api_key=api_key,
    max_retries=0,
)
...
response = self._client.responses.parse(
    model=self._model,
    input=[
        {"role": "developer", "content": EXTRACT_INSTRUCTIONS_V1},
        {"role": "user", "content": user_payload},
    ],
    text_format=ExtractorResponse,
    store=False,
    max_output_tokens=self._max_output_tokens,
)
```

Each `generate()` or `review()` attempt makes exactly one Responses request. Use `max_retries=0`, `store=False`, bounded output, no tools, strict Structured Outputs, developer/user separation, and closed refusal/incomplete/schema/transient error mapping. Pipeline retry owns retries. Record bounded request/usage telemetry, configured model, and actual returned model without leaking keys or raw untrusted source.

Tests mirror `tests/test_openai_extract.py:62-109,142-262`: exact request JSON, absent tools, key only in Authorization, parsed success, refusal, incomplete, schema-invalid, 429, and 500. Reviewer fixtures also cover YES, NO, 0.799, and 0.800.

**Exact source-wide OpenAI import allowlist** relative to `src/skillscout/`:

```python
{
    "adapters/openai_extract.py",
    "adapters/openai_generate.py",
    "adapters/openai_review.py",
}
```

Extend the AST confinement pattern at `tests/test_phase1_gap_closure.py:150-170,789-824` and assert equality with the actual importer set. Do not use globs, directory carve-outs, or a test exception. The existing Extractor path remains allowed and unchanged.

### Phase 3 ledger, orchestration, terminal summaries, and exact reuse

**Durable ledger/manifest analogs:**

- `src/skillscout/domain/models.py:197-241` — complete pre-lookup `RunIdentity`.
- `src/skillscout/adapters/state.py:1597-1685` — creation and exact-identity lookups.
- `src/skillscout/adapters/state.py:1734-2041` — full chain recomputation.
- `src/skillscout/adapters/state.py:2252-2426` — manifest-first persistence and verified reads.
- `src/skillscout/adapters/state.py:571-716,2639-2660` — descriptor-anchored retained state lock.

Copy the separation of runs, attempts, results, checkpoints, and hash-linked resume events; manifest-first/ledger-second commits; canonical content-addressed manifests; complete identity lookup; retained lock; and fail-closed verification. Do not copy the global stage-index assumption.

Implement a dedicated Phase 3 profile-relative verifier that enforces exactly `(QUALIFIER, GENERATOR, VALIDATOR, REVIEWER)`, relative index 0..3, `CandidateExecutionAuthorityV1` as genesis/input authority, every attempt/event/result/output-hash/checkpoint continuity rule, and the legal terminal branch for the observed prefix. Do not add fake Scout/Reader/Extractor rows, import Phase 2 records, or relax `application/pipeline.py:168-188`, `domain/models.py:300-305,421-425`, or `adapters/state.py:1827-1837,2304-2315`.

**Phase 3 terminal matrix:**

| Outcome | Package | Validation report | Review attestation | Required note |
|---|---:|---:|---:|---|
| `qualification_rejected` | no | no | no | lineage status is `not_evaluated_qualification_rejected` |
| `lineage_rejected` | no | no | no | exact binding failure; human review |
| `generator_refusal` | no | no | no | closed Generator outcome |
| `generator_incomplete` | no | no | no | closed Generator outcome |
| `generator_schema_failure` | no | no | no | closed Generator outcome |
| `validation_rejected` | frozen | yes, errors | no | companion review status `review_skipped_validation_errors` |
| `reviewer_refusal` | frozen | yes, clean | yes | attestation records refusal |
| `reviewer_incomplete` | frozen | yes, clean | yes | attestation records incomplete |
| `reviewer_schema_failure` | frozen | yes, clean | yes | attestation records schema failure |
| `review_rejected` | frozen | yes, clean | yes | Reviewer NO |
| `review_low_confidence` | frozen | yes, clean | yes | Reviewer YES below 0.80 |
| `eligible_local_candidate` | frozen | yes, clean | yes | Reviewer YES at or above 0.80 |

Every Phase 3-owned branch stores canonical `CandidateTerminalSummaryV1` bytes externally. The summary binds execution/workflow authorities, lineage resolution, optional Generator evidence, optional artifact/package digest, optional validation-report digest, optional review-attestation digest, `ELIGIBILITY_POLICY_VERSION`, and the closed outcome.

**Partial reuse analog:** `src/skillscout/application/pipeline.py:313-339,560-583,716-781`

Phase 2 verifies an exact completed identity and reprojects a deterministic summary with no processor calls. Phase 3 must be stricter: completed lookup re-verifies the Phase 3-relative chain and reprojects the **exact stored terminal-summary bytes** and exact stored optional package/report/attestation bytes. It must not reconstruct semantically equivalent JSON. Reuse creates zero new runs, attempts, results, checkpoints, resume events, terminal rows, or summary rows and makes zero Generator, Reviewer, validator, GitHub, or OpenAI calls. Missing/tampered external bytes fail closed without partial projection.

Tests must snapshot every relevant byte sequence and every ledger table count before and after reuse for every terminal branch. Existing Phase 2 tests (`tests/test_phase2_pipeline.py:198-225`; `tests/test_cli_extract_repo.py:232-289`) prove call suppression but do not prove exact byte equality or zero-row deltas.

### CLI: `cli.py`, `test_cli_validate_skill.py`, and `test_cli_security.py`

**Composition-root analog:** `src/skillscout/cli.py:28-42,45-85`

Keep non-echo parsing and closed `SafeFailure` output. The command order is: parse candidate-descriptor path; safely load descriptor; open only the read-only Phase 2 source state; resolve/reverify the source; on success construct execution authority; then open/lookup the separate Phase 3 state and run/reuse locally. No Phase 3 path receives a `RepositorySubject` or raw Reader bundle.

CLI tests copy the zero-side-effect/call-count pattern at `tests/test_cli_extract_repo.py:139-200,232-346`: source-unavailable before Phase 3 state, every terminal branch, exact OpenAI counts, zero GitHub calls, zero remote writes, optional package materialization, hostile descriptor files, and no untrusted diagnostic echo.

### Gate A3/B3: dependency files, preflight, acceptance tool, and tests

Gate A3 is a human supply-chain decision for exactly `skills-ref==0.1.1`, official provenance, and PyPI wheel SHA-256:

```text
d35db5bb8de71ae301daf5ca9cb71f8a555e8c6f83a6d40e46a5bc09f8f461b5
```

Record the source/distribution discrepancy and absence of Trusted Publishing as review signals. If Gate A3 rejects it, stop; do not substitute another package or validator.

Gate B3 approves the exact complete transitive graph, every resolved artifact hash, and exact `uv.lock` bytes. The one-line `config/supply-chain/phase3-gate-b3.lock.sha256` is created only from that approval. Do not copy the current Phase 2/B2 lock digest as Phase 3 authority.

**Executable authority analog:** `tools/verify_phase1_gap_evidence.py:19-33,198-225,299-307,655-715`

Copy lowercase full-hash parsing, bounded regular non-link reads, immutable-input comparison, and verify-before-command ordering. `tools/verify_phase3_gate_b3.sh` must be dependency-free and run before every downstream `uv`, import, test, or official-validator command. Missing, malformed, symlinked, or mismatched authority fails before the following command/sentinel executes.

`tests/test_phase3_lock_preflight.py` adds the guarantee absent from Phase 1/2: mutate `uv.lock` and prove the downstream executable was never invoked. The acceptance tool should use a fixed command registry, offline environment where applicable, immutable pre/post checks, exact import allowlist, authority/identity matrices, terminal/reuse matrix, and remote-write/effect-ceiling canaries.

## Shared Patterns

### Strict immutable contracts

**Source:** `src/skillscout/domain/models.py:109-126`

Apply `StrictFrozenModel`, forbidden extras, bounded collections/strings, strict parsing, and cross-field validators to descriptors, authorities, reports, artifacts, attestations, and terminal summaries.

### Closed errors and no secret/untrusted echo

**Source:** `src/skillscout/application/ports.py:23-73`

Extend only the closed `ErrorCode`/`ERROR_SUMMARIES` vocabulary. Public diagnostics are sanitized. Never include raw repository text, descriptor content, model output, credentials, validator output paths, or absolute paths.

### Manifest-first durability and verified trust entry

**Source:** `src/skillscout/adapters/state.py:2252-2426`

Write immutable canonical manifest bytes before committing ledger success. On every trust entry, derive the closed locator and recompute manifest, output, row, checkpoint, and chain hashes; never trust a stored path or digest alone.

### Retained serialization authority

**Source:** `src/skillscout/adapters/state.py:687-716,2639-2660`; `src/skillscout/application/pipeline.py:607-695`

Retain the same lock descriptor through recovery, read, atomic replacement/restore, and fsync. Do not delete/recreate the lock inode. Keep state and external-artifact writers structurally aligned.

### Capability ceiling

**Source:** `src/skillscout/application/pipeline.py:63-79,832-883`; `tests/test_phase2_pipeline.py:366-424`

Phase 3 permits local state/file operations and the two bounded OpenAI `REMOTE_READ` adapters only. It makes no GitHub call after source resolution, registers no `REMOTE_WRITE`, and never constructs Publisher or merge authority.

### Semantic isolation

The complete verified `WorkflowSpec` is the sole semantic input from Phase 2. Generator and Reviewer never receive a raw Reader bundle. External text stays inert user data; model responses never supply repository, commit, license, content-hash, lineage, validator, or eligibility authority.

## Protected Phase 1/2 Seams

The planner must treat these as invariants, not extension points:

- `src/skillscout/domain/subjects.py` and `src/skillscout/adapters/subjects.py`: keep `RepositorySubject` and `load_subject()` unchanged.
- `src/skillscout/application/processors.py`: preserve `PhaseTwoProcessor` behavior and its WorkflowSpec evidence verification.
- `src/skillscout/application/pipeline.py:168-188`: do not append Phase 3 to global prefix profiles.
- `src/skillscout/adapters/state.py:1734-2041`: keep the Phase 1/2 global verifier unchanged; add a separate Phase 3 verifier.
- `src/skillscout/domain/extraction.py:124-134`: do not widen or repurpose `wf-fingerprint-v1` as complete authority or lineage.
- `src/skillscout/adapters/openai_extract.py`: preserve the already verified Extractor adapter while including it in the exact final allowlist.

## No Analog Found

| File | Role | Data Flow | Reason / Planner Direction |
|---|---|---|---|
| `src/skillscout/adapters/skills_ref.py` | service adapter | bounded file-I/O | First third-party validator adapter. Use the research-locked narrow in-process API only after Gate A3/B3 and exact package admission. |
| `tests/fixtures/skills/**` | test fixture | file-I/O | No existing Agent Skill fixture tree. Create minimal explicit valid/invalid trees and never execute/import their contents. |

There is also no exact analog for stored exact-byte `CandidateTerminalSummaryV1` reprojection or the dependency-free Gate-B3 fail-before-exec script. Use the cited composite analogs and the stricter research-locked invariants above.

## Metadata

**Analog search scope:** `src/skillscout/**`, `tests/**`, `tools/**`, Phase 1/2 plans, summaries, and verification artifacts
**Strong analogs read:** 15 source/test files plus Phase 1/2 planning evidence
**Pattern extraction date:** 2026-07-23
**Superseded assumption:** any Phase 3 design that replays or models a full Scout-to-Reviewer prefix
