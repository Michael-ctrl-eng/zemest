"""Payout orchestration — merchant money OUT via Payoneer or SKALE.

Flow (no manual intervention unless policy demands it):

    user requests payout → fraud gate → balance check → freeze amount
    → auto-approve when amount <= PAYOUT_AUTO_APPROVE_MAX and no open
      flags, else admin approval queue
    → execute on the rail (payoneer send_payout | skale send_payout)
    → status lands via rail callback (Payoneer webhook / SKALE tx hash)
      or the admin retry button.

Fees: the platform keeps PLATFORM_FEE_PCT % of the gross balance
(computed in available_balance). Payoneer charges the receiver-side fee
on their side; SKALE transfers are gas-free (Europa chain) so the rail
cost is zero — the "lowest possible fees" requirement.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.billing import PayoutAccount, PayoutRequest
from app.services.billing import fraud
from app.services.billing.subscription_engine import available_balance

logger = logging.getLogger(__name__)


class PayoutError(Exception):
    pass


def compute_fee(amount: int) -> int:
    pct = get_settings().PLATFORM_FEE_PCT
    if pct <= 0:
        return 0
    d = (Decimal(amount) * Decimal(str(pct)) / 100).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(d)


async def create_payout_request(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    payout_account_id: uuid.UUID,
    amount: int,
) -> PayoutRequest:
    """Validate + freeze a payout request. Raises PayoutError with a
    merchant-safe message on any refusal."""
    s = get_settings()
    if amount < s.PAYOUT_MIN_AMOUNT:
        raise PayoutError(f"minimum payout is {s.PAYOUT_MIN_AMOUNT / 100:.2f} {s.PAYOUT_CURRENCY}")

    allowed, reason = await fraud.check_payout_request(db, user_id, amount)
    if not allowed:
        raise PayoutError(reason)

    res = await db.execute(
        select(PayoutAccount).where(
            PayoutAccount.id == payout_account_id, PayoutAccount.user_id == user_id
        )
    )
    account = res.scalar_one_or_none()
    if account is None:
        raise PayoutError("payout account not found")
    if account.status != "verified":
        raise PayoutError("payout account is not verified yet")

    rail = "skale" if account.method == "skale" else "payoneer"
    if rail == "skale":
        from app.services.billing.providers import skale as sk

        details = account.details or ""
        if not sk.valid_eth_address(details):
            raise PayoutError("payout account has an invalid wallet address")

    balance = await available_balance(db, user_id)
    if amount > balance:
        raise PayoutError(
            f"insufficient available balance (available: {balance / 100:.2f} "
            f"{s.PAYOUT_CURRENCY})"
        )

    fee = compute_fee(amount)
    request = PayoutRequest(
        user_id=user_id,
        payout_account_id=account.id,
        rail=rail,
        amount=amount,
        currency=s.PAYOUT_CURRENCY,
        fee_amount=fee,
        net_amount=amount - fee,
        status="pending",
    )
    db.add(request)
    await db.commit()

    # Auto-approve small, clean payouts → funds move without any human.
    clean = not await fraud.has_open_flags(db, user_id)
    if clean and amount <= s.PAYOUT_AUTO_APPROVE_MAX:
        await approve(db, request, approved_by="auto")
    return request


async def approve(db: AsyncSession, request: PayoutRequest, *, approved_by: str) -> PayoutRequest:
    if request.status != "pending":
        raise PayoutError(f"payout request is {request.status}, not pending")
    request.status = "approved"
    request.approved_by = approved_by[:40]
    await db.commit()
    # Execute immediately — the rails are idempotent (reference = request id)
    return await execute(db, request)


async def execute(db: AsyncSession, request: PayoutRequest) -> PayoutRequest:
    """Send the money on the rail. Idempotent per request id."""
    if request.status not in ("approved", "processing"):
        return request
    request.status = "processing"
    await db.commit()

    res = await db.execute(
        select(PayoutAccount).where(PayoutAccount.id == request.payout_account_id)
    )
    account = res.scalar_one_or_none()
    if account is None:
        request.status = "failed"
        request.failure_reason = "payout account vanished"
        await db.commit()
        return request

    amount_decimal = str(Decimal(request.net_amount) / 100)
    try:
        if request.rail == "payoneer":
            from app.services.billing.providers import payoneer

            client = payoneer.PayoneerClient()
            if not client.payouts_configured():
                request.status = "failed"
                request.failure_reason = "Payoneer rail is not configured"
                await db.commit()
                return request
            out = await client.send_payout(
                payee_id=account.details or "",
                amount=request.net_amount,
                currency=request.currency,
                client_reference_id=str(request.id),
            )
            request.provider_ref = out["provider_ref"]
            # Payoneer status lands via its webhook; assume processing until then
            request.status = "processing"
        else:  # skale
            from app.services.billing.providers import skale as sk

            out = await sk.send_payout(
                to=account.details or "",
                amount=amount_decimal,
                token="usdc",
                idempotency_key=str(request.id),
            )
            request.tx_hash = out["tx_hash"]
            request.status = "paid" if out.get("status") == "sent" else request.status
        request.processed_at = datetime.utcnow()
    except Exception as e:  # noqa: BLE001 — rail errors never crash the API
        request.status = "failed"
        request.failure_reason = str(e)[:300]
        logger.error("Payout %s failed on rail %s: %s", request.id, request.rail, e)
    await db.commit()

    if request.status == "paid":
        try:
            from app.services.telegram_notify import notify_admin_async

            notify_admin_async(
                f"💸 Payout sent: {amount_decimal} {request.currency} via "
                f"{request.rail} (tx {request.tx_hash or request.provider_ref or 'n/a'})"
            )
        except Exception:  # noqa: BLE001
            pass
    return request


async def mark_paid_by_webhook(
    db: AsyncSession, request_id: uuid.UUID, provider_ref: str | None = None
) -> bool:
    """Payoneer payout-status callback → paid. Compare-and-set: only a
    non-terminal request flips; redeliveries are no-ops."""
    from sqlalchemy import update

    stmt = (
        update(PayoutRequest)
        .where(
            PayoutRequest.id == request_id,
            PayoutRequest.status.in_(("pending", "approved", "processing")),
        )
        .values(
            status="paid",
            processed_at=datetime.utcnow(),
            **({"provider_ref": provider_ref} if provider_ref else {}),
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return bool(result.rowcount)
