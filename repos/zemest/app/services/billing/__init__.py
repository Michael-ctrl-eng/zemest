"""Zemest billing stack — new billing architecture.

Rails: payoneer (PRIMARY) / paymob (BACKUP) / usdc_solana (crypto, direct
Solana JSON-RPC — no sidecar sidecar). The removed rails stay removed.

Submodules:

* ``providers/``      — rail adapters behind one interface.
* ``subscription_engine`` — activation gate, monthly cycle, dunning,
  USDC settlement + void.
* ``webhook_processor``  — verify → dedupe → dispatch → compare-and-set.
"""
from app.services.billing.providers import (
    CheckoutResult,
    PayoneerProvider,
    PaymobBillingProvider,
    UsdcSolanaProvider,
    available_rails,
    get_provider,
)
from app.services.billing.providers.base import (
    ProviderApiError,
    ProviderConfigError,
    ProviderError,
)

__all__ = [
    "CheckoutResult",
    "PayoneerProvider",
    "PaymobBillingProvider",
    "UsdcSolanaProvider",
    "available_rails",
    "get_provider",
    "ProviderApiError",
    "ProviderConfigError",
    "ProviderError",
]
