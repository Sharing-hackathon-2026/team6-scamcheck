"""Health check endpoint — dùng cho Nginx healthcheck & giám sát."""
from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    """Trả trạng thái sống của backend."""
    from ..config import is_configured

    return jsonify({"ok": True, "ready": is_configured()})
