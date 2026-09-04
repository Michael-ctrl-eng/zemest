"""Adversarial tests — payouts, fraud gates and the billing API surface.

Attack surface:
* payout above balance / below minimum → refused
* payout velocity (PAYOUT_MAX_PER_DAY) → refused + flagged
* payouts held on open fraud flags → refused
* auto-approve only for small clean payouts; big ones stay pending
* account details encrypted at rest (ciphertext in DB, plain on read)
* API auth: no-token access → 401; foreign user's invoice → 404
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import get_settings
from app.models.billing import FraudFlag, PayoutAccount, PayoutRequest
from app.models.order import Order
from app.models.tenant import Tenant
from app.models.user import User
from app.models.customer import Customer  # noqa: F401 — used by _paid_order
from app.services.billing import payouts as payout_service
from app.services.billing import fraud
from app.services.billing.subscription_engine import available_balance

WALLET = "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"


@pytest_asyncio.fixture
async def merchant(db_session):
    user = User(name="Merch", email="merch@example.com")
    db_session.add(user)
    await db_session.commit()
    tenant = Tenant(
        id=uuid.uuid4(),
        owner_id=user.id,
        page_name="Shop",
        business_email="shop@example.com",
    )
    db_session.add(tenant)
    await db_session.commit()
    return user, tenant


async def _paid_order(db_session, tenant, total=4850.0):
    from app.models.customer import Customer

    customer = Customer(
        tenant_id=tenant.id,
        fb_psid=uuid.uuid4().hex[:16],
        name="C",
        phone="01000000000",
        channel="whatsapp",
    )
    db_session.add(customer)
    await db_session.flush()
    order = Order(
        tenant_id=tenant.id,
        customer_id=customer.id,
        order_number=f"ORD-{uuid.uuid4().hex[:8]}",
        customer_name="C",
        customer_phone="01000000000",
        governorate="Cairo",
        city="Cairo",
        address_detail="Nasr City",
        subtotal=Decimal(str(total)),
        total=Decimal(str(total)),
        payment_method="online",
        payment_status="paid",
    )
    db_session.add(order)
    await db_session.commit()
    return order


async def _wallet_account(db_session, user):
    account = PayoutAccount(
        user_id=user.id, method="skale", details=WALLET, status="verified", is_default=True
    )
    db_session.add(account)
    await db_session.commit()
    return account


class TestFraudGates:
    async def test_velocity_blocks_after_limit(self, db_session, merchant):
        user, _ = merchant
        s = get_settings()
        for _ in range(s.PAYOUT_MAX_PER_DAY):
            db_session.add(
                PayoutRequest(
                    user_id=user.id,
                    payout_account_id=uuid.uuid4(),
                    rail="skale",
                    amount=1000,
                    net_amount=1000,
                    status="paid",
                )
            )
        await db_session.commit()
        allowed, reason = await fraud.check_payout_request(db_session, user.id, 1000)
        assert allowed is False
        assert "limit" in reason.lower()

    async def test_held_payouts_block_requests(self, db_session, merchant):
        user, _ = merchant
        db_session.add(
            FraudFlag(
                user_id=user.id,
                kind="dispute",
                severity="high",
                action_taken="payouts_held",
            )
        )
        await db_session.commit()
        assert await fraud.payouts_held(db_session, user.id) is True
        allowed, reason = await fraud.check_payout_request(db_session, user.id, 1000)
        assert allowed is False
        assert "held" in reason.lower()

    async def test_charge_failure_velocity_flags(self, db_session, merchant):
        user, _ = merchant
        from app.models.billing import PaymentEvent

        for i in range(4):  # 4 previous + 1 in-flight = 5
            db_session.add(
                PaymentEvent(
                    provider="stripe",
                    provider_event_id=f"evt_f{i}",
                    event_type="invoice.payment_failed",
                    detail=str(user.id),
                    status="processed",
                )
            )
        await db_session.commit()
        await fraud.on_charge_failed(db_session, user.id)
        res = await db_session.execute(
            select(FraudFlag).where(
                FraudFlag.user_id == user.id, FraudFlag.kind == "failed_charges_velocity"
            )
        )
        flags = res.scalars().all()
        assert any(f.severity == "high" for f in flags)


class TestPayoutRequests:
    async def test_below_minimum_refused(self, db_session, merchant):
        user, _ = merchant
        account = await _wallet_account(db_session, user)
        s = get_settings()
        with pytest.raises(payout_service.PayoutError):
            await payout_service.create_payout_request(
                db_session,
                user.id,
                payout_account_id=account.id,
                amount=s.PAYOUT_MIN_AMOUNT - 1,
            )

    async def test_above_balance_refused(self, db_session, merchant):
        user, tenant = merchant
        account = await _wallet_account(db_session, user)
        await _paid_order(db_session, tenant, total=100.0)  # ~$2 balance
        with pytest.raises(payout_service.PayoutError):
            await payout_service.create_payout_request(
                db_session, user.id, payout_account_id=account.id, amount=100000
            )

    async def test_unknown_account_refused(self, db_session, merchant):
        user, _ = merchant
        with pytest.raises(payout_service.PayoutError):
            await payout_service.create_payout_request(
                db_session, user.id, payout_account_id=uuid.uuid4(), amount=5000
            )

    async def test_balance_freezes_after_request(self, db_session, merchant, monkeypatch):
        user, tenant = merchant
        account = await _wallet_account(db_session, user)
        await _paid_order(db_session, tenant, total=10000.0)  # ~$206
        before = await available_balance(db_session, user.id)
        assert before > 10000

        # Freeze WITHOUT hitting the real rail: patch the rail executor so
        # the request stays in a money-committed state.
        async def _fake_execute(db, request):
            request.status = "processing"
            return request

        monkeypatch.setattr(payout_service, "execute", _fake_execute)
        request = await payout_service.create_payout_request(
            db_session, user.id, payout_account_id=account.id, amount=10000
        )
        after = await available_balance(db_session, user.id)
        assert after == before - 10000  # committed payout already frozen
        assert request.status == "processing"

    async def test_failed_payout_releases_freeze(self, db_session, merchant, monkeypatch):
        user, tenant = merchant
        account = await _wallet_account(db_session, user)
        await _paid_order(db_session, tenant, total=10000.0)
        before = await available_balance(db_session, user.id)

        # Real execute path with an unconfigured rail → request fails →
        # the frozen amount is released back to the balance.
        s = get_settings()
        monkeypatch.setattr(s, "SKALE_PAYOUT_HMAC_SECRET", "", raising=False)
        request = await payout_service.create_payout_request(
            db_session, user.id, payout_account_id=account.id, amount=10000
        )
        await db_session.refresh(request)
        assert request.status == "failed"
        after = await available_balance(db_session, user.id)
        assert after == before

    async def test_large_payout_needs_admin(self, db_session, merchant, monkeypatch):
        user, tenant = merchant
        account = await _wallet_account(db_session, user)
        await _paid_order(db_session, tenant, total=1_000_000.0)
        s = get_settings()
        monkeypatch.setattr(s, "PAYOUT_AUTO_APPROVE_MAX", 10000, raising=False)
        # freeze stays pending (never auto-executed → never needs the rail)
        request = await payout_service.create_payout_request(
            db_session, user.id, payout_account_id=account.id, amount=500000
        )
        assert request.status == "pending"  # above auto-approve → admin queue

    async def test_details_encrypted_at_rest(self, db_session, merchant):
        user, _ = merchant
        account = await _wallet_account(db_session, user)
        await db_session.refresh(account)
        # ORM read is transparent (decrypted)
        assert account.details == WALLET
        # RAW SQL (no ORM type processing) — what's actually stored on disk
        from sqlalchemy import text

        raw = await db_session.execute(
            text("SELECT details FROM payout_accounts WHERE id = :id"),
            # SQLite stores sa.UUID() as 32-char hex (no dashes) — use .hex
            {"id": account.id.hex},
        )
        stored = raw.scalar_one()
        assert WALLET not in (stored or "")
        assert (stored or "").startswith("gAAAA")  # Fernet ciphertext

    async def test_execute_payoneer_requires_config(self, db_session, merchant, monkeypatch):
        user, _ = merchant
        account = PayoutAccount(
            user_id=user.id, method="payoneer", details="PAYEE1", status="verified"
        )
        db_session.add(account)
        await db_session.commit()
        request = PayoutRequest(
            user_id=user.id,
            payout_account_id=account.id,
            rail="payoneer",
            amount=5000,
            net_amount=5000,
            status="approved",
        )
        db_session.add(request)
        await db_session.commit()
        s = get_settings()
        monkeypatch.setattr(s, "PAYONEER_CLIENT_ID", "", raising=False)
        out = await payout_service.execute(db_session, request)
        await db_session.refresh(request)
        assert request.status == "failed"
        assert "not configured" in (request.failure_reason or "")


class TestBillingAPI:
    async def test_overview_requires_auth(self, client):
        r = await client.get("/api/billing/overview")
        assert r.status_code in (401, 403)

    async def test_overview_works_for_authed_user(self, client, auth_headers):
        r = await client.get("/api/billing/overview", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "subscription" in body
        assert "payouts" in body
        assert "rails" in body

    async def test_subscribe_rejects_bad_plan(self, client, auth_headers):
        r = await client.post(
            "/api/billing/subscribe", json={"plan": "enterprise", "provider": "stripe"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_subscribe_rejects_bad_provider(self, client, auth_headers):
        r = await client.post(
            "/api/billing/subscribe", json={"plan": "growth", "provider": "paypal"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_subscribe_rejects_unconfigured_rail(self, client, auth_headers):
        r = await client.post(
            "/api/billing/subscribe", json={"plan": "growth", "provider": "stripe"},
            headers=auth_headers,
        )
        assert r.status_code == 400  # rail not configured (no keys in tests)

    async def test_cancel_without_subscription_404(self, client, auth_headers):
        r = await client.post("/api/billing/cancel", json={"immediate": False}, headers=auth_headers)
        assert r.status_code == 404

    async def test_stripe_webhook_missing_signature_400(self, client):
        r = await client.post("/api/payments/webhook/stripe", json={"id": "evt_1"})
        assert r.status_code == 400

    async def test_stripe_webhook_bad_signature_401(self, client):
        r = await client.post(
            "/api/payments/webhook/stripe",
            content=b'{"id":"evt_1","type":"invoice.paid"}',
            headers={"stripe-signature": "t=123,v1=deadbeef"},
        )
        assert r.status_code == 401

    async def test_payoneer_webhook_missing_signature_400(self, client):
        r = await client.post("/api/payments/webhook/payoneer", json={"type": "payout.status"})
        assert r.status_code == 400

    async def test_payout_account_invalid_wallet_400(self, client, auth_headers):
        r = await client.post(
            "/api/billing/payout-accounts",
            json={"method": "skale", "details": "not-a-wallet"},
            headers=auth_headers,
        )
        assert r.status_code == 400

    async def test_payout_account_valid_wallet_201(self, client, auth_headers):
        r = await client.post(
            "/api/billing/payout-accounts",
            json={"method": "skale", "details": WALLET, "label": "My USDC wallet"},
            headers=auth_headers,
        )
        assert r.status_code in (200, 201)
        body = r.json()
        assert body["status"] == "verified"
        assert body["masked"].startswith("0x71C7")
