"""Fixtures dùng chung cho pytest.

- `client`: Flask test client (không cần server thật).
- `mock_gemini_text`: thay requests.post trả phản hồi Gemini giả.
"""
from __future__ import annotations

import pytest

from app import create_app
from app.config import Config


class _TestConfig(Config):
    """Config cố định cho test."""

    GEMINI_API_KEY = "test-key"
    GEMINI_MODEL = "gemini-3.1-flash-lite"
    FLASK_SECRET_KEY = "test-secret"
    CORS_ORIGINS = []


@pytest.fixture()
def client(tmp_path):
    """Flask test client với SQLite riêng cho từng test."""
    class RuntimeTestConfig(_TestConfig):
        SQLITE_PATH = str(tmp_path / "scamcheck-test.sqlite3")
        ADMIN_ALLOWED_EMAILS = ("admin@example.com",)
        ADMIN_AUTH_ORIGIN = "https://team6-scamcheck.exe.xyz:8001"
        ADMIN_PROXY_PORT = 8001

    app = create_app(RuntimeTestConfig)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _gemini_payload(text: str = "Kết quả giả") -> dict:
    """Tạo payload Gemini generateContent giả."""
    return {
        "candidates": [
            {"content": {"parts": [{"text": text}], "role": "model"}, "finishReason": "STOP"}
        ]
    }


@pytest.fixture()
def mock_gemini_text(monkeypatch):
    """Thay requests.post trong module gemini bằng hàm trả payload giả.

    Trả về một đối tượng có `.calls` để test đếm số lần gọi.
    """
    import app.services.gemini as gemini_mod

    state = {"calls": 0, "payload": _gemini_payload(), "raise": None, "last_body": None}

    class _FakeResponse:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def _fake_post(url, json=None, timeout=None, **kwargs):
        state["calls"] += 1
        state["last_body"] = json
        if state["raise"]:
            raise state["raise"]
        payload = state["payload"]
        # Route Stage 3 dùng terminal function call. Fixture cũ vẫn có thể cấp JSON text.
        if json and json.get("tools"):
            try:
                import json as json_module

                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                args = json_module.loads(text)
            except (KeyError, IndexError, TypeError, json_module.JSONDecodeError):
                args = {}
            risk = args.get("risk_level") if isinstance(args, dict) else None
            name = (
                "handoff_to_psychologist"
                if risk in {"nghi_ngo", "nguy_hiem"}
                else "complete_detective"
            )
            payload = {
                "candidates": [
                    {"content": {"parts": [{"functionCall": {"name": name, "args": args}}]}}
                ]
            }
        return _FakeResponse(payload)

    monkeypatch.setattr(gemini_mod.requests, "post", _fake_post)
    return state
