"""Paymob billing adapter — the BACKUP rail (new billing architecture).

Thin adapter over the existing, audit-verified Paymob Intention client
(``app/services/payments/paymob.py``). That module owns the hardened
HMAC-SHA512 webhook verification (exact field orders, fail-closed,
timing-safe) — the billing stack reuses it rather than forking a second
verification path.

Differences from the order-payment flow (``app/api/payments.py``):

* Correlation prefix is ``zbl-`` (Zemest billing) instead of ``zst-`` —
  billing invoices and buyer orders never collide in Paymob's
  ``merchant_order_id`` echo space.
* The webhook/notification URL points at the BILLING webhook route and is
  pinned to ``BILLING_WEBHOOK_PUBLIC_URL`` when configured (kills
  Host-header hijack of notification_url).
* Amounts are converted to piasters exactly once (``to_piasters``).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.config import get_settings
from app.services.payments.paymob import (
    PaymobApiError,
    PaymobClient,
    PaymobConfigError,
    to_piasters,
)
from app.services.billing.providers.base import (
    CheckoutResult,
    PaymentProvider,
    ProviderApiError,
    ProviderConfigError,
)

logger = logging.getLogger(__name__)

# Our billing invoices are linked to Paymob via special_reference =
# "zbl-{billing_transaction_id}" (order payments use "zst-{order_id}").
BILLING_REF_PREFIX = "zbl-"


def billing_reference(transaction_id) -> str:
    return f"{BILLING_REF_PREFIX}{transaction_id}"


def parse_billing_reference(ref: str) -> str | None:
    """Inverse of :func:`billing_reference` — None when not a billing ref."""
    if ref and ref.startswith(BILLING_REF_PREFIX):
        return ref[len(BILLING_REF_PREFIX):]
    return None


class PaymobBillingProvider(PaymentProvider):
    """Backup rail — Paymob Intention (Egypt EGP local payment methods)."""

    name = "paymob"

    def __init__(self, client: PaymobClient | None = None):
        self._client = client or PaymobClient()

    def is_configured(self) -> bool:
        return bool(self._client.api_key and self._client.integration_ids)

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
        if not self._client.api_key:
            raise ProviderConfigError("Paymob API key is not configured (PAYMOB_API_KEY)")
        if not self._client.integration_ids:
            raise ProviderConfigError(
                "No Paymob payment methods configured (PAYMOB_INTEGRATION_IDS)"
            )
        # Pin the notification URL when BILLING_WEBHOOK_PUBLIC_URL is set —
        # the Host-header-derived base is never used for callbacks then.
        notification_url = webhook_url
        pinned = get_settings().BILLING_WEBHOOK_PUBLIC_URL
        if pinned and notification_url:
            # Keep the path from the passed webhook_url, swap the origin.
            path = notification_url.split("/api/", 1)[-1]
            notification_url = f"{pinned.rstrip('/')}/api/{path}"
        elif pinned:
            notification_url = f"{pinned.rstrip('/')}/api/payments/webhook/paymob"

        billing_data = {
            "first_name": "Zemest",
            "last_name": "Merchant",
            "email": customer_email or "",
            "phone_number": "",
            "city": "",
            "state": "",
            "country": "EG",
        }
        # The engine passes OUR transaction id as ``reference``; the
        # zbl- prefix is added HERE so webhooks correlate unambiguously
        # (order payments use zst- and never collide).
        merchant_ref = (
            reference if reference.startswith(BILLING_REF_PREFIX)
            else billing_reference(reference)
        )
        try:
            intention = await self._client.create_intention(
                amount_egp=amount,
                billing_data=billing_data,
                merchant_order_id=merchant_ref,
                payment_methods=None,  # → settings PAYMOB_INTEGRATION_IDS
                items=[
                    {
                        "name": (description or "Zemest subscription")[:100],
                        "amount": to_piasters(amount),
                        "quantity": 1,
                        "description": (description or reference)[:100],
                    }
                ],
                currency=self._client.currency or currency or "EGP",
                notification_url=notification_url,
                redirection_url=success_url or "",
            )
        except PaymobConfigError as e:
            raise ProviderConfigError(str(e)) from e
        except PaymobApiError as e:
            raise ProviderApiError(str(e), e.status_code, e.body) from e

        logger.info("Paymob billing intention created (ref=%s)", reference)
        return CheckoutResult(
            provider=self.name,
            provider_reference=str(intention.get("intention_id") or ""),
            checkout_url=str(intention.get("payment_url") or ""),
            amount=amount,
            currency=self._client.currency or currency or "EGP",
            raw=intention.get("raw") or {},
        )

    async def cancel(self, provider_reference: str) -> bool:
        """Paymob intentions cannot be voided server-side without a
        transaction (they simply expire) — the caller voids the local
        invoice, which is the source of truth for unpaid state."""
        return False
