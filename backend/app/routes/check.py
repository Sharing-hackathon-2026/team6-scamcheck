"""POST /api/check — điểm vào chính của Cấp 1.

Nhận văn bản tin nhắn, gọi Gemini, trả kết quả thô (Cấp 1).
Cấp 2+ sẽ trả JSON có cấu trúc (Thám tử); Cấp 1 chỉ trả văn bản thô.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..prompts import STAGE1_SYSTEM_PROMPT
from ..services.gemini import GeminiError, generate_text
from ..services.validation import validate_input

bp = Blueprint("check", __name__)


@bp.post("/api/check")
def check():
    """Phân tích tin nhắn nghi ngờ lừa đảo.

    Request JSON: {"text": "<nội dung tin nhắn>"}
    Response 200 JSON:
        {"result": "<văn bản thô từ AI>"}        (Cấp 1)
        Cấp 2+: {"detective": {...}, "psychologist": {...}}
    Response 400 JSON: {"errors": ["..."]}
    Response 502 JSON: {"error": "..."}          (Lỗi gọi AI)
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")

    # L2-08: validate đầu vào trước khi gọi AI.
    errors = validate_input(text, max_len=current_app.config["MAX_INPUT_LENGTH"])
    if errors:
        return jsonify({"errors": errors}), 400

    api_key = current_app.config["GEMINI_API_KEY"]
    model = current_app.config["GEMINI_MODEL"]

    try:
        result = generate_text(
            api_key=api_key,
            model=model,
            user_prompt=text,
            system_prompt=STAGE1_SYSTEM_PROMPT,
        )
    except GeminiError as exc:
        # Lỗi gọi AI: trả 502 + thông báo thân thiện, KHÔNG gãy.
        return jsonify({"error": str(exc)}), 502

    return jsonify({"result": result})
