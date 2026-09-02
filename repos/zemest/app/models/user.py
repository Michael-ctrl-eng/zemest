import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fb_user_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    # Unique + indexed: the register endpoint relies on this constraint to
    # close the SELECT-then-INSERT race (two concurrent registrations of the
    # same email previously both passed the existence check).
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Admin kill-switch: blocked users fail auth with 403 and every refresh
    # token is revoked at block time.
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Subscription plan: free | growth | pro. Gates shop count, channel
    # count, monthly messages and daily LLM tokens (app/services/plan_service.py).
    # Upgrades are payment-gated in production (Paymob) — see /api/me/plan.
    plan: Mapped[str] = mapped_column(String(20), default="free", server_default="free")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())

    tenants = relationship("Tenant", back_populates="owner")
    refresh_token_records = relationship(
        "RefreshTokenRecord", back_populates="user", cascade="all, delete-orphan"
    )
