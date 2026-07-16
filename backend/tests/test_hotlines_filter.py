"""Hotline table và post-filter số điện thoại Stage 5."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.hotlines import (
    contains_untrusted_contact,
    hotline_prompt_payload,
    load_hotline_table,
    match_bank_hotlines,
    normalize_phone,
    strip_unknown_phones,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "hotlines.json"


def test_verified_table_has_ten_banks_police_cybersecurity_and_https_sources():
    table = load_hotline_table(DATA_PATH)
    assert table.version == 2
    assert len([item for item in table.entries if item.type == "bank"]) >= 10
    assert {"police", "cybersecurity"}.issubset({item.type for item in table.entries})
    assert all(item.source_url.startswith("https://") for item in table.entries)
    assert all(item.normalized_phone == normalize_phone(item.phone) for item in table.entries)
    assert len(table.by_id()) == len(table.entries)


def test_table_fails_closed_on_duplicate_phone(tmp_path):
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    raw["entries"][1]["phone"] = raw["entries"][0]["phone"]
    raw["entries"][1]["source_evidence"] = raw["entries"][0]["source_evidence"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="trùng"):
        load_hotline_table(path)


def test_table_fails_closed_when_number_specific_evidence_does_not_match(tmp_path):
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    raw["entries"][0]["source_evidence"] = "Tài liệu không ghi số liên hệ."
    path = tmp_path / "unproven.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="không chứa đúng số"):
        load_hotline_table(path)


def test_match_bank_hotlines_is_accent_insensitive_and_avoids_substrings():
    table = load_hotline_table(DATA_PATH)
    assert [item.id for item in match_bank_hotlines("Tin từ NGAN HANG NGOAI THUONG", table.entries)] == [
        "vietcombank"
    ]
    assert [item.id for item in match_bank_hotlines("Tài khoản MB Bank có biến động", table.entries)] == [
        "mbbank"
    ]
    assert match_bank_hotlines("Hôm nay em bé ăn cơm", table.entries) == []


def test_unknown_phone_filter_keeps_only_whitelist_across_formatting():
    text = "Gọi 1900 54 54 13 hoặc 0909-123-456; khẩn cấp 113, báo rác 156."
    cleaned = strip_unknown_phones(text, {"1900545413", "113", "156"})
    assert "1900 54 54 13" in cleaned
    assert "0909-123-456" not in cleaned
    assert "113" in cleaned and "156" in cleaned
    assert "số chưa được xác minh" in cleaned
    assert "911" not in strip_unknown_phones("Gọi 911", {"113"})


def test_contact_detector_rejects_urls_email_and_unknown_shortcodes_but_allows_whitelist():
    assert contains_untrusted_contact("Mở https://evil.example", set()) is True
    assert contains_untrusted_contact("Gửi a@evil.example", set()) is True
    assert contains_untrusted_contact("Gọi 911", {"113"}) is True
    assert contains_untrusted_contact("Gọi 1900 54 54 13", {"1900545413"}) is False


def test_prompt_payload_contains_only_public_matching_fields():
    table = load_hotline_table(DATA_PATH)
    payload = hotline_prompt_payload(table)
    assert payload[0].keys() == {"id", "name", "phone", "type", "channel"}
    assert "aliases" not in payload[0]
    assert all(item.source_evidence and item.source_checked_at for item in table.entries)
    assert all(item.normalized_phone in normalize_phone(item.source_evidence) for item in table.entries)
