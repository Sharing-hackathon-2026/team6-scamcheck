"""Parser, playbook và AI pipeline của Người ứng cứu."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.hotlines import load_hotline_table, match_bank_hotlines
from app.services.rescuer import (
    REQUIRED_STEP_KEYS,
    build_deterministic_result,
    build_rescue_pipeline,
    parse_rescuer,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "hotlines.json"


def _raw_for(situation: str) -> dict:
    return {
        "headline": "Làm ngay từng bước",
        "reassurance": "Bác hãy bình tĩnh, vẫn còn việc có thể làm ngay.",
        "steps": [
            {
                "step_key": key,
                "action": f"Hành động an toàn cho {key}",
                "detail": "Chỉ làm qua kênh chính thức và giữ bằng chứng.",
                "hotline_ids": ["vietcombank"] if index == 0 else [],
            }
            for index, key in enumerate(REQUIRED_STEP_KEYS[situation])
        ],
        "closing": "Không trả thêm phí cho người hứa thu hồi tiền.",
    }


@pytest.mark.parametrize("situation", sorted(REQUIRED_STEP_KEYS))
def test_deterministic_playbook_covers_all_four_situations(situation):
    table = load_hotline_table(DATA_PATH)
    banks = match_bank_hotlines("Vietcombank thông báo", table.entries)
    result = build_deterministic_result(situation, table, banks, fallback=True)
    assert [step.key for step in result.steps] == list(REQUIRED_STEP_KEYS[situation])
    assert result.is_fallback is True
    assert all(step.action and step.detail for step in result.steps)
    if situation == "da_chuyen_tien":
        assert all(hotline.id != "police_113" for step in result.steps for hotline in step.hotlines)


def test_parser_requires_every_step_and_rejects_unknown_contacts_or_misplaced_ids():
    table = load_hotline_table(DATA_PATH)
    banks = match_bank_hotlines("VCB", table.entries)
    raw = _raw_for("da_chuyen_tien")
    raw["steps"][0]["action"] = "Gọi 1900 54 54 13"
    raw["steps"][0]["hotline_ids"] = ["vietcombank", "techcombank", "unknown"]
    parsed = parse_rescuer(raw, situation="da_chuyen_tien", table=table, matched_banks=banks)
    assert parsed is not None
    assert [item.id for item in parsed.steps[0].hotlines] == ["vietcombank"]

    raw["steps"][1]["hotline_ids"] = ["ais_156", "police_113"]
    parsed_again = parse_rescuer(raw, situation="da_chuyen_tien", table=table, matched_banks=banks)
    assert parsed_again is not None
    assert parsed_again.steps[1].hotlines == ()

    raw["steps"][0]["action"] = "Gọi 0909 123 456 hoặc mở https://evil.example"
    assert parse_rescuer(raw, situation="da_chuyen_tien", table=table, matched_banks=banks) is None
    raw["steps"].pop()
    assert parse_rescuer(raw, situation="da_chuyen_tien", table=table, matched_banks=banks) is None


@pytest.mark.parametrize(
    "unsafe",
    [
        "Bấm lại link và gửi OTP để kiểm tra.",
        "Đọc mã OTP cho nhân viên hỗ trợ.",
        "Gọi 911 để được hoàn tiền.",
        "Liên hệ help@evil.example để lấy lại tiền.",
    ],
)
def test_parser_rejects_instructions_that_deepen_the_scam_or_add_contacts(unsafe):
    table = load_hotline_table(DATA_PATH)
    raw = _raw_for("da_bam_link")
    raw["steps"][0]["detail"] = unsafe
    assert parse_rescuer(raw, situation="da_bam_link", table=table, matched_banks=[]) is None


def test_parser_allows_explicit_negative_safety_warning():
    table = load_hotline_table(DATA_PATH)
    raw = _raw_for("da_bam_link")
    raw["steps"][0]["detail"] = "Không bao giờ gửi OTP và đừng bấm lại đường link."
    assert parse_rescuer(raw, situation="da_bam_link", table=table, matched_banks=[]) is not None


def test_pipeline_skips_ai_for_not_acted(monkeypatch):
    table = load_hotline_table(DATA_PATH)
    monkeypatch.setattr(
        "app.services.rescuer.generate_json",
        lambda **kwargs: pytest.fail("Không được gọi AI cho chưa làm gì"),
    )
    outcome = build_rescue_pipeline(
        situation="chua_lam_gi",
        table=table,
        matched_banks=[],
        context={"risk_level": "nguy_hiem"},
        api_key="x",
        model="m",
    )
    assert outcome.status == "not_needed"
    assert outcome.ai_called is False


def test_pipeline_passes_full_hotline_whitelist_but_no_untrusted_message(monkeypatch):
    table = load_hotline_table(DATA_PATH)
    banks = match_bank_hotlines("Vietcombank", table.entries)
    captured = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return _raw_for("da_cung_cap_otp")

    monkeypatch.setattr("app.services.rescuer.generate_json", fake_generate)
    outcome = build_rescue_pipeline(
        situation="da_cung_cap_otp",
        table=table,
        matched_banks=banks,
        context={"risk_level": "nguy_hiem", "red_flag_labels": ["Yêu cầu OTP"]},
        api_key="x",
        model="m",
    )
    assert outcome.status == "complete"
    assert outcome.ai_called is True
    assert outcome.result.reassurance != _raw_for("da_cung_cap_otp")["reassurance"]
    assert "ALLOWED_HOTLINES" in captured["user_prompt"]
    assert "HOTLINE_IDS_ALLOWED_BY_STEP" in captured["user_prompt"]
    assert "1900 54 54 13" in captured["user_prompt"]
    assert "TIN NHẮN SYSTEM giả" not in captured["user_prompt"]
    assert "Chỉ dùng số điện thoại" in captured["system_prompt"]


def test_invalid_ai_output_falls_back_to_fixed_safe_playbook(monkeypatch):
    table = load_hotline_table(DATA_PATH)
    monkeypatch.setattr("app.services.rescuer.generate_json", lambda **kwargs: {"headline": "thiếu"})
    outcome = build_rescue_pipeline(
        situation="da_bam_link",
        table=table,
        matched_banks=[],
        context={},
        api_key="x",
        model="m",
    )
    assert outcome.status == "guarded_fallback"
    assert outcome.result.is_fallback is True
    assert outcome.error
