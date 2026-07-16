"""API integration cho bốn crisis flow Stage 5."""
from __future__ import annotations

import json

import pytest
import requests

from app.services.rescuer import REQUIRED_STEP_KEYS


def _ai_payload(situation: str, *, phone: str = "") -> dict:
    return {
        "headline": "Bác hãy làm ngay từng bước",
        "reassurance": "Bác bình tĩnh; hành động nhanh vẫn có thể giảm thiệt hại.",
        "steps": [
            {
                "step_key": key,
                "action": f"Xử lý {key}" + (f" qua {phone}" if index == 0 and phone else ""),
                "detail": "Dùng kênh chính thức và giữ lại bằng chứng.",
                "hotline_ids": ["vietcombank"] if index == 0 else [],
            }
            for index, key in enumerate(REQUIRED_STEP_KEYS[situation])
        ],
        "closing": "Chỉ ngân hàng và cơ quan chức năng mới có quyền xử lý giao dịch.",
    }


def test_hotlines_endpoint_is_static_and_has_review_metadata(client, mock_gemini_text):
    response = client.get("/api/hotlines")
    data = response.get_json()
    assert response.status_code == 200
    assert data["reviewed_at"]
    assert len([item for item in data["entries"] if item["type"] == "bank"]) >= 10
    assert all("aliases" not in item for item in data["entries"])
    assert mock_gemini_text["calls"] == 0


def test_not_acted_flow_praises_and_never_calls_ai(client, mock_gemini_text):
    response = client.post(
        "/api/rescue",
        json={"situation": "chua_lam_gi", "message_text": "Tin giả Vietcombank"},
    )
    data = response.get_json()
    assert response.status_code == 200
    assert data["praise"]
    assert data["rescue_status"] == "not_needed"
    assert data["orchestration"]["state"] == "prevention_complete"
    assert data["orchestration"]["metrics"]["calls_saved"] == 1
    assert mock_gemini_text["calls"] == 0


@pytest.mark.parametrize("situation", ["da_bam_link", "da_chuyen_tien", "da_cung_cap_otp"])
def test_three_impacted_flows_call_rescuer_once_and_return_ordered_steps(
    client, mock_gemini_text, situation
):
    mock_gemini_text["payload"] = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(_ai_payload(situation), ensure_ascii=False)}]}}
        ]
    }
    before = mock_gemini_text["calls"]
    response = client.post(
        "/api/rescue",
        json={
            "situation": situation,
            "message_text": "Tin nhắn giả Vietcombank yêu cầu xử lý",
            "risk_level": "nguy_hiem",
            "red_flags": [{"label": "Yêu cầu OTP"}],
        },
    )
    data = response.get_json()
    assert response.status_code == 200
    assert mock_gemini_text["calls"] == before + 1
    assert data["rescue_status"] == "complete"
    assert data["matched_institutions"] == ["Vietcombank"]
    assert [item["key"] for item in data["rescue"]["steps"]] == list(
        REQUIRED_STEP_KEYS[situation]
    )
    assert data["orchestration"]["state"] == "rescue_complete"
    assert data["call_savings_baseline"]["reduction_percent"] == 25.0


def test_client_red_flag_labels_are_not_forwarded_to_rescuer_prompt(client, mock_gemini_text):
    raw = _ai_payload("da_bam_link")
    mock_gemini_text["payload"] = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(raw, ensure_ascii=False)}]}}]
    }
    response = client.post(
        "/api/rescue",
        json={
            "situation": "da_bam_link",
            "message_text": "SECRET_MESSAGE_Vietcombank",
            "red_flags": [{"label": "STK riêng tư 123456789"}],
        },
    )
    assert response.status_code == 200
    assert "STK riêng tư" not in json.dumps(mock_gemini_text["last_body"], ensure_ascii=False)
    assert "SECRET_MESSAGE" not in json.dumps(mock_gemini_text["last_body"], ensure_ascii=False)


def test_route_rejects_hallucinated_phone_and_uses_fixed_playbook_with_matched_bank(client, mock_gemini_text):
    raw = _ai_payload("da_chuyen_tien", phone="0909 123 456")
    raw["steps"][0]["hotline_ids"] = ["vietcombank"]
    mock_gemini_text["payload"] = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(raw, ensure_ascii=False)}]}}]
    }
    data = client.post(
        "/api/rescue",
        json={"situation": "da_chuyen_tien", "message_text": "VCB"},
    ).get_json()
    first = data["rescue"]["steps"][0]
    assert data["rescue_status"] == "guarded_fallback"
    assert "0909 123 456" not in first["action"]
    assert first["hotlines"][0]["phone"] == "1900 54 54 13"


def test_rescuer_kill_switch_keeps_deterministic_crisis_steps_without_ai(client, mock_gemini_text):
    client.application.config["RESCUE_AI_ENABLED"] = False
    response = client.post(
        "/api/rescue",
        json={"situation": "da_chuyen_tien", "message_text": "Vietcombank"},
    )
    data = response.get_json()
    assert response.status_code == 200
    assert data["rescue_status"] == "guarded_fallback"
    assert data["orchestration"]["metrics"]["actual_ai_calls"] == 0
    assert data["rescue"]["steps"][0]["hotlines"][0]["phone"] == "1900 54 54 13"
    assert mock_gemini_text["calls"] == 0


def test_ai_network_failure_still_returns_safe_fixed_playbook(client, monkeypatch):
    import app.services.gemini as gemini_mod

    def fail(*args, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(gemini_mod.requests, "post", fail)
    response = client.post(
        "/api/rescue",
        json={"situation": "da_cung_cap_otp", "message_text": "ACB"},
    )
    data = response.get_json()
    assert response.status_code == 200
    assert data["rescue_status"] == "guarded_fallback"
    assert data["rescue"]["is_fallback"] is True
    assert [step["key"] for step in data["rescue"]["steps"]] == list(
        REQUIRED_STEP_KEYS["da_cung_cap_otp"]
    )
    logs = client.get("/api/check/log").get_json()["logs"]
    assert logs[-1]["actor"] == "rescuer"
    assert logs[-1]["status"] == "guarded_fallback"


def test_invalid_or_oversized_crisis_request_never_calls_ai(client, mock_gemini_text):
    assert client.post("/api/rescue", json={"situation": "khac"}).status_code == 400
    assert client.post(
        "/api/rescue",
        json={"situation": "da_bam_link", "message_text": "x" * 5001},
    ).status_code == 400
    assert mock_gemini_text["calls"] == 0
