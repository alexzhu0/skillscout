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
Independent code review found no blocker. Full offline suite is in progress.
No successful package or usefulness result is claimed at this preparation point.

Minor deferred review suggestion: duplicate legacy adapter and publication-path
tests in addition to retained prompt hash, explicit version-pair/attempt tests,
and existing current-profile integration checks. No validation boundary removed.
