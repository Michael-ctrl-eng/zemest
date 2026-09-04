"""billing platform: subscriptions, invoices, payment methods, events,
payouts, fraud flags

Revision ID: k2e9f0008
Revises: j1c8d0007
Create Date: 2026-09-04

The full money stack (app/models/billing.py):
- subscriptions — the recurring contract (provider, period, dunning)
- invoices — monthly numbered charge units (INV-YYYYMM-NNNN)
- payment_methods — saved rails (display fields only, never PAN)
- payment_events — webhook ledger: (provider, event_id) unique = idempotency
- payout_accounts / payout_requests — money OUT via Payoneer / SKALE
- fraud_flags — velocity/dispute rules with automatic guard rails

The same tables are created idempotently at boot via create_all in
app/main.py for deployments that don't run alembic.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "k2e9f0008"
down_revision = "j1c8d0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="growth"),
        sa.Column("status", sa.String(20), nullable=False, server_default="incomplete"),
        sa.Column("provider", sa.String(20), nullable=False, server_default="stripe"),
        sa.Column("provider_customer_id", sa.String(120)),
        sa.Column("provider_subscription_id", sa.String(120)),
        sa.Column("current_period_start", sa.DateTime()),
        sa.Column("current_period_end", sa.DateTime()),
        sa.Column("charge_at_period_end", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("canceled_at", sa.DateTime()),
        sa.Column("cancel_reason", sa.String(200)),
        sa.Column("canceled_by", sa.String(20)),
        sa.Column("failed_attempts", sa.Integer(), server_default="0"),
        sa.Column("next_retry_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("idx_subscriptions_user_status", "subscriptions", ["user_id", "status"])
    op.create_index("idx_subscriptions_period_end", "subscriptions", ["current_period_end"])
    op.create_index("subscriptions_user_id_idx", "subscriptions", ["user_id"])
    op.create_index("subscriptions_provider_subscription_id_idx", "subscriptions", ["provider_subscription_id"])
    op.create_index("subscriptions_status_idx", "subscriptions", ["status"])
    op.create_index("subscriptions_next_retry_at_idx", "subscriptions", ["next_retry_at"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("number", sa.String(24), nullable=False, unique=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subscription_id", sa.UUID(), sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), server_default="0"),
        sa.Column("currency", sa.String(8), server_default="EGP"),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("period_start", sa.DateTime()),
        sa.Column("period_end", sa.DateTime()),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("paid_at", sa.DateTime()),
        sa.Column("provider", sa.String(20), server_default="stripe"),
        sa.Column("provider_invoice_id", sa.String(120)),
        sa.Column("provider_charge_id", sa.String(120)),
        sa.Column("payment_url", sa.String(600)),
        sa.Column("client_secret", sa.String(200)),
        sa.Column("attempt_count", sa.Integer(), server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime()),
        sa.Column("last_error", sa.String(300)),
        sa.Column("line_items", sa.JSON()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("subscription_id", "period_start", name="uq_invoice_sub_period"),
    )
    op.create_index("idx_invoices_user_status", "invoices", ["user_id", "status"])
    op.create_index("idx_invoices_number", "invoices", ["number"])
    op.create_index("invoices_subscription_id_idx", "invoices", ["subscription_id"])
    op.create_index("invoices_status_idx", "invoices", ["status"])
    op.create_index("invoices_provider_invoice_id_idx", "invoices", ["provider_invoice_id"])
    op.create_index("invoices_next_attempt_at_idx", "invoices", ["next_attempt_at"])

    op.create_table(
        "payment_methods",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_pm_id", sa.String(140), nullable=False),
        sa.Column("kind", sa.String(20), server_default="card"),
        sa.Column("brand", sa.String(30)),
        sa.Column("last4", sa.String(8)),
        sa.Column("exp_month", sa.Integer()),
        sa.Column("exp_year", sa.Integer()),
        sa.Column("billing_country", sa.String(4)),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("is_attached", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("user_id", "provider", "provider_pm_id", name="uq_pm_user_provider_id"),
    )
    op.create_index("idx_payment_methods_user", "payment_methods", ["user_id"])

    op.create_table(
        "payment_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_event_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(40)),
        sa.Column("detail", sa.String(400)),
        sa.Column("signature_valid", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("status", sa.String(20), server_default="received"),
        sa.Column("received_at", sa.DateTime()),
        sa.Column("processed_at", sa.DateTime()),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_payment_event_provider_id"),
    )
    op.create_index("idx_payment_events_received", "payment_events", ["received_at"])
    op.create_index("idx_payment_events_type", "payment_events", ["event_type"])

    op.create_table(
        "payout_accounts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("label", sa.String(80)),
        sa.Column("currency", sa.String(8), server_default="USD"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("idx_payout_accounts_user", "payout_accounts", ["user_id"])

    op.create_table(
        "payout_requests",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payout_account_id", sa.UUID(), sa.ForeignKey("payout_accounts.id"), nullable=False),
        sa.Column("rail", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(8), server_default="USD"),
        sa.Column("fee_amount", sa.Integer(), server_default="0"),
        sa.Column("net_amount", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("provider_ref", sa.String(120)),
        sa.Column("tx_hash", sa.String(100)),
        sa.Column("failure_reason", sa.String(300)),
        sa.Column("approved_by", sa.String(20)),
        sa.Column("requested_at", sa.DateTime()),
        sa.Column("processed_at", sa.DateTime()),
    )
    op.create_index("idx_payout_requests_user_status", "payout_requests", ["user_id", "status"])
    op.create_index("idx_payout_requests_status", "payout_requests", ["status"])

    op.create_table(
        "fraud_flags",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(10), server_default="low"),
        sa.Column("detail", sa.String(400)),
        sa.Column("action_taken", sa.String(200)),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("resolved_by", sa.String(40)),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("idx_fraud_flags_user", "fraud_flags", ["user_id", "severity"])
    op.create_index("idx_fraud_flags_open", "fraud_flags", ["resolved_at"])


def downgrade() -> None:
    op.drop_table("fraud_flags")
    op.drop_table("payout_requests")
    op.drop_table("payout_accounts")
    op.drop_table("payment_events")
    op.drop_table("payment_methods")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
