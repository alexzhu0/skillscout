"""Compare explicit offline candidate labels; never call a model or publish."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DATASET = Path(__file__).resolve().parents[1] / "tests/fixtures/workflow_selection/cases.json"
DECISIONS = frozenset({"select", "reject", "abstain"})
MAX_BYTES = 65_536


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _read_json(path: Path):
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("input too large")
    return json.loads(raw, object_pairs_hook=_unique_object), hashlib.sha256(raw).hexdigest()


def compare(dataset, predictions, *, dataset_digest: str, predictions_digest: str):
    """Report supplied-label agreement, not infer correctness from model text."""
    if (
        not isinstance(dataset, dict)
        or dataset.get("schema_version") != "workflow-selection-eval-v1"
        or dataset.get("label_status") != "assistant_proposed_not_human_validated"
        or not isinstance(dataset.get("cases"), list)
        or not dataset["cases"]
        or not isinstance(predictions, dict)
    ):
        raise ValueError("invalid evaluation input")
    expected = {}
    for case in dataset["cases"]:
        if not isinstance(case, dict):
            raise ValueError("invalid case")
        case_id = case.get("id")
        decision = case.get("expected")
        if (
            not isinstance(case_id, str)
            or not case_id
            or case_id in expected
            or not isinstance(decision, str)
            or decision not in DECISIONS
        ):
            raise ValueError("invalid case")
        expected[case_id] = decision
    if set(predictions) != set(expected) or any(
        not isinstance(value, str) or value not in DECISIONS for value in predictions.values()
    ):
        raise ValueError("invalid predictions")
    mismatches = {
        key: {"expected": expected[key], "actual": predictions[key]}
        for key in sorted(expected)
        if expected[key] != predictions[key]
    }
    return {
        "schema_version": "workflow-selection-comparison-v1",
        "kind": "offline_label_comparison",
        "label_status": dataset["label_status"],
        "dataset_sha256": dataset_digest,
        "predictions_sha256": predictions_digest,
        "total": len(expected),
        "matched": len(expected) - len(mismatches),
        "mismatches": mismatches,
        "missed_core": sorted(
            key for key in expected if expected[key] == "select" and predictions[key] != "select"
        ),
        "incorrectly_selected": sorted(
            key for key in expected if expected[key] != "select" and predictions[key] == "select"
        ),
        "not_evaluated": ["model_behavior", "skill_usefulness", "publication_admission"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        dataset, dataset_digest = _read_json(DATASET)
        predictions, predictions_digest = _read_json(args.predictions)
        report = compare(
            dataset, predictions,
            dataset_digest=dataset_digest, predictions_digest=predictions_digest,
        )
    except (OSError, ValueError, TypeError, RecursionError):
        print("invalid evaluation input", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
