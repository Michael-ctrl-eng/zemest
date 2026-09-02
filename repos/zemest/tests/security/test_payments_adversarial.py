"""Adversarial payment tests — one test per audit PoC (wave F4).

Audit sources: findings/A7-services.md (M2, M11, M3),
findings/D5-payments-research.md (P0 fixes: intention state guard,
notification_url Host-header pin).

Every test encodes the auditor's attack scenario:
* M3/intention-state-guard: retry of /intention after payment must not
  downgrade paid -> pending_deposit (the "double-reset" PoC)
* M11: notification_url derived from Host header -> attacker webhook
* M2: non-EGP currency transaction compared as piasters
* M2: refund/void transitions were log-only
"""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio

from app.config import get_settings
from app.models.customer import Customer
from app.models.order import Order
from app.models.tenant import Tenant
from app.services.payments.paymob import to_piasters
from tests.test_paymob import (
    TEST_SECRET,
    _FakeAsyncClient,
    _expected_txn_hmac,
    _order_ref,
    _txn_obj,
)


@pytest.fixture
def fake_paymob(monkeypatch):
    from app.services.payments import paymob as paymob_mod
    fake = _FakeAsyncClient()
    monkeypatch.setattr(paymob_mod, "_client", fake)
    return fake


@pytest.fixture
def paymob_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "PAYMOB_API_KEY", "sk-test-fake-not-real")
    monkeypatch.setattr(s, "PAYMOB_INTEGRATION_IDS", "12345,6789")
    monkeypatch.setattr(s, "PAYMOB_WEBHOOK_HMAC_SECRET", TEST_SECRET)
    monkeypatch.setattr(s, "PUBLIC_BASE_URL", "https://public.zemest.test")
    return s


@pytest_asyncio.fixture
async def paid_order(db_session, test_tenant, test_customer):
    """An order already fully paid — the state that must never regress."""
    order = Order(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        customer_id=test_customer.id,
        order_number=f"ORD-ADV-{uuid.uuid4().hex[:6]}",
        customer_name="Paid",
        customer_phone="01012345678",
        governorate="cairo",
        city="Cairo",
        area="Maadi",
        address_detail="15 Road 9, Maadi",
        subtotal=Decimal("1000.00"),
        delivery_charge=Decimal("0"),
        total=Decimal("1000.00"),
        payment_status="paid",
        paymob_transaction_id="555001",
    )
    db_session.add(order)
    await db_session.commit()
    return order


@pytest_asyncio.fixture
async def deposit_paid_order(db_session, test_tenant, test_customer):
    order = Order(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        customer_id=test_customer.id,
        order_number=f"ORD-ADV2-{uuid.uuid4().hex[:6]}",
        customer_name="Deposit",
        customer_phone="01012345678",
        governorate="cairo",
        city="Cairo",
        area="Maadi",
        address_detail="15 Road 9, Maadi",
        subtotal=Decimal("1000.00"),
        delivery_charge=Decimal("0"),
        total=Decimal("1000.00"),
        payment_status="deposit_paid",
        paymob_transaction_id="555001",
    )
    db_session.add(order)
    await db_session.commit()
    return order


# --------------------------------------------------------------------------- #
# Intention state guard (audit: paid order reset to pending_deposit)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestIntentionStateGuard:
    async def test_paid_order_cannot_be_reset(
        self, client, paymob_settings, fake_paymob, paid_order, auth_headers, db_session
    ):
        """Auditor PoC: POST /intention on an already-paid order used to
        overwrite payment_status='paid' -> 'pending_deposit'. Must 409."""
        resp = await client.post("/api/payments/intention", json={
            "order_id": str(paid_order.id),
            "deposit_amount": 100.0,
        }, headers=auth_headers)
        assert resp.status_code == 409, (
            f"paid order was reset! status={resp.status_code}"
        )
        await db_session.refresh(paid_order)
        assert paid_order.payment_status == "paid"

    async def test_deposit_paid_order_cannot_be_reset(
        self, client, paymob_settings, fake_paymob, deposit_paid_order,
        auth_headers, db_session
    ):
        resp = await client.post("/api/payments/intention", json={
            "order_id": str(deposit_paid_order.id),
            "deposit_amount": 100.0,
        }, headers=auth_headers)
        assert resp.status_code == 409
        await db_session.refresh(deposit_paid_order)
        assert deposit_paid_order.payment_status == "deposit_paid"

    async def test_pending_order_still_creates_intention(
        self, client, paymob_settings, fake_paymob, test_order, auth_headers
    ):
        """Guard must not block the legitimate first intention."""
        resp = await client.post("/api/payments/intention", json={
            "order_id": str(test_order.id),
            "deposit_amount": 100.0,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert "intention_id" in resp.json()


# --------------------------------------------------------------------------- #
# Host header -> notification_url (audit M11)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestHostHeaderPin:
    async def test_notification_url_uses_configured_origin(
        self, client, paymob_settings, fake_paymob, test_order, auth_headers
    ):
        """The URL registered with Paymob must come from PUBLIC_BASE_URL,
        not from any Host header the caller sends."""
        evil_headers = {**auth_headers, "Host": "attacker.example"}
        resp = await client.post("/api/payments/intention", json={
            "order_id": str(test_order.id),
            "deposit_amount": 100.0,
        }, headers=evil_headers)
        assert resp.status_code == 200
        call = fake_paymob.calls[0]
        notification = call["json"].get("notification_url", "")
        assert "attacker.example" not in notification, (
            "Host header leaked into Paymob webhook registration!"
        )
        assert notification.startswith("https://public.zemest.test")

    async def test_missing_public_base_url_fails_closed(
        self, client, monkeypatch, fake_paymob, test_order, auth_headers
    ):
        """No PUBLIC_BASE_URL -> REFUSE to create intentions (400), never
        fall back to the request Host header."""
        s = get_settings()
        monkeypatch.setattr(s, "PUBLIC_BASE_URL", "")
        monkeypatch.setattr(s, "PAYMOB_API_KEY", "sk-test-fake-not-real")
        monkeypatch.setattr(s, "PAYMOB_INTEGRATION_IDS", "12345")
        resp = await client.post("/api/payments/intention", json={
            "order_id": str(test_order.id),
            "deposit_amount": 100.0,
        }, headers=auth_headers)
        assert resp.status_code == 400
        assert "PUBLIC_BASE_URL" in resp.json()["detail"]


# --------------------------------------------------------------------------- #
# Currency gate (audit M2)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestCurrencyGate:
    async def test_foreign_currency_no_state_change(
        self, client, paymob_settings, test_order, db_session
    ):
        """A USD transaction for the same amount_cents must NOT mark the
        order paid (it was compared as piasters before)."""
        obj = _txn_obj(
            currency="USD",
            amount_cents=100000,
            order={"id": 777001, "merchant_order_id": _order_ref(test_order)},
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200  # accepted, no retry
        await db_session.refresh(test_order)
        assert test_order.payment_status != "paid", (
            "foreign-currency transaction flipped the order to paid!"
        )

    async def test_egp_still_works(self, client, paymob_settings, test_order, db_session):
        obj = _txn_obj(
            currency="EGP",
            order={"id": 777001, "merchant_order_id": _order_ref(test_order)},
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status == "deposit_paid"


# --------------------------------------------------------------------------- #
# Refund / void transitions (audit M2: log-only before)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestRefundVoidTransitions:
    async def test_refund_transitions_paid_to_refunded(
        self, client, paymob_settings, paid_order, db_session
    ):
        obj = _txn_obj(
            is_refunded=True,
            order={"id": 777001, "merchant_order_id": _order_ref(paid_order)},
        )
        # _txn_obj defaults id=555001 which matches paid_order.tx 555001
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(paid_order)
        assert paid_order.payment_status == "refunded", (
            "refund webhook was log-only — merchant never sees the state change"
        )

    async def test_void_transitions_paid_to_voided(
        self, client, paymob_settings, paid_order, db_session
    ):
        obj = _txn_obj(
            is_voided=True,
            order={"id": 777001, "merchant_order_id": _order_ref(paid_order)},
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(paid_order)
        assert paid_order.payment_status == "voided"

    async def test_refund_on_unpaid_order_noop(
        self, client, paymob_settings, test_order, db_session
    ):
        """Refund for a never-paid order: accepted, no state damage."""
        from sqlalchemy import update
        await db_session.execute(
            update(Order).where(Order.id == test_order.id).values(
                payment_status="pending_deposit"
            )
        )
        await db_session.commit()
        obj = _txn_obj(
            is_refunded=True,
            id=555777,
            order={"id": 777001, "merchant_order_id": _order_ref(test_order)},
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status == "pending_deposit"
