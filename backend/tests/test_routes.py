"""Test các route API (Cấp 1): /api/health và /api/check."""
from __future__ import annotations


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_check_returns_text_from_gemini(client, mock_gemini_text):
    """POST /api/check hợp lệ → trả JSON {result: ...}."""
    mock_gemini_text["payload"] = {
        "candidates": [{"content": {"parts": [{"text": "Tin này lừa đảo."}]}}]
    }
    r = client.post("/api/check", json={"text": "Kiếm tiền nhanh"})
    assert r.status_code == 200
    assert r.get_json()["result"] == "Tin này lừa đảo."
    assert mock_gemini_text["calls"] == 1


def test_check_rejects_empty_input(client, mock_gemini_text):
    """L2-08: tin trống → 400, không gọi AI."""
    r = client.post("/api/check", json={"text": ""})
    assert r.status_code == 400
    assert "errors" in r.get_json()
    assert mock_gemini_text["calls"] == 0


def test_check_rejects_missing_text_field(client, mock_gemini_text):
    r = client.post("/api/check", json={})
    assert r.status_code == 400
    assert mock_gemini_text["calls"] == 0


def test_check_rejects_too_long_input(client, mock_gemini_text):
    r = client.post("/api/check", json={"text": "a" * 5001})
    assert r.status_code == 400
    assert mock_gemini_text["calls"] == 0


def test_check_returns_502_on_gemini_error(client, monkeypatch):
    """AI lỗi → 502, không gãy."""
    import app.services.gemini as gemini_mod

    class _FakeResp:
        status_code = 400
        def json(self):
            return {"error": {"message": "invalid"}}

    monkeypatch.setattr(
        gemini_mod.requests, "post", lambda *a, **k: _FakeResp()
    )
    r = client.post("/api/check", json={"text": "hello"})
    assert r.status_code == 502
    assert "error" in r.get_json()


def test_check_handles_network_error(client, monkeypatch):
    """Mất kết nối → 502, không gãy."""
    import requests as real_requests
    import app.services.gemini as gemini_mod

    def _boom(*a, **k):
        raise real_requests.ConnectionError("down")

    monkeypatch.setattr(gemini_mod.requests, "post", _boom)
    r = client.post("/api/check", json={"text": "hello"})
    assert r.status_code == 502


def test_check_without_body_returns_400(client):
    """Không có body JSON → 400, không 500."""
    r = client.post("/api/check", content_type="application/json", data="not json")
    assert r.status_code == 400


def test_health_reports_not_ready_without_key(monkeypatch):
    """Health báo ready=False khi thiếu key."""
    from app import create_app
    from app.config import Config

    class _NoKey(Config):
        GEMINI_API_KEY = ""
        CORS_ORIGINS = []

    app = create_app(_NoKey)
    app.config["TESTING"] = True
    with app.test_client() as c:
        r = c.get("/api/health")
        data = r.get_json()
        assert data["ok"] is True
        assert data["ready"] is False
