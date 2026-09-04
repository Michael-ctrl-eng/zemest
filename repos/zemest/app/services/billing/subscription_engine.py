"""Subscription engine — activation gate, monthly cycle, dunning, USDC.

New billing architecture (rails: payoneer PRIMARY / paymob BACKUP /
usdc_solana crypto). Platform-managed recurring: OUR hourly billing tick
renews invoices and advances dunning — no provider-side subscription
machinery is trusted with state.

The golden rules (audit D5 + the subscription-activator playbook):

1. **Webhooks / on-chain sweeps are the ONLY payment triggers.** A browser
   redirect is UX, never a state change.
2. **Activation is idempotent** — ``mark_invoice_paid`` flips the invoice
   with a compare-and-set UPDATE (WHERE status IN non-terminal states);
   a redelivered webhook or a re-swept deposit returns False and changes
   nothing.
3. **Fail-safe direction** — when in doubt, do NOT unlock.
4. **Rails fallback** — automatic renewals try payoneer first; on
   provider outage/misconfiguration they fall back to paymob (the backup
   rail) instead of leaving the merchant with no way to pay.

State machine:

    trialing → active                    (first payment verified)
    active   → canceled                  (cancel_at_period_end honored)
    active   → past_due                  (dunning exhausted)
    past_due → active                    (payment recovered)
    past_due → expired                   (grace elapsed, no payment)
    canceled → active                    (reactivate before period end)

USDC-Solana specifics: pending USDC invoices are settled by an on-chain
deposit sweep (memo reference first, exact amount second, confirmations
required) and VOIDED when they outlive the payment window — "void" is the
local cancellation of an unpaid crypto invoice (the chain never refunds).
"""
from __future__ import annotations

import logging
import smtplib
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from email.message import EmailMessage
from typing import Any, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.billing import (
    BillingPlan,
    BillingSubscription,
    BillingTransaction,
    PaymentMethod,
)
from app.models.tenant import Tenant
from app.services.billing.providers import (
    CheckoutResult,
    ProviderApiError,
    ProviderConfigError,
    ProviderError,
    get_provider,
)
from app.services.billing.providers.usdc_solana import (
    UsdcSolanaProvider,
    new_solana_reference,
)

logger = logging.getLogger(__name__)

# Fixed-length months (no proration drift — matches the recurring-cycle
# playbook: 31 days, invoice per period).
PERIOD_DAYS = 31

# Dunning retry schedule: retry N happens this many days after the
# previous attempt; exhaustion (5 total attempts) → past_due.
DUNNING_SCHEDULE_DAYS: tuple[int, ...] = (1, 3, 5, 7)
PAST_DUE_GRACE_DAYS = 7

# USDC invoices must be paid within this window or they are voided.
USDC_PAYMENT_WINDOW_DAYS = 7

# Non-terminal invoice states a payment may transition FROM.
_OPEN_INVOICE_STATES = ("pending", "awaiting_confirmation", "failed")

SEED_PLANS = [
    (
        "starter",
        "Starter",
        Decimal("750.00"),
        Decimal("15.000000"),
        14,
        {"max_tenants": 1, "max_messages_per_month": 3000},
        "One page, 3,000 AI replies/month, Arabic + English.",
    ),
    (
        "growth",
        "Growth",
        Decimal("1850.00"),
        Decimal("37.000000"),
        14,
        {"max_tenants": 3, "max_messages_per_month": 15000},
        "Up to 3 pages, 15,000 AI replies/month, priority models.",
    ),
    (
        "pro",
        "Pro",
        Decimal("3900.00"),
        Decimal("78.000000"),
        14,
        {"max_tenants": 10, "max_messages_per_month": 60000},
        "10 pages, 60,000 AI replies/month, dedicated support.",
    ),
]


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #
async def ensure_default_plans(db: AsyncSession) -> None:
    """Idempotently seed the plan catalog (safe on every boot)."""
    for code, name, egp, usdc, trial, limits, desc in SEED_PLANS:
        existing = await db.scalar(select(BillingPlan).where(BillingPlan.code == code))
        if existing:
            continue
        db.add(
            BillingPlan(
                code=code,
                name=name,
                description=desc,
                price_egp=egp,
                price_usdc=usdc,
                billing_interval="monthly",
                trial_days=trial,
                limits=limits,
                is_active=True,
            )
        )
    await db.commit()


async def get_plan_by_code(db: AsyncSession, code: str) -> BillingPlan | None:
    return await db.scalar(
        select(BillingPlan).where(BillingPlan.code == code, BillingPlan.is_active.is_(True))
    )


# --------------------------------------------------------------------------- #
# Small pure helpers
# --------------------------------------------------------------------------- #
def next_period_end(start: datetime) -> datetime:
    return start + timedelta(days=PERIOD_DAYS)


def _period_key(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def invoice_idempotency_key(
    subscription_id: Any, period_start: datetime, attempt: int = 0
) -> str:
    """Deterministic dedup key — a retried cycle can never double-bill."""
    base = f"sub-{subscription_id}-{_period_key(period_start)}"
    return base if attempt <= 0 else f"{base}-r{attempt}"


def _egp_amount_for_plan(plan: BillingPlan, method: str) -> Decimal:
    """Price actually charged on a rail.

    * paymob  → plan EGP price (Egypt rail, EGP native).
    * payoneer → plan USDC price / USD: Payoneer charges USD; we charge
      the USD-equivalent of the plan list price using the env rate so the
      EGP catalog stays authoritative.
    * usdc_solana → plan USDC price (converted to micro-USDC upstream).
    """
    if method == PaymentMethod.PAYONEER:
        rate = Decimal(str(get_settings().BILLING_USD_TO_EGP_RATE or 48.0))
        usd = (plan.price_egp / rate).quantize(Decimal("0.01"))
        return usd
    if method == PaymentMethod.USDC_SOLANA:
        return plan.price_usdc
    return plan.price_egp


def _currency_for_method(method: str) -> str:
    if method == PaymentMethod.PAYONEER:
        return "USD"
    if method == PaymentMethod.USDC_SOLANA:
        return "USDC"
    return "EGP"


# --------------------------------------------------------------------------- #
# Checkout creation with rail fallback (payoneer → paymob)
# --------------------------------------------------------------------------- #
async def _create_checkout_with_fallback(
    *,
    method: str,
    amount: Decimal,
    reference: str,
    customer_email: str,
    description: str,
    success_url: str,
    webhook_url: str,
) -> tuple[str, CheckoutResult]:
    """Create a checkout on the preferred rail; fall back to paymob when
    the PRIMARY rail (payoneer) is unavailable. Returns
    ``(effective_method, result)``.

    Never falls back to usdc_solana — paying in crypto is an explicit
    user choice, not an automatic degradation.
    """
    order = [method]
    if method == PaymentMethod.PAYONEER:
        order.append(PaymentMethod.PAYMOB)
    last_error: Exception | None = None
    for candidate in order:
        try:
            provider = get_provider(candidate)
            result = await provider.create_checkout(
                amount=amount,
                currency=_currency_for_method(candidate),
                reference=reference,
                customer_email=customer_email,
                description=description,
                success_url=success_url,
                webhook_url=webhook_url,
            )
            return candidate, result
        except (ProviderApiError, ProviderConfigError) as e:
            last_error = e
            logger.warning(
                "billing checkout on %s failed (%s) — %s",
                candidate,
                type(e).__name__,
                e,
            )
    raise last_error or ProviderConfigError("no billing rail available")


# --------------------------------------------------------------------------- #
# Subscribe / renew — create the invoice + payment session
# --------------------------------------------------------------------------- #
async def upsert_subscription(
    db: AsyncSession,
    tenant: Tenant,
    plan: BillingPlan,
    method: str,
) -> BillingSubscription:
    """Create (or reset) the tenant's single subscription row — no invoice,
    no provider calls. Used by :func:`create_subscription` and by the admin
    comp-grant route (which skips the rails entirely)."""
    if not PaymentMethod.is_valid(method):
        raise ProviderConfigError(f"Unknown payment method {method!r}")
    subscription = await db.scalar(
        select(BillingSubscription).where(BillingSubscription.tenant_id == tenant.id)
    )
    now = datetime.utcnow()
    if subscription is None:
        subscription = BillingSubscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            payment_method=method,
            status="trialing" if plan.trial_days > 0 else "active",
            current_period_start=now,
            current_period_end=next_period_end(now),
        )
        db.add(subscription)
        await db.flush()
    else:
        # Resubscribe / plan change: reuse the single row.
        subscription.plan_id = plan.id
        subscription.payment_method = method
        subscription.cancel_at_period_end = False
        subscription.canceled_at = None
        subscription.dunning_attempts = 0
        subscription.dunning_next_retry_at = None
        if subscription.status in ("expired", "canceled", "past_due"):
            subscription.status = "active"
        if not subscription.current_period_end or subscription.current_period_end <= now:
            subscription.current_period_start = now
            subscription.current_period_end = next_period_end(now)
    return subscription


async def create_subscription(
    db: AsyncSession,
    tenant: Tenant,
    plan: BillingPlan,
    method: str,
    *,
    success_url: str = "",
    webhook_base_url: str = "",
) -> tuple[BillingSubscription, BillingTransaction, CheckoutResult]:
    """(Re)activate a tenant's subscription on a plan + rail.

    * Creates (or reuses) the subscription row — trialing during the
      trial window, pending first payment otherwise.
    * Creates the first invoice (deterministic idempotency key).
    * Starts the checkout: Payoneer/Paymob → hosted URL; USDC → on-chain
      payment instructions (reference memo persisted on the invoice).
    """
    subscription = await upsert_subscription(db, tenant, plan, method)

    transaction, checkout = await _create_invoice(
        db,
        subscription=subscription,
        plan=plan,
        method=method,
        customer_email=tenant.business_email or "",
        success_url=success_url,
        webhook_base_url=webhook_base_url,
    )
    await db.commit()
    await db.refresh(subscription)
    await db.refresh(transaction)
    return subscription, transaction, checkout


async def _create_invoice(
    db: AsyncSession,
    *,
    subscription: BillingSubscription,
    plan: BillingPlan,
    method: str,
    customer_email: str = "",
    success_url: str = "",
    webhook_base_url: str = "",
    attempt: int = 0,
) -> tuple[BillingTransaction, CheckoutResult]:
    """One open invoice + its checkout session (idempotent per period).

    The transaction UUID is generated UP FRONT (before any provider call)
    so every rail correlates callbacks to a stable reference:
    * payoneer  → ``client_reference_id`` = invoice UUID
    * paymob    → ``special_reference``   = ``zbl-{invoice UUID}``
    * usdc      → memo = fresh high-entropy ``zm-`` reference
    """
    period_start = subscription.current_period_start or datetime.utcnow()
    key = invoice_idempotency_key(subscription.id, period_start, attempt)
    existing = await db.scalar(
        select(BillingTransaction).where(BillingTransaction.idempotency_key == key)
    )
    if existing is not None:
        return existing, _fake_checkout_for(existing)  # type: ignore[return-value]

    tx_id = uuid.uuid4()
    amount = _egp_amount_for_plan(plan, method)
    if method == PaymentMethod.USDC_SOLANA:
        reference = new_solana_reference()
    else:
        reference = str(tx_id)

    webhook_url = ""
    if webhook_base_url:
        webhook_url = f"{webhook_base_url.rstrip('/')}/api/payments/webhook/paymob"

    effective_method, checkout = await _create_checkout_with_fallback(
        method=method,
        amount=amount,
        reference=reference,
        customer_email=customer_email,
        description=f"Zemest {plan.name} subscription",
        success_url=success_url,
        webhook_url=webhook_url,
    )

    transaction = BillingTransaction(
        id=tx_id,
        tenant_id=subscription.tenant_id,
        subscription_id=subscription.id,
        plan_id=plan.id,
        kind="subscription_payment",
        payment_method=effective_method,
        status="pending",
        amount=amount,
        amount_usdc=plan.price_usdc if effective_method == PaymentMethod.USDC_SOLANA else None,
        currency=_currency_for_method(effective_method),
        idempotency_key=key,
        provider_reference=checkout.provider_reference,
        checkout_url=checkout.checkout_url or None,
        solana_reference=checkout.reference_memo or None,
        raw={"checkout_reference": checkout.provider_reference},
    )
    db.add(transaction)
    await db.flush()
    return transaction, checkout


def _fake_checkout_for(transaction: BillingTransaction):
    """Rehydrate a checkout view for an already-existing invoice (the
    idempotent re-run path — callers only read instructions from it)."""
    from app.services.billing.providers.base import CheckoutResult as _CR

    return _CR(
        provider=transaction.payment_method,
        provider_reference=transaction.provider_reference or "",
        checkout_url=transaction.checkout_url or "",
        amount=transaction.amount,
        currency=transaction.currency,
        deposit_address=(get_provider(PaymentMethod.USDC_SOLANA).treasury_wallet or "")
        if transaction.payment_method == PaymentMethod.USDC_SOLANA
        else "",
        reference_memo=transaction.solana_reference or "",
        raw=transaction.raw or {},
    )


# --------------------------------------------------------------------------- #
# User-plan bridge (platform limits)
# --------------------------------------------------------------------------- #
# The platform's usage gates (plan_service: free/growth/pro) read
# ``users.plan``. The billing rails own the MONEY state; this bridge keeps
# the feature tier in sync so a paid subscription actually unlocks limits
# and a cancellation/expiry actually drops back to free.
_PLAN_TO_USER_PLAN = {
    "starter": "growth",  # first paid tier → Growth limits (multi-shop)
    "growth": "growth",
    "pro": "pro",
}


async def _sync_user_plan(db: AsyncSession, subscription: BillingSubscription, *, active: bool) -> None:
    """Mirror the subscription state onto the tenant owner's users.plan."""
    from app.models.user import User

    plan = await db.scalar(select(BillingPlan).where(BillingPlan.id == subscription.plan_id))
    target = "free"
    if active and plan is not None:
        target = _PLAN_TO_USER_PLAN.get((plan.code or "").lower(), "growth")
    tenant = await db.scalar(select(Tenant).where(Tenant.id == subscription.tenant_id))
    if tenant is None:
        return
    user = await db.scalar(select(User).where(User.id == tenant.owner_id))
    if user is not None and (getattr(user, "plan", None) or "free") != target:
        user.plan = target
        # A paid plan outranks (and ends) any free trial window.
        if target != "free":
            user.trial_ends_at = None


# --------------------------------------------------------------------------- #
# The idempotent activation gate
# --------------------------------------------------------------------------- #
async def mark_invoice_paid(
    db: AsyncSession,
    transaction: BillingTransaction,
    provider_reference: str,
    raw: dict | None = None,
) -> bool:
    """Flip an open invoice to ``succeeded`` and activate the subscription.

    Compare-and-set on the invoice row: a redelivered webhook or a re-swept
    deposit returns False and touches nothing. Terminal states
    (succeeded/refunded/disputed/voided) never regress.
    """
    result = await db.execute(
        update(BillingTransaction)
        .where(
            BillingTransaction.id == transaction.id,
            BillingTransaction.status.in_(_OPEN_INVOICE_STATES),
        )
        .values(
            status="succeeded",
            paid_at=datetime.utcnow(),
            provider_reference=provider_reference,
            raw=raw or transaction.raw,
        )
    )
    if not result.rowcount:
        return False
    await db.refresh(transaction)

    subscription = await db.scalar(
        select(BillingSubscription).where(
            BillingSubscription.id == transaction.subscription_id
        )
    )
    if subscription is not None:
        now = datetime.utcnow()
        subscription.status = "active"
        subscription.dunning_attempts = 0
        subscription.dunning_next_retry_at = None
        subscription.cancel_at_period_end = False
        subscription.canceled_at = None
        subscription.last_payment_at = now
        # Extend the period from the paid moment when it already lapsed
        # (recovery after past_due), else keep the scheduled window.
        if not subscription.current_period_end or subscription.current_period_end <= now:
            subscription.current_period_start = now
            subscription.current_period_end = next_period_end(now)
        await _sync_user_plan(db, subscription, active=True)
    await db.commit()

    tenant = await db.scalar(select(Tenant).where(Tenant.id == transaction.tenant_id))
    await _notify_payment_success(tenant, transaction)
    logger.info(
        "billing invoice %s paid via %s (ref=%s) — subscription activated",
        transaction.id, transaction.payment_method, provider_reference,
    )
    return True


async def mark_invoice_failed(
    db: AsyncSession,
    transaction: BillingTransaction,
    reason: str,
) -> bool:
    """Open invoice → failed (a provider reported a definitive failure)."""
    result = await db.execute(
        update(BillingTransaction)
        .where(
            BillingTransaction.id == transaction.id,
            BillingTransaction.status.in_(_OPEN_INVOICE_STATES),
        )
        .values(status="failed", failed_reason=(reason or "")[:255])
    )
    if not result.rowcount:
        return False
    await db.commit()
    return True


async def void_invoice(
    db: AsyncSession,
    transaction: BillingTransaction,
    reason: str,
) -> bool:
    """Open invoice → voided (canceled before payment landed).

    For fiat rails a provider-side void is attempted first (Payoneer
    sessions); for USDC voiding is purely local — the chain never
    refunds, and no on-chain state is touched.
    """
    if transaction.payment_method == PaymentMethod.PAYONEER and transaction.provider_reference:
        try:
            provider = get_provider(PaymentMethod.PAYONEER)
            await provider.cancel(transaction.provider_reference)
        except ProviderError as e:
            logger.warning("payoneer void attempt failed (invoice=%s): %s", transaction.id, e)
    result = await db.execute(
        update(BillingTransaction)
        .where(
            BillingTransaction.id == transaction.id,
            BillingTransaction.status.in_(_OPEN_INVOICE_STATES),
        )
        .values(status="voided", voided_at=datetime.utcnow(), failed_reason=(reason or "")[:255])
    )
    if not result.rowcount:
        return False
    await db.commit()
    logger.info("billing invoice %s voided (%s)", transaction.id, reason)
    return True


# --------------------------------------------------------------------------- #
# Cancel / reactivate
# --------------------------------------------------------------------------- #
async def cancel_subscription(
    db: AsyncSession,
    subscription: BillingSubscription,
    *,
    immediate: bool = False,
) -> BillingSubscription:
    """Default cancel keeps every feature until the paid period ends."""
    now = datetime.utcnow()
    if immediate:
        subscription.status = "canceled"
        subscription.canceled_at = now
        await _sync_user_plan(db, subscription, active=False)
    else:
        subscription.cancel_at_period_end = True
        if not subscription.current_period_end or subscription.current_period_end <= now:
            subscription.status = "canceled"
            subscription.canceled_at = now
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def reactivate_subscription(
    db: AsyncSession, subscription: BillingSubscription
) -> BillingSubscription:
    """Undo a scheduled cancel — only while the paid period is still live."""
    now = datetime.utcnow()
    if subscription.status != "active" or not subscription.cancel_at_period_end:
        raise ValueError("reactivation is only possible before the period ends")
    if subscription.current_period_end and subscription.current_period_end <= now:
        raise ValueError("the paid period already ended — subscribe again")
    subscription.cancel_at_period_end = False
    await db.commit()
    await db.refresh(subscription)
    return subscription


# --------------------------------------------------------------------------- #
# USDC-Solana settlement sweep (payment check + void)
# --------------------------------------------------------------------------- #
async def settle_usdc_invoices(
    db: AsyncSession,
    provider: UsdcSolanaProvider | None = None,
) -> dict:
    """Sweep on-chain USDC deposits and settle matching invoices.

    Matching: memo reference first, exact amount (within tolerance)
    second. Settlement requires the confirmation gate. Unpaid USDC
    invoices older than ``USDC_PAYMENT_WINDOW_DAYS`` are voided.
    """
    provider = provider or get_provider(PaymentMethod.USDC_SOLANA)  # type: ignore[assignment]
    stats = {"settled": 0, "voided": 0, "settled_ids": [], "voided_ids": []}
    if not isinstance(provider, UsdcSolanaProvider) or not provider.is_configured():
        return stats

    pending = (
        await db.scalars(
            select(BillingTransaction)
            .where(
                BillingTransaction.payment_method == PaymentMethod.USDC_SOLANA,
                BillingTransaction.status.in_(("pending", "awaiting_confirmation")),
                BillingTransaction.kind == "subscription_payment",
            )
            .order_by(BillingTransaction.created_at)
        )
    ).all()
    if not pending:
        return stats

    try:
        deposits = await provider.find_deposits()
    except ProviderApiError as e:
        logger.warning("USDC sweep skipped — RPC unavailable: %s", e)
        return stats

    now = datetime.utcnow()
    for txn in pending:
        expected_micro = int(
            (txn.amount_usdc or Decimal(0)) * Decimal(1_000_000)
        )
        matched = None
        for deposit in deposits:
            if provider.deposit_matches(
                deposit, expected_micro, txn.solana_reference
            ):
                matched = deposit
                break
        if matched is not None and provider.deposit_settled(matched):
            paid = await mark_invoice_paid(
                db,
                txn,
                provider_reference=str(matched.get("signature") or ""),
                raw={
                    "signature": matched.get("signature"),
                    "amount_micro": matched.get("amount_micro"),
                    "mint": provider.mint,
                },
            )
            if paid:
                stats["settled"] += 1
                stats["settled_ids"].append(str(txn.id))
            continue
        # Not matched: void once the payment window lapses.
        age = now - (txn.created_at or now)
        if age > timedelta(days=USDC_PAYMENT_WINDOW_DAYS):
            if await void_invoice(db, txn, "usdc payment window elapsed"):
                stats["voided"] += 1
                stats["voided_ids"].append(str(txn.id))
    return stats


# --------------------------------------------------------------------------- #
# The billing tick — RENEW / DUNNING / EXPIRE / USDC
# --------------------------------------------------------------------------- #
async def billing_tick(
    db: AsyncSession,
    now: datetime | None = None,
    webhook_base_url: str = "",
) -> dict:
    """One billing-cycle pass. Safe to run every hour; idempotent by
    construction (deterministic invoice keys + CAS everywhere).

    Returns counters for observability (the admin tick route surfaces
    them and the scheduler logs them).
    """
    now = now or datetime.utcnow()
    stats = {
        "renewed": 0,
        "dunning_attempted": 0,
        "past_due": 0,
        "canceled": 0,
        "expired": 0,
        "usdc_settled": 0,
        "usdc_voided": 0,
    }

    # ---- 1. RENEW: active/trialing subs whose period ended -------------
    # (past_due subs are deliberately NOT renewed — dunning owns their
    # retry invoices and the EXPIRE phase owns their grace; renewing them
    # here would double-bill the period.)
    due_subs = (
        await db.scalars(
            select(BillingSubscription).where(
                BillingSubscription.status.in_(("active", "trialing")),
                BillingSubscription.current_period_end <= now,
            )
        )
    ).all()
    for sub in due_subs:
        plan = await db.scalar(select(BillingPlan).where(BillingPlan.id == sub.plan_id))
        if plan is None:
            logger.warning("billing tick: subscription %s has no plan — skipped", sub.id)
            continue
        # Honor scheduled cancels.
        if sub.cancel_at_period_end:
            sub.status = "canceled"
            sub.canceled_at = now
            await _sync_user_plan(db, sub, active=False)
            stats["canceled"] += 1
            continue
        # Roll the period forward and open the next invoice (idempotent).
        sub.current_period_start = sub.current_period_end
        sub.current_period_end = next_period_end(sub.current_period_start)
        if sub.status == "trialing":
            sub.status = "active"  # trial ended → now a paying period
        tenant = await db.scalar(select(Tenant).where(Tenant.id == sub.tenant_id))
        await _create_invoice(
            db,
            subscription=sub,
            plan=plan,
            method=sub.payment_method,
            customer_email=(tenant.business_email if tenant else "") or "",
            webhook_base_url=webhook_base_url,
        )
        stats["renewed"] += 1
    if due_subs:
        await db.commit()

    # ---- 2. DUNNING: advance retry schedule on open invoices -------------
    open_txns = (
        await db.scalars(
            select(BillingTransaction)
            .where(
                BillingTransaction.status.in_(("pending", "awaiting_confirmation")),
                BillingTransaction.kind == "subscription_payment",
                BillingTransaction.payment_method.in_(
                    (PaymentMethod.PAYONEER, PaymentMethod.PAYMOB)
                ),
            )
        )
    ).all()
    settings = get_settings()
    max_attempts = settings.BILLING_DUNNING_MAX_ATTEMPTS or 4
    for txn in open_txns:
        sub = await db.scalar(
            select(BillingSubscription).where(
                BillingSubscription.id == txn.subscription_id
            )
        )
        if sub is None:
            continue
        attempts = sub.dunning_attempts or 0
        retry_at = sub.dunning_next_retry_at
        if retry_at and retry_at > now:
            continue  # not due yet
        if attempts >= max_attempts:
            # Exhausted → invoice uncollectible, subscription past_due.
            if sub.status == "active":
                sub.status = "past_due"
                stats["past_due"] += 1
            await mark_invoice_failed(db, txn, "dunning exhausted (uncollectible)")
            continue
        # First-attempt grace: a freshly opened invoice gets at least the
        # first backoff interval (1 day) before any retry — renewals are
        # not "immediately overdue".
        age = now - (txn.created_at or now)
        if attempts == 0 and age < timedelta(days=DUNNING_SCHEDULE_DAYS[0]):
            continue
        # Issue a fresh checkout on the same rail (sessions are
        # single-use) with a deterministic retry idempotency key.
        plan = await db.scalar(select(BillingPlan).where(BillingPlan.id == txn.plan_id))
        if plan is not None and sub.payment_method in (
            PaymentMethod.PAYONEER,
            PaymentMethod.PAYMOB,
        ):
            # Void the superseded attempt, then open the retry invoice.
            await void_invoice(db, txn, f"superseded by retry {attempts + 1}")
            await _create_invoice(
                db,
                subscription=sub,
                plan=plan,
                method=sub.payment_method,
                attempt=attempts + 1,
            )
        backoff_days = DUNNING_SCHEDULE_DAYS[
            min(attempts, len(DUNNING_SCHEDULE_DAYS) - 1)
        ]
        sub.dunning_attempts = attempts + 1
        sub.dunning_next_retry_at = now + timedelta(days=backoff_days)
        stats["dunning_attempted"] += 1
    await db.commit()

    # ---- 3. EXPIRE: past_due grace elapsed / scheduled cancels -----------
    expired_subs = (
        await db.scalars(
            select(BillingSubscription).where(
                BillingSubscription.status == "past_due",
                BillingSubscription.current_period_end
                <= now - timedelta(days=PAST_DUE_GRACE_DAYS),
            )
        )
    ).all()
    for sub in expired_subs:
        sub.status = "expired"
        await _sync_user_plan(db, sub, active=False)
        stats["expired"] += 1
    if expired_subs:
        await db.commit()

    # ---- 4. USDC: settle deposits / void stale invoices -------------------
    usdc = await settle_usdc_invoices(db)
    stats["usdc_settled"] = usdc.get("settled", 0)
    stats["usdc_voided"] = usdc.get("voided", 0)

    logger.info("billing tick: %s", stats)
    return stats


# --------------------------------------------------------------------------- #
# Notifications (best effort — never blocks money state)
# --------------------------------------------------------------------------- #
async def _notify_payment_success(
    tenant: Tenant | None, transaction: BillingTransaction
) -> None:
    """Best-effort merchant email + admin log on a paid invoice."""
    logger.info(
        "billing: invoice %s PAID (%s %s via %s) for tenant %s",
        transaction.id,
        transaction.amount,
        transaction.currency,
        transaction.payment_method,
        transaction.tenant_id,
    )
    if tenant is None or not tenant.business_email:
        return
    settings = get_settings()
    if not (settings.SMTP_USER and settings.SMTP_PASSWORD):
        return  # SMTP unconfigured — the log line above is the notification
    try:
        msg = EmailMessage()
        msg["Subject"] = "Zemest subscription activated"
        msg["From"] = settings.NOTIFICATION_FROM_EMAIL
        msg["To"] = tenant.business_email
        msg.set_content(
            f"Your Zemest subscription payment was received "
            f"({transaction.amount} {transaction.currency} via "
            f"{transaction.payment_method}). Your plan is now active."
        )
        # Sync SMTP in a worker thread would block the loop — for the
        # single-process deployment a short blocking send is acceptable
        # and keeps this dependency-free (no aiosmtplib import here).
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:  # noqa: BLE001 — notifications must never break billing
        logger.warning("billing success email failed", exc_info=True)
