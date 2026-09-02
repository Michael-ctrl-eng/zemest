from __future__ import annotations

import json
import re
import logging
from typing import Any

from app.utils.phone import validate_egyptian_phone

logger = logging.getLogger(__name__)

#: Fields the LLM is allowed to contribute to an order. Everything else it
#: invents (prices, totals, discounts, "notes to seller") is dropped — the
#: price of an order comes from the product catalog, never the model.
_ALLOWED_ITEM_FIELDS = {"product_name", "quantity"}

_ALLOWED_TOP_FIELDS = {
    "customer_name",
    "customer_phone",
    "governorate",
    "city",
    "area",
    "address_detail",
    "items",
    "payment_method",
}

#: Payment methods the platform actually supports (matches
#: ``payments.py``/``prompts.py`` guidance). Anything else the LLM emits
#: falls back to cash-on-delivery.
_SUPPORTED_PAYMENT_METHODS = {"cod", "instapay", "vodafone_cash"}

#: Quantity bounds: 1..99. The LLM hallucinating "quantity": 5000 or 2.5
#: must never become an order line.
_MAX_QTY = 99


def _extract_balanced_json_objects(text: str) -> list[str]:
    """Extract candidate JSON object spans using balanced-brace scanning.

    Why not regex: the previous ``r'\\{"action":...*\\}'`` was greedy to the
    LAST ``}`` in the whole response — anything after the order JSON (a
    second JSON block, an emoji, a literal brace) made the span unparseable
    and the order was silently DROPPED while the customer was told it was
    placed (audit H3: revenue loss). A linear brace-counter cannot backtrack
    and returns the exact object boundaries.
    """
    objects: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    objects.append(text[start : i + 1])
                    start = -1
    return objects


def extract_order_from_response(response_text: str) -> dict | None:
    """Extract an order from the AI response, if one is present.

    Tries, in order:
    1. Fenced ```` ```json {...}``` ```` blocks (captured group, exact span)
    2. Balanced-brace scan of the whole text — every top-level object is a
       candidate; the FIRST one whose ``action`` is ``create_order`` wins.

    Never raises; returns ``None`` when no valid order is present.
    """
    if not response_text or "{" not in response_text:
        return None

    candidates: list[str] = []

    fenced = re.findall(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if fenced:
        candidates.extend(fenced)

    candidates.extend(_extract_balanced_json_objects(response_text))

    for raw in candidates:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue  # LLM emitted a list/number — skip, don't crash
        if data.get("action") != "create_order":
            continue
        order_data = data.get("order_data")
        if not isinstance(order_data, dict):
            continue  # order_data must be an object
        validated = validate_order_data(order_data)
        if validated is not None:
            return validated
    return None


def _coerce_quantity(raw: Any) -> int | None:
    """Quantity must be an integer in [1, MAX]. Accepts int or the string
    "3" (models emit both); rejects floats, negatives, zero, garbage."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        qty = raw
    elif isinstance(raw, str):
        try:
            qty = int(raw.strip())
        except ValueError:
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

    out: dict[str, Any] = {}

    # --- required customer fields -----------------------------------------
    customer_name = _clean_str(data.get("customer_name"))
    phone = _clean_str(data.get("customer_phone"))
    governorate = _clean_str(data.get("governorate"))
    city = _clean_str(data.get("city"))
    address_detail = _clean_str(data.get("address_detail"), max_len=500)

    if not customer_name:
        logger.warning("Order rejected: missing customer_name")
        return None
    if not phone or not validate_egyptian_phone(phone):
        logger.warning("Order rejected: invalid Egyptian phone %r", phone)
        return None
    if not governorate:
        logger.warning("Order rejected: missing governorate")
        return None
    if not city:
        logger.warning("Order rejected: missing city")
        return None
    if not address_detail:
        logger.warning("Order rejected: missing address_detail")
        return None

    out["customer_name"] = customer_name
    out["customer_phone"] = phone
    out["governorate"] = governorate
    out["city"] = city
    out["address_detail"] = address_detail
    out["area"] = _clean_str(data.get("area"))

    # --- items --------------------------------------------------------------
    items_in = data.get("items")
    if items_in is None:
        # Old single-item format: promote product_name/quantity to items.
        items_in = [
            {
                "product_name": data.get("product_name"),
                "quantity": data.get("quantity", 1),
            }
        ]

    if not isinstance(items_in, list) or not items_in:
        logger.warning("Order rejected: items is not a non-empty list")
        return None

    items_out: list[dict[str, Any]] = []
    for item in items_in:
        if not isinstance(item, dict):
            return None
        name = _clean_str(item.get("product_name"), max_len=255)
        if not name:
            logger.warning("Order rejected: item missing product_name")
            return None
        qty = _coerce_quantity(item.get("quantity", 1))
        if qty is None:
            logger.warning("Order rejected: invalid quantity %r", item.get("quantity"))
            return None
        # NOTE: price/unit_price/total keys from the LLM are deliberately
        # dropped here — catalog-only pricing downstream.
        items_out.append({"product_name": name, "quantity": qty})

    if not items_out:
        return None
    out["items"] = items_out

    # --- payment method ------------------------------------------------------
    payment = _clean_str(data.get("payment_method")).lower()
    out["payment_method"] = payment if payment in _SUPPORTED_PAYMENT_METHODS else "cod"

    return out


def clean_response_for_customer(response_text: str) -> str:
    """Remove order-JSON blocks from the response before sending to customer.

    Uses the same balanced-brace scan so trailing braces in the prose can't
    swallow the whole message (the old greedy regex could delete the entire
    response body).
    """
    cleaned = re.sub(r"```json\s*\{.*?\}\s*```", "", response_text, flags=re.DOTALL)
    for obj in _extract_balanced_json_objects(cleaned):
        if '"create_order"' in obj:
            cleaned = cleaned.replace(obj, "")
    return cleaned.strip()
