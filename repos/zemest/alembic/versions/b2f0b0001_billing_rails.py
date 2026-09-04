"""billing rails: payoneer/paymob/usdc_solana (new billing architecture)

Revision ID: b2f0b0001_billing_rails
Revises: b1f0a0001_auth_hardening
Create Date: 2026-09-04 00:00:00

This migration introduces the Zemest billing stack with the three
post-legacy payment rails:

* ``payoneer``    — PRIMARY rail (Payoneer Checkout, USD)
* ``paymob``      — BACKUP rail (Egypt EGP rails — existing client reused)
* ``usdc_solana`` — crypto rail (direct Solana JSON-RPC, no sidecar)

This migration contains only the three active rails; migrating down
cleanly removes the billing stack.

New tables:

1. ``billing_plans`` — seeded subscription plans (starter/growth/pro).
2. ``billing_subscriptions`` — one row per tenant, whole state machine.
3. ``billing_transactions`` — money ledger with deterministic idempotency.
4. ``billing_webhook_events`` — webhook dedup ledger (unique
   provider+event_id).
5. ``payout_requests`` — treasury withdrawal workflow (2-approval).

Altered tables:

* ``tenants.usdc_wallet_address`` — merchant Solana wallet (base58 pubkey)
  for USDC payouts and payment matching.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f0b0001_billing_rails'
down_revision: Union[str, None] = 'b1f0a0001_auth_hardening'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def _uuid_type():
    return sa.Uuid() if hasattr(sa, "Uuid") else sa.String(36)


SEED_PLANS = [
    # code, name, price_egp, price_usdc, trial_days, limits, description
    (
        "starter",
        "Starter",
        "750.00",
        "15.000000",
        14,
        '{"max_tenants": 1, "max_messages_per_month": 3000}',
        "One page, 3,000 AI replies/month, Arabic + English.",
    ),
    (
        "growth",
        "Growth",
        "1850.00",
        "37.000000",
        14,
        '{"max_tenants": 3, "max_messages_per_month": 15000}',
        "Up to 3 pages, 15,000 AI replies/month, priority models.",
    ),
    (
        "pro",
        "Pro",
        "3900.00",
        "78.000000",
        14,
        '{"max_tenants": 10, "max_messages_per_month": 60000}',
        "10 pages, 60,000 AI replies/month, dedicated support.",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    # --- tenants.usdc_wallet_address ------------------------------------
    if not _column_exists(bind, "tenants", "usdc_wallet_address"):
        op.add_column(
            "tenants",
            sa.Column("usdc_wallet_address", sa.String(64), nullable=True),
        )
        op.create_index(
            "ix_tenants_usdc_wallet_address", "tenants", ["usdc_wallet_address"]
        )

    # --- billing_plans ---------------------------------------------------
    op.create_table(
        "billing_plans",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_egp", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_usdc", sa.Numeric(18, 6), nullable=False),
        sa.Column("billing_interval", sa.String(20), nullable=False,
                  server_default="monthly"),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limits", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_billing_plans_code", "billing_plans", ["code"], unique=True)

    # --- billing_subscriptions -------------------------------------------
    op.create_table(
        "billing_subscriptions",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("tenant_id", _uuid_type(),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", _uuid_type(),
                  sa.ForeignKey("billing_plans.id"), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False,
                  server_default="payoneer"),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="trialing"),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("provider_customer_ref", sa.String(100), nullable=True),
        sa.Column("provider_subscription_ref", sa.String(100), nullable=True),
        sa.Column("dunning_attempts", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("dunning_next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("last_payment_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", name="uq_billing_subscription_tenant"),
    )
    op.create_index("ix_billing_subscriptions_tenant_id", "billing_subscriptions", ["tenant_id"])
    op.create_index("ix_billing_subscriptions_plan_id", "billing_subscriptions", ["plan_id"])
    op.create_index(
        "idx_billing_subscription_status", "billing_subscriptions",
        ["status", "current_period_end"],
    )

    # --- billing_transactions --------------------------------------------
    op.create_table(
        "billing_transactions",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("tenant_id", _uuid_type(),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", _uuid_type(),
                  sa.ForeignKey("billing_subscriptions.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("plan_id", _uuid_type(), sa.ForeignKey("billing_plans.id"),
                  nullable=True),
        sa.Column("kind", sa.String(30), nullable=False,
                  server_default="subscription_payment"),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False,
                  server_default="pending"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_usdc", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="EGP"),
        sa.Column("idempotency_key", sa.String(120), nullable=False, unique=True),
        sa.Column("provider_reference", sa.String(120), nullable=True),
        sa.Column("checkout_url", sa.String(500), nullable=True),
        sa.Column("solana_reference", sa.String(200), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("failed_reason", sa.String(255), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_billing_transactions_tenant_id", "billing_transactions", ["tenant_id"])
    op.create_index("ix_billing_transactions_subscription_id", "billing_transactions", ["subscription_id"])
    op.create_index("ix_billing_transactions_plan_id", "billing_transactions", ["plan_id"])
    op.create_index("ix_billing_transactions_provider_reference", "billing_transactions", ["provider_reference"])
    op.create_index(
        "idx_billing_txn_tenant_status", "billing_transactions", ["tenant_id", "status"])
    op.create_index(
        "idx_billing_txn_pending_usdc", "billing_transactions",
        ["payment_method", "status"])

    # --- billing_webhook_events ------------------------------------------
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("provider", "event_id", name="uq_billing_webhook_event"),
    )

    # --- payout_requests --------------------------------------------------
    op.create_table(
        "payout_requests",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("tenant_id", _uuid_type(),
                  sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_by", _uuid_type(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="usdc"),
        sa.Column("amount_usdc", sa.Numeric(18, 6), nullable=True),
        sa.Column("amount_egp", sa.Numeric(12, 2), nullable=True),
        sa.Column("destination", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="request"),
        sa.Column("approvers", sa.JSON(), nullable=True),
        sa.Column("execution_reference", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payout_requests_tenant_id", "payout_requests", ["tenant_id"])
    op.create_index("ix_payout_requests_requested_by", "payout_requests", ["requested_by"])
    op.create_index(
        "idx_payout_requests_status", "payout_requests", ["status", "created_at"])

    # --- seed plans (idempotent) ------------------------------------------
    plan_table = sa.table(
        "billing_plans",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("price_egp", sa.Numeric),
        sa.column("price_usdc", sa.Numeric),
        sa.column("billing_interval", sa.String),
        sa.column("trial_days", sa.Integer),
        sa.column("limits", sa.JSON),
        sa.column("is_active", sa.Boolean),
    )
    existing = {row[0] for row in bind.execute(sa.select(plan_table.c.code))}
    for code, name, price_egp, price_usdc, trial, limits, desc in SEED_PLANS:
        if code not in existing:
            bind.execute(
                plan_table.insert().values(
                    code=code,
                    name=name,
                    description=desc,
                    price_egp=price_egp,
                    price_usdc=price_usdc,
                    billing_interval="monthly",
                    trial_days=trial,
                    limits=limits,
                    is_active=True,
                )
            )


def downgrade() -> None:
    op.drop_table("payout_requests")
    op.drop_table("billing_webhook_events")
    op.drop_index("idx_billing_txn_pending_usdc", table_name="billing_transactions")
    op.drop_index("idx_billing_txn_tenant_status", table_name="billing_transactions")
    op.drop_index("ix_billing_transactions_provider_reference", table_name="billing_transactions")
    op.drop_index("ix_billing_transactions_plan_id", table_name="billing_transactions")
    op.drop_index("ix_billing_transactions_subscription_id", table_name="billing_transactions")
    op.drop_index("ix_billing_transactions_tenant_id", table_name="billing_transactions")
    op.drop_table("billing_transactions")
    op.drop_index("idx_billing_subscription_status", table_name="billing_subscriptions")
    op.drop_index("ix_billing_subscriptions_plan_id", table_name="billing_subscriptions")
    op.drop_index("ix_billing_subscriptions_tenant_id", table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")
    op.drop_index("ix_billing_plans_code", table_name="billing_plans")
    op.drop_table("billing_plans")
    op.drop_index("ix_tenants_usdc_wallet_address", table_name="tenants")
    op.drop_column("tenants", "usdc_wallet_address")
