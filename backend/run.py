"""Entrypoint dev: chạy Flask trực tiếp ở :5000.

    python backend/run.py

Tự nạp .env từ backend/.env hoặc scamcheck/.env (không nạp khi test).
Prod dùng gunicorn (xem deploy/scamcheck-backend.service).
"""
from __future__ import annotations

import os
from pathlib import Path

# Nạp .env (dev). Bỏ qua nếu thiếu dotenv.
try:
    from dotenv import load_dotenv

    for candidate in (Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate)
            break
except ImportError:
    pass

from app import create_app
from app.config import Config

app = create_app(Config)


# Dev tiện lợi: phục vụ frontend/ từ chính backend ở cùng origin :5000.
# Prod KHÔNG dùng phần này (Nginx phục vụ frontend riêng).
import os
from flask import send_from_directory

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.route("/")
def _dev_index():
    return send_from_directory(_FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def _dev_static(path):
    # Chỉ phục vụ file thật trong frontend/; /api/* vẫn do blueprint xử lý.
    full = os.path.join(_FRONTEND_DIR, path)
    if os.path.isfile(full):
        return send_from_directory(_FRONTEND_DIR, path)
    return send_from_directory(_FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
