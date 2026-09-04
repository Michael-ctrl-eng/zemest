"""Adversarial tests — billing webhooks (Stripe + Payoneer).

Attack surface:
* forged / missing / replayed signatures → 401, DB untouched
* tampered body after signing → invalid signature
* unknown event types → 200 ignored (never 5xx loop)
* redelivered event id → duplicate, state applied ONCE
* amount tampering in-flight → not possible (signature covers raw body)
* dispute event → fraud hold + cancel + downgrade
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from sqlalchemy import select

from app.models.billing import FraudFlag, Invoice, PaymentEvent, Subscription
from app.models.user import User
from app.services.billing import subscription_engine as engine
from app.services.billing.providers import payoneer as payoneer_provider
from app.services.billing.providers import stripe_provider
from app.services.billing.webhook_processor import (
    WebhookRejected,
    process_payoneer_event,
    process_stripe_event,
)


async def _make_invoice(db_session):
    user = User(name="Wh", email="wh@example.com")
    db_session.add(user)
    await db_session.commit()
    sub, invoice = await engine.create_subscription_and_invoice(db_session, user, "growth", "stripe")
    return user, sub, invoice


def _stripe_event(event_id: str, event_type: str, obj: dict) -> bytes:
    return json.dumps(
        {"id": event_id, "type": event_type, "data": {"object": obj}}
    ).encode("utf-8")


def _stripe_sign(raw: bytes, secret: str, ts: int | None = None) -> str:
    ts = int(ts if ts is not None else time.time())
    sig = hmac.new(
        secret.encode("utf-8"), f"{ts}.".encode("utf-8") + raw, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={sig}"


SECRET = "whsec_test_secret"


@pytest.fixture
def stripe_secret(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", SECRET, raising=False)
    return SECRET


class TestStripeSignature:
    async def test_missing_secret_rejects(self, db_session):
        from app.config import get_settings

        settings = get_settings()
        old = settings.STRIPE_WEBHOOK_SECRET
        object.__setattr__(settings, "STRIPE_WEBHOOK_SECRET", "")
        try:
            raw = _stripe_event("evt_1", "invoice.paid", {})
            with pytest.raises(WebhookRejected):
                await process_stripe_event(db_session, raw, "t=1,v1=abc")
        finally:
            object.__setattr__(settings, "STRIPE_WEBHOOK_SECRET", old)

    async def test_forged_signature_rejected_no_db_write(self, db_session, stripe_secret):
        user, sub, invoice = await _make_invoice(db_session)
        raw = _stripe_event("evt_forge", "invoice.paid", {"id": "in_test", "metadata": {"user_id": str(user.id)}})
        sig = _stripe_sign(raw, "wrong-secret")
        with pytest.raises(WebhookRejected):
            await process_stripe_event(db_session, raw, sig)
        await db_session.refresh(invoice)
        assert invoice.status == "open"  # untouched

    async def test_body_tamper_after_signing_rejected(self, db_session, stripe_secret):
        raw = _stripe_event("evt_tamper", "invoice.paid", {"id": "in_x"})
        sig = _stripe_sign(raw, SECRET)
        tampered = raw.replace(b"in_x", b"in_y")
        with pytest.raises(WebhookRejected):
            await process_stripe_event(db_session, tampered, sig)

    async def test_replayed_timestamp_rejected(self, db_session, stripe_secret):
        raw = _stripe_event("evt_replay", "invoice.paid", {"id": "in_x"})
        old_ts = int(time.time()) - 3600
        sig = _stripe_sign(raw, SECRET, ts=old_ts)
        with pytest.raises(WebhookRejected):
            await process_stripe_event(db_session, raw, sig)

    def test_signature_primitives(self):
        raw = b'{"id": 1}'
        sig = _stripe_sign(raw, SECRET)
        assert stripe_provider.verify_webhook_signature(raw, sig, SECRET)
        assert not stripe_provider.verify_webhook_signature(raw, sig, SECRET + "x")
        assert not stripe_provider.verify_webhook_signature(raw, "t=,v1=", SECRET)
        assert not stripe_provider.verify_webhook_signature(raw, "garbage", SECRET)
        assert not stripe_provider.verify_webhook_signature(raw, sig, "")


class TestStripeProcessing:
    async def test_invoice_paid_activates(self, db_session, stripe_secret):
        user, sub, invoice = await _make_invoice(db_session)
        invoice.provider_invoice_id = "in_real_1"
        await db_session.commit()

        raw = _stripe_event(
            "evt_paid_1",
            "invoice.paid",
            {"id": "in_real_1", "metadata": {"user_id": str(user.id)}, "payment_intent": "pi_1"},
        )
        result = await process_stripe_event(db_session, raw, _stripe_sign(raw, SECRET))
        assert result["status"] == "paid"
        await db_session.refresh(invoice)
        assert invoice.status == "paid"
        await db_session.refresh(user)
        assert user.plan == "growth"

    async def test_redelivery_is_duplicate_no_double_activation(self, db_session, stripe_secret):
        user, sub, invoice = await _make_invoice(db_session)
        invoice.provider_invoice_id = "in_real_2"
        await db_session.commit()

        raw = _stripe_event(
            "evt_dup_1", "invoice.paid", {"id": "in_real_2", "metadata": {"user_id": str(user.id)}}
        )
        sig = _stripe_sign(raw, SECRET)
        await process_stripe_event(db_session, raw, sig)
        result = await process_stripe_event(db_session, raw, sig)
        assert result["status"] == "duplicate"

        # exactly one payment_event row for this provider event id
        res = await db_session.execute(
            select(PaymentEvent).where(PaymentEvent.provider_event_id == "evt_dup_1")
        )
        assert len(res.scalars().all()) == 1

    async def test_unknown_event_ignored_200(self, db_session, stripe_secret):
        raw = _stripe_event("evt_unknown", "customer.discount.created", {"id": "di_1"})
        result = await process_stripe_event(db_session, raw, _stripe_sign(raw, SECRET))
        assert result["status"] == "ignored"

    async def test_dispute_cancels_and_holds_payouts(self, db_session, stripe_secret):
        user, sub, invoice = await _make_invoice(db_session)
        invoice.provider_invoice_id = "in_real_3"
        await db_session.commit()
        raw = _stripe_event(
            "evt_paid_2", "invoice.paid", {"id": "in_real_3", "metadata": {"user_id": str(user.id)}}
        )
        await process_stripe_event(db_session, raw, _stripe_sign(raw, SECRET))

        raw = _stripe_event(
            "evt_dispute_1",
            "charge.dispute.created",
            {"id": "dp_1", "metadata": {"user_id": str(user.id)}},
        )
        result = await process_stripe_event(db_session, raw, _stripe_sign(raw, SECRET))
        assert result["status"] == "fraud_hold"

        await db_session.refresh(user)
        assert user.plan == "free"
        res = await db_session.execute(
            select(FraudFlag).where(FraudFlag.user_id == user.id, FraudFlag.kind == "dispute")
        )
        flags = res.scalars().all()
        assert flags and "payouts_held" in (flags[0].action_taken or "")

    async def test_subscription_deleted_syncs_cancel(self, db_session, stripe_secret):
        user, sub, invoice = await _make_invoice(db_session)
        sub.provider_subscription_id = "sub_real_1"
        sub.status = "active"
        user.plan = "growth"
        await db_session.commit()

        raw = _stripe_event(
            "evt_subdel_1",
            "customer.subscription.deleted",
            {"id": "sub_real_1", "status": "canceled", "customer": "cus_1"},
        )
        result = await process_stripe_event(db_session, raw, _stripe_sign(raw, SECRET))
        assert result["status"] == "synced"
        await db_session.refresh(sub)
        assert sub.status == "canceled"
        await db_session.refresh(user)
        assert user.plan == "free"


class TestPayoneerWebhooks:
    async def test_signature_hmac_over_raw_body(self):
        raw = b'{"type":"payout.status","status":"PAID"}'
        secret = "payoneer-test-secret"
        sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        assert payoneer_provider.verify_webhook_signature(raw, sig, secret, "sha256")
        assert not payoneer_provider.verify_webhook_signature(raw, sig, secret, "sha512")
        assert not payoneer_provider.verify_webhook_signature(raw, "deadbeef", secret, "sha256")
        assert not payoneer_provider.verify_webhook_signature(raw, sig, "", "sha256")

    async def test_payout_paid_marks_request(self, db_session, monkeypatch):
        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "PAYONEER_WEBHOOK_SECRET", "payoneer-test-secret", raising=False)

        from app.models.billing import PayoutAccount, PayoutRequest

        user = User(name="P", email="p@example.com")
        db_session.add(user)
        await db_session.commit()
        account = PayoutAccount(
            user_id=user.id, method="payoneer", details="PAYEE1", status="verified"
        )
        db_session.add(account)
        await db_session.commit()
        payout = PayoutRequest(
            user_id=user.id,
            payout_account_id=account.id,
            rail="payoneer",
            amount=5000,
            currency="USD",
            net_amount=5000,
            status="processing",
        )
        db_session.add(payout)
        await db_session.commit()

        raw = json.dumps(
            {
                "type": "payout.status",
                "status": "PAID",
                "client_reference_id": str(payout.id),
                "payout_id": "po_123",
            }
        ).encode()
        sig = hmac.new(b"payoneer-test-secret", raw, hashlib.sha256).hexdigest()
        result = await process_payoneer_event(db_session, raw, sig)
        assert result["status"] == "payout_paid"
        await db_session.refresh(payout)
        assert payout.status == "paid"
        assert payout.provider_ref == "po_123"

    async def test_forged_payoneer_signature_rejected(self, db_session, monkeypatch):
        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "PAYONEER_WEBHOOK_SECRET", "payoneer-test-secret", raising=False)
        raw = b'{"type":"payout.status","status":"PAID","client_reference_id":"x"}'
        with pytest.raises(WebhookRejected):
            await process_payoneer_event(db_session, raw, "forged")

    async def test_unknown_status_noted_not_failed(self, db_session, monkeypatch):
        from app.config import get_settings
        from app.models.billing import PayoutAccount, PayoutRequest

        settings = get_settings()
        monkeypatch.setattr(settings, "PAYONEER_WEBHOOK_SECRET", "payoneer-test-secret", raising=False)

        user = User(name="N", email="n@example.com")
        db_session.add(user)
        await db_session.commit()
        account = PayoutAccount(user_id=user.id, method="payoneer", details="PAYEE2", status="verified")
        db_session.add(account)
        await db_session.commit()
        payout = PayoutRequest(
            user_id=user.id,
            payout_account_id=account.id,
            rail="payoneer",
            amount=1000,
            net_amount=1000,
            status="processing",
        )
        db_session.add(payout)
        await db_session.commit()

        raw = json.dumps(
            {"type": "payout.status", "status": "PROCESSING", "client_reference_id": str(payout.id)}
        ).encode()
        sig = hmac.new(b"payoneer-test-secret", raw, hashlib.sha256).hexdigest()
        result = await process_payoneer_event(db_session, raw, sig)
        assert result["status"] == "noted"
        await db_session.refresh(payout)
        assert payout.status == "processing"  # interim status never touches the request


class TestPayoneerClient:
    async def test_config_gates(self):
        client = payoneer_provider.PayoneerClient(
            client_id="", client_secret="", base_url=""
        )
        assert client.configured() is False
        with pytest.raises(payoneer_provider.PayoneerConfigError):
            await client._get_token()

    async def test_send_payout_requires_program(self):
        client = payoneer_provider.PayoneerClient(
            client_id="id", client_secret="sec", program_id="", base_url="https://x"
        )
        with pytest.raises(payoneer_provider.PayoneerConfigError):
            await client.send_payout(
                payee_id="P1", amount=100, currency="USD", client_reference_id="r1"
            )


class TestSkaleProvider:
    def test_valid_eth_address(self):
        from app.services.billing.providers import skale

        assert skale.valid_eth_address("0x71C7656EC7ab88b098defB751B7401B5f6d8976F")
        assert not skale.valid_eth_address("0x123")
        assert not skale.valid_eth_address("nope")
        assert not skale.valid_eth_address(None)

    def test_sign_body(self):
        from app.services.billing.providers import skale

        sig = skale.sign_body(b"{}", "secret")
        expected = hmac.new(b"secret", b"{}", hashlib.sha256).hexdigest()
        assert sig == expected

    async def test_send_payout_validates_input(self):
        from app.services.billing.providers import skale

        with pytest.raises(skale.SkalePayoutError):
            await skale.send_payout(to="bad", amount="1", token="usdc", idempotency_key="k")
        with pytest.raises(skale.SkalePayoutError):
            await skale.send_payout(
                to="0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
                amount="1",
                token="btc",
                idempotency_key="k",
            )
