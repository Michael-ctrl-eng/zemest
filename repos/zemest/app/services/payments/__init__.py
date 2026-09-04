"""Payments gateway integrations (Paymob first — see docs/PAYMENTS.md (content folded into the module docstrings)).

Architecture rules shared by every gateway added under this package:

* COD stays the default payment rail; gateways power the deposit-to-confirm
  (عربون) flow and full online payments.
* Server webhooks are the ONLY source of payment state changes — browser
  redirects are UX-only and never trusted.
* Dedup on the gateway event/transaction id + one-transaction compare-and-set
  on the order row (no regressions, no double transitions).
"""
from app.services.payments.paymob import (
    PaymobApiError,
    PaymobClient,
    PaymobConfigError,
    PaymobError,
    TOKEN_HMAC_FIELDS,
    TRANSACTION_HMAC_FIELDS,
    build_hmac_message,
    build_intention_payload,
    close_client,
    to_piasters,
    verify_subscription_hmac,
    verify_token_hmac,
    verify_transaction_hmac,
)

__all__ = [
    "PaymobApiError",
    "PaymobClient",
    "PaymobConfigError",
    "PaymobError",
    "TOKEN_HMAC_FIELDS",
    "TRANSACTION_HMAC_FIELDS",
    "build_hmac_message",
    "build_intention_payload",
    "close_client",
    "to_piasters",
    "verify_subscription_hmac",
    "verify_token_hmac",
    "verify_transaction_hmac",
]
