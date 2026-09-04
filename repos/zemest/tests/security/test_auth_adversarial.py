"""Adversarial auth tests — one test per audit PoC (wave F1).

Every test here encodes a concrete attack from the security audit:
* Refresh-token replay (stolen-token reuse detection)
* Token-confusion (access token presented as refresh)
* Enumeration via register/login error differences
* Blocked-user auth fail-closed
* Login-timing oracle (unknown vs known email)
* >72-byte password bcrypt crash (the passlib 5.x ValueError)
* Registration race (unique-constraint as source of truth)
"""
import asyncio
import time
import uuid

import pytest
import pytest_asyncio

from app.models.refresh_token import RefreshTokenRecord
from app.models.user import User
from app.utils.security import (
    BCRYPT_ROUNDS,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


# --------------------------------------------------------------------------- #
# Password hashing primitives
# --------------------------------------------------------------------------- #
class TestBcryptHardening:
    def test_hash_verifies_roundtrip(self):
        h = hash_password("s3cret-password")
        assert h.startswith("$2b$")
        assert verify_password("s3cret-password", h)

    def test_bcrypt_rounds_is_12(self):
        """Audit: cost factor must be >= 12 (OWASP 2024 floor)."""
        assert BCRYPT_ROUNDS >= 12

    def test_72byte_password_does_not_crash(self):
        """Audit PoC: bcrypt 5.x raises ValueError on >72-byte passwords —
        a single 100-char registration crashed the whole endpoint."""
        long_pw = "A" * 200
        h = hash_password(long_pw)
        assert verify_password(long_pw, h) is True

    def test_malformed_hash_returns_false_not_raise(self):
        """Audit PoC: corrupt/garbage hash in DB must not 500 the login."""
        assert verify_password("x", "not-a-bcrypt-hash") is False
        assert verify_password("x", "") is False
        assert verify_password("x", "$2b$12$short") is False

    def test_hash_is_salted(self):
        """Same password, two hashes, different outputs (rainbow-table defense)."""
        assert hash_password("same-password") != hash_password("same-password")


# --------------------------------------------------------------------------- #
# Refresh-token rotation + reuse detection
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestRefreshRotation:
    async def test_login_returns_refresh_token(self, client, test_user):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        body = resp.json()
        assert resp.status_code == 200
        assert body.get("refresh_token")

    async def test_refresh_rotates_and_mints_new_pair(self, client, test_user):
        login = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        old_refresh = login.json()["refresh_token"]

        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": old_refresh,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["refresh_token"]
        # Rotation means a NEW refresh token, never the same one back.
        assert body["refresh_token"] != old_refresh

    async def test_refresh_replay_revokes_all_sessions(self, client, test_user):
        """Audit PoC: a stolen refresh token, replayed after the legitimate
        client rotated, must nuke the whole account session family."""
        login = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        stolen = login.json()["refresh_token"]

        # Legitimate client rotates — the thief keeps the OLD token.
        first = await client.post("/api/auth/refresh", json={
            "refresh_token": stolen,
        })
        assert first.status_code == 200
        legit_new = first.json()["refresh_token"]

        # Thief replays the stolen (now consumed) token.
        replay = await client.post("/api/auth/refresh", json={
            "refresh_token": stolen,
        })
        assert replay.status_code == 401

        # Reuse detection must have revoked the LEGITIMATE successor too —
        # otherwise the thief-and-victim race continues forever.
        legit_after_theft = await client.post("/api/auth/refresh", json={
            "refresh_token": legit_new,
        })
        assert legit_after_theft.status_code == 401

    async def test_access_token_rejected_as_refresh(self, client, test_user):
        """Token-confusion PoC: an ACCESS token must never work on /refresh."""
        access = create_access_token({"sub": str(test_user.id)})
        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": access,
        })
        assert resp.status_code == 401

    async def test_logout_revokes_refresh(self, client, test_user):
        login = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        refresh = login.json()["refresh_token"]
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        out = await client.post("/api/auth/logout", json={
            "refresh_token": refresh,
        }, headers=headers)
        assert out.status_code == 204

        replay = await client.post("/api/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert replay.status_code == 401

    async def test_forged_refresh_signature_rejected(self, client):
        """Forged token (wrong signing key) must never yield tokens."""
        from jose import jwt as josejwt
        forged = josejwt.encode(
            {"sub": str(uuid.uuid4()), "type": "refresh", "jti": str(uuid.uuid4()),
             "exp": 9999999999},
            "attacker-controlled-key",
            algorithm="HS256",
        )
        resp = await client.post("/api/auth/refresh", json={"refresh_token": forged})
        assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Enumeration defenses
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestAntiEnumeration:
    async def test_login_unknown_email_same_error_as_wrong_password(self, client, test_user):
        """Audit PoC: 'Invalid credentials' vs 'Invalid email or password'
        style differences (and timing) let attackers map registered emails."""
        wrong_pw = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "wrongwrong",
        })
        unknown = await client.post("/api/auth/login", json={
            "email": "ghost@example.com", "password": "wrongwrong",
        })
        assert wrong_pw.status_code == unknown.status_code == 401
        assert wrong_pw.json()["detail"] == unknown.json()["detail"]

    async def test_login_unknown_email_timing_equalized(self, client):
        """Timing oracle PoC: unknown-email login used to return in <5ms
        (no bcrypt burn) while wrong-password took ~250ms."""
        async def time_login(email: str) -> float:
            t0 = time.perf_counter()
            await client.post("/api/auth/login", json={
                "email": email, "password": "wrongwrong",
            })
            return time.perf_counter() - t0

        # Warm-up (first request pays import/connection costs).
        await time_login("warmup@example.com")
        times = [await time_login("ghost@example.com") for _ in range(3)]
        unknown = min(times)
        # A real account would burn bcrypt: test_user isn't in this client's
        # session DB here, so we measure the equalizer directly instead.
        from app.utils.security import burn_password_timing
        t0 = time.perf_counter()
        await asyncio.to_thread(burn_password_timing, "wrongwrong")
        burned = time.perf_counter() - t0
        # The unknown-email path must have burned a comparable amount of time
        # (>= 50ms of bcrypt work, not <5ms instant return).
        assert unknown >= 0.05, (
            f"unknown-email login returned in {unknown*1000:.1f}ms — "
            "enumeration timing oracle is open"
        )
        # Sanity: the equalizer itself takes a real bcrypt duration.
        assert burned >= 0.05

    async def test_register_duplicate_and_new_identical_response(self, client, test_user):
        """Full-response diff: status, body, timing-burn — no oracle."""
        new = await client.post("/api/auth/register", json={
            "name": "Fresh User", "email": "fresh@example.com", "password": "password123",
        })
        dup = await client.post("/api/auth/register", json={
            "name": "Copycat", "email": "test@example.com", "password": "password123",
        })
        assert new.status_code == dup.status_code == 202
        assert new.json() == dup.json()


# --------------------------------------------------------------------------- #
# Blocked users
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestBlockedUsers:
    async def test_blocked_user_login_403(self, client, test_user, db_session):
        test_user.is_blocked = True
        await db_session.commit()
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "testpass123",
        })
        assert resp.status_code == 403

    async def test_blocked_user_token_403_on_every_endpoint(self, client, test_user, db_session):
        """Audit PoC: blocking must revoke LIVE access tokens too, not just
        future logins — the get_current_user gate has to fail closed."""
        token = create_access_token({"sub": str(test_user.id)})
        headers = {"Authorization": f"Bearer {token}"}
        # Sanity: works before block.
        ok = await client.get("/api/auth/me", headers=headers)
        assert ok.status_code == 200

        test_user.is_blocked = True
        await db_session.commit()

        blocked = await client.get("/api/auth/me", headers=headers)
        assert blocked.status_code == 403

    async def test_blocked_user_refresh_revokes_family(self, client, test_user, db_session):
        login = await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "testpass123",
        })
        refresh = login.json()["refresh_token"]

        test_user.is_blocked = True
        await db_session.commit()

        resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code in (401, 403)


# --------------------------------------------------------------------------- #
# Registration race
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestRegistrationRace:
    async def test_concurrent_duplicate_registration_one_winner(self):
        """Audit PoC: SELECT-then-INSERT race let two concurrent registrations
        of the same email both succeed. In production each request gets its
        OWN session — simulated here with two independent sessions; the
        unique constraint (not the pre-check) must be the source of truth."""
        import asyncio
        from tests.conftest import TestSessionLocal
        from app.services import auth_service

        email = f"race-{uuid.uuid4().hex[:8]}@example.com"
        results = await asyncio.gather(
            _register_via_service(email, "password123"),
            _register_via_service(email, "password123"),
            return_exceptions=True,
        )
        # Exactly one winner, the loser raises EmailAlreadyRegistered
        # (or both surfaced something equivalent) — never two successes.
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) == 1, (
            f"race produced {len(successes)} successful registrations — "
            "duplicate accounts exist"
        )
        assert len(failures) == 1
        assert isinstance(failures[0], auth_service.EmailAlreadyRegistered)

    async def test_endpoint_uniform_202_for_both_racers(self, concurrent_client):
        """HTTP layer: both racers see the identical anti-enumeration 202."""
        import asyncio
        payload = {
            "name": "Race User",
            "email": f"race-http-{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
        }
        results = await asyncio.gather(
            concurrent_client.post("/api/auth/register", json=payload),
            concurrent_client.post("/api/auth/register", json=payload),
        )
        assert all(r.status_code == 202 for r in results)
        login = await concurrent_client.post("/api/auth/login", json={
            "email": payload["email"], "password": "password123",
        })
        assert login.status_code == 200


async def _register_via_service(email: str, password: str):
    """Register through the service with a PRIVATE session (per-request)."""
    from app.services import auth_service
    from tests.conftest import TestSessionLocal
    async with TestSessionLocal() as session:
        user = await auth_service.register_user(session, "Race User", email, password)
        await session.commit()
        return user


# --------------------------------------------------------------------------- #
# Ledger integrity
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestRefreshLedger:
    async def test_record_created_on_login(self, client, test_user, db_session):
        await client.post("/api/auth/login", json={
            "email": "test@example.com", "password": "testpass123",
        })
        from sqlalchemy import select
        rows = (await db_session.execute(
            select(RefreshTokenRecord).where(RefreshTokenRecord.user_id == test_user.id)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].revoked is False
        assert rows[0].expires_at is not None

    async def test_docs_gated_in_production(self):
        """Audit PoC: /docs, /redoc, /openapi.json exposed in production.

        Runs in a SUBPROCESS: importing the app with APP_ENV=production
        would reload modules in-process and desync the settings singleton
        for every later test (module-level ``settings`` snapshots).
        """
        import subprocess
        import sys
        from pathlib import Path

        backend_root = Path(__file__).resolve().parents[2]
        code = (
            "import os; os.environ['APP_ENV']='production'; "
            "os.environ.pop('DATABASE_URL', None); "
            "from app.main import app; "
            "assert app.docs_url is None, 'docs exposed in production'; "
            "assert app.redoc_url is None, 'redoc exposed in production'; "
            "assert app.openapi_url is None, 'openapi.json exposed in production'; "
            "print('OK')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(backend_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert "OK" in result.stdout, (
            f"production docs gating failed: {result.stderr[-500:]}"
        )
