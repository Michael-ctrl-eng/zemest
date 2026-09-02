"""user plan column (subscription tier)

Revision ID: e6b3d0004
Revises: d5a2c0003
Create Date: 2026-09-03

Plans module: users.plan (free|growth|pro) gates shop count, monthly
messages and daily LLM tokens (app/services/plan_service.py).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e6b3d0004"
down_revision = "d5a2c0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("plan", sa.String(20), nullable=False,
                      server_default="free")
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("plan")
