---
phase: 01-auditable-dry-run-spine
plan: "15"
subsystem: cli-recovery-security
tags: [argparse, closed-diagnostics, finite-retry, resume-events, no-replay]

requires:
  - phase: 01-auditable-dry-run-spine
    provides: schema-v3 event-first exact-identity resume and fully verified public reuse authority
provides:
  - One fixed non-echoing JSON boundary for every argparse failure shape
  - Finite retry classification for sanitized unexpected processor interruptions
  - Fail-once and exhaustion evidence that resumes at the failed stage without replaying a verified prefix
affects: [cli-security, pipeline-recovery, audit-diagnostics, phase-01-gap-closure]

tech-stack:
  added: []
  patterns:
    - parser-generated failure text is discarded before one closed diagnostic is emitted
    - unexpected processor exceptions share the existing digest-scoped finite transient budget
    - event-first recovery selects the verified checkpoint before retrying only the failed stage

key-files:
  created: []
  modified:
    - src/skillscout/application/ports.py
    - src/skillscout/application/pipeline.py
    - src/skillscout/cli.py
    - tests/test_pipeline_resume.py
    - tests/test_cli_security.py

key-decisions:
  - "Discard every argparse-generated message and rejected token inside SafeArgumentParser, while preserving status-zero help as a separate stdout-only path."
  - "Classify the fixed pipeline_interrupted outcome as transient only through the existing RetryPolicy ceiling; permanent stage failures remain non-retryable."
  - "Retain the 01-13/01-14 event ledger as resume authority and prove recovery by comparing prefix rows, manifest bytes, processor calls, and the checkpoint-bound resume event."

patterns-established:
  - "CLI rejection: every nonzero parser exit becomes the same canonical JSON object and process status 2."
  - "Unexpected recovery: exception arguments are discarded, the failed attempt is retryable, and the next invocation starts at the verified failed stage."

requirements-completed: [OPS-01, OPS-04]

coverage:
  - id: D1
    description: "Invalid choices, unknown options or commands, missing values, and missing required arguments exit 2 with one fixed non-echoing diagnostic and no durable files."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "tests/test_cli_security.py#test_argparse_failures_are_byte_exact_non_echoing_and_non_durable"
        status: pass
      - kind: integration
        ref: "tests/test_cli_security.py#test_safe_argument_parser_is_used_for_root_and_subparsers"
        status: pass
    human_judgment: false
  - id: D2
    description: "A fail-once unexpected exception resumes at the failed stage while preserving the verified six-stage prefix and sanitized durable evidence."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_fail_once_unexpected_exception_resumes_failed_stage_without_prefix_replay"
        status: pass
    human_judgment: false
  - id: D3
    description: "Three unexpected failures exhaust one reusable digest, the fourth invocation stops before processor work, changed identity gets a separate budget, and permanent failures remain single-invocation."
    requirement: OPS-04
    verification:
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_unexpected_exception_exhaustion_is_finite_and_identity_scoped"
        status: pass
      - kind: integration
        ref: "tests/test_pipeline_resume.py#test_permanent_error_is_not_invoked_twice_for_same_digest"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-19
status: complete
---

# Phase 01 Plan 15: Closed CLI Diagnostics and Finite Unexpected Recovery Summary

**A non-echoing argparse boundary and digest-scoped unexpected-interruption retries close CR-03 and WR-01 without weakening event-first resume or permanent-failure safety.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-19T10:48:37Z
- **Completed:** 2026-07-19T10:56:53Z
- **Tasks:** 2 TDD tasks
- **Files modified:** 5

## Accomplishments

- Added `invalid_cli_arguments` to the closed bounded ASCII vocabulary and routed root and subparser failures through `SafeArgumentParser` without usage text, choices, parser messages, or rejected argv.
- Made sanitized unexpected processor exceptions retryable under the unchanged three-attempt reusable-digest ceiling while leaving explicit permanent failures non-retryable.
- Proved event-first recovery resumes at Validators after a generator checkpoint, leaves the six successful prefix calls and persisted evidence unchanged, and never persists credential/path exception canaries.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 01-15-01 RED: Hostile non-echoing argparse matrix** - `ca84402` (test)
2. **Task 01-15-01 GREEN: Fixed SafeArgumentParser boundary** - `18aa86a` (feat)
3. **Task 01-15-02 RED: Fail-once and finite unexpected-retry matrix** - `58bcc63` (test)
4. **Task 01-15-02 GREEN: Policy-consistent interruption retry** - `ae61fb4` (feat)

## Byte-Exact CLI Diagnostic

Every parser rejection writes these exact UTF-8 bytes to stderr and nothing to stdout:

```text
b'{"error":{"code":"invalid_cli_arguments","summary":"Command-line arguments were rejected."}}\n'
```

| Rejected shape | Exit | stdout | stderr | Durable working-directory surface |
|---|---:|---|---|---|
| Invalid `--fail-after` choice | 2 | empty | exact fixed JSON | none |
| Unknown option plus value | 2 | empty | exact fixed JSON | none |
| Unknown subcommand | 2 | empty | exact fixed JSON | none |
| Missing option value | 2 | empty | exact fixed JSON | none |
| Missing required options | 2 | empty | exact fixed JSON | none |

Credential, absolute-path, newline/control, Unicode, and 4-KiB oversized canaries were absent from both streams and every temporary-directory byte. Root `--help` remains status 0, stdout-only, and non-durable.

## Retry Attempt Matrix

| Identity / invocation | Processor reached | Durable attempt result | Retryable | Outcome |
|---|---|---|---:|---|
| Original identity, attempt 1 | yes | `pipeline_interrupted` with fixed summary | true | sanitized interruption |
| Original identity, attempt 2 | yes | `pipeline_interrupted` with fixed summary | true | sanitized interruption |
| Original identity, attempt 3 | yes | `pipeline_interrupted` with fixed summary | true | sanitized interruption |
| Original identity, invocation 4 | no | no fourth attempt row | n/a | `retry_exhausted` |
| Changed canonical identity, attempt 1 | yes | `pipeline_interrupted` with fixed summary | true | separate budget |
| Explicit permanent failure, invocation 2 | no | original non-retryable row retained | false | `stage_permanent_failure` |

The maximum remains three attempts. No schema, attempt identity, retry-policy version, or permanent-failure semantics changed.

## No-Replay Evidence

- The fail-once processor completed Scout through Generator once, then raised at Validators with credential and path exception arguments.
- The retry appended a checkpoint-bound resume event with `reused_stage_count = 6` and `checkpoint_stage = generator` before new processor work.
- Scout through Generator processor call counts remained exactly one; Validators was called twice total; Reviewer and Publication Planner were called once.
- Every successful prefix attempt row, result row, checkpoint row, manifest locator, hash, and manifest byte remained equal across retry.
- Failed Validators evidence contained only `pipeline_interrupted`, its fixed summary, and `retryable = 1`; canaries were absent from the database, manifests, publication plan, and public exception text.

## Files Created/Modified

- `src/skillscout/application/ports.py` - Adds the fixed `INVALID_CLI_ARGUMENTS` code and bounded summary.
- `src/skillscout/cli.py` - Adds and uses `SafeArgumentParser` for the root and every subparser.
- `src/skillscout/application/pipeline.py` - Includes `PIPELINE_INTERRUPTED` in the default finite transient-code set.
- `tests/test_cli_security.py` - Adds the subprocess disclosure and zero-durability matrix plus help/parser-class coverage.
- `tests/test_pipeline_resume.py` - Adds fail-once no-replay and finite identity-scoped unexpected-exception recovery coverage.

## Decisions Made

- Parser status zero continues through argparse's normal help exit; every nonzero parser exit ignores its message and emits the same fixed status-2 JSON diagnostic.
- Unexpected exceptions remain semantically distinct from explicit permanent stage failures: only their sanitized `PIPELINE_INTERRUPTED` code enters the existing transient allowlist.
- Retry recovery continues to use the verified resume event and latest checkpoint from Plans 01-13/01-14; no parallel counter, weaker row read, or replay fallback was added.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Tracking integrity] Corrected legacy STATE and ROADMAP projections after registered handler drift**
- **Found during:** Sequential close-out after both tasks.
- **Issue:** The registered progress handler reported 94% but rewrote the nested STATE percentage as 0, while the roadmap handler interpreted this project's legacy Requirements column as a plan-count column and malformed the Phase 1 row.
- **Fix:** Ran the required handlers first, then restored the already-established legacy projection fields to the handler's own 15/16 and 94% counts; no product, requirement, or configuration authority changed.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** STATE shows Plan 15 of 16 and 94%; ROADMAP marks 01-15 complete and retains its four-column Phase/Status/Requirements/Completed contract.
- **Committed in:** Plan tracking metadata commit.

---

**Total deviations:** 1 auto-fixed (1 Rule 1 tracking-integrity repair).
**Impact on plan:** Close-out metadata now reflects the completed plan without changing implementation scope or safety behavior.

## Issues Encountered

- The repository sandbox denied the first `.git/index.lock` write. The exact scoped commit was retried through the approved git path with normal hooks; no hook was bypassed and no extra file was staged.

## Verification Evidence

- Task 01 RED: 6 intended failures exposed raw argparse output and the missing parser class.
- Task 01 focused GREEN: `7 passed`; combined CLI security/dry-run regression: `51 passed`.
- Task 02 RED: 2 intended failures exposed non-retryable interruption classification.
- Task 02 focused GREEN: `4 passed`; combined CLI security/resume regression: `83 passed`.
- Full locked offline suite: `275 passed`.
- Full Ruff scan across `src` and `tests`: all checks passed.
- `uv.lock` SHA-256: `caeeddcf4a6d5758d0b4182b49bf87730c2351a6f9d06986ebf612c7e5b4ac32`.
- Frozen schema-v1 database SHA-256: `49fa8067a2cc7e55b3afb2e2c93aca91f2b3d6cfbaee1bc32242f7b175bc0251`.
- User-owned `.planning/config.json` SHA-256 remained `5c5acc837fef244afd431f542223618d8abd043eb77b0ef9e08b98267d9d3219` and was never staged.

## Known Stubs

None.

## Threat and Safety Scan

- T-01-15-01 is mitigated by discarding all parser-generated failure detail and emitting only the fixed closed diagnostic.
- T-01-15-02 and T-01-15-03 are mitigated by the unchanged three-attempt reusable-digest ceiling and matching durable retryable classification.
- T-01-15-04 remains protected by verified checkpoint selection and event-first resume; successful prefix work is not replayed.
- T-01-15-SC remains satisfied: the approved lockfile and frozen schema-v1 fixture hashes are unchanged.
- No new network endpoint, authentication path, file-access pattern, database schema, dependency, remote-write authority, or executable-source surface was introduced.

## User Setup Required

None - no dependency, credential, network, remote-write, or external-service setup is required.

## Next Phase Readiness

- CR-03 and WR-01 are closed with deterministic subprocess and durable recovery evidence.
- Plan 01-16 can bind the remaining evidence-authority gap without compensating for parser disclosure or unexpected-interruption retry defects.

---
*Phase: 01-auditable-dry-run-spine*
*Completed: 2026-07-19*

## Self-Check: PASSED

- All five modified production/test files and this summary exist.
- TDD commits `ca84402`, `18aa86a`, `58bcc63`, and `ae61fb4` are present in git history in RED/GREEN order.
- All three coverage deliverables classify as fully auto-covered with passing integration evidence.
- Focused acceptance checks, the 275-test locked offline suite, full Ruff scan, diff checks, and protected hashes passed.
- No tracked file was deleted, no generated file remains untracked, and `.planning/config.json` remains the sole user-owned uncommitted change.
