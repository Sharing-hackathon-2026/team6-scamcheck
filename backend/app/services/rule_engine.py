"""Pure rule engine Stage 4 — lớp tín hiệu độc lập với Gemini."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

from .links import LinkAnalysis, analyze_links

_REQUEST = r"(?:gửi|cung\s*cấp|nhập|đọc|cho\s*biết|xác\s*nhận|điền|chia\s*sẻ|chụp)"
_CREDENTIAL = r"(?:mã\s*)?(?:otp|pin)|mật\s*khẩu|password|passcode|cvv"
_SENSITIVE = r"cccd|cmnd|căn\s*cước|số\s*thẻ|thông\s*tin\s*thẻ|ngày\s*sinh"
_NEGATION_RE = re.compile(r"(?:^|\b)(?:không(?:\s+cần)?|chẳng|đừng|chớ|khỏi)(?:\s+bao\s*giờ)?(?:\s+(?:yêu\s*cầu|đề\s*nghị))?\s*$", re.I)
_CLAUSE_RE = re.compile(r"[^.!?;\n]+(?:[.!?;\n]+|$)")

_CREDENTIAL_PATTERNS = (
    re.compile(rf"\b{_REQUEST}\b.{{0,45}}\b(?:{_CREDENTIAL})\b", re.I),
    re.compile(rf"\b(?:{_CREDENTIAL})\b.{{0,32}}\b{_REQUEST}\b", re.I),
)
_SENSITIVE_PATTERNS = (
    re.compile(rf"\b{_REQUEST}\b.{{0,45}}\b(?:{_SENSITIVE})\b", re.I),
    re.compile(rf"\b(?:{_SENSITIVE})\b.{{0,32}}\b{_REQUEST}\b", re.I),
)
_TRANSFER_RE = re.compile(
    r"\b(?:chuyển|nộp|gửi|đóng|thanh\s*toán)\b.{0,45}"
    r"\b(?:tiền|phí|cọc|vnđ|vnd|đồng|usd|usdt|khoản)\b",
    re.I,
)
_ACCOUNT_RE = re.compile(
    r"\b(?:stk|số\s*tài\s*khoản|tài\s*khoản)\b\s*(?:là|:|-)?\s*\d(?:[\s.-]?\d){5,18}\b",
    re.I,
)
_MONEY_AMOUNT_RE = re.compile(
    r"\b\d[\d.,\s]{0,14}\s*(?:k|nghìn|ngàn|triệu|tỷ|đồng|vnđ|vnd|usd|usdt)\b",
    re.I,
)
_MONEY_CONTEXT_RE = re.compile(
    r"\b(?:phí|tiền\s*cọc|đặt\s*cọc|phạt|thuế|chuộc|giữ\s*suất|xác\s*minh|"
    r"hồ\s*sơ|đầu\s*tư|tài\s*khoản\s*an\s*toàn|phục\s*vụ\s*điều\s*tra)\b",
    re.I,
)
_MONEY_DESTINATION_RE = re.compile(
    r"\b(?:vào|đến|tới|qua)\s+(?:stk|số\s*tài\s*khoản|tài\s*khoản|ví\s*điện\s*tử)\b",
    re.I,
)
_COMPLETED_MONEY_PREFIX_RE = re.compile(r"\b(?:đã|vừa)(?:\s+được)?\s*$", re.I)
_COMPLETED_MONEY_SUFFIX_RE = re.compile(
    r"^.{0,70}\b(?:thành\s*công|hoàn\s*tất|đã\s*nhận|đã\s*ghi\s*có)\b",
    re.I,
)
_BARE_MONEY_REQUEST_RE = re.compile(
    r"^\s*(?:(?:hãy|vui\s*lòng)\s+)?(?:chuyển|gửi)\s+tiền"
    r"(?:\s+(?:cho|giúp)\s+(?:tôi|mình|anh|chị|bác|em))?"
    r"(?:\s+(?:ngay|nhé|đi))?\s*[.!?]?\s*$",
    re.I,
)
_REWARD_EXPIRY_RE = re.compile(
    r"\b(?:điểm\s*(?:thưởng|tích\s*lũy)|phần\s*thưởng)\b.{0,80}"
    r"\b(?:sắp\s*hết\s*hạn|hết\s*hạn(?:\s+hôm\s+nay)?)\b",
    re.I,
)
_REWARD_FOLLOWUP_RE = re.compile(
    r"\b(?:xem|kiểm\s*tra|truy\s*cập|bấm)\b.{0,55}"
    r"(?:https?://|www\.|[\w-]+\.[a-z]{2,})",
    re.I,
)
_REWARD_HIGH_RISK_ACTION_RE = re.compile(
    r"\b(?:đăng\s*nhập|nhập\s+(?:mã|mật\s*khẩu|thông\s*tin)|cung\s*cấp|"
    r"chuyển\s*tiền|thanh\s*toán|tải\s*tệp|cài\s*(?:đặt|ứng\s*dụng)|quét\s*qr)\b",
    re.I,
)
_URGENCY_RE = re.compile(
    r"\b(?:khẩn\s*cấp|ngay\s*lập\s*tức|làm\s*ngay|trong\s*\d+\s*(?:phút|giờ)|"
    r"sắp\s*hết\s*hạn|cơ\s*hội\s*cuối)\b",
    re.I,
)
_THREAT_RE = re.compile(
    r"\b(?:bắt\s*giam|truy\s*tố|khóa\s*tài\s*khoản|tài\s*khoản.{0,16}(?:bị\s*)?khóa|"
    r"phạt\s*tiền|cắt\s*dịch\s*vụ|chịu\s*trách\s*nhiệm\s*trước\s*pháp\s*luật)\b",
    re.I,
)
_SUSPICIOUS_TLDS = {"xyz", "top", "click", "site", "live", "shop", "buzz", "icu"}
_EDUCATIONAL_CONTEXT_RE = re.compile(
    r"\b(?:ví\s*dụ|bài\s*tập|bao\s*nhiêu\s*ký\s*tự|dịch\s*câu|chữ\s*viết\s*tắt|trong\s*phim|bài\s*học)\b",
    re.I,
)
_IMPERATIVE_RE = re.compile(r"\b(?:hãy|vui\s*lòng|cần\s+bác|bác\s+phải|làm\s+ngay)\b", re.I)
_OTP_DELIVERY_NOTICE_RE = re.compile(
    r"^\s*(?:(?:ngân\s+hàng\s+)?[\wÀ-ỹ .-]{2,60}\s+thông\s+báo\s*:\s*)?"
    r"mã\s+(?:xác\s+thực\s+)?otp(?:\s+của\s+quý\s+khách)?\s*(?:là|:)\s*\d{4,8}"
    r"(?:\s*,?\s*(?:có\s+hiệu\s+lực(?:\s+trong(?:\s+vòng)?)?|hết\s+hạn\s+sau)"
    r"\s+\d+\s*(?:phút|giờ))?\s*[.!]?\s*$",
    re.I,
)
_OTP_VALIDITY_WINDOW_RE = re.compile(
    r"\bmã\s+(?:xác\s+thực\s+)?otp\b.{0,55}"
    r"\b(?:có\s+hiệu\s+lực(?:\s+trong(?:\s+vòng)?)?|hết\s+hạn\s+sau)\s+\d+\s*(?:phút|giờ)\b",
    re.I,
)


def is_otp_delivery_notification(text: str) -> bool:
    """Nhận diện hẹp thông báo *cấp* OTP, không nhầm thành yêu cầu giao OTP.

    Full-match có chủ ý: chỉ hạ verdict cho mẫu cấp mã thuần tuý. Chỉ cần có
    thêm link, lời yêu cầu thao tác, chuyển tiền hay đe doạ là không khớp và
    các guardrail bình thường vẫn áp dụng.
    """
    if not isinstance(text, str) or not text:
        return False
    return bool(_OTP_DELIVERY_NOTICE_RE.fullmatch(unicodedata.normalize("NFC", text)))


@dataclass(frozen=True)
class RuleSignal:
    code: str
    severity: str
    label: str
    excerpt: str
    explanation: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _clauses(text: str) -> Iterable[tuple[str, int]]:
    for match in _CLAUSE_RE.finditer(text):
        clause = match.group(0)
        if clause.strip():
            yield clause, match.start()


def _is_negated(clause: str, match_start: int) -> bool:
    """Chỉ xét phủ định sát hành động trong cùng mệnh đề."""
    prefix = clause[max(0, match_start - 28) : match_start]
    compact = " ".join(prefix.split())
    return bool(_NEGATION_RE.search(compact))


def _signal_from_match(
    *, code: str, severity: str, label: str, explanation: str,
    clause: str, clause_offset: int, match: re.Match[str], source: str,
) -> RuleSignal:
    start = clause_offset + match.start()
    end = clause_offset + match.end()
    return RuleSignal(code, severity, label, source[start:end], explanation)


def _is_completed_money_notice(clause: str, match: re.Match[str]) -> bool:
    """Loại thông báo giao dịch đã hoàn tất khỏi nhóm *yêu cầu* chuyển tiền."""
    prefix = clause[max(0, match.start() - 18) : match.start()]
    suffix = clause[match.end() :]
    return bool(
        _COMPLETED_MONEY_PREFIX_RE.search(prefix)
        or _COMPLETED_MONEY_SUFFIX_RE.search(suffix)
    )


def _money_request_is_concrete(clause: str) -> bool:
    """Chỉ coi yêu cầu tiền là nguy hiểm khi trong tin có chi tiết kiểm chứng được."""
    return any(pattern.search(clause) for pattern in (
        _MONEY_AMOUNT_RE,
        _ACCOUNT_RE,
        _MONEY_CONTEXT_RE,
        _MONEY_DESTINATION_RE,
        _THREAT_RE,
    ))


def is_low_context_ambiguity(
    text: str,
    signals: Iterable[RuleSignal] = (),
) -> bool:
    """Nhận diện hẹp hai dạng mơ hồ không đủ bằng chứng cho ``nguy_hiem``.

    Fail closed: chỉ trả true khi không có signal danger. Nội dung thêm OTP, dữ
    liệu nhạy cảm, tài khoản/tiền cụ thể, đe doạ hoặc tên miền giả vẫn giữ luồng
    nguy hiểm bình thường.
    """
    if not isinstance(text, str) or not text:
        return False
    if any(signal.severity == "danger" for signal in signals):
        return False
    working = unicodedata.normalize("NFC", text)
    return bool(
        _BARE_MONEY_REQUEST_RE.fullmatch(working)
        or (
            _REWARD_EXPIRY_RE.search(working)
            and _REWARD_FOLLOWUP_RE.search(working)
            and not _REWARD_HIGH_RISK_ACTION_RE.search(working)
        )
    )


def _pattern_signals(text: str) -> list[RuleSignal]:
    signals: list[RuleSignal] = []
    for clause, offset in _clauses(text):
        if _EDUCATIONAL_CONTEXT_RE.search(clause) and not _IMPERATIVE_RE.search(clause):
            continue
        for pattern in _CREDENTIAL_PATTERNS:
            for match in pattern.finditer(clause):
                if not _is_negated(clause, match.start()):
                    signals.append(_signal_from_match(
                        code="credential_request", severity="danger", label="Yêu cầu mã bí mật",
                        explanation="Tin yêu cầu OTP, PIN, mật khẩu hoặc mã bảo mật; thông tin này không nên cung cấp.",
                        clause=clause, clause_offset=offset, match=match, source=text,
                    ))
                    break
            else:
                continue
            break
        for pattern in _SENSITIVE_PATTERNS:
            for match in pattern.finditer(clause):
                if not _is_negated(clause, match.start()):
                    signals.append(_signal_from_match(
                        code="sensitive_data_request", severity="danger", label="Yêu cầu dữ liệu cá nhân",
                        explanation="Tin yêu cầu giấy tờ hoặc dữ liệu thẻ có thể bị lợi dụng để chiếm đoạt.",
                        clause=clause, clause_offset=offset, match=match, source=text,
                    ))
                    break
            else:
                continue
            break
        transfer_matches = [
            match for match in _TRANSFER_RE.finditer(clause)
            if not _is_negated(clause, match.start())
            and not _is_completed_money_notice(clause, match)
        ]
        if transfer_matches:
            concrete_money = _money_request_is_concrete(clause)
            signals.append(_signal_from_match(
                code="money_request",
                severity="danger" if concrete_money else "warning",
                label=(
                    "Yêu cầu chuyển tiền hoặc đóng phí" if concrete_money
                    else "Yêu cầu chuyển tiền chưa rõ bối cảnh"
                ),
                explanation=(
                    "Tin có số tiền, tài khoản, mục đích thanh toán hoặc áp lực cụ thể; không nên chuyển trước khi xác minh."
                    if concrete_money
                    else "Tin có yêu cầu tiền nhưng chưa nêu số tiền, tài khoản hay lý do cụ thể; cần hỏi lại và xác minh."
                ),
                clause=clause, clause_offset=offset, match=transfer_matches[0], source=text,
            ))
        account_match = _ACCOUNT_RE.search(clause)
        if account_match:
            signals.append(_signal_from_match(
                code="unknown_account", severity="danger" if transfer_matches else "warning",
                label="Có số tài khoản trong tin",
                explanation="Hãy tự xác minh chủ tài khoản qua kênh chính thức trước khi giao dịch.",
                clause=clause, clause_offset=offset, match=account_match, source=text,
            ))
        threat_match = _THREAT_RE.search(clause)
        if threat_match and not _is_negated(clause, threat_match.start()):
            signals.append(_signal_from_match(
                code="urgent_threat", severity="danger", label="Đe dọa hoặc gây áp lực",
                explanation="Kẻ gian thường gây sợ hãi để người nhận hành động trước khi kịp kiểm tra.",
                clause=clause, clause_offset=offset, match=threat_match, source=text,
            ))
        urgency_match = _URGENCY_RE.search(clause)
        validity_window = _OTP_VALIDITY_WINDOW_RE.search(clause)
        if urgency_match and not validity_window and not _is_negated(clause, urgency_match.start()):
            signals.append(_signal_from_match(
                code="urgency", severity="warning", label="Thúc giục gấp",
                explanation="Áp lực thời gian làm người nhận khó bình tĩnh xác minh thông tin.",
                clause=clause, clause_offset=offset, match=urgency_match, source=text,
            ))
    return signals


def _link_signals(links: Iterable[LinkAnalysis]) -> list[RuleSignal]:
    signals: list[RuleSignal] = []
    for link in links:
        warning_codes = {warning.code for warning in link.warnings}
        host = urlsplit(link.final_url or link.normalized_url).hostname or ""
        tld = host.rsplit(".", 1)[-1] if "." in host else ""
        if warning_codes & {"lookalike", "subdomain_deception", "suffix_deception", "mixed_script", "zero_width"}:
            signals.append(RuleSignal(
                "spoofed_domain", "danger", "Tên miền có dấu hiệu giả mạo", link.source_url,
                "Tên miền gần giống hoặc cố chèn tên một tổ chức chính thức; không nên đăng nhập hay cung cấp dữ liệu.",
            ))
        elif warning_codes & {"shortener", "punycode", "resolve_failed"}:
            signals.append(RuleSignal(
                "obscured_url", "warning", "Đường dẫn che khuất đích đến", link.source_url,
                "Đường dẫn rút gọn hoặc IDN khiến tên miền thật khó nhận biết.",
            ))
        elif tld.lower() in _SUSPICIOUS_TLDS:
            signals.append(RuleSignal(
                "unusual_tld", "danger", "Đường dẫn có đuôi miền rủi ro cao", link.source_url,
                "Đuôi miền bất thường đi cùng lời thúc thao tác; không nên mở trước khi xác minh chính thức.",
            ))
    return signals


def evaluate_rules(
    text: str,
    links: Iterable[LinkAnalysis] | None = None,
) -> list[RuleSignal]:
    """Trả các tín hiệu có cấu trúc; không tự đưa ra verdict cuối."""
    if not isinstance(text, str) or not text:
        return []
    working = unicodedata.normalize("NFC", text)
    inspected_links = list(links) if links is not None else analyze_links(
        working, resolve_shorteners=False
    )
    combined = _pattern_signals(working) + _link_signals(inspected_links)
    unique: dict[tuple[str, str], RuleSignal] = {}
    for signal in combined:
        unique.setdefault((signal.code, signal.excerpt), signal)
    return list(unique.values())[:8]


def signals_to_payload(signals: Iterable[RuleSignal]) -> list[dict[str, Any]]:
    return [signal.to_dict() for signal in signals]
