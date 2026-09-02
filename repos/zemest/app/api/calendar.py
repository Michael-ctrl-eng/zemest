"""Calendar subscription — ICS feed of the tenant's publishing schedule.

Any calendar app (Google Calendar "From URL", Apple Calendar "New Calendar
Subscription", Outlook, Fastmail …) can subscribe to:

    GET /api/calendar/{token}/calendar.ics

The token is a per-tenant random secret — no login required, which is exactly
what calendar apps need. The owner can rotate it any time.

Also:
- POST /api/tenants/{id}/calendar/token → (re)generate the subscription token

Google Calendar:  https://calendar.google.com/calendar/render?cid=<URL>
Apple Calendar:   webcal://<host>/api/calendar/<token> (or the https URL)
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.dependencies import get_tenant
from app.models.scheduled_post import ScheduledPost
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Calendar"])


def _ensure_calendar_token(tenant: Tenant) -> str:
    if not tenant.calendar_token:
        tenant.calendar_token = secrets.token_urlsafe(24)
    return tenant.calendar_token


# ============================================================
# Token management (authenticated, per-tenant)
# ============================================================

@router.post("/tenants/{tenant_id}/calendar/token")
async def regenerate_calendar_token(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """(Re)generate the calendar subscription token. Rotating invalidates the
    old ICS URL — anyone subscribed with the old link stops receiving updates."""
    tenant.calendar_token = secrets.token_urlsafe(24)
    await db.commit()
    return {"calendar_token": tenant.calendar_token}


@router.get("/tenants/{tenant_id}/calendar/url")
async def get_calendar_url(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Return the subscription token (the frontend composes the public URL
    from window.location.origin so it works on any host the platform runs on)."""
    token = _ensure_calendar_token(tenant)
    await db.commit()
    return {"calendar_token": token}


# ============================================================
# The ICS feed (public, token-authenticated) — RFC 5545 via icalendar
# ============================================================
# The hand-rolled line emitter was replaced with the icalendar library
# (roadmap R6): it handles content-line folding at 75 octets, correct
# escaping of commas/semicolons/newlines, and VTIMEZONE blocks — things the
# old emitter got subtly wrong, which some calendar clients reject.


def _ics_dt(dt: datetime) -> datetime:
    """Normalize a datetime to the UTC-aware form icalendar expects.

    Scheduled-post timestamps are stored naive-UTC (datetime.utcnow()),
    so attach UTC when the value is naive; aware values pass through.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _build_ics(tenant: Tenant, posts) -> bytes:
    from icalendar import Calendar, Event

    cal = Calendar()
    cal.add("prodid", "-//Zemest//Post Scheduler//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", f"Zemest — {tenant.page_name}")
    cal.add("x-wr-timezone", "UTC")

    now = _ics_dt(datetime.utcnow())
    for p in posts:
        start = _ics_dt(p.scheduled_at)
        end = start + timedelta(minutes=30)
        status = "CONFIRMED" if p.status == "scheduled" else (
            "TRANSPARENT" if p.status in ("published", "publishing") else "CANCELLED"
        )
        summary = f"[{p.platform.upper()}] {p.caption[:60]}" if p.caption else f"[{p.platform.upper()}] post"
        if p.status == "published":
            summary = f"✓ {summary}"

        ev = Event()
        ev.add("uid", f"{p.id}@zemest")
        ev.add("dtstamp", now)
        ev.add("dtstart", start)
        ev.add("dtend", end)
        ev.add("summary", summary)
        ev.add("description", p.caption or "")
        ev.add("status", status)
        cal.add_component(ev)

    return cal.to_ical()


@router.get("/calendar/{token}/calendar.ics")
async def calendar_ics(token: str):
    """The subscribable ICS feed — every scheduled or published post as an event."""
    if not token or len(token) > 128:
        return Response("Invalid calendar token", status_code=404)

    async with async_session() as db:
        result = await db.execute(select(Tenant).where(Tenant.calendar_token == token))
        tenant = result.scalar_one_or_none()
        if not tenant or not tenant.is_active:
            return Response("Invalid calendar token", status_code=404)

        result = await db.execute(
            select(ScheduledPost)
            .where(
                ScheduledPost.tenant_id == tenant.id,
                ScheduledPost.status.in_(("scheduled", "published", "publishing")),
            )
            .order_by(ScheduledPost.scheduled_at.asc())
            .limit(500)
        )
        posts = result.scalars().all()

    body = _build_ics(tenant, posts)

    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="{tenant.page_name}-schedule.ics"',
            "Cache-Control": "no-store",
        },
    )
