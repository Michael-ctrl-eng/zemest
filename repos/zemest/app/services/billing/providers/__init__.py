"""Billing provider registry — post-legacy rails.

Rails (``app.models.billing.PaymentMethod``):

* ``payoneer``    — PRIMARY (Payoneer Checkout, USD)
* ``paymob``      — BACKUP (Egypt EGP rails)
* ``usdc_solana`` — crypto rail (direct Solana JSON-RPC, no sidecar)

No removed rail is registered anywhere in this map (adversarial regression test:
``tests/billing/test_no_stripe_skale.py``).
"""
from __future__ import annotations

from app.models.billing import PaymentMethod
from app.services.billing.providers.base import (
    CheckoutResult,
    PaymentProvider,
    ProviderApiError,
    ProviderConfigError,
    ProviderError,
)
from app.services.billing.providers.payoneer import PayoneerProvider
from app.services.billing.providers.paymob import PaymobBillingProvider
from app.services.billing.providers.usdc_solana import UsdcSolanaProvider

# name → class (the ONLY place rails are registered)
_PROVIDER_CLASSES: dict[str, type[PaymentProvider]] = {
    PaymentMethod.PAYONEER: PayoneerProvider,
    PaymentMethod.PAYMOB: PaymobBillingProvider,
    PaymentMethod.USDC_SOLANA: UsdcSolanaProvider,
}


def get_provider(name: str, **kwargs) -> PaymentProvider:
    """Instantiate a provider by rail name. Unknown names raise (there is
    no fallback to any removed rail)."""
    try:
        cls = _PROVIDER_CLASSES[name]
    except KeyError:
        raise ProviderConfigError(
            f"Unknown payment rail {name!r} (valid: {sorted(_PROVIDER_CLASSES)})"
        ) from None
    return cls(**kwargs)


def available_rails() -> list[dict]:
    """Which rails are configured right now (drives /api/billing/rails).

    Order matters: payoneer (primary) first, paymob (backup) second,
    usdc_solana (wallet users) third — the frontend renders buttons in
    this order.
    """
    rails: list[dict] = []
    for name in (
        PaymentMethod.PAYONEER,
        PaymentMethod.PAYMOB,
        PaymentMethod.USDC_SOLANA,
    ):
        try:
            provider = get_provider(name)
            configured = provider.is_configured()
        except ProviderError:
            configured = False
        rails.append(
            {
                "method": name,
                "configured": configured,
                # Primary/backup/crypto role is fixed by architecture.
                "role": {
                    PaymentMethod.PAYONEER: "primary",
                    PaymentMethod.PAYMOB: "backup",
                    PaymentMethod.USDC_SOLANA: "crypto",
                }[name],
            }
        )
    return rails


__all__ = [
    "CheckoutResult",
    "PaymentProvider",
    "ProviderApiError",
    "ProviderConfigError",
    "ProviderError",
    "PayoneerProvider",
    "PaymobBillingProvider",
    "UsdcSolanaProvider",
    "get_provider",
    "available_rails",
]
