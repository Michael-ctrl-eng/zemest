"""Admin-related models: site-wide user tracking, IP bans, audit log, sessions."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IPBan(Base):
    """IP ban list with CIDR support."""
    __tablename__ = "ip_bans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ip_or_cidr: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    banned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())


class UserSession(Base):
    """Tracks user sessions for analytics."""
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    ip_address: Mapped[str] = mapped_column(String(64), index=True)
    country: Mapped[Optional[str]] = mapped_column(String(64))
    city: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    device_type: Mapped[Optional[str]] = mapped_column(String(32))  # mobile, desktop, tablet
    browser: Mapped[Optional[str]] = mapped_column(String(64))
    login_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow(), index=True)
    logout_at: Mapped[Optional[datetime]] = mapped_column()
    last_activity: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    """Append-only audit log of admin actions.

    ``id`` MUST be ``Integer`` (not ``BigInteger``): on SQLite only an
    INTEGER PRIMARY KEY is a rowid alias and auto-assigns ids — BIGINT PKs
    make every INSERT fail with NOT NULL (id) on SQLite.
    """
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))  # user.block, ip.ban, user.unblock, etc.
    target_type: Mapped[Optional[str]] = mapped_column(String(32))  # user, ip, tenant
    target_id: Mapped[Optional[str]] = mapped_column(String(64))
    metadata_: Mapped[Optional[dict]] = mapped_column(JSON)
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow(), index=True)


class BlockedUser(Base):
    """Site-wide blocked users (separate from tenant-level)."""
    __tablename__ = "blocked_users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    blocked_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    blocked_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=True)


class SiteUser(Base):
    """Site-wide user tracking with geo/device info for admin analytics."""
    __tablename__ = "site_users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text)
    blocked_at: Mapped[Optional[datetime]] = mapped_column()
    blocked_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    last_ip: Mapped[Optional[str]] = mapped_column(String(64))
    last_country: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    last_country_code: Mapped[Optional[str]] = mapped_column(String(8))
    last_city: Mapped[Optional[str]] = mapped_column(String(64))
    last_latitude: Mapped[Optional[float]] = mapped_column()
    last_longitude: Mapped[Optional[float]] = mapped_column()
    last_user_agent: Mapped[Optional[str]] = mapped_column(Text)
    last_device_type: Mapped[Optional[str]] = mapped_column(String(32))
    last_seen: Mapped[Optional[datetime]] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
