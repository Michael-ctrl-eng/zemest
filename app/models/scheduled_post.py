"""Models for scheduled social media posts."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScheduledPost(Base):
    """A scheduled social media post (FB Page or Instagram)."""
    __tablename__ = "scheduled_posts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)

    # Platform: 'facebook' or 'instagram'
    platform: Mapped[str] = mapped_column(String(20))  # facebook | instagram

    # Post content
    caption: Mapped[str] = mapped_column(Text)
    media_urls: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # list of public URLs
    media_type: Mapped[str] = mapped_column(String(20), default="text")  # text, photo, video, reel, story, carousel
    link: Mapped[Optional[str]] = mapped_column(String(1024))  # for FB link posts

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column()

    # Status: draft, scheduled, publishing, published, failed, cancelled
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)

    # Result (post_id from FB/IG after publishing)
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(255))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    # AI generation metadata
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_prompt: Mapped[Optional[str]] = mapped_column(Text)  # the prompt used to generate caption


class PostInsights(Base):
    """Cached insights for a published post."""
    __tablename__ = "post_insights"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scheduled_post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scheduled_posts.id"), index=True
    )
    platform: Mapped[str] = mapped_column(String(20))
    platform_post_id: Mapped[str] = mapped_column(String(255), index=True)

    # Metrics (JSON — different per platform)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    # FB: impressions, reach, engaged_users, reactions, comments, shares
    # IG: impressions, reach, engagement, saved, likes, comments, shares, video_views

    fetched_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow(), index=True)
