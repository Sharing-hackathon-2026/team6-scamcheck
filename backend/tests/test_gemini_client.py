"""Test client HTTP Gemini — JSON mode và retry rate-limit L1-03/L1-05."""
from __future__ import annotations

import pytest

from app.services import gemini
from app.services.gemini import GeminiError, GeminiRateLimitError, generate_json, generate_text


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
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_generate_text_returns_extracted_text(monkeypatch):
    fake = _CapturingPost(_ok("Tin này có dấu hiệu lừa đảo."))
    monkeypatch.setattr(gemini.requests, "post", fake)
    assert generate_text(api_key="k", model="m", user_prompt="hi") == "Tin này có dấu hiệu lừa đảo."


def test_generate_json_sends_json_mode(monkeypatch):
    fake = _CapturingPost(_ok('{"risk_level":"nghi_ngo"}'))
    monkeypatch.setattr(gemini.requests, "post", fake)
    out = generate_json(api_key="MYKEY", model="m", user_prompt="tin", system_prompt="vai")
    assert out == {"risk_level": "nghi_ngo"}
    assert fake.captured["json"]["generationConfig"]["response_mime_type"] == "application/json"
    schema = fake.captured["json"]["generationConfig"]["response_schema"]
    assert "additionalProperties" not in schema
    assert "additionalProperties" not in schema["properties"]["red_flags"]["items"]
    assert schema["required"] == ["risk_level", "reason", "red_flags", "actions"]
    assert fake.captured["json"]["system_instruction"]["parts"][0]["text"] == "vai"


def test_generate_function_call_sends_tools_and_extracts_arguments(monkeypatch):
    payload = _ok()
    payload["candidates"][0]["content"]["parts"] = [
        {"functionCall": {"name": "handoff_to_psychologist", "args": {"risk_level": "nguy_hiem"}}}
    ]
    fake = _CapturingPost(payload)
    monkeypatch.setattr(gemini.requests, "post", fake)
    name, args = gemini.generate_function_call(
        api_key="k",
        model="m",
        user_prompt="tin",
        system_prompt="vai",
        function_declarations=[{"name": "handoff_to_psychologist", "parameters": {"type": "object"}}],
    )
    assert name == "handoff_to_psychologist"
    assert args == {"risk_level": "nguy_hiem"}
    assert fake.captured["json"]["toolConfig"]["functionCallingConfig"]["mode"] == "ANY"
    assert fake.captured["json"]["tools"][0]["functionDeclarations"][0]["name"] == "handoff_to_psychologist"
    assert "generationConfig" not in fake.captured["json"]


def test_generate_function_call_returns_empty_for_missing_call(monkeypatch):
    monkeypatch.setattr(gemini.requests, "post", _CapturingPost(_ok("plain text")))
    assert gemini.generate_function_call(
        api_key="k", model="m", user_prompt="tin", system_prompt="vai", function_declarations=[]
    ) == ("", {})


def test_generate_text_raises_when_no_api_key():
    with pytest.raises(GeminiError):
        generate_text(api_key="", model="m", user_prompt="hi")


def test_generate_text_handles_network_error(monkeypatch):
    import requests as real_requests

    monkeypatch.setattr(gemini.requests, "post", lambda *a, **k: (_ for _ in ()).throw(real_requests.ConnectionError("down")))
    with pytest.raises(GeminiError):
        generate_text(api_key="k", model="m", user_prompt="hi")


def test_generate_text_handles_gemini_error_field(monkeypatch):
    monkeypatch.setattr(gemini.requests, "post", _CapturingPost({"error": {"message": "API key invalid"}}))
    with pytest.raises(GeminiError, match="API key invalid"):
        generate_text(api_key="k", model="m", user_prompt="hi")


def test_retry_429_then_success(monkeypatch):
    class Response:
        def __init__(self, status, payload):
            self.status_code, self.payload = status, payload
        def json(self):
            return self.payload

    responses = [Response(429, {"error": {}}), Response(200, _ok('{"risk_level":"an_toan"}'))]
    calls, sleeps = [], []
    monkeypatch.setattr(gemini.requests, "post", lambda *a, **k: calls.append(1) or responses.pop(0))
    monkeypatch.setattr(gemini.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert generate_json(api_key="k", model="m", user_prompt="hi", max_retries=2) == {"risk_level": "an_toan"}
    assert len(calls) == 2
    assert sleeps == [0.5]


def test_retry_503_exhausted_is_friendly(monkeypatch):
    class Response:
        status_code = 503
        def json(self):
            return {"error": {}}

    monkeypatch.setattr(gemini.requests, "post", lambda *a, **k: Response())
    monkeypatch.setattr(gemini.time, "sleep", lambda seconds: None)
    with pytest.raises(GeminiRateLimitError):
        generate_json(api_key="k", model="m", user_prompt="hi", max_retries=2)


def test_parse_json_lenient_handles_text_and_non_object():
    assert gemini._parse_json_lenient('Đây: {"risk":"nguy_hiem"}.') == {"risk": "nguy_hiem"}
    assert gemini._parse_json_lenient("[]") == {}
    assert gemini._parse_json_lenient("garbage") == {}
