"""Chuẩn hoá phản hồi Thám tử từ Gemini (L1-04).

Gemini là một nguồn không tin cậy: mọi dữ liệu phải được kiểm tra và ép về một
hình dạng an toàn trước khi route trả cho trình duyệt.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from ..prompts import STAGE1_REFUSAL

RISK_LEVELS = {"an_toan", "nghi_ngo", "nguy_hiem", "khong_lien_quan"}
DEFAULT_ACTIONS = [
    "Không bấm link hoặc quét mã QR trong tin nhắn.",
    "Không cung cấp mã OTP, mật khẩu hay thông tin cá nhân.",
    "Liên hệ kênh chính thức của đơn vị được nhắc đến để kiểm tra.",
]
CONSERVATIVE_REASON = (
    "Tin nhắn có yêu cầu hoặc dấu hiệu rủi ro cao; không nên làm theo trước khi kiểm tra qua kênh chính thức."
)

# Đây là guardrail hậu kiểm, không phải bộ phân loại lừa đảo. Nó chỉ nhận diện
# các tín hiệu rõ ràng mà theo hợp đồng tuyệt đối không được trả ``an_toan`` hay
# ``khong_lien_quan``. Việc phân tích ngữ cảnh và red flags vẫn do model thực hiện.
_REQUEST_VERBS = r"(?:gửi|gui|cung\s*cấp|cung\s*cap|nhập|nhap|đọc|doc|cho\s*biết|cho\s*biet|xác\s*nhận|xac\s*nhan)"
_CREDENTIALS = r"(?:otp|mã\s*pin|ma\s*pin|mật\s*khẩu|mat\s*khau|password|passcode)"
_SENSITIVE_DATA = r"(?:cccd|cmnd|căn\s*cước|can\s*cuoc|số\s*thẻ|so\s*the|cvv|số\s*tài\s*khoản|so\s*tai\s*khoan)"
_NEGATED_CREDENTIAL_REQUEST = re.compile(
    rf"\b(?:không|khong|đừng|dung|chớ)\b.{{0,24}}{_REQUEST_VERBS}.{{0,48}}(?:{_CREDENTIALS}|{_SENSITIVE_DATA})",
    re.I,
)
_CREDENTIAL_REQUEST_PATTERNS = (
    re.compile(rf"{_REQUEST_VERBS}.{{0,48}}(?:{_CREDENTIALS}|{_SENSITIVE_DATA})", re.I),
    re.compile(rf"(?:{_CREDENTIALS}|{_SENSITIVE_DATA}).{{0,48}}{_REQUEST_VERBS}", re.I),
)
_HIGH_RISK_PATTERNS = (
    re.compile(
        r"\b(?:chuyển|chuyen|nộp|nop|gửi|gui|đóng|dong|thanh\s*toán|thanh\s*toan)\b"
        r".{0,36}\b(?:tiền|tien|phí|phi|cọc|coc|vnđ|vnd|đồng|dong|usd|usdt)\b",
        re.I,
    ),
    # Chỉ hậu kiểm URL có đặc điểm đáng ngờ rõ, không coi mọi URL là độc hại.
    re.compile(
        r"(?:https?://)?(?:[^\s/@]+@|(?:\d{1,3}\.){3}\d{1,3}|(?:bit\.ly|tinyurl\.com|t\.co|"
        r"[a-z0-9-]+\.(?:xyz|top|click|site))(?:[/:?]|\b))",
        re.I,
    ),
    re.compile(
        r"\b(?:khẩn\s*cấp|khan\s*cap|ngay\s*lập\s*tức|ngay\s*lap\s*tuc|trong\s*\d+\s*(?:phút|phut|giờ|gio)|"
        r"bắt\s*giam|bat\s*giam|khóa\s*tài\s*khoản|khoa\s*tai\s*khoan|truy\s*tố|truy\s*to)\b",
        re.I,
    ),
)


def _searchable_text(value: str) -> str:
    """Chuẩn hoá Unicode vừa đủ để guardrail nhận diện chữ có dấu tổ hợp."""
    return unicodedata.normalize("NFC", value)


def has_explicit_high_risk_signal(source_text: str) -> bool:
    """Có tín hiệu thuộc nhóm tuyệt đối không được gán an toàn hay không."""
    if not isinstance(source_text, str) or not source_text:
        return False
    searchable = _searchable_text(source_text)
    credential_request = any(pattern.search(searchable) for pattern in _CREDENTIAL_REQUEST_PATTERNS)
    if credential_request and not _NEGATED_CREDENTIAL_REQUEST.search(searchable):
        return True
    return any(pattern.search(searchable) for pattern in _HIGH_RISK_PATTERNS)


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

    # Model không có quyền hạ mức rủi ro khi input chứa một tín hiệu cấm rõ ràng.
    # Guardrail chỉ nâng hai nhãn lạc quan; không thay thế phân tích của model.
    forced_high_risk = risk_level in {"an_toan", "khong_lien_quan"} and has_explicit_high_risk_signal(
        source_text
    )
    if forced_high_risk:
        risk_level = "nguy_hiem"

    if risk_level == "khong_lien_quan":
        return DetectiveResult(
            risk_level=risk_level,
            reason=STAGE1_REFUSAL,
            red_flags=[],
            actions=[],
        )

    reason = _clean_text(raw.get("reason"), 350)
    if forced_high_risk:
        reason = CONSERVATIVE_REASON
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
            if label and explanation:
                flags.append(RedFlag(label=label, excerpt=excerpt, explanation=explanation))

    return DetectiveResult(
        risk_level=risk_level,
        reason=reason,
        red_flags=flags,
        actions=_normalise_actions(raw.get("actions")),
    )
