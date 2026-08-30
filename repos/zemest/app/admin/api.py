"""Admin REST API endpoints for site-wide management.

All endpoints require is_superadmin=True on the User model.
"""
from __future__ import annotations

import ipaddress
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.admin import AuditLog, BlockedUser, IPBan, UserSession
from app.models.user import User
from app.models.tenant import Tenant
from app.models.order import Order
from app.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ============================================================
# Dependency: require superadmin
# ============================================================

async def require_superadmin(
    user: User = Depends(get_current_user),
) -> User:
    """Require the current user to be a superadmin."""
    if not user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user


# Alias for backward compatibility
get_superadmin = require_superadmin


# ============================================================
# Pydantic schemas
# ============================================================

class IPBanCreate(BaseModel):
    ip_or_cidr: str
    reason: Optional[str] = None


class IPBanResponse(BaseModel):
    id: str
    ip_or_cidr: str
    reason: Optional[str]
    is_active: bool
    created_at: datetime


class BlockUserRequest(BaseModel):
    reason: Optional[str] = None


class AnalyticsResponse(BaseModel):
    total_users: int
    total_tenants: int
    total_orders: int
    active_sessions: int
    blocked_users: int
    ip_bans: int
    total_tokens_used: int


class GeoDistributionItem(BaseModel):
    country: str
    user_count: int


class UserActivityItem(BaseModel):
    id: str
    ip_address: str
    country: Optional[str]
    city: Optional[str]
    device_type: Optional[str]
    browser: Optional[str]
    login_at: datetime
    last_activity: datetime
    is_active: bool


class AuditLogItem(BaseModel):
    id: int
    admin_id: str
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    ip: Optional[str]
    created_at: datetime


# ============================================================
# Helper: write audit log
# ============================================================

async def _write_audit_log(
    db: AsyncSession,
    admin: User,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Write an entry to the append-only audit log."""
    log = AuditLog(
        id=None,  # auto-increment
        admin_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_=metadata,
        ip=ip,
    )
    db.add(log)
    await db.flush()


# ============================================================
# User blocking endpoints
# ============================================================

@router.post("/users/{user_id}/block", status_code=200)
async def block_user_site_wide(
    user_id: uuid.UUID,
    req: BlockUserRequest,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Block a user from the entire site (across all tenants)."""
    # Check user exists
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already blocked
    existing = await db.execute(
        select(BlockedUser).where(BlockedUser.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already blocked")

    block = BlockedUser(
        id=uuid.uuid4(),
        user_id=user_id,
        reason=req.reason,
        blocked_by=admin.id,
    )
    db.add(block)
    await _write_audit_log(
        db, admin, "user.block", "user", str(user_id),
        metadata={"reason": req.reason},
    )
    await db.commit()
    return {"status": "blocked", "user_id": str(user_id)}


@router.delete("/users/{user_id}/block", status_code=200)
async def unblock_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Remove site-wide block from a user."""
    result = await db.execute(
        select(BlockedUser).where(BlockedUser.user_id == user_id)
    )
    block = result.scalar_one_or_none()
    if not block:
        raise HTTPException(status_code=404, detail="User not blocked")

    await db.delete(block)
    await _write_audit_log(db, admin, "user.unblock", "user", str(user_id))
    await db.commit()
    return {"status": "unblocked", "user_id": str(user_id)}


# ============================================================
# IP ban endpoints
# ============================================================

@router.get("/ip-bans")
async def list_ip_bans(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """List all active IP bans."""
    result = await db.execute(
        select(IPBan).where(IPBan.is_active == True).order_by(IPBan.created_at.desc())
    )
    bans = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "ip_or_cidr": b.ip_or_cidr,
            "reason": b.reason,
            "created_at": b.created_at.isoformat(),
        }
        for b in bans
    ]


@router.post("/ip-bans", status_code=201)
async def create_ip_ban(
    req: IPBanCreate,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Ban an IP address or CIDR range."""
    # Validate it's a valid IP or CIDR
    try:
        ipaddress.ip_address(req.ip_or_cidr)
    except ValueError:
        try:
            ipaddress.ip_network(req.ip_or_cidr, strict=False)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid IP or CIDR: {req.ip_or_cidr}",
            )

    # Check for duplicate
    existing = await db.execute(
        select(IPBan).where(IPBan.ip_or_cidr == req.ip_or_cidr)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="IP/CIDR already banned")

    ban = IPBan(
        id=uuid.uuid4(),
        ip_or_cidr=req.ip_or_cidr,
        reason=req.reason,
        banned_by=admin.id,
    )
    db.add(ban)
    await _write_audit_log(
        db, admin, "ip.ban", "ip", req.ip_or_cidr,
        metadata={"reason": req.reason},
    )
    await db.commit()
    return {"status": "banned", "ip_or_cidr": req.ip_or_cidr}


@router.delete("/ip-bans/{ban_id}", status_code=200)
async def delete_ip_ban(
    ban_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Remove an IP ban."""
    ban = await db.get(IPBan, ban_id)
    if not ban:
        raise HTTPException(status_code=404, detail="Ban not found")

    ban.is_active = False
    await _write_audit_log(db, admin, "ip.unban", "ip", ban.ip_or_cidr)
    await db.commit()
    return {"status": "unbanned", "ip_or_cidr": ban.ip_or_cidr}


# ============================================================
# Analytics endpoints
# ============================================================

@router.get("/analytics/overview")
async def get_analytics_overview(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Get platform-wide analytics overview."""
    # Count users
    users_count = await db.scalar(select(func.count(User.id)))
    tenants_count = await db.scalar(select(func.count(Tenant.id)).where(Tenant.is_active == True))
    orders_count = await db.scalar(select(func.count(Order.id)))
    blocked_count = await db.scalar(select(func.count(BlockedUser.id)).where(BlockedUser.is_blocked == True))
    bans_count = await db.scalar(select(func.count(IPBan.id)).where(IPBan.is_active == True))

    # Active sessions (last 30 min)
    thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
    active_sessions = await db.scalar(
        select(func.count(UserSession.id)).where(
            UserSession.is_active == True,
            UserSession.last_activity > thirty_min_ago,
        )
    )

    # Total tokens
    total_tokens = await db.scalar(select(func.sum(TokenUsage.total_tokens))) or 0

    return {
        "total_users": users_count or 0,
        "total_tenants": tenants_count or 0,
        "total_orders": orders_count or 0,
        "active_sessions": active_sessions or 0,
        "blocked_users": blocked_count or 0,
        "ip_bans": bans_count or 0,
        "total_tokens_used": int(total_tokens),
    }


@router.get("/analytics/geo-distribution")
async def get_geo_distribution(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Get user count by country."""
    result = await db.execute(
        select(
            UserSession.country,
            func.count(func.distinct(UserSession.user_id)).label("user_count"),
        )
        .where(UserSession.country.isnot(None))
        .group_by(UserSession.country)
        .order_by(func.count(func.distinct(UserSession.user_id)).desc())
    )
    rows = result.all()
    return [
        {"country": row[0] or "Unknown", "user_count": row[1]}
        for row in rows
    ]


@router.get("/analytics/user/{user_id}/activity")
async def get_user_activity(
    user_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Get a user's session history and activity."""
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .order_by(UserSession.login_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "ip_address": s.ip_address,
            "country": s.country,
            "city": s.city,
            "device_type": s.device_type,
            "browser": s.browser,
            "login_at": s.login_at.isoformat(),
            "last_activity": s.last_activity.isoformat(),
            "is_active": s.is_active,
        }
        for s in sessions
    ]


# ============================================================
# Audit log endpoints
# ============================================================

@router.get("/audit-log")
async def get_audit_log(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
):
    """Get paginated audit log."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.where(AuditLog.action == action)

    # Count total
    count_query = select(func.count(AuditLog.id))
    if action:
        count_query = count_query.where(AuditLog.action == action)
    total = await db.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": log.id,
                "admin_id": str(log.admin_id),
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "ip": log.ip,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# Active sessions (real-time)
# ============================================================

@router.get("/analytics/active-sessions")
async def get_active_sessions(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Get currently active sessions (last 30 minutes)."""
    thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
    result = await db.execute(
        select(UserSession)
        .where(
            UserSession.is_active == True,
            UserSession.last_activity > thirty_min_ago,
        )
        .order_by(UserSession.last_activity.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "user_id": str(s.user_id),
            "ip_address": s.ip_address,
            "country": s.country,
            "city": s.city,
            "device_type": s.device_type,
            "last_activity": s.last_activity.isoformat(),
        }
        for s in sessions
    ]
