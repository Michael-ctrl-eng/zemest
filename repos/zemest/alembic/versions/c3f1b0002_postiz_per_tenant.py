"""per-tenant Postiz session + channel hardening groundwork

Revision ID: c3f1b0002
Revises: b1f0a0001
Create Date: 2026-09-03

Audit A4-H1: one process-wide Postiz session was shared by every tenant —
any tenant's /postiz/login overwrote the global session token and the next
tenant's requests acted with it (cross-tenant post deletion / posting as
other tenants' pages). This adds per-tenant Postiz credentials so each
tenant gets a private client with its own persisted token.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3f1b0002"
down_revision = "b1f0a0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("postiz_email", sa.String(255), nullable=True))
        batch.add_column(sa.Column("postiz_token", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("postiz_token")
        batch.drop_column("postiz_email")
