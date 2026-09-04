"""Billing webhook routes — the ONLY payment state-change endpoints.

New billing architecture: exactly TWO webhook routes exist.

* ``POST /api/payments/webhook/payoneer`` — Payoneer Checkout events
  (HMAC-SHA256/512 over the exact raw bytes, header-delivered).
* ``POST /api/payments/webhook/paymob``    — Paymob billing transactions
  (HMAC-SHA512 field-concatenation, query-param-delivered).

No removed rail has a route or handler anywhere (regression-tested by
``tests/billing/test_no_stripe_skale.py``). USDC-Solana has no webhooks:
its payments settle via the on-chain sweep.

HTTP semantics (so providers never retry forever):

* verified + processed / duplicate / unknown-but-verified → 200
* bad signature / missing secret → 401 (logged, nothing touched)
* malformed body → 400

All money state changes live in
``app/services/billing/webhook_processor.py`` — these routes are pure
transport (read raw body → verify → dispatch → map outcome to status).
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.billing.webhook_processor import (
    DUPLICATE,
    IGNORED,
    MALFORMED,
    PROCESSED,
    REJECTED,
    process_paymob_billing_webhook,
    process_payoneer_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments/webhook", tags=["Billing Webhooks"])


def _status_for(outcome: str) -> int:
    if outcome == REJECTED:
        return 401
    if outcome == MALFORMED:
        return 400
    return 200  # PROCESSED | DUPLICATE | IGNORED


@router.post("/payoneer")
async def payoneer_billing_webhook(
    request: Request, db: AsyncSession = Depends(get_db)
):
    """Payoneer server-to-server callback (billing rail — PRIMARY).

    Verification order is non-negotiable: HMAC over the EXACT raw bytes
    BEFORE any processing. Bad signature → 401, nothing touched.
    """
    raw = await request.body()
    if not raw:
        return JSONResponse(status_code=400, content={"detail": "empty body"})
    result = await process_payoneer_webhook(db, raw, request.headers)
    return JSONResponse(
        status_code=_status_for(result["outcome"]),
        content={
            "status": "ok" if result["outcome"] != REJECTED else "rejected",
            "outcome": result["outcome"],
            "detail": result.get("detail", ""),
        },
    )


@router.post("/paymob")
async def paymob_billing_webhook(
    request: Request,
    hmac_signature: str = Query(default="", alias="hmac"),
    db: AsyncSession = Depends(get_db),
):
    """Paymob billing callback (BACKUP rail).

    Reuses the audited HMAC-SHA512 verification from the existing Paymob
    client — the same fail-closed posture as /api/payments/webhook.
    """
    raw = await request.body()
    if not raw:
        return JSONResponse(status_code=400, content={"detail": "empty body"})
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(status_code=400, content={"detail": "malformed JSON body"})
    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"detail": "body must be a JSON object"})

    # Paymob delivers the hmac as a query param (transaction callbacks) or
    # in the body (subscription callbacks).
    received_hmac = str(hmac_signature or payload.get("hmac") or "")
    result = await process_paymob_billing_webhook(db, payload, received_hmac)
    return JSONResponse(
        status_code=_status_for(result["outcome"]),
        content={
            "status": "ok" if result["outcome"] != REJECTED else "rejected",
            "outcome": result["outcome"],
            "detail": result.get("detail", ""),
        },
    )
