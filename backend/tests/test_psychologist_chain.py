"""Test route chain Stage 3: terminal handoff, quota và lỗi độc lập."""
from __future__ import annotations

from app.services.gemini import GeminiError


def _detective(risk: str) -> dict:
    return {
        "risk_level": risk,
        "reason": "Tin tạo áp lực để bác làm theo.",
        "red_flags": [],
        "actions": ["Dừng lại.", "Không cung cấp dữ liệu.", "Kiểm tra chính thức."],
    }


def test_safe_verdict_does_not_call_psychologist(client, monkeypatch):
    import app.routes.check as route

    calls = []
    monkeypatch.setattr(route, "generate_function_call", lambda **kwargs: (calls.append("detective") or "complete_detective", _detective("an_toan")))
    monkeypatch.setattr(route, "generate_json", lambda **kwargs: calls.append("psychologist"))
    data = client.post("/api/check", json={"text": "Thông báo giao hàng không yêu cầu thanh toán."}).get_json()
    assert calls == ["detective"]
    assert data["psychologist"] is None
    assert data["psychologist_status"] == "not_needed"
    assert data["usage"]["calls_used"] == 1


def test_handoff_calls_psychologist_and_returns_two_parts(client, monkeypatch):
    import app.routes.check as route

    calls = []
    monkeypatch.setattr(route, "generate_function_call", lambda **kwargs: (calls.append("detective") or "handoff_to_psychologist", _detective("nghi_ngo")))
    monkeypatch.setattr(route, "generate_json", lambda **kwargs: calls.append("psychologist") or {
        "message": "Cô hiểu lời hối thúc này dễ làm bác vội vàng. Bác hãy dừng lại một chút để bình tĩnh kiểm tra."
    })
    data = client.post("/api/check", json={"text": "Nhận thưởng ngay hôm nay"}).get_json()
    assert calls == ["detective", "psychologist"]
    assert data["psychologist_status"] == "complete"
    assert data["psychologist"]["message"].startswith("Cô hiểu")
    assert data["usage"]["calls_used"] == 2


def test_tool_name_cannot_bypass_server_activation_guardrail(client, monkeypatch):
    import app.routes.check as route

    calls = []
    monkeypatch.setattr(route, "generate_function_call", lambda **kwargs: ("complete_detective", _detective("an_toan")))
    monkeypatch.setattr(route, "generate_json", lambda **kwargs: calls.append("psychologist") or {
        "message": "Cô hiểu yêu cầu mã bí mật dễ khiến bác lo tài khoản bị khóa. Bác hãy dừng lại để kiểm tra."
    })
    data = client.post("/api/check", json={"text": "Gửi mã OTP ngay"}).get_json()
    assert data["detective"]["risk_level"] == "nguy_hiem"
    assert calls == ["psychologist"]


def test_psychologist_failure_keeps_detective_http_200(client, monkeypatch):
    import app.routes.check as route

    monkeypatch.setattr(route, "generate_function_call", lambda **kwargs: ("handoff_to_psychologist", _detective("nguy_hiem")))
    monkeypatch.setattr(route, "generate_json", lambda **kwargs: (_ for _ in ()).throw(GeminiError("down")))
    response = client.post("/api/check", json={"text": "Chuyển tiền phí ngay"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["detective"]["risk_level"] == "nguy_hiem"
    assert data["psychologist"] is None
    assert data["psychologist_status"] == "unavailable"
    assert data["usage"]["calls_used"] == 2


def test_one_remaining_call_returns_detective_and_quota_status(client, monkeypatch):
    import app.routes.check as route

    with client.session_transaction() as state:
        state["ai_call_log"] = [{"at": "x", "input_length": 1, "summary": "x"}] * 9
    monkeypatch.setattr(route, "generate_function_call", lambda **kwargs: ("handoff_to_psychologist", _detective("nghi_ngo")))
    data = client.post("/api/check", json={"text": "Tin đáng ngờ"}).get_json()
    assert data["psychologist_status"] == "quota_reached"
    assert data["usage"] == {"calls_used": 10, "call_limit": 10}
