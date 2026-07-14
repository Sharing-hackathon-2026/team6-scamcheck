"""Phân tích URL, redirect rút gọn và tên miền giả cho Stage 4.

Module không tải body. URL thường chỉ được phân tích tại chỗ; chỉ shortener trong
allowlist mới được gọi mạng. Mỗi redirect hop phải qua kiểm tra DNS chống SSRF.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

DEFAULT_DOMAINS_PATH = Path(__file__).resolve().parents[2] / "data" / "legit_domains.json"
SHORTENER_DOMAINS = frozenset(
    {
        "bit.ly",
        "t.co",
        "tinyurl.com",
        "goo.gl",
        "is.gd",
        "cutt.ly",
        "shorturl.at",
        "tiny.one",
        "rebrand.ly",
        "buff.ly",
    }
)
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_ZERO_WIDTH_RE = re.compile("[\u200b-\u200f\u2060\ufeff]")
# http(s), www, hoặc bare domain. Negative lookbehind tránh lấy domain trong email.
_URL_RE = re.compile(
    r"(?<![@\w])(?:"
    r"(?:https?://|www\.)[^\s<>\"']+"
    r"|(?:[\w\u0080-\uffff](?:[\w\u0080-\uffff-]{0,62})\.)+"
    r"(?:[a-zA-Z\u0080-\uffff]{2,63}|xn--[a-zA-Z0-9-]{2,59})"
    r"(?::\d{1,5})?(?:/[^\s<>\"']*)?"
    r")",
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION = ".,;:!?…'\"”’"
_CONFUSABLES = str.maketrans(
    {
        # Cyrillic thường được dùng để giả chữ Latin.
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
        "і": "i", "ј": "j", "к": "k", "м": "m", "т": "t", "в": "b", "н": "h",
        "А": "a", "Е": "e", "О": "o", "Р": "p", "С": "c", "У": "y", "Х": "x",
        "І": "i", "Ј": "j", "К": "k", "М": "m", "Т": "t", "В": "b", "Н": "h",
        # Greek và thay thế số phổ biến.
        "α": "a", "ο": "o", "ρ": "p", "χ": "x", "ι": "i", "κ": "k", "ν": "v",
        "0": "o", "1": "l", "3": "e", "5": "s", "7": "t",
    }
)


class UnsafeUrlError(ValueError):
    """URL không được phép gọi từ backend vì có nguy cơ SSRF."""


@dataclass(frozen=True)
class DomainWarning:
    code: str
    reason: str
    official_domain: str = ""
    severity: str = "warning"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class LinkAnalysis:
    source_url: str
    normalized_url: str
    original_domain: str
    final_url: str
    final_domain: str
    resolved: bool
    warnings: list[DomainWarning]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "normalized_url": self.normalized_url,
            "original_domain": self.original_domain,
            "final_url": self.final_url,
            "final_domain": self.final_domain,
            "resolved": self.resolved,
            "warnings": [item.to_dict() for item in self.warnings],
        }


def _strip_url_punctuation(value: str) -> str:
    value = value.rstrip(_TRAILING_PUNCTUATION)
    pairs = (("(", ")"), ("[", "]"), ("{", "}"))
    for opening, closing in pairs:
        while value.endswith(closing) and value.count(closing) > value.count(opening):
            value = value[:-1]
    return value


def extract_urls(text: str) -> list[str]:
    """Tách URL theo thứ tự xuất hiện, bỏ punctuation và duplicate."""
    if not isinstance(text, str):
        return []
    found: list[str] = []
    for match in _URL_RE.finditer(text):
        candidate = _strip_url_punctuation(match.group(0))
        if candidate and candidate not in found:
            found.append(candidate)
    return found


def _idna_host(host: str) -> str:
    labels = []
    for label in _ZERO_WIDTH_RE.sub("", host.strip(".")).split("."):
        if not label:
            raise ValueError("Tên miền không hợp lệ.")
        labels.append(label.encode("idna").decode("ascii"))
    return ".".join(labels).lower()


def unicode_host(host: str) -> str:
    """Hiển thị host IDN ở Unicode khi decode được."""
    labels = []
    for label in host.strip(".").split("."):
        try:
            labels.append(label.encode("ascii").decode("idna"))
        except (UnicodeError, UnicodeEncodeError):
            labels.append(label)
    return ".".join(labels).lower()


def normalize_url(value: str) -> str:
    """Chuẩn hoá URL về HTTP(S), IDNA host và bỏ fragment."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("URL rỗng.")
    candidate = _strip_url_punctuation(value.strip())
    if re.match(r"^[a-z][a-z0-9+.-]*://", candidate, re.IGNORECASE) and not re.match(
        r"^https?://", candidate, re.IGNORECASE
    ):
        raise ValueError("Chỉ hỗ trợ URL HTTP hoặc HTTPS.")
    if not re.match(r"^https?://", candidate, re.IGNORECASE):
        candidate = "https://" + candidate
    parts = urlsplit(candidate)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Chỉ hỗ trợ URL HTTP hoặc HTTPS.")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("URL chứa thông tin đăng nhập nên không được mở từ máy chủ.")
    host = _idna_host(parts.hostname)
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("Cổng URL không hợp lệ.") from exc
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc += f":{port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "", parts.query, ""))


def _resolved_addresses(
    host: str,
    port: int,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
        return [literal]
    except ValueError:
        pass
    try:
        records = resolver(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeUrlError("Không phân giải được tên miền.") from exc
    addresses = []
    for record in records:
        try:
            addresses.append(ipaddress.ip_address(record[4][0]))
        except (IndexError, ValueError):
            continue
    if not addresses:
        raise UnsafeUrlError("Tên miền không có địa chỉ mạng hợp lệ.")
    return addresses


def assert_public_url(
    url: str,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> None:
    """Chỉ cho phép URL mà mọi kết quả DNS đều là địa chỉ Internet public."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise UnsafeUrlError("Chỉ hỗ trợ URL HTTP hoặc HTTPS.")
    host = parts.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise UnsafeUrlError("Tên miền nội bộ bị chặn.")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if any(not address.is_global for address in _resolved_addresses(host, port, resolver)):
        raise UnsafeUrlError("Địa chỉ private/loopback/link-local/reserved bị chặn.")


def resolve_redirects(
    url: str,
    *,
    max_redirects: int = 3,
    timeout: float = 1.5,
    request_get: Callable[..., Any] = requests.get,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> tuple[str, bool]:
    """Giải redirect hữu hạn, không đọc body và kiểm tra SSRF trước từng hop."""
    current = normalize_url(url)
    redirected = False
    for _ in range(max_redirects + 1):
        assert_public_url(current, resolver)
        response = request_get(
            current,
            allow_redirects=False,
            stream=True,
            timeout=timeout,
            headers={"User-Agent": "ScamCheck-LinkInspector/1.0"},
        )
        try:
            location = response.headers.get("Location", "")
            if response.status_code not in _REDIRECT_CODES or not location:
                return current, redirected
            next_url = normalize_url(urljoin(current, location))
        finally:
            response.close()
        if next_url == current:
            raise ValueError("Chuỗi chuyển hướng bị lặp.")
        current = next_url
        redirected = True
    raise ValueError(f"Đường dẫn chuyển hướng quá {max_redirects} lần.")


def load_legit_domains(path: Path = DEFAULT_DOMAINS_PATH) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or not isinstance(value.get("domains"), list):
        raise ValueError("Danh sách tên miền chính thức không hợp lệ.")
    result: list[dict[str, str]] = []
    for item in value["domains"]:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str) and item[key].strip()
            for key in ("brand", "domain", "source")
        ):
            raise ValueError("Tên miền chính thức thiếu brand/domain/source.")
        result.append({key: item[key].strip() for key in item if isinstance(item[key], str)})
    if len(result) < 10:
        raise ValueError("Cần ít nhất 10 tên miền chính thức.")
    return result


def domain_skeleton(value: str) -> str:
    """Đưa Unicode confusable/zero-width về skeleton Latin để so sánh heuristic."""
    decoded = unicode_host(value)
    decoded = _ZERO_WIDTH_RE.sub("", decoded)
    normalized = unicodedata.normalize("NFKD", decoded).translate(_CONFUSABLES).casefold()
    return "".join(char for char in normalized if not unicodedata.combining(char))


def levenshtein(left: str, right: str) -> int:
    """Khoảng cách edit Levenshtein, dùng bộ nhớ O(min(n,m))."""
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, 1):
        current = [index]
        for right_index, right_char in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _brand_label(host: str) -> str:
    labels = domain_skeleton(host).split(".")
    if len(labels) >= 3 and labels[-2:] == ["com", "vn"]:
        return labels[-3]
    return labels[-2] if len(labels) >= 2 else labels[0]


def _has_mixed_scripts(value: str) -> bool:
    scripts = set()
    for char in unicode_host(value):
        if not char.isalpha():
            continue
        name = unicodedata.name(char, "")
        for script in ("LATIN", "CYRILLIC", "GREEK"):
            if script in name:
                scripts.add(script)
    return len(scripts) > 1


def detect_spoofed_domain(
    host: str,
    official_domains: list[dict[str, str]],
) -> list[DomainWarning]:
    """Phát hiện IDN/confusable/edit-distance; chỉ trả cảnh báo có lý do."""
    raw_host = host.lower().strip(".")
    clean_host = _ZERO_WIDTH_RE.sub("", unicode_host(raw_host))
    ascii_host = _idna_host(clean_host)
    official = [(item["brand"], item["domain"].lower().strip(".")) for item in official_domains]
    suspicious_encoding = bool(
        "xn--" in raw_host or _ZERO_WIDTH_RE.search(raw_host) or _has_mixed_scripts(clean_host)
    )
    if not suspicious_encoding and any(
        ascii_host == domain or ascii_host.endswith("." + domain) for _, domain in official
    ):
        return []

    warnings: list[DomainWarning] = []
    if "xn--" in raw_host:
        warnings.append(DomainWarning("punycode", "Tên miền dùng mã Punycode/IDN; cần kiểm tra kỹ ký tự hiển thị."))
    if _ZERO_WIDTH_RE.search(raw_host):
        warnings.append(DomainWarning("zero_width", "Tên miền chứa ký tự vô hình có thể làm người đọc nhầm."))
    if _has_mixed_scripts(clean_host):
        warnings.append(DomainWarning("mixed_script", "Tên miền trộn nhiều hệ chữ Latin/Cyrillic/Greek."))

    target_skeleton = domain_skeleton(clean_host)
    target_label = _brand_label(clean_host).replace("-", "")
    for brand, domain in official:
        official_skeleton = domain_skeleton(domain)
        official_label = _brand_label(domain).replace("-", "")
        if official_skeleton in target_skeleton and not (
            ascii_host == domain or ascii_host.endswith("." + domain)
        ):
            warnings.append(
                DomainWarning(
                    "subdomain_deception",
                    f"Tên miền có chèn “{domain}” nhưng không thực sự thuộc tên miền chính thức.",
                    domain,
                )
            )
            break
        distance = levenshtein(target_label, official_label)
        threshold = 1 if len(official_label) < 8 else 2
        if target_label != official_label and distance <= threshold:
            warnings.append(
                DomainWarning(
                    "lookalike",
                    f"Phần tên gần giống {brand} ({domain}), chỉ khác {distance} ký tự.",
                    domain,
                )
            )
            break
        if target_label == official_label and not target_skeleton.endswith(official_skeleton):
            warnings.append(
                DomainWarning(
                    "suffix_deception",
                    f"Tên thương hiệu giống {brand} nhưng đuôi miền không phải {domain}.",
                    domain,
                )
            )
            break
    # Giữ warning duy nhất theo code để payload gọn.
    unique: dict[str, DomainWarning] = {}
    for warning in warnings:
        unique.setdefault(warning.code, warning)
    return list(unique.values())[:3]


def analyze_links(
    text: str,
    *,
    official_domains: list[dict[str, str]] | None = None,
    resolve_shorteners: bool = True,
    request_get: Callable[..., Any] = requests.get,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> list[LinkAnalysis]:
    """Phân tích toàn bộ URL; lỗi từng link trở thành warning, không ném ra route."""
    domains = official_domains if official_domains is not None else load_legit_domains()
    analyses: list[LinkAnalysis] = []
    for source in extract_urls(text)[:5]:
        try:
            normalized = normalize_url(source)
            original_host = urlsplit(normalized).hostname or ""
        except (ValueError, UnsafeUrlError) as exc:
            analyses.append(
                LinkAnalysis(source, "", "", "", "", False, [DomainWarning("malformed", str(exc))])
            )
            continue
        final_url = normalized
        resolved = False
        warnings = detect_spoofed_domain(original_host, domains)
        if original_host in SHORTENER_DOMAINS:
            warnings.append(DomainWarning("shortener", "Đường dẫn rút gọn đang che tên miền đích."))
            if resolve_shorteners:
                try:
                    final_url, resolved = resolve_redirects(
                        normalized, request_get=request_get, resolver=resolver
                    )
                except (requests.RequestException, ValueError, UnsafeUrlError) as exc:
                    warnings.append(
                        DomainWarning("resolve_failed", f"Không thể giải đường dẫn an toàn: {exc}")
                    )
        final_host = urlsplit(final_url).hostname or original_host
        if final_host != original_host:
            warnings.extend(detect_spoofed_domain(final_host, domains))
        unique: dict[str, DomainWarning] = {}
        for warning in warnings:
            unique.setdefault(warning.code, warning)
        analyses.append(
            LinkAnalysis(
                source_url=source,
                normalized_url=normalized,
                original_domain=unicode_host(original_host),
                final_url=final_url,
                final_domain=unicode_host(final_host),
                resolved=resolved,
                warnings=list(unique.values())[:4],
            )
        )
    return analyses
