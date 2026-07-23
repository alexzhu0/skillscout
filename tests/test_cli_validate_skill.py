"""Public argparse contract for the local-only Phase 3 candidate command."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skillscout import cli
from skillscout.application.ports import ERROR_SUMMARIES, ErrorCode


def _build_candidate_parser() -> argparse.ArgumentParser:
    parser = cli.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return subparsers.choices["build-candidate"]


def test_build_candidate_parser_exposes_only_the_closed_local_contract() -> None:
    parser = _build_candidate_parser()
    actions = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option != "--help"
    }

    assert isinstance(parser, cli.SafeArgumentParser)
    assert actions == {
        "--candidate",
        "--phase2-state",
        "--state",
        "--output",
        "--fail-after",
    }
    fail_after = next(
        action for action in parser._actions if "--fail-after" in action.option_strings
    )
    assert tuple(fail_after.choices or ()) == (
        "qualifier",
        "generator",
        "validator",
        "reviewer",
    )
    assert {
        action.dest
        for action in parser._actions
        if action.required
    } == {"candidate", "phase2_state", "state", "output"}


def test_candidate_source_failure_precedes_phase3_state_and_output(
    tmp_path: Path,
    capsys,
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(b'{"not":"a canonical candidate descriptor"}')
    candidate.chmod(0o600)
    state = tmp_path / "phase3.db"
    output = tmp_path / "output"

    status = cli.main(
        [
            "build-candidate",
            "--candidate",
            str(candidate),
            "--phase2-state",
            str(tmp_path / "missing-phase2.db"),
            "--state",
            str(state),
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()

    assert status == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE.value,
            "summary": ERROR_SUMMARIES[ErrorCode.CANDIDATE_SOURCE_UNAVAILABLE],
        }
    }
    assert not state.exists()
    assert not state.with_suffix(".phase3-artifacts").exists()
    assert not output.exists()
