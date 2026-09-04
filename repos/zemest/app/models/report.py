"""User → admin support reports (product: "Report" section).

A logged-in merchant writes a title + subject from their dashboard; the
report lands in the admin panel with full user context (who they are, where
they signed up from, what they've done on the platform) and — when
TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_CHAT_ID are configured — a Telegram
notification carrying a short admin code so the operator can triage from
their phone.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SupportReport(Base):
    __tablename__ = "support_reports"
    __table_args__ = (
        Index("idx_support_reports_status_created", "status", "created_at"),
        Index("idx_support_reports_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Short human-friendly code (e.g. "ZM-7K2QA9") used in Telegram alerts
    # and admin links. Not a secret — just a handle.
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(Text)
    # open -> in_review -> resolved
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
