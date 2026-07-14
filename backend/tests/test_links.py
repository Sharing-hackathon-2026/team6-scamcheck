from __future__ import annotations

import requests
import pytest

from app.services.links import (
    UnsafeUrlError,
    analyze_links,
    assert_public_url,
    extract_urls,
    normalize_url,
    resolve_redirects,
)


def public_dns(host, port, type=None):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


class Response:
    def __init__(self, status=200, location=""):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self.closed = False

    def close(self):
        self.closed = True


def test_extracts_multiple_scheme_www_bare_urls_and_trims_punctuation():
    text = "Xem (https://a.example/path), www.b.example/x và bit.ly/demo."
    assert extract_urls(text) == ["https://a.example/path", "www.b.example/x", "bit.ly/demo"]


def test_extraction_ignores_email_and_deduplicates():
    assert extract_urls("mail a@bank.com; bank.com và bank.com") == ["bank.com"]


def test_normalize_url_adds_https_idna_and_removes_fragment():
    value = normalize_url("tênmiền.vn/a?q=1#secret")
    assert value.startswith("https://xn--")
    assert value.endswith("/a?q=1")
    assert "#" not in value


def test_normalize_rejects_userinfo_and_non_http():
    with pytest.raises(UnsafeUrlError):
        normalize_url("https://user:pass@example.com")
    with pytest.raises(ValueError):
        normalize_url("ftp://example.com")


def test_resolve_redirect_chain_without_reading_body():
    responses = [Response(302, "/next"), Response(301, "https://final.example/end"), Response()]
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    final, redirected = resolve_redirects(
        "https://bit.ly/demo", request_get=get, resolver=public_dns
    )
    assert final == "https://final.example/end"
    assert redirected is True
    assert all(call[1]["stream"] is True and call[1]["allow_redirects"] is False for call in calls)


def test_redirect_loop_or_too_many_hops_is_bounded():
    def get(url, **kwargs):
        return Response(302, "/next")

    with pytest.raises(ValueError):
        resolve_redirects("https://bit.ly/a", max_redirects=1, request_get=get, resolver=public_dns)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x",
    "http://10.0.0.1/x",
    "http://169.254.169.254/latest/meta-data",
    "http://[::1]/x",
])
def test_ssrf_private_loopback_link_local_are_blocked(url):
    with pytest.raises(UnsafeUrlError):
        assert_public_url(url)


def test_redirect_to_private_ip_is_blocked_before_second_request():
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response(302, "http://127.0.0.1/admin")

    with pytest.raises(UnsafeUrlError):
        resolve_redirects("https://bit.ly/a", request_get=get, resolver=public_dns)
    assert calls == ["https://bit.ly/a"]


def test_shortener_timeout_becomes_warning_instead_of_crashing():
    def timeout(*args, **kwargs):
        raise requests.Timeout("slow")

    result = analyze_links(
        "Mở bit.ly/abc", request_get=timeout, resolver=public_dns
    )
    codes = {warning.code for warning in result[0].warnings}
    assert {"shortener", "resolve_failed"}.issubset(codes)


def test_normal_url_is_not_fetched():
    def must_not_call(*args, **kwargs):
        raise AssertionError("URL thường không được backend truy cập")

    result = analyze_links("Xem https://example.com/a", request_get=must_not_call)
    assert result[0].final_domain == "example.com"
    assert result[0].resolved is False
