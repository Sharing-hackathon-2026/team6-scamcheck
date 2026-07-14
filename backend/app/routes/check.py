"""POST /api/check — tool-call Thám tử và chain Cô tâm lý Stage 3."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from ..prompts import (
    DETECTIVE_FUNCTION_DECLARATIONS,
    DETECTIVE_SYSTEM_PROMPT,
    GEMINI_PSYCHOLOGIST_RESPONSE_SCHEMA,
    PSYCHOLOGIST_SYSTEM_PROMPT,
    build_psychologist_user_prompt,
)
from ..services.audit import append_ai_log, get_ai_log
from ..services.gemini import GeminiError, generate_function_call, generate_json
from ..services.parser import parse_detective, parse_psychologist, should_activate_psychologist
from ..services.validation import normalize_nfc, validate_input

bp = Blueprint("check", __name__)


def _usage(call_limit: int) -> dict[str, int]:
    return {"calls_used": len(get_ai_log(session)), "call_limit": call_limit}


def _record_call(actor: str, text: str, result: dict, status: str = "complete") -> None:
    append_ai_log(session, len(text), result, actor=actor, status=status)


@bp.post("/api/check")
def check():
    """Phân tích bằng terminal tool call rồi nối Cô tâm lý khi verdict yêu cầu."""
    data = request.get_json(silent=True) or {}
    text = normalize_nfc(data.get("text", ""))
    errors = validate_input(text, max_len=current_app.config["MAX_INPUT_LENGTH"])
    if errors:
        return jsonify({"errors": errors}), 400

    call_limit = current_app.config["AI_CALL_LIMIT"]
    calls_used = len(get_ai_log(session))
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
        tool_name, tool_args = generate_function_call(
            api_key=current_app.config["GEMINI_API_KEY"],
            model=current_app.config["GEMINI_MODEL"],
            user_prompt=text,
            system_prompt=DETECTIVE_SYSTEM_PROMPT,
            function_declarations=DETECTIVE_FUNCTION_DECLARATIONS,
            timeout=6.0,
            max_retries=1,
        )
    except GeminiError as exc:
        _record_call(
            "detective",
            text,
            {"risk_level": "nghi_ngo"},
            status="error",
        )
        return jsonify({"error": str(exc)}), 502

    detective = parse_detective(tool_args, source_text=text)
    detective_payload = detective.to_dict()
    _record_call("detective", text, detective_payload)

    response = {
        "detective": detective_payload,
        "psychologist": None,
        "psychologist_status": "not_needed",
        "psychologist_error": None,
    }

    if should_activate_psychologist(detective.risk_level):
        # Tool name là advisory. Verdict đã parse/guardrail mới quyết định activation.
        if len(get_ai_log(session)) >= call_limit:
            response["psychologist_status"] = "quota_reached"
            response["psychologist_error"] = (
                "Đã có kết quả Thám tử, nhưng phiên này không còn lượt để gọi Cô tâm lý."
            )
        else:
            try:
                raw_psychologist = generate_json(
                    api_key=current_app.config["GEMINI_API_KEY"],
                    model=current_app.config["GEMINI_MODEL"],
                    user_prompt=build_psychologist_user_prompt(text, detective_payload),
                    system_prompt=PSYCHOLOGIST_SYSTEM_PROMPT,
                    response_schema=GEMINI_PSYCHOLOGIST_RESPONSE_SCHEMA,
                    timeout=5.0,
                    max_retries=0,
                )
                psychologist = parse_psychologist(raw_psychologist)
                if psychologist is None:
                    response["psychologist_status"] = "unavailable"
                    response["psychologist_error"] = (
                        "Cô tâm lý chưa thể giải thích thêm lúc này; kết quả Thám tử vẫn đầy đủ."
                    )
                    _record_call("psychologist", text, detective_payload, status="invalid_response")
                else:
                    response["psychologist"] = psychologist.to_dict()
                    response["psychologist_status"] = "complete"
                    _record_call("psychologist", text, detective_payload)
            except GeminiError:
                response["psychologist_status"] = "unavailable"
                response["psychologist_error"] = (
                    "Cô tâm lý đang tạm bận; bác vẫn có thể dùng kết quả Thám tử ở trên."
                )
                _record_call("psychologist", text, detective_payload, status="error")

    response["usage"] = _usage(call_limit)
    return jsonify(response)


@bp.get("/api/check/log")
def check_log():
    """Trả nhật ký metadata của từng persona invocation trong phiên."""
    logs = get_ai_log(session)
    return jsonify(
        {
            "logs": logs,
            "calls_used": len(logs),
            "call_limit": current_app.config["AI_CALL_LIMIT"],
        }
    )
