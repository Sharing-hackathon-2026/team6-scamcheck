"""Test nhật ký AI theo phiên L1-08."""
from __future__ import annotations

from app.services.audit import append_ai_log, get_ai_log, summarize_result


def test_summarize_result_uses_only_risk_level():
    assert summarize_result({"risk_level": "nguy_hiem", "reason": "bí mật"}) == "Mức rủi ro: nguy hiem"


def test_append_log_caps_at_ten_and_keeps_metadata():
    session = {}
    for _ in range(12):
        append_ai_log(session, 30, {"risk_level": "nghi_ngo"})
    logs = get_ai_log(session)
    assert len(logs) == 10
    assert logs[0]["input_length"] == 30
    assert "at" in logs[0]


def test_get_log_handles_corrupt_session_value():
    assert get_ai_log({"ai_call_log": "bad"}) == []
