"""Payoneer Checkout provider — the PRIMARY billing rail (post-legacy).

Hardened integration surface (the security posture the audit demanded):

* **Checkout sessions** — ``POST {base}/v2/checkout/sessions`` with a
  bearer API token and an ``Idempotency-Key`` header derived from OUR
  reference, so a retried subscribe/renew request can never create a
  second chargeable session on Payoneer's side.
* **Webhook verification (fail-closed)** — HMAC-SHA256 (or SHA512) over
  the EXACT raw request bytes, compared with ``hmac.compare_digest``.
  Never a re-serialized JSON copy: key reordering breaks signatures.
  The signature header is ``X-Payoneer-Signature`` by default and is
  env-overridable (``PAYONEER_SIG_HEADER``) because portal integrations
  occasionally rename it.
* **Amount parsing** — webhook amounts are validated against the expected
  invoice amount by the webhook processor (this module only parses and
  normalizes them into minor units).
* No card data, PANs or secrets are ever logged or persisted — the raw
  payload stored on transactions is redacted upstream.

Env contract (``app/config.py``): ``PAYONEER_API_TOKEN``,
``PAYONEER_API_BASE_URL``, ``PAYONEER_PARTNER_ID``, ``PAYONEER_PROGRAM_ID``,
``PAYONEER_WEBHOOK_SECRET``, ``PAYONEER_WEBHOOK_ALGO``,
``PAYONEER_SIG_HEADER``, ``PAYONEER_CURRENCY``.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.config import get_settings
from app.services.billing.providers.base import (
    CheckoutResult,
    PaymentProvider,
    ProviderApiError,
    ProviderConfigError,
)

logger = logging.getLogger(__name__)

CHECKOUT_SESSIONS_PATH = "/v2/checkout/sessions"
PAYOUT_STATUS_PATH = "/v4/payouts/{payout_id}"

# Checkout sessions expire quickly; our invoices stay payable longer, but
# a stale session URL is useless to the payer.
SESSION_TTL_MINUTES = 60

# Shared pooled HTTP client (same lifecycle pattern as paymob.py /
# llm_client.py — one client per process, lazily created).
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


async def close_client() -> None:
    """Release pooled connections (call on app shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# --------------------------------------------------------------------------- #
# Webhook verification — HMAC over the EXACT raw bytes (fail-closed)
# --------------------------------------------------------------------------- #
def verify_webhook_signature(
    raw_body: bytes,
    received_signature: str,
    secret: str,
    algorithm: str = "sha256",
) -> bool:
    """Constant-time HMAC check over the raw request bytes.

    * Empty body / empty signature / empty secret → False (fail closed).
    * ``algorithm`` is one of ``sha256`` | ``sha512`` (config-driven).
    * Non-hex junk input never raises — it just fails.
    """
    if not raw_body or not received_signature or not secret:
        return False
    algo = (algorithm or "sha256").lower()
    if algo not in ("sha256", "sha512"):
        algo = "sha256"
    digestmod = hashlib.sha256 if algo == "sha256" else hashlib.sha512
    expected = hmac.new(secret.encode("utf-8"), raw_body, digestmod).hexdigest()
    try:
        return hmac.compare_digest(expected, received_signature.strip().lower())
    except (TypeError, ValueError):
        return False


def extract_signature(headers: dict | httpx.Headers) -> str:
    """Pull the signature header (name configurable) from the request."""
    header_name = get_settings().PAYONEER_SIG_HEADER or "X-Payoneer-Signature"
    if isinstance(headers, httpx.Headers):
        return str(headers.get(header_name) or headers.get(header_name.lower()) or "")
    for key, value in headers.items():
        if key.lower() == header_name.lower():
            return str(value)
    return ""


def parse_amount(raw: Any) -> int | None:
    """Parse a webhook amount into integer minor units (cents).

    Payoneer delivers amounts as either a decimal number or an integer in
    minor units depending on the endpoint; both are handled. Returns None
    for garbage input (the caller treats that as an amount mismatch).
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    try:
        if isinstance(raw, float):
            return int(Decimal(str(raw)).scaleb(2))
        return int(Decimal(str(raw)).scaleb(2))
    except (ArithmeticError, ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
class PayoneerProvider(PaymentProvider):
    """Primary rail — Payoneer Checkout (card / wallet, USD)."""

    name = "payoneer"

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
        partner_id: str | None = None,
        program_id: str | None = None,
        currency: str | None = None,
        webhook_secret: str | None = None,
        webhook_algo: str | None = None,
    ):
        s = get_settings()
        self.api_token = api_token if api_token is not None else s.PAYONEER_API_TOKEN
        self.base_url = (base_url or s.PAYONEER_API_BASE_URL or "https://api.payoneer.com").rstrip("/")
        self.partner_id = partner_id if partner_id is not None else s.PAYONEER_PARTNER_ID
        self.program_id = program_id if program_id is not None else s.PAYONEER_PROGRAM_ID
        self.currency = currency or s.PAYONEER_CURRENCY or "USD"
        self.webhook_secret = (
            webhook_secret if webhook_secret is not None else s.PAYONEER_WEBHOOK_SECRET
        )
        self.webhook_algo = webhook_algo or s.PAYONEER_WEBHOOK_ALGO or "sha256"

    def is_configured(self) -> bool:
        return bool(self.api_token)

    # -- checkout --------------------------------------------------------- #
    def build_checkout_payload(
        self,
        *,
        amount: Decimal,
        currency: str,
        reference: str,
        customer_email: str = "",
        description: str = "",
        success_url: str = "",
        failure_url: str = "",
        webhook_url: str = "",
    ) -> dict:
        """Pure payload builder (unit-testable without HTTP)."""
        payload: dict = {
            "amount": str(amount),
            "currency": currency,
            "client_reference_id": reference,
            "description": description or f"Zemest subscription {reference}",
        }
        if customer_email:
            payload["payer"] = {"email": customer_email}
        if self.partner_id:
            payload["partner_id"] = self.partner_id
        if self.program_id:
            payload["program_id"] = self.program_id
        if success_url:
            payload["success_url"] = success_url
        if failure_url:
            payload["failure_url"] = failure_url
        if webhook_url:
            payload["webhook_url"] = webhook_url
        return payload

    async def create_checkout(
        self,
        *,
        amount: Decimal,
        currency: str,
        reference: str,
        customer_email: str = "",
        description: str = "",
        success_url: str = "",
        failure_url: str = "",
        webhook_url: str = "",
    ) -> CheckoutResult:
        if not self.api_token:
            raise ProviderConfigError(
                "Payoneer API token is not configured (PAYONEER_API_TOKEN)"
            )
        payload = self.build_checkout_payload(
            amount=amount,
            currency=currency,
            reference=reference,
            customer_email=customer_email,
            description=description,
            success_url=success_url,
            failure_url=failure_url,
            webhook_url=webhook_url,
        )
        url = f"{self.base_url}{CHECKOUT_SESSIONS_PATH}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            # Deterministic idempotency: same reference → same key, so a
            # network retry can never double-create a chargeable session.
            "Idempotency-Key": f"zst-billing-{reference}",
        }
        try:
            resp = await _get_client().post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise ProviderApiError(f"Payoneer checkout request timed out: {e}") from e
        except httpx.HTTPError as e:
            raise ProviderApiError(f"Payoneer connection error: {e}") from e

        body_text = resp.text[:2000]
        if resp.status_code >= 400:
            logger.warning(
                "Payoneer checkout API error %s: %s", resp.status_code, body_text
            )
            raise ProviderApiError(
                f"Payoneer checkout API returned {resp.status_code}",
                status_code=resp.status_code,
                body=body_text,
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise ProviderApiError(
                "Invalid JSON in Payoneer response", resp.status_code, body_text
            ) from e

        session_id = str(
            data.get("session_id")
            or data.get("checkout_session_id")
            or data.get("id")
            or ""
        )
        checkout_url = str(data.get("checkout_url") or data.get("redirect_url") or "")
        if not session_id or not checkout_url:
            raise ProviderApiError(
                "Payoneer checkout response missing session_id/checkout_url",
                body=body_text,
            )
        logger.info("Payoneer checkout session created (ref=%s)", reference)
        return CheckoutResult(
            provider=self.name,
            provider_reference=session_id,
            checkout_url=checkout_url,
            amount=amount,
            currency=currency,
            expires_at=datetime.utcnow() + timedelta(minutes=SESSION_TTL_MINUTES),
            raw=data,
        )

    # -- void -------------------------------------------------------------- #
    async def cancel(self, provider_reference: str) -> bool:
        """Void an unpaid checkout session (best effort).

        Payoneer checkout sessions expire on their own after
        SESSION_TTL_MINUTES; an explicit DELETE lets the processor skip
        waiting. A 404/409 (already consumed/expired) counts as NOT
        canceled — the caller falls back to voiding the local invoice.
        """
        if not self.api_token or not provider_reference:
            return False
        url = f"{self.base_url}{CHECKOUT_SESSIONS_PATH}/{provider_reference}"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        try:
            resp = await _get_client().delete(url, headers=headers)
        except httpx.HTTPError as e:
            logger.warning("Payoneer void failed (session=%s): %s", provider_reference, e)
            return False
        if 200 <= resp.status_code < 300:
            return True
        logger.info(
            "Payoneer void not confirmed (session=%s status=%s)",
            provider_reference, resp.status_code,
        )
        return False

    # -- payout status poll ------------------------------------------------ #
    async def get_payout_status(self, payout_id: str) -> dict:
        """Read-only payout status poll (PayoutRequest reconciliation)."""
        if not self.api_token:
            raise ProviderConfigError("Payoneer API token is not configured")
        url = f"{self.base_url}{PAYOUT_STATUS_PATH.format(payout_id=payout_id)}"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        try:
            resp = await _get_client().get(url, headers=headers)
        except httpx.HTTPError as e:
            raise ProviderApiError(f"Payoneer payout status error: {e}") from e
        if resp.status_code >= 400:
            raise ProviderApiError(
                f"Payoneer payout status returned {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:2000],
            )
        try:
            return resp.json()
        except ValueError as e:
            raise ProviderApiError("Invalid JSON in Payoneer payout response") from e
