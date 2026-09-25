# September 25 diagnostic real trial — provider outcome unknown

## Decision

The single authorized generation attempt ended without a terminal model result.
SkillScout recorded the generation attempt as `attempt_interrupted`; there is no
terminal summary, `generation-diagnostic.json`, request ID, or token telemetry.
It is therefore unknown whether the request reached DeepSeek or incurred a
charge. The reserved CNY20 is a safety limit, not an invoice or a spend estimate.
The request slot is consumed. Do not retry this trial.

No Skill package was produced. The Reviewer, validators, usefulness comparisons,
and publishing were not reached. This is neither a successful extraction nor a
validated/useful Skill, and it does not establish Phase 6 acceptance.

## Frozen inputs and limits

- Trial: `source-faithful-diagnostic-20260925`.
- Implementation: `cb919b8e4456046794f8ba3ef1118bc5bd9c5aa1`.
- Source: `danielmiessler/fabric`, commit
  `b682dad740f24e85ce9a48d23babc6780dd476ac`,
  `data/patterns/summarize/system.md`, MIT.
- Source content SHA-256:
  `29d393bf16f9a89464ef1f734cfd523e5949c01e5e580039540fd65823bc4a06`.
- Candidate SHA-256:
  `87a59998718012085be9f23e4b7e64a5fed86fd6d6b15975fc6339e52aef91db`.
- Generator: `deepseek-flash`; maximum one generation request, no retries.
- Reviewer was conditional and was not called. Comparisons were not authorized
  for this invocation. Remote writes and manual semantic repairs were disabled.
- CNY20 was reserved; known cumulative estimate before this attempt was
  CNY0.247996. Actual total after the attempt is unknown.

The official [DeepSeek model and pricing documentation](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)
states that, from September 14, 2026, requests named `deepseek-v4-pro` route to
V4.1-Flash until a new Pro model is available. Thus even if the conditional
Reviewer stage had run, that alias would not provide independent cross-model
evidence for this trial.

## Durable evidence

| Artifact | SHA-256 |
| --- | --- |
| `config.json` | `531601cb54fd0c264011efb561080d810aede474398f07b130eb38772a70d2e6` |
| `run-once.py` | `15669c9fff51760ce3fa3db3e5ecb77a1a77c8f6d79a7812747e1ed005d5c1ac` |
| `runtime/frozen-manifest.json` | `d204d5ca3429bd0bffdaee71bf19f34a2206e825757d43825c48ce0e1a2a09be` |
| `runtime/started.json` | `a07dc0d34e2ae8ceabb46c726160f415d33b77a116b691b9705b7fc96f2cdedb` |
| `runtime/invocation-result.json` | `834aaf9d0061843c409a4bedcf52b0912b56503f7eb9f6d6c13dbe802c9e8e92` |
| `runtime/phase3.db` | `19ce61b1263cf2565fdde09f9aaca18f3ded1700f069936cd18ef99df342c3ba` |

The invocation wrapper reported child exit code 1. The durable state contains a
qualifier pass and one interrupted generation attempt, but no completed
generation result. Because no terminal rejection reached the new diagnostic
classifier, the missing sidecar is expected and must not be interpreted as a
successful build. The old September 20 trial's database and terminal-summary
hashes were rechecked and remain unchanged.

## Follow-up

Offline recovery review found a separate retry-boundary defect: without a remote
durability guard, Phase 3 resume skipped the latest `attempt_interrupted` record
and could issue another generator or Reviewer request under a multi-attempt
profile. A crash after persisting the “running” attempt marker is equally
ambiguous, even if the process stopped before the client call. Phase 3 now
quarantines either condition unconditionally; confirmed transient failures keep
their existing retry behavior. The September 25 trial itself was already bound
to one generation attempt, so this change did not retroactively alter that run.

Regression tests reproduced a second generator request and a second Reviewer
request before the fix. After the fix, the focused Phase 3, CLI and acceptance
suite passed **194 tests**; full offline verification passed **3053 tests with 3
skips** in 1149.49s, and whole-repository Ruff passed. No model request was made
for this diagnosis or correction.

Any further live trial requires its own frozen inputs and fresh request
reservation; it must not reuse this consumed slot. Do not tune prompts or claim
that the new diagnostic was exercised until a completed, classified rejection
produces a sidecar.
