"""Admin REST API endpoints for site-wide management.

All endpoints require is_superadmin=True on the User model.
"""
from __future__ import annotations

import ipaddress
import json
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


# ============================================================
# Site analytics (first-party click/view tracking)
# ============================================================

@router.get("/analytics/pages")
async def analytics_pages(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    days: int = Query(14, ge=1, le=90),
    worst: bool = Query(True, description="Rank worst-engaging pages first"),
    prefix: Optional[str] = Query(None, max_length=512),
):
    """Per-path page performance + engagement ranking ("what sucks")."""
    from app.services import analytics_service

    pages = await analytics_service.page_performance(
        db, days=days, path_prefix=prefix, worst_first=worst
    )
    totals = await analytics_service.summary_totals(db, days=days, path_prefix=prefix)
    return {"totals": totals, "pages": pages}


@router.get("/analytics/visitors")
async def analytics_visitors(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Visitor directory (IP, geo, device, interests, PII decrypted)."""
    from app.services import analytics_service

    items, total = await analytics_service.visitor_list(
        db, query=q, limit=limit, offset=offset
    )
    return {"visitors": items, "total": total, "limit": limit, "offset": offset}


@router.get("/analytics/visitors/{visitor_id}")
async def analytics_visitor_detail(
    visitor_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Full drill-down: profile + recent events + linked user & shops."""
    from app.services import analytics_service

    data = await analytics_service.visitor_detail(db, visitor_id)
    if not data:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return data


@router.get("/analytics/storage")
async def analytics_storage(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Compression/storage stats for the raw event blobs."""
    from app.services import analytics_service

    return await analytics_service.storage_stats(db)


@router.get("/analytics/export")
async def analytics_export(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    day: str = Query(..., description="YYYY-MM-DD"),
):
    """Decrypt + decompress a day's raw events back to JSONL.

    The "extract the data for any use" requirement: batches are stored
    compressed+encrypted; this endpoint returns the original event stream.
    """
    from app.services import analytics_service

    try:
        from datetime import date as _date

        parsed = _date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=422, detail="day must be YYYY-MM-DD")

    events = await analytics_service.read_day_events(db, parsed)
    await _write_audit_log(db, admin, "analytics.export", "day", day)
    await db.commit()
    from fastapi.responses import PlainTextResponse

    lines = "\n".join(
        json.dumps(e, separators=(",", ":"), ensure_ascii=False) for e in events
    )
    return PlainTextResponse(
        content=lines or "",
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="analytics-{day}.jsonl"'},
    )


@router.post("/analytics/compact")
async def analytics_compact(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    day: Optional[str] = Query(None, description="YYYY-MM-DD (default: yesterday)"),
):
    """Merge a day's event batches into one blob (maintenance)."""
    from datetime import date as _date, timedelta as _td

    from app.services import analytics_service

    if day:
        try:
            target = _date.fromisoformat(day)
        except ValueError:
            raise HTTPException(status_code=422, detail="day must be YYYY-MM-DD")
    else:
        target = datetime.utcnow().date() - _td(days=1)

    merged = await analytics_service.compact_day(db, target)
    await _write_audit_log(
        db, admin, "analytics.compact", "day", target.isoformat(), metadata={"merged": merged}
    )
    await db.commit()
    return {"day": target.isoformat(), "batches_merged": merged}


# ============================================================
# Support reports (user dashboard → admin panel)
# ============================================================

class ReportStatusIn(BaseModel):
    status: str
    admin_note: Optional[str] = None


@router.get("/reports")
async def admin_reports(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """All reports with full submitter context (plan, signup IP, shops)."""
    from app.services import report_service

    return await report_service.admin_list_reports(
        db, status=status, page=page, page_size=page_size
    )


@router.get("/reports/{report_id}")
async def admin_report_detail(
    report_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """One report + everything about the submitter (sessions, shops, activity)."""
    from app.services import report_service

    report = await report_service.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    user = await db.get(User, report.user_id)
    context = None
    if user:
        sessions = (
            await db.execute(
                select(UserSession)
                .where(UserSession.user_id == user.id)
                .order_by(UserSession.login_at.desc())
                .limit(5)
            )
        ).scalars().all()
        shops = int(
            (await db.execute(
                select(func.count(Tenant.id)).where(
                    Tenant.owner_id == user.id, Tenant.is_active == True  # noqa: E712
                )
            )).scalar()
            or 0
        )
        context = {
            "name": user.name,
            "email": user.email,
            "plan": user.plan,
            "signup_ip": user.signup_ip,
            "trial_ends_at": user.trial_ends_at.isoformat() if getattr(user, "trial_ends_at", None) else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "shops": shops,
            "recent_sessions": [
                {
                    "ip": s.ip_address,
                    "country": s.country,
                    "city": s.city,
                    "device": s.device_type,
                    "login_at": s.login_at.isoformat(),
                }
                for s in sessions
            ],
        }
    data = {
        "id": str(report.id),
        "code": report.code,
        "title": report.title,
        "subject": report.subject,
        "status": report.status,
        "admin_note": report.admin_note,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
        "user": context,
    }
    return data


@router.patch("/reports/{report_id}")
async def admin_update_report(
    report_id: uuid.UUID,
    req: ReportStatusIn,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update report status / add an internal note."""
    from app.services import report_service

    report = await report_service.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        await report_service.update_report_status(db, report, req.status, req.admin_note)
    except report_service.ReportError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    await _write_audit_log(
        db,
        admin,
        "report.status",
        "report",
        str(report.id),
        metadata={"status": req.status},
    )
    await db.commit()
    return {"id": str(report.id), "status": report.status}


# ============================================================
# Encrypted data vault (chat / profile archives)
# ============================================================

from app.models.vault import VaultFile  # noqa: E402 — local import kept last
from app.services import vault as vault_service  # noqa: E402


class VaultArchiveIn(BaseModel):
    kind: str  # user_profiles | customer_profiles | chat_archive
    tenant_id: Optional[str] = None


@router.get("/vault")
async def admin_list_vault(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
    kind: Optional[str] = None,
):
    """Index of encrypted vault archives (metadata only — never plaintext)."""
    query = select(VaultFile).order_by(VaultFile.created_at.desc())
    if kind:
        query = query.where(VaultFile.kind == kind)
    rows = (await db.execute(query.limit(200))).scalars().all()
    return {
        "available": vault_service.vault_available(),
        "codec": "zstd" if vault_service._ZSTD_OK else "gzip",
        "files": [
            {
                "id": str(v.id),
                "kind": v.kind,
                "period": v.period,
                "tenant_id": str(v.tenant_id) if v.tenant_id else None,
                "row_count": v.row_count,
                "original_bytes": v.original_bytes,
                "stored_bytes": v.stored_bytes,
                "codec": v.codec,
                "cipher": v.cipher,
                "sha256": v.sha256,
                "compression_ratio": round(v.stored_bytes / max(1, v.original_bytes), 4),
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in rows
        ],
    }


@router.post("/vault/archive", status_code=201)
async def admin_create_vault_archive(
    req: VaultArchiveIn,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Build + seal a new encrypted archive from live data.

    Kinds: chat_archive (full conversations incl. enrichment + customer
    profiles), customer_profiles (buyer intelligence), user_profiles
    (accounts + sessions + trial state).
    """
    if req.kind not in ("user_profiles", "customer_profiles", "chat_archive"):
        raise HTTPException(status_code=422, detail="Unknown archive kind")

    if not vault_service.vault_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Vault is not configured: set VAULT_MASTER_KEY (32-byte hex) "
                "in the server environment to enable encrypted archives."
            ),
        )

    tenant_uuid = None
    if req.tenant_id:
        try:
            tenant_uuid = uuid.UUID(req.tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant id")

    records = await _collect_vault_records(db, req.kind, tenant_uuid)
    if not records:
        raise HTTPException(status_code=404, detail="No records matched this archive request")

    try:
        vf = await vault_service.archive_records(
            db, req.kind, records, tenant_id=tenant_uuid, created_by=admin.id
        )
    except vault_service.VaultError as e:
        raise HTTPException(status_code=500, detail=str(e))
    await _write_audit_log(
        db, admin, "vault.archive", "vault", str(vf.id),
        metadata={"kind": req.kind, "rows": vf.row_count},
    )
    await db.commit()
    return {
        "id": str(vf.id),
        "kind": vf.kind,
        "row_count": vf.row_count,
        "original_bytes": vf.original_bytes,
        "stored_bytes": vf.stored_bytes,
        "compression_ratio": round(vf.stored_bytes / max(1, vf.original_bytes), 4),
    }


async def _collect_vault_records(
    db: AsyncSession, kind: str, tenant_uuid: Optional[uuid.UUID]
) -> list[dict]:
    """Assemble the record sets that go into encrypted archives."""
    if kind == "user_profiles":
        rows = (await db.execute(
            select(User).order_by(User.created_at.desc()).limit(5000)
        )).scalars().all()
        sessions = (await db.execute(
            select(UserSession).order_by(UserSession.login_at.desc()).limit(20000)
        )).scalars().all()
        sessions_by_user: dict = {}
        for s in sessions:
            sessions_by_user.setdefault(str(s.user_id), []).append(
                {
                    "ip": s.ip_address,
                    "country": s.country,
                    "city": s.city,
                    "device_type": s.device_type,
                    "browser": s.browser,
                    "login_at": s.login_at.isoformat() if s.login_at else None,
                }
            )
        tenant_counts = dict((await db.execute(
            select(Tenant.owner_id, func.count(Tenant.id)).group_by(Tenant.owner_id)
        )).all())
        return [
            {
                "user_id": str(u.id),
                "name": u.name,
                "email": u.email,
                "dob": u.date_of_birth,
                "plan": u.plan,
                "trial_ends_at": u.trial_ends_at.isoformat() if u.trial_ends_at else None,
                "signup_ip": u.signup_ip,
                "is_superadmin": bool(u.is_superadmin),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "recent_sessions": sessions_by_user.get(str(u.id), [])[:50],
                "tenants_count": int(tenant_counts.get(u.id, 0)),
            }
            for u in rows
        ]

    if kind == "customer_profiles":
        from app.models.customer import Customer

        query = select(Customer).order_by(Customer.created_at.desc()).limit(5000)
        if tenant_uuid is not None:
            query = query.where(Customer.tenant_id == tenant_uuid)
        rows = (await db.execute(query)).scalars().all()
        return [
            {
                "customer_id": str(c.id),
                "tenant_id": str(c.tenant_id),
                "name": c.name,
                "phone": c.phone,
                "email": c.email,
                "dob": c.date_of_birth,
                "interests": c.interests,
                "profile_url": c.profile_url,
                "channel": c.channel,
                "governorate": c.governorate,
                "city": c.city,
                "area": c.area,
                "address_detail": c.address_detail,
                "country": c.country,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]

    if kind == "chat_archive":
        from app.models.conversation import Conversation
        from app.models.customer import Customer
        from app.models.message import Message

        conv_query = select(Conversation).order_by(Conversation.last_message_at.desc()).limit(2000)
        if tenant_uuid is not None:
            conv_query = conv_query.where(Conversation.tenant_id == tenant_uuid)
        conversations = (await db.execute(conv_query)).scalars().all()

        customers = {
            str(c.id): c
            for c in (await db.execute(select(Customer))).scalars().all()
        }
        records = []
        for conv in conversations:
            customer = customers.get(str(conv.customer_id))
            messages = (await db.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at)
                .limit(1000)
            )).scalars().all()
            records.append({
                "conversation_id": str(conv.id),
                "tenant_id": str(conv.tenant_id),
                "channel": conv.channel,
                "classification": conv.classification,
                "started_at": conv.started_at.isoformat() if conv.started_at else None,
                "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
                "customer": (
                    {
                        "id": str(customer.id),
                        "name": customer.name,
                        "phone": customer.phone,
                        "email": customer.email,
                        "interests": customer.interests,
                        "governorate": customer.governorate,
                        "city": customer.city,
                        "area": customer.area,
                        "country": customer.country,
                        "profile_url": customer.profile_url,
                    }
                    if customer
                    else None
                ),
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "channel": m.channel,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                        "enrichment": m.enrichment,
                        "media_urls": m.media_urls,
                    }
                    for m in messages
                ],
            })
        return records

    return []


@router.get("/vault/{file_id}/extract")
async def admin_extract_vault_file(
    file_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Decrypt + decompress one vault archive and return its rows."""
    vf = await db.get(VaultFile, file_id)
    if not vf:
        raise HTTPException(status_code=404, detail="Vault file not found")
    try:
        result = await vault_service.extract_records(db, vf)
    except vault_service.VaultError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await _write_audit_log(
        db, admin, "vault.extract", "vault", str(file_id),
        metadata={"kind": vf.kind, "rows": vf.row_count},
    )
    await db.commit()
    return result


# ============================================================
# Billing admin — subscriptions, invoices, payouts, fraud
# (all superadmin-only, all audit-logged where money moves)
# ============================================================

@router.get("/billing/subscriptions")
async def admin_billing_subscriptions(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """All subscriptions (optionally filtered by status) with owner info."""
    from app.models.billing import Subscription

    stmt = select(Subscription).order_by(Subscription.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Subscription.status == status)
    subs = (await db.execute(stmt)).scalars().all()

    user_ids = {s.user_id for s in subs}
    users = {}
    if user_ids:
        rows = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users = {u.id: u for u in rows}

    return [
        {
            "id": str(s.id),
            "user_id": str(s.user_id),
            "user_email": users.get(s.user_id).email if users.get(s.user_id) else None,
            "user_name": users.get(s.user_id).name if users.get(s.user_id) else None,
            "plan": s.plan,
            "status": s.status,
            "provider": s.provider,
            "current_period_end": s.current_period_end.isoformat() if s.current_period_end else None,
            "cancel_at_period_end": s.cancel_at_period_end,
            "failed_attempts": s.failed_attempts,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in subs
    ]


@router.get("/billing/invoices")
async def admin_billing_invoices(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Revenue view: every invoice, its status, dunning state."""
    from app.models.billing import Invoice

    stmt = select(Invoice).order_by(Invoice.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Invoice.status == status)
    invoices = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(i.id),
            "number": i.number,
            "user_id": str(i.user_id),
            "plan": i.plan,
            "amount": i.amount,
            "currency": i.currency,
            "status": i.status,
            "paid_at": i.paid_at.isoformat() if i.paid_at else None,
            "attempt_count": i.attempt_count,
            "next_attempt_at": i.next_attempt_at.isoformat() if i.next_attempt_at else None,
            "last_error": i.last_error,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in invoices
    ]


@router.get("/billing/overview")
async def admin_billing_overview(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Headline counters for the admin billing panel."""
    from app.models.billing import FraudFlag, Invoice, PayoutRequest, Subscription

    async def _count(model, *filters):
        stmt = select(func.count(model.id))
        if filters:
            stmt = stmt.where(*filters)
        return int((await db.execute(stmt)).scalar() or 0)

    mrr_cents = 0
    active_subs = (await db.execute(
        select(Subscription).where(Subscription.status == "active")
    )).scalars().all()
    for s in active_subs:
        mrr_cents += {"growth": 1299, "pro": 3499}.get(s.plan, 0)

    paid_invoices = (await db.execute(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(Invoice.status == "paid")
    )).scalar() or 0

    return {
        "active_subscriptions": len(active_subs),
        "past_due_subscriptions": await _count(
            Subscription, Subscription.status == "past_due"
        ),
        "canceled_subscriptions": await _count(
            Subscription, Subscription.status == "canceled"
        ),
        "trialing_subscriptions": await _count(
            Subscription, Subscription.status == "trialing"
        ),
        "mrr_cents": mrr_cents,
        "lifetime_revenue_cents": int(paid_invoices),
        "open_invoices": await _count(Invoice, Invoice.status.in_(("draft", "open"))),
        "payouts_pending": await _count(
            PayoutRequest, PayoutRequest.status.in_(("pending", "approved", "processing"))
        ),
        "payouts_paid_cents": int((await db.execute(
            select(func.coalesce(func.sum(PayoutRequest.net_amount), 0)).where(
                PayoutRequest.status == "paid"
            )
        )).scalar() or 0),
        "fraud_flags_open": await _count(FraudFlag, FraudFlag.resolved_at.is_(None)),
    }


@router.get("/billing/payouts")
async def admin_billing_payouts(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Payout queue: every request with rail, amounts, status."""
    from app.models.billing import PayoutAccount, PayoutRequest

    stmt = select(PayoutRequest).order_by(PayoutRequest.requested_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(PayoutRequest.status == status)
    payouts = (await db.execute(stmt)).scalars().all()

    account_ids = {p.payout_account_id for p in payouts}
    accounts = {}
    if account_ids:
        rows = (await db.execute(
            select(PayoutAccount).where(PayoutAccount.id.in_(account_ids))
        )).scalars().all()
        accounts = {a.id: a for a in rows}

    return [
        {
            "id": str(p.id),
            "user_id": str(p.user_id),
            "rail": p.rail,
            "amount": p.amount,
            "fee_amount": p.fee_amount,
            "net_amount": p.net_amount,
            "currency": p.currency,
            "status": p.status,
            "tx_hash": p.tx_hash,
            "provider_ref": p.provider_ref,
            "failure_reason": p.failure_reason,
            "approved_by": p.approved_by,
            "destination": (
                accounts.get(p.payout_account_id).label
                if accounts.get(p.payout_account_id)
                else None
            ),
            "requested_at": p.requested_at.isoformat() if p.requested_at else None,
            "processed_at": p.processed_at.isoformat() if p.processed_at else None,
        }
        for p in payouts
    ]


@router.post("/billing/payouts/{payout_id}/approve")
async def admin_approve_payout(
    payout_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Approve + execute a pending payout (manual review queue)."""
    from app.models.billing import PayoutRequest
    from app.services.billing import PayoutError
    from app.services.billing.payouts import approve as approve_payout

    payout = await db.get(PayoutRequest, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout request not found")
    try:
        payout = await approve_payout(db, payout, approved_by=f"admin:{admin.id}")
    except PayoutError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await _write_audit_log(
        db, admin, "billing.payout.approve", "payout", str(payout_id),
        metadata={"rail": payout.rail, "amount": payout.amount, "status": payout.status},
    )
    await db.commit()
    return {"status": payout.status, "id": str(payout.id), "tx_hash": payout.tx_hash}


@router.post("/billing/payouts/{payout_id}/retry")
async def admin_retry_payout(
    payout_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed payout on its rail (idempotent per request id)."""
    from app.models.billing import PayoutRequest
    from app.services.billing.payouts import execute as execute_payout

    payout = await db.get(PayoutRequest, payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout request not found")
    if payout.status != "failed":
        raise HTTPException(status_code=409, detail=f"payout is {payout.status}, not failed")
    payout.status = "approved"
    payout.failure_reason = None
    await db.commit()
    payout = await execute_payout(db, payout)
    await _write_audit_log(
        db, admin, "billing.payout.retry", "payout", str(payout_id),
        metadata={"rail": payout.rail, "status": payout.status},
    )
    await db.commit()
    return {"status": payout.status, "id": str(payout.id), "tx_hash": payout.tx_hash}


@router.get("/billing/fraud")
async def admin_billing_fraud(
    limit: int = Query(50, le=200),
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Open fraud flags (the review queue)."""
    from app.models.billing import FraudFlag

    flags = (await db.execute(
        select(FraudFlag)
        .where(FraudFlag.resolved_at.is_(None))
        .order_by(FraudFlag.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return [
        {
            "id": str(f.id),
            "user_id": str(f.user_id),
            "kind": f.kind,
            "severity": f.severity,
            "detail": f.detail,
            "action_taken": f.action_taken,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in flags
    ]


@router.post("/billing/fraud/{flag_id}/resolve")
async def admin_resolve_fraud_flag(
    flag_id: uuid.UUID,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a fraud flag (releases payout holds when none remain)."""
    from app.models.billing import FraudFlag

    flag = await db.get(FraudFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    flag.resolved_at = datetime.utcnow()
    flag.resolved_by = f"admin:{admin.id}"
    await _write_audit_log(
        db, admin, "billing.fraud.resolve", "fraud_flag", str(flag_id), metadata={}
    )
    await db.commit()
    return {"status": "resolved"}


@router.get("/billing/events")
async def admin_billing_events(
    limit: int = Query(50, le=200),
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Webhook ledger — the audit trail of every money event."""
    from app.models.billing import PaymentEvent

    events = (await db.execute(
        select(PaymentEvent).order_by(PaymentEvent.received_at.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": str(e.id),
            "provider": e.provider,
            "provider_event_id": e.provider_event_id,
            "event_type": e.event_type,
            "outcome": e.outcome,
            "detail": e.detail,
            "signature_valid": e.signature_valid,
            "status": e.status,
            "received_at": e.received_at.isoformat() if e.received_at else None,
        }
        for e in events
    ]


@router.post("/billing/tick")
async def admin_billing_tick(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Manually run the billing cycle (renew/dunning/expire)."""
    from app.services.billing.subscription_engine import billing_tick

    stats = await billing_tick(db)
    await _write_audit_log(
        db, admin, "billing.tick", "billing", "manual", metadata=stats
    )
    await db.commit()
    return stats


@router.post("/users/{user_id}/subscription")
async def admin_set_subscription(
    user_id: uuid.UUID,
    body: dict,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Grant/override a subscription manually (comps, support cases).

    Body: {"plan": "growth"|"pro", "status": "active", "reason": "..."}
    """
    from app.models.billing import Subscription
    from app.services.billing.subscription_engine import PERIOD_DAYS

    plan = str(body.get("plan") or "").lower()
    if plan not in ("growth", "pro", "free"):
        raise HTTPException(status_code=400, detail="plan must be growth|pro|free")
    reason = str(body.get("reason") or "admin grant")[:200]

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from sqlalchemy import update as _update
    from datetime import datetime as _dt, timedelta as _td

    if plan == "free":
        await db.execute(
            _update(Subscription)
            .where(Subscription.user_id == user_id, Subscription.status.in_(("active", "trialing", "past_due")))
            .values(status="canceled", canceled_at=_dt.utcnow(), canceled_by="admin",
                    cancel_reason=reason)
        )
        user.plan = "free"
        await db.commit()
    else:
        now = _dt.utcnow()
        res = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status.in_(("active", "trialing", "past_due")),
            ).order_by(Subscription.created_at.desc())
        )
        sub = res.scalars().first()
        if sub is None:
            sub = Subscription(
                user_id=user_id, plan=plan, status="active", provider="manual",
                current_period_start=now,
                current_period_end=now + _td(days=PERIOD_DAYS),
            )
            db.add(sub)
        else:
            sub.plan = plan
            sub.status = "active"
            sub.cancel_at_period_end = False
            sub.current_period_end = now + _td(days=PERIOD_DAYS)
        user.plan = plan
        await db.commit()

    await _write_audit_log(
        db, admin, "billing.subscription.set", "user", str(user_id),
        metadata={"plan": plan, "reason": reason},
    )
    await db.commit()
    return {"status": "ok", "plan": plan}
