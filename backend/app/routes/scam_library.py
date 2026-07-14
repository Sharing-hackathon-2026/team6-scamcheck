"""GET /api/scam-library — dữ liệu tĩnh, không gọi AI."""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..services.scam_library import load_scam_library

bp = Blueprint("scam_library", __name__)


@bp.get("/api/scam-library")
def scam_library():
    return jsonify(load_scam_library())
