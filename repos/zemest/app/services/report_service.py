"""Support reports: merchant dashboard → admin panel (+ Telegram alert).
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import SupportReport
from app.models.user import User
from app.services.telegram_notify import notify_admin_async

MAX_TITLE = 200
MAX_SUBJECT = 5_000
VALID_STATUSES = ("open", "in_review", "resolved")


class ReportError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _new_code() -> str:
    return f"ZM-{secrets.token_hex(3).upper()}"  # e.g. ZM-7K2QA9


async def create_report(db: AsyncSession, user: User, title: str, subject: str) -> SupportReport:
    title = (title or "").strip()[:MAX_TITLE]
    subject = (subject or "").strip()[:MAX_SUBJECT]
    if not title:
        raise ReportError("title_required", "A title is required")
    if len(subject) < 10:
        raise ReportError("subject_too_short", "Describe your issue in at least 10 characters")

    report = SupportReport(
        code=_new_code(),
        user_id=user.id,
        title=title,
        subject=subject,
        status="open",
    )
    db.add(report)
    await db.flush()

    notify_admin_async(
        f"🔔 <b>New report {report.code}</b>\n"
        f"<b>From:</b> {user.name} ({user.email or 'no email'})\n"
        f"<b>Title:</b> {title}\n\n"
        f"{subject[:600]}"
    )
    return report


async def list_own_reports(
    db: AsyncSession, user: User, limit: int = 50, offset: int = 0
) -> list[dict]:
    rows = (
        await db.execute(
            select(SupportReport)
            .where(SupportReport.user_id == user.id)
            .order_by(SupportReport.created_at.desc())
            .limit(min(limit, 100))
            .offset(max(offset, 0))
        )
    ).scalars().all()
    return [_report_public(r) for r in rows]


def _report_public(r: SupportReport, admin_view: bool = False, context: Optional[dict] = None) -> dict:
    data = {
        "id": str(r.id),
        "code": r.code,
        "title": r.title,
        "subject": r.subject,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
    }
    if admin_view:
        data["admin_note"] = r.admin_note
        data["user_id"] = str(r.user_id)
        if context:
            data["user"] = context
    return data


async def admin_list_reports(
    db: AsyncSession,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """All reports with submitter context (product: "view all the reports
    with everything he did")."""
    stmt = select(SupportReport)
    count_stmt = select(func.count(SupportReport.id))
    if status and status in VALID_STATUSES:
        stmt = stmt.where(SupportReport.status == status)
        count_stmt = count_stmt.where(SupportReport.status == status)
    total = int((await db.execute(count_stmt)).scalar() or 0)
    rows = (
        await db.execute(
            stmt.order_by(SupportReport.created_at.desc())
            .limit(min(page_size, 100))
            .offset((max(page, 1) - 1) * min(page_size, 100))
        )
    ).scalars().all()

    # Submitter context in one pass (users + their signup IP/plan/trial +
    # shop count + last session).
    from app.models.tenant import Tenant

    out = []
    for r in rows:
        user = await db.get(User, r.user_id)
        context = None
        if user:
            shops = int(
                (
                    await db.execute(
                        select(func.count(Tenant.id)).where(
                            Tenant.owner_id == user.id, Tenant.is_active == True  # noqa: E712
                        )
                    )
                ).scalar()
                or 0
            )
            context = {
                "name": user.name,
                "email": user.email,
                "plan": user.plan,
                "signup_ip": user.signup_ip,
                "shops": shops,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        out.append(_report_public(r, admin_view=True, context=context))
    return {"reports": out, "total": total, "page": page, "page_size": page_size}


async def get_report(db: AsyncSession, report_id) -> Optional[SupportReport]:
    import uuid as _uuid

    try:
        rid = _uuid.UUID(str(report_id))
    except (ValueError, TypeError):
        return None
    return await db.get(SupportReport, rid)


async def update_report_status(
    db: AsyncSession,
    report: SupportReport,
    status: str,
    admin_note: Optional[str] = None,
) -> SupportReport:
    status = (status or "").strip().lower()
    if status not in VALID_STATUSES:
        raise ReportError("invalid_status", f"Status must be one of {VALID_STATUSES}")
    report.status = status
    if admin_note is not None:
        report.admin_note = admin_note.strip()[:5_000]
    report.resolved_at = datetime.utcnow() if status == "resolved" else None
    await db.flush()
    return report


__all__ = [
    "ReportError",
    "create_report",
    "list_own_reports",
    "admin_list_reports",
    "get_report",
    "update_report_status",
]
