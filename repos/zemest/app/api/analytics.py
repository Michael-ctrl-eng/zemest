"""Analytics API: first-party click/view collection + merchant summaries.

Endpoints:
- ``POST /api/analytics/collect`` — PUBLIC (rate-limited). The frontend
  tracker beacons batches of page_view / click / scroll / session_end
  events. No cookies required, no PII in the payload: the client sends an
  anonymous visitor key, a session key and paths; IP/geo/UA are captured
  server-side, and identity is linked ONLY from the authenticated session
  (the BFF forwards the httpOnly cookie as a Bearer header).
- ``GET /api/analytics/summary`` — authenticated merchant view of their own
  blog/store page performance ("what engages, what sucks").

Admin-wide endpoints live in app/admin/api.py.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.middleware.rate_limit import get_limiter
from app.models.blog_post import BlogPost
from app.models.tenant import Tenant
from app.services import analytics_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

try:
    _limiter = get_limiter()
except Exception:  # pragma: no cover — soft dependency
    _limiter = None


class EventIn(BaseModel):
    type: str = Field(max_length=20)
    path: str = Field(max_length=512)
    page_name: Optional[str] = Field(default=None, max_length=255)
    element: Optional[str] = Field(default=None, max_length=128)
    scroll: Optional[int] = Field(default=None, ge=0, le=100)
    session_pages: Optional[int] = Field(default=None, ge=0, le=500)


class CollectIn(BaseModel):
    visitor: str = Field(max_length=72)
    session: Optional[str] = Field(default=None, max_length=64)
    events: list[EventIn] = Field(default_factory=list, max_length=60)


@router.post("/collect", status_code=204)
@_limiter.limit("60/minute")
async def collect(
    request: Request,
    payload: CollectIn,
    db: AsyncSession = Depends(get_db),
):
    """Collect one batch of analytics events (always 204).

    Malformed events are dropped silently — a buggy tracker must not lose
    the valid events in the same batch, and the client gets no error signal
    to retry-loop on.
    """
    # Optional identity link: reuse the JWT machinery, but never 401 here —
    # anonymous visitors are the norm.
    user = None
    try:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            from app.utils.security import decode_token
            from app.models.user import User

            claims = decode_token(auth_header.split(" ", 1)[1].strip())
            if claims and claims.get("sub"):
                import uuid as _uuid

                try:
                    user = await db.get(User, _uuid.UUID(str(claims["sub"])))
                except (ValueError, TypeError):
                    user = None
    except Exception:  # noqa: BLE001 — analytics must never 401/500
        user = None

    client_ip = None
    if request.client and request.client.host:
        client_ip = request.client.host
    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer")

    try:
        events = [e.model_dump() for e in payload.events]
        await analytics_service.ingest_events(
            db,
            events,
            visitor_key=payload.visitor,
            session_key=payload.session,
            client_ip=client_ip,
            user_agent=user_agent,
            referrer=referrer,
            user=user,
        )
        await db.commit()
    except Exception:  # noqa: BLE001 — never break the page for analytics
        try:
            await db.rollback()
        except Exception:
            pass
        logger.warning("analytics collect failed", exc_info=True)
    return None


@router.get("/summary")
async def merchant_summary(
    days: int = 14,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Performance of THIS merchant's own public pages (blog posts).

    Scopes the aggregate tables to the paths of the user's published blog
    posts — the store/blog surface they actually control.
    """
    tenants = (
        await db.execute(select(Tenant.id).where(Tenant.owner_id == user.id))
    ).scalars().all()

    slug_stmt = select(BlogPost.slug).where(BlogPost.status == "published")
    if tenants:
        slug_stmt = slug_stmt.where(BlogPost.tenant_id.in_(tenants))
    else:
        return {"days": days, "pages": [], "totals": {"views": 0, "clicks": 0, "sessions": 0, "bounces": 0}}
    slugs = (await db.execute(slug_stmt)).scalars().all()

    if not slugs:
        return {"days": days, "pages": [], "totals": {"views": 0, "clicks": 0, "sessions": 0, "bounces": 0}}

    pages = []
    for slug in slugs:
        perf = await analytics_service.page_performance(
            db, days=days, path_prefix=f"/blog/{slug}", worst_first=False, limit=1
        )
        pages.extend(perf)
    totals = await analytics_service.summary_totals(db, days=days, path_prefix="/blog/")

    # Only keep rows that belong to one of the user's slugs.
    wanted = {f"/blog/{s}" for s in slugs}
    pages = [p for p in pages if p["path"] in wanted]
    pages.sort(key=lambda p: -p["views"])
    return {"days": days, "pages": pages, "totals": totals}


__all__ = ["router"]
