---
phase: 4
slug: controlled-draft-pr
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-24
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for controlled Draft PR publication.

---

## Test Infrastructure

All commands run from the repository root. Offline tests use injected transports and fixtures. The live canary is opt-in, uses the same restricted GitHub App installation identity as production, and never supplies automated cleanup or merge authority.

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x with `httpx.MockTransport` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_domain.py tests/test_github_publish_adapter.py tests/test_publication_recovery.py tests/test_publication_security.py` |
| **Full suite command** | `.tools/uv-0.11.29/bin/uv run --locked pytest -q` |
| **Static quality command** | `.tools/uv-0.11.29/bin/uv run --locked ruff check .` |
| **Network policy** | Offline by default; live canary requires explicit protected-environment configuration |
| **Estimated runtime** | Focused checks target under 60 seconds; full suite measured during execution |

---

## Sampling Rate

- **After every task commit:** Run the narrow Phase 4 test file(s) touched by the task.
- **After every plan wave:** Run the four offline Phase 4 suites plus affected regression tests.
- **Before `$gsd-verify-work`:** Full suite, static workflow checks, and reviewed live-canary evidence must be green.
- **Max feedback latency:** 60 seconds for focused offline checks.

---

## Per-Requirement Verification Map

| Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| PUB-01 | T-04-01, T-04-02 | Only configured catalog, allowed machine ref, exact frozen-manifest owned subtree, Draft PR, and configured reviewer request are reachable | contract + transport integration | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_github_publish_adapter.py -x` | ❌ W0 | ⬜ pending |
| PUB-02 | T-04-03 | Canonical PR body contains every required provenance, evidence, review, and human-control field plus machine marker | unit + golden | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_domain.py -x` | ❌ W0 | ⬜ pending |
| PUB-03 | T-04-04 | Production adapter exposes no merge, review submission/approve, ready, auto-merge, ruleset, default-ref, arbitrary-repository, or arbitrary-ref operation; bounded completed-review GET is read-only | static AST + negative transport | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_security.py -x` | ❌ W0 | ⬜ pending |
| PUB-04 | T-04-05, T-04-06 | Exact `verify-publication-admission --compare-env` precedes token; same-identity live canary denies default write, merge, ruleset/admin, unauthorized resource, and secret access, while isolated transport/static evidence proves production cannot approve or ready a Draft | workflow static + opt-in live integration | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_live_canary.py tests/test_publication_security.py -x` | ❌ W0 | ⬜ pending |
| PUB-05 | T-04-07, T-04-08 | Stable publication identity accepts verified later revision lineage; same slug reuses one Draft PR, deletes stale owned files, recovers after local-state loss, and does not re-notify users or teams with current/completed/timeline receipts | crash/recovery matrix | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_recovery.py -x` | ❌ W0 | ⬜ pending |
| SEC-02 | T-04-09, T-04-10 | Minimal workflow permissions, protected environment, pinned action SHA, safe logging, and zero candidate-to-shell interpolation | workflow parser + AST/security | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_publication_security.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Required Test Matrices

1. **Admission/identity:** every mutation of canonical bytes, digest, path, mode, size, validation report, review verdict, confidence, or terminal eligibility fails before token or network access; stable identity accepts a verified later revision but rejects malformed, spoofed, cross-catalog, or inconsistent machine lineage.
2. **Provider responses:** success plus redirect, 401, 403, 404, 409, 422, 429, 5xx, oversized body, malformed JSON, wrong content type, missing request ID, pagination, unknown fields, and `truncated=true` tree.
3. **Crash points:** after blob/tree/commit, ref create/update, PR create/update, reviewer request, remote verification, and remote success before local checkpoint.
4. **Remote recovery/ambiguity:** complete owned-subtree enumeration and null-SHA stale deletion; duplicate PRs, non-Draft PR, wrong head/base, malformed/cross-catalog marker, inconsistent lineage, human commit, force-updated ref, deleted/reopened/closed PR, changed default branch, local-state loss, current requests, completed user reviews, fulfilled/removed team requests, assignment-expanded team requests, and ambiguous timeline evidence.
5. **Forbidden routes:** reject `PUT`, `DELETE`, GraphQL, `/merge`, review-submission/approval POST, `/update-branch`, `/rulesets`, default-branch refs, arbitrary refs, and arbitrary repositories; allow only the bounded read-only completed-review history needed for notification recovery.
6. **Workflow handoff:** exercise project-owned `PublicationEvidenceLocatorV1`, `verify_publication_admission_handoff`, canonical ten-field JSON, exact `verify-publication-admission --compare-env` command, and every locator/artifact/field/digest substitution; failure prevents token action and publication network.
7. **Capability proof:** live canary proves the positive machine-branch/Draft/reviewer path and causal negative default-ref/merge/ruleset/unauthorized-resource/secret-resource probes with the same installation identity and unchanged state. Isolated negative transport/static tests prove production has no approval submission or ready/GraphQL transition. Record residual coarse-token ready capability and require separate-authority cleanup.

---

## Wave 0 Requirements

- [ ] `tests/fixtures/github_publish/` — bounded Git object, ref, pull, reviewer, pagination, conflict, and rate-limit fixtures.
- [ ] `tests/test_publication_domain.py` — admission, identity, marker, PR-body, transition, and publication-record contracts.
- [ ] `tests/test_github_publish_adapter.py` — exact repository/method/path/body allowlist and response parsing.
- [ ] `tests/test_publication_recovery.py` — crash and remote-reconstruction matrix.
- [ ] `tests/test_publication_security.py` — AST/import/route/workflow/logging forbidden-surface checks.
- [ ] `tests/test_publication_live_canary.py` — opt-in environment contract; skipped unless explicit protected canary variables exist.
- [ ] Exact approved GitHub App-token action SHA and supply-chain evidence.
- [ ] Independent catalog ruleset evidence and human/admin canary cleanup procedure.

---

## Revised Task Command Anchors

| Task | Required automated command |
|---|---|
| `04-06-02` | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_cli_validate_skill.py -k 'publish or admission_handoff'` |
| `04-06-03` | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_cli_security.py tests/test_publication_security.py tests/test_cli_validate_skill.py -x` |
| `04-07-01` | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py` |
| `04-07-02` | `.tools/uv-0.11.29/bin/uv run --locked pytest -q tests/test_phase4_action_audit.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py` |
| `04-11-03` | `.tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_validation_map.py && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_action_audit.py && .tools/uv-0.11.29/bin/uv run --locked ruff check . && .tools/uv-0.11.29/bin/uv run --locked pytest -q && .tools/uv-0.11.29/bin/uv run --locked python tools/verify_phase4_acceptance.py` |

The locked project does not include mypy, so Phase 4 makes no mypy gate claim.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GitHub App action identity and exact SHA approval | SEC-02 | Third-party executable supply-chain identity cannot auto-approve itself | Review source, release provenance, permissions, exact full SHA, and resolved workflow diff before enabling the publishing job. |
| Catalog ruleset and installation-permission canary | PUB-04 | Repository rules and installation permissions are external control-plane state | In the protected environment, run positive Draft flow and negative default-push/merge/ruleset probes; a human reviews evidence and performs cleanup with separate authority. |
| Reviewer/team configuration | PUB-01 | Catalog governance decides the authorized human review destination | Confirm configured reviewer/team exists, is authorized, and current/completed/timeline evidence preserves user and team notification receipts after local-state loss. |
| Approve/ready production boundary | PUB-03 | GitHub Pull requests write is coarse and may retain out-of-process ready capability | Review isolated route/transport/CLI/workflow absence evidence and explicitly acknowledge the residual token risk; do not record it as platform denial. |

---

## Validation Sign-Off

- [ ] Every planned task has an automated verification command or explicit blocking human checkpoint.
- [ ] All six Phase 4 requirement IDs map to plan tasks and validation evidence.
- [ ] Sampling continuity has no three consecutive implementation tasks without automated verification.
- [ ] Wave 0 covers every missing fixture and test file.
- [ ] No watch-mode flags or implicit live-network dependency.
- [ ] Offline feedback latency stays under 60 seconds.
- [ ] Live canary evidence proves platform-enforceable negative capabilities using the production installation identity; approve/ready are proven absent from the production surface with residual token risk recorded.
- [ ] `nyquist_compliant: true` is set only after execution verification.

**Approval:** pending
