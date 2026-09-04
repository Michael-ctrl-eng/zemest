"""Billing webhooks — Stripe + Payoneer (raw-body verified, idempotent).

Endpoints (configure in each provider's dashboard):

* ``POST /api/payments/webhook/stripe``  — Stripe webhook secret
  (all events; the processor filters). Key events: invoice.paid,
  invoice.payment_failed, customer.subscription.*, charge.dispute.created,
  checkout.session.completed.
* ``POST /api/payments/webhook/payoneer`` — Payoneer partner callback:
  payout status + checkout collection confirmations. The signature is read
  from the ``X-Payoneer-Signature`` header (env-overridable via
  PAYONEER_SIG_HEADER if the program uses a different name).

Response policy (identical to the Paymob webhook):
* signature/config failure → 401 (fail closed, nothing touched)
* malformed body → 400
* verified → processed idempotently → ALWAYS 200 (redelivery must not loop)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.services.billing import WebhookRejected
from app.services.billing.webhook_processor import (
    process_payoneer_event,
    process_stripe_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments/webhook", tags=["Payments"])


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    if not raw:
        return JSONResponse(status_code=400, content={"detail": "empty body"})
    signature = request.headers.get("stripe-signature") or ""
    if not signature:
        logger.warning("Stripe webhook: missing Stripe-Signature header")
        return JSONResponse(status_code=400, content={"detail": "missing signature"})
    try:
        result = await process_stripe_event(db, raw, signature)
    except WebhookRejected as e:
        logger.warning("Stripe webhook rejected: %s", e)
        return JSONResponse(status_code=401, content={"detail": str(e)})
    return JSONResponse(status_code=200, content=result)


@router.post("/payoneer")
async def payoneer_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    if not raw:
        return JSONResponse(status_code=400, content={"detail": "empty body"})
    settings = get_settings()
    header_name = getattr(settings, "PAYONEER_SIG_HEADER", None) or "X-Payoneer-Signature"
    signature = request.headers.get(header_name.lower()) or request.headers.get(
        header_name
    ) or ""
    if not signature:
        logger.warning("Payoneer webhook: missing %s header", header_name)
        return JSONResponse(status_code=400, content={"detail": "missing signature"})
    try:
        result = await process_payoneer_event(db, raw, signature)
    except WebhookRejected as e:
        logger.warning("Payoneer webhook rejected: %s", e)
        return JSONResponse(status_code=401, content={"detail": str(e)})
    return JSONResponse(status_code=200, content=result)
