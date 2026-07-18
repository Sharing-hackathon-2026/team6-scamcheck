"""Stage 5 API: bảng hotline và Người ứng cứu theo tình huống một lần."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, session

from ..services.audit import append_ai_log
from ..services.fsm import SITUATIONS, after_situation, stage5_call_savings
from ..services.hotlines import load_hotline_table, match_bank_hotlines
from ..services.qr import approved_share_url, qr_svg
from ..services.rescuer import build_rescue_pipeline
from ..services.validation import normalize_nfc

bp = Blueprint("rescue", __name__)
_ALLOWED_RISKS = {"an_toan", "nghi_ngo", "nguy_hiem"}
_SITUATION_LABELS = {
    "chua_lam_gi": "Chưa làm gì",
    "da_bam_link": "Đã bấm vào đường link",
    "da_chuyen_tien": "Đã chuyển tiền",
    "da_cung_cap_otp": "Đã cung cấp OTP, PIN hoặc mật khẩu",
}


def _clean_context(data: dict[str, Any]) -> tuple[dict[str, Any], str, list[str]]:
    """Chỉ đưa metadata ngắn vào prompt; toàn văn tin chỉ dùng local để match ngân hàng."""
    errors: list[str] = []
    message_raw = data.get("message_text", "")
    if not isinstance(message_raw, str):
        errors.append("Nội dung tin nhắn đi kèm phải là chuỗi.")
        message_text = ""
    else:
        message_text = normalize_nfc(message_raw.strip())
        if len(message_text) > current_app.config["MAX_INPUT_LENGTH"]:
            errors.append("Nội dung tin nhắn đi kèm quá dài.")

    risk = data.get("risk_level", "nghi_ngo")
    risk_level = risk if isinstance(risk, str) and risk in _ALLOWED_RISKS else "nghi_ngo"
    # red_flags từ client có thể chứa dữ liệu riêng tư giả dạng label. Rescuer không cần
    # chúng để chọn deterministic playbook, nên tuyệt đối không chuyển trường này tới Gemini.
    return {"risk_level": risk_level}, message_text, errors


@bp.get("/api/share/qr.svg")
def share_qr():
    """QR chuẩn dẫn về trang chủ; không nhận URL tùy ý để tránh biến endpoint thành công cụ phishing."""
    configured = str(current_app.config.get("BASE_URL", ""))
    try:
        target = approved_share_url(
            configured,
            request.url_root,
            current_app.config["SHARE_ALLOWED_HOSTS"],
        )
        svg = qr_svg(target)
    except ValueError:
        return jsonify({"error": "Địa chỉ chia sẻ chưa được cấu hình hợp lệ."}), 503
    return Response(
        svg,
        mimetype="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@bp.get("/api/hotlines")
def hotlines():
    """Trả bảng nguồn liên hệ công khai; không gọi AI."""
    try:
        table = load_hotline_table(current_app.config["HOTLINES_PATH"])
    except ValueError:
        return jsonify({"error": "Bảng tổng đài đang tạm chưa sẵn sàng."}), 503
    return jsonify(
        {
            "version": table.version,
            "reviewed_at": table.reviewed_at,
            "notice": table.notice,
            "entries": [item.to_public_dict(table.reviewed_at) for item in table.entries],
        }
    )


@bp.post("/api/rescue")
def rescue():
    """Nhận đúng một trong bốn tình huống và trả playbook đã post-filter số điện thoại."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"errors": ["Vui lòng chọn tình huống bác đã gặp."]}), 400
    situation = data.get("situation")
    if situation not in SITUATIONS:
        return jsonify({"errors": ["Vui lòng chọn một trong bốn tình huống có sẵn."]}), 400
    context, message_text, errors = _clean_context(data)
    if errors:
        return jsonify({"errors": errors}), 400

    try:
        table = load_hotline_table(current_app.config["HOTLINES_PATH"])
    except ValueError:
        return jsonify({"error": "Quy trình ứng cứu đang tạm chưa sẵn sàng."}), 503
    matched_banks = match_bank_hotlines(message_text, table.entries)
    outcome = build_rescue_pipeline(
        situation=situation,
        table=table,
        matched_banks=matched_banks,
        context=context,
        api_key=current_app.config["GEMINI_API_KEY"],
        model=current_app.config["GEMINI_MODEL"],
        ai_enabled=current_app.config["RESCUE_AI_ENABLED"],
    )

    if outcome.ai_called:
        append_ai_log(
            session,
            len(message_text),
            {"situation": situation, "risk_level": context["risk_level"]},
            store=current_app.extensions["sqlite_store"],
            actor="rescuer",
            status="complete" if outcome.status == "complete" else "guarded_fallback",
            prompt=message_text,
        )
    orchestration = after_situation(situation, rescuer_called=outcome.ai_called)
    response = {
        "situation": situation,
        "situation_label": _SITUATION_LABELS[situation],
        "praise": (
            "Bác đã dừng lại trước khi làm theo — đây là bước bảo vệ quan trọng nhất."
            if situation == "chua_lam_gi" else None
        ),
        "rescue": outcome.result.to_dict(table.reviewed_at),
        "rescue_status": outcome.status,
        "rescue_error": outcome.error,
        "matched_institutions": [item.name for item in matched_banks],
        "orchestration": orchestration.to_dict(),
        "call_savings_baseline": stage5_call_savings(),
        "safety_notice": (
            "Chỉ dùng số đã đối chiếu từ bảng tĩnh. ScamCheck không thể khóa giao dịch "
            "hay bảo đảm lấy lại tiền."
        ),
    }
    return jsonify(response)
