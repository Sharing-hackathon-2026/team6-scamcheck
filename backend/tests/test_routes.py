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


def test_check_returns_structured_detective_without_session_limit(client, mock_gemini_text):
    import json

    mock_gemini_text["payload"] = {"candidates": [{"content": {"parts": [{"text": json.dumps(_structured())}]}}]}
    response = client.post("/api/check", json={"text": "Vui lòng gửi mã OTP ngay"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["detective"]["risk_level"] == "nguy_hiem"
    assert data["detective"]["red_flags"][0]["excerpt"] == "mã OTP"
    assert data["technical_analysis"]["rule_signals"]
    assert data["cache"]["hit"] is False
    assert "usage" not in data
    assert data["psychologist_status"] == "unavailable"
    assert mock_gemini_text["last_body"]["generationConfig"]["response_mime_type"] == "application/json"
    response_schema = mock_gemini_text["last_body"]["generationConfig"]["response_schema"]
    assert "additionalProperties" not in response_schema
    system_text = mock_gemini_text["last_body"]["system_instruction"]["parts"][0]["text"]
    assert "TIN_NHAN_KHONG_TIN_CAY" in system_text


def test_check_uses_parser_fallback_for_bad_ai_json(client, mock_gemini_text):
    mock_gemini_text["payload"] = {"candidates": [{"content": {"parts": [{"text": "not JSON"}]}}]}
    response = client.post("/api/check", json={"text": "Bấm link nhận thưởng"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["detective"]["risk_level"] == "nghi_ngo"
    assert len(data["detective"]["actions"]) == 3


def test_check_conservative_guard_rejects_ai_safe_label_for_otp(client, mock_gemini_text):
    import json

    mock_gemini_text["payload"] = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(_structured("an_toan"))}]}}]
    }
    response = client.post("/api/check", json={"text": "Hãy gửi mã OTP ngay"})
    assert response.status_code == 200
    assert response.get_json()["detective"]["risk_level"] == "nguy_hiem"


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
    response = client.post("/api/check", json={"text": "hãy gửi otp"})
    assert response.status_code == 502
    assert len(client.get("/api/check/log").get_json()["logs"]) == 1


def test_log_contains_only_metadata(client, mock_gemini_text):
    import json

    mock_gemini_text["payload"] = {"candidates": [{"content": {"parts": [{"text": json.dumps(_structured("an_toan"))}]}}]}
    client.post("/api/check", json={"text": "Nội dung nhạy cảm bí mật"})
    data = client.get("/api/check/log").get_json()
    assert len(data["logs"]) == 1
    assert data["logs"][0]["input_length"] == len("Nội dung nhạy cảm bí mật")
    assert "Nội dung nhạy cảm" not in str(data["logs"])


def test_legacy_cookie_logs_do_not_block_new_sqlite_analysis(client, mock_gemini_text):
    import json

    with client.session_transaction() as session:
        session["ai_call_log"] = [{"at": "x", "input_length": 1, "summary": "x"}] * 10
    mock_gemini_text["payload"] = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(_structured("an_toan"))}]}}]
    }
    response = client.post("/api/check", json={"text": "Thông báo không yêu cầu thao tác."})
    assert response.status_code == 200
    assert mock_gemini_text["calls"] == 1
    assert len(client.get("/api/check/log").get_json()["logs"]) == 1


def test_health_reports_not_ready_without_key(monkeypatch, tmp_path):
    from app import create_app
    from app.config import Config

    class NoKeyConfig(Config):
        GEMINI_API_KEY = ""
        CORS_ORIGINS = []
        SQLITE_PATH = str(tmp_path / "no-key.sqlite3")

    app = create_app(NoKeyConfig)
    app.config["TESTING"] = True
    with app.test_client() as client:
        assert client.get("/api/health").get_json()["ready"] is False


def test_production_default_does_not_emit_wildcard_cors(client):
    response = client.get("/api/health", headers={"Origin": "https://untrusted.example"})
    assert "Access-Control-Allow-Origin" not in response.headers
