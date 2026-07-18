"""Session AI history and exe.dev-authenticated universal admin exports."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

from flask import Blueprint, Response, current_app, jsonify, redirect, request, session

bp = Blueprint("ai_logs", __name__)


def _login_url(redirect_path: str = "/history.html?scope=all") -> str:
    origin = str(current_app.config["ADMIN_AUTH_ORIGIN"]).rstrip("/")
    return f"{origin}/__exe.dev/login?redirect={quote(redirect_path, safe='')}"


def _request_port() -> int | None:
    try:
        return urlsplit(f"//{request.host}").port
    except ValueError:
        return None


def _admin_email() -> tuple[str | None, Response | None]:
    """Trust exe.dev identity only on the dedicated :8001 proxy origin."""
    if _request_port() != int(current_app.config["ADMIN_PROXY_PORT"]):
        response = jsonify({
            "error": "Chế độ quản trị chỉ hoạt động qua cổng đăng nhập exe.dev :8001.",
            "login_url": _login_url(),
        })
        response.status_code = 403
        return None, response
    email = str(request.headers.get("X-ExeDev-Email", "")).strip().casefold()
    user_id = str(request.headers.get("X-ExeDev-UserID", "")).strip()
    if not email or not user_id:
        response = jsonify({
            "error": "Bác cần đăng nhập exe.dev để xem lịch sử toàn hệ thống.",
            "login_url": _login_url(),
        })
        response.status_code = 401
        return None, response
    allowed = set(current_app.config.get("ADMIN_ALLOWED_EMAILS", ()))
    if email not in allowed:
        response = jsonify({"error": "Tài khoản này không có quyền xem log toàn hệ thống."})
        response.status_code = 403
        return None, response
    return email, None


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.get("/api/ai-logs")
def ai_logs():
    """Self-service session history, or universal stats through exe.dev auth."""
    store = current_app.extensions["sqlite_store"]
    scope = request.args.get("scope", "self")
    admin_email = None
    session_id = None
    include_session_id = False
    if scope == "all":
        admin_email, error = _admin_email()
        if error is not None:
            return _no_store(error)
        include_session_id = True
    else:
        scope = "self"
        session_id = store.session_id(session)

    payload = {
        "scope": scope,
        "admin_email": admin_email,
        "stats": store.log_stats(session_id=session_id),
        "logs": store.list_logs(
            session_id=session_id,
            limit=500,
            include_session_id=include_session_id,
        ),
    }
    return _no_store(jsonify(payload))


def _safe_csv_cell(value: object) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


@bp.get("/api/ai-logs/export")
def export_ai_logs():
    """Download retained history; always requires allowlisted exe.dev login."""
    email, error = _admin_email()
    if error is not None:
        if error.status_code == 401:
            fmt = request.args.get("format", "json").casefold()
            target = f"/api/ai-logs/export?format={'csv' if fmt == 'csv' else 'json'}"
            return redirect(_login_url(target), code=302)
        return _no_store(error)

    store = current_app.extensions["sqlite_store"]
    logs = store.list_logs(limit=None, include_session_id=True)
    stats = store.log_stats()
    fmt = request.args.get("format", "json").casefold()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if fmt == "csv":
        output = io.StringIO(newline="")
        fields = [
            "id", "session_id", "at", "actor", "status",
            "risk_level", "input_length", "summary", "prompt", "verdict",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in logs:
            writer.writerow({key: _safe_csv_cell(item.get(key)) for key in fields})
        response = Response(output.getvalue(), content_type="text/csv; charset=utf-8")
        response.headers["Content-Disposition"] = (
            f'attachment; filename="scamcheck-ai-logs-{stamp}.csv"'
        )
        return _no_store(response)

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "all",
        "admin_email": email,
        "stats": stats,
        "logs": logs,
    }
    response = Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response.headers["Content-Disposition"] = (
        f'attachment; filename="scamcheck-ai-logs-{stamp}.json"'
    )
    return _no_store(response)
