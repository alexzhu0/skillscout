#!/usr/bin/env python3
"""Verify that Phase 6 Wave-0 suites are in one exact, collectable RED state."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UV = ROOT / ".tools" / "uv-0.11.29" / "bin" / "uv"

DOMAIN_CONTRACTS = (
    "NominationSetV1",
    "BenchmarkEntryV1",
    "BenchmarkLockAttestationV1",
    "LockedBenchmarkManifestV1",
    "AcceptanceScenarioResultV1",
    "HostedIsolationCapabilityV1",
    "OfflineAdversarialRunV1",
    "ReplayEvidenceV1",
    "ChangedSourceEvidenceV1",
    "PublicationReplayCompletionV1",
    "ChangedSourceDraftUpdateCompletionV1",
    "GateB4BindingV1",
    "HumanSkillReviewAttestationV1",
    "ProbeCleanupAttestationV1",
    "ReviewerCalibrationV1",
    "AcceptanceEvidenceRootV1",
    "AcceptanceReleaseVerdictV1",
)
APPLICATION_CONTRACTS = (
    "NominationDependencies",
    "LockedCampaignDependencies",
    "ReplayUpdateDependencies",
    "HumanAttestationDependencies",
    "CleanupAttestationDependencies",
    "AcceptanceRebuildDependencies",
)
PROVIDER_CONTRACTS = (
    "SemanticStage",
    "DEEPSEEK_MODEL_BY_STAGE",
)

SUITES = {
    "domain": {
        "files": ("tests/test_acceptance_domain.py",),
        "expected": tuple(
            (
                "tests/test_acceptance_domain.py::"
                f"test_required_phase6_domain_contract_is_missing[{name}]"
            )
            for name in DOMAIN_CONTRACTS
        ),
        "message_prefix": "phase6-missing-domain-contract:",
    },
    "application-provider": {
        "files": (
            "tests/test_acceptance_application.py",
            "tests/test_semantic_provider.py",
        ),
        "expected": (
            *tuple(
                (
                    "tests/test_acceptance_application.py::"
                    f"test_required_phase6_application_contract_is_missing[{name}]"
                )
                for name in APPLICATION_CONTRACTS
            ),
            *tuple(
                (
                    "tests/test_semantic_provider.py::"
                    f"test_required_phase6_provider_contract_is_missing[{name}]"
                )
                for name in PROVIDER_CONTRACTS
            ),
        ),
        "message_prefixes": {
            "tests/test_acceptance_application.py": (
                "phase6-missing-application-contract:"
            ),
            "tests/test_semantic_provider.py": "phase6-missing-provider-contract:",
        },
    },
}

FAILED_NODE_LINE = re.compile(r"^FAILED ([^ ]+)(?: - .*)?$", re.MULTILINE)
FAILED_MESSAGE_LINE = re.compile(
    r"^.*: Failed: (phase6-missing-[a-z-]+:[A-Za-z0-9_]+)$",
    re.MULTILINE,
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (str(UV), "run", "--locked", *args),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _fail(message: str, *, output: str = "") -> int:
    print(f"phase6-red-contract-verifier: FAIL: {message}", file=sys.stderr)
    if output:
        print(output, file=sys.stderr)
    return 1


def verify_suite(name: str) -> int:
    config = SUITES[name]
    files = tuple(config["files"])
    expected = tuple(config["expected"])
    collection = _run("pytest", "--collect-only", "-q", *files)
    collected_output = collection.stdout + collection.stderr
    if collection.returncode != 0:
        return _fail("collection failed", output=collected_output)
    collected_nodes = {
        line.strip()
        for line in collection.stdout.splitlines()
        if line.strip().startswith("tests/") and "::" in line
    }
    missing_nodes = set(expected) - collected_nodes
    if missing_nodes:
        return _fail(
            "required RED nodes did not collect",
            output="\n".join(sorted(missing_nodes)),
        )

    result = _run("pytest", "-q", "--tb=line", "-rA", *files)
    output = result.stdout + result.stderr
    if result.returncode != 1:
        return _fail(
            f"pytest returned {result.returncode}, expected the RED exit status 1",
            output=output,
        )
    if any(
        marker in output
        for marker in (
            "Traceback (most recent call last)",
            "ERROR collecting",
            "INTERNALERROR",
            "ModuleNotFoundError:",
            "ImportError:",
            "No module named ",
        )
    ):
        return _fail("traceback, collection, or infrastructure failure leaked", output=output)

    failed_nodes = set(FAILED_NODE_LINE.findall(output))
    if failed_nodes != set(expected):
        unexpected = failed_nodes - set(expected)
        absent = set(expected) - failed_nodes
        details = [
            *(f"unexpected: {node}" for node in sorted(unexpected)),
            *(f"missing: {node}" for node in sorted(absent)),
        ]
        return _fail("failure-node set is not exact", output="\n".join(details))
    if "message_prefix" in config:
        prefixes = {str(file): str(config["message_prefix"]) for file in files}
    else:
        prefixes = dict(config["message_prefixes"])
    expected_messages = set()
    for node in expected:
        file = node.split("::", 1)[0]
        contract = node.rsplit("[", 1)[-1].removesuffix("]")
        expected_messages.add(f"{prefixes[file]}{contract}")
    failure_messages = set(FAILED_MESSAGE_LINE.findall(output))
    if failure_messages != expected_messages:
        return _fail(
            "failure-message set is not exact",
            output="\n".join(sorted(failure_messages ^ expected_messages)),
        )
    for node in failed_nodes:
        contract = node.rsplit("[", 1)[-1].removesuffix("]")
        file = node.split("::", 1)[0]
        if f"{prefixes[file]}{contract}" not in failure_messages:
            return _fail(f"missing failure text for {node}")

    print(
        f"phase6-red-contract-verifier: PASS: {name} "
        f"collected with {len(expected)} exact missing-contract RED nodes"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=tuple(SUITES), required=True)
    args = parser.parse_args()
    if not UV.is_file():
        return _fail("repository-local locked uv executable is missing")
    return verify_suite(args.suite)


if __name__ == "__main__":
    raise SystemExit(main())
