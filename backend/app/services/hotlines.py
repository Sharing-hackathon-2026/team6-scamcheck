"""Bảng tổng đài tĩnh đã rà soát và các guardrail số điện thoại Stage 5."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

_ALLOWED_TYPES = {"bank", "police", "cybersecurity"}
_ALLOWED_CHANNELS = {"phone", "sms"}
_PHONE_CANDIDATE_RE = re.compile(
    r"(?<![\w])(?:\+?84|\*|\d)[\d\s().-]{4,}\d(?![\w])"
)
_SHORT_UNKNOWN_PHONE_RE = re.compile(r"(?<![\d.,])\d{3,5}(?![\d.,]|\s+\d)")
_CONTACT_URL_RE = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?(?:/\S*)?",
    re.I,
)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I)
_BLOCKED_PHONE_TEXT = "[số chưa được xác minh đã bị ẩn]"


@dataclass(frozen=True)
class Hotline:
    """Một số liên hệ cùng nguồn chính thức để đối chiếu."""

    id: str
    name: str
    phone: str
    type: str
    aliases: tuple[str, ...]
    source_url: str
    source_label: str
    source_evidence: str
    source_checked_at: str
    channel: str = "phone"
    emergency_only: bool = False

    @property
    def normalized_phone(self) -> str:
        """Dạng chỉ còn số để so khớp bất kể khoảng trắng/dấu chấm."""
        return normalize_phone(self.phone)

    def to_public_dict(self, reviewed_at: str) -> dict[str, Any]:
        """Payload công khai không chứa alias nội bộ dùng để matching."""
        data = asdict(self)
        data.pop("aliases", None)
        data["reviewed_at"] = reviewed_at
        return data


@dataclass(frozen=True)
class HotlineTable:
    """Bảng hotline đã validate toàn bộ trước khi dùng trong prompt/API."""

    version: int
    reviewed_at: str
    notice: str
    entries: tuple[Hotline, ...]

    def by_id(self) -> dict[str, Hotline]:
        return {item.id: item for item in self.entries}


def normalize_phone(value: str) -> str:
    """Chuẩn hóa số điện thoại; dấu ``*`` của shortcode không ảnh hưởng whitelist."""
    return "".join(char for char in str(value) if char.isdigit())


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())[:limit]


def _parse_entry(raw: Any) -> Hotline:
    if not isinstance(raw, dict):
        raise ValueError("Mỗi hotline phải là object.")
    identifier = _clean_text(raw.get("id"), 40)
    name = _clean_text(raw.get("name"), 100)
    phone = _clean_text(raw.get("phone"), 30)
    kind = _clean_text(raw.get("type"), 30)
    source_url = _clean_text(raw.get("source_url"), 300)
    source_label = _clean_text(raw.get("source_label"), 160)
    source_evidence = _clean_text(raw.get("source_evidence"), 320)
    source_checked_at = _clean_text(raw.get("source_checked_at"), 20)
    channel = _clean_text(raw.get("channel", "phone"), 12) or "phone"
    aliases_raw = raw.get("aliases")
    aliases = tuple(
        item for item in (_clean_text(alias, 80) for alias in aliases_raw or []) if item
    )
    parsed_url = urlparse(source_url)
    if not identifier or not re.fullmatch(r"[a-z0-9_]+", identifier):
        raise ValueError("Hotline id không hợp lệ.")
    if not name or not phone or not normalize_phone(phone):
        raise ValueError(f"Hotline {identifier} thiếu tên hoặc số.")
    if kind not in _ALLOWED_TYPES:
        raise ValueError(f"Hotline {identifier} có type không hợp lệ.")
    if channel not in _ALLOWED_CHANNELS:
        raise ValueError(f"Hotline {identifier} có channel không hợp lệ.")
    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise ValueError(f"Hotline {identifier} phải có nguồn HTTPS.")
    if not source_label or not source_evidence or not source_checked_at or not aliases:
        raise ValueError(f"Hotline {identifier} thiếu bằng chứng nguồn, ngày kiểm tra hoặc alias.")
    if normalize_phone(phone) not in normalize_phone(source_evidence):
        raise ValueError(f"Bằng chứng hotline {identifier} không chứa đúng số đã công bố.")
    return Hotline(
        id=identifier,
        name=name,
        phone=phone,
        type=kind,
        aliases=aliases,
        source_url=source_url,
        source_label=source_label,
        source_evidence=source_evidence,
        source_checked_at=source_checked_at,
        channel=channel,
        emergency_only=raw.get("emergency_only") is True,
    )


def load_hotline_table(path: str | Path) -> HotlineTable:
    """Đọc và validate bảng; fail closed nếu trùng id/số hay thiếu tối thiểu 10 ngân hàng."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Không đọc được bảng tổng đài đã xác minh.") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
        raise ValueError("Bảng tổng đài không đúng cấu trúc.")
    entries = tuple(_parse_entry(item) for item in raw["entries"])
    ids = [item.id for item in entries]
    phones = [item.normalized_phone for item in entries]
    if len(ids) != len(set(ids)) or len(phones) != len(set(phones)):
        raise ValueError("Bảng tổng đài có id hoặc số bị trùng.")
    if sum(item.type == "bank" for item in entries) < 10:
        raise ValueError("Bảng tổng đài phải có ít nhất 10 ngân hàng.")
    if not any(item.type == "police" for item in entries):
        raise ValueError("Bảng tổng đài thiếu liên hệ Công an.")
    if not any(item.type == "cybersecurity" for item in entries):
        raise ValueError("Bảng tổng đài thiếu liên hệ an toàn thông tin.")
    reviewed_at = _clean_text(raw.get("reviewed_at"), 20)
    notice = _clean_text(raw.get("notice"), 400)
    if not reviewed_at or not notice:
        raise ValueError("Bảng tổng đài thiếu ngày rà soát hoặc lưu ý.")
    version = raw.get("version")
    return HotlineTable(
        version=version if isinstance(version, int) and version > 0 else 1,
        reviewed_at=reviewed_at,
        notice=notice,
        entries=entries,
    )


def match_bank_hotlines(message_text: str, entries: Iterable[Hotline]) -> list[Hotline]:
    """Tìm ngân hàng được nhắc đến bằng alias; alias ngắn phải khớp nguyên từ."""
    folded = _fold(message_text)
    matched: list[Hotline] = []
    for entry in entries:
        if entry.type != "bank":
            continue
        for alias in entry.aliases:
            needle = _fold(alias)
            pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
            if re.search(pattern, folded):
                matched.append(entry)
                break
    return matched[:2]


def _replace_phone_candidate(match: re.Match[str], whitelist: set[str]) -> str:
    candidate = match.group(0)
    normalized = normalize_phone(candidate)
    return candidate if normalized in whitelist else _BLOCKED_PHONE_TEXT


def contains_untrusted_contact(text: Any, whitelist: Iterable[str]) -> bool:
    """Phát hiện URL/email bất kỳ hoặc số contact không thuộc whitelist."""
    cleaned = _clean_text(text, 4000)
    if _CONTACT_URL_RE.search(cleaned) or _EMAIL_RE.search(cleaned):
        return True
    allowed = {normalize_phone(phone) for phone in whitelist}
    candidates = list(_PHONE_CANDIDATE_RE.finditer(cleaned)) + list(
        _SHORT_UNKNOWN_PHONE_RE.finditer(cleaned)
    )
    return any(normalize_phone(match.group(0)) not in allowed for match in candidates)


def strip_unknown_phones(text: Any, whitelist: Iterable[str]) -> str:
    """Ẩn cứng mọi chuỗi giống số điện thoại nhưng không có trong whitelist.

    Số thứ tự bước, số tiền ngắn và mốc thời gian hai chữ số không bị xem là số điện thoại.
    """
    cleaned = _clean_text(text, 900)
    allowed = {normalize_phone(phone) for phone in whitelist}
    cleaned = _PHONE_CANDIDATE_RE.sub(
        lambda match: _replace_phone_candidate(match, allowed), cleaned
    )
    return _SHORT_UNKNOWN_PHONE_RE.sub(
        lambda match: match.group(0)
        if normalize_phone(match.group(0)) in allowed
        else _BLOCKED_PHONE_TEXT,
        cleaned,
    )


def hotline_prompt_payload(table: HotlineTable) -> list[dict[str, str]]:
    """Dữ liệu tối thiểu truyền vào prompt; không nhúng hotline trong source prompt."""
    return [
        {
            "id": item.id,
            "name": item.name,
            "phone": item.phone,
            "type": item.type,
            "channel": item.channel,
        }
        for item in table.entries
    ]
