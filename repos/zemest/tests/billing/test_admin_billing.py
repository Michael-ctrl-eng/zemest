"""Admin billing API tests — treasury, 2-approval withdrawals, gating.

Covers:
* superadmin-only gate (403 for regular users / 401 anonymous)
* USDC treasury balance + payout queue
* withdrawal lifecycle: create → pending (1st) → approved (2nd DISTINCT)
  → execute with on-chain signature verification
* dispute hold: payouts frozen while disputed invoices are open
* the request creator cannot be the first approver
* bank withdrawals + reserve floor
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.billing import (
    BillingSubscription,
    BillingTransaction,
    PayoutRequest,
)
from tests.billing.conftest import VALID_WALLET, make_pending_invoice


@pytest_asyncio.fixture
async def superadmin(db_session):
    from app.models.user import User
    from app.utils.security import hash_password

    admin = User(
        id=uuid.uuid4(),
        name="Super Admin",
        email="superadmin@example.com",
        hashed_password=hash_password("superpass123"),
        is_superadmin=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest_asyncio.fixture
async def superadmin_headers(superadmin):
    from app.utils.security import create_access_token

    token = create_access_token({"sub": str(superadmin.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_admin(db_session):
    from app.models.user import User
    from app.utils.security import hash_password

    admin = User(
        id=uuid.uuid4(),
        name="Second Admin",
        email="second-admin@example.com",
        hashed_password=hash_password("superpass456"),
        is_superadmin=True,
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest_asyncio.fixture
async def second_admin_headers(second_admin):
    from app.utils.security import create_access_token

    token = create_access_token({"sub": str(second_admin.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_treasury_chain(monkeypatch, billing_settings):
    """Offline treasury: fixed balance + signature verification."""
    from app.services.billing.providers.usdc_solana import UsdcSolanaProvider

    async def fake_balance(self):
        return Decimal("500.000000")

    async def fake_verify(self, signature: str):
        if signature == "bad-sig":
            return None
        return {"signature": signature, "confirmations": 65, "status": "finalized"}

    monkeypatch.setattr(UsdcSolanaProvider, "get_treasury_balance", fake_balance)
    monkeypatch.setattr(UsdcSolanaProvider, "verify_payout_execution", fake_verify)
    return None


class TestAdminGate:
    async def test_anonymous_401(self, client: AsyncClient):
        resp = await client.get("/api/admin/billing/overview")
        assert resp.status_code in (401, 403)

    async def test_regular_user_403(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.get("/api/admin/billing/overview", headers=auth_headers)
        assert resp.status_code == 403

    async def test_superadmin_200(
        self, client: AsyncClient, superadmin_headers, billing_settings
    ):
        resp = await client.get(
            "/api/admin/billing/overview", headers=superadmin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "mrr_egp" in body
        assert "open_disputes" in body
        assert body["payouts_held"] is False


class TestTreasury:
    async def test_treasury_status(
        self, client: AsyncClient, superadmin_headers, billing_settings,
        fake_treasury_chain,
    ):
        resp = await client.get(
            "/api/admin/billing/treasury", headers=superadmin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["usdc_balance"] == "500.000000"
        assert body["treasury_wallet"] == VALID_WALLET
        assert body["min_reserve_usdc"] is not None
        assert body["bank_label"]


class TestWithdrawalWorkflow:
    async def test_full_lifecycle(
        self, client: AsyncClient, superadmin, superadmin_headers,
        second_admin_headers, billing_settings, fake_treasury_chain,
    ):
        # 1. create
        resp = await client.post(
            "/api/admin/billing/withdrawals",
            headers=superadmin_headers,
            json={
                "kind": "usdc",
                "amount_usdc": "100.0",
                "destination": {"wallet": VALID_WALLET, "network": "solana"},
            },
        )
        assert resp.status_code == 200
        payout = resp.json()
        assert payout["status"] == "request"
        payout_id = payout["id"]

        # 2. creator cannot be the first approver
        resp = await client.post(
            f"/api/admin/billing/withdrawals/{payout_id}/approve",
            headers=superadmin_headers,
        )
        assert resp.status_code == 409

        # 3. first (distinct) approval → pending
        resp = await client.post(
            f"/api/admin/billing/withdrawals/{payout_id}/approve",
            headers=second_admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

        # 4. execute before full approval → 409
        resp = await client.post(
            f"/api/admin/billing/withdrawals/{payout_id}/execute",
            headers=second_admin_headers,
            json={"execution_reference": "GoodSignature123"},
        )
        assert resp.status_code == 409

        # 5. second approval → approved
        resp = await client.post(
            f"/api/admin/billing/withdrawals/{payout_id}/approve",
            headers=superadmin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # 6. execute with on-chain signature verification
        resp = await client.post(
            f"/api/admin/billing/withdrawals/{payout_id}/execute",
            headers=superadmin_headers,
            json={"execution_reference": "GoodSignature123"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "executed"
        assert resp.json()["execution_reference"] == "GoodSignature123"

    async def test_execute_with_unknown_signature_rejected(
        self, client: AsyncClient, superadmin, superadmin_headers,
        second_admin_headers, db_session, billing_settings, fake_treasury_chain,
    ):
        payout = PayoutRequest(
            tenant_id=None,
            requested_by=superadmin.id,
            kind="usdc",
            amount_usdc=Decimal("10"),
            status="approved",
            approvers=["a", "b"],
        )
        db_session.add(payout)
        await db_session.commit()
        resp = await client.post(
            f"/api/admin/billing/withdrawals/{payout.id}/execute",
            headers=superadmin_headers,
            json={"execution_reference": "bad-sig"},
        )
        assert resp.status_code == 400
        assert "not found on-chain" in resp.json()["detail"]

    async def test_reserve_floor_enforced(
        self, client: AsyncClient, superadmin_headers, billing_settings,
        fake_treasury_chain,
    ):
        # Balance 500, reserve 10 → a 600 withdrawal must fail.
        resp = await client.post(
            "/api/admin/billing/withdrawals",
            headers=superadmin_headers,
            json={"kind": "usdc", "amount_usdc": "600.0"},
        )
        assert resp.status_code == 409
        assert "reserve" in resp.json()["detail"]

    async def test_bank_withdrawal(
        self, client: AsyncClient, superadmin_headers, second_admin_headers,
        billing_settings,
    ):
        resp = await client.post(
            "/api/admin/billing/withdrawals",
            headers=superadmin_headers,
            json={
                "kind": "bank",
                "amount_egp": "25000.00",
                "destination": {"bank_label": "CIB ****1234"},
            },
        )
        assert resp.status_code == 200
        payout_id = resp.json()["id"]
        await client.post(
            f"/api/admin/billing/withdrawals/{payout_id}/approve",
            headers=second_admin_headers,
        )
        resp = await client.post(
            f"/api/admin/billing/withdrawals/{payout_id}/approve",
            headers=superadmin_headers,
        )
        # Bank execution: receipt recorded as-is (bank portal is truth).
        resp = await client.post(
            f"/api/admin/billing/withdrawals/{payout_id}/execute",
            headers=superadmin_headers,
            json={"execution_reference": "TRX-99881"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "executed"


class TestCompGrant:
    async def test_grant_activates_without_rails(
        self, db_session, client: AsyncClient, superadmin_headers, test_tenant,
        billing_settings, billing_plan,
    ):
        # No payoneer/paymob patching: the grant must not touch any rail.
        resp = await client.post(
            "/api/admin/billing/grant",
            headers=superadmin_headers,
            json={
                "tenant_id": str(test_tenant.id),
                "plan_code": "growth",
                "reason": "partnership comp",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "active"
        assert body["plan_code"] == "growth"

        sub = (
            await db_session.scalars(
                select(BillingSubscription).where(
                    BillingSubscription.tenant_id == test_tenant.id
                )
            )
        ).first()
        assert sub.status == "active"
        assert sub.payment_method == "comp"
        comp_txn = (
            await db_session.scalars(
                select(BillingTransaction).where(
                    BillingTransaction.subscription_id == sub.id
                )
            )
        ).all()
        assert len(comp_txn) == 1
        assert comp_txn[0].status == "succeeded"
        assert comp_txn[0].payment_method == "comp"

    async def test_grant_requires_superadmin(
        self, client: AsyncClient, auth_headers, test_tenant, billing_settings,
        billing_plan,
    ):
        resp = await client.post(
            "/api/admin/billing/grant",
            headers=auth_headers,
            json={
                "tenant_id": str(test_tenant.id),
                "plan_code": "growth",
                "reason": "should be forbidden",
            },
        )
        assert resp.status_code == 403


# The dispute-hold test needs the db_session fixture — defined as its own
# async test class below.
@pytest.mark.asyncio
class TestDisputeHoldDb:
    async def test_disputes_freeze_new_withdrawals(
        self, db_session, client: AsyncClient, superadmin_headers, subscription,
        billing_settings, fake_treasury_chain,
    ):
        txn = await make_pending_invoice(db_session, subscription)
        txn.status = "disputed"
        await db_session.commit()

        resp = await client.post(
            "/api/admin/billing/withdrawals",
            headers=superadmin_headers,
            json={"kind": "usdc", "amount_usdc": "50.0"},
        )
        assert resp.status_code == 409
        assert "HELD" in resp.json()["detail"]
