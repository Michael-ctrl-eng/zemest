"""Tests for order data extraction from AI responses."""
import pytest

from app.ai.order_collector import (
    clean_response_for_customer,
    extract_order_from_response,
)


class TestOrderCollector:

    def test_extract_order_from_json_block(self):
        response = '''Great! Your order is confirmed!

```json
{"action": "create_order", "order_data": {
  "product_name": "Cotton Galabiya",
  "quantity": 2,
  "customer_name": "Fatima",
  "customer_phone": "01012345678",
  "governorate": "cairo",
  "city": "Cairo",
  "area": "Maadi",
  "address_detail": "15 Road 9, Maadi",
  "payment_method": "cod"
}}
```'''
        order = extract_order_from_response(response)
        assert order is not None
        # Legacy single-item format is converted to items array
        assert len(order["items"]) == 1
        assert order["items"][0]["product_name"] == "Cotton Galabiya"
        assert order["items"][0]["quantity"] == 2
        assert order["customer_name"] == "Fatima"
        assert order["payment_method"] == "cod"

    def test_extract_order_missing_fields(self):
        response = '''```json
{"action": "create_order", "order_data": {
  "product_name": "Galabiya",
  "customer_name": "Test"
}}
```'''
        order = extract_order_from_response(response)
        assert order is None

    def test_extract_order_invalid_phone(self):
        response = '''```json
{"action": "create_order", "order_data": {
  "product_name": "Galabiya",
  "customer_name": "Test",
  "customer_phone": "12345",
  "governorate": "cairo",
  "city": "Cairo",
  "address_detail": "House 1"
}}
```'''
        order = extract_order_from_response(response)
        assert order is None

    def test_extract_no_order(self):
        response = "Our Galabiya costs 450 EGP. Would you like to order?"
        order = extract_order_from_response(response)
        assert order is None

    def test_clean_response_removes_json(self):
        response = '''Your order is confirmed! Thank you!

```json
{"action": "create_order", "order_data": {"product_name": "Galabiya"}}
```'''
        cleaned = clean_response_for_customer(response)
        assert "json" not in cleaned
        assert "create_order" not in cleaned
        assert "order is confirmed" in cleaned

    def test_clean_response_no_json(self):
        response = "Hello! How can I help you?"
        cleaned = clean_response_for_customer(response)
        assert cleaned == response

    def test_extract_order_defaults(self):
        response = '''```json
{"action": "create_order", "order_data": {
  "product_name": "Leather Bag",
  "customer_name": "Omar",
  "customer_phone": "01112345678",
  "governorate": "alexandria",
  "city": "Alexandria",
  "address_detail": "Corniche Road"
}}
```'''
        order = extract_order_from_response(response)
        assert order is not None
        # Defaults: quantity=1, payment_method="cod"
        assert len(order["items"]) == 1
        assert order["items"][0]["quantity"] == 1
        assert order["payment_method"] == "cod"
