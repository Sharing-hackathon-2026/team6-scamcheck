"""Test parser chịu lỗi L1-04."""
from __future__ import annotations

from app.prompts import STAGE1_REFUSAL
from app.services.parser import (
    AMBIGUOUS_REASON,
    CONSERVATIVE_REASON,
    DEFAULT_ACTIONS,
    has_explicit_high_risk_signal,
    parse_detective,
)


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


def test_outside_scope_is_folded_into_safe_with_canned_reason_and_empty_lists():
    result = parse_detective({"risk_level": "khong_lien_quan", "reason": "x", "red_flags": [1], "actions": ["x"]})
    assert result.risk_level == "an_toan"
    assert result.reason == STAGE1_REFUSAL
    assert result.red_flags == []
    assert result.actions == []


def test_safe_outside_scope_reason_variant_is_canonicalized():
    result = parse_detective({
        "risk_level": "an_toan",
        "reason": "Đây là trò chuyện ngoài phạm vi của công cụ.",
        "red_flags": [],
        "actions": ["x"],
    })
    assert result.risk_level == "an_toan"
    assert result.reason == STAGE1_REFUSAL
    assert result.actions == []


def test_conservative_guard_overrides_safe_otp_result():
    raw = {"risk_level": "an_toan", "reason": "Hợp lệ.", "red_flags": [], "actions": []}
    result = parse_detective(raw, "Nhân viên ngân hàng yêu cầu cung cấp mã OTP")
    assert result.risk_level == "nguy_hiem"
    assert result.reason == CONSERVATIVE_REASON
    assert result.actions == DEFAULT_ACTIONS


def test_conservative_guard_still_overrides_legacy_unrelated_money_request():
    raw = {"risk_level": "khong_lien_quan", "reason": "x", "red_flags": [], "actions": []}
    result = parse_detective(raw, "Chuyển tiền cọc 2 triệu đồng ngay")
    assert result.risk_level == "nguy_hiem"
    assert len(result.actions) == 3


def test_bare_money_request_caps_over_sensitive_model_at_suspicious():
    raw = {"risk_level": "nguy_hiem", "reason": "Quá bảo thủ.", "red_flags": [], "actions": []}
    result = parse_detective(raw, "Chuyển tiền cho tôi")
    assert result.risk_level == "nghi_ngo"
    assert result.reason == AMBIGUOUS_REASON
    assert result.red_flags[0].label == "Yêu cầu chuyển tiền chưa rõ bối cảnh"


def test_reward_expiry_with_plain_link_caps_over_sensitive_model_at_suspicious():
    text = "Điểm thưởng của bác sắp hết hạn hôm nay. Xem chi tiết tại rewards.example.com."
    raw = {
        "risk_level": "nguy_hiem",
        "reason": "Quá bảo thủ.",
        "red_flags": [{"label": "Thời hạn", "excerpt": "sắp hết hạn", "explanation": "Có áp lực."}],
        "actions": [],
    }
    result = parse_detective(raw, text)
    assert result.risk_level == "nghi_ngo"
    assert result.reason == AMBIGUOUS_REASON


def test_ambiguity_cap_does_not_lower_concrete_money_or_credential_request():
    raw = {"risk_level": "nguy_hiem", "reason": "Có bằng chứng.", "red_flags": [], "actions": []}
    assert parse_detective(raw, "Chuyển 2 triệu đồng vào tài khoản 0123456789.").risk_level == "nguy_hiem"
    reward_otp = "Điểm thưởng sắp hết hạn. Xem tại rewards.example.com và gửi mã OTP để nhận."
    assert parse_detective(raw, reward_otp).risk_level == "nguy_hiem"


def test_high_risk_guard_handles_unicode_combining_marks():
    text = "Cung c" + "a\u0302\u0301" + "p m" + "a\u0323\u0302" + "t kh" + "a\u0302\u0309" + "u ngay"
    assert has_explicit_high_risk_signal(text) is True


def test_high_risk_guard_does_not_mark_plain_conversation_or_bare_money_request():
    assert has_explicit_high_risk_signal("Chiều nay cả nhà ăn cơm lúc 6 giờ nhé") is False
    assert has_explicit_high_risk_signal("Chuyển tiền cho tôi") is False


def test_high_risk_guard_does_not_mark_security_advice_as_a_request():
    assert has_explicit_high_risk_signal("Không bao giờ gửi OTP hoặc mật khẩu cho người lạ") is False
