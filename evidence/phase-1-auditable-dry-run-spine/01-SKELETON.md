# Walking Skeleton — SkillScout

**Phase:** 1  
**Generated:** 2026-07-16

## Capability Proven End-to-End

> A SkillScout operator can run one frozen local fixture through Scout → Filter → Reader → Extractor → Qualifier → Generator → Validators → Reviewer → publication planning, then inspect durable structured evidence and a local publication plan without any remote capability or write.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Application framework | Python 3.13.14 packaged CLI using stdlib `argparse` and Pydantic 2.13.4 | The operator-facing product surface is a command, and strict typed contracts are the central architectural boundary. |
| Package and build | Checksum-verified repository-local uv 0.11.29, Astral managed CPython 3.13.14 build 20260623, exact `uv-build==0.11.29`, checked-in Gate-B-approved `uv.lock`, `src/` layout | Two distinct human gates approve immutable toolchain/direct artifacts and then the complete transitive graph before any build/import/test. |
| Data layer | stdlib `sqlite3` schema v1 → transactional v2 plus atomically written content-addressed JSON manifests | The first runnable slice writes a durable versioned format; `BEGIN IMMEDIATE` migration proves later contracts preserve existing runs/checkpoints. |
| Authentication | None in Phase 1; no credential-bearing or remote adapter is present | The frozen-fixture slice needs no external identity, and omitting remote capabilities is the strongest dry-run boundary. |
| Deployment target | Documented local commands using `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" UV_MANAGED_PYTHON=1 UV_PYTHON_DOWNLOADS=never "$PWD/.tools/uv-0.11.29/bin/uv" run --locked skillscout ...` | Each command independently binds the reviewed repo-local uv and managed CPython without ambient PATH/export assumptions; hosted automation begins in Phase 5. |
| Directory layout | `src/skillscout/{cli,domain,application,adapters}` with tests under `tests/` | Keeps domain contracts, orchestration and local I/O independently replaceable while remaining a compact modular monolith. |

## Stack Touched in Phase 1

- [ ] Project scaffold — verified repository-local uv/managed Python, two supply-chain gates, packaged project, exact build backend/lock, pytest and Ruff.
- [ ] Routing — real `dry-run` and `inspect-run` CLI subcommands.
- [ ] Database — real SQLite schema-v1 writes, transactional v1→v2 migration, attempts/results/checkpoints/manifests and real inspect reads.
- [ ] UI — operator invokes the packaged CLI and receives structured JSON summaries and exit codes.
- [ ] Deployment — documented local locked build, happy-path, Generator interruption, Validators-first resume and inspect commands; every command repeats the exact repo-local uv/managed-Python/no-download prefix inline.

## Out of Scope (Deferred to Later Slices)

- Live GitHub Search, repository filtering, bounded GitHub content reading and licenses.
- OpenAI requests, semantic extraction, generation and independent review.
- Agent Skill directories and official Agent Skills validation.
- GitHub App credentials, publication branches, Draft PR creation or any remote write.
- GitHub Actions scheduling and persistent `skillscout-state` branch synchronization.
- Candidate repository cloning, dependency installation, import, build, script execution or generated `scripts/`.
- Web UI, multi-tenancy, private repositories, vector search and automatic merge.

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without weakening its contracts or side-effect boundary:

- Phase 2: replace deterministic fixture semantics with safe single-public-repository filtering, bounded reading and `WorkflowSpec` extraction.
- Phase 3: qualify a `WorkflowSpec`, generate a documentation-only Skill, validate it and obtain an independent structured review.
- Phase 4: add a least-privilege GitHub App adapter that can create or update only an isolated Draft PR workflow.
- Phase 5: add bounded GitHub Search, scheduling and durable state-branch operations.
- Phase 6: prove the complete MVP against five pinned public repositories and adversarial inputs.
