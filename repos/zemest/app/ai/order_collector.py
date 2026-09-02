from __future__ import annotations

import logging
from typing import Any

from app.utils.safe_json import extract_first_json_object
from app.utils.phone import validate_egyptian_phone

logger = logging.getLogger(__name__)

# Anchors: extraction starts at the first occurrence of either the fenced
# ```json block or the raw action marker.
_ORDER_ANCHOR = '{"action"'

# Field whitelist — everything else the LLM invents is dropped (audit A6-H4).
_ALLOWED_FIELDS = frozenset({
    "items", "product_name", "quantity",
    "customer_name", "customer_phone",
    "governorate", "city", "area", "address_detail",
    "payment_method", "payment_phone_last2", "payment_trx_id",
})

# Payment methods the order pipeline actually supports downstream.
_PAYMENT_METHODS = frozenset({"cod", "vodafone_cash", "instapay", "fawry"})

# Quantity bounds: an LLM must never create an order for 10,000 units.
_MIN_QTY, _MAX_QTY = 1, 999


def extract_order_from_response(response_text: str) -> dict | None:
    """Extract order JSON from an AI response if present.

    Security/correctness notes (audit A6-H3/H4):
    - Uses :func:`app.utils.safe_json.extract_first_json_object` (balanced
      ``json.JSONDecoder().raw_decode``) instead of a greedy ``.*\\}`` regex
      that spanned to the LAST brace in the response and silently dropped
      perfectly valid orders whenever trailing prose contained any brace.
    - Non-dict ``order_data`` (LLM emits a list) is rejected instead of
      crashing with an uncaught ``AttributeError``.
    - Never raises for any string input.
    """
    if not response_text or not isinstance(response_text, str):
        return None

    data_obj, _start, _end = extract_first_json_object(
        response_text, anchor=_ORDER_ANCHOR
    )
    if not isinstance(data_obj, dict):
        return None
    if data_obj.get("action") != "create_order":
        return None

    order_data = data_obj.get("order_data")
    if not isinstance(order_data, dict):
        logger.warning("order_data is not a dict — rejecting")
        return None

    return validate_order_data(order_data)


def _coerce_quantity(raw) -> int | None:
    """Coerce an LLM-emitted quantity into an int in [1, 999], else None.

    Accepts int, float-with-integer-value, and numeric strings ("2").
    Rejects 0, negatives, fractions, absurd values, and garbage.
    """
    if isinstance(raw, bool):  # bool is an int subclass — reject explicitly
        return None
    value: int | None = None
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, float):
        value = int(raw) if raw.is_integer() else None
    elif isinstance(raw, str):
        stripped = raw.strip()
        if stripped.isdigit():
            value = int(stripped)
        else:
            try:
                as_float = float(stripped)
                value = int(as_float) if as_float.is_integer() else None
            except ValueError:
                return None
    if value is None:
        return None
    if not (_MIN_QTY <= value <= _MAX_QTY):
        return None
    return value


def validate_order_data(data: dict) -> dict | None:
    """Validate extracted order data. Supports both single and multi-item orders.

    Hardening (audit A6-H4 / A5-H4):
    - Pure function: returns a *copy* with only whitelisted fields — the
      caller's dict is never mutated by pop/setdefault side effects.
    - ``quantity`` is coerced and range-checked [1, 999] (previously ``"2"``,
      ``2.5``, ``0`` and ``-1`` all passed straight into order creation).
    - ``payment_method`` is whitelisted; anything else falls back to ``cod``.
    - Non-dict input is rejected instead of raising.
    - Items without a usable quantity are rejected (whole order → None) so a
      hallucinated payload can never create an order with garbage quantities.
    """
    if not isinstance(data, dict):
        return None

    # Required customer fields
    required = ["customer_name", "customer_phone", "governorate", "city", "address_detail"]
    for field_name in required:
        if not data.get(field_name):
            logger.warning(f"Missing required order field: {field_name}")
            return None
    elif isinstance(raw, float):
        return None  # "2.5 items" is a hallucination, not an order
    else:
        return None
    if not 1 <= qty <= _MAX_QTY:
        return None
    return qty


def _clean_str(value: Any, max_len: int = 255) -> str:
    """Coerce to a bounded, stripped string. Non-strings become empty."""
    if isinstance(value, str):
        return value.strip()[:max_len]
    return ""


def validate_order_data(data: dict) -> dict | None:
    """Validate + normalize extracted order data.

    Contract:
    * Only whitelisted fields survive (no LLM-invented extras).
    * ``quantity`` is an int in [1, 99] — strings coerced, floats rejected.
    * ``payment_method`` maps onto the supported set.
    * Customer PII strings are length-bounded.
    * PRICE FIELDS ARE INTENTIONALLY DROPPED: prices come from the product
      catalog at order-creation time (``agent.py``), never from the LLM.
    * Pure function: never mutates the input dict.
    """
    if not isinstance(data, dict):
        return None

    clean: dict = {
        "customer_name": str(data["customer_name"]).strip(),
        "customer_phone": str(phone).strip(),
        "governorate": str(data["governorate"]).strip(),
        "city": str(data["city"]).strip(),
        "address_detail": str(data["address_detail"]).strip(),
        "area": str(data.get("area") or "").strip(),
    }

    # Payment method whitelist
    payment = (data.get("payment_method") or "cod").strip().lower()
    if payment not in _PAYMENT_METHODS:
        payment = "cod"
    clean["payment_method"] = payment
    clean["payment_phone_last2"] = str(data.get("payment_phone_last2") or "").strip()
    clean["payment_trx_id"] = str(data.get("payment_trx_id") or "").strip()

    # Handle both formats:
    # New: {"items": [{"product_name": "...", "quantity": 1}, ...]}
    # Old: {"product_name": "...", "quantity": 1}
    if "items" not in data:
        # Old format — convert to items array
        if data.get("product_name"):
            raw_qty = data.get("quantity", 1)
        else:
            logger.warning("No items or product_name in order")
            return None
        items_raw = [{"product_name": data.get("product_name"), "quantity": raw_qty}]
    else:
        items_raw = data["items"]
        if not items_raw or not isinstance(items_raw, list):
            logger.warning("Items must be a non-empty array")
            return None

    items: list[dict] = []
    for item in items_raw:
        if not isinstance(item, dict):
            logger.warning("Item is not a dict — rejecting order")
            return None
        product_name = item.get("product_name")
        if not product_name or not str(product_name).strip():
            logger.warning("Item missing product_name")
            return None
        quantity = _coerce_quantity(item.get("quantity", 1))
        if quantity is None:
            logger.warning(f"Item quantity invalid: {item.get('quantity')!r}")
            return None
        items.append({
            "product_name": str(product_name).strip(),
            "quantity": quantity,
        })

    clean["items"] = items
    return clean


def clean_response_for_customer(response_text: str) -> str:
    """Remove the JSON block from response before sending to customer.

    Uses the same balanced extraction as :func:`extract_order_from_response`
    (via :mod:`app.utils.safe_json`) so the removed span is exactly the
    order JSON object — greedy ``.*\\}``` patterns previously deleted
    legitimate prose between the JSON and a later brace.
    """
    if not response_text or not isinstance(response_text, str):
        return ""

    cleaned = response_text

    # Remove any fenced ```json blocks (order or otherwise) verbatim.
    import re
    cleaned = re.sub(r"```json\s*\{.*?\}\s*```", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"```json\s*(.*?)```", "", cleaned, flags=re.DOTALL)

    # Remove a raw (unfenced) create_order object using balanced extraction.
    obj, start, end = extract_first_json_object(cleaned, anchor=_ORDER_ANCHOR)
    if obj is not None and obj.get("action") == "create_order":
        cleaned = cleaned[:start] + cleaned[end:]

    # Remove any leftover empty code fences.
    cleaned = re.sub(r"```\s*```", "", cleaned)

    return cleaned.strip()
