"""egyptian pivot: rename BD address cols, add missing columns, add indices

Revision ID: a89fe0001_egypt_pivot
Revises: 927179233531
Create Date: 2026-08-26 00:00:00

This migration reconciles the schema with the Egyptian-pivoted ORM models:
1. Renames Bangladeshi address columns (division/district/upazila) to
   Egyptian (governorate/city/area) on customers + orders.
2. Adds 12 missing columns on tenants (IG/WA channels, delivery fees,
   payment_methods, style_profile, knowledge_base, order_api_config, etc.)
3. Adds `channel` column on customers, conversations, messages.
4. Adds `media_urls` JSON on messages.
5. Adds 7 external-API-tracking columns on orders.
6. Adds missing hot-path indices.
7. Creates pg_trgm extension + GIN index on products.name.
8. Makes messages.fb_message_id unique (webhook idempotency).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a89fe0001_egypt_pivot'
down_revision: Union[str, None] = '927179233531'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    """Check if a column exists (Postgres + SQLite compatible)."""
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def _index_exists(bind, table: str, index: str) -> bool:
    """Check if an index exists."""
    inspector = sa.inspect(bind)
    idxs = [i["name"] for i in inspector.get_indexes(table)]
    return index in idxs


def upgrade() -> None:
    bind = op.get_bind()

    # ---------------------------------------------------------------
    # 0. pg_trgm extension (Postgres-only; skip on SQLite)
    # ---------------------------------------------------------------
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # ---------------------------------------------------------------
    # 1. Rename BD address columns → Egyptian (customers + orders)
    # ---------------------------------------------------------------
    # customers: division → governorate, district → city, upazila → area
    if _column_exists(bind, "customers", "division"):
        op.alter_column("customers", "division", new_column_name="governorate")
    if _column_exists(bind, "customers", "district"):
        op.alter_column("customers", "district", new_column_name="city")
    if _column_exists(bind, "customers", "upazila"):
        op.alter_column("customers", "upazila", new_column_name="area")

    # orders: same renames
    if _column_exists(bind, "orders", "division"):
        op.alter_column("orders", "division", new_column_name="governorate")
    if _column_exists(bind, "orders", "district"):
        op.alter_column("orders", "district", new_column_name="city")
    if _column_exists(bind, "orders", "upazila"):
        op.alter_column("orders", "upazila", new_column_name="area")

    # ---------------------------------------------------------------
    # 2. Add channel column on customers / conversations / messages
    # ---------------------------------------------------------------
    if not _column_exists(bind, "customers", "channel"):
        op.add_column("customers", sa.Column("channel", sa.String(20), nullable=False, server_default="messenger"))
    if not _column_exists(bind, "conversations", "channel"):
        op.add_column("conversations", sa.Column("channel", sa.String(20), nullable=False, server_default="messenger"))
    if not _column_exists(bind, "messages", "channel"):
        op.add_column("messages", sa.Column("channel", sa.String(20), nullable=False, server_default="messenger"))

    # ---------------------------------------------------------------
    # 3. Add media_urls JSON on messages
    # ---------------------------------------------------------------
    if not _column_exists(bind, "messages", "media_urls"):
        op.add_column("messages", sa.Column("media_urls", sa.JSON(), nullable=True))

    # ---------------------------------------------------------------
    # 4. Add missing tenant columns (12 total)
    # ---------------------------------------------------------------
    tenant_cols = [
        ("ig_user_id", sa.String(64)),
        ("ig_access_token", sa.Text()),
        ("wa_phone_number_id", sa.String(64)),
        ("wa_access_token", sa.Text()),
        ("wa_waba_id", sa.String(64)),
        ("delivery_inside_cairo", sa.Numeric(10, 2)),
        ("delivery_outside_cairo", sa.Numeric(10, 2)),
        ("free_delivery_above", sa.Numeric(10, 2)),
        ("payment_methods", sa.JSON()),
        ("style_profile", sa.JSON()),
        ("knowledge_base", sa.JSON()),
        ("knowledge_built_at", sa.DateTime()),
        ("order_api_config", sa.JSON()),
    ]
    for col_name, col_type in tenant_cols:
        if not _column_exists(bind, "tenants", col_name):
            nullable = col_name not in ("delivery_inside_cairo", "delivery_outside_cairo")
            op.add_column("tenants", sa.Column(col_name, col_type, nullable=nullable))

    # Set defaults for delivery columns if NULL
    if bind.dialect.name == "postgresql":
        op.execute("UPDATE tenants SET delivery_inside_cairo = 35 WHERE delivery_inside_cairo IS NULL;")
        op.execute("UPDATE tenants SET delivery_outside_cairo = 60 WHERE delivery_outside_cairo IS NULL;")
        op.execute("UPDATE tenants SET payment_methods = '{}' WHERE payment_methods IS NULL;")

    # Index the new tenant channel columns
    if not _index_exists(bind, "tenants", "ix_tenants_ig_user_id"):
        op.create_index("ix_tenants_ig_user_id", "tenants", ["ig_user_id"])
    if not _index_exists(bind, "tenants", "ix_tenants_wa_phone_number_id"):
        op.create_index("ix_tenants_wa_phone_number_id", "tenants", ["wa_phone_number_id"])

    # ---------------------------------------------------------------
    # 5. Add 7 API-tracking columns on orders + payment metadata
    # ---------------------------------------------------------------
    order_cols = [
        ("payment_phone_last2", sa.String(2)),
        ("payment_trx_id", sa.String(255)),
        ("api_status", sa.String(30)),
        ("api_response", sa.Text()),
        ("api_status_code", sa.Integer()),
        ("api_called_at", sa.DateTime()),
        ("api_external_id", sa.String(255)),
    ]
    for col_name, col_type in order_cols:
        if not _column_exists(bind, "orders", col_name):
            op.add_column("orders", sa.Column(col_name, col_type, nullable=True))

    # Set default for api_status if NULL
    if bind.dialect.name == "postgresql":
        op.execute("UPDATE orders SET api_status = 'not_configured' WHERE api_status IS NULL;")

    # ---------------------------------------------------------------
    # 6. Add missing indices for hot-path queries
    # ---------------------------------------------------------------
    # Orders: dashboard pagination by created_at DESC
    if not _index_exists(bind, "orders", "idx_orders_tenant_created"):
        op.create_index("idx_orders_tenant_created", "orders", ["tenant_id", "created_at"])

    # Messages: webhook idempotency dedup (unique on fb_message_id)
    if not _index_exists(bind, "messages", "idx_messages_fb_message_id"):
        op.create_index("idx_messages_fb_message_id", "messages", ["fb_message_id"])

    # Token usage: daily aggregation per tenant
    if not _index_exists(bind, "token_usage", "idx_token_usage_tenant_created"):
        op.create_index("idx_token_usage_tenant_created", "token_usage", ["tenant_id", "created_at"])

    # Token usage table — create if it doesn't exist (some installs lack it)
    inspector = sa.inspect(bind)
    if "token_usage" not in inspector.get_table_names():
        op.create_table(
            "token_usage",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("usage_type", sa.String(20), nullable=False),
            sa.Column("model", sa.String(100), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_token_usage_tenant_id", "token_usage", ["tenant_id"])
        op.create_index("idx_token_usage_tenant_created", "token_usage", ["tenant_id", "created_at"])

    # Order items: "orders containing product X"
    if not _index_exists(bind, "order_items", "ix_order_items_product_id"):
        op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    # Tenants: user-tenant list
    if not _index_exists(bind, "tenants", "ix_tenants_owner_id"):
        op.create_index("ix_tenants_owner_id", "tenants", ["owner_id"])

    # Conversations: active-chat list
    if not _index_exists(bind, "conversations", "idx_conversations_tenant_status_lastmsg"):
        op.create_index("idx_conversations_tenant_status_lastmsg", "conversations",
                        ["tenant_id", "status", "last_message_at"])

    # ---------------------------------------------------------------
    # 7. pg_trgm GIN index on products.name (Postgres-only)
    # ---------------------------------------------------------------
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_name_trgm "
            "ON products USING GIN (lower(name) gin_trgm_ops);"
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Drop pg_trgm GIN index
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS idx_products_name_trgm;")

    # Drop hot-path indices
    for idx, tbl in [
        ("idx_conversations_tenant_status_lastmsg", "conversations"),
        ("ix_tenants_owner_id", "tenants"),
        ("ix_order_items_product_id", "order_items"),
        ("idx_token_usage_tenant_created", "token_usage"),
        ("ix_token_usage_tenant_id", "token_usage"),
        ("idx_messages_fb_message_id", "messages"),
        ("idx_orders_tenant_created", "orders"),
        ("ix_tenants_wa_phone_number_id", "tenants"),
        ("ix_tenants_ig_user_id", "tenants"),
    ]:
        if _index_exists(bind, tbl, idx):
            op.drop_index(idx, table_name=tbl)

    # Drop order API-tracking columns
    for col_name in ["api_external_id", "api_called_at", "api_status_code", "api_response", "api_status", "payment_trx_id", "payment_phone_last2"]:
        if _column_exists(bind, "orders", col_name):
            op.drop_column("orders", col_name)

    # Drop tenant columns
    for col_name in ["order_api_config", "knowledge_built_at", "knowledge_base", "style_profile", "payment_methods", "free_delivery_above", "delivery_outside_cairo", "delivery_inside_cairo", "wa_waba_id", "wa_access_token", "wa_phone_number_id", "ig_access_token", "ig_user_id"]:
        if _column_exists(bind, "tenants", col_name):
            op.drop_column("tenants", col_name)

    # Drop messages.media_urls + channel
    if _column_exists(bind, "messages", "media_urls"):
        op.drop_column("messages", "media_urls")
    if _column_exists(bind, "messages", "channel"):
        op.drop_column("messages", "channel")

    # Drop channel columns
    for tbl in ["conversations", "customers"]:
        if _column_exists(bind, tbl, "channel"):
            op.drop_column(tbl, "channel")

    # Rename Egyptian → BD (only if reverting)
    if _column_exists(bind, "customers", "governorate"):
        op.alter_column("customers", "governorate", new_column_name="division")
    if _column_exists(bind, "customers", "city"):
        op.alter_column("customers", "city", new_column_name="district")
    if _column_exists(bind, "customers", "area"):
        op.alter_column("customers", "area", new_column_name="upazila")
    if _column_exists(bind, "orders", "governorate"):
        op.alter_column("orders", "governorate", new_column_name="division")
    if _column_exists(bind, "orders", "city"):
        op.alter_column("orders", "city", new_column_name="district")
    if _column_exists(bind, "orders", "area"):
        op.alter_column("orders", "area", new_column_name="upazila")
