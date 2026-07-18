"""Test module prompts — ràng buộc nội dung system prompt (harden Stage 1)."""
from __future__ import annotations

from app.prompts import (
    DETECTIVE_RESPONSE_SCHEMA,
    GEMINI_DETECTIVE_RESPONSE_SCHEMA,
    DETECTIVE_SYSTEM_PROMPT,
    STAGE1_REFUSAL,
    STAGE1_SYSTEM_PROMPT,
)


def test_refusal_message_is_short_and_vietnamese():
    assert STAGE1_REFUSAL == "Tin nhắn không thuộc nội dung cần kiểm tra lừa đảo."


def test_stage1_system_prompt_defines_role():
    assert "ScamCheck" in STAGE1_SYSTEM_PROMPT


def test_stage1_system_prompt_folds_outside_scope_into_safe():
    lowered = STAGE1_SYSTEM_PROMPT.lower()
    assert "không tồn tại nhãn \"khong_lien_quan\"" in lowered
    assert STAGE1_REFUSAL in STAGE1_SYSTEM_PROMPT


def test_stage1_system_prompt_caps_output_length():
    # Quy tắc giới hạn độ dài để tránh lãng phí output token khi có liên quan.
    assert "120 từ" in STAGE1_SYSTEM_PROMPT


def test_stage1_system_prompt_targets_45plus_audience():
    # Người dùng 45+, cần giọng bình tĩnh, không hù doạ.
    lowered = STAGE1_SYSTEM_PROMPT.lower()
    assert "45" in STAGE1_SYSTEM_PROMPT
    assert "bình tĩnh" in lowered


def test_detective_prompt_extends_stage1_contract_with_terminal_tool_handoff():
    assert STAGE1_SYSTEM_PROMPT in DETECTIVE_SYSTEM_PROMPT
    assert "function call" in DETECTIVE_SYSTEM_PROMPT.lower()
    assert "handoff_to_psychologist" in DETECTIVE_SYSTEM_PROMPT


def test_detective_voice_is_dry_rational_and_calm():
    lowered = STAGE1_SYSTEM_PROMPT.lower()
    assert all(word in lowered for word in ("khô khan", "lý tính", "bình tĩnh"))
    assert "không pha trò" in lowered


def test_prompt_treats_user_message_as_untrusted_data():
    lowered = STAGE1_SYSTEM_PROMPT.lower()
    assert "dữ liệu không tin cậy" in lowered
    assert "system" in lowered and "developer" in lowered
    assert "bỏ qua quy tắc" in lowered
    assert "tự gán nhãn an toàn" in lowered


def test_prompt_has_absolute_conservative_rule_for_every_required_risk():
    lowered = STAGE1_SYSTEM_PROMPT.lower()
    assert "tuyệt đối không" in lowered
    assert '"an_toan"' in lowered
    for risk in ("tiền", "otp", "mật khẩu", "thông tin nhạy cảm", "link", "đe dọa"):
        assert risk in lowered
    assert "phải là \"nguy_hiem\"" in lowered


def test_fixed_schema_has_exact_public_contract():
    assert DETECTIVE_RESPONSE_SCHEMA["additionalProperties"] is False
    assert DETECTIVE_RESPONSE_SCHEMA["required"] == [
        "risk_level",
        "reason",
        "red_flags",
        "actions",
    ]
    assert set(DETECTIVE_RESPONSE_SCHEMA["properties"]) == {
        "risk_level",
        "reason",
        "red_flags",
        "actions",
    }
    assert DETECTIVE_RESPONSE_SCHEMA["properties"]["risk_level"]["enum"] == [
        "an_toan", "nghi_ngo", "nguy_hiem",
    ]
    assert DETECTIVE_RESPONSE_SCHEMA["properties"]["red_flags"]["maxItems"] == 3
    assert DETECTIVE_RESPONSE_SCHEMA["properties"]["red_flags"]["items"]["additionalProperties"] is False


def test_gemini_schema_uses_only_supported_subset_without_weakening_prompt_contract():
    assert "additionalProperties" not in GEMINI_DETECTIVE_RESPONSE_SCHEMA
    flag_items = GEMINI_DETECTIVE_RESPONSE_SCHEMA["properties"]["red_flags"]["items"]
    assert "additionalProperties" not in flag_items
    assert GEMINI_DETECTIVE_RESPONSE_SCHEMA["required"] == DETECTIVE_RESPONSE_SCHEMA["required"]
    assert flag_items["required"] == ["label", "excerpt", "explanation"]
