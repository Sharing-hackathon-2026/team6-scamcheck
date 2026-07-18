"""Dataset loader và metrics Stage 4, không phụ thuộc Flask/Gemini."""
from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Callable

LABELS = ("an_toan", "nghi_ngo", "nguy_hiem")
DEFAULT_EVALUATION_PATH = Path(__file__).resolve().parents[2] / "data" / "evaluation_messages.json"


def load_evaluation_cases(path: Path = DEFAULT_EVALUATION_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list) or len(value) < 60:
        raise ValueError("Bộ đánh giá phải có ít nhất 60 tin.")
    required = {"id", "text", "expected", "rationale", "tags", "difficulty", "split"}
    ids: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError("Ca đánh giá thiếu trường bắt buộc.")
        if item["id"] in ids or item["expected"] not in LABELS:
            raise ValueError("ID trùng hoặc nhãn không hợp lệ.")
        if item["difficulty"] not in {"easy", "hard"} or item["split"] not in {"dev", "eval"}:
            raise ValueError("difficulty/split không hợp lệ.")
        if not isinstance(item["tags"], list) or not item["tags"]:
            raise ValueError("Mỗi ca phải có tags.")
        ids.add(item["id"])
    counts = Counter(item["expected"] for item in value)
    expected_counts = {"an_toan": 30, "nghi_ngo": 15, "nguy_hiem": 15}
    if counts != expected_counts:
        raise ValueError(
            "Bộ đánh giá phải giữ 30 ca an toàn (gồm 15 ngoài phạm vi), "
            "15 nghi ngờ và 15 nguy hiểm."
        )
    if sum(item["difficulty"] == "hard" for item in value) < 15:
        raise ValueError("Bộ đánh giá cần ít nhất 15 ca khó.")
    if {item["split"] for item in value} != {"dev", "eval"}:
        raise ValueError("Bộ đánh giá cần cả dev và eval split.")
    return value


def evaluate_cases(
    cases: list[dict[str, Any]],
    predictor: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """Predictor trả actual, latency_ms và valid; sinh metrics đầy đủ."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        prediction = predictor(case["text"])
        actual = prediction.get("actual")
        valid = bool(prediction.get("valid", actual in LABELS))
        if actual not in LABELS:
            actual = "nghi_ngo"
            valid = False
        rows.append({
            "id": case["id"],
            "expected": case["expected"],
            "actual": actual,
            "correct": actual == case["expected"],
            "valid": valid,
            "latency_ms": round(float(prediction.get("latency_ms", 0.0)), 2),
            "difficulty": case["difficulty"],
            "split": case["split"],
            "error": str(prediction.get("error", "")),
        })

    matrix = {expected: {actual: 0 for actual in LABELS} for expected in LABELS}
    for row in rows:
        matrix[row["expected"]][row["actual"]] += 1
    per_class: dict[str, dict[str, float | int]] = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[expected][label] for expected in LABELS if expected != label)
        fn = sum(matrix[label][actual] for actual in LABELS if actual != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
            "support": sum(matrix[label].values()),
        }
    latencies = [row["latency_ms"] for row in rows]
    correct = sum(row["correct"] for row in rows)
    hard_rows = [row for row in rows if row["difficulty"] == "hard"]
    return {
        "total": len(rows),
        "correct": correct,
        "accuracy": round(correct / len(rows), 4) if rows else 0.0,
        "hard_accuracy": round(sum(row["correct"] for row in hard_rows) / len(hard_rows), 4) if hard_rows else 0.0,
        "invalid_rate": round(sum(not row["valid"] for row in rows) / len(rows), 4) if rows else 0.0,
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0.0,
            "median": round(statistics.median(latencies), 2) if latencies else 0.0,
            "max": round(max(latencies), 2) if latencies else 0.0,
        },
        "per_class": per_class,
        "confusion_matrix": matrix,
        "rows": rows,
    }


def compare_reports(baseline: dict[str, Any], improved: dict[str, Any]) -> dict[str, float]:
    return {
        "accuracy_delta": round(improved["accuracy"] - baseline["accuracy"], 4),
        "danger_recall_delta": round(
            improved["per_class"]["nguy_hiem"]["recall"]
            - baseline["per_class"]["nguy_hiem"]["recall"],
            4,
        ),
        "hard_accuracy_delta": round(improved["hard_accuracy"] - baseline["hard_accuracy"], 4),
    }


def format_evaluation_markdown(report: dict[str, Any]) -> str:
    metadata = report["metadata"]
    baseline, improved = report["baseline"], report["improved"]
    lines = [
        "# Báo cáo đánh giá Stage 4",
        "",
        f"- Thời điểm: {metadata['timestamp']}",
        f"- Model: `{metadata['model']}`",
        f"- Commit: `{metadata['commit']}`",
        f"- Prompt/pipeline: `{metadata['prompt_version']}` / `{metadata['pipeline_version']}`",
        f"- Dataset: {baseline['total']} tin",
        f"- Phương pháp: {metadata.get('method', 'predictor cố định')}",
        "",
        "## Tổng quan",
        "",
        "| Metric | Baseline | Improved | Delta |",
        "|---|---:|---:|---:|",
        f"| Accuracy | {baseline['accuracy']:.1%} | {improved['accuracy']:.1%} | {report['comparison']['accuracy_delta']:+.1%} |",
        f"| Danger recall | {baseline['per_class']['nguy_hiem']['recall']:.1%} | {improved['per_class']['nguy_hiem']['recall']:.1%} | {report['comparison']['danger_recall_delta']:+.1%} |",
        f"| Hard accuracy | {baseline['hard_accuracy']:.1%} | {improved['hard_accuracy']:.1%} | {report['comparison']['hard_accuracy_delta']:+.1%} |",
        f"| Invalid/fallback | {baseline['invalid_rate']:.1%} | {improved['invalid_rate']:.1%} | — |",
        "",
        "## Theo lớp (improved)",
        "",
        "| Nhãn | Precision | Recall | F1 | Support |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in LABELS:
        metric = improved["per_class"][label]
        lines.append(
            f"| {label} | {metric['precision']:.1%} | {metric['recall']:.1%} | {metric['f1']:.1%} | {metric['support']} |"
        )
    lines.extend(["", "## Failure modes", ""])
    failures = report.get("failure_modes") or ["Chưa có failure mode được ghi nhận."]
    lines.extend(f"- {item}" for item in failures)
    return "\n".join(lines) + "\n"
