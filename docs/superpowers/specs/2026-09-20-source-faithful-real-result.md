# Source-faithful real generation regression — closed failure

Date: 2026-09-20. Trial: `source-faithful-real-20260920`.

## Decision

One real `deepseek-flash` request completed, but its result was rejected as
`schema_invalid`; the terminal is `generator_schema_failure`, `eligible=false`.
**No Skill package was produced.** Official format/local package validation, Pro
review and all nine usefulness comparisons were not reached. The trial is closed
without retry, semantic repair, prompt change or publication.

This is a freshly budgeted regression on a previously known source, independently
reviewed before and after the call. It is not a fresh extraction, unseen-source
evaluation, proof of useful output, or Phase 6 acceptance.

## Frozen source and implementation

- Repository: `danielmiessler/fabric`; MIT license.
- Commit: `b682dad740f24e85ce9a48d23babc6780dd476ac`.
- Document: `data/patterns/summarize/system.md`.
- Source SHA-256: `29d393bf16f9a89464ef1f734cfd523e5949c01e5e580039540fd65823bc4a06`.
- Immutable extraction run: `686a3ed1ed3b4c399ce66b0f13f4d18f`.
- Phase 2 state SHA-256: `f9289010b41e7ff1370afdb69a37211b2d11221fcba84130b2cf7255f3bdf932`.
- Original descriptor SHA-256: `87a59998718012085be9f23e4b7e64a5fed86fd6d6b15975fc6339e52aef91db`.
- Implementation: `291f74638f0a825f5b96e055c9b47b845500128c`.
- Frozen checkout: `1ff3aff750f301451297b005e70b6541af3f5bd3`; only documentation/configuration differ from the implementation.
- Profile/prompt: `phase3-local-source-faithful-v1` / `generator-local-source-faithful-v1`.

Independent input review re-admitted the original descriptor, verified all 16
source excerpts and 11 step references, and confirmed qualification 85/100 with no
hard failure. Empty approval/failure fields accurately reflect the source. The old
extraction, descriptor, failed package and historical trial remain intact.

## Real execution and accounting

The independently reviewed launcher reserved one-shot authority durably before
loading the already authorized runtime key. It invoked the real CLI with the
unchanged descriptor, fresh Phase 3 state/output, and all three explicit options:
`--deepseek-current-flash --single-attempt --source-faithful-generation`.
The official endpoint and zero SDK retries were retained. No credential or raw
rejected response was displayed or persisted.

Run: `phase3-2b956b2ccf674947ac74741a055e4d8d`.
Request: `37dd1804-29d2-40b3-8fe8-bdc9e73343cf`.
Configured and returned model: `deepseek-flash`. Recorded latency: 4,093 ms.
The database contains one qualifier attempt (`accepted`) and one generator
attempt (`schema_invalid`), and no validator or reviewer attempt.

| Stage | Real requests / frozen cap | Input tokens | Output tokens | Estimated CNY |
| --- | ---: | ---: | ---: | ---: |
| Extraction | 0 / 0 | 0 | 0 | 0 |
| Generation | 1 / 1 | 5,316 | 881 | 0.017680 |
| Pro review | 0 / 1 | 0 | 0 | 0 |
| A/B/C comparison | 0 / 9 | 0 | 0 | 0 |
| Total | 1 / 11 | 5,316 | 881 | 0.017680 |

Total tokens: 6,197. The conservative estimate uses peak uncached Flash rates of
CNY2/million input and CNY8/million output, checked against
[DeepSeek pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/).
Known prior estimate CNY0.230316 plus this trial gives **CNY0.247996** cumulative.
These are token-derived estimates, not provider bills; Codex work and human time
are not included. The CNY20 reservation was a ceiling, not actual spend. All unused
slots are closed, not transferable to another source, retry or campaign.

CLI exit0 and database `completed` mean the terminal outcome was recorded, not
that generation or acceptance succeeded. The stage ledger's `succeeded` label
likewise describes a recorded attempt; its `outcome_code` is `schema_invalid`.

## Known facts and diagnostic limit

Confirmed: the provider returned the exact configured model with request/token
telemetry; generation was rejected before rendering, validation or review.
The recorded outcome is not authentication failure, model-identity mismatch,
timeout or `incomplete`. The source remained qualified and unmodified.

The closed `schema_invalid` result does not retain model text or a field-level
diagnostic. Independent code inspection confirms four possible branches:
unexpected choice count, absent content, JSON/Pydantic validation failure, or the
local source-absent approval/failure sentinel check. Retained evidence cannot
distinguish them. It does **not** establish that the model again invented approvals,
which field was malformed, or whether the semantic content was faithful.

No package exists for fidelity inspection and no Pro judgment exists. The new
reference rendering and copying behavior were not exercised by this real response.
The known source is exposed to development; even success would not establish
generalization. There are no A/B/C scores or usefulness conclusions.

Next diagnostic hypothesis, not implemented here: the undifferentiated rejection
hides the failing boundary. Before another prompt/policy change, test minimal
content-free classification offline: fixed reason codes and allowlisted schema
field/error categories only, never rejected values, raw text, credentials or
exceptions. Reproduce the rejection branches with synthetic responses first.
Any later real call must be a fresh bounded experiment, not a rerun of this one.

## Verification and preserved artifacts

- Independent source review: GO for immutable inputs only.
- Independent launcher review: GO for the exact one-shot scope, no blocking findings.
- Independent post-run review: confirmed failed terminal, request accounting,
  unchanged inputs, no package/Pro/comparisons, and the diagnostic limit above.
- Fresh controller product regression: 329 passed in 9.59s; independent input review: 131 passed in 6.45s.
- Fresh private-launcher tests: 13 passed in 1.93s; Ruff check and format check clean.
- An initial static-check invocation hit the default uv cache permission boundary;
  both checks passed using the writable local cache. This was not a model retry.
- Prior full offline suite on unchanged code: 3,033 passed, 3 skipped in 1,163.93s.
  That historical full run was not repeated or represented as a new run.
- Six historical failure-artifact checksums matched before and after the call.
- No production source, dependency, schema or policy change in this trial.
- No push, PR, merge, remote state write, source-code execution or publication.

Raw evidence is local and ignored under `.tmp/source-faithful-real-20260920/runtime/`,
relative to this worktree.

| File | Raw file SHA-256 |
| --- | --- |
| `frozen-manifest.json` | `e75b54df3b1f691fa514547790f4a4b70b4751f819b95f0639794945f1f9fef4` |
| `started.json` | `73e24b431e409876759ab9642c588b765f789de4d536a1e2934e89de0e90b3ca` |
| `invocation-result.json` | `06dfd7923146b332608598f5fec0539e11761f5e56e7b1a6208bd4c5f0596eac` |
| `phase3.db` | `02dc3b6381d28e2a3263f2cb68760b9ee668ba0f4fc6c53d3ca475e13616f24c` |
| `output/candidate-terminal-summary.json` | `05c6cd0cf41bf6ad4969debeecac24c8797b4b3a4b5fdcaf3838aa46771876cb` |

The terminal's internal canonical digest is separately
`sha256:80573802757779943b59f93c6cd93eb8d75a013254ecaa07972547534a479861`;
it is not the raw file hash. Generator telemetry is preserved as
`phase3.phase3-artifacts/245987a2834ae195ba73651f333c47dcc821e7ce9cc7f7fdba43304c2394b730.json`.

Read the terminal summary and generator evidence to inspect the outcome. Do not
rerun the consumed launcher. General extraction/export/build instructions remain
in [Getting Started](../../GETTING-STARTED.md#local-extract-build-and-inspect-flow);
a new build is a new paid experiment, not read-only inspection.
