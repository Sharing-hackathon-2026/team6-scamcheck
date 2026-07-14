"""Nạp và chấm bộ hồi quy có nhãn Stage 3."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

DEFAULT_REGRESSION_PATH = Path(__file__).resolve().parents[2] / "data" / "regression_messages.json"


def load_regression_cases(path: Path = DEFAULT_REGRESSION_PATH) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list) or len(value) < 20:
        raise ValueError("Bộ hồi quy phải có ít nhất 20 tin.")
    required = {"id", "text", "expected", "reason"}
    if any(not isinstance(item, dict) or not required.issubset(item) for item in value):
        raise ValueError("Ca hồi quy thiếu trường bắt buộc.")
    return value


def evaluate_regression(
    cases: list[dict[str, str]], predictor: Callable[[str], str]
) -> dict[str, Any]:
    rows = []
    for case in cases:
        actual = predictor(case["text"])
        rows.append({**case, "actual": actual, "correct": actual == case["expected"]})
    correct = sum(row["correct"] for row in rows)
    return {"rows": rows, "correct": correct, "total": len(rows), "accuracy": correct / len(rows)}


def format_regression_report(report: dict[str, Any]) -> str:
    lines = ["ID | Expected | Actual | Result", "---|---|---|---"]
    for row in report["rows"]:
        lines.append(
            f"{row['id']} | {row['expected']} | {row['actual']} | {'ĐÚNG' if row['correct'] else 'SAI'}"
        )
    lines.append(f"Tổng: {report['correct']}/{report['total']} ({report['accuracy']:.1%})")
    return "\n".join(lines)
