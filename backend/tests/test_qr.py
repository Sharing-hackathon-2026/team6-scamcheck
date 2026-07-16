"""QR share endpoint và encoder local không phụ thuộc mạng."""
from __future__ import annotations

import pytest

from app.services.qr import approved_share_url, encode_qr_matrix, qr_svg


def test_share_origin_allowlist_rejects_host_header_and_bad_config():
    allowed = ("team6-scamcheck.exe.xyz", "localhost")
    assert approved_share_url(
        "https://team6-scamcheck.exe.xyz", "http://evil.example/", allowed
    ) == "https://team6-scamcheck.exe.xyz/"
    assert approved_share_url("", "http://localhost:5000/", allowed) == "http://localhost:5000/"
    with pytest.raises(ValueError, match="origin"):
        approved_share_url("", "https://evil.example/", allowed)
    with pytest.raises(ValueError, match="origin"):
        approved_share_url("https://evil.example/", "http://localhost/", allowed)
    with pytest.raises(ValueError, match="origin"):
        approved_share_url("http://team6-scamcheck.exe.xyz/", "", allowed)
    with pytest.raises(ValueError, match="cổng nội bộ"):
        approved_share_url("https://team6-scamcheck.exe.xyz:8000/", "", allowed)
    assert approved_share_url(
        "https://team6-scamcheck.exe.xyz:443/", "", allowed
    ) == "https://team6-scamcheck.exe.xyz/"
    with pytest.raises(ValueError, match="origin"):
        approved_share_url("https://team6-scamcheck.exe.xyz/?next=evil", "", allowed)


def test_qr_matrix_has_version3_size_finders_and_changes_with_url():
    first = encode_qr_matrix("https://scamcheck.example/")
    second = encode_qr_matrix("https://scamcheck.example/?x=1")
    assert len(first) == 29 and all(len(row) == 29 for row in first)
    assert first != second
    # Tâm ba finder pattern luôn tối.
    assert first[3][3] and first[3][25] and first[25][3]
    # Tâm alignment version 3.
    assert first[22][22]


def test_qr_rejects_payload_over_fixed_safe_capacity_and_small_border():
    with pytest.raises(ValueError, match="quá dài"):
        encode_qr_matrix("x" * 54)
    with pytest.raises(ValueError, match="quiet zone"):
        qr_svg("https://example.com", border=3)


def test_qr_svg_has_white_quiet_zone_crisp_modules_and_escaped_label():
    svg = qr_svg("https://example.com/?a=1&b=2")
    assert svg.startswith("<svg")
    assert 'viewBox="0 0 37 37"' in svg
    assert 'shape-rendering="crispEdges"' in svg
    assert 'fill="#fff"' in svg and 'fill="#000"' in svg
    assert "&amp;" in svg


def test_share_qr_endpoint_ignores_arbitrary_url_and_is_cacheable(client):
    response = client.get("/api/share/qr.svg?url=https://evil.example")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "evil.example" not in response.get_data(as_text=True)
    assert "Mã QR dẫn tới http://localhost/" in response.get_data(as_text=True)
    client.application.config["BASE_URL"] = ""
    rejected = client.get("/api/share/qr.svg", headers={"Host": "evil.example"})
    assert rejected.status_code == 503
