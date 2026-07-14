#!/usr/bin/env python3
"""Chạy 20 tin hồi quy với Gemini thật; cần GEMINI_API_KEY trong môi trường."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config
from app.prompts import DETECTIVE_FUNCTION_DECLARATIONS, DETECTIVE_SYSTEM_PROMPT
from app.services.gemini import generate_function_call
from app.services.parser import parse_detective
from app.services.regression import evaluate_regression, format_regression_report, load_regression_cases


def predict(text: str) -> str:
    _, args = generate_function_call(
        api_key=os.environ.get("GEMINI_API_KEY", ""),
        model=os.environ.get("GEMINI_MODEL", Config.GEMINI_MODEL),
        user_prompt=text,
        system_prompt=DETECTIVE_SYSTEM_PROMPT,
        function_declarations=DETECTIVE_FUNCTION_DECLARATIONS,
        timeout=6.0,
        max_retries=1,
    )
    return parse_detective(args, source_text=text).risk_level


def main() -> int:
    report = evaluate_regression(load_regression_cases(), predict)
    print(format_regression_report(report))
    return 0 if report["correct"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
