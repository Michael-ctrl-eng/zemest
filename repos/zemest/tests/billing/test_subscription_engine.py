"""Subscription engine tests — the idempotent activation gate + cycle.

Golden rules under test:
1. Webhook/sweep is the only trigger; ``mark_invoice_paid`` is a
   compare-and-set that NEVER double-activates.
2. Deterministic invoice keys: a re-run billing cycle cannot double-bill.
3. Dunning advances 1/3/5/7 days and exhausts into past_due → expired.
4. USDC invoices settle from matched deposits and void after the window.
5. Rail fallback: payoneer outage → paymob backup automatically.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.billing import (
    BillingPlan,
    BillingSubscription,
    BillingTransaction,
    PaymentMethod,
)
from app.services.billing.providers.base import (
    CheckoutResult,
    ProviderApiError,
    ProviderConfigError,
)
from app.services.billing.subscription_engine import (
    PERIOD_DAYS,
    billing_tick,
    cancel_subscription,
    create_subscription,
    ensure_default_plans,
    invoice_idempotency_key,
    mark_invoice_paid,
    reactivate_subscription,
    settle_usdc_invoices,
    void_invoice,
)
from tests.billing.conftest import VALID_WALLET, make_pending_invoice


class TestPlans:
    async def test_seed_idempotent(self, db_session):
        await ensure_default_plans(db_session)
        await ensure_default_plans(db_session)
        codes = (
            await db_session.scalars(select(BillingPlan.code))
        ).all()
        assert sorted(codes) == ["growth", "pro", "starter"]


class TestActivationGate:
    async def test_mark_invoice_paid_activates_once(
        self, db_session, subscription
    ):
        txn = await make_pending_invoice(db_session, subscription)
        assert await mark_invoice_paid(db_session, txn, "pay_123") is True

        await db_session.refresh(txn)
        await db_session.refresh(subscription)
        assert txn.status == "succeeded"
        assert txn.paid_at is not None
        assert txn.provider_reference == "pay_123"
        assert subscription.status == "active"
        assert subscription.dunning_attempts == 0
        assert subscription.last_payment_at is not None

    async def test_redelivery_is_a_noop(self, db_session, subscription):
        txn = await make_pending_invoice(db_session, subscription)
        assert await mark_invoice_paid(db_session, txn, "pay_123") is True
        # Redelivered webhook for the same invoice:
        assert await mark_invoice_paid(db_session, txn, "pay_123") is False

    async def test_terminal_states_never_regress(self, db_session, subscription):
        txn = await make_pending_invoice(db_session, subscription)
        txn.status = "refunded"
        await db_session.commit()
        assert await mark_invoice_paid(db_session, txn, "pay_123") is False
        assert txn.status == "refunded"

    async def test_void_invoice(self, db_session, subscription):
        txn = await make_pending_invoice(db_session, subscription)
        assert await void_invoice(db_session, txn, "stale") is True
        assert txn.status == "voided"
        assert txn.voided_at is not None
        # A second void (already terminal) changes nothing.
        assert await void_invoice(db_session, txn, "stale") is False

    async def test_recovery_extends_lapsed_period(self, db_session, subscription):
        subscription.current_period_end = datetime.utcnow() - timedelta(days=2)
        await db_session.commit()
        txn = await make_pending_invoice(db_session, subscription)
        assert await mark_invoice_paid(db_session, txn, "pay_9") is True
        await db_session.refresh(subscription)
        assert subscription.status == "active"
        assert subscription.current_period_end > datetime.utcnow()


class TestCreateSubscription:
    async def test_fiat_checkout_flow(
        self, db_session, test_tenant, billing_plan, billing_settings,
        fake_payoneer_checkout,
    ):
        sub, txn, checkout = await create_subscription(
            db_session, test_tenant, billing_plan, PaymentMethod.PAYONEER
        )
        assert sub.status == "trialing"  # starter has trial_days=14
        assert txn.payment_method == PaymentMethod.PAYONEER
        assert txn.status == "pending"
        assert txn.checkout_url.startswith("https://checkout.example")
        assert checkout.checkout_url == txn.checkout_url

    async def test_idempotent_second_call_returns_same_invoice(
        self, db_session, test_tenant, billing_plan, billing_settings,
        fake_payoneer_checkout,
    ):
        _, txn1, _ = await create_subscription(
            db_session, test_tenant, billing_plan, PaymentMethod.PAYONEER
        )
        _, txn2, _ = await create_subscription(
            db_session, test_tenant, billing_plan, PaymentMethod.PAYONEER
        )
        assert txn1.id == txn2.id
        count = len(
            (
                await db_session.scalars(
                    select(BillingTransaction).where(
                        BillingTransaction.subscription_id == txn1.subscription_id
                    )
                )
            ).all()
        )
        assert count == 1

    async def test_usdc_checkout_gives_instructions(
        self, db_session, test_tenant, billing_plan, billing_settings
    ):
        sub, txn, checkout = await create_subscription(
            db_session, test_tenant, billing_plan, PaymentMethod.USDC_SOLANA
        )
        assert txn.payment_method == PaymentMethod.USDC_SOLANA
        assert txn.amount_usdc == billing_plan.price_usdc
        assert txn.solana_reference and txn.solana_reference.startswith("zm-")
        assert checkout.deposit_address == VALID_WALLET
        assert checkout.reference_memo == txn.solana_reference
        assert checkout.checkout_url == ""  # no hosted page for crypto

    async def test_rail_fallback_payoneer_to_paymob(
        self, db_session, test_tenant, billing_plan, billing_settings,
        fake_paymob_checkout, monkeypatch,
    ):
        from app.services.billing.providers.payoneer import PayoneerProvider

        async def broken(self, **kwargs):
            raise ProviderApiError("payoneer checkout API returned 503", 503, "")

        monkeypatch.setattr(PayoneerProvider, "create_checkout", broken)
        _, txn, checkout = await create_subscription(
            db_session, test_tenant, billing_plan, PaymentMethod.PAYONEER
        )
        # Fell back to the BACKUP rail — merchant still gets a way to pay.
        assert txn.payment_method == PaymentMethod.PAYMOB
        assert txn.checkout_url.startswith("https://accept.example")

    async def test_unknown_method_rejected(
        self, db_session, test_tenant, billing_plan, billing_settings
    ):
        with pytest.raises(ProviderConfigError):
            await create_subscription(
                db_session, test_tenant, billing_plan, "stripe"
            )


class TestCancelReactivate:
    async def test_cancel_at_period_end_keeps_access(
        self, db_session, subscription
    ):
        await cancel_subscription(db_session, subscription)
        assert subscription.status == "active"
        assert subscription.cancel_at_period_end is True

    async def test_reactivate(self, db_session, subscription):
        await cancel_subscription(db_session, subscription)
        await reactivate_subscription(db_session, subscription)
        assert subscription.cancel_at_period_end is False

    async def test_reactivate_after_period_rejected(
        self, db_session, subscription
    ):
        subscription.current_period_end = datetime.utcnow() - timedelta(days=1)
        await db_session.commit()
        await cancel_subscription(db_session, subscription)
        # Period already lapsed → the row went straight to canceled.
        with pytest.raises(ValueError):
            await reactivate_subscription(db_session, subscription)


class TestUserPlanBridge:
    """Paid billing must actually unlock the platform limits (users.plan),
    and cancel/expiry must drop back to free."""

    async def test_activation_unlocks_owner_plan(
        self, db_session, test_user, subscription, billing_plan
    ):
        test_user.plan = "free"
        await db_session.commit()
        txn = await make_pending_invoice(db_session, subscription)
        assert await mark_invoice_paid(db_session, txn, "pay_x") is True
        await db_session.refresh(test_user)
        # starter (the billing_plan fixture) maps to Growth limits.
        assert test_user.plan == "growth"

    async def test_immediate_cancel_downgrades(
        self, db_session, test_user, subscription
    ):
        test_user.plan = "pro"
        await db_session.commit()
        await cancel_subscription(db_session, subscription, immediate=True)
        await db_session.refresh(test_user)
        assert test_user.plan == "free"

    async def test_expiry_downgrades(
        self, db_session, test_user, subscription, billing_settings
    ):
        test_user.plan = "growth"
        subscription.status = "past_due"
        subscription.current_period_end = datetime.utcnow() - timedelta(days=10)
        await db_session.commit()
        stats = await billing_tick(db_session)
        assert stats["expired"] == 1
        await db_session.refresh(test_user)
        assert test_user.plan == "free"


class TestBillingTick:
    async def test_renewal_rolls_period_and_opens_invoice(
        self, db_session, subscription, billing_settings, fake_payoneer_checkout
    ):
        old_end = datetime.utcnow() - timedelta(days=1)
        subscription.current_period_start = old_end - timedelta(days=31)
        subscription.current_period_end = old_end
        await db_session.commit()

        stats = await billing_tick(db_session)
        assert stats["renewed"] == 1
        await db_session.refresh(subscription)
        assert subscription.current_period_end == old_end + timedelta(days=PERIOD_DAYS)
        invoices = (
            await db_session.scalars(
                select(BillingTransaction).where(
                    BillingTransaction.subscription_id == subscription.id
                )
            )
        ).all()
        assert len(invoices) == 1  # the renewal invoice
        assert invoices[0].status == "pending"

    async def test_renewal_honors_scheduled_cancel(
        self, db_session, subscription, billing_settings
    ):
        subscription.current_period_end = datetime.utcnow() - timedelta(days=1)
        subscription.cancel_at_period_end = True
        await db_session.commit()
        stats = await billing_tick(db_session)
        assert stats["canceled"] == 1
        await db_session.refresh(subscription)
        assert subscription.status == "canceled"

    async def test_dunning_advances_and_creates_retry(
        self, db_session, subscription, billing_settings, fake_payoneer_checkout
    ):
        # Invoice opened 2 days ago (past the 1-day first-attempt grace)
        # with the retry due — dunning must act.
        txn = await make_pending_invoice(
            db_session, subscription, created_days_ago=2
        )
        subscription.dunning_next_retry_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()

        stats = await billing_tick(db_session)
        assert stats["dunning_attempted"] == 1
        await db_session.refresh(subscription)
        assert subscription.dunning_attempts == 1
        # Backoff day 1: retry scheduled +1 day.
        assert subscription.dunning_next_retry_at > datetime.utcnow()
        # The superseded attempt was voided; a retry invoice exists.
        await db_session.refresh(txn)
        assert txn.status == "voided"
        retries = (
            await db_session.scalars(
                select(BillingTransaction).where(
                    BillingTransaction.subscription_id == subscription.id,
                    BillingTransaction.status == "pending",
                )
            )
        ).all()
        assert len(retries) == 1
        assert retries[0].idempotency_key.endswith("-r1")

    async def test_dunning_exhaustion_goes_past_due_then_expired(
        self, db_session, subscription, billing_settings, fake_payoneer_checkout
    ):
        txn = await make_pending_invoice(db_session, subscription)
        subscription.dunning_attempts = 4  # exhausted
        subscription.dunning_next_retry_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.commit()
        stats = await billing_tick(db_session)
        assert stats["past_due"] == 1
        await db_session.refresh(txn)
        assert txn.status == "failed"

        # Grace elapses → expired.
        subscription.current_period_end = datetime.utcnow() - timedelta(days=8)
        await db_session.commit()
        stats = await billing_tick(db_session)
        assert stats["expired"] == 1
        await db_session.refresh(subscription)
        assert subscription.status == "expired"


class TestUsdcSettlement:
    async def test_settle_matched_deposit(
        self, db_session, subscription, billing_settings, fake_usdc_provider,
        fake_chain, billing_plan,
    ):
        txn = await make_pending_invoice(
            db_session, subscription,
            method=PaymentMethod.USDC_SOLANA,
            amount_usdc=billing_plan.price_usdc,
            solana_reference="zm-want-this",
        )
        fake_chain.add_deposit(
            int(billing_plan.price_usdc * Decimal(1_000_000)),
            reference="zm-want-this",
        )
        stats = await settle_usdc_invoices(db_session)
        assert stats["settled"] == 1
        await db_session.refresh(txn)
        await db_session.refresh(subscription)
        assert txn.status == "succeeded"
        assert txn.provider_reference  # the on-chain signature
        assert subscription.status == "active"

    async def test_underpayment_does_not_settle(
        self, db_session, subscription, billing_settings, fake_usdc_provider,
        fake_chain, billing_plan,
    ):
        await make_pending_invoice(
            db_session, subscription,
            method=PaymentMethod.USDC_SOLANA,
            amount_usdc=billing_plan.price_usdc,
            solana_reference="zm-under",
        )
        fake_chain.add_deposit(1000, reference="zm-under")  # far too little
        stats = await settle_usdc_invoices(db_session)
        assert stats["settled"] == 0

    async def test_unconfirmed_deposit_not_settled(
        self, db_session, subscription, billing_settings, fake_usdc_provider,
        fake_chain, billing_plan,
    ):
        await make_pending_invoice(
            db_session, subscription,
            method=PaymentMethod.USDC_SOLANA,
            amount_usdc=billing_plan.price_usdc,
            solana_reference="zm-early",
        )
        fake_chain.add_deposit(
            int(billing_plan.price_usdc * Decimal(1_000_000)),
            reference="zm-early",
            confirmations=2, status="processed",
        )
        assert (await settle_usdc_invoices(db_session))["settled"] == 0

    async def test_stale_invoice_voided(
        self, db_session, subscription, billing_settings, fake_usdc_provider,
        fake_chain, billing_plan,
    ):
        txn = await make_pending_invoice(
            db_session, subscription,
            method=PaymentMethod.USDC_SOLANA,
            amount_usdc=billing_plan.price_usdc,
            created_days_ago=9,  # window is 7 days
        )
        stats = await settle_usdc_invoices(db_session)
        assert stats["voided"] == 1
        await db_session.refresh(txn)
        assert txn.status == "voided"

    async def test_sweep_idempotent_after_settlement(
        self, db_session, subscription, billing_settings, fake_usdc_provider,
        fake_chain, billing_plan,
    ):
        await make_pending_invoice(
            db_session, subscription,
            method=PaymentMethod.USDC_SOLANA,
            amount_usdc=billing_plan.price_usdc,
            solana_reference="zm-once",
        )
        fake_chain.add_deposit(
            int(billing_plan.price_usdc * Decimal(1_000_000)),
            reference="zm-once",
        )
        first = await settle_usdc_invoices(db_session)
        second = await settle_usdc_invoices(db_session)
        assert first["settled"] == 1
        assert second["settled"] == 0  # invoice already succeeded (CAS)


class TestIdempotencyKeys:
    def test_deterministic(self):
        key1 = invoice_idempotency_key("abc", datetime(2026, 9, 1))
        key2 = invoice_idempotency_key("abc", datetime(2026, 9, 1))
        assert key1 == key2 == "sub-abc-20260901"
        assert invoice_idempotency_key("abc", datetime(2026, 9, 1), 2) == (
            "sub-abc-20260901-r2"
        )
