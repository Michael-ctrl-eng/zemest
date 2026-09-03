"""First-party site analytics: click/view events, daily aggregates, visitor
profiles.

Design goals (product requirement, verbatim):
- capture "analysis for every click and views" across public pages, blog and
  store pages, so we can see what engages and what "sucks";
- store the raw event stream **compressed + encrypted at rest** and keep the
  storage footprint minimal (raw JSONL ~150 B/event -> ~15-25 B/event after
  zstd; a 2026-09 comparison: the same payload in a naive ORM-per-event table
  would be ~10x larger);
- remain **decryptable on demand** so data can be extracted for any later use
  (admin export endpoint returns the original JSONL);
- keep dashboards fast WITHOUT decryption: a per-day/per-path aggregate table
  is maintained incrementally on ingest.

Three storage layers:

``AnalyticsBatch``   raw events, packed as JSONL -> zstd/zlib -> Fernet,
                    one row per collected request (a compaction job merges
                    same-day rows into one). This is the "file" layer.
``AnalyticsDaily``  incrementally-updated counters per (day, path):
                    views / clicks / sessions / bounces / exits / scroll.
                    Powers every dashboard query; tiny (one row per page per
                    day).
``VisitorProfile``  person-level record per anonymous visitor key (or
                    logged-in user): IP, geo, device, pages viewed count,
                    interests derived from browsed paths, first/last seen.
                    PII columns (email, name, DOB) are ``EncryptedText`` —
                    encrypted at rest, decrypted only for admin views.

Privacy posture:
- the browser tracker sends NO PII: only an anonymous visitor id, a session
  id, path, event type and scroll depth. Identity (email / user link) is
  attached SERVER-SIDE from the authenticated session — client claims are
  never trusted.
- raw IPs are kept (product decision: the admin panel is the operator's own
  data), but PII that identifies a person is encrypted at rest.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.db_types import EncryptedText


class AnalyticsBatch(Base):
    """One compressed+encrypted blob of raw analytics events (JSONL).

    ``blob`` = Fernet(compress(jsonl)). ``compression`` records the codec
    ("zstd" when the ``zstandard`` package is present, "zlib" fallback) so
    the reader knows how to decompress after decrypting. ``size_bytes`` is
    the uncompressed JSONL length (for compression-ratio stats),
    ``stored_bytes`` the on-disk blob length.
    """

    __tablename__ = "analytics_batches"
    __table_args__ = (
        Index("idx_analytics_batches_day", "day", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    day: Mapped[date] = mapped_column(Date, index=True)
    compression: Mapped[str] = mapped_column(String(8), default="zstd")
    blob: Mapped[bytes] = mapped_column(LargeBinary)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    stored_bytes: Mapped[int] = mapped_column(Integer, default=0)
    is_compacted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())


class AnalyticsDaily(Base):
    """Per (day, path) counters — the queryable aggregate layer.

    Bounce = session that saw exactly one page. Exit = last path of a
    session. ``visitor_keys`` is a capped distinct-visitor approximation
    (list of visitor keys seen that day on that path, max ~500 entries).
    """

    __tablename__ = "analytics_daily"
    __table_args__ = (
        UniqueConstraint("day", "path", name="uq_analytics_daily_day_path"),
        Index("idx_analytics_daily_path", "path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    day: Mapped[date] = mapped_column(Date, index=True)
    path: Mapped[str] = mapped_column(String(512))
    page_name: Mapped[Optional[str]] = mapped_column(String(255))
    views: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    sessions: Mapped[int] = mapped_column(Integer, default=0)
    bounces: Mapped[int] = mapped_column(Integer, default=0)
    exits: Mapped[int] = mapped_column(Integer, default=0)
    scroll_total: Mapped[int] = mapped_column(Integer, default=0)
    scroll_events: Mapped[int] = mapped_column(Integer, default=0)
    visitor_keys: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )


class VisitorProfile(Base):
    """Person-level analytics profile (site visitor / logged-in merchant).

    ``visitor_key`` is the anonymous client id ("v-<uuid>") or "u-<user_id>"
    once the visitor authenticates. Email / name / DOB are encrypted at rest
    and are only ever written from server-side context (authenticated user),
    never from client payloads.
    """

    __tablename__ = "visitor_profiles"
    __table_args__ = (
        Index("idx_visitor_profiles_last_seen", "last_seen"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    visitor_key: Mapped[str] = mapped_column(String(72), unique=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), index=True, default=None
    )
    # PII — encrypted at rest (EncryptedText), server-side written only.
    email: Mapped[Optional[str]] = mapped_column(EncryptedText(), default=None)
    name: Mapped[Optional[str]] = mapped_column(EncryptedText(), default=None)
    date_of_birth: Mapped[Optional[str]] = mapped_column(EncryptedText(), default=None)
    # Geo / device — captured server-side per request.
    country: Mapped[Optional[str]] = mapped_column(String(64))
    city: Mapped[Optional[str]] = mapped_column(String(64))
    latitude: Mapped[Optional[float]] = mapped_column()
    longitude: Mapped[Optional[float]] = mapped_column()
    last_ip: Mapped[Optional[str]] = mapped_column(String(64))
    last_user_agent: Mapped[Optional[str]] = mapped_column(Text)
    device_type: Mapped[Optional[str]] = mapped_column(String(32))
    browser: Mapped[Optional[str]] = mapped_column(String(64))
    first_referrer: Mapped[Optional[str]] = mapped_column(String(512))
    # Behavioural summary.
    interests: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    pages_viewed: Mapped[int] = mapped_column(Integer, default=0)
    sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    total_events: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    last_seen: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow(), index=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
