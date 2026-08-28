"""Call external order placement API after order is created in our system.

Replaces {{placeholders}} in the request template with actual order values,
calls the API, and saves the result on the order record.
"""
import json
import logging
import re
from base64 import b64encode
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


async def call_order_api(db: AsyncSession, tenant: Tenant, order: Order) -> dict:
    """Call the tenant's external order API. Returns status dict.

    Always saves result on the order record.
    """
    config = tenant.order_api_config
    if not config or not config.get("enabled") or not config.get("url"):
        order.api_status = "not_configured"
        await db.flush()
        return {"status": "not_configured"}

    url = config["url"]
    method = config.get("method", "POST").upper()
    auth_type = config.get("auth_type", "none")

    # Build headers
    headers = {"Content-Type": "application/json"}
    if auth_type == "api_key":
        key_header = config.get("auth_key", "X-API-Key")
        headers[key_header] = config.get("auth_value", "")
    elif auth_type == "bearer":
        headers["Authorization"] = f"Bearer {config.get('auth_value', '')}"
    elif auth_type == "basic":
        creds = b64encode(f"{config.get('auth_user', '')}:{config.get('auth_pass', '')}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"

    # Build request body from template
    template = config.get("request_template", "{}")
    body = _fill_template(template, order)

    # Make the API call
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers, params=body if isinstance(body, dict) else None)
            else:
                resp = await client.request(method, url, headers=headers, json=body)

        status_code = resp.status_code
        response_text = resp.text[:2000]  # Cap stored response

        # Determine success
        if 200 <= status_code < 300:
            # Try to extract external order ID from response
            external_id = _extract_order_id(response_text)

            # Check if response body indicates an error despite 2xx status
            try:
                resp_json = resp.json()
                if _is_error_response(resp_json):
                    order.api_status = "failed"
                    order.api_response = response_text
                    order.api_status_code = status_code
                    order.api_called_at = datetime.utcnow()
                    error_msg = resp_json.get("error", resp_json.get("message", "Unknown error in response"))
                    await db.flush()
                    logger.warning(f"Order API {status_code} but error in body: {error_msg}")
                    return {"status": "failed", "code": status_code, "error": str(error_msg)}
            except (json.JSONDecodeError, ValueError):
                pass

            order.api_status = "success"
            order.api_response = response_text
            order.api_status_code = status_code
            order.api_called_at = datetime.utcnow()
            order.api_external_id = external_id
            await db.flush()

            logger.info(f"Order API success: {status_code} external_id={external_id}")
            return {"status": "success", "code": status_code, "external_id": external_id}

        else:
            order.api_status = "failed"
            order.api_response = response_text
            order.api_status_code = status_code
            order.api_called_at = datetime.utcnow()
            await db.flush()

            logger.warning(f"Order API failed: {status_code} {response_text[:200]}")
            return {"status": "failed", "code": status_code, "error": response_text[:200]}

    except httpx.TimeoutException:
        order.api_status = "failed"
        order.api_response = "Request timed out after 30 seconds"
        order.api_status_code = 0
        order.api_called_at = datetime.utcnow()
        await db.flush()
        return {"status": "failed", "code": 0, "error": "Timeout"}

    except Exception as e:
        order.api_status = "failed"
        order.api_response = str(e)[:500]
        order.api_status_code = 0
        order.api_called_at = datetime.utcnow()
        await db.flush()
        logger.error(f"Order API error: {e}")
        return {"status": "failed", "code": 0, "error": str(e)[:200]}


def _fill_template(template_str: str, order: Order) -> dict:
    """Replace {{placeholders}} in template with order values."""
    # Build items JSON
    items_list = []
    for item in order.items:
        items_list.append({
            "name": item.product_name,
            "qty": item.quantity,
            "price": float(item.unit_price),
            "total": float(item.total_price),
        })

    replacements = {
        "{{customer_name}}": order.customer_name or "",
        "{{customer_phone}}": order.customer_phone or "",
        "{{governorate}}": getattr(order, "governorate", "") or "",
        "{{city}}": getattr(order, "city", "") or "",
        "{{area}}": getattr(order, "area", "") or "",
        "{{address_detail}}": order.address_detail or "",
        "{{payment_method}}": order.payment_method or "cod",
        "{{payment_phone_last2}}": order.payment_phone_last2 or "",
        "{{payment_trx_id}}": order.payment_trx_id or "",
        "{{subtotal}}": str(float(order.subtotal)),
        "{{delivery_charge}}": str(float(order.delivery_charge)),
        "{{total}}": str(float(order.total)),
        "{{order_number}}": order.order_number or "",
        "{{notes}}": order.notes or "",
        "{{items_json}}": json.dumps(items_list, ensure_ascii=False),
    }

    result = template_str
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse filled template as JSON: {result[:200]}")
        return {}


def _extract_order_id(response_text: str) -> str | None:
    """Try to extract an order/ID from the API response."""
    try:
        data = json.loads(response_text)
        for key in ["order_id", "id", "orderId", "order_number", "orderNumber", "reference"]:
            val = data.get(key)
            if val:
                return str(val)
        # Check nested
        if isinstance(data.get("data"), dict):
            for key in ["order_id", "id", "orderId"]:
                val = data["data"].get(key)
                if val:
                    return str(val)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _is_error_response(data: dict) -> bool:
    """Check if a 200/201 response actually contains an error."""
    if isinstance(data, dict):
        # Common patterns: {"error": "..."}, {"success": false}, {"status": "error"}
        if data.get("error") and data.get("error") is not True:
            return True
        if data.get("success") is False:
            return True
        if data.get("status") in ("error", "failed", "failure"):
            return True
    return False
