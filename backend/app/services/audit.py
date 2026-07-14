"""Nhật ký AI trong bộ nhớ theo từng phiên (L1-08)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SESSION_LOG_KEY = "ai_call_log"


def summarize_result(result: dict[str, Any]) -> str:
    """Tạo tóm tắt ngắn, không lưu toàn bộ nội dung tin nhắn nhạy cảm."""
    risk_level = result.get("risk_level")
    if isinstance(risk_level, str):
        return f"Mức rủi ro: {risk_level.replace('_', ' ')}"
    return "Đã nhận kết quả kiểm tra"


def append_ai_log(session: Any, input_length: int, result: dict[str, Any]) -> None:
    """Ghi tối đa 10 lần gọi gần nhất vào Flask session."""
    logs = session.get(SESSION_LOG_KEY, [])
    if not isinstance(logs, list):
        logs = []
    logs.append(
        {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "input_length": input_length,
            "summary": summarize_result(result),
        }
    )
    session[SESSION_LOG_KEY] = logs[-10:]
    if hasattr(session, "modified"):
        session.modified = True


def get_ai_log(session: Any) -> list[dict[str, Any]]:
    """Đọc log phiên, loại bỏ dữ liệu hỏng thay vì gây lỗi endpoint."""
    logs = session.get(SESSION_LOG_KEY, [])
    return logs if isinstance(logs, list) else []
