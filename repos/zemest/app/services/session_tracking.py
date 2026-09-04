"""User session + geo tracking (fixes audit F19: admin analytics tables
``user_sessions`` / ``site_users`` existed but were never populated, so
every admin screen showed zero sessions and no geo distribution).

Every successful login records a ``UserSession`` row (IP, geo, user-agent,
device, browser) and upserts ``SiteUser`` with the same intelligence. IP
attribution follows the deployment's trusted-proxy posture: uvicorn runs
with ``--proxy-headers`` and a loopback/private allow-list, so
``request.client.host`` is already the REAL visitor IP when behind the BFF
(and the socket peer when direct). Geo lookups are best-effort via the
optional GeoLite2 database — without the mmdb file everything still works,
geo fields stay None.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.geo import detect_device_type, locate_ip
from app.models.admin import SiteUser, UserSession
from app.models.user import User

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    """Trusted client IP (uvicorn ProxyHeaders already rewrote it)."""
    return (request.client.host if request.client else "") or "unknown"

# Browser sniffing for the admin sessions screen (display only).
def _browser_of(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "edg/" in ua:
        return "Edge"
    if "opr/" in ua or "opera" in ua:
        return "Opera"
    if "chrome" in ua and "chromium" not in ua:
        return "Chrome"
    if "chromium" in ua:
        return "Chromium"
    if "firefox" in ua:
        return "Firefox"
    if "safari" in ua:
        return "Safari"
    if "bot" in ua or "crawler" in ua or "spider" in ua:
        return "Bot"
    return "Other"


async def record_user_session(db: AsyncSession, user: User, request: Request) -> None:
    """Insert a UserSession row + upsert SiteUser for a successful login.

    Best-effort by design: failures are logged and swallowed by the caller
    (a tracking bug must never lock a user out of their account).
    """
    ip = _client_ip(request)
    user_agent = (request.headers.get("user-agent") or "")[:2000]
    device_type = detect_device_type(user_agent)
    browser = _browser_of(user_agent)

    geo = None
    try:
        geo = locate_ip(ip)
    except Exception:  # noqa: BLE001 — geoip2 issues must never break auth
        geo = None

    db.add(
        UserSession(
            user_id=user.id,
            ip_address=ip,
            country=(geo or {}).get("country"),
            city=(geo or {}).get("city"),
            user_agent=user_agent,
            device_type=device_type,
            browser=browser,
            is_active=True,
        )
    )
    await db.flush()

    # Upsert the site-user intelligence row.
    site_user = (await db.execute(
        select(SiteUser).where(SiteUser.user_id == user.id)
    )).scalar_one_or_none()
    if site_user is None:
        db.add(
            SiteUser(
                user_id=user.id,
                last_ip=ip,
                last_country=(geo or {}).get("country"),
                last_country_code=(geo or {}).get("country_code"),
                last_city=(geo or {}).get("city"),
                last_latitude=(geo or {}).get("lat"),
                last_longitude=(geo or {}).get("lon"),
                last_user_agent=user_agent,
                last_device_type=device_type,
                last_seen=datetime.utcnow(),
            )
        )
    else:
        site_user.last_ip = ip
        site_user.last_country = (geo or {}).get("country")
        site_user.last_country_code = (geo or {}).get("country_code")
        site_user.last_city = (geo or {}).get("city")
        site_user.last_latitude = (geo or {}).get("lat")
        site_user.last_longitude = (geo or {}).get("lon")
        site_user.last_user_agent = user_agent
        site_user.last_device_type = device_type
        site_user.last_seen = datetime.utcnow()
    await db.flush()


async def touch_last_activity(db: AsyncSession, user_id) -> None:
    """Keep the newest active session for this user 'alive' (refresh path)."""
    try:
        latest = (await db.execute(
            select(UserSession.id)
            .where(UserSession.user_id == user_id, UserSession.is_active == True)  # noqa: E712
            .order_by(UserSession.login_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if latest is not None:
            await db.execute(
                update(UserSession)
                .where(UserSession.id == latest)
                .values(last_activity=datetime.utcnow())
            )
    except Exception:  # noqa: BLE001
        logger.debug("touch_last_activity failed", exc_info=True)


async def mark_sessions_inactive(db: AsyncSession, user_id) -> None:
    """Logout: close the user's active sessions (best-effort)."""
    try:
        await db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_active == True,  # noqa: E712
            )
            .values(is_active=False, logout_at=datetime.utcnow())
        )
    except Exception:  # noqa: BLE001
        logger.debug("mark_sessions_inactive failed", exc_info=True)
