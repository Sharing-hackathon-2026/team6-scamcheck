#!/usr/bin/env python3
"""Chạy 60 Gemini Detective calls và so baseline với pipeline Stage 4.

Có tốn API. Script không chạy trong pytest/deploy; chỉ chạy chủ động để tạo evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from app.prompts import DETECTIVE_FUNCTION_DECLARATIONS, DETECTIVE_SYSTEM_PROMPT
from app.services.cache import STAGE4_PIPELINE_VERSION
from app.services.evaluation import (
    compare_reports,
    evaluate_cases,
    format_evaluation_markdown,
    load_evaluation_cases,
)
from app.services.gemini import GeminiError, generate_function_call
from app.services.links import analyze_links
from app.services.parser import RISK_LEVELS, parse_detective
from app.services.rule_engine import evaluate_rules

PROMPT_VERSION = "detective-function-call-v5-evidence-threshold"


def stage3_baseline_prompt() -> str:
    """Khôi phục policy scope Stage 3 để đo baseline trước cải thiện Stage 4."""
    scope = f'''PHẠM VI:
Chỉ phân tích khi tin có hoặc nghi có giả danh; yêu cầu tiền; OTP, mật khẩu hoặc
thông tin nhạy cảm; link, QR hay tệp; đầu tư/lợi nhuận bất thường; đe dọa hoặc
áp lực khẩn cấp. Tin ngoài phạm vi phải có risk_level "an_toan", reason đúng nguyên văn
"Tin nhắn không thuộc nội dung cần kiểm tra lừa đảo.", red_flags [] và actions [].

NGUYÊN TẮC PHÂN LOẠI THEO BẰNG CHỨNG:'''
    prompt = re.sub(
        r"PHẠM VI:\n.*?\nNGUYÊN TẮC PHÂN LOẠI THEO BẰNG CHỨNG:", scope,
        DETECTIVE_SYSTEM_PROMPT, flags=re.DOTALL,
    )
    return re.sub(
        r'- "an_toan" dùng cho thông báo.*?tên/logo/số điện thoại/tiêu đề\.',
        '- "an_toan" chỉ dùng cho nội dung thuộc phạm vi kiểm tra mà không có bất kỳ dấu hiệu rủi ro nào nêu trên. Không khẳng định một tổ chức/người gửi là thật chỉ dựa vào tên, logo, số điện thoại hay tiêu đề.',
        prompt, flags=re.DOTALL,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=BACKEND / "reports")
    parser.add_argument(
        "--delay", type=float, default=4.2,
        help="Khoảng nghỉ giữa calls để không vượt giới hạn request/phút của provider.",
    )
    parser.add_argument("--prompt-mode", choices=("stage4", "stage3"), default="stage4")
    parser.add_argument("--output-name", default="stage4-evaluation")
    args = parser.parse_args()
    key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if not key:
        print("Thiếu GEMINI_API_KEY; không gọi AI.", file=sys.stderr)
        return 2

    cases = load_evaluation_cases()
    system_prompt = DETECTIVE_SYSTEM_PROMPT if args.prompt_mode == "stage4" else stage3_baseline_prompt()
    prompt_version = PROMPT_VERSION if args.prompt_mode == "stage4" else "detective-function-call-v2-stage3-scope"
    raw_by_text: dict[str, dict] = {}
    print(f"Đang chạy {len(cases)} tin với {model} ({args.prompt_mode})…", flush=True)
    for index, case in enumerate(cases, 1):
        started = time.perf_counter()
        error = ""
        try:
            _, raw = generate_function_call(
                api_key=key,
                model=model,
                user_prompt=case["text"],
                system_prompt=system_prompt,
                function_declarations=DETECTIVE_FUNCTION_DECLARATIONS,
                timeout=8.0,
                max_retries=1,
            )
        except GeminiError as exc:
            raw, error = {}, str(exc)
        raw_by_text[case["text"]] = {
            "raw": raw,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "error": error,
            "valid": isinstance(raw, dict) and raw.get("risk_level") in RISK_LEVELS,
        }
        print(f"[{index:02d}/{len(cases)}] {case['id']}", flush=True)
        if index < len(cases) and args.delay > 0:
            time.sleep(args.delay)

    def baseline_predictor(text: str) -> dict:
        record = raw_by_text[text]
        result = parse_detective(record["raw"], source_text="", rule_signals=[])
        return {**record, "actual": result.risk_level}

    def improved_predictor(text: str) -> dict:
        record = raw_by_text[text]
        links = analyze_links(text, resolve_shorteners=False)
        signals = evaluate_rules(text, links)
        result = parse_detective(record["raw"], source_text=text, rule_signals=signals)
        return {**record, "actual": result.risk_level}

    baseline = evaluate_cases(cases, baseline_predictor)
    improved = evaluate_cases(cases, improved_predictor)
    improved_failures = [row for row in improved["rows"] if not row["correct"]]
    failure_modes = []
    for row in improved_failures[:3]:
        case = next(item for item in cases if item["id"] == row["id"])
        failure_modes.append(
            f"{row['id']}: expected {row['expected']} nhưng ra {row['actual']} — {case['rationale']}"
        )
    while len(failure_modes) < 3:
        failure_modes.append(
            "Cần tiếp tục theo dõi false positive ở câu phủ định/ngữ cảnh giáo dục trên dữ liệu ngoài tập này."
        )

    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    report = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model,
            "commit": commit,
            "prompt_version": prompt_version,
            "pipeline_version": STAGE4_PIPELINE_VERSION,
            "method": "one model call per case; same raw output scored baseline and improved",
        },
        "baseline": baseline,
        "improved": improved,
        "comparison": compare_reports(baseline, improved),
        "failure_modes": failure_modes,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{args.output_name}.json"
    md_path = args.output_dir / f"{args.output_name}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(format_evaluation_markdown(report), encoding="utf-8")
    print(format_evaluation_markdown(report))
    print(f"Đã ghi {json_path} và {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
