"""Chuẩn hoá phản hồi Thám tử từ Gemini (L1-04).

Gemini là một nguồn không tin cậy: mọi dữ liệu phải được kiểm tra và ép về một
hình dạng an toàn trước khi route trả cho trình duyệt.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from ..prompts import STAGE1_REFUSAL
from .rule_engine import RuleSignal, evaluate_rules

RISK_LEVELS = {"an_toan", "nghi_ngo", "nguy_hiem", "khong_lien_quan"}
DEFAULT_ACTIONS = [
    "Không bấm link hoặc quét mã QR trong tin nhắn.",
    "Không cung cấp mã OTP, mật khẩu hay thông tin cá nhân.",
    "Liên hệ kênh chính thức của đơn vị được nhắc đến để kiểm tra.",
]
CONSERVATIVE_REASON = (
    "Tin nhắn có yêu cầu hoặc dấu hiệu rủi ro cao; không nên làm theo trước khi kiểm tra qua kênh chính thức."
)

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
    """Validate model output rồi merge rule signals theo chính sách chỉ nâng rủi ro."""
    signals = list(rule_signals) if rule_signals is not None else evaluate_rules(source_text)
    danger = any(signal.severity == "danger" for signal in signals)
    warning = any(signal.severity == "warning" for signal in signals)

    if not isinstance(raw, dict) or raw.get("risk_level") not in RISK_LEVELS:
        fallback = fallback_detective_result()
        if danger:
            return DetectiveResult(
                "nguy_hiem", CONSERVATIVE_REASON, _flags_from_rules(signals, source_text),
                fallback.actions,
            )
        return fallback

    risk_level = raw["risk_level"]
    forced_by_rules = False
    if danger and risk_level != "nguy_hiem":
        risk_level = "nguy_hiem"
        forced_by_rules = True
    elif warning and risk_level in {"an_toan", "khong_lien_quan"}:
        risk_level = "nghi_ngo"
        forced_by_rules = True

    if risk_level == "khong_lien_quan":
        return DetectiveResult(risk_level, STAGE1_REFUSAL, [], [])

    reason = _clean_text(raw.get("reason"), 350)
    if forced_by_rules:
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
