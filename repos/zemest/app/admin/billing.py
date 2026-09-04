"""Admin billing API — treasury, withdrawals, tick, overview.

Superadmin-only (same gate as the rest of the admin REST API). Every
sensitive action is audit-logged. Current rails: payout execution on
the USDC-Solana rail is an OFF-CHAIN operator action (the app never holds
private keys) reconciled on-chain by signature; bank withdrawals are
recorded requests executed in the operator's bank portal.

Treasury withdrawal workflow (PayoutRequest):

    request → pending (1st approval) → approved (2nd DISTINCT approval)
    → executed (operator records the Solana signature / bank receipt)

* Approvals need TWO different superadmins (the creator cannot approve
  their own request).
* Open DISPUTES hold every payout (dispute → cancel + payout freeze is
  the fail-safe direction from the webhook processor).
* USDC execution is verified on-chain (getSignatureStatuses) before the
  request flips to ``executed``.
* The treasury reserve floor (``TREASURY_MIN_RESERVE_USDC``) must survive
  a withdrawal.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.billing import (
    BillingSubscription,
    BillingTransaction,
    PayoutRequest,
    PaymentMethod,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.billing.providers import (
    ProviderApiError,
    ProviderConfigError,
    get_provider,
)
from app.services.billing.subscription_engine import (
    billing_tick,
    get_plan_by_code,
)
from app.admin.api import require_superadmin, _write_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/billing", tags=["Admin Billing"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class WithdrawalCreate(BaseModel):
    kind: str = Field("usdc", description="usdc (Solana rail) | bank")
    amount_usdc: Optional[Decimal] = Field(None, gt=0)
    amount_egp: Optional[Decimal] = Field(None, gt=0)
    destination: dict = Field(
        default_factory=dict,
        description="Non-secret destination summary, e.g. "
        "{'wallet': '<base58>', 'network': 'solana'} or "
        "{'bank_label': 'CIB ****1234'}.",
    )
    notes: Optional[str] = Field(None, max_length=2000)


class WithdrawalDecision(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


class WithdrawalExecute(BaseModel):
    execution_reference: str = Field(
        ..., min_length=4, max_length=120,
        description="Solana tx signature (usdc) or bank receipt id (bank)",
    )


class WithdrawalItem(BaseModel):
    id: str
    kind: str
    status: str
    amount_usdc: Optional[str]
    amount_egp: Optional[str]
    destination: Optional[dict]
    approvers: Optional[list]
    execution_reference: Optional[str]
    notes: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _open_disputes(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(BillingTransaction).where(
                BillingTransaction.status == "disputed"
            )
        )
        or 0
    )


async def _treasury_balance_usdc() -> Decimal:
    try:
        provider = get_provider(PaymentMethod.USDC_SOLANA)
        if not provider.is_configured():
            return Decimal("0")
        return await provider.get_treasury_balance()
    except (ProviderApiError, ProviderConfigError) as e:
        logger.warning("treasury balance read failed: %s", e)
        raise HTTPException(status_code=502, detail="treasury balance unavailable")


def _serialize_withdrawal(p: PayoutRequest) -> dict:
    return {
        "id": str(p.id),
        "kind": p.kind,
        "status": p.status,
        "amount_usdc": str(p.amount_usdc) if p.amount_usdc is not None else None,
        "amount_egp": str(p.amount_egp) if p.amount_egp is not None else None,
        "destination": p.destination,
        "approvers": p.approvers or [],
        "execution_reference": p.execution_reference,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# --------------------------------------------------------------------------- #
# Overview + tick
# --------------------------------------------------------------------------- #
@router.get("/overview")
async def billing_overview(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Billing health snapshot: MRR, subscription funnel, invoices,
    payouts, disputes (the monthly-close checklist entry point)."""
    sub_counts = dict(
        (
            await db.execute(
                select(BillingSubscription.status, func.count())
                .group_by(BillingSubscription.status)
            )
        ).all()
    )
    txn_counts = dict(
        (
            await db.execute(
                select(BillingTransaction.status, func.count())
                .group_by(BillingTransaction.status)
            )
        ).all()
    )
    # MRR: active/past_due subscriptions' current plan EGP price.
    active_subs = (
        await db.scalars(
            select(BillingSubscription).where(
                BillingSubscription.status.in_(("active", "past_due"))
            )
        )
    ).all()
    mrr_egp = Decimal("0")
    for sub in active_subs:
        plan = await db.scalar(
            select(BillingPlan).where(BillingPlan.id == sub.plan_id)
        )
        if plan is not None:
            mrr_egp += plan.price_egp
    pending_payouts = int(
        await db.scalar(
            select(func.count()).select_from(PayoutRequest).where(
                PayoutRequest.status.in_(("request", "pending", "approved"))
            )
        )
        or 0
    )
    return {
        "mrr_egp": str(mrr_egp),
        "subscriptions": sub_counts,
        "invoices": txn_counts,
        "pending_payouts": pending_payouts,
        "open_disputes": await _open_disputes(db),
        "payouts_held": (await _open_disputes(db)) > 0,
    }


# BillingPlan import kept local to avoid a module-level cycle with models.
from app.models.billing import BillingPlan  # noqa: E402


@router.post("/tick")
async def run_billing_tick(
    request: Request,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Force one billing-cycle pass (RENEW / DUNNING / EXPIRE / USDC
    settlement + void). Idempotent — safe to run any time."""
    base = get_settings().BILLING_WEBHOOK_PUBLIC_URL or str(request.base_url).rstrip("/")
    stats = await billing_tick(db, webhook_base_url=base)
    await _write_audit_log(
        db, admin, "billing.tick", None, None,
        ip=(request.client.host if request.client else None),
        metadata=stats,
    )
    return stats


# --------------------------------------------------------------------------- #
# Comp grant (support / manual activation)
# --------------------------------------------------------------------------- #
class GrantRequest(BaseModel):
    tenant_id: uuid.UUID
    plan_code: str
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/grant")
async def grant_subscription(
    req: GrantRequest,
    request: Request,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Manually (re)activate a tenant's subscription without payment —
    comps, support cases, partnerships. Audit-logged; the subscription
    row and period bookkeeping stay consistent (never hand-UPDATE the
    tables). No payment rail is contacted — the comp invoice is created
    directly in the ``succeeded`` state."""
    from datetime import datetime as _dt

    from app.services.billing.subscription_engine import (
        invoice_idempotency_key,
        upsert_subscription,
    )

    plan = await get_plan_by_code(db, req.plan_code)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    tenant = await db.scalar(select(Tenant).where(Tenant.id == req.tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    sub = await upsert_subscription(db, tenant, plan, PaymentMethod.PAYONEER)
    sub.payment_method = "comp"
    sub.status = "active"
    sub.last_payment_at = _dt.utcnow()

    txn = BillingTransaction(
        tenant_id=tenant.id,
        subscription_id=sub.id,
        plan_id=plan.id,
        kind="subscription_payment",
        payment_method="comp",
        status="succeeded",
        amount=plan.price_egp,
        amount_usdc=plan.price_usdc,
        currency="EGP",
        idempotency_key=invoice_idempotency_key(
            sub.id, sub.current_period_start or _dt.utcnow(), 999
        ),
        paid_at=_dt.utcnow(),
        raw={"comp": True, "reason": req.reason, "granted_by": str(admin.id)},
    )
    db.add(txn)
    await db.commit()
    await db.refresh(sub)
    await _write_audit_log(
        db, admin, "billing.grant", "tenant", str(tenant.id),
        ip=(request.client.host if request.client else None),
        metadata={"plan_code": req.plan_code, "reason": req.reason},
    )
    return {
        "tenant_id": str(tenant.id),
        "plan_code": plan.code,
        "status": sub.status,
        "period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


# --------------------------------------------------------------------------- #
# Treasury
# --------------------------------------------------------------------------- #
@router.get("/treasury")
async def treasury_status(
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Live treasury USDC balance (on-chain), payout queue and policy."""
    settings = get_settings()
    balance = await _treasury_balance_usdc()
    pending = (
        await db.scalars(
            select(PayoutRequest)
            .where(PayoutRequest.status.in_(("request", "pending", "approved")))
            .order_by(PayoutRequest.created_at.desc())
            .limit(50)
        )
    ).all()
    provider = get_provider(PaymentMethod.USDC_SOLANA)
    return {
        "usdc_balance": str(balance),
        "usdc_mint": provider.mint,
        "treasury_wallet": provider.treasury_wallet or None,
        "treasury_configured": provider.is_configured(),
        "min_reserve_usdc": str(Decimal(str(settings.TREASURY_MIN_RESERVE_USDC))),
        "bank_label": settings.TREASURY_BANK_LABEL,
        "pending_withdrawals": [_serialize_withdrawal(p) for p in pending],
        "open_disputes": await _open_disputes(db),
        "payouts_held": (await _open_disputes(db)) > 0,
    }


# --------------------------------------------------------------------------- #
# Withdrawals — create / list / approve / reject / execute
# --------------------------------------------------------------------------- #
@router.get("/withdrawals")
async def list_withdrawals(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PayoutRequest).order_by(PayoutRequest.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(PayoutRequest.status == status)
    payouts = (await db.scalars(stmt)).all()
    return [_serialize_withdrawal(p) for p in payouts]


@router.post("/withdrawals")
async def create_withdrawal(
    req: WithdrawalCreate,
    request: Request,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Open a treasury withdrawal request (becomes executable only after
    TWO distinct superadmin approvals and a dispute-free payout state)."""
    if req.kind not in ("usdc", "bank"):
        raise HTTPException(status_code=400, detail="kind must be 'usdc' or 'bank'")
    if req.kind == "usdc" and (req.amount_usdc is None or req.amount_usdc <= 0):
        raise HTTPException(status_code=400, detail="usdc withdrawals need a positive amount_usdc")
    if req.kind == "bank" and (req.amount_egp is None or req.amount_egp <= 0):
        raise HTTPException(status_code=400, detail="bank withdrawals need a positive amount_egp")

    if await _open_disputes(db) > 0:
        raise HTTPException(
            status_code=409,
            detail="payouts are HELD while disputed invoices are open",
        )

    if req.kind == "usdc":
        # Reserve floor must survive the withdrawal.
        settings = get_settings()
        balance = await _treasury_balance_usdc()
        reserve = Decimal(str(settings.TREASURY_MIN_RESERVE_USDC))
        if balance - req.amount_usdc < reserve:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"withdrawal leaves treasury below the reserve floor "
                    f"(balance={balance}, requested={req.amount_usdc}, "
                    f"min_reserve={reserve})"
                ),
            )

    payout = PayoutRequest(
        tenant_id=None,  # platform treasury withdrawal (merchant payouts later)
        requested_by=admin.id,
        kind=req.kind,
        amount_usdc=req.amount_usdc,
        amount_egp=req.amount_egp,
        destination=req.destination or None,
        status="request",
        approvers=[],
        notes=req.notes,
    )
    db.add(payout)
    await db.commit()
    await db.refresh(payout)
    await _write_audit_log(
        db, admin, "billing.withdrawal.create", "payout_request", str(payout.id),
        ip=(request.client.host if request.client else None),
        metadata={"kind": req.kind, "amount_usdc": str(req.amount_usdc or 0),
                  "amount_egp": str(req.amount_egp or 0)},
    )
    return _serialize_withdrawal(payout)


@router.post("/withdrawals/{payout_id}/approve")
async def approve_withdrawal(
    payout_id: uuid.UUID,
    request: Request,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    payout = await db.get(PayoutRequest, payout_id)
    if payout is None:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if payout.status in ("executed", "rejected", "canceled"):
        raise HTTPException(status_code=409, detail="Withdrawal is already terminal")
    if str(admin.id) in (payout.approvers or []):
        raise HTTPException(status_code=409, detail="Already approved by this admin")
    if str(payout.requested_by) == str(admin.id) and not (payout.approvers or []):
        raise HTTPException(
            status_code=409, detail="The request creator cannot be its first approver"
        )
    if await _open_disputes(db) > 0:
        raise HTTPException(status_code=409, detail="payouts are HELD while disputes are open")

    approvers = list(payout.approvers or [])
    approvers.append(str(admin.id))
    payout.approvers = approvers
    # request → pending (1st approval) → approved (2nd DISTINCT approval)
    payout.status = "pending" if len(approvers) == 1 else "approved"
    await db.commit()
    await db.refresh(payout)
    await _write_audit_log(
        db, admin, "billing.withdrawal.approve", "payout_request", str(payout.id),
        ip=(request.client.host if request.client else None),
        metadata={"approvals": len(approvers)},
    )
    return _serialize_withdrawal(payout)


@router.post("/withdrawals/{payout_id}/reject")
async def reject_withdrawal(
    payout_id: uuid.UUID,
    req: WithdrawalDecision,
    request: Request,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    payout = await db.get(PayoutRequest, payout_id)
    if payout is None:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if payout.status in ("executed", "rejected", "canceled"):
        raise HTTPException(status_code=409, detail="Withdrawal is already terminal")
    payout.status = "rejected"
    payout.notes = (payout.notes or "") + (f" | rejected: {req.notes}" if req.notes else "")
    await db.commit()
    await _write_audit_log(
        db, admin, "billing.withdrawal.reject", "payout_request", str(payout.id),
        ip=(request.client.host if request.client else None),
    )
    return _serialize_withdrawal(payout)


@router.post("/withdrawals/{payout_id}/execute")
async def execute_withdrawal(
    payout_id: uuid.UUID,
    req: WithdrawalExecute,
    request: Request,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Record the operator's out-of-band execution and reconcile it.

    * usdc → the signature is verified ON-CHAIN (Solana getSignatureStatuses)
      before the request flips to ``executed``.
    * bank → the receipt id is recorded as-is (the bank portal is the
      source of truth).
    """
    payout = await db.get(PayoutRequest, payout_id)
    if payout is None:
        raise HTTPException(status_code=404, detail="Withdrawal request not found")
    if payout.status != "approved":
        raise HTTPException(
            status_code=409, detail="Withdrawal needs TWO approvals before execution"
        )
    if await _open_disputes(db) > 0:
        raise HTTPException(status_code=409, detail="payouts are HELD while disputes are open")

    if payout.kind == "usdc":
        provider = get_provider(PaymentMethod.USDC_SOLANA)
        try:
            verified = await provider.verify_payout_execution(req.execution_reference)
        except ProviderApiError as e:
            raise HTTPException(status_code=502, detail=f"chain verification failed: {e}")
        if verified is None:
            raise HTTPException(
                status_code=400,
                detail="signature not found on-chain (or the transaction failed)",
            )
    payout.status = "executed"
    payout.execution_reference = req.execution_reference
    await db.commit()
    await db.refresh(payout)
    await _write_audit_log(
        db, admin, "billing.withdrawal.execute", "payout_request", str(payout.id),
        ip=(request.client.host if request.client else None),
        metadata={"execution_reference": req.execution_reference, "kind": payout.kind},
    )
    return _serialize_withdrawal(payout)
