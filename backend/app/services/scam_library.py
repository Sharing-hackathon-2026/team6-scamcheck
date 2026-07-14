"""Nạp và kiểm tra thư viện kiểu lừa đảo tĩnh Stage 3."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GROUP_KEYS = {"fake_bank", "fake_police", "prize", "delivery"}
DEFAULT_LIBRARY_PATH = Path(__file__).resolve().parents[2] / "data" / "scam_library.json"


def validate_scam_library(value: Any) -> dict[str, Any]:
    """Cưỡng chế đúng bốn nhóm và ít nhất 12 mẫu có nội dung cần thiết."""
    if not isinstance(value, dict):
        raise ValueError("Thư viện phải là object JSON.")
    groups = value.get("groups")
    items = value.get("items")
    if not isinstance(groups, list) or not isinstance(items, list):
        raise ValueError("Thư viện thiếu groups hoặc items.")
    group_keys = {group.get("key") for group in groups if isinstance(group, dict)}
    if group_keys != GROUP_KEYS or len(groups) != 4:
        raise ValueError("Thư viện phải có đúng bốn nhóm Stage 3.")
    if len(items) < 12:
        raise ValueError("Thư viện phải có ít nhất 12 kiểu lừa đảo.")
    required = {"id", "group", "title", "summary", "warning_signs", "safe_action"}
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError("Mỗi mục thư viện phải có đủ trường bắt buộc.")
        if item["group"] not in GROUP_KEYS or item["id"] in seen:
            raise ValueError("Nhóm không hợp lệ hoặc id bị trùng.")
        if not isinstance(item["warning_signs"], list) or not item["warning_signs"]:
            raise ValueError("Mỗi mục cần ít nhất một dấu hiệu.")
        seen.add(item["id"])
    return value


def load_scam_library(path: Path = DEFAULT_LIBRARY_PATH) -> dict[str, Any]:
    """Đọc JSON UTF-8 và validate trước khi công khai qua API."""
    with path.open(encoding="utf-8") as handle:
        return validate_scam_library(json.load(handle))
