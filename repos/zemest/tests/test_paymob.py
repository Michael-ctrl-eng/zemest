"""Tests for the Paymob payments integration (analysis/G1-payments.md).

Conventions:
* No real HTTP — the module-level httpx.AsyncClient in
  ``app/services/payments/paymob.py`` is monkeypatched with a fake.
* No real keys — every key/secret below is a throwaway test value.
* HMAC expected values are computed with an INDEPENDENT hand-built
  concatenation (hard-coded G1 field order), so the tests are not
  tautological with the app implementation.
"""
import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio

from app.config import get_settings
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.tenant import Tenant
from app.models.user import User
from app.services.payments import (
    PaymobApiError,
    PaymobClient,
    PaymobConfigError,
    build_intention_payload,
    to_piasters,
    verify_subscription_hmac,
    verify_token_hmac,
    verify_transaction_hmac,
)
from app.services.payments import paymob as paymob_mod
from app.utils.security import hash_password

TEST_SECRET = "test-hmac-secret-not-real"
TEST_API_KEY = "sk-test-fake-not-real"
TEST_INTEGRATION_IDS = "12345,6789"


# ---------------------------------------------------------------------------
# Helpers — independent implementation of the G1 HMAC field orders
# ---------------------------------------------------------------------------
def _txn_obj(**overrides) -> dict:
    """A realistic Paymob transaction callback object (20 HMAC fields)."""
    obj = {
        "amount_cents": 100000,
        "created_at": "2026-02-01T12:34:56.789012",
        "currency": "EGP",
        "error_occured": False,
        "has_parent_transaction": False,
        "id": 555001,
        "integration_id": 12345,
        "is_3d_secure": True,
        "is_auth": False,
        "is_capture": False,
        "is_refunded": False,
        "is_standalone_payment": True,
        "is_voided": False,
        "order": {"id": 777001, "merchant_order_id": "zst-unknown"},
        "owner": 42,
        "pending": False,
        "source_data": {"pan": "1234", "sub_type": "MasterCard", "type": "card"},
        "success": True,
    }
    obj.update(overrides)
    return obj


def _b(v) -> str:
    return "true" if v else "false"


def _sha512_hex(message: str, secret: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha512).hexdigest()


def _expected_txn_hmac(obj: dict, secret: str = TEST_SECRET) -> str:
    """HMAC-SHA512 over the EXACT 20-field order from G1-payments.md §3."""
    msg = (
        f"{obj['amount_cents']}"
        f"{obj['created_at']}"
        f"{obj['currency']}"
        f"{_b(obj['error_occured'])}"
        f"{_b(obj['has_parent_transaction'])}"
        f"{obj['id']}"
        f"{obj['integration_id']}"
        f"{_b(obj['is_3d_secure'])}"
        f"{_b(obj['is_auth'])}"
        f"{_b(obj['is_capture'])}"
        f"{_b(obj['is_refunded'])}"
        f"{_b(obj['is_standalone_payment'])}"
        f"{_b(obj['is_voided'])}"
        f"{obj['order']['id']}"
        f"{obj['owner']}"
        f"{_b(obj['pending'])}"
        f"{obj['source_data']['pan']}"
        f"{obj['source_data']['sub_type']}"
        f"{obj['source_data']['type']}"
        f"{_b(obj['success'])}"
    )
    return _sha512_hex(msg, secret)


def _order_ref(order) -> str:
    return f"zst-{order.id}"


# ---------------------------------------------------------------------------
# Fake module-level httpx client (monkeypatched in place — no real HTTP)
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    """Stand-in for the module-level httpx.AsyncClient in paymob.py."""

    def __init__(self, response: _FakeResponse | None = None):
        self.response = response or _FakeResponse(
            payload={"id": 987, "client_secret": "cs-test-fake"}
        )
        self.calls: list[dict] = []

    @property
    def is_closed(self) -> bool:
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self.response


@pytest.fixture
def fake_paymob(monkeypatch):
    fake = _FakeAsyncClient()
    monkeypatch.setattr(paymob_mod, "_client", fake)
    return fake


@pytest.fixture
def paymob_settings(monkeypatch):
    """Point the cached Settings instance at throwaway test credentials."""
    s = get_settings()
    monkeypatch.setattr(s, "PAYMOB_API_KEY", TEST_API_KEY)
    monkeypatch.setattr(s, "PAYMOB_INTEGRATION_IDS", TEST_INTEGRATION_IDS)
    monkeypatch.setattr(s, "PAYMOB_WEBHOOK_HMAC_SECRET", TEST_SECRET)
    # F4: notification URLs are pinned to the configured public origin —
    # never derived from the request Host header.
    monkeypatch.setattr(s, "PUBLIC_BASE_URL", "https://public.zemest.test")
    return s


# ---------------------------------------------------------------------------
# HMAC-SHA512 verification (pure unit tests)
# ---------------------------------------------------------------------------
class TestHmacVerification:

    def test_transaction_correct_signature_passes(self):
        obj = _txn_obj()
        assert verify_transaction_hmac(obj, _expected_txn_hmac(obj), TEST_SECRET) is True

    def test_transaction_tampered_body_rejected(self):
        obj = _txn_obj()
        sig = _expected_txn_hmac(obj)
        obj["amount_cents"] = obj["amount_cents"] + 1  # tamper AFTER signing
        assert verify_transaction_hmac(obj, sig, TEST_SECRET) is False

    def test_transaction_wrong_secret_rejected(self):
        obj = _txn_obj()
        sig = _expected_txn_hmac(obj, secret="attacker-secret-not-real")
        assert verify_transaction_hmac(obj, sig, TEST_SECRET) is False

    def test_missing_signature_or_secret_fails_closed(self):
        obj = _txn_obj()
        assert verify_transaction_hmac(obj, "", TEST_SECRET) is False
        assert verify_transaction_hmac(obj, _expected_txn_hmac(obj), "") is False

    def test_none_and_missing_fields_render_as_empty_string(self):
        obj = _txn_obj()
        obj["integration_id"] = None
        del obj["owner"]
        # expected message: same 20-field order, None/missing → ""
        msg = (
            f"{obj['amount_cents']}{obj['created_at']}{obj['currency']}"
            f"{_b(obj['error_occured'])}{_b(obj['has_parent_transaction'])}"
            f"{obj['id']}"
            ""  # integration_id = None → ""
            f"{_b(obj['is_3d_secure'])}{_b(obj['is_auth'])}{_b(obj['is_capture'])}"
            f"{_b(obj['is_refunded'])}{_b(obj['is_standalone_payment'])}"
            f"{_b(obj['is_voided'])}"
            f"{obj['order']['id']}"
            ""  # owner missing → ""
            f"{_b(obj['pending'])}{obj['source_data']['pan']}"
            f"{obj['source_data']['sub_type']}{obj['source_data']['type']}"
            f"{_b(obj['success'])}"
        )
        assert verify_transaction_hmac(obj, _sha512_hex(msg, TEST_SECRET), TEST_SECRET) is True

    def test_card_token_correct_signature_passes(self):
        token_obj = {
            "card_subtype": "MasterCard",
            "created_at": "2026-02-01T12:00:00.000000",
            "email": "ahmed@example.com",
            "id": 9001,
            "masked_pan": "1234",
            "merchant_id": 42,
            "order_id": 777001,
            "token": "tok-test-fake",
        }
        msg = (
            f"{token_obj['card_subtype']}{token_obj['created_at']}{token_obj['email']}"
            f"{token_obj['id']}{token_obj['masked_pan']}{token_obj['merchant_id']}"
            f"{token_obj['order_id']}{token_obj['token']}"
        )
        sig = _sha512_hex(msg, TEST_SECRET)
        assert verify_token_hmac(token_obj, sig, TEST_SECRET) is True
        # tampered
        token_obj["token"] = "tok-tampered"
        assert verify_token_hmac(token_obj, sig, TEST_SECRET) is False

    def test_subscription_message_is_trigger_type_for_id(self):
        sub_obj = {"trigger_type": "charge", "subscription_data": {"id": 321}}
        sig = _sha512_hex("chargefor321", TEST_SECRET)
        assert verify_subscription_hmac(sub_obj, sig, TEST_SECRET) is True
        assert verify_subscription_hmac(sub_obj, _sha512_hex("refundfor321", TEST_SECRET), TEST_SECRET) is False


# ---------------------------------------------------------------------------
# Piaster math + intention payload builder (pure unit tests)
# ---------------------------------------------------------------------------
class TestPiasterMath:

    def test_1850_egp_to_piasters(self):
        assert to_piasters(Decimal("1850.00")) == 185000

    def test_float_int_and_str_inputs(self):
        assert to_piasters(1850.0) == 185000
        assert to_piasters(1500) == 150000
        assert to_piasters("1850.00") == 185000
        assert to_piasters(Decimal("59.99")) == 5999

    def test_returns_int_not_float(self):
        assert isinstance(to_piasters(Decimal("1850.00")), int)

    def test_garbage_input_raises(self):
        with pytest.raises(ValueError):
            to_piasters("not-a-number")


class TestIntentionPayload:

    def test_piaster_math_in_payload(self):
        payload = build_intention_payload(
            amount_egp=Decimal("1850.00"),
            billing_data={"first_name": "Ahmed", "phone_number": "01012345678"},
            merchant_order_id="zst-abc-123",
            payment_methods=[12345],
        )
        assert payload["amount"] == 185000
        assert isinstance(payload["amount"], int)

    def test_payload_shape(self):
        payload = build_intention_payload(
            amount_egp=1850.00,
            billing_data={"first_name": "Ahmed", "phone_number": "01012345678"},
            merchant_order_id="zst-abc-123",
            payment_methods=[12345, 6789],
            items=[{"name": "Galabiya", "amount": 185000, "quantity": 1}],
            notification_url="https://app.example.com/api/payments/webhook",
            redirection_url="https://app.example.com/thanks",
        )
        assert payload["currency"] == "EGP"
        assert payload["billing_data"]["first_name"] == "Ahmed"
        assert payload["billing_data"]["phone_number"] == "01012345678"
        # merchant_order_id travels as special_reference (Paymob echoes it
        # back as order.merchant_order_id on webhooks)
        assert payload["special_reference"] == "zst-abc-123"
        assert payload["payment_methods"] == [12345, 6789]
        assert payload["notification_url"] == "https://app.example.com/api/payments/webhook"
        assert payload["redirection_url"] == "https://app.example.com/thanks"
        assert payload["items"][0]["amount"] == 185000

    def test_empty_optionals_are_omitted(self):
        payload = build_intention_payload(
            amount_egp=100,
            billing_data={"first_name": "A"},
            merchant_order_id="zst-1",
        )
        assert "items" not in payload
        assert "notification_url" not in payload
        assert "redirection_url" not in payload


# ---------------------------------------------------------------------------
# PaymobClient.create_intention (module-level client monkeypatched)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestCreateIntention:

    async def test_sends_piasters_and_token_auth(self, paymob_settings, fake_paymob):
        client = PaymobClient()
        result = await client.create_intention(
            amount_egp=Decimal("1850.00"),
            billing_data={"first_name": "Ahmed", "phone_number": "01012345678"},
            merchant_order_id="zst-abc-123",
        )
        call = fake_paymob.calls[0]
        assert call["url"] == "https://egypt.paymob.com/v1/intention/"
        assert call["headers"]["Authorization"] == f"Token {TEST_API_KEY}"
        assert call["json"]["amount"] == 185000
        assert call["json"]["special_reference"] == "zst-abc-123"
        assert call["json"]["payment_methods"] == [12345, 6789]
        assert result["intention_id"] == "987"
        assert result["client_secret"] == "cs-test-fake"

    async def test_builds_checkout_url_from_public_key(self, paymob_settings, fake_paymob):
        client = PaymobClient()
        result = await client.create_intention(
            amount_egp=100,
            billing_data={"first_name": "A"},
            merchant_order_id="zst-1",
            public_key="pk-test-fake",
        )
        assert "publicKey=pk-test-fake" in result["payment_url"]
        assert "clientSecret=cs-test-fake" in result["payment_url"]
        assert result["payment_url"].startswith("https://egypt.paymob.com/unifiedcheckout/")

    async def test_api_error_raises(self, paymob_settings, fake_paymob):
        fake_paymob.response = _FakeResponse(status_code=401, payload={"detail": "bad key"})
        client = PaymobClient()
        with pytest.raises(PaymobApiError):
            await client.create_intention(
                amount_egp=100, billing_data={"first_name": "A"}, merchant_order_id="zst-1"
            )

    async def test_missing_api_key_is_a_config_error(self):
        client = PaymobClient(api_key="", integration_ids=[1])
        with pytest.raises(PaymobConfigError):
            await client.create_intention(
                amount_egp=100, billing_data={"first_name": "A"}, merchant_order_id="zst-1"
            )

    async def test_missing_integration_ids_is_a_config_error(self):
        client = PaymobClient(api_key="sk-x", integration_ids="")
        with pytest.raises(PaymobConfigError):
            await client.create_intention(
                amount_egp=100, billing_data={"first_name": "A"}, merchant_order_id="zst-1"
            )


# ---------------------------------------------------------------------------
# POST /api/payments/webhook (integration — HMAC before any processing)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestWebhookEndpoint:

    async def test_valid_webhook_flips_deposit_paid(
        self, client, paymob_settings, test_order, db_session
    ):
        obj = _txn_obj(order={"id": 777001, "merchant_order_id": _order_ref(test_order)})
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        await db_session.refresh(test_order)
        assert test_order.payment_status == "deposit_paid"
        assert str(test_order.paymob_transaction_id) == "555001"

    async def test_full_order_amount_marks_paid(
        self, client, paymob_settings, test_order, db_session
    ):
        obj = _txn_obj(
            amount_cents=to_piasters(test_order.total),  # 1260.00 EGP → 126000
            order={"id": 777001, "merchant_order_id": _order_ref(test_order)},
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status == "paid"

    async def test_same_obj_id_twice_single_transition(
        self, client, paymob_settings, test_order, db_session
    ):
        obj = _txn_obj(order={"id": 777001, "merchant_order_id": _order_ref(test_order)})
        body = {"type": "TRANSACTION", "obj": obj}
        sig = _expected_txn_hmac(obj)
        r1 = await client.post(f"/api/payments/webhook?hmac={sig}", json=body)
        r2 = await client.post(f"/api/payments/webhook?hmac={sig}", json=body)
        assert r1.status_code == 200
        assert r2.status_code == 200  # redelivery still 2xx — no retries
        await db_session.refresh(test_order)
        assert test_order.payment_status == "deposit_paid"
        assert str(test_order.paymob_transaction_id) == "555001"

        # a *different* transaction (new obj.id, failed) must NOT regress it
        obj2 = _txn_obj(
            id=555002,
            success=False,
            order={"id": 777001, "merchant_order_id": _order_ref(test_order)},
        )
        r3 = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj2)}",
            json={"type": "TRANSACTION", "obj": obj2},
        )
        assert r3.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status == "deposit_paid"  # never regresses
        assert str(test_order.paymob_transaction_id) == "555001"

    async def test_tampered_body_rejected_before_processing(
        self, client, paymob_settings, test_order, db_session
    ):
        obj = _txn_obj(order={"id": 777001, "merchant_order_id": _order_ref(test_order)})
        sig = _expected_txn_hmac(obj)
        obj["amount_cents"] = 999999  # tamper AFTER signing
        resp = await client.post(
            f"/api/payments/webhook?hmac={sig}", json={"type": "TRANSACTION", "obj": obj}
        )
        assert resp.status_code == 401
        await db_session.refresh(test_order)
        assert test_order.payment_status is None
        assert test_order.paymob_transaction_id is None

    async def test_wrong_secret_rejected(self, client, paymob_settings, test_order):
        obj = _txn_obj(order={"id": 777001, "merchant_order_id": _order_ref(test_order)})
        sig = _expected_txn_hmac(obj, secret="attacker-secret-not-real")
        resp = await client.post(
            f"/api/payments/webhook?hmac={sig}", json={"type": "TRANSACTION", "obj": obj}
        )
        assert resp.status_code == 401

    async def test_missing_hmac_rejected(self, client, paymob_settings, test_order):
        obj = _txn_obj(order={"id": 777001, "merchant_order_id": _order_ref(test_order)})
        resp = await client.post("/api/payments/webhook", json={"type": "TRANSACTION", "obj": obj})
        assert resp.status_code == 400

    async def test_malformed_body_rejected(self, client, paymob_settings):
        resp = await client.post("/api/payments/webhook?hmac=abc", content=b"not-json{{")
        assert resp.status_code == 400

    async def test_secret_not_configured_fails_closed(
        self, client, monkeypatch, test_order
    ):
        s = get_settings()
        monkeypatch.setattr(s, "PAYMOB_WEBHOOK_HMAC_SECRET", "")
        obj = _txn_obj(order={"id": 777001, "merchant_order_id": _order_ref(test_order)})
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 401

    async def test_failed_transaction_marks_failed(
        self, client, paymob_settings, test_order, db_session
    ):
        obj = _txn_obj(
            success=False,
            order={"id": 777001, "merchant_order_id": _order_ref(test_order)},
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status == "failed"

    async def test_pending_transaction_ignored(
        self, client, paymob_settings, test_order, db_session
    ):
        obj = _txn_obj(
            pending=True,
            order={"id": 777001, "merchant_order_id": _order_ref(test_order)},
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status is None

    async def test_unknown_order_reference_returns_200(
        self, client, paymob_settings, test_order, db_session
    ):
        obj = _txn_obj(order={"id": 777001, "merchant_order_id": f"zst-{uuid.uuid4()}"})
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status is None

    async def test_legacy_body_without_obj_wrapper(
        self, client, paymob_settings, test_order, db_session
    ):
        obj = _txn_obj(order={"id": 777001, "merchant_order_id": _order_ref(test_order)})
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}", json=obj
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status == "deposit_paid"

    async def test_card_token_event_accepted_no_state_change(
        self, client, paymob_settings, test_order, db_session
    ):
        token_obj = {
            "card_subtype": "MasterCard",
            "created_at": "2026-02-01T12:00:00.000000",
            "email": "ahmed@example.com",
            "id": 9001,
            "masked_pan": "1234",
            "merchant_id": 42,
            "order_id": 777001,
            "token": "tok-test-fake",
        }
        msg = (
            f"{token_obj['card_subtype']}{token_obj['created_at']}{token_obj['email']}"
            f"{token_obj['id']}{token_obj['masked_pan']}{token_obj['merchant_id']}"
            f"{token_obj['order_id']}{token_obj['token']}"
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_sha512_hex(msg, TEST_SECRET)}",
            json={"type": "CARD_TOKEN", "obj": token_obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status is None

    async def test_subscription_event_hmac_in_body(self, client, paymob_settings):
        sub_obj = {"trigger_type": "charge", "subscription_data": {"id": 321}}
        body = {
            "type": "SUBSCRIPTION",
            "obj": sub_obj,
            "hmac": _sha512_hex("chargefor321", TEST_SECRET),
        }
        resp = await client.post("/api/payments/webhook", json=body)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/payments/intention (authenticated)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestIntentionEndpoint:

    async def test_create_intention_for_own_order(
        self, client, auth_headers, paymob_settings, fake_paymob, test_order, db_session
    ):
        resp = await client.post(
            "/api/payments/intention",
            json={
                "order_id": str(test_order.id),
                "deposit_amount": 300.00,
                "public_key": "pk-test-fake",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount_piasters"] == 30000
        assert data["special_reference"] == _order_ref(test_order)
        assert data["payment_status"] == "pending_deposit"
        assert data["intention_id"] == "987"
        assert data["client_secret"] == "cs-test-fake"
        assert "publicKey=pk-test-fake" in data["payment_url"]
        assert "clientSecret=cs-test-fake" in data["payment_url"]

        # exactly one call to Paymob with the documented payload
        assert len(fake_paymob.calls) == 1
        call = fake_paymob.calls[0]
        assert call["url"] == "https://egypt.paymob.com/v1/intention/"
        assert call["headers"]["Authorization"] == f"Token {TEST_API_KEY}"
        body = call["json"]
        assert body["amount"] == 30000
        assert isinstance(body["amount"], int)
        assert body["currency"] == "EGP"
        assert body["special_reference"] == _order_ref(test_order)
        assert body["payment_methods"] == [12345, 6789]
        assert body["billing_data"]["first_name"] == "Ahmed"
        assert body["billing_data"]["phone_number"] == "01012345678"
        assert body["notification_url"].endswith("/api/payments/webhook")
        assert body["items"][0]["amount"] == 120000  # unit_price in piasters

        # deposit intent persisted on the order
        await db_session.refresh(test_order)
        assert test_order.payment_status == "pending_deposit"
        assert test_order.deposit_amount == Decimal("300.00")
        assert str(test_order.paymob_intention_id) == "987"

    async def test_intention_then_webhook_completes_deposit_flow(
        self, client, auth_headers, paymob_settings, fake_paymob, test_order, db_session
    ):
        """Deposit-to-confirm: intention → buyer pays → webhook flips state."""
        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(test_order.id), "deposit_amount": 300.00},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        obj = _txn_obj(
            amount_cents=30000,
            order={"id": 777001, "merchant_order_id": _order_ref(test_order)},
        )
        resp = await client.post(
            f"/api/payments/webhook?hmac={_expected_txn_hmac(obj)}",
            json={"type": "TRANSACTION", "obj": obj},
        )
        assert resp.status_code == 200
        await db_session.refresh(test_order)
        assert test_order.payment_status == "deposit_paid"  # COD still pending

    async def test_unknown_order_404(self, client, auth_headers, paymob_settings, fake_paymob):
        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(uuid.uuid4()), "deposit_amount": 100},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert fake_paymob.calls == []  # never called the gateway

    async def test_other_tenants_order_404(
        self, client, auth_headers, paymob_settings, fake_paymob, db_session
    ):
        other_user = User(
            id=uuid.uuid4(),
            name="Other Owner",
            email="other-owner@example.com",
            hashed_password=hash_password("otherpass123"),
        )
        other_tenant = Tenant(
            id=uuid.uuid4(),
            owner_id=other_user.id,
            page_name="Other Store",
            fb_page_id="other_page_123",
            website_url="https://otherstore.com",
            business_email="owner@otherstore.com",
            business_phone="01098765432",
            notification_pref="email",
        )
        other_customer = Customer(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            fb_psid="other_psid_123",
            name="Mona",
            phone="01098765432",
        )
        other_order = Order(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            customer_id=other_customer.id,
            order_number="ORD-260317-999",
            customer_name="Mona",
            customer_phone="01098765432",
            governorate="giza",
            city="Giza",
            address_detail="1 Street, Giza",
            payment_method="cod",
            subtotal=Decimal("100.00"),
            delivery_charge=Decimal("60.00"),
            total=Decimal("160.00"),
            status="pending",
        )
        db_session.add_all([other_user, other_tenant, other_customer, other_order])
        await db_session.commit()

        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(other_order.id), "deposit_amount": 50},
            headers=auth_headers,  # belongs to the FIRST user
        )
        assert resp.status_code == 404
        assert fake_paymob.calls == []

    async def test_unauthenticated_401(self, client, paymob_settings, fake_paymob, test_order):
        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(test_order.id), "deposit_amount": 100},
        )
        assert resp.status_code == 401
        assert fake_paymob.calls == []

    async def test_deposit_exceeding_total_400(
        self, client, auth_headers, paymob_settings, fake_paymob, test_order
    ):
        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(test_order.id), "deposit_amount": 99999.00},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert fake_paymob.calls == []

    async def test_not_configured_400(
        self, client, auth_headers, monkeypatch, fake_paymob, test_order
    ):
        s = get_settings()
        monkeypatch.setattr(s, "PAYMOB_API_KEY", "")
        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(test_order.id), "deposit_amount": 100},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "not configured" in resp.json()["detail"]

    async def test_gateway_error_maps_to_502(
        self, client, auth_headers, paymob_settings, fake_paymob, test_order
    ):
        fake_paymob.response = _FakeResponse(status_code=401, payload={"detail": "bad key"})
        resp = await client.post(
            "/api/payments/intention",
            json={"order_id": str(test_order.id), "deposit_amount": 100},
            headers=auth_headers,
        )
        assert resp.status_code == 502
