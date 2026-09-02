"""Paymob payment endpoints — webhook (only state-change source) + intention creation.

Architecture (analysis/G1-payments.md):

* COD stays the default payment rail; these endpoints power the
  deposit-to-confirm (عربون) flow and full online payments.
* ``POST /api/payments/webhook`` — HMAC-SHA512 verification happens BEFORE
  any processing; bad signature → 4xx (logged, nothing touched). Valid
  signature → idempotent processing (dedup on webhook ``obj.id`` +
  one-transaction compare-and-set via ``merchant_order_id``), always 200
  fast so Paymob does not retry forever.
* ``POST /api/payments/intention`` — authenticated endpoint that creates a
  Paymob Intention (deposit amount in EGP → piasters ×100) for one of the
  caller's orders and returns the payment/checkout URL.
"""
from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.order import Order
from app.models.tenant import Tenant
from app.services.payments import (
    PaymobApiError,
    PaymobClient,
    PaymobConfigError,
    to_piasters,
    verify_subscription_hmac,
    verify_token_hmac,
    verify_transaction_hmac,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["Payments"])

# Our orders are linked to Paymob via special_reference = "zst-{order.id}";
# Paymob echoes it back on every transaction webhook as
# order.merchant_order_id.
MERCHANT_REF_PREFIX = "zst-"

# payment_status state machine (COD-first, G1 §4). Source states a webhook
# may transition FROM — terminal states (deposit_paid/paid) never regress
# (deposit_paid may only upgrade to paid on a full-amount transaction).
_PENDING_PAYMENT_STATES = ("", "pending", "pending_deposit", "failed")


def _order_reference(order_id) -> str:
    return f"{MERCHANT_REF_PREFIX}{order_id}"


# --------------------------------------------------------------------------- #
# Request / response schemas (kept local — payments has no shared schemas)
# --------------------------------------------------------------------------- #
class PaymentIntentionRequest(BaseModel):
    order_id: uuid.UUID
    # Deposit amount in EGP — converted to integer piasters (×100) before
    # being sent to Paymob (1850.00 → 185000).
    deposit_amount: Decimal = Field(..., gt=0, description="Deposit amount in EGP")
    redirect_url: str | None = Field(
        None, description="Browser redirect after checkout (UX only, never trusted)"
    )
    public_key: str | None = Field(
        None,
        description="Frontend-safe Paymob public key — used to build the "
        "unified-checkout URL when the API response carries no URL",
    )


class PaymentIntentionResponse(BaseModel):
    order_id: str
    intention_id: str | None
    client_secret: str | None
    payment_url: str | None
    amount_piasters: int
    special_reference: str
    payment_status: str


# --------------------------------------------------------------------------- #
# Webhook — the only payment state-change path
# --------------------------------------------------------------------------- #
def _classify_event(payload: dict, obj: dict) -> str:
    """transaction | token | subscription (best effort, fail-closed)."""
    ptype = str(payload.get("type") or "").lower()
    if "transaction" in ptype:
        return "transaction"
    if "token" in ptype:
        return "token"
    if "subscription" in ptype:
        return "subscription"
    # No wrapper "type" — infer from the object shape.
    if "amount_cents" in obj or "order" in obj:
        return "transaction"
    if "masked_pan" in obj and ("card_subtype" in obj or "token" in obj):
        return "token"
    if "trigger_type" in obj:
        return "subscription"
    # Unknown shape: verify against the transaction field order (fails closed).
    return "transaction"


@router.post("/webhook")
async def paymob_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Paymob server-to-server callback.

    Verification order (non-negotiable): HMAC BEFORE any processing.
    * malformed/missing body → 400
    * missing ``hmac`` → 400; secret not configured → 401 (fail closed)
    * bad signature → 401
    * valid signature → idempotent processing, then 200 (always — an
      unknown/duplicate event must not make Paymob retry forever).
    """
    settings = get_settings()

    raw = await request.body()
    if not raw:
        logger.warning("Paymob webhook: empty body")
        return JSONResponse(status_code=400, content={"detail": "empty body"})
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Paymob webhook: malformed JSON body")
        return JSONResponse(status_code=400, content={"detail": "malformed JSON body"})
    if not isinstance(payload, dict):
        logger.warning("Paymob webhook: body is not a JSON object")
        return JSONResponse(status_code=400, content={"detail": "body must be a JSON object"})

    # Transaction callbacks deliver the hmac as a query param; subscription
    # callbacks deliver it in the body.
    received_hmac = str(request.query_params.get("hmac") or payload.get("hmac") or "")
    if not received_hmac:
        logger.warning("Paymob webhook: missing hmac")
        return JSONResponse(status_code=400, content={"detail": "missing hmac"})

    secret = settings.PAYMOB_WEBHOOK_HMAC_SECRET
    if not secret:
        # Fail closed: without the secret we cannot verify anything.
        logger.error("Paymob webhook rejected: PAYMOB_WEBHOOK_HMAC_SECRET not configured")
        return JSONResponse(status_code=401, content={"detail": "webhook secret not configured"})

    # Intention-era payloads wrap the object as {"type": ..., "obj": {...}};
    # legacy transaction callbacks POST the object directly.
    obj = payload.get("obj") if isinstance(payload.get("obj"), dict) else payload
    event_type = _classify_event(payload, obj)

    if event_type == "token":
        valid = verify_token_hmac(obj, received_hmac, secret)
    elif event_type == "subscription":
        valid = verify_subscription_hmac(obj, received_hmac, secret)
    else:
        valid = verify_transaction_hmac(obj, received_hmac, secret)

    if not valid:
        logger.warning(
            "Paymob webhook HMAC verification FAILED (type=%s) — rejected", event_type
        )
        return JSONResponse(status_code=401, content={"detail": "invalid hmac"})

    # ---- signature verified: safe to process ---- #
    if event_type == "transaction":
        await _process_transaction(db, obj)
    else:
        logger.info("Paymob webhook accepted (type=%s) — no state change", event_type)
    return {"status": "ok"}


async def _process_transaction(db: AsyncSession, obj: dict) -> None:
    """Apply ONE compare-and-set transition for a verified transaction.

    Idempotency: dedup on the webhook ``obj.id`` (paymob_transaction_id on
    the order row) — a redelivered transaction can never re-transition.
    Regressions are impossible: the UPDATE's WHERE clause only matches
    non-terminal payment_status values.
    """
    tx_id = str(obj.get("id") or "")
    if not tx_id:
        logger.warning("Paymob webhook: transaction object without id — ignored")
        return

    order_obj = obj.get("order") if isinstance(obj.get("order"), dict) else {}
    ref = str(order_obj.get("merchant_order_id") or "")
    if not ref.startswith(MERCHANT_REF_PREFIX):
        logger.info("Paymob webhook: reference %r not linked to an order — ignored", ref)
        return
    try:
        order_uuid = uuid.UUID(ref[len(MERCHANT_REF_PREFIX):])
    except ValueError:
        logger.warning("Paymob webhook: unparseable order reference %r — ignored", ref)
        return

    if obj.get("pending"):
        logger.info("Paymob transaction %s pending — no state change", tx_id)
        return
    if obj.get("is_refunded") or obj.get("is_voided"):
        # Refunds/voids map onto the manual returns handling (G1 §4) — log only.
        logger.info(
            "Paymob transaction %s is a refund/void — no automatic state change", tx_id
        )
        return

    try:
        amount_cents = int(obj.get("amount_cents") or 0)
    except (TypeError, ValueError):
        amount_cents = 0

    if obj.get("success"):
        # Deposit vs full payment: a transaction covering the whole order
        # total (in piasters) upgrades to "paid"; anything less is a deposit.
        target = "deposit_paid"
        res = await db.execute(select(Order.total).where(Order.id == order_uuid))
        total = res.scalar_one_or_none()
        if total is not None and amount_cents >= to_piasters(total):
            target = "paid"
        sources = list(_PENDING_PAYMENT_STATES)
        if target == "paid":
            sources.append("deposit_paid")  # upgrade only, never a regression
    else:
        target = "failed"
        sources = list(_PENDING_PAYMENT_STATES)

    stmt = (
        update(Order)
        .where(
            Order.id == order_uuid,
            # dedup on obj.id: a redelivered transaction never matches again
            or_(
                Order.paymob_transaction_id.is_(None),
                Order.paymob_transaction_id != tx_id,
            ),
            # compare-and-set: only non-terminal source states match
            or_(
                Order.payment_status.is_(None),
                Order.payment_status.in_(sources),
            ),
        )
        .values(payment_status=target, paymob_transaction_id=tx_id)
    )
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount:
        logger.info(
            "Paymob webhook: order %s payment_status → %s (tx %s, %d piasters)",
            order_uuid, target, tx_id, amount_cents,
        )
    else:
        logger.info(
            "Paymob webhook: no transition for order %s (tx %s) — duplicate, "
            "unknown order, or terminal state",
            order_uuid, tx_id,
        )


# --------------------------------------------------------------------------- #
# Intention creation (authenticated)
# --------------------------------------------------------------------------- #
@router.post("/intention", response_model=PaymentIntentionResponse)
async def create_payment_intention(
    req: PaymentIntentionRequest,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Paymob Intention for a deposit on one of the caller's orders.

    Guards: the order must belong to a tenant owned by the authenticated
    user (404 otherwise — no information leak); the deposit cannot exceed
    the order total. Returns the payment/checkout URL Paymob (or the
    public key + client_secret) points the buyer at.
    """
    res = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .join(Tenant, Order.tenant_id == Tenant.id)
        .where(Order.id == req.order_id, Tenant.owner_id == user.id)
    )
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if req.deposit_amount > order.total:
        raise HTTPException(
            status_code=400, detail="deposit amount cannot exceed the order total"
        )

    # Public webhook URL Paymob calls back (state changes happen only there).
    # request.base_url respects the Host header; behind a proxy/BFF set the
    # public backend origin on the proxy (X-Forwarded-Host etc.) or override
    # notification_url at the client level.
    notification_url = f"{str(request.base_url).rstrip('/')}/api/payments/webhook"

    name_parts = (order.customer_name or "Customer").split(" ", 1)
    billing_data = {
        "first_name": name_parts[0] or "Customer",
        "last_name": name_parts[1] if len(name_parts) > 1 else "",
        "phone_number": order.customer_phone or "",
        "email": "",
        "city": order.city or "",
        "state": order.governorate or "",
        "country": "EG",
    }
    items = [
        {
            "name": (item.product_name or "item")[:100],
            "amount": to_piasters(item.unit_price),
            "quantity": item.quantity,
            "description": f"order {order.order_number}",
        }
        for item in order.items
    ]

    client = PaymobClient()
    try:
        intention = await client.create_intention(
            amount_egp=req.deposit_amount,
            billing_data=billing_data,
            merchant_order_id=_order_reference(order.id),
            payment_methods=None,  # → settings PAYMOB_INTEGRATION_IDS
            items=items or None,
            notification_url=notification_url,
            redirection_url=req.redirect_url or "",
            public_key=req.public_key or "",
        )
    except PaymobConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymobApiError as e:
        logger.error("Paymob intention creation failed: %s (status=%s)", e, e.status_code)
        raise HTTPException(status_code=502, detail="payment gateway error")

    # Persist the deposit intent so the webhook has context to land on.
    order.payment_status = "pending_deposit"
    order.deposit_amount = req.deposit_amount
    if intention.get("intention_id"):
        order.paymob_intention_id = intention["intention_id"]
    await db.commit()

    return PaymentIntentionResponse(
        order_id=str(order.id),
        intention_id=intention.get("intention_id") or None,
        client_secret=intention.get("client_secret") or None,
        payment_url=intention.get("payment_url") or None,
        amount_piasters=to_piasters(req.deposit_amount),
        special_reference=_order_reference(order.id),
        payment_status=order.payment_status,
    )
