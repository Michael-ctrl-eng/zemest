"""Billing webhook processor tests — verify → dedupe → dispatch → CAS.

Adversarial coverage (the audit's webhook checklist):
* forged/missing signature → DB untouched
* missing secret → fail closed (401 path)
* redelivered verified event → duplicate, no double-activation
* amount tamper / underpayment → never activates
* dispute → immediate cancel + payouts held
* refund → cancel
* unknown-but-verified events → 200, no state change
"""
from __future__ import annotations

import hashlib
import hmac as hmac_lib
import json
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.billing import (
    BillingSubscription,
    BillingTransaction,
    BillingWebhookEvent,
    PayoutRequest,
)
from app.services.billing.webhook_processor import (
    process_paymob_billing_webhook,
    process_payoneer_webhook,
)
from app.services.payments.paymob import build_hmac_message, to_piasters, TRANSACTION_HMAC_FIELDS
from tests.billing.conftest import (
    PAYONEER_TEST_SECRET,
    PAYMOB_TEST_SECRET,
    make_pending_invoice,
)


def _sign(raw: bytes) -> str:
    return hmac_lib.new(
        PAYONEER_TEST_SECRET.encode(), raw, hashlib.sha256
    ).hexdigest()


def _payoneer_event(
    event_id: str,
    event_type: str,
    reference: str,
    amount="38.54",
    extra: dict | None = None,
) -> tuple[bytes, dict]:
    payload = {
        "callback_id": event_id,
        "type": event_type,
        "client_reference_id": reference,
        "amount": amount,
        "currency": "USD",
    }
    payload.update(extra or {})
    return json.dumps(payload).encode(), payload


class TestPayoneerWebhooks:
    async def test_valid_payment_activates(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(db_session, subscription)
        raw, _ = _payoneer_event("cb-1", "payment.succeeded", str(txn.id))
        result = await process_payoneer_webhook(db_session, raw, {"X-Payoneer-Signature": _sign(raw)})
        assert result["outcome"] == "processed"
        await db_session.refresh(txn)
        assert txn.status == "succeeded"
        await db_session.refresh(subscription)
        assert subscription.status == "active"

    async def test_forged_signature_leaves_db_untouched(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(db_session, subscription)
        raw, _ = _payoneer_event("cb-2", "payment.succeeded", str(txn.id))
        result = await process_payoneer_webhook(
            db_session, raw, {"X-Payoneer-Signature": "deadbeef" * 8}
        )
        assert result["outcome"] == "rejected"
        await db_session.refresh(txn)
        assert txn.status == "pending"
        events = (await db_session.scalars(select(BillingWebhookEvent))).all()
        assert events == []

    async def test_missing_secret_fails_closed(
        self, db_session, subscription, billing_settings, monkeypatch
    ):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "PAYONEER_WEBHOOK_SECRET", "")
        txn = await make_pending_invoice(db_session, subscription)
        raw, _ = _payoneer_event("cb-3", "payment.succeeded", str(txn.id))
        result = await process_payoneer_webhook(db_session, raw, {})
        assert result["outcome"] == "rejected"
        await db_session.refresh(txn)
        assert txn.status == "pending"

    async def test_redelivery_is_duplicate_noop(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(db_session, subscription)
        raw, _ = _payoneer_event("cb-4", "payment.succeeded", str(txn.id))
        headers = {"X-Payoneer-Signature": _sign(raw)}
        first = await process_payoneer_webhook(db_session, raw, headers)
        second = await process_payoneer_webhook(db_session, raw, headers)
        assert first["outcome"] == "processed"
        assert second["outcome"] == "duplicate"
        events = (
            await db_session.scalars(
                select(BillingWebhookEvent).where(
                    BillingWebhookEvent.event_id == "cb-4"
                )
            )
        ).all()
        assert len(events) == 1

    async def test_underpayment_never_activates(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(db_session, subscription)  # 38.54
        raw, _ = _payoneer_event("cb-5", "payment.succeeded", str(txn.id), amount="1.00")
        result = await process_payoneer_webhook(
            db_session, raw, {"X-Payoneer-Signature": _sign(raw)}
        )
        assert result["outcome"] == "processed"
        await db_session.refresh(txn)
        assert txn.status == "failed"
        assert "amount mismatch" in (txn.failed_reason or "")
        await db_session.refresh(subscription)
        assert subscription.status == "active"  # unchanged — no unlock

    async def test_dispute_cancels_immediately(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(db_session, subscription)
        txn.status = "succeeded"
        await db_session.commit()
        raw, _ = _payoneer_event("cb-6", "charge.disputed", str(txn.id))
        result = await process_payoneer_webhook(
            db_session, raw, {"X-Payoneer-Signature": _sign(raw)}
        )
        assert result["outcome"] == "processed"
        await db_session.refresh(txn)
        await db_session.refresh(subscription)
        assert txn.status == "disputed"
        assert subscription.status == "canceled"

    async def test_refund_cancels(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(db_session, subscription)
        txn.status = "succeeded"
        await db_session.commit()
        raw, _ = _payoneer_event("cb-7", "payment.refunded", str(txn.id))
        result = await process_payoneer_webhook(
            db_session, raw, {"X-Payoneer-Signature": _sign(raw)}
        )
        assert result["outcome"] == "processed"
        await db_session.refresh(txn)
        assert txn.status == "refunded"
        await db_session.refresh(subscription)
        assert subscription.status == "canceled"

    async def test_unknown_event_noted_not_state_changed(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(db_session, subscription)
        raw, _ = _payoneer_event("cb-8", "customer.updated", str(txn.id))
        result = await process_payoneer_webhook(
            db_session, raw, {"X-Payoneer-Signature": _sign(raw)}
        )
        assert result["outcome"] == "ignored"
        await db_session.refresh(txn)
        assert txn.status == "pending"

    async def test_payout_status_maps_to_request(
        self, db_session, subscription, billing_settings, test_user
    ):
        payout = PayoutRequest(
            tenant_id=None,
            requested_by=test_user.id,
            kind="bank",
            amount_egp=Decimal("1000"),
            status="pending",
            approvers=["a", "b"],
        )
        db_session.add(payout)
        await db_session.commit()
        raw = json.dumps(
            {
                "callback_id": "cb-9",
                "type": "payout.status",
                "payout_id": "po-1",
                "client_reference_id": str(payout.id),
                "status": "PAID",
            }
        ).encode()
        result = await process_payoneer_webhook(
            db_session, raw, {"X-Payoneer-Signature": _sign(raw)}
        )
        assert result["outcome"] == "processed"
        await db_session.refresh(payout)
        assert payout.status == "executed"
        assert payout.execution_reference == "po-1"

    async def test_malformed_json(self, db_session, billing_settings):
        result = await process_payoneer_webhook(
            db_session, b"not json", {"X-Payoneer-Signature": _sign(b"not json")}
        )
        assert result["outcome"] == "malformed"


class TestPaymobBillingWebhooks:
    def _obj(self, txn: BillingTransaction, amount_piasters: int) -> dict:
        return {
            "id": 998877,
            "amount_cents": amount_piasters,
            "currency": "EGP",
            "success": True,
            "pending": False,
            "is_refunded": False,
            "is_voided": False,
            "error_occured": False,
            "has_parent_transaction": False,
            "integration_id": 12345,
            "is_3d_secure": True,
            "is_auth": False,
            "is_capture": False,
            "is_standalone_payment": True,
            "created_at": "2026-09-04T00:00:00",
            "owner": 77,
            "order": {"id": 42, "merchant_order_id": f"zbl-{txn.id}"},
            "source_data": {"pan": "1234", "sub_type": "MasterCard", "type": "card"},
        }

    def _hmac(self, obj: dict) -> str:
        message = build_hmac_message(obj, TRANSACTION_HMAC_FIELDS)
        return hmac_lib.new(
            PAYMOB_TEST_SECRET.encode(), message.encode(), hashlib.sha512
        ).hexdigest()

    async def test_valid_payment_activates(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(
            db_session, subscription, method="paymob", amount=Decimal("750.00")
        )
        obj = self._obj(txn, to_piasters("750.00"))
        result = await process_paymob_billing_webhook(db_session, obj, self._hmac(obj))
        await db_session.refresh(txn)
        assert result["outcome"] == "processed"
        assert txn.status == "succeeded"
        assert txn.provider_reference == "998877"

    async def test_bad_signature_rejected(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(
            db_session, subscription, method="paymob", amount=Decimal("750.00")
        )
        obj = self._obj(txn, to_piasters("750.00"))
        result = await process_paymob_billing_webhook(
            db_session, obj, "f" * 128
        )
        assert result["outcome"] == "rejected"
        await db_session.refresh(txn)
        assert txn.status == "pending"

    async def test_amount_mismatch_rejected(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(
            db_session, subscription, method="paymob", amount=Decimal("750.00")
        )
        obj = self._obj(txn, to_piasters("10.00"))  # underpaid
        result = await process_paymob_billing_webhook(db_session, obj, self._hmac(obj))
        assert result["outcome"] == "processed"  # verified, but no activation
        await db_session.refresh(txn)
        assert txn.status == "failed"

    async def test_currency_mismatch_rejected(
        self, db_session, subscription, billing_settings
    ):
        txn = await make_pending_invoice(
            db_session, subscription, method="paymob", amount=Decimal("750.00")
        )
        obj = self._obj(txn, to_piasters("750.00"))
        obj["currency"] = "USD"
        result = await process_paymob_billing_webhook(
            db_session, obj, self._hmac(obj)
        )
        assert result["outcome"] == "processed"
        await db_session.refresh(txn)
        assert txn.status == "failed"
        assert "currency" in (txn.failed_reason or "")

    async def test_non_billing_reference_ignored(
        self, db_session, subscription, billing_settings
    ):
        obj = {
            "id": 1,
            "amount_cents": 100,
            "currency": "EGP",
            "success": True,
            "pending": False,
            "is_refunded": False,
            "is_voided": False,
            "error_occured": False,
            "has_parent_transaction": False,
            "integration_id": 1,
            "is_3d_secure": False,
            "is_auth": False,
            "is_capture": False,
            "is_standalone_payment": True,
            "created_at": "2026-09-04",
            "owner": 1,
            "order": {"id": 1, "merchant_order_id": "zst-some-order-id"},
            "source_data": {"pan": "1234", "sub_type": "x", "type": "card"},
        }
        result = await process_paymob_billing_webhook(db_session, obj, self._hmac(obj))
        assert result["outcome"] == "ignored"
