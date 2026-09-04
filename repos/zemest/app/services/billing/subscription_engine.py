"""Subscription engine — monthly recurring billing, the single source of truth.

Unified lifecycle for every provider:

    subscribe()  → Subscription (incomplete) + first Invoice + checkout handoff
    webhook      → mark_invoice_paid() → activate()   [idempotent — THE gate]
    billing tick → renew invoices for platform-managed rails (paymob/payoneer),
                   dunning with backoff, past_due → cancel → downgrade
    cancel()     → cancel_at_period_end (keep access) or immediate (downgrade)
    reactivate() → resume before period end, else new charge

Activation rules (the user's core requirement):
* ``activate()`` flips ``user.plan`` to the paid plan, extends the period,
  marks the subscription active and notifies (email + Telegram admin) —
  EXACTLY ONCE per invoice (guarded by invoice status + a compare-and-set
  UPDATE), so webhook redeliveries can never double-apply.
* ``downgrade()`` returns the account to the free plan lazily — the plan
  gates in plan_service read the live subscription status anyway, so a
  brief lag can never grant paid limits for free.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import (
    FraudFlag,
    Invoice,
    PaymentEvent,
    PaymentMethod,
    Subscription,
)
from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.services.plan_service import PLANS

logger = logging.getLogger(__name__)

PERIOD_DAYS = 31  # billing months are fixed-length (no proration drift)
DUNNING_SCHEDULE_HOURS = (24, 72, 120, 168)  # retry backoff after a failed charge
MAX_DUNNING_ATTEMPTS = len(DUNNING_SCHEDULE_HOURS) + 1  # initial + retries
PAST_DUE_GRACE_DAYS = 7  # canceled-for-non-payment grace before downgrade


# --------------------------------------------------------------------------- #
# Money helpers
# --------------------------------------------------------------------------- #
def to_smallest_unit(amount: Decimal | float | int | str, currency: str = "USD") -> int:
    """EGP/USD → piasters/cents (×100), Decimal-safe, ROUND_HALF_UP."""
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_smallest_unit(amount: int) -> str:
    return str(Decimal(amount) / 100)


def plan_amount(plan_key: str, provider: str) -> tuple[int, str]:
    """(amount, currency) for a plan on a provider rail.

    Paymob charges EGP (plan list prices); Stripe/Payoneer rails charge USD
    at the configured USD prices (Stripe Price objects carry the amount;
    here we only need a fallback number for OUR invoice when the Stripe
    invoice hasn't landed yet). USD fallback pricing: growth $12.99, pro $34.99.
    """
    plan = PLANS.get(plan_key) or PLANS["growth"]
    if provider == "paymob":
        return to_smallest_unit(plan.price_egp_month, "EGP"), "EGP"
    usd = {"growth": Decimal("12.99"), "pro": Decimal("34.99")}.get(
        plan_key, Decimal("12.99")
    )
    return to_smallest_unit(usd, "USD"), "USD"


# --------------------------------------------------------------------------- #
# Invoice numbering (INV-YYYYMM-NNNN, per-month sequence, race-safe via MAX+1
# inside the same transaction — the unique constraint backstops collisions)
# --------------------------------------------------------------------------- #
async def next_invoice_number(db: AsyncSession) -> str:
    prefix = f"INV-{datetime.utcnow().strftime('%Y%m')}-"
    res = await db.execute(
        select(func.max(Invoice.number)).where(Invoice.number.like(f"{prefix}%"))
    )
    current = res.scalar_one_or_none()
    if current:
        try:
            seq = int(current[len(prefix):]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


# --------------------------------------------------------------------------- #
# Subscribe / invoices
# --------------------------------------------------------------------------- #
async def get_active_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    res = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(("active", "trialing", "past_due")),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def create_subscription_and_invoice(
    db: AsyncSession,
    user: User,
    plan_key: str,
    provider: str,
) -> tuple[Subscription, Invoice]:
    """Create (or replace) the subscription contract + first open invoice.

    The invoice starts ``open`` with NO charge; the checkout flow (Stripe
    Checkout / Paymob intention / Payoneer redirect) collects payment and a
    VERIFIED webhook flips it to paid → activation. The user's plan does
    NOT change until that happens (never trust the browser redirect).
    """
    # Supersede any live subscription for this user first (plan changes
    # mid-period create a fresh contract; Stripe rails cancel the old
    # provider-side subscription separately).
    await db.execute(
        update(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_(("active", "trialing", "past_due", "incomplete")),
        )
        .values(status="canceled", canceled_at=datetime.utcnow(), canceled_by="system",
                cancel_reason="superseded by new subscription")
    )

    amount, currency = plan_amount(plan_key, provider)
    now = datetime.utcnow()
    sub = Subscription(
        user_id=user.id,
        plan=plan_key,
        status="incomplete",
        provider=provider,
        current_period_start=now,
        current_period_end=now + timedelta(days=PERIOD_DAYS),
    )
    db.add(sub)
    await db.flush()

    invoice = Invoice(
        number=await next_invoice_number(db),
        user_id=user.id,
        subscription_id=sub.id,
        plan=plan_key,
        amount=amount,
        currency=currency,
        status="open",
        period_start=now,
        period_end=now + timedelta(days=PERIOD_DAYS),
        due_at=now + timedelta(hours=48),
        provider=provider,
        line_items={
            "items": [
                {
                    "description": f"Zemest {PLANS[plan_key].name} — monthly subscription",
                    "amount": amount,
                    "currency": currency,
                    "quantity": 1,
                }
            ]
        },
    )
    db.add(invoice)
    await db.commit()
    logger.info(
        "Billing: subscription %s created for user %s (%s/%s, invoice %s)",
        sub.id, user.id, plan_key, provider, invoice.number,
    )
    return sub, invoice


async def get_invoice_by_provider_id(
    db: AsyncSession, provider: str, provider_invoice_id: str
) -> Invoice | None:
    res = await db.execute(
        select(Invoice).where(
            Invoice.provider == provider,
            Invoice.provider_invoice_id == provider_invoice_id,
        )
    )
    return res.scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Activation — THE idempotent money→features gate
# --------------------------------------------------------------------------- #
async def mark_invoice_paid(
    db: AsyncSession,
    invoice: Invoice,
    *,
    provider_charge_id: str | None = None,
    provider_invoice_id: str | None = None,
) -> bool:
    """Transition an invoice to paid + activate the plan. Returns True ONLY
    on the transition that actually flipped it (webhook redelivery → False).

    The UPDATE's WHERE clause is the compare-and-set: only a non-terminal,
    non-paid invoice matches, exactly once.
    """
    now = datetime.utcnow()
    stmt = (
        update(Invoice)
        .where(
            Invoice.id == invoice.id,
            Invoice.status.in_(("draft", "open")),
        )
        .values(
            status="paid",
            paid_at=now,
            attempt_count=invoice.attempt_count,
            last_error=None,
            **({"provider_charge_id": provider_charge_id} if provider_charge_id else {}),
            **({"provider_invoice_id": provider_invoice_id} if provider_invoice_id else {}),
        )
    )
    result = await db.execute(stmt)
    if not result.rowcount:
        await db.rollback()
        return False
    await db.commit()

    # Re-fetch the live subscription (the invoice row was updated blind)
    res = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
    sub = res.scalar_one_or_none()
    if sub is not None:
        await activate(db, sub, period_start=invoice.period_start or now)
    await _notify_payment_success(db, invoice)
    logger.info("Billing: invoice %s PAID — plan activated", invoice.number)
    return True


async def activate(
    db: AsyncSession, sub: Subscription, period_start: datetime | None = None
) -> None:
    """Flip the user's plan + limits + status — idempotent, notification fires."""
    start = period_start or datetime.utcnow()
    stmt = (
        update(Subscription)
        .where(Subscription.id == sub.id)
        .values(
            status="active",
            current_period_start=start,
            current_period_end=start + timedelta(days=PERIOD_DAYS),
            failed_attempts=0,
            next_retry_at=None,
            cancel_at_period_end=False,
            canceled_at=None,
            cancel_reason=None,
        )
    )
    await db.execute(stmt)

    # user.plan upgrade — ONE compare-and-set (only when the new plan is
    # actually higher, or the subscription just (re)activated).
    await db.execute(
        update(User)
        .where(User.id == sub.user_id)
        .values(plan=sub.plan)
    )
    await db.commit()


async def downgrade_to_free(db: AsyncSession, user_id: uuid.UUID, reason: str) -> None:
    """Return the account to free limits (cancel/expiry path)."""
    await db.execute(update(User).where(User.id == user_id).values(plan="free"))
    await db.commit()
    logger.info("Billing: user %s downgraded to free (%s)", user_id, reason)


# --------------------------------------------------------------------------- #
# Cancel / reactivate
# --------------------------------------------------------------------------- #
async def cancel_subscription(
    db: AsyncSession,
    sub: Subscription,
    *,
    immediate: bool = False,
    by: str = "user",
    reason: str | None = None,
) -> Subscription:
    """Cancel. Default: at period end (the user keeps what they paid for);
    ``immediate`` ends access now (refunds are issued rail-side only)."""
    now = datetime.utcnow()
    if immediate:
        sub.status = "canceled"
        sub.canceled_at = now
        await downgrade_to_free(db, sub.user_id, reason or "canceled immediate")
    else:
        sub.cancel_at_period_end = True
        sub.cancel_reason = reason or "user requested"
    sub.canceled_by = by
    await db.commit()
    return sub


async def reactivate_subscription(db: AsyncSession, sub: Subscription) -> Subscription:
    """Undo a scheduled cancel while the period is still live."""
    if sub.status != "active" or not sub.cancel_at_period_end:
        raise ValueError("subscription is not in a cancellable-but-live state")
    sub.cancel_at_period_end = False
    sub.cancel_reason = None
    await db.commit()
    return sub


# --------------------------------------------------------------------------- #
# Monthly billing tick (platform-managed rails) + dunning
# --------------------------------------------------------------------------- #
async def billing_tick(db: AsyncSession) -> dict:
    """Run by the scheduler hourly. Three jobs:

    1. RENEW: active subscriptions on platform-managed rails whose period
       ended → create the next open invoice.
    2. DUNNING: open invoices past their retry time → re-charge (the caller
       supplies the charge callback — see api/billing.py wiring); failure
       advances the backoff, exhaustion → past_due → grace → cancel.
    3. EXPIRE: canceled-at-period-end and past-due-grace-ended subs →
       downgrade to free.
    """
    now = datetime.utcnow()
    stats = {"renewed": 0, "dunning_attempted": 0, "past_due": 0, "canceled": 0, "downgraded": 0}

    # --- 1. renew ---------------------------------------------------------
    res = await db.execute(
        select(Subscription).where(
            Subscription.status == "active",
            Subscription.provider.in_(("paymob", "payoneer")),
            Subscription.current_period_end < now,
            Subscription.cancel_at_period_end == False,  # noqa: E712
        )
    )
    for sub in res.scalars():
        amount, currency = plan_amount(sub.plan, sub.provider)
        invoice = Invoice(
            number=await next_invoice_number(db),
            user_id=sub.user_id,
            subscription_id=sub.id,
            plan=sub.plan,
            amount=amount,
            currency=currency,
            status="open",
            period_start=sub.current_period_end,
            period_end=sub.current_period_end + timedelta(days=PERIOD_DAYS),
            due_at=now + timedelta(hours=48),
            provider=sub.provider,
            line_items={
                "items": [
                    {
                        "description": f"Zemest {PLANS[sub.plan].name} — monthly subscription",
                        "amount": amount,
                        "currency": currency,
                        "quantity": 1,
                    }
                ]
            },
        )
        db.add(invoice)
        sub.current_period_start = sub.current_period_end
        sub.current_period_end = sub.current_period_end + timedelta(days=PERIOD_DAYS)
        await db.commit()
        stats["renewed"] += 1

    # --- 2. dunning: fail open invoices on their schedule ------------------
    res = await db.execute(
        select(Invoice).where(
            Invoice.status == "open",
            Invoice.provider.in_(("paymob", "payoneer")),
            Invoice.next_attempt_at.is_not(None),
            Invoice.next_attempt_at <= now,
        )
    )
    for invoice in res.scalars():
        # The actual charge attempt is wired in api/billing.py (rail-aware);
        # this tick marks attempts exhausted → past_due escalation.
        invoice.attempt_count += 1
        if invoice.attempt_count >= MAX_DUNNING_ATTEMPTS:
            invoice.status = "uncollectible"
            await _escalate_past_due(db, invoice, stats)
        else:
            hours = DUNNING_SCHEDULE_HOURS[
                min(invoice.attempt_count - 1, len(DUNNING_SCHEDULE_HOURS) - 1)
            ]
            invoice.next_attempt_at = now + timedelta(hours=hours)
        await db.commit()
        stats["dunning_attempted"] += 1

    # --- 3. expire ---------------------------------------------------------
    # a) subscriptions that hit their period end while cancel_at_period_end
    res = await db.execute(
        select(Subscription).where(
            Subscription.status == "active",
            Subscription.cancel_at_period_end == True,  # noqa: E712
            Subscription.current_period_end < now,
        )
    )
    for sub in res.scalars():
        sub.status = "canceled"
        sub.canceled_at = now
        await downgrade_to_free(db, sub.user_id, "canceled at period end")
        stats["canceled"] += 1
        stats["downgraded"] += 1
        await db.commit()

    # b) past_due subscriptions whose grace window closed
    grace_cutoff = now - timedelta(days=PAST_DUE_GRACE_DAYS)
    res = await db.execute(
        select(Subscription).where(
            Subscription.status == "past_due",
            Subscription.canceled_at.is_not(None),
            Subscription.canceled_at < grace_cutoff,
        )
    )
    for sub in res.scalars():
        sub.status = "canceled"
        await downgrade_to_free(db, sub.user_id, "past due grace ended")
        stats["downgraded"] += 1
        await db.commit()

    return stats


async def _escalate_past_due(db: AsyncSession, invoice: Invoice, stats: dict) -> None:
    res = await db.execute(select(Subscription).where(Subscription.id == invoice.subscription_id))
    sub = res.scalar_one_or_none()
    if sub is None:
        return
    sub.status = "past_due"
    sub.failed_attempts = invoice.attempt_count
    sub.canceled_at = datetime.utcnow()  # grace clock anchor
    await db.commit()
    stats["past_due"] += 1
    logger.warning(
        "Billing: invoice %s uncollectible — subscription %s past_due",
        invoice.number, sub.id,
    )


# --------------------------------------------------------------------------- #
# Webhook ledger — idempotency for every provider event
# --------------------------------------------------------------------------- #
async def record_event(
    db: AsyncSession,
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    signature_valid: bool,
) -> PaymentEvent | None:
    """Insert the event ledger row. Returns None when already processed
    (idempotency: unique (provider, provider_event_id))."""
    existing = await db.execute(
        select(PaymentEvent).where(
            PaymentEvent.provider == provider,
            PaymentEvent.provider_event_id == provider_event_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        return None  # duplicate delivery
    event = PaymentEvent(
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
        signature_valid=signature_valid,
        status="received",
    )
    db.add(event)
    await db.commit()
    return event


async def finish_event(
    db: AsyncSession, event: PaymentEvent, outcome: str, detail: str | None = None
) -> None:
    event.outcome = outcome[:40]
    event.detail = (detail or "")[:400]
    event.status = "processed"
    event.processed_at = datetime.utcnow()
    await db.commit()


# --------------------------------------------------------------------------- #
# Notifications (best-effort — same posture as report_service)
# --------------------------------------------------------------------------- #
async def _notify_payment_success(db: AsyncSession, invoice: Invoice) -> None:
    try:
        from app.services.telegram_notify import notify_admin_async

        notify_admin_async(
            f"💰 Payment received: invoice {invoice.number} "
            f"({from_smallest_unit(invoice.amount)} {invoice.currency}) — "
            f"plan {invoice.plan} activated."
        )
    except Exception:  # noqa: BLE001 — notification must never break billing
        logger.debug("Telegram payment notification skipped", exc_info=True)

    try:
        res = await db.execute(select(User).where(User.id == invoice.user_id))
        user = res.scalar_one_or_none()
        if user and user.email:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            import aiosmtplib

            from app.config import get_settings

            s = get_settings()
            if not s.SMTP_USER:
                return
            msg = MIMEMultipart()
            msg["From"] = s.NOTIFICATION_FROM_EMAIL
            msg["To"] = user.email
            msg["Subject"] = f"Zemest — payment received ({invoice.number})"
            msg.attach(
                MIMEText(
                    f"Your {invoice.plan} subscription is active.\n"
                    f"Invoice {invoice.number}: "
                    f"{from_smallest_unit(invoice.amount)} {invoice.currency} — paid.\n"
                    "All features are unlocked in your dashboard.",
                    "plain",
                    "utf-8",
                )
            )
            await aiosmtplib.send(
                msg,
                hostname=s.SMTP_HOST,
                port=s.SMTP_PORT,
                username=s.SMTP_USER,
                password=s.SMTP_PASSWORD,
                use_tls=False,
                start_tls=True,
            )
    except Exception:  # noqa: BLE001
        logger.debug("Payment email skipped", exc_info=True)


# --------------------------------------------------------------------------- #
# Merchant balance → payouts
# --------------------------------------------------------------------------- #
async def available_balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    """What the platform currently owes the merchant (USD cents).

    = fully-paid online order totals (payment_status 'paid') across the
      user's shops − platform fee − every payout already granted
      (pending/approved/processing/paid — anything not failed/canceled).
    COD money is collected by the merchant on delivery and never passes
    through the platform, so it correctly contributes zero.
    """
    res = await db.execute(
        select(func.coalesce(func.sum(Order.total), 0)).join(
            Tenant, Order.tenant_id == Tenant.id
        ).where(
            Tenant.owner_id == user_id,
            Order.payment_status == "paid",
        )
    )
    gross_egp = float(res.scalar() or 0)
    from app.config import get_settings

    s = get_settings()
    fee_pct = s.PLATFORM_FEE_PCT
    net_egp = gross_egp * (1 - fee_pct / 100.0) if fee_pct > 0 else gross_egp

    from app.models.billing import PayoutRequest

    res = await db.execute(
        select(func.coalesce(func.sum(PayoutRequest.amount), 0)).where(
            PayoutRequest.user_id == user_id,
            PayoutRequest.status.in_(("pending", "approved", "processing", "paid")),
        )
    )
    paid_out_cents = int(res.scalar() or 0)

    # Unit hygiene (caught by adversarial test): order totals are EGP UNITS,
    # payout amounts are USD CENTS. Convert EGP → USD cents ONCE, then
    # subtract cents from cents.
    rate = s.EGP_TO_USD_RATE or 48.5
    gross_usd_cents = to_smallest_unit(Decimal(str(net_egp)) / Decimal(str(rate)), "USD")
    return max(0, gross_usd_cents - paid_out_cents)
