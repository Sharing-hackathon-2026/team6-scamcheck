"""Test loader, evaluator và report bộ hồi quy mà không gọi AI."""
import pytest

from app.services.regression import evaluate_regression, format_regression_report, load_regression_cases


def test_regression_dataset_has_twenty_labelled_messages():
    cases = load_regression_cases()
    assert len(cases) >= 20
    assert {case["expected"] for case in cases} == {
        "an_toan", "nghi_ngo", "nguy_hiem"
    }


def test_evaluator_compares_predictor_and_formats_table():
    cases = [
        {"id": "a", "text": "A", "expected": "an_toan", "reason": "x"},
        {"id": "b", "text": "B", "expected": "nguy_hiem", "reason": "y"},
    ]
    report = evaluate_regression(cases, lambda text: "an_toan")
    assert report["correct"] == 1
    assert report["accuracy"] == 0.5
    text = format_regression_report(report)
    assert "ĐÚNG" in text and "SAI" in text and "1/2" in text


def test_loader_rejects_too_small_dataset(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_regression_cases(path)
