"""AI history API, SQLite scoping, and exe.dev admin authorization."""
from __future__ import annotations


def _seed(client):
    store = client.application.extensions["sqlite_store"]
    first = "a" * 32
    second = "b" * 32
    store.append_log(
        session_id=first, input_length=12, summary="Mức rủi ro: an toan",
        actor="detective", status="complete", risk_level="an_toan",
    )
    store.append_log(
        session_id=first, input_length=12, summary="Đã giải thích",
        actor="psychologist", status="complete", risk_level="an_toan",
    )
    store.append_log(
        session_id=second, input_length=20, summary="Mức rủi ro: nguy hiem",
        actor="detective", status="complete", risk_level="nguy_hiem",
    )
    return first, second


def test_ordinary_history_only_returns_current_session(client):
    first, _ = _seed(client)
    with client.session_transaction() as state:
        state["scamcheck_session_id"] = first
    response = client.get("/api/ai-logs")
    data = response.get_json()
    assert response.status_code == 200
    assert response.headers["Cache-Control"].startswith("no-store")
    assert data["scope"] == "self"
    assert data["stats"]["ai_calls"] == 2
    assert data["stats"]["checks"] == 1
    assert data["stats"]["risk_counts"]["an_toan"] == 1
    assert len(data["logs"]) == 2
    assert "session_id" not in data["logs"][0]


def test_universal_history_requires_port_8001_and_allowlisted_exedev_email(client):
    _seed(client)
    wrong_port = client.get(
        "/api/ai-logs?scope=all",
        headers={"X-ExeDev-Email": "admin@example.com"},
    )
    assert wrong_port.status_code == 403
    assert ":8001" in wrong_port.get_json()["login_url"]

    missing = client.get(
        "/api/ai-logs?scope=all",
        base_url="https://team6-scamcheck.exe.xyz:8001",
    )
    assert missing.status_code == 401
    assert "/__exe.dev/login?redirect=" in missing.get_json()["login_url"]

    denied = client.get(
        "/api/ai-logs?scope=all",
        base_url="https://team6-scamcheck.exe.xyz:8001",
        headers={"X-ExeDev-Email": "other@example.com", "X-ExeDev-UserID": "usr-other"},
    )
    assert denied.status_code == 403

    allowed = client.get(
        "/api/ai-logs?scope=all",
        base_url="https://team6-scamcheck.exe.xyz:8001",
        headers={"X-ExeDev-Email": "ADMIN@example.com", "X-ExeDev-UserID": "usr-admin"},
    )
    data = allowed.get_json()
    assert allowed.status_code == 200
    assert data["scope"] == "all"
    assert data["admin_email"] == "admin@example.com"
    assert data["stats"]["ai_calls"] == 3
    assert {item["session_id"] for item in data["logs"]} == {"a" * 32, "b" * 32}


def test_admin_can_export_full_json_and_csv_but_public_cannot(client):
    _seed(client)
    login = client.get(
        "/api/ai-logs/export?format=json",
        base_url="https://team6-scamcheck.exe.xyz:8001",
    )
    assert login.status_code == 302
    assert "/__exe.dev/login?redirect=" in login.headers["Location"]

    headers = {"X-ExeDev-Email": "admin@example.com", "X-ExeDev-UserID": "usr-admin"}
    exported_json = client.get(
        "/api/ai-logs/export?format=json",
        base_url="https://team6-scamcheck.exe.xyz:8001",
        headers=headers,
    )
    assert exported_json.status_code == 200
    assert "attachment" in exported_json.headers["Content-Disposition"]
    assert exported_json.get_json()["stats"]["checks"] == 2

    exported_csv = client.get(
        "/api/ai-logs/export?format=csv",
        base_url="https://team6-scamcheck.exe.xyz:8001",
        headers=headers,
    )
    assert exported_csv.status_code == 200
    assert "text/csv" in exported_csv.content_type
    assert "session_id" in exported_csv.get_data(as_text=True).splitlines()[0]
