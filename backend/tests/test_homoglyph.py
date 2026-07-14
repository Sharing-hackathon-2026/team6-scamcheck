import pytest

from app.services.links import (
    detect_spoofed_domain,
    domain_skeleton,
    levenshtein,
    load_legit_domains,
)


@pytest.mark.parametrize("host", [
    "vietcornbank.com.vn",          # m -> rn
    "v1etcombank.com.vn",           # i -> 1
    "vietcombank.net",              # đổi suffix
    "vietcombank.com.vn.evil.com",  # subdomain deception
    "vіetcombank.com.vn",           # Cyrillic i
    "viet\u200bcombank.com.vn",     # zero width
    "viet-combank.com.vn",          # chèn dấu gạch
    "techcornbank.com",             # m -> rn brand khác
    "mbbanк.com.vn",                # Cyrillic k
    "bidvv.com.vn",                 # chèn ký tự
    "xn--80ak6aa92e.com",            # punycode
])
def test_at_least_ten_spoof_patterns_have_specific_warning(host):
    warnings = detect_spoofed_domain(host, load_legit_domains())
    assert warnings
    assert all(warning.code and warning.reason for warning in warnings)


def test_legitimate_domain_and_subdomain_do_not_warn():
    domains = load_legit_domains()
    assert detect_spoofed_domain("vietcombank.com.vn", domains) == []
    assert detect_spoofed_domain("login.vietcombank.com.vn", domains) == []
    assert detect_spoofed_domain("a-very-long-unrelated-legitimate-example.org", domains) == []


def test_skeleton_maps_confusables_and_distance_is_deterministic():
    assert domain_skeleton("раypal.com") == "paypal.com"
    assert levenshtein("vietcombank", "vietcornbank") == 2
    assert levenshtein("abc", "abc") == 0
