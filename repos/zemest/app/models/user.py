import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.db_types import EncryptedText


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
    # --- Trial & signup-abuse prevention (product: 7-day free trial) ---
    # Trial grants Growth-level limits for 7 days from registration. NULL =
    # no trial (IP already consumed one, or account pre-dates the system);
    # expiry is evaluated lazily in plan_service.effective_plan — no cron.
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    # IP the account was registered from — used to stop serial free-trial
    # farming (new accounts from a trial-consumed IP get no second trial)
    # and to cap total accounts per IP. Stored for admin visibility.
    signup_ip: Mapped[Optional[str]] = mapped_column(String(64), default=None, index=True)
    # Optional profile info (PII — encrypted at rest). Set by the user from
    # settings; surfaced in analytics/admin views. ISO date string.
    date_of_birth: Mapped[Optional[str]] = mapped_column(EncryptedText(), default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())

    tenants = relationship("Tenant", back_populates="owner")
    refresh_token_records = relationship(
        "RefreshTokenRecord", back_populates="user", cascade="all, delete-orphan"
    )
