"""Plans & limits module tests — enforcement, quotas, multi-shop.

Verifies:
- Shop creation gated by plan (free=1, growth=5, pro=25) with 402 + upgrade hint
- Multi-shop works on growth/pro (each shop its own channel set)
- LLM budget exhausted → honest holding reply, no LLM call (A5-H1 ceiling)
- Usage endpoint reports used/limit per resource
- Plan change endpoint + catalog
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.ai.agent import process_customer_message
from app.models.tenant import Tenant
from app.models.token_usage import TokenUsage
from app.models.user import User
from app.services.plan_service import (
    PLANS,
    check_can_create_shop,
    count_shops,
    get_usage,
    plan_catalog,
)


async def _create_shop(client, auth_headers, name: str):
    return await client.post(
        "/api/tenants",
        json={"page_name": name},
        headers=auth_headers,
    )


@pytest.mark.asyncio
class TestPlanEnforcement:
    async def test_free_plan_one_shop_only(self, client, auth_headers, test_tenant):
        """The fixture already created 1 shop for the free-plan user — a
        second must 402 with the upgrade path."""
        resp = await _create_shop(client, auth_headers, "Second Shop")
        assert resp.status_code == 402, resp.text
        detail = resp.json()["detail"]
        assert detail["code"] == "shop_limit"
        assert detail["plan"] == "free"
        assert detail["limit"] == 1
        assert detail["current"] >= 1
        assert detail["upgrade_url"]

    async def test_growth_plan_five_shops(self, client, db_session, auth_headers, test_user, test_tenant):
        test_user.plan = "growth"
        await db_session.commit()

        # fixture tenant = shop 1; add 4 more (limit 5)
        for i in range(4):
            resp = await _create_shop(client, auth_headers, f"Growth Shop {i + 2}")
            assert resp.status_code == 200, f"shop {i + 2} rejected: {resp.text}"

        # shop 6 → 402
        resp = await _create_shop(client, auth_headers, "One Too Many")
        assert resp.status_code == 402
        assert resp.json()["detail"]["limit"] == 5

    async def test_pro_plan_25_shops(self, client, db_session, auth_headers, test_user):
        test_user.plan = "pro"
        await db_session.commit()
        count = 0
        for i in range(25):
            resp = await _create_shop(client, auth_headers, f"Pro Shop {i + 1}")
            assert resp.status_code == 200, f"shop {i + 1} rejected"
            count += 1
        assert count == 25
        resp = await _create_shop(client, auth_headers, "Shop 26")
        assert resp.status_code == 402

    async def test_multi_shop_all_functional(self, client, db_session, auth_headers, test_user):
        """Higher plans get multiple shops, each with its own channel set."""
        test_user.plan = "growth"
        await db_session.commit()

        ids = []
        for i in range(3):
            resp = await _create_shop(client, auth_headers, f"Brand {i + 1}")
            ids.append(resp.json()["id"])
        assert len(set(ids)) == 3

        # Each shop connects its own (mocked) WhatsApp channel independently.
        from unittest.mock import AsyncMock, patch
        for tid in ids:
            fake_wa = {"display_phone_number": f"+20100000000{tid[-2:]}", "verified_name": "V", "quality_rating": None}
            with patch(
                "app.api.channels._graph_get", new=AsyncMock(return_value=fake_wa)
            ):
                resp = await client.post(
                    f"/api/tenants/{tid}/channels/whatsapp",
                    json={"phone_number_id": f"PNID-{tid[:8]}", "access_token": f"WA-{tid[:8]}"},
                    headers=auth_headers,
                )
            assert resp.status_code == 200, resp.text
            assert resp.json()["connected"] is True


@pytest.mark.asyncio
class TestLLMBudgetEnforcement:
    async def test_budget_exhausted_holding_reply_no_llm_call(
        self, db_session, test_tenant, test_user
    ):
        """A5-H1: the LLM ladder finally has a ceiling — when the daily
        token budget is gone, the customer gets an honest holding reply and
        NOT a single token is spent."""
        test_user.plan = "free"  # 50k tokens/day
        await db_session.flush()

        # Burn the whole budget in the ledger.
        db_session.add(TokenUsage(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            usage_type="chat",
            model="test",
            prompt_tokens=49_000,
            completion_tokens=2_000,
            total_tokens=51_000,
        ))
        await db_session.flush()

        from unittest.mock import AsyncMock
        llm_spy = AsyncMock(side_effect=AssertionError("LLM must not be called"))
        import app.ai.agent as agent_mod
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(agent_mod, "chat_completion_with_usage", llm_spy)
            reply = await process_customer_message(
                db_session, test_tenant, "psid_budget_1", "أهلاً، السعر بكام؟"
            )

        assert reply, "customer got silence on quota exhaustion"
        assert "فريق المتجر" in reply, "not the honest holding reply"
        assert "شكراً" in reply

    async def test_budget_counts_all_usage_types(self, db_session, test_tenant, test_user):
        """chat + vision + retrieval tokens all count toward one budget."""
        from app.services.plan_service import count_day_llm_tokens
        for usage_type, tokens in (("chat", 10_000), ("vision", 5_000), ("retrieval", 2_500)):
            db_session.add(TokenUsage(
                id=uuid.uuid4(),
                tenant_id=test_tenant.id,
                usage_type=usage_type,
                model="m",
                prompt_tokens=tokens,
                completion_tokens=0,
                total_tokens=tokens,
            ))
        await db_session.flush()
        used = await count_day_llm_tokens(db_session, test_tenant)
        assert used == 17_500

    async def test_within_budget_still_calls_llm(self, db_session, test_tenant, test_user):
        from unittest.mock import AsyncMock
        from app.ai.llm_client import LLMResponse
        llm = AsyncMock(return_value=LLMResponse(
            content="أهلاً بيك! إزاي أساعدك؟", model="t",
            prompt_tokens=10, completion_tokens=10, total_tokens=20,
        ))
        import app.ai.agent as agent_mod
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(agent_mod, "chat_completion_with_usage", llm)
            reply = await process_customer_message(
                db_session, test_tenant, "psid_ok_budget", "أهلاً"
            )
        assert reply and "أهلاً" in reply


@pytest.mark.asyncio
class TestPlansAPI:
    async def test_catalog_public(self, client):
        resp = await client.get("/api/plans")
        assert resp.status_code == 200
        plans = resp.json()["plans"]
        assert {p["key"] for p in plans} == {"free", "growth", "pro"}
        by_key = {p["key"]: p for p in plans}
        assert by_key["free"]["max_shops"] == 1
        assert by_key["growth"]["max_shops"] == 5
        assert by_key["pro"]["max_shops"] == 25
        assert by_key["growth"]["price_egp_month"] > 0

    async def test_usage_endpoint(self, client, auth_headers, test_user, test_tenant):
        resp = await client.get("/api/me/usage", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"]["key"] == "free"
        assert data["usage"]["shops"]["used"] >= 1
        assert data["usage"]["shops"]["limit"] == 1
        assert data["usage"]["llm_tokens_today"]["limit"] == 50_000

    async def test_plan_change(self, client, db_session, auth_headers, test_user):
        resp = await client.post(
            "/api/me/plan", json={"plan": "growth"}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["plan"] == "growth"
        await db_session.refresh(test_user)
        assert test_user.plan == "growth"

    async def test_plan_change_invalid_rejected(self, client, auth_headers):
        resp = await client.post(
            "/api/me/plan", json={"plan": "enterprise"}, headers=auth_headers
        )
        assert resp.status_code == 422

    async def test_usage_after_upgrade_allows_shop(self, client, db_session, auth_headers, test_user, test_tenant):
        """Upgrade flow: free hits the wall → upgrade → shop creation works."""
        resp = await _create_shop(client, auth_headers, "Blocked On Free")
        assert resp.status_code == 402

        await client.post("/api/me/plan", json={"plan": "growth"}, headers=auth_headers)
        resp = await _create_shop(client, auth_headers, "Allowed On Growth")
        assert resp.status_code == 200


class TestPlanServiceUnit:
    def test_catalog_matches_constants(self):
        cat = plan_catalog()
        assert len(cat) == len(PLANS)
        for entry in cat:
            limits = PLANS[entry["key"]]
            assert entry["max_shops"] == limits.max_shops
            assert entry["max_llm_tokens_per_day"] == limits.max_llm_tokens_per_day

    def test_limits_monotonic(self):
        """Each tier is strictly more generous than the previous one — no
        'no more or no less' surprises."""
        free, growth, pro = PLANS["free"], PLANS["growth"], PLANS["pro"]
        assert growth.max_shops > free.max_shops
        assert growth.max_messages_per_month > free.max_messages_per_month
        assert growth.max_llm_tokens_per_day > free.max_llm_tokens_per_day
        assert pro.max_shops > growth.max_shops
        assert pro.max_messages_per_month > growth.max_messages_per_month
        assert pro.max_llm_tokens_per_day > growth.max_llm_tokens_per_day
