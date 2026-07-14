"""Kiểm tra đầu vào người dùng (L2-08).

Trả về danh sách lỗi thân thiện (tiếng Việt) thay vì ném exception,
để route render thông báo cho người 45+ dễ hiểu.
"""
from __future__ import annotations

import unicodedata

from ..config import Config


def normalize_nfc(value: str) -> str:
    """Chuẩn hoá Unicode dựng sẵn để trình duyệt cũ render tiếng Việt ổn định."""
    if not isinstance(value, str):
        return value
    return unicodedata.normalize("NFC", value)


def validate_input(text: str, max_len: int | None = None) -> list[str]:
    """Kiểm tra văn bản tin nhắn.

    Args:
        text: nội dung tin nhắn người dùng dán vào.
        max_len: giới hạn ký tự (mặc định lấy từ Config).

    Returns:
        Danh sách thông báo lỗi (rỗng = hợp lệ). KHÔNG ném lỗi.
    """
    if max_len is None:
        max_len = Config.MAX_INPUT_LENGTH

    errors: list[str] = []

    if not isinstance(text, str) or not text.strip():
        errors.append("Vui lòng dán nội dung tin nhắn cần kiểm tra.")
        return errors

    if len(text) > max_len:
        errors.append(
            f"Tin nhắn quá dài ({len(text)} ký tự). Vui lòng gửi tối đa {max_len} ký tự."
        )

    return errors
