"""Flask application factory.

Backend là REST API thuần (trả JSON), KHÔNG render HTML.
Mọi endpoint nằm dưới tiền tố /api/*.
"""
from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from .config import Config


def create_app(cfg: Config | None = None) -> Flask:
    """Tạo và cấu hình Flask app.

    Args:
        cfg: đối tượng Config tuỳ chọn (dùng cho test). Nếu None, dùng Config mặc định đọc env.
    """
    app = Flask(__name__)
    config = cfg or Config
    app.config["GEMINI_API_KEY"] = config.GEMINI_API_KEY
    app.config["GEMINI_MODEL"] = config.GEMINI_MODEL
    app.config["SECRET_KEY"] = config.FLASK_SECRET_KEY
    app.config["MAX_INPUT_LENGTH"] = config.MAX_INPUT_LENGTH
    app.config["BASE_URL"] = config.BASE_URL
    app.config["CHECK_CACHE_CAPACITY"] = config.CHECK_CACHE_CAPACITY
    app.config["CHECK_CACHE_TTL"] = config.CHECK_CACHE_TTL

    from .services.cache import TTLHashCache

    app.extensions["check_cache"] = TTLHashCache(
        capacity=config.CHECK_CACHE_CAPACITY,
        ttl_seconds=config.CHECK_CACHE_TTL,
    )

    # CORS chỉ bật khi khai báo rõ cho dev tách port. Prod cùng origin không gửi wildcard.
    if config.CORS_ORIGINS:
        CORS(app, origins=config.CORS_ORIGINS)

    # Đăng ký blueprints.
    from .routes import register_blueprints

    register_blueprints(app)
    return app
