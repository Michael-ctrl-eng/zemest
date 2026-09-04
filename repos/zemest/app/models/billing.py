"""Billing & subscription platform (Stripe-grade + Payoneer + SKALE payouts).

One schema drives the whole money flow:

```
 Subscription (user, plan, provider, period)          <- the contract
    └── Invoice (monthly, numbered, dunning)          <- the charge attempts
          └── PaymentEvent (webhook log, idempotent)  <- the truth from rails
 PayoutAccount (payoneer | skale | bank_egypt)        <- where money goes OUT
    └── PayoutRequest (rail: payoneer | skale)        <- the payout job
 FraudFlag (velocity / disputes / anomalies)          <- the safety net
```

Design rules (mirrors the Paymob module's posture):
* **Webhooks are the only state-change source** for money. The browser is
  never trusted; every callback is signature-verified against the RAW body
  before any DB write, and deduplicated via ``payment_events`` (idempotent).
* **Activation is idempotent** — the same paid invoice can be re-delivered
  (webhook retries) and the user's plan flips exactly once.
* Providers: ``stripe`` (international cards + Apple Pay + Google Pay,
  provider-managed recurrence), ``paymob`` (Egypt EGP rails, platform-managed
  recurrence over saved tokens), ``payoneer`` (checkout + payout rail).
* Payout rails: ``payoneer`` (to Egypt bank / Payoneer account) and
  ``skale`` (USDC or native token on SKALE Network, gas-free Europa chain,
  sent through the ``mini-services/skale-payout`` ethers.js sidecar).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.db_types import EncryptedText


# --------------------------------------------------------------------------- #
# Subscription — the recurring contract
# --------------------------------------------------------------------------- #
class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("idx_subscriptions_user_status", "user_id", "status"),
        Index("idx_subscriptions_period_end", "current_period_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    # free | growth | pro (app/services/plan_service.py PLANS)
    plan: Mapped[str] = mapped_column(String(20), default="growth")
    # trialing | active | past_due | canceled | incomplete | unpaid
    status: Mapped[str] = mapped_column(String(20), default="incomplete", index=True)
    # stripe | paymob | payoneer | manual (admin grants)
    provider: Mapped[str] = mapped_column(String(20), default="stripe")

    # Provider-side ids (never secrets; safe to store plain)
    provider_customer_id: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(String(120), default=None, index=True)

    # Period bookkeeping (platform-managed providers; Stripe syncs via webhook)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    # Charge the default payment method at period end (False after cancel())
    charge_at_period_end: Mapped[bool] = mapped_column(Boolean, default=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    canceled_by: Mapped[Optional[str]] = mapped_column(String(20), default=None)  # user | admin | system

    # Dunning (platform-managed providers): retry schedule for failed charges
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, index=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    def active_or_trialing(self) -> bool:
        return self.status in ("active", "trialing")


# --------------------------------------------------------------------------- #
# Invoice — one per billing period, the single charge unit
# --------------------------------------------------------------------------- #
class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        # One live invoice per subscription+period — the compare-and-set anchor
        UniqueConstraint("subscription_id", "period_start", name="uq_invoice_sub_period"),
        Index("idx_invoices_user_status", "user_id", "status"),
        Index("idx_invoices_number", "number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(24), unique=True)  # INV-202609-0001
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    plan: Mapped[str] = mapped_column(String(20))

    # Money in the SMALLEST unit of `currency` (piasters for EGP, cents USD)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="EGP")
    # draft | open | paid | void | uncollectible | refunded
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)

    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)

    provider: Mapped[str] = mapped_column(String(20), default="stripe")
    provider_invoice_id: Mapped[Optional[str]] = mapped_column(String(120), default=None, index=True)
    provider_charge_id: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    # Hosted checkout URL (Payoneer/Paymob) or client_secret (Stripe) when open
    payment_url: Mapped[Optional[str]] = mapped_column(String(600), default=None)
    client_secret: Mapped[Optional[str]] = mapped_column(String(200), default=None)

    # Dunning state for this invoice (platform-managed providers)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(300), default=None)

    # Human-readable line items for receipts:
    # [{"description": "Zemest Growth — monthly", "amount": 29900, "quantity": 1}]
    line_items: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())

    def is_open_for_payment(self) -> bool:
        return self.status in ("draft", "open")


# --------------------------------------------------------------------------- #
# PaymentMethod — saved rails for recurring charges (user-scoped)
# --------------------------------------------------------------------------- #
class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "provider_pm_id", name="uq_pm_user_provider_id"),
        Index("idx_payment_methods_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    # stripe | paymob | payoneer
    provider: Mapped[str] = mapped_column(String(20))
    # Provider token (stripe pm_..., paymob token) — NEVER the PAN/CVV
    provider_pm_id: Mapped[str] = mapped_column(String(140))
    # card | apple_pay | google_pay | payoneer | wallet
    kind: Mapped[str] = mapped_column(String(20), default="card")
    # Display-only safe fields: brand, last4, expiry — no secrets, no PAN
    brand: Mapped[Optional[str]] = mapped_column(String(30), default=None)
    last4: Mapped[Optional[str]] = mapped_column(String(8), default=None)
    exp_month: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    exp_year: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    billing_country: Mapped[Optional[str]] = mapped_column(String(4), default=None)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # Fraud gate: a detached card (failed verification/dispute) stops being
    # chargeable so recurring attempts can never hammer a dead rail.
    is_attached: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())


# --------------------------------------------------------------------------- #
# PaymentEvent — webhook ledger: verification + idempotency + audit
# --------------------------------------------------------------------------- #
class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        # The idempotency key: one provider event id processed exactly once
        UniqueConstraint("provider", "provider_event_id", name="uq_payment_event_provider_id"),
        Index("idx_payment_events_received", "received_at"),
        Index("idx_payment_events_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    provider_event_id: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(80))
    # What the event did (matched subscription/invoice ids, action taken)
    outcome: Mapped[Optional[str]] = mapped_column(String(40), default=None)
    detail: Mapped[Optional[str]] = mapped_column(String(400), default=None)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="received")  # received | processed | duplicate | rejected | error
    received_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)


# --------------------------------------------------------------------------- #
# Payouts — money OUT to the merchant
# --------------------------------------------------------------------------- #
class PayoutAccount(Base):
    __tablename__ = "payout_accounts"
    __table_args__ = (
        Index("idx_payout_accounts_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    # payoneer | skale | bank_egypt
    method: Mapped[str] = mapped_column(String(20))
    # Method details (payee id / wallet address / bank fields). Encrypted at
    # rest with the platform Fernet key (Transparently-encrypted column):
    # reads decrypt transparently, writes encrypt — wallet addresses and
    # bank PII both land as ciphertext in the DB.
    details: Mapped[Optional[str]] = mapped_column(EncryptedText(), default=None)
    # Display label (e.g. "USDC wallet 0x1a…9f" / "Payoneer acc **43")
    label: Mapped[Optional[str]] = mapped_column(String(80), default=None)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    # pending | verified | rejected
    status: Mapped[str] = mapped_column(String(20), default="pending")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())


class PayoutRequest(Base):
    __tablename__ = "payout_requests"
    __table_args__ = (
        Index("idx_payout_requests_user_status", "user_id", "status"),
        Index("idx_payout_requests_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    payout_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payout_accounts.id"))
    # payoneer | skale
    rail: Mapped[str] = mapped_column(String(20))
    amount: Mapped[int] = mapped_column(Integer)        # smallest unit
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    fee_amount: Mapped[int] = mapped_column(Integer, default=0)   # platform fee kept
    net_amount: Mapped[int] = mapped_column(Integer, default=0)   # what lands

    # pending -> (auto|admin) approved -> processing -> paid | failed | canceled
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    provider_ref: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(100), default=None)  # SKALE
    failure_reason: Mapped[Optional[str]] = mapped_column(String(300), default=None)
    approved_by: Mapped[Optional[str]] = mapped_column(String(20), default=None)  # auto | admin:<id>
    requested_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)


# --------------------------------------------------------------------------- #
# FraudFlag — velocity rules, disputes, payout anomalies
# --------------------------------------------------------------------------- #
class FraudFlag(Base):
    __tablename__ = "fraud_flags"
    __table_args__ = (
        Index("idx_fraud_flags_user", "user_id", "severity"),
        Index("idx_fraud_flags_open", "resolved_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    # failed_charges_velocity | dispute | payout_velocity | payout_anomaly |
    # card_testing | ip_shared_trial_farm | chargeback_risk
    kind: Mapped[str] = mapped_column(String(40))
    # low | medium | high
    severity: Mapped[str] = mapped_column(String(10), default="low")
    detail: Mapped[Optional[str]] = mapped_column(String(400), default=None)
    # Automatic guard rails taken (subscription_canceled | payouts_held | ...)
    action_taken: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(40), default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
