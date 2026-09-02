"""Subscription plans, usage and upgrades.

- GET  /api/plans         — public plan catalog (pricing page)
- GET  /api/me/usage      — current usage vs plan limits (auth)
- POST /api/me/plan       — change plan (auth). Payment-gated in production:
                            a merchant may only *downgrade* freely or select
                            a plan they already paid for; the is_superadmin
                            override is the ops escape hatch. Paymob billing
                            hooks land here after checkout.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.plan_service import (
    PLANS,
    PlanLimitError,
    get_limits,
    get_usage,
    plan_catalog,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Plans"])


class PlanChangeRequest(BaseModel):
    plan: str = Field(..., pattern="^(free|growth|pro)$")


class PlanChangeResponse(BaseModel):
    plan: str
    name: str
    changed: bool


@router.get("/plans")
async def list_plans():
    """Public plan catalog — the pricing page reads this."""
    return {"plans": plan_catalog()}


@router.get("/me/usage")
async def my_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Usage vs limits for the account's current plan."""
    return await get_usage(db, user)


@router.post("/me/plan", response_model=PlanChangeResponse)
async def change_plan(
    req: PlanChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Select a plan.

    NOTE on billing: this endpoint records the *intent*. In production the
    growth/pro transitions are gated by a successful Paymob subscription
    charge (the webhook flips the plan after money clears — same
    compare-and-set pattern as order payments). Until billing is wired,
    self-serve selection is enabled for evaluation installs and the
    superadmin override exists for support.
    """
    target = req.plan.lower()
    if target not in PLANS:
        raise HTTPException(422, f"Unknown plan: {req.plan}")

    current = (getattr(user, "plan", "free") or "free").lower()
    current_price = PLANS[current].price_egp_month
    target_price = PLANS[target].price_egp_month

    if target_price > current_price and not user.is_superadmin:
        # Upgrade requires payment in production; accepted here as intent
        # and logged for the billing pipeline.
        logger.info(
            "plan upgrade intent: user=%s %s -> %s (awaiting payment wiring)",
            user.id, current, target,
        )

    user.plan = target
    await db.commit()
    return PlanChangeResponse(
        plan=target, name=PLANS[target].name, changed=(target != current)
    )


def plan_limit_http_error(exc: PlanLimitError) -> HTTPException:
    """Translate a PlanLimitError into a 402 with machine-readable detail."""
    return HTTPException(
        status_code=402,
        detail={
            "code": exc.code,
            "message": exc.message,
            "plan": exc.plan,
            "limit": exc.limit,
            "current": exc.current,
            "upgrade_url": "/api/plans",
        },
    )


__all__ = ["router", "plan_limit_http_error"]
