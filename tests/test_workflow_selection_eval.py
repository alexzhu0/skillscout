"""Offline evaluation plumbing, never a live semantic-quality claim."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/evaluate_workflow_selection.py"
DATA = ROOT / "tests/fixtures/workflow_selection/cases.json"
EXPECTED = {
    "rag_core": "select",
    "review_core": "select",
    "mixed_core": "select",
    "demo_only": "reject",
    "insufficient": "abstain",
    "injected": "reject",
    "real_v3_demo": "reject",
}


def _run(tmp_path, predictions):
    path = tmp_path / "predictions.json"
    path.write_text(json.dumps(predictions))
    return subprocess.run(
        [sys.executable, "-I", str(TOOL), "--predictions", str(path)],
        capture_output=True, text=True, check=False,
    )


def test_all_reject_cannot_masquerade_as_good_selection(tmp_path):
    result = _run(tmp_path, dict.fromkeys(EXPECTED, "reject"))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["matched"] == 3
    assert report["total"] == 7
    assert report["missed_core"] == ["mixed_core", "rag_core", "review_core"]
    assert report["incorrectly_selected"] == []
    assert report["not_evaluated"] == ["model_behavior", "skill_usefulness", "publication_admission"]


def test_all_select_exposes_negative_selection_and_abstention_errors(tmp_path):
    result = _run(tmp_path, dict.fromkeys(EXPECTED, "select"))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["matched"] == 3
    assert report["incorrectly_selected"] == [
        "demo_only", "injected", "insufficient", "real_v3_demo",
    ]
    assert report["missed_core"] == []
    assert report["mismatches"]["insufficient"] == {"expected": "abstain", "actual": "select"}


def test_supplied_matching_labels_report_agreement_not_live_success(tmp_path):
    result = _run(tmp_path, EXPECTED)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["matched"] == 7
    assert report["mismatches"] == {}
    assert report["kind"] == "offline_label_comparison"
    assert report["label_status"] == "assistant_proposed_not_human_validated"
    assert "passed" not in report


@pytest.mark.parametrize("change", ["missing", "extra", "invalid", "bool", "list"])
def test_incomplete_or_invalid_predictions_fail_closed(tmp_path, change):
    predictions = dict(EXPECTED)
    if change == "missing":
        predictions.pop("rag_core")
    elif change == "extra":
        predictions["not_in_set"] = "select"
    elif change == "invalid":
        predictions["rag_core"] = "approved"
    elif change == "bool":
        predictions["rag_core"] = True
    else:
        predictions = list(predictions)
    result = _run(tmp_path, predictions)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip() == "invalid evaluation input"


def test_duplicate_prediction_keys_fail_without_echoing_input(tmp_path):
    path = tmp_path / "predictions.json"
    path.write_text('{"rag_core":"select","rag_core":"private-canary-text"}')
    result = subprocess.run(
        [sys.executable, "-I", str(TOOL), "--predictions", str(path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert result.stderr.strip() == "invalid evaluation input"
    assert "private-canary" not in result.stdout + result.stderr


def test_no_predictions_means_no_automatic_answer_key_evaluation():
    result = subprocess.run(
        [sys.executable, "-I", str(TOOL)], capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert not result.stdout
    assert "--predictions" in result.stderr


@pytest.mark.parametrize("content", [b"{broken", b"x" * 65_537, b"\xff"])
def test_malformed_oversized_or_non_json_bytes_do_not_leak(tmp_path, content):
    path = tmp_path / "predictions.json"
    path.write_bytes(content)
    result = subprocess.run(
        [sys.executable, "-I", str(TOOL), "--predictions", str(path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip() == "invalid evaluation input"


def test_report_binds_exact_inputs_without_mutating_them(tmp_path):
    dataset_before = DATA.read_bytes()
    result = _run(tmp_path, EXPECTED)
    assert result.returncode == 0, result.stderr
    predictions = (tmp_path / "predictions.json").read_bytes()
    report = json.loads(result.stdout)
    assert report["dataset_sha256"] == hashlib.sha256(dataset_before).hexdigest()
    assert report["predictions_sha256"] == hashlib.sha256(predictions).hexdigest()
    assert DATA.read_bytes() == dataset_before
    assert json.loads(predictions) == EXPECTED
    assert list(tmp_path.iterdir()) == [tmp_path / "predictions.json"]
