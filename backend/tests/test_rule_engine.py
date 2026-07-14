import pytest

from app.services.links import analyze_links
from app.services.parser import parse_detective
from app.services.rule_engine import evaluate_rules


def codes(text):
    return {signal.code: signal for signal in evaluate_rules(text)}


@pytest.mark.parametrize(("text", "code"), [
    ("Hãy gửi mã OTP cho nhân viên.", "credential_request"),
    ("Cung cấp mật khẩu Internet Banking.", "credential_request"),
    ("Chụp CCCD và gửi qua Zalo.", "sensitive_data_request"),
    ("Chuyển 2 triệu đồng phí hồ sơ.", "money_request"),
    ("Chuyển tiền vào số tài khoản 0123456789.", "unknown_account"),
    ("Tài khoản sẽ bị khóa trong 10 phút.", "urgent_threat"),
])
def test_required_rule_categories(text, code):
    assert code in codes(text)


def test_negation_is_clause_local_and_cannot_hide_later_credential_request():
    text = "Không gửi OTP cho ai. Hãy gửi mã OTP cho tôi."
    signals = evaluate_rules(text)
    assert len([item for item in signals if item.code == "credential_request"]) == 1
    assert signals[0].excerpt == "gửi mã OTP"


def test_safe_negations_do_not_trigger_hard_rules():
    assert "credential_request" not in codes("Ngân hàng không bao giờ yêu cầu gửi mã OTP.")
    assert "money_request" not in codes("Bác không cần chuyển tiền trước.")


def test_educational_and_quoted_context_reduce_false_positive():
    assert evaluate_rules("Từ 'chuyển tiền' có bao nhiêu ký tự?") == []
    assert evaluate_rules("Số tài khoản trong ví dụ bài tập là 123456789.") == []


def test_rule_excerpt_is_always_real_source_slice():
    text = "Thông báo: vui lòng cung cấp số thẻ và CVV ngay."
    for signal in evaluate_rules(text):
        assert signal.excerpt in text


def test_danger_rule_can_only_raise_not_lower_model_verdict():
    raw_safe = {"risk_level": "an_toan", "reason": "Ổn", "red_flags": [], "actions": []}
    result = parse_detective(raw_safe, "Hãy gửi mã OTP ngay")
    assert result.risk_level == "nguy_hiem"
    assert len(result.actions) == 3
    raw_danger = {**raw_safe, "risk_level": "nguy_hiem"}
    assert parse_detective(raw_danger, "Tin mơ hồ").risk_level == "nguy_hiem"


def test_warning_rule_raises_safe_to_suspicious_not_dangerous():
    text = "Xem thông báo tại bit.ly/demo"
    links = analyze_links(text, resolve_shorteners=False)
    signals = evaluate_rules(text, links)
    raw = {"risk_level": "an_toan", "reason": "Ổn", "red_flags": [], "actions": []}
    assert parse_detective(raw, text, signals).risk_level == "nghi_ngo"


def test_spoofed_domain_is_a_danger_signal_with_reason():
    text = "Đăng nhập tại https://vietcombank.com.vn.evil.example/login"
    links = analyze_links(text, resolve_shorteners=False)
    signal = next(item for item in evaluate_rules(text, links) if item.code == "spoofed_domain")
    assert signal.severity == "danger"
    assert signal.excerpt in text
