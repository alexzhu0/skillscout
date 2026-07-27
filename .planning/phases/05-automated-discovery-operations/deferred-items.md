# Deferred Items

## 05-06

- The historical Phase 1/3 acceptance scanners currently pin the exact pre-Phase-5
  set of production `httpx` importers. The planned
  `src/skillscout/adapters/state_branch.py` import therefore causes three full-suite
  scanner failures while all 1,562 other tests pass. Updating those independent
  acceptance baselines is outside Plan 05-06 ownership and belongs to the Phase 5
  acceptance/map work; do not weaken the old scanners as part of the state adapter.
