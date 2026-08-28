"""Property-based tests for order data extraction from AI responses.

Goal: extract_order_from_response() and validate_order_data() must NEVER
crash on arbitrary text — they should always return dict|None.

Run:
    pytest tests/property/test_order_data_property.py -v
"""
from __future__ import annotations

import json

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from app.ai.order_collector import (
    clean_response_for_customer,
    extract_order_from_response,
    validate_order_data,
)


# Strategy: any text.
any_text = st.text(max_size=2000)

# Strategy: random JSON-compatible dict that *looks* like an order payload.
order_dict_strategy = st.fixed_dictionaries(
    {},
    optional={
        "action": st.sampled_from(["create_order", "delete_order", "", "search"]),
        "order_data": st.fixed_dictionaries(
            {},
            optional={
                "customer_name": st.text(max_size=50),
                "customer_phone": st.text(max_size=20),
                "governorate": st.text(max_size=30),
                "city": st.text(max_size=30),
                "area": st.text(max_size=30),
                "address_detail": st.text(max_size=200),
                "payment_method": st.sampled_from(["cod", "vodafone_cash", "instapay", ""]),
                "product_name": st.text(max_size=50),
                "quantity": st.one_of(st.integers(min_value=-5, max_value=100), st.text(max_size=5)),
                "items": st.lists(
                    st.fixed_dictionaries(
                        {},
                        optional={
                            "product_name": st.text(max_size=50),
                            "quantity": st.one_of(st.integers(min_value=-5, max_value=100), st.text(max_size=5)),
                        },
                    ),
                    max_size=5,
                ),
            },
        ),
    },
)

# Strategy: random JSON-encoded string that mimics AI response.
json_response_strategy = st.builds(
    lambda d: f"Here's your reply!\n```json\n{json.dumps(d)}\n```",
    order_dict_strategy,
)


class TestOrderExtractionProperty:
    """Order extraction must never raise on arbitrary inputs."""

    @given(any_text)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_extract_order_never_crashes(self, text):
        """extract_order_from_response must return dict|None for any text."""
        result = extract_order_from_response(text)
        assert result is None or isinstance(result, dict)

    @given(json_response_strategy)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_extract_order_from_random_json(self, text):
        """Random JSON-in-fenced-block must not crash extraction."""
        result = extract_order_from_response(text)
        assert result is None or isinstance(result, dict)

    @given(any_text)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_clean_response_never_crashes(self, text):
        """clean_response_for_customer must always return a string."""
        result = clean_response_for_customer(text)
        assert isinstance(result, str)

    @given(order_dict_strategy)
    @settings(max_examples=500, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_validate_order_data_never_crashes(self, data):
        """validate_order_data must return dict|None for any dict shape."""
        # The strategy may produce nested dicts that are already valid — that's fine.
        result = validate_order_data(data.get("order_data", {}) if isinstance(data.get("order_data"), dict) else {})
        assert result is None or isinstance(result, dict)

    @given(order_dict_strategy)
    @settings(max_examples=300, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_clean_then_extract_idempotent(self, data):
        """If extract finds an order, cleaning must remove the JSON block."""
        response = f"```json\n{json.dumps(data)}\n```"
        order = extract_order_from_response(response)
        cleaned = clean_response_for_customer(response)
        if order is not None:
            # The JSON block must have been stripped.
            assert "create_order" not in cleaned, (
                "clean_response_for_customer leaked the JSON action block"
            )
            assert "```json" not in cleaned

    @given(st.text(min_size=1000, max_size=5000))
    @settings(max_examples=50, deadline=None,
              suppress_health_check=[HealthCheck.too_slow])
    def test_extract_order_handles_huge_input(self, text):
        """Very long inputs must not cause regex DoS."""
        result = extract_order_from_response(text)
        assert result is None or isinstance(result, dict)
