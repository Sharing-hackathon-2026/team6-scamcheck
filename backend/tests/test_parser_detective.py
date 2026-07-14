"""Test parser chịu lỗi L1-04."""
from __future__ import annotations

from app.prompts import STAGE1_REFUSAL
from app.services.parser import DEFAULT_ACTIONS, parse_detective


def test_valid_result_keeps_supported_excerpt_and_three_actions():
    raw = {
        "risk_level": "nguy_hiem",
        "reason": "Tin yêu cầu mã OTP.",
        "red_flags": [
            {"label": "OTP", "excerpt": "gửi mã OTP", "explanation": "OTP rất nhạy cảm."}
        ],
        "actions": ["Không gửi OTP.", "Gọi ngân hàng.", "Chặn người gửi."],
    }
    result = parse_detective(raw, "Vui lòng gửi mã OTP ngay")
    assert result.risk_level == "nguy_hiem"
    assert result.red_flags[0].excerpt == "gửi mã OTP"
    assert len(result.actions) == 3


def test_non_dict_uses_cautious_fallback():
    result = parse_detective(["not", "a", "dict"])
    assert result.risk_level == "nghi_ngo"
    assert result.actions == DEFAULT_ACTIONS


def test_unknown_risk_uses_cautious_fallback():
    assert parse_detective({"risk_level": "red"}).risk_level == "nghi_ngo"


def test_invalid_nested_values_do_not_break_result():
    result = parse_detective({"risk_level": "nghi_ngo", "reason": 99, "red_flags": [None], "actions": "x"})
    assert result.risk_level == "nghi_ngo"
    assert len(result.actions) == 3
    assert result.red_flags == []


def test_hallucinated_excerpt_is_removed():
    result = parse_detective(
        {"risk_level": "nghi_ngo", "reason": "r", "red_flags": [{"label": "x", "excerpt": "bịa", "explanation": "e"}], "actions": []},
        "Tin gốc không có đoạn đó",
    )
    assert result.red_flags[0].excerpt == ""


def test_unrelated_has_canned_reason_and_empty_lists():
    result = parse_detective({"risk_level": "khong_lien_quan", "reason": "x", "red_flags": [1], "actions": ["x"]})
    assert result.reason == STAGE1_REFUSAL
    assert result.red_flags == []
    assert result.actions == []
