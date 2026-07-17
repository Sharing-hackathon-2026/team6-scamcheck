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
from ..services.cache import build_cache_key
from ..services.fsm import after_check
from ..services.gemini import GeminiError, generate_function_call, generate_json
from ..services.links import analyze_links
from ..services.parser import parse_detective, parse_psychologist, should_activate_psychologist
from ..services.rule_engine import evaluate_rules, signals_to_payload
from ..services.validation import normalize_nfc, validate_input

bp = Blueprint("check", __name__)


def _record_call(actor: str, text: str, result: dict, status: str = "complete") -> None:
    append_ai_log(
        session,
        len(text),
        result,
        store=current_app.extensions["sqlite_store"],
        actor=actor,
        status=status,
    )


@bp.post("/api/check")
def check():
    """Phân tích bằng terminal tool call rồi nối Cô tâm lý khi verdict yêu cầu."""
    data = request.get_json(silent=True) or {}
    text = normalize_nfc(data.get("text", ""))
    errors = validate_input(text, max_len=current_app.config["MAX_INPUT_LENGTH"])
    if errors:
        return jsonify({"errors": errors}), 400

    cache_key = build_cache_key(text, model=current_app.config["GEMINI_MODEL"])
    cache = current_app.extensions["check_cache"]
    cached = cache.get(cache_key)
    if cached is not None:
        cached["cache"] = {
            "hit": True,
            "ttl_seconds": current_app.config["CHECK_CACHE_TTL"],
        }
        cached["orchestration"] = after_check(
            cached.get("detective", {}).get("risk_level", "nghi_ngo"),
            cached.get("psychologist_status", "unavailable"),
            cache_hit=True,
        ).to_dict()
        return jsonify(cached)

    links = analyze_links(text)
    rule_signals = evaluate_rules(text, links)

    try:
        _tool_name, tool_args = generate_function_call(
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

    detective = parse_detective(tool_args, source_text=text, rule_signals=rule_signals)
    detective_payload = detective.to_dict()
    _record_call("detective", text, detective_payload)

    response = {
        "detective": detective_payload,
        "psychologist": None,
        "psychologist_status": "not_needed",
        "psychologist_error": None,
        "technical_analysis": {
            "links": [item.to_dict() for item in links],
            "rule_signals": signals_to_payload(rule_signals),
        },
        "cache": {
            "hit": False,
            "ttl_seconds": current_app.config["CHECK_CACHE_TTL"],
        },
    }

    if should_activate_psychologist(detective.risk_level):
        # Tool name là advisory. Verdict đã parse/guardrail mới quyết định activation.
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

    response["orchestration"] = after_check(
        detective.risk_level,
        response["psychologist_status"],
    ).to_dict()
    if response["psychologist_status"] != "unavailable":
        cache.put(cache_key, response)
    return jsonify(response)


@bp.get("/api/check/log")
def check_log():
    """Trả nhật ký metadata của từng persona invocation trong phiên."""
    logs = get_ai_log(session, store=current_app.extensions["sqlite_store"])
    response = jsonify({"logs": logs})
    response.headers["Cache-Control"] = "no-store"
    return response
