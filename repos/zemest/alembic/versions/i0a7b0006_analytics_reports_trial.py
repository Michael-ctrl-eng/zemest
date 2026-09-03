"""analytics + reports + trial columns (2026-09 product wave)

Revision ID: i0a7b0006
Revises: f7c4e0005
Create Date: 2026-09-03

New:
- analytics_batches / analytics_daily / visitor_profiles (first-party
  click+view analytics; raw events stored zstd/zlib-compressed + Fernet
  encrypted, aggregates in plain counters for dashboards)
- support_reports (merchant dashboard "Report" section → admin panel,
  optional Telegram alert)
- users.trial_ends_at / users.signup_ip / users.date_of_birth — 7-day
  trial with per-IP abuse prevention; DOB (encrypted) for analytics views
- customers.date_of_birth / customers.profile_url — buyer demographics
  (encrypted DOB) + public profile link

The same columns are patched idempotently at boot in app/main.py for
deployments that don't run alembic (create_all + ALTER loop).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "i0a7b0006"
down_revision = "f7c4e0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users: trial + signup IP + DOB --------------------------------
    op.add_column("users", sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("signup_ip", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Text(), nullable=True))
    op.create_index("ix_users_signup_ip", "users", ["signup_ip"])

    # --- customers: DOB + profile link ----------------------------------
    op.add_column("customers", sa.Column("date_of_birth", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("profile_url", sa.String(512), nullable=True))

    # --- analytics batches ----------------------------------------------
    op.create_table(
        "analytics_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("compression", sa.String(8), nullable=False, server_default="zstd"),
        sa.Column("blob", sa.LargeBinary(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stored_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_compacted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_analytics_batches_day", "analytics_batches", ["day"])
    op.create_index(
        "idx_analytics_batches_day", "analytics_batches", ["day", "created_at"]
    )

    # --- analytics daily aggregates -------------------------------------
    op.create_table(
        "analytics_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("page_name", sa.String(255), nullable=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bounces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scroll_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scroll_events", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visitor_keys", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("day", "path", name="uq_analytics_daily_day_path"),
    )
    op.create_index("idx_analytics_daily_path", "analytics_daily", ["path"])
    op.create_index("ix_analytics_daily_day", "analytics_daily", ["day"])

    # --- visitor profiles -------------------------------------------------
    op.create_table(
        "visitor_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visitor_key", sa.String(72), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("date_of_birth", sa.Text(), nullable=True),
        sa.Column("country", sa.String(64), nullable=True),
        sa.Column("city", sa.String(64), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("last_ip", sa.String(64), nullable=True),
        sa.Column("last_user_agent", sa.Text(), nullable=True),
        sa.Column("device_type", sa.String(32), nullable=True),
        sa.Column("browser", sa.String(64), nullable=True),
        sa.Column("first_referrer", sa.String(512), nullable=True),
        sa.Column("interests", sa.JSON(), nullable=True),
        sa.Column("pages_viewed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sessions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_events", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_visitor_profiles_visitor_key", "visitor_profiles", ["visitor_key"], unique=True)
    op.create_index("ix_visitor_profiles_user_id", "visitor_profiles", ["user_id"])
    op.create_index("idx_visitor_profiles_last_seen", "visitor_profiles", ["last_seen"])

    # --- support reports ---------------------------------------------------
    op.create_table(
        "support_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_support_reports_code", "support_reports", ["code"], unique=True)
    op.create_index("ix_support_reports_user", "support_reports", ["user_id"])
    op.create_index(
        "idx_support_reports_status_created", "support_reports", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("support_reports")
    op.drop_table("visitor_profiles")
    op.drop_table("analytics_daily")
    op.drop_table("analytics_batches")
    op.drop_column("customers", "profile_url")
    op.drop_column("customers", "date_of_birth")
    op.drop_index("ix_users_signup_ip", table_name="users")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "signup_ip")
    op.drop_column("users", "trial_ends_at")
