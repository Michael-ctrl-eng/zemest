"""F4 payments adversarial tests — one PoC per audit finding.

Covers:
- A4-M1  Intention creation regressing a paid order to pending_deposit
- A4-M3  notification_url derived from the request Host header (hijack)
- A7-M2  Currency never checked before paid/deposit classification
- A7-M2  Refunds/voids log-only — paid orders never marked refunded
- A4-L4  1-piaster deposit "buys" order confirmation
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.config import get_settings
from app.models.order import Order
from app.models.tenant import Tenant

settings = get_settings()


async def _seed_order(db_session, test_tenant, payment_status=None, total="350.00"):
    from app.models.customer import Customer
    customer = Customer(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        fb_psid=f"psid-{uuid.uuid4().hex[:8]}",
        name="Ahmed",
        channel="messenger",
    )
    db_session.add(customer)
    await db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        customer_id=customer.id,
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:6]}",
        customer_name="Ahmed",
        customer_phone="01012345678",
        governorate="cairo",
        city="Cairo",
        address_detail="Street 1",
        payment_method="paymob",
        subtotal=Decimal("350.00"),
        delivery_charge=Decimal("35.00"),
        total=Decimal(total),
        status="confirmed",
        payment_status=payment_status,
    )
    db_session.add(order)
    await db_session.flush()
    return order


@pytest.mark.asyncio
class TestIntentionStateGuard:
    @pytest.mark.parametrize("paid_state", ["paid", "deposit_paid", "refunded", "voided"])
    async def test_paid_order_cannot_regress(self, client, db_session, auth_headers, test_tenant, paid_state):
        """A4-M1 PoC: creating a new intention on a paid order previously
        reset it to pending_deposit."""
        order = await _seed_order(db_session, test_tenant, payment_status=paid_state)

        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(order.id), "deposit_amount": 50.0},
            headers=auth_headers,
        )
        assert resp.status_code == 409, (
            f"{paid_state} order regressed to pending_deposit (A4-M1)"
        )
        await db_session.refresh(order)
        assert order.payment_status == paid_state

    async def test_unpaid_order_allowed(self, client, db_session, auth_headers, test_tenant):
        order = await _seed_order(db_session, test_tenant, payment_status="pending")

        fake_intention = {"intention_id": "int-123", "client_secret": "cs-1"}
        with patch(
            "app.api.payments.PaymobClient"
        ) as mock_client_cls:
            mock_client_cls.return_value = AsyncMock()
            mock_client_cls.return_value.create_intention = AsyncMock(
                return_value=fake_intention
            )
            resp = await client.post(
                "/api/payments/intention",
                json={"order_id": str(order.id), "deposit_amount": 50.0},
                headers=auth_headers,
            )
        assert resp.status_code == 200

    async def test_piaster_deposit_rejected(self, client, db_session, auth_headers, test_tenant):
        """A4-L4: a 1-piaster 'deposit' must not buy confirmation."""
        order = await _seed_order(db_session, test_tenant, payment_status="pending")
        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(order.id), "deposit_amount": 0.01},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_deposit_above_total_rejected(self, client, db_session, auth_headers, test_tenant):
        order = await _seed_order(db_session, test_tenant, payment_status="pending")
        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(order.id), "deposit_amount": 99999.0},
            headers=auth_headers,
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestHostHeaderHijack:
    async def test_notification_url_uses_public_base_url(
        self, client, db_session, auth_headers, test_tenant, monkeypatch
    ):
        """A4-M3 PoC: a poisoned Host header must NOT redirect Paymob
        callbacks to the attacker host when PUBLIC_BASE_URL is set."""
        monkeypatch.setattr(
            settings, "PUBLIC_BASE_URL", "https://zemest-real.example", raising=False
        )
        order = await _seed_order(db_session, test_tenant, payment_status="pending")

        captured = {}

        async def fake_create_intention(**kwargs):
            captured.update(kwargs)
            return {"intention_id": "int-1", "client_secret": "cs"}

        with patch("app.api.payments.PaymobClient") as mock_client_cls:
            mock_client_cls.return_value = AsyncMock()
            mock_client_cls.return_value.create_intention = AsyncMock(
                side_effect=fake_create_intention
            )
            resp = await client.post(
                "/api/payments/intention",
                json={"order_id": str(order.id), "deposit_amount": 50.0},
                headers={**auth_headers, "Host": "attacker-evil.example"},
            )
        assert resp.status_code == 200
        assert captured["notification_url"].startswith("https://zemest-real.example")
        assert "attacker-evil.example" not in captured["notification_url"], (
            "Host header hijack: Paymob callbacks redirected to attacker host"
        )


@pytest.mark.asyncio
class TestWebhookCurrencyAndRefund:
    async def _call_process(self, db_session, order, obj):
        from app.api.payments import _process_transaction
        await _process_transaction(db_session, obj)
        await db_session.refresh(order)
        return order.payment_status

    async def test_foreign_currency_no_state_change(self, db_session, test_tenant):
        """A7-M2: a USD transaction must not be classified as piasters."""
        order = await _seed_order(db_session, test_tenant, payment_status="pending")
        from app.api.payments import MERCHANT_REF_PREFIX
        ref = f"{MERCHANT_REF_PREFIX}{order.id}"

        status = await self._call_process(db_session, order, {
            "id": "TX-USD-1",
            "success": True,
            "amount_cents": 350000,  # would classify as "paid" if currency ignored
            "currency": "USD",
            "order": {"merchant_order_id": ref},
        })
        assert status == "pending", "foreign-currency transaction moved the state"

    async def test_refund_transitions_paid_order(self, db_session, test_tenant):
        """A7-M2: refunds were log-only — the merchant never saw the money
        come back. A paid order must transition to refunded exactly once."""
        order = await _seed_order(db_session, test_tenant, payment_status="paid")
        from app.api.payments import MERCHANT_REF_PREFIX
        ref = f"{MERCHANT_REF_PREFIX}{order.id}"

        status = await self._call_process(db_session, order, {
            "id": "TX-REF-1",
            "success": True,
            "is_refunded": True,
            "amount_cents": 350000,
            "currency": "EGP",
            "order": {"merchant_order_id": ref},
        })
        assert status == "refunded"

    async def test_refund_on_unpaid_order_noop(self, db_session, test_tenant):
        """A refund webhook for a pending order must not create phantom state."""
        order = await _seed_order(db_session, test_tenant, payment_status="pending")
        from app.api.payments import MERCHANT_REF_PREFIX
        ref = f"{MERCHANT_REF_PREFIX}{order.id}"

        status = await self._call_process(db_session, order, {
            "id": "TX-REF-2",
            "success": True,
            "is_refunded": True,
            "amount_cents": 350000,
            "currency": "EGP",
            "order": {"merchant_order_id": ref},
        })
        assert status == "pending"

    async def test_void_transitions_paid_order(self, db_session, test_tenant):
        order = await _seed_order(db_session, test_tenant, payment_status="paid")
        from app.api.payments import MERCHANT_REF_PREFIX
        ref = f"{MERCHANT_REF_PREFIX}{order.id}"

        status = await self._call_process(db_session, order, {
            "id": "TX-VOID-1",
            "success": True,
            "is_voided": True,
            "amount_cents": 350000,
            "currency": "EGP",
            "order": {"merchant_order_id": ref},
        })
        assert status == "voided"

    async def test_refund_idempotent(self, db_session, test_tenant):
        """A redelivered refund webhook never re-transitions."""
        order = await _seed_order(db_session, test_tenant, payment_status="paid")
        from app.api.payments import MERCHANT_REF_PREFIX
        ref = f"{MERCHANT_REF_PREFIX}{order.id}"
        obj = {
            "id": "TX-REF-3",
            "success": True,
            "is_refunded": True,
            "amount_cents": 350000,
            "currency": "EGP",
            "order": {"merchant_order_id": ref},
        }
        await self._call_process(db_session, order, obj)
        # Redelivery: same tx id, state already refunded — stays put.
        status = await self._call_process(db_session, order, obj)
        assert status == "refunded"
