import json

import pytest

from app.services.evaluation import (
    LABELS,
    compare_reports,
    evaluate_cases,
    format_evaluation_markdown,
    load_evaluation_cases,
)


def test_dataset_has_60_balanced_cases_hard_subset_and_splits():
    cases = load_evaluation_cases()
    assert len(cases) == 60
    assert {label: sum(case["expected"] == label for case in cases) for label in LABELS} == {
        label: 15 for label in LABELS
    }
    assert sum(case["difficulty"] == "hard" for case in cases) >= 15
    assert {case["split"] for case in cases} == {"dev", "eval"}


def test_metrics_confusion_recall_latency_invalid_and_comparison():
    cases = [
        {"id": "1", "text": "a", "expected": "nguy_hiem", "difficulty": "hard", "split": "eval"},
        {"id": "2", "text": "b", "expected": "an_toan", "difficulty": "easy", "split": "eval"},
        {"id": "3", "text": "c", "expected": "nguy_hiem", "difficulty": "easy", "split": "dev"},
    ]
    outputs = {
        "a": {"actual": "nghi_ngo", "latency_ms": 10, "valid": True},
        "b": {"actual": "an_toan", "latency_ms": 20, "valid": True},
        "c": {"actual": "bad", "latency_ms": 30, "valid": False},
    }
    baseline = evaluate_cases(cases, outputs.__getitem__)
    assert baseline["accuracy"] == pytest.approx(1 / 3, abs=0.0001)
    assert baseline["per_class"]["nguy_hiem"]["recall"] == 0
    assert baseline["invalid_rate"] == pytest.approx(1 / 3, abs=0.0001)
    assert baseline["latency_ms"]["median"] == 20
    improved_outputs = {**outputs, "a": {"actual": "nguy_hiem"}, "c": {"actual": "nguy_hiem"}}
    improved = evaluate_cases(cases, improved_outputs.__getitem__)
    delta = compare_reports(baseline, improved)
    assert delta["accuracy_delta"] > 0
    assert delta["danger_recall_delta"] == 1


def test_markdown_report_contains_reproducibility_and_failure_modes():
    fake_metric = {
        "total": 60, "accuracy": 0.8, "hard_accuracy": 0.7, "invalid_rate": 0.0,
        "per_class": {label: {"precision": 0.8, "recall": 0.8, "f1": 0.8, "support": 15} for label in LABELS},
    }
    report = {
        "metadata": {"timestamp": "now", "model": "m", "commit": "abc", "prompt_version": "p", "pipeline_version": "v"},
        "baseline": fake_metric,
        "improved": fake_metric,
        "comparison": {"accuracy_delta": 0, "danger_recall_delta": 0, "hard_accuracy_delta": 0},
        "failure_modes": ["Một", "Hai", "Ba"],
    }
    output = format_evaluation_markdown(report)
    assert "Model: `m`" in output
    assert "Failure modes" in output
    assert output.count("- Một") == 1


def test_dataset_loader_rejects_unbalanced_copy(tmp_path):
    cases = load_evaluation_cases()
    cases[0]["expected"] = "nguy_hiem"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        load_evaluation_cases(path)
