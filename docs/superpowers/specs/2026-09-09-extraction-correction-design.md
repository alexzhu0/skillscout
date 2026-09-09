# Bounded extraction correction design

Base: `3dc3c1013d77dc5d4f7c12dbd49f5de245c93d18` (PR #38 merged).
Scope: the previously approved single correction opportunity for DeepSeek Flash.
This document does not authorize a live model request or release campaign.

## Purpose and success

Give an extraction response one opportunity to repair a locally detected format
or verbatim-evidence error. Preserve the safety validator, durable request
accounting, original failed-attempt telemetry, and terminal failure reporting.
The result is useful only if it later improves valid extraction on real inputs;
offline tests establish bounded behavior, not that improvement.

## Approach

Use the existing application-owned attempt loop and durability barrier. Do not
retry inside the provider adapter: one adapter invocation remains one HTTP
request. Do not introduce a new service, workflow, database, or parallel agent.

The alternatives were an adapter-internal retry (rejected because it hides a
billed request from the ledger) and evidence-ID extraction (potentially valuable,
but a different extraction contract and outside this repair).

This is a change to attempt semantics, not just prompt wording. Implementation
must preserve distinct transport failure, locally correctable output, unknown
completion, and final business outcomes even if some share an existing status.

## Correction eligibility

The policy applies only to the explicit DeepSeek extraction profile. OpenAI,
generation, and independent review behavior remain unchanged.

One correction can be scheduled only after a response with complete, validated
request telemetry, when no usable workflow survived, and either:

- strict JSON/schema decoding failed; or
- the result is `all_workflows_dropped` and at least one dropped workflow has
  only the `excerpt_not_verbatim` boundary reason.

A mixed response may include other rejected workflows. Their rejection grants
no permission to repair or admit them. The correction receives the original
bounded source input and a fixed format/evidence reminder; every newly proposed
workflow must independently pass all existing checks.

Never correct a legitimate `no_workflow`, a refusal, truncated/incomplete output,
unknown provider completion, invalid telemetry/model identity, or a response
whose workflows were all rejected only for other reasons such as forbidden
text, invented paths, or mismatched blob SHAs. Do not regenerate a partially
successful extraction just to recover additional rejected workflows.

## Request limits

- At most one correction HTTP request for a repository extraction identity.
- The correction consumes an existing attempt slot: the current three-attempt
  extraction ceiling and twenty-request campaign ceiling do not increase.
- Confirmed transport rejections before the correction retain the existing
  policy. If they consume the budget, no correction is available.
- After a correction is dispatched, do not retry it, including on a confirmed
  transport rejection. Record its appropriate terminal outcome.
- A successful business result and any exhausted/unknown terminal are immutable
  for that identity. Reinvocation must not create another model request.

For example, invalid output followed by a valid correction uses two requests.
A confirmed transport rejection, then invalid output, then its correction uses
three. Invalid output on attempt three terminates without a fourth request.

## Durable data and recovery

Keep each provider response's request ID, actual model, usage, latency, prompt
version, and policy version in its own attempt record. The first response must
not disappear into a combined telemetry total.

Use distinct closed failure codes to distinguish JSON/schema correction from
verbatim-evidence correction. These codes are application decisions, not
provider transport dispositions. Persist the first failed attempt, telemetry,
and correction eligibility before making the next reservation.

For correction scheduling, an existing `confirmed_retryable` operations status
may be reused only when the
corresponding verified pipeline attempt carries an explicit code owned by the
new correction policy. The retry decision must revalidate that code, policy
identity, remaining budget, and absence of a previously dispatched correction.
Never allow another request after an arbitrary `decided` predecessor.

The second attempt must have a durable request reservation and a known
correction prompt identity before crossing the provider boundary. A process
crash after starting the request is outcome-unknown and does not authorize
redispatch. A crash after the response was durably recorded can recover that
result without a call. A crash before dispatch may continue only from a verified
reservation that has not reached the started boundary.

The final stage envelope refers to the final accepted or failed result. Earlier
attempt records remain immutable and auditable. The coordinator must retain
telemetry for correction-eligible failed attempts as well as successful ones.

## Prompt and input boundary

Use a separately versioned, code-owned correction prompt. The only variable
feedback is one closed eligibility code; never promote rejected model text,
repository instructions, paths supplied by the model, or free-form diagnostics
into trusted messages.

Rehydrate the same bounded, pinned Reader input and verify its existing blob
identities. The correction still has no tools or execution permission. It must
produce the same strict response schema and pass the same source, excerpt,
forbidden-content, and workflow-count checks. Final rejection remains
`schema_exhausted` when those checks fail again.

## Versioning and authority

Give the correction policy and correction prompt new explicit versions. Bind
the enabled policy into the extraction reuse identity so a result produced with
the old one-response policy is not silently reinterpreted or reopened. Preserve
readability of historical records; do not rewrite their facts.

The implementation must audit the pipeline and operations verifiers together,
including their predecessor and telemetry rules. No database table migration is
planned; if existing records cannot express the distinction without losing
meaning, revise this design before introducing a new schema.

There is no operator flag to increase limits or bypass eligibility. Protected
execution still requires authority bound to the reviewed source and policy.

## Required offline verification

Use real production composition with recorded transports and synthetic inputs:

1. Schema-invalid output then valid correction: two independently recorded
   requests, one accepted final workflow set, preserved first-attempt usage.
2. Non-verbatim evidence then valid correction: unchanged validator admits only
   evidence actually present in the original pinned input.
3. Two invalid responses: terminal `schema_exhausted`, no third request.
4. Unsafe-only, legitimate negative, partial success, refusal, incomplete,
   unknown, or invalid telemetry: no correction request.
5. Prior transport retries consume their original slots; no fourth request.
6. A correction transport rejection is final, not another correction attempt.
7. Exhausted campaign budget prevents dispatch even when correction is eligible.
8. Crash at reservation, started, response persistence, and terminal boundaries:
   preserve the existing fail-closed recovery and no-duplicate guarantees.
9. Repeated invocation, tampered eligibility, stale policy, and a fabricated
   `decided` predecessor cannot obtain a correction request.
10. OpenAI and generation/review profiles retain their existing behavior.

Focused failures must be observed before implementation (TDD). A final audit
must inspect both request contents and durable facts, not only call counts.

## Handoff to product validation

After implementation and review, prepare one bounded real extraction from the
already selected repositories under fresh applicable authority. Review its
generated Skill and compare controlled task outcomes with task-only and
README-only baselines. Do not start another broad nomination or treat a passing
correction test as proof of a useful Skill.
