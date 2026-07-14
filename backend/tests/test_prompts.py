"""Test module prompts — ràng buộc nội dung system prompt (harden Stage 1)."""
from __future__ import annotations

from app.prompts import STAGE1_REFUSAL, STAGE1_SYSTEM_PROMPT


def test_refusal_message_is_short_and_vietnamese():
    # Refusal canned phải ngắn (tiết kiệm token) và nói rõ phạm vi công cụ.
    assert len(STAGE1_REFUSAL) < 300
    assert "ScamCheck" in STAGE1_REFUSAL
    assert "lừa đảo" in STAGE1_REFUSAL


def test_stage1_system_prompt_defines_role():
    assert "ScamCheck" in STAGE1_SYSTEM_PROMPT


def test_stage1_system_prompt_requires_refusal_for_unrelated():
    # Harden: phải yêu cầu AI từ chối tin không liên quan.
    lowered = STAGE1_SYSTEM_PROMPT.lower()
    assert "không liên quan" in lowered
    # Câu canned phải được nhúng nguyên văn vào prompt để AI复读 đúng.
    assert STAGE1_REFUSAL in STAGE1_SYSTEM_PROMPT


def test_stage1_system_prompt_caps_output_length():
    # Quy tắc giới hạn độ dài để tránh lãng phí output token khi có liên quan.
    assert "120 từ" in STAGE1_SYSTEM_PROMPT


def test_stage1_system_prompt_targets_45plus_audience():
    # Người dùng 45+, cần giọng bình tĩnh, không hù doạ.
    lowered = STAGE1_SYSTEM_PROMPT.lower()
    assert "45" in STAGE1_SYSTEM_PROMPT
    assert "bình tĩnh" in lowered