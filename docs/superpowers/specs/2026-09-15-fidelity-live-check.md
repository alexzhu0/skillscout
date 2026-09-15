# Fidelity repair: bounded live comparison

User requested a new live test and delegated task-related model spending below
CNY100 without repeated approval. This run is narrower: **12 requests maximum**,
no retries, fixed r1 versus r2 on three existing development regressions and
three newly curated source-only cases. It grants no publication/merge authority.

Frozen before curating new sources:
- Source commit: `6034cff`.
- r1 prompt: `sha256:14f240c426adebf6116d8811a591a71e49e59bf023efd59bfb72c4ab5e0098cb`.
- r2 prompt: `sha256:1e96ca30edab9d9664ac738caedd4ad515d15c77bc888dbda00cf4c2b986a56b`.
- Model: `deepseek-flash`, same no-thinking/no-tools guarded JSON request,
  8,000 maximum output tokens, no SDK retries, 65,536-byte input boundary.
- Peak rates checked at https://api-docs.deepseek.com/zh-cn/quick_start/pricing/:
  CNY2/million uncached input tokens and CNY8/million output tokens. Using a
  conservative 128,000 input-token allowance per bounded request yields
  CNY3.84 for all12. Stop if billing metadata contradicts this conservative bound.

Named campaign: `fidelity-check-20260915`; private files under
`.tmp/fidelity-check-20260915/`. Create a fresh exclusive counter with exactly
12 admitted slots and fixed prompt/input identities, reusing the existing
reservation/request/materialization functions. Never initialize, change, delete
or consume any slot of `useful-skill-loop-20260914`.

Run order: existing three regressions in file order, r1 then r2 per case;
then fresh h01..h03, r1 then r2 per case. Freeze every source byte/hash before
the first request. No labels/checklists in requests, no tuning/reselection.
The runtime program may select only DEEPSEEK_API_KEY from the previously named
root .env; never expose/store it or read other credential sources.

Score all authored fields against source/checklist: evidence roles and allowed
scope, asserted versus confirmed facts, supported steps/outputs/assumptions,
no invented authority or unsafe/demo steps. Candidate must pass all six cases;
report r1 alongside it, without requiring r1 to fail. An independent scorer
and controller inspect ambiguous cases. Exact excerpts/qualification are
separate checks, not proof of semantic fidelity. Synthetic labels are not human
gold. A pass only supports this repair on a small sample, not useful-Skill or
production readiness.

Stop immediately on unknown outcome or transport/schema failure; otherwise
finish the fixed comparison and stop after scoring. No artifact generation,
new campaign, tuning or extra spending follows automatically from this plan.

## Inputs frozen before dispatch

- Existing three: `sha256:b5553a22323c918c824f5f75aebbd405a7850d33ac868877c4181ea991a26778`.
- Independently curated fresh three: `sha256:f3a9b95038e48c6a1a26675f87bcf184e964a708e9400147ffbee85f5dff6999`.
- Private launcher checks plus shared runner tests: 57 passed; independent
  bounded safety review found no blocker. No live request had occurred at freeze.
