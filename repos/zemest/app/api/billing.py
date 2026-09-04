"""Billing API — subscribe / rails / subscription state / USDC check.

New billing architecture (rails: payoneer PRIMARY, paymob BACKUP,
usdc_solana for wallet users). Merchant-facing endpoints; every one is
authenticated and scoped to tenants OWNED by the caller (404 on foreign
tenants — no information leak, same posture as payments.py).

Routes:

* ``GET  /api/billing/plans``           — plan catalog
* ``GET  /api/billing/rails``           — which rails are configured
* ``GET  /api/billing/subscription``    — current subscription state
* ``POST /api/billing/subscribe``       — plan + rail → checkout session
  (fiat rails: hosted checkout URL; USDC: on-chain instructions)
* ``POST /api/billing/cancel``          — cancel at period end (default)
* ``POST /api/billing/reactivate``      — undo a scheduled cancel
* ``GET  /api/billing/transactions``    — invoice history
* ``POST /api/billing/usdc/check``      — trigger the on-chain settlement
  sweep and report this tenant's pending invoice
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.billing import (
    BillingSubscription,
    BillingTransaction,
    PaymentMethod,
)
from app.models.tenant import Tenant
from app.services.billing.providers import (
    ProviderConfigError,
    ProviderError,
    available_rails,
    get_provider,
)
from app.services.billing.subscription_engine import (
    cancel_subscription,
    create_subscription,
    ensure_default_plans,
    get_plan_by_code,
    reactivate_subscription,
    settle_usdc_invoices,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["Billing"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class SubscribeRequest(BaseModel):
    tenant_id: uuid.UUID
    plan_code: str = Field(..., min_length=1, max_length=30)
    # payoneer | paymob | usdc_solana — no removed rail.
    payment_method: str = Field(..., max_length=30)
    # Browser redirect after hosted checkout (UX only, never trusted).
    success_url: Optional[str] = Field(None, max_length=500)


class UsdcInstructions(BaseModel):
    network: str = "solana"
    deposit_address: str
    amount_usdc: str  # exact major-unit string, e.g. "15.000000"
    amount_micro: int
    reference_memo: str
    confirmations_required: int
    note: str = (
        "Send EXACTLY this amount of USDC (Solana network) to the address "
        "with the reference in the transfer memo. The payment is detected "
        "automatically after the required confirmations."
    )


class SubscribeResponse(BaseModel):
    tenant_id: str
    plan_code: str
    plan_name: str
    payment_method: str  # effective rail (may differ after fallback)
    subscription_status: str
    current_period_end: Optional[str]
    transaction_id: str
    amount: str
    currency: str
    checkout_url: Optional[str] = None
    usdc_instructions: Optional[UsdcInstructions] = None


class SubscriptionResponse(BaseModel):
    tenant_id: str
    status: str
    plan_code: Optional[str]
    plan_name: Optional[str]
    payment_method: Optional[str]
    current_period_start: Optional[str]
    current_period_end: Optional[str]
    cancel_at_period_end: bool
    dunning_attempts: int
    last_payment_at: Optional[str]
    limits: Optional[dict]


class TransactionItem(BaseModel):
    id: str
    kind: str
    payment_method: str
    status: str
    amount: str
    amount_usdc: Optional[str]
    currency: str
    checkout_url: Optional[str]
    solana_reference: Optional[str]
    created_at: Optional[str]
    paid_at: Optional[str]
    failed_reason: Optional[str]


class CancelRequest(BaseModel):
    tenant_id: uuid.UUID
    immediate: bool = False


class UsdcCheckResponse(BaseModel):
    tenant_id: str
    subscription_status: Optional[str]
    pending_invoice_id: Optional[str]
    pending_invoice_status: Optional[str]
    settled_now: bool
    swept_settled: int
    swept_voided: int


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _owned_tenant(
    db: AsyncSession, user, tenant_id: uuid.UUID
) -> Tenant:
    tenant = await db.scalar(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.owner_id == user.id)
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _webhook_base(request: Request) -> str:
    """Public base for webhook URLs — pinned config wins over Host header
    (kills notification_url hijack, audit D5 :301)."""
    pinned = get_settings().BILLING_WEBHOOK_PUBLIC_URL
    if pinned:
        return pinned.rstrip("/")
    return str(request.base_url).rstrip("/")


# --------------------------------------------------------------------------- #
# Plans & rails
# --------------------------------------------------------------------------- #
@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Plan catalog (idempotently seeded on boot)."""
    await ensure_default_plans(db)
    from app.models.billing import BillingPlan

    plans = (
        await db.scalars(
            select(BillingPlan)
            .where(BillingPlan.is_active.is_(True))
            .order_by(BillingPlan.price_egp)
        )
    ).all()
    return [
        {
            "code": p.code,
            "name": p.name,
            "description": p.description,
            "price_egp": str(p.price_egp),
            "price_usdc": str(p.price_usdc),
            "billing_interval": p.billing_interval,
            "trial_days": p.trial_days,
            "limits": p.limits,
        }
        for p in plans
    ]


@router.get("/rails")
async def list_rails():
    """Which payment rails are configured (drives the checkout buttons)."""
    settings = get_settings()
    return {
        "billing_enabled": settings.BILLING_ENABLED,
        "rails": available_rails(),
    }


# --------------------------------------------------------------------------- #
# Subscription lifecycle
# --------------------------------------------------------------------------- #
@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    tenant_id: uuid.UUID = Query(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_default_plans(db)
    tenant = await _owned_tenant(db, user, tenant_id)
    sub = await db.scalar(
        select(BillingSubscription)
        .options(selectinload(BillingSubscription.plan))
        .where(BillingSubscription.tenant_id == tenant.id)
    )
    if sub is None:
        return SubscriptionResponse(
            tenant_id=str(tenant.id),
            status="none",
            plan_code=None,
            plan_name=None,
            payment_method=None,
            current_period_start=None,
            current_period_end=None,
            cancel_at_period_end=False,
            dunning_attempts=0,
            last_payment_at=None,
            limits=None,
        )
    return SubscriptionResponse(
        tenant_id=str(tenant.id),
        status=sub.status,
        plan_code=sub.plan.code if sub.plan else None,
        plan_name=sub.plan.name if sub.plan else None,
        payment_method=sub.payment_method,
        current_period_start=sub.current_period_start.isoformat() if sub.current_period_start else None,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        cancel_at_period_end=sub.cancel_at_period_end,
        dunning_attempts=sub.dunning_attempts or 0,
        last_payment_at=sub.last_payment_at.isoformat() if sub.last_payment_at else None,
        limits=(sub.plan.limits if sub.plan else None),
    )


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    req: SubscribeRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Subscribe one of the caller's tenants to a plan on a chosen rail.

    * payoneer / paymob → hosted checkout URL (fallback payoneer→paymob
      happens automatically when the primary rail is unavailable).
    * usdc_solana → on-chain payment instructions (no hosted page).
    """
    settings = get_settings()
    if not settings.BILLING_ENABLED:
        raise HTTPException(status_code=503, detail="billing is disabled")

    await ensure_default_plans(db)
    tenant = await _owned_tenant(db, user, req.tenant_id)
    plan = await get_plan_by_code(db, req.plan_code)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not PaymentMethod.is_valid(req.payment_method):
        raise HTTPException(
            status_code=400,
            detail=f"payment_method must be one of {list(PaymentMethod.ALL)}",
        )
    # Chosen rail must actually be usable (USDC needs the treasury wallet
    # configured; fiat rails need credentials — fallback may rescue a
    # broken payoneer, but a broken USDC rail is a hard 400).
    try:
        provider = get_provider(req.payment_method)
        if not provider.is_configured():
            if req.payment_method != PaymentMethod.PAYONEER:
                raise HTTPException(
                    status_code=400,
                    detail=f"payment rail {req.payment_method} is not configured",
                )
            logger.info(
                "payoneer unconfigured for subscribe — falling back to paymob"
            )
    except ProviderConfigError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        subscription, transaction, checkout = await create_subscription(
            db,
            tenant,
            plan,
            req.payment_method,
            success_url=req.success_url or "",
            webhook_base_url=_webhook_base(request),
        )
    except ProviderConfigError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ProviderError:
        logger.exception("billing checkout failed for tenant %s", tenant.id)
        raise HTTPException(status_code=502, detail="payment gateway error")

    usdc_instructions = None
    if transaction.payment_method == PaymentMethod.USDC_SOLANA:
        micro = int((checkout.amount * Decimal(1_000_000)).to_integral_value())
        usdc_instructions = UsdcInstructions(
            deposit_address=checkout.deposit_address,
            amount_usdc=f"{checkout.amount:.6f}",
            amount_micro=micro,
            reference_memo=checkout.reference_memo,
            confirmations_required=get_settings().USDC_CONFIRMATIONS_REQUIRED,
        )

    return SubscribeResponse(
        tenant_id=str(tenant.id),
        plan_code=plan.code,
        plan_name=plan.name,
        payment_method=transaction.payment_method,
        subscription_status=subscription.status,
        current_period_end=(
            subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None
        ),
        transaction_id=str(transaction.id),
        amount=str(transaction.amount),
        currency=transaction.currency,
        checkout_url=transaction.checkout_url,
        usdc_instructions=usdc_instructions,
    )


@router.post("/cancel", response_model=SubscriptionResponse)
async def cancel(
    req: CancelRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel at period end by default — the merchant keeps every feature
    until the period they PAID for ends. Immediate only on explicit
    request."""
    tenant = await _owned_tenant(db, user, req.tenant_id)
    sub = await db.scalar(
        select(BillingSubscription).where(BillingSubscription.tenant_id == tenant.id)
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription to cancel")
    await cancel_subscription(db, sub, immediate=req.immediate)
    return await get_subscription(tenant_id=tenant.id, user=user, db=db)


@router.post("/reactivate", response_model=SubscriptionResponse)
async def reactivate(
    req: CancelRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _owned_tenant(db, user, req.tenant_id)
    sub = await db.scalar(
        select(BillingSubscription).where(BillingSubscription.tenant_id == tenant.id)
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription to reactivate")
    try:
        await reactivate_subscription(db, sub)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return await get_subscription(tenant_id=tenant.id, user=user, db=db)


@router.get("/transactions")
async def list_transactions(
    tenant_id: uuid.UUID = Query(...),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _owned_tenant(db, user, tenant_id)
    txns = (
        await db.scalars(
            select(BillingTransaction)
            .where(BillingTransaction.tenant_id == tenant.id)
            .order_by(BillingTransaction.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        TransactionItem(
            id=str(t.id),
            kind=t.kind,
            payment_method=t.payment_method,
            status=t.status,
            amount=str(t.amount),
            amount_usdc=str(t.amount_usdc) if t.amount_usdc is not None else None,
            currency=t.currency,
            checkout_url=t.checkout_url,
            solana_reference=t.solana_reference,
            created_at=t.created_at.isoformat() if t.created_at else None,
            paid_at=t.paid_at.isoformat() if t.paid_at else None,
            failed_reason=t.failed_reason,
        ).model_dump()
        for t in txns
    ]


@router.post("/usdc/check", response_model=UsdcCheckResponse)
async def usdc_check(
    req: CancelRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the on-chain USDC settlement sweep (all tenants — one RPC pass)
    and report this tenant's pending invoice state."""
    tenant = await _owned_tenant(db, user, req.tenant_id)
    stats = await settle_usdc_invoices(db)
    sub = await db.scalar(
        select(BillingSubscription).where(BillingSubscription.tenant_id == tenant.id)
    )
    pending = None
    if sub is not None:
        pending = await db.scalar(
            select(BillingTransaction)
            .where(
                BillingTransaction.subscription_id == sub.id,
                BillingTransaction.status.in_(("pending", "awaiting_confirmation")),
            )
            .order_by(BillingTransaction.created_at.desc())
        )
    settled_now = False
    if sub is not None and stats.get("settled_ids"):
        my_txns = {
            str(t.id)
            for t in (
                await db.scalars(
                    select(BillingTransaction).where(
                        BillingTransaction.subscription_id == sub.id
                    )
                )
            ).all()
        }
        settled_now = bool(set(my_txns) & set(stats["settled_ids"]))
    return UsdcCheckResponse(
        tenant_id=str(tenant.id),
        subscription_status=sub.status if sub else None,
        pending_invoice_id=str(pending.id) if pending else None,
        pending_invoice_status=pending.status if pending else None,
        settled_now=settled_now,
        swept_settled=int(stats.get("settled", 0)),
        swept_voided=int(stats.get("voided", 0)),
    )
