"""Cấu hình ứng dụng, đọc từ biến môi trường.

Tất cả tham số nhạy cảm (đặc biệt GEMINI_API_KEY) chỉ lấy từ env, không hardcode.
"""
from __future__ import annotations

import os


class Config:
    """Đọc cấu hình từ env một cách an toàn."""

    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    FLASK_SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
    PORT: int = int(os.environ.get("PORT", "5000"))

    # CORS (chỉ cần khi dev tách port). Prod qua Nginx cùng origin thì để rỗng.
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "").split(",")
        if o.strip()
    ]

    BASE_URL: str = os.environ.get("BASE_URL", "")

    # Endpoint Gemini REST.
    GEMINI_ENDPOINT: str = (
        "https://generativelanguage.googleapis.com/v1beta/models"
    )

    # Giới hạn đầu vào (L2-08).
    MAX_INPUT_LENGTH: int = 5000

    # Timeout gọi Gemini (giây) — đảm bảo < 15s mục tiêu UX.
    GEMINI_TIMEOUT: float = 30.0


def is_configured() -> bool:
    """Trả True khi đủ điều kiện chạy AI thật."""
    return bool(Config.GEMINI_API_KEY)
