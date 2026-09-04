"""Unified webhook processor — verify → dedupe → dispatch → compare-and-set.

New billing architecture: exactly TWO webhook sources exist
(payoneer, paymob). USDC-Solana has NO webhooks — it is settled by the
on-chain sweep in ``subscription_engine.settle_usdc_invoices``. There is no handler for any removed rail.

Security posture (the audit's hardening requirements):

* **Signature BEFORE any processing** — Payoneer: HMAC-SHA256/512 over
  the exact raw bytes (header-delivered); Paymob: HMAC-SHA512 over the
  documented field concatenation (query-param-delivered). Both fail
  closed: missing secret / empty signature → rejected, nothing touched.
* **Ledger dedupe** — every verified event is recorded ONCE in
  ``billing_webhook_events`` (unique provider+event_id); redelivery is
  a no-op.
* **Amount validation** — a payment event only activates an invoice when
  its verified amount covers the invoice. Underpayment never activates.
* **Terminal states never regress** — all state changes are
  compare-and-set UPDATEs inside the subscription engine.
* **Disputes** — a dispute event cancels the subscription immediately and
  flags the invoice ``disputed`` (fail-safe direction: lock first).

The API layer (``app/api/billing_webhooks.py``) maps processor outcomes
to HTTP codes: verified-but-unknown events still 200 (providers must not
retry forever); bad signature 401; malformed body 400.
"""
from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.billing import BillingTransaction, BillingWebhookEvent, PayoutRequest
from app.services.billing.providers.payoneer import (
    extract_signature,
    parse_amount,
    verify_webhook_signature,
)
from app.services.billing.subscription_engine import (
    cancel_subscription,
    mark_invoice_failed,
    mark_invoice_paid,
)

logger = logging.getLogger(__name__)

# Payoneer payout statuses → PayoutRequest.status transitions.
_PAYONEER_PAYOUT_STATUS_MAP = {
    "PAID": "executed",
    "COMPLETED": "executed",
    "FAILED": "rejected",
    "CANCELLED": "canceled",
    "PROCESSING": "pending",
    "PENDING": "pending",
}

# Outcome vocabulary returned to the API layer.
REJECTED = "rejected"        # bad signature / missing secret → 401
MALFORMED = "malformed"      # unparseable body → 400
DUPLICATE = "duplicate"      # verified redelivery → 200, no-op
PROCESSED = "processed"      # verified + state changed → 200
IGNORED = "ignored"          # verified but nothing to do → 200


# --------------------------------------------------------------------------- #
# Ledger dedupe
# --------------------------------------------------------------------------- #
async def _record_event(
    db: AsyncSession, provider: str, event_id: str, event_type: str, payload: dict
) -> bool:
    """Insert the event row; False when it already exists (redelivery)."""
    db.add(
        BillingWebhookEvent(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
        )
    )
    try:
        await db.flush()
        return True
    except IntegrityError:
        await db.rollback()
        return False


async def _mark_processed(db: AsyncSession, provider: str, event_id: str) -> None:
    from datetime import datetime
    from sqlalchemy import update

    await db.execute(
        update(BillingWebhookEvent)
        .where(
            BillingWebhookEvent.provider == provider,
            BillingWebhookEvent.event_id == event_id,
        )
        .values(processed=True, processed_at=datetime.utcnow())
    )
    await db.commit()


# --------------------------------------------------------------------------- #
# Payoneer
# --------------------------------------------------------------------------- #
def _payoneer_event_identity(payload: dict) -> tuple[str, str]:
    """(event_id, event_type) — tolerates the portal's naming variants."""
    event_id = str(
        payload.get("callback_id")
        or payload.get("event_id")
        or payload.get("id")
        or ""
    )
    event_type = str(
        payload.get("type") or payload.get("event") or ""
    ).lower()
    return event_id, event_type


async def process_payoneer_webhook(
    db: AsyncSession, raw_body: bytes, headers: Any
) -> dict:
    """Entry point for POST /api/payments/webhook/payoneer.

    Returns ``{"outcome": ..., "detail": ...}`` — the API layer owns HTTP
    status mapping, this function owns ALL payment state.
    """
    settings = get_settings()
    secret = settings.PAYONEER_WEBHOOK_SECRET
    if not secret:
        logger.error("Payoneer webhook rejected: PAYONEER_WEBHOOK_SECRET not configured")
        return {"outcome": REJECTED, "detail": "webhook secret not configured"}

    signature = extract_signature(headers)
    if not signature:
        logger.warning("Payoneer webhook rejected: missing signature header")
        return {"outcome": REJECTED, "detail": "missing signature"}

    if not verify_webhook_signature(
        raw_body, signature, secret, settings.PAYONEER_WEBHOOK_ALGO
    ):
        logger.warning("Payoneer webhook HMAC verification FAILED — rejected")
        return {"outcome": REJECTED, "detail": "invalid signature"}

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"outcome": MALFORMED, "detail": "malformed JSON body"}
    if not isinstance(payload, dict):
        return {"outcome": MALFORMED, "detail": "body must be a JSON object"}

    event_id, event_type = _payoneer_event_identity(payload)
    if not event_id:
        return {"outcome": MALFORMED, "detail": "event id missing"}

    if not await _record_event(db, "payoneer", event_id, event_type, payload):
        return {"outcome": DUPLICATE, "detail": event_id}

    outcome = await _dispatch_payoneer(db, payload, event_type)
    await _mark_processed(db, "payoneer", event_id)
    return {"outcome": outcome, "detail": event_id, "event_type": event_type}


async def _dispatch_payoneer(
    db: AsyncSession, payload: dict, event_type: str
) -> str:
    """Route one verified Payoneer event to its state change.

    Event families (field names per the portal's payload vocabulary):
    * payment.succeeded / payment.failed — checkout collection callbacks;
      correlate on ``client_reference_id`` = our invoice UUID.
    * payment.refunded / charge.disputed — money moved back / contested.
    * payout.status — treasury withdrawal reconciliation; correlate on
      ``client_reference_id`` = PayoutRequest UUID (or ``payout_id``).
    Unknown events are noted and ignored (no retry loop for providers).
    """
    etype = event_type or ""
    reference = str(
        payload.get("client_reference_id")
        or payload.get("client_reference")
        or ""
    )

    if "dispute" in etype:
        return await _handle_dispute(db, reference, payload)
    if "refund" in etype:
        return await _handle_refund(db, reference, payload)
    if "payout" in etype:
        return await _handle_payout_status(db, payload)
    if "succeed" in etype or "paid" in etype or "complete" in etype:
        return await _handle_payment_succeeded(db, reference, payload)
    if "fail" in etype or "cancel" in etype:
        return await _handle_payment_failed(db, reference, payload)
    logger.info("Payoneer event %r noted — no state change", etype)
    return IGNORED


async def _locate_invoice(
    db: AsyncSession, reference: str
) -> BillingTransaction | None:
    if not reference:
        return None
    try:
        tx_uuid = uuid.UUID(reference)
    except (ValueError, TypeError, AttributeError):
        return None
    return await db.scalar(
        select(BillingTransaction).where(BillingTransaction.id == tx_uuid)
    )


async def _handle_payment_succeeded(
    db: AsyncSession, reference: str, payload: dict
) -> str:
    invoice = await _locate_invoice(db, reference)
    if invoice is None:
        logger.info("Payoneer payment event without matching invoice (ref=%s)", reference)
        return IGNORED

    # ---- AMOUNT VALIDATION (hardened): the verified amount must cover ---
    # the invoice. Underpayment never activates (fail-safe direction).
    amount_minor = parse_amount(
        payload.get("amount")
        if payload.get("amount") is not None
        else payload.get("total")
    )
    expected_minor = int(
        (invoice.amount * Decimal(100)).to_integral_value()
    )
    if amount_minor is not None and amount_minor < expected_minor:
        logger.warning(
            "Payoneer payment amount MISMATCH: got %s minor units, invoice %s needs "
            "%s — NOT activating (invoice %s)",
            amount_minor, invoice.id, expected_minor, expected_minor,
        )
        await mark_invoice_failed(
            db, invoice, f"amount mismatch: {amount_minor} < {expected_minor}"
        )
        return PROCESSED

    provider_ref = str(payload.get("payment_id") or payload.get("session_id") or "")
    paid = await mark_invoice_paid(db, invoice, provider_ref, payload)
    return PROCESSED if paid else IGNORED


async def _handle_payment_failed(
    db: AsyncSession, reference: str, payload: dict
) -> str:
    invoice = await _locate_invoice(db, reference)
    if invoice is None:
        return IGNORED
    reason = str(payload.get("reason") or payload.get("error") or "payment failed")[:255]
    changed = await mark_invoice_failed(db, invoice, reason)
    return PROCESSED if changed else IGNORED


async def _handle_refund(db: AsyncSession, reference: str, payload: dict) -> str:
    invoice = await _locate_invoice(db, reference)
    if invoice is None:
        return IGNORED
    from datetime import datetime
    from sqlalchemy import update as sa_update

    result = await db.execute(
        sa_update(BillingTransaction)
        .where(
            BillingTransaction.id == invoice.id,
            BillingTransaction.status == "succeeded",
        )
        .values(status="refunded", failed_reason="refunded by provider")
    )
    if result.rowcount:
        # Refund = intent to end access: cancel the subscription.
        from app.models.billing import BillingSubscription

        sub = await db.scalar(
            select(BillingSubscription).where(
                BillingSubscription.id == invoice.subscription_id
            )
        )
        if sub is not None and sub.status in ("active", "past_due", "trialing"):
            await cancel_subscription(db, sub, immediate=True)
        await db.commit()
        return PROCESSED
    return IGNORED


async def _handle_dispute(db: AsyncSession, reference: str, payload: dict) -> str:
    """Dispute → immediate cancel + invoice flagged disputed.

    Fail-safe direction: payouts are held downstream (PayoutRequest
    approvals refuse while open disputes exist — admin billing route).
    """
    invoice = await _locate_invoice(db, reference)
    if invoice is None:
        return IGNORED
    from datetime import datetime
    from sqlalchemy import update as sa_update

    await db.execute(
        sa_update(BillingTransaction)
        .where(BillingTransaction.id == invoice.id)
        .values(status="disputed", failed_reason="chargeback / dispute")
    )
    from app.models.billing import BillingSubscription

    sub = await db.scalar(
        select(BillingSubscription).where(
            BillingSubscription.id == invoice.subscription_id
        )
    )
    if sub is not None and sub.status in ("active", "past_due", "trialing"):
        await cancel_subscription(db, sub, immediate=True)
    await db.commit()
    logger.warning(
        "Payoneer DISPUTE on invoice %s — subscription canceled, payouts held",
        invoice.id,
    )
    return PROCESSED


async def _handle_payout_status(db: AsyncSession, payload: dict) -> str:
    """Payout status callbacks (treasury withdrawal reconciliation)."""
    payout_id = str(payload.get("payout_id") or payload.get("id") or "")
    reference = str(payload.get("client_reference_id") or "")
    status = str(payload.get("status") or "").upper()

    request: PayoutRequest | None = None
    if reference:
        try:
            request = await db.scalar(
                select(PayoutRequest).where(PayoutRequest.id == uuid.UUID(reference))
            )
        except (ValueError, TypeError):
            request = None
    if request is None and payout_id:
        request = await db.scalar(
            select(PayoutRequest).where(
                PayoutRequest.execution_reference == payout_id
            )
        )
    if request is None:
        logger.info("Payoneer payout event without matching request (payout_id=%s)", payout_id)
        return IGNORED

    target = _PAYONEER_PAYOUT_STATUS_MAP.get(status)
    if target is None:
        logger.info("Payoneer payout status %r noted — no state change", status)
        return IGNORED
    if request.status in ("executed", "rejected", "canceled"):
        return IGNORED  # terminal — never regress
    from datetime import datetime

    request.status = target
    if target == "executed":
        request.execution_reference = payout_id
    await db.commit()
    return PROCESSED


# --------------------------------------------------------------------------- #
# Paymob (billing rail — the backup)
# --------------------------------------------------------------------------- #
async def process_paymob_billing_webhook(
    db: AsyncSession, payload: dict, received_hmac: str
) -> dict:
    """Entry point for POST /api/payments/webhook/paymob (billing rail).

    Reuses the audited HMAC-SHA512 verification from
    ``app.services.payments.paymob`` — never a second verification path.
    Correlates on ``order.merchant_order_id`` = ``zbl-{invoice UUID}``.
    """
    from app.services.payments.paymob import verify_transaction_hmac

    settings = get_settings()
    secret = settings.PAYMOB_WEBHOOK_HMAC_SECRET
    if not secret:
        logger.error("Paymob billing webhook rejected: PAYMOB_WEBHOOK_HMAC_SECRET not configured")
        return {"outcome": REJECTED, "detail": "webhook secret not configured"}
    if not received_hmac:
        return {"outcome": REJECTED, "detail": "missing hmac"}

    obj = payload.get("obj") if isinstance(payload.get("obj"), dict) else payload
    if not isinstance(obj, dict):
        return {"outcome": MALFORMED, "detail": "body must be a JSON object"}

    if not verify_transaction_hmac(obj, received_hmac, secret):
        logger.warning("Paymob billing webhook HMAC verification FAILED — rejected")
        return {"outcome": REJECTED, "detail": "invalid hmac"}

    tx_id = str(obj.get("id") or "")
    if not tx_id:
        return {"outcome": MALFORMED, "detail": "transaction id missing"}

    if not await _record_event(db, "paymob", f"tx-{tx_id}", "transaction", payload):
        return {"outcome": DUPLICATE, "detail": tx_id}

    outcome = await _dispatch_paymob(db, obj)
    await _mark_processed(db, "paymob", f"tx-{tx_id}")
    return {"outcome": outcome, "detail": tx_id}


async def _dispatch_paymob(db: AsyncSession, obj: dict) -> str:
    from app.services.billing.providers.paymob import parse_billing_reference
    from app.services.payments.paymob import to_piasters

    order_obj = obj.get("order") if isinstance(obj.get("order"), dict) else {}
    ref = str(order_obj.get("merchant_order_id") or "")
    tx_uuid_str = parse_billing_reference(ref)
    if not tx_uuid_str:
        logger.info("Paymob billing webhook: reference %r is not a billing invoice — ignored", ref)
        return IGNORED
    try:
        tx_uuid = uuid.UUID(tx_uuid_str)
    except (ValueError, TypeError):
        return IGNORED
    invoice = await db.scalar(
        select(BillingTransaction).where(BillingTransaction.id == tx_uuid)
    )
    if invoice is None:
        return IGNORED
    if obj.get("pending"):
        return IGNORED
    if obj.get("is_refunded") or obj.get("is_voided"):
        return IGNORED  # refunds/voids handled via the admin flows

    if not obj.get("success"):
        reason = "paymob transaction failed"
        changed = await mark_invoice_failed(db, invoice, reason)
        return PROCESSED if changed else IGNORED

    # ---- AMOUNT + CURRENCY validation (audit D5) -------------------------
    try:
        amount_cents = int(obj.get("amount_cents") or 0)
    except (TypeError, ValueError):
        amount_cents = 0
    currency = str(obj.get("currency") or "EGP").upper()
    expected_cents = to_piasters(invoice.amount)
    if currency != (invoice.currency or "EGP").upper():
        logger.warning(
            "Paymob billing amount CURRENCY mismatch: got %s, invoice in %s — "
            "NOT activating (invoice %s)",
            currency, invoice.currency, invoice.id,
        )
        await mark_invoice_failed(
            db, invoice, f"currency mismatch: {currency} != {invoice.currency}"
        )
        return PROCESSED
    if amount_cents < expected_cents:
        logger.warning(
            "Paymob billing amount MISMATCH: got %d piasters, invoice %s needs %d "
            "— NOT activating",
            amount_cents, invoice.id, expected_cents,
        )
        await mark_invoice_failed(
            db, invoice, f"amount mismatch: {amount_cents} < {expected_cents}"
        )
        return PROCESSED

    paid = await mark_invoice_paid(db, invoice, str(obj.get("id") or ""), obj)
    return PROCESSED if paid else IGNORED
