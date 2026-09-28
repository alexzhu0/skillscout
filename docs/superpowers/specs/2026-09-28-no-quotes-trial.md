# Local no-quotes regression

User approved the September28 proposal to omit optional quotations while keeping
provenance and all checks. This is a bounded prompt experiment, not a relaxation
of schemas or a repair of a failed model response.

New local profile/prompt v2 reuse the existing explicit CLI flag; historical v1
pairs retain their original prompt and are still recognized. Default/hosted
prompts, source contracts, quote limits, copying detection, independent Reviewer,
single-attempt limits and publication denial stay unchanged. The v2 instruction
asks for `quotes=[]`; generated content is never edited after receipt.

Trial `no-quotes-20260928` reuses the immutable Fabric source/Phase2 descriptor
from the prior report, with new SQLite state and a new reservation. Maximum calls:
generation1, review1, comparison9 (comparison only after all checks pass). Same
Flash generator and configured Pro alias Reviewer in independent contexts.
Unknown/rejected outcome stops the trial; no automatic retry or prompt tuning.

Budget: known cumulative estimate CNY0.265724 plus unresolved September25 CNY20
reserve plus fresh CNY20 reserve = CNY40.265724, below100. Only the reviewed
runtime loader reads the authorized `DEEPSEEK_API_KEY`; no new credential path.

Verification so far:49 focused tests pass, Ruff passes, v1 serialized prompt hash
is unchanged (`ef6e21be1bac806f8de8ad46d638be65b6020018b4bd4567f48b009f4a1c3ab5`).
Independent code review found no blocker. Full offline suite: **3056 passed,
3 skipped in1067.23 seconds**. The skips remain the existing Phase6 requirement
map and two unconfigured protected live canaries. The additional legacy
attempt-bound assertions passed in the49-test focused rerun. Private fresh-trial
reservation/no-retry check passed; Ruff and whitespace checks passed. Prior
source and failed-trial databases retained their recorded SHA256 values.
No accepted package or usefulness result is claimed.

## Real outcome — trial closed at validation

The one real generation call completed and passed JSON/schema parsing. Requested
and returned model were `deepseek-flash`, request ID
`151e0eea-73b9-4f1b-b034-92f9dc1e2ea6`, latency3745ms. Usage was5,348 input plus545
output tokens (5,893 total): estimated CNY0.015056 using peak uncached input2/output8
per million, not a bill. Known cumulative estimate is CNY0.280780, with September25
actual charge still unknown and its reserve retained.

The resulting unedited package has `quotes=[]`, correct source repository/commit
and MIT attribution. It is a **rejected diagnostic package**, not an accepted or
installable release. Package digest:
`sha256:a4f4380d02396bae7222b2dc06890f266ea2f887d7cff1539783cbad3ad41188`.
Local path:
`.tmp/no-quotes-20260928/runtime/output/content-summarization-pattern-eb4e5a36/`.

Official validation infrastructure succeeded; no official-format finding was
reported. Overall validation failed with exactly one error:
`overcopy_unregistered_source_match` in `SKILL.md`. Static comparison against
the frozen source evidence found normalized matching runs of101 and85 characters
in the main-points and takeaways instructions, exceeding the existing80-character
unregistered-match threshold. No automatic rewrite or threshold relaxation occurred.

Terminal: `validation_rejected`, `eligible=false`,
`review_skipped_validation_errors`. Actual model calls: generation1, Reviewer0,
comparison0. All remaining slots are closed. No nine-call comparison or value
claim can be made. The narrower hypothesis only reached its intermediate goal:
the model omitted quotes and produced a structurally parseable draft; it did not
solve faithful paraphrasing under the existing copying policy.

Next hypothesis, not executed here: explicitly require independently worded
instructions rather than copying WorkflowSpec instruction strings, retaining
exact list counts/section names and the unchanged copying check. Do not edit this
failed package, reuse its reservation, or label a later attempt as this trial.

Minor deferred review suggestion: duplicate legacy adapter and publication-path
tests in addition to retained prompt hash, explicit version-pair/attempt tests,
and existing current-profile integration checks. No validation boundary removed.

Independent post-run inspection confirmed the recorded stop and found no invented
obligations against the bound WorkflowSpec. It also confirmed that procedure prose
largely reuses WorkflowSpec wording; this is preliminary agent fidelity review,
not the skipped semantic Reviewer or a usefulness score.

## Local evidence SHA256

All paths below are relative to `.tmp/no-quotes-20260928/`.

| Evidence | SHA256 |
| --- | --- |
| config.json | `a35d647a79ed0862e0293e703f868aab8061af07148b1dae5b952d086989835f` |
| run-once.py | `fdb42d19ff59e84d6e88cd83558d30c80f83e43b0a4f225b6a0bd69a10d01aaf` |
| observer.py | `10cc34edd22e2250870bea12b3748e7da45847f15a80d09beaee06cc81278114` |
| runtime/frozen-manifest.json | `d8a3de997f4e9bc7a04b3775dc069b5d64b19c7064de6fcf1f534b335e99e7fc` |
| runtime/provider-event-1.json | `b7931f4522f9302a46387a8eca59ffe447487461065eda5a6631d146f168a137` |
| runtime/output/candidate-terminal-summary.json | `77821a8951379c716dd8fe64b380ad6816ca14d60f1fa6f41e31722bec736446` |
| runtime/output/validation-report.json | `9c519c0cc0e896a08ede6739977f1bd5876b149bdce692bcd728b4d6d819c8dd` |
| runtime/output/content-summarization-pattern-eb4e5a36/SKILL.md | `4fb8ba4f00c66791bc932bee2315189528fc0d65576b431a40483be7d8f2eb86` |
