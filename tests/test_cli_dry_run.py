"""Executable contract for the Phase 1 Walking Skeleton.

This module is deliberately created before Gate B and must not be executed until
the complete lock graph is approved. The happy-path test is the attributed RED;
the remaining named cases are collected now and activated by Plan 01-02.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import parse_cli_json


def test_approved_fixture_reaches_planned_not_published(
    approved_fixture: Path, run_cli, tmp_path: Path
) -> None:
    result = run_cli(
        "dry-run",
        "--fixture",
        str(approved_fixture),
        "--state",
        str(tmp_path / "state.db"),
        "--output",
        str(tmp_path / "output"),
    )
    assert result.returncode == 0, "dry-run CLI behavior is not implemented"
    payload = parse_cli_json(result)
    assert payload == {
        "run_id": payload["run_id"],
        "status": "planned_not_published",
        "last_stage": "publication_planner",
        "reused_stage_count": 0,
        "publication_plan_path": str(tmp_path / "output" / "publication-plan.json"),
        "remote_writes_attempted": 0,
    }


@pytest.mark.skip(reason="activated after the attributed happy-path RED")
def test_fixture_symlink_is_rejected_before_run_creation() -> None:
    """A symlink must never be followed or create durable state."""


@pytest.mark.skip(reason="activated after the attributed happy-path RED")
def test_non_regular_fixture_is_rejected_before_run_creation() -> None:
    """Directories, devices, sockets and FIFOs are not fixture inputs."""


@pytest.mark.skip(reason="activated after the attributed happy-path RED")
def test_declared_oversize_fixture_is_rejected_before_read() -> None:
    """A descriptor reporting more than 65,536 bytes is rejected."""


@pytest.mark.skip(reason="activated after the attributed happy-path RED")
def test_stream_overflow_is_rejected_at_cap_plus_one() -> None:
    """The bounded reader rejects the first byte beyond the cap."""


@pytest.mark.skip(reason="activated after the attributed happy-path RED")
def test_same_descriptor_change_is_rejected_before_parse() -> None:
    """Pre/post descriptor metadata changes fail closed."""


@pytest.mark.skip(reason="activated after the attributed happy-path RED")
def test_invalid_fixture_diagnostics_do_not_disclose_hostile_canaries() -> None:
    """Raw JSON, Pydantic details, credentials and paths never escape."""


@pytest.mark.skip(reason="activated after the attributed happy-path RED")
def test_exception_arguments_do_not_reach_any_durable_surface() -> None:
    """Exception args are replaced by a fixed allowlisted summary."""


@pytest.mark.skip(reason="activated after the attributed happy-path RED")
def test_fail_after_generator_is_durable_and_stops_before_validators() -> None:
    """Generator succeeds durably before intentional interruption."""
