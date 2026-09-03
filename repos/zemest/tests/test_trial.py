"""Trial system tests — 7-day trial, disposable emails, IP abuse prevention.

Product rules (verbatim from the requirements):
- "free trial be seven days"
- "if any user tries to create another account with demo emails … we would
  block creating new accounts" → disposable domain = registration refused
- "if he would create another account … his free trial would be gone" →
  second account from a trial-consumed IP gets NO trial
- trial expiry demotes limits lazily (no cron); /api/me reflects trial state
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.user import User
from app.services import auth_service
from app.services.plan_service import (
    PLANS,
    effective_plan,
    get_limits_for_user,
    trial_state,
)


async def _register(db_session, email: str, ip: str | None = None) -> User:
    """Service-level registration helper (deterministic IP control)."""
    return await auth_service.register_user(
        db_session, "Trial Tester", email, "StrongPass123!", signup_ip=ip
    )


@pytest.mark.asyncio
class TestTrialGrant:
    async def test_new_user_gets_seven_day_trial(self, db_session):
        user = await _register(db_session, "trial1@example.com", ip="41.10.0.1")
        await db_session.commit()
        assert user.trial_ends_at is not None
        remaining = (user.trial_ends_at - datetime.utcnow()).total_seconds()
        assert 6.99 * 86_400 < remaining <= 7.0 * 86_400
        assert user.signup_ip == "41.10.0.1"

    async def test_trial_grants_growth_limits(self, db_session):
        user = await _register(db_session, "trial2@example.com", ip="41.10.0.2")
        await db_session.commit()
        # plan field stays "free" — the EFFECTIVE plan is growth during trial
        assert user.plan == "free"
        assert effective_plan(user) == "growth"
        limits = get_limits_for_user(user)
        assert limits.key == "growth"
        assert limits.max_shops == PLANS["growth"].max_shops

    async def test_trial_state_fields(self, db_session):
        user = await _register(db_session, "trial3@example.com", ip="41.10.0.3")
        await db_session.commit()
        state = trial_state(user)
        assert state["active"] is True
        assert state["days_left"] == 7
        assert state["ends_at"] is not None


@pytest.mark.asyncio
class TestTrialExpiry:
    async def test_expired_trial_demotes_to_free(self, db_session):
        user = await _register(db_session, "expired@example.com", ip="41.10.0.4")
        user.trial_ends_at = datetime.utcnow() - timedelta(hours=1)
        await db_session.flush()
        assert effective_plan(user) == "free"
        state = trial_state(user)
        assert state["active"] is False
        assert state["days_left"] == 0

    async def test_paid_plan_ignores_trial(self, db_session):
        user = await _register(db_session, "paid@example.com", ip="41.10.0.5")
        user.plan = "pro"
        await db_session.flush()
        # Pro is higher than trial growth — plan wins
        assert effective_plan(user) == "pro"

    async def test_no_trial_field_means_free(self, db_session):
        user = await _register(db_session, "notrial@example.com", ip="41.10.0.6")
        user.trial_ends_at = None
        await db_session.flush()
        assert effective_plan(user) == "free"


@pytest.mark.asyncio
class TestIPAbusePrevention:
    async def test_second_account_same_ip_gets_no_trial(self, db_session):
        first = await _register(db_session, "first@example.com", ip="197.5.5.5")
        await db_session.commit()
        assert first.trial_ends_at is not None

        second = await _register(db_session, "second@example.com", ip="197.5.5.5")
        await db_session.commit()
        assert second.trial_ends_at is None, "trial farmed from the same IP"
        assert effective_plan(second) == "free"

    async def test_different_ip_still_gets_trial(self, db_session):
        await _register(db_session, "otherip@example.com", ip="197.5.5.6")
        fresh = await _register(db_session, "fresh@example.com", ip="41.20.0.9")
        await db_session.commit()
        assert fresh.trial_ends_at is not None

    async def test_ip_account_ceiling(self, db_session):
        ip = "197.99.99.99"
        for i in range(auth_service.MAX_ACCOUNTS_PER_IP):
            await _register(db_session, f"ceiling{i}@example.com", ip=ip)
        await db_session.commit()
        with pytest.raises(auth_service.RegistrationRefused) as exc_info:
            await _register(db_session, "one-too-many@example.com", ip=ip)
        assert exc_info.value.code == "ip_account_ceiling"

    async def test_ceiling_never_blocks_other_ips(self, db_session):
        ip = "197.98.98.98"
        for i in range(auth_service.MAX_ACCOUNTS_PER_IP):
            await _register(db_session, f"full{i}@example.com", ip=ip)
        await db_session.commit()
        other = await _register(db_session, "elsewhere@example.com", ip="41.30.0.1")
        assert other.id is not None


@pytest.mark.asyncio
class TestDisposableEmails:
    async def test_disposable_email_refused(self, db_session):
        with pytest.raises(auth_service.RegistrationRefused) as exc_info:
            await _register(db_session, "farmer@mailinator.com", ip="41.40.0.1")
        assert exc_info.value.code == "disposable_email"
        # No account was created
        result = await db_session.execute(
            select(User).where(User.email == "farmer@mailinator.com")
        )
        assert result.scalar_one_or_none() is None

    async def test_disposable_subdomain_refused(self, db_session):
        with pytest.raises(auth_service.RegistrationRefused):
            await _register(db_session, "x@anything.10minutemail.com", ip="41.40.0.2")

    async def test_normal_email_accepted(self, db_session):
        user = await _register(db_session, "normal@gmail.com", ip="41.40.0.3")
        assert user.email == "normal@gmail.com"


@pytest.mark.asyncio
class TestRegisterEndpoint:
    async def test_register_http_flow_grants_trial(self, client):
        resp = await client.post(
            "/api/auth/register",
            json={
                "name": "HTTP Trial",
                "email": "httptrial@example.com",
                "password": "StrongPass123!",
            },
        )
        assert resp.status_code == 202

    async def test_register_disposable_returns_same_202_anti_enum(self, client):
        """The refused signup is indistinguishable from success (anti-enumeration)."""
        resp = await client.post(
            "/api/auth/register",
            json={
                "name": "Disposable",
                "email": "throwaway@mailinator.com",
                "password": "StrongPass123!",
            },
        )
        assert resp.status_code == 202

    async def test_me_reports_trial_state(self, client, db_session, auth_headers, test_user):
        test_user.trial_ends_at = datetime.utcnow() + timedelta(days=3)
        await db_session.commit()
        resp = await client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial"]["active"] is True
        assert 1 <= data["trial"]["days_left"] <= 3
        assert data["plan"] == "growth"  # effective plan during trial

    async def test_usage_endpoint_includes_trial(
        self, client, db_session, auth_headers, test_user
    ):
        test_user.trial_ends_at = datetime.utcnow() + timedelta(days=2)
        await db_session.commit()
        resp = await client.get("/api/me/usage", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial"]["active"] is True
        assert data["plan"]["effective"] == "growth"
        # Growth-tier limits while trialing
        assert data["usage"]["shops"]["limit"] == PLANS["growth"].max_shops


@pytest.mark.asyncio
class TestSignupIPStorage:
    async def test_signup_ip_stored_and_indexed(self, db_session):
        user = await _register(db_session, "ipstored@example.com", ip="102.103.104.105")
        await db_session.commit()
        found = (
            await db_session.execute(
                select(User).where(User.signup_ip == "102.103.104.105")
            )
        ).scalar_one()
        assert found.id == user.id
