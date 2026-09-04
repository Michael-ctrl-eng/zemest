"""Webhook processor — the ONLY place money state changes.

Pipeline (identical for Stripe + Payoneer, mirroring the Paymob module):

    raw body → signature verification (fail closed, constant-time)
            → JSON parse (reject malformed)
            → event ledger insert (unique provider+event_id → duplicates die)
            → dispatch by event type → engine (idempotent compare-and-set)
            → ALWAYS 200 on verified events (a redelivery must not loop)

Stripe events handled:
    invoice.paid / invoice.payment_succeeded → mark_invoice_paid
    invoice.payment_failed                   → dunning + fraud velocity
    customer.subscription.updated/deleted    → status sync
    charge.dispute.created                   → fraud hold + cancel

Payoneer events handled (callback names per partner program docs — the
payoneer-webhook-analyzer skill maps the concrete payload):
    payout.paid / payout.status=PAID         → payout marked paid
    payout.failed                            → payout failed + admin ping
    payment.succeeded (checkout collection)  → invoice paid via reference
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.billing import Invoice, PaymentEvent, PayoutRequest, Subscription
from app.services.billing import fraud
from app.services.billing.providers import payoneer as payoneer_provider
from app.services.billing.providers import stripe_provider
from app.services.billing.subscription_engine import (
    finish_event,
    mark_invoice_paid,
    record_event,
)
from app.services.billing.payouts import mark_paid_by_webhook

logger = logging.getLogger(__name__)


class WebhookRejected(Exception):
    """Signature/config failure — respond 4xx, touch nothing."""


# --------------------------------------------------------------------------- #
# Stripe
# --------------------------------------------------------------------------- #
async def process_stripe_event(
    db: AsyncSession, raw_body: bytes, signature_header: str
) -> dict:
    secret = get_settings().STRIPE_WEBHOOK_SECRET
    if not secret:
        raise WebhookRejected("STRIPE_WEBHOOK_SECRET not configured")
    if not stripe_provider.verify_webhook_signature(raw_body, signature_header, secret):
        raise WebhookRejected("invalid stripe signature")

    import json

    try:
        event = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise WebhookRejected("malformed stripe JSON") from None
    if not isinstance(event, dict) or "type" not in event:
        raise WebhookRejected("stripe event missing type")

    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id:
        raise WebhookRejected("stripe event missing id")

    ledger = await record_event(
        db,
        provider="stripe",
        provider_event_id=event_id,
        event_type=event_type,
        signature_valid=True,
    )
    if ledger is None:
        return {"status": "duplicate"}  # redelivery — idempotent no-op

    obj = event.get("data", {}).get("object", {}) if isinstance(event.get("data"), dict) else {}

    try:
        outcome, detail = await _dispatch_stripe(db, event_type, obj)
    except Exception:  # noqa: BLE001 — log + keep 200 so Stripe doesn't loop
        logger.exception("Stripe webhook handler error (type=%s)", event_type)
        outcome, detail = "error", event_type

    await finish_event(db, ledger, outcome, detail)
    return {"status": outcome}


async def _dispatch_stripe(db: AsyncSession, event_type: str, obj: dict) -> tuple[str, str]:
    if event_type in ("invoice.paid", "invoice.payment_succeeded", "invoice.succeeded"):
        stripe_invoice_id = str(obj.get("id") or "")
        user_id = _metadata_user_id(obj)
        invoice = await _find_invoice(db, "stripe", stripe_invoice_id, user_id)
        if invoice is None:
            return "ignored", f"no local invoice for {stripe_invoice_id}"
        flipped = await mark_invoice_paid(
            db,
            invoice,
            provider_charge_id=str(obj.get("payment_intent") or "") or None,
            provider_invoice_id=stripe_invoice_id,
        )
        # Attach the provider subscription link for cancel/reactivate sync
        await _link_stripe_subscription(db, invoice, obj)
        return ("paid" if flipped else "duplicate"), invoice.number

    if event_type in ("invoice.payment_failed",):
        user_id = _metadata_user_id(obj) or _customer_to_user(db, obj)
        if user_id:
            await _record_failure(db, user_id, f"stripe invoice {obj.get('id')}")
            return "dunning", str(user_id)
        return "ignored", "payment_failed without user"

    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        stripe_sub_id = str(obj.get("id") or "")
        status = str(obj.get("status") or "")
        res = await db.execute(
            select(Subscription).where(
                Subscription.provider == "stripe",
                Subscription.provider_subscription_id == stripe_sub_id,
            )
        )
        sub = res.scalar_one_or_none()
        if sub is None:
            # first sighting (checkout.session.completed path links it)
            await _link_by_customer(db, obj)
            return "linked", stripe_sub_id
        if status in ("active", "trialing"):
            sub.status = status
            cancel_at_end = bool(obj.get("cancel_at_period_end"))
            sub.cancel_at_period_end = cancel_at_end
            if not cancel_at_end:
                sub.canceled_at = None
        elif status in ("past_due", "unpaid", "incomplete", "incomplete_expired", "canceled"):
            sub.status = "canceled" if status == "canceled" else "past_due"
            if sub.status == "canceled":
                from app.services.billing.subscription_engine import downgrade_to_free

                await downgrade_to_free(db, sub.user_id, f"stripe {status}")
                sub.canceled_at = sub.canceled_at or __import__("datetime").datetime.utcnow()
        await db.commit()
        return "synced", f"{stripe_sub_id} → {status}"

    if event_type == "charge.dispute.created":
        user_id = _metadata_user_id(obj) or _customer_to_user(db, obj)
        if user_id:
            await fraud.on_dispute(db, user_id, f"stripe dispute {obj.get('id')}")
            return "fraud_hold", str(user_id)
        return "ignored", "dispute without user"

    if event_type == "checkout.session.completed":
        # Link subscription → our record + payment method display fields
        await _link_by_checkout_session(db, obj)
        return "linked", str(obj.get("id") or "")

    if event_type == "checkout.session.async_payment_succeeded":
        await _link_by_checkout_session(db, obj)
        return "linked", str(obj.get("id") or "")

    return "ignored", event_type


# --------------------------------------------------------------------------- #
# Payoneer
# --------------------------------------------------------------------------- #
async def process_payoneer_event(
    db: AsyncSession,
    raw_body: bytes,
    signature: str,
    signature_header_name: str | None = None,
) -> dict:
    s = get_settings()
    if not s.PAYONEER_WEBHOOK_SECRET:
        raise WebhookRejected("PAYONEER_WEBHOOK_SECRET not configured")
    if not payoneer_provider.verify_webhook_signature(
        raw_body, signature, s.PAYONEER_WEBHOOK_SECRET, s.PAYONEER_WEBHOOK_ALGO
    ):
        raise WebhookRejected("invalid payoneer signature")

    import json

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise WebhookRejected("malformed payoneer JSON") from None
    if not isinstance(payload, dict):
        raise WebhookRejected("payoneer body is not an object")

    event_id = str(
        payload.get("callback_id")
        or payload.get("event_id")
        or payload.get("client_reference_id")
        or f"{payload.get('type', 'evt')}-{payload.get('payout_id', payload.get('id', ''))}"
    )
    event_type = str(payload.get("type") or payload.get("event") or "")
    status = str(payload.get("status") or "").upper()

    ledger = await record_event(
        db,
        provider="payoneer",
        provider_event_id=event_id,
        event_type=event_type or f"status.{status.lower()}" if status else event_type,
        signature_valid=True,
    )
    if ledger is None:
        return {"status": "duplicate"}

    try:
        outcome, detail = await _dispatch_payoneer(db, payload, event_type, status)
    except Exception:  # noqa: BLE001
        logger.exception("Payoneer webhook handler error")
        outcome, detail = "error", event_type

    await finish_event(db, ledger, outcome, detail)
    return {"status": outcome}


async def _dispatch_payoneer(
    db: AsyncSession, payload: dict, event_type: str, status: str
) -> tuple[str, str]:
    # Payout status callbacks: reference = our payout request id
    reference = str(
        payload.get("client_reference_id") or payload.get("client_reference") or ""
    )
    if reference:
        try:
            request_id = uuid.UUID(reference)
        except ValueError:
            request_id = None
        if request_id is not None:
            res = await db.execute(
                select(PayoutRequest).where(PayoutRequest.id == request_id)
            )
            request = res.scalar_one_or_none()
            if request is not None:
                if status in ("PAID", "COMPLETED", "SUCCESS", "DONE"):
                    await mark_paid_by_webhook(
                        db, request.id, str(payload.get("payout_id") or "")
                    )
                    return "payout_paid", reference
                if status in ("FAILED", "REJECTED", "ERROR", "CANCELLED"):
                    from sqlalchemy import update
                    from datetime import datetime

                    await db.execute(
                        update(PayoutRequest)
                        .where(
                            PayoutRequest.id == request.id,
                            PayoutRequest.status.in_(("pending", "approved", "processing")),
                        )
                        .values(
                            status="failed",
                            failure_reason=str(payload.get("reason") or status)[:300],
                            processed_at=datetime.utcnow(),
                        )
                    )
                    await db.commit()
                    return "payout_failed", reference
                return "noted", f"{event_type} {status}"

    # Checkout collection callbacks: reference → our invoice
    if status in ("PAID", "COMPLETED", "SUCCESS", "DONE") and reference:
        res = await db.execute(select(Invoice).where(Invoice.number == reference))
        invoice = res.scalar_one_or_none()
        if invoice is not None:
            flipped = await mark_invoice_paid(
                db, invoice, provider_charge_id=str(payload.get("payment_id") or "") or None
            )
            return ("paid" if flipped else "duplicate"), invoice.number

    return "ignored", f"{event_type} {status}".strip()


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _metadata_user_id(obj: dict) -> uuid.UUID | None:
    meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    raw = meta.get("user_id") or obj.get("client_reference_id") or ""
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return None


async def _customer_to_user(db: AsyncSession, obj: dict) -> uuid.UUID | None:
    customer = str(obj.get("customer") or "")
    if not customer:
        return None
    res = await db.execute(
        select(Subscription).where(Subscription.provider_customer_id == customer)
    )
    sub = res.scalar_one_or_none()
    return sub.user_id if sub else None


async def _find_invoice(
    db: AsyncSession, provider: str, provider_invoice_id: str, user_id: uuid.UUID | None
) -> Invoice | None:
    if provider_invoice_id:
        res = await db.execute(
            select(Invoice).where(
                Invoice.provider == provider,
                Invoice.provider_invoice_id == provider_invoice_id,
            )
        )
        invoice = res.scalar_one_or_none()
        if invoice is not None:
            return invoice
    if user_id is not None:
        res = await db.execute(
            select(Invoice)
            .where(
                Invoice.user_id == user_id,
                Invoice.provider == provider,
                Invoice.status.in_(("draft", "open")),
            )
            .order_by(Invoice.created_at.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()
    return None


async def _link_stripe_subscription(db: AsyncSession, invoice: Invoice, obj: dict) -> None:
    sub_obj = obj.get("subscription") or ""
    if isinstance(sub_obj, str) and sub_obj.startswith("sub_"):
        res = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
        sub = res.scalar_one_or_none()
        if sub is not None and not sub.provider_subscription_id:
            sub.provider_subscription_id = sub_obj
            await db.commit()


async def _link_by_checkout_session(db: AsyncSession, obj: dict) -> None:
    user_id = _metadata_user_id(obj)
    sub_id = str(obj.get("subscription") or "")
    customer = str(obj.get("customer") or "")
    if user_id is None or not sub_id:
        return
    res = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.provider == "stripe",
        ).order_by(Subscription.created_at.desc())
    )
    subs = res.scalars().all()
    if not subs:
        return
    sub = subs[0]
    sub.provider_subscription_id = sub_id
    sub.provider_customer_id = customer
    sub.status = "active"
    await db.commit()

    # Save display-only payment method fields (brand/last4 — never the PAN)
    payment_method = obj.get("payment_method") or ""
    if isinstance(payment_method, str) and payment_method.startswith("pm_"):
        from app.models.billing import PaymentMethod

        db.add(
            PaymentMethod(
                user_id=user_id,
                provider="stripe",
                provider_pm_id=payment_method,
                kind="card",
                is_default=True,
            )
        )
        await db.commit()


async def _link_by_customer(db: AsyncSession, obj: dict) -> None:
    customer = str(obj.get("customer") or "")
    sub_id = str(obj.get("id") or "")
    if not customer or not sub_id:
        return
    res = await db.execute(
        select(Subscription).where(
            Subscription.provider_customer_id == customer
        ).order_by(Subscription.created_at.desc())
    )
    subs = res.scalars().all()
    if subs:
        subs[0].provider_subscription_id = sub_id
        await db.commit()


async def _record_failure(db: AsyncSession, user_id: uuid.UUID, detail: str) -> None:
    """Count the failure in the event ledger for fraud velocity + advance
    dunning on the newest open invoice."""
    await fraud.on_charge_failed(db, user_id)
    res = await db.execute(
        select(Invoice)
        .where(
            Invoice.user_id == user_id,
            Invoice.status == "open",
        )
        .order_by(Invoice.created_at.desc())
        .limit(1)
    )
    invoice = res.scalar_one_or_none()
    if invoice is not None:
        invoice.last_error = detail[:300]
        await db.commit()
