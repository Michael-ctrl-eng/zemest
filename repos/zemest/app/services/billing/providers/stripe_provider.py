"""Stripe provider — international cards + Apple Pay + Google Pay.

Hand-rolled async REST client (same posture as paymob.py: pooled httpx,
config-gated, no SDK dependency to audit). Recurrence is STRIPE-MANAGED
(Stripe Subscriptions with smart retries/dunning); our webhook processor
applies state changes from ``invoice.paid`` / ``customer.subscription.*``
events so activation, cancellation and reactivation are driven by verified
webhooks — never by the browser.

Webhook signature (Stripe spec, implemented in verify_webhook_signature):
    Stripe-Signature: t=<unix ts>,v1=<hex hmac>
    signed_payload = f"{t}.{raw_body_bytes}"
    expected       = HMAC-SHA256(signed_payload, STRIPE_WEBHOOK_SECRET)
    + 5-minute timestamp tolerance (replay protection).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Stripe sends form-encoded bodies; timeouts mirror the pooled-client policy.
_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)
_REPLAY_TOLERANCE_SECONDS = 300


class StripeError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class StripeConfigError(StripeError):
    pass


_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# --------------------------------------------------------------------------- #
# Webhook signature verification — fail closed
# --------------------------------------------------------------------------- #
def parse_stripe_signature(header: str) -> tuple[int, list[str]]:
    """Parse ``t=...,v1=...`` → (timestamp, v1 signatures). Raises ValueError."""
    ts = 0
    sigs: list[str] = []
    for part in header.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        if key == "t":
            try:
                ts = int(value)
            except ValueError as e:
                raise ValueError(f"non-integer timestamp {value!r}") from e
        elif key == "v1":
            sigs.append(value)
    if ts == 0 or not sigs:
        raise ValueError("missing t or v1 in Stripe-Signature")
    return ts, sigs


def verify_webhook_signature(
    raw_body: bytes, signature_header: str, secret: str, tolerance: int = _REPLAY_TOLERANCE_SECONDS
) -> bool:
    """Constant-time Stripe signature check with replay window.

    Fails closed on: missing secret, malformed header, unknown timestamp
    format, expired timestamp (replay), and any v1 mismatch.
    """
    if not secret or not signature_header or not raw_body:
        return False
    try:
        ts, sigs = parse_stripe_signature(signature_header)
    except ValueError:
        return False
    if abs(time.time() - ts) > tolerance:
        return False
    signed_payload = f"{ts}.".encode("utf-8") + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return any(
        hmac.compare_digest(expected.encode("ascii"), s.encode("ascii"))
        for s in sigs
        if s
    )


# --------------------------------------------------------------------------- #
# REST client — form-encoded per Stripe API convention
# --------------------------------------------------------------------------- #
class StripeClient:
    def __init__(self, secret_key: str | None = None, api_base: str | None = None):
        s = get_settings()
        self.secret_key = secret_key if secret_key is not None else s.STRIPE_SECRET_KEY
        self.api_base = (api_base or s.STRIPE_API_BASE or "https://api.stripe.com").rstrip("/")

    # -- internals ---------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        if not self.secret_key:
            raise StripeConfigError("STRIPE_SECRET_KEY is not configured")
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        url = f"{self.api_base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        body = _flatten_form(data) if data else None
        try:
            resp = await _get_client().request(method, url, headers=headers, content=body)
        except httpx.TimeoutException as e:
            raise StripeError(f"Stripe request timed out: {e}") from e
        except httpx.HTTPError as e:
            raise StripeError(f"Stripe connection error: {e}") from e
        text = resp.text[:2000]
        if resp.status_code >= 400:
            logger.warning("Stripe API error %s %s: %s", method, path, text)
            raise StripeError(
                f"Stripe API returned {resp.status_code}", resp.status_code, text
            )
        try:
            return resp.json()
        except ValueError as e:
            raise StripeError("Invalid JSON in Stripe response", resp.status_code, text) from e

    # -- objects -----------------------------------------------------------
    async def ensure_customer(self, user_id: str, email: str, name: str) -> str:
        """Create (or reuse via idempotency key) a Stripe Customer → cus_..."""
        data = {"email": email, "name": name, "metadata[user_id]": user_id}
        out = await self._request(
            "POST", "/v1/customers", data=data, idempotency_key=f"cust-{user_id}"
        )
        return str(out.get("id") or "")

    async def create_checkout_subscription(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        client_reference_id: str,
    ) -> dict:
        """Hosted Checkout in ``subscription`` mode.

        Cards + Apple Pay + Google Pay are offered automatically by the
        hosted page (payment method types are attached to the Price in the
        Stripe dashboard). The browser only ever sees the hosted URL —
        no key material client-side. Returns {session_id, url}.
        """
        data = {
            "mode": "subscription",
            "customer": customer_id,
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": 1,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": client_reference_id,
            "metadata[user_id]": client_reference_id,
            "subscription_data[metadata][user_id]": client_reference_id,
        }
        out = await self._request(
            "POST", "/v1/checkout/sessions", data=data,
            idempotency_key=f"co-{client_reference_id}",
        )
        return {"session_id": str(out.get("id") or ""), "url": str(out.get("url") or "")}

    async def cancel_subscription(
        self, stripe_subscription_id: str, at_period_end: bool = True
    ) -> dict:
        if at_period_end:
            return await self._request(
                "POST", f"/v1/subscriptions/{stripe_subscription_id}",
                data={"cancel_at_period_end": "true"},
                idempotency_key=f"cancel-{stripe_subscription_id}",
            )
        return await self._request(
            "DELETE", f"/v1/subscriptions/{stripe_subscription_id}",
            idempotency_key=f"cancel-{stripe_subscription_id}",
        )

    async def reactivate_subscription(self, stripe_subscription_id: str) -> dict:
        return await self._request(
            "POST",
            f"/v1/subscriptions/{stripe_subscription_id}",
            data={"cancel_at_period_end": "false"},
            idempotency_key=f"resume-{stripe_subscription_id}",
        )


def _flatten_form(data: dict[str, Any]) -> bytes:
    """Stripe form encoding: nested dicts → ``a[b]=c`` keys; bools → true/false."""
    pairs: list[tuple[str, str]] = []

    def _walk(prefix: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, bool):
            pairs.append((prefix, "true" if value else "false"))
        elif isinstance(value, dict):
            for k, v in value.items():
                key = f"{prefix}[{k}]" if prefix else str(k)
                _walk(key, v)
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                _walk(f"{prefix}[{i}]", v)
        else:
            pairs.append((prefix, str(value)))

    for k, v in data.items():
        _walk(str(k), v)
    return urlencode(pairs).encode("utf-8")
