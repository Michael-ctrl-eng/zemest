"""Adversarial tests — billing engine core (invoicing, activation idempotency,
cancel/reactivate, dunning, balance).

Money invariants under attack:
* webhook redelivery must NEVER double-activate a plan (idempotency)
* invoice numbering must be unique + monotonic under same-transaction races
* cancel-at-period-end keeps access until the period ends; immediate cancel
  downgrades at once
* dunning advances 1d/3d/5d/7d then past_due → grace → cancel → free
* available_balance can never go negative (payouts freeze the amount)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.billing import Invoice, PayoutRequest, Subscription
from app.models.user import User
from app.services.billing import subscription_engine as engine


@pytest_asyncio.fixture
async def paid_user(db_session):
    user = User(name="Merchant", email="merchant@example.com")
    db_session.add(user)
    await db_session.commit()
    return user


async def _make_sub_invoice(db_session, user, plan="growth", provider="paymob"):
    return await engine.create_subscription_and_invoice(db_session, user, plan, provider)


class TestInvoicing:
    async def test_first_invoice_open_and_numbered(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user)
        assert invoice.status == "open"
        assert invoice.number.startswith("INV-")
        assert invoice.amount == 29900  # 299 EGP in piasters on the paymob rail
        assert invoice.currency == "EGP"
        assert sub.status == "incomplete"  # not active until payment confirms

    async def test_usd_amount_on_stripe_rail(self, db_session, paid_user):
        _, invoice = await _make_sub_invoice(db_session, paid_user, provider="stripe")
        assert invoice.currency == "USD"
        assert invoice.amount == 1299  # $12.99

    async def test_invoice_numbers_monotonic_unique(self, db_session, paid_user):
        nums = []
        for _ in range(3):
            _, invoice = await _make_sub_invoice(db_session, paid_user)
            nums.append(invoice.number)
        assert len(set(nums)) == 3
        seqs = [int(n.split("-")[-1]) for n in nums]
        assert seqs == sorted(seqs)

    async def test_old_live_subscription_superseded(self, db_session, paid_user):
        sub1, _ = await _make_sub_invoice(db_session, paid_user)
        await db_session.refresh(sub1)
        sub2, _ = await _make_sub_invoice(db_session, paid_user, plan="pro")
        res = await db_session.execute(select(Subscription).where(Subscription.user_id == paid_user.id))
        subs = res.scalars().all()
        statuses = {s.id: s.status for s in subs}
        assert statuses[sub1.id] == "canceled"
        assert statuses[sub2.id] == "incomplete"


class TestActivationIdempotency:
    async def test_mark_paid_activates_plan_exactly_once(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user)
        await db_session.refresh(paid_user)

        first = await engine.mark_invoice_paid(db_session, invoice)
        assert first is True
        await db_session.refresh(paid_user)
        assert paid_user.plan == "growth"

        # ---- webhook REDELIVERY: same invoice, must not re-flip ----------
        second = await engine.mark_invoice_paid(db_session, invoice)
        assert second is False
        await db_session.refresh(invoice)
        assert invoice.status == "paid"
        assert invoice.paid_at is not None

    async def test_activation_extends_period_and_resets_dunning(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user)
        sub.failed_attempts = 3
        sub.next_retry_at = datetime.utcnow()
        await db_session.commit()

        await engine.mark_invoice_paid(db_session, invoice)
        await db_session.refresh(sub)
        assert sub.status == "active"
        assert sub.failed_attempts == 0
        assert sub.next_retry_at is None
        assert sub.current_period_end > datetime.utcnow() + timedelta(days=29)


class TestCancelReactivate:
    async def test_cancel_at_period_end_keeps_access(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user)
        await engine.mark_invoice_paid(db_session, invoice)

        sub = await engine.cancel_subscription(db_session, sub, by="user")
        assert sub.status == "active"
        assert sub.cancel_at_period_end is True
        await db_session.refresh(paid_user)
        assert paid_user.plan == "growth"  # keeps what they paid for

    async def test_immediate_cancel_downgrades_now(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user)
        await engine.mark_invoice_paid(db_session, invoice)

        sub = await engine.cancel_subscription(db_session, sub, immediate=True, by="user")
        assert sub.status == "canceled"
        await db_session.refresh(paid_user)
        assert paid_user.plan == "free"

    async def test_reactivate_undoes_scheduled_cancel(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user)
        await engine.mark_invoice_paid(db_session, invoice)
        await engine.cancel_subscription(db_session, sub)
        sub = await engine.reactivate_subscription(db_session, sub)
        assert sub.cancel_at_period_end is False
        assert sub.status == "active"

    async def test_reactivate_rejects_canceled(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user)
        await engine.mark_invoice_paid(db_session, invoice)
        await engine.cancel_subscription(db_session, sub, immediate=True)
        with pytest.raises(ValueError):
            await engine.reactivate_subscription(db_session, sub)


class TestBillingTick:
    async def test_renewal_creates_next_invoice(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user, provider="paymob")
        await engine.mark_invoice_paid(db_session, invoice)
        # force the period to be over
        sub.current_period_end = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()

        stats = await engine.billing_tick(db_session)
        assert stats["renewed"] == 1
        res = await db_session.execute(
            select(Invoice).where(Invoice.subscription_id == sub.id, Invoice.status == "open")
        )
        assert res.scalars().first() is not None

    async def test_cancel_at_period_end_expires_to_free(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user, provider="paymob")
        await engine.mark_invoice_paid(db_session, invoice)
        sub.cancel_at_period_end = True
        sub.current_period_end = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()

        stats = await engine.billing_tick(db_session)
        assert stats["downgraded"] >= 1
        await db_session.refresh(paid_user)
        assert paid_user.plan == "free"
        await db_session.refresh(sub)
        assert sub.status == "canceled"

    async def test_dunning_schedule_advances(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user, provider="paymob")
        invoice.next_attempt_at = datetime.utcnow() - timedelta(minutes=1)
        invoice.attempt_count = 0
        await db_session.commit()

        stats = await engine.billing_tick(db_session)
        assert stats["dunning_attempted"] == 1
        await db_session.refresh(invoice)
        assert invoice.attempt_count == 1
        # next retry ~24h out
        assert invoice.next_attempt_at is not None
        assert invoice.next_attempt_at > datetime.utcnow() + timedelta(hours=22)

    async def test_dunning_exhaustion_goes_past_due(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user, provider="paymob")
        invoice.attempt_count = engine.MAX_DUNNING_ATTEMPTS - 1
        invoice.next_attempt_at = datetime.utcnow() - timedelta(minutes=1)
        await db_session.commit()

        stats = await engine.billing_tick(db_session)
        assert stats["past_due"] == 1
        await db_session.refresh(invoice)
        assert invoice.status == "uncollectible"
        await db_session.refresh(sub)
        assert sub.status == "past_due"

    async def test_past_due_grace_expiry_downgrades(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user, provider="paymob")
        await engine.mark_invoice_paid(db_session, invoice)
        sub.status = "past_due"
        sub.canceled_at = datetime.utcnow() - timedelta(days=engine.PAST_DUE_GRACE_DAYS + 1)
        await db_session.commit()

        await engine.billing_tick(db_session)
        await db_session.refresh(paid_user)
        assert paid_user.plan == "free"

    async def test_stripe_rail_never_renewed_locally(self, db_session, paid_user):
        sub, invoice = await _make_sub_invoice(db_session, paid_user, provider="stripe")
        await engine.mark_invoice_paid(db_session, invoice)
        sub.current_period_end = datetime.utcnow() - timedelta(days=5)
        await db_session.commit()

        stats = await engine.billing_tick(db_session)
        assert stats["renewed"] == 0  # Stripe drives its own recurrence


class TestBalance:
    async def test_balance_zero_without_paid_orders(self, db_session, paid_user):
        assert await engine.available_balance(db_session, paid_user.id) == 0

    async def test_money_helpers(self):
        assert engine.to_smallest_unit(Decimal("12.99")) == 1299
        assert engine.to_smallest_unit(299) == 29900
        assert engine.to_smallest_unit(0.005) == 1  # ROUND_HALF_UP
        assert engine.from_smallest_unit(1299) == "12.99"
