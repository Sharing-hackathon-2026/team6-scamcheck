"""Test dữ liệu và endpoint thư viện lừa đảo Stage 3."""
from pathlib import Path

import pytest

from app.services.scam_library import GROUP_KEYS, load_scam_library, validate_scam_library


def test_static_library_has_exact_groups_and_at_least_twelve_items():
    library = load_scam_library()
    assert {group["key"] for group in library["groups"]} == GROUP_KEYS
    assert len(library["items"]) >= 12
    assert all(item["warning_signs"] and item["safe_action"] for item in library["items"])


def test_validate_library_rejects_wrong_shape_and_duplicate_ids():
    with pytest.raises(ValueError):
        validate_scam_library([])
    valid = load_scam_library()
    broken = {**valid, "items": valid["items"] + [valid["items"][0]]}
    with pytest.raises(ValueError):
        validate_scam_library(broken)


def test_load_library_reads_requested_path(tmp_path: Path):
    source = Path(__file__).parents[1] / "data" / "scam_library.json"
    target = tmp_path / "library.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    assert load_scam_library(target)["version"] == "stage3-v1"


def test_library_endpoint_does_not_use_ai(client, mock_gemini_text):
    response = client.get("/api/scam-library")
    assert response.status_code == 200
    assert len(response.get_json()["items"]) >= 12
    assert mock_gemini_text["calls"] == 0
