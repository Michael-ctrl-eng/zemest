"""Billing models — new billing architecture.

Payment rails (``PaymentMethod``):

* ``payoneer``    — PRIMARY rail (card / wallet via Payoneer Checkout, USD).
* ``paymob``      — BACKUP rail (Egypt local rails via the existing Paymob
  Intention client, EGP).
* ``usdc_solana`` — crypto rail for wallet users (USDC over Solana; the
  backend talks DIRECTLY to a Solana JSON-RPC endpoint — no sidecar, no third-party custodian).

There is intentionally no legacy card-rail model, column, or default
value anywhere in this module (or the rest of the billing stack).

Design notes (matching repo conventions):

* Status/method columns are plain ``String`` (not SA ``Enum``) — keeps
  SQLite tests and alembic migrations simple; valid values are documented
  on each column and enforced at the service layer.
* Money: ``amount`` (EGP, Numeric(12,2)) for the fiat rails,
  ``amount_usdc`` (USDC, Numeric(18,6)) for the crypto rail. USDC has 6
  decimals on Solana; we quantize to whole micro-USDC (1e-6).
* One ``BillingSubscription`` row per tenant (unique constraint) — its
  ``status`` field is the whole state machine; history lives in
  ``BillingTransaction``.
* ``BillingWebhookEvent`` gives provider webhooks an idempotency ledger
  (unique ``(provider, event_id)``) so a redelivered Payoneer/Paymob event
  can never double-apply.
* ``PayoutRequest`` is the treasury withdrawal workflow (USDC on-chain or
  bank transfer): request → 2 admin approvals → operator executes →
  reconciliation. Private keys NEVER live in this app.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# --------------------------------------------------------------------------- #
# Payment rails — the ONLY accepted payment methods (only the three active rails)
# --------------------------------------------------------------------------- #
class PaymentMethod:
    """Valid ``payment_method`` values (stored as String(30))."""

    PAYONEER = "payoneer"
    PAYMOB = "paymob"
    USDC_SOLANA = "usdc_solana"

    ALL = (PAYONEER, PAYMOB, USDC_SOLANA)

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.ALL


# Subscription status machine:
#   trialing → active | canceled
#   active   → past_due | canceled | expired
#   past_due → active (payment recovered) | canceled (dunning exhausted) | expired
#   canceled → active (re-subscribe)
#   expired  → terminal (payment failed / canceled and grace elapsed)
SUBSCRIPTION_STATUSES = (
    "trialing",
    "active",
    "past_due",
    "canceled",
    "expired",
)

# BillingTransaction.status machine:
#   pending → awaiting_confirmation (usdc) → succeeded | failed
#   pending → voided            (invoice canceled before payment landed)
#   succeeded → refunded | disputed
TRANSACTION_STATUSES = (
    "pending",
    "awaiting_confirmation",
    "succeeded",
    "failed",
    "voided",
    "refunded",
    "disputed",
)

# BillingTransaction.kind
TRANSACTION_KINDS = (
    "subscription_payment",
    "adjustment",
    "refund",
    "payout",
)

# PayoutRequest.status: request → pending (2nd approval) → approved
#   → executed (operator records the on-chain signature / bank receipt)
#   any pre-execution step may reject / cancel.
PAYOUT_STATUSES = (
    "request",
    "pending",
    "approved",
    "rejected",
    "executed",
    "canceled",
)


class BillingPlan(Base):
    """A subscription plan (seeded rows — starter / growth / pro)."""

    __tablename__ = "billing_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Price in the two billing currencies. EGP is authoritative for the fiat
    # rails (Paymob); USDC is authoritative for the crypto rail (Payoneer
    # bills USD — converted to EGP at subscribe time by the engine, which is
    # also the single place where the EGP/USD rate is applied).
    price_egp: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_usdc: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    billing_interval: Mapped[str] = mapped_column(String(20), default="monthly")
    trial_days: Mapped[int] = mapped_column(Integer, default=0)

    # Feature limits consumed by the platform gate, e.g.
    # {"max_tenants": 1, "max_messages_per_month": 5000}
    limits: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    subscriptions = relationship("BillingSubscription", back_populates="plan")


class BillingSubscription(Base):
    """One subscription per tenant — the platform-access state machine."""

    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        # A tenant has exactly one subscription row (resubscribing reuses it).
        UniqueConstraint("tenant_id", name="uq_billing_subscription_tenant"),
        Index("idx_billing_subscription_status", "status", "current_period_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billing_plans.id"), index=True)

    # payoneer | paymob | usdc_solana (PaymentMethod) — no removed rail.
    payment_method: Mapped[str] = mapped_column(String(30), default=PaymentMethod.PAYONEER)

    # trialing | active | past_due | canceled | expired (SUBSCRIPTION_STATUSES)
    status: Mapped[str] = mapped_column(String(20), default="trialing")

    current_period_start: Mapped[Optional[datetime]] = mapped_column(default=None)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(default=None)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    # Provider-side references (Payoneer customer/subscription ids, Paymob
    # subscription id). USDC-Solana keeps these NULL (chain is the ledger).
    provider_customer_ref: Mapped[Optional[str]] = mapped_column(String(100))
    provider_subscription_ref: Mapped[Optional[str]] = mapped_column(String(100))

    # Dunning state (subscription engine): consecutive failed charge
    # attempts + next retry time. Reset to 0 on a successful payment.
    dunning_attempts: Mapped[int] = mapped_column(Integer, default=0)
    dunning_next_retry_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    last_payment_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    tenant = relationship("Tenant", back_populates="billing_subscription")
    plan = relationship("BillingPlan", back_populates="subscriptions")
    transactions = relationship(
        "BillingTransaction",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class BillingTransaction(Base):
    """Money ledger row — one per invoice / charge / payout attempt.

    Idempotency: ``idempotency_key`` is unique. The subscription engine
    generates deterministic keys (``sub-{subscription_id}-{period_start}``)
    so a retried billing cycle can never double-bill a period.
    """

    __tablename__ = "billing_transactions"
    __table_args__ = (
        Index("idx_billing_txn_tenant_status", "tenant_id", "status"),
        Index("idx_billing_txn_pending_usdc", "payment_method", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("billing_subscriptions.id", ondelete="SET NULL"), index=True
    )
    plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("billing_plans.id"))

    # subscription_payment | adjustment | refund | payout (TRANSACTION_KINDS)
    kind: Mapped[str] = mapped_column(String(30), default="subscription_payment")
    # payoneer | paymob | usdc_solana — no removed rail.
    payment_method: Mapped[str] = mapped_column(String(30))
    # pending | awaiting_confirmation | succeeded | failed | voided |
    # refunded | disputed (TRANSACTION_STATUSES)
    status: Mapped[str] = mapped_column(String(30), default="pending")

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # EGP (fiat rails)
    amount_usdc: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))  # crypto rail
    currency: Mapped[str] = mapped_column(String(8), default="EGP")

    # Deterministic dedup key (engine-owned; unique).
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)

    # Provider-side correlation: Payoneer checkout session id / payment id,
    # Paymob intention id / transaction id, Solana tx signature (USDC).
    provider_reference: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    # Browser-facing checkout URL (Payoneer hosted page / Paymob unified
    # checkout). Empty for USDC (payment instructions instead).
    checkout_url: Mapped[Optional[str]] = mapped_column(String(500))
    # USDC-Solana: the memo/reference the payer must attach so the engine can
    # match the on-chain transfer to THIS invoice.
    solana_reference: Mapped[Optional[str]] = mapped_column(String(200))

    paid_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    voided_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    failed_reason: Mapped[Optional[str]] = mapped_column(String(255))

    # Redacted provider payload snapshot (never card data / keys).
    raw: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    tenant = relationship("Tenant", back_populates="billing_transactions")
    subscription = relationship("BillingSubscription", back_populates="transactions")


class BillingWebhookEvent(Base):
    """Webhook idempotency ledger (Payoneer / Paymob server callbacks).

    Unique ``(provider, event_id)``: a redelivered webhook is recorded ONCE
    and its processing is skipped on the second delivery. This is the
    pattern recommended by every payment provider's retry semantics.
    """

    __tablename__ = "billing_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_billing_webhook_event"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # payoneer | paymob (USDC-Solana is polled, not webhook-driven).
    provider: Mapped[str] = mapped_column(String(30))
    event_id: Mapped[str] = mapped_column(String(120))
    event_type: Mapped[Optional[str]] = mapped_column(String(60))
    payload: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text)

    received_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    processed_at: Mapped[Optional[datetime]] = mapped_column(default=None)


class PayoutRequest(Base):
    """Treasury withdrawal workflow (USDC on-chain rail or bank transfer).

    Flow: a request is created (by a merchant for their payout, or by an
    admin for the platform treasury), needs TWO distinct superadmin
    approvals, then the operator executes it out-of-band (bank portal or
    wallet signer) and records the receipt / Solana signature. The backend
    verifies the signature on-chain when present. No private keys ever
    touch this app.
    """

    __tablename__ = "payout_requests"
    __table_args__ = (
        Index("idx_payout_requests_status", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # NULL = platform treasury withdrawal; set = merchant payout.
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)

    # usdc (Solana rail) | bank (treasury bank transfer)
    kind: Mapped[str] = mapped_column(String(20), default="usdc")
    amount_usdc: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    amount_egp: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))

    # Destination summary — a wallet address (usdc) or masked bank info
    # (bank). NEVER full account numbers/secrets: store the operator-facing
    # description only, e.g. "CIB ****1234 — Zemest ops".
    destination: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

    # request | pending | approved | rejected | executed | canceled
    status: Mapped[str] = mapped_column(String(20), default="request")

    # Distinct superadmin ids that approved (request needs 2).
    approvers: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    # On-chain signature / bank receipt reference once executed.
    execution_reference: Mapped[Optional[str]] = mapped_column(String(120))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
