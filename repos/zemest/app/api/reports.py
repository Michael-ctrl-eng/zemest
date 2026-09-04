"""User-side support reports ("Report" section in the merchant dashboard).

A merchant files a report with a title + subject; it lands in the admin
panel (with full user context) and optionally pings the operator's Telegram
bot. Users can list their own reports and see resolution status.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.services import report_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["Reports"])


class ReportCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=10, max_length=5_000)


class ReportOut(BaseModel):
    id: str
    code: str
    title: str
    subject: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    resolved_at: str | None = None


@router.post("", status_code=201, response_model=ReportOut)
async def create_report(
    req: ReportCreateIn,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """File a new report (title + subject) — lands in the admin panel."""
    try:
        report = await report_service.create_report(db, user, req.title, req.subject)
        await db.commit()
        return _out(report)
    except report_service.ReportError as e:
        raise HTTPException(status_code=e.status, detail=e.message)


@router.get("", response_model=list[ReportOut])
async def my_reports(
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The current user's reports, newest first."""
    items = await report_service.list_own_reports(db, user, limit=limit, offset=offset)
    return [ReportOut(**item) for item in items]


def _out(r) -> ReportOut:
    return ReportOut(
        id=str(r.id),
        code=r.code,
        title=r.title,
        subject=r.subject,
        status=r.status,
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
        resolved_at=r.resolved_at.isoformat() if r.resolved_at else None,
    )


__all__ = ["router"]
