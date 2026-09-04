"""ai-core hardening: unique fb_message_id, order pipeline guards

Revision ID: b2f0a0002_ai_core
Revises: b1f0a0001_auth_hardening
Create Date: 2026-09-02 00:00:00

F2 AI-core wave:
1. ``messages.fb_message_id`` becomes UNIQUE — webhook dedup races
   (Meta redelivery) now fail at the DB instead of double-spending LLM
   calls and creating duplicate orders.
2. Deduplication of legacy duplicate rows before the constraint lands.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f0a0002_ai_core'
down_revision: Union[str, None] = 'j1c8d0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # De-duplicate legacy fb_message_id collisions (keep earliest).
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DELETE FROM messages m
            USING messages v
            WHERE m.fb_message_id IS NOT NULL
              AND m.fb_message_id = v.fb_message_id
              AND m.created_at > v.created_at
            """
        )
    else:
        op.execute(
            """
            DELETE FROM messages
            WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM messages
                WHERE fb_message_id IS NOT NULL
                GROUP BY fb_message_id
            )
            AND fb_message_id IS NOT NULL
            """
        )

    op.create_unique_constraint(
        "uq_messages_fb_message_id", "messages", ["fb_message_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_messages_fb_message_id", "messages", type_="unique")
