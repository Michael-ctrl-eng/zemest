import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text, JSON, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BlogPost(Base):
    """SEO blog for a tenant's shop — block-based editor + measurable SEO.

    Blocks (JSON array, order preserved):
        {"type": "heading",   "level": 2, "text": "..."}
        {"type": "paragraph", "text": "..."}
        {"type": "image",     "url": "https://...", "alt": "..."}
        {"type": "quote",     "text": "...", "cite": "..."}

    Lifecycle: draft → published (published_at set, appears on /blog and in
    sitemap.xml) → unpublished back to draft.
    """

    __tablename__ = "blog_posts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_blogpost_tenant_slug"),
        Index("idx_blogpost_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), index=True
    )
    slug: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    # Focus keyword the SEO score optimizes for.
    keyword: Mapped[Optional[str]] = mapped_column(String(100))
    meta_description: Mapped[Optional[str]] = mapped_column(String(300))
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(512))
    blocks: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|published
    # 0-100 from blog_service.score_seo (recomputed on every save).
    seo_score: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    tenant = relationship("Tenant")

    @property
    def word_count(self) -> int:
        words = 0
        for block in self.blocks or []:
            if block.get("text"):
                words += len(str(block["text"]).split())
        return words
