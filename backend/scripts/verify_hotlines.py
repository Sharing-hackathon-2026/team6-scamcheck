"""Kiểm tra thủ công có thể tái lập: số hotline xuất hiện trên URL official cụ thể.

Không chạy trong pytest/deploy vì cần mạng. Với PDF cần binary ``pdftotext`` nếu có.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.hotlines import load_hotline_table, normalize_phone

DEFAULT_DATA = ROOT / "data" / "hotlines.json"
DEFAULT_OUTPUT = ROOT / "reports" / "stage5-hotline-verification.json"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _visible_text(content: bytes, content_type: str) -> tuple[str, str]:
    if "pdf" in content_type.casefold():
        try:
            completed = subprocess.run(
                ["pdftotext", "-", "-"],
                input=content,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=20,
            )
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Không đọc được PDF; cần pdftotext để verify.") from exc
        return completed.stdout.decode("utf-8", errors="replace"), "pdftotext"
    parser = _TextExtractor()
    parser.feed(content.decode("utf-8", errors="replace"))
    return " ".join(parser.parts), "html_visible_text"


def verify(path: Path, timeout: float = 30.0) -> dict[str, Any]:
    table = load_hotline_table(path)
    results = []
    for item in table.entries:
        row: dict[str, Any] = {
            "id": item.id,
            "phone": item.phone,
            "source_url": item.source_url,
            "source_checked_at": item.source_checked_at,
        }
        try:
            response = requests.get(
                item.source_url,
                headers={"User-Agent": "ScamCheck-Hotline-Review/1.0"},
                timeout=timeout,
                allow_redirects=True,
            )
            content_type = response.headers.get("Content-Type", "")
            text, method = _visible_text(response.content, content_type)
            expected = item.normalized_phone
            found = expected in normalize_phone(text)
            row.update(
                {
                    "ok": response.status_code == 200 and found,
                    "http_status": response.status_code,
                    "final_url": response.url,
                    "content_type": content_type,
                    "match_method": method,
                    "number_found": found,
                    "content_sha256": hashlib.sha256(response.content).hexdigest(),
                }
            )
        except (requests.RequestException, RuntimeError) as exc:
            row.update({"ok": False, "error": str(exc)[:300]})
        results.append(row)
    return {
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_version": table.version,
        "data_reviewed_at": table.reviewed_at,
        "all_passed": all(item.get("ok") is True for item in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = verify(args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{sum(item['ok'] for item in report['results'])}/{len(report['results'])} nguồn khớp số")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
