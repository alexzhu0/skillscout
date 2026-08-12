# Deferred Items

- 2026-07-19, Plan 01-09: an optional repository-wide `ruff format --check` reported pre-existing formatting drift in `src/skillscout/adapters/localfs.py`, `src/skillscout/application/pipeline.py`, `src/skillscout/application/ports.py`, `src/skillscout/domain/enums.py`, `tests/test_cli_dry_run.py`, `tests/test_side_effect_policy.py`, and `tests/test_stage_contracts.py`. Ruff lint passes, these files are outside Plan 01-09, and they were intentionally left untouched.
