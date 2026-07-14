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
        ]
        if transfer_matches:
            signals.append(_signal_from_match(
                code="money_request", severity="danger", label="Yêu cầu chuyển tiền hoặc đóng phí",
                explanation="Không nên chuyển tiền hoặc nộp phí chỉ dựa trên hướng dẫn trong tin nhắn.",
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
        if urgency_match and not _is_negated(clause, urgency_match.start()):
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
