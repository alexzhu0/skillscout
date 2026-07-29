#!/usr/bin/env python3
"""Independent Phase 6 hard-gate registry; live facts start explicitly absent."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Sequence


SUCCESS = "phase6 hard-gate registry valid"
INCOMPLETE = "phase6 acceptance incomplete"
INVALID = "phase6 acceptance registry invalid"


@dataclass(frozen=True)
class HardGate:
    identifier: str
    blocking: bool = True


HARD_GATE_REGISTRY = tuple(
    HardGate(identifier)
    for identifier in (
        "benchmark_human_lock",
        "five_fixed_sha_repositories",
        "controlled_scenario_coverage",
        "hosted_kernel_isolation",
        "synthetic_secret_absence",
        "no_untrusted_execution",
        "closed_provider_policy",
        "license_custody",
        "provenance_custody",
        "evidence_integrity",
        "identical_replay_zero_effects",
        "changed_source_same_draft_update",
        "fresh_gate_b4_binding",
        "permission_causal_denials",
        "open_value_draft",
        "exact_head_human_review",
        "probe_cleanup_attestation",
        "report_rebuild",
        "all_44_requirements",
    )
)


def registry_is_exact() -> bool:
    identifiers = tuple(gate.identifier for gate in HARD_GATE_REGISTRY)
    return (
        len(identifiers) == 19
        and len(set(identifiers)) == len(identifiers)
        and all(gate.blocking is True for gate in HARD_GATE_REGISTRY)
        and identifiers[0] == "benchmark_human_lock"
        and identifiers[-1] == "all_44_requirements"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--registry-only", action="store_true")
    parser.add_argument("--offline-only", action="store_true")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        print(INVALID, file=sys.stderr)
        return 1
    if not registry_is_exact() or (args.registry_only and args.offline_only):
        print(INVALID, file=sys.stderr)
        return 1
    if args.registry_only:
        print(SUCCESS)
        return 0
    # Wave 0 must never convert absent hosted/live/human facts into PASS.
    print(INCOMPLETE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
