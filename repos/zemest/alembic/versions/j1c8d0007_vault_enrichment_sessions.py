"""chat enrichment + encrypted vault + session tracking columns

Revision ID: j1c8d0007
Revises: i0a7b0006
Create Date: 2026-09-04

New:
- customers.email / customers.interests / customers.country — buyer
  intelligence folded in automatically from chat enrichment
  (app/ai/enrichment.py: Egyptian phone, email, governorate, interest
  tags, sentiment, intent — zero LLM cost)
- messages.enrichment — per-message extraction payload + when/where
  context (channel + timestamp + detected geo), server-side only
- user_sessions.browser — the model always declared it, DDL never created
  it; login now records sessions (audit F19: admin analytics tables were
  never populated)
- vault_files — index of AES-256-GCM encrypted, zstd/gzip-compressed
  archives (chat_archive / customer_profiles / user_profiles /
  analytics) extractable only by superadmins (app/services/vault.py)

The same columns/tables are patched idempotently at boot in app/main.py
for deployments that don't run alembic.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "j1c8d0007"
down_revision = "i0a7b0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- customers: buyer intelligence ----------------------------------
    op.add_column("customers", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("interests", sa.JSON(), nullable=True))
    op.add_column("customers", sa.Column("country", sa.String(64), nullable=True))

    # --- messages: enrichment payload ------------------------------------
    op.add_column("messages", sa.Column("enrichment", sa.JSON(), nullable=True))

    # --- user_sessions: the missing browser column ------------------------
    with op.batch_alter_table("user_sessions") as batch:
        batch.add_column(sa.Column("browser", sa.String(64), nullable=True))

    # --- vault_files: encrypted archive index -----------------------------
    op.create_table(
        "vault_files",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("period", sa.String(16), nullable=True),
        sa.Column("storage_path", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("plaintext_sha256", sa.String(64), nullable=False),
        sa.Column("original_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stored_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("codec", sa.String(8), nullable=False, server_default="gzip"),
        sa.Column("cipher", sa.String(16), nullable=False, server_default="aes-256-gcm"),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_vault_files_kind", "vault_files", ["kind"])
    op.create_index("ix_vault_files_created_at", "vault_files", ["created_at"])


def downgrade() -> None:
    op.drop_table("vault_files")
    with op.batch_alter_table("user_sessions") as batch:
        batch.drop_column("browser")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("enrichment")
    with op.batch_alter_table("customers") as batch:
        batch.drop_column("country")
        batch.drop_column("interests")
        batch.drop_column("email")
