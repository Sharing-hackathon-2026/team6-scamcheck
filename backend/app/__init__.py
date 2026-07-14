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
    app.config["AI_CALL_LIMIT"] = config.AI_CALL_LIMIT

    # CORS: bật khi dev tách port. Prod (Nginx cùng origin) không cần.
    if config.CORS_ORIGINS:
        CORS(app, origins=config.CORS_ORIGINS)
    else:
        CORS(app)  # permissive theo mặc định cho dev; chặn lại bằng Nginx khi prod.

    # Đăng ký blueprints.
    from .routes import register_blueprints

    register_blueprints(app)
    return app
