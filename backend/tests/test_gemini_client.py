"""Test client HTTP Gemini — quan trọng nhất (L1-03).

Kiểm tra: payload gửi đúng, bóc text đúng, xử lý lỗi mạng/HTTP/parse/cấu hình.
"""
from __future__ import annotations

import pytest

from app.services import gemini
from app.services.gemini import GeminiError, generate_text


class _CapturingPost:
    """Fake requests.post ghi lại payload gửi đi."""

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.captured = None

    def __call__(self, url, json=None, timeout=None, **kwargs):
        self.captured = {"url": url, "json": json, "timeout": timeout}
        return self

    def json(self):
        return self._payload


def _ok(text="OK"):
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }


def test_generate_text_returns_extracted_text(monkeypatch):
    fake = _CapturingPost(_ok("Tin này có dấu hiệu lừa đảo."))
    monkeypatch.setattr(gemini.requests, "post", fake)
    out = generate_text(api_key="k", model="gemini-3.1-flash-lite", user_prompt="hi")
    assert out == "Tin này có dấu hiệu lừa đảo."


def test_generate_text_sends_correct_payload(monkeypatch):
    """Verify request payload đúng: model trong URL, contents đúng cấu trúc."""
    fake = _CapturingPost(_ok("x"))
    monkeypatch.setattr(gemini.requests, "post", fake)
    generate_text(
        api_key="MYKEY", model="gemini-3.1-flash-lite",
        user_prompt="tin nhắn mẫu", system_prompt="bạn là thám tử",
    )
    assert "gemini-3.1-flash-lite" in fake.captured["url"]
    assert "MYKEY" in fake.captured["url"]
    body = fake.captured["json"]
    assert body["contents"][0]["parts"][0]["text"] == "tin nhắn mẫu"
    assert body["system_instruction"]["parts"][0]["text"] == "bạn là thám tử"


def test_generate_text_raises_when_no_api_key():
    with pytest.raises(GeminiError):
        generate_text(api_key="", model="m", user_prompt="hi")


def test_generate_text_handles_network_error(monkeypatch):
    import requests as real_requests

    def _boom(*a, **k):
        raise real_requests.ConnectionError("down")

    monkeypatch.setattr(gemini.requests, "post", _boom)
    with pytest.raises(GeminiError):
        generate_text(api_key="k", model="m", user_prompt="hi")


def test_generate_text_handles_gemini_error_field(monkeypatch):
    """Gemini trả {error: {...}} → phải ném GeminiError."""
    fake = _CapturingPost({"error": {"message": "API key invalid"}})
    monkeypatch.setattr(gemini.requests, "post", fake)
    with pytest.raises(GeminiError, match="API key invalid"):
        generate_text(api_key="k", model="m", user_prompt="hi")


def test_generate_text_empty_payload_returns_empty_string(monkeypatch):
    fake = _CapturingPost({"candidates": []})  # không có text
    monkeypatch.setattr(gemini.requests, "post", fake)
    assert generate_text(api_key="k", model="m", user_prompt="hi") == ""


def test_extract_text_helper():
    assert gemini._extract_text({"candidates": [{"content": {"parts": [{"text": "a"}]}}]}) == "a"
    assert gemini._extract_text({}) == ""
    assert gemini._extract_text({"candidates": []}) == ""


def test_parse_json_lenient_pure_json():
    assert gemini._parse_json_lenient('{"a": 1}') == {"a": 1}


def test_parse_json_lenient_with_surrounding_text():
    out = gemini._parse_json_lenient('Đây kết quả: {"risk": "nguy_hiem"}. Xong.')
    assert out == {"risk": "nguy_hiem"}


def test_parse_json_lenient_empty():
    assert gemini._parse_json_lenient("") == {}


def test_parse_json_lenient_garbage():
    assert gemini._parse_json_lenient("không phải json") == {}
