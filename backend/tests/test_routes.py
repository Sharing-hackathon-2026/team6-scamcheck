"""Test các route API structured của L1."""
from __future__ import annotations


def _structured(risk_level="nguy_hiem"):
    return {
        "risk_level": risk_level,
        "reason": "Tin yêu cầu mã OTP.",
        "red_flags": [{"label": "OTP", "excerpt": "mã OTP", "explanation": "Không ai được xin OTP."}],
        "actions": ["Không gửi OTP.", "Gọi ngân hàng.", "Chặn tin nhắn."],
    }


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_check_returns_structured_detective_and_usage(client, mock_gemini_text):
    import json

    mock_gemini_text["payload"] = {"candidates": [{"content": {"parts": [{"text": json.dumps(_structured())}]}}]}
    response = client.post("/api/check", json={"text": "Vui lòng gửi mã OTP ngay"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["detective"]["risk_level"] == "nguy_hiem"
    assert data["detective"]["red_flags"][0]["excerpt"] == "mã OTP"
    assert data["usage"] == {"calls_used": 1, "call_limit": 10}
    assert mock_gemini_text["last_body"]["generationConfig"]["response_mime_type"] == "application/json"


def test_check_uses_parser_fallback_for_bad_ai_json(client, mock_gemini_text):
    mock_gemini_text["payload"] = {"candidates": [{"content": {"parts": [{"text": "not JSON"}]}}]}
    response = client.post("/api/check", json={"text": "Bấm link nhận thưởng"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["detective"]["risk_level"] == "nghi_ngo"
    assert len(data["detective"]["actions"]) == 3


def test_check_rejects_empty_and_too_long_without_ai(client, mock_gemini_text):
    assert client.post("/api/check", json={"text": ""}).status_code == 400
    assert client.post("/api/check", json={"text": "a" * 5001}).status_code == 400
    assert mock_gemini_text["calls"] == 0


def test_check_returns_502_on_gemini_error(client, monkeypatch):
    import app.services.gemini as gemini_mod

    class Response:
        status_code = 400
        def json(self):
            return {"error": {"message": "invalid"}}

    monkeypatch.setattr(gemini_mod.requests, "post", lambda *a, **k: Response())
    assert client.post("/api/check", json={"text": "hãy gửi otp"}).status_code == 502


def test_log_contains_only_metadata(client, mock_gemini_text):
    import json

    mock_gemini_text["payload"] = {"candidates": [{"content": {"parts": [{"text": json.dumps(_structured("an_toan"))}]}}]}
    client.post("/api/check", json={"text": "Nội dung nhạy cảm bí mật"})
    data = client.get("/api/check/log").get_json()
    assert data["calls_used"] == 1
    assert data["logs"][0]["input_length"] == len("Nội dung nhạy cảm bí mật")
    assert "Nội dung nhạy cảm" not in str(data["logs"])


def test_call_limit_blocks_ai(client, mock_gemini_text):
    with client.session_transaction() as session:
        session["ai_call_log"] = [{"at": "x", "input_length": 1, "summary": "x"}] * 10
    response = client.post("/api/check", json={"text": "Gửi OTP"})
    assert response.status_code == 429
    assert response.get_json()["code"] == "ai_call_limit_reached"
    assert mock_gemini_text["calls"] == 0


def test_health_reports_not_ready_without_key(monkeypatch):
    from app import create_app
    from app.config import Config

    class NoKeyConfig(Config):
        GEMINI_API_KEY = ""
        CORS_ORIGINS = []

    app = create_app(NoKeyConfig)
    app.config["TESTING"] = True
    with app.test_client() as client:
        assert client.get("/api/health").get_json()["ready"] is False
