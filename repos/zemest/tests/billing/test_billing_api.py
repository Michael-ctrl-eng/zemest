"""Billing merchant API tests — auth, IDOR, subscribe flows, USDC check.

Post-Stripe rails: payoneer / paymob / usdc_solana. Adversarial cases:
* anonymous → 401; foreign tenant → 404 (no information leak)
* 'stripe' as payment_method → 400 (the rail no longer exists)
* subscribe returns checkout URL (fiat) or on-chain instructions (USDC)
* usdc/check settles a matched deposit via the fake chain
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.billing import PaymentMethod
from tests.billing.conftest import VALID_WALLET, make_pending_invoice


class TestPlansAndRails:
    async def test_plans_public_shape(self, client: AsyncClient):
        resp = await client.get("/api/billing/plans")
        assert resp.status_code == 200
        plans = resp.json()
        assert {p["code"] for p in plans} == {"starter", "growth", "pro"}
        for p in plans:
            assert p["price_egp"]
            assert p["price_usdc"]
            assert p["limits"]

    async def test_rails_report_post_stripe_architecture(
        self, client: AsyncClient
    ):
        resp = await client.get("/api/billing/rails")
        assert resp.status_code == 200
        body = resp.json()
        assert body["billing_enabled"] is True
        methods = [r["method"] for r in body["rails"]]
        assert methods == ["payoneer", "paymob", "usdc_solana"]
        roles = {r["method"]: r["role"] for r in body["rails"]}
        assert roles["payoneer"] == "primary"
        assert roles["paymob"] == "backup"
        assert roles["usdc_solana"] == "crypto"
        assert "stripe" not in methods

    async def test_subscription_requires_auth(self, client: AsyncClient, test_tenant):
        resp = await client.get(f"/api/billing/subscription?tenant_id={test_tenant.id}")
        assert resp.status_code in (401, 403)


class TestSubscribe:
    async def test_fiat_subscribe_returns_checkout_url(
        self, client: AsyncClient, auth_headers, test_tenant, billing_settings,
        fake_payoneer_checkout,
    ):
        resp = await client.post(
            "/api/billing/subscribe",
            headers=auth_headers,
            json={
                "tenant_id": str(test_tenant.id),
                "plan_code": "growth",
                "payment_method": "payoneer",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["payment_method"] == "payoneer"
        assert body["checkout_url"].startswith("https://checkout.example")
        assert body["subscription_status"] == "trialing"
        assert body["currency"] == "USD"
        assert body["usdc_instructions"] is None

    async def test_usdc_subscribe_returns_on_chain_instructions(
        self, client: AsyncClient, auth_headers, test_tenant, billing_settings
    ):
        resp = await client.post(
            "/api/billing/subscribe",
            headers=auth_headers,
            json={
                "tenant_id": str(test_tenant.id),
                "plan_code": "growth",
                "payment_method": "usdc_solana",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["payment_method"] == "usdc_solana"
        assert body["checkout_url"] is None
        usdc = body["usdc_instructions"]
        assert usdc["network"] == "solana"
        assert usdc["deposit_address"] == VALID_WALLET
        assert usdc["amount_usdc"] == "37.000000"
        assert usdc["amount_micro"] == 37_000_000
        assert usdc["reference_memo"].startswith("zm-")
        assert "USDC" in usdc["note"]

    async def test_stripe_method_rejected(
        self, client: AsyncClient, auth_headers, test_tenant, billing_settings
    ):
        resp = await client.post(
            "/api/billing/subscribe",
            headers=auth_headers,
            json={
                "tenant_id": str(test_tenant.id),
                "plan_code": "growth",
                "payment_method": "stripe",
            },
        )
        assert resp.status_code == 400
        assert "payment_method" in resp.json()["detail"]

    async def test_unknown_plan_404(
        self, client: AsyncClient, auth_headers, test_tenant, billing_settings
    ):
        resp = await client.post(
            "/api/billing/subscribe",
            headers=auth_headers,
            json={
                "tenant_id": str(test_tenant.id),
                "plan_code": "enterprise-ultra",
                "payment_method": "payoneer",
            },
        )
        assert resp.status_code == 404

    async def test_foreign_tenant_404_idor(
        self, client: AsyncClient, second_auth_headers, test_tenant,
        billing_settings,
    ):
        resp = await client.post(
            "/api/billing/subscribe",
            headers=second_auth_headers,
            json={
                "tenant_id": str(test_tenant.id),  # owned by test_user
                "plan_code": "growth",
                "payment_method": "payoneer",
            },
        )
        assert resp.status_code == 404

    async def test_usdc_rail_unconfigured_400(
        self, client: AsyncClient, auth_headers, test_tenant, billing_settings,
        monkeypatch,
    ):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "USDC_TREASURY_WALLET", "")
        resp = await client.post(
            "/api/billing/subscribe",
            headers=auth_headers,
            json={
                "tenant_id": str(test_tenant.id),
                "plan_code": "growth",
                "payment_method": "usdc_solana",
            },
        )
        assert resp.status_code == 400
        assert "not configured" in resp.json()["detail"]


class TestSubscriptionLifecycle:
    async def test_cancel_and_reactivate(
        self, client: AsyncClient, auth_headers, test_tenant, subscription,
        billing_settings,
    ):
        resp = await client.post(
            "/api/billing/cancel",
            headers=auth_headers,
            json={"tenant_id": str(test_tenant.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["cancel_at_period_end"] is True
        assert resp.json()["status"] == "active"

        resp = await client.post(
            "/api/billing/reactivate",
            headers=auth_headers,
            json={"tenant_id": str(test_tenant.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["cancel_at_period_end"] is False

    async def test_transactions_listed(
        self, client: AsyncClient, auth_headers, test_tenant, subscription,
        billing_settings,
    ):
        resp = await client.get(
            f"/api/billing/transactions?tenant_id={test_tenant.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_subscription_status(
        self, client: AsyncClient, auth_headers, test_tenant, subscription,
        billing_settings,
    ):
        resp = await client.get(
            f"/api/billing/subscription?tenant_id={test_tenant.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "active"
        assert body["plan_code"] == "starter"
        assert body["payment_method"] == "payoneer"


class TestUsdcCheck:
    async def test_check_settles_matched_deposit(
        self, db_session, client: AsyncClient, auth_headers, test_tenant,
        subscription, billing_settings, fake_usdc_provider, fake_chain,
        billing_plan,
    ):
        txn = await make_pending_invoice(
            db_session, subscription,
            method=PaymentMethod.USDC_SOLANA,
            amount_usdc=billing_plan.price_usdc,
            solana_reference="zm-api-check",
        )
        fake_chain.add_deposit(
            int(billing_plan.price_usdc * Decimal(1_000_000)),
            reference="zm-api-check",
        )
        resp = await client.post(
            "/api/billing/usdc/check",
            headers=auth_headers,
            json={"tenant_id": str(test_tenant.id)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["settled_now"] is True
        assert body["swept_settled"] == 1
        assert body["pending_invoice_id"] is None
        await db_session.refresh(txn)
        assert txn.status == "succeeded"
