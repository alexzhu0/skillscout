"""Shared paths for the Phase 1 CLI contract tests.

The first execution of these tests is intentionally deferred until Gate B.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def approved_fixture() -> Path:
    return Path(__file__).parent / "fixtures" / "pipeline" / "approved.json"


@pytest.fixture
def run_cli():
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "skillscout.cli", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    return _run


def parse_cli_json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """Parse a successful CLI response without hiding stderr in assertions."""
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)
