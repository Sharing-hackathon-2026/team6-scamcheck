"""Test SQLite-backed, session-scoped AI metadata audit."""
from __future__ import annotations

from app.services.audit import append_ai_log, get_ai_log, summarize_result
from app.services.storage import SQLiteStore


def _store(tmp_path):
    return SQLiteStore(str(tmp_path / "audit.sqlite3"), log_retention_days=30)


def test_summarize_result_uses_only_risk_level():
    assert summarize_result({"risk_level": "nguy_hiem", "reason": "bí mật"}) == "Mức rủi ro: nguy hiem"


def test_append_log_persists_full_session_history_as_metadata(tmp_path):
    session = {}
    store = _store(tmp_path)
    for _ in range(12):
        append_ai_log(
            session,
            30,
            {"risk_level": "nghi_ngo", "reason": "không được lưu"},
            store=store,
        )
    logs = get_ai_log(session, store=store)
    assert len(logs) == 12
    assert logs[0]["input_length"] == 30
    assert logs[0]["risk_level"] == "nghi_ngo"
    assert "không được lưu" not in str(logs)
    assert "scamcheck_session_id" in session


def test_logs_are_isolated_by_signed_session_identifier(tmp_path):
    store = _store(tmp_path)
    first, second = {}, {}
    append_ai_log(first, 10, {"risk_level": "an_toan"}, store=store)
    append_ai_log(second, 20, {"risk_level": "nguy_hiem"}, store=store)
    assert [item["input_length"] for item in get_ai_log(first, store=store)] == [10]
    assert [item["input_length"] for item in get_ai_log(second, store=store)] == [20]
