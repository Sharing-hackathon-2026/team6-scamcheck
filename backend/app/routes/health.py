"""Health check endpoint — dùng cho Nginx healthcheck & giám sát."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    """Trả trạng thái sống của backend."""
    return jsonify({"ok": True, "ready": bool(current_app.config.get("GEMINI_API_KEY"))})
