"""Chuẩn hoá phản hồi Thám tử từ Gemini (L1-04).

Gemini là một nguồn không tin cậy: mọi dữ liệu phải được kiểm tra và ép về một
hình dạng an toàn trước khi route trả cho trình duyệt.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from ..prompts import STAGE1_REFUSAL
from .rule_engine import (
    RuleSignal,
    evaluate_rules,
    is_low_context_ambiguity,
    is_otp_delivery_notification,
)

RISK_LEVELS = {"an_toan", "nghi_ngo", "nguy_hiem"}
_LEGACY_NOT_RELATED = "khong_lien_quan"
_OUTSIDE_SCOPE_HINT_RE = re.compile(
    r"\b(?:không\s+thuộc.{0,45}(?:kiểm\s+tra|lừa\s+đảo)|"
    r"không\s+liên\s+quan.{0,30}lừa\s+đảo|ngoài\s+phạm\s+vi)\b",
    re.I,
)
DEFAULT_ACTIONS = [
    "Không bấm link hoặc quét mã QR trong tin nhắn.",
    "Không cung cấp mã OTP, mật khẩu hay thông tin cá nhân.",
    "Liên hệ kênh chính thức của đơn vị được nhắc đến để kiểm tra.",
]
CONSERVATIVE_REASON = (
    "Tin nhắn có yêu cầu hoặc dấu hiệu rủi ro cao; không nên làm theo trước khi kiểm tra qua kênh chính thức."
)
AMBIGUOUS_REASON = (
    "Tin nhắn có dấu hiệu đáng ngờ nhưng chưa nêu đủ thông tin cụ thể để kết luận nguy hiểm; "
    "bác nên xác minh trước khi làm theo."
)
OTP_NOTICE_REASON = (
    "Đây là thông báo cấp mã OTP và thời hạn sử dụng; tin không yêu cầu gửi mã, "
    "bấm đường dẫn hay chuyển tiền. Nhãn này chỉ đánh giá nội dung, không xác nhận người gửi."
)
OTP_NOTICE_ACTIONS = [
    "Chỉ dùng mã cho giao dịch do chính bác vừa khởi tạo.",
    "Không đọc hoặc gửi mã OTP này cho bất kỳ ai.",
    "Nếu bác không yêu cầu mã, hãy tự mở ứng dụng ngân hàng để kiểm tra.",
]

def has_explicit_high_risk_signal(source_text: str) -> bool:
    """Tương thích API cũ: dùng rule engine theo mệnh đề để tránh bypass phủ định."""
    return any(signal.severity == "danger" for signal in evaluate_rules(source_text))


@dataclass(frozen=True)
class RedFlag:
    """Một dấu hiệu được gắn với đúng đoạn trích từ tin gốc."""

    label: str
    excerpt: str
    explanation: str

    def to_dict(self) -> dict[str, str]:
        """Chuyển thành JSON-safe dict."""
        return asdict(self)


@dataclass(frozen=True)
class DetectiveResult:
    """Kết quả có cấu trúc, luôn an toàn để frontend render."""

    risk_level: str
    reason: str
    red_flags: list[RedFlag]
    actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Chuyển thành payload JSON công khai."""
        return {
            "risk_level": self.risk_level,
            "reason": self.reason,
            "red_flags": [flag.to_dict() for flag in self.red_flags],
            "actions": self.actions,
        }


def _clean_text(value: Any, limit: int) -> str:
    """Ép giá trị về chuỗi gọn, tránh nội dung khổng lồ từ mô hình."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())[:limit]


def _safe_excerpt(value: Any, source_text: str) -> str:
    """Chỉ giữ excerpt xuất hiện nguyên văn trong input, tránh AI bịa trích dẫn."""
    excerpt = _clean_text(value, 100)
    if not excerpt:
        return ""
    return excerpt if excerpt in source_text else ""


def _normalise_actions(value: Any) -> list[str]:
    """Lấy tối đa ba hành động; thêm fallback để luôn đủ ba mục."""
    actions: list[str] = []
    if isinstance(value, list):
        for item in value:
            action = _clean_text(item, 180)
            if action and action not in actions:
                actions.append(action)
            if len(actions) == 3:
                break
    for fallback in DEFAULT_ACTIONS:
        if len(actions) == 3:
            break
        if fallback not in actions:
            actions.append(fallback)
    return actions


def fallback_detective_result() -> DetectiveResult:
    """Trả fallback thận trọng khi AI trả JSON sai hoặc thiếu trường."""
    return DetectiveResult(
        risk_level="nghi_ngo",
        reason="Không đọc được đầy đủ kết quả tự động; hãy thận trọng kiểm tra lại qua kênh chính thức.",
        red_flags=[],
        actions=DEFAULT_ACTIONS.copy(),
    )


@dataclass(frozen=True)
class PsychologistResult:
    """Lời giải thích ngắn, không có quyền thay đổi verdict Thám tử."""

    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_PSYCHOLOGIST_BLOCKED_PATTERNS = (
    re.compile(r"\b(?:system|developer|prompt|quy\s*tắc\s*ẩn)\b", re.I),
    re.compile(
        r"\b(?:tin|nội\s*dung).{0,24}(?:an\s*toàn|không\s*(?:phải|có)\s*lừa\s*đảo|không\s*nguy\s*hiểm)\b",
        re.I,
    ),
    re.compile(r"\b(?:bỏ\s*qua|đổi\s*vai|làm\s*theo\s*lệnh)\b", re.I),
)


def _sentence_count(text: str) -> int:
    """Đếm câu đủ ổn định cho lời giải thích tiếng Việt ngắn."""
    return len([part for part in re.split(r"[.!?]+(?:\s|$)", text) if part.strip()])


def parse_psychologist(raw: Any) -> PsychologistResult | None:
    """Chỉ nhận message 2–3 câu; từ chối đổi vai, lộ prompt hoặc hạ verdict."""
    if not isinstance(raw, dict):
        return None
    message = _clean_text(raw.get("message"), 600)
    if not message or not 2 <= _sentence_count(message) <= 3:
        return None
    if any(pattern.search(message) for pattern in _PSYCHOLOGIST_BLOCKED_PATTERNS):
        return None
    return PsychologistResult(message=message)


def should_activate_psychologist(risk_level: str) -> bool:
    """Cô tâm lý chỉ chạy sau verdict nghi ngờ hoặc nguy hiểm đã qua guardrail."""
    return risk_level in {"nghi_ngo", "nguy_hiem"}


def _flags_from_rules(signals: Iterable[RuleSignal], source_text: str) -> list[RedFlag]:
    flags: list[RedFlag] = []
    for signal in signals:
        excerpt = signal.excerpt if signal.excerpt and signal.excerpt in source_text else ""
        flag = RedFlag(
            label=_clean_text(signal.label, 80),
            excerpt=_clean_text(excerpt, 100),
            explanation=_clean_text(signal.explanation, 220),
        )
        if flag.label and flag.explanation and flag not in flags:
            flags.append(flag)
        if len(flags) == 3:
            break
    return flags


def parse_detective(
    raw: Any,
    source_text: str = "",
    rule_signals: Iterable[RuleSignal] | None = None,
) -> DetectiveResult:
    """Validate model output, merge rule signals và sửa ngoại lệ OTP notice hẹp."""
    signals = list(rule_signals) if rule_signals is not None else evaluate_rules(source_text)
    danger = any(signal.severity == "danger" for signal in signals)
    warning = any(signal.severity == "warning" for signal in signals)
    low_context = is_low_context_ambiguity(source_text, signals)

    # Ngoại lệ hẹp, deterministic: thông báo ngân hàng chỉ *cấp* OTP không phải
    # lời xin người nhận giao OTP. Full-match ở rule engine ngăn hạ verdict nếu
    # tin còn có link, yêu cầu thao tác, chuyển tiền hoặc nội dung khác.
    if not danger and is_otp_delivery_notification(source_text):
        return DetectiveResult("an_toan", OTP_NOTICE_REASON, [], OTP_NOTICE_ACTIONS.copy())

    raw_risk = raw.get("risk_level") if isinstance(raw, dict) else None
    if not isinstance(raw, dict) or raw_risk not in RISK_LEVELS | {_LEGACY_NOT_RELATED}:
        fallback = fallback_detective_result()
        if danger:
            return DetectiveResult(
                "nguy_hiem", CONSERVATIVE_REASON, _flags_from_rules(signals, source_text),
                fallback.actions,
            )
        return fallback

    risk_level = "an_toan" if raw_risk == _LEGACY_NOT_RELATED else raw_risk
    raw_reason = _clean_text(raw.get("reason"), 350)
    outside_scope = raw_risk == _LEGACY_NOT_RELATED or (
        risk_level == "an_toan"
        and (raw_reason == STAGE1_REFUSAL or bool(_OUTSIDE_SCOPE_HINT_RE.search(raw_reason)))
    )
    forced_by_rules = False
    ambiguity_capped = False
    if danger and risk_level != "nguy_hiem":
        risk_level = "nguy_hiem"
        outside_scope = False
        forced_by_rules = True
    elif low_context and risk_level == "nguy_hiem":
        # Hai mẫu mơ hồ được nhận diện hẹp không đủ bằng chứng để giữ nhãn đỏ,
        # kể cả khi model phản ứng quá bảo thủ. Chỉ áp dụng khi không có danger signal.
        risk_level = "nghi_ngo"
        outside_scope = False
        ambiguity_capped = True
    elif warning and risk_level == "an_toan":
        risk_level = "nghi_ngo"
        outside_scope = False
        forced_by_rules = True

    if outside_scope:
        return DetectiveResult("an_toan", STAGE1_REFUSAL, [], [])

    reason = raw_reason
    if ambiguity_capped:
        reason = AMBIGUOUS_REASON
    elif forced_by_rules:
        reason = CONSERVATIVE_REASON if danger else (
            "Tin nhắn có tín hiệu kỹ thuật cần xác minh thêm; không nên mở đường dẫn hoặc làm theo vội."
        )
    elif not reason:
        reason = "Kết quả cần được kiểm tra thận trọng trước khi làm theo."

    flags: list[RedFlag] = []
    raw_flags = raw.get("red_flags")
    if isinstance(raw_flags, list):
        for item in raw_flags[:3]:
            if not isinstance(item, dict):
                continue
            label = _clean_text(item.get("label"), 80)
            explanation = _clean_text(item.get("explanation"), 220)
            excerpt = _safe_excerpt(item.get("excerpt"), source_text)
            flag = RedFlag(label=label, excerpt=excerpt, explanation=explanation)
            if label and explanation and flag not in flags:
                flags.append(flag)
    for flag in _flags_from_rules(signals, source_text):
        if flag not in flags and len(flags) < 3:
            flags.append(flag)

    return DetectiveResult(
        risk_level=risk_level,
        reason=reason,
        red_flags=flags,
        actions=_normalise_actions(raw.get("actions")),
    )
