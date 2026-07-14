"""Đăng ký tất cả route blueprints, đều nằm dưới /api."""
from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from .health import bp as health_bp
    from .check import bp as check_bp

    from .scam_library import bp as scam_library_bp
    from .quiz_api import bp as quiz_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(check_bp)
    app.register_blueprint(scam_library_bp)
    app.register_blueprint(quiz_bp)
