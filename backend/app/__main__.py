"""Cho phép chạy `python -m app` từ trong thư mục backend/."""
from __future__ import annotations

from . import create_app
from .config import Config

app = create_app(Config)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
