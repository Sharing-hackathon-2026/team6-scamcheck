"""Nạp bộ luyện tập tĩnh 10 câu, không gọi AI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_QUIZ_PATH = Path(__file__).resolve().parents[2] / "data" / "quiz.json"


def validate_quiz(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != 10:
        raise ValueError("Bộ luyện tập phải có đúng 10 câu.")
    required = {"id", "text", "is_scam", "category", "explanation", "tip"}
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError("Câu luyện tập thiếu trường bắt buộc.")
        if not isinstance(item["is_scam"], bool):
            raise ValueError("Nhãn luyện tập phải là boolean.")
        if item["id"] in seen or any(not isinstance(item[key], str) or not item[key].strip() for key in required - {"is_scam"}):
            raise ValueError("Câu luyện tập có id trùng hoặc nội dung rỗng.")
        seen.add(item["id"])
    if {item["is_scam"] for item in value} != {True, False}:
        raise ValueError("Bộ luyện tập cần có cả tin an toàn và lừa đảo.")
    return value


def load_quiz(path: Path = DEFAULT_QUIZ_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return validate_quiz(json.load(handle))
