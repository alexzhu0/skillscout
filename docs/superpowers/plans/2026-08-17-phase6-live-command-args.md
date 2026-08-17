# Phase 6 Live Command Argument Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the Phase 6 benchmark and replay workflow commands so they pass the existing CLI's complete authority-state contract.

**Architecture:** Keep `skillscout.cli run-acceptance` unchanged. Both workflow jobs already check out `.phase6-authority-state` and expose the immutable authority commit and digest; append those established values to each command. A static workflow test binds both invocations to all required arguments, while the source-execution verifier receives the regenerated closed-workflow digest.

**Tech Stack:** GitHub Actions YAML, Python 3.13, pytest 9, Ruff, repository-local uv 0.11.29.

## Global Constraints

- Do not change CLI parsing, semantic-provider configuration, secrets, state schemas, source execution rules, publication, Pull Request, merge, or Draft behavior.
- `run-benchmark` and `run-replay` must both receive the same three authority arguments.
- All tests use `/Users/alexzhu/Lenovo/skillscout/.tools/uv-0.11.29/bin/uv run --locked` from this isolated worktree.
- The failed live run is terminal; do not rerun it. A merged workflow change requires a fresh exact benchmark approval packet.

---

### Task 1: Bind the workflow contract in a failing regression test

**Files:**
- Modify: `tests/test_phase6_workflow.py`

**Interfaces:**
- Consumes: `_job(source, "live_benchmark")` and `_job(source, "live_replay")`.
- Produces: a regression that requires each late `run-acceptance` invocation to include the authority checkout root, commit SHA, and root digest.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("job_name", ("live_benchmark", "live_replay"))
def test_live_execution_passes_complete_authority_state_to_run_acceptance(
    job_name: str,
) -> None:
    job = _job(_source(required=False), job_name)
    assert "run-acceptance" in job
    assert '--authority-state-root ".phase6-authority-state"' in job
    assert '--authority-state-commit-sha "$PHASE6_AUTHORITY_STATE_COMMIT_SHA"' in job
    assert '--authority-state-root-digest "$PHASE6_AUTHORITY_STATE_ROOT_DIGEST"' in job
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```bash
UV_CACHE_DIR=/Users/alexzhu/Lenovo/skillscout/.tools/uv-cache /Users/alexzhu/Lenovo/skillscout/.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py -k complete_authority_state_to_run_acceptance
```

Expected: FAIL for both parameter values because the three arguments are absent.

### Task 2: Add the existing required arguments at both workflow boundaries

**Files:**
- Modify: `.github/workflows/phase6-acceptance.yml`

**Interfaces:**
- Consumes: `.phase6-authority-state`, `PHASE6_AUTHORITY_STATE_COMMIT_SHA`, and `PHASE6_AUTHORITY_STATE_ROOT_DIGEST` already established by each job.
- Produces: CLI invocations matching `run-acceptance`'s required parser contract.

- [ ] **Step 1: Append the complete authority-state arguments to benchmark**

```bash
--authority-state-root ".phase6-authority-state" \
--authority-state-commit-sha "$PHASE6_AUTHORITY_STATE_COMMIT_SHA" \
--authority-state-root-digest "$PHASE6_AUTHORITY_STATE_ROOT_DIGEST"
```

- [ ] **Step 2: Append the identical arguments to replay**

```bash
--authority-state-root ".phase6-authority-state" \
--authority-state-commit-sha "$PHASE6_AUTHORITY_STATE_COMMIT_SHA" \
--authority-state-root-digest "$PHASE6_AUTHORITY_STATE_ROOT_DIGEST"
```

- [ ] **Step 3: Run the focused test to verify GREEN**

Run the Task 1 command.

Expected: `2 passed`.

### Task 3: Rebind the verifier to the reviewed workflow bytes

**Files:**
- Modify: `tools/verify_phase6_source_execution.py`

**Interfaces:**
- Consumes: the repaired `.github/workflows/phase6-acceptance.yml` and the
  verifier's existing `LIVE_AUTHORITY_JOB` sentinel normalization.
- Produces: the exact `EXPECTED_CLOSED_WORKFLOW_SOURCE_DIGESTS` entry for the
  reviewed Phase 6 workflow, preserving the closed-world verifier.

- [ ] **Step 1: Capture the existing verifier failure**

Run:

```bash
UV_CACHE_DIR=/Users/alexzhu/Lenovo/skillscout/.tools/uv-cache /Users/alexzhu/Lenovo/skillscout/.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_source_execution.py -k verifier_discovers_every_authoritative_entry_point
```

Expected: FAIL because the repaired workflow digest does not yet match the
frozen source-execution closure.

- [ ] **Step 2: Regenerate the normalized digest and update only its constant**

Use `tools.verify_phase6_source_execution._parse_jobs` and the existing
`FINAL_LIVE_AUTHORITY_JOB_SENTINEL` replacement to calculate the SHA-256 of
the repaired workflow; replace only the `.github/workflows/phase6-acceptance.yml`
digest in `EXPECTED_CLOSED_WORKFLOW_SOURCE_DIGESTS`.

- [ ] **Step 3: Re-run the Task 3 focused test to verify GREEN**

Run the Task 3 Step 1 command.

Expected: PASS.

### Task 4: Verify the repaired workflow and commit

**Files:**
- Modify: `.github/workflows/phase6-acceptance.yml`
- Modify: `tests/test_phase6_workflow.py`
- Modify: `tools/verify_phase6_source_execution.py`

**Interfaces:**
- Consumes: the repaired command contract from Tasks 1–2.
- Produces: a reviewable, tested workflow-only bug fix.

- [ ] **Step 1: Run focused workflow and security-contract tests**

```bash
UV_CACHE_DIR=/Users/alexzhu/Lenovo/skillscout/.tools/uv-cache /Users/alexzhu/Lenovo/skillscout/.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase6_workflow.py tests/test_phase6_source_execution.py tests/test_phase6_validation_map.py
```

Expected: PASS.

- [ ] **Step 2: Run static verifiers and Ruff**

```bash
/Users/alexzhu/Lenovo/skillscout/.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_source_execution.py
/Users/alexzhu/Lenovo/skillscout/.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase6_validation_map.py --plan-contract
/Users/alexzhu/Lenovo/skillscout/.tools/uv-0.11.29/bin/uv run --locked ruff check .
```

Expected: all commands report valid or exit zero.

- [ ] **Step 3: Run the full locked suite**

```bash
UV_CACHE_DIR=/Users/alexzhu/Lenovo/skillscout/.tools/uv-cache /Users/alexzhu/Lenovo/skillscout/.tools/uv-0.11.29/bin/uv run --locked pytest -q
```

Expected: PASS with only established skips.

- [ ] **Step 4: Commit the implementation**

```bash
git add .github/workflows/phase6-acceptance.yml tests/test_phase6_workflow.py
git commit -m "fix: pass Phase 6 authority state to live commands"
```

## Self-Review

- Spec coverage: Task 1 supplies the required RED evidence; Task 2 fixes both affected jobs; Task 3 verifies workflow, security, validation, lint, and full-suite behavior.
- Scope: no production Python, provider, secret, state, source-execution, or publication code changes.
- Consistency: both command lines use the authority checkout path and variables already created by their respective jobs.
