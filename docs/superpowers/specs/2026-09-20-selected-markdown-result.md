# Selected Markdown preview and source screening — 2026-09-20

## Status

The local preview can select one ordinary Markdown file at an immutable GitHub
commit using `--markdown-path`, with both `--evidence-selection` and
`--source-only-fields`. Commit `7c0c446` contains the bounded extension and tests.
The existing v4 prompt, evidence catalogue, source validation, qualification,
generation, security and publication boundaries are unchanged. This input-format
extension is not evidence of a useful Skill or completed Phase 6 acceptance.

Controller verification so far: 115 product-focused tests and 29 private launcher
tests passed; full Ruff and whitespace checks passed. Independent task and final
integration review found no blocking issue; one minor private-launcher path
validation mismatch was fixed and independently re-reviewed. The frozen full-suite
result is pending.

## Source screening before model use

The first repository was public MIT `microsoft/prompts-for-edu`, pinned to
`508567d4008b17dc1df98cbb89f88708c250f666`, with license blob
`9e841e7a26e4eb057b24511e7b92d42b257a80e5`.

| Selected path | Content SHA-256 | Result under unchanged catalogue |
| --- | --- | --- |
| `Administration/Prompts/Meeting Summary.MD` | `2b6e19285ec2aeff27c5c7ac506df97d6093bea3285d739a95d02979d08d787c` | Fenced normative prompt excluded; retained example loses mandatory summary length and heading constraints. |
| `Students/Prompts/Team Pre-mortem Coach.MD` | `ed04e2d2af1020a007c436f675647b9f7848da3b2cc3f3748d8768e5c172a8bb` | Fenced procedure/output contract excluded; original also requires outside research. |
| `Students/Prompts/Team Reflection Coach.MD` | `d92f88ff573a50edf5caf06bb544bfe94649be86f4cbce09830d6a6d89d100e8` | Fenced adaptive procedure excluded; retained synopsis cannot support its interaction rules. |

All three were excluded before any model request. An untruncated catalogue means
the retained entries fit the limit, not that every essential source fact survived
filtering. No fence or safety rule was relaxed to make a source eligible.

The second repository selected for bounded screening was `danielmiessler/fabric`,
only `data/patterns/summarize/system.md` (the historical
`patterns/summarize/system.md` only if the current path is absent). Two bounded
metadata attempts failed before any source content was obtained. A credential-free
connectivity check established GitHub anonymous API exhaustion: HTTP403,
remaining0, reset `2026-09-20T07:13:47Z`. A post-reset metadata attempt also failed.
No GitHub credential was accessed, and no web-page substitute was admitted as
source provenance. The three failed metadata attempts are preserved in the
private screen report. A third repository has not been screened.

At `07:15:18Z`, a credential-free header diagnostic confirmed actual recovery
(HTTP200, remaining58). One subsequent bounded adapter pass succeeded using five
reads. The source is public MIT, with no privileged action, execution, installation
or external research in the selected workflow. Its exact source identity and fixed
attempt order are frozen in
[`local-markdown-20260920.json`](../../../config/previews/local-markdown-20260920.json).
The sole eligible source meets all three ranking criteria (complete input/steps/
output, explicit constraints, standalone use); no model result influenced selection.

Fabric commit: `b682dad740f24e85ce9a48d23babc6780dd476ac`; selected blob:
`b655b620b895c71593ea578fb4ea5e975cfdd3a0`; license blob:
`fb06a6f8c497f15063059ff224965d9e60e98a01`; content SHA-256:
`29d393bf16f9a89464ef1f734cfd523e5949c01e5e580039540fd65823bc4a06`.
The unchanged catalogue retains all nonblank characters in 16 untruncated entries.
The contract specifies a 20-word summary, ten main points of at most 16 words each,
five takeaways, and numbered Markdown lists without notes, duplicate items or
repeated item openings. No author is inferred from the repository owner.

## Request and authority accounting

No new campaign was initialized and no new model call was made at this pre-call checkpoint.
The private launcher reserves one extraction slot durably before loading the
runtime credential or starting the real CLI, with no unknown-outcome replay.
Its new configuration must first freeze the eligible source, model and committed
code. The sole eligible source above is admitted for exactly one fresh extraction;
the configuration reserves CNY20 conservatively, without borrowing prior budgets.

Known historical model-cost estimate remains CNY0.196462, not a billing statement.
The cumulative ceiling is CNY100. Prior failed campaigns remain closed and their
budgets cannot be reused. New generation/review/comparison calls remain contingent
on actual extraction fidelity and deterministic qualification, not CLI exit status.

One later integration concern is explicitly recorded: the ordinary
`build-candidate` runtime profile permits up to three application-level generation
and review attempts. Before a real pilot build, it must be constrained to the
pilot's one-request-per-stage ceiling through a reviewed minimal implementation;
SDK retries being disabled does not establish that application-level bound.

No push, PR, merge, remote state mutation, Skill publication, source-code execution
or human repair of generated semantic data occurred.
