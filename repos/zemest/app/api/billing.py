"""Billing & subscription API — merchant-facing money endpoints.

* ``GET  /api/billing/overview``     — plan, subscription, invoices, balance,
                                        payout accounts + requests (one call)
* ``POST /api/billing/subscribe``    — create subscription + first invoice +
                                        rail-specific checkout handoff
* ``POST /api/billing/cancel``       — cancel (default at period end)
* ``POST /api/billing/reactivate``   — undo a scheduled cancel
* ``GET  /api/billing/invoices``     — invoice history w/ line items
* ``GET  /api/billing/methods``      — saved payment methods (display fields)
* ``DELETE /api/billing/methods/{id}`` — detach a saved method
* ``GET/POST/DELETE /api/billing/payout-accounts`` — payout destinations
* ``POST /api/billing/payouts``      — request a payout (fraud-gated)

Webhooks live in app/api/billing_webhooks.py (raw-body verified).
Every state change flows through the engine's compare-and-set updates —
the browser is never trusted for money state.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.billing import Invoice, PaymentMethod, PayoutAccount, PayoutRequest, Subscription
from app.models.user import User
from app.services.billing import (
    PayoutError,
    cancel_subscription,
    create_payout_request,
    create_subscription_and_invoice,
    fraud,
    get_active_subscription,
    reactivate_subscription,
)
from app.services.billing.payouts import compute_fee
from app.services.billing.subscription_engine import available_balance
from app.services.billing.providers import skale as skale_provider
from app.services.plan_service import PLANS, plan_catalog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["Billing"])

VALID_PLANS = ("growth", "pro")
VALID_PROVIDERS = ("stripe", "paymob", "payoneer")


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class SubscribeRequest(BaseModel):
    plan: str = Field(..., description="growth | pro")
    provider: str = Field("stripe", description="stripe | paymob | payoneer")
    # Browser UX redirect after checkout (never trusted for state)
    success_path: str | None = Field(None, description="/dashboard/... path")

    @field_validator("plan")
    @classmethod
    def _valid_plan(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_PLANS:
            raise ValueError(f"plan must be one of {VALID_PLANS}")
        return v

    @field_validator("provider")
    @classmethod
    def _valid_provider(cls, v: str) -> str:
        v = v.strip().lower() if v else "stripe"
        if v not in VALID_PROVIDERS:
            raise ValueError(f"provider must be one of {VALID_PROVIDERS}")
        return v


class CancelRequest(BaseModel):
    immediate: bool = False
    reason: str | None = Field(None, max_length=200)


class PayoutAccountRequest(BaseModel):
    method: str = Field(..., description="payoneer | skale | bank_egypt")
    details: str = Field(..., max_length=2000)
    label: str | None = Field(None, max_length=80)
    currency: str = Field("USD", max_length=8)

    @field_validator("method")
    @classmethod
    def _valid_method(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("payoneer", "skale", "bank_egypt"):
            raise ValueError("method must be payoneer | skale | bank_egypt")
        return v

    @field_validator("details")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("details are required")
        return v.strip()


class PayoutRequestBody(BaseModel):
    payout_account_id: uuid.UUID
    amount: int = Field(..., gt=0, description="smallest unit (cents USD)")


# --------------------------------------------------------------------------- #
# Overview — one call powers the whole billing page
# --------------------------------------------------------------------------- #
@router.get("/overview")
async def billing_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    sub = await get_active_subscription(db, user.id)
    if sub is None:
        res = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        sub = res.scalar_one_or_none()

    invoices_res = await db.execute(
        select(Invoice)
        .where(Invoice.user_id == user.id)
        .order_by(Invoice.created_at.desc())
        .limit(50)
    )
    invoices = invoices_res.scalars().all()

    methods_res = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.user_id == user.id, PaymentMethod.is_attached == True)  # noqa: E712
        .order_by(PaymentMethod.created_at.desc())
    )
    methods = methods_res.scalars().all()

    accounts_res = await db.execute(
        select(PayoutAccount)
        .where(PayoutAccount.user_id == user.id)
        .order_by(PayoutAccount.created_at.desc())
    )
    accounts = accounts_res.scalars().all()

    payouts_res = await db.execute(
        select(PayoutRequest)
        .where(PayoutRequest.user_id == user.id)
        .order_by(PayoutRequest.requested_at.desc())
        .limit(20)
    )
    payouts = payouts_res.scalars().all()

    open_invoices = [i for i in invoices if i.status in ("draft", "open")]

    return {
        "plan": {
            "key": (sub.plan if sub else "free"),
            "name": PLANS.get(sub.plan if sub else "free", PLANS["free"]).name,
            "user_plan": user.plan,
        },
        "subscription": _subscription_payload(sub),
        "open_invoice": _invoice_payload(open_invoices[0]) if open_invoices else None,
        "invoices": [_invoice_payload(i) for i in invoices[:24]],
        "payment_methods": [
            {
                "id": str(m.id),
                "provider": m.provider,
                "kind": m.kind,
                "brand": m.brand,
                "last4": m.last4,
                "is_default": m.is_default,
            }
            for m in methods
        ],
        "payouts": {
            "available_balance": await available_balance(db, user.id),
            "currency": s.PAYOUT_CURRENCY,
            "min_amount": s.PAYOUT_MIN_AMOUNT,
            "platform_fee_pct": s.PLATFORM_FEE_PCT,
            "accounts": [
                {
                    "id": str(a.id),
                    "method": a.method,
                    "label": a.label,
                    "status": a.status,
                    "is_default": a.is_default,
                    "currency": a.currency,
                    # Wallet addresses are public on-chain; payoneer ids are
                    # masked for display. bank details are NEVER returned.
                    "masked": _mask_details(a),
                }
                for a in accounts
            ],
            "requests": [
                {
                    "id": str(p.id),
                    "rail": p.rail,
                    "amount": p.amount,
                    "fee_amount": p.fee_amount,
                    "net_amount": p.net_amount,
                    "currency": p.currency,
                    "status": p.status,
                    "tx_hash": p.tx_hash,
                    "requested_at": p.requested_at.isoformat() if p.requested_at else None,
                    "processed_at": p.processed_at.isoformat() if p.processed_at else None,
                    "failure_reason": p.failure_reason,
                }
                for p in payouts
            ],
        },
        "rails": {
            "stripe_enabled": bool(s.STRIPE_SECRET_KEY and s.STRIPE_WEBHOOK_SECRET),
            "payoneer_checkout": bool(s.PAYONEER_CLIENT_ID and s.PAYONEER_CLIENT_SECRET),
            "paymob_enabled": bool(s.PAYMOB_API_KEY),
            "skale_payouts": bool(s.SKALE_PAYOUT_HMAC_SECRET),
            "payout_fee_preview": {
                "amount_100usd_fee": compute_fee(10000),
            },
        },
    }


def _subscription_payload(sub: Subscription | None) -> dict | None:
    if sub is None:
        return None
    return {
        "id": str(sub.id),
        "plan": sub.plan,
        "status": sub.status,
        "provider": sub.provider,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "canceled_at": sub.canceled_at.isoformat() if sub.canceled_at else None,
        "failed_attempts": sub.failed_attempts,
    }


def _invoice_payload(inv: Invoice) -> dict:
    return {
        "id": str(inv.id),
        "number": inv.number,
        "plan": inv.plan,
        "amount": inv.amount,
        "currency": inv.currency,
        "status": inv.status,
        "period_start": inv.period_start.isoformat() if inv.period_start else None,
        "period_end": inv.period_end.isoformat() if inv.period_end else None,
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "payment_url": inv.payment_url,
        "line_items": (inv.line_items or {}).get("items", []),
        "attempt_count": inv.attempt_count,
        "next_attempt_at": inv.next_attempt_at.isoformat() if inv.next_attempt_at else None,
    }


def _mask_details(account: PayoutAccount) -> str:
    d = account.details or ""
    if account.method == "skale":
        return f"{d[:6]}…{d[-4:]}" if len(d) >= 12 else "invalid"
    if account.method == "payoneer":
        return f"…{d[-4:]}" if len(d) >= 4 else "invalid"
    return "on file (encrypted)"  # bank_egypt — never echoed


# --------------------------------------------------------------------------- #
# Subscribe — create contract + checkout handoff
# --------------------------------------------------------------------------- #
@router.post("/subscribe")
async def subscribe(
    req: SubscribeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    base = s.PUBLIC_BASE_URL or str(request.base_url).rstrip("/")

    sub, invoice = await create_subscription_and_invoice(db, user, req.plan, req.provider)

    handoff: dict = {}

    if req.provider == "stripe":
        if not (s.STRIPE_SECRET_KEY and s.STRIPE_WEBHOOK_SECRET):
            raise HTTPException(400, "Stripe rail is not configured on this deployment")
        price_id = {"growth": s.STRIPE_PRICE_GROWTH, "pro": s.STRIPE_PRICE_PRO}[req.plan]
        if not price_id:
            raise HTTPException(400, f"Stripe price for plan {req.plan!r} is not configured")
        from app.services.billing.providers.stripe_provider import StripeClient, StripeError

        client = StripeClient()
        try:
            customer_id = await client.ensure_customer(str(user.id), user.email or "", user.name)
            sub.provider_customer_id = customer_id
            await db.commit()
            success_path = req.success_path or "/dashboard"
            session = await client.create_checkout_subscription(
                customer_id=customer_id,
                price_id=price_id,
                success_url=f"{base}{success_path}?billing=success&invoice={invoice.number}",
                cancel_url=f"{base}{success_path}?billing=canceled",
                client_reference_id=str(user.id),
            )
            invoice.payment_url = session["url"]
            await db.commit()
            handoff = {"type": "redirect", "url": session["url"]}
        except StripeError as e:
            logger.error("Stripe checkout failed: %s", e)
            raise HTTPException(502, "payment gateway error")

    elif req.provider == "paymob":
        if not s.PAYMOB_API_KEY:
            raise HTTPException(400, "Paymob rail is not configured on this deployment")
        from app.services.payments import PaymobApiError, PaymobClient, PaymobConfigError

        client = PaymobClient()
        try:
            intention = await client.create_intention(
                amount_egp=PLANS[req.plan].price_egp_month,
                billing_data={
                    "first_name": (user.name or "Merchant").split(" ")[0],
                    "last_name": "",
                    "email": user.email or "",
                    "phone_number": "",
                    "city": "", "state": "", "country": "EG",
                },
                merchant_order_id=f"sub-{invoice.number}",
                notification_url=f"{base}/api/payments/webhook",
                redirection_url=f"{base}/dashboard?billing=return",
            )
            invoice.payment_url = intention.get("payment_url") or ""
            invoice.client_secret = intention.get("client_secret") or ""
            await db.commit()
            handoff = {"type": "redirect", "url": intention.get("payment_url")}
        except (PaymobConfigError, PaymobApiError) as e:
            logger.error("Paymob subscription intention failed: %s", e)
            raise HTTPException(502, "payment gateway error")

    elif req.provider == "payoneer":
        if not (s.PAYONEER_CLIENT_ID and s.PAYONEER_CLIENT_SECRET):
            raise HTTPException(400, "Payoneer rail is not configured on this deployment")
        # Payoneer checkout: the partner-hosted payment page; our invoice
        # number is the client_reference the callback correlates on.
        handoff = {
            "type": "payoneer",
            "invoice_number": invoice.number,
            "amount": invoice.amount,
            "currency": invoice.currency,
            "note": "complete the Payoneer checkout; activation happens via the verified callback",
        }

    return {
        "subscription_id": str(sub.id),
        "invoice_number": invoice.number,
        "invoice_amount": invoice.amount,
        "invoice_currency": invoice.currency,
        "checkout": handoff,
    }


# --------------------------------------------------------------------------- #
# Cancel / reactivate
# --------------------------------------------------------------------------- #
@router.post("/cancel")
async def cancel(
    req: CancelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await get_active_subscription(db, user.id)
    if sub is None:
        raise HTTPException(404, "no active subscription")
    if sub.provider == "stripe" and sub.provider_subscription_id:
        from app.services.billing.providers.stripe_provider import StripeClient, StripeError

        try:
            await StripeClient().cancel_subscription(
                sub.provider_subscription_id, at_period_end=not req.immediate
            )
        except StripeError as e:
            logger.error("Stripe cancel failed: %s", e)
            raise HTTPException(502, "payment gateway error")

    sub = await cancel_subscription(
        db, sub, immediate=req.immediate, by="user", reason=req.reason
    )
    return {"status": "ok", "subscription": _subscription_payload(sub)}


@router.post("/reactivate")
async def reactivate(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = res.scalar_one_or_none()
    if sub is None:
        raise HTTPException(404, "no subscription")
    if sub.status == "canceled":
        raise HTTPException(409, "subscription already canceled — subscribe again")
    if sub.provider == "stripe" and sub.provider_subscription_id:
        from app.services.billing.providers.stripe_provider import StripeClient, StripeError

        try:
            await StripeClient().reactivate_subscription(sub.provider_subscription_id)
        except StripeError as e:
            logger.error("Stripe reactivate failed: %s", e)
            raise HTTPException(502, "payment gateway error")
    try:
        sub = await reactivate_subscription(db, sub)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"status": "ok", "subscription": _subscription_payload(sub)}


# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #
@router.get("/invoices")
async def invoices(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Invoice)
        .where(Invoice.user_id == user.id)
        .order_by(Invoice.created_at.desc())
        .limit(100)
    )
    return {"invoices": [_invoice_payload(i) for i in res.scalars().all()]}


# --------------------------------------------------------------------------- #
# Payment methods (display + detach)
# --------------------------------------------------------------------------- #
@router.get("/methods")
async def payment_methods(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(PaymentMethod)
        .where(PaymentMethod.user_id == user.id)
        .order_by(PaymentMethod.created_at.desc())
    )
    return {
        "methods": [
            {
                "id": str(m.id),
                "provider": m.provider,
                "kind": m.kind,
                "brand": m.brand,
                "last4": m.last4,
                "exp_month": m.exp_month,
                "exp_year": m.exp_year,
                "is_default": m.is_default,
                "is_attached": m.is_attached,
            }
            for m in res.scalars().all()
        ]
    }


@router.delete("/methods/{method_id}")
async def detach_method(
    method_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.id == method_id, PaymentMethod.user_id == user.id
        )
    )
    method = res.scalar_one_or_none()
    if method is None:
        raise HTTPException(404, "payment method not found")
    # Rail-side detach (Stripe) + local detach — failures are logged, the
    # local row is detached anyway (fail-safe: a dead card can never charge).
    if method.provider == "stripe" and method.provider_pm_id.startswith("pm_"):
        try:
            from app.services.billing.providers.stripe_provider import StripeClient

            await StripeClient()._request(
                "POST", f"/v1/payment_methods/{method.provider_pm_id}/detach"
            )
        except Exception:  # noqa: BLE001
            logger.warning("Stripe pm detach failed for %s", method.provider_pm_id)
    method.is_attached = False
    method.is_default = False
    await db.commit()
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Payout accounts
# --------------------------------------------------------------------------- #
@router.post("/payout-accounts")
async def add_payout_account(
    req: PayoutAccountRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.method == "skale" and not skale_provider.valid_eth_address(req.details):
        raise HTTPException(400, "invalid SKALE wallet address (expected 0x… 42 chars)")

    # Replace-as-default semantics: one default per method
    res = await db.execute(
        select(PayoutAccount).where(
            PayoutAccount.user_id == user.id, PayoutAccount.method == req.method
        )
    )
    for existing in res.scalars().all():
        existing.is_default = False

    account = PayoutAccount(
        user_id=user.id,
        method=req.method,
        # details land encrypted at rest (EncryptedText column); reads
        # decrypt transparently for the payout rails only.
        details=req.details,
        label=req.label,
        currency=req.currency[:8].upper(),
        # Wallets are verifiable instantly (address shape) → verified;
        # Payoneer payees + bank accounts wait for the first successful
        # payout / admin verification → pending.
        status="verified" if req.method == "skale" else "pending",
        is_default=True,
    )
    db.add(account)
    await db.commit()
    return {
        "id": str(account.id),
        "method": account.method,
        "status": account.status,
        "masked": _mask_details(account),
    }


@router.delete("/payout-accounts/{account_id}")
async def remove_payout_account(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(PayoutAccount).where(
            PayoutAccount.id == account_id, PayoutAccount.user_id == user.id
        )
    )
    account = res.scalar_one_or_none()
    if account is None:
        raise HTTPException(404, "payout account not found")
    await db.execute(
        delete(PayoutAccount).where(PayoutAccount.id == account_id)
    )
    await db.commit()
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Payout requests
# --------------------------------------------------------------------------- #
@router.post("/payouts")
async def request_payout(
    req: PayoutRequestBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        request = await create_payout_request(
            db, user.id, payout_account_id=req.payout_account_id, amount=req.amount
        )
    except PayoutError as e:
        raise HTTPException(400, str(e))
    return {
        "id": str(request.id),
        "status": request.status,
        "amount": request.amount,
        "fee_amount": request.fee_amount,
        "net_amount": request.net_amount,
        "rail": request.rail,
        "tx_hash": request.tx_hash,
    }
