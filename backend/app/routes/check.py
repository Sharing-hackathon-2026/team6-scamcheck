"""POST /api/check — kiểm tra có cấu trúc (L1-03 đến L1-08)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from ..prompts import STAGE1_SYSTEM_PROMPT
from ..services.audit import append_ai_log, get_ai_log
from ..services.gemini import GeminiError, generate_json
from ..services.parser import parse_detective
from ..services.validation import normalize_nfc, validate_input

bp = Blueprint("check", __name__)


@bp.post("/api/check")
def check():
    """Phân tích tin nhắn và luôn trả kết quả Thám tử có cấu trúc."""
    data = request.get_json(silent=True) or {}
    text = normalize_nfc(data.get("text", ""))
    errors = validate_input(text, max_len=current_app.config["MAX_INPUT_LENGTH"])
    if errors:
        return jsonify({"errors": errors}), 400

    calls_used = len(get_ai_log(session))
    call_limit = current_app.config["AI_CALL_LIMIT"]
    if calls_used >= call_limit:
        return jsonify(
            {
                "error": "Bác đã dùng hết lượt kiểm tra của phiên này. Vui lòng thử lại sau hoặc mở phiên mới.",
                "code": "ai_call_limit_reached",
                "calls_used": calls_used,
                "call_limit": call_limit,
            }
        ), 429

    try:
        raw_result = generate_json(
            api_key=current_app.config["GEMINI_API_KEY"],
            model=current_app.config["GEMINI_MODEL"],
            user_prompt=text,
            system_prompt=STAGE1_SYSTEM_PROMPT,
        )
    except GeminiError as exc:
        return jsonify({"error": str(exc)}), 502

    detective = parse_detective(raw_result, source_text=text)
    payload = detective.to_dict()
    append_ai_log(session, len(text), payload)
    return jsonify(
        {
            "detective": payload,
            "usage": {"calls_used": calls_used + 1, "call_limit": call_limit},
        }
    )


@bp.get("/api/check/log")
def check_log():
    """Trả nhật ký đã được tối giản của đúng phiên hiện tại (L1-08)."""
    logs = get_ai_log(session)
    return jsonify(
        {
            "logs": logs,
            "calls_used": len(logs),
            "call_limit": current_app.config["AI_CALL_LIMIT"],
        }
    )
