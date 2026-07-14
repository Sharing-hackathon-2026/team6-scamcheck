"""Cấu hình ứng dụng, đọc từ biến môi trường.

Tất cả tham số nhạy cảm (đặc biệt GEMINI_API_KEY) chỉ lấy từ env, không hardcode.
"""
from __future__ import annotations

import os


def _positive_int(value: str | None, default: int) -> int:
    """Đọc số nguyên dương từ env, trả ``default`` nếu giá trị không hợp lệ."""
    try:
        parsed = int(value or "")
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _bounded_timeout(value: str | None, default: float = 8.0) -> float:
    """Đọc timeout an toàn: tối đa 8 giây cho mỗi lần gọi Gemini."""
    try:
        parsed = float(value or "")
    except ValueError:
        return default
    return min(8.0, parsed) if parsed > 0 else default


class Config:
    """Đọc cấu hình từ env một cách an toàn."""

    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    FLASK_SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
    PORT: int = _positive_int(os.environ.get("PORT"), 5000)

    # CORS (chỉ cần khi dev tách port). Prod qua Nginx cùng origin thì để rỗng.
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]

    BASE_URL: str = os.environ.get("BASE_URL", "")
    GEMINI_ENDPOINT: str = "https://generativelanguage.googleapis.com/v1beta/models"
    MAX_INPUT_LENGTH: int = 5000

    # L1-07: giới hạn cứng tài nguyên theo phiên trình duyệt.
    AI_CALL_LIMIT: int = _positive_int(os.environ.get("AI_CALL_LIMIT"), 10)
    # Ba lần thử tối đa 8s + backoff 0.5 + 1s vẫn dưới ~26s.
    GEMINI_TIMEOUT: float = _bounded_timeout(os.environ.get("GEMINI_TIMEOUT"))
    GEMINI_MAX_RETRIES: int = 2


def is_configured() -> bool:
    """Trả True khi đủ điều kiện chạy AI thật."""
    return bool(Config.GEMINI_API_KEY)
