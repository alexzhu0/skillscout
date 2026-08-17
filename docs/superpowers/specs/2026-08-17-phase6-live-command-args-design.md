# Phase 6 Live Command Argument Repair

## Goal

Make the protected Phase 6 benchmark and zero-effect replay workflow commands
provide every authority argument that the existing `run-acceptance` CLI
requires.

## Scope

- Modify only the two `run-acceptance` invocations in
  `.github/workflows/phase6-acceptance.yml`.
- Add workflow regression coverage that proves both invocations carry the
  authority checkout path, authority state commit SHA, and authority state
  root digest.
- Preserve the existing preflight, state checkout, provider, secret, state
  persistence, Draft PR, and publication boundaries.

## Design

`run-acceptance` already requires these arguments:

```text
--authority-state-root
--authority-state-commit-sha
--authority-state-root-digest
```

Both protected jobs already check out the authority state at
`.phase6-authority-state` and export the matching commit and digest through
the existing `PHASE6_AUTHORITY_STATE_COMMIT_SHA` and
`PHASE6_AUTHORITY_STATE_ROOT_DIGEST` variables. Each invocation will append
the three arguments using exactly those established values. No CLI interface
or behavior changes.

The regression test will inspect the workflow as structured text and assert
that the benchmark and replay execution blocks invoke `run-acceptance` with
all three arguments. It will fail on the pre-fix workflow and on removal of
any one of the three arguments.

## Failure Handling

The already-failed benchmark run is terminal and will not be retried. Because
the workflow bytes will change, its previous approval is invalid. A new exact
approval packet is required after this fix is merged and verified.

## Acceptance Criteria

1. The two invocation sites pass the three required authority arguments.
2. The regression test fails before the workflow edit and passes after it.
3. Focused workflow tests, the Phase 6 workflow verifiers, Ruff, and the full
   locked test suite pass.
4. The PR contains no credential, provider, state-schema, source-execution,
   publication, or Draft-PR authority change.
