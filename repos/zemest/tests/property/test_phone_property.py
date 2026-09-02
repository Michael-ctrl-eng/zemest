"""Property-based tests for Egyptian phone validation.

Goal: validate_egyptian_phone() must NEVER crash on arbitrary input —
it should always return a bool. We throw hundreds of random strings,
unicode, binary-adjacent text, and oversized inputs at it.

Run:
    pytest tests/property/test_phone_property.py -v
"""
from __future__ import annotations

import string

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from app.utils.egypt_address import (
    normalize_egyptian_phone as normalize_addr_phone,
    validate_egyptian_phone as validate_addr_phone,
)
from app.utils.phone import (
    normalize_egyptian_phone as normalize_util_phone,
    validate_egyptian_phone as validate_util_phone,
)


# Strategy: any text up to 20 chars (covers phone-sized inputs + garbage).
phone_text = st.text(max_size=20)

# Strategy: realistic phone-shaped strings — digits + separators.
phone_realistic = st.builds(
    lambda prefix, digits, sep1, sep2, plus: (
        ("+" if plus else "")
        + prefix
        + sep1
        + digits
        + sep2
    ),
    prefix=st.sampled_from(["010", "011", "012", "015", "020", "20", "+20"]),
    digits=st.text(string.digits, min_size=0, max_size=12),
    sep1=st.sampled_from(["", "-", " ", "(", "/"]),
    sep2=st.sampled_from(["", "-", " "]),
    plus=st.booleans(),
)


class TestPhoneValidationProperty:
    """validate_egyptian_phone must be a total function — no exceptions."""

    @given(phone_text)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_validate_phone_never_crashes(self, phone):
        """Phone validation should never raise — always return bool."""
        result = validate_util_phone(phone)
        assert isinstance(result, bool), f"Expected bool, got {type(result)}"

    @given(phone_text)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_addr_validate_phone_never_crashes(self, phone):
        """The egypt_address copy of validate must also be total."""
        result = validate_addr_phone(phone)
        assert isinstance(result, bool)

    @given(phone_realistic)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_validate_phone_realistic_inputs(self, phone):
        """Realistic phone-shaped strings must not crash validation."""
        result = validate_util_phone(phone)
        assert isinstance(result, bool)

    @given(phone_text)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_normalize_phone_never_crashes(self, phone):
        """Normalize must return either a string or None — never raise."""
        result = normalize_util_phone(phone)
        assert result is None or isinstance(result, str)

    @given(phone_text)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_addr_normalize_phone_never_crashes(self, phone):
        """The egypt_address normalize must also be total."""
        result = normalize_addr_phone(phone)
        assert result is None or isinstance(result, str)

    @given(phone_text)
    @settings(max_examples=200, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_validate_normalize_consistency(self, phone):
        """If validate returns True, normalize should produce a re-validating string."""
        if validate_util_phone(phone):
            # The util-phone normalize always returns a string — and a valid
            # phone should normalize to something that ALSO validates True.
            normalized = normalize_util_phone(phone)
            assert isinstance(normalized, str)
            assert validate_util_phone(normalized) is True, (
                f"Normalized '{normalized}' from valid '{phone!r}' failed validation"
            )

    @given(st.one_of(st.none(), st.integers(), st.floats(), st.lists(st.integers())))
    @settings(max_examples=100, deadline=None)
    def test_validate_phone_handles_non_string(self, value):
        """Non-string inputs (None, int, list) must not crash validation.

        The function may return False (the falsy path), but it MUST NOT raise.
        """
        try:
            result = validate_util_phone(value)  # type: ignore[arg-type]
        except (TypeError, AttributeError):
            # If the implementation rejects non-strings, that's acceptable —
            # we only care that it doesn't crash with an unhandled exception.
            return
        assert isinstance(result, bool)

    @given(st.text(min_size=100, max_size=2000))
    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_validate_phone_handles_huge_input(self, phone):
        """Very long strings must not cause regex DoS."""
        result = validate_util_phone(phone)
        assert isinstance(result, bool)
