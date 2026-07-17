from app.services.cache import TTLHashCache, build_cache_key
from app.services.storage import SQLiteStore


def test_cache_key_uses_model_and_pipeline_version_without_plaintext():
    key = build_cache_key("Tin bí mật", model="m1")
    assert len(key) == 64
    assert "Tin" not in key
    assert key != build_cache_key("Tin bí mật", model="m2")
    assert key != build_cache_key("Tin khác", model="m1")


def test_ttl_expiry_lru_capacity_and_defensive_copy():
    now = [0.0]
    cache = TTLHashCache(capacity=2, ttl_seconds=10, clock=lambda: now[0])
    cache.put("a", {"value": [1]})
    cache.put("b", {"value": [2]})
    value = cache.get("a")
    value["value"].append(9)
    assert cache.get("a") == {"value": [1]}
    cache.put("c", {"value": [3]})
    assert cache.get("b") is None
    now[0] = 11
    assert cache.get("a") is None


def test_sqlite_cache_survives_store_restart_and_expires(tmp_path):
    now = [100.0]
    path = str(tmp_path / "persistent-cache.sqlite3")
    first = SQLiteStore(path, capacity=2, ttl_seconds=10, clock=lambda: now[0])
    first.put("a", {"value": [1]})
    second = SQLiteStore(path, capacity=2, ttl_seconds=10, clock=lambda: now[0])
    value = second.get("a")
    value["value"].append(9)
    assert second.get("a") == {"value": [1]}
    now[0] = 111.0
    assert second.get("a") is None


def test_duplicate_check_returns_cache_without_second_ai_call(client, monkeypatch):
    import app.routes.check as route

    calls = []
    detective = {
        "risk_level": "an_toan",
        "reason": "Không có yêu cầu rủi ro.",
        "red_flags": [],
        "actions": ["A", "B", "C"],
    }
    monkeypatch.setattr(
        route, "generate_function_call",
        lambda **kwargs: (calls.append(1) or "complete_detective", detective),
    )
    first = client.post("/api/check", json={"text": "Thông báo lịch hẹn lúc 9 giờ."}).get_json()
    second = client.post("/api/check", json={"text": "Thông báo lịch hẹn lúc 9 giờ."}).get_json()
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert first["orchestration"]["metrics"]["actual_ai_calls"] == 1
    assert second["orchestration"]["metrics"]["actual_ai_calls"] == 0
    assert len(calls) == 1


def test_transient_psychologist_failure_is_not_cached(client, monkeypatch):
    import app.routes.check as route
    from app.services.gemini import GeminiError

    calls = []
    detective = {
        "risk_level": "nghi_ngo", "reason": "Mơ hồ", "red_flags": [],
        "actions": ["A", "B", "C"],
    }
    monkeypatch.setattr(route, "generate_function_call", lambda **kwargs: (calls.append(1) or "handoff_to_psychologist", detective))
    monkeypatch.setattr(route, "generate_json", lambda **kwargs: (_ for _ in ()).throw(GeminiError("down")))
    text = "Thông báo đáng ngờ cần kiểm tra thêm."
    assert client.post("/api/check", json={"text": text}).get_json()["cache"]["hit"] is False
    assert client.post("/api/check", json={"text": text}).get_json()["cache"]["hit"] is False
    assert len(calls) == 2
