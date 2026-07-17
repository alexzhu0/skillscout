"""Packaged command-line boundary for the local-only dry-run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from skillscout.adapters.fixtures import FixtureProcessor, load_fixture
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.pipeline import STAGE_SEQUENCE, build_dry_run_runtime
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode, SafeFailure

__all__ = ["ERROR_SUMMARIES", "ErrorCode", "build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skillscout")
    commands = parser.add_subparsers(dest="command", required=True)
    dry_run = commands.add_parser("dry-run")
    dry_run.add_argument("--fixture", required=True, type=Path)
    dry_run.add_argument("--state", required=True, type=Path)
    dry_run.add_argument("--output", required=True, type=Path)
    dry_run.add_argument("--fail-after", choices=STAGE_SEQUENCE)
    inspect_run = commands.add_parser("inspect-run")
    inspect_run.add_argument("run_id")
    inspect_run.add_argument("--state", required=True, type=Path)
    inspect_run.add_argument("--format", choices=("json",), default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    state: SQLiteStateStore | None = None
    try:
        if arguments.command == "inspect-run":
            state = SQLiteStateStore(arguments.state)
            payload = state.inspect_run(arguments.run_id)
        else:
            subject = load_fixture(arguments.fixture)
            state = SQLiteStateStore(arguments.state)
            runtime = build_dry_run_runtime(state, FixtureProcessor())
            payload = runtime.runner.run(
                subject,
                arguments.output,
                fail_after=arguments.fail_after,
            ).as_dict()
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 0
    except SafeFailure as failure:
        print(
            json.dumps({"error": failure.as_dict()}, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 1
    except Exception:
        failure = SafeFailure(ErrorCode.STATE_OPERATION_FAILED)
        print(
            json.dumps({"error": failure.as_dict()}, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 1
    finally:
        if state is not None:
            state.close()


if __name__ == "__main__":
    raise SystemExit(main())
