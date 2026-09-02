"""auth hardening: unique email, is_blocked, refresh-token ledger

Revision ID: b1f0a0001_auth_hardening
Revises: a89fe0001_egypt_pivot
Create Date: 2026-09-02 00:00:00

This migration supports the F1 auth-hardening wave:
1. ``users.email`` becomes UNIQUE (closes the registration race and lets
   the register endpoint convert the constraint violation into an
   anti-enumeration 202 instead of a leaked 400).
   Pre-existing duplicates (if any) are de-duplicated deterministically
   before the unique index is created.
2. ``users.is_blocked`` — admin kill-switch, 403 on every authenticated call.
3. New table ``refresh_token_records`` — rotation ledger with compare-and-
   swap reuse detection.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1f0a0001_auth_hardening'
down_revision: Union[str, None] = 'a89fe0001_egypt_pivot'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. de-duplicate emails before enforcing uniqueness ----------------
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DELETE FROM users u
            USING users v
            WHERE u.email IS NOT NULL
              AND u.email = v.email
              AND u.created_at > v.created_at
            """
        )
    else:
        # SQLite (dev/test): keep the earliest row per email.
        op.execute(
            """
            DELETE FROM users
            WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM users
                WHERE email IS NOT NULL
                GROUP BY email
            )
            AND email IS NOT NULL
            """
        )

    # --- 2. users.is_blocked -----------------------------------------------
    if not _column_exists(bind, "users", "is_blocked"):
        op.add_column(
            "users",
            sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    # --- 3. unique index on users.email ------------------------------------
    op.create_index("ix_users_email_unique", "users", ["email"], unique=True)

    # --- 4. refresh-token rotation ledger ----------------------------------
    op.create_table(
        "refresh_token_records",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid() if hasattr(sa, "Uuid") else sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("replaced_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_refresh_token_records_user_id", "refresh_token_records", ["user_id"])
    op.create_index("ix_refresh_token_records_revoked", "refresh_token_records", ["revoked"])
    op.create_index("ix_refresh_token_records_expires_at", "refresh_token_records", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_token_records_expires_at", table_name="refresh_token_records")
    op.drop_index("ix_refresh_token_records_revoked", table_name="refresh_token_records")
    op.drop_index("ix_refresh_token_records_user_id", table_name="refresh_token_records")
    op.drop_table("refresh_token_records")
    op.drop_index("ix_users_email_unique", table_name="users")
    op.drop_column("users", "is_blocked")
