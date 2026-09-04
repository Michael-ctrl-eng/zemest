"""encrypt legacy channel tokens at rest

Revision ID: d5a2c0003
Revises: c3f1b0002
Create Date: 2026-09-03

Audit A4-H4: existing rows written before the EncryptedText columns keep
their plaintext tokens readable via the legacy passthrough — this data
migration re-encrypts every stored channel/Postiz token so nothing
plaintext remains at rest.

NOTE: run with the same TOKEN_ENCRYPTION_KEY / JWT_SECRET_KEY env the app
uses. No schema change (EncryptedText is app-level; the columns stay TEXT).
"""
from alembic import op
import sqlalchemy as sa

from app.utils.token_crypto import encrypt_token, is_encrypted


# revision identifiers, used by Alembic.
revision = "d5a2c0003"
down_revision = "c3f1b0002"
branch_labels = None
depends_on = None

_TOKEN_COLUMNS = (
    "page_access_token",
    "ig_access_token",
    "wa_access_token",
    "postiz_token",
)


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(f"SELECT id, {', '.join(_TOKEN_COLUMNS)} FROM tenants")
    ).mappings()

    encrypted = 0
    for row in rows:
        updates = {}
        for col in _TOKEN_COLUMNS:
            value = row[col]
            if value and not is_encrypted(value):
                updates[col] = encrypt_token(value)
        if updates:
            set_clause = ", ".join(f"{c} = :{c}" for c in updates)
            conn.execute(
                sa.text(f"UPDATE tenants SET {set_clause} WHERE id = :id"),
                {**updates, "id": row["id"]},
            )
            encrypted += 1

    if encrypted:
        print(f"[d5a2c0003] re-encrypted tokens for {encrypted} tenant row(s)")


def downgrade() -> None:
    # Decryption happens automatically at read time; no reverse data change.
    pass
