"""Chuẩn hoá phản hồi Thám tử từ Gemini (L1-04).

Gemini là một nguồn không tin cậy: mọi dữ liệu phải được kiểm tra và ép về một
hình dạng an toàn trước khi route trả cho trình duyệt.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..prompts import STAGE1_REFUSAL

RISK_LEVELS = {"an_toan", "nghi_ngo", "nguy_hiem", "khong_lien_quan"}
DEFAULT_ACTIONS = [
    "Không bấm link hoặc quét mã QR trong tin nhắn.",
    "Không cung cấp mã OTP, mật khẩu hay thông tin cá nhân.",
    "Liên hệ kênh chính thức của đơn vị được nhắc đến để kiểm tra.",
]


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


def parse_detective(raw: Any, source_text: str = "") -> DetectiveResult:
    """Validate và chuẩn hoá JSON Thám tử; không bao giờ ném exception.

    Nếu root hoặc mức rủi ro sai, dùng fallback thận trọng ``nghi_ngo``. Các
    trường con sai chỉ bị bỏ/điền fallback để vẫn giữ kết quả hữu ích.
    """
    if not isinstance(raw, dict):
        return fallback_detective_result()

    risk_level = raw.get("risk_level")
    if risk_level not in RISK_LEVELS:
        return fallback_detective_result()

    if risk_level == "khong_lien_quan":
        return DetectiveResult(
            risk_level=risk_level,
            reason=STAGE1_REFUSAL,
            red_flags=[],
            actions=[],
        )

    reason = _clean_text(raw.get("reason"), 350)
    if not reason:
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
            if label and explanation:
                flags.append(RedFlag(label=label, excerpt=excerpt, explanation=explanation))

    return DetectiveResult(
        risk_level=risk_level,
        reason=reason,
        red_flags=flags,
        actions=_normalise_actions(raw.get("actions")),
    )
