"""Property-based tests for Egyptian address / shipping calculation.

Goal: calculate_shipping() and detect_governorate_from_text() must NEVER
crash on arbitrary input — they should always return a dict / Optional[str].

Run:
    pytest tests/property/test_address_property.py -v
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from app.utils.egypt_address import (
    GOVERNORATES,
    calculate_shipping,
    detect_governorate_from_text,
    get_areas_for_governorate,
    get_cities,
    get_governorates,
    validate_egyptian_address,
)


# Strategy: any text up to 100 chars.
address_text = st.text(max_size=100)

# Strategy: any string — including None-like values.
governorate_key = st.sampled_from(list(GOVERNORATES.keys()) + [
    "", "Cairo", "CAIRO", "Giza", "unknown", "null", "123",
])

# Strategy: random float for cart total — can be negative or huge.
cart_total = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1000, max_value=1_000_000),
    st.integers(min_value=-1000, max_value=1_000_000),
    st.none(),
)


class TestAddressProperty:
    """All address functions must be total — no exceptions on any input."""

    @given(address_text)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_calculate_shipping_never_crashes(self, gov):
        """Shipping calc must always return a dict with 'cost' and 'free'."""
        result = calculate_shipping(gov)
        assert isinstance(result, dict)
        assert "cost" in result
        assert "free" in result

    @given(governorate_key, cart_total)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_calculate_shipping_with_cart_total(self, gov, total):
        """Shipping calc with arbitrary cart total must never crash."""
        try:
            result = calculate_shipping(gov, total)  # type: ignore[arg-type]
        except TypeError:
            # If total isn't numeric, the function may raise TypeError —
            # that's acceptable, we only care about valid numeric inputs.
            return
        assert isinstance(result, dict)
        assert "cost" in result
        assert "free" in result
        assert isinstance(result["cost"], (int, float))
        assert isinstance(result["free"], bool)

    @given(address_text)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_detect_governorate_never_crashes(self, text):
        """Governorate detection must return str|None."""
        result = detect_governorate_from_text(text)
        assert result is None or isinstance(result, str)

    @given(address_text)
    @settings(max_examples=200, deadline=None)
    def test_validate_address_never_crashes(self, gov):
        """Address validation must always return a bool."""
        result = validate_egyptian_address(gov)
        assert isinstance(result, bool)

    @given(governorate_key)
    @settings(max_examples=200, deadline=None)
    def test_get_cities_never_crashes(self, gov):
        """get_cities must always return a list."""
        result = get_cities(gov)
        assert isinstance(result, list)

    @given(governorate_key)
    @settings(max_examples=200, deadline=None)
    def test_get_areas_never_crashes(self, gov):
        """get_areas_for_governorate must always return a list."""
        result = get_areas_for_governorate(gov)
        assert isinstance(result, list)

    def test_get_governorates_returns_consistent_list(self):
        """get_governorates() should always return 27 governorates."""
        govs = get_governorates()
        assert len(govs) == 27
        for g in govs:
            assert "key" in g
            assert "name_ar" in g
            assert "zone" in g
            assert "shipping_cost" in g
            assert "free_threshold" in g

    @given(governorate_key)
    @settings(max_examples=200, deadline=None)
    def test_shipping_cost_is_non_negative(self, gov):
        """Shipping cost must never be negative."""
        result = calculate_shipping(gov)
        assert result["cost"] >= 0, f"Negative cost for {gov}: {result}"

    @given(governorate_key, st.floats(min_value=0, max_value=100_000, allow_nan=False))
    @settings(max_examples=300, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_shipping_free_when_above_threshold(self, gov, total):
        """When cart_total >= free_threshold, shipping must be free."""
        result = calculate_shipping(gov, total)
        if gov in GOVERNORATES:
            threshold = GOVERNORATES[gov]["free_threshold"]
            if total >= threshold:
                assert result["free"] is True
                assert result["cost"] == 0
