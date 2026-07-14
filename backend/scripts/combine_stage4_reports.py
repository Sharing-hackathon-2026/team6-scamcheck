#!/usr/bin/env python3
"""Ghép hai run Stage 3/Stage 4 thành report before/after chính thức."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.evaluation import compare_reports, format_evaluation_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("improved", type=Path)
    parser.add_argument("--output", type=Path, default=BACKEND / "reports" / "stage4-evaluation.json")
    args = parser.parse_args()
    baseline_run = json.loads(args.baseline.read_text(encoding="utf-8"))
    improved_run = json.loads(args.improved.read_text(encoding="utf-8"))
    if baseline_run["baseline"]["total"] != improved_run["improved"]["total"]:
        raise ValueError("Hai report không dùng cùng kích thước dataset.")
    if baseline_run["metadata"]["model"] != improved_run["metadata"]["model"]:
        raise ValueError("Hai report phải dùng cùng model.")
    baseline = baseline_run["baseline"]
    improved = improved_run["improved"]
    report = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": improved_run["metadata"]["model"],
            "commit": improved_run["metadata"]["commit"],
            "prompt_version": (
                f"baseline={baseline_run['metadata']['prompt_version']}; "
                f"improved={improved_run['metadata']['prompt_version']}"
            ),
            "pipeline_version": improved_run["metadata"]["pipeline_version"],
            "method": (
                "two throttled runs on the same labelled dataset; baseline prompt vs "
                "improved prompt + deterministic rules; invalid rate reported"
            ),
        },
        "baseline": baseline,
        "improved": improved,
        "comparison": compare_reports(baseline, improved),
        "failure_modes": improved_run.get("failure_modes", []),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(format_evaluation_markdown(report), encoding="utf-8")
    print(format_evaluation_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
