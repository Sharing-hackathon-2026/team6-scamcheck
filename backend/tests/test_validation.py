"""Test hàm validate_input (L2-08) — 2 trường hợp biên đầu tiên của Cấp 2.

Cấp 1 dùng luôn để chặn sớm; Cấp 2 mở rộng thêm.
"""
from __future__ import annotations

from app.services.validation import normalize_nfc, validate_input


def test_empty_string_invalid():
    errs = validate_input("")
    assert len(errs) == 1
    assert "dán" in errs[0].lower() or "vui lòng" in errs[0].lower()


def test_whitespace_only_invalid():
    assert validate_input("   \n  \t ") != []


def test_none_invalid():
    assert validate_input(None) != []  # type: ignore[arg-type]


def test_non_string_invalid():
    assert validate_input(12345) != []  # type: ignore[arg-type]


def test_valid_short_text_ok():
    assert validate_input("Chào bạn") == []


def test_too_long_text_invalid():
    long_text = "a" * 5001
    errs = validate_input(long_text, max_len=5000)
    assert len(errs) == 1
    assert "quá dài" in errs[0].lower()


def test_exactly_max_len_ok():
    assert validate_input("a" * 5000, max_len=5000) == []


def test_normalize_nfc_composes_vietnamese_combining_marks():
    decomposed = "Cung c" + "a\u0302\u0301" + "p m" + "a\u0323\u0302" + "t kh" + "a\u0302\u0309" + "u"
    normalized = normalize_nfc(decomposed)
    assert normalized == "Cung cấp mật khẩu"
    assert normalized != decomposed


def test_error_message_is_friendly_vietnamese():
    """Thông báo lỗi phải thân thiện, dễ hiểu cho người 45+."""
    errs = validate_input("")
    assert len(errs) > 0
    # không chứa traceback/kỹ thuật jargon
    msg = errs[0].lower()
    assert "traceback" not in msg and "exception" not in msg
