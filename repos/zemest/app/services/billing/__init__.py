"""Billing & subscription platform (Stripe-grade + Payoneer + SKALE payouts).

Public surface (used by app/api/billing.py):

* subscription_engine — lifecycle: subscribe, invoices, activation,
  dunning, cancel/reactivate, balance
* payouts             — payout orchestration on the Payoneer/SKALE rails
* fraud               — velocity/dispute rules gating payments and payouts
* webhook_processor   — verified-event pipeline (the only state changer)
* providers           — stripe_provider / payoneer / skale adapters
"""
from app.services.billing.subscription_engine import (
    billing_tick,
    cancel_subscription,
    create_subscription_and_invoice,
    get_active_subscription,
    mark_invoice_paid,
    reactivate_subscription,
    available_balance,
)
from app.services.billing.payouts import (
    PayoutError,
    approve as approve_payout,
    create_payout_request,
    execute as execute_payout,
    mark_paid_by_webhook,
)
from app.services.billing import fraud
from app.services.billing.webhook_processor import (
    WebhookRejected,
    process_payoneer_event,
    process_stripe_event,
)

__all__ = [
    "billing_tick",
    "cancel_subscription",
    "create_subscription_and_invoice",
    "get_active_subscription",
    "mark_invoice_paid",
    "reactivate_subscription",
    "available_balance",
    "PayoutError",
    "approve_payout",
    "create_payout_request",
    "execute_payout",
    "mark_paid_by_webhook",
    "fraud",
    "WebhookRejected",
    "process_payoneer_event",
    "process_stripe_event",
]
