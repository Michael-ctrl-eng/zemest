"""Provider contracts for the post-legacy billing rails.

Every payment rail (payoneer / paymob / usdc_solana) implements the same
small surface so the subscription engine and webhook processor stay
rail-agnostic:

* ``is_configured()``  — credentials present (rail advertised or not).
* ``create_checkout()`` — start a payment for a known amount + our
  reference; returns a browser-facing URL (fiat rails) or on-chain
  instructions (USDC).
* ``cancel()``          — void an unpaid provider object (best effort).

Webhook verification is intentionally NOT on this interface: each provider
delivers signatures differently (Payoneer HMAC header over raw bytes,
Paymob HMAC query param over a field concatenation, USDC has no webhooks
at all — it is polled on-chain). The webhook processor owns those paths
and lives in ``app/services/billing/webhook_processor.py``.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Errors — shared across providers
# --------------------------------------------------------------------------- #
class ProviderError(Exception):
    """Base class for billing provider errors."""


class ProviderConfigError(ProviderError):
    """Missing configuration (token / secret / wallet)."""


class ProviderApiError(ProviderError):
    """Provider API returned an error / transport failure."""

    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


# --------------------------------------------------------------------------- #
# Checkout result
# --------------------------------------------------------------------------- #
@dataclass
class CheckoutResult:
    """Normalized outcome of starting a payment on a rail.

    ``checkout_url`` is the browser-facing page for the fiat rails; for
    usdc_solana it is empty and the caller renders the on-chain
    instructions (treasury address, exact amount, reference memo).
    """

    provider: str
    provider_reference: str          # checkout session / intention id
    checkout_url: str = ""           # empty for usdc_solana
    amount: Decimal = Decimal("0")   # charged amount, major units
    currency: str = ""               # USD / EGP / USDC
    # usdc_solana only:
    deposit_address: str = ""        # treasury wallet (base58)
    reference_memo: str = ""         # payer MUST attach to the transfer
    expires_at: Optional[datetime] = None
    raw: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Provider interface
# --------------------------------------------------------------------------- #
class PaymentProvider(abc.ABC):
    """Interface implemented by every billing rail."""

    #: rail name — one of app.models.billing.PaymentMethod values
    name: str = ""

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True when the rail has the credentials it needs to operate."""

    @abc.abstractmethod
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
        """Start a payment. ``reference`` is OUR id echoed back by the
        provider on every callback (correlation key — never trust it for
        auth, only for lookup)."""

    async def cancel(self, provider_reference: str) -> bool:
        """Void an unpaid provider object. Returns True when the provider
        confirmed the void. Best-effort: rails without a void API return
        False and the caller voids the local invoice instead."""
        return False
