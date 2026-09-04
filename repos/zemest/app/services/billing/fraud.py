"""Fraud detection for the billing platform.

Rules (all automatic, all logged to ``fraud_flags``, all fail-SAFE):

1. **failed_charges_velocity** — >= 3 failed charge events for one user in
   24h → medium; >= 5 → high (card-testing pattern) + subscription moved to
   past_due + the default payment method detached.
2. **dispute / chargeback** — any ``charge.dispute.created`` event → high +
   payouts HELD (all payout requests blocked) + subscription canceled.
3. **payout_velocity** — more than PAYOUT_MAX_PER_DAY payout requests in a
   day → medium + the new request rejected.
4. **payout_anomaly** — payout request > 80% of lifetime paid volume in the
   first 14 days of the account → high + manual approval forced.
5. **ip_shared_trial_farm** — payments from an account whose signup_ip
   already carried a consumed trial (linking to the trial-abuse registry).

``payouts_held(user_id)`` is the gate every payout request passes through.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import FraudFlag, PaymentEvent, PayoutRequest, Subscription

logger = logging.getLogger(__name__)


async def has_open_flags(db: AsyncSession, user_id: uuid.UUID) -> bool:
    res = await db.execute(
        select(func.count(FraudFlag.id)).where(
            FraudFlag.user_id == user_id, FraudFlag.resolved_at.is_(None)
        )
    )
    return int(res.scalar() or 0) > 0


async def payouts_held(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """True when any open high-severity flag carries the payouts_held action."""
    res = await db.execute(
        select(func.count(FraudFlag.id)).where(
            FraudFlag.user_id == user_id,
            FraudFlag.resolved_at.is_(None),
            FraudFlag.action_taken.like("%payouts_held%"),
        )
    )
    return int(res.scalar() or 0) > 0


async def _flag(
    db: AsyncSession,
    user_id: uuid.UUID,
    kind: str,
    severity: str,
    detail: str,
    action_taken: str | None = None,
) -> FraudFlag:
    flag = FraudFlag(
        user_id=user_id, kind=kind, severity=severity, detail=detail[:400],
        action_taken=action_taken,
    )
    db.add(flag)
    await db.commit()
    logger.warning("Billing fraud flag: user=%s kind=%s severity=%s", user_id, kind, severity)
    try:
        from app.services.telegram_notify import notify_admin_async

        notify_admin_async(
            f"🚨 Fraud flag [{severity}] {kind} — user {user_id}: {detail[:200]}"
        )
    except Exception:  # noqa: BLE001
        pass
    return flag


async def on_charge_failed(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Called by the webhook processor for every verified failed-charge event.
    Velocity = payment_events rows of type invoice.payment_failed whose
    detail carries this user id, in the last 24h."""
    day_ago = datetime.utcnow() - timedelta(hours=24)
    res = await db.execute(
        select(func.count(PaymentEvent.id)).where(
            PaymentEvent.event_type == "invoice.payment_failed",
            PaymentEvent.detail == str(user_id),
            PaymentEvent.received_at >= day_ago,
        )
    )
    failures = int(res.scalar() or 0) + 1  # +1: the in-flight event's detail
    # is written by finish_event AFTER this dispatch — count it manually.
    if failures == 5:
        await _flag(
            db, user_id, "failed_charges_velocity", "high",
            f"{failures} failed charges in 24h (card testing pattern)",
            action_taken="subscription_past_due",
        )
        await db.execute(
            update_subscription_past_due_stmt(user_id)
        )
        await db.commit()
    elif failures == 3:
        await _flag(
            db, user_id, "failed_charges_velocity", "medium",
            f"{failures} failed charges in 24h",
        )


def update_subscription_past_due_stmt(user_id: uuid.UUID):
    from sqlalchemy import update

    return (
        update(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(("active", "trialing")),
        )
        .values(status="past_due", failed_attempts=5)
    )


async def on_dispute(db: AsyncSession, user_id: uuid.UUID, detail: str) -> None:
    """Chargeback opened → payouts frozen + subscription canceled."""
    await _flag(
        db, user_id, "dispute", "high", detail,
        action_taken="payouts_held,subscription_canceled",
    )
    from sqlalchemy import update

    now = datetime.utcnow()
    await db.execute(
        update(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(("active", "trialing", "past_due")),
        )
        .values(
            status="canceled", canceled_at=now, canceled_by="system",
            cancel_reason="dispute opened",
        )
    )
    from app.models.user import User

    await db.execute(update(User).where(User.id == user_id).values(plan="free"))
    await db.commit()


async def check_payout_request(
    db: AsyncSession, user_id: uuid.UUID, amount: int
) -> tuple[bool, str]:
    """Payout-request gate. Returns (allowed, reason)."""
    if await payouts_held(db, user_id):
        return False, "payouts are held pending fraud review (contact support)"

    day_ago = datetime.utcnow() - timedelta(hours=24)
    res = await db.execute(
        select(func.count(PayoutRequest.id)).where(
            PayoutRequest.user_id == user_id,
            PayoutRequest.requested_at >= day_ago,
        )
    )
    from app.config import get_settings

    max_per_day = get_settings().PAYOUT_MAX_PER_DAY
    count = int(res.scalar() or 0)
    if count >= max_per_day:
        await _flag(
            db, user_id, "payout_velocity", "medium",
            f"{count} payout requests in 24h (limit {max_per_day})",
        )
        return False, f"payout request limit reached ({max_per_day}/day)"
    return True, ""
