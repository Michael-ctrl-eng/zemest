from __future__ import annotations

import json
import re
import logging

from app.utils.phone import validate_egyptian_phone

logger = logging.getLogger(__name__)


def extract_order_from_response(response_text: str) -> dict | None:
    """Extract order JSON from AI response if present."""
    # Look for JSON block in response
    json_match = re.search(
        r'```json\s*(\{.*?\})\s*```',
        response_text,
        re.DOTALL,
    )
    if not json_match:
        # Try without code block — match nested JSON
        json_match = re.search(
            r'\{"action":\s*"create_order".*\}',
            response_text,
            re.DOTALL,
        )

    if not json_match:
        return None

    try:
        raw = json_match.group(1) if json_match.lastindex else json_match.group(0)
        data = json.loads(raw)
        if data.get("action") == "create_order":
            order_data = data.get("order_data", {})
            return validate_order_data(order_data)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse order JSON: {e}")

    return None


def validate_order_data(data: dict) -> dict | None:
    """Validate extracted order data. Supports both single and multi-item orders."""

    # Required customer fields
    required = ["customer_name", "customer_phone", "governorate", "city", "address_detail"]
    for field in required:
        if not data.get(field):
            logger.warning(f"Missing required order field: {field}")
            return None

    # Validate phone
    phone = data["customer_phone"]
    if not validate_egyptian_phone(phone):
        logger.warning(f"Invalid Egyptian phone number: {phone}")
        return None

    # Handle both formats:
    # New: {"items": [{"product_name": "...", "quantity": 1}, ...]}
    # Old: {"product_name": "...", "quantity": 1}
    if "items" not in data:
        # Old format — convert to items array
        if data.get("product_name"):
            data["items"] = [{
                "product_name": data.pop("product_name"),
                "quantity": data.pop("quantity", 1),
            }]
        else:
            logger.warning("No items or product_name in order")
            return None
    else:
        # Validate items array
        items = data["items"]
        if not items or not isinstance(items, list):
            logger.warning("Items must be a non-empty array")
            return None
        for item in items:
            if not item.get("product_name"):
                logger.warning("Item missing product_name")
                return None
            item.setdefault("quantity", 1)

    # Set defaults
    data.setdefault("payment_method", "cod")
    data.setdefault("area", "")
    data.setdefault("payment_phone_last2", "")
    data.setdefault("payment_trx_id", "")

    return data


def clean_response_for_customer(response_text: str) -> str:
    """Remove the JSON block from response before sending to customer."""
    cleaned = re.sub(r'```json\s*\{.*?\}\s*```', '', response_text, flags=re.DOTALL)
    cleaned = re.sub(
        r'\{"action":\s*"create_order".*\}',
        '',
        cleaned,
        flags=re.DOTALL,
    )
    return cleaned.strip()
