"""Rate-limiting tests.

Simulates a hacker trying to:
- Brute-force login (rapid password guessing)
- Enumerate users / tenants (rapid GET requests)
- Evade rate limits by rotating IPs or user agents

The defense under test is `app.middleware.rate_limiter.RateLimiter` —
a sliding-window in-memory limiter. The FastAPI app doesn't yet wire it
into a middleware; these tests verify the limiter primitive works
correctly, so a future middleware integration will have a tested base.

NOTE: We also include an integration test that hits /api/auth/login
repeatedly. If the app later installs a rate-limit middleware on login,
this test will pass; until then, it documents the expected behavior.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.middleware.rate_limiter import RateLimiter


class TestRateLimiterPrimitive:
    """Unit-level tests for the RateLimiter primitive."""

    def test_allows_up_to_limit(self, isolated_rate_limiter):
        """First N requests within window must be allowed."""
        limiter = isolated_rate_limiter
        for i in range(5):
            allowed, remaining = limiter.check("1.2.3.4")
            assert allowed is True, f"Request {i+1} was blocked unexpectedly"
            assert remaining == 5 - (i + 1)

    def test_blocks_after_limit(self, isolated_rate_limiter):
        """After N requests, the next must be blocked."""
        limiter = isolated_rate_limiter
        for _ in range(5):
            limiter.check("1.2.3.4")
        allowed, remaining = limiter.check("1.2.3.4")
        assert allowed is False
        assert remaining == 0

    def test_separate_identifiers_are_independent(self, isolated_rate_limiter):
        """Different IPs/identifiers should have separate buckets."""
        limiter = isolated_rate_limiter
        # Exhaust IP A
        for _ in range(5):
            limiter.check("1.1.1.1")
        # IP B should still be allowed
        allowed, _ = limiter.check("2.2.2.2")
        assert allowed is True

    def test_window_resets_after_time(self):
        """After window_seconds, bucket must reset."""
        limiter = RateLimiter(limit=3, window_seconds=1)
        for _ in range(3):
            limiter.check("1.2.3.4")
        assert limiter.check("1.2.3.4")[0] is False
        # Wait for window to slide
        time.sleep(1.1)
        allowed, _ = limiter.check("1.2.3.4")
        assert allowed is True

    def test_reset_clears_single_bucket(self, isolated_rate_limiter):
        """reset(identifier) clears only that identifier."""
        limiter = isolated_rate_limiter
        for _ in range(5):
            limiter.check("1.1.1.1")
        for _ in range(5):
            limiter.check("2.2.2.2")
        # Both blocked
        assert limiter.check("1.1.1.1")[0] is False
        assert limiter.check("2.2.2.2")[0] is False
        # Reset only 1.1.1.1
        limiter.reset("1.1.1.1")
        assert limiter.check("1.1.1.1")[0] is True
        assert limiter.check("2.2.2.2")[0] is False  # still blocked

    def test_reset_all_clears_everything(self, isolated_rate_limiter):
        """reset() with no args clears all buckets."""
        limiter = isolated_rate_limiter
        for _ in range(5):
            limiter.check("1.1.1.1")
        for _ in range(5):
            limiter.check("2.2.2.2")
        limiter.reset()
        assert limiter.check("1.1.1.1")[0] is True
        assert limiter.check("2.2.2.2")[0] is True

    def test_empty_identifier_fails_open(self, isolated_rate_limiter):
        """Empty identifier should fail-open (don't crash on missing IP)."""
        limiter = isolated_rate_limiter
        allowed, _ = limiter.check("")
        assert allowed is True

    def test_invalid_limit_raises(self):
        """Constructor must reject invalid limits."""
        with pytest.raises(ValueError):
            RateLimiter(limit=0)
        with pytest.raises(ValueError):
            RateLimiter(limit=-1)

    def test_invalid_window_raises(self):
        """Constructor must reject invalid windows."""
        with pytest.raises(ValueError):
            RateLimiter(limit=5, window_seconds=0)
        with pytest.raises(ValueError):
            RateLimiter(limit=5, window_seconds=-1)


class TestRateLimitEvasionAttempts:
    """Attacker tries various tricks to evade rate limiting."""

    def test_ip_rotation_does_not_bypass_per_ip_limit(self, isolated_rate_limiter):
        """If the limiter is per-IP, rotating IPs gives each a fresh bucket.

        This is *expected* — that's why per-IP limiting alone is insufficient.
        The test documents this so we know we also need per-account limiting.
        """
        limiter = isolated_rate_limiter
        for i in range(10):
            # Each request comes from a different IP
            allowed, _ = limiter.check(f"10.0.0.{i}")
            assert allowed is True, "IP rotation defeated by per-IP limiter"

    def test_user_agent_rotation_does_not_affect_ip_limiter(self, isolated_rate_limiter):
        """Changing User-Agent must not bypass the IP-based limiter."""
        limiter = isolated_rate_limiter
        # The limiter only sees the identifier — UA is irrelevant.
        for _ in range(5):
            limiter.check("1.2.3.4")  # always same IP
        # Even with a "different" UA, IP is the same → blocked
        allowed, _ = limiter.check("1.2.3.4")
        assert allowed is False

    def test_distributed_attack_still_hits_per_ip_limit(self):
        """Multiple identifiers, each hitting their own limit — totals high."""
        limiter = RateLimiter(limit=3, window_seconds=60)
        total_allowed = 0
        for ip in [f"10.0.0.{i}" for i in range(10)]:
            for _ in range(5):
                if limiter.check(ip)[0]:
                    total_allowed += 1
        # 10 IPs * 3 allowed each = 30 total requests allowed
        assert total_allowed == 30


@pytest.mark.asyncio
class TestLoginRateLimitIntegration:
    """Integration: if a rate-limit middleware were installed on /login,
    what would the expected behavior be?

    Currently the app has NO rate limit on login. This test documents
    the desired behavior — it's marked xfail until the middleware is added.
    """

    @pytest.mark.xfail(
        reason="Rate-limit middleware not yet installed on /api/auth/login",
        strict=False,
    )
    async def test_login_rate_limit(self, client):
        """After 5 failed logins from same IP, should get 429."""
        for i in range(6):
            resp = await client.post(
                "/api/auth/login",
                json={
                    "email": "nonexistent@test.com",
                    "password": "wrong",
                },
            )
            if i < 5:
                assert resp.status_code == 401, (
                    f"Request {i}: expected 401, got {resp.status_code}"
                )
            else:
                assert resp.status_code == 429, (
                    f"Request {i}: expected 429 (rate limited), got {resp.status_code}"
                )

    @pytest.mark.xfail(
        reason="Rate-limit middleware not yet installed on /api/auth/login",
        strict=False,
    )
    async def test_rate_limit_resets_after_window(self, client):
        """After the rate-limit window, login should work again."""
        # Exhaust limit
        for _ in range(5):
            await client.post(
                "/api/auth/login",
                json={"email": "x@y.com", "password": "wrong"},
            )
        # 6th should be 429
        resp = await client.post(
            "/api/auth/login",
            json={"email": "x@y.com", "password": "wrong"},
        )
        assert resp.status_code == 429
        # Wait for window
        await asyncio.sleep(61)  # 60s window
        resp = await client.post(
            "/api/auth/login",
            json={"email": "x@y.com", "password": "wrong"},
        )
        assert resp.status_code == 401  # back to "wrong credentials"
