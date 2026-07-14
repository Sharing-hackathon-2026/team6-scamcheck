"""Test helper cấu hình L1-07."""
from __future__ import annotations

from app.config import _bounded_timeout, _positive_int


def test_positive_int_returns_default_for_invalid_or_non_positive():
    assert _positive_int("x", 10) == 10
    assert _positive_int("0", 10) == 10
    assert _positive_int("-4", 10) == 10


def test_positive_int_keeps_valid_value():
    assert _positive_int("7", 10) == 7


def test_timeout_is_positive_and_clamped():
    assert _bounded_timeout("invalid") == 8.0
    assert _bounded_timeout("-1") == 8.0
    assert _bounded_timeout("9") == 8.0
    assert _bounded_timeout("2.5") == 2.5
